"""Executor deterministico de integracoes externas para o OXCAD (P3 - Integracoes Reais).

Consome itens em estado READY da SyncQueue, resolve o provedor via Integration Gateway,
valida estritamente a soberania de contexto do DWG ativo e executa a operacao
de forma sincrona e idempotente, atualizando a fila para SUCCEEDED, FAILED ou BLOCKED.

Regras de Governanca e Execucao:
1. Nao e daemon, worker em background, scheduler ou thread permanente.
2. Execucao exclusivamente sincrona e disparada sob demanda.
3. Respeita integralmente os estados da SyncQueue (sem criar novos estados).
4. Idempotencia estrita: itens SUCCEEDED nao sao reexecutados.
5. Soberania estrita: itens cuja SOB divirja do DWG ativo sao marcados como BLOCKED.
6. Zero segredos ou credenciais em logs, resultados ou excecoes.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from workspace.workspace_integrations import (
    IBusinessSystemProvider,
    IIntegrationProvider,
    IWorkOrderProvider,
    IntegrationContext,
    IntegrationRegistry,
    IntegrationResult,
    IntegrationStatus,
)
from workspace.workspace_sync_queue import SyncItem, SyncQueue, SyncStatus

logger = logging.getLogger("aux_cad.workspace.integration_executor")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class IntegrationExecutionResult:
    """Resultado deterministico da execucao de um item da SyncQueue."""
    success: bool
    sync_id: str
    operation_id: str
    idempotency_key: str
    correlation_id: str
    provider_id: str
    sob_id: str
    operation: str
    status: SyncStatus
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    executed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class IntegrationExecutor:
    """
    Executor síncrono e determinístico da fila de sincronização externa (P3).
    Garante a transição formal de estado:
    READY -> SUCCEEDED | FAILED | BLOCKED
    """

    def __init__(self, registry: Optional[IntegrationRegistry] = None) -> None:
        self._registry = registry or self._create_default_executor_registry()

    @staticmethod
    def _create_default_executor_registry() -> IntegrationRegistry:
        """Cria o registry padrao incluindo o provedor GOMNET preparado para P3."""
        from workspace.workspace_gomnet_provider import GomnetProvider
        registry = IntegrationRegistry.create_default()
        if registry.get("gomnet") is None:
            registry.register(GomnetProvider())
        return registry

    @property
    def registry(self) -> IntegrationRegistry:
        return self._registry

    def execute_sync_id(
        self,
        queue: SyncQueue,
        sync_id: str,
        context: IntegrationContext,
        force_reexec: bool = False,
    ) -> IntegrationExecutionResult:
        """Localiza o item por sync_id na fila e o executa com validacao de contexto."""
        item = queue.get_by_sync_id(sync_id)
        if not item:
            return IntegrationExecutionResult(
                success=False,
                sync_id=sync_id,
                operation_id="",
                idempotency_key="",
                correlation_id="",
                provider_id="",
                sob_id=context.sob_id,
                operation="",
                status=SyncStatus.FAILED,
                error_code="SYNC_ITEM_NOT_FOUND",
                error_message=f"Item com sync_id '{sync_id}' nao localizado na fila.",
                executed_at=_now_utc(),
            )
        return self.execute_item(queue, item, context, force_reexec=force_reexec)

    def execute_item(
        self,
        queue: SyncQueue,
        item: SyncItem,
        context: IntegrationContext,
        force_reexec: bool = False,
    ) -> IntegrationExecutionResult:
        """
        Executa uma única operação de integração a partir de um SyncItem.
        Valida precondições de estado, soberania de DWG e disponibilidade do provedor.
        """
        now = _now_utc()

        # 1. Regra de Idempotencia: SUCCEEDED nao pode ser regredido nem reexecutado
        if item.status == SyncStatus.SUCCEEDED and not force_reexec:
            return IntegrationExecutionResult(
                success=True,
                sync_id=item.sync_id,
                operation_id=item.operation_id,
                idempotency_key=item.idempotency_key,
                correlation_id=item.correlation_id,
                provider_id=item.provider_id,
                sob_id=item.sob_id,
                operation=item.operation,
                status=SyncStatus.SUCCEEDED,
                data=item.artifact.get("execution_result"),
                error_code=None,
                error_message="Operacao ja concluida anteriormente com sucesso (idempotente).",
                executed_at=item.updated_at or now,
            )

        # 2. Regra de Bloqueio: Itens BLOCKED nao sao executados
        if item.status == SyncStatus.BLOCKED and not force_reexec:
            return IntegrationExecutionResult(
                success=False,
                sync_id=item.sync_id,
                operation_id=item.operation_id,
                idempotency_key=item.idempotency_key,
                correlation_id=item.correlation_id,
                provider_id=item.provider_id,
                sob_id=item.sob_id,
                operation=item.operation,
                status=SyncStatus.BLOCKED,
                data=None,
                error_code="ITEM_BLOCKED",
                error_message=item.error_message or "Item bloqueado para execucao.",
                executed_at=now,
            )

        # 3. Regra de Prontidao: Somente itens READY (ou FAILED com tentativa explicita) podem executar
        if item.status == SyncStatus.PENDING:
            return IntegrationExecutionResult(
                success=False,
                sync_id=item.sync_id,
                operation_id=item.operation_id,
                idempotency_key=item.idempotency_key,
                correlation_id=item.correlation_id,
                provider_id=item.provider_id,
                sob_id=item.sob_id,
                operation=item.operation,
                status=SyncStatus.PENDING,
                data=None,
                error_code="NOT_READY",
                error_message=f"Item com status '{item.status.value}' nao esta pronto (READY) para execucao.",
                executed_at=now,
            )

        # 4. Validacao Estrita de Soberania de Identidade
        if not context.validate_sovereignty(item.sob_id, context.database_fingerprint):
            err_msg = (
                f"Violacao de soberania: a SOB do item '{item.sob_id}' diverge "
                f"da SOB do contexto do DWG ativo '{context.sob_id}'."
            )
            queue.update_status(item.sync_id, SyncStatus.BLOCKED, error=err_msg)
            return IntegrationExecutionResult(
                success=False,
                sync_id=item.sync_id,
                operation_id=item.operation_id,
                idempotency_key=item.idempotency_key,
                correlation_id=item.correlation_id,
                provider_id=item.provider_id,
                sob_id=item.sob_id,
                operation=item.operation,
                status=SyncStatus.BLOCKED,
                data=None,
                error_code="SOVEREIGNTY_VIOLATION",
                error_message=err_msg,
                executed_at=now,
            )

        # 5. Resolucao do Provedor no Integration Gateway
        provider = self._registry.get(item.provider_id)
        if not provider:
            err_msg = f"Provedor '{item.provider_id}' nao registrado no Integration Gateway."
            queue.update_status(item.sync_id, SyncStatus.BLOCKED, error=err_msg)
            return IntegrationExecutionResult(
                success=False,
                sync_id=item.sync_id,
                operation_id=item.operation_id,
                idempotency_key=item.idempotency_key,
                correlation_id=item.correlation_id,
                provider_id=item.provider_id,
                sob_id=item.sob_id,
                operation=item.operation,
                status=SyncStatus.BLOCKED,
                data=None,
                error_code="PROVIDER_NOT_FOUND",
                error_message=err_msg,
                executed_at=now,
            )

        # 6. Despacho da Operacao para o Provedor
        call_res = self._dispatch_operation(provider, item, context)

        # 7. Mapeamento Deterministico para Estados da SyncQueue
        if call_res.is_success:
            # Atualiza payload de artefato preservando metadados e IDs originais
            new_artifact = dict(item.artifact)
            new_artifact["execution_result"] = call_res.data
            new_artifact["last_executed_at"] = now
            updated_item = SyncItem(
                sync_id=item.sync_id,
                operation_id=item.operation_id,
                idempotency_key=item.idempotency_key,
                correlation_id=item.correlation_id,
                operation=item.operation,
                provider_id=item.provider_id,
                sob_id=item.sob_id,
                artifact=new_artifact,
                created_at=item.created_at,
                status=SyncStatus.SUCCEEDED,
                updated_at=now,
                error_message=None,
            )
            queue.update_item(updated_item)
            return IntegrationExecutionResult(
                success=True,
                sync_id=item.sync_id,
                operation_id=item.operation_id,
                idempotency_key=item.idempotency_key,
                correlation_id=item.correlation_id,
                provider_id=item.provider_id,
                sob_id=item.sob_id,
                operation=item.operation,
                status=SyncStatus.SUCCEEDED,
                data=call_res.data,
                executed_at=now,
            )

        # Tratar Erros FAILED vs BLOCKED conforme contratos P2.4 e P2.5
        new_status = self._map_integration_status_to_sync_status(call_res.status)
        queue.update_status(item.sync_id, new_status, error=call_res.error_message)

        return IntegrationExecutionResult(
            success=False,
            sync_id=item.sync_id,
            operation_id=item.operation_id,
            idempotency_key=item.idempotency_key,
            correlation_id=item.correlation_id,
            provider_id=item.provider_id,
            sob_id=item.sob_id,
            operation=item.operation,
            status=new_status,
            data=None,
            error_code=call_res.error_code or call_res.status.value,
            error_message=call_res.error_message or "Falha na execucao da integracao externa.",
            executed_at=now,
        )

    def _dispatch_operation(
        self,
        provider: IIntegrationProvider,
        item: SyncItem,
        context: IntegrationContext,
    ) -> IntegrationResult:
        """Despacha a operacao suportada para a interface de capacidade correspondente."""
        op = item.operation.strip().lower()

        # Operacao 1: Consulta cadastral da SOB e seus anexos (IBusinessSystemProvider)
        if op in {"query_sob", "query_business_entity", "consulta_sob"}:
            if not isinstance(provider, IBusinessSystemProvider):
                return IntegrationResult.not_supported(
                    f"Provedor '{provider.provider_id}' nao implementa IBusinessSystemProvider."
                )
            return provider.query_business_entity(context, "SOB", item.sob_id)

        # Operacao 2: Consulta de status de ordem de servico (IWorkOrderProvider)
        if op in {"get_work_order_status", "work_order_status", "status_sob"}:
            if not isinstance(provider, IWorkOrderProvider):
                return IntegrationResult.not_supported(
                    f"Provedor '{provider.provider_id}' nao implementa IWorkOrderProvider."
                )
            return provider.get_work_order_status(context, item.sob_id)

        return IntegrationResult.not_supported(
            f"Operacao '{item.operation}' nao e suportada pelo executor P3 para o provedor '{provider.provider_id}'."
        )

    @staticmethod
    def _map_integration_status_to_sync_status(status: IntegrationStatus) -> SyncStatus:
        """
        Mapeia estados do IntegrationResult para estados determinísticos da SyncQueue.
        - FAILED: Erros transitórios de rede, timeouts ou indisponibilidade remota.
        - BLOCKED: Falhas de precondição, autorização, soberania ou capacidades não suportadas.
        """
        if status in {
            IntegrationStatus.TIMEOUT,
            IntegrationStatus.UNAVAILABLE,
            IntegrationStatus.REMOTE_ERROR,
        }:
            return SyncStatus.FAILED

        if status in {
            IntegrationStatus.AUTH_REQUIRED,
            IntegrationStatus.IDENTITY_MISMATCH,
            IntegrationStatus.NOT_SUPPORTED,
            IntegrationStatus.NOT_CONFIGURED,
            IntegrationStatus.INVALID_REQUEST,
            IntegrationStatus.CANCELLED,
        }:
            return SyncStatus.BLOCKED

        return SyncStatus.FAILED
