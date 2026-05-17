# Repository Guide

This file is the repository map. It routes you to the right source document by task stage, problem type, and durable run state. Do not turn it back into a 600-line encyclopedia.

## Purpose
- Windows-only Godot + C# game template.
- `AGENTS.md` is the routing layer.
- `README.md` is the project-facing overview and startup entry.
- `docs/agents/` holds agent workflow, recovery, and navigation docs.
- `docs/architecture/**`, `docs/adr/**`, `docs/testing-framework.md`, and `DELIVERY_PROFILE.md` remain the deep source documents.

## Start Here

1. [Agents Docs Index](docs/agents/00-index.md)
2. [Session Recovery](docs/agents/01-session-recovery.md)
3. [RAG Sources And Session SSoT](docs/agents/13-rag-sources-and-session-ssot.md)
4. [Repo Map](docs/agents/02-repo-map.md)
5. [README](README.md)
6. If a task-scoped run already exists, `logs/ci/active-tasks/task-<id>.active.md`
7. Newest file in `execution-plans/`
8. Newest file in `decision-logs/`
9. If a local review pipeline already ran, `logs/ci/<date>/sc-review-pipeline-task-<task>/latest.json`


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

## Phase A Runtime Ops
- Stable local app bind for the live Phase A console is `http://127.0.0.1:18080`.
- Stable public reverse-proxy entry is `http://47.250.131.70:8080`.
- Canonical Phase A runtime config file is `runtime/phase-a/start-phasea.ps1`.
- Canonical Caddy config file is `runtime/phase-a/Caddyfile`.
- Important runtime configuration files must not live under `log/` or `logs/`. Logs stay under `logs/`; checked-in startup/config files stay under a stable source directory such as `runtime/phase-a/`.
- Caddy must listen on `0.0.0.0:8080` and reverse proxy to `127.0.0.1:18080`.
- Do not run Phase A with `dotnet run` against the default repo `obj/bin` paths for the live server. Use the checked-in startup script.
- The startup script must keep build outputs outside the repo source tree. Current stable build root is `C:\Users\Administrator\.codex\memories\phasea-runtime-build`.
- The startup script must explicitly set both `APP_BIND_URL` and `ASPNETCORE_URLS` to `http://127.0.0.1:18080` before starting `PhaseA.Platform.exe`.
- Repo-wide MSBuild default item excludes must keep generated `logs/**`, `obj/**`, and `bin/**` content out of compile inputs. This prevents duplicate assembly attribute failures during live server recovery.
- Recovery order when public `502` appears:
  - Verify `PhaseA.Platform` health on `127.0.0.1:18080` first.
  - Only after the app is healthy should `caddy` on `8080` be restarted or validated.
  - If the app fails to start, inspect bind-port conflicts and build-path contamination before touching Caddy again.

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
- Keep `AGENTS.md` as a routing map, not a duplicate rules catalog.
- Put detailed guidance into `docs/agents/`, `README.md`, or the relevant source doc.
- Put durable intent in git-tracked markdown under `execution-plans/` and `decision-logs/`.
- Store durable business-repo workflow rule feedback under `decision-logs/workflow-rule-feedback/`.
- Put high-frequency evidence in `logs/`.
