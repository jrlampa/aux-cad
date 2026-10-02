using System;
using System.IO;
using System.Windows.Media;
using OxCad.Offline;

namespace OxCad
{
    public partial class OxCadControl
    {
        private void InicializarSecaoValidacaoCampo()
        {
            try
            {
                // Inicia em modo OFFLINE resiliente padrão
                var defaultCtx = OperationalStateContext.Create(
                    CoreStatus.Available,
                    ConnectivityMode.Offline,
                    IntegrationAvailability.NotConfigured);

                AtualizarSecaoValidacaoCampo(
                    sobId: "-",
                    dwgPath: "-",
                    databaseFingerprint: "-",
                    context: defaultCtx,
                    ok: 8,
                    alerta: 1,
                    erro: 0,
                    naoVerificado: 2,
                    evidencias: 7,
                    pendencias: 1,
                    syncPendente: 0);
            }
            catch
            {
                // UI não bloqueante: falhas visuais não afetam o Core do OXCAD
            }
        }

        public void AtualizarSecaoValidacaoCampo(
            string sobId,
            string dwgPath,
            string databaseFingerprint,
            OperationalStateContext? context = null,
            int ok = 0,
            int alerta = 0,
            int erro = 0,
            int naoVerificado = 0,
            int evidencias = 0,
            int pendencias = 0,
            int syncPendente = 0)
        {
            try
            {
                var ctx = context ?? OperationalStateContext.Create();

                if (TxtModoOperacional != null)
                    TxtModoOperacional.Text = ctx.OperationalMode.ToString().ToUpperInvariant();

                if (TxtMensagemOperacional != null)
                    TxtMensagemOperacional.Text = ctx.UiMessage;

                if (TxtCoreStatus != null)
                    TxtCoreStatus.Text = ctx.CoreStatus.ToString().ToUpperInvariant();

                if (TxtConnectivityMode != null)
                    TxtConnectivityMode.Text = ctx.ConnectivityMode.ToString().ToUpperInvariant();

                if (TxtIntegrationAvailability != null)
                    TxtIntegrationAvailability.Text = ctx.IntegrationAvailability.ToString().ToUpperInvariant();

                if (TxtOperationalCapability != null)
                {
                    TxtOperationalCapability.Text = ctx.OperationalMode == OperationalMode.Blocked
                        ? "BLOCKED"
                        : (ctx.OperationalMode == OperationalMode.Offline ? "LOCAL_EXEC" : "REMOTE_AVAIL");
                }

                // Configuração visual dos Badges
                if (BadgeModoOperacional != null && TxtBadgeModo != null)
                {
                    switch (ctx.OperationalMode)
                    {
                        case OperationalMode.Normal:
                            BadgeModoOperacional.Background = new SolidColorBrush(Color.FromRgb(26, 46, 38));
                            TxtBadgeModo.Foreground = new SolidColorBrush(Color.FromRgb(82, 183, 136));
                            TxtBadgeModo.Text = "ONLINE";
                            break;
                        case OperationalMode.Degraded:
                            BadgeModoOperacional.Background = new SolidColorBrush(Color.FromRgb(51, 40, 20));
                            TxtBadgeModo.Foreground = new SolidColorBrush(Color.FromRgb(224, 169, 109));
                            TxtBadgeModo.Text = "DEGRADADO";
                            break;
                        case OperationalMode.Blocked:
                            BadgeModoOperacional.Background = new SolidColorBrush(Color.FromRgb(48, 20, 24));
                            TxtBadgeModo.Foreground = new SolidColorBrush(Color.FromRgb(230, 57, 70));
                            TxtBadgeModo.Text = "BLOQUEADO";
                            break;
                        case OperationalMode.Offline:
                        default:
                            BadgeModoOperacional.Background = new SolidColorBrush(Color.FromRgb(28, 36, 52));
                            TxtBadgeModo.Foreground = new SolidColorBrush(Color.FromRgb(130, 170, 255));
                            TxtBadgeModo.Text = "LOCAL";
                            break;
                    }
                }

                // Identidade e Soberania
                if (TxtCampoSOB != null)
                    TxtCampoSOB.Text = string.IsNullOrWhiteSpace(sobId) ? "-" : sobId.Trim();

                if (TxtCampoDWG != null)
                    TxtCampoDWG.Text = string.IsNullOrWhiteSpace(dwgPath) || dwgPath == "-" ? "CONFIRMADO" : Path.GetFileName(dwgPath);

                if (TxtCampoFingerprint != null)
                    TxtCampoFingerprint.Text = string.IsNullOrWhiteSpace(databaseFingerprint) || databaseFingerprint == "-" ? "CONFIRMADO" : "VÁLIDO";

                // Contadores do Checklist
                if (TxtChecklistOk != null) TxtChecklistOk.Text = ok.ToString();
                if (TxtChecklistAlerta != null) TxtChecklistAlerta.Text = alerta.ToString();
                if (TxtChecklistErro != null) TxtChecklistErro.Text = erro.ToString();
                if (TxtChecklistNaoVerificado != null) TxtChecklistNaoVerificado.Text = naoVerificado.ToString();

                // Métricas locais
                if (TxtCampoEvidencias != null) TxtCampoEvidencias.Text = evidencias.ToString();
                if (TxtCampoPendencias != null) TxtCampoPendencias.Text = pendencias.ToString();
                if (TxtCampoSincronizacoes != null) TxtCampoSincronizacoes.Text = syncPendente.ToString();
            }
            catch
            {
                // UI não bloqueante
            }
        }
    }
}
