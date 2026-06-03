using System.Text;
using System.Text.Json;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;

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
        ILlmRouteEngine? llmRouteEngine = null)
    {
        _metadataStore = metadataStore;
        _quickFixService = quickFixService;
        _stateWriter = stateWriter;
        _contractService = contractService ?? new PrototypeContractService();
        _llmRouteEngine = llmRouteEngine ?? (codexChatClient is null ? null : new LlmRouteEngine(codexChatClient));
    }

    public async Task<PrototypeRepairPlanResult> CreateAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await RequireProjectAsync(accountId, projectId, cancellationToken);
        var routeSkill = PrototypeRouteSkillPolicy.EnsureAvailable(project);
        if (!routeSkill.IsAvailable)
        {
            return new PrototypeRepairPlanResult("", routeSkill.FailureCode, routeSkill.FailureMessage, []);
        }

        var failedRun = await FindLatestFailedRunAsync(project.ProjectId, cancellationToken);
        if (failedRun is null)
        {
            return new PrototypeRepairPlanResult("", "missing_failure", "当前项目没有可用于生成修复计划的失败记录。", []);
        }

        var prototypeContract = _contractService.Read(project);
        var failureText = BuildFailureText(project, failedRun);
        var planContext = BuildPlanContext(project, prototypeContract, failedRun, failureText, routeSkill.Context);
        var goals = await BuildRepairGoalsAsync(project, planContext, cancellationToken);
        var summary = $"已基于最近一次失败生成 {goals.Count} 个修复步骤。请逐项执行，最后一步必须做全量验收。";
        var session = await _metadataStore.CreateProjectIterationSessionAsync(
            accountId,
            project.ProjectId,
            SourceKind,
            BuildSourceMessage(failedRun, failureText, routeSkill.Context),
            $"Repair the failed prototype route through small isolated repair steps for {routeSkill.Context.RouteSkillId}.",
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
            route_skill = routeSkill.Context,
            game_type_profile = PrototypeRouteSkillPolicy.ResolveProfile(project),
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
        var routeSkill = PrototypeRouteSkillPolicy.EnsureAvailable(project);
        if (!routeSkill.IsAvailable)
        {
            return new PrototypeRepairStepExecutionResult("", "", "", routeSkill.FailureCode, routeSkill.FailureMessage, 0, false, routeSkill.FailureCode);
        }

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

        var projectExecutionGuide = _stateWriter.ReadOrCreateProjectExecutionGuide(project, _contractService.Read(project));
        var feedback = BuildStepFeedback(project, details, current, request.Feedback, routeSkill.Context, projectExecutionGuide);
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
            ? $"修复步骤 {current.GoalIndex} 已完成。"
            : $"修复步骤 {current.GoalIndex} 仍需继续修复。";
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(refreshed.Session.SessionId, sessionStatus, current.GoalIndex, summary, null, sessionStatus == "completed" ? DateTimeOffset.UtcNow.ToString("O") : null, CancellationToken.None);

        _stateWriter.WriteRepairPlanState(project, new
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

    private static string BuildSourceMessage(RunSnapshot run, string failureText, PrototypeRouteSkillContext routeSkill)
    {
        return JsonSerializer.Serialize(new
        {
            source_run_id = run.RunId,
            source_run_type = run.RunType,
            source_status = run.Status,
            route_skill = routeSkill.RouteSkillId,
            failure_excerpt = Trim(failureText, 4000),
            failure_signals = ExtractRepairEvidenceSummary(failureText, maxLines: 40)
        });
    }

    private static PrototypeRepairPlanContext BuildPlanContext(
        ProjectSnapshot project,
        PrototypeContractSnapshot contract,
        RunSnapshot failedRun,
        string failureText,
        PrototypeRouteSkillContext routeSkill)
    {
        return new PrototypeRepairPlanContext(routeSkill, contract, failedRun, failureText);
    }

    private async Task<List<PrototypeRepairGoalResult>> BuildRepairGoalsAsync(
        ProjectSnapshot project,
        PrototypeRepairPlanContext context,
        CancellationToken cancellationToken)
    {
        if (context.RouteSkill.RouteSkillId == "prototype-rpg-godot-zh")
        {
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

    private async Task<List<PrototypeRepairGoalResult>> TryBuildRpgRepairGoalsFromModelAsync(
        ProjectSnapshot project,
        PrototypeRepairPlanContext context,
        CancellationToken cancellationToken)
    {
        if (_llmRouteEngine is null)
        {
            return [];
        }

        var completion = await _llmRouteEngine.CompleteAsync(
            new LlmRouteRequest(
                EnsureRepairPlanPromptWorkspace(project),
                "repair-plan",
                PrototypeModelPolicy.Normalize("gpt-5.4"),
                BuildRpgRepairGoalPrompt(project, context),
                RepairPlanningCodexOptions,
                project.AccountId,
                RequireJsonObject: true),
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
            This step passes only when the latest run blocker is removed and the prototype route can write its completion/TDD evidence without permission, build, or cache-lock failures.
            Do not report this step as succeeded if the latest failure evidence still blocks route completion artifacts.
            """);

        Add(
            "修复 RPG 场景与节点合同",
            BuildRpgSceneContractRepairDescription(context),
            """
            This step passes only when the current RPG prototype has the required contract-aligned scene structure, including the main prototype shell, MapScene, BattleScene, and required named map/player/enemy asset nodes.
            Scene/script contract drift must be eliminated before continuing.
            """);

        Add(
            "修复 RPG 玩法合同与表单追踪",
            BuildRpgGameplayContractRepairDescription(context),
            """
            This step passes only when concrete user form values from prototype-contract form_fields and input_traceability are represented in gameplay behavior, UI/state feedback, tests, or an explicit needs-fix blocker.
            Do not replace concrete project values with RPG template defaults.
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
            "Repair RPG runtime assets and Godot imports for GdUnit",
            BuildRpgGdUnitAssetRepairDescription(context),
            """
            This step passes only when the active dq-rpg scenes no longer reference missing PNG or .ctex resources and GdUnit can load MapScene.tscn and BattleScene.tscn without ext_resource parse errors.
            """);

        Add(
            "Repair RPG scene node contract expected by DqRpgPrototype tests",
            BuildRpgGdUnitNodeRepairDescription(context),
            """
            This step passes only when the node paths required by the project-specific GdUnit suite exist or the tests and scripts are updated together to a single authoritative RPG contract, with no Node not found errors.
            """);

        Add(
            "Repair RPG script input and loop behavior under the validated scene contract",
            BuildRpgGdUnitScriptRepairDescription(context),
            """
            This step passes only when the Invalid call to _UnhandledInput is gone and the map movement, encounter entry, battle, reward 3-choice, and return-to-map behaviors work through the same scene path used by GdUnit.
            """);

        Add(
            "Preserve project input contract while fixing RPG behavior",
            BuildRpgGdUnitContractRepairDescription(context),
            """
            This step passes only when concrete project values such as 15-battle victory, any-loss defeat, reward 3-choice, and visible battle comprehension are preserved in runtime/UI/test evidence; do not replace them with shorter template-default victory counts.
            """);

        Add(
            "Rerun RPG project-specific GdUnit and final prototype acceptance",
            BuildRpgGdUnitFinalAcceptanceDescription(context),
            """
            The repair is complete only when `tests/Prototype/DqRpgPrototype` runs with rc=0, no "No test cases found", no Godot ERROR/SCRIPT ERROR markers, and the front-end "重新验收原型" route succeeds.
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
            "Build cleanup: remove stale generated build dirs first",
            BuildRpgBuildCleanupRepairDescription(context),
            """
            This step passes only when the repository-local Game.Core and Game.Core.Tests obj/bin/buildcache directories are safely cleaned, generated AssemblyInfo files are not compiled from stale output, and the CS0579 duplicate assembly attribute failure is gone.
            """);

        Add(
            "Rerun prototype TDD green after build cleanup",
            "Rerun the RPG prototype TDD green lane and confirm the dotnet verification step passes before treating any remaining failure as a gameplay or scene contract issue.",
            """
            This step passes only when the latest prototype TDD green run no longer fails in the dotnet build/test step with CS0579, AssemblyInfo, TargetFrameworkAttribute, or obj/bin/buildcache contamination signals.
            """);

        Add(
            "Inspect RPG scene and gameplay only if TDD still fails",
            "If the clean build passes but the prototype still fails, inspect the remaining failure output and repair the concrete RPG scene, navigation, battle, reward, or form-traceability contract named by that new evidence.",
            """
            This step is started only after the build contamination is cleared. It passes when any remaining RPG contract failure is repaired against the current failure evidence instead of against a generic template.
            """);

        Add(
            "Final full acceptance after clean verification",
            "Run the final RPG prototype acceptance after build cleanup and any evidence-driven gameplay repair are complete.",
            "The repair is complete only when the final prototype route and verification evidence are green with no build contamination recurrence.");

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
            "Repair RPG scene/script node contract mismatch",
            BuildRpgSceneNodeContractRepairDescription(context),
            """
            This step passes only when the node path named by the latest Godot error exists in the active prototype scene or the script binding is corrected to the real contract path, with no Node not found errors during prototype navigation smoke.
            """);

        Add(
            "Rerun Start Adventure navigation and BattleScene smoke",
            "Rerun the user-facing Start Adventure path and verify MapScene remains visible, then trigger the BattleScene path that previously required the missing node.",
            """
            This step passes only when Start Adventure to visible MapScene still passes and the BattleScene UI path no longer crashes on missing labels or stale script bindings.
            """);

        Add(
            "Verify RPG reward and win/fail contract after node repair",
            "After the scene/script binding is stable, verify reward 3-choice return-to-map plus the concrete form rules for 15-battle victory and any-loss defeat.",
            """
            This step passes only when reward 3-choice, return-to-map, 15 battles victory, and any-loss defeat are visible in runtime behavior, UI/state feedback, or explicit evidence.
            """);

        Add(
            "Final full acceptance after scene contract repair",
            "Run the final RPG prototype acceptance after the node contract repair and follow-up gameplay checks are complete.",
            "The repair is complete only when the final prototype route and verification evidence are green with no Node not found or scene/script contract drift recurrence.");

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
            This step passes only when Start Adventure consistently reveals the real playable MapScene, hides stale menu-only state, and exposes visible map markers from the user-facing entry path.
            """);

        Add(
            "修复 RPG 奖励闭环与地图返回",
            BuildRpgRewardLoopRepairDescription(context),
            """
            This step passes only when battle victory leads to a readable reward 3-choice flow, one choice can be applied, and the player returns to the active map loop.
            Do not silently downgrade the reward step to a template-default omission when the project contract explicitly requires it.
            """);

        Add(
            "修复 RPG 胜负条件与表单硬约束落地",
            BuildRpgWinFailRepairDescription(context),
            """
            This step passes only when concrete user form values such as 15-battle victory, any-loss defeat, encounter rules, and stat rules are reflected in gameplay behavior, readable UI/state feedback, or explicit needs-fix blockers.
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
            "The latest failure reason is eliminated and the prototype route can produce completion evidence without build, cache, or write failures.");

        Add(
            "修复通用原型合同缺口",
            BuildGenericContractRepairDescription(context),
            "The default prototype route skill and project prototype contract are reflected in the repaired output, with no new prototype drift.");

        Add(
            "执行最终全量验收",
            "运行当前类型要求的最终 smoke/导航/可见性验收，确认修复闭环。",
            "最终验收通过后，原型修复才算完成。");

        return goals;
    }

    private static string BuildRpgEvidenceRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair the latest failed RPG prototype route evidence path using the route skill, project contract, and failure output.

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillGuide}
            - {context.RouteSkill.RouteSkillContract}

            Required repair scope:
            - Read the current project README and prototype contract first.
            - Use the latest failed run output as the source of truth for what broke.
            - Restore writable completion artifacts, TDD green evidence, and build outputs needed by the prototype route.
            - Do not broaden this step into gameplay or scene redesign.
            - Preserve browser-safe output.
            """;
    }

    private static string BuildRpgBuildCleanupRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            The latest RPG prototype failure is a .NET build contamination failure, not a gameplay-design failure. Clean the repo-local build outputs before changing scene or gameplay logic.

            Required focus:
            - Remove stale obj/bin/buildcache directories only inside the current prototype repository and targeted dotnet projects.
            - Verify generated AssemblyInfo and TargetFrameworkAttribute files are not duplicated by stale output.
            - Rerun the dotnet verification step and keep the latest log as evidence.
            - Do not start RPG scene/gameplay repair until CS0579 is gone.

            Evidence source:
            - Use the repair plan source failure record for the exact compiler error and generated build path.
            """;
    }

    private static string BuildRpgSceneNodeContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            The latest RPG prototype failure is a Godot scene/script node contract mismatch, not a build-cache failure. Repair the missing node path or script binding named by the engine error before changing broader gameplay.

            Required focus:
            - Use the latest Godot error as the source of truth.
            - If a required UI node such as BattleStatusLabel is missing, add it at the path expected by the active prototype script or update the script to the authoritative scene path.
            - Keep Start Adventure -> visible MapScene behavior intact.
            - Do not treat .godot/mono/temp/obj/Debug source-generator stack paths as CS0579 build contamination.

            Evidence source:
            - Use the repair plan source failure record for the exact Godot node/script error and stack context.
            """;
    }

    private static string BuildRpgGdUnitAssetRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            The latest RPG project-specific GdUnit validation failed while loading concrete Godot resources. Repair resource references before broad gameplay redesign.

            Required focus:
            - Fix missing runtime assets or scene ext_resource paths named in the GdUnit console summary.
            - Ensure MapScene.tscn and BattleScene.tscn do not reference missing PNG files or stale .godot/imported .ctex files.
            - Run Godot import through the project workflow after copying or restoring assets.
            - Do not mark this step complete if Parse Error or Failed loading resource remains.

            Evidence source:
            - Use the repair plan source failure record for the exact missing resource, parse error, and GdUnit console lines.
            """;
    }

    private static string BuildRpgGdUnitNodeRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair the RPG scene/node contract that the project-specific DqRpgPrototype GdUnit tests validate.

            Required focus:
            - Required test paths include CanvasLayer/UI/MapScene/RpgMapAsset, RpgPlayerAsset, RpgEnemyAsset, ChestToken, and CanvasLayer/UI/BattleScene/EnemyToken when named by the latest failure.
            - Keep the scene script and test contract aligned; do not move nodes without updating the authoritative scene path used by runtime code and tests together.
            - Preserve Start Adventure -> visible MapScene behavior.

            Evidence source:
            - Use the repair plan source failure record for the exact node path mismatch reported by GdUnit.
            """;
    }

    private static string BuildRpgGdUnitScriptRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair script/runtime errors exposed by RPG GdUnit after the resource and node contract is stable.

            Required focus:
            - Remove invalid calls such as calling _UnhandledInput on a Control base that does not expose that function.
            - Keep movement, encounter entry, battle resolution, reward 3-choice, and return-to-map callable through the same prototype shell used by the test.
            - Do not bypass failing behavior by weakening or deleting project-specific GdUnit tests.

            Evidence source:
            - Use the repair plan source failure record for the exact script/runtime error reported by GdUnit.
            """;
    }

    private static string BuildRpgGdUnitContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair gameplay behavior without drifting from the project prototype contract.

            Required focus:
            - Concrete project input values override RPG defaults and template examples.
            - Preserve reward 3-choice and visible battle comprehension.
            - Preserve the project win/fail condition from the contract; do not replace 15-battle victory with a shorter RPG template-default victory count unless the user contract says so.
            - Any unimplemented concrete input must become an explicit needs-fix blocker.

            Contract source:
            - Use the current prototype contract JSON and route skill contract as authoritative project input.
            - Use the repair plan source failure record for the latest validation blocker.
            """;
    }

    private static string BuildRpgGdUnitFinalAcceptanceDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Run final RPG validation against the same blocker that generated this repair plan.

            Required validation:
            - Project-specific GdUnit path: tests/Prototype/DqRpgPrototype.
            - Treat wrapper output GDUNIT_DONE rc=1 as failure even when normalized_rc is 0.
            - Treat No test cases found as failure.
            - Re-run the front-end prototype validation route after GdUnit is clean.

            Evidence source:
            - Use the repair plan source failure record for the exact validation blocker that must become green.
            """;
    }

    private static string BuildRpgSceneContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair the RPG scene and node contract using the selected route skill and prototype contract.

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillContract}

            Contract requirements:
            - The project prototype contract is authoritative.
            - MapScene, BattleScene, and the main prototype shell must have clear responsibilities.
            - Map, player, and enemy asset instances must use the RPG contract naming rules.
            - Main.tscn default-hidden VBox, Overlays, and ScreenRoot SOP must remain preserved where applicable.

            Evidence source:
            - Use the repair plan source failure record for the exact scene or script contract mismatch.
            """;
    }

    private static string BuildRpgGameplayContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair RPG gameplay behavior against project-specific form_fields and input_traceability.

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillContract}

            Contract requirements:
            - User form fields override RPG defaults and template examples.
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

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillContract}

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

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillContract}

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

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillContract}

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
            Repair the latest failed prototype route evidence path using the default prototype route skill and the project contract.

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillGuide}

            Required repair scope:
            - Read the current project README and prototype contract first.
            - Use the latest failed run output as the source of truth for what broke.
            - Restore route completion evidence before broader gameplay repair.
            - Preserve browser-safe output.
            """;
    }

    private static string BuildGenericContractRepairDescription(PrototypeRepairPlanContext context)
    {
        return $"""
            Repair the current prototype against the default prototype route skill and project prototype contract.

            Route skill:
            - {context.RouteSkill.RouteSkillId}
            - {context.RouteSkill.RouteSkillContract}

            Contract requirements:
            - User form fields override generic defaults.
            - The playable loop, UI feedback, and validation evidence must match the project prototype contract.
            - Do not invent type-specific steps unless the project contract demands them.

            Evidence source:
            - Use the repair plan source failure record and prototype contract for the latest generic prototype blocker.
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
            - Keep the final goal as full playable prototype acceptance.
            - Keep each goal narrow enough to execute independently.

            Project:
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}

            Route skill:
            - RouteSkillId: {context.RouteSkill.RouteSkillId}
            - RouteSkillGuide: {context.RouteSkill.RouteSkillGuide}
            - RouteSkillContract: {context.RouteSkill.RouteSkillContract}

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

                goals.Add(new PrototypeRepairGoalResult(index++, title, description, acceptance, "pending"));
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

    private static string BuildStepFeedback(ProjectSnapshot project, ProjectIterationSessionDetails details, ProjectIterationGoalSnapshot goal, string? feedback, PrototypeRouteSkillContext routeSkill, string projectExecutionGuide)
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

            Repair evidence context:
            {details.Session.SourceMessage}

            Mandatory rules:
            - Execute only the current repair step.
            - Read the Project Execution Guide as the project-level /new recovery protocol before changing files.
            - Use Prototype Chapter 6 Lite semantics: repair one current step, update lightweight route state, and do not create Taskmaster triplets, formal acceptance files, overlays, architecture contracts, or Chapter 6 review pipeline artifacts.
            - Do not regenerate the prototype, iteration plan, or repair plan.
            - Do not repair PhaseA platform code, docs, scripts, deployment, or route code.
            - Change only hosted game project files needed for this repair step.
            - Godot project root is project.godot at repository root, not Game.Godot/project.godot.
            - GdUnit project root is Tests.Godot; runtime assets are visible through Tests.Godot/Game.Godot.
            - If repairing asset import failures, run the import/prewarm against Tests.Godot and verify Tests.Godot/.godot/imported contains the required imported resources.
            - Keep output browser-safe: no paths, command lines, script names, logs, or environment values.

            Project:
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}

            Project Execution Guide:
            {Trim(projectExecutionGuide, 2200)}

            Route skill context:
            - RouteSkillId: {routeSkill.RouteSkillId}
            - RouteSkillName: {routeSkill.RouteSkillName}
            - RouteSkillLabel: {routeSkill.RouteSkillLabel}
            - RouteSkillGuide: {routeSkill.RouteSkillGuide}
            - RouteSkillContract: {routeSkill.RouteSkillContract}
            - MandatorySkillEntry: ${routeSkill.RouteSkillId}
            - MandatorySkillPath: {routeSkill.SkillRelativePath}

            Extra user feedback:
            {feedback}
            """;
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
    PrototypeRouteSkillContext RouteSkill,
    PrototypeContractSnapshot Contract,
    RunSnapshot FailedRun,
    string FailureText);
