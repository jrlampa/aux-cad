# -*- coding: utf-8 -*-
"""
test_cqt_gui.py - Testes unitários para as interfaces gráficas do CQT (ScenarioTab e CQTManagerGUI).
"""

import os
import sys
import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_curr_dir)
for _p in [_root_dir, os.path.join(_root_dir, "cqt")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from cqt_scenario_tab import ScenarioTab
from cqt_excel_manager import CQTManagerGUI
from cqt_excel_io import DEFAULT_CABLES_BASE


@pytest.fixture
def fake_root():
    """Cria uma janela Tk oculta para testes sem interface gráfica ativa."""
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        try:
            root.destroy()
        except Exception:
            pass
    except Exception:
        pytest.skip("Ambiente sem suporte a Tkinter display")


def test_scenario_tab_add_and_remove(fake_root):
    """Testa inserção, remoção e contagem de trechos na aba ScenarioTab."""
    tab = ScenarioTab(
        parent=fake_root,
        cenario="PROJETADO",
        cables_list=DEFAULT_CABLES_BASE[:10],
        get_template_path_fn=lambda: "template.xlsm"
    )

    assert len(tab.trechos_rows) == 0
    tab.add_trecho_row()
    assert len(tab.trechos_rows) == 1
    assert tab.trechos_rows[0]["letra"] == "A"
    assert tab.trechos_rows[0]["cb_montante"].get() == "TRAFO"

    tab.add_trecho_row()
    assert len(tab.trechos_rows) == 2
    assert tab.trechos_rows[1]["letra"] == "B"
    assert tab.trechos_rows[1]["cb_montante"].get() == "A"

    dados = tab.get_trechos_data()
    assert len(dados) == 2
    assert dados[0]["letra"] == "A"
    assert dados[1]["letra"] == "B"

    tab.remove_last_trecho()
    assert len(tab.trechos_rows) == 1
    assert tab.trechos_rows[0]["letra"] == "A"

    tab.clear_all_trechos()
    assert len(tab.trechos_rows) == 0


def test_scenario_tab_set_data_and_unknown_cable(fake_root):
    """Testa preenchimento em lote e incorporação dinâmica de condutor novo."""
    initial_cables = ["3x150+70 - Al - F.P 1", "3x70+70 (nú) - Al - F.P 1"]
    tab = ScenarioTab(
        parent=fake_root,
        cenario="ATUAL",
        cables_list=initial_cables,
        get_template_path_fn=lambda: "template.xlsm"
    )

    novos_trechos = [
        {
            "letra": "A",
            "montante": "TRAFO",
            "vaos": 2,
            "comprimento_m": 85.0,
            "condutor": "CONDUTOR_ESPECIAL_TESTE",
            "mono": 0,
            "bi": 15,
            "tri": 1,
            "esp_carga": 0,
            "ip70": 0,
            "ip125": 4,
            "ip250": 0,
        }
    ]

    tab.set_trechos_data(novos_trechos)
    assert len(tab.trechos_rows) == 1
    assert tab.trechos_rows[0]["cb_cabo"].get() == "CONDUTOR_ESPECIAL_TESTE"
    assert "CONDUTOR_ESPECIAL_TESTE" in tab.cables_list


def test_scenario_tab_update_cables_list(fake_root):
    """Testa a propagação de nova lista de condutores para as comboboxes."""
    tab = ScenarioTab(
        parent=fake_root,
        cenario="PROJETADO",
        cables_list=["Cabo1", "Cabo2"],
        get_template_path_fn=lambda: "template.xlsm"
    )
    tab.add_trecho_row()
    cb = tab.trechos_rows[0]["cb_cabo"]
    assert "Cabo1" in cb["values"]

    nova_lista = ["CaboA", "CaboB", "CaboC"]
    tab.update_cables_list(nova_lista)
    assert tab.cables_list == nova_lista
    assert "CaboA" in cb["values"]


def test_scenario_tab_live_preview_conformidade(fake_root):
    """Testa o cálculo do Live Preview e indicação de atendimento normativo."""
    mock_app = MagicMock()
    mock_app.txt_potencia.get.return_value = "45"

    tab = ScenarioTab(
        parent=fake_root,
        cenario="PROJETADO",
        cables_list=DEFAULT_CABLES_BASE,
        get_template_path_fn=lambda: "template.xlsm",
        parent_app=mock_app
    )

    # 1. Cenário normal com queda baixa
    tab.add_trecho_row({
        "letra": "A",
        "montante": "TRAFO",
        "vaos": 1,
        "comprimento_m": 40.0,
        "condutor": "3x150+70 - Al - F.P 1",
        "mono": 0,
        "bi": 10,
        "tri": 0,
        "esp_carga": 0,
        "ip70": 0,
        "ip125": 2,
        "ip250": 0,
    })

    tab.recalcular_live()
    assert "ATENDE" in tab.lbl_norma_badge.cget("text")

    # 2. Cenário crítico que extrapola o limite de 6%
    tab.clear_all_trechos()
    tab.add_trecho_row({
        "letra": "A",
        "montante": "TRAFO",
        "vaos": 10,
        "comprimento_m": 600.0,
        "condutor": "3x35+1x54,6 - Al - F.P 1",
        "mono": 0,
        "bi": 40,
        "tri": 0,
        "esp_carga": 0,
        "ip70": 0,
        "ip125": 10,
        "ip250": 0,
    })

    tab.recalcular_live()
    badge_txt = tab.lbl_norma_badge.cget("text")
    assert "QT EXCESSIVA" in badge_txt or "> 6.00%" in badge_txt or "VIOLAÇÃO" in badge_txt


def test_scenario_tab_copy_from(fake_root):
    """Testa a função de cópia de trechos entre cenários."""
    dados_fonte = [
        {"letra": "A", "montante": "TRAFO", "comprimento_m": 50.0, "condutor": "3x150+70 - Al - F.P 1"}
    ]

    def mock_get_source(cenario):
        if cenario == "ATUAL":
            return dados_fonte
        return []

    tab = ScenarioTab(
        parent=fake_root,
        cenario="ATUAL+NC",
        cables_list=DEFAULT_CABLES_BASE,
        get_template_path_fn=lambda: "template.xlsm",
        get_source_scenario_data_fn=mock_get_source
    )

    with patch("tkinter.messagebox.askyesno", return_value=True):
        tab._on_copy_from("ATUAL")

    assert len(tab.trechos_rows) == 1
    assert tab.trechos_rows[0]["letra"] == "A"


def test_cqt_manager_gui_init_and_get_all_scenarios(fake_root, monkeypatch):
    """Testa inicialização do orquestrador CQTManagerGUI."""
    # Garante que Tk() retorne fake_root
    monkeypatch.setattr(tk, "Tk", lambda: fake_root)

    app = CQTManagerGUI()
    assert "PROJETADO" in app.tabs
    assert "ATUAL+NC" in app.tabs
    assert "ATUAL" in app.tabs

    app.ent_proj.delete(0, tk.END)
    app.ent_proj.insert(0, "A057999888")
    app.ent_ponto.delete(0, tk.END)
    app.ent_ponto.insert(0, "T12345")

    app.tabs["PROJETADO"].add_trecho_row({
        "letra": "A", "montante": "TRAFO", "comprimento_m": 45.0, "condutor": "3x150+70 - Al - F.P 1"
    })

    with patch("cqt_excel_manager.update_cqt_excel", return_value=["PROJETADO"]) as mock_update, \
         patch("tkinter.messagebox.showinfo") as mock_info, \
         patch("os.startfile", create=True) as mock_startfile, \
         patch.object(app.root, "destroy") as mock_destroy:
        app._on_gravar()
        mock_update.assert_called_once()
        args, kwargs = mock_update.call_args
        payload = args[2]
        assert payload["projeto"] == "A057999888"
        assert payload["ponto_trafo"] == "T12345"
        assert "PROJETADO" in payload["scenarios"]
        assert len(payload["scenarios"]["PROJETADO"]) == 1



