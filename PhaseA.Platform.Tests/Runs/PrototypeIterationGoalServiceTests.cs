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
        var options = Options(workspaceRoot.Path, repoRoot.Path);
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
        var options = Options(workspaceRoot.Path, repoRoot.Path);
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
        new PrototypeContractService().WriteFromRequest(project!, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "contract");
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
        run.ProgressStep.Should().Be("completed");
        run.ProgressSubstep.Should().Be("succeeded");
        run.ProgressLabel.Should().Be("目标 1 已完成。");
        details.Should().NotBeNull();
        details!.Session.Status.Should().Be("paused_for_review");
        details.Session.LatestEvaluationJson.Should().NotBeNullOrWhiteSpace();
        details.LatestEvaluation.Should().NotBeNull();
        details.LatestEvaluation!.Decision.Should().Be("ready_to_execute");
        details.Goals[0].Status.Should().Be("succeeded");
        details.Goals[1].Status.Should().Be("pending");
        var codexCommand = runner.Commands.Single(command => command.Arguments.LastOrDefault() == "-");
        codexCommand.StandardInput.Should().Contain("prototype-baseline");
        codexCommand.StandardInput.Should().Contain("Project prototype contract");
        codexCommand.StandardInput.Should().Contain("Platform hard acceptance for RPG Step 1");
        codexCommand.StandardInput.Should().Contain("Game.Godot/Prototypes/dq-rpg/MapScene.tscn");
        codexCommand.StandardInput.Should().Contain("Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs");
        codexCommand.StandardInput.Should().Contain("RpgPlayerAsset");
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
        runner.Commands.Should().Contain(command =>
            command.FileName == "dotnet" &&
            command.Arguments.SequenceEqual(new[] { "build-server", "shutdown" }));
        stateWriter.ReadLatestExecuteNextGoalState(project!, 1).Should().Contain(result.RunId);
        stateWriter.ReadLatestExecuteNextGoalState(project!, 1).Should().Contain("prototype_contract");
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
        var options = Options(workspaceRoot.Path, repoRoot.Path);
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

    [Theory]
    [InlineData(1, "rpg-step1-navigation-encounter-entry")]
    [InlineData(2, "rpg-step2-battlescene-settlement")]
    [InlineData(3, "rpg-step3-reward-loop-return-map")]
    [InlineData(4, "rpg-step4-main-loop-scene-switching")]
    public async Task ExecuteNextAsync_ShouldUseRpgRouteAcceptanceKinds_ForNavigationFirstSteps(
        int goalIndex,
        string expectedAcceptanceKind)
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
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG prototype through the strict route-profile steps."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var now = DateTimeOffset.UtcNow.ToString("O");
        foreach (var goal in details!.Goals.Where(goal => goal.GoalIndex < goalIndex))
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "succeeded", $"Goal {goal.GoalIndex} already completed.", now);
        }

        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WriteProjectReadme(project);
        new PrototypeContractService().WriteFromRequest(project, ContractRequest(), "docs/prototypes/2026-05-20-contract.md", "contract");
        stateWriter.WritePrototypeState(project, new { route = "prototype-7day-playable", marker = "prototype-baseline" });
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), stateWriter);

        var result = await service.ExecuteNextAsync(accountId, projectId);
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.GoalIndex.Should().Be(goalIndex);
        refreshed!.Goals.Single(goal => goal.GoalIndex == goalIndex).Status.Should().Be("succeeded");
        run!.EvidenceJson.Should().Contain($"\"acceptance_validation\":\"{expectedAcceptanceKind}\"");
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
        result.GoalIndex.Should().Be(1);
        refreshed!.Goals.Single(goal => goal.GoalIndex == 1).Status.Should().Be("succeeded");
        run!.EvidenceJson.Should().Contain("\"acceptance_validation\":\"rpg-step1-navigation-encounter-entry\"");
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
        var now = DateTimeOffset.UtcNow.ToString("O");
        foreach (var goal in details!.Goals.Where(goal => goal.GoalIndex < 6))
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "succeeded", $"Goal {goal.GoalIndex} already completed.", now);
        }

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
        result.GoalIndex.Should().Be(6);
        refreshed!.Goals.Single(goal => goal.GoalIndex == 6).Status.Should().Be("succeeded");
        runner.Commands.Should().Contain(command => command.FileName == "dotnet" && command.Arguments.Contains("test"));
        runner.Commands.Should().Contain(command => command.FileName == "dotnet" && command.Arguments.Contains("build"));
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/smoke_headless.py", StringComparison.Ordinal)));
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/prototype_main_menu_navigation_smoke.py", StringComparison.Ordinal)));
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
        var now = DateTimeOffset.UtcNow.ToString("O");
        foreach (var goal in details!.Goals.Where(goal => goal.GoalIndex < 6))
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "succeeded", $"Goal {goal.GoalIndex} already completed.", now);
        }

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
        result.GoalIndex.Should().Be(6);
        refreshed!.Goals.Single(goal => goal.GoalIndex == 6).Status.Should().Be("needs_fix");
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
        var now = DateTimeOffset.UtcNow.ToString("O");
        foreach (var goal in details!.Goals.Where(goal => goal.GoalIndex < 6))
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "succeeded", $"Goal {goal.GoalIndex} already completed.", now);
        }

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
        result.GoalIndex.Should().Be(6);
        detailsAfter!.Goals.Single(goal => goal.GoalIndex == 6).ResultSummary.Should().Contain("rpg_form_contract_values_not_reflected");
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
[gd_scene format=3]

[node name="BattleScene" type="Node"]
[node name="AttackButton" type="Button" parent="."]
text = "Attack"
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
