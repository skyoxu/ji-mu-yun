# Repository Guide

This file is the repository map. It routes you to the right source document by task stage, problem type, and durable run state. Do not turn it back into a 600-line encyclopedia.

## Purpose
- Windows-only Godot + C# game template evolved into the Ji Mu Yun Phase A/B cloud prototype generation and hosting platform.
- `AGENTS.md` is the routing layer.
- `README.md` is the product-facing overview, phase status, stack summary, and startup entry.
- `docs/agents/` holds agent workflow, recovery, and navigation docs.
- `docs/architecture/**`, `docs/adr/**`, `docs/testing-framework.md`, and `DELIVERY_PROFILE.md` remain the deep source documents.

## Phase Service Scope
This AGENTS.md prioritizes Phase A/B platform service work before broader template or delivery-routing concerns. Treat the following as in-scope for Phase service changes:
- `PhaseA.Platform/**` and `PhaseA.Platform.Tests/**`.
- `runtime/phase-a/**`, including startup, recovery, watchdog, and Caddy configuration.
- `scripts/python/phase_a_*.py`, `scripts/python/phase_b_*.py`, and Phase-facing smoke or drill scripts.
- `logs/phase-a-innernet/**` as runtime state, live metadata, hosted workspaces, and evidence.
- Account isolation, admin/user auth, token hashing, audit exports, hosted workspace/artifact readback, and browser/API behavior.
- Phase browser-consumed prototype routes, including prototype creation, iteration, repair, GDD, asset, package, preview, and related route recovery state.
- Shared LLM/Codex execution entrypoints used by Phase routes and scripts.

## Start Here

1. For Phase service work, read `Phase Service Scope`, `Phase Service Change Contract`, and `Phase Runtime Recovery Order` in this file before editing.
2. [Agents Docs Index](docs/agents/00-index.md)
3. [Session Recovery](docs/agents/01-session-recovery.md)
4. [RAG Sources And Session SSoT](docs/agents/13-rag-sources-and-session-ssot.md)
5. [Repo Map](docs/agents/02-repo-map.md)
6. [README](README.md)
7. If a task-scoped run already exists, `logs/ci/active-tasks/task-<id>.active.md`
8. Newest file in `execution-plans/`
9. Newest file in `decision-logs/`
10. If a local review pipeline already ran, `logs/ci/<date>/sc-review-pipeline-task-<task>/latest.json`


## Game Project Metadata
- Game Name: TBD
- Game Type: TBD
- Game Type Source: TBD
- Game Type Guide: TBD

## Task Navigation
- New session or resume failed work:
  - [RAG Sources And Session SSoT](docs/agents/13-rag-sources-and-session-ssot.md)
  - [Session Recovery](docs/agents/01-session-recovery.md)
  - `logs/ci/active-tasks/task-<id>.active.md` for the shortest local recovery summary when it exists
  - `py -3 scripts/python/dev_cli.py resume-task --task-id <id>` when a task-scoped local run already exists
  - `py -3 scripts/python/dev_cli.py chapter6-route --task-id <id> --recommendation-only` before paying for another `6.7` or `6.8`
  - `py -3 scripts/python/dev_cli.py inspect-run --kind pipeline --task-id <id>` when resume and route are still not enough
  - [Persistent Harness](docs/agents/03-persistent-harness.md)
  - [Harness Run Protocol](docs/workflows/run-protocol.md)
  - [Harness Boundary Matrix](docs/workflows/harness-boundary-matrix.md)
  - [Agent-to-Agent Review](docs/agents/07-agent-to-agent-review.md)
- Check repo readiness or view the live local dashboard:
  - [Project Health Dashboard](docs/workflows/project-health-dashboard.md)
  - `py -3 scripts/python/dev_cli.py project-health-scan`
  - `logs/ci/project-health/latest.html`
- Understand the project, startup path, or stack:
  - [Startup, Stack, And Template Structure](docs/agents/14-startup-stack-and-template-structure.md)
  - [README](README.md)
  - [Project Documentation Index](docs/PROJECT_DOCUMENTATION_INDEX.md)
