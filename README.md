[![Windows Export Slim](https://github.com/skyoxu/godotgame/actions/workflows/windows-export-slim.yml/badge.svg)](https://github.com/skyoxu/godotgame/actions/workflows/windows-export-slim.yml) [![Windows Release](https://github.com/skyoxu/godotgame/actions/workflows/windows-release.yml/badge.svg)](https://github.com/skyoxu/godotgame/actions/workflows/windows-release.yml) [![Windows Quality Gate](https://github.com/skyoxu/godotgame/actions/workflows/windows-quality-gate.yml/badge.svg)](https://github.com/skyoxu/godotgame/actions/workflows/windows-quality-gate.yml)

# Godot Windows-only Template (C#)

即开即用，可复制的 Godot 4 + .NET（Windows-only）项目模板。

## Highest Encoding Rule
- All Chinese text reads and writes must use Python with explicit UTF-8, for example `Path(path).read_text(encoding="utf-8")` and `Path(path).write_text(text, encoding="utf-8", newline="\n")`.
- Do not use PowerShell, `Get-Content`, `Set-Content`, `Out-File`, `Add-Content`, `type`, `echo`, `copy con`, or other Windows-native text tools to read or write Chinese text.
- If a command script must contain Chinese literals, write it as a Python file or use ASCII-only Python source with Unicode escapes, then write the target file as UTF-8.
- This rule applies to `AGENTS.md`, `README.md`, `workflow.md`, `docs/**/*.md`, `.agents/skills/**/SKILL.md`, prototype records, and project-health documentation.
- Code, tests, logs, and machine output remain English unless the file is explicitly user-facing documentation.

## About This Template

Production-ready Godot 4.5 + C# game template with enterprise-grade tooling.

### Why This Template
- **Historical lineage**: this repository was originally bootstrapped from a legacy stack and is now fully standardized on Godot 4.5 + C# .NET 8 (Windows-only).
- **Purpose**: Eliminate setup overhead with pre-configured best practices
- **For**: Windows desktop games (simulation, management, strategy)

### Key Features
- **AI-Friendly**: Optimized for BMAD, SuperClaude, Claude Code workflows
- **Quality Gates**: Coverage (≥90%), Performance (P95≤20ms), Security baseline
- **Testable Architecture**: Ports & Adapters + 80% xUnit + 15% GdUnit4
- **Complete Stack**: Godot 4.5, C# .NET 8, xUnit, GdUnit4, godot-sqlite, Sentry

**Full technical details**: See `CLAUDE.md`

---

## 3‑Minute From Zero to Export（3 分钟从 0 到导出）

1) 安装 Godot .NET（mono）并设置环境：
   - `setx GODOT_BIN C:\Godot\Godot_v4.5.1-stable_mono_win64.exe`
2) 运行最小测试与冒烟（可选示例）：
   - `./scripts/test.ps1 -GodotBin "$env:GODOT_BIN"`（默认不含示例；`-IncludeDemo` 可启用）
   - `./scripts/ci/smoke_headless.ps1 -GodotBin "$env:GODOT_BIN"`
3) 在 Godot Editor 安装 Export Templates（Windows Desktop）。
4) 导出与运行 EXE：
   - `./scripts/ci/export_windows.ps1 -GodotBin "$env:GODOT_BIN" -Output build\Game.exe`
   - `./scripts/ci/smoke_exe.ps1 -ExePath build\Game.exe`

One‑liner（已在 Editor 安装 Export Templates 后）：
- PowerShell：`$env:GODOT_BIN='C:\\Godot\\Godot_v4.5.1-stable_mono_win64.exe'; ./scripts/ci/export_windows.ps1 -GodotBin "$env:GODOT_BIN" -Output build\Game.exe; ./scripts/ci/smoke_exe.ps1 -ExePath build\Game.exe`

## What You Get（模板内容）
- 适配层 Autoload：EventBus/DataStore/Logger/Audio/Time/Input/SqlDb
- 场景分层：ScreenRoot + Overlays；ScreenNavigator（淡入淡出 + Enter/Exit 钩子）
- 安全基线：仅允许 `res://`/`user://` 读取，启动审计 JSONL，HTTP 验证示例
- 可观测性：本地 JSONL（Security/Sentry 占位），性能指标（[PERF] + perf.json）
- 测试体系：xUnit + GdUnit4（示例默认关闭），一键脚本
- 导出与冒烟：Windows-only 脚本与文档

