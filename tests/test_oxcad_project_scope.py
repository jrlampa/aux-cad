import json
from pathlib import Path

from workspace.workspace_context_cli import (
    _resolver_project_scope, executar_acao_operacional,
    extrair_contexto_operacional,
)


def _scope_local(dwg: Path, sob_id: str | None):
    return _resolver_project_scope(dwg.parent, str(dwg), sob_id)


def _criar_sob(root: Path, sob_id: str, dwg_name: str | None = None) -> Path:
    root.mkdir(parents=True)
    dwg = root / (dwg_name or f"PE_{sob_id}_DESENHO.dwg")
    dwg.write_bytes(b"DWG")
    (root / ".sob_state.json").write_text(
        json.dumps({
            "sob_id": sob_id,
            "status": "CONCLUÍDO",
            "base_dwg": str(dwg),
        }),
        encoding="utf-8",
    )
    return dwg


def test_dwg_vinculado_a_uma_sob_unica_e_resolvido(tmp_path: Path):
    sob_id = "A057349839"
    dwg = _criar_sob(tmp_path / f"SOB_{sob_id}", sob_id)

    contexto = extrair_contexto_operacional(
        dwg_path=str(dwg),
        sob_id_esperada=sob_id,
        require_project_scope=True,
    )

    assert _scope_local(dwg, sob_id)["status"] == "Bound"
    assert contexto["project_scope_status"] == "Unverified"
    assert contexto["project_scope_resolved"] is False
    assert contexto["erro"] == "DWG_CONTEXT_NOT_VERIFIED"


def test_dwg_sem_vinculo_nao_usa_nome_ou_caminho(tmp_path: Path):
    sob_id = "A057349839"
    dwg = tmp_path / f"PE_{sob_id}_DESENHO.dwg"
    dwg.write_bytes(b"DWG")

    contexto = extrair_contexto_operacional(
        dwg_path=str(dwg),
        require_project_scope=True,
    )

    assert contexto["project_scope_status"] == "Unverified"
    assert contexto["project_scope_resolved"] is False
    assert contexto["status"] == "Contexto DWG não verificado"
    assert contexto["artefatos"] == []


def test_identidade_vinculada_conflitante_com_manifesto_e_ambigua(tmp_path: Path):
    dwg = tmp_path / "layout.dwg"
    dwg.write_bytes(b"DWG")
    (tmp_path / ".sob_state.json").write_text(
        json.dumps({
            "sob_id": "B123456789",
            "status": "CONCLUÍDO",
            "base_dwg": str(dwg),
        }),
        encoding="utf-8",
    )

    contexto = extrair_contexto_operacional(
        dwg_path=str(dwg),
        sob_id_esperada="A057349839",
        require_project_scope=True,
    )

    assert _scope_local(dwg, "A057349839")["status"] == "Ambiguous"
    assert contexto["project_scope_status"] == "Unverified"
    assert contexto["project_scope_resolved"] is False
    assert contexto["artefatos"] == []


def test_duas_sobs_candidatas_bloqueiam_resolucao_automatica(tmp_path: Path):
    sob_id = "A057349839"
    dwg = _criar_sob(tmp_path / f"SOB_{sob_id}", sob_id)
    (dwg.parent / "PE_B123456789_DESENHO.dwg").write_bytes(b"DWG")

    contexto = extrair_contexto_operacional(
        dwg_path=str(dwg),
        sob_id_esperada=sob_id,
        require_project_scope=True,
    )

    assert _scope_local(dwg, sob_id)["status"] == "Ambiguous"
    assert contexto["project_scope_status"] == "Unverified"
    assert contexto["project_scope_resolved"] is False
    assert contexto["artefatos"] == []


def test_manifesto_de_sob_em_subpasta_tambem_cria_ambiguidade(tmp_path: Path):
    sob_id = "A057349839"
    dwg = _criar_sob(tmp_path / f"SOB_{sob_id}", sob_id)
    outra_sob = dwg.parent / "SOB_B123456789"
    outra_sob.mkdir()
    (outra_sob / ".sob_state.json").write_text(
        json.dumps({"sob_id": "B123456789", "status": "CONCLUÍDO"}),
        encoding="utf-8",
    )

    contexto = extrair_contexto_operacional(
        dwg_path=str(dwg),
        sob_id_esperada=sob_id,
        require_project_scope=True,
    )

    assert _scope_local(dwg, sob_id)["status"] == "Ambiguous"
    assert contexto["project_scope_status"] == "Unverified"


def test_vinculo_persistido_sobrevive_a_renomeacao_e_movimentacao(tmp_path: Path):
    sob_id = "A057349839"
    original = tmp_path / "SOB_ORIGINAL"
    dwg = _criar_sob(original, sob_id)
    moved = tmp_path / "Projeto_renomeado"
    moved.mkdir()
    renamed_dwg = moved / "planta-revisao.dwg"
    dwg.rename(renamed_dwg)

    contexto = extrair_contexto_operacional(
        dwg_path=str(renamed_dwg),
        sob_id_esperada=sob_id,
        require_project_scope=True,
    )

    assert _scope_local(renamed_dwg, sob_id)["status"] == "Unbound"
    assert contexto["project_scope_status"] == "Unverified"
    assert contexto["project_scope_resolved"] is False
    assert contexto["erro"] == "DWG_CONTEXT_NOT_VERIFIED"


def test_dados_legados_sem_xrecord_nao_sao_promovidos_por_heuristica(tmp_path: Path):
    sob_id = "A057349839"
    dwg = _criar_sob(tmp_path / f"SOB_{sob_id}", sob_id)

    contexto = extrair_contexto_operacional(
        dwg_path=str(dwg),
        require_project_scope=True,
    )

    assert contexto["project_scope_status"] == "Unverified"
    assert contexto["project_scope_resolved"] is False
    assert contexto["status"] == "Contexto DWG não verificado"
    assert contexto["artefatos"] == []


def test_acao_tecnica_sem_project_scope_e_bloqueada(tmp_path: Path):
    dwg = tmp_path / "PE_A057349839_DESENHO.dwg"
    dwg.write_bytes(b"DWG")

    resultado = executar_acao_operacional(
        "cqt",
        dwg_path=str(dwg),
        require_project_scope=True,
    )

    assert resultado["sucesso"] is False
    assert resultado["project_scope_status"] == "Unverified"
    assert resultado["pid"] is None


def test_apontamento_sem_project_scope_nao_cria_registro(tmp_path: Path):
    dwg = tmp_path / "PE_A057349839_DESENHO.dwg"
    dwg.write_bytes(b"DWG")

    resultado = executar_acao_operacional(
        "tempo_iniciar",
        dwg_path=str(dwg),
        require_project_scope=True,
    )

    assert resultado["sucesso"] is False
    assert resultado["project_scope_status"] == "Unverified"
    assert not (tmp_path / ".oxcad" / "time.json").exists()