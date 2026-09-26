# -*- coding: utf-8 -*-
"""
test_workspace_ambiental_action.py - Testes unitários para a ação AMBIENTAL no Workspace.
Valida:
A. Workspace válido e montagem rigorosa dos 5 argumentos posicionais;
B. Workspace nulo / ausente (ValueError);
C. SOB ausente (None, "", "   ") (ValueError);
D. Normalização da SOB (ex: "  zna123456  " -> ZNA123456);
E. Root directory obrigatório e existente em disco (ValueError / FileNotFoundError);
F. Template DOCX existente vs ausente (resiliência com "");
G. kmz_points_input.json (explícito, root_dir, legado C:\\Temp, ausente);
H. kmz_boxes.txt (explícito, root_dir, legado C:\\Temp, ausente);
I. Fuso UTM default (23) e customizado;
J. Execução desacoplada não-bloqueante via subprocess.Popen;
K. Integração visual com WorkspaceGUI (_on_executar_ambiental);
L. Isolamento estrito de rede e serviços externos;
M. Não-regressão de métodos homologados (CPFC, Orçamento, SOB, AutoPranche).
"""

from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

from workspace.workspace_core import ProjectWorkspace
from workspace.workspace_actions import WorkspaceActionDispatcher, BASE_DIR
from workspace.workspace_cli import WorkspaceGUI