- Implement a feature or touch architecture:
  - [ADR Index](docs/architecture/ADR_INDEX_GODOT.md)
  - [Architecture Guardrails](docs/agents/05-architecture-guardrails.md)
  - [Execution Rules](docs/agents/12-execution-rules.md)
  - `docs/architecture/base/00-README.md`
  - [Template Customization](docs/agents/10-template-customization.md)
- Write tests, acceptance, or quality gates:
  - [Testing Framework](docs/testing-framework.md)
  - [Closed-Loop Testing](docs/agents/04-closed-loop-testing.md)
  - [Quality Gates And DoD](docs/agents/09-quality-gates-and-done.md)
  - `scripts/sc/README.md`
- Run or repair the local harness and reviews:
  - [Persistent Harness](docs/agents/03-persistent-harness.md)
  - [Harness Run Protocol](docs/workflows/run-protocol.md)
  - [Agent-to-Agent Review](docs/agents/07-agent-to-agent-review.md)
  - [DELIVERY_PROFILE](DELIVERY_PROFILE.md)
  - `scripts/sc/README.md`
- Tighten release or CI posture:
  - [Security, Release Health, And Runtime Ops Rules](docs/agents/15-security-release-health-and-runtime-ops.md)
- [Template Upgrade Protocol](docs/workflows/template-upgrade-protocol.md)
- [Workflow Rule Feedback Protocol](docs/workflows/workflow-rule-feedback-protocol.md)
- [Prototype Lane](docs/workflows/prototype-lane.md)
- [Prototype Lane Playbook](docs/workflows/prototype-lane-playbook.md)
- [Prototype TDD](docs/workflows/prototype-tdd.md)
- [Chapter 7 UI Wiring GDD](docs/gdd/ui-gdd-flow.md)
- [Chapter 7 Profile Guide](docs/workflows/chapter7-profile-guide.md)
- [Prototype Workspace](docs/prototypes/README.md)
  - [Quality Gates And DoD](docs/agents/09-quality-gates-and-done.md)
  - [DELIVERY_PROFILE](DELIVERY_PROFILE.md)
  - `docs/workflows/`
- Copy this template into a new project:
  - [Template Customization](docs/agents/10-template-customization.md)
  - [Template Bootstrap Checklist](docs/workflows/template-bootstrap-checklist.md)
  - [README](README.md)
  - [DELIVERY_PROFILE](DELIVERY_PROFILE.md)

## Problem Navigation
- Need project background, use cases, startup, or stack:
  - [Startup, Stack, And Template Structure](docs/agents/14-startup-stack-and-template-structure.md)
  - [README](README.md)
- Need repository directories or entry files:
  - [Repo Map](docs/agents/02-repo-map.md)
  - [Directory Responsibilities](docs/agents/16-directory-responsibilities.md)
  - [Project Documentation Index](docs/PROJECT_DOCUMENTATION_INDEX.md)
- Need ADR, Base, Overlay, or contract placement rules:
  - [ADR Index](docs/architecture/ADR_INDEX_GODOT.md)
  - [Architecture Guardrails](docs/agents/05-architecture-guardrails.md)
  - [Template Customization](docs/agents/10-template-customization.md)
- Need security posture, release health, logs, or runtime ops rules:
  - [Security, Release Health, And Runtime Ops Rules](docs/agents/15-security-release-health-and-runtime-ops.md)
- [Template Upgrade Protocol](docs/workflows/template-upgrade-protocol.md)
- [Workflow Rule Feedback Protocol](docs/workflows/workflow-rule-feedback-protocol.md)
- [Prototype Lane](docs/workflows/prototype-lane.md)
- [Prototype Lane Playbook](docs/workflows/prototype-lane-playbook.md)
- [Prototype TDD](docs/workflows/prototype-tdd.md)
- Need tests, logs, artifacts, Test-Refs, or DoD:
  - [Testing Framework](docs/testing-framework.md)
  - [Quality Gates And DoD](docs/agents/09-quality-gates-and-done.md)
- Need RAG source discipline, overlay source selection, or session source SSoT:
  - [RAG Sources And Session SSoT](docs/agents/13-rag-sources-and-session-ssot.md)
- Need delivery strictness or profile behavior:
  - [DELIVERY_PROFILE](DELIVERY_PROFILE.md)
  - [Prototype Lane](docs/workflows/prototype-lane.md)
  - [Prototype Workspace](docs/prototypes/README.md)
