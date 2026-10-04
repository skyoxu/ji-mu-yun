using System.IO.Compression;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Security;

namespace PhaseA.Platform.Readback;

public sealed class ProjectPackageService
{
    private const string RunType = "project-package";
    private const string PackageArtifactType = "project-package-zip";
    private const string PackageRootDirectory = "exports";
    private const string PlayablePreviewContractFileName = "playable-preview-contract.json";
    private const string PlayablePreviewContractSchemaVersion = "phasea-playable-preview-contract-v1";

    private static readonly string[] IncludedRoots =
    [
        "Game.Core",
        "Game.Core.Tests",
        "Game.Godot",
        "Game.Godot.Tests",
        "Tests.Godot",
        "docs/prototypes",
        "docs/gdd",
        "docs/prd",
        "docs/contracts"
    ];

    private static readonly string[] IncludedRootFiles =
    [
        ".editorconfig",
        ".gitattributes",
        ".gitignore",
        "Directory.Build.props",
        "Directory.Build.targets",
        "export_presets.cfg",
        "GodotGame.csproj",
        "GodotGame.sln",
        "icon.svg",
        "icon.svg.import",
        "packages.lock.json",
        "project.godot",
        "README.md"
    ];

    private static readonly string[] ExcludedDirectoryNames =
    [
        ".git",
        ".godot",
        ".vs",
        ".vscode",
        "bin",
        "obj",
        "logs",
        "reports",
        "TestResults",
        PackageRootDirectory
    ];

    private static readonly string[] ExcludedFileSuffixes =
    [
        ".user",
        ".suo",
        ".tmp",
        ".log",
        ".sqlite3",
        ".sqlite3-shm",
        ".sqlite3-wal"
    ];

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly HeavyRunnerQueueService _heavyRunnerQueue;
    private readonly RunCancellationService _runCancellation;
    private readonly IHostedProcessRunner _processRunner;
    private readonly ProjectWebPreviewService? _webPreviews;
    private readonly WorkspaceStorageService _storage;
    private readonly ExtensionPolicyState _snapshotPolicy;

