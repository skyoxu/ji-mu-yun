using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.IO.Compression;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;
using Microsoft.Extensions.DependencyInjection;

namespace PhaseA.Platform.Readback;

public sealed class ProjectAssetLibraryService
{
    private const string RunType = "project-asset-generation";
    private const string ImportRunType = "project-asset-import";
    private const string SelectionRunType = "project-asset-selection";
    private const int MaxInstructionLength = 2000;
    private const long MaxImportedAssetBytes = 50L * 1024L * 1024L;
    private static readonly string[] ImportableAssetExtensions = [".png", ".jpg", ".jpeg", ".webp", ".glb", ".gltf", ".obj", ".fbx", ".zip"];
    private static readonly string[] RuntimeAssetExtensions = [".png", ".jpg", ".jpeg", ".webp", ".glb", ".gltf", ".obj", ".fbx"];
    private static readonly string[] BlockedArchiveExtensions = [".cs", ".gd", ".dll", ".exe", ".bat", ".cmd", ".ps1", ".sh", ".js", ".ts", ".json", ".pck", ".so", ".dylib"];
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly ProjectAssetImageGenerator _imageGenerator;
    private readonly ILlmRouteEngine? _llmRouteEngine;
    private readonly HeavyRunnerQueueService _assetRunnerQueue;
    private readonly AssetGenerationConcurrencyLimiter _assetConcurrencyLimiter;
    private readonly HttpClient _httpClient;
    private readonly IHostedProcessRunner _processRunner;
    private readonly PrototypeEngineeringClosureService _engineeringClosure;

