"""Testes unitarios e de contrato do GomnetProvider (P3 - Integracoes Externas).

Valida conformidade com os contratos P2.4 (Integration Gateway),
verificacao estrita de soberania de identidade e mapeamento deterministico de erros.
"""

from unittest.mock import MagicMock
import pytest
import requests

from workspace.workspace_gomnet_provider import GomnetProvider
from workspace.workspace_integrations import (
    AuthenticationScheme,
    IntegrationCapability,
    IntegrationContext,
    IntegrationStatus,
)
from sob.sob_gomnet import (
    GomnetAnexo,
    GomnetAuthError,
    GomnetClient,
    GomnetNotFoundError,
)


@pytest.fixture
def mock_context():
    return IntegrationContext(
        sob_id="A057219996",
        project_root="/projetos/SOB_A057219996",
        dwg_path="/projetos/SOB_A057219996/PE_A057219996_DESENHO.dwg",
        database_fingerprint="FP_GUID_TEST_12345",
    )


@pytest.fixture
def sample_anexo():
    return GomnetAnexo(
        id_arquivo="998877",
        nome_arquivo="DESENHO_PE.dwg",
        tipo="CAD",
        categoria="PROJETO",
        descricao="Desenho de rede",
        data_gravacao="01/10/2026 10:00:00",
        usuario="A00123",
        url_download="http://gomnet/download/998877",
    )


def test_gomnet_provider_descriptor_e_capacidades():
    provider = GomnetProvider()
    desc = provider.descriptor

    assert provider.provider_id == "gomnet"
    assert desc.provider_type == "DistributorPortal"
    assert desc.authentication.scheme == AuthenticationScheme.NONE
    assert desc.authentication.requires_client_credential is True
    assert desc.has_capability(IntegrationCapability.BUSINESS_DATA_READ)
    assert desc.has_capability(IntegrationCapability.WORK_ORDER_READ)
    assert not desc.has_capability(IntegrationCapability.DOCUMENT_READ)
    assert not desc.has_capability(IntegrationCapability.DOCUMENT_WRITE)



def test_gomnet_provider_check_availability_sucesso():
    mock_client = MagicMock(spec=GomnetClient)
    mock_client.usuario = "USR_TEST"
    mock_client.senha = "PWD_TEST"

    provider = GomnetProvider(client=mock_client)
    res = provider.check_availability()
    assert res.is_success
    assert res.data["status"] == "READY_FOR_QUERY"


def test_gomnet_provider_check_availability_sem_credenciais():
    mock_client = MagicMock(spec=GomnetClient)
    mock_client.usuario = ""
    mock_client.senha = ""

    provider = GomnetProvider(client=mock_client)
    res = provider.check_availability()
    assert res.status == IntegrationStatus.AUTH_REQUIRED


def test_gomnet_provider_soberania_identidade_bloqueia_consulta_divergente(mock_context):
    provider = GomnetProvider()
    # Tenta consultar SOB diferente da que possui autoridade no contexto ativo
    res = provider.query_business_entity(mock_context, "SOB", "A057999999")
    assert res.status == IntegrationStatus.IDENTITY_MISMATCH
    assert "diverge da soberania do DWG ativo" in res.error_message


def test_gomnet_provider_tipo_entidade_invalido(mock_context):
    provider = GomnetProvider()
    res = provider.query_business_entity(mock_context, "CLIENTE_CRM", "A057219996")
    assert res.status == IntegrationStatus.NOT_SUPPORTED


def test_gomnet_provider_query_business_entity_sucesso(mock_context, sample_anexo):
    mock_client = MagicMock(spec=GomnetClient)
    mock_client.obter_status_sob.return_value = "Em Execução"
    mock_client.localizar_sob_e_listar_anexos.return_value = [sample_anexo]

    provider = GomnetProvider(client=mock_client)
    res = provider.query_business_entity(mock_context, "SOB", "A057219996")

    assert res.is_success
    assert res.data["sob_id"] == "A057219996"
    assert res.data["status_cadastral"] == "Em Execução"
    assert res.data["total_anexos"] == 1
    assert res.data["anexos"][0]["id"] == "998877"


def test_gomnet_provider_mapeamento_auth_error(mock_context):
    mock_client = MagicMock(spec=GomnetClient)
    mock_client.obter_status_sob.side_effect = GomnetAuthError("Usuario ou senha incorretos")

    provider = GomnetProvider(client=mock_client)
    res = provider.query_business_entity(mock_context, "SOB", "A057219996")

    assert res.status == IntegrationStatus.AUTH_REQUIRED
    assert res.error_code == "GOMNET_AUTH_FAILED"


def test_gomnet_provider_mapeamento_sob_nao_encontrada(mock_context):
    mock_client = MagicMock(spec=GomnetClient)
    mock_client.obter_status_sob.return_value = None
    mock_client.localizar_sob_e_listar_anexos.side_effect = GomnetNotFoundError("SOB inexistente")

    provider = GomnetProvider(client=mock_client)
    res = provider.query_business_entity(mock_context, "SOB", "A057219996")

    assert res.status == IntegrationStatus.REMOTE_ERROR
    assert res.error_code == "GOMNET_SOB_NOT_FOUND"


def test_gomnet_provider_mapeamento_timeout(mock_context):
    mock_client = MagicMock(spec=GomnetClient)
    mock_client.obter_status_sob.side_effect = requests.Timeout("Gateway timeout 504")

    provider = GomnetProvider(client=mock_client)
    res = provider.query_business_entity(mock_context, "SOB", "A057219996")

    assert res.status == IntegrationStatus.TIMEOUT


def test_gomnet_provider_mapeamento_indisponibilidade(mock_context):
    mock_client = MagicMock(spec=GomnetClient)
    mock_client.obter_status_sob.side_effect = requests.ConnectionError("Connection refused")

    provider = GomnetProvider(client=mock_client)
    res = provider.query_business_entity(mock_context, "SOB", "A057219996")

    assert res.status == IntegrationStatus.UNAVAILABLE


def test_gomnet_provider_get_work_order_status(mock_context):
    mock_client = MagicMock(spec=GomnetClient)
    mock_client.obter_status_sob.return_value = "Aprovado"

    provider = GomnetProvider(client=mock_client)
    res = provider.get_work_order_status(mock_context, "A057219996")

    assert res.is_success
    assert res.data["status"] == "Aprovado"
    assert res.data["status_disponivel"] is True


def test_gomnet_provider_nao_e_repositorio_documentos(mock_context):
    from workspace.workspace_integrations import IDocumentRepository
    provider = GomnetProvider()
    assert not isinstance(provider, IDocumentRepository)
    assert not hasattr(provider, "list_documents")
    assert not hasattr(provider, "get_document_metadata")
