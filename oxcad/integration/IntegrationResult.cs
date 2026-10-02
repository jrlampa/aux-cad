using System;

namespace OxCad.Integration
{
    /// <summary>
    /// Estados padronizados de execução e disponibilidade de integrações.
    /// </summary>
    public enum IntegrationStatus
    {
        Success,
        NotConfigured,
        NotSupported,
        AuthRequired,
        Unavailable,
        Timeout,
        InvalidRequest,
        RemoteError,
        IdentityMismatch,
        Cancelled
    }

    /// <summary>
    /// Resultado de operação de integração sem retorno tipado de dados.
    /// Não utiliza exceções como fluxo de controle normal.
    /// </summary>
    public class IntegrationResult
    {
        public IntegrationStatus Status { get; }
        public bool IsSuccess => Status == IntegrationStatus.Success;
        public string? ErrorCode { get; }
        public string? ErrorMessage { get; }
        public string? TechnicalDetails { get; }

        public IntegrationResult(
            IntegrationStatus status,
            string? errorCode = null,
            string? errorMessage = null,
            string? technicalDetails = null)
        {
            Status = status;
            ErrorCode = errorCode;
            ErrorMessage = errorMessage;
            TechnicalDetails = technicalDetails;
        }

        public static IntegrationResult Success() =>
            new IntegrationResult(IntegrationStatus.Success);

        public static IntegrationResult NotConfigured(string message = "Provedor de integração não configurado.") =>
            new IntegrationResult(IntegrationStatus.NotConfigured, "NOT_CONFIGURED", message);

        public static IntegrationResult NotSupported(string message = "Capacidade não suportada pelo provedor.") =>
            new IntegrationResult(IntegrationStatus.NotSupported, "NOT_SUPPORTED", message);

        public static IntegrationResult AuthRequired(string message = "Autenticação requerida para este provedor.") =>
            new IntegrationResult(IntegrationStatus.AuthRequired, "AUTH_REQUIRED", message);

        public static IntegrationResult Unavailable(string message = "Provedor temporariamente indisponível.") =>
            new IntegrationResult(IntegrationStatus.Unavailable, "UNAVAILABLE", message);

        public static IntegrationResult Timeout(string message = "Tempo limite da operação esgotado.") =>
            new IntegrationResult(IntegrationStatus.Timeout, "TIMEOUT", message);

        public static IntegrationResult InvalidRequest(string message = "Requisição inválida para o provedor.") =>
            new IntegrationResult(IntegrationStatus.InvalidRequest, "INVALID_REQUEST", message);

        public static IntegrationResult RemoteError(string message, string? details = null) =>
            new IntegrationResult(IntegrationStatus.RemoteError, "REMOTE_ERROR", message, details);

        public static IntegrationResult IdentityMismatch(string message = "Inconsistência de identidade ou violação de autoridade do DWG.") =>
            new IntegrationResult(IntegrationStatus.IdentityMismatch, "IDENTITY_MISMATCH", message);

        public static IntegrationResult Cancelled(string message = "Operação de integração cancelada.") =>
            new IntegrationResult(IntegrationStatus.Cancelled, "CANCELLED", message);
    }

    /// <summary>
    /// Resultado de operação de integração com dado de retorno tipado.
    /// </summary>
    public sealed class IntegrationResult<T> : IntegrationResult
    {
        public T? Data { get; }

        public IntegrationResult(
            IntegrationStatus status,
            T? data = default,
            string? errorCode = null,
            string? errorMessage = null,
            string? technicalDetails = null)
            : base(status, errorCode, errorMessage, technicalDetails)
        {
            Data = data;
        }

        public static IntegrationResult<T> Success(T data) =>
            new IntegrationResult<T>(IntegrationStatus.Success, data);

        public static new IntegrationResult<T> NotConfigured(string message = "Provedor de integração não configurado.") =>
            new IntegrationResult<T>(IntegrationStatus.NotConfigured, default, "NOT_CONFIGURED", message);

        public static new IntegrationResult<T> NotSupported(string message = "Capacidade não suportada pelo provedor.") =>
            new IntegrationResult<T>(IntegrationStatus.NotSupported, default, "NOT_SUPPORTED", message);

        public static new IntegrationResult<T> AuthRequired(string message = "Autenticação requerida.") =>
            new IntegrationResult<T>(IntegrationStatus.AuthRequired, default, "AUTH_REQUIRED", message);

        public static new IntegrationResult<T> Unavailable(string message = "Provedor indisponível.") =>
            new IntegrationResult<T>(IntegrationStatus.Unavailable, default, "UNAVAILABLE", message);

        public static new IntegrationResult<T> Timeout(string message = "Tempo limite excedido.") =>
            new IntegrationResult<T>(IntegrationStatus.Timeout, default, "TIMEOUT", message);

        public static new IntegrationResult<T> InvalidRequest(string message = "Requisição inválida.") =>
            new IntegrationResult<T>(IntegrationStatus.InvalidRequest, default, "INVALID_REQUEST", message);

        public static new IntegrationResult<T> RemoteError(string message, string? details = null) =>
            new IntegrationResult<T>(IntegrationStatus.RemoteError, default, "REMOTE_ERROR", message, details);

        public static new IntegrationResult<T> IdentityMismatch(string message = "Violação de autoridade de identidade.") =>
            new IntegrationResult<T>(IntegrationStatus.IdentityMismatch, default, "IDENTITY_MISMATCH", message);

        public static new IntegrationResult<T> Cancelled(string message = "Operação cancelada.") =>
            new IntegrationResult<T>(IntegrationStatus.Cancelled, default, "CANCELLED", message);
    }
}
