using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;

namespace PhaseA.Platform.Runs;

public sealed class GddMilestoneStepService
{
    private const string GddRelativePath = "docs/gdd/GDD.md";
    private const string StateRelativePath = "routes/gdd-milestones/latest.json";
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true
    };

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PrototypeIterationGoalService _iterationGoalService;
    private readonly PrototypeNeedsFixRouteService _needsFixRouteService;
    private readonly ILlmRouteEngine? _llmRouteEngine;

    public GddMilestoneStepService(
        PhaseAMetadataStore metadataStore,
        PrototypeIterationGoalService iterationGoalService,
        PrototypeNeedsFixRouteService needsFixRouteService,
        ILlmRouteEngine? llmRouteEngine = null)
    {
        _metadataStore = metadataStore;
        _iterationGoalService = iterationGoalService;
        _needsFixRouteService = needsFixRouteService;
        _llmRouteEngine = llmRouteEngine;
    }

    public async Task<GddMilestoneStepPlanResult?> GetOrCreateLatestAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        var state = await ReadStateAsync(project, cancellationToken) ??
                    await CreateStateFromGddAsync(project, cancellationToken);
        if (state is null)
        {
            return new GddMilestoneStepPlanResult(
                project.ProjectId,
                "gdd_not_found",
                "请先创建策划大纲，再生成游戏模块 step。",
                [],
                FailureCode: "gdd_not_found");
        }

        NormalizeState(state);
        await WriteStateAsync(project, state, cancellationToken);
        return ToResult(project.ProjectId, state);
    }

    public async Task<GddMilestoneStepActionResult?> ConfirmAsync(
        string accountId,
        string projectId,
        string stepId,
        GddMilestoneStepConfirmRequest request,
        CancellationToken cancellationToken = default)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        var state = await ReadStateAsync(project, cancellationToken) ??
                    await CreateStateFromGddAsync(project, cancellationToken);
        if (state is null)
        {
            return new GddMilestoneStepActionResult(project.ProjectId, stepId, "gdd_not_found", "请先创建策划大纲。", FailureCode: "gdd_not_found");
        }

        NormalizeState(state);
        var index = state.Steps.FindIndex(step => string.Equals(step.StepId, stepId, StringComparison.OrdinalIgnoreCase));
        if (index < 0)
        {
            return new GddMilestoneStepActionResult(project.ProjectId, stepId, "step_not_found", "没有找到这个 step。", ToResult(project.ProjectId, state), FailureCode: "step_not_found");
        }

        var step = state.Steps[index];
        if (step.Locked)
        {
            return new GddMilestoneStepActionResult(project.ProjectId, step.StepId, "step_locked", "当前 step 尚未解锁。", ToResult(project.ProjectId, state), FailureCode: "step_locked");
        }

        if (step.Status is not ("executed" or "feedback_submitted"))
        {
            return new GddMilestoneStepActionResult(project.ProjectId, step.StepId, "step_not_ready_to_confirm", "请先执行当前 Step，或完成当前 Step 的反馈修复后再确认完成。", ToResult(project.ProjectId, state), FailureCode: "step_not_ready_to_confirm");
        }

        var now = DateTimeOffset.UtcNow.ToString("O");
        state.Steps[index] = step with
        {
            Status = "confirmed",
            ConfirmedUtc = now,
            ConfirmationNotes = request.Notes?.Trim()
        };

        if (index + 1 < state.Steps.Count)
        {
            var next = state.Steps[index + 1];
            var review = await ReviewNextStepAsync(project, state.Steps[index], next, request.Model, cancellationToken);
            state.Steps[index + 1] = next with
            {
                Locked = false,
                Status = string.Equals(next.Status, "locked", StringComparison.OrdinalIgnoreCase) ? "ready" : next.Status,
                Title = review.Title ?? next.Title,
                Description = review.Description ?? next.Description,
                Acceptance = review.Acceptance ?? next.Acceptance,
                ScopeIn = review.ScopeIn ?? next.ScopeIn,
                ScopeOut = review.ScopeOut ?? next.ScopeOut,
                GodotSlice = review.GodotSlice ?? next.GodotSlice,
                PackagingValidation = review.PackagingValidation ?? next.PackagingValidation,
                FeedbackGuidance = review.FeedbackGuidance ?? next.FeedbackGuidance,
                NextStepReview = review.NextStepReview ?? next.NextStepReview,
                ReviewSummary = review.Summary
            };
            state.CurrentStepId = state.Steps[index + 1].StepId;
            state.Summary = $"已确认 {step.StepId}，并完成下一 step 解锁前检查。";
        }
        else
        {
            state.CurrentStepId = null;
            state.Status = "completed";
            state.Summary = "所有游戏模块 step 已确认完成，可以创建新一轮游戏模块。";
        }

        await WriteStateAsync(project, state, cancellationToken);
        return new GddMilestoneStepActionResult(project.ProjectId, step.StepId, "confirmed", state.Summary, ToResult(project.ProjectId, state));
    }

    public async Task<GddMilestoneStepActionResult?> SubmitFeedbackAsync(
        string accountId,
        string projectId,
        string stepId,
        GddMilestoneStepFeedbackRequest request,
        CancellationToken cancellationToken = default)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        var state = await ReadStateAsync(project, cancellationToken) ??
                    await CreateStateFromGddAsync(project, cancellationToken);
        if (state is null)
        {
            return new GddMilestoneStepActionResult(project.ProjectId, stepId, "gdd_not_found", "请先创建策划大纲。", FailureCode: "gdd_not_found");
        }

        NormalizeState(state);
        var index = state.Steps.FindIndex(step => string.Equals(step.StepId, stepId, StringComparison.OrdinalIgnoreCase));
        if (index < 0)
        {
            return new GddMilestoneStepActionResult(project.ProjectId, stepId, "step_not_found", "没有找到这个 step。", ToResult(project.ProjectId, state), FailureCode: "step_not_found");
        }

        var step = state.Steps[index];
        if (step.Locked)
        {
            return new GddMilestoneStepActionResult(project.ProjectId, step.StepId, "step_locked", "当前 step 尚未解锁。", ToResult(project.ProjectId, state), FailureCode: "step_locked");
        }

        var feedback = request.Feedback?.Trim();
        if (string.IsNullOrWhiteSpace(feedback))
        {
            return new GddMilestoneStepActionResult(project.ProjectId, step.StepId, "missing_feedback", "请输入这个 step 的反馈。", ToResult(project.ProjectId, state), FailureCode: "missing_feedback");
        }

        var session = await CreateStepSessionAsync(project, state, step, index, cancellationToken);
        var goal = session.Goals.FirstOrDefault();
        if (goal is null)
        {
            return new GddMilestoneStepActionResult(project.ProjectId, step.StepId, "step_session_invalid", "当前 Step 执行会话缺少目标，请重新执行当前 Step。", ToResult(project.ProjectId, state), FailureCode: "step_session_invalid");
        }

        await _metadataStore.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "needs_fix", feedback, null, cancellationToken);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(session.Session.SessionId, "needs_fix", goal.GoalIndex, feedback, session.Session.LatestEvaluationJson, null, cancellationToken);

        var scopedFeedback = $"""
            Game module step feedback.

            Current step: {step.StepId} - {step.Title}
            Step goal: {step.Description}
            Scope in: {step.ScopeIn}
            Scope out: {step.ScopeOut}
            Godot slice: {step.GodotSlice}
            Step acceptance: {step.Acceptance}
            Package validation: {step.PackagingValidation}

            Player feedback:
            {feedback}
            """;
        var result = await _needsFixRouteService.RunAsync(
            accountId,
            projectId,
            new PrototypeNeedsFixRouteRequest(scopedFeedback, request.Model, null, goal.GoalId, goal.GoalIndex),
            cancellationToken);

        var completed = result.Status is "completed" or "succeeded";
        var needsFix = string.Equals(result.Status, "needs_fix", StringComparison.OrdinalIgnoreCase);
        state.Steps[index] = step with
        {
            Status = completed ? "feedback_submitted" : needsFix ? "needs_fix" : "feedback_failed",
            IterationSessionId = session.Session.SessionId,
            FeedbackSummary = feedback,
            FeedbackRunId = string.IsNullOrWhiteSpace(result.RunId) ? step.FeedbackRunId : result.RunId
        };
        state.Summary = completed
            ? $"{step.StepId} 的反馈修复已完成。请打包下载试玩验证；确认通过后点击完成当前 Step。"
            : $"{step.StepId} 的反馈修复未完成：{result.Status}";
        await WriteStateAsync(project, state, CancellationToken.None);

        return new GddMilestoneStepActionResult(project.ProjectId, step.StepId, result.Status, state.Summary, ToResult(project.ProjectId, state), NeedsFixRun: result);
    }

    public Task<GddMilestoneStepActionResult?> CreateIterationPlanForCurrentStepAsync(
        string accountId,
        string projectId,
        string? model = null,
        CancellationToken cancellationToken = default)
    {
        return ExecuteCurrentStepAsync(accountId, projectId, cancellationToken);
    }

    public async Task<GddMilestoneStepActionResult?> ExecuteCurrentStepAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        var state = await ReadStateAsync(project, cancellationToken) ??
                    await CreateStateFromGddAsync(project, cancellationToken);
        if (state is null)
        {
            return new GddMilestoneStepActionResult(project.ProjectId, "", "gdd_not_found", "请先创建策划大纲。", FailureCode: "gdd_not_found");
        }

        NormalizeState(state);
        var step = ResolveCurrentStep(state);
        if (step is null)
        {
            return new GddMilestoneStepActionResult(project.ProjectId, "", "completed", "所有 step 已完成，可以创建新一轮游戏模块。", ToResult(project.ProjectId, state));
        }

        if (step.Locked)
        {
            return new GddMilestoneStepActionResult(project.ProjectId, step.StepId, "step_locked", "当前 step 尚未解锁。", ToResult(project.ProjectId, state), FailureCode: "step_locked");
        }

        var index = state.Steps.FindIndex(item => string.Equals(item.StepId, step.StepId, StringComparison.OrdinalIgnoreCase));
        if (index < 0)
        {
            return new GddMilestoneStepActionResult(project.ProjectId, step.StepId, "step_not_found", "没有找到当前 Step。", ToResult(project.ProjectId, state), FailureCode: "step_not_found");
        }

        var session = await CreateStepSessionAsync(project, state, step, index, cancellationToken);
        await WriteStateAsync(project, state, CancellationToken.None);

        var execution = await _iterationGoalService.ExecuteNextAsync(accountId, project.ProjectId, cancellationToken);
        var succeeded = (execution.Status is "completed" or "succeeded") && string.Equals(execution.SessionStatus, "completed", StringComparison.OrdinalIgnoreCase);
        var needsFix = execution.Status is "needs_fix" or "failed" or "project_busy" or "prototype_required";
        if (index >= 0)
        {
            state.Steps[index] = state.Steps[index] with
            {
                Status = succeeded ? "executed" : needsFix ? "needs_fix" : "execution_failed",
                IterationSessionId = string.IsNullOrWhiteSpace(execution.SessionId) ? session.Session.SessionId : execution.SessionId,
                ExecutionRunId = string.IsNullOrWhiteSpace(execution.RunId) ? state.Steps[index].ExecutionRunId : execution.RunId,
                ExecutionSummary = execution.Summary
            };
            state.Summary = succeeded
                ? $"{step.StepId} 已执行完成。请打包下载试玩验证；如果有问题，提交当前 Step 反馈。"
                : $"{step.StepId} 执行未完成：{execution.Summary}";
            await WriteStateAsync(project, state, CancellationToken.None);
        }

        return new GddMilestoneStepActionResult(project.ProjectId, step.StepId, execution.Status, state.Summary, ToResult(project.ProjectId, state), StepExecution: execution);
    }

    private async Task<ProjectIterationSessionDetails> CreateStepSessionAsync(
        ProjectSnapshot project,
        GddMilestoneState state,
        GddMilestoneStepState step,
        int stepIndex,
        CancellationToken cancellationToken)
    {
        var created = await _metadataStore.CreateProjectIterationSessionAsync(
            project.AccountId,
            project.ProjectId,
            "gdd_milestone_step",
            BuildStepSourceMessage(step),
            $"{step.StepId} - {step.Title}",
            [
                new ProjectIterationGoalCreateCommand(
                    step.StepIndex <= 0 ? stepIndex + 1 : step.StepIndex,
                    step.Title,
                    BuildStepGoalDescription(step),
                    BuildStepAcceptanceHint(step))
            ],
            cancellationToken);

        state.Steps[stepIndex] = step with
        {
            IterationSessionId = created.SessionId
        };

        return await _metadataStore.GetProjectIterationSessionAsync(project.ProjectId, created.SessionId, cancellationToken)
               ?? throw new InvalidOperationException("Created GDD milestone step session could not be loaded.");
    }

    private static string BuildStepSourceMessage(GddMilestoneStepState step)
    {
        return $"""
            GDD milestone step execution.

            Step: {step.StepId} - {step.Title}
            Description:
            {step.Description}

            Scope In:
            {step.ScopeIn}

            Scope Out:
            {step.ScopeOut}

            Godot/C# Slice:
            {step.GodotSlice}

            Acceptance:
            {step.Acceptance}

            Package / Player Validation:
            {step.PackagingValidation}

            Feedback Improvement Run:
            {step.FeedbackGuidance}

            Next Step Adjustment Check:
            {step.NextStepReview}

            Implement only this current milestone step. Do not split it into multiple player-visible tasks and do not advance later locked steps.
            """;
    }

    private static string BuildStepGoalDescription(GddMilestoneStepState step)
    {
        return $"""
            Implement {step.StepId} as one diablolike-style playable milestone.

            Goal:
            {step.Description}

            Scope in:
            {step.ScopeIn}

            Scope out:
            {step.ScopeOut}

            Runtime slice:
            {step.GodotSlice}
            """;
    }

    private static string BuildStepAcceptanceHint(GddMilestoneStepState step)
    {
        return $"""
            Acceptance:
            {step.Acceptance}

            Player package validation:
            {step.PackagingValidation}

            After implementation, the browser should prompt the player to package, download, and validate this Step before confirming completion.
            """;
    }

    private async Task<ProjectSnapshot?> GetProjectAsync(string accountId, string projectId, CancellationToken cancellationToken)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        return project is not null && string.Equals(project.AccountId, accountId, StringComparison.Ordinal) ? project : null;
    }

    private static async Task<GddMilestoneState?> CreateStateFromGddAsync(ProjectSnapshot project, CancellationToken cancellationToken)
    {
        var gddPath = Path.Combine(project.RepoPath, GddRelativePath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(gddPath))
        {
            return null;
        }

        var gddText = await File.ReadAllTextAsync(gddPath, Encoding.UTF8, cancellationToken);
        var steps = ExtractSteps(gddText);
        if (steps.Count == 0)
        {
            steps = BuildDefaultSteps(gddText);
        }

        if (steps.Count == 0)
        {
            steps.Add(CreateStepState(
                "M1",
                1,
                "M1：首个可玩闭环",
                "根据当前 GDD 创建第一个可打包、可验证的最小可玩闭环。",
                "ready",
                false));
        }

        for (var index = 0; index < steps.Count; index++)
        {
            steps[index] = steps[index] with
            {
                StepIndex = index + 1,
                Locked = index != 0,
                Status = index == 0 ? "ready" : "locked"
            };
        }

        var state = new GddMilestoneState(
            "phase-a.gdd-milestone-steps.v2",
            "ready",
            "已根据当前策划大纲生成游戏模块步骤规格。",
            steps[0].StepId,
            steps);
        NormalizeState(state);
        return state;
    }

    private static List<GddMilestoneStepState> ExtractSteps(string gddText)
    {
        var result = new List<GddMilestoneStepState>();
        var matches = Regex.Matches(
            gddText,
            @"(?im)^\s*(?:[-*]\s*)?(M\d+(?:[-.]\d+)?)\s*[:：\-]\s*(.+)$");
        foreach (Match match in matches)
        {
            var id = NormalizeStepId(match.Groups[1].Value);
            var titleBody = Compact(match.Groups[2].Value);
            if (string.IsNullOrWhiteSpace(titleBody))
            {
                continue;
            }

            result.Add(CreateStepState(
                id,
                result.Count + 1,
                $"{id}：{Trim(titleBody, 80)}",
                Trim(titleBody, 420),
                "locked",
                true));
        }

        return result
            .GroupBy(step => step.StepId, StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .Take(20)
            .ToList();
    }

    private static List<GddMilestoneStepState> BuildDefaultSteps(string gddText)
    {
        var text = Compact(gddText);
        var hasControls = ContainsAny(text, "键盘", "鼠标", "WASD", "Controls", "Input");
        var hasScene = ContainsAny(text, "场景", "关卡", "地图", "地城", "Scene", "Room", "Level");
        var hasProgression = ContainsAny(text, "升级", "成长", "奖励", "Progression", "Upgrade", "Reward");
        var hasPolish = ContainsAny(text, "素材", "动画", "音效", "VFX", "Asset", "Animation", "Polish");

        var steps = new List<GddMilestoneStepState>
        {
            BuildDefaultStep("M1", 1, "首个可玩场景与基础操作", hasScene || hasControls
                ? "创建首个可玩场景，接入 GDD 要求的键盘鼠标基础操作和可见反馈。"
                : "创建首个可玩场景，并提供基础操作入口和可见反馈。"),
            BuildDefaultStep("M2", 2, "核心玩法闭环", "实现 GDD 中最小核心玩法循环，让玩家能完成一次明确的开始、操作、反馈、结果闭环。")
        };

        if (hasProgression)
        {
            steps.Add(BuildDefaultStep("M3", 3, "奖励与成长反馈", "实现奖励、升级、永久成长或其他 GDD 指定的进度反馈。"));
        }

        if (hasPolish)
        {
            steps.Add(BuildDefaultStep($"M{steps.Count + 1}", steps.Count + 1, "素材替换与表现验证", "替换关键占位素材，并验证碰撞、场景加载、基础交互和运行 smoke。"));
        }

        steps.Add(BuildDefaultStep($"M{steps.Count + 1}", steps.Count + 1, "原型可玩性验证与打包", "补齐首轮可玩验证、打包下载提示和下一轮模块创建准备。"));
        return steps;
    }

    private static GddMilestoneStepState BuildDefaultStep(string id, int index, string title, string description)
    {
        return CreateStepState(id, index, $"{id}：{title}", description, "locked", true);
    }

    private static GddMilestoneStepState CreateStepState(
        string id,
        int index,
        string title,
        string description,
        string status,
        bool locked)
    {
        var spec = BuildStepSpec(id, title, description);
        return new GddMilestoneStepState(
            id,
            index,
            title,
            description,
            spec.Acceptance,
            spec.ScopeIn,
            spec.ScopeOut,
            spec.GodotSlice,
            spec.PackagingValidation,
            spec.FeedbackGuidance,
            spec.NextStepReview,
            status,
            locked);
    }

    private static GddMilestoneStepSpec BuildStepSpec(string id, string title, string description)
    {
        var body = Trim(description, 420);
        var lower = $"{title} {description}";
        var isAssetStep = ContainsAny(lower, "素材", "资产", "Asset", "KayKit", "碰撞", "collision", "Animation", "动画");
        var isUiStep = ContainsAny(lower, "UI", "HUD", "界面", "反馈", "screen", "本地化", "accessibility");
        var isFinalStep = ContainsAny(lower, "验收", "打包", "readiness", "polish", "final", "summary");

        var scopeIn = $"只实现 {id} 当前 step 所需的可玩功能：{body} 保持 scene path、screen id、input action、state name 稳定，并把玩家可见文本放到集中配置或本地化入口。";
        var scopeOut = "不提前实现后续锁定 step；不做最终视觉精装修；不引入 GDD 之外的新核心系统；不因为当前 step 未完成而跳到下一 step。";
        var godotSlice = "在 Godot 4.5.1 + C# 项目中完成可运行切片，优先覆盖场景、组件、输入、HUD/状态反馈和最小测试或 smoke 验证。";
        var acceptance = $"完成并验证：{body} 玩家能通过打包版本直接试玩当前 step，看到明确开始、操作、反馈和结果。";
        var packaging = "当前 step 完成后提示玩家打包下载并试玩验证；确认按钮只在当前 Step 执行完成或反馈修复完成后可用。";

        if (isAssetStep)
        {
            scopeIn += " 素材替换必须同时验证阻挡、碰撞、导航/移动边界、动画或朝向状态，以及场景加载 smoke。";
            godotSlice += " 对替换后的角色、敌人、道具或阻挡物补充碰撞层、碰撞形状和最小运行检查。";
            acceptance += " 替换素材不能让玩家穿模、卡死、无法命中或无法完成当前房间目标。";
        }

        if (isUiStep)
        {
            scopeIn += " UI 可用 placeholder，但 HUD 信息优先级、输入提示、冷却/生命/目标状态和文本来源必须稳定。";
            godotSlice += " UI screen contract 至少记录 screen id、scene path、关键状态和输入动作。";
            acceptance += " HUD 不遮挡核心战斗读图，关键状态不能只依赖颜色表达。";
        }

        if (isFinalStep)
        {
            acceptance += " 最后一轮还要覆盖核心循环回归、项目包生成、下载验证和下一轮游戏模块创建准备。";
        }

        return new GddMilestoneStepSpec(
            scopeIn,
            scopeOut,
            godotSlice,
            acceptance,
            packaging,
            "如果玩家反馈当前 step 未达预期，提交当前 Step 反馈并进入 needs-fix 修复，只修改当前已解锁 step 的问题，不自动推进后续 step。",
            "玩家确认当前 step 后，解锁下一 step 前执行一次检查；只有完成结果或反馈显示必要时，才微调下一 step 的标题、范围或验收。");
    }

    private static GddMilestoneStepState? ResolveCurrentStep(GddMilestoneState state)
    {
        if (!string.IsNullOrWhiteSpace(state.CurrentStepId))
        {
            var current = state.Steps.FirstOrDefault(step => string.Equals(step.StepId, state.CurrentStepId, StringComparison.OrdinalIgnoreCase));
            if (current is not null)
            {
                return current;
            }
        }

        return state.Steps.FirstOrDefault(step => !step.Locked && !string.Equals(step.Status, "confirmed", StringComparison.OrdinalIgnoreCase));
    }

    private static string BuildNextStepReviewSummary(GddMilestoneStepState completed, GddMilestoneStepState next)
    {
        return $"解锁前检查：{completed.StepId} 已由玩家确认。{next.StepId} 暂按原策划 step 继续；如玩家反馈显示方向变化，请先提交当前 Step 反馈修复后再执行。";
    }

    private async Task<GddMilestoneNextStepReview> ReviewNextStepAsync(
        ProjectSnapshot project,
        GddMilestoneStepState completed,
        GddMilestoneStepState next,
        string? model,
        CancellationToken cancellationToken)
    {
        var fallback = new GddMilestoneNextStepReview(
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            null,
            BuildNextStepReviewSummary(completed, next));
        if (_llmRouteEngine is null)
        {
            return fallback with
            {
                Summary = fallback.Summary
            };
        }

        var gddPath = Path.Combine(project.RepoPath, GddRelativePath.Replace('/', Path.DirectorySeparatorChar));
        var gddText = File.Exists(gddPath)
            ? await File.ReadAllTextAsync(gddPath, Encoding.UTF8, cancellationToken)
            : "";
        var prompt = $$"""
            Review whether the next game module step should be adjusted before it is unlocked.

            Return exactly one JSON object:
            {
              "shouldAdjust": true or false,
              "title": "optional revised next step title",
              "description": "optional revised next step description",
              "acceptance": "optional revised next step acceptance",
              "scopeIn": "optional revised scope in",
              "scopeOut": "optional revised scope out",
              "godotSlice": "optional revised Godot/C# slice",
              "packagingValidation": "optional revised package validation",
              "feedbackGuidance": "optional revised feedback guidance",
              "nextStepReview": "optional revised next-step adjustment check",
              "summary": "short Chinese review summary"
            }

            Rules:
            - Adjust only when the completed step notes or feedback imply the next step should change.
            - Preserve the next step id and milestone order.
            - Do not add new locked steps in this review.
            - Keep title, description, acceptance concise and player-verifiable.

            Completed step:
            - Id: {{completed.StepId}}
            - Title: {{completed.Title}}
            - Description: {{completed.Description}}
            - Scope in: {{completed.ScopeIn}}
            - Scope out: {{completed.ScopeOut}}
            - Godot slice: {{completed.GodotSlice}}
            - Acceptance: {{completed.Acceptance}}
            - Package validation: {{completed.PackagingValidation}}
            - Confirmation notes: {{completed.ConfirmationNotes}}
            - Feedback summary: {{completed.FeedbackSummary}}

            Next step before review:
            - Id: {{next.StepId}}
            - Title: {{next.Title}}
            - Description: {{next.Description}}
            - Scope in: {{next.ScopeIn}}
            - Scope out: {{next.ScopeOut}}
            - Godot slice: {{next.GodotSlice}}
            - Acceptance: {{next.Acceptance}}
            - Package validation: {{next.PackagingValidation}}

            Planning outline excerpt:
            {{Trim(gddText, 4000)}}
            """;
        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                project.RepoPath,
                "gdd-next-step-review",
                string.IsNullOrWhiteSpace(model) ? "gpt-5.5" : model.Trim(),
                prompt,
                RequireJsonObject: true),
            cancellationToken);
        if (!completion.Succeeded || string.IsNullOrWhiteSpace(completion.JsonObjectText))
        {
            return fallback with
            {
                Summary = fallback.Summary + " 本次未获得额外调整建议，按原策划继续。"
            };
        }

        try
        {
            using var document = JsonDocument.Parse(completion.JsonObjectText);
            var root = document.RootElement;
            var shouldAdjust = root.TryGetProperty("shouldAdjust", out var adjustElement) &&
                               adjustElement.ValueKind is JsonValueKind.True or JsonValueKind.False &&
                               adjustElement.GetBoolean();
            var summary = FirstNonEmpty(ReadString(root, "summary"), fallback.Summary);
            if (!shouldAdjust)
            {
                return fallback with
                {
                    Summary = summary
                };
            }

            return new GddMilestoneNextStepReview(
                NonEmptyOrNull(ReadString(root, "title")),
                NonEmptyOrNull(ReadString(root, "description")),
                NonEmptyOrNull(ReadString(root, "acceptance")),
                NonEmptyOrNull(ReadString(root, "scopeIn")),
                NonEmptyOrNull(ReadString(root, "scopeOut")),
                NonEmptyOrNull(ReadString(root, "godotSlice")),
                NonEmptyOrNull(ReadString(root, "packagingValidation")),
                NonEmptyOrNull(ReadString(root, "feedbackGuidance")),
                NonEmptyOrNull(ReadString(root, "nextStepReview")),
                summary);
        }
        catch (JsonException)
        {
            return fallback with
            {
                Summary = fallback.Summary + " 本次调整建议无法解析，按原策划继续。"
            };
        }
    }

    private static string ReadString(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()?.Trim() ?? ""
            : "";
    }

    private static string? NonEmptyOrNull(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? null : value.Trim();
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        return values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value))?.Trim() ?? "";
    }

    private static GddMilestoneStepPlanResult ToResult(string projectId, GddMilestoneState state)
    {
        return new GddMilestoneStepPlanResult(
            projectId,
            state.Status,
            state.Summary,
            state.Steps.Select(step => new GddMilestoneStepResult(
                step.StepId,
                step.StepIndex,
                step.Title,
                step.Description,
                step.Acceptance,
                step.ScopeIn,
                step.ScopeOut,
                step.GodotSlice,
                step.PackagingValidation,
                step.FeedbackGuidance,
                step.NextStepReview,
                step.Status,
                step.Locked,
                !step.Locked && step.Status is "ready" or "needs_fix" or "execution_failed" or "feedback_failed",
                !step.Locked && step.Status is "executed" or "feedback_submitted",
                !step.Locked && step.Status is "executed" or "needs_fix" or "execution_failed" or "feedback_failed",
                step.ReviewSummary)).ToArray(),
            state.CurrentStepId);
    }

    private static async Task<GddMilestoneState?> ReadStateAsync(ProjectSnapshot project, CancellationToken cancellationToken)
    {
        var path = Path.Combine(project.MetaPath, StateRelativePath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(path))
        {
            path = Path.Combine(project.RepoPath, "meta", StateRelativePath.Replace('/', Path.DirectorySeparatorChar));
        }

        if (!File.Exists(path))
        {
            return null;
        }

        await using var stream = File.OpenRead(path);
        return await JsonSerializer.DeserializeAsync<GddMilestoneState>(stream, JsonOptions, cancellationToken);
    }

    private static async Task WriteStateAsync(ProjectSnapshot project, GddMilestoneState state, CancellationToken cancellationToken)
    {
        NormalizeState(state);
        var serialized = JsonSerializer.Serialize(state, JsonOptions);
        var metaPath = Path.Combine(project.MetaPath, StateRelativePath.Replace('/', Path.DirectorySeparatorChar));
        var mirrorPath = Path.Combine(project.RepoPath, "meta", StateRelativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(metaPath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(mirrorPath)!);
        await File.WriteAllTextAsync(metaPath, serialized, Encoding.UTF8, cancellationToken);
        await File.WriteAllTextAsync(mirrorPath, serialized, Encoding.UTF8, cancellationToken);
    }

    private static void NormalizeState(GddMilestoneState state)
    {
        for (var index = 0; index < state.Steps.Count; index++)
        {
            var step = state.Steps[index];
            var spec = BuildStepSpec(step.StepId, step.Title, step.Description);
            state.Steps[index] = step with
            {
                StepIndex = step.StepIndex <= 0 ? index + 1 : step.StepIndex,
                Acceptance = FirstNonEmpty(step.Acceptance, spec.Acceptance),
                ScopeIn = FirstNonEmpty(step.ScopeIn, spec.ScopeIn),
                ScopeOut = FirstNonEmpty(step.ScopeOut, spec.ScopeOut),
                GodotSlice = FirstNonEmpty(step.GodotSlice, spec.GodotSlice),
                PackagingValidation = FirstNonEmpty(step.PackagingValidation, spec.PackagingValidation),
                FeedbackGuidance = FirstNonEmpty(step.FeedbackGuidance, spec.FeedbackGuidance),
                NextStepReview = FirstNonEmpty(step.NextStepReview, spec.NextStepReview)
            };
        }
    }

    private static bool ContainsAny(string value, params string[] needles)
    {
        return needles.Any(needle => value.Contains(needle, StringComparison.OrdinalIgnoreCase));
    }

    private static string NormalizeStepId(string value)
    {
        return value.Trim().ToUpperInvariant().Replace('.', '-');
    }

    private static string Compact(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? "" : Regex.Replace(value.Trim(), @"\s+", " ");
    }

    private static string Trim(string value, int maxLength)
    {
        var compact = Compact(value);
        return compact.Length <= maxLength ? compact : compact[..maxLength].TrimEnd() + "...";
    }

    private sealed class GddMilestoneState
    {
        public GddMilestoneState(
            string schema,
            string status,
            string summary,
            string? currentStepId,
            List<GddMilestoneStepState> steps)
        {
            Schema = schema;
            Status = status;
            Summary = summary;
            CurrentStepId = currentStepId;
            Steps = steps;
        }

        public string Schema { get; init; }

        public string Status { get; set; }

        public string Summary { get; set; }

        public string? CurrentStepId { get; set; }

        public List<GddMilestoneStepState> Steps { get; init; }
    }

    private sealed record GddMilestoneStepState(
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
        string? IterationSessionId = null,
        string? ExecutionRunId = null,
        string? ExecutionSummary = null,
        string? FeedbackRunId = null,
        string? FeedbackSummary = null,
        string? ConfirmedUtc = null,
        string? ConfirmationNotes = null,
        string? ReviewSummary = null);

    private sealed record GddMilestoneNextStepReview(
        string? Title,
        string? Description,
        string? Acceptance,
        string? ScopeIn,
        string? ScopeOut,
        string? GodotSlice,
        string? PackagingValidation,
        string? FeedbackGuidance,
        string? NextStepReview,
        string Summary);

    private sealed record GddMilestoneStepSpec(
        string ScopeIn,
        string ScopeOut,
        string GodotSlice,
        string Acceptance,
        string PackagingValidation,
        string FeedbackGuidance,
        string NextStepReview);
}
