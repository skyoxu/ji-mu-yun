using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public interface IGameTypeRouteEngine
{
    GameTypeRouteProfile Resolve(ProjectSnapshot project);

    PrototypeRouteSkillAvailability CheckAvailable(ProjectSnapshot project);

    PrototypeRouteSkillAvailability EnsureAvailable(ProjectSnapshot project);

    string BuildPromptBlock(ProjectSnapshot project);
}

public sealed class GameTypeRouteEngine : IGameTypeRouteEngine
{
    public GameTypeRouteProfile Resolve(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);
        return GameTypeRouteProfiles.Resolve(project);
    }

    public PrototypeRouteSkillAvailability CheckAvailable(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);
        var profile = Resolve(project);
        return CheckProfileAvailable(project, profile);
    }

    public PrototypeRouteSkillAvailability EnsureAvailable(ProjectSnapshot project)
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

    public string BuildPromptBlock(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);
        var profile = Resolve(project);
        var context = profile.RouteSkill;
        return $"""
            Game type route profile:
            - GameTypeId: {profile.GameTypeId}
            - ProfileId: {profile.ProfileId}
            - RouteSetId: {profile.RouteSetId}
            - PromptProtocolId: {profile.PromptProtocolId}
            - PlannerId: {profile.PlannerId}
            - EvaluatorId: {profile.EvaluatorId}
            - ExecutorId: {profile.ExecutorId}
            - NeedsFixId: {profile.NeedsFixId}
            - FinalAcceptanceId: {profile.FinalAcceptanceId}

            Route skill context:
            - RouteSkillId: {context.RouteSkillId}
            - RouteSkillName: {context.RouteSkillName}
            - RouteSkillLabel: {context.RouteSkillLabel}
            - RouteSkillGuide: {context.RouteSkillGuide}
            - RouteSkillContract: {context.RouteSkillContract}
            - MandatorySkillEntry: ${context.RouteSkillId}
            - MandatorySkillPath: {context.SkillRelativePath}
            - Rule: all cloud business top-level routes must enter through this game type route profile before planning, coding, repairing, validating, or reporting.
            - Rule: treat the selected route skill as the operating playbook for this route; load and follow it before using generic prototype behavior.
            - Rule: do not run a bare/generic prototype route when the route skill is missing or unresolved; report route_skill_required instead.
            - Rule: recover hosted project memory from project guide, contract, route state, ledger, and latest validation; do not use AGENTS.md as hosted project memory.
            - Rule: read-only JSON routes must use ILlmRouteEngine; executable Codex routes must use CodexHostedProcessCommandFactory with stdin prompt transport.
            """;
    }

    private static PrototypeRouteSkillAvailability CheckProfileAvailable(ProjectSnapshot project, GameTypeRouteProfile profile)
    {
        var context = profile.RouteSkill;
        var skillPath = Path.Combine(project.RepoPath, context.SkillRelativePath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(skillPath))
        {
            return new PrototypeRouteSkillAvailability(
                context,
                false,
                "route_skill_required",
                $"Required route skill is missing: {context.SkillRelativePath}");
        }

        if (!string.IsNullOrWhiteSpace(context.ContractRelativePath))
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

public static class GameTypeRouteProfiles
{
    public static GameTypeRouteProfile Resolve(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);
        if (IsSurvivorsLikeProject(project))
        {
            return SurvivorsLike;
        }

        if (IsRpgProject(project))
        {
            return Rpg;
        }

        return Default;
    }

    public static bool IsRpgProject(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);
        var text = string.Join(" ", project.GameTypeSource, project.TemplateRuleId, project.Name, project.GameName).ToLowerInvariant();
        return text.Contains("rpg", StringComparison.Ordinal) ||
               text.Contains("dragon quest", StringComparison.Ordinal) ||
               text.Contains("角色扮演", StringComparison.Ordinal) ||
               text.Contains("勇者斗恶龙", StringComparison.Ordinal);
    }

    public static bool IsSurvivorsLikeProject(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);
        var text = string.Join(" ", project.GameTypeSource, project.TemplateRuleId, project.Name, project.GameName).ToLowerInvariant();
        return text.Contains("vampire survivors", StringComparison.Ordinal) ||
               text.Contains("survivors like", StringComparison.Ordinal) ||
               text.Contains("survivors-like", StringComparison.Ordinal) ||
               text.Contains("survivor like", StringComparison.Ordinal) ||
               text.Contains("survivor-like", StringComparison.Ordinal) ||
               text.Contains("survivorslike", StringComparison.Ordinal) ||
               text.Contains("bullet heaven", StringComparison.Ordinal) ||
               text.Contains("auto shooter", StringComparison.Ordinal) ||
               text.Contains("arena survival", StringComparison.Ordinal) ||
               text.Contains("horde survival", StringComparison.Ordinal) ||
               text.Contains("\u5438\u8840\u9b3c\u5e78\u5b58\u8005", StringComparison.Ordinal) ||
               text.Contains("\u5e78\u5b58\u8005like", StringComparison.Ordinal) ||
               text.Contains("\u5e78\u5b58\u8005\u7c7b", StringComparison.Ordinal) ||
               text.Contains("\u5272\u8349", StringComparison.Ordinal) ||
               text.Contains("\u8089\u9e3d\u5272\u8349", StringComparison.Ordinal);
    }

    public static readonly GameTypeRouteProfile Rpg = new(
        "rpg",
        "godot-rpg-v1",
        "rpg-prototype-routes-v1",
        "rpg-prompt-protocol-v1",
        new PrototypeRouteSkillContext(
            "prototype-rpg-godot-zh",
            "RPG 原型 skill",
            "RPG 栏目默认路由技能",
            "用来统一约束 prototype / iteration-plan / execute-next-goal / needs-fix 四条流水线。",
            "地图场景、战斗场景、奖励闭环、基础素材与 UI 验收",
            ".agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md"),
        "rpg-iteration-planner-v1",
        "rpg-plan-evaluator-v1",
        "rpg-goal-executor-v1",
        "rpg-needs-fix-v1",
        "rpg-final-acceptance-v1");

    public static readonly GameTypeRouteProfile SurvivorsLike = new(
        "survivorslike",
        "godot-survivorslike-v1",
        "survivorslike-prototype-routes-v1",
        "survivorslike-prompt-protocol-v1",
        new PrototypeRouteSkillContext(
            "prototype-survivorslike-godot-zh",
            "Vampire Survivors-like prototype skill",
            "Vampire Survivors-like route skill",
            "Constrain prototype / iteration-plan / execute-next-goal / needs-fix around a short arena survival first loop.",
            "Arena survival, spawn pressure, auto-attack, pickups, level-up choices, escalation, run summary",
            ".agents/skills/prototype-survivorslike-godot-zh/references/survivorslike-prototype-contract.md"),
        "survivorslike-iteration-planner-v1",
        "survivorslike-plan-evaluator-v1",
        "survivorslike-goal-executor-v1",
        "survivorslike-needs-fix-v1",
        "survivorslike-final-acceptance-v1");

    public static readonly GameTypeRouteProfile Default = new(
        "default",
        "godot-playable-default-v1",
        "default-prototype-routes-v1",
        "default-prompt-protocol-v1",
        new PrototypeRouteSkillContext(
            "prototype-7day-playable-godot-zh",
            "原型骨架创建 skill",
            "默认原型路由技能",
            "用来统一约束 prototype / iteration-plan / execute-next-goal / needs-fix 四条流水线。",
            "原型骨架创建通用验收",
            null),
        "default-iteration-planner-v1",
        "default-plan-evaluator-v1",
        "default-goal-executor-v1",
        "default-needs-fix-v1",
        "default-final-acceptance-v1");
}

public sealed record GameTypeRouteProfile(
    string GameTypeId,
    string ProfileId,
    string RouteSetId,
    string PromptProtocolId,
    PrototypeRouteSkillContext RouteSkill,
    string PlannerId,
    string EvaluatorId,
    string ExecutorId,
    string NeedsFixId,
    string FinalAcceptanceId);
