using PhaseA.Platform.Data;
using PhaseA.Platform.Prototypes;

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

            Downstream source boundary:
            - Rule: this route profile is an internal platform routing identity, not a gameplay design source.
            - Rule: only the GDD route may read broad game-type sources such as docs/game-type-guides, prototype type kits, or route skill documents for design semantics.
            - Rule: planning, coding, repairing, validating, UI optimization, and readback routes must use only the current GDD-derived prototype contract, current module spec, route state, repair ledger, and latest validation evidence as gameplay requirements.
            - Rule: do not read docs/game-type-guides, docs/prototype-type-kits, or .agents/skills route documents to add new gameplay requirements after GDD generation.
            - Rule: recover hosted project memory from project guide, contract, route state, ledger, and latest validation; do not use AGENTS.md as hosted project memory.
            - Rule: read-only JSON routes must use ILlmRouteEngine; executable Codex routes must use CodexHostedProcessCommandFactory with stdin prompt transport.
            - {PrototypePlayerVisibleTextPolicy.PromptRule}

            {PrototypePhysicsRequirementPolicy.BuildPromptBlock(project)}
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
    private static readonly AsyncLocal<bool?> GenericPrototypeRouteOnlyOverride = new();

    public static bool UseGenericPrototypeRouteOnly => GenericPrototypeRouteOnlyOverride.Value ?? false;

    public static IDisposable UseGenericPrototypeRouteOnlyForTesting(bool value)
    {
        var previous = GenericPrototypeRouteOnlyOverride.Value;
        GenericPrototypeRouteOnlyOverride.Value = value;
        return new GenericPrototypeRouteOnlyOverrideScope(previous);
    }

    public static GameTypeRouteProfile Resolve(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);
        if (UseGenericPrototypeRouteOnly)
        {
            return Default;
        }

        if (IsSurvivorsLikeProject(project))
        {
            return SurvivorsLike;
        }

        if (IsDeckbuilderProject(project))
        {
            return Deckbuilder;
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
        var evidence = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson);
        return string.Equals(evidence.MatchedGameTypeId, "rpg", StringComparison.Ordinal) ||
               evidence.NormalizedGenreTags.Contains("rpg", StringComparer.Ordinal) ||
               evidence.NormalizedGenreTags.Contains("role-playing", StringComparer.Ordinal) ||
               evidence.NormalizedGenreTags.Contains("jrpg", StringComparer.Ordinal);
    }

    public static bool IsSurvivorsLikeProject(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);
        var evidence = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson);
        return string.Equals(evidence.MatchedGameTypeId, "survivorslike", StringComparison.Ordinal) ||
               evidence.NormalizedGenreTags.Contains("survivorslike", StringComparer.Ordinal) ||
               evidence.NormalizedGenreTags.Contains("vampire-survivors", StringComparer.Ordinal) ||
               evidence.NormalizedGenreTags.Contains("bullet-heaven", StringComparer.Ordinal) ||
               evidence.NormalizedGenreTags.Contains("auto-shooter", StringComparer.Ordinal) ||
               evidence.NormalizedGenreTags.Contains("arena-survival", StringComparer.Ordinal) ||
               evidence.NormalizedGenreTags.Contains("horde-survival", StringComparer.Ordinal);
    }

    public static bool IsDeckbuilderProject(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);
        var tags = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson).NormalizedGenreTags;
        return tags.Contains("deckbuilder", StringComparer.Ordinal) ||
               tags.Contains("deckbuild", StringComparer.Ordinal) ||
               tags.Contains("deck-build", StringComparer.Ordinal) ||
               tags.Contains("deck-building", StringComparer.Ordinal) ||
               tags.Contains("deckbuilding", StringComparer.Ordinal) ||
               tags.Contains("deck-builder", StringComparer.Ordinal) ||
               tags.Contains("roguelike-deckbuilder", StringComparer.Ordinal) ||
               tags.Contains("card-battler", StringComparer.Ordinal) ||
               tags.Contains("card-roguelike", StringComparer.Ordinal) ||
               (tags.Contains("card", StringComparer.Ordinal) && tags.Contains("roguelike", StringComparer.Ordinal));
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

    public static readonly GameTypeRouteProfile Deckbuilder = new(
        "deckbuilder",
        "godot-deckbuilder-v1",
        "deckbuilder-prototype-routes-v1",
        "deckbuilder-prompt-protocol-v1",
        new PrototypeRouteSkillContext(
            "prototype-deckbuilder-godot-zh",
            "Deckbuilder prototype skill",
            "Deckbuilder route skill",
            "Constrain prototype / iteration-plan / execute-next-goal / needs-fix around a short card-building first loop.",
            "Run context, readable starter deck, resources and turns, enemy intent, card play, deck cycling, combat result, reward draft, deck mutation, optional route choice",
            ".agents/skills/prototype-deckbuilder-godot-zh/references/deckbuilder-prototype-contract.md"),
        "deckbuilder-iteration-planner-v1",
        "deckbuilder-plan-evaluator-v1",
        "deckbuilder-goal-executor-v1",
        "deckbuilder-needs-fix-v1",
        "deckbuilder-final-acceptance-v1");

    public static readonly GameTypeRouteProfile Default = new(
        "default",
        "godot-playable-default-v1",
        "default-prototype-routes-v1",
        "default-prompt-protocol-v1",
        new PrototypeRouteSkillContext(
            "prototype-7day-playable-godot-zh",
            "游戏场景创建 skill",
            "默认原型路由技能",
            "用来统一约束 prototype / iteration-plan / execute-next-goal / needs-fix 四条流水线。",
            "游戏场景创建通用验收",
            null),
        "default-iteration-planner-v1",
        "default-plan-evaluator-v1",
        "default-goal-executor-v1",
        "default-needs-fix-v1",
        "default-final-acceptance-v1");

    private sealed class GenericPrototypeRouteOnlyOverrideScope(bool? previous) : IDisposable
    {
        public void Dispose()
        {
            GenericPrototypeRouteOnlyOverride.Value = previous;
        }
    }
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