## Delivery Profiles
- `DELIVERY_PROFILE=playable-ea`：最快的可玩性校验档位；覆盖率、语义审查、验收硬门尽量止损，安全默认派生到 `host-safe`。
- `DELIVERY_PROFILE=fast-ship`：模板默认档位；保留基本主机安全、核心测试和发版前的必要约束，适合日常开发。
- `DELIVERY_PROFILE=standard`：收口档位；ADR、验收、语义门禁更严格，安全默认派生到 `strict`。
- 生效优先级：CLI `--delivery-profile` > 环境变量 `DELIVERY_PROFILE` > 仓库默认 `fast-ship`。
- CI 工作流 `windows-quality-gate.yml` / `ci-windows.yml` 已接入 `delivery_profile` 输入，并会在 Step Summary 固化 `DeliveryProfile:` 与 `SecurityProfile:`。
- `prototype lane` 是探索通道，不是新的 `DELIVERY_PROFILE`；它只决定工作是否进入正式任务流，不替代正式交付门禁。

## Quick Links

### Daily Ops
- Daily Workflow: `workflow.md`
- Bootstrap Workflow Example: `workflow.example.md`
- Chapter 6 T56 Optimization Guide: `docs/workflows/chapter-6-t56-optimization-guide.md`
- Chapter 7 UI Wiring GDD: `docs/gdd/ui-gdd-flow.md`
- Chapter 7 Profile: `docs/workflows/chapter7-profile.json` (minimal seed: `docs/workflows/templates/chapter7-profile.minimal.example.json`)
- Chapter 7 Profile Guide: `docs/workflows/chapter7-profile-guide.md`
- Phase A Public Endpoint: `http://47.86.160.138:8080`
- Stable Public Entrypoints: `docs/workflows/stable-public-entrypoints.md`
- Delivery Profile 说明：`DELIVERY_PROFILE.md`
- Session Recovery: `docs/agents/01-session-recovery.md`
- Persistent Harness: `docs/agents/03-persistent-harness.md`
- Local Hard Checks: `docs/workflows/local-hard-checks.md`
- Project Health Dashboard: `docs/workflows/project-health-dashboard.md`
- Unified Technical Debt Register: `docs/technical-debt.md`

### Migration / Template Upgrade
- Template Bootstrap Checklist: `docs/workflows/template-bootstrap-checklist.md`
- Template Upgrade Protocol: `docs/workflows/template-upgrade-protocol.md`
- Workflow Rule Feedback Protocol: `docs/workflows/workflow-rule-feedback-protocol.md`
- Workflow Rule Feedback Template: `docs/workflows/templates/workflow-rule-feedback-template.md`
- Cloud Platform Evolution Plan: `docs/workflows/cloud-platform-evolution-plan.md`
- Business Repo Upgrade Guide: `docs/workflows/business-repo-upgrade-guide.md`
- Prototype Lane: `docs/workflows/prototype-lane.md`
- Prototype Lane Playbook: `docs/workflows/prototype-lane-playbook.md`
- Prototype TDD: `docs/workflows/prototype-tdd.md`
- Overlay Generation Quickstart: `docs/workflows/overlay-generation-quickstart.md`
- Overlay Generation SOP: `docs/workflows/overlay-generation-sop.md`
- Overlay Authoring Guide: `docs/workflows/overlays-authoring-guide.md`
- Godot+C# 快速开始（godotgame 项目）：`docs/TEMPLATE_GODOT_GETTING_STARTED.md`
- Windows-only 快速指引：`docs/migration/Phase-17-Windows-Only-Quickstart.md`
- FeatureFlags 快速指引：`docs/migration/Phase-18-Staged-Release-and-Canary-Strategy.md`
- 导出清单：`docs/migration/Phase-17-Export-Checklist.md`
- Headless 冒烟：`docs/migration/Phase-12-Headless-Smoke-Tests.md`
- 场景设计：`docs/migration/Phase-8-Scene-Design.md`
- 测试体系：`docs/migration/Phase-10-Unit-Tests.md`
- 安全基线：`docs/migration/Phase-14-Godot-Security-Baseline.md`
- 手动发布指引：`docs/release/WINDOWS_MANUAL_RELEASE.md`
- Release/Sentry 软门禁与工作流说明：`docs/workflows/GM-NG-T2-playable-guide.md`

## Recovery First

