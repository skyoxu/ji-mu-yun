using FluentAssertions;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Prototypes;
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
        result.Summary.Should().Contain("不适合直接执行");
        result.Summary.Should().NotContain("可以用");
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
        var codex = new SuccessfulRpgPlanCodexClient();
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, codex);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Please complete the first full playable loop: stable movement, visible encounter trigger, one battle, reward 3 choices, then return to the map.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().NotBeNullOrWhiteSpace();
        codex.LastGoalPlanPrompt.Should().Contain("default to Chinese");

        var latest = await service.GetLatestAsync(accountId, projectId);
        latest.Should().NotBeNull();
        latest!.LatestEvaluation.Should().NotBeNull();
        latest.LatestEvaluation!.Decision.Should().Be(result.LatestEvaluation.Decision);
    }

    [Fact]
    public async Task CreateAsync_ShouldRequireCustomRoute_WhenGenericLoopRequestIsTooBroad()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "????");
        var service = new PrototypeIterationPlanService(store);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "???????????????????Boss?????????????????????????????????????????",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Summary.Should().NotBeNullOrWhiteSpace();
        result.Goals.Should().NotBeEmpty();
    }

    [Fact]
    public async Task CreateAsync_ShouldSplitGenericLoopActionListIntoSmallGoals()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "模拟经营");
        var service = new PrototypeIterationPlanService(store);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "请继续把当前原型补成一个可反复试玩的最小闭环：围绕“采购、尝试制作、销售、盈利、继续采购、升级产品。”补齐关键反馈、状态切换和完成判定。完成后先验证“玩家能采购原材料。”是否真正成立。",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(5);
        result.Goals.Select(goal => goal.Title).Should().ContainInOrder(
            "任务 1：验证玩家能采购",
            "任务 2：补通制作反馈",
            "任务 3：补通销售反馈",
            "任务 4：补通盈利反馈",
            "最终任务：完整可玩原型验收");
        result.Goals[0].Description.Should().Contain("只处理“采购”这个最小动作");
        result.Goals[0].Description.Should().NotContain("可反复试玩的最小闭环");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().Be("ready_to_execute", result.LatestEvaluation.Reason);
    }

    [Fact]
    public async Task CreateAsync_ShouldNotSelectBattleCapabilities_WhenRpgRequestHasNoCombatSemantics()
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
                "Create a cozy town JRPG prototype where the hero wakes up, walks through a village, talks to an elder, finds a lost keepsake, and updates the objective.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().Be("ready_to_execute", result.LatestEvaluation.Reason);
        result.Goals.Select(goal => goal.Title).Should().ContainInOrder(
            "JRPG 首轮闭环：开局语境与玩家目标",
            "JRPG 首轮闭环：地图导航与稳定操控",
            "JRPG 首轮闭环：交互与发现节点",
            "JRPG 首轮闭环：任务或剧情推进",
            "JRPG 首轮闭环：最终首轮闭环验收");
        result.Goals.Select(goal => goal.Title).Should().NotContain("JRPG 首轮闭环：冲突入口触发");
        result.Goals.Select(goal => goal.Title).Should().NotContain("JRPG 首轮闭环：战斗或挑战结算");
        result.Goals.Select(goal => goal.Description + " " + goal.AcceptanceHint)
            .Should()
            .NotContain(text => text.Contains("BattleScene", StringComparison.OrdinalIgnoreCase));
        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateJson = new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project!);
        using var state = JsonDocument.Parse(stateJson);
        var selectedCapabilities = state.RootElement.GetProperty("selected_capabilities").EnumerateArray()
            .Select(item => item.GetString())
            .ToArray();
        selectedCapabilities.Should().Contain([
            "opening_context",
            "field_navigation",
            "interaction_discovery",
            "quest_or_story_progress",
            "final_first_loop_acceptance"
        ]);
        selectedCapabilities.Should().NotContain("conflict_entry");
        selectedCapabilities.Should().NotContain("battle_or_challenge_resolution");
    }

    [Fact]
    public async Task CreateAsync_ShouldIgnoreHistoricalPrototypeSummary_WhenSelectingRpgBattleCapabilities()
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
                "completed_through_day": 7,
                "completion_summary": "Template summary mentions BattleScene, enemy encounter, reward choice, RewardOptions.Count, and return to the map."
              }
            }
            """);
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Create a cozy town JRPG prototype where the hero wakes up, walks through a village, talks to an elder, finds a lost keepsake, updates the objective, and continues exploring.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        var stateJson = new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project);
        using var state = JsonDocument.Parse(stateJson);
        var selectedCapabilities = state.RootElement.GetProperty("selected_capabilities").EnumerateArray()
            .Select(item => item.GetString())
            .ToArray();
        selectedCapabilities.Should().NotContain("conflict_entry");
        selectedCapabilities.Should().NotContain("battle_or_challenge_resolution");
        selectedCapabilities.Should().NotContain("growth_feedback");
    }

    [Fact]
    public async Task CreateAsync_ShouldIgnoreHistoricalPrototypeSummary_WhenSelectingRpgNonBattleCapabilities()
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
                "completed_through_day": 7,
                "completion_summary": "Prior prototype summary mentions NPC dialogue, quest story progress, return-to-map continuation, and repeated loop closure."
              }
            }
            """);
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Create a JRPG prototype where Start Adventure opens a visible map and the player can move stably.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        var stateJson = new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project);
        using var state = JsonDocument.Parse(stateJson);
        var selectedCapabilities = state.RootElement.GetProperty("selected_capabilities").EnumerateArray()
            .Select(item => item.GetString())
            .ToArray();
        selectedCapabilities.Should().Contain("opening_context");
        selectedCapabilities.Should().Contain("field_navigation");
        selectedCapabilities.Should().Contain("final_first_loop_acceptance");
        selectedCapabilities.Should().NotContain("interaction_discovery");
        selectedCapabilities.Should().NotContain("quest_or_story_progress");
        selectedCapabilities.Should().NotContain("return_or_continue_loop");
    }

    [Fact]
    public async Task CreateAsync_ShouldIgnoreRouteProfileMetadata_WhenSelectingRpgBattleCapabilities()
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
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Create a cozy town JRPG prototype where the hero wakes up, walks through a village, talks to an elder, finds a lost keepsake, updates the objective, and continues exploring.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        var stateJson = new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project!);
        using var state = JsonDocument.Parse(stateJson);
        var selectedCapabilities = state.RootElement.GetProperty("selected_capabilities").EnumerateArray()
            .Select(item => item.GetString())
            .ToArray();
        selectedCapabilities.Should().NotContain("conflict_entry");
        selectedCapabilities.Should().NotContain("battle_or_challenge_resolution");
        selectedCapabilities.Should().NotContain("growth_feedback");
    }

    [Fact]
    public async Task CreateAsync_ShouldRespectNegatedCombatAndRewardSemantics_WhenSelectingRpgCapabilities()
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
                "Create a JRPG village errand with no combat, no enemy encounter, and without reward choices. The player should start adventure, walk through town, talk to an elder, update the objective, and continue exploring.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().Be("ready_to_execute");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateJson = new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project!);
        using var state = JsonDocument.Parse(stateJson);
        var selectedCapabilities = state.RootElement.GetProperty("selected_capabilities").EnumerateArray()
            .Select(item => item.GetString())
            .ToArray();
        selectedCapabilities.Should().Contain([
            "opening_context",
            "field_navigation",
            "interaction_discovery",
            "quest_or_story_progress",
            "return_or_continue_loop",
            "final_first_loop_acceptance"
        ]);
        selectedCapabilities.Should().NotContain("conflict_entry");
        selectedCapabilities.Should().NotContain("battle_or_challenge_resolution");
        selectedCapabilities.Should().NotContain("growth_feedback");
    }

    [Fact]
    public async Task CreateAsync_ShouldSelectBattleCapabilities_WhenRpgRequestMentionsCombat()
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
                "Create a JRPG first loop with field movement, a visible enemy encounter, one battle, HP feedback, reward choice, and return to the map.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：冲突入口触发");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：战斗或挑战结算");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：成长、奖励或后果反馈");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：返回或继续循环");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateJson = new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project!);
        using var state = JsonDocument.Parse(stateJson);
        state.RootElement.GetProperty("selected_capabilities").EnumerateArray()
            .Select(item => item.GetString())
            .Should()
            .Contain([
                "conflict_entry",
                "battle_or_challenge_resolution",
                "growth_feedback",
                "return_or_continue_loop"
            ]);
    }

    [Fact]
    public async Task CreateAsync_ShouldSelectRewardCapability_WhenRpgRequestMentionsXpWithPunctuation()
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
                "Create a JRPG training route with field movement, a visible lesson completion, gain XP, then return to the map.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateJson = new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project!);
        using var state = JsonDocument.Parse(stateJson);
        state.RootElement.GetProperty("selected_capabilities").EnumerateArray()
            .Select(item => item.GetString())
            .Should()
            .Contain("growth_feedback");
    }

    [Fact]
    public async Task CreateAsync_ShouldUseRequestedModelForStructuredPlanningCalls()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var codex = new SuccessfulRpgPlanCodexClient();
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, codex);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Please complete the first full playable loop: stable movement, visible encounter trigger, one battle, reward 3 choices, then return to the map.",
                "completion_suggestion",
                Model: "gpt-5.5"));

        result.Status.Should().Be("ready");
        codex.Models.Should().NotBeEmpty();
        codex.Models.Should().OnlyContain(model => model == "gpt-5.5");
        codex.LastGoalPlanPrompt.Should().Contain("Project execution guide");
        codex.LastGoalPlanPrompt.Should().Contain("Route Recovery Protocol");
        codex.LastGoalPlanPrompt.Should().Contain("Do not use AGENTS.md as hosted game-project recovery memory.");
        result.PlanningAnalysis!.StageTelemetry.Should().NotBeNullOrEmpty();
        result.PlanningAnalysis!.StageTelemetry!.Should().Contain(stage => stage.Stage == "goal-plan" && stage.Model == "gpt-5.5");

        var project = await store.GetProjectSnapshotAsync(projectId);
        var stateJson = new PrototypeRouteStateWriter().ReadLatestIterationPlanState(project!);
        using var state = JsonDocument.Parse(stateJson);
        var observability = state.RootElement.GetProperty("llm_observability");
        observability.GetProperty("schema").GetString().Should().Be("phase-a.iteration-plan.observability.v1");
        observability.GetProperty("totalEstimatedPromptTokens").GetInt32().Should().BeGreaterThan(0);
        observability.GetProperty("stages").EnumerateArray()
            .Should()
            .Contain(stage => stage.GetProperty("stage").GetString() == "goal-plan" &&
                stage.GetProperty("model").GetString() == "gpt-5.5");
    }


    [Fact]
    public async Task CreateAsync_ShouldUseTxtAttachmentsForPromptOnly()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var codex = new SuccessfulRpgPlanCodexClient();
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, codex);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Plan the next RPG loop improvement.",
                "manual_feedback",
                [new TextAttachment("notes.txt", "Important boss design reference.")]));

        result.Status.Should().Be("ready");
        codex.LastPlanningAnalysisPrompt.Should().BeNull();
        codex.LastGoalPlanPrompt.Should().Contain("Prototype Chapter 3 Lite semantics");
        codex.LastGoalPlanPrompt.Should().Contain("formal acceptance files");
        codex.LastGoalPlanPrompt.Should().Contain("older stable battle-route coverage");
        codex.LastGoalPlanPrompt.Should().Contain("Only omit BattleScene");
        codex.LastGoalPlanPrompt.Should().Contain("notes.txt");
        codex.LastGoalPlanPrompt.Should().Contain("Important boss design reference.");

        var latest = await store.GetLatestProjectIterationSessionAsync(projectId);
        latest.Should().NotBeNull();
        latest!.Session.SourceMessage.Should().Be("Plan the next RPG loop improvement.");
        latest.Session.SourceMessage.Should().NotContain("Important boss design reference.");
    }

    [Fact]
    public async Task CreateAsync_ShouldInjectBmadRpgDesignTemplateAsSemanticGuidance()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        WriteBmadRpgDesignTemplate(repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var codex = new SuccessfulRpgPlanCodexClient();
        var service = new PrototypeIterationPlanService(
            store,
            new PrototypeRouteStateWriter(),
            null,
            codex,
            null,
            null,
            new BmadGameTypeDesignCatalog(options));

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Plan the next JRPG first loop improvement.",
                "manual_feedback"));

        result.Status.Should().Be("ready");
        codex.LastPlanningAnalysisPrompt.Should().BeNull();
        codex.LastGoalPlanPrompt.Should().Contain("BMAD/GDS game-type design template summary");
        codex.LastGoalPlanPrompt.Should().Contain("semantic hints only");
        codex.LastGoalPlanPrompt.Should().Contain("do not turn the whole GDD template into iteration goals");
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
        result.Goals[4].Title.Should().Contain("最终任务");
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
        result.Goals[4].Title.Should().Contain("最终任务");
    }

    [Fact]
    public async Task CreateAsync_ShouldRejectGenericPlan_WhenDetectedCoreLoopNeedsCustomRoute()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Diablo");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "请继续把当前原型补成一个可反复试玩的最小闭环：围绕杀怪、掉装备、金币、获得经验升级、穿戴装备、购买药水、营地地图、野外地图、挑战Boss、随机装备词缀和剧情任务完成 10-15 分钟原型。",
                "completion_suggestion"));

        result.Status.Should().Be("custom_route_required");
        result.Goals.Should().BeEmpty();
        result.Summary.Should().Contain("联系管理员");
    }

    [Fact]
    public async Task CreateAsync_ShouldTrimGenericLootCombatPlan_ToMinimumLoopOnly()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Diablo");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "围绕杀怪 -> 掉装备或金币 -> 获得经验升级 -> 变强 -> 继续下一场战斗，补齐关键反馈。",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCountGreaterThanOrEqualTo(4);
        var planText = string.Join(" ", result.Goals.Select(goal => string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint)));
        planText.Should().Contain("击败一个普通敌人");
        planText.Should().Contain("展示玩家状态变化");
        planText.Should().NotContain("Boss");
        planText.Should().NotContain("完整商店");
        planText.Should().NotContain("多地图");
    }

    [Fact]
    public async Task CreateAsync_ShouldAutoEvaluateGenericMinimumLoopPlanAsReady()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Diablo");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "围绕杀怪 -> 掉装备或金币 -> 获得经验升级 -> 变强 -> 继续下一场战斗，补齐关键反馈。",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().Be("ready_to_execute");

        var latest = await service.GetLatestAsync(accountId, projectId);
        latest.Should().NotBeNull();
        latest!.LatestEvaluation.Should().NotBeNull();
        latest.LatestEvaluation!.Decision.Should().Be("ready_to_execute");
    }

    [Fact]
    public async Task CreateAsync_ShouldNotLeakTrimmedScopeIntoGenericFinalAcceptance()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Diablo");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "围绕杀怪、掉落金币、获得经验升级、挑战Boss和购买药水，补齐最小循环反馈。",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        var finalGoal = result.Goals.Should().Contain(goal => goal.Title.Contains("最终任务", StringComparison.Ordinal)).Subject;
        string.Join(" ", finalGoal.Title, finalGoal.Description, finalGoal.AcceptanceHint).Should()
            .Contain("最小闭环")
            .And.NotContain("Boss")
            .And.NotContain("购买药水");
    }

    [Fact]
    public async Task CreateAsync_ShouldNotRejectSmallGenericRequest_BecauseHistoricalContextWasLarge()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Diablo");
        var project = await store.GetProjectSnapshotAsync(projectId);
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
                "completed_through_day": 7,
                "completion_summary": "当前原型包含杀怪、掉装备、金币、经验升级、穿戴装备、购买药水、营地地图、野外地图、挑战Boss、随机装备词缀和剧情任务。"
              }
            }
            """);
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "只补杀怪后获得金币的反馈。",
                "manual_feedback"));

        result.Status.Should().Be("ready");
        result.Summary.Should().NotContain("联系管理员");
        result.Goals.Should().NotBeEmpty();
    }

    [Fact]
    public async Task CreateAsync_ShouldPreserveNumberedGenericLootCombatPlan()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Diablo");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                """
                1. 只补杀怪后的金币掉落反馈
                2. 只补经验升级后的状态变化显示
                3. 只补继续下一场战斗的入口提示
                """,
                "manual_feedback"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(4);
        result.Goals[0].Description.Should().Be("只补杀怪后的金币掉落反馈");
        result.Goals[1].Description.Should().Be("只补经验升级后的状态变化显示");
        result.Goals[2].Description.Should().Be("只补继续下一场战斗的入口提示");
        result.Goals[3].Title.Should().Contain("最终任务");
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
        var codex = new SuccessfulRpgPlanCodexClient();
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, codex);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Improve the first playable loop: movement, encounter, battle, reward, and return to the map.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCountGreaterThanOrEqualTo(4);
        result.Goals[0].Title.Should().Be("JRPG 首轮闭环：开局语境与玩家目标");
        result.Goals[1].Title.Should().Be("JRPG 首轮闭环：地图导航与稳定操控");
        string.Join(" ", result.Goals[1].Title, result.Goals[1].Description, result.Goals[1].AcceptanceHint)
            .Should()
            .Contain("Start Adventure")
            .And.Contain("playable field")
            .And.Contain("movement")
            .And.Contain("asset")
            .And.NotContain("encounter entry")
            .And.NotContain("BattleScene")
            .And.NotContain("full playable")
            .And.NotContain("scene switching");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：成长、奖励或后果反馈");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：战斗或挑战结算");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：成长、奖励或后果反馈");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：返回或继续循环");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：战斗或挑战结算");
        result.Goals.Select(goal => goal.Title).Should().Contain(title => title.Contains("\u5956\u52b1", StringComparison.OrdinalIgnoreCase));
        result.Goals.Last().Title.Should().Contain("最终首轮闭环验收");
        result.Goals.Last().AcceptanceHint.Should().Contain("端到端游玩");
        result.Goals.Last().AcceptanceHint.Should().Contain("project-specific contract fields");
    }

    [Fact]
    public async Task CreateAsync_ShouldUseSurvivorsLikeFirstLoopGoals_WhenProjectIsVampireSurvivorsLike()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Vampire Survivors-like");
        var service = new PrototypeIterationPlanService(store);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Build a Vampire Survivors-like first loop with arena movement, enemy waves, auto attack, pickups, level-up choices, escalation, and restart.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(10);
        result.Goals[0].Title.Should().Be("Vampire Survivors-like First Loop: run start and survival objective");
        result.Goals[1].Title.Should().Be("Vampire Survivors-like First Loop: arena movement and camera readability");
        result.Goals[2].Title.Should().Be("Vampire Survivors-like First Loop: enemy spawn pressure curve");
        result.Goals[3].Title.Should().Be("Vampire Survivors-like First Loop: auto-attack or core weapon loop");
        result.Goals[4].Title.Should().Be("Vampire Survivors-like First Loop: hit, damage, health, and death feedback");
        result.Goals[5].Title.Should().Be("Vampire Survivors-like First Loop: pickup and resource collection");
        result.Goals[6].Title.Should().Be("Vampire Survivors-like First Loop: level-up choice or power selection");
        result.Goals[7].Title.Should().Be("Vampire Survivors-like First Loop: build growth and power fantasy feedback");
        result.Goals[8].Title.Should().Be("Vampire Survivors-like First Loop: escalation event or mini-milestone");
        result.Goals[9].Title.Should().Be("Vampire Survivors-like First Loop: run end, summary, and restart loop");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().Be("ready_to_execute");
    }

    [Fact]
    public async Task CreateAsync_ShouldUseDeckbuilderFirstLoopGoals_WhenProjectIsDeckbuilder()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Roguelike Deckbuilder");
        var service = new PrototypeIterationPlanService(store);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Build a card-building first loop with readable starter deck, energy, enemy intent, play cards, draw/discard, win combat, choose a reward, and mutate the deck.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(10);
        result.Goals.Select(goal => goal.Title).Should().ContainInOrder(
            "Deckbuilder First Loop: run context and objective",
            "Deckbuilder First Loop: starter deck readability",
            "Deckbuilder First Loop: resource and turn rules",
            "Deckbuilder First Loop: enemy intent or pressure source",
            "Deckbuilder First Loop: card play resolution feedback",
            "Deckbuilder First Loop: deck cycle and hand flow",
            "Deckbuilder First Loop: combat win/fail resolution",
            "Deckbuilder First Loop: post-combat card draft or reward",
            "Deckbuilder First Loop: deck mutation feedback",
            "Deckbuilder First Loop: final deckbuilder first-loop acceptance");
        result.Goals.Select(goal => goal.Title).Should().NotContain(title => title.Contains("map or route choice", StringComparison.OrdinalIgnoreCase));
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().Be("ready_to_execute", result.LatestEvaluation.Reason);
    }

    [Fact]
    public async Task CreateAsync_ShouldIncludeDeckbuilderRouteChoice_WhenSourceRequestsRoutes()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "Slay the Spire-like deckbuilder");
        var service = new PrototypeIterationPlanService(store);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Build a deckbuilder run loop with a route map, event nodes, shop nodes, elites, combat, rewards, and deck mutation.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCount(11);
        result.Goals.Select(goal => goal.Title).Should().Contain("Deckbuilder First Loop: map or route choice");
        result.Goals[^1].Title.Should().Be("Deckbuilder First Loop: final deckbuilder first-loop acceptance");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().Be("ready_to_execute", result.LatestEvaluation.Reason);
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
        result.Goals.Should().HaveCountGreaterThanOrEqualTo(4);
        result.Goals[0].Title.Should().Be("JRPG 首轮闭环：开局语境与玩家目标");
        result.Goals[1].Title.Should().Be("JRPG 首轮闭环：地图导航与稳定操控");
        result.Goals.Select(goal => goal.Title).Should().NotContain("JRPG 首轮闭环：成长、奖励或后果反馈");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：返回或继续循环");
        result.Goals[0].Title.Should().NotContain("对齐原型合同");
        result.Goals.Last().Title.Should().Contain("最终首轮闭环验收");
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
            "Regenerate the RPG iteration plan: first priority must validate Start Adventure to visible MapScene and stable movement, then validate encounter trigger as step 2 before battle/reward polish."));
        await store.UpdateProjectIterationSessionStatusAsync(previous.SessionId, "ready", 0, "needs refinement", evaluationJson);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Please continue refining the current RPG prototype after the first successful playable loop.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCountGreaterThanOrEqualTo(4);
        result.Goals[0].Title.Should().Be("JRPG 首轮闭环：开局语境与玩家目标");
        result.Goals[1].Title.Should().Be("JRPG 首轮闭环：地图导航与稳定操控");
        result.Goals[1].Description.Should().Contain("Start Adventure");
        string.Join(" ", result.Goals[1].Description, result.Goals[1].AcceptanceHint).Should().Match(text => text.Contains("playable field", StringComparison.OrdinalIgnoreCase) || text.Contains("visible MapScene", StringComparison.OrdinalIgnoreCase));
        result.Goals[1].Description.Should().NotContain("encounter entry");
        result.Goals[1].AcceptanceHint.Should().Match(text =>
            text.Contains("stable movement", StringComparison.OrdinalIgnoreCase) ||
            text.Contains("移动稳定", StringComparison.OrdinalIgnoreCase));
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：冲突入口触发");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：战斗或挑战结算");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：成长、奖励或后果反馈");
        result.Goals[0].Title.ToLowerInvariant().Should().NotContain("foundation asset");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().NotBeNullOrWhiteSpace();
    }

    [Fact]
    public async Task CreateAsync_ShouldUseRegenerationGuidanceNegation_WhenSelectingRpgCapabilities()
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
                new ProjectIterationGoalCreateCommand(1, "JRPG 首轮闭环：冲突入口触发", "Validate encounter trigger.", "Encounter trigger passes."),
                new ProjectIterationGoalCreateCommand(2, "JRPG 首轮闭环：成长、奖励或后果反馈", "Validate reward.", "Reward passes.")
            ]);
        var evaluationJson = JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
            "should_refine_plan",
            "The plan must be regenerated without combat.",
            "The current request is a peaceful village route, so combat and rewards must be removed.",
            "Regenerate without combat and reward choices.",
            "Regenerate the RPG iteration plan with no combat, no enemy encounter, and without reward choices; keep only exploration, dialogue, objective progress, continuation, and final acceptance."));
        await store.UpdateProjectIterationSessionStatusAsync(previous.SessionId, "ready", 0, "needs refinement", evaluationJson);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Please continue refining the current RPG prototype after the first successful playable loop.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        var latestProject = await store.GetProjectSnapshotAsync(projectId);
        var stateJson = new PrototypeRouteStateWriter().ReadLatestIterationPlanState(latestProject!);
        using var state = JsonDocument.Parse(stateJson);
        var selectedCapabilities = state.RootElement.GetProperty("selected_capabilities").EnumerateArray()
            .Select(item => item.GetString())
            .ToArray();
        selectedCapabilities.Should().Contain("field_navigation");
        selectedCapabilities.Should().Contain("final_first_loop_acceptance");
        selectedCapabilities.Should().NotContain("conflict_entry");
        selectedCapabilities.Should().NotContain("battle_or_challenge_resolution");
        selectedCapabilities.Should().NotContain("growth_feedback");
    }

    [Fact]
    public async Task CreateAsync_ShouldNotUseLocalCombatNegationAsGlobal_WhenRegenerationGuidanceMentionsLaterBattle()
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
                new ProjectIterationGoalCreateCommand(1, "JRPG 首轮闭环：地图导航与稳定操控", "Validate map movement.", "Movement passes.")
            ]);
        var evaluationJson = JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
            "should_refine_plan",
            "The plan must separate navigation and battle.",
            "Navigation should have no combat before the boss battle step.",
            "Regenerate with navigation first, then boss battle.",
            "Regenerate the RPG iteration plan with no combat before boss battle; keep the later boss battle and reward choice steps."));
        await store.UpdateProjectIterationSessionStatusAsync(previous.SessionId, "ready", 0, "needs refinement", evaluationJson);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(
                "Please continue refining the current RPG prototype after the first successful playable loop.",
                "completion_suggestion"));

        result.Status.Should().Be("ready");
        var latestProject = await store.GetProjectSnapshotAsync(projectId);
        var stateJson = new PrototypeRouteStateWriter().ReadLatestIterationPlanState(latestProject!);
        using var state = JsonDocument.Parse(stateJson);
        var selectedCapabilities = state.RootElement.GetProperty("selected_capabilities").EnumerateArray()
            .Select(item => item.GetString())
            .ToArray();
        selectedCapabilities.Should().Contain("conflict_entry");
        selectedCapabilities.Should().Contain("battle_or_challenge_resolution");
        selectedCapabilities.Should().Contain("growth_feedback");
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
        result.Goals.Should().HaveCountGreaterThanOrEqualTo(4);
        result.Goals[0].Title.Should().Be("JRPG 首轮闭环：开局语境与玩家目标");
        result.Goals[1].Title.Should().Be("JRPG 首轮闭环：地图导航与稳定操控");
        string.Join(" ", result.Goals[1].Title, result.Goals[1].Description, result.Goals[1].AcceptanceHint)
            .Should()
            .Contain("Start Adventure")
            .And.Contain("visible MapScene")
            .And.Contain("movement")
            .And.NotContain("encounter entry")
            .And.NotContain("BattleScene")
            .And.NotContain("reward")
            .And.NotContain("final acceptance");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().NotBeNullOrWhiteSpace();
        result.LatestEvaluation.Reason.Should().Contain("saved final goals already cover the JRPG first-loop capability graph");
        result.LatestEvaluation.SuggestedPromptForRegeneration.Should().BeNull();

        var latest = await service.GetLatestAsync(accountId, projectId);
        latest.Should().NotBeNull();
        latest!.LatestEvaluation.Should().NotBeNull();
        latest.LatestEvaluation!.Decision.Should().Be("ready_to_execute");
    }

    [Fact]
    public async Task CreateAsync_ShouldUseDeterministicRpgSevenStepRegeneration_WhenPreviousEvaluationRequestsStrictRoute()
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
        var codex = new StrictRouteRegenerationCodexClient();
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, codex);
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
                new ProjectIterationGoalCreateCommand(1, "RPG Step 1: Start Adventure to visible MapScene, stable movement, and encounter entry", "Old broad first step.", "Old broad acceptance."),
                new ProjectIterationGoalCreateCommand(2, "RPG Step 2: BattleScene loop validation", "Old battle step.", "Old battle acceptance.")
            ]);
        const string strictPrompt = "Regenerate the RPG iteration plan as JRPG first-loop capability steps: Start Adventure to visible MapScene with stable movement first, encounter trigger and guaranteed encounter second, BattleScene visualization and settlement third, reward/growth feedback, reward application and return-to-map fifth, win/fail visibility sixth, and final final first-loop acceptance.";
        var evaluationJson = JsonSerializer.Serialize(new PrototypeIterationPlanEvaluationResult(
            "should_refine_plan",
            "The plan must be regenerated.",
            "The saved plan is still the old broad RPG route.",
            "Regenerate as JRPG first-loop capability steps.",
            strictPrompt));
        await store.UpdateProjectIterationSessionStatusAsync(previous.SessionId, "ready", 0, "needs refinement", evaluationJson);

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest(strictPrompt, "completion_suggestion"));

        result.Status.Should().Be("ready");
        result.Goals.Should().HaveCountGreaterThanOrEqualTo(4);
        result.Goals[0].Title.Should().Be("JRPG 首轮闭环：开局语境与玩家目标");
        result.Goals[1].Title.Should().Be("JRPG 首轮闭环：地图导航与稳定操控");
        result.Goals[1].Description.Should().Contain("Start Adventure");
        result.Goals[1].Description.Should().NotContain("encounter entry");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：冲突入口触发");
        codex.GoalPlanCallCount.Should().Be(0);
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().Be("ready_to_execute");
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
        result.Goals.Should().HaveCountGreaterThanOrEqualTo(5);
        result.Goals[0].Title.Should().Be("JRPG 首轮闭环：开局语境与玩家目标");
        result.Goals[1].Title.Should().Be("JRPG 首轮闭环：地图导航与稳定操控");
        string.Join(" ", result.Goals[1].Description, result.Goals[1].AcceptanceHint).Should().Match(text => text.Contains("playable field", StringComparison.OrdinalIgnoreCase) || text.Contains("visible MapScene", StringComparison.OrdinalIgnoreCase));
        result.Goals[1].AcceptanceHint.Should().Contain("asset");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG 首轮闭环：战斗或挑战结算");
        result.Goals[^1].AcceptanceHint.Should().Contain("project-specific contract fields");
        result.Summary.Should().Contain("model_plan_degraded=scaffold_fallback");
        var latest = await store.GetLatestProjectIterationSessionAsync(projectId);
        latest!.Session.LatestSummary.Should().Contain("model_plan_degraded=scaffold_fallback");
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
        result.Reason.Should().Contain("acceptance boundary mismatch");
        result.SuggestedAction.Should().Contain("JRPG first-loop capability profile");
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
            ValidRpgIterationGoalCommands());

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
        codex.LastPrompt.Should().Contain("Prototype Chapter 3 Lite / Chapter 6 Lite boundaries");
        codex.LastPrompt.Should().Contain("formal Chapter 3/6 task artifacts");
        codex.LastOptions.Should().NotBeNull();
        codex.LastOptions!.IgnoreRules.Should().BeTrue();
        codex.LastOptions.ReasoningEffort.Should().Be("minimal");
    }

    [Fact]
    public async Task EvaluateWithRunAsync_ShouldCreateVisibleEvaluationRun()
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
            ValidRpgIterationGoalCommands());

        var result = await service.EvaluateWithRunAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("failed", "failed", "", "done", null, null, null, "navigation failed", "system", "recommended", "MapScene is not visible after Start Adventure."));

        result.Status.Should().Be("succeeded");
        result.RunId.Should().NotBeNullOrWhiteSpace();
        result.Evaluation.Decision.Should().Be("should_refine_plan");
        var run = (await store.ListRunsForProjectAsync(projectId)).Should()
            .ContainSingle(item => item.RunId == result.RunId)
            .Subject;
        run.RunType.Should().Be("prototype-iteration-plan-evaluation");
        run.Status.Should().Be("succeeded");
        run.ProgressStep.Should().Be("succeeded");
        run.ProgressSubstep.Should().Be(result.Evaluation.Decision);
        run.StdoutText.Should().Contain("should_refine_plan");
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
            ValidRpgIterationGoalCommands());

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
                new ProjectIterationGoalCreateCommand(6, "JRPG 首轮闭环：最终首轮闭环验收", "Validate full playable prototype acceptance.", "Final acceptance passes with Start Adventure visible map and package readiness.")
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
            ValidRpgIterationGoalCommands(
                "Resolve the first RPG route blocker as the initial convergence step: Start Adventure opens a visible MapScene, shows runtime map/player assets, and proves stable controllable movement before encounter, battle, reward, or closure proof is mixed in. Keep this step tightly focused on map start and movement stability. Movement evidence is independent of encounter, battle, reward, or final acceptance behavior."));

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("ready_to_execute");
        result.Reason.Should().Contain("focused");
    }

    [Fact]
    public async Task EvaluateAsync_ShouldAllowNonCombatRpgPlan_WhenSourceNegatesEncounterAndRewards()
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
            "The saved goals intentionally keep this village route non-combat.",
            "Execute the next goal.",
            null));

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Create a JRPG village errand with no combat, no enemy encounter, and without reward choices. The route should cover Start Adventure, visible map movement, dialogue, objective progress, continuation, and final acceptance.",
            "Demo Game: non-combat village route.",
            [
                new ProjectIterationGoalCreateCommand(1, "JRPG 首轮闭环：地图导航与稳定操控", "Start Adventure opens a visible MapScene, proves stable movement, and keeps this step focused without encounter, battle, or reward work.", "Visible MapScene and stable movement pass."),
                new ProjectIterationGoalCreateCommand(2, "JRPG 首轮闭环：交互与发现节点", "Validate dialogue with the elder and discovery of the lost keepsake.", "Interaction and discovery pass."),
                new ProjectIterationGoalCreateCommand(3, "JRPG 首轮闭环：任务或剧情推进", "Validate objective update after returning the keepsake.", "Objective progress is visible."),
                new ProjectIterationGoalCreateCommand(4, "JRPG 首轮闭环：返回或继续循环", "Validate the next playable exploration state after the objective update.", "The player can continue exploring."),
                new ProjectIterationGoalCreateCommand(5, "JRPG 首轮闭环：最终首轮闭环验收", "Run final acceptance across Start Adventure visible map, interaction, objective progress, continuation, project contract, and package readiness.", "Final acceptance passes without combat or reward requirements.")
            ]);

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("ready_to_execute");
        result.Reason.Should().Contain("non-combat");
    }

    [Fact]
    public async Task EvaluateAsync_ShouldNotTreatItemizedChecklistAsRpgRewardRequirement()
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
            "The saved goals do not require reward flow.",
            "Execute the next goal.",
            null));

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Create a JRPG town walkthrough with an itemized checklist for validation notes, but no reward flow.",
            "Demo Game: town walkthrough checklist.",
            [
                new ProjectIterationGoalCreateCommand(1, "JRPG 首轮闭环：地图导航与稳定操控", "Start Adventure opens a visible MapScene, proves stable movement, and keeps this step focused before closure proof is mixed in.", "Visible MapScene and stable movement pass."),
                new ProjectIterationGoalCreateCommand(2, "JRPG 首轮闭环：交互与发现节点", "Review an itemized checklist of dialogue and inspectable-object validation notes.", "The checklist supports interaction validation."),
                new ProjectIterationGoalCreateCommand(3, "JRPG 首轮闭环：任务或剧情推进", "Validate story progress after the player talks to the elder.", "Story progress is visible."),
                new ProjectIterationGoalCreateCommand(4, "JRPG 首轮闭环：最终首轮闭环验收", "Run final acceptance across Start Adventure visible map, interaction, story progress, project contract, and package readiness.", "Final acceptance passes.")
            ]);

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("ready_to_execute");
        result.Reason.Should().Contain("reward flow");
    }

    [Fact]
    public async Task EvaluateAsync_ShouldFallbackToFilteredAnalysisEvidence_WhenSelectedCapabilitiesAreMissing()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var writer = new PrototypeRouteStateWriter();
        var service = new PrototypeIterationPlanService(store, writer, null, new RpgEvaluationCodexClient(
            "ready_to_execute",
            "The RPG plan can execute.",
            "The LLM would allow this, but the local route guard should catch missing battle and reward steps.",
            "Execute the next goal.",
            null));

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Improve the JRPG loop.",
            "Demo Game: legacy route state.",
            [
                new ProjectIterationGoalCreateCommand(1, "JRPG 首轮闭环：地图导航与稳定操控", "Start Adventure opens a visible MapScene and proves stable movement.", "Visible MapScene and stable movement pass."),
                new ProjectIterationGoalCreateCommand(2, "JRPG 首轮闭环：最终首轮闭环验收", "Run final acceptance across Start Adventure visible map and package readiness.", "Final acceptance passes.")
            ]);
        var project = await store.GetProjectSnapshotAsync(projectId);
        writer.WriteIterationPlanState(project!, new
        {
            planning_analysis = new
            {
                analysisSummary = "Legacy analysis uses actual evidence.",
                fieldCoverage = new[]
                {
                    new { field = "reward_loop", status = "partial", evidence = "The request needs a visible battle, reward choice, and return to the map.", missingReason = (string?)null }
                }
            }
        });

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("should_refine_plan");
        result.Reason.Should().Contain("battle or challenge resolution capability");
        result.Reason.Should().Contain("growth/reward feedback");
    }

    [Fact]
    public async Task EvaluateAsync_ShouldTreatEmptySelectedCapabilitiesAsMissingAndFallbackToSource()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var writer = new PrototypeRouteStateWriter();
        var service = new PrototypeIterationPlanService(store, writer, null, new RpgEvaluationCodexClient(
            "ready_to_execute",
            "The RPG plan can execute.",
            "The LLM would allow this, but the local route guard should catch missing battle and reward steps.",
            "Execute the next goal.",
            null));

        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Create a JRPG loop with a visible enemy encounter, one battle, XP reward, and return to the map.",
            "Demo Game: empty selected capabilities route state.",
            [
                new ProjectIterationGoalCreateCommand(1, "JRPG 首轮闭环：地图导航与稳定操控", "Start Adventure opens a visible MapScene and proves stable movement.", "Visible MapScene and stable movement pass."),
                new ProjectIterationGoalCreateCommand(2, "JRPG 首轮闭环：最终首轮闭环验收", "Run final acceptance across Start Adventure visible map and package readiness.", "Final acceptance passes.")
            ]);
        var project = await store.GetProjectSnapshotAsync(projectId);
        writer.WriteIterationPlanState(project!, new
        {
            session_id = session.SessionId,
            selected_capabilities = Array.Empty<string>(),
            planning_analysis = new
            {
                analysisSummary = "No selected capabilities were written.",
                fieldCoverage = Array.Empty<object>()
            }
        });

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("should_refine_plan");
        result.Reason.Should().Contain("battle or challenge resolution capability");
        result.Reason.Should().Contain("growth/reward feedback");
    }

    [Fact]
    public async Task EvaluateAsync_ShouldIgnoreSelectedCapabilities_WhenRouteStateSessionDoesNotMatch()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var writer = new PrototypeRouteStateWriter();
        var service = new PrototypeIterationPlanService(store, writer, null, new RpgEvaluationCodexClient(
            "ready_to_execute",
            "The RPG plan can execute.",
            "The stale selected capabilities would allow this if they were trusted.",
            "Execute the next goal.",
            null));

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Create a JRPG loop with a visible enemy encounter, one battle, XP reward, and return to the map.",
            "Demo Game: stale selected capabilities route state.",
            [
                new ProjectIterationGoalCreateCommand(1, "JRPG 首轮闭环：地图导航与稳定操控", "Start Adventure opens a visible MapScene and proves stable movement.", "Visible MapScene and stable movement pass."),
                new ProjectIterationGoalCreateCommand(2, "JRPG 首轮闭环：最终首轮闭环验收", "Run final acceptance across Start Adventure visible map and package readiness.", "Final acceptance passes.")
            ]);
        var project = await store.GetProjectSnapshotAsync(projectId);
        writer.WriteIterationPlanState(project!, new
        {
            session_id = "stale-session",
            selected_capabilities = new[] { "field_navigation", "final_first_loop_acceptance" },
            planning_analysis = new
            {
                analysisSummary = "Stale selected capabilities from a previous non-combat plan.",
                fieldCoverage = Array.Empty<object>()
            }
        });

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("should_refine_plan");
        result.Reason.Should().Contain("battle or challenge resolution capability");
        result.Reason.Should().Contain("growth/reward feedback");
    }

    [Fact]
    public async Task EvaluateAsync_ShouldIgnorePlanningAnalysis_WhenRouteStateSessionDoesNotMatch()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var writer = new PrototypeRouteStateWriter();
        var service = new PrototypeIterationPlanService(store, writer, null, new RpgEvaluationCodexClient(
            "ready_to_execute",
            "The RPG plan can execute.",
            "The current session is non-combat and stale route analysis must be ignored.",
            "Execute the next goal.",
            null));

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Create a JRPG village errand with no combat, no enemy encounter, and without reward choices.",
            "Demo Game: stale planning analysis route state.",
            [
                new ProjectIterationGoalCreateCommand(1, "JRPG 首轮闭环：地图导航与稳定操控", "Start Adventure opens a visible MapScene and proves stable movement.", "Visible MapScene and stable movement pass."),
                new ProjectIterationGoalCreateCommand(2, "JRPG 首轮闭环：交互与发现节点", "Validate dialogue with the elder.", "Interaction passes."),
                new ProjectIterationGoalCreateCommand(3, "JRPG 首轮闭环：最终首轮闭环验收", "Run final acceptance across Start Adventure visible map, interaction, project contract, and package readiness.", "Final acceptance passes without combat or reward requirements.")
            ]);
        var project = await store.GetProjectSnapshotAsync(projectId);
        writer.WriteIterationPlanState(project!, new
        {
            session_id = "stale-session",
            planning_analysis = new
            {
                analysisSummary = "Stale analysis from a combat route.",
                fieldCoverage = new[]
                {
                    new { field = "reward_loop", status = "partial", evidence = "The stale request needs BattleScene, reward choice, and return to the map.", missingReason = (string?)null }
                }
            }
        });

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("ready_to_execute");
        result.Reason.Should().Contain("stale route analysis must be ignored");
    }

    [Fact]
    public async Task EvaluateAsync_ShouldIgnoreAnalysisSummary_WhenInferringRpgBattleAndRewardNeeds()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var writer = new PrototypeRouteStateWriter();
        var service = new PrototypeIterationPlanService(store, writer, null, new RpgEvaluationCodexClient(
            "ready_to_execute",
            "The RPG plan can execute.",
            "The saved goals intentionally remain non-combat.",
            "Execute the next goal.",
            null));

        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Create a JRPG village errand with no combat, no enemy encounter, and without reward choices.",
            "Demo Game: noisy analysis summary.",
            [
                new ProjectIterationGoalCreateCommand(1, "JRPG 首轮闭环：地图导航与稳定操控", "Start Adventure opens a visible MapScene and proves stable movement.", "Visible MapScene and stable movement pass."),
                new ProjectIterationGoalCreateCommand(2, "JRPG 首轮闭环：交互与发现节点", "Validate dialogue with the elder.", "Interaction passes."),
                new ProjectIterationGoalCreateCommand(3, "JRPG 首轮闭环：最终首轮闭环验收", "Run final acceptance across Start Adventure visible map, interaction, project contract, and package readiness.", "Final acceptance passes without combat or reward requirements.")
            ]);
        var project = await store.GetProjectSnapshotAsync(projectId);
        writer.WriteIterationPlanState(project!, new
        {
            planning_analysis = new
            {
                analysisSummary = "Template summary says BattleScene and reward loop are missing.",
                fieldCoverage = Array.Empty<object>()
            }
        });

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("ready_to_execute");
        result.Reason.Should().Contain("non-combat");
    }

    [Fact]
    public async Task EvaluateAsync_ShouldTreatUnknownSelectedCapabilitiesAsMissingAndFallbackToSource()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var writer = new PrototypeRouteStateWriter();
        var service = new PrototypeIterationPlanService(store, writer, null, new RpgEvaluationCodexClient(
            "ready_to_execute",
            "The RPG plan can execute.",
            "Unknown selected capabilities should not suppress source-message semantics.",
            "Execute the next goal.",
            null));

        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Create a JRPG loop with a visible enemy encounter, one battle, XP reward, and return to the map.",
            "Demo Game: unknown selected capabilities route state.",
            [
                new ProjectIterationGoalCreateCommand(1, "JRPG 首轮闭环：地图导航与稳定操控", "Start Adventure opens a visible MapScene and proves stable movement.", "Visible MapScene and stable movement pass."),
                new ProjectIterationGoalCreateCommand(2, "JRPG 首轮闭环：最终首轮闭环验收", "Run final acceptance across Start Adventure visible map and package readiness.", "Final acceptance passes.")
            ]);
        var project = await store.GetProjectSnapshotAsync(projectId);
        writer.WriteIterationPlanState(project!, new
        {
            session_id = session.SessionId,
            selected_capabilities = new[] { "unknown_capability" },
            planning_analysis = new
            {
                analysisSummary = "Unknown selected capabilities were written.",
                fieldCoverage = Array.Empty<object>()
            }
        });

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("should_refine_plan");
        result.Reason.Should().Contain("battle or challenge resolution capability");
        result.Reason.Should().Contain("growth/reward feedback");
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
        var codex = new SuccessfulRpgPlanCodexClient();
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, codex);

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

        result.Decision.Should().NotBeNullOrWhiteSpace();
        codex.LastPrompt.Should().Contain("Project execution guide");
        codex.LastPrompt.Should().Contain("Route Recovery Protocol");
        codex.LastPrompt.Should().Contain("Do not use AGENTS.md as hosted game-project recovery memory.");
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
            ValidRpgIterationGoalCommands(
                stepSixDescription: "Show encounter rules and failure feedback, but omit explicit 15-battle victory wording."));

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
            ValidRpgIterationGoalCommands(
                stepTwoDescription: "Validate 10% encounter progress, guaranteed encounter within 10 steps, and movement-driven first encounter.",
                stepSixDescription: "Show and validate win after 15 battles, guaranteed encounter within 10 steps, and any battle loss means game loss."));

        var result = await service.EvaluateAsync(
            accountId,
            projectId,
            new PrototypeWorkflowProgress("succeeded", "succeeded", "", "done", null, null, null));

        result.Decision.Should().Be("ready_to_execute");
    }

    [Fact]
    public async Task CreateAsync_ShouldInjectExplicitRpgContractRulesIntoJrpgGoals()
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
                "rpg-explicit-rules-demo",
                "RPG Explicit Rules Demo",
                "rpg",
                "RPG",
                "Validate explicit battle rules.",
                "Explore a field, trigger danger, win after 15 battles, and lose if any battle is lost.",
                "Move on map, each movement increases encounter chance by 10%, guaranteed encounter within 10 steps, fight, grow, return.",
                ["Each next enemy gains +5 HP and +2 ATK."],
                "Each movement increases encounter chance by 10%; encounter is guaranteed within 10 steps.",
                "Move, trigger encounter, battle, track enemy scaling, return to map.",
                "Win after 15 battles; any battle loss means game loss.",
                true),
            "docs/prototypes/2026-06-15-rpg-explicit-rules-demo.md",
            "rpg-explicit-rules-demo");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SuccessfulRpgPlanCodexClient());

        var result = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest("Regenerate the RPG iteration plan as a JRPG first-loop capability plan.", "completion_suggestion"));

        result.Status.Should().Be("ready");
        var planText = string.Join(" ", result.Goals.Select(goal => string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint)));
        planText.Should().Contain("10%");
        planText.Should().Contain("10 steps");
        planText.Should().Contain("15 battles");
        planText.Should().Contain("any battle loss");
        planText.Should().Contain("+5 HP");
        planText.Should().Contain("+2 ATK");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().NotBe("should_refine_plan", result.LatestEvaluation.Reason);
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
        result.Goals[^1].AcceptanceHint.Should().Contain("project-specific contract fields");
    }

    [Fact]
    public async Task DeleteAsync_ShouldRemoveUnfinishedIterationPlansAndClearRouteState()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var writer = new PrototypeRouteStateWriter();
        var service = new PrototypeIterationPlanService(store, writer);
        var created = await service.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Add a small map polish step."));
        var project = await store.GetProjectSnapshotAsync(projectId);

        created.Status.Should().Be("ready");
        writer.ReadLatestIterationPlanState(project!).Should().NotBeNullOrWhiteSpace();

        var result = await service.DeleteAsync(accountId, projectId);

        result.Status.Should().Be("deleted");
        result.DeletedSessions.Should().BeGreaterThan(0);
        (await service.GetLatestAsync(accountId, projectId)).Should().BeNull();
        writer.ReadLatestIterationPlanState(project!).Should().BeEmpty();
    }

    [Fact]
    public async Task DeleteAsync_ShouldBlock_WhenIterationPlanIsComplete()
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
        await service.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Add a small map polish step."));
        var latest = await store.GetLatestProjectIterationSessionAsync(projectId);
        foreach (var goal in latest!.Goals)
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "completed", "done", DateTimeOffset.UtcNow.ToString("O"));
        }

        var result = await service.DeleteAsync(accountId, projectId);

        result.Status.Should().Be("blocked");
        (await service.GetLatestAsync(accountId, projectId)).Should().NotBeNull();
    }

    [Fact]
    public async Task DeleteSessionAsync_ShouldDeleteOnlySelectedIterationRound()
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
        var first = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest("Complete the first JRPG loop with movement, battle, reward, and return to map.", "completion_suggestion"));
        var firstDetails = await store.GetLatestProjectIterationSessionAsync(projectId);
        foreach (var goal in firstDetails!.Goals)
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "completed", "done", DateTimeOffset.UtcNow.ToString("O"));
        }
        await store.UpdateProjectIterationSessionStatusAsync(first.SessionId, "completed", firstDetails.Goals.Count, "First round completed.", null, DateTimeOffset.UtcNow.ToString("O"));
        var second = await service.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Second round: add a shop and stronger enemy.", "new_iteration_plan"));

        var result = await service.DeleteSessionAsync(accountId, projectId, second.SessionId);
        var rounds = await service.ListAsync(accountId, projectId);

        result.Status.Should().Be("deleted");
        result.DeletedSessions.Should().Be(1);
        rounds.Should().HaveCount(1);
        rounds[0].Session.SessionId.Should().Be(first.SessionId);
    }

    [Fact]
    public async Task CreateAsync_ShouldBlockUpdate_WhenIterationPlanHasStarted()
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
        var first = await service.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Add a small map polish step."));
        var latestBeforeUpdate = await store.GetLatestProjectIterationSessionAsync(projectId);
        await store.UpdateProjectIterationGoalStatusAsync(
            latestBeforeUpdate!.Goals[0].GoalId,
            "completed",
            "done",
            DateTimeOffset.UtcNow.ToString("O"));

        var second = await service.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Regenerate the remaining plan."));
        var latestAfterUpdate = await service.GetLatestAsync(accountId, projectId);

        first.Status.Should().Be("ready");
        second.Status.Should().Be("iteration_plan_update_blocked");
        second.Goals.Should().BeEmpty();
        latestAfterUpdate!.Session.SessionId.Should().Be(first.SessionId);
        latestAfterUpdate.Goals.Should().Contain(goal => goal.Status == "completed");
    }

    [Fact]
    public async Task CreateAsync_ShouldCreateNewIterationPlan_WhenPreviousPlanIsComplete()
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
        var first = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest("Complete the first JRPG loop with movement, battle, reward, and return to map.", "completion_suggestion"));
        var firstDetails = await store.GetLatestProjectIterationSessionAsync(projectId);
        foreach (var goal in firstDetails!.Goals)
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "completed", "done", DateTimeOffset.UtcNow.ToString("O"));
        }
        await store.UpdateProjectIterationSessionStatusAsync(
            first.SessionId,
            "completed",
            firstDetails.Goals.Count,
            "First round completed.",
            null,
            DateTimeOffset.UtcNow.ToString("O"));

        var second = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest("第二轮目标：增加村庄支线、商店补给和一次更强敌人挑战。", "new_iteration_plan"));
        var latest = await service.GetLatestAsync(accountId, projectId);

        second.Status.Should().Be("ready");
        second.SessionId.Should().NotBe(first.SessionId);
        latest!.Session.SessionId.Should().Be(second.SessionId);
        latest.Session.SourceKind.Should().Be("new_iteration_plan");
        latest.Session.SourceMessage.Should().Be("第二轮目标：增加村庄支线、商店补给和一次更强敌人挑战。");
        latest.Goals.Should().NotBeEmpty();
    }

    [Fact]
    public async Task CreateAsync_ShouldCreateNewIterationPlanWithScaffoldFallback_WhenRpgGoalJsonHasRecoverableTitleDamage()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new DamagedRpgTitleCodexClient());
        var first = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest("Complete the first JRPG loop with movement, battle, reward, and return to map.", "completion_suggestion"));
        var firstDetails = await store.GetLatestProjectIterationSessionAsync(projectId);
        foreach (var goal in firstDetails!.Goals)
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "completed", "done", DateTimeOffset.UtcNow.ToString("O"));
        }
        await store.UpdateProjectIterationSessionStatusAsync(
            first.SessionId,
            "completed",
            firstDetails.Goals.Count,
            "First round completed.",
            null,
            DateTimeOffset.UtcNow.ToString("O"));

        var second = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest("现在每次战斗，敌人的数量为随机1-3名，依旧是回合制自动战斗。", "new_iteration_plan"));
        var rounds = await service.ListAsync(accountId, projectId);

        second.Status.Should().Be("ready");
        second.SessionId.Should().NotBe(first.SessionId);
        second.Summary.Should().Contain("model_plan_degraded=scaffold_fallback");
        rounds.Should().HaveCount(2);
        rounds[1].Session.SessionId.Should().Be(second.SessionId);
        rounds[1].Session.SourceKind.Should().Be("new_iteration_plan");
    }

    [Fact]
    public async Task CreateAsync_ShouldCreateNewIterationPlanWithScaffoldFallback_WhenNewRpgPlanRefinementDoesNotMatchScaffold()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SecondGoalPlanGenericRpgCodexClient());
        var first = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest("Complete the first JRPG loop with movement, battle, reward, and return to map.", "completion_suggestion"));
        var firstDetails = await store.GetLatestProjectIterationSessionAsync(projectId);
        foreach (var goal in firstDetails!.Goals)
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "completed", "done", DateTimeOffset.UtcNow.ToString("O"));
        }
        await store.UpdateProjectIterationSessionStatusAsync(
            first.SessionId,
            "completed",
            firstDetails.Goals.Count,
            "First round completed.",
            null,
            DateTimeOffset.UtcNow.ToString("O"));

        var second = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest("第二轮目标：每次战斗随机出现 1-3 名敌人。", "new_iteration_plan"));
        var rounds = await service.ListAsync(accountId, projectId);

        second.Status.Should().Be("ready");
        second.Summary.Should().Contain("model_plan_degraded=scaffold_fallback");
        rounds.Should().HaveCount(2);
        rounds[1].Session.SessionId.Should().Be(second.SessionId);
        rounds[1].Goals.Should().Contain(goal => goal.Title == "JRPG 首轮闭环：战斗或挑战结算");
    }

    [Fact]
    public async Task CreateAsync_ShouldBlockNewIterationPlan_WhenPreviousPlanIsNotComplete()
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
        var first = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest("Complete the first JRPG loop with movement, battle, reward, and return to map.", "completion_suggestion"));

        var second = await service.CreateAsync(
            accountId,
            projectId,
            new PrototypeIterationPlanRequest("第二轮目标：增加村庄支线。", "new_iteration_plan"));
        var rounds = await service.ListAsync(accountId, projectId);

        first.Status.Should().Be("ready");
        second.Status.Should().Be("iteration_plan_update_blocked");
        second.Summary.Should().Contain("需要先完成当前游戏模块");
        rounds.Should().HaveCount(1);
    }

    [Fact]
    public async Task ListAsync_ShouldReturnIterationPlanRoundsInCreationOrder()
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
        var first = await service.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("First round JRPG loop.", "completion_suggestion"));
        var firstDetails = await store.GetLatestProjectIterationSessionAsync(projectId);
        foreach (var goal in firstDetails!.Goals)
        {
            await store.UpdateProjectIterationGoalStatusAsync(goal.GoalId, "completed", "done", DateTimeOffset.UtcNow.ToString("O"));
        }
        await store.UpdateProjectIterationSessionStatusAsync(first.SessionId, "completed", firstDetails.Goals.Count, "First round completed.", null, DateTimeOffset.UtcNow.ToString("O"));
        var second = await service.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Second round: add a shop and stronger enemy.", "new_iteration_plan"));

        var rounds = await service.ListAsync(accountId, projectId);

        rounds.Should().HaveCount(2);
        rounds[0].RoundIndex.Should().Be(1);
        rounds[0].Session.SessionId.Should().Be(first.SessionId);
        rounds[1].RoundIndex.Should().Be(2);
        rounds[1].Session.SessionId.Should().Be(second.SessionId);
        rounds[1].Session.SourceKind.Should().Be("new_iteration_plan");
    }

    [Fact]
    public async Task ListAsync_ShouldCollapseLegacyRegeneratedPlansIntoSingleBaseRound()
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
        var first = await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "First old plan.",
            "First old plan.",
            ValidRpgIterationGoalCommands());
        await store.CreateProjectIterationSessionAsync(
            accountId,
            projectId,
            "completion_suggestion",
            "Regenerated old plan.",
            "Regenerated old plan.",
            ValidRpgIterationGoalCommands(stepOneDescription: "Second old plan supersedes first."));

        var rounds = await service.ListAsync(accountId, projectId);

        rounds.Should().HaveCount(1);
        rounds[0].RoundIndex.Should().Be(1);
        rounds[0].Session.SessionId.Should().NotBe(first.SessionId);
        rounds[0].Session.SourceMessage.Should().Be("Regenerated old plan.");
    }

    [Fact]
    public async Task CreateAsync_ShouldNotPersistPlan_WhenSkeletonRecreationGuardRequiresNewPrototype()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempDirectory.Create("phase-a-workspaces");
        using var repoRoot = TempDirectory.Create("phase-a-repo");
        var options = Options(workspaceRoot.Path, repoRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId, "RPG");
        var service = new PrototypeIterationPlanService(store, new PrototypeRouteStateWriter(), null, new SkeletonRecreationGuardCodexClient());
        var first = await service.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Improve the current RPG first loop."));

        var second = await service.CreateAsync(accountId, projectId, new PrototypeIterationPlanRequest("Turn this into a side-scrolling action platformer with physics jumps."));
        var latest = await service.GetLatestAsync(accountId, projectId);

        first.Status.Should().Be("ready");
        second.Status.Should().Be("prototype_recreation_required");
        second.Goals.Should().BeEmpty();
        latest!.Session.SessionId.Should().Be(first.SessionId);
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId, string gameTypeSource = "Action")
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", gameTypeSource, null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
        return result.ProjectId!;
    }

    private static IReadOnlyList<ProjectIterationGoalCreateCommand> ValidRpgIterationGoalCommands(
        string stepOneDescription = "Start Adventure opens a visible MapScene with stable movement and map/player assets.",
        string stepTwoDescription = "Validate movement-driven encounter trigger, visible encounter progress, and guaranteed encounter within 10 steps.",
        string stepSixDescription = "Show and validate win after 15 battles, any battle loss means game loss, and encounter rules clearly.")
    {
        return
        [
            new ProjectIterationGoalCreateCommand(1, "JRPG 首轮闭环：地图导航与稳定操控", stepOneDescription, "Visible MapScene, stable movement, and map/player asset usage pass."),
            new ProjectIterationGoalCreateCommand(2, "JRPG 首轮闭环：冲突入口触发", stepTwoDescription, "Encounter trigger, encounter progress, and guaranteed encounter behavior pass."),
            new ProjectIterationGoalCreateCommand(3, "JRPG 首轮闭环：战斗或挑战结算", "Validate BattleScene with one readable battle, enemy asset usage, feedback, and settlement.", "BattleScene settlement and enemy asset usage pass."),
            new ProjectIterationGoalCreateCommand(4, "JRPG 首轮闭环：成长、奖励或后果反馈", "Validate reward 3-choice readability and player understanding.", "Reward 3-choice readability passes."),
            new ProjectIterationGoalCreateCommand(5, "JRPG 首轮闭环：返回或继续循环", "Validate reward state change and return-to-map.", "Reward application and return-to-map pass."),
            new ProjectIterationGoalCreateCommand(6, "JRPG 首轮闭环：角色或队伍状态可读性", stepSixDescription, "Win/fail and encounter rule feedback pass."),
            new ProjectIterationGoalCreateCommand(7, "JRPG 首轮闭环：最终首轮闭环验收", "Run final acceptance across Start Adventure visible map, encounter, battle, reward return-to-map, project contract, map/player/enemy assets, and package readiness.", "Final acceptance, explicit rule coverage, project contract, and asset usage pass.")
        ];
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

    private static void WriteBmadRpgDesignTemplate(string repoRoot)
    {
        var skillRoot = Path.Combine(repoRoot, ".agents", "skills", "gds-create-gdd");
        var gameTypesRoot = Path.Combine(skillRoot, "game-types");
        Directory.CreateDirectory(gameTypesRoot);
        File.WriteAllText(Path.Combine(skillRoot, "game-types.csv"), """
        id,name,description,genre_tags,fragment_file
        rpg,RPG,"Character progression, stats, inventory, quests","rpg,stats,inventory,quests,narrative",rpg.md
        """, System.Text.Encoding.UTF8);
        File.WriteAllText(Path.Combine(gameTypesRoot, "rpg.md"), """
        ## RPG Specific Elements

        ### Character System

        - Character progression
        - Stats
        - Leveling system

        ### Quest System

        - Main story quests
        - Side quests
        """, System.Text.Encoding.UTF8);
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
              "suggestedAction": "请先按导航阻塞点重拆 RPG 游戏模块。",
              "suggestedPromptForRegeneration": "Regenerate the RPG iteration plan starting with Start Adventure to visible MapScene, movement and first encounter, BattleScene, reward loop return-to-map, and final playable acceptance."
            }
            """;
            return Task.FromResult(new CodexChatClientResult(true, json, null, 0, "", ""));
        }
    }

    private class SuccessfulRpgPlanCodexClient : ICodexChatClient
    {
        private readonly bool _includeContractInstruction;

        public string? LastPrompt { get; private set; }
        public string? LastPlanningAnalysisPrompt { get; private set; }
        public string? LastGoalPlanPrompt { get; private set; }
        public List<string> Models { get; } = [];

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
            Models.Add(model);
            LastPrompt = prompt;
            if (options?.OutputSchemaPath?.Contains("planning-analysis", StringComparison.OrdinalIgnoreCase) == true)
            {
                LastPlanningAnalysisPrompt = prompt;
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
                LastGoalPlanPrompt = prompt;
                return Task.FromResult(new CodexChatClientResult(true, BuildGoalPlanFromScaffold(prompt), null, 0, "", ""));
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

        protected virtual string BuildGoalPlanFromScaffold(string prompt)
        {
            var scaffold = ExtractScaffoldGoals(prompt);
            var selectedTitles = scaffold.Select(goal => goal.Title).ToArray();
            var goals = scaffold.Select(goal => new
            {
                title = goal.Title,
                description = RefineScaffoldDescription(goal, selectedTitles),
                acceptanceHint = RefineScaffoldAcceptance(goal, selectedTitles)
            });
            return JsonSerializer.Serialize(new { goals });
        }

        private string RefineScaffoldDescription(ScaffoldGoal goal, IReadOnlyList<string> selectedTitles)
        {
            if (goal.Title.Contains("field navigation and stable control", StringComparison.Ordinal) ||
                goal.Title.Contains("地图导航与稳定操控", StringComparison.Ordinal))
            {
                return "Start Adventure opens a visible playable field or MapScene, proves stable controllable movement, and shows map/player asset usage.";
            }

            if (goal.Title.Contains("final first-loop acceptance", StringComparison.Ordinal) ||
                goal.Title.Contains("最终首轮闭环验收", StringComparison.Ordinal))
            {
                var selected = string.Join(", ", selectedTitles);
                return _includeContractInstruction
                    ? $"Run final acceptance across selected capabilities ({selected}), input_traceability, and project-specific contract fields."
                    : $"Run final acceptance across selected capabilities ({selected}) and project-specific contract fields.";
            }

            return goal.Description;
        }

        private static string RefineScaffoldAcceptance(ScaffoldGoal goal, IReadOnlyList<string> selectedTitles)
        {
            if (goal.Title.Contains("field navigation and stable control", StringComparison.Ordinal) ||
                goal.Title.Contains("地图导航与稳定操控", StringComparison.Ordinal))
            {
                return "Pass only when Start Adventure opens a visible playable field, movement is stable, and map/player asset usage is visible.";
            }

            if (goal.Title.Contains("final first-loop acceptance", StringComparison.Ordinal) ||
                goal.Title.Contains("最终首轮闭环验收", StringComparison.Ordinal))
            {
                var hasBattle = selectedTitles.Any(title => title.Contains("battle or challenge", StringComparison.OrdinalIgnoreCase));
                var hasReward = selectedTitles.Any(title => title.Contains("growth, reward", StringComparison.OrdinalIgnoreCase));
                var suffix = hasBattle
                    ? " BattleScene, enemy, and battle asset usage remain valid."
                    : " Map and player asset usage remain visible.";
                suffix += hasReward ? " Reward or growth feedback remains valid." : "";
                return "Pass only when the selected JRPG first-loop capabilities are playable end-to-end, and Start Adventure visible-map validation, project-specific contract fields, and package readiness all pass." + suffix;
            }

            return goal.AcceptanceHint;
        }

        protected static IReadOnlyList<ScaffoldGoal> ExtractScaffoldGoals(string prompt)
        {
            const string marker = "Goal scaffold that must be preserved:";
            var markerIndex = prompt.IndexOf(marker, StringComparison.Ordinal);
            if (markerIndex < 0)
            {
                return [];
            }

            var jsonStart = prompt.IndexOf('[', markerIndex);
            if (jsonStart < 0)
            {
                return [];
            }

            var json = ExtractJsonArray(prompt[jsonStart..]);
            if (string.IsNullOrWhiteSpace(json))
            {
                return [];
            }

            try
            {
                using var document = JsonDocument.Parse(json);
                return document.RootElement.EnumerateArray()
                    .Select(item => new ScaffoldGoal(
                        ReadString(item, "Title") ?? ReadString(item, "title") ?? "RPG Test Goal",
                        ReadString(item, "Description") ?? ReadString(item, "description") ?? "Test description.",
                        ReadString(item, "AcceptanceHint") ?? ReadString(item, "acceptanceHint") ?? "Test acceptance."))
                    .ToArray();
            }
            catch (JsonException)
            {
                return [];
            }
        }

        private static string? ExtractJsonArray(string text)
        {
            var depth = 0;
            var inString = false;
            var escaped = false;
            for (var index = 0; index < text.Length; index++)
            {
                var current = text[index];
                if (inString)
                {
                    if (escaped)
                    {
                        escaped = false;
                    }
                    else if (current == '\\')
                    {
                        escaped = true;
                    }
                    else if (current == '"')
                    {
                        inString = false;
                    }

                    continue;
                }

                if (current == '"')
                {
                    inString = true;
                    continue;
                }

                if (current == '[')
                {
                    depth++;
                }
                else if (current == ']')
                {
                    depth--;
                    if (depth == 0)
                    {
                        return text[..(index + 1)];
                    }
                }
            }

            return null;
        }

        private static string? ReadString(JsonElement element, string propertyName)
        {
            return element.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String
                ? property.GetString()
                : null;
        }

        protected sealed record ScaffoldGoal(string Title, string Description, string AcceptanceHint);
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
                          "title": "JRPG 首轮闭环：开局语境与玩家目标",
                          "description": "Establish who the player controls, where the JRPG prototype starts, and the next immediate objective.",
                          "acceptanceHint": "Pass only when the playable scene presents a clear controllable hero, context, and objective."
                        },
                        {
                          "title": "JRPG 首轮闭环：地图导航与稳定操控",
                          "description": "Resolve the navigation blocker first: Start Adventure opens a visible MapScene, proves stable movement, and shows map/player asset usage.",
                          "acceptanceHint": "Pass only when Start Adventure opens a visible RPG MapScene, movement stays stable, and map/player assets are visible."
                        },
                        {
                          "title": "JRPG 首轮闭环：冲突入口触发",
                          "description": "Validate movement-driven encounter trigger, visible encounter progress, and guaranteed encounter behavior.",
                          "acceptanceHint": "Pass only when actual map traversal exposes the first encounter and any guaranteed encounter rule is proven."
                        },
                        {
                          "title": "JRPG 首轮闭环：战斗或挑战结算",
                          "description": "Validate one readable BattleScene loop with enemy asset usage and settlement.",
                          "acceptanceHint": "Pass only when BattleScene reaches clear battle feedback, enemy asset usage, and settlement."
                        },
                        {
                          "title": "JRPG 首轮闭环：成长、奖励或后果反馈",
                          "description": "Prove reward 3-choice readability and player understanding.",
                          "acceptanceHint": "Pass only when reward choices are visible and understandable."
                        },
                        {
                          "title": "JRPG 首轮闭环：返回或继续循环",
                          "description": "Prove reward 3-choice changes state and returns to the active map loop.",
                          "acceptanceHint": "Pass only when reward selection, state change, and return-to-map are visible."
                        },
                        {
                          "title": "JRPG 首轮闭环：角色或队伍状态可读性",
                          "description": "Show and validate 15-battle victory, any-loss defeat, and encounter rules.",
                          "acceptanceHint": "Pass only when players can understand win/fail and encounter rules."
                        },
                        {
                          "title": "JRPG 首轮闭环：最终首轮闭环验收",
                          "description": "Run final acceptance across Start Adventure visible map, battle, reward return, navigation, and contract-specific runtime proof.",
                          "acceptanceHint": "Pass only when the JRPG first-loop prototype, Start Adventure visible-map validation, contract-specific runtime proof, and map/player/enemy asset usage all pass."
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
                  "reason": "RPG plan acceptance boundary mismatch: step 1 must only validate Start Adventure to visible MapScene and stable movement. Encounter trigger, BattleScene, reward, scene switching, package readiness, and final acceptance requirements must be split into later steps.",
                  "suggestedAction": "Regenerate the RPG iteration plan.",
                  "suggestedPromptForRegeneration": "Regenerate the plan so Step 1 only covers Start Adventure, visible MapScene, and stable movement before encounter trigger, BattleScene, reward, scene switching, and final acceptance."
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
                      "title": "RPG Godot 原型游戏模块",
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

    private sealed class SecondGoalPlanGenericRpgCodexClient : SuccessfulRpgPlanCodexClient
    {
        private int _goalPlanCalls;

        protected override string BuildGoalPlanFromScaffold(string prompt)
        {
            _goalPlanCalls++;
            if (_goalPlanCalls == 1)
            {
                return base.BuildGoalPlanFromScaffold(prompt);
            }

            var goals = new[]
            {
                new
                {
                    title = "RPG Godot 原型游戏模块",
                    description = "给出一个通用的 RPG 原型计划。",
                    acceptanceHint = "通用计划"
                },
                new
                {
                    title = "迭代 1：可玩底座",
                    description = "实现基础地图与移动。",
                    acceptanceHint = "可玩"
                }
            };
            return JsonSerializer.Serialize(new { goals });
        }
    }

    private sealed class DamagedRpgTitleCodexClient : SuccessfulRpgPlanCodexClient
    {
        protected override string BuildGoalPlanFromScaffold(string prompt)
        {
            var scaffold = ExtractScaffoldGoals(prompt);
            var goals = scaffold.Select((goal, index) => new
            {
                title = index == scaffold.Count - 1
                    ? goal.Title + "},{"
                    : goal.Title,
                description = goal.Description,
                acceptanceHint = goal.AcceptanceHint
            });
            return JsonSerializer.Serialize(new { goals });
        }
    }

    private sealed class StrictRouteRegenerationCodexClient : ICodexChatClient
    {
        public int GoalPlanCallCount { get; private set; }

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
                GoalPlanCallCount++;
                const string generic =
                    """
                    {
                      "goals": [
                        {
                          "title": "Generic RPG plan",
                          "description": "This stale response must not be used for strict regeneration.",
                          "acceptanceHint": "generic"
                        }
                      ]
                    }
                    """;
                return Task.FromResult(new CodexChatClientResult(true, generic, null, 0, "", ""));
            }

            const string evaluation =
                """
                {
                  "decision": "should_refine_plan",
                  "summary": "stale model boundary response",
                  "reason": "RPG plan acceptance boundary mismatch: step 1 must only validate Start Adventure to visible MapScene and stable movement. Encounter trigger, BattleScene, reward, scene switching, package readiness, and final acceptance requirements must be split into later steps.",
                  "suggestedAction": "Regenerate the RPG iteration plan.",
                  "suggestedPromptForRegeneration": "Regenerate the RPG iteration plan as JRPG first-loop capability steps: Start Adventure to visible MapScene with stable movement first, encounter trigger and guaranteed encounter second, BattleScene visualization and settlement third, reward/growth feedback, reward application and return-to-map fifth, win/fail visibility sixth, and final final first-loop acceptance."
                }
                """;
            return Task.FromResult(new CodexChatClientResult(true, evaluation, null, 0, "", ""));
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
                      "title": "JRPG 首轮闭环：开局语境与玩家目标",
                      "description": "Establish who the player controls, where the JRPG prototype starts, and the next immediate objective.",
                      "acceptanceHint": "Pass only when the playable scene presents a clear controllable hero, context, and objective."
                    },
                    {
                      "title": "JRPG 首轮闭环：地图导航与稳定操控",
                      "description": "Resolve the navigation blocker first: Start Adventure opens a visible MapScene and proves stable controllable movement.",
                      "acceptanceHint": "Pass only when Start Adventure opens a visible RPG MapScene and the player can move continuously."
                    },
                    {
                      "title": "JRPG 首轮闭环：冲突入口触发",
                      "description": "Validate movement-driven encounter trigger, visible encounter progress, and guaranteed encounter behavior.",
                      "acceptanceHint": "Pass only when actual map traversal exposes the first encounter and any guaranteed encounter rule is proven."
                    },
                    {
                      "title": "JRPG 首轮闭环：战斗或挑战结算",
                      "description": "Validate one readable BattleScene loop with enemy asset usage and settlement.",
                      "acceptanceHint": "Pass only when BattleScene reaches clear battle feedback, enemy asset usage, and settlement."
                    },
                    {
                      "title": "JRPG 首轮闭环：成长、奖励或后果反馈",
                      "description": "Prove reward 3-choice readability and player understanding.",
                      "acceptanceHint": "Pass only when reward choices are visible and understandable."
                    },
                    {
                      "title": "JRPG 首轮闭环：返回或继续循环",
                      "description": "Prove reward 3-choice changes state and returns to the active map loop.",
                      "acceptanceHint": "Pass only when reward selection, state change, and return-to-map are visible."
                    },
                    {
                      "title": "JRPG 首轮闭环：角色或队伍状态可读性",
                      "description": "Show and validate victory, failure, defeat, and encounter rules.",
                      "acceptanceHint": "Pass only when players can understand victory, failure, defeat, and encounter rule feedback."
                    },
                    {
                      "title": "JRPG 首轮闭环：最终首轮闭环验收",
                      "description": "Run final acceptance across map, battle, reward return, navigation, and project-specific contract fields.",
                      "acceptanceHint": "Pass only when the full playable prototype, Start Adventure visible-map validation, project-specific contract fields, and map/player/enemy asset usage all pass."
                    }
                  ]
                }
                """;
            return Task.FromResult(new CodexChatClientResult(true, payload, null, 0, "", ""));
        }
    }

    private sealed class SkeletonRecreationGuardCodexClient : ICodexChatClient
    {
        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            if (prompt.Contains("Phase A iteration-plan safety guard", StringComparison.OrdinalIgnoreCase))
            {
                const string guard =
                    """
                    {
                      "requiresPrototypeRecreation": true,
                      "reason": "游戏功能计划改动过大，需要新建项目重新创建游戏原型骨架。"
                    }
                    """;
                return Task.FromResult(new CodexChatClientResult(true, guard, null, 0, "", ""));
            }

            if (options?.OutputSchemaPath?.Contains("planning-analysis", StringComparison.OrdinalIgnoreCase) == true)
            {
                const string analysis =
                    """
                    {
                      "analysisSummary": "The RPG first loop can be planned.",
                      "fieldCoverage": [
                        { "field": "core_loop", "status": "present", "evidence": "RPG first loop", "missingReason": null }
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
                          "title": "JRPG 首轮闭环：开局语境与玩家目标",
                          "description": "Establish who the player controls, where the JRPG prototype starts, and the next immediate objective.",
                          "acceptanceHint": "Pass only when the playable scene presents a clear controllable hero, context, and objective."
                        },
                        {
                          "title": "JRPG 首轮闭环：地图导航与稳定操控",
                          "description": "Start Adventure opens a visible MapScene with stable movement and map/player assets.",
                          "acceptanceHint": "Visible MapScene, stable movement, and assets pass."
                        },
                        {
                          "title": "JRPG 首轮闭环：冲突入口触发",
                          "description": "Validate movement-driven encounter trigger, visible encounter progress, and guaranteed encounter behavior.",
                          "acceptanceHint": "Encounter trigger, encounter progress, and guaranteed encounter behavior pass."
                        },
                        {
                          "title": "JRPG 首轮闭环：战斗或挑战结算",
                          "description": "Validate BattleScene with one readable battle, enemy asset usage, feedback, and settlement.",
                          "acceptanceHint": "BattleScene settlement and enemy asset usage pass."
                        },
                        {
                          "title": "JRPG 首轮闭环：成长、奖励或后果反馈",
                          "description": "Validate reward 3-choice readability and player understanding.",
                          "acceptanceHint": "Reward 3-choice readability passes."
                        },
                        {
                          "title": "JRPG 首轮闭环：返回或继续循环",
                          "description": "Validate reward state change and return-to-map.",
                          "acceptanceHint": "Reward application and return-to-map pass."
                        },
                        {
                          "title": "JRPG 首轮闭环：角色或队伍状态可读性",
                          "description": "Show and validate win after 15 battles, any battle loss means game loss, and encounter rules clearly.",
                          "acceptanceHint": "Win/fail and encounter rule feedback pass."
                        },
                        {
                          "title": "JRPG 首轮闭环：最终首轮闭环验收",
                          "description": "Run final acceptance across Start Adventure visible map, encounter, battle, reward return-to-map, project contract, map/player/enemy assets, and package readiness.",
                          "acceptanceHint": "Final acceptance, explicit rule coverage, project contract, and asset usage pass."
                        }
                      ]
                    }
                    """;
                return Task.FromResult(new CodexChatClientResult(true, goals, null, 0, "", ""));
            }

            const string evaluation =
                """
                {
                  "decision": "ready_to_execute",
                  "summary": "The plan is usable.",
                  "reason": "The goals are bounded.",
                  "suggestedAction": "Execute the next goal.",
                  "suggestedPromptForRegeneration": null
                }
                """;
            return Task.FromResult(new CodexChatClientResult(true, evaluation, null, 0, "", ""));
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
