using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
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
        result.Summary.Should().Be("已根据当前策划大纲生成游戏模块步骤规格。");
        result.CurrentStepId.Should().Be("M1");
        result.Steps.Select(step => step.StepId).Should().Equal("M1", "M2", "M10-1");
        result.Steps[0].Locked.Should().BeFalse();
        result.Steps[0].CanExecute.Should().BeTrue();
        result.Steps[0].CanConfirm.Should().BeFalse();
        result.Steps[0].ScopeIn.Should().Contain("当前 step");
        result.Steps[0].ScopeOut.Should().Contain("不提前实现后续锁定 step");
        result.Steps[0].GodotSlice.Should().Contain("Godot 4.5.1 + C#");
        result.Steps[0].PackagingValidation.Should().Contain("打包下载");
        result.Steps[0].FeedbackGuidance.Should().Contain("needs-fix 修复");
        result.Steps[0].NextStepReview.Should().Contain("解锁下一 step");
        result.Steps[1].Locked.Should().BeTrue();
        result.Steps.Single(step => step.StepId == "M10-1").ScopeIn.Should().Contain("碰撞");
        result.Steps.Single(step => step.StepId == "M10-1").Acceptance.Should().Contain("穿模");
        File.Exists(Path.Combine(project.MetaPath, "routes", "gdd-milestones", "latest.json")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "meta", "routes", "gdd-milestones", "latest.json")).Should().BeTrue();
        File.ReadAllText(Path.Combine(project.MetaPath, "routes", "gdd-milestones", "latest.json"))
            .Should().Contain("phase-a.gdd-milestone-steps.v2");
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
    public async Task GetOrCreateLatestAsync_NormalizesLegacyIterationReadyStatus_ToExecutableReady()
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
        # Legacy State GDD

        M1: First playable scene and controls.
        M2: Core loop validation and package prompt.
        """);
        WriteLegacyStepState(project.MetaPath, project.RepoPath);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.CurrentStepId.Should().Be("M1");
        result.Steps.Single(step => step.StepId == "M1").Status.Should().Be("ready");
        result.Steps.Single(step => step.StepId == "M1").CanExecute.Should().BeTrue();
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
        var firstPlan = await service.ExecuteCurrentStepAsync(accountId, projectId);
        var first = await service.ConfirmAsync(accountId, projectId, "M1", new GddMilestoneStepConfirmRequest("player validated M1"));
        var secondPlan = await service.ExecuteCurrentStepAsync(accountId, projectId);
        var second = await service.ConfirmAsync(accountId, projectId, "M2", new GddMilestoneStepConfirmRequest("player validated M2"));

        blocked.Should().NotBeNull();
        blocked!.Status.Should().Be("step_not_ready_to_confirm");
        blocked.FailureCode.Should().Be("step_not_ready_to_confirm");
        firstPlan!.Status.Should().Be("completed");
        firstPlan.StepExecution.Should().NotBeNull();
        first.Should().NotBeNull();
        first!.Status.Should().Be("confirmed");
        first.Plan!.CurrentStepId.Should().Be("M2");
        first.Plan.Steps.Single(step => step.StepId == "M2").Locked.Should().BeFalse();
        first.Plan.Steps.Single(step => step.StepId == "M2").CanConfirm.Should().BeFalse();
        secondPlan!.Status.Should().Be("completed");
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
          "scopeIn": "Only adjust the first wave tempo and visible telegraph.",
          "scopeOut": "Do not add later boss rooms.",
          "godotSlice": "Tune the wave spawner and HUD progress state.",
          "packagingValidation": "Package and ask the player to validate the slower first wave.",
          "feedbackGuidance": "Submit feedback only for first wave pacing.",
          "nextStepReview": "Re-check whether the following reward step still fits.",
          "summary": "已根据 M1 反馈调整 M2 的首波节奏。"
        }
        """;
        var service = Service(store, options, new FakeLlmRouteEngine(reviewJson));

        var plan = await service.ExecuteCurrentStepAsync(accountId, projectId);
        plan!.Plan!.Steps.Single(step => step.StepId == "M1").CanConfirm.Should().BeTrue();
        var result = await service.ConfirmAsync(accountId, projectId, "M1", new GddMilestoneStepConfirmRequest("first wave too fast"));

        var next = result!.Plan!.Steps.Single(step => step.StepId == "M2");
        next.Title.Should().Contain("slower first wave");
        next.Description.Should().Contain("first wave was too fast");
        next.Acceptance.Should().Contain("slower first wave");
        next.ScopeIn.Should().Contain("first wave tempo");
        next.ScopeOut.Should().Contain("boss rooms");
        next.GodotSlice.Should().Contain("wave spawner");
        next.PackagingValidation.Should().Contain("Package");
        next.FeedbackGuidance.Should().Contain("first wave pacing");
        next.NextStepReview.Should().Contain("following reward step");
        next.ReviewSummary.Should().Contain("调整 M2");
    }

    [Fact]
    public async Task SubmitFeedbackAsync_RoutesCurrentStepFeedbackThroughNeedsFix()
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
        # Feedback Step GDD

        M1: First playable loop with visible state feedback.
        M2: Follow-up tuning.
        """);
        var service = Service(store, options);
        var executed = await service.ExecuteCurrentStepAsync(accountId, projectId);

        var result = await service.SubmitFeedbackAsync(
            accountId,
            projectId,
            "M1",
            new GddMilestoneStepFeedbackRequest("Please repair M1 and keep it scoped to the current milestone."));

        executed!.StepExecution.Should().NotBeNull();
        result.Should().NotBeNull();
        result!.NeedsFixRun.Should().NotBeNull();
        result.FeedbackRun.Should().BeNull();
        result.Plan!.CurrentStepId.Should().Be("M1");
        result.Plan.Steps.Single(step => step.StepId == "M1").CanConfirm.Should().BeTrue();
        result.Plan.Steps.Single(step => step.StepId == "M2").Locked.Should().BeTrue();
        result.NeedsFixRun!.GoalIndex.Should().Be(1);
    }

    private static GddMilestoneStepService Service(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        ILlmRouteEngine? llmRouteEngine = null)
    {
        var runner = new FakeHostedProcessRunner();
        return new GddMilestoneStepService(
            store,
            new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), new PrototypeRouteStateWriter()),
            new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), new PrototypeRouteStateWriter()),
            llmRouteEngine);
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "Action Roguelike", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(result.ProjectId!);
        SeedPrototypeBaseline(project!);
        return result.ProjectId!;
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

    private static void WriteGdd(string repoPath, string text)
    {
        var path = Path.Combine(repoPath, "docs", "gdd", "GDD.md");
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, text);
    }

    private static void WriteLegacyStepState(string metaPath, string repoPath)
    {
        const string payload = """
{
  "schema": "phase-a.gdd-milestone-steps.v2",
  "status": "ready",
  "summary": "legacy state",
  "currentStepId": "M1",
  "steps": [
    {
      "stepId": "M1",
      "stepIndex": 1,
      "title": "M1: First playable scene and controls.",
      "description": "First playable scene and controls.",
      "acceptance": "",
      "scopeIn": "",
      "scopeOut": "",
      "godotSlice": "",
      "packagingValidation": "",
      "feedbackGuidance": "",
      "nextStepReview": "",
      "status": "iteration_ready",
      "locked": false,
      "iterationSessionId": "legacy-session-1"
    },
    {
      "stepId": "M2",
      "stepIndex": 2,
      "title": "M2: Core loop validation and package prompt.",
      "description": "Core loop validation and package prompt.",
      "acceptance": "",
      "scopeIn": "",
      "scopeOut": "",
      "godotSlice": "",
      "packagingValidation": "",
      "feedbackGuidance": "",
      "nextStepReview": "",
      "status": "locked",
      "locked": true
    }
  ]
}
""";
        foreach (var root in new[] { metaPath, Path.Combine(repoPath, "meta") })
        {
            var path = Path.Combine(root, "routes", "gdd-milestones", "latest.json");
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, payload);
        }
    }

    private static void SeedPrototypeBaseline(ProjectSnapshot project)
    {
        new PrototypeRouteStateWriter().WritePrototypeState(project, new { route = "prototype-7day-playable", marker = "prototype-baseline" });
        WriteText(project.RepoPath, ".agents/skills/prototype-7day-playable-godot-zh/SKILL.md", "# skill\n");
        WriteText(project.RepoPath, "Game.Core/Prototypes/DemoPrototypeLoop.cs", """
public sealed class DemoPrototypeLoop
{
    public DemoPrototypeState CraftBurger(DemoPrototypeState state)
    {
        return state with { LastMessage = "Craft result feedback is visible.", CraftFeedback = "Result state changed." };
    }
}

public sealed record DemoPrototypeState(string LastMessage, string CraftFeedback);
""");
        WriteText(project.RepoPath, "Game.Core.Tests/Prototypes/DemoPrototypeLoopTests.cs", """
public sealed class DemoPrototypeLoopTests
{
    public void ShouldShowCraftFeedback_WhenPlayerMakesItem() { }
}
""");
        WriteText(project.RepoPath, "Game.Godot/Prototypes/demo/Scripts/DemoPrototype.cs", """
public sealed class DemoPrototype
{
    private string _craftFeedbackLabel = "Feedback Label";
}
""");
    }

    private static void WriteText(string repoPath, string relativePath, string text)
    {
        var path = Path.Combine(repoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
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
