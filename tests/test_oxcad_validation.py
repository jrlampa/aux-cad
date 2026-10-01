from concurrent.futures import ThreadPoolExecutor
from threading import Event
from pathlib import Path
import json

import openpyxl
from common.logging_config import configurar_logging
from workspace.workspace_context_cli import executar_acao_operacional
from workspace.workspace_validation import (
    CqtMaximumVoltageDropRule,
    ValidationContext,
    ValidationEngine,
    ValidationRule,
    ValidationSource,
    ValidationStatus,
)


def _context(
    root: Path,
    cqt_path: Path | None,
    execution_id: str = "exec-a",
    sob_id: str = "A057349839",
):
    root.mkdir(parents=True, exist_ok=True)
    dwg = root / f"PE_{sob_id}_DESENHO.dwg"
    if not dwg.exists():
        dwg.write_bytes(b"synthetic DWG for validation")
    (root / ".sob_state.json").write_text(
        json.dumps({
            "sob_id": sob_id, "status": "CONCLUÍDO", "base_dwg": str(dwg)
        }), encoding="utf-8",
    )
    return ValidationContext(
        execution_id=execution_id,
        correlation_id=f"corr-{execution_id}",
        sob_id=sob_id,
        dwg_path=str(dwg),
        dwg_identity=f"fingerprint-{sob_id}",
        database_fingerprint=f"fingerprint-{sob_id}",
        project_root=root,
        cqt_path=cqt_path,
    )


def _write_cqt(path: Path, values: dict[str, float | str]) -> Path:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "CQT ATUAL"
    for index, (segment, value) in enumerate(values.items(), start=11):
        sheet.cell(index, 1, segment)
        sheet.cell(index, 3, 1.0)
        sheet.cell(index, 12, value)
    workbook.save(path)
    workbook.close()
    return path


def test_cqt_rule_returns_ok_for_cached_value_within_existing_limit(
    tmp_path: Path,
):
    path = _write_cqt(tmp_path / "CQT_A057349839.xlsx", {"A": 5.9})

    result = ValidationEngine().validate(_context(tmp_path, path))[0]

    assert result.status == ValidationStatus.OK
    assert result.value == {"percentual": 5.9, "trecho": "A"}
    assert result.criterion == {"operator": "<=", "value": 6.0, "unit": "%"}


def test_cqt_rule_returns_alerta_above_existing_limit(tmp_path: Path):
    path = _write_cqt(tmp_path / "CQT_A057349839.xlsx", {"A": 6.25})

    result = ValidationEngine().validate(_context(tmp_path, path))[0]

    assert result.status == ValidationStatus.ALERTA
    assert result.value["percentual"] == 6.25


def test_cqt_rule_returns_erro_for_non_numeric_stored_value(tmp_path: Path):
    path = _write_cqt(tmp_path / "CQT_A057349839.xlsx", {"A": "sem leitura"})

    result = ValidationEngine().validate(_context(tmp_path, path))[0]

    assert result.status == ValidationStatus.ERRO
    assert result.value == "sem leitura"
    assert result.source.localizacao == "CQT ATUAL!L11"


def test_cqt_rule_returns_nao_disponivel_when_file_or_cached_values_are_missing(
    tmp_path: Path,
):
    missing = ValidationEngine().validate(
        _context(tmp_path, tmp_path / "nao-existe.xlsm")
    )[0]
    empty_path = _write_cqt(tmp_path / "CQT_vazio.xlsx", {})
    empty = ValidationEngine().validate(_context(tmp_path, empty_path))[0]

    assert missing.status == ValidationStatus.NAO_DISPONIVEL
    assert empty.status == ValidationStatus.NAO_DISPONIVEL


def test_result_preserves_real_source_cell_and_full_project_context(
    tmp_path: Path,
):
    path = _write_cqt(tmp_path / "CQT_A057349839.xlsx", {"A": 3.85})
    context = _context(tmp_path, path, "exec-evidence")

    result = ValidationEngine().validate(context)[0]

    assert result.source.tipo == "excel"
    assert result.source.arquivo == str(path)
    assert result.source.localizacao == "CQT ATUAL!L11"
    assert result.context.execution_id == "exec-evidence"
    assert result.context.correlation_id == "corr-exec-evidence"
    assert result.context.sob_id == "A057349839"
    assert result.context.database_fingerprint == "fingerprint-A057349839"
    assert result.context.origin == "workspace.cli"
    assert result.timestamp.endswith("Z")


def test_concurrent_validations_keep_independent_execution_contexts(
    tmp_path: Path,
):
    root_a = tmp_path / "A"
    root_b = tmp_path / "B"
    root_a.mkdir()
    root_b.mkdir()
    path_a = _write_cqt(root_a / "A.xlsx", {"A": 2.0})
    path_b = _write_cqt(root_b / "B.xlsx", {"A": 7.0})
    engine = ValidationEngine()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            engine.validate,
            [
                _context(root_a, path_a, "exec-a", "A057349839"),
                _context(root_b, path_b, "exec-b", "B123456789"),
            ],
        ))

    assert results[0][0].context.execution_id == "exec-a"
    assert results[0][0].context.sob_id == "A057349839"
    assert results[1][0].context.execution_id == "exec-b"
    assert results[1][0].context.sob_id == "B123456789"
    assert results[0][0].status == ValidationStatus.OK
    assert results[1][0].status == ValidationStatus.ALERTA


def test_delayed_validation_result_remains_bound_to_captured_context(
    tmp_path: Path,
):
    root_a = tmp_path / "A"
    root_b = tmp_path / "B"
    root_a.mkdir()
    root_b.mkdir()
    path_a = _write_cqt(root_a / "A.xlsx", {"A": 4.0})
    path_b = _write_cqt(root_b / "B.xlsx", {"A": 5.0})
    captured_a = _context(root_a, path_a, "exec-a", "A057349839")
    context_b = _context(root_b, path_b, "exec-b", "B123456789")

    release_a = Event()
    started_a = Event()

    class DelayedRule(ValidationRule):
        rule_id = "TEST.DELAYED"
        description = "Delayed context binding"

        def validate(self, context):
            started_a.set()
            release_a.wait(timeout=3)
            return [self.result(
                context,
                self.rule_id,
                self.description,
                ValidationStatus.OK,
                context.sob_id,
                None,
                ValidationSource("test", None, None, "captured context"),
                "Captured result",
            )]

    engine_a = ValidationEngine(rules=[DelayedRule()])
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending_a = pool.submit(engine_a.validate, captured_a)
        assert started_a.wait(timeout=3)
        result_b = ValidationEngine().validate(context_b)
        release_a.set()
        delayed_a = pending_a.result(timeout=3)

    assert delayed_a[0].context.sob_id == "A057349839"
    assert delayed_a[0].context.execution_id == "exec-a"
    assert result_b[0].context.sob_id == "B123456789"
    assert result_b[0].context.execution_id == "exec-b"


def test_unknown_rule_never_returns_false_ok(tmp_path: Path):
    result = ValidationEngine().validate(
        _context(tmp_path, None),
        requested_rules=["REGRA.NAO.REGISTRADA"],
    )[0]

    assert result.status == ValidationStatus.NAO_DISPONIVEL


def test_cqt_validator_reads_cached_workbook_values_without_running_calculator(
    tmp_path: Path,
    monkeypatch,
):
    path = _write_cqt(tmp_path / "CQT_A057349839.xlsx", {"A": 4.2})

    def fail_if_recalculated(*args, **kwargs):
        raise AssertionError("O validador não deve recalcular o CQT.")

    import cqt.cqt_live_calc
    monkeypatch.setattr(
        cqt.cqt_live_calc,
        "calcular_cqt_topologia",
        fail_if_recalculated,
    )

    result = CqtMaximumVoltageDropRule().validate(_context(tmp_path, path))[0]

    assert result.status == ValidationStatus.OK
    assert result.value["percentual"] == 4.2