- Need planning discipline, implementation stop-loss, or script size rules:
  - [Execution Rules](docs/agents/12-execution-rules.md)
- Need AGENTS structure or maintenance rules:
  - [AGENTS Construction Principles](docs/agents/11-agents-construction-principles.md)
  - [Directory Responsibilities](docs/agents/16-directory-responsibilities.md)


## Highest Encoding Rule
- All Chinese text reads and writes must use Python with explicit UTF-8, for example `Path(path).read_text(encoding="utf-8")` and `Path(path).write_text(text, encoding="utf-8", newline="\n")`.
- Do not use PowerShell, `Get-Content`, `Set-Content`, `Out-File`, `Add-Content`, `type`, `echo`, `copy con`, or other Windows-native text tools to read or write Chinese text.
- If a command script must contain Chinese literals, write it as a Python file or use ASCII-only Python source with Unicode escapes, then write the target file as UTF-8.
- This rule applies to `AGENTS.md`, `README.md`, `workflow.md`, `docs/**/*.md`, `.agents/skills/**/SKILL.md`, prototype records, and project-health documentation.
- Code, tests, logs, and machine output remain English unless the file is explicitly user-facing documentation.

## Core Rules
- Communicate with the user in Chinese.
- Default environment is Windows.
- Use Windows-compatible commands and paths.
- Read and write docs with Python and UTF-8.
- Do not use PowerShell text pipelines for doc edits.
- Keep code, scripts, tests, comments, and printed messages in English.
- Do not use emoji.
- Write logs and evidence under `logs/`.
- Do not revert user changes unless explicitly requested.
- Prefer small, deterministic, testable changes.
- Code or test changes should cite at least one accepted ADR; if thresholds, contracts, security posture, or release policy change, update or supersede the ADR set.

- Route architecture work in arc42 order: irreversible decisions -> cross-cutting rules -> runtime backbone -> feature slices.
- For overlay work, prefer generated shard or index sources when present; otherwise use the current repo indexes and do not blind-scan `docs/`.
- Ask before high-risk actions and never disable tests to get green.

## Phase Service Change Contract

### Change Matrix
| Change area | Must update | Required validation |
| --- | --- | --- |
| Platform API | Server handler/DTO, browser caller, auth boundary, and public behavior docs when behavior changes. | `PhaseA.Platform.Tests/**` plus relevant `phase_a_*` or `phase_b_*` smoke. |
| Metadata DB or persistence | Migration or recovery path, persistence tests, restore/drill docs, and runtime notes when DB paths or ownership change. | DB/persistence test, restore drill, or smoke evidence under `logs/`. |
| Auth, token, account isolation, audit | Token hashing path, admin/user boundary behavior, audit output, and CSV/export callers. | Unauthorized and authorized checks, preferably `scripts/python/phase_b_account_smoke.py`. |
| Runtime startup or watchdog | `runtime/phase-a/start-phasea.ps1`, `ensure-phasea.ps1`, `watch-phasea.ps1`, and runtime docs. | Local `/healthz`, `scripts/python/phase_a_ops_check.py`, and runtime log evidence. |
| Caddy or public proxy | `runtime/phase-a/Caddyfile`, public URL docs, and recovery notes. | Validate local PhaseA health first, then public `:8080/healthz`. |
| Hosted workspace, artifacts, packages, previews | Workspace boundary, artifact readback, cleanup/recovery behavior, and browser caller. | Integration or smoke evidence under `logs/`. |
| Phase prototype routes | Route recovery inputs, latest state, repair ledger behavior, acceptance evidence, and browser-safe output. | Route-specific smoke/acceptance evidence and no completion based only on assistant text. |
| LLM/Codex route execution | Shared route engine, command factory, script backend, and caller tests. | `CodexHostedProcessCommandFactoryTests`, `LlmRouteEngineTests`, `scripts/sc/tests/test_llm_backend.py`, plus route-specific tests. |

