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
