using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeNeedsFixRouteServiceTests
{
    [Fact]
    public async Task RunAsync_ShouldRequirePrototypeState_WhenNoNeedsFixStateExists()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, new SuccessRunner()), new PrototypeRouteStateWriter());

        var result = await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1));

        result.Status.Should().Be("prototype_required");
        result.RunId.Should().BeEmpty();
    }

    [Fact]
    public async Task RunAsync_ShouldConsumeCurrentStepState_AndPersistNeedsFixRouteState()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectWithNeedsFixGoalAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var writer = new PrototypeRouteStateWriter();
        writer.WriteProjectReadme(project!);
        writer.WriteNeedsFixState(project!, 1, new { route = "needs-fix", goal_index = 1, marker = "current-step-only" });
        writer.WriteNeedsFixState(project!, 2, new { route = "needs-fix", goal_index = 2, marker = "wrong-step" });
        var runner = new SuccessRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        var result = await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        result.Status.Should().Be("completed");
        runner.Prompt.Should().Contain("current-step-only");
        runner.Prompt.Should().NotContain("wrong-step");
        writer.ReadLatestNeedsFixState(project!, 1).Should().Contain(result.RunId);
    }

    private static async Task<string> CreateProjectWithNeedsFixGoalAsync(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        string accountId,
        bool prototypeSucceeded)
    {
        var projectService = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await projectService.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        if (prototypeSucceeded)
        {
            var runId = await store.CreateRunAsync(created.ProjectId!, null, "prototype-7day-playable");
            await store.MarkRunStartedAsync(runId);
            await store.CompleteRunAsync(runId, "succeeded", 0, "prototype ok", "", "{}");
        }

        var plan = new PrototypeIterationPlanService(store);
        await plan.CreateAsync(accountId, created.ProjectId!, new PrototypeIterationPlanRequest("1. Stabilize map movement\n2. Finish battle"));
        var details = await store.GetLatestProjectIterationSessionAsync(created.ProjectId!);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "still blocked", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "goal 1 needs fix");
        return created.ProjectId!;
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

    private sealed class SuccessRunner : IHostedProcessRunner
    {
        public string Prompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Prompt = command.Arguments.Last();
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "STATUS: completed\nSUMMARY: Current step completed.\nCHANGED: gameplay\nVERIFY: quick pass\nREMAINING: none\n");
            return Task.FromResult(new HostedProcessResult(0, "ok", ""));
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
