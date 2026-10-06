using System;
using System.Threading.Tasks;

namespace OxCad.Integration
{
    public static class UniversalizacaoOxCadCaller
    {
        public static Task<IntegrationResult<UniversalizacaoQueryData>> ConsultarAsync(
            OxCadVerifiedDwgContext verifiedContext,
            string? activeGroup,
            WorkOrderQuery query,
            bool independentQuery = false)
        {
            return ConsultarAsync(
                verifiedContext, activeGroup, query, independentQuery,
                WorkspaceService.ConsultarUniversalizacaoAsync);
        }

        internal static async Task<IntegrationResult<UniversalizacaoQueryData>> ConsultarAsync(
            OxCadVerifiedDwgContext verifiedContext,
            string? activeGroup,
            WorkOrderQuery query,
            bool independentQuery,
            Func<IntegrationContext, WorkOrderQuery, bool,
                Task<IntegrationResult<UniversalizacaoQueryData>>> dispatch)
        {
            if (verifiedContext == null || query == null ||
                (activeGroup != "A" && activeGroup != "B") || !query.IsValid ||
                verifiedContext.ContractVersion != 1 ||
                verifiedContext.ProjectScopeStatus != "Bound" ||
                string.IsNullOrWhiteSpace(verifiedContext.SobId) ||
                string.IsNullOrWhiteSpace(verifiedContext.DwgPath) ||
                string.IsNullOrWhiteSpace(verifiedContext.DwgIdentity) ||
                verifiedContext.ContextGeneration < 0)
                return IntegrationResult<UniversalizacaoQueryData>.InvalidRequest();

            var activeIdentity = new WorkOrderQuery(
                activeGroup, verifiedContext.SobId);
            if (!independentQuery && !activeIdentity.Matches(query))
                return IntegrationResult<UniversalizacaoQueryData>.IdentityMismatch();

            string correlationId = verifiedContext.CorrelationId ??
                Guid.NewGuid().ToString("N");
            string executionId = verifiedContext.ExecutionId ??
                Guid.NewGuid().ToString("N");
            if (!IsSafeId(correlationId) || !IsSafeId(executionId))
                return IntegrationResult<UniversalizacaoQueryData>.InvalidRequest();

            string projectRoot = WorkspaceService.ObterDiretorioRaizProjeto(
                verifiedContext.DwgPath);
            var context = new IntegrationContext(
                verifiedContext.SobId, projectRoot, verifiedContext.DwgPath,
                verifiedContext.DwgIdentity, correlationId, executionId);

            var result = await dispatch(context, query, independentQuery);
            if (!result.IsSuccess)
                return result;

            var data = result.Data;
            if (data?.Identity == null || !query.Matches(data.Identity) ||
                data.RequestedGrupo != query.Grupo ||
                data.RequestedSob != query.Sob ||
                data.ReturnedGrupo != query.Grupo ||
                data.ReturnedSob != query.Sob ||
                data.CorrelationId != correlationId ||
                data.ExecutionId != executionId)
                return IntegrationResult<UniversalizacaoQueryData>.IdentityMismatch();

            return result;
        }

        private static bool IsSafeId(string value) =>
            !string.IsNullOrWhiteSpace(value) &&
            System.Text.RegularExpressions.Regex.IsMatch(
                value, @"\A[A-Za-z0-9_-]{1,128}\z");
    }
}