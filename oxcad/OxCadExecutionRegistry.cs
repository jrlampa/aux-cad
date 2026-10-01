using System;
using System.Collections.Concurrent;
using System.Collections.Generic;

namespace OxCad
{
    public static class OxCadExecutionRegistry
    {
        private const int MaxRecentExecutions = 256;
        private static readonly ConcurrentDictionary<string, OxCadExecutionRecord> Records =
            new ConcurrentDictionary<string, OxCadExecutionRecord>(StringComparer.Ordinal);
        private static readonly ConcurrentQueue<string> RecordOrder = new ConcurrentQueue<string>();
        private static readonly ConcurrentDictionary<string, OxCadExecutionRecord> NativeCommands =
            new ConcurrentDictionary<string, OxCadExecutionRecord>(StringComparer.OrdinalIgnoreCase);

        public static event EventHandler<OxCadExecutionChangedEventArgs>? ExecutionChanged;

        public static OxCadExecutionRecord Iniciar(
            string executionId,
            string correlationId,
            string? sobId,
            string? dwgPath,
            string? dwgIdentity,
            string action,
            string origin,
            string? projectRoot,
            long contextGeneration = 0)
        {
            var record = new OxCadExecutionRecord(
                executionId,
                correlationId,
                sobId,
                dwgPath,
                dwgIdentity,
                action,
                origin,
                projectRoot,
                contextGeneration);
            if (!Records.TryAdd(executionId, record))
                throw new InvalidOperationException("ExecutionId duplicado.");
            RecordOrder.Enqueue(executionId);
            Publicar(record);
            LimitarHistoricoEmMemoria();
            return record;
        }

        public static bool Transicionar(
            OxCadExecutionRecord record,
            OxCadExecutionState state,
            string message,
            string? error = null,
            int? pid = null)
        {
            if (!record.Transicionar(state, message, error, pid))
                return false;

            try
            {
                Publicar(record);
            }
            catch (Exception ex)
            {
                record.FalharAuditoria($"Evento terminal não registrado: {ex.Message}");
                try
                {
                    ExecutionChanged?.Invoke(
                        null, new OxCadExecutionChangedEventArgs(record.Snapshot()));
                }
                catch { }
                throw;
            }
            return true;
        }

        public static bool DefinirPid(OxCadExecutionRecord record, int pid)
        {
            if (!record.DefinirPid(pid, $"Acompanhando processo {pid}."))
                return false;

            Publicar(record);
            return true;
        }

        public static OxCadExecutionSnapshot? Obter(string executionId)
        {
            return Records.TryGetValue(executionId, out OxCadExecutionRecord? record)
                ? record.Snapshot()
                : null;
        }

        public static void RegistrarComandoNativo(
            OxCadExecutionRecord record,
            string commandName)
        {
            string key = ChaveComandoNativo(record.DwgIdentity, commandName);
            if (!NativeCommands.TryAdd(key, record))
                throw new InvalidOperationException("Já existe execução desse comando neste DWG.");
        }

        public static bool FinalizarComandoNativo(
            string? dwgIdentity,
            string commandName,
            OxCadExecutionState state,
            string message)
        {
            string key = ChaveComandoNativo(dwgIdentity, commandName);
            if (!NativeCommands.TryRemove(key, out OxCadExecutionRecord? record))
                return false;
            return Transicionar(record, state, message);
        }

        public static void CancelarComandosNativosDoDwg(
            string? dwgIdentity,
            string message)
        {
            string prefix = $"{dwgIdentity ?? "sem-dwg"}|";
            foreach (KeyValuePair<string, OxCadExecutionRecord> pending in NativeCommands)
            {
                if (!pending.Key.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                    continue;
                if (NativeCommands.TryRemove(pending.Key, out OxCadExecutionRecord? record))
                    Transicionar(record, OxCadExecutionState.Cancelado, message);
            }
        }

        private static string ChaveComandoNativo(string? dwgIdentity, string commandName)
        {
            string normalizedCommand = (commandName ?? string.Empty)
                .Trim()
                .TrimStart('_', '.')
                .ToUpperInvariant();
            return $"{dwgIdentity ?? "sem-dwg"}|{normalizedCommand}";
        }

        private static void Publicar(OxCadExecutionRecord record)
        {
            OxCadExecutionSnapshot snapshot = record.Snapshot();
            OxCadLogger.LogExecutionTransition(snapshot);
            try
            {
                ExecutionChanged?.Invoke(
                    null,
                    new OxCadExecutionChangedEventArgs(snapshot));
            }
            catch
            {
                // UI listeners não alteram o resultado da execução.
            }
        }

        private static void LimitarHistoricoEmMemoria()
        {
            int tentativas = RecordOrder.Count;
            while (Records.Count > MaxRecentExecutions && tentativas-- > 0 &&
                   RecordOrder.TryDequeue(out string? oldestId))
            {
                if (!Records.TryGetValue(oldestId, out OxCadExecutionRecord? record))
                    continue;

                OxCadExecutionSnapshot snapshot = record.Snapshot();
                if (snapshot.FinishedAt.HasValue)
                    Records.TryRemove(oldestId, out _);
                else
                    RecordOrder.Enqueue(oldestId);
            }
        }
    }
}