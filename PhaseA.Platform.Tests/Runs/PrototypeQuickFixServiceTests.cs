using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeQuickFixServiceTests
{
    [Fact]
    public void GoalRepairCompletionEvidence_ShouldAcceptStrongStructuredVerification()
    {
        var output = """
STATUS: completed
SUMMARY: Current step is repaired through structured status.
CHANGED: Step repair completed.
VERIFY: Godot gameplay verification passed for map movement and first encounter trigger.
REMAINING: none
""";

        PrototypeQuickFixService.HasGoalRepairCompletionEvidenceForTesting(output).Should().BeTrue();
    }

    [Fact]
    public void GoalRepairCompletionEvidence_ShouldRejectMissingGameplayVerification()
    {
        var output = """
STATUS: completed
SUMMARY: Platform route tests passed, but gameplay acceptance is not verified.
CHANGED: Route recovery behavior was adjusted.
VERIFY: Platform tests passed.
REMAINING: none

还没有做的是 Godot 侧对地图移动稳定、明确进入第一次遇敌的业务验收。
""";

        PrototypeQuickFixService.HasGoalRepairCompletionEvidenceForTesting(output).Should().BeFalse();
    }

    [Fact]
    public async Task SubmitAsync_CreatesQuickFixRun_AndArtifacts()
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
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var artifacts = await store.ListArtifactsForRunAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.AssistantMessage.Should().Contain("快速修复已完成");
        run!.RunType.Should().Be("prototype-quick-fix");
        run.Status.Should().Be("completed");
        runner.Commands.Should().ContainSingle();
        runner.Commands[0].Arguments.Should().Contain(["exec", "--sandbox", "workspace-write", "-m", "gpt-5.4"]);
        runner.Commands[0].Arguments.Should().Contain(["-c", "model_reasoning_effort=\"low\""]);
        artifacts.Select(a => a.ArtifactType).Should().Contain([
            "prototype-quick-fix-submission",
            "prototype-quick-fix-result-log",
            "prototype-quick-fix-codex-output"
        ]);
    }

    [Fact]
    public async Task SubmitAsync_ReturnsTimeoutFailure_WhenRunnerDoesNotFinishInTime()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var runner = new TimeoutHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), TimeSpan.FromMilliseconds(50));

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.AssistantMessage.Should().Contain("快速修复超时");
        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(408);
    }

    [Fact]
    public async Task SubmitAsync_ShouldCompleteEvenWhenCallerTokenIsCanceledAfterRunStarts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        using var callerCancellation = new CancellationTokenSource();
        var runner = new CancelCallerThenReturnHostedProcessRunner(callerCancellation);
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(
            projectId,
            new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"),
            callerCancellation.Token);
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        run!.Status.Should().Be("completed");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPromoteNeedsFixGoal_WhenCurrentGoalBecomesReady()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new GoalRepairSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.IterationSessionStatus.Should().Be("paused_for_review");
        refreshed!.Goals[0].Status.Should().Be("succeeded");
        refreshed.Session.Status.Should().Be("paused_for_review");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldRunGodotSmoke_ForStepFive()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG reward loop to a clean return-to-map validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 5);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need engine verification for reward loop.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 5, "Goal 5 needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateWriter = new PrototypeRouteStateWriter();
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
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 5, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        runner.Commands.Should().Contain(command => command.FileName == "dotnet" && command.Arguments.Contains("test"));
        runner.Commands.Should().Contain(command => command.FileName == "dotnet" && command.Arguments.Contains("build"));
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/smoke_headless.py", StringComparison.Ordinal)));
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/prototype_main_menu_navigation_smoke.py", StringComparison.Ordinal)));
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldHonorStructuredCompletedStatus()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Stabilize map movement and first encounter trigger."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "still blocked", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "goal 1 needs fix");
        var runner = new StructuredCompletedHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        refreshed!.Goals[0].Status.Should().Be("succeeded");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepNeedsFix_WhenCurrentGoalIsStillBlocked()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new GoalRepairNeedsFixHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        refreshed.Session.Status.Should().Be("needs_fix");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldRejectCompletedStatus_WhenGameplayVerificationIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new StructuredCompletedButMissingGameplayVerificationHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        refreshed.Session.Status.Should().Be("needs_fix");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPersistNeedsFixSummary_WhenRepairTimesOut()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new TimeoutHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), TimeSpan.FromMilliseconds(50));

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("failed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        refreshed.Goals[0].ResultSummary.Should().Contain("修复超时");
        refreshed.Session.Status.Should().Be("needs_fix");
        refreshed.Session.LatestSummary.Should().Contain("修复超时");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldRejectOffTopicSuccessOutput()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = new PrototypeIterationPlanService(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        refreshed.Session.Status.Should().Be("needs_fix");
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
        File.WriteAllText(Path.Combine(repoPath, "GodotGame.csproj"), """
<Project Sdk="Microsoft.NET.Sdk">
</Project>
""");

        var testsPath = Path.Combine(repoPath, "Game.Core.Tests", "Prototypes");
        Directory.CreateDirectory(testsPath);
        File.WriteAllText(Path.Combine(testsPath, "DqRpgPrototypeLoopTests.cs"), """
public sealed class DqRpgPrototypeLoopTests
{
    public void MoveOnMap() { }
    public void ShouldReachRewardPhase_AfterWinningTheFirstEncounter() { }
    public void ResolveAttackTurn() { }
    public void BattlesWon() { }
    public void Victory() { }
    public void ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward() { }
    // RewardOptions.Count
    public void ApplyReward() { }
    // Battle reward selected
    // Return to the map
    // VictoryBattleCount
    // IsVictory
    // IsGameOver
}
""");

        var corePath = Path.Combine(repoPath, "Game.Core", "Prototypes");
        Directory.CreateDirectory(corePath);
        File.WriteAllText(Path.Combine(corePath, "DqRpgPrototypeLoop.cs"), """
public sealed class DqRpgPrototypeLoop
{
    public void MoveOnMap() { }
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
[gd_scene load_steps=4 format=3]

[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/map_floor_tile.png" id="1"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/player_hero.png" id="2"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/enemy_slime.png" id="3"]

[node name="DqRpgPrototype" type="Node"]
[node name="StartButton" type="Button" parent="."]
text = "Start Adventure"
[node name="CanvasLayer" type="CanvasLayer" parent="."]
[node name="UI" type="Control" parent="CanvasLayer"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
[node name="MapScene" parent="CanvasLayer/UI"]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
[node name="RpgMapAsset" type="TextureRect" parent="MapScene"]
texture = ExtResource("1")
[node name="RpgPlayerAsset" type="TextureRect" parent="MapScene"]
texture = ExtResource("2")
[node name="RpgEnemyAsset" type="TextureRect" parent="MapScene"]
texture = ExtResource("3")
""");
        File.WriteAllText(Path.Combine(scenePath, "MapScene.tscn"), """
[gd_scene load_steps=4 format=3]

[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/map_floor_tile.png" id="1"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/player_hero.png" id="2"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/enemy_slime.png" id="3"]

[node name="MapScene" type="Node"]
[node name="Grid" type="Node" parent="."]
[node name="Player" type="Node" parent="."]
[node name="Enemy" type="Node" parent="."]
[node name="RpgMapAsset" type="TextureRect" parent="."]
texture = ExtResource("1")
[node name="RpgPlayerAsset" type="TextureRect" parent="."]
texture = ExtResource("2")
[node name="RpgEnemyAsset" type="TextureRect" parent="."]
texture = ExtResource("3")
""");
        File.WriteAllText(Path.Combine(scenePath, "BattleScene.tscn"), """
[gd_scene format=3]

[node name="BattleScene" type="Node"]
[node name="AttackButton" type="Button" parent="."]
text = "Attack"
""");
        var scriptPath = Path.Combine(scenePath, "Scripts");
        Directory.CreateDirectory(scriptPath);
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), "public sealed class DqRpgPrototype { void Ready() { _mapScene = GetNode<MapScene>(\"CanvasLayer/UI/MapScene\"); StartButton.Pressed += ShowMapScene; _mapScene.Visible = true; } void ShowMapScene() {} }\n");
        File.WriteAllText(Path.Combine(scriptPath, "MapScene.cs"), "public sealed class MapScene { public event System.Action? EncounterEntered; void MovePlayer() {} }\n");
        File.WriteAllText(Path.Combine(scriptPath, "BattleScene.cs"), "public sealed class BattleScene { public event System.Action? BattleFinished; void ResolveBattle() {} }\n");
        var catalogPath = Path.Combine(repoPath, "Game.Godot", "Scripts", "Prototypes");
        Directory.CreateDirectory(catalogPath);
        File.WriteAllText(Path.Combine(catalogPath, "PrototypeCatalog.cs"), """
public static class PrototypeCatalog
{
    public const string DqRpgPrototypeScenePath = "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn";
}
""");
        var mainScenePath = Path.Combine(repoPath, "Game.Godot", "Scenes");
        Directory.CreateDirectory(mainScenePath);
        File.WriteAllText(Path.Combine(mainScenePath, "Main.tscn"), "[gd_scene format=3]\n");
        var dqAssetPath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Assets");
        Directory.CreateDirectory(dqAssetPath);
        foreach (var assetFile in new[] { "map_floor_tile.png", "player_hero.png", "enemy_slime.png" })
        {
            File.WriteAllText(Path.Combine(dqAssetPath, assetFile), "asset");
        }

        foreach (var (assetDir, assetFile) in new[] { ("Map", "map_tile.png"), ("Player", "player_hero.png"), ("Enemy", "enemy_slime.png") })
        {
            var path = Path.Combine(repoPath, "Game.Godot", "Prototypes", "DefaultRpgTemplate", "Assets", assetDir);
            Directory.CreateDirectory(path);
            File.WriteAllText(Path.Combine(path, assetFile), "asset");
        }
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "Quick fix applied.");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", ""));
        }
    }

    private sealed class GoalRepairSuccessHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
