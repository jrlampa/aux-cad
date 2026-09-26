# -*- coding: utf-8 -*-
"""
Suíte de Testes Unitários da Integração Workspace x Orçamento.
Valida o contrato estrito entre ProjectWorkspace e orcamento_manager.py:
1. Validação de workspace válido e rejeição de sob_id ausente/vazio.
2. workspace.sob_id como única fonte do argumento --projeto.
3. Propagação contextual de município quando disponível em workspace.metadados.
4. Ausência de município não adiciona --municipio e não quebra execução.
5. Preservação integral do JSON de engenharia CAD (--json) sem criar JSON temporário de metadados.
6. Despacho não-bloqueante via subprocess.Popen.
7. Detecção do artefato pelo WorkspaceScanner.
"""

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest

from workspace.workspace_core import ArtifactStatus, ProjectWorkspace
from workspace.workspace_actions import WorkspaceActionDispatcher
from workspace.workspace_scanner import WorkspaceScanner


@pytest.fixture
def mock_workspace_orcamento(tmp_path):
    """Cria um workspace mockado válido para testes de Orçamento."""
    sob_id = "A057349839"
    root = tmp_path / f"SOB_{sob_id}"
    root.mkdir()

    return ProjectWorkspace(
        sob_id=sob_id,
        sob_name=f"SOB_{sob_id}",
        root_dir=root,
        base_sigla="PE",
        metadados={
            "municipio": "São Gonçalo",
        },
    )


class TestWorkspaceOrcamentoAction:
    """Testes de contrato e despacho da ação Orçamento no WorkspaceActionDispatcher."""

    def test_01_comando_valido_basico(self, tmp_path):
        """Teste 1 — Workspace válido produz comando padrão com sys.executable, orcamento_manager e --projeto."""
        root = tmp_path / "SOB_A012345678"
        root.mkdir()
        ws = ProjectWorkspace(
            sob_id="A012345678",
            sob_name="SOB_A012345678",
            root_dir=root,
            metadados={},
        )

        cmd = WorkspaceActionDispatcher.montar_comando_orcamento(ws)

        assert isinstance(cmd, list)
        assert cmd[0] == sys.executable
        assert "orcamento_manager.py" in cmd[1]
        assert "--projeto" in cmd
        assert cmd[cmd.index("--projeto") + 1] == "A012345678"
        # Sem metadados opcionais, não deve propagar --municipio nem --projetista
        assert "--municipio" not in cmd
        assert "--projetista" not in cmd
        assert "--no-gui" not in cmd

    def test_02_workspace_ausente_gera_erro_controlado(self):
        """Teste 2 — Workspace ausente (None) deve gerar ValueError controlado."""
        with pytest.raises(ValueError, match="sob_id obrigatório ausente"):
            WorkspaceActionDispatcher.montar_comando_orcamento(None)

    def test_03_sob_invalida_ou_vazia(self, tmp_path):
        """Teste 3 — Workspace com sob_id ausente, vazio ou espaços deve gerar ValueError."""
        root = tmp_path / "SOB_INVALIDA"
        root.mkdir()

        ws_sem_sob = ProjectWorkspace(
            sob_id="",
            sob_name="SOB_SEM_ID",
            root_dir=root,
        )
        with pytest.raises(ValueError, match="sob_id obrigatório ausente|não pode ser vazio"):
            WorkspaceActionDispatcher.montar_comando_orcamento(ws_sem_sob)

        ws_espacos = ProjectWorkspace(
            sob_id="   ",
            sob_name="SOB_ESPACOS",
            root_dir=root,
        )
        with pytest.raises(ValueError, match="não pode ser vazio"):
            WorkspaceActionDispatcher.montar_comando_orcamento(ws_espacos)

    def test_04_propagacao_municipio(self, mock_workspace_orcamento):
        """Teste 4 — Município presente em workspace.metadados deve ser repassado via --municipio."""
        cmd = WorkspaceActionDispatcher.montar_comando_orcamento(mock_workspace_orcamento)

        assert "--municipio" in cmd
        assert cmd[cmd.index("--municipio") + 1] == "São Gonçalo"
        # Projetista NÃO deve ser propagado
        assert "--projetista" not in cmd

    def test_05_ausencia_municipio_nao_quebra_execucao(self, tmp_path):
        """Teste 5 — Ausência de município não quebra a execução e não injeta flag --municipio."""
        root = tmp_path / "SOB_A999"
        root.mkdir()
        ws = ProjectWorkspace(
            sob_id="A999888777",
            sob_name="SOB_A999888777",
            root_dir=root,
            metadados=None,
        )

        cmd = WorkspaceActionDispatcher.montar_comando_orcamento(ws)
        assert "--municipio" not in cmd
        assert "--projeto" in cmd
        assert cmd[cmd.index("--projeto") + 1] == "A999888777"

    def test_06_json_cad_engenharia_preservado(self, mock_workspace_orcamento, tmp_path):
        """Teste 6 — JSON de entidades de engenharia CAD é encaminhado via --json sem ser modificado."""
        # Caso 6A: JSON explícito
        fake_cad_json = tmp_path / "custom_cad.json"
        fake_cad_json.write_text('{"postes": [], "cabos": []}', encoding="utf-8")

        cmd_explicit = WorkspaceActionDispatcher.montar_comando_orcamento(
            mock_workspace_orcamento, dados_json=fake_cad_json
        )
        assert "--json" in cmd_explicit
        assert cmd_explicit[cmd_explicit.index("--json") + 1] == str(fake_cad_json)

        # Caso 6B: JSON detectado na raiz da SOB (orcamento_dados.json)
        auto_json = mock_workspace_orcamento.root_dir / "orcamento_dados.json"
        auto_json.write_text('{"postes": [{"id": "P1"}]}', encoding="utf-8")

        cmd_auto = WorkspaceActionDispatcher.montar_comando_orcamento(mock_workspace_orcamento)
        assert "--json" in cmd_auto
        assert cmd_auto[cmd_auto.index("--json") + 1] == str(auto_json)

    def test_07_despacho_nao_bloqueante(self, mock_workspace_orcamento):
        """Teste 7 — executar_orcamento() dispara subprocesso desacoplado via Popen com cwd esperado."""
        mock_proc = MagicMock(spec=subprocess.Popen)
        with patch.object(WorkspaceActionDispatcher, "_lancar_processo", return_value=mock_proc) as mock_lancar:
            proc = WorkspaceActionDispatcher.executar_orcamento(mock_workspace_orcamento)
            assert proc == mock_proc
            mock_lancar.assert_called_once()

            args, kwargs = mock_lancar.call_args
            cmd_enviado = args[0]
            assert "orcamento_manager.py" in cmd_enviado[1]
            assert "--projeto" in cmd_enviado
            assert "A057349839" in cmd_enviado
            assert "cwd" in kwargs

    def test_08_scanner_detecta_artefato_orcamento(self, tmp_path):
        """Teste 8 — WorkspaceScanner detecta planilha oficial de orçamento gerada na raiz da SOB."""
        sob_id = "A057349839"
        root = tmp_path / f"SOB_{sob_id}"
        root.mkdir()

        planilha_orc = root / f"ORCAMENTO_{sob_id}.xlsx"
        planilha_orc.write_bytes(b"MOCK_ORCAMENTO_EXCEL")

        ws = WorkspaceScanner.scan(root)
        assert ws is not None
        assert "ORCAMENTO" in ws.artefatos
        art_orc = ws.artefatos["ORCAMENTO"]
        assert art_orc.status == ArtifactStatus.EXISTE
        assert art_orc.caminho == planilha_orc