### Protected Phase Paths
Ask before modifying:
- Live metadata or runtime state under `logs/phase-a-innernet/data/**` and hosted workspaces under `logs/phase-a-innernet/workspaces/**`.
- `runtime/phase-a/start-phasea.ps1`, `runtime/phase-a/ensure-phasea.ps1`, `runtime/phase-a/watch-phasea.ps1`, and `runtime/phase-a/Caddyfile`.
- Auth, token hashing, account isolation, and audit code in `PhaseA.Platform/**`.
- Shared LLM/Codex execution entrypoints: `PhaseA.Platform/Llm/LlmRouteEngine.cs`, `PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs`, and `scripts/sc/_llm_backend.py`.
- Delivery/security profile behavior, public deployment URLs, bind addresses, secret source-of-truth, or Caddy listener behavior.
- Generated logs, runtime evidence, and failure artifacts when the intent is to rewrite or delete history instead of adding sidecar evidence.

### Definition of Done
A Phase service change is not done until:
- Local behavior is validated, or the validation gap and required follow-up evidence are recorded.
- API, auth, DB, runtime, Caddy, prototype-route, or LLM execution changes include targeted tests or smoke evidence.
- Evidence is written under `logs/` when a run, smoke, drill, or recovery action occurs.
- Live secrets and token material are not committed to git-tracked docs, scripts, config, logs, or test fixtures.
- Public proxy issues are debugged in order: local PhaseA health first, then Caddy/public health.
- Failures are preserved as evidence; add new sidecar files instead of rewriting generated history.

### Database and API Compatibility
- Do not manually mutate the live Phase A metadata DB unless the user explicitly authorizes it.
- Schema changes must be backward-compatible by default, include a migration or recovery path, and preserve existing data unless an approved decision log says otherwise.
- Public and browser-consumed APIs must remain backward-compatible by default. Do not remove or rename routes, fields, status codes, auth behavior, or artifact paths without explicit approval and a documented compatibility plan.

### Prototype Route Recovery
Phase service browser flows use prototype routes. For file-changing hosted game-project routes, consume the project-level recovery sources in authority order before editing:
1. Parsed game-type route profile and selected route skill prompt block.
2. `meta/project-execution-guide.md`.
3. `routes/prototype-contract/latest.json`.
4. Current route latest state, such as `meta/routes/prototype/latest.json`, `meta/routes/iteration-plan/latest.json`, or `meta/routes/execute-next-goal/latest.json`.
5. Current goal, step, repair step, or session state.
6. Repair ledger and failing acceptance or Godot diagnostic evidence for repair routes.
7. Latest live platform acceptance blocker, which wins over old assistant summaries, route state, and repair ledger memory.

Missing required recovery sources must fail closed. Route state and repair ledger are continuity memory, not current acceptance authority. Do not mark steps complete based only on assistant text.

## Template Reality Checks
- Legacy references such as `architecture_base.index`, `prd_chunks.index`, `shards/flattened-*.xml`, and `tasks/tasks.json` may not exist in this template.
- Current equivalents are routed by `docs/agents/13-rag-sources-and-session-ssot.md`.
- In the bare template, use `docs/PROJECT_DOCUMENTATION_INDEX.md`, `docs/architecture/base/00-README.md`, `docs/architecture/ADR_INDEX_GODOT.md`, and `docs/prd/**/*.md` first.
- Use `.taskmaster/tasks/*.json` only after the copied project has generated real triplet files.

## Hard Architecture Invariants
- Base chapter 08 stays a template only; concrete feature slices belong in `docs/architecture/overlays/<PRD-ID>/08/`.
- Overlay text should reference base chapters and ADRs instead of copying thresholds or policy text.
- Contracts stay in `Game.Core/Contracts/**`; do not duplicate contract definitions across docs and code.
- Route architectural change in arc42 order: irreversible decisions -> cross-cutting rules -> runtime backbone -> feature slices.

## Delivery And Security Quick Map
- `DELIVERY_PROFILE=playable-ea` -> default `SECURITY_PROFILE=host-safe`
- `DELIVERY_PROFILE=fast-ship` -> default `SECURITY_PROFILE=host-safe`
- `DELIVERY_PROFILE=standard` -> default `SECURITY_PROFILE=strict`
- CI should emit both `DeliveryProfile: <...>` and `SecurityProfile: <...>` in Step Summary.
- Host boundary rules stay hard in all profiles: `res://` and `user://` only, HTTPS only, `ALLOWED_EXTERNAL_HOSTS`, `GD_OFFLINE_MODE`, no dynamic external code loading.

## LLM Engine And Invocation Protocol Index
- New Phase A routes, services, scripts, and workflow helpers must use the shared LLM/Codex entrypoints below instead of constructing provider calls or `codex exec` commands locally.
- C# structured/read-only LLM calls must use `PhaseA.Platform/Llm/LlmRouteEngine.cs` through `ILlmRouteEngine`. Current callers include chat, draft import/coverage, asset inventory judgement, iteration planning/evaluation, repair-plan generation, and skill-action read-only output.
- C# executable Codex workflows must use `PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs`. This is the only place that should construct executable Codex `HostedProcessCommand` arguments, resolve `PHASEA_CODEX_COMMAND`, set `PHASEA_CODEX_DEFAULT_MODEL` / `PHASEA_CODEX_REASONING_EFFORT`, choose `read-only` vs `workspace-write`, and attach stdin prompts.
- Python LLM/Codex scripts must use `scripts/sc/_llm_backend.py::run_llm_exec` or a thin wrapper that delegates to it. This includes `scripts/python/run_prototype_workflow.py` and `scripts/sc/**` LLM helpers.
- Prompt transport protocol is stdin-first: use `codex exec ... -` with UTF-8 stdin, never append large prompts as command-line arguments. For output, use the shared helper options for `--output-last-message` or `-o`.
- Pure analysis or JSON-only decisions should remain read-only and schema/JSON parsed through the route engine or script backend. File-changing workflows must stay on explicit executable routes with `workspace-write` and existing acceptance/smoke validation.
- If a new route needs model, reasoning effort, sandbox, output path, billing, credential, or retry behavior that the shared entrypoint cannot express, extend the shared entrypoint and its tests first; do not fork local subprocess logic.
- Required regression coverage for protocol changes: `PhaseA.Platform.Tests/Runs/CodexHostedProcessCommandFactoryTests.cs`, `PhaseA.Platform.Tests/Llm/LlmRouteEngineTests.cs`, `scripts/sc/tests/test_llm_backend.py`, and the route-specific tests for the caller being changed.

## Phase Runtime Recovery Order
1. Check `http://127.0.0.1:18080/healthz`.
2. If local app health is unhealthy, run `runtime/phase-a/ensure-phasea.ps1`.
3. If local app health is healthy but public `:8080` health is unhealthy, inspect or restart Caddy after the app is healthy.
4. Do not use ordinary `dotnet run` for the live server. Use `runtime/phase-a/start-phasea.ps1`.
5. Do not manually edit the live metadata DB.
6. Record recovery evidence under `logs/phase-a-innernet/runtime/`.

## Phase A Runtime Ops
- Stable local app bind for the live Phase A console is `http://127.0.0.1:18080`.
- Stable public reverse-proxy entry is `http://47.86.160.138:8080`.
- Canonical Phase A runtime config file is `runtime/phase-a/start-phasea.ps1`.
- Canonical Caddy config file is `runtime/phase-a/Caddyfile`.
- Important runtime configuration files must not live under `log/` or `logs/`. Logs stay under `logs/`; checked-in startup/config files stay under a stable source directory such as `runtime/phase-a/`.
- Caddy must listen on `0.0.0.0:8080` and reverse proxy to `127.0.0.1:18080`.
- Do not run Phase A with `dotnet run` against the default repo `obj/bin` paths for the live server. Use the checked-in startup script.
- The startup script must keep build outputs outside the repo source tree. Current stable build root is `C:\Users\Administrator\.codex\memories\phasea-runtime-build`.
- The startup script must explicitly set both `APP_BIND_URL` and `ASPNETCORE_URLS` to `http://127.0.0.1:18080` before starting `PhaseA.Platform.exe`.
- Repo-wide MSBuild default item excludes must keep generated `logs/**`, `obj/**`, and `bin/**` content out of compile inputs. This prevents duplicate assembly attribute failures during live server recovery.
- Recovery-grade runtime variable map for the live server:
  - `APP_BIND_URL=http://127.0.0.1:18080`
  - `ASPNETCORE_URLS=http://127.0.0.1:18080`
  - `HTTPS_TERMINATION=caddy`
  - `PUBLIC_BASE_URL=https://47.86.160.138:8080`
  - `HOSTED_WORKSPACE_ROOT=C:\jimuyun\logs\phase-a-innernet\workspaces`
  - `HOSTED_PROJECT_LIMIT=2`
  - `PHASEA_MAX_CONCURRENT_CHATS=8`
  - `PHASEA_MAX_CONCURRENT_CHATS_PER_ACCOUNT=2`
  - `PHASEA_MAX_CONCURRENT_GDD_QUESTION_FORMS=4`
  - `PHASEA_MAX_CONCURRENT_GDD_QUESTION_FORMS_PER_ACCOUNT=1`
  - `PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS=3`
  - `PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS_PER_ACCOUNT=1`
  - `PHASEA_MAX_CONCURRENT_OTHER_RUNS=1`
  - `PHASEA_METADATA_DB_PATH=C:\jimuyun\logs\phase-a-innernet\data\phase-a-platform.sqlite3`
  - `PHASEA_REPOSITORY_ROOT=C:\jimuyun`
  - `PHASEA_CODEX_COMMAND=C:\Windows\System32\config\systemprofile\AppData\Roaming\npm\codex.cmd`
  - `GODOT_BIN=C:\Godot\4.5.1-mono\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe`
