namespace PhaseA.Platform.Skills;

public sealed record SkillActionDefinition(
    string ActionId,
    string SkillName,
    string Label,
    string Description,
    string Visibility,
    string ExecutionMode);
