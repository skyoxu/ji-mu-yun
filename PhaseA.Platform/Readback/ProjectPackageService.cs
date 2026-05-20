using System.IO.Compression;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
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

    public ProjectPackageService(PhaseAMetadataStore metadataStore, PhaseAPlatformOptions options)
    {
        _metadataStore = metadataStore;
        _options = options;
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
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);

        try
        {
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
}
