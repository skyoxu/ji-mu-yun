namespace PhaseA.Platform.Runs;

public sealed record PrototypeNeedsFixRouteRequest(
    string? Feedback = null,
    string? Model = null,
    string? SkillActionId = null,
    string? GoalId = null,
    int? GoalIndex = null);
