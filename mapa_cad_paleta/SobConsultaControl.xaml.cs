using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using Autodesk.AutoCAD.ApplicationServices;
using acApp = Autodesk.AutoCAD.ApplicationServices.Application;
using UserControl = System.Windows.Controls.UserControl;

namespace MapaCadPaleta
{
    public partial class SobConsultaControl : UserControl
    {
        private bool _temAnexos;
        private string? _pastaConsultada;

        public SobConsultaControl()
        {
            InitializeComponent();
            Loaded += SobConsultaControl_Loaded;
            CadBridge.ProjectScopeChanged += (s, e) => Dispatcher.Invoke(() => AtualizarEstadoContexto());
        }

        private void SobConsultaControl_Loaded(object sender, RoutedEventArgs e)
        {
            OxCadProjectContext context = CadBridge.GetCurrentProjectContext();
            if (string.IsNullOrWhiteSpace(TxtDestino.Text) && !string.IsNullOrWhiteSpace(context.ProjectRoot))
                TxtDestino.Text = context.ProjectRoot;

            AtualizarEstadoContexto(context);
        }

        private void AtualizarEstadoContexto(OxCadProjectContext? context = null)
        {
            context ??= CadBridge.GetCurrentProjectContext();
            if (context.IsBound && !string.IsNullOrWhiteSpace(context.SobId))
            {
                TxtContextoStatus.Text = $"Projeto ativo: SOB {context.SobId} (DWG vinculado via AUXCAD_PROJECT_SCOPE)";
                TxtContextoStatus.Foreground = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(0x1B, 0x36, 0x5D));
                if (string.IsNullOrWhiteSpace(TxtSob.Text))
                    TxtSob.Text = context.SobId;
            }
            else
            {
                TxtContextoStatus.Text = "Nenhum projeto OXCAD vinculado ao DWG ativo (operação avulsa).";
                TxtContextoStatus.Foreground = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(0x64, 0x74, 0x8B));
            }

