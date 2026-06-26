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

### Module Matrix

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