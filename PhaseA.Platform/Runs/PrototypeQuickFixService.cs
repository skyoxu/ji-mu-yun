using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed partial class PrototypeQuickFixService
{
    private const string RunType = "prototype-quick-fix";
    private const string ReasoningEffort = "low";
    private static readonly TimeSpan DefaultExecutionTimeout = TimeSpan.FromSeconds(300);
    private static readonly TimeSpan DefaultGoalRepairExecutionTimeout = TimeSpan.FromMinutes(12);
    private static readonly TimeSpan GodotSmokeValidationTimeout = TimeSpan.FromSeconds(45);

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly SkillActionCatalog _skillActionCatalog;
    private readonly PrototypeContractService _contractService;
    private readonly PrototypeRouteStateWriter _stateWriter;
    private readonly IAiCodeMirrorBillingClient _billingClient;
    private readonly AiCodeMirrorKeyPoolService? _keyPoolService;
    private readonly TimeSpan _executionTimeout;
    private readonly HeavyRunnerQueueService _heavyRunnerQueue;

    public PrototypeQuickFixService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner)
        : this(metadataStore, options, processRunner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), new PrototypeContractService(), null)
    {
    }

    public PrototypeQuickFixService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        IProjectWorkspaceSeeder workspaceSeeder,
        SkillActionCatalog skillActionCatalog,
        TimeSpan? executionTimeout)
        : this(metadataStore, options, processRunner, workspaceSeeder, skillActionCatalog, new PrototypeContractService(), executionTimeout: executionTimeout)
    {
    }

    public PrototypeQuickFixService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        IProjectWorkspaceSeeder workspaceSeeder,
        SkillActionCatalog skillActionCatalog,
        PrototypeContractService? contractService = null,
        IAiCodeMirrorBillingClient? billingClient = null,
        AiCodeMirrorKeyPoolService? keyPoolService = null,
        TimeSpan? executionTimeout = null,
        HeavyRunnerQueueService? heavyRunnerQueue = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _workspaceSeeder = workspaceSeeder;
        _skillActionCatalog = skillActionCatalog;
        _contractService = contractService ?? new PrototypeContractService();
        _stateWriter = new PrototypeRouteStateWriter();
        _billingClient = billingClient ?? new DisabledAiCodeMirrorBillingClient();
        _keyPoolService = keyPoolService;
        _executionTimeout = executionTimeout ?? DefaultExecutionTimeout;
        _heavyRunnerQueue = heavyRunnerQueue ?? new HeavyRunnerQueueService();
    }

    public async Task<PrototypeFeedbackResult> SubmitAsync(
        string accountId,
        string projectId,
        PrototypeFeedbackRequest request,
        CancellationToken cancellationToken = default)
    {
        return await SubmitAsync(accountId, projectId, request, requireSucceededPrototypeRun: true, cancellationToken);
    }

    internal async Task<PrototypeFeedbackResult> SubmitAsync(
        string accountId,
        string projectId,
        PrototypeFeedbackRequest request,
        bool requireSucceededPrototypeRun,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var feedback = request.Feedback?.Trim();
        if (string.IsNullOrWhiteSpace(feedback))
        {
            return new PrototypeFeedbackResult("", "missing_feedback", "请输入要快速修复的问题。", []);
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        if (requireSucceededPrototypeRun && !await HasSucceededPrototypeWorkflowAsync(project.ProjectId, cancellationToken))
        {
            return new PrototypeFeedbackResult("", "prototype_not_ready", "请先完成原型骨架创建，再使用快速修复。", []);
        }

        ProjectIterationSessionDetails? iterationDetails = null;
        ProjectIterationGoalSnapshot? targetGoal = null;
        PrototypeGoalRepairContext? goalRepair = null;
        ProjectRunMemorySnapshot? runMemory = null;
        var goalRepairMode = request.GoalRepair is not null;
        if (goalRepairMode)
        {
            iterationDetails = await ResolveGoalRepairSessionAsync(project.ProjectId, request.GoalRepair!, cancellationToken);
            if (iterationDetails is null)
            {
                return new PrototypeFeedbackResult("", "missing_plan", "当前项目还没有可修复的迭代计划。", []);
            }

            goalRepair = request.GoalRepair!;
            targetGoal = iterationDetails.Goals.FirstOrDefault(goal =>
                (!string.IsNullOrWhiteSpace(goalRepair.GoalId) && string.Equals(goal.GoalId, goalRepair.GoalId, StringComparison.Ordinal)) ||
                (goalRepair.GoalIndex > 0 && goal.GoalIndex == goalRepair.GoalIndex));
            if (targetGoal is null)
            {
                return new PrototypeFeedbackResult("", "missing_goal", "未找到需要修复的当前目标。", []);
            }

            runMemory = await _metadataStore.GetProjectRunMemoryAsync(project.ProjectId, BuildGoalMemoryScope(targetGoal.GoalIndex), cancellationToken);
        }

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var routeSkillAvailability = PrototypeRouteSkillPolicy.EnsureAvailable(project);
        if (!routeSkillAvailability.IsAvailable)
        {
            return new PrototypeFeedbackResult("", routeSkillAvailability.FailureCode, routeSkillAvailability.FailureMessage, []);
        }

        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return new PrototypeFeedbackResult(runId, "project_busy", "当前有任务正在执行，请等待完成后再试。", []);
        }

        await using var heavyRunnerLease = await _heavyRunnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, RunType, CancellationToken.None);
        await _metadataStore.MarkRunStartedAsync(runId, CancellationToken.None);
        await SetProgressAsync(runId, "running", "prepare", "正在准备快速修复任务。", CancellationToken.None);

        string submittedRelativePath = "";
        string resultRelativePath = "";
        string codexOutputRelativePath = "";
        string resultAbsolutePath = "";
        string codexOutputAbsolutePath = "";
        string now = DateTimeOffset.UtcNow.ToString("O");
        SkillActionDefinition? skillAction = null;
        ExecutionWorkspace? executionWorkspace = null;

        try
        {
            var relativeDir = Path.Combine("logs", "phase-a-quick-fix", project.ProjectId, runId);
            var absoluteDir = Path.Combine(project.RepoPath, relativeDir);
            Directory.CreateDirectory(absoluteDir);

            submittedRelativePath = ToSlash(Path.Combine(relativeDir, "submitted-feedback.md"));
            resultRelativePath = ToSlash(Path.Combine(relativeDir, "result-log.md"));
            codexOutputRelativePath = ToSlash(Path.Combine(relativeDir, "codex-output.txt"));
            var submittedAbsolutePath = Path.Combine(project.RepoPath, submittedRelativePath.Replace('/', Path.DirectorySeparatorChar));
            resultAbsolutePath = Path.Combine(project.RepoPath, resultRelativePath.Replace('/', Path.DirectorySeparatorChar));
            codexOutputAbsolutePath = Path.Combine(project.RepoPath, codexOutputRelativePath.Replace('/', Path.DirectorySeparatorChar));
            skillAction = ResolveSkillAction(request.SkillActionId);
            var routeSkill = PrototypeRouteSkillPolicy.Resolve(project);
            var routeProfile = PrototypeRouteSkillPolicy.ResolveProfile(project);
            executionWorkspace = PrepareExecutionWorkspace(project, targetGoal, runId, codexOutputAbsolutePath);

            await File.WriteAllTextAsync(
                submittedAbsolutePath,
                BuildSubmittedFeedback(project, runId, feedback, now, skillAction, targetGoal),
                Encoding.UTF8,
                CancellationToken.None);

            PrototypeGoalGodotSmokeValidationResult? preflightGodotSmokeFailure = null;
            var preflightResult = targetGoal is null || iterationDetails is null
                ? null
                : await TryCompleteAlreadySatisfiedGoalAsync(
                    project,
                    iterationDetails,
                    targetGoal,
                    runId,
                    submittedRelativePath,
                    resultRelativePath,
                    resultAbsolutePath,
                    codexOutputRelativePath,
                    codexOutputAbsolutePath,
                    routeSkill,
                    skillAction,
                    now,
                    smokeFailure => preflightGodotSmokeFailure = smokeFailure,
                    CancellationToken.None);
            if (preflightResult is not null)
            {
                return preflightResult;
            }

            var model = PrototypeModelPolicy.Normalize(request.Model);
            var effectiveTimeout = goalRepairMode
                ? Max(_executionTimeout, DefaultGoalRepairExecutionTimeout)
                : _executionTimeout;
            using var timeout = new CancellationTokenSource();
            timeout.CancelAfter(effectiveTimeout);
            var prototypeContract = _contractService.Read(project);
            await SetProgressAsync(runId, "running", "godot_diagnostic", "Checking recent Godot validation errors before repair.", CancellationToken.None);
            var godotDiagnostic = preflightGodotSmokeFailure is null
                ? await GodotFailureDiagnosticService.AnalyzeLatestAsync(_metadataStore, project, CancellationToken.None)
                : BuildGodotDiagnosticFromSmokeFailure(preflightGodotSmokeFailure);
            var godotCleanup = await GodotFailureDiagnosticService.CleanupIfRecommendedAsync(project, godotDiagnostic, CancellationToken.None);
            var currentAcceptanceValidation = targetGoal is null
                ? PrototypeGoalAcceptanceValidationResult.NotRun()
                : await PrototypeGoalAcceptanceValidator.ValidateAsync(project, targetGoal, _processRunner, CancellationToken.None);
            var prompt = BuildCodexPrompt(project, runId, feedback, skillAction, targetGoal, runMemory, prototypeContract, godotDiagnostic, godotCleanup, currentAcceptanceValidation);
            await SetProgressAsync(runId, "running", "codex", goalRepairMode ? $"Codex 正在修复目标 {targetGoal!.GoalIndex}。" : "Codex 正在执行快速修复。", CancellationToken.None);
            var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, CancellationToken.None);
            var billingApiKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
            var billingBefore = await _billingClient.CaptureAsync(billingApiKeyName, CancellationToken.None);
            var codexResult = await _processRunner.RunAsync(CodexHostedProcessCommandFactory.ApplyRuntime(BuildCodexCommand(prompt, executionWorkspace.CodexOutputPath, model, executionWorkspace.RootPath), runtimeCredential), timeout.Token);
            var providerBilling = new AiCodeMirrorBillingDelta(billingBefore, await _billingClient.CaptureAsync(billingApiKeyName, CancellationToken.None));
            if (executionWorkspace.SyncBack)
            {
                SyncFocusedWorkspaceBack(executionWorkspace, project.RepoPath);
            }

            if (File.Exists(executionWorkspace.CodexOutputPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(codexOutputAbsolutePath)!);
                File.Copy(executionWorkspace.CodexOutputPath, codexOutputAbsolutePath, overwrite: true);
            }

            var codexOutput = File.Exists(codexOutputAbsolutePath)
                ? await File.ReadAllTextAsync(codexOutputAbsolutePath, Encoding.UTF8, CancellationToken.None)
                : "";
            var publicCodexReport = BuildPublicCodexReport(codexResult, codexOutput);
            var assistantMessage = BuildAssistantMessage(publicCodexReport, targetGoal);
            var acceptanceValidation = targetGoal is null
                ? PrototypeGoalAcceptanceValidationResult.NotRun()
                : await PrototypeGoalAcceptanceValidator.ValidateAsync(project, targetGoal, _processRunner, CancellationToken.None);
            var godotSmokeValidation = PrototypeGoalGodotSmokeValidationResult.NotRequired();
            var rpgGdUnitValidation = PrototypeRpgGdUnitValidationResult.NotRequired("not_final_rpg_acceptance_goal");
            var projectSmokeValidation = targetGoal is null
                ? await ValidateProjectSmokeAfterQuickFixAsync(project, CancellationToken.None)
                : PrototypeGoalGodotSmokeValidationResult.NotRequired();
            if (acceptanceValidation.Passed)
            {
                assistantMessage = AppendAcceptanceValidationSummary(assistantMessage, targetGoal!);
                codexOutput = AppendAcceptanceValidationEvidence(codexOutput);
                var prototypeState = new PrototypeRouteStateWriter().ReadLatestPrototypeState(project);
                godotSmokeValidation = await PrototypeGodotSmokeService.ValidateGoalAsync(project, targetGoal!, prototypeState, _options, _processRunner, CancellationToken.None);
                if (godotSmokeValidation.Passed && godotSmokeValidation.Required)
                {
                    assistantMessage = BuildValidatedGoalRepairSummary(targetGoal!);
                    codexOutput = AppendGodotSmokeValidationEvidence(codexOutput);
                    rpgGdUnitValidation = await ValidateGoalRpgGdUnitAsync(project, targetGoal!, CancellationToken.None);
                    var rpgGdUnitBlocksGoal = IsRpgGdUnitBlockingForGoal(targetGoal!, rpgGdUnitValidation);
                    if (rpgGdUnitBlocksGoal)
                    {
                        assistantMessage = AppendRpgGdUnitValidationFailure(project, assistantMessage, rpgGdUnitValidation);
                        codexOutput = AppendRpgGdUnitValidationFailureEvidence(project, codexOutput, rpgGdUnitValidation);
                    }
                }
                else if (godotSmokeValidation.Required)
                {
                    assistantMessage = AppendGodotSmokeValidationFailure(assistantMessage, godotSmokeValidation);
                }
            }
            else if (targetGoal is not null && string.Equals(acceptanceValidation.Status, "failed", StringComparison.Ordinal))
            {
                assistantMessage = AppendAcceptanceValidationFailure(assistantMessage, targetGoal, acceptanceValidation);
                codexOutput = AppendAcceptanceValidationFailureEvidence(codexOutput, acceptanceValidation);
            }
            else if (projectSmokeValidation.Required)
            {
                assistantMessage = projectSmokeValidation.Passed
                    ? AppendProjectSmokeValidationSummary(assistantMessage)
                    : AppendProjectSmokeValidationFailure(assistantMessage, projectSmokeValidation);
            }
            await SetProgressAsync(runId, "running", "finalize", goalRepairMode ? "目标修复结果已返回，正在整理状态。" : "快速修复结果已返回，正在整理日志。", CancellationToken.None);

            var mutationGuardValidation = PrototypeRepairMutationGuard.Validate(project, targetGoal);
            if (!mutationGuardValidation.Passed)
            {
                assistantMessage = AppendMutationGuardFailure(assistantMessage, mutationGuardValidation);
                codexOutput = AppendMutationGuardFailureEvidence(codexOutput, mutationGuardValidation);
            }

            var goalRepairOutcome = targetGoal is null
                ? null
                : !mutationGuardValidation.Passed
                    ? new GoalRepairOutcome("needs_fix", false)
                : acceptanceValidation.Passed
                    ? godotSmokeValidation.Passed && !IsRpgGdUnitBlockingForGoal(targetGoal, rpgGdUnitValidation)
                        ? new GoalRepairOutcome("succeeded", true)
                        : new GoalRepairOutcome("needs_fix", false)
                    : RequiresHardPlatformAcceptance(targetGoal, acceptanceValidation)
                        ? new GoalRepairOutcome("needs_fix", false)
                    : DetermineGoalRepairOutcome(targetGoal, assistantMessage, codexResult, codexOutput);

            await File.WriteAllTextAsync(
                resultAbsolutePath,
                BuildResultLog(project, runId, feedback, assistantMessage, model, codexResult, codexOutput, now, skillAction, targetGoal, goalRepairOutcome),
                Encoding.UTF8,
                CancellationToken.None);

            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                project.ProjectId,
                "prototype-quick-fix-submission",
                submittedRelativePath,
                "Prototype quick fix submission"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                project.ProjectId,
                "prototype-quick-fix-result-log",
                resultRelativePath,
                "Prototype quick fix result log"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                project.ProjectId,
                "prototype-quick-fix-codex-output",
                codexOutputRelativePath,
                "Prototype quick fix Codex output"), CancellationToken.None);

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                model,
                submitted_feedback = submittedRelativePath,
                result_log = resultRelativePath,
                codex_output = codexOutputRelativePath,
                route_skill = routeSkill,
                game_type_profile = routeProfile,
                prototype_contract = prototypeContract.RelativePath,
                prototype_contract_present = !string.IsNullOrWhiteSpace(prototypeContract.Json),
                skill_action_id = skillAction?.ActionId,
                skill_name = skillAction?.SkillName,
                quick_fix = true,
                goal_repair = targetGoal is not null,
                goal_id = targetGoal?.GoalId,
                goal_index = targetGoal?.GoalIndex,
                goal_repair_status = goalRepairOutcome?.GoalStatus,
                acceptance_validation = acceptanceValidation.Kind,
                acceptance_validation_status = acceptanceValidation.Status,
                acceptance_validation_reason = acceptanceValidation.Reason,
                acceptance_validation_details = acceptanceValidation.Details,
                mutation_guard = mutationGuardValidation.ToEvidence(),
                godot_diagnostic = GodotFailureDiagnosticService.ToEvidence(godotDiagnostic, godotCleanup),
                godot_smoke_validation = godotSmokeValidation.ToEvidence(),
                rpg_gdunit_validation = rpgGdUnitValidation.ToEvidence(),
                project_smoke_validation = projectSmokeValidation.ToEvidence()
            });
            var nonGoalSmokeFailed = targetGoal is null && projectSmokeValidation.Required && !projectSmokeValidation.Passed;
            var runStatus = nonGoalSmokeFailed ? "failed" : "completed";
            var runExitCode = nonGoalSmokeFailed ? Math.Max(1, projectSmokeValidation.Smoke.ExitCode) : codexResult.ExitCode;
            await _metadataStore.CompleteRunAsync(runId, runStatus, runExitCode, codexResult.Stdout, codexResult.Stderr, evidenceJson, CancellationToken.None);
            await _metadataStore.RecordRunLlmAuditAsync(
                runId,
                "codex-cli",
                null,
                model,
                LlmUsageAuditJson.BuildCodexUsageJson(
                    operation: RunType,
                    model: model,
                    tokenUsage: CodexUsageExtractor.Extract(codexResult.Stdout, codexResult.Stderr),
                    runType: RunType,
                    projectId: project.ProjectId,
                    skillActionId: skillAction?.ActionId,
                    skillName: skillAction?.SkillName,
                    route: targetGoal is null ? "quick-fix" : "needs-fix",
                    exitCode: codexResult.ExitCode,
                    providerBilling: providerBilling),
                CancellationToken.None);
            if (targetGoal is not null && iterationDetails is not null && goalRepairOutcome is not null)
            {
                var iterationPlanState = _stateWriter.ReadLatestIterationPlanState(project);
                await _metadataStore.UpdateProjectIterationGoalStatusAsync(
                    targetGoal.GoalId,
                    goalRepairOutcome.GoalStatus,
                    assistantMessage,
                    goalRepairOutcome.MarkCompleted ? now : null,
                    CancellationToken.None);
                await _metadataStore.LinkProjectIterationGoalRunAsync(iterationDetails.Session.SessionId, targetGoal.GoalId, runId, "prototype-iteration-goal-repair", CancellationToken.None);

                var refreshed = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, CancellationToken.None);
                var hasNeedsFix = refreshed?.Goals.Any(goal => string.Equals(goal.Status, "needs_fix", StringComparison.Ordinal)) == true;
                var hasMoreGoals = refreshed?.Goals.Any(goal => string.Equals(goal.Status, "pending", StringComparison.Ordinal)) == true;
                var currentGoalIndex = goalRepairOutcome.GoalStatus == "succeeded"
                    ? targetGoal.GoalIndex
                    : refreshed?.Session.CurrentGoalIndex ?? targetGoal.GoalIndex;
                var sessionStatus = goalRepairOutcome.GoalStatus == "succeeded"
                    ? (hasMoreGoals ? "paused_for_review" : "completed")
                    : "needs_fix";
                var sessionSummary = goalRepairOutcome.GoalStatus == "succeeded"
                    ? (hasMoreGoals
                        ? $"目标 {targetGoal.GoalIndex} 已修复完成。请确认后决定是否继续目标 {targetGoal.GoalIndex + 1}。"
                        : "所有迭代目标已完成。")
                    : $"目标 {targetGoal.GoalIndex} 仍需修复。请继续修复当前目标，不要继续后续目标。";
                await _metadataStore.UpdateProjectIterationSessionStatusAsync(
                    iterationDetails.Session.SessionId,
                    sessionStatus,
                    currentGoalIndex,
                    sessionSummary,
                    refreshed?.Session.LatestEvaluationJson,
                    sessionStatus == "completed" ? now : null,
                    CancellationToken.None);
                PrototypeIterationPlanningAnalysisUpdater.Refresh(_stateWriter, project, iterationPlanState, targetGoal, goalRepairOutcome.GoalStatus, assistantMessage, now, sessionSummary);
                await UpsertGoalRunMemoryAsync(project.ProjectId, targetGoal, goalRepairOutcome.GoalStatus, sessionSummary, assistantMessage, goalRepairOutcome.GoalStatus == "succeeded" ? [] : [sessionSummary], CancellationToken.None);

                await SetProgressAsync(runId, "completed", "", goalRepairOutcome.GoalStatus == "succeeded" ? $"目标 {targetGoal.GoalIndex} 修复完成。" : $"目标 {targetGoal.GoalIndex} 仍需继续修复。", CancellationToken.None);

                var goalArtifacts = await _metadataStore.ListArtifactsForRunAsync(runId, CancellationToken.None);
                return new PrototypeFeedbackResult(
                    runId,
                    "completed",
                    assistantMessage,
                    goalArtifacts,
                    sessionStatus,
                    goalRepairOutcome.GoalStatus,
                    targetGoal.GoalIndex);
            }

            if (nonGoalSmokeFailed)
            {
                await SetProgressAsync(runId, "failed", "validation", "快速修复后验收未通过，仍需继续修复当前原型。", CancellationToken.None);
            }
            else
            {
                await SetProgressAsync(runId, "completed", "", projectSmokeValidation.Required ? "快速修复已完成，并通过原型验收。" : "快速修复已完成。", CancellationToken.None);
            }

            var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, CancellationToken.None);
            return new PrototypeFeedbackResult(runId, runStatus, assistantMessage, artifacts);
        }
        catch (OperationCanceledException)
        {
            var effectiveTimeout = goalRepairMode
                ? Max(_executionTimeout, DefaultGoalRepairExecutionTimeout)
                : _executionTimeout;
            if (targetGoal is not null && iterationDetails is not null)
            {
                var timeoutRecovery = await TryCompleteTimedOutGoalIfValidatedAsync(
                    project,
                    iterationDetails,
                    targetGoal,
                    runId,
                    submittedRelativePath,
                    resultRelativePath,
                    resultAbsolutePath,
                    codexOutputRelativePath,
                    codexOutputAbsolutePath,
                    executionWorkspace,
                    skillAction,
                    now,
                    effectiveTimeout,
                    CancellationToken.None);
                if (timeoutRecovery is not null)
                {
                    return timeoutRecovery;
                }

                var evidenceJson = JsonSerializer.Serialize(new
                {
                    run_type = RunType,
                    failure_code = "prototype_quick_fix_timeout"
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", 408, "", $"Prototype quick fix exceeded the {effectiveTimeout.TotalSeconds:0} second timeout.", evidenceJson, CancellationToken.None);
                var timeoutFocus = BuildGoalRepairTimeoutFocus(targetGoal);
                var summary = $"目标 {targetGoal.GoalIndex} 修复超时。当前目标仍需修复；下一轮应继续聚焦当前 step，并优先缩小到最小验收范围：{timeoutFocus}";
                var iterationPlanState = _stateWriter.ReadLatestIterationPlanState(project);
                await _metadataStore.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", summary, null, CancellationToken.None);
                await _metadataStore.UpdateProjectIterationSessionStatusAsync(iterationDetails.Session.SessionId, "needs_fix", targetGoal.GoalIndex, summary, iterationDetails.Session.LatestEvaluationJson, null, CancellationToken.None);
                PrototypeIterationPlanningAnalysisUpdater.Refresh(_stateWriter, project, iterationPlanState, targetGoal, "needs_fix", summary, DateTimeOffset.UtcNow.ToString("O"), summary);
                await UpsertGoalRunMemoryAsync(projectId, targetGoal, "needs_fix", $"继续修复当前 step 的最小验收范围：{timeoutFocus}", summary, [summary], CancellationToken.None);
                await SetProgressAsync(runId, "failed", "timeout", $"目标 {targetGoal.GoalIndex} 修复超时，仍需继续修复。", CancellationToken.None);
                return new PrototypeFeedbackResult(runId, "failed", "当前目标修复超时。系统没有切换到后续目标，你可以继续再次修复当前 step。", [], "needs_fix", "needs_fix", targetGoal.GoalIndex);
            }

            var timeoutEvidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                failure_code = "prototype_quick_fix_timeout"
            });
            await _metadataStore.CompleteRunAsync(runId, "failed", 408, "", $"Prototype quick fix exceeded the {effectiveTimeout.TotalSeconds:0} second timeout.", timeoutEvidenceJson, CancellationToken.None);
            await SetProgressAsync(runId, "failed", "timeout", "快速修复超时，请改用正式反馈或缩小问题范围。", CancellationToken.None);
            return new PrototypeFeedbackResult(runId, "failed", "快速修复超时。请改用正式反馈，或把问题描述得更小、更明确。", []);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                failure_code = "prototype_quick_fix_failed"
            });
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.Message, evidenceJson, CancellationToken.None);
            if (targetGoal is not null && iterationDetails is not null)
            {
                var summary = $"目标 {targetGoal.GoalIndex} 修复失败。当前目标仍需修复，请继续聚焦本 step。";
                var iterationPlanState = _stateWriter.ReadLatestIterationPlanState(project);
                await _metadataStore.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", summary, null, CancellationToken.None);
                await _metadataStore.UpdateProjectIterationSessionStatusAsync(iterationDetails.Session.SessionId, "needs_fix", targetGoal.GoalIndex, summary, iterationDetails.Session.LatestEvaluationJson, null, CancellationToken.None);
                PrototypeIterationPlanningAnalysisUpdater.Refresh(_stateWriter, project, iterationPlanState, targetGoal, "needs_fix", summary, DateTimeOffset.UtcNow.ToString("O"), summary);
                await UpsertGoalRunMemoryAsync(projectId, targetGoal, "needs_fix", summary, "当前目标修复失败。", [summary], CancellationToken.None);
                await SetProgressAsync(runId, "failed", "error", $"目标 {targetGoal.GoalIndex} 修复失败，仍需继续修复。", CancellationToken.None);
                return new PrototypeFeedbackResult(runId, "failed", "当前目标修复失败。系统没有推进后续目标，请继续修复这个 step。", [], "needs_fix", "needs_fix", targetGoal.GoalIndex);
            }

            await SetProgressAsync(runId, "failed", "error", "快速修复失败，请查看运行记录。", CancellationToken.None);
            return new PrototypeFeedbackResult(runId, "failed", "快速修复失败，请稍后重试。", []);
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    private SkillActionDefinition? ResolveSkillAction(string? actionId)
    {
        if (string.IsNullOrWhiteSpace(actionId) ||
            string.Equals(actionId.Trim(), "normal", StringComparison.Ordinal))
        {
            return null;
        }

        return _skillActionCatalog.Find(actionId.Trim());
    }

    private static TimeSpan Max(TimeSpan left, TimeSpan right)
    {
        return left >= right ? left : right;
    }

    private async Task<bool> HasSucceededPrototypeWorkflowAsync(string projectId, CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(projectId, cancellationToken);
        return runs.Any(run => run.RunType == "prototype-7day-playable" && run.Status == "succeeded");
    }

    private async Task<PrototypeFeedbackResult?> TryCompleteAlreadySatisfiedGoalAsync(
        ProjectSnapshot project,
        ProjectIterationSessionDetails iterationDetails,
        ProjectIterationGoalSnapshot targetGoal,
        string runId,
        string submittedRelativePath,
        string resultRelativePath,
        string resultAbsolutePath,
        string codexOutputRelativePath,
        string codexOutputAbsolutePath,
        object routeSkill,
        SkillActionDefinition? skillAction,
        string now,
        Action<PrototypeGoalGodotSmokeValidationResult>? onGodotSmokeFailure = null,
        CancellationToken cancellationToken = default)
    {
        await SetProgressAsync(runId, "running", "preflight", $"正在检查目标 {targetGoal.GoalIndex} 是否已经满足验收。", cancellationToken);
        var acceptanceValidation = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, targetGoal, _processRunner, cancellationToken);
        if (!acceptanceValidation.Passed)
        {
            return null;
        }

        var mutationGuardValidation = PrototypeRepairMutationGuard.Validate(project, targetGoal);
        if (!mutationGuardValidation.Passed)
        {
            return null;
        }

        var assistantMessage = $"""
            当前目标已经通过平台验收。

            Platform acceptance:
            Goal {targetGoal.GoalIndex} passed its platform validation. The current goal can move to the next step.
            """;
        var codexOutput = "Preflight validation passed before running Codex.";
        var godotSmokeValidation = PrototypeGoalGodotSmokeValidationResult.NotRequired();
        var rpgGdUnitValidation = PrototypeRpgGdUnitValidationResult.NotRequired("not_final_rpg_acceptance_goal");
        godotSmokeValidation = await ValidateGoalGodotSmokeWithTimeoutAsync(project, targetGoal, cancellationToken);
        if (godotSmokeValidation.Passed && godotSmokeValidation.Required)
        {
            assistantMessage = AppendGodotSmokeValidationSummary(assistantMessage, targetGoal, godotSmokeValidation);
            codexOutput = AppendGodotSmokeValidationEvidence(codexOutput);
            rpgGdUnitValidation = await ValidateGoalRpgGdUnitAsync(project, targetGoal, cancellationToken);
            if (IsRpgGdUnitBlockingForGoal(targetGoal, rpgGdUnitValidation))
            {
                assistantMessage = AppendRpgGdUnitValidationFailure(project, assistantMessage, rpgGdUnitValidation);
                codexOutput = AppendRpgGdUnitValidationFailureEvidence(project, codexOutput, rpgGdUnitValidation);
                return null;
            }
        }
        else if (godotSmokeValidation.Required)
        {
            assistantMessage = AppendGodotSmokeValidationFailure(assistantMessage, godotSmokeValidation);
            if (godotSmokeValidation.Smoke.Ran)
            {
                onGodotSmokeFailure?.Invoke(godotSmokeValidation);
                return null;
            }
        }

        var goalRepairOutcome = godotSmokeValidation.Passed
            ? new GoalRepairOutcome("succeeded", true)
            : new GoalRepairOutcome("needs_fix", false);

        await File.WriteAllTextAsync(codexOutputAbsolutePath, codexOutput, Encoding.UTF8, cancellationToken);
        await File.WriteAllTextAsync(
            resultAbsolutePath,
            BuildResultLog(
                project,
                runId,
                "Preflight validation",
                assistantMessage,
                PrototypeModelPolicy.Normalize(null),
                new HostedProcessResult(0, "Preflight validation passed.", ""),
                codexOutput,
                now,
                skillAction,
                targetGoal,
                goalRepairOutcome),
            Encoding.UTF8,
            cancellationToken);

        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "prototype-quick-fix-submission",
            submittedRelativePath,
            "Prototype quick fix submission"), cancellationToken);
        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "prototype-quick-fix-result-log",
            resultRelativePath,
            "Prototype quick fix result log"), cancellationToken);
        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "prototype-quick-fix-codex-output",
            codexOutputRelativePath,
            "Prototype quick fix Codex output"), cancellationToken);

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            preflight = true,
            submitted_feedback = submittedRelativePath,
            result_log = resultRelativePath,
            codex_output = codexOutputRelativePath,
            route_skill = routeSkill,
            game_type_profile = PrototypeRouteSkillPolicy.ResolveProfile(project),
            skill_action_id = skillAction?.ActionId,
            skill_name = skillAction?.SkillName,
            quick_fix = true,
            goal_repair = true,
            goal_id = targetGoal.GoalId,
            goal_index = targetGoal.GoalIndex,
            goal_repair_status = goalRepairOutcome.GoalStatus,
            acceptance_validation = acceptanceValidation.Kind,
            acceptance_validation_status = acceptanceValidation.Status,
            acceptance_validation_reason = acceptanceValidation.Reason,
            acceptance_validation_details = acceptanceValidation.Details,
            godot_smoke_validation = godotSmokeValidation.ToEvidence(),
            rpg_gdunit_validation = rpgGdUnitValidation.ToEvidence(),
            post_acceptance_validation_status = goalRepairOutcome.GoalStatus == "succeeded" ? "passed" : "failed",
            post_acceptance_validation_reason = goalRepairOutcome.GoalStatus == "succeeded" ? null : "godot_smoke_validation_failed"
        });
        await _metadataStore.CompleteRunAsync(runId, "completed", 0, "Preflight validation passed.", "", evidenceJson, cancellationToken);
        var iterationPlanState = _stateWriter.ReadLatestIterationPlanState(project);
        await _metadataStore.UpdateProjectIterationGoalStatusAsync(
            targetGoal.GoalId,
            goalRepairOutcome.GoalStatus,
            assistantMessage,
            goalRepairOutcome.MarkCompleted ? now : null,
            cancellationToken);
        await _metadataStore.LinkProjectIterationGoalRunAsync(iterationDetails.Session.SessionId, targetGoal.GoalId, runId, "prototype-iteration-goal-repair-preflight", cancellationToken);

        var refreshed = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, cancellationToken);
        var hasNeedsFix = refreshed?.Goals.Any(goal => string.Equals(goal.Status, "needs_fix", StringComparison.Ordinal)) == true;
        var hasMoreGoals = refreshed?.Goals.Any(goal => string.Equals(goal.Status, "pending", StringComparison.Ordinal)) == true;
        var sessionStatus = goalRepairOutcome.GoalStatus == "succeeded"
            ? (hasMoreGoals ? "paused_for_review" : "completed")
            : "needs_fix";
        var sessionSummary = goalRepairOutcome.GoalStatus == "succeeded"
            ? (hasMoreGoals
                ? $"目标 {targetGoal.GoalIndex} 已通过验收。请确认后决定是否继续目标 {targetGoal.GoalIndex + 1}。"
                : "所有迭代目标已完成。")
            : $"目标 {targetGoal.GoalIndex} 已通过核心验收，但仍需继续完成引擎验证。";
        if (hasNeedsFix && goalRepairOutcome.GoalStatus == "succeeded")
        {
            sessionStatus = "needs_fix";
        }

        await _metadataStore.UpdateProjectIterationSessionStatusAsync(
            iterationDetails.Session.SessionId,
            sessionStatus,
            targetGoal.GoalIndex,
            sessionSummary,
            refreshed?.Session.LatestEvaluationJson,
            sessionStatus == "completed" ? now : null,
            cancellationToken);
        PrototypeIterationPlanningAnalysisUpdater.Refresh(_stateWriter, project, iterationPlanState, targetGoal, goalRepairOutcome.GoalStatus, assistantMessage, now, sessionSummary);
        await UpsertGoalRunMemoryAsync(project.ProjectId, targetGoal, goalRepairOutcome.GoalStatus, sessionSummary, assistantMessage, goalRepairOutcome.GoalStatus == "succeeded" ? [] : [sessionSummary], cancellationToken);
        await SetProgressAsync(runId, "completed", "", goalRepairOutcome.GoalStatus == "succeeded" ? $"目标 {targetGoal.GoalIndex} 验收完成。" : $"目标 {targetGoal.GoalIndex} 仍需继续修复。", cancellationToken);

        var goalArtifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
        return new PrototypeFeedbackResult(
            runId,
            "completed",
            assistantMessage,
            goalArtifacts,
            sessionStatus,
            goalRepairOutcome.GoalStatus,
            targetGoal.GoalIndex);
    }

    private static GodotFailureDiagnostic BuildGodotDiagnosticFromSmokeFailure(PrototypeGoalGodotSmokeValidationResult validation)
    {
        var smoke = validation.Smoke;
        var excerpt = string.Join(
            Environment.NewLine,
            new[]
            {
                $"Reason: {smoke.Reason}",
                $"Scene: {smoke.ScenePath}",
                TrimForPromptExcerpt(smoke.Stdout, 700),
                TrimForPromptExcerpt(smoke.Stderr, 700)
            }.Where(static value => !string.IsNullOrWhiteSpace(value)));

        return new GodotFailureDiagnostic(
            true,
            false,
            "Latest Godot smoke validation failed after platform static acceptance. The repair must fix the concrete Godot stderr item. Scene parse errors in Game.Godot/Examples usually mean .tscn files start with UTF-8 BOM and must be rewritten without BOM. A Control anchor warning with C# backtrace means the named script line must stop setting Size directly on a Control with non-equal opposite anchors; use fixed anchors, CustomMinimumSize, or deferred sizing for that node. A Control can't grab focus warning means the named script line must stop calling GrabFocus on a non-focusable container or configure an appropriate focus mode before requesting focus.",
            excerpt,
            null);
    }

    private async Task<PrototypeFeedbackResult?> TryCompleteTimedOutGoalIfValidatedAsync(
        ProjectSnapshot project,
        ProjectIterationSessionDetails iterationDetails,
        ProjectIterationGoalSnapshot targetGoal,
        string runId,
        string submittedRelativePath,
        string resultRelativePath,
        string resultAbsolutePath,
        string codexOutputRelativePath,
        string codexOutputAbsolutePath,
        ExecutionWorkspace? executionWorkspace,
        SkillActionDefinition? skillAction,
        string now,
        TimeSpan effectiveTimeout,
        CancellationToken cancellationToken)
    {
        try
        {
            if (executionWorkspace?.SyncBack == true && Directory.Exists(executionWorkspace.RootPath))
            {
                SyncFocusedWorkspaceBack(executionWorkspace, project.RepoPath);
            }

            if (executionWorkspace is not null && File.Exists(executionWorkspace.CodexOutputPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(codexOutputAbsolutePath)!);
                File.Copy(executionWorkspace.CodexOutputPath, codexOutputAbsolutePath, overwrite: true);
            }

            var acceptanceValidation = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, targetGoal, _processRunner, cancellationToken);
            if (!acceptanceValidation.Passed)
            {
                return await CompleteTimedOutGoalValidationFailureAsync(
                    project,
                    iterationDetails,
                    targetGoal,
                    runId,
                    submittedRelativePath,
                    resultRelativePath,
                    resultAbsolutePath,
                    codexOutputRelativePath,
                    codexOutputAbsolutePath,
                    skillAction,
                    now,
                    effectiveTimeout,
                    acceptanceValidation,
                    PrototypeGoalGodotSmokeValidationResult.NotRequired(),
                    "platform_acceptance_validation_failed",
                    cancellationToken);
            }

            var godotSmokeValidation = await ValidateGoalGodotSmokeWithTimeoutAsync(project, targetGoal, cancellationToken);
            if (!godotSmokeValidation.Passed)
            {
                return await CompleteTimedOutGoalValidationFailureAsync(
                    project,
                    iterationDetails,
                    targetGoal,
                    runId,
                    submittedRelativePath,
                    resultRelativePath,
                    resultAbsolutePath,
                    codexOutputRelativePath,
                    codexOutputAbsolutePath,
                    skillAction,
                    now,
                    effectiveTimeout,
                    acceptanceValidation,
                    godotSmokeValidation,
                    godotSmokeValidation.Smoke.Reason,
                    cancellationToken);
            }

            var rpgGdUnitValidation = await ValidateGoalRpgGdUnitAsync(project, targetGoal, cancellationToken);
            if (IsRpgGdUnitBlockingForGoal(targetGoal, rpgGdUnitValidation))
            {
                return await CompleteTimedOutGoalValidationFailureAsync(
                    project,
                    iterationDetails,
                    targetGoal,
                    runId,
                    submittedRelativePath,
                    resultRelativePath,
                    resultAbsolutePath,
                    codexOutputRelativePath,
                    codexOutputAbsolutePath,
                    skillAction,
                    now,
                    effectiveTimeout,
                    acceptanceValidation,
                    godotSmokeValidation,
                    rpgGdUnitValidation.Reason,
                    cancellationToken);
            }

            var codexOutput = File.Exists(codexOutputAbsolutePath)
                ? await File.ReadAllTextAsync(codexOutputAbsolutePath, Encoding.UTF8, cancellationToken)
                : "Codex repair timed out after writing changes, but platform validation passed afterward.";
            if (!File.Exists(codexOutputAbsolutePath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(codexOutputAbsolutePath)!);
                await File.WriteAllTextAsync(codexOutputAbsolutePath, codexOutput, Encoding.UTF8, cancellationToken);
            }

            var assistantMessage = $"""
                目标 {targetGoal.GoalIndex} 修复已通过平台复验。
                本次修复进程超过 {effectiveTimeout.TotalSeconds:0} 秒后被终止，但文件变更已经落盘，并且当前目标的静态验收与 Godot smoke 验证均已通过。
                """;
            await File.WriteAllTextAsync(
                resultAbsolutePath,
                BuildResultLog(
                    project,
                    runId,
                    "Timed-out repair validated after cancellation",
                    assistantMessage,
                    PrototypeModelPolicy.Normalize(null),
                    new HostedProcessResult(408, "", $"Prototype quick fix exceeded the {effectiveTimeout.TotalSeconds:0} second timeout."),
                    codexOutput,
                    now,
                    skillAction,
                    targetGoal,
                    new GoalRepairOutcome("succeeded", true)),
                Encoding.UTF8,
                cancellationToken);

            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                project.ProjectId,
                "prototype-quick-fix-submission",
                submittedRelativePath,
                "Prototype quick fix submission"), cancellationToken);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                project.ProjectId,
                "prototype-quick-fix-result-log",
                resultRelativePath,
                "Prototype quick fix result log"), cancellationToken);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
                runId,
                project.ProjectId,
                "prototype-quick-fix-codex-output",
                codexOutputRelativePath,
                "Prototype quick fix Codex output"), cancellationToken);

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                failure_code = "prototype_quick_fix_timeout_validated_after_cancel",
                quick_fix = true,
                goal_repair = true,
                goal_id = targetGoal.GoalId,
                goal_index = targetGoal.GoalIndex,
                goal_repair_status = "succeeded",
                acceptance_validation = acceptanceValidation.Kind,
                acceptance_validation_status = acceptanceValidation.Status,
                acceptance_validation_reason = acceptanceValidation.Reason,
                acceptance_validation_details = acceptanceValidation.Details,
                godot_smoke_validation = godotSmokeValidation.ToEvidence(),
                rpg_gdunit_validation = rpgGdUnitValidation.ToEvidence()
            });
            await _metadataStore.CompleteRunAsync(
                runId,
                "completed",
                0,
                "Timed-out repair passed platform validation after cancellation.",
                "",
                evidenceJson,
                cancellationToken);

            var iterationPlanState = _stateWriter.ReadLatestIterationPlanState(project);
            await _metadataStore.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "succeeded", assistantMessage, now, cancellationToken);
            await _metadataStore.LinkProjectIterationGoalRunAsync(iterationDetails.Session.SessionId, targetGoal.GoalId, runId, "prototype-iteration-goal-repair-timeout-validated", cancellationToken);

            var refreshed = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, cancellationToken);
            var hasMoreGoals = refreshed?.Goals.Any(goal => string.Equals(goal.Status, "pending", StringComparison.Ordinal)) == true;
            var sessionStatus = hasMoreGoals ? "paused_for_review" : "completed";
            var sessionSummary = hasMoreGoals
                ? $"目标 {targetGoal.GoalIndex} 已通过超时后复验。请确认后决定是否继续目标 {targetGoal.GoalIndex + 1}。"
                : "所有迭代目标已完成。";
            await _metadataStore.UpdateProjectIterationSessionStatusAsync(
                iterationDetails.Session.SessionId,
                sessionStatus,
                targetGoal.GoalIndex,
                sessionSummary,
                refreshed?.Session.LatestEvaluationJson,
                sessionStatus == "completed" ? now : null,
                cancellationToken);
            PrototypeIterationPlanningAnalysisUpdater.Refresh(_stateWriter, project, iterationPlanState, targetGoal, "succeeded", assistantMessage, now, sessionSummary);
            await UpsertGoalRunMemoryAsync(project.ProjectId, targetGoal, "succeeded", sessionSummary, assistantMessage, [], cancellationToken);
            await SetProgressAsync(runId, "completed", "", $"目标 {targetGoal.GoalIndex} 已通过超时后复验。", cancellationToken);

            var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
            return new PrototypeFeedbackResult(runId, "completed", assistantMessage, artifacts, sessionStatus, "succeeded", targetGoal.GoalIndex);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            return null;
        }
    }

    private async Task<PrototypeFeedbackResult> CompleteTimedOutGoalValidationFailureAsync(
        ProjectSnapshot project,
        ProjectIterationSessionDetails iterationDetails,
        ProjectIterationGoalSnapshot targetGoal,
        string runId,
        string submittedRelativePath,
        string resultRelativePath,
        string resultAbsolutePath,
        string codexOutputRelativePath,
        string codexOutputAbsolutePath,
        SkillActionDefinition? skillAction,
        string now,
        TimeSpan effectiveTimeout,
        PrototypeGoalAcceptanceValidationResult acceptanceValidation,
        PrototypeGoalGodotSmokeValidationResult godotSmokeValidation,
        string? postAcceptanceReason,
        CancellationToken cancellationToken)
    {
        var codexOutput = File.Exists(codexOutputAbsolutePath)
            ? await File.ReadAllTextAsync(codexOutputAbsolutePath, Encoding.UTF8, cancellationToken)
            : "Codex repair timed out after writing changes, and platform validation still needs repair.";
        if (!File.Exists(codexOutputAbsolutePath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(codexOutputAbsolutePath)!);
            await File.WriteAllTextAsync(codexOutputAbsolutePath, codexOutput, Encoding.UTF8, cancellationToken);
        }

        var validationReason = !acceptanceValidation.Passed
            ? acceptanceValidation.Reason ?? acceptanceValidation.Status
            : postAcceptanceReason ?? godotSmokeValidation.Smoke.Reason;
        var timeoutFocus = BuildGoalRepairTimeoutFocus(targetGoal);
        var assistantMessage = $"""
            目标 {targetGoal.GoalIndex} 修复超时。当前目标仍需修复；下一轮应继续聚焦当前 step，并优先缩小到最小验收范围：{timeoutFocus}

            Goal {targetGoal.GoalIndex} repair timed out after {effectiveTimeout.TotalSeconds:0} seconds and still needs repair.

            Platform acceptance:
            STATUS: {(acceptanceValidation.Passed ? "passed" : "needs_fix")}
            REASON: {acceptanceValidation.Reason ?? acceptanceValidation.Status}

            Platform engine validation:
            STATUS: {(godotSmokeValidation.Passed ? "passed" : "needs_fix")}
            VERIFY: Godot smoke validation must pass before this goal can move forward.
            REMAINING: Continue repairing the current goal; do not advance to later goals yet.
            REASON: {validationReason}
            """;

        await File.WriteAllTextAsync(
            resultAbsolutePath,
            BuildResultLog(
                project,
                runId,
                "Timed-out repair still needs validation fixes",
                assistantMessage,
                PrototypeModelPolicy.Normalize(null),
                new HostedProcessResult(408, "", $"Prototype quick fix exceeded the {effectiveTimeout.TotalSeconds:0} second timeout."),
                codexOutput,
                now,
                skillAction,
                targetGoal,
                new GoalRepairOutcome("needs_fix", false)),
            Encoding.UTF8,
            cancellationToken);

        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "prototype-quick-fix-submission",
            submittedRelativePath,
            "Prototype quick fix submission"), cancellationToken);
        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "prototype-quick-fix-result-log",
            resultRelativePath,
            "Prototype quick fix result log"), cancellationToken);
        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "prototype-quick-fix-codex-output",
            codexOutputRelativePath,
            "Prototype quick fix Codex output"), cancellationToken);

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            failure_code = "prototype_quick_fix_timeout_validation_failed_after_cancel",
            quick_fix = true,
            goal_repair = true,
            goal_id = targetGoal.GoalId,
            goal_index = targetGoal.GoalIndex,
            goal_repair_status = "needs_fix",
            acceptance_validation = acceptanceValidation.Kind,
            acceptance_validation_status = acceptanceValidation.Status,
            acceptance_validation_reason = acceptanceValidation.Reason,
            acceptance_validation_details = acceptanceValidation.Details,
            godot_smoke_validation = godotSmokeValidation.ToEvidence(),
            post_acceptance_validation_status = "failed",
            post_acceptance_validation_reason = validationReason
        });
        await _metadataStore.CompleteRunAsync(
            runId,
            "failed",
            408,
            "",
            $"Prototype quick fix exceeded the {effectiveTimeout.TotalSeconds:0} second timeout; post-timeout validation still failed: {validationReason}",
            evidenceJson,
            cancellationToken);

        var iterationPlanState = _stateWriter.ReadLatestIterationPlanState(project);
        var sessionSummary = $"目标 {targetGoal.GoalIndex} 修复超时。当前目标仍需修复；下一轮应继续聚焦当前 step，并优先缩小到最小验收范围：{timeoutFocus} 验证原因：{validationReason}";
        await _metadataStore.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", assistantMessage, null, cancellationToken);
        await _metadataStore.LinkProjectIterationGoalRunAsync(iterationDetails.Session.SessionId, targetGoal.GoalId, runId, "prototype-iteration-goal-repair-timeout-validation-failed", cancellationToken);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(
            iterationDetails.Session.SessionId,
            "needs_fix",
            targetGoal.GoalIndex,
            sessionSummary,
            iterationDetails.Session.LatestEvaluationJson,
            null,
            cancellationToken);
        PrototypeIterationPlanningAnalysisUpdater.Refresh(_stateWriter, project, iterationPlanState, targetGoal, "needs_fix", assistantMessage, now, sessionSummary);
        await UpsertGoalRunMemoryAsync(project.ProjectId, targetGoal, "needs_fix", sessionSummary, assistantMessage, [sessionSummary], cancellationToken);
        await SetProgressAsync(runId, "failed", "validation", $"Goal {targetGoal.GoalIndex} timed out and still needs validation repair.", cancellationToken);

        var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
        return new PrototypeFeedbackResult(runId, "failed", assistantMessage, artifacts, "needs_fix", "needs_fix", targetGoal.GoalIndex);
    }

    private Task SetProgressAsync(string runId, string step, string substep, string label, CancellationToken cancellationToken)
    {
        return _metadataStore.UpdateRunProgressAsync(runId, step, substep, label, cancellationToken);
    }

    private async Task<PrototypeGoalGodotSmokeValidationResult> ValidateGoalGodotSmokeWithTimeoutAsync(
        ProjectSnapshot project,
        ProjectIterationGoalSnapshot targetGoal,
        CancellationToken cancellationToken)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(GodotSmokeValidationTimeout);
        var prototypeState = new PrototypeRouteStateWriter().ReadLatestPrototypeState(project);
        try
        {
            return await PrototypeGodotSmokeService.ValidateGoalAsync(project, targetGoal, prototypeState, _options, _processRunner, timeout.Token);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            var scenePath = ResolveSmokeSceneForTimeout(prototypeState);
            return PrototypeGoalGodotSmokeValidationResult.RequiredResult(new PrototypeGodotSmokeResult(
                true,
                124,
                "",
                $"Godot smoke validation exceeded the {GodotSmokeValidationTimeout.TotalSeconds:0} second timeout.",
                "godot_smoke_validation_timeout",
                scenePath));
        }
    }

    private async Task<PrototypeRpgGdUnitValidationResult> ValidateGoalRpgGdUnitAsync(
        ProjectSnapshot project,
        ProjectIterationGoalSnapshot targetGoal,
        CancellationToken cancellationToken)
    {
        if (!RequiresRpgGdUnitValidation(project, targetGoal))
        {
            return PrototypeRpgGdUnitValidationResult.NotRequired("not_final_rpg_acceptance_goal");
        }

        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(150));
        try
        {
            return await PrototypeGodotSmokeService.RunRpgGdUnitValidationAsync(
                _options,
                _processRunner,
                project,
                "dq-rpg",
                timeout.Token);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return PrototypeRpgGdUnitValidationResult.RequiredResult(
                false,
                124,
                "",
                "RPG GdUnit validation timed out.",
                "rpg_project_specific_gdunit_timeout",
                "tests/Prototype/DqRpgPrototype",
                null);
        }
    }

    private static bool RequiresRpgGdUnitValidation(ProjectSnapshot project, ProjectIterationGoalSnapshot targetGoal)
    {
        if (!PrototypeRouteSkillPolicy.IsRpgProject(project))
        {
            return false;
        }

        var text = string.Join(" ", targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint);
        return text.Contains("GdUnit", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("final prototype acceptance", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("full playable prototype acceptance", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("最终验收", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("全量验收", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsRpgGdUnitBlockingForGoal(
        ProjectIterationGoalSnapshot targetGoal,
        PrototypeRpgGdUnitValidationResult validation)
    {
        if (!validation.Required || validation.Passed)
        {
            return false;
        }

        if (RequiresFullRpgGdUnitValidation(targetGoal))
        {
            return true;
        }

        return HasBlockingRpgGdUnitInfrastructureFailure(validation);
    }

    private static bool RequiresFullRpgGdUnitValidation(ProjectIterationGoalSnapshot targetGoal)
    {
        var text = string.Join(" ", targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint);
        return text.Contains("final prototype acceptance", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("full playable prototype acceptance", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("Rerun RPG project-specific GdUnit", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("最终验收", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("全量验收", StringComparison.OrdinalIgnoreCase);
    }

    private static bool HasBlockingRpgGdUnitInfrastructureFailure(PrototypeRpgGdUnitValidationResult validation)
    {
        if (!validation.Ran)
        {
            return false;
        }

        var combined = string.Join(
            "\n",
            new[] { validation.Stdout, validation.Stderr, validation.Reason }.Where(static value => !string.IsNullOrWhiteSpace(value)));
        var blockingMarkers = new[]
        {
            "Failed loading resource",
            "Unable to open file",
            "Parse Error",
            "referenced non-existent resource",
            "Cannot instantiate C# script",
            "Node not found",
            "NullReferenceException",
            "SCRIPT ERROR",
            "Invalid call",
            "No test cases found",
            "rpg_gdunit_tests_missing",
            "rpg_project_specific_gdunit_timeout"
        };

        return blockingMarkers.Any(marker => combined.Contains(marker, StringComparison.OrdinalIgnoreCase));
    }

    private static string? ResolveSmokeSceneForTimeout(string prototypeStateJson)
    {
        if (string.IsNullOrWhiteSpace(prototypeStateJson))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(prototypeStateJson);
            var root = document.RootElement;
            if (root.TryGetProperty("prototype_completion", out var completion) &&
                completion.ValueKind == JsonValueKind.Object &&
                completion.TryGetProperty("smoke_scene", out var completionScene) &&
                completionScene.ValueKind == JsonValueKind.String)
            {
                return completionScene.GetString();
            }

            if (root.TryGetProperty("godot_smoke", out var smoke) &&
                smoke.ValueKind == JsonValueKind.Object &&
                smoke.TryGetProperty("scene", out var scene) &&
                scene.ValueKind == JsonValueKind.String)
            {
                return scene.GetString();
            }
        }
        catch (JsonException)
        {
            return null;
        }

        return null;
    }

    private static string TrimForPromptExcerpt(string? value, int maxLength)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var trimmed = value.Trim();
        return trimmed.Length <= maxLength ? trimmed : trimmed[..maxLength];
    }

    private static string BuildGoalRepairTimeoutFocus(ProjectIterationGoalSnapshot goal)
    {
        return goal.GoalIndex switch
        {
            1 => "Start Adventure 后显示 MapScene、玩家可见、稳定移动并触发首次遇敌。",
            2 => "创建独立 BattleScene 场景与脚本，完成敌人展示、攻击反馈以及胜利或失败结算；不要推进奖励选择。",
            3 => "胜利后显示 3 个奖励、选择任一奖励后状态变化可见、随后返回地图。",
            4 => "串联 Start Adventure、地图、遇敌、战斗、奖励选择和返回地图的首轮场景切换。",
            5 => "让 15 场胜利、任一失败和遇敌规则对玩家清晰可读。",
            6 => "完成 RPG 原型端到端验收、Godot smoke 和最终可玩证明。",
            _ => string.IsNullOrWhiteSpace(goal.AcceptanceHint) ? goal.Description : goal.AcceptanceHint
        };
    }

    private async Task<ProjectIterationSessionDetails?> ResolveGoalRepairSessionAsync(
        string projectId,
        PrototypeGoalRepairContext goalRepair,
        CancellationToken cancellationToken)
    {
        if (!string.IsNullOrWhiteSpace(goalRepair.SessionId))
        {
            foreach (var sourceKind in new string?[] { null, "repair_plan" })
            {
                var details = sourceKind is null
                    ? await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken)
                    : await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, sourceKind, cancellationToken);
                if (details is not null &&
                    string.Equals(details.Session.SessionId, goalRepair.SessionId, StringComparison.Ordinal))
                {
                    return details;
                }
            }
        }

        return await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
    }

    private async Task<string> ResolveBillingApiKeyNameAsync(string accountId, CancellationToken cancellationToken)
    {
        return await (_keyPoolService?.ResolveKeyNameForAccountAsync(accountId, cancellationToken) ?? Task.FromResult<string?>(null))
               ?? accountId;
    }

    private async Task<AiCodeMirrorRuntimeCredential> ResolveRuntimeCredentialAsync(string accountId, CancellationToken cancellationToken)
    {
        if (_keyPoolService is null)
        {
            return new AiCodeMirrorRuntimeCredential(accountId, null, null);
        }

        var credential = await _keyPoolService.ResolveRuntimeCredentialForAccountAsync(accountId, cancellationToken);
        return credential.BillingKeyName is null && credential.CodexHomePath is null
            ? new AiCodeMirrorRuntimeCredential(accountId, null, null)
            : credential;
    }

    private static string BuildSubmittedFeedback(
        ProjectSnapshot project,
        string runId,
        string feedback,
        string submittedAt,
        SkillActionDefinition? skillAction,
        ProjectIterationGoalSnapshot? goal)
    {
        return $"""
            # Prototype Quick Fix Submission

            Project: {project.Name}
            ProjectId: {project.ProjectId}
            RunId: {runId}
            SubmittedAtUtc: {submittedAt}
            SkillMode: {SkillModeLabel(skillAction)}
            GoalRepairMode: {(goal is null ? "false" : "true")}

            ## Feedback

            {feedback}
            
            {(goal is null ? "" : $"""
            ## Goal Context

            GoalIndex: {goal.GoalIndex}
            GoalTitle: {goal.Title}
            GoalDescription: {goal.Description}
            AcceptanceHint: {goal.AcceptanceHint}
            PreviousResultSummary: {BuildCompactGoalSummary(goal.ResultSummary)}
            """)}
            """;
    }

    private HostedProcessCommand BuildCodexCommand(string prompt, string outputPath, string model, string repositoryRoot)
    {
        return CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
            repositoryRoot,
            outputPath,
            prompt,
            model,
            ReasoningEffort));
    }

    private static string BuildCodexPrompt(
        ProjectSnapshot project,
        string runId,
        string feedback,
        SkillActionDefinition? skillAction,
        ProjectIterationGoalSnapshot? goal,
        ProjectRunMemorySnapshot? runMemory = null,
        PrototypeContractSnapshot? prototypeContract = null,
        GodotFailureDiagnostic? godotDiagnostic = null,
        GodotCacheCleanupResult? godotCleanup = null,
        PrototypeGoalAcceptanceValidationResult? currentAcceptanceValidation = null)
    {
        if (goal is not null)
        {
            return BuildGoalRepairPrompt(project, runId, feedback, goal, runMemory, prototypeContract, godotDiagnostic, godotCleanup, currentAcceptanceValidation);
        }

        var skillInstruction = skillAction is null
            ? "能力模式：普通模式。"
            : $"能力模式：{skillAction.Label}。执行时使用 ${skillAction.SkillName} 的方法。";
        var contractBlock = PrototypeContractService.BuildPromptBlock(prototypeContract ?? MissingPrototypeContract());
        var godotDiagnosticBlock = GodotFailureDiagnosticService.BuildPromptBlock(godotDiagnostic ?? GodotFailureDiagnostic.None(), godotCleanup);

        return $"""
            你正在执行积木云 Phase A 的快速修复任务。
            {PrototypeRouteSkillPolicy.BuildPromptBlock(project)}
            {contractBlock}
            {godotDiagnosticBlock}
            {skillInstruction}

            硬约束：
            - 这是一个 90 秒内完成的小修复，不要做大范围重构。
            - 仅处理明确、局部、低风险问题。
            - 优先修改少量文件，优先修接线、常量、菜单入口、状态显示、文本或小型前端逻辑。
            - 如果当前是 RPG 原型，Start Adventure 后必须让 MapScene 可见，并且必须保留 Grid，再满足以下两套可见验收标记之一：旧合同 `Title + StatusLabel`，或当前 HUD 合同 `HeaderLabel + StatsLabel + ObjectiveLabel`。
            - 如果当前是 RPG 原型，不要随意再造第三套近似命名；应复用上述两套合同之一，并保持节点命名与验收脚本一致。
            - 如果 Godot stderr 指向 `.tscn:1 - Parse Error: Expected '['`，检查对应场景文件是否以 UTF-8 BOM 开头；Godot 文本场景必须以 `[` 作为第一个字节级字符。
            - 如果 Godot stderr 指向 `Nodes with non-equal opposite anchors` 和 C# backtrace，修复 backtrace 中的脚本行，不要在 `_Ready()` 直接给非等锚点 Control 设置 `Size`。
            - 如果 Godot stderr 指向 `This control can't grab focus` 和 C# backtrace，修复 backtrace 中的脚本行：不要对不可聚焦的容器直接调用 `GrabFocus()`，或先配置合适的 focus mode。
            - Godot 运行验证只能使用仓库内已有的统一 smoke 入口；不要自行直接启动 Godot headless 长进程，不要自行指定 `user://logs` 日志路径。平台会在修复后独立执行统一 smoke 复验。
            - 如果问题超出小修范围，不要展开大工程，只输出简短结论，说明应改走正式反馈。
            - 输出必须面向浏览器用户，不要包含路径、命令、脚本名、日志名、环境变量。

            目标项目：
            - ProjectId: {project.ProjectId}
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}
            - QuickFixRunId: {runId}

            用户快速修复请求：
            {feedback}

            返回格式：
            1. 是否完成快速修复
            2. 改了什么
            3. 如何验证
            4. 如果未完成，说明为什么应改走正式反馈
            """;
    }

    private async Task<PrototypeGoalGodotSmokeValidationResult> ValidateProjectSmokeAfterQuickFixAsync(ProjectSnapshot project, CancellationToken cancellationToken)
    {
        if (!PrototypeRouteSkillPolicy.IsRpgProject(project))
        {
            return PrototypeGoalGodotSmokeValidationResult.NotRequired();
        }

        var prototypeState = new PrototypeRouteStateWriter().ReadLatestPrototypeState(project);
        var scenePath = ResolveSmokeScene(prototypeState);
        if (string.IsNullOrWhiteSpace(scenePath))
        {
            return PrototypeGoalGodotSmokeValidationResult.NotRequired();
        }

        var smoke = await PrototypeGodotSmokeService.RunAsync(_options, _processRunner, project.RepoPath, scenePath, cancellationToken);
        return PrototypeGoalGodotSmokeValidationResult.RequiredResult(smoke);
    }

    private static string? ResolveSmokeScene(string prototypeStateJson)
    {
        if (string.IsNullOrWhiteSpace(prototypeStateJson))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(prototypeStateJson);
            var root = document.RootElement;
            if (root.TryGetProperty("prototype_completion", out var completion) &&
                completion.ValueKind == JsonValueKind.Object &&
                completion.TryGetProperty("smoke_scene", out var completionScene) &&
                completionScene.ValueKind == JsonValueKind.String)
            {
                return completionScene.GetString();
            }

            if (root.TryGetProperty("godot_smoke", out var smoke) &&
                smoke.ValueKind == JsonValueKind.Object &&
                smoke.TryGetProperty("scene", out var scene) &&
                scene.ValueKind == JsonValueKind.String)
            {
                return scene.GetString();
            }
        }
        catch (JsonException)
        {
            return null;
        }

        return null;
    }

    private static PrototypeContractSnapshot MissingPrototypeContract()
    {
        return new PrototypeContractSnapshot("routes/prototype-contract/latest.json", "");
    }

    private static string BuildGoalRepairPrompt(
        ProjectSnapshot project,
        string runId,
        string feedback,
        ProjectIterationGoalSnapshot goal,
        ProjectRunMemorySnapshot? runMemory,
        PrototypeContractSnapshot? prototypeContract,
        GodotFailureDiagnostic? godotDiagnostic = null,
        GodotCacheCleanupResult? godotCleanup = null,
        PrototypeGoalAcceptanceValidationResult? currentAcceptanceValidation = null)
    {
        var memoryBlock = runMemory is null
            ? "暂无结构化运行记忆，直接按当前目标执行。"
            : $"""
            结构化运行记忆：
            - Status: {runMemory.Status}
            - CurrentObjective: {runMemory.CurrentObjective}
            - CompletedItemsJson: {runMemory.CompletedItemsJson}
            - CurrentBlockersJson: {runMemory.CurrentBlockersJson}
            - NextRecommendedAction: {runMemory.NextRecommendedAction}
            - AllowedScopeJson: {runMemory.AllowedScopeJson}
            - LastVerifiedResult: {runMemory.LastVerifiedResult}
            - LastRunOutcome: {runMemory.LastRunOutcome}
            """;
        var contractBlock = PrototypeContractService.BuildPromptBlock(prototypeContract ?? MissingPrototypeContract());
        var platformAcceptanceBlock = PrototypeGoalAcceptancePromptBuilder.Build(project, goal);
        var currentPlatformAcceptanceBlock = BuildCurrentPlatformAcceptanceBlock(currentAcceptanceValidation);
        var godotDiagnosticBlock = GodotFailureDiagnosticService.BuildPromptBlock(godotDiagnostic ?? GodotFailureDiagnostic.None(), godotCleanup);
        var rpgGdUnitContextBlock = BuildRpgGdUnitRepairContextBlock(project, goal);

        return $"""
            你正在执行积木云 Phase A 的单目标迭代修复任务。

            {PrototypeRouteSkillPolicy.BuildPromptBlock(project)}
            {contractBlock}
            {godotDiagnosticBlock}
            {rpgGdUnitContextBlock}
            Mandatory rules:
            - Do not define or shadow xUnit types. Never add `namespace Xunit`, `FactAttribute`, `TheoryAttribute`, `InlineDataAttribute`, or `Assert` classes in project tests. Use the existing `using Xunit;` and package references.
            - 这次只处理当前目标，不要顺手扩展到后续目标。
            - 这是目标级 needs-fix 修复，不是 90 秒快速修复；允许为了完成当前 step 做必要的局部实现，但仍禁止扩大到后续目标。
            - 直接围绕当前目标实现，不要先做任务恢复、仓库导览、规则总结或工作流巡检。
            - 不要读取或总结 AGENTS.md、decision-logs、execution-plans、active-task、session recovery 一类文件。
            - 不要修改 PhaseA.Platform/**、PhaseA.Platform.Tests/**、scripts/**、docs/** 这些云端控制台与工具链文件。
            - 如果当前目标是 RPG 原型修复，默认只允许修改 Game.Godot/Prototypes/dq-rpg/**、Game.Core/Prototypes/**、Game.Core.Tests/Prototypes/**、Tests.Godot/tests/Prototype/** 这些与原型直接相关的位置。
            - Godot C# 项目结构：可构建项目是仓库根目录的 GodotGame.csproj；Game.Godot/ 只是运行时场景和脚本目录，不是独立 C# 项目。不要执行或引用 Game.Godot/Game.Godot.csproj。
            - 不要在本路由中执行 dotnet build、dotnet test、Godot prewarm 或 GdUnit；这些本地验证命令会写入 obj/bin/.godot 并可能触发文件锁。修复完成后由平台统一执行隔离验收。
            - 仅当 Godot stderr 明确指出 `Game.Godot/Examples/**.tscn:1 - Parse Error: Expected '['` 时，允许把被点名的示例场景重写为无 UTF-8 BOM 的 Godot 文本场景；不要借机改示例内容。
            - 结构化运行记忆和历史摘要只用于理解上次到哪里了，不是本轮修复目标。
            - 不要把“路由状态、恢复逻辑、平台测试、文档整理、脚本调整”当作当前目标的完成内容，除非当前目标标题和验收提示明确要求。
            - 如果当前目标是玩法/Godot/RPG 目标，完成标准必须来自 Title、Description、AcceptanceHint 中的玩法验收。
            - Main.tscn SOP：原型相关修复必须保持根级 VBox、Overlays、ScreenRoot 默认 visible = false；final/full-playable 目标必须修到这一点通过。
            - Godot stderr 属于当前目标验收信号：`.tscn:1 - Parse Error: Expected '['` 必须修到对应场景文件首字符就是 `[`；`Nodes with non-equal opposite anchors` 必须修到 backtrace 指向的脚本不再触发该 warning。
            - `This control can't grab focus` 也属于当前目标验收信号：必须移除对不可聚焦容器的 `GrabFocus()`，或先配置正确 focus mode。
            - Godot 运行验证只能使用仓库内已有的统一 smoke 入口；不要自行直接启动 Godot headless 长进程，不要自行指定 `user://logs` 日志路径。平台会在修复后独立执行统一 smoke 复验。
            - 不要自行运行 dotnet build、dotnet test、Godot prewarm 或 GdUnit；这些验证由平台在隔离输出目录中执行。
            - 对玩法/Godot/RPG 目标，只有实际修复并验证对应玩法验收，才能输出 STATUS: completed。
            - 不要处理测试宿主、权限、构建系统、平台链路之类的基础设施问题，除非它们是阻塞当前目标的唯一剩余问题。
            - 优先用最小改动完成目标。
            - 如果被阻塞，直接报告阻塞原因，不要改无关基础设施。
            - 完成后输出面向浏览器用户的简明结果，不要包含路径、命令、脚本名、日志名、环境变量。

            项目：
            - ProjectId: {project.ProjectId}
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}
            - GoalRepairRunId: {runId}

            当前唯一目标：
            - GoalIndex: {goal.GoalIndex}
            - Title: {goal.Title}
            - Description: {goal.Description}
            - AcceptanceHint: {goal.AcceptanceHint}
            - PreviousResultSummary: {BuildCompactGoalSummary(goal.ResultSummary)}

            {platformAcceptanceBlock}

            {currentPlatformAcceptanceBlock}

            用户触发这次修复时附带的说明：
            {feedback}

            {memoryBlock}

            当前运行环境已经切到一个只包含原型白名单目录的聚焦工作区。
            你不需要也不应该做仓库恢复、全仓巡检、部署修复或文档整理。

            成功定义：
            - 只有当当前 step 已可继续，才可视为修复成功。
            - “已可继续”必须指当前目标的玩法/业务验收通过，不是平台路由或恢复语义通过。
            - 对奖励闭环目标，最小完成范围是：胜利后出现 3 个奖励、选择任一奖励后状态变化可见、随后返回地图。
            - 如果仍未可继续，必须明确写出“当前 step 仍需修复”以及唯一剩余阻塞。
            - 不要切换去处理 step {goal.GoalIndex + 1} 或任何后续目标。

            输出格式：
            STATUS: completed|needs_fix
            SUMMARY: 用 2-4 句说明当前目标是否完成，以及对用户有什么变化
            CHANGED: 用 1-3 行列出本轮实际完成的改动
            VERIFY: 用 1-3 行说明如何验证
            REMAINING: 若未完全完成，写出剩余问题；若已完成，写 none
            """;
    }

    private static string BuildRpgGdUnitRepairContextBlock(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        if (!PrototypeRouteSkillPolicy.IsRpgProject(project) ||
            !RequiresRpgGdUnitValidation(project, goal))
        {
            return "";
        }

        var reportRoot = Path.Combine(project.RepoPath, "logs", "e2e");
        if (!Directory.Exists(reportRoot))
        {
            return """
                Latest RPG GdUnit validation context:
                - No logs/e2e RPG GdUnit report directory was found yet.
                """;
        }

        var summaryPath = Directory
            .EnumerateFiles(reportRoot, "run-summary.json", SearchOption.AllDirectories)
            .Where(path => path.Contains("gdunit", StringComparison.OrdinalIgnoreCase))
            .Select(path => new FileInfo(path))
            .OrderByDescending(file => file.LastWriteTimeUtc)
            .FirstOrDefault();
        var reportDir = summaryPath?.Directory;
        var consolePath = reportDir is null
            ? null
            : Path.Combine(reportDir.FullName, "gdunit-console.txt");

        var lines = new List<string>
        {
            "Latest RPG GdUnit validation context:",
            "- This is the authoritative current blocker for RPG GdUnit/final repair goals; do not infer stale resource-link blockers when this context says tests executed."
        };

        if (summaryPath is not null)
        {
            lines.Add($"- run_summary: {TrimForPromptExcerpt(File.ReadAllText(summaryPath.FullName, Encoding.UTF8), 1200)}");
        }

        if (!string.IsNullOrWhiteSpace(consolePath) && File.Exists(consolePath))
        {
            lines.Add("- gdunit_console_failure_summary:");
            foreach (var line in ExtractGdUnitPromptSummary(File.ReadAllText(consolePath, Encoding.UTF8), 60))
            {
                lines.Add($"  {line}");
            }
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static IReadOnlyList<string> ExtractGdUnitPromptSummary(string consoleText, int maxLines)
    {
        if (string.IsNullOrWhiteSpace(consoleText))
        {
            return [];
        }

        var cleaned = AnsiEscapeRegex().Replace(consoleText, "");
        var result = new List<string>();
        var captureFailure = false;
        foreach (var rawLine in cleaned.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries))
        {
            var line = rawLine.Trim();
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            var isImportant = ContainsAny(
                line,
                "Statistics:",
                "Overall Summary:",
                "Exit code:",
                "ERROR:",
                "SCRIPT ERROR",
                "Node not found",
                "Parse Error",
                "Invalid call",
                "No test cases found",
                "FAILED",
                "Expecting:",
                "do contains");
            if (line.StartsWith("res://tests/Prototype/DqRpgPrototype/", StringComparison.OrdinalIgnoreCase))
            {
                isImportant = true;
                captureFailure = line.Contains("FAILED", StringComparison.OrdinalIgnoreCase);
            }
            else if (line.StartsWith("Report:", StringComparison.OrdinalIgnoreCase))
            {
                isImportant = true;
                captureFailure = true;
            }
            else if (captureFailure && (line.StartsWith("'", StringComparison.Ordinal) || line.Contains(" but is ", StringComparison.OrdinalIgnoreCase)))
            {
                isImportant = true;
            }

            if (!isImportant)
            {
                continue;
            }

            AddDistinctPromptLine(result, TrimForPromptExcerpt(line, 500));
            if (result.Count >= maxLines)
            {
                break;
            }
        }

        return result;
    }

    private static void AddDistinctPromptLine(List<string> lines, string line)
    {
        if (!string.IsNullOrWhiteSpace(line) &&
            !lines.Any(existing => string.Equals(existing, line, StringComparison.OrdinalIgnoreCase)))
        {
            lines.Add(line);
        }
    }

    private static bool ContainsAny(string text, params string[] needles)
    {
        return needles.Any(needle => text.Contains(needle, StringComparison.OrdinalIgnoreCase));
    }

    [GeneratedRegex(@"\x1B\[[0-?]*[ -/]*[@-~]", RegexOptions.Compiled)]
    private static partial Regex AnsiEscapeRegex();

    private static string BuildCurrentPlatformAcceptanceBlock(PrototypeGoalAcceptanceValidationResult? validation)
    {
        if (validation is null || string.Equals(validation.Status, "not_run", StringComparison.Ordinal))
        {
            return """
                Current platform acceptance diagnosis before repair:
                - Status: not_run
                - Reason: no target-specific acceptance contract was available before repair.
                """;
        }

        return $"""
            Current platform acceptance diagnosis before repair:
            - Kind: {validation.Kind}
            - Status: {validation.Status}
            - Reason: {validation.Reason ?? validation.Status}
            - Details: {validation.Details ?? "none"}
            - If Status is failed, repair the listed reason items before reporting STATUS: completed.
            """;
    }

    private static bool RequiresHardPlatformAcceptance(
        ProjectIterationGoalSnapshot goal,
        PrototypeGoalAcceptanceValidationResult acceptanceValidation)
    {
        return string.Equals(acceptanceValidation.Status, "failed", StringComparison.Ordinal) &&
               goal.GoalIndex is >= 1 and <= 6 &&
               acceptanceValidation.Kind.StartsWith("rpg-", StringComparison.Ordinal);
    }

    private static string BuildAssistantMessage(string publicCodexReport, ProjectIterationGoalSnapshot? goal)
    {
        return $"""
            {(goal is null ? "快速修复已完成。" : $"目标 {goal.GoalIndex} 修复已执行。")}
            完成报告：
            {publicCodexReport}
            """;
    }

    private static string BuildPublicCodexReport(HostedProcessResult codexResult, string codexOutput)
    {
        var result = !string.IsNullOrWhiteSpace(codexOutput)
            ? codexOutput.Trim()
            : FirstNonEmpty(codexResult.Stdout, codexResult.Stderr, "Quick fix did not return a final message.");
        var publicResult = PublicChatSanitizer.Sanitize(result);
        if (string.IsNullOrWhiteSpace(publicResult))
        {
            return "快速修复已执行，但没有可展示的公开摘要。";
        }

        return publicResult;
    }

    private static string BuildResultLog(
        ProjectSnapshot project,
        string runId,
        string feedback,
        string assistantMessage,
        string model,
        HostedProcessResult codexResult,
        string codexOutput,
        string completedAt,
        SkillActionDefinition? skillAction,
        ProjectIterationGoalSnapshot? goal,
        GoalRepairOutcome? goalRepairOutcome)
    {
        return $"""
            # Prototype Quick Fix Result

            Project: {project.Name}
            ProjectId: {project.ProjectId}
            RunId: {runId}
            Model: {model}
            SkillMode: {SkillModeLabel(skillAction)}
            CodexExitCode: {codexResult.ExitCode}
            CompletedAtUtc: {completedAt}
            GoalRepairMode: {(goal is null ? "false" : "true")}
            GoalRepairStatus: {goalRepairOutcome?.GoalStatus}

            ## Submitted Feedback

            {feedback}

            {(goal is null ? "" : $"""
            ## Goal Context

            GoalIndex: {goal.GoalIndex}
            GoalTitle: {goal.Title}
            GoalDescription: {goal.Description}
            AcceptanceHint: {goal.AcceptanceHint}
            PreviousResultSummary: {BuildCompactGoalSummary(goal.ResultSummary)}
            """)}

            ## Result

            {assistantMessage}

            ## Codex Stdout

            {codexResult.Stdout}

            ## Codex Stderr

            {codexResult.Stderr}

            ## Codex Output

            {codexOutput}
            """;
    }

    private static string SkillModeLabel(SkillActionDefinition? skillAction)
    {
        return skillAction is null ? "普通模式" : $"{skillAction.Label} (${skillAction.SkillName})";
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value.Length > 6000 ? value[^6000..] : value;
            }
        }

        return "";
    }

    private static string BuildCompactGoalSummary(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var lines = value
            .Replace("\r\n", "\n", StringComparison.Ordinal)
            .Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(line => !line.StartsWith("Project README:", StringComparison.OrdinalIgnoreCase))
            .Where(line => !line.StartsWith("Recovery source consumed:", StringComparison.OrdinalIgnoreCase))
            .Where(line => !line.StartsWith("Direction lock:", StringComparison.OrdinalIgnoreCase))
            .Where(line => !line.StartsWith("{", StringComparison.Ordinal))
            .Where(line => !line.StartsWith("\"", StringComparison.Ordinal))
            .Take(6);
        var summary = string.Join(" ", lines);
        return summary.Length <= 1000 ? summary : summary[..1000];
    }

    private static string ToSlash(string path)
    {
        return path.Replace('\\', '/');
    }

    private async Task<AcceptanceValidationResult> RunGoalAcceptanceValidationAsync(
        ProjectSnapshot project,
        ProjectIterationGoalSnapshot goal,
        CancellationToken cancellationToken)
    {
        if (!IsRpgFirstEncounterGoal(project, goal))
        {
            return AcceptanceValidationResult.NotRun();
        }

        var testProject = Path.Combine(project.RepoPath, "Game.Core.Tests", "Game.Core.Tests.csproj");
        if (!File.Exists(testProject))
        {
            return AcceptanceValidationResult.Failed("rpg-step1-core-tests");
        }

        using var timeout = new CancellationTokenSource(TimeSpan.FromMinutes(2));
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(timeout.Token, cancellationToken);
        try
        {
            var result = await _processRunner.RunAsync(
                new HostedProcessCommand(
                    "dotnet",
                    [
                        "test",
                        testProject,
                        "--filter",
                        "FullyQualifiedName~DqRpgPrototypeLoopTests"
                    ],
                    project.RepoPath,
                    new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)),
                linked.Token);
            return result.ExitCode == 0
                ? AcceptanceValidationResult.Pass("rpg-step1-core-tests")
                : AcceptanceValidationResult.Failed("rpg-step1-core-tests");
        }
        catch (OperationCanceledException)
        {
            return AcceptanceValidationResult.Failed("rpg-step1-core-tests");
        }
    }

    private static bool IsRpgFirstEncounterGoal(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        var projectType = string.Join(" ", project.GameTypeSource, project.TemplateRuleId).ToLowerInvariant();
        if (!projectType.Contains("rpg", StringComparison.Ordinal))
        {
            return false;
        }

        var goalText = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint).ToLowerInvariant();
        return goal.GoalIndex == 1 &&
               (goalText.Contains("encounter", StringComparison.Ordinal) ||
                goalText.Contains("battle", StringComparison.Ordinal) ||
                goalText.Contains("enemy", StringComparison.Ordinal) ||
                goalText.Contains("遇敌", StringComparison.Ordinal) ||
                goalText.Contains("遭遇", StringComparison.Ordinal));
    }

    private static string AppendAcceptanceValidationSummary(string assistantMessage, ProjectIterationGoalSnapshot goal)
    {
        return $"""
            {assistantMessage.Trim()}

            平台验收：
            目标 {goal.GoalIndex} 的最小玩法验收已通过。当前目标可以进入下一步。
            """;
    }

    private static string AppendAcceptanceValidationEvidence(string codexOutput)
    {
        var prefix = string.IsNullOrWhiteSpace(codexOutput) ? "" : codexOutput.Trim() + Environment.NewLine + Environment.NewLine;
        return prefix + """
            STATUS: completed
            VERIFY: Platform acceptance validation passed for the current gameplay goal.
            REMAINING: none
            """;
    }

    private static string AppendAcceptanceValidationFailure(
        string assistantMessage,
        ProjectIterationGoalSnapshot goal,
        PrototypeGoalAcceptanceValidationResult validation)
    {
        return $"""
            {assistantMessage.Trim()}

            平台验收：
            目标 {goal.GoalIndex} 没有通过平台验收，当前目标仍保持 needs_fix。
            原因：{validation.Reason ?? validation.Status}
            细节：{validation.Details ?? "none"}
            """;
    }

    private static string AppendAcceptanceValidationFailureEvidence(
        string codexOutput,
        PrototypeGoalAcceptanceValidationResult validation)
    {
        var prefix = string.IsNullOrWhiteSpace(codexOutput) ? "" : codexOutput.Trim() + Environment.NewLine + Environment.NewLine;
        return $"""
            {prefix}STATUS: needs_fix
            VERIFY: Platform acceptance validation failed for the current gameplay goal.
            REASON: {validation.Reason ?? validation.Status}
            DETAILS: {validation.Details ?? "none"}
            """;
    }

    private static string AppendMutationGuardFailure(
        string assistantMessage,
        PrototypeRepairMutationGuardResult validation)
    {
        return $"""
            {assistantMessage.Trim()}

            Platform mutation guard:
            STATUS: needs_fix
            VERIFY: Prototype repair must not define or shadow test framework types.
            REMAINING: Remove the local xUnit shim/shadow definitions and use the existing xUnit package references.
            REASON: {validation.Reason ?? validation.Status}
            DETAILS: {BuildMutationGuardDetails(validation)}
            """;
    }

    private static string AppendMutationGuardFailureEvidence(
        string codexOutput,
        PrototypeRepairMutationGuardResult validation)
    {
        var prefix = string.IsNullOrWhiteSpace(codexOutput) ? "" : codexOutput.Trim() + Environment.NewLine + Environment.NewLine;
        return $"""
            {prefix}STATUS: needs_fix
            VERIFY: Prototype mutation guard failed.
            REASON: {validation.Reason ?? validation.Status}
            DETAILS: {BuildMutationGuardDetails(validation)}
            """;
    }

    private static string BuildMutationGuardDetails(PrototypeRepairMutationGuardResult validation)
    {
        if (validation.Violations.Count == 0)
        {
            return "none";
        }

        return string.Join("; ", validation.Violations.Select(violation => $"{violation.Path}:{violation.Line}:{violation.Rule}"));
    }

    private static string AppendGodotSmokeValidationSummary(
        string assistantMessage,
        ProjectIterationGoalSnapshot goal,
        PrototypeGoalGodotSmokeValidationResult validation)
    {
        return $"""
            {assistantMessage.Trim()}

            Platform engine validation:
            Goal {goal.GoalIndex} passed Godot smoke validation.
            """;
    }

    private static string BuildValidatedGoalRepairSummary(ProjectIterationGoalSnapshot goal)
    {
        return $"""
            目标 {goal.GoalIndex} 修复已完成。

            平台验收：
            目标 {goal.GoalIndex} 的最小玩法验收已通过。

            Platform engine validation:
            Goal {goal.GoalIndex} passed Godot smoke validation.
            当前目标可以进入下一步。
            """;
    }

    private static string AppendGodotSmokeValidationFailure(
        string assistantMessage,
        PrototypeGoalGodotSmokeValidationResult validation)
    {
        return $"""
            {assistantMessage.Trim()}

            Platform engine validation:
            STATUS: needs_fix
            VERIFY: Godot smoke validation did not pass.
            REMAINING: Run and pass Godot smoke validation for the current gameplay goal.
            REASON: {validation.Smoke.Reason}
            """;
    }

    private static string AppendGodotSmokeValidationEvidence(string codexOutput)
    {
        var prefix = string.IsNullOrWhiteSpace(codexOutput) ? "" : codexOutput.Trim() + Environment.NewLine + Environment.NewLine;
        return prefix + """
            VERIFY: Godot smoke validation passed for the current gameplay goal.
            REMAINING: none
            """;
    }

    private static string AppendRpgGdUnitValidationFailure(
        ProjectSnapshot project,
        string assistantMessage,
        PrototypeRpgGdUnitValidationResult validation)
    {
        var summary = BuildRpgGdUnitFailureSummaryForUser(project, validation);
        return $"""
            RPG GdUnit validation:
            STATUS: needs_fix
            VERIFY: Project-specific RPG GdUnit validation did not pass.
            REMAINING: Continue repairing the current final validation step until the RPG GdUnit suite passes.
            REASON: {validation.Reason}
            {summary}
            """;
    }

    private static string AppendRpgGdUnitValidationFailureEvidence(
        ProjectSnapshot project,
        string codexOutput,
        PrototypeRpgGdUnitValidationResult validation)
    {
        var prefix = string.IsNullOrWhiteSpace(codexOutput) ? "" : codexOutput.Trim() + Environment.NewLine + Environment.NewLine;
        var summary = BuildRpgGdUnitFailureSummaryForUser(project, validation);
        return $"""
            {prefix}STATUS: needs_fix
            VERIFY: Project-specific RPG GdUnit validation failed.
            REASON: {validation.Reason}
            {summary}
            """;
    }

    private static string BuildRpgGdUnitFailureSummaryForUser(ProjectSnapshot project, PrototypeRpgGdUnitValidationResult validation)
    {
        if (!validation.Required || validation.Passed)
        {
            return "";
        }

        var summaryPath = ResolveRpgGdUnitReportFile(project.RepoPath, validation.ReportDir, "run-summary.json");
        var consolePath = ResolveRpgGdUnitReportFile(project.RepoPath, validation.ReportDir, "gdunit-console.txt");
        var lines = new List<string>();
        if (!string.IsNullOrWhiteSpace(summaryPath) && File.Exists(summaryPath))
        {
            lines.Add($"GDUNIT_SUMMARY: {TrimForPromptExcerpt(File.ReadAllText(summaryPath, Encoding.UTF8), 700)}");
        }

        if (!string.IsNullOrWhiteSpace(consolePath) && File.Exists(consolePath))
        {
            var failures = ExtractGdUnitPromptSummary(File.ReadAllText(consolePath, Encoding.UTF8), 16);
            if (failures.Count > 0)
            {
                lines.Add("GDUNIT_FAILURES:");
                lines.AddRange(failures.Select(line => $"- {line}"));
            }
        }

        return lines.Count == 0 ? "" : string.Join(Environment.NewLine, lines);
    }

    private static string? ResolveRpgGdUnitReportFile(string repoPath, string? reportDir, string fileName)
    {
        if (string.IsNullOrWhiteSpace(reportDir) || Path.IsPathRooted(reportDir))
        {
            return null;
        }

        var fullPath = Path.GetFullPath(Path.Combine(repoPath, reportDir.Replace('/', Path.DirectorySeparatorChar), fileName));
        var repoRoot = Path.GetFullPath(repoPath);
        return fullPath.StartsWith(repoRoot, StringComparison.OrdinalIgnoreCase) ? fullPath : null;
    }

    private static string AppendProjectSmokeValidationSummary(string assistantMessage)
    {
        return $"""
            {assistantMessage.Trim()}

            平台验收：
            快速修复后的原型入口与引擎验收已通过。
            """;
    }

    private static string AppendProjectSmokeValidationFailure(
        string assistantMessage,
        PrototypeGoalGodotSmokeValidationResult validation)
    {
        return $"""
            {assistantMessage.Trim()}

            平台验收：
            STATUS: needs_fix
            VERIFY: 快速修复后的原型入口或引擎验收未通过。
            REMAINING: 继续修复当前原型，直到主菜单进入原型和 Start Adventure 后地图可见验收通过。
            REASON: {validation.Smoke.Reason}
            """;
    }

    private static GoalRepairOutcome DetermineGoalRepairOutcome(
        ProjectIterationGoalSnapshot goal,
        string assistantMessage,
        HostedProcessResult codexResult,
        string codexOutput)
    {
        var combined = string.Join("\n", new[] { codexOutput, codexResult.Stdout, codexResult.Stderr }.Where(static value => !string.IsNullOrWhiteSpace(value)));
        var normalized = combined.ToLowerInvariant();
        var structuredStatus = ParseStructuredStatus(codexOutput)
            ?? ParseStructuredStatus(codexResult.Stdout)
            ?? ParseStructuredStatus(codexResult.Stderr);
        if (string.Equals(structuredStatus, "needs_fix", StringComparison.OrdinalIgnoreCase))
        {
            return new GoalRepairOutcome("needs_fix", false);
        }

        var fixSignals = new[]
        {
            "仍需修复",
            "needs fix",
            "need fix",
            "无法继续",
            "remaining blocker",
            "blocked",
            "未完成",
            "not ready",
            "not complete"
        };
        var successSignals = new[]
        {
            "已可继续",
            "可以继续",
            "current step is ready",
            "step is ready",
            "目标已修复",
            "修复完成",
            "ready to continue"
        };
        var goalKeywords = BuildGoalKeywords(goal);
        var goalMatched = goalKeywords.Count == 0 || goalKeywords.Any(normalized.Contains);
        var offTopicSignals = new[]
        {
            "caddy",
            "token",
            "hash",
            "deployment",
            "deploy",
            "start-phasea",
            "phasea.platform",
            "docs/workflows",
            "security test",
            "文档",
            "部署",
            "脚本",
            "安全测试"
        };
        var offTopicMatched = offTopicSignals.Any(normalized.Contains) && !GoalAllowsInfraTerms(goal);
        if (string.Equals(structuredStatus, "completed", StringComparison.OrdinalIgnoreCase))
        {
            return offTopicMatched || HasBlockingEvidence(codexOutput.ToLowerInvariant()) || !HasCompletionEvidence(codexOutput)
                ? new GoalRepairOutcome("needs_fix", false)
                : new GoalRepairOutcome("succeeded", true);
        }

        if (successSignals.Any(normalized.Contains) && !fixSignals.Any(normalized.Contains) && goalMatched)
        {
            if (offTopicMatched)
            {
                return new GoalRepairOutcome("needs_fix", false);
            }
            return new GoalRepairOutcome("succeeded", true);
        }

        if (!goalMatched)
        {
            return new GoalRepairOutcome("needs_fix", false);
        }

        if (offTopicMatched)
        {
            return new GoalRepairOutcome("needs_fix", false);
        }

        if (fixSignals.Any(normalized.Contains) || codexResult.ExitCode != 0)
        {
            return new GoalRepairOutcome("needs_fix", false);
        }

        if ((normalized.Contains($"目标 {goal.GoalIndex} 已") || normalized.Contains($"step {goal.GoalIndex}") && normalized.Contains("完成")) && goalMatched)
        {
            return new GoalRepairOutcome("succeeded", true);
        }

        return new GoalRepairOutcome("needs_fix", false);
    }

    public static bool HasGoalRepairCompletionEvidenceForTesting(params string?[] values)
    {
        return HasCompletionEvidence(values);
    }

    public static bool HasGoalRepairBlockingEvidenceForTesting(string normalizedText)
    {
        return HasBlockingEvidence(normalizedText.ToLowerInvariant());
    }

    private static bool HasBlockingEvidence(string normalizedText)
    {
        var blockingMarkers = new[]
        {
            "还没有做",
            "没有做",
            "未做",
            "未完成",
            "没有完成",
            "未验证",
            "没有验证",
            "业务验收",
            "仍需修复",
            "需要修复",
            "无法验证",
            "验证未通过",
            "验证失败",
            "测试失败",
            "not run",
            "not verified",
            "not completed",
            "not complete",
            "still incomplete",
            "could not verify",
            "unable to verify",
            "verification failed",
            "validation failed",
            "test failed",
            "tests failed",
            "blocked by",
            "remaining blocker",
            "permission denied",
            "access denied"
        };

        return blockingMarkers.Any(marker => normalizedText.Contains(marker, StringComparison.Ordinal));
    }

    private static bool HasCompletionEvidence(params string?[] values)
    {
        var text = string.Join("\n", values.Where(value => !string.IsNullOrWhiteSpace(value)));
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        var normalizedText = text.ToLowerInvariant();
        if (!normalizedText.Contains("verify:", StringComparison.Ordinal) ||
            !normalizedText.Contains("remaining: none", StringComparison.Ordinal))
        {
            return false;
        }

        var verify = ExtractStructuredField(text, "VERIFY");
        if (string.IsNullOrWhiteSpace(verify))
        {
            return false;
        }

        var remaining = ExtractStructuredField(text, "REMAINING");
        if (!string.Equals(remaining?.Trim(), "none", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        var normalizedVerify = verify.Trim().ToLowerInvariant();
        var strongVerifyMarkers = new[]
        {
            "pass",
            "passed",
            "green",
            "all green",
            "通过"
        };
        var hasStrongEvidence = strongVerifyMarkers.Any(marker => normalizedVerify.Contains(marker, StringComparison.Ordinal));
        return hasStrongEvidence && !HasBlockingEvidence(normalizedVerify);
    }

    private static string? ExtractStructuredField(string text, string fieldName)
    {
        var lines = text.Split(['\r', '\n'], StringSplitOptions.None);
        var prefix = fieldName + ":";
        for (var index = 0; index < lines.Length; index++)
        {
            var line = lines[index];
            if (!line.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var parts = new List<string> { line[prefix.Length..].Trim() };
            for (var next = index + 1; next < lines.Length; next++)
            {
                var nextLine = lines[next];
                if (nextLine.Contains(':', StringComparison.Ordinal) &&
                    nextLine.Split(':', 2)[0].All(static c => char.IsLetter(c) || c == '_'))
                {
                    break;
                }

                parts.Add(nextLine.Trim());
            }

            return string.Join(" ", parts.Where(static part => !string.IsNullOrWhiteSpace(part))).Trim();
        }

        return null;
    }

    private static string? ParseStructuredStatus(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        foreach (var rawLine in value.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (!rawLine.StartsWith("STATUS:", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var status = rawLine["STATUS:".Length..].Trim().ToLowerInvariant();
            if (status is "completed" or "needs_fix")
            {
                return status;
            }
        }

        return null;
    }

    private static List<string> BuildGoalKeywords(ProjectIterationGoalSnapshot goal)
    {
        var combined = string.Join(" ", new[] { goal.Title, goal.Description, goal.AcceptanceHint }.Where(static value => !string.IsNullOrWhiteSpace(value))).ToLowerInvariant();
        var keywords = new List<string>();

        void Add(params string[] values)
        {
            foreach (var value in values)
            {
                if (!keywords.Contains(value, StringComparer.Ordinal))
                {
                    keywords.Add(value);
                }
            }
        }

        if (combined.Contains("移动"))
        {
            Add("移动", "move", "movement", "player");
        }

        if (combined.Contains("遇敌"))
        {
            Add("遇敌", "encounter", "battle", "enemy");
        }

        if (combined.Contains("地图"))
        {
            Add("地图", "map", "scene");
        }

        if (combined.Contains("rpg"))
        {
            Add("rpg", "prototype");
        }

        return keywords;
    }

    private static bool GoalAllowsInfraTerms(ProjectIterationGoalSnapshot goal)
    {
        var combined = string.Join(" ", new[] { goal.Title, goal.Description, goal.AcceptanceHint }.Where(static value => !string.IsNullOrWhiteSpace(value))).ToLowerInvariant();
        return combined.Contains("部署") ||
               combined.Contains("文档") ||
               combined.Contains("脚本") ||
               combined.Contains("token") ||
               combined.Contains("caddy") ||
               combined.Contains("安全");
    }

    private async Task UpsertGoalRunMemoryAsync(
        string projectId,
        ProjectIterationGoalSnapshot goal,
        string status,
        string nextRecommendedAction,
        string lastRunOutcome,
        IReadOnlyList<string> blockers,
        CancellationToken cancellationToken)
    {
        var completed = status == "succeeded"
            ? JsonSerializer.Serialize(new[] { goal.Title })
            : "[]";
        var blockersJson = JsonSerializer.Serialize(blockers);
        var allowedScopeJson = JsonSerializer.Serialize(FocusedWorkspaceDirectories);
        await _metadataStore.UpsertProjectRunMemoryAsync(
            projectId,
            BuildGoalMemoryScope(goal.GoalIndex),
            status,
            goal.Description,
            completed,
            blockersJson,
            nextRecommendedAction,
            allowedScopeJson,
            goal.AcceptanceHint,
            lastRunOutcome,
            cancellationToken);
    }

    private static string BuildGoalMemoryScope(int goalIndex)
    {
        return $"goal-repair-step-{goalIndex}";
    }

    private static ExecutionWorkspace PrepareExecutionWorkspace(ProjectSnapshot project, ProjectIterationGoalSnapshot? goal, string runId, string fallbackCodexOutputPath)
    {
        if (!ShouldUseFocusedWorkspace(project, goal))
        {
            return new ExecutionWorkspace(project.RepoPath, CreateShortRuntimeOutputPath(runId), false, []);
        }

        var focusedRoot = Path.Combine(Path.GetTempPath(), "phasea-focused-workspaces", runId);
        if (Directory.Exists(focusedRoot))
        {
            Directory.Delete(focusedRoot, recursive: true);
        }

        Directory.CreateDirectory(focusedRoot);
        foreach (var relativeFile in FocusedWorkspaceRootFiles)
        {
            CopyRelativeFileIfExists(project.RepoPath, focusedRoot, relativeFile);
        }

        foreach (var relativeDirectory in FocusedWorkspaceDirectories)
        {
            CopyRelativeDirectoryIfExists(project.RepoPath, focusedRoot, relativeDirectory);
        }

        var codexOutputPath = Path.Combine(focusedRoot, ".phasea", "codex-output.txt");
        Directory.CreateDirectory(Path.GetDirectoryName(codexOutputPath)!);
        return new ExecutionWorkspace(focusedRoot, codexOutputPath, true, FocusedWorkspaceDirectories.Concat(FocusedWorkspaceRootFiles).ToArray());
    }

    private static string CreateShortRuntimeOutputPath(string runId)
    {
        var root = Path.Combine(Path.GetTempPath(), "phasea-codex-out", runId);
        Directory.CreateDirectory(root);
        return Path.Combine(root, "codex-output.txt");
    }

    private static bool ShouldUseFocusedWorkspace(ProjectSnapshot project, ProjectIterationGoalSnapshot? goal)
    {
        return goal is not null &&
               project.GameTypeSource.Contains("rpg", StringComparison.OrdinalIgnoreCase);
    }

    private static void SyncFocusedWorkspaceBack(ExecutionWorkspace workspace, string projectRepoPath)
    {
        foreach (var relativePath in workspace.ManagedPaths)
        {
            var sourcePath = Path.Combine(workspace.RootPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
            var targetPath = Path.Combine(projectRepoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
            if (Directory.Exists(sourcePath))
            {
                CopyDirectoryContents(sourcePath, targetPath);
                continue;
            }

            if (File.Exists(sourcePath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(targetPath)!);
                File.Copy(sourcePath, targetPath, overwrite: true);
            }
        }
    }

    private static void CopyRelativeFileIfExists(string sourceRoot, string targetRoot, string relativePath)
    {
        var sourcePath = Path.Combine(sourceRoot, relativePath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(sourcePath))
        {
            return;
        }

        var targetPath = Path.Combine(targetRoot, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(targetPath)!);
        File.Copy(sourcePath, targetPath, overwrite: true);
    }

    private static void CopyRelativeDirectoryIfExists(string sourceRoot, string targetRoot, string relativePath)
    {
        var sourcePath = Path.Combine(sourceRoot, relativePath.Replace('/', Path.DirectorySeparatorChar));
        if (!Directory.Exists(sourcePath))
        {
            return;
        }

        var targetPath = Path.Combine(targetRoot, relativePath.Replace('/', Path.DirectorySeparatorChar));
        CopyDirectoryContents(sourcePath, targetPath);
    }

    private static void CopyDirectoryContents(string sourceDirectory, string targetDirectory)
    {
        Directory.CreateDirectory(targetDirectory);
        foreach (var directory in Directory.EnumerateDirectories(sourceDirectory, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(sourceDirectory, directory);
            Directory.CreateDirectory(Path.Combine(targetDirectory, relative));
        }

        foreach (var file in Directory.EnumerateFiles(sourceDirectory, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(sourceDirectory, file);
            var destination = Path.Combine(targetDirectory, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            File.Copy(file, destination, overwrite: true);
        }
    }

    private static readonly string[] FocusedWorkspaceDirectories =
    [
        "Game.Godot/Prototypes/dq-rpg",
        "Game.Core/Prototypes",
        "Game.Core.Tests/Prototypes",
        "Tests.Godot/tests/Prototype/DqRpgPrototype"
    ];

    private static readonly string[] FocusedWorkspaceRootFiles =
    [
        "Game.sln",
        "GodotGame.sln",
        "GodotGame.csproj",
        "Directory.Build.props",
        "Directory.Build.targets",
        "project.godot",
        "export_presets.cfg",
        "packages.lock.json"
    ];

    private sealed record GoalRepairOutcome(string GoalStatus, bool MarkCompleted);
    private sealed record ExecutionWorkspace(string RootPath, string CodexOutputPath, bool SyncBack, IReadOnlyList<string> ManagedPaths);
    private sealed record AcceptanceValidationResult(string Kind, string Status)
    {
        public bool Passed => string.Equals(Status, "passed", StringComparison.Ordinal);

        public static AcceptanceValidationResult NotRun()
        {
            return new AcceptanceValidationResult("none", "not_run");
        }

        public static AcceptanceValidationResult Pass(string kind)
        {
            return new AcceptanceValidationResult(kind, "passed");
        }

        public static AcceptanceValidationResult Failed(string kind)
        {
            return new AcceptanceValidationResult(kind, "failed");
        }
    }
}
