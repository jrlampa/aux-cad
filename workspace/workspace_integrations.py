"""Plataforma de Integracao e Extensibilidade do OXCAD (P2.4).

Define contratos de dominio, descritores puramente declarativos, capacidades,
contexto soberano do projeto e catalogo deterministico de integracoes.

Regras Fundamentais:
1. Core do OXCAD conhece exclusivamente contratos de dominio, nunca URLs, endpoints ou SDKs.
2. Nenhuma credencial, token, senha ou chave secreta e persistida ou armazenada.
3. Nenhuma chamada de rede externa e ativada nesta fase.
4. O AutoCAD e a unica autoridade soberana da identidade real do DWG e SOB_ID.
5. Zero criacao de OxCadExecution e zero efeitos colaterais em disco.
"""

from __future__ import annotations

import uuid
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class IntegrationCapability(str, Enum):
    """Catalogo de capacidades funcionais suportadas por provedores."""
    # Documentos e Arquivos
    DOCUMENT_READ = "DOCUMENT_READ"
    DOCUMENT_WRITE = "DOCUMENT_WRITE"
    ARTIFACT_READ = "ARTIFACT_READ"
    ARTIFACT_WRITE = "ARTIFACT_WRITE"

    # Ordens de Servico e Processos
    WORK_ORDER_READ = "WORK_ORDER_READ"
    WORK_ORDER_WRITE = "WORK_ORDER_WRITE"

    # Sistemas Corporativos e ERP
    BUSINESS_DATA_READ = "BUSINESS_DATA_READ"
    BUSINESS_DATA_WRITE = "BUSINESS_DATA_WRITE"

    # Clientes e CRM
    CUSTOMER_READ = "CUSTOMER_READ"
    CUSTOMER_WRITE = "CUSTOMER_WRITE"

    # Identidade e Acesso
    IDENTITY_READ = "IDENTITY_READ"
    USER_READ = "USER_READ"

    # Mensageria e Eventos
    EVENT_SUBSCRIBE = "EVENT_SUBSCRIBE"
    EVENT_PUBLISH = "EVENT_PUBLISH"

    # Protocolos Genericos
    REST_CALL = "REST_CALL"
    SOAP_CALL = "SOAP_CALL"


class AuthenticationScheme(str, Enum):
    """Esquema declarativo de autenticacao."""
    NONE = "NONE"
    OAUTH2 = "OAUTH2"
    OPENID_CONNECT = "OPENID_CONNECT"
    CLIENT_CREDENTIALS = "CLIENT_CREDENTIALS"
    AUTHORIZATION_CODE = "AUTHORIZATION_CODE"
    SERVICE_ACCOUNT = "SERVICE_ACCOUNT"
    API_KEY = "API_KEY"
    BASIC_AUTH = "BASIC_AUTH"
    NTLM = "NTLM"


@dataclass(frozen=True)
class AuthenticationDescriptor:
    """Descritor puramente declarativo de requisitos de autenticacao."""
    scheme: AuthenticationScheme
    requires_user_context: bool = False
    requires_client_credential: bool = False
    supports_refresh: bool = False

    @classmethod
    def none(cls) -> AuthenticationDescriptor:
        return cls(AuthenticationScheme.NONE)

    @classmethod
    def oauth2_user_delegated(cls, supports_refresh: bool = True) -> AuthenticationDescriptor:
        return cls(
            scheme=AuthenticationScheme.OAUTH2,
            requires_user_context=True,
            requires_client_credential=True,
            supports_refresh=supports_refresh,
        )

    @classmethod
    def oauth2_client_credentials(cls) -> AuthenticationDescriptor:
        return cls(
            scheme=AuthenticationScheme.CLIENT_CREDENTIALS,
            requires_user_context=False,
            requires_client_credential=True,
            supports_refresh=False,
        )

    @classmethod
    def openid_connect(cls) -> AuthenticationDescriptor:
        return cls(
            scheme=AuthenticationScheme.OPENID_CONNECT,
            requires_user_context=True,
            requires_client_credential=True,
            supports_refresh=True,
        )

    @classmethod
    def api_key(cls) -> AuthenticationDescriptor:
        return cls(
            scheme=AuthenticationScheme.API_KEY,
            requires_user_context=False,
            requires_client_credential=True,
            supports_refresh=False,
        )

    @classmethod
    def basic_auth(cls) -> AuthenticationDescriptor:
        return cls(
            scheme=AuthenticationScheme.BASIC_AUTH,
            requires_user_context=True,
            requires_client_credential=True,
            supports_refresh=False,
        )


class IntegrationStatus(str, Enum):
    """Estados padronizados de execucao e disponibilidade."""
    SUCCESS = "SUCCESS"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    INVALID_REQUEST = "INVALID_REQUEST"
    REMOTE_ERROR = "REMOTE_ERROR"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class IntegrationResult:
    """Resultado padronizado de operacoes de integracao."""
    status: IntegrationStatus
    data: Optional[Any] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    technical_details: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.status == IntegrationStatus.SUCCESS

    @classmethod
    def success(cls, data: Optional[Any] = None) -> IntegrationResult:
        return cls(status=IntegrationStatus.SUCCESS, data=data)

    @classmethod
    def not_configured(cls, message: str = "Provedor nao configurado.") -> IntegrationResult:
        return cls(status=IntegrationStatus.NOT_CONFIGURED, error_code="NOT_CONFIGURED", error_message=message)

    @classmethod
    def not_supported(cls, message: str = "Capacidade nao suportada pelo provedor.") -> IntegrationResult:
        return cls(status=IntegrationStatus.NOT_SUPPORTED, error_code="NOT_SUPPORTED", error_message=message)

    @classmethod
    def auth_required(cls, message: str = "Autenticacao requerida.") -> IntegrationResult:
        return cls(status=IntegrationStatus.AUTH_REQUIRED, error_code="AUTH_REQUIRED", error_message=message)

    @classmethod
    def unavailable(cls, message: str = "Provedor indisponivel.") -> IntegrationResult:
        return cls(status=IntegrationStatus.UNAVAILABLE, error_code="UNAVAILABLE", error_message=message)

    @classmethod
    def timeout(cls, message: str = "Tempo limite excedido.") -> IntegrationResult:
        return cls(status=IntegrationStatus.TIMEOUT, error_code="TIMEOUT", error_message=message)

    @classmethod
    def invalid_request(cls, message: str = "Requisicao invalida.") -> IntegrationResult:
        return cls(status=IntegrationStatus.INVALID_REQUEST, error_code="INVALID_REQUEST", error_message=message)

    @classmethod
    def remote_error(cls, message: str, details: Optional[str] = None) -> IntegrationResult:
        return cls(status=IntegrationStatus.REMOTE_ERROR, error_code="REMOTE_ERROR", error_message=message, technical_details=details)

    @classmethod
    def identity_mismatch(cls, message: str = "Inconsistencia de identidade ou violacao de autoridade do DWG.") -> IntegrationResult:
        return cls(status=IntegrationStatus.IDENTITY_MISMATCH, error_code="IDENTITY_MISMATCH", error_message=message)

    @classmethod
    def cancelled(cls, message: str = "Operacao cancelada.") -> IntegrationResult:
        return cls(status=IntegrationStatus.CANCELLED, error_code="CANCELLED", error_message=message)


@dataclass(frozen=True)
class WorkOrderQuery:
    """Explicit query identity, independent of DWG/project scope."""
    grupo: str
    sob: str

    def to_dict(self) -> Dict[str, str]:
        return {"grupo": self.grupo, "sob": self.sob}

    def is_valid(self) -> bool:
        return (
            isinstance(self.grupo, str) and self.grupo in ("A", "B")
            and isinstance(self.sob, str)
            and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", self.sob) is not None
        )


