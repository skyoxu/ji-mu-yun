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
        Directory.CreateDirectory(Path.Combine(sourceRoot, "_bmad", "scripts"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "_bmad", "gds"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, ".agents", "skills", "prototype-rpg-godot-zh"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, ".agents", "skills", "bmad-agent-game-designer"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "docs", "prototype-type-kits"));
        File.WriteAllText(Path.Combine(sourceRoot, "scripts", "python", "run_prototype_workflow.py"), "new workflow\n");
        File.WriteAllText(Path.Combine(sourceRoot, "_bmad", "scripts", "resolve_customization.py"), "new resolver\n");
        File.WriteAllText(Path.Combine(sourceRoot, "_bmad", "gds", "config.yaml"), "new config\n");
        File.WriteAllText(Path.Combine(sourceRoot, ".agents", "skills", "prototype-rpg-godot-zh", "SKILL.md"), "new skill\n");
        File.WriteAllText(Path.Combine(sourceRoot, ".agents", "skills", "bmad-agent-game-designer", "SKILL.md"), "new bmad skill\n");
        File.WriteAllText(Path.Combine(sourceRoot, "docs", "prototype-type-kits", "rpg.md"), "new manifest\n");

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = sourceRoot
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        Directory.CreateDirectory(Path.Combine(targetRepo, "scripts", "python"));
        Directory.CreateDirectory(Path.Combine(targetRepo, "_bmad", "scripts"));
        Directory.CreateDirectory(Path.Combine(targetRepo, "_bmad", "gds"));
        Directory.CreateDirectory(Path.Combine(targetRepo, ".agents", "skills", "prototype-rpg-godot-zh"));
        Directory.CreateDirectory(Path.Combine(targetRepo, ".agents", "skills", "gds-edit-gdd"));
        Directory.CreateDirectory(Path.Combine(targetRepo, ".agents", "skills", "project-custom-skill"));
        Directory.CreateDirectory(Path.Combine(targetRepo, "docs", "prototype-type-kits"));
        File.WriteAllText(Path.Combine(targetRepo, "scripts", "python", "run_prototype_workflow.py"), "old workflow\n");
        File.WriteAllText(Path.Combine(targetRepo, "_bmad", "scripts", "resolve_customization.py"), "old resolver\n");
        File.WriteAllText(Path.Combine(targetRepo, "_bmad", "gds", "config.yaml"), "old config\n");
        File.WriteAllText(Path.Combine(targetRepo, ".agents", "skills", "prototype-rpg-godot-zh", "SKILL.md"), "old skill\n");
        File.WriteAllText(Path.Combine(targetRepo, ".agents", "skills", "gds-edit-gdd", "SKILL.md"), "retired skill\n");
        File.WriteAllText(Path.Combine(targetRepo, ".agents", "skills", "project-custom-skill", "SKILL.md"), "custom skill\n");
        File.WriteAllText(Path.Combine(targetRepo, "docs", "prototype-type-kits", "rpg.md"), "old manifest\n");
        File.WriteAllText(Path.Combine(targetRepo, "README.md"), "keep local file\n");

        var seeder = new ProjectWorkspaceSeeder(options);

        seeder.EnsureSeeded(targetRepo);

        File.ReadAllText(Path.Combine(targetRepo, "scripts", "python", "run_prototype_workflow.py")).Should().Be("new workflow\n");
        File.ReadAllText(Path.Combine(targetRepo, "_bmad", "scripts", "resolve_customization.py")).Should().Be("new resolver\n");
        File.ReadAllText(Path.Combine(targetRepo, "_bmad", "gds", "config.yaml")).Should().Be("old config\n");
        File.ReadAllText(Path.Combine(targetRepo, ".agents", "skills", "prototype-rpg-godot-zh", "SKILL.md")).Should().Be("new skill\n");
        File.ReadAllText(Path.Combine(targetRepo, ".agents", "skills", "bmad-agent-game-designer", "SKILL.md")).Should().Be("new bmad skill\n");
        Directory.Exists(Path.Combine(targetRepo, ".agents", "skills", "gds-edit-gdd")).Should().BeFalse();
        File.ReadAllText(Path.Combine(targetRepo, ".agents", "skills", "project-custom-skill", "SKILL.md")).Should().Be("custom skill\n");
        File.ReadAllText(Path.Combine(targetRepo, "docs", "prototype-type-kits", "rpg.md")).Should().Be("new manifest\n");
        File.ReadAllText(Path.Combine(targetRepo, "README.md")).Should().Be("keep local file\n");
        File.Exists(Path.Combine(targetRepo, "logs", ".gdignore")).Should().BeTrue();
    }

    [Fact]
    public void EnsureSeeded_CopiesGdsConfigWhenExistingWorkspaceIsMissingIt()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        Directory.CreateDirectory(Path.Combine(source.Path, "_bmad", "gds"));
        File.WriteAllText(Path.Combine(source.Path, "_bmad", "gds", "config.yaml"), "project_name: template\n");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = source.Path
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        Directory.CreateDirectory(targetRepo);
        File.WriteAllText(Path.Combine(targetRepo, "README.md"), "existing workspace\n");

        new ProjectWorkspaceSeeder(options).EnsureSeeded(targetRepo);

        File.ReadAllText(Path.Combine(targetRepo, "_bmad", "gds", "config.yaml")).Should().Be("project_name: template\n");
    }

    [Fact]
    public void EnsureSeeded_RestoresBootstrapBaselineIntoNonEmptyWorkspace()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        var sourceRoot = source.Path;
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Game.Core.Tests"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "scripts", "python"));
        File.WriteAllText(Path.Combine(sourceRoot, "AGENTS.md"), "source agents\n");
        File.WriteAllText(Path.Combine(sourceRoot, "README.md"), "source readme\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.sln"), "source solution\n");
        File.WriteAllText(Path.Combine(sourceRoot, "project.godot"), "source project\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Core.Tests", "Game.Core.Tests.csproj"), "<Project />\n");
        File.WriteAllText(Path.Combine(sourceRoot, "scripts", "python", "project_health_scan.py"), "print('ok')\n");

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = sourceRoot
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        Directory.CreateDirectory(Path.Combine(targetRepo, "scripts", "python"));
        File.WriteAllText(Path.Combine(targetRepo, "scripts", "python", "project_health_scan.py"), "existing helper\n");
        File.WriteAllText(Path.Combine(targetRepo, "local-note.txt"), "keep me\n");

        var seeder = new ProjectWorkspaceSeeder(options);

        seeder.EnsureSeeded(targetRepo);

        File.ReadAllText(Path.Combine(targetRepo, "AGENTS.md")).Should().Be("source agents\n");
        File.ReadAllText(Path.Combine(targetRepo, "README.md")).Should().Be("source readme\n");
        File.ReadAllText(Path.Combine(targetRepo, "Game.sln")).Should().Be("source solution\n");
        File.ReadAllText(Path.Combine(targetRepo, "project.godot")).Should().Be("source project\n");
        File.ReadAllText(Path.Combine(targetRepo, "Game.Core.Tests", "Game.Core.Tests.csproj")).Should().Be("<Project />\n");
        File.ReadAllText(Path.Combine(targetRepo, "scripts", "python", "project_health_scan.py")).Should().Be("print('ok')\n");
        File.ReadAllText(Path.Combine(targetRepo, "local-note.txt")).Should().Be("keep me\n");
    }

    [Fact]
    public void EnsureSeeded_ResumesIncompleteBootstrapWhenBaselineFilesAlreadyExist()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        var baselineFiles = new[]
        {
            "AGENTS.md",
            "README.md",
            "Game.sln",
            "project.godot",
            "Game.Core.Tests/Game.Core.Tests.csproj"
        };
        foreach (var relativePath in baselineFiles)
        {
            var sourcePath = Path.Combine(source.Path, relativePath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(sourcePath)!);
            File.WriteAllText(sourcePath, $"source:{relativePath}\n");
        }
        var ordinarySourcePath = Path.Combine(source.Path, "Game.Core", "OrdinarySource.cs");
        Directory.CreateDirectory(Path.GetDirectoryName(ordinarySourcePath)!);
        File.WriteAllText(ordinarySourcePath, "// ordinary source\n");

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = source.Path
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        foreach (var relativePath in baselineFiles)
        {
            var targetPath = Path.Combine(targetRepo, relativePath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(targetPath)!);
            File.WriteAllText(targetPath, $"existing:{relativePath}\n");
        }

        new ProjectWorkspaceSeeder(options).EnsureSeeded(targetRepo);

        File.ReadAllText(Path.Combine(targetRepo, "Game.Core", "OrdinarySource.cs"))
            .Should().Be("// ordinary source\n");
        File.Exists(Path.Combine(targetRepo, ".phasea-seed-complete")).Should().BeTrue();
    }

    [Fact]
    public void EnsureSeeded_CreatesLogsGdignoreForFreshWorkspace()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        var sourceRoot = source.Path;
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Game.Godot"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Tests.Godot"));

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = sourceRoot
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        var seeder = new ProjectWorkspaceSeeder(options);

        seeder.EnsureSeeded(targetRepo);

        File.Exists(Path.Combine(targetRepo, "logs", ".gdignore")).Should().BeTrue();
    }

    [Fact]
    public void EnsureSeeded_DoesNotCopyGameTypeGuidesIntoHostedWorkspace()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        var sourceRoot = source.Path;
        Directory.CreateDirectory(Path.Combine(sourceRoot, "docs", "game-type-guides"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "docs", "prototype-type-kits"));
        File.WriteAllText(Path.Combine(sourceRoot, "docs", "game-type-guides", "rpg.md"), "guide\n");
        File.WriteAllText(Path.Combine(sourceRoot, "docs", "prototype-type-kits", "rpg.md"), "kit\n");

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = sourceRoot
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        var seeder = new ProjectWorkspaceSeeder(options);

        seeder.EnsureSeeded(targetRepo);

        Directory.Exists(Path.Combine(targetRepo, "docs", "game-type-guides")).Should().BeFalse();
        File.Exists(Path.Combine(targetRepo, "docs", "prototype-type-kits", "rpg.md")).Should().BeTrue();
    }

    [Fact]
    public void EnsureSeeded_SkipsDotnetToolCache_WhenWorkspaceHasPartialResidualFiles()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        var sourceRoot = source.Path;
        var sourceToolCache = Path.Combine(sourceRoot, ".dotnet", "sdk", "8.0.401", "DotnetTools", "dotnet-format");
        Directory.CreateDirectory(sourceToolCache);
        File.WriteAllText(Path.Combine(sourceRoot, "README.md"), "source readme\n");
        File.WriteAllText(Path.Combine(sourceToolCache, "Microsoft.Extensions.Logging.Abstractions.dll"), "source dll\n");

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = sourceRoot
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        var residualToolCache = Path.Combine(targetRepo, ".dotnet", "sdk", "8.0.401", "DotnetTools", "dotnet-format");
        Directory.CreateDirectory(residualToolCache);
        File.WriteAllText(Path.Combine(residualToolCache, "Microsoft.Extensions.Logging.Abstractions.dll"), "residual dll\n");

        var seeder = new ProjectWorkspaceSeeder(options);

        seeder.EnsureSeeded(targetRepo);

        File.ReadAllText(Path.Combine(targetRepo, "README.md")).Should().Be("source readme\n");
        File.ReadAllText(Path.Combine(residualToolCache, "Microsoft.Extensions.Logging.Abstractions.dll")).Should().Be("residual dll\n");
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
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Game.Core", "buildcache", "int", "Debug", "net8.0"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Game.Core.Tests", "Prototypes"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Game.Core.Tests", "buildcache", "int", "Debug", "net8.0"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Tests.Godot", "tests", "Prototype", "DefaultRpgPrototype"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "docs", "prototypes"));

        File.WriteAllText(Path.Combine(sourceRoot, "Game.Godot", "Prototypes", "DefaultRpgTemplate", "DefaultRpgPrototype.tscn"), "[gd_scene]\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn"), "[gd_scene]\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Core", "Prototypes", "DefaultRpgPrototypeLoop.cs"), "default\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Core", "Prototypes", "DqRpgPrototypeLoop.cs"), "generated\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Core", "buildcache", "int", "Debug", "net8.0", "Game.Core.AssemblyInfo.cs"), "generated assembly info\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Core.Tests", "Prototypes", "DefaultRpgPrototypeLoopTests.cs"), "default test\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs"), "generated test\n");
        File.WriteAllText(Path.Combine(sourceRoot, "Game.Core.Tests", "buildcache", "int", "Debug", "net8.0", "Game.Core.Tests.AssemblyInfo.cs"), "generated test assembly info\n");
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
        Directory.Exists(Path.Combine(targetRepo, "Game.Core", "buildcache")).Should().BeFalse();
        File.Exists(Path.Combine(targetRepo, "Game.Core.Tests", "Prototypes", "DefaultRpgPrototypeLoopTests.cs")).Should().BeTrue();
        File.Exists(Path.Combine(targetRepo, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs")).Should().BeFalse();
        Directory.Exists(Path.Combine(targetRepo, "Game.Core.Tests", "buildcache")).Should().BeFalse();
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

    [Fact]
    public void EnsureSeeded_SkipsLockedGdUnitFiles_ButContinuesSync()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        var sourceRoot = source.Path;
        Directory.CreateDirectory(Path.Combine(sourceRoot, "Tests.Godot", "addons", "gdUnit4", "src"));
        Directory.CreateDirectory(Path.Combine(sourceRoot, "docs", "prototype-type-kits"));
        File.WriteAllText(Path.Combine(sourceRoot, "Tests.Godot", "addons", "gdUnit4", "src", "LockedSuite.gd"), "new suite\n");
        File.WriteAllText(Path.Combine(sourceRoot, "docs", "prototype-type-kits", "rpg.md"), "new manifest\n");

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = sourceRoot
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        Directory.CreateDirectory(Path.Combine(targetRepo, "Tests.Godot", "addons", "gdUnit4", "src"));
        Directory.CreateDirectory(Path.Combine(targetRepo, "docs", "prototype-type-kits"));
        File.WriteAllText(Path.Combine(targetRepo, "Tests.Godot", "addons", "gdUnit4", "src", "LockedSuite.gd"), "old suite\n");
        File.WriteAllText(Path.Combine(targetRepo, "docs", "prototype-type-kits", "rpg.md"), "old manifest\n");

        var seeder = new ProjectWorkspaceSeeder(options);
        var lockedPath = Path.Combine(targetRepo, "Tests.Godot", "addons", "gdUnit4", "src", "LockedSuite.gd");
        using (var lockedHandle = new FileStream(
                   lockedPath,
                   FileMode.Open,
                   FileAccess.Read,
                   FileShare.None))
        {
            seeder.EnsureSeeded(targetRepo);
        }

        File.ReadAllText(lockedPath).Should().Be("old suite\n");
        File.ReadAllText(Path.Combine(targetRepo, "docs", "prototype-type-kits", "rpg.md")).Should().Be("new manifest\n");
    }

    [Fact]
    public async Task EnsureSeeded_SerializesConcurrentInitializationOfSameWorkspace()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        Directory.CreateDirectory(Path.Combine(source.Path, "Game.Core"));
        for (var index = 0; index < 200; index++)
        {
            File.WriteAllText(
                Path.Combine(source.Path, "Game.Core", $"Seed-{index:000}.cs"),
                $"// seed {index}\n");
        }
        File.WriteAllText(Path.Combine(source.Path, "AGENTS.md"), "agents\n");
        File.WriteAllText(Path.Combine(source.Path, "README.md"), "readme\n");

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = source.Path
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        using var start = new ManualResetEventSlim(false);
        var tasks = Enumerable.Range(0, 8)
            .Select(_ => Task.Run(() =>
            {
                start.Wait();
                new ProjectWorkspaceSeeder(options).EnsureSeeded(targetRepo);
            }))
            .ToArray();

        start.Set();
        await Task.WhenAll(tasks);

        File.ReadAllText(Path.Combine(targetRepo, "README.md")).Should().Be("readme\n");
        Directory.EnumerateFiles(Path.Combine(targetRepo, "Game.Core"), "Seed-*.cs").Should().HaveCount(200);
    }

    [Fact]
    public async Task EnsureSeeded_AtomicallyReplacesManagedFilesWhileWorkspaceIsBeingRead()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        var sourceScripts = Path.Combine(source.Path, "scripts");
        Directory.CreateDirectory(sourceScripts);
        var sourcePath = Path.Combine(sourceScripts, "atomic-read.bin");
        var oldContent = Enumerable.Repeat((byte)'A', 2 * 1024 * 1024).ToArray();
        var newContent = Enumerable.Repeat((byte)'B', 2 * 1024 * 1024).ToArray();
        File.WriteAllBytes(sourcePath, newContent);

        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = source.Path
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        var targetPath = Path.Combine(targetRepo, "scripts", "atomic-read.bin");
        Directory.CreateDirectory(Path.GetDirectoryName(targetPath)!);
        File.WriteAllBytes(targetPath, oldContent);
        var invalidReadObserved = 0;
        using var stop = new CancellationTokenSource();
        var reader = Task.Run(() =>
        {
            while (!stop.IsCancellationRequested)
            {
                using var stream = new FileStream(
                    targetPath,
                    FileMode.Open,
                    FileAccess.Read,
                    FileShare.ReadWrite | FileShare.Delete);
                using var buffer = new MemoryStream();
                stream.CopyTo(buffer);
                var observed = buffer.ToArray();
                if (!observed.AsSpan().SequenceEqual(oldContent) && !observed.AsSpan().SequenceEqual(newContent))
                {
                    Interlocked.Exchange(ref invalidReadObserved, 1);
                    return;
                }
            }
        });

        await Task.WhenAll(Enumerable.Range(0, 12).Select(_ => Task.Run(() =>
            new ProjectWorkspaceSeeder(options).EnsureSeeded(targetRepo))));
        stop.Cancel();
        await reader;

        invalidReadObserved.Should().Be(0);
        new ProjectWorkspaceSeeder(options).EnsureSeeded(targetRepo);
        File.ReadAllBytes(targetPath).Should().Equal(newContent);
    }

    [Fact]
    public void EnsureSeeded_DoesNotMarkWorkspaceCompleteWhenCriticalManagedFileIsLocked()
    {
        using var source = TempDirectory.Create("phase-a-source");
        using var workspace = TempDirectory.Create("phase-a-workspaces");
        File.WriteAllText(Path.Combine(source.Path, "Directory.Build.props"), "new props\n");
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspace.Path,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspace.Path, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = source.Path
        });
        var targetRepo = Path.Combine(workspace.Path, "account", "project", "repo");
        Directory.CreateDirectory(targetRepo);
        var targetPath = Path.Combine(targetRepo, "Directory.Build.props");
        File.WriteAllText(targetPath, "old props\n");
        using var locked = new FileStream(targetPath, FileMode.Open, FileAccess.Read, FileShare.Read);

        var act = () => new ProjectWorkspaceSeeder(options).EnsureSeeded(targetRepo);

        act.Should().Throw<IOException>();
        File.Exists(Path.Combine(targetRepo, ".phasea-seed-complete")).Should().BeFalse();
        File.ReadAllText(targetPath).Should().Be("old props\n");
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
