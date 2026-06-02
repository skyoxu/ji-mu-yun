using System.Text.RegularExpressions;
using System.Text.Json;
using System.Text.Json.Nodes;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Prototypes;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeIterationPlanService
{
    private const int MaxTextAttachments = 5;
    private const int MaxTextAttachmentChars = 12000;
    private static readonly Regex SplitRegex = new(@"[。！？!?]\s*|\r?\n+", RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private static readonly Regex NumberedGoalRegex = new(
        @"(?:^|\n)\s*(?:step\s*)?\d{1,2}\s*[\.\):\-:：、]?\s*(.+?)(?=(?:\n\s*(?:step\s*)?\d{1,2}\s*[\.\):\-:：、]?\s*)|\z)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.Singleline);
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
    private static readonly CodexChatClientOptions PlanningCodexOptions = new(
        IgnoreRules: true,
        ReasoningEffort: "minimal");
    private static readonly string PlanningAnalysisSchemaPath = EnsurePlanningAnalysisSchemaFile();
    private static readonly string GoalPlanSchemaPath = EnsureGoalPlanSchemaFile();
    private static readonly string EvaluationSchemaPath = EnsureEvaluationSchemaFile();
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PrototypeRouteStateWriter _routeStateWriter;
    private readonly PrototypeContractService _contractService;
    private readonly ILlmRouteEngine? _llmRouteEngine;
    private readonly GameTypeTemplateCatalog? _templateCatalog;

    public PrototypeIterationPlanService(PhaseAMetadataStore metadataStore)
        : this(metadataStore, new PrototypeRouteStateWriter(), new PrototypeContractService(), null, null)
    {
    }

    public PrototypeIterationPlanService(
        PhaseAMetadataStore metadataStore,
        PrototypeRouteStateWriter routeStateWriter,
        PrototypeContractService? contractService = null,
        ICodexChatClient? codexChatClient = null,
        ILlmRouteEngine? llmRouteEngine = null,
        GameTypeTemplateCatalog? templateCatalog = null)
    {
        _metadataStore = metadataStore;
        _routeStateWriter = routeStateWriter;
        _contractService = contractService ?? new PrototypeContractService();
        _llmRouteEngine = llmRouteEngine ?? (codexChatClient is null ? null : new LlmRouteEngine(codexChatClient));
        _templateCatalog = templateCatalog;
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

        var rawMessage = request.Message?.Trim();
        var message = NormalizePlanningMessage(rawMessage, request.SourceKind);
        if (string.IsNullOrWhiteSpace(message))
        {
            return new PrototypeIterationPlanResult("", "missing_message", "请输入要拆解的优化目标。", [], null);
        }

        if ((request.Attachments?.Count ?? 0) > MaxTextAttachments)
        {
            return new PrototypeIterationPlanResult("", "too_many_attachments", "最多只能导入 5 个 TXT 参考文件。", [], null);
        }

        var attachmentContext = BuildAttachmentPromptBlock(request.Attachments);
        var promptMessage = AppendAttachmentContext(message, attachmentContext);

        var sourceKind = string.IsNullOrWhiteSpace(request.SourceKind) ? "manual_feedback" : request.SourceKind.Trim();
        if (string.Equals(sourceKind, "completion_suggestion", StringComparison.OrdinalIgnoreCase) &&
            IsInternalExecutionSuggestion(message))
        {
            return new PrototypeIterationPlanResult(
                "",
                "suggestion_needs_fix",
                "当前这条建议更像内部执行或环境修复信息，不适合直接拆成迭代目标。请先处理需修复项，或重新生成更明确的产品向优化建议。",
                [],
                null);
        }
        var routeSkill = PrototypeRouteSkillPolicy.Resolve(project);
        var routeProfile = PrototypeRouteSkillPolicy.ResolveProfile(project);
        var routeStrategy = GameTypeRouteStrategies.Resolve(project, routeProfile);
        var routeSkillAvailability = PrototypeRouteSkillPolicy.EnsureAvailable(project);
        if (!routeSkillAvailability.IsAvailable)
        {
            return new PrototypeIterationPlanResult("", routeSkillAvailability.FailureCode, routeSkillAvailability.FailureMessage, [], null);
        }

        var previousIterationPlan = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
        var regenerationGuidance = BuildPlanRegenerationGuidance(previousIterationPlan, promptMessage, sourceKind);
        var prototypeContract = _contractService.Read(project);
        IterationPlanningContext planningContext;
        try
        {
            planningContext = await BuildPlanningContextAsync(project, routeProfile, routeStrategy, routeSkill, prototypeContract, promptMessage, sourceKind, cancellationToken);
        }
        catch (PrototypeIterationPlanLlmException ex) when (routeStrategy.RequiresModelBackedIterationPlanning)
        {
            return new PrototypeIterationPlanResult(
                "",
                "llm_failed",
                $"迭代计划生成需要 LLM 成功参与，但当前调用失败：{ex.Message}",
                [],
                null,
                null);
        }

        List<PrototypeIterationPlanGoalResult> goals;
        try
        {
            goals = await BuildGoalsForProjectAsync(project, routeProfile, routeStrategy, prototypeContract, promptMessage, sourceKind, planningContext, regenerationGuidance, cancellationToken);
        }
        catch (PrototypeIterationPlanLlmException ex) when (routeStrategy.RequiresModelBackedIterationPlanning)
        {
            return new PrototypeIterationPlanResult(
                "",
                "llm_failed",
                $"迭代计划生成需要 LLM 成功细化目标，但当前调用失败：{ex.Message}",
                [],
                ToPlanningAnalysisResult(planningContext),
                null);
        }

        if (routeStrategy.RequiresNonEmptyIterationGoals && goals.Count == 0)
        {
            return new PrototypeIterationPlanResult(
                "",
                "llm_failed",
                "迭代计划生成需要 LLM 成功细化目标，但当前没有得到可用目标。",
                [],
                ToPlanningAnalysisResult(planningContext),
                null);
        }

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

        var summary = BuildPlanSummary(goals.Count, planningContext);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(created.SessionId, "ready", 0, summary, null, null, cancellationToken);
        var planningAnalysis = ToPlanningAnalysisResult(planningContext);
        _routeStateWriter.WriteIterationPlanAnalysisState(project, new
        {
            route = "iteration-plan",
            session_id = created.SessionId,
            planning_analysis = planningAnalysis,
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });
        _routeStateWriter.WriteIterationPlanState(project, new
        {
            route = "iteration-plan",
            route_skill = routeSkill,
            game_type_profile = routeProfile,
            prototype_contract = prototypeContract.RelativePath,
            prototype_contract_present = !string.IsNullOrWhiteSpace(prototypeContract.Json),
            session_id = created.SessionId,
            status = "ready",
            source_kind = sourceKind,
            summary,
            planning_analysis = planningAnalysis,
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

        var evaluation = await EvaluateAsync(accountId, projectId, ToPrototypeProgress(planningContext), cancellationToken);
        return new PrototypeIterationPlanResult(created.SessionId, "ready", summary, goals, planningAnalysis, evaluation);
    }

    private async Task<List<PrototypeIterationPlanGoalResult>> BuildGoalsForProjectAsync(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        IGameTypeRouteStrategy routeStrategy,
        PrototypeContractSnapshot prototypeContract,
        string message,
        string sourceKind,
        IterationPlanningContext planningContext,
        string? regenerationGuidance,
        CancellationToken cancellationToken)
    {
        if (routeStrategy.UsesSpecializedIterationPlanning &&
            string.Equals(routeStrategy.GameTypeId, "rpg", StringComparison.OrdinalIgnoreCase))
        {
            var scaffold = BuildRpgGoalsFromContext(message, sourceKind, prototypeContract, planningContext, regenerationGuidance);
            return await RefineRpgGoalsWithRequiredModelAsync(project, routeProfile, planningContext, message, scaffold, regenerationGuidance, cancellationToken);
        }

        var goals = BuildGoals(message, sourceKind);
        return AppendGenericFinalAcceptanceGoal(goals, message, prototypeContract);
    }

    private async Task<IterationPlanningContext> BuildPlanningContextAsync(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        IGameTypeRouteStrategy routeStrategy,
        PrototypeRouteSkillContext routeSkill,
        PrototypeContractSnapshot prototypeContract,
        string message,
        string sourceKind,
        CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        var latestPrototypeRun = runs
            .FirstOrDefault(run => string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase));
        var latestSuccessfulPrototypeRun = runs
            .FirstOrDefault(run =>
                string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase) &&
                string.Equals(run.Status, "succeeded", StringComparison.OrdinalIgnoreCase));
        var draft = await _metadataStore.GetProjectPrototypeDraftAsync(project.ProjectId, cancellationToken);
        var prototypeState = _routeStateWriter.ReadLatestPrototypeState(project);
        var template = _templateCatalog?.Find(NormalizeGameType(project.GameTypeSource));

        var deterministicFieldCoverage = BuildDeterministicFieldCoverage(draft);
        var fallback = new IterationPlanningContext(
            AnalysisSource: "deterministic_fallback",
            AnalysisSummary: BuildFallbackAnalysisSummary(latestPrototypeRun, latestSuccessfulPrototypeRun, draft),
            LatestPrototypeStatus: latestPrototypeRun?.Status ?? "missing",
            LatestPrototypeCompletionSummary: ReadCompletionSummaryFromRun(latestSuccessfulPrototypeRun ?? latestPrototypeRun),
            DraftCoveragePercent: draft?.CoveragePercent ?? 0,
            DraftCoverageSummary: draft?.CoverageSummary,
            TemplateId: template?.TemplateId,
            FieldCoverage: deterministicFieldCoverage,
            PrototypeStateExcerpt: TrimForPrompt(prototypeState),
            SourceMessage: message,
            SourceKind: sourceKind,
            RouteSkillId: routeSkill.RouteSkillId);

        if (_llmRouteEngine is null)
        {
            if (routeStrategy.RequiresModelBackedIterationPlanning)
            {
                throw new PrototypeIterationPlanLlmException("planning_analysis_llm_client_missing");
            }

            return fallback;
        }

        var modelPrompt = BuildPlanningAnalysisPrompt(project, routeProfile, prototypeContract, fallback, draft, latestPrototypeRun, latestSuccessfulPrototypeRun);
        var promptRoot = EnsureIterationPlanPromptWorkspace(project, "planning-analysis");
        var options = PlanningCodexOptions with { OutputSchemaPath = PlanningAnalysisSchemaPath };
        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                promptRoot,
                "planning-analysis",
                PrototypeModelPolicy.Normalize("gpt-5.4"),
                modelPrompt,
                options,
                project.AccountId,
                RequireJsonObject: true),
            cancellationToken);
        if (!completion.Succeeded)
        {
            if (routeStrategy.RequiresModelBackedIterationPlanning)
            {
                throw new PrototypeIterationPlanLlmException(completion.FailureCode ?? "planning_analysis_llm_failed");
            }

            return fallback with
            {
                AnalysisSummary = AppendFailureNote(fallback.AnalysisSummary, completion.FailureCode)
            };
        }

        var parsed = TryParsePlanningContext(completion.JsonObjectText ?? completion.AssistantMessage, fallback);
        if (parsed is null && routeStrategy.RequiresModelBackedIterationPlanning)
        {
            throw new PrototypeIterationPlanLlmException("planning_analysis_parse_failed");
        }

        return parsed ?? fallback with
        {
            AnalysisSummary = AppendFailureNote(fallback.AnalysisSummary, "planning_analysis_parse_failed")
        };
    }

    private async Task<List<PrototypeIterationPlanGoalResult>> RefineRpgGoalsWithRequiredModelAsync(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        IterationPlanningContext planningContext,
        string message,
        IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold,
        string? regenerationGuidance,
        CancellationToken cancellationToken)
    {
        if (_llmRouteEngine is null)
        {
            throw new PrototypeIterationPlanLlmException("goal_plan_llm_client_missing");
        }

        var prompt = BuildRpgGoalRefinementPrompt(project, routeProfile, planningContext, message, scaffold, regenerationGuidance);
        var promptRoot = EnsureIterationPlanPromptWorkspace(project, "goal-plan");
        var options = PlanningCodexOptions with { OutputSchemaPath = GoalPlanSchemaPath };
        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                promptRoot,
                "goal-plan",
                PrototypeModelPolicy.Normalize("gpt-5.4"),
                prompt,
                options,
                project.AccountId,
                RequireJsonObject: true),
            cancellationToken);
        if (!completion.Succeeded)
        {
            throw new PrototypeIterationPlanLlmException(completion.FailureCode ?? "goal_plan_llm_failed");
        }

        var parsed = ParseRefinedRpgGoalPlan(completion.JsonObjectText ?? completion.AssistantMessage, scaffold);
        if (parsed.Count == 0)
        {
            throw new PrototypeIterationPlanLlmException("goal_plan_parse_failed");
        }

        return parsed;
    }

    private static List<PrototypeIterationPlanGoalResult> BuildRpgGoalsFromContext(
        string message,
        string sourceKind,
        PrototypeContractSnapshot prototypeContract,
        IterationPlanningContext planningContext,
        string? regenerationGuidance)
    {
        if (string.Equals(planningContext.LatestPrototypeStatus, "succeeded", StringComparison.OrdinalIgnoreCase))
        {
            return BuildRpgClosureGoals(planningContext, regenerationGuidance);
        }

        var goals = BuildGoals(message, sourceKind);
        return BuildRpgContractGoals(message, goals, prototypeContract);
    }

    private static List<PrototypeIterationPlanGoalResult> BuildRpgClosureGoals(IterationPlanningContext planningContext, string? regenerationGuidance)
    {
        return BuildNavigationFirstRpgClosureGoals(planningContext, regenerationGuidance);
    }

    private static List<PrototypeIterationPlanGoalResult> BuildNavigationFirstRpgClosureGoals(IterationPlanningContext planningContext, string? regenerationGuidance)
    {
        var guidance = string.IsNullOrWhiteSpace(regenerationGuidance)
            ? "The previous plan evaluation required Start Adventure to visible MapScene and stable movement before broader polish."
            : regenerationGuidance.Trim();
        var missingWinFail = planningContext.FieldCoverage.Any(item => item.Field == "win_fail_conditions" && !string.Equals(item.Status, "completed", StringComparison.OrdinalIgnoreCase));
        var missingRewards = planningContext.FieldCoverage.Any(item => item.Field == "reward_loop" && !string.Equals(item.Status, "completed", StringComparison.OrdinalIgnoreCase));
        var ruleCoverage = missingWinFail
            ? " Keep 15-battle victory and any-loss defeat visible in later validation instead of hiding them in final acceptance."
            : string.Empty;
        var rewardCoverage = missingRewards
            ? " Treat reward 3-choice understandability as an independent runtime proof."
            : string.Empty;

        return
        [
            new PrototypeIterationPlanGoalResult(
                1,
                "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry",
                $"Resolve the first RPG route blocker as one converged navigation step: the real Start Adventure entry must open a visible MapScene, show the player on the map using the runtime map/player assets, prove sustained controllable movement, and expose the first encounter entry from actual map traversal before any battle, reward, or polish work is mixed in. Guidance: {TrimForHint(guidance, 180)}",
                "Pass only when Start Adventure opens a visible RPG MapScene, runtime evidence proves the player can move continuously and controllably on that map, map/player asset usage is visible, and actual traversal exposes a clear first encounter entry.",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                2,
                "RPG Step 2: BattleScene loop validation",
                "Validate one readable battle after encounter entry, including enemy asset presentation, battle feedback, attack resolution, victory or defeat settlement, and battle-side failure feedback. Do not include reward selection in this step.",
                "Pass only when BattleScene can complete one readable battle, show enemy asset usage, and show clear settlement feedback.",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                3,
                "RPG Step 3: reward 3-choice and return-to-map validation",
                $"Validate the reward loop independently: victory should show three understandable reward choices, choosing one should change visible state, and the flow should return to MapScene for another loop.{rewardCoverage}",
                "Pass only when reward 3-choice, visible state change, player understanding evidence, and return-to-map loop are all proven.",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                4,
                "RPG Step 4: main loop scene switching validation",
                "After reward and return-to-map behavior are proven, validate the main first-loop scene switching chain end to end: Start Adventure, visible MapScene, encounter entry, BattleScene, reward selection, and return to MapScene.",
                "Pass only when the main prototype scene switching proof covers the full first RPG loop through reward and return-to-map.",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                5,
                "RPG Step 5: win/fail visibility and readability validation",
                $"Make the user-facing RPG rules clear and verify they match gameplay feedback: 15 battle wins mean victory, any battle loss means game loss, and key encounter rules are visible enough for the player to understand.{ruleCoverage}",
                "Pass only when 15-battle victory, any-loss defeat, and encounter rule feedback are visibly understandable and consistent with gameplay.",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                6,
                "RPG Final Step: full playable prototype acceptance",
                "Run final acceptance only after the previous runtime proofs exist, covering Start Adventure, visible MapScene, stable movement, encounter entry, BattleScene, reward 3-choice, return-to-map, win/fail visibility, project contract traceability, and Godot validation evidence.",
                "Pass only when the current RPG prototype is playable end-to-end and all required runtime proofs, map/player/enemy asset usage, user-facing rules, project contract fields, and final acceptance evidence are complete.",
                "pending")
        ];
    }

    private static string BuildPlanSummary(int goalCount, IterationPlanningContext planningContext)
    {
        var prototypeStatus = string.IsNullOrWhiteSpace(planningContext.LatestPrototypeStatus)
            ? "unknown"
            : planningContext.LatestPrototypeStatus;
        var coverage = planningContext.DraftCoveragePercent;
        return $"已基于当前原型状态与需求覆盖分析生成 {goalCount} 个迭代目标。当前原型状态：{prototypeStatus}；表单覆盖率：{coverage}%。请先执行目标 1，再逐步推进后续目标。";
    }

    private static string BuildFallbackAnalysisSummary(RunSnapshot? latestPrototypeRun, RunSnapshot? latestSuccessfulPrototypeRun, ProjectPrototypeDraftSnapshot? draft)
    {
        var prototypeStatus = latestSuccessfulPrototypeRun is not null
            ? "已存在成功原型，可优先做收敛型迭代。"
            : latestPrototypeRun is not null
                ? $"最近一次原型状态为 {latestPrototypeRun.Status}，仍需保留基础收敛步骤。"
                : "尚未发现已完成的原型运行记录。";
        var draftSummary = draft is null
            ? "当前没有草稿覆盖率分析。"
            : $"最近草稿覆盖率约为 {draft.CoveragePercent}%。";
        return $"{prototypeStatus}{draftSummary}";
    }

    private static string AppendFailureNote(string summary, string? failureCode)
    {
        return string.IsNullOrWhiteSpace(failureCode)
            ? summary
            : $"{summary} 模型分析降级为本地规则，原因：{failureCode}。";
    }

    private static string BuildPlanningAnalysisPrompt(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        PrototypeContractSnapshot prototypeContract,
        IterationPlanningContext fallback,
        ProjectPrototypeDraftSnapshot? draft,
        RunSnapshot? latestPrototypeRun,
        RunSnapshot? latestSuccessfulPrototypeRun)
    {
        var draftJson = draft is null
            ? "{}"
            : JsonSerializer.Serialize(new
            {
                draft.PrototypeSlug,
                draft.Hypothesis,
                draft.CorePlayerFantasy,
                draft.MinimumPlayableLoop,
                SuccessCriteria = DeserializeJsonArray(draft.SuccessCriteriaJson),
                draft.GameFeature,
                draft.CoreGameplayLoop,
                draft.WinFailConditions,
                draft.CoveragePercent,
                draft.CoverageSummary,
                CoverageMissingTopics = DeserializeJsonArray(draft.CoverageMissingTopicsJson)
            });
        var runJson = JsonSerializer.Serialize(new
        {
            latest_run_status = latestPrototypeRun?.Status,
            latest_run_summary = ReadCompletionSummaryFromRun(latestPrototypeRun),
            latest_successful_status = latestSuccessfulPrototypeRun?.Status,
            latest_successful_summary = ReadCompletionSummaryFromRun(latestSuccessfulPrototypeRun),
            fallback_analysis = fallback.AnalysisSummary
        });

        return $"""
            You are analyzing a hosted Godot prototype after prototype creation has already run.
            Output JSON only. Do not explain. Do not use Markdown.
            Return these keys only:
            analysisSummary, fieldCoverage.

            fieldCoverage must be an array of objects with:
            field, status, evidence, missingReason

            Rules:
            - Use only the data provided in this prompt.
            - Do not read files, inspect the repository, call tools, or ask for more context.
            - status must be one of completed, partial, missing.
            - Judge completion against the current prototype result, not only the form text.
            - Focus on prototype-form fields, map/battle/reward loop, and win/fail expectations for RPG.
            - Keep evidence and missingReason short and browser-safe.

            Project:
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}
            - RouteSkillId: {fallback.RouteSkillId}
            - TemplateId: {fallback.TemplateId}
            - GameTypeProfileId: {routeProfile.ProfileId}
            - RouteSetId: {routeProfile.RouteSetId}
            - PromptProtocolId: {routeProfile.PromptProtocolId}
            - PlannerId: {routeProfile.PlannerId}

            Source message:
            {fallback.SourceMessage}

            Prototype contract:
            {TrimForPrompt(prototypeContract.Json)}

            Draft/form snapshot:
            {draftJson}

            Prototype run snapshot:
            {runJson}

            Prototype route state excerpt:
            {fallback.PrototypeStateExcerpt}
            """;
    }

    private static string BuildRpgGoalRefinementPrompt(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        IterationPlanningContext planningContext,
        string message,
        IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold,
        string? regenerationGuidance)
    {
        var analysisJson = JsonSerializer.Serialize(new
        {
            planningContext.AnalysisSummary,
            planningContext.LatestPrototypeStatus,
            planningContext.LatestPrototypeCompletionSummary,
            planningContext.DraftCoveragePercent,
            planningContext.DraftCoverageSummary,
            planningContext.TemplateId,
            fieldCoverage = planningContext.FieldCoverage
        });
        var scaffoldJson = JsonSerializer.Serialize(scaffold.Select(goal => new
        {
            goal.GoalIndex,
            goal.Title,
            goal.Description,
            goal.AcceptanceHint
        }).ToArray());

        return $"""
            You are refining a server-generated iteration plan for an RPG Godot prototype.
            Output JSON only. Do not explain. Do not use Markdown.
            Return these keys only:
            goals

            goals must be an array with the exact same number of items as the scaffold, and each object must contain:
            title, description, acceptanceHint

            Rules:
            - Use only the data provided in this prompt.
            - Do not read files, inspect the repository, call tools, or ask for more context.
            - Do not generate a new plan from scratch.
            - Keep the exact scaffold order.
            - Keep every title exactly unchanged from the scaffold.
            - Only refine description and acceptanceHint so they better reflect the current prototype state, prototype-form coverage, and RPG route-skill contract.
            - If the prototype already succeeded once, keep the convergence/closure framing already present in the scaffold.
            - If some user fields are still only partial, mention the most important missing runtime proof in the relevant later steps.
            - Keep each goal narrow enough to execute independently.
            - Final step must remain full playable acceptance.
            - If regeneration guidance is provided, treat it as a hard constraint from the previous plan evaluation.
            - When regeneration guidance says the current blocker is Start Adventure, visible MapScene, stable movement, or encounter entry, goal 1 must remain focused on that blocker.

            Project:
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}
            - GameTypeProfileId: {routeProfile.ProfileId}
            - RouteSetId: {routeProfile.RouteSetId}
            - PromptProtocolId: {routeProfile.PromptProtocolId}
            - PlannerId: {routeProfile.PlannerId}

            Requested optimization:
            {message}

            Regeneration guidance from previous plan evaluation:
            {(string.IsNullOrWhiteSpace(regenerationGuidance) ? "none" : regenerationGuidance.Trim())}

            Planning analysis:
            {analysisJson}

            Goal scaffold that must be preserved:
            {scaffoldJson}
            """;
    }

    private static IterationPlanningContext? TryParsePlanningContext(string? assistantMessage, IterationPlanningContext fallback)
    {
        if (string.IsNullOrWhiteSpace(assistantMessage))
        {
            return null;
        }

        try
        {
            var json = LlmRouteEngine.ExtractFirstJsonObject(assistantMessage) ?? assistantMessage;
            using var document = JsonDocument.Parse(json);
            var root = document.RootElement;
            var summary = root.TryGetProperty("analysisSummary", out var summaryElement) && summaryElement.ValueKind == JsonValueKind.String
                ? summaryElement.GetString() ?? fallback.AnalysisSummary
                : fallback.AnalysisSummary;
            var coverage = root.TryGetProperty("fieldCoverage", out var coverageElement) && coverageElement.ValueKind == JsonValueKind.Array
                ? coverageElement.EnumerateArray().Select(item => new PlanningFieldCoverage(
                    item.TryGetProperty("field", out var fieldElement) && fieldElement.ValueKind == JsonValueKind.String ? fieldElement.GetString() ?? "" : "",
                    item.TryGetProperty("status", out var statusElement) && statusElement.ValueKind == JsonValueKind.String ? statusElement.GetString() ?? "missing" : "missing",
                    item.TryGetProperty("evidence", out var evidenceElement) && evidenceElement.ValueKind == JsonValueKind.String ? evidenceElement.GetString() : null,
                    item.TryGetProperty("missingReason", out var missingElement) && missingElement.ValueKind == JsonValueKind.String ? missingElement.GetString() : null))
                    .Where(item => !string.IsNullOrWhiteSpace(item.Field))
                    .ToArray()
                : fallback.FieldCoverage;
            return fallback with
            {
                AnalysisSource = "codex_exec",
                AnalysisSummary = summary,
                FieldCoverage = coverage.Count == 0 ? fallback.FieldCoverage : coverage
            };
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static List<PrototypeIterationPlanGoalResult> ParseGoalPlan(string? assistantMessage)
    {
        if (string.IsNullOrWhiteSpace(assistantMessage))
        {
            return [];
        }

        try
        {
            var json = LlmRouteEngine.ExtractFirstJsonObject(assistantMessage) ?? assistantMessage;
            using var document = JsonDocument.Parse(json);
            if (!document.RootElement.TryGetProperty("goals", out var goalsElement) || goalsElement.ValueKind != JsonValueKind.Array)
            {
                return [];
            }

            var goals = new List<PrototypeIterationPlanGoalResult>();
            var index = 1;
            foreach (var item in goalsElement.EnumerateArray())
            {
                var title = item.TryGetProperty("title", out var titleElement) && titleElement.ValueKind == JsonValueKind.String
                    ? titleElement.GetString()
                    : null;
                var description = item.TryGetProperty("description", out var descriptionElement) && descriptionElement.ValueKind == JsonValueKind.String
                    ? descriptionElement.GetString()
                    : null;
                var acceptance = item.TryGetProperty("acceptanceHint", out var acceptanceElement) && acceptanceElement.ValueKind == JsonValueKind.String
                    ? acceptanceElement.GetString()
                    : null;
                if (string.IsNullOrWhiteSpace(title) || string.IsNullOrWhiteSpace(description) || string.IsNullOrWhiteSpace(acceptance))
                {
                    continue;
                }

                goals.Add(new PrototypeIterationPlanGoalResult(index++, title.Trim(), description.Trim(), acceptance.Trim(), "pending"));
            }

            return goals;
        }
        catch (JsonException)
        {
            return [];
        }
    }

    private static List<PrototypeIterationPlanGoalResult> ParseRefinedRpgGoalPlan(
        string? assistantMessage,
        IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold)
    {
        var parsed = ParseGoalPlan(assistantMessage);
        if (parsed.Count != scaffold.Count)
        {
            return [];
        }

        var refined = new List<PrototypeIterationPlanGoalResult>(scaffold.Count);
        for (var index = 0; index < scaffold.Count; index++)
        {
            var expected = scaffold[index];
            var actual = parsed[index];
            if (!string.Equals(actual.Title, expected.Title, StringComparison.Ordinal))
            {
                return [];
            }

            var actualText = string.Join(" ", actual.Description, actual.AcceptanceHint);
            if (WeakensRpgScaffoldContract(expected, actualText))
            {
                return [];
            }

            refined.Add(new PrototypeIterationPlanGoalResult(
                expected.GoalIndex,
                expected.Title,
                string.IsNullOrWhiteSpace(actual.Description) ? expected.Description : actual.Description,
                string.IsNullOrWhiteSpace(actual.AcceptanceHint) ? expected.AcceptanceHint : actual.AcceptanceHint,
                "pending"));
        }

        return refined;
    }

    private static bool WeakensRpgScaffoldContract(PrototypeIterationPlanGoalResult expected, string actualText)
    {
        if (string.IsNullOrWhiteSpace(actualText))
        {
            return false;
        }

        foreach (var group in RequiredRpgScaffoldTerms(expected.Title))
        {
            if (!ContainsAny(actualText, group))
            {
                return true;
            }
        }

        return false;
    }

    private static IEnumerable<string[]> RequiredRpgScaffoldTerms(string expectedText)
    {
        if (ContainsAny(expectedText, "Start Adventure", "visible MapScene", "stable movement", "encounter entry"))
        {
            yield return ["Start Adventure"];
            yield return ["visible MapScene", "visible RPG MapScene", "visible map", "non-empty visible MapScene"];
            yield return ["stable movement", "controllable movement", "move continuously", "movement"];
            yield return ["encounter entry", "first encounter", "encounter"];
            yield return ["asset", "assets", "map/player", "map/player/enemy", "map/player runtime"];
        }

        if (ContainsAny(expectedText, "BattleScene loop", "BattleScene"))
        {
            yield return ["BattleScene"];
            yield return ["settlement", "battle feedback", "complete one readable battle"];
            yield return ["enemy asset", "enemy assets", "enemy asset usage", "enemy"];
        }

        if (ContainsAny(expectedText, "reward 3-choice", "return-to-map"))
        {
            yield return ["reward", "3-choice", "three reward", "three choices"];
            yield return ["return-to-map", "return to MapScene", "return to the map"];
        }

        if (ContainsAny(expectedText, "main loop scene switching", "scene switching"))
        {
            yield return ["scene switching", "scene switch", "switching"];
            yield return ["Start Adventure"];
            yield return ["return-to-map", "return to MapScene", "return to the map"];
        }

        if (ContainsAny(expectedText, "win/fail", "victory", "failure"))
        {
            yield return ["win/fail", "victory", "failure", "defeat"];
            yield return ["encounter", "rule"];
        }

        if (ContainsAny(expectedText, "full playable prototype acceptance", "Final Step"))
        {
            yield return ["full playable", "full RPG playable", "full prototype", "final acceptance", "playable end-to-end", "end-to-end"];
            yield return ["project contract", "contract-specific", "input_traceability", "contract fields"];
            yield return ["asset", "assets", "map/player/enemy"];
        }
    }

    private static PlanningFieldCoverage[] BuildDeterministicFieldCoverage(ProjectPrototypeDraftSnapshot? draft)
    {
        if (draft is null)
        {
            return
            [
                new("hypothesis", "missing", null, "还没有导入或保存需求表单。"),
                new("core_player_fantasy", "missing", null, "还没有导入或保存需求表单。"),
                new("minimum_playable_loop", "missing", null, "还没有导入或保存需求表单。"),
                new("success_criteria", "missing", null, "还没有导入或保存需求表单。"),
                new("game_feature", "missing", null, "还没有导入或保存需求表单。"),
                new("core_gameplay_loop", "missing", null, "还没有导入或保存需求表单。"),
                new("win_fail_conditions", "missing", null, "还没有导入或保存需求表单。"),
                new("reward_loop", "missing", null, "无法从需求表单确认奖励回路。")
            ];
        }

        return
        [
            BuildFieldCoverage("hypothesis", draft.Hypothesis),
            BuildFieldCoverage("core_player_fantasy", draft.CorePlayerFantasy),
            BuildFieldCoverage("minimum_playable_loop", draft.MinimumPlayableLoop),
            BuildFieldCoverage("success_criteria", string.Join(" / ", DeserializeJsonArray(draft.SuccessCriteriaJson))),
            BuildFieldCoverage("game_feature", draft.GameFeature),
            BuildFieldCoverage("core_gameplay_loop", draft.CoreGameplayLoop),
            BuildFieldCoverage("win_fail_conditions", draft.WinFailConditions),
            BuildFieldCoverage("reward_loop", draft.CoreGameplayLoop)
        ];
    }

    private static PlanningFieldCoverage BuildFieldCoverage(string field, string? value)
    {
        return string.IsNullOrWhiteSpace(value)
            ? new PlanningFieldCoverage(field, "missing", null, "需求表单对应字段为空。")
            : new PlanningFieldCoverage(field, "partial", TrimForHint(value, 60), null);
    }

    private static string? ReadCompletionSummaryFromRun(RunSnapshot? run)
    {
        if (run is null || string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            if (!document.RootElement.TryGetProperty("prototype_completion", out var completionElement) ||
                completionElement.ValueKind != JsonValueKind.Object ||
                !completionElement.TryGetProperty("completion_summary", out var summaryElement) ||
                summaryElement.ValueKind != JsonValueKind.String)
            {
                return null;
            }

            return summaryElement.GetString();
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string[] DeserializeJsonArray(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return [];
        }

        try
        {
            return JsonSerializer.Deserialize<string[]>(json) ?? [];
        }
        catch (JsonException)
        {
            return [];
        }
    }

    private static PrototypeIterationPlanningAnalysisResult ToPlanningAnalysisResult(IterationPlanningContext planningContext)
    {
        return new PrototypeIterationPlanningAnalysisResult(
            planningContext.AnalysisSource,
            planningContext.AnalysisSummary,
            planningContext.LatestPrototypeStatus,
            planningContext.LatestPrototypeCompletionSummary,
            planningContext.DraftCoveragePercent,
            planningContext.DraftCoverageSummary,
            planningContext.TemplateId,
            planningContext.FieldCoverage.Select(item => new PrototypeIterationPlanningFieldResult(
                item.Field,
                item.Status,
                item.Evidence,
                item.MissingReason)).ToArray());
    }

    private static PrototypeIterationPlanningAnalysisResult? TryReadPlanningAnalysisFromState(string stateText)
    {
        if (string.IsNullOrWhiteSpace(stateText))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(stateText);
            if (!document.RootElement.TryGetProperty("planning_analysis", out var analysisElement))
            {
                return null;
            }

            var source = analysisElement.TryGetProperty("analysisSource", out var sourceElement) && sourceElement.ValueKind == JsonValueKind.String
                ? sourceElement.GetString() ?? ""
                : "";
            var summary = analysisElement.TryGetProperty("analysisSummary", out var summaryElement) && summaryElement.ValueKind == JsonValueKind.String
                ? summaryElement.GetString() ?? ""
                : "";
            var latestStatus = analysisElement.TryGetProperty("latestPrototypeStatus", out var statusElement) && statusElement.ValueKind == JsonValueKind.String
                ? statusElement.GetString() ?? ""
                : "";
            var latestCompletion = analysisElement.TryGetProperty("latestPrototypeCompletionSummary", out var completionElement) && completionElement.ValueKind == JsonValueKind.String
                ? completionElement.GetString()
                : null;
            var draftCoveragePercent = analysisElement.TryGetProperty("draftCoveragePercent", out var coverageElement) && coverageElement.ValueKind == JsonValueKind.Number
                ? coverageElement.GetInt32()
                : 0;
            var draftCoverageSummary = analysisElement.TryGetProperty("draftCoverageSummary", out var coverageSummaryElement) && coverageSummaryElement.ValueKind == JsonValueKind.String
                ? coverageSummaryElement.GetString()
                : null;
            var templateId = analysisElement.TryGetProperty("templateId", out var templateElement) && templateElement.ValueKind == JsonValueKind.String
                ? templateElement.GetString()
                : null;
            var fieldCoverage = analysisElement.TryGetProperty("fieldCoverage", out var fieldElement) && fieldElement.ValueKind == JsonValueKind.Array
                ? fieldElement.EnumerateArray().Select(item => new PrototypeIterationPlanningFieldResult(
                    item.TryGetProperty("field", out var fieldName) && fieldName.ValueKind == JsonValueKind.String ? fieldName.GetString() ?? "" : "",
                    item.TryGetProperty("status", out var fieldStatus) && fieldStatus.ValueKind == JsonValueKind.String ? fieldStatus.GetString() ?? "missing" : "missing",
                    item.TryGetProperty("evidence", out var evidenceElement) && evidenceElement.ValueKind == JsonValueKind.String ? evidenceElement.GetString() : null,
                    item.TryGetProperty("missingReason", out var missingReasonElement) && missingReasonElement.ValueKind == JsonValueKind.String ? missingReasonElement.GetString() : null))
                    .Where(item => !string.IsNullOrWhiteSpace(item.Field))
                    .ToArray()
                : [];

            return new PrototypeIterationPlanningAnalysisResult(
                source,
                summary,
                latestStatus,
                latestCompletion,
                draftCoveragePercent,
                draftCoverageSummary,
                templateId,
                fieldCoverage);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string? NormalizeGameType(string? gameTypeSource)
    {
        if (string.IsNullOrWhiteSpace(gameTypeSource))
        {
            return null;
        }

        var lowered = gameTypeSource.Trim().ToLowerInvariant();
        if (lowered.Contains("rpg", StringComparison.Ordinal) ||
            lowered.Contains("角色扮演", StringComparison.Ordinal) ||
            lowered.Contains("勇者斗恶龙", StringComparison.Ordinal))
        {
            return "rpg";
        }

        return lowered;
    }

    private static string TrimForPrompt(string value)
    {
        var trimmed = value.Trim();
        return trimmed.Length <= 5000 ? trimmed : trimmed[..5000];
    }

    private static string AppendAttachmentContext(string message, string attachmentContext)
    {
        if (string.IsNullOrWhiteSpace(attachmentContext) || attachmentContext == "无。")
        {
            return message;
        }

        return $"""
            {message}

            本次导入 TXT 参考资料：
            {attachmentContext}
            """;
    }

    private static string BuildAttachmentPromptBlock(IReadOnlyList<TextAttachment>? attachments)
    {
        if (attachments is null || attachments.Count == 0)
        {
            return "无。";
        }

        var usable = attachments
            .Take(MaxTextAttachments)
            .Where(item => !string.IsNullOrWhiteSpace(item.Content))
            .Select((item, index) =>
            {
                var fileName = string.IsNullOrWhiteSpace(item.FileName) ? $"attachment-{index + 1}.txt" : item.FileName.Trim();
                var content = item.Content!.Trim();
                if (content.Length > MaxTextAttachmentChars)
                {
                    content = content[..MaxTextAttachmentChars] + "\n[truncated]";
                }

                return $"[{index + 1}] {fileName}\n{content}";
            })
            .ToArray();

        return usable.Length == 0 ? "无。" : string.Join("\n\n", usable);
    }

    public async Task<PrototypeIterationPlanDetails?> GetLatestAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
        if (details is null)
        {
            return null;
        }

        var stateText = _routeStateWriter.ReadLatestIterationPlanState(project);
        return new PrototypeIterationPlanDetails(
            details.Session,
            details.Goals,
            details.GoalRuns,
            details.LatestEvaluation,
            TryReadPlanningAnalysisFromState(stateText));
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
            var result = new PrototypeIterationPlanEvaluationResult(
                "should_refine_plan",
                "当前项目还没有迭代计划。",
                "还没有可执行的目标列表，无法判断是否适合直接进入下一目标。",
                "请先生成迭代计划。",
                null);
            return result;
        }

        var goals = details.Goals.OrderBy(goal => goal.GoalIndex).ToArray();
        if (goals.Length == 0)
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "should_refine_plan",
                "当前计划没有有效目标。",
                "计划会话存在，但没有生成任何可执行目标。",
                "请重新生成迭代计划。",
                BuildRegenerationPrompt(prototypeProgress, details)));
        }

        if (goals.Any(goal => string.Equals(goal.Status, "needs_fix", StringComparison.Ordinal)))
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "blocked_by_current_goal",
                "当前计划里有需要先修复的目标。",
                "至少一个目标已经被标记为 needs_fix，继续执行后续目标只会放大不确定性。",
                "先修复当前目标，再决定是否继续后续目标。",
                null));
        }

        if (goals.Any(goal => string.Equals(goal.Status, "running", StringComparison.Ordinal)))
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "blocked_by_current_goal",
                "当前计划里有进行中的目标。",
                "已有目标正在执行，暂时不适合重新拆解或继续触发下一目标。",
                "等待当前目标完成后再刷新判断。",
                null));
        }

        var pendingGoals = goals.Where(goal => string.Equals(goal.Status, "pending", StringComparison.Ordinal)).ToArray();
        if (pendingGoals.Length == 0)
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "ready_to_execute",
                "当前计划已经没有待执行目标。",
                "所有目标都已完成或已停止，不需要继续执行下一目标。",
                "如果还有新需求，请基于新的优化目标重新生成计划。",
                null));
        }

        var routeProfile = PrototypeRouteSkillPolicy.ResolveProfile(project);
        var routeStrategy = GameTypeRouteStrategies.Resolve(project, routeProfile);
        if (routeStrategy.UsesSpecializedPlanEvaluation &&
            string.Equals(routeStrategy.GameTypeId, "rpg", StringComparison.OrdinalIgnoreCase))
        {
            var rpgPlanningAnalysis = TryReadPlanningAnalysisFromState(_routeStateWriter.ReadLatestIterationPlanState(project));
            var rpgPlanIssue = FindRpgPlanContractIssue(goals, rpgPlanningAnalysis, details.Session.SourceMessage);
            if (rpgPlanIssue is not null)
            {
                return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                    "should_refine_plan",
                    "当前 RPG 迭代计划缺少类型路由要求的场景、顺序或验收覆盖。",
                    rpgPlanIssue,
                    "请先按 RPG 类型路由重新生成迭代计划：Start Adventure 到可见 MapScene 与稳定移动必须作为第一目标，之后再拆 BattleScene、奖励回地图、主循环切换、胜负可读性和最终验收。",
                    BuildRpgRegenerationPrompt(details)));
            }

            var llmEvaluation = await EvaluateRpgPlanWithRequiredModelAsync(project, routeProfile, details, prototypeProgress, cancellationToken);
            if (IsStaleRpgBoundaryMismatchEvaluation(llmEvaluation, goals))
            {
                llmEvaluation = BuildRpgRouteGuardAcceptedEvaluation(llmEvaluation);
            }

            return await PersistEvaluationAsync(details, llmEvaluation, cancellationToken);
        }

        var firstPending = pendingGoals[0];
        var firstGoalLooksTooLarge = !IsRecognizedSmallGoal(firstPending) && (LooksTooBroad(firstPending.Title) || LooksTooBroad(firstPending.Description));
        var overallLooksLarge = goals.Length <= 3 && goals.Any(goal => LooksTooBroad(goal.Description));
        var recommendedButStillBroad = string.Equals(prototypeProgress?.NextStepEvaluation, "recommended", StringComparison.OrdinalIgnoreCase)
                                       && goals.Length <= 3
                                       && firstGoalLooksTooLarge;

        if (firstGoalLooksTooLarge || overallLooksLarge || recommendedButStillBroad)
        {
            return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
                "should_refine_plan",
                "当前计划可以用，但第一目标仍然偏大，直接执行风险较高。",
                $"当前第一个待执行目标“{firstPending.Title}”混合了多个连续实现点，更像总任务而不是单次小目标。",
                "建议先重生成一次更细的迭代计划，再执行下一目标。",
                BuildRegenerationPrompt(prototypeProgress, details)));
        }

        return await PersistEvaluationAsync(details, new PrototypeIterationPlanEvaluationResult(
            "ready_to_execute",
            "当前计划适合直接执行下一目标。",
            $"当前待执行目标“{firstPending.Title}”边界相对清楚，没有发现明显的 needs_fix 或过粗拆分信号。",
            "可以直接点击“执行下一目标”。",
            null));
    }

    private async Task<PrototypeIterationPlanEvaluationResult> EvaluateRpgPlanWithRequiredModelAsync(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        ProjectIterationSessionDetails details,
        PrototypeWorkflowProgress? prototypeProgress,
        CancellationToken cancellationToken)
    {
        if (_llmRouteEngine is null)
        {
            return BuildLlmFailedEvaluation("plan_evaluation_llm_client_missing");
        }

        var planningAnalysis = TryReadPlanningAnalysisFromState(_routeStateWriter.ReadLatestIterationPlanState(project));
        var promptRoot = EnsureIterationPlanPromptWorkspace(project, "plan-evaluation");
        var options = PlanningCodexOptions with { OutputSchemaPath = EvaluationSchemaPath };
        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                promptRoot,
                "plan-evaluation",
                PrototypeModelPolicy.Normalize("gpt-5.4"),
                BuildRpgPlanEvaluationPrompt(project, routeProfile, details, prototypeProgress, planningAnalysis),
                options,
                project.AccountId,
                RequireJsonObject: true),
            cancellationToken);
        if (!completion.Succeeded)
        {
            return BuildLlmFailedEvaluation(completion.FailureCode ?? "plan_evaluation_llm_failed");
        }

        var parsed = ParseModelEvaluation(completion.JsonObjectText ?? completion.AssistantMessage);
        if (parsed is null)
        {
            return BuildLlmFailedEvaluation("plan_evaluation_parse_failed");
        }

        return parsed;
    }

    private static List<PrototypeIterationPlanGoalResult> BuildGoals(string message, string sourceKind)
    {
        var refinedGoals = TryBuildRefinedGoals(message, sourceKind);
        if (refinedGoals.Count > 0)
        {
            return refinedGoals;
        }

        var normalized = message.Replace("\r", "\n");
        var segments = ExtractStructuredGoals(normalized);
        var usedStructuredGoals = segments.Count > 0;
        if (segments.Count == 0)
        {
            segments = SplitRegex
                .Split(normalized)
                .Select(value => value.Trim())
                .Where(IsMeaningfulGoalSegment)
                .Select(NormalizeGoalSegment)
                .Where(IsMeaningfulGoalSegment)
                .Distinct(StringComparer.Ordinal)
                .ToList();
        }

        if (segments.Count == 0)
        {
            segments.Add(NormalizeGoalSegment(message));
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
                $"完成并验证：{TrimForHint(segment)}。",
                "pending"));
            index++;
        }

        while (!usedStructuredGoals && goals.Count < 3)
        {
            var title = goals.Count switch
            {
                0 => "目标 1：补齐当前核心缺口",
                1 => "目标 2：收敛关键交互链路",
                _ => "目标 3：完成一次可验证检查"
            };
            var description = goals.Count switch
            {
                0 => "先补齐当前最影响可玩的核心能力，并让结果可见。",
                1 => "把与该能力直接相关的关键交互链路连通。",
                _ => "补一轮最小验证，确认这次改动已经可用。"
            };
            goals.Add(new PrototypeIterationPlanGoalResult(
                goals.Count + 1,
                title,
                description,
                $"完成并验证：{title}。",
                "pending"));
        }

        return goals;
    }

    private static List<PrototypeIterationPlanGoalResult> BuildRpgContractGoals(
        string message,
        List<PrototypeIterationPlanGoalResult> existingGoals,
        PrototypeContractSnapshot prototypeContract)
    {
        var hint = TrimForHint(message, 96);
        var contractInstruction = BuildContractGoalInstruction(prototypeContract);
        return
        [
            new PrototypeIterationPlanGoalResult(
                1,
                "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry",
                $"Create and validate the player's real RPG entry path first: clicking Start Adventure must open a non-empty visible MapScene, show map/player runtime assets, support stable movement, and expose the first encounter entry from actual traversal. {contractInstruction} Source request: {hint}",
                $"Pass only when Start Adventure opens a visible RPG MapScene, map/player asset usage is visible, runtime evidence proves stable movement, and traversal exposes first encounter entry. {contractInstruction}",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                2,
                "RPG Step 2: BattleScene loop validation",
                $"Create and validate a dedicated RPG BattleScene after encounter entry. This step must focus on enemy asset presentation, one readable battle, action resolution, victory/defeat settlement, and battle UI feedback. {contractInstruction}",
                $"Pass only when the project contains a valid RPG BattleScene, enemy asset usage is visible, and one battle can independently reach settlement. {contractInstruction}",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                3,
                "RPG Step 3: reward 3-choice and return-to-map validation",
                $"Validate the RPG reward flow as its own step after battle settlement: victory leads to three reward choices, choosing one changes visible state, and the player returns to the map loop. {contractInstruction}",
                $"Pass only when reward 3-choice selection, state change, and return-to-map loop are all verified. {contractInstruction}",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                4,
                "RPG Step 4: main loop scene switching validation",
                $"Create and validate the main RPG prototype scene that connects Start Adventure, MapScene, encounter entry, BattleScene, reward selection, and return-to-map after each individual scene proof exists. {contractInstruction}",
                $"Pass only when the main prototype scene switching proof covers the full first RPG loop through reward and return-to-map. {contractInstruction}",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                5,
                "RPG Step 5: win/fail visibility and readability validation",
                $"Make the user-facing RPG rules clear and verify they match gameplay feedback, including victory, failure, encounter, and important contract-specific loop rules. {contractInstruction}",
                $"Pass only when victory, failure, encounter rule feedback, and project-specific RPG loop rules are visibly understandable and consistent with gameplay. {contractInstruction}",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                6,
                "RPG Final Step: full playable prototype acceptance",
                $"Run the RPG type-skill final acceptance across the complete prototype: required RPG scenes, actual map/player/enemy asset usage in the current prototype scenes, main menu to prototype navigation, Main.tscn default-hidden VBox/Overlays/ScreenRoot SOP, Start Adventure to visible map, battle entry, reward return-to-map, Godot build, prototype scene smoke, and package readiness. {contractInstruction}",
                $"Pass only when the full RPG playable prototype is accepted end-to-end: MapScene, BattleScene, reward return-to-map flow, actual Map/Player/Enemy asset usage in current scenes, main menu navigation, Main.tscn root-level VBox/Overlays/ScreenRoot all default to visible = false, Start Adventure visible-map validation, Godot build, prototype scene smoke, package readiness, and all project-specific prototype contract fields pass.",
                "pending")
        ];
    }

    private static List<PrototypeIterationPlanGoalResult> AppendGenericFinalAcceptanceGoal(
        List<PrototypeIterationPlanGoalResult> goals,
        string message,
        PrototypeContractSnapshot prototypeContract)
    {
        if (goals.Any(IsFinalAcceptanceGoal))
        {
            return goals;
        }

        var nextIndex = goals.Count == 0 ? 1 : goals.Max(goal => goal.GoalIndex) + 1;
        goals.Add(new PrototypeIterationPlanGoalResult(
            nextIndex,
            "Final Step: full playable prototype acceptance",
            $"Run the generic prototype final acceptance across the complete playable slice, using the available prototype skill contract and the project-specific prototype contract as checklist sources. {BuildContractGoalInstruction(prototypeContract)} Source request: {TrimForHint(message, 96)}",
            $"Pass only when the complete playable prototype passes platform acceptance: project build, default prototype scene smoke, main menu entry, package readiness, no pending or needs-fix iteration goals, and all project-specific prototype contract fields pass. {BuildContractGoalInstruction(prototypeContract)}",
            "pending"));
        return goals;
    }

    private static string BuildContractGoalInstruction(PrototypeContractSnapshot prototypeContract)
    {
        return string.IsNullOrWhiteSpace(prototypeContract.Json)
            ? "If the project prototype contract is missing, do not invent form values; mark the goal needs_fix until the contract is restored."
            : "Use the project prototype contract and input_traceability as hard acceptance input; every non-empty user field must map to a goal, validation check, or explicit needs_fix blocker, and user form values override type template defaults.";
    }

    private static bool IsFinalAcceptanceGoal(PrototypeIterationPlanGoalResult goal)
    {
        var text = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint).ToLowerInvariant();
        return text.Contains("final", StringComparison.Ordinal) &&
               (text.Contains("acceptance", StringComparison.Ordinal) ||
                text.Contains("full playable", StringComparison.Ordinal) ||
                text.Contains("全量", StringComparison.Ordinal) ||
                text.Contains("交付验收", StringComparison.Ordinal));
    }

    private static string? FindRpgPlanContractIssue(
        ProjectIterationGoalSnapshot[] goals,
        PrototypeIterationPlanningAnalysisResult? planningAnalysis,
        string? sourceMessage)
    {
        var combined = string.Join("\n", goals.Select(goal => string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint))).ToLowerInvariant();
        var missing = new List<string>();
        var boundaryIssue = FindRpgPlanAcceptanceBoundaryIssue(goals);
        if (boundaryIssue is not null)
        {
            return boundaryIssue;
        }

        if (!ContainsAny(combined, "asset", "assets", "material", "materials", "sprite", "sprites", "tileset", "ui", "hud", "素材", "美术", "界面"))
        {
            missing.Add("map/player/enemy asset usage validation coverage");
        }

        if (!ContainsAny(combined, "mapscene", "map scene", "mapscene.tscn", "地图场景") ||
            !ContainsAny(combined, "start adventure", "visible map", "visible-map", "opens a valid visible", "可见地图", "开始冒险"))
        {
            missing.Add("Start Adventure to visible MapScene first step");
        }

        if (!ContainsAny(combined, "battlescene", "battle scene", "battlescene.tscn", "战斗场景"))
        {
            missing.Add("dedicated BattleScene step");
        }

        var hasMainScene = ContainsAny(combined, "main prototype", "main scene", "prototype scene", "main loop", "first-loop", "主原型", "主场景", "主循环");
        var hasSwitching = ContainsAny(combined, "scene switching", "scene switch", "switch into", "return path", "main loop scene switching", "场景切换", "跳转");
        if (!hasMainScene || !hasSwitching)
        {
            missing.Add("main loop scene switching step");
        }

        if (!ContainsAny(combined, "reward", "3-choice", "three reward", "three choices", "return-to-map", "return to the map", "奖励", "三选一", "3 选 1", "返回地图"))
        {
            missing.Add("reward loop and return-to-map step");
        }

        if (!ContainsAny(combined, "final acceptance", "full playable prototype acceptance", "full playable", "package readiness", "交付验收", "全量验收", "最终验收") ||
            !ContainsAny(combined, "start adventure", "visible map", "visible-map", "可见地图", "开始冒险"))
        {
            missing.Add("final full playable acceptance step with Start Adventure visible-map validation");
        }

        var explicitContractRuleIssues = FindMissingExplicitContractRules(combined, planningAnalysis, sourceMessage);
        missing.AddRange(explicitContractRuleIssues);

        if (missing.Count == 0)
        {
            return null;
        }

        return $"Missing RPG contract steps: {string.Join(", ", missing)}.";
    }

    private static List<string> FindMissingExplicitContractRules(
        string combined,
        PrototypeIterationPlanningAnalysisResult? planningAnalysis,
        string? sourceMessage)
    {
        var missing = new List<string>();
        var evidenceTexts = new List<(string Field, string Evidence)>();
        if (planningAnalysis is not null && planningAnalysis.FieldCoverage.Count > 0)
        {
            foreach (var item in planningAnalysis.FieldCoverage)
            {
                if (!string.Equals(item.Status, "completed", StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(item.Status, "partial", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                var evidence = (item.Evidence ?? string.Empty).Trim();
                if (!string.IsNullOrWhiteSpace(evidence))
                {
                    evidenceTexts.Add((((item.Field ?? string.Empty).Trim().ToLowerInvariant()), evidence));
                }
            }
        }

        if (!string.IsNullOrWhiteSpace(sourceMessage))
        {
            evidenceTexts.Add(("source_message", sourceMessage.Trim()));
        }

        foreach (var (field, evidence) in evidenceTexts)
        {
            var checksWinFail = field is "win_fail_conditions" or "source_message";
            var checksFlowRules = field is "game_feature" or "core_gameplay_loop" or "source_message";

            if (checksWinFail)
            {
                if (ContainsAny(evidence, "15场", "15 battles", "15 battle") &&
                    !ContainsAny(combined, "15场", "15 battles", "15 battle"))
                {
                    missing.Add("explicit 15-battle victory rule coverage");
                }

                if (ContainsAny(evidence, "任一战斗失败", "任一", "any battle loss", "any-loss defeat", "game loss") &&
                    !ContainsAny(combined, "任一战斗失败", "any battle loss", "any-loss defeat", "game loss", "失败即"))
                {
                    missing.Add("explicit any-loss defeat rule coverage");
                }
            }

            if (checksFlowRules)
            {
                if (ContainsAny(evidence, "10%", "10 %") &&
                    !ContainsAny(combined, "10%", "10 %"))
                {
                    missing.Add("explicit encounter probability rule coverage");
                }

                if (ContainsAny(evidence, "10步", "10 steps", "10-step") &&
                    !ContainsAny(combined, "10步", "10 steps", "10-step"))
                {
                    missing.Add("explicit guaranteed encounter rule coverage");
                }

                if (ContainsAny(evidence, "每个怪物", "下一个怪物", "+5", "+2", "enemy", "怪物") &&
                    ContainsAny(evidence, "5点生命", "5 hp", "+5 hp", "2点攻击", "2 atk", "+2 atk") &&
                    !ContainsAny(combined, "5点生命", "5 hp", "+5 hp", "2点攻击", "2 atk", "+2 atk", "enemy scaling", "怪物成长"))
                {
                    missing.Add("explicit enemy scaling rule coverage");
                }
            }
        }

        return missing.Distinct(StringComparer.Ordinal).ToList();
    }

    private static string? FindRpgPlanAcceptanceBoundaryIssue(ProjectIterationGoalSnapshot[] goals)
    {
        var firstGoal = goals.OrderBy(goal => goal.GoalIndex).FirstOrDefault();
        if (firstGoal is null)
        {
            return null;
        }

        var firstGoalText = string.Join(" ", firstGoal.Title, firstGoal.Description, firstGoal.AcceptanceHint);
        if (!ContainsAny(firstGoalText, "start adventure", "visible map", "visible mapscene", "mapscene", "stable movement", "encounter entry"))
        {
            return "RPG plan acceptance boundary mismatch: step 1 must target Start Adventure to visible MapScene, stable movement, and encounter entry before BattleScene, reward, polish, package readiness, or final acceptance work.";
        }

        var boundaryProbeText = StripRpgStepOneBoundaryExclusionClauses(firstGoalText);
        if (ContainsAny(
                boundaryProbeText,
                "battle scene",
                "battlescene",
                "battlescene.tscn",
                "reward",
                "3-choice",
                "three choices",
                "scene switching",
                "scene switch",
                "switch into",
                "return path",
                "full playable",
                "full rpg playable",
                "package readiness",
                "final acceptance"))
        {
            return "RPG plan acceptance boundary mismatch: step 1 must only validate Start Adventure to visible MapScene, stable movement, and encounter entry. BattleScene, reward, scene switching, package readiness, and final acceptance requirements must be split into later steps.";
        }

        return null;
    }

    private static string StripRpgStepOneBoundaryExclusionClauses(string value)
    {
        var text = value;
        text = Regex.Replace(
            text,
            @"\bbefore\b[^.。]*\b(?:battle|battlescene|reward|scene switching|package readiness|final acceptance|full playable)\b[^.。]*[.。]?",
            " ",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        text = Regex.Replace(
            text,
            @"\b(?:do not|don't|must not|should not|without)\b[^.。]*\b(?:battle|battlescene|reward|scene switching|package readiness|final acceptance|full playable)\b[^.。]*[.。]?",
            " ",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        text = Regex.Replace(
            text,
            @"\b(?:keep|remain|stays?)\b[^.。]*\b(?:focused|limited|scoped)\b[^.。]*\b(?:before|without|not)\b[^.。]*\b(?:battle|battlescene|reward|scene switching|package readiness|final acceptance|full playable)\b[^.。]*[.。]?",
            " ",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        return text;
    }

    private static bool IsStaleRpgBoundaryMismatchEvaluation(
        PrototypeIterationPlanEvaluationResult evaluation,
        ProjectIterationGoalSnapshot[] goals)
    {
        if (!string.Equals(evaluation.Decision, "should_refine_plan", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        if (FindRpgPlanAcceptanceBoundaryIssue(goals) is not null)
        {
            return false;
        }

        var evaluationText = string.Join(
            " ",
            evaluation.Summary ?? string.Empty,
            evaluation.Reason ?? string.Empty,
            evaluation.SuggestedAction ?? string.Empty,
            evaluation.SuggestedPromptForRegeneration ?? string.Empty);
        if (string.IsNullOrWhiteSpace(evaluationText))
        {
            return false;
        }

        return
            ContainsAny(evaluationText, "acceptance boundary mismatch", "step 1 must only", "step one must only", "first step must only") &&
            ContainsAny(evaluationText, "BattleScene", "battle scene", "reward", "scene switching", "package readiness", "final acceptance", "full playable") &&
            ContainsAny(evaluationText, "Start Adventure", "visible MapScene", "visible map", "stable movement", "encounter entry");
    }

    private static PrototypeIterationPlanEvaluationResult BuildRpgRouteGuardAcceptedEvaluation(PrototypeIterationPlanEvaluationResult staleEvaluation)
    {
        return new PrototypeIterationPlanEvaluationResult(
            "ready_to_execute",
            "RPG route guard accepted the saved iteration plan.",
            $"The model requested RPG acceptance-boundary refinement, but the saved final goals already keep Step 1 limited to Start Adventure, visible MapScene, stable movement, and encounter entry. Stale model reason: {TrimForHint(staleEvaluation.Reason, 240)}",
            "Execute the next goal.",
            null);
    }

    private static string BuildRpgRegenerationPrompt(ProjectIterationSessionDetails details)
    {
        var sourceMessage = details.Session.SourceMessage?.Trim();
        if (string.IsNullOrWhiteSpace(sourceMessage))
        {
            sourceMessage = details.Session.OverallGoal?.Trim();
        }

        return string.IsNullOrWhiteSpace(sourceMessage)
            ? "Regenerate the RPG iteration plan as strict route-profile steps: Start Adventure to visible MapScene with stable movement and encounter entry first, then BattleScene, reward 3-choice return-to-map, main loop scene switching, win/fail visibility, and final full playable acceptance."
            : $"Regenerate the RPG iteration plan as strict route-profile steps: Start Adventure to visible MapScene with stable movement and encounter entry first, then BattleScene, reward 3-choice return-to-map, main loop scene switching, win/fail visibility, and final full playable acceptance. Source request: {sourceMessage}";
    }

    private static string BuildRpgPlanEvaluationPrompt(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        ProjectIterationSessionDetails details,
        PrototypeWorkflowProgress? prototypeProgress,
        PrototypeIterationPlanningAnalysisResult? planningAnalysis)
    {
        var goalsJson = JsonSerializer.Serialize(details.Goals.OrderBy(goal => goal.GoalIndex).Select(goal => new
        {
            goal.GoalIndex,
            goal.Title,
            goal.Description,
            goal.AcceptanceHint,
            goal.Status
        }).ToArray());
        var progressJson = JsonSerializer.Serialize(prototypeProgress);
        var planningJson = JsonSerializer.Serialize(planningAnalysis);

        return $"""
            You are evaluating whether an RPG prototype iteration plan is accurate enough to execute as-is.
            Output JSON only. Do not explain. Do not use Markdown.
            Return these keys only:
            decision, summary, reason, suggestedAction, suggestedPromptForRegeneration

            Rules:
            - Use only the data provided in this prompt.
            - Do not read files, inspect the repository, call tools, or ask for more context.
            - decision must be one of: ready_to_execute, should_refine_plan.
            - Use the current prototype result, planning analysis, and RPG type requirements.
            - If the plan is generic, misses MapScene/BattleScene/reward loop/win-fail visibility/final acceptance coverage, or is misordered, return should_refine_plan.
            - If the latest prototype gap is navigation or visible-map related, prefer should_refine_plan unless the first steps clearly target that blocker.
            - suggestedPromptForRegeneration should be null only when decision is ready_to_execute.
            - Keep output browser-safe.

            Project:
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}
            - GameTypeProfileId: {routeProfile.ProfileId}
            - RouteSetId: {routeProfile.RouteSetId}
            - PromptProtocolId: {routeProfile.PromptProtocolId}
            - PlannerId: {routeProfile.PlannerId}
            - EvaluatorId: {routeProfile.EvaluatorId}
            - Rule: evaluate only against this same game-type route profile; do not invent requirements outside this route set.

            Iteration goals:
            {goalsJson}

            Prototype progress:
            {progressJson}

            Planning analysis:
            {planningJson}
            """;
    }

    private static PrototypeIterationPlanEvaluationResult? ParseModelEvaluation(string? assistantMessage)
    {
        if (string.IsNullOrWhiteSpace(assistantMessage))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(LlmRouteEngine.ExtractFirstJsonObject(assistantMessage) ?? assistantMessage);
            var root = document.RootElement;
            var decision = root.TryGetProperty("decision", out var decisionElement) && decisionElement.ValueKind == JsonValueKind.String
                ? decisionElement.GetString()?.Trim()
                : null;
            if (!string.Equals(decision, "ready_to_execute", StringComparison.OrdinalIgnoreCase) &&
                !string.Equals(decision, "should_refine_plan", StringComparison.OrdinalIgnoreCase))
            {
                return null;
            }

            var summary = root.TryGetProperty("summary", out var summaryElement) && summaryElement.ValueKind == JsonValueKind.String
                ? summaryElement.GetString()?.Trim()
                : null;
            var reason = root.TryGetProperty("reason", out var reasonElement) && reasonElement.ValueKind == JsonValueKind.String
                ? reasonElement.GetString()?.Trim()
                : null;
            var suggestedAction = root.TryGetProperty("suggestedAction", out var actionElement) && actionElement.ValueKind == JsonValueKind.String
                ? actionElement.GetString()?.Trim()
                : null;
            string? suggestedPrompt = null;
            if (root.TryGetProperty("suggestedPromptForRegeneration", out var promptElement) && promptElement.ValueKind == JsonValueKind.String)
            {
                suggestedPrompt = promptElement.GetString()?.Trim();
            }

            if (string.IsNullOrWhiteSpace(summary) || string.IsNullOrWhiteSpace(reason) || string.IsNullOrWhiteSpace(suggestedAction))
            {
                return null;
            }

            return new PrototypeIterationPlanEvaluationResult(
                decision!,
                summary!,
                reason!,
                suggestedAction!,
                string.Equals(decision, "ready_to_execute", StringComparison.OrdinalIgnoreCase) ? null : suggestedPrompt);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string? BuildPlanRegenerationGuidance(
        ProjectIterationSessionDetails? previousIterationPlan,
        string message,
        string sourceKind)
    {
        var candidates = new List<string>();
        if (previousIterationPlan?.LatestEvaluation is not null &&
            string.Equals(previousIterationPlan.LatestEvaluation.Decision, "should_refine_plan", StringComparison.OrdinalIgnoreCase))
        {
            if (!string.IsNullOrWhiteSpace(previousIterationPlan.LatestEvaluation.SuggestedPromptForRegeneration))
            {
                candidates.Add(previousIterationPlan.LatestEvaluation.SuggestedPromptForRegeneration!);
            }

            candidates.Add(previousIterationPlan.LatestEvaluation.SuggestedAction);
            candidates.Add(previousIterationPlan.LatestEvaluation.Reason);
        }

        if (string.Equals(sourceKind, "completion_suggestion", StringComparison.OrdinalIgnoreCase) &&
            LooksLikeRegenerationGuidance(message))
        {
            candidates.Add(message);
        }

        var guidance = string.Join("\n", candidates.Where(value => !string.IsNullOrWhiteSpace(value)).Select(value => value.Trim()));
        return string.IsNullOrWhiteSpace(guidance) ? null : guidance;
    }

    private static bool LooksLikeRegenerationGuidance(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        return ContainsAny(
            value,
            "重写 RPG 迭代计划",
            "重拆",
            "Regenerate the RPG iteration plan",
            "Start Adventure",
            "visible MapScene",
            "可见 MapScene",
            "稳定移动");
    }

    private static bool RequiresNavigationFirstRpgPlan(string? regenerationGuidance)
    {
        if (string.IsNullOrWhiteSpace(regenerationGuidance))
        {
            return false;
        }

        var guidance = regenerationGuidance.Trim();
        return ContainsAny(guidance, "Start Adventure", "visible MapScene", "可见 MapScene", "稳定移动") &&
               ContainsAny(guidance, "第一优先级", "首要阻塞", "first priority", "first blocker", "Step 1", "第一阶段", "先解决");
    }

    private static bool ContainsAny(string text, params string[] values)
    {
        return values.Any(value => text.Contains(value, StringComparison.OrdinalIgnoreCase));
    }

    private static List<PrototypeIterationPlanGoalResult> TryBuildRefinedGoals(string message, string sourceKind)
    {
        if (!string.Equals(sourceKind, "completion_suggestion", StringComparison.OrdinalIgnoreCase))
        {
            return [];
        }

        var normalized = message.Trim();
        if (string.IsNullOrWhiteSpace(normalized))
        {
            return [];
        }

        var looksLikeRpgClosure =
            normalized.Contains("RPG", StringComparison.OrdinalIgnoreCase) &&
            normalized.Contains("完整首轮闭环", StringComparison.Ordinal) &&
            normalized.Contains("移动", StringComparison.Ordinal) &&
            normalized.Contains("遇敌", StringComparison.Ordinal) &&
            normalized.Contains("战斗", StringComparison.Ordinal) &&
            normalized.Contains("奖励 3 选 1", StringComparison.Ordinal);
        if (!looksLikeRpgClosure)
        {
            return [];
        }

        return
        [
            new PrototypeIterationPlanGoalResult(
                1,
                "目标 1：补稳地图移动与可见遇敌触发",
                "先让玩家能稳定移动，并且能清楚看到或明确触发第一次遇敌，不要把战斗、奖励和胜负提示一起塞进这一步。",
                "完成并验证：玩家能稳定移动，并能明确进入第一次遇敌。",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                2,
                "目标 2：补通单场战斗与基础结算",
                "在首次遇敌后完成一场可读、可结束的战斗，至少让玩家能看到战斗开始、行动结果和胜利结算，不要在这一步同时处理奖励理解问题。",
                "完成并验证：玩家能完整打完一场战斗，并看到明确的胜利结算。",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                3,
                "目标 3：补通奖励 3 选 1 并返回地图",
                "战斗胜利后展示奖励 3 选 1，并在选择后正确返回地图继续流程，重点保证奖励含义可理解、选择后状态变化可见。",
                "完成并验证：奖励 3 选 1 可理解、可选择，且选择后能正确返回地图。",
                "pending"),
            new PrototypeIterationPlanGoalResult(
                4,
                "目标 4：补齐胜负目标提示与最小验证",
                "把“打赢 15 场胜利、任一战斗失败即失败”的规则做成玩家一眼能看懂的提示，并补一轮最小验证，确认首轮闭环与目标提示能一起工作。",
                "完成并验证：玩家能清楚理解胜负条件，且首轮闭环在提示存在时仍可正常工作。",
                "pending"),
        ];
    }

    private static List<string> ExtractStructuredGoals(string message)
    {
        return NumberedGoalRegex.Matches(message)
            .Select(match => match.Groups[1].Value.Trim())
            .Select(NormalizeGoalSegment)
            .Where(IsMeaningfulGoalSegment)
            .Distinct(StringComparer.Ordinal)
            .ToList();
    }

    private static string NormalizeGoalSegment(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        return value
            .Replace("\r", "\n")
            .Trim()
            .Trim(';', '；', ',', '，', '.', '。', ':', '：', '-', ' ')
            .Replace("\n", " ")
            .Trim();
    }

    private static bool IsMeaningfulGoalSegment(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var trimmed = value.Trim();
        if (trimmed.Length < 4)
        {
            return false;
        }

        var letterOrDigitCount = trimmed.Count(char.IsLetterOrDigit);
        return letterOrDigitCount >= 3;
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

    private static bool IsRecognizedSmallGoal(ProjectIterationGoalSnapshot goal)
    {
        var title = goal.Title?.Trim() ?? string.Empty;
        var description = goal.Description?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(title) || string.IsNullOrWhiteSpace(description))
        {
            return false;
        }

        return
            (title.Contains("补稳地图移动与可见遇敌触发", StringComparison.Ordinal) &&
             description.Contains("稳定移动", StringComparison.Ordinal) &&
             description.Contains("第一次遇敌", StringComparison.Ordinal)) ||
            (title.Contains("补通单场战斗与基础结算", StringComparison.Ordinal) &&
             description.Contains("首次遇敌后完成一场可读、可结束的战斗", StringComparison.Ordinal)) ||
            (title.Contains("补通奖励 3 选 1 并返回地图", StringComparison.Ordinal) &&
             description.Contains("奖励 3 选 1", StringComparison.Ordinal) &&
             description.Contains("返回地图", StringComparison.Ordinal)) ||
            (title.Contains("补齐胜负目标提示与最小验证", StringComparison.Ordinal) &&
             description.Contains("打赢 15 场胜利", StringComparison.Ordinal) &&
             description.Contains("任一战斗失败即失败", StringComparison.Ordinal));
    }

    private static PrototypeIterationPlanEvaluationResult BuildLlmFailedEvaluation(string failureCode)
    {
        var code = string.IsNullOrWhiteSpace(failureCode) ? "llm_failed" : failureCode.Trim();
        return new PrototypeIterationPlanEvaluationResult(
            "llm_failed",
            "迭代计划评估需要 LLM 成功参与，但当前调用失败。",
            $"LLM 调用失败：{code}。系统不会使用本地规则假装评估成功。",
            "请先修复 LLM 调用，再重新评估当前迭代计划。",
            null);
    }

    private async Task<PrototypeIterationPlanEvaluationResult> PersistEvaluationAsync(
        ProjectIterationSessionDetails details,
        PrototypeIterationPlanEvaluationResult evaluation,
        CancellationToken cancellationToken = default)
    {
        var serialized = JsonSerializer.Serialize(evaluation);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(
            details.Session.SessionId,
            details.Session.Status,
            details.Session.CurrentGoalIndex,
            details.Session.LatestSummary,
            serialized,
            details.Session.CompletedUtc,
            cancellationToken);
        return evaluation;
    }

    private static PrototypeWorkflowProgress ToPrototypeProgress(IterationPlanningContext context)
    {
        return new PrototypeWorkflowProgress(
            context.LatestPrototypeStatus,
            context.LatestPrototypeStatus,
            "",
            "done",
            null,
            null,
            null,
            context.LatestPrototypeCompletionSummary,
            "system",
            "recommended",
            context.AnalysisSummary);
    }

    private static string NormalizePlanningMessage(string? message, string? sourceKind)
    {
        var value = message?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        var kind = sourceKind?.Trim() ?? string.Empty;
        if (!string.Equals(kind, "completion_suggestion", StringComparison.OrdinalIgnoreCase))
        {
            return value;
        }

        return UnwrapRegenerationPrompt(value);
    }

    private static string UnwrapRegenerationPrompt(string message)
    {
        var value = message.Trim();
        var prefixes = new[]
        {
            "请把这条原型优化建议重拆成 4 个更小、能单独执行的目标，不要把多个连续实现点塞进同一个目标里：",
            "请根据当前 prototype completion report，把下一步优化拆成 4 个更小的目标：",
            "请把当前优化目标重拆成 4 个更小的连续目标，每个目标都要足够小，适合一次单独执行。"
        };

        var changed = true;
        while (changed)
        {
            changed = false;
            foreach (var prefix in prefixes)
            {
                if (!value.StartsWith(prefix, StringComparison.Ordinal))
                {
                    continue;
                }

                var remainder = value[prefix.Length..].Trim();
                if (string.IsNullOrWhiteSpace(remainder))
                {
                    return value;
                }

                value = remainder;
                changed = true;
                break;
            }
        }

        return value;
    }

    private sealed record PlanningFieldCoverage(
        string Field,
        string Status,
        string? Evidence,
        string? MissingReason);

    private sealed record IterationPlanningContext(
        string AnalysisSource,
        string AnalysisSummary,
        string LatestPrototypeStatus,
        string? LatestPrototypeCompletionSummary,
        int DraftCoveragePercent,
        string? DraftCoverageSummary,
        string? TemplateId,
        IReadOnlyList<PlanningFieldCoverage> FieldCoverage,
        string PrototypeStateExcerpt,
        string SourceMessage,
        string SourceKind,
        string RouteSkillId);

    private static string EnsurePlanningAnalysisSchemaFile()
    {
        var schemaDir = Path.Combine(Path.GetTempPath(), "phase-a-platform-schemas");
        Directory.CreateDirectory(schemaDir);
        var schemaPath = Path.Combine(schemaDir, "prototype-iteration-planning-analysis.schema.json");
        var schema = new JsonObject
        {
            ["type"] = "object",
            ["additionalProperties"] = false,
            ["properties"] = new JsonObject
            {
                ["analysisSummary"] = new JsonObject
                {
                    ["type"] = "string",
                    ["minLength"] = 1
                },
                ["fieldCoverage"] = new JsonObject
                {
                    ["type"] = "array",
                    ["items"] = new JsonObject
                    {
                        ["type"] = "object",
                        ["additionalProperties"] = false,
                        ["properties"] = new JsonObject
                        {
                            ["field"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 },
                            ["status"] = new JsonObject { ["type"] = "string", ["enum"] = new JsonArray("completed", "partial", "missing") },
                            ["evidence"] = new JsonObject { ["type"] = new JsonArray("string", "null") },
                            ["missingReason"] = new JsonObject { ["type"] = new JsonArray("string", "null") }
                        },
                        ["required"] = new JsonArray("field", "status", "evidence", "missingReason")
                    }
                }
            },
            ["required"] = new JsonArray("analysisSummary", "fieldCoverage")
        };

        File.WriteAllText(schemaPath, schema.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
        return schemaPath;
    }

    private static string EnsureGoalPlanSchemaFile()
    {
        var schemaDir = Path.Combine(Path.GetTempPath(), "phase-a-platform-schemas");
        Directory.CreateDirectory(schemaDir);
        var schemaPath = Path.Combine(schemaDir, "prototype-iteration-goal-plan.schema.json");
        var schema = new JsonObject
        {
            ["type"] = "object",
            ["additionalProperties"] = false,
            ["properties"] = new JsonObject
            {
                ["goals"] = new JsonObject
                {
                    ["type"] = "array",
                    ["minItems"] = 3,
                    ["maxItems"] = 8,
                    ["items"] = new JsonObject
                    {
                        ["type"] = "object",
                        ["additionalProperties"] = false,
                        ["properties"] = new JsonObject
                        {
                            ["title"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 },
                            ["description"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 },
                            ["acceptanceHint"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 }
                        },
                        ["required"] = new JsonArray("title", "description", "acceptanceHint")
                    }
                }
            },
            ["required"] = new JsonArray("goals")
        };

        File.WriteAllText(schemaPath, schema.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
        return schemaPath;
    }

    private static string EnsureEvaluationSchemaFile()
    {
        var schemaDir = Path.Combine(Path.GetTempPath(), "phase-a-platform-schemas");
        Directory.CreateDirectory(schemaDir);
        var schemaPath = Path.Combine(schemaDir, "prototype-iteration-evaluation.schema.json");
        var schema = new JsonObject
        {
            ["type"] = "object",
            ["additionalProperties"] = false,
            ["properties"] = new JsonObject
            {
                ["decision"] = new JsonObject { ["type"] = "string", ["enum"] = new JsonArray("ready_to_execute", "should_refine_plan") },
                ["summary"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 },
                ["reason"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 },
                ["suggestedAction"] = new JsonObject { ["type"] = "string", ["minLength"] = 1 },
                ["suggestedPromptForRegeneration"] = new JsonObject { ["type"] = new JsonArray("string", "null") }
            },
            ["required"] = new JsonArray("decision", "summary", "reason", "suggestedAction", "suggestedPromptForRegeneration")
        };

        File.WriteAllText(schemaPath, schema.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
        return schemaPath;
    }

    private static string EnsureIterationPlanPromptWorkspace(ProjectSnapshot project, string purpose)
    {
        var repoParent = Path.GetDirectoryName(project.RepoPath);
        var workspaceRoot = string.IsNullOrWhiteSpace(repoParent) ? project.RepoPath : repoParent;
        var root = Path.Combine(workspaceRoot, "_phasea_llm", purpose);
        Directory.CreateDirectory(root);
        return root;
    }
}

public sealed record PrototypeIterationPlanDetails(
    ProjectIterationSessionSnapshot Session,
    IReadOnlyList<ProjectIterationGoalSnapshot> Goals,
    IReadOnlyList<ProjectIterationGoalRunSnapshot> GoalRuns,
    PrototypeIterationPlanEvaluationResult? LatestEvaluation = null,
    PrototypeIterationPlanningAnalysisResult? PlanningAnalysis = null);

internal sealed class PrototypeIterationPlanLlmException : Exception
{
    public PrototypeIterationPlanLlmException(string message)
        : base(message)
    {
    }
}
