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
