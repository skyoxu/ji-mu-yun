namespace PhaseA.Platform.Runs;

public sealed record PrototypeFeedbackRequest(
    string? Feedback,
    string? Model = null,
    string? SkillActionId = null,
    PrototypeGoalRepairContext? GoalRepair = null);

public sealed record PrototypeGoalRepairContext(
    string? SessionId,
    string? GoalId,
    int GoalIndex,
    string? GoalTitle,
    string? GoalDescription,
    string? AcceptanceHint,
    string? ResultSummary);
