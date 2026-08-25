using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Workspaces;

public interface IProjectWorkspaceSeeder
{
    void EnsureSeeded(string projectRepoPath);
}

public sealed class ProjectWorkspaceSeeder : IProjectWorkspaceSeeder
{
    private const FileAttributes ReparsePointAttribute = (FileAttributes)0x400;
    private const string TestsProjectDirectoryName = "Tests.Godot";
    private const string RuntimeDirectoryName = "Game.Godot";
    private const string SeedCompletionMarkerName = ".phasea-seed-complete";
    private const string HostedProjectTemplateRelativeDirectory =
        "PhaseA.Platform/Workspaces/HostedProjectTemplate";
    private const int LockedFileRetryCount = 3;
    private static readonly TimeSpan LockedFileRetryDelay = TimeSpan.FromMilliseconds(250);
    private static readonly object WorkspaceSeedLocksGate = new();
    private static readonly Dictionary<string, WorkspaceSeedLockEntry> WorkspaceSeedLocks =
        new(StringComparer.OrdinalIgnoreCase);

    private static readonly string[] ExcludedDirectoryNames =
    [
        ".git",
        ".dotnet",
        ".vs",
        ".vscode",
        "bin",
        "obj",
        "buildcache",
        "logs",
        "TestResults",
        "PhaseA.Platform",
        "PhaseA.Platform.Tests",
        "execution-plans",
        "_bmad-output",
        ".fastctx"
    ];

    private static readonly string[] ManagedRelativeDirectories =
    [
        "scripts",
        "_bmad/scripts",
        ".agents/skills",
        "docs/prototype-type-kits",
        "Tests.Godot/addons/gdUnit4"
    ];

    private static readonly string[] ManagedRelativeFiles =
    [
        "Directory.Build.props",
        "Directory.Build.targets"
    ];

    private static readonly string[] ManagedIfMissingRelativeFiles =
    [
        "_bmad/gds/config.yaml"
    ];

    private static readonly string[] RetiredManagedSkillDirectories =
    [
        "bmad-create-ux-design",
        "bmad-distillator",
        "gds-create-prd",
        "gds-create-ux-design",
        "gds-edit-gdd",
        "gds-edit-prd",
        "gds-validate-gdd",
        "gds-validate-prd"
    ];

    private static readonly string[] BootstrapBaselineRelativeFiles =
    [
        "AGENTS.md",
        "README.md",
        "Game.sln",
        "project.godot",
        "Game.Core.Tests/Game.Core.Tests.csproj"
    ];

    private static readonly (string TemplateFileName, string DestinationFileName)[] HostedProjectEntryFiles =
    [
        ("AGENTS.template.md", "AGENTS.md"),
        ("README.template.md", "README.md")
    ];

    private static readonly string[] SeededPrototypeTemplateDirectories =
    [
        "DefaultRpgTemplate"
    ];

    private static readonly string[] SeededPrototypeTemplateRootFiles =
    [
        "README.md",
        "TEMPLATE.md",
        "TEMPLATE.zh-CN.md"
    ];

    private readonly PhaseAPlatformOptions _options;

    public ProjectWorkspaceSeeder(PhaseAPlatformOptions options)
    {
        _options = options;
    }

    public void EnsureSeeded(string projectRepoPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectRepoPath);

