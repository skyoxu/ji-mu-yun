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

        var latest = await service.GetLatestAsync(accountId, projectId);
        latest.Should().NotBeNull();
        latest!.LatestEvaluation.Should().NotBeNull();
        latest.LatestEvaluation!.Decision.Should().Be(result.LatestEvaluation.Decision);
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
        var finalGoal = result.Goals.Should().Contain(goal => goal.Title.Contains("Final Step", StringComparison.Ordinal)).Subject;
        string.Join(" ", finalGoal.Title, finalGoal.Description, finalGoal.AcceptanceHint).Should()
            .Contain("进入一次战斗")
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
        result.Goals[3].Title.Should().Contain("Final Step");
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
        result.Goals[0].Title.Should().Be("JRPG First Loop: field navigation and stable control");
        string.Join(" ", result.Goals[0].Title, result.Goals[0].Description, result.Goals[0].AcceptanceHint)
            .Should()
            .Contain("Start Adventure")
            .And.Contain("playable field")
            .And.Contain("movement")
            .And.Contain("asset")
            .And.NotContain("encounter entry")
            .And.NotContain("BattleScene")
            .And.NotContain("full playable")
            .And.NotContain("scene switching");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: growth, reward, or consequence feedback");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: battle or challenge resolution");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: growth, reward, or consequence feedback");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: return or continue loop");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: battle or challenge resolution");
        result.Goals.Select(goal => goal.Title).Should().Contain(title => title.Contains("reward", StringComparison.OrdinalIgnoreCase));
        result.Goals.Last().Title.Should().Contain("final first-loop acceptance");
        result.Goals.Last().AcceptanceHint.Should().Contain("playable end-to-end");
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
        result.Goals[0].Title.Should().Be("JRPG First Loop: field navigation and stable control");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: growth, reward, or consequence feedback");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: growth, reward, or consequence feedback");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: return or continue loop");
        result.Goals[0].Title.Should().NotContain("对齐原型合同");
        result.Goals.Last().Title.Should().Contain("final first-loop acceptance");
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
        result.Goals[0].Title.Should().Be("JRPG First Loop: field navigation and stable control");
        result.Goals[0].Description.Should().Contain("Start Adventure");
        string.Join(" ", result.Goals[0].Description, result.Goals[0].AcceptanceHint).Should().Match(text => text.Contains("playable field", StringComparison.OrdinalIgnoreCase) || text.Contains("visible MapScene", StringComparison.OrdinalIgnoreCase));
        result.Goals[0].Description.Should().NotContain("encounter entry");
        result.Goals[0].AcceptanceHint.Should().Contain("move continuously");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: conflict entry trigger");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: battle or challenge resolution");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: growth, reward, or consequence feedback");
        result.Goals[0].Title.ToLowerInvariant().Should().NotContain("foundation asset");
        result.LatestEvaluation.Should().NotBeNull();
        result.LatestEvaluation!.Decision.Should().NotBeNullOrWhiteSpace();
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
        result.Goals[0].Title.Should().Be("JRPG First Loop: field navigation and stable control");
        string.Join(" ", result.Goals[0].Title, result.Goals[0].Description, result.Goals[0].AcceptanceHint)
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
        result.Goals[0].Title.Should().Be("JRPG First Loop: field navigation and stable control");
        result.Goals[0].Description.Should().Contain("Start Adventure");
        result.Goals[0].Description.Should().NotContain("encounter entry");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: conflict entry trigger");
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
        string.Join(" ", result.Goals[0].Description, result.Goals[0].AcceptanceHint).Should().Match(text => text.Contains("playable field", StringComparison.OrdinalIgnoreCase) || text.Contains("visible MapScene", StringComparison.OrdinalIgnoreCase));
        result.Goals[0].AcceptanceHint.Should().Contain("asset");
        result.Goals.Select(goal => goal.Title).Should().Contain("JRPG First Loop: battle or challenge resolution");
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
                new ProjectIterationGoalCreateCommand(6, "JRPG First Loop: final first-loop acceptance", "Validate full playable prototype acceptance.", "Final acceptance passes with Start Adventure visible map and package readiness.")
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
            new ProjectIterationGoalCreateCommand(1, "JRPG First Loop: field navigation and stable control", stepOneDescription, "Visible MapScene, stable movement, and map/player asset usage pass."),
            new ProjectIterationGoalCreateCommand(2, "JRPG First Loop: conflict entry trigger", stepTwoDescription, "Encounter trigger, encounter progress, and guaranteed encounter behavior pass."),
            new ProjectIterationGoalCreateCommand(3, "JRPG First Loop: battle or challenge resolution", "Validate BattleScene with one readable battle, enemy asset usage, feedback, and settlement.", "BattleScene settlement and enemy asset usage pass."),
            new ProjectIterationGoalCreateCommand(4, "JRPG First Loop: growth, reward, or consequence feedback", "Validate reward 3-choice readability and player understanding.", "Reward 3-choice readability passes."),
            new ProjectIterationGoalCreateCommand(5, "JRPG First Loop: return or continue loop", "Validate reward state change and return-to-map.", "Reward application and return-to-map pass."),
            new ProjectIterationGoalCreateCommand(6, "JRPG First Loop: party or character state readability", stepSixDescription, "Win/fail and encounter rule feedback pass."),
            new ProjectIterationGoalCreateCommand(7, "JRPG First Loop: final first-loop acceptance", "Run final acceptance across Start Adventure visible map, encounter, battle, reward return-to-map, project contract, map/player/enemy assets, and package readiness.", "Final acceptance, explicit rule coverage, project contract, and asset usage pass.")
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
                var finalDescription = _includeContractInstruction
                    ? "Run final acceptance across map, battle, reward return, navigation, input_traceability, and contract-specific runtime proof."
                    : "Run final acceptance across map, battle, reward return, navigation, and contract-specific runtime proof.";
                var finalAcceptance = _includeContractInstruction
                    ? "Pass only when the full prototype and project-specific prototype contract fields pass."
                    : "Pass only when the JRPG first-loop prototype, Start Adventure visible-map validation, and contract-specific runtime proof all pass.";
                if (prompt.Contains("JRPG First Loop: field navigation and stable control", StringComparison.Ordinal))
                {
                    var navigationFirstPayload = $$"""
                    {
                      "goals": [
                        {
                          "title": "JRPG First Loop: field navigation and stable control",
                          "description": "Resolve the navigation blocker first: Start Adventure opens a visible MapScene, proves stable controllable movement, and shows map/player asset usage.",
                          "acceptanceHint": "Pass only when Start Adventure opens a visible RPG MapScene, the player can move continuously, and map/player assets are visible."
                        },
                        {
                          "title": "JRPG First Loop: conflict entry trigger",
                          "description": "Validate movement-driven encounter trigger, visible encounter progress, and guaranteed encounter behavior.",
                          "acceptanceHint": "Pass only when actual map traversal exposes the first encounter and any guaranteed encounter rule is proven."
                        },
                        {
                          "title": "JRPG First Loop: battle or challenge resolution",
                          "description": "Validate one readable BattleScene loop with enemy asset usage and settlement.",
                          "acceptanceHint": "Pass only when BattleScene reaches clear battle feedback, enemy asset usage, and settlement."
                        },
                        {
                          "title": "JRPG First Loop: growth, reward, or consequence feedback",
                          "description": "Prove reward 3-choice readability and player understanding.",
                          "acceptanceHint": "Pass only when reward choices are visible and understandable."
                        },
                        {
                          "title": "JRPG First Loop: return or continue loop",
                          "description": "Prove reward 3-choice changes state and returns to the active map loop.",
                          "acceptanceHint": "Pass only when reward selection, state change, and return-to-map are visible."
                        },
                        {
                          "title": "JRPG First Loop: party or character state readability",
                          "description": "Show and validate 15-battle victory, any-loss defeat, and encounter rules.",
                          "acceptanceHint": "Pass only when players can understand win/fail and encounter rules."
                        },
                        {
                          "title": "JRPG First Loop: final first-loop acceptance",
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
                      "title": "JRPG First Loop: field navigation and stable control",
                      "description": "Resolve the navigation blocker first: Start Adventure opens a visible MapScene, proves stable controllable movement, and shows map/player asset usage.",
                      "acceptanceHint": "Pass only when Start Adventure opens a visible RPG MapScene, the player can move continuously, and map/player assets are visible."
                    },
                    {
                      "title": "JRPG First Loop: conflict entry trigger",
                      "description": "Validate movement-driven encounter trigger, visible encounter progress, and guaranteed encounter behavior.",
                      "acceptanceHint": "Pass only when actual map traversal exposes the first encounter and any guaranteed encounter rule is proven."
                    },
                    {
                      "title": "JRPG First Loop: battle or challenge resolution",
                      "description": "Validate one readable BattleScene loop with enemy asset usage and settlement.",
                      "acceptanceHint": "Pass only when BattleScene reaches clear battle feedback, enemy asset usage, and settlement."
                    },
                    {
                      "title": "JRPG First Loop: growth, reward, or consequence feedback",
                      "description": "Prove reward 3-choice readability and player understanding.",
                      "acceptanceHint": "Pass only when reward choices are visible and understandable."
                    },
                    {
                      "title": "JRPG First Loop: return or continue loop",
                      "description": "Prove reward 3-choice changes state and returns to the active map loop.",
                      "acceptanceHint": "Pass only when reward selection, state change, and return-to-map are visible."
                    },
                    {
                      "title": "JRPG First Loop: party or character state readability",
                      "description": "Show and validate 15-battle victory, any-loss defeat, and encounter rules.",
                      "acceptanceHint": "Pass only when players can understand win/fail and encounter rules."
                    },
                    {
                      "title": "JRPG First Loop: final first-loop acceptance",
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
                          "title": "JRPG First Loop: field navigation and stable control",
                          "description": "Resolve the navigation blocker first: Start Adventure opens a visible MapScene, proves stable movement, and shows map/player asset usage.",
                          "acceptanceHint": "Pass only when Start Adventure opens a visible RPG MapScene, movement stays stable, and map/player assets are visible."
                        },
                        {
                          "title": "JRPG First Loop: conflict entry trigger",
                          "description": "Validate movement-driven encounter trigger, visible encounter progress, and guaranteed encounter behavior.",
                          "acceptanceHint": "Pass only when actual map traversal exposes the first encounter and any guaranteed encounter rule is proven."
                        },
                        {
                          "title": "JRPG First Loop: battle or challenge resolution",
                          "description": "Validate one readable BattleScene loop with enemy asset usage and settlement.",
                          "acceptanceHint": "Pass only when BattleScene reaches clear battle feedback, enemy asset usage, and settlement."
                        },
                        {
                          "title": "JRPG First Loop: growth, reward, or consequence feedback",
                          "description": "Prove reward 3-choice readability and player understanding.",
                          "acceptanceHint": "Pass only when reward choices are visible and understandable."
                        },
                        {
                          "title": "JRPG First Loop: return or continue loop",
                          "description": "Prove reward 3-choice changes state and returns to the active map loop.",
                          "acceptanceHint": "Pass only when reward selection, state change, and return-to-map are visible."
                        },
                        {
                          "title": "JRPG First Loop: party or character state readability",
                          "description": "Show and validate 15-battle victory, any-loss defeat, and encounter rules.",
                          "acceptanceHint": "Pass only when players can understand win/fail and encounter rules."
                        },
                        {
                          "title": "JRPG First Loop: final first-loop acceptance",
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
                      "title": "JRPG First Loop: field navigation and stable control",
                      "description": "Resolve the navigation blocker first: Start Adventure opens a visible MapScene, proves stable controllable movement, and shows map/player asset usage.",
                      "acceptanceHint": "Pass only when Start Adventure opens a visible RPG MapScene, the player can move continuously, and map/player assets are visible."
                    },
                    {
                      "title": "JRPG First Loop: conflict entry trigger",
                      "description": "Validate movement-driven encounter trigger, visible encounter progress, and guaranteed encounter behavior.",
                      "acceptanceHint": "Pass only when actual map traversal exposes the first encounter and any guaranteed encounter rule is proven."
                    },
                    {
                      "title": "JRPG First Loop: battle or challenge resolution",
                      "description": "Validate one readable BattleScene loop with enemy asset usage and settlement.",
                      "acceptanceHint": "Pass only when BattleScene reaches clear battle feedback, enemy asset usage, and settlement."
                    },
                    {
                      "title": "JRPG First Loop: growth, reward, or consequence feedback",
                      "description": "Prove reward 3-choice readability and player understanding.",
                      "acceptanceHint": "Pass only when reward choices are visible and understandable."
                    },
                    {
                      "title": "JRPG First Loop: return or continue loop",
                      "description": "Prove reward 3-choice changes state and returns to the active map loop.",
                      "acceptanceHint": "Pass only when reward selection, state change, and return-to-map are visible."
                    },
                    {
                      "title": "JRPG First Loop: party or character state readability",
                      "description": "Show and validate victory, failure, defeat, and encounter rules.",
                      "acceptanceHint": "Pass only when players can understand victory, failure, defeat, and encounter rule feedback."
                    },
                    {
                      "title": "JRPG First Loop: final first-loop acceptance",
                      "description": "Run final acceptance across map, battle, reward return, navigation, and contract-specific runtime proof.",
                      "acceptanceHint": "Pass only when the full playable prototype, Start Adventure visible-map validation, contract-specific runtime proof, and map/player/enemy asset usage all pass."
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
                          "title": "JRPG First Loop: field navigation and stable control",
                          "description": "Start Adventure opens a visible MapScene with stable movement and map/player assets.",
                          "acceptanceHint": "Visible MapScene, stable movement, and assets pass."
                        },
                        {
                          "title": "JRPG First Loop: conflict entry trigger",
                          "description": "Validate movement-driven encounter trigger, visible encounter progress, and guaranteed encounter behavior.",
                          "acceptanceHint": "Encounter trigger, encounter progress, and guaranteed encounter behavior pass."
                        },
                        {
                          "title": "JRPG First Loop: battle or challenge resolution",
                          "description": "Validate BattleScene with one readable battle, enemy asset usage, feedback, and settlement.",
                          "acceptanceHint": "BattleScene settlement and enemy asset usage pass."
                        },
                        {
                          "title": "JRPG First Loop: growth, reward, or consequence feedback",
                          "description": "Validate reward 3-choice readability and player understanding.",
                          "acceptanceHint": "Reward 3-choice readability passes."
                        },
                        {
                          "title": "JRPG First Loop: return or continue loop",
                          "description": "Validate reward state change and return-to-map.",
                          "acceptanceHint": "Reward application and return-to-map pass."
                        },
                        {
                          "title": "JRPG First Loop: party or character state readability",
                          "description": "Show and validate win after 15 battles, any battle loss means game loss, and encounter rules clearly.",
                          "acceptanceHint": "Win/fail and encounter rule feedback pass."
                        },
                        {
                          "title": "JRPG First Loop: final first-loop acceptance",
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
