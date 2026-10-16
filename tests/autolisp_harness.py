"""Interpretador AutoLISP mínimo para testes de integração do OXCAD.

Executa os arquivos .lsp REAIS (sem reimplementar a lógica em Python), com:
- escopo dinâmico idêntico ao AutoLISP (parâmetros e locais após "/");
- entradas de usuário roteirizadas (getkword, getint, getstring, entsel, ssget);
- DWG simulado (entidades TEXT por handle) e LData persistente por dicionário.

Funções ActiveX de tabela (vla-*) não são emuladas: os testes que envolvem tabela
substituem lp-sincronizar-levantamento por um stub que registra as chamadas.
"""
from __future__ import annotations

import math
import re
from pathlib import Path


class LispError(Exception):
    pass


class Sym(str):
    """Símbolo AutoLISP (nome normalizado em maiúsculas)."""


T = Sym("T")


class Pair:
    __slots__ = ("car", "cdr")

    def __init__(self, car, cdr):
        self.car, self.cdr = car, cdr

    def __eq__(self, other):
        return isinstance(other, Pair) and lisp_equal(self.car, other.car) and lisp_equal(self.cdr, other.cdr)

    def __repr__(self):
        return f"({to_str(self.car)} . {to_str(self.cdr)})"


class Lambda:
    def __init__(self, params, locs, body, name="LAMBDA"):
        self.params, self.locs, self.body, self.name = params, locs, body, name


class Ename:
    def __init__(self, handle):
        self.handle = handle

    def __eq__(self, other):
        return isinstance(other, Ename) and other.handle == self.handle

    def __hash__(self):
        return hash(self.handle)


class PickSet(list):
    pass


class ErrObj:
    def __init__(self, msg):
        self.msg = msg


def norm(v):
    return None if isinstance(v, list) and not v else v


