# Repository Guide

This file is the Phase-service-first repository map. It routes agents to current product, architecture, standards, runtime, and recovery authority. Keep detailed procedures in their source documents instead of expanding this file into a general template manual.

## Purpose
- The root repository is the Ji Mu Yun Phase A/B cloud prototype platform, not a specific game project.
- `AGENTS.md` is the concise agent routing and non-negotiable change-contract layer.
- `README.md` is the product overview, phase status, stack summary, and startup entry.
- Game-specific identity, genre, route profile, and execution state belong to each hosted project workspace and metadata records, not to root-level placeholder fields.
- `docs/architecture/phase-service/**`, `docs/architecture/ADR_INDEX_PHASE.md`, and `docs/standards/**` are the deep sources for Phase service decisions and conventions.

## Phase Service Scope
Treat the following as in-scope for Phase service changes:
- `PhaseA.Platform/**` and `PhaseA.Platform.Tests/**`.
- `runtime/phase-a/**`, including startup, recovery, watchdog, and Caddy configuration.
- `scripts/python/phase_a_*.py`, `scripts/python/phase_b_*.py`, and Phase-facing smoke or drill scripts.
- `logs/phase-a-innernet/**` as runtime state, live metadata, hosted workspaces, and evidence.
- Account isolation, admin/user auth, token hashing, audit exports, hosted workspace/artifact readback, and browser/API behavior.
- Phase browser-consumed prototype routes, including project creation, GDD, prototype generation, iteration, repair, asset, package, preview, and route recovery state.
- Shared LLM/Codex execution entrypoints used by Phase routes and scripts.
- Godot runtime, UI capability, UI style, diagnostics, preview, package, and acceptance rules consumed by hosted routes.

## Planned Frontend Boundary Hardening
- `execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md` is a `paused` downstream plan. It starts only after `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/` is fully complete and the protected BH-HANDOFF succeeds.
- Until that handoff, do not treat `/ui-v2`, Permit/Preflight, new browser session paths, Change Origin Gate, legacy freeze, or Phase platform SemVer as current repository capabilities. Current runtime commands and contracts in this file and `README.md` remain authoritative.
- Plan-readiness can be checked with `py -3 execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py`. A PASS means only that the plan is internally implementable; it cannot replace the repository-external protected BH-HANDOFF verifier and does not prove code completion.
- Update this routing file in the same change that makes a planned rule operational: BH-SF2 for Platform/Hosted Codex routing and Preflight, BH-SF3 for mutation/acceptance recovery entrypoints, BH-RP1 for version projection, BH-REACT1/BH-REACT2 for `/ui-v2`, session and legacy-route behavior, and BH-RELEASE for final SemVer/release authority. Never document a future phase as active before its exit evidence exists.

## Start Here
1. Read `README.md` for current product status and startup.
2. Read `docs/architecture/phase-service/_index.md` before changing Phase service boundaries.
3. Read `docs/architecture/ADR_INDEX_PHASE.md` before changing Phase service decisions.
4. Read `docs/standards/_index.md` and `docs/standards/phase-service.md` before changing API, DB, errors, logs, security, tests, or status contracts.
5. Read the relevant Godot standard before changing hosted Godot behavior:
   - `docs/standards/godot-engine-semantics.md`
   - `docs/standards/godot-ui-capability-contract.md`
   - `docs/standards/godot-ui-style-contract.md`
   - `docs/standards/godot-diagnostics-quality-gates.md`
6. Read the relevant file in `execution-plans/` and `decision-logs/` when the change is plan-scoped or decision-scoped.

## Change Routing
- Platform API, browser behavior, DTOs, or readback:
  - `docs/standards/phase-service.md`
  - `docs/architecture/phase-service/system-overview.md`
  - `PhaseA.Platform/Program.cs`
  - `PhaseA.Platform/Browser/**`
  - `PhaseA.Platform.Tests/Browser/**`
