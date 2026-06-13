---
name: prototype-rpg-godot-zh
description: "Use when the prototype top-level router has identified game_type rpg and the repo should implement or refine a short playable Godot RPG prototype through TDD, including map scene, battle scene, assets, UI, and scene switching without hardcoded project or asset paths."
---

# Prototype RPG Godot ZH

## Purpose

Provide the default repo-local implementation lane for RPG/JRPG prototypes inside the 7-day playable Godot workflow, using a JRPG first-loop capability profile instead of a fixed DQ-like step script.

## Required Reading

1. `docs/workflows/prototype-lane.md`
2. `docs/workflows/prototype-tdd.md`
3. `docs/workflows/prototype-7day-playable-godot-zh.md`
4. `docs/prototype-type-kits/rpg.md`
5. `references/rpg-prototype-contract.md`

`AGENTS.md` is required only when maintaining the Phase A platform repo, workflow code, docs, or this skill. Hosted RPG project routes must not use `AGENTS.md` as project recovery memory.


## Hosted Route Recovery Protocol

Before any hosted prototype route implements or repairs a game project, restore project memory from project-level route files, not from `AGENTS.md`:

1. Read the resolved game-type route profile and this route skill prompt block.
2. Read `meta/project-execution-guide.md` as the project-level `/new` recovery protocol.
3. Read `routes/prototype-contract/latest.json`; concrete user form fields and `input_traceability` override templates.
4. Read only the latest route state relevant to the current route and current step, such as `meta/routes/prototype/latest.json`, `meta/routes/iteration-plan/latest.json`, `meta/routes/execute-next-goal/latest.json`, `meta/routes/prototype-repair/latest.json`, or `meta/routes/repair-plan/latest.json`.
5. For needs-fix, read the current step `meta/routes/needs-fix/step-XX/repair-ledger.json` before changing files and update it with fixed, remaining, and newly found blockers.
6. Treat the latest platform validation blocker as higher priority than older assistant summaries, route state, or repair ledger memory.

If a mandatory recovery source is missing, fail closed or record the missing source explicitly. Do not infer project completion from assistant text alone; completion must come from route state, current goal acceptance, or platform validation evidence.

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
- Iteration-plan generation must first inspect the latest successful or failed prototype result, compare it with the current prototype contract and imported draft/form fields, and only then select the JRPG first-loop capabilities that should be reconstructed, closed, or polished.
- Do not hardcode every RPG/JRPG project into a fixed six-step or seven-step DQ-like plan. DQ-like movement, encounter, battle, reward, return, win/fail, and final acceptance are valid semantic capability selections only when the project request supports them.
- Town-quest, story-event, exploration, or interaction-first JRPG prototypes may omit BattleScene or reward-choice capabilities when the project contract does not ask for conflict or growth.

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
- Selected runtime asset instances must use exact node names:
  - `RpgMapAsset` for the map/background asset when a map asset is used.
  - `RpgPlayerAsset` for the player/hero asset.
  - `RpgEnemyAsset` for the enemy/monster asset only when conflict/battle capability is selected or the latest failure names an enemy asset.
- `Start Adventure` must reveal a non-empty map scene. Put the instantiated `MapScene` under `CanvasLayer/UI`, not directly under a `Node2D` root, and anchor the map scene to the full viewport. Put `BattleScene` under `CanvasLayer/UI` only when battle/conflict capability is selected or the latest failure names it.
- The main RPG prototype script must resolve the map scene through `CanvasLayer/UI/MapScene` and make it visible when `StartButton.Pressed` fires.
- The visible `MapScene` must contain exact node names `Title`, `Grid`, and `StatusLabel`. Do not substitute `MapTitle`, `PositionLabel`, or other near-equivalent names; platform navigation smoke checks these names exactly.
- Main scene SOP: when the RPG prototype is reachable from `Game.Godot/Scenes/Main.tscn`, the root-level `VBox`, `Overlays`, and `ScreenRoot` nodes in `Main.tscn` must be present and default to `visible = false`. Do not leave template/debug UI visible over the prototype route. Final acceptance must fail if any of these nodes are missing or default-visible.
- The playable map must keep the background map asset, movement grid, and token overlay under one fixed-size shared layer, for example a `TrackLayer` sized to the playable map. Do not make `RpgMapAsset`, `Grid`, and `Overlay` independent sibling layout controls without a common coordinate parent.
- `RpgPlayerAsset`, selected `RpgEnemyAsset`, and chest/objective tokens must move in the same coordinate space as the visible map asset. If the map is 600x600 and the grid is 10x10, token movement must align to that 600x600 layer instead of drifting relative to the background.
- When BattleScene is selected, it must use file-backed Texture2D nodes named `RpgPlayerAsset` and `RpgEnemyAsset` for the player and enemy presentation. ColorRect-only battle tokens do not satisfy selected battle-scene or final acceptance.
- Battle `Attack` should advance the battle according to the prototype record. Do not make one button press immediately leave the battle scene unless that press actually reaches a terminal battle state.
- A normal battle win must enter the reward flow when reward options exist. Do not use the final-run victory flag as the condition for showing ordinary post-battle rewards.
- Returning from reward or battle to map must restore map visibility, player token visibility, and movement input.

