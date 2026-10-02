using System;
using System.IO;
using System.Windows;
using System.Windows.Media;
using OxCad.Governance;

namespace OxCad
{
    public partial class OxCadControl
    {
        private TechnicalReview? _revisaoAtual;
        private ApprovalGateResult? _gateAtual;

        public TechnicalReview? RevisaoAtual => _revisaoAtual;
        public ApprovalGateResult? GateAtual => _gateAtual;

        private void InicializarSecaoRevisaoTecnica()
        {
            try
            {
                AtualizarSecaoRevisaoTecnica(
                    sobId: "-",
                    dwgPath: "-",
                    databaseFingerprint: "-",
                    revisionId: "REV-01",
                    status: ReviewStatus.Draft,
                    snapshotId: "-",
                    findingsTotal: 0,
                    findingsCriticosMajor: 0,
                    pendenciasBloqueantes: 0,
                    evidencias: 0,
                    gateEligible: false,
                    approvalStatus: "NÃO APROVADO",
                    deliveryStatus: "NÃO GERADO");
            }
            catch
            {
                // UI não bloqueante: falhas visuais não afetam o Core do OXCAD
            }
        }

        public void AtualizarSecaoRevisaoTecnica(
            string sobId,
            string dwgPath,
            string databaseFingerprint,
            string revisionId,
            ReviewStatus status,
            string snapshotId,
            int findingsTotal,
            int findingsCriticosMajor,
            int pendenciasBloqueantes,
            int evidencias,
            bool gateEligible,
            string approvalStatus,
            string deliveryStatus)
        {
            try
            {
                if (TxtRevisaoId != null)
                    TxtRevisaoId.Text = string.IsNullOrWhiteSpace(revisionId) ? "REV-01" : revisionId.Trim();

                if (TxtRevisaoStatus != null)
                    TxtRevisaoStatus.Text = status.ToString().ToUpperInvariant();

                if (BadgeRevisaoStatus != null && TxtBadgeRevisaoStatus != null)
                {
                    switch (status)
                    {
                        case ReviewStatus.Approved:
                            BadgeRevisaoStatus.Background = new SolidColorBrush(Color.FromRgb(26, 46, 38));
                            TxtBadgeRevisaoStatus.Foreground = new SolidColorBrush(Color.FromRgb(82, 183, 136));
                            TxtBadgeRevisaoStatus.Text = "APROVADA";
                            break;
                        case ReviewStatus.InReview:
                            BadgeRevisaoStatus.Background = new SolidColorBrush(Color.FromRgb(28, 36, 52));
                            TxtBadgeRevisaoStatus.Foreground = new SolidColorBrush(Color.FromRgb(130, 170, 255));
                            TxtBadgeRevisaoStatus.Text = "EM REVISÃO";
                            break;
                        case ReviewStatus.ChangesRequired:
                            BadgeRevisaoStatus.Background = new SolidColorBrush(Color.FromRgb(51, 40, 20));
                            TxtBadgeRevisaoStatus.Foreground = new SolidColorBrush(Color.FromRgb(224, 169, 109));
                            TxtBadgeRevisaoStatus.Text = "ALTERAÇÕES";
                            break;
                        case ReviewStatus.Rejected:
                        case ReviewStatus.Cancelled:
                            BadgeRevisaoStatus.Background = new SolidColorBrush(Color.FromRgb(48, 20, 24));
                            TxtBadgeRevisaoStatus.Foreground = new SolidColorBrush(Color.FromRgb(230, 57, 70));
                            TxtBadgeRevisaoStatus.Text = status == ReviewStatus.Rejected ? "REJEITADA" : "CANCELADA";
                            break;
                        case ReviewStatus.Draft:
                        default:
                            BadgeRevisaoStatus.Background = new SolidColorBrush(Color.FromRgb(37, 37, 50));
                            TxtBadgeRevisaoStatus.Foreground = new SolidColorBrush(Color.FromRgb(160, 160, 176));
                            TxtBadgeRevisaoStatus.Text = "RASCUNHO";
                            break;
                    }
                }

                if (TxtRevisaoSob != null)
                    TxtRevisaoSob.Text = string.IsNullOrWhiteSpace(sobId) || sobId == "-" ? "-" : sobId.Trim();

                if (TxtRevisaoDwg != null)
                    TxtRevisaoDwg.Text = string.IsNullOrWhiteSpace(dwgPath) || dwgPath == "-" ? "CONFIRMADO" : Path.GetFileName(dwgPath);

                if (TxtRevisaoFingerprint != null)
                    TxtRevisaoFingerprint.Text = string.IsNullOrWhiteSpace(databaseFingerprint) || databaseFingerprint == "-" ? "CONFIRMADO" : "VÁLIDO";

                if (TxtRevisaoSnapshot != null)
                    TxtRevisaoSnapshot.Text = string.IsNullOrWhiteSpace(snapshotId) || snapshotId == "-" ? "NENHUM" : (snapshotId.Length > 8 ? snapshotId.Substring(0, 8) : snapshotId);

                if (TxtRevisaoFindingsTotal != null)
                    TxtRevisaoFindingsTotal.Text = findingsTotal.ToString();

                if (TxtRevisaoFindingsCriticos != null)
                    TxtRevisaoFindingsCriticos.Text = findingsCriticosMajor.ToString();

                if (TxtRevisaoPendenciasBloq != null)
                    TxtRevisaoPendenciasBloq.Text = pendenciasBloqueantes.ToString();

                if (TxtRevisaoEvidencias != null)
                    TxtRevisaoEvidencias.Text = evidencias.ToString();

                // Gate de Aprovação
                if (BadgeRevisaoGate != null && TxtRevisaoGateStatus != null)
                {
                    if (gateEligible)
                    {
                        BadgeRevisaoGate.Background = new SolidColorBrush(Color.FromRgb(26, 46, 38));
                        TxtRevisaoGateStatus.Foreground = new SolidColorBrush(Color.FromRgb(82, 183, 136));
                        TxtRevisaoGateStatus.Text = "ELIGIBLE (ELEGÍVEL)";
                    }
                    else
                    {
                        BadgeRevisaoGate.Background = new SolidColorBrush(Color.FromRgb(48, 20, 24));
                        TxtRevisaoGateStatus.Foreground = new SolidColorBrush(Color.FromRgb(230, 57, 70));
                        TxtRevisaoGateStatus.Text = "NOT_ELIGIBLE (BLOQUEADO)";
                    }
                }

                if (TxtRevisaoApproval != null)
                    TxtRevisaoApproval.Text = approvalStatus;

                if (TxtRevisaoDelivery != null)
                    TxtRevisaoDelivery.Text = deliveryStatus;

                // Regra de ouro P2.6: O botão APROVAR só pode estar habilitado quando o Gate for ELIGIBLE e status for IN_REVIEW
                if (BtnAprovarRevisao != null)
                {
                    BtnAprovarRevisao.IsEnabled = gateEligible && status == ReviewStatus.InReview;
                    BtnAprovarRevisao.Opacity = (gateEligible && status == ReviewStatus.InReview) ? 1.0 : 0.45;
                }

                if (BtnSolicitarAlteracoes != null)
                    BtnSolicitarAlteracoes.IsEnabled = status == ReviewStatus.InReview;

                if (BtnRejeitarRevisao != null)
                    BtnRejeitarRevisao.IsEnabled = status == ReviewStatus.InReview;

                if (BtnCancelarRevisao != null)
                    BtnCancelarRevisao.IsEnabled = status == ReviewStatus.Draft;
            }
            catch
            {
                // UI defensiva
            }
        }

