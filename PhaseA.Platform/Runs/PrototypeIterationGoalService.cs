using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeIterationGoalService
{
    private const string RunType = "prototype-iteration-goal";
    private const string ReasoningEffort = "low";
    private static readonly TimeSpan DefaultExecutionTimeout = TimeSpan.FromMinutes(8);

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly TimeSpan _executionTimeout;

    public PrototypeIterationGoalService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner)
        : this(metadataStore, options, processRunner, new ProjectWorkspaceSeeder(options), null)
    {
    }

    public PrototypeIterationGoalService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        IProjectWorkspaceSeeder workspaceSeeder,
        TimeSpan? executionTimeout = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _workspaceSeeder = workspaceSeeder;
        _executionTimeout = executionTimeout ?? DefaultExecutionTimeout;
    }

    public async Task<PrototypeIterationGoalExecutionResult> ExecuteNextAsync(
        string accountId,
        string projectId,
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
            return new PrototypeIterationGoalExecutionResult("", "", "", "missing_plan", "当前项目还没有迭代计划。", 0, false, "failed");
        }

        var needsFixGoal = details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "needs_fix", StringComparison.Ordinal));
        if (needsFixGoal is not null)
        {
            var summary = $"当前计划存在需要修复的目标 {needsFixGoal.GoalIndex}。请先修复当前目标，不要继续执行下一目标。";
            await _metadataStore.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", needsFixGoal.GoalIndex, summary, null, null, CancellationToken.None);
            return new PrototypeIterationGoalExecutionResult(details.Session.SessionId, needsFixGoal.GoalId, "", "needs_fix", summary, needsFixGoal.GoalIndex, true, "needs_fix");
        }

        var nextGoal = details.Goals.FirstOrDefault(goal => string.Equals(goal.Status, "pending", StringComparison.Ordinal));
        if (nextGoal is null)
        {
            return new PrototypeIterationGoalExecutionResult(details.Session.SessionId, "", "", "no_pending_goal", "当前计划中没有待执行目标。", details.Session.CurrentGoalIndex, false, details.Session.Status);
        }

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return new PrototypeIterationGoalExecutionResult(details.Session.SessionId, nextGoal.GoalId, runId, "project_busy", "当前有任务正在执行，请等待完成后再试。", nextGoal.GoalIndex, true, "paused_for_review");
        }

        await _metadataStore.MarkRunStartedAsync(runId, CancellationToken.None);
        await _metadataStore.UpdateProjectIterationGoalStatusAsync(nextGoal.GoalId, "running", null, null, CancellationToken.None);
        await _metadataStore.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "running", nextGoal.GoalIndex, $"正在执行目标 {nextGoal.GoalIndex}。", null, null, CancellationToken.None);
        await _metadataStore.UpdateRunProgressAsync(runId, "running", "prepare", $"正在准备目标 {nextGoal.GoalIndex}。", CancellationToken.None);

        try
        {
            var relativeDir = Path.Combine("logs", "phase-a-iteration", project.ProjectId, details.Session.SessionId, nextGoal.GoalId, runId);
            var absoluteDir = Path.Combine(project.RepoPath, relativeDir);
            Directory.CreateDirectory(absoluteDir);

            var goalRelativePath = ToSlash(Path.Combine(relativeDir, "goal-input.md"));
            var resultRelativePath = ToSlash(Path.Combine(relativeDir, "goal-result.md"));
            var codexOutputRelativePath = ToSlash(Path.Combine(relativeDir, "codex-output.txt"));
            var goalAbsolutePath = Path.Combine(project.RepoPath, goalRelativePath.Replace('/', Path.DirectorySeparatorChar));
            var resultAbsolutePath = Path.Combine(project.RepoPath, resultRelativePath.Replace('/', Path.DirectorySeparatorChar));
            var codexOutputAbsolutePath = Path.Combine(project.RepoPath, codexOutputRelativePath.Replace('/', Path.DirectorySeparatorChar));
            var codexRuntimeOutputPath = CreateShortRuntimeOutputPath(runId);
            var now = DateTimeOffset.UtcNow.ToString("O");

            await File.WriteAllTextAsync(goalAbsolutePath, BuildGoalInput(details.Session, nextGoal, now), Encoding.UTF8, CancellationToken.None);

            using var timeout = new CancellationTokenSource();
            timeout.CancelAfter(_executionTimeout);
            var model = PrototypeModelPolicy.Normalize("gpt-5.4");
            var prompt = BuildPrompt(project, details.Session, nextGoal);
            await _metadataStore.UpdateRunProgressAsync(runId, "running", "codex", $"Codex 正在执行目标 {nextGoal.GoalIndex}。", CancellationToken.None);
            var codexResult = await _processRunner.RunAsync(BuildCodexCommand(prompt, codexRuntimeOutputPath, model, project.RepoPath), timeout.Token);
            if (File.Exists(codexRuntimeOutputPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(codexOutputAbsolutePath)!);
                File.Copy(codexRuntimeOutputPath, codexOutputAbsolutePath, overwrite: true);
            }

            var codexOutput = File.Exists(codexRuntimeOutputPath)
                ? await File.ReadAllTextAsync(codexRuntimeOutputPath, Encoding.UTF8, CancellationToken.None)
                : "";
            var publicSummary = BuildAssistantMessage(nextGoal, codexResult, codexOutput);
            var goalOutcome = DetermineGoalOutcome(publicSummary, codexResult, codexOutput);

            await File.WriteAllTextAsync(resultAbsolutePath, BuildResultLog(details.Session, nextGoal, runId, model, publicSummary, codexResult, codexOutput, now), Encoding.UTF8, CancellationToken.None);

            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "prototype-iteration-goal-input", goalRelativePath, "Prototype iteration goal input"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "prototype-iteration-goal-result", resultRelativePath, "Prototype iteration goal result"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "prototype-iteration-goal-codex-output", codexOutputRelativePath, "Prototype iteration goal Codex output"), CancellationToken.None);

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                session_id = details.Session.SessionId,
                goal_id = nextGoal.GoalId,
                goal_index = nextGoal.GoalIndex,
                model,
                goal_input = goalRelativePath,
                result_log = resultRelativePath,
                codex_output = codexOutputRelativePath
            });
            await _metadataStore.CompleteRunAsync(runId, "completed", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceJson, CancellationToken.None);
            await _metadataStore.UpdateProjectIterationGoalStatusAsync(nextGoal.GoalId, goalOutcome.GoalStatus, publicSummary, goalOutcome.MarkCompleted ? now : null, CancellationToken.None);
            await _metadataStore.LinkProjectIterationGoalRunAsync(details.Session.SessionId, nextGoal.GoalId, runId, RunType, CancellationToken.None);

            var refreshed = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, CancellationToken.None);
            var hasNeedsFix = refreshed?.Goals.Any(goal => string.Equals(goal.Status, "needs_fix", StringComparison.Ordinal)) == true;
            var hasMoreGoals = refreshed?.Goals.Any(goal => string.Equals(goal.Status, "pending", StringComparison.Ordinal)) == true;
            var sessionStatus = hasNeedsFix ? "needs_fix" : hasMoreGoals ? "paused_for_review" : "completed";
            var sessionSummary = hasNeedsFix
                ? $"目标 {nextGoal.GoalIndex} 需要修复。请先修复当前目标，再决定是否继续后续目标。"
                : hasMoreGoals
                    ? $"目标 {nextGoal.GoalIndex} 已完成。请确认后决定是否继续目标 {nextGoal.GoalIndex + 1}。"
                    : "所有迭代目标已完成。";
            await _metadataStore.UpdateProjectIterationSessionStatusAsync(
                details.Session.SessionId,
                sessionStatus,
                nextGoal.GoalIndex,
                sessionSummary,
                null,
                hasNeedsFix || hasMoreGoals ? null : now,
                CancellationToken.None);

            return new PrototypeIterationGoalExecutionResult(
                details.Session.SessionId,
                nextGoal.GoalId,
                runId,
                goalOutcome.ResultStatus,
                sessionSummary,
                nextGoal.GoalIndex,
                hasMoreGoals,
                sessionStatus);
        }
        catch (OperationCanceledException)
        {
            var failure = "本轮目标执行超时，请缩小目标范围后重试。";
            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                failure_code = "prototype_iteration_goal_timeout",
                session_id = details.Session.SessionId,
                goal_id = nextGoal.GoalId
            });
            await _metadataStore.CompleteRunAsync(runId, "failed", 408, "", $"Prototype iteration goal exceeded the {_executionTimeout.TotalSeconds:0} second timeout.", evidenceJson, CancellationToken.None);
            await _metadataStore.UpdateProjectIterationGoalStatusAsync(nextGoal.GoalId, "failed", failure, null, CancellationToken.None);
            await _metadataStore.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "paused_for_review", nextGoal.GoalIndex, failure, null, null, CancellationToken.None);
            return new PrototypeIterationGoalExecutionResult(details.Session.SessionId, nextGoal.GoalId, runId, "failed", failure, nextGoal.GoalIndex, true, "paused_for_review");
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            var failure = "本轮目标执行失败，请稍后重试。";
            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                failure_code = "prototype_iteration_goal_failed",
                session_id = details.Session.SessionId,
                goal_id = nextGoal.GoalId
            });
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.Message, evidenceJson, CancellationToken.None);
            await _metadataStore.UpdateProjectIterationGoalStatusAsync(nextGoal.GoalId, "failed", failure, null, CancellationToken.None);
            await _metadataStore.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "paused_for_review", nextGoal.GoalIndex, failure, null, null, CancellationToken.None);
            return new PrototypeIterationGoalExecutionResult(details.Session.SessionId, nextGoal.GoalId, runId, "failed", failure, nextGoal.GoalIndex, true, "paused_for_review");
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    private HostedProcessCommand BuildCodexCommand(string prompt, string outputPath, string model, string repositoryRoot)
    {
        return new HostedProcessCommand(
            ResolveCodexCommand(),
            [
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
                prompt
            ],
            repositoryRoot,
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["PHASEA_CODEX_DEFAULT_MODEL"] = model,
                ["PHASEA_CODEX_REASONING_EFFORT"] = ReasoningEffort
            });
    }

    private static string CreateShortRuntimeOutputPath(string runId)
    {
        var root = Path.Combine(Path.GetTempPath(), "phasea-codex-out", runId);
        Directory.CreateDirectory(root);
        return Path.Combine(root, "codex-output.txt");
    }

    private static string BuildPrompt(ProjectSnapshot project, ProjectIterationSessionSnapshot session, ProjectIterationGoalSnapshot goal)
    {
        return $"""
            你正在执行积木云 Phase A 的单目标迭代任务。

            Mandatory rules:
            - 这次只处理当前目标，不要顺手扩展到后续目标。
            - 直接围绕当前目标实现，不要先做任务恢复、仓库导览、规则总结或工作流巡检。
            - 除非当前目标明确要求，否则不要读取或总结 AGENTS.md、decision-logs、execution-plans、active-task、session recovery 一类文件。
            - 除非当前目标明确要求，否则不要修改 PhaseA.Platform/**、PhaseA.Platform.Tests/**、scripts/**、docs/** 这些云端控制台与工具链文件。
            - 优先用最小改动完成目标。
            - 如果被阻塞，直接报告阻塞原因，不要改无关基础设施。
            - 完成后输出面向浏览器用户的简明结果，不要包含路径、命令、脚本名、日志名、环境变量。
            - 如果当前目标过大，只完成最核心的一部分，并明确指出仍未完成的点。

            项目：
            - ProjectId: {project.ProjectId}
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}

            本次会话总目标：
            {session.OverallGoal}

            当前目标：
            - GoalIndex: {goal.GoalIndex}
            - Title: {goal.Title}
            - Description: {goal.Description}
            - AcceptanceHint: {goal.AcceptanceHint}

            你必须直接围绕这个目标做实现或修正，不要先做任务恢复、工作流巡检、仓库导览、规则总结，除非当前目标明确要求那样做。

            输出格式：
            STATUS: completed|needs_fix
            SUMMARY: 用 2-4 句说明当前目标是否完成，以及对用户有什么变化
            CHANGED: 用 1-3 行列出本轮实际完成的改动
            VERIFY: 用 1-3 行说明如何验证
            REMAINING: 若未完全完成，写出剩余问题；若已完成，写 none
            """;
    }

    private static string BuildGoalInput(ProjectIterationSessionSnapshot session, ProjectIterationGoalSnapshot goal, string now)
    {
        return $"""
            # Iteration Goal Input

            SessionId: {session.SessionId}
            OverallGoal: {session.OverallGoal}
            GoalIndex: {goal.GoalIndex}
            Title: {goal.Title}
            CreatedAtUtc: {now}

            ## Description

            {goal.Description}

            ## Acceptance Hint

            {goal.AcceptanceHint}
            """;
    }

    private static string BuildResultLog(
        ProjectIterationSessionSnapshot session,
        ProjectIterationGoalSnapshot goal,
        string runId,
        string model,
        string summary,
        HostedProcessResult codexResult,
        string codexOutput,
        string completedAt)
    {
        return $"""
            # Iteration Goal Result

            SessionId: {session.SessionId}
            GoalId: {goal.GoalId}
            GoalIndex: {goal.GoalIndex}
            RunId: {runId}
            Model: {model}
            CompletedAtUtc: {completedAt}

            ## Goal

            {goal.Title}

            {goal.Description}

            ## Summary

            {summary}

            ## Codex Stdout

            {codexResult.Stdout}

            ## Codex Stderr

            {codexResult.Stderr}

            ## Codex Output

            {codexOutput}
            """;
    }

    private static string BuildAssistantMessage(ProjectIterationGoalSnapshot goal, HostedProcessResult codexResult, string codexOutput)
    {
        var result = !string.IsNullOrWhiteSpace(codexOutput)
            ? codexOutput.Trim()
            : FirstNonEmpty(codexResult.Stdout, codexResult.Stderr, "本轮没有生成公开摘要。");
        var publicResult = PublicChatSanitizer.Sanitize(result);
        if (string.IsNullOrWhiteSpace(publicResult))
        {
            publicResult = "本轮没有生成公开摘要。";
        }

        return $"""
            目标 {goal.GoalIndex} 已执行。

            本轮目标：
            {goal.Title}

            完成报告：
            {publicResult}
            """;
    }

    private static IterationGoalOutcome DetermineGoalOutcome(string publicSummary, HostedProcessResult codexResult, string codexOutput)
    {
        var structuredStatus = ParseStructuredStatus(codexOutput)
            ?? ParseStructuredStatus(codexResult.Stdout)
            ?? ParseStructuredStatus(codexResult.Stderr);

        if (string.Equals(structuredStatus, "completed", StringComparison.OrdinalIgnoreCase))
        {
            return new IterationGoalOutcome("succeeded", "completed", true);
        }

        if (string.Equals(structuredStatus, "needs_fix", StringComparison.OrdinalIgnoreCase))
        {
            return new IterationGoalOutcome("needs_fix", "needs_fix", false);
        }

        if (codexResult.ExitCode != 0)
        {
            return new IterationGoalOutcome("needs_fix", "needs_fix", false);
        }

        var text = string.Join("\n", new[] { codexOutput, codexResult.Stdout, codexResult.Stderr }
                .Where(value => !string.IsNullOrWhiteSpace(value)))
            .Trim()
            .ToLowerInvariant();

        var needsFixMarkers = new[]
        {
            "未完成",
            "没能完成",
            "需要修复",
            "无法完成验证",
            "没能完成重跑验证",
            "先修复",
            "blocked by",
            "cannot complete",
            "could not complete",
            "not completed"
        };

        if (needsFixMarkers.Any(marker => text.Contains(marker.ToLowerInvariant(), StringComparison.Ordinal)))
        {
            return new IterationGoalOutcome("needs_fix", "needs_fix", false);
        }

        return new IterationGoalOutcome("succeeded", "completed", true);
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

    private sealed record IterationGoalOutcome(string GoalStatus, string ResultStatus, bool MarkCompleted);

    private static string ResolveCodexCommand()
    {
        var configured = Environment.GetEnvironmentVariable("PHASEA_CODEX_COMMAND");
        if (!string.IsNullOrWhiteSpace(configured))
        {
            return configured;
        }

        var candidates = new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "npm", "codex.cmd"),
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

    private static string ToSlash(string path)
    {
        return path.Replace('\\', '/');
    }
}
