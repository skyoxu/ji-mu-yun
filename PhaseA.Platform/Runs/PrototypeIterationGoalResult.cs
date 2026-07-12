namespace PhaseA.Platform.Runs;

public sealed record PrototypeIterationGoalExecutionResult(
    string SessionId,
    string GoalId,
    string RunId,
    string Status,
    string Summary,
    int GoalIndex,
    bool HasMoreGoals,
    string SessionStatus)
{
    public string OperationStatus => string.IsNullOrWhiteSpace(RunId)
        ? "rejected"
        : string.Equals(Status, "project_busy", StringComparison.Ordinal)
            ? "active_run_reused"
            : "created_run";
}
