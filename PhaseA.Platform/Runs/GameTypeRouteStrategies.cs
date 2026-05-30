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

        return goal.GoalIndex switch
        {
            1 => new PrototypeGoalAcceptanceContract(
                "rpg-step1-navigation-encounter-entry",
                ["MoveOnMap", "ShouldReachRewardPhase_AfterWinningTheFirstEncounter"],
                MapEntryAcceptance: true),
            2 => new PrototypeGoalAcceptanceContract(
                "rpg-step2-battlescene-settlement",
                ["ShouldReachRewardPhase_AfterWinningTheFirstEncounter", "ResolveAttackTurn", "BattlesWon", "Victory"],
                BattleSceneAcceptance: true),
            3 => new PrototypeGoalAcceptanceContract(
                "rpg-step3-reward-loop-return-map",
                ["RewardOptions.Count", "ApplyReward", "Battle reward selected", "Return to the map"],
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true),
            4 => new PrototypeGoalAcceptanceContract(
                "rpg-step4-main-loop-scene-switching",
                ["MoveOnMap", "ResolveAttackTurn", "RewardOptions.Count", "ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward"],
                MapEntryAcceptance: true,
                BattleSceneAcceptance: true,
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true),
            5 => new PrototypeGoalAcceptanceContract(
                "rpg-step5-win-fail-visibility",
                ["VictoryBattleCount", "IsVictory", "IsGameOver"],
                StaticAcceptanceOnly: true),
            6 => new PrototypeGoalAcceptanceContract(
                "rpg-final-full-playable-acceptance",
                ["MoveOnMap", "ResolveAttackTurn", "RewardOptions.Count", "ApplyReward", "Battle reward selected", "VictoryBattleCount", "IsVictory", "IsGameOver"],
                AssetUsageAcceptance: true,
                MapEntryAcceptance: true,
                BattleSceneAcceptance: true,
                RewardFlowAcceptance: true,
                MainSceneHostUiHiddenAcceptance: true,
                FinalAcceptance: true),
            _ => null
        };
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

        if (ContainsAny(title, "RPG Step 1: Start Adventure to visible MapScene", "rpg-step1-navigation-encounter-entry"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step1-navigation-encounter-entry",
                ["MoveOnMap", "ShouldReachRewardPhase_AfterWinningTheFirstEncounter"],
                MapEntryAcceptance: true);
        }

        if (ContainsAny(title, "RPG Step 2: BattleScene loop validation", "rpg-step2-battlescene-settlement"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step2-battlescene-settlement",
                ["ShouldReachRewardPhase_AfterWinningTheFirstEncounter", "ResolveAttackTurn", "BattlesWon", "Victory"],
                BattleSceneAcceptance: true);
        }

        if (ContainsAny(title, "RPG Step 3: reward 3-choice and return-to-map validation", "rpg-step3-reward-loop-return-map"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step3-reward-loop-return-map",
                ["RewardOptions.Count", "ApplyReward", "Battle reward selected", "Return to the map"],
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(title, "RPG Step 4: main loop scene switching validation", "rpg-step4-main-loop-scene-switching"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step4-main-loop-scene-switching",
                ["MoveOnMap", "ResolveAttackTurn", "RewardOptions.Count", "ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward"],
                MapEntryAcceptance: true,
                BattleSceneAcceptance: true,
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(title, "RPG Step 5: win/fail visibility and readability validation", "rpg-step5-win-fail-visibility"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step5-win-fail-visibility",
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
                "rpg-final-full-playable-acceptance",
                ["MoveOnMap", "ResolveAttackTurn", "RewardOptions.Count", "ApplyReward", "Battle reward selected", "VictoryBattleCount", "IsVictory", "IsGameOver"],
                AssetUsageAcceptance: true,
                MapEntryAcceptance: true,
                BattleSceneAcceptance: true,
                RewardFlowAcceptance: true,
                MainSceneHostUiHiddenAcceptance: true,
                FinalAcceptance: true);
        }

        if (ContainsAny(text, "\u5408\u540c", "contract", "traceability", "\u9700\u6c42\u8868\u5355", "\u6f02\u79fb"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-contract-alignment",
                ["MoveOnMap", "ResolveAttackTurn", "RewardOptions.Count"],
                AssetUsageAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "\u5956\u52b1 3 \u9009 1", "\u4e09\u9009\u4e00", "reward 3", "3-choice", "three reward", "\u5956\u52b1\u56de\u8def", "reward loop", "return-to-map"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step3-reward-loop-return-map",
                ["RewardOptions.Count", "ApplyReward", "Battle reward selected", "Return to the map"],
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
                "rpg-win-fail-conditions",
                ["VictoryBattleCount", "IsVictory", "IsGameOver"],
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "\u5730\u56fe\u79fb\u52a8", "\u9047\u654c", "map", "encounter", "visible map", "start adventure"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step1-navigation-encounter-entry",
                ["MoveOnMap", "ShouldReachRewardPhase_AfterWinningTheFirstEncounter"],
                MapEntryAcceptance: true);
        }

        if (ContainsAny(text, "\u6218\u6597", "battle", "\u7ed3\u7b97", "settlement", "battlescene"))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step2-battlescene-settlement",
                ["ShouldReachRewardPhase_AfterWinningTheFirstEncounter", "ResolveAttackTurn", "BattlesWon", "Victory"],
                BattleSceneAcceptance: true);
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
