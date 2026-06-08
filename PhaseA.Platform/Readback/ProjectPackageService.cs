using System.IO.Compression;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Readback;

public sealed class ProjectPackageService
{
    private const string RunType = "project-package";
    private const string PackageArtifactType = "project-package-zip";
    private const string PackageRootDirectory = "exports";

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

    public ProjectPackageService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        HeavyRunnerQueueService? heavyRunnerQueue = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _heavyRunnerQueue = heavyRunnerQueue ?? new HeavyRunnerQueueService();
    }

    public async Task<ProjectPackageResult> CreatePackageAsync(
        string accountId,
        string projectId,
        CancellationToken cancellationToken = default)
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

        if (!await HasSucceededPrototypeRunAsync(project.ProjectId, cancellationToken))
        {
            return Failure(projectId, "prototype_not_created");
        }

        var projectRoot = Path.GetFullPath(project.RepoPath);
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

        try
        {
            await using var heavyRunnerLease = await _heavyRunnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, RunType, CancellationToken.None);
            await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);
            var packageOrdinal = await NextPackageOrdinalAsync(project.ProjectId, cancellationToken);
            var version = CreateVersion(packageOrdinal);
            var safeName = SafeFileName(project.Name);
            var fileName = $"{safeName}-{version}.zip";
            var relativePath = $"{PackageRootDirectory}/{fileName}";
            var packagePath = ResolveUnderProject(projectRoot, relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(packagePath)!);
            if (File.Exists(packagePath))
            {
                File.Delete(packagePath);
            }

            var appliedAssetSelectionCount = ApplySelectedAssetLibraryEntries(projectRoot);
            var includedFileCount = CreateZip(projectRoot, packagePath, project, version);
            var sizeBytes = new FileInfo(packagePath).Length;
            var generatedUtc = DateTimeOffset.UtcNow.ToString("O");
            await _metadataStore.AddArtifactAsync(
                new ArtifactCreationCommand(
                    runId,
                    project.ProjectId,
                    PackageArtifactType,
                    relativePath,
                    "Downloadable project-only package"),
                cancellationToken);

            var evidenceJson = JsonSerializer.Serialize(new
            {
                run_type = RunType,
                version,
                generated_utc = generatedUtc,
                file_name = fileName,
                relative_path = relativePath,
                size_bytes = sizeBytes,
                included_file_count = includedFileCount,
                applied_asset_selection_count = appliedAssetSelectionCount,
                included_roots = IncludedRoots,
                included_root_files = IncludedRootFiles
            });
            await _metadataStore.CompleteRunAsync(runId, "succeeded", 0, $"Created {fileName}", "", evidenceJson, cancellationToken);
            var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);

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
                artifacts);
        }
        catch (Exception ex)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), "{}", CancellationToken.None);
            return new ProjectPackageResult(projectId, runId, "failed", "", "", "", "", 0, 0, [], "package_failed");
        }
        finally
        {
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

        var projectRoot = Path.GetFullPath(project.RepoPath);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        var hasPrototype = await HasSucceededPrototypeRunAsync(project.ProjectId, cancellationToken);
        var isBusy = project.BootstrapStatus == "running" ||
                     await _metadataStore.HasRunnerLockAsync(projectId, cancellationToken) ||
                     await _metadataStore.HasActiveRunAsync(project.ProjectId, cancellationToken);
        var disabledReason = !hasPrototype
            ? "prototype_not_created"
            : isBusy
                ? "project_busy"
                : null;

        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        var packages = new List<ProjectPackageListItem>();
        foreach (var run in runs.Where(run => run.RunType == RunType && run.Status == "succeeded"))
        {
            var artifacts = await _metadataStore.ListArtifactsForRunAsync(run.RunId, cancellationToken);
            foreach (var artifact in artifacts.Where(artifact => artifact.ArtifactType == PackageArtifactType))
            {
                var fileName = Path.GetFileName(artifact.RelativePath);
                var packagePath = ResolveUnderProject(projectRoot, artifact.RelativePath);
                if (!File.Exists(packagePath))
                {
                    continue;
                }

                packages.Add(new ProjectPackageListItem(
                    ExtractVersion(fileName),
                    fileName,
                    artifact.RelativePath,
                    $"/projects/{project.ProjectId}/packages/{Uri.EscapeDataString(fileName)}",
                    new FileInfo(packagePath).Length,
                    ReadGeneratedUtc(run.EvidenceJson)));
            }
        }

        return new ProjectPackageListResult(
            project.ProjectId,
            hasPrototype && !isBusy,
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

        var packagePath = ResolveUnderProject(project.RepoPath, $"{PackageRootDirectory}/{fileName}");
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

    private async Task<bool> HasSucceededPrototypeRunAsync(string projectId, CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(projectId, cancellationToken);
        return runs.Any(run => run.RunType == "prototype-7day-playable" && run.Status == "succeeded");
    }

    private static int CreateZip(string projectRoot, string packagePath, ProjectSnapshot project, string version)
    {
        using var stream = File.Create(packagePath);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Create);
        var included = 0;
        AddManifest(archive, project, version);

        foreach (var root in IncludedRoots)
        {
            var absoluteRoot = Path.Combine(projectRoot, root.Replace('/', Path.DirectorySeparatorChar));
            if (!Directory.Exists(absoluteRoot))
            {
                continue;
            }

            foreach (var file in Directory.EnumerateFiles(absoluteRoot, "*", SearchOption.AllDirectories))
            {
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

    private static int ApplySelectedAssetLibraryEntries(string projectRoot)
    {
        var libraryPath = ResolveUnderProject(projectRoot, "meta/assets/library.json");
        if (!File.Exists(libraryPath))
        {
            return 0;
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
            return 0;
        }

        if (library is null)
        {
            return 0;
        }

        var applied = 0;
        foreach (var unit in library.Units)
        {
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
            if (IsResPath(unit.ResourcePath))
            {
                var oldToken = $"path=\"{unit.ResourcePath}\"";
                var newToken = $"path=\"{selectedPreviewResourcePath}\"";
                if (!sceneText.Contains(oldToken, StringComparison.Ordinal))
                {
                    continue;
                }

                File.WriteAllText(scenePath, sceneText.Replace(oldToken, newToken, StringComparison.Ordinal), Encoding.UTF8);
                applied++;
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
        }

        return applied;
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
        var hash = unchecked((uint)HashCode.Combine(unitKey, previewResourcePath));
        return hash.ToString("x8");
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

    private static void AddManifest(ZipArchive archive, ProjectSnapshot project, string version)
    {
        var entry = archive.CreateEntry("PACKAGE-MANIFEST.json", CompressionLevel.Optimal);
        using var writer = new StreamWriter(entry.Open());
        writer.Write(JsonSerializer.Serialize(new
        {
            package_version = version,
            generated_utc = DateTimeOffset.UtcNow.ToString("O"),
            project_id = project.ProjectId,
            project_name = project.Name,
            game_name = project.GameName,
            game_type_source = project.GameTypeSource,
            policy = "project-files-only"
        }, new JsonSerializerOptions { WriteIndented = true }));
    }

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
}
