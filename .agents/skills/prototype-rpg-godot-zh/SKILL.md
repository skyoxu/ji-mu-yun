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

## Default Template Assets

Use the bundled RPG prototype asset pack as the default visual seed when the user does not provide stronger art direction:

- Asset pack root: `Game.Godot/Prototypes/DefaultRpgTemplate/Assets/`
- Scene template root: `Game.Godot/Prototypes/DefaultRpgTemplate/`
- Prototype record example: `docs/prototypes/2026-05-04-default-rpg-template.md`
- Template manifest: `docs/prototype-type-kits/default-rpg-template.manifest.json`

These files are template assets for RPG prototype work. Keep all references repo-relative, and copy or adapt them into a new prototype slug when the user wants a separate playable slice.


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
