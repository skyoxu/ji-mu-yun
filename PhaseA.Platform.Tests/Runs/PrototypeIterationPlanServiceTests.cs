using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
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
}
