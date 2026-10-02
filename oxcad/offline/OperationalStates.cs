using System;
using System.Collections.Generic;

namespace OxCad.Offline
{
    /// <summary>
    /// Estado do núcleo local operacional do OXCAD/AutoCAD.
    /// </summary>
    public enum CoreStatus
    {
        Available,
        Unavailable
    }

    /// <summary>
    /// Modo de conectividade de rede externa.
    /// </summary>
    public enum ConnectivityMode
    {
        Online,
        Offline,
        Unknown
    }

    /// <summary>
    /// Disponibilidade agregada dos provedores de integração externos.
    /// </summary>
    public enum IntegrationAvailability
    {
        Available,
        Partial,
        Unavailable,
        NotConfigured
    }

    /// <summary>
    /// Capacidade operacional efetiva do sistema ou operação.
    /// </summary>
    public enum OperationalMode
    {
        Normal,
        Degraded,
        Offline,
        Blocked
    }

    /// <summary>
    /// Contexto com as 4 dimensões explícitas de estado operacional.
    /// Não unifica os status em um único campo.
    /// </summary>
    public sealed class OperationalStateContext
    {
        public CoreStatus CoreStatus { get; }
        public ConnectivityMode ConnectivityMode { get; }
        public IntegrationAvailability IntegrationAvailability { get; }
        public OperationalMode OperationalMode { get; }
        public string UiMessage { get; }

        public OperationalStateContext(
            CoreStatus coreStatus,
            ConnectivityMode connectivityMode,
            IntegrationAvailability integrationAvailability,
            OperationalMode operationalMode,
            string? uiMessage = null)
        {
            CoreStatus = coreStatus;
            ConnectivityMode = connectivityMode;
            IntegrationAvailability = integrationAvailability;
            OperationalMode = operationalMode;
            UiMessage = uiMessage ?? GetDefaultMessage(operationalMode);
        }

        public static OperationalStateContext Create(
            CoreStatus coreStatus = CoreStatus.Available,
            ConnectivityMode connectivityMode = ConnectivityMode.Offline,
            IntegrationAvailability integrationAvailability = IntegrationAvailability.NotConfigured)
        {
            var derived = OperationalEvaluator.DeriveSystemMode(coreStatus, connectivityMode, integrationAvailability);
            return new OperationalStateContext(coreStatus, connectivityMode, integrationAvailability, derived);
        }

        public static string GetDefaultMessage(OperationalMode mode)
        {
            return mode switch
            {
                OperationalMode.Normal => "Operação online completa; integrações ativas e disponíveis.",
                OperationalMode.Degraded => "Operação online parcial; uma ou mais dependências externas estão indisponíveis.",
                OperationalMode.Offline => "Operação local disponível; sincronização externa pendente.",
                OperationalMode.Blocked => "Esta operação exige integração externa indisponível/não configurada ou núcleo inoperante.",
                _ => "Estado operacional não determinado."
            };
        }
    }

    /// <summary>
    /// Avaliador determinístico de regras de estado e resiliência operacional.
    /// </summary>
    public static class OperationalEvaluator
    {
        public static OperationalMode DeriveSystemMode(
            CoreStatus coreStatus,
            ConnectivityMode connectivityMode,
            IntegrationAvailability integrationAvailability)
        {
            if (coreStatus == CoreStatus.Unavailable)
                return OperationalMode.Blocked;

            if (connectivityMode == ConnectivityMode.Online)
            {
                if (integrationAvailability == IntegrationAvailability.Available)
                    return OperationalMode.Normal;

                return OperationalMode.Degraded;
            }

            // Ausência de conectividade externa com núcleo operacional disponível
            return OperationalMode.Offline;
        }

        public static OperationalMode EvaluateOperationMode(
            OperationalStateContext context,
            bool requiresConnectivity = false,
            IEnumerable<string>? requiredProviders = null,
            bool isLocalSupported = true,
            Func<string, bool>? providerChecker = null)
        {
            if (context.CoreStatus == CoreStatus.Unavailable)
                return OperationalMode.Blocked;

            if (requiresConnectivity && context.ConnectivityMode != ConnectivityMode.Online)
                return OperationalMode.Blocked;

            if (requiredProviders != null)
            {
                foreach (var pid in requiredProviders)
                {
                    if (providerChecker != null)
                    {
                        if (!providerChecker(pid))
                            return OperationalMode.Blocked;
                    }
                    else
                    {
                        if (context.IntegrationAvailability == IntegrationAvailability.Unavailable ||
                            context.IntegrationAvailability == IntegrationAvailability.NotConfigured)
                        {
                            return OperationalMode.Blocked;
                        }
                    }
                }
            }

            if (isLocalSupported)
            {
                if (context.ConnectivityMode == ConnectivityMode.Online)
                {
                    return context.IntegrationAvailability == IntegrationAvailability.Available
                        ? OperationalMode.Normal
                        : OperationalMode.Degraded;
                }
                return OperationalMode.Offline;
            }

            return OperationalMode.Blocked;
        }
    }
}
