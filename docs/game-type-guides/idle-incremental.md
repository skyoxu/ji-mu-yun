## Idle/Incremental Game Specific Elements

### Core Click/Interaction

{{core_interaction}}

**Primary mechanic:**

- Click action (what happens on click)
- Click value progression
- Auto-click mechanics
- Combo/streak systems (if applicable)
- Satisfaction and feedback (visual, audio)

### Upgrade Trees

{{upgrade_trees}}

**Upgrade systems:**

- Upgrade categories (click power, auto-generation, multipliers)
- Upgrade costs and scaling
- Unlock conditions
- Synergies between upgrades
- Upgrade branches and choices
- Meta-upgrades (affect future runs)

### Automation Systems

{{automation}}

**Passive mechanics:**

- Auto-clicker unlocks
- Manager/worker systems
- Multiplier stacking
- Offline progression
- Automation tiers
- Balance between active and idle play

### Prestige and Reset Mechanics

{{prestige_reset}}

**Long-term progression:**

- Prestige conditions (when to reset)
- Persistent bonuses after reset
- Prestige currency
- Multiple prestige layers (if applicable)
- Scaling between runs
- Endgame infinite scaling

### Number Balancing

{{number_balancing}}

**Economy design:**

- Exponential growth curves
- Notation systems (K, M, B, T or scientific)
- Soft caps and plateaus
- Time gates
- Pacing of progression
- Wall breaking mechanics

### Meta-Progression

{{meta_progression}}

**Long-term engagement:**

- Achievement system
- Collectibles
- Alternate game modes
- Seasonal content
- Challenge runs
- Endgame goals

### Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Idle Incremental loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `core_click_interaction` | Core Click/Interaction | Conditional | Plan the first-loop core click/interaction needed for this game type. | If included, the GDD or route plan defines the core click/interaction behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `upgrade_trees` | Upgrade Trees | Conditional | Plan the first-loop upgrade trees needed for this game type. | If included, the GDD or route plan defines the upgrade trees behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `automation_systems` | Automation Systems | Conditional | Plan the first-loop automation systems needed for this game type. | If included, the GDD or route plan defines the automation systems behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `prestige_and_reset_mechanics` | Prestige and Reset Mechanics | Conditional | Plan the first-loop prestige and reset mechanics needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the prestige and reset mechanics behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `number_balancing` | Number Balancing | Conditional | Plan the first-loop number balancing needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the number balancing behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `meta_progression` | Meta-Progression | Conditional | Plan the first-loop meta-progression needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the meta-progression behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_idle_incremental_loop_acceptance` | Final Idle Incremental first-loop acceptance | Always | Validate that the selected Idle Incremental modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |