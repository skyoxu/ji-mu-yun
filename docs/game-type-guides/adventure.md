## Adventure Specific Elements

<narrative-workflow-recommended>
This game type is **narrative-heavy**. Consider running the Narrative Design workflow after completing the GDD to create:
- Detailed story structure and beats
- Character profiles and arcs
- World lore and history
- Dialogue framework
- Environmental storytelling
</narrative-workflow-recommended>

### Exploration Mechanics

{{exploration_mechanics}}

**Exploration design:**

- World structure (linear, open, hub-based, interconnected)
- Movement and traversal
- Observation and inspection mechanics
- Discovery rewards (story reveals, items, secrets)
- Pacing of exploration vs. story

### Story Integration

{{story_integration}}

**Narrative gameplay:**

- Story delivery methods (cutscenes, in-game, environmental)
- Player agency in story (linear, branching, player-driven)
- Story pacing (acts, beats, tension/release)
- Character introduction and development
- Climax and resolution structure

**Note:** Detailed story elements (plot, characters, lore) belong in the Narrative Design Document.

### Puzzle Systems

{{puzzle_systems}}

**Puzzle integration:**

- Puzzle types (inventory, logic, environmental, dialogue)
- Puzzle difficulty curve
- Hint systems
- Puzzle-story connection (narrative purpose)
- Optional vs. required puzzles

### Character Interaction

{{character_interaction}}

**NPC systems:**

- Dialogue system (branching, linear, choice-based)
- Character relationships
- NPC schedules/behaviors
- Companion mechanics (if applicable)
- Memorable character moments

### Inventory and Items

{{inventory_items}}

**Item systems:**

- Inventory scope (key items, collectibles, consumables)
- Item examination/description
- Combination/crafting (if applicable)
- Story-critical items vs. optional items
- Item-based progression gates

### Environmental Storytelling

{{environmental_storytelling}}

**World narrative:**

- Visual storytelling techniques
- Audio atmosphere
- Readable documents (journals, notes, signs)
- Environmental clues
- Show vs. tell balance

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| exploration_scene | Exploration scene | Let the player inspect locations, objects, and route choices. | Always | start | interaction_dialogue,puzzle_or_objective | Scene contains interactables and a clear short-term objective. |
| interaction_dialogue | Interaction or dialogue state | Adventure games rely on authored interactions and narrative response. | Always | exploration_scene | exploration_scene | At least one object/NPC interaction reveals or changes state. |
| puzzle_or_objective | Puzzle, clue, or objective gate | Prove comprehension through a stateful gate. | Conditional | exploration_scene | exploration_scene | A clue/item/choice unlocks progress unless the GDD explicitly removes puzzles. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| interaction_hotspots | Interactable hotspots and inspection text | Always | The player must discover meaning through interaction. | Hotspots can be selected and produce contextual feedback. |
| inventory_or_clue_state | Inventory, clue, or flag state | Conditional | Stateful discovery prevents pure linear reading. | At least one flag/item/clue persists and gates or changes later content. |
| narrative_objective | Narrative objective tracking | Always | Exploration needs player intent. | Current goal is visible or strongly implied and updates after progress. |
| scene_transition | Scene or room transition | Conditional | Adventure structure commonly spans locations. | At least one transition exists when more than one location is present. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Adventure loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `exploration_mechanics` | Exploration Mechanics | Conditional | Plan the first-loop exploration mechanics needed for this game type. | If included, the GDD or route plan defines the exploration mechanics behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `story_integration` | Story Integration | Conditional | Plan the first-loop story integration needed for this game type. | If included, the GDD or route plan defines the story integration behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `puzzle_systems` | Puzzle Systems | Conditional | Plan the first-loop puzzle systems needed for this game type. | If included, the GDD or route plan defines the puzzle systems behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `character_interaction` | Character Interaction | Conditional | Plan the first-loop character interaction needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the character interaction behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `inventory_and_items` | Inventory and Items | Conditional | Plan the first-loop inventory and items needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the inventory and items behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `environmental_storytelling` | Environmental Storytelling | Conditional | Plan the first-loop environmental storytelling needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the environmental storytelling behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_adventure_loop_acceptance` | Final Adventure first-loop acceptance | Always | Validate that the selected Adventure modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |