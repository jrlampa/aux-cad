import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import openpyxl
import pytest

from common.logging_config import configurar_logging
from workspace.workspace_context_cli import executar_acao_operacional
from workspace.workspace_pending import create, get, list_pending, update
from workspace.workspace_validation import ValidationContext, ValidationEngine
from workspace.workspace_versions import capture
from workspace import workspace_pending as pending


def project(parent: Path, sob: str, dwg_name: str = "") -> ValidationContext:
    root = parent / f"SOB_{sob}"
    root.mkdir(exist_ok=True)
    dwg = root / (dwg_name or f"PE_{sob}_DESENHO.dwg")
    dwg.write_bytes(b"test dwg")
    manifest = root / ".sob_state.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps({
                "sob_id": sob, "status": "CONCLUÍDO", "base_dwg": str(dwg)
            }),
            encoding="utf-8",
        )
    return ValidationContext(
        execution_id="exec-A", correlation_id="corr-A", sob_id=sob,
        dwg_path=str(dwg), dwg_identity=f"fp-{dwg.name}",
        database_fingerprint=f"fp-{dwg.name}", project_root=root,
        cqt_path=None, origin="oxcad.palette",
    )


def test_create_and_isolate_context(tmp_path: Path):
    first = project(tmp_path, "A057349839")
    other_sob = project(tmp_path, "B123456789")
    other_dwg = project(tmp_path, "A057349839", "OUTRO.dwg")
    item = create(first, "Verificar ligação", "ALERTA")
    assert item["status"] == "ABERTA"
    assert item["responsible"] is None and item["evidence"] is None
    assert item["execution_id"] == "exec-A"
    assert item["history"][0]["action"] == "criada"
    assert get(first, item["id"])["id"] == item["id"]
    assert [row["id"] for row in list_pending(first)] == [item["id"]]
    assert list_pending(other_sob) == []
    with pytest.raises(ValueError, match="CONTEXT_MISMATCH"):
        list_pending(other_dwg)
    with pytest.raises(ValueError, match="CONTEXT_MISMATCH"):
        update(other_dwg, item["id"], status="RESOLVIDA")
    with pytest.raises(ValueError, match="CONTEXT_MISMATCH"):
        get(replace(first, dwg_identity="stale"), item["id"])
    with pytest.raises(ValueError, match="CONTEXT_MISMATCH"):
        update(
            replace(first, database_fingerprint="stale"),
            item["id"], status="RESOLVIDA",
        )
    with pytest.raises(ValueError, match="CONTEXT_MISMATCH"):
        update(
            replace(first, sob_id="B123456789"), item["id"],
            status="RESOLVIDA",
        )
    with pytest.raises(ValueError, match="DWG_MISMATCH"):
        list_pending(replace(first, dwg_path=None))
    assert get(first, item["id"])["status"] == "ABERTA"


def test_transitions_history_and_not_found(tmp_path: Path):
    context = project(tmp_path, "A057349839")
    item = create(context, "Medir novamente", "ERRO")
    updated = update(
        context, item["id"], "EM_ANDAMENTO", responsible="Equipe local"
    )
    assert updated["responsible"] == "Equipe local"
    assert updated["updated_at"] >= updated["created_at"]
    assert update(context, item["id"], "RESOLVIDA")["status"] == "RESOLVIDA"
    with pytest.raises(ValueError, match="INVALID_TRANSITION"):
        update(context, item["id"], description="silenciosa")
    with pytest.raises(ValueError, match="INVALID_TRANSITION"):
        update(context, item["id"], "DESCARTADA")
    reopened = update(context, item["id"], "ABERTA")
    assert reopened["history"][-1]["action"] == "reaberta"
    discarded = update(
        context, item["id"], "DESCARTADA", description="Sem ação"
    )
    assert discarded["status"] == "DESCARTADA"
    assert discarded["description"] == "Sem ação"
    assert discarded["history"][-1]["action"] == "descartada"
    with pytest.raises(ValueError, match="PENDING_NOT_FOUND"):
        get(context, "absent")
    with pytest.raises(ValueError, match="PENDING_NOT_FOUND"):
        update(context, "absent", "RESOLVIDA")


def test_incomplete_evidence_stays_absent(tmp_path: Path):
    context = project(tmp_path, "A057349839")
    item = create(context, "Averiguar", "ALERTA")
    assert item["rule_id"] is None
    assert item["evidence"] is None
    with pytest.raises(ValueError, match="EVIDENCE_INVALID"):
        create(context, "Averiguar", "ALERTA", validation={"status": "ALERTA"})
    assert len(list_pending(context)) == 1


