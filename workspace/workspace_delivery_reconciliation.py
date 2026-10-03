"""Motor autoritativo de reconciliação de entrega e preparação de sincronização offline (P2.7B).

Fecha o ciclo operacional:
OS/SOB -> projeto -> validação -> revisão -> aprovação -> entrega -> verificação local -> preparação para sincronização.

Garante determinismo:
- "Arquivo existe" != "entrega válida"
- Verificação estrita de SOB, DWG, Fingerprint, Snapshot, Approval Gate, Hashes SHA-256 e tamanhos físicos
- Distingue os 5 estados de entrega: GERADA, VERIFICADA, INCOMPATÍVEL, BLOQUEADA, PRONTA_PARA_SINCRONIZACAO
- Atualização idempotente de SyncQueue (.oxcad/sync_queue.json) com estados padronizados: PENDING, READY, BLOCKED, FAILED, SUCCEEDED
- 100% offline, zero daemons, zero chamadas de rede.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sob.sob_core import calcular_hash_arquivo
from workspace import (
    workspace_delivery,
    workspace_review,
)
from workspace.workspace_review import (
    GateEligibilityStatus,
    ReviewStatus,
)
from workspace.workspace_sync_queue import (
    SyncItem,
    SyncQueue,
    SyncStatus,
)
from workspace.workspace_validation import ValidationContext


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DeliveryReconciliationStatus(str, Enum):
    """Classificação autoritativa do ciclo de reconciliação de entrega."""
    NOT_GENERATED = "NOT_GENERATED"
    GENERATED = "GENERATED"
    VERIFIED = "VERIFIED"
    INCOMPATIBLE = "INCOMPATIBLE"
    BLOCKED = "BLOCKED"
    READY_FOR_SYNC = "READY_FOR_SYNC"


@dataclass
class DeliveryReconciliationResult:
    """Resultado estruturado e auditável da reconciliação de entrega local."""
    status: DeliveryReconciliationStatus
    eligible_for_sync: bool
    sob_id: str
    dwg_path: str
    fingerprint: str
    revision_id: str
    review_id: Optional[str] = None
    package_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    reasons: List[str] = field(default_factory=list)
    checks: Dict[str, Any] = field(default_factory=dict)
    reconciled_at: str = field(default_factory=_now_utc)
    sync_item: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


def _context_root(context: ValidationContext) -> Path:
    root = context.project_root.resolve()
    dwg = Path(context.dwg_path).resolve() if context.dwg_path else None
    if not root.is_dir() or dwg is None or dwg.parent != root:
        raise ValueError("DWG_MISMATCH")
    if not context.sob_id or not context.dwg_identity:
        raise ValueError("CONTEXT_MISMATCH")
    return root


def _make_result(
    status: DeliveryReconciliationStatus,
    context: ValidationContext,
    checks: Dict[str, Any],
    reasons: List[str],
    reconciled_at: str,
    review_id: Optional[str] = None,
    revision_id: Optional[str] = None,
    package_id: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    eligible: bool = False,
    sync_item: Optional[Dict[str, Any]] = None,
) -> DeliveryReconciliationResult:
    return DeliveryReconciliationResult(
        status=status,
        eligible_for_sync=eligible,
        sob_id=context.sob_id or "",
        dwg_path=str(context.dwg_path) if context.dwg_path else "",
        fingerprint=context.dwg_identity or "",
        revision_id=revision_id or context.revision or "REV-01",
        review_id=review_id,
        package_id=package_id,
        snapshot_id=snapshot_id,
        reasons=reasons,
        checks=checks,
        reconciled_at=reconciled_at,
        sync_item=sync_item,
    )


def reconcile_delivery(
    context: ValidationContext,
    review_id: Optional[str] = None,
    package_id: Optional[str] = None,
) -> DeliveryReconciliationResult:
    """Executa verificação determinística e sem heurísticas da entrega contra o contexto e revisão aprovada."""
    reconciled_at = _now_utc()
    checks: Dict[str, Any] = {
        "context_valid": False, "review_valid": False, "approval_gate_eligible": False,
        "package_verified": False, "files_intact": False, "pending_intact": False, "snapshot_compatible": False,
    }

    # 1. Validação de Contexto
    try:
        root = _context_root(context)
        checks["context_valid"] = True
    except Exception as e:
        return _make_result(
            DeliveryReconciliationStatus.INCOMPATIBLE, context, checks,
            [f"CONTEXT_MISMATCH: {e}"], reconciled_at
        )

    # 2. Resolução da Revisão
    try:
        rev = workspace_review.get_review(context, review_id) if review_id else (
            workspace_review.list_reviews(context)[-1] if workspace_review.list_reviews(context) else None
        )
    except Exception as err:
        return _make_result(
            DeliveryReconciliationStatus.INCOMPATIBLE, context, checks,
            [f"CONTEXT_MISMATCH: {err}"], reconciled_at
        )

    if not rev:
        return _make_result(
            DeliveryReconciliationStatus.BLOCKED, context, checks,
            ["REVIEW_NOT_FOUND: Nenhuma revisão técnica registrada para este projeto/DWG."], reconciled_at
        )

    resolved_rev_id = rev["review_id"]
    revision_id = rev.get("revision_id", "REV-01")
    snapshot_id = rev.get("source_snapshot_id")

    # 3. Verificação de Status da Revisão e Aprovação
    if rev["status"] != ReviewStatus.APPROVED.value:
        return _make_result(
            DeliveryReconciliationStatus.BLOCKED, context, checks,
            [f"REVIEW_NOT_APPROVED: Revisão em estado '{rev['status']}', aprovação formal mandatória."],
            reconciled_at, review_id=resolved_rev_id, revision_id=revision_id, snapshot_id=snapshot_id
        )

    approval = rev.get("approval")
    if not approval:
        return _make_result(
            DeliveryReconciliationStatus.BLOCKED, context, checks,
            ["APPROVAL_NOT_ACTIVE: Aprovação da revisão técnica ausente."],
            reconciled_at, review_id=resolved_rev_id, revision_id=revision_id, snapshot_id=snapshot_id
        )

    if approval.get("state") == "REVOGADO" or approval.get("revocation") is not None:
        return _make_result(
            DeliveryReconciliationStatus.BLOCKED, context, checks,
            ["APPROVAL_REVOKED: A aprovação da revisão técnica foi formalmente revogada."],
            reconciled_at, review_id=resolved_rev_id, revision_id=revision_id, snapshot_id=snapshot_id
        )

    if approval.get("state") != "APROVADO":
        return _make_result(
            DeliveryReconciliationStatus.BLOCKED, context, checks,
            ["APPROVAL_NOT_ACTIVE: Aprovação da revisão técnica inativa."],
            reconciled_at, review_id=resolved_rev_id, revision_id=revision_id, snapshot_id=snapshot_id
        )

    checks["review_valid"] = True

    # 4. Resolução do Pacote de Entrega
    target_pkg = package_id or (rev.get("delivery", {}).get("package_id") if isinstance(rev.get("delivery"), dict) else None)
    if not target_pkg:
        return _make_result(
            DeliveryReconciliationStatus.NOT_GENERATED, context, checks,
            ["DELIVERY_NOT_GENERATED: Nenhum pacote de entrega foi gerado para esta revisão aprovada."],
            reconciled_at, review_id=resolved_rev_id, revision_id=revision_id, snapshot_id=snapshot_id
        )

    # 5. Verificação Física e Estrutural do Pacote com workspace_delivery
    verify_res = workspace_delivery.verify(context, target_pkg)
    package_status = verify_res.get("status")

    if package_status in {"PACKAGE_NOT_FOUND", "CONTEXT_MISMATCH", "INVALID"}:
        return _make_result(
            DeliveryReconciliationStatus.INCOMPATIBLE, context, checks,
            [f"DELIVERY_PACKAGE_INVALID: Status de verificação do pacote é '{package_status}'."],
            reconciled_at, review_id=resolved_rev_id, revision_id=revision_id, package_id=target_pkg, snapshot_id=snapshot_id
        )

    # Vincula formalmente aprovação ao pacote de entrega se UNAPPROVED
    if package_status == "UNAPPROVED":
        try:
            workspace_delivery.approve(
                context=context, package_id=target_pkg, confirmed=True,
                decision_note=approval.get("decision_note") or "Aprovação confirmada via revisão técnica.",
            )
            verify_res = workspace_delivery.verify(context, target_pkg)
            package_status = verify_res.get("status")
        except Exception:
            pass

    manifest = verify_res.get("manifest", {})
    checks["manifest_sha256"] = verify_res.get("manifest_sha256")
    checks["package_status"] = package_status
    checks["files"] = verify_res.get("files", [])

    missing = [f["path"] for f in verify_res.get("files", []) if f.get("status") == "MISSING"]
    divergent = [f["path"] for f in verify_res.get("files", []) if f.get("status") == "DIVERGENT"]
    pending_changed = verify_res.get("pending_changed", False)

    reasons: List[str] = []
    if missing:
        reasons.append(f"FILES_MISSING: Arquivos previstos ausentes fisicamente: {', '.join(missing)}")
    if divergent:
        reasons.append(f"FILES_DIVERGENT: Tamanho ou SHA-256 divergente: {', '.join(divergent)}")
    if pending_changed:
        reasons.append("PENDING_CHANGED: Pendências alteradas após geração da entrega.")

    if missing or divergent or pending_changed:
        return _make_result(
            DeliveryReconciliationStatus.INCOMPATIBLE, context, checks, reasons,
            reconciled_at, review_id=resolved_rev_id, revision_id=revision_id, package_id=target_pkg, snapshot_id=snapshot_id
        )

    checks["files_intact"] = True
    checks["pending_intact"] = not pending_changed

    if package_status == "REVOKED":
        return _make_result(
            DeliveryReconciliationStatus.BLOCKED, context, checks,
            ["DELIVERY_REVOKED: O pacote de entrega foi formalmente revogado."],
            reconciled_at, review_id=resolved_rev_id, revision_id=revision_id, package_id=target_pkg, snapshot_id=snapshot_id
        )

    if package_status != "CONFIRMED":
        return _make_result(
            DeliveryReconciliationStatus.GENERATED, context, checks,
            [f"PACKAGE_UNCONFIRMED: Pacote em estado '{package_status}'."],
            reconciled_at, review_id=resolved_rev_id, revision_id=revision_id, package_id=target_pkg, snapshot_id=snapshot_id
        )

    checks["package_verified"] = True

    # 6. Compatibilidade Cruzada Manifest vs Revisão vs Snapshot
    if manifest.get("sob_id") != rev.get("sob_id"):
        reasons.append(f"SOB_MISMATCH: SOB do manifesto ({manifest.get('sob_id')}) diverge da revisão ({rev.get('sob_id')}).")
    if manifest.get("revision") != rev.get("revision_id"):
        reasons.append(f"REVISION_MISMATCH: Versão técnica ({manifest.get('revision')}) diverge da revisão ({rev.get('revision_id')}).")
    if manifest.get("dwg_identity") != rev.get("database_fingerprint"):
        reasons.append("FINGERPRINT_MISMATCH: Fingerprint do DWG diverge do registrado na revisão.")

    if snapshot_id:
        if not any(s.get("snapshot_id") == snapshot_id for s in manifest.get("snapshots", [])):
            reasons.append(f"SNAPSHOT_MISMATCH: Snapshot '{snapshot_id}' da revisão não consta no manifesto.")
        else:
            checks["snapshot_compatible"] = True
    else:
        checks["snapshot_compatible"] = True

    if reasons:
        return _make_result(
            DeliveryReconciliationStatus.INCOMPATIBLE, context, checks, reasons,
            reconciled_at, review_id=resolved_rev_id, revision_id=revision_id, package_id=target_pkg, snapshot_id=snapshot_id
        )

    # 7. Avaliação do Approval Gate e Integridade de Pendências
    gate = workspace_review.evaluate_approval_gate(context, resolved_rev_id)
    if gate["status"] != GateEligibilityStatus.ELIGIBLE.value:
        gate_reasons = gate.get("reasons", [])
        status_to_return = DeliveryReconciliationStatus.BLOCKED
        if any("DELIVERY_INCOMPATIBLE" in r for r in gate_reasons) and not any("BLOCKING_PENDINGS" in r or "OPEN_CRITICAL" in r for r in gate_reasons):
            status_to_return = DeliveryReconciliationStatus.INCOMPATIBLE
        return _make_result(
            status_to_return, context, checks,
            [f"APPROVAL_GATE_BLOCKED: {r}" for r in gate_reasons],
            reconciled_at, review_id=resolved_rev_id, revision_id=revision_id, package_id=target_pkg, snapshot_id=snapshot_id
        )

    checks["approval_gate_eligible"] = True

    # 8. Verificação do estado na SyncQueue
    queue = SyncQueue(root)
    sync_item = queue.get_by_idempotency_key(f"delivery:{context.sob_id}:{target_pkg}")

    final_status = DeliveryReconciliationStatus.VERIFIED
    if sync_item and sync_item.status == SyncStatus.READY:
        final_status = DeliveryReconciliationStatus.READY_FOR_SYNC

    return _make_result(
        final_status, context, checks, [], reconciled_at,
        review_id=resolved_rev_id, revision_id=revision_id, package_id=target_pkg, snapshot_id=snapshot_id,
        eligible=True, sync_item=sync_item.to_dict() if sync_item else None
    )


def prepare_sync_queue_for_delivery(
    context: ValidationContext,
    review_id: Optional[str] = None,
    package_id: Optional[str] = None,
    provider_id: str = "sharepoint",
    correlation_id: Optional[str] = None,
) -> Tuple[DeliveryReconciliationResult, Optional[SyncItem]]:
    """
    Reconcilia a entrega local e prepara/atualiza deterministicamente a intenção na SyncQueue.
    - Se a entrega for verificada e compatível: transiciona ou enfileira como READY.
    - Se a entrega for bloqueada ou incompatível: transiciona ou enfileira como BLOCKED.
    - Mantém estrita idempotência: reprocessar a mesma entrega não gera registros duplicados.
    """
    rec_res = reconcile_delivery(context, review_id=review_id, package_id=package_id)
    root = context.project_root.resolve()
    queue = SyncQueue(root)

    pkg_id = rec_res.package_id or package_id
    if not pkg_id:
        return rec_res, None

    idempotency_key = f"delivery:{context.sob_id}:{pkg_id}"
    existing = queue.get_by_idempotency_key(idempotency_key)
    op_id = f"op-delivery-{pkg_id[:12]}"
    corr_id = correlation_id or context.correlation_id or uuid.uuid4().hex

    if rec_res.eligible_for_sync and rec_res.status in {
        DeliveryReconciliationStatus.VERIFIED, DeliveryReconciliationStatus.READY_FOR_SYNC,
    }:
        if existing:
            item_ret = existing if existing.status == SyncStatus.SUCCEEDED else (
                queue.update_status(existing.sync_id, SyncStatus.READY, error=None) or existing
            )
        else:
            artifact_payload = {
                "package_id": pkg_id,
                "manifest_sha256": rec_res.checks.get("manifest_sha256"),
                "revision": rec_res.revision_id,
                "review_id": rec_res.review_id,
                "snapshot_id": rec_res.snapshot_id,
                "files_count": len(rec_res.checks.get("files", [])),
            }
            new_item = SyncItem.create(
                operation_id=op_id, idempotency_key=idempotency_key, correlation_id=corr_id,
                operation="sync_delivery_package", provider_id=provider_id, sob_id=context.sob_id,
                artifact=artifact_payload, status=SyncStatus.READY,
            )
            item_ret, _ = queue.enqueue(new_item)

        rec_res.status = DeliveryReconciliationStatus.READY_FOR_SYNC
        rec_res.sync_item = item_ret.to_dict() if item_ret else None
        return rec_res, item_ret

    # Caso entrega bloqueada, incompatível ou inválida
    err_msg = "; ".join(rec_res.reasons) if rec_res.reasons else "Precondições de entrega não atendidas."
    if existing:
        item_ret = existing if existing.status == SyncStatus.SUCCEEDED else (
            queue.update_status(existing.sync_id, SyncStatus.BLOCKED, error=err_msg) or existing
        )
    else:
        new_item = SyncItem.create(
            operation_id=op_id, idempotency_key=idempotency_key, correlation_id=corr_id,
            operation="sync_delivery_package", provider_id=provider_id, sob_id=context.sob_id,
            artifact={"package_id": pkg_id, "revision": rec_res.revision_id, "review_id": rec_res.review_id},
            status=SyncStatus.BLOCKED,
        )
        new_item = new_item.with_status(SyncStatus.BLOCKED, error=err_msg)
        item_ret, _ = queue.enqueue(new_item)

    rec_res.sync_item = item_ret.to_dict() if item_ret else None
    return rec_res, item_ret


def get_delivery_status(
    context: ValidationContext,
    review_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Retorna visão unificada de reconciliação de entrega e fila de sincronização."""
    result = reconcile_delivery(context, review_id=review_id)
    queue = SyncQueue(context.project_root)
    queue_items = queue.list_items(sob_id=context.sob_id)

    return {
        "success": True,
        "reconciliation": result.to_dict(),
        "sync_queue": [item.to_dict() for item in queue_items],
    }
