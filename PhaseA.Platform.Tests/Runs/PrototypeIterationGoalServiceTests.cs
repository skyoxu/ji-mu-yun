using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
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
        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WriteProjectReadme(project!);
        stateWriter.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-baseline" });
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

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
        runner.Commands[0].Arguments.Last().Should().Be("-");
        runner.Commands[0].StandardInput.Should().Contain("prototype-baseline");
        stateWriter.ReadLatestExecuteNextGoalState(project!, 1).Should().Contain(result.RunId);
        artifacts.Select(a => a.ArtifactType).Should().Contain([
            "prototype-iteration-goal-input",
            "prototype-iteration-goal-result",
            "prototype-iteration-goal-codex-output"
        ]);
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldRunGodotSmoke_ForStepFive()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG prototype through the strict contract steps."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var now = DateTimeOffset.UtcNow.ToString("O");
        foreach (var goal in details!.Goals.Where(goal => goal.GoalIndex < 5))
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "succeeded", $"Goal {goal.GoalIndex} already completed.", now);
        }

        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WriteProjectReadme(project!);
        stateWriter.WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        var runner = new StepFiveSmokeHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.GoalIndex.Should().Be(5);
        refreshed!.Goals.Single(goal => goal.GoalIndex == 5).Status.Should().Be("succeeded");
        runner.Commands.Should().Contain(command => command.FileName == "dotnet" && command.Arguments.Contains("test"));
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/smoke_headless.py", StringComparison.Ordinal)));
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/prototype_main_menu_navigation_smoke.py", StringComparison.Ordinal)));
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
    public async Task ExecuteNextAsync_ShouldRequirePrototypeRouteState()
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
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Fix the first playable RPG step."));
        var runner = new FakeHostedProcessRunner();
        var stateWriter = new PrototypeRouteStateWriter();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var project = await store.GetProjectSnapshotAsync(projectId);

        result.Status.Should().Be("needs_fix");
        result.SessionStatus.Should().Be("needs_fix");
        details!.Goals[0].Status.Should().Be("needs_fix");
        runner.Commands.Should().BeEmpty();
        stateWriter.ReadLatestExecuteNextGoalState(project!, 1).Should().Contain("prototype_required");
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

    [Fact]
    public async Task ExecuteNextAsync_MarksGoalNeedsFix_WhenCompletedOutputHasBlockedVerification()
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
        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-baseline" });
        var runner = new BlockedVerificationHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

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

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot, string? godotBin = null)
    {
        var values = new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = repoRoot
        };

        if (!string.IsNullOrWhiteSpace(godotBin))
        {
            values["GODOT_BIN"] = godotBin;
        }

        return PhaseAPlatformOptionsLoader.FromDictionary(values);
    }

    private static void EnsureRpgAcceptanceMarkers(string repoPath)
    {
        var testProjectRoot = Path.Combine(repoPath, "Game.Core.Tests");
        Directory.CreateDirectory(testProjectRoot);
        File.WriteAllText(Path.Combine(testProjectRoot, "Game.Core.Tests.csproj"), """
<Project Sdk="Microsoft.NET.Sdk">
</Project>
""");

        var testsPath = Path.Combine(repoPath, "Game.Core.Tests", "Prototypes");
        Directory.CreateDirectory(testsPath);
        File.WriteAllText(Path.Combine(testsPath, "DqRpgPrototypeLoopTests.cs"), """
public sealed class DqRpgPrototypeLoopTests
{
    public void ShouldReachRewardPhase_AfterWinningTheFirstEncounter() { }
    public void ResolveAttackTurn() { }
    public void BattlesWon() { }
    public void Victory() { }
    public void ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward() { }
    // RewardOptions.Count
    public void ApplyReward() { }
    // Reward chosen
}
""");

        var corePath = Path.Combine(repoPath, "Game.Core", "Prototypes");
        Directory.CreateDirectory(corePath);
        File.WriteAllText(Path.Combine(corePath, "DqRpgPrototypeLoop.cs"), """
public sealed class DqRpgPrototypeLoop
{
    public void ShouldReachRewardPhase_AfterWinningTheFirstEncounter() { }
    public void ResolveAttackTurn() { }
    public void BattlesWon() { }
    public void Victory() { }
    public void ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward() { }
    // RewardOptions.Count
    public void ApplyReward() { }
    // Battle reward selected
    // Return to the map
}
""");
    }

    private static void EnsureRpgSmokeSceneFile(string repoPath)
    {
        var scenePath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg");
        Directory.CreateDirectory(scenePath);
        File.WriteAllText(Path.Combine(scenePath, "DqRpgPrototype.tscn"), """
[gd_scene format=3]

[node name="DqRpgPrototype" type="Node"]
""");
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
SUMMARY: Completed the current goal with verified behavior.
CHANGED: Updated the current project page entry hint.
VERIFY: Unit tests passed and Godot smoke passed.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "iteration goal stdout", ""));
        }
    }

    private sealed class StepFiveSmokeHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, "dotnet test ok", ""));
            }

            if (command.Arguments.Contains("scripts/python/smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS", ""));
            }

            if (command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "NAVIGATION PASS", ""));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Step five completed with reward loop validation.
CHANGED: Connected the reward loop to return-to-map behavior.
VERIFY: Platform acceptance validation passed for the current gameplay goal.
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

    private sealed class BlockedVerificationHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Implemented the requested goal.
CHANGED: Updated gameplay behavior.
VERIFY: Godot verification was blocked by an existing log file permission issue.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "", ""));
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
