# Prototype Type Kits

This directory stores Phase A prototype type kits. A type kit is more specific than a generic BMAD/GDS game type guide: it defines the prototype-lane capability graph, minimum acceptance, scene responsibilities, and route recovery expectations for a game type.

Use these kits as document inputs before implementing or wiring executable game-type routes.

## Kits

| Game type | Kit | Source guide | Status |
| --- | --- | --- | --- |
| `rpg` | `rpg.md` | `docs/game-type-guides/rpg.md` | Executable JRPG/RPG route reference. |
| `deckbuilder` | `deckbuilder.md` | `docs/game-type-guides/card-game.md` | Executable deckbuilder route; route/map choice remains conditional. |

## Relationship To Game Type Guides

- `docs/game-type-guides/` contains extracted BMAD/GDS genre guides and broad design semantics.
- `docs/prototype-type-kits/` contains Phase A prototype-lane requirements and acceptance boundaries.
- For guide-level `Module Matrix` rules and authority order, see `docs/game-type-guides/README.md`.
- Do not treat a generic guide keyword or guide-level `Module Matrix` row as a runtime obligation. A type kit must decide whether a system is always-on, conditional, optional, or out of scope for an executable route.
