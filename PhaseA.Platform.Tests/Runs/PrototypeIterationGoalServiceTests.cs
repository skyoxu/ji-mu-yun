using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeIterationGoalServiceTests
{
    [Fact]
    public async Task CreateAsync_ShouldRejectInternalExecutionCompletionSuggestion()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = new PrototypeIterationPlanService(store);

        var result = await planService.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "如果你要我继续收口 Day 4，我下一步会只做环境清理再重跑： dotnet build-server shutdown 然后清掉 obj/tmp 后，再跑 dotnet test。",
                "completion_suggestion"));

        result.Status.Should().Be("suggestion_needs_fix");
        result.SessionId.Should().BeEmpty();
        result.Goals.Should().BeEmpty();
    }

    [Fact]
    public async Task ExecuteNextAsync_RunsSinglePendingGoal_AndPausesForReview()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先修主菜单入口。再修地图移动。最后补提示文案。"));
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var artifacts = await store.ListArtifactsForRunAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.GoalIndex.Should().Be(1);
        result.HasMoreGoals.Should().BeTrue();
        result.SessionStatus.Should().Be("paused_for_review");
        run!.RunType.Should().Be("prototype-iteration-goal");
        run.Status.Should().Be("completed");
        details.Should().NotBeNull();
        details!.Session.Status.Should().Be("paused_for_review");
        details.Goals[0].Status.Should().Be("succeeded");
        details.Goals[1].Status.Should().Be("pending");
        runner.Commands.Should().ContainSingle();
        artifacts.Select(a => a.ArtifactType).Should().Contain([
            "prototype-iteration-goal-input",
            "prototype-iteration-goal-result",
            "prototype-iteration-goal-codex-output"
        ]);
    }

    [Fact]
    public async Task ExecuteNextAsync_MarksGoalNeedsFix_WhenOutputSaysIncomplete()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先修 step1，再做 step2。"));
        var runner = new NeedsFixHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("needs_fix");
        result.SessionStatus.Should().Be("needs_fix");
        details.Should().NotBeNull();
        details!.Goals[0].Status.Should().Be("needs_fix");
        details.Session.Status.Should().Be("needs_fix");
    }

    [Fact]
    public async Task ExecuteNextAsync_MarksGoalNeedsFix_WhenRunnerExitCodeIsNonZero()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Fix the current project page hint first."));
        var runner = new ExitCodeFailureHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("needs_fix");
        result.SessionStatus.Should().Be("needs_fix");
        details.Should().NotBeNull();
        details!.Goals[0].Status.Should().Be("needs_fix");
        details.Session.Status.Should().Be("needs_fix");
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
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
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: 已完成当前目标，并让用户更容易理解接下来该做什么。
CHANGED: Updated the current project page entry hint.
VERIFY: Open the current project page and confirm the hint is visible.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "iteration goal stdout", ""));
        }
    }

    private sealed class NeedsFixHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: 当前目标还没有完成，需要先修复阻塞项。
CHANGED: Investigated the blocker.
VERIFY: Retry after the blocker is cleared.
REMAINING: One blocker still prevents completion.
""");
            return Task.FromResult(new HostedProcessResult(0, "STATUS: needs_fix", ""));
        }
    }

    private sealed class ExitCodeFailureHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
SUMMARY: A blocker interrupted this goal before completion.
CHANGED: Investigated the issue.
VERIFY: Retry after the runner problem is cleared.
REMAINING: The goal is still incomplete.
""");
            return Task.FromResult(new HostedProcessResult(2, "", "runner failed"));
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
