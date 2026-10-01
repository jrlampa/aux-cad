"""Pendências opt-in vinculadas ao ProjectScope e ao DWG ativo."""

import json
import os
import uuid
import importlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from workspace.workspace_validation import ValidationContext
from workspace.workspace_versions import _identity, inspect


STATES = {"ABERTA", "EM_ANDAMENTO", "RESOLVIDA", "DESCARTADA"}
TRANSITIONS = {
    "ABERTA": {"EM_ANDAMENTO", "RESOLVIDA", "DESCARTADA"},
    "EM_ANDAMENTO": {"ABERTA", "RESOLVIDA", "DESCARTADA"},
    "RESOLVIDA": {"ABERTA"},
    "DESCARTADA": {"ABERTA"},
}
STORE = "pending.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@contextmanager
def _locked(root: Path) -> Iterator[Path]:
    folder = root / ".oxcad"
    if folder.is_symlink():
        raise ValueError("STORE_INVALID")
    folder.mkdir(exist_ok=True)
    lock_path = folder / "pending.lock"
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
            yield folder / STORE
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                lock_api.flock(handle.fileno(), lock_api.LOCK_UN)


def _read(path: Path, context: ValidationContext) -> Dict[str, Any]:
    if path.is_symlink():
        raise ValueError("STORE_INVALID")
    if not path.exists():
        return {"schema": 1, "sob_id": context.sob_id, "items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or data.get("schema") != 1
                or data.get("sob_id") != context.sob_id
                or not isinstance(data.get("items"), list)):
            raise ValueError("STORE_INVALID")
        for item in data["items"]:
            if (not isinstance(item, dict)
                    or item.get("sob_id") != context.sob_id
                    or item.get("status") not in STATES
                    or not isinstance(item.get("history"), list)
                    or not item.get("dwg_path") or not item.get("dwg_identity")
                    or "database_fingerprint" not in item
                    or not item.get("id")):
                raise ValueError("STORE_INVALID")
        return data
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("STORE_INVALID") from error


