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
            GdunitPath: ["tests/Prototype/Demo"]));

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
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner(repoRoot.Path, "demo");
        var service = Service(store, options, runner);

        var result = await service.RunTddAsync(projectId, new PrototypeTddRequest("demo", "green"));
        var second = await service.CreateSceneAsync(projectId, new PrototypeSceneRequest("demo"));

        result.Status.Should().Be("succeeded");
        result.Artifacts.Select(a => a.ArtifactType).Should().Contain(["prototype-tdd-summary", "prototype-tdd-report", "prototype-sidecar-json"]);
        result.Stdout.Should().Contain("command ok");
        second.Status.Should().Be("succeeded");
    }

    [Fact]
    public async Task RunTddAsync_ReturnsBlocked_WhenProjectRunnerLockIsHeld()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var existingRunId = await store.CreateRunAsync(projectId, null, "prototype-tdd-red");
        (await store.TryAcquireRunnerLockAsync(projectId, existingRunId)).Should().BeTrue();
        var service = Service(store, options, new FakeHostedProcessRunner(repoRoot.Path, "demo"));

        var result = await service.RunTddAsync(projectId, new PrototypeTddRequest("demo", "red"));

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
        private readonly string _repoRoot;
        private readonly string _slug;

        public FakeHostedProcessRunner(string repoRoot, string slug)
        {
            _repoRoot = repoRoot;
            _slug = slug;
        }

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var tddDir = Path.Combine(_repoRoot, "logs", "ci", "2026-05-11", $"prototype-tdd-{_slug}-green");
            Directory.CreateDirectory(tddDir);
            File.WriteAllText(Path.Combine(tddDir, "summary.json"), "{}");
            File.WriteAllText(Path.Combine(tddDir, "report.md"), "report");
            var sidecar = Path.Combine(_repoRoot, "docs", "prototypes", $"{_slug}.prototype.json");
            Directory.CreateDirectory(Path.GetDirectoryName(sidecar)!);
            File.WriteAllText(sidecar, "{}");
            return Task.FromResult(new HostedProcessResult(0, "command ok\n", ""));
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
