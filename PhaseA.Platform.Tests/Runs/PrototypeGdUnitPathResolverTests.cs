using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeGdUnitPathResolverTests
{
    [Fact]
    public void ExtractGdUnitAddPathsFromRouteStates_ShouldReadExplicitGdUnitFields()
    {
        var state = """
        {
          "gdunit_path": "tests/Prototype/CustomSuite",
          "rpg_gdunit_validation": {
            "gdunit_path": "Tests.Godot/tests/Prototype/TowerdemoPrototype"
          }
        }
        """;

        var paths = PrototypeGdUnitPathResolver.ExtractGdUnitAddPathsFromRouteStates([state]);

        paths.Should().Equal("tests/Prototype/CustomSuite", "tests/Prototype/TowerdemoPrototype");
    }

    [Fact]
    public void ExtractManagedDirectoriesFromRouteStates_ShouldIgnorePathTextOutsideGdUnitFields()
    {
        var state = """
        {
          "summary": "Do not scope tests/Prototype/OldSuite from prose.",
          "notes": ["Tests.Godot/tests/Prototype/AlsoOld should remain prose"],
          "gdunit": {
            "added": ["tests/Prototype/CurrentSuite/test_current.gd"]
          }
        }
        """;

        var directories = PrototypeGdUnitPathResolver.ExtractManagedDirectoriesFromRouteStates([state]);

        directories.Should().Equal("Tests.Godot/tests/Prototype/CurrentSuite");
    }

    [Fact]
    public void ExtractManagedDirectoriesFromRouteStates_ShouldIgnoreIncidentalGdUnitNamedDiagnostics()
    {
        var state = """
        {
          "gdunit_warning_summary": {
            "added": ["tests/Prototype/StaleDiagnosticSuite/test_old.gd"]
          },
          "rpg_gdunit_validation": {
            "added": ["tests/Prototype/CurrentSuite/test_current.gd"]
          }
        }
        """;

        var directories = PrototypeGdUnitPathResolver.ExtractManagedDirectoriesFromRouteStates([state]);

        directories.Should().Equal("Tests.Godot/tests/Prototype/CurrentSuite");
    }

    [Fact]
    public async Task RunRpgGdUnitValidationAsync_ShouldNotFallbackToDefaultSuite_WhenPreferredSuiteIsMissing()
    {
        using var routeProfile = GameTypeRouteProfiles.UseGenericPrototypeRouteOnlyForTesting(true);
        using var repo = TempDirectory.Create("phase-a-repo");
        var defaultSuite = Path.Combine(repo.Path, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype");
        Directory.CreateDirectory(defaultSuite);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = repo.Path,
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
        var project = Project(repo.Path);
        var runner = new RecordingHostedProcessRunner();

        var result = await PrototypeGodotSmokeService.RunRpgGdUnitValidationAsync(
            options,
            runner,
            project,
            "towerdemo",
            ["tests/Prototype/MissingSuite"],
            requireSuite: true);

        result.Required.Should().BeTrue();
        result.Ran.Should().BeFalse();
        result.Passed.Should().BeFalse();
        result.Reason.Should().Be("rpg_gdunit_tests_missing");
        result.GdUnitPath.Should().Be("tests/Prototype/MissingSuite");
        result.AttemptedGdUnitPaths.Should().Contain("tests/Prototype/DqRpgPrototype");
        runner.Commands.Should().BeEmpty();
    }

    private static ProjectSnapshot Project(string repoPath)
    {
        return new ProjectSnapshot(
            "project-1",
            "account-1",
            "Project",
            "Game",
            "rpg",
            "",
            false,
            "[]",
            "ready",
            null,
            "workspace-1",
            repoPath,
            repoPath,
            repoPath,
            Path.Combine(repoPath, "meta"));
    }

    private sealed class RecordingHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            return Task.FromResult(new HostedProcessResult(0, "GDUNIT_DONE rc=0", ""));
        }
    }

    private sealed class TempDirectory : IDisposable
    {
        public TempDirectory(string prefix)
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"{prefix}-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public static TempDirectory Create(string prefix)
        {
            return new TempDirectory(prefix);
        }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
