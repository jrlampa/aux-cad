using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Autodesk.AutoCAD.ApplicationServices;
using acApp = Autodesk.AutoCAD.ApplicationServices.Application;

namespace OxCad
{
    /// <summary>
    /// Lógica de interação para OxCadControl.xaml (OXCAD 0.3.0).
    /// Interface integrada de consulta operacional e despacho de ações via WorkspaceActionDispatcher.
    /// </summary>
    public partial class OxCadControl : UserControl
    {
        private bool _isUpdating = false;
        private bool _isActionRunning = false;
        private string? _ultimoDwgFullPath = null;

        // Gerenciamento de Tempo Operacional (OXCAD 0.5.0)
        private System.Windows.Threading.DispatcherTimer? _uiTimer;
        private OxCadTimeEntryDto? _currentTempo;
        private DateTime _sessaoInicioUtc = DateTime.UtcNow;
        private double _acumuladoBaseSegundos = 0;

        public OxCadControl()
        {
            InitializeComponent();
            ConfigurarTimerVisual();
            Loaded += OxCadControl_Loaded;
        }

        private void ConfigurarTimerVisual()
        {
            _uiTimer = new System.Windows.Threading.DispatcherTimer();
            _uiTimer.Interval = TimeSpan.FromSeconds(1);
            _uiTimer.Tick += (s, e) => AtualizarTempoVisual();
        }

        private void OxCadControl_Loaded(object sender, RoutedEventArgs e)
        {
            _ = AtualizarContextoAsync();
        }

        private void BtnAtualizar_Click(object sender, RoutedEventArgs e)
        {
            _ = AtualizarContextoAsync();
        }

        /// <summary>
        /// Ponto de entrada síncrono mantido para compatibilidade com PaletteHost.
        /// </summary>
        public void AtualizarContexto()
        {
            _ = AtualizarContextoAsync();
        }

        /// <summary>
        /// Handler de clique para os botões de ação de engenharia (CQT, Orçamento, CPFC, etc.).
        /// </summary>
        private async void BtnAcao_Click(object sender, RoutedEventArgs e)
        {
            if (sender is Button btn && btn.Tag is string acao)
            {
                await ExecutarAcaoEngenhariaAsync(acao);
            }
        }

        /// <summary>
        /// Handler de clique para abrir um artefato existente da lista.
        /// </summary>
        private async void BtnAbrirItem_Click(object sender, RoutedEventArgs e)
        {
            if (sender is Button btn && btn.Tag is string caminho && !string.IsNullOrWhiteSpace(caminho))
            {
                await ExecutarAberturaArtefatoAsync(caminho);
            }
        }

        /// <summary>
        /// Dispara o módulo especialista através do WorkspaceActionDispatcher com prevenção de concorrência.
        /// </summary>
        private async Task ExecutarAcaoEngenhariaAsync(string acao)
        {
            if (_isActionRunning || _isUpdating)
                return;

            _isActionRunning = true;
            HabilitarBotoesAcao(false);

            try
            {
                TxtAcaoEstado.Text = "Executando...";
                TxtAcaoEstado.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97)); // Laranja
                TxtAcaoMensagem.Text = $"Disparando módulo {acao.ToUpper()}...";

                var resultado = await WorkspaceService.ExecutarAcaoAsync(acao, _ultimoDwgFullPath);

                TxtAcaoEstado.Text = resultado.Estado;
                TxtAcaoMensagem.Text = resultado.Mensagem;

                if (resultado.Sucesso)
                {
                    TxtAcaoEstado.Foreground = new SolidColorBrush(Color.FromRgb(82, 183, 136)); // Verde
                }
                else if (resultado.Estado == "Requer especificação")
                {
                    TxtAcaoEstado.Foreground = new SolidColorBrush(Color.FromRgb(247, 127, 0)); // Laranja/Aviso
                }
                else
                {
                    TxtAcaoEstado.Foreground = new SolidColorBrush(Color.FromRgb(231, 111, 81)); // Coral/Erro
                }

