using System;
using System.Collections.Generic;
using System.Linq;

namespace OxCad.Offline
{
    public enum SyncStatus
    {
        Pending,
        Ready,
        Succeeded,
        Failed,
        Blocked
    }

    public sealed class SyncItem
    {
        public string SyncId { get; }
        public string OperationId { get; }
        public string IdempotencyKey { get; }
        public string CorrelationId { get; }
        public string Operation { get; }
        public string ProviderId { get; }
        public string SobId { get; }
        public string ArtifactJson { get; }
        public DateTime CreatedAt { get; }
        public SyncStatus Status { get; set; }
        public DateTime? UpdatedAt { get; set; }
        public string? ErrorMessage { get; set; }

        public SyncItem(
            string syncId,
            string operationId,
            string idempotencyKey,
            string correlationId,
            string operation,
            string providerId,
            string sobId,
            string artifactJson,
            DateTime createdAt,
            SyncStatus status = SyncStatus.Pending,
            DateTime? updatedAt = null,
            string? errorMessage = null)
        {
            SyncId = syncId;
            OperationId = operationId;
            IdempotencyKey = idempotencyKey;
            CorrelationId = correlationId;
            Operation = operation;
            ProviderId = providerId;
            SobId = sobId;
            ArtifactJson = artifactJson;
            CreatedAt = createdAt;
            Status = status;
            UpdatedAt = updatedAt ?? createdAt;
            ErrorMessage = errorMessage;
        }

        public static SyncItem Create(
            string operationId,
            string idempotencyKey,
            string operation,
            string providerId,
            string sobId,
            string artifactJson = "{}",
            string? correlationId = null,
            SyncStatus status = SyncStatus.Pending)
        {
            if (string.IsNullOrWhiteSpace(operationId) ||
                string.IsNullOrWhiteSpace(idempotencyKey) ||
                string.IsNullOrWhiteSpace(operation) ||
                string.IsNullOrWhiteSpace(providerId) ||
                string.IsNullOrWhiteSpace(sobId))
            {
                throw new ArgumentException("Campos obrigatórios de SyncItem não podem ser vazios.");
            }

            DateTime now = DateTime.UtcNow;
            return new SyncItem(
                Guid.NewGuid().ToString("N"),
                operationId.Trim(),
                idempotencyKey.Trim(),
                string.IsNullOrWhiteSpace(correlationId) ? Guid.NewGuid().ToString("N") : correlationId!.Trim(),
                operation.Trim(),
                providerId.Trim().ToLowerInvariant(),
                sobId.Trim().ToUpperInvariant(),
                artifactJson,
                now,
                status,
                now);
        }
    }

    /// <summary>
    /// Gerenciador em memória da fila de sincronização com deduplicação por chave de idempotência.
    /// Não executa workers em background, agendamento ou chamadas externas.
    /// </summary>
    public sealed class SyncQueueStore
    {
        private readonly object _lock = new();
        private readonly Dictionary<string, SyncItem> _itemsById = new();
        private readonly Dictionary<string, string> _idByCorrelationOrIdempotency = new(StringComparer.OrdinalIgnoreCase);

        public (SyncItem item, bool isNew) Enqueue(SyncItem item)
        {
            lock (_lock)
            {
                if (_idByCorrelationOrIdempotency.TryGetValue(item.IdempotencyKey, out var existingId) &&
                    _itemsById.TryGetValue(existingId, out var existingItem))
                {
                    return (existingItem, false);
                }

                _itemsById[item.SyncId] = item;
                _idByCorrelationOrIdempotency[item.IdempotencyKey] = item.SyncId;
                return (item, true);
            }
        }

        public IReadOnlyList<SyncItem> ListItems(SyncStatus? filterStatus = null, string? sobId = null)
        {
            lock (_lock)
            {
                var query = _itemsById.Values.AsEnumerable();
                if (filterStatus.HasValue)
                    query = query.Where(i => i.Status == filterStatus.Value);
                if (!string.IsNullOrWhiteSpace(sobId))
                    query = query.Where(i => string.Equals(i.SobId, sobId!.Trim(), StringComparison.OrdinalIgnoreCase));

                return query.ToList();
            }
        }

        public SyncItem? GetByIdempotencyKey(string key)
        {
            lock (_lock)
            {
                if (_idByCorrelationOrIdempotency.TryGetValue(key.Trim(), out var id) &&
                    _itemsById.TryGetValue(id, out var item))
                {
                    return item;
                }
                return null;
            }
        }

        public SyncItem? GetBySyncId(string syncId)
        {
            lock (_lock)
            {
                if (_itemsById.TryGetValue(syncId.Trim(), out var item))
                {
                    return item;
                }
                return null;
            }
        }

        public SyncItem? UpdateStatus(string syncId, SyncStatus newStatus, string? errorMessage = null)
        {
            lock (_lock)
            {
                if (_itemsById.TryGetValue(syncId.Trim(), out var item))
                {
                    item.Status = newStatus;
                    item.UpdatedAt = DateTime.UtcNow;
                    item.ErrorMessage = errorMessage;
                    return item;
                }
                return null;
            }
        }
    }
}