- Sensitive runtime variables must not store real values in git-tracked docs:
  - `PHASEA_ADMIN_TOKEN_HASH`: required for live auth; load from the host secret store or service environment only; never commit the real value into `AGENTS.md`, `README.md`, scripts, or workflow docs.
  - If future user/admin token hashes are added, document the variable names and source-of-truth only, never the real hash values.
- Recovery order when public `502` appears:
  - Verify `PhaseA.Platform` health on `127.0.0.1:18080` first.
  - Only after the app is healthy should `caddy` on `8080` be restarted or validated.
  - If the app fails to start, inspect bind-port conflicts and build-path contamination before touching Caddy again.
- Phase A local self-recovery scripts:
  - `runtime/phase-a/ensure-phasea.ps1`: one-shot health check and restart recovery for `127.0.0.1:18080` and public `8080`.
  - `runtime/phase-a/watch-phasea.ps1`: background watchdog loop that runs `ensure-phasea.ps1` every 30 seconds and writes runtime evidence under `logs/phase-a-innernet/runtime/`.
  - Watchdog pid file: `logs/phase-a-innernet/phasea-watchdog.pid`
  - Watchdog log: `logs/phase-a-innernet/runtime/phasea-watchdog.log`

## Repo Map
- Detailed per-directory responsibilities and stop-loss rules: [Directory Responsibilities](docs/agents/16-directory-responsibilities.md)
- `Game.Core/`: pure C# domain logic and contract-adjacent code.
- `Game.Core.Tests/`: xUnit tests for core logic.
- `Game.Godot/`: shipped Godot runtime project and real runtime assets.
- `Tests.Godot/`: Godot-side tests and headless evidence.
- `docs/`: project, architecture, workflow, testing, and agents docs.
- `scripts/sc/`: task-facing orchestration, review pipeline, and recovery-aware automation.
- `scripts/python/`: deterministic validators, gates, sync tools, reporting, and recovery utilities.
- `.github/workflows/`: CI entry points.
- `.taskmaster/`: task triplet data.
- `execution-plans/` and `decision-logs/`: durable intent and decisions.
- `logs/`: runtime, CI, review artifacts, and `active-task` summaries.

