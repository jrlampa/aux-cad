import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from common.logging_config import configurar_logging
from workspace.workspace_context_cli import executar_acao_operacional
from workspace.workspace_validation import ValidationContext
from workspace import workspace_versions as versions


def project(parent: Path, sob: str) -> tuple[ValidationContext, Path]:
    root = parent / f"SOB_{sob}"
    root.mkdir()
    dwg = root / f"PE_{sob}_DESENHO.dwg"
    dwg.write_bytes(b"test dwg")
    (root / ".sob_state.json").write_text(
        json.dumps({"sob_id": sob, "status": "CONCLUÍDO", "base_dwg": str(dwg)}),
        encoding="utf-8",
    )
    artifact = root / "output.txt"
    artifact.write_bytes(b"saved content")
    return ValidationContext(
        execution_id="exec-1", correlation_id="corr-1", sob_id=sob,
        dwg_path=str(dwg), dwg_identity=f"fp-{sob}",
        database_fingerprint=f"fp-{sob}", project_root=root,
        cqt_path=None,
    ), artifact


def test_manifest_integrity_and_reproducible_hash(tmp_path: Path):
    context, artifact = project(tmp_path, "A057349839")
    captured = versions.capture(context, artifact.name)
    manifest = captured["manifest"]
    entry = manifest["files"][0]
    assert manifest["sob_id"] == context.sob_id
    assert manifest["dwg_identity"] == context.dwg_identity
    assert manifest["revision"] is None
    assert manifest["execution_id"] == "exec-1"
    assert manifest["correlation_id"] == "corr-1"
    assert manifest["timestamp"].endswith("Z")
    assert entry["path"] == entry["name"] == "output.txt"
    assert entry["size"] == len(b"saved content")
    assert entry["mtime_ns"] == artifact.stat().st_mtime_ns
    assert entry["sha256"] == hashlib.sha256(b"saved content").hexdigest()
    assert versions.inspect(context, captured["snapshot_id"])["status"] == "INTACT"
    assert versions.list_snapshots(context, artifact.name)["snapshots"][0]["revision"] is None


def test_changed_same_size_and_missing_are_distinct(tmp_path: Path):
    context, artifact = project(tmp_path, "A057349839")
    snapshot_id = versions.capture(context, artifact.name)["snapshot_id"]
    artifact.write_bytes(b"other content")
    assert versions.inspect(context, snapshot_id)["status"] == "CHANGED"
    artifact.unlink()
    assert versions.inspect(context, snapshot_id)["status"] == "MISSING"


def test_corrupt_payload_and_manifest_block_restore(tmp_path: Path):
    context, artifact = project(tmp_path, "A057349839")
    snapshot_id = versions.capture(context, artifact.name)["snapshot_id"]
    directory = context.project_root / versions.STORE / snapshot_id
    (directory / "payload").write_bytes(b"tampered")
    assert versions.inspect(context, snapshot_id)["status"] == "MANIFEST_INCONSISTENT"
    assert versions.restore(context, snapshot_id)["status"] == "MANIFEST_INCONSISTENT"
    (directory / "manifest.json").write_text("{bad", encoding="utf-8")
    assert versions.inspect(context, snapshot_id)["status"] == "MANIFEST_INCONSISTENT"
    assert artifact.read_bytes() == b"saved content"


def test_manifest_path_tamper_and_unverified_output_are_rejected(tmp_path: Path, monkeypatch):
    context, artifact = project(tmp_path, "A057349839")
    snapshot_id = versions.capture(context, artifact.name)["snapshot_id"]
    manifest_path = context.project_root / versions.STORE / snapshot_id / "manifest.json"
    original = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(original)
    manifest["files"][0]["path"] = "../outside.txt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert versions.inspect(context, snapshot_id)["status"] == "MANIFEST_INCONSISTENT"
    assert versions.list_snapshots(context, artifact.name)["status"] == "MANIFEST_INCONSISTENT"
    manifest_path.write_text(original, encoding="utf-8")
    manifest_path.unlink()
    assert versions.list_snapshots(context, artifact.name)["status"] == "MANIFEST_INCONSISTENT"
    manifest_path.write_text(original, encoding="utf-8")

    real_hash = versions.calcular_hash_arquivo
    destination_name = f"output.recuperado-{snapshot_id}.txt"

    def fail_destination_hash(path):
        if Path(path).name == destination_name:
            raise OSError("failed to verify copy")
        return real_hash(path)

    monkeypatch.setattr(versions, "calcular_hash_arquivo", fail_destination_hash)
    assert versions.restore(context, snapshot_id)["status"] == "RESTORE_FAILED"
    assert not (context.project_root / destination_name).exists()


