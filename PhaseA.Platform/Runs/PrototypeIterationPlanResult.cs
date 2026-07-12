namespace PhaseA.Platform.Runs;

public sealed record PrototypeIterationPlanResult(
    string SessionId,
    string Status,
    string Summary,
    IReadOnlyList<PrototypeIterationPlanGoalResult> Goals,
    PrototypeIterationPlanningAnalysisResult? PlanningAnalysis = null,
    PrototypeIterationPlanEvaluationResult? LatestEvaluation = null,
    IReadOnlyList<PrototypeIterationPlanRequiredModuleResult>? RequiredModules = null,
    string OperationStatus = "",
    string PlanHash = "",
    PrototypeIterationPlanSourceHashes? SourceHashes = null,
    PrototypeIterationPlanCoverageResult? Coverage = null,
    IReadOnlyList<PrototypeIterationPlanBlockerResult>? Blockers = null,
    PrototypeIterationPlanConfirmationResult? Confirmation = null,
    PrototypeIterationStyleApplicability? StyleApplicability = null);

public sealed record PrototypeIterationPlanRequiredModuleResult(
    string Id,
    string Source,
    string Status,
    string AppliesUnless,
    IReadOnlyList<string> AcceptanceMarkers,
    string? CoveredByGoalCapability,
    IReadOnlyList<string>? RequirementIds = null,
    string SourceReason = "",
    IReadOnlyList<string>? SourceRefs = null,
    string Priority = "P2",
    string CoverageStatus = "unknown",
    IReadOnlyList<string>? ValidationRefs = null);

public sealed record PrototypeIterationPlanGoalResult(
    int GoalIndex,
    string Title,
    string Description,
    string AcceptanceHint,
    string Status,
    IReadOnlyList<string>? RequirementIds = null,
    PrototypeIterationInfrastructureReason? InfrastructureReason = null,
    string SourceHashRef = "",
    PrototypeIterationUiSurfaceResult? UiSurface = null,
    PrototypeIterationStyleResult? Style = null,
    PrototypeIterationEngineSemanticsResult? EngineSemantics = null,
    PrototypeIterationInteractionRegionResult? InteractionRegion = null,
    GodotUiUpdateOwnership? GodotUiUpdateOwnership = null,
    GodotThirdPersonCameraProfile? GodotThirdPersonCameraProfile = null,
    PrototypeIterationCapabilityRequirements? CapabilityRequirements = null);

public sealed record PrototypeIterationCapabilityRequirements(
    bool DynamicUiRequired,
    bool ThirdPersonCameraRequired,
    bool FeatureFamilyReadingRequired,
    bool InteractionRegionRequired);

public sealed record PrototypeIterationPlanSourceHashes(
    string SourceGddHash,
    string SourceSceneRouteHash,
    string SourceRequirementMapHash,
    string SourceContractHash,
    string SourceContractSnapshotHash,
    string SourceGodotUiContractHash,
    string SourceUiStyleContractHash,
    string UiStyleSnapshotHash);

public sealed record PrototypeIterationStyleApplicability(
    string Status,
    string Reason,
    string ReviewedBy,
    string RecheckTrigger,
    string EvidenceHash);

public sealed record PrototypeIterationPlanCoverageResult(
    int P0P1RequirementCount,
    int GoalCoveredCount,
    int ModuleCoveredCount,
    int SkeletonCoveredCount,
    int ExplicitBlockerCount,
    IReadOnlyList<string> UncoveredRequirementIds);

public sealed record PrototypeIterationPlanBlockerResult(
    string DomainCode,
    string Severity,
    string Summary,
    IReadOnlyList<string> RequirementIds,
    IReadOnlyList<string> EvidenceRefs);

public sealed record PrototypeIterationPlanConfirmationResult(
    string Status,
    string SessionId,
    string PlanHash,
    string SourceHashRef,
    string ConfirmedBy,
    string ConfirmedUtc);

public sealed record PrototypeIterationPlanConfirmationRequest(string SessionId, string PlanHash);

