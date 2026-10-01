import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import openpyxl
import pytest

from common.logging_config import SafeRotatingFileHandler, configurar_logging
from workspace.workspace_actions import WorkspaceActionDispatcher
from workspace.workspace_context_cli import (
    executar_acao_operacional,
    extrair_contexto_operacional,
)
from workspace.workspace_delivery import approve, generate, verify
from workspace.workspace_validation import ValidationContext, ValidationEngine
from workspace.workspace_versions import capture


def _project(tmp_path: Path) -> ValidationContext:
    root = tmp_path / "SOB_A057349839"
    root.mkdir()
    dwg = root / "PE_A057349839_DESENHO.dwg"
    dwg.write_bytes(b"synthetic drawing")
    (root / ".sob_state.json").write_text(
        json.dumps({
            "sob_id": "A057349839", "status": "CONCLUÍDO",
            "base_dwg": str(dwg),
        }),
        encoding="utf-8",
    )
    cqt = root / "CQT_A057349839.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "CQT ATUAL"
    sheet["A11"] = "synthetic test segment"
    sheet["C11"] = 1.0
    sheet["L11"] = 5.0
    book.save(cqt)
    book.close()
    return ValidationContext(
        execution_id="exec-A", correlation_id="corr-A",
        sob_id="A057349839", dwg_path=str(dwg),
        dwg_identity="fp-A", database_fingerprint="fp-A",
        project_root=root, cqt_path=cqt,
    )


def test_scope_requires_persisted_matching_dwg_and_sob(
    tmp_path: Path, simulated_host_protocol
):
    context = _project(tmp_path)
    unit_envelope = simulated_host_protocol(
        context.dwg_path, context.sob_id, context.dwg_identity,
        context.execution_id, context.correlation_id,
    )
    valid = extrair_contexto_operacional(
        dwg_path=context.dwg_path, sob_id_esperada=context.sob_id,
        require_project_scope=True, host_context=unit_envelope,
    )
    assert valid["project_scope_status"] == "Bound"
    mistaken = extrair_contexto_operacional(
        dwg_path=context.dwg_path, sob_id_esperada="B123456789",
        host_context=unit_envelope,
    )
    assert mistaken["project_scope_resolved"] is False
    assert mistaken["artefatos"] == []
    for sob_id in ("B123456789", None):
        blocked = executar_acao_operacional(
            "versao_capturar", dwg_path=context.dwg_path,
            sob_id_esperada=sob_id, dwg_identity=context.dwg_identity,
            alvo=context.cqt_path.name,
        )
        assert blocked["sucesso"] is False
        assert "execution_id" not in blocked
    (context.project_root / ".sob_state.json").unlink()
    blocked = executar_acao_operacional(
        "versao_capturar", dwg_path=context.dwg_path,
        sob_id_esperada=context.sob_id, dwg_identity=context.dwg_identity,
        alvo=context.cqt_path.name,
    )
    assert blocked["project_scope_status"] == "Unverified"
    assert not (context.project_root / ".auxcad_versions").exists()


def test_incomplete_manifest_does_not_override_host_xrecord_unit_contract(
    tmp_path: Path, simulated_host_protocol
):
    context = _project(tmp_path)
    (context.project_root / ".sob_state.json").write_text(
        json.dumps({"sob_id": context.sob_id, "status": "CONCLUÍDO"}),
        encoding="utf-8",
    )
    blocked = executar_acao_operacional(
        "validar", dwg_path=context.dwg_path,
        sob_id_esperada=context.sob_id,
        host_context=simulated_host_protocol(
            context.dwg_path, context.sob_id, context.dwg_identity
        ),
    )
    assert blocked["sucesso"] is True
    assert blocked["validation_results"][0]["status"] == "OK"


def test_validation_rejects_wrong_source_or_unbound_context(tmp_path: Path):
    context = _project(tmp_path)
    source = ValidationEngine().validate(context)[0].to_dict()["source"]
    assert source["sha256"] == hashlib.sha256(context.cqt_path.read_bytes()).hexdigest()
    assert source["mtime_ns"] == context.cqt_path.stat().st_mtime_ns
    with pytest.raises(ValueError, match="VALIDATION_SOURCE_CONTEXT_MISMATCH"):
        ValidationEngine().validate(
            replace(context, cqt_path=tmp_path / "CQT_OTHER.xlsx")
        )
    with pytest.raises(ValueError, match="VALIDATION_CONTEXT_INVALID"):
        ValidationEngine().validate(replace(context, sob_id="B123456789"))
    with pytest.raises(ValueError, match="VALIDATION_CONTEXT_INVALID"):
        ValidationEngine().validate(
            replace(context, database_fingerprint="fp-other")
        )
    context.cqt_path.unlink()
    unavailable = ValidationEngine().validate(context)[0].to_dict()
    assert unavailable["status"] == "NÃO DISPONÍVEL"
    assert unavailable["source"]["sha256"] is None


def test_package_accepts_same_hash_and_rejects_old_or_missing_source(
    tmp_path: Path,
):
    context = _project(tmp_path)
    results = [item.to_dict() for item in ValidationEngine().validate(context)]
    package = generate(context, [context.cqt_path.name], results)
    assert package["manifest"]["validations"][0]["source"]["sha256"] == (
        results[0]["source"]["sha256"]
    )
    assert approve(context, package["package_id"], confirmed=True)["state"] == "APROVADO"
    context.cqt_path.write_bytes(b"new synthetic bytes")
    with pytest.raises(ValueError, match="VALIDATION_SOURCE_CHANGED"):
        generate(context, [context.cqt_path.name], results)
    context.cqt_path.unlink()
    with pytest.raises(ValueError, match="PACKAGE_INCOMPLETE"):
        generate(context, [context.cqt_path.name], results)


