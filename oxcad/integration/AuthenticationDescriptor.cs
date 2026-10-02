using System;

namespace OxCad.Integration
{
    /// <summary>
    /// Esquema declarativo de autenticação para provedores externos.
    /// </summary>
    public enum AuthenticationScheme
    {
        None,
        OAuth2,
        OpenIdConnect,
        ClientCredentials,
        AuthorizationCode,
        ServiceAccount,
        ApiKey,
        BasicAuth
    }

    /// <summary>
    /// Descritor de autenticação puramente declarativo.
    /// Registra apenas requisitos arquiteturais, sem armazenar credenciais, segredos, tokens ou senhas.
    /// </summary>
    public sealed class AuthenticationDescriptor
    {
        public AuthenticationScheme Scheme { get; }
        public bool RequiresUserContext { get; }
        public bool RequiresClientCredential { get; }
        public bool SupportsRefresh { get; }

        public AuthenticationDescriptor(
            AuthenticationScheme scheme,
            bool requiresUserContext = false,
            bool requiresClientCredential = false,
            bool supportsRefresh = false)
        {
            Scheme = scheme;
            RequiresUserContext = requiresUserContext;
            RequiresClientCredential = requiresClientCredential;
            SupportsRefresh = supportsRefresh;
        }

        public static AuthenticationDescriptor None() =>
            new AuthenticationDescriptor(AuthenticationScheme.None);

        public static AuthenticationDescriptor OAuth2UserDelegated(bool supportsRefresh = true) =>
            new AuthenticationDescriptor(
                AuthenticationScheme.OAuth2,
                requiresUserContext: true,
                requiresClientCredential: true,
                supportsRefresh: supportsRefresh);

        public static AuthenticationDescriptor OAuth2ClientCredentials() =>
            new AuthenticationDescriptor(
                AuthenticationScheme.ClientCredentials,
                requiresUserContext: false,
                requiresClientCredential: true,
                supportsRefresh: false);

        public static AuthenticationDescriptor OpenIdConnect() =>
            new AuthenticationDescriptor(
                AuthenticationScheme.OpenIdConnect,
                requiresUserContext: true,
                requiresClientCredential: true,
                supportsRefresh: true);

        public static AuthenticationDescriptor ApiKey() =>
            new AuthenticationDescriptor(
                AuthenticationScheme.ApiKey,
                requiresUserContext: false,
                requiresClientCredential: true,
                supportsRefresh: false);

        public static AuthenticationDescriptor BasicAuth() =>
            new AuthenticationDescriptor(
                AuthenticationScheme.BasicAuth,
                requiresUserContext: true,
                requiresClientCredential: true,
                supportsRefresh: false);
    }
}
