# -*- coding: utf-8 -*-
"""
Suíte de Testes da Integração de Ações — OXCAD 0.3.0.
Valida o despacho de ações via WorkspaceActionDispatcher:
1. Ação CQT;
2. Ação Orçamento;
3. Ação CPFC;
4. Ação Ambiental;
5. Ação AutoPrancha;
6. Ação Preparar SOB;
7. Ação Abrir artefato existente e inexistente;
8. Ação Localizar no Explorer;
9. Tratamento estrito do Unifilar (indicação de interação no AutoCAD);
10. Tratamento de ação desconhecida (Requer especificação);
11. Execução via CLI headless (--acao e --alvo);
12. Ausência de bloqueio ou Tkinter no despacho headless.
"""

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = ROOT_DIR / "workspace"
CLI_PATH = WORKSPACE_DIR / "workspace_context_cli.py"


def _vincular_dwg(dwg: Path) -> str:
    sob_id = "A057349839"
    (dwg.parent / ".sob_state.json").write_text(
        json.dumps({
            "sob_id": sob_id, "status": "CONCLUÍDO", "base_dwg": str(dwg)
        }), encoding="utf-8",
    )
    return sob_id


# ==============================================================================
# 1. Testes de Execução das Ações via executar_acao_operacional
# ==============================================================================

@patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_cqt")
def test_acao_cqt_executa_via_dispatcher(mock_cqt, tmp_path):
    """Valida despacho da ação CQT para o WorkspaceActionDispatcher."""
    from workspace.workspace_context_cli import _executar_acao_operacional_impl

    mock_proc = MagicMock()
    mock_proc.pid = 1111
    mock_cqt.return_value = mock_proc

    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy")

    res = _executar_acao_operacional_impl(
        "cqt", dwg_path=str(dwg), sob_id_esperada=_vincular_dwg(dwg)
    )

    assert res["sucesso"] is True
    assert res["acao"] == "cqt"
    assert res["estado"] == "Executando..."
    assert res["pid"] == 1111
    assert "CQT" in res["mensagem"]
    mock_cqt.assert_called_once()


@patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_orcamento")
def test_acao_orcamento_executa_via_dispatcher(mock_orc, tmp_path):
    """Valida despacho da ação Orçamento para o WorkspaceActionDispatcher."""
    from workspace.workspace_context_cli import _executar_acao_operacional_impl

    mock_proc = MagicMock()
    mock_proc.pid = 2222
    mock_orc.return_value = mock_proc

    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy")

    res = _executar_acao_operacional_impl(
        "orcamento", dwg_path=str(dwg), sob_id_esperada=_vincular_dwg(dwg)
    )

    assert res["sucesso"] is True
    assert res["acao"] == "orcamento"
    assert res["pid"] == 2222
    assert "Orçamento" in res["mensagem"]
    mock_orc.assert_called_once()


@patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_cpfc")
def test_acao_cpfc_executa_via_dispatcher(mock_cpfc, tmp_path):
    """Valida despacho da ação CPFC para o WorkspaceActionDispatcher."""
    from workspace.workspace_context_cli import _executar_acao_operacional_impl

    mock_proc = MagicMock()
    mock_proc.pid = 3333
    mock_cpfc.return_value = mock_proc

    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy")

    res = _executar_acao_operacional_impl(
        "cpfc", dwg_path=str(dwg), sob_id_esperada=_vincular_dwg(dwg)
    )

    assert res["sucesso"] is True
    assert res["acao"] == "cpfc"
    assert res["pid"] == 3333
    assert "CPFC" in res["mensagem"]
    mock_cpfc.assert_called_once()


@patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_ambiental")
def test_acao_ambiental_executa_via_dispatcher(mock_amb, tmp_path):
    """Valida despacho da ação Ambiental para o WorkspaceActionDispatcher."""
    from workspace.workspace_context_cli import _executar_acao_operacional_impl

    mock_proc = MagicMock()
    mock_proc.pid = 4444
    mock_amb.return_value = mock_proc

    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy")

    res = _executar_acao_operacional_impl(
        "ambiental", dwg_path=str(dwg), sob_id_esperada=_vincular_dwg(dwg)
    )

    assert res["sucesso"] is True
    assert res["acao"] == "ambiental"
    assert res["pid"] == 4444
    assert "Ambiental" in res["mensagem"]
    mock_amb.assert_called_once()


@patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_prancha")
def test_acao_prancha_executa_via_dispatcher(mock_prancha, tmp_path):
    """Valida despacho da ação AutoPrancha para o WorkspaceActionDispatcher."""
    from workspace.workspace_context_cli import _executar_acao_operacional_impl

    mock_proc = MagicMock()
    mock_proc.pid = 5555
    mock_prancha.return_value = mock_proc

    pasta_sob = tmp_path / "SOB_A057349839"
    pasta_sob.mkdir()
    dwg = pasta_sob / "PE_A057349839_DESENHO.dwg"
    dwg.write_text("dummy")

    res = _executar_acao_operacional_impl(
        "prancha", dwg_path=str(dwg), sob_id_esperada=_vincular_dwg(dwg)
    )

    assert res["sucesso"] is True
    assert res["acao"] == "prancha"
    assert res["pid"] == 5555
    assert "AutoPranche" in res["mensagem"]
    mock_prancha.assert_called_once()


@patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_sob")
def test_acao_sob_executa_via_dispatcher(mock_sob, tmp_path):
    """Valida despacho da ação Preparar SOB para o WorkspaceActionDispatcher."""
    from workspace.workspace_context_cli import executar_acao_operacional

    mock_proc = MagicMock()
    mock_proc.pid = 6666
    mock_sob.return_value = mock_proc

    res = executar_acao_operacional("sob", root_dir=str(tmp_path))

    assert res["sucesso"] is True
    assert res["acao"] == "sob"
    assert res["pid"] == 6666
    assert "Preparador de SOB" in res["mensagem"]
    mock_sob.assert_called_once()


@patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_sob")
def test_acao_sob_concluida_com_manifesto_valido_nao_gera_artifact_not_verified(mock_sob, tmp_path):
    """Requisito F: sob com sucesso + manifesto concluído -> não gerar ARTIFACT_NOT_VERIFIED."""
    from workspace.workspace_context_cli import executar_acao_operacional

    mock_proc = MagicMock()
    mock_proc.pid = 7777
    mock_proc.wait.return_value = 0

    pasta_sob = tmp_path / "A057526153"
    pasta_sob.mkdir()
    dwg = pasta_sob / "A057526153.dwg"
    dwg.write_text("dummy dwg content", encoding="utf-8")
    manifesto = pasta_sob / ".sob_state.json"
    manifesto.write_text(
        json.dumps({
            "status": "CONCLUÍDO",
            "sob_id": "A057526153",
            "base_dwg": str(dwg),
        }),
        encoding="utf-8",
    )

    def _fake_executar_sob(*args, **kwargs):
        res_json = kwargs.get("resultado_json")
        if res_json:
            Path(res_json).write_text(json.dumps({
                "sucesso": True,
                "status": "CONCLUÍDO",
                "SOB_ID": "A057526153",
                "SOB_ROOT": str(pasta_sob),
                "BASE_DWG": str(dwg),
                "manifesto_path": str(manifesto),
            }), encoding="utf-8")
        return mock_proc

    mock_sob.side_effect = _fake_executar_sob

    res = executar_acao_operacional(
        "sob",
        root_dir=str(tmp_path),
        sob_id_esperada="A057526153",
        wait_for_completion=True,
    )

    assert res["sucesso"] is True
    assert res["estado"] == "Concluído"
    assert res["exit_code"] == 0
    assert res["erro"] is None
    assert "entregável verificado" in res["mensagem"]


@patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_sob")
def test_acao_sob_exit_code_diferente_de_zero_falha(mock_sob, tmp_path):
    """Requisito G: sob com exit code diferente de zero -> continuar sendo falha."""
    from workspace.workspace_context_cli import executar_acao_operacional

    mock_proc = MagicMock()
    mock_proc.pid = 8888
    mock_proc.wait.return_value = 1
    mock_sob.return_value = mock_proc

    res = executar_acao_operacional(
        "sob",
        root_dir=str(tmp_path),
        wait_for_completion=True,
    )

    assert res["sucesso"] is False
    assert res["estado"] == "Falhou"
    assert res["exit_code"] == 1
    assert "Exit code 1" in (res.get("erro") or "")


@patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_sob")
def test_acao_sob_exit_zero_sem_manifesto_gera_artifact_not_verified(mock_sob, tmp_path):
    """Valida que exit code 0 sem evidências válidas resulta em ARTIFACT_NOT_VERIFIED."""
    from workspace.workspace_context_cli import executar_acao_operacional

    mock_proc = MagicMock()
    mock_proc.pid = 9999
    mock_proc.wait.return_value = 0
    mock_sob.return_value = mock_proc

    res = executar_acao_operacional(
        "sob",
        root_dir=str(tmp_path),
        sob_id_esperada="A057999999",
        wait_for_completion=True,
    )

    assert res["sucesso"] is False
    assert res["estado"] == "Falhou"
    assert res["exit_code"] == 0
    assert res["erro"] == "ARTIFACT_NOT_VERIFIED"


# ==============================================================================
# 2. Teste da Ação Unifilar (Interação Necessária no AutoCAD)
# ==============================================================================

def test_acao_unifilar_indica_interacao_autocad():
    """Valida que o Unifilar não é executado cegamente em subprocesso."""
    from workspace.workspace_context_cli import executar_acao_operacional

    res = executar_acao_operacional("unifilar")

    assert res["sucesso"] is False
    assert res["acao"] == "unifilar"
    assert res["estado"] == "Requer especificação"
    assert res["erro"] == "DWG_CONTEXT_NOT_VERIFIED"
    assert res["pid"] is None


# ==============================================================================
# 3. Testes de Abrir Artefato e Localizar no Explorer
# ==============================================================================

@patch("workspace.workspace_actions.WorkspaceActionDispatcher.abrir_artefato")
def test_acao_abrir_artefato_existente(mock_abrir, tmp_path):
    """Valida abertura de artefato existente via SO."""
    from workspace.workspace_context_cli import executar_acao_operacional

    mock_abrir.return_value = True
    arquivo = tmp_path / "CQT_A057349839.xlsm"
    arquivo.write_text("dummy")

    res = executar_acao_operacional("abrir", alvo=str(arquivo))

    assert res["sucesso"] is True
    assert res["estado"] == "Concluído"
    assert "CQT_A057349839.xlsm" in res["mensagem"]
    mock_abrir.assert_called_once()


def test_acao_abrir_artefato_inexistente():
    """Valida tratamento seguro ao tentar abrir artefato inexistente."""
    from workspace.workspace_context_cli import executar_acao_operacional

    res = executar_acao_operacional("abrir", alvo="C:\\nao_existe_arquivo_1234.xyz")

    assert res["sucesso"] is False
    assert res["estado"] == "Falhou"
    assert "não encontrado" in res["mensagem"]


@patch("workspace.workspace_actions.WorkspaceActionDispatcher.localizar_artefato")
def test_acao_localizar_artefato(mock_localizar, tmp_path):
    """Valida localização de pasta ou artefato no Explorer."""
    from workspace.workspace_context_cli import executar_acao_operacional

    mock_localizar.return_value = True
    res = executar_acao_operacional("localizar", alvo=str(tmp_path))

    assert res["sucesso"] is True
    assert res["estado"] == "Concluído"
    mock_localizar.assert_called_once()


# ==============================================================================
# 4. Ação Desconhecida / Requer Especificação
# ==============================================================================

def test_acao_desconhecida_retorna_requer_especificacao():
    """Valida tratamento de ação não homologada."""
    from workspace.workspace_context_cli import executar_acao_operacional

    res = executar_acao_operacional("acao_inexistente_xyz")

    assert res["sucesso"] is False
    assert res["estado"] == "Requer especificação"
    assert "não homologada" in res["mensagem"]


# ==============================================================================
# 5. Testes de Execução CLI com --acao e --alvo
# ==============================================================================

def test_cli_executa_acao_unifilar():
    """Valida execução da ação unifilar via processo CLI com retorno JSON."""
    cmd = [sys.executable, str(CLI_PATH), "--acao", "unifilar"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    assert proc.returncode == 1
    dados = json.loads(proc.stdout)
    assert dados["acao"] == "unifilar"
    assert dados["estado"] == "Requer especificação"
    assert dados["erro"] == "DWG_CONTEXT_NOT_VERIFIED"


def test_cli_executa_acao_abrir_inexistente():
    """Valida execução da ação abrir com alvo inexistente via CLI."""
    cmd = [sys.executable, str(CLI_PATH), "--acao", "abrir", "--alvo", "C:\\NaoExiste.dwg"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    assert proc.returncode == 1
    dados = json.loads(proc.stdout)
    assert dados["estado"] == "Falhou"
    assert "não encontrado" in dados["mensagem"]
