---
PRD-ID: PHASE-A-CLOUD-RUNNER
Title: Phase A Cloud Runner Architecture
Arch-Refs: [CH01, CH02, CH03, CH04, CH06, CH07, CH09, CH10, CH11]
ADRs: [ADR-0015, ADR-0018, ADR-0019, ADR-0025, ADR-0031]
Test-Refs: [scripts/python/dev_cli.py, scripts/python/validate_overlay_execution.py, scripts/python/check_docs_utf8_integrity.py]
Status: Draft
Updated: 2026-05-10
---

# Phase A Cloud Runner Architecture

## 1. Architecture Intent

Phase A turns the existing repository-native workflow into a hosted single-node product surface on one Windows ECS machine.

The architecture keeps the repository scripts as the execution authority. The cloud platform owns hosting, workspace lifecycle, process execution, artifact indexing, Web API access, browser presentation, and platform-level metadata.

Clarified Phase A decisions:

- The browser and Web API are public Internet facing, so authentication, HTTPS termination, and request audit are Phase A requirements.
- Account model starts as `single-admin + password/token`; schema may keep account fields, but Phase A does not implement organizations, roles, or invitation flows.
- The prototype server must support multiple projects with a default per-account project limit of `2`.
- Each project has exactly one default workspace in Phase A.
- The workspace root is configurable through `HOSTED_WORKSPACE_ROOT`, with `C:\workspaces` as the default.
- The Web Service should use ASP.NET Core 8 Minimal API for Phase A, serving a static browser UI and running background jobs through an in-process queue.
- Runner concurrency is project-scoped: each project has at most one active heavy runner at a time in Phase A.
- OpenAI/Codex execution is included in Phase A through a replaceable LLM gateway. The recommended Phase A gateway is `new-api` (`QuantumNous/new-api`) for per-account model access, quota, and billing.
- Phase A cloud mode does not expose arbitrary Git URL configuration to browser users and should not depend on user-provided Git remotes.
- Project creation is driven by admin-defined rules and server-side templates/configuration.
- Phase A product scope is the complete Prototype lane, including Chapter 2 repository bootstrap routing and the Chinese 7-day playable Godot prototype router.
- Formal Chapter 3 through Chapter 7 delivery orchestration is out of Phase A scope.
- HTTPS termination uses Caddy in Phase A.
- Platform-side LLM cost stop-loss defaults are `2.00 CNY` per run and `20.00 CNY` per account per day.
- The first admin-defined project creation rule is `godot-prototype-default`.

Authoritative requirement source:

- `execution-plans/2026-05-10-phase-a-cloud-runner-requirements.md`

Authoritative roadmap source:

- `docs/workflows/cloud-platform-evolution-plan.md`

## 2. Governing Decisions And References

This overlay references these accepted decisions:

- `ADR-0018`: Godot 4.5.1 .NET/mono and .NET 8 are the runtime baseline.
- `ADR-0019`: host boundary and Godot security baseline remain hard constraints.
- `ADR-0025`: xUnit, GdUnit4, and `logs/**` evidence remain the test strategy.
- `ADR-0031`: `host-safe` remains the default security profile unless explicitly tightened.
- `ADR-0015`: performance and gate thresholds are referenced from ADRs and workflow docs.

Base chapter alignment:

- CH01: Phase A goals and scope.
- CH02: host-safe security boundaries.
- CH03: platform and repository log evidence.
- CH04: system context and external actors.
- CH06: runtime flows and failure paths.
- CH07: build, checks, and gate execution.
- CH09: single-node capacity constraints.
- CH10: ops and release posture.
- CH11: risks and technical debt.

## 3. Context View

Phase A has five external actor groups:

- Operator: maintains the ECS host, workspace root, environment variables, and service process.
- Authenticated developer user: uses public browser pages to bootstrap projects, define prototypes, run prototype evidence, and inspect artifacts.
- API caller: invokes stable hosted endpoints from automation or agents after authentication.
- Admin rule source: provides allowed project creation rules, templates, and game-type routing constraints.
- LLM Gateway: `new-api` provides OpenAI-compatible model gateway, per-account quota, model routing, and billing.
- Upstream model providers: OpenAI, Claude, Gemini, Qwen, DeepSeek, or other providers configured behind `new-api`.

System boundary:

