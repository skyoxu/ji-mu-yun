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

        if (!await HasSucceededPrototypeWorkflowAsync(project.ProjectId, cancellationToken))
        {
            return new PrototypeFeedbackResult("", "prototype_not_ready", "请先完成 7 步可玩原型，再使用快速修复。", []);
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

            await File.WriteAllTextAsync(
                submittedAbsolutePath,
                BuildSubmittedFeedback(project, runId, feedback, now, skillAction),
                Encoding.UTF8,
                CancellationToken.None);

            var model = PrototypeModelPolicy.Normalize(request.Model);
            using var timeout = new CancellationTokenSource();
            timeout.CancelAfter(_executionTimeout);
            var prompt = BuildCodexPrompt(project, runId, feedback, skillAction);
            await SetProgressAsync(runId, "running", "codex", "Codex 正在执行快速修复。", CancellationToken.None);
            var codexResult = await _processRunner.RunAsync(BuildCodexCommand(prompt, codexOutputAbsolutePath, model, project.RepoPath), timeout.Token);
            var codexOutput = File.Exists(codexOutputAbsolutePath)
                ? await File.ReadAllTextAsync(codexOutputAbsolutePath, Encoding.UTF8, CancellationToken.None)
                : "";
            var assistantMessage = BuildAssistantMessage(feedback, codexResult, codexOutput);
            await SetProgressAsync(runId, "running", "finalize", "快速修复结果已返回，正在整理日志。", CancellationToken.None);

            await File.WriteAllTextAsync(
                resultAbsolutePath,
                BuildResultLog(project, runId, feedback, assistantMessage, model, codexResult, codexOutput, now, skillAction),
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
                skill_action_id = skillAction?.ActionId,
                skill_name = skillAction?.SkillName,
                quick_fix = true
            });
            await _metadataStore.CompleteRunAsync(runId, "completed", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceJson, CancellationToken.None);
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
        SkillActionDefinition? skillAction)
    {
        return $"""
            # Prototype Quick Fix Submission

            Project: {project.Name}
            ProjectId: {project.ProjectId}
            RunId: {runId}
            SubmittedAtUtc: {submittedAt}
            SkillMode: {SkillModeLabel(skillAction)}

            ## Feedback

            {feedback}
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
            prompt
        };

        return new HostedProcessCommand(
            ResolveCodexCommand(),
            arguments,
            repositoryRoot,
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["PHASEA_CODEX_DEFAULT_MODEL"] = model,
                ["PHASEA_CODEX_REASONING_EFFORT"] = ReasoningEffort
            });
    }

    private static string BuildCodexPrompt(ProjectSnapshot project, string runId, string feedback, SkillActionDefinition? skillAction)
    {
        var skillInstruction = skillAction is null
            ? "能力模式：普通模式。"
            : $"能力模式：{skillAction.Label}。执行时使用 ${skillAction.SkillName} 的方法。";

        return $"""
            你正在执行积木云 Phase A 的快速修复任务。
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

    private static string BuildAssistantMessage(string feedback, HostedProcessResult codexResult, string codexOutput)
    {
        var result = !string.IsNullOrWhiteSpace(codexOutput)
            ? codexOutput.Trim()
            : FirstNonEmpty(codexResult.Stdout, codexResult.Stderr, "Quick fix did not return a final message.");
        var publicResult = PublicChatSanitizer.Sanitize(result);
        if (string.IsNullOrWhiteSpace(publicResult))
        {
            publicResult = "快速修复已执行，但没有可展示的公开摘要。";
        }

        return $"""
            快速修复已完成。
            本轮目标：
            {feedback}

            完成报告：
            {publicResult}
            """;
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
        SkillActionDefinition? skillAction)
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

            ## Submitted Feedback

            {feedback}

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

    private static string ToSlash(string path)
    {
        return path.Replace('\\', '/');
    }
}