- Auth, accounts, tokens, isolation, limits, or audit:
  - `docs/architecture/phase-service/auth-and-accounts.md`
  - `docs/adr/ADR-0034-phase-account-scoped-token-auth.md`
  - `PhaseA.Platform/Security/**`
  - `PhaseA.Platform/Data/**`
- Metadata DB, migrations, restore, or persistence:
  - `docs/architecture/phase-service/metadata-db.md`
  - `docs/adr/ADR-0033-phase-metadata-sqlite-local-disk.md`
  - `PhaseA.Platform/Data/**`
- Hosted workspace, artifacts, packages, assets, or previews:
  - `docs/architecture/phase-service/hosted-workspaces-and-artifacts.md`
  - `PhaseA.Platform/Workspaces/**`
  - `PhaseA.Platform/Readback/**`
- Prototype, GDD, iteration, repair, UI closure, or route recovery:
  - `docs/architecture/phase-service/prototype-routes-and-recovery.md`
  - the relevant Godot standards under `docs/standards/`
  - the GDD-to-module source documents under `docs/workflows/phase-a-gdd-to-module-*.md`
  - `PhaseA.Platform/Runs/**`
- Shared LLM/Codex execution:
  - `docs/architecture/phase-service/llm-codex-execution.md`
  - `docs/adr/ADR-0037-phase-shared-llm-codex-entrypoints.md`
  - the shared entrypoints listed below
- Runtime, Caddy, watchdog, or public health:
  - `docs/architecture/phase-service/runtime-caddy-and-recovery.md`
  - `runtime/phase-a/**`
  - the recovery order below
- Tests, smoke, or evidence:
  - `docs/standards/phase-service.md`
  - `PhaseA.Platform.Tests/**`
  - Phase-facing smoke and drill scripts under `scripts/python/`
- Hosted Godot execution kernel, contracts, or engine-side tests:
  - `docs/architecture/ADR_INDEX_GODOT.md`
  - `docs/architecture/base/00-README.md`
  - `docs/testing-framework.md`
  - the relevant Godot standard under `docs/standards/`
  - keep shared contracts in `Game.Core/Contracts/**` and keep them Godot-free

## Repository Workflow Kernel Boundary
- `workflow.md` defines the repository-local formal delivery workflow. It is not the default Phase browser/API path.
- `workflow.example.md` is onboarding for a game repository copied from the original template. It is not onboarding for this root platform repository.
- A standalone requirements Markdown file is a direct implementation input and must not create a VDD directory. Use `$vdd-execution-plan` only when the user explicitly requests creation or repair of a complete execution-plan directory.
- Phase routes reuse selected repository scripts, validators, profiles, Godot assets, and route contracts as internal execution dependencies.
- Do not route ordinary Phase service work into business-repository Taskmaster triplets, formal Chapter 3-7 orchestration, Chapter 4 overlay-generator commands, local Chapter 6 review recovery, or game-template release steps unless the task explicitly targets that internal toolchain.
- Phase architecture overlays and ADRs must still be updated when a Phase boundary, threshold, contract, security posture, or release decision changes.
- Prototype routes use their project-local contracts, route profiles, latest state, ledgers, and acceptance evidence. They must not infer authority from root-level game metadata.
- `DELIVERY_PROFILE` is an internal hosted-workflow configuration with allowed values `playable-ea`, `fast-ship`, and `standard`; the platform default is `fast-ship`, and hosted Chapter 2 bootstrap consumes it. Detailed local formal-delivery behavior remains in `DELIVERY_PROFILE.md` and `workflow.md`.

## Highest Encoding Rule
- All Chinese text reads and writes must use Python with explicit UTF-8, for example `Path(path).read_text(encoding="utf-8")` and `Path(path).write_text(text, encoding="utf-8", newline="\n")`.
- Do not use PowerShell, `Get-Content`, `Set-Content`, `Out-File`, `Add-Content`, `type`, `echo`, `copy con`, or other Windows-native text tools to read or write Chinese text.
- If a command script must contain Chinese literals, write it as a Python file or use ASCII-only Python source with Unicode escapes, then write the target file as UTF-8.
- This rule applies to `AGENTS.md`, `README.md`, `workflow.md`, `docs/**/*.md`, `.agents/skills/**/SKILL.md`, prototype records, and project-health documentation.
- Code, tests, logs, and machine output remain English unless the file is explicitly user-facing documentation.

