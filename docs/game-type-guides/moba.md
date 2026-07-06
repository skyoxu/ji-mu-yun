## MOBA Specific Elements

### Hero/Champion Roster

{{hero_roster}}

**Character design:**

- Hero count (initial roster, planned additions)
- Hero roles (tank, support, carry, assassin, mage, etc.)
- Unique abilities per hero (Q, W, E, R + passive)
- Hero complexity tiers (beginner-friendly vs. advanced)
- Visual and thematic diversity
- Counter-pick dynamics

### Lane Structure and Map

{{lane_map}}

**Map design:**

- Lane configuration (3-lane, 2-lane, custom)
- Jungle/neutral areas
- Objective locations (towers, inhibitors, nexus/ancient)
- Spawn points and fountains
- Vision mechanics (wards, fog of war)

### Item and Build System

{{item_build}}

**Itemization:**

- Item categories (offensive, defensive, utility, consumables)
- Gold economy
- Build paths and item trees
- Situational itemization
- Starting items vs. late-game items

### Team Composition and Roles

{{team_composition}}

**Team strategy:**

- Role requirements (1-3-1, 2-1-2, etc.)
- Team synergies
- Draft/ban phase (if applicable)
- Meta considerations
- Flexible vs. rigid compositions

### Match Phases

{{match_phases}}

**Game flow:**

- Early game (laning phase)
- Mid game (roaming, objectives)
- Late game (team fights, sieging)
- Phase transition mechanics
- Comeback mechanics

### Objectives and Win Conditions

{{objectives_victory}}

**Strategic objectives:**

- Primary objective (destroy base/nexus/ancient)
- Secondary objectives (towers, dragons, baron, roshan, etc.)
- Neutral camps
- Vision control objectives
- Time limits and sudden death (if applicable)

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| lane_arena | Lane or arena map | Represent lanes, objectives, heroes, and team pressure. | Always | start | team_fight,shop_base | Playable top-down/arena space with objective and opposing pressure. |
| shop_base | Base, shop, or respawn state | Support reset, buying, leveling, or respawn. | Conditional | lane_arena | lane_arena | Player can recover, buy, level, or respawn when included. |
| team_fight | Team fight / objective clash | Show ability interplay and contestable goals. | Always | lane_arena | scoreboard_result,lane_arena | At least one hero ability interaction affects enemy/objective state. |
| scoreboard_result | Scoreboard or match result | Competitive loops need visible score/progress. | Always | team_fight | lane_arena | Kills/objectives/timer produce readable match feedback. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| hero_abilities | Hero abilities and cooldowns | Always | MOBA identity depends on ability kits. | At least two abilities or one ability plus basic attack have cooldown/feedback. |
| lane_or_objective_rules | Lane, tower, minion, or objective rules | Always | There must be a reason to fight over space. | Objective state changes through player/enemy actions. |
| enemy_team_pressure | Enemy hero, minion, or team pressure | Always | A MOBA without opposition is not representative. | Enemy actors contest the player or objective. |
| progression_items_levels | Items, levels, or temporary progression | Conditional | Most MOBAs include match-scoped growth. | Player gains level/item/power when the GDD includes progression. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first MOBA loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `hero_champion_roster` | Hero/Champion Roster | Conditional | Plan the first-loop hero/champion roster needed for this game type. | If included, the GDD or route plan defines the hero/champion roster behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `lane_structure_and_map` | Lane Structure and Map | Conditional | Plan the first-loop lane structure and map needed for this game type. | If included, the GDD or route plan defines the lane structure and map behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `item_and_build_system` | Item and Build System | Conditional | Plan the first-loop item and build system needed for this game type. | If included, the GDD or route plan defines the item and build system behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `team_composition_and_roles` | Team Composition and Roles | Conditional | Plan the first-loop team composition and roles needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the team composition and roles behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `match_phases` | Match Phases | Conditional | Plan the first-loop match phases needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the match phases behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `objectives_and_win_conditions` | Objectives and Win Conditions | Conditional | Plan the first-loop objectives and win conditions needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the objectives and win conditions behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_moba_loop_acceptance` | Final MOBA first-loop acceptance | Always | Validate that the selected MOBA modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |