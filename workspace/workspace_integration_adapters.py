"""Adaptadores arquiteturais padrao para a plataforma de integracao do OXCAD (P2.4).

Registram descriptors declarativos e capacidades sem estabelecer conexoes
externas de rede ou persistir segredos.
"""

from __future__ import annotations

from typing import List, Optional

from workspace.workspace_integrations import (
    AuthenticationDescriptor,
    AvailabilityStatus,
    ConfigurationStatus,
    IArtifactRepository,
    IBusinessSystemProvider,
    ICustomerProvider,
    IDocumentRepository,
    IEventProvider,
    IIdentityProvider,
    IRestProvider,
    ISoapProvider,
    IWorkOrderProvider,
    IntegrationCapability,
    IntegrationContext,
    IntegrationDescriptor,
    IntegrationResult,
    UnconfiguredProviderBase,
)


class LocalFileRepositoryAdapter(IArtifactRepository, IDocumentRepository):
    """Repositorio local de artefatos e documentos integrado ao workspace."""
    def __init__(self) -> None:
        self._descriptor = IntegrationDescriptor(
            provider_id="local",
            display_name="Repositorio Local",
            provider_type="Storage",
            version="1.0.0",
            capabilities={
                IntegrationCapability.DOCUMENT_READ,
                IntegrationCapability.DOCUMENT_WRITE,
                IntegrationCapability.ARTIFACT_READ,
                IntegrationCapability.ARTIFACT_WRITE,
            },
            authentication=AuthenticationDescriptor.none(),
            configuration_status=ConfigurationStatus.CONFIGURED,
            availability=AvailabilityStatus.AVAILABLE,
        )

    @property
    def provider_id(self) -> str:
        return "local"

    @property
    def descriptor(self) -> IntegrationDescriptor:
        return self._descriptor

    def check_availability(self) -> IntegrationResult:
        return IntegrationResult.success()

    def get_artifact_status(self, context: IntegrationContext, artifact_name: str) -> IntegrationResult:
        return IntegrationResult.success({"artifact": artifact_name, "status": "AVAILABLE_LOCAL"})

    def list_documents(self, context: IntegrationContext, folder_path: str) -> IntegrationResult:
        return IntegrationResult.success([])

    def get_document_metadata(self, context: IntegrationContext, document_id: str) -> IntegrationResult:
        return IntegrationResult.success({"document_id": document_id, "type": "local"})


class MicrosoftGraphAdapter(UnconfiguredProviderBase, IIdentityProvider, IDocumentRepository):
    """Adaptador arquitetural para Microsoft Graph (futuro)."""
    def __init__(self) -> None:
        super().__init__(IntegrationDescriptor(
            provider_id="microsoft.graph",
            display_name="Microsoft Graph",
            provider_type="Microsoft",
            version="1.0.0",
            capabilities={
                IntegrationCapability.IDENTITY_READ,
                IntegrationCapability.USER_READ,
                IntegrationCapability.DOCUMENT_READ,
                IntegrationCapability.ARTIFACT_READ,
            },
            authentication=AuthenticationDescriptor.oauth2_user_delegated(),
            configuration_status=ConfigurationStatus.NOT_CONFIGURED,
            availability=AvailabilityStatus.UNAVAILABLE,
        ))

    def get_user_display_name(self, context: IntegrationContext, user_id: str) -> IntegrationResult:
        return IntegrationResult.not_configured("Microsoft Graph nao configurado.")

    def list_documents(self, context: IntegrationContext, folder_path: str) -> IntegrationResult:
        return IntegrationResult.not_configured("Microsoft Graph nao configurado.")

    def get_document_metadata(self, context: IntegrationContext, document_id: str) -> IntegrationResult:
        return IntegrationResult.not_configured("Microsoft Graph nao configurado.")


class MicrosoftEntraAdapter(UnconfiguredProviderBase, IIdentityProvider):
    """Adaptador arquitetural para Microsoft Entra ID (futuro)."""
    def __init__(self) -> None:
        super().__init__(IntegrationDescriptor(
            provider_id="microsoft.entra",
            display_name="Microsoft Entra ID",
            provider_type="Identity",
            version="1.0.0",
            capabilities={
                IntegrationCapability.IDENTITY_READ,
                IntegrationCapability.USER_READ,
            },
            authentication=AuthenticationDescriptor.openid_connect(),
            configuration_status=ConfigurationStatus.NOT_CONFIGURED,
            availability=AvailabilityStatus.UNAVAILABLE,
        ))

    def get_user_display_name(self, context: IntegrationContext, user_id: str) -> IntegrationResult:
        return IntegrationResult.not_configured("Microsoft Entra ID nao configurado.")


class SharePointAdapter(UnconfiguredProviderBase, IDocumentRepository, IArtifactRepository):
    """Adaptador arquitetural para SharePoint (futuro)."""
    def __init__(self) -> None:
        super().__init__(IntegrationDescriptor(
            provider_id="sharepoint",
            display_name="SharePoint",
            provider_type="DocumentRepository",
            version="1.0.0",
            capabilities={
                IntegrationCapability.DOCUMENT_READ,
                IntegrationCapability.DOCUMENT_WRITE,
                IntegrationCapability.ARTIFACT_READ,
                IntegrationCapability.ARTIFACT_WRITE,
            },
            authentication=AuthenticationDescriptor.oauth2_user_delegated(),
            configuration_status=ConfigurationStatus.NOT_CONFIGURED,
            availability=AvailabilityStatus.UNAVAILABLE,
        ))

    def list_documents(self, context: IntegrationContext, folder_path: str) -> IntegrationResult:
        return IntegrationResult.not_configured("SharePoint nao configurado.")

    def get_document_metadata(self, context: IntegrationContext, document_id: str) -> IntegrationResult:
        return IntegrationResult.not_configured("SharePoint nao configurado.")

    def get_artifact_status(self, context: IntegrationContext, artifact_name: str) -> IntegrationResult:
        return IntegrationResult.not_configured("SharePoint nao configurado.")


class OneDriveAdapter(UnconfiguredProviderBase, IDocumentRepository, IArtifactRepository):
    """Adaptador arquitetural para OneDrive (futuro)."""
    def __init__(self) -> None:
        super().__init__(IntegrationDescriptor(
            provider_id="onedrive",
            display_name="OneDrive",
            provider_type="DocumentRepository",
            version="1.0.0",
            capabilities={
                IntegrationCapability.DOCUMENT_READ,
                IntegrationCapability.DOCUMENT_WRITE,
                IntegrationCapability.ARTIFACT_READ,
                IntegrationCapability.ARTIFACT_WRITE,
            },
            authentication=AuthenticationDescriptor.oauth2_user_delegated(),
            configuration_status=ConfigurationStatus.NOT_CONFIGURED,
            availability=AvailabilityStatus.UNAVAILABLE,
        ))

    def list_documents(self, context: IntegrationContext, folder_path: str) -> IntegrationResult:
        return IntegrationResult.not_configured("OneDrive nao configurado.")

    def get_document_metadata(self, context: IntegrationContext, document_id: str) -> IntegrationResult:
        return IntegrationResult.not_configured("OneDrive nao configurado.")

    def get_artifact_status(self, context: IntegrationContext, artifact_name: str) -> IntegrationResult:
        return IntegrationResult.not_configured("OneDrive nao configurado.")


class SapAdapter(UnconfiguredProviderBase, IBusinessSystemProvider, IWorkOrderProvider):
    """Adaptador arquitetural para SAP ERP (futuro)."""
    def __init__(self) -> None:
        super().__init__(IntegrationDescriptor(
            provider_id="sap",
            display_name="SAP",
            provider_type="ERP",
            version="1.0.0",
            capabilities={
                IntegrationCapability.WORK_ORDER_READ,
                IntegrationCapability.BUSINESS_DATA_READ,
            },
            authentication=AuthenticationDescriptor.oauth2_client_credentials(),
            configuration_status=ConfigurationStatus.NOT_CONFIGURED,
            availability=AvailabilityStatus.UNAVAILABLE,
        ))

    def query_business_entity(self, context: IntegrationContext, entity_type: str, entity_key: str) -> IntegrationResult:
        return IntegrationResult.not_configured("SAP ERP nao configurado.")

    def get_work_order_status(self, context: IntegrationContext, order_id: str) -> IntegrationResult:
        return IntegrationResult.not_configured("SAP ERP nao configurado.")


class SapS4HanaAdapter(UnconfiguredProviderBase, IBusinessSystemProvider, IWorkOrderProvider):
    """Adaptador arquitetural para SAP S/4HANA (futuro)."""
    def __init__(self) -> None:
        super().__init__(IntegrationDescriptor(
            provider_id="sap.s4hana",
            display_name="SAP S/4HANA",
            provider_type="ERP",
            version="1.0.0",
            capabilities={
                IntegrationCapability.WORK_ORDER_READ,
                IntegrationCapability.WORK_ORDER_WRITE,
                IntegrationCapability.BUSINESS_DATA_READ,
                IntegrationCapability.BUSINESS_DATA_WRITE,
            },
            authentication=AuthenticationDescriptor.oauth2_client_credentials(),
            configuration_status=ConfigurationStatus.NOT_CONFIGURED,
            availability=AvailabilityStatus.UNAVAILABLE,
        ))

    def query_business_entity(self, context: IntegrationContext, entity_type: str, entity_key: str) -> IntegrationResult:
        return IntegrationResult.not_configured("SAP S/4HANA nao configurado.")

    def get_work_order_status(self, context: IntegrationContext, order_id: str) -> IntegrationResult:
        return IntegrationResult.not_configured("SAP S/4HANA nao configurado.")


class SapBtpAdapter(UnconfiguredProviderBase, IBusinessSystemProvider, IEventProvider):
    """Adaptador arquitetural para SAP BTP (futuro)."""
    def __init__(self) -> None:
        super().__init__(IntegrationDescriptor(
            provider_id="sap.btp",
            display_name="SAP BTP",
            provider_type="Platform",
            version="1.0.0",
            capabilities={
                IntegrationCapability.BUSINESS_DATA_READ,
                IntegrationCapability.EVENT_SUBSCRIBE,
            },
            authentication=AuthenticationDescriptor.oauth2_client_credentials(),
            configuration_status=ConfigurationStatus.NOT_CONFIGURED,
            availability=AvailabilityStatus.UNAVAILABLE,
        ))

    def query_business_entity(self, context: IntegrationContext, entity_type: str, entity_key: str) -> IntegrationResult:
        return IntegrationResult.not_configured("SAP BTP nao configurado.")

    def publish_event(self, context: IntegrationContext, event_type: str, payload_reference: str) -> IntegrationResult:
        return IntegrationResult.not_configured("SAP BTP nao configurado.")


class SalesforceAdapter(UnconfiguredProviderBase, ICustomerProvider):
    """Adaptador arquitetural para Salesforce CRM (futuro)."""
    def __init__(self) -> None:
        super().__init__(IntegrationDescriptor(
            provider_id="salesforce",
            display_name="Salesforce",
            provider_type="CRM",
            version="1.0.0",
            capabilities={
                IntegrationCapability.CUSTOMER_READ,
                IntegrationCapability.CUSTOMER_WRITE,
            },
            authentication=AuthenticationDescriptor.oauth2_user_delegated(),
            configuration_status=ConfigurationStatus.NOT_CONFIGURED,
            availability=AvailabilityStatus.UNAVAILABLE,
        ))

    def get_customer_info(self, context: IntegrationContext, customer_id: str) -> IntegrationResult:
        return IntegrationResult.not_configured("Salesforce CRM nao configurado.")


class RestGatewayAdapter(IRestProvider):
    """Gateway declarativo para chamadas REST corporativas."""
    def __init__(self) -> None:
        self._descriptor = IntegrationDescriptor(
            provider_id="rest",
            display_name="REST Gateway",
            provider_type="Gateway",
            version="1.0.0",
            capabilities={IntegrationCapability.REST_CALL},
            authentication=AuthenticationDescriptor.api_key(),
            configuration_status=ConfigurationStatus.CONFIGURED,
            availability=AvailabilityStatus.AVAILABLE,
        )

    @property
    def provider_id(self) -> str:
        return "rest"

    @property
    def descriptor(self) -> IntegrationDescriptor:
        return self._descriptor

    def check_availability(self) -> IntegrationResult:
        return IntegrationResult.success()

    def execute_rest_request(self, context: IntegrationContext, method: str, relative_uri: str) -> IntegrationResult:
        return IntegrationResult.not_configured("Endpoint REST corporativo nao conectado nesta fase.")


class SoapGatewayAdapter(ISoapProvider):
    """Gateway declarativo para chamadas SOAP legadas."""
    def __init__(self) -> None:
        self._descriptor = IntegrationDescriptor(
            provider_id="soap",
            display_name="SOAP Gateway",
            provider_type="Gateway",
            version="1.0.0",
            capabilities={IntegrationCapability.SOAP_CALL},
            authentication=AuthenticationDescriptor.basic_auth(),
            configuration_status=ConfigurationStatus.CONFIGURED,
            availability=AvailabilityStatus.AVAILABLE,
        )

    @property
    def provider_id(self) -> str:
        return "soap"

    @property
    def descriptor(self) -> IntegrationDescriptor:
        return self._descriptor

    def check_availability(self) -> IntegrationResult:
        return IntegrationResult.success()

    def execute_soap_action(self, context: IntegrationContext, action: str, xml_payload: str) -> IntegrationResult:
        return IntegrationResult.not_configured("Servico SOAP legado nao conectado nesta fase.")
