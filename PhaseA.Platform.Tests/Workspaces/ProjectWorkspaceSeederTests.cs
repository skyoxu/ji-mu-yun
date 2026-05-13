using System.Diagnostics;
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Workspaces;

public sealed class ProjectWorkspaceSeederTests
{
    [Fact]
    public void EnsureSeeded_SkipsReparsePointDirectories()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        var sourceRoot = source.Path;
        var realRuntime = Path.Combine(sourceRoot, "Game.Godot");
        var testsRoot = Path.Combine(sourceRoot, "Tests.Godot");
        var junctionPath = Path.Combine(testsRoot, "Game.Godot");
        Directory.CreateDirectory(realRuntime);
        Directory.CreateDirectory(testsRoot);
        File.WriteAllText(Path.Combine(realRuntime, "Main.tscn"), "[gd_scene]\n");

        var junctionCreated = TryCreateJunction(junctionPath, realRuntime);
        if (!junctionCreated)
        {
            return;
        }

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = sourceRoot
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        var seeder = new ProjectWorkspaceSeeder(options);

        seeder.EnsureSeeded(targetRepo);

        Directory.Exists(Path.Combine(targetRepo, "Game.Godot")).Should().BeTrue();
        Directory.Exists(Path.Combine(targetRepo, "Tests.Godot")).Should().BeTrue();
        Directory.Exists(Path.Combine(targetRepo, "Tests.Godot", "Game.Godot")).Should().BeFalse();
    }

    private static bool TryCreateJunction(string junctionPath, string targetPath)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = "cmd.exe",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        startInfo.ArgumentList.Add("/c");
        startInfo.ArgumentList.Add("mklink");
        startInfo.ArgumentList.Add("/J");
        startInfo.ArgumentList.Add(junctionPath);
        startInfo.ArgumentList.Add(targetPath);

        using var process = Process.Start(startInfo);
        process!.WaitForExit(10_000);
        return process.ExitCode == 0;
    }

    private sealed class TempDirectory : IDisposable
    {
        private TempDirectory(string path)
        {
            Path = path;
        }

        public string Path { get; }

        public static TempDirectory Create(string prefix)
        {
            var path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"{prefix}-{Guid.NewGuid():N}");
            Directory.CreateDirectory(path);
            return new TempDirectory(path);
        }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                RemoveReparseDirectories(Path);
                Directory.Delete(Path, recursive: true);
            }
        }

        private static void RemoveReparseDirectories(string root)
        {
            foreach (var directory in Directory.EnumerateDirectories(root, "*", SearchOption.AllDirectories)
                         .OrderByDescending(path => path.Length))
            {
                if ((File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0)
                {
                    Directory.Delete(directory, recursive: false);
                }
            }
        }
    }
}
