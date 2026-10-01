from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from common.logging_config import configurar_logging
from workspace.workspace_context_cli import executar_acao_operacional
from workspace.workspace_time import carregar_tempo_projeto
from workspace.workspace_actions import WorkspaceActionDispatcher


def _criar_projeto(root: Path, sob_id: str) -> Path:
    root.mkdir(parents=True)
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
    return dwg


def _eventos(log_dir: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (log_dir / "application.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


def _executar_tempo(
    dwg: Path,
    sob_id: str,
    execution_id: str,
    correlation_id: str,
    host_protocol,
):
    # Simula somente o contrato de transporte, não a leitura real do AutoCAD.
    return executar_acao_operacional(
        "tempo_iniciar",
        dwg_path=str(dwg),
        sob_id_esperada=sob_id,
        require_project_scope=True,
        execution_id=execution_id,
        correlation_id=correlation_id,
        dwg_identity=f"database-{sob_id}",
        execution_origin="test.execution",
        host_context=host_protocol(
            dwg, sob_id, f"database-{sob_id}", execution_id, correlation_id
        ),
    )


def test_execucao_normal_registra_transicoes_e_contexto_congelado(
    tmp_path: Path,
    simulated_host_protocol,
):
    configurar_logging(diretorio_logs=tmp_path)
    sob_id = "A057349839"
    dwg = _criar_projeto(tmp_path / f"SOB_{sob_id}", sob_id)

    result = _executar_tempo(
        dwg, sob_id, "exec-normal", "corr-normal", simulated_host_protocol
    )

    transitions = [
        event for event in _eventos(tmp_path / "logs")
        if event.get("execution_id") == "exec-normal"
        and event.get("operation") == "action_execution.transition"
    ]
    assert [event["execution_state"] for event in transitions] == [
        "Iniciado", "Executando", "Concluído"
    ]
    assert all(
        event["correlation_id"] == "corr-normal" for event in transitions
    )
    assert result["execution_id"] == "exec-normal"
    assert result["execution_id"] != result["correlation_id"]
    assert result["sob_id"] == sob_id
    assert result["dwg_path"] == str(dwg.resolve())
    assert result["dwg_identity"] == f"database-{sob_id}"
    assert result["started_at"] and result["finished_at"]
    assert result["duration_ms"] >= 0


def test_excecao_falha_preserva_diagnostico(
    tmp_path: Path, monkeypatch, simulated_host_protocol
):
    configurar_logging(diretorio_logs=tmp_path)
    sob_id = "A057349839"
    dwg = _criar_projeto(tmp_path / f"SOB_{sob_id}", sob_id)

    def falhar_no_start(*args, **kwargs):
        raise RuntimeError("falha real ao inicializar processo")

    monkeypatch.setattr(
        WorkspaceActionDispatcher,
        "executar_cqt",
        falhar_no_start,
    )
    result = executar_acao_operacional(
        "cqt",
        dwg_path=str(dwg),
        sob_id_esperada=sob_id,
        require_project_scope=True,
        execution_id="exec-exception",
        correlation_id="corr-exception",
        host_context=simulated_host_protocol(
            dwg, sob_id, "test-only-fingerprint",
            "exec-exception", "corr-exception",
        ),
    )

    transitions = [
        event for event in _eventos(tmp_path / "logs")
        if event.get("execution_id") == "exec-exception"
        and event.get("operation") == "action_execution.transition"
    ]
    error_events = [
        event for event in _eventos(tmp_path / "logs")
        if event.get("execution_id") == "exec-exception"
        and event.get("exception_type") == "RuntimeError"
    ]
    assert [event["execution_state"] for event in transitions] == [
        "Iniciado", "Executando", "Falhou"
    ]
    assert result["exception_type"] == "RuntimeError"
    assert "falha real" in result["erro"]
    assert error_events and "stack_trace" in error_events[0]


def test_falha_durante_inicializacao_vai_direto_a_falhou(
    tmp_path: Path,
    monkeypatch,
):
    configurar_logging(diretorio_logs=tmp_path)

    def falhar_ao_criar_process(*args, **kwargs):
        raise OSError("launcher indisponível")

    monkeypatch.setattr(
        WorkspaceActionDispatcher,
        "executar_sob",
        falhar_ao_criar_process,
    )
    result = executar_acao_operacional(
        "sob",
        root_dir=str(tmp_path),
        execution_id="exec-init-failed",
        correlation_id="corr-init-failed",
    )

    states = [
        event["execution_state"]
        for event in _eventos(tmp_path / "logs")
        if event.get("execution_id") == "exec-init-failed"
        and event.get("operation") == "action_execution.transition"
    ]
    assert states == ["Iniciado", "Executando", "Falhou"]
    assert result["execution_state"] == "Falhou"


def test_subprocesso_real_so_conclui_execucao_apos_terminar(
    tmp_path: Path,
    monkeypatch,
    simulated_host_protocol,
):
    configurar_logging(diretorio_logs=tmp_path)
    sob_id = "A057349839"
    dwg = _criar_projeto(tmp_path / f"SOB_{sob_id}", sob_id)

    def iniciar_processo_real(workspace, **kwargs):
        return subprocess.Popen([sys.executable, "-c", "pass"])

    monkeypatch.setattr(
        WorkspaceActionDispatcher,
        "executar_cqt",
        iniciar_processo_real,
    )
    result = executar_acao_operacional(
        "cqt",
        dwg_path=str(dwg),
        sob_id_esperada=sob_id,
        require_project_scope=True,
        execution_id="exec-child",
        correlation_id="corr-child",
        wait_for_completion=True,
        execution_managed_by_host=True,
        host_context=simulated_host_protocol(
            dwg, sob_id, "test-only-fingerprint",
            "exec-child", "corr-child",
        ),
    )

    assert result["sucesso"] is False
    assert result["execution_state"] == "Falhou"
    assert result["erro"] == "ARTIFACT_NOT_VERIFIED"
    assert result["finished_at"] is not None
    assert result["pid"] is not None


def test_execucoes_simultaneas_tem_ids_e_contextos_independentes(
    tmp_path: Path,
    simulated_host_protocol,
):
    configurar_logging(diretorio_logs=tmp_path)
    dwg_a = _criar_projeto(tmp_path / "SOB_A", "A057349839")
    dwg_b = _criar_projeto(tmp_path / "SOB_B", "B123456789")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda values: _executar_tempo(*values, simulated_host_protocol),
            [
                (dwg_a, "A057349839", "exec-a", "corr-a"),
                (dwg_b, "B123456789", "exec-b", "corr-b"),
            ],
        ))

    assert {item["execution_id"] for item in results} == {"exec-a", "exec-b"}
    assert {item["sob_id"] for item in results} == {"A057349839", "B123456789"}
    entry_a = carregar_tempo_projeto(dwg_a.parent)
    entry_b = carregar_tempo_projeto(dwg_b.parent)
    assert entry_a.sob_id == "A057349839"
    assert entry_b.sob_id == "B123456789"


