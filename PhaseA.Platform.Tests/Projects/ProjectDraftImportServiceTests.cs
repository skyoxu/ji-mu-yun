using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Projects;

public sealed class ProjectDraftImportServiceTests
{
    [Fact]
    public void Import_ReusesPlainTextFields_WithoutAutoSubmitting()
    {
        var service = Service();
        var bytes = System.Text.Encoding.UTF8.GetBytes("""
            project_name: demo-prototype
            game_name: Demo Game
            game_type_source: RPG
            proto_slug: demo-prototype
            hypothesis: test the loop
            core_player_fantasy: be a hero
            minimum_playable_loop: move, fight, win
            success_criteria: understand the goal in 30 seconds
            success_criteria: finish one loop in 90 seconds
            game_feature: combat
            core_gameplay_loop: move fight loot
            win_fail_conditions: survive three waves
            """.ReplaceLineEndings("\n"));

        var result = service.ImportPlainText("draft.txt", bytes);

        result.Status.Should().Be("succeeded");
        result.GameName.Should().Be("Demo Game");
        result.GameTypeSource.Should().Be("RPG");
        result.PrototypeSlug.Should().Be("demo-prototype");
        result.SuccessCriteria.Should().ContainInOrder("understand the goal in 30 seconds", "finish one loop in 90 seconds");
        result.Warnings.Should().BeEmpty();
        result.FailureCode.Should().BeNull();
    }

    [Fact]
    public void Import_RejectsNonTxtFiles()
    {
        var service = Service();

        var result = service.ImportPlainText("draft.md", System.Text.Encoding.UTF8.GetBytes("game_name: Demo"));

        result.Status.Should().Be("failed");
        result.FailureCode.Should().Be("txt_only");
    }

    [Fact]
    public async Task AnalyzeAsync_CallsCodexAndRecordsRun()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var codex = new FakeCodex("""
            {
              "prototypeSlug": "llm-demo",
              "hypothesis": "LLM extracts the prototype hypothesis.",
              "successCriteria": ["one clear loop"]
            }
            """);
        var service = new ProjectDraftImportService(store, options, codex);

        var result = await service.AnalyzeAsync(accountId, projectId, "draft.txt", System.Text.Encoding.UTF8.GetBytes("make a game"), "gpt-5.4");
        var run = await store.GetRunSnapshotAsync(result.RunId);

