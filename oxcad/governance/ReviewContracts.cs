using System;
using System.Collections.Generic;

namespace OxCad.Governance
{
    public enum ReviewStatus
    {
        Draft,
        InReview,
        ChangesRequired,
        Approved,
        Rejected,
        Superseded,
        Cancelled
    }

    public enum FindingSeverity
    {
        Info,
        Minor,
        Major,
        Critical
    }

    public enum FindingStatus
    {
        Open,
        Resolved,
        Waived
    }

    public enum GateEligibilityStatus
    {
        Eligible,
        NotEligible
    }

    public sealed class ReviewHistoryEvent
    {
        public string EventId { get; }
        public ReviewStatus? FromStatus { get; }
        public ReviewStatus ToStatus { get; }
        public DateTime Timestamp { get; }
        public string Operator { get; }
        public string Reason { get; }

        public ReviewHistoryEvent(
            string eventId,
            ReviewStatus? fromStatus,
            ReviewStatus toStatus,
            DateTime timestamp,
            string op,
            string reason)
        {
            EventId = eventId;
            FromStatus = fromStatus;
            ToStatus = toStatus;
            Timestamp = timestamp;
            Operator = op;
            Reason = reason;
        }
    }

    public sealed class ReviewFinding
    {
        public string FindingId { get; }
        public string ReviewId { get; }
        public FindingSeverity Severity { get; }
        public string Category { get; }
        public string Description { get; }
        public FindingStatus Status { get; private set; }
        public IReadOnlyList<string> EvidenceReferences { get; }
        public string? PendingReference { get; }
        public DateTime CreatedAt { get; }
        public DateTime? ResolvedAt { get; private set; }
        public string? Notes { get; private set; }

        public ReviewFinding(
            string findingId,
            string reviewId,
            FindingSeverity severity,
            string category,
            string description,
            FindingStatus status,
            IReadOnlyList<string> evidenceReferences,
            string? pendingReference,
            DateTime createdAt,
            DateTime? resolvedAt = null,
            string? notes = null)
        {
            FindingId = findingId;
            ReviewId = reviewId;
            Severity = severity;
            Category = category;
            Description = description;
            Status = status;
            EvidenceReferences = evidenceReferences;
            PendingReference = pendingReference;
            CreatedAt = createdAt;
            ResolvedAt = resolvedAt;
            Notes = notes;
        }

        public void Resolve(string resolutionNotes, bool waive = false)
        {
            Status = waive ? FindingStatus.Waived : FindingStatus.Resolved;
            ResolvedAt = DateTime.UtcNow;
            Notes = $"{Notes} [Resolução: {resolutionNotes}]".Trim();
        }
    }

    public sealed class ReviewApproval
    {
        public int Schema { get; }
        public string ReviewId { get; }
        public string Revision { get; }
        public string State { get; private set; }
        public DateTime ApprovedAt { get; }
        public string SobId { get; }
        public string DwgPath { get; }
        public string DatabaseFingerprint { get; }
        public string? SourceSnapshotId { get; }
        public string Operator { get; }
        public IReadOnlyList<string> FindingsConsidered { get; }
        public string? DecisionNote { get; }
        public DateTime? RevokedAt { get; private set; }
        public string? RevocationReason { get; private set; }

        public ReviewApproval(
            string reviewId,
            string revision,
            string state,
            DateTime approvedAt,
            string sobId,
            string dwgPath,
            string databaseFingerprint,
            string? sourceSnapshotId,
            string op,
            IReadOnlyList<string> findingsConsidered,
            string? decisionNote = null)
        {
            Schema = 1;
            ReviewId = reviewId;
            Revision = revision;
            State = state;
            ApprovedAt = approvedAt;
            SobId = sobId;
            DwgPath = dwgPath;
            DatabaseFingerprint = databaseFingerprint;
            SourceSnapshotId = sourceSnapshotId;
            Operator = op;
            FindingsConsidered = findingsConsidered;
            DecisionNote = decisionNote;
        }

        public void Revoke(string reason)
        {
            State = "REVOGADO";
            RevokedAt = DateTime.UtcNow;
            RevocationReason = reason;
        }
    }

    public sealed class ReviewDeliveryReference
    {
        public string PackageId { get; }
        public string ManifestSha256 { get; }
        public DateTime PreparedAt { get; }
        public string Status { get; }

        public ReviewDeliveryReference(string packageId, string manifestSha256, DateTime preparedAt, string status)
        {
            PackageId = packageId;
            ManifestSha256 = manifestSha256;
            PreparedAt = preparedAt;
            Status = status;
        }
    }

    public sealed class TechnicalReview
    {
        public string ReviewId { get; }
        public string SobId { get; }
        public string ProjectRoot { get; }
        public string DwgPath { get; }
        public string DatabaseFingerprint { get; }
        public string RevisionId { get; }
        public string? SourceSnapshotId { get; }
        public DateTime CreatedAt { get; }
        public string Operator { get; }
        public ReviewStatus Status { get; private set; }
        public List<ReviewFinding> Findings { get; }
        public List<string> EvidenceReferences { get; }
        public List<string> PendingReferences { get; }
        public string? Notes { get; }
        public ReviewApproval? Approval { get; private set; }
        public ReviewDeliveryReference? Delivery { get; private set; }
        public List<ReviewHistoryEvent> History { get; }

        public TechnicalReview(
            string reviewId,
            string sobId,
            string projectRoot,
            string dwgPath,
            string databaseFingerprint,
            string revisionId,
            string? sourceSnapshotId,
            DateTime createdAt,
            string op,
            ReviewStatus status = ReviewStatus.Draft,
            string? notes = null)
        {
            ReviewId = reviewId;
            SobId = sobId;
            ProjectRoot = projectRoot;
            DwgPath = dwgPath;
            DatabaseFingerprint = databaseFingerprint;
            RevisionId = revisionId;
            SourceSnapshotId = sourceSnapshotId;
            CreatedAt = createdAt;
            Operator = op;
            Status = status;
            Notes = notes;
            Findings = new List<ReviewFinding>();
            EvidenceReferences = new List<string>();
            PendingReferences = new List<string>();
            History = new List<ReviewHistoryEvent>();

            History.Add(new ReviewHistoryEvent(
                Guid.NewGuid().ToString("N"),
                null,
                ReviewStatus.Draft,
                createdAt,
                op,
                "Revisão técnica criada em rascunho."));
        }

        public static bool IsTransitionAllowed(ReviewStatus current, ReviewStatus target)
        {
            return current switch
            {
                ReviewStatus.Draft => target == ReviewStatus.InReview || target == ReviewStatus.Cancelled,
                ReviewStatus.InReview => target == ReviewStatus.Approved || target == ReviewStatus.ChangesRequired || target == ReviewStatus.Rejected,
                ReviewStatus.ChangesRequired => target == ReviewStatus.Draft,
                ReviewStatus.Approved => target == ReviewStatus.Superseded,
                _ => false
            };
        }

        public void TransitionTo(ReviewStatus target, string reason, string op)
        {
            if (!IsTransitionAllowed(Status, target))
                throw new InvalidOperationException($"INVALID_TRANSITION: {Status} -> {target}");

            var prev = Status;
            Status = target;
            History.Add(new ReviewHistoryEvent(
                Guid.NewGuid().ToString("N"),
                prev,
                target,
                DateTime.UtcNow,
                op,
                reason));
        }

        public void SetApproval(ReviewApproval approval)
        {
            Approval = approval;
        }

        public void SetDelivery(ReviewDeliveryReference delivery)
        {
            Delivery = delivery;
        }
    }

    public sealed class ApprovalGateResult
    {
        public GateEligibilityStatus Status { get; }
        public bool IsEligible => Status == GateEligibilityStatus.Eligible;
        public IReadOnlyList<string> Reasons { get; }
        public IReadOnlyList<string> Warnings { get; }
        public string ReviewId { get; }
        public DateTime EvaluatedAt { get; }

        public ApprovalGateResult(
            GateEligibilityStatus status,
            IReadOnlyList<string> reasons,
            IReadOnlyList<string> warnings,
            string reviewId,
            DateTime evaluatedAt)
        {
            Status = status;
            Reasons = reasons;
            Warnings = warnings;
            ReviewId = reviewId;
            EvaluatedAt = evaluatedAt;
        }

        public static ApprovalGateResult Eligible(string reviewId, IReadOnlyList<string>? warnings = null)
        {
            return new ApprovalGateResult(
                GateEligibilityStatus.Eligible,
                Array.Empty<string>(),
                warnings ?? Array.Empty<string>(),
                reviewId,
                DateTime.UtcNow);
        }

        public static ApprovalGateResult NotEligible(string reviewId, IReadOnlyList<string> reasons, IReadOnlyList<string>? warnings = null)
        {
            return new ApprovalGateResult(
                GateEligibilityStatus.NotEligible,
                reasons,
                warnings ?? Array.Empty<string>(),
                reviewId,
                DateTime.UtcNow);
        }
    }

    public sealed class TraceabilityChain
    {
        public string SobId { get; }
        public string DwgPath { get; }
        public string DatabaseFingerprint { get; }
        public string RevisionId { get; }
        public string? SnapshotId { get; }
        public string ReviewId { get; }
        public ReviewStatus ReviewStatus { get; }
        public int TotalFindings { get; }
        public int OpenFindings { get; }
        public IReadOnlyList<string> PendingReferences { get; }
        public string? ApprovalState { get; }
        public string? DeliveryPackageId { get; }

        public TraceabilityChain(
            string sobId,
            string dwgPath,
            string databaseFingerprint,
            string revisionId,
            string? snapshotId,
            string reviewId,
            ReviewStatus reviewStatus,
            int totalFindings,
            int openFindings,
            IReadOnlyList<string> pendingReferences,
            string? approvalState,
            string? deliveryPackageId)
        {
            SobId = sobId;
            DwgPath = dwgPath;
            DatabaseFingerprint = databaseFingerprint;
            RevisionId = revisionId;
            SnapshotId = snapshotId;
            ReviewId = reviewId;
            ReviewStatus = reviewStatus;
            TotalFindings = totalFindings;
            OpenFindings = openFindings;
            PendingReferences = pendingReferences;
            ApprovalState = approvalState;
            DeliveryPackageId = deliveryPackageId;
        }
    }
}
