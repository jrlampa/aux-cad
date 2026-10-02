using System;
using System.Collections.Generic;
using System.Linq;

namespace OxCad.Integration
{
    /// <summary>
    /// Estado de configuração do provedor de integração.
    /// </summary>
    public enum ConfigurationStatus
    {
        NotConfigured,
        Configured,
        Disabled
    }

    /// <summary>
    /// Estado de disponibilidade operacional do provedor.
    /// </summary>
    public enum AvailabilityStatus
    {
        Available,
        Unavailable,
        Degraded,
        Unknown
    }

    /// <summary>
    /// Descritor padronizado de um provedor de integração.
    /// Representa a definição arquitetural e declarativa do provedor sem estabelecer conexões ativas.
    /// </summary>
    public sealed class IntegrationDescriptor
    {
        private readonly HashSet<IntegrationCapability> _capabilities;

        public string ProviderId { get; }
        public string DisplayName { get; }
        public string ProviderType { get; }
        public string Version { get; }
        public IReadOnlyCollection<IntegrationCapability> Capabilities => _capabilities;
        public AuthenticationDescriptor Authentication { get; }
        public ConfigurationStatus ConfigurationStatus { get; }
        public AvailabilityStatus Availability { get; }

        public bool IsAvailable => Availability == AvailabilityStatus.Available &&
                                   ConfigurationStatus == ConfigurationStatus.Configured;

        public IntegrationDescriptor(
            string providerId,
            string displayName,
            string providerType,
            string version,
            IEnumerable<IntegrationCapability> capabilities,
            AuthenticationDescriptor? authentication = null,
            ConfigurationStatus configurationStatus = ConfigurationStatus.NotConfigured,
            AvailabilityStatus availability = AvailabilityStatus.Unknown)
        {
            if (string.IsNullOrWhiteSpace(providerId))
                throw new ArgumentException("ProviderId não pode ser nulo ou vazio.", nameof(providerId));
            if (string.IsNullOrWhiteSpace(displayName))
                throw new ArgumentException("DisplayName não pode ser nulo ou vazio.", nameof(displayName));

            ProviderId = providerId.Trim();
            DisplayName = displayName.Trim();
            ProviderType = string.IsNullOrWhiteSpace(providerType) ? "Generic" : providerType.Trim();
            Version = string.IsNullOrWhiteSpace(version) ? "1.0.0" : version.Trim();
            _capabilities = new HashSet<IntegrationCapability>(capabilities ?? Enumerable.Empty<IntegrationCapability>());
            Authentication = authentication ?? AuthenticationDescriptor.None();
            ConfigurationStatus = configurationStatus;
            Availability = availability;
        }

        public bool HasCapability(IntegrationCapability capability) =>
            _capabilities.Contains(capability);
    }
}
