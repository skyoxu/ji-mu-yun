using System.Text.RegularExpressions;
using System.Text.Json;

namespace PhaseA.Platform.Runs;

internal static class JrpgRouteSemantics
{
    private static readonly HashSet<string> PrototypeContractIntentFields = new(StringComparer.OrdinalIgnoreCase)
    {
        "hypothesis",
        "core_player_fantasy",
        "minimum_playable_loop",
        "success_criteria",
        "game_feature",
        "core_gameplay_loop",
        "win_fail_conditions"
    };

    private static readonly string[] BattleNegationPhrases =
    [
        "non-combat",
        "non combat",
        "noncombat",
        "no combat",
        "without combat",
        "without combat and reward choices",
        "without a combat scene",
        "no battle",
        "without battle",
        "without encounter, battle",
        "without encounter, battle, or reward",
        "without encounter, battle, or reward work",
        "without encounter, battle, or reward requirements",
        "remove combat",
        "removed combat",
        "combat must be removed",
        "combat and rewards must be removed",
        "remove battle",
        "removed battle",
        "battle must be removed",
        "no encounter",
        "without encounter",
        "no enemy encounter",
        "without enemy encounter",
        "dialogue-only",
        "dialogue only",
        "exploration-only",
        "exploration only",
        "无战斗",
        "没有战斗",
        "不含战斗",
        "不需要战斗",
        "非战斗",
        "无遇敌",
        "没有遇敌",
        "不含遇敌",
        "不需要遇敌"
    ];

    private static readonly string[] BattleNormalizationPhrases =
    [
        ..BattleNegationPhrases,
        "no battles",
        "without battles",
        "no encounters",
        "without encounters",
        "no enemy encounters",
        "without enemy encounters",
        "no enemy",
        "without enemy",
        "no enemies",
        "without enemies",
        "no monster",
        "without monster",
        "no monsters",
        "without monsters",
        "no conflict",
        "without conflict",
        "jrpg first loop: battle or challenge resolution",
        "battle or challenge resolution",
        "battle_or_challenge_resolution",
        "无敌人",
        "没有敌人",
        "不含敌人",
        "不需要敌人",
        "无冲突",
        "没有冲突",
        "不含冲突"
    ];

    private static readonly string[] RewardNegationPhrases =
    [
        "no reward",
        "without reward",
        "without encounter, battle, or reward",
        "without encounter, battle, or reward work",
        "without encounter, battle, or reward requirements",
        "no reward choices",
        "without reward choices",
        "without combat and reward choices",
        "remove reward",
        "removed reward",
        "reward must be removed",
        "rewards must be removed",
        "combat and rewards must be removed",
        "remove rewards",
        "removed rewards",
        "remove reward choices",
        "removed reward choices",
        "no loot",
        "without loot",
        "no leveling",
        "without leveling",
        "no level up",
        "without level up",
        "no exp",
        "without exp",
        "no xp",
        "without xp",
        "no item",
        "without item",
        "no items",
        "without items",
        "no skill",
        "without skill",
        "no skills",
        "without skills",
        "不发奖励",
        "无奖励",
        "没有奖励",
        "不含奖励",
        "不需要奖励",
        "无掉落",
        "没有掉落",
        "不掉落",
        "不含掉落",
        "无升级",
        "没有升级",
        "不升级",
        "不含升级",
        "无经验",
        "没有经验",
        "不给经验",
        "不含经验",
        "无道具",
        "没有道具",
        "不给道具",
        "不含道具",
        "无技能",
        "没有技能",
        "不给技能",
        "不含技能",
        "不需要技能"
    ];

    private static readonly string[] RewardNormalizationPhrases =
    [
        ..RewardNegationPhrases,
        "jrpg first loop: growth, reward, or consequence feedback",
        "growth, reward, or consequence feedback",
        "growth_feedback",
        "without rewards"
    ];

    public static bool ContainsBattleNegation(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        return ContainsAny(text, BattleNegationPhrases);
    }

    public static bool ContainsRewardNegation(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        return ContainsAny(text, RewardNegationPhrases);
    }

