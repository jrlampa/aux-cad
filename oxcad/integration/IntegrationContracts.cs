using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace OxCad.Integration
{
    /// <summary>
    /// Contrato base unificado para todos os provedores da plataforma de integração.
    /// </summary>
    public interface IIntegrationProvider
    {
        string ProviderId { get; }
        IntegrationDescriptor Descriptor { get; }
        bool SupportsCapability(IntegrationCapability capability);
        Task<IntegrationResult> CheckAvailabilityAsync(CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Contrato de domínio para provedores de identidade corporativa (ex.: Entra ID, OAuth/OIDC).
    /// </summary>
    public interface IIdentityProvider : IIntegrationProvider
    {
        Task<IntegrationResult<string>> GetUserDisplayNameAsync(IntegrationContext context, string userId, CancellationToken cancellationToken = default);
        Task<IntegrationResult<IReadOnlyList<string>>> GetUserGroupsAsync(IntegrationContext context, string userId, CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Contrato de domínio para repositórios de documentos (ex.: SharePoint, OneDrive, GED).
    /// </summary>
    public interface IDocumentRepository : IIntegrationProvider
    {
        Task<IntegrationResult<IReadOnlyList<string>>> ListDocumentsAsync(IntegrationContext context, string folderPath, CancellationToken cancellationToken = default);
        Task<IntegrationResult<string>> GetDocumentMetadataAsync(IntegrationContext context, string documentId, CancellationToken cancellationToken = default);
        Task<IntegrationResult<byte[]>> DownloadDocumentAsync(IntegrationContext context, string documentId, CancellationToken cancellationToken = default);
        Task<IntegrationResult<string>> UploadDocumentAsync(IntegrationContext context, string destinationFolder, string fileName, byte[] content, CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Contrato de domínio para gestão e versionamento de artefatos de engenharia.
    /// </summary>
    public interface IArtifactRepository : IIntegrationProvider
    {
        Task<IntegrationResult<string>> GetArtifactStatusAsync(IntegrationContext context, string artifactName, CancellationToken cancellationToken = default);
        Task<IntegrationResult<IReadOnlyList<string>>> ListVersionsAsync(IntegrationContext context, string artifactName, CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Contrato de domínio para ordens de serviço e despachos de campo (ex.: SAP, ERP corporativo).
    /// </summary>
    public interface IWorkOrderProvider : IIntegrationProvider
    {
        Task<IntegrationResult<string>> GetWorkOrderStatusAsync(IntegrationContext context, string orderId, CancellationToken cancellationToken = default);
        Task<IntegrationResult<IReadOnlyList<string>>> SearchWorkOrdersAsync(IntegrationContext context, string query, CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Contrato de domínio para sistemas empresariais / ERP (ex.: SAP S/4HANA, SAP BTP).
    /// </summary>
    public interface IBusinessSystemProvider : IIntegrationProvider
    {
        Task<IntegrationResult<string>> QueryBusinessEntityAsync(IntegrationContext context, string entityType, string entityKey, CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Contrato de domínio para CRM e relacionamento com cliente (ex.: Salesforce).
    /// </summary>
    public interface ICustomerProvider : IIntegrationProvider
    {
        Task<IntegrationResult<string>> GetCustomerInfoAsync(IntegrationContext context, string customerId, CancellationToken cancellationToken = default);
        Task<IntegrationResult<IReadOnlyList<string>>> SearchCustomersAsync(IntegrationContext context, string term, CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Contrato de domínio para notificações operacionais.
    /// </summary>
    public interface INotificationProvider : IIntegrationProvider
    {
        Task<IntegrationResult> SendNotificationAsync(IntegrationContext context, string recipient, string title, string message, CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Contrato de domínio para publicação e consumo de eventos/webhooks.
    /// </summary>
    public interface IEventProvider : IIntegrationProvider
    {
        Task<IntegrationResult> PublishEventAsync(IntegrationContext context, string eventType, string payloadReference, CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Contrato genérico para requisições REST corporativas.
    /// </summary>
    public interface IRestProvider : IIntegrationProvider
    {
        Task<IntegrationResult<string>> ExecuteRestRequestAsync(IntegrationContext context, string method, string relativeUri, CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Contrato genérico para chamadas SOAP legadas corporativas.
    /// </summary>
    public interface ISoapProvider : IIntegrationProvider
    {
        Task<IntegrationResult<string>> ExecuteSoapActionAsync(IntegrationContext context, string action, string xmlPayload, CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Classe base leve para adaptadores declarativos ainda não configurados ou em preparação.
    /// Garante que nenhuma chamada externa seja feita e retorna imediatamente NotConfigured.
    /// </summary>
    public abstract class UnconfiguredProviderBase : IIntegrationProvider
    {
        public string ProviderId => Descriptor.ProviderId;
        public IntegrationDescriptor Descriptor { get; }

        protected UnconfiguredProviderBase(IntegrationDescriptor descriptor)
        {
            Descriptor = descriptor ?? throw new ArgumentNullException(nameof(descriptor));
        }

        public virtual bool SupportsCapability(IntegrationCapability capability) =>
            Descriptor.HasCapability(capability);

        public virtual Task<IntegrationResult> CheckAvailabilityAsync(CancellationToken cancellationToken = default) =>
            Task.FromResult(IntegrationResult.NotConfigured($"O provedor '{Descriptor.DisplayName}' não está configurado nesta instalação."));
    }
}
