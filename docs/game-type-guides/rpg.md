## RPG Specific Elements

### Character System

{{character_system}}

**Character attributes:**

- Stats (Strength, Dexterity, Intelligence, etc.)
- Classes/roles
- Leveling system
- Skill trees

### Inventory and Equipment

{{inventory_equipment}}

**Equipment system:**

- Item types (weapons, armor, accessories)
- Rarity tiers
- Item stats and modifiers
- Inventory management

### Quest System

{{quest_system}}

**Quest structure:**

- Main story quests
- Side quests
- Quest tracking
- Branching questlines
- Quest rewards

### World and Exploration

{{world_exploration}}

**World design:**

- Map structure (open world, hub-based, linear)
- Towns and safe zones
- Dungeons and combat zones
- Fast travel system
- Points of interest

### NPC and Dialogue

{{npc_dialogue}}

**NPC interaction:**

- Dialogue trees
- Relationship/reputation system
- Companion system
- Merchant NPCs

### Combat System

{{combat_system}}

**Combat mechanics:**

- Combat style (real-time, turn-based, tactical)
- Ability system
- Magic/skill system
- Status effects
- Party composition (if applicable)

### Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `opening_context` | Opening context, player identity, and current objective | Always | Establish who the player controls, where they are, and what they need to do now so the scene is not meaningless movement. | A playable scene clearly shows the controllable protagonist, current scene context, and short-term objective; the objective traces to project requirements or an explicit repair blocker. |
| 2 | `field_navigation` | Scene, map, town, field movement, and stable control | Always | Validate that the RPG map, town, or field layer works before combat and quests depend on it. | The entry opens a non-empty map or scene; the player character or marker is visible; movement is stable; map or player assets are actually used. |
| 3 | `interaction_discovery` | NPC dialogue, inspection, treasure, clues, and interactable discovery | Conditional | Make the map more than walking by adding NPCs, treasure, inspection targets, events, or discoveries. | If included, at least one project-relevant interaction is visible and reachable, and it changes feedback, objective state, or player understanding. |
| 4 | `conflict_entry` | Enemy encounter, challenge entry, and trigger rules | Optional | Validate the transition from exploration into combat, a challenge, or a dangerous event. | If included, the player can clearly trigger or reach the first conflict; the trigger rule is visible or verifiable, such as contact, random encounter, story trigger, or fixed steps. |
| 5 | `battle_or_challenge_resolution` | Battle, challenge, obstacle resolution, and success or failure settlement | Optional | Validate a readable RPG conflict resolution instead of only switching to a battle screen. | If included, at least one battle or challenge can be resolved; player and enemy or obstacle states are readable; action feedback is clear; victory, defeat, success, or failure is settled. |
| 6 | `party_or_character_state` | Character state, HP, stats, equipment, and party readability | Conditional | Help the player understand current capability and risk, such as HP, stats, equipment, class, allies, and status changes. | If included, relevant character or party state is visible, understandable, and consistent with project rules. |
| 7 | `growth_feedback` | Reward, growth, experience, level, item, skill, or consequence feedback | Optional | Validate that the player gains a benefit, change, or cost after the first loop, which is central to RPG continuation. | If included, reward, growth, or consequence is shown; the player can understand its meaning; state change is visible or verifiable. |
| 8 | `return_or_continue_loop` | Return to map or continue to the next playable state after reward or challenge | Conditional | Validate that combat or events do not break flow and the player can return, advance, or continue the loop. | If included, the prototype reaches the expected next playable state; input and navigation remain usable; no UI stack, scene lock, or state loss blocks continuation. |
| 9 | `quest_or_story_progress` | Quest, story, objective, or narrative progress | Conditional | Validate first-loop story progress when the project needs narrative, NPCs, town events, or quest goals. | If included, objective, quest, or story state advances visibly and can be traced to the project request. |
| 10 | `final_first_loop_acceptance` | Final first-loop acceptance | Always | Validate the full chain across entry, movement, interaction or encounter, battle or challenge, growth, return or continuation, and quest state. | Selected RPG modules are linked end to end; excluded conditional or optional modules have clear reasons; later execution scope must be confirmed by the type kit or route contract. |