# Phase A Prototype Lane Implementation Backlog

- Title: Phase A Prototype Lane Implementation Backlog
- Status: implementation-complete
- Branch: main
- Git Head: 0b20008cb9110c8f74394a438a588c23c1c727ca
- Goal: 将 Phase A Prototype lane 云端平台拆成可实现、可验证、可恢复的小切片，先交付完整 Prototype lane 公网原型闭环，而不是进入 Chapter 3-6 正式交付流水线。
- Scope: 包括 single-admin 登录、项目配额、`godot-prototype-default` 项目规则、单 workspace、Chapter 2 hosted bootstrap、prototype 7day playable hosted route、prototype TDD hosted route、artifact index、new-api 手动绑定、Caddy 部署配置、ASP.NET Core 8 Minimal API 和最小浏览器 UI。不包括 Chapter 3-7 formal delivery、API-driven new-api provisioning、多组织/多角色、分布式 runner、对象存储。
- Current step: Phase A implementation complete; hosted prototype E2E through Day 4 added and passing locally
- Last completed step: Hosted prototype E2E verifies Chapter 2, prototype route, scene command, TDD refactor, and artifact readback through Day 4
- Stop-loss: 不创建 Taskmaster formal tasks；不暴露 Chapter 3-7 UI/API；不允许浏览器输入任意 Git URL；不把 new-api 变成平台 workflow state store；不绕过 repository-native prototype scripts。
- Next action: prepare deployment operations, backup/recovery, and Day 5 Godot/GdUnit enablement before final ECS/Caddy public smoke.
- Recovery command: py -3 scripts/python/validate_recovery_docs.py --dir execution-plans
- Open questions: 1) Caddy 实际域名和证书来源上线前再定；2) 首版 UI 采用静态前端还是 ASP.NET Core Razor/SSR 可在 Slice 6 前决定；3) LLM stop-loss 阈值已默认 `2.00 CNY/run` 与 `20.00 CNY/account/day`，后续可按实测调整。
- Exit criteria: 1) 公网账号可登录；2) 每账号最多 2 个项目；3) 项目由 `godot-prototype-default` 创建且只有一个 workspace；4) Chapter 2 bootstrap 可运行；5) prototype 7day playable route 可运行；6) prototype TDD 可运行并可查看工件；7) new-api 手动绑定可用于 LLM 调用关联；8) Caddy 反代到 ASP.NET Core 服务；9) local checks 和针对性测试通过。
- Related ADRs: ADR-0018, ADR-0019, ADR-0025, ADR-0031
- Related decision logs: decision-logs/2026-05-11-phase-a-prototype-lane-implementation-route.md
- Related task id(s): n/a，因为 Phase A 自举实现明确不进入 Taskmaster / Chapter 3-6 正式任务流。
- Related run id: n/a，因为当前是 implementation backlog，尚未绑定 pipeline run。
- Related latest.json: n/a，因为当前不产生 task-scoped latest.json。
- Related pipeline artifacts: n/a

## Implementation Slices

### Slice 1: Account, Config, And SQLite Foundation

Goal:

- Establish ASP.NET Core 8 Minimal API service skeleton.
- Add SQLite schema for accounts, projects, workspaces, runs, artifacts, runner_locks, project_limits, and account_llm_bindings.
- Add configuration keys for workspace root, project limit, Caddy-facing base URL, LLM gateway, and stop-loss defaults.

Acceptance:

- Single-admin account can be bootstrapped from config or first-run setup.
- `HOSTED_PROJECT_LIMIT=2` is enforced at the service layer.
- SQLite migrations or deterministic schema initialization are repeatable.
- Tests cover config parsing and schema initialization.

### Slice 2: Project Rule And Workspace Foundation

Goal:

- Implement `godot-prototype-default`.
- Create exactly one workspace per project under `HOSTED_WORKSPACE_ROOT`.
- Block arbitrary browser-provided Git URL.

Acceptance:

