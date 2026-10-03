"""Adaptador de Integracao GOMNET para o OXCAD (P3 - Integracoes Externas).

Encapsula o cliente HTTP de sob/sob_gomnet.py sem duplicar logica de rede,
conectando-o aos contratos padronizados de P2.4 (Integration Gateway).

Regras de Soberania e Seguranca:
1. AutoCAD e a autoridade absoluta da identidade (FingerprintGuid, AUXCAD_PROJECT_SCOPE, SOB_ID).
2. O Python nao pode fabricar identidade.
3. Nenhuma credencial ou token persistido em disco ou codigo.
4. Operacao deterministica sem schedulers, workers ou background threads.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from workspace.workspace_integrations import (
    AuthenticationDescriptor,
    AuthenticationScheme,
    AvailabilityStatus,
    ConfigurationStatus,
    IBusinessSystemProvider,
    IWorkOrderProvider,
    IntegrationCapability,
    IntegrationContext,
    IntegrationDescriptor,
    IntegrationResult,
    IntegrationStatus,
)

try:
    from sob.sob_gomnet import (
        GomnetAnexo,
        GomnetAuthError,
        GomnetClient,
        GomnetDownloadError,
        GomnetError,
        GomnetNotFoundError,
    )
except ModuleNotFoundError:
    from sob_gomnet import (
        GomnetAnexo,
        GomnetAuthError,
        GomnetClient,
        GomnetDownloadError,
        GomnetError,
        GomnetNotFoundError,
    )

logger = logging.getLogger("aux_cad.workspace.gomnet_provider")


class GomnetProvider(IBusinessSystemProvider, IWorkOrderProvider):
    """Provedor concreto de integracao com o sistema GOMNET da distribuidora."""

    def __init__(
        self,
        client: Optional[GomnetClient] = None,
        timeout: int = 25,
    ) -> None:
        self._client = client
        self._timeout = timeout
        self._descriptor = IntegrationDescriptor(
            provider_id="gomnet",
            display_name="GOMNET (Portal Distribuidora)",
            provider_type="DistributorPortal",
            version="1.0.0",
            capabilities={
                IntegrationCapability.BUSINESS_DATA_READ,
                IntegrationCapability.WORK_ORDER_READ,
            },
            authentication=AuthenticationDescriptor(
                scheme=AuthenticationScheme.NONE,
                requires_user_context=False,
                requires_client_credential=True,
                supports_refresh=False,
            ),
            configuration_status=ConfigurationStatus.CONFIGURED,
            availability=AvailabilityStatus.AVAILABLE,
        )

    @property
    def provider_id(self) -> str:
        return "gomnet"

    @property
    def descriptor(self) -> IntegrationDescriptor:
        return self._descriptor

    def _obter_cliente(self) -> GomnetClient:
        if self._client is None:
            self._client = GomnetClient(timeout=self._timeout)
        return self._client

    def check_availability(self) -> IntegrationResult:
        """Verifica conectividade basica e configuracao sem expor credenciais."""
        try:
            client = self._obter_cliente()
            if not client.usuario or not client.senha:
                return IntegrationResult.auth_required(
                    "Credenciais do GOMNET nao configuradas no ambiente."
                )
            return IntegrationResult.success({"status": "READY_FOR_QUERY"})
        except GomnetAuthError as e:
            return IntegrationResult.auth_required(str(e))
        except Exception as e:
            return IntegrationResult.unavailable(f"Falha ao checar GOMNET: {e}")

    def query_business_entity(
        self,
        context: IntegrationContext,
        entity_type: str,
        entity_key: str,
    ) -> IntegrationResult:
        """Consulta entidade de negocio no GOMNET (entidade padrao: 'SOB')."""
        if entity_type.strip().upper() != "SOB":
            return IntegrationResult.not_supported(
                f"Entidade '{entity_type}' nao suportada pelo provedor GOMNET. Apenas 'SOB' e suportada."
            )

        sob_id = entity_key.strip().upper().replace("SOB_", "")
        if not context.validate_sovereignty(sob_id, context.database_fingerprint):
            return IntegrationResult.identity_mismatch(
                f"Tentativa de consultar SOB '{sob_id}' que diverge da soberania do DWG ativo '{context.sob_id}'."
            )

        try:
            client = self._obter_cliente()
            status = client.obter_status_sob(sob_id) if hasattr(client, "obter_status_sob") else None
            anexos = client.localizar_sob_e_listar_anexos(sob_id)

            return IntegrationResult.success({
                "sob_id": sob_id,
                "status_cadastral": status,
                "total_anexos": len(anexos),
                "anexos": [a.to_dict() for a in anexos],
            })
        except GomnetAuthError as e:
            return IntegrationResult(
                status=IntegrationStatus.AUTH_REQUIRED,
                error_code="GOMNET_AUTH_FAILED",
                error_message=str(e),
            )
        except GomnetNotFoundError as e:
            return IntegrationResult(
                status=IntegrationStatus.REMOTE_ERROR,
                error_code="GOMNET_SOB_NOT_FOUND",
                error_message=str(e),
            )
        except requests.Timeout as e:
            return IntegrationResult.timeout(f"Timeout ao consultar SOB {sob_id} no GOMNET: {e}")
        except requests.ConnectionError as e:
            return IntegrationResult.unavailable(f"Servico GOMNET indisponivel ou fora do ar: {e}")
        except Exception as e:
            return IntegrationResult.remote_error(
                f"Erro remoto ao consultar SOB {sob_id} no GOMNET: {e}"
            )

    def get_work_order_status(
        self,
        context: IntegrationContext,
        order_id: str,
    ) -> IntegrationResult:
        """Consulta status cadastral da Ordem de Servico / SOB no GOMNET."""
        sob_id = order_id.strip().upper().replace("SOB_", "")
        if not context.validate_sovereignty(sob_id, context.database_fingerprint):
            return IntegrationResult.identity_mismatch(
                f"Tentativa de consultar status da SOB '{sob_id}' incompativel com o DWG ativo '{context.sob_id}'."
            )

        try:
            client = self._obter_cliente()
            status = client.obter_status_sob(sob_id)
            return IntegrationResult.success({
                "sob_id": sob_id,
                "status": status,
                "status_disponivel": status is not None,
            })
        except GomnetAuthError as e:
            return IntegrationResult(
                status=IntegrationStatus.AUTH_REQUIRED,
                error_code="GOMNET_AUTH_FAILED",
                error_message=str(e),
            )
        except requests.Timeout as e:
            return IntegrationResult.timeout(f"Timeout ao consultar status da SOB {sob_id}: {e}")
        except Exception as e:
            return IntegrationResult.remote_error(f"Erro ao obter status da SOB no GOMNET: {e}")
