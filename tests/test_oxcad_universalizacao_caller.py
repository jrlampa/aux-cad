import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "active_group,query_group,active_sob,query_sob,independent,"
    "returned_group,status,calls",
    [
        ("B", "B", "SOB_001", "SOB_001", False, "B", "Success", 1),
        ("B", "A", "SOB_001", "SOB_001", False, "A", "IdentityMismatch", 0),
        ("B", "A", "SOB_001", "SOB_001", True, "A", "Success", 1),
        ("B", "B", "SOB_001", "SOB_002", False, "B", "IdentityMismatch", 0),
        ("B", "B", "SOB_001", "SOB_002", True, "B", "Success", 1),
        ("", "B", "SOB_001", "SOB_001", False, "B", "InvalidRequest", 0),
        ("B", "C", "SOB_001", "SOB_001", False, "C", "InvalidRequest", 0),
        ("B", "B", "SOB_001", "SOB_001", False, "A", "IdentityMismatch", 1),
    ],
)
def test_public_caller_to_service_cli_executor_provider_round_trip(
    caller_harness: tuple[str, Path],
    tmp_path: Path,
    active_group: str,
    query_group: str,
    active_sob: str,
    query_sob: str,
    independent: bool,
    returned_group: str,
    status: str,
    calls: int,
) -> None:
    source_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    html = "<script>" + "".join(
        f"parent.mainFrame.document.frm1.{field}.value="
        f"{json.dumps(value)};"
        for field, value in {
            "numero_ordem_projeto": query_sob,
            "grupo": returned_group,
            "select_grupo": returned_group,
            "etapa_ordem_proj": "SYNTHETIC_STAGE",
            "estado_ordem_proj": "SYNTHETIC_STATE",
            "status_ordem": "SYNTHETIC_STATUS",
            "nome": "SYNTHETIC_NAME",
            "logradouro": "SYNTHETIC_ADDRESS",
            "bairro": "SYNTHETIC_DISTRICT",
            "municipio": "SYNTHETIC_CITY",
            "area_tecnica": "SYNTHETIC_POLE",
            "tipo_servico": "SYNTHETIC_SERVICE",
            "notas_obs": "SYNTHETIC_NOTES",
            "notas_referencia": "SYNTHETIC_REFERENCE",
        }.items()
    ) + "</script>"
    cli_script = workspace / "workspace_integration_cli.py"
    cli_script.write_text(
        f"import sys\nsys.path.insert(0, {str(source_root)!r})\n"
        "import socket\n"
        "from typing import Callable\n"
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
        "call_count = 0\n"
        "def read_order(\n"
        "    self, sob: str, grupo: str, username: str | None,\n"
        "    password: str | None, *, consume: Callable[[str], None]\n"
        ") -> UniversalizacaoResult:\n"
        "    global call_count\n"
        "    call_count += 1\n"
        f"    assert (grupo, sob) == ({query_group!r}, {query_sob!r})\n"
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
    dotnet, assembly = caller_harness
    env = dict(
        os.environ,
        AUXCAD_ROOT=str(tmp_path),
        PYTHON_EXECUTABLE=sys.executable,
        PYTHONDONTWRITEBYTECODE="1",
    )
    consumed = subprocess.run(
        [
            dotnet, str(assembly), "--oxcad-universalizacao-process",
            str(tmp_path), active_group, query_group, active_sob, query_sob,
            str(independent).lower(),
        ],
        capture_output=True, text=True, timeout=30, env=env, check=False,
    )
    assert consumed.returncode == 0, consumed.stderr
    delivered = json.loads(consumed.stdout)
    assert delivered["status"] == status
    assert delivered["active_sob"] == active_sob
    assert delivered["scope_unchanged"] is True
    if status == "Success":
        assert delivered["data"]["identity"] == {
            "grupo": query_group, "sob": query_sob,
        }
        assert delivered["data"]["project_data"]["nome"] == "SYNTHETIC_NAME"
        assert (
            delivered["data"]["order_status"]["status_ordem"]
            == "SYNTHETIC_STATUS"
        )
        assert delivered["data"]["correlation_id"] == "synthetic-correlation"
        assert delivered["data"]["execution_id"] == "synthetic-execution"
    elif calls:
        assert delivered["data"]["project_data"] == {
            "nome": None, "endereco": None, "bairro": None,
            "municipio": None, "polo_tecnico": None,
            "tipo_servico": None, "notas_observacao": None,
            "referencia": None,
        }
    else:
        assert delivered["data"] is None
    assert sorted(
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*") if path.is_file()
    ) == ["workspace/workspace_integration_cli.py"]


CASES = [
    ("B", "B", "SOB_001", "SOB_001", False, "success", "Success", 1),
    ("B", "A", "SOB_001", "SOB_001", False, "success", "IdentityMismatch", 0),
    ("B", "A", "SOB_001", "SOB_001", True, "success", "Success", 1),
    ("B", "B", "SOB_001", "SOB_002", False, "success", "IdentityMismatch", 0),
    ("B", "B", "SOB_001", "SOB_002", True, "success", "Success", 1),
    ("", "B", "SOB_001", "SOB_001", False, "success", "InvalidRequest", 0),
    ("B", "C", "SOB_001", "SOB_001", False, "success", "InvalidRequest", 0),
    ("B", "B", "SOB_001", "SOB_001", False, "mismatch", "IdentityMismatch", 1),
]


@pytest.fixture(scope="module", name="caller_harness")
def build_caller_harness() -> tuple[str, Path]:
    dotnet = shutil.which("dotnet")
    if not dotnet:
        pytest.skip(".NET SDK required for OXCAD caller harness")
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


@pytest.mark.parametrize(
    "active_group,query_group,active_sob,query_sob,independent,"
    "returned,status,calls",
    CASES,
)
def test_oxcad_caller_preserves_authority_query_result_and_scope(
    caller_harness: tuple[str, Path],
    tmp_path: Path,
    active_group: str,
    query_group: str,
    active_sob: str,
    query_sob: str,
    independent: bool,
    returned: str,
    status: str,
    calls: int,
) -> None:
    dotnet, assembly = caller_harness
    result = subprocess.run(
        [
            dotnet, str(assembly), "--oxcad-universalizacao-caller",
            active_group, query_group, active_sob, query_sob,
            str(independent).lower(), returned,
        ],
        capture_output=True, text=True, timeout=30, check=False,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    delivered = json.loads(result.stdout)
    assert delivered["status"] == status
    assert delivered["calls"] == calls
    assert delivered["active_sob"] == active_sob
    assert delivered["project_scope_unchanged"] is True
    if calls:
        assert delivered["requested"] == {
            "grupo": query_group, "sob": query_sob,
        }
        assert delivered["context_sob"] == active_sob
        assert delivered["independent"] is independent
        if status == "Success":
            assert delivered["correlation_id"] == "synthetic-correlation"
            assert delivered["execution_id"] == "synthetic-execution"
        else:
            assert delivered["correlation_id"] is None
            assert delivered["execution_id"] is None
    else:
        assert delivered["requested"] == {"grupo": None, "sob": None}
        assert delivered["correlation_id"] is None
        assert delivered["execution_id"] is None
    assert list(tmp_path.iterdir()) == []