def test_legacy_validation_without_hash_cannot_approve(tmp_path: Path):
    context = _project(tmp_path)
    result = ValidationEngine().validate(context)[0].to_dict()
    result["source"].pop("sha256")
    with pytest.raises(ValueError, match="VALIDATION_EVIDENCE_UNVERIFIABLE"):
        generate(context, [context.cqt_path.name], [result])


def test_cqt_exit_zero_requires_new_valid_workbook(
    tmp_path: Path, monkeypatch, simulated_host_protocol
):
    context = _project(tmp_path)
    def successful_process(workspace, **kwargs):
        book = openpyxl.load_workbook(context.cqt_path)
        book["CQT ATUAL"]["L11"] = 4.0
        book.save(context.cqt_path)
        book.close()
        return subprocess.Popen([sys.executable, "-c", "pass"])

    monkeypatch.setattr(WorkspaceActionDispatcher, "executar_cqt", successful_process)
    result = executar_acao_operacional(
        "cqt", dwg_path=context.dwg_path,
        sob_id_esperada=context.sob_id, wait_for_completion=True,
        host_context=simulated_host_protocol(
            context.dwg_path, context.sob_id, context.dwg_identity
        ),
    )
    assert result["exit_code"] == 0
    assert result["execution_state"] == "Concluído"
    assert any(item["path"] == str(context.cqt_path) for item in result["artifacts"])


def test_cqt_exit_nonzero_is_not_completed(
    tmp_path: Path, monkeypatch, simulated_host_protocol
):
    context = _project(tmp_path)

    def failed_process(workspace, **kwargs):
        return subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(3)"])

    monkeypatch.setattr(WorkspaceActionDispatcher, "executar_cqt", failed_process)
    result = executar_acao_operacional(
        "cqt", dwg_path=context.dwg_path,
        sob_id_esperada=context.sob_id, wait_for_completion=True,
        host_context=simulated_host_protocol(
            context.dwg_path, context.sob_id, context.dwg_identity
        ),
    )
    assert result["exit_code"] == 3
    assert result["execution_state"] == "Falhou"


def test_critical_audit_write_failure_is_not_success(
    tmp_path: Path, monkeypatch, simulated_host_protocol
):
    context = _project(tmp_path)
    configurar_logging(diretorio_logs=tmp_path)

    def fail_write(self, record):
        raise OSError("audit unavailable")

    monkeypatch.setattr(SafeRotatingFileHandler, "emitir_obrigatorio", fail_write)
    result = executar_acao_operacional(
        "versao_capturar", dwg_path=context.dwg_path,
        sob_id_esperada=context.sob_id, dwg_identity=context.dwg_identity,
        alvo=context.cqt_path.name,
        host_context=simulated_host_protocol(
            context.dwg_path, context.sob_id, context.dwg_identity
        ),
    )
    assert result["sucesso"] is False
    assert result["execution_state"] == "Falhou"
    assert "audit unavailable" in result["erro"]


def test_validation_audit_failure_cannot_return_technical_ok(
    tmp_path: Path, monkeypatch, simulated_host_protocol
):
    context = _project(tmp_path)
    configurar_logging(diretorio_logs=tmp_path)

    def fail_write(self, record):
        raise OSError("audit unavailable")

    monkeypatch.setattr(SafeRotatingFileHandler, "emitir_obrigatorio", fail_write)
    result = executar_acao_operacional(
        "validar", dwg_path=context.dwg_path,
        sob_id_esperada=context.sob_id,
        host_context=simulated_host_protocol(
            context.dwg_path, context.sob_id, context.dwg_identity
        ),
    )
    assert result["sucesso"] is False
    assert result["execution_state"] == "Falhou"
    assert "validation_results" not in result


def test_direct_snapshot_rejects_divergent_fingerprint(tmp_path: Path):
    context = _project(tmp_path)
    with pytest.raises(ValueError, match="CONTEXT_MISMATCH"):
        capture(
            replace(context, database_fingerprint="fp-other"),
            context.cqt_path.name,
        )


def test_approval_event_failure_revokes_unlogged_approval(
    tmp_path: Path, monkeypatch, simulated_host_protocol
):
    context = _project(tmp_path)
    configurar_logging(diretorio_logs=tmp_path)
    results = [item.to_dict() for item in ValidationEngine().validate(context)]
    package_id = generate(
        context, [context.cqt_path.name], results
    )["package_id"]

    def fail_write(self, record):
        raise OSError("audit unavailable")

    monkeypatch.setattr(SafeRotatingFileHandler, "emitir_obrigatorio", fail_write)
    result = executar_acao_operacional(
        "entrega_aprovar", dwg_path=context.dwg_path,
        sob_id_esperada=context.sob_id, dwg_identity=context.dwg_identity,
        package_id=package_id, approval_confirmed=True,
        host_context=simulated_host_protocol(
            context.dwg_path, context.sob_id, context.dwg_identity
        ),
    )

    assert result["sucesso"] is False
    assert result["execution_state"] == "Falhou"
    assert verify(context, package_id)["status"] == "REVOKED"