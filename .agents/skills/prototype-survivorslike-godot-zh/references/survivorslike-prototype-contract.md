# Vampire Survivors-like Prototype Contract

## Intent

This contract defines the default implementation expectations for a short playable Godot arena-survival prototype routed through `prototype-survivorslike-godot-zh`.

## User Input Traceability

- The project prototype contract is the first source of truth for runtime behavior.
- Form fields override this contract whenever they provide concrete values.
- Survival timer, enemy spawn rules, weapon behavior, pickup rules, level-up choices, escalation events, win/fail rules, and player fantasy must derive from user fields when present.
- If a concrete non-empty user field exists only in metadata or docs and not in runtime behavior, UI feedback, tests, or a recorded needs-fix reason, final acceptance must fail.

## First-Loop Capability Profile

The route uses a Vampire Survivors-like first-loop capability profile:

1. Run start and survival objective.
2. Arena movement and camera readability.
3. Enemy spawn pressure curve.
4. Auto-attack or core weapon loop.
5. Hit, damage, health, and death feedback.
6. Pickup and resource collection.
7. Level-up choice or power selection.
8. Build growth and power fantasy feedback.
9. Escalation event or mini-milestone.
10. Run end, summary, and restart loop.

## Runtime Expectations

### Run Start

- The player can start a survival run from the prototype entry.
- The run objective, timer, wave, or survival goal is visible.
- Initial player health, weapon, or equivalent state is readable.

### Arena

- Player movement is stable and continuous.
- Camera, viewport, and background keep the player and threats readable.
- Arena bounds or infinite-space handling must not break player control.

### Spawn Pressure

- Enemies spawn repeatedly through time, wave, distance, or pressure rules.
- Spawn pressure escalates or changes in a way the player can perceive.

### Core Weapon

- Auto-attack or equivalent repeated attack is present.
- Cooldown, range, hit, and kill feedback are readable.

### Damage And Death

- Player health or equivalent durability is visible.
- Enemy/player hit feedback and death/failure feedback are visible.

### Pickups

- Enemies or events generate collectible resources.
- Collecting resources updates experience, coins, energy, or equivalent progress.

### Level-Up Choice

- Reaching a resource threshold opens a small set of understandable power choices.
- Selecting one option applies the chosen upgrade.

### Growth Feedback

- Upgrades visibly change runtime behavior.
- Valid examples include damage, area, cooldown, projectile count, summon, movement, defense, or project-specific equivalent.

### Escalation

- The first loop includes one short climax or milestone beyond basic spawning.
- Valid examples include elite enemy, timed wave, chest/event, danger spike, milestone reward, or boss-like beat.

### Run End

- Death, timeout, milestone completion, or stage result leads to a readable result.
- The player sees a run summary and can restart.

## Delivery Boundary

This contract does not require:

- full meta-progression
- full roguelite economy
- permanent save data
- large content pools
- production-scale balancing

