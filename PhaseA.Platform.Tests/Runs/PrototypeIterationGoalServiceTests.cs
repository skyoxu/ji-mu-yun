using System.Text.Json;
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
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);

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
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先修主菜单入口。再修地图移动。最后补提示文案。"));
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WriteProjectReadme(project);
        var contract = new PrototypeContractService().WriteFromRequest(project!, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "contract");
        stateWriter.WriteProjectExecutionGuide(project!, contract, "docs/prototypes/2026-05-20-contract.md", "contract", "prototype-7day-playable", "prototype-run", "succeeded");
        stateWriter.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-baseline" });
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

        var targetGoal = (await store.GetLatestProjectIterationSessionAsync(projectId))!.Goals
            .Single(goal => goal.Title.Contains("field navigation and stable control", StringComparison.Ordinal));
        await CompleteGoalsBeforeAsync(store, projectId, targetGoal.GoalIndex);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var artifacts = await store.ListArtifactsForRunAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.GoalIndex.Should().Be(targetGoal.GoalIndex);
        result.HasMoreGoals.Should().BeTrue();
        result.SessionStatus.Should().Be("paused_for_review");
        run!.RunType.Should().Be("prototype-iteration-goal");
        run.Status.Should().Be("completed");
        run.ProgressStep.Should().Be("completed");
        run.ProgressSubstep.Should().Be("succeeded");
        run.ProgressLabel.Should().Be($"目标 {targetGoal.GoalIndex} 已完成。");
        details.Should().NotBeNull();
        details!.Session.Status.Should().Be("paused_for_review");
        details.Session.LatestEvaluationJson.Should().NotBeNullOrWhiteSpace();
        details.LatestEvaluation.Should().NotBeNull();
        details.LatestEvaluation!.Decision.Should().Be("should_refine_plan");
        details.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).Status.Should().Be("succeeded");
        var codexCommand = runner.Commands.Single(command => command.Arguments.LastOrDefault() == "-");
        codexCommand.StandardInput.Should().Contain("prototype-baseline");
        codexCommand.StandardInput.Should().Contain("Project Execution Guide");
        codexCommand.StandardInput.Should().Contain("Route Recovery Protocol");
        codexCommand.StandardInput.Should().Contain("Prototype Chapter 6 Lite semantics");
        codexCommand.StandardInput.Should().Contain("formal acceptance files");
        codexCommand.StandardInput.Should().Contain("Project prototype contract");
        codexCommand.StandardInput.Should().Contain("Platform hard acceptance for JRPG field navigation");
        codexCommand.StandardInput.Should().Contain("visible playable field");
        codexCommand.StandardInput.Should().Contain("player marker or character");
        codexCommand.StandardInput.Should().Contain("Every movement increases encounter probability by 10% and encounter must happen within 10 steps.");
        codexCommand.StandardInput.Should().Contain("First enemy has 30 HP and 5 ATK.");
        var godotBuildCommand = runner.Commands.Single(command =>
            command.FileName == "dotnet" &&
            command.Arguments.Contains("build") &&
            command.Arguments.Any(argument => argument.EndsWith("GodotGame.csproj", StringComparison.Ordinal)));
        godotBuildCommand.Arguments.Should().NotContain("--no-restore");
        godotBuildCommand.Arguments.Should().Contain("-p:UseSharedCompilation=false");
        godotBuildCommand.Arguments.Should().Contain("-p:NodeReuse=false");
        godotBuildCommand.Arguments.Should().Contain("-m:1");
        godotBuildCommand.Arguments.Should().Contain("-p:BuildInParallel=false");
        godotBuildCommand.Arguments.Should().NotContain(argument => argument.StartsWith("-p:BaseIntermediateOutputPath=", StringComparison.Ordinal));
        godotBuildCommand.Arguments.Should().NotContain(argument => argument.StartsWith("-p:BaseOutputPath=", StringComparison.Ordinal));
        godotBuildCommand.Environment["UseSharedCompilation"].Should().Be("false");
        godotBuildCommand.Environment["MSBUILDDISABLENODEREUSE"].Should().Be("1");
        godotBuildCommand.Environment["TEMP"].Should().Contain("phase-a-validation-temp");
        godotBuildCommand.Environment["PHASEA_VALIDATION_BUILD_ROOT"].Should().Contain("phase-a-validation-build");
        var coreTestCommand = runner.Commands.Single(command =>
            command.FileName == "dotnet" &&
            command.Arguments.Contains("test") &&
            command.Arguments.Any(argument => argument.EndsWith("Game.Core.Tests.csproj", StringComparison.Ordinal)));
        coreTestCommand.Arguments.Should().Contain("-m:1");
        coreTestCommand.Arguments.Should().Contain("-p:BuildInParallel=false");
        coreTestCommand.Arguments.Should().Contain(argument => argument.StartsWith("-p:BaseIntermediateOutputPath=", StringComparison.Ordinal));
        coreTestCommand.Arguments.Should().Contain(argument => argument.StartsWith("-p:BaseOutputPath=", StringComparison.Ordinal));
        coreTestCommand.Arguments.Single(argument => argument.StartsWith("-p:BaseIntermediateOutputPath=", StringComparison.Ordinal)).Should().Contain("phase-a-validation-build");
        coreTestCommand.Arguments.Single(argument => argument.StartsWith("-p:BaseOutputPath=", StringComparison.Ordinal)).Should().Contain("phase-a-validation-build");
        runner.Commands.Should().Contain(command =>
            command.FileName == "dotnet" &&
            command.Arguments.SequenceEqual(new[] { "build-server", "shutdown" }));
        stateWriter.ReadLatestExecuteNextGoalState(project!, targetGoal.GoalIndex).Should().Contain(result.RunId);
        stateWriter.ReadLatestExecuteNextGoalState(project!, targetGoal.GoalIndex).Should().Contain("prototype_contract");
        stateWriter.ReadLatestExecuteNextGoalState(project!, targetGoal.GoalIndex).Should().Contain("project_execution_guide");
        artifacts.Select(a => a.ArtifactType).Should().Contain([
            "prototype-iteration-goal-input",
            "prototype-iteration-goal-result",
            "prototype-iteration-goal-codex-output"
        ]);
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldBlockOldGoals_WhenEvaluationRequiresPlanRefinement()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先修主菜单入口。再修地图移动。最后补提示文案。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var evaluationJson = JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
            "should_refine_plan",
            "Step 1 has the wrong priority.",
            "The playable path must start from Start Adventure into visible map movement and encounter entry.",
            "Regenerate the iteration plan before executing old goals.",
            "Start with Start Adventure -> visible MapScene -> movement -> encounter entry."));
        await store.UpdateProjectIterationSessionStatusAsync(
            details!.Session.SessionId,
            details.Session.Status,
            details.Session.CurrentGoalIndex,
            details.Session.LatestSummary,
            evaluationJson,
            details.Session.CompletedUtc);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("plan_needs_refinement");
        result.RunId.Should().BeEmpty();
        result.GoalIndex.Should().Be(1);
        result.SessionStatus.Should().Be("plan_needs_refinement");
        runner.Commands.Should().BeEmpty();
        refreshed.Should().NotBeNull();
        refreshed!.Session.Status.Should().Be("plan_needs_refinement");
        refreshed.Session.LatestEvaluationJson.Should().Be(evaluationJson);
        refreshed.LatestEvaluation!.Decision.Should().Be("should_refine_plan");
        refreshed.Goals[0].Status.Should().Be("pending");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldRetryRestore_WhenTestFrameworkReferencesArePresentButCompileLooksStale()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        File.WriteAllText(Path.Combine(repoPath, "Game.Core.Tests", "Game.Core.Tests.csproj"), """
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <IsTestProject>true</IsTestProject>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.10.0" />
    <PackageReference Include="xunit" Version="2.7.1" />
    <PackageReference Include="FluentAssertions" Version="6.12.0" />
  </ItemGroup>
</Project>
""");
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Demo Game",
            "Demo Game",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            1,
            "JRPG First Loop: field navigation and stable control",
            "Visible field navigation and stable movement.",
            "Pass when field navigation is visible and stable.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);
        var runner = new RestoreRetryHostedProcessRunner();

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, runner, CancellationToken.None);

        result.Passed.Should().BeTrue(result.Reason);
        runner.Commands.Count(command => command.FileName == "dotnet" && command.Arguments.Contains("test")).Should().Be(2);
        runner.Commands.Should().Contain(command => command.FileName == "dotnet" && command.Arguments.Contains("restore"));
        runner.Commands.SelectMany(command => command.Arguments).Should().Contain(argument => argument.Contains("core-tests-retry", StringComparison.Ordinal));
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldExplainMissingBattleSceneContractItems()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        var battleScript = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "BattleScene.cs");
        File.WriteAllText(battleScript, """
public sealed class BattleScene
{
    public void SetBattleVisible(bool visible) { }
}
""");
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Demo Game",
            "Demo Game",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "JRPG First Loop: battle or challenge resolution",
            "Validate one readable JRPG battle resolution.",
            "Pass when BattleScene reaches clear battle feedback and settlement.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new StepFiveSmokeHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeFalse();
        result.Reason.Should().StartWith("missing_rpg_battle_scene_contract");
        result.Reason.Should().Contain("battle_script_missing_ResolveBattle_or_ResolveAttackTurn");
        result.Reason.Should().Contain("battle_script_missing_BattleFinished");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldRequireBattleScenePlayerAndEnemyTextureAssets()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        File.WriteAllText(Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "BattleScene.tscn"), """
[gd_scene format=3]

[node name="BattleScene" type="Control"]
[node name="AttackButton" type="Button" parent="."]
[node name="PlayerToken" type="ColorRect" parent="."]
[node name="EnemyToken" type="ColorRect" parent="."]
""");
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Demo Game",
            "Demo Game",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "JRPG First Loop: battle or challenge resolution",
            "Validate one readable JRPG battle resolution.",
            "Pass when BattleScene reaches clear battle feedback and settlement.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeFalse();
        result.Reason.Should().StartWith("missing_rpg_battle_scene_contract");
        result.Reason.Should().Contain("battle_scene_missing_RpgPlayerAsset_Texture2D");
        result.Reason.Should().Contain("battle_scene_missing_RpgEnemyAsset_Texture2D");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireBattleScene_ForGenericFinalGoal_WhenContractHasNoCombatSemantics()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        File.Delete(Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "BattleScene.tscn"));
        File.Delete(Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "BattleScene.cs"));
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Cozy Town",
            "Cozy Town",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                Slug: "cozy-town",
                GameName: "Cozy Town",
                GameType: "rpg",
                GameTypeSource: "RPG",
                Hypothesis: "Validate a town opening with exploration and objective progress.",
                CorePlayerFantasy: "Walk through a village and help an elder.",
                MinimumPlayableLoop: "Start Adventure, walk to the elder, inspect the keepsake, and update the objective.",
                SuccessCriteria: ["Objective progress is visible."],
                GameFeature: "NPC dialogue and keepsake discovery.",
                CoreGameplayLoop: "Explore the town, talk, inspect, and continue.",
                WinFailConditions: "No failure state in this first loop.",
                Confirm: true),
            "docs/prototypes/2026-05-20-cozy-town.md",
            "cozy-town");
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "JRPG First Loop: final first-loop acceptance",
            "Validate selected capabilities, project contract, Godot validation, and package readiness.",
            "Final acceptance passes.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Reason.Should().NotContain("BattleScene");
        result.Reason.Should().NotContain("battle", because: "non-combat JRPG final acceptance must not require BattleScene contracts");
        result.Reason.Should().NotContain("enemy", because: "non-combat JRPG final acceptance must not require enemy asset contracts");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldIgnoreTemplateBattleWords_ForGenericFinalGoal_WhenContractHasNoCombatSemantics()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        File.Delete(Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "BattleScene.tscn"));
        File.Delete(Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "BattleScene.cs"));
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Cozy Town",
            "Cozy Town",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                Slug: "cozy-town",
                GameName: "Cozy Town",
                GameType: "rpg",
                GameTypeSource: "RPG",
                Hypothesis: "Validate a town opening with exploration and objective progress.",
                CorePlayerFantasy: "Walk through a village and help an elder.",
                MinimumPlayableLoop: "Start Adventure, walk to the elder, inspect the keepsake, and update the objective.",
                SuccessCriteria: ["Objective progress is visible."],
                GameFeature: "NPC dialogue and keepsake discovery.",
                CoreGameplayLoop: "Explore the town, talk, inspect, and continue.",
                WinFailConditions: "No failure state in this first loop.",
                Confirm: true),
            "docs/prototypes/2026-05-20-cozy-town.md",
            "cozy-town");
        File.WriteAllText(
            Path.Combine(repoPath, "README.md"),
            "Template recovery note: RPG battle scene and BattleScene are mentioned only as route examples.\n");
        var iterationStatePath = Path.Combine(project.MetaPath, "routes", "iteration-plan");
        Directory.CreateDirectory(iterationStatePath);
        File.WriteAllText(
            Path.Combine(iterationStatePath, "latest.json"),
            """
            {
              "route": "iteration-plan",
              "project_execution_guide": "Template protocol mentions BattleScene and combat examples.",
              "goals": [
                {
                  "title": "JRPG First Loop: opening context and player objective",
                  "description": "Show the starting town context and objective.",
                  "acceptanceHint": "Opening objective is readable."
                },
                {
                  "title": "JRPG First Loop: field navigation and stable control",
                  "description": "Start Adventure opens a visible town map with stable movement.",
                  "acceptanceHint": "Map movement works."
                },
                {
                  "title": "JRPG First Loop: quest or story progress",
                  "description": "Talking to the elder updates the objective.",
                  "acceptanceHint": "Story progress is visible."
                },
                {
                  "title": "JRPG First Loop: final first-loop acceptance",
                  "description": "Validate selected non-combat capabilities, project contract, Godot validation, package readiness, and ignore this template-only BattleScene example.",
                  "acceptanceHint": "Final acceptance passes."
                }
              ]
            }
            """);
        var prototypeStatePath = Path.Combine(project.MetaPath, "routes", "prototype");
        Directory.CreateDirectory(prototypeStatePath);
        File.WriteAllText(
            Path.Combine(prototypeStatePath, "latest.json"),
            """
            {
              "route": "prototype",
              "project_execution_guide": "Template protocol mentions BattleScene and combat examples.",
              "prototype_completion": {
                "smoke_scene": "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
              }
            }
            """);
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "JRPG First Loop: final first-loop acceptance",
            "Validate selected capabilities, project contract, Godot validation, and package readiness.",
            "Final acceptance passes.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Reason.Should().NotContain("BattleScene");
        result.Reason.Should().NotContain("battle", because: "template route state must not activate battle acceptance for a non-combat contract");
        result.Reason.Should().NotContain("enemy", because: "template route state must not activate enemy asset acceptance for a non-combat contract");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldIgnoreLegacyIterationPlanBattleWords_WhenStateHasNoSessionId()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Cozy Town",
            "Cozy Town",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                Slug: "cozy-town",
                GameName: "Cozy Town",
                GameType: "rpg",
                GameTypeSource: "RPG",
                Hypothesis: "Validate a town opening with exploration and objective progress.",
                CorePlayerFantasy: "Walk through a village and help an elder.",
                MinimumPlayableLoop: "Start Adventure, walk to the elder, inspect the keepsake, and update the objective.",
                SuccessCriteria: ["Objective progress is visible."],
                GameFeature: "NPC dialogue and keepsake discovery.",
                CoreGameplayLoop: "Explore the town, talk, inspect, and continue.",
                WinFailConditions: "No failure state in this first loop.",
                Confirm: true),
            "docs/prototypes/2026-05-20-cozy-town.md",
            "cozy-town");
        var iterationStatePath = Path.Combine(project.MetaPath, "routes", "iteration-plan");
        Directory.CreateDirectory(iterationStatePath);
        File.WriteAllText(
            Path.Combine(iterationStatePath, "latest.json"),
            """
            {
              "route": "iteration-plan",
              "source_message": "Old template text asks for BattleScene, enemy assets, combat, reward choice, and RewardOptions.Count.",
              "regeneration_guidance": "Legacy guidance says to add one battle and a reward return.",
              "selected_capabilities": [
                "conflict_entry",
                "battle_or_challenge_resolution",
                "growth_feedback"
              ]
            }
            """);
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "current-session",
            5,
            "JRPG First Loop: final first-loop acceptance",
            "Validate selected town exploration capabilities, project contract, Godot validation, and package readiness.",
            "Final acceptance passes without combat requirements.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Kind.Should().Be("jrpg-final-first-loop-acceptance");
        result.Reason.Should().NotContain("BattleScene");
        result.Reason.Should().NotContain("battle", because: "legacy iteration-plan state without session_id must not activate battle acceptance");
        result.Reason.Should().NotContain("enemy", because: "legacy iteration-plan state without session_id must not activate enemy asset acceptance");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireBattleScene_ForGenericRpgFinalGoal_WhenContractHasNoCombatSemantics()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Cozy Town",
            "Cozy Town",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                Slug: "cozy-town",
                GameName: "Cozy Town",
                GameType: "rpg",
                GameTypeSource: "RPG",
                Hypothesis: "Validate a town opening with exploration and objective progress.",
                CorePlayerFantasy: "Walk through a village and help an elder.",
                MinimumPlayableLoop: "Start Adventure, walk to the elder, inspect the keepsake, and update the objective.",
                SuccessCriteria: ["Objective progress is visible."],
                GameFeature: "NPC dialogue and keepsake discovery.",
                CoreGameplayLoop: "Explore the town, talk, inspect, and continue.",
                WinFailConditions: "No failure state in this first loop.",
                Confirm: true),
            "docs/prototypes/2026-05-20-cozy-town.md",
            "cozy-town");
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "RPG full playable prototype acceptance",
            "Validate project contract, Godot validation, and package readiness.",
            "Final acceptance passes.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Kind.Should().Be("rpg-final-full-playable-acceptance");
        result.Reason.Should().NotContain("BattleScene");
        result.Reason.Should().NotContain("battle", because: "generic RPG final acceptance must follow the non-combat contract");
        result.Reason.Should().NotContain("enemy", because: "generic RPG final acceptance must not require enemy assets for a non-combat contract");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldUseSelectedCapabilities_ForGenericRpgFinalGoal()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Cozy Town",
            "Cozy Town",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                Slug: "cozy-town",
                GameName: "Cozy Town",
                GameType: "rpg",
                GameTypeSource: "RPG",
                Hypothesis: "Validate a town opening with exploration and objective progress.",
                CorePlayerFantasy: "Walk through a village and help an elder.",
                MinimumPlayableLoop: "Start Adventure, walk to the elder, inspect the keepsake, and update the objective.",
                SuccessCriteria: ["Objective progress is visible."],
                GameFeature: "NPC dialogue and keepsake discovery.",
                CoreGameplayLoop: "Explore the town, talk, inspect, and continue.",
                WinFailConditions: "No failure state in this first loop.",
                Confirm: true),
            "docs/prototypes/2026-05-20-cozy-town.md",
            "cozy-town");
        var iterationStatePath = Path.Combine(project.MetaPath, "routes", "iteration-plan");
        Directory.CreateDirectory(iterationStatePath);
        File.WriteAllText(
            Path.Combine(iterationStatePath, "latest.json"),
            """
            {
              "route": "iteration-plan",
              "selected_capabilities": [
                "opening_context",
                "field_navigation",
                "quest_or_story_progress",
                "final_first_loop_acceptance"
              ],
              "project_execution_guide": "Template examples mention BattleScene, combat, reward choice, RewardOptions.Count, and enemy assets.",
              "goals": [
                {
                  "title": "RPG full playable prototype acceptance",
                  "description": "Validate selected non-combat capabilities and ignore template-only BattleScene examples.",
                  "acceptanceHint": "Final acceptance passes."
                }
              ]
            }
            """);
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "RPG full playable prototype acceptance",
            "Validate selected capabilities, project contract, Godot validation, and package readiness.",
            "Final acceptance passes.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Kind.Should().Be("rpg-final-full-playable-acceptance");
        result.Reason.Should().NotContain("BattleScene");
        result.Reason.Should().NotContain("RewardOptions");
        result.Reason.Should().NotContain("enemy");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldRequireBattleScene_WhenCurrentSelectedCapabilitiesIncludeBattle()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Cozy Town",
            "Cozy Town",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                Slug: "cozy-town",
                GameName: "Cozy Town",
                GameType: "rpg",
                GameTypeSource: "RPG",
                Hypothesis: "Validate a town opening with exploration and objective progress.",
                CorePlayerFantasy: "Walk through a village and help an elder.",
                MinimumPlayableLoop: "Start Adventure, walk to the elder, inspect the keepsake, and update the objective.",
                SuccessCriteria: ["Objective progress is visible."],
                GameFeature: "NPC dialogue and keepsake discovery.",
                CoreGameplayLoop: "Explore the town, talk, inspect, and continue.",
                WinFailConditions: "No failure state in this first loop.",
                Confirm: true),
            "docs/prototypes/2026-05-20-cozy-town.md",
            "cozy-town");
        var iterationStatePath = Path.Combine(project.MetaPath, "routes", "iteration-plan");
        Directory.CreateDirectory(iterationStatePath);
        File.WriteAllText(
            Path.Combine(iterationStatePath, "latest.json"),
            """
            {
              "route": "iteration-plan",
              "session_id": "session-id",
              "selected_capabilities": [
                "opening_context",
                "field_navigation",
                "battle_or_challenge_resolution",
                "final_first_loop_acceptance"
              ],
              "goals": [
                {
                  "title": "JRPG First Loop: final first-loop acceptance",
                  "description": "Validate selected capabilities and package readiness.",
                  "acceptanceHint": "Final acceptance passes."
                }
              ]
            }
            """);
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "JRPG First Loop: final first-loop acceptance",
            "Validate selected capabilities, project contract, Godot validation, and package readiness.",
            "Final acceptance passes.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Kind.Should().Be("jrpg-final-first-loop-acceptance");
        result.Reason.Should().Contain("missing_rpg_battle_scene", because: "current selected_capabilities are the final acceptance authority");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldIgnoreStaleSelectedCapabilities_ForGenericRpgFinalGoal()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Battle Route",
            "Battle Route",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var iterationStatePath = Path.Combine(project.MetaPath, "routes", "iteration-plan");
        Directory.CreateDirectory(iterationStatePath);
        File.WriteAllText(
            Path.Combine(iterationStatePath, "latest.json"),
            """
            {
              "route": "iteration-plan",
              "session_id": "stale-session",
              "selected_capabilities": [
                "opening_context",
                "field_navigation",
                "final_first_loop_acceptance"
              ]
            }
            """);
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "current-session",
            5,
            "RPG full playable prototype acceptance",
            "Validate the visible enemy encounter, BattleScene, reward choice, return to the map, project contract, Godot validation, and package readiness.",
            "Final acceptance passes after one battle and reward return.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Kind.Should().Be("rpg-final-full-playable-acceptance");
        result.Reason.Should().Contain("missing_rpg_battle_scene");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldIgnoreIterationAnalysisSummary_ForGenericRpgFinalGoal()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Cozy Town",
            "Cozy Town",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                Slug: "cozy-town",
                GameName: "Cozy Town",
                GameType: "rpg",
                GameTypeSource: "RPG",
                Hypothesis: "Validate a town opening with exploration and objective progress.",
                CorePlayerFantasy: "Walk through a village and help an elder.",
                MinimumPlayableLoop: "Start Adventure, walk to the elder, inspect the keepsake, and update the objective.",
                SuccessCriteria: ["Objective progress is visible."],
                GameFeature: "NPC dialogue and keepsake discovery.",
                CoreGameplayLoop: "Explore the town, talk, inspect, and continue.",
                WinFailConditions: "No failure state in this first loop.",
                Confirm: true),
            "docs/prototypes/2026-05-20-cozy-town.md",
            "cozy-town");
        var iterationStatePath = Path.Combine(project.MetaPath, "routes", "iteration-plan");
        Directory.CreateDirectory(iterationStatePath);
        File.WriteAllText(
            Path.Combine(iterationStatePath, "latest.json"),
            """
            {
              "route": "iteration-plan",
              "analysisSummary": "Template summary says BattleScene, combat, reward choice, RewardOptions.Count, and enemy assets are missing."
            }
            """);
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "RPG full playable prototype acceptance",
            "Validate selected non-combat capabilities, project contract, Godot validation, and package readiness.",
            "Final acceptance passes without combat or reward requirements.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Kind.Should().Be("rpg-final-full-playable-acceptance");
        result.Reason.Should().NotContain("BattleScene");
        result.Reason.Should().NotContain("RewardOptions");
        result.Reason.Should().NotContain("enemy");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldIgnorePrototypeSummaryBattleWords_ForGenericRpgFinalGoal()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Cozy Town",
            "Cozy Town",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                Slug: "cozy-town",
                GameName: "Cozy Town",
                GameType: "rpg",
                GameTypeSource: "RPG",
                Hypothesis: "Validate a town opening with exploration and objective progress.",
                CorePlayerFantasy: "Walk through a village and help an elder.",
                MinimumPlayableLoop: "Start Adventure, walk to the elder, inspect the keepsake, and update the objective.",
                SuccessCriteria: ["Objective progress is visible."],
                GameFeature: "NPC dialogue and keepsake discovery.",
                CoreGameplayLoop: "Explore the town, talk, inspect, and continue.",
                WinFailConditions: "No failure state in this first loop.",
                Confirm: true),
            "docs/prototypes/2026-05-20-cozy-town.md",
            "cozy-town");
        var prototypeStatePath = Path.Combine(project.MetaPath, "routes", "prototype");
        Directory.CreateDirectory(prototypeStatePath);
        File.WriteAllText(
            Path.Combine(prototypeStatePath, "latest.json"),
            """
            {
              "route": "prototype",
              "prototype_summary": "Template summary says BattleScene, combat, reward choice, RewardOptions.Count, and enemy assets are missing.",
              "completion_summary": "Repair suggestion mentions battle reward selected and enemy presentation as examples.",
              "prototype_completion": {
                "summary": "BattleScene and reward flow are examples only.",
                "smoke_scene": "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
              }
            }
            """);
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "RPG full playable prototype acceptance",
            "Validate project contract, Godot validation, and package readiness.",
            "Final acceptance passes.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Kind.Should().Be("rpg-final-full-playable-acceptance");
        result.Reason.Should().NotContain("BattleScene");
        result.Reason.Should().NotContain("RewardOptions");
        result.Reason.Should().NotContain("enemy");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldIgnorePrototypeMetadataBattleWords_ForGenericRpgFinalGoal()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Cozy Town",
            "Cozy Town",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                Slug: "cozy-town",
                GameName: "Cozy Town",
                GameType: "rpg",
                GameTypeSource: "RPG",
                Hypothesis: "Validate a town opening with exploration and objective progress.",
                CorePlayerFantasy: "Walk through a village and help an elder.",
                MinimumPlayableLoop: "Start Adventure, walk to the elder, inspect the keepsake, and update the objective.",
                SuccessCriteria: ["Objective progress is visible."],
                GameFeature: "NPC dialogue and keepsake discovery.",
                CoreGameplayLoop: "Explore the town, talk, inspect, and continue.",
                WinFailConditions: "No failure state in this first loop.",
                Confirm: true),
            "docs/prototypes/2026-05-20-cozy-town.md",
            "cozy-town");
        var prototypeStatePath = Path.Combine(project.MetaPath, "routes", "prototype");
        Directory.CreateDirectory(prototypeStatePath);
        File.WriteAllText(
            Path.Combine(prototypeStatePath, "latest.json"),
            """
            {
              "route": "prototype",
              "game_name": "BattleScene Combat Reward",
              "game_type": "enemy encounter RPG",
              "game_type_source": "battle reward template",
              "source_message": "Template example says create BattleScene, enemy assets, and RewardOptions.Count.",
              "prototype_completion": {
                "smoke_scene": "res://Game.Godot/Prototypes/dq-rpg/BattleScene.tscn"
              }
            }
            """);
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "RPG full playable prototype acceptance",
            "Validate project contract, Godot validation, and package readiness.",
            "Final acceptance passes.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Kind.Should().Be("rpg-final-full-playable-acceptance");
        result.Reason.Should().NotContain("BattleScene");
        result.Reason.Should().NotContain("battle", because: "prototype metadata must not activate battle acceptance");
        result.Reason.Should().NotContain("enemy", because: "prototype metadata must not activate enemy asset acceptance");
        result.Reason.Should().NotContain("RewardOptions");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireBattleScene_ForNonCombatChallengeResolution()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Puzzle Shrine",
            "Puzzle Shrine",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                Slug: "puzzle-shrine",
                GameName: "Puzzle Shrine",
                GameType: "rpg",
                GameTypeSource: "RPG",
                Hypothesis: "Validate a shrine puzzle challenge without a combat scene.",
                CorePlayerFantasy: "Explore a shrine, read clues, solve an obstacle, and open the next route.",
                MinimumPlayableLoop: "Start Adventure, walk to the shrine, inspect clues, resolve the obstacle, and continue to the next room.",
                SuccessCriteria: ["Obstacle resolution is readable."],
                GameFeature: "Puzzle challenge and route unlock.",
                CoreGameplayLoop: "Explore, inspect, solve, and continue.",
                WinFailConditions: "No combat failure state in this first loop.",
                Confirm: true),
            "docs/prototypes/2026-05-20-puzzle-shrine.md",
            "puzzle-shrine");
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "JRPG First Loop: battle or challenge resolution",
            "Validate a readable peaceful puzzle challenge resolution.",
            "Pass when the obstacle resolves with clear success feedback.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue();
        result.Kind.Should().Be("jrpg-battle-or-challenge-resolution");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireEnemyOrEncounter_ForFieldNavigationOnly()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteMapEntryWithoutEnemyOrEncounter(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Cozy Town",
            "Cozy Town",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            2,
            "JRPG First Loop: field navigation and stable control",
            "Validate Start Adventure to visible town map and stable movement.",
            "Pass when the town map opens and movement is stable.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new StepFiveSmokeHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue(result.Reason);
        result.Kind.Should().Be("jrpg-field-navigation-stable-control");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireEncounterRewardMarker_ForNegatedJrpgConflictEntry()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteMapEntryWithoutEnemyOrEncounter(repoPath);
        WriteCoreMarkersWithoutBattleOrReward(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            2,
            "JRPG First Loop: conflict entry trigger",
            "Validate the obstacle entry as a town gate choice with no encounter and without combat.",
            "Pass when map movement reaches the obstacle entry without enemy work.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue(result.Reason);
        result.Kind.Should().Be("jrpg-conflict-entry-trigger");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireRewardFlow_ForReturnContinueOnlyFinalAcceptance()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteMainScriptWithoutRewardFlow(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        new PrototypeContractService().WriteFromRequest(
            project,
            new PrototypeWorkflowRequest(
                Slug: "town-errand",
                GameName: "Town Errand",
                GameType: "rpg",
                GameTypeSource: "RPG",
                Hypothesis: "Validate a town errand loop that continues after story progress.",
                CorePlayerFantasy: "Walk through town, talk to an elder, inspect a keepsake, and continue to the next objective.",
                MinimumPlayableLoop: "Start Adventure, navigate town, complete the errand, and continue to the next playable state.",
                SuccessCriteria: ["The next objective is visible."],
                GameFeature: "NPC dialog and objective continuation.",
                CoreGameplayLoop: "Explore, interact, update objective, and continue.",
                WinFailConditions: "No failure state in this first loop.",
                Confirm: true),
            "docs/prototypes/2026-05-20-town-errand.md",
            "town-errand");
        var iterationStatePath = Path.Combine(project.MetaPath, "routes", "iteration-plan");
        Directory.CreateDirectory(iterationStatePath);
        File.WriteAllText(
            Path.Combine(iterationStatePath, "latest.json"),
            """
            {
              "route": "iteration-plan",
              "selected_capabilities": [
                "opening_context",
                "field_navigation",
                "interaction_discovery",
                "return_or_continue_loop",
                "quest_or_story_progress",
                "final_first_loop_acceptance"
              ]
            }
            """);
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            6,
            "JRPG First Loop: final first-loop acceptance",
            "Validate selected town errand capabilities, contract traceability, continuation, Godot validation, and package readiness.",
            "Final first-loop acceptance passes with objective continuation.",
            "pending",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        (result.Reason ?? "").Should().NotStartWith("missing_rpg_reward_flow_contract");
        (result.Reason ?? "").Should().NotContain("RewardOptions");
        (result.Reason ?? "").Should().NotContain("ApplyReward");
        (result.Reason ?? "").Should().NotContain("Battle reward selected");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireRewardFlow_ForReturnContinueCapabilityTitle()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteMainScriptWithoutRewardFlow(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "JRPG First Loop: return or continue loop",
            "Continue to the next playable town objective after the errand resolves.",
            "Pass when the map remains visible, player input remains usable, and the next objective is clear.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        (result.Reason ?? "").Should().NotStartWith("missing_rpg_reward_flow_contract");
        (result.Reason ?? "").Should().NotContain("RewardOptions");
        (result.Reason ?? "").Should().NotContain("ApplyReward");
        (result.Reason ?? "").Should().NotContain("Battle reward selected");
        result.Kind.Should().Be("jrpg-return-or-continue-loop");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireReturnToMapMarker_ForSemanticContinueLoop()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteMainScriptWithoutRewardFlow(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "JRPG First Loop: next objective continuation",
            "Validate continue loop to the next playable town objective after the errand resolves.",
            "Pass when the map remains visible, player input remains usable, and the next objective is clear.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Reason.Should().NotContain("Return to the map");
        result.Reason.Should().NotContain("missing_marker=Return to the map");
        result.Kind.Should().Be("jrpg-return-or-continue-loop");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireRewardFlow_ForStoryConsequenceFeedback()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteMainScriptWithoutRewardFlow(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "JRPG First Loop: growth, reward, or consequence feedback",
            "Show a story consequence after the elder receives the keepsake.",
            "Pass when the objective text changes and the player understands the story consequence.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue(result.Reason);
        result.Kind.Should().Be("jrpg-growth-reward-consequence-feedback");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireRewardFlow_ForSemanticStoryConsequenceFeedback()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteMainScriptWithoutRewardFlow(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "JRPG First Loop: elder story update",
            "Show consequence feedback after the elder receives the keepsake.",
            "Pass when the objective text changes and the player understands the story consequence.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue();
        result.Kind.Should().Be("jrpg-growth-reward-consequence-feedback");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotTreatExploreAsExpRewardFlow()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteMainScriptWithoutRewardFlow(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "JRPG First Loop: exploration consequence",
            "Explore the town and show consequence feedback after the elder receives the keepsake.",
            "Pass when exploration changes the objective text without reward choices.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue(result.Reason);
        result.Kind.Should().Be("jrpg-growth-reward-consequence-feedback");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotTreatItemizedAsItemRewardFlow()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteMainScriptWithoutRewardFlow(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "JRPG First Loop: itemized story consequence",
            "Show consequence feedback as an itemized checklist after the elder receives the keepsake.",
            "Pass when the itemized checklist changes objective text.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue(result.Reason);
        result.Kind.Should().Be("jrpg-growth-reward-consequence-feedback");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireBattleScene_ForNonCombatFailurePath()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteMainScriptWithoutRewardFlow(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Puzzle Shrine",
            "Puzzle Shrine",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "JRPG First Loop: puzzle failure path",
            "Validate failure path for an incorrect shrine answer without combat.",
            "Pass when failure feedback is readable and the player can continue exploring.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Reason.Should().NotContain("BattleScene");
        result.Reason.Should().NotContain("battle_scene");
        result.Kind.Should().Be("jrpg-loop-stability");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireRewardFlow_WhenRewardLoopIsNegated()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteMainScriptWithoutRewardFlow(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "JRPG First Loop: no reward loop continuation",
            "Validate continuation without reward loop after the errand resolves.",
            "Pass when the next objective is clear without reward choices.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        (result.Reason ?? "").Should().NotStartWith("missing_rpg_reward_flow_contract");
        (result.Reason ?? "").Should().NotContain("RewardOptions");
        (result.Reason ?? "").Should().NotContain("ApplyReward");
        (result.Reason ?? "").Should().NotContain("Battle reward selected");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireBattleOrReward_ForNonCombatSceneSwitching()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteMainScriptWithoutRewardFlow(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "JRPG First Loop: main prototype scene switching",
            "Validate main prototype scene switching for a non-combat town route without reward choices.",
            "Pass when Start Adventure opens the map and the player can continue exploring.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue(result.Reason);
        result.Kind.Should().Be("rpg-step4-main-loop-scene-switching");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldRequireBattleScene_WhenPeacefulContextStillMentionsBattle()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Peaceful Frontier",
            "Peaceful Frontier",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "JRPG First Loop: battle or challenge resolution",
            "Validate a peaceful town intro before one readable battle against a monster.",
            "Pass when BattleScene resolves the first battle.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Kind.Should().Be("jrpg-battle-or-challenge-resolution");
        result.Reason.Should().Contain("missing_rpg_battle_scene_contract");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireBattleScene_ForGenericBattleFallback_WhenBattleIsNegated()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "RPG settlement cleanup",
            "Validate story settlement without battle settlement and without combat.",
            "Pass when the story settlement is readable.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue(result.Reason);
        result.Kind.Should().Be("rpg-step3-battlescene-settlement");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireEncounterRewardMarker_WhenEncounterIsNegated()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteCoreMarkersWithoutBattleOrReward(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "RPG encounter cleanup",
            "Validate map continuation with no encounter and without combat.",
            "Pass when map movement is represented.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue(result.Reason);
        result.Kind.Should().Be("rpg-step2-encounter-trigger");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldGuardLegacyRpgStepTitles_WhenCombatAndRewardAreNegated()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteCoreMarkersWithoutBattleOrReward(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var step3 = new ProjectIterationGoalSnapshot(
            "goal-step3",
            "session-id",
            3,
            "RPG Step 3: BattleScene visualization and settlement validation",
            "No battle scene; validate peaceful story settlement only.",
            "Pass without combat.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);
        var step4 = new ProjectIterationGoalSnapshot(
            "goal-step4",
            "session-id",
            4,
            "RPG Step 4: reward 3-choice understandability validation",
            "No reward choices; validate continuation feedback only.",
            "Pass without reward choices.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var step3Result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, step3, new RestoreRetryHostedProcessRunner(), CancellationToken.None);
        var step4Result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, step4, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        step3Result.Passed.Should().BeTrue(step3Result.Reason);
        step3Result.Kind.Should().Be("rpg-step3-battlescene-settlement");
        step4Result.Passed.Should().BeTrue(step4Result.Reason);
        step4Result.Kind.Should().Be("rpg-step4-reward-choice-readability");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireBattleOrRewardMarkers_ForNonCombatContractAlignment()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteCoreMarkersWithoutBattleOrReward(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Errand",
            "Town Errand",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "JRPG First Loop: contract traceability",
            "Validate contract traceability for a no combat town request without rewards.",
            "Pass when movement and objective contract values are represented.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue(result.Reason);
        result.Kind.Should().Be("rpg-contract-alignment");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotRequireBattleOrRewardMarkers_ForNonCombatAssetAndUiValidation()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteCoreMarkersWithoutBattleOrReward(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Peaceful Library",
            "Peaceful Library",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "JRPG First Loop: peaceful assets and UI validation",
            "Validate assets and UI for a peaceful dialogue-only library route with no combat, no loot, and no leveling.",
            "Pass when map/player assets and the core UI are represented.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue(result.Reason);
        result.Kind.Should().Be("rpg-asset-usage-validation");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldNotTreatGuidanceAsUiAssetValidation()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        DeleteBattleSceneFiles(repoPath);
        WriteCoreMarkersWithoutBattleOrReward(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Town Guide",
            "Town Guide",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            5,
            "JRPG First Loop: story guidance update",
            "Use project execution guide and route guidance to validate story progress after talking to the elder.",
            "Pass when the Quest objective is represented without any asset validation requirement.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Kind.Should().Be("jrpg-quest-story-progress");
        result.Reason.Should().NotContain("rpg_asset", because: "guide/guidance must not trigger the UI asset route");
        result.Reason.Should().NotContain("asset_usage", because: "guide/guidance must not trigger the UI asset route");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldAcceptMainScriptOwnedRewardPanel()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        WriteMainScriptOwnedRewardPanel(repoPath);
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Demo Game",
            "Demo Game",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            6,
            "JRPG First Loop: growth, reward, or consequence feedback",
            "Validate reward choice and return feedback.",
            "Pass when a visible reward choice updates state and returns to map.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue();
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldExplainMissingRewardFlowContractItems()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        EnsureRpgAcceptanceMarkers(repoPath);
        EnsureRpgSmokeSceneFile(repoPath);
        var scriptPath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts");
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), """
public sealed class DqRpgPrototype
{
    private void OnBattleFinished(bool victory) { RefreshView(); }
    private void RefreshView() { }
}
""");
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Demo Game",
            "Demo Game",
            "RPG",
            "rpg",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            6,
            "JRPG First Loop: growth, reward, or consequence feedback",
            "Validate reward choice and return feedback.",
            "Pass when a visible reward choice updates state and returns to map.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeFalse();
        result.Reason.Should().StartWith("missing_rpg_reward_flow_contract");
        result.Reason.Should().Contain("reward_flow_missing_reward_list_guard");
        result.Reason.Should().Contain("reward_flow_missing_reward_entry");
        result.Reason.Should().Contain("reward_flow_missing_return_to_map_after_reward");
    }

    [Fact]
    public async Task GoalAcceptanceValidator_ShouldAcceptSurvivorsLikeMarkersOutsideRpgLoopFiles()
    {
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        var repoPath = workspaceRoot.Path;
        var coreDir = Path.Combine(repoPath, "Game.Core", "Prototypes");
        var testsDir = Path.Combine(repoPath, "Game.Core.Tests", "Prototypes");
        Directory.CreateDirectory(coreDir);
        Directory.CreateDirectory(testsDir);
        File.WriteAllText(Path.Combine(coreDir, "SurvivorsLikePrototypeLoop.cs"), """
public sealed class SurvivorsLikePrototypeLoop
{
    public const string AutoAttack = "AutoAttack";
    public const string WeaponCooldown = "WeaponCooldown";
    public const string Hit = "Hit";
}
""");
        File.WriteAllText(Path.Combine(testsDir, "SurvivorsLikePrototypeLoopTests.cs"), """
public sealed class SurvivorsLikePrototypeLoopTests
{
    // AutoAttack WeaponCooldown Hit
}
""");
        var project = new ProjectSnapshot(
            "project-id",
            "account-id",
            "Vampire Demo",
            "Vampire Demo",
            "Vampire Survivors-like",
            "godot-prototype-default",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-id",
            workspaceRoot.Path,
            repoPath,
            Path.Combine(repoPath, "runtime"),
            Path.Combine(repoPath, "meta"));
        var goal = new ProjectIterationGoalSnapshot(
            "goal-id",
            "session-id",
            4,
            "Vampire Survivors-like First Loop: auto-attack or core weapon loop",
            "Validate repeated core weapon behavior.",
            "Pass only when the core weapon repeatedly attacks and hits spawned enemies.",
            "needs_fix",
            null,
            DateTimeOffset.UtcNow.ToString("O"),
            DateTimeOffset.UtcNow.ToString("O"),
            null);

        var result = await PrototypeGoalAcceptanceValidator.ValidateAsync(project, goal, new RestoreRetryHostedProcessRunner(), CancellationToken.None);

        result.Passed.Should().BeTrue();
        result.Kind.Should().Be("survivorslike-auto-attack-core-weapon-loop");
    }

    [Theory]
    [InlineData("field navigation and stable control", "jrpg-field-navigation-stable-control")]
    [InlineData("conflict entry trigger", "jrpg-conflict-entry-trigger")]
    [InlineData("battle or challenge resolution", "jrpg-battle-or-challenge-resolution")]
    public async Task ExecuteNextAsync_ShouldUseRpgRouteAcceptanceKinds_ForNavigationFirstSteps(
        string targetTitle,
        string expectedAcceptanceKind)
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG prototype through field movement, a visible encounter trigger, one battle, reward feedback, and return to the map."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.Title.Contains(targetTitle, StringComparison.Ordinal));
        await CompleteGoalsBeforeAsync(store, projectId, targetGoal.GoalIndex);

        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WriteProjectReadme(project);
        new PrototypeContractService().WriteFromRequest(project, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "contract");
        stateWriter.WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            marker = "prototype-baseline",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);
        result.Status.Should().Be("completed");
        result.GoalIndex.Should().Be(targetGoal.GoalIndex);
        refreshed!.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).Status.Should().Be("succeeded");
        run!.EvidenceJson.Should().Contain($"\"acceptance_validation\":\"{expectedAcceptanceKind}\"");
        run.EvidenceJson.Should().Contain("\"acceptance_validation_status\":\"passed\"");
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldUseJrpgGrowthAcceptanceKind_WhenRewardRuntimeMarkersPass()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG prototype through movement, encounter, battle, reward, and return to the map."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.Title.Contains("growth, reward, or consequence feedback", StringComparison.Ordinal));
        var now = DateTimeOffset.UtcNow.ToString("O");
        foreach (var goal in details.Goals.Where(goal => goal.GoalIndex < targetGoal.GoalIndex))
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "succeeded", $"Goal {goal.GoalIndex} already completed.", now);
        }

        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        EnsureRpgRewardRuntimeMarkers(project.RepoPath);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WriteProjectReadme(project);
        new PrototypeContractService().WriteFromRequest(project, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "contract");
        stateWriter.WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            marker = "prototype-baseline",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var runner = new StepFiveSmokeHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        run!.EvidenceJson.Should().Contain("\"acceptance_validation_status\":\"passed\"");
        run.EvidenceJson.Should().Contain("\"godot_smoke_validation\":{\"required\":true,\"passed\":true");
        result.Status.Should().Be("completed");
        result.GoalIndex.Should().Be(targetGoal.GoalIndex);
        refreshed!.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).Status.Should().Be("succeeded");
        run.EvidenceJson.Should().Contain("\"acceptance_validation\":\"jrpg-growth-reward-consequence-feedback\"");
        run.EvidenceJson.Should().Contain("\"acceptance_validation_status\":\"passed\"");
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldAcceptCurrentRpgMapEntryContractShape()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Build the RPG map entry step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.Title.Contains("field navigation and stable control", StringComparison.Ordinal));
        await CompleteGoalsBeforeAsync(store, projectId, targetGoal.GoalIndex);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        WriteCurrentRpgMapEntryShape(project.RepoPath);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WriteProjectReadme(project);
        stateWriter.WritePrototypeState(project, new { route = "prototype-7day-playable", marker = "prototype-baseline" });
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);
        result.Status.Should().Be("completed");
        result.GoalIndex.Should().Be(targetGoal.GoalIndex);
        refreshed!.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).Status.Should().Be("succeeded");
        run!.EvidenceJson.Should().Contain("\"acceptance_validation\":\"jrpg-field-navigation-stable-control\"");
        run.EvidenceJson.Should().Contain("\"acceptance_validation_status\":\"passed\"");
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldRunGodotSmoke_ForRpgFinalStep()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG prototype through the strict contract steps."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.Title.Contains("final first-loop acceptance", StringComparison.Ordinal));
        await CompleteGoalsBeforeAsync(store, projectId, targetGoal.GoalIndex);

        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WriteProjectReadme(project!);
        new PrototypeContractService().WriteFromRequest(project!, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "contract");
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
        result.GoalIndex.Should().Be(targetGoal.GoalIndex);
        refreshed!.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).Status.Should().Be("succeeded");
        runner.Commands.Should().Contain(command => command.FileName == "dotnet" && command.Arguments.Contains("test"));
        runner.Commands.Should().Contain(command => command.FileName == "dotnet" && command.Arguments.Contains("build"));
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/smoke_headless.py", StringComparison.Ordinal)));
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/prototype_main_menu_navigation_smoke.py", StringComparison.Ordinal)));
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldRequireBattleAcceptance_ForGenericFinalGoal_WhenContractHasCombatSemantics()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG prototype through battle, reward, and final validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.Title.Contains("final first-loop acceptance", StringComparison.Ordinal));
        await store.UpdateProjectIterationGoalStatusAsync(
            targetGoal.GoalId,
            "pending",
            "Validate selected capabilities, contract, Godot validation, and package readiness.",
            DateTimeOffset.UtcNow.ToString("O"));
        await CompleteGoalsBeforeAsync(store, projectId, targetGoal.GoalIndex);

        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WriteProjectReadme(project!);
        new PrototypeContractService().WriteFromRequest(project!, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "contract");
        stateWriter.WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new { smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn" },
            godot_smoke = new { scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn" }
        });
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        File.WriteAllText(
            Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "BattleScene.cs"),
            "public sealed class BattleScene { public void ShowOnly() { } }\n");
        var runner = new StepFiveSmokeHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("needs_fix");
        result.GoalIndex.Should().Be(targetGoal.GoalIndex);
        refreshed!.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).Status.Should().Be("needs_fix");
        run!.EvidenceJson.Should().Contain("\"acceptance_validation\":\"jrpg-final-first-loop-acceptance\"");
        refreshed.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).ResultSummary.Should().Contain("missing_rpg_battle_scene_contract");
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldKeepRpgFinalStepNeedsFix_WhenFoundationAssetInstancesAreMismatched()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG prototype through the strict contract steps."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.Title.Contains("final first-loop acceptance", StringComparison.Ordinal));
        await CompleteGoalsBeforeAsync(store, projectId, targetGoal.GoalIndex);

        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WriteProjectReadme(project!);
        stateWriter.WritePrototypeState(project!, new { route = "prototype-7day-playable" });
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        WriteMismatchedRpgAssetScene(project.RepoPath);
        var runner = new NoopGoalHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("needs_fix");
        result.GoalIndex.Should().Be(targetGoal.GoalIndex);
        refreshed!.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).Status.Should().Be("needs_fix");
        runner.Commands.Should().ContainSingle(command => command.Arguments.Contains("exec"));
    }

    [Fact]
    public async Task ExecuteNextAsync_ShouldKeepRpgFinalStepNeedsFix_WhenFormValuesAreNotReflected()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG prototype through the strict contract steps."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.Title.Contains("final first-loop acceptance", StringComparison.Ordinal));
        await CompleteGoalsBeforeAsync(store, projectId, targetGoal.GoalIndex);

        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WriteProjectReadme(project!);
        new PrototypeContractService().WriteFromRequest(project!, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "contract");
        stateWriter.WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new { smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn" },
            godot_smoke = new { scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn" }
        });
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        OverwriteRpgCoreWithMismatchedFormValues(project.RepoPath);
        var runner = new StepFiveSmokeHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var detailsAfter = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("needs_fix");
        result.GoalIndex.Should().Be(targetGoal.GoalIndex);
        detailsAfter!.Goals.Single(goal => goal.GoalIndex == targetGoal.GoalIndex).ResultSummary.Should().Contain("rpg_form_contract_values_not_reflected");
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
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先修 step1，再做 step2。"));
        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WritePrototypeState(project!, new { route = "prototype-7day-playable", marker = "prototype-baseline" });
        var runner = new NeedsFixHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("needs_fix");
        result.SessionStatus.Should().Be("needs_fix");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.ProgressStep.Should().Be("needs_fix");
        run.ProgressSubstep.Should().Be("needs_fix");
        run.ProgressLabel.Should().Be("目标 1 需要修复。");
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
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
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
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
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
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
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

    private static async Task CompleteGoalsBeforeAsync(PhaseAMetadataStore store, string projectId, int goalIndex)
    {
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var now = DateTimeOffset.UtcNow.ToString("O");
        foreach (var goal in details!.Goals.Where(goal => goal.GoalIndex < goalIndex))
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "succeeded", $"Goal {goal.GoalIndex} already completed.", now);
        }
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
    // Objective: Start Adventure, learn the town context, and enter the first field.
    // Contract values: 100 HP, 10 ATK, 2 DEF, first enemy 30 HP and 5 ATK, +5 HP, +2 ATK, +1 DEF, 10% encounter, 10 steps, 15 battles.
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
    public const string Objective = "Start Adventure, learn the town context, and enter the first field.";
    public const int InitialPlayerHp = 100;
    public const int InitialPlayerAttack = 10;
    public const int InitialPlayerDefense = 2;
    public const int FirstEnemyHp = 30;
    public const int FirstEnemyAttack = 5;
    public const int HpReward = 5;
    public const int AttackReward = 2;
    public const int DefenseReward = 1;
    public const int EncounterChanceStepPercent = 10;
    public const int GuaranteedEncounterSteps = 10;
    public const int VictoryBattleCount = 15;
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
[node name="ObjectiveLabel" type="Label" parent="."]
text = "Objective: Start Adventure and find the village elder."
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
[gd_scene load_steps=5 format=3]