    public ProjectAssetLibraryService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        ProjectAssetImageGenerator imageGenerator,
        ILlmRouteEngine? llmRouteEngine = null,
        [FromKeyedServices("asset-generation")] HeavyRunnerQueueService? assetRunnerQueue = null,
        AssetGenerationConcurrencyLimiter? assetConcurrencyLimiter = null,
        HttpClient? httpClient = null,
        IHostedProcessRunner? processRunner = null,
        PrototypeEngineeringClosureService? engineeringClosure = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _imageGenerator = imageGenerator;
        _llmRouteEngine = llmRouteEngine;
        _assetRunnerQueue = assetRunnerQueue ?? new HeavyRunnerQueueService(TimeSpan.FromMinutes(4), options.MaxConcurrentAssetGenerations);
        _assetConcurrencyLimiter = assetConcurrencyLimiter ?? new AssetGenerationConcurrencyLimiter(options.MaxConcurrentAssetGenerationsPerAccount);
        _httpClient = httpClient ?? new HttpClient(new HttpClientHandler
        {
            AllowAutoRedirect = false
        });
        _processRunner = processRunner ?? new HostedProcessRunner();
        _engineeringClosure = engineeringClosure ?? new PrototypeEngineeringClosureService();
    }

    public async Task<ProjectAssetLibraryResult?> ReadAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        return ReadLibrary(project);
    }

    public async Task<ProjectAssetGenerationRunResult?> GenerateAsync(
        string accountId,
        string projectId,
        ProjectAssetGenerationRunRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }
        if (request.Unit is null)
        {
            throw new ArgumentException("Asset unit is required.", nameof(request));
        }

        var unit = NormalizeUnit(request.Unit);
        var count = Math.Clamp(request.Count ?? 1, 1, 4);
        var concurrency = await _assetConcurrencyLimiter.TryAcquireAsync(project.AccountId, cancellationToken);
        if (concurrency.Lease is null)
        {
            throw new AssetGenerationConcurrencyLimitException(concurrency.FailureCode ?? "user_asset_generation_concurrency_limit_exceeded");
        }

        await using var accountGenerationLease = concurrency.Lease;
        var actionId = await ResolveActionIdAsync(project, unit, request.FloatingPrompt, cancellationToken);
        var entryId = Guid.NewGuid().ToString("N");
        var outputRelativeDirectory = ToSlash(Path.Combine("Game.Godot", "Prototypes", "ProjectAssetLibrary", unit.Key, entryId));
        var outputAbsoluteDirectory = Path.Combine(project.RepoPath, outputRelativeDirectory.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(outputAbsoluteDirectory);
        var prompt = BuildImagePrompt(project, unit, request.FloatingPrompt, actionId);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var projectLocked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!projectLocked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            throw new InvalidOperationException("Project runner is busy.");
        }

        try
        {
            await using var assetQueueLease = await _assetRunnerQueue.EnterAsync(
                runId,
                project.AccountId,
                project.ProjectId,
                RunType,
                cancellationToken);
            await _metadataStore.MarkRunStartedAsync(runId, assetQueueLease.QueuePositionAtStart, cancellationToken);

            ProjectAssetImageGenerationResult imageResult;
            string? referenceImagePath = null;
            try
            {
                referenceImagePath = WriteTemporaryReferenceImage(outputAbsoluteDirectory, request);
                imageResult = await _imageGenerator.GenerateAsync(
                    project,
                    runId,
                    prompt,
                    outputAbsoluteDirectory,
                    outputRelativeDirectory,
                    SanitizeFileStem(unit.InstanceName, actionId),
                    count,
                    referenceImagePath,
                    cancellationToken);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                var failureEvidence = JsonSerializer.Serialize(new
                {
                    run_type = RunType,
                    action_id = actionId,
                    skill_name = actionId == "map-making-master" ? "generate2dmap" : "generate2dsprite",
                    output_directory = outputRelativeDirectory,
                    failure = ex.Message
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), failureEvidence, CancellationToken.None);
                imageResult = new ProjectAssetImageGenerationResult(
                    runId,
                    "failed",
                    500,
                    "",
                    ex.ToString(),
                    $"轻量图片生成失败：{ex.Message}",
                    [],
                    TimeSpan.Zero);
            }
            finally
            {
                if (!string.IsNullOrWhiteSpace(referenceImagePath) && File.Exists(referenceImagePath))
                {
                    File.Delete(referenceImagePath);
                    var referenceDirectory = Path.GetDirectoryName(referenceImagePath);
                    if (!string.IsNullOrWhiteSpace(referenceDirectory) && Directory.Exists(referenceDirectory))
                    {
                        Directory.Delete(referenceDirectory, recursive: true);
                    }
                }
            }

            foreach (var artifactPath in imageResult.ArtifactPaths)
            {
                await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
                    runId,
                    project.ProjectId,
                    "project-asset-generation-output",
                    artifactPath,
                    "Project asset generation output"), cancellationToken);
            }

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                action_id = actionId,
                skill_name = actionId == "map-making-master" ? "generate2dmap" : "generate2dsprite",
                generation_mode = string.Equals(request.GenerationMode, "image-to-image", StringComparison.OrdinalIgnoreCase) ? "image-to-image" : "text-to-image",
                requested_count = count,
                output_directory = outputRelativeDirectory,
                elapsed_seconds = Math.Round(imageResult.Elapsed.TotalSeconds, 3),
                artifacts = imageResult.ArtifactPaths
            });
            await _metadataStore.CompleteRunAsync(
                runId,
                imageResult.Status,
                imageResult.ExitCode,
                imageResult.Stdout,
                imageResult.Stderr,
                evidenceJson,
                cancellationToken);

            var library = ReadLibrary(project);
            var generatedFiles = EnumerateGeneratedFiles(project.RepoPath, outputAbsoluteDirectory).ToArray();
            var generatedImageFiles = generatedFiles
                .Where(path => IsPreviewResource(ToResPath(project.RepoPath, path)))
                .ToArray();
            var skillSucceeded = string.Equals(imageResult.Status, "succeeded", StringComparison.OrdinalIgnoreCase);
            var entryStatus = skillSucceeded && generatedImageFiles.Length == 0
                ? "no_image_generated"
                : imageResult.Status;
            if (generatedImageFiles.Length == 0)
            {
                var entry = CreateLibraryEntry(project, entryId, runId, actionId, prompt, entryStatus, imageResult, null, generatedImageFiles);
                await UpdateAssetsManifestAsync(project, unit, entry, cancellationToken);
                await WriteAssetRouteEvidenceAsync(
                    project,
                    runId,
                    entryStatus,
                    generatedFiles,
                    entry.SelectionValidation,
                    entryStatus,
                    cancellationToken);
                await _engineeringClosure.TouchMemoryAsync(project, "asset-library", runId, imageResult.Status, null, cancellationToken);
                return new ProjectAssetGenerationRunResult(
                    entryStatus,
                    actionId,
                    entry,
                    library);
            }

            var existingUnit = UpsertUnit(library, unit);
            var entries = generatedImageFiles
                .Select((path, index) => CreateLibraryEntry(project, index == 0 ? entryId : $"{entryId}-{index + 1:00}", runId, actionId, prompt, entryStatus, imageResult, path, generatedImageFiles))
                .ToArray();
            var updatedUnit = existingUnit with
            {
                Entries = [.. entries, .. existingUnit.Entries]
            };
            library = WriteUnit(library, updatedUnit);
            await WriteLibraryAsync(project, library, cancellationToken);
            foreach (var entry in entries)
            {
                await UpdateAssetsManifestAsync(project, unit, entry, cancellationToken);
            }
            await WriteAssetRouteEvidenceAsync(
                project,
                runId,
                imageResult.Status,
                generatedFiles,
                entries[0].SelectionValidation,
                imageResult.Status,
                cancellationToken);
            await _engineeringClosure.TouchMemoryAsync(project, "asset-library", runId, imageResult.Status, null, cancellationToken);

            return new ProjectAssetGenerationRunResult(
                imageResult.Status,
                actionId,
                entries[0],
                ReadLibrary(project));
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    public async Task<ProjectAssetLibraryResult?> SelectAsync(
        string accountId,
        string projectId,
        ProjectAssetSelectionRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        var library = ReadLibrary(project);
        var selectedUnit = library.Units.FirstOrDefault(unit => string.Equals(unit.Key, request.UnitKey, StringComparison.Ordinal));
        if (selectedUnit is null)
        {
            return library;
        }

        var selectedEntry = selectedUnit.Entries.FirstOrDefault(entry => string.Equals(entry.EntryId, request.EntryId, StringComparison.Ordinal));
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, SelectionRunType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            throw new InvalidOperationException("Project runner is busy.");
        }

        try
        {
            var patch = ApplySelectedEntryToScene(project, selectedUnit, selectedEntry);
            var smoke = request.ValidateWithSmoke == true
                ? await RunSelectionSmokeAsync(project, patch, cancellationToken)
                : null;
            var validation = ValidateReplacement(project, selectedUnit, selectedEntry, patch, smoke);
            if (ShouldRollbackSelection(validation))
            {
                patch.Rollback();
                patch = patch with { Applied = false, Reason = $"rolled_back_after_{validation.Status}" };
                validation = ValidateReplacement(project, selectedUnit, selectedEntry, patch, smoke);
            }
            var units = library.Units.Select(unit =>
            {
                if (!string.Equals(unit.Key, request.UnitKey, StringComparison.Ordinal))
                {
                    return unit;
                }

                return unit with
                {
                    SelectedEntryId = ShouldKeepSelection(validation) ? request.EntryId : null,
                    Entries = unit.Entries
                        .Select(entry => entry with
                        {
                            Selected = ShouldKeepSelection(validation) && string.Equals(entry.EntryId, request.EntryId, StringComparison.Ordinal),
                            SelectionValidation = string.Equals(entry.EntryId, request.EntryId, StringComparison.Ordinal) ? validation : entry.SelectionValidation
                        })
                        .ToArray()
                };
            }).ToArray();
            library = library with { Units = units };
            await WriteLibraryAsync(project, library, cancellationToken);
            if (selectedEntry is not null)
            {
                await UpdateAssetsManifestAsync(project, selectedUnit, selectedEntry with { Selected = validation.Status is "ready_for_package_smoke" or "smoke_passed", SelectionValidation = validation, RunId = runId }, cancellationToken);
            }

            var engineeringEvidence = await WriteAssetRouteEvidenceAsync(
                project,
                runId,
                validation.Status is "ready_for_package_smoke" or "smoke_passed" ? "passed" : "failed",
                [],
                validation,
                validation.Status,
                cancellationToken);
            await _engineeringClosure.TouchMemoryAsync(project, "asset-library", runId, validation.Status, null, cancellationToken);
            var evidence = JsonSerializer.Serialize(new
            {
                run_type = SelectionRunType,
                unit_key = request.UnitKey,
                entry_id = request.EntryId,
                validation = validation.Status,
                scene_patch = validation.ScenePatch?.Reason,
                engineering_evidence = engineeringEvidence.RelativePath
            });
            await _metadataStore.CompleteRunAsync(runId, "succeeded", 0, "", "", evidence, cancellationToken);
            return library;
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), "{}", CancellationToken.None);
            throw;
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    public async Task<ProjectAssetImportResult?> ImportAsync(
        string accountId,
        string projectId,
        ProjectAssetImportRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        var project = await GetProjectAsync(accountId, projectId, cancellationToken);
        if (project is null)
        {
            return null;
        }

        if (request.Unit is null)
        {
            throw new ArgumentException("Asset unit is required.", nameof(request));
        }

        var unit = NormalizeUnit(request.Unit);
        var source = NormalizeImportSource(request.QueryOrUrl);
        if (string.IsNullOrWhiteSpace(source.KeywordText) && source.Uri is null)
        {
            throw new ArgumentException("Asset keyword or URL is required.", nameof(request));
        }

        var entryId = Guid.NewGuid().ToString("N");
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, ImportRunType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            throw new InvalidOperationException("Project runner is busy.");
        }

        var outputRelativeDirectory = ToSlash(Path.Combine("Game.Godot", "Prototypes", "ProjectAssetLibrary", unit.Key, entryId));
        var outputAbsoluteDirectory = Path.Combine(project.RepoPath, outputRelativeDirectory.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(outputAbsoluteDirectory);
        var importedFiles = Array.Empty<string>();
        var status = "keyword_only";
        var sourceUrlAllowed = false;
        var assistantMessage = "URL 不在白名单内或未提供 URL，已仅按关键词记录，不执行下载。";

        try
        {
            if (source.Uri is not null && IsAllowedAssetUrl(source.Uri))
            {
                sourceUrlAllowed = true;
                IReadOnlyList<string> downloaded;
                try
                {
                    downloaded = await DownloadAndStageAssetAsync(project, runId, source.Uri, outputAbsoluteDirectory, cancellationToken);
                }
                catch (Exception ex) when (ex is not OperationCanceledException)
                {
                    var failedEntry = CreateAssetImportEntry(
                        project,
                        unit,
                        entryId,
                        runId,
                        source,
                        sourceUrlAllowed,
                        "failed",
                        $"素材下载失败：{ex.Message}",
                        []);
                    await UpdateAssetsManifestAsync(project, unit, failedEntry, cancellationToken);
                    await _engineeringClosure.WriteEvidenceAsync(
                        project,
                        new PrototypeEngineeringEvidence(
                            runId,
                            "asset-library",
                            "failed",
                            null,
                            AssetValidation: PrototypeEngineeringCheckResult.Failed(reason: ex.Message),
                            FailureSummary: [ex.Message]),
                        cancellationToken);
                    throw;
                }

                importedFiles = downloaded.ToArray();
                status = "imported";
                assistantMessage = "已从白名单 URL 导入素材。";
            }

            var library = ReadLibrary(project);
            var existingUnit = UpsertUnit(library, unit);
            var entry = CreateAssetImportEntry(
                project,
                unit,
                entryId,
                runId,
                source,
                sourceUrlAllowed,
                status,
                assistantMessage,
                importedFiles);
            var updatedUnit = existingUnit with
            {
                Entries = [entry, .. existingUnit.Entries]
            };
            library = WriteUnit(library, updatedUnit);
            await WriteLibraryAsync(project, library, cancellationToken);
            await UpdateAssetsManifestAsync(project, unit, entry, cancellationToken);
            var engineeringEvidence = await _engineeringClosure.WriteEvidenceAsync(
                    project,
                    new PrototypeEngineeringEvidence(
                        runId,
                        "asset-library",
                        "passed",
                        null,
                        AssetValidation: status == "imported"
                            ? PrototypeEngineeringCheckResult.Passed()
                            : PrototypeEngineeringCheckResult.Skipped("keyword-only import does not download assets"),
                        ChangedFiles: importedFiles.Select(path => ToSlash(Path.GetRelativePath(project.RepoPath, path))).ToArray(),
                        FailureSummary: []),
                    cancellationToken);
            await _engineeringClosure.TouchMemoryAsync(project, "asset-library", runId, status, null, cancellationToken);
            var runEvidence = JsonSerializer.Serialize(new
            {
                run_type = ImportRunType,
                entry_id = entry.EntryId,
                source_kind = entry.SourceKind,
                source_url_allowed = sourceUrlAllowed,
                engineering_evidence = engineeringEvidence.RelativePath
            });
            await _metadataStore.CompleteRunAsync(runId, status == "imported" || status == "keyword_only" ? "succeeded" : "failed", 0, assistantMessage, "", runEvidence, cancellationToken);

            return new ProjectAssetImportResult(status, sourceUrlAllowed, entry, ReadLibrary(project));
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), "{}", CancellationToken.None);
            throw;
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    private static ProjectAssetLibraryEntry CreateAssetImportEntry(
        ProjectSnapshot project,
        ProjectAssetLibraryUnit unit,
        string entryId,
        string runId,
        ProjectAssetImportSource source,
        bool sourceUrlAllowed,
        string status,
        string assistantMessage,
        IReadOnlyList<string> importedFiles)
    {
        var imageResult = new ProjectAssetImageGenerationResult(
            "",
            status,
            status == "failed" ? 1 : 0,
            "",
            "",
            assistantMessage,
            importedFiles.Select(path => ToSlash(Path.GetRelativePath(project.RepoPath, path))).ToArray(),
            TimeSpan.Zero);
        var entry = CreateLibraryEntry(
            project,
            entryId,
            runId,
            "asset-whitelist-import",
            BuildImportPrompt(unit, source.KeywordText, source.Uri, sourceUrlAllowed),
            status,
            imageResult,
            importedFiles.FirstOrDefault(IsReplacementResourceFile),
            importedFiles);
        return entry with
        {
            SourceKind = sourceUrlAllowed ? "whitelist_url" : "keyword_only",
            SourceUrl = sourceUrlAllowed ? source.Uri?.ToString() : null,
            SourceKeyword = source.KeywordText,
            SourceUrlAllowed = sourceUrlAllowed,
            SelectionValidation = ValidateReplacement(project, unit, entry)
        };
    }

    private async Task<PrototypeEngineeringEvidenceWriteResult> WriteAssetRouteEvidenceAsync(
        ProjectSnapshot project,
        string runId,
        string routeStatus,
        IReadOnlyList<string> changedFiles,
        ProjectAssetReplacementValidation? validation,
        string failureStatus,
        CancellationToken cancellationToken)
    {
        var assetValidation = validation is null
            ? PrototypeEngineeringCheckResult.Skipped("asset is recorded but not selected for scene replacement")
            : validation.Status is "ready_for_package_smoke" or "smoke_passed"
                ? PrototypeEngineeringCheckResult.Passed()
                : PrototypeEngineeringCheckResult.Failed(reason: validation.Status);
        var routePassed = routeStatus is "succeeded" or "imported" or "keyword_only" or "passed" or "ready_for_package_smoke" or "smoke_passed";
        var validationPassed = validation is null || validation.Status is "ready_for_package_smoke" or "smoke_passed";
        var finalStatus = routePassed && validationPassed ? "passed" : "failed";
        return await _engineeringClosure.WriteEvidenceAsync(
            project,
            new PrototypeEngineeringEvidence(
                runId,
                "asset-library",
                finalStatus,
                null,
                AssetValidation: assetValidation,
                ChangedFiles: changedFiles.Select(path => ToProjectRelativePath(project, path)).ToArray(),
                FailureSummary: finalStatus == "passed" ? [] : [failureStatus]),
            cancellationToken);
    }

    private async Task UpdateAssetsManifestAsync(
        ProjectSnapshot project,
        ProjectAssetLibraryUnit unit,
        ProjectAssetLibraryEntry entry,
        CancellationToken cancellationToken)
    {
        _engineeringClosure.EnsureProjectFiles(project);
        var path = Path.Combine(project.RepoPath, PrototypeEngineeringClosureService.AssetsRelativePath.Replace('/', Path.DirectorySeparatorChar));
        var validation = entry.SelectionValidation;
        var boundToScene = entry.Selected && validation?.ScenePatch?.Applied == true;
        var verified = boundToScene &&
                       validation is not null &&
                       validation.ReplacementResourceExists &&
                       validation.ScenePatchable &&
                       validation.CollisionPreserved &&
                       validation.Status is "ready_for_package_smoke" or "smoke_passed";
        var status = verified ? "verified" :
            string.Equals(entry.Status, "keyword_only", StringComparison.OrdinalIgnoreCase) ? "pending" :
            validation?.Status is "smoke_failed" or "needs_review" ? "failed" : "pending";
        var smokeStatus = validation?.SelectionSmoke is { Ran: true, ExitCode: 0 }
            ? "passed"
            : validation?.SelectionSmoke is { Ran: true }
                ? "failed"
                : "skipped";
        var block = $"""

            - id: {entry.EntryId}
              source: {entry.SourceKind ?? entry.ActionId}
              license: <unknown>
              original_path: {FirstOrEmpty(entry.ArtifactPaths)}
              godot_path: {entry.PreviewResourcePath ?? "none"}
              usage: {FirstNonEmpty(unit.Kind, unit.IntendedUse, "asset")}
              imported: {entry.ArtifactPaths.Count > 0}
              bound_to_scene: {(boundToScene ? unit.ScenePath : "none")}
              requires_collision: {RequiresCollisionPreservation(unit)}
              collision_shape: {(validation?.CollisionPreserved == true ? "preserved_or_not_required" : "missing_or_unverified")}
              asset_smoke: {smokeStatus}
              status: {status}
              last_verified_at: {DateTimeOffset.UtcNow:O}
              validation_run_id: {FirstNonEmpty(entry.RunId, entry.EntryId)}
            """;
        await File.AppendAllTextAsync(path, block, Encoding.UTF8, cancellationToken);
    }

    private static string ToProjectRelativePath(ProjectSnapshot project, string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return "";
        }

        return Path.IsPathRooted(path)
            ? ToSlash(Path.GetRelativePath(project.RepoPath, path))
            : ToSlash(path);
    }

    private static string SafePathSegment(string value)
    {
        var chars = value.Select(ch => char.IsLetterOrDigit(ch) || ch is '-' or '_' ? ch : '-').ToArray();
        var safe = new string(chars).Trim('-');
        return string.IsNullOrWhiteSpace(safe) ? "unknown" : safe;
    }

    private async Task<ProjectSnapshot?> GetProjectAsync(string accountId, string projectId, CancellationToken cancellationToken)
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

        return project;
    }

    private static ProjectAssetLibraryResult ReadLibrary(ProjectSnapshot project)
    {
        var path = LibraryPath(project);
        if (!File.Exists(path))
        {
            return new ProjectAssetLibraryResult(project.ProjectId, []);
        }

        try
        {
            return JsonSerializer.Deserialize<ProjectAssetLibraryResult>(
                       File.ReadAllText(path, Encoding.UTF8),
                       new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
                   ?? new ProjectAssetLibraryResult(project.ProjectId, []);
        }
        catch (JsonException)
        {
            return new ProjectAssetLibraryResult(project.ProjectId, []);
        }
    }

    private static async Task WriteLibraryAsync(ProjectSnapshot project, ProjectAssetLibraryResult library, CancellationToken cancellationToken)
    {
        var path = LibraryPath(project);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        await File.WriteAllTextAsync(
            path,
            JsonSerializer.Serialize(library, new JsonSerializerOptions { WriteIndented = true }),
            Encoding.UTF8,
            cancellationToken);
    }

    private static string LibraryPath(ProjectSnapshot project)
    {
        return Path.Combine(project.RepoPath, "meta", "assets", "library.json");
    }

    private static ProjectAssetLibraryUnit NormalizeUnit(ProjectAssetUnitRequest unit)
    {
        var scenePath = Trim(unit.ScenePath);
        var instanceName = Trim(unit.InstanceName);
        var resourcePath = Trim(unit.ResourcePath);
        var key = string.IsNullOrWhiteSpace(unit.UnitKey)
            ? ComputeUnitKey(scenePath, instanceName, resourcePath, Trim(unit.Kind))
            : Trim(unit.UnitKey);
        return new ProjectAssetLibraryUnit(
            key,
            instanceName,
            Trim(unit.NodeType),
            scenePath,
            resourcePath,
            Trim(unit.Kind),
            Trim(unit.IntendedUse),
            Trim(unit.Reason),
            null,
            []);
    }

    private static ProjectAssetLibraryUnit UpsertUnit(ProjectAssetLibraryResult library, ProjectAssetLibraryUnit unit)
    {
        return library.Units.FirstOrDefault(existing => string.Equals(existing.Key, unit.Key, StringComparison.Ordinal))
               ?? unit;
    }

    private static ProjectAssetLibraryResult WriteUnit(ProjectAssetLibraryResult library, ProjectAssetLibraryUnit unit)
    {
        var units = library.Units
            .Where(existing => !string.Equals(existing.Key, unit.Key, StringComparison.Ordinal))
            .Append(unit)
            .OrderBy(existing => existing.ScenePath, StringComparer.OrdinalIgnoreCase)
            .ThenBy(existing => existing.InstanceName, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        return library with { Units = units };
    }

    private static ProjectAssetLibraryEntry CreateLibraryEntry(
        ProjectSnapshot project,
        string entryId,
        string runId,
        string actionId,
        string prompt,
        string entryStatus,
        ProjectAssetImageGenerationResult imageResult,
        string? generatedImageFile,
        IReadOnlyList<string> generatedImageFiles)
    {
        var previewResourcePath = string.IsNullOrWhiteSpace(generatedImageFile)
            ? null
            : ToResPath(project.RepoPath, generatedImageFile);
        return new ProjectAssetLibraryEntry(
            entryId,
            DateTimeOffset.UtcNow.ToString("O"),
            runId,
            actionId,
            actionId == "map-making-master" ? "generate2dmap" : "generate2dsprite",
            prompt,
            entryStatus,
            imageResult.AssistantMessage,
            imageResult.ArtifactPaths.Concat(generatedImageFiles.Select(path => ToSlash(Path.GetRelativePath(project.RepoPath, path)))).Distinct(StringComparer.Ordinal).ToArray(),
            previewResourcePath,
            false,
            null,
            null,
            null,
            false,
            null);
    }

    private async Task<IReadOnlyList<string>> DownloadAndStageAssetAsync(
        ProjectSnapshot project,
        string runId,
        Uri sourceUri,
        string outputAbsoluteDirectory,
        CancellationToken cancellationToken)
    {
        var quarantineDirectory = Path.Combine(
            project.RepoPath,
            "logs",
            "prototype-evidence",
            SafePathSegment(project.ProjectId),
            SafePathSegment(runId),
            "asset-quarantine");
        Directory.CreateDirectory(quarantineDirectory);
        using var response = await _httpClient.GetAsync(sourceUri, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        if (IsRedirectStatusCode(response.StatusCode))
        {
            throw new ArgumentException("Imported asset redirects are not allowed.");
        }

        if (response.RequestMessage?.RequestUri is { } finalUri &&
            !SameAssetUri(sourceUri, finalUri))
        {
            throw new ArgumentException("Imported asset redirects are not allowed.");
        }

        response.EnsureSuccessStatusCode();
        if (response.Content.Headers.ContentLength is > MaxImportedAssetBytes)
        {
            throw new ArgumentException("Imported asset is too large.");
        }

        var extension = Path.GetExtension(sourceUri.AbsolutePath).ToLowerInvariant();
        if (!ImportableAssetExtensions.Contains(extension, StringComparer.OrdinalIgnoreCase))
        {
            extension = ExtensionFromContentType(response.Content.Headers.ContentType?.MediaType);
        }

        if (!ImportableAssetExtensions.Contains(extension, StringComparer.OrdinalIgnoreCase))
        {
            throw new ArgumentException("Imported asset type is not allowed.");
        }

        var fileName = $"{SanitizeFileStem(Path.GetFileNameWithoutExtension(sourceUri.AbsolutePath), "asset-whitelist-import")}{extension}";
        var quarantinePath = Path.Combine(quarantineDirectory, fileName);
        await using (var input = await response.Content.ReadAsStreamAsync(cancellationToken))
        await using (var output = File.Create(quarantinePath))
        {
            var buffer = new byte[81920];
            long total = 0;
            while (true)
            {
                var read = await input.ReadAsync(buffer.AsMemory(0, buffer.Length), cancellationToken);
                if (read == 0)
                {
                    break;
                }

                total += read;
                if (total > MaxImportedAssetBytes)
                {
                    throw new ArgumentException("Imported asset is too large.");
                }

                await output.WriteAsync(buffer.AsMemory(0, read), cancellationToken);
            }
        }

        if (extension.Equals(".zip", StringComparison.OrdinalIgnoreCase))
        {
            return ExtractAllowedArchiveAssets(project, quarantinePath, outputAbsoluteDirectory);
        }

        if (!RuntimeAssetExtensions.Contains(extension, StringComparer.OrdinalIgnoreCase))
        {
            throw new ArgumentException("Imported asset type is not allowed for runtime use.");
        }

        var stagedPath = ResolveUnderDirectory(outputAbsoluteDirectory, fileName);
        File.Copy(quarantinePath, stagedPath, overwrite: false);
        return [stagedPath];
    }

    private static IReadOnlyList<string> ExtractAllowedArchiveAssets(
        ProjectSnapshot project,
        string archivePath,
        string outputAbsoluteDirectory)
    {
        var staged = new List<string>();
        using var archive = ZipFile.OpenRead(archivePath);
        foreach (var entry in archive.Entries)
        {
            if (string.IsNullOrWhiteSpace(entry.Name))
            {
                continue;
            }

            var extension = Path.GetExtension(entry.Name).ToLowerInvariant();
            if (BlockedArchiveExtensions.Contains(extension, StringComparer.OrdinalIgnoreCase))
            {
                throw new ArgumentException("Imported archive contains dynamic code or executable files.");
            }

            if (!RuntimeAssetExtensions.Contains(extension, StringComparer.OrdinalIgnoreCase))
            {
                continue;
            }

            if (entry.Length > MaxImportedAssetBytes)
            {
                throw new ArgumentException("Imported archive entry is too large.");
            }

            var entryName = entry.FullName.Replace('\\', '/');
            if (entryName.StartsWith("/", StringComparison.Ordinal) ||
                entryName.Contains("../", StringComparison.Ordinal) ||
                entryName.Contains("..\\", StringComparison.Ordinal))
            {
                throw new ArgumentException("Imported archive entry path is not allowed.");
            }

            var outputName = $"{SanitizeFileStem(Path.GetFileNameWithoutExtension(entry.Name), "asset")}{extension}";
            var outputPath = ResolveUnderDirectory(outputAbsoluteDirectory, outputName);
            using var input = entry.Open();
            using var output = File.Create(outputPath);
            input.CopyTo(output);
            if (!WorkspacePathPolicy.IsUnderRoot(project.RepoPath, outputPath))
            {
                throw new ArgumentException("Imported archive entry escaped the project repository root.");
            }

            staged.Add(outputPath);
        }

        if (staged.Count == 0)
        {
            throw new ArgumentException("Imported archive did not contain supported runtime assets.");
        }

        return staged;
    }

    private static string ResolveUnderDirectory(string root, string fileName)
    {
        var path = Path.GetFullPath(Path.Combine(root, fileName));
        if (!WorkspacePathPolicy.IsUnderRoot(root, path))
        {
            throw new ArgumentException("Imported asset path escaped the output directory.");
        }

        return path;
    }

    private static bool IsRedirectStatusCode(HttpStatusCode statusCode)
    {
        var code = (int)statusCode;
        return code is >= 300 and <= 399;
    }

    private static bool SameAssetUri(Uri left, Uri right)
    {
        return string.Equals(left.Scheme, right.Scheme, StringComparison.OrdinalIgnoreCase) &&
               string.Equals(left.Host, right.Host, StringComparison.OrdinalIgnoreCase) &&
               left.Port == right.Port &&
               string.Equals(left.AbsolutePath, right.AbsolutePath, StringComparison.Ordinal) &&
               string.Equals(left.Query, right.Query, StringComparison.Ordinal);
    }

    private bool IsAllowedAssetUrl(Uri uri)
    {
        if (uri.Scheme != Uri.UriSchemeHttps)
        {
            return false;
        }

        return _options.AssetAllowedUrlPrefixes.Any(prefix => IsAllowedAssetUrlPrefix(uri, prefix));
    }

    private static bool IsAllowedAssetUrlPrefix(Uri uri, string prefix)
    {
        if (!Uri.TryCreate(prefix, UriKind.Absolute, out var allowed) ||
            allowed.Scheme != Uri.UriSchemeHttps ||
            !string.Equals(uri.Host, allowed.Host, StringComparison.OrdinalIgnoreCase) ||
            uri.Port != allowed.Port)
        {
            return false;
        }

        var allowedPath = string.IsNullOrWhiteSpace(allowed.AbsolutePath) ? "/" : allowed.AbsolutePath;
        if (allowedPath == "/")
        {
            return true;
        }

        var requestedPath = uri.AbsolutePath;
        var exactPath = allowedPath.TrimEnd('/');
        return string.Equals(requestedPath, exactPath, StringComparison.OrdinalIgnoreCase) ||
               requestedPath.StartsWith(exactPath + "/", StringComparison.OrdinalIgnoreCase);
    }

    private static ProjectAssetImportSource NormalizeImportSource(string? raw)
    {
        var text = Trim(raw);
        if (Uri.TryCreate(text, UriKind.Absolute, out var uri) &&
            (string.Equals(uri.Scheme, Uri.UriSchemeHttp, StringComparison.OrdinalIgnoreCase) ||
             string.Equals(uri.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase)))
        {
            return new ProjectAssetImportSource(uri, ExtractKeywordsFromUrl(uri));
        }

        return new ProjectAssetImportSource(null, text);
    }

    private static string ExtractKeywordsFromUrl(Uri uri)
    {
        var pathText = uri.AbsolutePath
            .Replace('/', ' ')
            .Replace('-', ' ')
            .Replace('_', ' ');
        var fileName = Path.GetFileNameWithoutExtension(pathText);
        var host = uri.Host.Replace("www.", "", StringComparison.OrdinalIgnoreCase);
        return Compact($"{host} {fileName}");
    }

    private static ProjectAssetReplacementValidation ValidateReplacement(
        ProjectSnapshot project,
        ProjectAssetLibraryUnit unit,
        ProjectAssetLibraryEntry? entry,
        ProjectAssetScenePatchResult? patch = null,
        ProjectAssetSelectionSmokeResult? smoke = null)
    {
        var checks = new List<ProjectAssetReplacementValidationCheck>();
        var replacementExists = false;
        var scenePatchable = false;
        var collisionPreserved = false;
        var smokeRequired = true;
        var previewPath = entry?.PreviewResourcePath;

        if (IsResPath(previewPath))
        {
            var fullPreviewPath = ResolveResPath(project.RepoPath, previewPath!);
            replacementExists = File.Exists(fullPreviewPath);
            checks.Add(new ProjectAssetReplacementValidationCheck(
                "replacement_resource_exists",
                replacementExists ? "passed" : "failed",
                previewPath!));
        }
        else
        {
            checks.Add(new ProjectAssetReplacementValidationCheck(
                "replacement_resource_exists",
                "failed",
                "Selected entry has no res:// preview resource."));
        }

        if (IsResPath(unit.ScenePath) && unit.ScenePath.EndsWith(".tscn", StringComparison.OrdinalIgnoreCase))
        {
            var scenePath = ResolveResPath(project.RepoPath, unit.ScenePath);
            var sceneExists = File.Exists(scenePath);
            var sceneText = sceneExists ? File.ReadAllText(scenePath, Encoding.UTF8) : "";
            scenePatchable = patch?.Applied == true ||
                             (sceneExists &&
                              ((IsResPath(unit.ResourcePath) && sceneText.Contains($"path=\"{unit.ResourcePath}\"", StringComparison.Ordinal)) ||
                               IsDirectTextureNodeType(unit.NodeType)));
            collisionPreserved = !RequiresCollisionPreservation(unit) || SceneContainsCollisionNearUnit(sceneText, unit.InstanceName);
            checks.Add(new ProjectAssetReplacementValidationCheck(
                "scene_patchable",
                scenePatchable ? "passed" : "failed",
                unit.ScenePath));
            checks.Add(new ProjectAssetReplacementValidationCheck(
                "collision_preserved",
                collisionPreserved ? "passed" : "warning",
                collisionPreserved ? "Collision check passed or is not required." : "Prop/player/enemy replacement should preserve CollisionShape/StaticBody/CharacterBody validation."));
        }
        else
        {
            checks.Add(new ProjectAssetReplacementValidationCheck(
                "scene_patchable",
                "warning",
                "No .tscn scene path is available for direct replacement validation."));
            collisionPreserved = true;
        }

        if (patch is not null)
        {
            checks.Add(new ProjectAssetReplacementValidationCheck(
                "scene_patch_applied",
                patch.Applied ? "passed" : "warning",
                patch.Reason));
        }

        if (smoke is not null)
        {
            checks.Add(new ProjectAssetReplacementValidationCheck(
                "selection_smoke",
                smoke.Ran && smoke.ExitCode == 0 ? "passed" : smoke.Ran ? "failed" : "warning",
                smoke.Reason));
        }

        checks.Add(new ProjectAssetReplacementValidationCheck(
            "post_replace_smoke_required",
            smoke?.Ran == true && smoke.ExitCode == 0 ? "passed" : "warning",
            smoke?.Ran == true && smoke.ExitCode == 0
                ? "Selection smoke passed; package smoke remains a final safety net."
                : "Run package or Godot smoke after replacement to verify import, collision, and scene load."));
        var status = smoke?.Ran == true && smoke.ExitCode != 0
            ? "smoke_failed"
            : replacementExists && scenePatchable && collisionPreserved
                ? smoke?.Ran == true ? "smoke_passed" : "ready_for_package_smoke"
                : "needs_review";
        return new ProjectAssetReplacementValidation(
            status,
            replacementExists,
            scenePatchable,
            collisionPreserved,
            smokeRequired && smoke?.ExitCode != 0,
            smoke?.Ran == true && smoke.ExitCode == 0
                ? "素材已替换并通过选择时 smoke；打包时仍会复验。"
                : "素材替换不会主动改玩法规则；打包或 Godot smoke 时应验证资源导入、碰撞和场景加载。",
            checks,
            patch,
            smoke);
    }

    private static bool ShouldRollbackSelection(ProjectAssetReplacementValidation validation)
    {
        return validation.ScenePatch?.Applied == true &&
               validation.Status is "smoke_failed" or "needs_review";
    }

    private static bool ShouldKeepSelection(ProjectAssetReplacementValidation validation)
    {
        if (validation.Status is "ready_for_package_smoke" or "smoke_passed")
        {
            return true;
        }

        if (validation.Status != "needs_review" || validation.ScenePatch?.Applied == true)
        {
            return false;
        }

        return validation.ScenePatch?.Reason.StartsWith("rolled_back_after_", StringComparison.OrdinalIgnoreCase) != true;
    }

    private static ProjectAssetScenePatchResult ApplySelectedEntryToScene(
        ProjectSnapshot project,
        ProjectAssetLibraryUnit unit,
        ProjectAssetLibraryEntry? entry)
    {
        if (!IsResPath(entry?.PreviewResourcePath))
        {
            return ProjectAssetScenePatchResult.NoChange("selected_entry_has_no_preview_resource", null);
        }

        if (!IsResPath(unit.ScenePath) || !unit.ScenePath.EndsWith(".tscn", StringComparison.OrdinalIgnoreCase))
        {
            return ProjectAssetScenePatchResult.NoChange("scene_path_not_patchable", null);
        }

        var scenePath = ResolveResPath(project.RepoPath, unit.ScenePath);
        if (!File.Exists(scenePath))
        {
            return ProjectAssetScenePatchResult.NoChange("scene_file_missing", unit.ScenePath);
        }

        var sceneText = File.ReadAllText(scenePath, Encoding.UTF8);
        var selectedPreviewResourcePath = entry!.PreviewResourcePath!;
        if (IsResPath(unit.ResourcePath))
        {
            var oldToken = $"path=\"{unit.ResourcePath}\"";
            var newToken = $"path=\"{selectedPreviewResourcePath}\"";
            if (sceneText.Contains(newToken, StringComparison.Ordinal))
            {
                return ProjectAssetScenePatchResult.NoChange("scene_already_uses_selected_resource", unit.ScenePath, applied: true);
            }

            if (!sceneText.Contains(oldToken, StringComparison.Ordinal))
            {
                return ProjectAssetScenePatchResult.NoChange("original_resource_reference_missing", unit.ScenePath);
            }

            File.WriteAllText(scenePath, sceneText.Replace(oldToken, newToken, StringComparison.Ordinal), Encoding.UTF8);
            return ProjectAssetScenePatchResult.Changed("scene_resource_reference_replaced", unit.ScenePath, scenePath, sceneText);
        }

        if (!IsDirectTextureNodeType(unit.NodeType))
        {
            return ProjectAssetScenePatchResult.NoChange("node_type_not_direct_texture", unit.ScenePath);
        }

        var updatedSceneText = AddTextureReferenceToExistingNode(sceneText, unit, selectedPreviewResourcePath);
        if (updatedSceneText is null)
        {
            return ProjectAssetScenePatchResult.NoChange("target_node_missing", unit.ScenePath);
        }

        if (!string.Equals(updatedSceneText, sceneText, StringComparison.Ordinal))
        {
            File.WriteAllText(scenePath, updatedSceneText, Encoding.UTF8);
            return ProjectAssetScenePatchResult.Changed("scene_texture_reference_inserted", unit.ScenePath, scenePath, sceneText);
        }

        return ProjectAssetScenePatchResult.NoChange("scene_texture_reference_inserted", unit.ScenePath, applied: true);
    }

    private static bool RequiresCollisionPreservation(ProjectAssetLibraryUnit unit)
    {
        var text = $"{unit.Kind} {unit.InstanceName} {unit.NodeType} {unit.IntendedUse} {unit.Reason}".ToLowerInvariant();
        return text.Contains("prop", StringComparison.Ordinal) ||
               text.Contains("wall", StringComparison.Ordinal) ||
               text.Contains("obstacle", StringComparison.Ordinal) ||
               text.Contains("collision", StringComparison.Ordinal) ||
               text.Contains("player", StringComparison.Ordinal) ||
               text.Contains("enemy", StringComparison.Ordinal);
    }

    private static bool IsResPath(string? value)
    {
        return !string.IsNullOrWhiteSpace(value) && value.StartsWith("res://", StringComparison.Ordinal);
    }

    private static bool IsDirectTextureNodeType(string? nodeType)
    {
        return string.Equals(nodeType, "Sprite2D", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(nodeType, "TextureRect", StringComparison.OrdinalIgnoreCase);
    }

    private static string ResolveResPath(string projectRoot, string resourcePath)
    {
        if (!IsResPath(resourcePath))
        {
            throw new InvalidOperationException("Resource path must use res://.");
        }

        var relativePath = resourcePath["res://".Length..].Replace('/', Path.DirectorySeparatorChar);
        var fullPath = Path.GetFullPath(Path.Combine(projectRoot, relativePath));
        if (!WorkspacePathPolicy.IsUnderRoot(projectRoot, fullPath))
        {
            throw new InvalidOperationException("Resource path escaped project repository root.");
        }

        return fullPath;
    }

    private static string? AddTextureReferenceToExistingNode(
        string sceneText,
        ProjectAssetLibraryUnit unit,
        string previewResourcePath)
    {
        var lines = sceneText.Replace("\r\n", "\n").Split('\n').ToList();
        var extResourceId = FindExtResourceId(lines, previewResourcePath);
        if (string.IsNullOrWhiteSpace(extResourceId))
        {
            extResourceId = $"phasea_asset_{StableShortId(unit.Key, previewResourcePath)}";
            var insertIndex = LastExtResourceLineIndex(lines);
            if (insertIndex < 0)
            {
                insertIndex = lines.FindIndex(line => line.StartsWith("[gd_scene", StringComparison.Ordinal));
            }

            lines.Insert(Math.Max(0, insertIndex + 1), $"[ext_resource type=\"Texture2D\" path=\"{previewResourcePath}\" id=\"{extResourceId}\"]");
        }

        var nodeIndex = FindNodeLineIndex(lines, unit.InstanceName, unit.NodeType);
        if (nodeIndex < 0)
        {
            return null;
        }

        var nextSectionIndex = lines.FindIndex(nodeIndex + 1, line => line.StartsWith("[node ", StringComparison.Ordinal) || line.StartsWith("[connection ", StringComparison.Ordinal) || line.StartsWith("[editable ", StringComparison.Ordinal));
        if (nextSectionIndex < 0)
        {
            nextSectionIndex = lines.Count;
        }

        for (var i = nodeIndex + 1; i < nextSectionIndex; i++)
        {
            if (lines[i].TrimStart().StartsWith("texture =", StringComparison.Ordinal))
            {
                lines[i] = $"texture = ExtResource(\"{extResourceId}\")";
                return string.Join('\n', lines);
            }
        }

        lines.Insert(nodeIndex + 1, $"texture = ExtResource(\"{extResourceId}\")");
        return string.Join('\n', lines);
    }

    private static string? FindExtResourceId(IReadOnlyList<string> lines, string previewResourcePath)
    {
        foreach (var line in lines)
        {
            var match = Regex.Match(line, "^\\[ext_resource\\s+.*path=\"(?<path>[^\"]+)\".*id=\"(?<id>[^\"]+)\".*\\]$");
            if (match.Success && string.Equals(match.Groups["path"].Value, previewResourcePath, StringComparison.Ordinal))
            {
                return match.Groups["id"].Value;
            }
        }

        return null;
    }

    private static int LastExtResourceLineIndex(IReadOnlyList<string> lines)
    {
        for (var i = lines.Count - 1; i >= 0; i--)
        {
            if (lines[i].StartsWith("[ext_resource ", StringComparison.Ordinal))
            {
                return i;
            }
        }

        return -1;
    }

    private static int FindNodeLineIndex(IReadOnlyList<string> lines, string instanceName, string nodeType)
    {
        for (var i = 0; i < lines.Count; i++)
        {
            var line = lines[i];
            if (line.StartsWith("[node ", StringComparison.Ordinal) &&
                line.Contains($"name=\"{instanceName}\"", StringComparison.Ordinal) &&
                line.Contains($"type=\"{nodeType}\"", StringComparison.Ordinal))
            {
                return i;
            }
        }

        return -1;
    }

    private static string StableShortId(string unitKey, string previewResourcePath)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes($"{unitKey}\n{previewResourcePath}"));
        return Convert.ToHexString(bytes, 0, 6).ToLowerInvariant();
    }

    private async Task<ProjectAssetSelectionSmokeResult> RunSelectionSmokeAsync(
        ProjectSnapshot project,
        ProjectAssetScenePatchResult patch,
        CancellationToken cancellationToken)
    {
        if (!patch.Applied || string.IsNullOrWhiteSpace(patch.ScenePath))
        {
            return ProjectAssetSelectionSmokeResult.Skipped(patch.Reason, patch.ScenePath);
        }

        if (string.IsNullOrWhiteSpace(_options.GodotBin))
        {
            return ProjectAssetSelectionSmokeResult.Skipped("godot_bin_not_configured", patch.ScenePath);
        }

        var command = new HostedProcessCommand(
            _options.PythonCommand,
            [
                "-3",
                ResolveRepositoryScriptPath("scripts/python/smoke_headless.py"),
                "--godot-bin",
                _options.GodotBin,
                "--project-path",
                project.RepoPath,
                "--scene",
                patch.ScenePath,
                "--timeout-sec",
                "10",
                "--strict"
            ],
            project.RepoPath,
            PrototypeValidationProcessEnvironment.Create(project.RepoPath, new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["GODOT_BIN"] = _options.GodotBin
            }));
        var result = await _processRunner.RunAsync(command, cancellationToken);
        var exitCode = ResolveSmokeExitCode(result);
        return new ProjectAssetSelectionSmokeResult(true, exitCode, exitCode == 0 ? "selection_scene_smoke_passed" : "selection_scene_smoke_failed", patch.ScenePath, result.Stdout, result.Stderr);
    }

    private string ResolveRepositoryScriptPath(string relativePath)
    {
        return Path.GetFullPath(Path.Combine(_options.RepositoryRoot, relativePath.Replace('/', Path.DirectorySeparatorChar)));
    }

    private static int ResolveSmokeExitCode(HostedProcessResult result)
    {
        var combined = $"{result.Stdout}\n{result.Stderr}";
        return ContainsGodotFailureMarker(combined) ? 1 : result.ExitCode;
    }

    private static bool ContainsGodotFailureMarker(string output)
    {
        return output.Contains("SCRIPT ERROR:", StringComparison.OrdinalIgnoreCase) ||
               output.Contains("ERROR:", StringComparison.OrdinalIgnoreCase) ||
               output.Contains("Parse Error", StringComparison.OrdinalIgnoreCase) ||
               output.Contains("Cannot instantiate C# script", StringComparison.OrdinalIgnoreCase);
    }

    private static bool SceneContainsCollisionNearUnit(string sceneText, string instanceName)
    {
        if (string.IsNullOrWhiteSpace(sceneText))
        {
            return false;
        }

        if (sceneText.Contains("CollisionShape", StringComparison.OrdinalIgnoreCase) ||
            sceneText.Contains("StaticBody", StringComparison.OrdinalIgnoreCase) ||
            sceneText.Contains("CharacterBody", StringComparison.OrdinalIgnoreCase) ||
            sceneText.Contains("RigidBody", StringComparison.OrdinalIgnoreCase) ||
            sceneText.Contains("Area", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        return !string.IsNullOrWhiteSpace(instanceName) &&
               sceneText.Contains($"{instanceName}/Collision", StringComparison.OrdinalIgnoreCase);
    }

    private static string BuildImportPrompt(ProjectAssetLibraryUnit unit, string? keyword, Uri? uri, bool urlAllowed)
    {
        return $"""
            Import external or keyword asset candidate for this hosted Godot project asset unit.

            Asset unit:
            - InstanceName: {unit.InstanceName}
            - NodeType: {unit.NodeType}
            - ScenePath: {unit.ScenePath}
            - CurrentResource: {unit.ResourcePath}
            - SuggestedKind: {unit.Kind}
            - IntendedUse: {unit.IntendedUse}
            - Reason: {unit.Reason}

            Source:
            - Keyword: {Trim(keyword)}
            - URL: {(uri is null ? "" : uri.ToString())}
            - URL allowed for download: {urlAllowed}

            Replacement rules:
            - Do not change gameplay rules.
            - Preserve collision expectations for props, player, enemies, and blocking objects.
            - Verify Godot import, scene load, collision, and smoke/package readiness after selection.
            """;
    }

    private static bool IsPreviewFile(string path)
    {
        var extension = Path.GetExtension(path);
        return extension.Equals(".png", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".jpg", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".jpeg", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".webp", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsReplacementResourceFile(string path)
    {
        var extension = Path.GetExtension(path);
        return IsPreviewFile(path) ||
               extension.Equals(".glb", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".gltf", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".obj", StringComparison.OrdinalIgnoreCase) ||
               extension.Equals(".fbx", StringComparison.OrdinalIgnoreCase);
    }

    private static string ExtensionFromContentType(string? mediaType)
    {
        return mediaType?.ToLowerInvariant() switch
        {
            "image/png" => ".png",
            "image/jpeg" => ".jpg",
            "image/webp" => ".webp",
            "model/gltf-binary" => ".glb",
            "model/gltf+json" => ".gltf",
            "application/zip" => ".zip",
            _ => ""
        };
    }

    private static string? WriteTemporaryReferenceImage(string outputAbsoluteDirectory, ProjectAssetGenerationRunRequest request)
    {
        if (!string.Equals(request.GenerationMode, "image-to-image", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var fileName = Trim(request.ReferenceImageFileName);
        var payload = Trim(request.ReferenceImageBase64);
        if (string.IsNullOrWhiteSpace(fileName) || string.IsNullOrWhiteSpace(payload))
        {
            throw new ArgumentException("Reference image is required for image-to-image generation.");
        }

        var extension = Path.GetExtension(fileName).ToLowerInvariant();
        if (extension is not ".png" and not ".jpg" and not ".jpeg" and not ".webp")
        {
            throw new ArgumentException("Reference image must be png, jpg, jpeg, or webp.");
        }

        var contentType = Trim(request.ReferenceImageContentType).ToLowerInvariant();
        if (!string.IsNullOrWhiteSpace(contentType) &&
            contentType is not "image/png" and not "image/jpeg" and not "image/webp")
        {
            throw new ArgumentException("Reference image content type must be image/png, image/jpeg, or image/webp.");
        }

        var commaIndex = payload.IndexOf(',', StringComparison.Ordinal);
        if (commaIndex >= 0)
        {
            payload = payload[(commaIndex + 1)..];
        }

        var bytes = Convert.FromBase64String(payload);
        if (bytes.Length > 10 * 1024 * 1024)
        {
            throw new ArgumentException("Reference image must be 10MB or smaller.");
        }

        var tempDirectory = Path.Combine(Path.GetTempPath(), "phasea-asset-reference", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempDirectory);
        var path = Path.Combine(tempDirectory, $"reference-input{extension}");
        File.WriteAllBytes(path, bytes);
        return path;
    }

    private async Task<string> ResolveActionIdAsync(
        ProjectSnapshot project,
        ProjectAssetLibraryUnit unit,
        string? floatingPrompt,
        CancellationToken cancellationToken)
    {
        if (_llmRouteEngine is null)
        {
            return ResolveActionIdHeuristic(unit, floatingPrompt);
        }

        var prompt = $$"""
            Decide the correct asset generation skill for one hosted Godot project asset unit.
            Return JSON only:
            {
              "actionId": "map-making-master|character-making-master",
              "reason": "short reason"
            }

            Choose map-making-master only for map, tilemap, terrain, level, room, field, overworld, background map, or spatial layout assets.
            Choose character-making-master for player, enemy, NPC, item, icon, projectile, effect, UI sprite, prop, or any sprite-like asset.
            Treat HudView, MapView, BattleView, RewardView, ActorView, LogView, InventoryView, and PrototypeRoot child visuals as lightweight Godot prototype component slots, not ECS.
            If IntendedUse names a component slot, preserve that slot in the reason and choose the skill that best fits the visual asset itself.

            Project:
            - GameName: {{project.GameName}}
            - GameType: {{project.GameTypeSource}}

            Asset unit:
            - InstanceName: {{unit.InstanceName}}
            - NodeType: {{unit.NodeType}}
            - ScenePath: {{unit.ScenePath}}
            - CurrentResource: {{unit.ResourcePath}}
            - SuggestedKind: {{unit.Kind}}
            - IntendedUse: {{unit.IntendedUse}}
            - Reason: {{unit.Reason}}

            User direction:
            {{Trim(floatingPrompt)}}
            """;
        try
        {
            var decision = await _llmRouteEngine.CompleteAsync(
                new LlmRouteRequest(
                    EnsureAssetLibraryDecisionWorkspace(project),
                    "project-asset-library-skill-selection",
                    "gpt-5.4",
                    prompt,
                    null,
                    project.AccountId,
                    RequireJsonObject: true),
                cancellationToken);
            if (!decision.Succeeded)
            {
                return ResolveActionIdHeuristic(unit, floatingPrompt);
            }

            using var document = JsonDocument.Parse(LlmRouteEngine.ExtractFirstJsonObject(decision.JsonObjectText ?? decision.AssistantMessage) ?? decision.AssistantMessage ?? "{}");
            var actionId = document.RootElement.TryGetProperty("actionId", out var actionElement) && actionElement.ValueKind == JsonValueKind.String
                ? actionElement.GetString()
                : null;
            return actionId is "map-making-master" or "character-making-master"
                ? actionId
                : ResolveActionIdHeuristic(unit, floatingPrompt);
        }
        catch (JsonException)
        {
            return ResolveActionIdHeuristic(unit, floatingPrompt);
        }
    }

    private static string ResolveActionIdHeuristic(ProjectAssetLibraryUnit unit, string? floatingPrompt)
    {
        var text = $"{unit.Kind} {unit.InstanceName} {unit.NodeType} {unit.IntendedUse} {unit.Reason} {floatingPrompt}".ToLowerInvariant();
        return text.Contains("map", StringComparison.Ordinal) ||
               text.Contains("tile", StringComparison.Ordinal) ||
               text.Contains("background", StringComparison.Ordinal) ||
               text.Contains("terrain", StringComparison.Ordinal)
            ? "map-making-master"
            : "character-making-master";
    }

    private static string EnsureAssetLibraryDecisionWorkspace(ProjectSnapshot project)
    {
        var repoParent = Path.GetDirectoryName(project.RepoPath);
        var workspaceRoot = string.IsNullOrWhiteSpace(repoParent) ? project.RepoPath : repoParent;
        var root = Path.Combine(workspaceRoot, "_phasea_llm", "asset-library");
        Directory.CreateDirectory(root);
        return root;
    }

    private static string BuildImagePrompt(ProjectSnapshot project, ProjectAssetLibraryUnit unit, string? floatingPrompt, string actionId)
    {
        var userInstruction = Trim(floatingPrompt);
        if (userInstruction.Length > MaxInstructionLength)
        {
            userInstruction = userInstruction[..MaxInstructionLength];
        }

        var assetMode = actionId == "map-making-master" ? "2D map/background asset" : "2D sprite/game asset";
        var currentResourceNote = string.IsNullOrWhiteSpace(unit.ResourcePath)
            ? "(none)"
            : unit.ResourcePath;
        var directionText = string.IsNullOrWhiteSpace(userInstruction)
            ? "(no explicit user style direction; infer only the minimum asset subject from the asset unit)"
            : userInstruction;
        return $"""
            Create one production-oriented {assetMode} for this hosted Godot project asset unit.

            Project:
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource} (classification only; do not treat this as a mandatory visual style when user direction says otherwise)

            Asset unit:
            - InstanceName: {unit.InstanceName}
            - NodeType: {unit.NodeType}
            - ScenePath: {unit.ScenePath}
            - CurrentResource: {currentResourceNote}
            - SuggestedKind: {unit.Kind}
            - IntendedUse: {unit.IntendedUse}
            - Reason: {unit.Reason}

            User generation direction:
            {directionText}

            Prompt isolation rules:
            - Treat User generation direction as the highest-priority style source.
            - Treat CurrentResource only as the asset slot being replaced. Do not copy its visual style, palette, composition, filename, or previous generated output unless the user explicitly asks to reference it.
            - Do not infer style from previous entries in Game.Godot/Prototypes/ProjectAssetLibrary.
            - Do not reuse earlier generation-prompt files, asset-manifest files, or previous fallback SVG/PNG decisions as style anchors.
            - IntendedUse and Reason describe gameplay placement only; do not let template wording such as JRPG, DQ, Dragon Quest, Final Fantasy, pixel art, or 16-bit override the current user direction.
            - If the user direction is empty, produce a neutral asset matching only the asset subject, gameplay role, and transparent-background requirement.

            Image requirements:
            - Generate exactly one clean game asset image.
            - No text, no watermark, no UI chrome, no border.
            - Use transparent background by default. Use an opaque or scene background only when the user generation direction explicitly asks for one.
            - Keep the subject centered with safe padding so it can be used as a Godot Texture2D.
            """;
    }

    private static string SanitizeFileStem(string value, string actionId)
    {
        var fallback = actionId == "map-making-master" ? "generated-map-asset" : "generated-sprite-asset";
        var source = string.IsNullOrWhiteSpace(value) ? fallback : value.Trim();
        var builder = new StringBuilder(source.Length);
        foreach (var ch in source)
        {
            if (char.IsAsciiLetterOrDigit(ch))
            {
                builder.Append(char.ToLowerInvariant(ch));
            }
            else if (ch is '-' or '_' || char.IsWhiteSpace(ch))
            {
                builder.Append('-');
            }
        }

        var stem = builder.ToString().Trim('-');
        while (stem.Contains("--", StringComparison.Ordinal))
        {
            stem = stem.Replace("--", "-", StringComparison.Ordinal);
        }

        return string.IsNullOrWhiteSpace(stem) ? fallback : stem[..Math.Min(stem.Length, 64)];
    }

    private static IEnumerable<string> EnumerateGeneratedFiles(string projectRoot, string outputAbsoluteDirectory)
    {
        if (!Directory.Exists(outputAbsoluteDirectory))
        {
            yield break;
        }

        foreach (var path in Directory.EnumerateFiles(outputAbsoluteDirectory, "*", SearchOption.AllDirectories))
        {
            var fullPath = Path.GetFullPath(path);
            if (WorkspacePathPolicy.IsUnderRoot(projectRoot, fullPath))
            {
                yield return fullPath;
            }
        }
    }

    private static bool IsPreviewResource(string resourcePath)
    {
        var extension = Path.GetExtension(resourcePath);
        return resourcePath.StartsWith("res://", StringComparison.Ordinal) &&
               (extension.Equals(".png", StringComparison.OrdinalIgnoreCase) ||
                extension.Equals(".jpg", StringComparison.OrdinalIgnoreCase) ||
                extension.Equals(".jpeg", StringComparison.OrdinalIgnoreCase) ||
                extension.Equals(".webp", StringComparison.OrdinalIgnoreCase));
    }

    private static string ToResPath(string projectRoot, string absolutePath)
    {
        return $"res://{ToSlash(Path.GetRelativePath(projectRoot, absolutePath))}";
    }

    private static string ToSlash(string path)
    {
        return path.Replace('\\', '/');
    }

    private static string ComputeUnitKey(string scenePath, string instanceName, string resourcePath, string kind)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes($"{scenePath}|{instanceName}|{resourcePath}|{kind}"));
        return Convert.ToHexString(bytes)[..24].ToLowerInvariant();
    }

    private static string Trim(string? value)
    {
        return value?.Trim() ?? "";
    }

    private static string Compact(string? value)
    {
        return string.IsNullOrWhiteSpace(value)
            ? ""
            : System.Text.RegularExpressions.Regex.Replace(value.Trim(), "\\s+", " ");
    }

    private static string FirstOrEmpty(IReadOnlyList<string> values)
    {
        return values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value)) ?? "";
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        return values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value))?.Trim() ?? "";
    }

    private sealed record ProjectAssetImportSource(Uri? Uri, string KeywordText);
}

