namespace PhaseA.Platform.Runs;

public sealed record PrototypeWorkflowProgress(
    string Status,
    string Step,
    string Substep,
    string Label,
    string? UpdatedUtc,
    string? RunId,
    string? Failure,
    string? CompletionSummary = null,
    string? NextStepSource = null,
    string? NextStepEvaluation = null,
    string? NextStepEvaluationReason = null,
    string? DefaultScene = null,
    string? DefaultSceneLabel = null,
    int? TddSummaryCount = null,
    int? TddRedCount = null,
    int? TddGreenCount = null,
    int? TddRefactorCount = null,
    IReadOnlyList<string>? PlaytestFocusPoints = null,
    PrototypeWorkflowFormSnapshot? Form = null,
    string? PrototypeCreationStatus = null,
    string? PrototypeCreationFailure = null,
    string? PrototypeCreationRunId = null,
    string? AcceptanceStatus = null,
    string? AcceptanceFailure = null,
    string? AcceptanceRunId = null);

public sealed record PrototypeWorkflowFormSnapshot(
    string? PrototypeSlug,
    string? Hypothesis,
    string? CorePlayerFantasy,
    string? MinimumPlayableLoop,
    IReadOnlyList<string>? SuccessCriteria,
    string? GameFeature,
    string? CoreGameplayLoop,
    string? WinFailConditions,
    string? SourcePath);
