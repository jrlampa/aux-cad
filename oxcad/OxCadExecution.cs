using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json.Serialization;

namespace OxCad
{
    public enum OxCadExecutionState
    {
        Iniciado,
        Executando,
        Concluido,
        Falhou,
        Cancelado
    }

    public sealed class OxCadExecutionArtifact
    {
        [JsonPropertyName("path")]
        public string Caminho { get; set; } = string.Empty;

        [JsonPropertyName("type")]
        public string Tipo { get; set; } = string.Empty;

        [JsonPropertyName("operation")]
        public string Operacao { get; set; } = string.Empty;

        [JsonPropertyName("exists")]
        public bool Existe { get; set; }

        [JsonPropertyName("timestamp")]
        public string TimestampUtc { get; set; } = string.Empty;
    }

    public sealed class OxCadExecutionSnapshot
    {
        internal OxCadExecutionSnapshot(
            string executionId,
            string correlationId,
            string? sobId,
            string? dwgPath,
            string? dwgIdentity,
            long contextGeneration,
            string action,
            OxCadExecutionState state,
            DateTimeOffset startedAt,
            DateTimeOffset? finishedAt,
            double durationMs,
            IReadOnlyList<OxCadExecutionArtifact> artifacts,
            string? error,
            string message,
            string origin,
            int? pid)
        {
            ExecutionId = executionId;
            CorrelationId = correlationId;
            SobId = sobId;
            DwgPath = dwgPath;
            DwgIdentity = dwgIdentity;
            ContextGeneration = contextGeneration;
            Action = action;
            State = state;
            StartedAt = startedAt;
            FinishedAt = finishedAt;
            DurationMs = durationMs;
            Artifacts = artifacts;
            Error = error;
            Message = message;
            Origin = origin;
            Pid = pid;
        }

        public string ExecutionId { get; }
        public string CorrelationId { get; }
        public string? SobId { get; }
        public string? DwgPath { get; }
        public string? DwgIdentity { get; }
        public long ContextGeneration { get; }
        public string Action { get; }
        public OxCadExecutionState State { get; }
        public string StateText => State == OxCadExecutionState.Concluido
            ? "Concluído"
            : State.ToString();
        public DateTimeOffset StartedAt { get; }
        public DateTimeOffset? FinishedAt { get; }
        public double DurationMs { get; }
        public IReadOnlyList<OxCadExecutionArtifact> Artifacts { get; }
        public string? Error { get; }
        public string Message { get; }
        public string Origin { get; }
        public int? Pid { get; }
    }

    public sealed class OxCadExecutionChangedEventArgs : EventArgs
    {
        public OxCadExecutionChangedEventArgs(OxCadExecutionSnapshot execution)
        {
            Execution = execution;
        }

        public OxCadExecutionSnapshot Execution { get; }
    }

    public sealed class OxCadExecutionRecord
    {
        private static readonly HashSet<string> ArtifactExtensions = new HashSet<string>(
            new[] { ".dwg", ".xls", ".xlsx", ".xlsm", ".csv", ".docx", ".pdf", ".json", ".txt", ".png", ".jpg", ".jpeg", ".kmz", ".kml", ".gpx", ".svg" },
            StringComparer.OrdinalIgnoreCase);

        private readonly object _sync = new object();
        private readonly string? _projectRoot;
        private readonly Dictionary<string, FileStamp> _filesBefore;
        private OxCadExecutionState _state = OxCadExecutionState.Iniciado;
        private DateTimeOffset? _finishedAt;
        private string? _error;
        private string _message;
        private int? _pid;
        private IReadOnlyList<OxCadExecutionArtifact> _artifacts = Array.Empty<OxCadExecutionArtifact>();