## Main Commands
- Full local review: `py -3 scripts/sc/run_review_pipeline.py --task-id <id> --godot-bin "$env:GODOT_BIN"` (auto-writes `agent-review.*` unless `--dry-run`, `--skip-agent-review`, or the active profile sets `agent_review.mode=skip`)
- Task-scoped execution entry: `py -3 scripts/sc/run_review_pipeline.py --task-id <id> --godot-bin "$env:GODOT_BIN"`
- Targeted test / acceptance / review checks are internal pipeline stages behind `run_review_pipeline.py`; do not document them as standalone task-level commands.
- First recovery entry: read `logs/ci/active-tasks/task-<id>.active.md` if present, then run `py -3 scripts/python/dev_cli.py resume-task --task-id <id>` for the full task-scoped summary.
- Before paying for another Chapter 6 rerun, use `py -3 scripts/python/dev_cli.py chapter6-route --task-id <id> --recommendation-only` to decide whether the right lane is `6.7`, `6.8`, residual recording, or inspection-first.
- If deeper inspection is still needed, run `py -3 scripts/python/dev_cli.py inspect-run --kind pipeline --task-id <id>` or inspect `execution-context.json`, `repair-guide.json`, and `agent-review.json` under the task run directory.
- Single-task Chapter 6 orchestrator: `py -3 scripts/python/dev_cli.py run-single-task-chapter6 --task-id <id> --godot-bin "$env:GODOT_BIN" --delivery-profile <profile>`
- Chapter 7 UI wiring orchestrator: `py -3 scripts/python/dev_cli.py run-chapter7-ui-wiring --delivery-profile <profile>`
- Chapter 7 profile guide: `docs/workflows/chapter7-profile-guide.md`
- Prototype-lane TDD entry: `py -3 scripts/python/dev_cli.py run-prototype-tdd --slug <slug> --stage <red|green|refactor> ...`
- Prototype top-level router: `py -3 scripts/python/dev_cli.py run-prototype-workflow --prototype-file docs/prototypes/<your-file>.md`
- Agent-to-agent review rebuild: `py -3 scripts/sc/agent_to_agent_review.py --task-id <id>`

## Recovery Files
- `logs/ci/<date>/sc-review-pipeline-task-<task>-<run_id>/summary.json`
- `logs/ci/<date>/sc-review-pipeline-task-<task>-<run_id>/execution-context.json`
- `logs/ci/<date>/sc-review-pipeline-task-<task>-<run_id>/repair-guide.json`
- `logs/ci/<date>/sc-review-pipeline-task-<task>-<run_id>/repair-guide.md`
- `logs/ci/<date>/sc-review-pipeline-task-<task>-<run_id>/agent-review.json`
- `logs/ci/<date>/sc-review-pipeline-task-<task>-<run_id>/agent-review.md`
- `logs/ci/<date>/sc-review-pipeline-task-<task>-<run_id>/run-events.jsonl`
- `logs/ci/<date>/sc-review-pipeline-task-<task>-<run_id>/harness-capabilities.json`
- `logs/ci/<date>/sc-review-pipeline-task-<task>/latest.json`
- `logs/ci/active-tasks/task-<task>.active.json`
- `logs/ci/active-tasks/task-<task>.active.md`

## Docs Index

- [README](README.md)
- [Project Documentation Index](docs/PROJECT_DOCUMENTATION_INDEX.md)
- [Testing Framework](docs/testing-framework.md)
- [DELIVERY_PROFILE](DELIVERY_PROFILE.md)
- [ADR Index](docs/architecture/ADR_INDEX_GODOT.md)
- [Agents Docs Index](docs/agents/00-index.md)
- [Directory Responsibilities](docs/agents/16-directory-responsibilities.md)
- [Execution Rules](docs/agents/12-execution-rules.md)
- [RAG Sources And Session SSoT](docs/agents/13-rag-sources-and-session-ssot.md)
- [Startup, Stack, And Template Structure](docs/agents/14-startup-stack-and-template-structure.md)
- [Security, Release Health, And Runtime Ops Rules](docs/agents/15-security-release-health-and-runtime-ops.md)
- [Template Upgrade Protocol](docs/workflows/template-upgrade-protocol.md)
- [Workflow Rule Feedback Protocol](docs/workflows/workflow-rule-feedback-protocol.md)
- [Prototype Lane](docs/workflows/prototype-lane.md)
- [Prototype Lane Playbook](docs/workflows/prototype-lane-playbook.md)
- [Prototype TDD](docs/workflows/prototype-tdd.md)

## Change Policy
- Keep `summary.json` schema stable.
- Add new recovery data as sidecar files.
- Keep `AGENTS.md` as a Phase-service-first routing map with concise non-negotiable change contracts, not a duplicate rules catalog.
- Put detailed guidance into `docs/agents/`, `README.md`, or the relevant source doc.
- Put durable intent in git-tracked markdown under `execution-plans/` and `decision-logs/`.
- Store durable business-repo workflow rule feedback under `decision-logs/workflow-rule-feedback/`.
- Put high-frequency evidence in `logs/`.