def test_sob_dwg_and_project_boundaries(tmp_path: Path):
    context, artifact = project(tmp_path, "A057349839")
    other, other_artifact = project(tmp_path, "B123456789")
    snapshot_id = versions.capture(context, artifact.name)["snapshot_id"]
    assert versions.inspect(context, "f" * 32)["status"] == "MISSING_SNAPSHOT"
    assert versions.restore(other, snapshot_id)["status"] == "MISSING_SNAPSHOT"
    assert versions.list_snapshots(other, other_artifact.name)["status"] == "NO_SNAPSHOTS"
    from dataclasses import replace
    assert versions.inspect(replace(context, sob_id=other.sob_id), snapshot_id)["status"] == "CONTEXT_MISMATCH"
    assert versions.inspect(replace(context, dwg_identity=other.dwg_identity), snapshot_id)["status"] == "CONTEXT_MISMATCH"
    assert versions.inspect(replace(context, dwg_path=other.dwg_path), snapshot_id)["status"] == "DWG_MISMATCH"
    assert other_artifact.read_bytes() == b"saved content"


def test_scope_rejection_does_not_start_version_execution(tmp_path: Path):
    context, artifact = project(tmp_path, "A057349839")
    result = executar_acao_operacional(
        "versao_capturar", dwg_path=context.dwg_path,
        sob_id_esperada="B123456789", dwg_identity=context.dwg_identity,
        alvo=artifact.name,
    )
    assert result["sucesso"] is False
    assert result["estado"] == "Requer especificação"
    assert "execution_id" not in result
    assert not (context.project_root / versions.STORE).exists()


def test_restore_never_overwrites_current_or_prior_recovery(tmp_path: Path):
    context, artifact = project(tmp_path, "A057349839")
    snapshot_id = versions.capture(context, artifact.name)["snapshot_id"]
    artifact.write_bytes(b"newer content")
    restored = versions.restore(context, snapshot_id)
    assert restored["status"] == "RESTORED"
    assert Path(restored["path"]).read_bytes() == b"saved content"
    assert artifact.read_bytes() == b"newer content"
    assert versions.restore(context, snapshot_id)["status"] == "DESTINATION_EXISTS"
    assert Path(restored["path"]).read_bytes() == b"saved content"


def test_copy_failure_cleans_partial_destination(tmp_path: Path, monkeypatch):
    context, artifact = project(tmp_path, "A057349839")
    snapshot_id = versions.capture(context, artifact.name)["snapshot_id"]
    artifact.write_bytes(b"newer content")

    def fail_copy(source, target):
        target.write(b"partial")
        raise OSError("interrupted")

    monkeypatch.setattr(versions.shutil, "copyfileobj", fail_copy)
    result = versions.restore(context, snapshot_id)
    assert result["status"] == "RESTORE_FAILED"
    assert artifact.read_bytes() == b"newer content"
    assert list(context.project_root.glob("*.recuperado-*")) == []


def test_traversal_and_missing_source_do_not_create_snapshot(tmp_path: Path):
    context, artifact = project(tmp_path, "A057349839")
    with pytest.raises(ValueError, match="MANIFEST_INCONSISTENT"):
        versions.capture(context, "../other.txt")
    assert versions.capture(context, "missing.txt")["status"] == "MISSING"
    assert artifact.read_bytes() == b"saved content"


def test_cli_scope_jsonl_and_context_isolation(
    tmp_path: Path, simulated_host_protocol
):
    configurar_logging(diretorio_logs=tmp_path)
    context, artifact = project(tmp_path, "A057349839")
    other, _ = project(tmp_path, "B123456789")

    def action(ctx, name, **kwargs):
        return executar_acao_operacional(
            name, dwg_path=ctx.dwg_path, sob_id_esperada=ctx.sob_id,
            dwg_identity=ctx.dwg_identity, execution_id=ctx.execution_id,
            correlation_id=ctx.correlation_id, execution_origin="oxcad.palette", **kwargs,
            host_context=simulated_host_protocol(
                ctx.dwg_path, ctx.sob_id, ctx.dwg_identity,
                ctx.execution_id, ctx.correlation_id,
            ),
        )

    captured = action(context, "versao_capturar", alvo=artifact.name)
    assert captured["sucesso"] is True
    snapshot_id = captured["version_result"]["snapshot_id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(action, context, "versao_verificar", snapshot_id=snapshot_id)
        second = pool.submit(action, other, "versao_recuperar", snapshot_id=snapshot_id)
        assert first.result()["version_result"]["status"] == "INTACT"
        assert second.result()["version_result"]["status"] == "MISSING_SNAPSHOT"
    event = next(
        json.loads(line) for line in (tmp_path / "logs" / "application.jsonl").read_text(
            encoding="utf-8"
        ).splitlines() if '"version_manifest"' in line
    )
    assert event["execution_id"] == "exec-1"
    assert event["correlation_id"] == "corr-1"
    assert event["origin"] == "oxcad.palette"
    assert event["version_manifest"]["files"][0]["sha256"] == hashlib.sha256(b"saved content").hexdigest()
    artifact.write_bytes(b"newer content")
    recovered = action(context, "versao_recuperar", snapshot_id=snapshot_id)
    assert recovered["version_result"]["status"] == "RESTORED"
    events = [json.loads(line) for line in (tmp_path / "logs" / "application.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()]
    assert any(item.get("version_status") == "RESTORED" and item.get("origin") == "oxcad.palette"
               for item in events)
    assert json.loads('{"level":"INFO","message":"old event"}')["message"] == "old event"