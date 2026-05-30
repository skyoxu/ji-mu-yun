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
            5 => """
                Platform hard acceptance for RPG Step 5:
                - ShowRewardScene(rewards) must show reward choices when rewards.Count > 0.
                - Choosing a reward applies one of +5 HP, +2 ATK, or +1 DEF, visibly changes player state, closes reward UI, returns to map, and preserves movement.
                - MapScene.cs must expose ShowRewardReturnStatus.
                - Keep markers: RewardOptions.Count, ApplyReward, Battle reward selected, Return to the map.
                - If the structural contract is missing, output STATUS: needs_fix.
                """,
            6 => """
                Platform hard acceptance for RPG Final Step:
                - Full RPG prototype acceptance must pass: MapScene, BattleScene, reward return-to-map loop, main-menu prototype entry, visible map after Start Adventure, Godot smoke, and package readiness.
                - Main.tscn root-level VBox, Overlays, and ScreenRoot must exist and default to visible = false.
                - Do not delete ScreenRoot or navigation wiring; only keep default visibility off and let navigation show it at runtime when needed.
                - If Main.tscn host UI is still visible by default, output STATUS: needs_fix.
                """,
            _ => ""
        };
    }
}
