using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace OxCad
{
    /// <summary>
    /// DTO representando um artefato de engenharia do Workspace.
    /// </summary>
    public class OxCadArtifactDto
    {
        [JsonPropertyName("chave")]
        public string Chave { get; set; } = string.Empty;

        [JsonPropertyName("rotulo")]
        public string Rotulo { get; set; } = string.Empty;

        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("existe")]
        public bool Existe { get; set; }

        [JsonPropertyName("icone")]
        public string Icone { get; set; } = "○";

        [JsonPropertyName("caminho")]
        public string? Caminho { get; set; }

        [JsonPropertyName("nome_arquivo")]
        public string? NomeArquivo { get; set; }
    }

    /// <summary>
    /// DTO representando o apontamento operacional de tempo de uma SOB/projeto.
    /// </summary>
    public class OxCadTimeEntryDto
    {
        [JsonPropertyName("sob_id")]
        public string SobId { get; set; } = "-";

        [JsonPropertyName("dwg_path")]
        public string? DwgPath { get; set; }

        [JsonPropertyName("estado")]
        public string Estado { get; set; } = "NaoIniciado";

        [JsonPropertyName("data_hora_inicio")]
        public string? DataHoraInicio { get; set; }

        [JsonPropertyName("data_hora_fim")]
        public string? DataHoraFim { get; set; }

        [JsonPropertyName("tempo_acumulado_segundos")]
        public double TempoAcumuladoSegundos { get; set; }

        [JsonPropertyName("sessao_atual_inicio")]
        public string? SessaoAtualInicio { get; set; }

        [JsonPropertyName("ultima_atualizacao")]
        public string? UltimaAtualizacao { get; set; }

        [JsonPropertyName("pid_processo")]
        public int? PidProcesso { get; set; }

        [JsonPropertyName("token_sessao")]
        public string? TokenSessao { get; set; }

        [JsonPropertyName("tempo_total_segundos")]
        public double TempoTotalSegundos { get; set; }

        [JsonPropertyName("tempo_formatado")]
        public string TempoFormatado { get; set; } = "00:00:00";

        [JsonPropertyName("inicio_formatado")]
        public string InicioFormatado { get; set; } = "-";

        [JsonPropertyName("fim_formatado")]
        public string FimFormatado { get; set; } = "-";
    }

    /// <summary>
    /// Contrato de contexto operacional completo (OxCadWorkspaceContext).
    /// </summary>
    public class OxCadWorkspaceContext
    {
        [JsonPropertyName("sob_id")]
        public string SobId { get; set; } = "-";

        [JsonPropertyName("root_dir")]
        public string RootDir { get; set; } = "-";

        [JsonPropertyName("dwg_principal")]
        public string DwgPrincipal { get; set; } = "-";

        [JsonPropertyName("municipio")]
        public string Municipio { get; set; } = "-";

        [JsonPropertyName("bairro")]
        public string Bairro { get; set; } = "-";

        [JsonPropertyName("endereco")]
        public string Endereco { get; set; } = "-";

        [JsonPropertyName("artefatos")]
        public List<OxCadArtifactDto> Artefatos { get; set; } = new List<OxCadArtifactDto>();

        [JsonPropertyName("tempo")]
        public OxCadTimeEntryDto? Tempo { get; set; }

        [JsonPropertyName("status")]
        public string Status { get; set; } = "Não consultado";

        [JsonPropertyName("inconsistencia")]
        public bool Inconsistencia { get; set; }

        [JsonPropertyName("mensagem_inconsistencia")]
        public string MensagemInconsistencia { get; set; } = string.Empty;

        [JsonPropertyName("erro")]
        public string? Erro { get; set; }
    }

    /// <summary>
    /// Serviço de integração pontual e não-residente com o backend Python do Workspace.
    /// Ciclo estrito: Iniciar processo -> Consultar -> Retornar JSON -> Encerrar.
    /// </summary>
    public static class WorkspaceService
    {
        private static readonly int TimeoutPadraoMilissegundos = 8000;

        /// <summary>
        /// Obtém o timeout configurado via variável de ambiente OXCAD_TIMEOUT_MS ou retorna o padrão (8000ms).
        /// </summary>
        public static int ObterTimeoutMilissegundos()
        {
            try
            {
                string? envTimeout = Environment.GetEnvironmentVariable("OXCAD_TIMEOUT_MS");
                if (!string.IsNullOrWhiteSpace(envTimeout) && int.TryParse(envTimeout, out int ms) && ms >= 1000)
                {
                    return ms;
                }
            }
            catch { }

            return TimeoutPadraoMilissegundos;
        }

        private static string? _instanciaSessionToken;

        /// <summary>
        /// Token imutável e exclusivo da sessão em execução do AutoCAD host.
        /// Combina PID, start ticks UTC do processo e um GUID aleatório para
        /// imunidade total contra reciclagem de PID pelo sistema operacional Windows.
        /// </summary>
        public static string InstanciaSessionToken
        {
            get
            {
                if (_instanciaSessionToken == null)
                {
                    try
                    {
                        var proc = Process.GetCurrentProcess();
                        long startTicks = 0;
                        try
                        {
                            startTicks = proc.StartTime.ToUniversalTime().Ticks;
                        }
                        catch { }
                        _instanciaSessionToken = $"{proc.Id}_{startTicks:X}_{Guid.NewGuid():N}";
                    }
                    catch
                    {
                        _instanciaSessionToken = $"{Process.GetCurrentProcess().Id}_{Guid.NewGuid():N}";
                    }
                }
                return _instanciaSessionToken;
            }
        }

        /// <summary>
        /// Extrai o payload JSON válido contido na saída, descartando quaisquer logs,
        /// warnings ou mensagens espúrias impressas antes do primeiro '{' ou após o último '}'.
        /// </summary>
        public static string ExtrairJsonValido(string? saida)
        {
            if (string.IsNullOrWhiteSpace(saida))
                return string.Empty;

            string s = saida!;
            int idxInicio = s.IndexOf('{');
            int idxFim = s.LastIndexOf('}');

            if (idxInicio >= 0 && idxFim > idxInicio)
            {
                return s.Substring(idxInicio, idxFim - idxInicio + 1).Trim();
            }

            return s.Trim();
        }

        /// <summary>
        /// Encerra o processo e toda a sua árvore de processos filhos, evitando processos órfãos ou zumbis.
        /// </summary>
        public static void EncerrarProcessoETodosOsFilhos(Process proc)
        {
            try
            {
                if (proc.HasExited) return;

                // No Windows, taskkill /F /T garante eliminação atômica do processo e de toda a árvore de subprocessos
                if (Environment.OSVersion.Platform == PlatformID.Win32NT)
                {
                    try
                    {
                        var psiKill = new ProcessStartInfo
                        {
                            FileName = "taskkill.exe",
                            Arguments = $"/F /T /PID {proc.Id}",
                            CreateNoWindow = true,
                            UseShellExecute = false
                        };
                        using (var killProc = Process.Start(psiKill))
                        {
                            killProc?.WaitForExit(1000);
                        }
                    }
                    catch { }
                }

                if (!proc.HasExited)
                {
                    proc.Kill();
                }
            }
            catch { }
        }

        /// <summary>
        /// Localiza o diretório raiz do projeto aux cad através de múltiplos fallbacks determinísticos.
        /// </summary>
        public static string ObterDiretorioRaizProjeto(string? dwgFullPath = null)
        {
            // 1. Variável de ambiente AUXCAD_ROOT se definida e válida
            try
            {
                string? envRoot = Environment.GetEnvironmentVariable("AUXCAD_ROOT");
                if (!string.IsNullOrWhiteSpace(envRoot) && Directory.Exists(envRoot))
                {
                    if (File.Exists(Path.Combine(envRoot, "acaddoc.lsp")) || Directory.Exists(Path.Combine(envRoot, "workspace")))
                        return envRoot;
                }
            }
            catch { }

            // 2. Busca subindo a árvore de diretórios a partir do assembly carregado
            try
            {
                string assemblyPath = typeof(WorkspaceService).Assembly.Location;
                if (!string.IsNullOrEmpty(assemblyPath))
                {
                    string? dir = Path.GetDirectoryName(assemblyPath);
                    while (!string.IsNullOrEmpty(dir))
                    {
                        if (File.Exists(Path.Combine(dir, "acaddoc.lsp")) ||
                            Directory.Exists(Path.Combine(dir, "workspace")))
                        {
                            return dir;
                        }
                        dir = Path.GetDirectoryName(dir);
                    }
                }
            }
            catch { }

            // 3. Busca a partir do diretório do arquivo DWG se informado
            if (!string.IsNullOrWhiteSpace(dwgFullPath))
            {
                try
                {
                    string? dirDwg = Path.GetDirectoryName(dwgFullPath);
                    while (!string.IsNullOrEmpty(dirDwg))
                    {
                        if (File.Exists(Path.Combine(dirDwg, "acaddoc.lsp")) ||
                            Directory.Exists(Path.Combine(dirDwg, "workspace")))
                        {
                            return dirDwg;
                        }
                        dirDwg = Path.GetDirectoryName(dirDwg);
                    }
                }
                catch { }
            }

            // 4. Fallback no diretório atual de trabalho
            try
            {
                string curr = Directory.GetCurrentDirectory();
                if (File.Exists(Path.Combine(curr, "acaddoc.lsp")) || Directory.Exists(Path.Combine(curr, "workspace")))
                {
                    return curr;
                }
            }
            catch { }

            return Directory.GetCurrentDirectory();
        }

        /// <summary>
        /// Localiza o executável do Python de forma determinística no sistema.
        /// </summary>
        public static string ObterExecutavelPython()
        {
            // 1. Variável de ambiente PYTHON_EXECUTABLE se definida
            string? envPy = Environment.GetEnvironmentVariable("PYTHON_EXECUTABLE");
            if (!string.IsNullOrWhiteSpace(envPy) && File.Exists(envPy))
                return envPy;

            // 2. Diretórios conhecidos no AppData do usuário
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            if (!string.IsNullOrEmpty(localAppData))
            {
                // WindowsApps (Python da Microsoft Store)
                string winApps = Path.Combine(localAppData, "Microsoft", "WindowsApps");
                string pyStore = Path.Combine(winApps, "python.exe");
                if (File.Exists(pyStore))
                    return pyStore;

                // Programs/Python
                string progPy = Path.Combine(localAppData, "Programs", "Python");
                if (Directory.Exists(progPy))
                {
                    var dirs = Directory.GetDirectories(progPy, "Python3*");
                    foreach (var d in dirs)
                    {
                        string cand = Path.Combine(d, "python.exe");
                        if (File.Exists(cand)) return cand;
                    }
                }
            }

            // 3. Pastas padrão no C:\
            try
            {
                var raizes = new[] { @"C:\", @"C:\Program Files", @"C:\Program Files (x86)" };
                foreach (var r in raizes)
                {
                    if (Directory.Exists(r))
                    {
                        var pyDirs = Directory.GetDirectories(r, "Python3*");
                        foreach (var d in pyDirs)
                        {
                            string cand = Path.Combine(d, "python.exe");
                            if (File.Exists(cand)) return cand;
                        }
                    }
                }
            }
            catch { }

            // 4. Fallback no PATH global
            return "python.exe";
        }

        /// <summary>
        /// Executa a consulta de contexto de forma assíncrona, desacoplada e segura.
        /// </summary>
        public static async Task<OxCadWorkspaceContext> ConsultarContextoAsync(string? dwgFullPath)
        {
            return await Task.Run(() =>
            {
                var contexto = new OxCadWorkspaceContext();

                try
                {
                    if (string.IsNullOrWhiteSpace(dwgFullPath) || !File.Exists(dwgFullPath))
                    {
                        contexto.Status = "Desenho ainda não salvo.";
                        contexto.DwgPrincipal = "Desenho ainda não salvo.";
                        return contexto;
                    }

                    string rootDir = ObterDiretorioRaizProjeto(dwgFullPath);
                    string scriptPath = Path.Combine(rootDir, "workspace", "workspace_context_cli.py");

                    if (!File.Exists(scriptPath))
                    {
                        contexto.Status = "Script de contexto não localizado.";
                        contexto.Erro = $"Arquivo não encontrado: {scriptPath}";
                        return contexto;
                    }

                    string pythonExe = ObterExecutavelPython();
                    int timeout = ObterTimeoutMilissegundos();
                    int currentPid = Process.GetCurrentProcess().Id;
                    string sessionToken = InstanciaSessionToken;

                    var psi = new ProcessStartInfo
                    {
                        FileName = pythonExe,
                        Arguments = $"\"{scriptPath}\" --dwg \"{dwgFullPath}\" --acad-pid {currentPid} --acad-token \"{sessionToken}\"",
                        WorkingDirectory = rootDir,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        StandardOutputEncoding = Encoding.UTF8,
                        StandardErrorEncoding = Encoding.UTF8
                    };

                    using (var proc = new Process { StartInfo = psi })
                    {
                        var outputBuilder = new StringBuilder();
                        var errorBuilder = new StringBuilder();

                        proc.OutputDataReceived += (s, e) => { if (e.Data != null) outputBuilder.AppendLine(e.Data); };
                        proc.ErrorDataReceived += (s, e) => { if (e.Data != null) errorBuilder.AppendLine(e.Data); };

                        try
                        {
                            proc.Start();
                        }
                        catch (System.ComponentModel.Win32Exception winEx)
                        {
                            contexto.Status = "Python não encontrado no sistema.";
                            contexto.Erro = $"Não foi possível iniciar o executável '{pythonExe}'. Configure a variável de ambiente PYTHON_EXECUTABLE. Detalhes: {winEx.Message}";
                            return contexto;
                        }

                        proc.BeginOutputReadLine();
                        proc.BeginErrorReadLine();

                        bool finished = proc.WaitForExit(timeout);

                        if (!finished)
                        {
                            EncerrarProcessoETodosOsFilhos(proc);
                            contexto.Status = "Tempo limite excedido.";
                            contexto.Erro = "A consulta ao Workspace demorou mais que o esperado.";
                            return contexto;
                        }

                        string saidaBruta = outputBuilder.ToString();
                        string saidaLimpa = ExtrairJsonValido(saidaBruta);
                        string erros = errorBuilder.ToString().Trim();

                        if (proc.ExitCode != 0 && string.IsNullOrWhiteSpace(saidaLimpa))
                        {
                            contexto.Status = "Falha no processo Python.";
                            contexto.Erro = string.IsNullOrWhiteSpace(erros) ? $"Exit Code {proc.ExitCode}" : erros;
                            return contexto;
                        }

                        // Desserialização do JSON limpo
                        var options = new JsonSerializerOptions
                        {
                            PropertyNameCaseInsensitive = true
                        };

                        try
                        {
                            var resultado = JsonSerializer.Deserialize<OxCadWorkspaceContext>(saidaLimpa, options);
                            if (resultado != null)
                            {
                                return resultado;
                            }
                        }
                        catch (Exception exJson)
                        {
                            contexto.Status = "Resposta JSON inválida.";
                            contexto.Erro = $"Falha ao interpretar JSON: {exJson.Message}. Saída recebida: {saidaBruta}";
                            return contexto;
                        }

                        contexto.Status = "Resposta JSON inválida.";
                        contexto.Erro = saidaBruta;
                    }
                }
                catch (Exception ex)
                {
                    contexto.Status = "Exceção ao consultar Workspace.";
                    contexto.Erro = ex.Message;
                }

                return contexto;
            });
        }

        /// <summary>
        /// Executa uma ação de engenharia de forma assíncrona através do WorkspaceActionDispatcher.
        /// </summary>
        public static async Task<OxCadActionResult> ExecutarAcaoAsync(string acao, string? dwgFullPath, string? alvo = null)
        {
            return await Task.Run(() =>
            {
                var resultado = new OxCadActionResult
                {
                    Acao = acao,
                    Estado = "Executando..."
                };

                try
                {
                    string rootDir = ObterDiretorioRaizProjeto(dwgFullPath);
                    string scriptPath = Path.Combine(rootDir, "workspace", "workspace_context_cli.py");

                    if (!File.Exists(scriptPath))
                    {
                        resultado.Sucesso = false;
                        resultado.Estado = "Falhou";
                        resultado.Mensagem = "Script do Workspace não encontrado.";
                        resultado.Erro = $"Arquivo não encontrado: {scriptPath}";
                        return resultado;
                    }

                    string pythonExe = ObterExecutavelPython();
                    int timeout = ObterTimeoutMilissegundos();

                    var argsBuilder = new StringBuilder();
                    argsBuilder.Append($"\"{scriptPath}\" --acao \"{acao}\"");

                    if (!string.IsNullOrWhiteSpace(dwgFullPath) && File.Exists(dwgFullPath))
                    {
                        argsBuilder.Append($" --dwg \"{dwgFullPath}\"");
                    }

                    if (!string.IsNullOrWhiteSpace(alvo))
                    {
                        argsBuilder.Append($" --alvo \"{alvo}\"");
                    }

                    int currentPid = Process.GetCurrentProcess().Id;
                    string sessionToken = InstanciaSessionToken;
                    argsBuilder.Append($" --acad-pid {currentPid} --acad-token \"{sessionToken}\"");

                    var psi = new ProcessStartInfo
                    {
                        FileName = pythonExe,
                        Arguments = argsBuilder.ToString(),
                        WorkingDirectory = rootDir,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        StandardOutputEncoding = Encoding.UTF8,
                        StandardErrorEncoding = Encoding.UTF8
                    };

                    using (var proc = new Process { StartInfo = psi })
                    {
                        var outputBuilder = new StringBuilder();
                        var errorBuilder = new StringBuilder();

                        proc.OutputDataReceived += (s, e) => { if (e.Data != null) outputBuilder.AppendLine(e.Data); };
                        proc.ErrorDataReceived += (s, e) => { if (e.Data != null) errorBuilder.AppendLine(e.Data); };

                        try
                        {
                            proc.Start();
                        }
                        catch (System.ComponentModel.Win32Exception winEx)
                        {
                            resultado.Sucesso = false;
                            resultado.Estado = "Falhou";
                            resultado.Mensagem = "Python não encontrado no sistema.";
                            resultado.Erro = $"Não foi possível iniciar o executável '{pythonExe}': {winEx.Message}";
                            return resultado;
                        }

                        proc.BeginOutputReadLine();
                        proc.BeginErrorReadLine();

                        bool finished = proc.WaitForExit(timeout);

                        if (!finished)
                        {
                            EncerrarProcessoETodosOsFilhos(proc);
                            resultado.Sucesso = false;
                            resultado.Estado = "Falhou";
                            resultado.Mensagem = "Tempo limite excedido na execução da ação.";
                            resultado.Erro = "Timeout";
                            return resultado;
                        }

                        string saidaBruta = outputBuilder.ToString();
                        string saidaLimpa = ExtrairJsonValido(saidaBruta);
                        string erros = errorBuilder.ToString().Trim();

                        var options = new JsonSerializerOptions
                        {
                            PropertyNameCaseInsensitive = true
                        };

                        if (!string.IsNullOrWhiteSpace(saidaLimpa))
                        {
                            try
                            {
                                var resDeserializado = JsonSerializer.Deserialize<OxCadActionResult>(saidaLimpa, options);
                                if (resDeserializado != null)
                                {
                                    return resDeserializado;
                                }
                            }
                            catch
                            {
                                // Fallback caso não seja JSON
                            }
                        }

                        resultado.Sucesso = (proc.ExitCode == 0);
                        resultado.Estado = proc.ExitCode == 0 ? "Concluído" : "Falhou";
                        resultado.Mensagem = string.IsNullOrWhiteSpace(saidaLimpa) ? (string.IsNullOrWhiteSpace(erros) ? $"Processo finalizado com exit code {proc.ExitCode}." : erros) : saidaLimpa;
                        if (proc.ExitCode != 0)
                        {
                            resultado.Erro = erros;
                        }
                    }
                }
                catch (Exception ex)
                {
                    resultado.Sucesso = false;
                    resultado.Estado = "Falhou";
                    resultado.Mensagem = $"Exceção ao disparar ação: {ex.Message}";
                    resultado.Erro = ex.Message;
                }

                return resultado;
            });
        }

        /// <summary>
        /// Envia um comando de controle de tempo para o backend Python (iniciar, pausar, retomar, concluir, reabrir).
        /// </summary>
        public static async Task<OxCadActionResult> ControlarTempoAsync(string acaoTempo, string? dwgFullPath)
        {
            string acaoNormalizada = acaoTempo.StartsWith("tempo_") ? acaoTempo : $"tempo_{acaoTempo}";
            return await ExecutarAcaoAsync(acaoNormalizada, dwgFullPath);
        }
    }

    /// <summary>
    /// DTO representando o resultado da execução de uma ação de Workspace.
    /// </summary>
    public class OxCadActionResult
    {
        [JsonPropertyName("sucesso")]
        public bool Sucesso { get; set; }

        [JsonPropertyName("acao")]
        public string Acao { get; set; } = string.Empty;

        [JsonPropertyName("estado")]
        public string Estado { get; set; } = "Pronto";

        [JsonPropertyName("mensagem")]
        public string Mensagem { get; set; } = string.Empty;

        [JsonPropertyName("pid")]
        public int? Pid { get; set; }

        [JsonPropertyName("erro")]
        public string? Erro { get; set; }
    }
}

