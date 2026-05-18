using System.Text.RegularExpressions;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeIterationPlanService
{
    private static readonly Regex SplitRegex = new(@"[。！？!?]\s*|\r?\n+", RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private static readonly string[] InternalSuggestionKeywords =
    [
        "Day 4",
        "Day 5",
        "Step 04",
        "Step 05",
        "dotnet test",
        "dotnet build",
        "build-server",
        "obj/tmp",
        "文件锁",
        "写权限",
        "环境清理",
        "重跑",
        "工作区",
        "GdUnit",
        "Godot/GdUnit"
    ];
    private readonly PhaseAMetadataStore _metadataStore;

    public PrototypeIterationPlanService(PhaseAMetadataStore metadataStore)
    {
        _metadataStore = metadataStore;
    }

    public async Task<PrototypeIterationPlanResult> CreateAsync(
        string accountId,
        string projectId,
        PrototypeIterationPlanRequest request,
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

        var message = request.Message?.Trim();
        if (string.IsNullOrWhiteSpace(message))
        {
            return new PrototypeIterationPlanResult("", "missing_message", "请输入要拆解的优化目标。", []);
        }

        var sourceKind = string.IsNullOrWhiteSpace(request.SourceKind) ? "manual_feedback" : request.SourceKind.Trim();
        if (string.Equals(sourceKind, "completion_suggestion", StringComparison.OrdinalIgnoreCase) &&
            IsInternalExecutionSuggestion(message))
        {
            return new PrototypeIterationPlanResult(
                "",
                "suggestion_needs_fix",
                "当前这条建议更像内部执行或环境修复信息，不适合直接拆成迭代目标。请先处理需修复项，或重新生成更明确的产品向优化建议。",
                []);
        }
        var goals = BuildGoals(message);
        var overallGoal = BuildOverallGoal(project.GameName, message);
        var created = await _metadataStore.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            sourceKind,
            message,
            overallGoal,
            goals.Select(goal => new ProjectIterationGoalCreateCommand(
                goal.GoalIndex,
                goal.Title,
                goal.Description,
                goal.AcceptanceHint)).ToArray(),
            cancellationToken);

        var summary = $"已生成 {goals.Count} 个迭代目标。请先执行目标 1，再逐步推进后续目标。";
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(created.SessionId, "ready", 0, summary, null, cancellationToken);
        return new PrototypeIterationPlanResult(created.SessionId, "ready", summary, goals);
    }

    public async Task<ProjectIterationSessionDetails?> GetLatestAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        return await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
    }

    public async Task<PrototypeIterationPlanEvaluationResult> EvaluateAsync(
        string accountId,
        string projectId,
        PrototypeWorkflowProgress? prototypeProgress,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
        if (details is null)
        {
            return new PrototypeIterationPlanEvaluationResult(
                "should_refine_plan",
                "当前项目还没有迭代计划。",
                "还没有可执行的目标列表，无法判断是否适合直接进入下一目标。",
                "请先生成迭代计划。",
                null);
        }

        var goals = details.Goals.OrderBy(goal => goal.GoalIndex).ToArray();
        if (goals.Length == 0)
        {
            return new PrototypeIterationPlanEvaluationResult(
                "should_refine_plan",
                "当前计划没有有效目标。",
                "计划会话存在，但没有生成任何可执行目标。",
                "请重新生成迭代计划。",
                BuildRegenerationPrompt(prototypeProgress, details));
        }

        if (goals.Any(goal => string.Equals(goal.Status, "needs_fix", StringComparison.Ordinal)))
        {
            return new PrototypeIterationPlanEvaluationResult(
                "blocked_by_current_goal",
                "当前计划里有需要先修复的目标。",
                "至少一个目标已经被标记为 needs_fix，继续执行后续目标只会放大不确定性。",
                "先修复当前目标，再决定是否继续后续目标。",
                null);
        }

        if (goals.Any(goal => string.Equals(goal.Status, "running", StringComparison.Ordinal)))
        {
            return new PrototypeIterationPlanEvaluationResult(
                "blocked_by_current_goal",
                "当前计划里有进行中的目标。",
                "已有目标正在执行，暂时不适合重新拆解或继续触发下一目标。",
                "等待当前目标完成后再刷新判断。",
                null);
        }

        var pendingGoals = goals.Where(goal => string.Equals(goal.Status, "pending", StringComparison.Ordinal)).ToArray();
        if (pendingGoals.Length == 0)
        {
            return new PrototypeIterationPlanEvaluationResult(
                "ready_to_execute",
                "当前计划已经没有待执行目标。",
                "所有目标都已完成或已停止，不需要继续执行下一目标。",
                "如果还有新需求，请基于新的优化目标重新生成计划。",
                null);
        }

        var firstPending = pendingGoals[0];
        var firstGoalLooksTooLarge = LooksTooBroad(firstPending.Title) || LooksTooBroad(firstPending.Description);
        var overallLooksLarge = goals.Length <= 3 && goals.Any(goal => LooksTooBroad(goal.Description));
        var recommendedButStillBroad = string.Equals(prototypeProgress?.NextStepEvaluation, "recommended", StringComparison.OrdinalIgnoreCase)
                                       && goals.Length <= 3
                                       && firstGoalLooksTooLarge;

        if (firstGoalLooksTooLarge || overallLooksLarge || recommendedButStillBroad)
        {
            return new PrototypeIterationPlanEvaluationResult(
                "should_refine_plan",
                "当前计划可以用，但第一目标仍然偏大，直接执行风险较高。",
                $"当前第一个待执行目标“{firstPending.Title}”混合了多个连续实现点，更像总任务而不是单次小目标。",
                "建议先重生成一次更细的迭代计划，再执行下一目标。",
                BuildRegenerationPrompt(prototypeProgress, details));
        }

        return new PrototypeIterationPlanEvaluationResult(
            "ready_to_execute",
            "当前计划适合直接执行下一目标。",
            $"当前待执行目标“{firstPending.Title}”边界相对清楚，没有发现明显的 needs_fix 或过粗拆分信号。",
            "可以直接点击“执行下一目标”。",
            null);
    }

    private static List<PrototypeIterationPlanGoalResult> BuildGoals(string message)
    {
        var normalized = message.Replace("\r", "\n");
        var segments = SplitRegex
            .Split(normalized)
            .Select(value => value.Trim())
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Distinct(StringComparer.Ordinal)
            .ToList();

        if (segments.Count == 0)
        {
            segments.Add(message.Trim());
        }

        var goals = new List<PrototypeIterationPlanGoalResult>();
        var index = 1;
        foreach (var segment in segments)
        {
            if (goals.Count >= 7)
            {
                break;
            }

            goals.Add(new PrototypeIterationPlanGoalResult(
                index,
                BuildGoalTitle(index, segment),
                segment,
                $"完成后应能明确判断“{TrimForHint(segment)}”是否已落地。",
                "pending"));
            index++;
        }

        while (goals.Count < 3)
        {
            var title = goals.Count switch
            {
                0 => "梳理当前缺口",
                1 => "完成最小闭环",
                _ => "补齐关键说明与验证"
            };
            var description = goals.Count switch
            {
                0 => "先定位当前原型里最阻塞玩家体验的一个核心问题，并整理出最小改动方向。",
                1 => "围绕最小可玩闭环完成一次明确的代码与场景推进。",
                _ => "补齐提示、说明或验证点，确保用户能判断本轮是否值得继续。"
            };
            goals.Add(new PrototypeIterationPlanGoalResult(
                goals.Count + 1,
                title,
                description,
                $"完成后应能人工确认“{title}”已达成。",
                "pending"));
        }

        return goals;
    }

    private static string BuildOverallGoal(string gameName, string message)
    {
        var prefix = string.IsNullOrWhiteSpace(gameName) ? "当前项目" : gameName.Trim();
        return $"{prefix}：{TrimForHint(message, 120)}";
    }

    private static bool IsInternalExecutionSuggestion(string message)
    {
        return InternalSuggestionKeywords.Any(keyword => message.Contains(keyword, StringComparison.OrdinalIgnoreCase));
    }

    private static string BuildGoalTitle(int index, string segment)
    {
        return $"目标 {index}：{TrimForHint(segment, 24)}";
    }

    private static string TrimForHint(string value, int maxLength = 32)
    {
        var trimmed = value.Trim();
        return trimmed.Length <= maxLength ? trimmed : $"{trimmed[..maxLength]}...";
    }

    private static string BuildRegenerationPrompt(PrototypeWorkflowProgress? prototypeProgress, ProjectIterationSessionDetails details)
    {
        var sourceMessage = details.Session.SourceMessage?.Trim();
        if (!string.IsNullOrWhiteSpace(sourceMessage))
        {
            return $"请把这条原型优化建议重拆成 4 个更小、能单独执行的目标，不要把多个连续实现点塞进同一个目标里：{sourceMessage}";
        }

        if (!string.IsNullOrWhiteSpace(prototypeProgress?.CompletionSummary))
        {
            return "请根据当前 prototype completion report，把下一步优化拆成 4 个更小的目标：先补地图稳定移动和可见遇敌触发，再补完成一场战斗并正常结算，再补胜利后奖励 3 选 1 并返回地图，最后补胜负条件提示与验证。";
        }

        return "请把当前优化目标重拆成 4 个更小的连续目标，每个目标都要足够小，适合一次单独执行。";
    }

    private static bool LooksTooBroad(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var text = value.Trim();
        var separators = new[] { "，", "、", "并", "然后", "同时", "再", "后", " and ", "," };
        var separatorHits = separators.Count(text.Contains);
        return text.Length >= 36 || separatorHits >= 2;
    }
}
