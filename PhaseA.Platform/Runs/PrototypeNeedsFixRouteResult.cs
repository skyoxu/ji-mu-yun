using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed record PrototypeNeedsFixRouteResult(
    string RunId,
    string Status,
    string Summary,
    int GoalIndex,
    string? IterationSessionStatus,
    string? IterationGoalStatus,
    IReadOnlyList<ArtifactSnapshot> Artifacts);
