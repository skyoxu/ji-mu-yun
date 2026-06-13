using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

internal static class PrototypeGoalAcceptancePromptBuilder
{
    public static string Build(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(goal);

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);
        if (contract is null ||
            (!contract.Kind.StartsWith("rpg-", StringComparison.Ordinal) &&
             !contract.Kind.StartsWith("jrpg-", StringComparison.Ordinal) &&
             !contract.Kind.StartsWith("survivorslike-", StringComparison.Ordinal)))
        {
            return "";
        }

        var byKind = contract.Kind switch
        {
            "jrpg-opening-context-objective" => """
                Platform hard acceptance for JRPG opening context:
                - The prototype entry must communicate who the player is, where they are, and the immediate objective.
                - The objective must be visible in runtime UI, dialog, or scene text, not only in code or docs.
                - Do not advance this step into movement, battle, reward, or final acceptance work.
                - Missing opening objective proof means STATUS: needs_fix.
                """,
            "jrpg-field-navigation-stable-control" => """
                Platform hard acceptance for JRPG field navigation:
                - Need a visible playable field, town, or map scene after Start Adventure or the project entry.
                - RPG route required pair: Game.Godot/Prototypes/dq-rpg/MapScene.tscn + Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs.
                - MapScene.tscn needs MapScene, TrackLayer, RpgMapAsset, Grid, Overlay, and RpgPlayerAsset nodes. Add RpgEnemyAsset only when the selected route includes encounter, conflict, or battle.
                - MapScene.cs needs grid mapping, player visibility restore, movement (MovePlayer/MoveOnMap/TryHandleMapKey).
                - The player marker or character must be visible and controllable with stable movement.
                - Runtime visuals must show map/field and player asset usage.
                - Do not advance this step into encounter, battle, reward, or final acceptance work.
                - Missing field navigation contract means STATUS: needs_fix.
                """,
            "jrpg-interaction-discovery" => """
                Platform hard acceptance for JRPG interaction and discovery:
                - The player must be able to discover or interact with at least one meaningful object, NPC, dialog, clue, chest, or inspectable target.
                - The interaction result must be visible and understandable in runtime UI or scene feedback.
                - Do not hide conflict, battle, reward, or final acceptance requirements inside this step.
                - Missing interaction/discovery proof means STATUS: needs_fix.
                """,
            "jrpg-conflict-entry-trigger" => """
                Platform hard acceptance for JRPG conflict entry:
                - Map, field, town, or interaction progress must expose a clear first conflict, encounter, challenge, or obstacle entry.
                - The trigger must be visible and verifiable from player action or traversal.
                - Do not advance this step into battle/challenge settlement or reward selection.
                - Missing conflict entry proof means STATUS: needs_fix.
                """,
            "jrpg-battle-or-challenge-resolution" => """
                Platform hard acceptance for JRPG battle or challenge resolution:
                - A readable battle, challenge, or obstacle resolution loop must show player state, opponent/obstacle state, action feedback, and success/failure settlement.
                - If the project uses BattleScene, keep battle UI and runtime behavior in the dedicated battle scene instead of only inside the main prototype controller.
                - Do not advance this step into reward selection or return-loop proof unless the project explicitly has no separate reward/return requirement.
                - Missing resolution proof means STATUS: needs_fix.
                """,
            "jrpg-party-character-state-readability" => """
                Platform hard acceptance for JRPG party or character state:
                - Player, party, HP, stats, status, equipment, or equivalent character state must be readable at runtime.
                - State must update or remain visibly consistent after the relevant loop event.
                - Do not treat code-only state as sufficient player-facing proof.
                - Missing state readability proof means STATUS: needs_fix.
                """,
            "jrpg-growth-reward-consequence-feedback" => """
                Platform hard acceptance for JRPG growth, reward, or consequence feedback:
                - The loop must show an understandable reward, growth, item, stat change, experience, skill unlock, or story consequence.
                - If the route uses the RPG reward contract, victory must expose exactly three understandable reward choices.
                - Choosing a reward must apply a visible state change when a reward choice is part of the selected capability.
                - Missing reward/growth/consequence proof means STATUS: needs_fix.
                """,
            "jrpg-return-or-continue-loop" => """
                Platform hard acceptance for JRPG return or continue loop:
                - After resolution or reward, the prototype must return to the active playable field/map/town or continue to a clear next playable state.
                - The player must remain visible and controllable when the selected loop expects continued play.
                - Runtime feedback must make the transition understandable.
                - Missing return/continue proof means STATUS: needs_fix.
                """,
            "jrpg-quest-story-progress" => """
                Platform hard acceptance for JRPG quest or story progress:
                - The prototype must show visible quest, story, objective, or narrative progress caused by player action.
                - The player must understand what changed and what the next objective is.
                - Do not force BattleScene or reward work unless the project semantics require it.
                - Missing quest/story progress proof means STATUS: needs_fix.
                """,
            "jrpg-final-first-loop-acceptance" => """
                Platform hard acceptance for JRPG final first-loop acceptance:
                - The selected first-loop capabilities must work together end-to-end from entry through the final playable state.
                - Project-specific contract fields, runtime proof, Godot smoke, asset usage, and package readiness must pass.
                - If the route uses RPG map, battle, reward, or return-loop contracts, those selected capabilities must remain valid.
                - Main.tscn root-level VBox, Overlays, and ScreenRoot must exist and default to visible = false when final host UI hiding is required.
                - Missing final first-loop proof means STATUS: needs_fix.
                """,
            _ => ""
        };
        if (!string.IsNullOrWhiteSpace(byKind))
        {
            return byKind;
        }

