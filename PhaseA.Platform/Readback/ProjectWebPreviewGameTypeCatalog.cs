using System.Text.RegularExpressions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Prototypes;

namespace PhaseA.Platform.Readback;

internal static class ProjectWebPreviewGameTypeCatalog
{
    private static readonly IReadOnlyDictionary<string, string> GuideById = new Dictionary<string, string>(StringComparer.Ordinal)
    {
        ["action-platformer"] = "docs/game-type-guides/action-platformer.md",
        ["adventure"] = "docs/game-type-guides/adventure.md",
        ["card-game"] = "docs/game-type-guides/card-game.md",
        ["fighting"] = "docs/game-type-guides/fighting.md",
        ["horror"] = "docs/game-type-guides/horror.md",
        ["idle-incremental"] = "docs/game-type-guides/idle-incremental.md",
        ["metroidvania"] = "docs/game-type-guides/metroidvania.md",
        ["moba"] = "docs/game-type-guides/moba.md",
        ["party-game"] = "docs/game-type-guides/party-game.md",
        ["puzzle"] = "docs/game-type-guides/puzzle.md",
        ["racing"] = "docs/game-type-guides/racing.md",
        ["rhythm"] = "docs/game-type-guides/rhythm.md",
        ["roguelike"] = "docs/game-type-guides/roguelike.md",
        ["rpg"] = "docs/game-type-guides/rpg.md",
        ["sandbox"] = "docs/game-type-guides/sandbox.md",
        ["shooter"] = "docs/game-type-guides/shooter.md",
        ["simulation"] = "docs/game-type-guides/simulation.md",
        ["sports"] = "docs/game-type-guides/sports.md",
        ["strategy"] = "docs/game-type-guides/strategy.md",
        ["survival"] = "docs/game-type-guides/survival.md",
        ["survivorslike"] = "docs/game-type-guides/survivorslike.md",
        ["text-based"] = "docs/game-type-guides/text-based.md",
        ["tower-defense"] = "docs/game-type-guides/tower-defense.md",
        ["turn-based-tactics"] = "docs/game-type-guides/turn-based-tactics.md",
        ["visual-novel"] = "docs/game-type-guides/visual-novel.md"
    };

    public static string ResolveGameTypeId(params string?[] values)
    {
        foreach (var value in values)
        {
            var resolved = ResolveKnownGameTypeId(value);
            if (!string.IsNullOrWhiteSpace(resolved))
            {
                return resolved;
            }
        }

        return "";
    }

    public static string ResolveProjectGameTypeId(ProjectSnapshot project)
    {
        var evidence = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson);
        return ResolveKnownGameTypeId(evidence.MatchedGameTypeId);
    }

    public static string ResolveGameTypeGuide(string? gameTypeId)
    {
        var normalized = NormalizeGameTypeToken(gameTypeId);
        return GuideById.TryGetValue(normalized, out var guide) ? guide : "";
    }

    public static string NormalizeGameTypeToken(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var normalized = Regex.Replace(value.Trim().ToLowerInvariant(), "[^a-z0-9]+", "-").Trim('-');
        return normalized switch
        {
            "role-playing-game" or "role-playing" or "roleplaying-game" or "roleplaying" or "jrpg" => "rpg",
            "vampire-survivors-like" or "survivors-like" or "survivor-like" or "survivorslike" or "survivor" or "arena-survival" => "survivorslike",
            "deck-builder" or "deck-building" or "deckbuilding" or "deckbuilder" or "roguelike-deckbuilder" => "card-game",
            "card" or "cards" => "card-game",
            "tower-defence" or "towerdefence" or "towerdefense" or "td" => "tower-defense",
            "platformer" or "action" => "action-platformer",
            "visual-novel-game" => "visual-novel",
            "text" or "text-game" or "interactive-fiction" => "text-based",
            "turn-based-tactical" or "tactics" or "turn-based" => "turn-based-tactics",
            "idle" or "incremental" => "idle-incremental",
            _ => normalized
        };
    }

    private static string ResolveKnownGameTypeId(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var normalized = NormalizeGameTypeToken(value);
        if (GuideById.ContainsKey(normalized))
        {
            return normalized;
        }

        var lower = value.Trim().ToLowerInvariant();
        foreach (var id in GuideById.Keys)
        {
            if (lower.Contains($"docs/game-type-guides/{id}.md", StringComparison.Ordinal))
            {
                return id;
            }
        }

        if (ContainsAny(lower, "塔防", "tower defense", "tower-def", "tower_defense"))
        {
            return "tower-defense";
        }

        if (ContainsAny(lower, "角色扮演", "跑团", "rpg", "jrpg", "role playing", "role-playing"))
        {
            return "rpg";
        }

        if (ContainsAny(lower, "幸存者", "吸血鬼", "survivor", "vampire survivors", "arena survival"))
        {
            return "survivorslike";
        }

        if (ContainsAny(lower, "survival", "生存"))
        {
            return "survival";
        }

        if (ContainsAny(lower, "卡牌", "牌组", "构筑", "deck", "card"))
        {
            return "card-game";
        }

        if (ContainsAny(lower, "肉鸽", "roguelike", "rogue-like", "permadeath"))
        {
            return "roguelike";
        }

        if (ContainsAny(lower, "平台跳跃", "平台动作", "platformer", "action platformer"))
        {
            return "action-platformer";
        }

        if (ContainsAny(lower, "射击", "shooter", "fps", "tps"))
        {
            return "shooter";
        }

        if (ContainsAny(lower, "格斗", "fighting"))
        {
            return "fighting";
        }

        if (ContainsAny(lower, "恐怖", "horror"))
        {
            return "horror";
        }

        if (ContainsAny(lower, "解谜", "puzzle"))
        {
            return "puzzle";
        }

        if (ContainsAny(lower, "节奏", "音游", "rhythm"))
        {
            return "rhythm";
        }

        if (ContainsAny(lower, "赛车", "racing"))
        {
            return "racing";
        }

        if (ContainsAny(lower, "体育", "sports"))
        {
            return "sports";
        }

        if (ContainsAny(lower, "派对", "party"))
        {
            return "party-game";
        }

        if (ContainsAny(lower, "战棋", "回合制战术", "tactics", "turn-based tactics"))
        {
            return "turn-based-tactics";
        }

        if (ContainsAny(lower, "策略", "strategy"))
        {
            return "strategy";
        }

        if (ContainsAny(lower, "模拟", "simulation"))
        {
            return "simulation";
        }

        if (ContainsAny(lower, "沙盒", "sandbox"))
        {
            return "sandbox";
        }

        if (ContainsAny(lower, "放置", "增量", "idle", "incremental"))
        {
            return "idle-incremental";
        }

        if (ContainsAny(lower, "视觉小说", "visual novel"))
        {
            return "visual-novel";
        }

        if (ContainsAny(lower, "文字", "text-based", "interactive fiction"))
        {
            return "text-based";
        }

        if (ContainsAny(lower, "冒险", "adventure"))
        {
            return "adventure";
        }

        if (ContainsAny(lower, "moba"))
        {
            return "moba";
        }

        if (ContainsAny(lower, "银河恶魔城", "metroidvania"))
        {
            return "metroidvania";
        }

        return "";
    }

    private static bool ContainsAny(string value, params string[] needles)
    {
        return needles.Any(needle => value.Contains(needle, StringComparison.Ordinal));
    }
}
