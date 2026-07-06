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
    private const int MaxModelCapacityRetries = 3;
    private static readonly Encoding Utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
    private static readonly TimeSpan DefaultExecutionTimeout = TimeSpan.FromMinutes(20);
    private static readonly TimeSpan DefaultModelCapacityRetryDelay = TimeSpan.FromSeconds(5);

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly IAiCodeMirrorBillingClient _billingClient;
    private readonly AiCodeMirrorKeyPoolService? _keyPoolService;
    private readonly HeavyRunnerQueueService _heavyRunnerQueue;
    private readonly TimeSpan _executionTimeout;
    private readonly TimeSpan _modelCapacityRetryDelay;

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
        TimeSpan? executionTimeout = null,
        TimeSpan? modelCapacityRetryDelay = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _workspaceSeeder = workspaceSeeder;
        _billingClient = billingClient ?? new DisabledAiCodeMirrorBillingClient();
        _keyPoolService = keyPoolService;
        _heavyRunnerQueue = heavyRunnerQueue ?? new HeavyRunnerQueueService();
        _executionTimeout = executionTimeout ?? DefaultExecutionTimeout;
        _modelCapacityRetryDelay = modelCapacityRetryDelay ?? DefaultModelCapacityRetryDelay;
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

        var existingOutlinePath = ResolveUnderProject(projectRoot, OutlineRelativePath);
        var existingGddPath = ResolveUnderProject(projectRoot, OutputRelativePath);
        if (File.Exists(existingOutlinePath) || File.Exists(existingGddPath))
        {
            return Failure(project.ProjectId, "gdd_already_exists", "\u7b56\u5212\u5927\u7eb2\u5df2\u5b58\u5728\uff0c\u8bf7\u5148\u67e5\u9605\u6216\u5220\u9664\u540e\u518d\u91cd\u65b0\u521b\u5efa\u3002");
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
            var sceneRoute = GameDesignSceneRouteService.NormalizeSubmittedSceneRoute(request.SceneRoute);
            var prompt = BuildPrompt(project, message, sceneRoute, memory?.MemorySummary, chatMessages, persistedAttachments, historicalAttachments, designTemplate, now, outlineDraftRelativePath);
            await File.WriteAllTextAsync(promptAbsolutePath, prompt, Encoding.UTF8, CancellationToken.None);

            using var timeout = new CancellationTokenSource();
            timeout.CancelAfter(_executionTimeout);
            var model = PrototypeModelPolicy.Normalize(request.Model);
            var runtimeOutputPath = CreateShortRuntimeOutputPath(runId);
            var generatedNotBeforeUtc = DateTimeOffset.UtcNow.AddSeconds(-2);
            await _metadataStore.UpdateRunProgressAsync(runId, "running", "generation", "\u6b63\u5728\u521b\u5efa\u7b56\u5212\u5927\u7eb2\u3002", CancellationToken.None);
            var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, CancellationToken.None);
            var billingKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
            var billingBefore = await _billingClient.CaptureAsync(billingKeyName, CancellationToken.None);
            var codexRun = await RunCodexWithModelCapacityRetriesAsync(runId, prompt, runtimeOutputPath, model, project.RepoPath, runtimeCredential, timeout.Token);
            var codexResult = codexRun.Result;
            var modelCapacityRetryCount = codexRun.ModelCapacityRetryCount;

            var providerBilling = new AiCodeMirrorBillingDelta(billingBefore, await _billingClient.CaptureAsync(billingKeyName, CancellationToken.None));

            if (File.Exists(runtimeOutputPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(codexOutputAbsolutePath)!);
                File.Copy(runtimeOutputPath, codexOutputAbsolutePath, overwrite: true);
            }

            if (codexResult.ExitCode != 0)
            {
                var failureCode = IsModelCapacityFailure(codexResult) ? "model_capacity" : "codex_failed";
                var failureSummary = IsModelCapacityFailure(codexResult)
                    ? "\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff1a\u5927\u6a21\u578b\u8bbf\u95ee\u7e41\u5fd9\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002"
                    : "\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff0c\u751f\u6210\u6d41\u7a0b\u672a\u6210\u529f\u5b8c\u6210\u3002";
                var evidenceFailed = JsonSerializer.Serialize(new
                {
                    run_type = RunType,
                    failure_code = failureCode,
                    model,
                    model_capacity_retry_count = modelCapacityRetryCount,
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    expected_file = OutlineRelativePath
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceFailed, CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", failureCode, failureSummary, CancellationToken.None);
                await RecordCodexAuditAsync(runId, RunType, model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return Failure(project.ProjectId, failureCode, failureSummary, runId);
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
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-codex-output", codexOutputRelativePath, "Game design GDD generation output"), CancellationToken.None);
            await WriteOutlineFilesAsync(outlineAbsolutePath, gddAbsolutePath, generatedOutline.Document, CancellationToken.None);
            var specRelativePaths = await GddMilestoneSpecDocumentWriter.WriteFromGddAsync(project, await File.ReadAllTextAsync(gddAbsolutePath, Encoding.UTF8, CancellationToken.None), CancellationToken.None);
            if (File.Exists(outlineDraftAbsolutePath))
            {
                await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-outline-draft", outlineDraftRelativePath, "Game design outline draft"), CancellationToken.None);
            }

            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, ArtifactType, OutputRelativePath, "Game design document"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-outline", OutlineRelativePath, "Game design outline"), CancellationToken.None);
            foreach (var specRelativePath in specRelativePaths)
            {
                await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-milestone-spec", specRelativePath, "Game design milestone spec"), CancellationToken.None);
            }

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                model,
                model_capacity_retry_count = modelCapacityRetryCount,
                skill_name = "bmad-agent-game-designer",
                canonical_skill_name = "gds-agent-game-designer",
                output_file = OutputRelativePath,
                outline_file = OutlineRelativePath,
                spec_files = specRelativePaths,
                prompt = promptRelativePath,
                codex_output = codexOutputRelativePath,
                attachment_count = persistedAttachments.Count,
                historical_attachment_count = historicalAttachments.Count,
                chat_message_count = chatMessages.Count,
                scene_route_scene_count = sceneRoute?.Scenes.Count ?? 0,
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
        var displayDocument = NormalizeMilestoneListsForDisplay(document);
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
            displayDocument.Title,
            displayDocument.Summary,
            OutlineRelativePath,
            info.LastWriteTimeUtc.ToString("O"),
            displayDocument.Sections);
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
        await GddMilestoneSpecDocumentWriter.WriteFromGddAsync(project, await File.ReadAllTextAsync(gddPath, Encoding.UTF8, cancellationToken), cancellationToken);
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
        await _metadataStore.UpdateRunProgressAsync(runId, "running", "generation", "\u6b63\u5728\u586b\u5145\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u3002", CancellationToken.None);

        try
        {
            var relativeDir = ToSlash(Path.Combine("logs", "phase-a-gdd", project.ProjectId, runId));
            var promptRelativePath = ToSlash(Path.Combine(relativeDir, "gdd-section-prompt.md"));
            var codexOutputRelativePath = ToSlash(Path.Combine(relativeDir, "codex-output.txt"));
            var outlineDraftRelativePath = ToSlash(Path.Combine(relativeDir, "gdd-section.generated.json"));
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
            var codexRun = await RunCodexWithModelCapacityRetriesAsync(runId, prompt, runtimeOutputPath, model, project.RepoPath, runtimeCredential, timeout.Token);
            var codexResult = codexRun.Result;
            var modelCapacityRetryCount = codexRun.ModelCapacityRetryCount;
            var providerBilling = new AiCodeMirrorBillingDelta(billingBefore, await _billingClient.CaptureAsync(billingKeyName, CancellationToken.None));

            if (File.Exists(runtimeOutputPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(codexOutputAbsolutePath)!);
                File.Copy(runtimeOutputPath, codexOutputAbsolutePath, overwrite: true);
            }

            if (codexResult.ExitCode != 0)
            {
                var failureCode = IsModelCapacityFailure(codexResult) ? "model_capacity" : "codex_failed";
                var failureSummary = IsModelCapacityFailure(codexResult)
                    ? "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff1a\u5927\u6a21\u578b\u8bbf\u95ee\u7e41\u5fd9\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002"
                    : "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff0c\u751f\u6210\u6d41\u7a0b\u672a\u6210\u529f\u5b8c\u6210\u3002";
                var evidenceFailed = JsonSerializer.Serialize(new
                {
                    run_type = "game-design-gdd-section",
                    failure_code = failureCode,
                    section_id = section.Id,
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    expected_file = OutlineRelativePath,
                    model_capacity_retry_count = modelCapacityRetryCount
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceFailed, CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", failureCode, failureSummary, CancellationToken.None);
                await RecordCodexAuditAsync(runId, "game-design-gdd-section", model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return Failure(project.ProjectId, failureCode, failureSummary, runId);
            }

            var generatedSection = await LoadGeneratedSectionAsync(
                generatedNotBeforeUtc,
                section,
                CancellationToken.None,
                new OutlineCandidate(outlineDraftAbsolutePath, outlineDraftRelativePath),
                new OutlineCandidate(outlineAbsolutePath, OutlineRelativePath));
            if (generatedSection.Section is null)
            {
                var evidenceMissing = JsonSerializer.Serialize(new
                {
                    run_type = "game-design-gdd-section",
                    failure_code = generatedSection.FailureCode,
                    section_id = section.Id,
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    expected_file = OutlineRelativePath,
                    draft_file = outlineDraftRelativePath,
                    model_capacity_retry_count = modelCapacityRetryCount
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", 424, codexResult.Stdout, codexResult.Stderr, evidenceMissing, CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", generatedSection.FailureCode, generatedSection.FailureSummary, CancellationToken.None);
                await RecordCodexAuditAsync(runId, "game-design-gdd-section", model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return Failure(project.ProjectId, generatedSection.FailureCode, generatedSection.FailureSummary, runId);
            }

            var updatedSection = generatedSection.Section;
            if (string.IsNullOrWhiteSpace(updatedSection.Content))
            {
                var failureCode = "gdd_outline_section_content_missing";
                var failureSummary = "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff1a\u751f\u6210\u7ed3\u679c\u672a\u5199\u5165\u5177\u4f53\u5185\u5bb9\u3002";
                await _metadataStore.CompleteRunAsync(runId, "failed", 424, codexResult.Stdout, codexResult.Stderr, JsonSerializer.Serialize(new
                {
                    run_type = "game-design-gdd-section",
                    failure_code = failureCode,
                    section_id = section.Id,
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    expected_file = OutlineRelativePath,
                    draft_file = outlineDraftRelativePath,
                    model_capacity_retry_count = modelCapacityRetryCount
                }), CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", failureCode, failureSummary, CancellationToken.None);
                await RecordCodexAuditAsync(runId, "game-design-gdd-section", model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return Failure(project.ProjectId, failureCode, failureSummary, runId);
            }

            var mergedOutline = MergeSectionContent(outline, updatedSection);
            await WriteOutlineFilesAsync(outlineAbsolutePath, gddAbsolutePath, mergedOutline, CancellationToken.None);
            await GddMilestoneSpecDocumentWriter.WriteFromGddAsync(project, await File.ReadAllTextAsync(gddAbsolutePath, Encoding.UTF8, CancellationToken.None), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-prompt", promptRelativePath, "Game design outline section prompt"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-output", codexOutputRelativePath, "Game design outline section generation output"), CancellationToken.None);
            if (File.Exists(outlineDraftAbsolutePath))
            {
                await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-draft", outlineDraftRelativePath, "Game design outline section draft"), CancellationToken.None);
            }

            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-outline", OutlineRelativePath, "Game design outline"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, ArtifactType, OutputRelativePath, "Game design document"), CancellationToken.None);

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = "game-design-gdd-section",
                model,
                writer_mode = "lightweight-section-writer",
                section_id = section.Id,
                model_capacity_retry_count = modelCapacityRetryCount,
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

    public async Task<GameDesignDocumentResult> AddSectionAsync(
        string accountId,
        string projectId,
        GameDesignOutlineAddSectionRequest request,
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
        if (string.IsNullOrWhiteSpace(message))
        {
            return Failure(project.ProjectId, "message_required", "请输入新增大纲章节的要求。");
        }

        if (message.Length > MaxMessageChars)
        {
            return Failure(project.ProjectId, "message_too_long", "输入过长，请缩短后再新增大纲章节。");
        }

        if (project.BootstrapStatus == "running" ||
            await _metadataStore.HasRunnerLockAsync(project.ProjectId, cancellationToken) ||
            await _metadataStore.HasActiveRunAsync(project.ProjectId, cancellationToken))
        {
            return Failure(project.ProjectId, "project_busy", "项目有后台任务正在执行，请稍后再新增大纲章节。");
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
            return Failure(project.ProjectId, "outline_not_found", "请先创建策划大纲。");
        }

        var outline = await ReadOutlineDocumentAsync(outlineAbsolutePath, cancellationToken);
        var newSectionId = NextSupplementSectionId(outline);
        var expectedSection = new GameDesignOutlineSection(
            newSectionId,
            "新增游戏模块或大纲章节",
            $"根据用户输入增量补充：{TrimForPrompt(message, 300)}",
            "");

        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, "game-design-gdd-section-add", cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return Failure(project.ProjectId, "project_busy", "项目有后台任务正在执行，请稍后再新增大纲章节。", runId);
        }

        await using var heavyRunnerLease = await _heavyRunnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, "game-design-gdd-section-add", CancellationToken.None);
        await _metadataStore.MarkRunStartedAsync(runId, heavyRunnerLease.QueuePositionAtStart, CancellationToken.None);
        await _metadataStore.UpdateRunProgressAsync(runId, "running", "generation", "正在新增策划大纲章节。", CancellationToken.None);

        try
        {
            var relativeDir = ToSlash(Path.Combine("logs", "phase-a-gdd", project.ProjectId, runId));
            var promptRelativePath = ToSlash(Path.Combine(relativeDir, "gdd-section-add-prompt.md"));
            var codexOutputRelativePath = ToSlash(Path.Combine(relativeDir, "codex-output.txt"));
            var outlineDraftRelativePath = ToSlash(Path.Combine(relativeDir, "gdd-section-add.generated.json"));
            var promptAbsolutePath = ResolveUnderProject(projectRoot, promptRelativePath);
            var codexOutputAbsolutePath = ResolveUnderProject(projectRoot, codexOutputRelativePath);
            var outlineDraftAbsolutePath = ResolveUnderProject(projectRoot, outlineDraftRelativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(promptAbsolutePath)!);
            Directory.CreateDirectory(Path.GetDirectoryName(outlineDraftAbsolutePath)!);
            File.Delete(outlineDraftAbsolutePath);

            var memory = await _metadataStore.GetProjectChatMemoryAsync(project.AccountId, project.ProjectId, CancellationToken.None);
            var historicalAttachments = LoadHistoricalAttachments(projectRoot, []);
            var prompt = BuildAddSectionPrompt(project, outline, expectedSection, message, memory?.MemorySummary, historicalAttachments, DateTimeOffset.UtcNow.ToString("O"), outlineDraftRelativePath);
            await File.WriteAllTextAsync(promptAbsolutePath, prompt, Encoding.UTF8, CancellationToken.None);

            using var timeout = new CancellationTokenSource();
            timeout.CancelAfter(_executionTimeout);
            var model = PrototypeModelPolicy.Normalize(request.Model);
            var runtimeOutputPath = CreateShortRuntimeOutputPath(runId);
            var generatedNotBeforeUtc = DateTimeOffset.UtcNow.AddSeconds(-2);
            var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, CancellationToken.None);
            var billingKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
            var billingBefore = await _billingClient.CaptureAsync(billingKeyName, CancellationToken.None);
            var codexRun = await RunCodexWithModelCapacityRetriesAsync(runId, prompt, runtimeOutputPath, model, project.RepoPath, runtimeCredential, timeout.Token);
            var codexResult = codexRun.Result;
            var modelCapacityRetryCount = codexRun.ModelCapacityRetryCount;
            var providerBilling = new AiCodeMirrorBillingDelta(billingBefore, await _billingClient.CaptureAsync(billingKeyName, CancellationToken.None));

            if (File.Exists(runtimeOutputPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(codexOutputAbsolutePath)!);
                File.Copy(runtimeOutputPath, codexOutputAbsolutePath, overwrite: true);
            }

            if (codexResult.ExitCode != 0)
            {
                var failureCode = IsModelCapacityFailure(codexResult) ? "model_capacity" : "codex_failed";
                var failureSummary = IsModelCapacityFailure(codexResult)
                    ? "新增策划大纲章节失败：大模型访问繁忙，请稍后再试。"
                    : "新增策划大纲章节失败，生成流程未成功完成。";
                var evidenceFailed = JsonSerializer.Serialize(new
                {
                    run_type = "game-design-gdd-section-add",
                    failure_code = failureCode,
                    section_id = expectedSection.Id,
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    draft_file = outlineDraftRelativePath,
                    model_capacity_retry_count = modelCapacityRetryCount
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceFailed, CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", failureCode, failureSummary, CancellationToken.None);
                await RecordCodexAuditAsync(runId, "game-design-gdd-section-add", model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return Failure(project.ProjectId, failureCode, failureSummary, runId);
            }

            var generatedSection = await LoadGeneratedSectionAsync(
                generatedNotBeforeUtc,
                expectedSection,
                CancellationToken.None,
                new OutlineCandidate(outlineDraftAbsolutePath, outlineDraftRelativePath));
            if (generatedSection.Section is null)
            {
                var evidenceMissing = JsonSerializer.Serialize(new
                {
                    run_type = "game-design-gdd-section-add",
                    failure_code = generatedSection.FailureCode,
                    section_id = expectedSection.Id,
                    prompt = promptRelativePath,
                    codex_output = codexOutputRelativePath,
                    draft_file = outlineDraftRelativePath,
                    model_capacity_retry_count = modelCapacityRetryCount
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", 424, codexResult.Stdout, codexResult.Stderr, evidenceMissing, CancellationToken.None);
                await _metadataStore.UpdateRunProgressAsync(runId, "failed", generatedSection.FailureCode, generatedSection.FailureSummary, CancellationToken.None);
                await RecordCodexAuditAsync(runId, "game-design-gdd-section-add", model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                return Failure(project.ProjectId, generatedSection.FailureCode, generatedSection.FailureSummary, runId);
            }

            var updatedOutline = AppendSection(outline, generatedSection.Section);
            await WriteOutlineFilesAsync(outlineAbsolutePath, gddAbsolutePath, updatedOutline, CancellationToken.None);
            var specRelativePaths = await GddMilestoneSpecDocumentWriter.WriteFromGddAsync(project, await File.ReadAllTextAsync(gddAbsolutePath, Encoding.UTF8, CancellationToken.None), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-add-prompt", promptRelativePath, "Game design outline add-section prompt"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-add-output", codexOutputRelativePath, "Game design outline add-section output"), CancellationToken.None);
            if (File.Exists(outlineDraftAbsolutePath))
            {
                await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-add-draft", outlineDraftRelativePath, "Game design outline add-section draft"), CancellationToken.None);
            }

            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-outline", OutlineRelativePath, "Game design outline"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, ArtifactType, OutputRelativePath, "Game design document"), CancellationToken.None);

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = "game-design-gdd-section-add",
                model,
                section_id = generatedSection.Section.Id,
                model_capacity_retry_count = modelCapacityRetryCount,
                outline_file = OutlineRelativePath,
                output_file = OutputRelativePath,
                spec_files = specRelativePaths,
                prompt = promptRelativePath,
                codex_output = codexOutputRelativePath,
                historical_attachment_count = historicalAttachments.Count
            });
            await _metadataStore.CompleteRunAsync(runId, "succeeded", codexResult.ExitCode, codexResult.Stdout, codexResult.Stderr, evidenceJson, CancellationToken.None);
            await RecordCodexAuditAsync(runId, "game-design-gdd-section-add", model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "succeeded", "completed", "策划大纲新增章节已创建。", CancellationToken.None);
            var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, CancellationToken.None);
            return new GameDesignDocumentResult(project.ProjectId, runId, "succeeded", OutlineRelativePath, $"/gdd-outline?projectId={project.ProjectId}", artifacts, Summary: "策划大纲新增章节已创建。");
        }
        catch (OperationCanceledException)
        {
            if (await IsRunCancelledAsync(runId, CancellationToken.None))
            {
                return Cancelled(project.ProjectId, runId, "新增策划大纲章节已取消。");
            }

            await _metadataStore.CompleteRunAsync(runId, "failed", 408, "", $"GDD outline add-section generation exceeded the {_executionTimeout.TotalSeconds:0} second timeout.", "{}", CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "timeout", "新增大纲章节超时，请缩小输入后重试。", CancellationToken.None);
            return Failure(project.ProjectId, "timeout", "新增大纲章节超时，请缩小输入后重试。", runId);
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.Message, "{}", CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "error", "新增大纲章节失败，请稍后重试。", CancellationToken.None);
            return Failure(project.ProjectId, "gdd_section_add_failed", "新增大纲章节失败，请稍后重试。", runId);
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    public async Task<GameDesignOutlineSectionSaveResult?> SaveSectionAsync(
        string accountId,
        string projectId,
        GameDesignOutlineSectionSaveRequest request,
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
        if (string.IsNullOrWhiteSpace(sectionId))
        {
            return null;
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
            return null;
        }

        var outline = await ReadOutlineDocumentAsync(outlineAbsolutePath, cancellationToken);
        var found = false;
        var sections = outline.Sections
            .Select(section =>
            {
                if (!string.Equals(section.Id, sectionId, StringComparison.OrdinalIgnoreCase))
                {
                    return section;
                }

                found = true;
                return section with
                {
                    Skeleton = string.IsNullOrWhiteSpace(request.Skeleton)
                        ? "\u5f85\u8865\u5145\u9aa8\u67b6\u3002"
                        : request.Skeleton.Trim(),
                    Content = request.Content?.Trim() ?? ""
                };
            })
            .ToArray();

        if (!found)
        {
            return null;
        }

        var updated = new GameDesignOutlineDocument(outline.Title, outline.Summary, sections);
        await WriteOutlineFilesAsync(outlineAbsolutePath, gddAbsolutePath, updated, cancellationToken);
        await GddMilestoneSpecDocumentWriter.WriteFromGddAsync(project, await File.ReadAllTextAsync(gddAbsolutePath, Encoding.UTF8, cancellationToken), cancellationToken);
        return new GameDesignOutlineSectionSaveResult(
            project.ProjectId,
            "succeeded",
            sectionId,
            "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u5df2\u4fdd\u5b58\u3002");
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
            var outlineDraftRelativePath = ToSlash(Path.Combine(relativeDir, "gdd-section.generated.json"));
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
            var codexRun = await RunCodexWithModelCapacityRetriesAsync(runId, prompt, runtimeOutputPath, model, project.RepoPath, runtimeCredential, timeout.Token);
            var codexResult = codexRun.Result;
            var modelCapacityRetryCount = codexRun.ModelCapacityRetryCount;
            var providerBilling = new AiCodeMirrorBillingDelta(billingBefore, await _billingClient.CaptureAsync(billingKeyName, CancellationToken.None));
            if (File.Exists(runtimeOutputPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(codexOutputAbsolutePath)!);
                File.Copy(runtimeOutputPath, codexOutputAbsolutePath, overwrite: true);
            }

            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-prompt", promptRelativePath, "Game design outline section prompt"), CancellationToken.None);
            await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-output", codexOutputRelativePath, "Game design outline section generation output"), CancellationToken.None);

            var generatedSection = await LoadGeneratedSectionAsync(
                generatedNotBeforeUtc,
                section,
                CancellationToken.None,
                new OutlineCandidate(outlineDraftAbsolutePath, outlineDraftRelativePath),
                new OutlineCandidate(outlineAbsolutePath, OutlineRelativePath));
            var updatedSection = generatedSection.Section;
            if (codexResult.ExitCode != 0 && updatedSection is null)
            {
                var failureCode = IsModelCapacityFailure(codexResult) ? "model_capacity" : "codex_failed";
                var failureSummary = IsModelCapacityFailure(codexResult)
                    ? "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff1a\u5927\u6a21\u578b\u8bbf\u95ee\u7e41\u5fd9\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002"
                    : "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\u3002";
                sectionResults.Add(new GameDesignOutlineCompleteAllSectionResult(section.Id, section.Title, failureCode, runId, failureCode, failureSummary));
                await RecordCodexAuditAsync(runId, SectionBatchRunType, model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                continue;
            }

            if (updatedSection is null || string.IsNullOrWhiteSpace(updatedSection.Content))
            {
                var failureCode = updatedSection is null ? generatedSection.FailureCode : "gdd_outline_section_content_missing";
                var failureSummary = updatedSection is null
                    ? generatedSection.FailureSummary
                    : "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff1a\u751f\u6210\u7ed3\u679c\u672a\u5199\u5165\u5177\u4f53\u5185\u5bb9\u3002";
                sectionResults.Add(new GameDesignOutlineCompleteAllSectionResult(section.Id, section.Title, failureCode, runId, failureCode, failureSummary));
                await RecordCodexAuditAsync(runId, SectionBatchRunType, model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
                continue;
            }

            var latestOutline = await ReadOutlineDocumentAsync(outlineAbsolutePath, CancellationToken.None);
            var mergedOutline = MergeSectionContent(latestOutline, updatedSection);
            await WriteOutlineFilesAsync(outlineAbsolutePath, gddAbsolutePath, mergedOutline, CancellationToken.None);
            await GddMilestoneSpecDocumentWriter.WriteFromGddAsync(project, await File.ReadAllTextAsync(gddAbsolutePath, Encoding.UTF8, CancellationToken.None), CancellationToken.None);
            if (File.Exists(outlineDraftAbsolutePath))
            {
                await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-section-draft", outlineDraftRelativePath, "Game design outline section draft"), CancellationToken.None);
            }
            sectionResults.Add(new GameDesignOutlineCompleteAllSectionResult(section.Id, section.Title, "succeeded", runId, null, "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u5185\u5bb9\u5df2\u66f4\u65b0\u3002"));
            await RecordCodexAuditAsync(runId, SectionBatchRunType, model, project.ProjectId, codexResult, providerBilling, CancellationToken.None);
        }

        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, "game-design-gdd-outline", OutlineRelativePath, "Game design outline"), CancellationToken.None);
        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(runId, project.ProjectId, ArtifactType, OutputRelativePath, "Game design document"), CancellationToken.None);
        var hasFailures = sectionResults.Any(result => !string.Equals(result.Status, "succeeded", StringComparison.OrdinalIgnoreCase));
        var finalStatus = hasFailures ? "partial_failed" : "succeeded";
        var finalExitCode = hasFailures ? 1 : 0;
        await CompleteBatchRunAsync(project.ProjectId, runId, model, pendingSectionIds.Count, sectionResults, finalStatus, finalExitCode, "", "");
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
        await _metadataStore.UpdateRunProgressAsync(
            runId,
            finalStatus,
            status,
            status == "succeeded" ? "\u7b56\u5212\u5927\u7eb2\u5df2\u6279\u91cf\u8865\u5168\u3002" : "\u7b56\u5212\u5927\u7eb2\u90e8\u5206\u6761\u76ee\u8865\u5168\u5931\u8d25\u3002",
            CancellationToken.None);
        await _metadataStore.CompleteRunAsync(runId, finalStatus, exitCode, stdout, stderr, evidenceJson, CancellationToken.None);
    }

    private static string BuildPrompt(
        ProjectSnapshot project,
        string message,
        GameDesignSceneRouteDocument? sceneRoute,
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
            2. User-confirmed scene route has the same high priority for scene count, scene roles, transitions, return paths, and state carried between scenes.
            3. Current uploaded TXT references have the next priority.
            4. Historical uploaded TXT references have medium priority.
            5. The selected game type `Default Prototype Contract` is workflow-consumed default guidance. Preserve its `Always` scenes and required modules when user input is missing, vague, or compatible. Only override an `Always` scene/module when the current user input, confirmed scene route, or uploaded GDD reference explicitly conflicts with it; record the override reason in the outline skeleton.
            6. Other guide prose and the `Module Matrix` are lower-priority scaffolding used to fill missing GDD dimensions.
            7. Project memory, server chat history, and implicit LLM context have low priority.
            If sources conflict, keep the higher-priority source and discard or ignore conflicting lower-priority details.
            Lay down the selected game type baseline first as reusable genre scaffolding and as default scene/module coverage. Current user input and uploaded references below must override it only when they explicitly conflict.

            Outline requirements:
            - Write user-facing fields in Chinese.
            - The draft file must preserve Chinese characters. Do not replace Chinese with question marks.
            - The raw JSON draft file must be ASCII-only. All Chinese text must be written as JSON unicode escapes in the file, for example "\u6838\u5fc3\u5faa\u73af", so Windows console encoding cannot corrupt it.
            - Use Python with UTF-8 and json.dumps(..., ensure_ascii=True, indent=2) or an equivalent structured JSON writer. Do not use PowerShell Set-Content, Out-File, echo, shell redirection, or console-default encoding to write Chinese text.
            - Before finishing, read the raw draft file as UTF-8 text and verify it does not contain consecutive question marks such as "???".
            - Create 6 to 12 sections covering vision, target player, core loop, player progression, world/levels, combat/interaction, UI/UX/HUD and player feedback, content and asset needs, prototype acceptance criteria, and open questions.
            - The outline must explicitly include the user's reference game or reference genre and explain what design signals are being borrowed.
            - Before using any game-type template signal, verify the reference game's likely public genre/tag signals from the provided context and your BMAD game design knowledge. Do not infer genre from title words alone. For example, a game named with "Tower" is not tower defense unless the gameplay/tag evidence says tower defense.
            - If reference-game title words conflict with the user's explicit gameplay genre, mechanics, controls, or loop, follow the user's explicit gameplay. Do not expose an incorrect template name or template rationale in user-facing title, summary, skeleton, or content.
            - The outline must include scene creation content: first playable scene, important rooms/boards/encounters, and how the player enters the scene.
            - When the selected game type guide includes `Default Prototype Contract`, include its `Always` default scenes and `Always` required modules in the GDD outline unless the user-confirmed GDD explicitly conflicts. If omitted or replaced, include the explicit conflict/override reason in the relevant skeleton.
            - If a user-confirmed scene route is provided, the outline must preserve that route as the authoritative scene topology. Include scene count intent, entry scene, required M1 scenes, transitions, return paths, and state carried. Do not collapse a confirmed multi-scene route into one generic scene.
            - The outline must include keyboard and mouse basics when the target platform is PC, covering movement, aiming/selection, primary action, cancel/dodge/back, and skill/action hotkeys where relevant.
            - The outline must include the basic gameplay loop that the prototype skeleton should materialize first.
            - The outline must include lightweight UI/UX pre-design sufficient to guide feature development, not polished visual design: screen inventory, core player flow map, HUD information priority, input model, key UI states, rough layout/wireframe notes, localization baseline, and accessibility baseline.
            - The outline must state feature-development UI structure rules: placeholder UI is allowed, but screen id, scene path, input action, and state naming must stay stable; player-visible text must not be hardcoded in isolated logic; repeated buttons and panels should share one style/component approach instead of each screen inventing its own.
            - Include a milestone or step-plan section whose steps are derived from the actual GDD scope; do not hardcode M1-M10. The plan may be shorter, longer, or include post-polish steps such as M10-1 when justified.
            - The milestone or step-plan section must contain parseable milestone lines. Each milestone line must start at the beginning of its own line with `M<number> <short title>：`, for example `M1 首个可玩战斗房：目标是...；Scope In...；Scope Out...；Godot/C# 切片...；玩家验收...；验证要求...`. Do not prefix milestone lines with bullets, numbering, bold labels, or prose such as `阶段 1`.
            - Keep each milestone short title before the first Chinese colon under 24 Chinese characters when possible. Put details after that colon; do not put `Scope In` inside the title itself.
            - Write exactly one authoritative milestone list in the whole GDD. Do not add a second simplified summary, duplicate numbering, or alternative M1-Mn list later in the same or another section.
            - Each milestone item must be implementation-facing enough to become a SPEC: include goal, scope in, scope out, Godot/C# scene or system slice, player-verifiable acceptance, and package/playtest validation expectation.
            - M1 must be the first playable skeleton module, not an empty shell: it must specify first playable scene, keyboard/mouse basics, core operation feedback, and the player feel that must be verified after completion.
            - If the reference game, genre/tags, or GDD content imply action movement, collision, hit detection, traversal, enemy pressure, aiming, dodge/roll/dash, platforming, shooter, extraction shooter / 搜打撤, racing, sports, or 3D embodied play, the milestone section must explicitly require matching Godot physics nodes and collision validation instead of UI-only simulation.
            - For action/shooter/extraction milestones, write player acceptance as a local playable loop: continuous movement, aim/facing, primary action, enemy pressure, loot/interaction contact, win/fail/extraction condition, and HUD feedback. State-machine-only or UI-panel-only completion is not acceptable for these milestones.
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

            Game Type Design Template Baseline and Default Prototype Contract:
            {{FormatDesignTemplate(designTemplate)}}

            Current user input, highest priority:
            {{EmptyAsNone(message)}}

            User-confirmed scene route, highest priority for scene topology:
            {{FormatSceneRoute(sceneRoute)}}

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
            Lightweight GDD section writer. This run fills exactly one planning outline section. Do not expand other sections.

            Source file: docs/gdd/gdd-outline.json
            Draft output file: {{outlineDraftRelativePath}}
            Do not invoke or load external skills, agents, plugins, or project-wide context discovery.
            Do not scan the repository. Do not read backup/, logs/, .agents/, .git/, bin/, obj/, or unrelated docs.
            Use only the prompt context below. If absolutely needed, read only the source file to confirm this section's metadata.
            Write a single JSON object to the draft output file with exactly these fields: id, title, skeleton, content.
            The JSON object must describe only the section whose id is "{{section.Id}}". Do not write a full outline document.
            The host service will validate the draft and then merge it into docs/gdd/gdd-outline.json itself. Do not write docs/gdd/gdd-outline.json directly.

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
            - The top-level JSON object must be a single section object, for example { "id": "{{section.Id}}", "title": "{{section.Title}}", "skeleton": "...", "content": "..." }.
            - The draft file must preserve Chinese characters. Do not replace Chinese with question marks.
            - The raw JSON draft file must be ASCII-only. All Chinese text must be written as JSON unicode escapes in the file, for example "\u6838\u5fc3\u5faa\u73af", so Windows console encoding cannot corrupt it.
            - Use Python with UTF-8 and json.dumps(..., ensure_ascii=True, indent=2) or an equivalent structured JSON writer. Do not use PowerShell Set-Content, Out-File, echo, shell redirection, or console-default encoding to write Chinese text.
            - Before finishing, read the raw draft file as UTF-8 text and verify it does not contain consecutive question marks such as "???".
            - Stay inside this section's scope.
            - If this section concerns reference, scenes, controls, UI/UX/HUD, player feedback, core loop, prototype acceptance, or milestones, preserve the hard GDD requirements: reference game/design signal, scene creation content, keyboard/mouse basics, basic gameplay loop, lightweight UI/UX pre-design, and dynamic milestone steps based on actual scope rather than fixed M1-M10.
            - If this section contains milestone or implementation-step content, write parseable milestone lines. Each milestone line must start at the beginning of its own line with `M<number> <short title>：`, for example `M1 首个可玩战斗房：目标是...；Scope In...；Scope Out...；Godot/C# 切片...；玩家验收...；验证要求...`. Do not prefix milestone lines with bullets, numbering, bold labels, or prose such as `阶段 1`.
            - Keep each milestone short title before the first Chinese colon under 24 Chinese characters when possible. Put details after that colon; do not put `Scope In` inside the title itself.
            - Write exactly one authoritative milestone list in the whole GDD. If a milestone list already exists elsewhere in the outline, update or reference that list instead of adding a second simplified summary, duplicate numbering, or alternative M1-Mn list.
            - For UI/UX/HUD content, include only development-guiding pre-design before features are built: screen inventory, core player flow map, HUD information priority, input model, key UI states, rough layout/wireframe notes, localization baseline, and accessibility baseline.
            - For implementation-facing UI/UX notes, keep structure stable: screen id, scene path, input action, and state names should be reusable across milestones; placeholder UI is acceptable; player-visible text should be localized or centralized instead of hardcoded in isolated gameplay code; repeated buttons and panels should share a style/component approach.
            - For post-feature UI/UX retrofit notes, describe when to add theme tokens, component kit, screen contracts, screenshot acceptance, focus checks, localization checks, and overflow checks.
            - content may contain compact headings, bullet points, rules, and acceptance notes.
            - Final assistant reply should be 1 to 3 short sentences only; do not print the whole JSON.
            """;
    }

    private static string BuildAddSectionPrompt(
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
            Incremental GDD outline section writer. This run creates exactly one new planning outline section and must not modify existing outline sections.

            Source file: docs/gdd/gdd-outline.json
            Draft output file: {{outlineDraftRelativePath}}
            Do not invoke or load external skills, agents, plugins, or project-wide context discovery.
            Do not scan the repository. Do not read backup/, logs/, .agents/, .git/, bin/, obj/, or unrelated docs.
            Use only the prompt context below. If absolutely needed, read only the source file to understand existing section titles.
            Write a single JSON object to the draft output file with exactly these fields: id, title, skeleton, content.
            The JSON object must describe only the new section whose id is "{{section.Id}}". Do not write a full outline document.
            The host service will append this section to docs/gdd/gdd-outline.json itself. Do not write docs/gdd/gdd-outline.json directly.

            Hard safety rules:
            - Preserve the original outline structure. Do not rewrite, summarize, reorder, delete, rename, merge, or duplicate existing sections.
            - The new section must be additive and scoped to the user's requested supplement.
            - If the user asks for new game modules or M steps, the generated title should contain `游戏模块` or `里程碑` so the module refresher can find it.
            - If the user asks for new game modules, place only the new M lines in this new section. Do not restate earlier M lines.
            - Milestone lines must be parseable. Each new milestone line must start at the beginning of its own line with `M<number> <short title>：`.
            - Keep milestone titles before the Chinese colon under 24 Chinese characters when possible.
            - Each milestone item must include goal, scope in, scope out, Godot/C# slice, player-verifiable acceptance, and package/playtest validation expectation.
            - If the supplement affects UI/UX/HUD, include screen id, scene path, input action, state naming, localization, accessibility, and overflow baseline as needed.
            - If the supplement affects action movement, collision, hit detection, traversal, enemy pressure, aiming, dodge/roll/dash, platforming, shooter, extraction shooter / 搜打撤, racing, sports, or 3D embodied play, explicitly require matching Godot physics nodes and collision validation instead of UI-only simulation.
            - For action/shooter/extraction supplements, require local playable-loop acceptance: continuous movement, aim/facing, primary action, enemy pressure, loot/interaction contact, win/fail/extraction condition, and HUD feedback. Do not let UI panels or scripted state transitions replace scene-driven gameplay.

            Existing outline, read-only:
            Title: {{outline.Title}}
            Summary: {{outline.Summary}}
            Sections:
            {{FormatOutlineSectionList(outline)}}

            New section seed:
            - id: {{section.Id}}
            - title seed: {{section.Title}}
            - skeleton seed: {{section.Skeleton}}
            - Time: {{now}}

            User input, highest priority:
            {{EmptyAsNone(message)}}

            Historical uploaded TXT references, medium priority:
            {{FormatAttachments(historicalAttachments)}}

            Project chat memory, low priority:
            {{EmptyAsNone(memorySummary)}}

            Requirements:
            - Write title, skeleton, and content in Chinese.
            - The top-level JSON object must be a single section object, for example { "id": "{{section.Id}}", "title": "...", "skeleton": "...", "content": "..." }.
            - The `id` value must remain exactly "{{section.Id}}".
            - The draft file must preserve Chinese characters. Do not replace Chinese with question marks.
            - The raw JSON draft file must be ASCII-only. All Chinese text must be written as JSON unicode escapes in the file.
            - Use Python with UTF-8 and json.dumps(..., ensure_ascii=True, indent=2) or an equivalent structured JSON writer. Do not use PowerShell Set-Content, Out-File, echo, shell redirection, or console-default encoding to write Chinese text.
            - Before finishing, read the raw draft file as UTF-8 text and verify it does not contain consecutive question marks such as "???".
            - content must not be empty.
            - Final assistant reply should be 1 to 3 short sentences only; do not print the whole JSON.
            """;
    }

    private static string FormatOutlineSectionList(GameDesignOutlineDocument outline)
    {
        if (outline.Sections.Count == 0)
        {
            return "(none)";
        }

        var builder = new StringBuilder();
        foreach (var section in outline.Sections)
        {
            builder.AppendLine($"- {section.Id}: {section.Title} | skeleton={TrimForPrompt(section.Skeleton, 220)} | content={(string.IsNullOrWhiteSpace(section.Content) ? "empty" : "filled")}");
        }

        return builder.ToString().TrimEnd();
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

    private static bool IsModelCapacityFailure(HostedProcessResult result)
    {
        return ContainsModelCapacityText(result.Stdout) || ContainsModelCapacityText(result.Stderr);
    }

    private static bool ContainsModelCapacityText(string? text)
    {
        return !string.IsNullOrWhiteSpace(text) &&
               text.Contains("Selected model is at capacity", StringComparison.OrdinalIgnoreCase);
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
        var matchEvidence = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson);
        var direct = catalog.Find(matchEvidence.MatchedGameTypeId);
        if (direct is not null)
        {
            return new SelectedGameTypeDesignTemplate(
                direct,
                "project.game_type_match",
                $"Project game type evidence matched template '{direct.Id}' from Steam genre tags.");
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
            "gdd_content_keyword_match",
            $"GDD input and references matched template '{best.Entry.Id}' with score {best.Score}.");
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

    private async Task<ModelCapacityRetryRun> RunCodexWithModelCapacityRetriesAsync(
        string runId,
        string prompt,
        string runtimeOutputPath,
        string model,
        string repositoryRoot,
        AiCodeMirrorRuntimeCredential runtimeCredential,
        CancellationToken cancellationToken)
    {
        var result = await _processRunner.RunAsync(
            CodexHostedProcessCommandFactory.ApplyRuntime(BuildCodexCommand(prompt, runtimeOutputPath, model, repositoryRoot), runtimeCredential).WithRunId(runId),
            cancellationToken);
        var retryCount = 0;
        while (result.ExitCode != 0 &&
               IsModelCapacityFailure(result) &&
               retryCount < MaxModelCapacityRetries)
        {
            retryCount++;
            await _metadataStore.UpdateRunProgressAsync(runId, "running", "model-capacity-retry", $"\u5927\u6a21\u578b\u8bbf\u95ee\u7e41\u5fd9\uff0c\u6b63\u5728\u7b49\u5f85 5 \u79d2\u540e\u91cd\u8bd5\uff08{retryCount}/{MaxModelCapacityRetries}\uff09\u3002", CancellationToken.None);
            if (_modelCapacityRetryDelay > TimeSpan.Zero)
            {
                await Task.Delay(_modelCapacityRetryDelay, cancellationToken);
            }

            if (File.Exists(runtimeOutputPath))
            {
                File.Delete(runtimeOutputPath);
            }

            result = await _processRunner.RunAsync(
                CodexHostedProcessCommandFactory.ApplyRuntime(BuildCodexCommand(prompt, runtimeOutputPath, model, repositoryRoot), runtimeCredential).WithRunId(runId),
                cancellationToken);
        }

        return new ModelCapacityRetryRun(result, retryCount);
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

    private static string FormatSceneRoute(GameDesignSceneRouteDocument? sceneRoute)
    {
        if (sceneRoute is null || (sceneRoute.Scenes?.Count ?? 0) == 0)
        {
            return "(none)";
        }

        var builder = new StringBuilder();
        builder.AppendLine($"SchemaVersion: {sceneRoute.SchemaVersion}");
        builder.AppendLine($"SceneCountIntent: {sceneRoute.SceneCountIntent}");
        builder.AppendLine($"EntryScene: {sceneRoute.EntryScene}");
        builder.AppendLine("Scenes:");
        foreach (var scene in (sceneRoute.Scenes ?? []).Take(12))
        {
            builder.AppendLine($"- {scene.Id}: {scene.Name}; role={scene.Role}; m1Required={scene.M1Required}; playerGoal={TrimForPrompt(scene.PlayerGoal, 240)}");
        }

        builder.AppendLine("Transitions:");
        var transitions = sceneRoute.Transitions ?? [];
        if (transitions.Count == 0)
        {
            builder.AppendLine("- (none)");
        }
        else
        {
            foreach (var transition in transitions.Take(24))
            {
                var returnsTo = string.IsNullOrWhiteSpace(transition.ReturnsTo) ? "none" : transition.ReturnsTo;
                var stateCarriedValues = transition.StateCarried ?? [];
                var stateCarried = stateCarriedValues.Count == 0
                    ? "none"
                    : string.Join(", ", stateCarriedValues.Take(12));
                builder.AppendLine($"- {transition.From} -> {transition.To}; trigger={TrimForPrompt(transition.Trigger, 180)}; returnsTo={returnsTo}; stateCarried={stateCarried}");
            }
        }

        var confirmation = sceneRoute.SingleSceneConfirmation ?? new GameDesignSingleSceneConfirmation(false, "");
        builder.AppendLine($"SingleSceneConfirmation: allowed={confirmation.Allowed}; reason={TrimForPrompt(confirmation.Reason, 240)}");
        var notes = sceneRoute.Notes ?? [];
        if (notes.Count > 0)
        {
            builder.AppendLine("Notes:");
            foreach (var note in notes.Take(8))
            {
                builder.AppendLine($"- {TrimForPrompt(note, 180)}");
            }
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
            - This baseline is injected before user details to provide missing GDD dimensions.
            - The `Default Prototype Contract` inside the guide excerpt is workflow-consumed default guidance for scene topology and required modules.
            - Preserve `Always` default scenes and `Always` required modules unless current user input, a user-confirmed scene route, or uploaded GDD/reference material explicitly conflicts.
            - If an `Always` item is omitted, renamed beyond recognition, or replaced, record the explicit override reason in the GDD outline skeleton.
            - Other guide prose and `Module Matrix` content are scaffolding and must not override explicit user requirements.

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
        await using var stream = new FileStream(outlinePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
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
        document = NormalizeMilestoneListsForDisplay(document);
        await WriteUtf8AtomicallyAsync(outlinePath, JsonSerializer.Serialize(document, new JsonSerializerOptions
        {
            WriteIndented = true
        }), cancellationToken);
        await WriteUtf8AtomicallyAsync(gddPath, RenderOutlineMarkdown(document), cancellationToken);
    }

    private static async Task WriteUtf8AtomicallyAsync(string path, string content, CancellationToken cancellationToken)
    {
        var directory = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        var tempPath = $"{path}.{Guid.NewGuid():N}.tmp";
        try
        {
            await File.WriteAllTextAsync(tempPath, content, Utf8NoBom, cancellationToken);
            File.Move(tempPath, path, overwrite: true);
        }
        finally
        {
            if (File.Exists(tempPath))
            {
                File.Delete(tempPath);
            }
        }
    }

    private static string StripUtf8Bom(string text)
    {
        return !string.IsNullOrEmpty(text) && text[0] == '\uFEFF'
            ? text[1..]
            : text;
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
                    "\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff1a\u751f\u6210\u7ed3\u679c\u7684 JSON \u65e0\u6cd5\u89e3\u6790\u3002");
            }

            if (ContainsGarbledText(document))
            {
                return GeneratedOutlineResult.Failed(
                    "gdd_outline_garbled_text",
                    "\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff1a\u751f\u6210\u7ed3\u679c\u7684\u4e2d\u6587\u53d8\u6210\u4e86\u8fde\u7eed\u95ee\u53f7\uff0c\u8bf7\u91cd\u65b0\u751f\u6210\u3002");
            }

            if (document.Sections.Count < minimumSectionCount)
            {
                return GeneratedOutlineResult.Failed(
                    "gdd_outline_too_thin",
                    $"\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff1a\u751f\u6210\u7ed3\u679c\u7684\u5927\u7eb2\u7ed3\u6784\u8fc7\u8584\uff0c\u81f3\u5c11\u9700\u8981 {minimumSectionCount} \u4e2a\u6761\u76ee\u3002");
            }

            if (rejectPlaceholderFields && ContainsPlaceholderOutline(document))
            {
                return GeneratedOutlineResult.Failed(
                    "gdd_outline_placeholder",
                    "\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff1a\u751f\u6210\u7ed3\u679c\u7684\u5927\u7eb2\u4ecd\u5305\u542b\u5360\u4f4d\u6807\u9898\u6216\u5360\u4f4d\u9aa8\u67b6\uff0c\u8bf7\u91cd\u65b0\u751f\u6210\u3002");
            }

            if (requireUiUxSection && !ContainsUiUxSection(document))
            {
                return GeneratedOutlineResult.Failed(
                    "gdd_outline_missing_ui_ux",
                    "\u7b56\u5212\u5927\u7eb2\u521b\u5efa\u5931\u8d25\uff1a\u751f\u6210\u7ed3\u679c\u7684\u5927\u7eb2\u7f3a\u5c11 UI/UX/HUD \u6216\u73a9\u5bb6\u53cd\u9988\u76f8\u5173\u6761\u76ee\uff0c\u8bf7\u91cd\u65b0\u751f\u6210\u3002");
            }

            return GeneratedOutlineResult.Success(document);
        }

        return GeneratedOutlineResult.Failed(
            "gdd_outline_not_created",
            "\u751f\u6210\u6d41\u7a0b\u5df2\u8fd0\u884c\uff0c\u4f46\u6ca1\u6709\u751f\u6210\u7b56\u5212\u5927\u7eb2\u6587\u4ef6\u3002");
    }

    private static async Task<GeneratedSectionResult> LoadGeneratedSectionAsync(
        DateTimeOffset notBeforeUtc,
        GameDesignOutlineSection expectedSection,
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

            var raw = StripUtf8Bom(await File.ReadAllTextAsync(candidate.AbsolutePath, Encoding.UTF8, cancellationToken));
            if (LooksGarbled(raw))
            {
                return GeneratedSectionResult.Failed(
                    "gdd_outline_garbled_text",
                    "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff1a\u751f\u6210\u7ed3\u679c\u7684\u4e2d\u6587\u53d8\u6210\u4e86\u8fde\u7eed\u95ee\u53f7\uff0c\u8bf7\u91cd\u65b0\u751f\u6210\u3002");
            }

            GameDesignOutlineSection? section;
            try
            {
                section = ParseGeneratedSection(raw, expectedSection);
            }
            catch (JsonException)
            {
                return GeneratedSectionResult.Failed(
                    "gdd_outline_invalid_json",
                    "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff1a\u751f\u6210\u7ed3\u679c\u7684 JSON \u65e0\u6cd5\u89e3\u6790\u3002");
            }

            if (section is null)
            {
                return GeneratedSectionResult.Failed(
                    "gdd_outline_section_missing",
                    "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff1a\u751f\u6210\u7ed3\u679c\u4e2d\u7f3a\u5c11\u5f53\u524d\u6761\u76ee\u3002");
            }

            if (LooksGarbled(section.Title) || LooksGarbled(section.Skeleton) || LooksGarbled(section.Content))
            {
                return GeneratedSectionResult.Failed(
                    "gdd_outline_garbled_text",
                    "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff1a\u751f\u6210\u7ed3\u679c\u7684\u4e2d\u6587\u53d8\u6210\u4e86\u8fde\u7eed\u95ee\u53f7\uff0c\u8bf7\u91cd\u65b0\u751f\u6210\u3002");
            }

            if (string.IsNullOrWhiteSpace(section.Content))
            {
                return GeneratedSectionResult.Failed(
                    "gdd_outline_section_content_missing",
                    "\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u751f\u6210\u5931\u8d25\uff1a\u751f\u6210\u7ed3\u679c\u672a\u5199\u5165\u5177\u4f53\u5185\u5bb9\u3002");
            }

            return GeneratedSectionResult.Success(section);
        }

        return GeneratedSectionResult.Failed(
            "gdd_outline_not_created",
            "\u751f\u6210\u6d41\u7a0b\u5df2\u8fd0\u884c\uff0c\u4f46\u6ca1\u6709\u751f\u6210\u7b56\u5212\u5927\u7eb2\u6761\u76ee\u6587\u4ef6\u3002");
    }

    private static GameDesignOutlineSection? ParseGeneratedSection(string raw, GameDesignOutlineSection expectedSection)
    {
        using var document = JsonDocument.Parse(raw, new JsonDocumentOptions
        {
            CommentHandling = JsonCommentHandling.Skip,
            AllowTrailingCommas = true
        });
        var root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object)
        {
            return null;
        }

        if (TryGetJsonProperty(root, "sections", out var sections) && sections.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in sections.EnumerateArray())
            {
                var section = ReadSectionElement(item, expectedSection);
                if (section is not null)
                {
                    return section;
                }
            }

            return null;
        }

        return ReadSectionElement(root, expectedSection);
    }

    private static GameDesignOutlineSection? ReadSectionElement(JsonElement element, GameDesignOutlineSection expectedSection)
    {
        if (element.ValueKind != JsonValueKind.Object)
        {
            return null;
        }

        var id = ReadJsonString(element, "id");
        if (!string.Equals(id, expectedSection.Id, StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var title = ReadJsonString(element, "title");
        var skeleton = ReadJsonString(element, "skeleton");
        var content = ReadJsonString(element, "content");
        return new GameDesignOutlineSection(
            expectedSection.Id,
            string.IsNullOrWhiteSpace(title) ? expectedSection.Title : title.Trim(),
            string.IsNullOrWhiteSpace(skeleton) ? expectedSection.Skeleton : skeleton.Trim(),
            content?.Trim() ?? "");
    }

    private static string? ReadJsonString(JsonElement element, string propertyName)
    {
        return TryGetJsonProperty(element, propertyName, out var property) && property.ValueKind == JsonValueKind.String
            ? property.GetString()
            : null;
    }

    private static bool TryGetJsonProperty(JsonElement element, string propertyName, out JsonElement value)
    {
        if (element.TryGetProperty(propertyName, out value))
        {
            return true;
        }

        foreach (var property in element.EnumerateObject())
        {
            if (string.Equals(property.Name, propertyName, StringComparison.OrdinalIgnoreCase))
            {
                value = property.Value;
                return true;
            }
        }

        value = default;
        return false;
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

    private static GameDesignOutlineDocument MergeSectionContents(GameDesignOutlineDocument current, IEnumerable<GameDesignOutlineSection> updatedSections)
    {
        var updatedById = updatedSections
            .GroupBy(section => section.Id, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(group => group.Key, group => group.First(), StringComparer.OrdinalIgnoreCase);
        var sections = current.Sections
            .Select(section => updatedById.TryGetValue(section.Id, out var updated)
                ? section with { Content = updated.Content }
                : section)
            .ToArray();
        return new GameDesignOutlineDocument(current.Title, current.Summary, sections);
    }

    private static GameDesignOutlineDocument AppendSection(GameDesignOutlineDocument current, GameDesignOutlineSection newSection)
    {
        var id = Slug(newSection.Id);
        if (current.Sections.Any(section => string.Equals(section.Id, id, StringComparison.OrdinalIgnoreCase)))
        {
            id = NextSupplementSectionId(current);
        }

        var section = new GameDesignOutlineSection(
            id,
            string.IsNullOrWhiteSpace(newSection.Title) ? "新增大纲章节" : newSection.Title.Trim(),
            string.IsNullOrWhiteSpace(newSection.Skeleton) ? "增量补充当前策划大纲。" : newSection.Skeleton.Trim(),
            newSection.Content?.Trim() ?? "");
        return new GameDesignOutlineDocument(current.Title, current.Summary, current.Sections.Concat([section]).ToArray());
    }

    private static string NextSupplementSectionId(GameDesignOutlineDocument outline)
    {
        for (var index = outline.Sections.Count + 1; index < outline.Sections.Count + 200; index++)
        {
            var id = $"supplement-{index:00}";
            if (!outline.Sections.Any(section => string.Equals(section.Id, id, StringComparison.OrdinalIgnoreCase)))
            {
                return id;
            }
        }

        return $"supplement-{DateTimeOffset.UtcNow:yyyyMMddHHmmss}";
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
        document = NormalizeMilestoneListsForDisplay(document);
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
            var content = string.IsNullOrWhiteSpace(section.Content)
                ? "_\u5f85\u751f\u6210\u5177\u4f53\u5185\u5bb9\u3002_"
                : section.Content;
            builder.AppendLine(content);
            builder.AppendLine();
        }

        return builder.ToString().TrimEnd() + "\n";
    }

    private static GameDesignOutlineDocument NormalizeMilestoneListsForDisplay(GameDesignOutlineDocument document)
    {
        var sectionsWithMilestoneGroups = document.Sections
            .Select((section, index) => new { Section = section, Index = index })
            .Where(item => !string.IsNullOrWhiteSpace(item.Section.Content) &&
                           GddMilestoneTextParser.ContainsMilestoneGroup(item.Section.Content))
            .ToArray();
        if (sectionsWithMilestoneGroups.Length <= 1)
        {
            return document;
        }

        var seenMilestoneIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var hasDuplicateMilestoneIds = false;
        foreach (var group in sectionsWithMilestoneGroups)
        {
            foreach (var step in GddMilestoneTextParser.ExtractExplicitSteps(group.Section.Content))
            {
                if (!seenMilestoneIds.Add(step.StepId))
                {
                    hasDuplicateMilestoneIds = true;
                }
            }
        }

        if (!hasDuplicateMilestoneIds)
        {
            return document;
        }

        var authoritativeIndex = sectionsWithMilestoneGroups
            .FirstOrDefault(item => IsAuthoritativeMilestoneSection(item.Section))?.Index ??
            sectionsWithMilestoneGroups[0].Index;

        var sections = document.Sections.Select((section, index) =>
        {
            if (index == authoritativeIndex ||
                string.IsNullOrWhiteSpace(section.Content) ||
                !GddMilestoneTextParser.ContainsMilestoneGroup(section.Content))
            {
                return section;
            }

            var content = GddMilestoneTextParser.RemoveMilestoneListLines(section.Content);
            if (string.IsNullOrWhiteSpace(content))
            {
                content = "\u672c\u6761\u76ee\u7684\u6a21\u5757\u6e05\u5355\u5df2\u5408\u5e76\u5230\u9996\u4e2a\u6743\u5a01\u91cc\u7a0b\u7891\u6e05\u5355\u4e2d\uff0c\u907f\u514d\u91cd\u590d\u7f16\u53f7\u3002";
            }

            return section with { Content = content };
        }).ToArray();

        return new GameDesignOutlineDocument(document.Title, document.Summary, sections);
    }

    private static bool IsAuthoritativeMilestoneSection(GameDesignOutlineSection section)
    {
        var text = $"{section.Id} {section.Title} {section.Skeleton}";
        return ContainsAnyOrdinalIgnoreCase(
            text,
            "\u91cc\u7a0b\u7891",
            "\u5b9e\u73b0\u6b65\u9aa4",
            "\u5b9e\u65bd\u6b65\u9aa4",
            "\u6a21\u5757\u6b65\u9aa4",
            "\u5f00\u53d1\u6b65\u9aa4",
            "Milestone",
            "Step Plan",
            "Implementation Steps");
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

    private sealed record ModelCapacityRetryRun(HostedProcessResult Result, int ModelCapacityRetryCount);

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

    private sealed record GeneratedSectionResult(
        GameDesignOutlineSection? Section,
        string FailureCode,
        string FailureSummary)
    {
        public static GeneratedSectionResult Success(GameDesignOutlineSection section)
        {
            return new GeneratedSectionResult(section, "", "");
        }

        public static GeneratedSectionResult Failed(string failureCode, string failureSummary)
        {
            return new GeneratedSectionResult(null, failureCode, failureSummary);
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