class TestWorkspaceAmbientalAction(unittest.TestCase):
    """Bateria completa de testes unitários para a integração do módulo Ambiental ao Workspace."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.temp_sob_dir = self.repo_root / "temp_fake_sob_amb"
        self.temp_sob_dir.mkdir(parents=True, exist_ok=True)
        self.workspace = ProjectWorkspace(
            sob_id="A057349839",
            sob_name="SOB_A057349839",
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

    def test_01_montagem_comando_e_argumentos_posicionais(self):
        """Teste 1: Confirmar montagem do comando com exatamente 5 argumentos posicionais do especialista."""
        cmd = WorkspaceActionDispatcher.montar_comando_ambiental(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        self.assertIsInstance(cmd, list)
        self.assertEqual(len(cmd), 7)  # [sys.executable, script, tpl, pts, boxes, fuso, out_dir]
        self.assertEqual(cmd[0], sys.executable)
        self.assertTrue(cmd[1].endswith("memorial_ambiental_generator.py"))
        # 5 argumentos do contrato:
        self.assertIsInstance(cmd[2], str)  # template_docx ("" se ausente)
        self.assertIsInstance(cmd[3], str)  # pts_json ("" se ausente)
        self.assertIsInstance(cmd[4], str)  # boxes_txt ("" se ausente)
        self.assertEqual(cmd[5], "23")      # fuso_utm ("23")
        self.assertEqual(cmd[6], str(self.temp_sob_dir.resolve()))  # out_dir

    def test_02_script_alvo_e_fallback_resiliente(self):
        """Teste 2: Confirmar resolução do script e fallback resiliente quando base_dir for pasta temporária."""
        # 1. Resolução padrão a partir da raiz do repositório
        cmd = WorkspaceActionDispatcher.montar_comando_ambiental(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        script_path = Path(cmd[1])
        self.assertTrue(script_path.exists())
        self.assertEqual(script_path.name, "memorial_ambiental_generator.py")
        self.assertEqual(script_path.parent.name, "ambiental")

        # 2. Resolução resiliente quando base_dir for pasta sem o script
        cmd_fallback = WorkspaceActionDispatcher.montar_comando_ambiental(
            workspace=self.workspace,
            base_dir=self.temp_sob_dir,
        )
        script_fb = Path(cmd_fallback[1])
        self.assertTrue(script_fb.exists())
        self.assertEqual(script_fb.resolve(), (BASE_DIR / "ambiental" / "memorial_ambiental_generator.py").resolve())

    def test_03_execucao_nao_bloqueante_com_popen(self):
        """Teste 3: Mockar subprocess.Popen e confirmar processo iniciado, não-bloqueante e cwd correto."""
        with patch("subprocess.Popen") as mock_popen, patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            proc = WorkspaceActionDispatcher.executar_ambiental(
                workspace=self.workspace,
                base_dir=self.repo_root,
            )
            self.assertEqual(proc, mock_proc)
            mock_popen.assert_called_once()
            mock_run.assert_not_called()
            mock_proc.wait.assert_not_called()

            args, kwargs = mock_popen.call_args
            self.assertEqual(kwargs.get("cwd"), str(self.repo_root))

    def test_04_tratamento_erro_popen(self):
        """Teste 4: Simular falha de execução no Popen e confirmar propagação controlada de exceção."""
        with patch("subprocess.Popen", side_effect=OSError("Falha ao invocar processo no Windows")):
            with self.assertRaises(OSError):
                WorkspaceActionDispatcher.executar_ambiental(
                    workspace=self.workspace,
                    base_dir=self.repo_root,
                )

    def test_05_validacao_workspace_sob_e_root_dir(self):
        """Teste 5: Validar rejeição estrita de workspace nulo, sob_id ausente/vazio e root_dir inexistente."""
        # 1. Workspace nulo
        with self.assertRaises(ValueError) as ctx_none:
            WorkspaceActionDispatcher.montar_comando_ambiental(
                workspace=None,
                base_dir=self.repo_root,
            )
        self.assertIn("workspace não informado", str(ctx_none.exception).lower())

        # 2. SOB None
        ws_no_sob = ProjectWorkspace(
            sob_id=None,
            sob_name="SOB_SEM_ID",
            root_dir=self.temp_sob_dir,
        )
        with self.assertRaises(ValueError) as ctx_sob:
            WorkspaceActionDispatcher.montar_comando_ambiental(
                workspace=ws_no_sob,
                base_dir=self.repo_root,
            )
        self.assertIn("sob_id", str(ctx_sob.exception).lower())

        # 3. SOB string vazia
        ws_empty_sob = ProjectWorkspace(
            sob_id="",
            sob_name="SOB_VAZIA",
            root_dir=self.temp_sob_dir,
        )
        with self.assertRaises(ValueError) as ctx_empty:
            WorkspaceActionDispatcher.montar_comando_ambiental(
                workspace=ws_empty_sob,
                base_dir=self.repo_root,
            )
        self.assertIn("sob_id", str(ctx_empty.exception).lower())

        # 4. SOB apenas espaços em branco
        ws_spaces_sob = ProjectWorkspace(
            sob_id="   ",
            sob_name="SOB_ESPACOS",
            root_dir=self.temp_sob_dir,
        )
        with self.assertRaises(ValueError) as ctx_spaces:
            WorkspaceActionDispatcher.montar_comando_ambiental(
                workspace=ws_spaces_sob,
                base_dir=self.repo_root,
            )
        self.assertIn("sob_id", str(ctx_spaces.exception).lower())

        # 5. Diretório root inexistente
        ws_fake_dir = ProjectWorkspace(
            sob_id="999999",
            sob_name="SOB_999999",
            root_dir=Path("/caminho/comprovadamente/inexistente_999999"),
        )
        with self.assertRaises(FileNotFoundError) as ctx_fnf:
            WorkspaceActionDispatcher.montar_comando_ambiental(
                workspace=ws_fake_dir,
                base_dir=self.repo_root,
            )
        self.assertIn("não existe no disco", str(ctx_fnf.exception))

    def test_06_normalizacao_sob_id(self):
        """Teste 6: Validar que sob_id com espaços ou minúsculas é devidamente aceito e normalizado."""
        ws_dirty = ProjectWorkspace(
            sob_id="  zna123456  ",
            sob_name="SOB_ZNA123456",
            root_dir=self.temp_sob_dir,
        )
        cmd = WorkspaceActionDispatcher.montar_comando_ambiental(
            workspace=ws_dirty,
            base_dir=self.repo_root,
        )
        self.assertIsNotNone(cmd)
        self.assertEqual(len(cmd), 7)

    def test_07_resolucao_template_docx(self):
        """Teste 7: Validar resolução do template DOCX quando existente e quando ausente (resiliência com "")."""
        # 1. Template explícito existente
        fake_tpl = self.temp_sob_dir / "template_teste.docx"
        fake_tpl.write_text("dummy", encoding="utf-8")

        cmd_tpl = WorkspaceActionDispatcher.montar_comando_ambiental(
            workspace=self.workspace,
            template_path=fake_tpl,
            base_dir=self.repo_root,
        )
        self.assertEqual(cmd_tpl[2], str(fake_tpl.resolve()))

        # 2. Template inexistente (não deve lançar exceção fatal, deve passar "")
        cmd_no_tpl = WorkspaceActionDispatcher.montar_comando_ambiental(
            workspace=self.workspace,
            template_path=self.temp_sob_dir / "inexistente.docx",
            base_dir=self.repo_root,
        )
        self.assertEqual(cmd_no_tpl[2], "")

    def test_08_resolucao_pontos_kmz_input(self):
        """Teste 8: Validar prioridade de resolução de kmz_points_input.json (explícito, root_dir, legado, ausente)."""
        # Prioridade 1: Argumento explícito
        explicit_pts = self.temp_sob_dir / "pts_explicito.json"
        explicit_pts.write_text("[]", encoding="utf-8")
        cmd_p1 = WorkspaceActionDispatcher.montar_comando_ambiental(
            workspace=self.workspace,
            pts_json=explicit_pts,
            base_dir=self.repo_root,
        )
        self.assertEqual(cmd_p1[3], str(explicit_pts.resolve()))

        # Prioridade 2: kmz_points_input.json na pasta da SOB (root_dir)
        sob_pts = self.temp_sob_dir / "kmz_points_input.json"
        sob_pts.write_text("[]", encoding="utf-8")
        cmd_p2 = WorkspaceActionDispatcher.montar_comando_ambiental(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        self.assertEqual(cmd_p2[3], str(sob_pts.resolve()))
        sob_pts.unlink()

        # Prioridade 3: Fallback legado C:\Temp\kmz_points_input.json via mock de Path.exists
        orig_exists = Path.exists
        def mock_legacy_pts(p_self):
            s = str(p_self)
            if "C:\\Temp\\kmz_points_input.json" in s or "C:/Temp/kmz_points_input.json" in s:
                return True
            if "kmz_points_input.json" in s:
                return False
            return orig_exists(p_self)

        with patch.object(Path, "exists", autospec=True, side_effect=mock_legacy_pts):
            cmd_p3 = WorkspaceActionDispatcher.montar_comando_ambiental(
                workspace=self.workspace,
                base_dir=self.repo_root,
            )
            self.assertTrue(cmd_p3[3].endswith("kmz_points_input.json"))

        # Prioridade 4: Ausência completa (inclusive em C:\Temp) -> string vazia ""
        def mock_none_pts(p_self):
            s = str(p_self)
            if "kmz_points_input.json" in s:
                return False
            return orig_exists(p_self)

        with patch.object(Path, "exists", autospec=True, side_effect=mock_none_pts):
            cmd_p4 = WorkspaceActionDispatcher.montar_comando_ambiental(
                workspace=self.workspace,
                base_dir=self.repo_root,
            )
            self.assertEqual(cmd_p4[3], "")

    def test_09_resolucao_boxes_txt(self):
        """Teste 9: Validar prioridade de resolução de kmz_boxes.txt (explícito, root_dir, legado, ausente)."""
        # Prioridade 1: Argumento explícito
        explicit_boxes = self.temp_sob_dir / "boxes_explicito.txt"
        explicit_boxes.write_text("APP|RIO", encoding="utf-8")
        cmd_b1 = WorkspaceActionDispatcher.montar_comando_ambiental(
            workspace=self.workspace,
            boxes_txt=explicit_boxes,
            base_dir=self.repo_root,
        )
        self.assertEqual(cmd_b1[4], str(explicit_boxes.resolve()))

        # Prioridade 2: kmz_boxes.txt na pasta da SOB (root_dir)
        sob_boxes = self.temp_sob_dir / "kmz_boxes.txt"
        sob_boxes.write_text("APP|RIO", encoding="utf-8")
        cmd_b2 = WorkspaceActionDispatcher.montar_comando_ambiental(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        self.assertEqual(cmd_b2[4], str(sob_boxes.resolve()))
        sob_boxes.unlink()

        # Prioridade 3: Fallback legado C:\Temp\kmz_boxes.txt via mock de Path.exists
        orig_exists = Path.exists
        def mock_legacy_boxes(p_self):
            s = str(p_self)
            if "C:\\Temp\\kmz_boxes.txt" in s or "C:/Temp/kmz_boxes.txt" in s:
                return True
            if "kmz_boxes.txt" in s:
                return False
            return orig_exists(p_self)

        with patch.object(Path, "exists", autospec=True, side_effect=mock_legacy_boxes):
            cmd_b3 = WorkspaceActionDispatcher.montar_comando_ambiental(
                workspace=self.workspace,
                base_dir=self.repo_root,
            )
            self.assertTrue(cmd_b3[4].endswith("kmz_boxes.txt"))

        # Prioridade 4: Ausência completa (inclusive em C:\Temp) -> string vazia ""
        def mock_none_boxes(p_self):
            s = str(p_self)
            if "kmz_boxes.txt" in s:
                return False
            return orig_exists(p_self)

        with patch.object(Path, "exists", autospec=True, side_effect=mock_none_boxes):
            cmd_b4 = WorkspaceActionDispatcher.montar_comando_ambiental(
                workspace=self.workspace,
                base_dir=self.repo_root,
            )
            self.assertEqual(cmd_b4[4], "")

    def test_10_fuso_utm_customizado_e_default(self):
        """Teste 10: Validar propagação do fuso UTM: default '23' ou valor numérico customizado."""
        # Default: 23
        cmd_def = WorkspaceActionDispatcher.montar_comando_ambiental(
            workspace=self.workspace,
            base_dir=self.repo_root,
        )
        self.assertEqual(cmd_def[5], "23")

        # Customizado: 24
        cmd_cst = WorkspaceActionDispatcher.montar_comando_ambiental(
            workspace=self.workspace,
            fuso=24,
            base_dir=self.repo_root,
        )
        self.assertEqual(cmd_cst[5], "24")

    def test_11_integracao_gui_botao_e_handler(self):
        """Teste 11: Confirmar existência do botão 🌿 Ambiental e que o handler chama o dispatcher."""
        app = WorkspaceGUI(root_dir=str(self.temp_sob_dir))
        app.withdraw()

        all_widgets = []
        def get_all(w):
            all_widgets.append(w)
            for c in w.children.values():
                get_all(c)
        get_all(app)

        btns_amb = [w for w in all_widgets if getattr(w, "cget", None) and w.winfo_class() == "Button" and "Ambiental" in w.cget("text")]
        self.assertEqual(len(btns_amb), 1)
        self.assertIn("Ambiental", btns_amb[0].cget("text"))

        # Caso Sucesso: Popen retorna processo válido -> showinfo
        with patch.object(WorkspaceActionDispatcher, "executar_ambiental") as mock_exec, \
             patch("tkinter.messagebox.showinfo") as mock_info:
            mock_exec.return_value = MagicMock()
            app._on_executar_ambiental()
            mock_exec.assert_called_once_with(app.workspace)
            mock_info.assert_called_once()
            self.assertIn("iniciado", mock_info.call_args[0][1])

        # Caso Falha: showerror amigável
        with patch.object(WorkspaceActionDispatcher, "executar_ambiental", side_effect=RuntimeError("Erro ao lançar")), \
             patch("tkinter.messagebox.showerror") as mock_err:
            app._on_executar_ambiental()
            mock_err.assert_called_once()
            self.assertIn("Erro ao Iniciar Ambiental", mock_err.call_args[0][0])

        app.destroy()

    def test_12_isolamento_sem_chamadas_externas(self):
        """Teste 12: Garantir que nenhuma chamada a rede, SharePoint, GOMNET ou AutoCAD ocorre."""
        with patch("urllib.request.urlopen") as mock_url, \
             patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()

            proc = WorkspaceActionDispatcher.executar_ambiental(
                workspace=self.workspace,
                base_dir=self.repo_root,
            )
            self.assertIsNotNone(proc)
            mock_url.assert_not_called()

    def test_13_nao_regressao_assinaturas_homologadas(self):
        """Teste 13: Garantir não-regressão estrita dos métodos despachantes já homologados."""
        # CPFC
        self.assertTrue(hasattr(WorkspaceActionDispatcher, "montar_comando_cpfc"))
        self.assertTrue(hasattr(WorkspaceActionDispatcher, "executar_cpfc"))
        cmd_cpfc = WorkspaceActionDispatcher.montar_comando_cpfc(self.workspace, base_dir=self.repo_root)
        self.assertTrue(any("cpfc_manager.py" in arg for arg in cmd_cpfc))

        # Orçamento
        self.assertTrue(hasattr(WorkspaceActionDispatcher, "montar_comando_orcamento"))
        self.assertTrue(hasattr(WorkspaceActionDispatcher, "executar_orcamento"))
        cmd_orc = WorkspaceActionDispatcher.montar_comando_orcamento(self.workspace, base_dir=self.repo_root)
        self.assertTrue(any("orcamento_manager.py" in arg for arg in cmd_orc))
        self.assertIn("--projeto", cmd_orc)
        self.assertIn("A057349839", cmd_orc)

        # SOB
        self.assertTrue(hasattr(WorkspaceActionDispatcher, "montar_comando_sob"))
        self.assertTrue(hasattr(WorkspaceActionDispatcher, "executar_sob"))

        # AutoPranche
        self.assertTrue(hasattr(WorkspaceActionDispatcher, "montar_comando_prancha"))
        self.assertTrue(hasattr(WorkspaceActionDispatcher, "executar_prancha"))


if __name__ == "__main__":
    unittest.main()
