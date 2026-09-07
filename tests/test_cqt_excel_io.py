import os
import pytest
from cqt_excel_io import (
    load_cables_from_database,
    load_scenario_from_excel,
    update_cqt_excel,
    DEFAULT_TEMPLATE_PATH,
)


def test_load_cables_fallback():
    cables = load_cables_from_database("caminho_inexistente_123.xlsm")
    assert isinstance(cables, list)
    assert len(cables) > 0
    assert "3x150+70 - Al - F.P 1" in cables
    assert "3x35+1x54,6 - Al - F.P 1" in cables


def test_load_scenario_nonexistent():
    data = load_scenario_from_excel("inexistente.xlsm", "ATUAL")
    assert data == {}


def test_update_cqt_excel_not_found():
    with pytest.raises(FileNotFoundError):
        update_cqt_excel("modelo_inexistente.xlsm", "dest.xlsm", {})


def test_cqt_cad_input_json_interchange(tmp_path):
    """Testa a geração e parsing do JSON de intercâmbio do comando CQTCAD."""
    import json

    json_file = tmp_path / "cqt_cad_input.json"
    dados_cad = {
        "projeto": "A057100646",
        "ponto_trafo": "A55323",
        "potencia_trafo": "45",
        "cenario": "PROJETADO",
        "salvar_em": "C:/Projetos/CQT_A057100646.xlsm",
        "trechos": [
            {"letra": "A", "montante": "TRAFO", "vaos": 2, "comprimento_m": 75.50},
            {"letra": "B", "montante": "A", "vaos": 1, "comprimento_m": 38.20}
        ]
    }
    json_file.write_text(json.dumps(dados_cad, ensure_ascii=False, indent=2), encoding="utf-8")

    assert os.path.exists(json_file)
    with open(json_file, "r", encoding="utf-8") as f:
        carregado = json.load(f)

    assert carregado["projeto"] == "A057100646"
    assert carregado["ponto_trafo"] == "A55323"
    assert carregado["cenario"] == "PROJETADO"
    assert len(carregado["trechos"]) == 2
    assert carregado["trechos"][0]["letra"] == "A"
    assert carregado["trechos"][0]["comprimento_m"] == 75.50

