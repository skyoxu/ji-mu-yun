using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Readback;

namespace PhaseA.Platform.Runs;

public sealed class ProjectWorkflowRouteService
{
    private const string NoActionId = "none";

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly PrototypeWorkflowService _prototypeWorkflow;
    private readonly PrototypeRepairPlanService _repairPlans;
    private readonly ProjectPackageService _packages;
    private readonly ProjectAssetInventoryService _assetInventory;
    private readonly ILlmRouteEngine _llmRouteEngine;

    public ProjectWorkflowRouteService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        PrototypeWorkflowService prototypeWorkflow,
        PrototypeRepairPlanService repairPlans,
        ProjectPackageService packages,
        ProjectAssetInventoryService assetInventory,
        ILlmRouteEngine llmRouteEngine)
    {
        _metadataStore = metadataStore;
        _options = options;
        _prototypeWorkflow = prototypeWorkflow;
        _repairPlans = repairPlans;
        _packages = packages;
        _assetInventory = assetInventory;
        _llmRouteEngine = llmRouteEngine;
    }

    public async Task<ProjectWorkflowRouteResult?> QueryAsync(
        string accountId,
        string projectId,
        string? playtestFeedback = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        var runs = await ReadOrDefaultAsync(
            () => _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken),
            Array.Empty<RunSnapshot>());
        var progress = await ReadOrDefaultAsync(
            () => _prototypeWorkflow.GetProgressAsync(accountId, project.ProjectId, cancellationToken),
            new PrototypeWorkflowProgress("idle", "", "", "项目进度读取失败。", null, null, "project_progress_read_failed"));
        var iteration = await ReadOrDefaultAsync<ProjectIterationSessionDetails?>(
            () => _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, cancellationToken),
            null);
        var repair = await ReadOrDefaultAsync<PrototypeRepairPlanResult?>(
            () => _repairPlans.GetLatestAsync(accountId, project.ProjectId, cancellationToken),
            null);
        var packageList = await ReadOrDefaultAsync<ProjectPackageListResult?>(
            () => _packages.ListPackagesAsync(accountId, project.ProjectId, cancellationToken),
            null);
        var inventory = await ReadOrDefaultAsync<ProjectAssetInventoryResult?>(
            () => _assetInventory.GetInventoryAsync(accountId, project.ProjectId, false, null, false, cancellationToken),
            null);

        var state = ProjectWorkflowState.From(project, runs, progress, iteration, repair, packageList, inventory);
        var steps = BuildSteps(state);
        var actions = ResolveNextActions(state, playtestFeedback);
        var action = actions[0];
        var stage = steps.FirstOrDefault(step => step.Id == action.UiTarget) ??
                    steps.FirstOrDefault(step => step.Id == state.StageId) ??
                    steps.First();

        return new ProjectWorkflowRouteResult(
            project.ProjectId,
            stage.Id,
            stage.Label,
            BuildSummary(project, state),
            BuildRecommendation(state, action, playtestFeedback),
            action,
            steps,
            actions);
    }

    public async Task<ProjectWorkflowIntentResult> ClassifyIntentAsync(
        string accountId,
        string projectId,
        ProjectWorkflowIntentRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var message = request.Message?.Trim();
        if (string.IsNullOrWhiteSpace(message))
        {
            return ProjectWorkflowIntentResult.NoRoute("empty_message");
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return new ProjectWorkflowIntentResult(false, "general_chat", "project_not_found", "", "project_not_found");
        }

        var deterministicIntent = TryClassifyDeterministicIntent(message);
        if (deterministicIntent is not null)
        {
            return deterministicIntent;
        }

        var prompt = BuildIntentPrompt(project, message);
        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                WorkspaceRoot: ResolveLlmWorkspace(project),
                Purpose: "project-workflow-route-intent",
                Model: PrototypeModelPolicy.Normalize(request.Model),
                Prompt: prompt,
                Options: new CodexChatClientOptions(ReasoningEffort: "low"),
                BillingAccountId: accountId,
                RequireJsonObject: true),
            cancellationToken);

        if (!completion.Succeeded || string.IsNullOrWhiteSpace(completion.JsonObjectText))
        {
            return new ProjectWorkflowIntentResult(
                false,
                "general_chat",
                "intent_classifier_failed",
                "",
                "llm_failed",
                completion.FailureCode);
        }

        try
        {
            using var document = JsonDocument.Parse(completion.JsonObjectText);
            var root = document.RootElement;
            var shouldRoute = ReadBoolean(root, "shouldRoute");
            var intent = NormalizeIntent(ReadString(root, "intent"));
            if (intent == "general_chat")
            {
                shouldRoute = false;
            }

            var reason = Truncate(ReadString(root, "routeReason"), 240);
            var feedback = Truncate(ReadString(root, "feedbackSummary"), 800);
            return new ProjectWorkflowIntentResult(shouldRoute, intent, reason, feedback, "succeeded");
        }
        catch (JsonException)
        {
            return new ProjectWorkflowIntentResult(false, "general_chat", "intent_json_parse_failed", "", "llm_failed", "llm_json_parse_failed");
        }
    }

    private static IReadOnlyList<ProjectWorkflowRouteStep> BuildSteps(ProjectWorkflowState state)
    {
        return
        [
            new("new-project", "游戏项目概述", "done", state.Project.Name),
            new("create-prototype", "游戏场景创建", state.PrototypeCreationStatus, state.PrototypeCreationEvidence),
            new("execute-or-repair", "场景验收修复", state.SkeletonRepairStatus, state.SkeletonRepairEvidence),
            new("iteration-plan", "创建游戏模块", state.IterationStatus, state.IterationEvidence),
            new("prototype-acceptance", "原型项目验收", state.AcceptanceStatus, state.AcceptanceEvidence),
            new("asset-inventory", "项目素材库", state.AssetInventoryStatus, state.AssetInventoryEvidence),
            new("download-project", "打包下载项目", state.DownloadStatus, state.DownloadEvidence)
        ];
    }

    private static ProjectWorkflowNextAction ResolveNextAction(ProjectWorkflowState state, string? playtestFeedback)
    {
        if (!string.IsNullOrWhiteSpace(playtestFeedback) && state.HasPackage)
        {
            return Action("create-next-iteration-plan", "创建新的游戏模块", "创建新的游戏模块", "iteration-plan");
        }

        if (!state.HasPrototypeSkeleton)
        {
            return Action("create-prototype", "运行游戏场景创建", "运行游戏场景创建", "create-prototype");
        }

        if (state.HasFailedAcceptance || state.HasRunnableRepairStep)
        {
            return state.HasRunnableRepairStep
                ? Action("execute-repair-step", "执行下一项修复", "执行下一项修复", "execute-or-repair")
                : Action("create-repair-plan", "生成修复计划", "生成修复计划", "execute-or-repair");
        }

        if (!state.SkeletonAcceptancePassed && state.RepairCompletedOrEmpty && !state.HasIterationPlan)
        {
            return Action("prototype-acceptance", "场景验收", "场景验收", "execute-or-repair");
        }

        if (!state.HasIterationPlan)
        {
            return Action("create-iteration-plan", "生成游戏模块", "生成游戏模块", "iteration-plan");
        }

        if (state.HasNeedsFixIterationGoal)
        {
            return Action("needs-fix-route", "运行需要修复路由", "运行需要修复路由", "iteration-plan");
        }

        if (!state.IterationCompleted)
        {
            return Action("execute-iteration-goal", "执行下一任务", "执行下一任务", "iteration-plan");
        }

        if (!state.FinalAcceptancePassed)
        {
            return Action("prototype-acceptance", "原型项目验收", "原型项目验收", "prototype-acceptance");
        }

        if (!state.AssetInventoryAvailable)
        {
            return Action("asset-inventory", "项目素材库", "项目素材库", "asset-inventory");
        }

        if (!state.HasPackage)
        {
            return Action("download-project", "打包下载项目", "打包下载项目", "download-project");
        }

        return Action("download-project", "打包下载项目", "打包下载项目", "download-project");
    }

    private static IReadOnlyList<ProjectWorkflowNextAction> ResolveNextActions(ProjectWorkflowState state, string? playtestFeedback)
    {
        var primary = ResolveNextAction(state, playtestFeedback);
        if (!state.HasPackage)
        {
            return [primary];
        }

        var download = Action("download-project", "打包下载项目", "打包下载项目", "download-project");
        var nextIteration = Action("create-next-iteration-plan", "创建新的游戏模块", "创建新的游戏模块", "iteration-plan");
        var actions = primary.ActionId == "create-next-iteration-plan"
            ? new List<ProjectWorkflowNextAction> { nextIteration, download }
            : [download, nextIteration];
        if (!state.UsesGenericPrototypeRoute)
        {
            var insertIndex = primary.ActionId == "create-next-iteration-plan" ? 2 : 1;
            actions.Insert(insertIndex, Action("asset-inventory", "查看项目素材库", "查看项目素材库", "asset-inventory"));
        }

        return actions;
    }

    private static string BuildSummary(ProjectSnapshot project, ProjectWorkflowState state)
    {
        var parts = new List<string>
        {
            $"项目：{project.Name}（{project.GameName}）",
            $"游戏类型：{project.GameTypeSource}",
            $"游戏场景：{HumanStatus(state.PrototypeCreationStatus)}",
            $"场景/原型项目验收：{HumanStatus(state.AcceptanceStatus)}",
            $"游戏模块：{state.IterationEvidence}",
            $"项目包：{state.PackageEvidence}"
        };

        return string.Join("\n", parts);
    }

    private static string BuildRecommendation(ProjectWorkflowState state, ProjectWorkflowNextAction action, string? playtestFeedback)
    {
        if (action.ActionId == NoActionId)
        {
            return "当前没有可推荐的下一步 run。请刷新项目状态后再查询。";
        }

        if (!string.IsNullOrWhiteSpace(playtestFeedback) && state.HasPackage)
        {
            return "系统判断你正在描述本地试玩后的修改需求。建议进入“创建游戏模块”，基于本次试玩反馈创建新一轮游戏模块。系统不会自动启动 run；点击下方一次性按钮只会打开对应页面，需要你在页面内确认执行。";
        }

        return action.ActionId switch
        {
            "create-prototype" => "建议先进行 2. 游戏场景创建。如果玩法设定还不清晰，可以先在聊天里使用高级策划模式梳理策划大纲；准备好后点击下方一次性按钮进入游戏场景创建。",
            "create-repair-plan" => "当前场景或验收存在失败记录，但还没有可执行修复任务。建议生成修复计划，把失败拆成小任务后逐项修复。",
            "execute-repair-step" => "当前修复计划里仍有待执行或需要继续修复的任务。建议继续执行下一项修复；修复计划完成后再回到场景验收。",
            "prototype-acceptance" when action.UiTarget == "execute-or-repair" => "游戏场景已经创建，但当前没有可用的场景验收通过状态。建议先做场景验收，确认场景可运行后再生成游戏模块。",
            "create-iteration-plan" => "场景验收已经通过，但当前还没有游戏模块。建议生成游戏模块，把最小可玩循环拆成可执行任务。",
            "needs-fix-route" => "当前游戏模块中存在“需要修复”的任务。建议运行需要修复路由，只围绕当前失败任务修复，不推进后续任务。",
            "execute-iteration-goal" => "当前游戏模块还有待执行任务。建议继续执行下一任务，直到所有任务完成。",
            "ui-optimization" => "游戏模块已经完成。游戏界面优化当前未作为主流程开放，请继续进行原型项目验收。",
            "prototype-acceptance" => "游戏模块已经完成，建议重新进行原型项目验收，确认当前可玩闭环仍然成立。",
            "asset-inventory" => "原型项目验收已经通过。建议进入项目素材库，检查已使用素材和可生成素材候选，必要时替换默认素材。",
            "download-project" when !state.HasPackage => "项目素材库状态已满足继续推进。建议进入“打包下载项目”，点击“打包项目文件”生成可下载的项目压缩包。",
            "download-project" => state.UsesGenericPrototypeRoute
                ? "项目文件包已经生成。建议进入“打包下载项目”下载压缩包并在本地 Godot 试玩；试玩结果可以发到聊天里，准备创建第二轮游戏模块。"
                : "项目文件包已经生成。建议进入“打包下载项目”下载压缩包并在本地 Godot 试玩；也可以查看项目素材库确认和替换素材。试玩结果可以发到聊天里，准备创建第二轮游戏模块。",
            _ => $"建议进入：{action.RunName}。系统不会自动启动 run；点击下方一次性按钮只会打开对应页面，需要你在页面内确认执行。"
        };
    }

    private static ProjectWorkflowNextAction Action(string actionId, string label, string runName, string uiTarget)
    {
        return new ProjectWorkflowNextAction(actionId, label, runName, runName, uiTarget, true);
    }

    private static async Task<T> ReadOrDefaultAsync<T>(Func<Task<T>> read, T fallback)
    {
        try
        {
            return await read();
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch
        {
            return fallback;
        }
    }

    private string ResolveLlmWorkspace(ProjectSnapshot project)
    {
        if (!string.IsNullOrWhiteSpace(project.WorkspaceRootPath))
        {
            return project.WorkspaceRootPath;
        }

        return Path.Combine(_options.HostedWorkspaceRoot, "_workflow-route");
    }

    private static ProjectWorkflowIntentResult? TryClassifyDeterministicIntent(string message)
    {
        var normalized = message.Trim().ToLowerInvariant();
        var asksNextStep =
            ContainsAny(normalized, "下一步", "接下来", "进度", "状态", "该做什么", "怎么继续", "如何继续") ||
            ContainsAny(normalized, "how to start", "how do i start", "what should i do next", "next step", "getting started");
        var asksGettingStarted =
            ContainsAny(normalized, "第一次登录", "第一次登陆", "刚登录", "刚登陆", "不会用", "不太会用", "如何开始", "怎么开始", "从哪里开始") &&
            ContainsAny(normalized, "创建", "游戏", "项目", "原型");
        var asksCreateGame =
            ContainsAny(normalized, "创建我的游戏", "创建游戏", "新建游戏", "开始创建", "生成游戏", "生成原型", "创建原型");

        if (asksNextStep || asksGettingStarted || asksCreateGame)
        {
            return new ProjectWorkflowIntentResult(
                true,
                "next_step",
                "用户在询问如何开始或下一步应该执行哪个项目流程。",
                "",
                "succeeded");
        }

        return null;
    }

    private static bool ContainsAny(string value, params string[] needles)
    {
        return needles.Any(needle => value.Contains(needle, StringComparison.OrdinalIgnoreCase));
    }

    private static string BuildIntentPrompt(ProjectSnapshot project, string message)
    {
        return $$"""
        You are a read-only intent classifier for a web game-prototype workflow.
        Return exactly one JSON object and no markdown.

        Classify whether the user's message should route to the project workflow next-step advisor.
        Route when the user is asking what to do next, how to get started, how to create their game/project/prototype, asking for project progress/status/run direction, or describing local playtest feedback/problems and wants the system to prepare a second iteration plan.
        Do not route ordinary game-design questions, implementation questions, casual chat, or requests that can be answered directly without querying workflow status.

        Project:
        - ProjectName: {{project.Name}}
        - GameName: {{project.GameName}}
        - GameType: {{project.GameTypeSource}}

        User message:
        {{message}}

        JSON schema:
        {
          "shouldRoute": true,
          "intent": "next_step | playtest_feedback | general_chat",
          "routeReason": "short reason in Chinese",
          "feedbackSummary": "if playtest_feedback, summarize the requested changes in Chinese; otherwise empty string"
        }
        """;
    }

    private static bool ReadBoolean(JsonElement root, string name)
    {
        return root.TryGetProperty(name, out var value) && value.ValueKind switch
        {
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.String => bool.TryParse(value.GetString(), out var parsed) && parsed,
            _ => false
        };
    }

    private static string ReadString(JsonElement root, string name)
    {
        return root.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()?.Trim() ?? ""
            : "";
    }

    private static string NormalizeIntent(string value)
    {
        var normalized = value.Trim().ToLowerInvariant();
        return normalized is "next_step" or "playtest_feedback" ? normalized : "general_chat";
    }

    private static string Truncate(string value, int maxLength)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        value = value.Trim();
        return value.Length <= maxLength ? value : value[..maxLength];
    }

    private static string HumanStatus(string status)
    {
        return status switch
        {
            "done" => "已完成",
            "fix" => "需要修复",
            "continue" => "需要继续",
            _ => "未完成"
        };
    }

    private sealed record ProjectWorkflowState(
        ProjectSnapshot Project,
        bool HasPrototypeSkeleton,
        bool SkeletonAcceptancePassed,
        bool FinalAcceptancePassed,
        bool HasFailedAcceptance,
        bool HasRunnableRepairStep,
        bool RepairCompletedOrEmpty,
        bool HasIterationPlan,
        bool HasNeedsFixIterationGoal,
        bool IterationCompleted,
        bool UiOptimizationSucceeded,
        bool AssetInventoryAvailable,
        bool HasPackage,
        bool UsesGenericPrototypeRoute,
        string StageId,
        string PrototypeCreationStatus,
        string PrototypeCreationEvidence,
        string SkeletonRepairStatus,
        string SkeletonRepairEvidence,
        string IterationStatus,
        string IterationEvidence,
        string UiOptimizationStatus,
        string UiOptimizationEvidence,
        string AcceptanceStatus,
        string AcceptanceEvidence,
        string AssetInventoryStatus,
        string AssetInventoryEvidence,
        string PackageStatus,
        string PackageEvidence,
        string DownloadStatus,
        string DownloadEvidence)
    {
        public static ProjectWorkflowState From(
            ProjectSnapshot project,
            IReadOnlyList<RunSnapshot> runs,
            PrototypeWorkflowProgress progress,
            ProjectIterationSessionDetails? iteration,
            PrototypeRepairPlanResult? repair,
            ProjectPackageListResult? packageList,
            ProjectAssetInventoryResult? inventory)
        {
            var creationStatus = Normalize(progress.PrototypeCreationStatus ?? progress.Status);
            var hasPrototype = creationStatus == "succeeded" || runs.Any(run => run.RunType == "prototype-7day-playable" && run.Status == "succeeded");

            var goals = iteration?.Goals ?? [];
            var hasPlan = goals.Count > 0;
            var hasNeedsFix = goals.Any(goal => IsNeedsFix(goal.Status));
            var hasPending = goals.Any(goal => IsPending(goal.Status));
            var iterationCompleted = hasPlan && goals.All(goal => IsDone(goal.Status));

            var latestAcceptanceRun = LatestRun(runs, run => run.RunType == "prototype-7day-playable" && IsFinalValidationOnly(run));
            var latestSkeletonAcceptanceRun = LatestRun(runs, run => run.RunType == "prototype-7day-playable" && IsSkeletonValidationOnly(run));
            var acceptanceStatusRaw = Normalize(latestAcceptanceRun?.Status ?? progress.AcceptanceStatus ?? "pending");
            var skeletonAcceptanceStatusRaw = Normalize(latestSkeletonAcceptanceRun?.Status ?? (creationStatus == "succeeded" ? "succeeded" : "pending"));
            var latestIterationCompletionUtc = LatestIterationCompletionUtc(iteration);
            var latestAcceptanceUtc = latestAcceptanceRun is null
                ? null
                : ParseUtc(latestAcceptanceRun.FinishedUtc ?? latestAcceptanceRun.ProgressUpdatedUtc ?? latestAcceptanceRun.StartedUtc ?? latestAcceptanceRun.CreatedUtc);
            var acceptancePassed = acceptanceStatusRaw == "succeeded";
            var skeletonAcceptancePassed = skeletonAcceptanceStatusRaw == "succeeded";
            var finalAcceptancePassed = acceptancePassed &&
                                        iterationCompleted &&
                                        latestAcceptanceRun is not null &&
                                        (!latestIterationCompletionUtc.HasValue ||
                                         latestAcceptanceUtc >= latestIterationCompletionUtc.Value);
            var finalAcceptanceFailed = acceptanceStatusRaw == "failed" &&
                                        (latestAcceptanceRun is null ||
                                         !latestIterationCompletionUtc.HasValue ||
                                         (latestAcceptanceUtc.HasValue && latestAcceptanceUtc >= latestIterationCompletionUtc.Value));
            var failedAcceptance = finalAcceptanceFailed || skeletonAcceptanceStatusRaw == "failed";

            var repairGoals = repair?.Goals ?? [];
            var hasRunnableRepair = repairGoals.Any(goal => IsRunnable(goal.Status));
            var repairCompletedOrEmpty = repairGoals.Count == 0 || repairGoals.All(goal => IsDone(goal.Status));

            var uiRun = LatestRun(runs, run => string.Equals(run.RunType, "prototype-ui-optimization", StringComparison.OrdinalIgnoreCase));
            var uiSucceeded = string.Equals(uiRun?.Status, "succeeded", StringComparison.OrdinalIgnoreCase) &&
                              !string.Equals(uiRun?.ProgressSubstep, "validation_skipped", StringComparison.OrdinalIgnoreCase);

            var packages = packageList?.Packages ?? [];
            var hasPackage = packages.Count > 0;
            var inventoryAvailable = inventory?.CanReadInventory == true;
            var usesGenericRoute = string.Equals(
                PrototypeRouteSkillPolicy.ResolveProfile(project).GameTypeId,
                "default",
                StringComparison.OrdinalIgnoreCase);

            var prototypeStepStatus = !hasPrototype
                ? creationStatus == "failed" ? "fix" : "pending"
                : "done";
            var repairStatus = hasRunnableRepair || failedAcceptance
                ? "fix"
                : repairGoals.Count > 0 && repairGoals.All(goal => IsDone(goal.Status))
                    ? "done"
                    : "pending";
            var iterationStatus = !hasPlan
                ? "pending"
                : hasNeedsFix
                    ? "fix"
                    : iterationCompleted
                        ? "done"
                        : hasPending
                            ? "continue"
                            : "pending";
            var uiStatus = uiSucceeded ? "done" : string.Equals(uiRun?.Status, "failed", StringComparison.OrdinalIgnoreCase) ? "fix" : "pending";
            var acceptanceStatus = finalAcceptancePassed ? "done" : failedAcceptance ? "fix" : "pending";
            var assetStatus = inventoryAvailable ? "done" : "pending";
            var packageStatus = hasPackage ? "done" : "pending";
            var downloadStatus = hasPackage ? "done" : "pending";

            var stageId = ResolveStageId(hasPrototype, failedAcceptance, hasRunnableRepair, hasPlan, hasNeedsFix, iterationCompleted, finalAcceptancePassed, inventoryAvailable, hasPackage);
            return new ProjectWorkflowState(
                project,
                hasPrototype,
                skeletonAcceptancePassed,
                finalAcceptancePassed,
                failedAcceptance,
                hasRunnableRepair,
                repairCompletedOrEmpty,
                hasPlan,
                hasNeedsFix,
                iterationCompleted,
                uiSucceeded,
                inventoryAvailable,
                hasPackage,
                usesGenericRoute,
                stageId,
                prototypeStepStatus,
                hasPrototype ? "游戏场景已创建。" : progress.PrototypeCreationFailure ?? progress.Failure ?? progress.Label ?? "尚未创建游戏场景。",
                repairStatus,
                repairGoals.Count == 0 ? "尚未生成修复计划。" : $"修复计划 {repairGoals.Count} 个任务，待处理 {repairGoals.Count(goal => IsRunnable(goal.Status))} 个任务。",
                iterationStatus,
                hasPlan ? $"共 {goals.Count} 个任务，完成 {goals.Count(goal => IsDone(goal.Status))} 个，需要修复 {goals.Count(goal => IsNeedsFix(goal.Status))} 个。" : "尚未生成游戏模块。",
                uiStatus,
                uiSucceeded ? "游戏界面优化已完成。" : uiRun is null ? "游戏界面优化尚未运行，可选。" : $"最近一次游戏界面优化状态：{uiRun.Status}。",
                acceptanceStatus,
                finalAcceptancePassed ? "原型项目验收通过。" : acceptancePassed && iterationCompleted ? "游戏模块完成后尚未重新进行原型项目验收。" : progress.AcceptanceFailure ?? progress.Failure ?? "尚未获得通过的原型项目验收。",
                assetStatus,
                inventoryAvailable ? "项目素材库可用。" : inventory?.DisabledReason ?? "项目素材库尚不可用。",
                packageStatus,
                hasPackage ? $"已生成 {packages.Count} 个项目文件包。" : packageList?.DisabledReason ?? "尚未打包项目文件。",
                downloadStatus,
                hasPackage ? "下载列表已有项目压缩包。" : "尚无可下载项目压缩包。");
        }

        private static string ResolveStageId(
            bool hasPrototype,
            bool failedAcceptance,
            bool hasRunnableRepair,
            bool hasPlan,
            bool hasNeedsFix,
            bool iterationCompleted,
            bool acceptancePassed,
            bool inventoryAvailable,
            bool hasPackage)
        {
            if (!hasPrototype) return "create-prototype";
            if (failedAcceptance || hasRunnableRepair) return "execute-or-repair";
            if (!hasPlan || hasNeedsFix || !iterationCompleted) return "iteration-plan";
            if (!acceptancePassed) return "prototype-acceptance";
            if (!inventoryAvailable) return "asset-inventory";
            if (!hasPackage) return "download-project";
            return "download-project";
        }

        private static RunSnapshot? LatestRun(IEnumerable<RunSnapshot> runs, Func<RunSnapshot, bool> predicate)
        {
            return runs
                .Where(predicate)
                .OrderByDescending(RunSortTimeUtc)
                .ThenByDescending(run => run.RunId, StringComparer.Ordinal)
                .FirstOrDefault();
        }

        private static DateTimeOffset RunSortTimeUtc(RunSnapshot run)
        {
            return ParseUtc(run.FinishedUtc) ??
                   ParseUtc(run.ProgressUpdatedUtc) ??
                   ParseUtc(run.StartedUtc) ??
                   ParseUtc(run.CreatedUtc) ??
                   DateTimeOffset.MinValue;
        }

        private static bool IsFinalValidationOnly(RunSnapshot run)
        {
            return IsAnyValidationOnly(run) && !IsSkeletonValidationOnly(run);
        }

        private static bool IsSkeletonValidationOnly(RunSnapshot run)
        {
            if (string.IsNullOrWhiteSpace(run.EvidenceJson))
            {
                return false;
            }

            try
            {
                using var document = JsonDocument.Parse(run.EvidenceJson);
                return document.RootElement.TryGetProperty("skeleton_validation_only", out var value) &&
                       value.ValueKind == JsonValueKind.True;
            }
            catch (JsonException)
            {
                return false;
            }
        }

        private static bool IsAnyValidationOnly(RunSnapshot run)
        {
            if (string.IsNullOrWhiteSpace(run.EvidenceJson))
            {
                return false;
            }

            try
            {
                using var document = JsonDocument.Parse(run.EvidenceJson);
                return document.RootElement.TryGetProperty("validation_only", out var value) &&
                       value.ValueKind == JsonValueKind.True;
            }
            catch (JsonException)
            {
                return false;
            }
        }

        private static DateTimeOffset? LatestIterationCompletionUtc(ProjectIterationSessionDetails? iteration)
        {
            if (iteration is null || iteration.Goals.Count == 0 || !iteration.Goals.All(goal => IsDone(goal.Status)))
            {
                return null;
            }

            var times = iteration.Goals
                .Select(goal => ParseUtc(goal.CompletedUtc ?? goal.UpdatedUtc ?? goal.CreatedUtc))
                .Where(time => time.HasValue)
                .Select(time => time!.Value)
                .ToArray();
            return times.Length == 0 ? null : times.Max();
        }

        private static DateTimeOffset? ParseUtc(string? value)
        {
            return DateTimeOffset.TryParse(value, out var parsed) ? parsed : null;
        }

        private static string Normalize(string? status)
        {
            return string.IsNullOrWhiteSpace(status) ? "" : status.Trim().ToLowerInvariant();
        }

        private static bool IsDone(string? status)
        {
            return string.Equals(status, "succeeded", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(status, "completed", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(status, "done", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsNeedsFix(string? status)
        {
            return string.Equals(status, "needs_fix", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(status, "failed", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsPending(string? status)
        {
            return string.Equals(status, "pending", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(status, "running", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(status, "planning", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsRunnable(string? status)
        {
            return IsPending(status) || IsNeedsFix(status);
        }
    }
}