        result.Status.Should().Be("succeeded");
        result.PrototypeSlug.Should().Be("llm-demo");
        result.Hypothesis.Should().Be("LLM extracts the prototype hypothesis.");
        result.SuccessCriteria.Should().ContainSingle("one clear loop");
        run!.RunType.Should().Be("prototype-draft-analysis");
        run.Status.Should().Be("succeeded");
        var persisted = await service.GetLatestAsync(accountId, projectId);
        persisted!.PrototypeSlug.Should().Be("llm-demo");
        persisted.Hypothesis.Should().Be("LLM extracts the prototype hypothesis.");
        persisted.SuccessCriteria.Should().ContainSingle("one clear loop");
        (await store.HasRunnerLockAsync(projectId)).Should().BeFalse();
        codex.Prompts.Should().NotBeEmpty();
        codex.Prompts[0].Should().Contain("This is a pure text-to-JSON extraction task.");
        codex.Prompts[0].Should().Contain("Do not inspect the repository, docs, workflow files, rules files, or any external context.");
    }

    [Fact]
    public async Task AnalyzeAsync_RejectsProjectOwnedByAnotherAccount()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var ownerAccountId = await store.EnsureSingleAdminAsync();
        var otherAccount = await store.CreateUserAccountAsync("draft-other-account", 1);
        var projectId = await CreateProjectAsync(store, options, ownerAccountId);
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var codex = new FakeCodex("{}");
        var service = new ProjectDraftImportService(store, options, codex);

        var act = () => service.AnalyzeAsync(
            otherAccount.AccountId,
            projectId,
            "draft.txt",
            System.Text.Encoding.UTF8.GetBytes("make a game"),
            "gpt-5.4");

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("Project not found.");
        codex.Prompts.Should().BeEmpty();
    }

    [Fact]
    public async Task AnalyzeAsync_AcceptsJsonEmbeddedInCodexText()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var codex = new FakeCodex("""
            Analysis result:
            {"prototypeSlug":"embedded-json","gameFeature":"fast tactical loop","successCriteria":["playable in two minutes"]}
            """);
        var service = new ProjectDraftImportService(store, options, codex);

        var result = await service.AnalyzeAsync(accountId, projectId, "draft.txt", System.Text.Encoding.UTF8.GetBytes("prototype idea"), "gpt-5.4");

        result.Status.Should().Be("succeeded");
        result.PrototypeSlug.Should().Be("embedded-json");
        result.GameFeature.Should().Be("fast tactical loop");
        result.SuccessCriteria.Should().ContainSingle("playable in two minutes");
        result.Warnings.Should().NotContain("llm_json_parse_failed");
    }

    [Fact]
    public async Task AnalyzeAsync_UsesDeterministicFallbackForFreeformChineseDraft()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var codex = new FakeCodex("Please paste the draft first.");
        var service = new ProjectDraftImportService(store, options, codex);
        var draft = string.Join("\n",
            "\u8fd9\u662f\u4e00\u4e2a RPG \u539f\u578b\uff0c\u73a9\u5bb6\u63a2\u7d22\u5730\u56fe\u5e76\u4e0e\u654c\u4eba\u6218\u6597\u3002",
            "\u6838\u5fc3\u4f53\u9a8c\u662f\u627e\u5230\u5b9d\u7bb1\u3001\u63d0\u5347\u89d2\u8272\u3001\u51fb\u8d25 boss\u3002",
            "\u73a9\u5bb6\u5e94\u8be5\u80fd\u5728\u77ed\u65f6\u95f4\u5185\u5b8c\u6210\u4e00\u6b21\u6218\u6597\u5faa\u73af\u3002");

        var result = await service.AnalyzeAsync(accountId, projectId, "rpg.txt", System.Text.Encoding.UTF8.GetBytes(draft), "gpt-5.4");
        var persisted = await service.GetLatestAsync(accountId, projectId);

        result.Status.Should().Be("succeeded");
        result.GameName.Should().Be("Demo Game");
        result.PrototypeSlug.Should().NotBeNullOrWhiteSpace();
        result.Hypothesis.Should().NotBeNullOrWhiteSpace();
        result.GameFeature.Should().NotBeNullOrWhiteSpace();
        result.Warnings.Should().Contain("llm_json_parse_failed");
        result.Warnings.Should().NotContain("missing_game_name");
        result.CoveragePercent.Should().BeLessThan(100);
        result.CoverageMissingTopics.Should().NotBeEmpty();
        persisted!.Hypothesis.Should().Be(result.Hypothesis);
    }

    [Fact]
    public void Import_RecognizesLocalizedFieldNames()
    {
        var service = Service();
        var draft = string.Join("\n",
            "\u6e38\u620f\u540d\uff1a\u5730\u57ce\u8bd5\u70bc",
            "\u6e38\u620f\u7c7b\u578b\uff1aRPG",
            "\u6838\u5fc3\u73a9\u6cd5\uff1a\u63a2\u7d22\u3001\u6218\u6597\u3001\u6210\u957f",
            "\u6210\u529f\u6807\u51c6\uff1a\u4e24\u5206\u949f\u5185\u5b8c\u6210\u4e00\u6b21\u6218\u6597");

        var result = service.ImportPlainText("draft.txt", System.Text.Encoding.UTF8.GetBytes(draft));

        result.Status.Should().Be("succeeded");
        result.GameName.Should().Be("\u5730\u57ce\u8bd5\u70bc");
        result.GameTypeSource.Should().Be("RPG");
        result.CoreGameplayLoop.Should().Be("\u63a2\u7d22\u3001\u6218\u6597\u3001\u6210\u957f");
        result.SuccessCriteria.Should().ContainSingle("\u4e24\u5206\u949f\u5185\u5b8c\u6210\u4e00\u6b21\u6218\u6597");
        result.Warnings.Should().BeEmpty();
    }

    [Fact]
    public void Import_RecognizesMultilineLocalizedDraftFields_AndAvoidsLabelPollution()
    {
        var service = Service();
        var draft = string.Join("\n",
            "\u6e38\u620f\u540d\uff1a\u9f99\u5883\u8bd5\u70bc",
            "\u6e38\u620f\u7c7b\u578b\uff1aRPG",
            "\u539f\u578b\u6807\u8bc6 Slug\uff1a",
            "dq-rpg",
            "\u539f\u578b\u5047\u8bbe\uff1a",
            "\u590d\u53e4rpg\u52a0\u8089\u9e3d\u6210\u957f",
            "\u6210\u529f\u6807\u51c6\uff0c\u6bcf\u884c\u4e00\u6761\uff1a",
            "\u73a9\u5bb6\u80fd\u5728 30 \u79d2\u5185\u7406\u89e3\u76ee\u6807",
            "\u73a9\u5bb6\u80fd\u5728 2 \u5206\u949f\u5185\u8dd1\u5b8c\u4e00\u6b21\u5faa\u73af",
            "\u6e38\u620f\u529f\u80fd\uff1a",
            "\u5730\u56fe\u63a2\u7d22\u3001\u649e\u602a\u3001\u56de\u5408\u6218\u6597",
            "\u80dc\u5229/\u5931\u8d25\u6761\u4ef6\uff1a",
            "\u51fb\u8d25 boss \u5373\u80dc\u5229\uff0cHP \u5f52\u96f6\u5219\u5931\u8d25");

        var result = service.ImportPlainText("rpg.txt", System.Text.Encoding.UTF8.GetBytes(draft));

        result.Status.Should().Be("succeeded");
        result.GameName.Should().Be("\u9f99\u5883\u8bd5\u70bc");
        result.GameTypeSource.Should().Be("RPG");
        result.PrototypeSlug.Should().Be("dq-rpg");
        result.Hypothesis.Should().Be("\u590d\u53e4rpg\u52a0\u8089\u9e3d\u6210\u957f");
        result.GameFeature.Should().Be("\u5730\u56fe\u63a2\u7d22\u3001\u649e\u602a\u3001\u56de\u5408\u6218\u6597");
        result.WinFailConditions.Should().Be("\u51fb\u8d25 boss \u5373\u80dc\u5229\uff0cHP \u5f52\u96f6\u5219\u5931\u8d25");
        result.SuccessCriteria.Should().ContainInOrder(
            "\u73a9\u5bb6\u80fd\u5728 30 \u79d2\u5185\u7406\u89e3\u76ee\u6807",
            "\u73a9\u5bb6\u80fd\u5728 2 \u5206\u949f\u5185\u8dd1\u5b8c\u4e00\u6b21\u5faa\u73af");
        result.Warnings.Should().BeEmpty();
        result.UnparsedLines.Should().BeEmpty();
    }

    [Fact]
    public async Task AnalyzeAsync_ShouldPreferDeterministicStructuredDraftParsing_WithoutLlmWarning()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var codex = new FakeCodex("请贴出草稿正文。");
        var service = new ProjectDraftImportService(store, options, codex);
        var draft = string.Join("\n",
            "游戏名：龙境试炼",
            "游戏类型：RPG",
            "原型标识 Slug：dq-rpg",
            "原型假设：复古rpg加肉鸽成长",
            "成功标准：奖励3选1可以正确理解",
            "游戏功能：（1.游戏场景默认1600*900；2.地图场景600*600用wsad自由连续移动；3.战斗胜利选择奖励3选1。）",
            "核心玩法循环：（1.地图移动；2.概率撞怪；3.打赢怪物；4.选择成长。）",
            "胜利/失败条件：（打赢15场战斗赢得游戏胜利；任一战斗失败就游戏失败）");

        var result = await service.AnalyzeAsync(accountId, projectId, "rpg.txt", System.Text.Encoding.UTF8.GetBytes(draft), "gpt-5.4");

        result.Status.Should().Be("succeeded");
        result.Warnings.Should().NotContain("llm_json_parse_failed");
        result.CoveragePercent.Should().BeLessThan(100);
        codex.Prompts.Should().HaveCount(2);
        codex.Prompts[0].Should().Contain("coveragePercent, coverageSummary, coverageMissingTopics");
        codex.Prompts[1].Should().Contain("Retry instruction:");
    }

    [Fact]
    public async Task AnalyzeAsync_ShouldPreferLlmCoverageForStructuredDraft_AndFallbackOnlyOnCoverageFailure()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var codex = new SequenceCodex(
            """
            {
              "coveragePercent": 78,
              "coverageSummary": "当前回填覆盖了大部分核心内容，但部分数值和约束仍不够明确。",
              "coverageMissingTopics": ["地图尺寸约束", "奖励规则细节"]
            }
            """);
        var service = new ProjectDraftImportService(store, options, codex);
        var draft = string.Join("\n",
            "游戏名：龙境试炼",
            "游戏类型：RPG",
            "原型标识 Slug：dq-rpg",
            "原型假设：复古rpg加肉鸽成长",
            "成功标准：奖励3选1可以正确理解",
            "游戏功能：（1.游戏场景默认1600*900；2.地图场景600*600用wsad自由连续移动；3.战斗胜利选择奖励3选1。）",
            "核心玩法循环：（1.地图移动；2.概率撞怪；3.打赢怪物；4.选择成长。）",
            "胜利/失败条件：（打赢15场战斗赢得游戏胜利；任一战斗失败就游戏失败）");

        var result = await service.AnalyzeAsync(accountId, projectId, "rpg.txt", System.Text.Encoding.UTF8.GetBytes(draft), "gpt-5.4");

        result.Status.Should().Be("succeeded");
        result.CoveragePercent.Should().Be(78);
        result.CoverageSummary.Should().Be("当前回填覆盖了大部分核心内容，但部分数值和约束仍不够明确。");
        result.CoverageMissingTopics.Should().ContainInOrder("地图尺寸约束", "奖励规则细节");
        codex.Prompts.Should().ContainSingle();
        codex.ProjectRoots.Should().ContainSingle();
        codex.ProjectRoots[0].Should().NotContain("\\repo");
        codex.ProjectRoots[0].Should().Contain("\\_phasea_llm\\draft-import\\");
        codex.Prompts[0].Should().Contain("coveragePercent, coverageSummary, coverageMissingTopics");
        codex.Prompts[0].Should().Contain("Use only the Draft text and the Filled form JSON included below.");
        codex.Prompts[0].Should().Contain("Do not inspect or infer from repository files, implementation code, workflow docs, tests, or any external context.");
        codex.Prompts[0].Should().Contain("Do not say the draft or form was not provided.");
        codex.Options.Should().ContainSingle();
        codex.Options[0]!.OutputSchemaPath.Should().NotBeNullOrWhiteSpace();
    }

    [Fact]
    public async Task AnalyzeAsync_ShouldClampVeryHighLlmCoverage_WhenMissingTopicsExist()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var codex = new SequenceCodex(
            """
            {
              "coveragePercent": 99,
              "coverageSummary": "表单几乎完整保留了草稿内容。",
              "coverageMissingTopics": ["敌人示例数值表述存在轻微不一致"]
            }
            """);
        var service = new ProjectDraftImportService(store, options, codex);
        var draft = string.Join("\n",
            "游戏名：龙境试炼",
            "游戏类型：RPG",
            "原型标识 Slug：dq-rpg",
            "原型假设：复古rpg加肉鸽成长",
            "成功标准：奖励3选1可以正确理解",
            "游戏功能：（1.游戏场景默认1600*900；2.地图场景600*600用wsad自由连续移动；3.战斗胜利选择奖励3选1。）",
            "核心玩法循环：（1.地图移动；2.概率撞怪；3.打赢怪物；4.选择成长。）",
            "胜利/失败条件：（打赢15场战斗赢得游戏胜利；任一战斗失败就游戏失败）");

        var result = await service.AnalyzeAsync(accountId, projectId, "rpg.txt", System.Text.Encoding.UTF8.GetBytes(draft), "gpt-5.4");

        result.Status.Should().Be("succeeded");
        result.CoveragePercent.Should().Be(92);
        result.CoverageMissingTopics.Should().ContainSingle("敌人示例数值表述存在轻微不一致");
    }

    [Fact]
    public async Task AnalyzeAsync_ShouldRetryCoverageWhenFirstLlmResponseIsNotParseable()
    {
        using var database = TempSqliteDatabase.Create();
        using var workspaceRoot = TempWorkspaceRoot.Create();
        var options = Options(workspaceRoot.Path);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        await store.SetProjectBootstrapStatusAsync(projectId, "succeeded", null);
        var codex = new SequenceCodex(
            "我认为覆盖率大概是 85%，但还缺少一些规则。",
            """
            {
              "coveragePercent": 74,
              "coverageSummary": "当前回填保留了主要玩法，但仍缺少部分关键约束。",
              "coverageMissingTopics": ["战斗日志", "遇敌概率规则"]
            }
            """);
        var service = new ProjectDraftImportService(store, options, codex);
        var draft = string.Join("\n",
            "游戏名：龙境试炼",
            "游戏类型：RPG",
            "原型标识 Slug：dq-rpg",
            "原型假设：复古rpg加肉鸽成长",
            "成功标准：奖励3选1可以正确理解",
            "游戏功能：（1.游戏场景默认1600*900；2.地图场景600*600用wsad自由连续移动；3.战斗胜利选择奖励3选1。）",
            "核心玩法循环：（1.地图移动；2.概率撞怪；3.打赢怪物；4.选择成长。）",
            "胜利/失败条件：（打赢15场战斗赢得游戏胜利；任一战斗失败就游戏失败）");

        var result = await service.AnalyzeAsync(accountId, projectId, "rpg.txt", System.Text.Encoding.UTF8.GetBytes(draft), "gpt-5.4");

        result.Status.Should().Be("succeeded");
        result.CoveragePercent.Should().Be(74);
        result.CoverageMissingTopics.Should().ContainInOrder("战斗日志", "遇敌概率规则");
        codex.Prompts.Should().HaveCount(2);
        codex.Prompts[1].Should().Contain("Retry instruction:");
        codex.Options.Should().HaveCount(2);
        codex.Options.All(option => !string.IsNullOrWhiteSpace(option?.OutputSchemaPath)).Should().BeTrue();
    }

    private static ProjectDraftImportService Service()
    {
        var options = Options(Path.Combine(Path.GetTempPath(), $"phase-a-workspaces-{Guid.NewGuid():N}"));
        var store = new PhaseAMetadataStore($"Data Source={Path.Combine(Path.GetTempPath(), $"phase-a-{Guid.NewGuid():N}.db")}", options);
        return new ProjectDraftImportService(store, options, new FakeCodex("{}"));
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "manual", null, null, null, null));
        return result.ProjectId!;
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3")
        });
    }

    private sealed class FakeCodex : ICodexChatClient
    {
        private readonly string _reply;

        public FakeCodex(string reply)
        {
            _reply = reply;
        }

        public string? LastPrompt { get; private set; }
        public List<string> Prompts { get; } = [];

        public Task<CodexChatClientResult> CompleteAsync(string projectRoot, string model, string prompt, CodexChatClientOptions? options = null, string? billingApiKeyName = null, CancellationToken cancellationToken = default)
        {
            LastPrompt = prompt;
            Prompts.Add(prompt);
            return Task.FromResult(new CodexChatClientResult(true, _reply, null, 0, "", ""));
        }
    }

    private sealed class TempWorkspaceRoot : IDisposable
    {
        private TempWorkspaceRoot(string path)
        {
            Path = path;
        }

        public string Path { get; }

        public static TempWorkspaceRoot Create()
        {
            var path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"phase-a-workspaces-{Guid.NewGuid():N}");
            Directory.CreateDirectory(path);
            return new TempWorkspaceRoot(path);
        }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }

    private sealed class SequenceCodex : ICodexChatClient
    {
        private readonly Queue<string> _replies;

        public SequenceCodex(params string[] replies)
        {
            _replies = new Queue<string>(replies);
        }

        public List<string> Prompts { get; } = [];
        public List<CodexChatClientOptions?> Options { get; } = [];
        public List<string> ProjectRoots { get; } = [];

        public Task<CodexChatClientResult> CompleteAsync(string projectRoot, string model, string prompt, CodexChatClientOptions? options = null, string? billingApiKeyName = null, CancellationToken cancellationToken = default)
        {
            ProjectRoots.Add(projectRoot);
            Prompts.Add(prompt);
            Options.Add(options);
            var reply = _replies.Count > 0 ? _replies.Dequeue() : "{}";
            return Task.FromResult(new CodexChatClientResult(true, reply, null, 0, "", ""));
        }
    }
}
