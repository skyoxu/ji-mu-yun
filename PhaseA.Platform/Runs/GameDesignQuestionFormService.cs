using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;

namespace PhaseA.Platform.Runs;

public sealed class GameDesignQuestionFormService
{
    private const string SchemaVersion = "gdd-question-form.v1";
    private const int MinFields = 8;
    private const int MaxFields = 12;
    private const int MinRequiredFields = 4;
    private const int MaxRequiredFields = 6;
    private const int DefaultMaxLength = 500;
    private const int MaxSchemaCacheEntries = 128;
    private static readonly TimeSpan AgentSchemaCacheTtl = TimeSpan.FromMinutes(5);
    private static readonly TimeSpan FallbackSchemaCacheTtl = TimeSpan.FromSeconds(30);
    private static readonly TimeSpan DefaultSchemaGenerationTimeout = TimeSpan.FromSeconds(120);

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly ILlmRouteEngine _llmRouteEngine;
    private readonly QuestionFormConcurrencyLimiter _concurrencyLimiter;
    private readonly TimeSpan _schemaGenerationTimeout;
    private readonly object _cacheLock = new();
    private readonly Dictionary<string, CachedQuestionFormSchema> _schemaCache = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Task<GameDesignQuestionFormResult>> _inFlightSchemas = new(StringComparer.Ordinal);

    private sealed record CachedQuestionFormSchema(
        GameDesignQuestionFormResult Result,
        DateTimeOffset ExpiresAt);

