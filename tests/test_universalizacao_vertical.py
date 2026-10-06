from unittest.mock import Mock
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable
import pytest

from workspace.workspace_integrations import (
    IntegrationContext, IntegrationRegistry, IntegrationStatus, WorkOrderQuery,
)
from workspace.workspace_universalizacao_client import (
    HandshakeStep, UniversalizacaoDiagnostic,
)
from workspace.workspace_integration_executor import IntegrationExecutor
from workspace.workspace_universalizacao_provider import (
    UniversalizacaoProvider,
)


def _synthetic_transport_diagnostic() -> UniversalizacaoDiagnostic:
    return UniversalizacaoDiagnostic(
        stage="RESPONSE_CONSUMPTION",
        steps=(
            HandshakeStep("GET", 401, ("negotiate", "ntlm"), False),
            HandshakeStep("TYPE1", 401, ("ntlm",), True, 1, 4, 2, 8),
            HandshakeStep("TYPE3", 200, (), True, 3, 12),
        ),
        connection_reused=True,
        expected_target_seen=True,
    )


def test_transient_executor_preserves_compound_identity_and_result() -> None:
    context = IntegrationContext(
        sob_id="SYNTHETIC_001", project_root="C:/synthetic",
        dwg_path="C:/synthetic/project.dwg",
        database_fingerprint="synthetic-fp",
        correlation_id="synthetic-corr", execution_id="synthetic-exec",
    )
    client = Mock()
    provider = UniversalizacaoProvider(
        client,
        credential_supplier=lambda: ("synthetic-user", "synthetic-pass"),
    )
    html = (
        "<script>if(parent.mainFrame.document.frm1){"
        "parent.mainFrame.document.frm1.numero_ordem_projeto.value="
        "'SYNTHETIC_001';"
        "parent.mainFrame.document.frm1.grupo.value='B';"
        "parent.mainFrame.document.frm1.status_ordem.value='SYNTHETIC_STATUS';"
        "parent.mainFrame.document.frm1.nome.value='SYNTHETIC_NAME';"
        "}</script>"
    )
    from workspace.workspace_universalizacao_client import (
        UniversalizacaoCode, UniversalizacaoResult,
    )

    def read_order(
        sob: str, grupo: str, username: str | None, password: str | None,
        *, consume: Callable[[str], None],
    ) -> UniversalizacaoResult:
        assert (grupo, sob) == ("B", "SYNTHETIC_001")
        assert (username, password) == ("synthetic-user", "synthetic-pass")
        consume(html)
        return UniversalizacaoResult(
            True, UniversalizacaoCode.SUCCESS, 200, "synthetic-url",
            "QUERY_ORDER", 0.1, True, "Synthetic result",
            _synthetic_transport_diagnostic(),
        )

    client.read_order.side_effect = read_order
    registry = IntegrationRegistry()
    registry.register(provider)
    request = WorkOrderQuery("B", "SYNTHETIC_001")
    result = IntegrationExecutor(registry).execute_query(
        "universalizacao", request, context
    )
    assert result.status == IntegrationStatus.SUCCESS
    assert result.data is not None
    assert result.data["identity"] == request.to_dict()
    assert result.data["project_data"]["nome"] == "SYNTHETIC_NAME"
    assert result.data["correlation_id"] == context.correlation_id
    assert result.data["execution_id"] == context.execution_id
    client.read_order.assert_called_once()


def test_cli_context_executor_provider_result_preserves_query_and_ids(
    tmp_path: Path,
) -> None:
    from workspace.workspace_context import ProjectContext
    from workspace.workspace_integration_cli import handle_consultar
    from workspace.workspace_integrations import IntegrationResult

    context = ProjectContext(
        sob_id="SYNTHETIC_001", dwg_path="C:/synthetic/project.dwg",
        database_fingerprint="synthetic-fp", project_root=tmp_path,
        correlation_id="synthetic-corr", execution_id="synthetic-exec",
    )
    provider = UniversalizacaoProvider()
    provider.query_work_order = Mock(return_value=IntegrationResult.success({
        "identity": {"grupo": "B", "sob": "SYNTHETIC_001"},
        "returned_grupo": "B", "returned_sob": "SYNTHETIC_001",
        "project_data": {"referencia": None},
    }))
    registry = IntegrationRegistry()
    registry.register(provider)
    query = WorkOrderQuery("B", "SYNTHETIC_001")
    out = handle_consultar(context, query, IntegrationExecutor(registry))
    assert out["sucesso"]
    assert out["query_identity"] == out["resultado"]["data"]["identity"]
    projected, forwarded = provider.query_work_order.call_args.args
    assert forwarded is query
    assert projected.correlation_id == context.correlation_id
    assert projected.execution_id == context.execution_id
    assert out["resultado"]["data"]["project_data"]["referencia"] is None
    assert not hasattr(context, "grupo")
    assert list(tmp_path.iterdir()) == []


BUSINESS: dict[str, str] = {
    "nome": "SYNTHETIC_NAME", "logradouro": "SYNTHETIC_ADDRESS",
    "bairro": "SYNTHETIC_DISTRICT", "municipio": "SYNTHETIC_CITY",
    "area_tecnica": "SYNTHETIC_POLE", "tipo_servico": "SYNTHETIC_SERVICE",
    "notas_obs": "SYNTHETIC_NOTES", "notas_referencia": "SYNTHETIC_REFERENCE",
}
CANONICAL: dict[str, str] = {
    "nome": BUSINESS["nome"], "endereco": BUSINESS["logradouro"],
    "bairro": BUSINESS["bairro"], "municipio": BUSINESS["municipio"],
    "polo_tecnico": BUSINESS["area_tecnica"],
    "tipo_servico": BUSINESS["tipo_servico"],
    "notas_observacao": BUSINESS["notas_obs"],
    "referencia": BUSINESS["notas_referencia"],
}
STATES: dict[str, str] = {
    "etapa_ordem_proj": "SYNTHETIC_STAGE",
    "estado_ordem_proj": "SYNTHETIC_STATE",
    "status_ordem": "SYNTHETIC_STATUS",
}
CASES: list[tuple[str, str | None, str, str, int]] = [
    ("full", "B", "SYNTHETIC_001", "SUCCESS", 1),
    ("optional", "B", "SYNTHETIC_001", "SUCCESS", 1),
    ("unknown", "B", "SYNTHETIC_001", "SUCCESS", 1),
    ("truncated", "B", "SYNTHETIC_001", "REMOTE_ERROR", 1),
    ("wrong_group", "B", "SYNTHETIC_001", "IDENTITY_MISMATCH", 1),
    ("wrong_sob", "B", "SYNTHETIC_001", "IDENTITY_MISMATCH", 1),
    ("full", None, "SYNTHETIC_001", "INVALID_REQUEST", 0),
    ("full", "", "SYNTHETIC_001", "INVALID_REQUEST", 0),
    ("full", "C", "SYNTHETIC_001", "INVALID_REQUEST", 0),
    ("full", "b", "SYNTHETIC_001", "INVALID_REQUEST", 0),
    ("full", "B", "SYNTHETIC_002", "IDENTITY_MISMATCH", 0),
]


def _cli_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    variant: str,
    grupo: str | None,
    sob: str,
) -> tuple[dict[str, Any], Mock]:
    from workspace import workspace_integration_cli as cli
    from workspace.workspace_universalizacao_client import (
        UniversalizacaoCode, UniversalizacaoResult,
    )

    fields = {
        "numero_ordem_projeto": "SYNTHETIC_001",
        "grupo": "B", "select_grupo": "B",
        **STATES, **BUSINESS,
    }
    if variant == "optional":
        for optional in ("area_tecnica", "notas_referencia", "bairro"):
            del fields[optional]
    if variant == "unknown":
        fields["unknown_field"] = "SYNTHETIC_IGNORED"
    if variant == "wrong_group":
        fields["grupo"] = fields["select_grupo"] = "A"
    if variant == "wrong_sob":
        fields["numero_ordem_projeto"] = "SYNTHETIC_002"
    html = "<script>" + "".join(
        f"parent.mainFrame.document.frm1.{field}.value='{value}';"
        for field, value in fields.items()
    )
    if variant == "truncated":
        html += "parent.mainFrame.document.frm1.notas_referencia.value='"
    html += "</script>"
    client = Mock()

    def read_order(
        requested_sob: str, requested_grupo: str, username: str | None,
        password: str | None, *, consume: Callable[[str], None],
    ) -> UniversalizacaoResult:
        assert (requested_grupo, requested_sob) == (grupo, sob)
        assert (username, password) == ("synthetic-user", "synthetic-pass")
        consume(html)
        return UniversalizacaoResult(
            True, UniversalizacaoCode.SUCCESS, 200, "synthetic-url",
            "QUERY_ORDER", 0.1, True, "Synthetic result",
            _synthetic_transport_diagnostic(),
        )

    client.read_order.side_effect = read_order
    provider = UniversalizacaoProvider(
        client,
        credential_supplier=lambda: ("synthetic-user", "synthetic-pass"),
    )
    registry = IntegrationRegistry()
    registry.register(provider)
    monkeypatch.setattr(
        cli, "_query_executor", lambda: IntegrationExecutor(registry)
    )
    queue_constructor = Mock(side_effect=AssertionError("No query queue"))
    monkeypatch.setattr(cli, "SyncQueue", queue_constructor)
    argv = [
        "--action", "consultar", "--project-root", str(tmp_path),
        "--sob", "SYNTHETIC_001", "--dwg", "C:/synthetic/project.dwg",
        "--fingerprint", "synthetic-fp", "--correlation-id", "synthetic-corr",
        "--execution-id", "synthetic-exec", "--query-sob", sob,
    ]
    if grupo is not None:
        argv.extend(["--grupo", grupo])
    monkeypatch.setattr(sys, "argv", ["workspace_integration_cli.py", *argv])
    exit_code = cli.main()
    envelope = json.loads(capsys.readouterr().out)
    assert exit_code == (0 if envelope["sucesso"] else 1)
    assert list(tmp_path.iterdir()) == []
    queue_constructor.assert_not_called()
    return envelope, client


