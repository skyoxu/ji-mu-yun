---
name: prototype-rpg-godot-zh
description: "Use when the prototype top-level router has identified game_type rpg and the repo should implement or refine a short playable Godot RPG prototype through TDD, including map scene, battle scene, assets, UI, and scene switching without hardcoded project or asset paths."
---

# Prototype RPG Godot ZH

## Purpose

Provide the default repo-local implementation lane for RPG prototypes inside the 7-day playable Godot workflow.

## Required Reading

1. `AGENTS.md`
2. `docs/workflows/prototype-lane.md`
3. `docs/workflows/prototype-tdd.md`
4. `docs/workflows/prototype-7day-playable-godot-zh.md`
5. `docs/prototype-type-kits/rpg.md`
6. `references/rpg-prototype-contract.md`

## Operating Rules

## Highest Encoding Rule

- 中文文档读写必须使用 Python UTF-8。
- 不得用 PowerShell 或 Windows 原生文本工具读写中文。

- Speak to the user in Chinese.
- Keep file writes UTF-8.
- Do not hardcode absolute project paths, Godot project paths, or asset paths.
- Resolve all repo paths from the active repository root.
- Prefer repo-relative paths when recording metadata.
- Treat this skill as prototype-lane only, not Chapter 6 formal delivery.

## Default Contract

When `game_type` is `rpg`, this skill is the default implementation route for:

- prototype record generation details
- prototype TDD red/green work
- Godot prototype scene creation
- map scene and battle scene switching
- RPG prototype assets and UI visuals
- repo-local asset generation or replacement work

## Input Traceability Requirement

- RPG prototype work must consume the project prototype contract `form_fields` and `input_traceability` before applying RPG defaults.
- RPG defaults, bundled template assets, and example scenes are fallback implementation aids only. They must not replace concrete user values from `hypothesis`, `core_player_fantasy`, `minimum_playable_loop`, `success_criteria`, `game_feature`, `core_gameplay_loop`, or `win_fail_conditions`.
- Map traversal, encounter rules, battle stats, reward rules, victory/failure conditions, and UI wording should be derived from the user fields when those fields are non-empty.
- If the user says "each movement increases encounter chance by 10%" or "first enemy has 30 HP and 5 attack", that content must become gameplay logic, visible state, test expectation, or an explicit `needs_fix` blocker.
- Final RPG acceptance must fail when a concrete non-empty input field is only present in documentation but not represented in scene flow, runtime behavior, tests, or a recorded needs-fix reason.
- Iteration-plan generation must first inspect the latest successful or failed prototype result, compare it with the current prototype contract and imported draft/form fields, and only then decide whether the next steps are reconstruction, closure, or polish.
- Do not generate a generic six-step RPG plan when the current project already has a succeeded prototype run. In that case, prefer convergence steps such as contract drift repair, reward comprehension, failure-path closure, evidence readability, and final acceptance.

## Default Template Assets

Use the bundled RPG prototype asset pack as the default visual seed when the user does not provide stronger art direction:

- Asset pack root: `Game.Godot/Prototypes/DefaultRpgTemplate/Assets/`
- Scene template root: `Game.Godot/Prototypes/DefaultRpgTemplate/`
- Prototype record example: `docs/prototypes/2026-05-04-default-rpg-template.md`
- Template manifest: `docs/prototype-type-kits/default-rpg-template.manifest.json`

These files are template assets for RPG prototype work. Keep all references repo-relative, and copy or adapt them into a new prototype slug when the user wants a separate playable slice.



## Runtime Asset And UI Layout Rules

- Do not leave or create `Game.Godot/.gdignore` in an active RPG prototype project; it prevents Godot from importing and loading `res://Game.Godot/**` runtime assets.
- Copy or adapt the minimum required RPG visual assets into the current prototype slug, for example `Game.Godot/Prototypes/dq-rpg/Assets/`, before referencing them from scenes.
- After adding or copying PNG assets, run Godot import for the active project before smoke validation so `.import` metadata exists.
- The three required runtime asset instances must use exact node names:
  - `RpgMapAsset` for the map/background asset.
  - `RpgPlayerAsset` for the player/hero asset.
  - `RpgEnemyAsset` for the enemy/monster asset.
- `Start Adventure` must reveal a non-empty map scene. Put the instantiated `MapScene` and `BattleScene` under `CanvasLayer/UI`, not directly under a `Node2D` root, and anchor the map scene to the full viewport.
- The main RPG prototype script must resolve the map scene through `CanvasLayer/UI/MapScene` and make it visible when `StartButton.Pressed` fires.
- The visible `MapScene` must contain exact node names `Title`, `Grid`, and `StatusLabel`. Do not substitute `MapTitle`, `PositionLabel`, or other near-equivalent names; platform navigation smoke checks these names exactly.
- Main scene SOP: when the RPG prototype is reachable from `Game.Godot/Scenes/Main.tscn`, the root-level `VBox`, `Overlays`, and `ScreenRoot` nodes in `Main.tscn` must be present and default to `visible = false`. Do not leave template/debug UI visible over the prototype route. Final acceptance must fail if any of these nodes are missing or default-visible.
- The playable map must keep the background map asset, movement grid, and token overlay under one fixed-size shared layer, for example a `TrackLayer` sized to the playable map. Do not make `RpgMapAsset`, `Grid`, and `Overlay` independent sibling layout controls without a common coordinate parent.
- `RpgPlayerAsset`, `RpgEnemyAsset`, and chest/objective tokens must move in the same coordinate space as the visible map asset. If the map is 600x600 and the grid is 10x10, token movement must align to that 600x600 layer instead of drifting relative to the background.
- Battle `Attack` should advance the battle according to the prototype record. Do not make one button press immediately leave the battle scene unless that press actually reaches a terminal battle state.
- A normal battle win must enter the reward flow when reward options exist. Do not use the final-run victory flag as the condition for showing ordinary post-battle rewards.
- Returning from reward or battle to map must restore map visibility, player token visibility, and movement input.

## Core RPG Resource Routes

For RPG prototypes, the smallest strong-coupling resources are:

- Map assets: `Game.Godot/Prototypes/DefaultRpgTemplate/Assets/Map/`
- Player assets: `Game.Godot/Prototypes/DefaultRpgTemplate/Assets/Player/`
- Enemy assets: `Game.Godot/Prototypes/DefaultRpgTemplate/Assets/Enemy/`

Treat these as repo-relative defaults. When a project slug is created, copy or adapt them into that slug instead of hardcoding absolute paths.

## Expected RPG Scope

- Map scene:
  - tile/grid-based traversal
  - player movement
  - chest/objective placement
  - obstacle placement with reachable paths
  - encounter probability or collision-driven battle entry
- Battle scene:
  - player and enemy presentation
  - visible attributes
  - passive-skill-oriented auto or semi-auto resolution
  - battle log
  - victory/failure handling
- Reward loop:
  - roguelike three-choice reward
  - return from battle or chest reward back to map when applicable
- Visual layer:
  - prototype-safe sprites, props, tiles, and UI treatment
  - no path assumptions about where generated assets live

## TDD Boundary

- Add or update tests before changing workflow or gameplay implementation behavior.
- Keep tests focused on prototype-lane behavior, intake parsing, routing, and the minimal playable loop.
- Do not expand into full RPG progression, economy, or long-term content systems unless explicitly requested.

## Repo-Relative References

- Skill file: `.agents/skills/prototype-rpg-godot-zh/SKILL.md`
- Contract file: `.agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md`