public sealed record PrototypeIterationPlanConfirmationOperationResult(
    string Status,
    string DomainCode,
    string Summary,
    string OperationStatus,
    PrototypeIterationPlanConfirmationResult? Confirmation = null);

public sealed record PrototypeIterationInfrastructureReason(
    string Code,
    string Summary,
    IReadOnlyList<string> SourceRefs);

public sealed record PrototypeIterationUiSurfaceResult(
    string SceneOwner,
    string NodeOwner,
    string SurfaceType,
    string Layout,
    string ViewportMode,
    string CanvasLayer,
    string InputOwnership,
    string FocusPolicy,
    IReadOnlyList<string> FeedbackStates,
    string StateBoundary,
    IReadOnlyList<string> ValidationRefs,
    string NoUiNeededDecisionRef = "");

public sealed record PrototypeIterationStyleResult(
    IReadOnlyList<string> StyleTokenRefs,
    IReadOnlyList<string> ComponentFamilies,
    IReadOnlyList<string> DesignDna,
    string Composition,
    string Motion,
    string UiTreeReadback,
    IReadOnlyList<string> VisualEvidenceExpectations,
    string StyleNotApplicableDecisionRef = "");

public sealed record PrototypeIterationEngineSemanticsResult(
    string ViewportSemantics,
    string CoordinateSemantics,
    string InputSemantics,
    string LayerSemantics,
    IReadOnlyList<string> ProfileRefs,
    IReadOnlyList<string> ReadingEvidenceRefs);

public sealed record PrototypeIterationInteractionRegionResult(
    string ArtifactRef,
    IReadOnlyList<string> Devices,
    IReadOnlyList<string> ValidRegions,
    IReadOnlyList<string> InvalidRegions,
    IReadOnlyList<string> StateTransitions,
    IReadOnlyList<string> ValidationRefs,
    string NoInteractionRegionNeededDecisionRef = "",
    IReadOnlyList<string>? OwnerRefs = null)
{
    public IReadOnlyList<string> OwnerRefs { get; init; } = OwnerRefs ?? [];

    public IReadOnlyList<PrototypeIterationInteractionGeometryResult> PlannedGeometry { get; init; } = [];
}

public sealed record PrototypeIterationInteractionGeometryResult(
    string GeometryId,
    string OwnerRef,
    string GeometryKind,
    string CoordinateSpace,
    PrototypeIterationInteractionBounds? Bounds,
    string Shape,
    string InteractionRole,
    string LocatorRef,
    string ResolutionSource,
    string BoundsPolicy);

public sealed record PrototypeIterationInteractionBounds(
    double X,
    double Y,
    double Width,
    double Height);

public sealed record PrototypeIterationPlanDeleteResult(
    string Status,
    string Summary,
    int DeletedSessions);

public sealed record PrototypeIterationPlanningAnalysisResult(
    string AnalysisSource,
    string AnalysisSummary,
    string LatestPrototypeStatus,
    string? LatestPrototypeCompletionSummary,
    int DraftCoveragePercent,
    string? DraftCoverageSummary,
    string? TemplateId,
    IReadOnlyList<PrototypeIterationPlanningFieldResult> FieldCoverage,
    IReadOnlyList<PrototypeIterationPlanStageTelemetryResult>? StageTelemetry = null);

public sealed record PrototypeIterationPlanningFieldResult(
    string Field,
    string Status,
    string? Evidence,
    string? MissingReason);

public sealed record PrototypeIterationPlanStageTelemetryResult(
    string Stage,
    string Model,
    long DurationMs,
    int PromptLength,
    int PromptUtf8Bytes,
    int EstimatedPromptTokens,
    string? FailureCode,
    string? FailureCategory);

internal sealed record PrototypeSkeletonRegenerationDecision(
    bool RequiresPrototypeRecreation,
    string? Reason)
{
    public static PrototypeSkeletonRegenerationDecision NotRequired() => new(false, null);
}
