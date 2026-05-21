using System.Text.Json;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeNeedsFixRouteService
{
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PrototypeQuickFixService _quickFixService;
    private readonly PrototypeRouteStateWriter _stateWriter;
    private readonly PrototypeContractService _contractService;

    public PrototypeNeedsFixRouteService(
        PhaseAMetadataStore metadataStore,
        PrototypeQuickFixService quickFixService,
        PrototypeRouteStateWriter stateWriter,
        PrototypeContractService? contractService = null)
    {
        _metadataStore = metadataStore;
        _quickFixService = quickFixService;
        _stateWriter = stateWriter;
        _contractService = contractService ?? new PrototypeContractService();
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
            return new PrototypeNeedsFixRouteResult("", "missing_plan", "当前项目还没有迭代计划。请先使用固定的“生成迭代计划”按钮创建计划；提交反馈不会自动生成计划。", 0, null, null, []);
        }

        var goal = ResolveGoal(details, request);
        if (goal is null)
        {
            return await RunProjectLevelNeedsFixAsync(project, details, request, cancellationToken);
        }

        var readme = _stateWriter.ReadProjectReadme(project);
        var prototypeContract = _contractService.Read(project);
        var stepState = _stateWriter.ReadLatestNeedsFixState(project, goal.GoalIndex);
        var executeNextGoalState = string.IsNullOrWhiteSpace(stepState)
            ? _stateWriter.ReadLatestExecuteNextGoalState(project, goal.GoalIndex)
            : "";
        var prototypeState = string.IsNullOrWhiteSpace(stepState) && string.IsNullOrWhiteSpace(executeNextGoalState)
            ? _stateWriter.ReadLatestPrototypeState(project)
            : "";
        if (string.IsNullOrWhiteSpace(stepState) && string.IsNullOrWhiteSpace(executeNextGoalState) && string.IsNullOrWhiteSpace(prototypeState))
        {
            return new PrototypeNeedsFixRouteResult("", "prototype_required", "当前项目缺少可恢复的原型路线产物。请先运行原型创建，再使用 Needs Fix 路由。", goal.GoalIndex, details.Session.Status, goal.Status, []);
        }

        var feedback = BuildFeedback(project, request.Feedback, readme, prototypeContract, stepState, executeNextGoalState, prototypeState, goal);
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
                    BuildCompactSummary(goal.ResultSummary))),
            requireSucceededPrototypeRun: false,
            cancellationToken);

        _stateWriter.WriteNeedsFixState(project, goal.GoalIndex, new
        {
            route = "needs-fix",
            route_skill = PrototypeRouteSkillPolicy.Resolve(project),
            project_id = project.ProjectId,
            session_id = details.Session.SessionId,
            goal_id = goal.GoalId,
            goal_index = goal.GoalIndex,
            run_id = quickFixResult.RunId,
            status = quickFixResult.Status,
            iteration_session_status = quickFixResult.IterationSessionStatus,
            iteration_goal_status = quickFixResult.IterationGoalStatus,
            summary = BuildCompactSummary(quickFixResult.AssistantMessage),
            consumed = new
            {
                project_readme = !string.IsNullOrWhiteSpace(readme),
                prototype_contract = !string.IsNullOrWhiteSpace(prototypeContract.Json),
                prototype_contract_path = prototypeContract.RelativePath
            },
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

    private async Task<PrototypeNeedsFixRouteResult> RunProjectLevelNeedsFixAsync(
        ProjectSnapshot project,
        ProjectIterationSessionDetails details,
        PrototypeNeedsFixRouteRequest request,
        CancellationToken cancellationToken)
    {
        var feedback = BuildProjectLevelFeedback(project, request.Feedback, _stateWriter.ReadProjectReadme(project), _contractService.Read(project), _stateWriter.ReadLatestPrototypeState(project));
        var quickFixResult = await _quickFixService.SubmitAsync(
            project.ProjectId,
            new PrototypeFeedbackRequest(
                feedback,
                request.Model,
                request.SkillActionId,
                null),
            requireSucceededPrototypeRun: false,
            cancellationToken);

        _stateWriter.WriteNeedsFixState(project, 0, new
        {
            route = "needs-fix",
            scope = "project",
            route_skill = PrototypeRouteSkillPolicy.Resolve(project),
            project_id = project.ProjectId,
            session_id = details.Session.SessionId,
            run_id = quickFixResult.RunId,
            status = quickFixResult.Status,
            summary = BuildCompactSummary(quickFixResult.AssistantMessage),
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });

        return new PrototypeNeedsFixRouteResult(
            quickFixResult.RunId,
            quickFixResult.Status,
            quickFixResult.AssistantMessage,
            0,
            details.Session.Status,
            null,
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
               ?? details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "failed", StringComparison.Ordinal))
               ?? details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "running", StringComparison.Ordinal))
               ?? details.Goals.FirstOrDefault(goal =>
                   goal.GoalIndex == details.Session.CurrentGoalIndex &&
                   !string.Equals(goal.Status, "pending", StringComparison.Ordinal) &&
                   !string.Equals(goal.Status, "succeeded", StringComparison.Ordinal));
    }

    private static string BuildFeedback(
        ProjectSnapshot project,
        string? userFeedback,
        string projectReadme,
        PrototypeContractSnapshot prototypeContract,
        string stepState,
        string executeNextGoalState,
        string prototypeState,
        ProjectIterationGoalSnapshot goal)
    {
        var sourceLabel = !string.IsNullOrWhiteSpace(stepState)
            ? "current needs fix step state"
            : !string.IsNullOrWhiteSpace(executeNextGoalState)
                ? "current execute next goal step state"
                : "prototype route state";
        var sourceState = CompactRouteState(!string.IsNullOrWhiteSpace(stepState)
            ? stepState
            : !string.IsNullOrWhiteSpace(executeNextGoalState)
                ? executeNextGoalState
                : prototypeState);
        return $"""
            Run the needs fix top-level route for the current prototype iteration step.

            Direction lock:
            - The repair target is only the Current goal below.
            - Project README and Recovery source are read-only recovery context, not repair targets.
            - Do not repair Phase A platform routing, route-state readers, recovery logic, docs, scripts, deployment, or tests unless the Current goal explicitly asks for that.
            - If Current goal is a gameplay/Godot/RPG goal, repair gameplay files only and verify the gameplay acceptance described by AcceptanceHint.
            - Platform route or recovery tests passing does not prove a gameplay goal is complete.

            Project README:
            {TrimForPrompt(projectReadme)}

            {PrototypeContractService.BuildPromptBlock(prototypeContract)}

            Current goal:
            - GoalIndex: {goal.GoalIndex}
            - Title: {goal.Title}
            - Description: {goal.Description}
            - AcceptanceHint: {goal.AcceptanceHint}
            - PreviousResultSummary: {BuildCompactSummary(goal.ResultSummary)}

            Recovery source consumed: {sourceLabel}
            {TrimForPrompt(sourceState)}

            User feedback:
            {userFeedback?.Trim()}

            Scope rule:
            Only repair this current step. Do not read or use needs fix state from another step.

            {PrototypeRouteSkillPolicy.BuildPromptBlock(project)}
            """;
    }

    private static string BuildProjectLevelFeedback(
        ProjectSnapshot project,
        string? userFeedback,
        string projectReadme,
        PrototypeContractSnapshot prototypeContract,
        string prototypeState)
    {
        return $"""
            Run the needs fix top-level route for a project-level runtime issue.

            Direction lock:
            - This request is still needs-fix-route, but it is not bound to a single iteration step.
            - Repair the user's reported runtime issue in the hosted game project.
            - Do not generate or rewrite the iteration plan.
            - Do not repair Phase A platform routing, route-state readers, recovery logic, deployment, or tests.
            - Prefer gameplay/project files only. If the report is too vague, inspect the Godot project configuration and fix the concrete runtime wiring problem that matches the report.
            - Output must be browser-safe: do not expose paths, command lines, script names, logs, or environment variables.

            Project README:
            {CompactRouteState(projectReadme)}

            {PrototypeContractService.BuildPromptBlock(prototypeContract)}

            Prototype route state:
            {CompactRouteState(prototypeState)}

            Project:
            - ProjectId: {project.ProjectId}
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}

            User reported issue:
            {userFeedback}
            """;
    }

    private static string BuildCompactSummary(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var lines = value
            .Replace("\r\n", "\n", StringComparison.Ordinal)
            .Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(line => !line.StartsWith("Project README:", StringComparison.OrdinalIgnoreCase))
            .Where(line => !line.StartsWith("Recovery source consumed:", StringComparison.OrdinalIgnoreCase))
            .Where(line => !line.StartsWith("{", StringComparison.Ordinal))
            .Take(8);
        var summary = string.Join(" ", lines);
        return summary.Length <= 1200 ? summary : summary[..1200];
    }

    private static string CompactRouteState(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "(empty)";
        }

        try
        {
            using var document = JsonDocument.Parse(value);
            var root = document.RootElement;
            var compact = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["route"] = ReadString(root, "route"),
                ["status"] = ReadString(root, "status"),
                ["run_id"] = ReadString(root, "run_id"),
                ["goal_index"] = ReadInt(root, "goal_index"),
                ["iteration_session_status"] = ReadString(root, "iteration_session_status"),
                ["iteration_goal_status"] = ReadString(root, "iteration_goal_status"),
                ["summary"] = BuildCompactSummary(ReadString(root, "summary"))
            };

            return JsonSerializer.Serialize(compact.Where(pair => pair.Value is not null).ToDictionary(pair => pair.Key, pair => pair.Value));
        }
        catch (JsonException)
        {
            return TrimForPrompt(BuildCompactSummary(value));
        }
    }

    private static string? ReadString(JsonElement root, string propertyName)
    {
        return root.ValueKind == JsonValueKind.Object &&
               root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;
    }

    private static int? ReadInt(JsonElement root, string propertyName)
    {
        return root.ValueKind == JsonValueKind.Object &&
               root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.Number &&
               value.TryGetInt32(out var result)
            ? result
            : null;
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
