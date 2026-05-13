using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeFeedbackIterationService
{
    private const string RunType = "prototype-feedback-iteration";
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly SkillActionCatalog _skillActionCatalog;

    public PrototypeFeedbackIterationService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner)
        : this(metadataStore, options, processRunner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog())
    {
    }

    public PrototypeFeedbackIterationService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        IProjectWorkspaceSeeder workspaceSeeder)
        : this(metadataStore, options, processRunner, workspaceSeeder, new SkillActionCatalog())
    {
    }

    public PrototypeFeedbackIterationService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        IProjectWorkspaceSeeder workspaceSeeder,
        SkillActionCatalog skillActionCatalog)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _workspaceSeeder = workspaceSeeder;
        _skillActionCatalog = skillActionCatalog;
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
            return new PrototypeFeedbackResult("", "missing_feedback", "请输入要正式提交的反馈。", []);
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            throw new InvalidOperationException("Project not found.");
        }

        if (!await HasSucceededPrototypeWorkflowAsync(project.ProjectId, cancellationToken))
        {
            return new PrototypeFeedbackResult("", "prototype_not_ready", "请先运行并完成 7 步可玩原型，再提交正式反馈。自由对话仍可使用。", []);
        }

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);

        var relativeDir = Path.Combine("logs", "phase-a-feedback", project.ProjectId, runId);
        var absoluteDir = Path.Combine(project.RepoPath, relativeDir);
        Directory.CreateDirectory(absoluteDir);

        var submittedRelativePath = ToSlash(Path.Combine(relativeDir, "submitted-feedback.md"));
        var resultRelativePath = ToSlash(Path.Combine(relativeDir, "result-log.md"));
        var submittedAbsolutePath = Path.Combine(project.RepoPath, submittedRelativePath.Replace('/', Path.DirectorySeparatorChar));
        var resultAbsolutePath = Path.Combine(project.RepoPath, resultRelativePath.Replace('/', Path.DirectorySeparatorChar));
        var now = DateTimeOffset.UtcNow.ToString("O");
        var skillAction = ResolveSkillAction(request.SkillActionId);

        await File.WriteAllTextAsync(
            submittedAbsolutePath,
            BuildSubmittedFeedback(project, runId, feedback, now, skillAction),
            Encoding.UTF8,
            cancellationToken);

        var model = PrototypeModelPolicy.Normalize(request.Model);
        var codexOutputRelativePath = ToSlash(Path.Combine(relativeDir, "codex-output.txt"));
        var codexOutputAbsolutePath = Path.Combine(project.RepoPath, codexOutputRelativePath.Replace('/', Path.DirectorySeparatorChar));
        var prompt = BuildCodexPrompt(project, runId, feedback, skillAction);
        var codexResult = await _processRunner.RunAsync(BuildCodexCommand(prompt, codexOutputAbsolutePath, model, project.RepoPath), cancellationToken);
        var codexOutput = File.Exists(codexOutputAbsolutePath)
            ? await File.ReadAllTextAsync(codexOutputAbsolutePath, Encoding.UTF8, cancellationToken)
            : "";
        var assistantMessage = BuildAssistantMessage(project, runId, model, feedback, codexResult, codexOutput, skillAction);
        await File.WriteAllTextAsync(
            resultAbsolutePath,
            BuildResultLog(project, runId, feedback, assistantMessage, model, codexResult, codexOutput, now, skillAction),
            Encoding.UTF8,
            cancellationToken);

        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "prototype-feedback-submission",
            submittedRelativePath,
            "Formal prototype feedback submission"), cancellationToken);
        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "prototype-feedback-result-log",
            resultRelativePath,
            "Formal prototype feedback result log"), cancellationToken);
        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "prototype-feedback-codex-output",
            codexOutputRelativePath,
            "Formal prototype feedback Codex output"), cancellationToken);

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            model,
            submitted_feedback = submittedRelativePath,
            result_log = resultRelativePath,
            codex_output = codexOutputRelativePath,
            skill_action_id = skillAction?.ActionId,
            skill_name = skillAction?.SkillName
        });
        await _metadataStore.CompleteRunAsync(runId, "completed", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceJson, cancellationToken);

        var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
        return new PrototypeFeedbackResult(runId, "completed", assistantMessage, artifacts);
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

    private static string BuildSubmittedFeedback(
        ProjectSnapshot project,
        string runId,
        string feedback,
        string submittedAt,
        SkillActionDefinition? skillAction)
    {
        return $"""
            # Prototype Feedback Submission

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
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryRoot);
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
            $"model_reasoning_effort=\"{PrototypeModelPolicy.DefaultReasoningEffort}\"",
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
                ["PHASEA_CODEX_REASONING_EFFORT"] = PrototypeModelPolicy.DefaultReasoningEffort
            });
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
            # Prototype Feedback Result

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

    private static string BuildAssistantMessage(
        ProjectSnapshot project,
        string runId,
        string model,
        string feedback,
        HostedProcessResult codexResult,
        string codexOutput,
        SkillActionDefinition? skillAction)
    {
        var result = !string.IsNullOrWhiteSpace(codexOutput)
            ? codexOutput.Trim()
            : FirstNonEmpty(codexResult.Stdout, codexResult.Stderr, "Codex did not return a final message.");
        var publicResult = PublicChatSanitizer.Sanitize(result);
        if (string.IsNullOrWhiteSpace(publicResult))
        {
            publicResult = "本轮优化已完成，但没有可展示的公开摘要。";
        }

        return $"""
            本轮继续优化已完成。

            本轮目标：
            {feedback}

            完成报告：
            {publicResult}

            下一步建议：
            请试玩当前原型，重点检查首分钟是否知道目标、操作反馈是否清晰、节奏是否顺畅、胜负条件是否明确。如果仍有明显问题，可以继续点击“同意继续优化”，我会把这些方向作为下一轮正式反馈继续交给 Codex 处理。
            """;
    }

    private static string BuildCodexPrompt(ProjectSnapshot project, string runId, string feedback, SkillActionDefinition? skillAction)
    {
        var skillInstruction = skillAction is null
            ? "能力模式：普通模式。不要激活任何额外 $skill，按通用原型迭代工程师方式处理。"
            : $"能力模式：{skillAction.Label}。请在执行本次正式反馈时使用 ${skillAction.SkillName} 的方法和判断框架，并将其用于代码、资源或文档优化决策。";

        return $"""
            你正在执行积木云 Phase A 的正式原型反馈迭代。
            {skillInstruction}

            目标：
            - 根据用户反馈继续优化当前 Godot 原型。
            - 可以修改当前仓库内与原型相关的代码、场景、测试和文档。
            - 保持 Prototype lane 范围，不进入 Chapter 3-7 正式交付流程。
            - 不要执行破坏性 git 操作。
            - 完成后总结：用户反馈、主要改动、验证结果、建议下一步。
            - 面向浏览器用户输出公开摘要，不要包含路径、命令、脚本名、日志名、环境变量或内部实现细节。
            - 如果还有值得继续优化的事项，请在结尾明确写“下一步建议：...”。如果没有明显建议，请写“下一步建议：暂无，建议进入试玩验收。”

            Project:
            - ProjectId: {project.ProjectId}
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}
            - FeedbackRunId: {runId}

            用户正式反馈：
            {feedback}
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
