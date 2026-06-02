using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed class GameDesignDocumentService
{
    private const string RunType = "game-design-gdd";
    private const string ArtifactType = "game-design-gdd";
    private const string OutputRelativePath = "docs/gdd/GDD.md";
    private const string ReasoningEffort = "high";
    private const int MaxMessageChars = 6000;
    private const int MaxAttachmentCount = 5;
    private const int MaxAttachmentChars = 12000;
    private static readonly TimeSpan DefaultExecutionTimeout = TimeSpan.FromMinutes(8);

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly IAiCodeMirrorBillingClient _billingClient;
    private readonly AiCodeMirrorKeyPoolService? _keyPoolService;
    private readonly HeavyRunnerQueueService _heavyRunnerQueue;
    private readonly TimeSpan _executionTimeout;

    public GameDesignDocumentService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        IProjectWorkspaceSeeder workspaceSeeder,
        IAiCodeMirrorBillingClient? billingClient = null,
        AiCodeMirrorKeyPoolService? keyPoolService = null,
        HeavyRunnerQueueService? heavyRunnerQueue = null,
        TimeSpan? executionTimeout = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _workspaceSeeder = workspaceSeeder;
        _billingClient = billingClient ?? new DisabledAiCodeMirrorBillingClient();
        _keyPoolService = keyPoolService;
        _heavyRunnerQueue = heavyRunnerQueue ?? new HeavyRunnerQueueService();
        _executionTimeout = executionTimeout ?? DefaultExecutionTimeout;
    }

    public async Task<GameDesignDocumentResult> CreateAsync(
        string accountId,
        string projectId,
        GameDesignDocumentRequest request,
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

        var message = (request.Message ?? "").Trim();
        if (message.Length > MaxMessageChars)
        {
            return Failure(project.ProjectId, "message_too_long", "聊天输入过长，请缩短后再创建 GDD。");
        }

        var attachments = NormalizeAttachments(request.Attachments);
        if (attachments.Count > MaxAttachmentCount)
        {
            return Failure(project.ProjectId, "too_many_attachments", "最多只能导入 5 个 TXT 参考文件。");
        }

        if (attachments.Any(item => (item.Content ?? "").Length > MaxAttachmentChars))
        {
            return Failure(project.ProjectId, "attachment_too_long", "单个 TXT 参考文件不能超过 12000 个字符。");
        }

        if (project.BootstrapStatus == "running" ||
            await _metadataStore.HasRunnerLockAsync(project.ProjectId, cancellationToken) ||
            await _metadataStore.HasActiveRunAsync(project.ProjectId, cancellationToken))
        {
            return Failure(project.ProjectId, "project_busy", "项目有后台任务正在执行，请稍后再创建 GDD。");
        }

        var projectRoot = Path.GetFullPath(project.RepoPath);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return Failure(project.ProjectId, "project_busy", "项目有后台任务正在执行，请稍后再创建 GDD。", runId);
        }

        await using var heavyRunnerLease = await _heavyRunnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, RunType, CancellationToken.None);
        await _metadataStore.MarkRunStartedAsync(runId, CancellationToken.None);
        await _metadataStore.UpdateRunProgressAsync(runId, "running", "prepare", "正在准备策划 GDD 文档。", CancellationToken.None);

        try
        {
            var relativeDir = ToSlash(Path.Combine("logs", "phase-a-gdd", project.ProjectId, runId));
            var promptRelativePath = ToSlash(Path.Combine(relativeDir, "gdd-prompt.md"));
            var codexOutputRelativePath = ToSlash(Path.Combine(relativeDir, "codex-output.txt"));
            var gddAbsolutePath = ResolveUnderProject(projectRoot, OutputRelativePath);
            var promptAbsolutePath = ResolveUnderProject(projectRoot, promptRelativePath);
            var codexOutputAbsolutePath = ResolveUnderProject(projectRoot, codexOutputRelativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(gddAbsolutePath)!);
            Directory.CreateDirectory(Path.GetDirectoryName(promptAbsolutePath)!);

            var chatMessages = await _metadataStore.ListProjectChatMessagesAsync(project.AccountId, project.ProjectId, ProjectChatHistoryService.DefaultLimit, CancellationToken.None);
            var memory = await _metadataStore.GetProjectChatMemoryAsync(project.AccountId, project.ProjectId, CancellationToken.None);
            var now = DateTimeOffset.UtcNow.ToString("O");
            var prompt = BuildPrompt(project, message, memory?.MemorySummary, chatMessages, attachments, now);
            await File.WriteAllTextAsync(promptAbsolutePath, prompt, Encoding.UTF8, CancellationToken.None);

            using var timeout = new CancellationTokenSource();
            timeout.CancelAfter(_executionTimeout);
            var model = PrototypeModelPolicy.Normalize(request.Model);
            var runtimeOutputPath = CreateShortRuntimeOutputPath(runId);
            await _metadataStore.UpdateRunProgressAsync(runId, "running", "codex", "BMAD 游戏策划正在创建 GDD.md。", CancellationToken.None);
            var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, CancellationToken.None);
            var billingKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
            var billingBefore = await _billingClient.CaptureAsync(billingKeyName, CancellationToken.None);
            var codexResult = await _processRunner.RunAsync(
                CodexHostedProcessCommandFactory.ApplyRuntime(BuildCodexCommand(prompt, runtimeOutputPath, model, project.RepoPath), runtimeCredential),
                timeout.Token);
            var providerBilling = new AiCodeMirrorBillingDelta(billingBefore, await _billingClient.CaptureAsync(billingKeyName, CancellationToken.None));

            if (File.Exists(runtimeOutputPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(codexOutputAbsolutePath)!);
                File.Copy(runtimeOutputPath, codexOutputAbsolutePath, overwrite: true);
            }

            if (!File.Exists(gddAbsolutePath) || new FileInfo(gddAbsolutePath).Length == 0)
            {
                var evidenceMissing = JsonSerializer.Serialize(new
                {
                    run_type = RunType,
                    failure_code = "gdd_not_created",
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    expected_file = OutputRelativePath
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", 424, codexResult.Stdout, codexResult.Stderr, evidenceMissing, CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", "gdd_not_created", "BMAD 已运行，但没有生成 GDD.md。", CancellationToken.None);
                return Failure(project.ProjectId, "gdd_not_created", "BMAD 已运行，但没有生成 GDD.md。", runId);
            }

            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-prompt", promptRelativePath, "Game design GDD generation prompt"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-codex-output", codexOutputRelativePath, "Game design GDD Codex output"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, ArtifactType, OutputRelativePath, "Game design document"), CancellationToken.None);

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                model,
                skill_name = "bmad-agent-game-designer",
                canonical_skill_name = "gds-agent-game-designer",
                output_file = OutputRelativePath,
                prompt = promptRelativePath,
                codex_output = codexOutputRelativePath,
                attachment_count = attachments.Count,
                chat_message_count = chatMessages.Count
            });
            await _metadataStore.CompleteRunAsync(runId, "succeeded", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceJson, CancellationToken.None);
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
                    route: RunType,
                    exitCode: codexResult.ExitCode,
                    providerBilling: providerBilling),
                CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "succeeded", "completed", "策划 GDD 文档已创建。", CancellationToken.None);
            var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, CancellationToken.None);
            return new GameDesignDocumentResult(
                project.ProjectId,
                runId,
                "succeeded",
                OutputRelativePath,
                $"/api/projects/{project.ProjectId}/gdd/download",
                artifacts,
                Summary: "策划 GDD 文档已创建。");
        }
        catch (OperationCanceledException)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 408, "", $"GDD generation exceeded the {_executionTimeout.TotalSeconds:0} second timeout.", "{}", CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "timeout", "创建 GDD 超时，请缩小输入后重试。", CancellationToken.None);
            return Failure(project.ProjectId, "timeout", "创建 GDD 超时，请缩小输入后重试。", runId);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.Message, "{}", CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "error", "创建 GDD 失败，请稍后重试。", CancellationToken.None);
            return Failure(project.ProjectId, "gdd_generation_failed", "创建 GDD 失败，请稍后重试。", runId);
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    public async Task<GameDesignDocumentReadResult?> ReadAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        var projectRoot = Path.GetFullPath(project.RepoPath);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        var absolutePath = ResolveUnderProject(projectRoot, OutputRelativePath);
        if (!File.Exists(absolutePath))
        {
            return null;
        }

        var info = new FileInfo(absolutePath);
        return new GameDesignDocumentReadResult(
            "GDD.md",
            "text/markdown; charset=utf-8",
            await File.ReadAllBytesAsync(absolutePath, cancellationToken),
            OutputRelativePath,
            info.Length,
            info.LastWriteTimeUtc.ToString("O"));
    }

    private static IReadOnlyList<TextAttachment> NormalizeAttachments(IReadOnlyList<TextAttachment>? attachments)
    {
        return (attachments ?? [])
            .Select(item => new TextAttachment(
                string.IsNullOrWhiteSpace(item.FileName) ? "reference.txt" : Path.GetFileName(item.FileName.Trim()),
                (item.Content ?? "").Trim()))
            .Where(item => !string.IsNullOrWhiteSpace(item.Content))
            .ToArray();
    }

    private static string BuildPrompt(
        ProjectSnapshot project,
        string message,
        string? memorySummary,
        IReadOnlyList<ProjectChatMessageSnapshot> chatMessages,
        IReadOnlyList<TextAttachment> attachments,
        string now)
    {
        return $"""
            请使用 $bmad-agent-game-designer 这个 BMAD 游戏策划 skill。它兼容 $gds-agent-game-designer 的游戏设计师工作流。

            你正在积木云 Phase A 的项目级 workspace 中运行。本次任务是创建或更新策划 GDD 文档，必须写入固定文件：
            docs/gdd/GDD.md

            Mandatory rules:
            - 使用 BMAD 游戏策划角色的判断方式整理玩法愿景、核心循环、系统、内容、UI/HUD、资产需求、验收建议。
            - 只允许创建或更新 docs/gdd/GDD.md，不要修改其他文件。
            - 不要创建 gdd.md、GDD.txt 或其他替代文件。
            - 可以基于当前 LLM 会话隐式上下文作补充，但必须优先使用下面的显式服务器聊天记录、当前输入和导入 TXT 参考文件。
            - 如果信息不足，仍然生成可继续迭代的 GDD，并在文档中标记 Assumptions 和 Open Questions。
            - 输出文档语言使用中文。
            - 最终回复只用 2-4 句说明 GDD 是否创建成功，不要输出整份文档。

            项目信息：
            - ProjectId: {project.ProjectId}
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}
            - CreatedAtUtc: {now}

            当前聊天输入：
            {EmptyAsNone(message)}

            项目聊天记忆摘要：
            {EmptyAsNone(memorySummary)}

            服务器聊天记录（最近 {chatMessages.Count} 条）：
            {FormatChatMessages(chatMessages)}

            导入 TXT 参考文件：
            {FormatAttachments(attachments)}

            请现在创建或更新 docs/gdd/GDD.md。
            """;
    }

    private HostedProcessCommand BuildCodexCommand(string prompt, string outputPath, string model, string repositoryRoot)
    {
        return CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
            repositoryRoot,
            outputPath,
            prompt,
            model,
            ReasoningEffort,
            ExtraEnvironment: new Dictionary<string, string>
            {
                ["PATH"] = CodexHostedProcessCommandFactory.ResolvePathWithRipgrep()
            }));
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

    private static string FormatChatMessages(IReadOnlyList<ProjectChatMessageSnapshot> messages)
    {
        if (messages.Count == 0)
        {
            return "(none)";
        }

        var builder = new StringBuilder();
        foreach (var message in messages)
        {
            builder.AppendLine($"[{message.CreatedUtc}] {message.Role} ({message.Kind ?? "chat"}):");
            builder.AppendLine(TrimForPrompt(PublicChatSanitizer.Sanitize(message.Content), 3000));
            builder.AppendLine();
        }

        return builder.ToString().Trim();
    }

    private static string FormatAttachments(IReadOnlyList<TextAttachment> attachments)
    {
        if (attachments.Count == 0)
        {
            return "(none)";
        }

        var builder = new StringBuilder();
        foreach (var attachment in attachments)
        {
            builder.AppendLine($"## {attachment.FileName}");
            builder.AppendLine(TrimForPrompt(attachment.Content, MaxAttachmentChars));
            builder.AppendLine();
        }

        return builder.ToString().Trim();
    }

    private static string EmptyAsNone(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? "(none)" : value.Trim();
    }

    private static string TrimForPrompt(string? value, int maxChars = 4000)
    {
        var text = value ?? "";
        return text.Length <= maxChars ? text : text[..maxChars] + "\n...[truncated]";
    }

    private static string ResolveUnderProject(string projectRoot, string relativePath)
    {
        var full = Path.GetFullPath(Path.Combine(projectRoot, relativePath.Replace('/', Path.DirectorySeparatorChar)));
        if (!WorkspacePathPolicy.IsUnderRoot(projectRoot, full))
        {
            throw new InvalidOperationException("Resolved path escaped the project root.");
        }

        return full;
    }

    private static string CreateShortRuntimeOutputPath(string runId)
    {
        var root = Path.Combine(Path.GetTempPath(), "phasea-codex-out", runId);
        Directory.CreateDirectory(root);
        return Path.Combine(root, "gdd-output.txt");
    }

    private static string ToSlash(string path)
    {
        return path.Replace('\\', '/');
    }

    private static GameDesignDocumentResult Failure(string projectId, string failureCode, string summary, string runId = "")
    {
        return new GameDesignDocumentResult(projectId, runId, "failed", OutputRelativePath, "", [], failureCode, summary);
    }
}
