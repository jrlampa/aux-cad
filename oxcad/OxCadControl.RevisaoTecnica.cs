using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Media;
using OxCad.Governance;

namespace OxCad
{
    public partial class OxCadControl
    {
        private TechnicalReview? _revisaoAtual;
        private ApprovalGateResult? _gateAtual;
        private bool _isReviewActionRunning = false;

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

                // Gate de Aprovação Autorizado pelo Domínio
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

                // Regra autoritativa: O botão APROVAR só fica ativo se o gate for elegível e a revisão estiver em andamento
                if (BtnAprovarRevisao != null)
                {
                    bool podeAprovar = gateEligible && status == ReviewStatus.InReview;
                    BtnAprovarRevisao.IsEnabled = podeAprovar;
                    BtnAprovarRevisao.Opacity = podeAprovar ? 1.0 : 0.45;
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

        /// <summary>
        /// Atualiza o painel de revisão a partir do payload JSON retornado pelo backend authoritative.
        /// </summary>
        private void AplicarResultadoRevisaoJson(string json, string sobIdFallback, string dwgFallback, string fingerprintFallback)
        {
            try
            {
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;
                bool success = root.TryGetProperty("success", out var succProp) && succProp.GetBoolean();

                if (!success)
                {
                    string erro = root.TryGetProperty("error", out var errProp) ? errProp.GetString() ?? "Operação não autorizada" : "Operação não autorizada";
                    MessageBox.Show($"Operação de revisão rejeitada pelo domínio:\n\n{erro}", "Revisão Técnica", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }

                bool hasReview = root.TryGetProperty("has_review", out var hrProp) ? hrProp.GetBoolean() : (root.TryGetProperty("review", out var rCheck) && rCheck.ValueKind != JsonValueKind.Null);

                if (!hasReview || !root.TryGetProperty("review", out var revProp) || revProp.ValueKind == JsonValueKind.Null)
                {
                    AtualizarSecaoRevisaoTecnica(
                        sobId: sobIdFallback,
                        dwgPath: dwgFallback,
                        databaseFingerprint: fingerprintFallback,
                        revisionId: "REV-01",
                        status: ReviewStatus.Draft,
                        snapshotId: "-",
                        findingsTotal: 0,
                        findingsCriticosMajor: 0,
                        pendenciasBloqueantes: 0,
                        evidencias: 0,
                        gateEligible: false,
                        approvalStatus: "NÃO INICIADO",
                        deliveryStatus: "NÃO GERADO");
                    return;
                }

                string revStatusStr = revProp.TryGetProperty("status", out var stElem) ? stElem.GetString() ?? "DRAFT" : "DRAFT";
                ReviewStatus status = revStatusStr.ToUpperInvariant() switch
                {
                    "IN_REVIEW" => ReviewStatus.InReview,
                    "CHANGES_REQUIRED" => ReviewStatus.ChangesRequired,
                    "APPROVED" => ReviewStatus.Approved,
                    "REJECTED" => ReviewStatus.Rejected,
                    "SUPERSEDED" => ReviewStatus.Superseded,
                    "CANCELLED" => ReviewStatus.Cancelled,
                    _ => ReviewStatus.Draft
                };

                string revision = revProp.TryGetProperty("revision_id", out var revElem) ? revElem.GetString() ?? "REV-01" : "REV-01";
                string? snapshot = revProp.TryGetProperty("snapshot_id", out var snapElem) && snapElem.ValueKind != JsonValueKind.Null ? snapElem.GetString() : "-";
                string sob = revProp.TryGetProperty("sob_id", out var sobElem) ? sobElem.GetString() ?? sobIdFallback : sobIdFallback;
                string dwg = revProp.TryGetProperty("dwg_path", out var dwgElem) ? dwgElem.GetString() ?? dwgFallback : dwgFallback;
                string fp = revProp.TryGetProperty("database_fingerprint", out var fpElem) ? fpElem.GetString() ?? fingerprintFallback : fingerprintFallback;

                int totalFindings = 0;
                int critMajor = 0;
                int pendenciasBloq = 0;
                int evidencias = 0;

                if (root.TryGetProperty("counts", out var countsProp) && countsProp.ValueKind == JsonValueKind.Object)
                {
                    totalFindings = countsProp.TryGetProperty("total_findings", out var tf) ? tf.GetInt32() : 0;
                    critMajor = countsProp.TryGetProperty("critical_major_findings", out var cm) ? cm.GetInt32() : 0;
                    pendenciasBloq = countsProp.TryGetProperty("blocking_pendings", out var bp) ? bp.GetInt32() : 0;
                    evidencias = countsProp.TryGetProperty("evidences", out var ev) ? ev.GetInt32() : 0;
                }

                bool gateEligible = false;
                if (root.TryGetProperty("gate", out var gateProp) && gateProp.ValueKind == JsonValueKind.Object)
                {
                    string gateStatus = gateProp.TryGetProperty("status", out var gs) ? gs.GetString() ?? "NOT_ELIGIBLE" : "NOT_ELIGIBLE";
                    gateEligible = string.Equals(gateStatus, "ELIGIBLE", StringComparison.OrdinalIgnoreCase);
                }

                string revId = revProp.TryGetProperty("review_id", out var idElem) ? idElem.GetString() ?? "REV-01" : "REV-01";
                string appStatus = status == ReviewStatus.Approved ? "APROVADO" : (status == ReviewStatus.InReview ? "EM ANÁLISE" : (status == ReviewStatus.ChangesRequired ? "ALTERAÇÕES REQUERIDAS" : (status == ReviewStatus.Rejected ? "REJEITADO" : "NÃO APROVADO")));
                string delivStatus = status == ReviewStatus.Approved ? "PRONTO P/ ENTREGA" : (status == ReviewStatus.InReview ? "EM ANÁLISE" : "NÃO PERMITIDO");

                _gateAtual = gateEligible
                    ? ApprovalGateResult.Eligible(revId)
                    : ApprovalGateResult.NotEligible(revId, new[] { "Gate não elegível" });

                string rootDir = WorkspaceService.ObterDiretorioRaizProjeto(dwg);
                _revisaoAtual = new TechnicalReview(
                    revId,
                    sob,
                    rootDir,
                    dwg,
                    fp,
                    revision,
                    snapshot,
                    DateTime.UtcNow,
                    "oxcad.palette",
                    status);

                AtualizarSecaoRevisaoTecnica(
                    sobId: sob,
                    dwgPath: dwg,
                    databaseFingerprint: fp,
                    revisionId: revision,
                    status: status,
                    snapshotId: snapshot ?? "-",
                    findingsTotal: totalFindings,
                    findingsCriticosMajor: critMajor,
                    pendenciasBloqueantes: pendenciasBloq,
                    evidencias: evidencias,
                    gateEligible: gateEligible,
                    approvalStatus: appStatus,
                    deliveryStatus: delivStatus);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Falha ao processar estado da revisão: {ex.Message}", "Revisão Técnica", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        /// <summary>
        /// Consulta assíncrona do status real da revisão técnica junto ao backend Python.
        /// </summary>
        public async Task AtualizarStatusRevisaoOperacionalAsync()
        {
            if (_isReviewActionRunning) return;
            try
            {
                string? dwg = _ultimoDwgFullPath ?? (TxtCampoDWG?.Text != "-" ? TxtCampoDWG?.Text : null);
                string? sob = _ultimoSobId ?? (TxtCampoSOB?.Text != "-" ? TxtCampoSOB?.Text : null);
                string? fp = _ultimoDwgIdentity ?? (TxtCampoFingerprint?.Text != "-" ? TxtCampoFingerprint?.Text : null);
                string rootDir = WorkspaceService.ObterDiretorioRaizProjeto(dwg);

                if (string.IsNullOrWhiteSpace(dwg) || string.IsNullOrWhiteSpace(sob) || sob == "-")
                {
                    return;
                }

                string json = await WorkspaceService.ExecutarComandoRevisaoAsync(
                    rootDir, dwg, sob, fp, "status");

                AplicarResultadoRevisaoJson(json, sob ?? "-", dwg ?? "-", fp ?? "-");
            }
            catch
            {
                // UI não bloqueante
            }
        }

        private async void BtnIniciarRevisao_Click(object sender, RoutedEventArgs e)
        {
            if (_isReviewActionRunning || _isActionRunning || _isUpdating) return;
            _isReviewActionRunning = true;
            try
            {
                string? dwg = _ultimoDwgFullPath ?? (TxtCampoDWG?.Text != "-" ? TxtCampoDWG?.Text : null);
                string? sob = _ultimoSobId ?? (TxtCampoSOB?.Text != "-" ? TxtCampoSOB?.Text : null);
                string? fp = _ultimoDwgIdentity ?? (TxtCampoFingerprint?.Text != "-" ? TxtCampoFingerprint?.Text : null);
                string rootDir = WorkspaceService.ObterDiretorioRaizProjeto(dwg);

                var param = new Dictionary<string, string>
                {
                    ["revision-id"] = TxtRevisaoId?.Text ?? "REV-01",
                    ["reviewer"] = "Operador OXCAD"
                };

                string json = await WorkspaceService.ExecutarComandoRevisaoAsync(
                    rootDir, dwg, sob, fp, "iniciar", param);

                AplicarResultadoRevisaoJson(json, sob ?? "-", dwg ?? "-", fp ?? "-");
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Falha ao iniciar revisão técnica: {ex.Message}", "Revisão Técnica", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
            finally
            {
                _isReviewActionRunning = false;
            }
        }

        private async void BtnRegistrarAchado_Click(object sender, RoutedEventArgs e)
        {
            if (_isReviewActionRunning || _isActionRunning || _isUpdating) return;
            _isReviewActionRunning = true;
            try
            {
                string? dwg = _ultimoDwgFullPath ?? (TxtCampoDWG?.Text != "-" ? TxtCampoDWG?.Text : null);
                string? sob = _ultimoSobId ?? (TxtCampoSOB?.Text != "-" ? TxtCampoSOB?.Text : null);
                string? fp = _ultimoDwgIdentity ?? (TxtCampoFingerprint?.Text != "-" ? TxtCampoFingerprint?.Text : null);
                string rootDir = WorkspaceService.ObterDiretorioRaizProjeto(dwg);

                var param = new Dictionary<string, string>
                {
                    ["category"] = "CRITERIO_TECNICO",
                    ["severity"] = "MAJOR",
                    ["description"] = "Achado técnico registrado via paleta OXCAD",
                    ["location"] = string.IsNullOrWhiteSpace(dwg) ? "Projeto DWG" : Path.GetFileName(dwg),
                    ["author"] = "Operador OXCAD",
                    ["creates-pending"] = ""
                };

                string json = await WorkspaceService.ExecutarComandoRevisaoAsync(
                    rootDir, dwg, sob, fp, "achado", param);

                AplicarResultadoRevisaoJson(json, sob ?? "-", dwg ?? "-", fp ?? "-");
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Falha ao registrar achado: {ex.Message}", "Revisão Técnica", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
            finally
            {
                _isReviewActionRunning = false;
            }
        }

        private async void BtnSolicitarAlteracoes_Click(object sender, RoutedEventArgs e)
        {
            if (_isReviewActionRunning || _isActionRunning || _isUpdating) return;
            _isReviewActionRunning = true;
            try
            {
                string? dwg = _ultimoDwgFullPath ?? (TxtCampoDWG?.Text != "-" ? TxtCampoDWG?.Text : null);
                string? sob = _ultimoSobId ?? (TxtCampoSOB?.Text != "-" ? TxtCampoSOB?.Text : null);
                string? fp = _ultimoDwgIdentity ?? (TxtCampoFingerprint?.Text != "-" ? TxtCampoFingerprint?.Text : null);
                string rootDir = WorkspaceService.ObterDiretorioRaizProjeto(dwg);

                var param = new Dictionary<string, string>
                {
                    ["actor"] = "Operador OXCAD",
                    ["reason"] = "Alterações técnicas solicitadas via paleta OXCAD"
                };

                string json = await WorkspaceService.ExecutarComandoRevisaoAsync(
                    rootDir, dwg, sob, fp, "solicitar-alteracoes", param);

                AplicarResultadoRevisaoJson(json, sob ?? "-", dwg ?? "-", fp ?? "-");
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Falha ao solicitar alterações: {ex.Message}", "Revisão Técnica", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
            finally
            {
                _isReviewActionRunning = false;
            }
        }

        private async void BtnAprovarRevisao_Click(object sender, RoutedEventArgs e)
        {
            if (_isReviewActionRunning || _isActionRunning || _isUpdating) return;
            _isReviewActionRunning = true;
            try
            {
                string? dwg = _ultimoDwgFullPath ?? (TxtCampoDWG?.Text != "-" ? TxtCampoDWG?.Text : null);
                string? sob = _ultimoSobId ?? (TxtCampoSOB?.Text != "-" ? TxtCampoSOB?.Text : null);
                string? fp = _ultimoDwgIdentity ?? (TxtCampoFingerprint?.Text != "-" ? TxtCampoFingerprint?.Text : null);
                string rootDir = WorkspaceService.ObterDiretorioRaizProjeto(dwg);

                var param = new Dictionary<string, string>
                {
                    ["approver"] = "Responsável Técnico OXCAD",
                    ["comments"] = "Aprovação técnica autorizada via paleta OXCAD"
                };

                string json = await WorkspaceService.ExecutarComandoRevisaoAsync(
                    rootDir, dwg, sob, fp, "aprovar", param);

                AplicarResultadoRevisaoJson(json, sob ?? "-", dwg ?? "-", fp ?? "-");
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Falha na aprovação da revisão: {ex.Message}", "Revisão Técnica", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
            finally
            {
                _isReviewActionRunning = false;
            }
        }

        private async void BtnRejeitarRevisao_Click(object sender, RoutedEventArgs e)
        {
            if (_isReviewActionRunning || _isActionRunning || _isUpdating) return;
            _isReviewActionRunning = true;
            try
            {
                string? dwg = _ultimoDwgFullPath ?? (TxtCampoDWG?.Text != "-" ? TxtCampoDWG?.Text : null);
                string? sob = _ultimoSobId ?? (TxtCampoSOB?.Text != "-" ? TxtCampoSOB?.Text : null);
                string? fp = _ultimoDwgIdentity ?? (TxtCampoFingerprint?.Text != "-" ? TxtCampoFingerprint?.Text : null);
                string rootDir = WorkspaceService.ObterDiretorioRaizProjeto(dwg);

                var param = new Dictionary<string, string>
                {
                    ["actor"] = "Operador OXCAD",
                    ["reason"] = "Revisão técnica rejeitada via paleta OXCAD"
                };

                string json = await WorkspaceService.ExecutarComandoRevisaoAsync(
                    rootDir, dwg, sob, fp, "rejeitar", param);

                AplicarResultadoRevisaoJson(json, sob ?? "-", dwg ?? "-", fp ?? "-");
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Falha ao rejeitar revisão técnica: {ex.Message}", "Revisão Técnica", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
            finally
            {
                _isReviewActionRunning = false;
            }
        }

        private async void BtnCancelarRevisao_Click(object sender, RoutedEventArgs e)
        {
            if (_isReviewActionRunning || _isActionRunning || _isUpdating) return;
            _isReviewActionRunning = true;
            try
            {
                string? dwg = _ultimoDwgFullPath ?? (TxtCampoDWG?.Text != "-" ? TxtCampoDWG?.Text : null);
                string? sob = _ultimoSobId ?? (TxtCampoSOB?.Text != "-" ? TxtCampoSOB?.Text : null);
                string? fp = _ultimoDwgIdentity ?? (TxtCampoFingerprint?.Text != "-" ? TxtCampoFingerprint?.Text : null);
                string rootDir = WorkspaceService.ObterDiretorioRaizProjeto(dwg);

                var param = new Dictionary<string, string>
                {
                    ["actor"] = "Operador OXCAD",
                    ["reason"] = "Revisão técnica cancelada pelo operador"
                };

                string json = await WorkspaceService.ExecutarComandoRevisaoAsync(
                    rootDir, dwg, sob, fp, "cancelar", param);

                AplicarResultadoRevisaoJson(json, sob ?? "-", dwg ?? "-", fp ?? "-");
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Falha ao cancelar revisão técnica: {ex.Message}", "Revisão Técnica", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
            finally
            {
                _isReviewActionRunning = false;
            }
        }
    }
}
