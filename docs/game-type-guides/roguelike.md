## Roguelike Specific Elements

### Run Structure

{{run_structure}}

**Run design:**

- Run length (time, stages)
- Starting conditions
- Difficulty scaling per run
- Victory conditions

### Procedural Generation

{{procedural_generation}}

**Generation systems:**

- Level generation algorithm
- Enemy placement
- Item/loot distribution
- Biome/theme variation
- Seed system (if deterministic)

### Permadeath and Progression

{{permadeath_progression}}

**Death mechanics:**

- Permadeath rules
- What persists between runs
- Meta-progression systems
- Unlock conditions

### Item and Upgrade System

{{item_upgrade_system}}

**Item mechanics:**

- Item types (passive, active, consumable)
- Rarity system
- Item synergies
- Build variety
- Curse/risk mechanics

### Character Selection

{{character_selection}}

**Playable characters:**

- Starting characters
- Unlockable characters
- Character unique abilities
- Character playstyle differences

### Difficulty Modifiers

{{difficulty_modifiers}}

**Challenge systems:**

- Difficulty tiers
- Modifiers/curses
- Challenge runs
- Achievement conditions

### Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Roguelike loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `run_structure` | Run Structure | Conditional | Plan the first-loop run structure needed for this game type. | If included, the GDD or route plan defines the run structure behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `procedural_generation` | Procedural Generation | Conditional | Plan the first-loop procedural generation needed for this game type. | If included, the GDD or route plan defines the procedural generation behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `permadeath_and_progression` | Permadeath and Progression | Conditional | Plan the first-loop permadeath and progression needed for this game type. | If included, the GDD or route plan defines the permadeath and progression behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `item_and_upgrade_system` | Item and Upgrade System | Conditional | Plan the first-loop item and upgrade system needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the item and upgrade system behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `character_selection` | Character Selection | Conditional | Plan the first-loop character selection needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the character selection behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `difficulty_modifiers` | Difficulty Modifiers | Conditional | Plan the first-loop difficulty modifiers needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the difficulty modifiers behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_roguelike_loop_acceptance` | Final Roguelike first-loop acceptance | Always | Validate that the selected Roguelike modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |