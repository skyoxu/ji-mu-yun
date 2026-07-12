namespace PhaseA.Platform.Data;

public sealed record ProjectAdminReviewQueueCommand(
    string AccountId,
    string ProjectId,
    string RouteId,
    string RequirementId,
    string Severity,
    string BlockingReason,
    string SourceArtifactPath,
    string EvidenceRefsJson,
    string Status = "open");

public sealed record ProjectAdminReviewQueueEntry(
    string Id,
    string AccountId,
    string ProjectId,
    string RouteId,
    string RequirementId,
    string Severity,
    string BlockingReason,
    string SourceArtifactPath,
    string EvidenceRefsJson,
    string Status,
    string DecisionStatus,
    string? DecisionActorAccountId,
    string DecisionReason,
    string DecisionMetadataJson,
    int DecisionVersion,
    string CreatedUtc,
    string UpdatedUtc,
    string? DecidedUtc,
    string? ProjectDeletedUtc,
    string? SupersedesEntryId,
    string? SupersededByEntryId);

public sealed record ProjectAdminReviewQueueQuery(
    string Status = "open",
    string? ProjectId = null,
    string? RouteId = null,
    string? Severity = null,
    int? MinimumAgeMinutes = null,
    int Limit = 100);

public sealed record ProjectAdminReviewDecisionRequest(
    string DecisionStatus,
    string DecisionReason,
    int ExpectedDecisionVersion,
    IReadOnlyList<string>? DecisionEvidenceRefs = null,
    string? DeferredOwner = null,
    string? DeferredUntilUtc = null,
    string? RecheckTrigger = null,
    IReadOnlyList<string>? AffectedRoutes = null);

public sealed record ProjectAdminReviewDecisionResult(
    string Status,
    string? FailureCode,
    ProjectAdminReviewQueueEntry? Entry);

public sealed record ProjectDiagnosticSpoolCommand(
    string AccountId,
    string ProjectId,
    string RouteId,
    string FailureFamily,
    string Severity,
    string SafeSummary,
    string EvidenceRefsJson,
    string SourceArtifactPath = "",
    string TriageStatus = "unresolved",
    string ProjectNameSnapshot = "",
    string RunId = "",
    string SourceRefsJson = "[]",
    string RedactionStatus = "redacted",
    string RetentionClass = "",
    string CleanupStatus = "preserved",
    string ReplacementEvidenceRefsJson = "[]",
    string AdminSummary = "",
    string RemediationHintId = "",
    string DedupeScopeKey = "");

public sealed record ProjectDiagnosticSpoolEntry(
    string Id,
    string DiagnosticId,
    string AccountId,
    string ProjectId,
    string ProjectNameSnapshot,
    string RunId,
    string RouteId,
    string FailureFamily,
    string Severity,
    string TriageStatus,
    string RetentionClass,
    string RedactionStatus,
    string SpoolRef,
    string SafeSummary,
    string UserSafeSummary,
    string SourceRefsJson,
    string EvidenceRefsJson,
    string SourceArtifactPath,
    string CleanupStatus,
    string ReplacementEvidenceRefsJson,
    string AdminSummary,
    string RemediationHintId,
    string CreatedUtc,
    string UpdatedUtc,
    string? ResolvedUtc,
    string? ProjectDeletedUtc,
    string? TriageDecisionBy,
    string TriageDecisionReason,
    string? DeletionEventId,
    string? ProjectTombstoneId);

public sealed record ProjectDiagnosticSpoolQuery(
    string TriageStatus = "unresolved",
    string? AccountId = null,
    string? ProjectId = null,
    string? RouteId = null,
    string? FailureFamily = null,
    string? Severity = null,
    int Limit = 100);

public sealed record ProjectDiagnosticTriageDecisionResult(
    string Status,
    string? FailureCode,
    ProjectDiagnosticSpoolEntry? Entry);

public sealed record ProjectDeleteTombstone(
    string ProjectTombstoneId,
    string DeletionEventId,
    string ProjectId,
    string AccountId,
    string ProjectName,
    string DeletedUtc,
    int UnresolvedAdminReviewCount,
    int UnresolvedDiagnosticCount,
    string EvidenceRefsJson);