```text
Public Browser / API caller
        |
        v
HTTPS + Authentication
        |
        v
Phase A Web Service on Windows ECS
        |
        v
Project + Workspace + Runner + Artifact Indexer
        |
        v
Prototype lane scripts, skills, and sidecars
```

The browser observes and triggers. The repository scripts decide.

## 4. Container View

Phase A contains these containers.

### 4.1 Web Service

Responsibilities:

- Serve the browser UI.
- Expose JSON API endpoints.
- Authenticate public requests.
- Enforce HTTPS exposure through a reverse proxy, load balancer, or Kestrel TLS configuration.
- Validate request shape.
- Delegate execution to the Runner.
- Read indexed artifact summaries.
- Apply project quota and per-project runner concurrency rules.

The Web Service must not implement workflow routing decisions.

Recommended stack:

- ASP.NET Core 8 Minimal API for API, static UI hosting, authentication middleware, and background worker integration.
- SQLite through `Microsoft.Data.Sqlite` for Phase A metadata.
- Static browser UI built separately and served by ASP.NET Core, or server-rendered pages if the first UI remains very small.

Rationale:

- Windows service hosting and process management are stable on ECS Windows.
- ASP.NET Core handles medium public concurrency well without introducing a second runtime family for the server.
- Background queues, cancellation tokens, streaming responses, and authentication middleware are mature.
- Repository workflow execution still happens through Python and repository scripts, so the Web Service stack does not absorb workflow authority.

### 4.2 Workspace Manager

Responsibilities:

- Create workspace directories.
- Materialize a project workspace from admin-approved local rules or templates.
- Restore an existing workspace.
- Maintain workspace metadata.
- Enforce workspace root boundaries.

Workspace path:

```text
%HOSTED_WORKSPACE_ROOT%\<tenant>\<project>\<workspace-id>\
```

Default root:

```text
C:\workspaces
```

The earlier roadmap uses `/workspaces/...`; on Windows ECS the concrete path is resolved from `HOSTED_WORKSPACE_ROOT`.

Project quota:

- Phase A supports multiple projects on the prototype server.
- The default active project limit is `2` per account.
- The limit should be configurable as `HOSTED_PROJECT_LIMIT`.
- Project creation must fail closed when the quota is reached.
- Browser users cannot enter arbitrary repository URLs.
- Project source rules are configured by admin-controlled platform rules.

First project creation rule:

```json
{
  "rule_id": "godot-prototype-default",
  "template": "local-template",
  "max_workspaces_per_project": 1,
  "requires_llm_binding": true,
  "allowed_workflows": [
    "chapter2-bootstrap",
    "prototype-7day-playable",
    "prototype-tdd",
    "prototype-scene"
  ],
  "blocked_workflows": [
    "chapter3",
    "chapter4",
    "chapter5",
    "chapter6",
    "chapter7"
  ]
}
```

User-provided project creation fields:

- `game_name`
- `game_type_source`

Admin/rule-controlled fields:

- `project_name`
- `game_type`
- `game_type_guide`
- `template_rule_id`
- `workspace_root`
- `llm_binding_required`

### 4.3 Runner

Responsibilities:

- Execute stable top-level repository commands.
- Capture stdout, stderr, exit code, start time, end time, and command line.
- Update platform run metadata.
- Refresh artifact index after execution.
- Support cancellation for active child processes.

Runner commands must be allowlisted. Phase A should start with repository entrypoints exposed through `scripts/python/dev_cli.py`.

Runner scope:

- A project owns exactly one default workspace in Phase A.
- A workspace owns repository state, sidecars, runtime logs, and metadata for the prototype execution context.
- A prototype is the primary execution target inside one workspace during Phase A.
- A task is not a Phase A formal delivery object; Chapter 3 through Chapter 7 task execution is deferred.
- A runner run is a platform process execution bound to exactly one workspace and optionally one task.
- Phase A permits at most one active heavy runner per project.
- Multiple read-only requests may inspect artifacts while a runner is active.

This means two different projects may run concurrently if host capacity allows, but two heavy commands for the same project must not run at the same time in Phase A.

Phase A allowed orchestration families:

- Chapter 2 repository bootstrap route.
- Prototype top-level router: `run-prototype-workflow`.
- Prototype TDD: `run-prototype-tdd`.
- Prototype scene creation: `create-prototype-scene`.
- 7-day playable Godot prototype guidance and skills.

Phase A excluded orchestration families:

