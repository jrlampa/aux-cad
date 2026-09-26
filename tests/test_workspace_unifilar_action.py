# -*- coding: utf-8 -*-
"""
test_workspace_unifilar_action.py - Testes unitários para a integração CAD do Unifilar no Workspace.
Valida:
1. Identificação do DWG correto
2. Reutilização do mecanismo existente de abertura (WorkspaceActionDispatcher.abrir_artefato)
3. Exibição de mensagem orientativa de comandos AutoCAD (UNIFILAR / PROTECAO)
4. Tratamento controlado de DWG inexistente
5. Comportamento não-bloqueante
6. Presença do botão na GUI e integração com a Treeview
7. Isolamento — nenhum acesso a SGT e SQLite
8. Nenhum lançamento de unifilar_manager.py
"""

from pathlib import Path
import sqlite3
import subprocess
import unittest
from unittest.mock import MagicMock, patch
import urllib.request

from workspace.workspace_core import ArtifactStatus, ProjectArtifact, ProjectWorkspace
from workspace.workspace_actions import WorkspaceActionDispatcher
from workspace.workspace_cli import WorkspaceGUI


class TestWorkspaceUnifilarAction(unittest.TestCase):
    """Bateria de testes para a ação contextual do Unifilar no Workspace."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.temp_sob_dir = self.repo_root / "temp_fake_sob_unifilar"
        self.temp_sob_dir.mkdir(parents=True, exist_ok=True)

        self.fake_dwg = self.temp_sob_dir / "PE_A057349839_DESENHO.dwg"
        self.fake_dwg.write_bytes(b"FAKE_DWG_CONTENT")

        self.workspace = ProjectWorkspace(
            sob_id="A057349839",
            sob_name="SOB_A057349839",
            root_dir=self.temp_sob_dir,
            base_sigla="PE",
            dwg_principal=self.fake_dwg,
        )

    def tearDown(self):
        if self.fake_dwg.exists():
            try:
                self.fake_dwg.unlink()
            except Exception:
                pass
        if self.temp_sob_dir.exists():
            try:
                self.temp_sob_dir.rmdir()
            except Exception:
                pass

    def test_01_identificacao_dwg_correto(self):
        """Teste 1: Confirmar identificação do DWG correto no contexto da SOB."""
        self.assertIsNotNone(self.workspace.dwg_principal)
        self.assertEqual(self.workspace.dwg_principal, self.fake_dwg)
        self.assertTrue(self.workspace.dwg_principal.exists())

    def test_02_reutilizacao_mecanismo_existente_abrir_artefato(self):
        """Teste 2: Confirmar que a ação reutiliza WorkspaceActionDispatcher.abrir_artefato."""
        with patch.object(WorkspaceActionDispatcher, "abrir_artefato", return_value=True) as mock_abrir:
            app = WorkspaceGUI(root_dir=str(self.temp_sob_dir))
            app.withdraw()
            app.workspace = self.workspace

            with patch("tkinter.messagebox.showinfo"):
                app._on_abrir_unifilar()

            mock_abrir.assert_called_once_with(self.fake_dwg)
            app.destroy()

    def test_03_chamada_abertura_e_mensagem_orientativa(self):
        """Teste 3: Confirmar que mensagem orienta o projetista com os comandos UNIFILAR e PROTECAO."""
        with patch.object(WorkspaceActionDispatcher, "abrir_artefato", return_value=True), \
             patch("tkinter.messagebox.showinfo") as mock_info:

            app = WorkspaceGUI(root_dir=str(self.temp_sob_dir))
            app.withdraw()
            app.workspace = self.workspace

            app._on_abrir_unifilar()

            mock_info.assert_called_once()
            titulo, mensagem = mock_info.call_args[0]
            self.assertIn("Unifilar", titulo)
            self.assertIn("UNIFILAR", mensagem)
            self.assertIn("PROTECAO", mensagem)
            self.assertIn("AutoCAD", mensagem)
            app.destroy()

    def test_04_tratamento_dwg_inexistente(self):
        """Teste 4: Confirmar tratamento controlado quando o DWG não existe no disco."""
        ws_sem_dwg = ProjectWorkspace(
            sob_id="999999",
            sob_name="SOB_999999",
            root_dir=self.temp_sob_dir,
            dwg_principal=None,
        )

        with patch.object(WorkspaceActionDispatcher, "abrir_artefato") as mock_abrir, \
             patch("tkinter.messagebox.showwarning") as mock_warn:

            app = WorkspaceGUI(root_dir=str(self.temp_sob_dir))
            app.withdraw()
            app.workspace = ws_sem_dwg

            app._on_abrir_unifilar()

            mock_abrir.assert_not_called()
            mock_warn.assert_called_once()
            self.assertIn("DWG Não Encontrado", mock_warn.call_args[0][0])
            app.destroy()

    def test_05_comportamento_nao_bloqueante(self):
        """Teste 5: Confirmar que a abertura via Dispatcher é não-bloqueante."""
        with patch("os.startfile", create=True) as mock_startfile, \
             patch("subprocess.run") as mock_run:

            res = WorkspaceActionDispatcher.abrir_artefato(self.fake_dwg)
            self.assertTrue(res)
            mock_startfile.assert_called_once_with(str(self.fake_dwg.resolve()))
            mock_run.assert_not_called()

    def test_06_integracao_gui_botao_e_treeview(self):
        """Teste 6: Confirmar existência do botão ⚡ Unifilar e integração com seleção na Treeview."""
        app = WorkspaceGUI(root_dir=str(self.temp_sob_dir))
        app.withdraw()
        app.workspace = self.workspace

        # 1. Verifica botão na interface
        all_widgets = []
        def get_all(w):
            all_widgets.append(w)
            for c in w.children.values():
                get_all(c)
        get_all(app)

        btns_unif = [w for w in all_widgets if getattr(w, "cget", None) and w.winfo_class() == "Button" and "Unifilar" in w.cget("text")]
        self.assertEqual(len(btns_unif), 1)

        # 2. Verifica abertura via Treeview quando UNIFILAR não foi gerado
        art_unifilar = ProjectArtifact(
            chave="UNIFILAR",
            rotulo="Diagrama Unifilar / Proteção",
            status=ArtifactStatus.NAO_EXISTE,
            caminho=None,
        )
        with patch.object(app, "_get_selected_artifact", return_value=art_unifilar), \
             patch.object(app, "_on_abrir_unifilar") as mock_on_unif:

            app._on_abrir_artefato()
            mock_on_unif.assert_called_once()

        app.destroy()

    def test_07_isolamento_sem_sgt_e_sem_sqlite(self):
        """Teste 7: Confirmar isolamento total — sem chamadas HTTP ao SGT e sem queries SQLite."""
        with patch.object(urllib.request, "urlopen") as mock_url, \
             patch.object(sqlite3, "connect") as mock_sql, \
             patch.object(WorkspaceActionDispatcher, "abrir_artefato", return_value=True), \
             patch("tkinter.messagebox.showinfo"):

            app = WorkspaceGUI(root_dir=str(self.temp_sob_dir))
            app.withdraw()
            app.workspace = self.workspace

            app._on_abrir_unifilar()

            mock_url.assert_not_called()
            mock_sql.assert_not_called()
            app.destroy()

    def test_08_nenhum_lancamento_unifilar_manager(self):
        """Teste 8: Confirmar que unifilar_manager.py NÃO é disparado pelo Workspace."""
        with patch("subprocess.Popen") as mock_popen, \
             patch.object(WorkspaceActionDispatcher, "abrir_artefato", return_value=True), \
             patch("tkinter.messagebox.showinfo"):

            app = WorkspaceGUI(root_dir=str(self.temp_sob_dir))
            app.withdraw()
            app.workspace = self.workspace

            app._on_abrir_unifilar()

            # Popen não deve ser chamado para unifilar_manager.py
            for call in mock_popen.call_args_list:
                args = call[0]
                if args and isinstance(args[0], (list, tuple)):
                    cmd_str = " ".join(str(x) for x in args[0])
                    self.assertNotIn("unifilar_manager.py", cmd_str)

            app.destroy()


if __name__ == "__main__":
    unittest.main()
