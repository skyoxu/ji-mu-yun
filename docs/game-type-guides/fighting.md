## Fighting Game Specific Elements

### Character Roster

{{character_roster}}

**Fighter design:**

- Roster size (launch + planned DLC)
- Character archetypes (rushdown, zoner, grappler, all-rounder, etc.)
- Move list diversity
- Complexity tiers (beginner vs. expert characters)
- Balance philosophy (everyone viable vs. tier system)

### Move Lists and Frame Data

{{moves_frame_data}}

**Combat mechanics:**

- Normal moves (light, medium, heavy)
- Special moves (quarter-circle, charge, etc.)
- Super/ultimate moves
- Frame data (startup, active, recovery, advantage)
- Hit/hurt boxes
- Command inputs vs. simplified inputs

### Combo System

{{combo_system}}

**Combo design:**

- Combo structure (links, cancels, chains)
- Juggle system
- Wall/ground bounces
- Combo scaling
- Reset opportunities
- Optimal vs. practical combos

### Defensive Mechanics

{{defensive_mechanics}}

**Defense options:**

- Blocking (high, low, crossup protection)
- Dodging/rolling/backdashing
- Parries/counters
- Pushblock/advancing guard
- Invincibility frames
- Escape options (burst, breaker, etc.)

### Stage Design

{{stage_design}}

**Arena design:**

- Stage size and boundaries
- Wall mechanics (wall combos, wall break)
- Interactive elements
- Ring-out mechanics (if applicable)
- Visual clarity vs. aesthetics

### Single Player Modes

{{single_player}}

**Offline content:**

- Arcade/story mode
- Training mode features
- Mission/challenge mode
- Boss fights
- Unlockables

### Competitive Features

{{competitive_features}}

**Tournament-ready:**

- Ranked matchmaking
- Lobby systems
- Replay features
- Frame delay/rollback netcode
- Spectator mode
- Tournament mode

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| fight_arena | Fight arena | Host the round with two fighters, health, timer, spacing, and hit feedback. | Always | start | round_result | Playable fight with attacks, block/dodge, and health changes. |
| character_select | Character select or matchup setup | Character-driven fighters need visible matchup setup. | Conditional | start | fight_arena | Player can choose or confirm fighter when multiple fighters exist. |
| round_result | Round result | Rounds need win/loss and rematch flow. | Always | fight_arena | fight_arena,character_select | KO, timer, or score result is shown with rematch path. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| fighter_controls | Movement, attack, block/dodge controls | Always | Fighting feel starts with responsive direct control. | Inputs trigger movement and at least light/heavy/special or equivalent actions. |
| hit_hurt_boxes | Hit/hurt detection and impact feedback | Always | Combat cannot be UI-only. | Attacks can connect/miss and produce stun, damage, or feedback. |
| round_rules | Health, timer, rounds, and win condition | Always | The fight needs competitive structure. | Round ends when health/time/score condition is met. |
| opponent_behavior | Opponent behavior or second-player input | Always | A solo dummy is insufficient unless explicitly requested. | AI or local second-player control can oppose the player. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Fighting loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `character_roster` | Character Roster | Conditional | Plan the first-loop character roster needed for this game type. | If included, the GDD or route plan defines the character roster behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `move_lists_and_frame_data` | Move Lists and Frame Data | Conditional | Plan the first-loop move lists and frame data needed for this game type. | If included, the GDD or route plan defines the move lists and frame data behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `combo_system` | Combo System | Conditional | Plan the first-loop combo system needed for this game type. | If included, the GDD or route plan defines the combo system behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `defensive_mechanics` | Defensive Mechanics | Conditional | Plan the first-loop defensive mechanics needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the defensive mechanics behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `stage_design` | Stage Design | Conditional | Plan the first-loop stage design needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the stage design behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `single_player_modes` | Single Player Modes | Conditional | Plan the first-loop single player modes needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the single player modes behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `competitive_features` | Competitive Features | Conditional | Plan the first-loop competitive features needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the competitive features behavior, player-facing feedback, and how it changes the first-loop state. |
| 9 | `final_fighting_loop_acceptance` | Final Fighting first-loop acceptance | Always | Validate that the selected Fighting modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |