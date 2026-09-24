using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using Microsoft.Web.WebView2.Core;

namespace MapaCadPaleta
{
    public partial class MapaControl : UserControl
    {
        private Task? _initializationTask;

        public MapaControl()
        {
            InitializeComponent();
            Loaded += MapaControl_Loaded;
        }

        [System.Runtime.InteropServices.DllImport("kernel32.dll", CharSet = System.Runtime.InteropServices.CharSet.Auto, SetLastError = true)]
        private static extern bool SetDllDirectory(string lpPathName);

        private async void MapaControl_Loaded(object sender, RoutedEventArgs e)
        {
            try
            {
                await GarantirWebViewProntoAsync();
            }
            catch
            {
                // O erro já foi refletido no status e permanece disponível para operações dependentes.
            }
        }

        private Task GarantirWebViewProntoAsync()
        {
            return _initializationTask ??= InicializarWebViewAsync();
        }

        private async Task InicializarWebViewAsync()
        {
            try
            {
                string assemblyDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location) ?? "";
                string winX64Native = Path.Combine(assemblyDir, "runtimes", "win-x64", "native");

                // Configura resolução nativa da DLL do WebView2Loader
                if (File.Exists(Path.Combine(winX64Native, "WebView2Loader.dll")))
                {
                    SetDllDirectory(winX64Native);
                    try { CoreWebView2Environment.SetLoaderDllFolderPath(winX64Native); } catch { }
                }
                else if (File.Exists(Path.Combine(assemblyDir, "WebView2Loader.dll")))
                {
                    SetDllDirectory(assemblyDir);
                    try { CoreWebView2Environment.SetLoaderDllFolderPath(assemblyDir); } catch { }
                }

                string userDataFolder = Path.Combine(Path.GetTempPath(), "AuxCadWebView2Data");
                var env = await CoreWebView2Environment.CreateAsync(null, userDataFolder);

                await WebView.EnsureCoreWebView2Async(env);
                WebView.CoreWebView2.Settings.UserAgent = "OSMPALETA (CAD interno)";
                var navigationCompleted = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);

                string webDir = Path.Combine(assemblyDir, "web");

                // Fallback para pasta de desenvolvimento se executando direto
                if (!Directory.Exists(webDir))
                {
                    string altDir = Path.Combine(Directory.GetCurrentDirectory(), "mapa_cad_paleta", "web");
                    if (Directory.Exists(altDir))
                    {
                        webDir = altDir;
                    }
                }

                string indexHtml = Path.Combine(webDir, "index.html");
                if (File.Exists(indexHtml))
                {
                    WebView.CoreWebView2.Settings.AreDevToolsEnabled = true;
                    WebView.CoreWebView2.Settings.IsWebMessageEnabled = true;

                    WebView.CoreWebView2.WebMessageReceived += CoreWebView2_WebMessageReceived;
                    WebView.NavigationCompleted += (s, args) =>
                    {
                        LoadingPanel.Visibility = Visibility.Collapsed;
                        if (args.IsSuccess)
                        {
                            AtualizarStatus("Mapa OSM carregado com sucesso.");
                        }
                        else
                        {
                            AtualizarStatus($"Status de navegação: {args.WebErrorStatus}");
                        }
                        navigationCompleted.TrySetResult(args.IsSuccess);
                    };

                    try
                    {
                        WebView.CoreWebView2.SetVirtualHostNameToFolderMapping(
                            "appassets.example",
                            webDir,
                            CoreWebView2HostResourceAccessKind.Allow
                        );
                        WebView.CoreWebView2.Navigate("https://appassets.example/index.html");
                    }
                    catch
                    {
                        WebView.CoreWebView2.Navigate(new Uri(indexHtml).AbsoluteUri);
                    }
                }
                else
                {
                    // Fallback se pasta web não for encontrada
                    WebView.NavigateToString("<html><body style='font-family:sans-serif;padding:20px;'>" +
                        "<h3>Pasta 'web' não localizada</h3>" +
                        $"<p>Caminho esperado: {webDir}</p></body></html>");
                }

