namespace PhaseA.Platform.Runs;

public sealed record PrototypeIterationPlanEvaluationRunResult(
    string RunId,
    string Status,
    PrototypeIterationPlanEvaluationResult Evaluation)
{
    public string OperationStatus => string.IsNullOrWhiteSpace(RunId) ? "rejected" : "created_run";
}
