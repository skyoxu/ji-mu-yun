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
        var restoredJunction = Path.Combine(targetRepo, "Tests.Godot", "Game.Godot");
        Directory.Exists(restoredJunction).Should().BeTrue();
        File.GetAttributes(restoredJunction).Should().HaveFlag(FileAttributes.ReparsePoint);
    }

    [Fact]
    public void EnsureSeeded_SyncsManagedWorkflowFilesIntoExistingWorkspace()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        var sourceRoot = source.Path;
        Directory.CreateDirectory(Path.Combine(sourceRoot, "scripts", "python"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, ".agents", "skills", "prototype-rpg-godot-zh"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "docs", "prototype-type-kits"));
        File.WriteAllText(Path.Combine(sourceRoot, "scripts", "python", "run_prototype_workflow.py"), "new workflow\n");
        File.WriteAllText(Path.Combine(sourceRoot, ".agents", "skills", "prototype-rpg-godot-zh", "SKILL.md"), "new skill\n");
        File.WriteAllText(Path.Combine(sourceRoot, "docs", "prototype-type-kits", "rpg.md"), "new manifest\n");

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = sourceRoot
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        Directory.CreateDirectory(Path.Combine(targetRepo, "scripts", "python"));
        Directory.CreateDirectory(Path.Combine(targetRepo, ".agents", "skills", "prototype-rpg-godot-zh"));
        Directory.CreateDirectory(Path.Combine(targetRepo, "docs", "prototype-type-kits"));
        File.WriteAllText(Path.Combine(targetRepo, "scripts", "python", "run_prototype_workflow.py"), "old workflow\n");
        File.WriteAllText(Path.Combine(targetRepo, ".agents", "skills", "prototype-rpg-godot-zh", "SKILL.md"), "old skill\n");
        File.WriteAllText(Path.Combine(targetRepo, "docs", "prototype-type-kits", "rpg.md"), "old manifest\n");
        File.WriteAllText(Path.Combine(targetRepo, "README.md"), "keep local file\n");

        var seeder = new ProjectWorkspaceSeeder(options);

        seeder.EnsureSeeded(targetRepo);

        File.ReadAllText(Path.Combine(targetRepo, "scripts", "python", "run_prototype_workflow.py")).Should().Be("new workflow\n");
        File.ReadAllText(Path.Combine(targetRepo, ".agents", "skills", "prototype-rpg-godot-zh", "SKILL.md")).Should().Be("new skill\n");
        File.ReadAllText(Path.Combine(targetRepo, "docs", "prototype-type-kits", "rpg.md")).Should().Be("new manifest\n");
        File.ReadAllText(Path.Combine(targetRepo, "README.md")).Should().Be("keep local file\n");
    }

    [Fact]
    public void EnsureSeeded_RestoresJunction_WhenSourceContainsMirroredRuntimeDirectory()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        var sourceRoot = source.Path;
        var realRuntime = Path.Combine(sourceRoot, "Game.Godot");
        var mirroredRuntime = Path.Combine(sourceRoot, "Tests.Godot", "Game.Godot");
        Directory.CreateDirectory(realRuntime);
        Directory.CreateDirectory(mirroredRuntime);
        File.WriteAllText(Path.Combine(realRuntime, "Main.tscn"), "[gd_scene]\n");
        File.WriteAllText(Path.Combine(mirroredRuntime, "stale.txt"), "mirror\n");

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(workspace.Path, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = sourceRoot
        });

        var targetRepo = Path.Combine(
            options.HostedWorkspaceRoot,
            "cccccccccccccccccccccccccccccccc",
            "dddddddddddddddddddddddddddddddd",
            "repo");
        var seeder = new ProjectWorkspaceSeeder(options);

        seeder.EnsureSeeded(targetRepo);

        var restoredJunction = Path.Combine(targetRepo, "Tests.Godot", "Game.Godot");
        Directory.Exists(Path.Combine(targetRepo, "Game.Godot")).Should().BeTrue();
        Directory.Exists(restoredJunction).Should().BeTrue();
        File.GetAttributes(restoredJunction).Should().HaveFlag(FileAttributes.ReparsePoint);
        File.Exists(Path.Combine(restoredJunction, "Main.tscn")).Should().BeTrue();
        File.Exists(Path.Combine(restoredJunction, "stale.txt")).Should().BeFalse();
    }

    [Fact]
    public void EnsureSeeded_ExcludesGeneratedPrototypeArtifacts_AndKeepsTemplateBaseline()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        var sourceRoot = source.Path;
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Game.Godot", "Prototypes", "DefaultRpgTemplate"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Game.Godot", "Prototypes", "dq-rpg"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Game.Core", "Prototypes"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Game.Core.Tests", "Prototypes"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Tests.Godot", "tests", "Prototype", "DefaultRpgPrototype"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "docs", "prototypes"));

        File.WriteAllText(Path.Combine(sourceRoot, "Game.Godot", "Prototypes", "DefaultRpgTemplate", "DefaultRpgPrototype.tscn"), "[gd_scene]\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn"), "[gd_scene]\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Core", "Prototypes", "DefaultRpgPrototypeLoop.cs"), "default\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Core", "Prototypes", "DqRpgPrototypeLoop.cs"), "generated\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Core.Tests", "Prototypes", "DefaultRpgPrototypeLoopTests.cs"), "default test\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs"), "generated test\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Tests.Godot", "tests", "Prototype", "DefaultRpgPrototype", "test_default_rpg_prototype_scene.gd"), "default gd\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype", "test_dq_rpg_prototype_scene.gd"), "generated gd\n");
        File.WriteAllText(Path.Combine(sourceRoot, "docs", "prototypes", "README.md"), "readme\n");
        File.WriteAllText(Path.Combine(sourceRoot, "docs", "prototypes", "TEMPLATE.md"), "template\n");
        File.WriteAllText(Path.Combine(sourceRoot, "docs", "prototypes", "2026-05-15-dq-rpg.md"), "generated record\n");

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = sourceRoot
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        var seeder = new ProjectWorkspaceSeeder(options);

        seeder.EnsureSeeded(targetRepo);

        File.Exists(Path.Combine(targetRepo, "Game.Godot", "Prototypes", "DefaultRpgTemplate", "DefaultRpgPrototype.tscn")).Should().BeTrue();
        File.Exists(Path.Combine(targetRepo, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn")).Should().BeFalse();
        File.Exists(Path.Combine(targetRepo, "Game.Core", "Prototypes", "DefaultRpgPrototypeLoop.cs")).Should().BeTrue();
        File.Exists(Path.Combine(targetRepo, "Game.Core", "Prototypes", "DqRpgPrototypeLoop.cs")).Should().BeFalse();
        File.Exists(Path.Combine(targetRepo, "Game.Core.Tests", "Prototypes", "DefaultRpgPrototypeLoopTests.cs")).Should().BeTrue();
        File.Exists(Path.Combine(targetRepo, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs")).Should().BeFalse();
        File.Exists(Path.Combine(targetRepo, "Tests.Godot", "tests", "Prototype", "DefaultRpgPrototype", "test_default_rpg_prototype_scene.gd")).Should().BeTrue();
        File.Exists(Path.Combine(targetRepo, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype", "test_dq_rpg_prototype_scene.gd")).Should().BeFalse();
        File.Exists(Path.Combine(targetRepo, "docs", "prototypes", "README.md")).Should().BeTrue();
        File.Exists(Path.Combine(targetRepo, "docs", "prototypes", "TEMPLATE.md")).Should().BeTrue();
        File.Exists(Path.Combine(targetRepo, "docs", "prototypes", "2026-05-15-dq-rpg.md")).Should().BeFalse();
    }

    [Fact]
    public void EnsureSeeded_PreservesGdUnitBinDirectoryForWorkspaceValidation()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        var sourceRoot = source.Path;
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Tests.Godot", "addons", "gdUnit4", "bin"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Tests.Godot", "addons", "gdUnit4", "src"));
        File.WriteAllText(Path.Combine(sourceRoot, "Tests.Godot", "addons", "gdUnit4", "bin", "GdUnitCmdTool.gd"), "runner\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Tests.Godot", "addons", "gdUnit4", "src", "GdUnitTestSuite.gd"), "suite\n");

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = sourceRoot
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        var seeder = new ProjectWorkspaceSeeder(options);

        seeder.EnsureSeeded(targetRepo);

        File.Exists(Path.Combine(targetRepo, "Tests.Godot", "addons", "gdUnit4", "bin", "GdUnitCmdTool.gd")).Should().BeTrue();
        File.Exists(Path.Combine(targetRepo, "Tests.Godot", "addons", "gdUnit4", "src", "GdUnitTestSuite.gd")).Should().BeTrue();
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
