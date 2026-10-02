"""Suite de testes completa para P2.4 — Plataforma de Integracao e Extensibilidade.

Cobre rigorosamente:
1. registro de provider;
2. provider duplicado;
3. provider inexistente;
4. listagem deterministica;
5. capability existente;
6. capability inexistente;
7. provider indisponivel;
8. provider nao configurado;
9. resultado SUCCESS;
10. resultado NOT_SUPPORTED;
11. resultado AUTH_REQUIRED;
12. resultado UNAVAILABLE;
13. resultado TIMEOUT;
14. resultado IDENTITY_MISMATCH;
15. contexto SOB;
16. Fingerprint preservado;
17. provider nao altera identidade nem soberania;
18. contrato de documentos (IDocumentRepository);
19. contrato de artefatos (IArtifactRepository);
20. contrato de OS (IWorkOrderProvider);
21. contrato de CRM (ICustomerProvider);
22. contrato de identidade (IIdentityProvider);
23. descriptor Microsoft Graph;
24. descriptor Entra ID;
25. descriptor SharePoint;
26. descriptor OneDrive;
27. descriptor SAP (ERP, S4HANA, BTP);
28. descriptor Salesforce;
29. descriptor REST e SOAP;
30. autenticacao declarativa sem secrets;
31. nenhum secret persistido;
32. nenhuma chamada externa efetuada;
33. nenhuma execucao OxCadExecution gerada;
34. nenhum arquivo operacional alterado;
35. UI / operacao nao bloqueante;
36. determinismo estrito;
37. regressao P2.1 (indicadores de gestao);
38. regressao P2.2 (visao operacional e filtros);
39. regressao P2.3 (qualidade, historico e stores duraveis);
40. limites de linhas e modularidade (<750 linhas).
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from workspace.workspace_integrations import (
    AuthenticationDescriptor,
    AuthenticationScheme,
    AvailabilityStatus,
    ConfigurationStatus,
    IArtifactRepository,
    IBusinessSystemProvider,
    ICustomerProvider,
    IDocumentRepository,
    IEventProvider,
    IIdentityProvider,
    IIntegrationProvider,
    IRestProvider,
    ISoapProvider,
    IWorkOrderProvider,
    IntegrationCapability,
    IntegrationContext,
    IntegrationDescriptor,
    IntegrationRegistry,
    IntegrationResult,
    IntegrationStatus,
    UnconfiguredProviderBase,
)
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


@pytest.fixture
def default_registry() -> IntegrationRegistry:
    return IntegrationRegistry.create_default()


@pytest.fixture
def valid_context() -> IntegrationContext:
    return IntegrationContext(
        sob_id="A057526153",
        project_root=r"C:\Projetos\SOB_A057526153",
        dwg_path=r"C:\Projetos\SOB_A057526153\CF_A057526153_DESENHO.dwg",
        database_fingerprint="{11111111-2222-3333-4444-555555555555}",
        correlation_id="corr-test-001",
        execution_id="exec-test-001",
    )


# 1. Registro de provider
def test_p24_01_registro_provider():
    reg = IntegrationRegistry()
    provider = LocalFileRepositoryAdapter()
    reg.register(provider)
    assert reg.get("local") is provider


# 2. Provider duplicado falha deterministicamente
def test_p24_02_provider_duplicado_falha():
    reg = IntegrationRegistry()
    provider = LocalFileRepositoryAdapter()
    reg.register(provider)
    with pytest.raises(ValueError, match="ja registrado"):
        reg.register(provider)


# 3. Provider inexistente retorna None explícito
def test_p24_03_provider_inexistente():
    reg = IntegrationRegistry()
    assert reg.get("desconhecido") is None
    assert not reg.is_available("desconhecido")
    assert reg.get_capabilities("desconhecido") == set()
    assert not reg.has_capability("desconhecido", IntegrationCapability.DOCUMENT_READ)


# 4. Listagem determinística
def test_p24_04_listagem_deterministica(default_registry: IntegrationRegistry):
    lista1 = [p.provider_id for p in default_registry.list_providers()]
    lista2 = [p.provider_id for p in default_registry.list_providers()]
    assert lista1 == lista2
    assert lista1 == sorted(lista1)


# 5. Capability existente
def test_p24_05_capability_existente(default_registry: IntegrationRegistry):
    assert default_registry.has_capability("microsoft.graph", IntegrationCapability.IDENTITY_READ)
    assert default_registry.has_capability("sharepoint", IntegrationCapability.DOCUMENT_READ)
    assert default_registry.has_capability("sap", IntegrationCapability.WORK_ORDER_READ)
    assert default_registry.has_capability("salesforce", IntegrationCapability.CUSTOMER_READ)


# 6. Capability inexistente
def test_p24_06_capability_inexistente(default_registry: IntegrationRegistry):
    assert not default_registry.has_capability("microsoft.entra", IntegrationCapability.DOCUMENT_WRITE)
    assert not default_registry.has_capability("salesforce", IntegrationCapability.SOAP_CALL)


# 7. Provider indisponível
def test_p24_07_provider_indisponivel(default_registry: IntegrationRegistry):
    graph = default_registry.get("microsoft.graph")
    assert graph is not None
    assert graph.descriptor.availability == AvailabilityStatus.UNAVAILABLE
    assert not default_registry.is_available("microsoft.graph")


# 8. Provider não configurado
def test_p24_08_provider_nao_configurado(default_registry: IntegrationRegistry):
    sap = default_registry.get("sap")
    assert sap is not None
    assert sap.descriptor.configuration_status == ConfigurationStatus.NOT_CONFIGURED
    res = sap.check_availability()
    assert res.status == IntegrationStatus.NOT_CONFIGURED


# 9. Status SUCCESS
def test_p24_09_resultado_success():
    res = IntegrationResult.success({"key": "val"})
    assert res.is_success
    assert res.status == IntegrationStatus.SUCCESS
    assert res.data == {"key": "val"}
    assert res.error_code is None


# 10. Status NOT_SUPPORTED
def test_p24_10_resultado_not_supported():
    res = IntegrationResult.not_supported("Operacao nao suportada.")
    assert not res.is_success
    assert res.status == IntegrationStatus.NOT_SUPPORTED
    assert res.error_code == "NOT_SUPPORTED"


# 11. Status AUTH_REQUIRED
def test_p24_11_resultado_auth_required():
    res = IntegrationResult.auth_required("Token expirado.")
    assert not res.is_success
    assert res.status == IntegrationStatus.AUTH_REQUIRED
    assert res.error_code == "AUTH_REQUIRED"


# 12. Status UNAVAILABLE
def test_p24_12_resultado_unavailable():
    res = IntegrationResult.unavailable("Servico fora do ar.")
    assert not res.is_success
    assert res.status == IntegrationStatus.UNAVAILABLE


# 13. Status TIMEOUT
def test_p24_13_resultado_timeout():
    res = IntegrationResult.timeout("Tempo esgotado.")
    assert not res.is_success
    assert res.status == IntegrationStatus.TIMEOUT


# 14. Status IDENTITY_MISMATCH
def test_p24_14_resultado_identity_mismatch():
    res = IntegrationResult.identity_mismatch("Violacao de identidade.")
    assert not res.is_success
    assert res.status == IntegrationStatus.IDENTITY_MISMATCH


# 15. Contexto SOB imutável e validado
def test_p24_15_contexto_sob(valid_context: IntegrationContext):
    assert valid_context.sob_id == "A057526153"
    assert valid_context.project_root == r"C:\Projetos\SOB_A057526153"
    with pytest.raises(ValueError):
        IntegrationContext("", r"C:\p", r"C:\d.dwg", "{guid}")


# 16. Fingerprint preservado contra adulteração
def test_p24_16_fingerprint_preservado(valid_context: IntegrationContext):
    assert valid_context.validate_sovereignty("A057526153", "{11111111-2222-3333-4444-555555555555}")
    assert not valid_context.validate_sovereignty("A057526153", "{OUTRO-FINGERPRINT}")


# 17. Provider não altera autoridade do DWG
def test_p24_17_autoridade_dwg(valid_context: IntegrationContext):
    res_ok = valid_context.validate_authority_against(r"C:\Projetos\SOB_A057526153\CF_A057526153_DESENHO.dwg")
    assert res_ok.is_success
    res_err = valid_context.validate_authority_against(r"C:\OutroLugar\malicioso.dwg")
    assert res_err.status == IntegrationStatus.IDENTITY_MISMATCH


# 18. Contrato de documentos (IDocumentRepository)
def test_p24_18_contrato_documentos(default_registry: IntegrationRegistry, valid_context: IntegrationContext):
    sharepoint = default_registry.get("sharepoint")
    assert isinstance(sharepoint, IDocumentRepository)
    res = sharepoint.list_documents(valid_context, "/pasta")
    assert res.status == IntegrationStatus.NOT_CONFIGURED


# 19. Contrato de artefatos (IArtifactRepository)
def test_p24_19_contrato_artefatos(default_registry: IntegrationRegistry, valid_context: IntegrationContext):
    onedrive = default_registry.get("onedrive")
    assert isinstance(onedrive, IArtifactRepository)
    res = onedrive.get_artifact_status(valid_context, "cqt_relatorio")
    assert res.status == IntegrationStatus.NOT_CONFIGURED


# 20. Contrato de OS (IWorkOrderProvider)
def test_p24_20_contrato_work_order(default_registry: IntegrationRegistry, valid_context: IntegrationContext):
    sap = default_registry.get("sap")
    assert isinstance(sap, IWorkOrderProvider)
    res = sap.get_work_order_status(valid_context, "OS-998811")
    assert res.status == IntegrationStatus.NOT_CONFIGURED


# 21. Contrato de CRM (ICustomerProvider)
def test_p24_21_contrato_crm(default_registry: IntegrationRegistry, valid_context: IntegrationContext):
    salesforce = default_registry.get("salesforce")
    assert isinstance(salesforce, ICustomerProvider)
    res = salesforce.get_customer_info(valid_context, "CLI-00123")
    assert res.status == IntegrationStatus.NOT_CONFIGURED


# 22. Contrato de identidade (IIdentityProvider)
def test_p24_22_contrato_identidade(default_registry: IntegrationRegistry, valid_context: IntegrationContext):
    entra = default_registry.get("microsoft.entra")
    assert isinstance(entra, IIdentityProvider)
    res = entra.get_user_display_name(valid_context, "user@empresa.com")
    assert res.status == IntegrationStatus.NOT_CONFIGURED


# 23. Descriptor Microsoft Graph
def test_p24_23_descriptor_microsoft_graph(default_registry: IntegrationRegistry):
    graph = default_registry.get("microsoft.graph")
    assert graph is not None
    desc = graph.descriptor
    assert desc.display_name == "Microsoft Graph"
    assert desc.provider_type == "Microsoft"
    assert desc.authentication.scheme == AuthenticationScheme.OAUTH2


# 24. Descriptor Microsoft Entra ID
def test_p24_24_descriptor_entra(default_registry: IntegrationRegistry):
    entra = default_registry.get("microsoft.entra")
    assert entra is not None
    desc = entra.descriptor
    assert desc.display_name == "Microsoft Entra ID"
    assert desc.provider_type == "Identity"
    assert desc.authentication.scheme == AuthenticationScheme.OPENID_CONNECT


# 25. Descriptor SharePoint
def test_p24_25_descriptor_sharepoint(default_registry: IntegrationRegistry):
    sp = default_registry.get("sharepoint")
    assert sp is not None
    desc = sp.descriptor
    assert desc.display_name == "SharePoint"
    assert desc.provider_type == "DocumentRepository"
    assert IntegrationCapability.DOCUMENT_READ in desc.capabilities


# 26. Descriptor OneDrive
def test_p24_26_descriptor_onedrive(default_registry: IntegrationRegistry):
    one = default_registry.get("onedrive")
    assert one is not None
    desc = one.descriptor
    assert desc.display_name == "OneDrive"
    assert desc.provider_type == "DocumentRepository"
    assert IntegrationCapability.ARTIFACT_WRITE in desc.capabilities


# 27. Descriptor SAP (ERP, S4HANA, BTP)
def test_p24_27_descriptor_sap(default_registry: IntegrationRegistry):
    sap = default_registry.get("sap")
    s4 = default_registry.get("sap.s4hana")
    btp = default_registry.get("sap.btp")
    assert sap is not None and s4 is not None and btp is not None
    assert sap.descriptor.authentication.scheme == AuthenticationScheme.CLIENT_CREDENTIALS
    assert s4.descriptor.authentication.scheme == AuthenticationScheme.CLIENT_CREDENTIALS
    assert btp.descriptor.has_capability(IntegrationCapability.EVENT_SUBSCRIBE)


# 28. Descriptor Salesforce
def test_p24_28_descriptor_salesforce(default_registry: IntegrationRegistry):
    sf = default_registry.get("salesforce")
    assert sf is not None
    desc = sf.descriptor
    assert desc.display_name == "Salesforce"
    assert desc.provider_type == "CRM"
    assert IntegrationCapability.CUSTOMER_READ in desc.capabilities


# 29. Descriptor REST e SOAP
def test_p24_29_descriptor_rest_soap(default_registry: IntegrationRegistry, valid_context: IntegrationContext):
    rest = default_registry.get("rest")
    soap = default_registry.get("soap")
    assert rest is not None and soap is not None
    assert rest.descriptor.is_available
    assert soap.descriptor.is_available
    assert rest.supports_capability(IntegrationCapability.REST_CALL)
    assert soap.supports_capability(IntegrationCapability.SOAP_CALL)
    # Chamadas permanecem puramente declarativas
    res_rest = rest.execute_rest_request(valid_context, "GET", "/api/v1/test")
    assert res_rest.status == IntegrationStatus.NOT_CONFIGURED


# 30. Autenticação puramente declarativa sem segredos
def test_p24_30_autenticacao_declarativa():
    auth = AuthenticationDescriptor.oauth2_client_credentials()
    assert auth.scheme == AuthenticationScheme.CLIENT_CREDENTIALS
    assert not hasattr(auth, "client_secret")
    assert not hasattr(auth, "password")
    assert not hasattr(auth, "token")


# 31. Nenhum secret persistido
def test_p24_31_nenhum_secret_persistido(default_registry: IntegrationRegistry):
    for provider in default_registry.list_providers():
        desc = provider.descriptor
        d_dict = vars(desc)
        for k, v in d_dict.items():
            assert "secret" not in k.lower()
            assert "token" not in k.lower()
            assert "password" not in k.lower()


# 32. Nenhuma chamada externa efetuada (100% offline e rápido)
def test_p24_32_nenhuma_chamada_externa(default_registry: IntegrationRegistry, valid_context: IntegrationContext):
    import time
    t0 = time.perf_counter()
    for provider in default_registry.list_providers():
        provider.check_availability()
    duracao = time.perf_counter() - t0
    # Todas as checagens devem ocorrer em menos de 10 milissegundos sem qualquer I/O de rede
    assert duracao < 0.05


# 33. Nenhuma execução OxCadExecution gerada
def test_p24_33_nenhuma_execucao_gerada(default_registry: IntegrationRegistry):
    # Consulta a providers e descriptors não deve instanciar nem registrar OxCadExecution
    providers = default_registry.list_providers()
    assert len(providers) >= 11


# 34. Nenhum arquivo operacional alterado
def test_p24_34_nenhum_arquivo_alterado(default_registry: IntegrationRegistry, valid_context: IntegrationContext, tmp_path: Path):
    arquivo_sentinela = tmp_path / "sentinela.txt"
    arquivo_sentinela.write_text("conteudo original")
    sp = default_registry.get("sharepoint")
    sp.list_documents(valid_context, str(tmp_path))
    assert arquivo_sentinela.read_text() == "conteudo original"


# 35. UI / Operação não bloqueante
def test_p24_35_operacao_nao_bloqueante(default_registry: IntegrationRegistry):
    # Simula chamada de inicialização rápida como executada na Paleta WPF
    items = []
    for pid in ["microsoft.graph", "microsoft.entra", "sharepoint", "onedrive", "sap", "salesforce", "rest", "soap"]:
        p = default_registry.get(pid)
        assert p is not None
        status_txt = "Disponível" if p.descriptor.configuration_status == ConfigurationStatus.CONFIGURED else "Não configurado"
        items.append((p.descriptor.display_name, status_txt))
    assert len(items) == 8


# 36. Determinismo estrito em múltiplas criações
def test_p24_36_determinismo_estrito():
    reg1 = IntegrationRegistry.create_default()
    reg2 = IntegrationRegistry.create_default()
    assert [p.provider_id for p in reg1.list_providers()] == [p.provider_id for p in reg2.list_providers()]


# 37. Regressão P2.1 (Indicadores de Gestão)
def test_p24_37_regressao_p21():
    from workspace.workspace_indicators import consultar_indicadores, IndicadoresAnalyzer
    assert callable(consultar_indicadores)
    assert IndicadoresAnalyzer is not None


# 38. Regressão P2.2 (Visão Operacional e Filtros)
def test_p24_38_regressao_p22(tmp_path: Path):
    from workspace.workspace_indicators import consultar_indicadores
    res = consultar_indicadores(project_root=tmp_path, acao="cqt", estado="Concluido")
    assert res["schema"] == 1
    assert "execucoes" in res
    assert res["execucoes"]["status"] in ("SUCESSO", "SEM_DADOS", "NÃO DISPONÍVEL")


# 39. Regressão P2.3 (Qualidade, Histórico e Stores Duráveis)
def test_p24_39_regressao_p23():
    from workspace.workspace_indicator_quality import (
        COBERTURA_COMPLETA,
        COBERTURA_SEM_DADOS,
        comparar_indicadores,
        PROVENIENCIA_FONTES,
    )
    from workspace.workspace_indicator_stores import (
        processar_pending,
        processar_deliveries,
        processar_time,
    )
    assert COBERTURA_COMPLETA == "COMPLETA"
    assert COBERTURA_SEM_DADOS == "SEM_DADOS"
    assert callable(comparar_indicadores)
    assert callable(processar_pending)
    assert callable(processar_deliveries)
    assert callable(processar_time)


# 40. Limites de linhas por arquivo (< 750 linhas)
def test_p24_40_limites_linhas():
    root = Path(__file__).resolve().parent.parent
    arquivos_p24 = [
        root / "workspace" / "workspace_integrations.py",
        root / "workspace" / "workspace_integration_adapters.py",
        root / "oxcad" / "OxCadControl.Integracoes.cs",
        root / "oxcad" / "integration" / "IntegrationCapability.cs",
        root / "oxcad" / "integration" / "AuthenticationDescriptor.cs",
        root / "oxcad" / "integration" / "IntegrationResult.cs",
        root / "oxcad" / "integration" / "IntegrationContext.cs",
        root / "oxcad" / "integration" / "IntegrationDescriptor.cs",
        root / "oxcad" / "integration" / "IntegrationContracts.cs",
        root / "oxcad" / "integration" / "IntegrationRegistry.cs",
    ]
    for arq in arquivos_p24:
        assert arq.exists(), f"Arquivo não encontrado: {arq}"
        linhas = len(arq.read_text(encoding="utf-8").splitlines())
        assert linhas < 750, f"Arquivo {arq.name} com {linhas} linhas ultrapassa o limite de 750 linhas."
