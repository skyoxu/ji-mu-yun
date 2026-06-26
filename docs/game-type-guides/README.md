# Game Type Guides

Source: `.agents/skills/gds-create-gdd/game-types/` and `.agents/skills/gds-create-gdd/game-types.csv`.

These 24 guides are the extracted BMAD/GDS game-type templates used by the prototype lane and project-health metadata. They are docs-side reference material only; they do not replace the formal Chapter 3 through Chapter 7 workflow.

Each guide includes a `Module Matrix` section. A matrix is an optional planning convention for first-loop GDD ordering, module scoping, and later route/type-kit design. It is not an executable route contract, and it does not override a project-specific brief, GDD, prototype type kit, or route strategy.

Authority order, highest first:

1. Executable route contract and strategy.
2. Prototype type kit.
3. Project-specific brief, GDD, or accepted user requirement.
4. Guide-level `Module Matrix`.
5. Guide prose.

A guide-level matrix is an input to type-kit authoring and route planning, not peer authority with a type kit or route strategy.

When a matrix is present, keep this column contract:

| Column | Required | Rule |
| --- | --- | --- |
| `No` | Yes | Stable display order only; it is not an execution step id. |
| `id` | Yes | Stable snake_case identifier for cross-reference from type kits or route docs. |
| `Module` | Yes | Human-readable module name. |
| `Default` | Yes | One of `Always`, `Conditional`, `Optional`, or `Out of Scope`. |
| `Purpose` | Yes | Why the module matters to the game type. |
| `Acceptance` | Yes | GDD or route-plan acceptance anchor, not final runtime evidence. |

- `Always`
- `Conditional`
- `Optional`
- `Out of Scope`

Canonical ids:

- `action-platformer` -> `action-platformer.md`
- `adventure` -> `adventure.md`
- `card-game` -> `card-game.md`
- `fighting` -> `fighting.md`
- `horror` -> `horror.md`
- `idle-incremental` -> `idle-incremental.md`
- `metroidvania` -> `metroidvania.md`
- `moba` -> `moba.md`
- `party-game` -> `party-game.md`
- `puzzle` -> `puzzle.md`
- `racing` -> `racing.md`
- `rhythm` -> `rhythm.md`
- `roguelike` -> `roguelike.md`
- `rpg` -> `rpg.md`
- `sandbox` -> `sandbox.md`
- `shooter` -> `shooter.md`
- `simulation` -> `simulation.md`
- `sports` -> `sports.md`
- `strategy` -> `strategy.md`
- `survival` -> `survival.md`
- `text-based` -> `text-based.md`
- `tower-defense` -> `tower-defense.md`
- `turn-based-tactics` -> `turn-based-tactics.md`
- `visual-novel` -> `visual-novel.md`
