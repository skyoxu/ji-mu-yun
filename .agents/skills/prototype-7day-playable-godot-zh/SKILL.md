---
name: prototype-7day-playable-godot-zh
description: Use when running or guiding the Chinese 7-day playable Godot prototype lane from docs/workflows/prototype-7day-playable-godot-zh.md, especially to keep exploratory prototype work out of Chapter 3-7 formal delivery, load BMAD/GDS game-type guides, pause for player-provided gameplay definition fields, and route through run-prototype-workflow.
---

# Prototype 7-Day Playable Godot ZH

## Purpose

Operate the top-level prototype lane router for Chinese Godot prototype work without entering the formal Chapter 3 through Chapter 7 delivery flow.

## Required Reading

1. `docs/workflows/prototype-lane.md`
2. `docs/workflows/prototype-tdd.md`
3. `docs/workflows/prototype-7day-playable-godot-zh.md`
4. `docs/game-type-guides/README.md`
5. The specific `docs/game-type-guides/<game_type>.md` when project metadata contains a known game type.
6. The specific `docs/prototype-type-kits/<game_type>.md` when it exists, starting with `rpg.md`.

`AGENTS.md` is required only when maintaining the Phase A platform repo, workflow code, docs, or this skill. Hosted prototype routes must not use `AGENTS.md` as project recovery memory.


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

- 所有中文文档读写必须通过 Python 并显式 `encoding="utf-8"`。
- 严禁使用 PowerShell、`Get-Content`、`Set-Content`、`Out-File`、`Add-Content`、`type`、`echo` 或 Windows 原生文本工具读写中文。
- 如果命令脚本必须包含中文，使用 ASCII-only Python source + Unicode escapes，再用 UTF-8 写入目标文件。

- Speak to the user in Chinese.
- Keep logs and generated command output in English.
- Use Python with UTF-8 for document reads and writes.
- All user-facing interaction text emitted by the prototype top-level router must be Chinese (questions, missing-field prompts, confirmation summaries, resume hints).
- Do not create formal task refs, acceptance refs, overlay refs, or Chapter 6 evidence from prototype-lane output.
- Treat `docs/game-type-guides/` as extracted BMAD/GDS guide material. Use it to ask better prototype questions; do not copy a full GDD workflow into the prototype record.
- Treat `docs/prototype-type-kits/` as prototype-only default flow/UI material for 1-2 scene playable loops. Use it to confirm or adjust the default route; do not expand it into full GDD, balance, economy, progression, or boundary design.
- Stop for user input when required prototype fields are missing. Do not invent gameplay content.
- Main scene SOP: every prototype creation or repair that wires a playable prototype through `Game.Godot/Scenes/Main.tscn` must set the root-level `VBox`, `Overlays`, and `ScreenRoot` nodes to `visible = false` by default. They may be shown later only by explicit runtime navigation. This prevents template/debug UI from covering the prototype entry and is a final acceptance requirement.
- Godot C# namespace rule: any script under `namespace Game.Godot.*` must use `global::Godot.*` for fully qualified Godot API references, for example `global::Godot.Collections.Array<string>`. Prefer plain C# collections unless Godot serialization specifically requires Godot collections. This prevents C# from resolving `Godot.*` as `Game.Godot.*` inside project namespaces.

## Default Command

```powershell
py -3 scripts/python/dev_cli.py run-prototype-workflow --prototype-file docs/prototypes/<prototype-file>.md
```

Continue only after confirmation:

```powershell
py -3 scripts/python/dev_cli.py run-prototype-workflow --prototype-file docs/prototypes/<prototype-file>.md --confirm --godot-bin "$env:GODOT_BIN"
```

## Required Intake Fields

The router must have these fields before it can proceed beyond intake:

- `slug`
- `hypothesis`
- `core_player_fantasy`
- `minimum_playable_loop`
- `success_criteria`
- `game_feature`
- `core_gameplay_loop`
- `win_fail_conditions`

## Prototype Input Traceability

- The top-level prototype router must treat all non-empty intake fields as a project-specific input contract, not as loose background text.
- The canonical intake fields are: `slug`, `game_name`, `game_type`, `game_type_source`, `hypothesis`, `core_player_fantasy`, `minimum_playable_loop`, `success_criteria`, `game_feature`, `core_gameplay_loop`, and `win_fail_conditions`.
- The router must preserve these fields in the prototype record under `## Prototype Input Contract` and in the project prototype contract JSON as `form_fields` and `input_traceability`.
- Prototype creation, iteration-plan generation/evaluation, execute-next-goal, needs-fix, repair-plan, quick-fix, and final acceptance must consume the same prototype contract.
- Type templates and prototype type kits may provide defaults only for missing or ambiguous fields. They must not override concrete user values.
- If a non-empty user field cannot be reflected in gameplay, UI, scene flow, tests, or final acceptance, mark the relevant goal `needs_fix` and report the missing field coverage instead of reporting success.
- Iteration-plan generation must read the latest prototype outcome and imported draft coverage before deciding the next goals. The plan must be state-aware, not only type-template-aware.

## Top-Level Route Coordination

- Treat prototype creation, revalidation, repair-plan generation, execute-repair-step, quick-fix, needs-fix, iteration-plan generation/evaluation, and final acceptance as separate top-level routes sharing one prototype contract.
- When the frontend asks to revalidate a completed prototype, run validation only: completion-state checks, Godot smoke/navigation checks, and any game-type-specific hard validation. Do not call Codex during revalidation.
- If revalidation fails, generate or continue a repair plan from the latest failed run. Do not generate a normal polish iteration plan until the failed validation blocker is removed.
- Repair-plan generation must use the latest failed run evidence as source of truth, including route state, prototype contract, Godot smoke output, and game-type-specific validation evidence.
- Execute-repair-step must run only the current repair step. It must not regenerate the prototype, regenerate the iteration plan, regenerate the repair plan, or modify Phase A platform code.
- Quick-fix and needs-fix routes must keep the same route skill and game-type profile as the project. They must not fall back to generic prototype defaults when a specific game type has been resolved.
- Final acceptance must be stricter than prototype creation success. A completed Day 7 route is not sufficient when later revalidation exposes a game-type-specific failure.

The last three correspond to the user-facing pause sequence:

1. Game feature
2. Core gameplay loop
3. Win/fail conditions

Any user input is acceptable for these three fields; save it and continue to the next route step.

## Game Type Guide Use

If `README.md`, `meta/project-execution-guide.md`, or project metadata contains `Game Type: <id>` and `docs/game-type-guides/<id>.md` exists:

1. Load that guide before scoring or planning Day 1 to Day 5.
2. Use only the sections relevant to the prototype's smallest playable loop.
3. Preserve the router's lightweight purpose: capture core concept, gameplay uniqueness, loop, and win/fail conditions.

## Step07-Lite Intake

The prototype router reuses BMAD/GDS Step 7 as `Step07-lite`:

1. Parse `docs/game-type-guides/<game_type>.md` by `###` sections.
2. Select at most three prototype-relevant sections, prioritizing core mechanics, loop, progression, level/objective, controls, combat, and systems.
3. Pause for answers using `game_type_specifics.<section_id>` keys.
4. Save answers into:
   - `logs/ci/active-prototypes/<slug>.active.json`
   - `docs/prototypes/<date>-<slug>.md` under `## Game Type Specifics`
   - `logs/ci/project-health/latest.json` and `logs/ci/project-health/latest.html` after project-health scan
   - prototype TDD `summary.json` as `prototype_intake.game_type_specifics`

Do not use Step07-lite to run the full 14-step GDD flow. Do not generate formal task refs, acceptance refs, overlay refs, or Chapter 6 evidence.

Example continuation when the router asks a Step07-lite question:

```powershell
py -3 scripts/python/dev_cli.py run-prototype-workflow --resume-active gravity-room --set game_type_specifics.core_puzzle_mechanics="Flip gravity changes the valid path through one constrained room."
```

## Prototype Type Kit Intake

Prototype Type Kits are separate from BMAD/GDS Step07-lite. They capture the default 1-2 scene playable loop and scene UI for a specific game type.

Current source:

- `docs/prototype-type-kits/rpg.md`

When a matching kit exists:

1. Load `docs/prototype-type-kits/<game_type>.md` after the basic prototype fields and Step07-lite context are known.
2. Use its `Gameplay Flow / GDD Route` section to ask one confirmation round about the minimum playable route.
3. Use its `Prototype Scene UI` section to ask one confirmation round about the required scene UI.
4. Save the result under `## Prototype Type Kit` in `docs/prototypes/<date>-<slug>.md` or the user-provided prototype file.
5. Ensure prototype TDD can consume the record through `prototype_intake.prototype_type_kit` in `summary.json`.

For RPG, the required confirmation questions are:

- 使用随机遇怪、地图撞怪，还是二者都支持？
- 战斗是回合制指令，还是即时碰撞/自动战斗？
- 胜利后回到地图，还是进入结算后结束 prototype？
- 战斗场景需要哪些 UI：HP、指令按钮、战斗日志、技能栏？
- 地图场景需要哪些 UI：HP、任务提示、小地图、遇怪提示？
- 失败后是直接 Game Over，还是允许 Retry？

The canonical record shape is the `## Prototype Type Kit` section in `docs/prototypes/TEMPLATE.md`. Keep that section parseable by `run_prototype_tdd.py`:

```markdown
## Prototype Type Kit
- Game Type: rpg
- Kit Path: docs/prototype-type-kits/rpg.md

### Gameplay Flow / GDD Route
- 使用随机遇怪、地图撞怪，还是二者都支持？ <player answer>

### Prototype Scene UI
- 战斗场景需要哪些 UI：HP、指令按钮、战斗日志、技能栏？ <player answer>
```

Do not treat Prototype Type Kit answers as formal Chapter 6 evidence. They are prototype intake context only.

## Encoding Rule

- When writing Chinese content into `docs/prototypes/*.md`, `docs/prototype-type-kits/*.md`, or related skills/workflow docs, use Python and explicit UTF-8 encoding.
- Avoid relying on PowerShell default encoding for Chinese writes.

## Completion Boundary

Run only through Day 5 unless the user explicitly asks for manual Day 6/Day 7 planning. Day 6 playtest judgment and Day 7 `discard | archive | promote` remain human decision points.

## Prototype Spec Sidecar

- 顶层路由在确认阶段必须生成 `docs/prototypes/<slug>.prototype.json`。
- Markdown prototype 记录面向人类阅读；sidecar JSON 是 prototype TDD 和 project-health 的稳定脚本契约。
- TDD 必须优先消费 sidecar，只在 sidecar 不存在时回退解析 Markdown。
- project-health 必须展示 prototype blueprint：游戏特色、核心游戏循环、胜利/失败条件、Gameplay Flow、Prototype Scene UI 和 TDD 状态。
