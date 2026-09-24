# -*- coding: utf-8 -*-
"""
Suíte de Testes Unitários da Integração Visual do Workspace (GUI -> Dispatcher).
Testa os fluxos de seleção de artefatos na Treeview, disparo de ações (Abrir, Localizar),
lançamento de módulos especialistas (CQT, Orçamento, CPFC) e tratamento de erros e ausências.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from workspace.workspace_core import ArtifactStatus, ProjectArtifact, ProjectWorkspace
from workspace.workspace_cli import WorkspaceGUI


@pytest.fixture(scope="module")
def mock_gui_app(tmp_path_factory):
    """
    Cria uma instância real de WorkspaceGUI inicializada com contexto de teste,
    compartilhada no escopo do módulo para estabilidade do interpretador Tcl/Tkinter.
    """
    import tkinter as tk
    try:
        tmp_dir = tmp_path_factory.mktemp("workspace_gui")
    except Exception:
        pytest.skip("Ambiente de teste de disco indisponível")

    sob_id = "A057349839"
    root = tmp_dir / f"SOB_{sob_id}"
    root.mkdir()

    dwg = root / f"PE_{sob_id}_DESENHO.dwg"
    dwg.write_bytes(b"DWG_TESTE")

    cqt = root / f"CQT_{sob_id}.xlsm"
    cqt.write_bytes(b"CQT_TESTE")

    orc = root / f"ORCAMENTO_{sob_id}.xlsx"
    orc.write_bytes(b"ORCAMENTO_TESTE")

    cpfc = root / f"PE_{sob_id}_CPFC_REN1.059.xlsx"
    cpfc.write_bytes(b"CPFC_TESTE")

    try:
        app = WorkspaceGUI(root_dir=str(root), sob_id=sob_id)
        app.withdraw()
    except Exception as e:
        pytest.skip(f"Ambiente gráfico Tkinter não inicializável: {e}")

    yield app

    try:
        app.destroy()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_tree_selection(mock_gui_app):
    """Garante estado limpo de seleção antes de cada teste."""
    sel = mock_gui_app.tree.selection()
    if sel:
        mock_gui_app.tree.selection_remove(sel)
    yield


class TestWorkspaceGUIArtifactSelection:
    """Testes de seleção de artefatos na Treeview."""

    def test_selecao_de_artefato_valido(self, mock_gui_app):
        # Seleciona a linha DWG
        mock_gui_app.tree.selection_set("DWG")
        art = mock_gui_app._get_selected_artifact()
        assert art is not None
        assert art.chave == "DWG"
        assert art.status == ArtifactStatus.EXISTE
        assert art.caminho.name.endswith(".dwg")

    def test_nenhum_artefato_selecionado_retorna_none(self, mock_gui_app):
        mock_gui_app.tree.selection_remove(mock_gui_app.tree.selection())
        art = mock_gui_app._get_selected_artifact()
        assert art is None


class TestWorkspaceGUIAbrirAcoes:
    """Testes da ação ABRIR na GUI."""

    def test_abrir_sem_selecao_exibe_aviso(self, mock_gui_app):
        mock_gui_app.tree.selection_remove(mock_gui_app.tree.selection())
        with patch("tkinter.messagebox.showinfo") as mock_info, patch("workspace.workspace_actions.WorkspaceActionDispatcher.abrir_artefato") as mock_abrir:
            mock_gui_app._on_abrir_artefato()
            mock_info.assert_called_once()
            assert "Nenhum artefato selecionado" in mock_info.call_args[0][1]
            mock_abrir.assert_not_called()

    def test_abrir_artefato_inexistente_exibe_alerta(self, mock_gui_app):
        # Seleciona MEMORIAL_AMBIENTAL que não foi gerado na fixture
        mock_gui_app.tree.selection_set("MEMORIAL_AMBIENTAL")
        with patch("tkinter.messagebox.showwarning") as mock_warn, patch("workspace.workspace_actions.WorkspaceActionDispatcher.abrir_artefato") as mock_abrir:
            mock_gui_app._on_abrir_artefato()
            mock_warn.assert_called_once()
            assert "ainda não foi gerado" in mock_warn.call_args[0][1]
            mock_abrir.assert_not_called()

    def test_abrir_artefato_existente_chama_dispatcher(self, mock_gui_app):
        mock_gui_app.tree.selection_set("DWG")
        with patch("workspace.workspace_actions.WorkspaceActionDispatcher.abrir_artefato", return_value=True) as mock_abrir:
            mock_gui_app._on_abrir_artefato()
            mock_abrir.assert_called_once()
            art_passado = mock_abrir.call_args[0][0]
            assert art_passado.chave == "DWG"

    def test_abrir_artefato_erro_dispatcher_exibe_erro(self, mock_gui_app):
        mock_gui_app.tree.selection_set("DWG")
        with patch("workspace.workspace_actions.WorkspaceActionDispatcher.abrir_artefato", return_value=False) as mock_abrir, patch("tkinter.messagebox.showerror") as mock_err:
            mock_gui_app._on_abrir_artefato()
            mock_abrir.assert_called_once()
            mock_err.assert_called_once()
            assert "Não foi possível abrir" in mock_err.call_args[0][1]


class TestWorkspaceGUILocalizarAcoes:
    """Testes da ação LOCALIZAR no Explorer na GUI."""

    def test_localizar_sem_selecao_exibe_aviso(self, mock_gui_app):
        mock_gui_app.tree.selection_remove(mock_gui_app.tree.selection())
        with patch("tkinter.messagebox.showinfo") as mock_info, patch("workspace.workspace_actions.WorkspaceActionDispatcher.localizar_artefato") as mock_loc:
            mock_gui_app._on_localizar_artefato()
            mock_info.assert_called_once()
            mock_loc.assert_not_called()

    def test_localizar_artefato_inexistente_exibe_alerta(self, mock_gui_app):
        mock_gui_app.tree.selection_set("MEMORIAL_AMBIENTAL")
        with patch("tkinter.messagebox.showwarning") as mock_warn, patch("workspace.workspace_actions.WorkspaceActionDispatcher.localizar_artefato") as mock_loc:
            mock_gui_app._on_localizar_artefato()
            mock_warn.assert_called_once()
            mock_loc.assert_not_called()

    def test_localizar_artefato_existente_chama_dispatcher(self, mock_gui_app):
        mock_gui_app.tree.selection_set("ORCAMENTO")
        with patch("workspace.workspace_actions.WorkspaceActionDispatcher.localizar_artefato", return_value=True) as mock_loc:
            mock_gui_app._on_localizar_artefato()
            mock_loc.assert_called_once()
            art_passado = mock_loc.call_args[0][0]
            assert art_passado.chave == "ORCAMENTO"

    def test_localizar_artefato_erro_dispatcher_exibe_erro(self, mock_gui_app):
        mock_gui_app.tree.selection_set("ORCAMENTO")
        with patch("workspace.workspace_actions.WorkspaceActionDispatcher.localizar_artefato", return_value=False) as mock_loc, patch("tkinter.messagebox.showerror") as mock_err:
            mock_gui_app._on_localizar_artefato()
            mock_loc.assert_called_once()
            mock_err.assert_called_once()
            assert "Não foi possível localizar" in mock_err.call_args[0][1]


class TestWorkspaceGUIExecutarModulos:
    """Testes de acionamento dos módulos especialistas (CQT, Orçamento, CPFC)."""

    def test_executar_cqt_chama_dispatcher(self, mock_gui_app):
        mock_proc = MagicMock()
        with patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_cqt", return_value=mock_proc) as mock_exec, patch("tkinter.messagebox.showinfo") as mock_info:
            mock_gui_app._on_executar_cqt()
            mock_exec.assert_called_once_with(mock_gui_app.workspace)
            mock_info.assert_called_once()
            assert "CQT" in mock_info.call_args[0][0]

    def test_executar_cqt_trata_excecao(self, mock_gui_app):
        with patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_cqt", side_effect=RuntimeError("Falha subprocesso")), patch("tkinter.messagebox.showerror") as mock_err:
            mock_gui_app._on_executar_cqt()
            mock_err.assert_called_once()
            assert "Falha subprocesso" in mock_err.call_args[0][1]

    def test_executar_orcamento_chama_dispatcher(self, mock_gui_app):
        mock_proc = MagicMock()
        with patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_orcamento", return_value=mock_proc) as mock_exec, patch("tkinter.messagebox.showinfo") as mock_info:
            mock_gui_app._on_executar_orcamento()
            mock_exec.assert_called_once_with(mock_gui_app.workspace)
            mock_info.assert_called_once()
            assert "Orçamento" in mock_info.call_args[0][0]

    def test_executar_orcamento_trata_excecao(self, mock_gui_app):
        with patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_orcamento", side_effect=RuntimeError("Falha Orcamento")), patch("tkinter.messagebox.showerror") as mock_err:
            mock_gui_app._on_executar_orcamento()
            mock_err.assert_called_once()
            assert "Falha Orcamento" in mock_err.call_args[0][1]

    def test_executar_cpfc_chama_dispatcher(self, mock_gui_app):
        mock_proc = MagicMock()
        with patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_cpfc", return_value=mock_proc) as mock_exec, patch("tkinter.messagebox.showinfo") as mock_info:
            mock_gui_app._on_executar_cpfc()
            mock_exec.assert_called_once_with(mock_gui_app.workspace)
            mock_info.assert_called_once()
            assert "CPFC" in mock_info.call_args[0][0]

    def test_executar_cpfc_trata_excecao(self, mock_gui_app):
        with patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_cpfc", side_effect=RuntimeError("Falha CPFC")), patch("tkinter.messagebox.showerror") as mock_err:
            mock_gui_app._on_executar_cpfc()
            mock_err.assert_called_once()
            assert "Falha CPFC" in mock_err.call_args[0][1]

    def test_abrir_pasta_atual_chama_dispatcher(self, mock_gui_app):
        with patch("workspace.workspace_actions.WorkspaceActionDispatcher.localizar_artefato", return_value=True) as mock_loc:
            mock_gui_app._abrir_pasta_atual()
            mock_loc.assert_called_once_with(mock_gui_app.workspace.root_dir)
