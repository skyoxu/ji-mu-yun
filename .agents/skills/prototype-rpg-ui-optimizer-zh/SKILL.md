---
name: prototype-rpg-ui-optimizer-zh
description: Use when a Phase A RPG/JRPG Godot prototype has completed its iteration plan and needs UI optimization against the game-type template, especially He-is-Coming-style map, battle, reward, status, and log panels.
---

# Prototype RPG UI Optimizer

Use this skill only for the dedicated `prototype-ui-optimization` route after the iteration plan is complete and before the second prototype acceptance.

## Recovery

1. Read `AGENTS.md` and `README.md` only for repository-level operating rules; do not use them as project completion memory.
2. Read `meta/project-execution-guide.md` and `meta/project-context.md` when present.
3. Read `meta/routes/prototype-contract/latest.json` as the primary project contract source. Concrete user form fields and `input_traceability` override templates and examples.
4. Use `routes/prototype-contract/latest.json` only as a legacy fallback when `meta/routes/prototype-contract/latest.json` is missing.
5. Read latest route state under `meta/routes/prototype/`, `meta/routes/iteration-plan/`, and `meta/routes/execute-next-goal/` when present.
6. Inspect `project.godot` and `Game.Godot/Prototypes/**`.
7. If a mandatory recovery source is missing, report the missing source explicitly and continue only when enough current project state exists to keep UI changes scoped.

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
