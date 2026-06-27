# Web Preview Conversion Contract

This document defines the docs-side contract for converting cloud-produced Godot package downloads into Godot 3 browser previews. It complements the per-game-type guides; it does not replace a project-specific GDD, package manifest, or executable route contract.

## Scope

The web-preview converter consumes a packaged download artifact, not the live project source directory. The package is the source of truth for preview generation.

The converter may use these package-visible inputs:

| Input | Required | Purpose |
| --- | --- | --- |
| `PACKAGE-MANIFEST.json` | Conditional | Project name, game name, declared game type, and package metadata. |
| `project.godot` | Conditional | Main scene and Godot project identity when present in the package. |
| `*.tscn` scene inventory | Conditional | Scene count, scene names, and game-type adapter hints. |
| Type guide id | Conditional | Maps a package to the nearest generic adapter when no high-fidelity template exists. |
| Template fingerprints | Optional | Enables a high-fidelity subset converter for known packages such as Towerdemo2. |
| Text catalog | Optional | Preserves package-visible UI/combat/domain text when exposed by the package. |

The converter must not read untracked source files from the project workspace to create the playable preview. If future converters need richer input, that input must first be included in the package or in a package-owned web-preview manifest.

## Adapter Contract

Each adapter must declare these stable fields in the generated runtime contract:

| Field | Rule |
| --- | --- |
| `mode` | Stable conversion mode identifier, e.g. `godot3-html5-rpg-package-preview`. |
| `converter_id` | Stable converter implementation id. |
| `converter_compatibility_id` | Compatibility/fingerprint id used to invalidate stale outputs. |
| `fidelity_tier` | One of `template_high_fidelity`, `game_type_adapter_preview`, or `generic_package_preview`. |
| `playable_surface` | Concrete playable surface represented by the preview. |
| `game_type_id` | Canonical guide id when a type adapter is used. Empty only for generic fallback. |
| `game_type_guide` | `docs/game-type-guides/<id>.md` when a guide-backed adapter is used. |

The generated guest-readable file is `web/preview-contract.json`. Smoke tests must treat this file as the public proof that a preview belongs to the current package and converter contract.

## Fidelity Tiers

| Tier | Meaning | Required playable behavior |
| --- | --- | --- |
| `template_high_fidelity` | Known package/template subset with source fingerprints. | Preserve the core loop, primary inputs, key text, and package-specific progression surface. |
| `game_type_adapter_preview` | Generic adapter selected by game type guide. | Provide an honest browser-playable approximation of the guide's dominant loop. |
| `generic_package_preview` | No reliable type adapter. | Provide package identity, scene inventory, and basic interactive scene inspection. |

A preview is a playable approximation and must not be presented as a Godot 4 to Godot 3 project migration.

## Guide-to-Adapter Expectations

| Guide family | Adapter style | Minimum playable surface |
| --- | --- | --- |
| `tower-defense`, `strategy`, `simulation`, `idle-incremental`, `moba`, `sandbox` | `tower-defense` | Placement or system-state action, wave/pressure progression, base/objective feedback. |
| `rpg`, `turn-based-tactics` | `rpg` | Movement or focus selection, encounter action, reward/status feedback. |
| `card-game`, `roguelike` when deck-focused | `card` | Hand/resource action, encounter state, scene or card focus. |
| `survival` | `survival` | Resource gathering, needs pressure, shelter/base state, and day/progression feedback. |
| `action-platformer`, `metroidvania`, `shooter`, `fighting`, `horror` | `survivorslike` or action adapter | Movement, attack/pressure loop, health or threat feedback. |
| `visual-novel`, `text-based`, `adventure` | `generic` narrative surface | Scene inspection, text/choice progression, package identity. |
| `puzzle`, `rhythm`, `racing`, `sports`, `party-game` | `generic` rules surface | Interactive inspection or simple rule-state progression. |

## Acceptance

A generated preview is acceptable only when all of the following are true:

1. The preview was generated from the selected package file and records its SHA-256 in `preview-contract.json`.
2. `index.html`, `index.js`, `index.wasm`, and `index.pck` are served as guest-readable preview assets.
3. `preview-contract.json` is served as guest-readable JSON and includes non-empty `package_file`, `package_sha256`, `mode`, `converter_id`, `fidelity_tier`, and `playable_surface`.
4. If `game_type_guide` is set, it points to `docs/game-type-guides/*.md` and `game_type_id` is non-empty.
5. Desktop and mobile browser smoke checks load a nonblank WebGL canvas and complete the loading overlay.
6. The package list exposes the ready preview only for the matching package file and preview id.

## Stale Output Rules

A preview must be considered stale when the package SHA-256, converter compatibility id, manifest SHA-256, or type adapter contract changes. Stale previews may remain stored, but package status must not present them as current for a different package.
