using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeFeedbackIterationServiceTests
{
    [Fact]
    public async Task SubmitAsync_CreatesFormalFeedbackRun_AndDownloadableArtifacts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeFeedbackIterationService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest("Make combat feedback stronger.", "gpt-5.4", "map-making-master"));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var artifacts = await store.ListArtifactsForRunAsync(result.RunId);
        var project = await store.GetProjectSnapshotAsync(projectId);

        result.Status.Should().Be("completed");
        result.AssistantMessage.Should().Contain("本轮继续优化已完成");
        result.AssistantMessage.Should().Contain("Codex changed prototype.");
        result.AssistantMessage.Should().Contain("下一步建议");
        runner.Commands.Should().ContainSingle();
        runner.Commands[0].Arguments.Should().Contain(["exec", "--sandbox", "workspace-write", "-m", "gpt-5.4"]);
        runner.Commands[0].Arguments.Should().Contain(["-c", "model_reasoning_effort=\"high\""]);
        string.Join("\n", runner.Commands[0].Arguments).Should().Contain("地图制作大师").And.Contain("$generate2dmap");
        runner.Commands[0].Environment["PHASEA_CODEX_REASONING_EFFORT"].Should().Be("high");
        run!.RunType.Should().Be("prototype-feedback-iteration");
        run.Status.Should().Be("completed");
        artifacts.Select(a => a.ArtifactType).Should().Contain([
            "prototype-feedback-submission",
            "prototype-feedback-result-log",
            "prototype-feedback-codex-output"
        ]);
        File.Exists(Path.Combine(project!.RepoPath, artifacts[0].RelativePath.Replace('/', Path.DirectorySeparatorChar))).Should().BeTrue();
    }


    [Fact]
    public async Task SubmitAsync_BlocksFormalFeedback_UntilPrototypeWorkflowSucceeded()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: false);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeFeedbackIterationService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest("Make combat feedback stronger.", "gpt-5.4"));

        result.Status.Should().Be("prototype_not_ready");
        result.RunId.Should().BeEmpty();
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task SubmitAsync_BlocksWhenRunnerLockIsHeld()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var lockRunId = await store.CreateRunAsync(projectId, null, "existing-run");
        (await store.TryAcquireRunnerLockAsync(projectId, lockRunId)).Should().BeTrue();
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeFeedbackIterationService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest("Make combat feedback stronger.", "gpt-5.4"));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("project_busy");
        run!.Status.Should().Be("blocked");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task SubmitAsync_MarksRunFailedAndReleasesLock_WhenRunnerThrows()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var runner = new ThrowingHostedProcessRunner();
        var service = new PrototypeFeedbackIterationService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest("Make combat feedback stronger.", "gpt-5.4"));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(500);
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId, bool prototypeSucceeded)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
        if (prototypeSucceeded)
        {
            var runId = await store.CreateRunAsync(result.ProjectId!, null, "prototype-7day-playable");
            await store.MarkRunStartedAsync(runId);
            await store.CompleteRunAsync(runId, "succeeded", 0, "prototype ok", "", "{}");
        }

        return result.ProjectId!;
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

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "Codex changed prototype.");
            return Task.FromResult(new HostedProcessResult(0, "codex stdout", ""));
        }
    }

    private sealed class ThrowingHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            throw new InvalidOperationException("runner failed");
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
