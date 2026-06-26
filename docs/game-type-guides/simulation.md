## Simulation Specific Elements

### Core Simulation Systems

{{simulation_systems}}

**What's being simulated:**

- Primary simulation focus (city, farm, business, ecosystem, etc.)
- Simulation depth (abstract vs. realistic)
- System interconnections
- Emergent behaviors
- Simulation tickrate and performance

### Management Mechanics

{{management_mechanics}}

**Management systems:**

- Resource management (budget, materials, time)
- Decision-making mechanics
- Automation vs. manual control
- Delegation systems (if applicable)
- Efficiency optimization

### Building and Construction

{{building_construction}}

**Construction systems:**

- Placeable objects/structures
- Grid system (free placement, snap-to-grid, tiles)
- Building prerequisites and unlocks
- Upgrade/demolition mechanics
- Space constraints and planning

### Economic and Resource Loops

{{economic_loops}}

**Economic design:**

- Income sources
- Expenses and maintenance
- Supply chains (if applicable)
- Market dynamics
- Economic balance and pacing

### Progression and Unlocks

{{progression_unlocks}}

**Progression systems:**

- Unlock conditions (achievements, milestones, levels)
- Tech/research tree
- New mechanics/features over time
- Difficulty scaling
- Endgame content

### Sandbox vs. Scenario

{{sandbox_scenario}}

**Game modes:**

- Sandbox mode (unlimited resources, creative freedom)
- Scenario/campaign mode (specific goals, constraints)
- Challenge modes
- Random/procedural scenarios
- Custom scenario creation

### Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Simulation loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `core_simulation_systems` | Core Simulation Systems | Conditional | Plan the first-loop core simulation systems needed for this game type. | If included, the GDD or route plan defines the core simulation systems behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `management_mechanics` | Management Mechanics | Conditional | Plan the first-loop management mechanics needed for this game type. | If included, the GDD or route plan defines the management mechanics behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `building_and_construction` | Building and Construction | Conditional | Plan the first-loop building and construction needed for this game type. | If included, the GDD or route plan defines the building and construction behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `economic_and_resource_loops` | Economic and Resource Loops | Conditional | Plan the first-loop economic and resource loops needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the economic and resource loops behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `progression_and_unlocks` | Progression and Unlocks | Conditional | Plan the first-loop progression and unlocks needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the progression and unlocks behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `sandbox_vs_scenario` | Sandbox vs. Scenario | Conditional | Plan the first-loop sandbox vs. scenario needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the sandbox vs. scenario behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_simulation_loop_acceptance` | Final Simulation first-loop acceptance | Always | Validate that the selected Simulation modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |