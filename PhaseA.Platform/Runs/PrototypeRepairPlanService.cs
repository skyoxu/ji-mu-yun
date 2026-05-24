using System.Text.Json;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeRepairPlanService
{
    private const string SourceKind = "repair_plan";
    private const string ExecuteRunType = "prototype-repair-step";

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PrototypeQuickFixService _quickFixService;
    private readonly PrototypeRouteStateWriter _stateWriter;
    private readonly PrototypeContractService _contractService;

    public PrototypeRepairPlanService(
        PhaseAMetadataStore metadataStore,
        PrototypeQuickFixService quickFixService)
        : this(metadataStore, quickFixService, new PrototypeRouteStateWriter(), new PrototypeContractService())
    {
    }

    public PrototypeRepairPlanService(
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

    public async Task<PrototypeRepairPlanResult> CreateAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await RequireProjectAsync(accountId, projectId, cancellationToken);
        var failedRun = await FindLatestFailedRunAsync(project.ProjectId, cancellationToken);
        if (failedRun is null)
        {
            return new PrototypeRepairPlanResult("", "missing_failure", "当前项目没有可用于生成修复计划的失败记录。", []);
        }

        var failureText = BuildFailureText(failedRun);
        var goals = BuildRepairGoals(failureText);
        var summary = $"已基于最近一次失败生成 {goals.Count} 个修复步骤。请逐项执行，最后一步必须做全量验收。";
        var session = await _metadataStore.CreateProjectIterationSessionAsync(
            accountId,
            project.ProjectId,
            SourceKind,
            BuildSourceMessage(failedRun, failureText),
            "Repair the failed prototype route through small isolated repair steps.",
            goals.Select(goal => new ProjectIterationGoalCreateCommand(
                goal.GoalIndex,
                goal.Title,
                goal.Description,
                goal.AcceptanceHint)).ToArray(),
            cancellationToken);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(session.SessionId, "ready", 0, summary, null, null, cancellationToken);

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, SourceKind, cancellationToken);
        _stateWriter.WriteNeedsFixState(project, 0, new
        {
            route = "repair-plan",
            source_kind = SourceKind,
            source_run_id = failedRun.RunId,
            session_id = session.SessionId,
            status = "ready",
            summary,
            route_skill = PrototypeRouteSkillPolicy.Resolve(project),
            prototype_contract = _contractService.Read(project).RelativePath,
            goals = goals.Select(goal => new
            {
                goal.GoalIndex,
                goal.Title,
                goal.Description,
                goal.AcceptanceHint,
                goal.Status
            }).ToArray(),
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });

        return PrototypeRepairPlanResult.FromDetails(details!, summary);
    }

    public async Task<PrototypeRepairPlanResult?> GetLatestAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, SourceKind, cancellationToken);
        return details is null
            ? null
            : PrototypeRepairPlanResult.FromDetails(details, details.Session.LatestSummary ?? "已有修复计划。");
    }

    public async Task<PrototypeRepairStepExecutionResult> ExecuteNextAsync(
        string accountId,
        string projectId,
        PrototypeRepairStepExecutionRequest request,
        CancellationToken cancellationToken = default)
    {
        var project = await RequireProjectAsync(accountId, projectId, cancellationToken);
        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, SourceKind, cancellationToken);
        if (details is null)
        {
            return new PrototypeRepairStepExecutionResult("", "", "", "missing_repair_plan", "当前项目还没有修复计划，请先生成修复计划。", 0, false, "missing_repair_plan");
        }

        var current = details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "needs_fix", StringComparison.OrdinalIgnoreCase))
                      ?? details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "failed", StringComparison.OrdinalIgnoreCase))
                      ?? details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "pending", StringComparison.OrdinalIgnoreCase));
        if (current is null)
        {
            return new PrototypeRepairStepExecutionResult(details.Session.SessionId, "", "", "no_pending_repair_step", "当前修复计划没有待执行步骤。", details.Session.CurrentGoalIndex, false, details.Session.Status);
        }

        await _metadataStore.UpdateProjectIterationGoalStatusAsync(current.GoalId, "running", current.ResultSummary, null, cancellationToken);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "running", current.GoalIndex, $"正在执行修复步骤 {current.GoalIndex}。", null, null, cancellationToken);

        var feedback = BuildStepFeedback(project, details, current, request.Feedback);
        var result = await _quickFixService.SubmitAsync(
            project.ProjectId,
            new PrototypeFeedbackRequest(feedback, request.Model, null, null),
            requireSucceededPrototypeRun: false,
            cancellationToken);

        var completed = string.Equals(result.Status, "completed", StringComparison.OrdinalIgnoreCase);
        var goalStatus = completed ? "succeeded" : "needs_fix";
        await _metadataStore.UpdateProjectIterationGoalStatusAsync(
            current.GoalId,
            goalStatus,
            result.AssistantMessage,
            completed ? DateTimeOffset.UtcNow.ToString("O") : null,
            CancellationToken.None);
        if (!string.IsNullOrWhiteSpace(result.RunId))
        {
            await _metadataStore.LinkProjectIterationGoalRunAsync(details.Session.SessionId, current.GoalId, result.RunId, ExecuteRunType, CancellationToken.None);
        }

        var refreshed = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, SourceKind, CancellationToken.None)
            ?? details;
        var hasNeedsFix = refreshed.Goals.Any(goal => string.Equals(goal.Status, "needs_fix", StringComparison.OrdinalIgnoreCase));
        var hasPending = refreshed.Goals.Any(goal => string.Equals(goal.Status, "pending", StringComparison.OrdinalIgnoreCase));
        var sessionStatus = hasNeedsFix ? "needs_fix" : hasPending ? "paused_for_review" : "completed";
        var summary = completed
            ? $"修复步骤 {current.GoalIndex} 已完成。"
            : $"修复步骤 {current.GoalIndex} 仍需继续修复。";
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(refreshed.Session.SessionId, sessionStatus, current.GoalIndex, summary, null, sessionStatus == "completed" ? DateTimeOffset.UtcNow.ToString("O") : null, CancellationToken.None);

        _stateWriter.WriteNeedsFixState(project, 0, new
        {
            route = "execute-repair-step",
            source_kind = SourceKind,
            session_id = refreshed.Session.SessionId,
            run_id = result.RunId,
            goal_id = current.GoalId,
            goal_index = current.GoalIndex,
            status = result.Status,
            goal_status = goalStatus,
            session_status = sessionStatus,
            summary,
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });

        return new PrototypeRepairStepExecutionResult(refreshed.Session.SessionId, current.GoalId, result.RunId, result.Status, summary, current.GoalIndex, true, sessionStatus);
    }

    private async Task<ProjectSnapshot> RequireProjectAsync(string accountId, string projectId, CancellationToken cancellationToken)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        return project;
    }

    private async Task<RunSnapshot?> FindLatestFailedRunAsync(string projectId, CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(projectId, cancellationToken);
        return runs.FirstOrDefault(run =>
            string.Equals(run.Status, "failed", StringComparison.OrdinalIgnoreCase) &&
            (run.RunType.Contains("prototype", StringComparison.OrdinalIgnoreCase) ||
             run.RunType.Contains("needs-fix", StringComparison.OrdinalIgnoreCase)));
    }

    private static string BuildFailureText(RunSnapshot run)
    {
        return string.Join("\n", run.ProgressLabel, run.StderrText, run.StdoutText, run.EvidenceJson)
            .Trim();
    }

    private static string BuildSourceMessage(RunSnapshot run, string failureText)
    {
        return JsonSerializer.Serialize(new
        {
            source_run_id = run.RunId,
            source_run_type = run.RunType,
            source_status = run.Status,
            failure_excerpt = Trim(failureText, 4000)
        });
    }

    private static List<PrototypeRepairGoalResult> BuildRepairGoals(string failureText)
    {
        var text = failureText.ToLowerInvariant();
        var goals = new List<PrototypeRepairGoalResult>();
        void Add(string title, string description, string acceptance)
        {
            if (goals.Any(goal => string.Equals(goal.Title, title, StringComparison.OrdinalIgnoreCase)))
            {
                return;
            }

            goals.Add(new PrototypeRepairGoalResult(goals.Count + 1, title, description, acceptance, "pending"));
        }

        if (text.Contains("no loader found") || text.Contains("non-existent resource") || text.Contains("referenced non-existent resource") || text.Contains("asset"))
        {
            Add("修复素材与资源引用", "把缺失资源复制到项目自己的有效资源目录，并把场景资源引用改为项目内资源。", "场景不再引用缺失资源，Godot 加载时不出现资源不存在或 loader 错误。");
        }

        if (text.Contains("start_button_missing") || text.Contains("main_menu") || text.Contains("prototype_main_menu_navigation_failed"))
        {
            Add("修复主菜单到原型入口", "确保主菜单原型入口能打开当前 prototype shell 场景。", "点击主菜单原型入口后能进入当前原型 shell，而不是停留在模板主菜单。");
        }

        if (text.Contains("start adventure") ||
            text.Contains("rpg_start_button_missing") ||
            (text.Contains("prototype_main_menu_navigation_failed") && text.Contains("dq-rpg")))
        {
            Add("修复原型开始交互", "确保 prototype shell 中存在可见、可点击的开始按钮，并能触发原型流程。", "开始按钮可见可点击，点击后进入核心玩法第一阶段。");
        }

        if (text.Contains("visible") || text.Contains("size") || text.Contains("map_visible") || text.Contains("markers_missing"))
        {
            Add("修复关键场景可见性", "确保点击入口后关键场景、玩家和核心交互节点可见且有有效尺寸。", "验收脚本能看到关键节点，且节点没有被隐藏、遮挡或尺寸为零。");
        }

        if (text.Contains("cs2012") || text.Contains("access to the path") || text.Contains("build") || text.Contains("compile"))
        {
            Add("修复构建和文件锁问题", "清理或规避项目构建输出被占用的问题，避免验证阶段因文件锁失败。", "构建/预热阶段不再因文件占用失败。");
        }

        if (goals.Count == 0)
        {
            Add("修复最近失败项", "根据最近一次失败记录修复最小范围的问题，不扩大到新功能。", "最近一次失败原因被消除，且没有引入新的关键错误。");
        }

        Add("执行最终全量验收", "运行当前类型要求的最终 smoke/导航/可见性验收，确认修复闭环。", "最终验收通过后，原型修复才算完成。");
        return goals;
    }

    private static string BuildStepFeedback(ProjectSnapshot project, ProjectIterationSessionDetails details, ProjectIterationGoalSnapshot goal, string? feedback)
    {
        return $"""
            Run the execute-repair-step top-level route.

            Repair plan:
            - SessionId: {details.Session.SessionId}
            - SourceKind: {SourceKind}
            - CurrentStep: {goal.GoalIndex}
            - Title: {goal.Title}
            - Description: {goal.Description}
            - AcceptanceHint: {goal.AcceptanceHint}

            Mandatory rules:
            - Execute only the current repair step.
            - Do not regenerate the prototype, iteration plan, or repair plan.
            - Do not repair PhaseA platform code, docs, scripts, deployment, or route code.
            - Change only hosted game project files needed for this repair step.
            - Keep output browser-safe: no paths, command lines, script names, logs, or environment values.

            Project:
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}

            {PrototypeRouteSkillPolicy.BuildPromptBlock(project)}

            Extra user feedback:
            {feedback}
            """;
    }

    private static string Trim(string value, int maxLength)
    {
        return value.Length <= maxLength ? value : value[..maxLength];
    }
}

public sealed record PrototypeRepairPlanResult(
    string SessionId,
    string Status,
    string Summary,
    IReadOnlyList<PrototypeRepairGoalResult> Goals)
{
    public static PrototypeRepairPlanResult FromDetails(ProjectIterationSessionDetails details, string summary)
    {
        return new PrototypeRepairPlanResult(
            details.Session.SessionId,
            details.Session.Status,
            summary,
            details.Goals.Select(goal => new PrototypeRepairGoalResult(
                goal.GoalIndex,
                goal.Title,
                goal.Description,
                goal.AcceptanceHint ?? "",
                goal.Status,
                goal.ResultSummary)).ToArray());
    }
}

public sealed record PrototypeRepairGoalResult(
    int GoalIndex,
    string Title,
    string Description,
    string AcceptanceHint,
    string Status,
    string? ResultSummary = null);

public sealed record PrototypeRepairStepExecutionRequest(string? Model = null, string? Feedback = null);

public sealed record PrototypeRepairStepExecutionResult(
    string SessionId,
    string GoalId,
    string RunId,
    string Status,
    string Summary,
    int GoalIndex,
    bool HasMoreWork,
    string SessionStatus);
