using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class GddMilestoneStepServiceTests
{
    [Fact]
    public async Task GetOrCreateLatestAsync_ReturnsGddNotFound_UntilGddExists()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("gdd_not_found");
        result.FailureCode.Should().Be("gdd_not_found");
        result.Steps.Should().BeEmpty();
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_ExtractsExplicitMilestoneSteps_FromGdd()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        WriteGdd(project!.RepoPath, """
        # Action Roguelike GDD

        ## Milestones
        M1: Core combat loop with movement, mouse facing, attacks, dodge, and first room validation.
        M2: Active skills with right click, Q, and E cooldown feedback.
        M10-1: Asset replacement validation with collision and smoke checks.
        """);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        result.CurrentStepId.Should().Be("M1");
        result.Steps.Select(step => step.StepId).Should().Equal("M1", "M2", "M10-1");
        result.Steps[0].Locked.Should().BeFalse();
        result.Steps[0].CanExecute.Should().BeTrue();
        result.Steps[0].CanConfirm.Should().BeFalse();
        result.Steps[1].Locked.Should().BeTrue();
        File.Exists(Path.Combine(project.MetaPath, "routes", "gdd-milestones", "latest.json")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "meta", "routes", "gdd-milestones", "latest.json")).Should().BeTrue();
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_BuildsDynamicDefaultSteps_WhenGddHasNoMilestoneIds()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        WriteGdd(project!.RepoPath, """
        # Cozy Dungeon GDD

        Reference game: Phantom Tower.
        Scene: a dungeon room with doors, rewards, and enemy waves.
        Controls: WASD movement, mouse aiming, left click attack, space dodge.
        Progression: upgrades and persistent souls.
        Assets: replace placeholder characters and props before final validation.
        """);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.Steps.Should().HaveCount(5);
        result.Steps.Select(step => step.StepId).Should().Equal("M1", "M2", "M3", "M4", "M5");
        result.Steps[0].Title.Should().Contain("M1");
        result.Steps[3].Description.Should().Contain("smoke");
    }

    [Fact]
    public async Task ConfirmAsync_UnlocksNextStep_AndCompletesAfterFinalStep()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        WriteGdd(project!.RepoPath, """
        # Two Step GDD

        M1: First playable scene and controls.
        M2: Core loop validation and package prompt.
        """);
        var service = Service(store, options);

        var blocked = await service.ConfirmAsync(accountId, projectId, "M1", new GddMilestoneStepConfirmRequest("too early"));
        var firstPlan = await service.CreateIterationPlanForCurrentStepAsync(accountId, projectId);
        var first = await service.ConfirmAsync(accountId, projectId, "M1", new GddMilestoneStepConfirmRequest("player validated M1"));
        var secondPlan = await service.CreateIterationPlanForCurrentStepAsync(accountId, projectId);
        var second = await service.ConfirmAsync(accountId, projectId, "M2", new GddMilestoneStepConfirmRequest("player validated M2"));

        blocked.Should().NotBeNull();
        blocked!.Status.Should().Be("step_not_ready_to_confirm");
        blocked.FailureCode.Should().Be("step_not_ready_to_confirm");
        firstPlan!.Status.Should().Be("ready");
        first.Should().NotBeNull();
        first!.Status.Should().Be("confirmed");
        first.Plan!.CurrentStepId.Should().Be("M2");
        first.Plan.Steps.Single(step => step.StepId == "M2").Locked.Should().BeFalse();
        first.Plan.Steps.Single(step => step.StepId == "M2").CanConfirm.Should().BeFalse();
        secondPlan!.Status.Should().Be("ready");
        second.Should().NotBeNull();
        second!.Plan!.Status.Should().Be("completed");
        second.Plan.CurrentStepId.Should().BeNull();
        second.Plan.Steps.Should().OnlyContain(step => step.Status == "confirmed");
    }

    [Fact]
    public async Task ConfirmAsync_ReviewsAndAdjustsNextStep_WhenLlmSuggestsChange()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var project = await store.GetProjectSnapshotAsync(projectId);
        WriteGdd(project!.RepoPath, """
        # Two Step GDD

        M1: First playable scene and controls.
        M2: Core loop validation and package prompt.
        """);
        var reviewJson = """
        {
          "shouldAdjust": true,
          "title": "M2：Core loop with slower first wave",
          "description": "Adjust M2 around player feedback that the first wave was too fast.",
          "acceptance": "Player can validate a slower first wave before package confirmation.",
          "summary": "已根据 M1 反馈调整 M2 的首波节奏。"
        }
        """;
        var service = Service(store, options, new FakeLlmRouteEngine(reviewJson));

        var plan = await service.CreateIterationPlanForCurrentStepAsync(accountId, projectId);
        plan!.Plan!.Steps.Single(step => step.StepId == "M1").CanConfirm.Should().BeTrue();
        var result = await service.ConfirmAsync(accountId, projectId, "M1", new GddMilestoneStepConfirmRequest("first wave too fast"));

        var next = result!.Plan!.Steps.Single(step => step.StepId == "M2");
        next.Title.Should().Contain("slower first wave");
        next.Description.Should().Contain("first wave was too fast");
        next.Acceptance.Should().Contain("slower first wave");
        next.ReviewSummary.Should().Contain("调整 M2");
    }

    private static GddMilestoneStepService Service(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        ILlmRouteEngine? llmRouteEngine = null)
    {
        return new GddMilestoneStepService(
            store,
            new PrototypeIterationPlanService(store),
            new PrototypeFeedbackIterationService(store, options, new FakeHostedProcessRunner()),
            llmRouteEngine);
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "Action Roguelike", null, null, null, null));
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

    private static void WriteGdd(string repoPath, string text)
    {
        var path = Path.Combine(repoPath, "docs", "gdd", "GDD.md");
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, text);
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new HostedProcessResult(0, "ok", ""));
        }
    }

    private sealed class FakeLlmRouteEngine : ILlmRouteEngine
    {
        private readonly string _json;

        public FakeLlmRouteEngine(string json)
        {
            _json = json;
        }

        public Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new LlmRouteResult(
                true,
                _json,
                _json,
                request.Model,
                null,
                null,
                0,
                "",
                "",
                null,
                1,
                request.Prompt.Length,
                System.Text.Encoding.UTF8.GetByteCount(request.Prompt),
                1));
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
