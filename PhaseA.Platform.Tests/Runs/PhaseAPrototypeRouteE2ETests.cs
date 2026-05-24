using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PhaseAPrototypeRouteE2ETests
{
    [Fact]
    public async Task PrototypePlanAndNeedsFixRoutes_ShouldFlowThroughRecoverableArtifacts()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var routeStateWriter = new PrototypeRouteStateWriter();
        var projectCreation = new ProjectCreationService(store, options, new ProjectRuleCatalog(), new ProjectWorkspaceSeeder(options), routeStateWriter);

        var created = await projectCreation.CreateProjectAsync(
            accountId,
            new ProjectCreationRequest("route-e2e", "Route E2E RPG", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);

        File.Exists(Path.Combine(project!.RepoPath, "README.md")).Should().BeTrue();
        File.ReadAllText(Path.Combine(project.RepoPath, "README.md")).Should().Contain(project.ProjectId);

        var prototypeRunner = new PrototypeWorkflowRunner();
        var prototypeWorkflow = new PrototypeWorkflowService(
            store,
            options,
            prototypeRunner,
            new PrototypeRecordWriter(options),
            new PrototypeWorkflowCommandBuilder(options),
            new PrototypeArtifactIndexer(),
            new LlmBindingService(store, options),
            new LlmStopLossService(store, options),
            new ProjectWorkspaceSeeder(options),
            new GameTypeTemplateCatalog(options),
            routeStateWriter);
        var prototype = await prototypeWorkflow.RunAsync(project.ProjectId, PrototypeRequest());
        prototype.Status.Should().Be("succeeded");
        routeStateWriter.ReadLatestPrototypeState(project).Should().Contain(prototype.RunId);

        var planService = new PrototypeIterationPlanService(store, routeStateWriter);
        var plan = await planService.CreateAsync(
            accountId,
            project.ProjectId,
            new PrototypeIterationPlanRequest("First stabilize map movement. Then complete the first encounter. Finally clarify the victory condition."));
        plan.Status.Should().Be("ready");
        routeStateWriter.ReadLatestPrototypeState(project).Should().Contain(prototype.RunId);
        File.ReadAllText(Path.Combine(project.MetaPath, "routes", "iteration-plan", "latest.json")).Should().Contain(plan.SessionId);

        var iterationRunner = new IterationNeedsFixRunner();
        var iterationGoalService = new PrototypeIterationGoalService(store, options, iterationRunner);
        var executed = await iterationGoalService.ExecuteNextAsync(accountId, project.ProjectId);
        executed.Status.Should().Be("needs_fix");
        executed.SessionStatus.Should().Be("needs_fix");

        var details = await store.GetLatestProjectIterationSessionAsync(project.ProjectId);
        var blockedGoal = details!.Goals.Single(goal => goal.Status == "needs_fix");
        var needsFixRunner = new NeedsFixCompletedRunner();
        var needsFixRoute = new PrototypeNeedsFixRouteService(
            store,
            new PrototypeQuickFixService(store, options, needsFixRunner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog()),
            routeStateWriter);

        var fixedResult = await needsFixRoute.RunAsync(
            accountId,
            project.ProjectId,
            new PrototypeNeedsFixRouteRequest("Repair this step.", "gpt-5.4", "normal", blockedGoal.GoalId, blockedGoal.GoalIndex));

        fixedResult.Status.Should().Be("completed");
        fixedResult.IterationGoalStatus.Should().Be("succeeded", fixedResult.Summary);
        routeStateWriter.ReadLatestNeedsFixState(project, blockedGoal.GoalIndex).Should().Contain(fixedResult.RunId);
        needsFixRunner.Prompt.Should().Contain("Project README:");
        needsFixRunner.Prompt.Should().Contain("Prototype route state");
        needsFixRunner.Prompt.Should().Contain(project.ProjectId);

        var refreshed = await store.GetLatestProjectIterationSessionAsync(project.ProjectId);
        refreshed!.Goals.Single(goal => goal.GoalId == blockedGoal.GoalId).Status.Should().Be("succeeded");
        refreshed.Session.Status.Should().Be("paused_for_review");
    }

    private static PrototypeWorkflowRequest PrototypeRequest()
    {
        return new PrototypeWorkflowRequest(
            Slug: "route-e2e-rpg",
            GameName: "Route E2E RPG",
            GameType: "rpg",
            GameTypeSource: "RPG",
            Hypothesis: "A tiny RPG loop can prove the fantasy.",
            CorePlayerFantasy: "The player can move, trigger an encounter, and understand the goal.",
            MinimumPlayableLoop: "Move on map, enter encounter, win or lose.",
            SuccessCriteria: ["Player reaches the encounter.", "Outcome is clear."],
            GameFeature: "RPG first encounter.",
            CoreGameplayLoop: "Move, encounter, resolve, return.",
            WinFailConditions: "Win after one successful encounter; fail when defeated.",
            Confirm: true);
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

    private sealed class PrototypeWorkflowRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.Arguments.Contains("scripts/python/smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (marker)\n", ""));
            }

            if (command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "MAIN_MENU_PROTOTYPE_NAV PASS scene=res://Game.Godot/Prototypes/route-e2e-rpg/RouteE2eRpgPrototype.tscn\n", ""));
            }

            Write(command.WorkingDirectory, "docs/prototypes/route-e2e-rpg.prototype.json", """
{
  "prototype_type_kit": {
    "manifest": {
      "paths": {
        "default_scene": "res://Game.Godot/Prototypes/route-e2e-rpg/RouteE2eRpgPrototype.tscn"
      }
    }
  }
}
""");
            Write(command.WorkingDirectory, "Game.Godot/Prototypes/route-e2e-rpg/RouteE2eRpgPrototype.tscn", "[gd_scene format=3]\n");
            Write(command.WorkingDirectory, "logs/ci/project-health/latest.html", "<html></html>");
            Write(command.WorkingDirectory, "logs/ci/project-health/latest.json", "{}");
            Write(command.WorkingDirectory, "logs/ci/active-prototypes/route-e2e-rpg.completion.md", "# Prototype Completion Report\n");
            Write(command.WorkingDirectory, "logs/ci/active-prototypes/route-e2e-rpg.packaging.json", """
{
  "kind": "prototype-packaging-summary",
  "default_scene": "res://Game.Godot/Prototypes/route-e2e-rpg/RouteE2eRpgPrototype.tscn",
  "tdd_stage_counts": { "red": 1, "green": 1, "refactor": 1 }
}
""");
            WriteRpgAcceptanceFiles(command.WorkingDirectory);
            Write(command.WorkingDirectory, "logs/ci/active-prototypes/route-e2e-rpg.active.json", """
{
  "status": "completed-through-day",
  "completed_through_day": 7,
  "missing_required_fields": [],
  "prototype_spec": "docs/prototypes/route-e2e-rpg.prototype.json",
  "completion_summary": "Prototype route finished. Next step: stabilize the first encounter.",
  "steps_run": [
    { "day": 1, "status": "ok" },
    { "day": 2, "status": "ok" },
    { "day": 3, "status": "ok" },
    { "day": 4, "status": "ok" },
    { "day": 5, "status": "ok" },
    { "day": 6, "status": "ok" },
    { "day": 7, "status": "ok" }
  ]
}
""");
            return Task.FromResult(new HostedProcessResult(0, "prototype workflow ok\n", ""));
        }
    }

    private sealed class IterationNeedsFixRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: The first goal still needs route repair.
