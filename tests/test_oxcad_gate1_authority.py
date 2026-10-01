"""Gate 1: o envelope sintético testa só o protocolo, não o DWG real."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from workspace.workspace_context_cli import (
    _verificar_envelope_host,
    executar_acao_operacional,
)


SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "workspace" / "workspace_context_cli.py"
)


def _declared_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "SOB_A057349839"
    root.mkdir()
    dwg = root / "PE_A057349839_DESENHO.dwg"
    dwg.write_bytes(b"synthetic drawing, not an AutoCAD Xrecord")
    (root / ".sob_state.json").write_text(
        json.dumps({
            "sob_id": "A057349839", "status": "CONCLUÍDO",
            "base_dwg": str(dwg),
        }), encoding="utf-8",
    )
    return root, dwg


@pytest.mark.parametrize(
    "sob_id,fingerprint",
    [
        ("B123456789", "false-fingerprint"),
        ("A057349839", "false-fingerprint"),
        ("A057349839", "declared-fingerprint"),
    ],
)
def test_manual_identity_flags_are_not_proof(
    tmp_path: Path, sob_id: str, fingerprint: str
):
    root, dwg = _declared_project(tmp_path)
    proc = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--acao", "versao_capturar",
            "--dwg", str(dwg), "--sob", sob_id,
            "--dwg-identity", fingerprint, "--alvo", "CQT.xlsx",
        ],
        cwd=root, capture_output=True, text=True, encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 1
    result = json.loads(proc.stdout)
    assert result["erro"] == "DWG_CONTEXT_NOT_VERIFIED"
    assert result["project_scope_status"] == "Unverified"
    assert not (root / ".auxcad_versions").exists()


def test_protocol_rejects_stale_or_conflicting_host_fields(
    tmp_path: Path, simulated_host_protocol
):
    _, dwg = _declared_project(tmp_path)
    synthetic_envelope = {
        "contract_version": 1, "project_scope_status": "Bound",
        "sob_id": "A057349839", "dwg_path": str(dwg),
        "dwg_identity": "simulated-host-fingerprint",
        "context_generation": 4, "execution_id": "exec-a",
        "correlation_id": "corr-a",
    }
    verified, status = _verificar_envelope_host(
        synthetic_envelope, str(dwg), "A057349839",
        "simulated-host-fingerprint", "exec-a", "corr-a",
    )
    assert status == "CONTEXTO_VERIFICADO"
    assert verified["sob_id"] == "A057349839"
    for sob_id, fingerprint in (
        ("B123456789", "simulated-host-fingerprint"),
        ("A057349839", "different-fingerprint"),
    ):
        _, status = _verificar_envelope_host(
            synthetic_envelope, str(dwg), sob_id, fingerprint,
            "exec-a", "corr-a",
        )
        assert status == "DWG_CONTEXT_INCOMPATIBLE"
    other = dwg.with_name("another.dwg")
    other.write_bytes(b"different synthetic drawing")
    _, status = _verificar_envelope_host(
        synthetic_envelope, str(other), "A057349839",
        "simulated-host-fingerprint", "exec-a", "corr-a",
    )
    assert status == "DWG_CONTEXT_INCOMPATIBLE"
    _, status = _verificar_envelope_host(
        {**synthetic_envelope, "context_generation": 0},
        str(dwg), "A057349839", None, "exec-a", "corr-a",
    )
    assert status == "DWG_CONTEXT_NOT_VERIFIED"


def test_no_host_context_never_becomes_verified_from_manifest(tmp_path: Path):
    _, dwg = _declared_project(tmp_path)
    result = executar_acao_operacional(
        "validar", dwg_path=str(dwg), sob_id_esperada="A057349839",
        dwg_identity="simulated-host-fingerprint",
    )
    assert result["sucesso"] is False
    assert result["erro"] == "DWG_CONTEXT_NOT_VERIFIED"
    assert "validation_results" not in result


def test_forged_stdin_from_non_autocad_parent_is_rejected(tmp_path: Path):
    root, dwg = _declared_project(tmp_path)
    payload = {
        "contract_version": 1, "project_scope_status": "Bound",
        "sob_id": "A057349839", "dwg_path": str(dwg),
        "dwg_identity": "declared-fingerprint", "context_generation": 1,
        "execution_id": "exec-a", "correlation_id": "corr-a",
    }
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--acao", "versao_capturar",
         "--host-context-stdin", "--acad-pid", str(os.getpid()),
         "--alvo", "output.txt"],
        input=json.dumps(payload) + "\n", cwd=root,
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["erro"] == "DWG_CONTEXT_NOT_VERIFIED"
    assert not (root / ".auxcad_versions").exists()


def test_unit_host_scope_uses_xrecord_contract_not_local_manifest(
    tmp_path: Path, simulated_host_protocol
):
    root, dwg = _declared_project(tmp_path)
    (root / ".sob_state.json").unlink()
    (root / "output.txt").write_bytes(b"synthetic test output")
    envelope = simulated_host_protocol(
        dwg, "A057349839", "unit-fingerprint", "exec-a", "corr-a"
    )
    captured = executar_acao_operacional(
        "versao_capturar", dwg_path=str(dwg),
        sob_id_esperada="A057349839", dwg_identity="unit-fingerprint",
        execution_id="exec-a", correlation_id="corr-a", alvo="output.txt",
        host_context=envelope,
    )
    assert captured["sucesso"] is True
    assert captured["version_result"]["manifest"]["sob_id"] == "A057349839"
    incompatible = executar_acao_operacional(
        "versao_capturar", dwg_path=str(dwg),
        sob_id_esperada="B123456789", alvo="output.txt",
        host_context=envelope,
    )
    assert incompatible["erro"] == "DWG_CONTEXT_INCOMPATIBLE"
    wrong_fingerprint = executar_acao_operacional(
        "versao_capturar", dwg_path=str(dwg),
        dwg_identity="forged-fingerprint", alvo="output.txt",
        host_context=envelope,
    )
    assert wrong_fingerprint["erro"] == "DWG_CONTEXT_INCOMPATIBLE"


def test_host_code_routes_active_xrecord_fingerprint_by_stdin():
    root = Path(__file__).resolve().parent.parent
    control = (root / "oxcad" / "OxCadControl.xaml.cs").read_text(
        encoding="utf-8"
    )
    service = (root / "oxcad" / "WorkspaceService.cs").read_text(
        encoding="utf-8"
    )
    assert "acApp.DocumentManager.MdiActiveDocument" in control
    assert "DwgProjectScopeStore.Read(database)" in control
    assert "database.FingerprintGuid" in control
    assert "_contextRefreshGate.IsCurrentGeneration(generation)" in control
    assert "CapturarContextoVerificado()" in control
    assert "RedirectStandardInput = verifiedContext != null" in service
    assert (
        "proc.StandardInput.WriteLine(JsonSerializer.Serialize(verifiedContext))"
        in service
    )
    assert 'argsBuilder.Append(" --host-context-stdin")' in service
