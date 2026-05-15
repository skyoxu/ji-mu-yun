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
    string? DefaultScene = null,
    string? DefaultSceneLabel = null,
    int? TddSummaryCount = null,
    int? TddRedCount = null,
    int? TddGreenCount = null,
    int? TddRefactorCount = null,
    IReadOnlyList<string>? PlaytestFocusPoints = null);