def test_explicit_validation_result_link_and_no_auto_creation(tmp_path: Path):
    context = project(tmp_path, "A057349839")
    workbook_path = context.project_root / "CQT_A057349839.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "CQT ATUAL"
    sheet["A11"] = "TRECHO-1"
    sheet["C11"] = 1.0
    sheet["L11"] = 6.25
    workbook.save(workbook_path)
    workbook.close()
    validation = ValidationEngine().validate(
        replace(context, cqt_path=workbook_path)
    )[0].to_dict()
    assert validation["status"] == "ALERTA"
    assert list_pending(context) == []

    item = create(
        context, "Revisar queda de tensão", "ALERTA", validation=validation
    )
    evidence = item["evidence"]
    assert item["rule_id"] == "CQT.TENSAO_MAXIMA"
    assert evidence["source"]["location"] == "CQT ATUAL!L11"
    assert evidence["source"]["file"] == str(workbook_path.resolve())
    assert evidence["source"]["sha256"] == validation["source"]["sha256"]
    assert evidence["execution_id"] == validation["execution_id"]
    assert evidence["correlation_id"] == validation["correlation_id"]
    assert "value" not in evidence
    with pytest.raises(ValueError, match="CONTEXT_MISMATCH"):
        create(
            replace(context, dwg_identity="stale"),
            "Outro", "ALERTA", validation=validation,
        )


def test_snapshot_reference_and_missing_evidence(tmp_path: Path):
    context = project(tmp_path, "A057349839")
    artifact = context.project_root / "artifact.txt"
    artifact.write_bytes(b"reference")
    snapshot_id = capture(context, artifact.name)["snapshot_id"]
    item = create(context, "Revisar arquivo", "ERRO", snapshot_id=snapshot_id)
    assert item["evidence"]["kind"] == "snapshot"
    assert item["evidence"]["file"] == artifact.name
    assert len(item["evidence"]["sha256"]) == 64
    with pytest.raises(ValueError, match="EVIDENCE_INVALID"):
        create(context, "Sem fonte", "ERRO", snapshot_id="f" * 32)


def test_corrupt_store_and_failed_write_never_resolve(
    tmp_path: Path, monkeypatch
):
    context = project(tmp_path, "A057349839")
    item = create(context, "Conferir", "ERRO")
    original_write = pending._write

    def fail_write(path, data):
        raise OSError("disk full")

    monkeypatch.setattr(pending, "_write", fail_write)
    with pytest.raises(OSError, match="disk full"):
        update(context, item["id"], "RESOLVIDA")
    monkeypatch.setattr(pending, "_write", original_write)
    assert get(context, item["id"])["status"] == "ABERTA"
    store = context.project_root / ".oxcad" / "pending.json"
    store.write_text("{invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="STORE_INVALID"):
        list_pending(context)
    with pytest.raises(ValueError, match="STORE_INVALID"):
        create(context, "Outra", "ALERTA")


def test_cli_lifecycle_jsonl_and_stale_context(
    tmp_path: Path, monkeypatch, simulated_host_protocol
):
    configurar_logging(diretorio_logs=tmp_path)
    first = project(tmp_path, "A057349839")
    second = project(tmp_path, "B123456789")

    def action(context, name, **kwargs):
        return executar_acao_operacional(
            name, dwg_path=context.dwg_path, sob_id_esperada=context.sob_id,
            dwg_identity=context.dwg_identity,
            execution_id=context.execution_id,
            correlation_id=context.correlation_id,
            execution_origin=context.origin,
            host_context=simulated_host_protocol(
                context.dwg_path, context.sob_id, context.dwg_identity,
                context.execution_id, context.correlation_id,
            ),
            **kwargs,
        )

    created = action(
        first, "pendencia_criar", pending_description="Verificar campo",
        pending_severity="ALERTA",
    )
    assert created["sucesso"] is True
    pending_id = created["pending_result"]["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        current = pool.submit(action, first, "pendencia_listar")
        stale = pool.submit(
            action, second, "pendencia_resolver", pending_id=pending_id
        )
        assert len(current.result()["pending_result"]) == 1
        assert stale.result()["sucesso"] is False
    current = action(first, "pendencia_obter", pending_id=pending_id)
    assert current["pending_result"]["status"] == "ABERTA"

    original_write = pending._write

    def fail_write(*args):
        raise OSError("disk full")

    monkeypatch.setattr(pending, "_write", fail_write)
    failed = action(first, "pendencia_resolver", pending_id=pending_id)
    assert failed["sucesso"] is False and failed["execution_state"] == "Falhou"
    monkeypatch.setattr(pending, "_write", original_write)
    current = action(first, "pendencia_obter", pending_id=pending_id)
    assert current["pending_result"]["status"] == "ABERTA"
    resolved = action(first, "pendencia_resolver", pending_id=pending_id)
    assert resolved["pending_result"]["status"] == "RESOLVIDA"
    lines = (tmp_path / "logs" / "application.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    events = [json.loads(line) for line in lines]
    assert any(
        event.get("pending_id") == pending_id
        and event.get("pending_status") == "RESOLVIDA"
        and event.get("execution_id") == "exec-A"
        and event.get("correlation_id") == "corr-A"
        for event in events
    )
    legacy = json.loads('{"level":"INFO","message":"old event"}')
    assert legacy["message"] == "old event"