任务在 context reset、跨会话或隔天恢复时，先走恢复链，不要直接重开一轮完整 Chapter 6。

1. 先读：`docs/agents/01-session-recovery.md`
2. 先执行：`py -3 scripts/python/dev_cli.py resume-task --task-id <id>`
3. 只有当 recovery summary 仍然不够时，再执行：`py -3 scripts/python/inspect_run.py --kind pipeline --task-id <id>`

在重开完整 `6.7` 前，至少先看这些信号：

- `Latest reason`
- `Latest run type`
- `Latest reuse mode`
- `Latest artifact integrity`
- `Chapter6 blocked by`
- `recommended_action_why`

如果恢复链已经显示 `planned-only`、`artifact_integrity`、`rerun_guard`、`llm_retry_stop_loss`、`sc_test_retry_stop_loss` 或 `needs-fix-fast`，先按恢复建议做窄修复或回退，不要直接付出一次新的完整重跑成本。

### Deep Reference
- 文档索引：`docs/PROJECT_DOCUMENTATION_INDEX.md`
- Script Entrypoints Index: `docs/workflows/script-entrypoints-index.md`
- Harness Run Protocol: `docs/workflows/run-protocol.md`
- Harness Boundary Matrix: `docs/workflows/harness-boundary-matrix.md`
- Harness Marathon: `docs/agents/06-harness-marathon.md`
- Directory Responsibilities: `docs/agents/16-directory-responsibilities.md`
- AGENTS 构建原则：`docs/agents/11-agents-construction-principles.md`
- Actions 快速链路验证（Dry Run）：`.github/workflows/windows-smoke-dry-run.yml`
## Task / ADR / PRD 工具

README 只保留稳定公共入口摘要，不再在这里维护长脚本清单。

- 日常推荐入口：`docs/workflows/stable-public-entrypoints.md`
- 全量工作流入口、依赖、参数扫描：`docs/workflows/script-entrypoints-index.md`

稳定公共入口按用途分为 3 组：

1. 仓库 bootstrap / 恢复
- `py -3 scripts/python/dev_cli.py run-local-hard-checks`
- `py -3 scripts/python/dev_cli.py project-health-scan`
- `py -3 scripts/python/dev_cli.py serve-project-health`
- `py -3 scripts/python/dev_cli.py resume-task --task-id <id>`
- `py -3 scripts/python/dev_cli.py run-prototype-tdd --slug <slug> --stage <red|green|refactor> ...`
- `py -3 scripts/python/dev_cli.py run-prototype-workflow --prototype-file docs/prototypes/<your-file>.md`
- `py -3 scripts/python/dev_cli.py inspect-run --kind <kind> [--task-id <id>]`
- `py -3 scripts/python/dev_cli.py chapter6-route --task-id <id> --recommendation-only`
- `py -3 scripts/python/dev_cli.py run-single-task-chapter6 --task-id <id> --godot-bin "$env:GODOT_BIN" --delivery-profile <profile>`
- `py -3 scripts/python/dev_cli.py run-chapter7-ui-wiring --delivery-profile <profile>`

2. 任务交付主环
- `py -3 scripts/sc/run_review_pipeline.py --task-id <id> --godot-bin "$env:GODOT_BIN" --delivery-profile <profile>`
- `py -3 scripts/sc/llm_generate_tests_from_acceptance_refs.py --task-id <id> --tdd-stage red-first --verify <mode>`
- `py -3 scripts/sc/check_tdd_execution_plan.py --task-id <id> --tdd-stage red-first --verify auto --execution-plan-policy <mode>`
- `py -3 scripts/sc/build.py tdd --stage <red|green|refactor>`

3. 任务元数据 / 架构一致性
- `py -3 scripts/python/task_links_validate.py`
- `py -3 scripts/python/check_tasks_all_refs.py`
- `py -3 scripts/python/validate_task_master_triplet.py`
- `py -3 scripts/python/validate_contracts.py`
- `py -3 scripts/python/check_domain_contracts.py`
- `py -3 scripts/python/sync_task_overlay_refs.py --prd-id <PRD-ID> --write`
- `py -3 scripts/sc/llm_generate_overlays_batch.py ...`

止损规则：
- 不要再把一次性迁移、兄弟仓同步、编码修复、文档清洗脚本堆到 README 首页。
- 如果某个脚本不在上面的稳定公共入口里，先去 `stable-public-entrypoints.md` 或 `script-entrypoints-index.md` 查，不要凭印象直接运行。

## New project task-gate alignment

When you copy this template to create a new project, enable task-scoped gates after real Taskmaster files are ready:

1) Prepare triplet files:
- `.taskmaster/tasks/tasks.json`
- `.taskmaster/tasks/tasks_back.json`
- `.taskmaster/tasks/tasks_gameplay.json`

2) Pick one delivery profile and let scripts derive the default security posture:
- Playable EA posture:
  - `py -3 scripts/sc/run_review_pipeline.py --task-id <id> --godot-bin "$env:GODOT_BIN" --delivery-profile playable-ea --skip-llm-review`
- Fast ship posture (template default):
  - `py -3 scripts/sc/run_review_pipeline.py --task-id <id> --godot-bin "$env:GODOT_BIN" --delivery-profile fast-ship --skip-llm-review`
- Standard posture (release tightening):
  - `py -3 scripts/sc/run_review_pipeline.py --task-id <id> --godot-bin "$env:GODOT_BIN" --delivery-profile standard --skip-llm-review`
- Remove `--skip-llm-review` only when you intentionally want the advisory LLM review stage as part of the unified pipeline.
- Only pass `--security-profile` when you intentionally need to break the default mapping.
- Optional per-task review hint: add `semantic_review_tier` to `tasks_back.json` / `tasks_gameplay.json` with `auto | minimal | targeted | full`; this only changes `sc-llm-review`, not deterministic gates.
- Stop-loss escalation still applies: `P1` tasks escalate to at least `targeted`; `P0`, contract/security/workflow/CI/release/ADR/architecture/performance-heavy tasks escalate to `full`.
- `P0/P1` review findings stay in the must-fix path; `P2/P3/P4` are synced into `docs/technical-debt.md` after a successful `sc-llm-review`.

3) Keep profile observability in CI:
- Step Summary should contain both `DeliveryProfile: <playable-ea|fast-ship|standard>` and `SecurityProfile: <host-safe|strict>`.
- LLM scripts are diagnostic only and do not replace hard gates.

4) Initialize `overlay_task_drift` only after real Taskmaster triplet files exist:
- `py -3 scripts/python/remind_overlay_task_drift.py --write --overlay-index docs/architecture/overlays/PRD-Guild-Manager/08/_index.md`
- Do not run `--write` in the bare template state; otherwise the baseline only records missing task files.

<!-- END:NEW_PROJECT_SANGUO_ALIGNMENT -->

## Notes
- DB 后端：默认插件优先；`GODOT_DB_BACKEND=plugin|managed` 可控。
- 示例 UI/测试：默认关闭；设置 `TEMPLATE_DEMO=1` 启用（Examples/**）。

## Feature Flags（特性旗标）
- Autoload：`/root/FeatureFlags`（文件：`Game.Godot/Scripts/Config/FeatureFlags.cs`）
- 环境变量优先生效：
  - 单项：`setx FEATURE_demo_screens 1`
  - 多项：`setx GAME_FEATURES "demo_screens,perf_overlay"`
- 文件配置：`user://config/features.json`（示例：`{"demo_screens": true}`）
- 代码示例：`if (FeatureFlags.IsEnabled("demo_screens")) { /* ... */ }`

## 如何发版（打 tag）
- 确认主分支已包含所需变更：`git status && git push`
- 创建版本标签：`git tag v0.1.1 -m "v0.1.1 release"`
- 推送标签触发发布：`git push origin v0.1.1`
- 工作流：`Windows Release (Tag)` 自动导出并将 `build/Game.exe` 附加到 GitHub Release。
- 如需手动导出：运行 `Windows Release (Manual)` 或 `Windows Export Slim`。

## 自定义应用元数据（图标/公司/描述）
- 文件：`export_presets.cfg` → `[preset.0.options]` 段。
- 关键字段：
  - `application/product_name`（产品名），`application/company_name`（公司名）
  - `application/file_description`（文件描述），`application/*_version`（版本）
  - 图标：`application/icon`（推荐 ICO：`res://icon.ico`；当前为 `res://icon.svg`）
- 修改后，运行 `Windows Export Slim` 或 `Windows Release (Manual)` 验证导出产物。
## Game Project Metadata
- Game Name: TBD
- Game Type: TBD
- Game Type Source: TBD
- Game Type Guide: TBD
