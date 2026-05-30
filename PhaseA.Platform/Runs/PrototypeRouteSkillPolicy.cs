using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public static class PrototypeRouteSkillPolicy
{
    private static readonly GameTypeRouteEngine Engine = new();

    public static PrototypeRouteSkillContext Resolve(ProjectSnapshot project)
    {
        return Engine.Resolve(project).RouteSkill;
    }

    public static GameTypeRouteProfile ResolveProfile(ProjectSnapshot project)
    {
        return Engine.Resolve(project);
    }

    public static bool IsRpgProject(ProjectSnapshot project)
    {
        return GameTypeRouteProfiles.IsRpgProject(project);
    }

    public static string BuildPromptBlock(ProjectSnapshot project)
    {
        return Engine.BuildPromptBlock(project);
    }

    public static PrototypeRouteSkillAvailability CheckAvailable(ProjectSnapshot project)
    {
        return Engine.CheckAvailable(project);
    }

    public static PrototypeRouteSkillAvailability EnsureAvailable(ProjectSnapshot project)
    {
        return Engine.EnsureAvailable(project);
    }
}

public sealed record PrototypeRouteSkillContext(
    string RouteSkillId,
    string RouteSkillName,
    string RouteSkillLabel,
    string RouteSkillGuide,
    string RouteSkillContract,
    string? ContractRelativePath = null)
{
    public string SkillRelativePath => $".agents/skills/{RouteSkillId}/SKILL.md";
}

public sealed record PrototypeRouteSkillAvailability(
    PrototypeRouteSkillContext Context,
    bool IsAvailable,
    string FailureCode,
    string FailureMessage);