        var sourceRoot = Path.GetFullPath(_options.RepositoryRoot);
        var targetRoot = Path.TrimEndingDirectorySeparator(Path.GetFullPath(projectRepoPath));
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, targetRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        var seedLock = AcquireWorkspaceSeedLock(targetRoot);
        try
        {
            lock (seedLock.SyncRoot)
            {
                EnsureSeededCore(sourceRoot, targetRoot);
            }
        }
        finally
        {
            ReleaseWorkspaceSeedLock(targetRoot, seedLock);
        }
    }

    private static void EnsureSeededCore(string sourceRoot, string targetRoot)
    {
        if (Directory.Exists(targetRoot) && Directory.EnumerateFileSystemEntries(targetRoot).Any())
        {
            if (!File.Exists(Path.Combine(targetRoot, SeedCompletionMarkerName)))
            {
                CopyDirectory(sourceRoot, sourceRoot, targetRoot, overwriteFiles: false);
            }
            else
            {
                EnsureBootstrapBaseline(sourceRoot, targetRoot);
            }
            EnsureHostedProjectEntryDocuments(sourceRoot, targetRoot);
            SyncManagedFiles(sourceRoot, targetRoot);
            SyncManagedDirectories(sourceRoot, targetRoot);
            RestoreWorkspaceJunctions(sourceRoot, targetRoot);
            EnsureRuntimeLogsAreGodotIgnored(targetRoot);
            WriteSeedCompletionMarker(targetRoot);
            return;
        }

        Directory.CreateDirectory(targetRoot);
        CopyDirectory(sourceRoot, sourceRoot, targetRoot, overwriteFiles: false);
        EnsureHostedProjectEntryDocuments(sourceRoot, targetRoot);
        RestoreWorkspaceJunctions(sourceRoot, targetRoot);
        EnsureRuntimeLogsAreGodotIgnored(targetRoot);
        WriteSeedCompletionMarker(targetRoot);
    }

    private static void EnsureBootstrapBaseline(string sourceRoot, string targetRoot)
    {
        if (!NeedsBootstrapBaseline(sourceRoot, targetRoot))
        {
            return;
        }

        CopyDirectory(sourceRoot, sourceRoot, targetRoot, overwriteFiles: false);
    }

    private static bool NeedsBootstrapBaseline(string sourceRoot, string targetRoot)
    {
        foreach (var relativePath in BootstrapBaselineRelativeFiles)
        {
            var sourcePath = Path.Combine(sourceRoot, relativePath.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(sourcePath))
            {
                continue;
            }

            var targetPath = Path.Combine(targetRoot, relativePath.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(targetPath))
            {
                return true;
            }
        }

        return false;
    }

    private static void EnsureHostedProjectEntryDocuments(string sourceRoot, string targetRoot)
    {
        if (!HasHostedProjectEntryTemplate(sourceRoot))
        {
            return;
        }

        var templateRoot = ResolveRepositoryRelativePath(sourceRoot, HostedProjectTemplateRelativeDirectory);
        foreach (var (templateFileName, destinationFileName) in HostedProjectEntryFiles)
        {
            var destinationPath = Path.Combine(targetRoot, destinationFileName);
            if (File.Exists(destinationPath))
            {
                continue;
            }

            File.Copy(Path.Combine(templateRoot, templateFileName), destinationPath, overwrite: false);
        }
    }

    private static bool HasHostedProjectEntryTemplate(string sourceRoot)
    {
        var templateRoot = ResolveRepositoryRelativePath(sourceRoot, HostedProjectTemplateRelativeDirectory);
        return HostedProjectEntryFiles.All(item => File.Exists(Path.Combine(templateRoot, item.TemplateFileName)));
    }

    private static string ResolveRepositoryRelativePath(string sourceRoot, string relativePath)
    {
        return Path.Combine(sourceRoot, relativePath.Replace('/', Path.DirectorySeparatorChar));
    }

    private static void SyncManagedFiles(string sourceRoot, string targetRoot)
    {
        foreach (var relativeFile in ManagedRelativeFiles)
        {
            var sourcePath = Path.Combine(sourceRoot, relativeFile.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(sourcePath))
            {
                continue;
            }

            var destinationPath = Path.Combine(targetRoot, relativeFile.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(destinationPath)!);
            if (!TryCopyFileWithLockTolerance(sourceRoot, sourcePath, destinationPath, overwriteFiles: true))
            {
                throw new IOException($"Managed workspace file could not be synchronized: {relativeFile}");
            }
        }

        foreach (var relativeFile in ManagedIfMissingRelativeFiles)
        {
            var sourcePath = Path.Combine(sourceRoot, relativeFile.Replace('/', Path.DirectorySeparatorChar));
            var destinationPath = Path.Combine(targetRoot, relativeFile.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(sourcePath) || File.Exists(destinationPath))
            {
                continue;
            }

            Directory.CreateDirectory(Path.GetDirectoryName(destinationPath)!);
            if (!TryCopyFileWithLockTolerance(sourceRoot, sourcePath, destinationPath, overwriteFiles: false))
            {
                throw new IOException($"Required workspace file could not be seeded: {relativeFile}");
            }
        }
    }

    private static WorkspaceSeedLockEntry AcquireWorkspaceSeedLock(string targetRoot)
    {
        lock (WorkspaceSeedLocksGate)
        {
            if (!WorkspaceSeedLocks.TryGetValue(targetRoot, out var entry))
            {
                entry = new WorkspaceSeedLockEntry();
                WorkspaceSeedLocks.Add(targetRoot, entry);
            }
            entry.ReferenceCount++;
            return entry;
        }
    }

    private static void ReleaseWorkspaceSeedLock(string targetRoot, WorkspaceSeedLockEntry entry)
    {
        lock (WorkspaceSeedLocksGate)
        {
            entry.ReferenceCount--;
            if (entry.ReferenceCount == 0)
            {
                WorkspaceSeedLocks.Remove(targetRoot);
            }
        }
    }

    private static void SyncManagedDirectories(string sourceRoot, string targetRoot)
    {
        foreach (var relativeDirectory in ManagedRelativeDirectories)
        {
            var sourcePath = Path.Combine(sourceRoot, relativeDirectory.Replace('/', Path.DirectorySeparatorChar));
            if (!Directory.Exists(sourcePath))
            {
                continue;
            }

            var destinationPath = Path.Combine(targetRoot, relativeDirectory.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(destinationPath);
            CopyDirectory(sourceRoot, sourcePath, destinationPath, overwriteFiles: true);
            if (string.Equals(relativeDirectory, ".agents/skills", StringComparison.OrdinalIgnoreCase))
            {
                PruneRetiredManagedSkills(sourcePath, destinationPath);
            }
        }
    }

    private static void PruneRetiredManagedSkills(string sourceSkillRoot, string targetSkillRoot)
    {
        foreach (var skillName in RetiredManagedSkillDirectories)
        {
            if (Directory.Exists(Path.Combine(sourceSkillRoot, skillName)))
            {
                continue;
            }

            var targetPath = Path.Combine(targetSkillRoot, skillName);
            if (!Directory.Exists(targetPath))
            {
                continue;
            }

            var attributes = File.GetAttributes(targetPath);
            Directory.Delete(targetPath, recursive: (attributes & FileAttributes.ReparsePoint) == 0);
        }
    }

    private static void CopyDirectory(string repositoryRoot, string sourceRoot, string targetRoot, bool overwriteFiles)
    {
        CopyDirectory(
            repositoryRoot,
            sourceRoot,
            targetRoot,
            overwriteFiles,
            HasHostedProjectEntryTemplate(repositoryRoot));
    }

    private static void CopyDirectory(
        string repositoryRoot,
        string sourceRoot,
        string targetRoot,
        bool overwriteFiles,
        bool hasHostedProjectEntryTemplate)
    {
        foreach (var directory in Directory.EnumerateDirectories(sourceRoot))
        {
            var name = Path.GetFileName(directory);
            if (ShouldSkipDirectory(repositoryRoot, name, directory))
            {
                continue;
            }

            var destination = Path.Combine(targetRoot, name);
            Directory.CreateDirectory(destination);
            CopyDirectory(
                repositoryRoot,
                directory,
                destination,
                overwriteFiles,
                hasHostedProjectEntryTemplate);
        }

        foreach (var file in Directory.EnumerateFiles(sourceRoot))
        {
            var name = Path.GetFileName(file);
            if (ShouldSkipFile(repositoryRoot, name, file, hasHostedProjectEntryTemplate))
            {
                continue;
            }

            var destination = Path.Combine(targetRoot, name);
            if (!TryCopyFileWithLockTolerance(repositoryRoot, file, destination, overwriteFiles))
            {
                continue;
            }
        }
    }

    private static bool TryCopyFileWithLockTolerance(string repositoryRoot, string sourcePath, string destinationPath, bool overwriteFiles)
    {
        if (!overwriteFiles && File.Exists(destinationPath))
        {
            return true;
        }

        var relativePath = Path.GetRelativePath(repositoryRoot, sourcePath)
            .Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar);
        var tolerateLockedFile = IsLockTolerantManagedPath(relativePath);
        for (var attempt = 1; attempt <= LockedFileRetryCount; attempt++)
        {
            string? temporaryPath = null;
            try
            {
                if (overwriteFiles)
                {
                    temporaryPath = $"{destinationPath}.phasea-seed-{Guid.NewGuid():N}.tmp";
                    File.Copy(sourcePath, temporaryPath, overwrite: false);
                    File.Move(temporaryPath, destinationPath, overwrite: true);
                    temporaryPath = null;
                }
                else
                {
                    File.Copy(sourcePath, destinationPath, overwrite: false);
                }
                return true;
            }
            catch (IOException) when ((tolerateLockedFile || overwriteFiles) && attempt < LockedFileRetryCount)
            {
                Thread.Sleep(LockedFileRetryDelay);
            }
            catch (UnauthorizedAccessException) when ((tolerateLockedFile || overwriteFiles) && attempt < LockedFileRetryCount)
            {
                Thread.Sleep(LockedFileRetryDelay);
            }
            catch (IOException) when (tolerateLockedFile || overwriteFiles)
            {
                return false;
            }
            catch (UnauthorizedAccessException) when (tolerateLockedFile || overwriteFiles)
            {
                return false;
            }
            finally
            {
                if (!string.IsNullOrWhiteSpace(temporaryPath) && File.Exists(temporaryPath))
                {
                    File.Delete(temporaryPath);
                }
            }
        }

        return false;
    }

    private static bool IsLockTolerantManagedPath(string relativePath)
    {
        return relativePath.StartsWith(
            $"Tests.Godot{Path.DirectorySeparatorChar}addons{Path.DirectorySeparatorChar}gdUnit4{Path.DirectorySeparatorChar}",
            StringComparison.OrdinalIgnoreCase);
    }

    private static void EnsureRuntimeLogsAreGodotIgnored(string targetRoot)
    {
        var logsRoot = Path.Combine(targetRoot, "logs");
        Directory.CreateDirectory(logsRoot);
        var gdignorePath = Path.Combine(logsRoot, ".gdignore");
        if (!File.Exists(gdignorePath))
        {
            File.WriteAllText(gdignorePath, string.Empty);
        }
    }

    private static void WriteSeedCompletionMarker(string targetRoot)
    {
        File.WriteAllText(
            Path.Combine(targetRoot, SeedCompletionMarkerName),
            "phase-a-workspace-seed.v1\n");
    }

    private static void RestoreWorkspaceJunctions(string sourceRoot, string targetRoot)
    {
        var sourceTestsRoot = Path.Combine(sourceRoot, TestsProjectDirectoryName);
        if (!Directory.Exists(sourceTestsRoot))
        {
            return;
        }

        var targetRuntime = Path.Combine(targetRoot, RuntimeDirectoryName);
        var targetTestsRoot = Path.Combine(targetRoot, TestsProjectDirectoryName);
        if (!Directory.Exists(targetTestsRoot) || !Directory.Exists(targetRuntime))
        {
            return;
        }

        var targetLink = Path.Combine(targetTestsRoot, RuntimeDirectoryName);
        if (Directory.Exists(targetLink) && IsReparsePoint(targetLink))
        {
            var resolved = Path.GetFullPath(new DirectoryInfo(targetLink).ResolveLinkTarget(returnFinalTarget: true)?.FullName ?? string.Empty);
            if (string.Equals(resolved, Path.GetFullPath(targetRuntime), StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            TryDeleteJunction(targetLink);
        }
        else if (Directory.Exists(targetLink))
        {
            Directory.Delete(targetLink, recursive: true);
        }

        if (!TryCreateJunction(targetLink, targetRuntime, out var createDetails))
        {
            throw new InvalidOperationException($"Failed to restore Tests.Godot/Game.Godot junction in hosted workspace. {createDetails}");
        }
    }

    private static bool ShouldSkipDirectory(string sourceRoot, string name, string fullPath)
    {
        if (IsReparsePoint(fullPath))
        {
            return true;
        }

        if (ShouldAlwaysKeepDirectory(sourceRoot, fullPath))
        {
            return false;
        }

        if (ShouldSkipHostedProjectTemplateDirectory(sourceRoot, fullPath))
        {
            return true;
        }

        if (ExcludedDirectoryNames.Contains(name, StringComparer.OrdinalIgnoreCase))
        {
            return true;
        }

        if (ShouldSkipDownstreamGameTypeGuideDirectory(sourceRoot, fullPath))
        {
            return true;
        }

        if (ShouldSkipGeneratedPrototypeContent(sourceRoot, fullPath, name, isDirectory: true))
        {
            return true;
        }

        return name.StartsWith("phase-a-workspaces-", StringComparison.OrdinalIgnoreCase) ||
               fullPath.Contains($"{Path.DirectorySeparatorChar}logs{Path.DirectorySeparatorChar}phase-a-innernet{Path.DirectorySeparatorChar}workspaces", StringComparison.OrdinalIgnoreCase);
    }

    private static bool ShouldAlwaysKeepDirectory(string sourceRoot, string fullPath)
    {
        var relativePath = Path.GetRelativePath(sourceRoot, fullPath)
            .Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar);

        return relativePath.Equals(
            $"Tests.Godot{Path.DirectorySeparatorChar}addons{Path.DirectorySeparatorChar}gdUnit4{Path.DirectorySeparatorChar}bin",
            StringComparison.OrdinalIgnoreCase);
    }

    private static bool ShouldSkipDownstreamGameTypeGuideDirectory(string sourceRoot, string fullPath)
    {
        var relativePath = Path.GetRelativePath(sourceRoot, fullPath)
            .Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar);

        return relativePath.Equals(
            $"docs{Path.DirectorySeparatorChar}game-type-guides",
            StringComparison.OrdinalIgnoreCase);
    }

    private static bool ShouldSkipHostedProjectTemplateDirectory(string sourceRoot, string fullPath)
    {
        var relativePath = Path.GetRelativePath(sourceRoot, fullPath)
            .Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar);

        return relativePath.Equals(
            HostedProjectTemplateRelativeDirectory.Replace('/', Path.DirectorySeparatorChar),
            StringComparison.OrdinalIgnoreCase);
    }

    private static bool ShouldSkipFile(
        string sourceRoot,
        string name,
        string fullPath,
        bool hasHostedProjectEntryTemplate)
    {
        if (hasHostedProjectEntryTemplate && IsRepositoryRootEntryDocument(sourceRoot, name, fullPath))
        {
            return true;
        }

        if (ShouldSkipGeneratedPrototypeContent(sourceRoot, fullPath, name, isDirectory: false))
        {
            return true;
        }

        return name.EndsWith(".user", StringComparison.OrdinalIgnoreCase) ||
               name.EndsWith(".suo", StringComparison.OrdinalIgnoreCase) ||
               name.Equals("phase-a-platform.sqlite3", StringComparison.OrdinalIgnoreCase) ||
               name.Equals("phase-a-platform.sqlite3-shm", StringComparison.OrdinalIgnoreCase) ||
               name.Equals("phase-a-platform.sqlite3-wal", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsRepositoryRootEntryDocument(string sourceRoot, string name, string fullPath)
    {
        if (!name.Equals("AGENTS.md", StringComparison.OrdinalIgnoreCase) &&
            !name.Equals("README.md", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        var relativePath = Path.GetRelativePath(sourceRoot, fullPath);
        return !relativePath.Contains(Path.DirectorySeparatorChar) &&
               !relativePath.Contains(Path.AltDirectorySeparatorChar);
    }

    private static bool ShouldSkipGeneratedPrototypeContent(string sourceRoot, string fullPath, string name, bool isDirectory)
    {
        var relativePath = Path.GetRelativePath(sourceRoot, fullPath)
            .Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar);
        var segments = relativePath.Split(Path.DirectorySeparatorChar, StringSplitOptions.RemoveEmptyEntries);
        if (segments.Length < 2)
        {
            return false;
        }

        if (segments[0].Equals("Game.Godot", StringComparison.OrdinalIgnoreCase) &&
            segments[1].Equals("Prototypes", StringComparison.OrdinalIgnoreCase))
        {
            return segments.Length >= 3 &&
                   !SeededPrototypeTemplateDirectories.Contains(segments[2], StringComparer.OrdinalIgnoreCase);
        }

        if (segments[0].Equals("Game.Core", StringComparison.OrdinalIgnoreCase) &&
            segments[1].Equals("Prototypes", StringComparison.OrdinalIgnoreCase))
        {
            return segments.Length >= 3 &&
                   !name.StartsWith("DefaultRpgPrototypeLoop", StringComparison.OrdinalIgnoreCase);
        }

        if (segments[0].Equals("Game.Core.Tests", StringComparison.OrdinalIgnoreCase) &&
            segments[1].Equals("Prototypes", StringComparison.OrdinalIgnoreCase))
        {
            return segments.Length >= 3 &&
                   !name.StartsWith("DefaultRpgPrototypeLoopTests", StringComparison.OrdinalIgnoreCase);
        }

        if (segments[0].Equals("Tests.Godot", StringComparison.OrdinalIgnoreCase) &&
            segments[1].Equals("tests", StringComparison.OrdinalIgnoreCase) &&
            segments.Length >= 3 &&
            segments[2].Equals("Prototype", StringComparison.OrdinalIgnoreCase))
        {
            return segments.Length >= 4 &&
                   !segments[3].Equals("DefaultRpgPrototype", StringComparison.OrdinalIgnoreCase);
        }

        if (segments[0].Equals("docs", StringComparison.OrdinalIgnoreCase) &&
            segments[1].Equals("prototypes", StringComparison.OrdinalIgnoreCase))
        {
            if (segments.Length >= 4)
            {
                return true;
            }

            if (segments.Length == 3)
            {
                if (SeededPrototypeTemplateRootFiles.Contains(name, StringComparer.OrdinalIgnoreCase))
                {
                    return false;
                }

                return !name.Contains("default-rpg-template", StringComparison.OrdinalIgnoreCase);
            }
        }

        return false;
    }

    private static bool IsReparsePoint(string fullPath)
    {
        return (File.GetAttributes(fullPath) & ReparsePointAttribute) != 0;
    }

    private static void TryDeleteJunction(string fullPath)
    {
        try
        {
            Directory.Delete(fullPath, recursive: false);
        }
        catch (IOException)
        {
            Directory.Delete(fullPath, recursive: true);
        }
    }

    private static bool TryCreateJunction(string junctionPath, string targetPath, out string details)
    {
        var parent = Path.GetDirectoryName(junctionPath);
        if (string.IsNullOrWhiteSpace(parent))
        {
            details = "parent_path_missing";
            return false;
        }

        Directory.CreateDirectory(parent);
        try
        {
            Directory.CreateSymbolicLink(junctionPath, targetPath);
            var created = Directory.Exists(junctionPath) && IsReparsePoint(junctionPath);
            details = $"mode=dotnet-symlink; junction={junctionPath}; target={targetPath}; created={created}";
            if (created)
            {
                return true;
            }
        }
        catch (Exception ex)
        {
            details = $"mode=dotnet-symlink; junction={junctionPath}; target={targetPath}; error={ex.GetType().Name}:{ex.Message}";
        }

        var relativeTarget = Path.GetRelativePath(parent, targetPath).Replace('/', '\\');
        var startInfo = new System.Diagnostics.ProcessStartInfo
        {
            FileName = "cmd.exe",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            WorkingDirectory = parent
        };
        startInfo.ArgumentList.Add("/c");
        startInfo.ArgumentList.Add("mklink");
        startInfo.ArgumentList.Add("/J");
        startInfo.ArgumentList.Add(Path.GetFileName(junctionPath));
        startInfo.ArgumentList.Add(relativeTarget);

        using var process = System.Diagnostics.Process.Start(startInfo);
        process?.WaitForExit(10_000);
        var stdout = process?.StandardOutput.ReadToEnd() ?? string.Empty;
        var stderr = process?.StandardError.ReadToEnd() ?? string.Empty;
        var ok = process is not null && process.ExitCode == 0 && Directory.Exists(junctionPath) && IsReparsePoint(junctionPath);
        details = $"{details}; mode=mklink-junction; rc={process?.ExitCode ?? -1}; parent={parent}; junction={junctionPath}; target={targetPath}; relative={relativeTarget}; stdout={stdout}; stderr={stderr}";
        return ok;
    }

    private sealed class WorkspaceSeedLockEntry
    {
        public object SyncRoot { get; } = new();

        public int ReferenceCount { get; set; }
    }
}
