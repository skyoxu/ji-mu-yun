using System.Text.RegularExpressions;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public static class PrototypePhysicsRequirementPolicy
{
    private static readonly string[] PhysicsRequiredTerms =
    [
        "action", "动作", "real-time", "realtime", "实时", "tps", "fps",
        "action rpg", "arpg", "动作 rpg", "动作角色扮演",
        "hack and slash", "hack-and-slash", "砍杀", "slash",
        "souls-like", "soulslike", "类魂", "魂like",
        "dungeon crawler", "dungeon-crawler", "地牢探索", "地城探索",
        "third person", "third-person", "第三人称", "first person", "first-person", "第一人称",
        "platformer", "平台跳跃", "metroidvania", "类银河恶魔城",
        "roguelike action", "action roguelike", "动作 roguelike", "动作肉鸽",
        "survivors", "幸存者", "割草", "arena survival",
        "shooter", "射击", "top-down shooter", "俯视角射击", "bullet hell", "弹幕", "beat em up", "清版动作",
        "extraction shooter", "loot extraction", "raid extraction", "extraction raid",
        "搜打撤", "搜打撤离", "撤离射击", "撤离搜刮", "搜刮撤离", "逃离鸭科夫",
        "fighting", "格斗", "racing", "竞速", "sports", "体育",
        "physics", "物理", "collision", "碰撞", "hitbox", "hurtbox", "命中", "受击",
        "dodge", "roll", "翻滚", "dash", "冲刺", "knockback", "击退",
        "navigation", "pathfinding", "追踪", "寻路", "enemy chase", "敌人追踪"
    ];

    private static readonly string[] ThreeDimensionalTerms =
    [
        "3d", "3-d", "三维", "third person", "third-person", "第三人称",
        "first person", "first-person", "第一人称", "tps", "fps",
        "camera3d", "node3d", "characterbody3d", "gltf", "glb", "kaykit"
    ];

    private static readonly string[] TwoDimensionalTerms =
    [
        "2d", "2-d", "二维", "top-down", "top down", "俯视角",
        "side-scroller", "sidescroller", "横版", "platformer", "平台跳跃",
        "camera2d", "node2d", "characterbody2d"
    ];

    public static PrototypePhysicsRequirementResult Evaluate(ProjectSnapshot project, string? gddText = null)
    {
        ArgumentNullException.ThrowIfNull(project);
        var source = string.Join("\n", project.GameTypeSource, project.TemplateRuleId, project.Name, project.GameName, gddText ?? "");
        var normalized = Normalize(source);
        var matchedTerms = PhysicsRequiredTerms
            .Where(term => normalized.Contains(Normalize(term), StringComparison.OrdinalIgnoreCase))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(16)
            .ToArray();
        var requiresPhysics = matchedTerms.Length > 0;
        var dimension = ResolveDimension(normalized);
        var engine = dimension == "3d" ? "GodotPhysics3D" : dimension == "2d" ? "GodotPhysics2D" : "GodotPhysics2D_or_GodotPhysics3D_by_scene_dimension";
        var nodeContract = dimension switch
        {
            "3d" => "Use Node3D/CharacterBody3D/Area3D/CollisionShape3D/Camera3D and _PhysicsProcess/MoveAndSlide where player-operated motion, hit detection, or room traversal exists.",
            "2d" => "Use Node2D/CharacterBody2D/Area2D/CollisionShape2D/Camera2D and _PhysicsProcess/MoveAndSlide where player-operated motion, hit detection, or room traversal exists.",
            _ => "Choose 2D or 3D from the GDD scene dimension, then use the matching CharacterBody, Area, CollisionShape, camera, _PhysicsProcess, and MoveAndSlide contracts."
        };

        return new PrototypePhysicsRequirementResult(requiresPhysics, dimension, engine, matchedTerms, nodeContract);
    }

    public static string BuildPromptBlock(ProjectSnapshot project, string? gddText = null)
    {
        var result = Evaluate(project, gddText);
        if (!result.RequiresPhysics)
        {
            return """
                Physics embodiment policy:
                - RequiresPhysics: false
                - Rule: If the current milestone adds player-operated movement, collision, hit detection, traversal, or enemy chasing, re-evaluate and use the matching Godot physics nodes instead of UI-only state changes.
                - StateMachineGuard: UI/HUD may report game state, but it must not become the playable authority for action, shooter, traversal, or extraction loops if those loops appear later in the GDD or module spec.
                """;
        }

        return $"""
            Physics embodiment policy:
            - RequiresPhysics: true
            - Dimension: {result.Dimension}
            - RecommendedEngine: {result.RecommendedEngine}
            - MatchedTerms: {string.Join(", ", result.MatchedTerms)}
            - NodeContract: {result.NodeContract}
            - Rule: playable milestones must embody movement, collision, hit detection, traversal, or enemy pressure in scene/runtime objects when the GDD asks for them; UI text may explain state but must not replace player-operated gameplay.
            - StateMachineGuard: controllers may store state, but action/shooter/extraction gameplay must not be completed mainly by button panels, labels, scripted state transitions, or abstract timers. The player's core loop must be driven by continuous input, scene objects, physics/collision areas, and visible feedback.
            - LocalPlaytestContract: for shooter/extraction/action loops, acceptance must cover player-operated movement, aim or facing, primary action, enemy pressure, loot or interaction contact, win/fail/extraction conditions, and HUD feedback as one local playable loop.
            """;
    }

    private static string ResolveDimension(string normalized)
    {
        if (ThreeDimensionalTerms.Any(term => normalized.Contains(Normalize(term), StringComparison.OrdinalIgnoreCase)))
        {
            return "3d";
        }

        if (TwoDimensionalTerms.Any(term => normalized.Contains(Normalize(term), StringComparison.OrdinalIgnoreCase)))
        {
            return "2d";
        }

        return "unspecified";
    }

    private static string Normalize(string value)
        => Regex.Replace(value.ToLowerInvariant(), @"\s+", " ").Trim();
}

public sealed record PrototypePhysicsRequirementResult(
    bool RequiresPhysics,
    string Dimension,
    string RecommendedEngine,
    IReadOnlyList<string> MatchedTerms,
    string NodeContract);
