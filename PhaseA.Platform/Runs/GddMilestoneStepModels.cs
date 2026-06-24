namespace PhaseA.Platform.Runs;

public sealed record GddMilestoneStepPlanResult(
    string ProjectId,
    string Status,
    string Summary,
    IReadOnlyList<GddMilestoneStepResult> Steps,
    string? CurrentStepId = null,
    string? FailureCode = null);

public sealed record GddMilestoneStepResult(
    string StepId,
    int StepIndex,
    string Title,
    string Description,
    string Acceptance,
    string ScopeIn,
    string ScopeOut,
    string GodotSlice,
    string PackagingValidation,
    string FeedbackGuidance,
    string NextStepReview,
    string Status,
    bool Locked,
    bool CanExecute,
    bool CanConfirm,
    bool CanSubmitFeedback,
    string? ReviewSummary = null,
    string? SpecRelativePath = null,
    string? LatestEvidenceRelativePath = null);

public sealed record GddMilestoneStepConfirmRequest(
    string? Notes = null,
    string? Model = null);

public sealed record GddMilestoneStepFeedbackRequest(
    string? Feedback,
    string? Model = null);

public sealed record GddMilestoneStepActionResult(
    string ProjectId,
    string StepId,
    string Status,
    string Summary,
    GddMilestoneStepPlanResult? Plan = null,
    PrototypeIterationPlanResult? IterationPlan = null,
    PrototypeFeedbackResult? FeedbackRun = null,
    PrototypeIterationGoalExecutionResult? StepExecution = null,
    PrototypeNeedsFixRouteResult? NeedsFixRun = null,
    string? FailureCode = null);
