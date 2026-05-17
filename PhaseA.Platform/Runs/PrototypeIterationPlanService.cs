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
}