    public static bool RequiresRewardFlow(string text)
    {
        var rewardText = NormalizeRewardDetectionText(text);
        return ContainsAny(rewardText,
            "reward",
            "rewardoptions",
            "applyreward",
            "3-choice",
            "three reward",
            "reward choice",
            "experience",
            "奖励",
            "三选一",
            "道具",
            "经验",
            "升级",
            "技能",
            "掉落") ||
            ContainsAsciiWord(rewardText, "xp") ||
            ContainsAsciiWord(rewardText, "exp") ||
            ContainsAsciiWord(rewardText, "item") ||
            ContainsAsciiWord(rewardText, "level") ||
            ContainsAsciiWord(rewardText, "skill") ||
            ContainsAsciiWord(rewardText, "drop");
    }

    public static bool RequiresBattleScene(string text)
    {
        var battleText = NormalizeBattleDetectionText(text);
        return ContainsAny(
            battleText,
            "battle",
            "combat",
            "battlescene",
            "encounter",
            "enemy",
            "monster",
            "boss",
            "fight",
            "victory battle",
            "battle victory",
            "battle defeat",
            "战斗",
            "遇敌",
            "敌人",
            "怪物",
            "击败");
    }

    public static string ExtractPrototypeContractIntentText(string? contractJson)
    {
        if (string.IsNullOrWhiteSpace(contractJson))
        {
            return string.Empty;
        }

        try
        {
            using var document = JsonDocument.Parse(contractJson);
            var parts = new List<string>();
            var root = document.RootElement;
            if (root.TryGetProperty("form_fields", out var formFields) &&
                formFields.ValueKind == JsonValueKind.Object)
            {
                foreach (var property in formFields.EnumerateObject())
                {
                    if (PrototypeContractIntentFields.Contains(property.Name))
                    {
                        AddJsonStringValues(parts, property.Value);
                    }
                }
            }

            if (root.TryGetProperty("input_traceability", out var traceability) &&
                traceability.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in traceability.EnumerateArray())
                {
                    if (item.ValueKind != JsonValueKind.Object ||
                        !item.TryGetProperty("field", out var fieldElement) ||
                        fieldElement.ValueKind != JsonValueKind.String ||
                        !PrototypeContractIntentFields.Contains(fieldElement.GetString() ?? string.Empty) ||
                        !item.TryGetProperty("value", out var valueElement))
                    {
                        continue;
                    }

                    AddJsonStringValues(parts, valueElement);
                }
            }

            return string.Join(" ", parts.Where(part => !string.IsNullOrWhiteSpace(part)));
        }
        catch (JsonException)
        {
            return string.Empty;
        }
    }

    public static string NormalizeBattleDetectionText(string text)
    {
        var normalized = text;
        foreach (var phrase in BattleNormalizationPhrases)
        {
            normalized = normalized.Replace(phrase, " ", StringComparison.OrdinalIgnoreCase);
        }

        return normalized;
    }

    public static string NormalizeRewardDetectionText(string text)
    {
        var normalized = text;
        foreach (var phrase in RewardNormalizationPhrases)
        {
            normalized = normalized.Replace(phrase, " ", StringComparison.OrdinalIgnoreCase);
        }

        return normalized;
    }

    private static bool ContainsAny(string text, params string[] needles)
    {
        return needles.Any(needle => text.Contains(needle, StringComparison.OrdinalIgnoreCase));
    }

    private static bool ContainsAny(string text, IEnumerable<string> needles)
    {
        return needles.Any(needle => text.Contains(needle, StringComparison.OrdinalIgnoreCase));
    }

    private static void AddJsonStringValues(List<string> parts, JsonElement element)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                foreach (var property in element.EnumerateObject())
                {
                    AddJsonStringValues(parts, property.Value);
                }

                break;
            case JsonValueKind.Array:
                foreach (var item in element.EnumerateArray())
                {
                    AddJsonStringValues(parts, item);
                }

                break;
            case JsonValueKind.String:
                var value = element.GetString();
                if (!string.IsNullOrWhiteSpace(value))
                {
                    parts.Add(value);
                }

                break;
        }
    }

    private static bool ContainsAsciiWord(string text, string word)
    {
        return Regex.IsMatch(text, $@"(?<![a-z0-9]){Regex.Escape(word)}(?![a-z0-9])", RegexOptions.IgnoreCase);
    }
}
