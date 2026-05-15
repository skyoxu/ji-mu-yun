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

    private static readonly string[] ExcludedDirectoryNames =
    [
        ".git",
        ".vs",
        ".vscode",
        "bin",
        "obj",
        "logs",
        "TestResults"
    ];

    private static readonly string[] ManagedRelativeDirectories =
    [
        "scripts",
        ".agents/skills",
        "docs/prototype-type-kits",
        "docs/game-type-guides"
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
        var targetRoot = Path.GetFullPath(projectRepoPath);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, targetRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        if (Directory.Exists(targetRoot) && Directory.EnumerateFileSystemEntries(targetRoot).Any())
        {
            SyncManagedDirectories(sourceRoot, targetRoot);
            RestoreWorkspaceJunctions(sourceRoot, targetRoot);
            return;
        }

        Directory.CreateDirectory(targetRoot);
        CopyDirectory(sourceRoot, sourceRoot, targetRoot, overwriteFiles: false);
        RestoreWorkspaceJunctions(sourceRoot, targetRoot);
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
        }
    }

    private static void CopyDirectory(string repositoryRoot, string sourceRoot, string targetRoot, bool overwriteFiles)
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
            CopyDirectory(repositoryRoot, directory, destination, overwriteFiles);
        }

        foreach (var file in Directory.EnumerateFiles(sourceRoot))
        {
            var name = Path.GetFileName(file);
            if (ShouldSkipFile(repositoryRoot, name, file))
            {
                continue;
            }

            File.Copy(file, Path.Combine(targetRoot, name), overwrite: overwriteFiles);
        }
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

        if (ExcludedDirectoryNames.Contains(name, StringComparer.OrdinalIgnoreCase))
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

    private static bool ShouldSkipFile(string sourceRoot, string name, string fullPath)
    {
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
}
