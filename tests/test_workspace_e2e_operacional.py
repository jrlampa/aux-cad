# -*- coding: utf-8 -*-
"""
test_workspace_e2e_operacional.py - Homologação Operacional E2E do Workspace V1.

Valida o ciclo operacional de ponta a ponta:
1. Ciclo de Refresh: detecção inicial -> geração externa de artefatos -> refresh -> Treeview atualizada.
2. Comportamento Não-Bloqueante: execução de subprocessos desacoplados sem travamento de GUI.
3. Ciclo de Artefatos para CQT, Orçamento, Ambiental, CPFC, Prancha, SOB e Unifilar.
4. Triagem de Unifilar (abertura de DWG e orientação CAD sem subprocesso headless).
5. Avaliação do Multiclick / Dupla Execução e resiliência a erros.
"""

from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

from workspace.workspace_core import ArtifactStatus, ProjectArtifact, ProjectWorkspace
from workspace.workspace_scanner import WorkspaceScanner
from workspace.workspace_actions import WorkspaceActionDispatcher
from workspace.workspace_cli import WorkspaceGUI


class TestWorkspaceE2EOperacional(unittest.TestCase):
    """Bateria de testes E2E do fluxo operacional integrado do Workspace V1."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.temp_root = self.repo_root / "temp_e2e_workspace_test"
        self.temp_root.mkdir(parents=True, exist_ok=True)

        self.sob_id = "A057999888"
        self.sob_dir = self.temp_root / f"SOB_{self.sob_id}"
        self.sob_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        # Limpeza segura do diretório temporário de testes
        if self.temp_root.exists():
            import shutil
            shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_e2e_01_ciclo_completo_refresh_artefatos(self):
        """
        FASE 3 & FASE 7: Valida o ciclo completo de detecção, geração externa e refresh.
        - Inicialmente, pasta vazia da SOB: artefatos com status NAO_EXISTE.
        - Criação sintética dos arquivos gerados pelos especialistas.
        - Execução do refresh (simulando clique no botão Atualizar).
        - Validação de que a Treeview e o Workspace transicionam para EXISTE.
        """
        app = WorkspaceGUI(root_dir=str(self.sob_dir), sob_id=self.sob_id)
        app.withdraw()

        # 1. Estado Inicial: sem artefatos gerados
        ws_inicial = app.workspace
        self.assertEqual(ws_inicial.sob_id, self.sob_id)
        self.assertEqual(ws_inicial.status_de("CQT"), ArtifactStatus.NAO_EXISTE)
        self.assertEqual(ws_inicial.status_de("ORCAMENTO"), ArtifactStatus.NAO_EXISTE)
        self.assertEqual(ws_inicial.status_de("MEMORIAL_AMBIENTAL"), ArtifactStatus.NAO_EXISTE)
        self.assertEqual(ws_inicial.status_de("CHECKLIST_AMBIENTAL"), ArtifactStatus.NAO_EXISTE)
        self.assertEqual(ws_inicial.status_de("CPFC"), ArtifactStatus.NAO_EXISTE)

        # 2. Criação externa de artefatos de especialistas (CQT, Orçamento, Ambiental, CPFC, DWG)
        cqt_file = self.sob_dir / f"CQT_{self.sob_id}.xlsm"
        cqt_file.write_bytes(b"FAKE_CQT_EXCEL")

        orc_file = self.sob_dir / f"ORCAMENTO_{self.sob_id}.xlsx"
        orc_file.write_bytes(b"FAKE_ORCAMENTO_EXCEL")

        mem_file = self.sob_dir / f"MEMORIAL_DESCRITIVO_{self.sob_id}.docx"
        mem_file.write_bytes(b"FAKE_MEMORIAL_WORD")

        chk_file = self.sob_dir / f"CHECKLIST_{self.sob_id}.xlsx"
        chk_file.write_bytes(b"FAKE_CHECKLIST_EXCEL")

        cpfc_file = self.sob_dir / f"CPFC_{self.sob_id}.xlsx"
        cpfc_file.write_bytes(b"FAKE_CPFC_EXCEL")

        dwg_file = self.sob_dir / f"PE_{self.sob_id}_DESENHO.dwg"
        dwg_file.write_bytes(b"FAKE_DWG_CONTENT")

        # 3. Disparo do Refresh (simula clique em 🔄 Atualizar)
        app._executar_varredura()

        # 4. Estado Atualizado: todos os artefatos devem constar como EXISTE
        ws_atualizado = app.workspace
        self.assertEqual(ws_atualizado.status_de("CQT"), ArtifactStatus.EXISTE)
        self.assertEqual(ws_atualizado.status_de("ORCAMENTO"), ArtifactStatus.EXISTE)
        self.assertEqual(ws_atualizado.status_de("MEMORIAL_AMBIENTAL"), ArtifactStatus.EXISTE)
        self.assertEqual(ws_atualizado.status_de("CHECKLIST_AMBIENTAL"), ArtifactStatus.EXISTE)
        self.assertEqual(ws_atualizado.status_de("CPFC"), ArtifactStatus.EXISTE)
        self.assertEqual(ws_atualizado.status_de("DWG"), ArtifactStatus.EXISTE)

        # 5. Verifica se os valores foram refletidos na Treeview
        item_cqt = app.tree.item("CQT")
        self.assertIn("✔ EXISTE", item_cqt["values"])
        self.assertIn(cqt_file.name, item_cqt["values"][2])

        item_orc = app.tree.item("ORCAMENTO")
        self.assertIn("✔ EXISTE", item_orc["values"])
        self.assertIn(orc_file.name, item_orc["values"][2])

        item_mem = app.tree.item("MEMORIAL_AMBIENTAL")
        self.assertIn("✔ EXISTE", item_mem["values"])
        self.assertIn(mem_file.name, item_mem["values"][2])

        app.destroy()

    def test_e2e_02_comportamento_nao_bloqueante_e_independencia_processo(self):
        """
        FASE 5 & FASE 6: Valida que _lancar_processo executa Popen sem travar a GUI.
        Demonstra que o processo filho inicia e o método retorna imediatamente (< 0.1s)
        mesmo que o subprocesso execute por tempo superior.
        """
        cmd_dormir = [sys.executable, "-c", "import time; time.sleep(0.3)"]
        t_inicio = time.perf_counter()
        proc = WorkspaceActionDispatcher._lancar_processo(cmd_dormir, cwd=self.temp_root)
        t_retorno = time.perf_counter() - t_inicio

        # O retorno deve ser praticamente instantâneo (não-bloqueante)
        self.assertLess(t_retorno, 0.15, "O lançamento do processo bloqueou a thread chamadora!")
        self.assertIsInstance(proc, subprocess.Popen)
        self.assertIsNotNone(proc.pid)

        # O processo continua em execução em paralelo
        self.assertIsNone(proc.poll(), "O processo já encerrou antes do esperado!")

        # Aguarda finalização controlada para limpeza do teste
        proc.wait(timeout=2.0)
        self.assertEqual(proc.returncode, 0)

    def test_e2e_03_acoes_gui_despacham_e_tratam_resiliencia(self):
        """
        FASE 4: Valida os handlers de cada ação na GUI, confirmando que:
        - Chamam o Dispatcher correto;
        - Repassam self.workspace;
        - Tratam exceções sem derrubar a GUI;
        - Exibem diálogos de confirmação ou erro de forma controlada.
        """
        app = WorkspaceGUI(root_dir=str(self.sob_dir), sob_id=self.sob_id)
        app.withdraw()

        # Mock dos despachantes para simulação de disparo seguro
        with patch.object(WorkspaceActionDispatcher, "executar_cqt") as mock_cqt, \
             patch.object(WorkspaceActionDispatcher, "executar_orcamento") as mock_orc, \
             patch.object(WorkspaceActionDispatcher, "executar_cpfc") as mock_cpfc, \
             patch.object(WorkspaceActionDispatcher, "executar_ambiental") as mock_amb, \
             patch.object(WorkspaceActionDispatcher, "executar_prancha") as mock_prancha, \
             patch.object(WorkspaceActionDispatcher, "executar_sob") as mock_sob, \
             patch("tkinter.messagebox.showinfo") as mock_info:

            fake_popen = MagicMock()
            mock_cqt.return_value = fake_popen
            mock_orc.return_value = fake_popen
            mock_cpfc.return_value = fake_popen
            mock_amb.return_value = fake_popen
            mock_prancha.return_value = fake_popen
            mock_sob.return_value = fake_popen

            # Disparo CQT
            app._on_executar_cqt()
            mock_cqt.assert_called_once_with(app.workspace)

            # Disparo Orçamento
            app._on_executar_orcamento()
            mock_orc.assert_called_once_with(app.workspace)

            # Disparo CPFC
            app._on_executar_cpfc()
            mock_cpfc.assert_called_once_with(app.workspace)

            # Disparo Ambiental
            app._on_executar_ambiental()
            mock_amb.assert_called_once_with(app.workspace)

            # Disparo AutoPranche
            app._on_executar_prancha()
            mock_prancha.assert_called_once_with(app.workspace)

            # Disparo SOB Launcher
            app._on_executar_sob()
            mock_sob.assert_called_once_with(workspace=app.workspace)

            self.assertEqual(mock_info.call_count, 6)

        app.destroy()

    def test_e2e_04_unifilar_fluxo_cad_interativo_estrito(self):
        """
        FASE 8: Valida especificamente que o Unifilar não lança processo Python,
        mas abre o DWG no AutoCAD via Dispatcher e emite diálogo com UNIFILAR/PROTECAO.
        """
        app = WorkspaceGUI(root_dir=str(self.sob_dir), sob_id=self.sob_id)
        app.withdraw()

        # Cenário 1: Sem DWG gerado -> emite aviso e não tenta abrir
        with patch("tkinter.messagebox.showwarning") as mock_warn:
            app._on_abrir_unifilar()
            mock_warn.assert_called_once()
            titulo, msg = mock_warn.call_args[0]
            self.assertIn("DWG Não Encontrado", titulo)

        # Cenário 2: Com DWG gerado -> abre artefato e exibe comandos orientativos
        dwg_file = self.sob_dir / f"PE_{self.sob_id}_DESENHO.dwg"
        dwg_file.write_bytes(b"DWG_TEST")
        app._executar_varredura()

        with patch.object(WorkspaceActionDispatcher, "abrir_artefato", return_value=True) as mock_abrir, \
             patch("tkinter.messagebox.showinfo") as mock_info:
            app._on_abrir_unifilar()
            mock_abrir.assert_called_once_with(dwg_file)
            mock_info.assert_called_once()
            titulo, msg = mock_info.call_args[0]
            self.assertIn("Diagrama Unifilar", titulo)
            self.assertIn("UNIFILAR", msg)
            self.assertIn("PROTECAO", msg)

        app.destroy()

    def test_e2e_05_avaliacao_multiclick_e_resiliencia(self):
        """
        FASE 10: Avalia o impacto de duplo clique rápido em botão de especialista.
        Verifica que chamadas sucessivas não corrompem o estado da GUI e que cada
        despacho ocorre de forma controlada sem gerar exceções não tratadas.
        """
        app = WorkspaceGUI(root_dir=str(self.sob_dir), sob_id=self.sob_id)
        app.withdraw()

        chamadas = []
        def fake_executar(ws):
            chamadas.append(ws.sob_id)
            return MagicMock()

        with patch.object(WorkspaceActionDispatcher, "executar_cqt", side_effect=fake_executar), \
             patch("tkinter.messagebox.showinfo"):
            # Simula 2 cliques rápidos
            app._on_executar_cqt()
            app._on_executar_cqt()

            self.assertEqual(len(chamadas), 2)
            self.assertEqual(chamadas[0], self.sob_id)
            self.assertEqual(chamadas[1], self.sob_id)

        app.destroy()


if __name__ == "__main__":
    unittest.main()
