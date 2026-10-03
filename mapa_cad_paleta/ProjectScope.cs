using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.RegularExpressions;

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

        public static ProjectScope Bound(string sobId)
            => ProjectScope.Create(ProjectScopeStatus.Bound, sobId: sobId);

        public static ProjectScope Ambiguous(string detail)
            => ProjectScope.Create(ProjectScopeStatus.Ambiguous, detail: detail);

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

        public static ProjectScope ReconcileCompletedManifest(string dwgPath)
        {
            if (string.IsNullOrWhiteSpace(dwgPath))
                return Invalid("MISSING_DWG_PATH");

            string fullDwgPath;
            try
            {
                fullDwgPath = Path.GetFullPath(dwgPath);
            }
            catch (Exception)
            {
                return Invalid("INVALID_DWG_PATH");
            }

            if (!File.Exists(fullDwgPath))
                return Invalid("DWG_FILE_NOT_FOUND");

            string? sobRoot = Path.GetDirectoryName(fullDwgPath);
            if (string.IsNullOrWhiteSpace(sobRoot) || !Directory.Exists(sobRoot))
                return Invalid("SOB_DIRECTORY_NOT_FOUND");

            string manifestPath = Path.Combine(sobRoot, ".sob_state.json");
            if (!File.Exists(manifestPath))
                return Unbound();

            JsonDocument manifest;
            try
            {
                manifest = JsonDocument.Parse(File.ReadAllText(manifestPath));
            }
            catch (Exception)
            {
                return Invalid("PROJECT_MANIFEST_INVALID");
            }

            using (manifest)
            {
                JsonElement root = manifest.RootElement;
                if (root.ValueKind != JsonValueKind.Object)
                    return Invalid("PROJECT_MANIFEST_INVALID");

                if (!root.TryGetProperty("status", out JsonElement statusElem) ||
                    statusElem.ValueKind != JsonValueKind.String)
                    return Invalid("MANIFEST_STATUS_INVALID");

                string statusStr = statusElem.GetString()?.Trim().ToUpperInvariant() ?? string.Empty;
                if (statusStr != "CONCLUÍDO" && statusStr != "CONCLUIDO")
                    return Invalid("MANIFEST_NOT_COMPLETED");

                if (!root.TryGetProperty("sob_id", out JsonElement sobIdElem) ||
                    sobIdElem.ValueKind != JsonValueKind.String ||
                    !TryNormalizeSobId(sobIdElem.GetString(), out string manifestSobId))
                    return Invalid("MANIFEST_SOB_ID_INVALID");

                if (!root.TryGetProperty("base_dwg", out JsonElement baseDwgElem) ||
                    baseDwgElem.ValueKind != JsonValueKind.String)
                    return Invalid("PROJECT_DWG_UNVERIFIABLE");

                string? baseDwgRaw = baseDwgElem.GetString();
                if (string.IsNullOrWhiteSpace(baseDwgRaw))
                    return Invalid("PROJECT_DWG_UNVERIFIABLE");

                string manifestDwgCanonical;
                try
                {
                    manifestDwgCanonical = Path.IsPathRooted(baseDwgRaw)
                        ? Path.GetFullPath(baseDwgRaw)
                        : Path.GetFullPath(Path.Combine(sobRoot, baseDwgRaw));
                }
                catch (Exception)
                {
                    return Invalid("PROJECT_DWG_UNVERIFIABLE");
                }

                if (!string.Equals(manifestDwgCanonical, fullDwgPath, StringComparison.OrdinalIgnoreCase))
                    return Invalid("BASE_DWG_MISMATCH");

                if (HasConflictingIdentities(sobRoot, fullDwgPath, manifestSobId))
                    return Ambiguous("CONFLICTING_SOB_IDENTITIES");

                return Bound(manifestSobId);
            }
        }

        private static bool HasConflictingIdentities(string sobRoot, string activeDwgPath, string expectedSobId)
        {
            try
            {
                foreach (string otherDwg in Directory.EnumerateFiles(sobRoot, "*.dwg", SearchOption.TopDirectoryOnly))
                {
                    string otherCanonical = Path.GetFullPath(otherDwg);
                    if (string.Equals(otherCanonical, activeDwgPath, StringComparison.OrdinalIgnoreCase))
                        continue;

                    string otherFileName = Path.GetFileNameWithoutExtension(otherDwg);
                    if (TryExtractSobCandidate(otherFileName, out string candidateSobId))
                    {
                        if (!string.Equals(candidateSobId, expectedSobId, StringComparison.Ordinal))
                            return true;
                    }
                }
            }
            catch (Exception)
            {
            }

            try
            {
                foreach (string subDir in Directory.EnumerateDirectories(sobRoot, "*", SearchOption.TopDirectoryOnly))
                {
                    string subManifest = Path.Combine(subDir, ".sob_state.json");
                    if (File.Exists(subManifest))
                    {
                        try
                        {
                            using JsonDocument subDoc = JsonDocument.Parse(File.ReadAllText(subManifest));
                            if (subDoc.RootElement.TryGetProperty("sob_id", out JsonElement subSobElem) &&
                                subSobElem.ValueKind == JsonValueKind.String &&
                                TryNormalizeSobId(subSobElem.GetString(), out string subSobId))
                            {
                                if (!string.Equals(subSobId, expectedSobId, StringComparison.Ordinal))
                                    return true;
                            }
                        }
                        catch
                        {
                        }
                    }
                }
            }
            catch (Exception)
            {
            }

            return false;
        }

        public static bool TryExtractSobCandidate(string text, out string candidate)
        {
            candidate = string.Empty;
            if (string.IsNullOrWhiteSpace(text))
                return false;

            var matchDwg = Regex.Match(
                text, @"^[A-Za-z]{2}_([A-Za-z0-9_\-]+)_DESENHO$", RegexOptions.IgnoreCase);
            if (matchDwg.Success && TryNormalizeSobId(matchDwg.Groups[1].Value, out candidate))
                return true;

            var matchAlfa = Regex.Match(
                text, @"(?:^|[^A-Za-z0-9])([A-Za-z][0-9]{8,12})(?:[^A-Za-z0-9]|$)", RegexOptions.IgnoreCase);
            if (matchAlfa.Success && TryNormalizeSobId(matchAlfa.Groups[1].Value, out candidate))
                return true;

            if (TryNormalizeSobId(text, out candidate))
                return true;

            return false;
        }
    }

    /// <summary>
    /// Contrato imutavel de contexto compartilhado de projeto do OXCAD.
    /// Captura atomicamente o estado autoritativo do AutoCAD (DWG, FingerprintGuid, ProjectScope, ProjectRoot, Generation).
    /// </summary>
    public sealed class OxCadProjectContext : IEquatable<OxCadProjectContext>
    {
        public static readonly OxCadProjectContext Empty = new(
            ProjectScopeContract.Unbound(),
            dwgPath: null,
            databaseFingerprint: null,
            projectRoot: null,
            generation: 0,
            isDwgSaved: false);

        public OxCadProjectContext(
            ProjectScope scope,
            string? dwgPath,
            string? databaseFingerprint,
            string? projectRoot,
            long generation,
            bool isDwgSaved)
        {
            Scope = scope ?? ProjectScopeContract.Unbound();
            DwgPath = dwgPath;
            DatabaseFingerprint = databaseFingerprint;
            ProjectRoot = projectRoot;
            Generation = generation;
            IsDwgSaved = isDwgSaved;
        }

        public ProjectScope Scope { get; }
        public string? SobId => Scope.SobId;
        public bool IsBound => Scope.IsBound;
        public ProjectScopeStatus Status => Scope.Status;
        public string? DwgPath { get; }
        public string? DatabaseFingerprint { get; }
        public string? ProjectRoot { get; }
        public long Generation { get; }
        public bool IsDwgSaved { get; }

        public bool Equals(OxCadProjectContext? other)
        {
            if (other is null) return false;
            if (ReferenceEquals(this, other)) return true;
            return Scope.Equals(other.Scope) &&
                   string.Equals(DwgPath, other.DwgPath, StringComparison.OrdinalIgnoreCase) &&
                   string.Equals(DatabaseFingerprint, other.DatabaseFingerprint, StringComparison.OrdinalIgnoreCase) &&
                   string.Equals(ProjectRoot, other.ProjectRoot, StringComparison.OrdinalIgnoreCase) &&
                   Generation == other.Generation &&
                   IsDwgSaved == other.IsDwgSaved;
        }

        public override bool Equals(object? obj) => Equals(obj as OxCadProjectContext);

        public override int GetHashCode()
        {
            unchecked
            {
                int hash = Scope.GetHashCode();
                hash = (hash * 397) ^ (DwgPath?.ToUpperInvariant().GetHashCode() ?? 0);
                hash = (hash * 397) ^ (DatabaseFingerprint?.ToUpperInvariant().GetHashCode() ?? 0);
                hash = (hash * 397) ^ (ProjectRoot?.ToUpperInvariant().GetHashCode() ?? 0);
                hash = (hash * 397) ^ Generation.GetHashCode();
                hash = (hash * 397) ^ IsDwgSaved.GetHashCode();
                return hash;
            }
        }
    }
}
