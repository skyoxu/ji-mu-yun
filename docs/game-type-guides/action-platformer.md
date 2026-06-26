## Action Platformer Specific Elements

### Movement System

{{movement_mechanics}}

**Core movement abilities:**

- Jump mechanics (height, air control, coyote time)
- Running/walking speed
- Special movement (dash, wall-jump, double-jump, etc.)

### Combat System

{{combat_system}}

**Combat mechanics:**

- Attack types (melee, ranged, special)
- Combo system
- Enemy AI behavior patterns
- Hit feedback and impact

### Level Design Patterns

{{level_design_patterns}}

**Level structure:**

- Platforming challenges
- Combat arenas
- Secret areas and collectibles
- Checkpoint placement
- Difficulty spikes and pacing

### Player Abilities and Unlocks

{{player_abilities}}

**Ability progression:**

- Starting abilities
- Unlockable abilities
- Ability synergies
- Upgrade paths

### Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `traversal_context_objective` | Traversal context and objective | Always | Make clear where the player starts, where they need to go, and why movement matters. | Start point, endpoint or direction goal, controllable character, and objective cue are defined through UI, camera, composition, or landmarks. |
| 2 | `ground_movement_control` | Ground movement control | Always | Establish the basic feel of running, turning, stopping, and accelerating. | Movement response is stable; speed change is readable; the player does not stick to walls, jitter, or lose input. |
| 3 | `jump_gap_vault_flow` | Jump, gap, and vault flow | Always | Prove the basic platforming action can cross small obstacles. | The player can jump gaps, vault low obstacles, cross platforms, or clear an equivalent traversal challenge with clear success and failure feedback. |
| 4 | `route_readability_wayfinding` | Route readability and wayfinding | Always | Let the player read the intended path without external explanation. | Climbable edges, wall-run surfaces, jump points, landing zones, or route markers are distinguishable from decoration. |
| 5 | `vertical_surface_climb` | Vertical surface climb | Conditional | Support climbing-focused movement such as grip, upward travel, lateral travel, and mantle. | If included, the player can grab a specified surface, move on it, reach a top edge, or safely detach. |
| 6 | `momentum_chain_flow` | Momentum chain flow | Conditional | Support continuous action-platformer or parkour feel. | If included, at least two or three actions chain together, such as run-jump, slide, vault, wall run, dash, or landing into continued movement. |
| 7 | `grip_stamina_resource` | Grip or stamina resource | Optional | Create traversal pressure and route decisions. | If included, grip or stamina is visible; consumption and recovery are clear; depletion has a readable consequence. |
| 8 | `fall_risk_recovery_checkpoint` | Fall risk, recovery, and checkpoint | Always | Make height and failure safe to retry. | Falling, missing a jump, or failing a route gives clear feedback and respawns or recovers at a reasonable checkpoint without soft lock. |
| 9 | `environmental_timing_hazard` | Environmental timing or hazard | Optional | Add movement challenge through timing or danger. | If included, moving platforms, wind, collapse, lasers, patrol vision, spikes, or equivalent hazards are readable, avoidable, fail-able, and retryable. |
| 10 | `chase_or_pressure_sequence` | Chase or pressure sequence | Optional | Support pursuit, time limit, escape, alarm, or collapsing-route pacing. | If included, enemies, countdown, collapse, alarm, or chase pressure can be escaped through movement skill. |
| 11 | `route_discovery_reward` | Route discovery and reward | Optional | Reward alternate routes, shortcuts, collectibles, or high-skill traversal. | If included, at least one discoverable route, shortcut, collectible, or mastery reward provides visible feedback or practical benefit. |
| 12 | `final_traversal_acceptance` | Final traversal loop acceptance | Always | Validate the selected traversal modules end to end. | GDD or route plan links start, route reading, movement chain, success or failure recovery, and endpoint or next state; excluded modules have reasons. |