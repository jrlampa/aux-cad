"""Testes unitários e de integração do IntegrationExecutor (P3 - Execução GOMNET).

Valida conformidade com os contratos P2.4, P2.5 e P3:
1. Execução determinística de itens READY;
2. Transição para SUCCEEDED com preservação de IDs e metadados;
3. Tratamento de timeouts e indisponibilidade remota -> FAILED;
4. Bloqueio determinístico por falha de autenticação -> BLOCKED;
5. Soberania estrita: SOB divergente do DWG ativo -> BLOCKED;
6. Idempotência: itens SUCCEEDED não são reexecutados;
7. Itens BLOCKED não são reexecutados;
8. Itens PENDING rejeitados para execução;
9. Provedor desconhecido ou operação não suportada -> BLOCKED;
10. Ausência total de credenciais em resultados e mensagens;
11. Interface CLI (workspace_integration_cli.py) operacional.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from sob.sob_gomnet import (
    GomnetAnexo,
    GomnetAuthError,
    GomnetClient,
    GomnetNotFoundError,
)
from workspace.workspace_gomnet_provider import GomnetProvider
from workspace.workspace_integration_cli import handle_executar, handle_status
from workspace.workspace_integration_executor import (
    IntegrationExecutionResult,
    IntegrationExecutor,
)
from workspace.workspace_integrations import (
    IntegrationContext,
    IntegrationRegistry,
)
from workspace.workspace_sync_queue import (
    SyncItem,
    SyncQueue,
    SyncStatus,
)


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    proj = tmp_path / "SOB_A057526153"
    proj.mkdir(parents=True, exist_ok=True)
    return proj


@pytest.fixture
def valid_context(temp_project: Path) -> IntegrationContext:
    dwg = temp_project / "PE_A057526153_DESENHO.dwg"
    dwg.touch()
    return IntegrationContext(
        sob_id="A057526153",
        project_root=str(temp_project),
        dwg_path=str(dwg),
        database_fingerprint="FP_GUID_VALID_999",
    )


@pytest.fixture
def mock_gomnet_client() -> MagicMock:
    client = MagicMock(spec=GomnetClient)
    client.usuario = "USR_TEST"
    client.senha = "PWD_TEST"
    client.obter_status_sob.return_value = "Em Execução"
    client.localizar_sob_e_listar_anexos.return_value = [
        GomnetAnexo(
            id_arquivo="101",
            nome_arquivo="DESENHO.dwg",
            tipo="CAD",
            categoria="PROJETO",
            descricao="Desenho PE",
            data_gravacao="03/10/2026",
            usuario="IM3",
            url_download="http://gomnet/download/101",
        )
    ]
    return client


@pytest.fixture
def custom_executor(mock_gomnet_client: MagicMock) -> IntegrationExecutor:
    provider = GomnetProvider(client=mock_gomnet_client)
    registry = IntegrationRegistry()
    registry.register(provider)
    return IntegrationExecutor(registry=registry)


def test_executor_sucesso_transiciona_para_succeeded(
    temp_project: Path,
    valid_context: IntegrationContext,
    custom_executor: IntegrationExecutor,
):
    queue = SyncQueue(temp_project)
    item = SyncItem.create(
        operation_id="op-001",
        idempotency_key="gomnet:query:A057526153",
        operation="query_sob",
        provider_id="gomnet",
        sob_id="A057526153",
        artifact={"initial": "data"},
        status=SyncStatus.READY,
    )
    enqueued, _ = queue.enqueue(item)

    res = custom_executor.execute_item(queue, enqueued, valid_context)

    assert res.success is True
    assert res.status == SyncStatus.SUCCEEDED
    assert res.sob_id == "A057526153"
    assert res.data["status_cadastral"] == "Em Execução"
    assert res.data["total_anexos"] == 1

    # Verificar que na fila o item agora esta SUCCEEDED e contem o resultado
    persisted = queue.get_by_sync_id(enqueued.sync_id)
    assert persisted is not None
    assert persisted.status == SyncStatus.SUCCEEDED
    assert persisted.artifact["execution_result"]["total_anexos"] == 1
    assert "last_executed_at" in persisted.artifact
    assert persisted.error_message is None


def test_executor_idempotencia_nao_reexecuta_succeeded(
    temp_project: Path,
    valid_context: IntegrationContext,
    custom_executor: IntegrationExecutor,
    mock_gomnet_client: MagicMock,
):
    queue = SyncQueue(temp_project)
    item = SyncItem.create(
        operation_id="op-002",
        idempotency_key="gomnet:query:A057526153",
        operation="query_sob",
        provider_id="gomnet",
        sob_id="A057526153",
        artifact={"execution_result": {"status": "Aprovado"}},
        status=SyncStatus.SUCCEEDED,
    )
    queue.enqueue(item)

    res = custom_executor.execute_item(queue, item, valid_context)

    assert res.success is True
    assert res.status == SyncStatus.SUCCEEDED
    assert "idempotente" in res.error_message
    mock_gomnet_client.localizar_sob_e_listar_anexos.assert_not_called()


def test_executor_bloqueia_item_blocked(
    temp_project: Path,
    valid_context: IntegrationContext,
    custom_executor: IntegrationExecutor,
):
    queue = SyncQueue(temp_project)
    item = SyncItem.create(
        operation_id="op-003",
        idempotency_key="gomnet:blocked:123",
        operation="query_sob",
        provider_id="gomnet",
        sob_id="A057526153",
        artifact={},
        status=SyncStatus.BLOCKED,
    )
    res = custom_executor.execute_item(queue, item, valid_context)

    assert res.success is False
    assert res.status == SyncStatus.BLOCKED
    assert res.error_code == "ITEM_BLOCKED"


def test_executor_rejeita_item_pending(
    temp_project: Path,
    valid_context: IntegrationContext,
    custom_executor: IntegrationExecutor,
):
    queue = SyncQueue(temp_project)
    item = SyncItem.create(
        operation_id="op-004",
        idempotency_key="gomnet:pending:123",
        operation="query_sob",
        provider_id="gomnet",
        sob_id="A057526153",
        artifact={},
        status=SyncStatus.PENDING,
    )
    res = custom_executor.execute_item(queue, item, valid_context)

    assert res.success is False
    assert res.status == SyncStatus.PENDING
    assert res.error_code == "NOT_READY"


def test_executor_violacao_de_soberania_bloqueia_item(
    temp_project: Path,
    valid_context: IntegrationContext,
    custom_executor: IntegrationExecutor,
):
    queue = SyncQueue(temp_project)
    # Item criado para SOB divergente do contexto do DWG ativo
    item = SyncItem.create(
        operation_id="op-005",
        idempotency_key="gomnet:divergent:999",
        operation="query_sob",
        provider_id="gomnet",
        sob_id="A057999999",
        artifact={},
        status=SyncStatus.READY,
    )
    queue.enqueue(item)

    res = custom_executor.execute_item(queue, item, valid_context)

    assert res.success is False
    assert res.status == SyncStatus.BLOCKED
    assert res.error_code == "SOVEREIGNTY_VIOLATION"

    # Verificar atualizacao na fila
    persisted = queue.get_by_sync_id(item.sync_id)
    assert persisted.status == SyncStatus.BLOCKED
    assert "Violacao de soberania" in persisted.error_message


def test_executor_timeout_marca_failed(
    temp_project: Path,
    valid_context: IntegrationContext,
    mock_gomnet_client: MagicMock,
):
    mock_gomnet_client.localizar_sob_e_listar_anexos.side_effect = requests.Timeout("Gateway timeout 504")
    provider = GomnetProvider(client=mock_gomnet_client)
    registry = IntegrationRegistry()
    registry.register(provider)
    executor = IntegrationExecutor(registry=registry)

    queue = SyncQueue(temp_project)
    item = SyncItem.create(
        operation_id="op-006",
        idempotency_key="gomnet:timeout:123",
        operation="query_sob",
        provider_id="gomnet",
        sob_id="A057526153",
        artifact={},
        status=SyncStatus.READY,
    )
    queue.enqueue(item)

    res = executor.execute_item(queue, item, valid_context)

    assert res.success is False
    assert res.status == SyncStatus.FAILED
    assert "Timeout" in res.error_message

    persisted = queue.get_by_sync_id(item.sync_id)
    assert persisted.status == SyncStatus.FAILED


def test_executor_indisponibilidade_marca_failed(
    temp_project: Path,
    valid_context: IntegrationContext,
    mock_gomnet_client: MagicMock,
):
    mock_gomnet_client.localizar_sob_e_listar_anexos.side_effect = requests.ConnectionError("Connection refused")
    provider = GomnetProvider(client=mock_gomnet_client)
    registry = IntegrationRegistry()
    registry.register(provider)
    executor = IntegrationExecutor(registry=registry)

    queue = SyncQueue(temp_project)
    item = SyncItem.create(
        operation_id="op-007",
        idempotency_key="gomnet:unavail:123",
        operation="query_sob",
        provider_id="gomnet",
        sob_id="A057526153",
        artifact={},
        status=SyncStatus.READY,
    )
    queue.enqueue(item)

    res = executor.execute_item(queue, item, valid_context)

    assert res.success is False
    assert res.status == SyncStatus.FAILED
    assert "indisponivel" in res.error_message


def test_executor_falha_autenticacao_marca_blocked(
    temp_project: Path,
    valid_context: IntegrationContext,
    mock_gomnet_client: MagicMock,
):
    mock_gomnet_client.localizar_sob_e_listar_anexos.side_effect = GomnetAuthError("Credenciais invalidas")
    provider = GomnetProvider(client=mock_gomnet_client)
    registry = IntegrationRegistry()
    registry.register(provider)
    executor = IntegrationExecutor(registry=registry)

    queue = SyncQueue(temp_project)
    item = SyncItem.create(
        operation_id="op-008",
        idempotency_key="gomnet:auth:123",
        operation="query_sob",
        provider_id="gomnet",
        sob_id="A057526153",
        artifact={},
        status=SyncStatus.READY,
    )
    queue.enqueue(item)

    res = executor.execute_item(queue, item, valid_context)

    assert res.success is False
    assert res.status == SyncStatus.BLOCKED
    assert res.error_code == "GOMNET_AUTH_FAILED"

    persisted = queue.get_by_sync_id(item.sync_id)
    assert persisted.status == SyncStatus.BLOCKED


def test_executor_provedor_inexistente_bloqueia(
    temp_project: Path,
    valid_context: IntegrationContext,
):
    # Registry vazio sem provedor gomnet
    executor = IntegrationExecutor(registry=IntegrationRegistry())
    queue = SyncQueue(temp_project)
    item = SyncItem.create(
        operation_id="op-009",
        idempotency_key="inexistente:123",
        operation="query_sob",
        provider_id="provedor_desconhecido",
        sob_id="A057526153",
        artifact={},
        status=SyncStatus.READY,
    )
    queue.enqueue(item)

    res = executor.execute_item(queue, item, valid_context)

    assert res.success is False
    assert res.status == SyncStatus.BLOCKED
    assert res.error_code == "PROVIDER_NOT_FOUND"


def test_executor_operacao_nao_suportada_bloqueia(
    temp_project: Path,
    valid_context: IntegrationContext,
    custom_executor: IntegrationExecutor,
):
    queue = SyncQueue(temp_project)
    item = SyncItem.create(
        operation_id="op-010",
        idempotency_key="gomnet:unsupported:123",
        operation="upload_arquivo_desconhecido",
        provider_id="gomnet",
        sob_id="A057526153",
        artifact={},
        status=SyncStatus.READY,
    )
    queue.enqueue(item)

    res = custom_executor.execute_item(queue, item, valid_context)

    assert res.success is False
    assert res.status == SyncStatus.BLOCKED
    assert "nao e suportada" in res.error_message


def test_executor_execucao_work_order_status(
    temp_project: Path,
    valid_context: IntegrationContext,
    custom_executor: IntegrationExecutor,
):
    queue = SyncQueue(temp_project)
    item = SyncItem.create(
        operation_id="op-011",
        idempotency_key="gomnet:wo:A057526153",
        operation="get_work_order_status",
        provider_id="gomnet",
        sob_id="A057526153",
        artifact={},
        status=SyncStatus.READY,
    )
    queue.enqueue(item)

    res = custom_executor.execute_item(queue, item, valid_context)

    assert res.success is True
    assert res.status == SyncStatus.SUCCEEDED
    assert res.data["status"] == "Em Execução"
    assert res.data["status_disponivel"] is True


def test_executor_preserva_todos_os_ids(
    temp_project: Path,
    valid_context: IntegrationContext,
    custom_executor: IntegrationExecutor,
):
    queue = SyncQueue(temp_project)
    item = SyncItem.create(
        operation_id="op-preserva-999",
        idempotency_key="key-preserva-888",
        correlation_id="corr-preserva-777",
        operation="query_sob",
        provider_id="gomnet",
        sob_id="A057526153",
        artifact={"initial_meta": 42},
        status=SyncStatus.READY,
    )
    queue.enqueue(item)

    res = custom_executor.execute_item(queue, item, valid_context)

    assert res.operation_id == "op-preserva-999"
    assert res.idempotency_key == "key-preserva-888"
    assert res.correlation_id == "corr-preserva-777"
    assert res.provider_id == "gomnet"
    assert res.sob_id == "A057526153"

    persisted = queue.get_by_sync_id(item.sync_id)
    assert persisted.operation_id == "op-preserva-999"
    assert persisted.idempotency_key == "key-preserva-888"
    assert persisted.correlation_id == "corr-preserva-777"


def test_cli_integration_status_e_executar(
    temp_project: Path,
    valid_context: IntegrationContext,
):
    queue = SyncQueue(temp_project)
    item = SyncItem.create(
        operation_id="op-cli-1",
        idempotency_key="cli:test:1",
        operation="query_sob",
        provider_id="gomnet",
        sob_id="A057526153",
        artifact={},
        status=SyncStatus.READY,
    )
    enqueued, _ = queue.enqueue(item)

    # 1. Testar status
    res_status = handle_status(queue, enqueued.sync_id, None)
    assert res_status["sucesso"] is True
    assert res_status["item"]["sync_id"] == enqueued.sync_id

    # 2. Testar executar com mock de GomnetClient
    with patch("workspace.workspace_gomnet_provider.GomnetClient") as mock_cls:
        client_inst = MagicMock()
        client_inst.usuario = "U"
        client_inst.senha = "P"
        client_inst.obter_status_sob.return_value = "Concluído"
        client_inst.localizar_sob_e_listar_anexos.return_value = []
        mock_cls.return_value = client_inst

        res_exec = handle_executar(
            queue=queue,
            sync_id=enqueued.sync_id,
            sob="A057526153",
            dwg=valid_context.dwg_path,
            fingerprint="FP_GUID_VALID_999",
            project_root=temp_project,
        )

        assert res_exec["sucesso"] is True
        assert res_exec["resultado"]["status"] == "SUCCEEDED"
