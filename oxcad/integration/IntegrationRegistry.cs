using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;

namespace OxCad.Integration
{
    /// <summary>
    /// Registro determinístico e thread-safe de provedores de integração.
    /// Mantém o catálogo de integrações sem efeitos colaterais, sem rede e sem persistir secrets.
    /// </summary>
    public sealed class IntegrationRegistry
    {
        private readonly ConcurrentDictionary<string, IIntegrationProvider> _providers =
            new ConcurrentDictionary<string, IIntegrationProvider>(StringComparer.OrdinalIgnoreCase);

        /// <summary>
        /// Registra um provedor no catálogo.
        /// Lança InvalidOperationException se o providerId já estiver registrado.
        /// </summary>
        public void Register(IIntegrationProvider provider)
        {
            if (provider == null)
                throw new ArgumentNullException(nameof(provider));

            string id = provider.ProviderId.Trim();
            if (!_providers.TryAdd(id, provider))
            {
                throw new InvalidOperationException($"Provedor de integração com id '{id}' já está registrado.");
            }
        }

        /// <summary>
        /// Remove um provedor do catálogo.
        /// </summary>
        public bool Unregister(string providerId)
        {
            if (string.IsNullOrWhiteSpace(providerId))
                return false;

            return _providers.TryRemove(providerId.Trim(), out _);
        }

        /// <summary>
        /// Obtém um provedor pelo identificador.
        /// </summary>
        public IIntegrationProvider? Get(string providerId)
        {
            if (string.IsNullOrWhiteSpace(providerId))
                return null;

            _providers.TryGetValue(providerId.Trim(), out var provider);
            return provider;
        }

        /// <summary>
        /// Obtém um provedor tipado pelo identificador.
        /// </summary>
        public TProvider? Get<TProvider>(string providerId) where TProvider : class, IIntegrationProvider
        {
            var provider = Get(providerId);
            return provider as TProvider;
        }

