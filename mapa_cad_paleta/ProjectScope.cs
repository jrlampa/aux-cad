using System;
using System.Collections.Generic;
using System.Text.Json;

namespace MapaCadPaleta
{
    public enum ProjectScopeStatus
    {
        Bound,
        Unbound,
        Invalid,
        Ambiguous
    }

    public sealed class ProjectScope : IEquatable<ProjectScope>
    {
        private ProjectScope(ProjectScopeStatus status, string? sobId, string? detail)
        {
            Status = status;
            SobId = sobId;
            Detail = detail;
        }

        public ProjectScopeStatus Status { get; }
        public string? SobId { get; }
        public string? Detail { get; }
        public bool IsBound => Status == ProjectScopeStatus.Bound;

        internal static ProjectScope Create(ProjectScopeStatus status, string? sobId = null, string? detail = null)
            => new(status, sobId, detail);

        public bool Equals(ProjectScope? other)
        {
            return other != null &&
                   Status == other.Status &&
                   string.Equals(SobId, other.SobId, StringComparison.Ordinal) &&
                   string.Equals(Detail, other.Detail, StringComparison.Ordinal);
        }

        public override bool Equals(object? obj) => Equals(obj as ProjectScope);

        public override int GetHashCode()
        {
            unchecked
            {
                int hash = (int)Status;
                hash = (hash * 397) ^ (SobId?.GetHashCode() ?? 0);
                hash = (hash * 397) ^ (Detail?.GetHashCode() ?? 0);
                return hash;
            }
        }
    }

    public sealed class ProjectScopeChangedEventArgs : EventArgs
    {
        public ProjectScopeChangedEventArgs(ProjectScope previous, ProjectScope current, long generation)
        {
            Previous = previous;
            Current = current;
            Generation = generation;
            ProjectIdentityChanged = !previous.Equals(current);
        }

        public ProjectScope Previous { get; }
        public ProjectScope Current { get; }
        public long Generation { get; }
        public bool ProjectIdentityChanged { get; }
    }

    public static class ProjectScopeContract
    {
        public const int MetadataVersion = 1;
        public const string MetadataKey = "AUXCAD_PROJECT_SCOPE";
        public const string SobIdField = "SOB_ID";

        public static ProjectScope Unbound()
            => ProjectScope.Create(ProjectScopeStatus.Unbound);

        public static ProjectScope Invalid(string detail)
            => ProjectScope.Create(ProjectScopeStatus.Invalid, detail: detail);

        public static ProjectScope Resolve(
            int version,
            IEnumerable<KeyValuePair<string, string>>? fields)
        {
            if (version != MetadataVersion)
                return Invalid("UNSUPPORTED_METADATA_VERSION");

            if (fields == null)
                return Invalid("MISSING_METADATA_FIELDS");

            var ids = new HashSet<string>(StringComparer.Ordinal);
            foreach (KeyValuePair<string, string> field in fields)
            {
                if (!string.Equals(field.Key, SobIdField, StringComparison.Ordinal))
                    return Invalid("UNKNOWN_METADATA_FIELD");

                if (!TryNormalizeSobId(field.Value, out string normalized))
                    return Invalid("INVALID_SOB_ID");

                ids.Add(normalized);
            }

            if (ids.Count == 0)
                return Invalid("MISSING_SOB_ID");

            if (ids.Count > 1)
                return ProjectScope.Create(ProjectScopeStatus.Ambiguous, detail: "CONFLICTING_SOB_IDS");

            foreach (string id in ids)
                return ProjectScope.Create(ProjectScopeStatus.Bound, id);

            return Invalid("MISSING_SOB_ID");
        }

        public static IReadOnlyList<KeyValuePair<string, string>> Encode(string sobId)
        {
            if (!TryNormalizeSobId(sobId, out string normalized))
                throw new ArgumentException("SOB_ID inválido.", nameof(sobId));

            return new[]
            {
                new KeyValuePair<string, string>(SobIdField, normalized)
            };
        }

        public static string ValidateWrite(ProjectScope existingScope, string? sobId)
        {
            if (existingScope == null)
                throw new ArgumentNullException(nameof(existingScope));

            if (!TryNormalizeSobId(sobId, out string normalized))
                throw new ArgumentException("SOB_ID inválido.", nameof(sobId));

            if (existingScope.Status == ProjectScopeStatus.Bound)
            {
                if (!string.Equals(existingScope.SobId, normalized, StringComparison.Ordinal))
                    throw new InvalidOperationException("O DWG já está vinculado a outro ProjectScope.");

                return normalized;
            }

            if (existingScope.Status != ProjectScopeStatus.Unbound)
                throw new InvalidOperationException($"Metadata ProjectScope existente é inválida: {existingScope.Detail}.");

            return normalized;
        }

        public static bool TryValidatePayload(
            JsonElement root,
            ProjectScope activeScope,
            long currentGeneration,
            out string error)
        {
            error = string.Empty;
            if (!activeScope.IsBound)
            {
                error = "ACTIVE_PROJECT_SCOPE_UNBOUND";
                return false;
            }

            if (!root.TryGetProperty("projectScope", out JsonElement payloadScope) ||
                payloadScope.ValueKind != JsonValueKind.Object)
            {
                error = "PROJECT_SCOPE_MISSING";
                return false;
            }

            if (!payloadScope.TryGetProperty("sobId", out JsonElement sobIdElement) ||
                sobIdElement.ValueKind != JsonValueKind.String ||
                !TryNormalizeSobId(sobIdElement.GetString(), out string payloadSobId))
            {
                error = "PROJECT_SCOPE_ID_INVALID";
                return false;
            }

            if (!payloadScope.TryGetProperty("generation", out JsonElement generationElement) ||
                generationElement.ValueKind != JsonValueKind.Number ||
                !generationElement.TryGetInt64(out long payloadGeneration) ||
                payloadGeneration < 0)
            {
                error = "PROJECT_SCOPE_GENERATION_INVALID";
                return false;
            }

            if (!string.Equals(payloadSobId, activeScope.SobId, StringComparison.Ordinal))
            {
                error = "PROJECT_SCOPE_MISMATCH";
                return false;
            }

            if (payloadGeneration != currentGeneration)
            {
                error = "PROJECT_SCOPE_GENERATION_STALE";
                return false;
            }

            return true;
        }

        public static bool TryNormalizeSobId(string? sobId, out string normalized)
        {
            normalized = string.Empty;
            if (sobId is null || string.IsNullOrWhiteSpace(sobId))
                return false;

            string candidate = sobId.Trim().ToUpperInvariant();
            if (candidate.Length < 3 || candidate.Length > 30 ||
                candidate.StartsWith("SOB_", StringComparison.Ordinal))
                return false;

            foreach (char character in candidate)
            {
                bool allowed = character >= 'A' && character <= 'Z' ||
                               character >= '0' && character <= '9' ||
                               character == '_' ||
                               character == '-';
                if (!allowed)
                    return false;
            }

            normalized = candidate;
            return true;
        }
    }
}