[ext_resource type="Script" path="res://Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs" id="script_map"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/map_floor_tile.png" id="1"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/player_hero.png" id="2"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/enemy_slime.png" id="3"]

[node name="MapScene" type="Control"]
script = ExtResource("script_map")
custom_minimum_size = Vector2(700, 700)
[node name="TrackLayer" type="Control" parent="."]
custom_minimum_size = Vector2(600, 600)
[node name="RpgMapAsset" type="TextureRect" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer"]
custom_minimum_size = Vector2(600, 600)
texture = ExtResource("1")
[node name="Grid" type="GridContainer" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer"]
[node name="Overlay" type="Control" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer"]
[node name="RpgPlayerAsset" type="TextureRect" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer/Overlay"]
texture = ExtResource("2")
[node name="RpgEnemyAsset" type="TextureRect" parent="Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer/Overlay"]
texture = ExtResource("3")
""");
        File.WriteAllText(Path.Combine(scenePath, "BattleScene.tscn"), """
[gd_scene load_steps=3 format=3]

[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/player_hero.png" id="1"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/enemy_slime.png" id="2"]
[node name="BattleScene" type="Node"]
[node name="AttackButton" type="Button" parent="."]
text = "Attack"
[node name="RpgPlayerAsset" type="TextureRect" parent="BattleScene"]
texture = ExtResource("1")
[node name="RpgEnemyAsset" type="TextureRect" parent="BattleScene"]
texture = ExtResource("2")
""");
        var scriptPath = Path.Combine(scenePath, "Scripts");
        Directory.CreateDirectory(scriptPath);
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), "public sealed class DqRpgPrototype { void Ready() { _mapScene = GetNode<MapScene>(\"CanvasLayer/UI/MapScene\"); StartButton.Pressed += ShowMapScene; _mapScene.Visible = true; } void ShowMapScene() {} void ShowRewardScene(object rewards) {} void OnBattleFinished(bool isVictory, System.Collections.Generic.IReadOnlyList<object> rewards) { if (rewards.Count > 0) { ShowRewardScene(rewards); return; } ShowMapScene(); } }\n");
        File.WriteAllText(Path.Combine(scriptPath, "MapScene.cs"), "public sealed class MapScene { object TrackLayer; public event System.Action? EncounterEntered; void MovePlayer() { GridToPosition(); } void GridToPosition() {} void ShowRewardReturnStatus() { _player.Visible = true; } dynamic _player; }\n");
        File.WriteAllText(Path.Combine(scriptPath, "BattleScene.cs"), "public sealed class BattleScene { public event System.Action? BattleFinished; void ResolveBattle() { ResolveAttackTurn(); } void ResolveAttackTurn() {} }\n");
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
        File.WriteAllText(Path.Combine(mainScenePath, "Main.tscn"), """
[gd_scene format=3]

[node name="Main" type="Control"]

[node name="ScreenRoot" type="Control" parent="."]
visible = false

[node name="Overlays" type="Control" parent="."]
visible = false

[node name="VBox" type="VBoxContainer" parent="."]
visible = false
""");
        var dqAssetPath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Assets");
        Directory.CreateDirectory(dqAssetPath);
        foreach (var assetFile in new[] { "map_floor_tile.png", "player_hero.png", "enemy_slime.png" })
        {
            File.WriteAllText(Path.Combine(dqAssetPath, assetFile), "asset\n");
        }

        foreach (var (assetDir, assetFile) in new[] { ("Map", "map_tile.png"), ("Player", "player_hero.png"), ("Enemy", "enemy_slime.png") })
        {
            var path = Path.Combine(repoPath, "Game.Godot", "Prototypes", "DefaultRpgTemplate", "Assets", assetDir);
            Directory.CreateDirectory(path);
            File.WriteAllText(Path.Combine(path, assetFile), "asset\n");
        }
    }

    private static void WriteCurrentRpgMapEntryShape(string repoPath)
    {
        var scenePath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg");
        var scriptPath = Path.Combine(scenePath, "Scripts");
        Directory.CreateDirectory(scriptPath);
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), """
public sealed class DqRpgPrototype
{
    private MapScene _mapScene = default!;
    private bool _hasStarted;
    public void Ready()
    {
        _mapScene = GetNode<MapScene>("CanvasLayer/UI/MapScene");
        _startButton.Pressed += StartRun;
        _mapScene.EncounterTriggered += OnEncounterTriggered;
    }
    private void StartRun()
    {
        _hasStarted = true;
        _mapScene.StartAdventure(0);
        RefreshView();
    }
    private void RefreshView()
    {
        var mapVisible = _hasStarted;
        _mapScene.Visible = mapVisible;
    }
}
""");
        File.WriteAllText(Path.Combine(scenePath, "MapScene.tscn"), """
[gd_scene load_steps=5 format=3]

[ext_resource type="Script" path="res://Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs" id="script_map"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/map_floor_tile.png" id="1"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/player_hero.png" id="2"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/enemy_slime.png" id="3"]

[node name="MapScene" type="Control"]
script = ExtResource("script_map")
[node name="TrackLayer" type="Control" parent="."]
custom_minimum_size = Vector2(600, 600)
[node name="RpgMapAsset" type="TextureRect" parent="TrackLayer"]
texture = ExtResource("1")
[node name="Grid" type="GridContainer" parent="TrackLayer"]
[node name="Overlay" type="Control" parent="TrackLayer"]
[node name="RpgPlayerAsset" type="TextureRect" parent="TrackLayer"]
texture = ExtResource("2")
[node name="RpgEnemyAsset" type="TextureRect" parent="TrackLayer"]
texture = ExtResource("3")
""");
        File.WriteAllText(Path.Combine(scriptPath, "MapScene.cs"), """
public sealed class MapScene
{
    public event System.Action<string>? EncounterTriggered;
    private object TrackLayer = new();
    private dynamic _playerToken;
    public void StartAdventure(int battlesWon = 0)
    {
        Visible = true;
        _playerToken.Visible = true;
    }
    public bool TryHandleMapKey(object keycode)
    {
        MoveOnMap();
        return true;
    }
    private void MoveOnMap()
    {
        _playerToken.Position = GridToPosition();
        EncounterTriggered?.Invoke("traversal_charge");
    }
    private object GridToPosition() => new();
}
""");
    }

    private static void DeleteBattleSceneFiles(string repoPath)
    {
        var scenePath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg");
        File.Delete(Path.Combine(scenePath, "BattleScene.tscn"));
        File.Delete(Path.Combine(scenePath, "Scripts", "BattleScene.cs"));
    }

    private static void WriteMainScriptWithoutRewardFlow(string repoPath)
    {
        var scriptPath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts");
        Directory.CreateDirectory(scriptPath);
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), """
public sealed class DqRpgPrototype
{
    void Ready()
    {
        _mapScene = GetNode<MapScene>("CanvasLayer/UI/MapScene");
        StartButton.Pressed += ShowMapScene;
        _mapScene.Visible = true;
    }

    void ShowMapScene() {}
    void ContinueToNextObjective() { ShowMapScene(); }

    private MapScene _mapScene = default!;
    private dynamic StartButton;
}
""");
    }

    private static void WriteMapEntryWithoutEnemyOrEncounter(string repoPath)
    {
        var scenePath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg");
        Directory.CreateDirectory(scenePath);
        File.WriteAllText(Path.Combine(scenePath, "MapScene.tscn"), """
[gd_scene load_steps=4 format=3]

[ext_resource type="Script" path="res://Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs" id="script_map"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/map_floor_tile.png" id="1"]
[ext_resource type="Texture2D" path="res://Game.Godot/Prototypes/dq-rpg/Assets/player_hero.png" id="2"]

[node name="MapScene" type="Control"]
script = ExtResource("script_map")
custom_minimum_size = Vector2(700, 700)
[node name="TrackLayer" type="Control" parent="."]
custom_minimum_size = Vector2(600, 600)
[node name="RpgMapAsset" type="TextureRect" parent="TrackLayer"]
custom_minimum_size = Vector2(600, 600)
texture = ExtResource("1")
[node name="Grid" type="GridContainer" parent="TrackLayer"]
[node name="Overlay" type="Control" parent="TrackLayer"]
[node name="RpgPlayerAsset" type="TextureRect" parent="TrackLayer/Overlay"]
texture = ExtResource("2")
""");

        var scriptPath = Path.Combine(scenePath, "Scripts");
        Directory.CreateDirectory(scriptPath);
        File.WriteAllText(Path.Combine(scriptPath, "MapScene.cs"), """
public sealed class MapScene
{
    private object TrackLayer = new();
    private dynamic _player;
    public bool TryHandleMapKey(object keycode) { MoveOnMap(); return true; }
    private void MoveOnMap() { GridToPosition(); _player.Visible = true; }
    private object GridToPosition() => new();
}
""");
    }

    private static void WriteCoreMarkersWithoutBattleOrReward(string repoPath)
    {
        var testsPath = Path.Combine(repoPath, "Game.Core.Tests", "Prototypes");
        Directory.CreateDirectory(testsPath);
        File.WriteAllText(Path.Combine(testsPath, "DqRpgPrototypeLoopTests.cs"), """
public sealed class DqRpgPrototypeLoopTests
{
    public void MoveOnMap() { }
}
""");

        var corePath = Path.Combine(repoPath, "Game.Core", "Prototypes");
        Directory.CreateDirectory(corePath);
        File.WriteAllText(Path.Combine(corePath, "DqRpgPrototypeLoop.cs"), """
public sealed class DqRpgPrototypeLoop
{
    public const string Objective = "Start Adventure, help the elder, and continue exploring.";
    public void MoveOnMap() { }
}
""");
    }

    private static void WriteMismatchedRpgAssetScene(string repoPath)
    {
        var scenePath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn");
        File.WriteAllText(scenePath, """
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
texture = ExtResource("1")
[node name="RpgEnemyAsset" type="TextureRect" parent="MapScene"]
texture = ExtResource("3")
""");
    }

    private static void OverwriteRpgCoreWithMismatchedFormValues(string repoPath)
    {
        var corePath = Path.Combine(repoPath, "Game.Core", "Prototypes", "DqRpgPrototypeLoop.cs");
        File.WriteAllText(corePath, """
public sealed class DqRpgPrototypeLoop
{
    public const int VictoryBattleCount = 15;
    public int PlayerHp = 28;
    public int PlayerAttack = 6;
    public int FirstEnemyHp = 9;
    public int FirstEnemyAttack = 3;
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
    // IsVictory
    // IsGameOver
}
""");
    }

    private static void EnsureRpgRewardRuntimeMarkers(string repoPath)
    {
        var scriptPath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts");
        Directory.CreateDirectory(scriptPath);
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), """
public sealed class DqRpgPrototype
{
    public System.Collections.Generic.IReadOnlyList<object> RewardOptions { get; set; } = System.Array.Empty<object>();
    void Ready() { _mapScene = GetNode<MapScene>("CanvasLayer/UI/MapScene"); StartButton.Pressed += ShowMapScene; _mapScene.Visible = true; }
    T GetNode<T>(string path) => default!;
    dynamic StartButton;
    dynamic _mapScene;
    void ShowMapScene() {}
    void RefreshView() {}
    void ShowRewardReturnStatus() {}
    void ShowRewardScene(System.Collections.Generic.IReadOnlyList<object> rewards)
    {
        if (rewards.Count > 0 || RewardOptions.Count > 0)
        {
            ApplyReward();
            BattleRewardSelected();
            ShowMapScene();
        }
    }
    void OnBattleFinished(bool isVictory, System.Collections.Generic.IReadOnlyList<object> rewards)
    {
        if (rewards.Count > 0)
        {
            ShowRewardScene(rewards);
            return;
        }
        ShowMapScene();
    }
    void ApplyReward() { RefreshView(); ShowRewardReturnStatus(); }
    void BattleRewardSelected() {}
    // Battle reward selected
}
""");
    }

    private static void WriteMainScriptOwnedRewardPanel(string repoPath)
    {
        var scriptPath = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts");
        Directory.CreateDirectory(scriptPath);
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), """
public sealed class DqRpgPrototype
{
    private DqRpgPrototypeLoop _loop = new();
    private dynamic _state;
    private dynamic _rewardPanel;
    private dynamic[] _rewardButtons = new dynamic[3];

    private void OnBattleFinished(dynamic result)
    {
        var rewards = result.RewardOptions.Count > 0
            ? result.RewardOptions
            : _loop.CreateRewardOptions(_state, fromChest: false);
        if (rewards.Count > 0)
        {
            ShowRewardScene(rewards);
            return;
        }

        RefreshView();
    }

    private void ShowRewardScene(System.Collections.Generic.IReadOnlyList<object> rewards)
    {
        for (var i = 0; i < _rewardButtons.Length; i++)
        {
            if (i < rewards.Count)
            {
                _rewardButtons[i].Text = $"Reward {i + 1}";
                _rewardButtons[i].Visible = true;
            }
            else
            {
                _rewardButtons[i].Visible = false;
            }
        }

        _rewardPanel.Visible = true;
    }

    private void SelectReward(int rewardIndex)
    {
        _state = _loop.ApplyReward(_state, rewardIndex, fromChest: false);
        _rewardPanel.Visible = false;
        RefreshView();
    }

    private string DebugGetRpgRewardFlowContract()
    {
        return "rpg_reward_flow_contract choice_count=3 Battle reward selected Return to the map";
    }

    private void RefreshView() { }
}
""");
        File.WriteAllText(Path.Combine(scriptPath, "MapScene.cs"), """
public sealed class MapScene
{
    private dynamic _playerToken;
    public bool TryHandleMapKey(object keycode) { MoveOnMap(); return true; }
    private void MoveOnMap() { GridToPosition(); EncounterTriggered?.Invoke("enemy"); }
    private object GridToPosition() => new();
    public event System.Action<string>? EncounterTriggered;
}
""");
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
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
SUMMARY: Completed the current goal with verified behavior.
CHANGED: Updated the current project page entry hint.
VERIFY: Unit tests passed and Godot smoke passed.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "iteration goal stdout", ""));
        }
    }

    private sealed class RestoreRetryHostedProcessRunner : IHostedProcessRunner
    {
        private int _testAttempts;

        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet" && command.Arguments.Contains("test"))
            {
                _testAttempts++;
                if (_testAttempts == 1)
                {
                    return Task.FromResult(new HostedProcessResult(
                        1,
                        "",
                        "Game.Core.Tests\\Domain\\GameConfigTests.cs(1,7): error CS0246: The type or namespace name 'FluentAssertions' could not be found\r\nGame.Core.Tests\\Domain\\GameConfigTests.cs(3,7): error CS0246: The type or namespace name 'Xunit' could not be found"));
                }
            }

            return Task.FromResult(new HostedProcessResult(0, "ok", ""));
        }
    }

    private sealed class NoopGoalHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).FirstOrDefault();
            if (!string.IsNullOrWhiteSpace(outputPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
                File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: Foundation asset instances are still mismatched.
CHANGED: none
VERIFY: blocked
REMAINING: Fix RPG map, player, and enemy asset instance binding.
""");
            }

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
