using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Media;
using OxCad.Integration;

namespace OxCad
{
    public sealed class IntegrationUiItem
    {
        public string DisplayName { get; }
        public string StatusText { get; }
        public Brush StatusBackground { get; }
        public Brush StatusForeground { get; }

        public IntegrationUiItem(string displayName, string statusText, Brush background, Brush foreground)
        {
            DisplayName = displayName;
            StatusText = statusText;
            StatusBackground = background;
            StatusForeground = foreground;
        }
    }

    public partial class OxCadControl
    {
        private bool _universalizacaoConsultaEmAndamento;

        private void InicializarSecaoIntegracoes()
        {
            try
            {
                var registry = IntegrationRegistry.CreateDefault();
                var items = new List<IntegrationUiItem>();

                var brushConfigured = new SolidColorBrush(Color.FromRgb(82, 183, 136));     // Verde
                var brushNotConfigured = new SolidColorBrush(Color.FromRgb(160, 160, 176)); // Cinza claro
                var bgConfigured = new SolidColorBrush(Color.FromRgb(26, 46, 38));          // Verde escuro
                var bgNotConfigured = new SolidColorBrush(Color.FromRgb(37, 37, 50));       // Cinza escuro

                // Selecionar os provedores requeridos pelo P2.4 na ordem canônica da especificação
                var idsDesejados = new[]
                {
                    "microsoft.graph",
                    "microsoft.entra",
                    "sharepoint",
                    "onedrive",
                    "sap",
                    "salesforce",
                    "rest",
                    "soap"
                };

                foreach (var id in idsDesejados)
                {
                    var provider = registry.Get(id);
                    if (provider == null)
                        continue;

                    var desc = provider.Descriptor;
                    string statusText = desc.ConfigurationStatus == ConfigurationStatus.Configured ? "Disponível" : "Não configurado";
                    var fg = desc.ConfigurationStatus == ConfigurationStatus.Configured ? brushConfigured : brushNotConfigured;
                    var bg = desc.ConfigurationStatus == ConfigurationStatus.Configured ? bgConfigured : bgNotConfigured;

                    items.Add(new IntegrationUiItem(desc.DisplayName, statusText, bg, fg));
                }

                if (ListaIntegracoes != null)
                {
                    ListaIntegracoes.ItemsSource = items;
                }
            }
            catch
            {
                // UI não bloqueante: falhas visuais não afetam o Core do OXCAD
            }
        }

        private void ChkConsultaIndependente_Changed(object sender, RoutedEventArgs e)
        {
            bool enabled = ChkConsultaIndependente.IsChecked == true;
            if (TxtSobConsultaIndependente != null)
            {
                TxtSobConsultaIndependente.IsEnabled = enabled;
                if (!enabled)
                    TxtSobConsultaIndependente.Clear();
            }
            if (LblSobConsultaIndependente != null)
                LblSobConsultaIndependente.Visibility = enabled
                    ? System.Windows.Visibility.Visible
                    : System.Windows.Visibility.Collapsed;
        }

        private async void BtnConsultarUniversalizacao_Click(
            object sender, RoutedEventArgs e)
        {
            if (_universalizacaoConsultaEmAndamento)
                return;

            string? activeGroup = GetSelectedGroup(ComboGrupoReferencia);
            string? queryGroup = GetSelectedGroup(ComboGrupoConsulta);
            bool independentQuery = ChkConsultaIndependente.IsChecked == true;
            if (activeGroup == null || queryGroup == null)
            {
                TxtUniversalizacaoResultado.Text =
                    "Selecione explicitamente os grupos de referência e consulta.";
                return;
            }

            OxCadVerifiedDwgContext source;
            try
            {
                source = CapturarContextoVerificado();
            }
            catch (InvalidOperationException)
            {
                TxtUniversalizacaoResultado.Text =
                    "Consulta bloqueada: não há contexto DWG/SOB verificado.";
                return;
            }

