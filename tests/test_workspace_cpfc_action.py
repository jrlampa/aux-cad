# -*- coding: utf-8 -*-
"""
Suíte de Testes Unitários da Integração Workspace x CPFC.
Testa a validação estrita, montagem de comando, propagação de metadados via JSON de intercâmbio,
despacho não-bloqueante e detecção do artefato pelo WorkspaceScanner.
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
def mock_workspace_cpfc(tmp_path):
    """Cria um workspace mockado válido para testes de CPFC."""
    sob_id = "A057032667"
    root = tmp_path / f"SOB_{sob_id}"
    root.mkdir()

    return ProjectWorkspace(
        sob_id=sob_id,
        sob_name=f"SOB_{sob_id}",
        root_dir=root,
        base_sigla="PE",
        metadados={
            "municipio": "São Gonçalo",
            "endereco": "Rua Yolanda Saad Abuzaid 150",
        },
    )


class TestWorkspaceCpfcAction:
    """Testes de contrato e despacho da ação CPFC no WorkspaceActionDispatcher."""

    def test_comando_valido_sem_metadados_adicionais(self, tmp_path):
        """Teste 1 — Workspace válido sem metadados opcionais gera comando com root_dir e sob_id."""
        root = tmp_path / "SOB_A012345678"
        root.mkdir()
        ws = ProjectWorkspace(
            sob_id="A012345678",
            sob_name="SOB_A012345678",
            root_dir=root,
            metadados={},
        )

        cmd = WorkspaceActionDispatcher.montar_comando_cpfc(ws)

        assert isinstance(cmd, list)
        assert len(cmd) == 4
        assert cmd[0] == sys.executable
        assert "cpfc_manager.py" in cmd[1]
        assert cmd[2] == str(root)
        assert cmd[3] == "A012345678"

    def test_workspace_ausente(self):
        """Teste 2 — Workspace ausente (None) deve gerar erro controlado (ValueError)."""
        with pytest.raises(ValueError, match="sob_id obrigatório ausente"):
            WorkspaceActionDispatcher.montar_comando_cpfc(None)

    def test_sob_ausente_ou_vazia(self, tmp_path):
        """Teste 3 — Workspace sem sob_id ou com sob_id vazio deve gerar erro controlado."""
        root = tmp_path / "SOB_SEM_ID"
        root.mkdir()

        ws_sem_sob = ProjectWorkspace(
            sob_id="",
            sob_name="SOB_SEM_ID",
            root_dir=root,
        )
        with pytest.raises(ValueError, match="sob_id obrigatório ausente|não pode ser vazio"):
            WorkspaceActionDispatcher.montar_comando_cpfc(ws_sem_sob)

        ws_espacos = ProjectWorkspace(
            sob_id="   ",
            sob_name="SOB_VAZIA",
            root_dir=root,
        )
        with pytest.raises(ValueError, match="não pode ser vazio"):
            WorkspaceActionDispatcher.montar_comando_cpfc(ws_espacos)

    def test_metadados_propagados_via_json(self, mock_workspace_cpfc):
        """Teste 4 — Quando presentes, municipio e endereco devem ser propagados via JSON."""
        cmd = WorkspaceActionDispatcher.montar_comando_cpfc(mock_workspace_cpfc)

        assert isinstance(cmd, list)
        assert len(cmd) == 3
        assert cmd[0] == sys.executable
        assert "cpfc_manager.py" in cmd[1]

        json_path = Path(cmd[2])
        assert json_path.exists(), "O arquivo JSON de intercâmbio temporário deve existir."
        assert json_path.suffix == ".json"

        conteudo = json.loads(json_path.read_text(encoding="utf-8"))
        assert conteudo["projeto"] == "A057032667"
        assert conteudo["pasta_destino"] == str(mock_workspace_cpfc.root_dir)
        assert conteudo["municipio"] == "São Gonçalo"
        assert conteudo["endereco"] == "Rua Yolanda Saad Abuzaid 150"

        # Limpeza do arquivo temporário gerado no teste
        try:
            json_path.unlink()
        except OSError:
            pass

    def test_ausencia_metadados_opcionais_nao_quebra_execucao(self, tmp_path):
        """Teste 5 — Ausência de municipio e endereco não quebra a execução e usa fallback posicional."""
        root = tmp_path / "SOB_A999"
        root.mkdir()
        ws = ProjectWorkspace(
            sob_id="A999888777",
            sob_name="SOB_A999888777",
            root_dir=root,
            metadados=None,
        )

        cmd = WorkspaceActionDispatcher.montar_comando_cpfc(ws)
        assert isinstance(cmd, list)
        assert len(cmd) == 4
        assert cmd[2] == str(root)
        assert cmd[3] == "A999888777"

    def test_executar_cpfc_despacho_nao_bloqueante(self, mock_workspace_cpfc):
        """Teste 6 — Validar que executar_cpfc() utiliza Popen com cwd esperado sem bloquear."""
        mock_proc = MagicMock(spec=subprocess.Popen)
        with patch.object(WorkspaceActionDispatcher, "_lancar_processo", return_value=mock_proc) as mock_lancar:
            proc = WorkspaceActionDispatcher.executar_cpfc(mock_workspace_cpfc)
            assert proc == mock_proc
            mock_lancar.assert_called_once()

            args, kwargs = mock_lancar.call_args
            cmd_enviado = args[0]
            assert "cpfc_manager.py" in cmd_enviado[1]
            assert "cwd" in kwargs

    def test_scanner_detecta_artefato_cpfc(self, tmp_path):
        """Teste 7 — WorkspaceScanner detecta planilha CPFC com nomenclatura oficial."""
        sob_id = "A057032667"
        root = tmp_path / f"SOB_{sob_id}"
        root.mkdir()

        # Nomenclatura oficial gerada pelo CPFC: PE_{projeto}_CPFC_REN1.059.xlsx
        planilha_cpfc = root / f"PE_{sob_id}_CPFC_REN1.059.xlsx"
        planilha_cpfc.write_bytes(b"MOCK_EXCEL_BYTES")

        ws = WorkspaceScanner.scan(root)
        assert ws is not None
        assert "CPFC" in ws.artefatos
        art_cpfc = ws.artefatos["CPFC"]
        assert art_cpfc.status == ArtifactStatus.EXISTE
        assert art_cpfc.caminho == planilha_cpfc
