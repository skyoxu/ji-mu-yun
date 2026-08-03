using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Security.Cryptography;
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
    private const int RecoveredWorkflowMaxDay = 7;
    private const int QuickFixFeedbackPromptMaxChars = 8000;
    private const int GoalRepairFeedbackPromptMaxChars = 12000;
    private const int FeedbackArtifactMaxChars = 20000;
    private const int GeneratorStreamLogMaxChars = 20000;
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
    private readonly HostedContextManifestIssuer? _contextManifestIssuer;
    private readonly HostedContextGatePolicy _contextGatePolicy;
    private readonly IHostedContextManifestValidator? _contextManifestValidator;

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
        HeavyRunnerQueueService? heavyRunnerQueue = null,
        HostedContextManifestIssuer? contextManifestIssuer = null,
        HostedContextGatePolicy? contextGatePolicy = null,
        IHostedContextManifestValidator? contextManifestValidator = null)
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
        _contextManifestIssuer = contextManifestIssuer;
        _contextGatePolicy = contextGatePolicy ?? new HostedContextGatePolicy();
        _contextManifestValidator = contextManifestValidator;
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
            return new PrototypeFeedbackResult("", "prototype_not_ready", "请先完成游戏场景创建，再使用快速修复。", []);
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
                return new PrototypeFeedbackResult("", "missing_plan", "当前项目还没有可修复的游戏模块。", []);
            }

            goalRepair = request.GoalRepair!;
            targetGoal = iterationDetails.Goals.FirstOrDefault(goal =>
                (!string.IsNullOrWhiteSpace(goalRepair.GoalId) && string.Equals(goal.GoalId, goalRepair.GoalId, StringComparison.Ordinal)) ||
                (goalRepair.GoalIndex > 0 && goal.GoalIndex == goalRepair.GoalIndex));
            if (targetGoal is null)
            {
                return new PrototypeFeedbackResult("", "missing_goal", "未找到需要修复的当前任务。", []);
            }

            runMemory = await _metadataStore.GetProjectRunMemoryAsync(project.ProjectId, BuildGoalMemoryScope(targetGoal.GoalIndex), cancellationToken);
        }

        _workspaceSeeder.EnsureSeeded(project.RepoPath);

        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return new PrototypeFeedbackResult(runId, "project_busy", "当前有任务正在执行，请等待完成后再试。", []);
        }

        await using var heavyRunnerLease = await _heavyRunnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, RunType, CancellationToken.None);
        await _metadataStore.MarkRunStartedAsync(runId, heavyRunnerLease.QueuePositionAtStart, CancellationToken.None);
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
            var routeProfile = PrototypeRouteSkillPolicy.ResolveProfile(project);

            await File.WriteAllTextAsync(
                submittedAbsolutePath,
                BuildSubmittedFeedback(project, runId, feedback, now, skillAction, targetGoal),
                Encoding.UTF8,
                CancellationToken.None);

            PrototypeGoalGodotSmokeValidationResult? preflightGodotSmokeFailure = null;
            var preflightResult = targetGoal is null || iterationDetails is null
                ? null
                : ShouldAllowAlreadySatisfiedPreflight(request, targetGoal)
                    ? await TryCompleteAlreadySatisfiedGoalAsync(
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
                        request.SourceKind,
                        now,
                        smokeFailure => preflightGodotSmokeFailure = smokeFailure,
                        CancellationToken.None)
                    : null;
            if (preflightResult is not null)
            {
                return preflightResult;
            }

            var currentAcceptanceValidation = targetGoal is null
                ? PrototypeGoalAcceptanceValidationResult.NotRun()
                : await PrototypeGoalAcceptanceValidator.ValidateAsync(project, targetGoal, _processRunner, CancellationToken.None);
            executionWorkspace = await PrepareExecutionWorkspaceAsync(project, targetGoal, currentAcceptanceValidation, runId, codexOutputAbsolutePath, CancellationToken.None);
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
            var prompt = BuildCodexPrompt(project, runId, feedback, skillAction, targetGoal, runMemory, prototypeContract, godotDiagnostic, godotCleanup, currentAcceptanceValidation, executionWorkspace.ManagedPaths);
            await SetProgressAsync(runId, "running", "generation", goalRepairMode ? $"正在修复任务 {targetGoal!.GoalIndex}。" : "正在执行快速修复。", CancellationToken.None);
            var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, CancellationToken.None);
            var billingApiKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
            var billingBefore = await _billingClient.CaptureAsync(billingApiKeyName, CancellationToken.None);
            var codexCommand = await BuildCodexCommandAsync(prompt, executionWorkspace.CodexOutputPath, model, executionWorkspace.RootPath, project, runId, timeout.Token);
            var codexResult = await _processRunner.RunAsync(CodexHostedProcessCommandFactory.ApplyRuntime(codexCommand, runtimeCredential).WithRunId(runId), timeout.Token);
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
            var recoveredCompletionSummary = "";
            var recoveredCompletionEvidence = "";
            var recoveredProtectedCompletionState = targetGoal is not null &&
                                                   TryRecoverProtectedPrototypeCompletionState(
                                                       project,
                                                       runId,
                                                       targetGoal,
                                                       out recoveredCompletionSummary,
                                                       out recoveredCompletionEvidence);
            if (recoveredProtectedCompletionState)
            {
                assistantMessage = recoveredCompletionSummary;
                codexOutput = AppendCompletionRecoveryEvidence(codexOutput, recoveredCompletionEvidence);
            }
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
                godotSmokeValidation = await ValidateGoalGodotSmokeWithTimeoutAsync(project, targetGoal!, CancellationToken.None);
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
            else if (targetGoal is not null && IsGoalRepairPlatformAcceptanceFailedOrMissing(project, targetGoal, acceptanceValidation))
            {
                assistantMessage = AppendAcceptanceValidationNotRunFailure(assistantMessage, targetGoal);
                codexOutput = AppendAcceptanceValidationNotRunEvidence(codexOutput);
            }
            else if (projectSmokeValidation.Required)
            {
                assistantMessage = projectSmokeValidation.Passed
                    ? AppendProjectSmokeValidationSummary(assistantMessage)
                    : AppendProjectSmokeValidationFailure(assistantMessage, projectSmokeValidation);
            }
            await SetProgressAsync(runId, "running", "finalize", goalRepairMode ? "任务修复结果已返回，正在整理状态。" : "快速修复结果已返回，正在整理日志。", CancellationToken.None);

            var mutationGuardValidation = PrototypeRepairMutationGuard.Validate(project, targetGoal);
            if (!mutationGuardValidation.AllowsProgress)
            {
                assistantMessage = AppendMutationGuardFailure(assistantMessage, mutationGuardValidation);
                codexOutput = AppendMutationGuardFailureEvidence(codexOutput, mutationGuardValidation);
            }

            var goalRepairOutcome = targetGoal is null
                ? null
                : !mutationGuardValidation.AllowsProgress
                    ? new GoalRepairOutcome("needs_fix", false)
                : recoveredProtectedCompletionState
                    ? new GoalRepairOutcome("succeeded", true)
                : acceptanceValidation.Passed
                    ? godotSmokeValidation.Passed && !IsRpgGdUnitBlockingForGoal(targetGoal, rpgGdUnitValidation)
                        ? new GoalRepairOutcome("succeeded", true)
                        : new GoalRepairOutcome("needs_fix", false)
                    : RequiresHardPlatformAcceptance(targetGoal, acceptanceValidation) ||
                      IsGoalRepairPlatformAcceptanceFailedOrMissing(project, targetGoal, acceptanceValidation)
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
                "Prototype quick fix generation output"), CancellationToken.None);

            var platformAcceptanceRepairReason = targetGoal is not null
                ? ResolveGoalRepairPlatformAcceptanceReason(project, targetGoal, acceptanceValidation)
                : null;
            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                model,
                submitted_feedback = submittedRelativePath,
                result_log = resultRelativePath,
                codex_output = codexOutputRelativePath,
                game_type_profile = routeProfile,
                source_boundary = "gdd_derived_contract_only_after_gdd_generation",
                prototype_contract = prototypeContract.RelativePath,
                prototype_contract_present = !string.IsNullOrWhiteSpace(prototypeContract.Json),
                skill_action_id = skillAction?.ActionId,
                skill_name = skillAction?.SkillName,
                source_kind = request.SourceKind,
                quick_fix = true,
                goal_repair = targetGoal is not null,
                goal_id = targetGoal?.GoalId,
                goal_index = targetGoal?.GoalIndex,
                goal_repair_status = goalRepairOutcome?.GoalStatus,
                acceptance_validation = acceptanceValidation.Kind,
                acceptance_validation_status = acceptanceValidation.Status,
                acceptance_validation_reason = acceptanceValidation.Reason,
                acceptance_validation_details = acceptanceValidation.Details,
                goal_repair_platform_acceptance_reason = platformAcceptanceRepairReason,
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

                var refreshed = await RefreshIterationSessionAsync(project.ProjectId, iterationDetails, CancellationToken.None);
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
                        ? $"任务 {targetGoal.GoalIndex} 已修复完成。请确认后决定是否继续任务 {targetGoal.GoalIndex + 1}。"
                        : "所有游戏模块任务已完成。")
                    : $"任务 {targetGoal.GoalIndex} 仍需修复。请继续修复当前任务，不要继续后续任务。";
                await _metadataStore.UpdateProjectIterationSessionStatusAsync(
                    iterationDetails.Session.SessionId,
                    sessionStatus,
                    currentGoalIndex,
                    sessionSummary,
                    refreshed?.Session.LatestEvaluationJson,
                    sessionStatus == "completed" ? now : null,
                    CancellationToken.None);
                PrototypeIterationPlanningAnalysisUpdater.Refresh(_stateWriter, project, iterationPlanState, targetGoal, goalRepairOutcome.GoalStatus, assistantMessage, now, sessionSummary);
                await UpsertGoalRunMemoryAsync(project, targetGoal, goalRepairOutcome.GoalStatus, sessionSummary, assistantMessage, goalRepairOutcome.GoalStatus == "succeeded" ? [] : [sessionSummary], executionWorkspace.ManagedPaths, CancellationToken.None);

                await SetProgressAsync(runId, "completed", "", goalRepairOutcome.GoalStatus == "succeeded" ? $"任务 {targetGoal.GoalIndex} 修复完成。" : $"任务 {targetGoal.GoalIndex} 仍需继续修复。", CancellationToken.None);

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
                await SetProgressAsync(runId, "completed", "", projectSmokeValidation.Required ? "快速修复已完成，并通过原型项目验收。" : "快速修复已完成。", CancellationToken.None);
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
                var summary = $"任务 {targetGoal.GoalIndex} 修复超时。当前任务仍需修复；下一轮应继续聚焦当前任务，并优先缩小到最小验收范围：{timeoutFocus}";
                var iterationPlanState = _stateWriter.ReadLatestIterationPlanState(project);
                await _metadataStore.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", summary, null, CancellationToken.None);
                await _metadataStore.UpdateProjectIterationSessionStatusAsync(iterationDetails.Session.SessionId, "needs_fix", targetGoal.GoalIndex, summary, iterationDetails.Session.LatestEvaluationJson, null, CancellationToken.None);
                PrototypeIterationPlanningAnalysisUpdater.Refresh(_stateWriter, project, iterationPlanState, targetGoal, "needs_fix", summary, DateTimeOffset.UtcNow.ToString("O"), summary);
                await UpsertGoalRunMemoryAsync(project, targetGoal, "needs_fix", $"继续修复当前任务的最小验收范围：{timeoutFocus}", summary, [summary], executionWorkspace?.ManagedPaths, CancellationToken.None);
                await SetProgressAsync(runId, "failed", "timeout", $"任务 {targetGoal.GoalIndex} 修复超时，仍需继续修复。", CancellationToken.None);
                return new PrototypeFeedbackResult(runId, "failed", "当前任务修复超时。系统没有切换到后续任务，你可以继续再次修复当前任务。", [], "needs_fix", "needs_fix", targetGoal.GoalIndex);
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
                var summary = $"任务 {targetGoal.GoalIndex} 修复失败。当前任务仍需修复，请继续聚焦本任务。";
                var iterationPlanState = _stateWriter.ReadLatestIterationPlanState(project);
                await _metadataStore.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", summary, null, CancellationToken.None);
                await _metadataStore.UpdateProjectIterationSessionStatusAsync(iterationDetails.Session.SessionId, "needs_fix", targetGoal.GoalIndex, summary, iterationDetails.Session.LatestEvaluationJson, null, CancellationToken.None);
                PrototypeIterationPlanningAnalysisUpdater.Refresh(_stateWriter, project, iterationPlanState, targetGoal, "needs_fix", summary, DateTimeOffset.UtcNow.ToString("O"), summary);
                await UpsertGoalRunMemoryAsync(project, targetGoal, "needs_fix", summary, "当前任务修复失败。", [summary], executionWorkspace?.ManagedPaths, CancellationToken.None);
                await SetProgressAsync(runId, "failed", "error", $"任务 {targetGoal.GoalIndex} 修复失败，仍需继续修复。", CancellationToken.None);
                return new PrototypeFeedbackResult(runId, "failed", "当前任务修复失败。系统没有推进后续任务，请继续修复这个任务。", [], "needs_fix", "needs_fix", targetGoal.GoalIndex);
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

    private static bool ShouldAllowAlreadySatisfiedPreflight(PrototypeFeedbackRequest request, ProjectIterationGoalSnapshot targetGoal)
    {
        var sourceKind = request.SourceKind?.Trim();
        if (string.Equals(sourceKind, "manual_feedback", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(sourceKind, "feedback_submitted", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(sourceKind, "automatic_validation_repair", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(sourceKind, "module_execute", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        if (IsExperienceModuleGoal(targetGoal) && !IsCompletionEvidenceRecoveryGoal(targetGoal))
        {
            return false;
        }

        return true;
    }

    internal static bool ShouldAllowAlreadySatisfiedPreflightForTesting(PrototypeFeedbackRequest request, ProjectIterationGoalSnapshot targetGoal)
    {
        return ShouldAllowAlreadySatisfiedPreflight(request, targetGoal);
    }

    private static bool IsExperienceModuleGoal(ProjectIterationGoalSnapshot goal)
    {
        if (goal.GoalIndex >= 8)
        {
            return true;
        }

        var combined = string.Join(
            "\n",
            new[] { goal.Title, goal.Description, goal.AcceptanceHint, goal.ResultSummary }
                .Where(static value => !string.IsNullOrWhiteSpace(value)));
        return Regex.IsMatch(combined, @"\bM(?:[8-9]|[1-9][0-9]+)\b", RegexOptions.IgnoreCase) ||
               combined.Contains("试玩", StringComparison.OrdinalIgnoreCase) ||
               combined.Contains("体验", StringComparison.OrdinalIgnoreCase) ||
               combined.Contains("手感", StringComparison.OrdinalIgnoreCase) ||
               combined.Contains("playable experience", StringComparison.OrdinalIgnoreCase) ||
               combined.Contains("game feel", StringComparison.OrdinalIgnoreCase);
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
        SkillActionDefinition? skillAction,
        string? sourceKind,
        string now,
        Action<PrototypeGoalGodotSmokeValidationResult>? onGodotSmokeFailure = null,
        CancellationToken cancellationToken = default)
    {
        await SetProgressAsync(runId, "running", "preflight", $"正在检查任务 {targetGoal.GoalIndex} 是否已经满足验收。", cancellationToken);
        var acceptanceValidation = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, targetGoal, _processRunner, cancellationToken);
        if (!acceptanceValidation.Passed)
        {
            return null;
        }

        var mutationGuardValidation = PrototypeRepairMutationGuard.Validate(project, targetGoal);
        if (!mutationGuardValidation.AllowsProgress)
        {
            return null;
        }

        var assistantMessage = $"""
            当前任务已经通过平台验收。

            平台验收：
            任务 {targetGoal.GoalIndex} 已通过平台验收。当前任务可以进入下一步。
            """;
        var codexOutput = "Preflight validation passed before running generation.";
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
            onGodotSmokeFailure?.Invoke(godotSmokeValidation);
            return null;
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
            "Prototype quick fix generation output"), cancellationToken);

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            preflight = true,
            submitted_feedback = submittedRelativePath,
            result_log = resultRelativePath,
            codex_output = codexOutputRelativePath,
            game_type_profile = PrototypeRouteSkillPolicy.ResolveProfile(project),
            source_boundary = "gdd_derived_contract_only_after_gdd_generation",
            skill_action_id = skillAction?.ActionId,
            skill_name = skillAction?.SkillName,
            source_kind = sourceKind,
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

        var refreshed = await RefreshIterationSessionAsync(project.ProjectId, iterationDetails, cancellationToken);
        var hasNeedsFix = refreshed?.Goals.Any(goal => string.Equals(goal.Status, "needs_fix", StringComparison.Ordinal)) == true;
        var hasMoreGoals = refreshed?.Goals.Any(goal => string.Equals(goal.Status, "pending", StringComparison.Ordinal)) == true;
        var sessionStatus = goalRepairOutcome.GoalStatus == "succeeded"
            ? (hasMoreGoals ? "paused_for_review" : "completed")
            : "needs_fix";
        var sessionSummary = goalRepairOutcome.GoalStatus == "succeeded"
            ? (hasMoreGoals
                ? $"任务 {targetGoal.GoalIndex} 已通过验收。请确认后决定是否继续任务 {targetGoal.GoalIndex + 1}。"
                : "所有游戏模块任务已完成。")
            : $"任务 {targetGoal.GoalIndex} 已通过核心验收，但仍需继续完成引擎验证。";
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
        await UpsertGoalRunMemoryAsync(project, targetGoal, goalRepairOutcome.GoalStatus, sessionSummary, assistantMessage, goalRepairOutcome.GoalStatus == "succeeded" ? [] : [sessionSummary], null, cancellationToken);
        await SetProgressAsync(runId, "completed", "", goalRepairOutcome.GoalStatus == "succeeded" ? $"任务 {targetGoal.GoalIndex} 验收完成。" : $"任务 {targetGoal.GoalIndex} 仍需继续修复。", cancellationToken);

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
                : "Repair timed out after writing changes, but platform validation passed afterward.";
            if (!File.Exists(codexOutputAbsolutePath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(codexOutputAbsolutePath)!);
                await File.WriteAllTextAsync(codexOutputAbsolutePath, codexOutput, Encoding.UTF8, cancellationToken);
            }

            var assistantMessage = $"""
                任务 {targetGoal.GoalIndex} 修复已通过平台复验。
                本次修复进程超过 {effectiveTimeout.TotalSeconds:0} 秒后被终止，但文件变更已经落盘，并且当前任务的静态验收与 Godot smoke 验证均已通过。
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
                "Prototype quick fix generation output"), cancellationToken);

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
                ? $"任务 {targetGoal.GoalIndex} 已通过超时后复验。请确认后决定是否继续任务 {targetGoal.GoalIndex + 1}。"
                : "所有游戏模块任务已完成。";
            await _metadataStore.UpdateProjectIterationSessionStatusAsync(
                iterationDetails.Session.SessionId,
                sessionStatus,
                targetGoal.GoalIndex,
                sessionSummary,
                refreshed?.Session.LatestEvaluationJson,
                sessionStatus == "completed" ? now : null,
                cancellationToken);
            PrototypeIterationPlanningAnalysisUpdater.Refresh(_stateWriter, project, iterationPlanState, targetGoal, "succeeded", assistantMessage, now, sessionSummary);
            await UpsertGoalRunMemoryAsync(project, targetGoal, "succeeded", sessionSummary, assistantMessage, [], null, cancellationToken);
            await SetProgressAsync(runId, "completed", "", $"任务 {targetGoal.GoalIndex} 已通过超时后复验。", cancellationToken);

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
            : "Repair timed out after writing changes, and platform validation still needs repair.";
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
            任务 {targetGoal.GoalIndex} 修复超时。当前任务仍需修复；下一轮应继续聚焦当前任务，并优先缩小到最小验收范围：{timeoutFocus}

            任务 {targetGoal.GoalIndex} 修复运行超过 {effectiveTimeout.TotalSeconds:0} 秒，当前任务仍需修复。

            平台验收：
            STATUS: {(acceptanceValidation.Passed ? "passed" : "needs_fix")}
            REASON: {acceptanceValidation.Reason ?? acceptanceValidation.Status}

            平台引擎验收：
            STATUS: {(godotSmokeValidation.Passed ? "passed" : "needs_fix")}
            VERIFY: 当前任务必须通过 Godot smoke 验证后才能继续。
            REMAINING: 继续修复当前任务，暂时不要推进后续任务。
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
            "Prototype quick fix generation output"), cancellationToken);

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
        var sessionSummary = $"任务 {targetGoal.GoalIndex} 修复超时。当前任务仍需修复；下一轮应继续聚焦当前任务，并优先缩小到最小验收范围：{timeoutFocus} 验证原因：{validationReason}";
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
        await UpsertGoalRunMemoryAsync(project, targetGoal, "needs_fix", sessionSummary, assistantMessage, [sessionSummary], null, cancellationToken);
        await SetProgressAsync(runId, "failed", "validation", $"任务 {targetGoal.GoalIndex} 超时，仍需继续修复验证问题。", cancellationToken);

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
        string? scenePath = null;
        try
        {
            scenePath = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
                _metadataStore,
                project,
                _stateWriter,
                targetGoal.GoalIndex,
                timeout.Token,
                sessionId: targetGoal.SessionId,
                goal: targetGoal,
                allowMissingGoalStateScene: true,
                allowBaselineFallbackForGoalContext: true);
            return await PrototypeGodotSmokeService.ValidateGoalSceneAsync(project, targetGoal, scenePath, _options, _processRunner, timeout.Token);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
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
        var selectedRouteStates = SelectCurrentRouteStates(project, targetGoal);
        var preferredGdUnitPaths = PrototypeGdUnitPathResolver.ExtractGdUnitAddPathsFromRouteStates(selectedRouteStates);
        var smokeScene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            _metadataStore,
            project,
            _stateWriter,
            targetGoal.GoalIndex,
            cancellationToken,
            sessionId: targetGoal.SessionId,
            goal: targetGoal,
            allowMissingGoalStateScene: true);
        var slug = TryResolvePrototypeSlug(smokeScene) ?? "dq-rpg";
        try
        {
            return await PrototypeGodotSmokeService.RunRpgGdUnitValidationAsync(
                _options,
                _processRunner,
                project,
                slug,
                preferredGdUnitPaths,
                requireSuite: true,
                cancellationToken: timeout.Token);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return PrototypeRpgGdUnitValidationResult.RequiredResult(
                false,
                124,
                "",
                "RPG GdUnit validation timed out.",
                "rpg_project_specific_gdunit_timeout",
                preferredGdUnitPaths.FirstOrDefault() ?? "tests/Prototype/DqRpgPrototype",
                null,
                preferredGdUnitPaths);
        }
    }

    private static string? TryResolvePrototypeSlug(string? scene)
    {
        const string prefix = "res://Game.Godot/Prototypes/";
        if (string.IsNullOrWhiteSpace(scene) ||
            !scene.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var remainder = scene[prefix.Length..].Replace('\\', '/');
        var slashIndex = remainder.IndexOf('/', StringComparison.Ordinal);
        if (slashIndex <= 0)
        {
            return null;
        }

        var slug = remainder[..slashIndex];
        return string.IsNullOrWhiteSpace(slug) ? null : slug;
    }

    private static bool RequiresRpgGdUnitValidation(ProjectSnapshot project, ProjectIterationGoalSnapshot targetGoal)
    {
        if (!GameTypeRouteProfiles.IsRpgProject(project))
        {
            return false;
        }

        var text = string.Join(" ", targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint);
        return text.Contains("GdUnit", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("final first-loop acceptance", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("final first loop acceptance", StringComparison.OrdinalIgnoreCase) ||
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

        if (RequiresExplicitRpgGdUnitValidation(targetGoal) && !validation.Ran)
        {
            return true;
        }

        return HasBlockingRpgGdUnitInfrastructureFailure(validation);
    }

    private static bool RequiresExplicitRpgGdUnitValidation(ProjectIterationGoalSnapshot targetGoal)
    {
        var text = string.Join(" ", targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint);
        return text.Contains("GdUnit", StringComparison.OrdinalIgnoreCase);
    }

    private static bool RequiresFullRpgGdUnitValidation(ProjectIterationGoalSnapshot targetGoal)
    {
        var text = string.Join(" ", targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint);
        return text.Contains("final first-loop acceptance", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("final first loop acceptance", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("final prototype acceptance", StringComparison.OrdinalIgnoreCase) ||
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

    private static string TrimForPromptExcerpt(string? value, int maxLength)
    {
        return PrototypePromptText.TrimHeadAndTail(value, maxLength);
    }

    private static string BuildGoalRepairTimeoutFocus(ProjectIterationGoalSnapshot goal)
    {
        var goalText = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint);
        if (ContainsAny(goalText, "opening context", "player objective"))
        {
            return "呈现玩家身份、起点场景和当前目标，并保留 Start Adventure 到下一步能力的入口。";
        }

        if (ContainsAny(goalText, "field navigation", "stable control", "visible MapScene", "map entry", "地图", "移动"))
        {
            return "Start Adventure 后显示 MapScene、玩家可见、稳定移动。只有当前目标明确包含遇敌时才触发首次遇敌。";
        }

        if (ContainsAny(goalText, "conflict entry", "encounter", "first conflict", "遇敌", "冲突"))
        {
            return "从地图、场景或交互清晰进入首次冲突/遇敌/挑战，不推进战斗结算或奖励选择。";
        }

        if (ContainsAny(goalText, "battle or challenge resolution", "battle", "combat", "battlescene", "challenge resolution", "战斗", "挑战"))
        {
            return "完成选中战斗或挑战能力的可读结算；只有项目使用 BattleScene 时才创建或修复独立 BattleScene。";
        }

        if (ContainsAny(goalText, "growth", "reward", "consequence", "奖励", "成长"))
        {
            return "展示奖励、成长或后果反馈；若当前目标要求奖励选择，则胜利后显示 3 个奖励、选择后状态变化可见，并通过 ShowRewardReturnFeedback/ShowRewardReturnStatus、Returned to map、movement is restored 或 rpg_reward_flow_contract 之一留下返回地图反馈契约。";
        }

        if (ContainsAny(goalText, "return or continue", "return-to-map", "return to map", "返回地图"))
        {
            return "返回地图、继续到下一可玩状态或完成指定循环续航，并保持玩家可见和输入可用。";
        }

        if (ContainsAny(goalText, "final first-loop acceptance", "final acceptance", "端到端", "最终验收"))
        {
            return "完成所选 JRPG 首轮能力的端到端验收、Godot smoke、资源解析和最终可玩证明；不要补未被选择的 BattleScene。";
        }

        return goal.GoalIndex switch
        {
            1 => "Start Adventure 后显示 MapScene、玩家可见、稳定移动。只有当前目标明确包含遇敌时才触发首次遇敌。",
            2 => "修复当前目标明确要求的第二个 JRPG 能力；只有目标或最新失败证据包含战斗/冲突时才创建或修复 BattleScene。",
            3 => "修复当前目标明确要求的第三个 JRPG 能力；只有目标要求奖励时才补奖励选择与状态变化。",
            4 => "串联当前已选择的 JRPG 首轮能力，不要补未被选择的战斗、奖励或返回地图能力。",
            5 => "让当前目标明确要求的胜负、失败或进度规则对玩家清晰可读；不要替项目补默认战斗胜负规则。",
            6 => "完成 RPG 原型端到端验收、Godot smoke 和最终可玩证明。",
            _ => string.IsNullOrWhiteSpace(goal.AcceptanceHint) ? goal.Description : goal.AcceptanceHint
        };
    }

    private async Task<ProjectIterationSessionDetails?> RefreshIterationSessionAsync(
        string projectId,
        ProjectIterationSessionDetails iterationDetails,
        CancellationToken cancellationToken)
    {
        var sourceKind = string.Equals(iterationDetails.Session.SourceKind, "repair_plan", StringComparison.OrdinalIgnoreCase)
            ? "repair_plan"
            : null;
        return sourceKind is null
            ? await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken)
            : await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, sourceKind, cancellationToken);
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
        var feedbackForArtifact = TrimForPromptExcerpt(feedback, FeedbackArtifactMaxChars);
        return $"""
            # Prototype Quick Fix Submission

            Project: {project.Name}
            ProjectId: {project.ProjectId}
            RunId: {runId}
            SubmittedAtUtc: {submittedAt}
            SkillMode: {SkillModeLabel(skillAction)}
            GoalRepairMode: {(goal is null ? "false" : "true")}

            ## Feedback

            {feedbackForArtifact}
            
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

    private async Task<HostedProcessCommand> BuildCodexCommandAsync(
        string prompt,
        string outputPath,
        string model,
        string repositoryRoot,
        ProjectSnapshot project,
        string runId,
        CancellationToken cancellationToken)
    {
        HostedContextEnvelope? envelope = null;
        if (_contextManifestIssuer is not null)
        {
            var snapshotId = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(string.Join(
                "\n",
                project.ProjectId,
                project.AccountId,
                runId,
                "codex:prototype-quick-fix",
                prompt)))).ToLowerInvariant();
            envelope = await _contextManifestIssuer.IssueAsync(
                new HostedContextManifestIssue(
                    project.AccountId,
                    project.ProjectId,
                    "codex:prototype-quick-fix",
                    snapshotId,
                    "prototype-quick-fix.v1",
                    TimeSpan.FromMinutes(5),
                    prompt,
                    runId,
                    "workspace-write",
                    [repositoryRoot],
                    [outputPath]),
                cancellationToken);
        }

        return await CodexHostedProcessCommandFactory.BuildAsync(new CodexHostedProcessRequest(
            repositoryRoot,
            outputPath,
            prompt,
            model,
            ReasoningEffort,
            OperationKey: "codex:prototype-quick-fix",
            ContextEnvelope: envelope),
            _contextGatePolicy,
            _contextManifestValidator,
            cancellationToken);
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
        PrototypeGoalAcceptanceValidationResult? currentAcceptanceValidation = null,
        IReadOnlyList<string>? focusedWorkspaceDirectories = null)
    {
        if (goal is not null)
        {
            return BuildGoalRepairPrompt(project, runId, feedback, goal, runMemory, prototypeContract, godotDiagnostic, godotCleanup, currentAcceptanceValidation, focusedWorkspaceDirectories ?? []);
        }

        var skillInstruction = skillAction is null
            ? "能力模式：普通模式。"
            : $"能力模式：{skillAction.Label}。执行时使用 ${skillAction.SkillName} 的方法。";
        var contractBlock = PrototypeContractService.BuildPromptBlock(prototypeContract ?? MissingPrototypeContract());
        var godotDiagnosticBlock = GodotFailureDiagnosticService.BuildPromptBlock(godotDiagnostic ?? GodotFailureDiagnostic.None(), godotCleanup);
        var physicsPolicyBlock = PrototypePhysicsRequirementPolicy.BuildPromptBlock(project, feedback);
        var feedbackForPrompt = TrimForPromptExcerpt(feedback, QuickFixFeedbackPromptMaxChars);

        return $"""
            你正在执行积木云 Phase A 的快速修复任务。
            {PrototypeRouteSkillPolicy.BuildPromptBlock(project)}
            {contractBlock}
            {godotDiagnosticBlock}
            {physicsPolicyBlock}
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
            - Windows/UTF-8 约束：读取包含中文文件名或中文内容的文件时，使用 Python `Path(...).read_text(encoding="utf-8-sig")` 或 `encoding="utf-8"`；需要打印中文或 BOM 内容时先设置 `PYTHONIOENCODING=utf-8`。不要用会把中文路径变成问号的 PowerShell 文本管道读取这些文件。
            - Windows 路径约束：不要在 PowerShell 下把 `Game.Godot/**/*.cs` 这类 Unix glob 直接传给 `rg`；用 `rg --files -g "*.cs" Game.Godot` 或明确文件路径。
            - 如果最新平台阻塞是 Godot smoke、Godot build callback、`--build-solutions` 或 C# 编译失败，必须优先修复平台 stderr 指出的具体阻塞；如果无法读取、无法定位或只做了静态猜测，输出 STATUS: needs_fix，不要输出 STATUS: completed。
            - Godot 运行验证只能使用仓库内已有的统一 smoke 入口；不要自行直接启动 Godot headless 长进程，不要自行指定 `user://logs` 日志路径。平台会在修复后独立执行统一 smoke 复验。
            - 如果问题超出小修范围，不要展开大工程，只输出简短结论，说明应改走正式反馈。
            - 输出必须面向浏览器用户，不要包含路径、命令、脚本名、日志名、环境变量。

            {PrototypeGameplayPromptGuards.BuildCombatPressureGuardPromptBlock()}

            目标项目：
            - ProjectId: {project.ProjectId}
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}
            - QuickFixRunId: {runId}

            用户快速修复请求：
            {feedbackForPrompt}

            返回格式：
            1. 是否完成快速修复
            2. 改了什么
            3. 如何验证
            4. 如果未完成，说明为什么应改走正式反馈
            """;
    }

    private async Task<PrototypeGoalGodotSmokeValidationResult> ValidateProjectSmokeAfterQuickFixAsync(ProjectSnapshot project, CancellationToken cancellationToken)
    {
        if (!GameTypeRouteProfiles.IsRpgProject(project))
        {
            return PrototypeGoalGodotSmokeValidationResult.NotRequired();
        }

        var scenePath = await PrototypeSmokeSceneResolver.ResolveLatestAsync(_metadataStore, project, _stateWriter, cancellationToken: cancellationToken);
        if (string.IsNullOrWhiteSpace(scenePath))
        {
            return PrototypeGoalGodotSmokeValidationResult.RequiredResult(PrototypeGodotSmokeResult.NotRun("prototype_smoke_scene_missing"));
        }

        var smoke = await PrototypeGodotSmokeService.RunAsync(_options, _processRunner, project.RepoPath, scenePath, cancellationToken);
        return PrototypeGoalGodotSmokeValidationResult.RequiredResult(smoke);
    }

    private bool TryRecoverProtectedPrototypeCompletionState(
        ProjectSnapshot project,
        string runId,
        ProjectIterationGoalSnapshot goal,
        out string assistantMessage,
        out string recoveryEvidence)
    {
        assistantMessage = "";
        recoveryEvidence = "";
        var repairState = IsCompletionEvidenceRecoveryGoal(goal)
            ? _stateWriter.ReadLatestPrototypeRepairState(project)
            : "";
        if (string.IsNullOrWhiteSpace(repairState))
        {
            repairState = ReadLatestNeedsFixCompletionEvidenceState(project, goal.GoalIndex);
            if (string.IsNullOrWhiteSpace(repairState))
            {
                return false;
            }
        }

        try
        {
            using var document = JsonDocument.Parse(repairState);
            var root = document.RootElement;
            if (!IsProtectedCompletionRecoveryState(root))
            {
                return false;
            }

            if (!root.TryGetProperty("prototype_completion", out var completion) ||
                completion.ValueKind != JsonValueKind.Object ||
                !TryReadBool(completion, "succeeded") ||
                !string.IsNullOrWhiteSpace(TryReadString(completion, "error")))
            {
                return false;
            }

            var smokeScene = TryReadString(root, "smoke_scene");
            if (string.IsNullOrWhiteSpace(smokeScene))
            {
                smokeScene = TryReadString(completion, "smoke_scene");
            }

            var prototypeRecord = TryReadString(root, "prototype_record");
            var prototypeContract = TryReadString(root, "prototype_contract");
            var slug = ResolveRecoverySlug(project, root, prototypeRecord, smokeScene);
            if (string.IsNullOrWhiteSpace(slug) ||
                string.IsNullOrWhiteSpace(prototypeRecord) ||
                string.IsNullOrWhiteSpace(smokeScene))
            {
                return false;
            }

            var prototypeSpec = ResolveRecoveryPrototypeSpec(project.RepoPath, root, slug);
            if (string.IsNullOrWhiteSpace(prototypeSpec))
            {
                return false;
            }

            var normalizedSlug = PrototypeRecordWriter.SanitizeSlug(slug);
            if (!TryResolveRecoveredCompletionEvidence(
                    project.RepoPath,
                    normalizedSlug,
                    prototypeRecord,
                    prototypeSpec,
                    smokeScene,
                    root,
                    completion,
                    out var completedThroughDay,
                    out var recoveredWorkflowSteps))
            {
                return false;
            }

            var prototypeRecordPath = Path.Combine(project.RepoPath, prototypeRecord.Replace('/', Path.DirectorySeparatorChar));
            var prototypeSpecPath = Path.Combine(project.RepoPath, prototypeSpec.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(prototypeRecordPath) ||
                !File.Exists(prototypeSpecPath) ||
                !PrototypeSceneExists(project.RepoPath, smokeScene))
            {
                return false;
            }

            var activeRoot = Path.Combine(project.RepoPath, "logs", "ci", "active-prototypes");
            Directory.CreateDirectory(activeRoot);
            var packagingRelativePath = ToSlash(Path.Combine("logs", "ci", "active-prototypes", $"{normalizedSlug}.packaging.json"));
            var completionRelativePath = ToSlash(Path.Combine("logs", "ci", "active-prototypes", $"{normalizedSlug}.completion.md"));
            var completionSummary = FirstNonEmpty(
                TryReadString(completion, "completion_summary"),
                TryReadString(root, "completion_summary"),
                $"Prototype completion state for {normalizedSlug} was recovered from prototype-repair evidence.");
            var nextStepSource = TryReadString(completion, "next_step_source");
            var nextStepEvaluation = TryReadString(completion, "next_step_evaluation");
            var nextStepEvaluationReason = TryReadString(completion, "next_step_evaluation_reason");

            var activeStatePath = Path.Combine(activeRoot, $"{normalizedSlug}.active.json");
            File.WriteAllText(
                activeStatePath,
                JsonSerializer.Serialize(new
                {
                    status = "completed-through-day",
                    prototype_file = prototypeRecord,
                    prototype_spec = prototypeSpec,
                    completed_through_day = completedThroughDay,
                    missing_required_fields = Array.Empty<string>(),
                    steps_run = recoveredWorkflowSteps,
                    packaging_summary = packagingRelativePath,
                    completion_summary = completionSummary,
                    completion_report = completionRelativePath,
                    next_step_source = nextStepSource,
                    next_step_evaluation = nextStepEvaluation,
                    next_step_evaluation_reason = nextStepEvaluationReason
                }, new JsonSerializerOptions(JsonSerializerDefaults.Web) { WriteIndented = true }),
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

            var packagingPath = Path.Combine(project.RepoPath, packagingRelativePath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(packagingPath)!);
            File.WriteAllText(
                packagingPath,
                JsonSerializer.Serialize(new
                {
                    schema_version = 1,
                    kind = "prototype-packaging-summary",
                    generated_at_utc = DateTimeOffset.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                    slug = normalizedSlug,
                    prototype_record = prototypeRecord,
                    prototype_spec = prototypeSpec,
                    default_scene = smokeScene,
                    default_scene_label = Path.GetFileNameWithoutExtension(smokeScene),
                    tdd_summary_paths = Array.Empty<string>(),
                    tdd_summaries = Array.Empty<object>(),
                    tdd_stage_counts = new { red = 0, green = 0, refactor = 0, total = 0 },
                    prototype_artifacts = new[] { prototypeRecord, prototypeSpec, packagingRelativePath, completionRelativePath },
                    playtest_focus_points = Array.Empty<string>(),
                    steps_completed = recoveredWorkflowSteps
                }, new JsonSerializerOptions(JsonSerializerDefaults.Web) { WriteIndented = true }),
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

            var completionPath = Path.Combine(project.RepoPath, completionRelativePath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(completionPath)!);
            File.WriteAllText(
                completionPath,
                string.Join(
                    "\n",
                    [
                        "# Prototype Completion Recovery",
                        "",
                        completionSummary,
                        "",
                        $"Recovered from repair evidence during run `{runId}`.",
                        $"Default scene: `{smokeScene}`"
                    ]),
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

            _stateWriter.WritePrototypeState(project, new
            {
                route = "prototype-7day-playable",
                game_type_profile = PrototypeRouteSkillPolicy.ResolveProfile(project),
                source_boundary = "gdd_derived_contract_only_after_gdd_generation",
                run_id = runId,
                status = "succeeded",
                exit_code = 0,
                prototype_record = prototypeRecord,
                prototype_contract = prototypeContract,
                slug = normalizedSlug,
                prototype_completion = new
                {
                    succeeded = true,
                    status = "completed-through-day",
                    completed_through_day = completedThroughDay,
                    error = (string?)null,
                    smoke_scene = smokeScene,
                    completion_summary = completionSummary,
                    next_step_source = nextStepSource,
                    next_step_evaluation = nextStepEvaluation,
                    next_step_evaluation_reason = nextStepEvaluationReason
                },
                godot_smoke = new
                {
                    ran = false,
                    exit_code = 0,
                    reason = "recovered_from_prototype_repair_state",
                    scene = smokeScene,
                    diagnostic_excerpt = "",
                    resource_diagnostics = Array.Empty<string>()
                },
                updated_utc = DateTimeOffset.UtcNow.ToString("O")
            });

            assistantMessage =
                $"当前任务已完成。系统已根据原型修复旁证恢复 canonical 原型完成状态，任务 {goal.GoalIndex} 可以进入下一步。";
            recoveryEvidence =
                $"Recovered protected prototype completion state for slug {normalizedSlug}; active prototype state, packaging summary, completion report, and canonical route state were rewritten by the platform.";
            return true;
        }
        catch (JsonException)
        {
            return false;
        }
        catch (IOException)
        {
            return false;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private static PrototypeContractSnapshot MissingPrototypeContract()
    {
        return new PrototypeContractSnapshot("routes/prototype-contract/latest.json", "");
    }

    private static string ReadLatestNeedsFixCompletionEvidenceState(ProjectSnapshot project, int goalIndex)
    {
        var step = goalIndex <= 0 ? "step-unknown" : $"step-{goalIndex:00}";
        var candidateRoots = new[]
        {
            Path.Combine(project.RepoPath, "meta", "routes", "needs-fix", step),
            Path.Combine(project.MetaPath, "routes", "needs-fix", step)
        };

        foreach (var directory in candidateRoots.Where(Directory.Exists).Distinct(StringComparer.OrdinalIgnoreCase))
        {
            var candidate = Directory
                .EnumerateFiles(directory, "*.json", SearchOption.TopDirectoryOnly)
                .Select(path => new FileInfo(path))
                .Where(file => file.Name.Contains("completion-evidence", StringComparison.OrdinalIgnoreCase))
                .OrderByDescending(file => file.LastWriteTimeUtc)
                .FirstOrDefault(file => IsNeedsFixCompletionEvidenceState(file.FullName));
            if (candidate is not null)
            {
                return File.ReadAllText(candidate.FullName, Encoding.UTF8);
            }
        }

        return "";
    }

    private static bool IsNeedsFixCompletionEvidenceState(string path)
    {
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
            return IsProtectedCompletionRecoveryState(document.RootElement);
        }
        catch (JsonException)
        {
            return false;
        }
        catch (IOException)
        {
            return false;
        }
    }

    private static bool IsProtectedCompletionRecoveryState(JsonElement root)
    {
        var repairStatus = TryReadString(root, "status");
        if (string.Equals(repairStatus, "completed_with_protected_latest_blocker", StringComparison.OrdinalIgnoreCase) &&
            JsonArrayContains(root, "fixed_intent", "prototype_completion_state_missing"))
        {
            return true;
        }

        if (!string.Equals(repairStatus, "succeeded", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        var canonicalWrite = TryReadString(root, "canonical_completion_state_write");
        var blockedTarget = TryReadString(root, "blocked_target");
        var blockedReason = TryReadString(root, "blocked_reason") ?? "";
        return string.Equals(canonicalWrite, "blocked_permission_denied", StringComparison.OrdinalIgnoreCase) &&
               SameSlashPath(blockedTarget, "meta/routes/prototype/latest.json") &&
               (blockedReason.Contains("canonical", StringComparison.OrdinalIgnoreCase) ||
                blockedReason.Contains("prototype_completion_state_missing", StringComparison.OrdinalIgnoreCase) ||
                blockedReason.Contains("completion state", StringComparison.OrdinalIgnoreCase));
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
        PrototypeGoalAcceptanceValidationResult? currentAcceptanceValidation = null,
        IReadOnlyList<string>? focusedWorkspaceDirectories = null)
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
        var platformAcceptanceScopeOverrideBlock = BuildPlatformAcceptanceScopeOverrideBlock(currentAcceptanceValidation);
        var godotDiagnosticBlock = GodotFailureDiagnosticService.BuildPromptBlock(godotDiagnostic ?? GodotFailureDiagnostic.None(), godotCleanup);
        var rpgGdUnitContextBlock = BuildRpgGdUnitRepairContextBlock(project, goal);
        var physicsPolicyBlock = PrototypePhysicsRequirementPolicy.BuildPromptBlock(project, string.Join("\n", goal.Title, goal.Description, goal.AcceptanceHint, feedback));
        var feedbackForPrompt = TrimForPromptExcerpt(feedback, GoalRepairFeedbackPromptMaxChars);

        return $"""
            你正在执行积木云 Phase A 的单目标迭代修复任务。

            {PrototypeRouteSkillPolicy.BuildPromptBlock(project)}
            {contractBlock}
            {godotDiagnosticBlock}
            {rpgGdUnitContextBlock}
            {physicsPolicyBlock}
            Mandatory rules:
            - Do not define or shadow xUnit types. Never add `namespace Xunit`, `FactAttribute`, `TheoryAttribute`, `InlineDataAttribute`, or `Assert` classes in project tests. Use the existing `using Xunit;` and package references.
            - 这次只处理当前任务，不要顺手扩展到后续任务。
            - 这是任务级 needs-fix 修复，不是 90 秒快速修复；允许为了完成当前任务做必要的局部实现，但仍禁止扩大到后续任务。
            - 直接围绕当前任务实现，不要先做任务恢复、仓库导览、规则总结或工作流巡检。
            - 不要读取或总结 AGENTS.md、decision-logs、execution-plans、active-task、session recovery 一类文件。
            - 不要修改 PhaseA.Platform/**、PhaseA.Platform.Tests/**、scripts/**、docs/** 这些云端控制台与工具链文件。
            - 如果当前任务是 RPG 原型修复，默认只允许修改 {BuildFocusedWorkspaceScopeText(focusedWorkspaceDirectories ?? [])} 这些与原型直接相关的位置。
            - Godot C# 项目结构：可构建项目是仓库根目录的 GodotGame.csproj；Game.Godot/ 只是运行时场景和脚本目录，不是独立 C# 项目。不要执行或引用 Game.Godot/Game.Godot.csproj。
            - 不要在本路由中执行 dotnet build、dotnet test、Godot prewarm 或 GdUnit；这些本地验证命令会写入 obj/bin/.godot 并可能触发文件锁。修复完成后由平台统一执行隔离验收。
            - 仅当 Godot stderr 明确指出 `Game.Godot/Examples/**.tscn:1 - Parse Error: Expected '['` 时，允许把被点名的示例场景重写为无 UTF-8 BOM 的 Godot 文本场景；不要借机改示例内容。
            - 结构化运行记忆和历史摘要只用于理解上次到哪里了，不是本轮修复任务。
            - 不要把“路由状态、恢复逻辑、平台测试、文档整理、脚本调整”当作当前任务的完成内容，除非当前任务标题和验收提示明确要求。
            - 如果当前任务是玩法/Godot/RPG 任务，完成标准必须来自 Title、Description、AcceptanceHint 中的玩法验收。
            - 如果当前任务是“恢复运行证据/完成证据”，且因为受保护文件无法直接覆写 canonical completion state，则必须把已验证的 completion evidence 完整写入当前 repair 输出：至少包含 completed_through_day，以及 day 1-7 的 steps_run/steps_completed。
            - 对这类 completion evidence 恢复，不要只写“已恢复”摘要；要保留真实 step status、reason、record、prototype_spec 等结构化字段，便于平台补写 canonical state。
            - Main.tscn SOP：原型相关修复必须保持根级 VBox、Overlays、ScreenRoot 默认 visible = false；final/full-playable 目标必须修到这一点通过。
            - Godot stderr 属于当前任务验收信号：`.tscn:1 - Parse Error: Expected '['` 必须修到对应场景文件首字符就是 `[`；`Nodes with non-equal opposite anchors` 必须修到 backtrace 指向的脚本不再触发该 warning。
            - `This control can't grab focus` 也属于当前任务验收信号：必须移除对不可聚焦容器的 `GrabFocus()`，或先配置正确 focus mode。
            - Windows/UTF-8 约束：读取包含中文文件名或中文内容的文件时，使用 Python `Path(...).read_text(encoding="utf-8-sig")` 或 `encoding="utf-8"`；需要打印中文或 BOM 内容时先设置 `PYTHONIOENCODING=utf-8`。不要用会把中文路径变成问号的 PowerShell 文本管道读取这些文件。
            - Windows 路径约束：不要在 PowerShell 下把 `Game.Godot/**/*.cs` 这类 Unix glob 直接传给 `rg`；用 `rg --files -g "*.cs" Game.Godot` 或明确文件路径。
            - 如果最新平台阻塞是 Godot smoke、Godot build callback、`--build-solutions` 或 C# 编译失败，必须优先修复平台 stderr 指出的具体阻塞；如果无法读取、无法定位或只做了静态猜测，输出 STATUS: needs_fix，不要输出 STATUS: completed。
            - Godot 运行验证只能使用仓库内已有的统一 smoke 入口；不要自行直接启动 Godot headless 长进程，不要自行指定 `user://logs` 日志路径。平台会在修复后独立执行统一 smoke 复验。
            - 不要自行运行 dotnet build、dotnet test、Godot prewarm 或 GdUnit；这些验证由平台在隔离输出目录中执行。
            - 对玩法/Godot/RPG 任务，只有实际修复并验证对应玩法验收，才能输出 STATUS: completed。
            - 不要处理测试宿主、权限、构建系统、平台链路之类的基础设施问题，除非它们是阻塞当前任务的唯一剩余问题。
            - 优先用最小改动完成任务。
            - 如果被阻塞，直接报告阻塞原因，不要改无关基础设施。
            - 完成后输出面向浏览器用户的简明中文结果，不要包含路径、命令、脚本名、日志名、环境变量。

            {PrototypeGameplayPromptGuards.BuildCombatPressureGuardPromptBlock()}

            项目：
            - ProjectId: {project.ProjectId}
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}
            - GoalRepairRunId: {runId}

            当前唯一任务：
            - GoalIndex: {goal.GoalIndex}
            - Title: {goal.Title}
            - Description: {goal.Description}
            - AcceptanceHint: {goal.AcceptanceHint}
            - PreviousResultSummary: {BuildCompactGoalSummary(goal.ResultSummary)}

            {platformAcceptanceBlock}

            {currentPlatformAcceptanceBlock}

            {platformAcceptanceScopeOverrideBlock}

            用户触发这次修复时附带的说明：
            {feedbackForPrompt}

            {memoryBlock}

            {BuildWorkspaceRuntimeText(focusedWorkspaceDirectories ?? [])}
            你不需要也不应该做仓库恢复、全仓巡检、部署修复或文档整理。

            成功定义：
            - 只有当当前任务已可继续，才可视为修复成功。
            - “已可继续”必须指当前任务的玩法/业务验收通过，不是平台路由或恢复语义通过。
            - 对奖励闭环目标，最小完成范围是：胜利后出现 3 个奖励、选择任一奖励后状态变化可见、随后返回地图。
            - 如果仍未可继续，必须明确写出“当前任务仍需修复”以及唯一剩余阻塞。
            - 不要切换去处理任务 {goal.GoalIndex + 1} 或任何后续任务。

            输出格式：
            STATUS: completed|needs_fix
            SUMMARY: 用 2-4 句中文说明当前任务是否完成，以及对用户有什么变化
            CHANGED: 用 1-3 行列出本轮实际完成的改动
            VERIFY: 用 1-3 行说明如何验证
            REMAINING: 若未完全完成，写出剩余问题；若已完成，写 none
            """;
    }

    private static string BuildPlatformAcceptanceScopeOverrideBlock(PrototypeGoalAcceptanceValidationResult? validation)
    {
        if (!IsCoreTestFailure(validation))
        {
            return "";
        }

        if (IsCoreTestPackageReferenceFailure(validation))
        {
            return """
                Platform acceptance scope override:
                - The current blocker is core_tests_failed with CS0246 for Xunit or FluentAssertions.
                - This overrides the generic RPG gameplay-only edit scope for this run.
                - Required first target: inspect and repair Game.Core.Tests/Game.Core.Tests.csproj PackageReference entries.
                - Allowed package references include Microsoft.NET.Test.Sdk, xunit, xunit.runner.visualstudio, FluentAssertions, and related test dependencies.
                - Do not create hand-written Xunit shims, do not delete tests, and do not change gameplay/UI while this blocker remains open.
                - Report STATUS: needs_fix unless the package-reference blocker has actually been repaired.
                """;
        }

        if (IsMsBuildProjectExtensionsPathFailure(validation))
        {
            return """
                Platform acceptance scope override:
                - The current blocker is core_tests_failed with MSB3540 for MSBuildProjectExtensionsPath.
                - This overrides the generic RPG gameplay-only edit scope for this run.
                - Required first target: remove any MSBuildProjectExtensionsPath assignment from .csproj files when it is imported too late.
                - If intermediate-output isolation is still required, set it before Microsoft.Common.props is imported, for example in Directory.Build.props.
                - Do not add late MSBuildProjectExtensionsPath properties to GodotGame.csproj, Game.Core.csproj, or Game.Core.Tests.csproj.
                - Report STATUS: needs_fix unless the MSB3540 blocker has actually been repaired.
                """;
        }

        return """
            Platform acceptance scope override:
            - The current blocker is core_tests_failed with C# compile errors in PlatformAcceptanceDetails.
            - This overrides the generic RPG gameplay-only edit scope for this run.
            - Required first target: repair only the files, symbols, and C# error codes named in Current platform acceptance diagnosis before repair.
            - If PlatformAcceptanceDetails names Game.Core/Prototypes/DqRpgPrototypeLoop.cs and missing PlayerX/PlayerY on DqRpgPrototypeState, fix that compile contract first.
            - Do not continue gameplay/UI/content polish while a named C# compile error remains open.
            - Report STATUS: needs_fix unless the named C# compile errors have actually been repaired.
            """;
    }

    private static string BuildWorkspaceRuntimeText(IReadOnlyList<string> focusedWorkspaceDirectories)
    {
        return focusedWorkspaceDirectories.Count == 0
            ? "当前运行环境使用完整项目工作区；仍必须按当前任务范围执行，不要做仓库恢复、全仓巡检、部署修复或文档整理。"
            : "当前运行环境已经切到一个只包含原型白名单目录的聚焦工作区。";
    }

    private static bool IsCoreTestFailure(PrototypeGoalAcceptanceValidationResult? validation)
    {
        return validation is not null &&
               string.Equals(validation.Status, "failed", StringComparison.OrdinalIgnoreCase) &&
               string.Equals(validation.Reason, "core_tests_failed", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsCoreTestPackageReferenceFailure(PrototypeGoalAcceptanceValidationResult? validation)
    {
        if (validation is null || !IsCoreTestFailure(validation))
        {
            return false;
        }

        var details = validation.Details ?? "";
        return details.Contains("CS0246", StringComparison.OrdinalIgnoreCase) &&
               (details.Contains("Xunit", StringComparison.OrdinalIgnoreCase) ||
                details.Contains("FluentAssertions", StringComparison.OrdinalIgnoreCase));
    }

    private static bool IsMsBuildProjectExtensionsPathFailure(PrototypeGoalAcceptanceValidationResult? validation)
    {
        if (validation is null || !IsCoreTestFailure(validation))
        {
            return false;
        }

        var details = validation.Details ?? "";
        return details.Contains("MSB3540", StringComparison.OrdinalIgnoreCase) &&
               details.Contains("MSBuildProjectExtensionsPath", StringComparison.OrdinalIgnoreCase);
    }

    private static string BuildRpgGdUnitRepairContextBlock(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        if (!GameTypeRouteProfiles.IsRpgProject(project) ||
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
            if (line.StartsWith("res://tests/Prototype/", StringComparison.OrdinalIgnoreCase))
            {
                isImportant = true;
                captureFailure = line.Contains("FAILED", StringComparison.OrdinalIgnoreCase);
            }
            else if (line.StartsWith("Report:", StringComparison.OrdinalIgnoreCase))
            {
                isImportant = true;
                captureFailure = true;
            }
            else if (captureFailure &&
                     (line.StartsWith("'", StringComparison.Ordinal) ||
                      line.StartsWith("but is ", StringComparison.OrdinalIgnoreCase) ||
                      line.Contains(" but is ", StringComparison.OrdinalIgnoreCase)))
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
            {BuildCurrentAcceptanceRepairFocus(validation)}
            - If Status is failed, repair the listed reason items before reporting STATUS: completed.
            """;
    }

    private static string BuildCurrentAcceptanceRepairFocus(PrototypeGoalAcceptanceValidationResult validation)
    {
        if (validation.Reason?.StartsWith("missing_rpg_map_entry_contract", StringComparison.OrdinalIgnoreCase) == true)
        {
            return "- RepairFocus: Repair the full RPG/JRPG map-entry contract group, not only the first missing_file. Ensure MapScene.tscn and Scripts/MapScene.cs exist together, and satisfy map nodes, grid-position mapping, player visibility restore, and stable movement handling. Add RpgEnemyAsset or encounter trigger wiring only when the selected route or latest failure explicitly requires encounter, conflict, or battle.";
        }

        if (validation.Reason?.StartsWith("missing_rpg_battle_scene_contract", StringComparison.OrdinalIgnoreCase) == true)
        {
            return "- RepairFocus: Repair the dedicated RPG/JRPG battle-scene contract. Ensure Game.Godot/Prototypes/dq-rpg/BattleScene.tscn and Scripts/BattleScene.cs exist together, BattleScene.tscn exposes BattleScene, AttackButton, and file-backed Texture2D nodes named RpgPlayerAsset and RpgEnemyAsset, and BattleScene.cs exposes BattleFinished plus ResolveBattle or ResolveAttackTurn battle settlement wiring instead of leaving the battle loop only inside DqRpgPrototype.cs.";
        }

        if (validation.Reason?.StartsWith("missing_rpg_reward_flow_contract", StringComparison.OrdinalIgnoreCase) == true)
        {
            return "- RepairFocus: Repair the RPG/JRPG reward-flow contract. Ensure victory or consequence creates exactly three understandable reward choices, selecting one calls ApplyReward, closes the reward panel, shows visible stat/consequence feedback, returns or refreshes the map view, and restores player visibility. Also leave a validation-facing map-return feedback marker such as ShowRewardReturnFeedback, ShowRewardReturnStatus, Returned to map, movement is restored, or rpg_reward_flow_contract in the active DqRpgPrototype.cs/MapScene.cs flow. If the reward panel is owned by DqRpgPrototype.cs instead of BattleScene.cs, keep that shape coherent and expose the same contract markers there.";
        }

        if (validation.Reason?.StartsWith("missing_required_core_markers", StringComparison.OrdinalIgnoreCase) == true)
        {
            return validation.Kind switch
            {
                "jrpg-party-character-state-readability" => "- RepairFocus: Repair the complete JRPG character-state readability contract. Make HP/stats/status or equivalent character state visible in runtime UI and keep the state consistent after the relevant loop event; do not satisfy this step with code-only markers.",
                "jrpg-return-or-continue-loop" => "- RepairFocus: Repair the complete JRPG return/continue contract. After resolution or reward, return to a visible playable field/map/town or the intended next playable state, restore player visibility, restore input, and show feedback that explains the transition.",
                "jrpg-quest-story-progress" => "- RepairFocus: Repair the complete JRPG quest/story progress contract. Player action must visibly change objective, quest, story, dialog, or narrative state and communicate the next objective; do not add BattleScene or reward work unless the project contract requires it.",
                "jrpg-final-first-loop-acceptance" => "- RepairFocus: Repair the selected JRPG first-loop end-to-end contract as a group. Preserve opening context, field navigation, selected conflict/battle/reward/return/quest capabilities, runtime asset usage, Main.tscn hidden host UI, Godot validation, and package readiness together before reporting completion.",
                _ => "- RepairFocus: Add or restore the exact required runtime/test evidence markers listed in PlatformAcceptanceReason. Keep the repair scoped to the current goal capability; do not report completion until each missing_marker item is represented in gameplay code, tests, UI text, or a clear validation-facing contract marker."
            };
        }

        return "";
    }

    private static bool RequiresHardPlatformAcceptance(
        ProjectIterationGoalSnapshot goal,
        PrototypeGoalAcceptanceValidationResult acceptanceValidation)
    {
        return string.Equals(acceptanceValidation.Status, "failed", StringComparison.Ordinal) &&
               goal.GoalIndex is >= 1 and <= 10 &&
               (acceptanceValidation.Kind.StartsWith("rpg-", StringComparison.Ordinal) ||
                acceptanceValidation.Kind.StartsWith("jrpg-", StringComparison.Ordinal) ||
                acceptanceValidation.Kind.StartsWith("survivorslike-", StringComparison.Ordinal));
    }

    private static bool IsGoalRepairPlatformAcceptanceFailedOrMissing(
        ProjectSnapshot project,
        ProjectIterationGoalSnapshot goal,
        PrototypeGoalAcceptanceValidationResult acceptanceValidation)
    {
        return ResolveGoalRepairPlatformAcceptanceReason(project, goal, acceptanceValidation) is not null;
    }

    private static string? ResolveGoalRepairPlatformAcceptanceReason(
        ProjectSnapshot project,
        ProjectIterationGoalSnapshot goal,
        PrototypeGoalAcceptanceValidationResult acceptanceValidation)
    {
        if (string.Equals(acceptanceValidation.Status, "failed", StringComparison.OrdinalIgnoreCase))
        {
            return string.IsNullOrWhiteSpace(acceptanceValidation.Reason)
                ? "platform_acceptance_failed"
                : acceptanceValidation.Reason;
        }

        if (string.Equals(acceptanceValidation.Status, "not_run", StringComparison.OrdinalIgnoreCase) &&
            RequiresRpgGoalPlatformAcceptance(project, goal))
        {
            return "platform_acceptance_not_run_for_rpg_goal";
        }

        return null;
    }

    private static bool RequiresRpgGoalPlatformAcceptance(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);
        if (contract is not null &&
            (contract.MapEntryAcceptance ||
             contract.BattleSceneAcceptance ||
             contract.RewardFlowAcceptance ||
             contract.FinalAcceptance ||
             contract.AssetUsageAcceptance ||
             contract.MainSceneHostUiHiddenAcceptance ||
             contract.Kind.StartsWith("rpg-", StringComparison.Ordinal) ||
             contract.Kind.StartsWith("jrpg-", StringComparison.Ordinal) ||
             contract.Kind.StartsWith("default-rpg-", StringComparison.Ordinal)))
        {
            return true;
        }

        if (!GameTypeRouteProfiles.IsRpgProject(project))
        {
            return false;
        }

        var text = string.Join(" ", project.GameTypeSource, project.GameName, goal.Title, goal.Description, goal.AcceptanceHint);
        return ContainsAny(
            text,
            "start adventure",
            "map movement",
            "stable movement",
            "visible map",
            "mapscene",
            "battle",
            "battle scene",
            "battlescene",
            "encounter",
            "challenge resolution",
            "battle or challenge resolution",
            "settlement",
            "reward loop",
            "return to map",
            "first loop",
            "地图移动",
            "稳定移动",
            "可见地图",
            "战斗",
            "遇敌",
            "战斗场景",
            "挑战结算",
            "战斗或挑战结算",
            "结算",
            "奖励回路",
            "返回地图",
            "首轮闭环");
    }

    private static string BuildAssistantMessage(string publicCodexReport, ProjectIterationGoalSnapshot? goal)
    {
        return $"""
            {(goal is null ? "快速修复已完成。" : $"任务 {goal.GoalIndex} 修复已执行。")}
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
        var feedbackForLog = TrimForPromptExcerpt(feedback, FeedbackArtifactMaxChars);
        var stdoutForLog = TrimForPromptExcerpt(codexResult.Stdout, GeneratorStreamLogMaxChars);
        var stderrForLog = TrimForPromptExcerpt(codexResult.Stderr, GeneratorStreamLogMaxChars);
        var outputForLog = TrimForPromptExcerpt(codexOutput, GeneratorStreamLogMaxChars);
        return $"""
            # Prototype Quick Fix Result

            Project: {project.Name}
            ProjectId: {project.ProjectId}
            RunId: {runId}
            Model: {model}
            SkillMode: {SkillModeLabel(skillAction)}
            GeneratorExitCode: {codexResult.ExitCode}
            CompletedAtUtc: {completedAt}
            GoalRepairMode: {(goal is null ? "false" : "true")}
            GoalRepairStatus: {goalRepairOutcome?.GoalStatus}

            ## Submitted Feedback

            {feedbackForLog}

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

            ## Generator Stdout

            {stdoutForLog}

            ## Generator Stderr

            {stderrForLog}

            ## Generator Output

            {outputForLog}
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
        if (!GameTypeRouteProfiles.IsRpgProject(project))
        {
            return false;
        }

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);
        if (string.Equals(contract?.Kind, "jrpg-conflict-entry-trigger", StringComparison.Ordinal) ||
            string.Equals(contract?.Kind, "rpg-step2-encounter-trigger", StringComparison.Ordinal))
        {
            return true;
        }

        var goalText = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint).ToLowerInvariant();
        return goalText.Contains("conflict entry", StringComparison.Ordinal) ||
               goalText.Contains("encounter", StringComparison.Ordinal) ||
               goalText.Contains("first conflict", StringComparison.Ordinal) ||
               goalText.Contains("遇敌", StringComparison.Ordinal) ||
               goalText.Contains("遭遇", StringComparison.Ordinal);
    }

    private static string AppendAcceptanceValidationSummary(string assistantMessage, ProjectIterationGoalSnapshot goal)
    {
        return $"""
            {assistantMessage.Trim()}

            平台验收：
            任务 {goal.GoalIndex} 的最小玩法验收已通过。当前任务可以进入下一步。
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
        var publicDetails = BuildPublicAcceptanceValidationDetails(validation);
        return $"""
            {assistantMessage.Trim()}

            平台验收：
            任务 {goal.GoalIndex} 没有通过平台验收，当前任务仍保持需要修复。
            原因：{validation.Reason ?? validation.Status}
            细节：{publicDetails}
            """;
    }

    private static string AppendAcceptanceValidationNotRunFailure(
        string assistantMessage,
        ProjectIterationGoalSnapshot goal)
    {
        return $"""
            {assistantMessage.Trim()}

            平台验收：
            STATUS: needs_fix
            任务 {goal.GoalIndex} 还没有可用的平台玩法验收合同，当前任务仍保持需要修复。
            原因：platform_acceptance_not_run_for_rpg_goal
            细节：请先恢复或补齐当前 RPG/JRPG 任务可验证的合同、标记或验收文件，再报告完成。
            """;
    }

    private static string BuildPublicAcceptanceValidationDetails(PrototypeGoalAcceptanceValidationResult validation)
    {
        if (string.Equals(validation.Reason, "core_tests_failed", StringComparison.OrdinalIgnoreCase) &&
            IsCoreTestPackageReferenceFailure(validation))
        {
            return "核心测试项目缺少测试框架包引用。请优先修复 Game.Core.Tests 的 xunit、xunit.runner.visualstudio、FluentAssertions、Microsoft.NET.Test.Sdk 等 PackageReference，再继续玩法或 UI 修复。";
        }

        var sanitized = PublicChatSanitizer.Sanitize(validation.Details);
        return string.IsNullOrWhiteSpace(sanitized)
            ? "请根据当前平台验收原因修复对应阻塞项。"
            : sanitized;
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

    private static string AppendAcceptanceValidationNotRunEvidence(string codexOutput)
    {
        var prefix = string.IsNullOrWhiteSpace(codexOutput) ? "" : codexOutput.Trim() + Environment.NewLine + Environment.NewLine;
        return $"""
            {prefix}STATUS: needs_fix
            VERIFY: Platform acceptance validation did not run for the current RPG/JRPG gameplay goal.
            REASON: platform_acceptance_not_run_for_rpg_goal
            DETAILS: current RPG/JRPG goal needs a concrete platform acceptance contract before it can be marked completed
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

            平台引擎验收：
            任务 {goal.GoalIndex} 已通过 Godot smoke 验证。
            """;
    }

    private static string BuildValidatedGoalRepairSummary(ProjectIterationGoalSnapshot goal)
    {
        return $"""
            任务 {goal.GoalIndex} 修复已完成。

            平台验收：
            任务 {goal.GoalIndex} 的最小玩法验收已通过。

            平台引擎验收：
            任务 {goal.GoalIndex} 已通过 Godot smoke 验证。
            当前任务可以进入下一步。
            """;
    }

    private static string AppendGodotSmokeValidationFailure(
        string assistantMessage,
        PrototypeGoalGodotSmokeValidationResult validation)
    {
        return $"""
            {assistantMessage.Trim()}

            平台引擎验收：
            STATUS: needs_fix
            VERIFY: Godot smoke 验证未通过。
            REMAINING: 继续修复当前玩法任务，直到 Godot smoke 验证通过。
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
            {assistantMessage.Trim()}

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
        if (validation.AttemptedGdUnitPaths.Count > 0)
        {
            lines.Add($"GDUNIT_ATTEMPTED_PATHS: {string.Join(", ", validation.AttemptedGdUnitPaths)}");
        }

        if (string.Equals(validation.Reason, "rpg_gdunit_tests_missing", StringComparison.OrdinalIgnoreCase))
        {
            lines.Add($"GDUNIT_PATH_HINT: create or repair a project-specific suite under Tests.Godot/{validation.GdUnitPath ?? validation.AttemptedGdUnitPaths.FirstOrDefault() ?? "tests/Prototype/<PrototypeSuite>"}.");
        }

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
        var structuredStatus = ParseStructuredStatus(assistantMessage)
            ?? ParseStructuredStatus(codexOutput)
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
        var offTopicSource = string.Equals(structuredStatus, "completed", StringComparison.OrdinalIgnoreCase)
            ? codexOutput.ToLowerInvariant()
            : normalized;
        var offTopicMatched = HasOffTopicEvidence(offTopicSource) && !GoalAllowsInfraTerms(goal);
        if (string.Equals(structuredStatus, "completed", StringComparison.OrdinalIgnoreCase))
        {
            return offTopicMatched || !HasCompletionEvidence(assistantMessage, codexOutput)
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

    public static bool HasGoalRepairOffTopicEvidenceForTesting(string normalizedText)
    {
        return HasOffTopicEvidence(normalizedText.ToLowerInvariant());
    }

    public static string DetermineGoalRepairOutcomeStatusForTesting(
        ProjectIterationGoalSnapshot goal,
        string codexOutput,
        string stdout,
        string stderr)
    {
        return DetermineGoalRepairOutcome(goal, "", new HostedProcessResult(0, stdout, stderr), codexOutput).GoalStatus;
    }

    public static IReadOnlyList<string> ExtractGdUnitPromptSummaryForTesting(string consoleText, int maxLines)
    {
        return ExtractGdUnitPromptSummary(consoleText, maxLines);
    }

    private static bool HasOffTopicEvidence(string normalizedText)
    {
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
            "平台脚本",
            "启动脚本",
            "部署脚本",
            "工作流脚本",
            "安全测试"
        };

        return offTopicSignals.Any(marker => normalizedText.Contains(marker, StringComparison.Ordinal));
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
        var normalizedVerifyForBlocking = RemoveDeferredPlatformValidationNotes(normalizedVerify);
        var strongVerifyMarkers = new[]
        {
            "pass",
            "passed",
            "green",
            "all green",
            "confirmed",
            "verified",
            "static confirmation",
            "static check",
            "static inspection",
            "checked",
            "should show",
            "should see",
            "should become",
            "should be",
            "should remain",
            "应看到",
            "应显示",
            "应出现",
            "应重新可用",
            "应保持",
            "应变为",
            "no longer contains",
            "通过",
            "已确认",
            "已检查",
            "静态确认",
            "静态核对",
            "静态检查",
            "核对",
            "检查",
            "确认"
        };
        var hasStrongEvidence = strongVerifyMarkers.Any(marker => normalizedVerify.Contains(marker, StringComparison.Ordinal));
        return hasStrongEvidence && !HasBlockingEvidence(normalizedVerifyForBlocking);
    }

    private static string RemoveDeferredPlatformValidationNotes(string normalizedText)
    {
        var lines = normalizedText.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        return string.Join(
            "\n",
            lines.Where(static line =>
                !(line.Contains("未运行", StringComparison.Ordinal) &&
                  (line.Contains("引擎验证", StringComparison.Ordinal) ||
                   line.Contains("godot", StringComparison.Ordinal) ||
                   line.Contains("平台隔离复验", StringComparison.Ordinal)))));
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

    private static bool IsCompletionEvidenceRecoveryGoal(ProjectIterationGoalSnapshot goal)
    {
        var combined = string.Join(
            "\n",
            new[] { goal.Title, goal.Description, goal.AcceptanceHint }
                .Where(static value => !string.IsNullOrWhiteSpace(value)))
            .ToLowerInvariant();
        return combined.Contains("运行证据", StringComparison.Ordinal) ||
               combined.Contains("完成证据", StringComparison.Ordinal) ||
               combined.Contains("completion evidence", StringComparison.Ordinal) ||
               combined.Contains("completion artifacts", StringComparison.Ordinal) ||
               combined.Contains("prototype route can generate completion evidence", StringComparison.Ordinal);
    }

    private static string ResolveRecoveryPrototypeSpec(string repositoryRoot, JsonElement root, string slug)
    {
        var stateSpec = TryReadString(root, "prototype_spec");
        if (!string.IsNullOrWhiteSpace(stateSpec) &&
            File.Exists(Path.Combine(repositoryRoot, stateSpec.Replace('/', Path.DirectorySeparatorChar))))
        {
            return stateSpec;
        }

        var candidate = ToSlash(Path.Combine("docs", "prototypes", $"{PrototypeRecordWriter.SanitizeSlug(slug)}.prototype.json"));
        return File.Exists(Path.Combine(repositoryRoot, candidate.Replace('/', Path.DirectorySeparatorChar)))
            ? candidate
            : "";
    }

    private static string ResolveRecoverySlug(ProjectSnapshot project, JsonElement root, string? prototypeRecord, string? smokeScene)
    {
        var stateSlug = TryReadString(root, "slug");
        if (!string.IsNullOrWhiteSpace(stateSlug))
        {
            return PrototypeRecordWriter.SanitizeSlug(stateSlug);
        }

        if (!string.IsNullOrWhiteSpace(smokeScene))
        {
            var marker = "res://Game.Godot/Prototypes/";
            if (smokeScene.StartsWith(marker, StringComparison.OrdinalIgnoreCase))
            {
                var remainder = smokeScene[marker.Length..];
                var segment = remainder.Split('/', StringSplitOptions.RemoveEmptyEntries).FirstOrDefault();
                if (!string.IsNullOrWhiteSpace(segment))
                {
                    return PrototypeRecordWriter.SanitizeSlug(segment);
                }
            }
        }

        if (!string.IsNullOrWhiteSpace(prototypeRecord))
        {
            var fileName = Path.GetFileNameWithoutExtension(prototypeRecord);
            if (!string.IsNullOrWhiteSpace(fileName))
            {
                var parts = fileName.Split('-', StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length >= 4)
                {
                    return PrototypeRecordWriter.SanitizeSlug(string.Join('-', parts.Skip(3)));
                }

                return PrototypeRecordWriter.SanitizeSlug(fileName);
            }
        }

        return PrototypeRecordWriter.SanitizeSlug(FirstNonEmpty(project.GameName, project.Name, "prototype"));
    }

    private static bool TryResolveRecoveredCompletionEvidence(
        string repositoryRoot,
        string normalizedSlug,
        string expectedPrototypeRecord,
        string expectedPrototypeSpec,
        string expectedSmokeScene,
        JsonElement root,
        JsonElement completion,
        out int completedThroughDay,
        out object[] steps)
    {
        completedThroughDay = TryReadInt(completion, "completed_through_day");
        if (completedThroughDay < RecoveredWorkflowMaxDay)
        {
            steps = [];
            return false;
        }

        if (TryReadRecoveredWorkflowSteps(root, completion, out steps))
        {
            return true;
        }

        if (TryReadRecoveredWorkflowStepsFromCompletionEvidence(root, out steps))
        {
            return true;
        }

        return TryReadRecoveredWorkflowStepsFromActiveState(
            repositoryRoot,
            normalizedSlug,
            expectedPrototypeRecord,
            expectedPrototypeSpec,
            expectedSmokeScene,
            out steps);
    }

    private static bool TryReadRecoveredWorkflowSteps(JsonElement root, JsonElement completion, out object[] steps)
    {
        steps = [];
        if (!TryGetWorkflowStepsArray(completion, out var stepsElement) &&
            !TryGetWorkflowStepsArray(root, out stepsElement))
        {
            return false;
        }

        return TryNormalizeRecoveredWorkflowSteps(stepsElement, out steps);
    }

    private static bool TryReadRecoveredWorkflowStepsFromCompletionEvidence(JsonElement root, out object[] steps)
    {
        steps = [];
        if (!root.TryGetProperty("completion_evidence", out var evidence) ||
            evidence.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        var recoveredSteps = new List<object>();
        for (var day = 1; day <= RecoveredWorkflowMaxDay; day++)
        {
            if (!evidence.TryGetProperty($"day_{day}", out var step) ||
                step.ValueKind != JsonValueKind.Object)
            {
                return false;
            }

            var status = TryReadString(step, "status") ?? "";
            if (!IsAcceptableRecoveredWorkflowStep(day, status, step))
            {
                return false;
            }

            recoveredSteps.Add(new
            {
                day,
                title = FirstNonEmpty(TryReadString(step, "title"), $"Recovered workflow step {day:00}"),
                status,
                reason = TryReadString(step, "reason"),
                record = TryReadString(step, "record"),
                prototype_spec = TryReadString(step, "prototype_spec")
            });
        }

        steps = recoveredSteps.ToArray();
        return true;
    }

    private static bool TryReadRecoveredWorkflowStepsFromActiveState(
        string repositoryRoot,
        string normalizedSlug,
        string expectedPrototypeRecord,
        string expectedPrototypeSpec,
        string expectedSmokeScene,
        out object[] steps)
    {
        steps = [];
        var activeStatePath = Path.Combine(repositoryRoot, "logs", "ci", "active-prototypes", $"{normalizedSlug}.active.json");
        if (!File.Exists(activeStatePath))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(activeStatePath, Encoding.UTF8));
            var root = document.RootElement;
            var status = TryReadString(root, "status");
            var completedThroughDay = TryReadInt(root, "completed_through_day");
            if (!string.Equals(status, "completed-through-day", StringComparison.OrdinalIgnoreCase) ||
                completedThroughDay < RecoveredWorkflowMaxDay)
            {
                return false;
            }

            if (!ActiveStateMatchesRecoveryEvidence(repositoryRoot, root, expectedPrototypeRecord, expectedPrototypeSpec, expectedSmokeScene))
            {
                return false;
            }

            return TryGetWorkflowStepsArray(root, out var stepsElement) &&
                   TryNormalizeRecoveredWorkflowSteps(stepsElement, out steps);
        }
        catch (JsonException)
        {
            return false;
        }
        catch (IOException)
        {
            return false;
        }
    }

    private static bool ActiveStateMatchesRecoveryEvidence(
        string repositoryRoot,
        JsonElement activeRoot,
        string expectedPrototypeRecord,
        string expectedPrototypeSpec,
        string expectedSmokeScene)
    {
        var activePrototypeRecord = TryReadString(activeRoot, "prototype_file");
        var activePrototypeSpec = TryReadString(activeRoot, "prototype_spec");
        if (!SameSlashPath(activePrototypeRecord, expectedPrototypeRecord) ||
            !SameSlashPath(activePrototypeSpec, expectedPrototypeSpec))
        {
            return false;
        }

        return TryResolveActiveStateSmokeScene(repositoryRoot, activeRoot, activePrototypeSpec!, out var activeSmokeScene) &&
               SameSlashPath(activeSmokeScene, expectedSmokeScene);
    }

    private static bool TryResolveActiveStateSmokeScene(string repositoryRoot, JsonElement activeRoot, string activePrototypeSpec, out string smokeScene)
    {
        smokeScene = FirstNonEmpty(TryReadString(activeRoot, "smoke_scene"), TryReadString(activeRoot, "default_scene"));
        if (!string.IsNullOrWhiteSpace(smokeScene))
        {
            return true;
        }

        var packagingSummary = TryReadString(activeRoot, "packaging_summary");
        if (!string.IsNullOrWhiteSpace(packagingSummary))
        {
            var packagingPath = Path.Combine(repositoryRoot, packagingSummary.Replace('/', Path.DirectorySeparatorChar));
            if (File.Exists(packagingPath))
            {
                try
                {
                    using var document = JsonDocument.Parse(File.ReadAllText(packagingPath, Encoding.UTF8));
                    smokeScene = TryReadString(document.RootElement, "default_scene") ?? "";
                    if (!string.IsNullOrWhiteSpace(smokeScene))
                    {
                        return true;
                    }
                }
                catch (JsonException)
                {
                    smokeScene = "";
                }
                catch (IOException)
                {
                    smokeScene = "";
                }
            }
        }

        return TryResolvePrototypeSpecSmokeScene(repositoryRoot, activePrototypeSpec, out smokeScene);
    }

    private static bool TryResolvePrototypeSpecSmokeScene(string repositoryRoot, string prototypeSpec, out string smokeScene)
    {
        smokeScene = "";
        var prototypeSpecPath = Path.Combine(repositoryRoot, prototypeSpec.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(prototypeSpecPath))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(prototypeSpecPath, Encoding.UTF8));
            var root = document.RootElement;
            if (!root.TryGetProperty("prototype_type_kit", out var typeKit) || typeKit.ValueKind != JsonValueKind.Object ||
                !typeKit.TryGetProperty("manifest", out var manifest) || manifest.ValueKind != JsonValueKind.Object)
            {
                return false;
            }

            smokeScene = TryReadString(manifest, "default_scene") ?? "";
            if (string.IsNullOrWhiteSpace(smokeScene) &&
                manifest.TryGetProperty("paths", out var paths) &&
                paths.ValueKind == JsonValueKind.Object)
            {
                smokeScene = TryReadString(paths, "default_scene") ?? "";
            }

            return !string.IsNullOrWhiteSpace(smokeScene);
        }
        catch (JsonException)
        {
            return false;
        }
        catch (IOException)
        {
            return false;
        }
    }

    private static bool SameSlashPath(string? left, string? right)
    {
        return !string.IsNullOrWhiteSpace(left) &&
               !string.IsNullOrWhiteSpace(right) &&
               string.Equals(ToSlash(left.Trim()), ToSlash(right.Trim()), StringComparison.OrdinalIgnoreCase);
    }

    private static bool TryNormalizeRecoveredWorkflowSteps(JsonElement stepsElement, out object[] steps)
    {
        steps = [];
        var stepsByDay = new Dictionary<int, JsonElement>();
        foreach (var step in stepsElement.EnumerateArray())
        {
            if (!step.TryGetProperty("day", out var dayElement) ||
                dayElement.ValueKind != JsonValueKind.Number ||
                !dayElement.TryGetInt32(out var day) ||
                day < 1 ||
                day > RecoveredWorkflowMaxDay)
            {
                continue;
            }

            stepsByDay[day] = step.Clone();
        }

        var recoveredSteps = new List<object>();
        for (var day = 1; day <= RecoveredWorkflowMaxDay; day++)
        {
            if (!stepsByDay.TryGetValue(day, out var step))
            {
                return false;
            }

            var status = TryReadString(step, "status") ?? "";
            if (!IsAcceptableRecoveredWorkflowStep(day, status, step))
            {
                return false;
            }

            recoveredSteps.Add(new
            {
                day,
                title = FirstNonEmpty(TryReadString(step, "title"), $"Recovered workflow step {day:00}"),
                status,
                reason = TryReadString(step, "reason"),
                record = TryReadString(step, "record"),
                prototype_spec = TryReadString(step, "prototype_spec")
            });
        }

        steps = recoveredSteps.ToArray();
        return true;
    }

    private static bool TryGetWorkflowStepsArray(JsonElement root, out JsonElement stepsElement)
    {
        if (root.TryGetProperty("steps_run", out stepsElement) && stepsElement.ValueKind == JsonValueKind.Array)
        {
            return true;
        }

        if (root.TryGetProperty("steps_completed", out stepsElement) && stepsElement.ValueKind == JsonValueKind.Array)
        {
            return true;
        }

        stepsElement = default;
        return false;
    }

    private static bool IsAcceptableRecoveredWorkflowStep(int day, string status, JsonElement step)
    {
        if (string.Equals(status, "ok", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        if (string.Equals(status, "completed", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(status, "succeeded", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        if (day == 2 && string.Equals(status, "skipped", StringComparison.OrdinalIgnoreCase))
        {
            return string.Equals(TryReadString(step, "reason"), "prototype_scaffold_already_exists", StringComparison.OrdinalIgnoreCase);
        }

        if ((day == 3 || day == 4) && string.Equals(status, "skipped", StringComparison.OrdinalIgnoreCase))
        {
            return string.Equals(TryReadString(step, "reason"), "existing_project_specific_prototype_ready_for_green", StringComparison.OrdinalIgnoreCase);
        }

        return false;
    }

    private static bool PrototypeSceneExists(string repositoryRoot, string scene)
    {
        return TryResolvePrototypeScenePath(repositoryRoot, scene, out _, out var fullPath) && IsValidGodotSceneFile(fullPath);
    }

    private static bool TryResolvePrototypeScenePath(string repositoryRoot, string scene, out string relativePath, out string fullPath)
    {
        relativePath = "";
        fullPath = "";
        if (string.IsNullOrWhiteSpace(scene) || !scene.StartsWith("res://", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        relativePath = scene["res://".Length..].Replace('/', Path.DirectorySeparatorChar);
        fullPath = Path.Combine(repositoryRoot, relativePath);
        return true;
    }

    private static bool IsValidGodotSceneFile(string fullPath)
    {
        return PrototypeGodotSmokeService.HasValidGodotScenePrefix(fullPath);
    }

    private static string AppendCompletionRecoveryEvidence(string codexOutput, string recoveryEvidence)
    {
        if (string.IsNullOrWhiteSpace(recoveryEvidence))
        {
            return codexOutput;
        }

        return string.IsNullOrWhiteSpace(codexOutput)
            ? recoveryEvidence
            : $"{codexOutput}{Environment.NewLine}{recoveryEvidence}";
    }

    private static string? TryReadString(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var element) && element.ValueKind == JsonValueKind.String
            ? element.GetString()
            : null;
    }

    private static int TryReadInt(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var element) && element.ValueKind == JsonValueKind.Number
            ? element.GetInt32()
            : 0;
    }

    private static bool TryReadBool(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var element) &&
               (element.ValueKind == JsonValueKind.True || element.ValueKind == JsonValueKind.False) &&
               element.GetBoolean();
    }

    private static bool JsonArrayContains(JsonElement root, string propertyName, string expectedValue)
    {
        if (!root.TryGetProperty(propertyName, out var element) || element.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        foreach (var item in element.EnumerateArray())
        {
            if (item.ValueKind == JsonValueKind.String &&
                string.Equals(item.GetString(), expectedValue, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
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

    private static string BuildGoalMemoryScope(int goalIndex)
    {
        return $"goal-repair-step-{goalIndex}";
    }

    private async Task UpsertGoalRunMemoryAsync(
        ProjectSnapshot project,
        ProjectIterationGoalSnapshot goal,
        string status,
        string nextRecommendedAction,
        string lastRunOutcome,
        IReadOnlyList<string> blockers,
        IReadOnlyList<string>? allowedScopeOverride,
        CancellationToken cancellationToken)
    {
        var completed = status == "succeeded"
            ? JsonSerializer.Serialize(new[] { goal.Title })
            : "[]";
        var blockersJson = JsonSerializer.Serialize(blockers);
        var allowedScope = allowedScopeOverride is { Count: > 0 }
            ? allowedScopeOverride
            : await ResolveGoalAllowedScopeAsync(project, goal, cancellationToken);
        var allowedScopeJson = JsonSerializer.Serialize(allowedScope);
        await _metadataStore.UpsertProjectRunMemoryAsync(
            project.ProjectId,
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

    private static string BuildFocusedWorkspaceScopeText(IReadOnlyList<string> focusedWorkspaceDirectories)
    {
        return focusedWorkspaceDirectories.Count == 0
            ? "当前项目工作区"
            : string.Join("、", focusedWorkspaceDirectories.Select(FormatFocusedWorkspaceScopePath));
    }

    private static string FormatFocusedWorkspaceScopePath(string path)
    {
        return FocusedWorkspaceRootFiles.Contains(path, StringComparer.OrdinalIgnoreCase)
            ? path
            : $"{path}/**";
    }

    private async Task<ExecutionWorkspace> PrepareExecutionWorkspaceAsync(
        ProjectSnapshot project,
        ProjectIterationGoalSnapshot? goal,
        PrototypeGoalAcceptanceValidationResult currentAcceptanceValidation,
        string runId,
        string fallbackCodexOutputPath,
        CancellationToken cancellationToken)
    {
        if (!ShouldUseFocusedWorkspace(project, goal))
        {
            return new ExecutionWorkspace(project.RepoPath, CreateShortRuntimeOutputPath(runId), false, [], []);
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
        var writableRootFiles = ResolveFocusedWorkspaceWritableRootFiles(project, goal, currentAcceptanceValidation);

        var activeSmokeScene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            _metadataStore,
            project,
            _stateWriter,
            goal?.GoalIndex,
            cancellationToken,
            sessionId: goal?.SessionId,
            goal: goal,
            allowMissingGoalStateScene: true,
            allowBaselineFallbackForGoalContext: true);
        var managedDirectories = ResolveFocusedWorkspaceDirectories(project, activeSmokeScene, goal);
        AddFocusedRouteStateTestDirectories(project, managedDirectories, goal);
        foreach (var relativeDirectory in managedDirectories)
        {
            CopyRelativeDirectoryIfExists(project.RepoPath, focusedRoot, relativeDirectory);
        }

        var codexOutputPath = Path.Combine(focusedRoot, ".phasea", "codex-output.txt");
        Directory.CreateDirectory(Path.GetDirectoryName(codexOutputPath)!);
        return new ExecutionWorkspace(focusedRoot, codexOutputPath, true, managedDirectories, managedDirectories.Concat(writableRootFiles).ToArray());
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
               GameTypeRouteProfiles.IsRpgProject(project);
    }

    private static IReadOnlyList<string> ResolveFocusedWorkspaceWritableRootFiles(
        ProjectSnapshot project,
        ProjectIterationGoalSnapshot? goal,
        PrototypeGoalAcceptanceValidationResult currentAcceptanceValidation)
    {
        if (goal is null)
        {
            return [];
        }

        var files = new List<string>();
        if (ShouldIncludeProjectGodotRootFile(project, goal, currentAcceptanceValidation))
        {
            AddUnique(files, "project.godot");
        }

        if (AllowsBuildRootFileRepair(currentAcceptanceValidation))
        {
            AddUnique(files, "Game.sln");
            AddUnique(files, "GodotGame.sln");
            AddUnique(files, "GodotGame.csproj");
            AddUnique(files, "Directory.Build.props");
            AddUnique(files, "Directory.Build.targets");
            AddUnique(files, "packages.lock.json");
        }

        return files;
    }

    private static bool ShouldIncludeProjectGodotRootFile(
        ProjectSnapshot project,
        ProjectIterationGoalSnapshot goal,
        PrototypeGoalAcceptanceValidationResult currentAcceptanceValidation)
    {
        if (ShouldIncludeHostSceneDirectory(project, goal))
        {
            return true;
        }

        if (string.Equals(currentAcceptanceValidation.Reason, "main_scene_default_ui_not_hidden", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        var text = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint);
        return ContainsAny(text, "project.godot", "run/main_scene");
    }

    private static bool AllowsBuildRootFileRepair(PrototypeGoalAcceptanceValidationResult currentAcceptanceValidation)
    {
        return IsCoreTestFailure(currentAcceptanceValidation) ||
               ContainsAny(
                   string.Join(" ", currentAcceptanceValidation.Reason, currentAcceptanceValidation.Details),
                   "MSBuildProjectExtensionsPath",
                   "Directory.Build.props",
                   "Directory.Build.targets",
                   "GodotGame.csproj",
                   "CS0246",
                   "PackageReference");
    }

    private static void SyncFocusedWorkspaceBack(ExecutionWorkspace workspace, string projectRepoPath)
    {
        foreach (var relativePath in workspace.ManagedPaths)
        {
            var sourcePath = Path.Combine(workspace.RootPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
            var targetPath = Path.Combine(projectRepoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
            if (Directory.Exists(sourcePath))
            {
                MirrorDirectoryContents(sourcePath, targetPath);
                continue;
            }

            if (File.Exists(sourcePath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(targetPath)!);
                File.Copy(sourcePath, targetPath, overwrite: true);
                continue;
            }

            // Missing managed roots are ignored. File-level deletes inside an existing managed
            // directory are still mirrored by MirrorDirectoryContents, but a transient workspace
            // omission must not remove an entire source-tree directory.
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

    private static void MirrorDirectoryContents(string sourceDirectory, string targetDirectory)
    {
        Directory.CreateDirectory(targetDirectory);
        foreach (var file in Directory.EnumerateFiles(targetDirectory, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(targetDirectory, file);
            if (!File.Exists(Path.Combine(sourceDirectory, relative)))
            {
                File.Delete(file);
            }
        }

        foreach (var directory in Directory.EnumerateDirectories(targetDirectory, "*", SearchOption.AllDirectories)
                     .OrderByDescending(path => path.Length))
        {
            var relative = Path.GetRelativePath(targetDirectory, directory);
            if (!Directory.Exists(Path.Combine(sourceDirectory, relative)) &&
                !Directory.EnumerateFileSystemEntries(directory).Any())
            {
                Directory.Delete(directory);
            }
        }

        CopyDirectoryContents(sourceDirectory, targetDirectory);
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

    private static List<string> ResolveFocusedWorkspaceDirectories(ProjectSnapshot project, string? activeSmokeScene, ProjectIterationGoalSnapshot? goal)
    {
        var directories = new List<string>(FocusedWorkspaceBaseDirectories);
        if (ShouldIncludeHostSceneDirectory(project, goal))
        {
            AddUnique(directories, "Game.Godot/Scenes");
        }

        var prototypeDirectory = TryResolvePrototypeDirectory(activeSmokeScene);
        if (!string.IsNullOrWhiteSpace(prototypeDirectory))
        {
            AddUnique(directories, prototypeDirectory);
            AddFocusedPrototypeTestDirectories(project.RepoPath, directories, prototypeDirectory);
        }

        return directories;
    }

    private async Task<IReadOnlyList<string>> ResolveGoalAllowedScopeAsync(
        ProjectSnapshot project,
        ProjectIterationGoalSnapshot goal,
        CancellationToken cancellationToken)
    {
        if (!ShouldUseFocusedWorkspace(project, goal))
        {
            return [];
        }

        var activeSmokeScene = await PrototypeSmokeSceneResolver.ResolveLatestAsync(
            _metadataStore,
            project,
            _stateWriter,
            goal.GoalIndex,
            cancellationToken,
            sessionId: goal.SessionId,
            goal: goal,
            allowMissingGoalStateScene: true,
            allowBaselineFallbackForGoalContext: true);
        var directories = ResolveFocusedWorkspaceDirectories(project, activeSmokeScene, goal);
        AddFocusedRouteStateTestDirectories(project, directories, goal);
        return directories;
    }

    private void AddFocusedRouteStateTestDirectories(ProjectSnapshot project, List<string> directories, ProjectIterationGoalSnapshot? goal)
    {
        if (goal is null)
        {
            return;
        }

        foreach (var gdUnitPath in PrototypeGdUnitPathResolver.ExtractManagedDirectoriesFromRouteStates(SelectCurrentRouteStates(project, goal)))
        {
            AddUnique(directories, gdUnitPath);
        }
    }

    private static bool ShouldIncludeHostSceneDirectory(ProjectSnapshot project, ProjectIterationGoalSnapshot? goal)
    {
        if (goal is null)
        {
            return false;
        }

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);
        if (contract?.MainSceneHostUiHiddenAcceptance == true)
        {
            return true;
        }

        var text = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint);
        return ContainsAny(text, "Main.tscn", "main scene", "host ui", "host scene");
    }

    private IReadOnlyList<string> SelectCurrentRouteStates(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        return PrototypeRouteStateSelection.SelectCurrentRouteStates(
            _stateWriter.ReadLatestNeedsFixState(project, goal.GoalIndex),
            _stateWriter.ReadLatestExecuteNextGoalState(project, goal.GoalIndex),
            goal.SessionId,
            goal);
    }

    private static string? TryResolvePrototypeDirectory(string? scene)
    {
        const string prefix = "res://Game.Godot/Prototypes/";
        if (string.IsNullOrWhiteSpace(scene) ||
            !scene.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var remainder = scene[prefix.Length..].Replace('\\', '/');
        var slashIndex = remainder.IndexOf('/', StringComparison.Ordinal);
        if (slashIndex <= 0)
        {
            return null;
        }

        var slug = remainder[..slashIndex];
        return string.IsNullOrWhiteSpace(slug) ? null : $"Game.Godot/Prototypes/{slug}";
    }

    private static void AddFocusedPrototypeTestDirectories(string repoPath, List<string> directories, string prototypeDirectory)
    {
        var slug = prototypeDirectory.Split('/').LastOrDefault();
        if (string.IsNullOrWhiteSpace(slug))
        {
            return;
        }

        var pascalSlug = ToPascalCase(slug);
        foreach (var candidate in new[]
                 {
                     $"Tests.Godot/tests/Prototype/{slug}",
                     $"Tests.Godot/tests/Prototype/{pascalSlug}",
                     $"Tests.Godot/tests/Prototype/{pascalSlug}Prototype"
                 })
        {
            AddUnique(directories, candidate);
        }

        var testsRoot = Path.Combine(repoPath, "Tests.Godot", "tests", "Prototype");
        if (!Directory.Exists(testsRoot))
        {
            return;
        }

        var normalizedSlug = NormalizeDirectoryToken(slug);
        var normalizedPascalSlug = NormalizeDirectoryToken(pascalSlug);
        foreach (var directory in Directory.EnumerateDirectories(testsRoot))
        {
            var name = Path.GetFileName(directory);
            var normalizedName = NormalizeDirectoryToken(name);
            if (normalizedName == normalizedSlug ||
                normalizedName == normalizedPascalSlug ||
                normalizedName == $"{normalizedPascalSlug}prototype")
            {
                AddUnique(directories, $"Tests.Godot/tests/Prototype/{name}");
            }
        }
    }

    private static string ToPascalCase(string value)
    {
        var parts = value.Split(['-', '_', ' '], StringSplitOptions.RemoveEmptyEntries);
        return string.Concat(parts.Select(part => char.ToUpperInvariant(part[0]) + part[1..]));
    }

    private static string NormalizeDirectoryToken(string value)
    {
        return new string(value.Where(char.IsLetterOrDigit).Select(char.ToLowerInvariant).ToArray());
    }

    private static void AddUnique(List<string> values, string value)
    {
        if (!values.Contains(value, StringComparer.OrdinalIgnoreCase))
        {
            values.Add(value);
        }
    }

    private static readonly string[] FocusedWorkspaceBaseDirectories =
    [
        "Game.Godot/Scripts/Prototypes",
        "Game.Core/Prototypes",
        "Game.Core.Tests/Prototypes"
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
    private sealed record ExecutionWorkspace(string RootPath, string CodexOutputPath, bool SyncBack, IReadOnlyList<string> ManagedDirectories, IReadOnlyList<string> ManagedPaths);
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