@pytest.mark.parametrize("variant,grupo,sob,status,calls", CASES)
def test_cli_executor_provider_vertical_contract(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    variant: str,
    grupo: str | None,
    sob: str,
    status: str,
    calls: int,
) -> None:
    out, client = _cli_result(
        monkeypatch, capsys, tmp_path, variant, grupo, sob
    )
    assert out["resultado"]["status"] == status
    assert out["query_identity"] == {"grupo": grupo, "sob": sob}
    assert client.read_order.call_count == calls
    if status == "SUCCESS":
        data = out["resultado"]["data"]
        assert data["identity"] == out["query_identity"]
        expected: dict[str, str | None] = dict(CANONICAL)
        if variant == "optional":
            expected.update(polo_tecnico=None, referencia=None, bairro=None)
        assert data["project_data"] == expected
        assert data["order_status"] == STATES
        assert data["correlation_id"] == "synthetic-corr"
        assert data["execution_id"] == "synthetic-exec"
    elif calls:
        assert all(
            value is None
            for value in out["resultado"]["data"]["project_data"].values()
        )


@pytest.fixture(scope="module", name="csharp_harness")
def _build_csharp_harness() -> tuple[str, Path]:
    dotnet = shutil.which("dotnet")
    if not dotnet:
        pytest.skip(
            ".NET SDK required for compiled WorkspaceService consumer proof"
        )
    project = (
        Path(__file__).parent / "oxcad_context_gate"
        / "OxCadContextGateHarness.csproj"
    )
    built = subprocess.run(
        [dotnet, "build", str(project), "--no-restore", "-v", "quiet"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    assembly = (
        project.parent / "bin" / "Debug" / "net8.0"
        / "OxCadContextGateHarness.dll"
    )
    return dotnet, assembly


@pytest.mark.parametrize("variant,grupo,sob,status,calls", CASES)
def test_python_cli_result_reaches_actual_csharp_workspace_service(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    csharp_harness: tuple[str, Path],
    variant: str,
    grupo: str | None,
    sob: str,
    status: str,
    calls: int,
) -> None:
    out, client = _cli_result(
        monkeypatch, capsys, tmp_path, variant, grupo, sob
    )
    wire = tmp_path / "synthetic-result.json"
    wire.write_text(json.dumps(out), encoding="utf-8")
    dotnet, assembly = csharp_harness
    consumed = subprocess.run(
        [
            dotnet, str(assembly), "--universalizacao", str(wire),
            grupo or "", sob,
        ],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert consumed.returncode == 0, consumed.stderr
    delivered = json.loads(consumed.stdout)
    expected_status = {
        "SUCCESS": "Success", "REMOTE_ERROR": "RemoteError",
        "INVALID_REQUEST": "InvalidRequest",
        "IDENTITY_MISMATCH": "IdentityMismatch",
    }[status]
    assert delivered["status"] == expected_status
    assert delivered["active_sob"] == "SYNTHETIC_001"
    assert client.read_order.call_count == calls
    if status == "SUCCESS":
        assert delivered["data"] == out["resultado"]["data"]
    else:
        assert delivered["error_code"] == out["resultado"]["error_code"]


@pytest.mark.parametrize("field,value", [
    ("returned_grupo", "A"), ("returned_sob", "SYNTHETIC_002"),
    ("correlation_id", "another-correlation"),
    ("execution_id", "another-execution"),
])
def test_csharp_rechecks_wire_identity_and_ids(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    csharp_harness: tuple[str, Path],
    field: str,
    value: str,
) -> None:
    out, _ = _cli_result(
        monkeypatch, capsys, tmp_path, "full", "B", "SYNTHETIC_001"
    )
    out["resultado"]["data"][field] = value
    wire = tmp_path / "synthetic-result.json"
    wire.write_text(json.dumps(out), encoding="utf-8")
    dotnet, assembly = csharp_harness
    consumed = subprocess.run(
        [
            dotnet, str(assembly), "--universalizacao", str(wire), "B",
            "SYNTHETIC_001",
        ],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert consumed.returncode == 0, consumed.stderr
    delivered = json.loads(consumed.stdout)
    assert delivered["status"] == "IdentityMismatch"
    assert delivered["data"] is None


@pytest.mark.parametrize("field,value", [
    ("method", "POST"), ("route", "/synthetic/other"),
    ("ntlm_version", "NTLMv1"), ("sspi", True),
    ("cookies_sent", True), ("cookies_persisted", True),
    ("redirects_followed", True), ("connection_reused", False),
])
def test_csharp_rejects_unverified_transport_evidence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    csharp_harness: tuple[str, Path],
    field: str,
    value: Any,
) -> None:
    out, _ = _cli_result(
        monkeypatch, capsys, tmp_path, "full", "B", "SYNTHETIC_001"
    )
    out["resultado"]["data"]["transport"][field] = value
    wire = tmp_path / "synthetic-result.json"
    wire.write_text(json.dumps(out), encoding="utf-8")
    dotnet, assembly = csharp_harness
    consumed = subprocess.run(
        [
            dotnet, str(assembly), "--universalizacao", str(wire), "B",
            "SYNTHETIC_001",
        ],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert consumed.returncode == 0, consumed.stderr
    delivered = json.loads(consumed.stdout)
    assert delivered["status"] == "RemoteError"
    assert delivered["data"] is None


@pytest.mark.parametrize(
    "grupo,sob", [("A", "SYNTHETIC_001"), ("B", "SYNTHETIC_002")]
)
def test_executor_rechecks_successful_provider_identity(
    grupo: str, sob: str,
) -> None:
    from workspace.workspace_integrations import IntegrationResult

    context = IntegrationContext(
        "SYNTHETIC_001", "C:/synthetic", "project.dwg", "fp"
    )
    provider = UniversalizacaoProvider()
    provider.query_work_order = Mock(return_value=IntegrationResult.success({
        "identity": {"grupo": grupo, "sob": sob},
        "returned_grupo": grupo, "returned_sob": sob,
    }))
    registry = IntegrationRegistry()
    registry.register(provider)
    result = IntegrationExecutor(registry).execute_query(
        "universalizacao", WorkOrderQuery("B", "SYNTHETIC_001"), context
    )
    assert result.status == IntegrationStatus.IDENTITY_MISMATCH
    assert result.data is None


@pytest.mark.parametrize("variant,grupo,sob,status,calls", CASES)
def test_real_workspace_service_subprocess_cli_provider_round_trip(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    csharp_harness: tuple[str, Path],
    variant: str,
    grupo: str | None,
    sob: str,
    status: str,
    calls: int,
) -> None:
    out, _ = _cli_result(monkeypatch, capsys, tmp_path, variant, grupo, sob)
    source_root = Path(__file__).resolve().parents[1]
    fields = {
        "numero_ordem_projeto": "SYNTHETIC_001", "grupo": "B",
        **STATES, **BUSINESS,
    }
    if variant == "optional":
        for optional in ("area_tecnica", "notas_referencia", "bairro"):
            del fields[optional]
    if variant == "unknown":
        fields["unknown_field"] = "SYNTHETIC_IGNORED"
    if variant == "wrong_group":
        fields["grupo"] = "A"
    if variant == "wrong_sob":
        fields["numero_ordem_projeto"] = "SYNTHETIC_002"
    html = "<script>" + "".join(
        f"parent.mainFrame.document.frm1.{field}.value='{value}';"
        for field, value in fields.items()
    )
    if variant == "truncated":
        html += "parent.mainFrame.document.frm1.notas_referencia.value='"
    html += "</script>"
    script = tmp_path / "workspace" / "workspace_integration_cli.py"
    script.parent.mkdir()
    script.write_text(
        f"import sys\nsys.path.insert(0, {str(source_root)!r})\n"
        "import socket\n"
        "from typing import Callable\n"
        "call_count = 0\n"
        "def no_network(*args, **kwargs):\n"
        "    raise AssertionError('External network forbidden')\n"
        "socket.socket.connect = no_network\n"
        "socket.socket.connect_ex = no_network\n"
        "socket.getaddrinfo = no_network\n"
        "from workspace import workspace_integration_cli as cli\n"
        "from workspace.workspace_universalizacao_client import (\n"
        "    UniversalizacaoClient, UniversalizacaoResult,\n"
        "    UniversalizacaoCode, UniversalizacaoDiagnostic, HandshakeStep)\n"
        "cli._query_credentials = lambda: (\n"
        "    'synthetic-user', 'synthetic-pass')\n"
        "synthetic_diagnostic = UniversalizacaoDiagnostic(\n"
        "    stage='RESPONSE_CONSUMPTION',\n"
        "    steps=(\n"
        "        HandshakeStep('GET', 401, ('negotiate', 'ntlm'), False),\n"
        "        HandshakeStep('TYPE1', 401, ('ntlm',), True, 1, 4, 2, 8),\n"
        "        HandshakeStep('TYPE3', 200, (), True, 3, 12),\n"
        "    ), connection_reused=True, expected_target_seen=True)\n"
        "def read_order(\n"
        "    self, sob: str, grupo: str, username: str | None,\n"
        "    password: str | None, *, consume: Callable[[str], None]\n"
        ") -> UniversalizacaoResult:\n"
        "    global call_count\n"
        "    call_count += 1\n"
        "    assert (grupo, sob) == ('B', 'SYNTHETIC_001')\n"
        "    assert (username, password) == (\n"
        "        'synthetic-user', 'synthetic-pass')\n"
        f"    consume({html!r})\n"
        "    return UniversalizacaoResult(\n"
        "        True, UniversalizacaoCode.SUCCESS, 200, 'synthetic-url',\n"
        "        'QUERY_ORDER', 0.1, True, 'Synthetic result',\n"
        "        synthetic_diagnostic)\n"
        "UniversalizacaoClient.read_order = read_order\n"
        "exit_code = cli.main()\n"
        f"assert call_count == {calls}\n"
        "raise SystemExit(exit_code)\n",
        encoding="utf-8",
    )
    dotnet, assembly = csharp_harness
    env = dict(
        os.environ, AUXCAD_ROOT=str(tmp_path),
        PYTHON_EXECUTABLE=sys.executable, PYTHONDONTWRITEBYTECODE="1",
    )
    consumed = subprocess.run(
        [
            dotnet, str(assembly), "--universalizacao-process", str(tmp_path),
            grupo or "", sob,
        ],
        capture_output=True, text=True, timeout=30, env=env, check=False,
    )
    assert consumed.returncode == 0, consumed.stderr
    delivered = json.loads(consumed.stdout)
    expected_status = {
        "SUCCESS": "Success", "REMOTE_ERROR": "RemoteError",
        "INVALID_REQUEST": "InvalidRequest",
        "IDENTITY_MISMATCH": "IdentityMismatch",
    }[status]
    assert delivered["status"] == expected_status
    assert delivered["active_sob"] == "SYNTHETIC_001"
    if status == "SUCCESS":
        assert delivered["data"] == out["resultado"]["data"]
    created_files = sorted(
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*") if path.is_file()
    )
    assert created_files == ["workspace/workspace_integration_cli.py"]


def test_actual_cli_file_entry_rejects_invalid_group_without_queue(
    tmp_path: Path,
) -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "workspace" / "workspace_integration_cli.py"
    )
    consumed = subprocess.run(
        [
            sys.executable, "-B", str(script), "--action", "consultar",
            "--grupo", "C", "--query-sob", "SYNTHETIC_001",
            "--sob", "SYNTHETIC_001", "--project-root", str(tmp_path),
        ],
        capture_output=True, text=True, timeout=30, cwd=tmp_path,
        check=False,
    )
    assert consumed.returncode == 1
    out = json.loads(consumed.stdout)
    assert out["resultado"]["status"] == "INVALID_REQUEST"
    assert list(tmp_path.iterdir()) == []


def test_csharp_rejects_argument_injection_in_context_id(
    csharp_harness: tuple[str, Path],
) -> None:
    dotnet, assembly = csharp_harness
    result = subprocess.run(
        [
            dotnet, str(assembly), "--invalid-context-id",
            'synthetic" --action executar',
        ],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "status": "InvalidRequest", "calls": 0,
    }