def test_jobtime_reutiliza_um_registro_sem_duplicar_sessoes(
    tmp_path: Path, simulated_host_protocol
):
    configurar_logging(diretorio_logs=tmp_path)
    sob_id = "A057349839"
    dwg = _criar_projeto(tmp_path / f"SOB_{sob_id}", sob_id)

    first = _executar_tempo(
        dwg, sob_id, "exec-time-1", "corr-time-1", simulated_host_protocol
    )
    first_entry = carregar_tempo_projeto(dwg.parent)
    second = _executar_tempo(
        dwg, sob_id, "exec-time-2", "corr-time-2", simulated_host_protocol
    )
    second_entry = carregar_tempo_projeto(dwg.parent)

    assert first["execution_state"] == second["execution_state"] == "Concluído"
    assert first_entry.data_hora_inicio == second_entry.data_hora_inicio
    assert len(second_entry.sessoes) == len(first_entry.sessoes) == 0
    assert (dwg.parent / ".oxcad" / "time.json").is_file()


def test_contexto_invalido_nao_cria_execucao_concluida(tmp_path: Path):
    configurar_logging(diretorio_logs=tmp_path)
    dwg = tmp_path / "sem_vinculo" / "PE_A057349839_DESENHO.dwg"
    dwg.parent.mkdir()
    dwg.write_bytes(b"DWG")

    result = executar_acao_operacional(
        "cqt",
        dwg_path=str(dwg),
        require_project_scope=True,
        execution_id="exec-blocked",
        correlation_id="corr-blocked",
    )

    transitions = [
        event for event in _eventos(tmp_path / "logs")
        if event.get("execution_id") == "exec-blocked"
        and event.get("operation") == "action_execution.transition"
    ]
    assert result["sucesso"] is False
    assert result["project_scope_status"] == "Unverified"
    assert transitions == []


def test_evento_jsonl_legado_sem_campos_de_execucao_continua_legivel():
    legacy_event = (
        '{"timestamp":"2026-09-30T00:00:00Z","level":"INFO",'
        '"message":"evento legado"}'
    )
    parsed = json.loads(legacy_event)

    assert parsed["message"] == "evento legado"
    assert "execution_id" not in parsed


def test_ui_e_servico_correlacionam_executionid_e_contexto():
    root = Path(__file__).resolve().parent.parent
    service = (root / "oxcad" / "WorkspaceService.cs").read_text(
        encoding="utf-8"
    )
    control = (root / "oxcad" / "OxCadControl.xaml.cs").read_text(
        encoding="utf-8"
    )
    plugin = (root / "oxcad" / "Plugin.cs").read_text(encoding="utf-8")

    assert "--execution-id" in service
    assert "--wait-for-completion" in service
    assert "execution.DwgIdentity" in control
    assert "execution.CorrelationId" in control
    assert "document.CommandCancelled += OnDocumentCommandCancelled" in plugin
    assert "OxCadExecutionState.Cancelado" in plugin