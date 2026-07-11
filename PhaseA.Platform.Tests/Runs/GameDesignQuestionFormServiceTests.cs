using System.Text;
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class GameDesignQuestionFormServiceTests
{
    [Fact]
    public void ParseQuestionFormAnswers_ShouldPreserveMultilineAnswers()
    {
        const string prompt = """
        GDD question-form raw material:
        Project: deckdemo99

        Question-form answers:
        1. 参考信号: 杀戮尖塔路线选择
        2. 首个可玩场景: 职业选择场景，地图路线选择场景
         玩家进入 3 场普通战斗 + 1 场精英战斗。
        3. 战斗规则重点: 每回合 3 点能量、5 张卡牌。

        Use these answers as authoritative raw material.
        """;

        var answers = GameDesignQuestionFormRestoreService.ParseQuestionFormAnswers(prompt);

        answers.Should().HaveCount(3);
        answers[0].Label.Should().Be("参考信号");
        answers[0].Answer.Should().Be("杀戮尖塔路线选择");
        answers[1].Answer.Should().Contain("职业选择场景");
        answers[1].Answer.Should().Contain("玩家进入 3 场普通战斗");
        answers[2].Label.Should().Be("战斗规则重点");
    }

    [Fact]
    public async Task RestoreLatestAsync_ShouldReadLatestGddPromptForSameAccount()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var otherAccount = await store.CreateUserAccountAsync("account-two", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "deckbuilder");
        var project = await store.GetProjectSnapshotAsync(projectId);
        var runId = await store.CreateRunAsync(projectId, project!.WorkspaceId, "game-design-gdd");
        await store.MarkRunStartedAsync(runId);
        await store.CompleteRunAsync(runId, "succeeded", 0, "", "", "{}");
        var promptPath = Path.Combine(project.RepoPath, "logs", "phase-a-gdd", projectId, runId, "gdd-prompt.md");
        Directory.CreateDirectory(Path.GetDirectoryName(promptPath)!);
        await File.WriteAllTextAsync(
            promptPath,
            """
            Question-form answers:
            1. 参考信号: Slay the Spire route risk.
            2. 玩家幻想: Build a lean deck.
            """);
        var service = new GameDesignQuestionFormRestoreService(store, options);

        var result = await service.ReadLatestAsync(account.AccountId, projectId);
        var denied = await service.ReadLatestAsync(otherAccount.AccountId, projectId);

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        result.SourceRunId.Should().Be(runId);
        result.Answers.Should().HaveCount(2);
        result.Answers[0].Answer.Should().Be("Slay the Spire route risk.");
        denied.Should().BeNull();
    }

    [Fact]
    public async Task CreateAsync_ShouldUseAgentSchema_WhenLlmReturnsValidFields()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "Diablolike ARPG");
        var llm = new FakeLlmRouteEngine(ValidSchemaJson());
        var service = new GameDesignQuestionFormService(store, options, llm);

        var result = await service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest("gpt-5.4"));

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        result.Source.Should().Be("agent");
        result.Fields.Should().HaveCount(8);
        result.Fields[0].Id.Should().Be("reference_signal");
        result.Fields.Should().OnlyContain(field => field.InputType == "textarea");
        result.Fields.Should().OnlyContain(field => field.MaxLength >= 120 && field.MaxLength <= 700);
        llm.LastRequest.Should().NotBeNull();
        llm.LastRequest!.Purpose.Should().Be("gdd-question-form");
        llm.LastRequest.RequireJsonObject.Should().BeTrue();
        llm.LastRequest.Prompt.Should().Contain("Diablolike ARPG");
    }

    [Fact]
    public async Task CreateAsync_ShouldReturnFallbackSchema_WhenLlmFails()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "塔防");
        var service = new GameDesignQuestionFormService(
            store,
            options,
            new FakeLlmRouteEngine("", succeeded: false, failureCode: "model_capacity"));

        var result = await service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest());

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        result.Source.Should().Be("fallback");
        result.FailureCode.Should().Be("model_capacity");
        result.Fields.Should().HaveCount(10);
        result.Fields.Should().Contain(field => field.Id == "tower_map");
        result.Fields.Where(field => field.Required).Should().HaveCount(4);
        result.Fields.First(field => field.Id == "tower_map").Required.Should().BeTrue();
        result.Fields.First(field => field.Id == "reference_signal").Required.Should().BeTrue();
    }

    [Fact]
    public async Task CreateAsync_ShouldReturnFallbackSchema_WhenAgentRequiredFieldCountIsInvalid()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "Diablolike ARPG");
        var service = new GameDesignQuestionFormService(
            store,
            options,
            new FakeLlmRouteEngine(InvalidRequiredCountSchemaJson()));

        var result = await service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest());

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        result.Source.Should().Be("fallback");
        result.FailureCode.Should().Be("invalid_required_field_count");
        result.Fields.Where(field => field.Required).Should().HaveCount(count => count >= 4 && count <= 6);
    }

    [Fact]
    public async Task CreateAsync_ShouldAskLlmBeforeReusingCachedSchema()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "Diablolike ARPG");
        var llm = new FakeLlmRouteEngine(ValidSchemaJson());
        var service = new GameDesignQuestionFormService(store, options, llm);

        var first = await service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest("gpt-5.4"));
        var second = await service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest("gpt-5.4"));

        first.Should().NotBeNull();
        second.Should().NotBeNull();
        first!.Fields.Should().Equal(second!.Fields);
        llm.CallCount.Should().Be(2);
        llm.LastRequest!.Purpose.Should().Be("gdd-question-form-cache-decision");
        llm.LastRequest.Prompt.Should().Contain("Prefer reusing the cached form");
    }

    [Fact]
    public async Task CreateAsync_ShouldRebuildCachedSchema_WhenLlmRequestsRebuild()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "Diablolike ARPG");
        var llm = new FakeLlmRouteEngine(new[]
        {
            ValidSchemaJson(),
            """{ "rebuild": true, "reason": "cached schema no longer fits" }""",
            AlternateSchemaJson()
        });
        var service = new GameDesignQuestionFormService(store, options, llm);

        var first = await service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest("gpt-5.4"));
        var second = await service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest("gpt-5.4"));

        first.Should().NotBeNull();
        second.Should().NotBeNull();
        llm.CallCount.Should().Be(3);
        llm.LastRequest!.Purpose.Should().Be("gdd-question-form");
        first!.Fields.Should().NotEqual(second!.Fields);
        second.Fields[0].Id.Should().Be("reference_signal_v2");
    }

    [Fact]
    public async Task CreateAsync_ShouldCoalesceConcurrentSchemaRequestsForSameProjectAndModel()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "Diablolike ARPG");
        var llm = new FakeLlmRouteEngine(ValidSchemaJson(), completionDelay: TimeSpan.FromMilliseconds(100));
        var service = new GameDesignQuestionFormService(store, options, llm);

        var tasks = Enumerable.Range(0, 8)
            .Select(_ => service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest("gpt-5.4")))
            .ToArray();

        var results = await Task.WhenAll(tasks);

        results.Should().OnlyContain(result => result != null && result.Source == "agent");
        results.Select(result => result!.Fields).Should().OnlyContain(fields => fields.SequenceEqual(results[0]!.Fields));
        llm.CallCount.Should().Be(1);
    }

    [Fact]
    public async Task CreateAsync_ShouldKeepSharedSchemaGenerationAlive_WhenOneWaiterIsCancelled()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "Diablolike ARPG");
        var llm = new FakeLlmRouteEngine(ValidSchemaJson(), completionDelay: TimeSpan.FromMilliseconds(250));
        var service = new GameDesignQuestionFormService(store, options, llm);
        using var firstCancellation = new CancellationTokenSource();

        var first = service.CreateAsync(
            account.AccountId,
            projectId,
            new GameDesignQuestionFormRequest("gpt-5.4"),
            firstCancellation.Token);
        var second = service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest("gpt-5.4"));
        await WaitUntilAsync(() => llm.CallCount == 1 && second.Status == TaskStatus.WaitingForActivation);

        firstCancellation.Cancel();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(async () => await first);
        var secondResult = await second;

        secondResult.Should().NotBeNull();
        secondResult!.Status.Should().Be("ready");
        secondResult.Source.Should().Be("agent");
        llm.CallCount.Should().Be(1);
    }

    [Fact]
    public async Task CreateAsync_ShouldReturnRateLimited_WhenAccountQuestionFormLimitIsExceeded()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var firstProjectId = await CreateProjectAsync(store, options, account.AccountId, "Diablolike ARPG");
        var secondProjectId = await CreateProjectAsync(store, options, account.AccountId, "塔防");
        var llm = new FakeLlmRouteEngine(ValidSchemaJson(), completionDelay: TimeSpan.FromMilliseconds(250));
        var limiter = new QuestionFormConcurrencyLimiter(maxConcurrentQuestionForms: 8, maxConcurrentQuestionFormsPerAccount: 1);
        var service = new GameDesignQuestionFormService(store, options, llm, limiter);

        var first = service.CreateAsync(account.AccountId, firstProjectId, new GameDesignQuestionFormRequest("gpt-5.4"));
        await Task.Delay(25);
        var second = await service.CreateAsync(account.AccountId, secondProjectId, new GameDesignQuestionFormRequest("gpt-5.4"));
        var firstResult = await first;

        firstResult.Should().NotBeNull();
        firstResult!.Source.Should().Be("agent");
        second.Should().NotBeNull();
        second!.Status.Should().Be("rate_limited");
        second.Source.Should().Be("none");
        second.FailureCode.Should().Be("user_gdd_question_form_concurrency_limit_exceeded");
        llm.CallCount.Should().Be(1);
    }

    [Fact]
    public async Task CreateAsync_ShouldReturnFallbackSchema_WhenSchemaGenerationTimesOut()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "塔防");
        var llm = new FakeLlmRouteEngine(ValidSchemaJson(), completionDelay: TimeSpan.FromMilliseconds(500));
        var service = new GameDesignQuestionFormService(
            store,
            options,
            llm,
            new QuestionFormConcurrencyLimiter(),
            schemaGenerationTimeout: TimeSpan.FromMilliseconds(50));

        var result = await service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest());

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        result.Source.Should().Be("fallback");
        result.FailureCode.Should().Be("schema_timeout");
        result.Fields.Should().Contain(field => field.Id == "tower_map");
        llm.CallCount.Should().Be(1);

        var cached = await service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest());

        cached.Should().NotBeNull();
        cached!.FailureCode.Should().Be("schema_timeout");
        llm.CallCount.Should().Be(1);
    }

    [Fact]
    public async Task CreateAsync_ShouldReleaseQuestionFormLimit_WhenRequestIsCancelled()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var firstProjectId = await CreateProjectAsync(store, options, account.AccountId, "Diablolike ARPG");
        var secondProjectId = await CreateProjectAsync(store, options, account.AccountId, "塔防");
        var llm = new FakeLlmRouteEngine(ValidSchemaJson(), completionDelay: TimeSpan.FromMilliseconds(250));
        var limiter = new QuestionFormConcurrencyLimiter(maxConcurrentQuestionForms: 2, maxConcurrentQuestionFormsPerAccount: 1);
        var service = new GameDesignQuestionFormService(store, options, llm, limiter);
        using var cancellation = new CancellationTokenSource();

        var first = service.CreateAsync(account.AccountId, firstProjectId, new GameDesignQuestionFormRequest(), cancellation.Token);
        await Task.Delay(25);
        cancellation.Cancel();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(async () => await first);

        var second = await service.CreateAsync(account.AccountId, secondProjectId, new GameDesignQuestionFormRequest());

        second.Should().NotBeNull();
        second!.Status.Should().Be("ready");
        second.Source.Should().Be("agent");
        llm.CallCount.Should().Be(2);
    }

    [Fact]
    public async Task CreateAsync_ShouldStartReplacement_WhenSameCacheKeyIsCancelled()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "Diablolike ARPG");
        var llm = new FakeLlmRouteEngine(ValidSchemaJson(), completionDelay: TimeSpan.FromMilliseconds(250));
        var service = new GameDesignQuestionFormService(store, options, llm);
        using var cancellation = new CancellationTokenSource();

        var first = service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest(), cancellation.Token);
        await WaitUntilAsync(() => llm.CallCount == 1);
        cancellation.Cancel();
        var second = service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest());

        await Assert.ThrowsAnyAsync<OperationCanceledException>(async () => await first);
        var result = await second;

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        llm.CallCount.Should().Be(2);
    }

    [Fact]
    public async Task CreateAsync_ShouldBoundLastWaiterCleanup_WhenLlmIgnoresCancellation()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "Diablolike ARPG");
        var llm = new BlockingLlmRouteEngine(ValidSchemaJson());
        var service = new GameDesignQuestionFormService(
            store,
            options,
            llm,
            lastWaiterCleanupTimeout: TimeSpan.FromMilliseconds(50));
        using var cancellation = new CancellationTokenSource();
        var request = service.CreateAsync(account.AccountId, projectId, new GameDesignQuestionFormRequest(), cancellation.Token);
        await llm.Started;
        cancellation.Cancel();
        var cancellationResult = Assert.ThrowsAnyAsync<OperationCanceledException>(async () => await request);
        await cancellationResult.WaitAsync(TimeSpan.FromSeconds(2));
        llm.Release();
    }

    [Fact]
    public void BuildFallbackFields_ShouldUseProjectNameSignals_WhenExplicitGameTypeIsMissing()
    {
        var project = new ProjectSnapshot(
            "p1",
            "account-1",
            "Tower Defense Prototype",
            "Towerdemo2",
            "",
            "",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-1",
            "C:\\workspaces",
            "C:\\workspaces\\p1",
            "C:\\workspaces\\p1\\runtime",
            "C:\\workspaces\\p1\\.phasea");

        var fields = GameDesignQuestionFormService.BuildFallbackFields(project);

        fields.Should().Contain(field => field.Id == "tower_map");
        fields.Should().Contain(field => field.Id == "tower_loop");
    }

    private static string ValidSchemaJson()
    {
        return """
        {
          "fields": [
            { "id": "reference_signal", "label": "参考标杆", "placeholder": "参考对象和禁忌方向。", "inputType": "textarea", "rows": 2, "maxLength": 300, "required": true },
            { "id": "player_fantasy", "label": "玩家幻想", "placeholder": "玩家第一分钟的感受。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true },
            { "id": "combat_loop", "label": "战斗循环", "placeholder": "进入、战斗、掉落、回城。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true },
            { "id": "first_dungeon", "label": "首个地牢", "placeholder": "地图、敌人、目标。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true },
            { "id": "controls_camera", "label": "操作视角", "placeholder": "移动、技能、镜头。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true },
            { "id": "pressure_fail", "label": "压力失败", "placeholder": "受压和失败条件。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true },
            { "id": "loot_growth", "label": "掉落成长", "placeholder": "装备、技能、数值。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false },
            { "id": "hud_feedback", "label": "HUD反馈", "placeholder": "血量、资源、掉落提示。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false }
          ]
        }
        """;
    }

    private static string InvalidRequiredCountSchemaJson()
    {
        return """
        {
          "fields": [
            { "id": "reference_signal", "label": "参考标杆", "placeholder": "参考对象和禁忌方向。", "inputType": "textarea", "rows": 2, "maxLength": 300, "required": false },
            { "id": "player_fantasy", "label": "玩家幻想", "placeholder": "玩家第一分钟的感受。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false },
            { "id": "combat_loop", "label": "战斗循环", "placeholder": "进入、战斗、掉落、回城。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false },
            { "id": "first_dungeon", "label": "首个地牢", "placeholder": "地图、敌人、目标。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false },
            { "id": "controls_camera", "label": "操作视角", "placeholder": "移动、技能、镜头。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false },
            { "id": "pressure_fail", "label": "压力失败", "placeholder": "受压和失败条件。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false },
            { "id": "loot_growth", "label": "掉落成长", "placeholder": "装备、技能、数值。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false },
            { "id": "hud_feedback", "label": "HUD反馈", "placeholder": "血量、资源、掉落提示。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": false }
          ]
        }
        """;
    }

    private static string AlternateSchemaJson()
    {
        return ValidSchemaJson()
            .Replace("\"reference_signal\"", "\"reference_signal_v2\"", StringComparison.Ordinal)
            .Replace("\"参考标杆\"", "\"新版参考标杆\"", StringComparison.Ordinal);
    }

    private static async Task<string> CreateProjectAsync(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        string accountId,
        string gameType)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", gameType, null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
        return result.ProjectId!;
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot)
    {
        var resolvedRepoRoot = ResolveRepositoryRoot(repoRoot);
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = resolvedRepoRoot
        });
    }

    private static string ResolveRepositoryRoot(string repoRoot)
    {
        var full = Path.GetFullPath(repoRoot);
        if (File.Exists(Path.Combine(full, "docs", "game-type-guides", "game-types.csv")))
        {
            return full;
        }

        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "docs", "game-type-guides", "game-types.csv")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return full;
    }

    private static async Task WaitUntilAsync(Func<bool> condition)
    {
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(5));
        while (!condition())
        {
            await Task.Delay(10, timeout.Token);
        }
    }

    private sealed class FakeLlmRouteEngine : ILlmRouteEngine
    {
        private readonly Queue<string> _jsonResponses;
        private readonly bool _succeeded;
        private readonly string? _failureCode;
        private readonly TimeSpan _completionDelay;
        private readonly bool _ignoreCancellation;
        private int _callCount;

        public FakeLlmRouteEngine(
            string json,
            bool succeeded = true,
            string? failureCode = null,
            TimeSpan completionDelay = default,
            bool ignoreCancellation = false)
            : this(new[] { json }, succeeded, failureCode, completionDelay, ignoreCancellation)
        {
        }

        public FakeLlmRouteEngine(
            IEnumerable<string> jsonResponses,
            bool succeeded = true,
            string? failureCode = null,
            TimeSpan completionDelay = default,
            bool ignoreCancellation = false)
        {
            _jsonResponses = new Queue<string>(jsonResponses);
            _succeeded = succeeded;
            _failureCode = failureCode;
            _completionDelay = completionDelay;
            _ignoreCancellation = ignoreCancellation;
        }

        public LlmRouteRequest? LastRequest { get; private set; }
        public int CallCount => Volatile.Read(ref _callCount);

        public async Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            LastRequest = request;
            Interlocked.Increment(ref _callCount);
            if (_completionDelay > TimeSpan.Zero)
            {
                await Task.Delay(_completionDelay, _ignoreCancellation ? CancellationToken.None : cancellationToken);
            }

            var json = _jsonResponses.Count > 1
                ? _jsonResponses.Dequeue()
                : _jsonResponses.Peek();

            return new LlmRouteResult(
                _succeeded,
                json,
                _succeeded ? json : null,
                request.Model,
                _failureCode,
                null,
                _succeeded ? 0 : 1,
                "",
                "",
                null,
                1,
                request.Prompt.Length,
                Encoding.UTF8.GetByteCount(request.Prompt),
                1);
        }
    }

    private sealed class BlockingLlmRouteEngine(string json) : ILlmRouteEngine
    {
        private readonly TaskCompletionSource _started = new(TaskCreationOptions.RunContinuationsAsynchronously);
        private readonly TaskCompletionSource _release = new(TaskCreationOptions.RunContinuationsAsynchronously);

        public Task Started => _started.Task;

        public void Release()
        {
            _release.TrySetResult();
        }

        public async Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            _started.TrySetResult();
            await _release.Task;
            return new LlmRouteResult(
                true,
                json,
                json,
                request.Model,
                null,
                null,
                0,
                "",
                "",
                null,
                1,
                request.Prompt.Length,
                Encoding.UTF8.GetByteCount(request.Prompt),
                1);
        }
    }

    private sealed class TempWorkspace : IDisposable
    {
        public TempWorkspace()
        {
            Root = Path.Combine(Path.GetTempPath(), "phasea-gdd-question-form-tests", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Root);
        }

        public string Root { get; }

        public void Dispose()
        {
            try
            {
                if (Directory.Exists(Root))
                {
                    Directory.Delete(Root, recursive: true);
                }
            }
            catch
            {
                // Test cleanup best effort.
            }
        }
    }
}
