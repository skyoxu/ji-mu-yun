## Tower Defense Specific Elements

### Tower Types and Upgrades

{{tower_types}}

**Tower design:**

- Tower categories (damage, slow, splash, support, special)
- Tower stats (damage, range, fire rate, cost)
- Upgrade paths (linear, branching)
- Tower synergies
- Tier progression
- Special abilities and targeting

### Enemy Wave Design

{{wave_design}}

**Enemy systems:**

- Enemy types (fast, tank, flying, immune, boss)
- Wave composition
- Wave difficulty scaling
- Wave scheduling and pacing
- Boss encounters
- Endless mode scaling (if applicable)

### Path and Placement Strategy

{{path_placement}}

**Strategic space:**

- Path structure (fixed, custom, maze-building)
- Placement restrictions (grid, free placement)
- Terrain types (buildable, non-buildable, special)
- Choke points and strategic locations
- Multiple paths (if applicable)
- Line of sight and range visualization

### Economy and Resources

{{economy}}

**Resource management:**

- Starting resources
- Resource generation (per wave, per kill, passive)
- Resource spending (towers, upgrades, abilities)
- Selling/refund mechanics
- Special currencies (if applicable)
- Economic optimization strategies

### Abilities and Powers

{{abilities_powers}}

**Active mechanics:**

- Player-activated abilities (airstrikes, freezes, etc.)
- Cooldown systems
- Ability unlocks
- Ability upgrade paths
- Strategic timing
- Resource cost vs. cooldown

### Difficulty and Replayability

{{difficulty_replay}}

**Challenge systems:**

- Difficulty levels
- Mission objectives (perfect clear, no lives lost, etc.)
- Star ratings
- Challenge modifiers
- Randomized elements
- New Game+ or prestige modes

### Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `defense_context_objective` | Defense context and objective | Always | Make clear what must be protected, where enemies come from, and how failure happens. | Core, base, exit, enemy entry, path, wave, lives, and failure condition are defined. |
| 2 | `lane_path_readability` | Lane and path readability | Always | Let the player read enemy movement before placing defenses. | At least one route, entry, exit, turn, blocking zone, or terrain boundary is visually or structurally clear. |
| 3 | `tower_placement_rules` | Tower placement rules | Always | Establish the main decision of where to build. | Tower selection, legal and illegal placement feedback, cost, and placed tower state are defined. |
| 4 | `tower_attack_targeting_loop` | Tower attack and targeting loop | Always | Prove defenses actually detect and affect enemies. | Tower range, targeting, attack timing, damage or status effect, and hit feedback are scoped. |
| 5 | `wave_spawn_pressure` | Wave spawn and pressure | Always | Create the wave-based attack rhythm. | Enemies spawn by wave, time, queue, or lane; current wave and next pressure are readable. |
| 6 | `damage_leak_life_feedback` | Damage, leaks, and base life feedback | Always | Show why the defense succeeds or fails. | Enemy damage, death, leaks, base life loss, victory, and failure state are defined. |
| 7 | `resource_income_spend_loop` | Resource income and spend loop | Always | Connect kills or waves to reinvestment. | Resource gain, tower cost, upgrade cost, spending feedback, and remaining budget are scoped. |
| 8 | `tower_upgrade_or_variant_choice` | Tower upgrade or variant choice | Conditional | Add strategic growth to the defense line. | If included, upgrade, branch, replacement, or tower variant changes range, damage, speed, effect, or appearance. |
| 9 | `enemy_type_counterplay` | Enemy type and counterplay | Conditional | Avoid pure number stacking by requiring response choices. | If included, at least two enemy types differ and have readable counterplay. |
| 10 | `build_phase_wave_transition` | Build phase and wave transition | Conditional | Support prepare, defend, and adjust pacing. | If included, pre-wave build, start wave, combat, post-wave adjustment, and next wave are defined. |
| 11 | `special_ability_or_active_tool` | Special ability or active tool | Optional | Support bombs, hero skills, slows, summons, traps, or emergency tools. | If included, active tool cost, cooldown, range, effect, and feedback are scoped. |
| 12 | `final_defense_loop_acceptance` | Final defense loop acceptance | Always | Validate one complete defense loop. | GDD or route plan links build, wave, tower attack, enemy result, resources, upgrade or next wave, and restart or continuation; excluded modules have reasons. |