namespace PhaseA.Platform.Runs;

public sealed record PrototypeIterationPlanEvaluationResult(
    string Decision,
    string Summary,
    string Reason,
    string SuggestedAction,
    string? SuggestedPromptForRegeneration = null);
