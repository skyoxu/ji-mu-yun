using FluentAssertions;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypeIterationPlanServiceTests
{
    [Fact]
    public async Task EvaluateAsync_ShouldSuggestRefine_WhenFirstGoalIsTooBroad()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Please complete the first full playable loop: stable movement, visible encounter trigger, one battle, reward 3 choices, then return to the map.",
                "completion_suggestion"));

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress(
                "succeeded",
                "succeeded",
                "",
                "done",
                null,
                null,
                null,
                "completion summary",
                "system",
                "recommended",
                "The next step is aligned with the current prototype gap."));

        result.Decision.Should().Be("should_refine_plan");
        result.Summary.Should().NotBeNullOrWhiteSpace();
        result.Reason.Should().NotBeNullOrWhiteSpace();
        result.SuggestedAction.Should().NotBeNullOrWhiteSpace();
        result.SuggestedPromptForRegeneration.Should().NotBeNullOrWhiteSpace();
    }

    [Fact]
    public async Task CreateAsync_ShouldAutoEvaluateAndPersistLatestEvaluation()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Please complete the first full playable loop: stable movement, visible encounter trigger, one battle, reward 3 choices, then return to the map.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().NotBeNullOrWhiteSpace();

        var latest = await service.GetLatestAsync(accountId, projectId);
        latest.Should().NotBeNull();
        latest!.LatestEvaluation.Should().NotBeNull();
        latest.LatestEvaluation!.Decision.Should().Be(result.LatestEvaluation.Decision);
    }

    [Fact]
    public async Task EvaluateAsync_ShouldBeReadyToExecute_WhenPendingGoalIsFocused()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "manual_feedback",
            "Improve one objective hint.",
            "Demo Game: improve one objective hint.",
            [
                new ProjectIterationGoalCreateCommand(1, "Goal 1", "Show one clear hint.", "The player sees the hint."),
                new ProjectIterationGoalCreateCommand(2, "Goal 2", "Keep the hint accurate.", "The hint still matches the flow."),
                new ProjectIterationGoalCreateCommand(3, "Goal 3", "Verify one quick pass.", "One quick pass is complete.")
            ]);

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("ready_to_execute");
        result.Summary.Should().NotBeNullOrWhiteSpace();
        result.Reason.Should().NotBeNullOrWhiteSpace();
        result.SuggestedAction.Should().NotBeNullOrWhiteSpace();
        result.SuggestedPromptForRegeneration.Should().BeNull();
    }

    [Fact]
    public async Task CreateAsync_ShouldKeepStructuredGoals_WhenMessageUsesNumberedList()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Please split this into 4 smaller goals.\n1. Stabilize map movement\n2. Add visible encounter trigger\n3. Finish one battle and settlement\n4. Reward 3 choices and return to the map.",
                "manual_feedback"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(5);
        result.Goals[0].Description.Should().Be("Stabilize map movement");
        result.Goals[1].Description.Should().Be("Add visible encounter trigger");
        result.Goals[2].Description.Should().Be("Finish one battle and settlement");
        result.Goals[3].Description.Should().StartWith("Reward 3 choices and return to the map");
        result.Goals[4].Title.Should().Contain("Final Step");
    }

    [Fact]
    public async Task CreateAsync_ShouldKeepOnlyNumberedGoals_WhenChineseMessageHasIntroText()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                """
                请基于当前原型缺口，重拆成 4 个更小、可以单独执行的目标：
                1. 先稳定地图移动与镜头跟随
                2. 加入可见遇敌触发并能正常进入战斗
                3. 完成一场战斗并正确结算胜负
                4. 胜利后给出三选一奖励并返回地图
                """,
                "manual_feedback"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(5);
        result.Goals.Take(4).Select(goal => goal.Description).Should().Equal(
            "先稳定地图移动与镜头跟随",
            "加入可见遇敌触发并能正常进入战斗",
            "完成一场战斗并正确结算胜负",
            "胜利后给出三选一奖励并返回地图");
        result.Goals[4].Title.Should().Contain("Final Step");
    }

    [Fact]
    public async Task CreateAsync_ShouldForceRpgContractGoals_WhenProjectIsRpg()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Improve the first playable loop: movement, encounter, battle, reward, and return to the map.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(6);
        result.Goals[0].Title.Should().Be("RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry");
        string.Join(" ", result.Goals[0].Title, result.Goals[0].Description, result.Goals[0].AcceptanceHint)
            .Should()
            .Contain("Start Adventure")
            .And.Contain("MapScene")
            .And.Contain("stable movement")
            .And.Contain("encounter entry")
            .And.Contain("asset")
            .And.NotContain("BattleScene")
            .And.NotContain("full playable")
            .And.NotContain("scene switching");
        result.Goals[1].Title.Should().Be("RPG Step 2: BattleScene loop validation");
        result.Goals[1].Description.Should().Contain("enemy asset");
        result.Goals[2].Title.Should().Be("RPG Step 3: reward 3-choice and return-to-map validation");
        result.Goals[3].Title.Should().Be("RPG Step 4: main loop scene switching validation");
        result.Goals[4].Title.Should().Be("RPG Step 5: win/fail visibility and readability validation");
        result.Goals.Select(goal => goal.Title).Should().Contain(title => title.Contains("BattleScene", StringComparison.OrdinalIgnoreCase));
        result.Goals.Select(goal => goal.Title).Should().Contain(title => title.Contains("scene switching", StringComparison.OrdinalIgnoreCase));
        result.Goals.Select(goal => goal.Title).Should().Contain(title => title.Contains("reward", StringComparison.OrdinalIgnoreCase));
        result.Goals.Last().Title.Should().Contain("Final Step");
        result.Goals.Last().AcceptanceHint.Should().Contain("full RPG playable prototype");
        result.Goals.Last().AcceptanceHint.Should().Contain("Start Adventure visible-map validation");
    }

    [Fact]
    public async Task CreateAsync_ShouldUseRpgClosureGoals_AfterPrototypeAlreadySucceeded()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var runId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(
            runId,
            "succeeded",
            0,
            "ok",
            "",
            """
            {
              "prototype_completion": {
                "succeeded": true,
                "completed_through_day": 7
              }
            }
            """);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Please continue refining the current RPG prototype after the first successful playable loop.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(6);
        result.Goals[0].Title.Should().Be("RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry");
        result.Goals[1].Title.Should().Be("RPG Step 2: BattleScene loop validation");
        result.Goals[2].Title.Should().Be("RPG Step 3: reward 3-choice and return-to-map validation");
        result.Goals[3].Title.Should().Be("RPG Step 4: main loop scene switching validation");
        result.Goals[4].Title.Should().Be("RPG Step 5: win/fail visibility and readability validation");
        result.Goals[0].Title.Should().NotContain("对齐原型合同");
        result.Goals.Last().Title.Should().Contain("RPG Final Step");
    }

    [Fact]
    public async Task CreateAsync_ShouldUsePreviousRefinementEvaluation_AsHardRegenerationGuidance()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());
        var runId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(runId, "succeeded", 0, "ok", "", "{}");
        var previous = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Improve the RPG playable loop.",
            "Demo Game: improve RPG loop.",
            [
                new ProjectIterationGoalCreateCommand(1, "RPG Step 1: foundation asset usage and UI contract", "Validate foundation assets first.", "Foundation assets pass."),
                new ProjectIterationGoalCreateCommand(2, "RPG Step 2: Start Adventure to visible MapScene validation", "Validate visible map later.", "Visible map passes.")
            ]);
        var evaluationJson = JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
            "should_refine_plan",
            "The plan must be regenerated.",
            "The latest prototype gap is navigation and visible-map related, so Step 1 must target Start Adventure to visible MapScene and stable movement.",
            "Regenerate the plan with the navigation blocker first.",
            "Regenerate the RPG iteration plan: first priority must combine Start Adventure to visible MapScene, stable movement, and encounter entry before assets/UI polish."));
        await store.UpdateProjectIterationSessionStatusAsync(previous.SessionId, "ready", 0, "needs refinement", evaluationJson);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Please continue refining the current RPG prototype after the first successful playable loop.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(6);
        result.Goals[0].Title.Should().Be("RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry");
        result.Goals[0].Description.Should().Contain("Start Adventure");
        result.Goals[0].Description.Should().Contain("visible MapScene");
        result.Goals[0].Description.Should().Contain("encounter entry");
        result.Goals[0].AcceptanceHint.Should().Contain("move continuously");
        result.Goals[0].AcceptanceHint.Should().Contain("first encounter entry");
        result.Goals[1].Title.Should().Be("RPG Step 2: BattleScene loop validation");
        result.Goals[2].Title.Should().Be("RPG Step 3: reward 3-choice and return-to-map validation");
        result.Goals[3].Title.Should().Be("RPG Step 4: main loop scene switching validation");
        result.Goals[0].Title.ToLowerInvariant().Should().NotContain("foundation asset");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().Be("ready_to_execute");
    }

    [Fact]
    public async Task CreateAsync_ShouldIgnoreStaleRpgBoundaryEvaluation_WhenSavedPlanAlreadyMatchesStrictRoute()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new StaleBoundaryRpgPlanCodexClient());
        var runId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "prototype-7day-playable");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(runId, "succeeded", 0, "ok", "", "{}");

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Please continue refining the current RPG prototype after the first successful playable loop.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(6);
        result.Goals[0].Title.Should().Be("RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry");
        string.Join(" ", result.Goals[0].Title, result.Goals[0].Description, result.Goals[0].AcceptanceHint)
            .Should()
            .Contain("Start Adventure")
            .And.Contain("visible MapScene")
            .And.Contain("stable movement")
            .And.Contain("encounter entry")
            .And.NotContain("BattleScene")
            .And.NotContain("reward")
            .And.NotContain("final acceptance");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().Be("ready_to_execute");
        result.LatestEvaluation.Reason.Should().Contain("saved final goals already keep Step 1 limited");
        result.LatestEvaluation.SuggestedPromptForRegeneration.Should().BeNull();

        var latest = await service.GetLatestAsync(accountId, projectId);
        latest.Should().NotBeNull();
        latest!.LatestEvaluation.Should().NotBeNull();
        latest.LatestEvaluation!.Decision.Should().Be("ready_to_execute");
    }

    [Fact]
    public async Task CreateAsync_ShouldReturnLlmFailed_WhenModelGeneratedPlanDoesNotMatchRpgScaffold()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new GenericRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Improve the first playable loop: movement, encounter, battle, reward, and return to the map.",
                "completion_suggestion"));

        result.Status.Should().Be("llm_failed");
        result.Goals.Should().BeEmpty();
        result.Summary.Should().Contain("goal_plan_parse_failed");
    }

    [Fact]
    public async Task CreateAsync_ShouldAcceptModelRefinement_OnlyWhenTitlesMatchScaffold()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new MatchingRpgRefinementCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Improve the first playable loop: movement, encounter, battle, reward, and return to the map.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(6);
        result.Goals[0].Description.Should().Contain("visible MapScene");
        result.Goals[0].AcceptanceHint.Should().Contain("asset");
        result.Goals[1].AcceptanceHint.Should().Contain("enemy asset");
        result.Goals[5].AcceptanceHint.Should().Contain("contract-specific runtime proof");
    }

    [Fact]
    public async Task EvaluateAsync_ShouldRefineRpgPlan_WhenContractStepsAreMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new RpgEvaluationCodexClient(
            "should_refine_plan",
            "当前计划仍需重拆。",
            "Missing RPG contract steps: MapScene, BattleScene, reward loop.",
            "请重拆 RPG 计划。",
            "Regenerate the RPG iteration plan."));

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "manual_feedback",
            "Improve RPG loop.",
            "Demo Game: improve RPG loop.",
            [
                new ProjectIterationGoalCreateCommand(1, "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry", "Start Adventure opens a visible MapScene with stable movement, map/player assets, and encounter entry.", "Visible MapScene, stable movement, assets, and encounter entry pass."),
                new ProjectIterationGoalCreateCommand(2, "Goal 2", "Polish one map label.", "The map label is readable.")
            ]);

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("should_refine_plan");
        result.Reason.Should().Contain("Missing RPG contract steps");
        result.SuggestedPromptForRegeneration.Should().NotBeNullOrWhiteSpace();
    }

    [Fact]
    public async Task EvaluateAsync_ShouldUseLlmEvaluation_AfterRpgPlanPassesLocalRouteGuard()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var codex = new LlmEvaluationCodexClient();
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, codex);

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Improve RPG loop.",
            "Demo Game: improve RPG loop.",
            [
                new ProjectIterationGoalCreateCommand(1, "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry", "Start Adventure opens a visible MapScene with stable movement, map/player assets, and encounter entry.", "Visible MapScene, stable movement, assets, and encounter entry pass."),
                new ProjectIterationGoalCreateCommand(2, "RPG Step 2: BattleScene loop validation", "Validate BattleScene with one readable battle, enemy asset usage, feedback, and settlement.", "BattleScene settlement and enemy asset usage pass."),
                new ProjectIterationGoalCreateCommand(3, "RPG Step 3: reward 3-choice and return-to-map validation", "Validate reward 3-choice state change and return-to-map.", "Reward 3-choice and return-to-map pass."),
                new ProjectIterationGoalCreateCommand(4, "RPG Step 4: main loop scene switching validation", "Validate main loop scene switching from Start Adventure to map, encounter, BattleScene, reward, and return-to-map.", "Main loop scene switching passes."),
                new ProjectIterationGoalCreateCommand(5, "RPG Step 5: win/fail visibility and readability validation", "Show victory, failure, defeat, and encounter rules clearly.", "Win/fail and encounter rule feedback pass."),
                new ProjectIterationGoalCreateCommand(6, "RPG Final Step: full playable prototype acceptance", "Run final acceptance across Start Adventure visible map, battle, reward return-to-map, project contract, map/player/enemy assets, and package readiness.", "Final acceptance, project contract, and asset usage pass.")
            ]);

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("failed", "failed", "", "done", null, null, null, "navigation failed", "system", "recommended", "MapScene is not visible after Start Adventure."));

        result.Decision.Should().Be("should_refine_plan");
        result.Summary.Should().Contain("需要重拆");
        result.Reason.Should().Contain("MapScene");
        result.SuggestedPromptForRegeneration.Should().Contain("Start Adventure");
        codex.LastPrompt.Should().Contain("Use only the data provided in this prompt.");
        codex.LastPrompt.Should().Contain("Do not read files, inspect the repository, call tools, or ask for more context.");
        codex.LastOptions.Should().NotBeNull();
        codex.LastOptions!.IgnoreRules.Should().BeTrue();
        codex.LastOptions.ReasoningEffort.Should().Be("minimal");
    }

    [Fact]
    public async Task EvaluateAsync_ShouldReturnLlmFailed_WhenRpgLlmEvaluationFails()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new FailedEvaluationCodexClient());

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "manual_feedback",
            "Improve RPG loop.",
            "Demo Game: improve RPG loop.",
            [
                new ProjectIterationGoalCreateCommand(1, "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry", "Start Adventure opens a visible MapScene with stable movement, map/player assets, and encounter entry.", "Visible MapScene, stable movement, assets, and encounter entry pass."),
                new ProjectIterationGoalCreateCommand(2, "RPG Step 2: BattleScene loop validation", "Validate BattleScene with one readable battle, enemy asset usage, feedback, and settlement.", "BattleScene settlement and enemy asset usage pass."),
                new ProjectIterationGoalCreateCommand(3, "RPG Step 3: reward 3-choice and return-to-map validation", "Validate reward 3-choice state change and return-to-map.", "Reward 3-choice and return-to-map pass."),
                new ProjectIterationGoalCreateCommand(4, "RPG Step 4: main loop scene switching validation", "Validate main loop scene switching from Start Adventure to map, encounter, BattleScene, reward, and return-to-map.", "Main loop scene switching passes."),
                new ProjectIterationGoalCreateCommand(5, "RPG Step 5: win/fail visibility and readability validation", "Show victory, failure, defeat, and encounter rules clearly.", "Win/fail and encounter rule feedback pass."),
                new ProjectIterationGoalCreateCommand(6, "RPG Final Step: full playable prototype acceptance", "Run final acceptance across Start Adventure visible map, battle, reward return-to-map, project contract, map/player/enemy assets, and package readiness.", "Final acceptance, project contract, and asset usage pass.")
            ]);

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("llm_failed");
        result.Reason.Should().Contain("codex_failed");
        result.SuggestedAction.Should().Contain("修复 LLM");
    }

    [Fact]
    public async Task CreateAsync_ShouldReturnLlmFailed_WhenRpgPlanningAnalysisFails()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new FailedEvaluationCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Improve the first playable loop: movement, encounter, battle, reward, and return to the map.",
                "completion_suggestion"));

        result.Status.Should().Be("llm_failed");
        result.SessionId.Should().BeEmpty();
        result.Goals.Should().BeEmpty();
        result.Summary.Should().Contain("codex_failed");
        var latest = await service.GetLatestAsync(accountId, projectId);
        latest.Should().BeNull();
    }

    [Fact]
    public async Task EvaluateAsync_ShouldRefineRpgPlan_WhenStepOneCrossesAcceptanceBoundary()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new RpgEvaluationCodexClient(
            "should_refine_plan",
            "当前计划仍需重拆。",
            "acceptance boundary mismatch: first step crosses scene and full-playable boundaries.",
            "请重拆 RPG 计划。",
            "Regenerate the RPG iteration plan."));

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "manual_feedback",
            "Improve RPG loop.",
            "Demo Game: improve RPG loop.",
            [
                new ProjectIterationGoalCreateCommand(1, "RPG Step 1: basic assets and full scene validation", "Validate assets, MapScene.tscn, BattleScene.tscn, and full playable scene switching.", "Pass when MapScene and BattleScene both work."),
                new ProjectIterationGoalCreateCommand(2, "RPG Step 2: Start Adventure to visible MapScene validation", "Create and validate visible MapScene.", "Start Adventure opens a visible RPG MapScene."),
                new ProjectIterationGoalCreateCommand(3, "RPG Step 3: BattleScene creation and validation", "Create and validate BattleScene.", "BattleScene reaches settlement."),
                new ProjectIterationGoalCreateCommand(4, "RPG Step 4: main prototype scene and scene switching validation", "Connect the main scene switching flow.", "Main prototype scene switching works."),
                new ProjectIterationGoalCreateCommand(5, "RPG Step 5: reward loop and return-to-map validation", "Validate reward and return-to-map.", "Reward returns to the map."),
                new ProjectIterationGoalCreateCommand(6, "RPG Final Step: full playable prototype acceptance", "Validate full playable prototype acceptance.", "Final acceptance passes with Start Adventure visible map and package readiness.")
            ]);

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("should_refine_plan");
        result.Reason.Should().Contain("acceptance boundary mismatch");
        result.SuggestedPromptForRegeneration.Should().NotBeNullOrWhiteSpace();
    }

    [Fact]
    public async Task EvaluateAsync_ShouldAllowRpgPlan_WhenStepOneOnlyMentionsLaterWorkAsExclusion()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new RpgEvaluationCodexClient(
            "ready_to_execute",
            "The RPG plan can execute.",
            "The saved goals keep Step 1 focused and split later work into later steps.",
            "Execute the next goal.",
            null));

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Win after 15 battles; any battle loss means game loss.",
            "Demo Game: improve RPG loop.",
            [
                new ProjectIterationGoalCreateCommand(
                    1,
                    "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry",
                    "Resolve the first RPG route blocker as the initial convergence step: Start Adventure opens a visible MapScene, shows runtime map/player assets, proves stable controllable movement, and exposes the first encounter entry. Keep this step tightly focused on map start, movement stability, and encounter entry because those are still the primary unproven runtime blockers before battle, reward, or broader loop closure work.",
                    "Pass only when Start Adventure opens a visible RPG MapScene, runtime evidence proves the player can move continuously and controllably on that map, map/player asset usage is visible, and actual traversal reaches a clear first encounter entry."),
                new ProjectIterationGoalCreateCommand(2, "RPG Step 2: BattleScene loop validation", "Validate BattleScene with one readable battle, enemy asset usage, feedback, and settlement.", "BattleScene settlement and enemy asset usage pass."),
                new ProjectIterationGoalCreateCommand(3, "RPG Step 3: reward 3-choice and return-to-map validation", "Validate reward 3-choice state change and return-to-map.", "Reward 3-choice and return-to-map pass."),
                new ProjectIterationGoalCreateCommand(4, "RPG Step 4: main loop scene switching validation", "Validate main loop scene switching from Start Adventure to map, encounter, BattleScene, reward, and return-to-map.", "Main loop scene switching passes."),
                new ProjectIterationGoalCreateCommand(5, "RPG Step 5: win/fail visibility and readability validation", "Show and validate win after 15 battles, any battle loss means game loss, and encounter rules clearly.", "Win after 15 battles, any-loss defeat, and encounter rule feedback pass."),
                new ProjectIterationGoalCreateCommand(6, "RPG Final Step: full playable prototype acceptance", "Run final acceptance across Start Adventure visible map, battle, reward return-to-map, win after 15 battles, any battle loss means game loss, project contract, map/player/enemy assets, and package readiness.", "Final acceptance, explicit rule coverage, project contract, and asset usage pass.")
            ]);

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("ready_to_execute");
        result.Reason.Should().Contain("focused");
    }

    [Fact]
    public async Task EvaluateAsync_ShouldBeReadyForRpgPlan_WhenContractStepsExist()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Improve the RPG playable loop.",
                "completion_suggestion"));

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("ready_to_execute");
        result.SuggestedPromptForRegeneration.Should().BeNull();
    }

    [Fact]
    public async Task EvaluateAsync_ShouldRefineRpgPlan_WhenExplicitWinFailRulesAreNotNamedInGoals()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new RpgEvaluationCodexClient(
            "should_refine_plan",
            "当前计划缺少显式胜负规则覆盖。",
            "Missing explicit 15-battle victory rule coverage.",
            "请重拆 RPG 计划。",
            "Regenerate the RPG iteration plan with explicit win/fail rules."));

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Please continue the RPG loop and explicitly keep these hard rules: win after 15 battles, any battle loss means game loss, every movement increases encounter chance by 10%, and encounter must happen within 10 steps.",
            "Demo Game: improve RPG loop with explicit hard rules.",
            [
                new ProjectIterationGoalCreateCommand(1, "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry", "Start Adventure opens visible MapScene with stable movement, map/player assets, and encounter progress.", "Visible MapScene, stable movement, assets, and encounter validation pass."),
                new ProjectIterationGoalCreateCommand(2, "RPG Step 2: BattleScene loop validation", "Validate BattleScene with one readable battle and enemy asset usage.", "BattleScene proves battle settlement."),
                new ProjectIterationGoalCreateCommand(3, "RPG Step 3: reward 3-choice and return-to-map validation", "Reward 3-choice returns to map and keeps the loop active.", "Reward 3-choice and return-to-map pass."),
                new ProjectIterationGoalCreateCommand(4, "RPG Step 4: main loop scene switching validation", "Connect Start Adventure, map, encounter, BattleScene, reward, and return-to-map.", "Main loop scene switching passes."),
                new ProjectIterationGoalCreateCommand(5, "RPG Step 5: win/fail visibility and readability validation", "Show encounter rules and failure feedback, but omit explicit 15-battle victory wording.", "Win/fail and encounter rule feedback pass."),
                new ProjectIterationGoalCreateCommand(6, "RPG Final Step: full playable prototype acceptance", "Run final acceptance across Start Adventure visible map, reward return-to-map, project contract, map/player/enemy assets, and package readiness.", "Final acceptance, project contract, and asset usage pass.")
            ]);

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("should_refine_plan");
        result.Reason.Should().Contain("15-battle");
    }

    [Fact]
    public async Task EvaluateAsync_ShouldAllowRpgPlan_WhenExplicitRulesAreNamedInGoals()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new RpgEvaluationCodexClient(
            "ready_to_execute",
            "当前计划可执行。",
            "The plan explicitly covers RPG rules.",
            "可以直接执行下一目标。",
            null));

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Improve RPG loop.",
            "Demo Game: improve RPG loop.",
            [
                new ProjectIterationGoalCreateCommand(1, "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry", "Start Adventure opens visible MapScene with stable movement, map/player assets, 10% encounter progress, and guaranteed encounter within 10 steps.", "Visible MapScene, 10% encounter progress, 10 steps, stable movement, assets, and encounter validation pass."),
                new ProjectIterationGoalCreateCommand(2, "RPG Step 2: BattleScene loop validation", "Validate BattleScene with one readable battle, enemy asset usage, any-loss defeat settlement, and enemy scaling with +5 HP and +2 ATK each battle.", "BattleScene proves battle settlement, any-loss defeat rule, and enemy scaling."),
                new ProjectIterationGoalCreateCommand(3, "RPG Step 3: reward 3-choice and return-to-map validation", "Reward 3-choice returns to map and keeps the loop active.", "Reward 3-choice and return-to-map pass."),
                new ProjectIterationGoalCreateCommand(4, "RPG Step 4: main loop scene switching validation", "Connect Start Adventure, map, encounter, BattleScene, reward, and return-to-map.", "Main loop scene switching passes."),
                new ProjectIterationGoalCreateCommand(5, "RPG Step 5: win/fail visibility and readability validation", "Show and validate win after 15 battles, guaranteed encounter within 10 steps, and any battle loss means game loss.", "15 battles, 10 steps, and any-loss defeat rules are all visible and validated."),
                new ProjectIterationGoalCreateCommand(6, "RPG Final Step: full playable prototype acceptance", "Run final acceptance across Start Adventure visible map, reward return-to-map, 15 battles rule, project contract, map/player/enemy assets, and package readiness.", "Final acceptance, explicit rule coverage, project contract, and asset usage pass.")
            ]);

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("ready_to_execute");
    }

    [Fact]
    public async Task CreateAsync_FinalGoal_ShouldCarryPrototypeInputContractInstruction()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var project = await store.GetProjectSnapshotAsync(projectId);
        new PrototypeContractService().WriteFromRequest(
            project!,
            new PrototypeWorkflowRequest(
                "rpg-contract-demo",
                "RPG Contract Demo",
                "rpg",
                "RPG",
                "Validate user-specific RPG rules.",
                "Explore, trigger danger, survive a small battle.",
                "Move on map, trigger encounter, fight, choose reward, return.",
                ["The first enemy has 30 HP and 5 attack."],
                "Each movement increases encounter chance by 10%.",
                "Move once, update encounter chance, enter battle, resolve reward.",
                "Win by defeating enemy; fail when hero HP reaches zero.",
                true),
            "docs/prototypes/2026-05-24-rpg-contract-demo.md",
            "rpg-contract-demo");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient(includeContractInstruction: true));

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest("Improve the RPG playable loop.", "completion_suggestion"));

        result.Goals.Should().NotBeEmpty();
        result.Goals[^1].Description.Should().Contain("input_traceability");
        result.Goals[^1].AcceptanceHint.Should().Contain("project-specific prototype contract fields pass");
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId, string gameTypeSource = "Action")
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", gameTypeSource, null, null, null, null));
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

    private sealed class LlmEvaluationCodexClient : ICodexChatClient
    {
        public string? LastPrompt { get; private set; }
        public CodexChatClientOptions? LastOptions { get; private set; }

        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            LastPrompt = prompt;
            LastOptions = options;
            const string json = """
            {
              "decision": "should_refine_plan",
              "summary": "当前计划仍需要重拆。",
              "reason": "The plan does not start from the navigation blocker. It should begin with Start Adventure to visible MapScene, then movement and encounter, before any generic contract-alignment step.",
              "suggestedAction": "请先按导航阻塞点重拆 RPG 迭代计划。",
              "suggestedPromptForRegeneration": "Regenerate the RPG iteration plan starting with Start Adventure to visible MapScene, movement and first encounter, BattleScene, reward loop return-to-map, and final playable acceptance."
            }
            """;
            return Task.FromResult(new CodexChatClientResult(true, json, null, 0, "", ""));
        }
    }

    private sealed class SuccessfulRpgPlanCodexClient : ICodexChatClient
    {
        private readonly bool _includeContractInstruction;

        public SuccessfulRpgPlanCodexClient(bool includeContractInstruction = false)
        {
            _includeContractInstruction = includeContractInstruction;
        }

        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            if (options?.OutputSchemaPath?.Contains("planning-analysis", StringComparison.OrdinalIgnoreCase) == true)
            {
                const string analysis =
                    """
                    {
                      "analysisSummary": "LLM planning analysis ok.",
                      "fieldCoverage": [
                        { "field": "hypothesis", "status": "partial", "evidence": "prototype request", "missingReason": null },
                        { "field": "reward_loop", "status": "partial", "evidence": "reward 3-choice", "missingReason": null },
                        { "field": "win_fail_conditions", "status": "partial", "evidence": "win/fail rules", "missingReason": null }
                      ]
                    }
                    """;
                return Task.FromResult(new CodexChatClientResult(true, analysis, null, 0, "", ""));
            }

            if (options?.OutputSchemaPath?.Contains("goal-plan", StringComparison.OrdinalIgnoreCase) == true)
            {
                var finalDescription = _includeContractInstruction
                    ? "Run final acceptance across map, battle, reward return, navigation, input_traceability, and contract-specific runtime proof."
                    : "Run final acceptance across map, battle, reward return, navigation, and contract-specific runtime proof.";
                var finalAcceptance = _includeContractInstruction
                    ? "Pass only when the full prototype and project-specific prototype contract fields pass."
                    : "Pass only when the full RPG playable prototype, Start Adventure visible-map validation, and contract-specific runtime proof all pass.";
                if (prompt.Contains("RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry", StringComparison.Ordinal))
                {
                    var navigationFirstPayload = $$"""
                    {
                      "goals": [
                        {
                          "title": "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry",
                          "description": "Resolve the navigation blocker first: Start Adventure opens a visible MapScene, proves stable controllable movement, shows map/player asset usage, and exposes first encounter entry.",
                          "acceptanceHint": "Pass only when Start Adventure opens a visible RPG MapScene, the player can move continuously, map/player assets are visible, and first encounter entry is exposed."
                        },
                        {
                          "title": "RPG Step 2: BattleScene loop validation",
                          "description": "Validate one readable BattleScene loop with enemy asset usage and settlement.",
                          "acceptanceHint": "Pass only when BattleScene reaches clear battle feedback, enemy asset usage, and settlement."
                        },
                        {
                          "title": "RPG Step 3: reward 3-choice and return-to-map validation",
                          "description": "Prove reward 3-choice changes state and returns to the active map loop.",
                          "acceptanceHint": "Pass only when reward selection, state change, and return-to-map are visible."
                        },
                        {
                          "title": "RPG Step 4: main loop scene switching validation",
                          "description": "Connect Start Adventure, map, encounter, battle, reward, and return-to-map after the reward loop is proven.",
                          "acceptanceHint": "Pass only when scene switching covers the full first RPG loop."
                        },
                        {
                          "title": "RPG Step 5: win/fail visibility and readability validation",
                          "description": "Show and validate 15-battle victory, any-loss defeat, and encounter rules.",
                          "acceptanceHint": "Pass only when players can understand win/fail and encounter rules."
                        },
                        {
                          "title": "RPG Final Step: full playable prototype acceptance",
                          "description": "{{finalDescription}}",
                          "acceptanceHint": "{{finalAcceptance}} map/player/enemy asset usage remains visible."
                        }
                      ]
                    }
                    """;
                    return Task.FromResult(new CodexChatClientResult(true, navigationFirstPayload, null, 0, "", ""));
                }

                var payload = $$"""
                {
                  "goals": [
                    {
                      "title": "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry",
                      "description": "Resolve the navigation blocker first: Start Adventure opens a visible MapScene, proves stable controllable movement, shows map/player asset usage, and exposes first encounter entry.",
                      "acceptanceHint": "Pass only when Start Adventure opens a visible RPG MapScene, the player can move continuously, map/player assets are visible, and first encounter entry is exposed."
                    },
                    {
                      "title": "RPG Step 2: BattleScene loop validation",
                      "description": "Validate one readable BattleScene loop with enemy asset usage and settlement.",
                      "acceptanceHint": "Pass only when BattleScene reaches clear battle feedback, enemy asset usage, and settlement."
                    },
                    {
                      "title": "RPG Step 3: reward 3-choice and return-to-map validation",
                      "description": "Prove reward 3-choice changes state and returns to the active map loop.",
                      "acceptanceHint": "Pass only when reward selection, state change, and return-to-map are visible."
                    },
                    {
                      "title": "RPG Step 4: main loop scene switching validation",
                      "description": "Connect Start Adventure, map, encounter, battle, reward, and return-to-map after the reward loop is proven.",
                      "acceptanceHint": "Pass only when scene switching covers the full first RPG loop."
                    },
                    {
                      "title": "RPG Step 5: win/fail visibility and readability validation",
                      "description": "Show and validate 15-battle victory, any-loss defeat, and encounter rules.",
                      "acceptanceHint": "Pass only when players can understand win/fail and encounter rules."
                    },
                    {
                      "title": "RPG Final Step: full playable prototype acceptance",
                      "description": "{{finalDescription}}",
                      "acceptanceHint": "{{finalAcceptance}} map/player/enemy asset usage remains visible."
                    }
                  ]
                }
                """;
                return Task.FromResult(new CodexChatClientResult(true, payload, null, 0, "", ""));
            }

            const string evaluation =
                """
                {
                  "decision": "ready_to_execute",
                  "summary": "当前计划可执行。",
                  "reason": "The plan is focused and ordered.",
                  "suggestedAction": "可以执行下一目标。",
                  "suggestedPromptForRegeneration": null
                }
                """;
            return Task.FromResult(new CodexChatClientResult(true, evaluation, null, 0, "", ""));
        }
    }

    private sealed class RpgEvaluationCodexClient : ICodexChatClient
    {
        private readonly string _decision;
        private readonly string _summary;
        private readonly string _reason;
        private readonly string _suggestedAction;
        private readonly string? _suggestedPrompt;

        public RpgEvaluationCodexClient(
            string decision,
            string summary,
            string reason,
            string suggestedAction,
            string? suggestedPrompt)
        {
            _decision = decision;
            _summary = summary;
            _reason = reason;
            _suggestedAction = suggestedAction;
            _suggestedPrompt = suggestedPrompt;
        }

        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            var payload = $$"""
            {
              "decision": "{{_decision}}",
              "summary": "{{_summary}}",
              "reason": "{{_reason}}",
              "suggestedAction": "{{_suggestedAction}}",
              "suggestedPromptForRegeneration": {{(_suggestedPrompt is null ? "null" : JsonSerializer.Serialize(_suggestedPrompt))}}
            }
            """;
            return Task.FromResult(new CodexChatClientResult(true, payload, null, 0, "", ""));
        }
    }

    private sealed class StaleBoundaryRpgPlanCodexClient : ICodexChatClient
    {
        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            if (options?.OutputSchemaPath?.Contains("planning-analysis", StringComparison.OrdinalIgnoreCase) == true)
            {
                const string analysis =
                    """
                    {
                      "analysisSummary": "LLM planning analysis ok.",
                      "fieldCoverage": [
                        { "field": "reward_loop", "status": "partial", "evidence": "reward 3-choice", "missingReason": null },
                        { "field": "win_fail_conditions", "status": "partial", "evidence": "win/fail rules", "missingReason": null }
                      ]
                    }
                    """;
                return Task.FromResult(new CodexChatClientResult(true, analysis, null, 0, "", ""));
            }

            if (options?.OutputSchemaPath?.Contains("goal-plan", StringComparison.OrdinalIgnoreCase) == true)
            {
                const string goals =
                    """
                    {
                      "goals": [
                        {
                          "title": "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry",
                          "description": "Resolve the navigation blocker first: Start Adventure opens a visible MapScene, proves stable movement, shows map/player asset usage, and exposes encounter entry.",
                          "acceptanceHint": "Pass only when Start Adventure opens a visible RPG MapScene, movement stays stable, map/player assets are visible, and encounter entry is exposed."
                        },
                        {
                          "title": "RPG Step 2: BattleScene loop validation",
                          "description": "Validate one readable BattleScene loop with enemy asset usage and settlement.",
                          "acceptanceHint": "Pass only when BattleScene reaches clear battle feedback, enemy asset usage, and settlement."
                        },
                        {
                          "title": "RPG Step 3: reward 3-choice and return-to-map validation",
                          "description": "Prove reward 3-choice changes state and returns to the active map loop.",
                          "acceptanceHint": "Pass only when reward selection, state change, and return-to-map are visible."
                        },
                        {
                          "title": "RPG Step 4: main loop scene switching validation",
                          "description": "Connect Start Adventure, map, encounter, BattleScene, reward, and return-to-map after the reward loop is proven.",
                          "acceptanceHint": "Pass only when scene switching covers the full first RPG loop."
                        },
                        {
                          "title": "RPG Step 5: win/fail visibility and readability validation",
                          "description": "Show and validate 15-battle victory, any-loss defeat, and encounter rules.",
                          "acceptanceHint": "Pass only when players can understand win/fail and encounter rules."
                        },
                        {
                          "title": "RPG Final Step: full playable prototype acceptance",
                          "description": "Run final acceptance across Start Adventure visible map, battle, reward return, navigation, and contract-specific runtime proof.",
                          "acceptanceHint": "Pass only when the full RPG playable prototype, Start Adventure visible-map validation, contract-specific runtime proof, and map/player/enemy asset usage all pass."
                        }
                      ]
                    }
                    """;
                return Task.FromResult(new CodexChatClientResult(true, goals, null, 0, "", ""));
            }

            const string evaluation =
                """
                {
                  "decision": "should_refine_plan",
                  "summary": "The RPG plan still needs refinement.",
                  "reason": "RPG plan acceptance boundary mismatch: step 1 must only validate Start Adventure to visible MapScene, stable movement, and encounter entry. BattleScene, reward, scene switching, package readiness, and final acceptance requirements must be split into later steps.",
                  "suggestedAction": "Regenerate the RPG iteration plan.",
                  "suggestedPromptForRegeneration": "Regenerate the plan so Step 1 only covers Start Adventure, visible MapScene, stable movement, and encounter entry before BattleScene, reward, scene switching, and final acceptance."
                }
                """;
            return Task.FromResult(new CodexChatClientResult(true, evaluation, null, 0, "", ""));
        }
    }

    private sealed class GenericRpgPlanCodexClient : ICodexChatClient
    {
        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            const string payload =
                """
                {
                  "goals": [
                    {
                      "title": "RPG Godot 原型迭代计划",
                      "description": "给出一个通用的 RPG 原型计划。",
                      "acceptanceHint": "通用计划"
                    },
                    {
                      "title": "迭代 1：可玩底座",
                      "description": "实现基础地图与移动。",
                      "acceptanceHint": "可玩"
                    },
                    {
                      "title": "迭代 2：探索-战斗闭环",
                      "description": "加入遇敌与战斗。",
                      "acceptanceHint": "闭环"
                    }
                  ]
                }
                """;
            return Task.FromResult(new CodexChatClientResult(true, payload, null, 0, "", ""));
        }
    }

    private sealed class MatchingRpgRefinementCodexClient : ICodexChatClient
    {
        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            const string payload =
                """
                {
                  "goals": [
                    {
                      "title": "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry",
                      "description": "Resolve the navigation blocker first: Start Adventure opens a visible MapScene, proves stable controllable movement, shows map/player asset usage, and exposes first encounter entry.",
                      "acceptanceHint": "Pass only when Start Adventure opens a visible RPG MapScene, the player can move continuously, map/player assets are visible, and first encounter entry is exposed."
                    },
                    {
                      "title": "RPG Step 2: BattleScene loop validation",
                      "description": "Validate one readable BattleScene loop with enemy asset usage and settlement.",
                      "acceptanceHint": "Pass only when BattleScene reaches clear battle feedback, enemy asset usage, and settlement."
                    },
                    {
                      "title": "RPG Step 3: reward 3-choice and return-to-map validation",
                      "description": "Prove reward 3-choice changes state and returns to the active map loop.",
                      "acceptanceHint": "Pass only when reward selection, state change, and return-to-map are visible."
                    },
                    {
                      "title": "RPG Step 4: main loop scene switching validation",
                      "description": "Connect Start Adventure, map, encounter, battle, reward, and return-to-map after the reward loop is proven.",
                      "acceptanceHint": "Pass only when scene switching covers the full first RPG loop."
                    },
                    {
                      "title": "RPG Step 5: win/fail visibility and readability validation",
                      "description": "Show and validate victory, failure, defeat, and encounter rules.",
                      "acceptanceHint": "Pass only when players can understand victory, failure, defeat, and encounter rule feedback."
                    },
                    {
                      "title": "RPG Final Step: full playable prototype acceptance",
                      "description": "Run final acceptance across map, battle, reward return, navigation, and contract-specific runtime proof.",
                      "acceptanceHint": "Pass only when the full playable prototype, Start Adventure visible-map validation, contract-specific runtime proof, and map/player/enemy asset usage all pass."
                    }
                  ]
                }
                """;
            return Task.FromResult(new CodexChatClientResult(true, payload, null, 0, "", ""));
        }
    }

    private sealed class FailedEvaluationCodexClient : ICodexChatClient
    {
        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new CodexChatClientResult(false, null, "codex_failed", 1, "", ""));
        }
    }
}
