namespace PhaseA.Platform.Runs;

public sealed record PrototypeIterationPlanResult(
    string SessionId,
    string Status,
    string Summary,
    IReadOnlyList<PrototypeIterationPlanGoalResult> Goals,
    PrototypeIterationPlanningAnalysisResult? PlanningAnalysis = null,
    PrototypeIterationPlanEvaluationResult? LatestEvaluation = null);

public sealed record PrototypeIterationPlanGoalResult(
    int GoalIndex,
    string Title,
    string Description,
    string AcceptanceHint,
    string Status);

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
