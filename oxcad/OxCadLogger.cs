using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using System.Threading;

namespace OxCad
{
    /// <summary>
    /// Infraestrutura central de logging e observabilidade estruturada (.jsonl) do OXCAD (.NET).
    /// Grava eventos padronizados no diretório logs/ do projeto com correlação,
    /// rotação segura, sanitização e zero dependências externas adicionais.
    /// </summary>
    public static class OxCadLogger
    {
        private static readonly object _fileLock = new object();
        private const long MaxBytesPerFile = 5 * 1024 * 1024; // 5 MB
        private const int MaxBackupCount = 5;

        private static readonly Regex[] SensitivePatterns = new[]
        {
            new Regex(@"(?i)(password|senha|passwd|pwd)\s*[:=]\s*[""']?([^""'\s&,]+)", RegexOptions.Compiled),
            new Regex(@"(?i)(access_token|refresh_token|token|jwt|bearer)\s*[:=]\s*[""']?([^""'\s&,]+)", RegexOptions.Compiled),
            new Regex(@"(?i)(client_secret|secret_key|api_key|secret)\s*[:=]\s*[""']?([^""'\s&,]+)", RegexOptions.Compiled),
            new Regex(@"(?i)(authorization:\s*bearer\s+)([A-Za-z0-9\-\._~\+\/]+=*)", RegexOptions.Compiled),
            new Regex(@"(?i)(cookie:\s*)([^;\r\n]+)", RegexOptions.Compiled)
        };

        private static string? _cachedLogDir;

        /// <summary>
        /// Obtém o diretório central de logs (aux cad/logs/), com fallback para %TEMP%/auxcad_logs.
        /// </summary>
        public static string ObterDiretorioLogs(string? dwgFullPath = null)
        {
            if (!string.IsNullOrWhiteSpace(_cachedLogDir) && Directory.Exists(_cachedLogDir))
                return _cachedLogDir!;

            try
            {
                string root = WorkspaceService.ObterDiretorioRaizProjeto(dwgFullPath);
                string candidato = Path.Combine(root, "logs");
                if (!Directory.Exists(candidato))
                {
                    Directory.CreateDirectory(candidato);
                }
                _cachedLogDir = candidato;
                return candidato;
            }
            catch
            {
                string fallback = Path.Combine(Path.GetTempPath(), "auxcad_logs");
                if (!Directory.Exists(fallback))
                {
                    Directory.CreateDirectory(fallback);
                }
                _cachedLogDir = fallback;
                return fallback;
            }
        }

        public static string Sanitizar(string? texto)
        {
            if (string.IsNullOrEmpty(texto))
                return string.Empty;

            string sanitizado = texto!;
            foreach (var padrao in SensitivePatterns)
            {
                sanitizado = padrao.Replace(sanitizado, "$1=***");
            }
            return sanitizado;
        }

        /// <summary>
        /// Grava um evento estruturado no arquivo application.jsonl e errors.jsonl (se nível for ERROR/CRITICAL).
        /// </summary>
        public static void Log(
            string level,
            string message,
            string? correlationId = null,
            string? sobId = null,
            string? dwgPath = null,
            string? module = null,
            string? action = null,
            string? operation = null,
            double? durationMs = null,
            string? result = null,
            Exception? ex = null,
            string loggerName = "oxcad.net")
        {
            try
            {
                string logDir = ObterDiretorioLogs(dwgPath);
                string appLogFile = Path.Combine(logDir, "application.jsonl");

                var evento = new Dictionary<string, object?>
                {
                    ["timestamp"] = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"),
                    ["level"] = level.ToUpperInvariant(),
                    ["logger"] = loggerName,
                    ["message"] = Sanitizar(message),
                    ["process_id"] = System.Diagnostics.Process.GetCurrentProcess().Id,
                    ["process_name"] = System.Diagnostics.Process.GetCurrentProcess().ProcessName,
                    ["thread_id"] = Thread.CurrentThread.ManagedThreadId
                };

                if (!string.IsNullOrWhiteSpace(correlationId)) evento["correlation_id"] = correlationId;
                if (!string.IsNullOrWhiteSpace(sobId)) evento["sob_id"] = sobId;
                if (!string.IsNullOrWhiteSpace(dwgPath)) evento["dwg_path"] = Sanitizar(dwgPath);
                if (!string.IsNullOrWhiteSpace(module)) evento["module"] = module;
                if (!string.IsNullOrWhiteSpace(action)) evento["action"] = action;
                if (!string.IsNullOrWhiteSpace(operation)) evento["operation"] = operation;
                if (durationMs.HasValue) evento["duration_ms"] = Math.Round(durationMs.Value, 2);
                if (!string.IsNullOrWhiteSpace(result)) evento["result"] = result;

                if (ex != null)
                {
                    evento["exception_type"] = ex.GetType().Name;
                    evento["exception_message"] = Sanitizar(ex.Message);
                    evento["stack_trace"] = Sanitizar(ex.StackTrace ?? string.Empty);
                }

                string jsonLine = JsonSerializer.Serialize(evento);

                lock (_fileLock)
                {
                    EscreverLinhaComRotacao(appLogFile, jsonLine);

                    if (level.Equals("ERROR", StringComparison.OrdinalIgnoreCase) ||
                        level.Equals("CRITICAL", StringComparison.OrdinalIgnoreCase))
                    {
                        string errLogFile = Path.Combine(logDir, "errors.jsonl");
                        EscreverLinhaComRotacao(errLogFile, jsonLine);
                    }
                }
            }
            catch
            {
                // Resiliência estrita: falhas de log nunca derrubam o AutoCAD
            }
        }

