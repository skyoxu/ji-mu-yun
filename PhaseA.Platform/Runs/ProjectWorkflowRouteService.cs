using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Readback;

namespace PhaseA.Platform.Runs;

public sealed class ProjectWorkflowRouteService
{
    private const string NoActionId = "none";

    private static readonly IReadOnlyList<ProjectWorkflowStageDefinition> StageDefinitions =
    [
        new("project-created", "项目创建", "input", "metadata project row, workspace root, bootstrap status", "P0"),
        new("gdd-question-form", "GDD 问卷", "input", "GDD question-form answers or restore state", "P1"),
        new("scene-route-confirmation", "场景路线确认", "input", "confirmed scene route draft", "P1"),
        new("gdd-document-generation", "GDD 文档生成", "input", "docs/gdd/GDD.md and outline readback", "P1"),
        new("gdd-requirement-map", "GDD 需求映射", "contract", "requirement map sidecar or explicit missing-state readback", "P1"),
        new("prototype-contract-freeze", "原型契约冻结", "contract", "prototype contract with source hashes and freshness state", "P0"),
        new("prototype-skeleton", "M1 场景骨架", "execution", "prototype workflow run and skeleton validation evidence", "P0"),
        new("iteration-plan", "游戏模块计划", "execution", "iteration session and mapped executable goals", "P1"),
        new("module-execution", "模块逐项执行", "execution", "current goal state, run link, and acceptance evidence", "P1"),
        new("needs-fix-or-repair", "验收修复", "recovery", "repair ledger or latest blocker evidence", "P0"),
        new("ui-wiring-closure", "UI wiring closure", "closure", "UI closure readback or explicit pending state", "P1"),
        new("preview-package", "预览打包下载", "release", "preview/package/readback artifacts", "P2")
    ];

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly PrototypeWorkflowService _prototypeWorkflow;
    private readonly PrototypeRepairPlanService _repairPlans;
    private readonly ProjectPackageService _packages;
    private readonly ProjectAssetInventoryService _assetInventory;
    private readonly ILlmRouteEngine _llmRouteEngine;
    private readonly ProjectRouteStateArtifactService _routeStateArtifacts;

    public ProjectWorkflowRouteService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        PrototypeWorkflowService prototypeWorkflow,
        PrototypeRepairPlanService repairPlans,
        ProjectPackageService packages,
        ProjectAssetInventoryService assetInventory,
        ILlmRouteEngine llmRouteEngine,
        ProjectRouteStateArtifactService? routeStateArtifacts = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _prototypeWorkflow = prototypeWorkflow;
        _repairPlans = repairPlans;
        _packages = packages;
        _assetInventory = assetInventory;
        _llmRouteEngine = llmRouteEngine;
        _routeStateArtifacts = routeStateArtifacts ?? new ProjectRouteStateArtifactService();
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
        var promptBindings = (await _metadataStore.ListProjectRoutePromptEvidenceBindingsAsync(project.ProjectId, cancellationToken))
            .ToDictionary(binding => binding.RouteId, StringComparer.Ordinal);
        var projectArtifactIds = (await _metadataStore.ListArtifactsForProjectAsync(project.ProjectId, cancellationToken))
            .Select(artifact => artifact.ArtifactId)
            .ToHashSet(StringComparer.Ordinal);
        var routeStateArtifacts = _routeStateArtifacts.Read(project, promptBindings, projectArtifactIds);
        var workflowRecommendation = _routeStateArtifacts.BuildRecommendation(project, routeStateArtifacts, action);
        var unresolvedDiagnosticBlockerCount = await _metadataStore.CountUnresolvedBlockingDiagnosticsAsync(
            accountId,
            project.ProjectId,
            cancellationToken);

