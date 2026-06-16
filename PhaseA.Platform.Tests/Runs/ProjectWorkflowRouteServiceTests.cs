using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Readback;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class ProjectWorkflowRouteServiceTests
{
    [Fact]
    public async Task QueryAsync_WhenPrototypeMissing_RecommendsPrototypeCreation()
    {
        var fixture = await WorkflowFixture.CreateAsync();

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId);

        result!.NextAction.ActionId.Should().Be("create-prototype");
        result.StageId.Should().Be("create-prototype");
        result.Recommendation.Should().Contain("建议先进行 2. 原型骨架创建");
        result.Recommendation.Should().Contain("高级策划模式");
    }

    [Fact]
    public async Task QueryAsync_WhenSkeletonAcceptedButNoPlan_RecommendsIterationPlan()
    {
        var fixture = await WorkflowFixture.CreateAsync();
        await fixture.SeedPrototypeCreationAsync("succeeded");

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId);

        result!.NextAction.ActionId.Should().Be("create-iteration-plan");
        result.Recommendation.Should().Contain("骨架验收已经通过");
        result.Recommendation.Should().Contain("生成迭代计划");
    }

    [Fact]
    public async Task QueryAsync_WhenIterationHasPendingGoal_RecommendsExecuteNextGoal()
    {
        var fixture = await WorkflowFixture.CreateAsync();
        await fixture.SeedPrototypeCreationAsync("succeeded");
        await fixture.CreateIterationSessionAsync(["pending", "pending"]);

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId);

        result!.NextAction.ActionId.Should().Be("execute-iteration-goal");
        result.Recommendation.Should().Contain("当前迭代计划还有待执行 step");
    }

    [Fact]
    public async Task QueryAsync_WhenIterationHasNeedsFixGoal_RecommendsNeedsFixRoute()
    {
        var fixture = await WorkflowFixture.CreateAsync();
        await fixture.SeedPrototypeCreationAsync("succeeded");
        await fixture.CreateIterationSessionAsync(["succeeded", "needs_fix"]);

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId);

        result!.NextAction.ActionId.Should().Be("needs-fix-route");
        result.Recommendation.Should().Contain("存在 needs fix 或 failed");
    }

    [Fact]
    public async Task QueryAsync_WhenIterationCompletedButNoPostIterationAcceptance_RecommendsPrototypeAcceptance()
    {
        var fixture = await WorkflowFixture.CreateAsync();
        await fixture.SeedPrototypeCreationAsync("succeeded");
        await fixture.CreateIterationSessionAsync(["succeeded", "succeeded"]);

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId);

        result!.NextAction.ActionId.Should().Be("prototype-acceptance");
        result.Steps.Single(step => step.Id == "prototype-acceptance").Status.Should().Be("pending");
        result.Recommendation.Should().Contain("迭代计划已经完成");
        result.Recommendation.Should().Contain("重新进行原型验收");
    }

    [Fact]
    public async Task QueryAsync_WhenOnlyOldValidationPredatesCompletedIteration_RecommendsPrototypeAcceptance()
    {
        var fixture = await WorkflowFixture.CreateAsync();
        await fixture.SeedPrototypeCreationAsync("succeeded");
        await fixture.SeedValidationOnlyRunAsync("succeeded");
        await Task.Delay(20);
        await fixture.CreateIterationSessionAsync(["succeeded", "succeeded"]);

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId);

        result!.NextAction.ActionId.Should().Be("prototype-acceptance");
        result.Steps.Single(step => step.Id == "prototype-acceptance").Status.Should().Be("pending");
    }

    [Fact]
    public async Task QueryAsync_WhenLatestValidationSucceedsAfterFailure_MarksAcceptanceDone()
    {
        var fixture = await WorkflowFixture.CreateAsync();
        await fixture.SeedPrototypeCreationAsync("succeeded");
        await fixture.CreateIterationSessionAsync(["succeeded", "succeeded"]);
        await fixture.SeedValidationOnlyRunAsync("failed");
        await Task.Delay(20);
        await fixture.SeedValidationOnlyRunAsync("succeeded");

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId);

        result!.Steps.Single(step => step.Id == "prototype-acceptance").Status.Should().Be("done");
        result.NextAction.ActionId.Should().Be("download-project");
        result.NextAction.ButtonLabel.Should().Be("打包下载项目");
        result.Recommendation.Should().Contain("打包下载项目");
    }

    [Fact]
    public async Task QueryAsync_WhenLatestUiOptimizationSucceedsAfterFailure_MarksUiDone()
    {
        var fixture = await WorkflowFixture.CreateAsync();
        await fixture.SeedUiOptimizationRunAsync("failed");
        await Task.Delay(20);
        await fixture.SeedUiOptimizationRunAsync("succeeded");

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId);

        result!.Steps.Single(step => step.Id == "ui-optimization").Status.Should().Be("done");
        result.Steps.Single(step => step.Id == "ui-optimization").Evidence.Should().Be("UI 优化已完成。");
    }

    [Fact]
    public async Task QueryAsync_WhenPackageExists_RecommendsDownload()
    {
        var fixture = await WorkflowFixture.CreateAsync();
        await fixture.SeedPrototypeCreationAsync("succeeded");
        await fixture.CreateIterationSessionAsync(["succeeded", "succeeded"]);
        await Task.Delay(20);
        await fixture.SeedValidationOnlyRunAsync("succeeded");
        await fixture.SeedPackageRunAsync();

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId);

        result!.NextAction.ActionId.Should().Be("download-project");
        result.Actions.Should().NotBeNull();
        result.Actions!.Select(action => action.ActionId).Should().Equal(
            "download-project",
            "ui-optimization",
            "asset-inventory",
            "create-next-iteration-plan");
        result.Actions!.Single(action => action.ActionId == "ui-optimization").ButtonLabel.Should().Be("运行 UI 优化");
        result.Actions!.Single(action => action.ActionId == "asset-inventory").ButtonLabel.Should().Be("查看项目素材库");
        result.Recommendation.Should().Contain("下载压缩包");
        result.Recommendation.Should().Contain("UI 优化");
        result.Recommendation.Should().Contain("项目素材库");
    }

    [Fact]
    public async Task QueryAsync_WhenPackageExistsForDragonQuestLikeRoute_RecommendsSpecializedUiAndAssets()
    {
        var fixture = await WorkflowFixture.CreateAsync(gameTypeSource: "勇者斗恶龙");
        await fixture.SeedPrototypeCreationAsync("succeeded");
        await fixture.CreateIterationSessionAsync(["succeeded", "succeeded"]);
        await Task.Delay(20);
        await fixture.SeedValidationOnlyRunAsync("succeeded");
        await fixture.SeedPackageRunAsync();

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId);

        result!.NextAction.ActionId.Should().Be("download-project");
        result.Actions.Should().NotBeNull();
        result.Actions!.Select(action => action.ActionId).Should().Equal(
            "download-project",
            "ui-optimization",
            "asset-inventory",
            "create-next-iteration-plan");
        result.Actions!.Single(action => action.ActionId == "ui-optimization").ButtonLabel.Should().Be("运行 UI 优化");
        result.Actions!.Single(action => action.ActionId == "asset-inventory").ButtonLabel.Should().Be("查看项目素材库");
        result.Recommendation.Should().Contain("UI 优化");
        result.Recommendation.Should().Contain("项目素材库");
    }

    [Fact]
    public async Task QueryAsync_WhenPackageExistsAndUiOptimizationAlreadySucceeded_HidesUiOptimizationAction()
    {
        var fixture = await WorkflowFixture.CreateAsync(gameTypeSource: "勇者斗恶龙");
        await fixture.SeedPrototypeCreationAsync("succeeded");
        await fixture.CreateIterationSessionAsync(["succeeded", "succeeded"]);
        await Task.Delay(20);
        await fixture.SeedValidationOnlyRunAsync("succeeded");
        await fixture.SeedPackageRunAsync();
        await fixture.SeedUiOptimizationRunAsync("succeeded");

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId);

        result!.NextAction.ActionId.Should().Be("download-project");
        result.Actions.Should().NotBeNull();
        result.Actions!.Select(action => action.ActionId).Should().Equal(
            "download-project",
            "asset-inventory",
            "create-next-iteration-plan");
        result.Actions!.Should().NotContain(action => action.ActionId == "ui-optimization");
        result.Recommendation.Should().Contain("UI 优化也已完成");
        result.Recommendation.Should().Contain("项目素材库");
    }

    [Fact]
    public async Task QueryAsync_WhenPackageExistsForGenericRoute_DoesNotRecommendSpecializedUiOrAssets()
    {
        var fixture = await WorkflowFixture.CreateAsync(gameTypeSource: "platformer");
        await fixture.SeedPrototypeCreationAsync("succeeded");
        await fixture.CreateIterationSessionAsync(["succeeded", "succeeded"]);
        await Task.Delay(20);
        await fixture.SeedValidationOnlyRunAsync("succeeded");
        await fixture.SeedPackageRunAsync();

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId);

        result!.NextAction.ActionId.Should().Be("download-project");
        result.Actions.Should().NotBeNull();
        result.Actions!.Select(action => action.ActionId).Should().Equal(
            "download-project",
            "create-next-iteration-plan");
        result.Recommendation.Should().Contain("下载压缩包");
        result.Recommendation.Should().NotContain("项目素材库");
    }

    [Fact]
    public async Task QueryAsync_WhenPlaytestFeedbackAndPackageExists_RecommendsNextIterationPlan()
    {
        var fixture = await WorkflowFixture.CreateAsync();
        await fixture.SeedPrototypeCreationAsync("succeeded");
        await fixture.CreateIterationSessionAsync(["succeeded"]);
        await Task.Delay(20);
        await fixture.SeedValidationOnlyRunAsync("succeeded");
        await fixture.SeedPackageRunAsync();

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId, "试玩后希望提升战斗反馈。");

        result!.NextAction.ActionId.Should().Be("create-next-iteration-plan");
        result.Actions.Should().NotBeNull();
        result.Actions!.Select(action => action.ActionId).Should().Equal(
            "create-next-iteration-plan",
            "download-project",
            "ui-optimization",
            "asset-inventory");
        result.Recommendation.Should().Contain("试玩反馈创建新一轮迭代计划");
    }

    [Fact]
    public async Task QueryAsync_WhenPlaytestFeedbackAndUiOptimizationAlreadySucceeded_HidesUiOptimizationAction()
    {
        var fixture = await WorkflowFixture.CreateAsync(gameTypeSource: "勇者斗恶龙");
        await fixture.SeedPrototypeCreationAsync("succeeded");
        await fixture.CreateIterationSessionAsync(["succeeded"]);
        await Task.Delay(20);
        await fixture.SeedValidationOnlyRunAsync("succeeded");
        await fixture.SeedPackageRunAsync();
        await fixture.SeedUiOptimizationRunAsync("succeeded");

        var result = await fixture.Service.QueryAsync(fixture.AccountId, fixture.ProjectId, "试玩后希望提升战斗反馈。");

        result!.NextAction.ActionId.Should().Be("create-next-iteration-plan");
        result.Actions.Should().NotBeNull();
        result.Actions!.Select(action => action.ActionId).Should().Equal(
            "create-next-iteration-plan",
            "download-project",
            "asset-inventory");
        result.Actions!.Should().NotContain(action => action.ActionId == "ui-optimization");
    }

    [Fact]
    public async Task ClassifyIntentAsync_WhenLlmRoutesNextStep_ReturnsRouteIntent()
    {
        var fixture = await WorkflowFixture.CreateAsync("""{"shouldRoute":true,"intent":"next_step","routeReason":"用户询问下一步","feedbackSummary":""}""");

        var result = await fixture.Service.ClassifyIntentAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new ProjectWorkflowIntentRequest("我下一步应该做什么？", "gpt-5.5"));

        result.ShouldRoute.Should().BeTrue();
        result.Intent.Should().Be("next_step");
        result.RouteReason.Should().Contain("下一步");
        result.FeedbackSummary.Should().BeEmpty();
    }

    [Fact]
    public async Task ClassifyIntentAsync_WhenUserAsksHowToStartCreatingGame_RoutesWithoutLlm()
    {
        var fixture = await WorkflowFixture.CreateAsync("""{"shouldRoute":false,"intent":"general_chat","routeReason":"","feedbackSummary":""}""");

        var result = await fixture.Service.ClassifyIntentAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new ProjectWorkflowIntentRequest("我第一次登陆这个系统，还不太会用，我要如何开始创建我的游戏？", "gpt-5.5"));

        result.ShouldRoute.Should().BeTrue();
        result.Intent.Should().Be("next_step");
        result.RouteReason.Should().Contain("如何开始");
    }

    [Fact]
    public async Task ClassifyIntentAsync_WhenLlmRoutesPlaytestFeedback_ReturnsFeedbackSummary()
    {
        var fixture = await WorkflowFixture.CreateAsync("""{"shouldRoute":true,"intent":"playtest_feedback","routeReason":"用户描述试玩问题","feedbackSummary":"战斗反馈不足，需要二次迭代。"}""");

        var result = await fixture.Service.ClassifyIntentAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new ProjectWorkflowIntentRequest("我试玩后觉得战斗反馈太弱，想做第二轮修改。", "gpt-5.5"));

        result.ShouldRoute.Should().BeTrue();
        result.Intent.Should().Be("playtest_feedback");
        result.RouteReason.Should().Be("用户描述试玩问题");
        result.FeedbackSummary.Should().Be("战斗反馈不足，需要二次迭代。");
    }

    [Fact]
    public async Task ClassifyIntentAsync_WhenLlmMarksGeneralChatAsRoute_DisablesRouting()
    {
        var fixture = await WorkflowFixture.CreateAsync("""{"shouldRoute":true,"intent":"general_chat","routeReason":"模型误判","feedbackSummary":""}""");

        var result = await fixture.Service.ClassifyIntentAsync(
            fixture.AccountId,
            fixture.ProjectId,
            new ProjectWorkflowIntentRequest("普通策划问题", "gpt-5.5"));

        result.ShouldRoute.Should().BeFalse();
        result.Intent.Should().Be("general_chat");
    }

    private sealed class WorkflowFixture : IDisposable
    {
        private readonly TempSqliteDatabase _database;
        private readonly TempDirectory _workspaceRoot;
        private readonly TempDirectory _repoRoot;

        private WorkflowFixture(
            TempSqliteDatabase database,
            TempDirectory workspaceRoot,
            TempDirectory repoRoot,
            PhaseAPlatformOptions options,
            PhaseAMetadataStore store,
            string accountId,
            string projectId,
            ProjectWorkflowRouteService service)
        {
            _database = database;
            _workspaceRoot = workspaceRoot;
            _repoRoot = repoRoot;
            Options = options;
            Store = store;
            AccountId = accountId;
            ProjectId = projectId;
            Service = service;
        }

        public PhaseAPlatformOptions Options { get; }

        public PhaseAMetadataStore Store { get; }

        public string AccountId { get; }

        public string ProjectId { get; }

        public ProjectWorkflowRouteService Service { get; }

        public static async Task<WorkflowFixture> CreateAsync(string? llmJson = null, string gameTypeSource = "RPG")
        {
            var database = TempSqliteDatabase.Create();
            var workspaceRoot = TempDirectory.Create("phase-a-workflow-route-workspaces");
            var repoRoot = TempDirectory.Create("phase-a-workflow-route-repo");
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot.Path,
                ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot.Path, "metadata.sqlite3"),
                ["PHASEA_REPOSITORY_ROOT"] = repoRoot.Path
            });
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var accountId = await store.EnsureSingleAdminAsync();
            var projectId = await CreateProjectAsync(store, options, accountId, gameTypeSource);
            var service = CreateService(store, options, llmJson);
            return new WorkflowFixture(database, workspaceRoot, repoRoot, options, store, accountId, projectId, service);
        }

        public async Task SeedPrototypeCreationAsync(string status)
        {
            var project = (await Store.GetProjectSnapshotAsync(ProjectId))!;
            var runId = await Store.CreateRunAsync(ProjectId, project.WorkspaceId, "prototype-7day-playable");
            await Store.MarkRunStartedAsync(runId);
            await Store.CompleteRunAsync(
                runId,
                status,
                status == "succeeded" ? 0 : 1,
                "prototype creation",
                "",
                """{"prototype_completion":{"succeeded":true},"godot_smoke":{"exit_code":0}}""");
        }

        public async Task SeedValidationOnlyRunAsync(string status)
        {
            var project = (await Store.GetProjectSnapshotAsync(ProjectId))!;
            var runId = await Store.CreateRunAsync(ProjectId, project.WorkspaceId, "prototype-7day-playable");
            await Store.MarkRunStartedAsync(runId);
            await Store.CompleteRunAsync(
                runId,
                status,
                status == "succeeded" ? 0 : 1,
                "prototype validation",
                "",
                """{"validation_only":true,"prototype_completion":{"succeeded":true},"godot_smoke":{"exit_code":0}}""");
        }

        public async Task CreateIterationSessionAsync(IReadOnlyList<string> statuses)
        {
            var session = await Store.CreateProjectIterationSessionAsync(
                AccountId,
                ProjectId,
                "manual_feedback",
                "test iteration",
                "test iteration",
                statuses.Select((_, index) => new ProjectIterationGoalCreateCommand(index + 1, $"Step {index + 1}", $"Step {index + 1} description", $"Step {index + 1} acceptance")).ToArray());

            foreach (var goal in (await Store.GetLatestProjectIterationSessionAsync(ProjectId))!.Goals)
            {
                var status = statuses[goal.GoalIndex - 1];
                await Store.UpdateProjectIterationGoalStatusAsync(
                    goal.GoalId,
                    status,
                    status == "succeeded" ? "done" : null,
                    status == "succeeded" ? DateTimeOffset.UtcNow.ToString("O") : null);
            }

            var completed = statuses.All(status => status == "succeeded");
            await Store.UpdateProjectIterationSessionStatusAsync(
                session.SessionId,
                completed ? "completed" : "paused_for_review",
                statuses.Count,
                "seeded iteration session",
                null,
                completed ? DateTimeOffset.UtcNow.ToString("O") : null);
        }

        public async Task SeedPackageRunAsync()
        {
            var project = (await Store.GetProjectSnapshotAsync(ProjectId))!;
            var packageRelativePath = Path.Combine("exports", "test-package.zip").Replace('\\', '/');
            var packagePath = Path.Combine(project.RepoPath, packageRelativePath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(packagePath)!);
            await File.WriteAllBytesAsync(packagePath, [1, 2, 3]);
            var runId = await Store.CreateRunAsync(ProjectId, project.WorkspaceId, "project-package");
            await Store.MarkRunStartedAsync(runId);
            await Store.CompleteRunAsync(runId, "succeeded", 0, "", "", "{}");
            await Store.AddArtifactAsync(new ArtifactCreationCommand(runId, ProjectId, "project-package-zip", packageRelativePath, "Package"));
        }

        public async Task SeedUiOptimizationRunAsync(string status)
        {
            var project = (await Store.GetProjectSnapshotAsync(ProjectId))!;
            var runId = await Store.CreateRunAsync(ProjectId, project.WorkspaceId, "prototype-ui-optimization");
            await Store.MarkRunStartedAsync(runId);
            await Store.CompleteRunAsync(runId, status, status == "succeeded" ? 0 : 1, "ui optimization", "", "{}");
        }

        public void Dispose()
        {
            _database.Dispose();
            _workspaceRoot.Dispose();
            _repoRoot.Dispose();
        }

        private static ProjectWorkflowRouteService CreateService(PhaseAMetadataStore store, PhaseAPlatformOptions options, string? llmJson)
        {
            var codex = new FakeCodexClient(llmJson);
            var workflow = new PrototypeWorkflowService(
                store,
                options,
                new NoopRunner(),
                new PrototypeRecordWriter(options),
                new PrototypeWorkflowCommandBuilder(options),
                new PrototypeArtifactIndexer(),
                new LlmBindingService(store, options),
                new LlmStopLossService(store, options),
                new ProjectWorkspaceSeeder(options),
                new GameTypeTemplateCatalog(options));
            var quickFix = new PrototypeQuickFixService(store, options, new NoopRunner());
            var repair = new PrototypeRepairPlanService(store, quickFix, new PrototypeRouteStateWriter(), llmRouteEngine: new LlmRouteEngine(codex));
            var packages = new ProjectPackageService(store, options);
            var inventory = new ProjectAssetInventoryService(store, options, codex, new ProjectWorkspaceSeeder(options), new LlmRouteEngine(codex));
            return new ProjectWorkflowRouteService(store, options, workflow, repair, packages, inventory, new LlmRouteEngine(codex));
        }

        private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId, string gameTypeSource)
        {
            var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
            var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", gameTypeSource, null, null, null, null));
            await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
            return result.ProjectId!;
        }
    }

    private sealed class NoopRunner : IHostedProcessRunner
    {
        public Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            throw new InvalidOperationException("This test should not execute hosted processes.");
        }
    }

    private sealed class FakeCodexClient : ICodexChatClient
    {
        private readonly string _json;

        public FakeCodexClient(string? json = null)
        {
            _json = json ?? """{"shouldRoute":false,"intent":"general_chat","routeReason":"","feedbackSummary":""}""";
        }

        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new CodexChatClientResult(true, _json, null, 0, "", ""));
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
                Directory.Delete(Path, true);
            }
        }
    }
}