    public ProjectPackageService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        HeavyRunnerQueueService? heavyRunnerQueue = null,
        RunCancellationService? runCancellation = null,
        IHostedProcessRunner? processRunner = null,
        ProjectWebPreviewService? webPreviews = null,
        WorkspaceStorageService? storage = null,
        ExtensionPolicyState? snapshotPolicy = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _heavyRunnerQueue = heavyRunnerQueue ?? new HeavyRunnerQueueService();
        _runCancellation = runCancellation ?? new RunCancellationService();
        _processRunner = processRunner ?? new HostedProcessRunner();
        _webPreviews = webPreviews;
        _storage = storage ?? new WorkspaceStorageService();
        _snapshotPolicy = snapshotPolicy ?? new ExtensionPolicyState();
    }

    public async Task<ProjectPackageResult> CreatePackageAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default,
        RequestContext? requestContext = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return Failure(projectId, "project_not_found");
        }

        if (project.BootstrapStatus == "running" ||
            await _metadataStore.HasRunnerLockAsync(projectId, cancellationToken) ||
            await _metadataStore.HasActiveRunAsync(project.ProjectId, cancellationToken))
        {
            return Failure(projectId, "project_busy");
        }

        var gate = await ResolvePackageGateAsync(project, cancellationToken);
        if (!gate.CanCreate)
        {
            return Failure(projectId, gate.DisabledReason ?? "package_prerequisites_not_met");
        }

        var projectRoot = Path.GetFullPath(project.RepoPath);
        RunnerIsolationPolicy.RequireNoReparsePoint(_options.HostedWorkspaceRoot, projectRoot);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return Failure(projectId, "project_busy", runId);
        }

        WorkspaceSnapshotRecord? capturedSnapshot = null;
        RequestContext? captureContext = null;
        var packagePublished = false;
        try
        {
            await using var heavyRunnerLease = await _heavyRunnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, RunType, CancellationToken.None);
            await _metadataStore.MarkRunStartedAsync(runId, heavyRunnerLease.QueuePositionAtStart, cancellationToken);
            using var runCancellation = _runCancellation.CreateLinkedTokenSource(runId, cancellationToken);
            var runToken = runCancellation.Token;
            if (requestContext is not null &&
                (await _metadataStore.ResolveAccountByTokenHashAsync(requestContext.CredentialId, runToken))?.AccountId != accountId)
                throw new UnauthorizedAccessException("Package credential is no longer authorized.");
            var packageOrdinal = await NextPackageOrdinalAsync(project.ProjectId, runToken);
            var version = CreateVersion(packageOrdinal);
            var safeName = SafeFileName(project.Name);
            var fileName = $"{safeName}-{version}.zip";
            var relativePath = $"{PackageRootDirectory}/{fileName}";
            var packagePath = ResolveUnderProject(GetPackageRepositoryRoot(project), relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(packagePath)!);
            if (File.Exists(packagePath))
            {
                File.Delete(packagePath);
            }

            var assetSelectionResult = ApplySelectedAssetLibraryEntries(projectRoot, runToken);
            var assetSmoke = await RunAssetReplacementSmokeAsync(projectRoot, assetSelectionResult.ScenePaths, runToken);
            if (assetSmoke.Ran && assetSmoke.ExitCode != 0)
            {
                var failureEvidenceJson = JsonSerializer.Serialize(new
                {
                    run_type = RunType,
                    asset_replacement = new
                    {
                        applied_asset_selection_count = assetSelectionResult.AppliedCount,
                        scene_paths = assetSelectionResult.ScenePaths,
                        smoke = assetSmoke
                    }
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", assetSmoke.ExitCode, assetSmoke.Stdout, assetSmoke.Stderr, failureEvidenceJson, runToken);
                return new ProjectPackageResult(projectId, runId, "failed", "", "", "", "", 0, 0, [], "asset_replacement_smoke_failed");
            }
            // ADR-0061: ZIP bytes come from this immutable capture, not a second
            // read of files that another request could change after the snapshot.
            var policy = _snapshotPolicy.ReadSnapshotPolicy();
            var context = requestContext ?? new RequestContext("package-service", accountId,
                new HashSet<string> { PhaseAAuth.UserRole }, $"package:{runId}", runId);
            context.DemandAccount(accountId);
            var snapshot = _storage.CreateSnapshot(context, Path.GetDirectoryName(projectRoot)!,
                $"package-{runId}", project.WorkspaceId, project.ProjectId, policy.Version, policy.Blacklist);
            capturedSnapshot = snapshot;
            captureContext = context;
            var staging = Path.Combine(project.RuntimePath, "tmp", $"package-{runId}");
            int includedFileCount;
            try
            {
                foreach (var (path, content) in snapshot.Manifest.ReadProtectedContent())
                {
                    runToken.ThrowIfCancellationRequested();
                    if (!path.StartsWith("repo/", StringComparison.Ordinal)) continue;
                    var target = RunnerIsolationPolicy.RequireContainedPath(staging, path[5..]);
                    Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                    File.WriteAllBytes(target, content);
                }
                includedFileCount = CreateZip(staging, packagePath, project, version, runToken);
            }
            finally
            {
                if (Directory.Exists(staging)) Directory.Delete(staging, true);
            }
            var sizeBytes = new FileInfo(packagePath).Length;
            var packageSha256 = ComputeFileSha256(packagePath);
            var generatedUtc = DateTimeOffset.UtcNow.ToString("O");
            await _metadataStore.AddArtifactAsync(
                new ArtifactCreationCommand(
                    runId,
                    project.ProjectId,
                    PackageArtifactType,
                    relativePath,
                    "Downloadable project-only package"),
                runToken);

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                version,
                generated_utc = generatedUtc,
                file_name = fileName,
                relative_path = relativePath,
                package_sha256 = packageSha256,
                snapshot_id = snapshot.Manifest.SnapshotId,
                size_bytes = sizeBytes,
                included_file_count = includedFileCount,
                applied_asset_selection_count = assetSelectionResult.AppliedCount,
                asset_replacement_smoke = assetSmoke,
                included_roots = IncludedRoots,
                included_root_files = IncludedRootFiles
            });
            runToken.ThrowIfCancellationRequested();
            await _metadataStore.CompleteRunAsync(runId, "succeeded", 0, $"Created {fileName}", "", evidenceJson, CancellationToken.None);
            packagePublished = (await _metadataStore.GetRunSnapshotAsync(runId, CancellationToken.None))?.Status == "succeeded";
            if (!packagePublished)
                return new ProjectPackageResult(projectId, runId, "cancel", "", "", "", "", 0, 0, [], "cancel");
            var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, CancellationToken.None);

            return new ProjectPackageResult(
                project.ProjectId,
                runId,
                "succeeded",
                version,
                fileName,
                relativePath,
                $"/projects/{project.ProjectId}/packages/{Uri.EscapeDataString(fileName)}",
                sizeBytes,
                includedFileCount,
                artifacts,
                SnapshotId: snapshot.Manifest.SnapshotId);
        }
        catch (OperationCanceledException)
        {
            await _metadataStore.CompleteRunAsync(runId, "cancel", 499, "", "Packaging was cancelled.", "{}", CancellationToken.None);
            return new ProjectPackageResult(projectId, runId, "cancel", "", "", "", "", 0, 0, [], "cancel");
        }
        catch (Exception ex)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), "{}", CancellationToken.None);
            return new ProjectPackageResult(projectId, runId, "failed", "", "", "", "", 0, 0, [], "package_failed");
        }
        finally
        {
            if (!packagePublished && capturedSnapshot is not null && captureContext is not null)
                _storage.SoftDeleteSnapshot(captureContext, capturedSnapshot.Manifest.SnapshotId);
            _runCancellation.Unregister(runId);
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    public async Task<ProjectPackageListResult?> ListPackagesAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        var projectRoot = GetPackageRepositoryRoot(project);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        var gate = await ResolvePackageGateAsync(project, cancellationToken);
        var isBusy = project.BootstrapStatus == "running" ||
                      await _metadataStore.HasRunnerLockAsync(projectId, cancellationToken) ||
                      await _metadataStore.HasActiveRunAsync(project.ProjectId, cancellationToken);
        var disabledReason = isBusy ? "project_busy" : gate.DisabledReason;

        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        var packageRuns = runs
            .Where(run => run.RunType == RunType && run.Status == "succeeded")
            .ToArray();
        var packageArtifacts = await _metadataStore.ListArtifactsForRunsAsync(
            packageRuns.Select(run => run.RunId).ToArray(),
            cancellationToken);
        var artifactsByRunId = packageArtifacts
            .Where(artifact => !string.IsNullOrWhiteSpace(artifact.RunId))
            .GroupBy(artifact => artifact.RunId!, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.ToArray(), StringComparer.Ordinal);
        var packageRecords = new List<ProjectPackageRecord>();
        foreach (var run in packageRuns)
        {
            if (!artifactsByRunId.TryGetValue(run.RunId, out var artifacts))
            {
                continue;
            }

            foreach (var artifact in artifacts.Where(artifact => artifact.ArtifactType == PackageArtifactType))
            {
                var fileName = Path.GetFileName(artifact.RelativePath);
                var packagePath = ResolveUnderProject(projectRoot, artifact.RelativePath);
                if (!File.Exists(packagePath))
                {
                    continue;
                }

                packageRecords.Add(new ProjectPackageRecord(
                    ExtractVersion(fileName),
                    fileName,
                    artifact.RelativePath,
                    new FileInfo(packagePath).Length,
                    ReadPackageSha256(run.EvidenceJson) ?? ComputeFileSha256(packagePath),
                    ReadGeneratedUtc(run.EvidenceJson),
                    ReadSnapshotId(run.EvidenceJson)));
            }
        }

        var webPreviewStatuses = _webPreviews?.ResolvePreviewsForPackages(
            project,
            packageRecords.Select(package => package.FileName),
            runs);
        var snapshotIds = _storage.ListSnapshots(accountId, projectId)
            .Select(snapshot => snapshot.Manifest.SnapshotId).ToHashSet(StringComparer.Ordinal);
        var registered = RunnerIsolationPolicy.TryGetWorkspaceDescriptor(project.WorkspaceRootPath, out var descriptor)
            && descriptor.AccountId == accountId && descriptor.ProjectId == projectId;
        var packages = packageRecords.Select(package =>
        {
            var webPreviewStatus = webPreviewStatuses is not null &&
                                   webPreviewStatuses.TryGetValue(package.FileName, out var status)
                ? status
                : new ProjectWebPreviewPackageStatus("not_generated", null, null, null, null);
            return new ProjectPackageListItem(
                package.Version,
                package.FileName,
                package.RelativePath,
                $"/projects/{project.ProjectId}/packages/{Uri.EscapeDataString(package.FileName)}",
                package.SizeBytes,
                package.PackageSha256,
                package.CreatedUtc,
                webPreviewStatus,
                package.SnapshotId,
                !isBusy && registered && package.SnapshotId is not null && snapshotIds.Contains(package.SnapshotId),
                isBusy ? "project_busy" : !registered ? "workspace_isolation_unavailable" :
                    package.SnapshotId is null || !snapshotIds.Contains(package.SnapshotId) ? "package_snapshot_unavailable" : null);
        });

        return new ProjectPackageListResult(
            project.ProjectId,
            gate.CanCreate && !isBusy,
            disabledReason,
            packages
                .OrderByDescending(package => package.CreatedUtc, StringComparer.Ordinal)
                .ThenByDescending(package => package.Version, StringComparer.Ordinal)
                .ToArray());
    }

    public async Task<ProjectPackageReadResult?> ReadPackageAsync(
        string accountId,
        string projectId,
        string fileName,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(fileName);

        if (!string.Equals(fileName, Path.GetFileName(fileName), StringComparison.Ordinal))
        {
            return null;
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        var packagePath = ResolveUnderProject(GetPackageRepositoryRoot(project), $"{PackageRootDirectory}/{fileName}");
        if (!File.Exists(packagePath))
        {
            return null;
        }

        return new ProjectPackageReadResult(
            fileName,
            "application/zip",
            await File.ReadAllBytesAsync(packagePath, cancellationToken));
    }

    private async Task<int> NextPackageOrdinalAsync(string projectId, CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(projectId, cancellationToken);
        return runs.Count(run => run.RunType == RunType && run.Status == "succeeded") + 1;
    }

    private async Task<PackageGate> ResolvePackageGateAsync(ProjectSnapshot project, CancellationToken cancellationToken)
    {
        var m1Gate = await TryResolveM1PackageGateAsync(project, cancellationToken);
        if (m1Gate is not null)
        {
            return m1Gate;
        }

        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        if (!runs.Any(run => run.RunType == "prototype-7day-playable" && IsDone(run.Status)))
        {
            return new PackageGate(false, "prototype_not_created");
        }

        return new PackageGate(true, null);
    }

    private static async Task<PackageGate?> TryResolveM1PackageGateAsync(ProjectSnapshot project, CancellationToken cancellationToken)
    {
        var statePath = ResolveGddMilestoneStatePath(project);
        if (statePath is null)
        {
            return null;
        }

        try
        {
            await using var stream = File.OpenRead(statePath);
            using var document = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
            if (!document.RootElement.TryGetProperty("steps", out var steps) ||
                steps.ValueKind != JsonValueKind.Array)
            {
                return new PackageGate(false, "m1_not_completed");
            }

            JsonElement? firstStep = null;
            foreach (var step in steps.EnumerateArray())
            {
                if (step.ValueKind != JsonValueKind.Object)
                {
                    continue;
                }

                firstStep ??= step;
                if (step.TryGetProperty("stepId", out var id) &&
                    string.Equals(id.GetString(), "M1", StringComparison.OrdinalIgnoreCase))
                {
                    return IsM1PackageReady(step)
                        ? new PackageGate(true, null)
                        : new PackageGate(false, "m1_not_completed");
                }
            }

            return firstStep is { } fallback && IsM1PackageReady(fallback)
                ? new PackageGate(true, null)
                : new PackageGate(false, "m1_not_completed");
        }
        catch (JsonException)
        {
            return new PackageGate(false, "m1_not_completed");
        }
        catch (IOException)
        {
            return new PackageGate(false, "m1_not_completed");
        }
    }

    private static string? ResolveGddMilestoneStatePath(ProjectSnapshot project)
    {
        var metaPath = Path.Combine(project.MetaPath, "routes", "gdd-milestones", "latest.json");
        if (File.Exists(metaPath))
        {
            return metaPath;
        }

        var repoMirrorPath = Path.Combine(project.RepoPath, "meta", "routes", "gdd-milestones", "latest.json");
        return File.Exists(repoMirrorPath) ? repoMirrorPath : null;
    }

    private static bool IsM1PackageReady(JsonElement step)
    {
        if (step.TryGetProperty("confirmedUtc", out var confirmedUtc) &&
            !string.IsNullOrWhiteSpace(confirmedUtc.GetString()))
        {
            return true;
        }

        var status = step.TryGetProperty("status", out var statusElement)
            ? statusElement.GetString()
            : null;
        return status is not null && IsM1PackageReadyStatus(status);
    }

    private static bool IsM1PackageReadyStatus(string status)
    {
        return status.Trim().ToLowerInvariant() is "confirmed" or "executed" or "feedback_submitted" or "succeeded" or "completed";
    }

    private static bool IsDone(string? status)
    {
        return string.Equals(status, "succeeded", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "completed", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "done", StringComparison.OrdinalIgnoreCase);
    }

    private sealed record PackageGate(bool CanCreate, string? DisabledReason);

    private static int CreateZip(string projectRoot, string packagePath, ProjectSnapshot project, string version, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        using var stream = File.Create(packagePath);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Create);
        var included = 0;
        AddManifest(archive, project, version);
        AddPlayablePreviewContract(archive, projectRoot, project, version);

        foreach (var root in IncludedRoots)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var absoluteRoot = Path.Combine(projectRoot, root.Replace('/', Path.DirectorySeparatorChar));
            if (!Directory.Exists(absoluteRoot))
            {
                continue;
            }

            foreach (var file in Directory.EnumerateFiles(absoluteRoot, "*", SearchOption.AllDirectories))
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (!ShouldIncludeFile(projectRoot, file))
                {
                    continue;
                }

                AddFile(archive, projectRoot, file);
                included++;
            }
        }

        foreach (var rootFile in IncludedRootFiles)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var absoluteFile = Path.Combine(projectRoot, rootFile);
            if (!File.Exists(absoluteFile) || !ShouldIncludeFile(projectRoot, absoluteFile))
            {
                continue;
            }

            AddFile(archive, projectRoot, absoluteFile);
            included++;
        }

        return included;
    }

    private static AssetSelectionApplyResult ApplySelectedAssetLibraryEntries(string projectRoot, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var libraryPath = ResolveUnderProject(projectRoot, "meta/assets/library.json");
        if (!File.Exists(libraryPath))
        {
            return new AssetSelectionApplyResult(0, []);
        }

        ProjectAssetLibraryResult? library;
        try
        {
            library = JsonSerializer.Deserialize<ProjectAssetLibraryResult>(
                File.ReadAllText(libraryPath, Encoding.UTF8),
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        }
        catch (JsonException)
        {
            return new AssetSelectionApplyResult(0, []);
        }

        if (library is null)
        {
            return new AssetSelectionApplyResult(0, []);
        }

        var applied = 0;
        var scenePaths = new HashSet<string>(StringComparer.Ordinal);
        foreach (var unit in library.Units)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (!IsResPath(unit.ScenePath) || !unit.ScenePath.EndsWith(".tscn", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var selected = unit.Entries.FirstOrDefault(entry =>
                entry.Selected ||
                string.Equals(entry.EntryId, unit.SelectedEntryId, StringComparison.Ordinal));
            if (!IsResPath(selected?.PreviewResourcePath) ||
                string.Equals(unit.ResourcePath, selected!.PreviewResourcePath, StringComparison.Ordinal))
            {
                continue;
            }
            var selectedPreviewResourcePath = selected.PreviewResourcePath!;

            var scenePath = ResolveResPath(projectRoot, unit.ScenePath);
            if (!File.Exists(scenePath))
            {
                continue;
            }

            var sceneText = File.ReadAllText(scenePath, Encoding.UTF8);
            var alreadyUsesSelectedResource = sceneText.Contains($"path=\"{selectedPreviewResourcePath}\"", StringComparison.Ordinal);
            if (IsResPath(unit.ResourcePath))
            {
                var oldToken = $"path=\"{unit.ResourcePath}\"";
                var newToken = $"path=\"{selectedPreviewResourcePath}\"";
                if (alreadyUsesSelectedResource)
                {
                    applied++;
                    scenePaths.Add(unit.ScenePath);
                    continue;
                }

                if (!sceneText.Contains(oldToken, StringComparison.Ordinal))
                {
                    continue;
                }

                File.WriteAllText(scenePath, sceneText.Replace(oldToken, newToken, StringComparison.Ordinal), Encoding.UTF8);
                applied++;
                scenePaths.Add(unit.ScenePath);
                continue;
            }

            if (!IsDirectTextureNodeType(unit.NodeType))
            {
                continue;
            }

            var updatedSceneText = AddTextureReferenceToExistingNode(sceneText, unit, selectedPreviewResourcePath);
            if (updatedSceneText is null)
            {
                continue;
            }

            File.WriteAllText(scenePath, updatedSceneText, Encoding.UTF8);
            applied++;
            scenePaths.Add(unit.ScenePath);
        }

        return new AssetSelectionApplyResult(applied, scenePaths.OrderBy(path => path, StringComparer.Ordinal).ToArray());
    }

    private async Task<AssetReplacementSmokeResult> RunAssetReplacementSmokeAsync(
        string projectRoot,
        IReadOnlyList<string> scenePaths,
        CancellationToken cancellationToken)
    {
        if (scenePaths.Count == 0)
        {
            return AssetReplacementSmokeResult.NotRequired("no_asset_replacements_applied");
        }

        if (string.IsNullOrWhiteSpace(_options.GodotBin))
        {
            return AssetReplacementSmokeResult.Skipped("godot_bin_not_configured", scenePaths);
        }

        foreach (var scenePath in scenePaths)
        {
            var command = new HostedProcessCommand(
                _options.PythonCommand,
                [
                    "-3",
                    ResolveRepositoryScriptPath("scripts/python/smoke_headless.py"),
                    "--godot-bin",
                    _options.GodotBin,
                    "--project-path",
                    projectRoot,
                    "--scene",
                    scenePath,
                    "--timeout-sec",
                    "10",
                    "--strict"
                ],
                projectRoot,
                PrototypeValidationProcessEnvironment.Create(projectRoot, new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                {
                    ["GODOT_BIN"] = _options.GodotBin
                }));
            var result = await _processRunner.RunAsync(command, cancellationToken);
            var exitCode = ResolveSmokeExitCode(result);
            if (exitCode != 0)
            {
                return new AssetReplacementSmokeResult(true, exitCode, "asset_replacement_scene_smoke_failed", scenePath, scenePaths, result.Stdout, result.Stderr);
            }
        }

        return new AssetReplacementSmokeResult(true, 0, "asset_replacement_scene_smoke_passed", scenePaths[^1], scenePaths, "", "");
    }

    private async Task<bool> IsRunCancelledAsync(string runId, CancellationToken cancellationToken)
    {
        var run = await _metadataStore.GetRunSnapshotAsync(runId, cancellationToken);
        return string.Equals(run?.Status, "cancel", StringComparison.Ordinal);
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

    private static string ComputeFileSha256(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
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

    private static void AddManifest(ZipArchive archive, ProjectSnapshot project, string version)
    {
        var entry = archive.CreateEntry("PACKAGE-MANIFEST.json", CompressionLevel.Optimal);
        var gameTypeId = ProjectWebPreviewGameTypeCatalog.ResolveProjectGameTypeId(project);
        var gameTypeGuide = ProjectWebPreviewGameTypeCatalog.ResolveGameTypeGuide(gameTypeId);
        using var writer = new StreamWriter(entry.Open());
        writer.Write(JsonSerializer.Serialize(new
        {
            package_version = version,
            generated_utc = DateTimeOffset.UtcNow.ToString("O"),
            project_id = project.ProjectId,
            project_name = project.Name,
            game_name = project.GameName,
            game_type_source = project.GameTypeSource,
            game_type_id = gameTypeId,
            game_type_guide = gameTypeGuide,
            policy = "project-files-only"
        }, new JsonSerializerOptions { WriteIndented = true }));
    }

    private static void AddPlayablePreviewContract(ZipArchive archive, string projectRoot, ProjectSnapshot project, string version)
    {
        var entry = archive.CreateEntry(PlayablePreviewContractFileName, CompressionLevel.Optimal);
        var gameTypeId = ProjectWebPreviewGameTypeCatalog.ResolveProjectGameTypeId(project);
        var gameTypeGuide = ProjectWebPreviewGameTypeCatalog.ResolveGameTypeGuide(gameTypeId);
        var mainScene = TryReadMainScene(projectRoot);
        var scenes = DiscoverSceneResourcePaths(projectRoot, mainScene, project);
        var sceneEntities = scenes
            .Take(12)
            .Select((scene, index) => new
            {
                id = $"scene_{index + 1}",
                label = SceneLabel(scene, index),
                role = index == 0 ? "entry_scene" : "scene_marker",
                scene,
                objective = index == 0 ? "Enter the playable route." : "Inspect this package scene."
            })
            .ToArray();
        var nodeEntities = DiscoverContractNodeEntities(projectRoot, scenes.Take(6).ToArray())
            .OrderBy(NodeEntityPriority)
            .ThenBy(entity => entity.Scene, StringComparer.OrdinalIgnoreCase)
            .ThenBy(entity => entity.Label, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var entities = nodeEntities
            .Cast<object>()
            .Concat(sceneEntities)
            .Take(40)
            .ToArray();
        var mechanicHints = nodeEntities
            .Select(entity => entity.Role)
            .Distinct(StringComparer.Ordinal)
            .OrderBy(role => role, StringComparer.Ordinal)
            .ToArray();

        using var writer = new StreamWriter(entry.Open(), new UTF8Encoding(false));
        writer.Write(JsonSerializer.Serialize(new
        {
            schema_version = PlayablePreviewContractSchemaVersion,
            source = "project-package-service",
            package_version = version,
            generated_utc = DateTimeOffset.UtcNow.ToString("O"),
            project_id = project.ProjectId,
            project_name = project.Name,
            game_name = project.GameName,
            game_type_source = project.GameTypeSource,
            game_type_id = gameTypeId,
            game_type_guide = gameTypeGuide,
            main_scene = mainScene,
            objectives = new[]
            {
                new
                {
                    id = "first_playable_loop",
                    label = "Move, inspect scene nodes, and complete the first browser preview loop.",
                    success = "The player can move, select a scene node, interact, and see progress feedback."
                }
            },
            entities,
            mechanic_hints = mechanicHints,
            state_model = BuildPreviewStateModel(),
            role_interactions = BuildRoleInteractions(mechanicHints),
            win_conditions = new[]
            {
                new
                {
                    id = "priority_roles_complete",
                    label = "Complete interactions with the player, pressure, action, reward, and UI roles that exist in the contract."
                }
            },
            loss_conditions = new[]
            {
                new
                {
                    id = "pressure_overflow_retryable",
                    label = "Pressure can reduce preview HP, but the browser preview remains retryable."
                }
            },
            input_actions = new[]
            {
                new { action = "move", inputs = new[] { "W", "A", "S", "D", "MouseLeft" }, behavior = "Move the preview avatar through the package-derived play space." },
                new { action = "interact", inputs = new[] { "Space", "Enter", "MouseLeft" }, behavior = "Inspect or activate the nearest contract entity." },
                new { action = "select_scene", inputs = new[] { "1", "2", "3" }, behavior = "Jump to a contract scene node." }
            }
        }, new JsonSerializerOptions { WriteIndented = true }));
    }

    private static string TryReadMainScene(string projectRoot)
    {
        var projectGodot = Path.Combine(projectRoot, "project.godot");
        if (!File.Exists(projectGodot))
        {
            return "";
        }

        foreach (var line in File.ReadLines(projectGodot, Encoding.UTF8))
        {
            if (line.StartsWith("run/main_scene=", StringComparison.Ordinal))
            {
                return line.Split('=', 2)[1].Trim().Trim('"');
            }
        }

        return "";
    }

    private static IReadOnlyList<string> DiscoverSceneResourcePaths(string projectRoot, string mainScene, ProjectSnapshot project)
    {
        var godotRoot = Path.Combine(projectRoot, "Game.Godot");
        if (!Directory.Exists(godotRoot))
        {
            return [];
        }

        var projectTokens = new[]
            {
                project.Name,
                project.GameName
            }
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(NormalizeToken)
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Distinct(StringComparer.Ordinal)
            .ToArray();

        return Directory
            .EnumerateFiles(godotRoot, "*.tscn", SearchOption.AllDirectories)
            .Select(path => $"res://{Path.GetRelativePath(projectRoot, path).Replace('\\', '/')}")
            .OrderBy(path => ScenePriority(path, mainScene, projectTokens))
            .ThenBy(path => path, StringComparer.OrdinalIgnoreCase)
            .Take(80)
            .ToArray();
    }

    private static int ScenePriority(string scenePath, string mainScene, IReadOnlyList<string> projectTokens)
    {
        if (!string.IsNullOrWhiteSpace(mainScene) && string.Equals(scenePath, mainScene, StringComparison.OrdinalIgnoreCase))
        {
            return 0;
        }

        var normalized = NormalizeToken(scenePath);
        if (projectTokens.Any(token => normalized.Contains(token, StringComparison.Ordinal)))
        {
            return 1;
        }

        if (scenePath.Contains("/Prototypes/", StringComparison.OrdinalIgnoreCase))
        {
            return 2;
        }

        if (scenePath.Contains("/Examples/", StringComparison.OrdinalIgnoreCase) ||
            scenePath.Contains("/Tests.", StringComparison.OrdinalIgnoreCase) ||
            scenePath.Contains("DefaultRpgTemplate", StringComparison.OrdinalIgnoreCase))
        {
            return 9;
        }

        return 4;
    }

    private static IReadOnlyList<PreviewContractNodeEntity> DiscoverContractNodeEntities(
        string projectRoot,
        IReadOnlyList<string> sceneResourcePaths)
    {
        var entities = new List<PreviewContractNodeEntity>();
        var seenRoles = new HashSet<string>(StringComparer.Ordinal);
        var sequence = 1;
        foreach (var sceneResourcePath in sceneResourcePaths)
        {
            var sceneFile = ResolveOptionalResPath(projectRoot, sceneResourcePath);
            if (sceneFile is null || !File.Exists(sceneFile))
            {
                continue;
            }

            foreach (var entity in ParseSceneNodeEntities(sceneResourcePath, sceneFile))
            {
                var roleKey = $"{entity.Role}:{entity.Label}";
                if (!seenRoles.Add(roleKey))
                {
                    continue;
                }

                entities.Add(entity with { Id = $"entity_{sequence++}" });
                if (entities.Count >= 28)
                {
                    return entities;
                }
            }
        }

        return entities;
    }

    private static IEnumerable<PreviewContractNodeEntity> ParseSceneNodeEntities(string sceneResourcePath, string sceneFile)
    {
        var nodes = ParseSceneNodes(sceneFile);
        foreach (var node in nodes.Values)
        {
            var role = ClassifyContractNodeRole(node.Name, node.Type, node.Parent);
            if (role is null)
            {
                continue;
            }

            yield return new PreviewContractNodeEntity(
                "",
                node.Name,
                role,
                sceneResourcePath,
                NodeObjective(role, node.Name),
                node.Type,
                node.Path,
                node.LocalPosition,
                ResolveWorldPosition(node, nodes),
                node.TargetPosition,
                node.TargetPosition is null ? null : Math.Round(VectorLength(node.TargetPosition), 2));
        }
    }

    private static IReadOnlyDictionary<string, PreviewSceneNode> ParseSceneNodes(string sceneFile)
    {
        var nodes = new Dictionary<string, PreviewSceneNode>(StringComparer.Ordinal);
        PreviewSceneNode? current = null;
        foreach (var line in File.ReadLines(sceneFile, Encoding.UTF8))
        {
            var nodeMatch = Regex.Match(line, "^\\[node\\s+.*name=\"(?<name>[^\"]+)\"\\s+type=\"(?<type>[^\"]+)\"(?:\\s+parent=\"(?<parent>[^\"]+)\")?.*\\]$");
            if (nodeMatch.Success)
            {
                var name = nodeMatch.Groups["name"].Value;
                var type = nodeMatch.Groups["type"].Value;
                var parent = nodeMatch.Groups["parent"].Value;
                var path = string.IsNullOrWhiteSpace(parent) ? name : $"{parent}/{name}";
                current = new PreviewSceneNode(name, type, parent, path);
                nodes[path] = current;
                continue;
            }

            if (current is null)
            {
                continue;
            }

            if (line.StartsWith("transform = ", StringComparison.Ordinal))
            {
                current.LocalPosition = ParseTransformPosition(line);
            }
            else if (line.StartsWith("position = ", StringComparison.Ordinal) ||
                line.StartsWith("translation = ", StringComparison.Ordinal))
            {
                current.LocalPosition = ParseVectorPosition(line);
            }
            else if (line.StartsWith("target_position = ", StringComparison.Ordinal))
            {
                current.TargetPosition = ParseVectorPosition(line);
            }
        }

        return nodes;
    }

    private static PreviewVector3? ResolveWorldPosition(
        PreviewSceneNode node,
        IReadOnlyDictionary<string, PreviewSceneNode> nodes)
    {
        if (node.WorldPosition is not null)
        {
            return node.WorldPosition;
        }

        var local = node.LocalPosition ?? new PreviewVector3(0, 0, 0);
        if (!string.IsNullOrWhiteSpace(node.Parent) &&
            nodes.TryGetValue(node.Parent, out var parent) &&
            !ReferenceEquals(parent, node))
        {
            var parentWorld = ResolveWorldPosition(parent, nodes) ?? new PreviewVector3(0, 0, 0);
            node.WorldPosition = new PreviewVector3(
                Math.Round(parentWorld.X + local.X, 3),
                Math.Round(parentWorld.Y + local.Y, 3),
                Math.Round(parentWorld.Z + local.Z, 3));
            return node.WorldPosition;
        }

        node.WorldPosition = local;
        return node.WorldPosition;
    }

    private static PreviewVector3? ParseTransformPosition(string line)
    {
        var values = ParseNumbers(line);
        if (values.Count < 12)
        {
            return null;
        }

        return new PreviewVector3(
            Math.Round(values[^3], 3),
            Math.Round(values[^2], 3),
            Math.Round(values[^1], 3));
    }

    private static PreviewVector3? ParseVectorPosition(string line)
    {
        var values = ParseNumbers(line);
        if (values.Count < 2)
        {
            return null;
        }

        if (values.Count == 2)
        {
            return new PreviewVector3(Math.Round(values[0], 3), 0, Math.Round(values[1], 3));
        }

        return new PreviewVector3(
            Math.Round(values[0], 3),
            Math.Round(values[1], 3),
            Math.Round(values[2], 3));
    }

    private static IReadOnlyList<double> ParseNumbers(string line)
    {
        var start = line.IndexOf('(', StringComparison.Ordinal);
        var end = line.LastIndexOf(')');
        var valueText = start >= 0 && end > start
            ? line.Substring(start + 1, end - start - 1)
            : line;
        return Regex.Matches(valueText, "-?\\d+(?:\\.\\d+)?")
            .Select(match => double.Parse(match.Value, CultureInfo.InvariantCulture))
            .ToArray();
    }

    private static double VectorLength(PreviewVector3 vector)
    {
        return Math.Sqrt(vector.X * vector.X + vector.Y * vector.Y + vector.Z * vector.Z);
    }

    private static string? ClassifyContractNodeRole(string nodeName, string nodeType, string parent)
    {
        var text = $"{nodeName} {nodeType} {parent}".ToLowerInvariant();
        if (ContainsAny(text, "mesh", "collision", "light", "shadow"))
        {
            return null;
        }

        if (ContainsAny(text, "spawn", "wave"))
        {
            return "pressure_source";
        }

        if (ContainsAny(text, "attack", "skill", "cast"))
        {
            return "action";
        }

        if (ContainsAny(text, "player", "hero", "avatar"))
        {
            return "player_start";
        }

        if (ContainsAny(text, "enemy", "monster", "boss", "opponent"))
        {
            return "challenge";
        }

        if (ContainsAny(text, "reward", "loot", "upgrade", "choice", "levelup"))
        {
            return "reward";
        }

        if (ContainsAny(text, "startbutton", "retrybutton", "continuebutton", "button"))
        {
            return "ui_action";
        }

        if (ContainsAny(text, "objective", "status", "hud", "label", "log"))
        {
            return "feedback";
        }

        if (ContainsAny(text, "door", "portal", "exit", "route"))
        {
            return "transition";
        }

        if (ContainsAny(text, "map", "room", "path", "floor"))
        {
            return "play_space";
        }

        if (ContainsAny(text, "tower", "turret", "defense"))
        {
            return "buildable_unit";
        }

        return null;
    }

    private static string NodeObjective(string role, string nodeName)
    {
        return role switch
        {
            "player_start" => $"Use {nodeName} as the controllable avatar anchor.",
            "challenge" => $"Resolve or inspect the challenge represented by {nodeName}.",
            "pressure_source" => $"Advance pressure from {nodeName}.",
            "reward" => $"Claim or inspect the reward state from {nodeName}.",
            "ui_action" => $"Trigger the UI action {nodeName}.",
            "feedback" => $"Read feedback from {nodeName}.",
            "transition" => $"Move through the transition {nodeName}.",
            "action" => $"Use the action affordance {nodeName}.",
            "play_space" => $"Navigate the play space {nodeName}.",
            "buildable_unit" => $"Inspect the buildable or defensive unit {nodeName}.",
            _ => $"Inspect {nodeName}."
        };
    }

    private static int NodeEntityPriority(PreviewContractNodeEntity entity)
    {
        return entity.Role switch
        {
            "player_start" => 0,
            "challenge" => 1,
            "pressure_source" => 2,
            "reward" => 3,
            "transition" => 4,
            "action" => 5,
            "ui_action" => 6,
            "feedback" => 7,
            "buildable_unit" => 8,
            "play_space" => 9,
            _ => 20
        };
    }

    private static IReadOnlyList<PreviewStateField> BuildPreviewStateModel()
    {
        return
        [
            new PreviewStateField("score", "Score", 0, 0, 999),
            new PreviewStateField("pressure", "Pressure", 0, 0, 9),
            new PreviewStateField("rewards", "Rewards", 0, 0, 9),
            new PreviewStateField("hp", "HP", 3, 0, 3),
            new PreviewStateField("phase", "Phase", 1, 1, 9),
            new PreviewStateField("energy", "Energy", 3, 0, 3)
        ];
    }

    private static IReadOnlyList<PreviewRoleInteraction> BuildRoleInteractions(IReadOnlyList<string> mechanicHints)
    {
        var roles = mechanicHints.Count == 0
            ? new HashSet<string>(["player_start", "pressure_source", "action", "reward", "ui_action"], StringComparer.Ordinal)
            : new HashSet<string>(mechanicHints, StringComparer.Ordinal);
        var interactions = new List<PreviewRoleInteraction>();
        AddInteraction(interactions, roles, "player_start", new Dictionary<string, int> { ["score"] = 1 }, "已定位可控角色 {label}，移动与交互链路就绪。");
        AddInteraction(interactions, roles, "pressure_source", new Dictionary<string, int> { ["pressure"] = 1, ["score"] = 2 }, "处理压力源 {label}，压力升高但仍可继续。");
        AddInteraction(interactions, roles, "challenge", new Dictionary<string, int> { ["pressure"] = 1, ["score"] = 2 }, "遭遇 {label}，完成一次通用挑战验证。");
        AddInteraction(interactions, roles, "action", new Dictionary<string, int> { ["pressure"] = -1, ["score"] = 2, ["energy"] = -1 }, "触发动作节点 {label}，压力下降并获得反馈。");
        AddInteraction(interactions, roles, "reward", new Dictionary<string, int> { ["rewards"] = 1, ["score"] = 3, ["energy"] = 3, ["phase"] = 1 }, "领取奖励 {label}，能量恢复并推进阶段。");
        AddInteraction(interactions, roles, "ui_action", new Dictionary<string, int> { ["score"] = 1 }, "触发界面动作 {label}，流程按钮可响应。");
        AddInteraction(interactions, roles, "feedback", new Dictionary<string, int>(), "读取反馈节点 {label}，HUD/日志信息可追踪。");
        AddInteraction(interactions, roles, "transition", new Dictionary<string, int> { ["phase"] = 1 }, "通过转场节点 {label}，进入下一阶段。");
        AddInteraction(interactions, roles, "play_space", new Dictionary<string, int>(), "确认可导航空间 {label}，移动区域可验证。");
        AddInteraction(interactions, roles, "buildable_unit", new Dictionary<string, int> { ["score"] = 1 }, "检查可构筑/防御单位 {label}，构筑类节点可被通用契约表达。");
        return interactions;
    }

    private static void AddInteraction(
        List<PreviewRoleInteraction> interactions,
        HashSet<string> roles,
        string role,
        IReadOnlyDictionary<string, int> stateDelta,
        string feedback)
    {
        if (!roles.Contains(role))
        {
            return;
        }

        interactions.Add(new PreviewRoleInteraction(role, stateDelta, feedback));
    }

    private static string? ResolveOptionalResPath(string projectRoot, string resourcePath)
    {
        if (!resourcePath.StartsWith("res://", StringComparison.Ordinal))
        {
            return null;
        }

        var relativePath = resourcePath["res://".Length..].Replace('/', Path.DirectorySeparatorChar);
        var fullPath = Path.GetFullPath(Path.Combine(projectRoot, relativePath));
        return WorkspacePathPolicy.IsUnderRoot(projectRoot, fullPath) ? fullPath : null;
    }

    private static bool ContainsAny(string text, params string[] needles)
    {
        return needles.Any(needle => text.Contains(needle, StringComparison.Ordinal));
    }

    private static string NormalizeToken(string value)
    {
        return Regex.Replace(value.ToLowerInvariant(), "[^a-z0-9]+", "", RegexOptions.CultureInvariant);
    }

    private static string SceneLabel(string scene, int index)
    {
        var fileName = scene.Split('/').LastOrDefault() ?? $"Scene {index + 1}";
        return Regex.Replace(fileName, "\\.tscn$", "", RegexOptions.IgnoreCase);
    }

    private sealed record PreviewContractNodeEntity(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("label")] string Label,
        [property: JsonPropertyName("role")] string Role,
        [property: JsonPropertyName("scene")] string Scene,
        [property: JsonPropertyName("objective")] string Objective,
        [property: JsonPropertyName("node_type")] string NodeType,
        [property: JsonPropertyName("node_path")] string NodePath,
        [property: JsonPropertyName("local_position")] PreviewVector3? LocalPosition = null,
        [property: JsonPropertyName("world_position")] PreviewVector3? WorldPosition = null,
        [property: JsonPropertyName("target_position")] PreviewVector3? TargetPosition = null,
        [property: JsonPropertyName("range_hint")] double? RangeHint = null);

    private sealed class PreviewSceneNode(string name, string type, string parent, string path)
    {
        public string Name { get; } = name;
        public string Type { get; } = type;
        public string Parent { get; } = parent;
        public string Path { get; } = path;
        public PreviewVector3? LocalPosition { get; set; }
        public PreviewVector3? WorldPosition { get; set; }
        public PreviewVector3? TargetPosition { get; set; }
    }

    private sealed record PreviewVector3(
        [property: JsonPropertyName("x")] double X,
        [property: JsonPropertyName("y")] double Y,
        [property: JsonPropertyName("z")] double Z);

    private sealed record PreviewStateField(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("label")] string Label,
        [property: JsonPropertyName("initial")] int Initial,
        [property: JsonPropertyName("min")] int Min,
        [property: JsonPropertyName("max")] int Max);

    private sealed record PreviewRoleInteraction(
        [property: JsonPropertyName("role")] string Role,
        [property: JsonPropertyName("state_delta")] IReadOnlyDictionary<string, int> StateDelta,
        [property: JsonPropertyName("feedback")] string Feedback);

    private static void AddFile(ZipArchive archive, string projectRoot, string absoluteFile)
    {
        var relativePath = Path.GetRelativePath(projectRoot, absoluteFile).Replace('\\', '/');
        archive.CreateEntryFromFile(absoluteFile, relativePath, CompressionLevel.Optimal);
    }

    private static bool ShouldIncludeFile(string projectRoot, string absoluteFile)
    {
        var fullPath = Path.GetFullPath(absoluteFile);
        if (!WorkspacePathPolicy.IsUnderRoot(projectRoot, fullPath))
        {
            return false;
        }

        var relativeParts = Path.GetRelativePath(projectRoot, fullPath)
            .Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        if (relativeParts.Any(part => ExcludedDirectoryNames.Contains(part, StringComparer.OrdinalIgnoreCase)))
        {
            return false;
        }

        var name = Path.GetFileName(fullPath);
        return !ExcludedFileSuffixes.Any(suffix => name.EndsWith(suffix, StringComparison.OrdinalIgnoreCase));
    }

    private static string ResolveUnderProject(string projectRoot, string relativePath)
    {
        var fullPath = Path.GetFullPath(Path.Combine(projectRoot, relativePath.Replace('/', Path.DirectorySeparatorChar)));
        if (!WorkspacePathPolicy.IsUnderRoot(projectRoot, fullPath))
        {
            throw new InvalidOperationException("Package path escaped project repository root.");
        }

        RunnerIsolationPolicy.RequireNoReparsePoint(projectRoot, fullPath);
        return fullPath;
    }

    private static string CreateVersion(int ordinal)
    {
        return $"v0.1.{DateTimeOffset.UtcNow:yyyyMMdd}.{ordinal:000}";
    }

    private static string ExtractVersion(string fileName)
    {
        var name = Path.GetFileNameWithoutExtension(fileName);
        var marker = "-v0.1.";
        var index = name.LastIndexOf(marker, StringComparison.Ordinal);
        return index < 0 ? name : name[(index + 1)..];
    }

    private static string ReadGeneratedUtc(string? evidenceJson)
    {
        if (string.IsNullOrWhiteSpace(evidenceJson))
        {
            return "";
        }

        try
        {
            using var doc = JsonDocument.Parse(evidenceJson);
            return doc.RootElement.TryGetProperty("generated_utc", out var generatedUtc)
                ? generatedUtc.GetString() ?? ""
                : "";
        }
        catch (JsonException)
        {
            return "";
        }
    }

    private static string? ReadPackageSha256(string? evidenceJson)
    {
        if (string.IsNullOrWhiteSpace(evidenceJson))
        {
            return null;
        }

        try
        {
            using var doc = JsonDocument.Parse(evidenceJson);
            if (!doc.RootElement.TryGetProperty("package_sha256", out var packageSha256))
            {
                return null;
            }

            var value = packageSha256.GetString();
            return IsSha256(value) ? value!.ToLowerInvariant() : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    // The export catalog belongs to the stable workspace, not its active source generation.
    public static string GetPackageRepositoryRoot(ProjectSnapshot project) =>
        Path.GetFullPath(Path.Combine(WorkspaceGenerationPaths.StorageRoot(project), "repo"));

    private static string? ReadSnapshotId(string? evidenceJson)
    {
        try
        {
            using var doc = JsonDocument.Parse(evidenceJson ?? "{}");
            return doc.RootElement.TryGetProperty("snapshot_id", out var value) && value.ValueKind == JsonValueKind.String
                ? value.GetString() : null;
        }
        catch (JsonException) { return null; }
    }

    private static bool IsSha256(string? value)
    {
        return value is { Length: 64 } &&
               value.All(ch => ch is >= '0' and <= '9' or >= 'a' and <= 'f' or >= 'A' and <= 'F');
    }

    private static string SafeFileName(string value)
    {
        var invalid = Path.GetInvalidFileNameChars().ToHashSet();
        var cleaned = new string(value.Trim().Select(ch => invalid.Contains(ch) || char.IsWhiteSpace(ch) ? '-' : ch).ToArray());
        return string.IsNullOrWhiteSpace(cleaned) ? "project" : cleaned;
    }

    private static ProjectPackageResult Failure(string projectId, string failureCode)
    {
        return new ProjectPackageResult(projectId, "", failureCode, "", "", "", "", 0, 0, [], failureCode);
    }

    private static ProjectPackageResult Failure(string projectId, string failureCode, string runId)
    {
        return new ProjectPackageResult(projectId, runId, failureCode, "", "", "", "", 0, 0, [], failureCode);
    }

    private sealed record AssetSelectionApplyResult(
        int AppliedCount,
        IReadOnlyList<string> ScenePaths);

    private sealed record ProjectPackageRecord(
        string Version,
        string FileName,
        string RelativePath,
        long SizeBytes,
        string PackageSha256,
        string CreatedUtc,
        string? SnapshotId);

    private sealed record AssetReplacementSmokeResult(
        bool Ran,
        int ExitCode,
        string Reason,
        string? ScenePath,
        IReadOnlyList<string> ScenePaths,
        string Stdout,
        string Stderr)
    {
        public static AssetReplacementSmokeResult NotRequired(string reason)
        {
            return new AssetReplacementSmokeResult(false, 0, reason, null, [], "", "");
        }

        public static AssetReplacementSmokeResult Skipped(string reason, IReadOnlyList<string> scenePaths)
        {
            return new AssetReplacementSmokeResult(false, 0, reason, scenePaths.FirstOrDefault(), scenePaths, "", "");
        }
    }
}
