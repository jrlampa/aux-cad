"""Manifestos verificáveis de entrega associados ao ProjectScope OXCAD."""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sob.sob_core import calcular_hash_arquivo
from workspace.workspace_pending import _locked, _matches, _read
from workspace.workspace_validation import ValidationContext
from workspace.workspace_versions import _file, _identity, _manifest, inspect


STATUSES = {"OK", "ALERTA", "ERRO", "NÃO DISPONÍVEL"}
STORE = "deliveries"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(data: Dict[str, Any]) -> str:
    encoded = json.dumps(
        data, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _context_root(
    context: ValidationContext, require_file: bool = True
) -> Path:
    if require_file:
        return _identity(context)
    root = context.project_root.resolve()
    dwg = Path(context.dwg_path).resolve() if context.dwg_path else None
    if not root.is_dir() or dwg is None or dwg.parent != root:
        raise ValueError("DWG_MISMATCH")
    if not context.sob_id or not context.dwg_identity:
        raise ValueError("CONTEXT_MISMATCH")
    from workspace.workspace_context_cli import _resolver_project_scope

    scope = _resolver_project_scope(
        root, str(dwg), context.sob_id, require_existing_dwg=False
    ) if not context.host_verified else None
    if scope is not None and scope["status"] != "Bound":
        raise ValueError("CONTEXT_MISMATCH")
    return root


def _directory(root: Path, package_id: str) -> Path:
    if (not isinstance(package_id, str) or len(package_id) != 32
            or any(char not in "0123456789abcdef" for char in package_id)):
        raise ValueError("PACKAGE_INVALID")
    store = root / ".oxcad" / STORE
    if (root / ".oxcad").is_symlink() or store.is_symlink():
        raise ValueError("PACKAGE_INVALID")
    directory = store / package_id
    if directory.is_symlink():
        raise ValueError("PACKAGE_INVALID")
    return directory


def _pending(context: ValidationContext, path: Path) -> list[Dict[str, Any]]:
    items = _read(path, context)["items"]
    return sorted(({
        "id": item["id"], "status": item["status"],
        "severity": item["severity"], "updated_at": item["updated_at"],
        "evidence": item.get("evidence"),
    } for item in items if _matches(item, context)),
        key=lambda item: item["id"])


def _validation(context: ValidationContext, results: list[Dict[str, Any]],
                included: set[str]) -> list[Dict[str, Any]]:
    if not isinstance(results, list) or not results:
        raise ValueError("PACKAGE_INCOMPLETE")
    validated = []
    root = context.project_root.resolve()
    for result in results:
        if (
            not isinstance(result, dict)
            or result.get("status") not in STATUSES
            or not result.get("rule_id") or not result.get("timestamp")
            or result.get("sob_id") != context.sob_id
            or result.get("dwg_path") != str(
                Path(context.dwg_path).resolve()
            )
            or result.get("dwg_identity") != context.dwg_identity
            or result.get("database_fingerprint")
            != context.database_fingerprint
            or not result.get("execution_id")
            or not result.get("correlation_id")
        ):
            raise ValueError("VALIDATION_CONTEXT_MISMATCH")
        source = result.get("source")
        source_ref = None
        if isinstance(source, dict) and source.get("arquivo"):
            path = Path(source["arquivo"]).resolve()
            if not path.is_relative_to(root):
                raise ValueError("PACKAGE_INCOMPLETE")
            relative = path.relative_to(root).as_posix()
            if relative not in included and result["status"] != "NÃO DISPONÍVEL":
                raise ValueError("PACKAGE_INCOMPLETE")
            source_hash = source.get("sha256")
            if relative in included and source_hash is not None:
                if calcular_hash_arquivo(path) != source_hash:
                    raise ValueError("VALIDATION_SOURCE_CHANGED")
            elif result["status"] != "NÃO DISPONÍVEL":
                raise ValueError("VALIDATION_EVIDENCE_UNVERIFIABLE")
            source_ref = {
                "file": relative,
                "location": source.get("localizacao") or None,
                "type": source.get("tipo") or None,
                "sha256": source_hash,
                "mtime_ns": source.get("mtime_ns"),
            }
        elif result["status"] != "NÃO DISPONÍVEL":
            raise ValueError("VALIDATION_EVIDENCE_UNVERIFIABLE")
        validated.append({
            "rule_id": result["rule_id"], "status": result["status"],
            "timestamp": result["timestamp"], "source": source_ref,
            "execution_id": result["execution_id"],
            "correlation_id": result["correlation_id"],
        })
    return sorted(validated, key=lambda item: (
        item["rule_id"], item["status"], item["timestamp"]
    ))


def _snapshot_refs(context: ValidationContext, snapshot_ids: list[str],
                   entries: Dict[str, Dict[str, Any]]) -> list[Dict[str, str]]:
    references = []
    for snapshot_id in snapshot_ids:
        checked = inspect(context, snapshot_id)
        if checked["status"] != "INTACT":
            raise ValueError("SNAPSHOT_INCOMPATIBLE")
        source = checked["manifest"]["files"][0]
        path = source["path"]
        if path not in entries or source["sha256"] != entries[path]["sha256"]:
            raise ValueError("SNAPSHOT_INCOMPATIBLE")
        references.append({"snapshot_id": snapshot_id, "path": path,
                           "sha256": source["sha256"]})
    return sorted(references, key=lambda item: item["snapshot_id"])


def generate(context: ValidationContext, artifacts: list[str],
             validations: list[Dict[str, Any]],
             snapshot_ids: Optional[list[str]] = None) -> Dict[str, Any]:
    root = _context_root(context)
    dwg_relative = (
        Path(context.dwg_path).resolve().relative_to(root).as_posix()
    )
    if (not isinstance(artifacts, list) or not artifacts
            or not all(isinstance(name, str) for name in artifacts)):
        raise ValueError("PACKAGE_INCOMPLETE")
    selected = set(artifacts)
    selected.add(dwg_relative)
    if not selected - {dwg_relative}:
        raise ValueError("PACKAGE_INCOMPLETE")
    files: Dict[str, Dict[str, Any]] = {}
    for relative in sorted(selected):
        path = _file(root, relative)
        if path.relative_to(root).parts[0] == ".oxcad" or not path.is_file():
            raise ValueError("PACKAGE_INCOMPLETE")
        before = path.stat()
        entry = _manifest(context, relative, path)["files"][0]
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (
            after.st_size, after.st_mtime_ns
        ):
            raise ValueError("PACKAGE_CHANGED")
        files[relative] = entry
    linked = _validation(context, validations, set(files))
    if snapshot_ids is not None and (
        not isinstance(snapshot_ids, list)
        or len(snapshot_ids) != len(set(snapshot_ids))
    ):
        raise ValueError("SNAPSHOT_INCOMPATIBLE")
    snapshots = _snapshot_refs(context, snapshot_ids or [], files)
    with _locked(root) as pending_path:
        pendings = _pending(context, pending_path)
        package_id = uuid.uuid4().hex
        directory = _directory(root, package_id)
        directory.parent.mkdir(exist_ok=True)
        staging = directory.with_name(f".{package_id}.tmp")
        staging.mkdir()
        try:
            manifest = {
                "schema": 1, "package_id": package_id,
                "sob_id": context.sob_id,
                "dwg_path": str(Path(context.dwg_path).resolve()),
                "dwg_identity": context.dwg_identity,
                "database_fingerprint": context.database_fingerprint,
                "revision": context.revision, "timestamp": _now(),
                "execution_id": context.execution_id or None,
                "correlation_id": context.correlation_id or None,
                "origin": context.origin,
                "files": list(files.values()), "validations": linked,
                "pending": pendings, "snapshots": snapshots,
            }
            (staging / "manifest.json").write_text(
                json.dumps(
                    manifest, sort_keys=True, ensure_ascii=False, indent=2
                ),
                encoding="utf-8",
            )
            (staging / "manifest.sha256").write_text(
                _digest(manifest), encoding="ascii"
            )
            staging.rename(directory)
        finally:
            if staging.exists():
                import shutil
                shutil.rmtree(staging)
        try:
            checked = _check(context, package_id, pending_path)
            if checked["status"] != "UNAPPROVED":
                raise ValueError("PACKAGE_CHANGED")
        except Exception:
            import shutil
            shutil.rmtree(directory)
            raise
        return {"package_id": package_id, "manifest": manifest,
                "manifest_sha256": _digest(manifest), "status": "UNAPPROVED"}


def _load(
    context: ValidationContext, package_id: str
) -> tuple[Path, Dict[str, Any]]:
    directory = _directory(context.project_root.resolve(), package_id)
    path = directory / "manifest.json"
    if path.is_symlink():
        raise ValueError("PACKAGE_INVALID")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("PACKAGE_INVALID")
    if (manifest.get("sob_id") != context.sob_id
            or manifest.get("dwg_path") != str(
                Path(context.dwg_path).resolve())
            or manifest.get("dwg_identity") != context.dwg_identity
            or manifest.get("database_fingerprint")
            != context.database_fingerprint):
        raise ValueError("CONTEXT_MISMATCH")
    if (manifest.get("schema") != 1 or manifest.get("package_id") != package_id
            or not isinstance(manifest.get("files"), list)
            or not isinstance(manifest.get("validations"), list)
            or not isinstance(manifest.get("pending"), list)
            or not isinstance(manifest.get("snapshots"), list)):
        raise ValueError("PACKAGE_INVALID")
    digest_path = directory / "manifest.sha256"
    if (digest_path.is_symlink()
            or digest_path.read_text(encoding="ascii") != _digest(manifest)):
        raise ValueError("PACKAGE_INVALID")
    return directory, manifest


def _check(context: ValidationContext, package_id: str,
           pending_path: Path) -> Dict[str, Any]:
    root = context.project_root.resolve()
    directory, manifest = _load(context, package_id)
    dwg_relative = (
        Path(context.dwg_path).resolve().relative_to(root).as_posix()
    )
    files = {}
    file_results = []
    for entry in manifest["files"]:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("path"), str)
        ):
            raise ValueError("PACKAGE_INVALID")
        path = _file(root, entry["path"])
        relative = entry["path"]
        if (
            relative in files or path.relative_to(root).parts[0] == ".oxcad"
            or entry.get("name") != path.name
            or type(entry.get("size")) is not int or entry["size"] < 0
            or not isinstance(entry.get("sha256"), str)
            or len(entry["sha256"]) != 64
            or any(
                char not in "0123456789abcdef" for char in entry["sha256"]
            )
        ):
            raise ValueError("PACKAGE_INVALID")
        files[relative] = entry
        status = "MISSING" if not path.is_file() else (
            "INTACT" if path.stat().st_size == entry["size"]
            and calcular_hash_arquivo(path) == entry["sha256"] else "DIVERGENT"
        )
        file_results.append({"path": relative, "status": status})
    if dwg_relative not in files or len(files) < 2:
        raise ValueError("PACKAGE_INVALID")
    if (not manifest["validations"] or any(
        not isinstance(item, dict) or item.get("status") not in STATUSES
        or not item.get("rule_id") for item in manifest["validations"]
    )):
        raise ValueError("PACKAGE_INVALID")
    for result in manifest["validations"]:
        source = result.get("source")
        if (source is not None and (
            not isinstance(source, dict)
            or source.get("file") not in files
            and result["status"] != "NÃO DISPONÍVEL"
        )):
            raise ValueError("PACKAGE_INVALID")
        if result["status"] != "NÃO DISPONÍVEL" and (
            source is None or source.get("sha256")
            != files[source["file"]]["sha256"]
        ):
            raise ValueError("PACKAGE_INVALID")
    for reference in manifest["snapshots"]:
        if (not isinstance(reference, dict)
                or reference.get("path") not in files
                or reference.get("sha256")
                != files[reference["path"]]["sha256"]):
            raise ValueError("PACKAGE_INVALID")
        checked = inspect(context, reference.get("snapshot_id"))
        if checked["status"] not in {"INTACT", "CHANGED", "MISSING"}:
            raise ValueError("PACKAGE_INVALID")
        source = checked["manifest"]["files"][0]
        if (source["path"] != reference["path"]
                or source["sha256"] != reference["sha256"]):
            raise ValueError("PACKAGE_INVALID")
    pending_changed = _pending(context, pending_path) != manifest["pending"]
    approval_path = directory / "approval.json"
    if approval_path.is_symlink():
        raise ValueError("PACKAGE_INVALID")
    approval = None
    if approval_path.exists():
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        if (not isinstance(approval, dict) or approval.get("schema") != 1
                or approval.get("package_id") != package_id
                or approval.get("manifest_sha256") != _digest(manifest)
            or approval.get("sob_id") != manifest["sob_id"]
            or approval.get("dwg_path") != manifest["dwg_path"]
            or approval.get("dwg_identity") != manifest["dwg_identity"]
            or approval.get("database_fingerprint")
            != manifest["database_fingerprint"]
            or approval.get("revision") != manifest["revision"]
                or approval.get("state") not in {"APROVADO", "REVOGADO"}):
            raise ValueError("PACKAGE_INVALID")
    if any(item["status"] == "MISSING" for item in file_results):
        status = "MISSING"
    elif pending_changed or any(
        item["status"] == "DIVERGENT" for item in file_results
    ):
        status = "DIVERGENT"
    elif approval is None:
        status = "UNAPPROVED"
    elif approval["state"] == "REVOGADO":
        status = "REVOKED"
    else:
        status = "CONFIRMED"
    return {"status": status, "approval_valid": status == "CONFIRMED",
            "approval": approval, "files": file_results,
            "pending_changed": pending_changed, "package_id": package_id,
            "manifest": manifest, "manifest_sha256": _digest(manifest)}


