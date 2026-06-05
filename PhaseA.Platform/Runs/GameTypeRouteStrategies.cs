using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

// ADR-0018 and ADR-0025 keep Godot runtime work and validation behind stable platform/workflow boundaries.
internal interface IGameTypeRouteStrategy
{
    string GameTypeId { get; }

    bool RequiresModelBackedIterationPlanning { get; }

    bool RequiresNonEmptyIterationGoals { get; }

    bool UsesSpecializedIterationPlanning { get; }

    bool UsesSpecializedPlanEvaluation { get; }

    PrototypeGoalAcceptanceContract? ResolveAcceptanceContract(ProjectSnapshot project, ProjectIterationGoalSnapshot goal);
}

internal static class GameTypeRouteStrategies
{
    private static readonly IGameTypeRouteStrategy Rpg = new RpgGameTypeRouteStrategy();
    private static readonly IGameTypeRouteStrategy SurvivorsLike = new SurvivorsLikeGameTypeRouteStrategy();
    private static readonly IGameTypeRouteStrategy Default = new DefaultGameTypeRouteStrategy();

    public static IGameTypeRouteStrategy Resolve(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);
        return Resolve(project, PrototypeRouteSkillPolicy.ResolveProfile(project));
    }

    public static IGameTypeRouteStrategy Resolve(ProjectSnapshot project, GameTypeRouteProfile profile)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(profile);

        if (string.Equals(profile.GameTypeId, "survivorslike", StringComparison.OrdinalIgnoreCase))
        {
            return SurvivorsLike;
        }

        return string.Equals(profile.GameTypeId, "rpg", StringComparison.OrdinalIgnoreCase) || RpgGameTypeRouteStrategy.HasLegacyRpgShape(project)
            ? Rpg
            : Default;
    }
}

internal sealed class DefaultGameTypeRouteStrategy : IGameTypeRouteStrategy
{
    public string GameTypeId => "default";

    public bool RequiresModelBackedIterationPlanning => false;

    public bool RequiresNonEmptyIterationGoals => false;

    public bool UsesSpecializedIterationPlanning => false;

    public bool UsesSpecializedPlanEvaluation => false;

    public PrototypeGoalAcceptanceContract? ResolveAcceptanceContract(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(goal);
        return null;
    }
}

internal sealed class RpgGameTypeRouteStrategy : IGameTypeRouteStrategy
{
    public string GameTypeId => "rpg";

    public bool RequiresModelBackedIterationPlanning => true;

    public bool RequiresNonEmptyIterationGoals => true;

    public bool UsesSpecializedIterationPlanning => true;

    public bool UsesSpecializedPlanEvaluation => true;

    public PrototypeGoalAcceptanceContract? ResolveAcceptanceContract(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(goal);

        if (!IsRpgProject(project))
        {
            return null;
        }

        var routeTitle = ResolveRpgRouteGoalTitle(goal);
        if (routeTitle is not null)
        {
            return routeTitle;
        }

        var semantic = ResolveRpgGoalSemantic(goal);
        if (semantic is not null)
        {
            return semantic;
        }

        return null;
    }