- Chapter 3 task triplet generation.
- Chapter 4 overlay baseline.
- Chapter 5 semantics stabilization.
- Chapter 6 formal task delivery.
- Chapter 7 UI wiring closure.

### 4.4 Artifact Indexer

Responsibilities:

- Locate active task files and latest run sidecars.
- Produce compact summaries for browser/API consumption.
- Point to authoritative files instead of copying workflow truth.
- Refresh after runs and on demand.

The indexer reads repository artifacts, but it does not reinterpret workflow decisions.

### 4.5 SQLite Metadata Store

Responsibilities:

- Track projects, workspaces, runs, artifact index rows, and approval sync state.
- Track project quota usage.
- Track runner lock state per project.
- Support recovery of platform process state after service restart.
- Link platform runs to repository output directories.

SQLite is sufficient in Phase A because there is one node and one local disk.

### 4.6 Browser UI

Responsibilities:

- List projects and workspaces.
- Show task recovery status before execution actions.
- Show run status and logs.
- Render or link artifacts.
- Expose approval readback and decision submission.

The UI should be operational and dense. It should favor status tables, task panels, log panes, and artifact viewers over marketing-style screens.

## 5. Deployment View

Phase A deployment on Alibaba Cloud ECS:

```text
Windows ECS
  C:\jimuyun\                         current project checkout
  C:\workspaces\                      hosted workspace root
  C:\Program Files\Python312\         Python 3.12 runtime
  C:\Program Files\dotnet\            .NET 8 SDK/runtime
  C:\Godot\4.5.1-mono\                Godot 4.5.1 .NET/mono
  <platform-service-root>\            Web Service + UI + SQLite DB
  <caddy-root>\                        Caddy HTTPS termination
```

Required host tools:

- `git`
- `py -3`
- `node`
- `codex`
- `.NET SDK 8`
- `Godot 4.5.1 .NET/mono`

Environment variables:

- `HOSTED_WORKSPACE_ROOT`
- `HOSTED_PROJECT_LIMIT`
- `GODOT_BIN`
- `DELIVERY_PROFILE`
- `SECURITY_PROFILE`
- `OPENAI_API_KEY` when OpenAI API transport is enabled
- `ALLOWED_EXTERNAL_HOSTS` when runtime network access is needed
- `GD_OFFLINE_MODE` when offline mode is required
- `HTTPS_TERMINATION=caddy`
- `APP_BIND_URL=http://127.0.0.1:8080`
- `PUBLIC_BASE_URL=https://<your-domain>`
- `LLM_COST_STOP_LOSS_PER_RUN_CNY=2.00`
- `LLM_COST_STOP_LOSS_DAILY_ACCOUNT_CNY=20.00`

## 6. Workspace Layout

Each hosted workspace uses this layout:

```text
%HOSTED_WORKSPACE_ROOT%\<tenant>\<project>\<workspace-id>\
  repo\
  runtime\
    stdout\
    stderr\
    commands\
  meta\
    workspace.json
    latest-run.json
    approvals.json
```

Ownership:

