## Puzzle Game Specific Elements

### Core Puzzle Mechanics

{{puzzle_mechanics}}

**Puzzle elements:**

- Primary puzzle mechanic(s)
- Supporting mechanics
- Mechanic interactions
- Constraint systems

### Puzzle Progression

{{puzzle_progression}}

**Difficulty progression:**

- Tutorial/introduction puzzles
- Core concept puzzles
- Combined mechanic puzzles
- Expert/bonus puzzles
- Pacing and difficulty curve

### Level Structure

{{level_structure}}

**Level organization:**

- Number of levels/puzzles
- World/chapter grouping
- Unlock progression
- Optional/bonus content

### Player Assistance

{{player_assistance}}

**Help systems:**

- Hint system
- Undo/reset mechanics
- Skip puzzle options
- Tutorial integration

### Replayability

{{replayability}}

**Replay elements:**

- Par time/move goals
- Perfect solution challenges
- Procedural generation (if applicable)
- Daily/weekly puzzles
- Challenge modes

### Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Puzzle loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `core_puzzle_mechanics` | Core Puzzle Mechanics | Conditional | Plan the first-loop core puzzle mechanics needed for this game type. | If included, the GDD or route plan defines the core puzzle mechanics behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `puzzle_progression` | Puzzle Progression | Conditional | Plan the first-loop puzzle progression needed for this game type. | If included, the GDD or route plan defines the puzzle progression behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `level_structure` | Level Structure | Conditional | Plan the first-loop level structure needed for this game type. | If included, the GDD or route plan defines the level structure behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `player_assistance` | Player Assistance | Conditional | Plan the first-loop player assistance needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the player assistance behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `replayability` | Replayability | Conditional | Plan the first-loop replayability needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the replayability behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `final_puzzle_loop_acceptance` | Final Puzzle first-loop acceptance | Always | Validate that the selected Puzzle modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |