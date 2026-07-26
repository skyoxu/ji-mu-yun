using System.Text;
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Tests.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class GameDesignSceneRouteServiceTests
{
    [Fact]
    public async Task CreateAsync_ShouldUseAgentSceneRoute_WhenLlmReturnsValidRoute()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "RPG");
        var llm = new FakeLlmRouteEngine(ValidSceneRouteJson());
        var service = new GameDesignSceneRouteService(store, options, llm);

        var result = await service.CreateAsync(
            account.AccountId,
            projectId,
            new GameDesignSceneRouteDraftRequest(
                "玩家在地图探索并进入战斗。",
                [new GameDesignQuestionAnswer("core_loop", "核心循环", "地图、战斗、奖励。", true)],
                "gpt-5.4"));

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        result.Source.Should().Be("agent");
        result.SceneRoute.SchemaVersion.Should().Be("gdd-scene-route.v1");
        result.SceneRoute.SceneCountIntent.Should().Be("multi");
        result.SceneRoute.EntryScene.Should().Be("map");
        result.SceneRoute.Scenes.Should().Contain(scene => scene.Id == "combat" && scene.M1Required);
        result.SceneRoute.Transitions.Should().Contain(transition => transition.From == "map" && transition.To == "combat");
        llm.LastRequest.Should().NotBeNull();
        llm.LastRequest!.Purpose.Should().Be("gdd-scene-route-draft");
        llm.LastRequest.RequireJsonObject.Should().BeTrue();
        llm.LastRequest.Prompt.Should().Contain("玩家在地图探索并进入战斗。");
        llm.LastRequest.Prompt.Should().Contain("地图、战斗、奖励。");
        llm.LastRequest.Prompt.Should().Contain("Default Prototype Contract");
        llm.LastRequest.Prompt.Should().Contain("Project game-type contract snapshot");
        llm.LastRequest.Prompt.Should().Contain("field_exploration");
        llm.LastRequest.Prompt.Should().Contain("combat_encounter");
        llm.LastRequest.Prompt.Should().Contain("DefaultScenes:");
        llm.LastRequest.Prompt.Should().Contain("Preserve `Always` default scenes");
    }

    [Fact]
    public async Task CreateAsync_ShouldIssueHostedContextEnvelope_ForSceneRouteDraft()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "RPG");
        var issuer = new HostedContextManifestIssuer(
            store,
            new HostedContextManifestSignatureService("test-key", new Dictionary<string, string>
            {
                ["test-key"] = "test-hosted-context-signing-secret"
            }));
        var llm = new FakeLlmRouteEngine(ValidSceneRouteJson());
        var service = new GameDesignSceneRouteService(store, options, llm, contextManifestIssuer: issuer);

        var result = await service.CreateAsync(account.AccountId, projectId, new GameDesignSceneRouteDraftRequest("route", [], "gpt-5.4"));

        result!.Source.Should().Be("agent");
        llm.LastRequest!.OperationKey.Should().Be("llm:gdd-scene-route-draft");
        llm.LastRequest.ContextEnvelope.Should().NotBeNull();
        llm.LastRequest.ContextEnvelope!.AccountId.Should().Be(account.AccountId);
        llm.LastRequest.ContextEnvelope.ProjectId.Should().Be(projectId);
        llm.LastRequest.ContextEnvelope.OperationKey.Should().Be("llm:gdd-scene-route-draft");
        llm.LastRequest.ContextEnvelope.SignatureKeyId.Should().Be("test-key");
    }

    [Fact]
    public async Task CreateAsync_ShouldReturnFallbackSceneRoute_WhenLlmFails()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "卡牌肉鸽");
        var service = new GameDesignSceneRouteService(
            store,
            options,
            new FakeLlmRouteEngine("", succeeded: false, failureCode: "model_capacity"));

        var result = await service.CreateAsync(account.AccountId, projectId, new GameDesignSceneRouteDraftRequest(""));

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        result.Source.Should().Be("fallback");
        result.FailureCode.Should().Be("model_capacity");
        result.SceneRoute.SceneCountIntent.Should().Be("multi");
        result.SceneRoute.EntryScene.Should().Be("class_selection");
        result.SceneRoute.Scenes.Should().Contain(scene => scene.Id == "class_selection" && scene.M1Required);
        result.SceneRoute.Scenes.Should().Contain(scene => scene.Id == "route_map" && scene.M1Required && scene.Role == "hub");
        result.SceneRoute.Scenes.Should().Contain(scene => scene.Id == "card_battle" && scene.M1Required);
        result.SceneRoute.Scenes.Should().Contain(scene => scene.Id == "reward_choice" && scene.M1Required && scene.Role == "reward");
        result.SceneRoute.Transitions.Should().Contain(transition => transition.From == "class_selection" && transition.To == "route_map");
        result.SceneRoute.Transitions.Should().Contain(transition => transition.From == "route_map" && transition.To == "card_battle");
        result.SceneRoute.Transitions.Should().Contain(transition => transition.From == "card_battle" && transition.To == "reward_choice");
        result.SceneRoute.Transitions.Should().Contain(transition => transition.From == "reward_choice" && transition.To == "route_map");
    }

    [Fact]
    public async Task CreateAsync_ShouldReturnNull_AndSkipLlm_WhenProjectBelongsToAnotherAccount()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var owner = await store.CreateUserAccountAsync("owner-account", 10);
        var otherAccount = await store.CreateUserAccountAsync("other-account", 10);
        var projectId = await CreateProjectAsync(store, options, owner.AccountId, "RPG");
        var llm = new FakeLlmRouteEngine(ValidSceneRouteJson());
        var service = new GameDesignSceneRouteService(store, options, llm);

        var result = await service.CreateAsync(
            otherAccount.AccountId,
            projectId,
            new GameDesignSceneRouteDraftRequest("cross-account request"));

        result.Should().BeNull();
        llm.CallCount.Should().Be(0);
    }

    [Fact]
    public async Task CreateAsync_ShouldReturnRateLimited_WhenAccountSceneRouteLimitIsExceeded()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var firstProjectId = await CreateProjectAsync(store, options, account.AccountId, "RPG");
        var secondProjectId = await CreateProjectAsync(store, options, account.AccountId, "Tower defense");
        var llm = new FakeLlmRouteEngine(ValidSceneRouteJson(), completionDelay: TimeSpan.FromMilliseconds(250));
        var limiter = new QuestionFormConcurrencyLimiter(maxConcurrentQuestionForms: 8, maxConcurrentQuestionFormsPerAccount: 1);
        var service = new GameDesignSceneRouteService(store, options, llm, limiter);

        var first = service.CreateAsync(account.AccountId, firstProjectId, new GameDesignSceneRouteDraftRequest("first"));
        await Task.Delay(25);
        var second = await service.CreateAsync(account.AccountId, secondProjectId, new GameDesignSceneRouteDraftRequest("second"));
        var firstResult = await first;

        firstResult.Should().NotBeNull();
        firstResult!.Source.Should().Be("agent");
        second.Should().NotBeNull();
        second!.Status.Should().Be("rate_limited");
        second.Source.Should().Be("none");
        second.FailureCode.Should().Be("user_gdd_scene_route_concurrency_limit_exceeded");
        llm.CallCount.Should().Be(1);
    }

    [Fact]
    public async Task CreateAsync_ShouldReturnFallbackSceneRoute_WhenGenerationTimesOut()
    {
        using var workspace = new TempWorkspace();
        using var database = TempSqliteDatabase.Create();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var account = await store.CreateUserAccountAsync("account-one", 10);
        var projectId = await CreateProjectAsync(store, options, account.AccountId, "Tower defense");
        var llm = new FakeLlmRouteEngine(ValidSceneRouteJson(), completionDelay: TimeSpan.FromMilliseconds(500));
        var service = new GameDesignSceneRouteService(
            store,
            options,
            llm,
            new QuestionFormConcurrencyLimiter(),
            sceneRouteGenerationTimeout: TimeSpan.FromMilliseconds(50));

        var result = await service.CreateAsync(account.AccountId, projectId, new GameDesignSceneRouteDraftRequest(""));

        result.Should().NotBeNull();
        result!.Status.Should().Be("ready");
        result.Source.Should().Be("fallback");
        result.FailureCode.Should().Be("scene_route_timeout");
        result.SceneRoute.Scenes.Should().Contain(scene => scene.Id == "build_phase");
        llm.CallCount.Should().Be(1);
    }

    [Fact]
    public void BuildFallbackSceneRoute_ShouldUseSingleSceneForUnknownType()
    {
        var project = new ProjectSnapshot(
            "p1",
            "account-1",
            "Mystery Prototype",
            "Mystery",
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

        var sceneRoute = GameDesignSceneRouteService.BuildFallbackSceneRoute(project);

        sceneRoute.SceneCountIntent.Should().Be("unsure");
        sceneRoute.Scenes.Should().ContainSingle(scene => scene.Id == "first_playable");
        sceneRoute.SingleSceneConfirmation.Allowed.Should().BeFalse();
    }

    [Fact]
    public void BuildFallbackSceneRoute_ShouldUseDefaultPrototypeContractScenes_WhenGuideExists()
    {
        using var workspace = new TempWorkspace();
        var options = Options(workspace.Root, Directory.GetCurrentDirectory());
        var now = DateTimeOffset.UtcNow.ToString("O");
        var project = new ProjectSnapshot(
            "p1",
            "account-1",
            "Action Prototype",
            "Action Game",
            "Action Platformer",
            "",
            false,
            "[]",
            "succeeded",
            null,
            "workspace-1",
            workspace.Root,
            Path.Combine(workspace.Root, "p1"),
            Path.Combine(workspace.Root, "p1", "runtime"),
            Path.Combine(workspace.Root, "p1", ".phasea"),
            new ProjectGameTypeMatchEvidence(
                1,
                "matched",
                "matched_by_test_genre_tags",
                "steam",
                "Action Platformer",
                "1",
                "Test App",
                ["Action", "Platformer"],
                [],
                [],
                ["action-platformer", "platformer"],
                "action-platformer",
                "docs/game-type-guides/action-platformer.md",
                20,
                [],
                "",
                "test",
                now,
                now).ToJson());

        var sceneRoute = GameDesignSceneRouteService.BuildFallbackSceneRoute(project, options);

        sceneRoute.SceneCountIntent.Should().Be("multi");
        sceneRoute.EntryScene.Should().Be("level_start");
        sceneRoute.Scenes.Should().Contain(scene => scene.Id == "level_start" && scene.M1Required);
        sceneRoute.Scenes.Should().Contain(scene => scene.Id == "traversal_combat" && scene.M1Required);
        sceneRoute.Scenes.Should().Contain(scene => scene.Id == "checkpoint_goal" && scene.M1Required);
        sceneRoute.Transitions.Should().Contain(transition => transition.From == "level_start" && transition.To == "traversal_combat");
        sceneRoute.Notes.Should().Contain(note => note.Contains("Default Prototype Contract", StringComparison.Ordinal));
    }

    [Fact]
    public void NormalizeSubmittedSceneRoute_ShouldTrimAndDropInvalidReferences()
    {
        var longText = new string('x', 500);
        var route = new GameDesignSceneRouteDocument(
            "custom-version",
            "multi",
            "地图入口",
            [
                new GameDesignSceneRouteScene("地图入口", "探索地图", "unknown-role", true, longText),
                new GameDesignSceneRouteScene("combat", "战斗场景", "combat", true, longText),
                new GameDesignSceneRouteScene("combat", "重复战斗", "combat", false, "duplicate")
            ],
            [
                new GameDesignSceneRouteTransition("地图入口", "combat", longText, "missing", ["hp", "hp", longText]),
                new GameDesignSceneRouteTransition("missing", "combat", "invalid", "", [])
            ],
            new GameDesignSingleSceneConfirmation(true, longText),
            [longText, longText]);

        var normalized = GameDesignSceneRouteService.NormalizeSubmittedSceneRoute(route);

        normalized.Should().NotBeNull();
        normalized!.SchemaVersion.Should().Be("gdd-scene-route.v1");
        normalized.EntryScene.Should().Be("combat");
        normalized.Scenes.Should().ContainSingle(scene => scene.Id == "combat");
        normalized.Scenes[0].PlayerGoal.Should().HaveLength(180);
        normalized.Transitions.Should().BeEmpty();
        normalized.SingleSceneConfirmation.Allowed.Should().BeFalse();
        normalized.SingleSceneConfirmation.Reason.Should().HaveLength(220);
        normalized.Notes.Should().ContainSingle().Which.Should().HaveLength(180);
    }

    private static string ValidSceneRouteJson()
    {
        return """
        {
          "sceneCountIntent": "multi",
          "entryScene": "map",
          "scenes": [
            { "id": "map", "name": "探索地图", "role": "hub", "m1Required": true, "playerGoal": "选择遭遇并推进路线。" },
            { "id": "combat", "name": "战斗场景", "role": "combat", "m1Required": true, "playerGoal": "击败敌人并获得奖励。" },
            { "id": "reward", "name": "奖励结算", "role": "reward", "m1Required": true, "playerGoal": "选择奖励并返回地图。" }
          ],
          "transitions": [
            { "from": "map", "to": "combat", "trigger": "点击敌人节点", "returnsTo": "reward", "stateCarried": ["hp", "gold"] },
            { "from": "combat", "to": "reward", "trigger": "胜利", "returnsTo": "map", "stateCarried": ["hp", "loot"] }
          ],
          "singleSceneConfirmation": { "allowed": false, "reason": "该类型需要地图和战斗状态。" },
          "notes": ["M1 至少保留地图、战斗和奖励。"]
        }
        """;
    }

    private static async Task<string> CreateProjectAsync(
        PhaseAMetadataStore store,
        PhaseAPlatformOptions options,
        string accountId,
        string gameType)
    {
        var service = new ProjectCreationService(
            store,
            options,
            new ProjectRuleCatalog(),
            new ProjectWorkspaceSeeder(options),
            gameTypeMatchService: new FakeGameTypeMatchService(gameType, options));
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", gameType, null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(result.ProjectId!, "succeeded", null);
        return result.ProjectId!;
    }

    private sealed class FakeGameTypeMatchService : IProjectGameTypeMatchService
    {
        private readonly string _source;
        private readonly PhaseAPlatformOptions _options;

        public FakeGameTypeMatchService(string source, PhaseAPlatformOptions options)
        {
            _source = source;
            _options = options;
        }

        public Task<ProjectGameTypeMatchEvidence> ResolveAsync(string gameTypeSource, CancellationToken cancellationToken)
        {
            var lower = _source.ToLowerInvariant();
            var matched = lower.Contains("tower", StringComparison.Ordinal)
                ? "tower-defense"
                : lower.Contains("card", StringComparison.Ordinal) || lower.Contains("卡", StringComparison.Ordinal)
                    ? "card-game"
                    : lower.Contains("rpg", StringComparison.Ordinal)
                        ? "rpg"
                        : "";
            var tags = matched switch
            {
                "tower-defense" => new[] { "tower-defense", "waves", "placement" },
                "card-game" => new[] { "card", "deck-building", "roguelike" },
                "rpg" => new[] { "rpg", "role-playing" },
                _ => []
            };
            var now = DateTimeOffset.UtcNow.ToString("O");
            var evidence = new ProjectGameTypeMatchEvidence(
                1,
                string.IsNullOrWhiteSpace(matched) ? "no_match" : "matched",
                string.IsNullOrWhiteSpace(matched) ? "test_no_match" : "matched_by_test_genre_tags",
                "steam",
                gameTypeSource,
                "1",
                "Test App",
                tags,
                [],
                tags,
                tags,
                matched,
                string.IsNullOrWhiteSpace(matched) ? "" : $"docs/game-type-guides/{matched}.md",
                string.IsNullOrWhiteSpace(matched) ? 0 : 20,
                [],
                "",
                "test",
                now,
                now);
            return Task.FromResult(evidence with
            {
                ContractSnapshot = ProjectGameTypeContractSnapshot.FromProjectMatch(_options, evidence)
            });
        }
    }

    private static PhaseAPlatformOptions Options(string workspaceRoot, string repoRoot)
    {
        return PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = workspaceRoot,
            ["PHASEA_METADATA_DB_PATH"] = Path.Combine(workspaceRoot, "metadata.sqlite3"),
            ["PHASEA_REPOSITORY_ROOT"] = ResolveRepositoryRoot(repoRoot)
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

    private sealed class FakeLlmRouteEngine : ILlmRouteEngine
    {
        private readonly string _json;
        private readonly bool _succeeded;
        private readonly string? _failureCode;
        private readonly TimeSpan _completionDelay;
        private int _callCount;

        public FakeLlmRouteEngine(
            string json,
            bool succeeded = true,
            string? failureCode = null,
            TimeSpan completionDelay = default)
        {
            _json = json;
            _succeeded = succeeded;
            _failureCode = failureCode;
            _completionDelay = completionDelay;
        }

        public LlmRouteRequest? LastRequest { get; private set; }
        public int CallCount => Volatile.Read(ref _callCount);

        public async Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            LastRequest = request;
            Interlocked.Increment(ref _callCount);
            if (_completionDelay > TimeSpan.Zero)
            {
                await Task.Delay(_completionDelay, cancellationToken);
            }

            return new LlmRouteResult(
                _succeeded,
                _json,
                _succeeded ? _json : null,
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

    private sealed class TempWorkspace : IDisposable
    {
        public TempWorkspace()
        {
            Root = Path.Combine(Path.GetTempPath(), "phasea-gdd-scene-route-tests", Guid.NewGuid().ToString("N"));
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