## Core Rules
- Communicate with the user in Chinese.
- Default environment is Windows; use Windows-compatible commands and paths.
- Keep code, scripts, tests, comments, and printed messages in English.
- Do not use emoji.
- Write logs and evidence under `logs/`.
- Do not revert user changes unless explicitly requested.
- Prefer small, deterministic, testable changes.
- Code or test changes should cite at least one accepted ADR; if thresholds, contracts, security posture, or release policy change, update or supersede the ADR set.
- Route architecture work in arc42 order: irreversible decisions -> cross-cutting rules -> runtime backbone -> feature slices.
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
- Detailed Phase service API, DB, error, logging, security, testing, and status standards live in `docs/standards/phase-service.md`; the standards index is `docs/standards/_index.md`.
- Do not manually mutate the live Phase A metadata DB unless the user explicitly authorizes it.
- Schema changes must be backward-compatible by default, include a migration or recovery path, and preserve existing data unless an approved decision log says otherwise.
- Public and browser-consumed APIs must remain backward-compatible by default. Do not remove or rename routes, fields, status codes, auth behavior, or artifact paths without explicit approval and a documented compatibility plan.

### Prototype Route Recovery
For file-changing hosted game-project routes, consume project-level recovery sources in authority order before editing:
1. Parsed game-type route profile and selected route skill prompt block.
2. `meta/project-execution-guide.md`.
3. `routes/prototype-contract/latest.json`.
4. Current route latest state, such as `meta/routes/prototype/latest.json`, `meta/routes/iteration-plan/latest.json`, or `meta/routes/execute-next-goal/latest.json`.
5. Current goal, step, repair step, or session state.
6. Repair ledger and failing acceptance or Godot diagnostic evidence for repair routes.
7. Latest live platform acceptance blocker, which wins over old assistant summaries, route state, and repair ledger memory.

Missing required recovery sources must fail closed. Route state and repair ledger are continuity memory, not current acceptance authority. Do not mark steps complete based only on assistant text.

## LLM Engine And Invocation Protocol
- New Phase routes, services, scripts, and workflow helpers must use the shared LLM/Codex entrypoints instead of constructing provider calls or `codex exec` commands locally.
- C# structured/read-only LLM calls must use `PhaseA.Platform/Llm/LlmRouteEngine.cs` through `ILlmRouteEngine`.
- C# executable Codex workflows must use `PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs`.
- Python LLM/Codex scripts must use `scripts/sc/_llm_backend.py::run_llm_exec` or a thin wrapper that delegates to it.
- Prompt transport is stdin-first: use `codex exec ... -` with UTF-8 stdin, never append large prompts as command-line arguments.
- Pure analysis or JSON-only decisions remain read-only and schema/JSON parsed. File-changing workflows require an explicit executable route, `workspace-write`, and acceptance/smoke validation.
- If the shared entrypoint cannot express a required model, reasoning, sandbox, output, billing, credential, or retry behavior, extend the shared entrypoint and its tests first.
- Required regression coverage: `PhaseA.Platform.Tests/Runs/CodexHostedProcessCommandFactoryTests.cs`, `PhaseA.Platform.Tests/Llm/LlmRouteEngineTests.cs`, `scripts/sc/tests/test_llm_backend.py`, and route-specific tests.

## Phase Runtime Recovery Order
1. Check `http://127.0.0.1:18080/healthz`.
2. If local app health is unhealthy, run `runtime/phase-a/ensure-phasea.ps1`.
3. If local app health is healthy but public `:8080` health is unhealthy, inspect or restart Caddy after the app is healthy.
4. Do not use ordinary `dotnet run` for the live server. Use `runtime/phase-a/start-phasea.ps1`.
5. Do not manually edit the live metadata DB.
6. Record recovery evidence under `logs/phase-a-innernet/runtime/`.

