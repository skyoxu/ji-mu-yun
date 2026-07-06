## Text-Based Game Specific Elements

<narrative-workflow-critical>
This game type is **narrative-critical**. You MUST run the Narrative Design workflow after completing the GDD to create:
- Complete story and all narrative paths
- Room descriptions and atmosphere
- Puzzle solutions and hints
- Character dialogue
- World lore and backstory
- Parser vocabulary (if parser-based)
</narrative-workflow-critical>

### Input System

{{input_system}}

**Core interface:**

- Parser-based (natural language commands)
- Choice-based (numbered/lettered options)
- Hybrid system
- Command vocabulary depth
- Synonyms and flexibility
- Error messaging and hints

### Room/Location Structure

{{location_structure}}

**World design:**

- Room count and scope
- Room descriptions (length, detail)
- Connection types (doors, paths, obstacles)
- Map structure (linear, branching, maze-like, open)
- Landmarks and navigation aids
- Fast travel or mapping system

### Item and Inventory System

{{item_inventory}}

**Object interaction:**

- Examinable objects
- Takeable vs. scenery objects
- Item use and combinations
- Inventory management
- Object descriptions
- Hidden objects and clues

### Puzzle Design

{{puzzle_design}}

**Challenge structure:**

- Puzzle types (logic, inventory, knowledge, exploration)
- Difficulty curve
- Hint system (gradual reveals)
- Red herrings vs. crucial clues
- Puzzle integration with story
- Non-linear puzzle solving

### Narrative and Writing

{{narrative_writing}}

**Story delivery:**

- Writing tone and style
- Descriptive density
- Character voice
- Dialogue systems
- Branching narrative (if applicable)
- Multiple endings (if applicable)

**Note:** All narrative content must be written in the Narrative Design Document.

### Game Flow and Pacing

{{game_flow}}

**Structure:**

- Game length target
- Acts or chapters
- Save system
- Undo/rewind mechanics
- Walkthrough or hint accessibility
- Replayability considerations

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| text_interface | Text interface | Present narrative, prompt, input/choices, and current state. | Always | start | state_update,ending | Player can read, choose/type, and receive response. |
| state_update | State update / log | Text games need persistent flags, inventory, or room state. | Always | text_interface | text_interface,ending | Input changes state and output reflects the change. |
| ending | Ending or branch result | Narrative choices should reach consequence. | Conditional | state_update | text_interface | At least one branch/failure/success result is reachable when scoped. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| parser_or_choice_input | Parser or choice input model | Always | Text interaction is the primary control surface. | Commands or choices are accepted and validated. |
| narrative_state | Narrative flags, inventory, room, or relationship state | Always | Responses need memory. | State changes from input and affects later output. |
| response_renderer | Text response and history renderer | Always | Readability is the entire interface. | Current response and recent history are legible and stable. |
| branching_logic | Branching, fail, or ending logic | Conditional | Interactive fiction needs consequences. | Different inputs can produce different reachable outcomes when in scope. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Text Based loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `input_system` | Input System | Conditional | Plan the first-loop input system needed for this game type. | If included, the GDD or route plan defines the input system behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `room_location_structure` | Room/Location Structure | Conditional | Plan the first-loop room/location structure needed for this game type. | If included, the GDD or route plan defines the room/location structure behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `item_and_inventory_system` | Item and Inventory System | Conditional | Plan the first-loop item and inventory system needed for this game type. | If included, the GDD or route plan defines the item and inventory system behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `puzzle_design` | Puzzle Design | Conditional | Plan the first-loop puzzle design needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the puzzle design behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `narrative_and_writing` | Narrative and Writing | Conditional | Plan the first-loop narrative and writing needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the narrative and writing behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `game_flow_and_pacing` | Game Flow and Pacing | Conditional | Plan the first-loop game flow and pacing needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the game flow and pacing behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_text_based_loop_acceptance` | Final Text Based first-loop acceptance | Always | Validate that the selected Text Based modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |