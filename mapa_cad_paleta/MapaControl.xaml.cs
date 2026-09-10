using System;
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
        private bool _isInitialized = false;

        public MapaControl()
        {
            InitializeComponent();
            Loaded += MapaControl_Loaded;
        }

        [System.Runtime.InteropServices.DllImport("kernel32.dll", CharSet = System.Runtime.InteropServices.CharSet.Auto, SetLastError = true)]
        private static extern bool SetDllDirectory(string lpPathName);

        private async void MapaControl_Loaded(object sender, RoutedEventArgs e)
        {
            if (_isInitialized) return;
            await InicializarWebViewAsync();
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

                _isInitialized = true;
            }
            catch (Exception ex)
            {
                LoadingPanel.Visibility = Visibility.Collapsed;
                AtualizarStatus($"Erro ao carregar WebView2: {ex.Message}");
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
            if (WebView?.CoreWebView2 != null)
            {
                WebView.CoreWebView2.Reload();
            }
            else
            {
                await InicializarWebViewAsync();
            }
        }

        private void EnviarMensagemWeb(object obj)
        {
            if (WebView?.CoreWebView2 != null)
            {
                string json = JsonSerializer.Serialize(obj);
                WebView.CoreWebView2.PostWebMessageAsJson(json);
            }
        }

        private void AtualizarStatus(string texto)
        {
            Dispatcher.Invoke(() =>
            {
                TxtStatus.Text = texto;
            });
        }
    }
}
