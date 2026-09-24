# -*- coding: utf-8 -*-
"""
test_workspace_sob_action.py - Testes unitários para a ação PREPARAR SOB no Workspace.
Garante localização correta do launcher, execução desacoplada não-bloqueante,
tratamento controlado de erros e ausência de execução automática.
"""

from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

from workspace.workspace_core import ProjectWorkspace
from workspace.workspace_actions import WorkspaceActionDispatcher
from workspace.workspace_cli import WorkspaceGUI


class TestWorkspaceSobAction(unittest.TestCase):
    """Bateria de testes para ação PREPARAR SOB no WorkspaceActionDispatcher e WorkspaceGUI."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.workspace = ProjectWorkspace(
            sob_id="12345678",
            sob_name="SOB_12345678",
            root_dir=self.repo_root / "temp_fake_sob",
            base_sigla="PE",
        )

    def test_01_launcher_existente(self):
        """Teste 1: Confirmar que o dispatcher localiza o script oficial sob/sob_launcher_gui.py."""
        cmd = WorkspaceActionDispatcher.montar_comando_sob(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        self.assertIsInstance(cmd, list)
        self.assertEqual(len(cmd), 2)
        self.assertEqual(cmd[0], sys.executable)
        caminho_script = Path(cmd[1])
        self.assertTrue(caminho_script.exists())
        self.assertEqual(caminho_script.name, "sob_launcher_gui.py")

    def test_02_comando_somente_argumentos_suportados(self):
        """Teste 2: Mockar Popen e verificar que cmd contém estritamente sys.executable e script."""
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            proc = WorkspaceActionDispatcher.executar_sob(
                workspace=self.workspace,
                base_dir=self.repo_root,
            )
            self.assertEqual(proc, mock_proc)
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            cmd = args[0]
            self.assertEqual(cmd[0], sys.executable)
            self.assertTrue(cmd[1].endswith("sob_launcher_gui.py"))
            # Confirma que não foram inventados argumentos CLI não suportados pelo launcher GUI
            self.assertEqual(len(cmd), 2)

    def test_03_execucao_nao_bloqueante_com_popen(self):
        """Teste 3: Confirmar que a ação utiliza subprocess.Popen e NUNCA subprocess.run ou wait."""
        with patch("subprocess.Popen") as mock_popen, patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            proc = WorkspaceActionDispatcher.executar_sob(
                workspace=self.workspace,
                base_dir=self.repo_root,
            )
            self.assertIsNotNone(proc)
            mock_popen.assert_called_once()
            mock_run.assert_not_called()
            mock_proc.wait.assert_not_called()

    def test_04_launcher_ausente_falha_controlada(self):
        """Teste 4: Simular launcher inexistente em diretório fictício e esperar FileNotFoundError."""
        fake_dir = Path("/caminho/comprovadamente/inexistente/aux_cad_fake")
        with self.assertRaises(FileNotFoundError) as ctx:
            WorkspaceActionDispatcher.montar_comando_sob(
                workspace=self.workspace,
                base_dir=fake_dir,
            )
        self.assertIn("Launcher oficial da SOB não encontrado", str(ctx.exception))

    def test_05_erro_popen_tratamento_controlado(self):
        """Teste 5: Mockar Popen levantando OSError e confirmar que erro pode ser capturado sem quebrar."""
        with patch("subprocess.Popen", side_effect=OSError("Falha de permissão no SO")):
            with self.assertRaises(OSError):
                WorkspaceActionDispatcher.executar_sob(
                    workspace=self.workspace,
                    base_dir=self.repo_root,
                )

    def test_06_integracao_gui_chama_dispatcher_e_messagebox(self):
        """Teste 6: Confirmar que _on_executar_sob() chama o dispatcher e trata sucesso e falha."""
        app = WorkspaceGUI(root_dir=str(self.repo_root))
        app.withdraw()

        # Caso Sucesso: Popen retorna processo válido -> showinfo
        with patch.object(WorkspaceActionDispatcher, "executar_sob") as mock_exec, \
             patch("tkinter.messagebox.showinfo") as mock_info:
            mock_exec.return_value = MagicMock()
            app._on_executar_sob()
            mock_exec.assert_called_once()
            mock_info.assert_called_once()
            self.assertIn("iniciado", mock_info.call_args[0][1])

        # Caso Launcher ausente: FileNotFoundError -> showerror amigável sem traceback
        with patch.object(WorkspaceActionDispatcher, "executar_sob", side_effect=FileNotFoundError("Arquivo ausente")), \
             patch("tkinter.messagebox.showerror") as mock_err:
            app._on_executar_sob()
            mock_err.assert_called_once()
            self.assertIn("Launcher Não Encontrado", mock_err.call_args[0][0])

        # Caso Erro genérico no Popen: Exception -> showerror amigável
        with patch.object(WorkspaceActionDispatcher, "executar_sob", side_effect=RuntimeError("Falha genérica")), \
             patch("tkinter.messagebox.showerror") as mock_err_gen:
            app._on_executar_sob()
            mock_err_gen.assert_called_once()
            self.assertIn("Erro ao Iniciar Preparador SOB", mock_err_gen.call_args[0][0])

        app.destroy()

    def test_07_nenhuma_execucao_automatica_ao_instanciar_gui(self):
        """Teste 7: Instanciar WorkspaceGUI não pode disparar SOB ou outros processos especialistas."""
        with patch.object(WorkspaceActionDispatcher, "executar_sob") as mock_sob, \
             patch.object(WorkspaceActionDispatcher, "executar_cqt") as mock_cqt, \
             patch.object(WorkspaceActionDispatcher, "executar_orcamento") as mock_orc, \
             patch.object(WorkspaceActionDispatcher, "executar_cpfc") as mock_cpfc, \
             patch("subprocess.Popen") as mock_popen:

            app = WorkspaceGUI(root_dir=str(self.repo_root))
            app.withdraw()

            mock_sob.assert_not_called()
            mock_cqt.assert_not_called()
            mock_orc.assert_not_called()
            mock_cpfc.assert_not_called()
            mock_popen.assert_not_called()

            app.destroy()


if __name__ == "__main__":
    unittest.main()
