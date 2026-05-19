using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeNeedsFixRouteService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PrototypeQuickFixService _quickFixService;
    private readonly PrototypeRouteStateWriter _stateWriter;

    public PrototypeNeedsFixRouteService(
        PhaseAMetadataStore metadataStore,
        PrototypeQuickFixService quickFixService,
        PrototypeRouteStateWriter stateWriter)
    {
        _metadataStore = metadataStore;
        _quickFixService = quickFixService;
        _stateWriter = stateWriter;
    }

    public async Task<PrototypeNeedsFixRouteResult> RunAsync(
        string accountId,
        string projectId,
        PrototypeNeedsFixRouteRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, cancellationToken);
        if (details is null)
        {
            return new PrototypeNeedsFixRouteResult("", "missing_plan", "Please generate an iteration plan before running needs fix.", 0, null, null, []);
        }

        var goal = ResolveGoal(details, request);
        if (goal is null)
        {
            return new PrototypeNeedsFixRouteResult("", "missing_goal", "No current needs fix goal was found.", 0, details.Session.Status, null, []);
        }

        var readme = _stateWriter.ReadProjectReadme(project);
        var stepState = _stateWriter.ReadLatestNeedsFixState(project, goal.GoalIndex);
        var prototypeState = string.IsNullOrWhiteSpace(stepState)
            ? _stateWriter.ReadLatestPrototypeState(project)
            : "";
        if (string.IsNullOrWhiteSpace(stepState) && string.IsNullOrWhiteSpace(prototypeState))
        {
            return new PrototypeNeedsFixRouteResult("", "prototype_required", "Please run prototype creation before needs fix.", goal.GoalIndex, details.Session.Status, goal.Status, []);
        }

        var feedback = BuildFeedback(request.Feedback, readme, stepState, prototypeState, goal);
        var quickFixResult = await _quickFixService.SubmitAsync(
            project.ProjectId,
            new PrototypeFeedbackRequest(
                feedback,
                request.Model,
                request.SkillActionId,
                new PrototypeGoalRepairContext(
                    details.Session.SessionId,
                    goal.GoalId,
                    goal.GoalIndex,
                    goal.Title,
                    goal.Description,
                    goal.AcceptanceHint,
                    goal.ResultSummary)),
            requireSucceededPrototypeRun: false,
            cancellationToken);

        _stateWriter.WriteNeedsFixState(project, goal.GoalIndex, new
        {
            route = "needs-fix",
            project_id = project.ProjectId,
            session_id = details.Session.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            run_id = quickFixResult.RunId,
            status = quickFixResult.Status,
            iteration_session_status = quickFixResult.IterationSessionStatus,
            iteration_goal_status = quickFixResult.IterationGoalStatus,
            summary = quickFixResult.AssistantMessage,
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });

        return new PrototypeNeedsFixRouteResult(
            quickFixResult.RunId,
            quickFixResult.Status,
            quickFixResult.AssistantMessage,
            goal.GoalIndex,
            quickFixResult.IterationSessionStatus,
            quickFixResult.IterationGoalStatus,
            quickFixResult.Artifacts);
    }

    private static ProjectIterationGoalSnapshot? ResolveGoal(ProjectIterationSessionDetails details, PrototypeNeedsFixRouteRequest request)
    {
        if (!string.IsNullOrWhiteSpace(request.GoalId))
        {
            return details.Goals.FirstOrDefault(goal => string.Equals(goal.GoalId, request.GoalId, StringComparison.Ordinal));
        }

        if (request.GoalIndex is > 0)
        {
            return details.Goals.FirstOrDefault(goal => goal.GoalIndex == request.GoalIndex.Value);
        }

        return details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "needs_fix", StringComparison.Ordinal))
               ?? details.Goals.FirstOrDefault(goal => goal.GoalIndex == details.Session.CurrentGoalIndex)
               ?? details.Goals.FirstOrDefault();
    }

    private static string BuildFeedback(
        string? userFeedback,
        string projectReadme,
        string stepState,
        string prototypeState,
        ProjectIterationGoalSnapshot goal)
    {
        var sourceLabel = string.IsNullOrWhiteSpace(stepState)
            ? "prototype route state"
            : "current needs fix step state";
        var sourceState = string.IsNullOrWhiteSpace(stepState) ? prototypeState : stepState;
        return $"""
            Run the needs fix top-level route for the current prototype iteration step.

            Project README:
            {TrimForPrompt(projectReadme)}

            Current goal:
            - GoalIndex: {goal.GoalIndex}
            - Title: {goal.Title}
            - Description: {goal.Description}
            - AcceptanceHint: {goal.AcceptanceHint}
            - PreviousResultSummary: {goal.ResultSummary}

            Recovery source consumed: {sourceLabel}
            {TrimForPrompt(sourceState)}

            User feedback:
            {userFeedback?.Trim()}

            Scope rule:
            Only repair this current step. Do not read or use needs fix state from another step.
            """;
    }

    private static string TrimForPrompt(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "(empty)";
        }

        var trimmed = value.Trim();
        return trimmed.Length <= 6000 ? trimmed : trimmed[..6000];
    }
}