        public OxCadExecutionRecord(
            string executionId,
            string correlationId,
            string? sobId,
            string? dwgPath,
            string? dwgIdentity,
            string action,
            string origin,
            string? projectRoot,
            long contextGeneration = 0,
            DateTimeOffset? startedAt = null)
        {
            if (string.IsNullOrWhiteSpace(executionId))
                throw new ArgumentException("ExecutionId obrigatório.", nameof(executionId));
            if (string.IsNullOrWhiteSpace(correlationId))
                throw new ArgumentException("CorrelationId obrigatório.", nameof(correlationId));
            if (string.Equals(executionId, correlationId, StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("ExecutionId deve ser diferente de CorrelationId.", nameof(executionId));

            ExecutionId = executionId;
            CorrelationId = correlationId;
            SobId = sobId;
            DwgPath = dwgPath;
            DwgIdentity = dwgIdentity;
            ContextGeneration = contextGeneration;
            Action = action;
            Origin = origin;
            _projectRoot = projectRoot;
            StartedAt = startedAt ?? DateTimeOffset.UtcNow;
            _message = "Execução iniciada.";
            _filesBefore = CapturarArquivos(projectRoot);
        }

        public string ExecutionId { get; }
        public string CorrelationId { get; }
        public string? SobId { get; }
        public string? DwgPath { get; }
        public string? DwgIdentity { get; }
        public long ContextGeneration { get; }
        public string Action { get; }
        public string Origin { get; }
        public DateTimeOffset StartedAt { get; }

        public bool Transicionar(
            OxCadExecutionState novoEstado,
            string message,
            string? error = null,
            int? pid = null,
            DateTimeOffset? timestamp = null)
        {
            lock (_sync)
            {
                if (IsTerminal(_state))
                    return false;

                bool transicaoValida =
                    _state == OxCadExecutionState.Iniciado &&
                    (novoEstado == OxCadExecutionState.Executando || IsTerminal(novoEstado)) ||
                    _state == OxCadExecutionState.Executando && IsTerminal(novoEstado);
                if (!transicaoValida)
                    throw new InvalidOperationException($"Transição inválida: {_state} -> {novoEstado}.");

                _state = novoEstado;
                _message = message ?? string.Empty;
                _error = error;
                _pid = pid;
                if (IsTerminal(novoEstado))
                {
                    _finishedAt = timestamp ?? DateTimeOffset.UtcNow;
                    _artifacts = DetectarArtefatos();
                }
                return true;
            }
        }

        public bool DefinirPid(int pid, string message)
        {
            lock (_sync)
            {
                if (_state != OxCadExecutionState.Executando || IsTerminal(_state))
                    return false;
                _pid = pid;
                _message = message;
                return true;
            }
        }

        internal void FalharAuditoria(string message)
        {
            lock (_sync)
            {
                if (_state != OxCadExecutionState.Concluido)
                    return;
                _state = OxCadExecutionState.Falhou;
                _error = message;
                _message = message;
            }
        }

        public OxCadExecutionSnapshot Snapshot(DateTimeOffset? now = null)
        {
            lock (_sync)
            {
                DateTimeOffset end = _finishedAt ?? now ?? DateTimeOffset.UtcNow;
                double durationMs = Math.Max(0, (end - StartedAt).TotalMilliseconds);
                return new OxCadExecutionSnapshot(
                    ExecutionId,
                    CorrelationId,
                    SobId,
                    DwgPath,
                    DwgIdentity,
                    ContextGeneration,
                    Action,
                    _state,
                    StartedAt,
                    _finishedAt,
                    durationMs,
                    _artifacts.ToArray(),
                    _error,
                    _message,
                    Origin,
                    _pid);
            }
        }

        private IReadOnlyList<OxCadExecutionArtifact> DetectarArtefatos()
        {
            Dictionary<string, FileStamp> atuais = CapturarArquivos(_projectRoot);
            var artefatos = new List<OxCadExecutionArtifact>();
            foreach (KeyValuePair<string, FileStamp> atual in atuais)
            {
                bool existia = _filesBefore.TryGetValue(atual.Key, out FileStamp anterior);
                if (existia && anterior.Equals(atual.Value))
                    continue;

                artefatos.Add(new OxCadExecutionArtifact
                {
                    Caminho = atual.Key,
                    Tipo = Path.GetExtension(atual.Key).TrimStart('.').ToLowerInvariant(),
                    Operacao = existia ? "modificado" : "criado",
                    Existe = File.Exists(atual.Key),
                    TimestampUtc = atual.Value.LastWriteTimeUtc.ToString("O")
                });
            }
            return artefatos;
        }

        private static Dictionary<string, FileStamp> CapturarArquivos(string? root)
        {
            var snapshot = new Dictionary<string, FileStamp>(StringComparer.OrdinalIgnoreCase);
            if (string.IsNullOrWhiteSpace(root) || !Directory.Exists(root))
                return snapshot;

            var directories = new List<string> { root! };
            try
            {
                directories.AddRange(Array.FindAll(
                    Directory.GetDirectories(root!),
                        directory => !string.Equals(
                        Path.GetFileName(directory),
                        ".oxcad",
                        StringComparison.OrdinalIgnoreCase)));
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }

            foreach (string directory in directories)
            {
                try
                {
                    foreach (string file in Directory.GetFiles(directory))
                    {
                        if (!ArtifactExtensions.Contains(Path.GetExtension(file)) ||
                            Path.GetFileName(file).StartsWith("~", StringComparison.Ordinal))
                            continue;

                        try
                        {
                            var info = new FileInfo(file);
                            snapshot[Path.GetFullPath(file)] =
                                new FileStamp(info.Length, info.LastWriteTimeUtc);
                        }
                        catch (IOException) { }
                        catch (UnauthorizedAccessException) { }
                    }
                }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
            }
            return snapshot;
        }

        private static bool IsTerminal(OxCadExecutionState state)
            => state == OxCadExecutionState.Concluido ||
               state == OxCadExecutionState.Falhou ||
               state == OxCadExecutionState.Cancelado;

        private readonly struct FileStamp : IEquatable<FileStamp>
        {
            public FileStamp(long length, DateTime lastWriteTimeUtc)
            {
                Length = length;
                LastWriteTimeUtc = lastWriteTimeUtc;
            }

            public long Length { get; }
            public DateTime LastWriteTimeUtc { get; }

            public bool Equals(FileStamp other)
                => Length == other.Length && LastWriteTimeUtc == other.LastWriteTimeUtc;
        }
    }
}