            VerificarDivergenciaContexto(context);
        }

        private void TxtSob_TextChanged(object sender, TextChangedEventArgs e)
        {
            VerificarDivergenciaContexto();
        }

        private void VerificarDivergenciaContexto(OxCadProjectContext? context = null)
        {
            context ??= CadBridge.GetCurrentProjectContext();
            if (context.IsBound && !string.IsNullOrWhiteSpace(context.SobId))
            {
                string sobDigitada = NormalizarSob(TxtSob.Text);
                string sobAtiva = NormalizarSob(context.SobId);

                if (!string.IsNullOrWhiteSpace(sobDigitada) && !string.Equals(sobDigitada, sobAtiva, StringComparison.OrdinalIgnoreCase))
                {
                    BorderAvisoDivergencia.Visibility = Visibility.Visible;
                    TxtAvisoDivergencia.Text = $"A SOB informada ({sobDigitada}) é DIFERENTE do projeto ativo ({sobAtiva}). " +
                        "Os arquivos pertencerão à SOB consultada e NÃO serão vinculados ao DWG atual. Confirmação explícita será exigida antes do download.";
                    return;
                }
            }

            BorderAvisoDivergencia.Visibility = Visibility.Collapsed;
        }

        private static string NormalizarSob(string? valor)
        {
            if (string.IsNullOrWhiteSpace(valor))
                return "";
            string v = valor!.Trim().ToUpperInvariant();
            return v.StartsWith("SOB_", StringComparison.OrdinalIgnoreCase) ? v.Substring(4) : v;
        }

        private static string ObterDiretorioDwgAtivo()
        {
            OxCadProjectContext context = CadBridge.GetCurrentProjectContext();
            return context.ProjectRoot ?? "";
        }

        private async void BtnConsultar_Click(object sender, RoutedEventArgs e)
        {
            string sob = TxtSob.Text.Trim();
            if (string.IsNullOrWhiteSpace(sob))
            {
                TxtResultado.Text = "Informe o número da SOB.";
                TxtSob.Focus();
                return;
            }

            LstAnexos.Items.Clear();
            _temAnexos = false;
            BtnBaixar.IsEnabled = false;
            BtnAbrirPasta.IsEnabled = false;

            OxCadProjectContext context = CadBridge.GetCurrentProjectContext();
            string contextoSob = (context.IsBound && !string.IsNullOrWhiteSpace(context.SobId)) ? context.SobId! : "";
            await ExecutarAcaoAsync("consultar", sob, "", contextoSob);
        }

        private async void BtnBaixar_Click(object sender, RoutedEventArgs e)
        {
            string destino = TxtDestino.Text.Trim();
            if (string.IsNullOrWhiteSpace(destino) || !Directory.Exists(destino))
            {
                TxtResultado.Text = "Selecione uma pasta válida antes de baixar os arquivos.";
                return;
            }

            OxCadProjectContext context = CadBridge.GetCurrentProjectContext();
            bool divergente = false;
            if (context.IsBound && !string.IsNullOrWhiteSpace(context.SobId))
            {
                string sobDigitada = NormalizarSob(TxtSob.Text);
                string sobAtiva = NormalizarSob(context.SobId);
                if (!string.Equals(sobDigitada, sobAtiva, StringComparison.OrdinalIgnoreCase))
                {
                    divergente = true;
                    MessageBoxResult confirmacao = System.Windows.MessageBox.Show(
                        $"A SOB informada ({sobDigitada}) diverge do projeto ativo ({sobAtiva}).\n\n" +
                        "Os arquivos baixados pertencerão à SOB consultada e NÃO serão vinculados ao DWG ativo.\n\n" +
                        "Deseja confirmar e prosseguir com o download da SOB divergente mesmo assim?",
                        "Confirmação de Download Divergente",
                        MessageBoxButton.YesNo,
                        MessageBoxImage.Warning);

                    if (confirmacao != MessageBoxResult.Yes)
                    {
                        TxtResultado.Text = "Download cancelado pelo usuário: SOB divergente do projeto ativo.";
                        return;
                    }
                }
            }

            string contextoSob = (context.IsBound && !string.IsNullOrWhiteSpace(context.SobId)) ? context.SobId! : "";
            await ExecutarAcaoAsync("baixar", TxtSob.Text.Trim(), destino, contextoSob, divergente);
        }

        private void BtnSelecionarPasta_Click(object sender, RoutedEventArgs e)
        {
            using var dialog = new System.Windows.Forms.FolderBrowserDialog
            {
                Description = "Selecione o diretório-base para salvar os arquivos da SOB.",
                SelectedPath = Directory.Exists(TxtDestino.Text) ? TxtDestino.Text : Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                ShowNewFolderButton = true
            };

            if (dialog.ShowDialog() == System.Windows.Forms.DialogResult.OK && !string.IsNullOrWhiteSpace(dialog.SelectedPath))
                TxtDestino.Text = dialog.SelectedPath;
        }

        private void BtnAbrirPasta_Click(object sender, RoutedEventArgs e)
        {
            string pasta = _pastaConsultada ?? "";
            if (string.IsNullOrWhiteSpace(pasta) || !Directory.Exists(pasta))
                return;

            Process.Start(new ProcessStartInfo("explorer.exe", QuoteArgument(pasta))
            {
                UseShellExecute = true
            });
        }

        private async Task ExecutarAcaoAsync(string acao, string sob, string destino, string contextoSob = "", bool confirmarDivergencia = false)
        {
            DefinirCarregando(true, acao == "consultar" ? "Consultando GOMnet..." : "Baixando arquivos da SOB...");
            try
            {
                string json = await ExecutarPythonAsync(acao, sob, destino, contextoSob, confirmarDivergencia);
                using JsonDocument document = JsonDocument.Parse(json);
                JsonElement root = document.RootElement;
                bool sucesso = LerBooleano(root, "success");
                if (!sucesso)
                {
                    string codigo = LerString(root, "error_code");
                    string erro = LerString(root, "error");
                    TxtResultado.Text = TraduzirErro(codigo, erro);
                    TxtSituacao.Text = "Situação cadastral: não disponível.";
                    return;
                }

                if (acao == "consultar")
                    AplicarResultadoConsulta(root);
                else
                    AplicarResultadoDownload(root);
            }
            catch (Exception ex)
            {
                TxtResultado.Text = $"Não foi possível concluir a operação GOMnet: {ex.Message}";
                TxtSituacao.Text = "Situação cadastral: não disponível.";
            }
            finally
            {
                DefinirCarregando(false, "");
            }
        }

        private void AplicarResultadoConsulta(JsonElement resultado)
        {
            string status = LerString(resultado, "status");
            string statusMensagem = LerString(resultado, "status_mensagem");
            TxtSituacao.Text = !string.IsNullOrWhiteSpace(status)
                ? $"Situação cadastral: {status}."
                : $"Situação cadastral: {statusMensagem}";
            JsonElement anexos = resultado.GetProperty("anexos");
            foreach (JsonElement anexo in anexos.EnumerateArray())
            {
                string nome = LerString(anexo, "nome");
                string extensao = LerString(anexo, "extensao");
                LstAnexos.Items.Add(string.IsNullOrWhiteSpace(extensao) ? nome : $"{nome}  ·  {extensao}");
            }

            _temAnexos = LstAnexos.Items.Count > 0;
            bool divergencia = resultado.TryGetProperty("divergencia", out JsonElement divElem) && divElem.ValueKind == JsonValueKind.True;
            string sufixoDivergencia = divergencia ? " (SOB divergente do projeto ativo)" : "";

            TxtResultado.Text = _temAnexos
                ? $"{LstAnexos.Items.Count} arquivo(s) vinculado(s) à SOB.{sufixoDivergencia}"
                : $"Nenhum projeto ou anexo vinculado a esta SOB.{sufixoDivergencia}";
            BtnBaixar.IsEnabled = _temAnexos;
        }

        private void AplicarResultadoDownload(JsonElement resultado)
        {
            _pastaConsultada = LerString(resultado, "diretorio");
            TxtResultado.Text = LerString(resultado, "message");
            TxtSituacao.Text = "Download concluído com sucesso.";
            BtnAbrirPasta.IsEnabled = !string.IsNullOrWhiteSpace(_pastaConsultada) && Directory.Exists(_pastaConsultada);
        }

        private void DefinirCarregando(bool carregando, string mensagem)
        {
            ProgressConsulta.Visibility = carregando ? Visibility.Visible : Visibility.Collapsed;
            BtnConsultar.IsEnabled = !carregando;
            BtnBaixar.IsEnabled = !carregando && _temAnexos;
            BtnSelecionarPasta.IsEnabled = !carregando;
            if (carregando)
                TxtResultado.Text = mensagem;
        }

        private static string TraduzirErro(string codigo, string erro)
        {
            if (codigo.Equals("GomnetAuthError", StringComparison.OrdinalIgnoreCase))
                return "Falha de autenticação no GOMnet. Verifique as credenciais configuradas.";
            if (codigo.Equals("GomnetNotFoundError", StringComparison.OrdinalIgnoreCase))
                return string.IsNullOrWhiteSpace(erro) ? "SOB não encontrada no GOMnet." : erro;
            if (codigo.Equals("CONFIRMACAO_DIVERGENCIA_NECESSARIA", StringComparison.OrdinalIgnoreCase))
                return string.IsNullOrWhiteSpace(erro) ? "Confirmação necessária para download de SOB divergente." : erro;
            return string.IsNullOrWhiteSpace(erro) ? "Falha ao consultar a SOB no GOMnet." : erro;
        }

        private static string LerString(JsonElement elemento, string propriedade)
        {
            return elemento.TryGetProperty(propriedade, out JsonElement valor) && valor.ValueKind == JsonValueKind.String
                ? valor.GetString() ?? ""
                : "";
        }

        private static bool LerBooleano(JsonElement elemento, string propriedade)
        {
            return elemento.TryGetProperty(propriedade, out JsonElement valor) &&
                   valor.ValueKind == JsonValueKind.True;
        }

        private static async Task<string> ExecutarPythonAsync(string acao, string sob, string destino, string contextoSob = "", bool confirmarDivergencia = false)
        {
            string script = LocalizarScriptConsulta();
            string argumentos = $"{QuoteArgument(script)} --sob {QuoteArgument(sob)} --acao {QuoteArgument(acao)}";
            if (!string.IsNullOrWhiteSpace(destino))
                argumentos += $" --destino {QuoteArgument(destino)}";
            if (!string.IsNullOrWhiteSpace(contextoSob))
                argumentos += $" --contexto-sob {QuoteArgument(contextoSob)}";
            if (confirmarDivergencia)
                argumentos += " --confirmar-divergencia";

            Process? processo;
            try
            {
                processo = Process.Start(CriarStartInfo("python", argumentos));
            }
            catch (System.ComponentModel.Win32Exception)
            {
                processo = Process.Start(CriarStartInfo("py", $"-3 {argumentos}"));
            }

            if (processo == null)
                throw new InvalidOperationException("Não foi possível iniciar o Python.");

            using (processo)
            {
                Task<string> stdoutTask = processo.StandardOutput.ReadToEndAsync();
                Task<string> stderrTask = processo.StandardError.ReadToEndAsync();
                await Task.Run(() => processo.WaitForExit());
                string stdout = await stdoutTask;
                string stderr = await stderrTask;
                if (string.IsNullOrWhiteSpace(stdout))
                    throw new InvalidOperationException(string.IsNullOrWhiteSpace(stderr) ? "O processo Python não retornou resultado." : stderr.Trim());
                return stdout.Trim();
            }
        }

        private static ProcessStartInfo CriarStartInfo(string executavel, string argumentos)
        {
            return new ProcessStartInfo(executavel, argumentos)
            {
                WorkingDirectory = Path.GetDirectoryName(LocalizarScriptConsulta()) ?? Environment.CurrentDirectory,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8
            };
        }

        private static string LocalizarScriptConsulta()
        {
            string assemblyDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location) ?? "";
            for (DirectoryInfo? dir = new DirectoryInfo(assemblyDir); dir != null; dir = dir.Parent)
            {
                string candidato = Path.Combine(dir.FullName, "sob", "sob_consulta.py");
                if (File.Exists(candidato))
                    return candidato;
            }

            string cwdCandidate = Path.Combine(Environment.CurrentDirectory, "sob", "sob_consulta.py");
            if (File.Exists(cwdCandidate))
                return cwdCandidate;

            throw new FileNotFoundException("Script de consulta SOB não encontrado (sob/sob_consulta.py).");
        }

        private static string QuoteArgument(string argumento)
        {
            var quoted = new StringBuilder("\"");
            int backslashes = 0;
            foreach (char caractere in argumento)
            {
                if (caractere == '\\')
                {
                    backslashes++;
                    continue;
                }

                if (caractere == '\"')
                {
                    quoted.Append('\\', backslashes * 2 + 1);
                    quoted.Append(caractere);
                }
                else
                {
                    quoted.Append('\\', backslashes);
                    quoted.Append(caractere);
                }
                backslashes = 0;
            }

            quoted.Append('\\', backslashes * 2);
            quoted.Append('\"');
            return quoted.ToString();
        }
    }
}
