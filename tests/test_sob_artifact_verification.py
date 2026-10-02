# -*- coding: utf-8 -*-
"""
test_sob_artifact_verification.py - Testes unitários e integrados cobrindo
rigorosamente os 7 cenários obrigatórios de atestação física do artefato da ação SOB:
A. SOB concluída + caminho explícito correto -> artefato verificado.
B. Caminho inexistente -> ARTIFACT_NOT_VERIFIED.
C. Manifesto de outra SOB no diretório histórico -> NÃO pode ser aceito.
D. Status diferente de CONCLUÍDO -> rejeitar.
E. base_dwg inexistente ou diferente -> rejeitar.
F. exit_code=0 sem artefato verificável -> rejeitar.
G. Caminho explícito contendo espaços -> funcionar.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from workspace.workspace_context_cli import (
    _artefato_sob_gerado,
    executar_acao_operacional,
)


def _criar_sob_cenario(
    pasta_sob: Path,
    sob_id: str = "A057526153",
    status: str = "CONCLUÍDO",
    dwg_valido: bool = True,
    dwg_conteudo: str = "dwg mock data",
    base_dwg_relativo: bool = False,
    apenas_manifesto: bool = False,
) -> Path:
    """Helper para criar uma estrutura de SOB com manifesto e DWG para testes."""
    pasta_sob.mkdir(parents=True, exist_ok=True)
    dwg_path = pasta_sob / f"{sob_id}.dwg"
    if dwg_valido:
        dwg_path.write_text(dwg_conteudo, encoding="utf-8")
    elif not apenas_manifesto:
        # Cria arquivo vazio se dwg não for válido mas não for para omitir
        dwg_path.write_text("", encoding="utf-8")

    manifesto_path = pasta_sob / ".sob_state.json"
    manifesto_dados = {
        "status": status,
        "sob_id": sob_id,
        "base_dwg": f"{sob_id}.dwg" if base_dwg_relativo else str(dwg_path),
    }
    manifesto_path.write_text(
        json.dumps(manifesto_dados, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifesto_path


def test_cenario_a_sob_concluida_caminho_explicito_verificado(tmp_path: Path):
    """Cenário A: SOB concluída + caminho explícito correto -> artefato verificado."""
    pasta = tmp_path / "SOB_A057526153"
    _criar_sob_cenario(pasta, sob_id="A057526153", status="CONCLUÍDO", dwg_valido=True)

    # 1. Via caminho explícito apontando para o diretório
    assert _artefato_sob_gerado(
        caminho_explicito=pasta,
        sob_id_esperada="A057526153",
    ) is True

    # 2. Via caminho explícito apontando diretamente para .sob_state.json
    assert _artefato_sob_gerado(
        caminho_explicito=pasta / ".sob_state.json",
        sob_id_esperada="A057526153",
    ) is True

    # 3. Via arquivo de resultado estruturado (resultado_json)
    res_file = tmp_path / "resultado_execucao.json"
    res_file.write_text(
        json.dumps({
            "sucesso": True,
            "status": "CONCLUÍDO",
            "SOB_ID": "A057526153",
            "SOB_ROOT": str(pasta),
            "manifesto_path": str(pasta / ".sob_state.json"),
        }),
        encoding="utf-8",
    )
    assert _artefato_sob_gerado(
        resultado_json=res_file,
        sob_id_esperada="A057526153",
    ) is True


def test_cenario_b_caminho_inexistente_retorna_artifact_not_verified(tmp_path: Path):
    """Cenário B: Caminho inexistente -> ARTIFACT_NOT_VERIFIED."""
    caminho_fantasma = tmp_path / "nao_existe_pasta_xyz"
    assert _artefato_sob_gerado(
        caminho_explicito=caminho_fantasma,
        sob_id_esperada="A057526153",
    ) is False

    # Na execução operacional, resulta em ARTIFACT_NOT_VERIFIED
    with patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_sob") as mock_sob:
        mock_proc = MagicMock()
        mock_proc.pid = 1111
        mock_proc.wait.return_value = 0
        mock_sob.return_value = mock_proc

        res = executar_acao_operacional(
            "sob",
            root_dir=str(tmp_path),
            sob_id_esperada="A057526153",
            wait_for_completion=True,
            caminho_explicito_sob=caminho_fantasma,
        )

        assert res["sucesso"] is False
        assert res["erro"] == "ARTIFACT_NOT_VERIFIED"


def test_cenario_c_manifesto_outra_sob_diretorio_historico_rejeitado(tmp_path: Path):
    """Cenário C: Manifesto de outra SOB no diretório histórico -> NÃO pode ser aceito."""
    pasta_historica = tmp_path / "HISTORICO" / "SOB_A057999999"
    _criar_sob_cenario(pasta_historica, sob_id="A057999999", status="CONCLUÍDO", dwg_valido=True)

    # Esperamos SOB A057526153, mas o caminho aponta para A057999999 -> DEVE REJEITAR
    assert _artefato_sob_gerado(
        caminho_explicito=pasta_historica,
        sob_id_esperada="A057526153",
    ) is False

    # Mesmo com resultado_json apontando para a SOB errada -> DEVE REJEITAR
    res_file = tmp_path / "resultado_antigo.json"
    res_file.write_text(
        json.dumps({
            "sucesso": True,
            "status": "CONCLUÍDO",
            "SOB_ID": "A057999999",
            "SOB_ROOT": str(pasta_historica),
            "manifesto_path": str(pasta_historica / ".sob_state.json"),
        }),
        encoding="utf-8",
    )
    assert _artefato_sob_gerado(
        resultado_json=res_file,
        sob_id_esperada="A057526153",
    ) is False


def test_cenario_d_status_diferente_de_concluido_rejeitado(tmp_path: Path):
    """Cenário D: Status diferente de CONCLUÍDO -> rejeitar."""
    for st in ["INICIADO", "FALHA", "BLOQUEADO", "EM_ANDAMENTO", ""]:
        pasta = tmp_path / f"SOB_STATUS_{st or 'VAZIO'}"
        _criar_sob_cenario(pasta, sob_id="A057526153", status=st, dwg_valido=True)

        assert _artefato_sob_gerado(
            caminho_explicito=pasta,
            sob_id_esperada="A057526153",
        ) is False


def test_cenario_e_base_dwg_inexistente_ou_diferente_rejeitado(tmp_path: Path):
    """Cenário E: base_dwg inexistente, vazio ou fora da pasta -> rejeitar."""
    # E1: DWG inexistente
    pasta_sem_dwg = tmp_path / "SOB_SEM_DWG"
    _criar_sob_cenario(pasta_sem_dwg, sob_id="A057526153", status="CONCLUÍDO", dwg_valido=False, apenas_manifesto=True)
    assert _artefato_sob_gerado(caminho_explicito=pasta_sem_dwg, sob_id_esperada="A057526153") is False

    # E2: DWG com tamanho zero (0 bytes)
    pasta_dwg_vazio = tmp_path / "SOB_DWG_VAZIO"
    _criar_sob_cenario(pasta_dwg_vazio, sob_id="A057526153", status="CONCLUÍDO", dwg_valido=False, dwg_conteudo="")
    assert _artefato_sob_gerado(caminho_explicito=pasta_dwg_vazio, sob_id_esperada="A057526153") is False

    # E3: DWG apontando para fora da pasta da SOB
    pasta_invalida = tmp_path / "SOB_EXTERNA"
    pasta_invalida.mkdir()
    dwg_fora = tmp_path / "outro_lugar.dwg"
    dwg_fora.write_text("conteudo", encoding="utf-8")
    man = pasta_invalida / ".sob_state.json"
    man.write_text(json.dumps({
        "status": "CONCLUÍDO",
        "sob_id": "A057526153",
        "base_dwg": str(dwg_fora),
    }), encoding="utf-8")
    assert _artefato_sob_gerado(caminho_explicito=pasta_invalida, sob_id_esperada="A057526153") is False


def test_cenario_f_exit_code_zero_sem_artefato_verificavel_rejeitado(tmp_path: Path):
    """Cenário F: exit_code=0 sem artefato verificável -> rejeitar."""
    # Sem caminho explícito e sem resultado_json
    assert _artefato_sob_gerado() is False

    with patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_sob") as mock_sob:
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_proc.wait.return_value = 0
        mock_sob.return_value = mock_proc

        res = executar_acao_operacional(
            "sob",
            root_dir=str(tmp_path),
            sob_id_esperada="A057526153",
            wait_for_completion=True,
            # Não passa caminho_explicito_sob e mock não grava resultado_json
        )

        assert res["sucesso"] is False
        assert res["estado"] == "Falhou"
        assert res["exit_code"] == 0
        assert res["erro"] == "ARTIFACT_NOT_VERIFIED"


def test_cenario_g_caminho_explicito_com_espacos_funciona(tmp_path: Path):
    """Cenário G: Caminho explícito contendo espaços -> funcionar."""
    pasta_com_espacos = tmp_path / "Projetos Em Andamento Com Espacos" / "SOB A057526153 Final"
    _criar_sob_cenario(pasta_com_espacos, sob_id="A057526153", status="CONCLUÍDO", dwg_valido=True)

    # 1. Validação física direta
    assert _artefato_sob_gerado(
        caminho_explicito=pasta_com_espacos,
        sob_id_esperada="A057526153",
    ) is True

    # 2. Validação via execução operacional
    with patch("workspace.workspace_actions.WorkspaceActionDispatcher.executar_sob") as mock_sob:
        mock_proc = MagicMock()
        mock_proc.pid = 3333
        mock_proc.wait.return_value = 0

        def _fake_exec(*args, **kwargs):
            res_file = kwargs.get("resultado_json")
            if res_file:
                Path(res_file).write_text(json.dumps({
                    "sucesso": True,
                    "status": "CONCLUÍDO",
                    "SOB_ID": "A057526153",
                    "SOB_ROOT": str(pasta_com_espacos),
                    "BASE_DWG": str(pasta_com_espacos / "A057526153.dwg"),
                    "manifesto_path": str(pasta_com_espacos / ".sob_state.json"),
                }), encoding="utf-8")
            return mock_proc

        mock_sob.side_effect = _fake_exec

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
