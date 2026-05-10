namespace PhaseA.Platform.Runs;

public sealed record PrototypeWorkflowRequest(
    string? Slug,
    string? Hypothesis,
    string? CorePlayerFantasy,
    string? MinimumPlayableLoop,
    IReadOnlyList<string>? SuccessCriteria,
    string? GameFeature,
    string? CoreGameplayLoop,
    string? WinFailConditions,
    bool Confirm = false,
    int? StopAfterDay = null,
    string? ScoreEngine = null);
