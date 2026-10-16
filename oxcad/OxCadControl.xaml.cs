using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Autodesk.AutoCAD.ApplicationServices;
using MapaCadPaleta;
using AcDb = Autodesk.AutoCAD.DatabaseServices;
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
        private readonly ContextRefreshGate _contextRefreshGate = new ContextRefreshGate();
        private readonly object _refreshScheduleLock = new object();
        private bool _isRefreshScheduled = false;
        private string? _nativeCommandExecutionId = null;
        private string? _ultimoDwgFullPath = null;
        private string? _ultimoSobId = null;
        private string? _ultimoDwgIdentity = null;
        private bool _projectScopeResolved = false;

        // Gerenciamento de Tempo Operacional (OXCAD 0.5.0)
        private System.Windows.Threading.DispatcherTimer? _uiTimer;
        private OxCadTimeEntryDto? _currentTempo;
        private DateTime _sessaoInicioUtc = DateTime.UtcNow;
        private double _acumuladoBaseSegundos = 0;

        public OxCadControl()
        {
            InitializeComponent();
            CarregarIconeHeader();
            ConfigurarTimerVisual();
            InicializarSecaoIntegracoes();
            InicializarSecaoValidacaoCampo();
            InicializarSecaoRevisaoTecnica();
            Loaded += OxCadControl_Loaded;
            Unloaded += OxCadControl_Unloaded;
        }

        private void CarregarIconeHeader()
        {
            try
            {
                string dirDll = System.IO.Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location) ?? "";
                string caminhoPng = System.IO.Path.Combine(dirDll, "assets", "oxcad_64.png");
                if (!System.IO.File.Exists(caminhoPng))
                {
                    string raizProj = WorkspaceService.ObterDiretorioRaizProjeto();
                    caminhoPng = System.IO.Path.Combine(raizProj, "oxcad", "assets", "oxcad_64.png");
                }
                if (System.IO.File.Exists(caminhoPng))
                {
                    var bmp = new System.Windows.Media.Imaging.BitmapImage();
                    bmp.BeginInit();
                    bmp.UriSource = new Uri(caminhoPng, UriKind.Absolute);
                    bmp.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad;
                    bmp.EndInit();
                    ImgLogoHeader.Source = bmp;
                }
            }
            catch
            {
                // Fallback gracioso: imagem não é exibida se indisponível
            }
        }

        private void ConfigurarTimerVisual()
        {
            _uiTimer = new System.Windows.Threading.DispatcherTimer();
            _uiTimer.Interval = TimeSpan.FromSeconds(1);
            _uiTimer.Tick += (s, e) => AtualizarTempoVisual();
        }

        private void OxCadControl_Loaded(object sender, RoutedEventArgs e)
        {
            OxCadExecutionRegistry.ExecutionChanged -= OnExecutionChanged;
            OxCadExecutionRegistry.ExecutionChanged += OnExecutionChanged;
            _ = AtualizarContextoAsync();
        }

        private void OxCadControl_Unloaded(object sender, RoutedEventArgs e)
        {
            OxCadExecutionRegistry.ExecutionChanged -= OnExecutionChanged;
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

        public void NotificarDocumentoAtivoAlterado()
        {
            ExecutarNaThreadUi(() => _ = AtualizarContextoAsync());
        }

        public void NotificarDocumentoFechando(Document? document)
        {
            ExecutarNaThreadUi(() =>
            {
                if (document == null)
                {
                    _ = AtualizarContextoAsync();
                    return;
                }

                if (!_contextRefreshGate.IsCurrentDocument(document))
                    return;

                _contextRefreshGate.Invalidate();
                _isUpdating = false;
                InvalidarContextoVisual("Documento sendo fechado...");
                BtnAtualizar.IsEnabled = true;
                BtnAtualizar.Content = "🔄 Atualizar Contexto";
            });
        }

        public void NotificarDocumentoSalvo(Document document)
        {
            ExecutarNaThreadUi(() =>
            {
                if (ReferenceEquals(document, acApp.DocumentManager.MdiActiveDocument))
                    _ = AtualizarContextoAsync();
            });
        }

        private void ExecutarNaThreadUi(Action action)
        {
            if (Dispatcher.CheckAccess())
                action();
            else
                Dispatcher.BeginInvoke(action);
        }

        private void AgendarAtualizacaoContextoAssincrona()
        {
            lock (_refreshScheduleLock)
            {
                if (_isRefreshScheduled)
                    return;
                _isRefreshScheduled = true;
            }

            Dispatcher.BeginInvoke(
                System.Windows.Threading.DispatcherPriority.Background,
                new Action(() =>
                {
                    lock (_refreshScheduleLock)
                    {
                        _isRefreshScheduled = false;
                    }
                    _ = AtualizarContextoAsync();
                }));
        }

        private void OnExecutionChanged(object? sender, OxCadExecutionChangedEventArgs eventArgs)
        {
            OxCadExecutionSnapshot execution = eventArgs.Execution;
            if (!string.Equals(execution.Origin, "oxcad.palette", StringComparison.Ordinal))
                return;

            ExecutarNaThreadUi(() =>
            {
                if (string.Equals(
                        execution.ExecutionId,
                        _nativeCommandExecutionId,
                        StringComparison.Ordinal) &&
                    execution.FinishedAt.HasValue)
                {
                    _nativeCommandExecutionId = null;
                    _isActionRunning = false;
                    HabilitarBotoesAcao(true);
                }

                if (execution.ContextGeneration != _contextRefreshGate.CurrentGeneration)
                    return;

                if (!string.IsNullOrWhiteSpace(execution.DwgIdentity) &&
                    !string.Equals(
                        execution.DwgIdentity,
                        _ultimoDwgIdentity,
                        StringComparison.OrdinalIgnoreCase))
                    return;

                TxtAcaoEstado.Text = execution.StateText;
                TxtAcaoEstado.Foreground = execution.State switch
                {
                    OxCadExecutionState.Concluido => new SolidColorBrush(Color.FromRgb(82, 183, 136)),
                    OxCadExecutionState.Falhou => new SolidColorBrush(Color.FromRgb(231, 111, 81)),
                    OxCadExecutionState.Cancelado => new SolidColorBrush(Color.FromRgb(247, 127, 0)),
                    _ => new SolidColorBrush(Color.FromRgb(244, 162, 97))
                };
                TxtAcaoMensagem.Text = execution.FinishedAt.HasValue
                    ? $"{execution.Message} ({FormatarDuracaoExecucao(execution.DurationMs)})"
                    : execution.Message;
            });
        }

        private OxCadExecutionRecord IniciarExecucaoPaleta(
            string acao,
            Document? document = null)
        {
            string correlationId = Guid.NewGuid().ToString("N");
            string executionId;
            do
            {
                executionId = Guid.NewGuid().ToString("N");
            }
            while (string.Equals(executionId, correlationId, StringComparison.OrdinalIgnoreCase));

            string? dwgPath = _ultimoDwgFullPath;
            string? sobId = _ultimoSobId;
            string? dwgIdentity = _ultimoDwgIdentity;
            if (document != null)
            {
                dwgPath = string.IsNullOrWhiteSpace(document.Database.Filename)
                    ? null
                    : document.Database.Filename;
                dwgIdentity = document.Database.FingerprintGuid;
                if (!string.Equals(dwgIdentity, _ultimoDwgIdentity, StringComparison.OrdinalIgnoreCase))
                    sobId = null;
            }

            string? projectRoot = string.IsNullOrWhiteSpace(dwgPath)
                ? null
                : Path.GetDirectoryName(dwgPath);
            OxCadExecutionRecord execution = OxCadExecutionRegistry.Iniciar(
                executionId,
                correlationId,
                sobId,
                dwgPath,
                dwgIdentity,
                acao,
                "oxcad.palette",
                projectRoot,
                _contextRefreshGate.CurrentGeneration);
            OxCadExecutionRegistry.Transicionar(
                execution,
                OxCadExecutionState.Executando,
                $"Executando {acao}.");
            return execution;
        }

        private static string FormatarDuracaoExecucao(double durationMs)
        {
            TimeSpan duration = TimeSpan.FromMilliseconds(Math.Max(0, durationMs));
            return duration.TotalHours >= 1
                ? $"{(int)duration.TotalHours:00}:{duration.Minutes:00}:{duration.Seconds:00}"
                : $"{duration.Minutes:00}:{duration.Seconds:00}";
        }

        private static void FinalizarExecucaoPaleta(
            OxCadExecutionRecord execution,
            OxCadActionResult? result,
            Exception? exception = null)
        {
            bool sucesso = exception == null && result?.Sucesso == true &&
                result.Estado != "Requer especificação" && result.Estado != "Falhou";
            OxCadExecutionRegistry.Transicionar(
                execution,
                sucesso ? OxCadExecutionState.Concluido : OxCadExecutionState.Falhou,
                exception?.Message ?? result?.Mensagem ?? "Execução falhou.",
                exception?.ToString() ?? result?.Erro,
                result?.Pid);
        }

        private bool ContextoDwgAtivoCoerente(bool requireProjectScope)
        {
            try
            {
                Document? activeDocument = acApp.DocumentManager.MdiActiveDocument;
                if (activeDocument == null || !_contextRefreshGate.IsCurrentDocument(activeDocument))
                    return false;
                if (!requireProjectScope)
                    return true;

                string identity = activeDocument.Database.FingerprintGuid;
                return _projectScopeResolved &&
                       string.Equals(identity, _ultimoDwgIdentity, StringComparison.OrdinalIgnoreCase);
            }
            catch
            {
                return false;
            }
        }

        private OxCadVerifiedDwgContext CapturarContextoVerificado()
        {
            Document? document = acApp.DocumentManager.MdiActiveDocument;
            if (document == null || !_contextRefreshGate.IsCurrentDocument(document))
                throw new InvalidOperationException("CONTEXTO_INCOMPATIVEL");

            AcDb.Database database = document.Database;
            long generation = _contextRefreshGate.CurrentGeneration;
            ProjectScope scope = DwgProjectScopeStore.Read(database);
            string path = database.Filename;
            string fingerprint = database.FingerprintGuid;
            if (!scope.IsBound || !_projectScopeResolved ||
                !string.Equals(scope.SobId, _ultimoSobId, StringComparison.Ordinal) ||
                !string.Equals(fingerprint, _ultimoDwgIdentity, StringComparison.OrdinalIgnoreCase) ||
                string.IsNullOrWhiteSpace(path) || !File.Exists(path) ||
                !string.Equals(Path.GetFullPath(path), Path.GetFullPath(_ultimoDwgFullPath ?? string.Empty), StringComparison.OrdinalIgnoreCase) ||
                !_contextRefreshGate.IsCurrentGeneration(generation) ||
                !ReferenceEquals(document, acApp.DocumentManager.MdiActiveDocument))
                throw new InvalidOperationException("CONTEXTO_INCOMPATIVEL");

            return new OxCadVerifiedDwgContext(scope.SobId!, path, fingerprint, generation);
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

            bool requerProjectScope = !string.Equals(acao, "sob", StringComparison.OrdinalIgnoreCase);
            if (requerProjectScope && !_projectScopeResolved)
                return;
            if (_ultimoDwgIdentity != null &&
                !ContextoDwgAtivoCoerente(requerProjectScope))
                return;

            OxCadVerifiedDwgContext? source = null;
            try
            {
                if (requerProjectScope)
                    source = CapturarContextoVerificado();
            }
            catch (InvalidOperationException)
            {
                return;
            }

            long contextGeneration = _contextRefreshGate.CurrentGeneration;
            OxCadExecutionRecord execution = IniciarExecucaoPaleta(acao);
            OxCadVerifiedDwgContext? verified = source == null ? null :
                new OxCadVerifiedDwgContext(
                    source.SobId, source.DwgPath, source.DwgIdentity,
                    source.ContextGeneration, execution.ExecutionId,
                    execution.CorrelationId);
            _isActionRunning = true;
            HabilitarBotoesAcao(false);

            try
            {
                TxtAcaoEstado.Text = "Executando...";
                TxtAcaoEstado.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97)); // Laranja
                TxtAcaoMensagem.Text = $"Disparando módulo {acao.ToUpper()}...";

                var resultado = await WorkspaceService.ExecutarAcaoAsync(
                    acao,
                    execution.DwgPath,
                    correlationId: execution.CorrelationId,
                    sobId: execution.SobId,
                    requireProjectScope: requerProjectScope,
                    executionId: execution.ExecutionId,
                    dwgIdentity: execution.DwgIdentity,
                    executionOrigin: execution.Origin,
                    waitForCompletion: true,
                    executionManagedByHost: true,
                    verifiedContext: verified);

                FinalizarExecucaoPaleta(execution, resultado);

                if (!_contextRefreshGate.IsCurrentGeneration(contextGeneration))
                    return;

                if (string.Equals(acao, "validar", StringComparison.OrdinalIgnoreCase))
                {
                    AtualizarResultadosValidacao(resultado);
                }
                else if (ContextoDwgAtivoCoerente(requerProjectScope))
                {
                    await AtualizarContextoAsync(preserveExecutionSummary: true);
                }
            }
            catch (Exception ex)
            {
                FinalizarExecucaoPaleta(execution, null, ex);
                OxCadLogger.LogError(
                    $"Falha na execução {execution.ExecutionId} ({acao})",
                    ex,
                    correlationId: execution.CorrelationId,
                    sobId: execution.SobId,
                    dwgPath: execution.DwgPath,
                    action: acao,
                    executionId: execution.ExecutionId);
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
            if (_isActionRunning || !_projectScopeResolved || !ContextoDwgAtivoCoerente(true))
                return;

            OxCadVerifiedDwgContext source;
            try { source = CapturarContextoVerificado(); }
            catch (InvalidOperationException) { return; }

            OxCadExecutionRecord execution = IniciarExecucaoPaleta("abrir");
            var verified = new OxCadVerifiedDwgContext(
                source.SobId, source.DwgPath, source.DwgIdentity,
                source.ContextGeneration, execution.ExecutionId, execution.CorrelationId);
            _isActionRunning = true;
            HabilitarBotoesAcao(false);
            try
            {
                TxtAcaoEstado.Text = "Abrindo...";
                TxtAcaoEstado.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
                TxtAcaoMensagem.Text = $"Abrindo artefato: {Path.GetFileName(caminho)}...";

                var resultado = await WorkspaceService.ExecutarAcaoAsync(
                    "abrir",
                    execution.DwgPath,
                    caminho,
                    correlationId: execution.CorrelationId,
                    sobId: execution.SobId,
                    requireProjectScope: true,
                    executionId: execution.ExecutionId,
                    dwgIdentity: execution.DwgIdentity,
                    executionOrigin: execution.Origin,
                    waitForCompletion: true,
                    executionManagedByHost: true,
                    verifiedContext: verified);
                FinalizarExecucaoPaleta(execution, resultado);
            }
            catch (Exception ex)
            {
                FinalizarExecucaoPaleta(execution, null, ex);
                OxCadLogger.LogError(
                    $"Falha na execução {execution.ExecutionId} (abrir)",
                    ex,
                    correlationId: execution.CorrelationId,
                    sobId: execution.SobId,
                    dwgPath: execution.DwgPath,
                    action: "abrir",
                    executionId: execution.ExecutionId);
            }
            finally
            {
                _isActionRunning = false;
                HabilitarBotoesAcao(true);
            }
        }

        private void HabilitarBotoesAcao(bool habilitado)
        {
            bool enabled = habilitado && !_isActionRunning;
            bool habilitadoComProjectScope = enabled && _projectScopeResolved;
            BtnCqt.IsEnabled = habilitadoComProjectScope;
            BtnValidar.IsEnabled = habilitadoComProjectScope;
            BtnOrcamento.IsEnabled = habilitadoComProjectScope;
            BtnCpfc.IsEnabled = habilitadoComProjectScope;
            BtnAmbiental.IsEnabled = habilitadoComProjectScope;
            BtnPrancha.IsEnabled = habilitadoComProjectScope;
            BtnSob.IsEnabled = enabled;
            BtnLevantamentoCondutores.IsEnabled = enabled;
            BtnLevantamentoPostes.IsEnabled = enabled;
            BtnTempoAcaoPrincipal.IsEnabled = habilitadoComProjectScope;
            BtnTempoConcluir.IsEnabled = habilitadoComProjectScope &&
                _currentTempo != null &&
                _currentTempo.Estado != "NaoIniciado" &&
                _currentTempo.Estado != "Concluido";
        }

        private void BtnLevantarCondutores_Click(object sender, RoutedEventArgs e)
        {
            if (_isActionRunning)
                return;

            Document? doc = acApp.DocumentManager.MdiActiveDocument;
            if (doc == null)
            {
                TxtAcaoEstado.Text = "Indisponível";
                TxtAcaoMensagem.Text = "Abra um desenho no AutoCAD antes de iniciar o levantamento.";
                return;
            }

            OxCadExecutionRecord execution = IniciarExecucaoPaleta(
                "LEVANTAR_CONDUTORES",
                doc);
            _nativeCommandExecutionId = execution.ExecutionId;
            _isActionRunning = true;
            HabilitarBotoesAcao(false);
            try
            {
                OxCadExecutionRegistry.RegistrarComandoNativo(
                    execution,
                    "LEVANTAR_CONDUTORES");
                doc.SendStringToExecute("_.LEVANTAR_CONDUTORES ", true, false, false);
            }
            catch (Exception ex)
            {
                _nativeCommandExecutionId = null;
                _isActionRunning = false;
                FinalizarExecucaoPaleta(execution, null, ex);
                HabilitarBotoesAcao(true);
                TxtAcaoMensagem.Text = ex.Message;
            }
        }

        private void BtnLevantarPostes_Click(object sender, RoutedEventArgs e)
        {
            if (_isActionRunning)
                return;

            Document? doc = acApp.DocumentManager.MdiActiveDocument;
            if (doc == null)
            {
                TxtAcaoEstado.Text = "Indisponível";
                TxtAcaoMensagem.Text = "Abra um desenho no AutoCAD antes de iniciar o levantamento de postes.";
                return;
            }

            OxCadExecutionRecord execution = IniciarExecucaoPaleta(
                "LEVANTAR_POSTES",
                doc);
            _nativeCommandExecutionId = execution.ExecutionId;
            _isActionRunning = true;
            HabilitarBotoesAcao(false);
            try
            {
                OxCadExecutionRegistry.RegistrarComandoNativo(
                    execution,
                    "LEVANTAR_POSTES");
                doc.SendStringToExecute("_.LEVANTAR_POSTES ", true, false, false);
            }
            catch (Exception ex)
            {
                _nativeCommandExecutionId = null;
                _isActionRunning = false;
                FinalizarExecucaoPaleta(execution, null, ex);
                HabilitarBotoesAcao(true);
                TxtAcaoMensagem.Text = ex.Message;
            }
        }

        /// <summary>
        /// Consulta assíncrona do contexto operacional com controle de concorrência.
        /// </summary>
        public async Task AtualizarContextoAsync(bool preserveExecutionSummary = false)
        {
            Document? document = null;
            AcDb.Database? database = null;
            try
            {
                document = acApp.DocumentManager.MdiActiveDocument;
                database = document?.Database;
            }
            catch
            {
                // AutoCAD pode não ter documento durante encerramento ou inicialização.
            }

            if (document == null || database == null)
            {
                _contextRefreshGate.Invalidate();
                _isUpdating = false;
                InvalidarContextoVisual("Nenhum documento ativo.");
                ExibirEstadoSemDocumento();
                BtnAtualizar.IsEnabled = true;
                BtnAtualizar.Content = "🔄 Atualizar Contexto";
                HabilitarBotoesAcao(true);
                return;
            }

            string dwgIdentity = database.FingerprintGuid;
            ContextRefreshTicket ticket = _contextRefreshGate.Begin(document, database, dwgIdentity);
            _isUpdating = true;
            InvalidarContextoVisual("Atualizando contexto...", preserveExecutionSummary);
            _ultimoDwgIdentity = dwgIdentity;
            TxtDwg.Text = document.Name;
            BtnAtualizar.IsEnabled = false;
            BtnAtualizar.Content = "⏳ Consultando...";
            HabilitarBotoesAcao(false);

            try
            {
                string dwgFilename = database.Filename;
                if (string.IsNullOrWhiteSpace(dwgFilename) || !File.Exists(dwgFilename))
                {
                    if (TicketAindaAtivo(ticket))
                        ExibirEstadoDesenhoNaoSalvo();
                    return;
                }

                ProjectScope projectScope = DwgProjectScopeStore.Read(database);
                if (!TicketAindaAtivo(ticket))
                    return;

                if (!projectScope.IsBound)
                {
                    if (DwgProjectScopeStore.TryReconcile(document, database, dwgFilename, out ProjectScope reconciledScope))
                    {
                        projectScope = reconciledScope;
                    }
                    else
                    {
                        _ultimoDwgFullPath = dwgFilename;
                        ExibirEstadoProjectScope(reconciledScope, dwgFilename);
                        return;
                    }
                }

                string correlationId = Guid.NewGuid().ToString("N");
                var verified = new OxCadVerifiedDwgContext(
                    projectScope.SobId!, dwgFilename, dwgIdentity,
                    ticket.Generation, correlationId: correlationId);

                OxCadWorkspaceContext contexto = await WorkspaceService.ConsultarContextoAsync(
                    dwgFilename,
                    correlationId: correlationId,
                    sobId: projectScope.SobId,
                    verifiedContext: verified);

                if (!TicketAindaAtivo(ticket))
                    return;

                _ultimoDwgFullPath = dwgFilename;
                _ultimoDwgIdentity = dwgIdentity;
                _ultimoSobId = projectScope.SobId;
                AplicarContextoNaInterface(contexto);
            }
            catch (Exception ex)
            {
                if (TicketAindaAtivo(ticket))
                {
                    TxtStatus.Text = $"Falha ao atualizar: {ex.Message}";
                    TxtStatus.Foreground = new SolidColorBrush(Color.FromRgb(231, 111, 81));
                }
            }
            finally
            {
                if (_contextRefreshGate.IsCurrentGeneration(ticket.Generation))
                {
                    if (!TicketAindaAtivo(ticket))
                    {
                        _contextRefreshGate.Invalidate();
                        _isUpdating = false;
                        AgendarAtualizacaoContextoAssincrona();
                    }
                    else
                    {
                        _isUpdating = false;
                        HabilitarBotoesAcao(true);
                        BtnAtualizar.IsEnabled = true;
                        BtnAtualizar.Content = "🔄 Atualizar Contexto";
                    }
                }
            }
        }

        private bool TicketAindaAtivo(ContextRefreshTicket ticket)
        {
            try
            {
                Document? activeDocument = acApp.DocumentManager.MdiActiveDocument;
                if (activeDocument == null)
                    return false;
                AcDb.Database? activeDatabase = activeDocument.Database;
                if (activeDatabase == null)
                    return false;

                string? activeFingerprint = null;
                try
                {
                    activeFingerprint = activeDatabase.FingerprintGuid;
                }
                catch
                {
                }

                return _contextRefreshGate.IsCurrent(
                    ticket,
                    activeDocument,
                    activeDatabase,
                    activeFingerprint);
            }
            catch
            {
                return false;
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
            if (_isActionRunning || _isUpdating || !_projectScopeResolved ||
                !ContextoDwgAtivoCoerente(true)) return;

            OxCadVerifiedDwgContext source;
            try { source = CapturarContextoVerificado(); }
            catch (InvalidOperationException) { return; }

            OxCadExecutionRecord execution = IniciarExecucaoPaleta(acaoTempo);
            var verified = new OxCadVerifiedDwgContext(
                source.SobId, source.DwgPath, source.DwgIdentity,
                source.ContextGeneration, execution.ExecutionId, execution.CorrelationId);
            _isActionRunning = true;
            HabilitarBotoesAcao(false);
            BtnTempoAcaoPrincipal.IsEnabled = false;
            BtnTempoConcluir.IsEnabled = false;

            try
            {
                TxtAcaoEstado.Text = "Executando...";
                TxtAcaoEstado.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
                TxtAcaoMensagem.Text = $"Atualizando apontamento de tempo ({acaoTempo})...";

                var resultado = await WorkspaceService.ControlarTempoAsync(
                    acaoTempo,
                    execution.DwgPath,
                    correlationId: execution.CorrelationId,
                    sobId: execution.SobId,
                    requireProjectScope: true,
                    executionId: execution.ExecutionId,
                    dwgIdentity: execution.DwgIdentity,
                    executionOrigin: execution.Origin,
                    waitForCompletion: true,
                    executionManagedByHost: true,
                    verifiedContext: verified);
                FinalizarExecucaoPaleta(execution, resultado);

                await AtualizarContextoAsync(preserveExecutionSummary: true);
            }
            catch (Exception ex)
            {
                FinalizarExecucaoPaleta(execution, null, ex);
                OxCadLogger.LogError(
                    $"Falha na execução {execution.ExecutionId} ({acaoTempo})",
                    ex,
                    correlationId: execution.CorrelationId,
                    sobId: execution.SobId,
                    dwgPath: execution.DwgPath,
                    action: acaoTempo,
                    executionId: execution.ExecutionId);
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
                        OxCadVerifiedDwgContext source;
                        try { source = CapturarContextoVerificado(); }
                        catch (InvalidOperationException) { return; }
                        var heartbeat = new OxCadVerifiedDwgContext(
                            source.SobId, source.DwgPath, source.DwgIdentity,
                            source.ContextGeneration,
                            Guid.NewGuid().ToString("N"), Guid.NewGuid().ToString("N"));

                        _isHeartbeatRunning = true;
                        _ = Task.Run(async () =>
                        {
                            try
                            {
                                await WorkspaceService.ControlarTempoAsync(
                                    "tempo_heartbeat",
                                    heartbeat.DwgPath,
                                    correlationId: heartbeat.CorrelationId,
                                    sobId: heartbeat.SobId,
                                    requireProjectScope: true,
                                    executionId: heartbeat.ExecutionId,
                                    dwgIdentity: heartbeat.DwgIdentity,
                                    verifiedContext: heartbeat);
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

        private void InvalidarContextoVisual(
            string status,
            bool preserveExecutionSummary = false)
        {
            _ultimoDwgFullPath = null;
            _ultimoSobId = null;
            _ultimoDwgIdentity = null;
            _projectScopeResolved = false;
            _uiTimer?.Stop();

            TxtStatus.Text = status;
            TxtStatus.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
            TxtSob.Text = "-";
            TxtDwg.Text = "-";
            TxtPasta.Text = "-";
            TxtMunicipio.Text = "-";
            TxtBairro.Text = "-";
            TxtEndereco.Text = "-";
            if (!preserveExecutionSummary)
            {
                TxtAcaoEstado.Text = "Pronto";
                TxtAcaoMensagem.Text = string.Empty;
            }
            CardInconsistencia.Visibility = Visibility.Collapsed;
            ListaArtefatos.ItemsSource = null;
            ListaValidacoes.ItemsSource = null;
            TxtValidationSummary.Text = string.Empty;
            PainelValidacao.Visibility = Visibility.Collapsed;
            AplicarTempoNaInterface(null);
            BtnTempoAcaoPrincipal.IsEnabled = false;
            BtnTempoConcluir.IsEnabled = false;
            HabilitarBotoesAcao(false);
        }

        private void AtualizarResultadosValidacao(OxCadActionResult resultado)
        {
            ListaValidacoes.ItemsSource = resultado.ValidationResults;
            int CountFor(string status)
                => resultado.ValidationSummary.TryGetValue(status, out int count) ? count : 0;

            TxtValidationSummary.Text =
                $"Validação: {CountFor("OK")} OK | " +
                $"{CountFor("ALERTA")} ALERTA | " +
                $"{CountFor("ERRO")} ERRO | " +
                $"{CountFor("NÃO DISPONÍVEL")} NÃO DISPONÍVEL";
            PainelValidacao.Visibility = Visibility.Visible;
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

        private void ExibirEstadoProjectScope(ProjectScope projectScope, string dwgFilename)
        {
            TxtStatus.Text = projectScope.Status switch
            {
                ProjectScopeStatus.Unbound => "Contexto não identificado.",
                ProjectScopeStatus.Ambiguous => "Vínculo de projeto ambíguo.",
                _ => $"Vínculo de projeto inválido: {projectScope.Detail ?? "metadata inválida"}."
            };
            TxtStatus.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
            TxtSob.Text = projectScope.SobId ?? "-";
            TxtDwg.Text = Path.GetFileName(dwgFilename);
            TxtPasta.Text = Path.GetDirectoryName(dwgFilename) ?? "-";
            TxtMunicipio.Text = "-";
            TxtBairro.Text = "-";
            TxtEndereco.Text = "-";
            CardInconsistencia.Visibility = projectScope.Status == ProjectScopeStatus.Ambiguous
                ? Visibility.Visible
                : Visibility.Collapsed;
            TxtInconsistenciaMsg.Text = projectScope.Detail ?? "Mais de uma identidade de projeto foi encontrada no DWG.";
            ListaArtefatos.ItemsSource = null;
            AplicarTempoNaInterface(null);
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
            _projectScopeResolved = contexto.ProjectScopeResolved &&
                string.Equals(contexto.SobId, _ultimoSobId, StringComparison.Ordinal);

            TxtStatus.Text = contexto.Status;
            TxtSob.Text = contexto.SobId;
            TxtDwg.Text = contexto.DwgPrincipal;
            TxtPasta.Text = contexto.RootDir;
            TxtMunicipio.Text = contexto.Municipio;
            TxtBairro.Text = contexto.Bairro;
            TxtEndereco.Text = contexto.Endereco;

            if (!_projectScopeResolved)
            {
                TxtStatus.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
                CardInconsistencia.Visibility = contexto.ProjectScopeStatus == "Ambiguous"
                    ? Visibility.Visible
                    : Visibility.Collapsed;
                TxtInconsistenciaMsg.Text = contexto.MensagemInconsistencia;
                ListaArtefatos.ItemsSource = null;
                AplicarTempoNaInterface(null);
                return;
            }

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

        private async void BtnConsultarIndicadores_Click(object sender, RoutedEventArgs e)
        {
            if (BtnConsultarIndicadores == null) return;
            BtnConsultarIndicadores.IsEnabled = false;
            TxtIndicadoresStatus.Text = "Consultando indicadores analíticos...";
            TxtIndicadoresStatus.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));

            try
            {
                string? sobId = _ultimoSobId != "-" ? _ultimoSobId : null;
                string? projectRoot = null;
                if (!string.IsNullOrWhiteSpace(_ultimoDwgFullPath) && File.Exists(_ultimoDwgFullPath))
                {
                    try
                    {
                        projectRoot = WorkspaceService.ObterDiretorioRaizProjeto(_ultimoDwgFullPath);
                    }
                    catch { }
                }

                // Consulta de indicadores totalmente desacoplada e assíncrona (não gera OxCadExecution)
                string json = await WorkspaceService.ConsultarIndicadoresJsonAsync(
                    projectRoot: projectRoot,
                    sobId: sobId);

                using (var doc = System.Text.Json.JsonDocument.Parse(json))
                {
                    var root = doc.RootElement;
                    string statusGeral = root.TryGetProperty("escopo", out var escopoProp) && escopoProp.TryGetProperty("status_identidade", out var idProp)
                        ? idProp.GetString() ?? "VALIDA"
                        : "VALIDA";

                    if (statusGeral == "IDENTITY_UNVERIFIABLE")
                    {
                        TxtIndicadoresStatus.Text = "Identidade inverificável (SOB divergente ou ausente).";
                        TxtIndicadoresStatus.Foreground = new SolidColorBrush(Color.FromRgb(231, 111, 81));
                        PainelIndicadoresMetricas.Visibility = Visibility.Collapsed;
                        return;
                    }

                    if (root.TryGetProperty("execucoes", out var execProp))
                    {
                        string stExec = execProp.TryGetProperty("status", out var st) ? st.GetString() ?? "" : "";
                        if (stExec == "OK" || stExec == "SEM_DADOS")
                        {
                            int total = execProp.TryGetProperty("total_execucoes", out var t) && t.ValueKind == System.Text.Json.JsonValueKind.Number ? t.GetInt32() : 0;
                            int conc = execProp.TryGetProperty("concluidas", out var c) && c.ValueKind == System.Text.Json.JsonValueKind.Number ? c.GetInt32() : 0;
                            int falhas = execProp.TryGetProperty("falhas", out var f) && f.ValueKind == System.Text.Json.JsonValueKind.Number ? f.GetInt32() : 0;

                            TxtIndTotalExec.Text = total.ToString();
                            TxtIndConcluidas.Text = conc.ToString();
                            TxtIndFalhas.Text = falhas.ToString();

                            if (execProp.TryGetProperty("taxa_conclusao_pct", out var tx) && tx.ValueKind == System.Text.Json.JsonValueKind.Number)
                            {
                                TxtIndTaxaConclusao.Text = $"Taxa de sucesso: {tx.GetDouble():F1}%";
                            }
                            else
                            {
                                TxtIndTaxaConclusao.Text = "Taxa de sucesso: N/D";
                            }

                            if (execProp.TryGetProperty("duracao_ms", out var durProp) && durProp.TryGetProperty("p95_ms", out var p95) && p95.ValueKind == System.Text.Json.JsonValueKind.Number)
                            {
                                TxtIndDuracaoP95.Text = $"P95: {p95.GetDouble() / 1000.0:F2}s";
                            }
                            else
                            {
                                TxtIndDuracaoP95.Text = "P95: N/D";
                            }
                        }
                    }

                    // Pendências
                    if (root.TryGetProperty("pendencias", out var pendProp))
                    {
                        string stPend = pendProp.TryGetProperty("status", out var st) ? st.GetString() ?? "" : "";
                        if (stPend == "OK")
                        {
                            int totP = pendProp.TryGetProperty("total", out var tp) && tp.ValueKind == System.Text.Json.JsonValueKind.Number ? tp.GetInt32() : 0;
                            int abP = pendProp.TryGetProperty("abertas", out var ap) && ap.ValueKind == System.Text.Json.JsonValueKind.Number ? ap.GetInt32() : 0;
                            TxtIndPendencias.Text = $"{abP} abertas / {totP} total";
                        }
                        else
                        {
                            TxtIndPendencias.Text = "NÃO DISPONÍVEL";
                        }
                    }

                    // Entregas
                    if (root.TryGetProperty("entregas", out var delivProp))
                    {
                        string stDel = delivProp.TryGetProperty("status", out var st) ? st.GetString() ?? "" : "";
                        if (stDel == "OK")
                        {
                            int totD = delivProp.TryGetProperty("total_pacotes", out var td) && td.ValueKind == System.Text.Json.JsonValueKind.Number ? td.GetInt32() : 0;
                            int aprD = delivProp.TryGetProperty("aprovados", out var ad) && ad.ValueKind == System.Text.Json.JsonValueKind.Number ? ad.GetInt32() : 0;
                            TxtIndEntregas.Text = $"{aprD} aprovados / {totD} total";
                        }
                        else
                        {
                            TxtIndEntregas.Text = "NÃO DISPONÍVEL";
                        }
                    }

                    // Qualidade e Cobertura (P2.3)
                    if (root.TryGetProperty("qualidade_dados", out var qualProp))
                    {
                        string cob = qualProp.TryGetProperty("cobertura", out var cb) ? cb.GetString() ?? "PARCIAL" : "PARCIAL";
                        TxtIndCobertura.Text = $"COBERTURA: {cob}";
                        switch (cob)
                        {
                            case "COMPLETA":
                                TxtIndCobertura.Foreground = new SolidColorBrush(Color.FromRgb(82, 183, 136));
                                break;
                            case "PARCIAL":
                                TxtIndCobertura.Foreground = new SolidColorBrush(Color.FromRgb(233, 196, 106));
                                break;
                            case "LIMITADA_POR_ROTACAO":
                                TxtIndCobertura.Foreground = new SolidColorBrush(Color.FromRgb(244, 162, 97));
                                break;
                            case "SEM_DADOS":
                                TxtIndCobertura.Foreground = new SolidColorBrush(Color.FromRgb(160, 160, 176));
                                break;
                            default:
                                TxtIndCobertura.Foreground = new SolidColorBrush(Color.FromRgb(231, 111, 81));
                                break;
                        }

                        if (qualProp.TryGetProperty("fontes_utilizadas", out var fProp) && fProp.ValueKind == System.Text.Json.JsonValueKind.Array)
                        {
                            var listaFontes = new List<string>();
                            foreach (var item in fProp.EnumerateArray())
                            {
                                string? fStr = item.GetString();
                                if (!string.IsNullOrWhiteSpace(fStr)) listaFontes.Add(fStr!);
                            }
                            TxtIndFontes.Text = listaFontes.Count > 0 ? $"Fontes: {string.Join(", ", listaFontes)}" : "Fontes: Nenhuma";
                        }

                        if (qualProp.TryGetProperty("limitacoes_cobertura", out var limProp) && limProp.ValueKind == System.Text.Json.JsonValueKind.Array)
                        {
                            var listaLim = new List<string>();
                            foreach (var lim in limProp.EnumerateArray())
                            {
                                string? lStr = lim.GetString();
                                if (!string.IsNullOrWhiteSpace(lStr)) listaLim.Add(lStr!);
                            }
                            if (listaLim.Count > 0)
                            {
                                TxtIndObservacoes.Text = string.Join(" | ", listaLim);
                            }
                        }
                    }

                    // Período Observado
                    if (root.TryGetProperty("periodo_observado", out var perProp))
                    {
                        string pIni = perProp.TryGetProperty("inicio", out var pi) ? pi.GetString() ?? "" : "";
                        string pFim = perProp.TryGetProperty("fim", out var pf) ? pf.GetString() ?? "" : "";
                        if (!string.IsNullOrWhiteSpace(pIni))
                        {
                            string iniData = pIni.Contains("T") ? pIni.Split('T')[0] : pIni;
                            string fimData = !string.IsNullOrWhiteSpace(pFim) && pFim.Contains("T") ? pFim.Split('T')[0] : (string.IsNullOrWhiteSpace(pFim) ? "atual" : pFim);
                            TxtIndPeriodo.Text = $"{iniData} .. {fimData}";
                        }
                        else
                        {
                            TxtIndPeriodo.Text = "Período: N/D";
                        }
                    }

                    TxtIndAtualizadoEm.Text = DateTime.Now.ToString("HH:mm:ss");
                    TxtIndicadoresStatus.Text = "Indicadores atualizados com sucesso.";
                    TxtIndicadoresStatus.Foreground = new SolidColorBrush(Color.FromRgb(82, 183, 136));
                    PainelIndicadoresMetricas.Visibility = Visibility.Visible;
                }
            }
            catch (Exception ex)
            {
                TxtIndicadoresStatus.Text = $"Erro na consulta de indicadores: {ex.Message}";
                TxtIndicadoresStatus.Foreground = new SolidColorBrush(Color.FromRgb(231, 111, 81));
            }
            finally
            {
                BtnConsultarIndicadores.IsEnabled = true;
            }
        }
    }
}