当前目标修复已完成。
玩家现在可以稳定移动，并且能够明确触发第一次遇敌。
地图中的第一次遇敌入口已经接通，本 step 现在已可继续。
ready to continue
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class GoalRepairStep5HostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
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
SUMMARY: Goal 5 is repaired.
CHANGED: Updated the reward loop.
VERIFY: Platform acceptance validation passed for the current gameplay goal.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class StructuredCompletedHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Current step is repaired through structured status.
CHANGED: Step repair completed.
VERIFY: Godot gameplay verification passed for map movement and first encounter trigger.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class StructuredCompletedButMissingGameplayVerificationHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Platform route tests passed, but gameplay acceptance is not verified.
CHANGED: Route recovery behavior was adjusted.
VERIFY: Platform tests passed.
REMAINING: none

还没有做的是 Godot 侧对地图移动稳定、明确进入第一次遇敌的业务验收。
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class GoalRepairNeedsFixHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
当前 step 仍需修复。
还有 remaining blocker。
not ready
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class TimeoutHostedProcessRunner : IHostedProcessRunner
    {
        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            await Task.Delay(TimeSpan.FromSeconds(1), cancellationToken);
            return new HostedProcessResult(0, "", "");
        }
    }

    private sealed class OffTopicSuccessHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
当前目标修复已完成。
本 step 现在已可继续。
我更新了部署脚本、文档和安全测试。
ready to continue
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class CancelCallerThenReturnHostedProcessRunner : IHostedProcessRunner
    {
        private readonly CancellationTokenSource _callerCancellation;

        public CancelCallerThenReturnHostedProcessRunner(CancellationTokenSource callerCancellation)
        {
            _callerCancellation = callerCancellation;
        }

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            _callerCancellation.Cancel();
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, "Quick fix applied after caller disconnect.");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", ""));
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