                // Atualiza o contexto pós-execução para refletir novos artefatos gerados
                await AtualizarContextoAsync();
            }
            catch (Exception ex)
            {
                TxtAcaoEstado.Text = "Falhou";
                TxtAcaoEstado.Foreground = new SolidColorBrush(Color.FromRgb(231, 111, 81));
                TxtAcaoMensagem.Text = ex.Message;
            }
            finally
            {
                _isActionRunning = false;
                HabilitarBotoesAcao(true);
            }
        }

        /// <summary>
        /// Abre o arquivo físico associado a um artefato.
        /// </summary>
        private async Task ExecutarAberturaArtefatoAsync(string caminho)
        {
            if (_isActionRunning)
                return;

            try
            {
                TxtAcaoEstado.Text = "Abrindo...";
                TxtAcaoEstado.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
                TxtAcaoMensagem.Text = $"Abrindo artefato: {Path.GetFileName(caminho)}...";

                var resultado = await WorkspaceService.ExecutarAcaoAsync("abrir", _ultimoDwgFullPath, caminho);

                TxtAcaoEstado.Text = resultado.Estado;
                TxtAcaoMensagem.Text = resultado.Mensagem;
                TxtAcaoEstado.Foreground = resultado.Sucesso 
                    ? new SolidColorBrush(Color.FromRgb(82, 183, 136)) 
                    : new SolidColorBrush(Color.FromRgb(231, 111, 81));
            }
            catch (Exception ex)
            {
                TxtAcaoEstado.Text = "Falhou";
                TxtAcaoEstado.Foreground = new SolidColorBrush(Color.FromRgb(231, 111, 81));
                TxtAcaoMensagem.Text = ex.Message;
            }
        }

        private void HabilitarBotoesAcao(bool habilitado)
        {
            BtnCqt.IsEnabled = habilitado;
            BtnOrcamento.IsEnabled = habilitado;
            BtnCpfc.IsEnabled = habilitado;
            BtnAmbiental.IsEnabled = habilitado;
            BtnPrancha.IsEnabled = habilitado;
            BtnSob.IsEnabled = habilitado;
        }

        /// <summary>
        /// Consulta assíncrona do contexto operacional com controle de concorrência.
        /// </summary>
        public async Task AtualizarContextoAsync()
        {
            if (_isUpdating)
                return;

            _isUpdating = true;

            try
            {
                BtnAtualizar.IsEnabled = false;
                BtnAtualizar.Content = "⏳ Consultando...";

                Document? doc = null;
                try
                {
                    doc = acApp.DocumentManager.MdiActiveDocument;
                }
                catch
                {
                    // Ambiente sem ApplicationServices ativo
                }

                if (doc == null || doc.Database == null)
                {
                    _ultimoDwgFullPath = null;
                    ExibirEstadoSemDocumento();
                    return;
                }

                string? dwgFilename = null;
                try
                {
                    dwgFilename = doc.Database.Filename;
                }
                catch
                {
                    dwgFilename = null;
                }

                _ultimoDwgFullPath = dwgFilename;

                if (string.IsNullOrWhiteSpace(dwgFilename) || !File.Exists(dwgFilename))
                {
                    ExibirEstadoDesenhoNaoSalvo();
                    return;
                }

                OxCadWorkspaceContext contexto = await WorkspaceService.ConsultarContextoAsync(dwgFilename);

                AplicarContextoNaInterface(contexto);
            }
            catch (Exception ex)
            {
                TxtStatus.Text = $"Falha ao atualizar: {ex.Message}";
                TxtStatus.Foreground = new SolidColorBrush(Color.FromRgb(231, 111, 81));
            }
            finally
            {
                _isUpdating = false;
                BtnAtualizar.IsEnabled = true;
                BtnAtualizar.Content = "🔄 Atualizar Contexto";
            }
        }

        /// <summary>
        /// Handler de clique para a ação principal de tempo (Iniciar / Pausar / Retomar / Reabrir).
        /// </summary>
        private async void BtnTempoAcaoPrincipal_Click(object sender, RoutedEventArgs e)
        {
            if (sender is Button btn && btn.Tag is string acao && !string.IsNullOrWhiteSpace(acao))
            {
                await ExecutarAcaoTempoAsync(acao);
            }
        }

        /// <summary>
        /// Handler de clique para concluir o apontamento com confirmação prévia.
        /// </summary>
        private async void BtnTempoConcluir_Click(object sender, RoutedEventArgs e)
        {
            if (_isActionRunning || _isUpdating) return;

            string tempoFormatado = TxtTempoFormatado.Text;
            var confirm = MessageBox.Show(
                $"Deseja concluir o apontamento operacional deste projeto?\n\nTempo trabalhado: {tempoFormatado}",
                "Concluir Apontamento",
                MessageBoxButton.YesNo,
                MessageBoxImage.Question
            );

            if (confirm == MessageBoxResult.Yes)
            {
                await ExecutarAcaoTempoAsync("tempo_concluir");
            }
        }

        /// <summary>
        /// Executa o comando de tempo via WorkspaceService com controle de concorrência.
        /// </summary>
        private async Task ExecutarAcaoTempoAsync(string acaoTempo)
        {
            if (_isActionRunning || _isUpdating) return;

            _isActionRunning = true;
            HabilitarBotoesAcao(false);
            BtnTempoAcaoPrincipal.IsEnabled = false;
            BtnTempoConcluir.IsEnabled = false;

            try
            {
                TxtAcaoEstado.Text = "Executando...";
                TxtAcaoEstado.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
                TxtAcaoMensagem.Text = $"Atualizando apontamento de tempo ({acaoTempo})...";

                var resultado = await WorkspaceService.ControlarTempoAsync(acaoTempo, _ultimoDwgFullPath);

                TxtAcaoEstado.Text = resultado.Estado;
                TxtAcaoMensagem.Text = resultado.Mensagem;
                TxtAcaoEstado.Foreground = resultado.Sucesso
                    ? new SolidColorBrush(Color.FromRgb(82, 183, 136))
                    : new SolidColorBrush(Color.FromRgb(231, 111, 81));

                await AtualizarContextoAsync();
            }
            catch (Exception ex)
            {
                TxtAcaoEstado.Text = "Falhou";
                TxtAcaoEstado.Foreground = new SolidColorBrush(Color.FromRgb(231, 111, 81));
                TxtAcaoMensagem.Text = ex.Message;
            }
            finally
            {
                _isActionRunning = false;
                HabilitarBotoesAcao(true);
            }
        }

        private int _heartbeatCounter = 0;
        private bool _isHeartbeatRunning = false;

        private void AtualizarTempoVisual()
        {
            if (_currentTempo != null && _currentTempo.Estado == "EmExecucao")
            {
                double decorrido = _acumuladoBaseSegundos + (DateTime.UtcNow - _sessaoInicioUtc).TotalSeconds;
                TxtTempoFormatado.Text = FormatarSegundos(decorrido);

                // Heartbeat defensivo a cada 60s em background sem bloquear a UI e sem sobreposição
                _heartbeatCounter++;
                if (_heartbeatCounter >= 60)
                {
                    _heartbeatCounter = 0;
                    if (!_isHeartbeatRunning && !string.IsNullOrWhiteSpace(_ultimoDwgFullPath))
                    {
                        _isHeartbeatRunning = true;
                        _ = Task.Run(async () =>
                        {
                            try
                            {
                                await WorkspaceService.ControlarTempoAsync("tempo_heartbeat", _ultimoDwgFullPath);
                            }
                            catch
                            {
                                // Falhas transitórias no heartbeat não afetam a paleta
                            }
                            finally
                            {
                                _isHeartbeatRunning = false;
                            }
                        });
                    }
                }
            }
        }

        private static string FormatarSegundos(double segundosTotais)
        {
            int sec = Math.Max(0, (int)Math.Round(segundosTotais));
            int horas = sec / 3600;
            int resto = sec % 3600;
            int minutos = resto / 60;
            int segundos = resto % 60;
            return $"{horas:D2}:{minutos:D2}:{segundos:D2}";
        }

        private void AplicarTempoNaInterface(OxCadTimeEntryDto? tempo)
        {
            _currentTempo = tempo;

            if (tempo == null || tempo.Estado == "NaoIniciado")
            {
                _uiTimer?.Stop();
                TxtTempoEstado.Text = "Não iniciado";
                TxtTempoEstado.Foreground = new SolidColorBrush(Color.FromRgb(158, 158, 176));
                TxtTempoInicio.Text = "-";
                TxtTempoFormatado.Text = "00:00:00";
                TxtTempoFormatado.Foreground = new SolidColorBrush(Color.FromRgb(158, 158, 176));
                PainelTempoFim.Visibility = Visibility.Collapsed;

                BtnTempoAcaoPrincipal.Content = "▶ Iniciar";
                BtnTempoAcaoPrincipal.Tag = "tempo_iniciar";
                BtnTempoAcaoPrincipal.Background = new SolidColorBrush(Color.FromRgb(42, 75, 60));
                BtnTempoAcaoPrincipal.IsEnabled = true;
                BtnTempoConcluir.IsEnabled = false;
                return;
            }

            if (tempo.Estado == "EmExecucao")
            {
                TxtTempoEstado.Text = "● Em execução";
                TxtTempoEstado.Foreground = new SolidColorBrush(Color.FromRgb(82, 183, 136));
                TxtTempoInicio.Text = tempo.InicioFormatado;
                TxtTempoFormatado.Foreground = new SolidColorBrush(Color.FromRgb(82, 183, 136));
                PainelTempoFim.Visibility = Visibility.Collapsed;

                BtnTempoAcaoPrincipal.Content = "⏸ Pausar";
                BtnTempoAcaoPrincipal.Tag = "tempo_pausar";
                BtnTempoAcaoPrincipal.Background = new SolidColorBrush(Color.FromRgb(244, 162, 97));
                BtnTempoAcaoPrincipal.IsEnabled = true;
                BtnTempoConcluir.IsEnabled = true;

                if (!string.IsNullOrWhiteSpace(tempo.SessaoAtualInicio) && DateTime.TryParse(tempo.SessaoAtualInicio, out DateTime dtInicio))
                {
                    _sessaoInicioUtc = dtInicio.ToUniversalTime();
                }
                else
                {
                    _sessaoInicioUtc = DateTime.UtcNow;
                }

                _acumuladoBaseSegundos = tempo.TempoAcumuladoSegundos;
                _heartbeatCounter = 0;
                _uiTimer?.Start();
                AtualizarTempoVisual();
                return;
            }

            if (tempo.Estado == "Interrompido")
            {
                _uiTimer?.Stop();
                TxtTempoEstado.Text = "⚠ Sessão interrompida";
                TxtTempoEstado.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
                TxtTempoInicio.Text = tempo.InicioFormatado;
                TxtTempoFormatado.Text = tempo.TempoFormatado;
                TxtTempoFormatado.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
                PainelTempoFim.Visibility = Visibility.Collapsed;

                BtnTempoAcaoPrincipal.Content = "▶ Retomar";
                BtnTempoAcaoPrincipal.Tag = "tempo_retomar";
                BtnTempoAcaoPrincipal.Background = new SolidColorBrush(Color.FromRgb(42, 75, 60));
                BtnTempoAcaoPrincipal.IsEnabled = true;
                BtnTempoConcluir.IsEnabled = true;
                return;
            }

            if (tempo.Estado == "Pausado")
            {
                _uiTimer?.Stop();
                TxtTempoEstado.Text = "⏸ Pausado";
                TxtTempoEstado.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
                TxtTempoInicio.Text = tempo.InicioFormatado;
                TxtTempoFormatado.Text = tempo.TempoFormatado;
                TxtTempoFormatado.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
                PainelTempoFim.Visibility = Visibility.Collapsed;

                BtnTempoAcaoPrincipal.Content = "▶ Retomar";
                BtnTempoAcaoPrincipal.Tag = "tempo_retomar";
                BtnTempoAcaoPrincipal.Background = new SolidColorBrush(Color.FromRgb(42, 75, 60));
                BtnTempoAcaoPrincipal.IsEnabled = true;
                BtnTempoConcluir.IsEnabled = true;
                return;
            }

            if (tempo.Estado == "Concluido")
            {
                _uiTimer?.Stop();
                TxtTempoEstado.Text = "✓ Concluído";
                TxtTempoEstado.Foreground = new SolidColorBrush(Color.FromRgb(78, 168, 222));
                TxtTempoInicio.Text = tempo.InicioFormatado;
                TxtTempoFim.Text = tempo.FimFormatado;
                TxtTempoFormatado.Text = tempo.TempoFormatado;
                TxtTempoFormatado.Foreground = new SolidColorBrush(Color.FromRgb(78, 168, 222));
                PainelTempoFim.Visibility = Visibility.Visible;

                BtnTempoAcaoPrincipal.Content = "Reabrir";
                BtnTempoAcaoPrincipal.Tag = "tempo_reabrir";
                BtnTempoAcaoPrincipal.Background = new SolidColorBrush(Color.FromRgb(58, 58, 76));
                BtnTempoAcaoPrincipal.IsEnabled = true;
                BtnTempoConcluir.IsEnabled = false;
            }
        }

        private void ExibirEstadoSemDocumento()
        {
            TxtStatus.Text = "Nenhum documento ativo no AutoCAD.";
            TxtStatus.Foreground = new SolidColorBrush(Color.FromRgb(247, 127, 0));
            TxtSob.Text = "-";
            TxtDwg.Text = "-";
            TxtPasta.Text = "-";
            TxtMunicipio.Text = "-";
            TxtBairro.Text = "-";
            TxtEndereco.Text = "-";
            CardInconsistencia.Visibility = Visibility.Collapsed;
            ListaArtefatos.ItemsSource = null;
            AplicarTempoNaInterface(null);
            BtnTempoAcaoPrincipal.IsEnabled = false;
            BtnTempoConcluir.IsEnabled = false;
        }

        private void ExibirEstadoDesenhoNaoSalvo()
        {
            TxtStatus.Text = "Desenho ainda não salvo.";
            TxtStatus.Foreground = new SolidColorBrush(Color.FromRgb(231, 111, 81));
            TxtSob.Text = "-";
            TxtDwg.Text = "Desenho ainda não salvo.";
            TxtPasta.Text = "-";
            TxtMunicipio.Text = "-";
            TxtBairro.Text = "-";
            TxtEndereco.Text = "-";
            CardInconsistencia.Visibility = Visibility.Collapsed;
            ListaArtefatos.ItemsSource = null;
            AplicarTempoNaInterface(null);
            BtnTempoAcaoPrincipal.IsEnabled = false;
            BtnTempoConcluir.IsEnabled = false;
        }

        private void AplicarContextoNaInterface(OxCadWorkspaceContext contexto)
        {
            TxtStatus.Text = contexto.Status;
            TxtSob.Text = contexto.SobId;
            TxtDwg.Text = contexto.DwgPrincipal;
            TxtPasta.Text = contexto.RootDir;
            TxtMunicipio.Text = contexto.Municipio;
            TxtBairro.Text = contexto.Bairro;
            TxtEndereco.Text = contexto.Endereco;

            if (contexto.Inconsistencia)
            {
                CardInconsistencia.Visibility = Visibility.Visible;
                TxtInconsistenciaMsg.Text = contexto.MensagemInconsistencia;
                TxtStatus.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
            }
            else
            {
                CardInconsistencia.Visibility = Visibility.Collapsed;
                if (contexto.SobId != "-" && contexto.SobId != "PROJETO")
                {
                    TxtStatus.Foreground = new SolidColorBrush(Color.FromRgb(82, 183, 136));
                }
                else
                {
                    TxtStatus.Foreground = new SolidColorBrush(Color.FromRgb(247, 127, 0));
                }
            }

            ListaArtefatos.ItemsSource = contexto.Artefatos;
            AplicarTempoNaInterface(contexto.Tempo);
        }
    }
}
