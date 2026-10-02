"""Revisão técnica, governança de entrega e rastreabilidade operacional (P2.6).

Fecha o ciclo formal:
Projeto -> Execução -> Validação -> Evidências -> Pendências -> Revisão -> Aprovação -> Entrega

Separa explicitamente:
1. REVISION - versão técnica sendo analisada;
2. REVIEW - processo de análise técnica daquela revisão;
3. APPROVAL - decisão formal sobre a revisão;
4. DELIVERY - pacote efetivamente preparado para entrega;
5. REVOCATION - invalidação posterior quando aplicável.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
import importlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
import uuid

from sob.sob_core import calcular_hash_arquivo
from workspace import workspace_delivery, workspace_pending, workspace_versions
from workspace.workspace_validation import ValidationContext


STORE_FILE = "reviews.json"
LOCK_FILE = "reviews.lock"


class ReviewStatus(str, Enum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


class FindingSeverity(str, Enum):
    INFO = "INFO"
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


class FindingStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    WAIVED = "WAIVED"


class GateEligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


REVIEW_TRANSITIONS: Dict[str, set[str]] = {
    ReviewStatus.DRAFT.value: {ReviewStatus.IN_REVIEW.value, ReviewStatus.CANCELLED.value},
    ReviewStatus.IN_REVIEW.value: {
        ReviewStatus.APPROVED.value,
        ReviewStatus.CHANGES_REQUIRED.value,
        ReviewStatus.REJECTED.value,
    },
    ReviewStatus.CHANGES_REQUIRED.value: {ReviewStatus.DRAFT.value},
    ReviewStatus.APPROVED.value: {ReviewStatus.SUPERSEDED.value},
    ReviewStatus.REJECTED.value: set(),
    ReviewStatus.SUPERSEDED.value: set(),
    ReviewStatus.CANCELLED.value: set(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _context_root(context: ValidationContext, require_existing_dwg: bool = True) -> Path:
    root = context.project_root.resolve()
    dwg = Path(context.dwg_path).resolve() if context.dwg_path else None
    if not root.is_dir() or dwg is None or dwg.parent != root:
        raise ValueError("DWG_MISMATCH")
    if require_existing_dwg and not dwg.is_file():
        raise ValueError("DWG_NOT_FOUND")
    if not context.sob_id or not context.dwg_identity:
        raise ValueError("CONTEXT_MISMATCH")
    if (
        context.database_fingerprint
        and context.database_fingerprint.casefold() != context.dwg_identity.casefold()
    ):
        raise ValueError("CONTEXT_MISMATCH")
    return root


@contextmanager
def _locked_reviews(root: Path) -> Iterator[Path]:
    folder = root / ".oxcad"
    if folder.is_symlink():
        raise ValueError("STORE_INVALID")
    folder.mkdir(exist_ok=True)
    lock_path = folder / LOCK_FILE
    if lock_path.is_symlink():
        raise ValueError("STORE_INVALID")
    with lock_path.open("a+b") as handle:
        if lock_path.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            lock_api = importlib.import_module("fcntl")
            lock_api.flock(handle.fileno(), lock_api.LOCK_EX)
        try:
            yield folder / STORE_FILE
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                lock_api.flock(handle.fileno(), lock_api.LOCK_UN)


def _read_reviews(path: Path, context: ValidationContext) -> Dict[str, Any]:
    if path.is_symlink():
        raise ValueError("STORE_INVALID")
    if not path.exists():
        return {"schema": 1, "sob_id": context.sob_id, "reviews": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or data.get("schema") != 1
            or data.get("sob_id") != context.sob_id
            or not isinstance(data.get("reviews"), list)
        ):
            raise ValueError("STORE_INVALID")
        for item in data["reviews"]:
            if (
                not isinstance(item, dict)
                or item.get("sob_id") != context.sob_id
                or not item.get("review_id")
                or not item.get("status")
                or not isinstance(item.get("history"), list)
            ):
                raise ValueError("STORE_INVALID")
        return data
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("STORE_INVALID") from error


def _write_reviews(path: Path, data: Dict[str, Any]) -> None:
    temp = path.with_name(f".reviews-{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("x", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=False, sort_keys=True, indent=2)
            output.flush()
            os.fsync(output.fileno())
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def create_review(
    context: ValidationContext,
    revision_id: str,
    source_snapshot_id: Optional[str] = None,
    notes: Optional[str] = None,
    evidence_references: Optional[List[str]] = None,
    pending_references: Optional[List[str]] = None,
    operator: Optional[str] = None,
) -> Dict[str, Any]:
    root = _context_root(context)
    if not revision_id or not isinstance(revision_id, str):
        raise ValueError("REVISION_ID_REQUIRED")

    if source_snapshot_id:
        inspected = workspace_versions.inspect(context, source_snapshot_id)
        if inspected.get("status") != "INTACT":
            raise ValueError("SNAPSHOT_INCOMPATIBLE")

    review_id = uuid.uuid4().hex
    now = _now()
    operator_ctx = {
        "operator": operator or "revisor_tecnico",
        "origin": context.origin or "oxcad",
        "host": "local_cad",
    }

    initial_event = {
        "event_id": uuid.uuid4().hex,
        "from_status": None,
        "to_status": ReviewStatus.DRAFT.value,
        "timestamp": now,
        "operator": operator_ctx["operator"],
        "reason": "Revisão técnica iniciada em rascunho.",
    }

    review = {
        "review_id": review_id,
        "sob_id": context.sob_id,
        "project_root": str(root),
        "dwg_path": str(Path(context.dwg_path).resolve()),
        "dwg_identity": context.dwg_identity,
        "database_fingerprint": context.database_fingerprint,
        "revision_id": revision_id.strip(),
        "source_snapshot_id": source_snapshot_id,
        "created_at": now,
        "created_by": operator_ctx,
        "status": ReviewStatus.DRAFT.value,
        "findings": [],
        "evidence_references": list(evidence_references or []),
        "pending_references": list(pending_references or []),
        "notes": notes.strip() if notes else None,
        "approval": None,
        "delivery": None,
        "history": [initial_event],
    }

    with _locked_reviews(root) as store_path:
        store = _read_reviews(store_path, context)
        store["reviews"].append(review)
        _write_reviews(store_path, store)

    return review


def get_review(context: ValidationContext, review_id: str) -> Dict[str, Any]:
    root = _context_root(context, require_existing_dwg=False)
    with _locked_reviews(root) as store_path:
        store = _read_reviews(store_path, context)
        for r in store["reviews"]:
            if r["review_id"] == review_id:
                if (
                    r["sob_id"] != context.sob_id
                    or r["dwg_path"] != str(Path(context.dwg_path).resolve())
                    or r["database_fingerprint"] != context.database_fingerprint
                ):
                    raise ValueError("CONTEXT_MISMATCH")
                return r
    raise ValueError("REVIEW_NOT_FOUND")


def list_reviews(context: ValidationContext) -> List[Dict[str, Any]]:
    root = _context_root(context, require_existing_dwg=False)
    with _locked_reviews(root) as store_path:
        store = _read_reviews(store_path, context)
        return [
            r
            for r in store["reviews"]
            if r["sob_id"] == context.sob_id
            and r["dwg_path"] == str(Path(context.dwg_path).resolve())
            and r["database_fingerprint"] == context.database_fingerprint
        ]


def add_finding(
    context: ValidationContext,
    review_id: str,
    severity: str,
    category: str,
    description: str,
    evidence_references: Optional[List[str]] = None,
    pending_reference: Optional[str] = None,
    create_pending_if_missing: bool = False,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    root = _context_root(context)
    sev_upper = severity.strip().upper()
    if sev_upper not in {s.value for s in FindingSeverity}:
        raise ValueError("INVALID_SEVERITY")
    if not description or not description.strip():
        raise ValueError("DESCRIPTION_REQUIRED")

    resolved_pending_id = pending_reference
    if not resolved_pending_id and create_pending_if_missing:
        created_p = workspace_pending.create(
            context=context,
            description=f"[{category.strip()}] {description.strip()}",
            severity="ERRO" if sev_upper in {"CRITICAL", "MAJOR"} else "ALERTA",
        )
        resolved_pending_id = created_p["id"]

    finding_id = uuid.uuid4().hex
    now = _now()
    finding = {
        "finding_id": finding_id,
        "review_id": review_id,
        "severity": sev_upper,
        "category": category.strip() if category else "Geral",
        "description": description.strip(),
        "status": FindingStatus.OPEN.value,
        "evidence_references": list(evidence_references or []),
        "pending_reference": resolved_pending_id,
        "created_at": now,
        "resolved_at": None,
        "notes": notes.strip() if notes else None,
    }

    with _locked_reviews(root) as store_path:
        store = _read_reviews(store_path, context)
        target_rev = None
        for r in store["reviews"]:
            if r["review_id"] == review_id:
                target_rev = r
                break
        if not target_rev:
            raise ValueError("REVIEW_NOT_FOUND")

        if target_rev["status"] in {
            ReviewStatus.APPROVED.value,
            ReviewStatus.SUPERSEDED.value,
            ReviewStatus.CANCELLED.value,
        }:
            raise ValueError("REVIEW_IMMUTABLE")

        target_rev["findings"].append(finding)
        if resolved_pending_id and resolved_pending_id not in target_rev["pending_references"]:
            target_rev["pending_references"].append(resolved_pending_id)

        _write_reviews(store_path, store)

    return finding


def resolve_finding(
    context: ValidationContext,
    review_id: str,
    finding_id: str,
    resolution_notes: str,
    waive: bool = False,
) -> Dict[str, Any]:
    root = _context_root(context)
    if not resolution_notes or not resolution_notes.strip():
        raise ValueError("RESOLUTION_NOTES_REQUIRED")

    with _locked_reviews(root) as store_path:
        store = _read_reviews(store_path, context)
        target_rev = None
        for r in store["reviews"]:
            if r["review_id"] == review_id:
                target_rev = r
                break
        if not target_rev:
            raise ValueError("REVIEW_NOT_FOUND")

        target_finding = None
        for f in target_rev["findings"]:
            if f["finding_id"] == finding_id:
                target_finding = f
                break
        if not target_finding:
            raise ValueError("FINDING_NOT_FOUND")

        target_finding["status"] = (
            FindingStatus.WAIVED.value if waive else FindingStatus.RESOLVED.value
        )
        target_finding["resolved_at"] = _now()
        target_finding["notes"] = (
            f"{target_finding.get('notes') or ''} [Resolução: {resolution_notes.strip()}]".strip()
        )
        _write_reviews(store_path, store)
        return target_finding


def transition_review(
    context: ValidationContext,
    review_id: str,
    target_status: str,
    reason: str,
    operator: Optional[str] = None,
) -> Dict[str, Any]:
    root = _context_root(context)
    status_upper = target_status.strip().upper()
    if status_upper not in {s.value for s in ReviewStatus}:
        raise ValueError(f"UNKNOWN_STATUS: {target_status}")
    if not reason or not reason.strip():
        raise ValueError("TRANSITION_REASON_REQUIRED")

    with _locked_reviews(root) as store_path:
        store = _read_reviews(store_path, context)
        target_rev = None
        for r in store["reviews"]:
            if r["review_id"] == review_id:
                target_rev = r
                break
        if not target_rev:
            raise ValueError("REVIEW_NOT_FOUND")

        current_status = target_rev["status"]
        allowed = REVIEW_TRANSITIONS.get(current_status, set())
        if status_upper not in allowed:
            raise ValueError(f"INVALID_TRANSITION: {current_status} -> {status_upper}")

        if status_upper == ReviewStatus.APPROVED.value:
            gate = evaluate_approval_gate(context, review_id)
            if gate["status"] != GateEligibilityStatus.ELIGIBLE.value:
                raise ValueError(f"APPROVAL_GATE_BLOCKED: {', '.join(gate['reasons'])}")

        now = _now()
        target_rev["status"] = status_upper
        event = {
            "event_id": uuid.uuid4().hex,
            "from_status": current_status,
            "to_status": status_upper,
            "timestamp": now,
            "operator": operator or "revisor",
            "reason": reason.strip(),
        }
        target_rev["history"].append(event)
        _write_reviews(store_path, store)
        return target_rev


def evaluate_approval_gate(context: ValidationContext, review_id: str) -> Dict[str, Any]:
    reasons: List[str] = []
    warnings: List[str] = []
    checks: Dict[str, bool] = {
        "identity_valid": True,
        "dwg_exists": True,
        "snapshot_valid": True,
        "evidences_intact": True,
        "critical_findings_clear": True,
        "major_findings_clear": True,
        "blocking_pendings_clear": True,
        "delivery_compatible": True,
    }

    try:
        root = _context_root(context, require_existing_dwg=True)
    except Exception as err:
        reasons.append(str(err))
        checks["identity_valid"] = False
        return {
            "status": GateEligibilityStatus.NOT_ELIGIBLE.value,
            "eligible": False,
            "reasons": reasons,
            "warnings": warnings,
            "checks": checks,
            "review_id": review_id,
            "evaluated_at": _now(),
        }

    try:
        rev = get_review(context, review_id)
    except Exception as err:
        reasons.append(str(err))
        return {
            "status": GateEligibilityStatus.NOT_ELIGIBLE.value,
            "eligible": False,
            "reasons": reasons,
            "warnings": warnings,
            "checks": checks,
            "review_id": review_id,
            "evaluated_at": _now(),
        }

    dwg_file = Path(rev["dwg_path"])
    if not dwg_file.is_file():
        reasons.append("DWG_NOT_FOUND")
        checks["dwg_exists"] = False

    snap_id = rev.get("source_snapshot_id")
    if snap_id:
        try:
            inspected = workspace_versions.inspect(context, snap_id)
            if inspected.get("status") != "INTACT":
                reasons.append("SNAPSHOT_INVALID")
                checks["snapshot_valid"] = False
        except Exception:
            reasons.append("SNAPSHOT_INVALID")
            checks["snapshot_valid"] = False

    all_evidences = set(rev.get("evidence_references", []))
    for f in rev.get("findings", []):
        all_evidences.update(f.get("evidence_references", []))

    for ev in all_evidences:
        p = Path(ev)
        if not p.is_absolute():
            p = root / ev
        if not p.exists():
            reasons.append(f"EVIDENCE_MISSING: {ev}")
            checks["evidences_intact"] = False
        else:
            try:
                pass
            except Exception:
                reasons.append(f"EVIDENCE_CORRUPT: {ev}")
                checks["evidences_intact"] = False

    open_critical = [
        f for f in rev.get("findings", [])
        if f["status"] == FindingStatus.OPEN.value and f["severity"] == FindingSeverity.CRITICAL.value
    ]
    if open_critical:
        reasons.append(f"OPEN_CRITICAL_FINDINGS: {len(open_critical)}")
        checks["critical_findings_clear"] = False

    open_major = [
        f for f in rev.get("findings", [])
        if f["status"] == FindingStatus.OPEN.value and f["severity"] == FindingSeverity.MAJOR.value
    ]
    if open_major:
        reasons.append(f"OPEN_MAJOR_FINDINGS: {len(open_major)}")
        checks["major_findings_clear"] = False

    open_minor = [
        f for f in rev.get("findings", [])
        if f["status"] == FindingStatus.OPEN.value and f["severity"] in {FindingSeverity.MINOR.value, FindingSeverity.INFO.value}
    ]
    if open_minor:
        warnings.append(f"OPEN_MINOR_OR_INFO_FINDINGS: {len(open_minor)}")

    try:
        pending_list = workspace_pending.list_pending(context)
        blocking_items = [
            p for p in pending_list
            if p["status"] in {"ABERTA", "EM_ANDAMENTO"}
            and (p.get("severity") in {"BLOQUEANTE", "ALTA", "ERRO"} or p["id"] in rev.get("pending_references", []))
        ]
        if blocking_items:
            reasons.append(f"BLOCKING_PENDINGS: {len(blocking_items)}")
            checks["blocking_pendings_clear"] = False
    except Exception:
        pass

    deliv = rev.get("delivery")
    if deliv and isinstance(deliv, dict) and deliv.get("package_id"):
        try:
            ver = workspace_delivery.verify(context, deliv["package_id"])
            if ver.get("status") in {"DIVERGENT", "MISSING", "CONTEXT_MISMATCH"}:
                reasons.append("DELIVERY_INCOMPATIBLE")
                checks["delivery_compatible"] = False
        except Exception:
            reasons.append("DELIVERY_INCOMPATIBLE")
            checks["delivery_compatible"] = False

    eligible = len(reasons) == 0
    return {
        "status": GateEligibilityStatus.ELIGIBLE.value if eligible else GateEligibilityStatus.NOT_ELIGIBLE.value,
        "eligible": eligible,
        "reasons": reasons,
        "warnings": warnings,
        "checks": checks,
        "review_id": review_id,
        "evaluated_at": _now(),
    }


def approve_review(
    context: ValidationContext,
    review_id: str,
    confirmed: bool = False,
    decision_note: Optional[str] = None,
    operator: Optional[str] = None,
) -> Dict[str, Any]:
    root = _context_root(context)
    if confirmed is not True:
        raise ValueError("APPROVAL_NOT_CONFIRMED")

    rev = get_review(context, review_id)
    if rev["status"] != ReviewStatus.IN_REVIEW.value:
        raise ValueError(f"REVIEW_NOT_IN_REVIEW: {rev['status']}")

    gate = evaluate_approval_gate(context, review_id)
    if not gate["eligible"]:
        raise ValueError(f"APPROVAL_GATE_BLOCKED: {', '.join(gate['reasons'])}")

    now = _now()
    approval = {
        "schema": 1,
        "review_id": review_id,
        "revision": rev["revision_id"],
        "state": "APROVADO",
        "approved_at": now,
        "sob_id": context.sob_id,
        "dwg_path": str(Path(context.dwg_path).resolve()),
        "dwg_identity": context.dwg_identity,
        "database_fingerprint": context.database_fingerprint,
        "source_snapshot_id": rev.get("source_snapshot_id"),
        "operator_context": {
            "operator": operator or "revisor_aprovador",
            "origin": context.origin or "oxcad",
        },
        "findings_considered": [f["finding_id"] for f in rev.get("findings", [])],
        "decision_note": decision_note.strip() if decision_note else None,
        "revocation": None,
    }

    with _locked_reviews(root) as store_path:
        store = _read_reviews(store_path, context)
        target_rev = None
        for r in store["reviews"]:
            if r["review_id"] == review_id:
                target_rev = r
                break
        if not target_rev:
            raise ValueError("REVIEW_NOT_FOUND")

        target_rev["status"] = ReviewStatus.APPROVED.value
        target_rev["approval"] = approval
        target_rev["history"].append({
            "event_id": uuid.uuid4().hex,
            "from_status": ReviewStatus.IN_REVIEW.value,
            "to_status": ReviewStatus.APPROVED.value,
            "timestamp": now,
            "operator": operator or "revisor_aprovador",
            "reason": f"Revisão formalmente aprovada. {decision_note or ''}".strip(),
        })
        _write_reviews(store_path, store)

    return approval


def revoke_review_approval(
    context: ValidationContext,
    review_id: str,
    reason: str,
    operator: Optional[str] = None,
) -> Dict[str, Any]:
    root = _context_root(context, require_existing_dwg=False)
    if not reason or not reason.strip():
        raise ValueError("REVOCATION_REASON_REQUIRED")

    with _locked_reviews(root) as store_path:
        store = _read_reviews(store_path, context)
        target_rev = None
        for r in store["reviews"]:
            if r["review_id"] == review_id:
                target_rev = r
                break
        if not target_rev:
            raise ValueError("REVIEW_NOT_FOUND")

        approval = target_rev.get("approval")
        if not approval or approval.get("state") != "APROVADO":
            raise ValueError("APPROVAL_NOT_ACTIVE")

        now = _now()
        approval["state"] = "REVOGADO"
        revocation_data = {
            "timestamp": now,
            "reason": reason.strip(),
            "operator": operator or "auditor_revisor",
            "origin": context.origin or "oxcad",
        }
        approval["revocation"] = revocation_data
        target_rev["history"].append({
            "event_id": uuid.uuid4().hex,
            "from_status": target_rev["status"],
            "to_status": target_rev["status"],
            "timestamp": now,
            "operator": operator or "auditor_revisor",
            "reason": f"Aprovação revogada: {reason.strip()}",
        })
        _write_reviews(store_path, store)
        return approval


def prepare_delivery_for_review(
    context: ValidationContext,
    review_id: str,
    artifacts: List[str],
    validations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    root = _context_root(context)
    rev = get_review(context, review_id)
    if rev["status"] != ReviewStatus.APPROVED.value:
        raise ValueError("REVIEW_NOT_APPROVED")

    approval = rev.get("approval")
    if not approval or approval.get("state") != "APROVADO":
        raise ValueError("APPROVAL_NOT_ACTIVE")

    snap_ids = [rev["source_snapshot_id"]] if rev.get("source_snapshot_id") else None
    pkg = workspace_delivery.generate(
        context=context,
        artifacts=artifacts,
        validations=validations,
        snapshot_ids=snap_ids,
    )

    delivery_ref = {
        "package_id": pkg["package_id"],
        "manifest_sha256": pkg["manifest_sha256"],
        "prepared_at": _now(),
        "status": "PREPARED",
    }

    with _locked_reviews(root) as store_path:
        store = _read_reviews(store_path, context)
        for r in store["reviews"]:
            if r["review_id"] == review_id:
                r["delivery"] = delivery_ref
                r["history"].append({
                    "event_id": uuid.uuid4().hex,
                    "from_status": r["status"],
                    "to_status": r["status"],
                    "timestamp": _now(),
                    "operator": context.origin or "oxcad",
                    "reason": f"Pacote de entrega associado: {pkg['package_id']}",
                })
                break
        _write_reviews(store_path, store)

    return pkg


def build_traceability_chain(context: ValidationContext, review_id: str) -> Dict[str, Any]:
    root = _context_root(context, require_existing_dwg=False)
    rev = get_review(context, review_id)

    snap_info = None
    if rev.get("source_snapshot_id"):
        try:
            snap_info = workspace_versions.inspect(context, rev["source_snapshot_id"])
        except Exception as e:
            snap_info = {"status": "UNAVAILABLE", "error": str(e)}

    pendings_info = []
    try:
        all_pendings = workspace_pending.list_pending(context)
        ref_ids = set(rev.get("pending_references", []))
        for p in all_pendings:
            if p["id"] in ref_ids:
                pendings_info.append({
                    "id": p["id"],
                    "status": p["status"],
                    "severity": p.get("severity"),
                    "description": p.get("description"),
                })
    except Exception:
        pass

    delivery_info = None
    if rev.get("delivery") and isinstance(rev["delivery"], dict):
        pkg_id = rev["delivery"].get("package_id")
        if pkg_id:
            try:
                delivery_info = workspace_delivery.verify(context, pkg_id)
            except Exception as e:
                delivery_info = {"status": "UNAVAILABLE", "error": str(e)}

    chain = {
        "sob_id": rev["sob_id"],
        "dwg_path": rev["dwg_path"],
        "database_fingerprint": rev["database_fingerprint"],
        "revision_id": rev["revision_id"],
        "snapshot": snap_info,
        "review": {
            "review_id": rev["review_id"],
            "status": rev["status"],
            "created_at": rev["created_at"],
            "created_by": rev["created_by"],
            "notes": rev.get("notes"),
        },
        "findings": {
            "total": len(rev.get("findings", [])),
            "items": rev.get("findings", []),
        },
        "pendings": pendings_info,
        "approval": rev.get("approval"),
        "delivery": delivery_info,
        "audit_answers": {
            "qual_revisao_foi_revisada": rev["revision_id"],
            "quais_evidencias_foram_consideradas": rev.get("evidence_references", []),
            "quais_pendencias_estavam_abertas": [p["id"] for p in pendings_info if p["status"] in {"ABERTA", "EM_ANDAMENTO"}],
            "quem_realizou_a_revisao": rev["created_by"].get("operator"),
            "por_que_foi_aprovada_ou_rejeitada": (
                rev["approval"].get("decision_note") if rev.get("approval") else None
            ),
            "qual_pacote_foi_entregue": (
                rev["delivery"].get("package_id") if rev.get("delivery") else None
            ),
            "qual_versao_exata_originou_o_pacote": rev["revision_id"],
        },
    }
    return chain