def test_validador_exception_fails_execution_not_rule_result(
    tmp_path: Path,
    monkeypatch,
    simulated_host_protocol,
):
    sob_id = "A057349839"
    root = tmp_path / f"SOB_{sob_id}"
    root.mkdir()
    dwg = root / f"PE_{sob_id}_DESENHO.dwg"
    dwg.write_bytes(b"DWG")
    (root / ".sob_state.json").write_text(
        json.dumps({
            "sob_id": sob_id,
            "status": "CONCLUÍDO",
            "base_dwg": str(dwg),
        }),
        encoding="utf-8",
    )

    def fail_validation(self, context):
        raise RuntimeError("falha de leitura CQT")

    monkeypatch.setattr(CqtMaximumVoltageDropRule, "validate", fail_validation)
    result = executar_acao_operacional(
        "validar",
        dwg_path=str(dwg),
        sob_id_esperada=sob_id,
        require_project_scope=True,
        execution_id="exec-validation-error",
        correlation_id="corr-validation-error",
        execution_managed_by_host=True,
        host_context=simulated_host_protocol(
            dwg, sob_id, "unit-only-fingerprint",
            "exec-validation-error", "corr-validation-error",
        ),
    )

    assert result["execution_state"] == "Falhou"
    assert result["exception_type"] == "RuntimeError"
    assert result.get("validation_results", []) == []


def test_validation_context_is_immutable_and_dwg_missing_is_not_ok(
    tmp_path: Path,
):
    context = _context(tmp_path, tmp_path / "missing.xlsx", "exec-missing")
    result = ValidationEngine().validate(context)[0]

    assert result.status == ValidationStatus.NAO_DISPONIVEL
    assert result.context.execution_id == "exec-missing"
    assert result.context.sob_id == "A057349839"


def test_validation_rule_events_jsonl_and_old_events_remain_compatible(
    tmp_path: Path, simulated_host_protocol
):
    configurar_logging(diretorio_logs=tmp_path)
    sob_id = "A057349839"
    root = tmp_path / f"SOB_{sob_id}"
    root.mkdir()
    dwg = root / f"PE_{sob_id}_DESENHO.dwg"
    dwg.write_bytes(b"DWG")
    (root / ".sob_state.json").write_text(
        json.dumps({
            "sob_id": sob_id,
            "status": "CONCLUÍDO",
            "base_dwg": str(dwg),
        }),
        encoding="utf-8",
    )
    _write_cqt(root / f"CQT_{sob_id}.xlsx", {"A": 4.0})
    executar_acao_operacional(
        "validar",
        dwg_path=str(dwg),
        sob_id_esperada=sob_id,
        require_project_scope=True,
        execution_id="exec-jsonl",
        correlation_id="corr-jsonl",
        host_context=simulated_host_protocol(
            dwg, sob_id, "unit-only-fingerprint", "exec-jsonl", "corr-jsonl"
        ),
    )

    event = next(
        json.loads(line)
        for line in (tmp_path / "logs" / "application.jsonl").read_text(encoding="utf-8").splitlines()
        if '"validation_rule_id"' in line
    )
    assert event["execution_id"] == "exec-jsonl"
    assert event["correlation_id"] == "corr-jsonl"
    assert event["validation_rule_id"] == "CQT.TENSAO_MAXIMA"
    assert event["validation_status"] == "OK"
    assert event["validation_source"]["localizacao"] == "CQT ATUAL!L11"
    assert event["origin"] == "oxcad.palette"

    legacy = '{"level":"INFO","message":"older event"}'
    parsed_legacy = json.loads(legacy)
    assert parsed_legacy["message"] == "older event"
    assert "execution_id" not in parsed_legacy