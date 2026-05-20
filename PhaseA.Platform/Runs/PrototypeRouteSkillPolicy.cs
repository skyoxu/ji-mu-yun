using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

internal static class PrototypeRouteSkillPolicy
{
    public static PrototypeRouteSkillContext Resolve(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);

        if (IsRpgProject(project))
        {
            return new PrototypeRouteSkillContext(
                "prototype-rpg-godot-zh",
                "RPG 原型 skill",
                "RPG 栏目默认路由技能",
                "用来统一约束 prototype / iteration-plan / execute-next-goal / needs-fix 四条流水线。",
                "地图场景、战斗场景、奖励闭环、基础素材与 UI 验收");
        }

        return new PrototypeRouteSkillContext(
            "prototype-7day-playable-godot-zh",
            "7步可玩原型 skill",
            "默认原型路由技能",
            "用来统一约束 prototype / iteration-plan / execute-next-goal / needs-fix 四条流水线。",
            "7步可玩原型通用验收");
    }

    public static bool IsRpgProject(ProjectSnapshot project)
    {
        var text = string.Join(" ", project.GameTypeSource, project.TemplateRuleId, project.Name, project.GameName).ToLowerInvariant();
        return text.Contains("rpg", StringComparison.Ordinal) ||
               text.Contains("dragon quest", StringComparison.Ordinal) ||
               text.Contains("角色扮演", StringComparison.Ordinal) ||
               text.Contains("勇者斗恶龙", StringComparison.Ordinal);
    }

    public static string BuildPromptBlock(ProjectSnapshot project)
    {
        var context = Resolve(project);
        return $"""
            Route skill context:
            - RouteSkillId: {context.RouteSkillId}
            - RouteSkillName: {context.RouteSkillName}
            - RouteSkillLabel: {context.RouteSkillLabel}
            - RouteSkillGuide: {context.RouteSkillGuide}
            - RouteSkillContract: {context.RouteSkillContract}
            """;
    }
}

internal sealed record PrototypeRouteSkillContext(
    string RouteSkillId,
    string RouteSkillName,
    string RouteSkillLabel,
    string RouteSkillGuide,
    string RouteSkillContract);
