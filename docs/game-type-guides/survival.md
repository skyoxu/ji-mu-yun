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

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| survival_world | Survival world | Let the player explore, gather, face threats, and manage needs. | Always | start | craft_base,threat_event | Playable world space with resource pickup and danger or need pressure. |
| craft_base | Crafting / base / inventory state | Survival loops depend on resource conversion and preparation. | Always | survival_world | survival_world | Player can craft, build, or manage inventory from gathered resources. |
| threat_event | Threat or environmental event | Survival requires danger beyond collection. | Always | survival_world | death_or_safe_return,survival_world | Enemy, hunger, weather, darkness, or timer creates risk. |
| death_or_safe_return | Death, safe return, or day summary | Players need closure for failure or safe progress. | Conditional | threat_event | survival_world | Fail/safe condition is visible when health/needs/threats are active. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| vitals_resources | Vitals, resources, or condition meters | Always | Survival depends on constrained player state. | At least one need/resource changes through action or time. |
| gather_craft_build | Gathering, crafting, or building rules | Always | The loop needs resource transformation. | Resource pickup feeds a craft/build/use action. |
| threat_system | Threat, enemy, weather, or depletion pressure | Always | Risk differentiates survival from sandbox collection. | Threat can damage, block, chase, deplete, or force action. |
| inventory_persistence | Inventory and persistence | Always | Player preparation must carry across actions. | Inventory/resources persist across scene states or loop steps. |

## Module Matrix

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