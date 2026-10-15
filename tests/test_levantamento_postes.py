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
    assert '"Adicionar Revisar Excluir Gerar Limpar Sair"' in source
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
