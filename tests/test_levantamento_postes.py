from pathlib import Path
import re
import pytest

ROOT = Path(__file__).resolve().parents[1]
LISP_PATH = ROOT / "orcamento" / "levantamento_postes.lsp"


def test_levantamento_postes_lisp_balance_and_syntax():
    """Valida que todos os parênteses e strings do LISP estão estritamente balanceados."""
    source = LISP_PATH.read_text(encoding="utf-8")

    depth = 0
    in_string = False
    in_comment = False
    for index, char in enumerate(source):
        if in_comment:
            if char == "\n":
                in_comment = False
            continue
        if char == ";" and not in_string:
            in_comment = True
            continue
        if char == '"':
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and source[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                in_string = not in_string
            continue
        if not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                assert depth >= 0, f"Parêntese de fechamento excedente na posição {index}"

    assert depth == 0, f"Parênteses desbalanceados: profundidade restante = {depth}"
    assert not in_string, "String não fechada no arquivo LISP"


def test_levantamento_postes_contract_and_commands():
    """Valida o contrato público de funções, comandos e estrutura de 10 colunas da rotina LISP."""
    source = LISP_PATH.read_text(encoding="utf-8")

    # Comandos
    assert "(defun c:LEVANTAR_POSTES" in source
    assert "(defun c:LP " in source

    # Parsers
    assert "(defun lp-parse-poste" in source
    assert "(defun lp-parse-ramais-e-clientes" in source
    assert "(defun lp-parse-luminaria" in source
    assert "(defun lp-parse-demanda" in source
    assert "(defun lp-parse-acumulada" in source
    assert "(defun lp-extract-value-after-key" in source
    assert "(defun lp-is-noise-line" in source
    assert "(defun lp-format-val" in source

    # Cálculos
    assert "(defun lp-calc-posicoes" in source
    assert "(defun lp-calc-cs" in source

    # Manipulação, Exclusão e Reindexação Sequencial
    assert "(defun lp-renumerar-pontos" in source
    assert "(defun lp-excluir-ponto" in source
    assert "(defun lp-precisa-renumerar-p" in source

    # Persistência DWG via LData
    assert "(vlax-ldata-get" in source
    assert "(vlax-ldata-put" in source
    assert "(vlax-ldata-delete" in source
    assert '"OXCAD_LEVANTAMENTO"' in source
    assert '"PONTOS"' in source
    assert '"TABELA_HANDLE"' in source
    assert "(defun lp-db-obter-tabela-handle" in source
    assert "(defun lp-db-salvar-tabela-handle" in source
    assert "(defun lp-db-remover-tabela-handle" in source

    # Sincronização e Rastreabilidade por Handles
    assert "(defun lp-validar-handle-texto" in source
    assert "(defun lp-recalcular-demandas-acumuladas" in source
    assert "(defun lp-atualizar-celulas-tabela" in source
    assert "(defun lp-sincronizar-levantamento" in source
    assert "(defun lp-atualizar-exclusao-tabela" in source
    assert '"TEXT_HANDLES"' in source

    # Tabela nativa de 10 colunas
    assert "vla-AddTable" in source
    assert "col-count 10" in source
    assert "(vla-MergeCells table 0 0 0 9)" in source
    assert '"LEVANTAMENTO DE POSTES E CLIENTES"' in source
    assert '"PONTO"' in source
    assert '"POSTE"' in source
    assert '"RAMAIS"' in source
    assert '"LUMINÁRIA"' in source
    assert '"TOTAL CLIENTES"' in source
    assert '"TOTAL POSIÇÕES"' in source
    assert '"TOTAL CS"' in source
    assert '"DEMANDA (kVA)"`' in source or '"DEMANDA (kVA)"' in source
    assert '"ACUMULADA (kVA)"' in source
    assert '"COORDENADAS"' in source


# ==============================================================================
# Modelagem lógica idêntica aos parsers AutoLISP para testes de regras de negócio
# ==============================================================================

def py_strip_mtext(val: str) -> str:
    cleaned = re.sub(r"\\[Pp~]", "\n", val)
    cleaned = re.sub(r"\\[A-Za-z0-9]+;", "", cleaned)
    cleaned = re.sub(r"[{}]", "", cleaned)
    return cleaned.strip()


def py_is_noise_line(line: str) -> bool:
    up = line.upper().strip()
    return not up or any(noise in up for noise in [
        "DAN", "ESF. RES", "ESF.", "ESFORCO",
        "DEM.:", "DEM.", "DEMANDA", "ACUM.:", "ACUM.", "ACUMULADO", "KVA", "CLIENTE"
    ])


def py_parse_poste(lines: list[str]) -> str:
    for line in lines:
        up = line.upper().strip()
        if not py_is_noise_line(up) and len(up) >= 2 and up.startswith("P"):
            ch = up[1]
            if ch.isdigit() or ch == "-":
                return up
    return "-"


def py_parse_ramais_e_clientes(lines: list[str]) -> tuple[str, str | int, int, int, int]:
    mono = bi = tri = 0
    ramais_found = False

    for line in lines:
        up = line.upper().strip()
        if not py_is_noise_line(up):
            parts = re.split(r"[,|+\s]+", up)
            for part in parts:
                m = re.match(r"^(\d+)[X*](\d+|TRI|BI|MONO|[Øø]|%%C)", part)
                if m:
                    qty = int(m.group(1))
                    suf = part[m.end(1) + 1:]
                    if "3" in suf or "TRI" in suf:
                        tri += qty
                    elif "2" in suf or "BI" in suf:
                        bi += qty
                    else:
                        mono += qty
                    ramais_found = True

    ramais_list = []
    if mono > 0:
        ramais_list.append(f"{mono}x%%C1")
    if bi > 0:
        ramais_list.append(f"{bi}x%%C2")
    if tri > 0:
        ramais_list.append(f"{tri}x%%C3")

    if not ramais_found or (mono == 0 and bi == 0 and tri == 0):
        return "-", "-", 0, 0, 0

    ramal_str = " | ".join(ramais_list)
    clientes_total = mono + bi + tri
    return ramal_str, clientes_total, mono, bi, tri


def py_parse_luminaria(lines: list[str]) -> str:
    for line in lines:
        up = line.upper().strip()
        if not py_is_noise_line(up):
            if any(k in up for k in ["IP", "LUM", "LED", "PÉTALA", "PETALA"]):
                return line.strip()
            if "W" in up and any(w in up for w in ["70", "100", "150", "250"]):
                return line.strip()
    return "-"


def py_extract_value_after_key(text: str, prefixes: list[str]) -> str | None:
    up = text.upper()
    for prefix in prefixes:
        pos = up.find(prefix)
        if pos != -1:
            idx = pos + len(prefix)
            while idx < len(text) and text[idx] in [".", ":", " ", "-", "=", "\t"]:
                idx += 1
            val = ""
            has_digit = False
            while idx < len(text) and (text[idx].isdigit() or text[idx] in [",", "."]):
                ch = text[idx]
                if ch.isdigit():
                    has_digit = True
                val += ch
                idx += 1
            val = val.rstrip(".,")
            if has_digit and len(val) > 0:
                return val
    return None


def py_parse_demanda(lines: list[str]) -> str:
    prefixes = ["DEMANDA", "DEM.:", "DEM:", "DEM.", "DEM"]
    found_val = None
    ambig = False
    for line in lines:
        cand = py_extract_value_after_key(line, prefixes)
        if cand:
            if found_val is None:
                found_val = cand
            elif found_val != cand:
                ambig = True
    if found_val is None or ambig:
        return "-"
    return found_val


def py_parse_acumulada(lines: list[str]) -> str:
    prefixes = ["ACUMULADA", "ACUMULADO", "ACUM.:", "ACUM:", "ACUM.", "ACUM"]
    found_val = None
    ambig = False
    for line in lines:
        cand = py_extract_value_after_key(line, prefixes)
        if cand:
            if found_val is None:
                found_val = cand
            elif found_val != cand:
                ambig = True
    if found_val is None or ambig:
        return "-"
    return found_val


def py_calc_posicoes(mono: int, bi: int, tri: int) -> str | int:
    if mono == 0 and bi == 0 and tri == 0:
        return "-"
    return (mono * 1) + (bi * 2) + (tri * 3)


def py_calc_cs(posicoes: str | int) -> str | int:
    if not isinstance(posicoes, int) or posicoes <= 0:
        return "-"
    return (posicoes + 8) // 9


def py_process_point_texts(raw_texts_list: list[str], seq: int, coords: str = "-") -> dict:
    """Modelo Python fiel a lp-process-point-texts para testes de persistência e integridade."""
    lines = []
    for txt in raw_texts_list:
        lines.extend(py_strip_mtext(txt).split("\n"))
    poste = py_parse_poste(lines)
    ramal_str, clientes, mono, bi, tri = py_parse_ramais_e_clientes(lines)
    lum = py_parse_luminaria(lines)
    pos = py_calc_posicoes(mono, bi, tri)
    cs = py_calc_cs(pos)
    dem = py_parse_demanda(lines)
    acum = py_parse_acumulada(lines)
    return {
        "SEQ": seq,
        "POSTE": poste,
        "RAMAIS": ramal_str,
        "LUM": lum,
        "CLIENTES": clientes,
        "POSICOES": pos,
        "CS": cs,
        "DEMANDA": dem,
        "ACUMULADA": acum,
        "COORDENADAS": coords or "-",
        "RAW": raw_texts_list,
    }


def py_renumerar_pontos(pontos: list[dict]) -> list[dict]:
    """Modelo Python fiel a lp-renumerar-pontos: renumera de 1 a N preservando atributos."""
    resultado = []
    for idx, p in enumerate(pontos, start=1):
        item = p.copy()
        item["SEQ"] = idx
        resultado.append(item)
    return resultado


def py_excluir_ponto(pontos: list[dict], idx_alvo: int) -> list[dict]:
    """Modelo Python fiel a lp-excluir-ponto: remove o ponto 1 a N e renumera sequencialmente."""
    if not pontos or idx_alvo < 1 or idx_alvo > len(pontos):
        return pontos
    removido = False
    remanescentes = []
    for i, p in enumerate(pontos, start=1):
        if not removido and (p.get("SEQ") == idx_alvo or i == idx_alvo):
            removido = True
        else:
            remanescentes.append(p)
    return py_renumerar_pontos(remanescentes)


def py_formata_linha_revisao(p: dict) -> str:
    """Simula a formatação de uma linha de revisão em lp-exibir-revisao."""
    seq = str(p.get("SEQ", "-"))
    poste = str(p.get("POSTE", "-"))
    ramais = str(p.get("RAMAIS", "-"))
    lum = str(p.get("LUM", "-"))
    cli = str(p.get("CLIENTES", "-"))
    pos = str(p.get("POSICOES", "-"))
    cs = str(p.get("CS", "-"))
    dem = str(p.get("DEMANDA", "-"))
    acum = str(p.get("ACUMULADA", "-"))
    coords = str(p.get("COORDENADAS", "-")).replace("\n", " | ")
    return f"{seq} | {poste} | {ramais} | {lum} | {cli} | {pos} | {cs} | {dem} | {acum} | {coords}"


def py_parse_num(val_str: str) -> float | None:
    if not val_str or val_str == "-":
        return None
    clean = str(val_str).replace(",", ".").strip()
    try:
        return float(clean)
    except ValueError:
        return None


def py_format_num(num: float | None, use_comma: bool) -> str:
    if num is None:
        return "-"
    s = f"{num:.2f}"
    return s.replace(".", ",") if use_comma else s


def py_recalcular_demandas_acumuladas(pontos: list[dict]) -> list[dict]:
    novos = []
    acum_anterior = 0.0
    for p in pontos:
        item = p.copy()
        dem_str = str(item.get("DEMANDA", "-"))
        acum_str = str(item.get("ACUMULADA", "-"))
        dem_val = py_parse_num(dem_str)
        use_comma = ("," in dem_str) or ("," in acum_str)
        if dem_val is not None:
            if acum_str == "-" or (py_parse_num(acum_str) is not None and acum_anterior > 0.0):
                acum_anterior += dem_val
                item["ACUMULADA"] = py_format_num(acum_anterior, use_comma)
            else:
                acum_val = py_parse_num(acum_str)
                acum_anterior = acum_val if acum_val is not None else (acum_anterior + dem_val)
        novos.append(item)
    return novos


def py_sincronizar_levantamento(
    pontos: list[dict],
    tbl_handle: str | None,
    dwg_entities: dict,
    tbl_mock: dict | None = None,
    modo: str = "NORMAL",
    area: int = 50,
    topologia: list | dict | None = None,
):
    if not pontos or not tbl_handle:
        return ":nada-a-fazer", pontos, []

    if tbl_handle not in dwg_entities or dwg_entities[tbl_handle].get("type") != "ACAD_TABLE":
        return ":tabela-inexistente", tbl_handle, []

    tem_alteracao = False
    pontos_afetados = []
    novos_pontos = []
    erro_msg = None

    for p in pontos:
        if erro_msg:
            break
        seq = p.get("SEQ")
        handles = p.get("TEXT_HANDLES")
        raw_antigo = p.get("RAW", [])
        coords = p.get("COORDENADAS", "-")
        blk_h = p.get("BLOCO_POSTE_HANDLE")

        if not handles or not isinstance(handles, list):
            novos_pontos.append(p.copy())
            continue

        cur_raw = []
        for h in handles:
            if h not in dwg_entities:
                erro_msg = f"Texto do Ponto {seq} (Handle #{h}): Entidade não encontrada no desenho (excluída)"
                break
            ent = dwg_entities[h]
            if ent.get("type") not in ["TEXT", "MTEXT"]:
                erro_msg = f"Texto do Ponto {seq} (Handle #{h}): Tipo inválido, esperado TEXT ou MTEXT"
                break
            cur_raw.append(ent.get("text", ""))

        if erro_msg:
            break

        if cur_raw == raw_antigo:
            novos_pontos.append(p.copy())
        else:
            tem_alteracao = True
            pontos_afetados.append(seq)
            novo_p = py_process_point_texts(cur_raw, seq=seq, coords=coords)
            novo_p["TEXT_HANDLES"] = handles
            if blk_h:
                novo_p["BLOCO_POSTE_HANDLE"] = blk_h
            if novo_p.get("POSTE") == "-" and p.get("POSTE") and p.get("POSTE") != "-":
                novo_p["POSTE"] = p["POSTE"]
            novos_pontos.append(novo_p)

    if erro_msg:
        return ":erro", erro_msg, []

    if not tem_alteracao:
        return ":sem-alteracoes", pontos, []

    if modo == "CLANDESTINO":
        recalc = py_clan_recalcular_pontos(novos_pontos, area_padrao=area, topologia=topologia)
        if any(p.get("DEMANDA") == "-" or p.get("ACUMULADA") == "-" for p in recalc):
            return ":erro", "Falha no cálculo normativo LIGHT: limite excedido ou dados inválidos", []
        novos_pontos = recalc
    else:
        novos_pontos = py_recalcular_demandas_acumuladas(novos_pontos)

    if tbl_mock is not None:
        tbl_mock["rows"] = [
            [
                p["SEQ"], p["POSTE"], p["RAMAIS"], p["LUM"],
                p["CLIENTES"], p["POSICOES"], p["CS"],
                p["DEMANDA"], p["ACUMULADA"], p["COORDENADAS"]
            ]
            for p in novos_pontos
        ]

    return ":atualizado", novos_pontos, pontos_afetados


# ==============================================================================
# Casos de Teste Rigorosos Baseados na Especificação
# ==============================================================================

def test_calculo_ramais_8x1_e_6x3_normativo():
    """Valida 8x1ø | 6x3ø → 14 clientes, 26 posições, 3 CS."""
    lines = ["8x1ø | 6x3ø"]
    ramal_str, clientes, mono, bi, tri = py_parse_ramais_e_clientes(lines)
    assert ramal_str == "8x%%C1 | 6x%%C3"
    assert mono == 8
    assert bi == 0
    assert tri == 6
    assert clientes == 14

    pos = py_calc_posicoes(mono, bi, tri)
    assert pos == 26
    cs = py_calc_cs(pos)
    assert cs == 3


def test_calculo_ramais_12x1_e_1x3_normativo():
    """Valida 12x1ø | 1x3ø → 13 clientes, 15 posições, 2 CS."""
    lines = ["12x1ø | 1x3ø"]
    ramal_str, clientes, mono, bi, tri = py_parse_ramais_e_clientes(lines)
    assert ramal_str == "12x%%C1 | 1x%%C3"
    assert clientes == 13

    pos = py_calc_posicoes(mono, bi, tri)
    assert pos == 15
    cs = py_calc_cs(pos)
    assert cs == 2


def test_ignorar_somatorio_escrito_no_desenho():
    """Valida que textos como 14+20=34-CLIENTES NÃO são utilizados para total de clientes."""
    raw = "14+20=34-CLIENTES\\PDEM.: 28,33kVA\\PACUM.: 57,59kVA"
    lines = py_strip_mtext(raw).split("\n")

    ramal_str, clientes, mono, bi, tri = py_parse_ramais_e_clientes(lines)
    # Sem ramais, não deve inventar total de 14, 20 ou 34 clientes
    assert clientes == "-"
    assert ramal_str == "-"
    assert py_calc_posicoes(mono, bi, tri) == "-"
    assert py_calc_cs(py_calc_posicoes(mono, bi, tri)) == "-"


def test_extracao_demanda_e_acumulada_separadas():
    """Valida extração precisa de DEM.: 28,33kVA e ACUM.: 57,59kVA preservando formato."""
    raw = "DEM.: 28,33kVA\\PACUM.: 57,59kVA"
    lines = py_strip_mtext(raw).split("\n")

    dem = py_parse_demanda(lines)
    acum = py_parse_acumulada(lines)

    assert dem == "28,33"
    assert acum == "57,59"


def test_demanda_e_acumulada_na_mesma_linha_e_variacoes():
    """Valida interpretação mesmo na mesma linha e com variações de caixa e pontuação."""
    line = "DEM: 22.50 kVA  ACUMULADA: 45.75kVA"
    lines = [line]

    dem = py_parse_demanda(lines)
    acum = py_parse_acumulada(lines)

    assert dem == "22.50"
    assert acum == "45.75"


def test_textos_sem_ramais_nao_inventam_clientes():
    """Valida que ponto sem ramais recebe '-' e não calcula posições nem CS indevidamente."""
    lines = ["POSTE P112600B", "ESF. RES. 140 daN", "DEM.: 10,0kVA"]
    ramal_str, clientes, mono, bi, tri = py_parse_ramais_e_clientes(lines)

    assert ramal_str == "-"
    assert clientes == "-"
    assert py_calc_posicoes(mono, bi, tri) == "-"
    assert py_calc_cs("-") == "-"


def test_valores_ausentes_ou_ambiguos_seguem_padrao_dados_incompletos():
    """Valida que demanda/acumulada ausente ou conflitante gera '-' (dados incompletos)."""
    # Ausente
    lines_vazio = ["P112600B", "8x1ø"]
    assert py_parse_demanda(lines_vazio) == "-"
    assert py_parse_acumulada(lines_vazio) == "-"

    # Conflito / ambíguo em demanda
    lines_ambig = ["DEM.: 28,33kVA", "DEM.: 35,00kVA"]
    assert py_parse_demanda(lines_ambig) == "-"

    # Repetido com mesmo valor não é ambíguo
    lines_ok = ["DEM.: 28,33kVA", "DEM.: 28,33kVA"]
    assert py_parse_demanda(lines_ok) == "28,33"


def test_tabela_nativa_cad_contem_exatamente_10_colunas_na_ordem():
    """Valida que a tabela do AutoCAD é gerada com 10 colunas na ordem exata especificada."""
    source = LISP_PATH.read_text(encoding="utf-8")

    assert "col-count 10" in source
    assert "(vla-MergeCells table 0 0 0 9)" in source

    # Ordem dos cabeçalhos
    assert '(vla-SetText table 1 0 "PONTO")' in source
    assert '(vla-SetText table 1 1 "POSTE")' in source
    assert '(vla-SetText table 1 2 "RAMAIS")' in source
    assert '(vla-SetText table 1 3 "LUMINÁRIA")' in source
    assert '(vla-SetText table 1 4 "TOTAL CLIENTES")' in source
    assert '(vla-SetText table 1 5 "TOTAL POSIÇÕES")' in source
    assert '(vla-SetText table 1 6 "TOTAL CS")' in source
    assert '(vla-SetText table 1 7 "DEMANDA (kVA)")' in source
    assert '(vla-SetText table 1 8 "ACUMULADA (kVA)")' in source
    assert '(vla-SetText table 1 9 "COORDENADAS")' in source

    # Larguras das 10 colunas
    assert "(vla-SetColumnWidth table 0 22.0)" in source
    assert "(vla-SetColumnWidth table 1 35.0)" in source
    assert "(vla-SetColumnWidth table 2 50.0)" in source
    assert "(vla-SetColumnWidth table 3 35.0)" in source
    assert "(vla-SetColumnWidth table 4 38.0)" in source
    assert "(vla-SetColumnWidth table 5 38.0)" in source
    assert "(vla-SetColumnWidth table 6 25.0)" in source
    assert "(vla-SetColumnWidth table 7 38.0)" in source
    assert "(vla-SetColumnWidth table 8 38.0)" in source
    assert "(vla-SetColumnWidth table 9 45.0)" in source


def test_coordenadas_usam_somente_contrato_real_do_bloco_co():
    """N/E vêm dos atributos que ADDBLOCO grava no CO, nunca do ponto de inserção."""
    source = LISP_PATH.read_text(encoding="utf-8")
    addbloco = (ROOT / "topografia" / "addbloco.lsp").read_text(encoding="utf-8")
    assert "(defun lp-extrair-coordenadas-bloco" in source
    assert '((= tag "N")' in source
    assert '((= tag "E")' in source
    assert '(cons "COORDENADAS" coords)' in source
    assert '"BLOCO_POSTE_HANDLE"' in source
    assert '(cdr (assoc 10 edata))' not in source.split("(defun lp-extrair-coordenadas-bloco", 1)[1].split(";;; ----------------------------------------------------------------------------", 1)[0]
    assert '((= tag "N") (vla-put-TextString att strN))' in addbloco
    assert '((= tag "E") (vla-put-TextString att strE))' in addbloco


def test_extracao_codigo_poste_e_filtro_esforco_mecanico():
    """Valida extração dos códigos de poste ignorando daN e esforços mecânicos."""
    lines1 = py_strip_mtext("P112600B\\P140 daN").split("\n")
    assert py_parse_poste(lines1) == "P112600B"

    lines2 = py_strip_mtext("P212600B\\PESF. RES.\\P619 daN").split("\n")
    assert py_parse_poste(lines2) == "P212600B"

    lines3 = ["140 daN", "ESF. RES."]
    assert py_parse_poste(lines3) == "-"


def test_extracao_luminaria():
    """Valida detecção de IP/Luminária e fallback '-'."""
    assert py_parse_luminaria(["IP LED 50W"]) == "IP LED 50W"
    assert py_parse_luminaria(["LUMINARIA 70W VS"]) == "LUMINARIA 70W VS"
    assert py_parse_luminaria(["POSTE P01", "140 daN"]) == "-"


def test_lisp_formula_cs_implementation():
    """Valida a fórmula do CS no código AutoLISP diretamente."""
    source = LISP_PATH.read_text(encoding="utf-8")
    assert "(defun lp-calc-cs (posicoes)" in source
    assert "(/ (+ posicoes 8) 9)" in source


def test_lisp_persistencia_e_preservacao_em_falha():
    """Valida que o LISP só limpa o LData após criação confirmada da tabela e protege contra falhas COM."""
    source = LISP_PATH.read_text(encoding="utf-8")
    assert "(setq table-ok (lp-gerar-tabela-cad pontos))" in source
    assert "(if table-ok" in source
    assert "(lp-db-limpar-pontos)" in source
    assert "(vl-catch-all-apply" in source
    assert "'vla-AddTable" in source
    assert "defconst" not in source
    assert '(setq *lp-dict-name* "OXCAD_LEVANTAMENTO")' in source
    assert "A tabela não foi criada. A coleta foi preservada." in source


def test_levantamento_postes_is_loaded_globally_in_acaddoc():
    """Valida carregamento global em acaddoc.lsp e documentação no menu COMANDOS."""
    loader = (ROOT / "acaddoc.lsp").read_text(encoding="utf-8")
    assert 'load-aux-safe "orcamento\\\\levantamento_postes.lsp"' in loader
    assert "LEVANTAR_POSTES ou LP" in loader


def test_oxcad_palette_button_dispatches_postes_command():
    """Valida botão na paleta OXCAD e despacho seguro para o documento ativo."""
    xaml = (ROOT / "oxcad" / "OxCadControl.xaml").read_text(encoding="utf-8")
    code = (ROOT / "oxcad" / "OxCadControl.xaml.cs").read_text(encoding="utf-8")

    assert 'x:Name="BtnLevantamentoPostes"' in xaml
    assert 'Click="BtnLevantarPostes_Click"' in xaml
    assert "BtnLevantamentoPostes.IsEnabled = enabled;" in code
    assert 'doc.SendStringToExecute("_.LEVANTAR_POSTES "' in code
    assert 'OxCadExecutionRegistry.RegistrarComandoNativo(' in code


def test_deteccao_duplicidade_e_preservacao_de_ocorrencias_distintas():
    """Valida que postes repetidos são mantidos na tabela e alertados para revisão."""
    source = LISP_PATH.read_text(encoding="utf-8")
    assert "(defun lp-verificar-duplicidade" in source
    assert "já coletado no(s) ponto(s):" in source
    assert "Registrado como nova ocorrência." in source
    assert "(setq pontos (append pontos (list novo-ponto)))" in source


def test_menu_interativo_revisao_e_exclusao_com_reindexacao():
    """Valida que o comando suporta Revisão, Exclusão com reindexação e Limpeza explícita."""
    source = LISP_PATH.read_text(encoding="utf-8")
    assert '"Adicionar Revisar Excluir Gerar Limpar Sair Configurar"' in source
    assert "(defun lp-exibir-revisao" in source
    assert "(subst (cons \"SEQ\" idx) (assoc \"SEQ\" p) p)" in source
    assert "Deseja realmente descartar todos os pontos coletados?" in source


# ==============================================================================
# Testes de Regressão: Defeito de Numeração (PONTO = 1) no LEVANTAR_POSTES
# ==============================================================================

def test_regressao_reproducao_defeito_antigo_vs_correcao():
    """Demonstra que a lógica antiga com idx estático causava PONTO = 1 para todos,
    e valida que a correção renumera sequencialmente mantendo identidades e dados."""
    # 4 pontos iniciais conforme reprodução manual do usuário
    pts = [
        {"SEQ": 1, "POSTE": "-", "RAMAIS": "14x%%C1 | 2x%%C3", "CLIENTES": 16, "POSICOES": 20, "CS": 3, "DEMANDA": "31,79", "ACUMULADA": "198,34", "COORDENADAS": "N: 7450100.10\nE: 678100.10"},
        {"SEQ": 2, "POSTE": "-", "RAMAIS": "13x%%C1 | 4x%%C3", "CLIENTES": 17, "POSICOES": 25, "CS": 3, "DEMANDA": "33,52", "ACUMULADA": "103,32", "COORDENADAS": "N: 7450200.20\nE: 678200.20"},
        {"SEQ": 3, "POSTE": "-", "RAMAIS": "15x%%C1 | 3x%%C3", "CLIENTES": 18, "POSICOES": 24, "CS": 3, "DEMANDA": "35,25", "ACUMULADA": "82,18", "COORDENADAS": "N: 7450300.30\nE: 678300.30"},
        {"SEQ": 4, "POSTE": "-", "RAMAIS": "7x%%C1 | 2x%%C2", "CLIENTES": 9, "POSICOES": 11, "CS": 2, "DEMANDA": "19,27", "ACUMULADA": "58,92", "COORDENADAS": "N: 7450400.40\nE: 678400.40"},
    ]

    # Reprodução exata do defeito da implementação anterior (idx = 1 estático):
    remanescentes_bug = [p.copy() for p in pts if p["SEQ"] != 2]
    idx_bug = 1
    pontos_defeito = []
    for p in remanescentes_bug:
        item = p.copy()
        item["SEQ"] = idx_bug  # sem incremento!
        pontos_defeito.append(item)
    # Todos os pontos assumiam SEQ = 1 (defeito reportado)
    assert [p["SEQ"] for p in pontos_defeito] == [1, 1, 1]

    # Com a correção:
    pontos_corrigidos = py_excluir_ponto(pts, 2)
    assert [p["SEQ"] for p in pontos_corrigidos] == [1, 2, 3]
    # Garante categoricamente que os pontos restantes NÃO assumem 1
    assert pontos_corrigidos[1]["SEQ"] == 2
    assert pontos_corrigidos[2]["SEQ"] == 3


def test_coleta_quatro_pontos_exclusao_segundo_ponto_e_revisao_consecutiva():
    """Valida o fluxo completo especificado:
    1. Coleta de 4 pontos (numeração 1, 2, 3, 4);
    2. Exclusão do 2º ponto (remanescentes 1, 2, 3);
    3. Nova revisão confirmando que a numeração permanece correta;
    4. Exclusão de outro ponto com renumeração imediata;
    5. Associação correta dos dados e preservação de coordenadas e cálculos."""
    # 1. Coleta de 4 pontos com dados reais
    p1 = py_process_point_texts(
        ["14x1ø | 2x3ø", "DEM.: 31,79kVA", "ACUM.: 198,34kVA"],
        seq=1,
        coords="N: 7450100.10\nE: 678100.10"
    )
    p1["BLOCO_POSTE_HANDLE"] = "101"

    p2 = py_process_point_texts(
        ["13x1ø | 4x3ø", "DEM.: 33,52kVA", "ACUM.: 103,32kVA"],
        seq=2,
        coords="N: 7450200.20\nE: 678200.20"
    )
    p2["BLOCO_POSTE_HANDLE"] = "102"

    p3 = py_process_point_texts(
        ["15x1ø | 3x3ø", "DEM.: 35,25kVA", "ACUM.: 82,18kVA"],
        seq=3,
        coords="N: 7450300.30\nE: 678300.30"
    )
    p3["BLOCO_POSTE_HANDLE"] = "103"

    p4 = py_process_point_texts(
        ["7x1ø | 2x2ø", "DEM.: 19,27kVA", "ACUM.: 58,92kVA"],
        seq=4,
        coords="N: 7450400.40\nE: 678400.40"
    )
    p4["BLOCO_POSTE_HANDLE"] = "104"

    pontos = [p1, p2, p3, p4]

    # Confirmar numeração inicial 1, 2, 3, 4
    assert [p["SEQ"] for p in pontos] == [1, 2, 3, 4]
    assert pontos[0]["CLIENTES"] == 16
    assert pontos[0]["POSICOES"] == 20
    assert pontos[0]["CS"] == 3

    assert pontos[1]["CLIENTES"] == 17
    assert pontos[1]["POSICOES"] == 25
    assert pontos[1]["CS"] == 3

    assert pontos[2]["CLIENTES"] == 18
    assert pontos[2]["POSICOES"] == 24
    assert pontos[2]["CS"] == 3

    assert pontos[3]["CLIENTES"] == 9
    assert pontos[3]["POSICOES"] == 11
    assert pontos[3]["CS"] == 2

    # 2. Excluir o segundo ponto (ponto 2)
    pontos = py_excluir_ponto(pontos, idx_alvo=2)

    # Confirmar que restaram 3 registros com numeração sequencial 1, 2, 3
    assert len(pontos) == 3
    assert [p["SEQ"] for p in pontos] == [1, 2, 3]

    # 3. Solicitar nova revisão: a numeração e linhas formatadas devem ser 1, 2, 3
    rev_linhas = [py_formata_linha_revisao(p) for p in pontos]
    assert rev_linhas[0].startswith("1 |")
    assert rev_linhas[1].startswith("2 |")
    assert rev_linhas[2].startswith("3 |")
    assert not any(l.startswith("1 |") for l in rev_linhas[1:])

    # Validar integridade dos dados dos 3 pontos restantes:
    # Registro 1 é o P1 original
    assert pontos[0]["RAMAIS"] == "14x%%C1 | 2x%%C3"
    assert pontos[0]["CLIENTES"] == 16
    assert pontos[0]["POSICOES"] == 20
    assert pontos[0]["CS"] == 3
    assert pontos[0]["DEMANDA"] == "31,79"
    assert pontos[0]["ACUMULADA"] == "198,34"
    assert pontos[0]["COORDENADAS"] == "N: 7450100.10\nE: 678100.10"
    assert pontos[0]["BLOCO_POSTE_HANDLE"] == "101"

    # Registro 2 é o P3 original (renumerado para 2)
    assert pontos[1]["RAMAIS"] == "15x%%C1 | 3x%%C3"
    assert pontos[1]["CLIENTES"] == 18
    assert pontos[1]["POSICOES"] == 24
    assert pontos[1]["CS"] == 3
    assert pontos[1]["DEMANDA"] == "35,25"
    assert pontos[1]["ACUMULADA"] == "82,18"
    assert pontos[1]["COORDENADAS"] == "N: 7450300.30\nE: 678300.30"
    assert pontos[1]["BLOCO_POSTE_HANDLE"] == "103"

    # Registro 3 é o P4 original (renumerado para 3)
    assert pontos[2]["RAMAIS"] == "7x%%C1 | 2x%%C2"
    assert pontos[2]["CLIENTES"] == 9
    assert pontos[2]["POSICOES"] == 11
    assert pontos[2]["CS"] == 2
    assert pontos[2]["DEMANDA"] == "19,27"
    assert pontos[2]["ACUMULADA"] == "58,92"
    assert pontos[2]["COORDENADAS"] == "N: 7450400.40\nE: 678400.40"
    assert pontos[2]["BLOCO_POSTE_HANDLE"] == "104"

    # 4. Excluir outro ponto: excluir o novo ponto 2 (que era o P3 original)
    pontos = py_excluir_ponto(pontos, idx_alvo=2)

    # Confirmar renumeração dos restantes para 1, 2
    assert len(pontos) == 2
    assert [p["SEQ"] for p in pontos] == [1, 2]

    # Verificar que os pontos restantes são P1 (SEQ=1) e P4 (SEQ=2)
    assert pontos[0]["BLOCO_POSTE_HANDLE"] == "101"
    assert pontos[0]["DEMANDA"] == "31,79"
    assert pontos[1]["BLOCO_POSTE_HANDLE"] == "104"
    assert pontos[1]["DEMANDA"] == "19,27"
    assert pontos[1]["RAMAIS"] == "7x%%C1 | 2x%%C2"

    # Segunda revisão consecutiva mantém 1 e 2 perfeitamente
    rev_linhas_2 = [py_formata_linha_revisao(p) for p in pontos]
    assert rev_linhas_2[0].startswith("1 |")
    assert rev_linhas_2[1].startswith("2 |")


def test_persistencia_recuperacao_estado_dwg_e_auto_cura():
    """Valida o mecanismo de persistência no DWG (LData) e a capacidade de auto-cura
    caso o estado anterior tenha sido persistido com defeito de numeração."""
    # Dicionário mock do DWG (LData)
    dwg_ldata = {}

    pts = [
        {"SEQ": 1, "POSTE": "P01", "RAMAIS": "8x%%C1", "CLIENTES": 8, "POSICOES": 8, "CS": 1, "DEMANDA": "10,0", "ACUMULADA": "20,0", "COORDENADAS": "N: 100\nE: 200"},
        {"SEQ": 2, "POSTE": "P02", "RAMAIS": "6x%%C1", "CLIENTES": 6, "POSICOES": 6, "CS": 1, "DEMANDA": "8,0", "ACUMULADA": "18,0", "COORDENADAS": "N: 150\nE: 250"},
        {"SEQ": 3, "POSTE": "P03", "RAMAIS": "4x%%C1", "CLIENTES": 4, "POSICOES": 4, "CS": 1, "DEMANDA": "5,0", "ACUMULADA": "10,0", "COORDENADAS": "N: 200\nE: 300"},
    ]

    # Exclusão do ponto 2 e persistência
    pts_restantes = py_excluir_ponto(pts, 2)
    dwg_ldata["OXCAD_LEVANTAMENTO"] = {"PONTOS": pts_restantes}

    # Simulação de pausa, fechamento e reabertura do DWG
    pts_recuperados = dwg_ldata["OXCAD_LEVANTAMENTO"]["PONTOS"]
    assert len(pts_recuperados) == 2
    assert [p["SEQ"] for p in pts_recuperados] == [1, 2]
    assert pts_recuperados[0]["POSTE"] == "P01"
    assert pts_recuperados[1]["POSTE"] == "P03"

    # Teste de auto-cura: simula estado corrompido herdado onde todos possuem SEQ = 1
    pontos_corrompidos = [
        {"SEQ": 1, "POSTE": "P1", "RAMAIS": "1x%%C1"},
        {"SEQ": 1, "POSTE": "P2", "RAMAIS": "2x%%C1"},
        {"SEQ": 1, "POSTE": "P3", "RAMAIS": "3x%%C1"},
        {"SEQ": 1, "POSTE": "P4", "RAMAIS": "4x%%C1"},
    ]
    curados = py_renumerar_pontos(pontos_corrompidos)
    assert [p["SEQ"] for p in curados] == [1, 2, 3, 4]
    assert curados[0]["POSTE"] == "P1"
    assert curados[1]["POSTE"] == "P2"
    assert curados[2]["POSTE"] == "P3"
    assert curados[3]["POSTE"] == "P4"

    # Exclusão no estado corrompido remove apenas o ponto alvo e normaliza os demais
    restantes_apos_cura = py_excluir_ponto(pontos_corrompidos, idx_alvo=2)
    assert len(restantes_apos_cura) == 3
    assert [p["SEQ"] for p in restantes_apos_cura] == [1, 2, 3]
    assert restantes_apos_cura[0]["POSTE"] == "P1"
    assert restantes_apos_cura[1]["POSTE"] == "P3"
    assert restantes_apos_cura[2]["POSTE"] == "P4"


def test_lisp_ast_renumeracao_estavel_e_sem_hardcoded_um():
    """Valida estaticamente no código AutoLISP que a renumeração incrementa o índice
    e que o antigo bug de atribuição estática foi completamente removido."""
    source = LISP_PATH.read_text(encoding="utf-8")

    # Funções modulares implementadas
    assert "(defun lp-renumerar-pontos (pontos / idx)" in source
    assert "(defun lp-excluir-ponto (pontos idx-alvo / i removido remanescentes)" in source
    assert "(defun lp-precisa-renumerar-p (pontos / idx precisa)" in source

    # O incremento real deve existir
    assert "(setq idx (1+ idx))" in source

    # O trecho defeituoso com idx estático em 1 NÃO deve mais existir
    assert "(setq idx 1\n                     pontos (mapcar '(lambda (p)\n                                       (subst (cons \"SEQ\" idx)" not in source
    assert "(setq idx 1\r\n                     pontos (mapcar '(lambda (p)\r\n                                       (subst (cons \"SEQ\" idx)" not in source

    # lp-excluir-ponto deve ser invocado no comando principal
    assert "(setq pontos (lp-excluir-ponto pontos idx))" in source
    assert "(lp-db-salvar-pontos pontos)" in source

    # Revisão e Tabela usam exatamente a mesma fonte de numeração ("SEQ")
    assert '(lp-format-val (cdr (assoc "SEQ" p)))' in source
    assert '(vla-SetText table row-idx 0 (lp-format-val (cdr (assoc "SEQ" p))))' in source


# ==============================================================================
# Suíte de Testes de Regressão: Sincronização entre Desenho e Tabela Vinculada
# ==============================================================================

def test_persistencia_dos_handles_dos_textos_e_da_tabela():
    """Valida que cada ponto retém seus TEXT_HANDLES e que a tabela vinculada é registrada no LData."""
    p1 = py_process_point_texts(["14x1ø | 2x3ø", "DEM.: 31,79kVA"], seq=1, coords="N: 100\nE: 200")
    p1["TEXT_HANDLES"] = ["34A1", "34A2"]
    p1["BLOCO_POSTE_HANDLE"] = "99B1"

    assert "TEXT_HANDLES" in p1
    assert p1["TEXT_HANDLES"] == ["34A1", "34A2"]
    assert p1["BLOCO_POSTE_HANDLE"] == "99B1"

    # Simulação do LData do DWG
    dwg_ldata = {
        "OXCAD_LEVANTAMENTO": {
            "PONTOS": [p1],
            "TABELA_HANDLE": "TABLE_555"
        }
    }
    assert dwg_ldata["OXCAD_LEVANTAMENTO"]["TABELA_HANDLE"] == "TABLE_555"
    assert dwg_ldata["OXCAD_LEVANTAMENTO"]["PONTOS"][0]["TEXT_HANDLES"] == ["34A1", "34A2"]


def test_deteccao_alteracao_texto_e_atualizacao_dados():
    """Valida detecção de alteração de texto de referência no DWG e recálculo dos dados."""
    p1 = py_process_point_texts(["14x1ø | 2x3ø", "DEM.: 31,79kVA", "ACUM.: 198,34kVA"], seq=1)
    p1["TEXT_HANDLES"] = ["T1"]

    dwg_entities = {
        "TABLE_1": {"type": "ACAD_TABLE"},
        "T1": {"type": "MTEXT", "text": "10x1ø | 1x3ø\\PDEM.: 25,00kVA\\PACUM.: 150,00kVA"}
    }
    tbl_mock = {"rows": []}

    status, novos_pontos, afetados = py_sincronizar_levantamento([p1], "TABLE_1", dwg_entities, tbl_mock)

    assert status == ":atualizado"
    assert afetados == [1]
    assert len(novos_pontos) == 1
    # Clientes: 10 + 1 = 11 (era 16)
    assert novos_pontos[0]["CLIENTES"] == 11
    # Posições: (10*1) + (1*3) = 13 (era 20)
    assert novos_pontos[0]["POSICOES"] == 13
    # CS: ceil(13/9) = 2 (era 3)
    assert novos_pontos[0]["CS"] == 2
    assert novos_pontos[0]["DEMANDA"] == "25,00"
    assert novos_pontos[0]["ACUMULADA"] == "150,00"
    assert len(tbl_mock["rows"]) == 1


def test_ausencia_de_atualizacao_quando_nada_mudou():
    """Valida que quando os textos no DWG estão inalterados, nenhuma atualização ocorre."""
    raw = ["14x1ø | 2x3ø", "DEM.: 31,79kVA"]
    p1 = py_process_point_texts(raw, seq=1)
    p1["TEXT_HANDLES"] = ["T1", "T2"]

    dwg_entities = {
        "TABLE_1": {"type": "ACAD_TABLE"},
        "T1": {"type": "MTEXT", "text": "14x1ø | 2x3ø"},
        "T2": {"type": "TEXT", "text": "DEM.: 31,79kVA"}
    }
    tbl_mock = {"rows": [["initial"]]}

    status, novos_pontos, afetados = py_sincronizar_levantamento([p1], "TABLE_1", dwg_entities, tbl_mock)

    assert status == ":sem-alteracoes"
    assert afetados == []
    # Tabela mock não deve ter sido regravada
    assert tbl_mock["rows"] == [["initial"]]


def test_atualizacao_dos_valores_calculados():
    """Valida atualização exata de posições, caixas de serviço e ramais mantendo coordenadas e poste."""
    p1 = py_process_point_texts(["P112600B", "8x1ø | 6x3ø"], seq=1, coords="N: 7000.10\nE: 6000.20")
    p1["TEXT_HANDLES"] = ["TXT_P1"]
    p1["BLOCO_POSTE_HANDLE"] = "BLK_CO_1"

    # 8x1 e 6x3 = 14 clientes, 26 posições, 3 CS
    assert p1["CLIENTES"] == 14
    assert p1["POSICOES"] == 26
    assert p1["CS"] == 3

    # Usuário alterou no CAD para 4x1ø | 2x3ø
    dwg_entities = {
        "TBL": {"type": "ACAD_TABLE"},
        "TXT_P1": {"type": "MTEXT", "text": "P112600B\\P4x1ø | 2x3ø"}
    }
    status, novos, afetados = py_sincronizar_levantamento([p1], "TBL", dwg_entities)

    assert status == ":atualizado"
    # 4x1 e 2x3 = 6 clientes, 10 posições, 2 CS
    assert novos[0]["CLIENTES"] == 6
    assert novos[0]["POSICOES"] == 10
    assert novos[0]["CS"] == 2
    assert novos[0]["COORDENADAS"] == "N: 7000.10\nE: 6000.20"
    assert novos[0]["BLOCO_POSTE_HANDLE"] == "BLK_CO_1"


def test_recalculo_demanda_acumulada_pontos_seguintes():
    """Valida que quando a demanda de um ponto é alterada, a demanda acumulada dos pontos
    posteriores é automaticamente recalculada em cadeia."""
    p1 = py_process_point_texts(["DEM.: 10,0kVA", "ACUM.: 10,0kVA"], seq=1)
    p1["TEXT_HANDLES"] = ["T1"]
    p2 = py_process_point_texts(["DEM.: 8,0kVA", "ACUM.: 18,0kVA"], seq=2)
    p2["TEXT_HANDLES"] = ["T2"]
    p3 = py_process_point_texts(["DEM.: 5,0kVA", "ACUM.: 23,0kVA"], seq=3)
    p3["TEXT_HANDLES"] = ["T3"]

    pontos = [p1, p2, p3]

    # No desenho ativo, o projetista editou APENAS o texto de T1 (P1) para 15,0kVA.
    # Os textos de T2 e T3 no DWG continuam com seus valores originais.
    dwg_entities = {
        "TBL": {"type": "ACAD_TABLE"},
        "T1": {"type": "TEXT", "text": "DEM.: 15,0kVA"},
        "T2": {"type": "TEXT", "text": "DEM.: 8,0kVA\\PACUM.: 18,0kVA"},
        "T3": {"type": "TEXT", "text": "DEM.: 5,0kVA\\PACUM.: 23,0kVA"}
    }

    status, novos, afetados = py_sincronizar_levantamento(pontos, "TBL", dwg_entities)

    assert status == ":atualizado"
    assert 1 in afetados
    # P1 atualizado: demanda 15,0, acum 15,0
    assert novos[0]["DEMANDA"] == "15,0"
    assert novos[0]["ACUMULADA"] == "15,00"
    # P2 posterior recalculado: 15,0 + 8,0 = 23,00
    assert novos[1]["DEMANDA"] == "8,0"
    assert novos[1]["ACUMULADA"] == "23,00"
    # P3 posterior recalculado: 23,00 + 5,0 = 28,00
    assert novos[2]["DEMANDA"] == "5,0"
    assert novos[2]["ACUMULADA"] == "28,00"


def test_preservacao_da_ordem_e_dados_dos_pontos():
    """Valida que a sincronização preserva estritamente a sequência 1, 2, 3 e metadados."""
    pts = [
        {"SEQ": 1, "POSTE": "P01", "RAMAIS": "1x%%C1", "COORDENADAS": "C1", "TEXT_HANDLES": ["H1"], "RAW": ["1x1ø"], "BLOCO_POSTE_HANDLE": "B1"},
        {"SEQ": 2, "POSTE": "P02", "RAMAIS": "2x%%C1", "COORDENADAS": "C2", "TEXT_HANDLES": ["H2"], "RAW": ["2x1ø"], "BLOCO_POSTE_HANDLE": "B2"},
        {"SEQ": 3, "POSTE": "P03", "RAMAIS": "3x%%C1", "COORDENADAS": "C3", "TEXT_HANDLES": ["H3"], "RAW": ["3x1ø"], "BLOCO_POSTE_HANDLE": "B3"},
    ]
    dwg = {
        "TBL": {"type": "ACAD_TABLE"},
        "H1": {"type": "TEXT", "text": "1x1ø"},
        "H2": {"type": "TEXT", "text": "4x1ø"},  # alterado
        "H3": {"type": "TEXT", "text": "3x1ø"}
    }

    status, novos, afetados = py_sincronizar_levantamento(pts, "TBL", dwg)
    assert status == ":atualizado"
    assert [p["SEQ"] for p in novos] == [1, 2, 3]
    assert [p["POSTE"] for p in novos] == ["P01", "P02", "P03"]
    assert [p["COORDENADAS"] for p in novos] == ["C1", "C2", "C3"]
    assert [p["BLOCO_POSTE_HANDLE"] for p in novos] == ["B1", "B2", "B3"]
    assert novos[1]["RAMAIS"] == "4x%%C1"


def test_manutencao_da_mesma_tabela_sem_duplicacao():
    """Valida que a tabela vinculada existente é atualizada in-place sem gerar nova tabela."""
    p1 = py_process_point_texts(["8x1ø"], seq=1)
    p1["TEXT_HANDLES"] = ["T1"]

    dwg = {
        "TABELA_EXISTENTE_100": {"type": "ACAD_TABLE"},
        "T1": {"type": "TEXT", "text": "12x1ø"}
    }
    tbl_mock = {"id": "TABELA_EXISTENTE_100", "rows": []}

    status, novos, afetados = py_sincronizar_levantamento([p1], "TABELA_EXISTENTE_100", dwg, tbl_mock)
    assert status == ":atualizado"
    assert tbl_mock["id"] == "TABELA_EXISTENTE_100"  # mesma identidade preservada
    assert tbl_mock["rows"][0][2] == "12x%%C1"


def test_recuperacao_estado_apos_reabrir_dwg():
    """Valida restauração do estado persistido em LData após salvar, fechar e reabrir o DWG."""
    dwg_salvo = {
        "OXCAD_LEVANTAMENTO": {
            "PONTOS": [
                {"SEQ": 1, "POSTE": "P1", "RAMAIS": "1x%%C1", "TEXT_HANDLES": ["H1"], "RAW": ["1x1ø"], "COORDENADAS": "N:1\nE:2"},
                {"SEQ": 2, "POSTE": "P2", "RAMAIS": "2x%%C1", "TEXT_HANDLES": ["H2"], "RAW": ["2x1ø"], "COORDENADAS": "N:3\nE:4"}
            ],
            "TABELA_HANDLE": "TBL_PERSISTIDA"
        }
    }

    # Simula leitura do LData ao abrir o DWG
    pontos_recuperados = dwg_salvo["OXCAD_LEVANTAMENTO"]["PONTOS"]
    tbl_recuperada = dwg_salvo["OXCAD_LEVANTAMENTO"]["TABELA_HANDLE"]

    assert len(pontos_recuperados) == 2
    assert tbl_recuperada == "TBL_PERSISTIDA"

    # Simula execução de sincronização com os dados recuperados
    dwg_entities = {
        "TBL_PERSISTIDA": {"type": "ACAD_TABLE"},
        "H1": {"type": "TEXT", "text": "1x1ø"},
        "H2": {"type": "TEXT", "text": "5x1ø"}  # alterado enquanto o DWG estava fechado
    }
    status, novos, afetados = py_sincronizar_levantamento(pontos_recuperados, tbl_recuperada, dwg_entities)
    assert status == ":atualizado"
    assert afetados == [2]
    assert novos[1]["RAMAIS"] == "5x%%C1"


def test_tratamento_texto_excluido_do_desenho():
    """Valida que quando um texto de referência é excluído do CAD, a sincronização é interrompida com segurança."""
    p1 = py_process_point_texts(["8x1ø"], seq=1)
    p1["TEXT_HANDLES"] = ["HANDLE_APAGADO"]

    dwg = {
        "TBL": {"type": "ACAD_TABLE"}
        # HANDLE_APAGADO não existe no DWG
    }

    status, msg, afetados = py_sincronizar_levantamento([p1], "TBL", dwg)
    assert status == ":erro"
    assert "Entidade não encontrada no desenho (excluída)" in msg
    # Não corrompe nem inventa dados
    assert p1["RAMAIS"] == "8x%%C1"


def test_tratamento_tabela_excluida_e_recuperacao():
    """Valida detecção de tabela excluída pelo usuário no CAD sem recriação silenciosa."""
    p1 = py_process_point_texts(["8x1ø"], seq=1)
    p1["TEXT_HANDLES"] = ["T1"]

    dwg = {
        "T1": {"type": "TEXT", "text": "8x1ø"}
        # A tabela TBL_DELETADA não existe mais em dwg
    }

    status, handle_retornado, afetados = py_sincronizar_levantamento([p1], "TBL_DELETADA", dwg)
    assert status == ":tabela-inexistente"
    assert handle_retornado == "TBL_DELETADA"


def test_protecao_contra_estado_inconsistente():
    """Valida proteção contra pontos nulos, handles inválidos ou entidades que não são tabelas."""
    # Pontos vazios
    assert py_sincronizar_levantamento([], "TBL", {}) == (":nada-a-fazer", [], [])
    assert py_sincronizar_levantamento(None, "TBL", {}) == (":nada-a-fazer", None, [])
    assert py_sincronizar_levantamento([{"SEQ": 1}], None, {}) == (":nada-a-fazer", [{"SEQ": 1}], [])

    # Handle apontando para entidade que não é tabela (ex: LINE)
    dwg_com_linha = {"OBJ_LINHA": {"type": "LINE"}}
    status, _, _ = py_sincronizar_levantamento([{"SEQ": 1, "TEXT_HANDLES": ["H"]}], "OBJ_LINHA", dwg_com_linha)
    assert status == ":tabela-inexistente"


def test_compatibilidade_com_exclusao_e_renumeracao_de_pontos():
    """Valida que a exclusão de pontos mantém a integridade de TEXT_HANDLES e renumera normalmente."""
    p1 = {"SEQ": 1, "POSTE": "P1", "TEXT_HANDLES": ["H1"], "RAW": ["1x1ø"]}
    p2 = {"SEQ": 2, "POSTE": "P2", "TEXT_HANDLES": ["H2"], "RAW": ["2x1ø"]}
    p3 = {"SEQ": 3, "POSTE": "P3", "TEXT_HANDLES": ["H3"], "RAW": ["3x1ø"]}

    pontos = [p1, p2, p3]
    restantes = py_excluir_ponto(pontos, idx_alvo=2)

    assert len(restantes) == 2
    assert [p["SEQ"] for p in restantes] == [1, 2]
    assert restantes[0]["POSTE"] == "P1"
    assert restantes[0]["TEXT_HANDLES"] == ["H1"]
    assert restantes[1]["POSTE"] == "P3"
    assert restantes[1]["TEXT_HANDLES"] == ["H3"]


def test_lisp_ast_sincronizacao_e_rastreabilidade():
    """Valida estaticamente no código AutoLISP a presença dos mecanismos de sincronização e rastreabilidade."""
    source = LISP_PATH.read_text(encoding="utf-8")

    # Funções de sincronismo
    assert "(defun lp-sincronizar-levantamento" in source
    assert "(defun lp-atualizar-celulas-tabela" in source
    assert "(defun lp-validar-handle-texto" in source
    assert "(defun lp-recalcular-demandas-acumuladas" in source
    assert "(defun lp-atualizar-exclusao-tabela" in source

    # Gestão do Handle da Tabela no LData
    assert "(defun lp-db-obter-tabela-handle" in source
    assert "(defun lp-db-salvar-tabela-handle" in source
    assert "(defun lp-db-remover-tabela-handle" in source
    assert '"TABELA_HANDLE"' in source

    # Associação persistente dos handles de texto na coleta
    assert "(setq text-handles (append text-handles (list (cdr (assoc 5 (entget ent))))))" in source
    assert '(cons (cons "TEXT_HANDLES" text-handles) novo-ponto)' in source

    # Preservação da tabela e coleta na geração
    assert "(lp-db-salvar-tabela-handle tbl-handle)" in source
    assert "(lp-db-salvar-pontos pontos)" in source

    # Sincronização executada automaticamente no início de c:LEVANTAR_POSTES
    assert "(setq sync-res (lp-sincronizar-levantamento pontos tbl-handle))" in source
    assert "(= (car sync-res) :atualizado)" in source
    assert "(= (car sync-res) :sem-alteracoes)" in source
    assert "(= (car sync-res) :tabela-inexistente)" in source
    assert "(= (car sync-res) :erro)" in source


# ==============================================================================
# ==============================================================================
# Módulo CLANDESTINO LIGHT (CQTS_ZNA853248_ATUAL.xlsx) - Python Mirrors & Testes
# ==============================================================================

CLAN_LISP_PATH = ROOT / "orcamento" / "clandestino_light.lsp"
TOPO_LISP_PATH = ROOT / "orcamento" / "clandestino_topologia.lsp"


def _load_clan_lisp_list(var_name: str) -> list[float]:
    source = CLAN_LISP_PATH.read_text(encoding="utf-8")
    match = re.search(rf"\(setq\s+{re.escape(var_name)}\s*'\((\s*[\d\.\s]+)\)\)", source, re.DOTALL)
    if not match:
        raise ValueError(f"Variável {var_name} não encontrada em {CLAN_LISP_PATH}")
    return [float(x) for x in match.group(1).split()]


_DMDI_20_400 = _load_clan_lisp_list("*lp-clan-dmdi-20-400*")
_FDIV_1_300 = _load_clan_lisp_list("*lp-clan-fdiv-1-300*")


def py_clan_inteiro_p(val):
    """Verifica se o valor é estritamente numérico e inteiro."""
    if val is None or isinstance(val, bool):
        return False
    if isinstance(val, int):
        return True
    if isinstance(val, float):
        return val.is_integer()
    return False


def py_clan_validar_area(area):
    """Valida se a área residencial é um número inteiro estrito entre 20 e 400 m²."""
    if area is None or isinstance(area, bool) or not isinstance(area, (int, float)):
        return False
    if not py_clan_inteiro_p(area):
        return False
    a = int(area)
    return 20 <= a <= 400


def py_clan_obter_dmdi(area):
    """Espelho em Python de lp-clan-obter-dmdi."""
    if not py_clan_validar_area(area):
        return None
    return _DMDI_20_400[int(area) - 20]


def py_clan_validar_clientes(clientes):
    """Valida se a quantidade de clientes é um número inteiro entre 0 e 300."""
    if clientes is None or isinstance(clientes, bool) or not isinstance(clientes, (int, float)):
        return False
    if not py_clan_inteiro_p(clientes):
        return False
    c = int(clientes)
    return 0 <= c <= 300


def py_clan_obter_fdiv(clientes):
    """Espelho em Python de lp-clan-obter-fator-div."""
    if clientes is None or isinstance(clientes, bool) or not isinstance(clientes, (int, float)):
        return None
    if not py_clan_inteiro_p(clientes):
        return None
    c = int(clientes)
    if c == 0:
        return 0.0
    if not (1 <= c <= 300):
        return None
    return _FDIV_1_300[c - 1]


def py_clan_calcular_demanda(area, clientes):
    """Espelho em Python de lp-clan-calcular-demanda."""
    dmdi = py_clan_obter_dmdi(area)
    fdiv = py_clan_obter_fdiv(clientes)
    if dmdi is None or fdiv is None:
        return None
    return round(dmdi * fdiv, 2)


def py_clan_calcular_acumulada(area, clientes_acumulados):
    """Espelho em Python de lp-clan-calcular-acumulada."""
    dmdi = py_clan_obter_dmdi(area)
    fdiv = py_clan_obter_fdiv(clientes_acumulados)
    if dmdi is None or fdiv is None:
        return None
    return round(dmdi * fdiv, 2)


def py_clan_parse_cli(c):
    """Converte o valor de CLIENTES (int ou string) em inteiro."""
    if c is None or isinstance(c, bool):
        return 0
    if isinstance(c, (int, float)):
        return int(c)
    if isinstance(c, str):
        try:
            return int(float(c))
        except ValueError:
            return 0
    return 0


def py_clan_adicionar_aresta(u: str, v: str, mapa: dict) -> dict:
    u_str = str(u).upper().strip()
    v_str = str(v).upper().strip()
    if not u_str or not v_str or u_str == v_str:
        return mapa
    if u_str not in mapa:
        mapa[u_str] = []
    if v_str not in mapa[u_str]:
        mapa[u_str].append(v_str)
    return mapa


def py_clan_construir_mapa_filhos(topologia=None, pontos=None) -> dict[str, list[str]]:
    """Constrói o mapa de adjacência {pai: [filho1, filho2, ...]} a partir de topologia ou atributos."""
    mapa: dict[str, list[str]] = {}
    if topologia:
        ramos = []
        if isinstance(topologia, dict):
            lados = topologia.get("LADOS") or topologia.get("TRECHOS") or topologia.get("BRANCHES") or []
            deriv = topologia.get("DERIVACOES") or []
            ramos.extend(lados)
            ramos.extend(deriv)
        elif isinstance(topologia, list):
            ramos = topologia

        for item in ramos:
            if isinstance(item, (list, tuple)):
                if len(item) == 2 and not any(k in str(item[0]).upper() for k in ["LADO", "RAMO", "CIRCUITO"]):
                    py_clan_adicionar_aresta(item[0], item[1], mapa)
                else:
                    nodes = []
                    for n in item:
                        n_str = str(n).upper().strip()
                        if not any(k in n_str for k in ["LADO", "RAMO", "CIRCUITO", "TR "]):
                            nodes.append(n_str)
                    for i in range(len(nodes) - 1):
                        py_clan_adicionar_aresta(nodes[i], nodes[i + 1], mapa)

    if pontos:
        for p in pontos:
            poste = str(p.get("POSTE", "")).upper().strip()
            if poste and poste != "-":
                jusante = p.get("JUSANTE")
                if jusante:
                    if isinstance(jusante, (list, tuple)):
                        for j in jusante:
                            py_clan_adicionar_aresta(poste, j, mapa)
                    else:
                        py_clan_adicionar_aresta(poste, jusante, mapa)
                montante = p.get("MONTANTE")
                if montante and montante != "-":
                    py_clan_adicionar_aresta(montante, poste, mapa)
    return mapa


def py_clan_obter_jusante(poste: str, mapa_filhos: dict[str, list[str]]) -> list[str]:
    """Retorna a lista de nomes de nós a jusante (descendentes) de poste na árvore."""
    p_up = str(poste).upper().strip()
    visitados = []
    fila = list(mapa_filhos.get(p_up, []))
    while fila:
        atual = fila.pop(0)
        if atual not in visitados:
            visitados.append(atual)
            for f in mapa_filhos.get(atual, []):
                if f not in visitados:
                    fila.append(f)
    return visitados


def py_clan_recalcular_pontos(pontos, area_padrao=50, sentido="PONTA->FONTE", topologia=None):
    """Espelho em Python de lp-clan-recalcular-pontos com suporte a topologia e cálculo transacional."""
    if not pontos or not py_clan_validar_area(area_padrao):
        return pontos

    pts = [dict(p) for p in pontos]
    area = int(area_padrao)

    topo = topologia
    if topo is None and isinstance(sentido, (list, dict)):
        topo = sentido

    mapa_filhos = py_clan_construir_mapa_filhos(topo, pts)

    # 1. Validação estrita de todos os clientes locais
    cli_lookup = {}
    for p in pts:
        poste = str(p.get("POSTE", "")).upper().strip()
        raw_cli = p.get("CLIENTES")
        if raw_cli is None or isinstance(raw_cli, bool):
            return pontos
        if isinstance(raw_cli, float) and not raw_cli.is_integer():
            return pontos
        try:
            cli = int(raw_cli)
        except (ValueError, TypeError):
            return pontos
        if not py_clan_validar_clientes(cli):
            return pontos
        cli_lookup[poste] = cli

    # Modo topológico
    if mapa_filhos:
        # Pré-validação de limites acumulados a jusante
        for p in pts:
            poste = str(p.get("POSTE", "")).upper().strip()
            local_cli = cli_lookup.get(poste, 0)
            jusante_postes = py_clan_obter_jusante(poste, mapa_filhos)
            acum_cli = local_cli + sum(cli_lookup.get(j, 0) for j in jusante_postes)
            if acum_cli > 300:
                return pontos

        for p in pts:
            poste = str(p.get("POSTE", "")).upper().strip()
            local_cli = cli_lookup.get(poste, 0)
            jusante_postes = py_clan_obter_jusante(poste, mapa_filhos)
            acum_cli = local_cli + sum(cli_lookup.get(j, 0) for j in jusante_postes)
            dem = py_clan_calcular_demanda(area, local_cli)
            acum = py_clan_calcular_acumulada(area, acum_cli)
            if dem is None or acum is None:
                return pontos
            p["DEMANDA"] = f"{dem:.2f}".replace(".", ",")
            p["ACUMULADA"] = f"{acum:.2f}".replace(".", ",")
        return pts

    # Modo sequencial linear
    sentido_str = str(sentido).upper() if isinstance(sentido, str) else "PONTA->FONTE"
    if sentido_str == "FONTE->PONTA":
        tot = 0
        cli_map = []
        for p in reversed(pts):
            c = cli_lookup.get(str(p.get("POSTE", "")).upper().strip(), 0)
            tot += c
            if tot > 300:
                return pontos
            cli_map.insert(0, tot)
        for p, acum_c in zip(pts, cli_map):
            c = cli_lookup.get(str(p.get("POSTE", "")).upper().strip(), 0)
            dem = py_clan_calcular_demanda(area, c)
            acum = py_clan_calcular_acumulada(area, acum_c)
            if dem is None or acum is None:
                return pontos
            p["DEMANDA"] = f"{dem:.2f}".replace(".", ",")
            p["ACUMULADA"] = f"{acum:.2f}".replace(".", ",")
        return pts
    else:
        # PONTA->FONTE
        tot = 0
        for p in pts:
            c = cli_lookup.get(str(p.get("POSTE", "")).upper().strip(), 0)
            tot += c
            if tot > 300:
                return pontos
        acum_c = 0
        for p in pts:
            c = cli_lookup.get(str(p.get("POSTE", "")).upper().strip(), 0)
            acum_c += c
            dem = py_clan_calcular_demanda(area, c)
            acum = py_clan_calcular_acumulada(area, acum_c)
            if dem is None or acum is None:
                return pontos
            p["DEMANDA"] = f"{dem:.2f}".replace(".", ",")
            p["ACUMULADA"] = f"{acum:.2f}".replace(".", ",")
        return pts


# ------------------------------------------------------------------------------
# Testes Unitários de Conformidade e Segurança
# ------------------------------------------------------------------------------

def test_clandestino_dmdi_valores_normativos():
    """Valida DMDI para as áreas obrigatórias: 20, 42, 43, 50 e 400 m² (DB!A36:B416)."""
    assert py_clan_obter_dmdi(20) == 1.62
    assert py_clan_obter_dmdi(42) == 1.62
    assert py_clan_obter_dmdi(43) == 1.64
    assert py_clan_obter_dmdi(50) == 1.88
    assert py_clan_obter_dmdi(400) == 12.13


def test_clandestino_fator_diversificacao_valores_normativos():
    """Valida fatores de diversificação para os clientes obrigatórios: 1, 4, 5, 10, 13, 50, 132, 278, 279 e 300."""
    assert py_clan_obter_fdiv(1) == 3.88
    assert py_clan_obter_fdiv(4) == 3.88
    assert py_clan_obter_fdiv(5) == 4.84
    assert py_clan_obter_fdiv(10) == 9.64
    assert py_clan_obter_fdiv(13) == 11.98
    assert py_clan_obter_fdiv(50) == 35.34
    assert py_clan_obter_fdiv(132) == 70.99
    assert py_clan_obter_fdiv(278) == 83.00
    assert py_clan_obter_fdiv(279) == 83.00
    assert py_clan_obter_fdiv(300) == 83.00


def test_clandestino_demandas_individuais_e_acumuladas():
    """Valida o cálculo individual e acumulado comprovando a não-linearidade da rede clandestina."""
    area = 50  # DMDI = 1.88 kVA

    # Poste A: 24 clientes -> 1.88 * 19.88 = 37.37 kVA
    dem_a = py_clan_calcular_demanda(area, 24)
    assert dem_a == 37.37

    # Poste B: 26 clientes -> 1.88 * 21.10 = 39.67 kVA
    dem_b = py_clan_calcular_demanda(area, 26)
    assert dem_b == 39.67

    # Demanda acumulada de A + B (total 50 clientes): 1.88 * 35.34 = 66.44 kVA
    acum_ab = py_clan_calcular_acumulada(area, 50)
    assert acum_ab == 66.44

    # PROVA NÃO-LINEAR: Demanda acumulada (66.44) é estritamente diferente da soma linear (77.04)
    assert round(dem_a + dem_b, 2) == 77.04
    assert acum_ab != round(dem_a + dem_b, 2)


def test_clandestino_acumulado_multiplos_pontos_topologia_real():
    """Valida acumulado com múltiplos pontos a jusante pela topologia real (circuito RUA IRINÉIA VERÇOSA)."""
    # 4 pontos reais da planilha LIGHT CQTS_ZNA853248_ATUAL.xlsx (PROJ1, linhas 13-16)
    # P7 (24 cli), P6 (26 cli), P5 (10 cli), P4 (13 cli)
    # Levantamento da ponta para a fonte (P7 -> P6 -> P5 -> P4):
    pontos = [
        {"SEQ": 1, "POSTE": "P7", "CLIENTES": 24},
        {"SEQ": 2, "POSTE": "P6", "CLIENTES": 26},
        {"SEQ": 3, "POSTE": "P5", "CLIENTES": 10},
        {"SEQ": 4, "POSTE": "P4", "CLIENTES": 13},
    ]

    recalc = py_clan_recalcular_pontos(pontos, area_padrao=50, sentido="PONTA->FONTE")

    # Linha 16 (P7): 24 clientes locais, 24 acumulados -> 37.37 / 37.37
    assert recalc[0]["DEMANDA"] == "37,37"
    assert recalc[0]["ACUMULADA"] == "37,37"

    # Linha 15 (P6): 26 clientes locais, 50 acumulados -> 39.67 / 66.44
    assert recalc[1]["DEMANDA"] == "39,67"
    assert recalc[1]["ACUMULADA"] == "66,44"

    # Linha 14 (P5): 10 clientes locais, 60 acumulados -> 18.12 / 76.97
    assert recalc[2]["DEMANDA"] == "18,12"
    assert recalc[2]["ACUMULADA"] == "76,97"

    # Linha 13 (P4): 13 clientes locais, 73 acumulados -> 22.52 / 90.65
    assert recalc[3]["DEMANDA"] == "22,52"
    assert recalc[3]["ACUMULADA"] == "90,65"

    # Topologia inversa: FONTE->PONTA (P4 -> P5 -> P6 -> P7)
    pontos_rev = [
        {"SEQ": 1, "POSTE": "P4", "CLIENTES": 13},
        {"SEQ": 2, "POSTE": "P5", "CLIENTES": 10},
        {"SEQ": 3, "POSTE": "P6", "CLIENTES": 26},
        {"SEQ": 4, "POSTE": "P7", "CLIENTES": 24},
    ]
    recalc_rev = py_clan_recalcular_pontos(pontos_rev, area_padrao=50, sentido="FONTE->PONTA")
    assert recalc_rev[0]["ACUMULADA"] == "90,65"  # P4 acumula todos os 73 clientes
    assert recalc_rev[1]["ACUMULADA"] == "76,97"  # P5 acumula 60 clientes
    assert recalc_rev[2]["ACUMULADA"] == "66,44"  # P6 acumula 50 clientes
    assert recalc_rev[3]["ACUMULADA"] == "37,37"  # P7 é ponta (24 clientes)


def test_clandestino_atualizacao_demanda_e_acumulados_apos_alteracao_ramais():
    """Valida recálculo dinâmico da demanda e de todos os acumulados ao editar ramais no CAD e sincronizar."""
    p1 = {
        "SEQ": 1, "POSTE": "P7", "RAMAIS": "24x1ø", "CLIENTES": "24",
        "DEMANDA": "37,37", "ACUMULADA": "37,37",
        "TEXT_HANDLES": ["TXT_P7"], "RAW": ["24x1ø"]
    }
    p2 = {
        "SEQ": 2, "POSTE": "P6", "RAMAIS": "26x1ø", "CLIENTES": "26",
        "DEMANDA": "39,67", "ACUMULADA": "66,44",
        "TEXT_HANDLES": ["TXT_P6"], "RAW": ["26x1ø"]
    }

    # Usuário edita o texto de ramal do P7 no CAD para 30x1ø
    dwg = {
        "TBL": {"type": "ACAD_TABLE"},
        "TXT_P7": {"type": "TEXT", "text": "30x1ø"},
        "TXT_P6": {"type": "TEXT", "text": "26x1ø"},
    }

    status, atualizados, afetados = py_sincronizar_levantamento([p1, p2], "TBL", dwg)
    assert status == ":atualizado"
    assert afetados == [1]

    # Recalcula cadeia no modo clandestino
    recalculados = py_clan_recalcular_pontos(atualizados, area_padrao=50, sentido="PONTA->FONTE")

    # P7 atualizado para 30 clientes (fdiv = 23.54 -> dem = 44.26 / acum = 44.26)
    assert str(recalculados[0]["CLIENTES"]) == "30"
    assert recalculados[0]["DEMANDA"] == "44,26"
    assert recalculados[0]["ACUMULADA"] == "44,26"

    # P6 mantém 26 clientes locais, mas acumulado sobe para 56 clientes (fdiv = 38.70 -> acum = 72.76)
    assert str(recalculados[1]["CLIENTES"]) == "26"
    assert recalculados[1]["DEMANDA"] == "39,67"
    assert recalculados[1]["ACUMULADA"] == "72,76"


def test_clandestino_entradas_invalidas_e_limites_nao_suportados():
    """Valida a rejeição explícita e interrupção de cálculo para áreas <20, >400, decimais e clientes >300."""
    # Áreas menores que 20 m²
    assert py_clan_obter_dmdi(19) is None
    assert py_clan_obter_dmdi(0) is None
    assert py_clan_obter_dmdi(-10) is None

    # Áreas maiores que 400 m² (não extrapola)
    assert py_clan_obter_dmdi(401) is None
    assert py_clan_obter_dmdi(500) is None

    # Áreas decimais (não arredonda silenciosamente)
    assert py_clan_obter_dmdi(20.5) is None
    assert py_clan_obter_dmdi(49.6) is None
    assert py_clan_obter_dmdi(50.4) is None

    # Áreas não numéricas ou nulas
    assert py_clan_obter_dmdi(None) is None
    assert py_clan_obter_dmdi("50") is None

    # Quantidade de clientes > 300 (não extrapola ou limita silenciosamente)
    assert py_clan_obter_fdiv(301) is None
    assert py_clan_obter_fdiv(500) is None

    # Quantidade de clientes negativa ou decimal
    assert py_clan_obter_fdiv(-1) is None
    assert py_clan_obter_fdiv(10.5) is None
    assert py_clan_obter_fdiv(None) is None

    # Demanda e acumulada interrompem retornando None quando entrada é inválida
    assert py_clan_calcular_demanda(19, 10) is None
    assert py_clan_calcular_demanda(401, 10) is None
    assert py_clan_calcular_demanda(50, 301) is None
    assert py_clan_calcular_acumulada(50.5, 50) is None
    assert py_clan_calcular_acumulada(50, 350) is None

    # Recalcular pontos com entrada inválida interrompe preservando lista sem extrapolação
    pts_invalidos = [{"SEQ": 1, "POSTE": "P1", "CLIENTES": 350}]
    resultado = py_clan_recalcular_pontos(pts_invalidos, area_padrao=50)
    assert resultado == pts_invalidos


def test_clandestino_persistencia_da_configuracao_entre_execucoes():
    """Valida o contrato de persistência no DWG via LData para chaves MODO, AREA_CLANDESTINO, SENTIDO e TOPOLOGIA."""
    source = CLAN_LISP_PATH.read_text(encoding="utf-8")
    assert '"MODO"' in source
    assert '"AREA_CLANDESTINO"' in source
    assert '"SENTIDO_ACUMULACAO"' in source
    assert '"TOPOLOGIA"' in source
    assert "(defun lp-db-obter-modo" in source
    assert "(defun lp-db-salvar-modo" in source
    assert "(defun lp-db-obter-area" in source
    assert "(defun lp-db-salvar-area" in source
    assert "(defun lp-db-obter-sentido" in source
    assert "(defun lp-db-salvar-sentido" in source
    assert "(defun lp-db-obter-topologia" in source
    assert "(defun lp-db-salvar-topologia" in source
    assert "(defun lp-clan-obter-ultimo-erro" in source


def test_regressao_integral_modo_normal():
    """Valida regressão estrita do modo NORMAL: preserva leitura literal de DEM.: e ACUM.: sem cálculo clandestino."""
    raw = [
        "POSTE 10/300",
        "8x1ø + 2x2ø",
        "DEM.: 15.50",
        "ACUM.: 45.20"
    ]
    ponto = py_process_point_texts(raw, seq=1)
    assert ponto["CLIENTES"] == 10
    assert ponto["DEMANDA"] == "15.50"
    assert ponto["ACUMULADA"] == "45.20"


def test_clandestino_topologia_independencia_da_ordem_de_cadastro():
    """RISCO 1: Valida que ordens distintas de coleta/cadastro produzem resultados idênticos via topologia física."""
    # Topologia da planilha oficial LIGHT CQTS_ZNA853248_ATUAL.xlsx: TR -> P4 -> P5 -> P6 -> P7
    topologia = [["LADO 1", "P4", "P5", "P6", "P7"]]

    # Cenário A: Ordem da fonte para a ponta (P4, P5, P6, P7)
    cenario_a = [
        {"SEQ": 1, "POSTE": "P4", "CLIENTES": 13},
        {"SEQ": 2, "POSTE": "P5", "CLIENTES": 10},
        {"SEQ": 3, "POSTE": "P6", "CLIENTES": 26},
        {"SEQ": 4, "POSTE": "P7", "CLIENTES": 24},
    ]

    # Cenário B: Ordem da ponta para a fonte (P7, P6, P5, P4)
    cenario_b = [
        {"SEQ": 1, "POSTE": "P7", "CLIENTES": 24},
        {"SEQ": 2, "POSTE": "P6", "CLIENTES": 26},
        {"SEQ": 3, "POSTE": "P5", "CLIENTES": 10},
        {"SEQ": 4, "POSTE": "P4", "CLIENTES": 13},
    ]

    # Cenário C: Ordem arbitrária/desordenada de campo (P5, P7, P4, P6)
    cenario_c = [
        {"SEQ": 1, "POSTE": "P5", "CLIENTES": 10},
        {"SEQ": 2, "POSTE": "P7", "CLIENTES": 24},
        {"SEQ": 3, "POSTE": "P4", "CLIENTES": 13},
        {"SEQ": 4, "POSTE": "P6", "CLIENTES": 26},
    ]

    res_a = {p["POSTE"]: p for p in py_clan_recalcular_pontos(cenario_a, area_padrao=50, topologia=topologia)}
    res_b = {p["POSTE"]: p for p in py_clan_recalcular_pontos(cenario_b, area_padrao=50, topologia=topologia)}
    res_c = {p["POSTE"]: p for p in py_clan_recalcular_pontos(cenario_c, area_padrao=50, topologia=topologia)}

    # Valores canônicos extraídos da planilha LIGHT CQTS_ZNA853248_ATUAL.xlsx:
    # P7: 24 clientes locais / 24 acumulados -> Dem: 37,37 / Acum: 37,37
    # P6: 26 clientes locais / 50 acumulados -> Dem: 39,67 / Acum: 66,44
    # P5: 10 clientes locais / 60 acumulados -> Dem: 18,12 / Acum: 76,97
    # P4: 13 clientes locais / 73 acumulados -> Dem: 22,52 / Acum: 90,65
    for res in [res_a, res_b, res_c]:
        assert res["P7"]["DEMANDA"] == "37,37"
        assert res["P7"]["ACUMULADA"] == "37,37"

        assert res["P6"]["DEMANDA"] == "39,67"
        assert res["P6"]["ACUMULADA"] == "66,44"

        assert res["P5"]["DEMANDA"] == "18,12"
        assert res["P5"]["ACUMULADA"] == "76,97"

        assert res["P4"]["DEMANDA"] == "22,52"
        assert res["P4"]["ACUMULADA"] == "90,65"

    # Confirmação estrita de equivalência absoluta entre todas as ordens
    for poste in ["P4", "P5", "P6", "P7"]:
        assert res_a[poste]["DEMANDA"] == res_b[poste]["DEMANDA"] == res_c[poste]["DEMANDA"]
        assert res_a[poste]["ACUMULADA"] == res_b[poste]["ACUMULADA"] == res_c[poste]["ACUMULADA"]


def test_clandestino_topologia_com_derivacao_independencia_da_ordem():
    """RISCO 1: Valida topologia com bifurcação/derivação da planilha real (P2 -> P4... e P2 -> P3)."""
    # Topologia com tronco e derivação: TR -> P2 -> P4 -> P5 -> P6 -> P7 e P2 -> P3
    topologia = {
        "TR": "TR 01",
        "LADOS": [["LADO 1", "P2", "P4", "P5", "P6", "P7"]],
        "DERIVACOES": [["DERIVACAO P2", "P2", "P3"]]
    }

    # Ordem 1: Natural da fonte para as pontas
    ordem_1 = [
        {"SEQ": 1, "POSTE": "P2", "CLIENTES": 0},
        {"SEQ": 2, "POSTE": "P3", "CLIENTES": 10},
        {"SEQ": 3, "POSTE": "P4", "CLIENTES": 13},
        {"SEQ": 4, "POSTE": "P5", "CLIENTES": 10},
        {"SEQ": 5, "POSTE": "P6", "CLIENTES": 26},
        {"SEQ": 6, "POSTE": "P7", "CLIENTES": 24},
    ]

    # Ordem 2: Totalmente misturada
    ordem_2 = [
        {"SEQ": 1, "POSTE": "P6", "CLIENTES": 26},
        {"SEQ": 2, "POSTE": "P2", "CLIENTES": 0},
        {"SEQ": 3, "POSTE": "P7", "CLIENTES": 24},
        {"SEQ": 4, "POSTE": "P3", "CLIENTES": 10},
        {"SEQ": 5, "POSTE": "P5", "CLIENTES": 10},
        {"SEQ": 6, "POSTE": "P4", "CLIENTES": 13},
    ]

    res_1 = {p["POSTE"]: p for p in py_clan_recalcular_pontos(ordem_1, area_padrao=50, topologia=topologia)}
    res_2 = {p["POSTE"]: p for p in py_clan_recalcular_pontos(ordem_2, area_padrao=50, topologia=topologia)}

    # P2 acumula jusante total: 0 + 10 (P3) + 73 (P4+P5+P6+P7) = 83 clientes -> fdiv(83) = 53.82 -> 101.18 kVA
    assert res_1["P2"]["ACUMULADA"] == res_2["P2"]["ACUMULADA"] == "101,18"
    assert res_1["P2"]["DEMANDA"] == res_2["P2"]["DEMANDA"] == "0,00"

    # P3 derivação acumula apenas seus 10 clientes: fdiv(10) = 9.64 -> 18.12 kVA
    assert res_1["P3"]["ACUMULADA"] == res_2["P3"]["ACUMULADA"] == "18,12"
    assert res_1["P3"]["DEMANDA"] == res_2["P3"]["DEMANDA"] == "18,12"

    # P4 a P7 mantêm valores canônicos idênticos em ambas as ordens
    assert res_1["P4"]["ACUMULADA"] == res_2["P4"]["ACUMULADA"] == "90,65"
    assert res_1["P5"]["ACUMULADA"] == res_2["P5"]["ACUMULADA"] == "76,97"
    assert res_1["P6"]["ACUMULADA"] == res_2["P6"]["ACUMULADA"] == "66,44"
    assert res_1["P7"]["ACUMULADA"] == res_2["P7"]["ACUMULADA"] == "37,37"


def test_clandestino_falha_calculo_preservacao_integral_de_dados_validos():
    """RISCO 2: Valida que qualquer falha (área, clientes, limites) preserva 100% dos dados válidos sem zeros ou traços."""
    pontos_originais = [
        {"SEQ": 1, "POSTE": "P4", "RAMAIS": "13x%%C1", "CLIENTES": 13, "DEMANDA": "22,52", "ACUMULADA": "90,65", "COORDENADAS": "X:1 Y:1"},
        {"SEQ": 2, "POSTE": "P5", "RAMAIS": "10x%%C1", "CLIENTES": 10, "DEMANDA": "18,12", "ACUMULADA": "76,97", "COORDENADAS": "X:2 Y:2"},
        {"SEQ": 3, "POSTE": "P6", "RAMAIS": "26x%%C1", "CLIENTES": 26, "DEMANDA": "39,67", "ACUMULADA": "66,44", "COORDENADAS": "X:3 Y:3"},
        {"SEQ": 4, "POSTE": "P7", "RAMAIS": "24x%%C1", "CLIENTES": 24, "DEMANDA": "37,37", "ACUMULADA": "37,37", "COORDENADAS": "X:4 Y:4"},
    ]
    topologia = [["LADO 1", "P4", "P5", "P6", "P7"]]

    # 1. Falha por área < 20
    res_area_baixa = py_clan_recalcular_pontos(pontos_originais, area_padrao=19, topologia=topologia)
    assert res_area_baixa == pontos_originais

    # 2. Falha por área > 400
    res_area_alta = py_clan_recalcular_pontos(pontos_originais, area_padrao=401, topologia=topologia)
    assert res_area_alta == pontos_originais

    # 3. Falha por área decimal (ex: 50.5 m²)
    res_area_dec = py_clan_recalcular_pontos(pontos_originais, area_padrao=50.5, topologia=topologia)
    assert res_area_dec == pontos_originais

    # 4. Falha por clientes individuais > 300
    pts_cli_excedente = [
        dict(pontos_originais[0], CLIENTES=305),
        pontos_originais[1],
        pontos_originais[2],
        pontos_originais[3],
    ]
    res_cli_alta = py_clan_recalcular_pontos(pts_cli_excedente, area_padrao=50, topologia=topologia)
    assert res_cli_alta == pts_cli_excedente
    # Garante que nenhum dado existente virou "-" ou "0,00"
    assert res_cli_alta[0]["DEMANDA"] == "22,52"
    assert res_cli_alta[0]["ACUMULADA"] == "90,65"

    # 5. Falha por clientes acumulados a jusante > 300 (mesmo com locais <= 300)
    # Exemplo: P4 tem 200 clientes e P5 tem 150 clientes -> acumulado em P4 = 350 > 300
    pts_acum_excedente = [
        {"SEQ": 1, "POSTE": "P4", "CLIENTES": 200, "DEMANDA": "150,00", "ACUMULADA": "150,00"},
        {"SEQ": 2, "POSTE": "P5", "CLIENTES": 150, "DEMANDA": "120,00", "ACUMULADA": "120,00"},
    ]
    res_acum_alta = py_clan_recalcular_pontos(pts_acum_excedente, area_padrao=50, topologia=[["P4", "P5"]])
    assert res_acum_alta == pts_acum_excedente
    assert res_acum_alta[0]["DEMANDA"] == "150,00"
    assert res_acum_alta[0]["ACUMULADA"] == "150,00"
    assert res_acum_alta[1]["DEMANDA"] == "120,00"
    assert res_acum_alta[1]["ACUMULADA"] == "120,00"

    # 6. Falha por clientes negativos ou decimais
    pts_cli_neg = [dict(pontos_originais[0], CLIENTES=-5), pontos_originais[1]]
    assert py_clan_recalcular_pontos(pts_cli_neg, area_padrao=50, topologia=topologia) == pts_cli_neg

    pts_cli_float = [dict(pontos_originais[0], CLIENTES=12.5), pontos_originais[1]]
    assert py_clan_recalcular_pontos(pts_cli_float, area_padrao=50, topologia=topologia) == pts_cli_float


def test_clandestino_sincronizacao_tabela_nao_corrompe_ao_falhar():
    """RISCO 2: Valida que erro em textos do CAD impede mutação da tabela vinculada preservando células intactas."""
    p1 = {
        "SEQ": 1, "POSTE": "P4", "RAMAIS": "13x%%C1", "CLIENTES": 13,
        "DEMANDA": "22,52", "ACUMULADA": "90,65", "COORDENADAS": "C1",
        "TEXT_HANDLES": ["H4"], "RAW": ["13x1ø"]
    }
    dwg = {
        "TBL_VINCULADA": {"type": "ACAD_TABLE"},
        # Usuário edita o texto de ramal no CAD para um valor absurdo que excede 300 clientes:
        "H4": {"type": "TEXT", "text": "350x1ø"}
    }
    # Tabela com dados válidos originais
    tbl_mock = {
        "id": "TBL_VINCULADA",
        "rows": [
            [1, "P4", "13x%%C1", "-", 13, 13, 2, "22,52", "90,65", "C1"]
        ]
    }

    status, novos, afetados = py_sincronizar_levantamento(
        [p1], "TBL_VINCULADA", dwg, tbl_mock=tbl_mock, modo="CLANDESTINO", area=50
    )

    # A sincronização deve relatar falha normativa e NÃO alterar as células da tabela
    assert status == ":erro"
    assert "Falha no cálculo normativo LIGHT" in novos

    # Células da tabela mock permanecem 100% inalteradas (sem "-", sem zeros, sem corrupção)
    assert tbl_mock["rows"][0][7] == "22,52"
    assert tbl_mock["rows"][0][8] == "90,65"
    assert tbl_mock["rows"][0][2] == "13x%%C1"
    assert tbl_mock["rows"][0][4] == 13


def test_clandestino_lisp_ast_e_balanceamento():
    """Valida a sintaxe, balanceamento, teto de linhas e modularidade dos módulos CLANDESTINO."""
    assert CLAN_LISP_PATH.exists(), "clandestino_light.lsp não encontrado"
    assert TOPO_LISP_PATH.exists(), "clandestino_topologia.lsp não encontrado"
    source_clan = CLAN_LISP_PATH.read_text(encoding="utf-8")
    source_topo = TOPO_LISP_PATH.read_text(encoding="utf-8")

    # Limite estrito de modularidade: <= 500 linhas para cada módulo auxiliar
    lines_clan = source_clan.splitlines()
    assert len(lines_clan) <= 500, f"clandestino_light.lsp superou 500 linhas: {len(lines_clan)}"

    lines_topo = source_topo.splitlines()
    assert len(lines_topo) <= 500, f"clandestino_topologia.lsp superou 500 linhas: {len(lines_topo)}"

    # Parênteses 100% balanceados em ambos
    assert source_clan.count("(") == source_clan.count(")"), "Parênteses desbalanceados em clandestino_light.lsp"
    assert source_topo.count("(") == source_topo.count(")"), "Parênteses desbalanceados em clandestino_topologia.lsp"

    # Funções puras e tabelas em clandestino_light.lsp
    assert "(defun lp-clan-obter-dmdi" in source_clan
    assert "(defun lp-clan-obter-fator-div" in source_clan
    assert "(defun lp-clan-calcular-demanda" in source_clan
    assert "(defun lp-clan-calcular-acumulada" in source_clan
    assert "(defun lp-clan-atualizar-ponto-demandas" in source_clan
    assert "(defun lp-clan-format-num" in source_clan
    assert "(defun lp-clan-validar-area" in source_clan
    assert "(defun lp-clan-validar-clientes" in source_clan
    assert "(defun lp-clan-recalcular-pontos" in source_clan
    assert "(defun lp-clan-adicionar-aresta" in source_clan
    assert "(defun lp-clan-construir-mapa-filhos" in source_clan
    assert "(defun lp-clan-obter-jusante" in source_clan
    assert "*lp-clan-key-topologia*" in source_clan
    assert "*lp-clan-ultimo-erro*" in source_clan
    assert "(defun lp-clan-obter-ultimo-erro" in source_clan
    assert "*lp-clan-dmdi-20-400*" in source_clan
    assert "*lp-clan-fdiv-1-300*" in source_clan

    # Fluxo interativo e wizard CAD em clandestino_topologia.lsp
    assert "(defun lp-configurar-modo" in source_topo
    assert "(defun lp-clan-cadastrar-topologia" in source_topo
    assert "(defun lp-clan-parse-tr" in source_topo
    assert "(defun lp-clan-parse-no-poste" in source_topo
    assert "(defun lp-clan-selecionar-no-cad" in source_topo
    assert "(defun lp-clan-coletar-sequencia-postes" in source_topo
    assert "(defun lp-clan-executar-editor-topologia" in source_topo

    # Não deve existir detecção arbitrária de área por texto de poste
    assert "lp-clan-parse-area" not in source_clan
    assert "lp-clan-parse-area" not in source_topo
    lp_source = LISP_PATH.read_text(encoding="utf-8")
    assert "lp-clan-parse-area" not in lp_source

    # Carregamento no acaddoc.lsp
    acaddoc = (ROOT / "acaddoc.lsp").read_text(encoding="utf-8")
    assert 'load-aux-safe "orcamento\\\\clandestino_light.lsp"' in acaddoc
    assert 'load-aux-safe "orcamento\\\\clandestino_topologia.lsp"' in acaddoc

    # levantamento_postes.lsp estritamente <= 1000 linhas
    lp_lines = lp_source.splitlines()
    assert len(lp_lines) <= 1000, f"levantamento_postes.lsp excedeu 1000 linhas: {len(lp_lines)}"


# ==============================================================================
# Testes de Integração de Execução Real com o AutoLISP Harness
# ==============================================================================

from tests.autolisp_harness import AutoLisp, Ename, Pair


def _criar_harness_com_modulos(dwg=None, inputs=None):
    interp = AutoLisp(search_dirs=[ROOT, ROOT / "orcamento"], dwg=dwg, inputs=inputs)
    interp.load(CLAN_LISP_PATH)
    interp.load(TOPO_LISP_PATH)
    interp.load(LISP_PATH)
    return interp


def _dict_para_alist(d):
    return [Pair(k, v) for k, v in d.items()]


def _alist_para_dict(al):
    res = {}
    for item in al or []:
        if isinstance(item, Pair):
            res[item.car] = item.cdr
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            res[item[0]] = item[1]
    return res


def test_fluxo_interativo_topologia_tr_lados_derivacoes_e_concluir():
    """Valida o cadastro interativo real: TR -> LADO 1 -> LADO 2 -> DERIVACAO -> CONCLUIR.
    
    Topologia construída:
      TR-01 -> P4 -> P5 -> P6 -> P7   (LADO 1)
      TR-01 -> P8 -> P9               (LADO 2)
      P5 -> P10 -> P11                (DERIVAÇÃO a partir de P5)
    """
    dwg = {
        "H_TR": {"0": "TEXT", "1": "TR-01", "5": "H_TR"},
        "H_P4": {"0": "TEXT", "1": "P4", "5": "H_P4"},
        "H_P5": {"0": "TEXT", "1": "P5", "5": "H_P5"},
        "H_P6": {"0": "TEXT", "1": "P6", "5": "H_P6"},
        "H_P7": {"0": "TEXT", "1": "P7", "5": "H_P7"},
        "H_P8": {"0": "TEXT", "1": "P8", "5": "H_P8"},
        "H_P9": {"0": "TEXT", "1": "P9", "5": "H_P9"},
        "H_P10": {"0": "TEXT", "1": "P10", "5": "H_P10"},
        "H_P11": {"0": "TEXT", "1": "P11", "5": "H_P11"},
    }

    inputs = [
        # TR
        "H_TR",
        # LADO 1
        "H_P4",
        "H_P5",
        "H_P6",
        "H_P7",
        None,  # Enter fecha LADO 1
        # Menu opção -> Lado (LADO 2)
        "Lado",
        "H_P8",
        "H_P9",
        None,  # Enter fecha LADO 2
        # Menu opção -> Derivacao
        "Derivacao",
        "H_P5",  # Poste de partida da derivação
        "H_P10",
        "H_P11",
        None,  # Enter fecha derivação
        # Menu opção -> Concluir
        "Concluir",
    ]

    interp = _criar_harness_com_modulos(dwg=dwg, inputs=inputs)
    res = interp.call("lp-clan-cadastrar-topologia")
    assert res is not None, "Topologia retornou nil"

    # Confirma persistência da topologia no LData
    topo_ldata = interp.call("lp-db-obter-topologia")
    assert topo_ldata is not None, "Topologia não foi persistida no LData"

    # Constrói o mapa de adjacências de filhos e valida as conexões
    mapa = interp.call("lp-clan-construir-mapa-filhos", topo_ldata, None)
    assert mapa is not None

    # P7 é folha: nenhum poste a jusante
    jus_p7 = interp.call("lp-clan-obter-jusante", "P7", mapa)
    assert not jus_p7

    # P6 tem P7 a jusante
    jus_p6 = interp.call("lp-clan-obter-jusante", "P6", mapa)
    assert jus_p6 == ["P7"]

    # P10 tem P11 a jusante
    jus_p10 = interp.call("lp-clan-obter-jusante", "P10", mapa)
    assert jus_p10 == ["P11"]

    # P5 tem tronco P6, P7 e ramal derivado P10, P11
    jus_p5 = interp.call("lp-clan-obter-jusante", "P5", mapa)
    assert set(jus_p5) == {"P6", "P7", "P10", "P11"}

    # P4 tem toda a subárvore
    jus_p4 = interp.call("lp-clan-obter-jusante", "P4", mapa)
    assert set(jus_p4) == {"P5", "P6", "P7", "P10", "P11"}

    # LADO 2
    jus_p8 = interp.call("lp-clan-obter-jusante", "P8", mapa)
    assert jus_p8 == ["P9"]
    jus_p9 = interp.call("lp-clan-obter-jusante", "P9", mapa)
    assert not jus_p9


def test_calculo_acumulada_ordem_arbitraria_e_validacao_oficial_light():
    """Valida que a demanda acumulada segue estritamente a topologia da rede,
    independentemente da ordem de coleta ou cadastro dos postes.
    
    Valores reais obtidos por consulta estrita às tabelas da LIGHT (CQTS_ZNA853248_ATUAL.xlsx):
    - Área 50 m² -> DMDI = 1,88 kVA (DB!A65:B65)
    - Totais acumulados e fatores oficiais (DB!C36:E335):
      * P7 (4 cli): fdiv=3,88 -> 1,88 * 3,88 = 7,29 kVA
      * P11 (3 cli): fdiv=3,88 -> 1,88 * 3,88 = 7,29 kVA
      * P10 (2+3 = 5 cli): fdiv=4,84 -> 1,88 * 4,84 = 9,10 kVA
      * P6 (5+4 = 9 cli): fdiv=8,68 -> 1,88 * 8,68 = 16,32 kVA
      * P9 (8 cli): fdiv=7,72 -> 1,88 * 7,72 = 14,51 kVA
      * P8 (7+8 = 15 cli): fdiv=13,54 -> 1,88 * 13,54 = 25,46 kVA
      * P5 (6+9+5 = 20 cli): fdiv=17,44 -> 1,88 * 17,44 = 32,79 kVA
      * P4 (10+20 = 30 cli): fdiv=23,54 -> 1,88 * 23,54 = 44,26 kVA
    """
    arestas = [
        ["TR-01", "P4"],
        ["P4", "P5"],
        ["P5", "P6"],
        ["P6", "P7"],
        ["TR-01", "P8"],
        ["P8", "P9"],
        ["P5", "P10"],
        ["P10", "P11"],
    ]

    interp = _criar_harness_com_modulos()
    interp.ldata[("OXCAD_LEVANTAMENTO", "MODO")] = "CLANDESTINO"
    interp.ldata[("OXCAD_LEVANTAMENTO", "AREA_MEDIA")] = 50
    interp.ldata[("OXCAD_LEVANTAMENTO", "TOPOLOGIA")] = arestas

    # Ordem de coleta 1 (embaralhada / ponta antes da fonte):
    # P7, P11, P6, P10, P9, P8, P5, P4
    dados_ordem_1 = [
        {"SEQ": 1, "POSTE": "P7", "CLIENTES": 4},
        {"SEQ": 2, "POSTE": "P11", "CLIENTES": 3},
        {"SEQ": 3, "POSTE": "P6", "CLIENTES": 5},
        {"SEQ": 4, "POSTE": "P10", "CLIENTES": 2},
        {"SEQ": 5, "POSTE": "P9", "CLIENTES": 8},
        {"SEQ": 6, "POSTE": "P8", "CLIENTES": 7},
        {"SEQ": 7, "POSTE": "P5", "CLIENTES": 6},
        {"SEQ": 8, "POSTE": "P4", "CLIENTES": 10},
    ]
    pontos_ordem_1 = [_dict_para_alist(d) for d in dados_ordem_1]

    calc_1 = interp.call("lp-recalcular-demandas-acumuladas", pontos_ordem_1)
    res_1 = {_alist_para_dict(p)["POSTE"]: _alist_para_dict(p)["ACUMULADA"] for p in calc_1}

    assert res_1["P7"] == "7,29"
    assert res_1["P11"] == "7,29"
    assert res_1["P10"] == "9,10"
    assert res_1["P6"] == "16,32"
    assert res_1["P9"] == "14,51"
    assert res_1["P8"] == "25,46"
    assert res_1["P5"] == "32,79"
    assert res_1["P4"] == "44,26"

    # Ordem de coleta 2 (inversa / fonte antes da ponta):
    # P4, P8, P5, P9, P6, P10, P7, P11
    dados_ordem_2 = [
        {"SEQ": 1, "POSTE": "P4", "CLIENTES": 10},
        {"SEQ": 2, "POSTE": "P8", "CLIENTES": 7},
        {"SEQ": 3, "POSTE": "P5", "CLIENTES": 6},
        {"SEQ": 4, "POSTE": "P9", "CLIENTES": 8},
        {"SEQ": 5, "POSTE": "P6", "CLIENTES": 5},
        {"SEQ": 6, "POSTE": "P10", "CLIENTES": 2},
        {"SEQ": 7, "POSTE": "P7", "CLIENTES": 4},
        {"SEQ": 8, "POSTE": "P11", "CLIENTES": 3},
    ]
    pontos_ordem_2 = [_dict_para_alist(d) for d in dados_ordem_2]

    calc_2 = interp.call("lp-recalcular-demandas-acumuladas", pontos_ordem_2)
    res_2 = {_alist_para_dict(p)["POSTE"]: _alist_para_dict(p)["ACUMULADA"] for p in calc_2}

    # As demandas acumuladas são idênticas em ambas as ordens de cadastro
    assert res_2 == res_1


def test_cancelamento_seguro_da_topologia_preserva_dwg():
    """Valida que o cancelamento no cadastro não sobrescreve topologia existente nem corrompe o DWG."""
    arestas_anteriores = [["TR-01", "P1"], ["P1", "P2"]]

    interp = _criar_harness_com_modulos()
    interp.ldata[("OXCAD_LEVANTAMENTO", "TOPOLOGIA")] = arestas_anteriores

    # 1. Usuário seleciona 'Cancelar' no menu de topologia existente:
    interp.inputs = ["Cancelar"]
    res_cancel = interp.call("lp-clan-cadastrar-topologia")
    assert res_cancel == arestas_anteriores
    assert interp.call("lp-db-obter-topologia") == arestas_anteriores

    # 2. Usuário inicia cadastro novo sem topologia prévia e cancela na seleção do TR (Enter):
    interp_novo = _criar_harness_com_modulos()
    interp_novo.inputs = [None]
    res_novo_cancel = interp_novo.call("lp-clan-cadastrar-topologia")
    assert res_novo_cancel is None
    assert interp_novo.call("lp-db-obter-topologia") is None


def test_resiliencia_area_ldata_e_status_modo_str():
    """Valida que valores inválidos ou 'T' no LData de área não quebram lp-db-obter-area nem lp-clan-status-modo-str."""
    interp = _criar_harness_com_modulos()

    # Caso 1: LData corrompido com 'T' (True retornado por (or ...))
    interp.ldata[("OXCAD_LEVANTAMENTO", "MODO")] = "CLANDESTINO"
    interp.ldata[("OXCAD_LEVANTAMENTO", "AREA_CLANDESTINO")] = True
    area_obtida = interp.call("lp-db-obter-area")
    assert area_obtida == 50
    assert isinstance(area_obtida, int)

    status = interp.call("lp-clan-status-modo-str")
    assert "CLANDESTINO | Área: 50 m²" in status

    # Caso 2: LData vazio (None)
    interp.ldata[("OXCAD_LEVANTAMENTO", "AREA_CLANDESTINO")] = None
    area_nil = interp.call("lp-db-obter-area")
    assert area_nil == 50
    assert isinstance(area_nil, int)
    status_nil = interp.call("lp-clan-status-modo-str")
    assert "CLANDESTINO | Área: 50 m²" in status_nil

    # Caso 3: LData com valor válido (ex: 80 m²)
    interp.ldata[("OXCAD_LEVANTAMENTO", "AREA_CLANDESTINO")] = 80
    area_80 = interp.call("lp-db-obter-area")
    assert area_80 == 80
    status_80 = interp.call("lp-clan-status-modo-str")
    assert "CLANDESTINO | Área: 80 m²" in status_80