CHANGED: Found the blocker.
VERIFY: Needs-fix route should repair it.
REMAINING: Run needs-fix for this step.
""");
            return Task.FromResult(new HostedProcessResult(0, "iteration needs fix", ""));
        }
    }

    private sealed class NeedsFixCompletedRunner : IHostedProcessRunner
    {
        public string Prompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.Arguments.Contains("scripts/python/smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (marker)\n", ""));
            }

            if (command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "MAIN_MENU_PROTOTYPE_NAV PASS scene=res://Game.Godot/Prototypes/route-e2e-rpg/RouteE2eRpgPrototype.tscn\n", ""));
            }

            if (command.Arguments.Contains("dotnet") || command.FileName.Contains("dotnet", StringComparison.OrdinalIgnoreCase))
            {
                return Task.FromResult(new HostedProcessResult(0, "Build succeeded.\n", ""));
            }

            Prompt = command.StandardInput ?? "";
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Current step is ready to continue.
CHANGED: Repaired the current step.
VERIFY: Current step verification passed.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair finished", ""));
        }
    }


    private static void WriteRpgAcceptanceFiles(string root)
    {
        Write(root, "Game.Core/Prototypes/DqRpgPrototypeLoop.cs", """
namespace Game.Core.Prototypes;

public sealed class DqRpgPrototypeLoop
{
    private const string RewardOptionsMarker = "RewardOptions.Count";
    public int RewardOptionsCount => 3;
    public int VictoryBattleCount => 1;
    public bool IsVictory => true;
    public bool IsGameOver => false;
    public void MoveOnMap() { }
    public void ResolveAttackTurn() { }
    public void ApplyReward() { }
}
""");
        Write(root, "Game.Core.Tests/Prototypes/DqRpgPrototypeLoopTests.cs", """
namespace Game.Core.Tests.Prototypes;

public sealed class DqRpgPrototypeLoopTests
{
    public void ShouldReachRewardPhase_AfterWinningTheFirstEncounter() { }
    public void ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward() { }
    public void RewardOptions_Count() { }
    public void Battle_reward_selected_Return_to_the_map() { }
}
""");
        Write(root, "Game.Godot/Prototypes/dq-rpg/Assets/Map/map.png", "map");
        Write(root, "Game.Godot/Prototypes/dq-rpg/Assets/Player/player.png", "player");
        Write(root, "Game.Godot/Prototypes/dq-rpg/Assets/Enemy/enemy.png", "enemy");
        Write(root, "Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", """