def _write(path: Path, data: Dict[str, Any]) -> None:
    temp = path.with_name(f".pending-{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("x", encoding="utf-8") as output:
            json.dump(
                data, output, ensure_ascii=False, sort_keys=True, indent=2
            )
            output.flush()
            os.fsync(output.fileno())
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def _matches(item: Dict[str, Any], context: ValidationContext) -> bool:
    return (
        item["sob_id"] == context.sob_id
        and item["dwg_path"] == str(Path(context.dwg_path).resolve())
        and item["dwg_identity"] == context.dwg_identity
        and item["database_fingerprint"] == context.database_fingerprint
    )


def _evidence(
    context: ValidationContext,
    validation: Optional[Dict[str, Any]],
    snapshot_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    if validation is not None and snapshot_id is not None:
        raise ValueError("EVIDENCE_INVALID")
    if validation is not None:
        if (not isinstance(validation, dict)
                or validation.get("status") not in {"ALERTA", "ERRO"}
                or not validation.get("rule_id")
                or validation.get("sob_id") != context.sob_id
                or validation.get("dwg_path") != str(
                    Path(context.dwg_path).resolve()
                )
                or validation.get("dwg_identity") != context.dwg_identity
                or validation.get("database_fingerprint")
                != context.database_fingerprint
                or not validation.get("execution_id")
                or not validation.get("correlation_id")):
            raise ValueError("EVIDENCE_INVALID")
        source = validation.get("source")
        reference = None
        if isinstance(source, dict) and source.get("arquivo"):
            path = Path(source["arquivo"]).resolve()
            if not path.is_relative_to(context.project_root.resolve()):
                raise ValueError("EVIDENCE_INVALID")
            reference = {
                "file": str(path),
                "location": source.get("localizacao") or None,
                "type": source.get("tipo") or None,
                "sha256": source.get("sha256") or None,
                "mtime_ns": source.get("mtime_ns"),
            }
        return {
            "kind": "validation", "rule_id": validation["rule_id"],
            "status": validation["status"],
            "execution_id": validation["execution_id"],
            "correlation_id": validation["correlation_id"],
            "timestamp": validation.get("timestamp") or None,
            "source": reference,
        }
    if snapshot_id is not None:
        checked = inspect(context, snapshot_id)
        if checked["status"] not in {"INTACT", "CHANGED", "MISSING"}:
            raise ValueError("EVIDENCE_INVALID")
        manifest = checked["manifest"]
        file = manifest["files"][0]
        return {
            "kind": "snapshot", "snapshot_id": snapshot_id,
            "file": file["path"], "sha256": file["sha256"],
            "execution_id": manifest.get("execution_id"),
            "correlation_id": manifest.get("correlation_id"),
        }
    return None


def create(
    context: ValidationContext,
    description: str,
    severity: str,
    validation: Optional[Dict[str, Any]] = None,
    snapshot_id: Optional[str] = None,
    responsible: Optional[str] = None,
) -> Dict[str, Any]:
    root = _identity(context)
    if (
        not isinstance(description, str) or not description.strip()
        or severity not in {"ALERTA", "ERRO"}
        or responsible is not None and (
            not isinstance(responsible, str) or not responsible.strip()
        )
    ):
        raise ValueError("PENDING_INVALID")
    evidence = _evidence(context, validation, snapshot_id)
    if validation is not None and severity != validation["status"]:
        raise ValueError("PENDING_INVALID")
    timestamp = _now()
    item = {
        "id": uuid.uuid4().hex,
        "sob_id": context.sob_id,
        "dwg_path": str(Path(context.dwg_path).resolve()),
        "dwg_identity": context.dwg_identity,
        "database_fingerprint": context.database_fingerprint,
        "description": description.strip(),
        "origin": context.origin,
        "rule_id": evidence.get("rule_id") if evidence else None,
        "severity": severity,
        "status": "ABERTA",
        "responsible": responsible.strip() if responsible else None,
        "evidence": evidence,
        "execution_id": context.execution_id or None,
        "correlation_id": context.correlation_id or None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "history": [{
            "action": "criada", "timestamp": timestamp,
            "status": "ABERTA", "execution_id": context.execution_id or None,
            "correlation_id": context.correlation_id or None,
        }],
    }
    with _locked(root) as path:
        data = _read(path, context)
        data["items"].append(item)
        _write(path, data)
    return item


def list_pending(context: ValidationContext) -> list[Dict[str, Any]]:
    root = _identity(context)
    with _locked(root) as path:
        return [
            item for item in _read(path, context)["items"]
            if _matches(item, context)
        ]


def get(context: ValidationContext, pending_id: str) -> Dict[str, Any]:
    root = _identity(context)
    with _locked(root) as path:
        for item in _read(path, context)["items"]:
            if item["id"] == pending_id:
                if not _matches(item, context):
                    raise ValueError("CONTEXT_MISMATCH")
                return item
    raise ValueError("PENDING_NOT_FOUND")


def update(
    context: ValidationContext,
    pending_id: str,
    status: Optional[str] = None,
    description: Optional[str] = None,
    responsible: Optional[str] = None,
) -> Dict[str, Any]:
    root = _identity(context)
    if (
        (status is None and description is None and responsible is None)
        or (description is not None and (
            not isinstance(description, str) or not description.strip()
        ))
        or (responsible is not None and (
            not isinstance(responsible, str) or not responsible.strip()
        ))
    ):
        raise ValueError("PENDING_INVALID")
    with _locked(root) as path:
        data = _read(path, context)
        for item in data["items"]:
            if item["id"] != pending_id:
                continue
            if not _matches(item, context):
                raise ValueError("CONTEXT_MISMATCH")
            previous = item["status"]
            if status is not None and status not in TRANSITIONS[previous]:
                raise ValueError("INVALID_TRANSITION")
            if previous in {"RESOLVIDA", "DESCARTADA"} and status != "ABERTA":
                raise ValueError("INVALID_TRANSITION")
            if status is not None:
                item["status"] = status
            if description is not None:
                item["description"] = description.strip()
            if responsible is not None:
                item["responsible"] = responsible.strip()
            timestamp = _now()
            item["updated_at"] = timestamp
            action = (
                {"RESOLVIDA": "resolvida", "DESCARTADA": "descartada",
                 "ABERTA": "reaberta"}.get(status, "atualizada")
            )
            item["history"].append({
                "action": action, "timestamp": timestamp,
                "previous_status": previous, "status": item["status"],
                "execution_id": context.execution_id or None,
                "correlation_id": context.correlation_id or None,
            })
            _write(path, data)
            return item
    raise ValueError("PENDING_NOT_FOUND")
