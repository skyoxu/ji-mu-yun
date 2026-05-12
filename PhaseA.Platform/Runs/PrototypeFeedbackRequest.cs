namespace PhaseA.Platform.Runs;

public sealed record PrototypeFeedbackRequest(
    string? Feedback,
    string? Model = null,
    string? SkillActionId = null);
