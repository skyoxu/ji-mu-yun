using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeQuickFixService
{
    private const string RunType = "prototype-quick-fix";
    private const string ReasoningEffort = "low";
    private static readonly TimeSpan DefaultExecutionTimeout = TimeSpan.FromSeconds(300);

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly SkillActionCatalog _skillActionCatalog;
    private readonly TimeSpan _executionTimeout;

    public PrototypeQuickFixService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner)
        : this(metadataStore, options, processRunner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), null)
    {
    }

    public PrototypeQuickFixService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        IProjectWorkspaceSeeder workspaceSeeder,
        SkillActionCatalog skillActionCatalog,
        TimeSpan? executionTimeout = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _workspaceSeeder = workspaceSeeder;
        _skillActionCatalog = skillActionCatalog;
        _executionTimeout = executionTimeout ?? DefaultExecutionTimeout;
    }

    public async Task<PrototypeFeedbackResult> SubmitAsync(
        string projectId,
        PrototypeFeedbackRequest request,
        CancellationToken cancellationToken = default)
    {
        return await SubmitAsync(projectId, request, requireSucceededPrototypeRun: true, cancellationToken);
    }

    internal async Task<PrototypeFeedbackResult> SubmitAsync(
        string projectId,
        PrototypeFeedbackRequest request,
        bool requireSucceededPrototypeRun,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var feedback = request.Feedback?.Trim();
        if (string.IsNullOrWhiteSpace(feedback))
        {
            return new PrototypeFeedbackResult("", "missing_feedback", "请输入要快速修复的问题。", []);
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            throw new InvalidOperationException("Project not found.");
        }

        if (requireSucceededPrototypeRun && !await HasSucceededPrototypeWorkflowAsync(project.ProjectId, cancellationToken))
        {
            return new PrototypeFeedbackResult("", "prototype_not_ready", "请先完成 7 步可玩原型，再使用快速修复。", []);
        }

        ProjectIterationSessionDetails? iterationDetails = null;
        ProjectIterationGoalSnapshot? targetGoal = null;
        PrototypeGoalRepairContext? goalRepair = null;
        ProjectRunMemorySnapshot? runMemory = null;
        var goalRepairMode = request.GoalRepair is not null;
        if (goalRepairMode)
        {
            iterationDetails = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, cancellationToken);
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
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return new PrototypeFeedbackResult(runId, "project_busy", "当前有任务正在执行，请等待完成后再试。", []);
        }

        await _metadataStore.MarkRunStartedAsync(runId, CancellationToken.None);
        await SetProgressAsync(runId, "running", "prepare", "正在准备快速修复任务。", CancellationToken.None);

        try
        {
            var relativeDir = Path.Combine("logs", "phase-a-quick-fix", project.ProjectId, runId);
            var absoluteDir = Path.Combine(project.RepoPath, relativeDir);
            Directory.CreateDirectory(absoluteDir);

            var submittedRelativePath = ToSlash(Path.Combine(relativeDir, "submitted-feedback.md"));
            var resultRelativePath = ToSlash(Path.Combine(relativeDir, "result-log.md"));
            var codexOutputRelativePath = ToSlash(Path.Combine(relativeDir, "codex-output.txt"));
            var submittedAbsolutePath = Path.Combine(project.RepoPath, submittedRelativePath.Replace('/', Path.DirectorySeparatorChar));
            var resultAbsolutePath = Path.Combine(project.RepoPath, resultRelativePath.Replace('/', Path.DirectorySeparatorChar));
            var codexOutputAbsolutePath = Path.Combine(project.RepoPath, codexOutputRelativePath.Replace('/', Path.DirectorySeparatorChar));
            var now = DateTimeOffset.UtcNow.ToString("O");
            var skillAction = ResolveSkillAction(request.SkillActionId);
            var routeSkill = PrototypeRouteSkillPolicy.Resolve(project);
            var executionWorkspace = PrepareExecutionWorkspace(project, targetGoal, runId, codexOutputAbsolutePath);

            await File.WriteAllTextAsync(
                submittedAbsolutePath,
                BuildSubmittedFeedback(project, runId, feedback, now, skillAction, targetGoal),
                Encoding.UTF8,
                CancellationToken.None);

            var model = PrototypeModelPolicy.Normalize(request.Model);
            using var timeout = new CancellationTokenSource();
            timeout.CancelAfter(_executionTimeout);
            var prompt = BuildCodexPrompt(project, runId, feedback, skillAction, targetGoal, runMemory);
            await SetProgressAsync(runId, "running", "codex", goalRepairMode ? $"Codex 正在修复目标 {targetGoal!.GoalIndex}。" : "Codex 正在执行快速修复。", CancellationToken.None);
            var codexResult = await _processRunner.RunAsync(BuildCodexCommand(prompt, executionWorkspace.CodexOutputPath, model, executionWorkspace.RootPath), timeout.Token);
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
            if (acceptanceValidation.Passed)
            {
                assistantMessage = AppendAcceptanceValidationSummary(assistantMessage, targetGoal!);
                codexOutput = AppendAcceptanceValidationEvidence(codexOutput);
                var prototypeState = new PrototypeRouteStateWriter().ReadLatestPrototypeState(project);
                godotSmokeValidation = await PrototypeGodotSmokeService.ValidateGoalAsync(project, targetGoal!, prototypeState, _options, _processRunner, CancellationToken.None);
                if (godotSmokeValidation.Passed && godotSmokeValidation.Required)
                {
                    assistantMessage = AppendGodotSmokeValidationSummary(assistantMessage, targetGoal!, godotSmokeValidation);
                    codexOutput = AppendGodotSmokeValidationEvidence(codexOutput);
                }
                else if (godotSmokeValidation.Required)
                {
                    assistantMessage = AppendGodotSmokeValidationFailure(assistantMessage, godotSmokeValidation);
                }
            }
            await SetProgressAsync(runId, "running", "finalize", goalRepairMode ? "目标修复结果已返回，正在整理状态。" : "快速修复结果已返回，正在整理日志。", CancellationToken.None);

            var goalRepairOutcome = targetGoal is null
                ? null
                : acceptanceValidation.Passed
                    ? godotSmokeValidation.Passed
                        ? new GoalRepairOutcome("succeeded", true)
                        : new GoalRepairOutcome("needs_fix", false)
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
                skill_action_id = skillAction?.ActionId,
                skill_name = skillAction?.SkillName,
                quick_fix = true,
                goal_repair = targetGoal is not null,
                goal_id = targetGoal?.GoalId,
                goal_index = targetGoal?.GoalIndex,
                goal_repair_status = goalRepairOutcome?.GoalStatus,
                acceptance_validation = acceptanceValidation.Kind,
                acceptance_validation_status = acceptanceValidation.Status,
                godot_smoke_validation = godotSmokeValidation.ToEvidence()
            });
            await _metadataStore.CompleteRunAsync(runId, "completed", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceJson, CancellationToken.None);
            if (targetGoal is not null && iterationDetails is not null && goalRepairOutcome is not null)
            {
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

            await SetProgressAsync(runId, "completed", "", "快速修复已完成。", CancellationToken.None);

            var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, CancellationToken.None);
            return new PrototypeFeedbackResult(runId, "completed", assistantMessage, artifacts);
        }
        catch (OperationCanceledException)
        {
            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                failure_code = "prototype_quick_fix_timeout"
            });
            await _metadataStore.CompleteRunAsync(runId, "failed", 408, "", $"Prototype quick fix exceeded the {_executionTimeout.TotalSeconds:0} second timeout.", evidenceJson, CancellationToken.None);
            if (targetGoal is not null && iterationDetails is not null)
            {
                var summary = $"目标 {targetGoal.GoalIndex} 修复超时。当前目标仍需修复，请继续聚焦本 step，不要切到后续目标。";
                await _metadataStore.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", summary, null, CancellationToken.None);
                await _metadataStore.UpdateProjectIterationSessionStatusAsync(iterationDetails.Session.SessionId, "needs_fix", targetGoal.GoalIndex, summary, iterationDetails.Session.LatestEvaluationJson, null, CancellationToken.None);
                await UpsertGoalRunMemoryAsync(projectId, targetGoal, "needs_fix", summary, "当前目标修复超时。", [summary], CancellationToken.None);
                await SetProgressAsync(runId, "failed", "timeout", $"目标 {targetGoal.GoalIndex} 修复超时，仍需继续修复。", CancellationToken.None);
                return new PrototypeFeedbackResult(runId, "failed", "当前目标修复超时。系统没有切换到后续目标，你可以继续再次修复当前 step。", [], "needs_fix", "needs_fix", targetGoal.GoalIndex);
            }

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
                await _metadataStore.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", summary, null, CancellationToken.None);
                await _metadataStore.UpdateProjectIterationSessionStatusAsync(iterationDetails.Session.SessionId, "needs_fix", targetGoal.GoalIndex, summary, iterationDetails.Session.LatestEvaluationJson, null, CancellationToken.None);
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

    private async Task<bool> HasSucceededPrototypeWorkflowAsync(string projectId, CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(projectId, cancellationToken);
        return runs.Any(run => run.RunType == "prototype-7day-playable" && run.Status == "succeeded");
    }

    private Task SetProgressAsync(string runId, string step, string substep, string label, CancellationToken cancellationToken)
    {
        return _metadataStore.UpdateRunProgressAsync(runId, step, substep, label, cancellationToken);
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
        var arguments = new List<string>
        {
            "exec",
            "--sandbox",
            "workspace-write",
            "-m",
            model,
            "-c",
            "approval_policy=\"never\"",
            "-c",
            $"model_reasoning_effort=\"{ReasoningEffort}\"",
            "--cd",
            repositoryRoot,
            "-o",
            outputPath,
            "-"
        };

        return new HostedProcessCommand(
            ResolveCodexCommand(),
            arguments,
            repositoryRoot,
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["PHASEA_CODEX_DEFAULT_MODEL"] = model,
                ["PHASEA_CODEX_REASONING_EFFORT"] = ReasoningEffort
            },
            prompt);
    }

    private static string BuildCodexPrompt(ProjectSnapshot project, string runId, string feedback, SkillActionDefinition? skillAction, ProjectIterationGoalSnapshot? goal, ProjectRunMemorySnapshot? runMemory = null)
    {
        if (goal is not null)
        {
            return BuildGoalRepairPrompt(project, runId, feedback, goal, runMemory);
        }

        var skillInstruction = skillAction is null
            ? "能力模式：普通模式。"
            : $"能力模式：{skillAction.Label}。执行时使用 ${skillAction.SkillName} 的方法。";

        return $"""
            你正在执行积木云 Phase A 的快速修复任务。
            {PrototypeRouteSkillPolicy.BuildPromptBlock(project)}
            {skillInstruction}

            硬约束：
            - 这是一个 90 秒内完成的小修复，不要做大范围重构。
            - 仅处理明确、局部、低风险问题。
            - 优先修改少量文件，优先修接线、常量、菜单入口、状态显示、文本或小型前端逻辑。
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

    private static string BuildGoalRepairPrompt(ProjectSnapshot project, string runId, string feedback, ProjectIterationGoalSnapshot goal, ProjectRunMemorySnapshot? runMemory)
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

        return $"""
            你正在执行积木云 Phase A 的单目标迭代修复任务。

            {PrototypeRouteSkillPolicy.BuildPromptBlock(project)}
            Mandatory rules:
            - 这次只处理当前目标，不要顺手扩展到后续目标。
            - 直接围绕当前目标实现，不要先做任务恢复、仓库导览、规则总结或工作流巡检。
            - 不要读取或总结 AGENTS.md、decision-logs、execution-plans、active-task、session recovery 一类文件。
            - 不要修改 PhaseA.Platform/**、PhaseA.Platform.Tests/**、scripts/**、docs/** 这些云端控制台与工具链文件。
            - 如果当前目标是 RPG 原型修复，默认只允许修改 Game.Godot/Prototypes/dq-rpg/**、Game.Core/Prototypes/**、Game.Core.Tests/Prototypes/**、Tests.Godot/tests/Prototype/** 这些与原型直接相关的位置。
            - 结构化运行记忆和历史摘要只用于理解上次到哪里了，不是本轮修复目标。
            - 不要把“路由状态、恢复逻辑、平台测试、文档整理、脚本调整”当作当前目标的完成内容，除非当前目标标题和验收提示明确要求。
            - 如果当前目标是玩法/Godot/RPG 目标，完成标准必须来自 Title、Description、AcceptanceHint 中的玩法验收。
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

            用户触发这次修复时附带的说明：
            {feedback}

            {memoryBlock}

            当前运行环境已经切到一个只包含原型白名单目录的聚焦工作区。
            你不需要也不应该做仓库恢复、全仓巡检、部署修复或文档整理。

            成功定义：
            - 只有当当前 step 已可继续，才可视为修复成功。
            - “已可继续”必须指当前目标的玩法/业务验收通过，不是平台路由或恢复语义通过。
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

    private static string ResolveCodexCommand()
    {
        var configured = Environment.GetEnvironmentVariable("PHASEA_CODEX_COMMAND");
        if (!string.IsNullOrWhiteSpace(configured))
        {
            return configured;
        }

        var candidates = new[]
        {
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "npm",
                "codex.cmd"),
            @"C:\Windows\System32\config\systemprofile\AppData\Roaming\npm\codex.cmd",
            @"C:\Users\Administrator\AppData\Roaming\npm\codex.cmd"
        };

        return candidates.FirstOrDefault(File.Exists) ?? "codex";
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
