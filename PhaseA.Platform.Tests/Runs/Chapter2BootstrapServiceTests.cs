using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class Chapter2BootstrapServiceTests
{
    [Fact]
    public async Task RunAsync_CreatesRunRecord_CapturesOutput_AndIndexesProjectHealthArtifacts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner([
            new HostedProcessResult(0, "hard checks ok\n", "")
        ], writeProjectHealth: true);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId);

        result.Status.Should().Be("succeeded");
        result.ExitCode.Should().Be(0);
        result.Stdout.Should().Contain("hard checks ok");
        result.Artifacts.Select(a => a.RelativePath).Should().Contain([
            "logs/ci/project-health/latest.html",
            "logs/ci/project-health/latest.json",
            "logs/ci/project-health/project-health-scan.latest.json"
        ]);

        var run = await store.GetRunSnapshotAsync(result.RunId);
        run.Should().NotBeNull();
        run!.RunType.Should().Be("chapter2-bootstrap");
        run.Status.Should().Be("succeeded");
        run.ExitCode.Should().Be(0);
        run.StdoutText.Should().Contain("hard checks ok");
        run.EvidenceJson.Should().Contain("project_health_artifacts");
        runner.CallCount.Should().Be(1);
    }

    [Fact]
    public async Task RunAsync_MarksRunFailed_WhenHardChecksFail()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner([
            new HostedProcessResult(7, "", "hard checks failed\n")
        ]);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId);

        result.Status.Should().Be("failed");
        result.ExitCode.Should().Be(7);
        result.Stderr.Should().Contain("hard checks failed");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("failed");
        run.StderrText.Should().Contain("hard checks failed");
        runner.CallCount.Should().Be(1);
    }

    [Fact]
    public async Task RunAsync_ReturnsExistingSuccess_WhenChapter2AlreadySucceeded()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        WriteProjectHealthArtifacts(repoRoot.Path);
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new FakeHostedProcessRunner([
            new HostedProcessResult(0, "hard checks ok\n", "")
        ]);
        var service = Service(store, options, runner);
        var first = await service.RunAsync(projectId);

        var second = await service.RunAsync(projectId);

        second.Status.Should().Be("already_succeeded");
        second.RunId.Should().Be(first.RunId);
        runner.CallCount.Should().Be(1);
        var runs = await store.ListRunsForProjectAsync(projectId);
        runs.Where(run => run.RunType == "chapter2-bootstrap").Should().ContainSingle();
    }

    [Fact]
    public async Task RunAsync_ReturnsBlocked_WhenProjectRunnerLockIsHeld()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var existingRunId = await store.CreateRunAsync(projectId, null, "prototype-tdd-red");
        (await store.TryAcquireRunnerLockAsync(projectId, existingRunId)).Should().BeTrue();
        var runner = new FakeHostedProcessRunner([
            new HostedProcessResult(0, "hard checks ok\n", "")
        ]);
        var service = Service(store, options, runner);

        var result = await service.RunAsync(projectId);

        result.Status.Should().Be("blocked");
        result.ExitCode.Should().Be(423);
        runner.CallCount.Should().Be(0);
        var runs = await store.ListRunsForProjectAsync(projectId);
        runs.Should().Contain(run => run.RunType == "chapter2-bootstrap" && run.Status == "blocked");
    }

    [Fact]
    public async Task RunAsync_TimesOutAndReleasesRunnerLock()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        var store = await CreateStoreAsync(database.ConnectionString, options);
        var projectId = await CreateProjectAsync(store, options);
        var runner = new HangingHostedProcessRunner();
        var service = new Chapter2BootstrapService(
            store,
            options,
            runner,
            new Chapter2BootstrapCommandBuilder(options),
            new ProjectHealthArtifactIndexer(),
            new ProjectWorkspaceSeeder(options),
            TimeSpan.FromMilliseconds(50));

        var result = await service.RunAsync(projectId);

        result.Status.Should().Be("failed");
        result.ExitCode.Should().Be(124);
        result.Stderr.Should().Contain("timed out");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(124);
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

    private static Chapter2BootstrapService Service(PhaseAMetadataStore store, PhaseAPlatformOptions options, IHostedProcessRunner runner)
    {
        return new Chapter2BootstrapService(
            store,
            options,
            runner,
            new Chapter2BootstrapCommandBuilder(options),
            new ProjectHealthArtifactIndexer());
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot
        });
    }

    private static void WriteProjectHealthArtifacts(string repoRoot)
    {
        var dir = Path.Combine(repoRoot, "logs", "ci", "project-health");
        Directory.CreateDirectory(dir);
        File.WriteAllText(Path.Combine(dir, "latest.html"), "<html></html>");
        File.WriteAllText(Path.Combine(dir, "latest.json"), "{}");
        File.WriteAllText(Path.Combine(dir, "project-health-scan.latest.json"), "{}");
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        private readonly Queue<HostedProcessResult> _results;
        private readonly bool _writeProjectHealth;

        public FakeHostedProcessRunner(IEnumerable<HostedProcessResult> results, bool writeProjectHealth = false)
        {
            _results = new Queue<HostedProcessResult>(results);
            _writeProjectHealth = writeProjectHealth;
        }

        public int CallCount { get; private set; }

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            CallCount++;
            if (_writeProjectHealth)
            {
                WriteProjectHealthArtifacts(command.WorkingDirectory);
            }

            return Task.FromResult(_results.Dequeue());
        }
    }

    private sealed class HangingHostedProcessRunner : IHostedProcessRunner
    {
        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            await Task.Delay(TimeSpan.FromMinutes(5), cancellationToken);
            return new HostedProcessResult(0, "", "");
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