def verify(context: ValidationContext, package_id: str) -> Dict[str, Any]:
    try:
        root = _context_root(context, require_file=False)
    except ValueError as error:
        return {"status": str(error), "approval_valid": False}
    with _locked(root) as pending_path:
        try:
            return _check(context, package_id, pending_path)
        except FileNotFoundError:
            return {"status": "PACKAGE_NOT_FOUND", "approval_valid": False}
        except (
            ValueError, KeyError, TypeError, json.JSONDecodeError, OSError
        ) as error:
            if str(error) == "CONTEXT_MISMATCH":
                return {"status": "CONTEXT_MISMATCH", "approval_valid": False}
            return {"status": "INVALID", "approval_valid": False}


def _write_approval(path: Path, data: Dict[str, Any]) -> None:
    temp = path.with_name(f".approval-{uuid.uuid4().hex}.tmp")
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


def approve(
    context: ValidationContext, package_id: str, confirmed: bool = False,
    acknowledge_issues: bool = False,
    decision_note: Optional[str] = None,
) -> Dict[str, Any]:
    root = _context_root(context)
    if confirmed is not True:
        raise ValueError("APPROVAL_NOT_CONFIRMED")
    with _locked(root) as pending_path:
        checked = _check(context, package_id, pending_path)
        if checked["status"] != "UNAPPROVED":
            raise ValueError("PACKAGE_NOT_APPROVABLE")
        manifest = checked["manifest"]
        issues = {
            "errors": [item["rule_id"] for item in manifest["validations"]
                       if item["status"] == "ERRO"],
            "open_pending": [item["id"] for item in manifest["pending"]
                             if item["status"] in {"ABERTA", "EM_ANDAMENTO"}],
        }
        if any(issues.values()) and (
            acknowledge_issues is not True
            or not isinstance(decision_note, str)
            or not decision_note.strip()
        ):
            raise ValueError("ISSUES_REQUIRE_DECISION")
        directory = _directory(root, package_id)
        path = directory / "approval.json"
        if path.exists() or path.is_symlink():
            raise ValueError("APPROVAL_ALREADY_RECORDED")
        timestamp = _now()
        approval = {
            "schema": 1, "package_id": package_id,
            "state": "APROVADO", "approved_at": timestamp,
            "manifest_sha256": checked["manifest_sha256"],
            "sob_id": context.sob_id,
            "dwg_path": str(Path(context.dwg_path).resolve()),
            "dwg_identity": context.dwg_identity,
            "database_fingerprint": context.database_fingerprint,
            "revision": manifest["revision"],
            "execution_id": context.execution_id or None,
            "correlation_id": context.correlation_id or None,
            "origin": context.origin, "approver": None,
            "issues": issues,
            "issues_acknowledged": bool(any(issues.values())),
            "decision_note": decision_note.strip() if decision_note else None,
            "revocation": None,
        }
        _write_approval(path, approval)
        return approval


def revoke(context: ValidationContext, package_id: str,
           reason: str) -> Dict[str, Any]:
    root = _context_root(context, require_file=False)
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("REVOCATION_REASON_REQUIRED")
    with _locked(root) as pending_path:
        checked = _check(context, package_id, pending_path)
        approval = checked["approval"]
        if approval is None or approval["state"] != "APROVADO":
            raise ValueError("APPROVAL_NOT_ACTIVE")
        approval["state"] = "REVOGADO"
        approval["revocation"] = {
            "timestamp": _now(), "reason": reason.strip(),
            "execution_id": context.execution_id or None,
            "correlation_id": context.correlation_id or None,
            "origin": context.origin,
        }
        path = _directory(root, package_id) / "approval.json"
        _write_approval(path, approval)
        return approval