                if (!await navigationCompleted.Task.ConfigureAwait(true))
                    throw new InvalidOperationException("A navegação do WebView2 não foi concluída com sucesso.");

            }
            catch (Exception ex)
            {
                LoadingPanel.Visibility = Visibility.Collapsed;
                AtualizarStatus($"Erro ao carregar WebView2: {ex.Message}");
                throw;
            }
        }

        private void CoreWebView2_WebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
        {
            try
            {
                string rawJson = e.WebMessageAsJson;
                using var doc = JsonDocument.Parse(rawJson);
                var root = doc.RootElement;

                string action = root.TryGetProperty("action", out var actProp) ? actProp.GetString() ?? "" : "";

                switch (action)
                {
                    case "inserir_poste":
                        var res = CadBridge.InserirPoste(rawJson);
                        AtualizarStatus(res.Message);
                        EnviarMensagemWeb(new { action = "resultado_insercao", success = res.Success, message = res.Message });
                        break;

                    case "capturar_ponto":
                        ExecutarCapturaCad();
                        break;

                    case "escanear_dwg":
                        int fuso = root.TryGetProperty("fuso", out var fusoProp) ? fusoProp.GetInt32() : 23;
                        var postes = CadBridge.EscanearPostesDwg(fuso);
                        AtualizarStatus($"{postes.Count} postes encontrados no DWG.");
                        EnviarMensagemWeb(new { action = "postes_dwg", postes });
                        break;

                    case "desenhar_vao":
                        double x1 = root.TryGetProperty("x1", out var px1) ? px1.GetDouble() : 0;
                        double y1 = root.TryGetProperty("y1", out var py1) ? py1.GetDouble() : 0;
                        double x2 = root.TryGetProperty("x2", out var px2) ? px2.GetDouble() : 0;
                        double y2 = root.TryGetProperty("y2", out var py2) ? py2.GetDouble() : 0;
                        string tipoRede = root.TryGetProperty("tipoRede", out var pTr) ? pTr.GetString() ?? "BT" : "BT";
                        string textoVao = root.TryGetProperty("textoVao", out var pTv) ? pTv.GetString() ?? "" : "";
                        var resVao = CadBridge.InserirVaoCabos(x1, y1, x2, y2, tipoRede, textoVao);
                        AtualizarStatus(resVao.Message);
                        break;

                    case "desfazer_vao":
                        string numDesfazer = root.TryGetProperty("numero", out var pNum) ? pNum.GetString() ?? "" : "";
                        AtualizarStatus($"↩️ Traçado: Poste P{numDesfazer} desfeito.");
                        break;

                    case "abrir_kmz_ambiental":
                        AbrirArquivoAmbiental();
                        break;

                    case "desenhar_elementos_urbanos":
                        var resUrb = CadBridge.DesenharElementosUrbanos(rawJson);
                        AtualizarStatus(resUrb.Message);
                        break;

                    case "exportar_cqt":
                    case "abrir_cqtui":
                        ExportarParaCqt(rawJson);
                        break;

                    case "status":
                        string msg = root.TryGetProperty("message", out var m) ? m.GetString() ?? "" : "";
                        AtualizarStatus(msg);
                        break;
                }
            }
            catch (Exception ex)
            {
                AtualizarStatus($"Erro na comunicação: {ex.Message}");
            }
        }

        private void BtnCapturarCad_Click(object sender, RoutedEventArgs e)
        {
            ExecutarCapturaCad();
        }

        private void ExecutarCapturaCad()
        {
            AtualizarStatus("Clique no DWG para capturar coordenadas...");
            var cap = CadBridge.CapturarPontoCad(23);
            if (cap.Success)
            {
                AtualizarStatus($"Ponto capturado: X={cap.X:F2}, Y={cap.Y:F2}");
                EnviarMensagemWeb(new
                {
                    action = "ponto_capturado",
                    x = cap.X,
                    y = cap.Y,
                    lat = cap.Lat,
                    lon = cap.Lon
                });
            }
            else
            {
                if (!string.IsNullOrEmpty(cap.Error))
                    AtualizarStatus(cap.Error);
            }
        }

        private async void BtnRecarregar_Click(object sender, RoutedEventArgs e)
        {
            LoadingPanel.Visibility = Visibility.Visible;
            try
            {
                await GarantirWebViewProntoAsync();
                WebView.CoreWebView2.Reload();
            }
            catch (Exception ex)
            {
                AtualizarStatus($"Erro ao recarregar WebView2: {ex.Message}");
            }
        }

        private async void EnviarMensagemWeb(object obj)
        {
            try
            {
                await GarantirWebViewProntoAsync();
                string json = JsonSerializer.Serialize(obj);
                WebView.CoreWebView2.PostWebMessageAsJson(json);
            }
            catch (Exception ex)
            {
                AtualizarStatus($"Erro ao enviar mensagem ao WebView2: {ex.Message}");
            }
        }

        private void AtualizarStatus(string texto)
        {
            Dispatcher.Invoke(() =>
            {
                TxtStatus.Text = texto;
            });
        }

        private void AbrirArquivoAmbiental()
        {
            Dispatcher.Invoke(() =>
            {
                var dlg = new Microsoft.Win32.OpenFileDialog
                {
                    Title = "Selecionar Arquivo de Restrições Ambientais (KMZ, KML ou GeoJSON)",
                    Filter = "Camadas Ambientais (*.kmz;*.kml;*.geojson;*.json)|*.kmz;*.kml;*.geojson;*.json|Google Earth (*.kmz;*.kml)|*.kmz;*.kml|GeoJSON (*.geojson;*.json)|*.geojson;*.json|Todos os Arquivos (*.*)|*.*"
                };

                if (dlg.ShowDialog() == true)
                {
                    try
                    {
                        var poligonos = AmbientalParser.CarregarArquivo(dlg.FileName);
                        AtualizarStatus($"{poligonos.Count} polígonos ambientais carregados de {Path.GetFileName(dlg.FileName)}.");
                        EnviarMensagemWeb(new
                        {
                            action = "poligonos_ambientais",
                            arquivo = Path.GetFileName(dlg.FileName),
                            poligonos
                        });
                    }
                    catch (Exception ex)
                    {
                        AtualizarStatus($"Erro ao ler arquivo ambiental: {ex.Message}");
                    }
                }
            });
        }

        private void ExportarParaCqt(string rawJson)
        {
            try
            {
                using var doc = JsonDocument.Parse(rawJson);
                string jsonPayload = "{}";
                if (doc.RootElement.TryGetProperty("dadosCqt", out var dadosProp))
                {
                    jsonPayload = dadosProp.GetRawText();
                }

                // Salva o JSON tanto em Path.GetTempPath() quanto em C:\Temp para máxima resiliência
                string tempDir = Path.GetTempPath();
                string jsonPathUserTemp = Path.Combine(tempDir, "auxcad_cqt_import.json");
                string jsonPathCTemp = Path.Combine(@"C:\Temp", "auxcad_cqt_import.json");

                try { File.WriteAllText(jsonPathUserTemp, jsonPayload, System.Text.Encoding.UTF8); } catch { }
                try
                {
                    if (!Directory.Exists(@"C:\Temp")) Directory.CreateDirectory(@"C:\Temp");
                    File.WriteAllText(jsonPathCTemp, jsonPayload, System.Text.Encoding.UTF8);
                }
                catch { }

                string chosenJson = File.Exists(jsonPathUserTemp) ? jsonPathUserTemp : jsonPathCTemp;

                // Localizar script cqt_excel_manager.py por múltiplos caminhos candidatos
                string? cqtScript = null;

                // Candidato 1: Subindo a partir do assembly em execução
                string assemblyLocation = Assembly.GetExecutingAssembly().Location;
                if (!string.IsNullOrEmpty(assemblyLocation))
                {
                    string root = Path.GetDirectoryName(assemblyLocation) ?? "";
                    for (int i = 0; i < 5; i++)
                    {
                        string test = Path.Combine(root, "cqt", "cqt_excel_manager.py");
                        if (File.Exists(test)) { cqtScript = test; break; }
                        var parent = Directory.GetParent(root);
                        if (parent != null) root = parent.FullName; else break;
                    }
                }

                // Candidato 2: Subindo a partir do diretório web ativo
                if (string.IsNullOrEmpty(cqtScript))
                {
                    string baseWeb = Path.Combine(Directory.GetCurrentDirectory(), "mapa_cad_paleta");
                    for (int i = 0; i < 4; i++)
                    {
                        string test = Path.Combine(baseWeb, "cqt", "cqt_excel_manager.py");
                        if (File.Exists(test)) { cqtScript = test; break; }
                        var parent = Directory.GetParent(baseWeb);
                        if (parent != null) baseWeb = parent.FullName; else break;
                    }
                }

                // Candidato 3: Caminho absoluto conhecido do workspace
                if (string.IsNullOrEmpty(cqtScript))
                {
                    string fallback = @"C:\Users\jonat\OneDrive - IM3 Brasil\aux cad\cqt\cqt_excel_manager.py";
                    if (File.Exists(fallback)) cqtScript = fallback;
                }

                if (!string.IsNullOrEmpty(cqtScript) && File.Exists(cqtScript))
                {
                    // Lançar via CMD com "py" para contornar problemas de permissão com App Execution Alias do Windows 11
                    var psi = new ProcessStartInfo
                    {
                        FileName = "cmd.exe",
                        Arguments = $"/c start \"\" py \"{cqtScript}\" \"{chosenJson}\"",
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                    Process.Start(psi);
                    AtualizarStatus($"⚡ Gerenciador CQTUI aberto com sucesso! ({chosenJson})");
                }
                else
                {
                    AtualizarStatus($"JSON CQT salvo em: {chosenJson}");
                }
            }
            catch (Exception ex)
            {
                AtualizarStatus($"Erro ao exportar para CQT: {ex.Message}");
            }
        }
    }
}