public sealed record ProjectAssetLibraryResult(
    string ProjectId,
    IReadOnlyList<ProjectAssetLibraryUnit> Units);

public sealed record ProjectAssetLibraryUnit(
    string Key,
    string InstanceName,
    string NodeType,
    string ScenePath,
    string ResourcePath,
    string Kind,
    string IntendedUse,
    string Reason,
    string? SelectedEntryId,
    IReadOnlyList<ProjectAssetLibraryEntry> Entries);

public sealed record ProjectAssetLibraryEntry(
    string EntryId,
    string CreatedUtc,
    string RunId,
    string ActionId,
    string SkillName,
    string Prompt,
    string Status,
    string AssistantMessage,
    IReadOnlyList<string> ArtifactPaths,
    string? PreviewResourcePath,
    bool Selected,
    string? SourceKind = null,
    string? SourceUrl = null,
    string? SourceKeyword = null,
    bool SourceUrlAllowed = false,
    ProjectAssetReplacementValidation? SelectionValidation = null);

public sealed record ProjectAssetGenerationRunRequest(
    string? FloatingPrompt,
    ProjectAssetUnitRequest? Unit,
    string? GenerationMode = null,
    int? Count = null,
    string? ReferenceImageFileName = null,
    string? ReferenceImageBase64 = null,
    string? ReferenceImageContentType = null);

