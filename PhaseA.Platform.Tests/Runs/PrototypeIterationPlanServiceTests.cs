using FluentAssertions;
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
        var service = new PrototypeIterationPlanService(store);

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
        var service = new PrototypeIterationPlanService(store);

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
        var service = new PrototypeIterationPlanService(store);

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
        var service = new PrototypeIterationPlanService(store);

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
        var service = new PrototypeIterationPlanService(store);

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
        var service = new PrototypeIterationPlanService(store);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Improve the first playable loop: movement, encounter, battle, reward, and return to the map.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(6);
        result.Goals.Select(goal => goal.Title).Should().Contain(title => title.Contains("assets", StringComparison.OrdinalIgnoreCase));
        string.Join(" ", result.Goals[0].Title, result.Goals[0].Description, result.Goals[0].AcceptanceHint)
            .Should()
            .NotContain("MapScene")
            .And.NotContain("BattleScene")
            .And.NotContain("full playable")
            .And.NotContain("scene switching");
        result.Goals[1].Title.Should().Contain("Start Adventure");
        result.Goals[1].Title.Should().Contain("MapScene");
        result.Goals[1].Description.Should().Contain("clicking Start Adventure");
        result.Goals[1].AcceptanceHint.Should().Contain("visible RPG MapScene");
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
        var service = new PrototypeIterationPlanService(store);

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
        result.Goals.Should().HaveCountGreaterOrEqualTo(6);
        result.Goals[0].Title.Should().Be("RPG Step 1: foundation asset usage and UI contract");
        result.Goals[1].Title.Should().Be("RPG Step 2: Start Adventure to visible MapScene validation");
        result.Goals[2].Title.Should().Be("RPG Step 3: BattleScene loop validation");
        result.Goals[3].Title.Should().Be("RPG Step 4: main prototype scene and scene switching validation");
        result.Goals[4].Title.Should().Be("RPG Step 5: reward 3-choice and return-to-map validation");
        result.Goals[0].Title.Should().NotContain("对齐原型合同");
        result.Goals.Last().Title.Should().Contain("RPG Final Step");
    }

    [Fact]
    public async Task CreateAsync_ShouldRejectModelGeneratedGenericRpgPlan_AndKeepServerScaffold()
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

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(6);
        result.Goals[0].Title.Should().Be("RPG Step 1: basic assets and UI validation");
        result.Goals[1].Title.Should().Be("RPG Step 2: Start Adventure to visible MapScene validation");
        result.Goals[2].Title.Should().Be("RPG Step 3: BattleScene creation and validation");
        result.Goals[3].Title.Should().Be("RPG Step 4: main prototype scene and scene switching validation");
        result.Goals[4].Title.Should().Be("RPG Step 5: reward loop and return-to-map validation");
        result.Goals[5].Title.Should().Be("RPG Final Step: full playable prototype acceptance");
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
        result.Goals[0].Description.Should().Contain("user-facing map");
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
        var service = new PrototypeIterationPlanService(store);

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "manual_feedback",
            "Improve RPG loop.",
            "Demo Game: improve RPG loop.",
            [
                new ProjectIterationGoalCreateCommand(1, "Goal 1", "Improve map movement and encounter trigger.", "Movement and encounter work."),
                new ProjectIterationGoalCreateCommand(2, "Goal 2", "Improve one battle and settlement.", "Battle reaches settlement."),
                new ProjectIterationGoalCreateCommand(3, "Goal 3", "Improve reward choice and return to map.", "Reward returns to map.")
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
    public async Task EvaluateAsync_ShouldPreferLlmEvaluation_ForRpgPlans()
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
                new ProjectIterationGoalCreateCommand(1, "Goal 1", "Contract alignment first.", "Align contract."),
                new ProjectIterationGoalCreateCommand(2, "Goal 2", "Reward readability.", "Reward is readable."),
                new ProjectIterationGoalCreateCommand(3, "Goal 3", "Battle follow-up.", "Battle loop works.")
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
    public async Task EvaluateAsync_ShouldFallbackToDeterministicRules_WhenLlmEvaluationFails()
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
                new ProjectIterationGoalCreateCommand(1, "Goal 1", "Improve map movement and encounter trigger.", "Movement and encounter work."),
                new ProjectIterationGoalCreateCommand(2, "Goal 2", "Improve one battle and settlement.", "Battle reaches settlement."),
                new ProjectIterationGoalCreateCommand(3, "Goal 3", "Improve reward choice and return to map.", "Reward returns to map.")
            ]);

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("should_refine_plan");
        result.Reason.Should().Contain("Missing RPG contract steps");
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
        var service = new PrototypeIterationPlanService(store);

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
        var service = new PrototypeIterationPlanService(store);

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
        var service = new PrototypeIterationPlanService(store);

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Please continue the RPG loop and explicitly keep these hard rules: win after 15 battles, any battle loss means game loss, every movement increases encounter chance by 10%, and encounter must happen within 10 steps.",
            "Demo Game: improve RPG loop with explicit hard rules.",
            [
                new ProjectIterationGoalCreateCommand(1, "RPG Step 1: foundation asset usage and UI contract", "Validate map, player, enemy assets and readable UI.", "Foundation assets and UI pass."),
                new ProjectIterationGoalCreateCommand(2, "RPG Step 2: Start Adventure to visible MapScene validation", "Start Adventure opens visible MapScene with movement.", "Visible MapScene validation pass."),
                new ProjectIterationGoalCreateCommand(3, "RPG Step 3: BattleScene loop validation", "Validate BattleScene with one readable battle.", "BattleScene proves battle settlement."),
                new ProjectIterationGoalCreateCommand(4, "RPG Step 4: main prototype scene and scene switching validation", "Connect menu, map, battle, and return path.", "Main prototype scene switches correctly."),
                new ProjectIterationGoalCreateCommand(5, "RPG Step 5: reward 3-choice and return-to-map validation", "Reward 3-choice returns to map and keeps the loop active.", "Reward 3-choice and return-to-map pass."),
                new ProjectIterationGoalCreateCommand(6, "RPG Final Step: full playable prototype acceptance", "Run final acceptance across Start Adventure visible map, reward return-to-map, and package readiness.", "Final acceptance passes.")
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
        var service = new PrototypeIterationPlanService(store);

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Improve RPG loop.",
            "Demo Game: improve RPG loop.",
            [
                new ProjectIterationGoalCreateCommand(1, "RPG Step 1: foundation asset usage and UI contract", "Validate map, player, enemy assets and readable UI.", "Foundation assets and UI pass."),
                new ProjectIterationGoalCreateCommand(2, "RPG Step 2: Start Adventure to visible MapScene validation", "Start Adventure opens visible MapScene with movement and 10% encounter progress.", "Visible MapScene and 10% encounter validation pass."),
                new ProjectIterationGoalCreateCommand(3, "RPG Step 3: BattleScene loop validation", "Validate BattleScene with one readable battle and any-loss defeat settlement.", "BattleScene proves battle settlement and any-loss defeat rule."),
                new ProjectIterationGoalCreateCommand(4, "RPG Step 4: main prototype scene and scene switching validation", "Connect menu, map, battle, and return path.", "Main prototype scene switches correctly."),
                new ProjectIterationGoalCreateCommand(5, "RPG Step 5: reward 3-choice and return-to-map validation", "Reward 3-choice returns to map and keeps the loop active.", "Reward 3-choice and return-to-map pass."),
                new ProjectIterationGoalCreateCommand(6, "RPG Step 6: explicit win/fail and scaling rule validation", "Show and validate win after 15 battles, guaranteed encounter within 10 steps, and enemy scaling with +5 HP and +2 ATK each battle.", "15 battles, 10 steps, and enemy scaling rules are all visible and validated."),
                new ProjectIterationGoalCreateCommand(7, "RPG Final Step: full playable prototype acceptance", "Run final acceptance across Start Adventure visible map, reward return-to-map, 15 battles rule, and package readiness.", "Final acceptance passes with explicit rule coverage.")
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
        var service = new PrototypeIterationPlanService(store);

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
                      "title": "RPG Step 1: basic assets and UI validation",
                      "description": "Confirm the current prototype already shows the required foundation assets and readable UI markers on the user-facing map before changing later scenes.",
                      "acceptanceHint": "Pass only when map, player, enemy asset usage and readable map, battle, reward UI markers are visible in the current prototype scene."
                    },
                    {
                      "title": "RPG Step 2: Start Adventure to visible MapScene validation",
                      "description": "Verify the real Start Adventure entry reveals a visible user-facing map, enables movement, and exposes the first encounter trigger.",
                      "acceptanceHint": "Pass only when Start Adventure opens a visible map and proves movement plus encounter entry."
                    },
                    {
                      "title": "RPG Step 3: BattleScene creation and validation",
                      "description": "Validate one dedicated battle scene with readable action resolution and terminal settlement.",
                      "acceptanceHint": "Pass only when one BattleScene run reaches a readable settlement."
                    },
                    {
                      "title": "RPG Step 4: main prototype scene and scene switching validation",
                      "description": "Check the main prototype scene routes menu, map, battle, and return flow without hiding state transitions.",
                      "acceptanceHint": "Pass only when the main prototype scene can switch between menu, map, battle, and return flow."
                    },
                    {
                      "title": "RPG Step 5: reward loop and return-to-map validation",
                      "description": "Prove the reward 3-choice step changes visible state and returns the player to the active map loop.",
                      "acceptanceHint": "Pass only when reward choice, visible state change, and return-to-map all work."
                    },
                    {
                      "title": "RPG Final Step: full playable prototype acceptance",
                      "description": "Run final acceptance across map, battle, reward return, navigation, and contract-specific runtime proof.",
                      "acceptanceHint": "Pass only when the full prototype, Start Adventure visible-map validation, and contract-specific runtime proof all pass."
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