## Core RPG Resource Routes

For RPG prototypes, the smallest strong-coupling resources are:

- Map assets: `Game.Godot/Prototypes/DefaultRpgTemplate/Assets/Map/`
- Player assets: `Game.Godot/Prototypes/DefaultRpgTemplate/Assets/Player/`
- Enemy assets: `Game.Godot/Prototypes/DefaultRpgTemplate/Assets/Enemy/`

Treat these as repo-relative defaults. When a project slug is created, copy or adapt them into that slug instead of hardcoding absolute paths.

## JRPG First-Loop Capability Scope

RPG/JRPG routes use a first-loop capability profile, not a fixed DQ-like map-battle-reward script. Select only the capabilities implied by the project form fields, prototype contract, `input_traceability`, route state, or an explicit needs-fix blocker.

| Id | Design Purpose | Pass Standard | Omit When |
|---|---|---|---|
| `opening_context` | Establish who the player controls, where the prototype starts, and the immediate objective before expanding systems. | The playable scene presents a clear controllable hero/context/objective, and the objective maps to the project contract or a recorded blocker. | Never omit for JRPG first-loop plans. |
| `field_navigation` | Validate the field, town, or map movement layer as the base experience. | Entry or Start Adventure opens a non-empty visible field/map/town scene, the player marker or character is visible, movement is stable, and selected map/player assets are represented. | Never omit for JRPG first-loop plans. |
| `interaction_discovery` | Give the field a meaningful discovery beat such as NPC dialogue, inspection, a chest, or objective reveal. | At least one project-relevant interaction is visible, reachable, and changes feedback, objective state, or player understanding. | Omit when the project has no interaction, discovery, NPC, object, or event requirement. |
| `conflict_entry` | Validate the transition from navigation/interaction into the first conflict, encounter, challenge, or battle. | The player can clearly trigger or reach the first conflict, and the trigger rule is visible or validated. | Omit when form/contract text has no encounter, battle, combat, enemy, monster, boss, fight, challenge, or equivalent conflict language. |
| `battle_or_challenge_resolution` | Validate one readable conflict resolution without hiding growth or return proof inside the battle step. | One conflict or challenge resolves with readable state, action feedback, and success/failure or victory/defeat settlement. BattleScene is required only when this selected capability uses a battle scene. | Omit whenever `conflict_entry` is omitted. Do not create BattleScene for non-combat JRPG forms. |
| `party_or_character_state` | Make player-facing character or party state readable and traceable to the rules. | Relevant HP, stats, party, equipment, passive skill, or status changes are visible, understandable, and consistent with project rules. | Omit when the first loop does not depend on character/party state readability beyond the visible actor. |
| `growth_feedback` | Prove the first loop's reward, growth, or consequence feedback. | Reward, item gain, stat change, experience, skill unlock, story consequence, or other state change is shown and understandable. | Omit when the project has no reward, growth, choice, item, level, experience, skill, or consequence requirement. |
| `return_or_continue_loop` | Ensure the prototype does not dead-end after a resolution. | The prototype reaches the intended next playable state, and navigation/input remain usable without visual stacking or broken state. | Omit only when the requested first loop intentionally ends at a terminal result. |
| `quest_or_story_progress` | Validate first-loop story or quest progress for narrative, town-event, or objective-driven JRPGs. | Objective, quest, or story state visibly progresses and remains traceable to the project request. | Omit when the project has no story, quest, NPC flow, town event, or objective-completion requirement. |
| `final_first_loop_acceptance` | Run final end-to-end acceptance across the selected JRPG capabilities. | Selected capabilities are playable end-to-end, project-specific contract fields are represented or explicitly blocked, assets resolve, Godot validation passes, and package readiness is proven. | Never omit for JRPG first-loop plans. |

BattleScene rule: if the form/contract/traceability does not mention combat or conflict, the route must not create, require, or repair BattleScene. Town-quest, story-event, exploration, and interaction-first JRPG prototypes are valid JRPG routes when they satisfy their selected capabilities.

Visual layer:
- prototype-safe sprites, props, tiles, and UI treatment
- no path assumptions about where generated assets live

## TDD Boundary

- Add or update tests before changing workflow or gameplay implementation behavior.
- Keep tests focused on prototype-lane behavior, intake parsing, routing, and the minimal playable loop.
- Do not expand into full RPG progression, economy, or long-term content systems unless explicitly requested.

## RPG Validation And Repair Routes

- When the top-level router identifies `game_type` as RPG, keep prototype creation, iteration planning, needs-fix, quick-fix, repair-plan, execute-repair-step, revalidation, and final acceptance on the RPG route profile.
- UI optimization is an optional polish route for RPG prototypes. It must not block RPG revalidation or final prototype acceptance after the iteration plan is complete.
- RPG revalidation must include the project-specific GdUnit behavior suite when it exists. For the current default RPG slice, use `tests/Prototype/DqRpgPrototype` relative to `Tests.Godot`; do not pass `Tests.Godot/tests/...` as the `--add` path.
- Treat `No test cases found` as validation failure even if the wrapper exits 0.
- Treat `GDUNIT_DONE rc=<nonzero>` as validation failure even if the wrapper normalized process exit code is 0.
- Treat Godot `ERROR:`, `SCRIPT ERROR`, `Parse Error`, missing resource, and `Node not found` markers from GdUnit console output as repair evidence. Do not hide them behind a generic "playable loop incomplete" diagnosis.
- Do not weaken, delete, or bypass the project-specific GdUnit tests to get green. Repair runtime assets, scenes, scripts, and contract drift instead.

## RPG GdUnit Repair Priority

When RPG project-specific GdUnit validation fails, repair in this order:

1. Runtime assets and Godot imports:
   - Restore or copy missing PNG assets into the active prototype slug, for example `Game.Godot/Prototypes/<slug>/Assets/`.
   - Fix scene `ext_resource` paths before changing gameplay logic.
   - Run Godot import through the project workflow after adding or restoring assets.
2. Scene node contract:
   - Ensure test-validated nodes exist at the authoritative path or update scene, script, and tests together to one contract.
   - For the default `dq-rpg` contract, GdUnit may require selected nodes such as `CanvasLayer/UI/MapScene/RpgMapAsset`, `RpgPlayerAsset`, `ChestToken`, plus `RpgEnemyAsset` or `CanvasLayer/UI/BattleScene/EnemyToken` only when battle/conflict capability is selected or the latest failure names them.
3. Script/runtime errors:
   - Fix invalid calls such as invoking `_UnhandledInput` on a `Control` base that does not expose it.
   - Keep map movement, encounter entry, battle, reward selection, and return-to-map callable through the same prototype shell used by tests.
4. Gameplay/input contract:
   - Preserve concrete user inputs such as reward 3-choice, visible battle comprehension, encounter rules, and win/fail conditions.
   - Do not replace a project contract such as "15 battles to win" with a shorter RPG template default.
5. Final validation:
   - Re-run the RPG GdUnit suite and then the platform revalidation route.
   - The repair is complete only when project-specific GdUnit, smoke/navigation, and frontend revalidation all pass.

## Repo-Relative References

- Skill file: `.agents/skills/prototype-rpg-godot-zh/SKILL.md`
- Contract file: `.agents/skills/prototype-rpg-godot-zh/references/rpg-prototype-contract.md`
