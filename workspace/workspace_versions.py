"""Snapshots opt-in de artefatos associados ao ProjectScope ativo."""

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from sob.sob_core import calcular_hash_arquivo
from workspace.workspace_validation import ValidationContext


STORE = ".auxcad_versions"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _file(root: Path, relative: str) -> Path:
    if (
        not isinstance(relative, str)
        or not relative
        or "\\" in relative
        or Path(relative).is_absolute()
        or any(part in (".", "..") for part in Path(relative).parts)
    ):
        raise ValueError("MANIFEST_INCONSISTENT")
    path = root / relative
    if path.resolve() == root or not path.resolve().is_relative_to(root):
        raise ValueError("MANIFEST_INCONSISTENT")
    if STORE in path.relative_to(root).parts:
        raise ValueError("MANIFEST_INCONSISTENT")
    return path


def _identity(context: ValidationContext) -> Path:
    root = context.project_root.resolve()
    dwg = Path(context.dwg_path).resolve() if context.dwg_path else None
    if not root.is_dir() or not dwg or not dwg.is_file() or dwg.parent != root:
        raise ValueError("DWG_MISMATCH")
    if not context.sob_id or not context.dwg_identity:
        raise ValueError("CONTEXT_MISMATCH")
    if (context.database_fingerprint
            and context.database_fingerprint.casefold()
            != context.dwg_identity.casefold()):
        raise ValueError("CONTEXT_MISMATCH")
    from workspace.workspace_context_cli import _resolver_project_scope

    scope = _resolver_project_scope(root, str(dwg), context.sob_id) if not context.host_verified else None
    if scope is not None and scope["status"] != "Bound":
        raise ValueError("CONTEXT_MISMATCH")
    return root


def _manifest(
    context: ValidationContext, relative: str, payload: Path
) -> Dict[str, Any]:
    stat = payload.stat()
    return {
        "schema": 1,
        "sob_id": context.sob_id,
        "dwg_path": str(Path(context.dwg_path).resolve()),
        "dwg_identity": context.dwg_identity,
        "revision": context.revision,
        "timestamp": _now(),
        "execution_id": context.execution_id or None,
        "correlation_id": context.correlation_id or None,
        "origin": context.origin,
        "files": [{
            "path": relative,
            "name": payload.name,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": calcular_hash_arquivo(payload),
            "type": payload.suffix.lower() or None,
        }],
    }


def capture(context: ValidationContext, relative: str) -> Dict[str, Any]:
    root = _identity(context)
    path = _file(root, relative)
    if not path.is_file():
        return {"status": "MISSING"}
    store = root / STORE
    if store.is_symlink():
        raise ValueError("MANIFEST_INCONSISTENT")
    store.mkdir(exist_ok=True)
    snapshot_id = uuid.uuid4().hex
    staging = store / f".{snapshot_id}.tmp"
    final = store / snapshot_id
    staging.mkdir()
    try:
        shutil.copy2(path, staging / "payload")
        manifest = _manifest(context, relative, path)
        entry = manifest["files"][0]
        if (
            calcular_hash_arquivo(staging / "payload") != entry["sha256"]
            or (staging / "payload").stat().st_size != entry["size"]
        ):
            return {"status": "CHANGED"}
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        staging.rename(final)
        return {
            "status": "CAPTURED",
            "snapshot_id": snapshot_id,
            "manifest": manifest,
        }
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _load(
    context: ValidationContext, snapshot_id: str
) -> tuple[Path, Path, Dict[str, Any]]:
    root = _identity(context)
    if not isinstance(snapshot_id, str) or len(snapshot_id) != 32 or any(
        char not in "0123456789abcdef" for char in snapshot_id
    ):
        raise ValueError("MANIFEST_INCONSISTENT")
    directory = root / STORE / snapshot_id
    if (root / STORE).is_symlink() or directory.is_symlink():
        raise ValueError("MANIFEST_INCONSISTENT")
    manifest = json.loads(
        (directory / "manifest.json").read_text(encoding="utf-8")
    )
    files = manifest["files"]
    if (manifest["schema"] != 1 or manifest["sob_id"] != context.sob_id
            or manifest["dwg_path"] != str(Path(context.dwg_path).resolve())
            or manifest["dwg_identity"] != context.dwg_identity):
        raise ValueError("CONTEXT_MISMATCH")
    if len(files) != 1:
        raise ValueError("MANIFEST_INCONSISTENT")
    entry = files[0]
    target = _file(root, entry["path"])
    if (entry["name"] != target.name or type(entry["size"]) is not int
            or entry["size"] < 0 or not isinstance(entry["sha256"], str)
            or len(entry["sha256"]) != 64 or any(
                char not in "0123456789abcdef" for char in entry["sha256"]
            ) or (directory / "payload").is_symlink()):
        raise ValueError("MANIFEST_INCONSISTENT")
    return directory / "payload", target, manifest


