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
    private readonly BmadGameTypeDesignCatalog? _bmadGameTypeDesignCatalog;

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
        GameTypeTemplateCatalog? templateCatalog = null,
        BmadGameTypeDesignCatalog? bmadGameTypeDesignCatalog = null)
    {
        _metadataStore = metadataStore;
        _routeStateWriter = routeStateWriter;
        _contractService = contractService ?? new PrototypeContractService();
        _llmRouteEngine = llmRouteEngine ?? (codexChatClient is null ? null : new LlmRouteEngine(codexChatClient));
        _templateCatalog = templateCatalog;
        _bmadGameTypeDesignCatalog = bmadGameTypeDesignCatalog;
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
        var model = PrototypeModelPolicy.Normalize(request.Model);
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
        var projectExecutionGuide = _routeStateWriter.ReadOrCreateProjectExecutionGuide(project, prototypeContract);
        IterationPlanningContext planningContext;
        try
        {
            planningContext = await BuildPlanningContextAsync(project, routeProfile, routeStrategy, routeSkill, prototypeContract, promptMessage, sourceKind, regenerationGuidance, model, cancellationToken);
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

        IterationGoalBuildResult goalBuild;
        try
        {
            goalBuild = await BuildGoalsForProjectAsync(project, routeProfile, routeStrategy, prototypeContract, promptMessage, sourceKind, planningContext, regenerationGuidance, model, cancellationToken);
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

        var goals = goalBuild.Goals;
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

        var summary = BuildPlanSummary(goals.Count, planningContext, goalBuild.UsedScaffoldFallback);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(created.SessionId, "ready", 0, summary, null, null, cancellationToken);
        var planningAnalysis = ToPlanningAnalysisResult(planningContext, goalBuild.StageTelemetry);
        var llmObservability = BuildIterationPlanObservability(planningContext, goalBuild);
        _routeStateWriter.WriteIterationPlanAnalysisState(project, new
        {
            route = "iteration-plan",
            session_id = created.SessionId,
            planning_analysis = planningAnalysis,
            llm_observability = llmObservability,
            model_plan_degraded = goalBuild.UsedScaffoldFallback ? "scaffold_fallback" : null,
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });
        _routeStateWriter.WriteIterationPlanState(project, new
        {
            route = "iteration-plan",
            route_skill = routeSkill,
            game_type_profile = routeProfile,
            project_execution_guide_present = !string.IsNullOrWhiteSpace(projectExecutionGuide),
            project_execution_guide_path = PrototypeRouteStateWriter.ProjectExecutionGuideRelativePath,
            prototype_contract = prototypeContract.RelativePath,
            prototype_contract_present = !string.IsNullOrWhiteSpace(prototypeContract.Json),
            session_id = created.SessionId,
            status = "ready",
            source_kind = sourceKind,
            summary,
            model_plan_degraded = goalBuild.UsedScaffoldFallback ? "scaffold_fallback" : null,
            planning_analysis = planningAnalysis,
            llm_observability = llmObservability,
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

        var evaluation = await EvaluateAsync(accountId, projectId, ToPrototypeProgress(planningContext), model, cancellationToken);
        return new PrototypeIterationPlanResult(created.SessionId, "ready", summary, goals, planningAnalysis, evaluation);
    }

    private async Task<IterationGoalBuildResult> BuildGoalsForProjectAsync(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        IGameTypeRouteStrategy routeStrategy,
        PrototypeContractSnapshot prototypeContract,
        string message,
        string sourceKind,
        IterationPlanningContext planningContext,
        string? regenerationGuidance,
        string model,
        CancellationToken cancellationToken)
    {
        if (routeStrategy.UsesSpecializedIterationPlanning &&
            string.Equals(routeStrategy.GameTypeId, "rpg", StringComparison.OrdinalIgnoreCase))
        {
            var scaffold = BuildRpgGoalsFromContext(message, sourceKind, prototypeContract, planningContext, regenerationGuidance);
            if (IsDeterministicRpgRegenerationRequest(sourceKind, message, regenerationGuidance))
            {
                return new IterationGoalBuildResult(scaffold, false);
            }

            return await RefineRpgGoalsWithRequiredModelAsync(project, routeProfile, planningContext, message, scaffold, regenerationGuidance, model, cancellationToken);
        }

        var goals = BuildGoals(message, sourceKind);
        return new IterationGoalBuildResult(AppendGenericFinalAcceptanceGoal(goals, message, prototypeContract), false);
    }

    private async Task<IterationPlanningContext> BuildPlanningContextAsync(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        IGameTypeRouteStrategy routeStrategy,
        PrototypeRouteSkillContext routeSkill,
        PrototypeContractSnapshot prototypeContract,
        string message,
        string sourceKind,
        string? regenerationGuidance,
        string model,
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
        var projectExecutionGuide = _routeStateWriter.ReadOrCreateProjectExecutionGuide(project, prototypeContract);
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
            RouteSkillId: routeSkill.RouteSkillId,
            StageTelemetry: []);

        if (AllowsSoftPlanningAnalysisFallback(routeStrategy))
        {
            return fallback with
            {
                AnalysisSummary = AppendFailureNote(fallback.AnalysisSummary, "planning_analysis_skipped_for_rpg_route"),
                StageTelemetry = [BuildSkippedTelemetry("planning-analysis", model, "planning_analysis_skipped_for_rpg_route")]
            };
        }

        if (_llmRouteEngine is null)
        {
            if (routeStrategy.RequiresModelBackedIterationPlanning &&
                !AllowsSoftPlanningAnalysisFallback(routeStrategy) &&
                !IsDeterministicRpgRegenerationRequest(sourceKind, message, regenerationGuidance))
            {
                throw new PrototypeIterationPlanLlmException("planning_analysis_llm_client_missing");
            }

            return fallback;
        }

        var designTemplateGuidance = BuildCompactDesignTemplateGuidance(project, routeProfile);
        var modelPrompt = BuildPlanningAnalysisPrompt(project, routeProfile, projectExecutionGuide, designTemplateGuidance, prototypeContract, fallback, draft, latestPrototypeRun, latestSuccessfulPrototypeRun);
        var promptRoot = EnsureIterationPlanPromptWorkspace(project, "planning-analysis");
        var options = PlanningCodexOptions with { OutputSchemaPath = PlanningAnalysisSchemaPath };
        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                promptRoot,
                "planning-analysis",
                model,
                modelPrompt,
                options,
                project.AccountId,
                RequireJsonObject: true),
            cancellationToken);
        if (!completion.Succeeded)
        {
            if (routeStrategy.RequiresModelBackedIterationPlanning &&
                !AllowsSoftPlanningAnalysisFallback(routeStrategy) &&
                !IsDeterministicRpgRegenerationRequest(sourceKind, message, regenerationGuidance))
            {
                throw new PrototypeIterationPlanLlmException(completion.FailureCode ?? "planning_analysis_llm_failed");
            }

            return fallback with
            {
                AnalysisSummary = AppendFailureNote(fallback.AnalysisSummary, completion.FailureCode),
                StageTelemetry = [BuildTelemetry("planning-analysis", completion)]
            };
        }

        var parsed = TryParsePlanningContext(completion.JsonObjectText ?? completion.AssistantMessage, fallback);
        if (parsed is null &&
            routeStrategy.RequiresModelBackedIterationPlanning &&
            !AllowsSoftPlanningAnalysisFallback(routeStrategy) &&
            !IsDeterministicRpgRegenerationRequest(sourceKind, message, regenerationGuidance))
        {
            throw new PrototypeIterationPlanLlmException("planning_analysis_parse_failed");
        }

        var telemetry = BuildTelemetry("planning-analysis", completion);
        if (parsed is not null)
        {
            return parsed with { StageTelemetry = [telemetry] };
        }

        return fallback with
        {
            AnalysisSummary = AppendFailureNote(fallback.AnalysisSummary, "planning_analysis_parse_failed"),
            StageTelemetry = [telemetry]
        };
    }

    private async Task<IterationGoalBuildResult> RefineRpgGoalsWithRequiredModelAsync(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        IterationPlanningContext planningContext,
        string message,
        IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold,
        string? regenerationGuidance,
        string model,
        CancellationToken cancellationToken)
    {
        if (_llmRouteEngine is null)
        {
            throw new PrototypeIterationPlanLlmException("goal_plan_llm_client_missing");
        }

        var projectExecutionGuide = _routeStateWriter.ReadOrCreateProjectExecutionGuide(project, _contractService.Read(project));
        var designTemplateGuidance = BuildCompactDesignTemplateGuidance(project, routeProfile);
        var prompt = BuildRpgGoalRefinementPrompt(project, routeProfile, projectExecutionGuide, designTemplateGuidance, planningContext, message, scaffold, regenerationGuidance);
        var promptRoot = EnsureIterationPlanPromptWorkspace(project, "goal-plan");
        var options = PlanningCodexOptions with { OutputSchemaPath = GoalPlanSchemaPath };
        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                promptRoot,
                "goal-plan",
                model,
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
        if (parsed.Goals.Count == 0)
        {
            throw new PrototypeIterationPlanLlmException("goal_plan_parse_failed");
        }

        return parsed with
        {
            StageTelemetry = [BuildTelemetry("goal-plan", completion)]
        };
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
        _ = goals;
        return BuildJrpgFirstLoopGoals(message, planningContext, prototypeContract, regenerationGuidance);
    }

    private static bool AllowsSoftPlanningAnalysisFallback(IGameTypeRouteStrategy routeStrategy)
    {
        return routeStrategy.UsesSpecializedIterationPlanning &&
            string.Equals(routeStrategy.GameTypeId, "rpg", StringComparison.OrdinalIgnoreCase);
    }

    private static List<PrototypeIterationPlanGoalResult> BuildRpgClosureGoals(IterationPlanningContext planningContext, string? regenerationGuidance)
    {
        return BuildJrpgFirstLoopGoals(planningContext.SourceMessage, planningContext, null, regenerationGuidance);
    }

    private static List<PrototypeIterationPlanGoalResult> BuildNavigationFirstRpgClosureGoals(IterationPlanningContext planningContext, string? regenerationGuidance)
    {
        return BuildJrpgFirstLoopGoals(planningContext.SourceMessage, planningContext, null, regenerationGuidance);
    }

    private static string BuildPlanSummary(int goalCount, IterationPlanningContext planningContext, bool usedScaffoldFallback)
    {
        var prototypeStatus = string.IsNullOrWhiteSpace(planningContext.LatestPrototypeStatus)
            ? "unknown"
            : planningContext.LatestPrototypeStatus;
        var coverage = planningContext.DraftCoveragePercent;
        var degraded = usedScaffoldFallback ? " model_plan_degraded=scaffold_fallback." : "";
        return $"已基于当前原型状态与需求覆盖分析生成 {goalCount} 个迭代目标。当前原型状态：{prototypeStatus}；表单覆盖率：{coverage}%。请先执行目标 1，再逐步推进后续目标。{degraded}";
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

    private string BuildDesignTemplateGuidance(ProjectSnapshot project, GameTypeRouteProfile routeProfile)
    {
        var entry = _bmadGameTypeDesignCatalog?.Find(routeProfile.GameTypeId)
            ?? _bmadGameTypeDesignCatalog?.Find(project.GameTypeSource);
        if (entry is null)
        {
            return "No BMAD/GDS game-type design template was loaded. Use only route profile, project execution guide, prototype contract, and user request.";
        }

        return $"""
            BMAD/GDS game-type design template:
            - Id: {entry.Id}
            - Name: {entry.Name}
            - Description: {entry.Description}
            - GenreTags: {entry.GenreTags}
            - Source: {entry.FragmentRelativePath}

            Template excerpt:
            {TrimForPrompt(entry.GuideExcerpt)}
            """;
    }

    private string BuildCompactDesignTemplateGuidance(ProjectSnapshot project, GameTypeRouteProfile routeProfile)
    {
        var entry = _bmadGameTypeDesignCatalog?.Find(routeProfile.GameTypeId)
            ?? _bmadGameTypeDesignCatalog?.Find(project.GameTypeSource);
        if (entry is null)
        {
            return "No BMAD/GDS game-type design template was loaded.";
        }

        return $"""
            BMAD/GDS game-type design template summary:
            - Id: {entry.Id}
            - Name: {entry.Name}
            - Description: {CompactForPrompt(entry.Description, 360)}
            - GenreTags: {entry.GenreTags}
            - Source: {entry.FragmentRelativePath}
            """;
    }

    private static string BuildPlanningAnalysisPrompt(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        string projectExecutionGuide,
        string designTemplateGuidance,
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
                Hypothesis = CompactForPrompt(draft.Hypothesis, 600),
                CorePlayerFantasy = CompactForPrompt(draft.CorePlayerFantasy, 600),
                MinimumPlayableLoop = CompactForPrompt(draft.MinimumPlayableLoop, 800),
                SuccessCriteria = DeserializeJsonArray(draft.SuccessCriteriaJson).Select(item => CompactForPrompt(item, 300)).Take(6).ToArray(),
                GameFeature = CompactForPrompt(draft.GameFeature, 800),
                CoreGameplayLoop = CompactForPrompt(draft.CoreGameplayLoop, 800),
                WinFailConditions = CompactForPrompt(draft.WinFailConditions, 600),
                draft.CoveragePercent,
                CoverageSummary = CompactForPrompt(draft.CoverageSummary, 600),
                CoverageMissingTopics = DeserializeJsonArray(draft.CoverageMissingTopicsJson).Select(item => CompactForPrompt(item, 220)).Take(8).ToArray()
            });
        var runJson = JsonSerializer.Serialize(new
        {
            latest_run_status = latestPrototypeRun?.Status,
            latest_run_summary = CompactForPrompt(ReadCompletionSummaryFromRun(latestPrototypeRun), 1000),
            latest_successful_status = latestSuccessfulPrototypeRun?.Status,
            latest_successful_summary = CompactForPrompt(ReadCompletionSummaryFromRun(latestSuccessfulPrototypeRun), 1000),
            fallback_analysis = CompactForPrompt(fallback.AnalysisSummary, 800)
        });
        var contractSummary = string.IsNullOrWhiteSpace(prototypeContract.Json)
            ? "{}"
            : JsonSerializer.Serialize(new
            {
                prototypeContract.RelativePath,
                present = true,
                excerpt = CompactForPrompt(prototypeContract.Json, 1000)
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
            - Use Prototype Chapter 3 Lite semantics: split small ordered prototype goals from context without creating Taskmaster triplets, formal task files, overlays, formal acceptance files, or architecture contracts.
            - Treat the Project execution guide below as the project-level /new recovery protocol, especially its Route Recovery Protocol section.
            - Recover route memory in this order: route profile and route skill, Project execution guide, prototype contract, latest prototype state, draft/form snapshot, and latest prototype run evidence.
            - Do not use AGENTS.md as hosted game-project recovery memory.
            - status must be one of completed, partial, missing.
            - Judge completion against the current prototype result, not only the form text.
            - Focus on prototype-form fields and the current route profile. For RPG/JRPG, judge only the JRPG first-loop capabilities implied by the project semantics instead of forcing every map/battle/reward template section.
            - Keep evidence and missingReason short and browser-safe.
            - Treat BMAD/GDS game-type design template guidance as taxonomy and semantic hints only; do not treat it as an executable route profile or a requirement to add every listed GDD section.

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
            {CompactForPrompt(fallback.SourceMessage, 1600)}

            Project execution guide:
            {CompactForPrompt(projectExecutionGuide, 1200)}

            Design template guidance:
            {designTemplateGuidance}

            Prototype contract:
            {contractSummary}

            Draft/form snapshot:
            {draftJson}

            Prototype run snapshot:
            {runJson}

            Prototype route state excerpt:
            {CompactForPrompt(fallback.PrototypeStateExcerpt, 1200)}
            """;
    }

    private static string BuildRpgGoalRefinementPrompt(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        string projectExecutionGuide,
        string designTemplateGuidance,
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
            You are refining a server-generated iteration plan for a JRPG first-loop Godot prototype route.
            Output JSON only. Do not explain. Do not use Markdown.
            Return these keys only:
            goals

            goals must be an array with the exact same number of items as the scaffold, and each object must contain:
            title, description, acceptanceHint

            Rules:
            - Use only the data provided in this prompt.
            - Do not read files, inspect the repository, call tools, or ask for more context.
            - Use Prototype Chapter 3 Lite semantics: refine the lightweight iteration plan only, without creating Taskmaster triplets, formal task files, overlays, formal acceptance files, or architecture contracts.
            - Treat the Project execution guide below as the project-level /new recovery protocol, especially its Route Recovery Protocol section.
            - Recover route memory in this order: route profile and route skill, Project execution guide, prototype contract, latest prototype state, planning analysis, and scaffold.
            - Do not use AGENTS.md as hosted game-project recovery memory.
            - Do not generate a new plan from scratch.
            - Keep the exact scaffold order.
            - Keep every title exactly unchanged from the scaffold.
            - Only refine description and acceptanceHint so they better reflect the current prototype state, prototype-form coverage, and RPG route-skill contract.
            - If the prototype already succeeded once, keep the convergence/closure framing already present in the scaffold.
            - If some user fields are still only partial, mention the most important missing runtime proof in the relevant later steps.
            - Keep each goal narrow enough to execute independently.
            - Treat RPG as a JRPG first-loop capability profile, not a fixed DQ-like script.
            - Treat BMAD/GDS game-type design template guidance as taxonomy and semantic hints only; do not turn the whole GDD template into iteration goals.
            - The scaffold is a semantic capability graph. Do not add, remove, or reorder capabilities.
            - Final step must remain final first-loop acceptance.
            - If regeneration guidance is provided, treat it as a hard constraint from the previous plan evaluation.
            - When regeneration guidance says the current blocker is Start Adventure, visible MapScene, or stable movement, goal 1 must remain focused on that blocker.
            - When regeneration guidance says the current blocker is encounter entry or encounter trigger, keep conflict entry separate from navigation and battle/challenge resolution.

            Project:
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}
            - GameTypeProfileId: {routeProfile.ProfileId}
            - RouteSetId: {routeProfile.RouteSetId}
            - PromptProtocolId: {routeProfile.PromptProtocolId}
            - PlannerId: {routeProfile.PlannerId}

            Requested optimization:
            {CompactForPrompt(message, 1800)}

            Regeneration guidance from previous plan evaluation:
            {(string.IsNullOrWhiteSpace(regenerationGuidance) ? "none" : CompactForPrompt(regenerationGuidance, 1200))}

            Project execution guide:
            {CompactForPrompt(projectExecutionGuide, 1800)}

            Design template guidance:
            {designTemplateGuidance}

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

    private static IterationGoalBuildResult ParseRefinedRpgGoalPlan(
        string? assistantMessage,
        IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold)
    {
        var parsed = ParseGoalPlan(assistantMessage);
        if (parsed.Count == 0 &&
            !string.IsNullOrWhiteSpace(assistantMessage) &&
            scaffold.All(goal => assistantMessage.Contains(goal.Title, StringComparison.Ordinal)))
        {
            return new IterationGoalBuildResult(CloneScaffoldGoals(scaffold), true);
        }

        if (parsed.Count < scaffold.Count)
        {
            if (IsAcceptableJrpgScaffoldSubset(parsed, scaffold))
            {
                return new IterationGoalBuildResult(CloneScaffoldGoals(scaffold), true);
            }

            return new IterationGoalBuildResult([], false);
        }

        var refined = new List<PrototypeIterationPlanGoalResult>(scaffold.Count);
        var parsedByTitle = parsed
            .GroupBy(goal => goal.Title, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);
        for (var index = 0; index < scaffold.Count; index++)
        {
            var expected = scaffold[index];
            if (!parsedByTitle.TryGetValue(expected.Title, out var actual))
            {
                if (IsAcceptableJrpgScaffoldSubset(parsed, scaffold))
                {
                    return new IterationGoalBuildResult(CloneScaffoldGoals(scaffold), true);
                }

                return new IterationGoalBuildResult([], false);
            }

            refined.Add(new PrototypeIterationPlanGoalResult(
                expected.GoalIndex,
                expected.Title,
                string.IsNullOrWhiteSpace(actual.Description) ? expected.Description : actual.Description,
                string.IsNullOrWhiteSpace(actual.AcceptanceHint) ? expected.AcceptanceHint : actual.AcceptanceHint,
                "pending"));
        }

        return new IterationGoalBuildResult(refined, false);
    }

    private static List<PrototypeIterationPlanGoalResult> CloneScaffoldGoals(IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold)
    {
        return scaffold
            .Select(goal => new PrototypeIterationPlanGoalResult(goal.GoalIndex, goal.Title, goal.Description, goal.AcceptanceHint, "pending"))
            .ToList();
    }

    private static bool IsAcceptableJrpgScaffoldSubset(
        IReadOnlyList<PrototypeIterationPlanGoalResult> parsed,
        IReadOnlyList<PrototypeIterationPlanGoalResult> scaffold)
    {
        if (parsed.Count < 2 || scaffold.Count < 2)
        {
            return false;
        }

        var firstTitle = scaffold[0].Title;
        var finalTitle = scaffold[^1].Title;
        return parsed.Any(goal => string.Equals(goal.Title, firstTitle, StringComparison.Ordinal)) &&
               parsed.Any(goal => string.Equals(goal.Title, finalTitle, StringComparison.Ordinal)) &&
               parsed.All(goal => goal.Title.StartsWith("JRPG First Loop:", StringComparison.Ordinal));
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
        if (ContainsAny(expectedText, "Start Adventure", "visible MapScene", "stable movement"))
        {
            yield return ["Start Adventure"];
            yield return ["visible MapScene", "visible RPG MapScene", "visible map", "non-empty visible MapScene"];
            yield return ["stable movement", "controllable movement", "move continuously", "movement"];
            yield return ["asset", "assets", "map/player", "map/player/enemy", "map/player runtime"];
        }

        if (ContainsAny(expectedText, "encounter trigger", "guaranteed encounter"))
        {
            yield return ["encounter trigger", "first encounter", "encounter"];
            yield return ["guaranteed", "10 steps", "10-step", "probability", "encounter progress"];
        }

        if (ContainsAny(expectedText, "BattleScene loop", "BattleScene"))
        {
            yield return ["BattleScene"];
            yield return ["settlement", "battle feedback", "complete one readable battle"];
            yield return ["enemy asset", "enemy assets", "enemy asset usage", "enemy"];
        }

        if (ContainsAny(expectedText, "reward 3-choice"))
        {
            yield return ["reward", "3-choice", "three reward", "three choices"];
            yield return ["understandability", "readability", "understandable", "player understanding", "choices are visible"];
        }

        if (ContainsAny(expectedText, "reward application", "return-to-map"))
        {
            yield return ["reward"];
            yield return ["state change", "changes state", "visible state", "application", "apply", "selection"];
            yield return ["return-to-map", "return to MapScene", "return to the map", "returns to MapScene", "returns the player to the map"];
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

        if (ContainsAny(expectedText, "full playable prototype acceptance", "Final Step", "final first-loop acceptance"))
        {
            yield return ["full playable", "full RPG playable", "full prototype", "final acceptance", "playable end-to-end", "end-to-end", "JRPG first-loop prototype", "first-loop prototype"];
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

    private static PrototypeIterationPlanningAnalysisResult ToPlanningAnalysisResult(
        IterationPlanningContext planningContext,
        IReadOnlyList<PrototypeIterationPlanStageTelemetryResult>? extraStageTelemetry = null)
    {
        var stageTelemetry = planningContext.StageTelemetry
            .Concat(extraStageTelemetry ?? [])
            .ToArray();
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
                item.MissingReason)).ToArray(),
            stageTelemetry);
    }

    private static PrototypeIterationPlanStageTelemetryResult BuildTelemetry(string stage, LlmRouteResult completion)
    {
        return new PrototypeIterationPlanStageTelemetryResult(
            stage,
            completion.Model,
            completion.DurationMs,
            completion.PromptLength,
            completion.PromptUtf8Bytes,
            completion.EstimatedPromptTokens,
            completion.FailureCode,
            completion.FailureCategory);
    }

    private static PrototypeIterationPlanStageTelemetryResult BuildSkippedTelemetry(
        string stage,
        string model,
        string reason)
    {
        return new PrototypeIterationPlanStageTelemetryResult(
            stage,
            model,
            0,
            0,
            0,
            0,
            reason,
            "skipped");
    }

    private static object BuildIterationPlanObservability(
        IterationPlanningContext planningContext,
        IterationGoalBuildResult goalBuild)
    {
        var stages = planningContext.StageTelemetry
            .Concat(goalBuild.StageTelemetry ?? [])
            .ToArray();
        return new
        {
            schema = "phase-a.iteration-plan.observability.v1",
            stages,
            totalDurationMs = stages.Sum(stage => stage.DurationMs),
            totalPromptLength = stages.Sum(stage => stage.PromptLength),
            totalPromptUtf8Bytes = stages.Sum(stage => stage.PromptUtf8Bytes),
            totalEstimatedPromptTokens = stages.Sum(stage => stage.EstimatedPromptTokens),
            failedStages = stages
                .Where(stage => !string.IsNullOrWhiteSpace(stage.FailureCode) &&
                    !string.Equals(stage.FailureCategory, "skipped", StringComparison.OrdinalIgnoreCase))
                .Select(stage => new
                {
                    stage.Stage,
                    stage.FailureCode,
                    stage.FailureCategory
                })
                .ToArray()
        };
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

    private static string CompactForPrompt(string? value, int maxChars)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var trimmed = value.Trim();
        if (trimmed.Length <= maxChars)
        {
            return trimmed;
        }

        return trimmed[..maxChars] + "\n[truncated]";
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
        string? model = null,
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
                    "请按 JRPG first-loop capability profile 重新生成迭代计划：目标 1 只覆盖项目入口、可见地图/场景与稳定移动；后续只选择项目语义实际需要的能力模块，并以最终首轮闭环验收收尾。",
                    BuildRpgRegenerationPrompt(details)));
            }

            var llmEvaluation = await EvaluateRpgPlanWithRequiredModelAsync(project, routeProfile, details, prototypeProgress, PrototypeModelPolicy.Normalize(model), cancellationToken);
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
        string model,
        CancellationToken cancellationToken)
    {
        if (_llmRouteEngine is null)
        {
            return BuildLlmFailedEvaluation("plan_evaluation_llm_client_missing");
        }

        var planningAnalysis = TryReadPlanningAnalysisFromState(_routeStateWriter.ReadLatestIterationPlanState(project));
        var projectExecutionGuide = _routeStateWriter.ReadOrCreateProjectExecutionGuide(project, _contractService.Read(project));
        var promptRoot = EnsureIterationPlanPromptWorkspace(project, "plan-evaluation");
        var options = PlanningCodexOptions with { OutputSchemaPath = EvaluationSchemaPath };
        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                promptRoot,
                "plan-evaluation",
                model,
                BuildRpgPlanEvaluationPrompt(project, routeProfile, projectExecutionGuide, details, prototypeProgress, planningAnalysis),
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
        _ = existingGoals;
        return BuildJrpgFirstLoopGoals(message, null, prototypeContract, null);
    }

    private static List<PrototypeIterationPlanGoalResult> BuildJrpgFirstLoopGoals(
        string message,
        IterationPlanningContext? planningContext,
        PrototypeContractSnapshot? prototypeContract,
        string? regenerationGuidance)
    {
        var selected = SelectJrpgFirstLoopCapabilities(message, planningContext, prototypeContract, regenerationGuidance);
        var contractInstruction = prototypeContract is null
            ? "Use the project execution guide, current prototype state, and route-skill contract as hard acceptance input."
            : BuildContractGoalInstruction(prototypeContract);
        var hint = TrimForHint(string.Join(" ", message, regenerationGuidance).Trim(), 120);
        var goals = new List<PrototypeIterationPlanGoalResult>(selected.Count);
        var index = 1;
        foreach (var capability in selected)
        {
            var description = capability.DescriptionTemplate
                .Replace("{contractInstruction}", contractInstruction, StringComparison.Ordinal)
                .Replace("{sourceHint}", hint, StringComparison.Ordinal);
            var acceptance = capability.AcceptanceTemplate
                .Replace("{contractInstruction}", contractInstruction, StringComparison.Ordinal);
            goals.Add(new PrototypeIterationPlanGoalResult(
                index++,
                $"JRPG First Loop: {capability.Title}",
                description,
                acceptance,
                "pending"));
        }

        return goals;
    }

    private static IReadOnlyList<JrpgFirstLoopCapability> SelectJrpgFirstLoopCapabilities(
        string message,
        IterationPlanningContext? planningContext,
        PrototypeContractSnapshot? prototypeContract,
        string? regenerationGuidance)
    {
        var text = BuildJrpgSelectionText(message, planningContext, prototypeContract, regenerationGuidance);
        var selectedIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "field_navigation"
        };

        var strictFirstLoopRoute = ContainsAny(text, "strict route-profile", "route-profile steps", "strict contract", "contract steps", "rpg route", "jrpg first-loop", "reward loop step", "return-to-map validation", "clean return-to-map", "final rpg acceptance", "final playable acceptance");
        if (strictFirstLoopRoute)
        {
            return SelectJrpgCapabilitiesInOrder(
                "field_navigation",
                "conflict_entry",
                "battle_or_challenge_resolution",
                "party_or_character_state",
                "growth_feedback",
                "return_or_continue_loop",
                "final_first_loop_acceptance");
        }

        var hasConflict = strictFirstLoopRoute || ContainsAny(text, "encounter", "battle", "combat", "enemy", "monster", "boss", "danger", "fight", "battle scene", "battlescene", "遇敌", "战斗", "敌人", "怪物", "首战");
        var hasReward = strictFirstLoopRoute || ContainsAny(text, "reward", "level", "exp", "growth", "loot", "item", "skill", "choice", "3-choice", "three choices", "奖励", "成长", "经验", "升级", "道具", "技能", "三选一", "选择");
        var hasOpeningContext = ContainsAny(text, "opening context", "who they control", "hero/context/objective", "player objective", "开场", "玩家身份", "当前目标");
        var hasStory = ContainsAny(text, "story", "quest", "npc", "dialog", "dialogue", "town", "village", "objective", "cutscene", "narrative", "剧情", "任务", "村庄", "城镇", "对话", "目标", "事件");
        var hasInteraction = hasStory || ContainsAny(text, "chest", "inspect", "talk", "discover", "interaction", "探索", "宝箱", "调查", "交互", "发现");
        var hasPartyState = hasConflict || ContainsAny(text, "party", "character", "hero", "hp", "mp", "stat", "status", "equipment", "job", "角色", "队伍", "主角", "生命", "属性", "装备", "职业");
        var hasReturnLoop = hasConflict || hasReward || ContainsAny(text, "loop", "return", "continue", "repeat", "map loop", "first loop", "闭环", "返回", "继续", "循环", "首轮");

        if (hasOpeningContext)
        {
            selectedIds.Add("opening_context");
        }

        if (hasInteraction)
        {
            selectedIds.Add("interaction_discovery");
        }

        if (hasConflict)
        {
            selectedIds.Add("conflict_entry");
            selectedIds.Add("battle_or_challenge_resolution");
        }

        if (hasPartyState)
        {
            selectedIds.Add("party_or_character_state");
        }

        if (hasReward)
        {
            selectedIds.Add("growth_feedback");
        }

        if (hasReturnLoop)
        {
            selectedIds.Add("return_or_continue_loop");
        }

        if (hasStory)
        {
            selectedIds.Add("quest_or_story_progress");
        }

        selectedIds.Add("final_first_loop_acceptance");
        return SelectJrpgCapabilitiesInOrder(selectedIds);
    }

    private static IReadOnlyList<JrpgFirstLoopCapability> SelectJrpgCapabilitiesInOrder(params string[] selectedIds)
    {
        return SelectJrpgCapabilitiesInOrder(new HashSet<string>(selectedIds, StringComparer.OrdinalIgnoreCase));
    }

    private static IReadOnlyList<JrpgFirstLoopCapability> SelectJrpgCapabilitiesInOrder(ISet<string> selectedIds)
    {
        return JrpgFirstLoopCapabilities
            .Where(capability => selectedIds.Contains(capability.Id))
            .ToArray();
    }

    private static string BuildJrpgSelectionText(
        string message,
        IterationPlanningContext? planningContext,
        PrototypeContractSnapshot? prototypeContract,
        string? regenerationGuidance)
    {
        var fieldCoverage = planningContext is null
            ? string.Empty
            : string.Join(" ", planningContext.FieldCoverage.Select(item => string.Join(" ", item.Field, item.Status, item.Evidence, item.MissingReason)));
        return string.Join(
            " ",
            message ?? string.Empty,
            regenerationGuidance ?? string.Empty,
            planningContext?.AnalysisSummary ?? string.Empty,
            planningContext?.LatestPrototypeCompletionSummary ?? string.Empty,
            planningContext?.DraftCoverageSummary ?? string.Empty,
            planningContext?.PrototypeStateExcerpt ?? string.Empty,
            fieldCoverage,
            prototypeContract?.Json ?? string.Empty).ToLowerInvariant();
    }

    private static readonly JrpgFirstLoopCapability[] JrpgFirstLoopCapabilities =
    [
        new(
            "opening_context",
            "opening context and player objective",
            "Establish the short JRPG prototype's immediate context before expanding systems: the player must know who they control, where they are, and what the next objective is. {contractInstruction} Source request: {sourceHint}",
            "Pass only when the playable scene presents a clear controllable hero/context/objective and the objective maps to the project contract or an explicit needs-fix blocker."),
        new(
            "field_navigation",
            "field navigation and stable control",
            "Validate the field or town movement layer as its own capability: Start Adventure or the project entry must reveal a non-empty playable field, show the player marker or character, and support stable controllable movement before conflict, rewards, or final acceptance are mixed in. {contractInstruction}",
            "Pass only when the entry opens a visible playable field/map/town scene, movement is stable, and player/map asset usage is visible."),
        new(
            "interaction_discovery",
            "interaction and discovery beat",
            "Validate the first meaningful interaction beat, such as talking to an NPC, inspecting an object, opening a chest, or discovering the next objective. Keep it separate from battle settlement and final acceptance unless the project has no interaction requirement. {contractInstruction}",
            "Pass only when at least one project-relevant interaction is visible, reachable, and changes feedback, objective state, or player understanding."),
        new(
            "conflict_entry",
            "conflict entry trigger",
            "Validate the transition from navigation or interaction into the first conflict, encounter, challenge, or battle. Include project-specific trigger rules such as probability, scripted contact, or guaranteed steps when present. {contractInstruction}",
            "Pass only when the player can clearly trigger or reach the first conflict and the trigger rule is visible or validated."),
        new(
            "battle_or_challenge_resolution",
            "battle or challenge resolution",
            "Validate one readable JRPG conflict resolution: battle/challenge presentation, player and opponent or obstacle state, action feedback, and victory/defeat or success/failure settlement. Do not hide growth or return-loop proof inside this step unless the project truly has no separate reward/return requirement. {contractInstruction}",
            "Pass only when one conflict or challenge can be resolved with readable state, action feedback, and settlement evidence."),
        new(
            "party_or_character_state",
            "party or character state readability",
            "Validate the player-facing character state needed for this first loop, such as HP, stats, party member, equipment, passive skill, or status changes. Keep this focused on readability and rule traceability, not full progression systems. {contractInstruction}",
            "Pass only when the relevant character or party state is visible, understandable, and consistent with the project rules."),
        new(
            "growth_feedback",
            "growth, reward, or consequence feedback",
            "Validate the first loop's reward, growth, or consequence feedback, such as reward choice, item gain, stat change, experience, skill unlock, or story consequence. {contractInstruction}",
            "Pass only when the reward/growth/consequence is shown, the player can understand its meaning, and any state change is visible or validated."),
        new(
            "return_or_continue_loop",
            "return or continue loop",
            "Validate that the player can continue after the first resolution: return to field, continue to the next objective, repeat a loop, or reach a clear next playable state without visual stacking or broken input. {contractInstruction}",
            "Pass only when the prototype reaches the intended next playable state and navigation/input remain usable."),
        new(
            "quest_or_story_progress",
            "quest or story progress",
            "Validate the first loop's story or quest progress if the project asks for narrative framing, NPC flow, town events, or objective completion. Keep this scoped to the first playable loop instead of long-form content production. {contractInstruction}",
            "Pass only when the objective, quest, or story state visibly progresses and remains traceable to the project request."),
        new(
            "final_first_loop_acceptance",
            "final first-loop acceptance",
            "Run final JRPG first-loop acceptance only after the selected capabilities have evidence. Cover entry, navigation, selected interaction/conflict/growth/story capabilities, project contract traceability, Godot validation evidence, and package readiness. {contractInstruction}",
            "Pass only when the selected JRPG first-loop capabilities are playable end-to-end, project-specific contract fields are represented or explicitly blocked, assets are resolved, Godot validation passes, and package readiness is proven.")
    ];

    private sealed record JrpgFirstLoopCapability(
        string Id,
        string Title,
        string DescriptionTemplate,
        string AcceptanceTemplate);

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
        var requirementSource = string.Join(
            " ",
            sourceMessage ?? string.Empty,
            planningAnalysis?.AnalysisSummary ?? string.Empty,
            planningAnalysis is null ? string.Empty : string.Join(" ", planningAnalysis.FieldCoverage.Select(item => string.Join(" ", item.Field, item.Evidence, item.MissingReason)))).ToLowerInvariant();
        var requiresConflict = ContainsAny(requirementSource, "encounter", "battle", "combat", "enemy", "monster", "boss", "fight", "遇敌", "战斗", "敌人", "怪物");
        var requiresReward = ContainsAny(requirementSource, "reward", "growth", "level", "exp", "item", "choice", "3-choice", "奖励", "成长", "升级", "经验", "道具", "选择");
        var missing = new List<string>();
        var boundaryIssue = FindRpgPlanAcceptanceBoundaryIssue(goals);
        if (boundaryIssue is not null)
        {
            return boundaryIssue;
        }

        if (!ContainsAny(combined, "mapscene", "map scene", "mapscene.tscn", "field navigation", "playable field", "town scene", "visible map", "地图场景", "场域", "城镇") ||
            !ContainsAny(combined, "start adventure", "project entry", "visible map", "visible-map", "opens a valid visible", "entry opens", "可见地图", "开始冒险", "入口"))
        {
            missing.Add("field navigation and stable control capability");
        }

        if (requiresConflict &&
            !ContainsAny(combined, "battlescene", "battle scene", "battle or challenge", "challenge resolution", "battlescene.tscn", "战斗场景", "战斗", "挑战"))
        {
            missing.Add("battle or challenge resolution capability");
        }

        if (requiresConflict &&
            !ContainsAny(combined, "encounter trigger", "first encounter", "guaranteed encounter", "encounter progress", "conflict entry", "10 steps", "10-step"))
        {
            missing.Add("independent conflict entry capability");
        }
        if (requiresReward &&
            !ContainsAny(combined, "reward", "growth", "consequence", "3-choice", "three reward", "three choices", "return-to-map", "return to the map", "奖励", "成长", "后果", "三选一", "3 选 1", "返回地图"))
        {
            missing.Add("growth/reward feedback and return-or-continue capability");
        }

        if (!ContainsAny(combined, "final acceptance", "final first-loop acceptance", "full playable prototype acceptance", "full playable", "package readiness", "交付验收", "全量验收", "最终验收"))
        {
            missing.Add("final first-loop acceptance capability");
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
        if (!ContainsAny(firstGoalText, "start adventure", "visible map", "visible mapscene", "mapscene", "stable movement"))
        {
            return "RPG plan acceptance boundary mismatch: step 1 must target Start Adventure to visible MapScene and stable movement before encounter, BattleScene, reward, polish, package readiness, or final acceptance work.";
        }

        var boundaryProbeText = StripRpgStepOneBoundaryExclusionClauses(firstGoalText);
        if (ContainsAny(
                boundaryProbeText,
                "encounter entry",
                "encounter trigger",
                "first encounter",
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
            return "RPG plan acceptance boundary mismatch: step 1 must only validate Start Adventure to visible MapScene and stable movement. Encounter trigger, BattleScene, reward, scene switching, package readiness, and final acceptance requirements must be split into later steps.";
        }

        var orderedGoals = goals.OrderBy(goal => goal.GoalIndex).ToArray();
        var finalGoalText = string.Join(" ", orderedGoals[^1].Title, orderedGoals[^1].Description, orderedGoals[^1].AcceptanceHint);
        if (!ContainsAny(finalGoalText, "final acceptance", "full playable", "package readiness", "final first-loop acceptance", "first-loop acceptance", "end-to-end"))
        {
            return "JRPG first-loop plan boundary mismatch: the final goal must be final first-loop acceptance with selected capability, contract, Godot validation, and package readiness coverage.";
        }

        var selectedCapabilities = ResolveJrpgCapabilitiesFromGoals(orderedGoals);
        if (!selectedCapabilities.Contains("field_navigation", StringComparer.OrdinalIgnoreCase))
        {
            return "JRPG first-loop plan boundary mismatch: the selected capability graph must include field navigation and stable control.";
        }

        if (!selectedCapabilities.Contains("final_first_loop_acceptance", StringComparer.OrdinalIgnoreCase))
        {
            return "JRPG first-loop plan boundary mismatch: the selected capability graph must end with final first-loop acceptance.";
        }

        var hasConflict = selectedCapabilities.Contains("conflict_entry", StringComparer.OrdinalIgnoreCase) ||
                          selectedCapabilities.Contains("battle_or_challenge_resolution", StringComparer.OrdinalIgnoreCase);
        if (hasConflict &&
            (!selectedCapabilities.Contains("conflict_entry", StringComparer.OrdinalIgnoreCase) ||
             !selectedCapabilities.Contains("battle_or_challenge_resolution", StringComparer.OrdinalIgnoreCase)))
        {
            return "JRPG first-loop plan boundary mismatch: conflict-oriented plans must split conflict entry from battle or challenge resolution.";
        }

        var hasReward = selectedCapabilities.Contains("growth_feedback", StringComparer.OrdinalIgnoreCase);
        if (hasReward &&
            !selectedCapabilities.Contains("return_or_continue_loop", StringComparer.OrdinalIgnoreCase))
        {
            return "JRPG first-loop plan boundary mismatch: reward or growth plans must include a return-or-continue loop capability.";
        }

        return null;
    }

    private static HashSet<string> ResolveJrpgCapabilitiesFromGoals(ProjectIterationGoalSnapshot[] goals)
    {
        var selected = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var goal in goals)
        {
            var text = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint).ToLowerInvariant();
            if (ContainsAny(text, "final first-loop acceptance", "final acceptance", "full playable", "package readiness", "end-to-end", "最终验收", "全量验收"))
            {
                selected.Add("final_first_loop_acceptance");
                continue;
            }

            if (ContainsAny(text, "opening context", "player objective", "objective", "hero/context/objective", "目标", "开场"))
            {
                selected.Add("opening_context");
            }

            if (ContainsAny(text, "field navigation", "stable control", "stable movement", "visible map", "mapscene", "map scene", "town scene", "field", "movement", "地图", "移动", "场景"))
            {
                selected.Add("field_navigation");
            }

            if (ContainsAny(text, "interaction", "discovery", "npc", "dialog", "chest", "inspect", "交互", "发现", "对话", "宝箱", "调查"))
            {
                selected.Add("interaction_discovery");
            }

            if (ContainsAny(text, "conflict entry", "encounter trigger", "first encounter", "guaranteed encounter", "trigger", "遇敌", "触发"))
            {
                selected.Add("conflict_entry");
            }

            if (ContainsAny(text, "battle or challenge resolution", "battlescene", "battle scene", "battle", "challenge", "settlement", "combat", "战斗", "结算", "挑战"))
            {
                selected.Add("battle_or_challenge_resolution");
            }

            if (ContainsAny(text, "party or character state", "character state", "party", "hp", "stat", "status", "equipment", "角色", "队伍", "属性", "状态", "装备"))
            {
                selected.Add("party_or_character_state");
            }

            if (ContainsAny(text, "growth", "reward", "consequence", "exp", "level", "item gain", "3-choice", "奖励", "成长", "经验", "升级", "道具"))
            {
                selected.Add("growth_feedback");
            }

            if (ContainsAny(text, "return or continue", "return-to-map", "return to the map", "continue loop", "next playable state", "返回", "继续", "循环"))
            {
                selected.Add("return_or_continue_loop");
            }

            if (ContainsAny(text, "quest", "story", "narrative", "objective completion", "剧情", "任务", "叙事"))
            {
                selected.Add("quest_or_story_progress");
            }

        }

        return selected;
    }

    private static string StripRpgStepOneBoundaryExclusionClauses(string value)
    {
        var clauses = Regex.Split(value, @"(?<=[.;??])\s+|\s+(?=\bPass only when\b)", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        return string.Join(" ", clauses.Where(clause => !IsRpgStepOneBoundaryExclusionClause(clause)));
    }

    private static bool IsRpgStepOneBoundaryExclusionClause(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var text = value.ToLowerInvariant();
        var mentionsLaterCapability = ContainsAny(
            text,
            "conflict",
            "encounter",
            "first encounter",
            "encounter trigger",
            "battle",
            "battlescene",
            "reward",
            "rewards",
            "3-choice",
            "three choices",
            "polish",
            "scene switching",
            "package readiness",
            "final acceptance",
            "full playable");
        if (!mentionsLaterCapability)
        {
            return false;
        }

        return ContainsAny(
            text,
            "before",
            "without",
            "independent of",
            "separate from",
            "not include",
            "not cover",
            "do not",
            "don't",
            "must not",
            "should not",
            "exclude",
            "excluding",
            "only validate",
            "only covers",
            "keep this scoped",
            "keep this focused",
            "focused on",
            "limited to",
            "mixed in");
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
            ContainsAny(evaluationText, "Start Adventure", "visible MapScene", "visible map", "stable movement");
    }

    private static PrototypeIterationPlanEvaluationResult BuildRpgRouteGuardAcceptedEvaluation(PrototypeIterationPlanEvaluationResult staleEvaluation)
    {
        return new PrototypeIterationPlanEvaluationResult(
            "ready_to_execute",
            "RPG route guard accepted the saved iteration plan.",
            $"The model requested RPG acceptance-boundary refinement, but the saved final goals already cover the JRPG first-loop capability graph with the first executable capability limited to Start Adventure, visible MapScene, and stable movement. Stale model reason: {TrimForHint(staleEvaluation.Reason, 240)}",
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
            ? "Regenerate the RPG iteration plan as a JRPG first-loop capability plan. Select only the capabilities implied by the project semantics: opening context, field navigation, interaction/discovery, conflict entry, battle/challenge resolution, party or character state, growth/reward/consequence feedback, return/continue loop, quest/story progress, and final first-loop acceptance. Do not force a fixed 7-step DQ-like route."
            : $"Regenerate the RPG iteration plan as a JRPG first-loop capability plan. Select only the capabilities implied by the project semantics: opening context, field navigation, interaction/discovery, conflict entry, battle/challenge resolution, party or character state, growth/reward/consequence feedback, return/continue loop, quest/story progress, and final first-loop acceptance. Do not force a fixed 7-step DQ-like route. Source request: {sourceMessage}";
    }

    private static string BuildRpgPlanEvaluationPrompt(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile,
        string projectExecutionGuide,
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
            You are evaluating whether an RPG/JRPG prototype iteration plan is accurate enough to execute as-is.
            Output JSON only. Do not explain. Do not use Markdown.
            Return these keys only:
            decision, summary, reason, suggestedAction, suggestedPromptForRegeneration

            Rules:
            - Use only the data provided in this prompt.
            - Do not read files, inspect the repository, call tools, or ask for more context.
            - Use Prototype Chapter 3 Lite / Chapter 6 Lite boundaries: evaluate whether the lightweight prototype goals are executable, not whether formal Chapter 3/6 task artifacts exist.
            - Treat the Project execution guide below as the project-level /new recovery protocol, especially its Route Recovery Protocol section.
            - Recover route memory in this order: route profile and route skill, Project execution guide, prototype contract/state inside the guide, current iteration goals, prototype progress, and planning analysis.
            - Do not use AGENTS.md as hosted game-project recovery memory.
            - decision must be one of: ready_to_execute, should_refine_plan.
            - Use the current prototype result, planning analysis, and RPG/JRPG type requirements.
            - Treat the route as a JRPG first-loop capability profile, not a fixed DQ-like 7-step script.
            - If the plan is generic, misses the selected capability coverage, lacks field navigation, lacks final first-loop acceptance, or merges unrelated boundaries, return should_refine_plan.
            - If the latest prototype gap is navigation or visible-map related, prefer should_refine_plan unless the first executable capability clearly targets Start Adventure or the project entry into a visible playable field/map/town with stable movement.
            - Conflict-oriented projects should split conflict entry from battle/challenge resolution.
            - Reward or growth projects should include growth/reward/consequence feedback and a return-or-continue loop, unless the project explicitly ends after the reward.
            - Story or town-first JRPGs do not need BattleScene/reward steps unless the source semantics asks for conflict or growth.
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

            Project execution guide:
            {TrimForPrompt(projectExecutionGuide)}

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

    private static bool IsDeterministicRpgRegenerationRequest(string sourceKind, string message, string? regenerationGuidance)
    {
        if (!string.Equals(sourceKind, "completion_suggestion", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        var combined = string.Join("\n", message ?? string.Empty, regenerationGuidance ?? string.Empty);
        if (string.IsNullOrWhiteSpace(combined))
        {
            return false;
        }

        return ContainsAny(
            combined,
            "strict 7 route-profile",
            "RPG iteration plan as strict 7",
            "JRPG first-loop capability steps",
            "RPG iteration plan as JRPG first-loop capabilities",
            "visible MapScene with stable movement first",
            "reward 3-choice understandability fourth",
            "full playable acceptance seventh",
            "final first-loop acceptance");
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
        string RouteSkillId,
        IReadOnlyList<PrototypeIterationPlanStageTelemetryResult> StageTelemetry);

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

    private sealed record IterationGoalBuildResult(
        List<PrototypeIterationPlanGoalResult> Goals,
        bool UsedScaffoldFallback,
        IReadOnlyList<PrototypeIterationPlanStageTelemetryResult>? StageTelemetry = null);
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