        var survivorsLike = contract.Kind switch
        {
            "survivorslike-run-start-survival-objective" => """
                Platform hard acceptance for Vampire Survivors-like run start:
                - The prototype must expose a clear run entry and survival objective before adding weapons, pickups, or escalation.
                - Runtime UI must communicate the short-term objective, timer, wave, or survival goal.
                - Missing run start or survival objective proof means STATUS: needs_fix.
                """,
            "survivorslike-arena-movement-camera-readability" => """
                Platform hard acceptance for Vampire Survivors-like arena movement:
                - The player must move continuously in an arena or equivalent survival space.
                - The player, camera/viewport, arena background, and threat directions must remain readable.
                - Do not advance this step into weapon, pickup, level-up, or final summary work.
                - Missing arena movement or readability proof means STATUS: needs_fix.
                """,
            "survivorslike-enemy-spawn-pressure-curve" => """
                Platform hard acceptance for Vampire Survivors-like spawn pressure:
                - Enemies must spawn repeatedly through time, wave, distance, or pressure rules.
                - The player must be able to perceive escalating pressure, not only a static enemy placement.
                - Missing continuous spawn pressure proof means STATUS: needs_fix.
                """,
            "survivorslike-auto-attack-core-weapon-loop" => """
                Platform hard acceptance for Vampire Survivors-like core weapon:
                - The prototype must include auto-attack or equivalent repeated core weapon behavior.
                - Weapon cooldown, hit range/direction, enemy hit feedback, and kill feedback must be readable.
                - Missing core weapon loop proof means STATUS: needs_fix.
                """,
            "survivorslike-hit-damage-health-death-feedback" => """
                Platform hard acceptance for Vampire Survivors-like damage and death:
                - Player health or equivalent durability must be readable.
                - Enemy and player hit feedback, damage feedback, and death/failure feedback must be visible or validated.
                - Missing survival risk feedback means STATUS: needs_fix.
                """,
            "survivorslike-pickup-resource-collection" => """
                Platform hard acceptance for Vampire Survivors-like pickups:
                - Defeated enemies or arena events must create visible collectible resources.
                - Pickup collection must update experience, coins, energy, or equivalent progress.
                - Missing pickup/resource collection proof means STATUS: needs_fix.
                """,
            "survivorslike-level-up-choice-power-selection" => """
                Platform hard acceptance for Vampire Survivors-like level-up choice:
                - Resource threshold must trigger a small set of understandable power choices.
                - Selecting a choice must apply the selected upgrade.
                - Missing level-up choice or applied selection proof means STATUS: needs_fix.
                """,
            "survivorslike-build-growth-power-fantasy-feedback" => """
                Platform hard acceptance for Vampire Survivors-like power growth:
                - The selected upgrade must create visible before/after power growth in the survival loop.
                - Growth may affect damage, area, cooldown, projectile count, summon, speed, defense, or another project-specific stat.
                - Text-only upgrade proof is not sufficient when runtime behavior does not change.
                - Missing power fantasy feedback means STATUS: needs_fix.
                """,
            "survivorslike-escalation-event-mini-milestone" => """
                Platform hard acceptance for Vampire Survivors-like escalation:
                - The run must reach at least one escalation event or mini-milestone beyond basic spawning.
                - Examples: elite enemy, timed wave, chest/event, danger spike, milestone reward, or boss-like beat.
                - Missing escalation or milestone proof means STATUS: needs_fix.
                """,
            "survivorslike-run-end-summary-restart-loop" => """
                Platform hard acceptance for Vampire Survivors-like final first-loop closure:
                - Death, timeout, milestone completion, or stage result must lead to a readable run result.
                - The player must see a run summary and have a restart path.
                - Selected first-loop capabilities, project contract traceability, Godot validation evidence, and package readiness must pass.
                - Missing run summary/restart or final first-loop proof means STATUS: needs_fix.
                """,
            _ => ""
        };
        if (!string.IsNullOrWhiteSpace(survivorsLike))
        {
            return survivorsLike;
        }

