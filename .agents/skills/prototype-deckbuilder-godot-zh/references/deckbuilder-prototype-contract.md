# Deckbuilder Prototype Contract

## Intent

This contract defines default implementation expectations for a short playable Godot deckbuilder prototype routed through `prototype-deckbuilder-godot-zh`.

## User Input Traceability

- The project prototype contract is the first source of truth for runtime behavior.
- Form fields override this contract whenever they provide concrete values.
- Card types, resources, turn rules, enemy pressure, reward rules, deck mutation, class selection, route-map path selection, hand-card dragging, win/fail conditions, and player fantasy must derive from user fields when present.
- If a concrete non-empty user field exists only in metadata or docs and not in runtime behavior, UI feedback, tests, or a recorded needs-fix reason, final acceptance must fail.

## First-Loop Capability Profile

The route uses a deckbuilder first-loop capability profile:

1. Run context and objective.
2. Class selection and starter deck readability.
3. Resource and turn rules.
4. Enemy intent or pressure source.
5. Card play resolution feedback with hand-card dragging.
6. Deck cycle and hand flow.
7. Combat win/fail resolution.
8. Post-combat card draft or reward.
9. Deck mutation feedback.
10. Map route choice by default.
11. Final deckbuilder first-loop acceptance.

## Runtime Expectations

### Run Context

- The player can start or enter a run.
- The current role, short-term objective, failure condition, or forward direction is visible.

### Starter Deck

- The player can choose a class, archetype, or starter identity before the route map unless the user-confirmed GDD explicitly conflicts with class selection.
- At least two class choices are visible.
- The selected class affects the starter deck, starting stats, or run identity.
- The player can inspect at least one of hand, draw pile, discard pile, deck list, or starter deck summary.
- Cards show name, cost/resource, and effect text.

### Resources And Turns

- Energy, mana, action point, candle, or project-specific cost is visible.
- Playing cards consumes resources correctly.
- The player can end or advance a turn.
- Invalid plays provide readable feedback.

### Enemy Intent Or Pressure

- Enemy attack, buff, countdown, track pressure, narrative threat, or equivalent pressure is visible.
- The pressure source gives the player a reason to choose cards tactically.

### Card Play

- The player can drag at least one card out of the hand.
- Dragging lifts the card above the hand and previews a valid or invalid target/play zone.
- Cancelled drags snap the card back to the hand.
- Dropping on a valid target or play zone resolves the card.
- Card play produces immediate visible feedback such as damage, block, draw, summon, sacrifice, status, or another project-specific effect.

### Deck Cycle

- Cards visibly move through at least one draw, discard, shuffle, exhaust, or equivalent flow.
- The flow is repeatable and does not deadlock after the first turn.

### Combat Result

- Combat can reach victory or defeat.
- The result is visible and understandable.

### Reward Or Card Draft

- Victory opens at least two or three reward/card choices unless the project contract explicitly replaces rewards with another deckbuilding mutation.
- The player can select or skip.
- The selected choice affects deck or run state.

### Deck Mutation

- Adding, removing, upgrading, or transforming a card, relic, artifact, totem, or rule visibly changes deck or run state.
- The player can understand what changed.

### Route Map Path Selection

- Route choice is required by default unless the user-confirmed GDD explicitly conflicts with it.
- The route map should be Slay-the-Spire-like: connected nodes, reachable next-node constraints, and a clear selected path.
- The player can choose among at least two reachable next nodes/routes/events.
- The selected route is stored or visibly reflected before transitioning into the selected encounter or next state.

## Delivery Boundary

This contract does not require:

- full card collection economy
- ranked or multiplayer modes
- long-term balance
- large content pools
- complete map acts
- permanent progression
- production-scale card art
