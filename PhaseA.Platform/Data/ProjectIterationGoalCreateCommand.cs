namespace PhaseA.Platform.Data;

public sealed record ProjectIterationGoalCreateCommand(
    int GoalIndex,
    string Title,
    string Description,
    string? AcceptanceHint);