## Phase A Runtime Ops
- Stable local app bind: `http://127.0.0.1:18080`.
- Canonical external `PUBLIC_BASE_URL`: `https://47.86.160.138:8080`.
- Current direct public health probe: `http://47.86.160.138:8080/healthz`.
- Do not claim public HTTPS reachability until `py -3 scripts/python/phase_a_public_smoke.py --base-url https://47.86.160.138:8080` passes without `--allow-http`.
- Canonical runtime config: `runtime/phase-a/start-phasea.ps1`.
- Canonical Caddy config: `runtime/phase-a/Caddyfile`.
- Caddy must listen on `0.0.0.0:8080` and reverse proxy to `127.0.0.1:18080`.
- Live build outputs must stay outside the repository source tree. Current stable build root: `C:\Users\Administrator\.codex\memories\phasea-runtime-build`.
- Startup must set both `APP_BIND_URL` and `ASPNETCORE_URLS` to `http://127.0.0.1:18080`.
- Repo-wide MSBuild excludes must keep generated `logs/**`, `obj/**`, and `bin/**` out of compile inputs.
- `PHASEA_ADMIN_TOKEN_HASH` must come from the host secret store or service environment; never commit real token material or hashes.
- Recovery from public `502` always starts with local PhaseA health, then Caddy/public health.
- Watchdog PID: `logs/phase-a-innernet/phasea-watchdog.pid`.
- Watchdog log: `logs/phase-a-innernet/runtime/phasea-watchdog.log`.

### Minimum Recovery-Grade Runtime Variables
`runtime/phase-a/start-phasea.ps1` is the complete operational source of truth. This list records stable non-secret recovery defaults and is intentionally not an exhaustive environment manifest:
- `APP_BIND_URL=http://127.0.0.1:18080`
- `ASPNETCORE_URLS=http://127.0.0.1:18080`
- `HTTPS_TERMINATION=caddy`
- `PUBLIC_BASE_URL=https://47.86.160.138:8080`
- `HOSTED_WORKSPACE_ROOT=C:\jimuyun\logs\phase-a-innernet\workspaces`
- `HOSTED_PROJECT_LIMIT=2`
- `PHASEA_MAX_CONCURRENT_CHATS=8`
- `PHASEA_MAX_CONCURRENT_CHATS_PER_ACCOUNT=1`
- `PHASEA_MAX_CONCURRENT_GDD_QUESTION_FORMS=4`
- `PHASEA_MAX_CONCURRENT_GDD_QUESTION_FORMS_PER_ACCOUNT=1`
- `PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS=3`
- `PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS_PER_ACCOUNT=1`
- `PHASEA_MAX_CONCURRENT_OTHER_RUNS=3`
- `PHASEA_MAX_CONCURRENT_PROTOTYPE_CREATIONS=2`
- `PHASEA_MAX_CONCURRENT_WEB_PREVIEWS=3`
- `PHASEA_MAX_CONCURRENT_WEB_PREVIEWS_PER_ACCOUNT=1`
- `PHASEA_GODOT3_WEB_PREVIEW_EXPORT_TIMEOUT_SECONDS=180`
- `PHASEA_GODOT3_WEB_PREVIEW_EXPORT_INACTIVITY_TIMEOUT_SECONDS=45`
- `PHASEA_MAX_CONCURRENT_ASSET_GENERATIONS_PER_ACCOUNT=1`
- `PHASEA_METADATA_DB_PATH=C:\jimuyun\logs\phase-a-innernet\data\phase-a-platform.sqlite3`
- `PHASEA_REPOSITORY_ROOT=C:\jimuyun`
- `GODOT_BIN=C:\Godot\4.5.1-mono\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe`
- `PHASEA_GODOT3_BIN=C:\Godot\3.6.2\Godot_v3.6.2-stable_win64.exe`
- `DOTNET_ROOT=C:\jimuyun\.dotnet`

