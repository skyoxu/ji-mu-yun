namespace PhaseA.Platform.Skills;

public sealed class SkillActionCatalog
{
    private static readonly SkillActionDefinition[] Defaults =
    [
        new(
            "game-design-master",
            "bmad-agent-game-designer",
            "游戏策划大师",
            "调用白名单游戏策划 skill，帮助梳理玩法、GDD、机制、叙事与原型设计建议。",
            "user",
            "codex-read-only"),
        new(
            "map-making-master",
            "generate2dmap",
            "地图制作大师",
            "调用白名单 2D 地图制作 skill，生成或细化可玩的 2D 场景地图方案。",
            "user",
            "codex-read-only"),
        new(
            "character-making-master",
            "generate2dsprite",
            "角色制作大师",
            "调用白名单 2D 角色与精灵制作 skill，生成或细化角色、敌人、NPC、道具和动画资源方案。",
            "user",
            "codex-read-only")
    ];

    public IReadOnlyList<SkillActionDefinition> ListAllowed(string role)
    {
        return Defaults
            .Where(action => action.Visibility == "user" || string.Equals(role, "admin", StringComparison.OrdinalIgnoreCase))
            .ToArray();
    }

    public SkillActionDefinition? Find(string actionId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(actionId);
        return Defaults.FirstOrDefault(action => string.Equals(action.ActionId, actionId, StringComparison.Ordinal));
    }
}
