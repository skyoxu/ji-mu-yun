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