        return new ProjectWorkflowRouteResult(
            project.ProjectId,
            stage.Id,
            stage.Label,
            BuildSummary(project, state),
            BuildRecommendation(state, action, playtestFeedback),
            action,
            steps,
            actions,
            StageDefinitions,
            BuildSeverityReview(state, unresolvedDiagnosticBlockerCount),
            workflowRecommendation,
            routeStateArtifacts);
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
            Step("project-created", "done", state.Project.Name),
            Step("gdd-question-form", state.GddQuestionFormStatus, state.GddQuestionFormEvidence),
            Step("scene-route-confirmation", state.SceneRouteStatus, state.SceneRouteEvidence),
            Step("gdd-document-generation", state.GddDocumentStatus, state.GddDocumentEvidence),
            Step("gdd-requirement-map", state.RequirementMapStatus, state.RequirementMapEvidence),
            Step("prototype-contract-freeze", state.ContractFreezeStatus, state.ContractFreezeEvidence),
            Step("prototype-skeleton", state.PrototypeCreationStatus, state.PrototypeCreationEvidence),
            Step("needs-fix-or-repair", state.SkeletonRepairStatus, state.SkeletonRepairEvidence),
            Step("iteration-plan", state.IterationStatus, state.IterationEvidence),
            Step("module-execution", state.ModuleExecutionStatus, state.ModuleExecutionEvidence),
            Step("ui-wiring-closure", state.UiClosureStatus, state.UiClosureEvidence),
            Step("preview-package", state.DownloadStatus, state.DownloadEvidence),
            new("new-project", "游戏项目概述", "done", state.Project.Name, "legacy", "P0"),
            new("create-prototype", "游戏场景创建", state.PrototypeCreationStatus, state.PrototypeCreationEvidence, "legacy", "P0"),
            new("execute-or-repair", "场景验收修复", state.SkeletonRepairStatus, state.SkeletonRepairEvidence, "legacy", "P0"),
            new("prototype-acceptance", "原型项目验收", state.AcceptanceStatus, state.AcceptanceEvidence, "legacy", "P1"),
            new("asset-inventory", "项目素材库", state.AssetInventoryStatus, state.AssetInventoryEvidence, "legacy", "P2"),
            new("download-project", "打包下载项目", state.DownloadStatus, state.DownloadEvidence, "legacy", "P2")
        ];
    }

    private static ProjectWorkflowRouteStep Step(string id, string status, string evidence)
    {
        var definition = StageDefinitions.First(stage => stage.Id == id);
        return new ProjectWorkflowRouteStep(id, definition.Label, status, evidence, definition.StageGroup, definition.SeverityGate);
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
            $"当前阶段：{state.StageId}",
            $"GDD 链路：{HumanStatus(state.GddDocumentStatus)}；需求映射：{HumanStatus(state.RequirementMapStatus)}；契约冻结：{HumanStatus(state.ContractFreezeStatus)}",
            $"游戏场景：{HumanStatus(state.PrototypeCreationStatus)}",
            $"场景/原型项目验收：{HumanStatus(state.AcceptanceStatus)}",
            $"游戏模块：{state.IterationEvidence}",
            $"项目包：{state.PackageEvidence}"
        };

        return string.Join("\n", parts);
    }

    private static ProjectWorkflowSeverityReview BuildSeverityReview(ProjectWorkflowState state, int unresolvedDiagnosticBlockerCount)
    {
        var blockers = new SortedSet<string>(StringComparer.Ordinal)
        {
            "P0",
            "P1"
        };

        if (!state.HasPackage)
        {
            blockers.Add("P2");
        }

        if (state.HasPrototypeSkeleton && !state.HasContractFreeze)
        {
            blockers.Add("P0");
        }

        if (state.HasIterationPlan && !state.HasRequirementMap)
        {
            blockers.Add("P1");
        }

        if (unresolvedDiagnosticBlockerCount > 0)
        {
            blockers.Add("P1");
        }

        var refs = new List<string>
        {
            "route:/api/projects/{projectId}/workflow-route",
            "artifact:project-workflow-route-result"
        };

        if (state.HasPrototypeSkeleton)
        {
            refs.Add("run:prototype-7day-playable");
        }

        if (state.HasIterationPlan)
        {
            refs.Add("db:project_iteration_sessions");
        }

        if (state.HasPackage)
        {
            refs.Add("artifact:project-package-zip");
        }

        if (unresolvedDiagnosticBlockerCount > 0)
        {
            refs.Add("metadata:project_diagnostic_spool");
        }

        var status = blockers.Count == 0 ? "passed" : "blocked";
        var summary = status == "passed"
            ? "No unresolved P0/P1/P2 workflow blockers are visible in the current route readback."
            : "Workflow route reports unresolved severity gates; continue only through the recommended recoverable action.";

        return new ProjectWorkflowSeverityReview(status, blockers.ToArray(), refs, summary);
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
        bool HasRequirementMap,
        bool HasContractFreeze,
        bool HasNeedsFixIterationGoal,
        bool IterationCompleted,
        bool UiOptimizationSucceeded,
        bool AssetInventoryAvailable,
        bool HasPackage,
        bool UsesGenericPrototypeRoute,
        string StageId,
        string GddQuestionFormStatus,
        string GddQuestionFormEvidence,
        string SceneRouteStatus,
        string SceneRouteEvidence,
        string GddDocumentStatus,
        string GddDocumentEvidence,
        string RequirementMapStatus,
        string RequirementMapEvidence,
        string ContractFreezeStatus,
        string ContractFreezeEvidence,
        string PrototypeCreationStatus,
        string PrototypeCreationEvidence,
        string SkeletonRepairStatus,
        string SkeletonRepairEvidence,
        string IterationStatus,
        string IterationEvidence,
        string ModuleExecutionStatus,
        string ModuleExecutionEvidence,
        string UiOptimizationStatus,
        string UiOptimizationEvidence,
        string UiClosureStatus,
        string UiClosureEvidence,
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
            var hasQuestionForm = AnyProjectFileExists(
                project,
                Path.Combine("meta", "gdd", "question-form.latest.json"),
                Path.Combine("meta", "routes", "gdd-question-form", "latest.json"),
                Path.Combine("routes", "gdd-question-form", "latest.json"));
            var hasSceneRoute = AnyProjectFileExists(
                project,
                Path.Combine("meta", "routes", "gdd-scene-route", "latest.json"),
                Path.Combine("meta", "routes", "scene-route", "latest.json"),
                Path.Combine("routes", "gdd-scene-route", "latest.json"));
            var hasGddDocument = AnyProjectFileExists(
                project,
                Path.Combine("docs", "gdd", "GDD.md"),
                Path.Combine("docs", "gdd", "gdd.md"));
            var hasRequirementMap = AnyProjectFileExists(
                project,
                Path.Combine("meta", "routes", "gdd-requirement-map", "latest.json"),
                Path.Combine("meta", "routes", "requirement-map", "latest.json"),
                Path.Combine("routes", "gdd-requirement-map", "latest.json"));
            var hasContractFreeze = AnyProjectFileExists(
                project,
                Path.Combine("meta", "routes", "prototype-contract", "latest.json"),
                Path.Combine("routes", "prototype-contract", "latest.json"));
            var hasUiClosure = AnyProjectFileExists(
                project,
                Path.Combine("meta", "routes", "ui-wiring-closure", "latest.json"),
                Path.Combine("meta", "routes", "ui-closure", "latest.json"),
                Path.Combine("logs", "ci", "chapter7-ui-wiring", "closure-summary.json"));

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
            var questionFormStatus = hasQuestionForm ? "done" : "pending";
            var sceneRouteStatus = hasSceneRoute ? "done" : "pending";
            var gddStatus = hasGddDocument ? "done" : "pending";
            var requirementMapStatus = hasRequirementMap ? "done" : hasGddDocument ? "pending" : "blocked";
            var contractStatus = hasContractFreeze ? "done" : hasRequirementMap ? "pending" : "blocked";
            var moduleExecutionStatus = !hasPlan
                ? "pending"
                : hasNeedsFix
                    ? "fix"
                    : iterationCompleted
                        ? "done"
                        : "continue";
            var uiClosureStatus = hasUiClosure ? "done" : iterationCompleted ? "pending" : "blocked";

            var stageId = ResolveStageId(
                hasQuestionForm,
                hasSceneRoute,
                hasGddDocument,
                hasRequirementMap,
                hasContractFreeze,
                hasPrototype,
                failedAcceptance,
                hasRunnableRepair,
                hasPlan,
                hasNeedsFix,
                iterationCompleted,
                hasUiClosure,
                finalAcceptancePassed,
                hasPackage);
            return new ProjectWorkflowState(
                project,
                hasPrototype,
                skeletonAcceptancePassed,
                finalAcceptancePassed,
                failedAcceptance,
                hasRunnableRepair,
                repairCompletedOrEmpty,
                hasPlan,
                hasRequirementMap,
                hasContractFreeze,
                hasNeedsFix,
                iterationCompleted,
                uiSucceeded,
                inventoryAvailable,
                hasPackage,
                usesGenericRoute,
                stageId,
                questionFormStatus,
                hasQuestionForm ? "GDD question-form state is available." : "GDD question-form state is missing or not yet restored.",
                sceneRouteStatus,
                hasSceneRoute ? "Confirmed scene route state is available." : "Scene route confirmation state is missing.",
                gddStatus,
                hasGddDocument ? "docs/gdd/GDD.md is available." : "GDD document has not been generated yet.",
                requirementMapStatus,
                hasRequirementMap ? "GDD requirement map sidecar is available." : "GDD requirement map sidecar is not available yet.",
                contractStatus,
                hasContractFreeze ? "Prototype contract freeze sidecar is available." : "Prototype contract freeze sidecar is missing or blocked by upstream inputs.",
                prototypeStepStatus,
                hasPrototype ? "游戏场景已创建。" : progress.PrototypeCreationFailure ?? progress.Failure ?? progress.Label ?? "尚未创建游戏场景。",
                repairStatus,
                repairGoals.Count == 0 ? "尚未生成修复计划。" : $"修复计划 {repairGoals.Count} 个任务，待处理 {repairGoals.Count(goal => IsRunnable(goal.Status))} 个任务。",
                iterationStatus,
                hasPlan ? $"共 {goals.Count} 个任务，完成 {goals.Count(goal => IsDone(goal.Status))} 个，需要修复 {goals.Count(goal => IsNeedsFix(goal.Status))} 个。" : "尚未生成游戏模块。",
                moduleExecutionStatus,
                hasPlan ? $"模块执行状态：完成 {goals.Count(goal => IsDone(goal.Status))}/{goals.Count}，需要修复 {goals.Count(goal => IsNeedsFix(goal.Status))}。" : "尚无可执行模块任务。",
                uiStatus,
                uiSucceeded ? "游戏界面优化已完成。" : uiRun is null ? "游戏界面优化尚未运行，可选。" : $"最近一次游戏界面优化状态：{uiRun.Status}。",
                uiClosureStatus,
                hasUiClosure ? "UI wiring closure evidence is available." : "UI wiring closure has not been completed.",
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
            bool hasQuestionForm,
            bool hasSceneRoute,
            bool hasGddDocument,
            bool hasRequirementMap,
            bool hasContractFreeze,
            bool hasPrototype,
            bool failedAcceptance,
            bool hasRunnableRepair,
            bool hasPlan,
            bool hasNeedsFix,
            bool iterationCompleted,
            bool hasUiClosure,
            bool acceptancePassed,
            bool hasPackage)
        {
            if (!hasQuestionForm) return "gdd-question-form";
            if (!hasSceneRoute) return "scene-route-confirmation";
            if (!hasGddDocument) return "gdd-document-generation";
            if (!hasRequirementMap) return "gdd-requirement-map";
            if (!hasContractFreeze) return "prototype-contract-freeze";
            if (!hasPrototype) return "prototype-skeleton";
            if (failedAcceptance || hasRunnableRepair) return "needs-fix-or-repair";
            if (!hasPlan || hasNeedsFix || !iterationCompleted) return "iteration-plan";
            if (!hasUiClosure) return "ui-wiring-closure";
            if (!acceptancePassed) return "prototype-acceptance";
            if (!hasPackage) return "preview-package";
            return "preview-package";
        }

        private static bool AnyProjectFileExists(ProjectSnapshot project, params string[] relativePaths)
        {
            return relativePaths.Any(relativePath => ProjectFileExists(project, relativePath));
        }

        private static bool ProjectFileExists(ProjectSnapshot project, string relativePath)
        {
            if (string.IsNullOrWhiteSpace(relativePath) ||
                Path.IsPathRooted(relativePath) ||
                relativePath.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar).Any(part => part == ".."))
            {
                return false;
            }

            return SafeFileExists(project.RepoPath, relativePath) || SafeFileExists(project.MetaPath, relativePath);
        }

        private static bool SafeFileExists(string root, string relativePath)
        {
            if (string.IsNullOrWhiteSpace(root))
            {
                return false;
            }

            try
            {
                var rootFullPath = Path.GetFullPath(root);
                var fullPath = Path.GetFullPath(Path.Combine(rootFullPath, relativePath));
                var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
                if (!fullPath.StartsWith(rootFullPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar, comparison) &&
                    !string.Equals(fullPath, rootFullPath, comparison))
                {
                    return false;
                }

                return File.Exists(fullPath);
            }
            catch (ArgumentException)
            {
                return false;
            }
            catch (NotSupportedException)
            {
                return false;
            }
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