        return contract.Kind switch
        {
            "rpg-step1-visible-map-movement" => """
                Platform hard acceptance for RPG Step 1:
                - Need: Game.Godot/Prototypes/dq-rpg/MapScene.tscn and Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs.
                - DqRpgPrototype.tscn keeps Start Adventure and CanvasLayer/UI/MapScene; click shows it via ShowMapScene or StartRun/StartAdventure.
                - MapScene has TrackLayer with RpgMapAsset, Grid, Overlay, and RpgPlayerAsset. Add RpgEnemyAsset only when the selected route includes encounter, conflict, or battle.
                - MapScene.cs moves player and maps grid positions; do not advance this step into encounter, battle, reward, or final acceptance work.
                - Missing contract means STATUS: needs_fix.
                """,
            "rpg-step2-encounter-trigger" => """
                Platform hard acceptance for RPG Step 2:
                - This step is encounter trigger validation, not BattleScene implementation.
                - Map traversal must expose visible encounter progress and a clear first encounter trigger.
                - Project-specific encounter probability or guaranteed-step rules must be visible and verifiable.
                - MapScene.cs must expose EncounterEntered/EncounterPressed/EncounterTriggered or equivalent movement-driven encounter wiring.
                - Do not advance this step into BattleScene settlement or reward selection.
                - Missing contract means STATUS: needs_fix.
                """,
            "rpg-step3-battlescene-settlement" => """
                Platform hard acceptance for RPG Step 3:
                - Need: Game.Godot/Prototypes/dq-rpg/BattleScene.tscn and Game.Godot/Prototypes/dq-rpg/Scripts/BattleScene.cs.
                - Keep battle UI and battle-side runtime behavior in the dedicated BattleScene instead of leaving the full battle loop only inside DqRpgPrototype.cs.
                - BattleScene.tscn must expose a recognizable BattleScene node, AttackButton, and file-backed Texture2D nodes named RpgPlayerAsset and RpgEnemyAsset.
                - BattleScene.cs must expose battle settlement wiring through BattleFinished and ResolveBattle/ResolveAttackTurn.
                - The battle loop must show readable enemy presentation, attack feedback, and victory or defeat settlement without advancing into reward selection.
                - Missing contract means STATUS: needs_fix.
                """,
            "rpg-step4-reward-choice-readability" => """
                Platform hard acceptance for RPG Step 4:
                - This step is reward choice understandability, not return-to-map implementation.
                - ShowRewardScene(rewards) must show exactly three understandable reward choices after a battle victory when rewards.Count > 0.
                - Each reward choice must communicate its effect clearly enough for the player to choose.
                - Keep markers: RewardOptions.Count and three visible reward choices.
                - If reward choices are missing, fewer than three, or unclear to the player, output STATUS: needs_fix.
                """,
            "rpg-step5-reward-loop-return-map" => """
                Platform hard acceptance for RPG Step 5:
                - ShowRewardScene(rewards) must show exactly three understandable reward choices after a battle victory when rewards.Count > 0.
                - Choosing a reward must apply one visible growth option: +5 HP, +2 ATK, or +1 DEF.
                - The +5 HP reward must make the post-reward state visibly equal to StartingPlayerHp + 5 for the first battle reward proof, not merely current damaged HP + 5.
                - Choosing any reward must close the reward UI, return to MapScene, keep the player visible and movable, and record Battle reward selected / Return to the map evidence.
                - MapScene.cs must expose ShowRewardReturnStatus or ApplyState so the return-to-map state is visible.
                - Keep markers: RewardOptions.Count, ApplyReward, Battle reward selected, Return to the map, ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward.
                - If reward values, reward UI, or return-to-map proof are missing, output STATUS: needs_fix.
                """,
            "rpg-step6-win-fail-visibility" => """
                Platform hard acceptance for RPG Step 6:
                - This step is win/fail visibility and readability, not the reward implementation step.
                - 15 battle wins must be visibly communicated as the game victory condition.
                - Any battle loss must visibly communicate game failure and stop the run.
                - Encounter rules and battle count progress must be readable at a glance in runtime UI.
                - Keep victory/failure markers: VictoryBattleCount, IsVictory, IsGameOver.
                - If win/fail rules are only in code or docs and not visible to the player, output STATUS: needs_fix.
                """,
            "rpg-step4-main-loop-scene-switching" => """
                Platform hard acceptance for RPG scene switching:
                - The main prototype scene must open the selected playable map, field, town, or next scene from the project entry.
                - Preserve Start Adventure, visible MapScene, player visibility, and stable return or continuation wiring for the current goal.
                - Require BattleScene, reward UI, or reward return proof only when the current platform contract explicitly requires those acceptances.
                - Missing selected scene switching proof means STATUS: needs_fix.
                """,
            "rpg-contract-alignment" => """
                Platform hard acceptance for RPG contract alignment:
                - Concrete user form values from the prototype contract must be represented in gameplay behavior, UI/state feedback, tests, or an explicit needs-fix blocker.
                - Validate only the selected route capabilities for this project; do not add BattleScene or reward work from template examples.
                - Missing contract traceability proof means STATUS: needs_fix.
                """,
            "rpg-asset-usage-validation" => """
                Platform hard acceptance for RPG asset usage:
                - Selected runtime scenes must use real file-backed Texture2D assets for required map/player nodes.
                - Enemy and BattleScene asset nodes are required only when the current platform contract includes battle acceptance.
                - Do not create unselected battle or reward scenes just to satisfy template examples.
                - Missing selected asset proof means STATUS: needs_fix.
                """,
            "rpg-loop-stability" => """
                Platform hard acceptance for RPG loop stability:
                - The selected playable loop must return or continue to a clear controllable state without breaking the current goal.
                - Trigger BattleScene or reward flows only when the current platform contract explicitly requires them.
                - Missing selected loop stability proof means STATUS: needs_fix.
                """,
            "rpg-final-full-playable-acceptance" => """
                Platform hard acceptance for RPG Final Step:
                - Full RPG prototype acceptance must pass the selected route capabilities, main-menu prototype entry, visible map after Start Adventure, Godot smoke, and package readiness.
                - Require BattleScene and reward return-to-map proof only when the project contract or current goal explicitly includes battle, encounter, conflict, reward, or return-loop capabilities.
                - Runtime visuals must use real file-backed Texture2D assets for selected runtime nodes such as MapScene RpgMapAsset and RpgPlayerAsset; require RpgEnemyAsset and BattleScene asset nodes only when encounter, conflict, or BattleScene is part of the selected route.
                - Copy/adapt selected assets into Game.Godot/Prototypes/dq-rpg/Assets/Map and Assets/Player; use Assets/Enemy only when enemy/encounter/conflict is selected. Reference them through res:// ext_resource Texture2D paths.
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
