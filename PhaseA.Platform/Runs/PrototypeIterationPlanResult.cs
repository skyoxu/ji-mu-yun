namespace PhaseA.Platform.Runs;

public sealed record PrototypeIterationPlanResult(
    string SessionId,
    string Status,
    string Summary,
    IReadOnlyList<PrototypeIterationPlanGoalResult> Goals);

public sealed record PrototypeIterationPlanGoalResult(
    int GoalIndex,
    string Title,
    string Description,
    string AcceptanceHint,
    string Status);
