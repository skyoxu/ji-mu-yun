using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed record PrototypeFeedbackResult(
    string RunId,
    string Status,
    string AssistantMessage,
    IReadOnlyList<ArtifactSnapshot> Artifacts,
    string? IterationSessionStatus = null,
    string? IterationGoalStatus = null,
    int? IterationGoalIndex = null);
