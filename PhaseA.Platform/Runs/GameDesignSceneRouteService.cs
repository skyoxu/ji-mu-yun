using System.Text.Json;
using System.Security.Cryptography;
using System.Text;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Prototypes;

namespace PhaseA.Platform.Runs;

public sealed class GameDesignSceneRouteService
{
    private const string SchemaVersion = "gdd-scene-route.v1";
    private const int MaxMessageChars = 6000;
    private const int MaxAnswers = 16;
    private const int MaxAnswerChars = 700;
    private const int MinScenes = 1;
    private const int MaxScenes = 8;
    private const int MaxTransitions = 16;
    private static readonly TimeSpan DefaultSceneRouteGenerationTimeout = TimeSpan.FromSeconds(120);

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly ILlmRouteEngine _llmRouteEngine;
    private readonly QuestionFormConcurrencyLimiter _concurrencyLimiter;
    private readonly ProjectGameTypeMatchBackfillService? _gameTypeMatchBackfill;
    private readonly TimeSpan _sceneRouteGenerationTimeout;
    private readonly HostedContextManifestIssuer? _contextManifestIssuer;

    public GameDesignSceneRouteService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        ILlmRouteEngine llmRouteEngine,
        QuestionFormConcurrencyLimiter? concurrencyLimiter = null,
        ProjectGameTypeMatchBackfillService? gameTypeMatchBackfill = null,
        TimeSpan? sceneRouteGenerationTimeout = null,
        HostedContextManifestIssuer? contextManifestIssuer = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _llmRouteEngine = llmRouteEngine;
        _concurrencyLimiter = concurrencyLimiter ?? new QuestionFormConcurrencyLimiter();
        _gameTypeMatchBackfill = gameTypeMatchBackfill;
        _sceneRouteGenerationTimeout = sceneRouteGenerationTimeout ?? DefaultSceneRouteGenerationTimeout;
        _contextManifestIssuer = contextManifestIssuer;
    }

    public async Task<GameDesignSceneRouteDraftResult?> CreateAsync(
        string accountId,
        string projectId,
        GameDesignSceneRouteDraftRequest request,
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
        if (_gameTypeMatchBackfill is not null)
        {
            project = await _gameTypeMatchBackfill.EnsureResolvedAsync(project, cancellationToken);
        }

        var message = Trim(request.Message, MaxMessageChars);
        var answers = NormalizeAnswers(request.Answers);
        var model = PrototypeModelPolicy.Normalize(request.Model);

        var concurrency = await _concurrencyLimiter.TryAcquireAsync(accountId, cancellationToken);
        if (concurrency.Lease is null)
        {
            return RateLimited(project, SceneRouteConcurrencyFailureCode(concurrency.FailureCode));
        }

        await using var lease = concurrency.Lease;
        using var timeout = new CancellationTokenSource(_sceneRouteGenerationTimeout);
        using var linkedCancellation = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, timeout.Token);
        HostedContextEnvelope? envelope;
        try
        {
            envelope = _contextManifestIssuer is null
                ? null
                : await _contextManifestIssuer.IssueAsync(
                    new HostedContextManifestIssue(
                        accountId,
                        project.ProjectId,
                        "llm:gdd-scene-route-draft",
                        BuildContextSnapshotId(project),
                        SchemaVersion,
                        TimeSpan.FromMinutes(5)),
                    linkedCancellation.Token);
        }
        catch (InvalidOperationException)
        {
            return Fallback(project, "context_manifest_issue_failed");
        }

        LlmRouteResult completion;
        try
        {
            completion = await _llmRouteEngine.CompleteAsync(
                new LlmRouteRequest(
                    WorkspaceRoot: ResolveLlmWorkspace(project),
                    Purpose: "gdd-scene-route-draft",
                    Model: model,
                    Prompt: BuildPrompt(project, message, answers),
                    Options: new CodexChatClientOptions(ReasoningEffort: "low"),
                    BillingAccountId: accountId,
                    RequireJsonObject: true,
                    OperationKey: "llm:gdd-scene-route-draft",
                    ContextEnvelope: envelope),
                linkedCancellation.Token);
        }
        catch (OperationCanceledException) when (timeout.IsCancellationRequested)
        {
            return Fallback(project, "scene_route_timeout");
        }
        catch (JsonException)
        {
            return Fallback(project, "invalid_json");
        }

        if (!completion.Succeeded || string.IsNullOrWhiteSpace(completion.JsonObjectText))
        {
            return Fallback(project, completion.FailureCode ?? "llm_failed");
        }

        try
        {
            var parsed = ParseSceneRoute(completion.JsonObjectText);
            if (parsed is null)
            {
                return Fallback(project, "invalid_scene_route");
            }

            return new GameDesignSceneRouteDraftResult("ready", project.ProjectId, parsed, "agent");
        }
        catch (JsonException)
        {
            return Fallback(project, "invalid_json");
        }
    }

    private static string BuildContextSnapshotId(ProjectSnapshot project)
    {
        var source = string.Join("\n", project.ProjectId, project.AccountId, project.GameName, project.GameTypeSource, project.WorkspaceId);
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(source))).ToLowerInvariant();
    }

    internal static GameDesignSceneRouteDocument? NormalizeSubmittedSceneRoute(GameDesignSceneRouteDocument? sceneRoute)
    {
        if (sceneRoute is null)
        {
            return null;
        }

        var scenes = NormalizeScenes(sceneRoute.Scenes);
        if (scenes.Count is < MinScenes or > MaxScenes)
        {
            return null;
        }

        var sceneIds = scenes.Select(scene => scene.Id).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var entryScene = NormalizeId(sceneRoute.EntryScene);
        if (string.IsNullOrWhiteSpace(entryScene) || !sceneIds.Contains(entryScene))
        {
            entryScene = scenes[0].Id;
        }

        var transitions = NormalizeTransitions(sceneRoute.Transitions, sceneIds);
        var intent = NormalizeIntent(sceneRoute.SceneCountIntent);
        var confirmation = new GameDesignSingleSceneConfirmation(
            sceneRoute.SingleSceneConfirmation?.Allowed == true && scenes.Count == 1 && intent == "single",
            Trim(sceneRoute.SingleSceneConfirmation?.Reason, 220));
        var notes = NormalizeStringList(sceneRoute.Notes, 8, 180);

        return new GameDesignSceneRouteDocument(
            SchemaVersion,
            intent,
            entryScene,
            scenes,
            transitions,
            confirmation,
            notes);
    }

    internal static GameDesignSceneRouteDocument BuildFallbackSceneRoute(
        ProjectSnapshot project,
        PhaseAPlatformOptions? options = null)
    {
        var defaultContractRoute = BuildFallbackSceneRouteFromDefaultContract(project, options);
        if (defaultContractRoute is not null)
        {
            return defaultContractRoute;
        }

        var gameType = GameType(project).ToLowerInvariant();
        if (ContainsAny(gameType, "deck", "card", "牌", "卡"))
        {
            return Document(
                "multi",
                "route_map",
                [
                    Scene("route_map", "路线地图", "hub", true, "选择下一场遭遇或奖励节点。"),
                    Scene("combat", "牌局战斗", "combat", true, "通过抽牌、出牌和资源管理击败敌人。"),
                    Scene("reward", "战斗奖励", "reward", true, "选择卡牌、资源或构筑奖励后回到路线。")
                ],
                [
                    Transition("route_map", "combat", "选择敌人节点", "reward", ["hp", "deck", "gold", "route_progress"]),
                    Transition("combat", "reward", "战斗胜利", "route_map", ["hp", "deck", "gold", "rewards"]),
                    Transition("reward", "route_map", "确认奖励", "", ["hp", "deck", "gold", "route_progress"])
                ],
                "卡牌构筑原型通常至少需要路线/战斗/奖励三个体验状态。");
        }

        if (ContainsAny(gameType, "rpg", "role", "jrpg", "crpg", "arpg", "diablo", "dungeon"))
        {
            return Document(
                "multi",
                "exploration",
                [
                    Scene("exploration", "探索地图", "hub", true, "移动、发现目标并触发遭遇。"),
                    Scene("combat", "战斗遭遇", "combat", true, "处理敌人压力、技能和胜负反馈。"),
                    Scene("reward", "结算反馈", "reward", false, "展示奖励、成长或剧情推进。")
                ],
                [
                    Transition("exploration", "combat", "接触敌人、事件或入口", "exploration", ["hp", "inventory", "quest_progress"]),
                    Transition("combat", "reward", "战斗胜利或事件完成", "exploration", ["hp", "loot", "quest_progress"]),
                    Transition("reward", "exploration", "确认结算", "", ["hp", "inventory", "quest_progress"])
                ],
                "RPG/ARPG 原型通常不应只剩一个静态场景；至少要明确探索和遭遇之间的状态交接。");
        }

        if (ContainsAny(gameType, "survivor", "arena", "吸血鬼", "割草", "幸存"))
        {
            return Document(
                "multi",
                "arena",
                [
                    Scene("arena", "生存战斗场", "gameplay", true, "移动、攻击、拾取经验并承受敌潮压力。"),
                    Scene("level_up", "升级选择", "reward", true, "暂停战斗并选择升级奖励。"),
                    Scene("summary", "结算", "ending", false, "显示坚持时间、击杀、构筑和失败原因。")
                ],
                [
                    Transition("arena", "level_up", "经验达到升级阈值", "arena", ["hp", "weapons", "level", "elapsed_time"]),
                    Transition("level_up", "arena", "确认升级", "", ["hp", "weapons", "level", "elapsed_time"]),
                    Transition("arena", "summary", "死亡、撤离或计时结束", "", ["elapsed_time", "kills", "build"])
                ],
                "幸存者类可以用单个 Godot 场景实现，但体验状态仍需要区分战斗、升级选择和结算。");
        }

        if (ContainsAny(gameType, "tower", "defen", "塔防"))
        {
            return Document(
                "multi",
                "build_phase",
                [
                    Scene("build_phase", "布防阶段", "gameplay", true, "查看路径、放置或升级防御。"),
                    Scene("wave_phase", "波次战斗", "combat", true, "敌人沿路径进攻，防御自动或半自动输出。"),
                    Scene("wave_reward", "波次结算", "reward", false, "显示收益、损失和下一波准备。")
                ],
                [
                    Transition("build_phase", "wave_phase", "开始波次", "build_phase", ["gold", "towers", "base_hp", "wave_index"]),
                    Transition("wave_phase", "wave_reward", "波次清空或基地失败", "build_phase", ["gold", "towers", "base_hp", "wave_index"]),
                    Transition("wave_reward", "build_phase", "确认结算", "", ["gold", "towers", "base_hp", "wave_index"])
                ],
                "塔防原型至少需要布防、波次战斗和结算/下一波的路由关系。");
        }

        return Document(
            "unsure",
            "first_playable",
            [
                Scene("first_playable", "首个可玩场景", "gameplay", true, "承载第一轮核心操作、反馈和成功/失败判断。")
            ],
            [],
                "用户或 GDD 需要确认是否真的只做单一体验状态。");
    }

    private static GameDesignSceneRouteDocument? BuildFallbackSceneRouteFromDefaultContract(
        ProjectSnapshot project,
        PhaseAPlatformOptions? options)
    {
        var evidence = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson);
        var snapshotRoute = BuildFallbackSceneRouteFromContractSnapshot(evidence.ContractSnapshot);
        if (snapshotRoute is not null)
        {
            return snapshotRoute;
        }

        if (options is null)
        {
            return null;
        }

        if (string.IsNullOrWhiteSpace(evidence.MatchedGameTypeId))
        {
            return null;
        }

        var entry = new BmadGameTypeDesignCatalog(options).Find(evidence.MatchedGameTypeId);
        if (entry is null || string.IsNullOrWhiteSpace(entry.GuideExcerpt))
        {
            return null;
        }

        var sceneRows = ParseDefaultSceneRows(entry.GuideExcerpt)
            .Where(row => string.Equals(row.Required, "Always", StringComparison.OrdinalIgnoreCase) ||
                          string.Equals(row.Required, "Conditional", StringComparison.OrdinalIgnoreCase))
            .Take(MaxScenes)
            .ToArray();
        if (sceneRows.Length == 0)
        {
            return null;
        }

        var scenes = sceneRows
            .Select(row => Scene(
                row.SceneId,
                row.SceneName,
                InferContractSceneRole(row),
                string.Equals(row.Required, "Always", StringComparison.OrdinalIgnoreCase),
                row.MinimumPlayableContent))
            .ToArray();
        var sceneIds = scenes.Select(scene => scene.Id).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var entryScene = sceneRows.FirstOrDefault(row => ContainsSceneToken(row.EntryFrom, "start"))?.SceneId ?? scenes[0].Id;
        if (!sceneIds.Contains(entryScene))
        {
            entryScene = scenes[0].Id;
        }

        var transitions = sceneRows
            .SelectMany(row => SplitSceneTokens(row.ExitsTo)
                .Where(to => sceneIds.Contains(to))
                .Select(to => Transition(
                    row.SceneId,
                    to,
                    "Default contract transition",
                    "",
                    [])))
            .Take(MaxTransitions)
            .ToArray();

        return Document(
            scenes.Length > 1 ? "multi" : "single",
            entryScene,
            scenes,
            transitions,
            $"Fallback generated from Default Prototype Contract for {entry.Id}.");
    }

    private static GameDesignSceneRouteDocument? BuildFallbackSceneRouteFromContractSnapshot(
        ProjectGameTypeContractSnapshot snapshot)
    {
        if (!snapshot.HasContract)
        {
            return null;
        }

        var sceneRows = snapshot.DefaultScenes
            .Where(row => string.Equals(row.Required, "Always", StringComparison.OrdinalIgnoreCase) ||
                          string.Equals(row.Required, "Conditional", StringComparison.OrdinalIgnoreCase))
            .Take(MaxScenes)
            .ToArray();
        if (sceneRows.Length == 0)
        {
            return null;
        }

        var scenes = sceneRows
            .Select(row => Scene(
                row.SceneId,
                row.SceneName,
                InferContractSceneRole(row.SceneId, row.SceneName, row.Purpose),
                string.Equals(row.Required, "Always", StringComparison.OrdinalIgnoreCase),
                row.MinimumPlayableContent))
            .ToArray();
        var sceneIds = scenes.Select(scene => scene.Id).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var entryScene = sceneRows.FirstOrDefault(row => ContainsSceneToken(row.EntryFrom, "start"))?.SceneId ?? scenes[0].Id;
        if (!sceneIds.Contains(entryScene))
        {
            entryScene = scenes[0].Id;
        }

        var transitions = sceneRows
            .SelectMany(row => SplitSceneTokens(row.ExitsTo)
                .Where(to => sceneIds.Contains(to))
                .Select(to => Transition(
                    row.SceneId,
                    to,
                    "Contract snapshot transition",
                    "",
                    [])))
            .Take(MaxTransitions)
            .ToArray();

        return Document(
            scenes.Length > 1 ? "multi" : "single",
            entryScene,
            scenes,
            transitions,
            $"Fallback generated from project contract snapshot for {snapshot.MatchedGameTypeId}.");
    }

    private static IReadOnlyList<DefaultSceneContractRow> ParseDefaultSceneRows(string guideExcerpt)
    {
        var lines = guideExcerpt.Replace("\r\n", "\n", StringComparison.Ordinal)
            .Replace('\r', '\n')
            .Split('\n', StringSplitOptions.TrimEntries);
        var rows = new List<DefaultSceneContractRow>();
        var inDefaultScenes = false;
        foreach (var line in lines)
        {
            if (line.StartsWith("### Default Scenes", StringComparison.OrdinalIgnoreCase))
            {
                inDefaultScenes = true;
                continue;
            }

            if (inDefaultScenes && line.StartsWith("### ", StringComparison.Ordinal))
            {
                break;
            }

            if (!inDefaultScenes || !line.StartsWith("|", StringComparison.Ordinal))
            {
                continue;
            }

            var columns = SplitMarkdownTableRow(line);
            if (columns.Length < 7 ||
                columns[0].Contains("---", StringComparison.Ordinal) ||
                string.Equals(columns[0], "scene_id", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var sceneId = NormalizeId(columns[0]);
            if (string.IsNullOrWhiteSpace(sceneId))
            {
                continue;
            }

            rows.Add(new DefaultSceneContractRow(
                sceneId,
                Trim(columns[1], 80),
                Trim(columns[2], 180),
                Trim(columns[3], 40),
                Trim(columns[4], 160),
                Trim(columns[5], 160),
                Trim(columns[6], 220)));
        }

        return rows;
    }

    private static string[] SplitMarkdownTableRow(string line)
    {
        return line.Trim().Trim('|')
            .Split('|', StringSplitOptions.TrimEntries)
            .Select(column => column.Replace("\\|", "|", StringComparison.Ordinal).Trim())
            .ToArray();
    }

    private static string InferContractSceneRole(DefaultSceneContractRow row)
    {
        return InferContractSceneRole(row.SceneId, row.SceneName, row.Purpose);
    }

    private static string InferContractSceneRole(string sceneId, string sceneName, string purpose)
    {
        var text = string.Join(" ", sceneId, sceneName, purpose).ToLowerInvariant();
        if (ContainsAny(text, "reward", "upgrade", "result", "summary", "debrief"))
        {
            return "reward";
        }

        if (ContainsAny(text, "combat", "battle", "fight", "wave", "threat", "encounter"))
        {
            return "combat";
        }

        if (ContainsAny(text, "shop", "loadout", "deckbuilding", "setup", "lobby", "menu", "garage"))
        {
            return "menu";
        }

        if (ContainsAny(text, "ending", "end", "death", "victory"))
        {
            return "ending";
        }

        if (ContainsAny(text, "field", "map", "world", "hub", "exploration", "dashboard"))
        {
            return "hub";
        }

        return NormalizeRole(sceneId);
    }

    private static bool ContainsSceneToken(string value, string token)
    {
        return SplitSceneTokens(value).Contains(token, StringComparer.OrdinalIgnoreCase);
    }

    private static IReadOnlyList<string> SplitSceneTokens(string value)
    {
        return (value ?? "")
            .Split([',', ';', '|'], StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries)
            .Select(NormalizeId)
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .ToArray();
    }

    private string ResolveLlmWorkspace(ProjectSnapshot project)
    {
        if (!string.IsNullOrWhiteSpace(project.WorkspaceRootPath))
        {
            return project.WorkspaceRootPath;
        }

        return Path.Combine(_options.HostedWorkspaceRoot, "_gdd-scene-route");
    }

    private string BuildPrompt(
        ProjectSnapshot project,
        string message,
        IReadOnlyList<GameDesignQuestionAnswer> answers)
    {
        return $$"""
        Return JSON object only. Draft a scene-routing form for a game prototype before the GDD outline route runs.

        Project:
        - Project id: {{project.ProjectId}}
        - Game name: {{project.GameName}}
        - Project name: {{project.Name}}
        - Game type source (raw user input, do not use for game-types.csv matching): {{project.GameTypeSource}}
        - Matched game type id: {{ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson).MatchedGameTypeId}}
        - Normalized Steam genre tags: {{string.Join(", ", ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson).NormalizedGenreTags)}}
        - Matched guide path: {{ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson).MatchedGuidePath}}
        - Template rule id: {{project.TemplateRuleId}}

        User GDD raw material:
        {{EmptyAsNone(message)}}

        Question-form answers:
        {{FormatAnswers(answers)}}

        Project game-type contract snapshot:
        {{FormatContractSnapshot(project)}}

        Game type default prototype contract and guide excerpt:
        {{FormatGameTypeGuideExcerpt(project)}}

        Requirements:
        - Infer from the matched game type evidence, Steam English genre tags, and the user's GDD form answers.
        - If the guide excerpt includes `Default Prototype Contract`, use `Default Scenes` as default scene topology and `Required Modules` as default implementation coverage.
        - Preserve `Always` default scenes unless the user's GDD material explicitly conflicts with them. If an `Always` scene is omitted, renamed beyond recognition, or merged, explain the explicit override reason in `notes`.
        - Distinguish player-facing experience states from Godot .tscn files. Do not force one .tscn per state.
        - Prefer a multi-scene route when the genre commonly needs map/combat/reward, route/combat/reward, build/wave/reward, arena/upgrade/summary, or hub/mission/summary states.
        - Keep M1 tight: mark only the scenes required for the first playable loop as m1Required=true.
        - If a single-scene route is plausible, still explain why it is allowed.
        - Return:
          {
            "sceneCountIntent": "single | multi | unsure",
            "entryScene": "scene_id",
            "scenes": [
              {
                "id": "safe_snake_case_id",
                "name": "Chinese scene name",
                "role": "hub | gameplay | combat | reward | shop | menu | ending | support",
                "m1Required": true,
                "playerGoal": "What the player does here"
              }
            ],
            "transitions": [
              {
                "from": "scene_id",
                "to": "scene_id",
                "trigger": "Chinese trigger",
                "returnsTo": "scene_id or empty",
                "stateCarried": ["hp", "gold"]
              }
            ],
            "singleSceneConfirmation": {
              "allowed": false,
              "reason": "Chinese reason"
            },
            "notes": ["Chinese note"]
          }
        - Use 1 to 8 scenes and at most 16 transitions.
        - Scene ids and transition ids must refer to existing scenes.
        """;
    }

    private string FormatGameTypeGuideExcerpt(ProjectSnapshot project)
    {
        var evidence = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson);
        if (string.IsNullOrWhiteSpace(evidence.MatchedGameTypeId))
        {
            return "(none)";
        }

        var entry = new BmadGameTypeDesignCatalog(_options).Find(evidence.MatchedGameTypeId);
        if (entry is null || string.IsNullOrWhiteSpace(entry.GuideExcerpt))
        {
            return "(none)";
        }

        return $$"""
        GuideId: {{entry.Id}}
        GuidePath: {{entry.FragmentRelativePath}}

        {{entry.GuideExcerpt}}
        """;
    }

    private static string FormatContractSnapshot(ProjectSnapshot project)
    {
        var snapshot = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson).ContractSnapshot;
        if (!snapshot.HasContract)
        {
            return "(none)";
        }

        var scenes = snapshot.DefaultScenes.Count == 0
            ? "- (none)"
            : string.Join(Environment.NewLine, snapshot.DefaultScenes.Select(scene =>
                $"- {scene.SceneId}: {scene.SceneName}; required={scene.Required}; entry_from={scene.EntryFrom}; exits_to={scene.ExitsTo}; minimum={scene.MinimumPlayableContent}"));
        var modules = snapshot.RequiredModules.Count == 0
            ? "- (none)"
            : string.Join(Environment.NewLine, snapshot.RequiredModules.Select(module =>
                $"- {module.ModuleId}: {module.ModuleName}; required_by_default={module.RequiredByDefault}; acceptance={module.MinimumAcceptance}"));

        return $$"""
        MatchedGameTypeId: {{snapshot.MatchedGameTypeId}}
        GuidePath: {{snapshot.GuidePath}}
        SourceGuideHash: {{snapshot.SourceGuideHash}}
        DefaultScenes:
        {{scenes}}
        RequiredModules:
        {{modules}}
        """;
    }

    private GameDesignSceneRouteDraftResult Fallback(ProjectSnapshot project, string failureCode)
    {
        return new GameDesignSceneRouteDraftResult(
            "ready",
            project.ProjectId,
            BuildFallbackSceneRoute(project, _options),
            "fallback",
            failureCode);
    }

    private GameDesignSceneRouteDraftResult RateLimited(ProjectSnapshot project, string failureCode)
    {
        return new GameDesignSceneRouteDraftResult(
            "rate_limited",
            project.ProjectId,
            BuildFallbackSceneRoute(project, _options),
            "none",
            failureCode);
    }

    private static string SceneRouteConcurrencyFailureCode(string? failureCode)
    {
        return failureCode switch
        {
            "user_gdd_question_form_concurrency_limit_exceeded" => "user_gdd_scene_route_concurrency_limit_exceeded",
            "gdd_question_form_concurrency_limit_exceeded" => "gdd_scene_route_concurrency_limit_exceeded",
            _ => "gdd_scene_route_concurrency_limit_exceeded"
        };
    }

    private static GameDesignSceneRouteDocument? ParseSceneRoute(string json)
    {
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object)
        {
            return null;
        }

        var sceneCountIntent = NormalizeIntent(ReadString(root, "sceneCountIntent"));
        var scenes = ParseScenes(root);
        if (scenes.Count is < MinScenes or > MaxScenes)
        {
            return null;
        }

        var sceneIds = scenes.Select(scene => scene.Id).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var entryScene = NormalizeId(ReadString(root, "entryScene"));
        if (string.IsNullOrWhiteSpace(entryScene) || !sceneIds.Contains(entryScene))
        {
            entryScene = scenes[0].Id;
        }

        var transitions = ParseTransitions(root, sceneIds);
        var confirmation = ParseSingleSceneConfirmation(root, sceneCountIntent, scenes.Count);
        var notes = ParseStringArray(root, "notes", 8, 180);

        return new GameDesignSceneRouteDocument(
            SchemaVersion,
            sceneCountIntent,
            entryScene,
            scenes,
            transitions,
            confirmation,
            notes);
    }

    private static List<GameDesignSceneRouteScene> ParseScenes(JsonElement root)
    {
        if (!TryGetProperty(root, "scenes", out var element) || element.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        var sceneInputs = new List<GameDesignSceneRouteScene>();
        foreach (var item in element.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object)
            {
                continue;
            }

            sceneInputs.Add(new GameDesignSceneRouteScene(
                ReadString(item, "id"),
                ReadString(item, "name"),
                ReadString(item, "role"),
                ReadBoolean(item, "m1Required", sceneInputs.Count == 0),
                ReadString(item, "playerGoal")));
            if (sceneInputs.Count == MaxScenes)
            {
                break;
            }
        }

        return NormalizeScenes(sceneInputs);
    }

    private static List<GameDesignSceneRouteTransition> ParseTransitions(JsonElement root, HashSet<string> sceneIds)
    {
        if (!TryGetProperty(root, "transitions", out var element) || element.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        var transitionInputs = new List<GameDesignSceneRouteTransition>();
        foreach (var item in element.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object)
            {
                continue;
            }

            transitionInputs.Add(new GameDesignSceneRouteTransition(
                ReadString(item, "from"),
                ReadString(item, "to"),
                ReadString(item, "trigger"),
                ReadString(item, "returnsTo"),
                ParseStringArray(item, "stateCarried", 10, 40)));
            if (transitionInputs.Count == MaxTransitions)
            {
                break;
            }
        }

        return NormalizeTransitions(transitionInputs, sceneIds);
    }

    private static GameDesignSingleSceneConfirmation ParseSingleSceneConfirmation(
        JsonElement root,
        string sceneCountIntent,
        int sceneCount)
    {
        if (TryGetProperty(root, "singleSceneConfirmation", out var element) && element.ValueKind == JsonValueKind.Object)
        {
            return new GameDesignSingleSceneConfirmation(
                ReadBoolean(element, "allowed", sceneCount == 1 && sceneCountIntent == "single"),
                Trim(ReadString(element, "reason"), 220));
        }

        return new GameDesignSingleSceneConfirmation(
            sceneCount == 1 && sceneCountIntent == "single",
            sceneCount == 1
                ? "需要用户确认首版原型确实只包含一个体验状态。"
                : "多场景路线已明确，单场景确认不适用。");
    }

    private static GameDesignSceneRouteDocument Document(
        string intent,
        string entryScene,
        IReadOnlyList<GameDesignSceneRouteScene> scenes,
        IReadOnlyList<GameDesignSceneRouteTransition> transitions,
        string confirmationReason)
    {
        return new GameDesignSceneRouteDocument(
            SchemaVersion,
            intent,
            entryScene,
            scenes,
            transitions,
            new GameDesignSingleSceneConfirmation(intent == "single", confirmationReason),
            [confirmationReason]);
    }

    private static GameDesignSceneRouteScene Scene(string id, string name, string role, bool m1Required, string playerGoal)
    {
        return new GameDesignSceneRouteScene(id, name, role, m1Required, playerGoal);
    }

    private static GameDesignSceneRouteTransition Transition(
        string from,
        string to,
        string trigger,
        string returnsTo,
        IReadOnlyList<string> stateCarried)
    {
        return new GameDesignSceneRouteTransition(from, to, trigger, returnsTo, stateCarried);
    }

    private static IReadOnlyList<GameDesignQuestionAnswer> NormalizeAnswers(IReadOnlyList<GameDesignQuestionAnswer>? answers)
    {
        return (answers ?? [])
            .Take(MaxAnswers)
            .Select(item => new GameDesignQuestionAnswer(
                NormalizeId(item.Id),
                Trim(item.Label, 80),
                Trim(item.Answer, MaxAnswerChars),
                item.Required))
            .Where(item => !string.IsNullOrWhiteSpace(item.Label) || !string.IsNullOrWhiteSpace(item.Answer))
            .ToArray();
    }

    private static string FormatAnswers(IReadOnlyList<GameDesignQuestionAnswer> answers)
    {
        if (answers.Count == 0)
        {
            return "None.";
        }

        return string.Join(
            "\n",
            answers.Select((item, index) => $"{index + 1}. {item.Label}: {EmptyAsNone(item.Answer)}"));
    }

    private static IReadOnlyList<string> ParseStringArray(JsonElement root, string name, int maxItems, int maxLength)
    {
        if (!TryGetProperty(root, name, out var element) || element.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        return element.EnumerateArray()
            .Where(item => item.ValueKind == JsonValueKind.String)
            .Select(item => Trim(item.GetString(), maxLength))
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(maxItems)
            .ToArray();
    }

    private static List<GameDesignSceneRouteScene> NormalizeScenes(IReadOnlyList<GameDesignSceneRouteScene>? scenes)
    {
        var usedIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var normalized = new List<GameDesignSceneRouteScene>();
        foreach (var scene in scenes ?? [])
        {
            var name = Trim(scene?.Name, 40);
            var id = NormalizeId(scene?.Id ?? "");
            if (string.IsNullOrWhiteSpace(id))
            {
                id = NormalizeId(name);
            }

            if (string.IsNullOrWhiteSpace(id) || string.IsNullOrWhiteSpace(name) || !usedIds.Add(id))
            {
                continue;
            }

            normalized.Add(new GameDesignSceneRouteScene(
                id,
                name,
                NormalizeRole(scene?.Role ?? ""),
                scene?.M1Required ?? normalized.Count == 0,
                Trim(scene?.PlayerGoal, 180)));
            if (normalized.Count == MaxScenes)
            {
                break;
            }
        }

        return normalized;
    }

    private static List<GameDesignSceneRouteTransition> NormalizeTransitions(
        IReadOnlyList<GameDesignSceneRouteTransition>? transitions,
        HashSet<string> sceneIds)
    {
        var normalized = new List<GameDesignSceneRouteTransition>();
        foreach (var transition in transitions ?? [])
        {
            var from = NormalizeId(transition?.From ?? "");
            var to = NormalizeId(transition?.To ?? "");
            if (!sceneIds.Contains(from) || !sceneIds.Contains(to))
            {
                continue;
            }

            var returnsTo = NormalizeId(transition?.ReturnsTo ?? "");
            if (!string.IsNullOrWhiteSpace(returnsTo) && !sceneIds.Contains(returnsTo))
            {
                returnsTo = "";
            }

            normalized.Add(new GameDesignSceneRouteTransition(
                from,
                to,
                Trim(transition?.Trigger, 160),
                returnsTo,
                NormalizeStringList(transition?.StateCarried, 10, 40)));
            if (normalized.Count == MaxTransitions)
            {
                break;
            }
        }

        return normalized;
    }

    private static IReadOnlyList<string> NormalizeStringList(IReadOnlyList<string>? values, int maxItems, int maxLength)
    {
        return (values ?? [])
            .Select(item => Trim(item, maxLength))
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(maxItems)
            .ToArray();
    }

    private static bool TryGetProperty(JsonElement element, string name, out JsonElement value)
    {
        foreach (var property in element.EnumerateObject())
        {
            if (string.Equals(property.Name, name, StringComparison.OrdinalIgnoreCase))
            {
                value = property.Value;
                return true;
            }
        }

        value = default;
        return false;
    }

    private static string ReadString(JsonElement element, string name)
    {
        return TryGetProperty(element, name, out var property) && property.ValueKind == JsonValueKind.String
            ? property.GetString() ?? ""
            : "";
    }

    private static bool ReadBoolean(JsonElement element, string name, bool fallback)
    {
        return TryGetProperty(element, name, out var property) && property.ValueKind is JsonValueKind.True or JsonValueKind.False
            ? property.GetBoolean()
            : fallback;
    }

    private static string NormalizeIntent(string value)
    {
        var normalized = (value ?? "").Trim().ToLowerInvariant();
        return normalized is "single" or "multi" or "unsure" ? normalized : "unsure";
    }

    private static string NormalizeRole(string value)
    {
        var normalized = (value ?? "").Trim().ToLowerInvariant();
        return normalized is "hub" or "gameplay" or "combat" or "reward" or "shop" or "menu" or "ending" or "support"
            ? normalized
            : "gameplay";
    }

    private static string NormalizeId(string value)
    {
        var normalized = new string((value ?? "").Trim().ToLowerInvariant()
            .Select(ch => ch is >= 'a' and <= 'z' or >= '0' and <= '9' ? ch : '_')
            .ToArray());
        while (normalized.Contains("__", StringComparison.Ordinal))
        {
            normalized = normalized.Replace("__", "_", StringComparison.Ordinal);
        }

        return normalized.Trim('_');
    }

    private static string GameType(ProjectSnapshot project)
    {
        var evidence = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson);
        return string.Join(
            " ",
            new[] { evidence.MatchedGameTypeId, string.Join(" ", evidence.NormalizedGenreTags), project.TemplateRuleId }
                .Where(value => !string.IsNullOrWhiteSpace(value)));
    }

    private static bool ContainsAny(string value, params string[] needles)
    {
        return needles.Any(needle => value.Contains(needle, StringComparison.OrdinalIgnoreCase));
    }

    private static string EmptyAsNone(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? "None." : value.Trim();
    }

    private static string Trim(string? value, int maxLength)
    {
        var trimmed = (value ?? "").Trim();
        return trimmed.Length <= maxLength ? trimmed : trimmed[..maxLength];
    }

    private sealed record DefaultSceneContractRow(
        string SceneId,
        string SceneName,
        string Purpose,
        string Required,
        string EntryFrom,
        string ExitsTo,
        string MinimumPlayableContent);
}
