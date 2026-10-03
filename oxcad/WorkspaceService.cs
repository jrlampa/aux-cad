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

        [JsonPropertyName("project_scope_status")]
        public string ProjectScopeStatus { get; set; } = "NotRequired";

        [JsonPropertyName("project_scope_resolved")]
        public bool ProjectScopeResolved { get; set; }

        [JsonPropertyName("project_scope_candidates")]
        public List<string> ProjectScopeCandidates { get; set; } = new List<string>();
    }

    public sealed class OxCadVerifiedDwgContext
    {
        public OxCadVerifiedDwgContext(
            string sobId, string dwgPath, string dwgIdentity,
            long contextGeneration, string? executionId = null,
            string? correlationId = null)
        {
            SobId = sobId;
            DwgPath = dwgPath;
            DwgIdentity = dwgIdentity;
            ContextGeneration = contextGeneration;
            ExecutionId = executionId;
            CorrelationId = correlationId;
        }

        [JsonPropertyName("contract_version")]
        public int ContractVersion => 1;

        [JsonPropertyName("project_scope_status")]
        public string ProjectScopeStatus => "Bound";

        [JsonPropertyName("sob_id")]
        public string SobId { get; }

        [JsonPropertyName("dwg_path")]
        public string DwgPath { get; }

        [JsonPropertyName("dwg_identity")]
        public string DwgIdentity { get; }

        [JsonPropertyName("context_generation")]
        public long ContextGeneration { get; }

        [JsonPropertyName("execution_id")]
        public string? ExecutionId { get; }

        [JsonPropertyName("correlation_id")]
        public string? CorrelationId { get; }
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
        public static async Task<OxCadWorkspaceContext> ConsultarContextoAsync(
            string? dwgFullPath,
            string? correlationId = null,
            string? sobId = null,
            OxCadVerifiedDwgContext? verifiedContext = null)
        {
            correlationId ??= Guid.NewGuid().ToString("N");
            var sw = Stopwatch.StartNew();

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

                    OxCadLogger.LogInfo(
                        $"Iniciando consulta de contexto para DWG: {Path.GetFileName(dwgFullPath)}",
                        correlationId: correlationId,
                        dwgPath: dwgFullPath,
                        action: "consultar_contexto"
                    );

                    string rootDir = ObterDiretorioRaizProjeto(dwgFullPath);
                    string scriptPath = Path.Combine(rootDir, "workspace", "workspace_context_cli.py");

                    if (!File.Exists(scriptPath))
                    {
                        contexto.Status = "Script de contexto não localizado.";
                        contexto.Erro = $"Arquivo não encontrado: {scriptPath}";
                        OxCadLogger.LogError(
                            $"Script de contexto não localizado: {scriptPath}",
                            correlationId: correlationId,
                            dwgPath: dwgFullPath,
                            action: "consultar_contexto"
                        );
                        return contexto;
                    }

                    string pythonExe = ObterExecutavelPython();
                    int timeout = ObterTimeoutMilissegundos();
                    int currentPid = Process.GetCurrentProcess().Id;
                    string sessionToken = InstanciaSessionToken;
                    string scopeArgument = string.IsNullOrWhiteSpace(sobId) ? string.Empty : $" --sob \"{sobId}\"";

                    var psi = new ProcessStartInfo
                    {
                        FileName = pythonExe,
                        Arguments = $"\"{scriptPath}\" --dwg \"{dwgFullPath}\"{scopeArgument} --require-project-scope{(verifiedContext != null ? " --host-context-stdin" : "")} --acad-pid {currentPid} --acad-token \"{sessionToken}\" --correlation-id \"{correlationId}\"",
                        WorkingDirectory = rootDir,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        RedirectStandardInput = verifiedContext != null,
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
                            if (verifiedContext != null)
                            {
                                proc.StandardInput.WriteLine(JsonSerializer.Serialize(verifiedContext));
                                proc.StandardInput.Close();
                            }
                        }
                        catch (System.ComponentModel.Win32Exception winEx)
                        {
                            sw.Stop();
                            contexto.Status = "Python não encontrado no sistema.";
                            contexto.Erro = $"Não foi possível iniciar o executável '{pythonExe}'. Configure a variável de ambiente PYTHON_EXECUTABLE. Detalhes: {winEx.Message}";
                            OxCadLogger.LogError(
                                $"Falha ao iniciar executável Python '{pythonExe}' ({sw.Elapsed.TotalMilliseconds:F1}ms)",
                                winEx,
                                correlationId: correlationId,
                                dwgPath: dwgFullPath,
                                action: "consultar_contexto"
                            );
                            return contexto;
                        }

                        proc.BeginOutputReadLine();
                        proc.BeginErrorReadLine();

                        bool finished = proc.WaitForExit(timeout);

                        if (!finished)
                        {
                            EncerrarProcessoETodosOsFilhos(proc);
                            sw.Stop();
                            contexto.Status = "Tempo limite excedido.";
                            contexto.Erro = "A consulta ao Workspace demorou mais que o esperado.";
                            OxCadLogger.LogError(
                                $"Timeout na consulta de contexto ({sw.Elapsed.TotalMilliseconds:F1}ms)",
                                correlationId: correlationId,
                                dwgPath: dwgFullPath,
                                action: "consultar_contexto"
                            );
                            return contexto;
                        }

                        sw.Stop();
                        double durationMs = sw.Elapsed.TotalMilliseconds;

                        string saidaBruta = outputBuilder.ToString();
                        string saidaLimpa = ExtrairJsonValido(saidaBruta);
                        string erros = errorBuilder.ToString().Trim();

                        if (proc.ExitCode != 0 && string.IsNullOrWhiteSpace(saidaLimpa))
                        {
                            contexto.Status = "Falha no processo Python.";
                            contexto.Erro = string.IsNullOrWhiteSpace(erros) ? $"Exit Code {proc.ExitCode}" : erros;
                            OxCadLogger.LogError(
                                $"Processo Python encerrou com exit code {proc.ExitCode} ({durationMs:F1}ms): {contexto.Erro}",
                                correlationId: correlationId,
                                dwgPath: dwgFullPath,
                                action: "consultar_contexto"
                            );
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
                                OxCadLogger.LogInfo(
                                    $"Consulta de contexto concluída com sucesso ({durationMs:F1}ms)",
                                    correlationId: correlationId,
                                    sobId: resultado.SobId,
                                    dwgPath: dwgFullPath,
                                    action: "consultar_contexto",
                                    durationMs: durationMs,
                                    result: "sucesso"
                                );
                                return resultado;
                            }
                        }
                        catch (Exception exJson)
                        {
                            contexto.Status = "Resposta JSON inválida.";
                            contexto.Erro = $"Falha ao interpretar JSON: {exJson.Message}. Saída recebida: {saidaBruta}";
                            OxCadLogger.LogError(
                                $"Falha ao interpretar JSON de contexto ({durationMs:F1}ms)",
                                exJson,
                                correlationId: correlationId,
                                dwgPath: dwgFullPath,
                                action: "consultar_contexto"
                            );
                            return contexto;
                        }

                        contexto.Status = "Resposta JSON inválida.";
                        contexto.Erro = saidaBruta;
                    }
                }
                catch (Exception ex)
                {
                    sw.Stop();
                    contexto.Status = "Exceção ao consultar Workspace.";
                    contexto.Erro = ex.Message;
                    OxCadLogger.LogError(
                        $"Exceção não tratada na consulta de contexto ({sw.Elapsed.TotalMilliseconds:F1}ms)",
                        ex,
                        correlationId: correlationId,
                        dwgPath: dwgFullPath,
                        action: "consultar_contexto"
                    );
                }

                return contexto;
            });
        }

        /// <summary>
        /// Executa uma ação de engenharia de forma assíncrona através do WorkspaceActionDispatcher.
        /// </summary>
        public static async Task<OxCadActionResult> ExecutarAcaoAsync(
            string acao,
            string? dwgFullPath,
            string? alvo = null,
            string? correlationId = null,
            string? sobId = null,
            bool requireProjectScope = false,
            string? executionId = null,
            string? dwgIdentity = null,
            string executionOrigin = "oxcad.palette",
            bool waitForCompletion = false,
            bool executionManagedByHost = false,
            List<string>? validationRules = null,
            OxCadVerifiedDwgContext? verifiedContext = null)
        {
            correlationId ??= Guid.NewGuid().ToString("N");
            var sw = Stopwatch.StartNew();

            return await Task.Run(() =>
            {
                var resultado = new OxCadActionResult
                {
                    Acao = acao,
                    Estado = "Executando...",
                    CorrelationId = correlationId,
                    ExecutionId = executionId,
                    SobId = sobId,
                    DwgPath = dwgFullPath,
                    DwgIdentity = dwgIdentity,
                    Origin = executionOrigin,
                    ExecutionState = "Executando"
                };

                try
                {
                    OxCadLogger.LogInfo(
                        $"Iniciando ação '{acao}' (alvo: {(string.IsNullOrWhiteSpace(alvo) ? "-" : Path.GetFileName(alvo))})",
                        correlationId: correlationId,
                        dwgPath: dwgFullPath,
                        action: acao,
                        executionId: executionId
                    );

                    string rootDir = ObterDiretorioRaizProjeto(dwgFullPath);
                    string scriptPath = Path.Combine(rootDir, "workspace", "workspace_context_cli.py");

                    if (!File.Exists(scriptPath))
                    {
                        sw.Stop();
                        resultado.Sucesso = false;
                        resultado.Estado = "Falhou";
                        resultado.Mensagem = "Script do Workspace não encontrado.";
                        resultado.Erro = $"Arquivo não encontrado: {scriptPath}";
                        resultado.DurationMs = sw.Elapsed.TotalMilliseconds;
                        OxCadLogger.LogError(
                            $"Script do Workspace não encontrado: {scriptPath}",
                            correlationId: correlationId,
                            dwgPath: dwgFullPath,
                            action: acao,
                            executionId: executionId
                        );
                        return resultado;
                    }

                    string pythonExe = ObterExecutavelPython();
                    int timeout = ObterTimeoutMilissegundos();

                    var argsBuilder = new StringBuilder();
                    argsBuilder.Append($"\"{scriptPath}\" --acao \"{acao}\"");

                    if (requireProjectScope)
                    {
                        argsBuilder.Append(" --require-project-scope");
                        if (verifiedContext == null && !string.IsNullOrWhiteSpace(sobId))
                        {
                            argsBuilder.Append($" --sob \"{sobId}\"");
                        }
                    }

                    if (!string.IsNullOrWhiteSpace(executionId))
                        argsBuilder.Append($" --execution-id \"{executionId}\"");
                    if (verifiedContext == null && !string.IsNullOrWhiteSpace(dwgIdentity))
                        argsBuilder.Append($" --dwg-identity \"{dwgIdentity}\"");
                    if (!string.IsNullOrWhiteSpace(executionOrigin))
                        argsBuilder.Append($" --execution-origin \"{executionOrigin}\"");
                    if (waitForCompletion)
                        argsBuilder.Append(" --wait-for-completion");
                    if (executionManagedByHost)
                        argsBuilder.Append(" --execution-managed-by-host");
                    if (validationRules != null)
                    {
                        foreach (string rule in validationRules)
                            argsBuilder.Append($" --validation-rule \"{rule}\"");
                    }

                    if (verifiedContext == null && !string.IsNullOrWhiteSpace(dwgFullPath) && File.Exists(dwgFullPath))
                    {
                        argsBuilder.Append($" --dwg \"{dwgFullPath}\"");
                    }

                    if (!string.IsNullOrWhiteSpace(alvo))
                    {
                        argsBuilder.Append($" --alvo \"{alvo}\"");
                    }

                    int currentPid = Process.GetCurrentProcess().Id;
                    string sessionToken = InstanciaSessionToken;
                    argsBuilder.Append($" --acad-pid {currentPid} --acad-token \"{sessionToken}\" --correlation-id \"{correlationId}\"");
                    if (verifiedContext != null)
                        argsBuilder.Append(" --host-context-stdin");

                    var psi = new ProcessStartInfo
                    {
                        FileName = pythonExe,
                        Arguments = argsBuilder.ToString(),
                        WorkingDirectory = rootDir,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        RedirectStandardInput = verifiedContext != null,
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
                            if (verifiedContext != null)
                            {
                                proc.StandardInput.WriteLine(JsonSerializer.Serialize(verifiedContext));
                                proc.StandardInput.Close();
                            }
                        }
                        catch (System.ComponentModel.Win32Exception winEx)
                        {
                            sw.Stop();
                            resultado.Sucesso = false;
                            resultado.Estado = "Falhou";
                            resultado.Mensagem = "Python não encontrado no sistema.";
                            resultado.Erro = $"Não foi possível iniciar o executável '{pythonExe}': {winEx.Message}";
                            resultado.DurationMs = sw.Elapsed.TotalMilliseconds;
                            OxCadLogger.LogError(
                                $"Falha ao iniciar executável Python '{pythonExe}' na ação '{acao}' ({sw.Elapsed.TotalMilliseconds:F1}ms)",
                                winEx,
                                correlationId: correlationId,
                                dwgPath: dwgFullPath,
                                action: acao,
                                executionId: executionId
                            );
                            return resultado;
                        }

                        proc.BeginOutputReadLine();
                        proc.BeginErrorReadLine();

                        bool finished;
                        if (waitForCompletion)
                        {
                            proc.WaitForExit();
                            finished = true;
                        }
                        else
                        {
                            finished = proc.WaitForExit(timeout);
                        }

                        if (!finished)
                        {
                            EncerrarProcessoETodosOsFilhos(proc);
                            sw.Stop();
                            resultado.Sucesso = false;
                            resultado.Estado = "Falhou";
                            resultado.Mensagem = "Tempo limite excedido na execução da ação.";
                            resultado.Erro = "Timeout";
                            resultado.DurationMs = sw.Elapsed.TotalMilliseconds;
                            OxCadLogger.LogError(
                                $"Timeout na ação '{acao}' ({sw.Elapsed.TotalMilliseconds:F1}ms)",
                                correlationId: correlationId,
                                dwgPath: dwgFullPath,
                                action: acao,
                                executionId: executionId
                            );
                            return resultado;
                        }

                        sw.Stop();
                        double durationMs = sw.Elapsed.TotalMilliseconds;
                        resultado.DurationMs = durationMs;

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
                                    resDeserializado.CorrelationId = correlationId;
                                    resDeserializado.ExecutionId = executionId ?? resDeserializado.ExecutionId;
                                    resDeserializado.SobId = sobId ?? resDeserializado.SobId;
                                    resDeserializado.DwgPath = dwgFullPath ?? resDeserializado.DwgPath;
                                    resDeserializado.DwgIdentity = dwgIdentity ?? resDeserializado.DwgIdentity;
                                    resDeserializado.Origin = executionOrigin;
                                    resDeserializado.DurationMs = durationMs;
                                    if (resDeserializado.Sucesso)
                                    {
                                        OxCadLogger.LogInfo(
                                            $"Ação '{acao}' executada com sucesso ({durationMs:F1}ms)",
                                            correlationId: correlationId,
                                            dwgPath: dwgFullPath,
                                            action: acao,
                                            durationMs: durationMs,
                                            result: "sucesso",
                                            executionId: executionId
                                        );
                                    }
                                    else
                                    {
                                        OxCadLogger.LogError(
                                            $"Ação '{acao}' retornou insucesso ({durationMs:F1}ms): {resDeserializado.Mensagem}",
                                            correlationId: correlationId,
                                            dwgPath: dwgFullPath,
                                            action: acao,
                                            executionId: executionId
                                        );
                                    }
                                    return resDeserializado;
                                }
                            }
                            catch (Exception exJson)
                            {
                                OxCadLogger.LogWarning(
                                    $"Aviso: Resposta da ação '{acao}' não era JSON válido: {exJson.Message}",
                                    correlationId: correlationId,
                                    dwgPath: dwgFullPath,
                                    action: acao,
                                    executionId: executionId
                                );
                            }
                        }

                        resultado.Sucesso = (proc.ExitCode == 0);
                        resultado.Estado = proc.ExitCode == 0 ? "Concluído" : "Falhou";
                        resultado.Mensagem = string.IsNullOrWhiteSpace(saidaLimpa) ? (string.IsNullOrWhiteSpace(erros) ? $"Processo finalizado com exit code {proc.ExitCode}." : erros) : saidaLimpa;
                        if (proc.ExitCode != 0)
                        {
                            resultado.Erro = erros;
                            OxCadLogger.LogError(
                                $"Ação '{acao}' encerrou com exit code {proc.ExitCode} ({durationMs:F1}ms): {resultado.Mensagem}",
                                correlationId: correlationId,
                                dwgPath: dwgFullPath,
                                action: acao,
                                executionId: executionId
                            );
                        }
                        else
                        {
                            OxCadLogger.LogInfo(
                                $"Ação '{acao}' finalizada com sucesso ({durationMs:F1}ms)",
                                correlationId: correlationId,
                                dwgPath: dwgFullPath,
                                action: acao,
                                durationMs: durationMs,
                                result: "sucesso",
                                executionId: executionId
                            );
                        }
                    }
                }
                catch (Exception ex)
                {
                    sw.Stop();
                    resultado.Sucesso = false;
                    resultado.Estado = "Falhou";
                    resultado.Mensagem = $"Exceção ao disparar ação: {ex.Message}";
                    resultado.Erro = ex.Message;
                    resultado.DurationMs = sw.Elapsed.TotalMilliseconds;
                    OxCadLogger.LogError(
                        $"Exceção não tratada ao disparar ação '{acao}' ({sw.Elapsed.TotalMilliseconds:F1}ms)",
                        ex,
                        correlationId: correlationId,
                        dwgPath: dwgFullPath,
                        action: acao,
                        executionId: executionId
                    );
                }

                return resultado;
            });
        }

        /// <summary>
        /// Envia um comando de controle de tempo para o backend Python (iniciar, pausar, retomar, concluir, reabrir).
        /// </summary>
        public static async Task<OxCadActionResult> ControlarTempoAsync(
            string acaoTempo,
            string? dwgFullPath,
            string? correlationId = null,
            string? sobId = null,
            bool requireProjectScope = false,
            string? executionId = null,
            string? dwgIdentity = null,
            string executionOrigin = "oxcad.palette",
            bool waitForCompletion = false,
            bool executionManagedByHost = false,
            OxCadVerifiedDwgContext? verifiedContext = null)
        {
            string acaoNormalizada = acaoTempo.StartsWith("tempo_") ? acaoTempo : $"tempo_{acaoTempo}";
            return await ExecutarAcaoAsync(
                acaoNormalizada,
                dwgFullPath,
                correlationId: correlationId,
                sobId: sobId,
                requireProjectScope: requireProjectScope,
                executionId: executionId,
                dwgIdentity: dwgIdentity,
                executionOrigin: executionOrigin,
                waitForCompletion: waitForCompletion,
                executionManagedByHost: executionManagedByHost,
                verifiedContext: verifiedContext);
        }

        /// <summary>
        /// P2.2: Consulta analítica e operacional de indicadores de processo e gestão (SOB / Workspace).
        /// Totalmente read-only, não entra no ciclo OxCadExecutionRegistry e não cria execuções operacionais.
        /// </summary>
        public static async Task<string> ConsultarIndicadoresJsonAsync(
            string? projectRoot = null,
            string? sobId = null,
            string? workspaceRoot = null,
            string? acao = null,
            string? estado = null,
            string? logFile = null,
            string? compareStart = null,
            string? compareEnd = null)
        {
            return await Task.Run(() =>
            {
                try
                {
                    string rootDir = ObterDiretorioRaizProjeto(projectRoot ?? workspaceRoot);
                    string scriptPath = Path.Combine(rootDir, "workspace", "workspace_indicators_cli.py");
                    if (!File.Exists(scriptPath))
                    {
                        scriptPath = Path.Combine(rootDir, "workspace", "workspace_indicators.py");
                    }

                    if (!File.Exists(scriptPath))
                    {
                        return "{\"status\": \"NÃO DISPONÍVEL\", \"erro\": \"Script de indicadores não localizado.\"}";
                    }

                    string pythonExe = ObterExecutavelPython();
                    int timeout = ObterTimeoutMilissegundos();

                    var sbArgs = new StringBuilder();
                    sbArgs.Append($"\"{scriptPath}\"");

                    if (!string.IsNullOrWhiteSpace(projectRoot) && Directory.Exists(projectRoot))
                    {
                        sbArgs.Append($" --project-root \"{projectRoot}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(sobId))
                    {
                        sbArgs.Append($" --sob \"{sobId}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(workspaceRoot) && Directory.Exists(workspaceRoot))
                    {
                        sbArgs.Append($" --workspace-root \"{workspaceRoot}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(acao))
                    {
                        sbArgs.Append($" --action \"{acao}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(estado))
                    {
                        sbArgs.Append($" --state \"{estado}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(logFile) && File.Exists(logFile))
                    {
                        sbArgs.Append($" --log-file \"{logFile}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(compareStart))
                    {
                        sbArgs.Append($" --compare-start \"{compareStart}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(compareEnd))
                    {
                        sbArgs.Append($" --compare-end \"{compareEnd}\"");
                    }

                    var psi = new ProcessStartInfo
                    {
                        FileName = pythonExe,
                        Arguments = sbArgs.ToString(),
                        WorkingDirectory = rootDir,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        StandardOutputEncoding = Encoding.UTF8,
                        StandardErrorEncoding = Encoding.UTF8
                    };

                    using var proc = new Process { StartInfo = psi };
                    var outputBuilder = new StringBuilder();
                    var errorBuilder = new StringBuilder();

                    proc.OutputDataReceived += (s, e) => { if (e.Data != null) outputBuilder.AppendLine(e.Data); };
                    proc.ErrorDataReceived += (s, e) => { if (e.Data != null) errorBuilder.AppendLine(e.Data); };

                    proc.Start();
                    proc.BeginOutputReadLine();
                    proc.BeginErrorReadLine();

                    bool finished = proc.WaitForExit(timeout);
                    if (!finished)
                    {
                        EncerrarProcessoETodosOsFilhos(proc);
                        return "{\"status\": \"NÃO DISPONÍVEL\", \"erro\": \"Tempo limite excedido na consulta de indicadores.\"}";
                    }

                    string saidaLimpa = ExtrairJsonValido(outputBuilder.ToString());
                    if (string.IsNullOrWhiteSpace(saidaLimpa))
                    {
                        return "{\"status\": \"NÃO DISPONÍVEL\", \"erro\": \"Falha ao obter payload JSON válido de indicadores.\"}";
                    }

                    return saidaLimpa;
                }
                catch (Exception ex)
                {
                    return $"{{\"status\": \"NÃO DISPONÍVEL\", \"erro\": \"Exceção na consulta de indicadores: {ex.Message.Replace("\"", "'")}\"}}";
                }
            });
        }

        /// <summary>
        /// P2.7A: Execução de comandos de revisão técnica e governança via CLI dedicado (workspace_review_cli.py).
        /// Conecta a paleta WPF diretamente ao domínio authoritative em workspace_review.py.
        /// </summary>
        public static async Task<string> ExecutarComandoRevisaoAsync(
            string? projectRoot,
            string? dwgPath,
            string? sobId,
            string? fingerprint,
            string comando,
            Dictionary<string, string>? parametros = null,
            string? correlationId = null)
        {
            return await Task.Run(() =>
            {
                try
                {
                    string rootDir = ObterDiretorioRaizProjeto(projectRoot ?? dwgPath);
                    string scriptPath = Path.Combine(rootDir, "workspace", "workspace_review_cli.py");

                    if (!File.Exists(scriptPath))
                    {
                        return "{\"success\": false, \"error\": \"Script workspace_review_cli.py não localizado.\"}";
                    }

                    string pythonExe = ObterExecutavelPython();
                    int timeout = ObterTimeoutMilissegundos();

                    var sbArgs = new StringBuilder();
                    sbArgs.Append($"\"{scriptPath}\" {comando}");

                    if (!string.IsNullOrWhiteSpace(projectRoot) && Directory.Exists(projectRoot))
                    {
                        sbArgs.Append($" --project-root \"{projectRoot}\"");
                    }
                    else if (!string.IsNullOrWhiteSpace(rootDir) && Directory.Exists(rootDir))
                    {
                        sbArgs.Append($" --project-root \"{rootDir}\"");
                    }

                    if (!string.IsNullOrWhiteSpace(dwgPath))
                    {
                        sbArgs.Append($" --dwg \"{dwgPath}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(sobId) && sobId != "-")
                    {
                        sbArgs.Append($" --sob \"{sobId}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(fingerprint) && fingerprint != "-")
                    {
                        sbArgs.Append($" --fingerprint \"{fingerprint}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(correlationId))
                    {
                        sbArgs.Append($" --correlation-id \"{correlationId}\"");
                    }

                    if (parametros != null)
                    {
                        foreach (var kvp in parametros)
                        {
                            if (!string.IsNullOrWhiteSpace(kvp.Value))
                            {
                                sbArgs.Append($" --{kvp.Key} \"{kvp.Value}\"");
                            }
                            else if (kvp.Key == "creates-pending")
                            {
                                sbArgs.Append(" --creates-pending");
                            }
                        }
                    }

                    var psi = new ProcessStartInfo
                    {
                        FileName = pythonExe,
                        Arguments = sbArgs.ToString(),
                        WorkingDirectory = rootDir,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        StandardOutputEncoding = Encoding.UTF8,
                        StandardErrorEncoding = Encoding.UTF8
                    };

                    using var proc = new Process { StartInfo = psi };
                    var outputBuilder = new StringBuilder();
                    var errorBuilder = new StringBuilder();

                    proc.OutputDataReceived += (s, e) => { if (e.Data != null) outputBuilder.AppendLine(e.Data); };
                    proc.ErrorDataReceived += (s, e) => { if (e.Data != null) errorBuilder.AppendLine(e.Data); };

                    proc.Start();
                    proc.BeginOutputReadLine();
                    proc.BeginErrorReadLine();

                    bool finished = proc.WaitForExit(timeout);
                    if (!finished)
                    {
                        EncerrarProcessoETodosOsFilhos(proc);
                        return "{\"success\": false, \"error\": \"Tempo limite excedido na operação de revisão técnica.\"}";
                    }

                    string saidaLimpa = ExtrairJsonValido(outputBuilder.ToString());
                    if (string.IsNullOrWhiteSpace(saidaLimpa))
                    {
                        string err = errorBuilder.ToString().Trim();
                        return $"{{\"success\": false, \"error\": \"{(string.IsNullOrWhiteSpace(err) ? "Falha ao obter resposta JSON da revisão técnica." : err.Replace("\"", "'"))}\"}}";
                    }

                    return saidaLimpa;
                }
                catch (Exception ex)
                {
                    return $"{{\"success\": false, \"error\": \"Exceção na operação de revisão: {ex.Message.Replace("\"", "'")}\"}}";
                }
            });
        }

        /// <summary>
        /// P2.7B: Execução de comandos de fechamento de entrega e reconciliação offline via CLI dedicado (workspace_delivery_cli.py).
        /// Conecta a paleta WPF e o harness ao motor determinístico de reconciliação de entrega e fila de sincronização.
        /// </summary>
        public static async Task<string> ExecutarComandoDeliveryAsync(
            string? projectRoot,
            string? dwgPath,
            string? sobId,
            string? fingerprint,
            string comando,
            Dictionary<string, string>? parametros = null,
            string? correlationId = null)
        {
            return await Task.Run(() =>
            {
                try
                {
                    string rootDir = ObterDiretorioRaizProjeto(projectRoot ?? dwgPath);
                    string scriptPath = Path.Combine(rootDir, "workspace", "workspace_delivery_cli.py");

                    if (!File.Exists(scriptPath))
                    {
                        return "{\"success\": false, \"error\": \"Script workspace_delivery_cli.py não localizado.\"}";
                    }

                    string pythonExe = ObterExecutavelPython();
                    int timeout = ObterTimeoutMilissegundos();

                    var sbArgs = new StringBuilder();
                    sbArgs.Append($"\"{scriptPath}\" {comando}");

                    if (!string.IsNullOrWhiteSpace(projectRoot) && Directory.Exists(projectRoot))
                    {
                        sbArgs.Append($" --project-root \"{projectRoot}\"");
                    }
                    else if (!string.IsNullOrWhiteSpace(rootDir) && Directory.Exists(rootDir))
                    {
                        sbArgs.Append($" --project-root \"{rootDir}\"");
                    }

                    if (!string.IsNullOrWhiteSpace(dwgPath))
                    {
                        sbArgs.Append($" --dwg \"{dwgPath}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(sobId) && sobId != "-")
                    {
                        sbArgs.Append($" --sob \"{sobId}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(fingerprint) && fingerprint != "-")
                    {
                        sbArgs.Append($" --fingerprint \"{fingerprint}\"");
                    }
                    if (!string.IsNullOrWhiteSpace(correlationId))
                    {
                        sbArgs.Append($" --correlation-id \"{correlationId}\"");
                    }

                    if (parametros != null)
                    {
                        foreach (var kvp in parametros)
                        {
                            if (!string.IsNullOrWhiteSpace(kvp.Value))
                            {
                                sbArgs.Append($" --{kvp.Key} \"{kvp.Value}\"");
                            }
                            else
                            {
                                sbArgs.Append($" --{kvp.Key}");
                            }
                        }
                    }

                    var psi = new ProcessStartInfo
                    {
                        FileName = pythonExe,
                        Arguments = sbArgs.ToString(),
                        WorkingDirectory = rootDir,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        StandardOutputEncoding = Encoding.UTF8,
                        StandardErrorEncoding = Encoding.UTF8
                    };

                    using var proc = new Process { StartInfo = psi };
                    var outputBuilder = new StringBuilder();
                    var errorBuilder = new StringBuilder();

                    proc.OutputDataReceived += (s, e) => { if (e.Data != null) outputBuilder.AppendLine(e.Data); };
                    proc.ErrorDataReceived += (s, e) => { if (e.Data != null) errorBuilder.AppendLine(e.Data); };

                    proc.Start();
                    proc.BeginOutputReadLine();
                    proc.BeginErrorReadLine();

                    bool finished = proc.WaitForExit(timeout);
                    if (!finished)
                    {
                        EncerrarProcessoETodosOsFilhos(proc);
                        return "{\"success\": false, \"error\": \"Tempo limite excedido na operação de entrega.\"}";
                    }

                    string saidaLimpa = ExtrairJsonValido(outputBuilder.ToString());
                    if (string.IsNullOrWhiteSpace(saidaLimpa))
                    {
                        string err = errorBuilder.ToString().Trim();
                        return $"{{\"success\": false, \"error\": \"{(string.IsNullOrWhiteSpace(err) ? "Falha ao obter resposta JSON da entrega." : err.Replace("\"", "'"))}\"}}";
                    }

                    return saidaLimpa;
                }
                catch (Exception ex)
                {
                    return $"{{\"success\": false, \"error\": \"Exceção na operação de entrega: {ex.Message.Replace("\"", "'")}\"}}";
                }
            });
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

        [JsonPropertyName("correlation_id")]
        public string? CorrelationId { get; set; }

        [JsonPropertyName("duration_ms")]
        public double? DurationMs { get; set; }

        [JsonPropertyName("execution_id")]
        public string? ExecutionId { get; set; }

        [JsonPropertyName("execution_state")]
        public string? ExecutionState { get; set; }

        [JsonPropertyName("sob_id")]
        public string? SobId { get; set; }

        [JsonPropertyName("dwg_path")]
        public string? DwgPath { get; set; }

        [JsonPropertyName("dwg_identity")]
        public string? DwgIdentity { get; set; }

        [JsonPropertyName("started_at")]
        public string? StartedAt { get; set; }

        [JsonPropertyName("finished_at")]
        public string? FinishedAt { get; set; }

        [JsonPropertyName("origin")]
        public string? Origin { get; set; }

        [JsonPropertyName("artifacts")]
        public List<OxCadExecutionArtifact> Artifacts { get; set; } = new List<OxCadExecutionArtifact>();

        [JsonPropertyName("validation_summary")]
        public Dictionary<string, int> ValidationSummary { get; set; } = new Dictionary<string, int>();

        [JsonPropertyName("validation_results")]
        public List<OxCadValidationResultDto> ValidationResults { get; set; } = new List<OxCadValidationResultDto>();

        [JsonPropertyName("exception_type")]
        public string? ExceptionType { get; set; }

        [JsonPropertyName("exit_code")]
        public int? ExitCode { get; set; }
    }

    public sealed class OxCadValidationSourceDto
    {
        [JsonPropertyName("tipo")]
        public string Tipo { get; set; } = string.Empty;

        [JsonPropertyName("arquivo")]
        public string? Arquivo { get; set; }

        [JsonPropertyName("localizacao")]
        public string? Localizacao { get; set; }

        [JsonPropertyName("origem")]
        public string Origem { get; set; } = string.Empty;
    }

    public sealed class OxCadValidationResultDto
    {
        [JsonPropertyName("rule_id")]
        public string RuleId { get; set; } = string.Empty;

        [JsonPropertyName("description")]
        public string Description { get; set; } = string.Empty;

        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("value")]
        public JsonElement? Value { get; set; }

        [JsonPropertyName("criterion")]
        public JsonElement? Criterion { get; set; }

        [JsonPropertyName("source")]
        public OxCadValidationSourceDto Source { get; set; } = new OxCadValidationSourceDto();

        [JsonPropertyName("timestamp")]
        public string Timestamp { get; set; } = string.Empty;

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;

        [JsonPropertyName("execution_id")]
        public string ExecutionId { get; set; } = string.Empty;

        [JsonPropertyName("correlation_id")]
        public string CorrelationId { get; set; } = string.Empty;

        [JsonPropertyName("sob_id")]
        public string SobId { get; set; } = string.Empty;

        [JsonPropertyName("dwg_path")]
        public string? DwgPath { get; set; }

        [JsonPropertyName("dwg_identity")]
        public string? DwgIdentity { get; set; }

        [JsonPropertyName("database_fingerprint")]
        public string? DatabaseFingerprint { get; set; }

        [JsonPropertyName("revision")]
        public string? Revision { get; set; }

        [JsonPropertyName("origin")]
        public string Origin { get; set; } = string.Empty;

        public string EvidenceDisplay =>
            string.IsNullOrWhiteSpace(Source.Localizacao)
                ? Source.Arquivo ?? Source.Origem
                : $"{Source.Arquivo} · {Source.Localizacao}";
    }
}

