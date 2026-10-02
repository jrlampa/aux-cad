using System;

namespace OxCad.Integration
{
    /// <summary>
    /// Contexto de execução para integrações externas.
    /// Transporta a identidade autoritativa do projeto corrente.
    ///
    /// REGRA FUNDAMENTAL:
    /// O AutoCAD é a única autoridade da identidade real do DWG.
    /// Nenhum provedor externo tem permissão para alterar SOB_ID, DatabaseFingerprint,
    /// escopo do projeto ou desviar o caminho DWG autorizado.
    /// </summary>
    public sealed class IntegrationContext
    {
        public string SobId { get; }
        public string ProjectRoot { get; }
        public string DwgPath { get; }
        public string DatabaseFingerprint { get; }
        public string CorrelationId { get; }
        public string ExecutionId { get; }

        public IntegrationContext(
            string sobId,
            string projectRoot,
            string dwgPath,
            string databaseFingerprint,
            string? correlationId = null,
            string? executionId = null)
        {
            if (string.IsNullOrWhiteSpace(sobId))
                throw new ArgumentException("SobId não pode ser nulo ou vazio.", nameof(sobId));
            if (string.IsNullOrWhiteSpace(projectRoot))
                throw new ArgumentException("ProjectRoot não pode ser nulo ou vazio.", nameof(projectRoot));
            if (string.IsNullOrWhiteSpace(dwgPath))
                throw new ArgumentException("DwgPath não pode ser nulo ou vazio.", nameof(dwgPath));
            if (string.IsNullOrWhiteSpace(databaseFingerprint))
                throw new ArgumentException("DatabaseFingerprint não pode ser nulo ou vazio.", nameof(databaseFingerprint));

            SobId = sobId.Trim();
            ProjectRoot = projectRoot.Trim();
            DwgPath = dwgPath.Trim();
            DatabaseFingerprint = databaseFingerprint.Trim();
            CorrelationId = string.IsNullOrWhiteSpace(correlationId) ? Guid.NewGuid().ToString("N") : correlationId!.Trim();
            ExecutionId = string.IsNullOrWhiteSpace(executionId) ? Guid.NewGuid().ToString("N") : executionId!.Trim();
        }

        /// <summary>
        /// Valida se a requisição externa respeita a autoridade do DWG ativo.
        /// Retorna true se a identidade for compatível; false se houver tentativa de sequestro de identidade.
        /// </summary>
        public bool ValidateSovereignty(string requestedSobId, string requestedFingerprint)
        {
            if (string.IsNullOrWhiteSpace(requestedSobId) || string.IsNullOrWhiteSpace(requestedFingerprint))
                return false;

            return string.Equals(SobId, requestedSobId.Trim(), StringComparison.OrdinalIgnoreCase) &&
                   string.Equals(DatabaseFingerprint, requestedFingerprint.Trim(), StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>
        /// Assegura imutabilidade: providers não podem sobrescrever os campos de autoridade.
        /// </summary>
        public IntegrationResult ValidateAuthorityAgainst(string requestedDwgPath)
        {
            if (string.IsNullOrWhiteSpace(requestedDwgPath))
                return IntegrationResult.InvalidRequest("Caminho do DWG solicitado não informado.");

            if (!string.Equals(DwgPath, requestedDwgPath.Trim(), StringComparison.OrdinalIgnoreCase))
            {
                return IntegrationResult.IdentityMismatch(
                    $"Tentativa de associar DWG não autorizado. Esperado: '{DwgPath}', Solicitado: '{requestedDwgPath}'.");
            }

            return IntegrationResult.Success();
        }
    }
}