[gd_scene load_steps=4 format=3]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/Map/map.png" id="1_map"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/Player/player.png" id="2_player"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/Enemy/enemy.png" id="3_enemy"]
[node name="DqRpgPrototype" type="Control"]
anchors_preset = 15
[node name="CanvasLayer" type="CanvasLayer" parent="."]
[node name="UI" type="Control" parent="CanvasLayer"]
[node name="StartButton" type="Button" parent="CanvasLayer/UI"]
text = "Start Adventure"
[node name="MapScene" parent="CanvasLayer/UI" instance=ExtResource("4_mapscene")]
[node name="RpgMapAsset" type="TextureRect" parent="."]
texture = ExtResource("1_map")
[node name="RpgPlayerAsset" type="TextureRect" parent="."]
texture = ExtResource("2_player")
[node name="RpgEnemyAsset" type="TextureRect" parent="."]
texture = ExtResource("3_enemy")
""");
        Write(root, "Game.Godot/Prototypes/dq-rpg/MapScene.tscn", """
[gd_scene load_steps=4 format=3]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/Map/map.png" id="1_map"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/Player/player.png" id="2_player"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/Enemy/enemy.png" id="3_enemy"]
[ext_resource type="Script" path="res://Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs" id="4_script"]
[node name="MapScene" type="Control"]
script = ExtResource("4_script")
[node name="Panel" type="Panel" parent="."]
[node name="Margin" type="MarginContainer" parent="Panel"]
[node name="VBox" type="VBoxContainer" parent="Panel/Margin"]
[node name="Title" type="Label" parent="Panel/Margin/VBox"]
[node name="StatusLabel" type="Label" parent="Panel/Margin/VBox"]
[node name="TrackFrame" type="Panel" parent="Panel/Margin/VBox"]
[node name="TrackMargin" type="MarginContainer" parent="Panel/Margin/VBox/TrackFrame"]
[node name="TrackLayer" type="Control" parent="Panel/Margin/VBox/TrackFrame/TrackMargin"]
custom_minimum_size = Vector2(600, 600)
[node name="RpgMapAsset" type="TextureRect" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer"]
texture = ExtResource("1_map")
[node name="Grid" type="Control" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer"]
[node name="Overlay" type="Control" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer"]
[node name="RpgPlayerAsset" type="TextureRect" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer/Overlay"]
texture = ExtResource("2_player")
[node name="RpgEnemyAsset" type="TextureRect" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer/Overlay"]
texture = ExtResource("3_enemy")
""");
        Write(root, "Game.Godot/Prototypes/dq-rpg/BattleScene.tscn", """
[gd_scene load_steps=2 format=3]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/Enemy/enemy.png" id="1_enemy"]
[node name="BattleScene" type="Control"]
[node name="Attack" type="Button" parent="."]
[node name="RpgEnemyAsset" type="TextureRect" parent="."]
texture = ExtResource("1_enemy")
""");
        Write(root, "Game.Godot/Prototypes/dq-rpg/Scripts/DqRpgPrototype.cs", """
public sealed class DqRpgPrototype
{
    public void StartRun() { ShowMapScene(); }
    public void ShowMapScene() { _mapScene.Visible = true; }
    private dynamic _mapScene;
    public void ShowRewardScene(System.Collections.Generic.IReadOnlyList<string> rewards) { if (rewards.Count <= 0) return; ShowMapScene(); }
}
""");
        Write(root, "Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs", """
public sealed class MapScene
{
    public void MovePlayer() { _player.Visible = true; }
    public void GridToPosition() { }
    public void EncounterEntered() { }
    public void ShowRewardReturnStatus() { _player.Visible = true; }
    private dynamic _player;
}
""");
        Write(root, "Game.Godot/Prototypes/dq-rpg/Scripts/BattleScene.cs", """
public sealed class BattleScene
{
    public void ResolveAttackTurn() { BattleFinished(); }
    public void BattleFinished() { }
}
""");
        Write(root, "Game.Godot/Scripts/Prototypes/PrototypeCatalog.cs", """
public static class PrototypeCatalog
{
    public const string DqRpg = "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn";
}
""");
        Write(root, "Game.Godot/Scenes/Main.tscn", """
[gd_scene format=3]
[node name="Main" type="Control"]
[node name="VBox" type="Control" parent="."]
visible = false
[node name="Overlays" type="Control" parent="."]
visible = false
[node name="ScreenRoot" type="Control" parent="."]
visible = false
""");
    }

    private static void Write(string root, string relativePath, string content)
    {
        var path = Path.Combine(root, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
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
