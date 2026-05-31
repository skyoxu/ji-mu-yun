using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;
using System.Text.Json;

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

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));
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
    public async Task SubmitAsync_RejectsProjectOwnedByAnotherAccount()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var ownerAccountId = await store.EnsureSingleAdminAsync();
        var otherAccount = await store.CreateUserAccountAsync("quick-fix-other-account", 1);
        var projectId = await CreateProjectAsync(store, options, ownerAccountId, prototypeSucceeded: true);
        var runner = new FakeHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var act = () => service.SubmitAsync(
            otherAccount.AccountId,
            projectId,
            new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("Project not found.");
        runner.Commands.Should().BeEmpty();
    }

    [Fact]
    public async Task SubmitAsync_NonGoalRpgQuickFix_ShouldFailRun_WhenPostFixPrototypeSmokeFails()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        new PrototypeRouteStateWriter().WritePrototypeState(project!, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        var runner = new QuickFixNavigationFailHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest("修复 Start Adventure 后空白。", "gpt-5.4", "normal"));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.AssistantMessage.Should().Contain("STATUS: needs_fix");
        run!.Status.Should().Be("failed");
        run.ProgressStep.Should().Be("failed");
        run.ProgressSubstep.Should().Be("validation");
        run.EvidenceJson.Should().Contain("project_smoke_validation");
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/smoke_headless.py", StringComparison.Ordinal)));
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/prototype_main_menu_navigation_smoke.py", StringComparison.Ordinal)));
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

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest("Fix prototype menu routing.", "gpt-5.4", "normal"));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("failed");
        result.AssistantMessage.Should().Contain("快速修复超时");
        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(408);
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPromoteGoal_WhenTimedOutRepairAlreadyPassesValidation()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair map entry smoke validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Godot navigation smoke failed.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new TimedOutValidatedGoalRepairRunner();
        var service = new PrototypeQuickFixService(store, options, runner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), TimeSpan.FromMilliseconds(50));

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current Godot smoke failure.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        refreshed!.Goals.Single(goal => goal.GoalIndex == 1).Status.Should().Be("succeeded");
        run!.Status.Should().Be("completed");
        run.ExitCode.Should().Be(0);
        run.EvidenceJson.Should().Contain("prototype_quick_fix_timeout_validated_after_cancel");
        runner.Commands.Should().Contain(command => command.Arguments.Contains("exec"));
        runner.Commands.Should().Contain(command => command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"));
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPersistGodotFailure_WhenTimedOutRepairStillFailsSmoke()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair map entry smoke validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Godot navigation smoke failed.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new TimedOutSmokeFailingGoalRepairRunner();
        var service = new PrototypeQuickFixService(store, options, runner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), TimeSpan.FromMilliseconds(50));

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current Godot smoke failure.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("failed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("prototype_main_menu_navigation_failed");
        refreshed!.Goals.Single(goal => goal.GoalIndex == 1).Status.Should().Be("needs_fix");
        run!.Status.Should().Be("failed");
        run.ExitCode.Should().Be(408);
        run.EvidenceJson.Should().Contain("prototype_quick_fix_timeout_validation_failed_after_cancel");
        run.EvidenceJson.Should().Contain("\"acceptance_validation_status\":\"passed\"");
        run.EvidenceJson.Should().Contain("\"post_acceptance_validation_status\":\"failed\"");
        run.EvidenceJson.Should().Contain("prototype_main_menu_navigation_failed");
        runner.Commands.Should().Contain(command => command.Arguments.Contains("exec"));
        runner.Commands.Should().Contain(command => command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"));
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPromoteStepOne_WhenRpgGdUnitHasOnlyBehaviorAssertionFailures()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var details = await CreateRpgGdUnitRepairSessionAsync(store, accountId, projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "GdUnit asset/import step needs repair.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new GoalRepairStepOneBehaviorGdUnitFailRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        run!.EvidenceJson.Should().Contain("\"rpg_gdunit_validation\"");
        run.EvidenceJson.Should().Contain("\"passed\":false");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepStepOneNeedsFix_WhenRpgGdUnitHasInfrastructureFailures()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var details = await CreateRpgGdUnitRepairSessionAsync(store, accountId, projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "GdUnit asset/import step needs repair.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new GoalRepairStepOneInfrastructureGdUnitFailRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("RPG GdUnit validation");
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
            accountId,
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
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new GoalRepairSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
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
        var planningAnalysis = ReadPlanningAnalysis(project!.MetaPath);
        var loopFields = planningAnalysis.GetProperty("fieldCoverage").EnumerateArray().ToArray();
        loopFields.Should().Contain(field =>
            field.GetProperty("field").GetString() == "minimum_playable_loop" &&
            field.GetProperty("status").GetString() == "completed");
        loopFields.Should().Contain(field =>
            field.GetProperty("field").GetString() == "core_gameplay_loop" &&
            field.GetProperty("status").GetString() == "completed");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldContinueToCodex_WhenPreflightGodotSmokeFails()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair map entry smoke validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Godot navigation smoke failed.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new QuickFixNavigationFailHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current Godot smoke failure.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/smoke_headless.py", StringComparison.Ordinal)));
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/prototype_main_menu_navigation_smoke.py", StringComparison.Ordinal)));
        var codexCommand = runner.Commands.Single(command => command.Arguments.Contains("exec"));
        codexCommand.StandardInput.Should().Contain("Latest Godot smoke validation failed after platform static acceptance");
        codexCommand.StandardInput.Should().Contain("prototype_main_menu_navigation_failed");
        run!.EvidenceJson.Should().NotContain("\"preflight\":true");
        run.EvidenceJson.Should().Contain("\"godot_smoke_validation\"");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldContinueToCodex_WhenPreflightGodotSmokeTimesOut()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Repair map entry smoke validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Godot navigation smoke timed out.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new QuickFixGodotSmokeTimeoutHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current Godot smoke timeout.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "scripts/python/smoke_headless.py", StringComparison.Ordinal)));
        runner.Commands.Should().Contain(command => command.Arguments.Any(arg => string.Equals(arg, "exec", StringComparison.Ordinal)));
        var codexCommand = runner.Commands.Single(command => command.Arguments.Contains("exec"));
        codexCommand.StandardInput.Should().Contain("godot_smoke_validation_timeout");
        run!.EvidenceJson.Should().Contain("prototype_main_menu_navigation_failed");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepStepOneNeedsFix_WhenMapEntryContractIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG map entry step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "missing_rpg_map_entry_contract", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        refreshed!.Goals.Single(goal => goal.GoalIndex == 1).Status.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("missing_rpg_");
        runner.LastPrompt.Should().Contain("Platform hard acceptance for RPG Step 1");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/dq-rpg/MapScene.tscn");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs");
        runner.LastPrompt.Should().Contain("RpgPlayerAsset");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldReturnSpecificStepOneContractGaps()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project.RepoPath);
        RemoveStepOneMapSizeAndPlayerVisibilityContract(project.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG map entry step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 1);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "missing_rpg_map_entry_contract", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "Goal 1 needs fix");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 1, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("map_scene_missing_600x600_custom_minimum_size");
        result.AssistantMessage.Should().Contain("map_script_missing_player_visibility_restore");
        run!.EvidenceJson.Should().Contain("map_scene_missing_600x600_custom_minimum_size");
        run.EvidenceJson.Should().Contain("map_script_missing_player_visibility_restore");
        runner.LastPrompt.Should().Contain("Current platform acceptance diagnosis before repair");
        runner.LastPrompt.Should().Contain("map_scene_missing_600x600_custom_minimum_size");
        runner.LastPrompt.Should().Contain("map_script_missing_player_visibility_restore");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldRequireDedicatedBattleScene_ForStepTwo()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG battle scene step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 2);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "missing_rpg_battle_scene_contract", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 2, "Goal 2 needs fix");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 2, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("missing_rpg_battle_scene_contract");
        runner.LastPrompt.Should().Contain("Platform hard acceptance for RPG Step 2");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/dq-rpg/BattleScene.tscn");
        runner.LastPrompt.Should().Contain("Game.Godot/Prototypes/dq-rpg/Scripts/BattleScene.cs");
        runner.LastPrompt.Should().Contain("RpgEnemyAsset");
        runner.LastPrompt.Should().Contain("ResolveBattle/ResolveAttackTurn");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepStepTwoTimeoutFocusedOnBattleScene()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG battle scene step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 2);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "missing_rpg_battle_scene_contract", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 2, "Goal 2 needs fix");
        var service = new PrototypeQuickFixService(store, options, new ImmediateCanceledHostedProcessRunner());

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 2, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);
        var summary = refreshed!.Goals.Single(goal => goal.GoalIndex == 2).ResultSummary;

        result.Status.Should().Be("failed");
        summary.Should().Contain("独立 BattleScene 场景与脚本");
        summary.Should().Contain("不要推进奖励选择");
        summary.Should().NotContain("胜利后显示 3 个奖励");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldInjectRewardContract_ForStepThree()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG reward loop step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 3);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "reward values are wrong", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 3, "Goal 3 needs fix");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 3, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.IterationGoalStatus.Should().Be("needs_fix");
        runner.LastPrompt.Should().Contain("Platform hard acceptance for RPG Step 3");
        runner.LastPrompt.Should().Contain("统一 smoke");
        runner.LastPrompt.Should().Contain("+5 HP");
        runner.LastPrompt.Should().Contain("+2 ATK");
        runner.LastPrompt.Should().Contain("+1 DEF");
        runner.LastPrompt.Should().Contain("StartingPlayerHp + 5");
        runner.LastPrompt.Should().Contain("ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldAcceptBattleSceneOwnedRewardFlow_ForStepThree()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG reward loop step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 3);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need reward loop verification.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 3, "Goal 3 needs fix");

        var scriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts");
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), """
public sealed class DqRpgPrototype
{
    private BattleScene _battleScene = new();
    private MapScene _mapScene = new();
    private DqRpgPrototypeLoop _loop = new();
    private dynamic _state;

    public void Ready()
    {
        _battleScene.RewardSelected += ApplyRewardSelection;
    }

    private void OnBattleFinished(dynamic result)
    {
        if (result.RewardOptions.Count > 0)
        {
            _battleScene.ApplyState(result.NextState);
            return;
        }

        RefreshView();
    }

    private void ApplyRewardSelection(int rewardIndex)
    {
        _state = _loop.ApplyReward(_state, rewardIndex, fromChest: false);
        _mapScene.ResumeAfterReward();
        _mapScene.ShowRewardReturnStatus("Battle reward selected. Return to the map.");
        RefreshView();
    }

    private void RefreshView() { }
}
""");
        File.WriteAllText(Path.Combine(scriptPath, "MapScene.cs"), """
public sealed class MapScene
{
    private dynamic _player;
    public void ResumeAfterReward() { _player.Visible = true; }
    public void ShowRewardReturnStatus(string status) { _player.Visible = true; }
}
""");
        File.WriteAllText(Path.Combine(scriptPath, "BattleScene.cs"), """
public sealed class BattleScene
{
    public event System.Action<int>? RewardSelected;
    private dynamic RewardOptionOneButton;
    private dynamic RewardOptionTwoButton;
    private dynamic RewardOptionThreeButton;

    public void ApplyState(dynamic state)
    {
        var rewardVisible = state.RewardOptions.Count == 3;
        if (state.RewardOptions.Count != 3)
        {
            return;
        }

        ConfigureRewardButton(RewardOptionOneButton, state.RewardOptions[0]);
        ConfigureRewardButton(RewardOptionTwoButton, state.RewardOptions[1]);
        ConfigureRewardButton(RewardOptionThreeButton, state.RewardOptions[2]);
    }

    private void ConfigureRewardButton(dynamic button, dynamic reward) { }
    private void SelectFirstReward() => RewardSelected?.Invoke(0);
}
""");

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 3, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.IterationSessionStatus.Should().Be("paused_for_review");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldAcceptShellOwnedRewardPanelReturningThroughMapApplyState_ForStepThree()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG reward loop step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 3);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need reward loop verification.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 3, "Goal 3 needs fix");

        var scriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts");
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), """
public sealed class DqRpgPrototype
{
    private MapScene _mapScene = new();
    private BattleScene _battleScene = new();
    private DqRpgPrototypeLoop _loop = new();
    private dynamic _state;
    private dynamic _rewardPanel;
    private dynamic[] _rewardButtons = [];

    private void OnBattleFinished(bool victory)
    {
        var rewards = _state.RewardOptions.Count > 0
            ? _state.RewardOptions
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
        _rewardPanel.Visible = true;
        _rewardButtons[0].Text = "+5 HP fully restores to the new max HP";
        _rewardButtons[1].Text = "+2 ATK increases damage";
        _rewardButtons[2].Text = "+1 DEF reduces damage taken";
    }

    private void SelectReward(int rewardIndex)
    {
        _state = _loop.ApplyReward(_state, rewardIndex, fromChest: false);
        _rewardPanel.Visible = false;
        _mapScene.ApplyState("Battle reward selected. HP 105/105, ATK 10, DEF 2. Return to the map.");
        RefreshView();
    }

    private void RefreshView() { }
}
""");
        File.WriteAllText(Path.Combine(scriptPath, "MapScene.cs"), """
public sealed class MapScene
{
    private dynamic _playerAsset;
    public void ApplyState(string rewardReturnStatus) { _playerAsset.Visible = true; }
}
""");

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 3, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.IterationSessionStatus.Should().Be("paused_for_review");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldShowValidatedSummary_WhenCodexReportsStaleGodotNeedsFix()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            },
            godot_smoke = new
            {
                scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Create the RPG reward loop step."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 3);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need reward loop verification.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 3, "Goal 3 needs fix");

        var scriptPath = Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts");
        File.WriteAllText(Path.Combine(scriptPath, "DqRpgPrototype.cs"), """
public sealed class DqRpgPrototype
{
    private MapScene _mapScene = new();
    private BattleScene _battleScene = new();
    private DqRpgPrototypeLoop _loop = new();
    private dynamic _state;
    private dynamic _rewardPanel;
    private dynamic[] _rewardButtons = [];

    private void OnBattleFinished(bool victory)
    {
        var rewards = _state.RewardOptions.Count > 0
            ? _state.RewardOptions
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
        _rewardPanel.Visible = true;
        _rewardButtons[0].Text = "+5 HP fully restores to the new max HP";
        _rewardButtons[1].Text = "+2 ATK increases damage";
        _rewardButtons[2].Text = "+1 DEF reduces damage taken";
    }

    private void SelectReward(int rewardIndex)
    {
        _state = _loop.ApplyReward(_state, rewardIndex, fromChest: false);
        _rewardPanel.Visible = false;
        _mapScene.ApplyState("Battle reward selected. HP 105/105, ATK 10, DEF 2. Return to the map.");
        RefreshView();
    }

    private void RefreshView() { }
}
""");
        File.WriteAllText(Path.Combine(scriptPath, "MapScene.cs"), """
public sealed class MapScene
{
    private dynamic _playerAsset;
    public void ApplyState(string rewardReturnStatus) { _playerAsset.Visible = true; }
}
""");

        var runner = new GoalRepairStaleGodotNeedsFixButSmokePassRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 3, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.AssistantMessage.Should().Contain("目标 3 修复已完成");
        result.AssistantMessage.Should().Contain("passed Godot smoke validation");
        result.AssistantMessage.Should().NotContain("STATUS: needs_fix");
        result.AssistantMessage.Should().NotContain("Failed to open 'user://logs");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldRunGodotSmoke_ForStepFiveRewardLoop()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG reward loop to a clean return-to-map validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 5);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need engine verification for reward loop.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 5, "Goal 5 needs fix");

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

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 5, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.AssistantMessage.Should().Contain("Godot");
        var smokeCommand = runner.Commands.Single(command => command.Arguments.Contains("scripts/python/smoke_headless.py"));
        smokeCommand.Environment["GODOT_BIN"].Should().Be(@"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        smokeCommand.Environment["UseSharedCompilation"].Should().Be("false");
        smokeCommand.Environment["MSBUILDDISABLENODEREUSE"].Should().Be("1");
        smokeCommand.Environment["TEMP"].Should().Contain("phase-a-validation-temp");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldAcceptStepFiveRewardEntryMethodSignature()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG reward loop to a clean return-to-map validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 5);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need reward loop verification.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 5, "Goal 5 needs fix");

        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        File.WriteAllText(
            Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "DqRpgPrototype.cs"),
            """
public sealed class DqRpgPrototype
{
    void ShowMapScene() { }
    public void ShowRewardScene(System.Collections.Generic.IReadOnlyList<object> rewards)
    {
        if (rewards is null || rewards.Count <= 0) { ShowMapScene(); return; }
        ShowRewardReturnStatus();
    }
    public void ShowRewardReturnStatus() { ShowMapScene(); }
}
""");

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 5, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
        result.AssistantMessage.Should().Contain("Godot");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepStepFiveNeedsFix_WhenRewardContractIsMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG reward loop to a clean return-to-map validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Single(goal => goal.GoalIndex == 5);
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need reward loop verification.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 5, "Goal 5 needs fix");

        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        File.WriteAllText(
            Path.Combine(project.RepoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "MapScene.cs"),
            "public sealed class MapScene { dynamic _player; void ResetMap() { _player.Visible = true; } }\n");

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, 5, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        run!.EvidenceJson.Should().Contain("acceptance_validation_status");
        run.EvidenceJson.Should().Contain("\"failed\"");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepFinalStepNeedsFix_WhenMainSceneHostUiIsVisible()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: false);

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        run!.EvidenceJson.Should().Contain("main_scene_default_ui_not_hidden");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldReportGdignore_WhenFinalRpgAssetsAreBlocked()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        File.WriteAllText(Path.Combine(project.RepoPath, "Game.Godot", ".gdignore"), "");

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        run!.EvidenceJson.Should().Contain("game_godot_gdignore_blocks_rpg_assets");
        result.AssistantMessage.Should().Contain("game_godot_gdignore_blocks_rpg_assets");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldPassFinalStep_WhenMainSceneHostUiDefaultsHidden()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateWriter = new PrototypeRouteStateWriter();
        stateWriter.WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("succeeded");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldKeepFinalStepNeedsFix_WhenRpgGdUnitFails()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        new PrototypeRouteStateWriter().WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));
        SeedLatestRpgGdUnitFailureReport(project.RepoPath);

        var runner = new GoalRepairFinalGdUnitFailRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        result.Status.Should().Be("completed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.AssistantMessage.Should().Contain("RPG GdUnit validation");
        result.AssistantMessage.Should().Contain("GDUNIT_FAILURES");
        result.AssistantMessage.Should().Contain("Read the three reward cards");
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);
        refreshed!.Goals.Last().Status.Should().Be("needs_fix");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldIncludeLatestRpgGdUnitFailuresInFinalRepairPrompt()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        new PrototypeRouteStateWriter().WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));
        SeedLatestRpgGdUnitFailureReport(project.RepoPath);

        var runner = new GoalRepairFinalGdUnitFailRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        _ = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        runner.LastPrompt.Should().Contain("Latest RPG GdUnit validation context");
        runner.LastPrompt.Should().Contain("\"failures\":27");
        runner.LastPrompt.Should().Contain("Encounter ready");
        runner.LastPrompt.Should().Contain("Read the three reward cards");
        runner.LastPrompt.Should().Contain("BattleScene finished");
    }

    [Fact]
    public async Task SubmitAsync_GoalRepair_ShouldUseLocalDateForRpgGdUnitReportDir()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path, @"C:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe");
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, prototypeSucceeded: true);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Bring the RPG final acceptance to a clean full playable validation."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        var targetGoal = details!.Goals.Last();
        await store.UpdateProjectIterationGoalStatusAsync(targetGoal.GoalId, "needs_fix", "Need final validation.", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", targetGoal.GoalIndex, "Goal final needs fix");

        var project = await store.GetProjectSnapshotAsync(projectId);
        new PrototypeRouteStateWriter().WritePrototypeState(project!, new
        {
            route = "prototype-7day-playable",
            prototype_completion = new
            {
                smoke_scene = @"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"
            }
        });
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        EnsureRpgAcceptanceMarkers(project.RepoPath);
        EnsureRpgPrototypeContractValues(project.MetaPath);
        WriteMainScene(project.RepoPath, hidePrototypeHostUi: true);
        Directory.CreateDirectory(Path.Combine(project.RepoPath, "Tests.Godot", "tests", "Prototype", "DqRpgPrototype"));

        var runner = new GoalRepairStep5HostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);
        var localDateBefore = DateTimeOffset.Now.ToString("yyyy-MM-dd");

        _ = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "Repair current goal.",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, targetGoal.GoalId, targetGoal.GoalIndex, targetGoal.Title, targetGoal.Description, targetGoal.AcceptanceHint, targetGoal.ResultSummary)));

        var localDateAfter = DateTimeOffset.Now.ToString("yyyy-MM-dd");
        var gdUnitCommand = runner.Commands.Single(command => command.Arguments.Contains("scripts/python/run_gdunit.py"));
        gdUnitCommand.Arguments.Should().Contain("--prewarm");
        var reportDir = gdUnitCommand.Arguments.SkipWhile(arg => arg != "--rd").Skip(1).First();
        reportDir.Should().BeOneOf(
            $"logs/e2e/{localDateBefore}/gdunit-dq-rpg-prototype",
            $"logs/e2e/{localDateAfter}/gdunit-dq-rpg-prototype");
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
        var project = await store.GetProjectSnapshotAsync(projectId);
        EnsureRpgAcceptanceMarkers(project!.RepoPath);
        EnsureRpgSmokeSceneFile(project!.RepoPath);
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Stabilize map movement and first encounter trigger."));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "still blocked", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "goal 1 needs fix");
        var runner = new StructuredCompletedHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
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
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new GoalRepairNeedsFixHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
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
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new StructuredCompletedButMissingGameplayVerificationHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
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
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new ImmediateCanceledHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner, new ProjectWorkspaceSeeder(options), new SkillActionCatalog(), TimeSpan.FromMilliseconds(50));

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
            "修复当前目标",
            "gpt-5.4",
            "normal",
            new PrototypeGoalRepairContext(details.Session.SessionId, details.Goals[0].GoalId, 1, details.Goals[0].Title, details.Goals[0].Description, details.Goals[0].AcceptanceHint, details.Goals[0].ResultSummary)));
        var refreshed = await store.GetLatestProjectIterationSessionAsync(projectId);

        result.Status.Should().Be("failed");
        result.IterationGoalStatus.Should().Be("needs_fix");
        result.IterationSessionStatus.Should().Be("needs_fix");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.StderrText.Should().Contain("720 second timeout");
        refreshed!.Goals[0].Status.Should().Be("needs_fix");
        refreshed.Goals[0].ResultSummary.Should().Contain("修复超时");
        refreshed.Goals[0].ResultSummary.Should().Contain("Start Adventure");
        refreshed.Goals[0].ResultSummary.Should().Contain("MapScene");
        refreshed.Session.Status.Should().Be("needs_fix");
        refreshed.Session.LatestSummary.Should().Contain("修复超时");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var planningAnalysis = ReadPlanningAnalysis(project!.MetaPath);
        var loopFields = planningAnalysis.GetProperty("fieldCoverage").EnumerateArray().ToArray();
        loopFields.Should().Contain(field =>
            field.GetProperty("field").GetString() == "minimum_playable_loop" &&
            field.GetProperty("status").GetString() == "partial");
        loopFields.Should().Contain(field =>
            field.GetProperty("field").GetString() == "core_gameplay_loop" &&
            field.GetProperty("status").GetString() == "partial");
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
        var planService = TestRpgIterationPlanServiceFactory.Create(store);
        await planService.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("先让玩家能稳定移动并明确触发第一次遇敌，再继续后续目标。"));
        var details = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(details!.Goals[0].GoalId, "needs_fix", "当前 step 还没可继续。", null);
        await store.UpdateProjectIterationSessionStatusAsync(details.Session.SessionId, "needs_fix", 1, "目标 1 需要修复。");
        var runner = new OffTopicSuccessHostedProcessRunner();
        var service = new PrototypeQuickFixService(store, options, runner);

        var result = await service.SubmitAsync(accountId, projectId, new PrototypeFeedbackRequest(
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
        runner.LastPrompt.Should().Contain("这是目标级 needs-fix 修复，不是 90 秒快速修复");
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

    private static async Task<ProjectIterationSessionDetails> CreateRpgGdUnitRepairSessionAsync(
        PhaseAMetadataStore store,
        string accountId,
        string projectId)
    {
        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "prototype-repair-plan",
            "Repair RPG GdUnit validation failure.",
            "Repair RPG project-specific GdUnit validation.",
            [
                new ProjectIterationGoalCreateCommand(
                    1,
                    "Repair RPG runtime assets and Godot imports for GdUnit",
                    "Fix missing runtime assets, scene ext_resource paths, and Godot import visibility before broad gameplay redesign.",
                    "This step passes only when the active dq-rpg scenes no longer reference missing PNG or .ctex resources and GdUnit can load MapScene.tscn and BattleScene.tscn without ext_resource parse errors."),
                new ProjectIterationGoalCreateCommand(
                    2,
                    "Repair RPG scene node contract for GdUnit",
                    "Fix node paths required by the project-specific GdUnit suite.",
                    "This step passes only when the node paths required by the project-specific GdUnit suite exist or tests and scripts are updated together."),
                new ProjectIterationGoalCreateCommand(
                    3,
                    "Rerun RPG project-specific GdUnit and final prototype acceptance",
                    "Run final acceptance across the full playable RPG prototype.",
                    "Final RPG GdUnit and prototype acceptance pass.")
            ]);
        return (await store.GetLatestProjectIterationSessionAsync(projectId))!;
    }

    private static void SeedLatestRpgGdUnitFailureReport(string repoPath)
    {
        var reportDir = Path.Combine(repoPath, "logs", "e2e", "2099-01-01", "gdunit-dq-rpg-prototype");
        Directory.CreateDirectory(reportDir);
        WriteRpgGdUnitFailureReport(reportDir);
    }

    private static void SeedRpgGdUnitFailureReportForCommand(HostedProcessCommand command)
    {
        var relativeReportDir = command.Arguments.SkipWhile(arg => arg != "--rd").Skip(1).FirstOrDefault();
        if (string.IsNullOrWhiteSpace(relativeReportDir))
        {
            return;
        }

        var reportDir = Path.Combine(command.WorkingDirectory, relativeReportDir.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(reportDir);
        WriteRpgGdUnitFailureReport(reportDir);
    }

    private static void WriteRpgGdUnitFailureReport(string reportDir)
    {
        File.WriteAllText(Path.Combine(reportDir, "run-summary.json"), """
{"rc":100,"normalized_rc":100,"strict_exit_code":false,"results":{"tests":6,"failures":27,"errors":0},"prewarm_rc":0,"prewarm_attempts":1}
""");
        File.WriteAllText(Path.Combine(reportDir, "gdunit-console.txt"), """
res://tests/Prototype/DqRpgPrototype/test_dq_rpg_prototype_scene.gd > test_map_scene_moves_player_and_reaches_first_encounter_with_traversal FAILED
Report:
  Expecting:
  'Position (9, 1)  Encounter chance 80%'
  do contains
  'Encounter ready'
res://tests/Prototype/DqRpgPrototype/test_dq_rpg_prototype_scene.gd > test_full_first_loop_proves_scene_switching_from_start_to_reward_and_back FAILED
Report:
  Expecting:
  'Use WASD to move. Watch encounter chance and step progress in the map panel until battle triggers.'
  do contains
  'Read the three reward cards'
Report:
  Expecting:
  '- Adventure started.'
  do contains
  'BattleScene finished'
Statistics: 6 test cases | 0 errors | 27 failures | 0 flaky | 0 skipped | 0 orphans |
Exit code: 100
""");
    }

    private static JsonElement ReadPlanningAnalysis(string metaPath)
    {
        var path = Path.Combine(metaPath, "routes", "iteration-plan", "latest.json");
        using var document = JsonDocument.Parse(File.ReadAllText(path));
        return document.RootElement.GetProperty("planning_analysis").Clone();
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
    public const int StartingHp = 30;
    public const int StartingAtk = 10;
    public const int StartingDef = 2;
    public const int RewardHpBonus = 5;
    public const int RewardAtkBonus = 2;
    public const int RewardDefBonus = 1;
    public const int VictoryTargetBattles = 15;
    public const int RewardHealPercent = 10;
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

    private static void EnsureRpgPrototypeContractValues(string metaPath)
    {
        var contractDir = Path.Combine(metaPath, "routes", "prototype-contract");
        Directory.CreateDirectory(contractDir);
        var payload = new
        {
            form_fields = new
            {
                success_criteria = new[]
                {
                    "Player starts with 30 HP, 10 ATK, 2 DEF.",
                    "Rewards can add 5 HP, 2 ATK, or 1 DEF.",
                    "Win after 15 battles.",
                    "Heal reward restores 10% HP."
                }
            }
        };
        File.WriteAllText(
            Path.Combine(contractDir, "latest.json"),
            JsonSerializer.Serialize(payload),
            System.Text.Encoding.UTF8);
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
        WriteMainScene(repoPath, hidePrototypeHostUi: true);
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

    private static void RemoveStepOneMapSizeAndPlayerVisibilityContract(string repoPath)
    {
        var mapScene = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "MapScene.tscn");
        var sceneText = File.ReadAllText(mapScene);
        sceneText = sceneText
            .Replace("custom_minimum_size = Vector2(700, 700)\n", "", StringComparison.Ordinal)
            .Replace("custom_minimum_size = Vector2(600, 600)\n", "", StringComparison.Ordinal);
        File.WriteAllText(mapScene, sceneText);

        var mapScript = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "MapScene.cs");
        var scriptText = File.ReadAllText(mapScript);
        scriptText = scriptText
            .Replace("ShowRewardReturnStatus() { _player.Visible = true; } dynamic _player;", "ShowRewardReturnStatus() { }", StringComparison.Ordinal);
        File.WriteAllText(mapScript, scriptText);
    }

    private static void WriteMainScene(string repoPath, bool hidePrototypeHostUi)
    {
        var mainScenePath = Path.Combine(repoPath, "Game.Godot", "Scenes");
        Directory.CreateDirectory(mainScenePath);
        var visibility = hidePrototypeHostUi ? "visible = false\n" : "";
        File.WriteAllText(Path.Combine(mainScenePath, "Main.tscn"), $$"""
[gd_scene format=3]

[node name="Main" type="Control"]

[node name="ScreenRoot" type="Control" parent="."]
{{visibility}}layout_mode = 3

[node name="Overlays" type="Control" parent="."]
{{visibility}}layout_mode = 3

[node name="VBox" type="VBoxContainer" parent="."]
{{visibility}}layout_mode = 2
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
            File.WriteAllText(outputPath, "Quick fix applied.");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", ""));
        }
    }

    private sealed class QuickFixNavigationFailHostedProcessRunner : IHostedProcessRunner
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
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (prototype scene alive)", ""));
            }

            if (command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(14, "", "MAIN_MENU_PROTOTYPE_NAV FAIL\nERROR: rpg_map_visible_markers_missing_after_start"));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Quick fix attempted.
CHANGED: Updated prototype start routing.
VERIFY: Re-run platform validation.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", ""));
        }
    }

    private sealed class QuickFixGodotSmokeTimeoutHostedProcessRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];
        private bool _codexStarted;

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (command.Arguments.Contains("scripts/python/smoke_headless.py"))
            {
                if (!_codexStarted)
                {
                    throw new OperationCanceledException(cancellationToken);
                }

                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (prototype scene alive)", ""));
            }

            if (command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(14, "", "MAIN_MENU_PROTOTYPE_NAV FAIL\nERROR: rpg_map_visible_markers_missing_after_start"));
            }

            _codexStarted = true;
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: Godot smoke still needs repair.
CHANGED: Recorded the timeout condition.
VERIFY: Godot smoke timed out before runtime proof.
REMAINING: Continue fixing the current Godot smoke timeout.
""");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", ""));
        }
    }

    private sealed class GoalRepairSuccessHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

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

            if (command.Arguments.Contains("scripts/python/run_gdunit.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "GDUNIT_DONE rc=0", ""));
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

    private sealed class GoalRepairStepOneBehaviorGdUnitFailRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
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

            if (command.Arguments.Contains("scripts/python/run_gdunit.py"))
            {
                return Task.FromResult(new HostedProcessResult(100, """
                    Expecting:
                     'Use WASD to explore the map.' do contains 'Read the three reward cards'
                    Statistics: 6 test cases | 0 errors | 27 failures
                    Exit code: 100
                    """, ""));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Goal 1 asset/import repair is complete.
CHANGED: Fixed resource import setup for the RPG test project.
VERIFY: Platform acceptance validation passed for the current gameplay goal.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class GoalRepairStepOneInfrastructureGdUnitFailRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
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

            if (command.Arguments.Contains("scripts/python/run_gdunit.py"))
            {
                return Task.FromResult(new HostedProcessResult(1, """
                    ERROR: Failed loading resource: res://Game.Godot/Prototypes/dq-rpg/Assets/Map/showcase_map_overworld.png.
                    ERROR: res://Game.Godot/Prototypes/dq-rpg/MapScene.tscn Parse Error: [ext_resource] referenced non-existent resource.
                    ERROR: Node not found: Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer.
                    GDUNIT_DONE rc=1
                    """, ""));
            }

            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Goal 1 asset/import repair attempted.
CHANGED: Updated resource import setup for the RPG test project.
VERIFY: Platform acceptance validation passed for the current gameplay goal.
REMAINING: none
""");
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class GoalRepairFinalGdUnitFailRunner : IHostedProcessRunner
    {
        public string LastPrompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
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

            if (command.Arguments.Contains("scripts/python/run_gdunit.py"))
            {
                SeedRpgGdUnitFailureReportForCommand(command);
                return Task.FromResult(new HostedProcessResult(0, "GDUNIT_DONE rc=1", ""));
            }

            LastPrompt = command.StandardInput ?? "";
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
            STATUS: completed
            SUMMARY: Final RPG repair attempted.
            CHANGED: Updated final RPG validation target.
            VERIFY: Platform acceptance validation passed for the current gameplay goal.
            REMAINING: none
            """);
            return Task.FromResult(new HostedProcessResult(0, "goal repair stdout", ""));
        }
    }

    private sealed class GoalRepairStaleGodotNeedsFixButSmokePassRunner : IHostedProcessRunner
    {
        private bool _codexStarted;

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (command.Arguments.Contains("scripts/python/smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (prototype scene alive)", ""));
            }

            if (command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"))
            {
                return _codexStarted
                    ? Task.FromResult(new HostedProcessResult(0, "MAIN_MENU_PROTOTYPE_NAV PASS scene=res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", ""))
                    : Task.FromResult(new HostedProcessResult(14, "", "MAIN_MENU_PROTOTYPE_NAV FAIL\nERROR: stale focus warning before repair"));
            }

            _codexStarted = true;
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: needs_fix
SUMMARY: Godot smoke still needs repair.
CHANGED: Fixed the focus mode issue.
VERIFY: Godot crashed before runtime proof.
REMAINING: Current step still needs repair because Godot failed to open 'user://logs/godot.log'.
""");
            return Task.FromResult(new HostedProcessResult(0, "quick fix stdout", "ERROR: Failed to open 'user://logs/godot.log'."));
        }
    }

    private sealed class StructuredCompletedHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

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

    private sealed class TimedOutValidatedGoalRepairRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];
        private bool _codexStarted;

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (command.Arguments.Contains("scripts/python/smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (prototype scene alive)", ""));
            }

            if (command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"))
            {
                if (!_codexStarted)
                {
                    return Task.FromResult(new HostedProcessResult(14, "", "MAIN_MENU_PROTOTYPE_NAV FAIL\nERROR: missing map asset before repair"));
                }

                return Task.FromResult(new HostedProcessResult(0, "MAIN_MENU_PROTOTYPE_NAV PASS scene=res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", ""));
            }

            _codexStarted = true;
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Map navigation is repaired.
CHANGED: Updated RPG map entry wiring.
            VERIFY: Godot gameplay verification passed for map movement and first encounter trigger.
REMAINING: none
""");
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class TimedOutSmokeFailingGoalRepairRunner : IHostedProcessRunner
    {
        public List<HostedProcessCommand> Commands { get; } = [];
        private bool _codexStarted;

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            Commands.Add(command);
            if (command.FileName == "dotnet")
            {
                return Task.FromResult(new HostedProcessResult(0, command.Arguments.Contains("build") ? "dotnet build ok" : "dotnet test ok", ""));
            }

            if (command.Arguments.Contains("scripts/python/smoke_headless.py"))
            {
                return Task.FromResult(new HostedProcessResult(0, "SMOKE PASS (prototype scene alive)", ""));
            }

            if (command.Arguments.Contains("scripts/python/prototype_main_menu_navigation_smoke.py"))
            {
                return Task.FromResult(new HostedProcessResult(14, "", _codexStarted
                    ? "MAIN_MENU_PROTOTYPE_NAV FAIL\nERROR: rpg_map_visible_markers_missing_after_timeout"
                    : "MAIN_MENU_PROTOTYPE_NAV FAIL\nERROR: missing map asset before repair"));
            }

            _codexStarted = true;
            var outputPath = command.Arguments.SkipWhile(arg => arg != "-o").Skip(1).First();
            Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
            File.WriteAllText(outputPath, """
STATUS: completed
SUMMARY: Map navigation repair was attempted.
CHANGED: Updated RPG map entry wiring.
VERIFY: Godot gameplay verification was attempted.
REMAINING: none
""");
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class ImmediateCanceledHostedProcessRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            throw new OperationCanceledException(cancellationToken);
        }
    }

    private sealed class OffTopicSuccessHostedProcessRunner : IHostedProcessRunner
    {
        public string LastPrompt { get; private set; } = "";

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            LastPrompt = command.StandardInput ?? "";
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