- Browser/API can create a project from `game_name` and `game_type_source`.
- Admin-controlled rule fills `template_rule_id`, `workspace_root`, `llm_binding_required`, and allowed workflows.
- Project creation fails when account quota is reached.
- Workspace path normalization prevents escaping the configured root.

### Slice 3: Hosted Chapter 2 Bootstrap

Goal:

- Expose a hosted Chapter 2 bootstrap action that delegates to repository-native scripts and skills.
- Capture stdout, stderr, run status, and project-health artifacts.

Acceptance:

- Run record is created with `run_type=chapter2-bootstrap`.
- Project metadata fields are written according to Chapter 2 rules.
- Project-health latest HTML/JSON is indexed.
- Failure returns actionable error and evidence paths.

### Slice 4: Prototype 7-Day Playable Router

Goal:

- Expose `run-prototype-workflow` through a hosted route.
- Preserve Chinese intake prompts and required fields.
- Use `prototype-7day-playable-godot-zh` guidance where applicable.

Acceptance:

- Required fields are tracked: `slug`, `hypothesis`, `core_player_fantasy`, `minimum_playable_loop`, `success_criteria`, `game_feature`, `core_gameplay_loop`, `win_fail_conditions`.
- Active prototype sidecar is discoverable.
- Prototype record and `.prototype.json` sidecar are indexed.
- Chapter 3-7 actions remain unavailable.

### Slice 5: Prototype TDD And Scene Commands

Goal:

- Expose `run-prototype-tdd` and `create-prototype-scene` through hosted commands.
- Enforce project runner lock.
- Capture run logs and TDD outputs.

Acceptance:

- Red/green/refactor commands can be run with explicit user action.
- Godot path uses configured `GODOT_BIN`.
- TDD summaries and reports are indexed.
- Same-project heavy commands are serialized.

### Slice 6: Artifact Index And Browser Readback

Goal:

- Build artifact index for active prototypes, prototype records, `.prototype.json`, TDD summaries, reports, step logs, project-health, execution plans, and decision logs.
- Provide browser pages for project list, prototype intake, run status, artifact view, and project health.

Acceptance:

- Browser can view run status and artifacts without direct filesystem knowledge.
- Artifact summaries link back to authoritative files.
- Log display uses polling first.
- Read-only artifact views work while a runner is active.

### Slice 7: new-api Manual Binding And LLM Audit

Goal:

- Add account-level manual binding to `new-api`.
- Record `llm_gateway`, `llm_request_id`, `llm_model`, and `llm_cost_json` when available.
- Enforce platform-side LLM stop-loss before costly actions.

Acceptance:

- Admin can bind an account to a `new-api` user/token reference.
- Upstream provider keys are never stored in Phase A platform tables.
- Cost stop-loss blocks calls above configured thresholds.
- LLM execution remains an explicit user action and follows existing repository rules.

### Slice 8: Caddy Deployment And Public Hardening

Goal:

- Provide Caddy reverse proxy deployment guidance for `PUBLIC_BASE_URL -> APP_BIND_URL`.
- Lock down ASP.NET Core binding to localhost.
- Record deployment checks.

Acceptance:

- Service binds to `127.0.0.1:8080` by default.
- Caddy handles HTTPS.
- Auth is required before project, workspace, run, artifact, or LLM endpoints.
- Domain and certificate source can remain deployment-time values until public launch.

## Validation Strategy

Per-slice validation:

- Use targeted unit/integration tests first.
- Use fixture workspaces where possible.
- Write evidence under `logs/**`.

Baseline validation:

```powershell
py -3 scripts/python/dev_cli.py run-local-hard-checks-preflight --delivery-profile fast-ship
```

Architecture validation:

```powershell
py -3 scripts/python/validate_overlay_execution.py --prd-id PHASE-A-CLOUD-RUNNER
py -3 scripts/python/validate_recovery_docs.py --dir all
py -3 scripts/python/check_docs_utf8_integrity.py --root docs
```
