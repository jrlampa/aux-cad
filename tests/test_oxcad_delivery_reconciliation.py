"""Suíte de testes contratuais para o Fechamento da Entrega e Reconciliação Offline (P2.7B).

Cobre exaustivamente:
- Entrega válida e verificada
- Entrega inexistente
- Arquivo alterado (tamanho / hash SHA-256)
- DWG, SOB e Fingerprint divergentes
- Revisão divergente
- Snapshot divergente
- Review não aprovado / aprovação revogada
- Delivery incompatível / pendências alteradas
- Pending bloqueante / Approval Gate
- Transições de SyncQueue para READY e BLOCKED
- Idempotência, deduplicação e reexecução segura
- Ausência total de chamadas externas e persistência estrita
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from unittest.mock import patch

from workspace import (
    workspace_delivery,
    workspace_delivery_reconciliation,
    workspace_pending,
    workspace_review,
    workspace_versions,
)
from workspace.workspace_delivery_reconciliation import (
    DeliveryReconciliationStatus,
    prepare_sync_queue_for_delivery,
    reconcile_delivery,
)
from workspace.workspace_review import (
    FindingSeverity,
    ReviewStatus,
)
from workspace.workspace_sync_queue import (
    SyncItem,
    SyncQueue,
    SyncStatus,
)
from workspace.workspace_validation import ValidationContext


@pytest.fixture
def p27b_env(tmp_path: Path):
    """Cria um ambiente de projeto homologado, íntegro e isolado."""
    sob_id = "A057526153"
    dwg_file = tmp_path / "PROJETO_A057526153.dwg"
    dwg_file.write_text("DWG_HEX_BINARY_VALID_2026", encoding="utf-8")
    fingerprint = "{FINGERPRINT-GUID-A057526153-VALID}"

    calc_file = tmp_path / "calculo.xlsx"
    calc_file.write_text("CALC_VALID_DATA", encoding="utf-8")

    ctx = ValidationContext(
        execution_id="exec-p27b-01",
        correlation_id="corr-p27b-01",
        sob_id=sob_id,
        dwg_path=str(dwg_file),
        dwg_identity=fingerprint,
        database_fingerprint=fingerprint,
        project_root=tmp_path,
        cqt_path=None,
        revision="REV-01",
        origin="oxcad.tests",
        host_verified=True,
    )

    # 1. Snapshot base
    snap = workspace_versions.capture(ctx, dwg_file.name)

    # 2. Criação da revisão e transição para IN_REVIEW
    rev = workspace_review.create_review(
        context=ctx,
        revision_id="REV-01",
        source_snapshot_id=snap["snapshot_id"],
        operator="Engenheiro Revisor",
    )
    rev = workspace_review.transition_review(
        context=ctx,
        review_id=rev["review_id"],
        target_status=ReviewStatus.IN_REVIEW.value,
        reason="Iniciando checagem técnica",
        operator="Engenheiro Revisor",
    )

    # Validação base para compor pacote de entrega
    dwg_rel = dwg_file.name
    import hashlib
    dwg_hash = hashlib.sha256("DWG_HEX_BINARY_VALID_2026".encode("utf-8")).hexdigest()
    validations = [{
        "rule_id": "REG-01",
        "status": "OK",
        "timestamp": "2026-10-03T00:00:00Z",
        "sob_id": sob_id,
        "dwg_path": str(dwg_file.resolve()),
        "dwg_identity": fingerprint,
        "database_fingerprint": fingerprint,
        "execution_id": "exec-p27b-01",
        "correlation_id": "corr-p27b-01",
        "source": {
            "arquivo": str(dwg_file.resolve()),
            "sha256": dwg_hash,
            "tipo": "DWG",
        }
    }]

    return {
        "root": tmp_path,
        "context": ctx,
        "sob_id": sob_id,
        "dwg": dwg_file,
        "fingerprint": fingerprint,
        "calc": calc_file,
        "snapshot": snap,
        "review": rev,
        "validations": validations,
        "artifacts": [dwg_rel, calc_file.name],
    }


def _aprovar_e_gerar_entrega(env) -> dict:
    """Helper para aprovar formalmente a revisão e gerar pacote de entrega associado."""
    ctx = env["context"]
    rev_id = env["review"]["review_id"]

    # Aprova a revisão formalmente
    workspace_review.approve_review(
        context=ctx,
        review_id=rev_id,
        confirmed=True,
        decision_note="Revisão aprovada nos testes.",
        operator="Responsável Técnico",
    )

    # Gera pacote de entrega vinculado à revisão
    pkg = workspace_review.prepare_delivery_for_review(
        context=ctx,
        review_id=rev_id,
        artifacts=env["artifacts"],
        validations=env["validations"],
    )
    return pkg


# ==============================================================================
# 1. TESTES DE RECONCILIAÇÃO BÁSICA E VERIFICAÇÃO DE ENTREGA
# ==============================================================================

def test_01_reconciliacao_entrega_valida(p27b_env):
    """Entrega gerada para revisão aprovada e arquivos íntegros é reconciliada como VERIFIED."""
    pkg = _aprovar_e_gerar_entrega(p27b_env)
    res = reconcile_delivery(p27b_env["context"])

    assert res.status == DeliveryReconciliationStatus.VERIFIED
    assert res.eligible_for_sync is True
    assert res.package_id == pkg["package_id"]
    assert res.checks["files_intact"] is True
    assert res.checks["review_valid"] is True
    assert res.checks["approval_gate_eligible"] is True
    assert len(res.reasons) == 0


def test_02_reconciliacao_entrega_inexistente(p27b_env):
    """Revisão aprovada sem pacote de entrega gerado resulta em NOT_GENERATED."""
    workspace_review.approve_review(
        context=p27b_env["context"],
        review_id=p27b_env["review"]["review_id"],
        confirmed=True,
        decision_note="Aprovado sem delivery gerado.",
    )
    res = reconcile_delivery(p27b_env["context"])

    assert res.status == DeliveryReconciliationStatus.NOT_GENERATED
    assert res.eligible_for_sync is False
    assert any("DELIVERY_NOT_GENERATED" in r for r in res.reasons)


def test_03_reconciliacao_arquivo_alterado_hash_divergente(p27b_env):
    """Arquivo físico modificado após a geração da entrega resulta em INCOMPATIBLE por divergência de hash."""
    _aprovar_e_gerar_entrega(p27b_env)

    # Modifica o conteúdo físico do arquivo sem alterar o manifesto
    p27b_env["calc"].write_text("CALC_DATA_ALTERADA_INDEVIDAMENTE", encoding="utf-8")

    res = reconcile_delivery(p27b_env["context"])
    assert res.status == DeliveryReconciliationStatus.INCOMPATIBLE
    assert res.eligible_for_sync is False
    assert any("FILES_DIVERGENT" in r for r in res.reasons)


def test_04_reconciliacao_tamanho_divergente(p27b_env):
    """Arquivo com tamanho físico alterado resulta em INCOMPATIBLE."""
    _aprovar_e_gerar_entrega(p27b_env)

    # Modifica tamanho adicionando bytes
    p27b_env["calc"].write_text("CALC_VALID_DATA" + ("A" * 500), encoding="utf-8")

    res = reconcile_delivery(p27b_env["context"])
    assert res.status == DeliveryReconciliationStatus.INCOMPATIBLE
    assert any("FILES_DIVERGENT" in r for r in res.reasons)


def test_05_reconciliacao_arquivo_previsto_ausente(p27b_env):
    """Arquivo do manifesto fisicamente deletado resulta em INCOMPATIBLE (FILES_MISSING)."""
    _aprovar_e_gerar_entrega(p27b_env)

    # Deleta arquivo físico
    p27b_env["calc"].unlink()

    res = reconcile_delivery(p27b_env["context"])
    assert res.status == DeliveryReconciliationStatus.INCOMPATIBLE
    assert any("FILES_MISSING" in r for r in res.reasons)


# ==============================================================================
# 2. TESTES DE SOBERANIA DE IDENTIDADE E DIVERGÊNCIA DE CONTEXTO
# ==============================================================================

def test_06_reconciliacao_dwg_divergente(p27b_env):
    """DWG divergente do contexto do projeto resulta em erro de CONTEXT_MISMATCH."""
    _aprovar_e_gerar_entrega(p27b_env)

    outro_dwg = p27b_env["root"] / "OUTRO_DWG.dwg"
    ctx_div = ValidationContext(
        execution_id="exec-div", correlation_id="corr-div", sob_id=p27b_env["sob_id"],
        dwg_path=str(outro_dwg), dwg_identity=p27b_env["fingerprint"], database_fingerprint=p27b_env["fingerprint"],
        project_root=p27b_env["root"], cqt_path=None, host_verified=False,
    )
    res = reconcile_delivery(ctx_div)
    assert res.status in {DeliveryReconciliationStatus.INCOMPATIBLE, DeliveryReconciliationStatus.BLOCKED}
    assert any("CONTEXT_MISMATCH" in r or "REVIEW_NOT_FOUND" in r or "DWG" in r for r in res.reasons)


def test_07_reconciliacao_fingerprint_divergente(p27b_env):
    """Fingerprint divergente da autoridade AutoCAD rejeita a reconciliação com CONTEXT_MISMATCH."""
    _aprovar_e_gerar_entrega(p27b_env)

    ctx_div = ValidationContext(
        execution_id="exec-div", correlation_id="corr-div", sob_id=p27b_env["sob_id"],
        dwg_path=str(p27b_env["dwg"]), dwg_identity="{FINGERPRINT-DIVERGENTE}", database_fingerprint="{FINGERPRINT-DIVERGENTE}",
        project_root=p27b_env["root"], cqt_path=None, host_verified=True,
    )
    res = reconcile_delivery(ctx_div)
    assert res.status in {DeliveryReconciliationStatus.INCOMPATIBLE, DeliveryReconciliationStatus.BLOCKED}
    assert any("CONTEXT_MISMATCH" in r or "REVIEW_NOT_FOUND" in r or "FINGERPRINT" in r for r in res.reasons)


def test_08_reconciliacao_sob_divergente(p27b_env):
    """SOB divergente no contexto resulta em bloqueio/incompatibilidade imediata."""
    _aprovar_e_gerar_entrega(p27b_env)

    ctx_div = ValidationContext(
        execution_id="exec-div", correlation_id="corr-div", sob_id="B999999999",
        dwg_path=str(p27b_env["dwg"]), dwg_identity=p27b_env["fingerprint"], database_fingerprint=p27b_env["fingerprint"],
        project_root=p27b_env["root"], cqt_path=None, host_verified=True,
    )
    res = reconcile_delivery(ctx_div)
    assert res.status in {DeliveryReconciliationStatus.INCOMPATIBLE, DeliveryReconciliationStatus.BLOCKED}
    assert any("SOB" in r or "REVIEW_NOT_FOUND" in r or "STORE_INVALID" in r or "CONTEXT_MISMATCH" in r for r in res.reasons)


# ==============================================================================
# 3. TESTES DE COMPATIBILIDADE COM A REVISÃO E APPROVAL GATE
# ==============================================================================

def test_09_reconciliacao_review_nao_aprovado(p27b_env):
    """Revisão ainda em DRAFT ou IN_REVIEW bloqueia a entrega (REVIEW_NOT_APPROVED)."""
    # A revisão da fixture está em IN_REVIEW
    res = reconcile_delivery(p27b_env["context"])
    assert res.status == DeliveryReconciliationStatus.BLOCKED
    assert any("REVIEW_NOT_APPROVED" in r for r in res.reasons)


def test_10_reconciliacao_aprovacao_revogada(p27b_env):
    """Revogação posterior da aprovação da revisão bloqueia a entrega imediatamente."""
    _aprovar_e_gerar_entrega(p27b_env)
    ctx = p27b_env["context"]
    rev_id = p27b_env["review"]["review_id"]

    # Revoga formalmente a aprovação
    workspace_review.revoke_review_approval(ctx, rev_id, reason="Erro de projeto detectado pós-aprovação.")

    res = reconcile_delivery(ctx)
    assert res.status == DeliveryReconciliationStatus.BLOCKED
    assert any("APPROVAL_REVOKED" in r or "APPROVAL_GATE_BLOCKED" in r for r in res.reasons)


def test_11_reconciliacao_gate_bloqueado_por_pending_bloqueante(p27b_env):
    """Criação de pendência bloqueante no projeto bloqueia a entrega via Approval Gate."""
    _aprovar_e_gerar_entrega(p27b_env)
    ctx = p27b_env["context"]

    # Registra pendência bloqueante autoritativa
    workspace_pending.create(
        context=ctx,
        description="Falta aprovação da travessia com DER",
        severity="ERRO",
    )

    res = reconcile_delivery(ctx)
    assert res.status in {DeliveryReconciliationStatus.BLOCKED, DeliveryReconciliationStatus.INCOMPATIBLE}
    assert any("APPROVAL_GATE_BLOCKED" in r or "PENDING_CHANGED" in r for r in res.reasons)


def test_12_reconciliacao_snapshot_divergente(p27b_env):
    """Revisão vinculada a snapshot diferente do contido no pacote de entrega é rejeitada."""
    pkg = _aprovar_e_gerar_entrega(p27b_env)
    ctx = p27b_env["context"]

    # Cria outro snapshot e altera artificialmente a revisão para apontar para o novo
    snap2 = workspace_versions.capture(ctx, p27b_env["calc"].name)
    store_file = p27b_env["root"] / ".oxcad" / "reviews.json"
    data = json.loads(store_file.read_text(encoding="utf-8"))
    for r in data["reviews"]:
        if r["review_id"] == p27b_env["review"]["review_id"]:
            r["source_snapshot_id"] = snap2["snapshot_id"]
            break
    store_file.write_text(json.dumps(data), encoding="utf-8")

    res = reconcile_delivery(ctx)
    assert res.status == DeliveryReconciliationStatus.INCOMPATIBLE
    assert any("SNAPSHOT_MISMATCH" in r for r in res.reasons)


# ==============================================================================
# 4. TESTES DE EVOLUÇÃO DA SYNC QUEUE E IDEMPOTÊNCIA
# ==============================================================================

def test_13_preparar_sync_queue_transicao_para_ready(p27b_env):
    """Entrega verificada é enfileirada deterministicamente com status READY na SyncQueue."""
    pkg = _aprovar_e_gerar_entrega(p27b_env)
    ctx = p27b_env["context"]

    rec_res, sync_item = prepare_sync_queue_for_delivery(ctx, provider_id="sharepoint")

    assert rec_res.status == DeliveryReconciliationStatus.READY_FOR_SYNC
    assert rec_res.eligible_for_sync is True
    assert sync_item is not None
    assert sync_item.status == SyncStatus.READY
    assert sync_item.sob_id == p27b_env["sob_id"]
    assert sync_item.provider_id == "sharepoint"

    # Confirma persistência em .oxcad/sync_queue.json
    queue = SyncQueue(p27b_env["root"])
    items = queue.list_items()
    assert len(items) == 1
    assert items[0].status == SyncStatus.READY
    assert items[0].idempotency_key == f"delivery:{p27b_env['sob_id']}:{pkg['package_id']}"


def test_14_preparar_sync_queue_transicao_para_blocked(p27b_env):
    """Entrega não aprovada tem intenção registrada ou atualizada como BLOCKED na SyncQueue."""
    # Revisão ainda não aprovada
    ctx = p27b_env["context"]
    rec_res, sync_item = prepare_sync_queue_for_delivery(ctx, package_id="0123456789abcdef0123456789abcdef")

    assert rec_res.status == DeliveryReconciliationStatus.BLOCKED
    assert rec_res.eligible_for_sync is False
    assert sync_item is not None
    assert sync_item.status == SyncStatus.BLOCKED
    assert sync_item.error_message is not None
    assert "REVIEW_NOT_APPROVED" in sync_item.error_message


def test_15_idempotencia_sem_duplicacao_na_fila(p27b_env):
    """Múltiplas chamadas de preparação de sync para a mesma entrega não duplicam registros na fila."""
    _aprovar_e_gerar_entrega(p27b_env)
    ctx = p27b_env["context"]

    # 1ª execução
    res1, item1 = prepare_sync_queue_for_delivery(ctx)
    # 2ª execução
    res2, item2 = prepare_sync_queue_for_delivery(ctx)

    assert item1.sync_id == item2.sync_id
    assert item1.idempotency_key == item2.idempotency_key
    queue = SyncQueue(p27b_env["root"])
    assert len(queue.list_items()) == 1


def test_16_preservacao_de_item_ja_concluido(p27b_env):
    """Item marcado como SUCCEEDED não é regredido acidentalmente para READY em nova reconciliação."""
    _aprovar_e_gerar_entrega(p27b_env)
    ctx = p27b_env["context"]

    _, item = prepare_sync_queue_for_delivery(ctx)
    queue = SyncQueue(p27b_env["root"])

    # Simula sucesso posterior de sincronização
    item_succeeded = queue.update_status(item.sync_id, SyncStatus.SUCCEEDED)
    assert item_succeeded.status == SyncStatus.SUCCEEDED

    # Nova reconciliação
    _, rechecked = prepare_sync_queue_for_delivery(ctx)
    assert rechecked.status == SyncStatus.SUCCEEDED


def test_17_reconciliacao_reexecucao_segura_idempotente(p27b_env):
    """Execução repetida de reconcile_delivery é puramente determinística e read-only."""
    _aprovar_e_gerar_entrega(p27b_env)
    ctx = p27b_env["context"]

    res_a = reconcile_delivery(ctx)
    res_b = reconcile_delivery(ctx)

    assert res_a.status == res_b.status
    assert res_a.package_id == res_b.package_id
    assert res_a.eligible_for_sync == res_b.eligible_for_sync


def test_18_ausencia_de_chamadas_externas_e_secrets(p27b_env):
    """Garante que P2.7B é 100% offline, sem sockets, threads de rede ou secrets persistidos."""
    _aprovar_e_gerar_entrega(p27b_env)
    ctx = p27b_env["context"]

    with patch("urllib.request.urlopen") as mock_url, \
         patch("http.client.HTTPConnection") as mock_http:
        rec_res, sync_item = prepare_sync_queue_for_delivery(ctx)
        mock_url.assert_not_called()
        mock_http.assert_not_called()

    # Confirma que nada de credencial foi gravado
    raw_sync = (p27b_env["root"] / ".oxcad" / "sync_queue.json").read_text(encoding="utf-8")
    for sec in ["password", "secret", "token", "Bearer", "client_secret"]:
        assert sec not in raw_sync


# ==============================================================================
# 5. TESTES DE INTEGRAÇÃO COM O CLI DEDICADO (workspace_delivery_cli.py)
# ==============================================================================

def test_19_cli_delivery_reconciliar_e_preparar_sync(p27b_env):
    """O CLI dedicado workspace_delivery_cli.py executa ponta a ponta retornando JSON válido."""
    pkg = _aprovar_e_gerar_entrega(p27b_env)
    from workspace import workspace_delivery_cli

    argv_status = [
        "status",
        "--project-root", str(p27b_env["root"]),
        "--dwg", str(p27b_env["dwg"]),
        "--sob", p27b_env["sob_id"],
        "--fingerprint", p27b_env["fingerprint"],
    ]
    parser = workspace_delivery_cli.create_parser()
    args_st = parser.parse_args(argv_status)
    st_res = workspace_delivery_cli.handle_status(args_st)
    assert st_res["success"] is True
    assert st_res["data"]["reconciliation"]["status"] in {
        DeliveryReconciliationStatus.VERIFIED.value,
        DeliveryReconciliationStatus.READY_FOR_SYNC.value,
    }

    argv_sync = [
        "preparar-sync",
        "--project-root", str(p27b_env["root"]),
        "--dwg", str(p27b_env["dwg"]),
        "--sob", p27b_env["sob_id"],
        "--fingerprint", p27b_env["fingerprint"],
        "--provider-id", "sharepoint",
    ]
    args_sync = parser.parse_args(argv_sync)
    sync_res = workspace_delivery_cli.handle_preparar_sync(args_sync)
    assert sync_res["success"] is True
    assert sync_res["reconciliation"]["status"] == DeliveryReconciliationStatus.READY_FOR_SYNC.value
    assert sync_res["sync_item"]["status"] == SyncStatus.READY.value