    public GameDesignQuestionFormService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        ILlmRouteEngine llmRouteEngine,
        QuestionFormConcurrencyLimiter? concurrencyLimiter = null,
        TimeSpan? schemaGenerationTimeout = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _llmRouteEngine = llmRouteEngine;
        _concurrencyLimiter = concurrencyLimiter ?? new QuestionFormConcurrencyLimiter();
        _schemaGenerationTimeout = schemaGenerationTimeout ?? DefaultSchemaGenerationTimeout;
    }

    public async Task<GameDesignQuestionFormResult?> CreateAsync(
        string accountId,
        string projectId,
        GameDesignQuestionFormRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return null;
        }

        var model = PrototypeModelPolicy.Normalize(request.Model);
        var cacheKey = CacheKey(project, model);
        if (TryReadCache(cacheKey, out var cached))
        {
            return cached;
        }

        var schemaTask = GetOrStartSchemaTask(cacheKey, project, model, accountId, cancellationToken);
        return await schemaTask.WaitAsync(cancellationToken);
    }

    private Task<GameDesignQuestionFormResult> GetOrStartSchemaTask(
        string cacheKey,
        ProjectSnapshot project,
        string model,
        string accountId,
        CancellationToken cancellationToken)
    {
        lock (_cacheLock)
        {
            if (TryReadCacheLocked(cacheKey, DateTimeOffset.UtcNow, out var cached))
            {
                return Task.FromResult(cached!);
            }

            if (_inFlightSchemas.TryGetValue(cacheKey, out var existing))
            {
                return existing;
            }

            var task = CreateAndCacheSchemaAsync(cacheKey, project, model, accountId, cancellationToken);
            _inFlightSchemas[cacheKey] = task;
            return task;
        }
    }

    private async Task<GameDesignQuestionFormResult> CreateAndCacheSchemaAsync(
        string cacheKey,
        ProjectSnapshot project,
        string model,
        string accountId,
        CancellationToken cancellationToken)
    {
        try
        {
            return await CreateAndCacheSchemaCoreAsync(cacheKey, project, model, accountId, cancellationToken);
        }
        finally
        {
            lock (_cacheLock)
            {
                _inFlightSchemas.Remove(cacheKey);
            }
        }
    }

    private async Task<GameDesignQuestionFormResult> CreateAndCacheSchemaCoreAsync(
        string cacheKey,
        ProjectSnapshot project,
        string model,
        string accountId,
        CancellationToken cancellationToken)
    {
        var concurrency = await _concurrencyLimiter.TryAcquireAsync(accountId, cancellationToken);
        if (concurrency.Lease is null)
        {
            return RateLimited(project, concurrency.FailureCode ?? "gdd_question_form_concurrency_limit_exceeded");
        }

        await using var lease = concurrency.Lease;
        using var timeout = new CancellationTokenSource(_schemaGenerationTimeout);
        using var linkedCancellation = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, timeout.Token);
        var prompt = BuildPrompt(project);
        LlmRouteResult completion;
        try
        {
            completion = await _llmRouteEngine.CompleteAsync(
                new LlmRouteRequest(
                    WorkspaceRoot: ResolveLlmWorkspace(project),
                    Purpose: "gdd-question-form",
                    Model: model,
                    Prompt: prompt,
                    Options: new CodexChatClientOptions(ReasoningEffort: "low"),
                    BillingAccountId: accountId,
                    RequireJsonObject: true),
                linkedCancellation.Token);
        }
        catch (OperationCanceledException) when (timeout.IsCancellationRequested)
        {
            return Cache(cacheKey, Fallback(project, "schema_timeout"), FallbackSchemaCacheTtl);
        }

        if (!completion.Succeeded || string.IsNullOrWhiteSpace(completion.JsonObjectText))
        {
            return Cache(cacheKey, Fallback(project, completion.FailureCode ?? "llm_failed"), FallbackSchemaCacheTtl);
        }

        try
        {
            var fields = ParseFields(completion.JsonObjectText);
            if (fields.Count is < MinFields or > MaxFields)
            {
                return Cache(cacheKey, Fallback(project, "invalid_field_count"), FallbackSchemaCacheTtl);
            }

            var requiredFieldCount = fields.Count(field => field.Required);
            if (requiredFieldCount is < MinRequiredFields or > MaxRequiredFields)
            {
                return Cache(cacheKey, Fallback(project, "invalid_required_field_count"), FallbackSchemaCacheTtl);
            }

            return Cache(cacheKey, new GameDesignQuestionFormResult(
                "ready",
                project.ProjectId,
                SchemaVersion,
                "创建策划大纲",
                GameType(project),
                fields,
                "agent"), AgentSchemaCacheTtl);
        }
        catch (JsonException)
        {
            return Cache(cacheKey, Fallback(project, "invalid_json"), FallbackSchemaCacheTtl);
        }
    }

    private GameDesignQuestionFormResult Fallback(ProjectSnapshot project, string failureCode)
    {
        return new GameDesignQuestionFormResult(
            "ready",
            project.ProjectId,
            SchemaVersion,
            "创建策划大纲",
            GameType(project),
            BuildFallbackFields(project),
            "fallback",
            failureCode);
    }

    private GameDesignQuestionFormResult RateLimited(ProjectSnapshot project, string failureCode)
    {
        return new GameDesignQuestionFormResult(
            "rate_limited",
            project.ProjectId,
            SchemaVersion,
            "创建策划大纲",
            GameType(project),
            [],
            "none",
            failureCode);
    }

    private string ResolveLlmWorkspace(ProjectSnapshot project)
    {
        if (!string.IsNullOrWhiteSpace(project.WorkspaceRootPath))
        {
            return project.WorkspaceRootPath;
        }

        return Path.Combine(_options.HostedWorkspaceRoot, "_gdd-question-form");
    }

    private static string BuildPrompt(ProjectSnapshot project)
    {
        return $$"""
        Return JSON object only. Plan a question-form for collecting raw user input before a Game Design Document outline route starts.

        Project:
        - Project id: {{project.ProjectId}}
        - Game name: {{project.GameName}}
        - Project name: {{project.Name}}
        - Game type source: {{project.GameTypeSource}}
        - Template rule id: {{project.TemplateRuleId}}

        Requirements:
        - Do not write the GDD.
        - Ask 8 to 12 high-signal questions tailored to the current game type.
        - Questions must collect source material for a GDD outline: reference signals, player fantasy, core loop, first playable scene, controls/camera, challenge/failure, progression/rewards, UI feedback, scope boundaries, and acceptance criteria.
        - Prefer concrete game-type-specific wording over generic product questions.
        - Return:
          {
            "fields": [
              {
                "id": "safe_snake_case_id",
                "label": "short Chinese label",
                "placeholder": "Chinese placeholder with examples",
                "inputType": "textarea",
                "rows": 2 or 3 or 4,
                "maxLength": 120 to 700,
                "required": true
              }
            ]
          }
        - Use only textarea inputType.
        - Use unique ASCII snake_case ids.
        - Mark 4 to 6 essential fields as required=true. Mark the remaining useful but optional fields as required=false.
        - Keep labels under 32 characters and placeholders under 120 characters.
        """;
    }

    private static IReadOnlyList<GameDesignQuestionFormField> ParseFields(string json)
    {
        using var document = JsonDocument.Parse(json);
        if (!document.RootElement.TryGetProperty("fields", out var fieldsElement) ||
            fieldsElement.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        var fields = new List<GameDesignQuestionFormField>();
        var usedIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var item in fieldsElement.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object)
            {
                continue;
            }

            var label = Truncate(ReadString(item, "label"), 32);
            if (string.IsNullOrWhiteSpace(label))
            {
                continue;
            }

            var id = NormalizeId(ReadString(item, "id"));
            if (string.IsNullOrWhiteSpace(id))
            {
                id = NormalizeId(label);
            }

            if (string.IsNullOrWhiteSpace(id) || !usedIds.Add(id))
            {
                continue;
            }

            var placeholder = Truncate(ReadString(item, "placeholder"), 120);
            var rows = Clamp(ReadInt(item, "rows", 3), 2, 4);
            var maxLength = Clamp(ReadInt(item, "maxLength", DefaultMaxLength), 120, 700);
            var required = ReadBoolean(item, "required", false);
            fields.Add(new GameDesignQuestionFormField(
                id,
                label,
                placeholder,
                "textarea",
                rows,
                maxLength,
                required));

            if (fields.Count == MaxFields)
            {
                break;
            }
        }

        return fields;
    }

    internal static IReadOnlyList<GameDesignQuestionFormField> BuildFallbackFields(ProjectSnapshot project)
    {
        var fields = new List<GameDesignQuestionFormField>
        {
            Field("reference_signal", "参考游戏或体验标杆", ReferencePlaceholder(project), 2, true),
            Field("player_fantasy", "玩家核心幻想", "玩家在 1 分钟内应该感到自己在做什么、变强什么、承担什么风险。", required: true),
            Field("core_loop", "核心循环", "进入场景、做选择、获得反馈、成长或失败、再次尝试的循环。", required: true),
            Field("first_scene", "首个可玩场景", "首个场景里要出现的地图、对象、敌人、目标、交互或事件。", required: true),
            Field("controls_camera", "操作、视角与基础手感", "移动、点击、键鼠输入、镜头、节奏、碰撞或命中反馈。"),
            Field("challenge_fail", "主要挑战与失败条件", "玩家如何受压、如何犯错、失败或损失如何发生。"),
            Field("progression_reward", "成长、奖励与解锁", "局内/局外成长、资源、装备、技能、卡牌、关卡或剧情推进。"),
            Field("ui_feedback", "UI/HUD 与玩家反馈", "必须显示的状态、提示、数值、按钮、战斗/交互反馈。"),
            Field("scope_boundaries", "首版范围边界", "本次 GDD 和首个原型必须做什么，明确不做什么。"),
            Field("acceptance", "验收标准", "怎样判断 GDD 和第一个可玩版本是成功的。")
        };

        var normalized = GameType(project).ToLowerInvariant();
        if (ContainsAny(normalized, "rpg", "role", "jrpg", "crpg", "arpg", "diablo", "dungeon"))
        {
            fields[3] = Field("rpg_scene", "首个可探索区域", "区域布局、NPC/敌人、事件、入口出口、互动对象。", required: true);
            fields[5] = Field("rpg_conflict", "战斗/冲突/遭遇", "遇敌方式、回合或即时规则、角色能力、胜负反馈。");
            fields[6] = Field("rpg_growth", "角色成长与叙事推进", "等级、装备、技能、任务、剧情或队伍状态如何推进。");
        }
        else if (ContainsAny(normalized, "deck", "card", "牌", "卡"))
        {
            fields[2] = Field("deck_loop", "牌局核心循环", "抽牌、出牌、资源、敌方回合、结算、奖励和下一场。", required: true);
            fields[5] = Field("deck_pressure", "敌人压力与失败条件", "敌人意图、伤害、状态、倒计时或资源枯竭。");
            fields[6] = Field("deck_growth", "卡组构筑与奖励", "新增卡、删卡、升级、遗物、货币、路线选择。");
        }
        else if (ContainsAny(normalized, "survivor", "arena", "吸血鬼", "割草", "幸存"))
        {
            fields[2] = Field("survivors_loop", "单局战斗循环", "移动、自动/手动攻击、拾取、升级、敌潮、坚持或撤离。", required: true);
            fields[5] = Field("survivors_pressure", "敌潮、精英与生存压力", "敌人类型、刷怪节奏、危险升级、失败原因。");
            fields[6] = Field("survivors_build", "升级、构筑与局外成长", "局内升级选择、武器组合、被动、局外解锁。");
        }
        else if (ContainsAny(normalized, "tower", "defen", "塔防"))
        {
            fields[2] = Field("tower_loop", "波次防守循环", "布防、出怪、战斗、结算、升级、下一波。", required: true);
            fields[3] = Field("tower_map", "首张防守地图", "路径、入口出口、建造点、阻挡、目标生命或基地。", required: true);
            fields[6] = Field("tower_economy", "塔、敌人与经济", "塔类型、升级、费用、敌人护甲/速度/特殊能力、收益。");
        }

        return fields;
    }

    private static GameDesignQuestionFormField Field(string id, string label, string placeholder, int rows = 3, bool required = false)
    {
        return new GameDesignQuestionFormField(id, label, placeholder, "textarea", rows, DefaultMaxLength, required);
    }

    private static string GameType(ProjectSnapshot project)
    {
        return string.Join(
            " ",
            new[] { project.GameTypeSource, project.TemplateRuleId, project.GameName, project.Name }
                .Where(item => !string.IsNullOrWhiteSpace(item)))
            .Trim();
    }

    private static string ReferencePlaceholder(ProjectSnapshot project)
    {
        return string.IsNullOrWhiteSpace(project.GameName)
            ? "例如参考对象、想保留的体验、明确不想要的方向。"
            : $"{project.GameName} 的参考对象、体验目标和禁忌方向。";
    }

    private static string ReadString(JsonElement element, string propertyName)
    {
        return element.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String
            ? property.GetString()?.Trim() ?? ""
            : "";
    }

    private static int ReadInt(JsonElement element, string propertyName, int fallback)
    {
        return element.TryGetProperty(propertyName, out var property) && property.TryGetInt32(out var value)
            ? value
            : fallback;
    }

    private static bool ReadBoolean(JsonElement element, string propertyName, bool fallback)
    {
        return element.TryGetProperty(propertyName, out var property) && property.ValueKind is JsonValueKind.True or JsonValueKind.False
            ? property.GetBoolean()
            : fallback;
    }

    private static string NormalizeId(string value)
    {
        var chars = new List<char>();
        var previousUnderscore = false;
        foreach (var c in value.Trim().ToLowerInvariant())
        {
            if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9'))
            {
                chars.Add(c);
                previousUnderscore = false;
                continue;
            }

            if (c == '_' || c == '-' || char.IsWhiteSpace(c))
            {
                if (!previousUnderscore && chars.Count > 0)
                {
                    chars.Add('_');
                    previousUnderscore = true;
                }
            }
        }

        return new string(chars.ToArray()).Trim('_');
    }

    private static string Truncate(string value, int maxLength)
    {
        return value.Length <= maxLength ? value : value[..maxLength].Trim();
    }

    private static int Clamp(int value, int min, int max)
    {
        return Math.Min(max, Math.Max(min, value));
    }

    private static bool ContainsAny(string value, params string[] candidates)
    {
        return candidates.Any(candidate => value.Contains(candidate, StringComparison.OrdinalIgnoreCase));
    }

    private bool TryReadCache(string cacheKey, out GameDesignQuestionFormResult? result)
    {
        lock (_cacheLock)
        {
            return TryReadCacheLocked(cacheKey, DateTimeOffset.UtcNow, out result);
        }
    }

    private bool TryReadCacheLocked(
        string cacheKey,
        DateTimeOffset now,
        out GameDesignQuestionFormResult? result)
    {
        if (_schemaCache.TryGetValue(cacheKey, out var cached) && cached.ExpiresAt > now)
        {
            result = cached.Result;
            return true;
        }

        _schemaCache.Remove(cacheKey);
        result = null;
        return false;
    }

    private GameDesignQuestionFormResult Cache(
        string cacheKey,
        GameDesignQuestionFormResult result,
        TimeSpan ttl)
    {
        lock (_cacheLock)
        {
            var now = DateTimeOffset.UtcNow;
            _schemaCache[cacheKey] = new CachedQuestionFormSchema(result, now.Add(ttl));
            PruneCacheLocked(now);
        }

        return result;
    }

    private void PruneCacheLocked(DateTimeOffset now)
    {
        foreach (var key in _schemaCache
            .Where(item => item.Value.ExpiresAt <= now)
            .Select(item => item.Key)
            .ToArray())
        {
            _schemaCache.Remove(key);
        }

        if (_schemaCache.Count <= MaxSchemaCacheEntries)
        {
            return;
        }

        foreach (var key in _schemaCache
            .OrderBy(item => item.Value.ExpiresAt)
            .Take(_schemaCache.Count - MaxSchemaCacheEntries)
            .Select(item => item.Key)
            .ToArray())
        {
            _schemaCache.Remove(key);
        }
    }

    private static string CacheKey(ProjectSnapshot project, string model)
    {
        return string.Join(
            "|",
            project.AccountId,
            project.ProjectId,
            model,
            project.GameName,
            project.GameTypeSource,
            project.TemplateRuleId);
    }
}
