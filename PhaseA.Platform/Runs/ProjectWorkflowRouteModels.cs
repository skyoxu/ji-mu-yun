namespace PhaseA.Platform.Runs;

public sealed record ProjectWorkflowRouteResult(
    string ProjectId,
    string StageId,
    string StageLabel,
    string Summary,
    string Recommendation,
    ProjectWorkflowNextAction NextAction,
    IReadOnlyList<ProjectWorkflowRouteStep> Steps,
    IReadOnlyList<ProjectWorkflowNextAction>? Actions = null,
    IReadOnlyList<ProjectWorkflowStageDefinition>? StageDefinitions = null,
    ProjectWorkflowSeverityReview? AcceptanceReview = null,
    ProjectWorkflowRecommendation? WorkflowRecommendation = null,
    ProjectRouteStateArtifactReadback? RouteStateArtifacts = null,
    ProjectBusinessChainStatus? BusinessChain = null);

public sealed record ProjectWorkflowRouteStep(
    string Id,
    string Label,
    string Status,
    string Evidence,
    string? StageGroup = null,
    string? SeverityGate = null);

public sealed record ProjectWorkflowStageDefinition(
    string Id,
    string Label,
    string StageGroup,
    string RequiredEvidence,
    string SeverityGate);

public sealed record ProjectWorkflowSeverityReview(
    string Status,
    IReadOnlyList<string> BlockingSeverities,
    IReadOnlyList<string> EvidenceRefs,
    string Summary);

public sealed record ProjectWorkflowRecommendation(
    string SchemaVersion,
    ProjectWorkflowActionDescriptorRef ActionDescriptorRef,
    string RecommendedAction,
    string Reason,
    string StatusDimension,
    IReadOnlyList<string> StatusAllowedValues,
    string Status,
    string ReadinessScope,
    string StatusReason,
    IReadOnlyList<ProjectWorkflowBlockingIssue> BlockingIssues,
    IReadOnlyList<ProjectWorkflowRecommendationAction> AllowedActions,
    IReadOnlyList<ProjectWorkflowRecommendationAction> ForbiddenActions,
    IReadOnlyList<string> StaleArtifacts,
    string UpdatedUtc,
    IReadOnlyList<ProjectRouteStateEvidenceRef> EvidenceRefs);

public sealed record ProjectWorkflowActionDescriptorRef(
    string DescriptorId,
    string DescriptorVersion,
    string DescriptorHash);

public sealed record ProjectWorkflowRecommendationAction(
    string ActionId,
    string DescriptorHash,
    string ExposureClass,
    string PhaseEligibility,
    string ApiRoute,
    string BrowserActionId,
    string DisplayLabelKey,
    string OperationScope,
    string ReadbackUrl,
    IReadOnlyList<string> BlockingIssueRefs,
    string? DisabledReason = null,
    string? DisabledDomainCode = null,
    string? MissingContractRef = null,
    string? RequiredPhase = null);

public sealed record ProjectWorkflowBlockingIssue(
    string IssueId,
    string DomainCode,
    string Severity,
    string Summary,
    IReadOnlyList<ProjectRouteStateEvidenceRef> EvidenceRefs);

public sealed record ProjectRouteStateArtifactReadback(
    string Status,
    string StatusReason,
    IReadOnlyList<ProjectRouteStateArtifactSummary> Artifacts,
    IReadOnlyList<ProjectWorkflowBlockingIssue> BlockingIssues);

public sealed record ProjectRouteStateArtifactSummary(
    string Route,
    string CanonicalPath,
    string? MirrorPath,
    string Authority,
    string Status,
    string StatusDimension,
    IReadOnlyList<string> StatusAllowedValues,
    string Freshness,
    IReadOnlyList<string> BlockingIssueIds,
    IReadOnlyList<GameDesignRequirementRow>? Requirements = null,
    string? SourceGddHash = null,
    string? SourceSceneRouteHash = null,
    string? SourceRequirementMapHash = null,
    string? SourceGodotUiContractHash = null,
    string? SourceUiStyleContractHash = null,
    string? UiStyleSnapshotHash = null,
    string? SourceIterationSessionHash = null,
    string? SourceValidationInputHash = null,
    string? SourceContractHash = null);

public sealed record ProjectRouteStateEvidenceRef(
    string Kind,
    string Path,
    string? Summary = null);

public sealed record ProjectWorkflowNextAction(
    string ActionId,
    string Label,
    string RunName,
    string ButtonLabel,
    string UiTarget,
    bool Enabled,
    string? DisabledReason = null);

public sealed record ProjectWorkflowIntentRequest(
    string? Message,
    string? Model = null);

public sealed record ProjectWorkflowIntentResult(
    bool ShouldRoute,
    string Intent,
    string RouteReason,
    string FeedbackSummary,
    string Status,
    string? FailureCode = null)
{
    public static ProjectWorkflowIntentResult NoRoute(string reason = "") =>
        new(false, "general_chat", reason, "", "succeeded");
}
