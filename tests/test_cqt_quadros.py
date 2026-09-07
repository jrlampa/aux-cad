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
    assert anc["residencial"]["qtde"] == "50"
    assert anc["residencial"]["dmdi"] == "1,30"
    assert anc["residencial"]["total"] == "65,00"
    assert anc["req_resid"]["qtde"] == "01"
    assert anc["total_clientes"] == "50"
    assert anc["max_prev"] == "66,25kVA"
    assert anc["carregamento"] == "44,17%"

    at = resumo["ATUAL"]
    assert at["residencial"]["qtde"] == "49"
    assert at["residencial"]["total"] == "63,70"
    assert at["total_clientes"] == "49"
    assert at["carregamento"] == "43,30%"

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
