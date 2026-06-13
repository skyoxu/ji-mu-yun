using System.Text.Json;
using System.Text.RegularExpressions;
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

        var routeTitle = ResolveRpgRouteGoalTitle(project, goal);
        if (routeTitle is not null)
        {
            return routeTitle;
        }

        var semantic = ResolveRpgGoalSemantic(project, goal);
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

    private static readonly HashSet<string> KnownJrpgCapabilityIds = new(StringComparer.OrdinalIgnoreCase)
    {
        "opening_context",
        "field_navigation",
        "interaction_discovery",
        "conflict_entry",
        "battle_or_challenge_resolution",
        "party_or_character_state",
        "growth_feedback",
        "return_or_continue_loop",
        "quest_or_story_progress",
        "final_first_loop_acceptance"
    };

    private static PrototypeGoalAcceptanceContract? ResolveRpgRouteGoalTitle(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
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
            var text = string.Join(" ", goal.Title, goal.Description, goal.AcceptanceHint);
            if (ContainsAny(text, "map entry smoke", "navigation smoke", "visible MapScene", "map entry", "field movement", "stable movement"))
            {
                return new PrototypeGoalAcceptanceContract(
                    "jrpg-field-navigation-stable-control",
                    ["MoveOnMap"],
                    MapEntryAcceptance: true);
            }

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
            var context = BuildJrpgCapabilityContext(project, goal);
            if (!RequiresBattleSceneForGoalContext(context.Text, goal))
            {
                return new PrototypeGoalAcceptanceContract(
                    "jrpg-conflict-entry-trigger",
                    ["MoveOnMap"],
                    MapEntryAcceptance: true,
                    StaticAcceptanceOnly: true);
            }

            return new PrototypeGoalAcceptanceContract(
                "jrpg-conflict-entry-trigger",
                ["MoveOnMap", "ShouldReachRewardPhase_AfterWinningTheFirstEncounter"],
                MapEntryAcceptance: true);
        }

        if (ContainsAny(title, "JRPG First Loop: battle or challenge resolution"))
        {
            var context = BuildJrpgCapabilityContext(project, goal);
            if (!RequiresBattleScene(context.Text))
            {
                return new PrototypeGoalAcceptanceContract(
                    "jrpg-battle-or-challenge-resolution",
                    [],
                    StaticAcceptanceOnly: true);
            }

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
            var context = BuildJrpgCapabilityContext(project, goal);
            if (!RequiresRewardFlow(context.Text))
            {
                return new PrototypeGoalAcceptanceContract(
                    "jrpg-growth-reward-consequence-feedback",
                    [],
                    StaticAcceptanceOnly: true);
            }

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
                ["MoveOnMap"],
                MapEntryAcceptance: true);
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
            var context = BuildJrpgCapabilityContext(project, goal);
            return BuildJrpgFinalAcceptanceContract(context.Text, context.SelectedCapabilities);
        }

        if (ContainsAny(title, "RPG Step 2: encounter trigger and guaranteed encounter validation", "rpg-step2-encounter-trigger"))
        {
            var context = BuildJrpgCapabilityContext(project, goal);
            if (!RequiresBattleSceneForGoalContext(context.Text, goal))
            {
                return new PrototypeGoalAcceptanceContract(
                    "rpg-step2-encounter-trigger",
                    ["MoveOnMap"],
                    MapEntryAcceptance: true,
                    StaticAcceptanceOnly: true);
            }

            return new PrototypeGoalAcceptanceContract(
                "rpg-step2-encounter-trigger",
                ["MoveOnMap", "ShouldReachRewardPhase_AfterWinningTheFirstEncounter"],
                MapEntryAcceptance: true);
        }

        if (ContainsAny(title, "RPG Step 3: BattleScene visualization and settlement validation", "rpg-step3-battlescene-settlement"))
        {
            var context = BuildJrpgCapabilityContext(project, goal);
            if (!RequiresBattleSceneForGoalContext(context.Text, goal))
            {
                return new PrototypeGoalAcceptanceContract(
                    "rpg-step3-battlescene-settlement",
                    [],
                    StaticAcceptanceOnly: true);
            }

            return new PrototypeGoalAcceptanceContract(
                "rpg-step3-battlescene-settlement",
                ["ShouldReachRewardPhase_AfterWinningTheFirstEncounter", "ResolveAttackTurn", "BattlesWon", "Victory"],
                BattleSceneAcceptance: true);
        }

        if (ContainsAny(title, "RPG Step 4: reward 3-choice understandability validation", "rpg-step4-reward-choice-readability"))
        {
            var context = BuildJrpgCapabilityContext(project, goal);
            if (!RequiresRewardFlowForGoalContext(context.Text, goal))
            {
                return new PrototypeGoalAcceptanceContract(
                    "rpg-step4-reward-choice-readability",
                    [],
                    StaticAcceptanceOnly: true);
            }

            return new PrototypeGoalAcceptanceContract(
                "rpg-step4-reward-choice-readability",
                ["RewardOptions.Count", "Battle reward selected"],
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(title, "RPG Step 5: reward application and return-to-map validation", "rpg-step5-reward-loop-return-map"))
        {
            var context = BuildJrpgCapabilityContext(project, goal);
            if (!RequiresRewardFlowForGoalContext(context.Text, goal))
            {
                return new PrototypeGoalAcceptanceContract(
                    "rpg-step5-reward-loop-return-map",
                    ["MoveOnMap"],
                    MapEntryAcceptance: true,
                    StaticAcceptanceOnly: true);
            }

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

    private static PrototypeGoalAcceptanceContract? ResolveRpgGoalSemantic(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        var combined = string.Join(" ", goal.Title ?? "", goal.Description ?? "", goal.AcceptanceHint ?? "");
        if (string.IsNullOrWhiteSpace(combined))
        {
            return null;
        }

        var text = combined.ToLowerInvariant();
        var requestsFinalGdUnitValidation =
            ContainsAny(text, "project-specific gdunit", "rpg gdunit", "gdunit") &&
            ContainsAny(text, "final", "prototype acceptance", "front-end prototype validation", "validation route", "\u6700\u7ec8\u9a8c\u6536", "\u5168\u91cf\u9a8c\u6536");
        if (ContainsAny(text, "full playable prototype acceptance", "final acceptance", "final prototype acceptance", "prototype acceptance", "\u6700\u7ec8\u9a8c\u6536", "\u5168\u91cf\u9a8c\u6536", "\u7aef\u5230\u7aef") ||
            requestsFinalGdUnitValidation)
        {
            if (ContainsAny(text, "jrpg", "first-loop", "first loop"))
            {
                var context = BuildJrpgCapabilityContext(project, goal);
                return BuildJrpgFinalAcceptanceContract(context.Text, context.SelectedCapabilities);
            }

            var contextForGenericFinal = BuildJrpgCapabilityContext(project, goal);
            return BuildRpgFinalAcceptanceContract(contextForGenericFinal.Text, contextForGenericFinal.SelectedCapabilities);
        }

        if (ContainsAny(text, "opening context", "player objective", "hero/context/objective", "\u5f00\u573a", "\u73a9\u5bb6\u76ee\u6807"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-opening-context-objective",
                ["Objective", "Start Adventure"],
                StaticAcceptanceOnly: true);
        }

        if (!ContainsAssetOrUiValidation(text) &&
            ContainsAny(text, "interaction and discovery", "discovery beat", "npc", "dialog", "chest", "inspect", "\u4ea4\u4e92", "\u53d1\u73b0", "\u5bf9\u8bdd", "\u5b9d\u7bb1", "\u8c03\u67e5"))
        {
            return new PrototypeGoalAcceptanceContract(
                "jrpg-interaction-discovery",
                ["Objective", "Interact"],
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "\u5408\u540c", "contract", "traceability", "\u9700\u6c42\u8868\u5355", "\u6f02\u79fb"))
        {
            var context = BuildJrpgCapabilityContext(project, goal);
            var requiresBattle = RequiresBattleScene(context.Text);
            var requiresReward = RequiresRewardFlow(context.Text);
            return new PrototypeGoalAcceptanceContract(
                "rpg-contract-alignment",
                BuildRpgContractAlignmentRequiredMarkers(requiresBattle, requiresReward),
                AssetUsageAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "\u5956\u52b1\u56de\u8def", "reward loop", "return-to-map", "return to the map", "returns to the map") &&
            RequiresRewardFlow(text))
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
                ["MoveOnMap"],
                MapEntryAcceptance: true);
        }

        if (ContainsAny(text, "\u5956\u52b1 3 \u9009 1", "\u4e09\u9009\u4e00", "reward 3", "3-choice", "three reward", "reward choice") &&
            RequiresRewardFlow(text))
        {
            return new PrototypeGoalAcceptanceContract(
                "rpg-step4-reward-choice-readability",
                ["RewardOptions.Count", "Battle reward selected"],
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (!ContainsAssetOrUiValidation(text) &&
            ContainsAny(text, "growth", "consequence feedback", "experience", " xp ", " exp ", "level", "item gain", "\u6210\u957f", "\u7ecf\u9a8c", "\u5347\u7ea7", "\u9053\u5177", "\u540e\u679c"))
        {
            if (!RequiresRewardFlow(text))
            {
                return new PrototypeGoalAcceptanceContract(
                    "jrpg-growth-reward-consequence-feedback",
                    [],
                    StaticAcceptanceOnly: true);
            }

            return new PrototypeGoalAcceptanceContract(
                "jrpg-growth-reward-consequence-feedback",
                ["RewardOptions.Count", "ApplyReward", "Battle reward selected"],
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAny(text, "\u5931\u8d25\u5206\u652f", "failure path", "\u518d\u6b21\u9047\u654c", "\u518d\u6b21\u8fdb\u5165\u6218\u6597", "\u56de\u73af\u7a33\u5b9a", "\u7ed3\u679c\u56de\u73af"))
        {
            if (!RequiresBattleScene(text))
            {
                return new PrototypeGoalAcceptanceContract(
                    "jrpg-loop-stability",
                    ["MoveOnMap"],
                    MapEntryAcceptance: true);
            }

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
            if (!RequiresBattleSceneForGoalContext(text, goal))
            {
                return new PrototypeGoalAcceptanceContract(
                    ContainsAny(text, "jrpg", "conflict entry") ? "jrpg-conflict-entry-trigger" : "rpg-step2-encounter-trigger",
                    ["MoveOnMap"],
                    MapEntryAcceptance: true,
                    StaticAcceptanceOnly: true);
            }

            return new PrototypeGoalAcceptanceContract(
                ContainsAny(text, "jrpg", "conflict entry") ? "jrpg-conflict-entry-trigger" : "rpg-step2-encounter-trigger",
                ["MoveOnMap", "ShouldReachRewardPhase_AfterWinningTheFirstEncounter"],
                MapEntryAcceptance: true);
        }

        if (!ContainsAny(text, "\u573a\u666f\u5207\u6362", "scene switching", "main prototype scene", "\u4e3b\u539f\u578b") &&
            !ContainsAssetOrUiValidation(text) &&
            ContainsAny(text, "\u5730\u56fe\u79fb\u52a8", "map", "visible map", "start adventure", "field navigation", "stable control", "town scene"))
        {
            return new PrototypeGoalAcceptanceContract(
                ContainsAny(text, "jrpg", "field navigation", "stable control", "town scene") ? "jrpg-field-navigation-stable-control" : "rpg-step1-visible-map-movement",
                ["MoveOnMap"],
                MapEntryAcceptance: true);
        }

        if (ContainsAny(text, "\u6218\u6597", "battle", "\u7ed3\u7b97", "settlement", "battlescene", "challenge resolution"))
        {
            if (!RequiresBattleSceneForGoalContext(text, goal))
            {
                return new PrototypeGoalAcceptanceContract(
                    ContainsAny(text, "jrpg", "challenge resolution") ? "jrpg-battle-or-challenge-resolution" : "rpg-step3-battlescene-settlement",
                    [],
                    StaticAcceptanceOnly: true);
            }

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
            var context = BuildJrpgCapabilityContext(project, goal);
            var requiresBattle = RequiresBattleScene(context.Text);
            var requiresReward = RequiresRewardFlow(context.Text);
            return new PrototypeGoalAcceptanceContract(
                "rpg-step4-main-loop-scene-switching",
                BuildRpgSceneSwitchingRequiredMarkers(requiresBattle, requiresReward),
                MapEntryAcceptance: true,
                BattleSceneAcceptance: requiresBattle,
                RewardFlowAcceptance: requiresReward,
                StaticAcceptanceOnly: true);
        }

        if (ContainsAssetOrUiValidation(text))
        {
            var context = BuildJrpgCapabilityContext(project, goal);
            var requiresBattle = RequiresBattleScene(context.Text);
            var requiresReward = RequiresRewardFlow(context.Text);
            return new PrototypeGoalAcceptanceContract(
                "rpg-asset-usage-validation",
                BuildRpgContractAlignmentRequiredMarkers(requiresBattle, requiresReward),
                AssetUsageAcceptance: true,
                BattleSceneAcceptance: requiresBattle,
                RewardFlowAcceptance: requiresReward,
                StaticAcceptanceOnly: true);
        }

        return null;
    }

    private static string[] BuildJrpgFinalRequiredMarkers(bool requiresBattle, bool requiresReward)
    {
        var markers = new List<string> { "Objective", "Start Adventure", "MoveOnMap" };
        if (requiresBattle)
        {
            markers.AddRange(["ResolveAttackTurn", "VictoryBattleCount", "IsVictory", "IsGameOver"]);
        }

        if (requiresReward)
        {
            markers.AddRange(["RewardOptions.Count", "ApplyReward", "Battle reward selected"]);
        }

        return markers.ToArray();
    }

    private static bool ContainsAssetOrUiValidation(string text)
    {
        return ContainsAny(text, "assets", "asset validation", "user interface", "hud", "\u7d20\u6750", "\u754c\u9762", "\u57fa\u7840\u754c\u9762", "\u57fa\u7840\u7d20\u6750") ||
               Regex.IsMatch(text, @"(?<![a-z0-9])ui(?![a-z0-9])", RegexOptions.IgnoreCase);
    }

    private static string[] BuildRpgContractAlignmentRequiredMarkers(bool requiresBattle, bool requiresReward)
    {
        var markers = new List<string> { "MoveOnMap" };
        if (requiresBattle)
        {
            markers.Add("ResolveAttackTurn");
        }

        if (requiresReward)
        {
            markers.Add("RewardOptions.Count");
        }

        return markers.ToArray();
    }

    private static string[] BuildRpgSceneSwitchingRequiredMarkers(bool requiresBattle, bool requiresReward)
    {
        var markers = new List<string> { "MoveOnMap" };
        if (requiresBattle)
        {
            markers.Add("ResolveAttackTurn");
        }

        if (requiresReward)
        {
            markers.Add("RewardOptions.Count");
            markers.Add("ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward");
        }

        return markers.ToArray();
    }

    private static PrototypeGoalAcceptanceContract BuildJrpgFinalAcceptanceContract(string text)
    {
        return BuildJrpgFinalAcceptanceContract(text, null);
    }

    private static PrototypeGoalAcceptanceContract BuildJrpgFinalAcceptanceContract(string text, IReadOnlySet<string>? selectedCapabilities)
    {
        var (requiresBattle, requiresReward) = ResolveFinalRequirements(text, selectedCapabilities);
        return BuildJrpgFinalAcceptanceContractFromRequirements(requiresBattle, requiresReward);
    }

    private static bool RequiresRewardFlow(string text)
    {
        return JrpgRouteSemantics.RequiresRewardFlow(text);
    }

    private static bool RequiresBattleScene(string text)
    {
        return JrpgRouteSemantics.RequiresBattleScene(text);
    }

    private static bool RequiresBattleSceneForGoalContext(string fullText, ProjectIterationGoalSnapshot goal)
    {
        var bodyText = string.Join(" ", goal.Description ?? "", goal.AcceptanceHint ?? "");
        if (JrpgRouteSemantics.ContainsBattleNegation(bodyText) &&
            !JrpgRouteSemantics.RequiresBattleScene(bodyText))
        {
            return false;
        }

        return RequiresBattleScene(fullText);
    }

    private static bool RequiresRewardFlowForGoalContext(string fullText, ProjectIterationGoalSnapshot goal)
    {
        var bodyText = string.Join(" ", goal.Description ?? "", goal.AcceptanceHint ?? "");
        if (JrpgRouteSemantics.ContainsRewardNegation(bodyText) &&
            !JrpgRouteSemantics.RequiresRewardFlow(bodyText))
        {
            return false;
        }

        return RequiresRewardFlow(fullText);
    }

    private static PrototypeGoalAcceptanceContract BuildJrpgFinalAcceptanceContractFromRequirements(bool requiresBattle, bool requiresReward)
    {
        return new PrototypeGoalAcceptanceContract(
            "jrpg-final-first-loop-acceptance",
            BuildJrpgFinalRequiredMarkers(requiresBattle, requiresReward),
            AssetUsageAcceptance: true,
            MapEntryAcceptance: true,
            BattleSceneAcceptance: requiresBattle,
            RewardFlowAcceptance: requiresReward,
            MainSceneHostUiHiddenAcceptance: true,
            FinalAcceptance: true);
    }

    private static PrototypeGoalAcceptanceContract BuildRpgFinalAcceptanceContract(string text, IReadOnlySet<string>? selectedCapabilities)
    {
        var (requiresBattle, requiresReward) = ResolveFinalRequirements(text, selectedCapabilities);
        return new PrototypeGoalAcceptanceContract(
            "rpg-final-full-playable-acceptance",
            BuildJrpgFinalRequiredMarkers(requiresBattle, requiresReward),
            AssetUsageAcceptance: true,
            MapEntryAcceptance: true,
            BattleSceneAcceptance: requiresBattle,
            RewardFlowAcceptance: requiresReward,
            MainSceneHostUiHiddenAcceptance: true,
            FinalAcceptance: true);
    }

    private static (bool RequiresBattle, bool RequiresReward) ResolveFinalRequirements(string text, IReadOnlySet<string>? selectedCapabilities)
    {
        if (selectedCapabilities is not null && selectedCapabilities.Count > 0)
        {
            var capabilityRequiresBattle =
                selectedCapabilities.Contains("conflict_entry") ||
                selectedCapabilities.Contains("battle_or_challenge_resolution");
            var capabilityRequiresReward =
                selectedCapabilities.Contains("growth_feedback");
            return (capabilityRequiresBattle, capabilityRequiresReward);
        }

        return (RequiresBattleScene(text), RequiresRewardFlow(text));
    }

    private static JrpgCapabilityContext BuildJrpgCapabilityContext(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        var parts = new List<string>
        {
            project.GameTypeSource ?? "",
            goal.Title ?? "",
            goal.Description ?? "",
            goal.AcceptanceHint ?? ""
        };
        var selectedCapabilities = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        AddContractFieldsIfReadable(parts, Path.Combine(project.MetaPath, "routes", "prototype-contract", "latest.json"));
        AddContractFieldsIfReadable(parts, Path.Combine(project.RepoPath, "meta", "routes", "prototype-contract", "latest.json"));
        AddIterationPlanCapabilityFieldsIfReadable(parts, selectedCapabilities, Path.Combine(project.MetaPath, "routes", "iteration-plan", "latest.json"), goal.SessionId);
        AddIterationPlanCapabilityFieldsIfReadable(parts, selectedCapabilities, Path.Combine(project.RepoPath, "meta", "routes", "iteration-plan", "latest.json"), goal.SessionId);
        return new JrpgCapabilityContext(
            string.Join(" ", parts.Where(part => !string.IsNullOrWhiteSpace(part))),
            selectedCapabilities);
    }

    private static void AddIterationPlanCapabilityFieldsIfReadable(List<string> parts, HashSet<string> selectedCapabilities, string path, string? expectedSessionId)
    {
        try
        {
            if (!File.Exists(path))
            {
                return;
            }

            using var document = JsonDocument.Parse(File.ReadAllText(path));
            var root = document.RootElement;
            if (!IsCurrentIterationPlanState(root, expectedSessionId))
            {
                return;
            }

            AddKnownJsonString(parts, root, "source_kind");
            AddKnownJsonString(parts, root, "prompt_source_kind");
            AddKnownJsonString(parts, root, "source_message");
            AddKnownJsonString(parts, root, "sourceMessage");
            AddKnownJsonString(parts, root, "regeneration_guidance");
            AddKnownJsonString(parts, root, "regenerationGuidance");
            AddSelectedCapabilities(selectedCapabilities, root);
        }
        catch (JsonException)
        {
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    private static bool IsCurrentIterationPlanState(JsonElement root, string? expectedSessionId)
    {
        if (string.IsNullOrWhiteSpace(expectedSessionId) ||
            !root.TryGetProperty("session_id", out var sessionElement))
        {
            return false;
        }

        return sessionElement.ValueKind == JsonValueKind.String &&
               string.Equals(sessionElement.GetString(), expectedSessionId, StringComparison.Ordinal);
    }

    private static void AddContractFieldsIfReadable(List<string> parts, string path)
    {
        try
        {
            if (!File.Exists(path))
            {
                return;
            }

            var intentText = JrpgRouteSemantics.ExtractPrototypeContractIntentText(File.ReadAllText(path));
            if (!string.IsNullOrWhiteSpace(intentText))
            {
                parts.Add(intentText);
            }
        }
        catch (JsonException)
        {
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    private static void AddKnownJsonString(List<string> parts, JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out var property) || property.ValueKind != JsonValueKind.String)
        {
            return;
        }

        parts.Add(property.GetString() ?? "");
    }

    private static void AddSelectedCapabilities(HashSet<string> selectedCapabilities, JsonElement root)
    {
        if (!root.TryGetProperty("selected_capabilities", out var capabilities) ||
            capabilities.ValueKind != JsonValueKind.Array)
        {
            return;
        }

        foreach (var capability in capabilities.EnumerateArray())
        {
            if (capability.ValueKind != JsonValueKind.String)
            {
                continue;
            }

            var id = capability.GetString();
            if (!string.IsNullOrWhiteSpace(id) && KnownJrpgCapabilityIds.Contains(id.Trim()))
            {
                selectedCapabilities.Add(id.Trim());
            }
        }
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

internal sealed record JrpgCapabilityContext(string Text, IReadOnlySet<string> SelectedCapabilities);
