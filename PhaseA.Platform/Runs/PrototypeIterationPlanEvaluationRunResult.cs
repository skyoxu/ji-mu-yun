namespace PhaseA.Platform.Runs;

public sealed record PrototypeIterationPlanEvaluationRunResult(
    string RunId,
    string Status,
    PrototypeIterationPlanEvaluationResult Evaluation);