        private static void EscreverLinhaComRotacao(string filePath, string jsonLine)
        {
            try
            {
                VerificarERotacionar(filePath);

                using (var fs = new FileStream(filePath, FileMode.Append, FileAccess.Write, FileShare.ReadWrite))
                using (var sw = new StreamWriter(fs, Encoding.UTF8))
                {
                    sw.WriteLine(jsonLine);
                }
            }
            catch
            {
                // Descarta em caso de contenção transitória de SO
            }
        }

        private static void VerificarERotacionar(string filePath)
        {
            try
            {
                if (!File.Exists(filePath))
                    return;

                var fi = new FileInfo(filePath);
                if (fi.Length < MaxBytesPerFile)
                    return;

                for (int i = MaxBackupCount - 1; i >= 1; i--)
                {
                    string oldBackup = $"{filePath}.{i}";
                    string newBackup = $"{filePath}.{i + 1}";
                    if (File.Exists(oldBackup))
                    {
                        File.Copy(oldBackup, newBackup, true);
                    }
                }

                string firstBackup = $"{filePath}.1";
                File.Move(filePath, firstBackup);
            }
            catch
            {
                // Não interrompe execução se houver contenção na rotação
            }
        }

        public static void LogInfo(string message, string? correlationId = null, string? sobId = null, string? dwgPath = null, string? action = null, double? durationMs = null, string? result = null)
            => Log("INFO", message, correlationId, sobId, dwgPath, null, action, null, durationMs, result, null);

        public static void LogWarning(string message, string? correlationId = null, string? sobId = null, string? dwgPath = null, string? action = null)
            => Log("WARNING", message, correlationId, sobId, dwgPath, null, action, null, null, null, null);

        public static void LogError(string message, Exception? ex = null, string? correlationId = null, string? sobId = null, string? dwgPath = null, string? action = null)
            => Log("ERROR", message, correlationId, sobId, dwgPath, null, action, null, null, "falha", ex);

        public static void LogDebug(string message, string? correlationId = null, string? sobId = null)
            => Log("DEBUG", message, correlationId, sobId);

        public static void RegistrarSessaoInicio(string versao, string acadVer, int pid, string runtime)
        {
            Log("INFO", $"OXCAD inicializado com sucesso (v{versao})",
                action: "oxcad.iniciado",
                operation: "lifecycle.initialize",
                result: "sucesso",
                loggerName: "oxcad.lifecycle");
        }

        public static void RegistrarSessaoFim()
        {
            Log("INFO", "OXCAD descarregado / finalizado",
                action: "oxcad.encerrado",
                operation: "lifecycle.terminate",
                result: "sucesso",
                loggerName: "oxcad.lifecycle");
        }

        /// <summary>
        /// Lê as últimas linhas do arquivo application.jsonl para o comando de diagnóstico.
        /// </summary>
        public static List<string> ObterUltimosEventos(int quantidade = 10, string? dwgFullPath = null)
        {
            var linhas = new List<string>();
            try
            {
                string logDir = ObterDiretorioLogs(dwgFullPath);
                string appLogFile = Path.Combine(logDir, "application.jsonl");

                if (!File.Exists(appLogFile))
                    return linhas;

                using (var fs = new FileStream(appLogFile, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (var sr = new StreamReader(fs, Encoding.UTF8))
                {
                    var todas = new List<string>();
                    string? l;
                    while ((l = sr.ReadLine()) != null)
                    {
                        if (!string.IsNullOrWhiteSpace(l))
                            todas.Add(l);
                    }
                    int pular = Math.Max(0, todas.Count - quantidade);
                    linhas.AddRange(todas.Skip(pular));
                }
            }
            catch
            {
                // Fallback seguro
            }
            return linhas;
        }
    }
}