def inspect(context: ValidationContext, snapshot_id: str) -> Dict[str, Any]:
    try:
        payload, current, manifest = _load(context, snapshot_id)
        entry = manifest["files"][0]
        if (
            not payload.is_file()
            or payload.stat().st_size != entry["size"]
            or calcular_hash_arquivo(payload) != entry["sha256"]
        ):
            return {"status": "MANIFEST_INCONSISTENT"}
        status = "MISSING"
        if current.is_file():
            status = (
                "INTACT" if calcular_hash_arquivo(current) == entry["sha256"]
                else "CHANGED"
            )
        return {
            "status": status, "snapshot_id": snapshot_id, "manifest": manifest
        }
    except FileNotFoundError:
        return {"status": "MISSING_SNAPSHOT"}
    except (
        ValueError, KeyError, TypeError, json.JSONDecodeError, OSError
    ) as error:
        code = str(error)
        return {
            "status": code if code in ("CONTEXT_MISMATCH", "DWG_MISMATCH")
            else "MANIFEST_INCONSISTENT"
        }


def list_snapshots(
    context: ValidationContext, relative: str
) -> Dict[str, Any]:
    try:
        root = _identity(context)
        path = _file(root, relative)
        store = root / STORE
        if store.is_symlink():
            return {"status": "MANIFEST_INCONSISTENT"}
        entries = []
        for directory in sorted(store.iterdir()) if store.exists() else []:
            if not directory.is_dir() or directory.name.startswith("."):
                continue
            check = inspect(context, directory.name)
            if check["status"] in {
                "MANIFEST_INCONSISTENT", "MISSING_SNAPSHOT"
            }:
                return {"status": "MANIFEST_INCONSISTENT"}
            manifest = check.get("manifest", {})
            if any(
                entry.get("path") == relative
                for entry in manifest.get("files", [])
            ):
                entries.append({
                    "snapshot_id": directory.name,
                    "status": check["status"],
                    "revision": manifest.get("revision"),
                    "timestamp": manifest.get("timestamp"),
                })
        return {
            "status": "FOUND" if entries else "NO_SNAPSHOTS",
            "path": str(path), "snapshots": entries,
        }
    except (OSError, ValueError) as error:
        code = str(error)
        return {
            "status": code if code in ("CONTEXT_MISMATCH", "DWG_MISMATCH")
            else "MANIFEST_INCONSISTENT"
        }


def restore(context: ValidationContext, snapshot_id: str) -> Dict[str, Any]:
    check = inspect(context, snapshot_id)
    if check["status"] not in ("INTACT", "CHANGED", "MISSING"):
        return check
    try:
        payload, current, manifest = _load(context, snapshot_id)
        destination = current.with_name(
            f"{current.stem}.recuperado-{snapshot_id}{current.suffix}"
        )
        created = False
        verified = False
        try:
            with (
                payload.open("rb") as source,
                destination.open("xb") as output,
            ):
                created = True
                shutil.copyfileobj(source, output)
            expected_hash = manifest["files"][0]["sha256"]
            if calcular_hash_arquivo(destination) != expected_hash:
                return {"status": "MANIFEST_INCONSISTENT"}
            verified = True
            return {
                "status": "RESTORED", "path": str(destination),
                "snapshot_id": snapshot_id,
            }
        finally:
            if created and not verified:
                destination.unlink()
    except FileExistsError:
        return {"status": "DESTINATION_EXISTS"}
    except (OSError, ValueError) as error:
        return {"status": "RESTORE_FAILED", "error": str(error)}
