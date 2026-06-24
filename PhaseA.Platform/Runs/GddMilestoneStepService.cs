using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;

namespace PhaseA.Platform.Runs;

public sealed class GddMilestoneStepService
{
    private const string GddRelativePath = "docs/gdd/GDD.md";
    private const string OutlineRelativePath = "docs/gdd/gdd-outline.json";
    private const string StateRelativePath = "routes/gdd-milestones/latest.json";
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true
    };

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PrototypeIterationGoalService _iterationGoalService;
    private readonly PrototypeNeedsFixRouteService _needsFixRouteService;
    private readonly PrototypeEngineeringClosureService _engineeringClosure;
    private readonly IPrototypeLightweightValidationService? _lightweightValidationService;
    private readonly ILlmRouteEngine? _llmRouteEngine;

    public GddMilestoneStepService(
        PhaseAMetadataStore metadataStore,
        PrototypeIterationGoalService iterationGoalService,
        PrototypeNeedsFixRouteService needsFixRouteService,
        ILlmRouteEngine? llmRouteEngine = null,
        IPrototypeLightweightValidationService? lightweightValidationService = null,
        PrototypeEngineeringClosureService? engineeringClosure = null)
    {
        _metadataStore = metadataStore;
        _iterationGoalService = iterationGoalService;
        _needsFixRouteService = needsFixRouteService;
        _engineeringClosure = engineeringClosure ?? new PrototypeEngineeringClosureService();
        _lightweightValidationService = lightweightValidationService;
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

        _engineeringClosure.EnsureProjectFiles(project);
        await ReconcileUnstartedStateWithGddAsync(project, state, cancellationToken);
        await ReconcileAdditionalStepsFromGddAsync(project, state, cancellationToken);
        await RefreshOutlineCompletionAsync(project, state, cancellationToken);
        NormalizeState(state);
        await ReconcilePrototypeSkeletonM1Async(project, state, cancellationToken);
        await ReconcileLatestGddMilestoneSessionAsync(project, state, cancellationToken);
        await ReconcileCompletedMilestoneExecutionsAsync(project, state, cancellationToken);
        await WriteStateAsync(project, state, cancellationToken);
        await WriteSpecFilesAsync(project, state, cancellationToken);
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
        await WriteSpecFilesAsync(project, state, cancellationToken);
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

            {PrototypeGameplayPromptGuards.BuildCombatPressureGuardPromptBlock()}

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
        var routeSummary = FirstNonEmpty(result.Summary, feedback);
        var outcome = new GddMilestoneStepValidationOutcome(
            completed ? "feedback_submitted" : needsFix ? "needs_fix" : "feedback_failed",
            routeSummary,
            null,
            null);
        if (completed)
        {
            var validation = await ValidateAndAutoRepairStepAsync(accountId, project, step, session, request.Model, cancellationToken);
            outcome = BuildStepValidationOutcome("feedback_submitted", feedback, validation);
        }

        var feedbackEvidencePath = string.IsNullOrWhiteSpace(result.RunId)
            ? step.LatestEvidenceRelativePath
            : (await WriteStepEvidenceAsync(project, result.RunId, "feedback-repair", outcome.Status, step.StepId, outcome.LastRepairRun is null ? 0 : 1, outcome.LightweightValidationRun, cancellationToken)).RelativePath;
        await _engineeringClosure.TouchMemoryAsync(project, "feedback-repair", FirstNonEmpty(result.RunId, outcome.LastRepairRun?.RunId, "unknown"), outcome.Status, step.StepId, cancellationToken);

        var latestRepairRunId = FirstNonEmpty(outcome.LastRepairRun?.RunId, result.RunId, step.FeedbackRunId);
        state.Steps[index] = step with
        {
            Status = outcome.Status,
            IterationSessionId = session.Session.SessionId,
            ExecutionSummary = outcome.Summary,
            ExecutionRunId = FirstNonEmpty(latestRepairRunId, step.ExecutionRunId),
            FeedbackSummary = outcome.Summary,
            FeedbackRunId = latestRepairRunId,
            LatestEvidenceRelativePath = feedbackEvidencePath
        };
        state.Summary = BuildStepActionSummary(step, "feedback", completed, outcome.Status, result.Status);
        await WriteStateAsync(project, state, CancellationToken.None);
        await WriteSpecFilesAsync(project, state, CancellationToken.None);

        return new GddMilestoneStepActionResult(project.ProjectId, step.StepId, result.Status, state.Summary, ToResult(project.ProjectId, state), NeedsFixRun: outcome.LastRepairRun ?? result);
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
        await ReconcileAdditionalStepsFromGddAsync(project, state, cancellationToken);
        await RefreshOutlineCompletionAsync(project, state, cancellationToken);
        if (state.IncompleteOutlineSections.Count > 0)
        {
            await WriteStateAsync(project, state, CancellationToken.None);
            return new GddMilestoneStepActionResult(
                project.ProjectId,
                state.CurrentStepId ?? "",
                "outline_incomplete",
                $"请先补全所有策划大纲章节后再执行当前模块。未补全：{string.Join("、", state.IncompleteOutlineSections.Take(5))}",
                ToResult(project.ProjectId, state),
                FailureCode: "outline_incomplete");
        }

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
        await WriteSpecFilesAsync(project, state, CancellationToken.None);

        var execution = await _iterationGoalService.ExecuteNextAsync(accountId, project.ProjectId, cancellationToken);
        var succeeded = await IsMilestoneStepExecutionCompleteAsync(project, execution, cancellationToken);
        if (succeeded)
        {
            await MarkMilestoneExecutionCompletedAsync(project.ProjectId, execution, state, step, cancellationToken);
        }

        var needsFix = execution.Status is "needs_fix" or "failed" or "project_busy" or "prototype_required";
        var outcome = new GddMilestoneStepValidationOutcome(
            succeeded ? "executed" : needsFix ? "needs_fix" : "execution_failed",
            execution.Summary,
            null,
            null);
        if (index >= 0)
        {
            if (succeeded)
            {
                var validation = await ValidateAndAutoRepairStepAsync(accountId, project, step, session, requestModel: null, cancellationToken);
                outcome = BuildStepValidationOutcome("executed", execution.Summary, validation);
            }

            var executionEvidencePath = string.IsNullOrWhiteSpace(execution.RunId)
                ? state.Steps[index].LatestEvidenceRelativePath
                : (await WriteStepEvidenceAsync(project, execution.RunId, "module-execute", outcome.Status, step.StepId, outcome.LastRepairRun is null ? 0 : 1, outcome.LightweightValidationRun, cancellationToken)).RelativePath;
            await _engineeringClosure.TouchMemoryAsync(project, "module-execute", FirstNonEmpty(execution.RunId, outcome.LastRepairRun?.RunId, "unknown"), outcome.Status, step.StepId, cancellationToken);

            state.Steps[index] = state.Steps[index] with
            {
                Status = outcome.Status,
                IterationSessionId = string.IsNullOrWhiteSpace(execution.SessionId) ? session.Session.SessionId : execution.SessionId,
                ExecutionRunId = string.IsNullOrWhiteSpace(execution.RunId) ? state.Steps[index].ExecutionRunId : execution.RunId,
                ExecutionSummary = outcome.Summary,
                FeedbackRunId = string.IsNullOrWhiteSpace(outcome.LastRepairRun?.RunId) ? state.Steps[index].FeedbackRunId : outcome.LastRepairRun.RunId,
                LatestEvidenceRelativePath = executionEvidencePath
            };
            state.Summary = BuildStepActionSummary(step, "execution", succeeded, outcome.Status, execution.Summary);
            await WriteStateAsync(project, state, CancellationToken.None);
            await WriteSpecFilesAsync(project, state, CancellationToken.None);
        }

        return new GddMilestoneStepActionResult(project.ProjectId, step.StepId, execution.Status, state.Summary, ToResult(project.ProjectId, state), StepExecution: execution, NeedsFixRun: outcome.LastRepairRun);
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
        var specPath = StepSpecRelativePath(step);
        return $"""
            GDD milestone step execution.

            Current milestone spec file:
            {specPath}

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

            {PrototypeGameplayPromptGuards.BuildCombatPressureGuardPromptBlock()}

            Feedback Improvement Run:
            {step.FeedbackGuidance}

            Next Step Adjustment Check:
            {step.NextStepReview}

            Required context:
            - Read docs/gdd/GDD.md.
            - Read docs/prototype-v1-plan.md when it exists.
            - Read {specPath} as the current step's implementation contract.
            - Read docs/prototype/STRUCTURE.md, docs/prototype/MEMORY.md, and docs/prototype/ASSETS.md before editing. Update them only when the current module changes stable scene/script/input/collision/asset facts.
            - Read docs/prototypes/ records for earlier completed milestone notes when relevant.

            Implement only this current milestone step as one playable milestone. Do not split it into multiple player-visible tasks and do not advance later locked steps.
            Add or update a current-module smoke/assertion path that proves the module's playable contract, and make the route evidence able to point at that check.
            """;
    }

    private static string BuildStepGoalDescription(GddMilestoneStepState step)
    {
        var specPath = StepSpecRelativePath(step);
        return $"""
            Implement {step.StepId} as one diablolike-style playable milestone.

            Current milestone spec:
            {specPath}

            Goal:
            {step.Description}

            Scope in:
            {step.ScopeIn}

            Scope out:
            {step.ScopeOut}

            Runtime slice:
            {step.GodotSlice}

            Before editing, read the current milestone spec file and treat it as authoritative over generic prototype-route defaults.
            Required module smoke: add or update a focused smoke/assertion for {step.StepId} that covers the player-visible contract, and keep it scoped to this module.
            """;
    }

    private static string BuildStepAcceptanceHint(GddMilestoneStepState step)
    {
        return $"""
            Acceptance:
            {step.Acceptance}

            Player package validation:
            {step.PackagingValidation}

            Module smoke evidence:
            Add or update one focused current-module smoke/assertion and keep its path stable enough for logs/prototype-evidence to reference it.

            After implementation, the browser should recommend that the player package, download, and validate this module before confirming completion. Do not require package download as a completion gate.
            """;
    }

    private async Task<bool> IsMilestoneStepExecutionCompleteAsync(
        ProjectSnapshot project,
        PrototypeIterationGoalExecutionResult execution,
        CancellationToken cancellationToken)
    {
        if (execution.Status is "completed" or "succeeded")
        {
            return true;
        }

        if (!string.Equals(execution.Status, "needs_fix", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        var run = string.IsNullOrWhiteSpace(execution.RunId)
            ? null
            : await _metadataStore.GetRunSnapshotAsync(execution.RunId, cancellationToken);
        if (run is null)
        {
            return false;
        }

        if (!string.Equals(run.Status, "completed", StringComparison.OrdinalIgnoreCase) ||
            run.ExitCode is not 0)
        {
            return false;
        }

        var output = string.Join("\n", run.StdoutText, ReadRunEvidenceText(project, run, "codex_output"));
        return ContainsStructuredValue(output, "STATUS", "completed") &&
               ContainsStructuredValue(output, "REMAINING", "none");
    }

    private async Task<GddMilestoneLightweightValidationResult> ValidateAndAutoRepairStepAsync(
        string accountId,
        ProjectSnapshot project,
        GddMilestoneStepState step,
        ProjectIterationSessionDetails session,
        string? requestModel,
        CancellationToken cancellationToken)
    {
        if (_lightweightValidationService is null)
        {
            return new GddMilestoneLightweightValidationResult(true, "未配置轻量验收服务，已保留模块执行结果。", null, null);
        }

        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromMinutes(20));
        var loopToken = timeout.Token;
        var stopwatch = Stopwatch.StartNew();
        try
        {
            var validation = await _lightweightValidationService.ValidateAsync(accountId, project.ProjectId, loopToken);
            if (IsLightweightValidationPassed(validation))
            {
                return new GddMilestoneLightweightValidationResult(true, $"{step.StepId} 轻量验收已通过。", null, validation);
            }

            var goal = session.Goals.FirstOrDefault(goal => goal.GoalIndex == step.StepIndex) ?? session.Goals.FirstOrDefault();
            if (goal is null)
            {
                return new GddMilestoneLightweightValidationResult(false, $"{step.StepId} 轻量验收失败，且当前模块缺少可修复目标。请提交反馈并修正模块。", null, validation);
            }

            PrototypeNeedsFixRouteResult? lastRepair = null;
            var failures = new List<string> { BuildValidationFailureSummary(validation) };
            for (var attempt = 1; attempt <= 3; attempt++)
            {
                if (stopwatch.Elapsed >= TimeSpan.FromMinutes(20))
                {
                    break;
                }

                var feedback = BuildAutomaticValidationRepairFeedback(step, validation, attempt);
                await _metadataStore.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "needs_fix", feedback, null, loopToken);
                await _metadataStore.UpdateProjectIterationSessionStatusAsync(session.Session.SessionId, "needs_fix", goal.GoalIndex, feedback, session.Session.LatestEvaluationJson, null, loopToken);

                lastRepair = await _needsFixRouteService.RunAsync(
                    accountId,
                    project.ProjectId,
                    new PrototypeNeedsFixRouteRequest(feedback, requestModel, null, goal.GoalId, goal.GoalIndex),
                    loopToken);

                if (stopwatch.Elapsed >= TimeSpan.FromMinutes(20))
                {
                    break;
                }

                validation = await _lightweightValidationService.ValidateAsync(accountId, project.ProjectId, loopToken);
                if (IsLightweightValidationPassed(validation))
                {
                    return new GddMilestoneLightweightValidationResult(true, $"{step.StepId} 轻量验收在自动修复第 {attempt} 次后通过。", lastRepair, validation);
                }

                failures.Add(BuildValidationFailureSummary(validation));
            }

            var summary = $"{step.StepId} 轻量验收未通过；已自动修复 {CountRepairAttempts(lastRepair, failures)} 次或达到 20 分钟上限。请使用“提交反馈并修正模块”继续修复。最近失败：{Trim(string.Join(" | ", failures.TakeLast(2)), 900)}";
            return new GddMilestoneLightweightValidationResult(false, summary, lastRepair, validation);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested && timeout.IsCancellationRequested)
        {
            return new GddMilestoneLightweightValidationResult(false, $"{step.StepId} 轻量验收自动修复已达到 20 分钟上限。请使用“提交反馈并修正模块”继续修复。", null, null);
        }
    }

    private static bool IsLightweightValidationPassed(PrototypeWorkflowResult validation)
    {
        return (validation.Status is "succeeded" or "completed") && validation.ExitCode == 0;
    }

    private static GddMilestoneStepValidationOutcome BuildStepValidationOutcome(
        string passedStatus,
        string? baseSummary,
        GddMilestoneLightweightValidationResult validation)
    {
        var safeBaseSummary = !string.IsNullOrWhiteSpace(baseSummary) && !TextIndicatesNeedsFix(baseSummary)
            ? baseSummary.Trim()
            : "";
        var summary = validation.Passed
            ? string.IsNullOrWhiteSpace(safeBaseSummary)
                ? validation.Summary
                : $"{safeBaseSummary}\n{validation.Summary}"
            : string.IsNullOrWhiteSpace(baseSummary)
            ? validation.Summary
            : $"{baseSummary}\n{validation.Summary}";
        return new GddMilestoneStepValidationOutcome(
            validation.Passed ? passedStatus : "needs_fix",
            summary,
            validation.LastRepairRun,
            validation.LightweightValidationRun);
    }

    private static string BuildStepActionSummary(
        GddMilestoneStepState step,
        string action,
        bool actionCompleted,
        string finalStatus,
        string fallbackDetail)
    {
        if (string.Equals(action, "feedback", StringComparison.Ordinal))
        {
            return actionCompleted && string.Equals(finalStatus, "feedback_submitted", StringComparison.Ordinal)
                ? $"{step.StepId} 的反馈修复已完成，轻量验收已通过。请打包下载试玩验证；确认通过后点击完成当前模块。"
                : actionCompleted
                    ? $"{step.StepId} 的反馈修复已完成，但轻量验收自动修复后仍未通过。请继续提交反馈并修正模块。"
                    : $"{step.StepId} 的反馈修复未完成：{fallbackDetail}";
        }

        return actionCompleted && string.Equals(finalStatus, "executed", StringComparison.Ordinal)
            ? $"{step.StepId} 已执行完成，轻量验收已通过。建议打包下载试玩验证；如果有问题，提交反馈并修正模块，也可以直接确认完成。"
            : actionCompleted
                ? $"{step.StepId} 已执行，但轻量验收自动修复后仍未通过。请使用“提交反馈并修正模块”继续修复。"
                : $"{step.StepId} 执行未完成：{fallbackDetail}";
    }

    private static int CountRepairAttempts(PrototypeNeedsFixRouteResult? lastRepair, IReadOnlyList<string> failures)
    {
        return lastRepair is null ? 0 : Math.Min(3, Math.Max(1, failures.Count - 1));
    }

    private static string BuildAutomaticValidationRepairFeedback(
        GddMilestoneStepState step,
        PrototypeWorkflowResult validation,
        int attempt)
    {
        return $"""
            Automatic lightweight validation failed after executing the current game module.

            Current module: {step.StepId} - {step.Title}
            Repair attempt: {attempt} of 3

            Module scope:
            {step.ScopeIn}

            Acceptance:
            {step.Acceptance}

            {PrototypeGameplayPromptGuards.BuildCombatPressureGuardPromptBlock()}

            Lightweight validation result:
            - RunId: {validation.RunId}
            - Status: {validation.Status}
            - ExitCode: {validation.ExitCode}
            - Stderr: {Trim(validation.Stderr, 1600)}
            - Stdout: {Trim(validation.Stdout, 800)}

            Repair only the current module. Do not unlock, implement, or alter later modules.
            Re-run and satisfy the lightweight validation before reporting completion.
            """;
    }

    private static string BuildValidationFailureSummary(PrototypeWorkflowResult validation)
    {
        return $"run={validation.RunId}; status={validation.Status}; exitCode={validation.ExitCode}; stderr={Trim(validation.Stderr, 240)}";
    }

    private static string ReadRunEvidenceText(ProjectSnapshot project, RunSnapshot run, string evidenceKey)
    {
        if (string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return "";
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            if (!document.RootElement.TryGetProperty(evidenceKey, out var element))
            {
                return "";
            }

            var relativePath = element.GetString();
            if (string.IsNullOrWhiteSpace(relativePath))
            {
                return "";
            }

            var fullPath = Path.Combine(project.RepoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
            return File.Exists(fullPath) ? File.ReadAllText(fullPath, Encoding.UTF8) : "";
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

    private static bool ContainsStructuredValue(string text, string fieldName, string expectedValue)
    {
        var value = ExtractStructuredField(text, fieldName);
        return string.Equals(value?.Trim(), expectedValue, StringComparison.OrdinalIgnoreCase);
    }

    private static string? ExtractStructuredField(string value, string fieldName)
    {
        var prefix = fieldName + ":";
        var lines = value.Replace("\r", "").Split('\n');
        for (var index = 0; index < lines.Length; index++)
        {
            var line = lines[index].Trim();
            if (!line.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var result = line[prefix.Length..].Trim();
            for (var next = index + 1; next < lines.Length; next++)
            {
                var nextLine = lines[next].Trim();
                if (nextLine.Contains(':', StringComparison.Ordinal) &&
                    nextLine.Split(':', 2)[0].All(ch => char.IsLetter(ch) || ch == '_'))
                {
                    break;
                }

                if (!string.IsNullOrWhiteSpace(nextLine))
                {
                    result = string.IsNullOrWhiteSpace(result) ? nextLine : $"{result}\n{nextLine}";
                }
            }

            return result;
        }

        return null;
    }

    private async Task MarkMilestoneExecutionCompletedAsync(
        string projectId,
        PrototypeIterationGoalExecutionResult execution,
        GddMilestoneState state,
        GddMilestoneStepState step,
        CancellationToken cancellationToken)
    {
        var summary = $"{step.StepId} 已执行完成。建议打包下载试玩验证；如果有问题，提交反馈并修正模块，也可以直接确认完成。";
        if (!string.IsNullOrWhiteSpace(execution.RunId))
        {
            await _metadataStore.UpdateRunProgressAsync(execution.RunId, "completed", "completed", $"{step.StepId} 已执行完成。", cancellationToken);
        }

        if (!string.IsNullOrWhiteSpace(execution.GoalId))
        {
            await _metadataStore.UpdateProjectIterationGoalStatusAsync(execution.GoalId, "succeeded", summary, DateTimeOffset.UtcNow.ToString("O"), cancellationToken);
        }

        if (!string.IsNullOrWhiteSpace(execution.SessionId))
        {
            var details = await _metadataStore.GetProjectIterationSessionAsync(projectId, execution.SessionId, cancellationToken);
            await _metadataStore.UpdateProjectIterationSessionStatusAsync(
                execution.SessionId,
                "paused_for_review",
                step.StepIndex,
                summary,
                details?.Session.LatestEvaluationJson,
                null,
                cancellationToken);
        }

        state.Summary = summary;
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
        return GddMilestoneTextParser.ExtractExplicitSteps(gddText)
            .Select(step => CreateStepState(step.StepId, step.StepIndex, step.Title, step.Description, "locked", true))
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
            BuildDefaultStep("M2", 2, "核心玩法闭环", "实现 GDD 中最小核心玩法循环，让玩家能完成一次明确的开始、操作、反馈、结果闭环。"),
            BuildDefaultStep("M3", 3, "主要交互与能力扩展", "补齐 GDD 中玩家最常使用的第二层交互、技能、道具、卡牌或操作变体，并提供冷却、消耗或状态反馈。"),
            BuildDefaultStep("M4", 4, "关卡流程与目标推进", "实现关卡、房间、波次、遭遇、回合或流程推进，让玩家能从入口推进到明确目标。"),
            BuildDefaultStep("M5", 5, "敌人、障碍或挑战变化", "加入至少一种新的挑战变化，并验证它与核心操作、失败条件和反馈表现协同工作。")
        };

        if (hasProgression)
        {
            steps.Add(BuildDefaultStep("M6", 6, "奖励与成长反馈", "实现奖励、升级、永久成长或其他 GDD 指定的进度反馈。"));
        }
        else
        {
            steps.Add(BuildDefaultStep("M6", 6, "结果结算与重开循环", "实现胜负、结算、重开或继续游玩的结果反馈，让一次试玩有清晰收束。"));
        }

        steps.Add(BuildDefaultStep("M7", 7, "HUD 与关键 UI 状态", "补齐核心屏幕、HUD 信息优先级、输入提示、关键状态、本地化入口和基础 accessibility 表现。"));
        steps.Add(BuildDefaultStep("M8", 8, "反馈表现与手感调整", "补齐命中、受击、交互、奖励、失败、转场等关键反馈，可先使用 placeholder 但保持命名和状态稳定。"));
        steps.Add(BuildDefaultStep("M9", 9, hasPolish ? "素材替换与碰撞验证" : "占位素材整理与碰撞验证", "替换或整理关键占位素材，并验证碰撞、阻挡、移动边界、命中、场景加载和基础交互 smoke。"));
        steps.Add(BuildDefaultStep("M10", 10, "原型可玩性验证与打包", "补齐首轮可玩验证、打包下载提示、截图或 smoke 证据，以及下一轮游戏模块创建准备。"));
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
        var godotSlice = "在 Godot 4.5.1 + C# 项目中完成可运行切片，优先覆盖场景、组件、输入、HUD/状态反馈和当前模块 smoke/assertion 验证。";
        var acceptance = $"完成并验证：{body} 玩家能通过打包版本直接试玩当前 step，看到明确开始、操作、反馈和结果；同时必须有一个当前模块 smoke/assertion 证明该可玩契约。";
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

    private static async Task ReconcileUnstartedStateWithGddAsync(
        ProjectSnapshot project,
        GddMilestoneState state,
        CancellationToken cancellationToken)
    {
        if (!StateCanBeReplacedFromGdd(state))
        {
            return;
        }

        var gddPath = Path.Combine(project.RepoPath, GddRelativePath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(gddPath))
        {
            return;
        }

        var gddText = await File.ReadAllTextAsync(gddPath, Encoding.UTF8, cancellationToken);
        var explicitSteps = ExtractSteps(gddText);
        if (explicitSteps.Count == 0 || SameStepShape(state.Steps, explicitSteps))
        {
            return;
        }

        for (var index = 0; index < explicitSteps.Count; index++)
        {
            explicitSteps[index] = explicitSteps[index] with
            {
                StepIndex = index + 1,
                Locked = index != 0,
                Status = index == 0 ? "ready" : "locked"
            };
        }

        state.Steps.Clear();
        state.Steps.AddRange(explicitSteps);
        state.CurrentStepId = state.Steps[0].StepId;
        state.Status = "ready";
        state.Summary = "已根据最新策划大纲里程碑刷新游戏模块步骤规格。";
    }

    private static bool StateCanBeReplacedFromGdd(GddMilestoneState state)
    {
        return state.Steps.Count > 0 &&
               state.Steps.All(step =>
                   string.IsNullOrWhiteSpace(step.IterationSessionId) &&
                   string.IsNullOrWhiteSpace(step.ExecutionRunId) &&
                   string.IsNullOrWhiteSpace(step.FeedbackRunId) &&
                   string.IsNullOrWhiteSpace(step.ConfirmedUtc) &&
                   step.Status is "ready" or "locked");
    }

    private static bool SameStepShape(IReadOnlyList<GddMilestoneStepState> current, IReadOnlyList<GddMilestoneStepState> incoming)
    {
        if (current.Count != incoming.Count)
        {
            return false;
        }

        for (var index = 0; index < current.Count; index++)
        {
            if (!string.Equals(current[index].StepId, incoming[index].StepId, StringComparison.OrdinalIgnoreCase) ||
                !string.Equals(current[index].Title, incoming[index].Title, StringComparison.Ordinal))
            {
                return false;
            }
        }

        return true;
    }

    private static async Task ReconcileAdditionalStepsFromGddAsync(
        ProjectSnapshot project,
        GddMilestoneState state,
        CancellationToken cancellationToken)
    {
        var gddPath = Path.Combine(project.RepoPath, GddRelativePath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(gddPath))
        {
            return;
        }

        var gddText = await File.ReadAllTextAsync(gddPath, Encoding.UTF8, cancellationToken);
        var incoming = ExtractSteps(gddText);
        if (incoming.Count == 0)
        {
            return;
        }

        var existingIds = state.Steps.Select(step => step.StepId).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var additions = incoming
            .Where(step => !existingIds.Contains(step.StepId))
            .OrderBy(step => step.StepIndex)
            .ToArray();
        if (additions.Length == 0)
        {
            return;
        }

        var hasActive = state.Steps.Any(step => !step.Locked && !string.Equals(step.Status, "confirmed", StringComparison.OrdinalIgnoreCase));
        var unlockFirstAddition = !hasActive && state.Steps.All(step => string.Equals(step.Status, "confirmed", StringComparison.OrdinalIgnoreCase));
        foreach (var addition in additions)
        {
            state.Steps.Add(addition with
            {
                StepIndex = state.Steps.Count + 1,
                Locked = !unlockFirstAddition || state.Steps.Any(step => !string.Equals(step.Status, "confirmed", StringComparison.OrdinalIgnoreCase)),
                Status = unlockFirstAddition && state.Steps.All(step => string.Equals(step.Status, "confirmed", StringComparison.OrdinalIgnoreCase)) ? "ready" : "locked"
            });
        }

        if (unlockFirstAddition)
        {
            var firstNew = state.Steps.FirstOrDefault(step => !step.Locked && !string.Equals(step.Status, "confirmed", StringComparison.OrdinalIgnoreCase));
            state.CurrentStepId = firstNew?.StepId;
            state.Status = "ready";
        }

        state.Summary = $"已从最新策划大纲同步新增 {additions.Length} 个游戏模块。";
    }

    private static async Task RefreshOutlineCompletionAsync(
        ProjectSnapshot project,
        GddMilestoneState state,
        CancellationToken cancellationToken)
    {
        var outlinePath = Path.Combine(project.RepoPath, OutlineRelativePath.Replace('/', Path.DirectorySeparatorChar));
        state.IncompleteOutlineSections.Clear();
        if (!File.Exists(outlinePath))
        {
            return;
        }

        GameDesignOutlineDocument? outline;
        try
        {
            await using var stream = File.OpenRead(outlinePath);
            outline = await JsonSerializer.DeserializeAsync<GameDesignOutlineDocument>(stream, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                ReadCommentHandling = JsonCommentHandling.Skip,
                AllowTrailingCommas = true
            }, cancellationToken);
        }
        catch (JsonException)
        {
            state.IncompleteOutlineSections.Add("策划大纲文件无法解析");
            return;
        }

        foreach (var section in outline?.Sections ?? [])
        {
            if (string.IsNullOrWhiteSpace(section.Content))
            {
                state.IncompleteOutlineSections.Add(string.IsNullOrWhiteSpace(section.Title) ? section.Id : section.Title);
            }
        }
    }

    private async Task ReconcileCompletedMilestoneExecutionsAsync(
        ProjectSnapshot project,
        GddMilestoneState state,
        CancellationToken cancellationToken)
    {
        var changed = false;
        for (var index = 0; index < state.Steps.Count; index++)
        {
            var step = state.Steps[index];
            if (!string.Equals(step.Status, "needs_fix", StringComparison.OrdinalIgnoreCase) ||
                string.IsNullOrWhiteSpace(step.ExecutionRunId) ||
                StepResultIndicatesNeedsFix(step))
            {
                continue;
            }

            var execution = new PrototypeIterationGoalExecutionResult(
                step.IterationSessionId ?? "",
                "",
                step.ExecutionRunId,
                "needs_fix",
                step.ExecutionSummary ?? "",
                step.StepIndex,
                false,
                "needs_fix");
            if (!await IsMilestoneStepExecutionCompleteAsync(project, execution, cancellationToken))
            {
                continue;
            }

            var details = string.IsNullOrWhiteSpace(step.IterationSessionId)
                ? null
                : await _metadataStore.GetProjectIterationSessionAsync(project.ProjectId, step.IterationSessionId, cancellationToken);
            var goalId = details?.Goals.FirstOrDefault(goal => goal.GoalIndex == step.StepIndex)?.GoalId ?? "";
            execution = execution with
            {
                SessionId = step.IterationSessionId ?? "",
                GoalId = goalId
            };
            await MarkMilestoneExecutionCompletedAsync(project.ProjectId, execution, state, step, cancellationToken);
            state.Steps[index] = step with
            {
                Status = "executed",
                ExecutionSummary = FirstNonEmpty(
                    step.ExecutionSummary,
                    $"{step.StepId} 已执行完成。建议打包下载试玩验证；如果有问题，提交反馈并修正模块，也可以直接确认完成。")
            };
            state.Summary = $"{step.StepId} 已执行完成。建议打包下载试玩验证；如果有问题，提交反馈并修正模块，也可以直接确认完成。";
            changed = true;
        }

        if (changed && state.Status == "completed")
        {
            state.Status = "ready";
        }
    }

    private async Task ReconcileLatestGddMilestoneSessionAsync(
        ProjectSnapshot project,
        GddMilestoneState state,
        CancellationToken cancellationToken)
    {
        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, "gdd_milestone_step", cancellationToken);
        if (details is null || details.Goals.Count == 0)
        {
            return;
        }

        var goal = details.Goals.FirstOrDefault(candidate => candidate.GoalIndex == details.Session.CurrentGoalIndex) ??
                   details.Goals.OrderByDescending(candidate => candidate.UpdatedUtc, StringComparer.Ordinal).FirstOrDefault();
        if (goal is null)
        {
            return;
        }

        var stepIndex = state.Steps.FindIndex(step =>
            step.StepIndex == goal.GoalIndex ||
            string.Equals(step.StepId, $"M{goal.GoalIndex}", StringComparison.OrdinalIgnoreCase));
        if (stepIndex < 0)
        {
            return;
        }

        var step = state.Steps[stepIndex];
        if (string.Equals(step.Status, "confirmed", StringComparison.OrdinalIgnoreCase))
        {
            return;
        }

        var executionRun = details.GoalRuns
            .Where(run => string.Equals(run.GoalId, goal.GoalId, StringComparison.OrdinalIgnoreCase) &&
                          string.Equals(run.RunType, "prototype-iteration-goal", StringComparison.OrdinalIgnoreCase))
            .OrderByDescending(run => run.CreatedUtc, StringComparer.Ordinal)
            .FirstOrDefault();
        var repairRun = details.GoalRuns
            .Where(run => string.Equals(run.GoalId, goal.GoalId, StringComparison.OrdinalIgnoreCase) &&
                          !string.Equals(run.RunType, "prototype-iteration-goal", StringComparison.OrdinalIgnoreCase))
            .OrderByDescending(run => run.CreatedUtc, StringComparer.Ordinal)
            .FirstOrDefault();
        if (executionRun is null && repairRun is null)
        {
            return;
        }

        var latestRunId = FirstNonEmpty(repairRun?.RunId, executionRun?.RunId);
        var runNeedsFix = await RunEvidenceIndicatesNeedsFixAsync(latestRunId, cancellationToken);
        var summaryNeedsFix = TextIndicatesNeedsFix(goal.ResultSummary) ||
                              TextIndicatesNeedsFix(details.Session.LatestSummary);
        var status = runNeedsFix || summaryNeedsFix
            ? "needs_fix"
            : goal.Status switch
        {
            "succeeded" or "completed" => repairRun is null ? "executed" : "feedback_submitted",
            "needs_fix" or "failed" => "needs_fix",
            _ => step.Status
        };
        if (string.IsNullOrWhiteSpace(status) || status is "ready" or "locked")
        {
            status = details.Session.Status is "needs_fix" or "failed"
                ? "needs_fix"
                : details.Session.Status is "paused_for_review" or "completed" or "succeeded"
                    ? (repairRun is null ? "executed" : "feedback_submitted")
                    : step.Status;
        }

        var evidence = string.IsNullOrWhiteSpace(latestRunId)
            ? null
            : await WriteStepEvidenceAsync(
                project,
                latestRunId,
                "module-session-sync",
                status,
                step.StepId,
                repairRun is null ? 0 : 1,
                null,
                cancellationToken);

        state.Steps[stepIndex] = step with
        {
            Locked = false,
            Status = status,
            IterationSessionId = details.Session.SessionId,
            ExecutionRunId = FirstNonEmpty(step.ExecutionRunId, executionRun?.RunId),
            ExecutionSummary = FirstNonEmpty(step.ExecutionSummary, goal.ResultSummary, details.Session.LatestSummary),
            FeedbackRunId = FirstNonEmpty(step.FeedbackRunId, repairRun?.RunId),
            FeedbackSummary = FirstNonEmpty(step.FeedbackSummary, repairRun is null ? null : goal.ResultSummary),
            LatestEvidenceRelativePath = FirstNonEmpty(step.LatestEvidenceRelativePath, evidence?.RelativePath)
        };
        state.CurrentStepId = status == "executed"
            ? step.StepId
            : state.Steps[stepIndex].StepId;
        state.Status = status == "needs_fix" ? "needs_fix" : state.Status;
        state.Summary = FirstNonEmpty(goal.ResultSummary, details.Session.LatestSummary, state.Summary);
    }

    private async Task<bool> RunEvidenceIndicatesNeedsFixAsync(string? runId, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(runId))
        {
            return false;
        }

        var run = await _metadataStore.GetRunSnapshotAsync(runId, cancellationToken);
        return TextIndicatesNeedsFix(run?.EvidenceJson) ||
               TextIndicatesNeedsFix(run?.StdoutText) ||
               TextIndicatesNeedsFix(run?.StderrText) ||
               TextIndicatesNeedsFix(run?.ProgressLabel);
    }

    private async Task ReconcilePrototypeSkeletonM1Async(
        ProjectSnapshot project,
        GddMilestoneState state,
        CancellationToken cancellationToken)
    {
        if (state.Steps.Count == 0)
        {
            return;
        }

        var first = state.Steps[0];
        if (!string.Equals(first.StepId, "M1", StringComparison.OrdinalIgnoreCase) ||
            first.Locked ||
            first.Status is "executed" or "feedback_submitted" or "confirmed" ||
            !string.IsNullOrWhiteSpace(first.IterationSessionId) ||
            !string.IsNullOrWhiteSpace(first.FeedbackRunId))
        {
            return;
        }

        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        var successfulSkeletonRun = runs.FirstOrDefault(run =>
            string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase) &&
            !PrototypeRunIsValidationOnly(run.EvidenceJson) &&
            string.Equals(run.Status, "succeeded", StringComparison.OrdinalIgnoreCase) &&
            PrototypeCompletionSucceeded(run.EvidenceJson));
        if (successfulSkeletonRun is not null)
        {
            var summary = "M1 已通过游戏场景创建完成。建议打包下载试玩验证基本操作、首个场景和首轮手感；如果有问题，提交反馈并修正模块，也可以直接确认完成。";
            var evidence = await WriteStepEvidenceAsync(project, successfulSkeletonRun.RunId, "scene-create", "executed", first.StepId, 0, null, cancellationToken);
            state.Steps[0] = first with
            {
                Status = "executed",
                ExecutionRunId = successfulSkeletonRun.RunId,
                ExecutionSummary = summary,
                LatestEvidenceRelativePath = evidence.RelativePath
            };
            state.CurrentStepId = first.StepId;
            state.Summary = summary;
            return;
        }

        var failedSkeletonRun = runs.FirstOrDefault(run =>
            string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase) &&
            !PrototypeRunIsValidationOnly(run.EvidenceJson) &&
            string.Equals(run.Status, "failed", StringComparison.OrdinalIgnoreCase) &&
            PrototypeCompletionFailed(run.EvidenceJson));
        if (failedSkeletonRun is null)
        {
            return;
        }

        var failureSummary = BuildPrototypeSkeletonFailureSummary(failedSkeletonRun);
        var alreadySyncedFailure = string.Equals(first.ExecutionRunId, failedSkeletonRun.RunId, StringComparison.OrdinalIgnoreCase) &&
                                   string.Equals(first.Status, "needs_fix", StringComparison.OrdinalIgnoreCase);
        var evidencePath = first.LatestEvidenceRelativePath;
        if (!alreadySyncedFailure || string.IsNullOrWhiteSpace(evidencePath))
        {
            var evidence = await WriteStepEvidenceAsync(project, failedSkeletonRun.RunId, "scene-create", "needs_fix", first.StepId, 0, null, cancellationToken);
            evidencePath = evidence.RelativePath;
        }

        var failedSummary = $"M1 游戏场景创建未通过，需要修复。{failureSummary}";
        state.Steps[0] = first with
        {
            Status = "needs_fix",
            ExecutionRunId = failedSkeletonRun.RunId,
            ExecutionSummary = failedSummary,
            LatestEvidenceRelativePath = evidencePath
        };
        state.CurrentStepId = first.StepId;
        state.Summary = failedSummary;
    }

    private static bool PrototypeCompletionSucceeded(string? evidenceJson)
    {
        if (string.IsNullOrWhiteSpace(evidenceJson))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(evidenceJson);
            if (!document.RootElement.TryGetProperty("prototype_completion", out var completion) ||
                completion.ValueKind != JsonValueKind.Object)
            {
                return false;
            }

            return completion.TryGetProperty("succeeded", out var succeeded) &&
                   succeeded.ValueKind == JsonValueKind.True;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool PrototypeRunIsValidationOnly(string? evidenceJson)
    {
        if (string.IsNullOrWhiteSpace(evidenceJson))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(evidenceJson);
            return IsTrue(document.RootElement, "validation_only") ||
                   IsTrue(document.RootElement, "skeleton_validation_only");
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool IsTrue(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.True;
    }

    private static bool PrototypeCompletionFailed(string? evidenceJson)
    {
        if (string.IsNullOrWhiteSpace(evidenceJson))
        {
            return true;
        }

        try
        {
            using var document = JsonDocument.Parse(evidenceJson);
            if (!document.RootElement.TryGetProperty("prototype_completion", out var completion) ||
                completion.ValueKind != JsonValueKind.Object)
            {
                return true;
            }

            return completion.TryGetProperty("succeeded", out var succeeded) &&
                   succeeded.ValueKind == JsonValueKind.False;
        }
        catch (JsonException)
        {
            return true;
        }
    }

    private static string BuildPrototypeSkeletonFailureSummary(RunSnapshot run)
    {
        var evidenceError = ReadPrototypeCompletionError(run.EvidenceJson);
        var diagnostic = FirstNonEmpty(
            MostRelevantFailureLine(run.StdoutText),
            LastNonEmptyLine(run.StderrText),
            evidenceError,
            run.ProgressLabel,
            "请查看运行记录错误输出。");
        return Trim(diagnostic, 260);
    }

    private static string ReadPrototypeCompletionError(string? evidenceJson)
    {
        if (string.IsNullOrWhiteSpace(evidenceJson))
        {
            return "";
        }

        try
        {
            using var document = JsonDocument.Parse(evidenceJson);
            if (!document.RootElement.TryGetProperty("prototype_completion", out var completion) ||
                completion.ValueKind != JsonValueKind.Object)
            {
                return "";
            }

            return ReadString(completion, "error");
        }
        catch (JsonException)
        {
            return "";
        }
    }

    private static string LastNonEmptyLine(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return "";
        }

        return text.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .Select(line => line.Trim())
            .LastOrDefault(line => !string.IsNullOrWhiteSpace(line)) ?? "";
    }

    private static string MostRelevantFailureLine(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return "";
        }

        var lines = text.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .Select(line => line.Trim())
            .Where(line => !string.IsNullOrWhiteSpace(line))
            .ToArray();
        return lines.FirstOrDefault(line => line.Contains("DAY4_IMPLEMENTATION_VALIDATION", StringComparison.OrdinalIgnoreCase)) ??
               lines.FirstOrDefault(line => line.Contains("failed", StringComparison.OrdinalIgnoreCase)) ??
               lines.LastOrDefault() ??
               "";
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
        var outlineComplete = state.IncompleteOutlineSections.Count == 0;
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
                outlineComplete && !step.Locked && (step.Status is "ready" or "needs_fix" or "execution_failed" or "feedback_failed" or "timed_out"),
                !step.Locked && (step.Status is "executed" or "feedback_submitted"),
                !step.Locked && (step.Status is "executed" or "needs_fix" or "execution_failed" or "feedback_failed" or "timed_out"),
                step.ReviewSummary,
                StepSpecRelativePath(step),
                step.LatestEvidenceRelativePath,
                step.ExecutionRunId,
                step.ExecutionSummary,
                step.FeedbackRunId,
                step.FeedbackSummary,
                step.ConfirmedUtc)).ToArray(),
            state.CurrentStepId,
            OutlineComplete: outlineComplete,
            IncompleteOutlineSections: state.IncompleteOutlineSections.ToArray());
    }

    private Task<PrototypeEngineeringEvidenceWriteResult> WriteStepEvidenceAsync(
        ProjectSnapshot project,
        string runId,
        string route,
        string status,
        string moduleId,
        int repairAttempts,
        PrototypeWorkflowResult? lightweightValidationRun,
        CancellationToken cancellationToken)
    {
        var checkStatus = status is "executed" or "feedback_submitted" ? "passed" :
            status is "needs_fix" or "execution_failed" or "feedback_failed" or "timed_out" ? "failed" : "skipped";
        var check = BuildLightweightEvidenceCheck(checkStatus, status, lightweightValidationRun);
        return _engineeringClosure.WriteEvidenceAsync(
            project,
            new PrototypeEngineeringEvidence(
                runId,
                route,
                status is "executed" or "feedback_submitted" ? "passed" : status is "needs_fix" ? "needs_user_feedback" : status,
                moduleId,
                RepairAttempts: repairAttempts,
                DotnetBuild: check,
                GodotImport: check,
                HeadlessLoad: check,
                MilestoneSmoke: check,
                AssetValidation: PrototypeEngineeringCheckResult.Skipped("not an asset-library route"),
                FrameCheck: PrototypeEngineeringCheckResult.Skipped("not required for this module route"),
                FailureSummary: checkStatus == "failed" ? [status] : []),
            cancellationToken);
    }

    private static PrototypeEngineeringCheckResult BuildLightweightEvidenceCheck(
        string checkStatus,
        string status,
        PrototypeWorkflowResult? lightweightValidationRun)
    {
        if (lightweightValidationRun is null)
        {
            return checkStatus switch
            {
                "passed" => PrototypeEngineeringCheckResult.Passed(),
                "failed" => PrototypeEngineeringCheckResult.Failed(reason: status),
                _ => PrototypeEngineeringCheckResult.Skipped(status)
            };
        }

        var log = $"run={lightweightValidationRun.RunId}; exitCode={lightweightValidationRun.ExitCode}";
        if (checkStatus == "passed")
        {
            return PrototypeEngineeringCheckResult.Passed(log);
        }

        return PrototypeEngineeringCheckResult.Failed(log, Trim(BuildValidationFailureSummary(lightweightValidationRun), 300));
    }

    private static async Task WriteSpecFilesAsync(ProjectSnapshot project, GddMilestoneState state, CancellationToken cancellationToken)
    {
        NormalizeState(state);
        var gddPath = Path.Combine(project.RepoPath, GddRelativePath.Replace('/', Path.DirectorySeparatorChar));
        if (File.Exists(gddPath))
        {
            var gddText = await File.ReadAllTextAsync(gddPath, Encoding.UTF8, cancellationToken);
            await GddMilestoneSpecDocumentWriter.WriteFromMilestoneStateAsync(project, ToResult(project.ProjectId, state).Steps, gddText, cancellationToken);
        }
    }

    private static string StepSpecRelativePath(GddMilestoneStepState step)
        => GddMilestoneSpecDocumentWriter.StepSpecRelativePath(step.StepId, step.Title);

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
        state.IncompleteOutlineSections ??= [];
        for (var index = 0; index < state.Steps.Count; index++)
        {
            var step = state.Steps[index];
            var spec = BuildStepSpec(step.StepId, step.Title, step.Description);
            var normalizedStatus = NormalizeRecoverableStepStatus(step);
            if (!string.IsNullOrWhiteSpace(step.ConfirmedUtc))
            {
                normalizedStatus = "confirmed";
            }
            else if (!IsSuccessfulStepStatus(normalizedStatus) && StepResultIndicatesNeedsFix(step))
            {
                normalizedStatus = "needs_fix";
            }
            state.Steps[index] = step with
            {
                StepIndex = step.StepIndex <= 0 ? index + 1 : step.StepIndex,
                Status = normalizedStatus,
                Acceptance = FirstNonEmpty(step.Acceptance, spec.Acceptance),
                ScopeIn = FirstNonEmpty(step.ScopeIn, spec.ScopeIn),
                ScopeOut = FirstNonEmpty(step.ScopeOut, spec.ScopeOut),
                GodotSlice = FirstNonEmpty(step.GodotSlice, spec.GodotSlice),
                PackagingValidation = FirstNonEmpty(step.PackagingValidation, spec.PackagingValidation),
                FeedbackGuidance = FirstNonEmpty(step.FeedbackGuidance, spec.FeedbackGuidance),
                NextStepReview = FirstNonEmpty(step.NextStepReview, spec.NextStepReview)
            };
        }

        if (state.Steps.Count > 0)
        {
            var hasNeedsFix = state.Steps.Any(step => step.Status is "needs_fix" or "execution_failed" or "feedback_failed" or "timed_out");
            var allConfirmed = state.Steps.All(step => string.Equals(step.Status, "confirmed", StringComparison.OrdinalIgnoreCase));
            if (hasNeedsFix)
            {
                state.Status = "needs_fix";
            }
            else if (allConfirmed)
            {
                state.Status = "completed";
            }
            else if (string.Equals(state.Status, "needs_fix", StringComparison.OrdinalIgnoreCase))
            {
                state.Status = "ready";
            }
        }
    }

    private static string NormalizeRecoverableStepStatus(GddMilestoneStepState step)
    {
        var normalized = NormalizeLegacyStepStatus(step.Status);
        if (!IsTransientStepStatus(normalized))
        {
            return normalized;
        }

        return !string.IsNullOrWhiteSpace(step.ExecutionRunId) ||
               !string.IsNullOrWhiteSpace(step.FeedbackRunId) ||
               !string.IsNullOrWhiteSpace(step.IterationSessionId)
            ? "timed_out"
            : "ready";
    }

    private static bool StepResultIndicatesNeedsFix(GddMilestoneStepState step)
    {
        return TextIndicatesNeedsFix(step.ExecutionSummary) ||
               TextIndicatesNeedsFix(step.FeedbackSummary) ||
               TextIndicatesNeedsFix(step.ReviewSummary);
    }

    private static bool IsSuccessfulStepStatus(string? status)
    {
        return string.Equals(status, "executed", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "feedback_submitted", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "confirmed", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "completed", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "succeeded", StringComparison.OrdinalIgnoreCase);
    }

    private static bool TextIndicatesNeedsFix(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        return text.Contains("STATUS: needs_fix", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("\"goal_repair_status\":\"needs_fix\"", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("\"goalRepairStatus\":\"needs_fix\"", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("\"status\":\"needs_fix\"", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("prototype_smoke_scene_missing", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("prototype_completion_state_missing", StringComparison.OrdinalIgnoreCase) ||
               text.Contains("仍需修复", StringComparison.Ordinal) ||
               text.Contains("需要修复", StringComparison.Ordinal) ||
               text.Contains("未通过", StringComparison.Ordinal);
    }

    private static string NormalizeLegacyStepStatus(string? status)
    {
        var normalized = string.IsNullOrWhiteSpace(status) ? "ready" : status.Trim();
        return normalized switch
        {
            "iteration_ready" => "ready",
            "iteration_plan_failed" => "execution_failed",
            _ => normalized
        };
    }

    private static bool IsTransientStepStatus(string status)
    {
        return status is "running" or "executing" or "validating" or "auto_repairing" or "repairing" or "feedback_running";
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

        public List<string> IncompleteOutlineSections { get; set; } = [];
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
        string? ReviewSummary = null,
        string? LatestEvidenceRelativePath = null);

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

    private sealed record GddMilestoneLightweightValidationResult(
        bool Passed,
        string Summary,
        PrototypeNeedsFixRouteResult? LastRepairRun,
        PrototypeWorkflowResult? LightweightValidationRun);

    private sealed record GddMilestoneStepValidationOutcome(
        string Status,
        string Summary,
        PrototypeNeedsFixRouteResult? LastRepairRun,
        PrototypeWorkflowResult? LightweightValidationRun);
}
