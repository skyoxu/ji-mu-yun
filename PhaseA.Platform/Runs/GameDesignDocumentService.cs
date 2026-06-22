using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed class GameDesignDocumentService
{
    private const string RunType = "game-design-gdd";
    private const string SectionBatchRunType = "game-design-gdd-section-batch";
    private const string ArtifactType = "game-design-gdd";
    private const string OutputRelativePath = "docs/gdd/GDD.md";
    private const string OutlineRelativePath = "docs/gdd/gdd-outline.json";
    private const string ReferenceRelativeDir = "docs/gdd/references";
    private const string ReasoningEffort = "high";
    private const int MaxMessageChars = 6000;
    private const int MaxAttachmentCount = 5;
    private const int MaxAttachmentChars = 12000;
    private const int MaxTemplateMatchTextChars = 40000;
    private static readonly TimeSpan DefaultExecutionTimeout = TimeSpan.FromMinutes(20);

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly IAiCodeMirrorBillingClient _billingClient;
    private readonly AiCodeMirrorKeyPoolService? _keyPoolService;
    private readonly HeavyRunnerQueueService _heavyRunnerQueue;
    private readonly TimeSpan _executionTimeout;

    private sealed record SelectedGameTypeDesignTemplate(
        BmadGameTypeDesignEntry Entry,
        string SelectionSource,
        string SelectionReason);

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
            var outlineDraftRelativePath = ToSlash(Path.Combine(relativeDir, "gdd-outline.generated.json"));
            var gddAbsolutePath = ResolveUnderProject(projectRoot, OutputRelativePath);
            var outlineAbsolutePath = ResolveUnderProject(projectRoot, OutlineRelativePath);
            var promptAbsolutePath = ResolveUnderProject(projectRoot, promptRelativePath);
            var codexOutputAbsolutePath = ResolveUnderProject(projectRoot, codexOutputRelativePath);
            var outlineDraftAbsolutePath = ResolveUnderProject(projectRoot, outlineDraftRelativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(gddAbsolutePath)!);
            Directory.CreateDirectory(Path.GetDirectoryName(outlineAbsolutePath)!);
            Directory.CreateDirectory(Path.GetDirectoryName(promptAbsolutePath)!);
            Directory.CreateDirectory(Path.GetDirectoryName(outlineDraftAbsolutePath)!);
            File.Delete(outlineDraftAbsolutePath);

            var chatMessages = await _metadataStore.ListProjectChatMessagesAsync(project.AccountId, project.ProjectId, ProjectChatHistoryService.DefaultLimit, CancellationToken.None);
            var memory = await _metadataStore.GetProjectChatMemoryAsync(project.AccountId, project.ProjectId, CancellationToken.None);
            var now = DateTimeOffset.UtcNow.ToString("O");
            var persistedAttachments = await PersistAttachmentsAsync(projectRoot, runId, attachments, CancellationToken.None);
            var historicalAttachments = LoadHistoricalAttachments(projectRoot, persistedAttachments);
            var designTemplate = SelectGameTypeDesignTemplate(project, message, memory?.MemorySummary, chatMessages, persistedAttachments, historicalAttachments);
            var prompt = BuildPrompt(project, message, memory?.MemorySummary, chatMessages, persistedAttachments, historicalAttachments, designTemplate, now, outlineDraftRelativePath);
            await File.WriteAllTextAsync(promptAbsolutePath, prompt, Encoding.UTF8, CancellationToken.None);

            using var timeout = new CancellationTokenSource();
            timeout.CancelAfter(_executionTimeout);
            var model = PrototypeModelPolicy.Normalize(request.Model);
            var runtimeOutputPath = CreateShortRuntimeOutputPath(runId);
            var generatedNotBeforeUtc = DateTimeOffset.UtcNow.AddSeconds(-2);
            await _metadataStore.UpdateRunProgressAsync(runId, "running", "codex", "\u6b63\u5728\u4f7f\u7528 BMAD \u6e38\u620f\u7b56\u5212\u5927\u5e08\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u3002", CancellationToken.None);
            var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, CancellationToken.None);
            var billingKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
            var billingBefore = await _billingClient.CaptureAsync(billingKeyName, CancellationToken.None);
            var codexResult = await _processRunner.RunAsync(
                CodexHostedProcessCommandFactory.ApplyRuntime(BuildCodexCommand(prompt, runtimeOutputPath, model, project.RepoPath), runtimeCredential).WithRunId(runId),
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

            var generatedOutline = await LoadGeneratedOutlineAsync(
                generatedNotBeforeUtc,
                minimumSectionCount: 6,
                rejectPlaceholderFields: true,
                requireUiUxSection: true,
                CancellationToken.None,
                new OutlineCandidate(outlineDraftAbsolutePath, outlineDraftRelativePath),
                new OutlineCandidate(outlineAbsolutePath, OutlineRelativePath));
            if (generatedOutline.Document is null)
            {
                var evidenceMissing = JsonSerializer.Serialize(new
                {
                    run_type = RunType,
                    failure_code = generatedOutline.FailureCode,
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    expected_file = OutlineRelativePath,
                    draft_file = outlineDraftRelativePath
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", 424, codexResult.Stdout, codexResult.Stderr, evidenceMissing, CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", generatedOutline.FailureCode, generatedOutline.FailureSummary, CancellationToken.None);
                await RecordCodexAuditAsync(runId, RunType, model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return Failure(project.ProjectId, generatedOutline.FailureCode, generatedOutline.FailureSummary, runId);
            }

            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-prompt", promptRelativePath, "Game design GDD generation prompt"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-codex-output", codexOutputRelativePath, "Game design GDD Codex output"), CancellationToken.None);
            await WriteOutlineFilesAsync(outlineAbsolutePath, gddAbsolutePath, generatedOutline.Document, CancellationToken.None);
            if (File.Exists(outlineDraftAbsolutePath))
            {
                await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-outline-draft", outlineDraftRelativePath, "Game design outline draft"), CancellationToken.None);
            }

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
                chat_message_count = chatMessages.Count,
                game_type_design_template = designTemplate is null
                    ? null
                    : new
                    {
                        id = designTemplate.Entry.Id,
                        name = designTemplate.Entry.Name,
                        fragment_path = designTemplate.Entry.FragmentRelativePath,
                        selection_source = designTemplate.SelectionSource,
                        selection_reason = designTemplate.SelectionReason
                    }
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
            if (await IsRunCancelledAsync(runId, CancellationToken.None))
            {
                return Cancelled(project.ProjectId, runId, "\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u5df2\u53d6\u6d88\u3002");
            }

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
        if (ContainsGarbledText(document))
        {
            return new GameDesignOutlineReadResult(
                project.ProjectId,
                "\u7b56\u5212\u5927\u7eb2\u9700\u8981\u91cd\u65b0\u751f\u6210",
                "\u5f53\u524d\u7b56\u5212\u5927\u7eb2\u6587\u4ef6\u5df2\u51fa\u73b0\u8fde\u7eed\u95ee\u53f7\u4e71\u7801\uff0c\u4e0d\u518d\u4f5c\u4e3a\u6709\u6548\u5927\u7eb2\u5c55\u793a\u3002\u8bf7\u5220\u9664\u540e\u91cd\u65b0\u521b\u5efa\u3002",
                OutlineRelativePath,
                new FileInfo(outlinePath).LastWriteTimeUtc.ToString("O"),
                []);
        }

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

    public async Task<GameDesignOutlineDeleteResult?> DeleteOutlineAsync(
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

        var deleted = new List<string>();
        foreach (var relativePath in new[] { OutlineRelativePath, OutputRelativePath })
        {
            var absolutePath = ResolveUnderProject(projectRoot, relativePath);
            if (!File.Exists(absolutePath))
            {
                continue;
            }

            File.Delete(absolutePath);
            deleted.Add(relativePath);
        }

        return new GameDesignOutlineDeleteResult(
            project.ProjectId,
            deleted.Count > 0 ? "deleted" : "not_found",
            deleted);
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
            var outlineDraftRelativePath = ToSlash(Path.Combine(relativeDir, "gdd-outline.generated.json"));
            var promptAbsolutePath = ResolveUnderProject(projectRoot, promptRelativePath);
            var codexOutputAbsolutePath = ResolveUnderProject(projectRoot, codexOutputRelativePath);
            var outlineDraftAbsolutePath = ResolveUnderProject(projectRoot, outlineDraftRelativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(promptAbsolutePath)!);
            Directory.CreateDirectory(Path.GetDirectoryName(outlineDraftAbsolutePath)!);
            File.Delete(outlineDraftAbsolutePath);

            var memory = await _metadataStore.GetProjectChatMemoryAsync(project.AccountId, project.ProjectId, CancellationToken.None);
            var historicalAttachments = LoadHistoricalAttachments(projectRoot, []);
            var prompt = BuildSectionPrompt(project, outline, section, message, memory?.MemorySummary, historicalAttachments, DateTimeOffset.UtcNow.ToString("O"), outlineDraftRelativePath);
            await File.WriteAllTextAsync(promptAbsolutePath, prompt, Encoding.UTF8, CancellationToken.None);

            using var timeout = new CancellationTokenSource();
            timeout.CancelAfter(_executionTimeout);
            var model = PrototypeModelPolicy.Normalize(request.Model);
            var runtimeOutputPath = CreateShortRuntimeOutputPath(runId);
            var generatedNotBeforeUtc = DateTimeOffset.UtcNow.AddSeconds(-2);
            var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, CancellationToken.None);
            var billingKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
            var billingBefore = await _billingClient.CaptureAsync(billingKeyName, CancellationToken.None);
            var codexResult = await _processRunner.RunAsync(
                CodexHostedProcessCommandFactory.ApplyRuntime(BuildCodexCommand(prompt, runtimeOutputPath, model, project.RepoPath), runtimeCredential).WithRunId(runId),
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

            var generatedOutline = await LoadGeneratedOutlineAsync(
                generatedNotBeforeUtc,
                minimumSectionCount: 1,
                rejectPlaceholderFields: false,
                requireUiUxSection: false,
                CancellationToken.None,
                new OutlineCandidate(outlineDraftAbsolutePath, outlineDraftRelativePath),
                new OutlineCandidate(outlineAbsolutePath, OutlineRelativePath));
            if (generatedOutline.Document is null)
            {
                var evidenceMissing = JsonSerializer.Serialize(new
                {
                    run_type = "game-design-gdd-section",
                    failure_code = generatedOutline.FailureCode,
                    section_id = section.Id,
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    expected_file = OutlineRelativePath,
                    draft_file = outlineDraftRelativePath
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", 424, codexResult.Stdout, codexResult.Stderr, evidenceMissing, CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", generatedOutline.FailureCode, generatedOutline.FailureSummary, CancellationToken.None);
                await RecordCodexAuditAsync(runId, "game-design-gdd-section", model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return Failure(project.ProjectId, generatedOutline.FailureCode, generatedOutline.FailureSummary, runId);
            }

            var updatedSection = generatedOutline.Document.Sections.FirstOrDefault(item => string.Equals(item.Id, section.Id, StringComparison.OrdinalIgnoreCase));
            if (updatedSection is null || string.IsNullOrWhiteSpace(updatedSection.Content))
            {
                var failureCode = updatedSection is null ? "gdd_outline_section_missing" : "gdd_outline_section_content_missing";
                var failureSummary = updatedSection is null
                    ? "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff1aBMAD \u8f93\u51fa\u4e2d\u7f3a\u5c11\u5f53\u524d\u6761\u76ee\u3002"
                    : "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff1aBMAD \u672a\u5199\u5165\u5177\u4f53\u5185\u5bb9\u3002";
                await _metadataStore.CompleteRunAsync(runId, "failed", 424, codexResult.Stdout, codexResult.Stderr, JsonSerializer.Serialize(new
                {
                    run_type = "game-design-gdd-section",
                    failure_code = failureCode,
                    section_id = section.Id,
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    expected_file = OutlineRelativePath,
                    draft_file = outlineDraftRelativePath
                }), CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", failureCode, failureSummary, CancellationToken.None);
                await RecordCodexAuditAsync(runId, "game-design-gdd-section", model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return Failure(project.ProjectId, failureCode, failureSummary, runId);
            }

            var mergedOutline = MergeSectionContent(outline, updatedSection);
            await WriteOutlineFilesAsync(outlineAbsolutePath, gddAbsolutePath, mergedOutline, CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-prompt", promptRelativePath, "Game design outline section prompt"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-output", codexOutputRelativePath, "Game design outline section Codex output"), CancellationToken.None);
            if (File.Exists(outlineDraftAbsolutePath))
            {
                await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-outline-draft", outlineDraftRelativePath, "Game design outline draft"), CancellationToken.None);
            }

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
            if (await IsRunCancelledAsync(runId, CancellationToken.None))
            {
                return Cancelled(project.ProjectId, runId, "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5df2\u53d6\u6d88\u3002");
            }

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

    public async Task<GameDesignOutlineCompleteAllResult> CompleteMissingSectionsAsync(
        string accountId,
        string projectId,
        GameDesignOutlineCompleteAllRequest request,
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

        if (project.BootstrapStatus == "running" ||
            await _metadataStore.HasRunnerLockAsync(project.ProjectId, cancellationToken) ||
            await _metadataStore.HasActiveRunAsync(project.ProjectId, cancellationToken))
        {
            return new GameDesignOutlineCompleteAllResult(
                project.ProjectId,
                "project_busy",
                0,
                0,
                [],
                "\u9879\u76ee\u6709\u540e\u53f0\u4efb\u52a1\u6b63\u5728\u6267\u884c\uff0c\u8bf7\u7a0d\u540e\u518d\u8865\u5168\u7b56\u5212\u5927\u7eb2\u3002");
        }

        var projectRoot = Path.GetFullPath(project.RepoPath);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        var outlineAbsolutePath = ResolveUnderProject(projectRoot, OutlineRelativePath);
        if (!File.Exists(outlineAbsolutePath))
        {
            return new GameDesignOutlineCompleteAllResult(
                project.ProjectId,
                "outline_not_found",
                0,
                0,
                [],
                "\u8bf7\u5148\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u3002");
        }

        var outline = await ReadOutlineDocumentAsync(outlineAbsolutePath, cancellationToken);
        var pendingSections = outline.Sections
            .Where(section => string.IsNullOrWhiteSpace(section.Content))
            .ToArray();
        if (pendingSections.Length == 0)
        {
            return new GameDesignOutlineCompleteAllResult(
                project.ProjectId,
                "already_complete",
                0,
                0,
                [],
                "\u6240\u6709\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u90fd\u5df2\u6709\u5177\u4f53\u5185\u5bb9\u3002");
        }

        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, SectionBatchRunType, cancellationToken);
        await _metadataStore.UpdateRunProgressAsync(runId, "queued", "batch", "\u5df2\u63d0\u4ea4\u7b56\u5212\u5927\u7eb2\u6279\u91cf\u8865\u5168\uff0c\u7b49\u5f85 runner\u3002", cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return new GameDesignOutlineCompleteAllResult(project.ProjectId, "project_busy", pendingSections.Length, 0, [], "\u9879\u76ee\u6709\u540e\u53f0\u4efb\u52a1\u6b63\u5728\u6267\u884c\u3002", runId);
        }

        _ = Task.Run(async () =>
        {
            try
            {
                await _heavyRunnerQueue.ExecuteAsync(
                    runId,
                    project.AccountId,
                    project.ProjectId,
                    SectionBatchRunType,
                    async (queueStart, _) =>
                    {
                        await RunCompleteMissingSectionsBatchAsync(project, request, runId, pendingSections.Select(section => section.Id).ToArray(), queueStart.QueuePositionAtStart);
                        return true;
                    },
                    CancellationToken.None);
            }
            catch (Exception ex)
            {
                await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), "{}", CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", "error", "\u7b56\u5212\u5927\u7eb2\u6279\u91cf\u8865\u5168\u5931\u8d25\u3002", CancellationToken.None);
            }
            finally
            {
                await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
            }
        }, CancellationToken.None);

        return new GameDesignOutlineCompleteAllResult(
            project.ProjectId,
            "queued",
            pendingSections.Length,
            0,
            [],
            "\u7b56\u5212\u5927\u7eb2\u6279\u91cf\u8865\u5168\u5df2\u63d0\u4ea4\u540e\u53f0\u6267\u884c\u3002",
            runId);
    }

    private async Task RunCompleteMissingSectionsBatchAsync(
        ProjectSnapshot project,
        GameDesignOutlineCompleteAllRequest request,
        string runId,
        IReadOnlyList<string> pendingSectionIds,
        int? queuePositionAtStart)
    {
        await _metadataStore.MarkRunStartedAsync(runId, queuePositionAtStart, CancellationToken.None);
        await _metadataStore.UpdateRunProgressAsync(runId, "running", "prepare", "\u6b63\u5728\u51c6\u5907\u7b56\u5212\u5927\u7eb2\u6279\u91cf\u8865\u5168\u3002", CancellationToken.None);

        var sectionResults = new List<GameDesignOutlineCompleteAllSectionResult>();
        var projectRoot = Path.GetFullPath(project.RepoPath);
        var outlineAbsolutePath = ResolveUnderProject(projectRoot, OutlineRelativePath);
        var gddAbsolutePath = ResolveUnderProject(projectRoot, OutputRelativePath);
        var model = PrototypeModelPolicy.Normalize(request.Model);
        var memory = await _metadataStore.GetProjectChatMemoryAsync(project.AccountId, project.ProjectId, CancellationToken.None);
        var historicalAttachments = LoadHistoricalAttachments(projectRoot, []);

        for (var index = 0; index < pendingSectionIds.Count; index++)
        {
            var outline = await ReadOutlineDocumentAsync(outlineAbsolutePath, CancellationToken.None);
            var section = outline.Sections.FirstOrDefault(item => string.Equals(item.Id, pendingSectionIds[index], StringComparison.OrdinalIgnoreCase));
            if (section is null || !string.IsNullOrWhiteSpace(section.Content))
            {
                continue;
            }

            await _metadataStore.UpdateRunProgressAsync(runId, "running", section.Id, $"\u6b63\u5728\u8865\u5168 {index + 1}/{pendingSectionIds.Count}: {section.Title}", CancellationToken.None);
            var relativeDir = ToSlash(Path.Combine("logs", "phase-a-gdd", project.ProjectId, runId, section.Id));
            var promptRelativePath = ToSlash(Path.Combine(relativeDir, "gdd-section-prompt.md"));
            var codexOutputRelativePath = ToSlash(Path.Combine(relativeDir, "codex-output.txt"));
            var outlineDraftRelativePath = ToSlash(Path.Combine(relativeDir, "gdd-outline.generated.json"));
            var promptAbsolutePath = ResolveUnderProject(projectRoot, promptRelativePath);
            var codexOutputAbsolutePath = ResolveUnderProject(projectRoot, codexOutputRelativePath);
            var outlineDraftAbsolutePath = ResolveUnderProject(projectRoot, outlineDraftRelativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(promptAbsolutePath)!);
            Directory.CreateDirectory(Path.GetDirectoryName(outlineDraftAbsolutePath)!);
            File.Delete(outlineDraftAbsolutePath);

            var prompt = BuildSectionPrompt(project, outline, section, request.Message ?? "", memory?.MemorySummary, historicalAttachments, DateTimeOffset.UtcNow.ToString("O"), outlineDraftRelativePath);
            await File.WriteAllTextAsync(promptAbsolutePath, prompt, Encoding.UTF8, CancellationToken.None);

            using var timeout = new CancellationTokenSource();
            timeout.CancelAfter(_executionTimeout);
            var runtimeOutputPath = CreateShortRuntimeOutputPath(runId);
            var generatedNotBeforeUtc = DateTimeOffset.UtcNow.AddSeconds(-2);
            var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, CancellationToken.None);
            var billingKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
            var billingBefore = await _billingClient.CaptureAsync(billingKeyName, CancellationToken.None);
            var codexResult = await _processRunner.RunAsync(
                CodexHostedProcessCommandFactory.ApplyRuntime(BuildCodexCommand(prompt, runtimeOutputPath, model, project.RepoPath), runtimeCredential).WithRunId(runId),
                timeout.Token);
            var providerBilling = new AiCodeMirrorBillingDelta(billingBefore, await _billingClient.CaptureAsync(billingKeyName, CancellationToken.None));
            if (File.Exists(runtimeOutputPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(codexOutputAbsolutePath)!);
                File.Copy(runtimeOutputPath, codexOutputAbsolutePath, overwrite: true);
            }

            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-prompt", promptRelativePath, "Game design outline section prompt"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-output", codexOutputRelativePath, "Game design outline section Codex output"), CancellationToken.None);

            if (codexResult.ExitCode != 0)
            {
                sectionResults.Add(new GameDesignOutlineCompleteAllSectionResult(section.Id, section.Title, "codex_failed", runId, "codex_failed", "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\u3002"));
                await CompleteBatchRunAsync(project.ProjectId, runId, model, pendingSectionIds.Count, sectionResults, "partial_failed", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr);
                await RecordCodexAuditAsync(runId, SectionBatchRunType, model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return;
            }

            var generatedOutline = await LoadGeneratedOutlineAsync(
                generatedNotBeforeUtc,
                minimumSectionCount: 1,
                rejectPlaceholderFields: false,
                requireUiUxSection: false,
                CancellationToken.None,
                new OutlineCandidate(outlineDraftAbsolutePath, outlineDraftRelativePath),
                new OutlineCandidate(outlineAbsolutePath, OutlineRelativePath));
            var updatedSection = generatedOutline.Document?.Sections.FirstOrDefault(item => string.Equals(item.Id, section.Id, StringComparison.OrdinalIgnoreCase));
            if (generatedOutline.Document is null || updatedSection is null || string.IsNullOrWhiteSpace(updatedSection.Content))
            {
                var failureCode = generatedOutline.Document is null ? generatedOutline.FailureCode : updatedSection is null ? "gdd_outline_section_missing" : "gdd_outline_section_content_missing";
                sectionResults.Add(new GameDesignOutlineCompleteAllSectionResult(section.Id, section.Title, failureCode, runId, failureCode, generatedOutline.FailureSummary));
                await CompleteBatchRunAsync(project.ProjectId, runId, model, pendingSectionIds.Count, sectionResults, "partial_failed", 424, codexResult.Stdout, codexResult.Stderr);
                await RecordCodexAuditAsync(runId, SectionBatchRunType, model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return;
            }

            var latestOutline = await ReadOutlineDocumentAsync(outlineAbsolutePath, CancellationToken.None);
            var mergedOutline = MergeSectionContent(latestOutline, updatedSection);
            await WriteOutlineFilesAsync(outlineAbsolutePath, gddAbsolutePath, mergedOutline, CancellationToken.None);
            if (File.Exists(outlineDraftAbsolutePath))
            {
                await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-outline-draft", outlineDraftRelativePath, "Game design outline draft"), CancellationToken.None);
            }
            sectionResults.Add(new GameDesignOutlineCompleteAllSectionResult(section.Id, section.Title, "succeeded", runId, null, "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u5185\u5bb9\u5df2\u66f4\u65b0\u3002"));
            await RecordCodexAuditAsync(runId, SectionBatchRunType, model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
        }

        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-outline", OutlineRelativePath, "Game design outline"), CancellationToken.None);
        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, ArtifactType, OutputRelativePath, "Game design document"), CancellationToken.None);
        await CompleteBatchRunAsync(project.ProjectId, runId, model, pendingSectionIds.Count, sectionResults, "succeeded", 0, "", "");
    }

    private async Task CompleteBatchRunAsync(
        string projectId,
        string runId,
        string model,
        int requestedCount,
        IReadOnlyList<GameDesignOutlineCompleteAllSectionResult> sectionResults,
        string status,
        int exitCode,
        string stdout,
        string stderr)
    {
        var completedCount = sectionResults.Count(item => item.Status == "succeeded");
        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = SectionBatchRunType,
            model,
            requested_count = requestedCount,
            completed_count = completedCount,
            sections = sectionResults,
            outline_file = OutlineRelativePath,
            output_file = OutputRelativePath
        });
        var finalStatus = status == "succeeded" ? "succeeded" : "failed";
        await _metadataStore.CompleteRunAsync(runId, finalStatus, exitCode, stdout, stderr, evidenceJson, CancellationToken.None);
        await _metadataStore.UpdateRunProgressAsync(
            runId,
            finalStatus,
            status,
            status == "succeeded" ? "\u7b56\u5212\u5927\u7eb2\u5df2\u6279\u91cf\u8865\u5168\u3002" : "\u7b56\u5212\u5927\u7eb2\u6279\u91cf\u8865\u5168\u4e2d\u65ad\u3002",
            CancellationToken.None);
    }

    private static string BuildPrompt(
        ProjectSnapshot project,
        string message,
        string? memorySummary,
        IReadOnlyList<ProjectChatMessageSnapshot> chatMessages,
        IReadOnlyList<TextAttachment> currentAttachments,
        IReadOnlyList<TextAttachment> historicalAttachments,
        SelectedGameTypeDesignTemplate? designTemplate,
        string now,
        string outlineDraftRelativePath)
    {
        return $$"""
            Use the $bmad-agent-game-designer BMAD game design skill. This is mandatory: create the planning outline through BMAD game design reasoning, not a generic freeform plan. You may use the BMAD/GDS GDD template as structural inspiration, but this run creates only a planning outline and skeleton, not full prose.

            You are running inside a Phase A project workspace. Create or update exactly this UTF-8 JSON draft file:
            {{outlineDraftRelativePath}}

            The host service will validate that draft and then write docs/gdd/gdd-outline.json itself. Do not write docs/gdd/gdd-outline.json directly.

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
            4. The 24-type game design template baseline is a low-priority scaffold used only to fill missing GDD dimensions.
            5. Project memory, server chat history, and implicit LLM context have low priority.
            If sources conflict, keep the higher-priority source and discard or ignore conflicting lower-priority details.
            Lay down the selected template baseline first only as reusable genre scaffolding; current user input and uploaded references below must override it.

            Outline requirements:
            - Write user-facing fields in Chinese.
            - The draft file must preserve Chinese characters. Do not replace Chinese with question marks.
            - Prefer JSON unicode escapes for all Chinese text, for example "\u6838\u5fc3\u5faa\u73af", so Windows console encoding cannot corrupt the file.
            - Create 6 to 12 sections covering vision, target player, core loop, player progression, world/levels, combat/interaction, UI/UX/HUD and player feedback, content and asset needs, prototype acceptance criteria, and open questions.
            - The outline must explicitly include the user's reference game or reference genre and explain what design signals are being borrowed.
            - Before using any game-type template signal, verify the reference game's likely public genre/tag signals from the provided context and your BMAD game design knowledge. Do not infer genre from title words alone. For example, a game named with "Tower" is not tower defense unless the gameplay/tag evidence says tower defense.
            - If reference-game title words conflict with the user's explicit gameplay genre, mechanics, controls, or loop, follow the user's explicit gameplay. Do not expose an incorrect template name or template rationale in user-facing title, summary, skeleton, or content.
            - The outline must include scene creation content: first playable scene, important rooms/boards/encounters, and how the player enters the scene.
            - The outline must include keyboard and mouse basics when the target platform is PC, covering movement, aiming/selection, primary action, cancel/dodge/back, and skill/action hotkeys where relevant.
            - The outline must include the basic gameplay loop that the prototype skeleton should materialize first.
            - The outline must include lightweight UI/UX pre-design sufficient to guide feature development, not polished visual design: screen inventory, core player flow map, HUD information priority, input model, key UI states, rough layout/wireframe notes, localization baseline, and accessibility baseline.
            - The outline must state feature-development UI structure rules: placeholder UI is allowed, but screen id, scene path, input action, and state naming must stay stable; player-visible text must not be hardcoded in isolated logic; repeated buttons and panels should share one style/component approach instead of each screen inventing its own.
            - Include a milestone or step-plan section whose steps are derived from the actual GDD scope; do not hardcode M1-M10. The plan may be shorter, longer, or include post-polish steps such as M10-1 when justified.
            - The milestone or step-plan section should reserve formal UI/UX retrofit work after functional completion when relevant: theme tokens, component kit, screen contracts, screenshot acceptance, focus checks, localization checks, and overflow checks.
            - For prototype-oriented projects, include a lightweight component/scene responsibility section or make UI/UX/HUD and content/asset sections explicitly name component slots such as PrototypeRoot, HudView, MapView, BattleView, RewardView, ActorView, LogView, InventoryView, Systems, and Data/State where relevant.
            - Treat those component names as Godot Node/scene responsibility slots, not ECS. Do not propose ECS, EntityComponent, IComponent, or a new framework unless the user explicitly asks for it.
            - Every section.content must be an empty string. Section content is generated later by the section route.
            - section.id must be stable, lowercase, hyphenated, and unique.
            - Final assistant reply should be 2 to 4 short sentences only; do not print the whole JSON.

            Project:
            - ProjectId: {{project.ProjectId}}
            - Name: {{project.Name}}
            - GameName: {{project.GameName}}
            - GameType: {{project.GameTypeSource}}
            - CreatedAtUtc: {{now}}

            Game Type Design Template Baseline, low priority and only for GDD creation:
            {{FormatDesignTemplate(designTemplate)}}

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

            Create or update {{outlineDraftRelativePath}} now.
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
        string now,
        string outlineDraftRelativePath)
    {
        return $$"""
            Use the $bmad-agent-game-designer BMAD game design skill. This run fills exactly one planning outline section. Do not expand other sections.

            Source file: docs/gdd/gdd-outline.json
            Draft output file: {{outlineDraftRelativePath}}
            Read the source file, update only the section whose id is "{{section.Id}}", and write the full updated JSON document to the draft output file. Replace only that section.content field. Do not change title, skeleton, or other sections.
            The host service will validate the draft and then write docs/gdd/gdd-outline.json itself. Do not write docs/gdd/gdd-outline.json directly.

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
            - The draft file must preserve Chinese characters. Do not replace Chinese with question marks.
            - Prefer JSON unicode escapes for all Chinese text, for example "\u6838\u5fc3\u5faa\u73af", so Windows console encoding cannot corrupt the file.
            - Stay inside this section's scope.
            - If this section concerns reference, scenes, controls, UI/UX/HUD, player feedback, core loop, prototype acceptance, or milestones, preserve the hard GDD requirements: reference game/design signal, scene creation content, keyboard/mouse basics, basic gameplay loop, lightweight UI/UX pre-design, and dynamic milestone steps based on actual scope rather than fixed M1-M10.
            - For UI/UX/HUD content, include only development-guiding pre-design before features are built: screen inventory, core player flow map, HUD information priority, input model, key UI states, rough layout/wireframe notes, localization baseline, and accessibility baseline.
            - For implementation-facing UI/UX notes, keep structure stable: screen id, scene path, input action, and state names should be reusable across milestones; placeholder UI is acceptable; player-visible text should be localized or centralized instead of hardcoded in isolated gameplay code; repeated buttons and panels should share a style/component approach.
            - For post-feature UI/UX retrofit notes, describe when to add theme tokens, component kit, screen contracts, screenshot acceptance, focus checks, localization checks, and overflow checks.
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

    private SelectedGameTypeDesignTemplate? SelectGameTypeDesignTemplate(
        ProjectSnapshot project,
        string message,
        string? memorySummary,
        IReadOnlyList<ProjectChatMessageSnapshot> chatMessages,
        IReadOnlyList<TextAttachment> currentAttachments,
        IReadOnlyList<TextAttachment> historicalAttachments)
    {
        var catalog = new BmadGameTypeDesignCatalog(_options);
        var direct = catalog.Find(project.GameTypeSource);
        if (direct is not null)
        {
            return new SelectedGameTypeDesignTemplate(
                direct,
                "project.game_type_source",
                $"Project game type '{project.GameTypeSource}' matched template '{direct.Id}'.");
        }

        var gameplayText = BuildGameplayTemplateMatchText(project, message, memorySummary, chatMessages, currentAttachments, historicalAttachments);
        var gameplayTemplateId = GameTypeDesignTemplateDetector.DetectExplicitGameplayTemplateId(gameplayText);
        if (!string.IsNullOrWhiteSpace(gameplayTemplateId))
        {
            var gameplayEntry = catalog.Find(gameplayTemplateId);
            if (gameplayEntry is not null)
            {
                return new SelectedGameTypeDesignTemplate(
                    gameplayEntry,
                    "explicit_gameplay_semantics",
                    $"Explicit gameplay semantics matched template '{gameplayEntry.Id}'.");
            }
        }

        var matchText = BuildTemplateMatchText(project, message, memorySummary, chatMessages, currentAttachments, historicalAttachments);
        if (string.IsNullOrWhiteSpace(matchText))
        {
            return null;
        }

        var best = catalog.Entries
            .Select(entry => new
            {
                Entry = entry,
                Score = ScoreTemplateMatch(entry, matchText)
            })
            .OrderByDescending(item => item.Score)
            .ThenBy(item => item.Entry.Id, StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault();

        if (best is null || best.Score <= 0)
        {
            return null;
        }

        return new SelectedGameTypeDesignTemplate(
            best.Entry,
            "project_context_keyword_match",
            $"Project input and references matched template '{best.Entry.Id}' with score {best.Score}.");
    }

    private static string BuildTemplateMatchText(
        ProjectSnapshot project,
        string message,
        string? memorySummary,
        IReadOnlyList<ProjectChatMessageSnapshot> chatMessages,
        IReadOnlyList<TextAttachment> currentAttachments,
        IReadOnlyList<TextAttachment> historicalAttachments)
    {
        var builder = new StringBuilder();
        builder.AppendLine(message);
        builder.AppendLine(memorySummary);
        foreach (var chatMessage in chatMessages)
        {
            builder.AppendLine(chatMessage.Content);
        }

        foreach (var attachment in currentAttachments.Concat(historicalAttachments))
        {
            builder.AppendLine(attachment.FileName);
            builder.AppendLine(attachment.Content);
            if (builder.Length >= MaxTemplateMatchTextChars)
            {
                break;
            }
        }

        var text = builder.ToString();
        return text.Length <= MaxTemplateMatchTextChars ? text : text[..MaxTemplateMatchTextChars];
    }

    private static string BuildGameplayTemplateMatchText(
        ProjectSnapshot project,
        string message,
        string? memorySummary,
        IReadOnlyList<ProjectChatMessageSnapshot> chatMessages,
        IReadOnlyList<TextAttachment> currentAttachments,
        IReadOnlyList<TextAttachment> historicalAttachments)
    {
        var builder = new StringBuilder();
        builder.AppendLine(message);
        builder.AppendLine(memorySummary);
        foreach (var chatMessage in chatMessages)
        {
            builder.AppendLine(chatMessage.Content);
        }

        foreach (var attachment in currentAttachments.Concat(historicalAttachments))
        {
            builder.AppendLine(attachment.Content);
            if (builder.Length >= MaxTemplateMatchTextChars)
            {
                break;
            }
        }

        var text = builder.ToString();
        return text.Length <= MaxTemplateMatchTextChars ? text : text[..MaxTemplateMatchTextChars];
    }

    private static int ScoreTemplateMatch(BmadGameTypeDesignEntry entry, string text)
    {
        var normalized = text.ToLowerInvariant();
        var tokens = TokenizeForTemplateMatch(normalized);
        var score = 0;
        score += ScoreTerm(normalized, tokens, entry.Id, 8);
        score += ScoreTerm(normalized, tokens, entry.Name, 8);
        foreach (var tag in SplitTemplateTokens(entry.GenreTags))
        {
            score += ScoreTerm(normalized, tokens, tag, 4);
        }

        foreach (var token in SplitTemplateTokens(entry.Description))
        {
            score += ScoreTerm(normalized, tokens, token, 1);
        }

        return score;
    }

    private static int ScoreTerm(string normalizedText, IReadOnlySet<string> normalizedTokens, string? term, int weight)
    {
        if (string.IsNullOrWhiteSpace(term))
        {
            return 0;
        }

        var normalizedTerm = term.Trim().ToLowerInvariant();
        if (IsAsciiTokenTerm(normalizedTerm))
        {
            return normalizedTokens.Contains(normalizedTerm) ? weight : 0;
        }

        return normalizedText.Contains(normalizedTerm, StringComparison.Ordinal) ? weight : 0;
    }

    private static IReadOnlySet<string> TokenizeForTemplateMatch(string normalizedText)
    {
        return normalizedText
            .Split([' ', '\t', '\r', '\n', ',', ';', '/', '|', '\\', '.', ':', '：', '、', '，', '。', '!', '?', '！', '？', '(', ')', '[', ']', '{', '}', '"', '\''], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .SelectMany(SplitCamelAndSeparatorTokens)
            .Where(token => token.Length >= 2)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
    }

    private static IEnumerable<string> SplitCamelAndSeparatorTokens(string token)
    {
        foreach (var part in token.Split(['_', '-'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (!string.IsNullOrWhiteSpace(part))
            {
                yield return part;
            }
        }
    }

    private static bool IsAsciiTokenTerm(string term)
    {
        return term.All(ch => (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') || ch is '-' or '_');
    }

    private static IReadOnlyList<string> SplitTemplateTokens(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return [];
        }

        return value.Split([',', ';', '/', '|', ' ', '\t', '\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(token => token.Length >= 3)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
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

    private static string FormatDesignTemplate(SelectedGameTypeDesignTemplate? selected)
    {
        if (selected is null)
        {
            return "(none)";
        }

        var entry = selected.Entry;
        return $$"""
            Template policy:
            - This baseline is injected before user details only to provide missing GDD dimensions.
            - Current user input and uploaded references override this baseline.
            - This template must not affect prototype skeleton creation, milestone execution, asset replacement, packaging, route selection, or type-kit selection.

            TemplateId: {{entry.Id}}
            TemplateName: {{entry.Name}}
            FragmentPath: {{EmptyAsNone(entry.FragmentRelativePath)}}
            SelectionSource: {{selected.SelectionSource}}
            SelectionReason: {{selected.SelectionReason}}
            Description: {{EmptyAsNone(entry.Description)}}
            GenreTags: {{EmptyAsNone(entry.GenreTags)}}

            GuideExcerpt:
            {{EmptyAsNone(entry.GuideExcerpt)}}
            """;
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
        ThrowIfGarbled(document);
        await WriteOutlineFilesAsync(outlinePath, gddPath, document, cancellationToken);
    }

    private static async Task WriteOutlineFilesAsync(
        string outlinePath,
        string gddPath,
        GameDesignOutlineDocument document,
        CancellationToken cancellationToken)
    {
        ThrowIfGarbled(document);
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

    private static async Task<GeneratedOutlineResult> LoadGeneratedOutlineAsync(
        DateTimeOffset notBeforeUtc,
        int minimumSectionCount,
        bool rejectPlaceholderFields,
        bool requireUiUxSection,
        CancellationToken cancellationToken,
        params OutlineCandidate[] candidates)
    {
        foreach (var candidate in candidates)
        {
            if (!File.Exists(candidate.AbsolutePath))
            {
                continue;
            }

            var info = new FileInfo(candidate.AbsolutePath);
            if (info.Length == 0 || info.LastWriteTimeUtc < notBeforeUtc.UtcDateTime)
            {
                continue;
            }

            GameDesignOutlineDocument document;
            try
            {
                document = await ReadOutlineDocumentAsync(candidate.AbsolutePath, cancellationToken);
            }
            catch (Exception ex) when (ex is JsonException or IOException or UnauthorizedAccessException)
            {
                return GeneratedOutlineResult.Failed(
                    "gdd_outline_invalid_json",
                    "\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff1aBMAD \u8f93\u51fa\u7684 JSON \u65e0\u6cd5\u89e3\u6790\u3002");
            }

            if (ContainsGarbledText(document))
            {
                return GeneratedOutlineResult.Failed(
                    "gdd_outline_garbled_text",
                    "\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff1aBMAD \u8f93\u51fa\u7684\u4e2d\u6587\u53d8\u6210\u4e86\u8fde\u7eed\u95ee\u53f7\uff0c\u8bf7\u91cd\u65b0\u751f\u6210\u3002");
            }

            if (document.Sections.Count < minimumSectionCount)
            {
                return GeneratedOutlineResult.Failed(
                    "gdd_outline_too_thin",
                    $"\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff1aBMAD \u8f93\u51fa\u7684\u5927\u7eb2\u7ed3\u6784\u8fc7\u8584\uff0c\u81f3\u5c11\u9700\u8981 {minimumSectionCount} \u4e2a\u6761\u76ee\u3002");
            }

            if (rejectPlaceholderFields && ContainsPlaceholderOutline(document))
            {
                return GeneratedOutlineResult.Failed(
                    "gdd_outline_placeholder",
                    "\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff1aBMAD \u8f93\u51fa\u7684\u5927\u7eb2\u4ecd\u5305\u542b\u5360\u4f4d\u6807\u9898\u6216\u5360\u4f4d\u9aa8\u67b6\uff0c\u8bf7\u91cd\u65b0\u751f\u6210\u3002");
            }

            if (requireUiUxSection && !ContainsUiUxSection(document))
            {
                return GeneratedOutlineResult.Failed(
                    "gdd_outline_missing_ui_ux",
                    "\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff1aBMAD \u8f93\u51fa\u7684\u5927\u7eb2\u7f3a\u5c11 UI/UX/HUD \u6216\u73a9\u5bb6\u53cd\u9988\u76f8\u5173\u6761\u76ee\uff0c\u8bf7\u91cd\u65b0\u751f\u6210\u3002");
            }

            return GeneratedOutlineResult.Success(document);
        }

        return GeneratedOutlineResult.Failed(
            "gdd_outline_not_created",
            "BMAD \u5df2\u8fd0\u884c\uff0c\u4f46\u6ca1\u6709\u751f\u6210\u7b56\u5212\u5927\u7eb2\u6587\u4ef6\u3002");
    }

    private static GameDesignOutlineDocument MergeSectionContent(GameDesignOutlineDocument current, GameDesignOutlineSection updatedSection)
    {
        var sections = current.Sections
            .Select(section => string.Equals(section.Id, updatedSection.Id, StringComparison.OrdinalIgnoreCase)
                ? section with { Content = updatedSection.Content }
                : section)
            .ToArray();
        return new GameDesignOutlineDocument(current.Title, current.Summary, sections);
    }

    private static void ThrowIfGarbled(GameDesignOutlineDocument document)
    {
        if (ContainsGarbledText(document))
        {
            throw new InvalidOperationException("GDD outline contains garbled question-mark text.");
        }
    }

    private static bool ContainsGarbledText(GameDesignOutlineDocument document)
    {
        if (LooksGarbled(document.Title) || LooksGarbled(document.Summary))
        {
            return true;
        }

        return document.Sections.Any(section =>
            LooksGarbled(section.Title) ||
            LooksGarbled(section.Skeleton) ||
            LooksGarbled(section.Content));
    }

    private static bool ContainsPlaceholderOutline(GameDesignOutlineDocument document)
    {
        var topLevelPlaceholderSignals = 0;
        if (string.Equals(document.Title, "\u6e38\u620f\u7b56\u5212\u5927\u7eb2", StringComparison.Ordinal))
        {
            topLevelPlaceholderSignals++;
        }

        if (string.Equals(document.Summary, "\u5f85\u8865\u5145\u3002", StringComparison.Ordinal))
        {
            topLevelPlaceholderSignals++;
        }

        return topLevelPlaceholderSignals >= 2 ||
               document.Sections.Any(section =>
                   section.Title.StartsWith("\u7b56\u5212\u6761\u76ee ", StringComparison.Ordinal) ||
                   string.Equals(section.Skeleton, "\u5f85\u8865\u5145\u9aa8\u67b6\u3002", StringComparison.Ordinal));
    }

    private static bool ContainsUiUxSection(GameDesignOutlineDocument document)
    {
        return document.Sections.Any(section =>
        {
            var text = $"{section.Id} {section.Title} {section.Skeleton}";
            return ContainsAnyOrdinalIgnoreCase(text, "interface", "screen", "layout", "wireframe", "\u754c\u9762", "\u4ea4\u4e92", "\u73a9\u5bb6\u53cd\u9988", "\u4fe1\u606f\u5c42\u7ea7", "\u5e03\u5c40", "\u7ebf\u6846", "\u65e0\u969c\u788d", "\u672c\u5730\u5316") ||
                   ContainsAnyAsciiToken(text, "ui", "ux", "hud");
        });
    }

    private static bool ContainsAnyOrdinalIgnoreCase(string text, params string[] needles)
    {
        return needles.Any(needle => text.Contains(needle, StringComparison.OrdinalIgnoreCase));
    }

    private static bool ContainsAnyAsciiToken(string text, params string[] needles)
    {
        return text
            .Split([' ', '\t', '\r', '\n', '-', '_', '/', '\\', '.', ':', ';', ',', '(', ')', '[', ']', '{', '}', '"', '\''], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Any(token => needles.Any(needle => string.Equals(token, needle, StringComparison.OrdinalIgnoreCase)));
    }

    private static bool LooksGarbled(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var questionCount = value.Count(ch => ch == '?');
        if (questionCount >= 3 && value.Contains("???", StringComparison.Ordinal))
        {
            return true;
        }

        var visibleCount = value.Count(ch => !char.IsWhiteSpace(ch));
        return visibleCount >= 12 && questionCount >= 8 && questionCount * 3 >= visibleCount;
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

    private sealed record OutlineCandidate(string AbsolutePath, string RelativePath);

    private sealed record GeneratedOutlineResult(
        GameDesignOutlineDocument? Document,
        string FailureCode,
        string FailureSummary)
    {
        public static GeneratedOutlineResult Success(GameDesignOutlineDocument document)
        {
            return new GeneratedOutlineResult(document, "", "");
        }

        public static GeneratedOutlineResult Failed(string failureCode, string failureSummary)
        {
            return new GeneratedOutlineResult(null, failureCode, failureSummary);
        }
    }

    private static GameDesignDocumentResult Failure(string projectId, string failureCode, string summary, string runId = "")
    {
        return new GameDesignDocumentResult(projectId, runId, "failed", OutputRelativePath, "", [], failureCode, summary);
    }

    private static GameDesignDocumentResult Cancelled(string projectId, string runId, string summary)
    {
        return new GameDesignDocumentResult(projectId, runId, "cancel", OutputRelativePath, "", [], "cancel", summary);
    }

    private async Task<bool> IsRunCancelledAsync(string runId, CancellationToken cancellationToken)
    {
        var run = await _metadataStore.GetRunSnapshotAsync(runId, cancellationToken);
        return string.Equals(run?.Status, "cancel", StringComparison.Ordinal);
    }
}
