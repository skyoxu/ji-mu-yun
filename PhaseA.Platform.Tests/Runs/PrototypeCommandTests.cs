using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeCommandTests
{
    [Fact]
    public void BuildTdd_IncludesStageAndConfiguredGodotBin()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = @"C:\repo",
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
        var builder = new PrototypeCommandBuilder(options);

        var command = builder.BuildTdd(new PrototypeTddRequest(
            "demo",
            "red",
            Expect: "fail",
            Filter: "DemoFilter",
            TimeoutSec: 30,
            DotnetTarget: ["Game.Core.Tests/Game.Core.Tests.csproj"],
            GdunitPath: ["tests/Prototype/Demo"]), @"C:\project-repo");

        command.WorkingDirectory.Should().Be(@"C:\project-repo");
        command.Arguments.Should().ContainInOrder(
            "-3",
            "scripts/python/dev_cli.py",
            "run-prototype-tdd",
            "--slug",
            "demo",
            "--stage",
            "red",
            "--expect",
            "fail",
            "--filter",
            "DemoFilter",
            "--dotnet-target",
            "Game.Core.Tests/Game.Core.Tests.csproj",
            "--gdunit-path",
            "tests/Prototype/Demo",
            "--timeout-sec",
            "30",
            "--godot-bin",
            @"C:\Godot\Godot.exe");
        command.Environment["GODOT_BIN"].Should().Be(@"C:\Godot\Godot.exe");
    }

    [Fact]
    public void BuildScene_IncludesPrototypeOnlyEngineRecommendationArgs()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = @"C:\repo",
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
        var builder = new PrototypeCommandBuilder(options);

        var command = builder.BuildScene(
            new PrototypeSceneRequest(
                "physics-lab",
                SceneRoot: "Node2D",
                PrototypeRoot: "Game.Godot/Prototypes",
                EngineBackend: "rapier_2d",
                EngineApplyMode: "confirm_apply",
                EngineConfidence: "medium",
                EngineReason: "Prototype needs stronger 2D collision feel.",
                EngineRequiresPlugin: true,
                EngineInstallTarget: "project_local_addon"),
            @"C:\project-repo");

        command.Arguments.Should().ContainInOrder(
            "-3",
            "scripts/python/dev_cli.py",
            "create-prototype-scene",
            "--slug",
            "physics-lab",
            "--scene-root",
            "Node2D",
            "--prototype-root",
            "Game.Godot/Prototypes",
            "--engine-backend",
            "rapier_2d",
            "--engine-apply-mode",
            "confirm_apply",
            "--engine-confidence",
            "medium",
            "--engine-reason",
            "Prototype needs stronger 2D collision feel.",
            "--engine-requires-plugin",
            "true",
            "--engine-install-target",
            "project_local_addon");
    }

    [Fact]
    public void BuildScene_InfersEngineRecommendationFromPrototypeIntake()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = @"C:\repo",
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
        var builder = new PrototypeCommandBuilder(options);

        var command = builder.BuildScene(
            new PrototypeSceneRequest(
                "physics-lab",
                MinimumPlayableLoop: "2D platform movement with gravity, collision, replay, and deterministic physics feel.",
                GameFeature: "Strong collision feel and rollback-friendly simulation."),
            @"C:\project-repo");

        command.Arguments.Should().ContainInOrder(
            "--engine-backend",
            "rapier_2d",
            "--engine-apply-mode",
            "confirm_apply",
            "--engine-confidence",
            "medium",
            "--engine-requires-plugin",
            "true",
            "--engine-install-target",
            "project_local_addon");
    }

    [Fact]
    public void BuildScene_DoesNotSendEngineRecommendation_WhenIntakeIsEmpty()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = @"C:\repo",
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
        var builder = new PrototypeCommandBuilder(options);

        var command = builder.BuildScene(new PrototypeSceneRequest("physics-lab"), @"C:\project-repo");

        command.Arguments.Should().NotContain("--engine-backend");
        command.Arguments.Should().NotContain("--engine-requires-plugin");
        command.Arguments.Should().NotContain("--engine-install-target");
    }

    [Fact]
    public void BuildScene_DoesNotSendEngineRecommendation_WhenOnlyGameTypeIsPresent()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = @"C:\repo",
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
        var builder = new PrototypeCommandBuilder(options);

        var command = builder.BuildScene(
            new PrototypeSceneRequest("rpg-loop", GameType: "rpg"),
            @"C:\project-repo");

        command.Arguments.Should().NotContain("--engine-backend");
        command.Arguments.Should().NotContain("--engine-requires-plugin");
        command.Arguments.Should().NotContain("--engine-install-target");
    }

    [Fact]
    public void BuildScene_DoesNotTreatRpgMovementAsPhysicsBackendNeed()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = @"C:\repo",
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
        var builder = new PrototypeCommandBuilder(options);

        var command = builder.BuildScene(
            new PrototypeSceneRequest(
                "rpg-loop",
                GameType: "rpg",
                MinimumPlayableLoop: "Player movement through a village, dialogue, menu choice, and quest state feedback."),
            @"C:\project-repo");

        command.Arguments.Should().ContainInOrder(
            "--engine-backend",
            "none",
            "--engine-apply-mode",
            "recommend_only",
            "--engine-confidence",
            "medium");
    }

    [Fact]
    public void BuildScene_DoesNotTreat3dMovementOnlyAsJoltNeed()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["PHASEA_REPOSITORY_ROOT"] = @"C:\repo",
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
        var builder = new PrototypeCommandBuilder(options);

        var command = builder.BuildScene(
            new PrototypeSceneRequest(
                "walk-loop",
                GameType: "adventure",
                MinimumPlayableLoop: "3D movement through a small room with camera look and dialogue interaction."),
            @"C:\project-repo");

        command.Arguments.Should().ContainInOrder(
            "--engine-backend",
            "none",
            "--engine-apply-mode",
            "recommend_only",
            "--engine-confidence",
            "low");
    }

    [Theory]
    [InlineData("red")]
    [InlineData("green")]
    [InlineData("refactor")]
    public void MissingTddFields_AcceptsExplicitStages(string stage)
    {
        var missing = PrototypeCommandValidation.MissingTddFields(new PrototypeTddRequest("demo", stage));

        missing.Should().BeEmpty();
    }

    [Fact]
    public async Task RunTddAsync_CapturesOutput_IndexesTddArtifacts_AndReleasesLock()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new FakeHostedProcessRunner("demo");
        var service = Service(store, options, runner);

        var result = await service.RunTddAsync(accountId, projectId, new PrototypeTddRequest("demo", "green"));
        var second = await service.CreateSceneAsync(accountId, projectId, new PrototypeSceneRequest("demo"));

        result.Status.Should().Be("succeeded");
        result.Artifacts.Select(a => a.ArtifactType).Should().Contain(["prototype-tdd-summary", "prototype-tdd-report", "prototype-sidecar-json"]);
        result.Stdout.Should().Contain("command ok");
        second.Status.Should().Be("succeeded");
    }

    [Fact]
    public async Task CreateSceneAsync_TreatsExistingScaffoldRefreshAsSucceeded()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var runner = new StaticHostedProcessRunner(new HostedProcessResult(
            1,
            "",
            "PROTOTYPE_SCENE ERROR: scaffold already exists for slug=demo; pass --force to overwrite.\n"));
        var service = Service(store, options, runner);

        var result = await service.CreateSceneAsync(accountId, projectId, new PrototypeSceneRequest(
            "demo",
            EngineBackend: "godot_physics_2d",
            EngineApplyMode: "recommend_only"));

        result.Status.Should().Be("succeeded");
        result.ExitCode.Should().Be(0);
        result.Stdout.Should().Contain("reason=prototype_scaffold_already_exists");
        result.Stdout.Should().Contain("metadata=preserved_or_refreshed");
        result.Stdout.Should().NotContain("metadata=refreshed");
        result.Stderr.Should().BeEmpty();
    }

    [Fact]
    public async Task RunTddAsync_ReturnsBlocked_WhenProjectRunnerLockIsHeld()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectWithAccountAsync(store, options);
        var existingRunId = await store.CreateRunAsync(projectId, null, "prototype-tdd-red");
        (await store.TryAcquireRunnerLockAsync(projectId, existingRunId)).Should().BeTrue();
        var service = Service(store, options, new FakeHostedProcessRunner("demo"));

        var result = await service.RunTddAsync(accountId, projectId, new PrototypeTddRequest("demo", "red"));

        result.Status.Should().Be("blocked");
        result.ExitCode.Should().Be(423);
        result.Stderr.Should().Contain("runner lock already held");
    }

    private static async Task<PhaseAMetadataStore> CreateStoreAsync(string connectionString, PhaseAPlatformOptions options)
    {
        await SqliteMetadataSchema.InitializeAsync(connectionString);
        var store = new PhaseAMetadataStore(connectionString, options);
        await store.EnsureSingleAdminAsync();
        return store;
    }

    private static async Task<(string AccountId, string ProjectId)> CreateProjectWithAccountAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options)
    {
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "manual", null, null, null, null));
        return (accountId, result.ProjectId!);
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options)
    {
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "manual", null, null, null, null));
        return result.ProjectId!;
    }

    private static PrototypeCommandService Service(PhaseAMetadataStore store, PhaseAPlatformOptions options, IHostedProcessRunner runner)
    {
        return new PrototypeCommandService(
            store,
            options,
            runner,
            new PrototypeCommandBuilder(options),
            new PrototypeTddArtifactIndexer());
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot,
            ["GODOT_BIN"] = @"C:\Godot\Godot.exe"
        });
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        private readonly string _slug;

        public FakeHostedProcessRunner(string slug)
        {
            _slug = slug;
        }

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var tddDir = Path.Combine(command.WorkingDirectory, "logs", "ci", "2026-05-11", $"prototype-tdd-{_slug}-green");
            Directory.CreateDirectory(tddDir);
            File.WriteAllText(Path.Combine(tddDir, "summary.json"), "{}");
            File.WriteAllText(Path.Combine(tddDir, "report.md"), "report");
            var sidecar = Path.Combine(command.WorkingDirectory, "docs", "prototypes", $"{_slug}.prototype.json");
            Directory.CreateDirectory(Path.GetDirectoryName(sidecar)!);
            File.WriteAllText(sidecar, "{}");
            return Task.FromResult(new HostedProcessResult(0, "command ok\n", ""));
        }
    }

    private sealed class StaticHostedProcessRunner : IHostedProcessRunner
    {
        private readonly HostedProcessResult _result;

        public StaticHostedProcessRunner(HostedProcessResult result)
        {
            _result = result;
        }

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(_result);
        }
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
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
