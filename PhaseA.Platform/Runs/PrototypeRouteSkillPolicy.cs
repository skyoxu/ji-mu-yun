using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public static class PrototypeRouteSkillPolicy
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
            - MandatorySkillEntry: ${context.RouteSkillId}
            - MandatorySkillPath: {context.SkillRelativePath}
            - Rule: all cloud business top-level routes must enter through this route skill context before planning, coding, repairing, validating, or reporting.
            - Rule: treat the selected route skill as the operating playbook for this route; load and follow it before using generic prototype behavior.
            - Rule: do not run a bare/generic prototype route when the route skill is missing or unresolved; report route_skill_required instead.
            """;
    }

    public static PrototypeRouteSkillAvailability CheckAvailable(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);

        var context = Resolve(project);
        var skillPath = Path.Combine(project.RepoPath, context.SkillRelativePath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(skillPath))
        {
            return new PrototypeRouteSkillAvailability(
                context,
                false,
                "route_skill_required",
                $"Required route skill is missing: {context.SkillRelativePath}");
        }

        if (IsRpgProject(project))
        {
            var contractPath = Path.Combine(project.RepoPath, context.ContractRelativePath!.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(contractPath))
            {
                return new PrototypeRouteSkillAvailability(
                    context,
                    false,
                    "route_skill_contract_required",
                    $"Required route skill contract is missing: {context.ContractRelativePath}");
            }
        }

        return new PrototypeRouteSkillAvailability(context, true, "", "");
    }

    public static PrototypeRouteSkillAvailability EnsureAvailable(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);

        var availability = CheckAvailable(project);
        if (availability.IsAvailable)
        {
            return availability;
        }

        TrySeedRouteSkillFromHost(project, availability.Context);
        return CheckAvailable(project);
    }

    private static void TrySeedRouteSkillFromHost(ProjectSnapshot project, PrototypeRouteSkillContext context)
    {
        var sourceRoot = ResolveHostRepositoryRoot(context);
        if (string.IsNullOrWhiteSpace(sourceRoot))
        {
            return;
        }

        var sourceSkillDirectory = Path.Combine(sourceRoot, ".agents", "skills", context.RouteSkillId);
        var targetSkillDirectory = Path.Combine(project.RepoPath, ".agents", "skills", context.RouteSkillId);
        if (!Directory.Exists(sourceSkillDirectory))
        {
            return;
        }

        CopyDirectory(sourceSkillDirectory, targetSkillDirectory);
    }

    private static string? ResolveHostRepositoryRoot(PrototypeRouteSkillContext context)
    {
        foreach (var root in CandidateHostRoots())
        {
            var skillPath = Path.Combine(root, context.SkillRelativePath.Replace('/', Path.DirectorySeparatorChar));
            if (File.Exists(skillPath))
            {
                return root;
            }
        }

        return null;
    }

    private static IEnumerable<string> CandidateHostRoots()
    {
        var current = Directory.GetCurrentDirectory();
        foreach (var candidate in WalkParents(current))
        {
            yield return candidate;
        }

        foreach (var candidate in WalkParents(AppContext.BaseDirectory))
        {
            yield return candidate;
        }
    }

    private static IEnumerable<string> WalkParents(string start)
    {
        var directory = new DirectoryInfo(Path.GetFullPath(start));
        while (directory is not null)
        {
            yield return directory.FullName;
            directory = directory.Parent;
        }
    }

    private static void CopyDirectory(string sourceDirectory, string targetDirectory)
    {
        Directory.CreateDirectory(targetDirectory);
        foreach (var directory in Directory.EnumerateDirectories(sourceDirectory, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(sourceDirectory, directory);
            Directory.CreateDirectory(Path.Combine(targetDirectory, relative));
        }

        foreach (var file in Directory.EnumerateFiles(sourceDirectory, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(sourceDirectory, file);
            var destination = Path.Combine(targetDirectory, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            File.Copy(file, destination, overwrite: true);
        }
    }
}

public sealed record PrototypeRouteSkillContext(
    string RouteSkillId,
    string RouteSkillName,
    string RouteSkillLabel,
    string RouteSkillGuide,
    string RouteSkillContract)
{
    public string SkillRelativePath => $".agents/skills/{RouteSkillId}/SKILL.md";

    public string? ContractRelativePath => RouteSkillId == "prototype-rpg-godot-zh"
        ? ".agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md"
        : null;
}

public sealed record PrototypeRouteSkillAvailability(
    PrototypeRouteSkillContext Context,
    bool IsAvailable,
    string FailureCode,
    string FailureMessage);
