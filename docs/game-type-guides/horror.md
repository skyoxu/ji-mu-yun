## Horror Game Specific Elements

<narrative-workflow-recommended>
This game type is **narrative-important**. Consider running the Narrative Design workflow after completing the GDD to create:
- Detailed story structure and scares
- Character backstories and motivations
- World lore and mythology
- Environmental storytelling
- Tension pacing and narrative beats
</narrative-workflow-recommended>

### Atmosphere and Tension Building

{{atmosphere}}

**Horror atmosphere:**

- Visual design (lighting, shadows, color palette)
- Audio design (soundscape, silence, music cues)
- Environmental storytelling
- Pacing of tension and release
- Jump scares vs. psychological horror
- Safe zones vs. danger zones

### Fear Mechanics

{{fear_mechanics}}

**Core horror systems:**

- Visibility/darkness mechanics
- Limited resources (ammo, health, light)
- Vulnerability (combat avoidance, hiding)
- Sanity/fear meter (if applicable)
- Pursuer/stalker mechanics
- Detection systems (line of sight, sound)

### Enemy/Threat Design

{{enemy_threat}}

**Threat systems:**

- Enemy types (stalker, environmental, psychological)
- Enemy behavior (patrol, hunt, ambush)
- Telegraphing and tells
- Invincible vs. killable enemies
- Boss encounters
- Encounter frequency and pacing

### Resource Scarcity

{{resource_scarcity}}

**Limited resources:**

- Ammo/weapon durability
- Health items
- Light sources (batteries, fuel)
- Save points (if limited)
- Inventory constraints
- Risk vs. reward of exploration

### Safe Zones and Respite

{{safe_zones}}

**Tension management:**

- Safe room design
- Save point placement
- Temporary refuge mechanics
- Calm before storm pacing
- Item management areas

### Puzzle Integration

{{puzzles}}

**Environmental puzzles:**

- Puzzle types (locks, codes, environmental)
- Difficulty balance (accessibility vs. challenge)
- Hint systems
- Puzzle-tension balance
- Narrative purpose of puzzles

## Default Prototype Contract

This contract is workflow-consumed default guidance. Unless the user-confirmed GDD explicitly conflicts with it, `Always` scenes and modules must be included in the GDD outline, scene route, prototype plan, and repair/iteration planning. If the GDD overrides an `Always` item, record the override reason explicitly.

### Default Scenes

| scene_id | scene_name | purpose | required | entry_from | exits_to | minimum_playable_content |
| --- | --- | --- | --- | --- | --- | --- |
| tense_exploration | Tense exploration | Establish unsafe space, limited information, and objective. | Always | start | threat_encounter,safe_inventory | Player explores with restricted visibility/audio/tension cues. |
| threat_encounter | Threat encounter | Horror needs danger or psychological pressure. | Always | tense_exploration | escape_or_reveal,tense_exploration | Threat appears, pursues, attacks, stalks, or manipulates player state. |
| safe_inventory | Safe room / inventory / clue state | Alternate danger and preparation. | Conditional | tense_exploration | tense_exploration | Player can inspect clues/items or recover when included. |
| escape_or_reveal | Escape, reveal, or failure state | Tension needs a consequence or reveal. | Always | threat_encounter | tense_exploration | Player reaches escape/reveal/failure feedback. |

### Required Modules

| module_id | module_name | required_by_default | purpose | minimum_acceptance |
| --- | --- | --- | --- | --- |
| atmosphere_feedback | Lighting, audio, camera, or ambience feedback | Always | Horror relies on mood and readability. | Scene includes deliberate tension cues that react or guide play. |
| threat_behavior | Threat behavior or scripted scare | Always | There must be an active horror pressure. | Threat event changes player state, route, or objective. |
| limited_resources | Limited resource, inventory, or vulnerability rule | Conditional | Resource pressure supports survival horror. | Ammo/battery/health/key item is limited when survival horror is in scope. |
| mystery_objective | Mystery, clue, or escape objective | Always | Players need a reason to enter danger. | Objective/clue updates after exploration or threat interaction. |

## Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `first_loop_context` | First-loop context and objective | Always | Establish the player role, starting state, and near-term objective for the first Horror loop. | GDD or route plan identifies the player role, first playable state, short-term goal, and success or failure condition. |
| 2 | `atmosphere_and_tension_building` | Atmosphere and Tension Building | Conditional | Plan the first-loop atmosphere and tension building needed for this game type. | If included, the GDD or route plan defines the atmosphere and tension building behavior, player-facing feedback, and how it changes the first-loop state. |
| 3 | `fear_mechanics` | Fear Mechanics | Conditional | Plan the first-loop fear mechanics needed for this game type. | If included, the GDD or route plan defines the fear mechanics behavior, player-facing feedback, and how it changes the first-loop state. |
| 4 | `enemy_threat_design` | Enemy/Threat Design | Conditional | Plan the first-loop enemy/threat design needed for this game type. | If included, the GDD or route plan defines the enemy/threat design behavior, player-facing feedback, and how it changes the first-loop state. |
| 5 | `resource_scarcity` | Resource Scarcity | Conditional | Plan the first-loop resource scarcity needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the resource scarcity behavior, player-facing feedback, and how it changes the first-loop state. |
| 6 | `safe_zones_and_respite` | Safe Zones and Respite | Conditional | Plan the first-loop safe zones and respite needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the safe zones and respite behavior, player-facing feedback, and how it changes the first-loop state. |
| 7 | `puzzle_integration` | Puzzle Integration | Conditional | Plan the first-loop puzzle integration needed for this game type without turning the whole template into scope. | If included, the GDD or route plan defines the puzzle integration behavior, player-facing feedback, and how it changes the first-loop state. |
| 8 | `final_horror_loop_acceptance` | Final Horror first-loop acceptance | Always | Validate that the selected Horror modules form one coherent playable first loop. | GDD or route plan links entry, core action, feedback, result, and next state; excluded conditional or optional modules have clear reasons. |