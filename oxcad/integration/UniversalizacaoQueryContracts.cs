using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace OxCad.Integration
{
    public sealed class WorkOrderQuery
    {
        [JsonConstructor]
        public WorkOrderQuery(string? grupo, string? sob)
        {
            Grupo = grupo;
            Sob = sob;
        }

        [JsonPropertyName("grupo")]
        public string? Grupo { get; }
        [JsonPropertyName("sob")]
        public string? Sob { get; }

        [JsonIgnore]
        public bool IsValid => (Grupo == "A" || Grupo == "B") &&
            Sob != null && Regex.IsMatch(Sob, @"\A[A-Za-z0-9_-]{1,128}\z");

        public bool Matches(WorkOrderQuery? other) => other != null &&
            string.Equals(Grupo, other.Grupo, StringComparison.Ordinal) &&
            string.Equals(Sob, other.Sob, StringComparison.Ordinal);
    }

    public sealed class UniversalizacaoProjectData
    {
        [JsonPropertyName("nome")] public string? Nome { get; set; }
        [JsonPropertyName("endereco")] public string? Endereco { get; set; }
        [JsonPropertyName("bairro")] public string? Bairro { get; set; }
        [JsonPropertyName("municipio")] public string? Municipio { get; set; }
        [JsonPropertyName("polo_tecnico")] public string? PoloTecnico { get; set; }
        [JsonPropertyName("tipo_servico")] public string? TipoServico { get; set; }
        [JsonPropertyName("notas_observacao")] public string? NotasObservacao { get; set; }
        [JsonPropertyName("referencia")] public string? Referencia { get; set; }
    }

    public sealed class UniversalizacaoOrderStatus
    {
        [JsonPropertyName("etapa_ordem_proj")] public string? EtapaOrdemProj { get; set; }
        [JsonPropertyName("estado_ordem_proj")] public string? EstadoOrdemProj { get; set; }
        [JsonPropertyName("status_ordem")] public string? StatusOrdem { get; set; }
    }

    public sealed class UniversalizacaoHandshakeStep
    {
        [JsonPropertyName("stage")] public string? Stage { get; set; }
        [JsonPropertyName("http_status")] public int HttpStatus { get; set; }
        [JsonPropertyName("authenticate_schemes")] public List<string> AuthenticateSchemes { get; set; } = new();
        [JsonPropertyName("authorization_present")] public bool AuthorizationPresent { get; set; }
        [JsonPropertyName("outgoing_type")] public int? OutgoingType { get; set; }
        [JsonPropertyName("outgoing_token_bytes")] public int OutgoingTokenBytes { get; set; }
        [JsonPropertyName("incoming_type")] public int? IncomingType { get; set; }
        [JsonPropertyName("incoming_token_bytes")] public int IncomingTokenBytes { get; set; }
    }

    public sealed class UniversalizacaoTransportData
    {
        [JsonPropertyName("operation")] public string? Operation { get; set; }
        [JsonPropertyName("method")] public string? Method { get; set; }
        [JsonPropertyName("route")] public string? Route { get; set; }
        [JsonPropertyName("authentication_backend")] public string? AuthenticationBackend { get; set; }
        [JsonPropertyName("ntlm_version")] public string? NtlmVersion { get; set; }
        [JsonPropertyName("sspi")] public bool Sspi { get; set; }
        [JsonPropertyName("expected_target_seen")] public bool ExpectedTargetSeen { get; set; }
        [JsonPropertyName("proxy_mode")] public string? ProxyMode { get; set; }
        [JsonPropertyName("redirects_followed")] public bool RedirectsFollowed { get; set; }
        [JsonPropertyName("connection_reused")] public bool ConnectionReused { get; set; }
        [JsonPropertyName("cookies_sent")] public bool CookiesSent { get; set; }
        [JsonPropertyName("cookies_persisted")] public bool CookiesPersisted { get; set; }
        [JsonPropertyName("handshake_steps")] public List<UniversalizacaoHandshakeStep>? HandshakeSteps { get; set; }
    }

    public sealed class UniversalizacaoQueryData
    {
        [JsonPropertyName("identity")] public WorkOrderQuery? Identity { get; set; }
        [JsonPropertyName("requested_grupo")] public string? RequestedGrupo { get; set; }
        [JsonPropertyName("requested_sob")] public string? RequestedSob { get; set; }
        [JsonPropertyName("returned_grupo")] public string? ReturnedGrupo { get; set; }
        [JsonPropertyName("returned_sob")] public string? ReturnedSob { get; set; }
        [JsonPropertyName("project_data")] public UniversalizacaoProjectData? ProjectData { get; set; }
        [JsonPropertyName("order_status")] public UniversalizacaoOrderStatus? OrderStatus { get; set; }
        [JsonPropertyName("transport")] public UniversalizacaoTransportData? Transport { get; set; }
        [JsonPropertyName("http_status")] public int? HttpStatus { get; set; }
        [JsonPropertyName("authenticated")] public bool Authenticated { get; set; }
        [JsonPropertyName("outcome")] public string? Outcome { get; set; }
        [JsonPropertyName("correlation_id")] public string? CorrelationId { get; set; }
        [JsonPropertyName("execution_id")] public string? ExecutionId { get; set; }
    }

    public static class UniversalizacaoQueryContract
    {
        private sealed class ResultPayload
        {
            [JsonPropertyName("status")] public string? Status { get; set; }
            [JsonPropertyName("data")] public UniversalizacaoQueryData? Data { get; set; }
            [JsonPropertyName("error_code")] public string? ErrorCode { get; set; }
            [JsonPropertyName("error_message")] public string? ErrorMessage { get; set; }
        }

        private sealed class Envelope
        {
            [JsonPropertyName("sucesso")] public bool Success { get; set; }
            [JsonPropertyName("query_identity")] public WorkOrderQuery? QueryIdentity { get; set; }
            [JsonPropertyName("resultado")] public ResultPayload? Result { get; set; }
        }

        public static IntegrationResult<UniversalizacaoQueryData> Parse(
            string json, WorkOrderQuery expected)
        {
            if (expected == null || !expected.IsValid)
                return IntegrationResult<UniversalizacaoQueryData>.InvalidRequest();
            try
            {
                var envelope = JsonSerializer.Deserialize<Envelope>(json);
                if (envelope?.Result == null)
                    return IntegrationResult<UniversalizacaoQueryData>.RemoteError("Resposta de integracao invalida.");
                if (!expected.Matches(envelope.QueryIdentity))
                    return IntegrationResult<UniversalizacaoQueryData>.IdentityMismatch();
                var payload = envelope.Result;
                IntegrationStatus status = payload.Status switch
                {
                    "SUCCESS" => IntegrationStatus.Success,
                    "AUTH_REQUIRED" => IntegrationStatus.AuthRequired,
                    "INVALID_REQUEST" => IntegrationStatus.InvalidRequest,
                    "IDENTITY_MISMATCH" => IntegrationStatus.IdentityMismatch,
                    "UNAVAILABLE" => IntegrationStatus.Unavailable,
                    "TIMEOUT" => IntegrationStatus.Timeout,
                    "NOT_SUPPORTED" => IntegrationStatus.NotSupported,
                    "NOT_CONFIGURED" => IntegrationStatus.NotConfigured,
                    "CANCELLED" => IntegrationStatus.Cancelled,
                    _ => IntegrationStatus.RemoteError
                };
                var data = payload.Data;
                if (status == IntegrationStatus.Success)
                {
                    if (!envelope.Success || data == null || data.Identity == null ||
                        data.ProjectData == null || data.OrderStatus == null ||
                        data.HttpStatus != 200 || !data.Authenticated ||
                        !HasVerifiedReadTransport(data.Transport))
                        return IntegrationResult<UniversalizacaoQueryData>.RemoteError("Resposta positiva incompleta.");
                    if (!expected.Matches(data.Identity) ||
                        data.RequestedSob != expected.Sob || data.RequestedGrupo != expected.Grupo ||
                        data.ReturnedSob != expected.Sob || data.ReturnedGrupo != expected.Grupo)
                        return IntegrationResult<UniversalizacaoQueryData>.IdentityMismatch();
                }
                return new IntegrationResult<UniversalizacaoQueryData>(
                    status, data, payload.ErrorCode, payload.ErrorMessage);
            }
            catch (JsonException)
            {
                return IntegrationResult<UniversalizacaoQueryData>.RemoteError("JSON de integracao invalido.");
            }
        }

        private static bool HasVerifiedReadTransport(UniversalizacaoTransportData? transport)
        {
            if (transport == null || transport.Operation != "QUERY_ORDER" ||
                transport.Method != "GET" ||
                transport.Route != "/sistemas/universalizacao/controle.asp" ||
                transport.AuthenticationBackend != "pyspnego.NTLMProxy/use_ntlm" ||
                transport.NtlmVersion != "NTLMv2" || transport.Sspi ||
                !transport.ExpectedTargetSeen || transport.ProxyMode != "DIRECT" ||
                transport.RedirectsFollowed || !transport.ConnectionReused ||
                transport.CookiesSent || transport.CookiesPersisted)
                return false;

            var steps = transport.HandshakeSteps;
            return steps != null && steps.Count == 3 &&
                steps[0].Stage == "GET" && steps[0].HttpStatus == 401 &&
                !steps[0].AuthorizationPresent &&
                steps[1].Stage == "TYPE1" && steps[1].HttpStatus == 401 &&
                steps[1].OutgoingType == 1 && steps[1].IncomingType == 2 &&
                steps[1].OutgoingTokenBytes > 0 && steps[1].IncomingTokenBytes > 0 &&
                steps[1].AuthenticateSchemes.Contains("ntlm") &&
                steps[2].Stage == "TYPE3" && steps[2].HttpStatus == 200 &&
                steps[2].OutgoingType == 3 &&
                steps[2].OutgoingTokenBytes > 0 && steps[2].AuthorizationPresent;
        }
    }
}