        /// <summary>
        /// Lista todos os provedores em ordem alfabética determinística.
        /// </summary>
        public IReadOnlyList<IIntegrationProvider> List()
        {
            return _providers.Values
                .OrderBy(p => p.ProviderId, StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        /// <summary>
        /// Retorna as capacidades de um provedor.
        /// </summary>
        public IReadOnlyCollection<IntegrationCapability> GetCapabilities(string providerId)
        {
            var provider = Get(providerId);
            return provider != null ? provider.Descriptor.Capabilities : Array.Empty<IntegrationCapability>();
        }

        /// <summary>
        /// Verifica se um provedor está disponível e configurado.
        /// </summary>
        public bool IsAvailable(string providerId)
        {
            var provider = Get(providerId);
            return provider != null && provider.Descriptor.IsAvailable;
        }

        /// <summary>
        /// Verifica se um provedor suporta uma capacidade específica.
        /// </summary>
        public bool HasCapability(string providerId, IntegrationCapability capability)
        {
            var provider = Get(providerId);
            return provider != null && provider.SupportsCapability(capability);
        }

        /// <summary>
        /// Cria o catálogo padrão de provedores arquiteturais do OXCAD (P2.4).
        /// Todos os provedores externos iniciam como NotConfigured e sem chamadas ativas de rede.
        /// </summary>
        public static IntegrationRegistry CreateDefault()
        {
            var registry = new IntegrationRegistry();

            // 1. Repositório Local de Artefatos/Documentos (Disponível)
            registry.Register(new LocalFileRepositoryAdapter());

            // 2. Microsoft Graph (Não Configurado)
            registry.Register(new MicrosoftGraphAdapter());

            // 3. Microsoft Entra ID (Não Configurado)
            registry.Register(new MicrosoftEntraAdapter());

            // 4. SharePoint (Não Configurado)
            registry.Register(new SharePointAdapter());

            // 5. OneDrive (Não Configurado)
            registry.Register(new OneDriveAdapter());

            // 6. SAP ERP (Não Configurado)
            registry.Register(new SapAdapter());

            // 7. SAP S/4HANA (Não Configurado)
            registry.Register(new SapS4HanaAdapter());

            // 8. SAP BTP (Não Configurado)
            registry.Register(new SapBtpAdapter());

            // 9. Salesforce CRM (Não Configurado)
            registry.Register(new SalesforceAdapter());

            // 10. REST Corporativo Gateway (Disponível arquiteturalmente)
            registry.Register(new RestGatewayAdapter());

            // 11. SOAP Corporativo Gateway (Disponível arquiteturalmente)
            registry.Register(new SoapGatewayAdapter());

            return registry;
        }
    }

    #region Adaptadores Arquiteturais Padrão (Sem chamadas externas)

    internal sealed class LocalFileRepositoryAdapter : IArtifactRepository, IDocumentRepository
    {
        public string ProviderId => "local";
        public IntegrationDescriptor Descriptor { get; }

        public LocalFileRepositoryAdapter()
        {
            Descriptor = new IntegrationDescriptor(
                providerId: "local",
                displayName: "Repositório Local",
                providerType: "Storage",
                version: "1.0.0",
                capabilities: new[]
                {
                    IntegrationCapability.DocumentRead,
                    IntegrationCapability.DocumentWrite,
                    IntegrationCapability.ArtifactRead,
                    IntegrationCapability.ArtifactWrite
                },
                authentication: AuthenticationDescriptor.None(),
                configurationStatus: ConfigurationStatus.Configured,
                availability: AvailabilityStatus.Available);
        }

        public bool SupportsCapability(IntegrationCapability capability) => Descriptor.HasCapability(capability);

        public Task<IntegrationResult> CheckAvailabilityAsync(CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult.Success());

        public Task<IntegrationResult<string>> GetArtifactStatusAsync(IntegrationContext context, string artifactName, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.Success($"Artefato local '{artifactName}' disponível no workspace."));

        public Task<IntegrationResult<IReadOnlyList<string>>> ListVersionsAsync(IntegrationContext context, string artifactName, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<IReadOnlyList<string>>.Success(new List<string> { "1.0.0" }));

        public Task<IntegrationResult<IReadOnlyList<string>>> ListDocumentsAsync(IntegrationContext context, string folderPath, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<IReadOnlyList<string>>.Success(new List<string>()));

        public Task<IntegrationResult<string>> GetDocumentMetadataAsync(IntegrationContext context, string documentId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.Success($"Metadata local do documento '{documentId}'"));

        public Task<IntegrationResult<byte[]>> DownloadDocumentAsync(IntegrationContext context, string documentId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<byte[]>.Success(Array.Empty<byte>()));

        public Task<IntegrationResult<string>> UploadDocumentAsync(IntegrationContext context, string destinationFolder, string fileName, byte[] content, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.Success(fileName));
    }

    internal sealed class MicrosoftGraphAdapter : UnconfiguredProviderBase, IIdentityProvider, IDocumentRepository
    {
        public MicrosoftGraphAdapter() : base(new IntegrationDescriptor(
            providerId: "microsoft.graph",
            displayName: "Microsoft Graph",
            providerType: "Microsoft",
            version: "1.0.0",
            capabilities: new[]
            {
                IntegrationCapability.IdentityRead,
                IntegrationCapability.UserRead,
                IntegrationCapability.DocumentRead,
                IntegrationCapability.ArtifactRead
            },
            authentication: AuthenticationDescriptor.OAuth2UserDelegated(),
            configurationStatus: ConfigurationStatus.NotConfigured,
            availability: AvailabilityStatus.Unavailable))
        { }

        public Task<IntegrationResult<string>> GetUserDisplayNameAsync(IntegrationContext context, string userId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("Microsoft Graph não configurado."));

        public Task<IntegrationResult<IReadOnlyList<string>>> GetUserGroupsAsync(IntegrationContext context, string userId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<IReadOnlyList<string>>.NotConfigured("Microsoft Graph não configurado."));

        public Task<IntegrationResult<IReadOnlyList<string>>> ListDocumentsAsync(IntegrationContext context, string folderPath, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<IReadOnlyList<string>>.NotConfigured("Microsoft Graph não configurado."));

        public Task<IntegrationResult<string>> GetDocumentMetadataAsync(IntegrationContext context, string documentId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("Microsoft Graph não configurado."));

        public Task<IntegrationResult<byte[]>> DownloadDocumentAsync(IntegrationContext context, string documentId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<byte[]>.NotConfigured("Microsoft Graph não configurado."));

        public Task<IntegrationResult<string>> UploadDocumentAsync(IntegrationContext context, string destinationFolder, string fileName, byte[] content, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("Microsoft Graph não configurado."));
    }

    internal sealed class MicrosoftEntraAdapter : UnconfiguredProviderBase, IIdentityProvider
    {
        public MicrosoftEntraAdapter() : base(new IntegrationDescriptor(
            providerId: "microsoft.entra",
            displayName: "Microsoft Entra ID",
            providerType: "Identity",
            version: "1.0.0",
            capabilities: new[]
            {
                IntegrationCapability.IdentityRead,
                IntegrationCapability.UserRead
            },
            authentication: AuthenticationDescriptor.OpenIdConnect(),
            configurationStatus: ConfigurationStatus.NotConfigured,
            availability: AvailabilityStatus.Unavailable))
        { }

        public Task<IntegrationResult<string>> GetUserDisplayNameAsync(IntegrationContext context, string userId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("Microsoft Entra ID não configurado."));

        public Task<IntegrationResult<IReadOnlyList<string>>> GetUserGroupsAsync(IntegrationContext context, string userId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<IReadOnlyList<string>>.NotConfigured("Microsoft Entra ID não configurado."));
    }

    internal sealed class SharePointAdapter : UnconfiguredProviderBase, IDocumentRepository, IArtifactRepository
    {
        public SharePointAdapter() : base(new IntegrationDescriptor(
            providerId: "sharepoint",
            displayName: "SharePoint",
            providerType: "DocumentRepository",
            version: "1.0.0",
            capabilities: new[]
            {
                IntegrationCapability.DocumentRead,
                IntegrationCapability.DocumentWrite,
                IntegrationCapability.ArtifactRead,
                IntegrationCapability.ArtifactWrite
            },
            authentication: AuthenticationDescriptor.OAuth2UserDelegated(),
            configurationStatus: ConfigurationStatus.NotConfigured,
            availability: AvailabilityStatus.Unavailable))
        { }

        public Task<IntegrationResult<IReadOnlyList<string>>> ListDocumentsAsync(IntegrationContext context, string folderPath, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<IReadOnlyList<string>>.NotConfigured("SharePoint não configurado."));

        public Task<IntegrationResult<string>> GetDocumentMetadataAsync(IntegrationContext context, string documentId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("SharePoint não configurado."));

        public Task<IntegrationResult<byte[]>> DownloadDocumentAsync(IntegrationContext context, string documentId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<byte[]>.NotConfigured("SharePoint não configurado."));

        public Task<IntegrationResult<string>> UploadDocumentAsync(IntegrationContext context, string destinationFolder, string fileName, byte[] content, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("SharePoint não configurado."));

        public Task<IntegrationResult<string>> GetArtifactStatusAsync(IntegrationContext context, string artifactName, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("SharePoint não configurado."));

        public Task<IntegrationResult<IReadOnlyList<string>>> ListVersionsAsync(IntegrationContext context, string artifactName, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<IReadOnlyList<string>>.NotConfigured("SharePoint não configurado."));
    }

    internal sealed class OneDriveAdapter : UnconfiguredProviderBase, IDocumentRepository, IArtifactRepository
    {
        public OneDriveAdapter() : base(new IntegrationDescriptor(
            providerId: "onedrive",
            displayName: "OneDrive",
            providerType: "DocumentRepository",
            version: "1.0.0",
            capabilities: new[]
            {
                IntegrationCapability.DocumentRead,
                IntegrationCapability.DocumentWrite,
                IntegrationCapability.ArtifactRead,
                IntegrationCapability.ArtifactWrite
            },
            authentication: AuthenticationDescriptor.OAuth2UserDelegated(),
            configurationStatus: ConfigurationStatus.NotConfigured,
            availability: AvailabilityStatus.Unavailable))
        { }

        public Task<IntegrationResult<IReadOnlyList<string>>> ListDocumentsAsync(IntegrationContext context, string folderPath, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<IReadOnlyList<string>>.NotConfigured("OneDrive não configurado."));

        public Task<IntegrationResult<string>> GetDocumentMetadataAsync(IntegrationContext context, string documentId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("OneDrive não configurado."));

        public Task<IntegrationResult<byte[]>> DownloadDocumentAsync(IntegrationContext context, string documentId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<byte[]>.NotConfigured("OneDrive não configurado."));

        public Task<IntegrationResult<string>> UploadDocumentAsync(IntegrationContext context, string destinationFolder, string fileName, byte[] content, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("OneDrive não configurado."));

        public Task<IntegrationResult<string>> GetArtifactStatusAsync(IntegrationContext context, string artifactName, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("OneDrive não configurado."));

        public Task<IntegrationResult<IReadOnlyList<string>>> ListVersionsAsync(IntegrationContext context, string artifactName, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<IReadOnlyList<string>>.NotConfigured("OneDrive não configurado."));
    }

    internal sealed class SapAdapter : UnconfiguredProviderBase, IBusinessSystemProvider, IWorkOrderProvider
    {
        public SapAdapter() : base(new IntegrationDescriptor(
            providerId: "sap",
            displayName: "SAP",
            providerType: "ERP",
            version: "1.0.0",
            capabilities: new[]
            {
                IntegrationCapability.WorkOrderRead,
                IntegrationCapability.BusinessDataRead
            },
            authentication: AuthenticationDescriptor.OAuth2ClientCredentials(),
            configurationStatus: ConfigurationStatus.NotConfigured,
            availability: AvailabilityStatus.Unavailable))
        { }

        public Task<IntegrationResult<string>> QueryBusinessEntityAsync(IntegrationContext context, string entityType, string entityKey, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("SAP ERP não configurado."));

        public Task<IntegrationResult<string>> GetWorkOrderStatusAsync(IntegrationContext context, string orderId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("SAP ERP não configurado."));

        public Task<IntegrationResult<IReadOnlyList<string>>> SearchWorkOrdersAsync(IntegrationContext context, string query, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<IReadOnlyList<string>>.NotConfigured("SAP ERP não configurado."));
    }

    internal sealed class SapS4HanaAdapter : UnconfiguredProviderBase, IBusinessSystemProvider, IWorkOrderProvider
    {
        public SapS4HanaAdapter() : base(new IntegrationDescriptor(
            providerId: "sap.s4hana",
            displayName: "SAP S/4HANA",
            providerType: "ERP",
            version: "1.0.0",
            capabilities: new[]
            {
                IntegrationCapability.WorkOrderRead,
                IntegrationCapability.WorkOrderWrite,
                IntegrationCapability.BusinessDataRead,
                IntegrationCapability.BusinessDataWrite
            },
            authentication: AuthenticationDescriptor.OAuth2ClientCredentials(),
            configurationStatus: ConfigurationStatus.NotConfigured,
            availability: AvailabilityStatus.Unavailable))
        { }

        public Task<IntegrationResult<string>> QueryBusinessEntityAsync(IntegrationContext context, string entityType, string entityKey, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("SAP S/4HANA não configurado."));

        public Task<IntegrationResult<string>> GetWorkOrderStatusAsync(IntegrationContext context, string orderId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("SAP S/4HANA não configurado."));

        public Task<IntegrationResult<IReadOnlyList<string>>> SearchWorkOrdersAsync(IntegrationContext context, string query, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<IReadOnlyList<string>>.NotConfigured("SAP S/4HANA não configurado."));
    }

    internal sealed class SapBtpAdapter : UnconfiguredProviderBase, IBusinessSystemProvider, IEventProvider
    {
        public SapBtpAdapter() : base(new IntegrationDescriptor(
            providerId: "sap.btp",
            displayName: "SAP BTP",
            providerType: "Platform",
            version: "1.0.0",
            capabilities: new[]
            {
                IntegrationCapability.BusinessDataRead,
                IntegrationCapability.EventSubscribe
            },
            authentication: AuthenticationDescriptor.OAuth2ClientCredentials(),
            configurationStatus: ConfigurationStatus.NotConfigured,
            availability: AvailabilityStatus.Unavailable))
        { }

        public Task<IntegrationResult<string>> QueryBusinessEntityAsync(IntegrationContext context, string entityType, string entityKey, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("SAP BTP não configurado."));

        public Task<IntegrationResult> PublishEventAsync(IntegrationContext context, string eventType, string payloadReference, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult.NotConfigured("SAP BTP não configurado."));
    }

    internal sealed class SalesforceAdapter : UnconfiguredProviderBase, ICustomerProvider
    {
        public SalesforceAdapter() : base(new IntegrationDescriptor(
            providerId: "salesforce",
            displayName: "Salesforce",
            providerType: "CRM",
            version: "1.0.0",
            capabilities: new[]
            {
                IntegrationCapability.CustomerRead,
                IntegrationCapability.CustomerWrite
            },
            authentication: AuthenticationDescriptor.OAuth2UserDelegated(),
            configurationStatus: ConfigurationStatus.NotConfigured,
            availability: AvailabilityStatus.Unavailable))
        { }

        public Task<IntegrationResult<string>> GetCustomerInfoAsync(IntegrationContext context, string customerId, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("Salesforce CRM não configurado."));

        public Task<IntegrationResult<IReadOnlyList<string>>> SearchCustomersAsync(IntegrationContext context, string term, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<IReadOnlyList<string>>.NotConfigured("Salesforce CRM não configurado."));
    }

    internal sealed class RestGatewayAdapter : IRestProvider
    {
        public string ProviderId => "rest";
        public IntegrationDescriptor Descriptor { get; }

        public RestGatewayAdapter()
        {
            Descriptor = new IntegrationDescriptor(
                providerId: "rest",
                displayName: "REST Gateway",
                providerType: "Gateway",
                version: "1.0.0",
                capabilities: new[] { IntegrationCapability.RestCall },
                authentication: AuthenticationDescriptor.ApiKey(),
                configurationStatus: ConfigurationStatus.Configured,
                availability: AvailabilityStatus.Available);
        }

        public bool SupportsCapability(IntegrationCapability capability) => Descriptor.HasCapability(capability);

        public Task<IntegrationResult> CheckAvailabilityAsync(CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult.Success());

        public Task<IntegrationResult<string>> ExecuteRestRequestAsync(IntegrationContext context, string method, string relativeUri, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("Endpoint REST não conectado. Operação puramente declarativa."));
    }

    internal sealed class SoapGatewayAdapter : ISoapProvider
    {
        public string ProviderId => "soap";
        public IntegrationDescriptor Descriptor { get; }

        public SoapGatewayAdapter()
        {
            Descriptor = new IntegrationDescriptor(
                providerId: "soap",
                displayName: "SOAP Gateway",
                providerType: "Gateway",
                version: "1.0.0",
                capabilities: new[] { IntegrationCapability.SoapCall },
                authentication: AuthenticationDescriptor.BasicAuth(),
                configurationStatus: ConfigurationStatus.Configured,
                availability: AvailabilityStatus.Available);
        }

        public bool SupportsCapability(IntegrationCapability capability) => Descriptor.HasCapability(capability);

        public Task<IntegrationResult> CheckAvailabilityAsync(CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult.Success());

        public Task<IntegrationResult<string>> ExecuteSoapActionAsync(IntegrationContext context, string action, string xmlPayload, CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult<string>.NotConfigured("Serviço SOAP não conectado. Operação puramente declarativa."));
    }

    #endregion
}