- `repo\` is the server-controlled project workspace and contains repository-native `logs/**`.
- `runtime\` is platform-owned execution evidence.
- `meta\` is platform-owned metadata and must not become workflow truth.

## 7. Data Ownership

Data ownership is intentionally split.

| Data | Owner | Storage | Notes |
|---|---|---|---|
| Source code and durable docs | Server-controlled project workspace | `repo\` | Phase A does not accept browser-provided Git URLs. |
| Runtime sidecars | Repository scripts | `repo\logs\**` | Authority for prototype recovery, route, and inspection. |
| Platform run logs | Runner | `runtime\stdout`, `runtime\stderr`, `runtime\commands` | Authority for platform process execution evidence. |
| Platform metadata | Web Service | SQLite + `meta\*.json` | Indexing and access state only. |
| Artifact summaries | Artifact Indexer | SQLite and generated summary JSON | Cache derived from authoritative repository files. |
| LLM usage audit | Runner / Web Service | SQLite + runtime command logs | Records request intent, model/backend label, duration, exit state, and cost metadata when available; never stores API keys. |
| LLM quota and billing | `new-api` | `new-api` database | External gateway owns model routing, user quota, and billing. Platform stores only binding and correlation metadata. |

## 7.1 Project, Workspace, Runner, And Task Relationship

The Phase A object model is:

```text
Account
  Project
    Workspace
      Prototype
      Run
      Artifact
```

Definitions:

- Account: the login owner. Phase A starts with single-admin plus password or token.
- Project: a server-controlled game prototype project configured from admin rules. Phase A default limit is two projects per account.
- Workspace: the project's one default executable workspace and runtime state directory.
- Prototype: the gameplay/UI/interaction experiment record handled by prototype lane scripts.
- Runner: the platform process executor. It is not a durable business object; each execution creates a `runs` row.
- Run: one command execution with stdout, stderr, status, and optional prototype linkage.

Concurrency rule:

- Project-level write lock: one active heavy runner per project.
- Workspace-level mutation lock: one active mutating command per workspace.
- Read-only artifact and status requests are allowed concurrently.

Practical examples:

- Project A prototype `battle-loop` can run while Project B prototype `hud-flow` runs, if host capacity allows.
- Project A `run-prototype-workflow` and Project A `run-prototype-tdd` must not both run heavy mutating commands at the same time.
- A user may view Project A artifacts while Project A prototype evidence is running.

## 8. Runtime Flows

### 8.1 Chapter 2 Project Bootstrap Flow

```text
API request
  -> authenticate account
  -> enforce per-account project quota
  -> apply admin-defined project creation rule
  -> create project and one default workspace
  -> run Chapter 2 bootstrap route
  -> metadata update
  -> project health refresh
  -> artifact index refresh
```

Failure behavior:

- Dependency failure returns readiness details.
- Rule mismatch returns a blocked project creation state.
- Bootstrap failure keeps the workspace for inspection.
- The platform must not delete a workspace to recover from bootstrap failure.

### 8.2 Prototype Intake And Routing Flow

```text
Open prototype page
  -> read active prototype and project metadata
  -> collect required prototype fields
  -> run-prototype-workflow
  -> load prototype-7day-playable-godot-zh guidance when applicable
  -> artifact index refresh
  -> UI displays next prototype day, blockers, and required user input
```

The prototype page must not offer Chapter 3 through Chapter 7 formal delivery actions in Phase A.

### 8.3 Prototype TDD Execution

```text
User starts prototype red/green/refactor
  -> API validates workspace and prototype slug
  -> Runner records run row
  -> Runner executes run-prototype-tdd
  -> stdout/stderr and exit code captured
  -> artifact index refresh
  -> run status completed or failed
```

Runner must call stable top-level commands such as:

```powershell
py -3 scripts/python/dev_cli.py run-prototype-workflow --prototype-file docs/prototypes/<prototype-file>.md --confirm --godot-bin "%GODOT_BIN%"
py -3 scripts/python/dev_cli.py run-prototype-tdd --slug <slug> --stage red --dotnet-target Game.Core.Tests/Game.Core.Tests.csproj --filter <Expr>
py -3 scripts/python/dev_cli.py create-prototype-scene --slug <slug>
```

### 8.4 Project Health Flow

```text
User opens health page
  -> API reads latest project health artifact
  -> optional project-health-scan run
  -> latest.html or compact summary returned
```

### 8.5 Approval Sync Flow

```text
Artifact index refresh
  -> read approval sidecars
  -> update approval metadata rows
  -> UI renders pending/approved/denied/invalid/forbidden state
  -> operator submits decision
  -> run-approval-sync writes or delegates sidecar update
```

The approval state transition rules stay script-owned.

## 9. API Architecture

The API should use resource-oriented endpoints from the requirement document.

Implementation rules:

- Request handlers validate inputs and delegate.
- Command execution always goes through Runner.
- Artifact reads always go through Artifact Indexer or direct authoritative file streaming.
- Error responses include `code`, `message`, `details`, and optional `next_action`.

Recommended response shape:

```json
{
  "status": "ok",
  "data": {},
  "warnings": [],
  "source": {
    "workspace_id": "local-main",
    "artifact_path": "logs/ci/active-tasks/task-1.active.md"
  }
}
```

Run state enum:

- `queued`
- `running`
- `completed`
- `failed`
- `cancel_requested`
- `cancelled`
- `blocked`

## 10. Metadata Schema

Phase A SQLite tables:

```sql
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  name TEXT NOT NULL,
  source_rule_id TEXT NOT NULL,
  game_type TEXT,
  game_type_source TEXT,
  game_type_guide TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE workspaces (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  account_id TEXT NOT NULL,
  path TEXT NOT NULL,
  status TEXT NOT NULL,
  last_synced_at TEXT,
  FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  task_id TEXT,
  prototype_slug TEXT,
  run_type TEXT NOT NULL,
  command TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  run_dir TEXT,
  stdout_path TEXT,
  stderr_path TEXT,
  exit_code INTEGER,
  runner_lock_key TEXT,
  llm_backend TEXT,
  llm_gateway TEXT,
  llm_request_id TEXT,
  llm_model TEXT,
  llm_cost_json TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
);

CREATE TABLE artifacts (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  task_id TEXT,
  run_id TEXT,
  artifact_type TEXT NOT NULL,
  path TEXT NOT NULL,
  status TEXT,
  summary_json TEXT,
  updated_at TEXT NOT NULL,
  authoritative INTEGER NOT NULL DEFAULT 1,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
);

CREATE TABLE approvals (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  task_id TEXT,
  status TEXT NOT NULL,
  decision TEXT,
  reason TEXT,
  updated_at TEXT NOT NULL,
  source_path TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
);

CREATE TABLE project_limits (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  max_projects INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE accounts (
  id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT,
  api_token_hash TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE account_llm_bindings (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  gateway_base_url TEXT NOT NULL,
  external_user_id TEXT,
  token_ref TEXT NOT NULL,
  quota_policy TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(account_id) REFERENCES accounts(id)
);

CREATE TABLE runner_locks (
  lock_key TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  workspace_id TEXT,
  run_id TEXT,
  status TEXT NOT NULL,
  acquired_at TEXT NOT NULL,
  heartbeat_at TEXT,
  FOREIGN KEY(project_id) REFERENCES projects(id)
);
```

Schema notes:

- `summary_json` is a cache, not the source of truth.
- `path` values should be workspace-relative where practical.
- All paths must be normalized and checked against workspace root before read or write.

## 11. Hosted Entrypoint Architecture

Phase A should add stable script-first hosted entrypoints around the existing Chapter 2 and Prototype lane commands. Formal Chapter 3 through Chapter 7 entrypoints are intentionally deferred.

Recommended script placement:

- `scripts/python/workspace_bootstrap_check.py`
- `scripts/python/describe_task_tools.py`
- `scripts/python/run_artifact_index_refresh.py`
- `scripts/python/run_hosted_chapter2_bootstrap.py`
- `scripts/python/run_hosted_prototype_workflow.py`
- `scripts/python/run_hosted_prototype_tdd.py`
- `scripts/python/export_active_prototype_summary.py`
- `scripts/python/read_approval_state.py`

Recommended CLI aggregation:

- Add subcommands to `scripts/python/dev_cli.py` after standalone scripts are implemented.

Script rules:

- Keep each script deterministic and under the script size guardrail where practical.
- Emit JSON summaries for Web API and CLI callers.
- Write evidence under `logs/**`.
- Call existing repository commands instead of copying their logic.

## 12. Security Architecture

Phase A keeps `host-safe` as the default security profile.

Security controls:

- Public access requires authentication before any project, workspace, run, artifact, or approval endpoint is usable.
- Public access requires HTTPS termination.
- Workspace root allowlist.
- Path normalization before file reads and writes.
- Command allowlist for Runner.
- No arbitrary shell command endpoint.
- No browser-provided raw command execution.
- Secrets kept in environment variables or host secret store, not SQLite rows.
- Session cookies or bearer tokens must be configured with secure flags when HTTPS is enabled.
- API writes must be auditable with user, project, workspace, operation, timestamp, and result.

Host boundary rules from ADR-0019 and ADR-0031 remain active:

- `res://` and `user://` remain runtime resource boundaries.
- External network access remains HTTPS and allowlist based.
- Dynamic external code loading remains forbidden.

### 12.1 LLM Gateway Integration

Phase A should use `new-api` as a replaceable LLM gateway rather than calling model providers directly from the platform.

Integration model:

```text
Phase A Platform Account
  -> account_llm_bindings
  -> new-api user/token
  -> new-api model routing, quota, and billing
  -> upstream model providers
```

Responsibilities kept in the Phase A platform:

- account, project, workspace, prototype, run, and artifact state
- runner locks and run lifecycle
- explicit user action before LLM-costing work
- correlation between platform run and LLM gateway request
- platform-side stop-loss before issuing a costly command

Responsibilities delegated to `new-api`:

- upstream provider API keys
- model routing
- per-account quota and billing
- model-level pricing and availability
- provider retry or channel fallback policy

Configuration:

- `LLM_GATEWAY_PROVIDER=new-api`
- `LLM_GATEWAY_BASE_URL=https://<new-api-domain>/v1`
- `LLM_GATEWAY_TOKEN_MODE=per-account`
- `LLM_GATEWAY_BINDING_MODE=manual-admin`

Correlation:

- Platform runs should attach `account_id`, `project_id`, `run_id`, and `prototype_slug` to gateway calls through headers or request metadata when supported.
- Platform `runs.llm_request_id` stores the gateway request id when available.
- Platform `runs.llm_cost_json` stores a summary copy of cost metadata when available, not the billing source of truth.

Boundary:

- `new-api` must not own platform workflow state.
- The Phase A platform must not depend on `new-api` internal database tables.
- Replacing `new-api` later should require changing only gateway configuration and binding adapters, not Prototype lane workflow state.
- Phase A uses manual admin binding from a platform account to a `new-api` user/token. API-driven provisioning is deferred.

Compliance and licensing notes:

- `new-api` is an external AGPL-licensed component and should be deployed as a separate service.
- If `new-api` is modified and provided over a network, AGPL obligations must be reviewed.
- The current ECS host is in Malaysia, so Phase A does not apply China mainland generative AI service requirements by default.
- Domain, certificate source, public launch compliance posture, and any region-specific obligations may be finalized before production launch instead of blocking prototype implementation.

OpenAI/Codex controls:

- Upstream provider keys are owned by `new-api`, not by the Phase A platform.
- The platform stores `token_ref` or binding metadata, not raw gateway tokens in git-tracked files.
- Runs record backend label, command intent, start time, finish time, exit code, and cost metadata when available.
- Existing repository rules continue to control when OpenAI/Codex-backed work is invoked.
- The browser must expose explicit user actions for any LLM-costing operation.
- Retry limits and stop-loss rules are explicit per hosted command.
- LLM-backed routes remain advisory or script-owned according to the existing Prototype lane workflow.

## 13. Reliability And Recovery

Recovery model:

- Repository recovery is sidecar-driven.
- Platform recovery is SQLite + runtime log driven.
- A service restart must preserve workspace state and run history.

Failure families:

- `dependency_missing`
- `workspace_sync_blocked`
- `runner_command_failed`
- `artifact_index_missing`
- `approval_blocked`
- `route_recommends_stop`
- `project_health_failed`
- `project_quota_exceeded`
- `runner_lock_active`
- `auth_required`
- `llm_backend_failed`
- `llm_cost_stop_loss`

Each failure should expose:

- what failed
- where the authoritative evidence is
- recommended next action
- whether a rerun is allowed

## 14. Observability

Minimum platform evidence:

- one command record per run
- stdout file
- stderr file
- run metadata row
- artifact index refresh result
- service log

Repository evidence remains in:

- `repo\logs\ci\**`
- `repo\logs\unit\**`
- `repo\logs\e2e\**`

The browser should link to both platform logs and repository artifacts when both exist.

## 15. Testing Strategy

Phase A tests should follow ADR-0025 and repository conventions.

Recommended test layers:

- Unit tests for path normalization, command allowlist, schema validation, and artifact discovery.
- Integration tests for workspace bootstrap against a local fixture repo.
- CLI tests for Chapter 2 and Prototype hosted scripts with dry-run or fixture modes.
- API tests for run lifecycle and artifact readback.
- Optional browser smoke once UI exists.

Minimum pre-implementation validation:

```powershell
py -3 scripts/python/dev_cli.py run-local-hard-checks-preflight --delivery-profile fast-ship
```

Minimum post-implementation validation:

```powershell
py -3 scripts/python/dev_cli.py run-local-hard-checks --godot-bin "$env:GODOT_BIN"
```

## 16. Capacity And Performance

Phase A assumes:

- one Windows ECS node
- local disk workspace storage
- public browser access
- medium read concurrency
- project-scoped runner serialization
- default per-account project quota of `2`
- one workspace per project

The architecture should allow concurrent read-only artifact views while a runner task is active.

The system should not optimize for distributed scale in Phase A. The important performance target is operational responsiveness under moderate browser/API load:

- API status reads should be quick.
- artifact index reads should avoid rescanning the whole repository on every request.
- long-running tasks should not block the Web Service event loop.
- log streaming or polling should not hold exclusive runner locks.
- SQLite writes should be short, explicit transactions.

## 17. Key Trade-offs

| Decision | Chosen option | Why |
|---|---|---|
| Metadata store | SQLite | Matches single-node scope and keeps deployment simple. |
| Web Service stack | ASP.NET Core 8 Minimal API | Stable on Windows ECS, strong concurrency, built-in auth middleware, background workers, and good static UI hosting. |
| Workflow authority | Repository scripts | Prevents drift from existing recovery and stop-loss logic. |
| Source model | Admin-defined local rules, no browser Git URL | Keeps the public prototype product controlled while custom quality gates evolve later. |
| Workspace storage | Local disk | Fastest path for Phase A and enough for one ECS node. |
| Runner model | Project-scoped controlled runner | Allows multiple projects while preventing same-project workspace mutation races. |
| Project count | Multiple projects, default account limit 2 | Supports prototype multi-project use without prematurely becoming a full multi-tenant platform. |
| Workspace count | One workspace per project | Fits prototype lane and avoids branch/log state complexity. |
| Public access | Authenticated HTTPS | Browser users access over the public Internet, so auth and transport security are part of Phase A. |
| LLM gateway | `new-api` as replaceable external gateway | Provides per-account quota, billing, and model routing while keeping platform workflow state separate. |
| LLM execution | Included with audit and stop-loss | LLM support is required for first-version hosted value, but must be explicit, observable, and bounded. |
| Phase A workflow scope | Chapter 2 + Prototype 7-day playable | Delivers a complete prototype product before formal Chapter 3-7 cloud orchestration. |
| API behavior | Delegate and observe | Keeps Web API thin and lowers risk of logic fork. |
| UI scope | Operational minimum | Gives useful access without building Phase B product surface early. |

## 18. Implementation Slices

Recommended implementation order:

1. Account login and per-account project quota.
2. Admin-defined project creation rules and Chapter 2 hosted bootstrap.
3. One-workspace-per-project metadata schema.
4. Public Web Service shell with authentication and HTTPS deployment decision.
5. Prototype hosted entrypoints and project runner locks.
6. Artifact indexer for active prototypes, prototype records, sidecar JSON, TDD summaries, and project-health.
7. OpenAI/Codex execution audit and stop-loss using existing invocation rules.
8. Browser pages for project bootstrap, prototype intake, 7-day playable routing, TDD evidence, and project health.
9. Thin operator skills and resolver rules for Chapter 2 and Prototype lane only.

Each slice should produce runnable evidence under `logs/**` and should not require waiting for later slices to validate its own behavior.

## 19. Open Architecture Questions

- Which authentication method should Phase A use first: single admin account, OAuth provider, or signed invite tokens?
- What cost threshold should trigger platform-side `llm_cost_stop_loss` before forwarding to `new-api`?
- Should log streaming use Server-Sent Events first, or simple polling until the UI proves stable?
- What should the first admin-defined project creation rule contain besides game name and game type?
- Which production domain and certificate source should be used before public launch?

Recommended default until decided:

- Use `HOSTED_WORKSPACE_ROOT` with `C:\workspaces` as default.
- Use `HOSTED_PROJECT_LIMIT=2`.
- Use ASP.NET Core 8 Minimal API.
- Use single-admin username/password or single admin token only for the first prototype.
- Use Caddy or Nginx on ECS for HTTPS termination.
- Use polling for logs until the UI proves stable.
- Use `new-api` as `LLM_GATEWAY_PROVIDER` and keep it external to platform workflow state.
- Use manual admin binding for `new-api` user/token in Phase A; defer API-driven provisioning.
- Defer production domain, certificate source, and region-specific launch compliance confirmation until before public launch.

## 20. Architecture Exit Criteria

The Phase A architecture is ready for implementation when:

- Hosted entrypoint JSON contracts are defined.
- Workspace root and metadata schema are accepted.
- Runner allowlist is accepted.
- Artifact index summary shape is accepted.
- API framework is chosen.
- Authentication method and HTTPS termination path are recorded.
- LLM audit and cost stop-loss shape is accepted.
- `new-api` account binding and request correlation shape is accepted.
- Manual admin binding workflow for `new-api` users/tokens is documented.

## 21. One-Sentence Architecture Rule

The Phase A platform is a hosted shell around the repository workflow kernel: scripts decide, the platform hosts, records, indexes, and presents.
