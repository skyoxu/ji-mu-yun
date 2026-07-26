using System.Text;
using System.Text.Json;
using System.Security.Cryptography;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Workflow;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeRepairPlanService
{
    private const string SourceKind = "repair_plan";
    private const string ExecuteRunType = "prototype-repair-step";
    private static readonly CodexChatClientOptions RepairPlanningCodexOptions = new(
        IgnoreRules: true,
        ReasoningEffort: "minimal");

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PrototypeQuickFixService _quickFixService;
    private readonly PrototypeRouteStateWriter _stateWriter;
    private readonly PrototypeContractService _contractService;
    private readonly ILlmRouteEngine? _llmRouteEngine;
    private readonly HostedContextManifestIssuer? _contextManifestIssuer;

    public PrototypeRepairPlanService(
        PhaseAMetadataStore metadataStore,
        PrototypeQuickFixService quickFixService,
        ICodexChatClient? codexChatClient = null)
        : this(metadataStore, quickFixService, new PrototypeRouteStateWriter(), new PrototypeContractService(), codexChatClient)
    {
    }

    public PrototypeRepairPlanService(
        PhaseAMetadataStore metadataStore,
        PrototypeQuickFixService quickFixService,
        PrototypeRouteStateWriter stateWriter,
        PrototypeContractService? contractService = null,
        ICodexChatClient? codexChatClient = null,
        ILlmRouteEngine? llmRouteEngine = null,
        HostedContextManifestIssuer? contextManifestIssuer = null)
    {
        _metadataStore = metadataStore;
        _quickFixService = quickFixService;
        _stateWriter = stateWriter;
        _contractService = contractService ?? new PrototypeContractService();
        _llmRouteEngine = llmRouteEngine ?? (codexChatClient is null ? null : new LlmRouteEngine(codexChatClient));
        _contextManifestIssuer = contextManifestIssuer;
    }

    public async Task<PrototypeRepairPlanResult> CreateAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await RequireProjectAsync(accountId, projectId, cancellationToken);
        var routeProfile = PrototypeRouteSkillPolicy.ResolveProfile(project);
        var promptAuthorities = BuildPromptAuthorities(project, routeProfile);

        var failedRun = await FindLatestFailedRunAsync(project.ProjectId, cancellationToken);
        if (failedRun is null)
        {
            return new PrototypeRepairPlanResult("", "missing_failure", "当前项目没有可用于生成修复计划的失败记录。", []);
        }

        var prototypeContract = _contractService.Read(project);
        var failureText = BuildFailureText(project, failedRun);
        var planContext = BuildPlanContext(project, prototypeContract, failedRun, failureText, routeProfile, promptAuthorities);
        var goals = await BuildRepairGoalsAsync(project, planContext, cancellationToken);
        var summary = $"已基于最近一次失败生成 {goals.Count} 个修复任务。请逐项执行，最后一步必须做全量验收。";
        var session = await _metadataStore.CreateProjectIterationSessionAsync(
            accountId,
            project.ProjectId,
            SourceKind,
            BuildSourceMessage(failedRun, failureText, routeProfile, promptAuthorities),
            $"通过小而独立的修复任务修复失败的原型路由：{routeProfile.GameTypeId}。",
            goals.Select(goal => new ProjectIterationGoalCreateCommand(
                goal.GoalIndex,
                goal.Title,
                goal.Description,
                goal.AcceptanceHint)).ToArray(),
            cancellationToken);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(session.SessionId, "ready", 0, summary, null, null, cancellationToken);

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, SourceKind, cancellationToken);
        _stateWriter.WriteRepairPlanState(project, new
        {
            route = "repair-plan",
            source_kind = SourceKind,
            source_run_id = failedRun.RunId,
            session_id = session.SessionId,
            status = "ready",
            summary,
            game_type_profile = routeProfile,
            source_boundary = "gdd_derived_contract_only_after_gdd_generation",
            prompt_authority_binding = BuildPromptAuthorityState(promptAuthorities),
            prototype_contract = prototypeContract.RelativePath,
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
        var routeProfile = PrototypeRouteSkillPolicy.ResolveProfile(project);
        var promptAuthorities = BuildPromptAuthorities(project, routeProfile);

        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, SourceKind, cancellationToken);
        if (details is null)
        {
            return new PrototypeRepairStepExecutionResult("", "", "", "missing_repair_plan", "当前项目还没有修复计划，请先生成修复计划。", 0, false, "missing_repair_plan");
        }

        if (!SessionPromptAuthoritiesMatch(details.Session.SourceMessage, promptAuthorities))
        {
            return new PrototypeRepairStepExecutionResult(
                details.Session.SessionId,
                "",
                "",
                "blocked_by_stale_recovery_authority",
                "修复计划的路由权限来源已经变化，请重新生成修复计划后再执行。",
                details.Session.CurrentGoalIndex,
                true,
                details.Session.Status);
        }

        var current = details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "needs_fix", StringComparison.OrdinalIgnoreCase))
                      ?? details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "failed", StringComparison.OrdinalIgnoreCase))
                      ?? details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "pending", StringComparison.OrdinalIgnoreCase));
        if (current is null)
        {
            return new PrototypeRepairStepExecutionResult(details.Session.SessionId, "", "", "no_pending_repair_step", "当前修复计划没有待执行步骤。", details.Session.CurrentGoalIndex, false, details.Session.Status);
        }

        if (IsServiceRestartRecoveryGoal(current))
        {
            return await CompleteServiceRestartRecoveryStepWithoutCodexAsync(project, details, current, routeProfile, cancellationToken);
        }

        await _metadataStore.UpdateProjectIterationGoalStatusAsync(current.GoalId, "running", current.ResultSummary, null, cancellationToken);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "running", current.GoalIndex, $"正在执行修复任务 {current.GoalIndex}。", null, null, cancellationToken);

        var projectExecutionGuide = _stateWriter.ReadOrCreateProjectExecutionGuide(project, _contractService.Read(project));
        var feedback = BuildStepFeedback(project, details, current, request.Feedback, projectExecutionGuide, promptAuthorities);
        var result = await _quickFixService.SubmitAsync(
            project.AccountId,
            project.ProjectId,
            new PrototypeFeedbackRequest(
                feedback,
                request.Model,
                null,
                new PrototypeGoalRepairContext(
                    details.Session.SessionId,
                    current.GoalId,
                    current.GoalIndex,
                    current.Title,
                    current.Description,
                    current.AcceptanceHint,
                    current.ResultSummary)),
            requireSucceededPrototypeRun: false,
            cancellationToken);

        var runCompleted = string.Equals(result.Status, "completed", StringComparison.OrdinalIgnoreCase);
        var goalStatus = NormalizeRepairGoalStatus(result.IterationGoalStatus, runCompleted);
        var goalCompleted = string.Equals(goalStatus, "succeeded", StringComparison.OrdinalIgnoreCase);
        await _metadataStore.UpdateProjectIterationGoalStatusAsync(
            current.GoalId,
            goalStatus,
            result.AssistantMessage,
            goalCompleted ? DateTimeOffset.UtcNow.ToString("O") : null,
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
        var summary = goalCompleted
            ? $"修复任务 {current.GoalIndex} 已完成。"
            : $"修复任务 {current.GoalIndex} 仍需继续修复。";
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(refreshed.Session.SessionId, sessionStatus, current.GoalIndex, summary, null, sessionStatus == "completed" ? DateTimeOffset.UtcNow.ToString("O") : null, CancellationToken.None);

        _stateWriter.WriteRepairPlanExecutionState(project, current.GoalIndex, new
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
            prompt_authority_binding = BuildPromptAuthorityState(promptAuthorities),
            summary,
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });
        _stateWriter.WriteRepairPlanState(project, BuildRepairPlanState(project, refreshed, sessionStatus, summary, routeProfile));

        return new PrototypeRepairStepExecutionResult(refreshed.Session.SessionId, current.GoalId, result.RunId, result.Status, summary, current.GoalIndex, true, sessionStatus);
    }

    private async Task<PrototypeRepairStepExecutionResult> CompleteServiceRestartRecoveryStepWithoutCodexAsync(
        ProjectSnapshot project,
        ProjectIterationSessionDetails details,
        ProjectIterationGoalSnapshot current,
        GameTypeRouteProfile routeProfile,
        CancellationToken cancellationToken)
    {
        const string status = "blocked_by_revalidation_required";
        const string sessionStatus = "needs_fix";
        const string goalStatus = "needs_fix";
        const string summary = "Service restart recovery requires rerunning prototype acceptance; no hosted game file repair was executed.";

        await _metadataStore.UpdateProjectIterationGoalStatusAsync(current.GoalId, goalStatus, summary, null, cancellationToken);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, sessionStatus, current.GoalIndex, summary, null, null, cancellationToken);

        var refreshed = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, SourceKind, cancellationToken)
            ?? details;

        _stateWriter.WriteRepairPlanExecutionState(project, current.GoalIndex, new
        {
            route = "execute-repair-step",
            source_kind = SourceKind,
            session_id = refreshed.Session.SessionId,
            run_id = "",
            goal_id = current.GoalId,
            goal_index = current.GoalIndex,
            status,
            goal_status = goalStatus,
            session_status = sessionStatus,
            prompt_authority_binding = BuildPromptAuthorityState(BuildPromptAuthorities(project, routeProfile)),
            summary,
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });
        _stateWriter.WriteRepairPlanState(project, BuildRepairPlanState(project, refreshed, sessionStatus, summary, routeProfile));

        return new PrototypeRepairStepExecutionResult(refreshed.Session.SessionId, current.GoalId, "", status, summary, current.GoalIndex, true, sessionStatus);
    }

    private object BuildRepairPlanState(
        ProjectSnapshot project,
        ProjectIterationSessionDetails details,
        string status,
        string summary,
        GameTypeRouteProfile routeProfile)
    {
        return new
        {
            route = "repair-plan",
            source_kind = SourceKind,
            session_id = details.Session.SessionId,
            status,
            summary,
            source_message = details.Session.SourceMessage,
            game_type_profile = routeProfile,
            source_boundary = "gdd_derived_contract_only_after_gdd_generation",
            prompt_authority_binding = BuildPromptAuthorityState(BuildPromptAuthorities(project, routeProfile)),
            goals = details.Goals.Select(goal => new
            {
                goal.GoalIndex,
                goal.Title,
                goal.Description,
                goal.AcceptanceHint,
                goal.Status,
                goal.ResultSummary,
                goal.CompletedUtc
            }).ToArray(),
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        };
    }

    private static string NormalizeRepairGoalStatus(string? iterationGoalStatus, bool runCompleted)
    {
        if (string.Equals(iterationGoalStatus, "succeeded", StringComparison.OrdinalIgnoreCase))
        {
            return "succeeded";
        }

        if (string.Equals(iterationGoalStatus, "needs_fix", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(iterationGoalStatus, "failed", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(iterationGoalStatus, "running", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(iterationGoalStatus, "pending", StringComparison.OrdinalIgnoreCase))
        {
            return "needs_fix";
        }

        return runCompleted ? "succeeded" : "needs_fix";
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

    private static string BuildFailureText(ProjectSnapshot project, RunSnapshot run)
    {
        return string.Join("\n", run.ProgressLabel, run.StderrText, run.StdoutText, run.EvidenceJson, BuildGdUnitFailureContext(project, run))
            .Trim();
    }

    private static string BuildGdUnitFailureContext(ProjectSnapshot project, RunSnapshot run)
    {
        if (string.IsNullOrWhiteSpace(run.EvidenceJson) ||
            !run.EvidenceJson.Contains("rpg_gdunit_validation", StringComparison.OrdinalIgnoreCase))
        {
            return "";
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            if (!document.RootElement.TryGetProperty("rpg_gdunit_validation", out var validation) ||
                validation.ValueKind != JsonValueKind.Object)
            {
                return "";
            }

            var gdUnitPath = ReadString(validation, "gdunit_path");
            var reportDir = ReadString(validation, "report_dir");
            var reason = ReadString(validation, "reason");
            var lines = new List<string>
            {
                "RPG GdUnit validation context:",
                $"- reason: {reason}",
                $"- gdunit_path: {gdUnitPath}",
                $"- report_dir: {reportDir}"
            };

            var consolePath = ResolveReportFile(project.RepoPath, reportDir, "gdunit-console.txt");
            if (!string.IsNullOrWhiteSpace(consolePath) && File.Exists(consolePath))
            {
                lines.Add("- gdunit_console_summary:");
                lines.AddRange(ExtractGdUnitErrorSummary(File.ReadAllText(consolePath), maxLines: 40).Select(line => $"  {line}"));
            }

            var summaryPath = ResolveReportFile(project.RepoPath, reportDir, "run-summary.json");
            if (!string.IsNullOrWhiteSpace(summaryPath) && File.Exists(summaryPath))
            {
                lines.Add("- gdunit_run_summary:");
                lines.Add($"  {Trim(File.ReadAllText(summaryPath), 1200)}");
            }

            return string.Join("\n", lines);
        }
        catch (JsonException)
        {
            return "";
        }
        catch (IOException)
        {
            return "";
        }
        catch (UnauthorizedAccessException)
        {
            return "";
        }
    }

    private static string BuildSourceMessage(
        RunSnapshot run,
        string failureText,
        GameTypeRouteProfile routeProfile,
        RepairPromptAuthorityBinding promptAuthorities)
    {
        return JsonSerializer.Serialize(new
        {
            source_run_id = run.RunId,
            source_run_type = run.RunType,
            source_status = run.Status,
            game_type_profile = routeProfile,
            source_boundary = "gdd_derived_contract_only_after_gdd_generation",
            prompt_authority_binding = BuildPromptAuthorityState(promptAuthorities),
            failure_excerpt = Trim(failureText, 4000),
            failure_signals = ExtractRepairEvidenceSummary(failureText, maxLines: 40)
        });
    }

    private static PrototypeRepairPlanContext BuildPlanContext(
        ProjectSnapshot project,
        PrototypeContractSnapshot contract,
        RunSnapshot failedRun,
        string failureText,
        GameTypeRouteProfile routeProfile,
        RepairPromptAuthorityBinding promptAuthorities)
    {
        return new PrototypeRepairPlanContext(routeProfile, contract, failedRun, failureText, promptAuthorities);
    }

    private async Task<List<PrototypeRepairGoalResult>> BuildRepairGoalsAsync(
        ProjectSnapshot project,
        PrototypeRepairPlanContext context,
        CancellationToken cancellationToken)
    {
        if (string.Equals(context.RouteProfile.GameTypeId, "rpg", StringComparison.OrdinalIgnoreCase))
        {
            if (ShouldUseServiceRestartRecoveryRepairPlan(context))
            {
                return BuildServiceRestartRecoveryRepairGoals(context);
            }

            if (ShouldUseBuildCleanupRepairPlan(context))
            {
                return BuildRpgBuildCleanupRepairGoals(context);
            }

            if (ShouldUseRpgGdUnitValidationRepairPlan(context))
            {
                return BuildRpgGdUnitValidationRepairGoals(context);
            }

            if (ShouldUseSceneNodeContractRepairPlan(context))
            {
                return BuildRpgSceneNodeContractRepairGoals(context);
            }

            var planned = await TryBuildRpgRepairGoalsFromModelAsync(project, context, cancellationToken);
            if (planned.Count > 0)
            {
                return planned;
            }

            return BuildRpgRepairGoals(context);
        }

        return BuildGenericRepairGoals(context);
    }

    private static bool ShouldUseServiceRestartRecoveryRepairPlan(PrototypeRepairPlanContext context)
    {
        return ContainsAny(
            context.FailureText,
            "interrupted_by_service_restart",
            "service_restart_recovery",
            "service restarted before completion",
            "Run was interrupted because the service restarted before completion");
    }

    private static List<PrototypeRepairGoalResult> BuildServiceRestartRecoveryRepairGoals(PrototypeRepairPlanContext context)
    {
        return
        [
            new PrototypeRepairGoalResult(
                1,
                "服务重启后恢复第 7 步最终摘要",
                $"""
                失败运行在第 7 步生成最终摘要时被服务重启中断。不要从玩法、地图、战斗、奖励、证据、TDD、缓存或构建代码编辑开始。先恢复路由完成路径：保留最新成功原型产物，重跑或恢复最终摘要生成，并在不丢失原型合同的前提下写入最终完成状态。

                失败来源：
                {Trim(context.FailureText, 1200)}
                """,
                "只有原型路由在服务重启恢复后可以到达最终摘要/完成状态，而不是停在 interrupted_by_service_restart 时，本任务才算通过。",
                "pending"),
            new PrototypeRepairGoalResult(
                2,
                "重新验证现有 RPG 可玩证据",
                "修改玩法代码前，先验证现有 RPG 原型产物。确认上一次通过的 TDD/GdUnit 证据、Godot smoke 证据、原型记录、旁路合同和完成产物仍然存在且一致。",
                "只有现有原型证据可读，并且没有把陈旧的服务重启失败误当成玩法缺陷时，本任务才算通过。",
                "pending"),
            new PrototypeRepairGoalResult(
                3,
                "恢复后再运行 RPG 最终验收",
                "服务重启恢复路径稳定后，运行 RPG 最终验收门禁。只有该验收报告具体地图、移动、战斗、奖励、胜负、素材或 UI 失败时，后续修复任务才应修改游戏文件。",
                "只有最终 RPG 验收成功，或报告了与 service_restart_recovery 无关的新具体玩法阻塞项时，修复计划才算完成。",
                "pending")
        ];
    }

    private async Task<List<PrototypeRepairGoalResult>> TryBuildRpgRepairGoalsFromModelAsync(
        ProjectSnapshot project,
        PrototypeRepairPlanContext context,
        CancellationToken cancellationToken)
    {
        if (_llmRouteEngine is null)
        {
            return [];
        }

        var prompt = BuildRpgRepairGoalPrompt(project, context);
        HostedContextEnvelope? envelope = null;
        if (_contextManifestIssuer is not null)
        {
            try
            {
                envelope = await _contextManifestIssuer.IssueAsync(
                    new HostedContextManifestIssue(
                        project.AccountId,
                        project.ProjectId,
                        "llm:repair-plan",
                        Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(string.Join("\n", project.ProjectId, project.AccountId, prompt)))).ToLowerInvariant(),
                        "repair-plan.v1",
                        TimeSpan.FromMinutes(5)),
                    cancellationToken);
            }
            catch (InvalidOperationException)
            {
                return [];
            }
        }

        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                EnsureRepairPlanPromptWorkspace(project),
                "repair-plan",
                PrototypeModelPolicy.Normalize("gpt-5.4"),
                prompt,
                RepairPlanningCodexOptions,
                project.AccountId,
                RequireJsonObject: true,
                OperationKey: "llm:repair-plan",
                ContextEnvelope: envelope),
            cancellationToken);
        if (!completion.Succeeded)
        {
            return [];
        }

        return ParseRepairGoalPlan(completion.JsonObjectText ?? completion.AssistantMessage);
    }

    private static List<PrototypeRepairGoalResult> BuildRpgRepairGoals(PrototypeRepairPlanContext context)
    {
        if (ShouldUseNavigationFirstRepairPlan(context))
        {
            return BuildRpgNavigationFirstRepairGoals(context);
        }

        var goals = new List<PrototypeRepairGoalResult>();
        void Add(string title, string description, string acceptance)
        {
            if (goals.Any(goal => string.Equals(goal.Title, title, StringComparison.OrdinalIgnoreCase)))
            {
                return;
            }

            goals.Add(new PrototypeRepairGoalResult(goals.Count + 1, title, description, acceptance, "pending"));
        }

        Add(
            "恢复原型运行证据与 TDD 绿灯",
            BuildRpgEvidenceRepairDescription(context),
            """
            只有最新运行阻塞已经移除，并且原型路由可以写入完成/TDD 证据且没有权限、构建或缓存锁失败时，本任务才算通过。
            如果最新失败证据仍然阻塞路由完成产物，不要报告本任务成功。
            """);

        Add(
            "修复 RPG 场景与节点合同",
            BuildRpgSceneContractRepairDescription(context),
            """
            只有当前 RPG 原型具备已选择能力所需的合同对齐场景结构，包括主原型壳、MapScene，以及必需命名的地图/玩家素材节点时，本任务才算通过。敌人素材节点和 BattleScene 只在战斗/冲突能力或最新失败证据点名时加入。
            继续前必须消除场景/脚本合同漂移。
            """);

        Add(
            "修复 RPG 玩法合同与表单追踪",
            BuildRpgGameplayContractRepairDescription(context),
            """
            只有 prototype-contract 的 form_fields 和 input_traceability 中的具体用户表单值被体现在玩法行为、UI/状态反馈、测试或明确的需要修复阻塞项中时，本任务才算通过。
            不要用 RPG 模板默认值替换具体项目值。
            """);

        Add(
            "执行最终全量验收",
            "运行 RPG 类型要求的最终 smoke/导航/可见性/合同一致性验收，确认修复闭环。",
            "最终验收通过后，原型修复才算完成。");

        return goals;
    }

    private static bool ShouldUseBuildCleanupRepairPlan(PrototypeRepairPlanContext context)
    {
        var failureText = context.FailureText;
        var hasDuplicateAssemblySignal = ContainsAny(
            failureText,
            "CS0579",
            "AssemblyInfo",
            "TargetFrameworkAttribute",
            ".NETCoreApp,Version",
            "duplicate assembly attribute");
        var hasGeneratedBuildPath = ContainsAny(
            failureText,
            @"Game.Core\obj\Debug",
            "Game.Core/obj/Debug",
            @"Game.Core\obj\Release",
            "Game.Core/obj/Release",
            @"Game.Core.Tests\obj\Debug",
            "Game.Core.Tests/obj/Debug",
            @"Game.Core.Tests\obj\Release",
            "Game.Core.Tests/obj/Release",
            @"buildcache\int",
            "buildcache/int");

        return hasDuplicateAssemblySignal && hasGeneratedBuildPath;
    }

    private static bool ShouldUseSceneNodeContractRepairPlan(PrototypeRepairPlanContext context)
    {
        if (HasEvidenceRecoveryFailure(context))
        {
            return false;
        }

        return ContainsAny(
            context.FailureText,
            "Node not found",
            "get_node",
            "BattleStatusLabel",
            "relative to",
            "scene/main/node.cpp",
            "rpg_scene_node_contract_drift",
            "rpg_script_node_contract_drift");
    }

    private static bool ShouldUseRpgGdUnitValidationRepairPlan(PrototypeRepairPlanContext context)
    {
        if (HasEvidenceRecoveryFailure(context))
        {
            return false;
        }

        return ContainsAny(
            context.FailureText,
            "rpg_gdunit_validation",
            "rpg_project_specific_gdunit_failed",
            "RPG GdUnit validation context",
            "tests/Prototype/DqRpgPrototype",
            "gdunit-console.txt");
    }

    private static List<PrototypeRepairGoalResult> BuildRpgGdUnitValidationRepairGoals(PrototypeRepairPlanContext context)
    {
        var goals = new List<PrototypeRepairGoalResult>();

        void Add(string title, string description, string acceptance)
        {
            goals.Add(new PrototypeRepairGoalResult(goals.Count + 1, title, description, acceptance, "pending"));
        }

        Add(
            "修复 RPG 运行素材与 Godot 导入",
            BuildRpgGdUnitAssetRepairDescription(context),
            """
            只有已选择能力对应的 dq-rpg 活跃场景不再引用缺失的 PNG 或 .ctex 资源，GdUnit 可以加载 MapScene.tscn，并且仅在战斗/冲突能力被选择或最新失败点名时加载 BattleScene.tscn 且没有 ext_resource 解析错误时，本任务才算通过。
            """);

        Add(
            "修复 DqRpgPrototype 测试要求的 RPG 场景节点合同",
            BuildRpgGdUnitNodeRepairDescription(context),
            """
            只有项目专属 GdUnit 套件要求的节点路径存在，或测试与脚本被同步更新到同一个权威 RPG 合同，并且不再出现 Node not found 错误时，本任务才算通过。
            """);

        Add(
            "修复已验证场景合同下的 RPG 脚本输入与循环行为",
            BuildRpgGdUnitScriptRepairDescription(context),
            """
            只有 Invalid call to _UnhandledInput 消失，并且地图移动、遇敌入口、战斗、奖励 3 选 1 和返回地图行为都能通过 GdUnit 使用的同一场景路径运行时，本任务才算通过。
            """);

        Add(
            "修复 RPG 行为时保持项目输入合同",
            BuildRpgGdUnitContractRepairDescription(context),
            """
            只有运行时、UI 或测试证据保留了项目具体值，例如 15 场战斗胜利、任一战斗失败即失败、奖励 3 选 1 和可读战斗理解反馈，并且没有替换成更短的模板默认胜利次数时，本任务才算通过。
            """);

        Add(
            "重跑 RPG 项目专属 GdUnit 与最终原型项目验收",
            BuildRpgGdUnitFinalAcceptanceDescription(context),
            """
            只有 `tests/Prototype/DqRpgPrototype` 运行 rc=0、没有 "No test cases found"、没有 Godot ERROR/SCRIPT ERROR 标记，并且前台“重新触发原型项目验收”路由成功时，修复才算完成。
            """);

        return goals;
    }

    private static List<PrototypeRepairGoalResult> BuildRpgBuildCleanupRepairGoals(PrototypeRepairPlanContext context)
    {
        var goals = new List<PrototypeRepairGoalResult>();

        void Add(string title, string description, string acceptance)
        {
            goals.Add(new PrototypeRepairGoalResult(goals.Count + 1, title, description, acceptance, "pending"));
        }

        Add(
            "构建清理：先移除陈旧生成目录",
            BuildRpgBuildCleanupRepairDescription(context),
            """
            只有仓库内 Game.Core 与 Game.Core.Tests 的 obj/bin/buildcache 目录被安全清理，陈旧输出里的 AssemblyInfo 文件不再参与编译，并且 CS0579 重复程序集属性失败消失时，本任务才算通过。
            """);

        Add(
            "构建清理后重跑原型 TDD green",
            "重跑 RPG 原型 TDD green 通道，并在把剩余失败视为玩法或场景合同问题前，确认 dotnet 验证步骤已经通过。",
            """
            只有最新原型 TDD green 运行不再因为 CS0579、AssemblyInfo、TargetFrameworkAttribute 或 obj/bin/buildcache 污染信号而在 dotnet build/test 步骤失败时，本任务才算通过。
            """);

        Add(
            "仅在 TDD 仍失败时检查 RPG 场景与玩法",
            "如果干净构建通过但原型仍失败，检查剩余失败输出，并修复新证据点名的具体 RPG 场景、导航、战斗、奖励或表单可追溯合同。",
            """
            本任务只能在构建污染清除后开始。只有剩余 RPG 合同失败按当前失败证据修复，而不是按通用模板修复时，本任务才算通过。
            """);

        Add(
            "干净验证后的最终全量验收",
            "在构建清理和所有证据驱动的玩法修复完成后，运行 RPG 原型最终验收。",
            "只有最终原型路由和验证证据都通过，并且构建污染没有复发时，修复才算完成。");

        return goals;
    }

    private static List<PrototypeRepairGoalResult> BuildRpgSceneNodeContractRepairGoals(PrototypeRepairPlanContext context)
    {
        var goals = new List<PrototypeRepairGoalResult>();

        void Add(string title, string description, string acceptance)
        {
            goals.Add(new PrototypeRepairGoalResult(goals.Count + 1, title, description, acceptance, "pending"));
        }

        Add(
            "修复 RPG 场景/脚本节点合同不匹配",
            BuildRpgSceneNodeContractRepairDescription(context),
            """
            只有最新 Godot 错误点名的节点路径存在于活跃原型场景中，或脚本绑定被修正到真实合同路径，并且原型导航 smoke 中不再出现 Node not found 错误时，本任务才算通过。
            """);

        Add(
            "重跑 Start Adventure 导航与已选择能力 smoke",
            "重跑面向用户的 Start Adventure 路径并确认 MapScene 仍可见，然后触发此前需要缺失节点的已选择能力路径。只有战斗/冲突能力被选择或最新失败点名时才触发 BattleScene。",
            """
            只有 Start Adventure 到可见 MapScene 仍通过，并且已选择能力的 UI 路径不再因为缺失 Label 或陈旧脚本绑定崩溃时，本任务才算通过。BattleScene 仅在战斗/冲突能力被选择或最新失败点名时属于本次 smoke 范围。
            """);

        Add(
            "节点修复后验证 RPG 奖励与胜负合同",
            "场景/脚本绑定稳定后，验证奖励 3 选 1 返回地图，以及 15 场战斗胜利、任一战斗失败即失败这些具体表单规则。",
            """
            只有奖励 3 选 1、返回地图、15 场战斗胜利和任一战斗失败即失败在运行时行为、UI/状态反馈或明确证据中可见时，本任务才算通过。
            """);

        Add(
            "场景合同修复后的最终全量验收",
            "在节点合同修复和后续玩法检查完成后，运行 RPG 原型最终验收。",
            "只有最终原型路由和验证证据都通过，并且没有 Node not found 或场景/脚本合同漂移复发时，修复才算完成。");

        return goals;
    }

    private static bool ShouldUseNavigationFirstRepairPlan(PrototypeRepairPlanContext context)
    {
        var failure = context.FailureText;
        if (string.IsNullOrWhiteSpace(failure))
        {
            return false;
        }

        var hasNavigationSignal =
            ContainsAny(failure,
                "Start Adventure",
                "MapScene",
                "visible map",
                "visible MapScene",
                "navigation",
                "main menu") ||
            ContainsAny(context.FailedRun.ProgressLabel ?? string.Empty,
                "navigation",
                "MapScene");

        if (!hasNavigationSignal)
        {
            return false;
        }

        return !HasEvidenceRecoveryFailure(context);
    }

    private static bool HasEvidenceRecoveryFailure(PrototypeRepairPlanContext context)
    {
        return ContainsAny(
            context.FailureText,
            "Permission denied",
            "permission denied",
            "Access is denied",
            "write failure",
            "cache lock",
            "build failure",
            "missing completion artifacts",
            "missing artifact",
            "artifact write");
    }

    private static List<PrototypeRepairGoalResult> BuildRpgNavigationFirstRepairGoals(PrototypeRepairPlanContext context)
    {
        var goals = new List<PrototypeRepairGoalResult>();

        void Add(string title, string description, string acceptance)
        {
            goals.Add(new PrototypeRepairGoalResult(goals.Count + 1, title, description, acceptance, "pending"));
        }

        Add(
            "修复 Start Adventure 到可见 MapScene 入口",
            BuildRpgNavigationRepairDescription(context),
            """
            只有 Start Adventure 能稳定展示真实可玩的 MapScene，隐藏陈旧的纯菜单状态，并从用户入口显示可见地图标记时，本任务才算通过。
            """);

        Add(
            "修复 RPG 奖励闭环与地图返回",
            BuildRpgRewardLoopRepairDescription(context),
            """
            只有战斗胜利能进入可读的奖励 3 选 1 流程，至少一个选项可应用，并且玩家能返回活跃地图循环时，本任务才算通过。
            当项目合同明确要求奖励时，不要静默降级为模板默认省略。
            """);

        Add(
            "修复 RPG 胜负条件与表单硬约束落地",
            BuildRpgWinFailRepairDescription(context),
            """
            只有 15 场战斗胜利、任一战斗失败即失败、遇敌规则、属性规则等具体用户表单值能体现在玩法行为、可读 UI/状态反馈或明确的需要修复阻塞项中时，本任务才算通过。
            """);

        Add(
            "执行最终全量验收",
            "运行 RPG 类型要求的最终 smoke、导航、可见性、奖励闭环、胜负条件与合同一致性验收，确认修复闭环。",
            "最终验收通过后，原型修复才算完成。");

        return goals;
    }

    private static List<PrototypeRepairGoalResult> BuildGenericRepairGoals(PrototypeRepairPlanContext context)
    {
        var goals = new List<PrototypeRepairGoalResult>();
        void Add(string title, string description, string acceptance)
        {
            if (goals.Any(goal => string.Equals(goal.Title, title, StringComparison.OrdinalIgnoreCase)))
            {
                return;
            }

            goals.Add(new PrototypeRepairGoalResult(goals.Count + 1, title, description, acceptance, "pending"));
        }

        Add(
            "恢复原型运行证据",
            BuildGenericEvidenceRepairDescription(context),
            "最新失败原因已经消除，并且原型路由可以生成完成证据，没有构建、缓存或写入失败。");

        Add(
            "修复通用原型合同缺口",
            BuildGenericContractRepairDescription(context),
            "GDD 派生的项目原型合同已经体现在修复后的输出中，并且没有新的原型漂移。");

        Add(
            "执行最终全量验收",
            "运行当前类型要求的最终 smoke/导航/可见性验收，确认修复闭环。",
            "最终验收通过后，原型修复才算完成。");

        return goals;
    }

    private static string BuildRpgEvidenceRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair the latest failed prototype route evidence path using the GDD-derived project contract and failure output.

            Required repair scope:
            - Read the current project README and prototype contract first.
            - Do not read docs/game-type-guides, docs/prototype-type-kits, or route skill documents to add gameplay requirements.
            - Use the latest failed run output as the source of truth for what broke.
            - Restore writable completion artifacts, TDD green evidence, and build outputs needed by the prototype route.
            - Do not broaden this step into gameplay or scene redesign.
            - Preserve browser-safe output.
            """;
    }

    private static string BuildRpgBuildCleanupRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            最新 RPG 原型失败属于 .NET 构建污染，不是玩法设计失败。修改场景或玩法逻辑前，先清理仓库内构建输出。

            本任务重点：
            - 只移除当前原型仓库和目标 dotnet 项目内的陈旧 obj/bin/buildcache 目录。
            - 确认生成的 AssemblyInfo 与 TargetFrameworkAttribute 文件不会被陈旧输出重复编译。
            - 重跑 dotnet 验证步骤，并保留最新结果作为证据。
            - CS0579 消失前，不要开始 RPG 场景或玩法修复。

            证据来源：
            - 使用修复计划源失败记录中的具体编译错误和生成构建路径。
            """;
    }

    private static string BuildRpgSceneNodeContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            最新 RPG 原型失败属于 Godot 场景/脚本节点合同不匹配，不是构建缓存失败。扩展玩法前，先修复引擎错误点名的缺失节点路径或脚本绑定。

            本任务重点：
            - 以最新 Godot 错误作为事实来源。
            - 如果缺少 BattleStatusLabel 这类必需 UI 节点，就把它添加到活跃原型脚本期望的路径，或把脚本更新到权威场景路径。
            - 保持 Start Adventure -> 可见 MapScene 行为不退化。
            - 不要把 .godot/mono/temp/obj/Debug source-generator 栈路径误判为 CS0579 构建污染。

            证据来源：
            - 使用修复计划源失败记录里的具体 Godot 节点/脚本错误和堆栈上下文。
            """;
    }

    private static string BuildRpgGdUnitAssetRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            最新 RPG 项目专属 GdUnit 验证在加载具体 Godot 资源时失败。先修复资源引用，再考虑更广泛的玩法调整。

            本任务重点：
            - 修复 GdUnit 控制台摘要点名的缺失运行素材或场景 ext_resource 路径。
            - 确保 MapScene.tscn 等已选择路线场景，以及仅在战斗/冲突能力被选择或最新失败点名时需要的 BattleScene.tscn，不再引用缺失 PNG 或陈旧 .godot/imported .ctex 文件。
            - 复制或恢复素材后，通过项目工作流执行 Godot 导入。
            - 如果仍有 Parse Error 或 Failed loading resource，不得标记本任务完成。

            证据来源：
            - 使用修复计划源失败记录里的具体缺失资源、解析错误和 GdUnit 控制台行。
            """;
    }

    private static string BuildRpgGdUnitNodeRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            修复项目专属 DqRpgPrototype GdUnit 测试验证的 RPG 场景/节点合同。

            本任务重点：
            - 必需测试路径包含已选择能力节点，例如 CanvasLayer/UI/MapScene/RpgMapAsset、RpgPlayerAsset、RpgEnemyAsset、ChestToken；CanvasLayer/UI/BattleScene/EnemyToken 仅在最新失败点名或战斗/冲突能力被选择时需要。
            - 保持场景脚本和测试合同一致；不要移动节点却不同时更新运行时代码和测试使用的权威场景路径。
            - 保持 Start Adventure -> 可见 MapScene 行为。

            证据来源：
            - 使用修复计划源失败记录中 GdUnit 报告的具体节点路径不匹配。
            """;
    }

    private static string BuildRpgGdUnitScriptRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            在资源和节点合同稳定后，修复 RPG GdUnit 暴露的脚本/运行时错误。

            本任务重点：
            - 移除无效调用，例如在不暴露 _UnhandledInput 的 Control 基类上调用该函数。
            - 保持移动、遇敌入口、战斗结算、奖励 3 选 1 和返回地图都能通过测试使用的同一个原型壳调用。
            - 不要通过削弱或删除项目专属 GdUnit 测试来绕过失败行为。

            证据来源：
            - 使用修复计划源失败记录中 GdUnit 报告的具体脚本/运行时错误。
            """;
    }

    private static string BuildRpgGdUnitContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            修复玩法行为，同时不得偏离项目原型合同。

            本任务重点：
            - 具体项目输入值优先于 RPG 默认值和模板示例。
            - 保留奖励 3 选 1 和可见的战斗理解反馈。
            - 保留合同里的项目胜负条件；除非用户合同要求，不要把 15 场战斗胜利替换成更短的 RPG 模板默认胜利次数。
            - 任何未实现的具体输入都必须成为明确的需要修复阻塞项。

            合同来源：
            - 使用当前原型合同 JSON 和路由技能合同作为权威项目输入。
            - 使用修复计划源失败记录中的最新验证阻塞项。
            """;
    }

    private static string BuildRpgGdUnitFinalAcceptanceDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            针对生成本修复计划的同一个阻塞项执行 RPG 最终验证。

            必需验证：
            - 项目专属 GdUnit 路径：tests/Prototype/DqRpgPrototype。
            - 即使 normalized_rc 为 0，只要包装输出 GDUNIT_DONE rc=1 就视为失败。
            - No test cases found 视为失败。
            - GdUnit 干净后，重跑前台原型项目验收路由。

            证据来源：
            - 使用修复计划源失败记录中必须转绿的具体验证阻塞项。
            """;
    }

    private static string BuildRpgSceneContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair the scene and node contract using the GDD-derived prototype contract.

            Contract requirements:
            - The project prototype contract is authoritative.
            - MapScene and the main prototype shell must have clear responsibilities.
            - BattleScene must have clear responsibilities only when battle/conflict capability is selected or named by the latest failure.
            - Map and player asset instances must use the RPG contract naming rules; enemy asset instances are required only for selected conflict/battle capabilities or failures that name them.
            - Main.tscn default-hidden VBox, Overlays, and ScreenRoot SOP must remain preserved where applicable.

            Evidence source:
            - Use the repair plan source failure record for the exact scene or script contract mismatch.
            """;
    }

    private static string BuildRpgGameplayContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair RPG gameplay behavior against project-specific form_fields and input_traceability.

            Contract requirements:
            - User form fields override RPG defaults and template examples.
            - Do not read docs/game-type-guides, docs/prototype-type-kits, or route skill documents to add gameplay requirements.
            - Encounter probability, guaranteed encounter, player stats, enemy stats, reward choices, return-to-map flow, and win/fail rules must match concrete project values when present.
            - Any concrete non-empty input field that cannot be implemented must become an explicit needs-fix blocker, not a silent omission.

            Evidence source:
            - Use the repair plan source failure record and prototype contract for the latest concrete gameplay drift.
            """;
    }

    private static string BuildRpgNavigationRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair the user-facing RPG entry path first.

            Priority requirements:
            - Start Adventure must reveal the real playable MapScene from the main prototype shell.
            - The map must be visibly present to the player, not only instantiated in the scene tree.
            - Keep the repair focused on navigation and map visibility before broader gameplay expansion.

            Evidence source:
            - Use the repair plan source failure record for the exact navigation or map visibility blocker.
            """;
    }

    private static string BuildRpgRewardLoopRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair the RPG reward loop strictly against the project contract.

            Contract requirements:
            - When the project contract explicitly requires reward 3-choice, do not skip or downgrade it to a template-default omission.
            - Victory must lead to reward selection and then return the player to the active map loop.
            - Reward flow must remain visible and understandable to the player.

            Evidence source:
            - Use the repair plan source failure record and prototype contract for the current reward-loop blocker.
            """;
    }

    private static string BuildRpgWinFailRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair win/fail rules and concrete project-specific gameplay constraints.

            Contract requirements:
            - Concrete user form values override RPG defaults and examples.
            - Win after 15 battles, any-loss defeat, encounter rules, enemy scaling, and visible battle outcome rules must match the project contract when present.
            - Update implementation, player-facing summary, and test evidence together so the playable loop description does not drift from runtime behavior.

            Evidence source:
            - Use the repair plan source failure record and prototype contract for the current win/fail blocker.
            """;
    }

    private static string BuildGenericEvidenceRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            使用 GDD 派生的项目合同和最新失败证据修复原型路由证据路径。

            修复范围：
            - 先读取当前项目 README 和原型合同。
            - 不要读取 docs/game-type-guides、docs/prototype-type-kits 或 route skill 文档来新增玩法需求。
            - 以最新失败运行输出作为故障事实来源。
            - 在更广泛的玩法修复前，先恢复路由完成证据。
            - 保持输出对浏览器用户安全。
            """;
    }

    private static string BuildGenericContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            按 GDD 派生的项目原型合同修复当前原型。

            合同要求：
            - 用户表单字段优先于通用默认值。
            - 不要读取 docs/game-type-guides、docs/prototype-type-kits 或 route skill 文档来新增玩法需求。
            - 可玩循环、UI 反馈和验证证据必须匹配项目原型合同。
            - 除非项目合同要求，不要虚构类型专属任务。

            证据来源：
            - 使用修复计划源失败记录和原型合同来定位最新通用原型阻塞项。
            """;
    }

    private static string BuildRpgRepairGoalPrompt(ProjectSnapshot project, PrototypeRepairPlanContext context)
    {
        var failureJson = JsonSerializer.Serialize(new
        {
            runType = context.FailedRun.RunType,
            status = context.FailedRun.Status,
            progressLabel = context.FailedRun.ProgressLabel,
            stderr = Trim(context.FailedRun.StderrText ?? "", 2000),
            stdout = Trim(context.FailedRun.StdoutText ?? "", 2000),
            evidence = Trim(context.FailedRun.EvidenceJson ?? "", 3000)
        });

        return $"""
            You are generating a repair plan for a failed hosted RPG Godot prototype run.
            Output JSON only. Do not explain. Do not use Markdown.
            Return these keys only:
            goals

            goals must be an array of 4 to 6 objects with:
            title, description, acceptanceHint

            Rules:
            - Use only the data provided in this prompt.
            - Do not read files, inspect the repository, call tools, or ask for more context.
            - Base the plan on the latest failed blocker, not on a generic RPG template.
            - First goal must target the concrete failed blocker with the highest repair value.
            - If the failure is main-menu/navigation/map-visibility related, do not start with evidence, TDD, permission, cache, or build-recovery steps.
            - Use small isolated gameplay repair steps: MapScene entry, movement/encounter, battle, reward loop, win/fail visibility, final acceptance.
            - Mention evidence/TDD/build recovery only when the failure explicitly points to permission denied, write failure, cache lock, build failure, or missing completion artifacts.
            - Write title, description, and acceptanceHint in Simplified Chinese by default. English is allowed only for code identifiers, fixed node names, resource paths, tests, logs, route ids, and platform validation names.
            - Keep the final goal as full playable prototype acceptance, but write the user-facing final goal title in Chinese.
            - Keep each goal narrow enough to execute independently.

            Parsed game-type route profile authority:
            {context.PromptAuthorities.ParsedRouteProfileJson}

            Selected route skill prompt block authority:
            {context.PromptAuthorities.SelectedRouteSkillPromptBlock}

            Authority use rule:
            - These two values select and bind the current route behavior. They do not authorize reading mutable guide or skill files, and they do not override the frozen GDD-derived prototype contract.

            Project:
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}

            Downstream source boundary:
            - Only the GDD route may read broad game-type sources such as docs/game-type-guides, prototype type kits, or route skill documents for design semantics.
            - Repair planning must use only the GDD-derived prototype contract, latest failed run, route state, repair ledger, and validation evidence as gameplay requirements.
            - Do not read docs/game-type-guides, docs/prototype-type-kits, or .agents/skills route documents to add gameplay requirements after GDD generation.

            Prototype contract:
            {Trim(context.Contract.Json ?? "", 3000)}

            Latest failed run:
            {failureJson}

            Failure excerpt:
            {Trim(context.FailureText, 4000)}
            """;
    }

    private static List<PrototypeRepairGoalResult> ParseRepairGoalPlan(string? assistantMessage)
    {
        if (string.IsNullOrWhiteSpace(assistantMessage))
        {
            return [];
        }

        try
        {
            using var document = JsonDocument.Parse(LlmRouteEngine.ExtractFirstJsonObject(assistantMessage) ?? assistantMessage);
            if (!document.RootElement.TryGetProperty("goals", out var goalsElement) || goalsElement.ValueKind != JsonValueKind.Array)
            {
                return [];
            }

            var goals = new List<PrototypeRepairGoalResult>();
            var index = 1;
            foreach (var item in goalsElement.EnumerateArray())
            {
                var title = item.TryGetProperty("title", out var titleElement) && titleElement.ValueKind == JsonValueKind.String
                    ? titleElement.GetString()?.Trim()
                    : null;
                var description = item.TryGetProperty("description", out var descriptionElement) && descriptionElement.ValueKind == JsonValueKind.String
                    ? descriptionElement.GetString()?.Trim()
                    : null;
                var acceptance = item.TryGetProperty("acceptanceHint", out var acceptanceElement) && acceptanceElement.ValueKind == JsonValueKind.String
                    ? acceptanceElement.GetString()?.Trim()
                    : null;
                if (string.IsNullOrWhiteSpace(title) || string.IsNullOrWhiteSpace(description) || string.IsNullOrWhiteSpace(acceptance))
                {
                    continue;
                }

                goals.Add(new PrototypeRepairGoalResult(index++, NormalizeRepairGoalTitle(title), description, acceptance, "pending"));
            }

            return goals.Count >= 4 ? goals : [];
        }
        catch (JsonException)
        {
            return [];
        }
    }

    private static string EnsureRepairPlanPromptWorkspace(ProjectSnapshot project)
    {
        var repoParent = Path.GetDirectoryName(project.RepoPath);
        var workspaceRoot = string.IsNullOrWhiteSpace(repoParent) ? project.RepoPath : repoParent;
        var root = Path.Combine(workspaceRoot, "_phasea_llm", "repair-plan");
        Directory.CreateDirectory(root);
        return root;
    }

    private static string NormalizeRepairGoalTitle(string title)
    {
        var normalized = title.Trim();
        if (normalized.StartsWith("RPG Repair Step 1:", StringComparison.OrdinalIgnoreCase))
        {
            return "修复任务 1：Start Adventure 到可见 MapScene";
        }

        if (normalized.StartsWith("RPG Repair Step 2:", StringComparison.OrdinalIgnoreCase))
        {
            return "修复任务 2：移动与第一次遇敌入口";
        }

        if (normalized.StartsWith("RPG Repair Step 3:", StringComparison.OrdinalIgnoreCase))
        {
            return "修复任务 3：BattleScene 单轮验证";
        }

        if (normalized.StartsWith("RPG Repair Step 4:", StringComparison.OrdinalIgnoreCase))
        {
            return "修复任务 4：奖励 3 选 1 与返回地图";
        }

        if (normalized.StartsWith("RPG Repair Step 5:", StringComparison.OrdinalIgnoreCase))
        {
            return "修复任务 5：胜负可见性";
        }

        if (normalized.StartsWith("Recover Step 07", StringComparison.OrdinalIgnoreCase))
        {
            return "服务重启后恢复第 7 步最终摘要";
        }

        if (normalized.StartsWith("Revalidate existing RPG playable evidence", StringComparison.OrdinalIgnoreCase))
        {
            return "重新验证现有 RPG 可玩证据";
        }

        if (normalized.StartsWith("Run final RPG acceptance only after recovery", StringComparison.OrdinalIgnoreCase))
        {
            return "恢复后再运行 RPG 最终验收";
        }

        if (normalized.StartsWith("Build cleanup:", StringComparison.OrdinalIgnoreCase))
        {
            return "构建清理：先移除陈旧生成目录";
        }

        if (normalized.StartsWith("Repair RPG script input and loop behavior under the validated scene contract", StringComparison.OrdinalIgnoreCase))
        {
            return "修复已验证场景合同下的 RPG 脚本输入与循环行为";
        }

        if (normalized.StartsWith("Repair RPG", StringComparison.OrdinalIgnoreCase))
        {
            return "修复 RPG 相关任务";
        }

        return normalized;
    }

    private static string BuildStepFeedback(
        ProjectSnapshot project,
        ProjectIterationSessionDetails details,
        ProjectIterationGoalSnapshot goal,
        string? feedback,
        string projectExecutionGuide,
        RepairPromptAuthorityBinding promptAuthorities)
    {
        var recoveryOnlyRules = IsServiceRestartRecoveryGoal(goal)
            ? """
            Recovery-only task:
            - The current failure is service_restart_recovery / interrupted_by_service_restart, not a gameplay defect.
            - Do not add or change map, movement, battle, reward, win/fail, UI, asset, test, or scene files unless the current task explicitly names a concrete gameplay validation failure.
            - Prefer preserving existing prototype artifacts and reporting that final prototype acceptance must be rerun after service recovery.
            - If no hosted game file change is required, return STATUS: completed with REMAINING: rerun final prototype acceptance.
            """
            : "";

        return $"""
            Run the execute-repair-step top-level route.

            Repair plan:
            - SessionId: {details.Session.SessionId}
            - SourceKind: {SourceKind}
            - CurrentRepairTask: {goal.GoalIndex}
            - Title: {goal.Title}
            - Description: {goal.Description}
            - AcceptanceHint: {goal.AcceptanceHint}

            Repair evidence context:
            {details.Session.SourceMessage}

            Mandatory rules:
            - Execute only the current repair task.
            - Read the Project Execution Guide as the project-level /new recovery protocol before changing files.
            - Use Prototype Chapter 6 Lite semantics: repair one current task, update lightweight route state, and do not create Taskmaster triplets, formal acceptance files, overlays, architecture contracts, or Chapter 6 review pipeline artifacts.
            - Do not regenerate the prototype, iteration plan, or repair plan.
            - Do not repair PhaseA platform code, docs, scripts, deployment, or route code.
            - Change only hosted game project files needed for this repair step.
            - Godot project root is project.godot at repository root, not Game.Godot/project.godot.
            - GdUnit project root is Tests.Godot; runtime assets are visible through Tests.Godot/Game.Godot.
            - If repairing asset import failures, run the import/prewarm against Tests.Godot and verify Tests.Godot/.godot/imported contains the required imported resources.
            - Keep output browser-safe: no paths, command lines, script names, logs, or environment values.
            - Browser-facing output must be Simplified Chinese. Keep only machine protocol tokens such as STATUS: completed|needs_fix in English.
            {recoveryOnlyRules}

            Project:
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}

            Parsed game-type route profile authority:
            {promptAuthorities.ParsedRouteProfileJson}

            Selected route skill prompt block authority:
            {promptAuthorities.SelectedRouteSkillPromptBlock}

            Authority use rule:
            - These two values bind the current route behavior. Do not use them to bypass the frozen GDD-derived contract or to read mutable guide/skill files.

            Project Execution Guide:
            {Trim(projectExecutionGuide, 2200)}

            Downstream source boundary:
            - Only the GDD route may read broad game-type sources such as docs/game-type-guides, prototype type kits, or route skill documents for design semantics.
            - Repair steps must use only the GDD-derived prototype contract, current goal, route state, repair ledger, latest validation evidence, and user feedback as gameplay requirements.
            - Do not read docs/game-type-guides, docs/prototype-type-kits, or .agents/skills route documents to add gameplay requirements after GDD generation.

            Extra user feedback:
            {feedback}

            输出格式：
            STATUS: completed|needs_fix
            SUMMARY: 用 2-4 句中文说明当前修复任务是否完成，以及对用户有什么变化
            CHANGED: 用 1-3 行中文列出本轮实际完成的改动
            VERIFY: 用 1-3 行中文说明如何验证
            REMAINING: 若未完全完成，用中文写出剩余问题；若已完成，写 none
            """;
    }

    private static RepairPromptAuthorityBinding BuildPromptAuthorities(
        ProjectSnapshot project,
        GameTypeRouteProfile routeProfile)
    {
        var parsedRouteProfileJson = JsonSerializer.Serialize(routeProfile);
        var selectedRouteSkillPromptBlock = PrototypeRouteSkillPolicy.BuildPromptBlock(project);
        return new RepairPromptAuthorityBinding(
            parsedRouteProfileJson,
            selectedRouteSkillPromptBlock,
            HostedRouteForbiddenSourceGuard.PromptHash(parsedRouteProfileJson),
            HostedRouteForbiddenSourceGuard.PromptHash(selectedRouteSkillPromptBlock));
    }

    private static object BuildPromptAuthorityState(RepairPromptAuthorityBinding promptAuthorities)
    {
        return new
        {
            recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
            recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
            authority_sources = new[]
            {
                HostedRouteRecoveryContract.ParsedRouteProfileSource,
                HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockSource
            },
            source_hashes = new Dictionary<string, string>(StringComparer.Ordinal)
            {
                [HostedRouteRecoveryContract.ParsedRouteProfileHashKey] = promptAuthorities.ParsedRouteProfileHash,
                [HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey] = promptAuthorities.SelectedRouteSkillPromptBlockHash
            }
        };
    }

    private static bool SessionPromptAuthoritiesMatch(
        string? sourceMessage,
        RepairPromptAuthorityBinding current)
    {
        if (string.IsNullOrWhiteSpace(sourceMessage))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(sourceMessage);
            if (!document.RootElement.TryGetProperty("prompt_authority_binding", out var binding) ||
                binding.ValueKind != JsonValueKind.Object ||
                !string.Equals(ReadString(binding, "recovery_source_order_ref"), HostedRouteRecoveryContract.ContractId, StringComparison.Ordinal) ||
                !binding.TryGetProperty("recovery_source_order", out var sourceOrder) ||
                sourceOrder.ValueKind != JsonValueKind.Array ||
                !sourceOrder.EnumerateArray()
                    .Select(item => item.ValueKind == JsonValueKind.String ? item.GetString() ?? "" : "")
                    .SequenceEqual(HostedRouteRecoveryContract.SourceOrder, StringComparer.Ordinal) ||
                !binding.TryGetProperty("source_hashes", out var hashes) ||
                hashes.ValueKind != JsonValueKind.Object)
            {
                return false;
            }

            return string.Equals(
                       ReadString(hashes, HostedRouteRecoveryContract.ParsedRouteProfileHashKey),
                       current.ParsedRouteProfileHash,
                       StringComparison.Ordinal) &&
                   string.Equals(
                       ReadString(hashes, HostedRouteRecoveryContract.SelectedRouteSkillPromptBlockHashKey),
                       current.SelectedRouteSkillPromptBlockHash,
                       StringComparison.Ordinal);
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool IsServiceRestartRecoveryGoal(ProjectIterationGoalSnapshot goal)
    {
        return ContainsAny(
            string.Join("\n", goal.Title, goal.Description, goal.AcceptanceHint),
            "interrupted_by_service_restart",
            "service_restart_recovery",
            "service restart",
            "service-restart");
    }

    private static string Trim(string value, int maxLength)
    {
        return value.Length <= maxLength ? value : value[..maxLength];
    }

    private static string? ReadString(JsonElement element, string propertyName)
    {
        return element.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;
    }

    private static string? ResolveReportFile(string repoPath, string? reportDir, string fileName)
    {
        if (string.IsNullOrWhiteSpace(reportDir))
        {
            return null;
        }

        var relative = reportDir.Replace('/', Path.DirectorySeparatorChar).Replace('\\', Path.DirectorySeparatorChar);
        var path = Path.Combine(repoPath, relative, fileName);
        return Path.GetFullPath(path);
    }

    private static IReadOnlyList<string> ExtractGdUnitErrorSummary(string consoleText, int maxLines)
    {
        var lines = new List<string>();
        foreach (var rawLine in consoleText.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries))
        {
            var line = rawLine.Trim();
            if (!ContainsAny(
                    line,
                    "ERROR:",
                    "SCRIPT ERROR",
                    "Node not found",
                    "Parse Error",
                    "Invalid call",
                    "No test cases found",
                    "GDUNIT_DONE"))
            {
                continue;
            }

            if (lines.Any(existing => string.Equals(existing, line, StringComparison.OrdinalIgnoreCase)))
            {
                continue;
            }

            lines.Add(Trim(line, 500));
            if (lines.Count >= maxLines)
            {
                break;
            }
        }

        return lines;
    }

    private static IReadOnlyList<string> ExtractRepairEvidenceSummary(string failureText, int maxLines)
    {
        var lines = new List<string>();
        foreach (var rawLine in failureText.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries))
        {
            var line = rawLine.Trim();
            if (!ContainsAny(
                    line,
                    "ERROR:",
                    "SCRIPT ERROR",
                    "Parse Error",
                    "Node not found",
                    "Invalid call",
                    "Permission denied",
                    "CS0579",
                    "GDUNIT_DONE",
                    "No test cases found",
                    "rpg_project_specific_gdunit_failed",
                    "prototype_main_menu_navigation_failed",
                    "visible MapScene markers were not found"))
            {
                continue;
            }

            if (lines.Any(existing => string.Equals(existing, line, StringComparison.OrdinalIgnoreCase)))
            {
                continue;
            }

            lines.Add(Trim(line, 500));
            if (lines.Count >= maxLines)
            {
                break;
            }
        }

        return lines;
    }

    private static bool ContainsAny(string text, params string[] needles)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        foreach (var needle in needles)
        {
            if (!string.IsNullOrWhiteSpace(needle) &&
                text.Contains(needle, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
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

public sealed record PrototypeRepairPlanContext(
    GameTypeRouteProfile RouteProfile,
    PrototypeContractSnapshot Contract,
    RunSnapshot FailedRun,
    string FailureText,
    RepairPromptAuthorityBinding PromptAuthorities);

public sealed record RepairPromptAuthorityBinding(
    string ParsedRouteProfileJson,
    string SelectedRouteSkillPromptBlock,
    string ParsedRouteProfileHash,
    string SelectedRouteSkillPromptBlockHash);
