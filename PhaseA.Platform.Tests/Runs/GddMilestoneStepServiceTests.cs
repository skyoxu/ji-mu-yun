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
        File.Exists(Path.Combine(project.RepoPath, "docs", "prototype-v1-plan.md")).Should().BeTrue();
        File.Exists(Path.Combine(project.RepoPath, result.Steps[0].SpecRelativePath!.Replace('/', Path.DirectorySeparatorChar))).Should().BeTrue();
        result.Steps[0].SpecRelativePath.Should().StartWith("docs/m1-");
        File.ReadAllText(Path.Combine(project.MetaPath, "routes", "gdd-milestones", "latest.json"))
            .Should().Contain("phase-a.gdd-milestone-steps.v2");
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
        result.Summary.Should().Contain("M1 已通过原型骨架创建完成");
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
        var adjustedSpec = File.ReadAllText(Path.Combine(project.RepoPath, next.SpecRelativePath!.Replace('/', Path.DirectorySeparatorChar)));
        adjustedSpec.Should().Contain("Only adjust the first wave tempo");
        adjustedSpec.Should().Contain("Player can validate a slower first wave");
        adjustedSpec.Should().Contain("Tune the wave spawner");
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
        result!.Plan!.Steps.Single(step => step.StepId == "M1").Status.Should().Be("feedback_submitted");
        result.Plan.Steps.Single(step => step.StepId == "M1").CanConfirm.Should().BeTrue();
        result.Plan.Summary.Should().Contain("轻量验收已通过");
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
        result.Plan.Summary.Should().Contain("轻量验收自动修复后仍未通过");
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
        var service = Service(store, options, runnerOutput: runnerOutput);

        var result = await service.ExecuteCurrentStepAsync(accountId, projectId);

        result.Should().NotBeNull();
        result!.StepExecution.Should().NotBeNull();
        result.StepExecution!.Status.Should().Be("needs_fix");
        result.StepExecution.SessionStatus.Should().Be("needs_fix");
        result.Plan!.Steps.Single(step => step.StepId == "M1").Status.Should().Be("executed");
        result.Plan.Steps.Single(step => step.StepId == "M1").CanConfirm.Should().BeTrue();
        result.Plan.Summary.Should().Contain("可以直接确认完成");
        var run = await store.GetRunSnapshotAsync(result.StepExecution.RunId);
        run!.ProgressStep.Should().Be("completed");
        run.ProgressLabel.Should().Contain("M1 已执行完成");
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
        result.Plan.Summary.Should().Contain("轻量验收已通过");
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
        result.Plan.Summary.Should().Contain("提交反馈并修正模块");
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

    private static GddMilestoneStepService Service(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        ILlmRouteEngine? llmRouteEngine = null,
        string runnerOutput = """
        STATUS: completed
        VERIFY: Current module repair passed static check for the current milestone goal.
        REMAINING: none
        """,
        IPrototypeLightweightValidationService? validationService = null)
    {
        var runner = new FakeHostedProcessRunner(runnerOutput);
        return new GddMilestoneStepService(
            store,
            new PrototypeIterationGoalService(store, options, runner, new ProjectWorkspaceSeeder(options), new PrototypeRouteStateWriter()),
            new PrototypeNeedsFixRouteService(store, new PrototypeQuickFixService(store, options, runner), new PrototypeRouteStateWriter()),
            llmRouteEngine,
            validationService);
    }

    private static PrototypeWorkflowResult ValidationResult(string runId, string status, int exitCode, string stdout = "", string stderr = "")
    {
        return new PrototypeWorkflowResult(runId, status, exitCode, "docs/prototypes/demo.md", stdout, stderr, [], []);
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

    private static void SeedPrototypeBaseline(ProjectSnapshot project)
    {
        new PrototypeRouteStateWriter().WritePrototypeState(project, new
        {
            route = "prototype-7day-playable",
            marker = "prototype-baseline",
            prototype_completion = new
            {
                succeeded = true,
                smoke_scene = "res://Game.Godot/Prototypes/demo/DemoPrototype.tscn"
            }
        });
        WriteText(project.RepoPath, ".agents/skills/prototype-7day-playable-godot-zh/SKILL.md", "# skill\n");
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

    private static void WriteText(string repoPath, string relativePath, string text)
    {
        var path = Path.Combine(repoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, text);
    }

    private sealed class FakeHostedProcessRunner : IHostedProcessRunner
    {
        private readonly string _output;

        public FakeHostedProcessRunner(string output)
        {
            _output = output;
        }

        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
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
