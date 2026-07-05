namespace PhaseA.Platform.Runs;

internal static class GameTypeDesignTemplateDetector
{
    private sealed record ExplicitGameplayTemplateRule(
        string TemplateId,
        string[] TextAliases,
        string[] TokenAliases,
        string[][] RequiredTokenSets);

    internal static IReadOnlySet<string> SupportedTemplateIds => ExplicitGameplayTemplateRules
        .Select(rule => rule.TemplateId)
        .ToHashSet(StringComparer.OrdinalIgnoreCase);

    internal static string? DetectExplicitGameplayTemplateId(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return null;
        }

        var normalized = text.ToLowerInvariant();
        var tokens = TokenizeForTemplateMatch(normalized);

        foreach (var rule in ExplicitGameplayTemplateRules)
        {
            if (!ExplicitGameplayRuleMatches(rule, normalized, tokens))
            {
                continue;
            }

            if (rule.TemplateId == "tower-defense" && ContainsRoguelikeOrThirdPersonActionSemantics(normalized, tokens))
            {
                continue;
            }

            return rule.TemplateId;
        }

        return null;
    }

    private static bool ExplicitGameplayRuleMatches(ExplicitGameplayTemplateRule rule, string normalized, IReadOnlySet<string> tokens)
    {
        return ContainsAnyTextAlias(normalized, tokens, rule.TextAliases) ||
            ContainsAnyToken(tokens, rule.TokenAliases) ||
            ContainsAnyTokenSet(tokens, rule.RequiredTokenSets);
    }

    private static bool ContainsAnyTextAlias(string normalized, IReadOnlySet<string> tokens, params string[] aliases)
    {
        foreach (var alias in aliases)
        {
            if (IsSingleAsciiTokenAlias(alias))
            {
                if (tokens.Contains(alias))
                {
                    return true;
                }

                continue;
            }

            if (normalized.Contains(alias, StringComparison.Ordinal))
            {
                return true;
            }
        }

        return false;
    }

    private static bool IsSingleAsciiTokenAlias(string alias)
    {
        return alias.All(ch => (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9'));
    }

    private static bool ContainsRoguelikeOrThirdPersonActionSemantics(string normalized, IReadOnlySet<string> tokens)
    {
        return ContainsAny(normalized, "third-person action", "第三人称动作", "随机地城", "随机地下城", "肉鸽", "类rogue", "死亡保留", "死亡重来") ||
            ContainsAnyToken(tokens, "roguelike", "rogue", "roguelite");
    }

    private static readonly IReadOnlyList<ExplicitGameplayTemplateRule> ExplicitGameplayTemplateRules =
    [
        new("survivorslike",
            ["survivorslike", "survivor-like", "vampire survivors", "bullet heaven", "bullet-heaven", "auto shooter", "auto-shooter", "arena survival", "horde survival"],
            ["survivorslike"],
            [["survivor", "like"], ["vampire", "survivors"], ["bullet", "heaven"], ["auto", "shooter"], ["arena", "survival"], ["horde", "survival"]]),
        new("roguelike",
            ["随机地城", "随机地下城", "肉鸽", "类rogue", "死亡保留", "死亡重来", "roguelike", "roguelite"],
            ["roguelike", "roguelite"],
            [["rogue", "like"], ["rogue", "lite"]]),
        new("metroidvania",
            ["metroidvania", "类银河战士恶魔城", "银河恶魔城", "银河城"],
            ["metroidvania"],
            [["metroid", "vania"]]),
        new("visual-novel",
            ["visual novel", "visual-novel", "视觉小说", "文字恋爱", "剧情分支"],
            [],
            [["visual", "novel"]]),
        new("turn-based-tactics",
            ["turn based tactics", "turn-based tactics", "turn-based-tactics", "回合制战术", "回合战术", "战棋", "棋盘战术", "网格战术"],
            [],
            [["turn", "based", "tactics"], ["turn", "based", "tactical"], ["grid", "tactics"], ["grid", "tactical"]]),
        new("tower-defense",
            ["tower defense", "tower-defense", "防御塔", "塔防", "造塔"],
            [],
            [["tower", "defense"]]),
        new("idle-incremental",
            ["idle incremental", "idle-incremental", "放置", "挂机", "增量游戏", "点击放置"],
            ["idle", "incremental", "clicker"],
            [["idle", "incremental"]]),
        new("action-platformer",
            ["action platformer", "action-platformer", "平台跳跃", "动作平台", "横版平台"],
            ["platformer", "platforming"],
            [["action", "platformer"], ["action", "platforming"]]),
        new("card-game",
            ["deck building", "deck-building", "deckbuilder", "card game", "card-game", "卡牌构筑", "牌组构筑", "卡牌游戏", "打牌"],
            ["deckbuilder"],
            [["deck", "building"], ["card", "game"]]),
        new("text-based",
            ["text based", "text-based", "interactive fiction", "文字游戏", "文字冒险", "纯文字", "mud游戏"],
            ["mud"],
            [["text", "based"], ["interactive", "fiction"]]),
        new("moba",
            ["moba", "多人在线战术竞技", "三路推塔", "对线推塔"],
            ["moba"],
            [["multiplayer", "online", "battle", "arena"]]),
        new("fighting",
            ["fighting game", "格斗游戏", "对战格斗", "街机格斗"],
            ["fighter", "fighting"],
            [["fighting", "game"]]),
        new("racing",
            ["racing game", "赛车", "竞速", "竞速游戏", "驾驶竞速"],
            ["racing"],
            [["racing", "game"]]),
        new("sports",
            ["sports game", "体育游戏", "足球", "篮球", "棒球", "网球", "高尔夫"],
            ["sports", "football", "soccer", "basketball", "baseball", "tennis", "golf"],
            [["sports", "game"]]),
        new("horror",
            ["horror game", "恐怖游戏", "生存恐怖", "心理恐怖", "惊悚"],
            ["horror"],
            [["horror", "game"], ["survival", "horror"]]),
        new("survival",
            ["survival game", "生存游戏", "开放世界生存", "采集建造生存", "饥饿口渴"],
            ["survival"],
            [["survival", "game"], ["survival", "crafting"]]),
        new("puzzle",
            ["puzzle game", "解谜游戏", "益智", "谜题", "机关解谜"],
            ["puzzle", "puzzler"],
            [["puzzle", "game"]]),
        new("strategy",
            ["strategy game", "策略游戏", "即时战略", "实时战略", "经营策略", "4x策略"],
            ["strategy", "rts", "4x"],
            [["strategy", "game"], ["real", "time", "strategy"]]),
        new("shooter",
            ["shooter", "first person shooter", "third person shooter", "射击", "第一人称射击", "第三人称射击"],
            ["shooter", "fps", "tps"],
            [["first", "person", "shooter"], ["third", "person", "shooter"]]),
        new("adventure",
            ["adventure game", "冒险游戏", "探索冒险", "叙事冒险"],
            ["adventure"],
            [["adventure", "game"]]),
        new("simulation",
            ["simulation game", "模拟经营", "生活模拟", "建造模拟", "驾驶模拟", "农场模拟"],
            ["simulation", "simulator", "sim"],
            [["simulation", "game"]]),
        new("rpg",
            ["角色扮演", "勇者斗恶龙", "jrpg"],
            ["rpg", "jrpg"],
            [["role", "playing"], ["role", "playing", "game"]]),
        new("rhythm",
            ["rhythm game", "音乐节奏", "节奏游戏", "音游"],
            ["rhythm"],
            [["rhythm", "game"]]),
        new("sandbox",
            ["sandbox game", "沙盒", "开放沙盒", "创造模式"],
            ["sandbox"],
            [["sandbox", "game"]]),
        new("party-game",
            ["party game", "party-game", "派对游戏", "多人派对", "本地多人小游戏"],
            [],
            [["party", "game"]])
    ];

    private static bool ContainsAnyTokenSet(IReadOnlySet<string> tokens, params string[][] tokenSets)
    {
        return tokenSets.Any(tokenSet => tokenSet.All(tokens.Contains));
    }

    private static bool ContainsAny(string text, params string[] needles)
    {
        return needles.Any(needle => text.Contains(needle, StringComparison.Ordinal));
    }

    private static bool ContainsAnyToken(IReadOnlySet<string> tokens, params string[] needles)
    {
        return needles.Any(tokens.Contains);
    }

    private static IReadOnlySet<string> TokenizeForTemplateMatch(string normalizedText)
    {
        return normalizedText
            .Split([' ', '\t', '\r', '\n', ',', ';', '/', '|', '\\', '.', ':', '：', '、', '，', '。', '!', '?', '！', '？', '(', ')', '[', ']', '{', '}', '"', '\''], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .SelectMany(SplitCamelAndSeparatorTokens)
            .Where(token => token.Length >= 2)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
    }

    private static IEnumerable<string> SplitCamelAndSeparatorTokens(string token)
    {
        foreach (var part in token.Split(['_', '-'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (!string.IsNullOrWhiteSpace(part))
            {
                yield return part;
            }
        }
    }
}