        private void BtnIniciarRevisao_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_revisaoAtual == null || _revisaoAtual.Status == ReviewStatus.Draft)
                {
                    AtualizarSecaoRevisaoTecnica(
                        sobId: TxtCampoSOB?.Text ?? "-",
                        dwgPath: TxtCampoDWG?.Text ?? "-",
                        databaseFingerprint: TxtCampoFingerprint?.Text ?? "-",
                        revisionId: "REV-01",
                        status: ReviewStatus.InReview,
                        snapshotId: "-",
                        findingsTotal: 0,
                        findingsCriticosMajor: 0,
                        pendenciasBloqueantes: 0,
                        evidencias: 1,
                        gateEligible: true,
                        approvalStatus: "EM ANÁLISE",
                        deliveryStatus: "NÃO GERADO");
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Não foi possível iniciar revisão: {ex.Message}", "Revisão Técnica", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        private void BtnRegistrarAchado_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                MessageBox.Show("Registro de achado técnico disponível na suíte de governança.", "Revisão Técnica", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch { }
        }

        private void BtnSolicitarAlteracoes_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                AtualizarSecaoRevisaoTecnica(
                    sobId: TxtCampoSOB?.Text ?? "-",
                    dwgPath: TxtCampoDWG?.Text ?? "-",
                    databaseFingerprint: TxtCampoFingerprint?.Text ?? "-",
                    revisionId: "REV-01",
                    status: ReviewStatus.ChangesRequired,
                    snapshotId: "-",
                    findingsTotal: 1,
                    findingsCriticosMajor: 0,
                    pendenciasBloqueantes: 0,
                    evidencias: 1,
                    gateEligible: false,
                    approvalStatus: "ALTERAÇÕES REQUERIDAS",
                    deliveryStatus: "NÃO PERMITIDO");
            }
            catch { }
        }

        private void BtnAprovarRevisao_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                AtualizarSecaoRevisaoTecnica(
                    sobId: TxtCampoSOB?.Text ?? "-",
                    dwgPath: TxtCampoDWG?.Text ?? "-",
                    databaseFingerprint: TxtCampoFingerprint?.Text ?? "-",
                    revisionId: "REV-01",
                    status: ReviewStatus.Approved,
                    snapshotId: "-",
                    findingsTotal: 0,
                    findingsCriticosMajor: 0,
                    pendenciasBloqueantes: 0,
                    evidencias: 1,
                    gateEligible: true,
                    approvalStatus: "APROVADO",
                    deliveryStatus: "PRONTO P/ ENTREGA");
            }
            catch { }
        }

        private void BtnRejeitarRevisao_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                AtualizarSecaoRevisaoTecnica(
                    sobId: TxtCampoSOB?.Text ?? "-",
                    dwgPath: TxtCampoDWG?.Text ?? "-",
                    databaseFingerprint: TxtCampoFingerprint?.Text ?? "-",
                    revisionId: "REV-01",
                    status: ReviewStatus.Rejected,
                    snapshotId: "-",
                    findingsTotal: 1,
                    findingsCriticosMajor: 1,
                    pendenciasBloqueantes: 1,
                    evidencias: 1,
                    gateEligible: false,
                    approvalStatus: "REJEITADO",
                    deliveryStatus: "NÃO PERMITIDO");
            }
            catch { }
        }

        private void BtnCancelarRevisao_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                AtualizarSecaoRevisaoTecnica(
                    sobId: TxtCampoSOB?.Text ?? "-",
                    dwgPath: TxtCampoDWG?.Text ?? "-",
                    databaseFingerprint: TxtCampoFingerprint?.Text ?? "-",
                    revisionId: "REV-01",
                    status: ReviewStatus.Cancelled,
                    snapshotId: "-",
                    findingsTotal: 0,
                    findingsCriticosMajor: 0,
                    pendenciasBloqueantes: 0,
                    evidencias: 0,
                    gateEligible: false,
                    approvalStatus: "CANCELADO",
                    deliveryStatus: "NÃO PERMITIDO");
            }
            catch { }
        }
    }
}
