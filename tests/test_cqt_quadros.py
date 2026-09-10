import os
import pytest
from cqt_quadros_generator import format_num, extract_quadros_data, generate_cad_lisp, save_quadros_json

REAL_EXCEL = r"G:\Meu Drive\1-HBT\HBT\SETEMBRO\05\A057146257\AN_A057146257_CQT.xlsm"

def test_format_num():
    assert format_num(None) == "-"
    assert format_num(0) == "-"
    assert format_num("-") == "-"
    assert format_num(1.3, 2) == "1,30"
    assert format_num(65, 2) == "65,00"
    assert format_num(0.4416666, is_pct=True) == "44,17%"
    assert format_num(0.433, is_pct=True) == "43,30%"

def test_extract_quadros_data_real():
    if not os.path.exists(REAL_EXCEL):
        pytest.skip("Planilha real de teste não encontrada no caminho especificado.")

    data = extract_quadros_data(REAL_EXCEL, custom_ponto_trafo="77245")
    assert "resumo_trafo" in data
    resumo = data["resumo_trafo"]

    assert "ATUAL+NC" in resumo
    assert "ATUAL" in resumo

    anc = resumo["ATUAL+NC"]
    assert anc["ponto_trafo"] == "77245"
    assert anc["residencial"]["qtde"] == "57"
    assert anc["residencial"]["dmdi"] == "1,30"
    assert anc["residencial"]["total"] == "74,10"
    assert anc["req_n_resid"]["qtde"] == "1"
    assert anc["req_n_resid"]["total"] == "49,00"
    assert anc["ilum_publica"]["qtde"] == "10"
    assert anc["ilum_publica"]["total"] == "1,25"
    assert anc["total_clientes"] == "58"
    assert anc["max_prev"] == "124,35kVA"
    assert anc["carregamento"] == "82,90%"

    at = resumo["ATUAL"]
    assert at["residencial"]["qtde"] == "57"
    assert at["residencial"]["dmdi"] == "1,30"
    assert at["residencial"]["total"] == "74,10"
    assert at["n_residencial"]["qtde"] == "1"
    assert at["n_residencial"]["total"] == "1,30"
    assert at["ilum_publica"]["qtde"] == "10"
    assert at["ilum_publica"]["total"] == "1,25"
    assert at["total_clientes"] == "58"
    assert at["max_prev"] == "76,65kVA"
    assert at["carregamento"] == "51,10%"

    # Valida Queda de Tensão Acumulada por Trecho extraída diretamente do Excel
    trechos = data["trechos_cqt"]
    assert len(trechos) == 3
    assert trechos[0]["trecho"] == "A"
    assert trechos[0]["qt_atual"] == "3,85%"
    assert trechos[0]["qt_atual_nc"] == "3,99%"
    assert trechos[1]["trecho"] == "B"
    assert trechos[1]["qt_atual"] == "3,85%"
    assert trechos[1]["qt_atual_nc"] == "4,02%"
    assert trechos[2]["trecho"] == "C"
    assert trechos[2]["qt_atual"] == "4,64%"
    assert trechos[2]["qt_atual_nc"] == "4,77%"

def test_generate_cad_lisp_and_json(tmp_path):
    if not os.path.exists(REAL_EXCEL):
        pytest.skip("Planilha real não encontrada.")

    json_path = str(tmp_path / "quadros.json")
    save_quadros_json(REAL_EXCEL, json_out_path=json_path, custom_ponto_trafo="77245")
    assert os.path.exists(json_path)

    # Teste de leitura do LSP gerado
    with open(r"C:\Temp\cqt_draw_quadros.lsp", "r", encoding="windows-1252") as f:
        content = f.read()

    assert "c:CQTQUADROS" in content
    assert "77245 - ATUAL+NC" in content
    assert "77245 - ATUAL" in content
    assert "ILUM. PÚBLICA" in content
    assert "MÁX. PREV." in content
    assert "CARREGAMENTO" in content


def test_extract_quadros_excel_existente_xlsx(tmp_path):
    """Testa geração de quadros a partir de um arquivo .xlsx existente criado dinamicamente."""
    import openpyxl

    wb = openpyxl.Workbook()
    # Cria abas necessárias
    ws_capa = wb.active
    ws_capa.title = "CAPA-RESUMO"
    ws_capa["A14"] = "TRAFO EXIST.:"
    ws_capa["B14"] = "176262-3-150kVA"

    ws_at = wb.create_sheet("ATUAL")
    ws_at["C4"] = 49
    ws_at["C5"] = 1.30
    ws_at["C6"] = 63.70
    ws_at["C12"] = 49
    ws_at["C13"] = 64.95
    ws_at["C14"] = 0.433

    ws_anc = wb.create_sheet("ATUAL+NC")
    ws_anc["C4"] = 50
    ws_anc["C5"] = 1.30
    ws_anc["C6"] = 65.00
    ws_anc["C12"] = 50
    ws_anc["C13"] = 66.25
    ws_anc["C14"] = 0.4417

    ws_cqt_at = wb.create_sheet("CQT ATUAL")
    ws_cqt_at["F4"] = "77245"
    ws_cqt_at["C11"] = "A"
    ws_cqt_at["Q11"] = 1.50

    ws_cqt_anc = wb.create_sheet("CQT ATUAL+NC")
    ws_cqt_anc["F4"] = "77245"
    ws_cqt_anc["C11"] = "A"
    ws_cqt_anc["Q11"] = 2.10

    excel_file = tmp_path / "CQT_PROJETO_TESTE.xlsx"
    wb.save(str(excel_file))
    wb.close()

    # 1. Extração com ponto trafo "auto"
    data = extract_quadros_data(str(excel_file), custom_ponto_trafo="auto")
    assert "resumo_trafo" in data
    assert "ATUAL" in data["resumo_trafo"]
    assert "ATUAL+NC" in data["resumo_trafo"]
    assert data["resumo_trafo"]["ATUAL"]["ponto_trafo"] == "77245"

    # 2. Geração de JSON e LISP
    json_out = str(tmp_path / "saida_quadros.json")
    save_quadros_json(str(excel_file), json_out_path=json_out, custom_ponto_trafo=None)
    assert os.path.exists(json_out)

    # 3. Teste da CLI
    import sys
    import subprocess
    py_exec = sys.executable
    cmd = [py_exec, "cqt/cqt_quadros_generator.py", str(excel_file), "auto"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "[SUCESSO]" in res.stdout or "exportados" in res.stdout