The startup script also resolves dynamic or secret-backed variables including `PHASEA_CODEX_COMMAND`, `PHASEA_RIPGREP_DIR`, `PHASEA_ADMIN_TOKEN_HASH`, `PHASEA_TICKET_SIGNING_SECRET`, `PHASEA_WEB_PREVIEW_SIGNING_SECRET`, and optional `AICODEMIRROR_*` integration values. Document names and sources only; never commit real secret values.

## Repo Map
- `PhaseA.Platform/`: ASP.NET Core Web/API, browser UI, route services, security, metadata, workspaces, LLM integration, and readback.
- `PhaseA.Platform.Tests/`: Phase service unit and integration tests.
- `runtime/phase-a/`: stable startup, recovery, watchdog, and Caddy configuration.
- `logs/phase-a-innernet/`: live metadata, hosted workspaces, runtime state, and evidence; protected runtime data, not source configuration.
- `scripts/python/phase_a_*.py` and `scripts/python/phase_b_*.py`: Phase operations, smoke, drill, and recovery utilities.
- `Game.Core/`, `Game.Godot/`, `Game.Core.Tests/`, and `Tests.Godot/`: hosted Godot prototype execution kernel and its tests.
- `scripts/sc/` and other `scripts/python/` tools: internal execution and validation infrastructure; not automatically public Phase entrypoints.
- `docs/architecture/phase-service/`, `docs/adr/`, and `docs/standards/`: Phase architecture, decisions, and standards.
- `execution-plans/` and `decision-logs/`: durable scoped intent and decisions.
- `logs/`: generated runtime, smoke, review, and evidence artifacts.

## Main Phase Commands
- One-shot local recovery: `powershell -ExecutionPolicy Bypass -File runtime/phase-a/ensure-phasea.ps1`
- Watchdog: `powershell -ExecutionPolicy Bypass -File runtime/phase-a/watch-phasea.ps1`
- Local operations check: `py -3 scripts/python/phase_a_ops_check.py`
- Local account/auth smoke: `py -3 scripts/python/phase_b_account_smoke.py --base-url http://127.0.0.1:18080`
- Direct HTTP public smoke: `py -3 scripts/python/phase_a_public_smoke.py --base-url http://47.86.160.138:8080 --allow-http`
- HTTPS closure smoke: `py -3 scripts/python/phase_a_public_smoke.py --base-url https://47.86.160.138:8080`
- Platform tests: `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj`

## Evidence Locations
- Runtime recovery and watchdog evidence: `logs/phase-a-innernet/runtime/`.
- Live metadata DB: `logs/phase-a-innernet/data/phase-a-platform.sqlite3` (protected; do not edit manually).
- Hosted workspaces and project-local route state: `logs/phase-a-innernet/workspaces/**` (protected).
- Phase smoke, drill, and test evidence: write under `logs/` without rewriting historical failures.
- Project-local route authority: `meta/**`, `routes/**`, route ledgers, acceptance evidence, diagnostics, and database-bound artifacts inside the hosted workspace.

## Docs Index
- `README.md`
- `docs/architecture/phase-service/_index.md`
- `docs/architecture/ADR_INDEX_PHASE.md`
- `docs/standards/_index.md`
- `docs/standards/phase-service.md`
- `docs/standards/godot-engine-semantics.md`
- `docs/standards/godot-ui-capability-contract.md`
- `docs/standards/godot-ui-style-contract.md`
- `docs/standards/godot-diagnostics-quality-gates.md`
- `docs/reference/godot-official-examples-index.md`
- `docs/PROJECT_DOCUMENTATION_INDEX.md`
- `workflow.md` only when maintaining the repository-local formal delivery toolchain.
- `workflow.example.md` only when maintaining template-derived game-repository onboarding.

## Change Policy
- Keep `AGENTS.md` Phase-service-first and concise.
- Keep public and browser-consumed contracts backward-compatible by default.
- Add recovery data as structured sidecars instead of rewriting historical evidence.
- Put detailed guidance in the relevant architecture, standard, workflow, or operations document.
- Put durable intent in `execution-plans/` and durable decisions in `decision-logs/`.
- Put high-frequency generated evidence in `logs/`.