@dataclass(frozen=True)
class IntegrationContext:
    """Contexto de execucao com soberania estrita de identidade DWG/SOB."""
    sob_id: str
    project_root: str
    dwg_path: str
    database_fingerprint: str
    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    execution_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        if not self.sob_id or not self.sob_id.strip():
            raise ValueError("sob_id obrigatorio e nao pode ser vazio.")
        if not self.project_root or not self.project_root.strip():
            raise ValueError("project_root obrigatorio e nao pode ser vazio.")
        if not self.dwg_path or not self.dwg_path.strip():
            raise ValueError("dwg_path obrigatorio e nao pode ser vazio.")
        if not self.database_fingerprint or not self.database_fingerprint.strip():
            raise ValueError("database_fingerprint obrigatorio e nao pode ser vazio.")

    def validate_sovereignty(self, requested_sob_id: str, requested_fingerprint: str) -> bool:
        """Assegura que nenhuma integracao externa altere a soberania do DWG ativo."""
        if not requested_sob_id or not requested_fingerprint:
            return False
        return (
            self.sob_id.strip().upper() == requested_sob_id.strip().upper()
            and self.database_fingerprint.strip().upper() == requested_fingerprint.strip().upper()
        )

    def validate_authority_against(self, requested_dwg_path: str) -> IntegrationResult:
        if not requested_dwg_path or not requested_dwg_path.strip():
            return IntegrationResult.invalid_request("Caminho do DWG solicitado nao informado.")
        if self.dwg_path.strip().lower() != requested_dwg_path.strip().lower():
            return IntegrationResult.identity_mismatch(
                f"Tentativa de associar DWG nao autorizado. Esperado: '{self.dwg_path}', Solicitado: '{requested_dwg_path}'."
            )
        return IntegrationResult.success()


class ConfigurationStatus(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURED = "CONFIGURED"
    DISABLED = "DISABLED"


class AvailabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class IntegrationDescriptor:
    """Descritor arquitetural padronizado de um provedor."""
    provider_id: str
    display_name: str
    provider_type: str
    version: str
    capabilities: Set[IntegrationCapability]
    authentication: AuthenticationDescriptor
    configuration_status: ConfigurationStatus = ConfigurationStatus.NOT_CONFIGURED
    availability: AvailabilityStatus = AvailabilityStatus.UNKNOWN

    @property
    def is_available(self) -> bool:
        return (
            self.availability == AvailabilityStatus.AVAILABLE
            and self.configuration_status == ConfigurationStatus.CONFIGURED
        )

    def has_capability(self, capability: IntegrationCapability) -> bool:
        return capability in self.capabilities


class IIntegrationProvider(ABC):
    """Interface base para provedores de integracao."""
    @property
    @abstractmethod
    def provider_id(self) -> str:
        pass

    @property
    @abstractmethod
    def descriptor(self) -> IntegrationDescriptor:
        pass

    def supports_capability(self, capability: IntegrationCapability) -> bool:
        return self.descriptor.has_capability(capability)

    def check_availability(self) -> IntegrationResult:
        return IntegrationResult.not_configured(f"Provedor '{self.descriptor.display_name}' nao configurado.")


class IIdentityProvider(IIntegrationProvider):
    @abstractmethod
    def get_user_display_name(self, context: IntegrationContext, user_id: str) -> IntegrationResult:
        pass


class IDocumentRepository(IIntegrationProvider):
    @abstractmethod
    def list_documents(self, context: IntegrationContext, folder_path: str) -> IntegrationResult:
        pass

    @abstractmethod
    def get_document_metadata(self, context: IntegrationContext, document_id: str) -> IntegrationResult:
        pass


class IArtifactRepository(IIntegrationProvider):
    @abstractmethod
    def get_artifact_status(self, context: IntegrationContext, artifact_name: str) -> IntegrationResult:
        pass


class IWorkOrderProvider(IIntegrationProvider):
    @abstractmethod
    def get_work_order_status(self, context: IntegrationContext, order_id: str) -> IntegrationResult:
        pass

    def query_work_order(
        self, context: IntegrationContext, query: WorkOrderQuery,
        *, independent_query: bool = False,
    ) -> IntegrationResult:
        return IntegrationResult.not_supported(
            "Consulta com identidade composta nao suportada."
        )


class IBusinessSystemProvider(IIntegrationProvider):
    @abstractmethod
    def query_business_entity(self, context: IntegrationContext, entity_type: str, entity_key: str) -> IntegrationResult:
        pass


class ICustomerProvider(IIntegrationProvider):
    @abstractmethod
    def get_customer_info(self, context: IntegrationContext, customer_id: str) -> IntegrationResult:
        pass


class INotificationProvider(IIntegrationProvider):
    @abstractmethod
    def send_notification(self, context: IntegrationContext, recipient: str, title: str, message: str) -> IntegrationResult:
        pass


class IEventProvider(IIntegrationProvider):
    @abstractmethod
    def publish_event(self, context: IntegrationContext, event_type: str, payload_reference: str) -> IntegrationResult:
        pass


class IRestProvider(IIntegrationProvider):
    @abstractmethod
    def execute_rest_request(self, context: IntegrationContext, method: str, relative_uri: str) -> IntegrationResult:
        pass


class ISoapProvider(IIntegrationProvider):
    @abstractmethod
    def execute_soap_action(self, context: IntegrationContext, action: str, xml_payload: str) -> IntegrationResult:
        pass


class UnconfiguredProviderBase(IIntegrationProvider):
    """Provedor base declarativo nao configurado (seguranca estrita sem rede)."""
    def __init__(self, descriptor: IntegrationDescriptor) -> None:
        self._descriptor = descriptor

    @property
    def provider_id(self) -> str:
        return self._descriptor.provider_id

    @property
    def descriptor(self) -> IntegrationDescriptor:
        return self._descriptor

    def check_availability(self) -> IntegrationResult:
        return IntegrationResult.not_configured(f"Provedor '{self.descriptor.display_name}' nao configurado.")


class IntegrationRegistry:
    """Registro deterministico de provedores de integracao."""
    def __init__(self) -> None:
        self._providers: Dict[str, IIntegrationProvider] = {}

    def register(self, provider: IIntegrationProvider) -> None:
        if provider is None:
            raise ValueError("Provedor nao pode ser None.")
        pid = provider.provider_id.strip()
        if pid in self._providers:
            raise ValueError(f"Provedor '{pid}' ja registrado.")
        self._providers[pid] = provider

    def unregister(self, provider_id: str) -> bool:
        if not provider_id:
            return False
        return self._providers.pop(provider_id.strip(), None) is not None

    def get(self, provider_id: str) -> Optional[IIntegrationProvider]:
        if not provider_id:
            return None
        return self._providers.get(provider_id.strip())

    def list_providers(self) -> List[IIntegrationProvider]:
        return [self._providers[k] for k in sorted(self._providers.keys())]

    def get_capabilities(self, provider_id: str) -> Set[IntegrationCapability]:
        provider = self.get(provider_id)
        if not provider:
            return set()
        return set(provider.descriptor.capabilities)

    def is_available(self, provider_id: str) -> bool:
        provider = self.get(provider_id)
        return provider.descriptor.is_available if provider else False

    def has_capability(self, provider_id: str, capability: IntegrationCapability) -> bool:
        provider = self.get(provider_id)
        return provider.supports_capability(capability) if provider else False

    @classmethod
    def create_default(cls) -> IntegrationRegistry:
        from workspace.workspace_integration_adapters import (
            LocalFileRepositoryAdapter,
            MicrosoftEntraAdapter,
            MicrosoftGraphAdapter,
            OneDriveAdapter,
            RestGatewayAdapter,
            SalesforceAdapter,
            SapAdapter,
            SapBtpAdapter,
            SapS4HanaAdapter,
            SharePointAdapter,
            SoapGatewayAdapter,
        )
        registry = cls()
        registry.register(LocalFileRepositoryAdapter())
        registry.register(MicrosoftGraphAdapter())
        registry.register(MicrosoftEntraAdapter())
        registry.register(SharePointAdapter())
        registry.register(OneDriveAdapter())
        registry.register(SapAdapter())
        registry.register(SapS4HanaAdapter())
        registry.register(SapBtpAdapter())
        registry.register(SalesforceAdapter())
        registry.register(RestGatewayAdapter())
        registry.register(SoapGatewayAdapter())
        return registry
