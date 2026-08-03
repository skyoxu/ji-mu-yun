using System.Text.Json;
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
        WriteText(project!.RepoPath, "project.godot", """
        [application]
        run/main_scene="res://Game.Godot/Scenes/Main.tscn"

        [autoload]
        GameState="*res://Game.Godot/Scripts/GameState.cs"

        [input]
        move_left={"deadzone":0.5,"events":[]}
        attack={"deadzone":0.5,"events":[]}

        [layer_names]
        3d_physics/layer_1="player"
        3d_physics/layer_2="enemy"
        """);
        WriteText(project.RepoPath, "Game.Godot/Scenes/Main.tscn", "[gd_scene format=3]\n");
        WriteText(project.RepoPath, "Game.Godot/Prototypes/demo/DemoPrototype.tscn", "[gd_scene format=3]\n[node name=\"Player\" type=\"CharacterBody3D\"]\n[node name=\"Collider\" type=\"CollisionShape3D\"]\n");
        WriteText(project.RepoPath, "Game.Godot/Prototypes/demo/Scripts/DemoPrototype.cs", "public sealed class DemoPrototype : CharacterBody3D {}\n");
        WriteText(project.RepoPath, "Game.Godot/Prototypes/demo/Assets/hero.glb", "asset");
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
        result.Steps[0].GodotSlice.Should().Contain("smoke/assertion");
        result.Steps[0].Acceptance.Should().Contain("当前模块 smoke/assertion");
        result.Steps[0].PackagingValidation.Should().Contain("打包下载");
        result.Steps[0].FeedbackGuidance.Should().Contain("needs-fix 修复");
        result.Steps[0].NextStepReview.Should().Contain("解锁下一 step");
        result.Steps[1].Locked.Should().BeTrue();
        result.Steps.Single(step => step.StepId == "M10-1").ScopeIn.Should().Contain("碰撞");
        result.Steps.Single(step => step.StepId == "M10-1").Acceptance.Should().Contain("穿模");
        File.Exists(Path.Combine(project.MetaPath, "routes", "gdd-milestones", "latest.json")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "meta", "routes", "gdd-milestones", "latest.json")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "docs", "prototype-v1-plan.md")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "docs", "prototype", "STRUCTURE.md")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "docs", "prototype", "MEMORY.md")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "docs", "prototype", "ASSETS.md")).Should().BeTrue();
        var structureText = File.ReadAllText(Path.Combine(project.RepoPath, "docs", "prototype", "STRUCTURE.md"));
        structureText.Should().Contain("res://Game.Godot/Scenes/Main.tscn");
        structureText.Should().Contain("Game.Godot/Prototypes/demo/DemoPrototype.tscn");
        structureText.Should().Contain("Game.Godot/Prototypes/demo/Scripts/DemoPrototype.cs");
        structureText.Should().Contain("move_left");
        structureText.Should().Contain("3d_physics/layer_1");
        structureText.Should().Contain("hero.glb");
        var memoryText = File.ReadAllText(Path.Combine(project.RepoPath, "docs", "prototype", "MEMORY.md"));
        memoryText.Should().Contain("dimension: 3d");
        memoryText.Should().Contain("physics: godot-3d-physics");
        File.Exists(Path.Combine(project.RepoPath, result.Steps[0].SpecRelativePath!.Replace('/', Path.DirectorySeparatorChar))).Should().BeTrue();
        result.Steps[0].SpecRelativePath.Should().StartWith("docs/m1-");
        var specText = File.ReadAllText(Path.Combine(project.RepoPath, result.Steps[0].SpecRelativePath!.Replace('/', Path.DirectorySeparatorChar)));
        specText.Should().Contain("smoke/assertion");
        File.ReadAllText(Path.Combine(project.MetaPath, "routes", "gdd-milestones", "latest.json"))
            .Should().Contain("phase-a.gdd-milestone-steps.v2");
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_ReconcilesLatestGddMilestoneSession_WhenStepStateMissedRunResult()
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

        M1: First playable room.
        M2: Skill pressure.
        M3: Run upgrade loop.
        """);
        WriteM3ReadyStepState(project.MetaPath, project.RepoPath);
        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "gdd_milestone_step",
            "M3 session",
            "M3 - Run upgrade loop",
            [new ProjectIterationGoalCreateCommand(3, "M3: Run upgrade loop", "Implement M3.", "Validate M3.")]);
        var details = await store.GetProjectIterationSessionAsync(projectId, session.SessionId);
        var goal = details!.Goals.Single();
        var executionRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-iteration-goal");
        await store.CompleteRunAsync(executionRunId, "completed", 0, "execution stdout", "", "{\"goal_index\":3}", CancellationToken.None);
        await store.LinkProjectIterationGoalRunAsync(session.SessionId, goal.GoalId, executionRunId, "prototype-iteration-goal");
        var repairRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-quick-fix");
        await store.CompleteRunAsync(repairRunId, "completed", 0, "repair stdout", "", "{\"goal_index\":3}", CancellationToken.None);
        await store.LinkProjectIterationGoalRunAsync(session.SessionId, goal.GoalId, repairRunId, "prototype-iteration-goal-repair");
        await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "needs_fix", "M3 still needs Godot smoke repair.", null);
        await store.UpdateProjectIterationSessionStatusAsync(session.SessionId, "needs_fix", 3, "Task 3 still needs repair.", null, null);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        var step = result!.Steps.Single(candidate => candidate.StepId == "M3");
        step.Status.Should().Be("needs_fix");
        step.ExecutionRunId.Should().Be(executionRunId);
        step.FeedbackRunId.Should().Be(repairRunId);
        step.ExecutionSummary.Should().Contain("M3 still needs Godot smoke repair.");
        step.FeedbackSummary.Should().Contain("M3 still needs Godot smoke repair.");
        step.CanSubmitFeedback.Should().BeTrue();
        step.LatestEvidenceRelativePath.Should().NotBeNullOrWhiteSpace();
        result.CurrentStepId.Should().Be("M3");
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_ReconcilesLatestGddMilestoneSession_WhenStepStateHasStaleRepairRun()
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

        M1: First playable room.
        M2: Skill pressure.
        M3: Run upgrade loop.
        """);
        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "gdd_milestone_step",
            "M3 session",
            "M3 - Run upgrade loop",
            [new ProjectIterationGoalCreateCommand(3, "M3: Run upgrade loop", "Implement M3.", "Validate M3.")]);
        var details = await store.GetProjectIterationSessionAsync(projectId, session.SessionId);
        var goal = details!.Goals.Single();
        var executionRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-iteration-goal");
        await store.CompleteRunAsync(executionRunId, "completed", 0, "execution stdout", "", "{\"goal_index\":3}", CancellationToken.None);
        await store.LinkProjectIterationGoalRunAsync(session.SessionId, goal.GoalId, executionRunId, "prototype-iteration-goal");
        var staleRepairRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-quick-fix");
        await store.CompleteRunAsync(staleRepairRunId, "completed", 0, "stale repair stdout", "", "{\"goal_index\":3}", CancellationToken.None);
        await store.LinkProjectIterationGoalRunAsync(session.SessionId, goal.GoalId, staleRepairRunId, "prototype-iteration-goal-repair");
        WriteM3StaleRepairStepState(project.MetaPath, project.RepoPath, executionRunId, staleRepairRunId);
        await Task.Delay(5);
        var latestRepairRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-quick-fix");
        await store.CompleteRunAsync(latestRepairRunId, "completed", 0, "latest repair stdout", "", "{\"goal_index\":3}", CancellationToken.None);
        await store.LinkProjectIterationGoalRunAsync(session.SessionId, goal.GoalId, latestRepairRunId, "prototype-iteration-goal-repair");
        await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "succeeded", "M3 acceptance passed after latest repair.", null);
        await store.UpdateProjectIterationSessionStatusAsync(session.SessionId, "completed", 3, "Task 3 acceptance passed.", null, null);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        var step = result!.Steps.Single(candidate => candidate.StepId == "M3");
        step.Status.Should().Be("feedback_submitted");
        step.ExecutionRunId.Should().Be(executionRunId);
        step.FeedbackRunId.Should().Be(latestRepairRunId);
        step.FeedbackRunId.Should().NotBe(staleRepairRunId);
        step.FeedbackSummary.Should().Contain("M3 acceptance passed after latest repair.");
        step.FeedbackSummary.Should().NotContain("stale");
        step.LatestEvidenceRelativePath.Should().NotBe("logs/prototype-evidence/stale-repair.json");
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_PreservesConfirmedStep_WhenHistoricalResultStillNeedsFix()
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

        M1: First playable room.
        M2: Skill pressure.
        M3: Run upgrade loop.
        """);
        WriteStepState(project.MetaPath, project.RepoPath, """
        {
          "schema": "phase-a.gdd-milestone-steps.v2",
          "status": "ready",
          "summary": "M3 was incorrectly confirmed",
          "currentStepId": "M4",
          "steps": [
            { "stepId": "M1", "stepIndex": 1, "title": "M1", "description": "M1", "status": "confirmed", "locked": false },
            { "stepId": "M2", "stepIndex": 2, "title": "M2", "description": "M2", "status": "confirmed", "locked": false },
            {
              "stepId": "M3",
              "stepIndex": 3,
              "title": "M3",
              "description": "M3",
              "status": "confirmed",
              "locked": false,
              "confirmedUtc": "2026-06-24T00:00:00Z",
              "executionRunId": "run-m3",
              "feedbackRunId": "repair-m3",
              "executionSummary": "STATUS: needs_fix\nREMAINING: continue repair",
              "feedbackSummary": "STATUS: needs_fix\nREMAINING: continue repair"
            }
          ]
        }
        """);
        var runner = new FakeHostedProcessRunner("""
        STATUS: completed
        VERIFY: Current module repair passed static check for the current milestone goal.
        REMAINING: none
        """);
        var service = Service(store, options, runner: runner);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        var step = result!.Steps.Single(candidate => candidate.StepId == "M3");
        step.Status.Should().Be("confirmed");
        step.CanConfirm.Should().BeFalse();
        step.CanSubmitFeedback.Should().BeFalse();
        step.ConfirmedUtc.Should().Be("2026-06-24T00:00:00Z");
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_AppendsNewGddMilestones_WithoutResettingExistingState()
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
        M1: First playable scene and controls.
        M2: Active skills.
        M3: Boss and run summary.
        """);
        WriteCompletedAndReadyStepState(project.MetaPath, project.RepoPath);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.Steps.Select(step => step.StepId).Should().Equal("M1", "M2", "M3");
        result.Steps.Single(step => step.StepId == "M1").Status.Should().Be("confirmed");
        result.Steps.Single(step => step.StepId == "M2").Status.Should().Be("ready");
        result.Steps.Single(step => step.StepId == "M3").Status.Should().Be("locked");
        result.Steps.Single(step => step.StepId == "M3").Locked.Should().BeTrue();
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_AppendsMilestonesFromSupplementalGddSections()
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
        M1: First playable scene and controls.
        M2: Active skills.

        ## Supplemental Modules
        M3: Boss and run summary.
        """);
        WriteCompletedAndReadyStepState(project.MetaPath, project.RepoPath);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.Steps.Select(step => step.StepId).Should().Equal("M1", "M2", "M3");
        result.Steps.Single(step => step.StepId == "M3").Title.Should().Contain("Boss");
        result.Steps.Single(step => step.StepId == "M3").Locked.Should().BeTrue();
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_AppendsNewGddMilestone_AsActive_WhenExistingStepsAreConfirmed()
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
        M1: First playable scene and controls.
        M2: Boss and run summary.
        """);
        WriteAllConfirmedStepState(project.MetaPath, project.RepoPath);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.CurrentStepId.Should().Be("M2");
        result.Steps.Select(step => step.StepId).Should().Equal("M1", "M2");
        result.Steps.Single(step => step.StepId == "M1").Status.Should().Be("confirmed");
        result.Steps.Single(step => step.StepId == "M2").Status.Should().Be("ready");
        result.Steps.Single(step => step.StepId == "M2").Locked.Should().BeFalse();
        result.Steps.Single(step => step.StepId == "M2").CanExecute.Should().BeTrue();
    }

    [Fact]
    public async Task CreateNewRoundStepAsync_AppendsM12ToGddMilestoneState()
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
        # SDC GDD

        ## Milestones
        M1: Module 1.
        M2: Module 2.
        M3: Module 3.
        M4: Module 4.
        M5: Module 5.
        M6: Module 6.
        M7: Module 7.
        M8: Module 8.
        M9: Module 9.
        M10: Module 10.
        M11: Module 11.

        ## Additional Game Modules
        """);
        WriteAllConfirmedStepState(project.MetaPath, project.RepoPath, 11);
        var service = Service(store, options);

        var result = await service.CreateNewRoundStepAsync(
            accountId,
            projectId,
            new GddMilestoneNewRoundRequest("SDC local playtest alignment with real physics and extraction loop."));

        result.Should().NotBeNull();
        result!.Status.Should().Be("created");
        result.StepId.Should().Be("M12");
        result.Plan!.CurrentStepId.Should().Be("M12");
        result.Plan.Status.Should().Be("ready");
        var m12 = result.Plan.Steps.Single(step => step.StepId == "M12");
        m12.Locked.Should().BeFalse();
        m12.CanExecute.Should().BeTrue();
        m12.Title.Should().Contain("SDC local playtest");
        var gdd = File.ReadAllText(Path.Combine(project.RepoPath, "docs", "gdd", "GDD.md"));
        gdd.Should().Contain("M12: SDC local playtest alignment");
        (gdd.Split("## Additional Game Modules").Length - 1).Should().Be(1);
    }

    [Fact]
    public async Task ExecuteCurrentStepAsync_Blocks_WhenGddOutlineHasIncompleteSections()
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
        M1: First playable scene and controls.
        """);
        WriteOutline(project.RepoPath, """
        {
          "title": "Action Roguelike GDD",
          "summary": "summary",
          "sections": [
            { "id": "milestones", "title": "Milestones", "skeleton": "M plan", "content": "" }
          ]
        }
        """);
        var service = Service(store, options);

        var plan = await service.GetOrCreateLatestAsync(accountId, projectId);
        var result = await service.ExecuteCurrentStepAsync(accountId, projectId);

        plan.Should().NotBeNull();
        plan!.OutlineComplete.Should().BeFalse();
        plan.IncompleteOutlineSections.Should().Contain("Milestones");
        plan.Steps.Single().CanExecute.Should().BeFalse();
        result.Should().NotBeNull();
        result!.Status.Should().Be("outline_incomplete");
        result.FailureCode.Should().Be("outline_incomplete");
    }

    [Fact]
    public async Task ExecuteCurrentStepAsync_QueuesPrototypeCreation_WhenFirstStepHasNoPrototypeState()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, seedPrototypeBaseline: false);
        var project = await store.GetProjectSnapshotAsync(projectId);
        WriteGdd(project!.RepoPath, """
        # New Project GDD

        M1: First playable scene and controls.
        M2: Core loop validation.
        """);
        var prototypeWorkflow = new FakePrototypeFromGddWorkflow(new PrototypeWorkflowResult(
            "prototype-run-1",
            "queued",
            202,
            "docs/prototypes/new-project.prototype.json",
            "",
            "",
            [],
            []));
        var service = Service(store, options, prototypeWorkflow: prototypeWorkflow);

        var result = await service.ExecuteCurrentStepAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("queued");
        result.FailureCode.Should().BeNull();
        result.StepExecution.Should().BeNull();
        prototypeWorkflow.Calls.Should().Be(1);
        prototypeWorkflow.LastAccountId.Should().Be(accountId);
        prototypeWorkflow.LastProjectId.Should().Be(projectId);
        var firstStep = result.Plan!.Steps.Single(step => step.StepId == "M1");
        result.Plan.Status.Should().Be("running");
        firstStep.Status.Should().Be("running");
        firstStep.ExecutionRunId.Should().Be("prototype-run-1");
        firstStep.ExecutionSummary.Should().Contain("M1");
        firstStep.LatestEvidenceRelativePath.Should().NotBeNullOrWhiteSpace();
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_ReconcilesFailedM1PrototypeCreation_WhenStepHasIterationSession()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, seedPrototypeBaseline: false);
        var project = await store.GetProjectSnapshotAsync(projectId);
        WriteGdd(project!.RepoPath, """
        # New Project GDD

        M1: First playable scene and controls.
        M2: Core loop validation.
        """);
        var runId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "prototype-7day-playable");
        await store.CompleteRunAsync(
            runId,
            "failed",
            1,
            "generation output",
            "",
            """
            {
              "run_type": "prototype-7day-playable",
              "prototype_completion": {
                "succeeded": false,
                "error": "prototype_workflow_failed"
              }
            }
            """);
        WriteRunningSkeletonStepState(project.MetaPath, project.RepoPath, runId);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("needs_fix");
        var firstStep = result.Steps.Single(step => step.StepId == "M1");
        firstStep.Status.Should().Be("needs_fix");
        firstStep.CanSubmitFeedback.Should().BeTrue();
        firstStep.ExecutionRunId.Should().Be(runId);
        firstStep.ExecutionSummary.Should().Contain("M1 游戏场景创建未通过");
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_ExtractsChineseHeadingMilestones_AndReplacesUnstartedFallbackState()
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
        # Tower Demo GDD

        Reference game: Phantom Tower.
        Scene: a dark tower dungeon.
        Controls: WASD movement, mouse facing, left click combo, space dodge.
        Progression: wave rewards and persistent souls.
        """);
        var service = Service(store, options);
        var fallback = await service.GetOrCreateLatestAsync(accountId, projectId);
        fallback!.Steps.Should().HaveCount(10);
        File.Exists(Path.Combine(project.RepoPath, "docs", "m10-原型可玩性验证与打包-spec.md")).Should().BeTrue();

        WriteGdd(project.RepoPath, """
        # Tower Demo GDD

        ## Prototype V1 Milestones

        M1 第一可玩骨架：
        建立第三人称场景、WASD 移动、鼠标朝向、左键连击、空格翻滚，以及第一房间手感验证。

        M2 波次战斗与升级：
        加入波次刷怪、击杀经验、升级选项和 HUD 反馈。

        M3 随机房间与地城连接：
        加入随机房间、门、奖励房和地城推进目标。

        M4 死亡、灵魂货币与永久升级：
        加入死亡结算、灵魂保留和永久升级入口。

        M5 内容替换与体验扩展：
        替换关键素材并验证碰撞、阻挡和命中。

        M6 UI/UX 正式回收与截图验收：
        统一 HUD、状态反馈、截图验收和打包验证。
        """);

        var refreshed = await service.GetOrCreateLatestAsync(accountId, projectId);

        refreshed.Should().NotBeNull();
        refreshed!.Steps.Select(step => step.StepId).Should().Equal("M1", "M2", "M3", "M4", "M5", "M6");
        refreshed.Summary.Should().Be("已根据最新策划大纲里程碑刷新游戏模块步骤规格。");
        refreshed.Steps[0].Title.Should().Be("M1：第一可玩骨架");
        refreshed.Steps[0].Description.Should().Contain("第三人称场景");
        refreshed.Steps[1].Title.Should().Be("M2：波次战斗与升级");
        refreshed.Steps[1].Description.Should().Contain("波次刷怪");
        refreshed.Steps[5].Title.Should().Be("M6：UI/UX 正式回收与截图验收");
        refreshed.CurrentStepId.Should().Be("M1");
        refreshed.Steps[0].Locked.Should().BeFalse();
        refreshed.Steps[1].Locked.Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, "docs", "m10-原型可玩性验证与打包-spec.md")).Should().BeFalse();
        File.Exists(Path.Combine(project.RepoPath, refreshed.Steps[0].SpecRelativePath!.Replace('/', Path.DirectorySeparatorChar))).Should().BeTrue();
        File.ReadAllText(Path.Combine(project.RepoPath, "docs", "prototype-v1-plan.md")).Should().Contain("M6：UI/UX 正式回收与截图验收");
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_ExtractsMilestonesOnlyFromAuthoritativeSection_AndCleansTitles()
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
        # Route GDD

        ## UI/UX、HUD 与玩家反馈

        - M6 再集中补入 theme tokens、screen contracts、截图验收、键盘焦点检查、本地化检查和文案溢出检查。

        ## 里程碑与实现步骤

        **骨架**: M1 首个可玩战斗房：目标是交付真正可玩的第一战；Scope In 包括 StartScreen/调试入口进入 PrototypeRoot、前厅到首战房的进入流程、WASD 移动、鼠标朝向、左键连击、空格翻滚、右键/Q/E 基础技能槽位与最小反馈、生命值/HUD/受击反馈、1 类训练敌人；Scope Out 为随机地城、多房间串联、永久成长；Godot/C# 切片应至少覆盖 PrototypeRoot.tscn、Player CharacterBody3D、CameraRig、Enemy Actor、HUD、Input Actions、HitBox/HurtBox、碰撞层与受击事件；玩家验收是 3 分钟内能完成进场、绕怪、翻滚、打出一套连击并清掉第一波；验证要求包括 Windows 包启动、键鼠输入正常、碰撞与击中反馈可复现。
        M2 敌人压力与波次循环：目标是让战斗从演示变成有失败风险的循环；Scope In 包括 2 到 3 类敌人原型、基础 AI、寻路/包夹、波次刷怪、房间清理判定、掉血与死亡；Scope Out 为复杂 Boss 机制与大地图探索；Godot/C# 切片应覆盖 EnemySpawner、NavigationRegion3D/NavigationAgent3D、BattleView、伤害/死亡结算；玩家验收是玩家需要主动走位与翻滚，不再能站桩过关；验证要求包括碰撞、卡位、刷怪点与波次结束条件检查。
        M3 局内升级与奖励：目标是把杀怪升级与成长决策接入基础循环；Scope In 包括经验值、升级触发、RewardView、三选一强化、至少 6 个可感知升级项、战后奖励节点；Scope Out 为局外永久成长与复杂装备系统；Godot/C# 切片应覆盖 ProgressionSystem、RewardView、Data/State run state、LogView；玩家验收是升级选择能立刻改变下一波战斗策略；验证要求包括升级 UI 可操作、升级效果可见、日志与 HUD 同步。
        M4 随机房间串联与精英校验：目标是形成短局 run 结构；Scope In 包括战斗房/奖励房/恢复房的最小随机串联、房间重置、1 场精英或小 Boss 校验战、出入口与战后过渡；Scope Out 为完整章节、剧情、复杂程序地形；Godot/C# 切片应覆盖 MapView、房间图生成、场景切换或同场景分区切换、Elite Encounter；玩家验收是单局能完成至少 3 到 5 个节点并感到难度抬升；验证要求包括房间切换稳定、随机结果可复现或可记录 seed、精英战不会因碰撞/相机失效。
        M5 死亡结算与局外永久成长：目标是闭合 Roguelike 的失败后推进循环；Scope In 包括死亡结算页、灵魂货币累计、meta upgrade 页面、1 到 2 条永久成长线、保存与下次开局继承；Scope Out 为庞大天赋树与长期数值平衡；Godot/C# 切片应覆盖 death_summary、meta_upgrade、Save/Load、MetaProgressionSystem；玩家验收是死亡不等于白打，并且下一局能感到小幅永久提升；验证要求包括重启游戏后数据仍在、异常中断不会损坏核心存档。
        M6 UI/UX 回补、组件统一与试玩打包：目标是把功能原型整理成可交付试玩包；Scope In 包括 theme tokens、按钮/卡片/面板组件统一、screen contract 固化、截图验收、键盘焦点检查、本地化键值接入、文案溢出检查、可访问性开关与 Windows 打包；Scope Out 为最终美术精修；Godot/C# 切片应覆盖 shared UI components、SettingsScreen、HUD/Reward/Death 页面合同、翻译表与打包脚本；玩家验收是新玩家无需口头说明也能完成一局并理解主要反馈；验证要求包括 720p/1080p 截图检查、焦点流正确、文本不过界、打包后试玩日志可回收。
        """);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.Steps.Select(step => step.StepId).Should().Equal("M1", "M2", "M3", "M4", "M5", "M6");
        result.Steps[0].Title.Should().Be("M1：首个可玩战斗房");
        result.Steps[0].Description.Should().Contain("PrototypeRoot.tscn");
        result.Steps[1].Title.Should().Be("M2：敌人压力与波次循环");
        result.Steps[5].Title.Should().Be("M6：UI/UX 回补、组件统一与试玩打包");
        result.Steps[5].Description.Should().Contain("screen contract");
        result.Steps.Should().OnlyContain(step => !step.Title.Contains("Scope In", StringComparison.OrdinalIgnoreCase));
        result.Steps[0].SpecRelativePath.Should().Be("docs/m1-首个可玩战斗房-spec.md");
        result.Steps[1].SpecRelativePath.Should().Be("docs/m2-敌人压力与波次循环-spec.md");
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_PrefersMilestoneSectionOverEarlierPrototypeAcceptanceSection()
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
        # Route GDD

        ## 原型验收标准

        - M6 再集中补入 theme tokens、screen contracts、截图验收、键盘焦点检查、本地化检查和文案溢出检查。
        1. M1 到 M3 必备资产

        ## 里程碑与实现步骤

        M1 首个可玩战斗房：目标是交付真正可玩的第一战；Scope In 包括 WASD、鼠标朝向、左键连击、空格翻滚和首个训练敌人；Scope Out 为随机地城。
        M2 敌人压力与波次循环：目标是让战斗从演示变成有失败风险的循环；Scope In 包括敌人 AI、波次刷怪和房间清理判定。
        M3 局内升级与奖励：目标是把杀怪升级与成长决策接入基础循环；Scope In 包括经验值、升级触发和三选一强化。
        """);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.Steps.Select(step => step.StepId).Should().Equal("M1", "M2", "M3");
        result.Steps[0].Title.Should().Be("M1：首个可玩战斗房");
        result.Steps[1].Title.Should().Be("M2：敌人压力与波次循环");
        result.Steps[2].Title.Should().Be("M3：局内升级与奖励");
        result.Steps.Should().NotContain(step => step.Title.Contains("theme tokens", StringComparison.OrdinalIgnoreCase));
        result.Steps.Should().NotContain(step => step.Title.Contains("必备资产", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_MarksM1Executed_WhenSkeletonCreationAlreadySucceeded()
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

        M1: First playable scene with WASD movement, mouse facing, combo, dodge, and first room feel validation.
        M2: Active skills.
        """);
        var runId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.CompleteRunAsync(
            runId,
            "succeeded",
            0,
            "",
            "",
            """{"prototype_completion":{"succeeded":true},"godot_smoke":{"exit_code":0}}""");
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        var m1 = result!.Steps.Single(step => step.StepId == "M1");
        m1.Status.Should().Be("executed");
        m1.CanConfirm.Should().BeTrue();
        result.CurrentStepId.Should().Be("M1");
        result.Summary.Should().Contain("M1 已通过游戏场景创建完成");
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_MarksM1NeedsFix_WhenSkeletonCreationFailed()
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

        M1: First playable scene with WASD movement, mouse facing, combo, dodge, and first room feel validation.
        M2: Active skills.
        """);
        var runId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.CompleteRunAsync(
            runId,
            "failed",
            1,
            "DAY4_IMPLEMENTATION_VALIDATION failed component_slots_not_wired=Game.Godot/Prototypes/Towerdemo2/Scripts/Towerdemo2Prototype.cs",
            "",
            """{"prototype_completion":{"succeeded":false,"error":"prototype_workflow_failed"},"godot_smoke":{"ran":false}}""");
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        var m1 = result!.Steps.Single(step => step.StepId == "M1");
        m1.Status.Should().Be("needs_fix");
        m1.CanSubmitFeedback.Should().BeTrue();
        m1.CanConfirm.Should().BeFalse();
        m1.ExecutionRunId.Should().Be(runId);
        m1.ExecutionSummary.Should().Contain("component_slots_not_wired");
        m1.LatestEvidenceRelativePath.Should().StartWith("logs/prototype-evidence/");
        result.CurrentStepId.Should().Be("M1");
        result.Summary.Should().Contain("M1 游戏场景创建未通过");

        var successRunId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.CompleteRunAsync(
            successRunId,
            "succeeded",
            0,
            "",
            "",
            """{"prototype_completion":{"succeeded":true},"godot_smoke":{"exit_code":0}}""");

        var recovered = await service.GetOrCreateLatestAsync(accountId, projectId);

        var recoveredM1 = recovered!.Steps.Single(step => step.StepId == "M1");
        recoveredM1.Status.Should().Be("executed");
        recoveredM1.ExecutionRunId.Should().Be(successRunId);
        recoveredM1.LatestEvidenceRelativePath.Should().NotBe(m1.LatestEvidenceRelativePath);
        File.ReadAllText(Path.Combine(project.RepoPath, recoveredM1.LatestEvidenceRelativePath!.Replace('/', Path.DirectorySeparatorChar)))
            .Should().Contain("\"status\": \"passed\"");
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_IgnoresValidationOnlyPrototypeFailure_WhenReconcilingM1SceneCreation()
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

        M1: First playable scene with WASD movement, mouse facing, combo, dodge, and first room feel validation.
        """);
        var runId = await store.CreateRunAsync(projectId, project.WorkspaceId, "prototype-7day-playable");
        await store.CompleteRunAsync(
            runId,
            "failed",
            1,
            "",
            "Godot validation failed.",
            """{"validation_only":true,"skeleton_validation_only":true,"godot_smoke":{"exit_code":1}}""");
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        var m1 = result!.Steps.Single(step => step.StepId == "M1");
        m1.Status.Should().Be("ready");
        m1.ExecutionRunId.Should().BeNull();
        m1.CanSubmitFeedback.Should().BeFalse();
        m1.CanExecute.Should().BeTrue();
    }

    [Fact]
    public async Task ExecuteCurrentStepAsync_WritesPrototypeEngineeringEvidence_AndExposesPath()
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

        M1: First playable scene and controls.
        """);
        var validation = new FakeLightweightValidationService(
            ValidationResult("validation-1", "succeeded", 0));
        var service = Service(store, options, validationService: validation);

        var result = await service.ExecuteCurrentStepAsync(accountId, projectId);

        result.Should().NotBeNull();
        var step = result!.Plan!.Steps.Single(item => item.StepId == "M1");
        step.Status.Should().Be("executed");
        step.LatestEvidenceRelativePath.Should().StartWith("logs/prototype-evidence/");
        var evidencePath = Path.Combine(project.RepoPath, step.LatestEvidenceRelativePath!.Replace('/', Path.DirectorySeparatorChar));
        File.Exists(evidencePath).Should().BeTrue();
        var evidence = File.ReadAllText(evidencePath);
        evidence.Should().Contain("\"route\": \"module-execute\"");
        evidence.Should().Contain("\"moduleId\": \"M1\"");
        evidence.Should().Contain("\"status\": \"passed\"");
        evidence.Should().Contain("\"dotnetBuild\":");
        evidence.Should().Contain("\"milestoneSmoke\":");
        evidence.Should().Contain("validation-1");
        evidence.Should().Contain("exitCode=0");
        File.ReadAllText(Path.Combine(project.RepoPath, "docs", "prototype", "MEMORY.md"))
            .Should().Contain("route=module-execute");

        await service.GetOrCreateLatestAsync(accountId, projectId);
        File.ReadAllText(Path.Combine(project.RepoPath, "docs", "prototype", "MEMORY.md"))
            .Should().Contain("route=module-execute");
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
        result!.Steps.Should().HaveCount(10);
        result.Steps.Select(step => step.StepId).Should().Equal("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10");
        result.Steps[0].Title.Should().Contain("M1");
        result.Steps[8].Description.Should().Contain("smoke");
        result.Steps[8].ScopeIn.Should().Contain("碰撞");
        result.Steps[9].PackagingValidation.Should().Contain("打包下载");
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
        var issuer = new HostedContextManifestIssuer(
            store,
            new HostedContextManifestSignatureService("test-key", new Dictionary<string, string>
            {
                ["test-key"] = "test-hosted-context-signing-secret"
            }));
        var llm = new FakeLlmRouteEngine(reviewJson);
        var service = Service(store, options, llm, contextManifestIssuer: issuer);

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
        var adjustedSpec = File.ReadAllText(Path.Combine(project.RepoPath, next.SpecRelativePath!.Replace('/', Path.DirectorySeparatorChar)));
        adjustedSpec.Should().Contain("Only adjust the first wave tempo");
        adjustedSpec.Should().Contain("Player can validate a slower first wave");
        adjustedSpec.Should().Contain("Tune the wave spawner");
        next.ReviewSummary.Should().Contain("调整 M2");
        llm.LastRequest!.OperationKey.Should().Be("llm:gdd-next-step-review");
        llm.LastRequest.ContextEnvelope.Should().NotBeNull();
        llm.LastRequest.ContextEnvelope!.AccountId.Should().Be(accountId);
        llm.LastRequest.ContextEnvelope.ProjectId.Should().Be(projectId);
        llm.LastRequest.ContextEnvelope.SignatureKeyId.Should().Be("test-key");
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
        var runner = new FakeHostedProcessRunner("""
        STATUS: completed
        VERIFY: Current module repair passed static check for the current milestone goal.
        REMAINING: none
        """);
        var service = Service(store, options, runner: runner);
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
        runner.StandardInputs.Should().Contain(input => input.Contains("Combat pressure interpretation guard", StringComparison.Ordinal));
        runner.StandardInputs.Should().Contain(input => input.Contains("Do not implement hidden damage-over-time", StringComparison.Ordinal));
    }

    [Fact]
    public async Task SubmitFeedbackAsync_RunsLightweightValidationAfterNeedsFixCompletes()
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
        """);
        var validation = new FakeLightweightValidationService(ValidationResult("validation-1", "succeeded", 0));
        await Service(store, options).ExecuteCurrentStepAsync(accountId, projectId);
        var service = Service(store, options, validationService: validation);

        var result = await service.SubmitFeedbackAsync(
            accountId,
            projectId,
            "M1",
            new GddMilestoneStepFeedbackRequest("Please repair M1 and keep it scoped to the current milestone."));

        result.Should().NotBeNull();
        var step = result!.Plan!.Steps.Single(step => step.StepId == "M1");
        step.Status.Should().Be("feedback_submitted");
        step.CanConfirm.Should().BeTrue();
        step.ExecutionRunId.Should().Be(step.FeedbackRunId);
        step.ExecutionSummary.Should().Be(step.FeedbackSummary);
        step.ExecutionSummary.Should().Contain("轻量验收已通过");
        validation.Calls.Should().Be(1);
    }

    [Fact]
    public async Task SubmitFeedbackAsync_WhenSuccessfulRepairFeedbackContainsOldFailureText_DoesNotReopenNeedsFix()
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
        """);
        var validation = new FakeLightweightValidationService(ValidationResult("validation-1", "succeeded", 0));
        await Service(store, options).ExecuteCurrentStepAsync(accountId, projectId);
        var service = Service(store, options, validationService: validation);

        var result = await service.SubmitFeedbackAsync(
            accountId,
            projectId,
            "M1",
            new GddMilestoneStepFeedbackRequest("""
            请根据当前模块 M1 的最近执行结果直接修复。
            最近执行结果：
            M1 轻量验收未通过，需要修复旧的编译错误。
            """));
        var reloaded = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        var returnedStep = result!.Plan!.Steps.Single(step => step.StepId == "M1");
        var persistedStep = reloaded!.Steps.Single(step => step.StepId == "M1");
        returnedStep.Status.Should().Be("feedback_submitted");
        returnedStep.CanConfirm.Should().BeTrue();
        returnedStep.ExecutionSummary.Should().Contain("轻量验收已通过");
        returnedStep.ExecutionSummary.Should().NotContain("未通过");
        returnedStep.ExecutionSummary.Should().NotContain("需要修复");
        persistedStep.Status.Should().Be("feedback_submitted");
        persistedStep.CanConfirm.Should().BeTrue();
        persistedStep.CanSubmitFeedback.Should().BeTrue();
        validation.Calls.Should().Be(1);
    }

    [Fact]
    public async Task SubmitFeedbackAsync_LeavesStepInNeedsFix_WhenPostFeedbackValidationIsExhausted()
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
        """);
        var validation = new FakeLightweightValidationService(
            ValidationResult("validation-1", "failed", 1, stderr: "first failure"),
            ValidationResult("validation-2", "failed", 1, stderr: "second failure"),
            ValidationResult("validation-3", "failed", 1, stderr: "third failure"),
            ValidationResult("validation-4", "failed", 1, stderr: "fourth failure"));
        await Service(store, options).ExecuteCurrentStepAsync(accountId, projectId);
        var service = Service(store, options, validationService: validation);

        var result = await service.SubmitFeedbackAsync(
            accountId,
            projectId,
            "M1",
            new GddMilestoneStepFeedbackRequest("Please repair M1 and keep it scoped to the current milestone."));

        result.Should().NotBeNull();
        var step = result!.Plan!.Steps.Single(step => step.StepId == "M1");
        step.Status.Should().Be("needs_fix");
        step.CanConfirm.Should().BeFalse();
        step.CanSubmitFeedback.Should().BeTrue();
        step.ExecutionRunId.Should().Be(step.FeedbackRunId);
        step.ExecutionSummary.Should().Be(step.FeedbackSummary);
        step.ExecutionSummary.Should().Contain("轻量验收未通过");
        validation.Calls.Should().Be(4);
    }

    [Fact]
    public async Task ExecuteCurrentStepAsync_TreatsCompletedMilestoneOutputAsExecuted_EvenWhenGenericSessionPausedForReview()
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
        # Single Step GDD

        M1: First playable scene and controls.
        """);
        var runnerOutput = """
        STATUS: completed
        SUMMARY: M1 is implemented and ready for player confirmation.
        CHANGED: gameplay slice
        VERIFY: quick code-level check completed
        REMAINING: none
        """;
        var runner = new FakeHostedProcessRunner(runnerOutput);
        var service = Service(store, options, runner: runner, runnerOutput: runnerOutput);

        var result = await service.ExecuteCurrentStepAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.StepExecution.Should().NotBeNull();
        result.StepExecution!.Status.Should().Be("completed");
        result.StepExecution.SessionStatus.Should().Be("completed");
        result.Plan!.Steps.Single(step => step.StepId == "M1").Status.Should().Be("executed");
        result.Plan.Steps.Single(step => step.StepId == "M1").CanConfirm.Should().BeTrue();
        result.Plan.Steps.Single(step => step.StepId == "M1").CanSubmitFeedback.Should().BeTrue();
        var run = await store.GetRunSnapshotAsync(result.StepExecution.RunId);
        run!.ProgressStep.Should().Be("completed");
        run.ProgressLabel.Should().Contain("M1 已执行完成");
        runner.StandardInputs.Should().Contain(input => input.Contains("Combat pressure interpretation guard", StringComparison.Ordinal));
        runner.StandardInputs.Should().Contain(input => input.Contains("standing-still damage", StringComparison.Ordinal));
        runner.StandardInputs.Should().Contain(input => input.Contains("Physics embodiment policy", StringComparison.Ordinal));
        runner.StandardInputs.Should().Contain(input => input.Contains("Local prototype entry contract", StringComparison.Ordinal));
        runner.StandardInputs.Should().Contain(input => input.Contains("default_scene", StringComparison.Ordinal) &&
                                                        input.Contains("smoke_scene", StringComparison.Ordinal) &&
                                                        input.Contains("playable_scene", StringComparison.Ordinal));
    }

    [Fact]
    public void LocalEntryContractValidator_Passes_WhenEntrySceneInstancesPlayableScene()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        WriteText(repoRoot.Path, "Game.Godot/Prototypes/demo/DemoPrototype.tscn", """
        [gd_scene load_steps=2 format=3]

        [ext_resource id="1" path="res://Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn" type="PackedScene"]

        [node name="DemoPrototype" type="Node2D"]

        [node name="PrototypeLoop" type="Node2D" parent="."]

        [node name="FirstPlayableRaid" parent="PrototypeLoop" instance=ExtResource("1")]
        """);
        WriteText(repoRoot.Path, "Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn", "[gd_scene format=3]\n");
        var state = """
        {
          "default_scene": "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
          "smoke_scene": "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
          "playable_scene": "res://Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn",
          "local_entry_contract": {
            "status": "ready",
            "entry_scene_instances_playable_scene": true
          }
        }
        """;

        var result = PrototypeLocalEntryContractValidator.Validate(repoRoot.Path, state);

        result.Passed.Should().BeTrue();
        result.DefaultScene.Should().Be("res://Game.Godot/Prototypes/demo/DemoPrototype.tscn");
        result.PlayableScene.Should().Be("res://Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn");
    }

    [Fact]
    public void LocalEntryContractValidator_Fails_WhenDefaultSceneDoesNotMatchProjectContract()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        WriteText(repoRoot.Path, "Game.Godot/Prototypes/demo/DemoPrototype.tscn", "[gd_scene format=3]\n");
        WriteText(repoRoot.Path, "Game.Godot/Prototypes/demo/GenericPrototype.tscn", "[gd_scene format=3]\n");
        WriteText(repoRoot.Path, "meta/routes/prototype-contract/latest.json", """
        {
          "local_entry_contract": {
            "expected_entry_scene": "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn"
          }
        }
        """);
        var state = """
        {
          "default_scene": "res://Game.Godot/Prototypes/demo/GenericPrototype.tscn",
          "smoke_scene": "res://Game.Godot/Prototypes/demo/GenericPrototype.tscn",
          "playable_scene": "res://Game.Godot/Prototypes/demo/GenericPrototype.tscn",
          "local_entry_contract": {
            "status": "ready",
            "entry_scene_instances_playable_scene": false
          }
        }
        """;

        var result = PrototypeLocalEntryContractValidator.Validate(repoRoot.Path, state);

        result.Passed.Should().BeFalse();
        result.Status.Should().Be("local_entry_project_specific_scene_mismatch");
        result.Summary.Should().Contain("expected=res://Game.Godot/Prototypes/demo/DemoPrototype.tscn");
    }

    [Fact]
    public void LocalEntryContractValidator_Fails_WhenContractIsMissing()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        WriteText(repoRoot.Path, "Game.Godot/Prototypes/demo/DemoPrototype.tscn", "[gd_scene format=3]\n");
        var state = """
        {
          "default_scene": "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
          "smoke_scene": "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
          "playable_scene": "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn"
        }
        """;

        var result = PrototypeLocalEntryContractValidator.Validate(repoRoot.Path, state);

        result.Passed.Should().BeFalse();
        result.Status.Should().Be("local_entry_contract_missing_fields");
        result.Summary.Should().Contain("local_entry_contract");
    }

    [Fact]
    public void LocalEntryContractValidator_Fails_WhenInstanceFlagIsFalseAndScenesDiffer()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        WriteText(repoRoot.Path, "Game.Godot/Prototypes/demo/DemoPrototype.tscn", """
        [gd_scene load_steps=2 format=3]

        [ext_resource id="1" path="res://Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn" type="PackedScene"]

        [node name="DemoPrototype" type="Node2D"]

        [node name="FirstPlayableRaid" parent="." instance=ExtResource("1")]
        """);
        WriteText(repoRoot.Path, "Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn", "[gd_scene format=3]\n");
        var state = """
        {
          "default_scene": "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
          "smoke_scene": "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
          "playable_scene": "res://Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn",
          "local_entry_contract": {
            "status": "ready",
            "entry_scene_instances_playable_scene": false
          }
        }
        """;

        var result = PrototypeLocalEntryContractValidator.Validate(repoRoot.Path, state);

        result.Passed.Should().BeFalse();
        result.Status.Should().Be("local_entry_contract_instance_flag_missing");
    }

    [Fact]
    public void LocalEntryContractValidator_Fails_WhenPlayableSceneIsMissing()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        WriteText(repoRoot.Path, "Game.Godot/Prototypes/demo/DemoPrototype.tscn", "[gd_scene format=3]\n");
        var state = """
        {
          "default_scene": "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
          "smoke_scene": "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
          "playable_scene": "res://Game.Godot/Prototypes/demo/MissingPlayable.tscn",
          "local_entry_contract": {
            "status": "ready",
            "entry_scene_instances_playable_scene": true
          }
        }
        """;

        var result = PrototypeLocalEntryContractValidator.Validate(repoRoot.Path, state);

        result.Passed.Should().BeFalse();
        result.Status.Should().Be("local_entry_scene_invalid");
        result.Summary.Should().Contain("playable_scene");
    }

    [Fact]
    public void LocalEntryContractValidator_Passes_WhenPackedSceneAttributesAreOutOfOrder()
    {
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        WriteText(repoRoot.Path, "Game.Godot/Prototypes/demo/DemoPrototype.tscn", """
        [gd_scene load_steps=2 format=3]

        [ext_resource uid="uid://demo" type="PackedScene" path="res://Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn" id="raid"]

        [node name="DemoPrototype" type="Node2D"]

        [node name="FirstPlayableRaid" parent="." instance=ExtResource("raid")]
        """);
        WriteText(repoRoot.Path, "Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn", "[gd_scene format=3]\n");
        var state = """
        {
          "default_scene": "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
          "smoke_scene": "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
          "playable_scene": "res://Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn",
          "local_entry_contract": {
            "status": "ready",
            "entry_scene_instances_playable_scene": true
          }
        }
        """;

        var result = PrototypeLocalEntryContractValidator.Validate(repoRoot.Path, state);

        result.Passed.Should().BeTrue();
        result.PlayableScene.Should().Be("res://Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn");
    }

    [Fact]
    public async Task ExecuteCurrentStepAsync_Fails_WhenLocalEntryDoesNotInstancePlayableScene()
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
        # Single Step GDD

        M1: First playable scene and controls.
        """);
        WriteText(project.RepoPath, "Game.Godot/Prototypes/demo/ShellPrototype.tscn", """
        [gd_scene format=3]

        [node name="ShellPrototype" type="Node2D"]
        """);
        WriteText(project.RepoPath, "Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn", "[gd_scene format=3]\n");
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            slug = "demo",
            default_scene = "res://Game.Godot/Prototypes/demo/ShellPrototype.tscn",
            smoke_scene = "res://Game.Godot/Prototypes/demo/ShellPrototype.tscn",
            playable_scene = "res://Game.Godot/Prototypes/demo/FirstPlayableRaid.tscn",
            local_entry_contract = new
            {
                status = "ready",
                entry_scene_instances_playable_scene = true
            },
            prototype_completion = new
            {
                succeeded = true,
                smoke_scene = "res://Game.Godot/Prototypes/demo/ShellPrototype.tscn"
            }
        });
        var validation = new FakeLightweightValidationService(
            ValidationResult("validation-1", "succeeded", 0),
            ValidationResult("validation-2", "succeeded", 0),
            ValidationResult("validation-3", "succeeded", 0),
            ValidationResult("validation-4", "succeeded", 0));
        var service = Service(store, options, validationService: validation);

        var result = await service.ExecuteCurrentStepAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.NeedsFixRun.Should().NotBeNull();
        var step = result.Plan!.Steps.Single(step => step.StepId == "M1");
        step.Status.Should().Be("needs_fix");
        step.ExecutionSummary.Should().Contain("local_entry_contract_failed");
        step.CanConfirm.Should().BeFalse();
        step.CanSubmitFeedback.Should().BeTrue();
        step.LatestEvidenceRelativePath.Should().NotBeNullOrWhiteSpace();
        var evidencePath = Path.Combine(project.RepoPath, step.LatestEvidenceRelativePath!.Replace('/', Path.DirectorySeparatorChar));
        var evidence = File.ReadAllText(evidencePath);
        using var evidenceJson = JsonDocument.Parse(evidence);
        var localEntryContract = evidenceJson.RootElement.GetProperty("checks").GetProperty("localEntryContract");
        localEntryContract.GetProperty("status").GetString().Should().Be("failed");
        localEntryContract.GetProperty("reason").GetString().Should().Contain("local_entry_contract_failed");
        validation.Calls.Should().Be(4);
    }

    [Fact]
    public async Task ExecuteCurrentStepAsync_AutoRepairs_WhenLightweightValidationFailsThenPasses()
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
        # Single Step GDD

        M1: First playable scene and controls.
        """);
        var validation = new FakeLightweightValidationService(
            ValidationResult("validation-1", "failed", 1, stderr: "Godot smoke failed."),
            ValidationResult("validation-2", "succeeded", 0));
        var service = Service(store, options, validationService: validation);

        var result = await service.ExecuteCurrentStepAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.NeedsFixRun.Should().NotBeNull();
        result.Plan!.Steps.Single(step => step.StepId == "M1").Status.Should().Be("executed");
        result.Plan.Steps.Single(step => step.StepId == "M1").CanConfirm.Should().BeTrue();
        validation.Calls.Should().Be(2);
    }

    [Fact]
    public async Task ExecuteCurrentStepAsync_LeavesStepInNeedsFix_WhenAutoRepairValidationIsExhausted()
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
        # Single Step GDD

        M1: First playable scene and controls.
        """);
        var validation = new FakeLightweightValidationService(
            ValidationResult("validation-1", "failed", 1, stderr: "first failure"),
            ValidationResult("validation-2", "failed", 1, stderr: "second failure"),
            ValidationResult("validation-3", "failed", 1, stderr: "third failure"),
            ValidationResult("validation-4", "failed", 1, stderr: "fourth failure"));
        var service = Service(store, options, validationService: validation);

        var result = await service.ExecuteCurrentStepAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.NeedsFixRun.Should().NotBeNull();
        var step = result.Plan!.Steps.Single(step => step.StepId == "M1");
        step.Status.Should().Be("needs_fix");
        step.CanConfirm.Should().BeFalse();
        step.CanSubmitFeedback.Should().BeTrue();
        validation.Calls.Should().Be(4);
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_ReconcilesLegacyNeedsFix_WhenExecutionRunOutputShowsCompleted()
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
        # Single Step GDD

        M1: First playable scene and controls.
        """);
        var runId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "prototype-iteration-goal");
        var outputRelativePath = "logs/phase-a-iteration/test-run/codex-output.txt";
        WriteText(project.RepoPath, outputRelativePath, """
        STATUS: completed
        SUMMARY: M1 completed.
        VERIFY: quick code-level check completed
        REMAINING: none
        """);
        await store.CompleteRunAsync(
            runId,
            "completed",
            0,
            "",
            "",
            $$"""{"codex_output":"{{outputRelativePath}}"}""");
        WriteNeedsFixStepState(project.MetaPath, project.RepoPath, runId);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        var step = result!.Steps.Single(item => item.StepId == "M1");
        step.Status.Should().Be("executed");
        step.CanConfirm.Should().BeTrue();
        result.Summary.Should().Contain("可以直接确认完成");
        var run = await store.GetRunSnapshotAsync(runId);
        run!.ProgressStep.Should().Be("completed");
    }

    [Fact]
    public async Task GetOrCreateLatestAsync_RecoversTransientStepStatus_ToRetryableState()
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
        # Single Step GDD

        M1: First playable scene and controls.
        """);
        WriteTransientStepState(project.MetaPath, project.RepoPath);
        var service = Service(store, options);

        var result = await service.GetOrCreateLatestAsync(accountId, projectId);

        result.Should().NotBeNull();
        var step = result!.Steps.Single(item => item.StepId == "M1");
        step.Status.Should().Be("timed_out");
        step.CanExecute.Should().BeTrue();
        step.CanSubmitFeedback.Should().BeTrue();
        step.CanConfirm.Should().BeFalse();
    }

    private static GddMilestoneStepService Service(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        ILlmRouteEngine? llmRouteEngine = null,
        string runnerOutput = """
        STATUS: completed
        VERIFY: Current module repair passed static check for the current milestone goal.
        REMAINING: none
        """,
        IPrototypeLightweightValidationService? validationService = null,
        FakeHostedProcessRunner? runner = null,
        IPrototypeFromGddWorkflow? prototypeWorkflow = null,
        HostedContextManifestIssuer? contextManifestIssuer = null)
    {
        runner ??= new FakeHostedProcessRunner(runnerOutput);
        return new GddMilestoneStepService(
            store,
            new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), new PrototypeRouteStateWriter()),
            new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), new PrototypeRouteStateWriter()),
            llmRouteEngine,
            validationService,
            prototypeWorkflowService: prototypeWorkflow,
            contextManifestIssuer: contextManifestIssuer);
    }

    private static PrototypeWorkflowResult ValidationResult(string runId, string status, int exitCode, string stdout = "", string stderr = "")
    {
        return new PrototypeWorkflowResult(runId, status, exitCode, "docs/prototypes/demo.md", stdout, stderr, [], []);
    }

    private static async Task<string> CreateProjectAsync(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        string accountId,
        bool seedPrototypeBaseline = true)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "Action Roguelike", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(result.ProjectId!);
        if (seedPrototypeBaseline)
        {
            SeedPrototypeBaseline(project!);
        }
        else
        {
            SeedRouteSkill(project!);
        }

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

    private static void WriteOutline(string repoPath, string text)
    {
        var path = Path.Combine(repoPath, "docs", "gdd", "gdd-outline.json");
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, text);
    }

    private static void WriteCompletedAndReadyStepState(string metaPath, string repoPath)
    {
        const string payload = """
{
  "schema": "phase-a.gdd-milestone-steps.v2",
  "status": "ready",
  "summary": "existing state",
  "currentStepId": "M2",
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
      "status": "confirmed",
      "locked": false,
      "confirmedUtc": "2026-06-24T00:00:00Z"
    },
    {
      "stepId": "M2",
      "stepIndex": 2,
      "title": "M2: Active skills.",
      "description": "Active skills.",
      "acceptance": "",
      "scopeIn": "",
      "scopeOut": "",
      "godotSlice": "",
      "packagingValidation": "",
      "feedbackGuidance": "",
      "nextStepReview": "",
      "status": "ready",
      "locked": false
    }
  ]
}
""";
        WriteStepState(metaPath, repoPath, payload);
    }

    private static void WriteM3ReadyStepState(string metaPath, string repoPath)
    {
        const string payload = """
{
  "schema": "phase-a.gdd-milestone-steps.v2",
  "status": "ready",
  "summary": "M3 ready state without run result",
  "currentStepId": "M3",
  "steps": [
    {
      "stepId": "M1",
      "stepIndex": 1,
      "title": "M1: First playable room.",
      "description": "First playable room.",
      "acceptance": "",
      "scopeIn": "",
      "scopeOut": "",
      "godotSlice": "",
      "packagingValidation": "",
      "feedbackGuidance": "",
      "nextStepReview": "",
      "status": "confirmed",
      "locked": false,
      "confirmedUtc": "2026-06-24T00:00:00Z"
    },
    {
      "stepId": "M2",
      "stepIndex": 2,
      "title": "M2: Skill pressure.",
      "description": "Skill pressure.",
      "acceptance": "",
      "scopeIn": "",
      "scopeOut": "",
      "godotSlice": "",
      "packagingValidation": "",
      "feedbackGuidance": "",
      "nextStepReview": "",
      "status": "confirmed",
      "locked": false,
      "confirmedUtc": "2026-06-24T00:05:00Z"
    },
    {
      "stepId": "M3",
      "stepIndex": 3,
      "title": "M3: Run upgrade loop.",
      "description": "Run upgrade loop.",
      "acceptance": "",
      "scopeIn": "",
      "scopeOut": "",
      "godotSlice": "",
      "packagingValidation": "",
      "feedbackGuidance": "",
      "nextStepReview": "",
      "status": "ready",
      "locked": false
    }
  ]
}
""";
        WriteStepState(metaPath, repoPath, payload);
    }

    private static void WriteM3StaleRepairStepState(string metaPath, string repoPath, string executionRunId, string staleRepairRunId)
    {
        var payload = $$"""
{
  "schema": "phase-a.gdd-milestone-steps.v2",
  "status": "ready",
  "summary": "stale state",
  "currentStepId": "M3",
  "steps": [
    {
      "stepId": "M1",
      "stepIndex": 1,
      "title": "M1: First playable room.",
      "description": "First playable room.",
      "acceptance": "",
      "scopeIn": "",
      "scopeOut": "",
      "godotSlice": "",
      "packagingValidation": "",
      "feedbackGuidance": "",
      "nextStepReview": "",
      "status": "confirmed",
      "locked": false,
      "confirmedUtc": "2026-06-24T00:00:00Z"
    },
    {
      "stepId": "M2",
      "stepIndex": 2,
      "title": "M2: Skill pressure.",
      "description": "Skill pressure.",
      "acceptance": "",
      "scopeIn": "",
      "scopeOut": "",
      "godotSlice": "",
      "packagingValidation": "",
      "feedbackGuidance": "",
      "nextStepReview": "",
      "status": "confirmed",
      "locked": false,
      "confirmedUtc": "2026-06-24T00:05:00Z"
    },
    {
      "stepId": "M3",
      "stepIndex": 3,
      "title": "M3: Run upgrade loop.",
      "description": "Run upgrade loop.",
      "acceptance": "",
      "scopeIn": "",
      "scopeOut": "",
      "godotSlice": "",
      "packagingValidation": "",
      "feedbackGuidance": "",
      "nextStepReview": "",
      "status": "feedback_submitted",
      "locked": false,
      "iterationSessionId": "stale-session",
      "executionRunId": "{{executionRunId}}",
      "executionSummary": "M3 old execution summary.",
      "feedbackRunId": "{{staleRepairRunId}}",
      "feedbackSummary": "stale repair still says Godot smoke failed.",
      "latestEvidenceRelativePath": "logs/prototype-evidence/stale-repair.json"
    }
  ]
}
""";
        WriteStepState(metaPath, repoPath, payload);
    }

    private static void WriteAllConfirmedStepState(string metaPath, string repoPath)
    {
        const string payload = """
{
  "schema": "phase-a.gdd-milestone-steps.v2",
  "status": "completed",
  "summary": "all completed",
  "currentStepId": null,
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
      "status": "confirmed",
      "locked": false,
      "confirmedUtc": "2026-06-24T00:00:00Z"
    }
  ]
}
""";
        WriteStepState(metaPath, repoPath, payload);
    }

    private static void WriteAllConfirmedStepState(string metaPath, string repoPath, int count)
    {
        var steps = Enumerable.Range(1, count)
            .Select(index => new
            {
                stepId = $"M{index}",
                stepIndex = index,
                title = $"M{index}: Module {index}.",
                description = $"Module {index}.",
                acceptance = "",
                scopeIn = "",
                scopeOut = "",
                godotSlice = "",
                packagingValidation = "",
                feedbackGuidance = "",
                nextStepReview = "",
                status = "confirmed",
                locked = false,
                confirmedUtc = $"2026-06-24T00:{index:00}:00Z"
            })
            .ToArray();
        var payload = JsonSerializer.Serialize(new
        {
            schema = "phase-a.gdd-milestone-steps.v2",
            status = "completed",
            summary = "all completed",
            currentStepId = (string?)null,
            steps
        });
        WriteStepState(metaPath, repoPath, payload);
    }

    private static void WriteStepState(string metaPath, string repoPath, string payload)
    {
        foreach (var root in new[] { metaPath, Path.Combine(repoPath, "meta") })
        {
            var path = Path.Combine(root, "routes", "gdd-milestones", "latest.json");
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, payload);
        }
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
        WriteStepState(metaPath, repoPath, payload);
    }

    private static void WriteNeedsFixStepState(string metaPath, string repoPath, string runId)
    {
        var payload = $$"""
{
  "schema": "phase-a.gdd-milestone-steps.v2",
  "status": "ready",
  "summary": "legacy needs_fix state",
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
      "status": "needs_fix",
      "locked": false,
      "iterationSessionId": "legacy-session-1",
      "executionRunId": "{{runId}}"
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

    private static void WriteTransientStepState(string metaPath, string repoPath)
    {
        const string payload = """
{
  "schema": "phase-a.gdd-milestone-steps.v2",
  "status": "ready",
  "summary": "interrupted transient state",
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
      "status": "validating",
      "locked": false,
      "iterationSessionId": "interrupted-session-1",
      "executionRunId": "interrupted-run-1"
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

    private static void WriteRunningSkeletonStepState(string metaPath, string repoPath, string runId)
    {
        var payload = $$"""
{
  "schema": "phase-a.gdd-milestone-steps.v2",
  "status": "running",
  "summary": "M1 scene creation queued.",
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
      "status": "running",
      "locked": false,
      "iterationSessionId": "m1-scene-session",
      "executionRunId": "{{runId}}",
      "executionSummary": "M1 scene creation queued."
    },
    {
      "stepId": "M2",
      "stepIndex": 2,
      "title": "M2: Core loop validation.",
      "description": "Core loop validation.",
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
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            marker = "prototype-baseline",
            slug = "demo",
            default_scene = "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
            smoke_scene = "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
            playable_scene = "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn",
            local_entry_contract = new
            {
                status = "ready",
                entry_scene_instances_playable_scene = false
            },
            prototype_completion = new
            {
                succeeded = true,
                smoke_scene = "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn"
            }
        });
        SeedRouteSkill(project);
        WriteText(project.RepoPath, "Game.Core/Prototypes/DemoPrototypeLoop.cs", """
public sealed class DemoPrototypeLoop
{
    public const string LoopAcceptanceMarker = "Loop continues with visible State and Feedback.";

    public DemoPrototypeState CraftBurger(DemoPrototypeState state)
    {
        return state with { LastMessage = "Craft result feedback is visible. Loop can continue.", CraftFeedback = "Result state changed." };
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
        WriteText(project.RepoPath, "Game.Godot/Prototypes/demo/DemoPrototype.tscn", """
[gd_scene format=3]

[node name="DemoPrototype" type="Node"]
""");
    }

    private static void SeedRouteSkill(ProjectSnapshot project)
    {
        WriteText(project.RepoPath, ".agents/skills/prototype-7day-playable-godot-zh/SKILL.md", "# skill\n");
    }

    private static void WriteText(string repoPath, string relativePath, string text)
    {
        var path = Path.Combine(repoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, text);
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        private readonly string _output;

        public List<string> StandardInputs { get; } = [];

        public FakeHostedProcessRunner(string output)
        {
            _output = output;
        }

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (!string.IsNullOrWhiteSpace(command.StandardInput))
            {
                StandardInputs.Add(command.StandardInput);
            }

            if (command.Arguments.Any(argument =>
                    argument.Contains("smoke_headless.py", StringComparison.OrdinalIgnoreCase) ||
                    argument.Contains("prototype_main_menu_navigation_smoke.py", StringComparison.OrdinalIgnoreCase)))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS", ""));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).FirstOrDefault();
            if (!string.IsNullOrWhiteSpace(outputPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
                File.WriteAllText(outputPath, _output);
            }

            return Task.FromResult(new HostedProcessResult(0, _output, ""));
        }
    }

    private sealed class FakePrototypeFromGddWorkflow : IPrototypeFromGddWorkflow
    {
        private readonly PrototypeWorkflowResult _result;

        public FakePrototypeFromGddWorkflow(PrototypeWorkflowResult result)
        {
            _result = result;
        }

        public int Calls { get; private set; }

        public string? LastAccountId { get; private set; }

        public string? LastProjectId { get; private set; }

        public Task<PrototypeWorkflowResult> QueueFromGddAsync(
            string accountId,
            string projectId,
            PrototypeFromGddRequest request,
            CancellationToken cancellationToken = default)
        {
            Calls++;
            LastAccountId = accountId;
            LastProjectId = projectId;
            return Task.FromResult(_result);
        }
    }

    private sealed class FakeLlmRouteEngine : ILlmRouteEngine
    {
        private readonly string _json;

        public FakeLlmRouteEngine(string json)
        {
            _json = json;
        }

        public LlmRouteRequest? LastRequest { get; private set; }

        public Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            LastRequest = request;
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

    private sealed class FakeLightweightValidationService : IPrototypeLightweightValidationService
    {
        private readonly Queue<PrototypeWorkflowResult> _results;

        public FakeLightweightValidationService(params PrototypeWorkflowResult[] results)
        {
            _results = new Queue<PrototypeWorkflowResult>(results);
        }

        public int Calls { get; private set; }

        public Task<PrototypeWorkflowResult> ValidateAsync(string accountId, string projectId, CancellationToken cancellationToken = default)
        {
            Calls++;
            return Task.FromResult(_results.Count == 0
                ? ValidationResult("validation-fallback", "failed", 1, stderr: "validation exhausted")
                : _results.Dequeue());
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