def lisp_equal(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(lisp_equal(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b or (isinstance(a, str) and isinstance(b, str) and a == b)


def to_str(v, quote=True):
    if v is None:
        return "nil"
    if isinstance(v, Sym):
        return str(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"' if quote else v
    if isinstance(v, bool):
        raise LispError("bool inválido")
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, list):
        return "(" + " ".join(to_str(x) for x in v) + ")"
    return repr(v)


# ------------------------------------------------------------------ leitor
_ESC = {"n": "\n", "r": "\r", "t": "\t", "e": "\x1b", "\\": "\\", '"': '"'}
_INT = re.compile(r"^[+-]?\d+$")
_FLT = re.compile(r"^[+-]?(\d+\.\d*|\.\d+)([eE][+-]?\d+)?$")


def tokenize(src):
    toks, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
        elif c == ";":
            while i < n and src[i] != "\n":
                i += 1
        elif c in "()'":
            toks.append(c)
            i += 1
        elif c == '"':
            i += 1
            buf = []
            while src[i] != '"':
                if src[i] == "\\":
                    buf.append(_ESC.get(src[i + 1], src[i + 1]))
                    i += 2
                else:
                    buf.append(src[i])
                    i += 1
            i += 1
            toks.append(("STR", "".join(buf)))
        else:
            j = i
            while j < n and not src[j].isspace() and src[j] not in "()';\"":
                j += 1
            toks.append(src[i:j])
            i = j
    return toks


def parse_all(src):
    toks, pos, out = tokenize(src), [0], []

    def atom(t):
        if isinstance(t, tuple):
            return t[1]
        if _INT.match(t):
            return int(t)
        if _FLT.match(t):
            return float(t)
        return Sym(t.upper())

    def read():
        t = toks[pos[0]]
        pos[0] += 1
        if t == "'":
            return [Sym("QUOTE"), read()]
        if t == "(":
            items = []
            while toks[pos[0]] != ")":
                if toks[pos[0]] == ".":
                    pos[0] += 1
                    cdr = read()
                    items = Pair(items[0], cdr) if len(items) == 1 else items
                else:
                    items.append(read())
            pos[0] += 1
            return items
        return atom(t)

    while pos[0] < len(toks):
        out.append(read())
    return out


# ------------------------------------------------------------- interpretador
class AutoLisp:
    MAX_STEPS = 2_000_000

    def __init__(self, search_dirs, dwg=None, inputs=None):
        self.env: dict = {}
        self.search_dirs = [Path(d) for d in search_dirs]
        self.dwg = dict(dwg or {})
        self.inputs = list(inputs or [])
        self.prompts: list[tuple[str, str]] = []
        self.out: list[str] = []
        self.ldata: dict = {}
        self.sysvars = {"ERRNO": 0, "PICKADD": 2}
        self.keywords: list[str] = []
        self.steps = 0
        self._install_builtins()

    # ---------- API de teste
    def load(self, path):
        for form in parse_all(Path(path).read_text(encoding="utf-8")):
            self.ev(form)

    def run(self, code):
        res = None
        for form in parse_all(code):
            res = self.ev(form)
        return res

    def call(self, name, *args):
        return self.apply(self.env[Sym(name.upper())], list(args))

    def define(self, name, fn):
        self.env[Sym(name.upper())] = fn

    @property
    def output(self):
        return "".join(self.out)

    def ld_get(self, key, dict_name="OXCAD_LEVANTAMENTO"):
        return self.ldata.get((dict_name, key))

    # ---------- avaliação
    def ev(self, x):
        self.steps += 1
        if self.steps > self.MAX_STEPS:
            raise LispError("limite de passos excedido (laço infinito?)")
        if isinstance(x, Sym):
            if x == "T":
                return T
            if x == "NIL":
                return None
            if x.startswith(":"):
                return x
            return self.env.get(x)
        if not isinstance(x, list):
            return x
        if not x:
            return None
        head = x[0]
        sf = getattr(self, "_sf_" + head.replace("-", "_").lower(), None) if isinstance(head, Sym) else None
        if sf:
            return sf(x[1:])
        fn = self.ev(head)
        if fn is None:
            raise LispError(f"no function definition: {head}")
        return self.apply(fn, [self.ev(a) for a in x[1:]])

    def apply(self, fn, args):
        if isinstance(fn, Sym):
            fn = self.env.get(fn)
        if isinstance(fn, list) and fn and fn[0] == "LAMBDA":
            fn = self._make_lambda(fn[1], fn[2:])
        if isinstance(fn, Lambda):
            if len(args) != len(fn.params):
                raise LispError(f"too few/many arguments: {fn.name}")
            names = fn.params + fn.locs
            saved = {k: self.env.get(k) for k in names}
            try:
                for k in fn.locs:
                    self.env[k] = None
                for k, v in zip(fn.params, args):
                    self.env[k] = v
                res = None
                for form in fn.body:
                    res = self.ev(form)
                return res
            finally:
                self.env.update(saved)
        if callable(fn):
            return fn(*args)
        raise LispError(f"bad function: {to_str(fn)}")

    @staticmethod
    def _make_lambda(arglist, body, name="LAMBDA"):
        arglist = arglist or []
        if Sym("/") in arglist:
            k = arglist.index(Sym("/"))
            return Lambda(arglist[:k], arglist[k + 1:], body, name)
        return Lambda(list(arglist), [], body, name)

    # ---------- formas especiais
    def _sf_quote(self, a):
        return norm(a[0])

    def _sf_setq(self, a):
        v = None
        for i in range(0, len(a), 2):
            v = self.env[a[i]] = self.ev(a[i + 1])
        return v

    def _sf_if(self, a):
        if self.ev(a[0]) is not None:
            return self.ev(a[1])
        return self.ev(a[2]) if len(a) > 2 else None

    def _sf_cond(self, a):
        for clause in a:
            v = self.ev(clause[0])
            if v is not None:
                for f in clause[1:]:
                    v = self.ev(f)
                return v
        return None

    def _sf_progn(self, a):
        v = None
        for f in a:
            v = self.ev(f)
        return v

    def _sf_and(self, a):
        for f in a:
            if self.ev(f) is None:
                return None
        return T

    def _sf_or(self, a):
        for f in a:
            if self.ev(f) is not None:
                return T
        return None

    def _sf_while(self, a):
        v = None
        while self.ev(a[0]) is not None:
            v = self._sf_progn(a[1:])
        return v

    def _sf_repeat(self, a):
        v = None
        for _ in range(int(self.ev(a[0]))):
            v = self._sf_progn(a[1:])
        return v

    def _sf_foreach(self, a):
        var, lst, v = a[0], self.ev(a[1]), None
        saved = self.env.get(var)
        try:
            for item in (lst or []):
                self.env[var] = item
                v = self._sf_progn(a[2:])
        finally:
            self.env[var] = saved
        return v

    def _sf_defun(self, a):
        self.env[a[0]] = self._make_lambda(a[1], a[2:], a[0])
        return a[0]

    def _sf_lambda(self, a):
        return self._make_lambda(a[0], a[1:])

    def _sf_function(self, a):
        return self.ev(a[0])

    # ---------- entradas roteirizadas
    def _next(self, fn, prompt):
        if not self.inputs:
            raise LispError(f"roteiro de entradas esgotado em {fn}: {prompt!r}")
        ans = self.inputs.pop(0)
        self.prompts.append((fn, str(prompt)))
        return ans

    def _getkword(self, prompt=""):
        ans, kws, self.keywords = self._next("getkword", prompt), self.keywords, []
        if ans is None:
            return None
        for k in kws:
            if k.upper().startswith(str(ans).upper()):
                return k
        raise LispError(f"palavra-chave {ans!r} inválida para {kws} em {prompt!r}")

    def _entsel(self, prompt=""):
        ans = self._next("entsel", prompt)
        if ans is None or ans == "MISS":
            self.sysvars["ERRNO"] = 7 if ans == "MISS" else 52
            return None
        handle = ans[0] if isinstance(ans, (tuple, list)) else ans
        if handle not in self.dwg:
            raise LispError(f"handle {handle!r} inexistente no DWG simulado")
        pt = list(ans[1]) if isinstance(ans, (tuple, list)) and len(ans) > 1 else [0.0, 0.0, 0.0]
        return [Ename(handle), pt]

    def _ssget(self, *args):
        ans = self._next("ssget", "Select objects")
        return PickSet(Ename(h) for h in ans) if ans else None

    def _entget(self, e):
        if not isinstance(e, Ename) or e.handle not in self.dwg:
            return None
        ent = self.dwg[e.handle]
        type_val = ent.get("type", ent.get("0", ent.get(0, "TEXT")))
        text_val = ent.get("text", ent.get("1", ent.get(1, "")))
        return [Pair(-1, e), Pair(0, type_val), Pair(5, e.handle), Pair(1, text_val)]

    def _findfile(self, p):
        cand = Path(p)
        if cand.is_absolute():
            return str(cand) if cand.exists() else None
        for d in self.search_dirs:
            f = d / p.replace("\\", "/")
            if f.exists():
                return str(f)
        return None

    def _catch(self, fn, args=None):
        try:
            return self.apply(fn, list(args or []))
        except LispError as exc:
            return ErrObj(str(exc))

    # ---------- primitivas
    def _install_builtins(self):
        def cons(a, b):
            return [a] if b is None else ([a] + b if isinstance(b, list) else Pair(a, b))

        def car(x):
            return x[0] if isinstance(x, list) else (x.car if isinstance(x, Pair) else None)

        def cdr(x):
            return norm(x[1:]) if isinstance(x, list) else (x.cdr if isinstance(x, Pair) else None)

        def assoc(k, al):
            for it in al or []:
                if (isinstance(it, Pair) and lisp_equal(it.car, k)) or (isinstance(it, list) and lisp_equal(it[0], k)):
                    return it
            return None

        def subst(new, old, lst):
            if lisp_equal(lst, old):
                return new
            return [subst(new, old, x) for x in lst] if isinstance(lst, list) else lst

        def member(x, lst):
            for i, e in enumerate(lst or []):
                if lisp_equal(e, x):
                    return lst[i:]
            return None

        def ltype(x):
            if x is None:
                return None
            for cls, name in ((Sym, "SYM"), (str, "STR"), (int, "INT"), (float, "REAL"), (Lambda, "USUBR"),
                              (Ename, "ENAME"), (PickSet, "PICKSET"), (list, "LIST"), (Pair, "LIST")):
                if isinstance(x, cls):
                    return Sym(name)
            return Sym("SUBR") if callable(x) else None

        def div(a, *r):
            for b in r:
                a = int(a / b) if isinstance(a, int) and isinstance(b, int) else a / b
            return a

        def tb(v):
            return T if v else None

        def num(v):
            if not isinstance(v, (int, float)):
                raise LispError(f"bad argument type: numberp: {to_str(v)}")
            return v

        def substr(s, start, n=None):
            return s[start - 1:] if n is None else s[start - 1:start - 1 + n]

        def princ(x=None):
            self.out.append(to_str(x, quote=False) if x is not None else "")
            return x

        def distof(s, mode=None):
            try:
                return float(s)
            except (TypeError, ValueError):
                return None

        def atoi(s):
            m = re.match(r"\s*([+-]?\d+)", s or "")
            return int(m.group(1)) if m else 0

        def rtos(n, mode=2, prec=2):
            return f"{num(n):.{prec}f}"

        def lread(s):
            forms = parse_all(s) if s and s.strip() else []
            return norm(forms[0]) if forms else None

        def initget(*args):
            self.keywords = next((a.split() for a in args if isinstance(a, str)), [])

        def ldata_put(d, k, v):
            self.ldata[(d, k)] = v
            return v

        b = {
            "+": lambda *a: sum(num(x) for x in a), "-": lambda a, *r: -num(a) if not r else a - sum(num(x) for x in r),
            "*": lambda *a: math.prod(num(x) for x in a), "/": div, "1+": lambda a: num(a) + 1, "1-": lambda a: num(a) - 1,
            "=": lambda a, *r: tb(all(a == x for x in r)), "/=": lambda a, b: tb(a != b),
            "<": lambda a, b: tb(num(a) < num(b)), ">": lambda a, b: tb(num(a) > num(b)),
            "<=": lambda a, b: tb(num(a) <= num(b)), ">=": lambda a, b: tb(num(a) >= num(b)),
            "abs": lambda a: abs(num(a)), "max": lambda *a: max(a), "fix": lambda a: int(num(a)), "float": lambda a: float(num(a)),
            "cons": cons, "car": car, "cdr": cdr, "cadr": lambda x: car(cdr(x)), "caddr": lambda x: car(cdr(cdr(x))),
            "list": lambda *a: norm(list(a)), "append": lambda *ls: norm([e for lst in ls for e in (lst or [])]),
            "length": lambda x: len(x or []), "nth": lambda n, x: x[n] if x and 0 <= n < len(x) else None,
            "reverse": lambda x: norm(list(reversed(x or []))), "last": lambda x: x[-1] if x else None,
            "assoc": assoc, "subst": subst, "member": member, "equal": lambda a, b, *f: tb(lisp_equal(a, b)),
            "mapcar": lambda f, *ls: norm([self.apply(f, list(z)) for z in zip(*[(l or []) for l in ls])]),
            "null": lambda x: tb(x is None), "not": lambda x: tb(x is None),
            "listp": lambda x: tb(x is None or isinstance(x, (list, Pair))),
            "numberp": lambda x: tb(isinstance(x, (int, float))), "type": ltype,
            "boundp": lambda s: tb(self.env.get(s) is not None), "eval": self.ev,
            "strcat": lambda *a: "".join(a), "strlen": lambda s: len(s), "substr": substr,
            "strcase": lambda s, low=None: s.lower() if low else s.upper(), "itoa": lambda i: str(int(i)),
            "atoi": atoi, "atof": lambda s: distof(s) or 0.0, "distof": distof, "rtos": rtos, "read": lread,
            "ascii": lambda s: ord(s[0]) if s else 0,
            "vl-string-search": lambda p, s, st=0: (lambda i: None if i < 0 else i)(s.find(p, st)),
            "vl-string-trim": lambda c, s: s.strip(c), "vl-string-translate": lambda a, z, s: s.translate(str.maketrans(a, z)),
            "vl-prin1-to-string": lambda x: to_str(x), "princ": princ, "prin1": princ, "print": princ,
            "vl-load-com": lambda: None, "textscr": lambda: None, "graphscr": lambda: None,
            "findfile": self._findfile, "load": lambda p, *r: self.load(self._findfile(p) or p),
            "vl-catch-all-apply": self._catch, "vl-catch-all-error-p": lambda x: tb(isinstance(x, ErrObj)),
            "vl-catch-all-error-message": lambda x: x.msg,
            "getvar": lambda k: self.sysvars.get(k.upper()), "setvar": lambda k, v: self.sysvars.__setitem__(k.upper(), v) or v,
            "initget": initget, "getkword": self._getkword, "getint": lambda p="": self._next("getint", p),
            "getstring": lambda *a: self._next("getstring", a[-1] if a else "") or "",
            "getpoint": lambda *a: self._next("getpoint", a[-1] if a else ""),
            "entsel": self._entsel, "ssget": self._ssget, "sslength": lambda s: len(s), "ssname": lambda s, i: s[i] if i < len(s) else None,
            "entget": self._entget, "entnext": lambda *a: None, "handent": lambda h: Ename(h) if h in self.dwg else None,
            "vlax-ldata-get": lambda d, k, *r: self.ldata.get((d, k)), "vlax-ldata-put": ldata_put,
            "vlax-ldata-delete": lambda d, k: tb(self.ldata.pop((d, k), None) is not None),
        }
        for name, fn in b.items():
            self.env[Sym(name.upper())] = fn
