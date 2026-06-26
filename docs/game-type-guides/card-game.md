## Card Game Specific Elements

### Card Types and Effects

{{card_types}}

**Card design:**

- Card categories (creatures, spells, enchantments, etc.)
- Card rarity tiers (common, rare, epic, legendary)
- Card attributes (cost, power, health, etc.)
- Effect types (damage, healing, draw, control, etc.)
- Keywords and abilities
- Card synergies

### Deck Building

{{deck_building}}

**Deck construction:**

- Deck size limits (minimum, maximum)
- Card quantity limits (e.g., max 2 copies)
- Class/faction restrictions
- Deck archetypes (aggro, control, combo, midrange)
- Sideboard mechanics (if applicable)
- Pre-built vs. custom decks

### Mana/Resource System

{{mana_resources}}

**Resource mechanics:**

- Mana generation (per turn, from cards, etc.)
- Mana curve design
- Resource types (colored mana, energy, etc.)
- Ramp mechanics
- Resource denial strategies

### Turn Structure

{{turn_structure}}

**Game flow:**

- Turn phases (draw, main, combat, end)
- Priority and response windows
- Simultaneous vs. alternating turns
- Time limits per turn
- Match length targets

### Card Collection and Progression

{{collection_progression}}

**Player progression:**

- Card acquisition (packs, rewards, crafting)
- Deck unlocks
- Currency systems (gold, dust, wildcards)
- Free-to-play balance
- Collection completion incentives

### Game Modes

{{game_modes}}

**Mode variety:**

- Ranked ladder
- Draft/Arena modes
- Campaign/story mode
- Casual/unranked
- Special event modes
- Tournament formats

### Module Matrix

This matrix is a first-loop planning convention for GDD creation and later module scoping. It does not override a project-specific brief, GDD, prototype type kit, or executable route contract.

Use only these default values: `Always`, `Conditional`, `Optional`, and `Out of Scope`.

| No | id | Module | Default | Purpose | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 1 | `run_context` | Run or match context | Always | Make clear whether the player is in a duel, run, draft, route node, or isolated encounter. | Player side, opponent or pressure source, short-term goal, failure condition, and forward route are visible or specified. |
| 2 | `starter_deck_readability` | Starter deck readability | Always | Validate that the player can understand their initial card toolbox. | Hand, draw pile, discard pile, or deck list is visible; card names, costs, and effects are readable. |
| 3 | `resource_and_turn_rules` | Resource and turn rules | Always | Validate the constraints that make card play meaningful. | Energy, mana, action points, candle, or equivalent resource is visible; playing cards consumes resources and advances or ends the turn correctly. |
| 4 | `enemy_intent_or_pressure` | Enemy intent or pressure source | Conditional | Give the player a reason to choose specific cards instead of clicking attacks blindly. | If included, enemy attack, buff, countdown, lane pressure, route danger, or narrative threat is visible before the player acts. |
| 5 | `card_play_resolution` | Card play resolution feedback | Always | Validate the minimum card interaction feel. | The player can play at least one card and see immediate damage, block, summon, sacrifice, draw, control, or equivalent feedback. |
| 6 | `deck_cycle_and_hand_flow` | Deck cycle and hand flow | Always | Cards must visibly move through the system rather than existing as static buttons. | Draw, discard, reshuffle, exhaust, or consume flow is visible and cannot dead-end the first turn loop. |
| 7 | `combat_resolution` | Combat or encounter resolution | Always | Complete the first conflict. | The encounter can reach victory, defeat, score threshold, objective completion, or another clear settlement state. |
| 8 | `reward_or_card_draft` | Post-combat reward or card draft | Conditional | Move from card combat into card building. | If included, at least two or three reward choices appear; the player can choose one and it affects the deck or next state. |
| 9 | `deck_mutation_feedback` | Deck mutation feedback | Conditional | Show that build decisions persist and matter. | Card gain, removal, upgrade, relic, artifact, totem, faction, or rule change is visible in the deck or next encounter. |
| 10 | `map_or_route_choice` | Map, route, event, shop, or elite choice | Optional | Support run structure beyond a single demo fight. | If included, the next node or route choice changes the next encounter, shop, event, or reward context. |
| 11 | `final_deckbuilder_first_loop_acceptance` | Final card-builder first-loop acceptance | Always | Validate a run loop rather than a single battle demo. | GDD or route plan links run start, route or node choice, combat, card play, settlement, reward or deck change, and return to route or next node; excluded modules have reasons. |