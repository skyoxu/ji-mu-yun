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

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| production_dashboard | Production dashboard | Show resources, generators, rates, and available upgrades. | Always | start | upgrade_shop,milestone_summary | Resources increase and UI communicates rate/change. |
| upgrade_shop | Upgrade shop | Incremental loops need spending and multiplier feedback. | Always | production_dashboard | production_dashboard | Player buys at least one upgrade that changes production. |
| milestone_summary | Milestone / prestige / summary | Long-term goals guide idle play. | Conditional | production_dashboard | production_dashboard | Milestone or summary appears when thresholds are reached. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| resource_accumulation | Resource accumulation over time or clicks | Always | Idle/incremental identity depends on growing numbers. | Resource increases through time, clicks, or automation. |
| upgrade_multipliers | Upgrade costs and effects | Always | Progression requires meaningful purchase choices. | Upgrade spends resources and changes rate/output/capacity. |
| automation_loop | Automation or passive production | Always | Idle play requires progress without constant action. | At least one generator produces automatically or on a timer. |
| milestone_scaling | Milestones, unlocks, or scaling costs | Conditional | Long-term structure prevents flat growth. | Threshold unlocks content or adjusts cost/output curve when in scope. |

## Module Matrix

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