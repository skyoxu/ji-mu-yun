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
