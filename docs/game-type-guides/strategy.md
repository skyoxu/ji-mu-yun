## Strategy Specific Elements

### Resource Systems

{{resource_systems}}

**Resource management:**

- Resource types (gold, food, energy, population, etc.)
- Gathering mechanics (auto-generate, harvesting, capturing)
- Resource spending (units, buildings, research, upgrades)
- Economic balance (income vs. expenses)
- Scarcity and strategic choices

### Unit Types and Stats

{{unit_types}}

**Unit design:**

- Unit roster (basic, advanced, specialized, hero units)
- Unit stats (health, attack, defense, speed, range)
- Unit abilities (active, passive, unique)
- Counter systems (rock-paper-scissors dynamics)
- Unit production (cost, build time, prerequisites)

### Technology and Progression

{{tech_progression}}

**Progression systems:**

- Tech tree structure (linear, branching, era-based)
- Research mechanics (time, cost, prerequisites)
- Upgrade paths (unit upgrades, building improvements)
- Unlock conditions (progression gates, achievements)

### Map and Terrain

{{map_terrain}}

**Strategic space:**

- Map size and structure (small/medium/large, symmetric/asymmetric)
- Terrain types (passable, impassable, elevated, water)
- Terrain effects (movement, combat bonuses, vision)
- Strategic points (resources, objectives, choke points)
- Fog of war / vision system

### AI Opponent

{{ai_opponent}}

**AI design:**

- AI difficulty levels (easy, medium, hard, expert)
- AI behavior patterns (aggressive, defensive, economic, adaptive)
- AI cheating considerations (fair vs. challenge-focused)
- AI personality types (if multiple opponents)

### Victory Conditions

{{victory_conditions}}

**Win/loss design:**

- Victory types (domination, economic, technological, diplomatic, etc.)
- Time limits (if applicable)
- Score systems (if applicable)
- Defeat conditions
- Early surrender / concession mechanics

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| command_map | Command map | Show the strategic board, units, territory, or base state. | Always | start | economy_build,battle_resolution | The player can inspect map state and choose a strategic action. |
| economy_build | Economy / build / production state | Allocate resources toward future tactical or strategic advantage. | Always | command_map | battle_resolution | At least one resource is spent to build, produce, research, or deploy. |
| battle_resolution | Battle or turn resolution | The plan produces a visible conflict or outcome. | Always | command_map,economy_build | command_map | A unit/order/tactic resolves and changes map or score state. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| resource_economy | Resource economy | Always | Strategic decisions need constrained resources. | Resources are displayed, spent, and changed by player choices. |
| unit_or_structure_rules | Unit, structure, or order rules | Always | The prototype needs controllable strategic actors. | At least one actor/structure accepts commands and changes state. |
| opposition_ai_or_rules | Opponent AI or rule pressure | Always | Without opposition there is no strategic tension. | Enemy, timer, wave, or objective pressure responds to player state. |
| turn_or_tick_resolution | Turn/tick/action resolution | Always | The game must advance consequences deterministically. | A clear turn, tick, or command resolution updates the world. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `strategic_context_objective` | Strategic context and victory objective | Always | Clarify faction, map, era, conflict, and victory condition. | Faction, strategic map, current phase, objective, and win or loss condition are defined. |
| 2 | `map_frontline_readability` | Map and frontline readability | Always | Make the strategic situation readable at a glance. | Territory, units, cities, borders, terrain, frontlines, or control zones are defined. |
| 3 | `turn_or_phase_loop` | Turn or phase loop | Always | Establish the decide, resolve, and next-turn rhythm. | Turn end, phase advance, action points, AI turn, or simultaneous resolution is scoped. |
| 4 | `unit_or_stack_control` | Unit or stack control | Always | Let players direct forces or agents. | Select, move, command, stance, attack, defend, or assign behavior is defined. |
| 5 | `resource_economy_loop` | Resource and economy loop | Always | Tie decisions to production and scarcity. | Resource income, stockpile, spending, upkeep, or shortage feedback is scoped. |
| 6 | `production_or_recruitment` | Production or recruitment | Always | Let the player convert resources into future capability. | Build, train, recruit, research, queue, or upgrade action is defined. |
| 7 | `combat_resolution` | Combat resolution | Always | Resolve strategic confrontation. | Battle, contest, influence, siege, capture, or opposed action result is defined. |
| 8 | `fog_of_war_or_scouting` | Fog of war or scouting | Conditional | Make uncertainty part of strategy when relevant. | If included, fog of war, scouting, reveal, detection, or intel rules are defined. |
| 9 | `technology_or_doctrine_growth` | Technology or doctrine growth | Conditional | Support long-term planning and unlocks. | If included, research, doctrine, policy, law, age, or faction bonus growth is scoped. |
| 10 | `diplomacy_or_politics` | Diplomacy or politics | Optional | Support non-combat strategic choices. | If included, alliance, trade, treaty, morale, loyalty, influence, or political event is defined. |
| 11 | `logistics_supply_control` | Logistics or supply control | Conditional | Support deeper operational planning when relevant. | If included, supply, transport, attrition, route, or capacity rules affect decisions. |
| 12 | `final_strategy_loop_acceptance` | Final strategy loop acceptance | Always | Validate a first strategic decision cycle. | GDD or route plan links map read, unit or economy action, resolution, feedback, and next phase; excluded modules have reasons. |