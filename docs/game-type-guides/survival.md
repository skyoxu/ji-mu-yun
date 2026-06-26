## Survival Game Specific Elements

### Resource Gathering and Crafting

{{resource_crafting}}

**Resource systems:**

- Resource types (wood, stone, food, water, etc.)
- Gathering methods (mining, foraging, hunting, looting)
- Crafting recipes and trees
- Tool/weapon crafting
- Durability and repair
- Storage and inventory management

### Survival Needs

{{survival_needs}}

**Player vitals:**

- Hunger/thirst systems
- Health and healing
- Temperature/exposure
- Sleep/rest (if applicable)
- Sanity/morale (if applicable)
- Status effects (poison, disease, etc.)

### Environmental Threats

{{environmental_threats}}

**Danger systems:**

- Wildlife (predators, hostile creatures)
- Environmental hazards (weather, terrain)
- Day/night cycle threats
- Seasonal changes (if applicable)
- Natural disasters
- Dynamic threat scaling

### Base Building

{{base_building}}

**Construction systems:**

- Building materials and recipes
- Structure types (shelter, storage, defenses)
- Base location and planning
- Upgrade paths
- Defensive structures
- Automation (if applicable)

### Progression and Technology

{{progression_tech}}

**Advancement:**

- Tech tree or skill progression
- Tool/weapon tiers
- Unlock conditions
- New biomes/areas access
- Endgame objectives (if applicable)
- Prestige/restart mechanics (if applicable)

### World Structure

{{world_structure}}

**Map design:**

- World size and boundaries
- Biome diversity
- Procedural vs. handcrafted
- Points of interest
- Risk/reward zones
- Fast travel or navigation systems

### Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Survival loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `resource_gathering_and_crafting` | Resource Gathering and Crafting | Conditional | Plan the first-loop resource gathering and crafting needed for this game type. | If included, the GDD or route plan defines the resource gathering and crafting behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `survival_needs` | Survival Needs | Conditional | Plan the first-loop survival needs needed for this game type. | If included, the GDD or route plan defines the survival needs behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `environmental_threats` | Environmental Threats | Conditional | Plan the first-loop environmental threats needed for this game type. | If included, the GDD or route plan defines the environmental threats behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `base_building` | Base Building | Conditional | Plan the first-loop base building needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the base building behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `progression_and_technology` | Progression and Technology | Conditional | Plan the first-loop progression and technology needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the progression and technology behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `world_structure` | World Structure | Conditional | Plan the first-loop world structure needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the world structure behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_survival_loop_acceptance` | Final Survival first-loop acceptance | Always | Validate that the selected Survival modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |