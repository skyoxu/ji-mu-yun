# Game Type Guides

Source: `.agents/skills/gds-create-gdd/game-types/` and `.agents/skills/gds-create-gdd/game-types.csv`.

These 25 guides are the extracted BMAD/GDS game-type templates used by the prototype lane and project-health metadata. They provide docs-side reference material plus workflow-consumed default prototype contracts; they do not replace the formal Chapter 3 through Chapter 7 workflow.

For browser preview generation, use [Web Preview Conversion Contract](web-preview-conversion-contract.md). The converter consumes packaged download artifacts and publishes a guest-readable `web/preview-contract.json` for package-to-preview consistency checks.

Each guide includes a `Default Prototype Contract` section and a `Module Matrix` section.

The `Default Prototype Contract` is workflow-consumed default guidance. It defines the game type's default scene topology and required baseline modules. Unless the user-confirmed GDD explicitly conflicts with an `Always` scene or module, GDD outline generation, scene-route drafting, prototype planning, and repair/iteration planning must preserve it. If the GDD overrides an `Always` item, the workflow should record the override reason explicitly.

The `Module Matrix` remains a planning convention for first-loop GDD ordering, module scoping, and later route/type-kit design. It is not an executable route contract, and it does not override a project-specific brief, GDD, prototype type kit, or route strategy.

Authority order, highest first:

1. Executable route contract and strategy.
2. Prototype type kit.
3. Project-specific brief, GDD, or accepted user requirement.
4. Guide-level `Default Prototype Contract`.
5. Guide-level `Module Matrix`.
6. Guide prose.

A guide-level default prototype contract is an input to GDD, scene-route, prototype planning, and repair/iteration prompts. A guide-level matrix is an input to type-kit authoring and route planning, not peer authority with a type kit or route strategy.

When a default prototype contract is present, keep these subsections:

1. `### Default Scenes`
2. `### Required Modules`

`Default Scenes` column contract:

| Column | Required | Rule |
| --- | --- | --- |
| `scene_id` | Yes | Stable snake_case identifier for scene-route and GDD references. |
| `scene_name` | Yes | Human-readable default scene name. |
| `purpose` | Yes | Why this scene exists for the type. |
| `required` | Yes | One of `Always`, `Conditional`, or `Optional`. |
| `entry_from` | Yes | Comma-separated source scene ids or `start`. |
| `exits_to` | Yes | Comma-separated destination scene ids or empty when terminal. |
| `minimum_playable_content` | Yes | Minimum evidence that the scene is represented in the first playable prototype. |

`Required Modules` column contract:

| Column | Required | Rule |
| --- | --- | --- |
| `module_id` | Yes | Stable snake_case identifier for GDD, plan, and repair references. |
| `module_name` | Yes | Human-readable module name. |
| `required_by_default` | Yes | One of `Always`, `Conditional`, or `Optional`. |
| `purpose` | Yes | Why the module matters to the game type. |
| `minimum_acceptance` | Yes | Minimum GDD or prototype-plan acceptance anchor. |

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
- `survivorslike` -> `survivorslike.md`
- `text-based` -> `text-based.md`
- `tower-defense` -> `tower-defense.md`
- `turn-based-tactics` -> `turn-based-tactics.md`
- `visual-novel` -> `visual-novel.md`
