using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Workspaces;

public interface IProjectWorkspaceSeeder
{
    void EnsureSeeded(string projectRepoPath);
}

public sealed class ProjectWorkspaceSeeder : IProjectWorkspaceSeeder
{
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
            return;
        }

        Directory.CreateDirectory(targetRoot);
        CopyDirectory(sourceRoot, targetRoot);
    }

    private static void CopyDirectory(string sourceRoot, string targetRoot)
    {
        foreach (var directory in Directory.EnumerateDirectories(sourceRoot))
        {
            var name = Path.GetFileName(directory);
            if (ShouldSkipDirectory(name, directory))
            {
                continue;
            }

            var destination = Path.Combine(targetRoot, name);
            Directory.CreateDirectory(destination);
            CopyDirectory(directory, destination);
        }

        foreach (var file in Directory.EnumerateFiles(sourceRoot))
        {
            var name = Path.GetFileName(file);
            if (ShouldSkipFile(name))
            {
                continue;
            }

            File.Copy(file, Path.Combine(targetRoot, name), overwrite: false);
        }
    }

    private static bool ShouldSkipDirectory(string name, string fullPath)
    {
        if (ExcludedDirectoryNames.Contains(name, StringComparer.OrdinalIgnoreCase))
        {
            return true;
        }

        return name.StartsWith("phase-a-workspaces-", StringComparison.OrdinalIgnoreCase) ||
               fullPath.Contains($"{Path.DirectorySeparatorChar}logs{Path.DirectorySeparatorChar}phase-a-innernet{Path.DirectorySeparatorChar}workspaces", StringComparison.OrdinalIgnoreCase);
    }

    private static bool ShouldSkipFile(string name)
    {
        return name.EndsWith(".user", StringComparison.OrdinalIgnoreCase) ||
               name.EndsWith(".suo", StringComparison.OrdinalIgnoreCase) ||
               name.Equals("phase-a-platform.sqlite3", StringComparison.OrdinalIgnoreCase) ||
               name.Equals("phase-a-platform.sqlite3-shm", StringComparison.OrdinalIgnoreCase) ||
               name.Equals("phase-a-platform.sqlite3-wal", StringComparison.OrdinalIgnoreCase);
    }
}