public sealed record ProjectAssetUnitRequest(
    string? UnitKey,
    string? InstanceName,
    string? NodeType,
    string? ScenePath,
    string? ResourcePath,
    string? Kind,
    string? IntendedUse,
    string? Reason);

public sealed record ProjectAssetGenerationRunResult(
    string Status,
    string ActionId,
    ProjectAssetLibraryEntry Entry,
    ProjectAssetLibraryResult Library);

public sealed record ProjectAssetSelectionRequest(
    string UnitKey,
    string EntryId,
    bool? ValidateWithSmoke = null);

public sealed record ProjectAssetImportRequest(
    string? QueryOrUrl,
    ProjectAssetUnitRequest? Unit);

public sealed record ProjectAssetImportResult(
    string Status,
    bool SourceUrlAllowed,
    ProjectAssetLibraryEntry Entry,
    ProjectAssetLibraryResult Library);

public sealed record ProjectAssetReplacementValidation(
    string Status,
    bool ReplacementResourceExists,
    bool ScenePatchable,
    bool CollisionPreserved,
    bool SmokeRequired,
    string Summary,
    IReadOnlyList<ProjectAssetReplacementValidationCheck> Checks,
    ProjectAssetScenePatchResult? ScenePatch = null,
    ProjectAssetSelectionSmokeResult? SelectionSmoke = null);

public sealed record ProjectAssetReplacementValidationCheck(
    string Name,
    string Status,
    string Details);

public sealed record ProjectAssetScenePatchResult(
    bool Applied,
    string Reason,
    string? ScenePath,
    string? AbsoluteScenePath = null,
    string? OriginalSceneText = null)
{
    public static ProjectAssetScenePatchResult NoChange(string reason, string? scenePath, bool applied = false)
        => new(applied, reason, scenePath);

    public static ProjectAssetScenePatchResult Changed(string reason, string scenePath, string absoluteScenePath, string originalSceneText)
        => new(true, reason, scenePath, absoluteScenePath, originalSceneText);

    public void Rollback()
    {
        if (!string.IsNullOrWhiteSpace(AbsoluteScenePath) && OriginalSceneText is not null)
        {
            File.WriteAllText(AbsoluteScenePath, OriginalSceneText, Encoding.UTF8);
        }
    }
}

public sealed record ProjectAssetSelectionSmokeResult(
    bool Ran,
    int ExitCode,
    string Reason,
    string? ScenePath,
    string Stdout,
    string Stderr)
{
    public static ProjectAssetSelectionSmokeResult Skipped(string reason, string? scenePath)
    {
        return new ProjectAssetSelectionSmokeResult(false, 0, reason, scenePath, "", "");
    }
}
