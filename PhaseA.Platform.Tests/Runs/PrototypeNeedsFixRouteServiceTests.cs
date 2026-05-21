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
    public async Task RunAsync_ShouldUseProjectLevelNeedsFix_WhenNoCurrentRepairGoalExists()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectService = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await projectService.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var plan = new PrototypeIterationPlanService(store);
        await plan.CreateAsync(accountId, created.ProjectId!, new PrototypeIterationPlanRequest("1. Stabilize map movement\n2. Finish battle"));
        var runner = new SuccessRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), new PrototypeRouteStateWriter());

        var result = await route.RunAsync(accountId, created.ProjectId!, new PrototypeNeedsFixRouteRequest(Feedback: "Godot error"));

        result.Status.Should().Be("completed");
        result.RunId.Should().NotBeEmpty();
        result.GoalIndex.Should().Be(0);
        var details = await store.GetLatestProjectIterationSessionAsync(created.ProjectId!);
        details!.Goals[0].Status.Should().Be("pending");
        runner.Prompt.Should().Contain("project-level runtime issue");
        runner.Prompt.Should().Contain("Do not generate or rewrite the iteration plan.");
    }

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
        new PrototypeContractService().WriteFromRequest(project!, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "contract");
        writer.WriteNeedsFixState(project!, 1, new
        {
            route = "needs-fix",
            goal_index = 1,
            marker = "current-step-only",
            summary = string.Concat(Enumerable.Repeat("nested-old-prompt ", 800))
        });
        writer.WriteNeedsFixState(project!, 2, new { route = "needs-fix", goal_index = 2, marker = "wrong-step" });
        var runner = new SuccessRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        var result = await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        result.Status.Should().Be("completed");
        result.Summary.Should().Contain("完成报告");
        result.Summary.Should().Contain("STATUS: completed");
        result.Summary.Should().NotContain("Project README:");
        result.Summary.Should().NotContain("Recovery source consumed:");
        result.Summary.Should().NotContain("Direction lock:");
        result.Summary.Should().NotContain("Current goal:");
        runner.Prompt.Should().Contain("current needs fix step state");
        runner.Prompt.Should().NotContain("wrong-step");
        runner.Prompt.Length.Should().BeLessThan(16000);
        runner.Prompt.Should().Contain("Project README and Recovery source are read-only recovery context, not repair targets.");
        runner.Prompt.Should().Contain("Platform route or recovery tests passing does not prove a gameplay goal is complete.");
        runner.Prompt.Should().Contain("Project prototype contract");
        runner.Prompt.Should().Contain("Every movement increases encounter probability by 10% and encounter must happen within 10 steps.");
        runner.Prompt.Should().Contain("First enemy has 30 HP and 5 ATK.");
        writer.ReadLatestNeedsFixState(project!, 1).Should().Contain(result.RunId);
        writer.ReadLatestNeedsFixState(project!, 1).Should().Contain("prototype_contract");
    }

    [Fact]
    public async Task RunAsync_ShouldConsumeExecuteNextGoalState_WhenNeedsFixStateIsMissing()
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
        writer.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-fallback" });
        writer.WriteExecuteNextGoalState(project!, 1, new { route = "execute-next-goal", goal_index = 1, marker = "execute-next-current-step" });
        var runner = new SuccessRunner();
        var route = new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), writer);

        var result = await route.RunAsync(accountId, projectId, new PrototypeNeedsFixRouteRequest(GoalIndex: 1, Feedback: "continue current step"));

        result.Status.Should().Be("completed");
        runner.Prompt.Should().Contain("current execute next goal step state");
        runner.Prompt.Should().Contain("\"route\":\"execute-next-goal\"");
        runner.Prompt.Should().NotContain("prototype-fallback");
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
        await store.UpdateProjectIterationGoalStatusAsync(
            details!.Goals[0].GoalId,
            "needs_fix",
            "still blocked\nProject README:\n" + string.Concat(Enumerable.Repeat("old nested prompt ", 800)),
            null);
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

    private static PrototypeWorkflowRequest ContractRequest()
    {
        return new PrototypeWorkflowRequest(
            Slug: "contract",
            GameName: "Contract RPG",
            GameType: "rpg",
            GameTypeSource: "RPG",
            Hypothesis: "Project-specific form values must drive the RPG prototype.",
            CorePlayerFantasy: "Explore, encounter enemies, and grow through rewards.",
            MinimumPlayableLoop: "Move on map, trigger encounter, win battle, choose reward, return to map.",
            SuccessCriteria: ["Contract values are implemented."],
            GameFeature: "Every movement increases encounter probability by 10% and encounter must happen within 10 steps.",
            CoreGameplayLoop: "Player starts at 100 HP, 10 ATK, 2 DEF. First enemy has 30 HP and 5 ATK.",
            WinFailConditions: "Win after 15 battles. Any battle loss means game loss.",
            Confirm: true);
    }

    private sealed class SuccessRunner : IHostedProcessRunner
    {
        public string Prompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Prompt = command.StandardInput ?? "";
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
