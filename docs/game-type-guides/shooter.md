## Shooter Specific Elements

### Weapon Systems

{{weapon_systems}}

**Weapon design:**

- Weapon types (pistol, rifle, shotgun, sniper, explosive, etc.)
- Weapon stats (damage, fire rate, accuracy, reload time, ammo capacity)
- Weapon progression (starting weapons, unlocks, upgrades)
- Weapon feel (recoil patterns, sound design, impact feedback)
- Balance considerations (risk/reward, situational use)

### Aiming and Combat Mechanics

{{aiming_combat}}

**Combat systems:**

- Aiming system (first-person, third-person, twin-stick, lock-on)
- Hit detection (hitscan vs. projectile)
- Accuracy mechanics (spread, recoil, movement penalties)
- Critical hits / weak points
- Melee integration (if applicable)

### Enemy Design and AI

{{enemy_ai}}

**Enemy systems:**

- Enemy types (fodder, elite, tank, ranged, melee, boss)
- AI behavior patterns (aggressive, defensive, flanking, cover use)
- Spawn systems (waves, triggers, procedural)
- Difficulty scaling (health, damage, AI sophistication)
- Enemy tells and telegraphing

### Arena and Level Design

{{arena_level_design}}

**Level structure:**

- Arena flow (choke points, open spaces, verticality)
- Cover system design (destructible, dynamic, static)
- Spawn points and safe zones
- Power-up placement
- Environmental hazards
- Sightlines and engagement distances

### Multiplayer Considerations

{{multiplayer}}

**Multiplayer systems (if applicable):**

- Game modes (deathmatch, team deathmatch, objective-based, etc.)
- Map design for PvP
- Loadout systems
- Matchmaking and ranking
- Balance considerations (skill ceiling, counter-play)

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| combat_arena | Combat arena or mission room | Provide movement, aiming, firing, targets, and cover/space. | Always | start | objective_result | Playable arena with aim, weapon fire, enemy/target pressure, and hit feedback. |
| loadout_spawn | Loadout / spawn state | Define weapon and combat resources before action starts. | Conditional | start | combat_arena | Player starts with a defined weapon and ammo/resource state. |
| objective_result | Objective and result state | The loop needs win/fail/extract or score feedback. | Always | combat_arena | combat_arena | Kill, survive, extract, or score condition is detected and shown. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| movement_aiming | Movement and aim/facing controls | Always | Shooter feel depends on embodied aiming and positioning. | Mouse/keyboard or twin-stick aim updates facing and shot direction. |
| weapon_projectile_hits | Weapon, projectile, raycast, and hit feedback | Always | The core action must be playable, not UI-only. | Shots consume ammo/cooldown and can hit targets with feedback. |
| enemy_or_target_pressure | Enemies, targets, or combat pressure | Always | A shooting range without pressure is incomplete unless explicitly requested. | At least one target or enemy reacts, attacks, moves, or scores. |
| combat_hud | Ammo, health, crosshair, score, or objective HUD | Always | Players need immediate combat readability. | HUD shows critical combat state and updates during play. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Shooter loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `weapon_systems` | Weapon Systems | Conditional | Plan the first-loop weapon systems needed for this game type. | If included, the GDD or route plan defines the weapon systems behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `aiming_and_combat_mechanics` | Aiming and Combat Mechanics | Conditional | Plan the first-loop aiming and combat mechanics needed for this game type. | If included, the GDD or route plan defines the aiming and combat mechanics behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `enemy_design_and_ai` | Enemy Design and AI | Conditional | Plan the first-loop enemy design and ai needed for this game type. | If included, the GDD or route plan defines the enemy design and ai behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `arena_and_level_design` | Arena and Level Design | Conditional | Plan the first-loop arena and level design needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the arena and level design behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `multiplayer_considerations` | Multiplayer Considerations | Conditional | Plan the first-loop multiplayer considerations needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the multiplayer considerations behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `final_shooter_loop_acceptance` | Final Shooter first-loop acceptance | Always | Validate that the selected Shooter modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |