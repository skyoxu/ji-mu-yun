using PhaseA.Platform.Data;

namespace PhaseA.Platform.Skills;

public sealed record SkillActionRunResult(
    string RunId,
    string Status,
    int ExitCode,
    string ActionId,
    string SkillName,
    string AssistantMessage,
    IReadOnlyList<ArtifactSnapshot> Artifacts,
    string? FailureCode = null);
