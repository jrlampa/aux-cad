# -*- coding: utf-8 -*-
"""
test_workspace_cqt_action.py - Testes unitários para a ação CQT no Workspace.
Valida:
1. Montagem normal do comando na ordem correta [sys.executable, script, tpl, json, dest];
2. Workspace inválido (workspace=None) lança ValueError;
3. SOB ausente (None, "", "   ") lança ValueError;
4. root_dir ausente/inexistente lança ValueError / FileNotFoundError;
5. Normalização da SOB (ex: "a057100646" -> "A057100646");
6. Fallback resiliente do script quando base_dir for temporário;
7. Resolução do modelo padrão modelos/cqt_modelo.xlsm;
8. Resolução do JSON da SOB (workspace.root_dir / "cqt_cad_input.json");
9. Prioridade de JSON explícito sobre o arquivo do diretório;
10. Ausência de JSON resulta em "" sem fabricar dados;
11. Destino padrão workspace.root_dir / f"CQT_{SOB}.xlsm";
12. Destino explícito preservado;
13. Execução desacoplada não-bloqueante via subprocess.Popen (sem wait(), sem run());
14. Alvo do comando apontando exclusivamente para cqt/cqt_excel_manager.py;
15. Isolamento total sem chamadas a processos ou rede externa.
"""

from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

from workspace.workspace_core import ProjectWorkspace
from workspace.workspace_actions import WorkspaceActionDispatcher, BASE_DIR


