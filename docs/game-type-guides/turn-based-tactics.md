## Turn-Based Tactics Specific Elements

<narrative-workflow-recommended>
This game type is **narrative-moderate to heavy**. Consider running the Narrative Design workflow after completing the GDD to create:
- Campaign story and mission briefings
- Character backstories and development
- Faction lore and motivations
- Mission narratives
</narrative-workflow-recommended>

### Grid System and Movement

{{grid_movement}}

**Spatial design:**

- Grid type (square, hex, free-form)
- Movement range calculation
- Movement types (walk, fly, teleport)
- Terrain movement costs
- Zone of control
- Pathfinding visualization

### Unit Types and Classes

{{unit_classes}}

**Unit design:**

- Class roster (warrior, archer, mage, healer, etc.)
- Class abilities and specializations
- Unit progression (leveling, promotions)
- Unit customization
- Unique units (heroes, named characters)
- Class balance and counters

### Action Economy

{{action_economy}}

**Turn structure:**

- Action points system (fixed, variable, pooled)
- Action types (move, attack, ability, item, wait)
- Free actions vs. costing actions
- Opportunity attacks
- Turn order (initiative, simultaneous, alternating)
- Time limits per turn (if applicable)

### Positioning and Tactics

{{positioning_tactics}}

**Strategic depth:**

- Flanking mechanics
- High ground advantage
- Cover system
- Formation bonuses
- Area denial
- Chokepoint tactics
- Line of sight and vision

### Terrain and Environmental Effects

{{terrain_effects}}

**Map design:**

- Terrain types (grass, water, lava, ice, etc.)
- Terrain effects (defense bonus, movement penalty, damage)
- Destructible terrain
- Interactive objects
- Weather effects
- Elevation and verticality

### Campaign Structure

{{campaign}}

**Mission design:**

- Campaign length and pacing
- Mission variety (defeat all, survive, escort, capture, etc.)
- Optional objectives
- Branching campaigns
- Permadeath vs. casualty systems
- Resource management between missions

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| tactical_grid | Tactical grid | Represent units, movement range, terrain, and turn order. | Always | start,prep_loadout | combat_resolution | Player selects unit, moves on grid, and performs an action. |
| prep_loadout | Preparation / squad setup | Tactics games often need unit/loadout setup. | Conditional | start | tactical_grid | Player can inspect or choose units when squad composition matters. |
| combat_resolution | Combat resolution | Turns need visible consequences and win/fail objective. | Always | tactical_grid | reward_debrief,tactical_grid | Attack/action resolves with HP/status/objective changes. |
| reward_debrief | Reward / debrief | Campaign tactics need post-mission feedback. | Conditional | combat_resolution | tactical_grid,prep_loadout | Mission result updates units/resources when campaign loop is in scope. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| grid_movement | Grid movement and range rules | Always | Tactics identity depends on spatial decisions. | Movement range, blocked tiles, and destination validation work. |
| turn_order | Turn order and action economy | Always | Players need structured tactical sequencing. | Units act in a clear order with limited actions. |
| combat_actions | Attack, skill, or ability resolution | Always | The grid must support meaningful conflict. | Action resolves hit/damage/status with feedback. |
| terrain_objectives | Terrain, cover, or mission objective rules | Conditional | Terrain/objectives create tactical depth. | At least one tile/objective modifier affects decisions when in scope. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Turn Based Tactics loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `grid_system_and_movement` | Grid System and Movement | Conditional | Plan the first-loop grid system and movement needed for this game type. | If included, the GDD or route plan defines the grid system and movement behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `unit_types_and_classes` | Unit Types and Classes | Conditional | Plan the first-loop unit types and classes needed for this game type. | If included, the GDD or route plan defines the unit types and classes behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `action_economy` | Action Economy | Conditional | Plan the first-loop action economy needed for this game type. | If included, the GDD or route plan defines the action economy behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `positioning_and_tactics` | Positioning and Tactics | Conditional | Plan the first-loop positioning and tactics needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the positioning and tactics behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `terrain_and_environmental_effects` | Terrain and Environmental Effects | Conditional | Plan the first-loop terrain and environmental effects needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the terrain and environmental effects behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `campaign_structure` | Campaign Structure | Conditional | Plan the first-loop campaign structure needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the campaign structure behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_turn_based_tactics_loop_acceptance` | Final Turn Based Tactics first-loop acceptance | Always | Validate that the selected Turn Based Tactics modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |