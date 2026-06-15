namespace PhaseA.Platform.Runs;

public sealed record ProjectWorkflowRouteResult(
    string ProjectId,
    string StageId,
    string StageLabel,
    string Summary,
    string Recommendation,
    ProjectWorkflowNextAction NextAction,
    IReadOnlyList<ProjectWorkflowRouteStep> Steps,
    IReadOnlyList<ProjectWorkflowNextAction>? Actions = null);

public sealed record ProjectWorkflowRouteStep(
    string Id,
    string Label,
    string Status,
    string Evidence);

public sealed record ProjectWorkflowNextAction(
    string ActionId,
    string Label,
    string RunName,
    string ButtonLabel,
    string UiTarget,
    bool Enabled,
    string? DisabledReason = null);

public sealed record ProjectWorkflowIntentRequest(
    string? Message,
    string? Model = null);

public sealed record ProjectWorkflowIntentResult(
    bool ShouldRoute,
    string Intent,
    string RouteReason,
    string FeedbackSummary,
    string Status,
    string? FailureCode = null)
{
    public static ProjectWorkflowIntentResult NoRoute(string reason = "") =>
        new(false, "general_chat", reason, "", "succeeded");
}
