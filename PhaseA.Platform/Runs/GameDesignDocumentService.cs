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
    private const string OutlineRelativePath = "docs/gdd/gdd-outline.json";
    private const string ReferenceRelativeDir = "docs/gdd/references";
    private const string ReasoningEffort = "high";
    private const int MaxMessageChars = 6000;
    private const int MaxAttachmentCount = 5;
    private const int MaxAttachmentChars = 12000;
    private static readonly TimeSpan DefaultExecutionTimeout = TimeSpan.FromMinutes(20);

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
            return Failure(project.ProjectId, "message_too_long", "\u804a\u5929\u8f93\u5165\u8fc7\u957f\uff0c\u8bf7\u7f29\u77ed\u540e\u518d\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u3002");
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
            return Failure(project.ProjectId, "project_busy", "\u9879\u76ee\u6709\u540e\u53f0\u4efb\u52a1\u6b63\u5728\u6267\u884c\uff0c\u8bf7\u7a0d\u540e\u518d\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u3002");
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
            return Failure(project.ProjectId, "project_busy", "\u9879\u76ee\u6709\u540e\u53f0\u4efb\u52a1\u6b63\u5728\u6267\u884c\uff0c\u8bf7\u7a0d\u540e\u518d\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u3002", runId);
        }

        await using var heavyRunnerLease = await _heavyRunnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, RunType, CancellationToken.None);
        await _metadataStore.MarkRunStartedAsync(runId, heavyRunnerLease.QueuePositionAtStart, CancellationToken.None);
        await _metadataStore.UpdateRunProgressAsync(runId, "running", "prepare", "\u6b63\u5728\u51c6\u5907\u7b56\u5212\u5927\u7eb2\u3002", CancellationToken.None);

        try
        {
            var relativeDir = ToSlash(Path.Combine("logs", "phase-a-gdd", project.ProjectId, runId));
            var promptRelativePath = ToSlash(Path.Combine(relativeDir, "gdd-prompt.md"));
            var codexOutputRelativePath = ToSlash(Path.Combine(relativeDir, "codex-output.txt"));
            var gddAbsolutePath = ResolveUnderProject(projectRoot, OutputRelativePath);
            var outlineAbsolutePath = ResolveUnderProject(projectRoot, OutlineRelativePath);
            var promptAbsolutePath = ResolveUnderProject(projectRoot, promptRelativePath);
            var codexOutputAbsolutePath = ResolveUnderProject(projectRoot, codexOutputRelativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(gddAbsolutePath)!);
            Directory.CreateDirectory(Path.GetDirectoryName(outlineAbsolutePath)!);
            Directory.CreateDirectory(Path.GetDirectoryName(promptAbsolutePath)!);

            var chatMessages = await _metadataStore.ListProjectChatMessagesAsync(project.AccountId, project.ProjectId, ProjectChatHistoryService.DefaultLimit, CancellationToken.None);
            var memory = await _metadataStore.GetProjectChatMemoryAsync(project.AccountId, project.ProjectId, CancellationToken.None);
            var now = DateTimeOffset.UtcNow.ToString("O");
            var persistedAttachments = await PersistAttachmentsAsync(projectRoot, runId, attachments, CancellationToken.None);
            var historicalAttachments = LoadHistoricalAttachments(projectRoot, persistedAttachments);
            var prompt = BuildPrompt(project, message, memory?.MemorySummary, chatMessages, persistedAttachments, historicalAttachments, now);
            await File.WriteAllTextAsync(promptAbsolutePath, prompt, Encoding.UTF8, CancellationToken.None);

            using var timeout = new CancellationTokenSource();
            timeout.CancelAfter(_executionTimeout);
            var model = PrototypeModelPolicy.Normalize(request.Model);
            var runtimeOutputPath = CreateShortRuntimeOutputPath(runId);
            await _metadataStore.UpdateRunProgressAsync(runId, "running", "codex", "\u6b63\u5728\u4f7f\u7528 BMAD \u6e38\u620f\u7b56\u5212\u5927\u5e08\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u3002", CancellationToken.None);
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

            if (codexResult.ExitCode != 0)
            {
                var evidenceFailed = JsonSerializer.Serialize(new
                {
                    run_type = RunType,
                    failure_code = "codex_failed",
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    expected_file = OutlineRelativePath
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceFailed, CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", "codex_failed", "\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff0cBMAD \u8fd0\u884c\u672a\u6210\u529f\u5b8c\u6210\u3002", CancellationToken.None);
                await RecordCodexAuditAsync(runId, RunType, model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return Failure(project.ProjectId, "codex_failed", "\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff0c\u8bf7\u67e5\u770b\u8fd0\u884c\u8bb0\u5f55\u540e\u91cd\u8bd5\u3002", runId);
            }

            if (!File.Exists(outlineAbsolutePath) || new FileInfo(outlineAbsolutePath).Length == 0)
            {
                var evidenceMissing = JsonSerializer.Serialize(new
                {
                    run_type = RunType,
                    failure_code = "gdd_outline_not_created",
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    expected_file = OutlineRelativePath
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", 424, codexResult.Stdout, codexResult.Stderr, evidenceMissing, CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", "gdd_outline_not_created", "BMAD \u5df2\u8fd0\u884c\uff0c\u4f46\u6ca1\u6709\u751f\u6210\u7b56\u5212\u5927\u7eb2\u6587\u4ef6\u3002", CancellationToken.None);
                await RecordCodexAuditAsync(runId, RunType, model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return Failure(project.ProjectId, "gdd_outline_not_created", "BMAD \u5df2\u8fd0\u884c\uff0c\u4f46\u6ca1\u6709\u751f\u6210\u7b56\u5212\u5927\u7eb2\u6587\u4ef6\u3002", runId);
            }

            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-prompt", promptRelativePath, "Game design GDD generation prompt"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-codex-output", codexOutputRelativePath, "Game design GDD Codex output"), CancellationToken.None);
            await NormalizeOutlineFileAsync(outlineAbsolutePath, gddAbsolutePath, CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, ArtifactType, OutputRelativePath, "Game design document"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-outline", OutlineRelativePath, "Game design outline"), CancellationToken.None);

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                model,
                skill_name = "bmad-agent-game-designer",
                canonical_skill_name = "gds-agent-game-designer",
                output_file = OutputRelativePath,
                outline_file = OutlineRelativePath,
                prompt = promptRelativePath,
                codex_output = codexOutputRelativePath,
                attachment_count = persistedAttachments.Count,
                historical_attachment_count = historicalAttachments.Count,
                chat_message_count = chatMessages.Count
            });
            await _metadataStore.CompleteRunAsync(runId, "succeeded", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceJson, CancellationToken.None);
            await RecordCodexAuditAsync(runId, RunType, model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "succeeded", "completed", "\u7b56\u5212\u5927\u7eb2\u5df2\u521b\u5efa\u3002", CancellationToken.None);
            var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, CancellationToken.None);
            return new GameDesignDocumentResult(
                project.ProjectId,
                runId,
                "succeeded",
                OutputRelativePath,
                $"/api/projects/{project.ProjectId}/gdd/download",
                artifacts,
                Summary: "\u7b56\u5212\u5927\u7eb2\u5df2\u521b\u5efa\u3002");
        }
        catch (OperationCanceledException)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 408, "", $"GDD generation exceeded the {_executionTimeout.TotalSeconds:0} second timeout.", "{}", CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "timeout", "\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u8d85\u65f6\uff0c\u8bf7\u7f29\u5c0f\u8f93\u5165\u540e\u91cd\u8bd5\u3002", CancellationToken.None);
            return Failure(project.ProjectId, "timeout", "\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u8d85\u65f6\uff0c\u8bf7\u7f29\u5c0f\u8f93\u5165\u540e\u91cd\u8bd5\u3002", runId);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.Message, "{}", CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "error", "\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002", CancellationToken.None);
            return Failure(project.ProjectId, "gdd_outline_generation_failed", "\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002", runId);
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

    public async Task<GameDesignOutlineReadResult?> ReadOutlineAsync(
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

        var outlinePath = ResolveUnderProject(projectRoot, OutlineRelativePath);
        if (!File.Exists(outlinePath))
        {
            return null;
        }

        var document = await ReadOutlineDocumentAsync(outlinePath, cancellationToken);
        var info = new FileInfo(outlinePath);
        return new GameDesignOutlineReadResult(
            project.ProjectId,
            document.Title,
            document.Summary,
            OutlineRelativePath,
            info.LastWriteTimeUtc.ToString("O"),
            document.Sections);
    }

    public async Task<GameDesignDocumentReadResult?> ExportOutlineMarkdownAsync(
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

        var outlinePath = ResolveUnderProject(projectRoot, OutlineRelativePath);
        if (!File.Exists(outlinePath))
        {
            return null;
        }

        var gddPath = ResolveUnderProject(projectRoot, OutputRelativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(gddPath)!);
        await NormalizeOutlineFileAsync(outlinePath, gddPath, cancellationToken);
        return await ReadAsync(accountId, projectId, cancellationToken);
    }

    public async Task<GameDesignDocumentResult> GenerateSectionAsync(
        string accountId,
        string projectId,
        GameDesignOutlineSectionRequest request,
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

        var sectionId = (request.SectionId ?? "").Trim();
        var message = (request.Message ?? "").Trim();
        if (string.IsNullOrWhiteSpace(sectionId))
        {
            return Failure(project.ProjectId, "section_id_required", "\u8bf7\u5148\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u3002");
        }

        if (message.Length > MaxMessageChars)
        {
            return Failure(project.ProjectId, "message_too_long", "\u8f93\u5165\u8fc7\u957f\uff0c\u8bf7\u7f29\u77ed\u540e\u518d\u751f\u6210\u6761\u76ee\u5185\u5bb9\u3002");
        }

        if (project.BootstrapStatus == "running" ||
            await _metadataStore.HasRunnerLockAsync(project.ProjectId, cancellationToken) ||
            await _metadataStore.HasActiveRunAsync(project.ProjectId, cancellationToken))
        {
            return Failure(project.ProjectId, "project_busy", "\u9879\u76ee\u6709\u540e\u53f0\u4efb\u52a1\u6b63\u5728\u6267\u884c\uff0c\u8bf7\u7a0d\u540e\u518d\u751f\u6210\u6761\u76ee\u5185\u5bb9\u3002");
        }

        var projectRoot = Path.GetFullPath(project.RepoPath);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        var outlineAbsolutePath = ResolveUnderProject(projectRoot, OutlineRelativePath);
        var gddAbsolutePath = ResolveUnderProject(projectRoot, OutputRelativePath);
        if (!File.Exists(outlineAbsolutePath))
        {
            return Failure(project.ProjectId, "outline_not_found", "\u8bf7\u5148\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u3002");
        }

        var outline = await ReadOutlineDocumentAsync(outlineAbsolutePath, cancellationToken);
        var section = outline.Sections.FirstOrDefault(item => string.Equals(item.Id, sectionId, StringComparison.OrdinalIgnoreCase));
        if (section is null)
        {
            return Failure(project.ProjectId, "section_not_found", "\u6ca1\u6709\u627e\u5230\u8fd9\u4e2a\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u3002");
        }

        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, "game-design-gdd-section", cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return Failure(project.ProjectId, "project_busy", "\u9879\u76ee\u6709\u540e\u53f0\u4efb\u52a1\u6b63\u5728\u6267\u884c\uff0c\u8bf7\u7a0d\u540e\u518d\u751f\u6210\u6761\u76ee\u5185\u5bb9\u3002", runId);
        }

        await using var heavyRunnerLease = await _heavyRunnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, "game-design-gdd-section", CancellationToken.None);
        await _metadataStore.MarkRunStartedAsync(runId, heavyRunnerLease.QueuePositionAtStart, CancellationToken.None);
        await _metadataStore.UpdateRunProgressAsync(runId, "running", "codex", "BMAD \u6e38\u620f\u7b56\u5212\u6b63\u5728\u586b\u5145\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u3002", CancellationToken.None);

        try
        {
            var relativeDir = ToSlash(Path.Combine("logs", "phase-a-gdd", project.ProjectId, runId));
            var promptRelativePath = ToSlash(Path.Combine(relativeDir, "gdd-section-prompt.md"));
            var codexOutputRelativePath = ToSlash(Path.Combine(relativeDir, "codex-output.txt"));
            var promptAbsolutePath = ResolveUnderProject(projectRoot, promptRelativePath);
            var codexOutputAbsolutePath = ResolveUnderProject(projectRoot, codexOutputRelativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(promptAbsolutePath)!);

            var memory = await _metadataStore.GetProjectChatMemoryAsync(project.AccountId, project.ProjectId, CancellationToken.None);
            var historicalAttachments = LoadHistoricalAttachments(projectRoot, []);
            var prompt = BuildSectionPrompt(project, outline, section, message, memory?.MemorySummary, historicalAttachments, DateTimeOffset.UtcNow.ToString("O"));
            await File.WriteAllTextAsync(promptAbsolutePath, prompt, Encoding.UTF8, CancellationToken.None);

            using var timeout = new CancellationTokenSource();
            timeout.CancelAfter(_executionTimeout);
            var model = PrototypeModelPolicy.Normalize(request.Model);
            var runtimeOutputPath = CreateShortRuntimeOutputPath(runId);
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

            if (codexResult.ExitCode != 0)
            {
                var evidenceFailed = JsonSerializer.Serialize(new
                {
                    run_type = "game-design-gdd-section",
                    failure_code = "codex_failed",
                    section_id = section.Id,
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    expected_file = OutlineRelativePath
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceFailed, CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", "codex_failed", "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff0cBMAD \u8fd0\u884c\u672a\u6210\u529f\u5b8c\u6210\u3002", CancellationToken.None);
                await RecordCodexAuditAsync(runId, "game-design-gdd-section", model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return Failure(project.ProjectId, "codex_failed", "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff0c\u8bf7\u67e5\u770b\u8fd0\u884c\u8bb0\u5f55\u540e\u91cd\u8bd5\u3002", runId);
            }

            await NormalizeOutlineFileAsync(outlineAbsolutePath, gddAbsolutePath, CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-prompt", promptRelativePath, "Game design outline section prompt"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-output", codexOutputRelativePath, "Game design outline section Codex output"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-outline", OutlineRelativePath, "Game design outline"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, ArtifactType, OutputRelativePath, "Game design document"), CancellationToken.None);

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = "game-design-gdd-section",
                model,
                skill_name = "bmad-agent-game-designer",
                section_id = section.Id,
                outline_file = OutlineRelativePath,
                output_file = OutputRelativePath,
                prompt = promptRelativePath,
                codex_output = codexOutputRelativePath,
                historical_attachment_count = historicalAttachments.Count
            });
            await _metadataStore.CompleteRunAsync(runId, "succeeded", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceJson, CancellationToken.None);
            await RecordCodexAuditAsync(runId, "game-design-gdd-section", model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "succeeded", "completed", "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u5185\u5bb9\u5df2\u66f4\u65b0\u3002", CancellationToken.None);
            var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, CancellationToken.None);
            return new GameDesignDocumentResult(project.ProjectId, runId, "succeeded", OutlineRelativePath, $"/gdd-outline?projectId={project.ProjectId}", artifacts, Summary: "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u5185\u5bb9\u5df2\u66f4\u65b0\u3002");
        }
        catch (OperationCanceledException)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 408, "", $"GDD outline section generation exceeded the {_executionTimeout.TotalSeconds:0} second timeout.", "{}", CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "timeout", "\u751f\u6210\u6761\u76ee\u5185\u5bb9\u8d85\u65f6\uff0c\u8bf7\u7f29\u5c0f\u8f93\u5165\u540e\u91cd\u8bd5\u3002", CancellationToken.None);
            return Failure(project.ProjectId, "timeout", "\u751f\u6210\u6761\u76ee\u5185\u5bb9\u8d85\u65f6\uff0c\u8bf7\u7f29\u5c0f\u8f93\u5165\u540e\u91cd\u8bd5\u3002", runId);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.Message, "{}", CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "error", "\u751f\u6210\u6761\u76ee\u5185\u5bb9\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002", CancellationToken.None);
            return Failure(project.ProjectId, "gdd_section_generation_failed", "\u751f\u6210\u6761\u76ee\u5185\u5bb9\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002", runId);
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    private static string BuildPrompt(
        ProjectSnapshot project,
        string message,
        string? memorySummary,
        IReadOnlyList<ProjectChatMessageSnapshot> chatMessages,
        IReadOnlyList<TextAttachment> currentAttachments,
        IReadOnlyList<TextAttachment> historicalAttachments,
        string now)
    {
        return $$"""
            Use the $bmad-agent-game-designer BMAD game design skill. You may use the BMAD/GDS GDD template as structural inspiration, but this run creates only a planning outline and skeleton, not full prose.

            You are running inside a Phase A project workspace. Create or update exactly this UTF-8 JSON file:
            docs/gdd/gdd-outline.json

            Do not modify unrelated files. The JSON schema must be:
            {
              "title": "Game design outline title",
              "summary": "One to three sentence project design summary",
              "sections": [
                { "id": "core-loop", "title": "Core Loop", "skeleton": "Questions, boundaries, and design intent for this section", "content": "" }
              ]
            }

            Priority and conflict rules:
            1. Current user input has the highest priority.
            2. Current uploaded TXT references have the next priority.
            3. Historical uploaded TXT references have medium priority.
            4. Project memory, server chat history, and implicit LLM context have low priority.
            If sources conflict, keep the higher-priority source and discard or ignore conflicting lower-priority details.

            Outline requirements:
            - Write user-facing fields in Chinese.
            - Create 6 to 12 sections covering vision, target player, core loop, player progression, world/levels, combat/interaction, UI/HUD, content and asset needs, prototype acceptance criteria, and open questions.
            - Every section.content must be an empty string. Section content is generated later by the section route.
            - section.id must be stable, lowercase, hyphenated, and unique.
            - Final assistant reply should be 2 to 4 short sentences only; do not print the whole JSON.

            Project:
            - ProjectId: {{project.ProjectId}}
            - Name: {{project.Name}}
            - GameName: {{project.GameName}}
            - GameType: {{project.GameTypeSource}}
            - CreatedAtUtc: {{now}}

            Current user input, highest priority:
            {{EmptyAsNone(message)}}

            Current uploaded TXT references, second priority:
            {{FormatAttachments(currentAttachments)}}

            Historical uploaded TXT references, medium priority:
            {{FormatAttachments(historicalAttachments)}}

            Project chat memory, low priority:
            {{EmptyAsNone(memorySummary)}}

            Server chat history, low priority, latest {{chatMessages.Count}} messages:
            {{FormatChatMessages(chatMessages)}}

            Create or update docs/gdd/gdd-outline.json now.
            """;
    }

    private Task RecordCodexAuditAsync(
        string runId,
        string operation,
        string model,
        string projectId,
        HostedProcessResult codexResult,
        AiCodeMirrorBillingDelta providerBilling,
        CancellationToken cancellationToken)
    {
        return _metadataStore.RecordRunLlmAuditAsync(
            runId,
            "codex-cli",
            null,
            model,
            LlmUsageAuditJson.BuildCodexUsageJson(
                operation: operation,
                model: model,
                tokenUsage: CodexUsageExtractor.Extract(codexResult.Stdout, codexResult.Stderr),
                runType: operation,
                projectId: projectId,
                route: operation,
                exitCode: codexResult.ExitCode,
                providerBilling: providerBilling),
            cancellationToken);
    }

    private static string BuildSectionPrompt(
        ProjectSnapshot project,
        GameDesignOutlineDocument outline,
        GameDesignOutlineSection section,
        string message,
        string? memorySummary,
        IReadOnlyList<TextAttachment> historicalAttachments,
        string now)
    {
        return $$"""
            Use the $bmad-agent-game-designer BMAD game design skill. This run fills exactly one planning outline section. Do not expand other sections.

            Fixed file: docs/gdd/gdd-outline.json
            Read and update only the section whose id is "{{section.Id}}". Replace only that section.content field. Do not change title, skeleton, or other sections.

            Priority and conflict rules:
            1. The editor input below has the highest priority.
            2. Historical uploaded TXT references have medium priority.
            3. Project memory and implicit LLM context have low priority.
            If sources conflict, keep the higher-priority source and discard or ignore conflicting lower-priority details.

            Scope:
            - Project: {{project.GameName}} / {{project.GameTypeSource}}
            - Outline title: {{outline.Title}}
            - Section id: {{section.Id}}
            - Section title: {{section.Title}}
            - Section skeleton: {{section.Skeleton}}
            - Existing section content: {{EmptyAsNone(section.Content)}}
            - Time: {{now}}

            Editor input, highest priority:
            {{EmptyAsNone(message)}}

            Historical uploaded TXT references, medium priority:
            {{FormatAttachments(historicalAttachments)}}

            Project chat memory, low priority:
            {{EmptyAsNone(memorySummary)}}

            Requirements:
            - Write section.content in Chinese.
            - Stay inside this section's scope.
            - content may contain compact headings, bullet points, rules, and acceptance notes.
            - Final assistant reply should be 1 to 3 short sentences only; do not print the whole JSON.
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

    private static async Task<IReadOnlyList<TextAttachment>> PersistAttachmentsAsync(
        string projectRoot,
        string runId,
        IReadOnlyList<TextAttachment> attachments,
        CancellationToken cancellationToken)
    {
        if (attachments.Count == 0)
        {
            return [];
        }

        var result = new List<TextAttachment>();
        var dir = ResolveUnderProject(projectRoot, ReferenceRelativeDir);
        Directory.CreateDirectory(dir);
        var stamp = DateTimeOffset.UtcNow.ToString("yyyyMMddHHmmss");
        for (var index = 0; index < attachments.Count; index++)
        {
            var attachment = attachments[index];
            var safeName = SafeFileName(string.IsNullOrWhiteSpace(attachment.FileName) ? $"reference-{index + 1}.txt" : attachment.FileName!);
            var fileName = $"{stamp}-{runId[..Math.Min(8, runId.Length)]}-{index + 1:00}-{safeName}";
            if (!fileName.EndsWith(".txt", StringComparison.OrdinalIgnoreCase))
            {
                fileName += ".txt";
            }

            var path = Path.Combine(dir, fileName);
            await File.WriteAllTextAsync(path, attachment.Content ?? "", Encoding.UTF8, cancellationToken);
            result.Add(new TextAttachment(fileName, attachment.Content));
        }

        return result;
    }

    private static IReadOnlyList<TextAttachment> LoadHistoricalAttachments(string projectRoot, IReadOnlyList<TextAttachment> exclude)
    {
        var dir = ResolveUnderProject(projectRoot, ReferenceRelativeDir);
        if (!Directory.Exists(dir))
        {
            return [];
        }

        var excluded = exclude.Select(item => item.FileName ?? "").ToHashSet(StringComparer.OrdinalIgnoreCase);
        return Directory.EnumerateFiles(dir, "*.txt", SearchOption.TopDirectoryOnly)
            .OrderByDescending(File.GetLastWriteTimeUtc)
            .Where(path => !excluded.Contains(Path.GetFileName(path)))
            .Take(20)
            .Select(path => new TextAttachment(Path.GetFileName(path), TrimForPrompt(File.ReadAllText(path, Encoding.UTF8), MaxAttachmentChars)))
            .Where(item => !string.IsNullOrWhiteSpace(item.Content))
            .ToArray();
    }

    private static async Task<GameDesignOutlineDocument> ReadOutlineDocumentAsync(string outlinePath, CancellationToken cancellationToken)
    {
        await using var stream = File.OpenRead(outlinePath);
        var document = await JsonSerializer.DeserializeAsync<GameDesignOutlineDocument>(stream, new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            ReadCommentHandling = JsonCommentHandling.Skip,
            AllowTrailingCommas = true
        }, cancellationToken);
        return NormalizeOutlineDocument(document);
    }

    private static async Task NormalizeOutlineFileAsync(string outlinePath, string gddPath, CancellationToken cancellationToken)
    {
        var document = await ReadOutlineDocumentAsync(outlinePath, cancellationToken);
        await File.WriteAllTextAsync(outlinePath, JsonSerializer.Serialize(document, new JsonSerializerOptions
        {
            WriteIndented = true
        }), Encoding.UTF8, cancellationToken);
        await File.WriteAllTextAsync(gddPath, RenderOutlineMarkdown(document), Encoding.UTF8, cancellationToken);
    }

    private static GameDesignOutlineDocument NormalizeOutlineDocument(GameDesignOutlineDocument? document)
    {
        var title = string.IsNullOrWhiteSpace(document?.Title) ? "\u6e38\u620f\u7b56\u5212\u5927\u7eb2" : document!.Title.Trim();
        var summary = string.IsNullOrWhiteSpace(document?.Summary) ? "\u5f85\u8865\u5145\u3002" : document!.Summary.Trim();
        var sections = (document?.Sections ?? [])
            .Select((item, index) => new GameDesignOutlineSection(
                string.IsNullOrWhiteSpace(item.Id) ? $"section-{index + 1:00}" : Slug(item.Id),
                string.IsNullOrWhiteSpace(item.Title) ? $"\u7b56\u5212\u6761\u76ee {index + 1}" : item.Title.Trim(),
                string.IsNullOrWhiteSpace(item.Skeleton) ? "\u5f85\u8865\u5145\u9aa8\u67b6\u3002" : item.Skeleton.Trim(),
                item.Content?.Trim() ?? ""))
            .GroupBy(item => item.Id, StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .ToArray();
        if (sections.Length == 0)
        {
            sections = [new GameDesignOutlineSection("core-loop", "\u6838\u5fc3\u5faa\u73af", "\u63cf\u8ff0\u73a9\u5bb6\u53cd\u590d\u8fdb\u884c\u7684\u6838\u5fc3\u884c\u52a8\u3001\u53cd\u9988\u548c\u76ee\u6807\u3002", "")];
        }

        return new GameDesignOutlineDocument(title, summary, sections);
    }

    private static string RenderOutlineMarkdown(GameDesignOutlineDocument document)
    {
        var builder = new StringBuilder();
        builder.AppendLine($"# {document.Title}");
        builder.AppendLine();
        builder.AppendLine(document.Summary);
        builder.AppendLine();
        foreach (var section in document.Sections)
        {
            builder.AppendLine($"## {section.Title}");
            builder.AppendLine();
            builder.AppendLine($"**\u9aa8\u67b6**: {section.Skeleton}");
            builder.AppendLine();
            builder.AppendLine(string.IsNullOrWhiteSpace(section.Content) ? "_\u5f85\u751f\u6210\u5177\u4f53\u5185\u5bb9\u3002_" : section.Content);
            builder.AppendLine();
        }

        return builder.ToString().TrimEnd() + "\n";
    }

    private static string SafeFileName(string value)
    {
        var invalid = Path.GetInvalidFileNameChars().ToHashSet();
        var safe = new string(value.Select(ch => invalid.Contains(ch) ? '-' : ch).ToArray()).Trim('-', ' ', '.');
        return string.IsNullOrWhiteSpace(safe) ? "reference.txt" : safe;
    }

    private static string Slug(string value)
    {
        var text = value.Trim().ToLowerInvariant();
        var builder = new StringBuilder();
        var lastDash = false;
        foreach (var ch in text)
        {
            if (char.IsLetterOrDigit(ch))
            {
                builder.Append(ch);
                lastDash = false;
            }
            else if (!lastDash)
            {
                builder.Append('-');
                lastDash = true;
            }
        }

        return builder.ToString().Trim('-') is { Length: > 0 } slug ? slug : "section";
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
