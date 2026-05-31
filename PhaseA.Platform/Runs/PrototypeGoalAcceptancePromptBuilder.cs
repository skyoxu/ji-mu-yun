using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

internal static class PrototypeGoalAcceptancePromptBuilder
{
    public static string Build(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(goal);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);
        if (contract is null || !contract.Kind.StartsWith("rpg-", StringComparison.Ordinal))
        {
            return "";
        }

        return goal.GoalIndex switch
        {
            1 => """
                Platform hard acceptance for RPG Step 1:
                - Need: Game.Godot/Prototypes/dq-rpg/MapScene.tscn and Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs.
                - DqRpgPrototype.tscn keeps Start Adventure and CanvasLayer/UI/MapScene; click shows it via ShowMapScene or StartRun/StartAdventure.
                - MapScene has TrackLayer with RpgMapAsset, Grid, Overlay, RpgPlayerAsset, RpgEnemyAsset.
                - MapScene.cs moves player, maps grid positions, and exposes EncounterEntered/EncounterPressed/EncounterTriggered.
                - Missing contract means STATUS: needs_fix.
                """,
            2 => """
                Platform hard acceptance for RPG Step 2:
                - Need: Game.Godot/Prototypes/dq-rpg/BattleScene.tscn and Game.Godot/Prototypes/dq-rpg/Scripts/BattleScene.cs.
                - Keep battle UI and battle-side runtime behavior in the dedicated BattleScene instead of leaving the full battle loop only inside DqRpgPrototype.cs.
                - BattleScene.tscn must expose a recognizable BattleScene node, RpgEnemyAsset, and AttackButton.
                - BattleScene.cs must expose battle settlement wiring through BattleFinished and ResolveBattle/ResolveAttackTurn.
                - The battle loop must show readable enemy presentation, attack feedback, and victory or defeat settlement without advancing into reward selection.
                - Missing contract means STATUS: needs_fix.
                """,
            3 => """
                Platform hard acceptance for RPG Step 3:
                - ShowRewardScene(rewards) must show exactly three understandable reward choices after a battle victory when rewards.Count > 0.
                - Choosing a reward must apply one visible growth option: +5 HP, +2 ATK, or +1 DEF.
                - The +5 HP reward must make the post-reward state visibly equal to StartingPlayerHp + 5 for the first battle reward proof, not merely current damaged HP + 5.
                - Choosing any reward must close the reward UI, return to MapScene, keep the player visible and movable, and record Battle reward selected / Return to the map evidence.
                - MapScene.cs must expose ShowRewardReturnStatus or ApplyState so the return-to-map state is visible.
                - Keep markers: RewardOptions.Count, ApplyReward, Battle reward selected, Return to the map, ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward.
                - If reward values, reward UI, or return-to-map proof are missing, output STATUS: needs_fix.
                """,
            5 => """
                Platform hard acceptance for RPG Step 5:
                - This step is win/fail visibility and readability, not the reward implementation step.
                - 15 battle wins must be visibly communicated as the game victory condition.
                - Any battle loss must visibly communicate game failure and stop the run.
                - Encounter rules and battle count progress must be readable at a glance in runtime UI.
                - Keep victory/failure markers: VictoryBattleCount, IsVictory, IsGameOver.
                - If win/fail rules are only in code or docs and not visible to the player, output STATUS: needs_fix.
                """,
            6 => """
                Platform hard acceptance for RPG Final Step:
                - Full RPG prototype acceptance must pass: MapScene, BattleScene, reward return-to-map loop, main-menu prototype entry, visible map after Start Adventure, Godot smoke, and package readiness.
                - Runtime visuals must use real file-backed Texture2D assets for the exact nodes RpgMapAsset, RpgPlayerAsset, and RpgEnemyAsset.
                - Copy/adapt assets into Game.Godot/Prototypes/dq-rpg/Assets/Map, Assets/Player, and Assets/Enemy, then reference them through res:// ext_resource Texture2D paths.
                - GradientTexture2D/sub_resource placeholders do not satisfy final asset acceptance, even when node names are correct.
                - Delete Game.Godot/.gdignore if present; it blocks Godot from importing res://Game.Godot/** runtime assets and fails final RPG asset acceptance.
                - Main.tscn root-level VBox, Overlays, and ScreenRoot must exist and default to visible = false.
                - Do not delete ScreenRoot or navigation wiring; only keep default visibility off and let navigation show it at runtime when needed.
                - If file-backed RPG assets or Main.tscn host UI hiding are missing, output STATUS: needs_fix.
                """,
            _ => ""
        };
    }
}
