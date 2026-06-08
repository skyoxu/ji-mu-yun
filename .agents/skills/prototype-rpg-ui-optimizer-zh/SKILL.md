---
name: prototype-rpg-ui-optimizer-zh
description: Use when a Phase A RPG/JRPG Godot prototype has completed its iteration plan and needs UI optimization against the game-type template, especially He-is-Coming-style map, battle, reward, status, and log panels.
---

# Prototype RPG UI Optimizer

Use this skill only for the dedicated `prototype-ui-optimization` route after the iteration plan is complete and before the second prototype acceptance.

## Recovery

1. Read `AGENTS.md` and `README.md`.
2. Read `meta/project-context.md` when present.
3. Read latest route state under `meta/routes/prototype/`, `meta/routes/iteration-plan/`, and `meta/routes/execute-next-goal/` when present.
4. Inspect `project.godot` and `Game.Godot/Prototypes/**`.

## Goal

Align the current RPG prototype UI with the project game-type template. For RPG/JRPG/DQ-like projects, treat `He-is-Coming` as the reference style:

- launch into the actual playable RPG prototype instead of the generic template `Main.tscn` demo UI;
- map/status UI should make movement, encounter pressure, chest/reward state, and party state visible;
- battle UI should make player/enemy state, turn result, reward choice, and battle log visible;
- user-facing labels should be Chinese when the project input/GDD is Chinese;
- prefer reusing existing scenes, scripts, panels, and nodes.

## Editing Rules

- Do not create a second unrelated prototype.
- Do not remove playable logic.
- Do not invent a new game loop.
- Prefer modifying existing `Game.Godot/Prototypes/**` scenes and scripts.
- If a local `DefaultRpgTemplate` or `He-is-Coming`-like prototype exists, reuse its layout/style patterns.
- Keep changes scoped to UI wiring, labels, layout, scene entry, and visual asset references needed for UI alignment.

## Completion

Report:

- changed files;
- which template UI features are now aligned;
- remaining gaps;
- whether a second prototype acceptance should be run.
