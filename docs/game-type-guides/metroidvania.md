## Metroidvania Specific Elements

<narrative-workflow-recommended>
This game type is **narrative-moderate**. Consider running the Narrative Design workflow after completing the GDD to create:
- World lore and environmental storytelling
- Character encounters and NPC arcs
- Backstory reveals through exploration
- Optional narrative depth
</narrative-workflow-recommended>

### Interconnected World Map

{{world_map}}

**Map design:**

- World structure (regions, zones, biomes)
- Interconnection points (shortcuts, elevators, warps)
- Verticality and layering
- Secret areas
- Map reveal mechanics
- Fast travel system (if applicable)

### Ability-Gating System

{{ability_gating}}

**Progression gates:**

- Core abilities (double jump, dash, wall climb, swim, etc.)
- Ability locations and pacing
- Soft gates vs. hard gates
- Optional abilities
- Sequence breaking considerations
- Ability synergies

### Backtracking Design

{{backtracking}}

**Return mechanics:**

- Obvious backtrack opportunities
- Hidden backtrack rewards
- Fast travel to reduce tedium
- Enemy respawn considerations
- Changed world state (if applicable)
- Completionist incentives

### Exploration Rewards

{{exploration_rewards}}

**Discovery incentives:**

- Health/energy upgrades
- Ability upgrades
- Collectibles (lore, cosmetics)
- Secret bosses
- Optional areas
- Completion percentage tracking

### Combat System

{{combat_system}}

**Combat mechanics:**

- Attack types (melee, ranged, magic)
- Boss fight design
- Enemy variety and placement
- Combat progression
- Defensive options
- Difficulty balance

### Sequence Breaking

{{sequence_breaking}}

**Advanced play:**

- Intended vs. unintended skips
- Speedrun considerations
- Difficulty of sequence breaks
- Reward for sequence breaking
- Developer stance on breaks
- Game completion without all abilities

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| interconnected_room | Interconnected room | Provide traversal, combat/hazards, exits, and map memory. | Always | start | ability_gate | Room has at least two exits or a visible blocked path. |
| ability_gate | Ability gate | Show a path blocked/unlocked by ability, item, or movement skill. | Always | interconnected_room | interconnected_room,reward_unlock | Gate communicates requirement and changes after unlock. |
| reward_unlock | Reward / ability unlock | Progression depends on new traversal or combat capability. | Always | ability_gate,interconnected_room | interconnected_room | Player gains ability/item that enables a new route or interaction. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| traversal_controller | Traversal movement and collision | Always | Metroidvania identity depends on movement through rooms. | Movement/jump/dash or equivalent traversal is playable with collision. |
| room_graph | Room graph and transitions | Always | The world must feel interconnected. | At least two rooms/states or exits connect with persistent state. |
| ability_gating | Ability or item gating | Always | Nonlinear progression requires locks and unlocks. | A gate blocks progress until the player obtains an ability/item. |
| combat_or_hazards | Combat, hazards, or environmental pressure | Always | Rooms need challenge beyond walking. | Enemy/hazard damages, blocks, or tests traversal. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Metroidvania loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `interconnected_world_map` | Interconnected World Map | Conditional | Plan the first-loop interconnected world map needed for this game type. | If included, the GDD or route plan defines the interconnected world map behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `ability_gating_system` | Ability-Gating System | Conditional | Plan the first-loop ability-gating system needed for this game type. | If included, the GDD or route plan defines the ability-gating system behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `backtracking_design` | Backtracking Design | Conditional | Plan the first-loop backtracking design needed for this game type. | If included, the GDD or route plan defines the backtracking design behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `exploration_rewards` | Exploration Rewards | Conditional | Plan the first-loop exploration rewards needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the exploration rewards behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `combat_system` | Combat System | Conditional | Plan the first-loop combat system needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the combat system behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `sequence_breaking` | Sequence Breaking | Conditional | Plan the first-loop sequence breaking needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the sequence breaking behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_metroidvania_loop_acceptance` | Final Metroidvania first-loop acceptance | Always | Validate that the selected Metroidvania modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |