using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;

namespace OxCad.Offline
{
    public enum FieldValidationStatus
    {
        Ok,
        Alerta,
        Erro,
        NaoVerificado,
        NaoAplicavel,
        NaoDisponivel
    }

    public enum EvidenceStatus
    {
        Valid,
        Missing,
        Changed,
        Corrupt,
        IdentityMismatch
    }

    public sealed class FieldEvidenceReference
    {
        public string EvidenceId { get; }
        public string SobId { get; }
        public string DatabaseFingerprint { get; }
        public string Path { get; }
        public string Type { get; }
        public long Size { get; }
        public string Sha256 { get; }
        public DateTime CreatedAt { get; }
        public DateTime ModifiedAt { get; }
        public string Source { get; }

        public FieldEvidenceReference(
            string evidenceId,
            string sobId,
            string databaseFingerprint,
            string path,
            string type,
            long size,
            string sha256,
            DateTime createdAt,
            DateTime modifiedAt,
            string source)
        {
            EvidenceId = evidenceId;
            SobId = sobId;
            DatabaseFingerprint = databaseFingerprint;
            Path = path;
            Type = type;
            Size = size;
            Sha256 = sha256;
            CreatedAt = createdAt;
            ModifiedAt = modifiedAt;
            Source = source;
        }

        public EvidenceStatus VerifyIntegrity(string? currentSobId = null, string? currentFingerprint = null)
        {
            if (!string.IsNullOrWhiteSpace(currentSobId) &&
                !string.Equals(SobId, currentSobId!.Trim(), StringComparison.OrdinalIgnoreCase))
            {
                return EvidenceStatus.IdentityMismatch;
            }

            if (!string.IsNullOrWhiteSpace(currentFingerprint) &&
                !string.Equals(DatabaseFingerprint, currentFingerprint!.Trim(), StringComparison.OrdinalIgnoreCase))
            {
                return EvidenceStatus.IdentityMismatch;
            }

            if (!File.Exists(Path))
                return EvidenceStatus.Missing;

            try
            {
                using var stream = File.OpenRead(Path);
                using var sha = SHA256.Create();
                byte[] hashBytes = sha.ComputeHash(stream);
                string computed = BitConverter.ToString(hashBytes).Replace("-", "").ToLowerInvariant();

                if (!string.Equals(Sha256, computed, StringComparison.OrdinalIgnoreCase))
                    return EvidenceStatus.Changed;
            }
            catch
            {
                return EvidenceStatus.Corrupt;
            }

            return EvidenceStatus.Valid;
        }
    }

    public sealed class FieldValidationItem
    {
        public string ValidationId { get; }
        public string SobId { get; }
        public string ProjectRoot { get; }
        public string DwgPath { get; }
        public string DatabaseFingerprint { get; }
        public DateTime Timestamp { get; }
        public string OperatorContext { get; }
        public string Category { get; }
        public string Question { get; }
        public string Expected { get; }
        public string Observed { get; }
        public FieldValidationStatus Status { get; set; }
        public List<string> EvidenceReferences { get; }
        public string? Notes { get; set; }

        public FieldValidationItem(
            string validationId,
            string sobId,
            string projectRoot,
            string dwgPath,
            string databaseFingerprint,
            DateTime timestamp,
            string operatorContext,
            string category,
            string question,
            string expected,
            string observed,
            FieldValidationStatus status,
            List<string>? evidenceReferences = null,
            string? notes = null)
        {
            ValidationId = validationId;
            SobId = sobId;
            ProjectRoot = projectRoot;
            DwgPath = dwgPath;
            DatabaseFingerprint = databaseFingerprint;
            Timestamp = timestamp;
            OperatorContext = operatorContext;
            Category = category;
            Question = question;
            Expected = expected;
            Observed = observed;
            Status = status;
            EvidenceReferences = evidenceReferences ?? new List<string>();
            Notes = notes;
        }

        public bool ValidateIdentity(string currentSobId, string currentDwg, string currentFingerprint)
        {
            if (string.IsNullOrWhiteSpace(currentSobId) ||
                string.IsNullOrWhiteSpace(currentDwg) ||
                string.IsNullOrWhiteSpace(currentFingerprint))
            {
                return false;
            }

            bool sobMatch = string.Equals(SobId, currentSobId.Trim(), StringComparison.OrdinalIgnoreCase);
            bool fpMatch = string.Equals(DatabaseFingerprint, currentFingerprint.Trim(), StringComparison.OrdinalIgnoreCase);

            bool dwgMatch;
            try
            {
                string norm1 = System.IO.Path.GetFullPath(DwgPath);
                string norm2 = System.IO.Path.GetFullPath(currentDwg);
                dwgMatch = string.Equals(norm1, norm2, StringComparison.OrdinalIgnoreCase);
            }
            catch
            {
                dwgMatch = string.Equals(DwgPath.Trim(), currentDwg.Trim(), StringComparison.OrdinalIgnoreCase);
            }

            return sobMatch && fpMatch && dwgMatch;
        }
    }

    public sealed class FieldChecklistSummary
    {
        public int Total { get; set; }
        public int Ok { get; set; }
        public int Alerta { get; set; }
        public int Erro { get; set; }
        public int NaoVerificado { get; set; }
        public int NaoAplicavel { get; set; }
        public int NaoDisponivel { get; set; }
    }
}