            string querySob;
            if (independentQuery)
            {
                querySob = TxtSobConsultaIndependente.Text.Trim();
                if (string.IsNullOrWhiteSpace(querySob))
                {
                    TxtUniversalizacaoResultado.Text =
                        "Informe a SOB explícita da consulta independente.";
                    return;
                }
            }
            else
            {
                if (!string.Equals(activeGroup, queryGroup, StringComparison.Ordinal))
                {
                    TxtUniversalizacaoResultado.Text =
                        "Grupo divergente exige consulta independente explícita.";
                    return;
                }
                querySob = source.SobId;
            }

            var query = new WorkOrderQuery(queryGroup, querySob);
            if (!query.IsValid)
            {
                TxtUniversalizacaoResultado.Text =
                    "Grupo ou SOB da consulta inválido.";
                return;
            }

            string correlationId = Guid.NewGuid().ToString("N");
            string executionId = Guid.NewGuid().ToString("N");
            var verifiedContext = new OxCadVerifiedDwgContext(
                source.SobId, source.DwgPath, source.DwgIdentity,
                source.ContextGeneration, executionId, correlationId);

            _universalizacaoConsultaEmAndamento = true;
            BtnConsultarUniversalizacao.IsEnabled = false;
            TxtUniversalizacaoResultado.Text = "Consultando Universalização...";
            TxtUniversalizacaoDados.Text = string.Empty;
            try
            {
                IntegrationResult<UniversalizacaoQueryData> result =
                    await UniversalizacaoOxCadCaller.ConsultarAsync(
                        verifiedContext, activeGroup, query, independentQuery);

                if (!_contextRefreshGate.IsCurrentGeneration(
                        source.ContextGeneration))
                {
                    TxtUniversalizacaoResultado.Text =
                        "Resultado descartado: o contexto DWG mudou durante a consulta.";
                    return;
                }

                TxtUniversalizacaoResultado.Text = result.IsSuccess
                    ? $"Consulta concluída: {result.Status} · HTTP {result.Data?.HttpStatus}"
                    : $"Consulta não concluída: {result.Status} ({result.ErrorCode})";
                if (result.IsSuccess && result.Data != null)
                    TxtUniversalizacaoDados.Text = FormatUniversalizacaoResult(
                        result.Data);
            }
            catch
            {
                TxtUniversalizacaoResultado.Text =
                    "Consulta não concluída: erro interno sanitizado.";
                TxtUniversalizacaoDados.Text = string.Empty;
            }
            finally
            {
                _universalizacaoConsultaEmAndamento = false;
                BtnConsultarUniversalizacao.IsEnabled = true;
            }
        }

        private static string? GetSelectedGroup(System.Windows.Controls.ComboBox combo)
        {
            return (combo.SelectedItem as System.Windows.Controls.ComboBoxItem)
                ?.Content as string;
        }

        private static string FormatUniversalizacaoResult(
            UniversalizacaoQueryData data)
        {
            static string Value(string? value) => value ?? "(null)";
            UniversalizacaoProjectData project = data.ProjectData!;
            UniversalizacaoOrderStatus state = data.OrderStatus!;
            UniversalizacaoTransportData transport = data.Transport!;
            return string.Join(Environment.NewLine, new[]
            {
                $"Identidade: {data.RequestedGrupo}/{data.RequestedSob}",
                $"Nome: {Value(project.Nome)}",
                $"Endereço: {Value(project.Endereco)}",
                $"Bairro: {Value(project.Bairro)}",
                $"Município: {Value(project.Municipio)}",
                $"Pólo Técnico/BASE: {Value(project.PoloTecnico)}",
                $"Tipo de Serviço: {Value(project.TipoServico)}",
                $"Notas de Observação: {Value(project.NotasObservacao)}",
                $"Referência: {Value(project.Referencia)}",
                $"Etapa/Estado/Status: {Value(state.EtapaOrdemProj)} / " +
                    $"{Value(state.EstadoOrdemProj)} / {Value(state.StatusOrdem)}",
                $"HTTP {data.HttpStatus}; {transport.Method} {transport.Route}; " +
                    $"{transport.NtlmVersion}; SSPI={transport.Sspi}; " +
                    $"correlation={data.CorrelationId}; execution={data.ExecutionId}",
            });
        }
    }
}