    public static bool HasLegacyRpgShape(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);
        return File.Exists(Path.Combine(project.RepoPath, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs"));
    }

    private static bool IsRpgProject(ProjectSnapshot project)
    {
        return PrototypeRouteSkillPolicy.IsRpgProject(project) || HasLegacyRpgShape(project);
    }

    private static PrototypeGoalAcceptanceContract? ResolveRpgRouteGoalTitle(ProjectIterationGoalSnapshot goal)
    {
        var title = goal.Title ?? "";
        if (string.IsNullOrWhiteSpace(title))
        {
            return null;
        }

        if (ContainsAny(title, "RPG Step 1: Start Adventure to visible MapScene", "rpg-step1-visible-map-movement"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step1-visible-map-movement",
                ["MoveOnMap"],
                MapEntryAcceptance: true);
        }

        if (ContainsAny(title, "JRPG First Loop: opening context and player objective"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-opening-context-objective",
                ["Objective", "Start Adventure"],
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(title, "JRPG First Loop: field navigation and stable control"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-field-navigation-stable-control",
                ["MoveOnMap"],
                MapEntryAcceptance: true);
        }

        if (ContainsAny(title, "JRPG First Loop: interaction and discovery beat"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-interaction-discovery",
                ["Objective", "Interact"],
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(title, "JRPG First Loop: conflict entry trigger"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-conflict-entry-trigger",
                ["MoveOnMap", "ShouldReachRewardPhase_AfterWinningTheFirstEncounter"],
                MapEntryAcceptance: true);
        }

        if (ContainsAny(title, "JRPG First Loop: battle or challenge resolution"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-battle-or-challenge-resolution",
                ["ResolveAttackTurn", "Victory", "BattlesWon"],
                BattleSceneAcceptance: true);
        }

        if (ContainsAny(title, "JRPG First Loop: party or character state readability"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-party-character-state-readability",
                ["HP", "Stats", "Status"],
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(title, "JRPG First Loop: growth, reward, or consequence feedback"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-growth-reward-consequence-feedback",
                ["RewardOptions.Count", "ApplyReward", "Battle reward selected"],
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(title, "JRPG First Loop: return or continue loop"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-return-or-continue-loop",
                ["Return to the map", "MoveOnMap"],
                MapEntryAcceptance: true,
                RewardFlowAcceptance: true);
        }

        if (ContainsAny(title, "JRPG First Loop: quest or story progress"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-quest-story-progress",
                ["Objective", "Quest"],
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(title, "JRPG First Loop: final first-loop acceptance"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-final-first-loop-acceptance",
                ["MoveOnMap", "ResolveAttackTurn", "RewardOptions.Count", "ApplyReward", "Battle reward selected", "VictoryBattleCount", "IsVictory", "IsGameOver"],
                AssetUsageAcceptance: true,
                MapEntryAcceptance: true,
                BattleSceneAcceptance: true,
                RewardFlowAcceptance: true,
                MainSceneHostUiHiddenAcceptance: true,
                FinalAcceptance: true);
        }

        if (ContainsAny(title, "RPG Step 2: encounter trigger and guaranteed encounter validation", "rpg-step2-encounter-trigger"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step2-encounter-trigger",
                ["MoveOnMap", "ShouldReachRewardPhase_AfterWinningTheFirstEncounter"],
                MapEntryAcceptance: true);
        }

        if (ContainsAny(title, "RPG Step 3: BattleScene visualization and settlement validation", "rpg-step3-battlescene-settlement"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step3-battlescene-settlement",
                ["ShouldReachRewardPhase_AfterWinningTheFirstEncounter", "ResolveAttackTurn", "BattlesWon", "Victory"],
                BattleSceneAcceptance: true);
        }

        if (ContainsAny(title, "RPG Step 4: reward 3-choice understandability validation", "rpg-step4-reward-choice-readability"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step4-reward-choice-readability",
                ["RewardOptions.Count", "Battle reward selected"],
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(title, "RPG Step 5: reward application and return-to-map validation", "rpg-step5-reward-loop-return-map"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step5-reward-loop-return-map",
                ["RewardOptions.Count", "ApplyReward", "Battle reward selected", "Return to the map"],
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(title, "RPG Step 6: win/fail visibility and readability validation", "rpg-step6-win-fail-visibility"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step6-win-fail-visibility",
                ["VictoryBattleCount", "IsVictory", "IsGameOver"],
                StaticAcceptanceOnly: true);
        }

        return null;
    }

    private static PrototypeGoalAcceptanceContract? ResolveRpgGoalSemantic(ProjectIterationGoalSnapshot goal)
    {
        var combined = string.Join(" ", goal.Title ?? "", goal.Description ?? "", goal.AcceptanceHint ?? "");
        if (string.IsNullOrWhiteSpace(combined))
        {
            return null;
        }

        var text = combined.ToLowerInvariant();
        if (ContainsAny(text, "full playable prototype acceptance", "final acceptance", "\u6700\u7ec8\u9a8c\u6536", "\u5168\u91cf\u9a8c\u6536", "\u7aef\u5230\u7aef"))
        {
            return new PrototypeGoalAcceptanceContract(
                ContainsAny(text, "jrpg", "first-loop", "first loop") ? "jrpg-final-first-loop-acceptance" : "rpg-final-full-playable-acceptance",
                ["MoveOnMap", "ResolveAttackTurn", "RewardOptions.Count", "ApplyReward", "Battle reward selected", "VictoryBattleCount", "IsVictory", "IsGameOver"],
                AssetUsageAcceptance: true,
                MapEntryAcceptance: true,
                BattleSceneAcceptance: true,
                RewardFlowAcceptance: true,
                MainSceneHostUiHiddenAcceptance: true,
                FinalAcceptance: true);
        }

        if (ContainsAny(text, "opening context", "player objective", "hero/context/objective", "\u5f00\u573a", "\u73a9\u5bb6\u76ee\u6807"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-opening-context-objective",
                ["Objective", "Start Adventure"],
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "interaction and discovery", "discovery beat", "npc", "dialog", "chest", "inspect", "\u4ea4\u4e92", "\u53d1\u73b0", "\u5bf9\u8bdd", "\u5b9d\u7bb1", "\u8c03\u67e5"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-interaction-discovery",
                ["Objective", "Interact"],
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "\u5408\u540c", "contract", "traceability", "\u9700\u6c42\u8868\u5355", "\u6f02\u79fb"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-contract-alignment",
                ["MoveOnMap", "ResolveAttackTurn", "RewardOptions.Count"],
                AssetUsageAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "\u5956\u52b1\u56de\u8def", "reward loop", "return-to-map", "return to the map", "returns to the map"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step5-reward-loop-return-map",
                ["RewardOptions.Count", "ApplyReward", "Battle reward selected", "Return to the map"],
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "return or continue loop", "next playable state", "continue loop", "\u8fd4\u56de", "\u7ee7\u7eed\u5faa\u73af"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-return-or-continue-loop",
                ["Return to the map", "MoveOnMap"],
                MapEntryAcceptance: true,
                RewardFlowAcceptance: true);
        }

        if (ContainsAny(text, "\u5956\u52b1 3 \u9009 1", "\u4e09\u9009\u4e00", "reward 3", "3-choice", "three reward", "reward choice"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step4-reward-choice-readability",
                ["RewardOptions.Count", "Battle reward selected"],
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "growth", "consequence feedback", "exp", "level", "item gain", "\u6210\u957f", "\u7ecf\u9a8c", "\u5347\u7ea7", "\u9053\u5177", "\u540e\u679c"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-growth-reward-consequence-feedback",
                ["RewardOptions.Count", "ApplyReward", "Battle reward selected"],
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "\u5931\u8d25\u5206\u652f", "failure path", "\u518d\u6b21\u9047\u654c", "\u518d\u6b21\u8fdb\u5165\u6218\u6597", "\u56de\u73af\u7a33\u5b9a", "\u7ed3\u679c\u56de\u73af"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-loop-stability",
                ["MoveOnMap", "ResolveAttackTurn", "ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward", "IsGameOver"],
                MapEntryAcceptance: true,
                BattleSceneAcceptance: true);
        }

        if (ContainsAny(text, "\u80dc\u8d1f\u6761\u4ef6", "game over", "victory condition", "\u5931\u8d25\u6761\u4ef6", "\u76ee\u6807\u63d0\u793a"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step6-win-fail-visibility",
                ["VictoryBattleCount", "IsVictory", "IsGameOver"],
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "\u9047\u654c", "encounter", "encounter trigger", "first encounter", "guaranteed encounter"))
        {
            return new PrototypeGoalAcceptanceContract(
                ContainsAny(text, "jrpg", "conflict entry") ? "jrpg-conflict-entry-trigger" : "rpg-step2-encounter-trigger",
                ["MoveOnMap", "ShouldReachRewardPhase_AfterWinningTheFirstEncounter"],
                MapEntryAcceptance: true);
        }

        if (ContainsAny(text, "\u5730\u56fe\u79fb\u52a8", "map", "visible map", "start adventure", "field navigation", "stable control", "town scene"))
        {
            return new PrototypeGoalAcceptanceContract(
                ContainsAny(text, "jrpg", "field navigation", "stable control", "town scene") ? "jrpg-field-navigation-stable-control" : "rpg-step1-visible-map-movement",
                ["MoveOnMap"],
                MapEntryAcceptance: true);
        }

        if (ContainsAny(text, "\u6218\u6597", "battle", "\u7ed3\u7b97", "settlement", "battlescene", "challenge resolution"))
        {
            return new PrototypeGoalAcceptanceContract(
                ContainsAny(text, "jrpg", "challenge resolution") ? "jrpg-battle-or-challenge-resolution" : "rpg-step3-battlescene-settlement",
                ["ShouldReachRewardPhase_AfterWinningTheFirstEncounter", "ResolveAttackTurn", "BattlesWon", "Victory"],
                BattleSceneAcceptance: true);
        }

        if (ContainsAny(text, "party", "character state", "hp", "stat", "status", "equipment", "\u961f\u4f0d", "\u89d2\u8272\u72b6\u6001", "\u5c5e\u6027", "\u88c5\u5907"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-party-character-state-readability",
                ["HP", "Stats", "Status"],
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "quest", "story", "narrative", "objective completion", "\u5267\u60c5", "\u4efb\u52a1", "\u53d9\u4e8b"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-quest-story-progress",
                ["Objective", "Quest"],
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "\u573a\u666f\u5207\u6362", "scene switching", "main prototype scene", "\u4e3b\u539f\u578b"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step4-main-loop-scene-switching",
                ["MoveOnMap", "ResolveAttackTurn", "RewardOptions.Count", "ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward"],
                MapEntryAcceptance: true,
                BattleSceneAcceptance: true,
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "assets", "\u7d20\u6750", "ui", "\u57fa\u7840\u754c\u9762", "\u57fa\u7840\u7d20\u6750"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-asset-usage-validation",
                ["MoveOnMap", "ResolveAttackTurn", "RewardOptions.Count"],
                AssetUsageAcceptance: true);
        }

        return null;
    }

    private static bool ContainsAny(string text, params string[] values)
    {
        return values.Any(value => text.Contains(value, StringComparison.OrdinalIgnoreCase));
    }
}

internal sealed class SurvivorsLikeGameTypeRouteStrategy : IGameTypeRouteStrategy
{
    public string GameTypeId => "survivorslike";

    public bool RequiresModelBackedIterationPlanning => false;

    public bool RequiresNonEmptyIterationGoals => true;

    public bool UsesSpecializedIterationPlanning => true;

    public bool UsesSpecializedPlanEvaluation => true;

    public PrototypeGoalAcceptanceContract? ResolveAcceptanceContract(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(goal);

        if (!PrototypeRouteSkillPolicy.IsSurvivorsLikeProject(project))
        {
            return null;
        }

        var text = string.Join(" ", goal.Title ?? "", goal.Description ?? "", goal.AcceptanceHint ?? "").ToLowerInvariant();
        if (ContainsAny(text, "run start and survival objective"))
        {
            return Static("survivorslike-run-start-survival-objective", ["RunStart", "SurvivalObjective"]);
        }

        if (ContainsAny(text, "arena movement and camera readability"))
        {
            return Static("survivorslike-arena-movement-camera-readability", ["ArenaMovement", "PlayerMovement", "Camera"]);
        }

        if (ContainsAny(text, "enemy spawn pressure curve"))
        {
            return Static("survivorslike-enemy-spawn-pressure-curve", ["EnemySpawn", "SpawnPressure"]);
        }

        if (ContainsAny(text, "auto-attack", "auto attack", "core weapon loop"))
        {
            return Static("survivorslike-auto-attack-core-weapon-loop", ["AutoAttack", "WeaponCooldown", "Hit"]);
        }

        if (ContainsAny(text, "hit, damage, health", "death feedback"))
        {
            return Static("survivorslike-hit-damage-health-death-feedback", ["Health", "Damage", "Death"]);
        }

        if (ContainsAny(text, "pickup and resource collection"))
        {
            return Static("survivorslike-pickup-resource-collection", ["Pickup", "Experience", "Resource"]);
        }

        if (ContainsAny(text, "level-up choice", "power selection"))
        {
            return Static("survivorslike-level-up-choice-power-selection", ["LevelUp", "PowerChoice", "Upgrade"]);
        }

        if (ContainsAny(text, "build growth", "power fantasy feedback"))
        {
            return Static("survivorslike-build-growth-power-fantasy-feedback", ["Upgrade", "PowerGrowth", "PowerFantasy"]);
        }

        if (ContainsAny(text, "escalation event", "mini-milestone"))
        {
            return Static("survivorslike-escalation-event-mini-milestone", ["Escalation", "Elite", "Milestone"]);
        }

        if (ContainsAny(text, "run end", "summary", "restart loop", "final first-loop acceptance"))
        {
            return Static("survivorslike-run-end-summary-restart-loop", ["RunSummary", "Restart", "SurvivalObjective"]);
        }

        return null;
    }

    private static PrototypeGoalAcceptanceContract Static(string kind, IReadOnlyList<string> markers)
    {
        return new PrototypeGoalAcceptanceContract(kind, markers, StaticAcceptanceOnly: true);
    }

    private static bool ContainsAny(string text, params string[] values)
    {
        return values.Any(value => text.Contains(value, StringComparison.OrdinalIgnoreCase));
    }
}

internal sealed record PrototypeGoalAcceptanceContract(
    string Kind,
    IReadOnlyList<string> RequiredMarkers,
    bool AssetUsageAcceptance = false,
    bool MapEntryAcceptance = false,
    bool BattleSceneAcceptance = false,
    bool RewardFlowAcceptance = false,
    bool MainSceneHostUiHiddenAcceptance = false,
    bool FinalAcceptance = false,
    bool StaticAcceptanceOnly = false);
