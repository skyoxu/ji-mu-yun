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

### Module Matrix

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