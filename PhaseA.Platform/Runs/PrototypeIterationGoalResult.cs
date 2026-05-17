namespace PhaseA.Platform.Runs;

public sealed record PrototypeIterationGoalExecutionResult(
    string SessionId,
    string GoalId,
    string RunId,
    string Status,
    string Summary,
    int GoalIndex,
    bool HasMoreGoals,
    string SessionStatus);