class TestWorkspaceCQTAction(unittest.TestCase):
    """Bateria completa de testes unitários para a integração do módulo CQT ao Workspace."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.temp_sob_dir = self.repo_root / "temp_fake_sob_cqt"
        self.temp_sob_dir.mkdir(parents=True, exist_ok=True)
        self.workspace = ProjectWorkspace(
            sob_id="A057100646",
            sob_name="SOB_A057100646",
            root_dir=self.temp_sob_dir,
            base_sigla="PE",
        )

    def tearDown(self):
        if self.temp_sob_dir.exists():
            for f in self.temp_sob_dir.glob("*"):
                try:
                    f.unlink()
                except Exception:
                    pass
            try:
                self.temp_sob_dir.rmdir()
            except Exception:
                pass

    def test_01_montagem_normal(self):
        """Teste 1: Workspace válido produz python, cqt_excel_manager.py, modelo XLSM, JSON CAD, CQT_{SOB}.xlsm na ordem correta."""
        cmd = WorkspaceActionDispatcher.montar_comando_cqt(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        self.assertIsInstance(cmd, list)
        self.assertEqual(len(cmd), 5)
        self.assertEqual(cmd[0], sys.executable)
        self.assertTrue(cmd[1].endswith("cqt_excel_manager.py"))
        self.assertTrue(cmd[2].endswith("cqt_modelo.xlsm"))
        self.assertEqual(cmd[3], "")  # Sem JSON prévio
        self.assertTrue(cmd[4].endswith("CQT_A057100646.xlsm"))

    def test_02_workspace_invalido(self):
        """Teste 2: workspace=None deve falhar com ValueError."""
        with self.assertRaises(ValueError) as ctx:
            WorkspaceActionDispatcher.montar_comando_cqt(workspace=None)
        self.assertIn("workspace não informado", str(ctx.exception).lower())

    def test_03_sob_ausente(self):
        """Teste 3: SOB ausente (None, '', '   ') deve falhar com ValueError."""
        ws_none = ProjectWorkspace(sob_id=None, sob_name="SOB_SEM_ID", root_dir=self.temp_sob_dir)
        with self.assertRaises(ValueError):
            WorkspaceActionDispatcher.montar_comando_cqt(workspace=ws_none)

        ws_empty = ProjectWorkspace(sob_id="", sob_name="SOB_VAZIA", root_dir=self.temp_sob_dir)
        with self.assertRaises(ValueError):
            WorkspaceActionDispatcher.montar_comando_cqt(workspace=ws_empty)

        ws_spaces = ProjectWorkspace(sob_id="   ", sob_name="SOB_ESPACOS", root_dir=self.temp_sob_dir)
        with self.assertRaises(ValueError):
            WorkspaceActionDispatcher.montar_comando_cqt(workspace=ws_spaces)

    def test_04_root_dir_ausente_ou_inexistente(self):
        """Teste 4: root_dir ausente ou inexistente no disco deve falhar claramente."""
        ws_no_root = ProjectWorkspace(sob_id="A057100646", sob_name="SOB", root_dir=None)
        with self.assertRaises(ValueError):
            WorkspaceActionDispatcher.montar_comando_cqt(workspace=ws_no_root)

        pasta_inexistente = self.repo_root / "pasta_fantasma_inexistente_cqt"
        ws_fake_root = ProjectWorkspace(sob_id="A057100646", sob_name="SOB", root_dir=pasta_inexistente)
        with self.assertRaises(FileNotFoundError):
            WorkspaceActionDispatcher.montar_comando_cqt(workspace=ws_fake_root)

    def test_05_normalizacao_da_sob(self):
        """Teste 5: Exemplo 'a057100646' deve resultar em 'A057100646' no nome do arquivo de destino."""
        ws_lower = ProjectWorkspace(
            sob_id="  a057100646  ",
            sob_name="SOB_teste",
            root_dir=self.temp_sob_dir,
        )
        cmd = WorkspaceActionDispatcher.montar_comando_cqt(
            workspace=ws_lower,
            base_dir=self.repo_root,
        )
        self.assertTrue(cmd[4].endswith("CQT_A057100646.xlsm"))

    def test_06_fallback_do_script(self):
        """Teste 6: Com base_dir=tmp_path (sem script), confirma que o Dispatcher encontra o script real em BASE_DIR."""
        cmd = WorkspaceActionDispatcher.montar_comando_cqt(
            workspace=self.workspace,
            base_dir=self.temp_sob_dir,
        )
        script_path = Path(cmd[1])
        self.assertTrue(script_path.exists())
        self.assertEqual(script_path.name, "cqt_excel_manager.py")
        self.assertEqual(script_path.parent.name, "cqt")

    def test_07_modelo_padrao(self):
        """Teste 7: Confirmar que o comando utiliza modelos/cqt_modelo.xlsm oficial."""
        cmd = WorkspaceActionDispatcher.montar_comando_cqt(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        modelo_path = Path(cmd[2])
        self.assertTrue(modelo_path.exists())
        self.assertEqual(modelo_path.name, "cqt_modelo.xlsm")
        self.assertEqual(modelo_path.parent.name, "modelos")

    def test_08_json_da_sob(self):
        """Teste 8: Criar workspace.root_dir/cqt_cad_input.json e confirmar que ele é utilizado."""
        cad_json = self.temp_sob_dir / "cqt_cad_input.json"
        cad_json.write_text('{"projeto": "A057100646", "trechos": []}', encoding="utf-8")

        cmd = WorkspaceActionDispatcher.montar_comando_cqt(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        self.assertEqual(cmd[3], str(cad_json))

    def test_09_json_explicito_tem_prioridade(self):
        """Teste 9: Confirmar que cad_json explicitamente fornecido tem prioridade sobre o da pasta da SOB."""
        cad_sob = self.temp_sob_dir / "cqt_cad_input.json"
        cad_sob.write_text('{"origem": "sob"}', encoding="utf-8")

        cad_custom = self.temp_sob_dir / "custom_input.json"
        cad_custom.write_text('{"origem": "custom"}', encoding="utf-8")

        cmd = WorkspaceActionDispatcher.montar_comando_cqt(
            workspace=self.workspace,
            cad_json=cad_custom,
            base_dir=self.repo_root,
        )
        self.assertEqual(cmd[3], str(cad_custom))

    def test_10_ausencia_do_json(self):
        """Teste 10: Confirmar que na ausência do JSON o comando utiliza string vazia '' sem fabricar dados."""
        cmd = WorkspaceActionDispatcher.montar_comando_cqt(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        self.assertEqual(cmd[3], "")

    def test_11_destino_padrao(self):
        """Teste 11: Confirmar destino padrão workspace.root_dir/CQT_{SOB}.xlsm."""
        cmd = WorkspaceActionDispatcher.montar_comando_cqt(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        esperado = str(self.temp_sob_dir / "CQT_A057100646.xlsm")
        self.assertEqual(cmd[4], esperado)

    def test_12_destino_explicito(self):
        """Teste 12: Confirmar que dest_file explícito é preservado."""
        dest_custom = self.temp_sob_dir / "CQT_PERSONALIZADO_REV2.xlsm"
        cmd = WorkspaceActionDispatcher.montar_comando_cqt(
            workspace=self.workspace,
            dest_file=dest_custom,
            base_dir=self.repo_root,
        )
        self.assertEqual(cmd[4], str(dest_custom))

    def test_13_execucao_nao_bloqueante_com_popen(self):
        """Teste 13: Mockar subprocess.Popen e verificar chamada realizada, comando correto, cwd e sem wait/run."""
        with patch("subprocess.Popen") as mock_popen, patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            proc = WorkspaceActionDispatcher.executar_cqt(
                workspace=self.workspace,
                base_dir=self.repo_root,
            )
            self.assertEqual(proc, mock_proc)
            mock_popen.assert_called_once()
            mock_run.assert_not_called()
            mock_proc.wait.assert_not_called()

            args, kwargs = mock_popen.call_args
            cmd_enviado = args[0]
            self.assertEqual(cmd_enviado[0], sys.executable)
            self.assertTrue(cmd_enviado[1].endswith("cqt_excel_manager.py"))
            self.assertEqual(kwargs.get("cwd"), str(self.repo_root))

    def test_14_gui_dispatcher_aponta_para_cqt_excel_manager(self):
        """Teste 14: Confirmar que a ação continua direcionada ao cqt_excel_manager.py e não a um novo executável."""
        cmd = WorkspaceActionDispatcher.montar_comando_cqt(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        self.assertEqual(Path(cmd[1]).name, "cqt_excel_manager.py")
        self.assertEqual(Path(cmd[1]).parent.name, "cqt")

    def test_15_isolamento_sem_chamadas_reais(self):
        """Teste 15: Confirmar que montar_comando_cqt não faz I/O no disco de destino nem executa processos."""
        dest_esperado = self.temp_sob_dir / "CQT_A057100646.xlsm"
        self.assertFalse(dest_esperado.exists())

        cmd = WorkspaceActionDispatcher.montar_comando_cqt(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        self.assertIsInstance(cmd, list)
        # O arquivo de destino NÃO deve ter sido criado pelo Dispatcher
        self.assertFalse(dest_esperado.exists())


if __name__ == "__main__":
    unittest.main()
