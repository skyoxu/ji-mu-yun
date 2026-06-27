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
    public async Task CreateAsync_ShouldCacheSchemaForSameProjectAndModel()
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
        llm.CallCount.Should().Be(1);
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
            { "id": "loot_growth", "label": "掉落成长", "placeholder": "装备、技能、数值。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true },
            { "id": "hud_feedback", "label": "HUD反馈", "placeholder": "血量、资源、掉落提示。", "inputType": "textarea", "rows": 3, "maxLength": 500, "required": true }
          ]
        }
        """;
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

    private sealed class FakeLlmRouteEngine : ILlmRouteEngine
    {
        private readonly string _json;
        private readonly bool _succeeded;
        private readonly string? _failureCode;

        public FakeLlmRouteEngine(string json, bool succeeded = true, string? failureCode = null)
        {
            _json = json;
            _succeeded = succeeded;
            _failureCode = failureCode;
        }

        public LlmRouteRequest? LastRequest { get; private set; }
        public int CallCount { get; private set; }

        public Task<LlmRouteResult> CompleteAsync(LlmRouteRequest request, CancellationToken cancellationToken = default)
        {
            LastRequest = request;
            CallCount += 1;
            return Task.FromResult(new LlmRouteResult(
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
                1));
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
