# -*- coding: utf-8 -*-
"""
test_sob_launcher_gui.py - Testes unitários para o lançador interativo sob_launcher_gui.py.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import tkinter as tk

from sob.sob_launcher_gui import SobLauncherDialog, lancar_dialogo_sob


@pytest.fixture
def fake_root():
    """Cria uma janela Tk oculta para testes sem bloquear."""
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


def test_dialog_inicializacao(fake_root):
    """Testa inicialização com valores padrão corretos."""
    dialog = SobLauncherDialog(fake_root)
    assert dialog.base_var.get() == "PE"
    assert dialog.sp_var.get() is True
    assert dialog.cad_var.get() is True
    assert "PREPARAÇÃO DE PROJETO SOB" in dialog.root.title().upper()
    dialog.root.destroy()


def test_dialog_validacao_sob_invalida(fake_root):
    """Testa que erro é exibido se a SOB for inválida."""
    dialog = SobLauncherDialog(fake_root)
    dialog.sob_var.set("SOB_INVALIDA!@#$")

    with patch("tkinter.messagebox.showerror") as mock_err:
        dialog._iniciar_execucao()
        mock_err.assert_called_once()
        assert "SOB Inválida" in mock_err.call_args[0][0]
    dialog.root.destroy()


def test_dialog_validacao_destino_invalido(fake_root):
    """Testa que erro é exibido se o diretório de destino não existir."""
    dialog = SobLauncherDialog(fake_root)
    dialog.sob_var.set("A057349839")
    dialog.destino_var.set("C:/Caminho/Que/Nao/Existe/Jamais/12345")

    with patch("tkinter.messagebox.showerror") as mock_err:
        dialog._iniciar_execucao()
        mock_err.assert_called_once()
        assert "Destino Inválido" in mock_err.call_args[0][0]
    dialog.root.destroy()


def test_dialog_procurar_pasta(fake_root, tmp_path: Path):
    """Testa seleção de pasta via filedialog."""
    dialog = SobLauncherDialog(fake_root)
    with patch("tkinter.filedialog.askdirectory", return_value=str(tmp_path)):
        dialog._procurar_pasta()
        assert dialog.destino_var.get() == str(tmp_path)
    dialog.root.destroy()


def test_dialog_iniciar_execucao_sucesso(fake_root, tmp_path: Path):
    """Testa acionamento do orquestrador e GUI de progresso com dados válidos."""
    dialog = SobLauncherDialog(fake_root)
    dialog.sob_var.set("A057349839")
    dialog.destino_var.set(str(tmp_path))
    dialog.cb_base.set("CF - Cabo Frio")

    with patch("sob.sob_launcher_gui.SobOrchestrator") as mock_orch_cls, \
         patch("sob.sob_launcher_gui.SobProgressGUI") as mock_gui_cls:

        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        mock_gui = MagicMock()
        mock_gui_cls.return_value = mock_gui

        dialog._iniciar_execucao()

        mock_gui_cls.assert_called_once()
        args, kwargs = mock_gui_cls.call_args
        assert kwargs["sob_id"] == "A057349839"
        assert kwargs["base_inicial"] == "CF"
        mock_gui.iniciar.assert_called_once()


def test_lancar_dialogo_sob_com_parent(fake_root):
    """Testa função wrapper lancar_dialogo_sob com parent."""
    with patch("sob.sob_launcher_gui.SobLauncherDialog") as mock_dialog:
        lancar_dialogo_sob(fake_root)
        mock_dialog.assert_called_once_with(fake_root)
