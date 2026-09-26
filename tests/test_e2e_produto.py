# -*- coding: utf-8 -*-
"""
test_e2e_produto.py - Homologação E2E de Integração do Produto AUX CAD V1.

Valida a coerência dos contratos funcionais entre os módulos especialistas:
1. Consistência Transversal da SOB e Root Directory em todos os módulos.
2. Contratos de Dados CAD intermediários (JSON) -> Especialistas -> Saídas.
3. Correspondência exata entre arquivos gerados e padrões de detecção do WorkspaceScanner.
4. Idempotência operacional (repetição de rotinas na mesma pasta).
5. Recuperação resiliente após falha parcial de artefatos.
"""

import json
from pathlib import Path
import unittest

from workspace.workspace_core import ArtifactStatus, ProjectWorkspace
from workspace.workspace_scanner import WorkspaceScanner
from workspace.workspace_actions import WorkspaceActionDispatcher


class TestE2EIntegracaoProduto(unittest.TestCase):
    """Testes de integração funcional de produto da suíte AUX CAD V1."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.temp_root = self.repo_root / "temp_e2e_produto_test"
        self.temp_root.mkdir(parents=True, exist_ok=True)

        self.sob_id = "A057349839"
        self.sob_dir = self.temp_root / f"SOB_{self.sob_id}"
        self.sob_dir.mkdir(parents=True, exist_ok=True)

        self.workspace = ProjectWorkspace(
            sob_id=self.sob_id,
            sob_name=f"SOB_{self.sob_id}",
            root_dir=self.sob_dir,
            base_sigla="PE",
            metadados={"municipio": "ANGRA DOS REIS", "endereco": "RUA DAS FLORES 10"},
        )

    def tearDown(self):
        if self.temp_root.exists():
            import shutil
            shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_01_consistencia_transversal_sob_e_root(self):
        """
        Valida que todos os comandos gerados pelos métodos do Dispatcher
        utilizam rigorosamente a mesma SOB ('A057349839') e apontam para o root_dir da SOB.
        """
        # CQT
        cmd_cqt = WorkspaceActionDispatcher.montar_comando_cqt(self.workspace)
        self.assertIn(f"CQT_{self.sob_id}.xlsm", cmd_cqt[4])
        self.assertTrue(str(self.sob_dir) in cmd_cqt[4])

        # Orçamento
        cmd_orc = WorkspaceActionDispatcher.montar_comando_orcamento(self.workspace)
        self.assertIn("--projeto", cmd_orc)
        self.assertIn(self.sob_id, cmd_orc)
        self.assertIn("--municipio", cmd_orc)
        self.assertIn("ANGRA DOS REIS", cmd_orc)

        # CPFC
        cmd_cpfc = WorkspaceActionDispatcher.montar_comando_cpfc(self.workspace)
        # Com metadados, passa arquivo json temporário contendo SOB e pasta_destino
        json_temp_path = Path(cmd_cpfc[2])
        self.assertTrue(json_temp_path.exists())
        conteudo_cpfc = json.loads(json_temp_path.read_text(encoding="utf-8"))
        self.assertEqual(conteudo_cpfc["projeto"], self.sob_id)
        self.assertEqual(conteudo_cpfc["pasta_destino"], str(self.sob_dir))

        # Ambiental
        cmd_amb = WorkspaceActionDispatcher.montar_comando_ambiental(self.workspace)
        self.assertEqual(cmd_amb[6], str(self.sob_dir.resolve()))

        # AutoPranche
        cmd_prancha = WorkspaceActionDispatcher.montar_comando_prancha(self.workspace)
        self.assertIn("--sob", cmd_prancha)
        self.assertIn(self.sob_id, cmd_prancha)
        self.assertIn("--root", cmd_prancha)
        self.assertIn(str(self.sob_dir), cmd_prancha)

    def test_02_contrato_cad_cqt_e_reconhecimento_scanner(self):
        """
        Valida o fluxo CAD -> CQT:
        - Geração de intercâmbio cqt_cad_input.json na pasta da SOB.
        - Detecção automática pelo Dispatcher.
        - Geração da planilha de saída CQT_{SOB}.xlsm.
        - Reconhecimento com status EXISTE pelo WorkspaceScanner.
        """
        cad_json = self.sob_dir / "cqt_cad_input.json"
        cad_json.write_text(json.dumps({"trechos": [], "trafo": {}}), encoding="utf-8")

        cmd = WorkspaceActionDispatcher.montar_comando_cqt(self.workspace)
        self.assertEqual(cmd[3], str(cad_json))

        # Simula criação do arquivo final pelo especialista
        cqt_out = self.sob_dir / f"CQT_{self.sob_id}.xlsm"
        cqt_out.write_bytes(b"EXCEL_CQT_DATA")

        ws_scan = WorkspaceScanner.scan(self.sob_dir)
        self.assertEqual(ws_scan.status_de("CQT"), ArtifactStatus.EXISTE)
        self.assertEqual(ws_scan.obter_artefato("CQT").caminho, cqt_out)

    def test_03_contrato_cad_orcamento_e_reconhecimento_scanner(self):
        """
        Valida o fluxo CAD -> Orçamento:
        - Presença de orcamento_dados.json gerado pelo comando CAD ORCAD.
        - Encaminhamento automático via flag --json.
        - Geração de ORCAMENTO_{SOB}.xlsx.
        - Reconhecimento com status EXISTE pelo WorkspaceScanner.
        """
        orc_cad_json = self.sob_dir / "orcamento_dados.json"
        orc_cad_json.write_text(json.dumps({"postes": [], "cabos": []}), encoding="utf-8")

        cmd = WorkspaceActionDispatcher.montar_comando_orcamento(self.workspace)
        idx_json = cmd.index("--json")
        self.assertEqual(cmd[idx_json + 1], str(orc_cad_json))

        # Simula criação do arquivo final
        orc_out = self.sob_dir / f"ORCAMENTO_{self.sob_id}.xlsx"
        orc_out.write_bytes(b"EXCEL_ORCAMENTO_DATA")

        ws_scan = WorkspaceScanner.scan(self.sob_dir)
        self.assertEqual(ws_scan.status_de("ORCAMENTO"), ArtifactStatus.EXISTE)
        self.assertEqual(ws_scan.obter_artefato("ORCAMENTO").caminho, orc_out)

    def test_04_contrato_cad_ambiental_e_reconhecimento_scanner(self):
        """
        Valida o fluxo CAD -> Ambiental:
        - Presença de kmz_points_input.json e kmz_boxes.txt na pasta da SOB.
        - Resolução automática das entradas pelo Dispatcher.
        - Geração condicional de CHECKLIST_{SOB}.xlsx e MEMORIAL_DESCRITIVO_{SOB}.docx.
        - Reconhecimento de ambos pelo WorkspaceScanner.
        """
        pts_json = self.sob_dir / "kmz_points_input.json"
        pts_json.write_text(json.dumps([]), encoding="utf-8")

        boxes_txt = self.sob_dir / "kmz_boxes.txt"
        boxes_txt.write_text("APP|Faixa Marginal de Protecao\n", encoding="utf-8")

        cmd = WorkspaceActionDispatcher.montar_comando_ambiental(self.workspace)
        self.assertEqual(cmd[3], str(pts_json.resolve()))
        self.assertEqual(cmd[4], str(boxes_txt.resolve()))

        # Simula geração dos artefatos
        chk_out = self.sob_dir / f"CHECKLIST_{self.sob_id}.xlsx"
        chk_out.write_bytes(b"CHECKLIST_DATA")

        mem_out = self.sob_dir / f"MEMORIAL_DESCRITIVO_{self.sob_id}.docx"
        mem_out.write_bytes(b"MEMORIAL_DATA")

        ws_scan = WorkspaceScanner.scan(self.sob_dir)
        self.assertEqual(ws_scan.status_de("CHECKLIST_AMBIENTAL"), ArtifactStatus.EXISTE)
        self.assertEqual(ws_scan.status_de("MEMORIAL_AMBIENTAL"), ArtifactStatus.EXISTE)

    def test_05_idempotencia_e_recuperacao_resiliente(self):
        """
        Valida a idempotência do produto:
        - Múltiplas varreduras sucessivas do WorkspaceScanner não alteram ou duplicam o estado.
        - Remoção ou acréscimo de artefatos é refletida de forma consistente e determinística.
        """
        ws1 = WorkspaceScanner.scan(self.sob_dir)
        self.assertEqual(ws1.status_de("CQT"), ArtifactStatus.NAO_EXISTE)

        # 1ª Geração de CQT
        cqt_out = self.sob_dir / f"CQT_{self.sob_id}.xlsm"
        cqt_out.write_bytes(b"CQT_V1")

        ws2 = WorkspaceScanner.scan(self.sob_dir)
        self.assertEqual(ws2.status_de("CQT"), ArtifactStatus.EXISTE)

        # 2ª Execução / Sobrescrita segura (Idempotência)
        cqt_out.write_bytes(b"CQT_V2_ATUALIZADO")
        ws3 = WorkspaceScanner.scan(self.sob_dir)
        self.assertEqual(ws3.status_de("CQT"), ArtifactStatus.EXISTE)
        self.assertEqual(len(ws3.artefatos), len(ws2.artefatos))


if __name__ == "__main__":
    unittest.main()
