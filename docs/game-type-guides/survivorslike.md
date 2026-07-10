# Survivorslike Web Preview Guide

This guide covers Vampire Survivors-like arena survival projects for the web-preview converter.

The package-derived Godot 3 preview should prioritize:

- continuous arena movement
- simple attack or auto-attack pressure
- enemy wave pressure
- upgrade or reward feedback when package metadata exposes it
- readable scene markers derived from packaged Godot scenes

The preview is a browser-playable approximation built from the packaged download artifact. It is not a lossless Godot 4 to Godot 3 gameplay port.

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| arena_survival | Arena survival | Host continuous movement, enemy swarms, auto-attacks, XP, and timer pressure. | Always | start | upgrade_choice,run_summary | Player survives in arena with enemy waves and automatic or simple attacks. |
| upgrade_choice | Upgrade choice | Survivorslike loops depend on periodic build choices. | Always | arena_survival | arena_survival | Player chooses an upgrade that changes weapon/stats/behavior. |
| run_summary | Run summary | Runs need death/victory/time summary and retry path. | Always | arena_survival | arena_survival | Timer, kills, level, or score are summarized after fail/win. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| continuous_movement | Continuous arena movement | Always | The player must kite and reposition under pressure. | Movement is continuous, responsive, and bounded by arena/camera rules. |
| auto_attack_weapons | Auto-attack or simple weapon system | Always | The genre depends on attacks firing while movement remains primary. | Weapon triggers by timer/input and damages enemies. |
| enemy_wave_spawner | Enemy swarm and wave pressure | Always | Pressure scaling defines the loop. | Enemies spawn over time and approach or pressure the player. |
| xp_upgrade_loop | XP, level-up, and upgrade selection | Always | Build growth differentiates the genre from a basic shooter. | Collecting XP or rewards opens upgrade choice and applies effect. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `arena_movement_context` | Arena movement context | Always | Establish the player, arena boundary, movement rules, and immediate survival objective. | The player can move continuously in a bounded arena and the survival objective is visible or strongly implied. |
| 2 | `automatic_weapon_pressure` | Automatic weapon pressure | Always | Keep movement primary while attacks resolve through timers, proximity, or simple aim rules. | At least one weapon fires or resolves repeatedly and visibly damages enemies. |
| 3 | `enemy_swarm_scaling` | Enemy swarm scaling | Always | Create increasing positional pressure over the run. | Enemies spawn over time, approach the player, and increase pressure without immediate soft lock. |
| 4 | `xp_level_upgrade_choice` | XP, level, and upgrade choice | Always | Turn survival time and defeated enemies into build growth. | Collecting XP or rewards triggers a choice and the selected upgrade changes weapon, stats, or behavior. |
| 5 | `health_failure_retry` | Health, failure, and retry | Always | Make damage, death, and restart readable. | Health or equivalent survival state changes on contact; failure produces a summary and a working retry path. |
| 6 | `timed_run_progression` | Timed run progression | Conditional | Support waves, elapsed-time milestones, elite spawns, or a run endpoint. | If included, elapsed time or wave state changes encounter pressure and reaches a visible milestone. |
| 7 | `reward_build_synergy` | Reward and build synergy | Optional | Let upgrades combine into a recognizable run build. | If included, at least two choices interact or create a visible weapon/stat synergy. |
| 8 | `final_survivorslike_loop_acceptance` | Final survivorslike loop acceptance | Always | Validate one coherent arena-survival loop end to end. | GDD or route plan links movement, weapon pressure, enemy scaling, growth choice, failure or milestone, summary, and retry; excluded modules have reasons. |
