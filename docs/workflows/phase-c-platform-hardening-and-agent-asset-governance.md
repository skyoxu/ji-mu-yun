# Phase C Platform Hardening And Agent Asset Governance Plan

- Status: draft
- Language: English first pass
- Created: 2026-06-24
- Owner: Phase A/B platform evolution
- Scope: Phase C planning, deferred Phase A/B closure, and ECC pattern absorption

## Purpose

This document turns the current Phase A/B platform state and the ECC research pass into a concrete Phase C planning baseline.

Phase C is not a rewrite of the repository workflow kernel. It is the point where the hosted platform becomes safer, more portable, and easier to operate by combining three unfinished threads:

1. Deferred Phase A hosted-product hardening.
2. Deferred Phase B production multi-tenant isolation.
3. Selective ECC-style agent asset governance.

The result should preserve the repository rule that scripts own execution truth, sidecars own workflow evidence, and browser/API surfaces observe or trigger stable entrypoints without becoming a second workflow engine.

## Implementation Backlog Index

The companion implementation backlog is tracked in `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance-backlog.md`. It keeps Phase C work split into coarse P0/P1/P2 hardening and governance slices so this plan remains an architecture and conflict-resolution baseline rather than an overloaded task list.

## Priority Summary

No P0 blocker is known in the current Phase C baseline. The highest-risk Phase C work is security and authority preserving work, not feature expansion.

| Priority | Workstreams | Why |
|---|---|---|
| P1 | C0, C1, C3, C4, C5 | These decide source authority, hosted entrypoint safety, account boundary correctness, and OS-level isolation. They should happen before scale-out or strong isolation UX. |
| P2 | C2, C6, C7, C8 | These improve recovery, portability, observability, and isolation tiers, but they depend on the P1 authority and boundary decisions. |

Recommended first implementation batch: C0, then C1 minimum schema, then C3 hosted entrypoint inventory, C4a account hardening, and C5 isolation design. C2, C6, C7, and C8 should wait until those authority and boundary decisions are stable.

## Source Review

This pass reviewed the following repository sources:

- `README.md`: current Phase A/B completion summary and deferred Phase B items.
- `docs/workflows/cloud-platform-evolution-plan.md`: Phase A/B/C boundaries, cloud platform principles, and tool-layer productization rules.
- `docs/workflows/phase-b-account-isolation.md`: implemented Phase B account isolation slice and explicit deferred items.
- `docs/workflows/cloud-user-telemetry-and-feedback-plan.md`: event model, Phase A minimal instrumentation order, and future dashboard additions.
- `execution-plans/2026-05-10-phase-a-cloud-runner-requirements.md`: Phase A scope, out-of-scope list, and follow-up deliverables.
- `execution-plans/2026-05-11-phase-a-prototype-lane-implementation-backlog.md`: Phase A implementation completion state and remaining deployment/public-smoke questions.
- `docs/architecture/overlays/PHASE-A-CLOUD-RUNNER/08/08-Phase-A-Cloud-Runner-Architecture.md`: Phase A architecture, hosted entrypoint rules, security boundary, LLM gateway boundary, and open architecture questions.
- `affaan-m/ECC` GitHub repository at reviewed commit `71d22d0a77b7e0684f4e51cba03749b788993cdb`: external pattern source for agent asset lifecycle, not an authoritative dependency for this repository.

Local note: `logs/research/ecc/` was the temporary read-only clone used for this review. It is evidence for this session only and must not be treated as a durable source path.

## Current Phase State

### Phase A: Completed Core

The repository documentation says Phase A is implemented as a single-node hosted prototype platform with:

- ASP.NET Core Web/API service in `PhaseA.Platform/`.
- SQLite metadata.
- Workspace management.
- Project creation.
- Hosted prototype lane routes.
- Browser UI.
- Caddy reverse proxy configuration.
- Runtime evidence and recovery chain.
- Local runtime startup, recovery, and watchdog scripts under `runtime/phase-a/`.

Phase A also established the key architectural rule: the platform hosts, records, indexes, and presents repository workflows, but repository scripts remain the execution authority.

### Phase A: Unfinished Or Deferred Inputs To Phase C

The following Phase A items remain unfinished, deferred, or only partially productized:

1. Final public deployment closure
   - The Phase A backlog still names final ECS/Caddy public smoke after deployment domain and certificate decisions as the next action.
   - Production domain, certificate source, and region-specific public launch compliance remain deployment-time decisions.

2. Formal Chapter 3-7 hosted delivery
   - Phase A intentionally excludes Chapter 3 task triplets, Chapter 4 overlays, Chapter 5 semantics stabilization, Chapter 6 formal task delivery, and Chapter 7 UI wiring closure.
   - Phase C should not automatically expose these routes. It should first decide whether hosted formal delivery belongs in the same platform product or a later product lane.

3. Script-level hosted entrypoint closeout
   - The cloud evolution plan recommends machine-callable entrypoints such as `workspace-bootstrap-check`, `describe-task-tools`, `run-artifact-index-refresh`, `run-hosted-resume`, `run-hosted-task`, and approval readback/sync.
   - The repository already has project-health infrastructure and Phase A platform-specific command builders, but the recommended hosted entrypoint set is not fully present as standalone script contracts.

4. Minimal instrumentation
   - The telemetry plan recommends stabilizing `bootstrap_checked`, `task_started`, `task_route_decided`, `task_step_finished`, `task_stop_loss_triggered`, `approval_updated`, and `task_completed` before broader product analytics.
   - Phase C should treat this as operational observability, not growth analytics.

5. Hosted operator guidance and resolver rules
   - Phase A permits thin skills and lightweight resolver behavior, but the execution rules must remain script-owned.
   - Phase C can make this safer by adding an explicit agent asset catalog and health checks instead of relying on ad hoc skill discovery.

### Phase B: Completed Prototype-Hardening Slice

The Phase B account isolation slice is complete for the current prototype-hardening scope. Implemented capabilities include:

- Bearer-token authentication for host admin token and database-backed user tokens.
- Admin-created users.
- User disable/enable.
- User token rotation with one-time plaintext return.
- Account-scoped project, run, artifact, package, asset, chat, and workflow readback APIs.
- Admin-only route protection.
- Per-account LLM gateway binding and usage summary.
- Admin LLM usage summary, CSV export, and recent LLM run summaries.
- Account action audit filtering, paging, and CSV export.
- Local and public Phase B smoke checks, including optional authorized boundary checks.

### Phase B: Unfinished Or Deferred Inputs To Phase C

The current docs explicitly defer the following beyond the Phase B prototype-hardening scope:

1. User deletion.
2. Full LLM audit export with richer filters and pagination.
3. Full integration tests around HTTP auth middleware.
4. Username/password login, password reset, OAuth, OIDC, or self-service registration.
5. Automated browser E2E for admin management panels.
6. Separate Windows accounts for `PhaseA.Platform` and user-task runners.
7. Project-level NTFS ACLs for `workspaces/<account-id>/<project-id>`.
8. OS write-permission separation between platform binaries, metadata DB, Caddy configuration, and user workspaces.
9. Stronger runner isolation beyond application-level account checks.

These items should be treated as Phase C or pre-production security-hardening inputs. They should not be described as already complete Phase B work.

### Phase C: Existing Roadmap Baseline

The existing roadmap defines Phase C as storage abstraction and scale-out. Its baseline goals are:

- Abstract file storage for artifacts and durable docs.
- Support remote or object-backed storage later.
- Support node affinity and worker expansion.
- Evaluate containers, Windows Sandbox, or lightweight VMs as strong-isolation runners.
- Provide stronger runner isolation tiers for high-risk or high-value accounts.

The success criteria are:

- Workspace restoration is not tied to one machine forever.
- The platform can scale without rewriting repository workflow logic.
- Strong-isolation runners can replace or augment the local runner without breaking the Phase B workspace/ACL model.

## ECC Patterns Worth Absorbing

ECC should be treated as a pattern source, not a package to install into this repository. The useful parts are the operating-system-like asset lifecycle around agent workflows.

### 1. Manifest-Driven Capability Inventory

ECC separates installable material into components, modules, and profiles. Its manifest model allows dry-run planning before mutation.

Absorb the pattern as a project-local capability inventory:

- Define platform capabilities such as `phase-a-runtime`, `phase-b-account-isolation`, `prototype-lane`, `chapter6-formal-delivery`, `chapter7-ui-wiring`, `project-health`, `agent-review`, and `codex-entrypoints`.
- For each capability, declare owning docs, scripts, tests, runtime variables, logs, evidence paths, risk level, and whether it can be triggered by browser/API/CLI.
- Add a dry-run planner that reports missing files, missing env vars, stale docs, and unsafe activation paths without changing state.
- Keep this inventory project-local. Do not copy ECC global install semantics or user-home synchronization.

Phase C benefit: operators and hosted UI can ask what the platform can safely do before starting a run.

### 2. Install-State, Doctor, Repair, And Uninstall Lifecycle

ECC records managed files and can diagnose drift, repair expected files, or uninstall managed assets.

Absorb the lifecycle, but not the global installer:

- Create a project-local agent/platform asset state record under `logs/` or a generated runtime state path.
- Track generated indexes, exported Codex reference configs, skill catalog outputs, project-health dashboard outputs, and hosted capability manifests.
- Add a doctor mode that validates whether assets still match their source documents and schemas.
- Add a repair mode that regenerates only derived assets from authoritative repository sources.
- Add an uninstall or cleanup mode only for generated runtime artifacts, never for source docs or user-authored skills.

Phase C benefit: platform asset drift becomes visible and recoverable instead of becoming hidden prompt or config drift.

### 3. Agent Asset Health

ECC has health and evolution concepts for skills and sessions. This repository already has many skills, workflow docs, and runtime entrypoints, but no single project-local view of their health.

Absorb this as a conservative health check:

- Validate every selected `SKILL.md` has required front matter and reachable referenced files.
- Detect overlapping or ambiguous skill trigger descriptions.
- Detect skills that point to missing scripts, stale docs, or retired routes.
- Detect skills that would violate repository rules, such as bypassing shared LLM/Codex entrypoints.
- Track failures by skill or workflow family only after a stable evidence schema exists.

Phase C benefit: skills remain thin guidance layers instead of silently becoming a second workflow engine.

### 4. State Store And Operator Dashboard Shape

ECC models sessions, skill runs, decisions, install state, governance events, and work items in a queryable state store.

Absorb the shape, but keep repository truth where it already lives:

- `sessions` maps to Phase A platform runs and active runner state.
- `skillRuns` maps only to explicit skill-assisted operations when evidence exists.
- `decisions` maps to `decision-logs/`, not a new database-only decision record.
- `installState` maps to generated asset inventory and doctor state.
- `governanceEvents` maps to admin account audit, security stop-loss, approval updates, and forbidden command events.
- `workItems` maps to active tasks, prototypes, and formal Taskmaster triplets when present.

Phase C benefit: the operator dashboard can summarize distributed state without relocating workflow truth away from files and sidecars.

### 5. Session Inspect And Handoff

ECC's session inspection direction is useful because this repository already relies on recovery after context reset.

Absorb it as a handoff compiler:

- Read active-task summaries, latest pipeline pointers, Phase A run records, project-health output, and prototype sidecars.
- Emit compact handoff documents for browser/API/operator use.
- Preserve exact source pointers instead of summarizing away evidence.
- Avoid indexing private prompt bodies, raw tokens, or full stdout/stderr unless explicitly needed for an authenticated admin path.

Phase C benefit: recovery remains cheap and deterministic as hosted usage increases.

### 6. Codex Adapter Governance

ECC includes Codex support and a Codex-specific guidance file. The useful idea is a per-surface adapter, not a direct migration from Claude Code.

Absorb this as project-local adapter governance:

- Keep `AGENTS.md` and `docs/agents/` as the authoritative instruction surface.
- Generate or document Codex-facing reference config only from project sources.
- Avoid global `~/.codex` synchronization as a default Phase C behavior.
- Require shared LLM/Codex entrypoints for all Phase A routes, services, scripts, and workflow helpers.
- Treat Codex skills as guidance and Codex MCP as explicit external action surfaces, never as hidden workflow authority.

Phase C benefit: Codex usage becomes reproducible without polluting the operator's global environment.

### 7. MCP Inventory And External Action Boundaries

ECC catalogs many MCP servers. The useful pattern is inventory and gating, not importing a broad MCP list.

Absorb this as an allowlisted external action inventory:

- Record each MCP or external integration with owner, purpose, auth source, secret source, network boundary, and allowed workflows.
- Keep placeholders out of git-tracked secrets.
- Block MCPs that require broad filesystem, browser, or account access until a specific workflow needs them.
- Prefer repository-native scripts for workflow decisions and MCP only for live external data/actions.

Phase C benefit: external capability growth stays auditable.

### 8. Hook Profile And Security Tiering

ECC has hook strictness and runtime controls. Direct hook import would conflict with this repository's Codex and Phase A rules.

Absorb only the tiering idea:

- Model security levels through existing `DELIVERY_PROFILE` and `SECURITY_PROFILE` behavior.
- Add explicit Phase C runner tiers such as `local-runner`, `acl-isolated-runner`, and `strong-isolation-runner`.
- Use project-health and preflight checks instead of hidden hooks for enforcement.
- Where hooks are used in Codex or other surfaces, require documented, project-local, auditable behavior.

Phase C benefit: security posture can vary by account/project risk without importing tool-specific hidden behavior.

### 9. Worktree And Worker Orchestration

ECC has worktree and worker orchestration ideas. This is useful only after runner isolation is real.

Absorb later, gated by Phase C prerequisites:

- Do not add multi-worktree hosted concurrency until project-level NTFS ACLs and runner account separation are in place.
- Keep one active heavy runner per project until the concurrency model has tested lock and cleanup behavior.
- Consider worker expansion only after storage abstraction and workspace restore contracts are stable.

Phase C benefit: scale-out happens without weakening the current recovery and lock model.

## Merge And Conflict Resolution

### Conflict 1: ECC Skills Marketplace vs Repository Rule Against Early Skills Marketplace

Existing repository rule: Phase A explicitly does not start with a full skills marketplace.

Resolution:

- Do not import ECC's full skill library.
- Build a project-local capability and skill catalog for known repository skills only.
- Treat catalog output as diagnostics and routing help, not a marketplace.

### Conflict 2: ECC Hooks vs Codex/Phase A Security Boundary

Existing repository rule: workflow authority belongs to scripts, shared Codex entrypoints, and documented security profiles.

Resolution:

- Do not import ECC hook runtime.
- Convert useful hook ideas into explicit preflight checks, project-health checks, or runner-tier policy.
- Keep enforcement visible in scripts and tests.

### Conflict 3: ECC State Store vs Existing File And Sidecar Truth

Existing repository rule: logs, sidecars, decision logs, active-task summaries, and Phase A SQLite metadata are authoritative in their own domains.

Resolution:

- Do not introduce a second authoritative workflow database.
- If a Phase C state store is added, make it a derived index with source pointers and rebuild behavior.
- Decisions continue to live in `decision-logs/`; execution evidence continues to live under `logs/`.

### Conflict 4: Global Agent Install vs Project-Scoped Reproducibility

Existing repository rule: this project has strong local conventions, Windows-only assumptions, and shared LLM/Codex invocation entrypoints.

Resolution:

- Do not sync ECC or generated config into global user-home locations by default.
- Keep generated adapter outputs project-local or explicitly opt-in.
- Any global install must be documented as an operator action outside normal Phase C acceptance.

### Conflict 5: Multi-Agent/Worktree UX vs Current Runner Lock Model

Existing repository rule: Phase A allows at most one active heavy runner per project.

Resolution:

- Defer multi-worktree hosted orchestration until OS-level isolation, ACLs, storage abstraction, and runner queueing are complete.
- Start with status visibility and queue correctness, not collaboration UX.

### Conflict 6: Browser/API Convenience vs Workflow Authority

Existing repository rule: browser/API surfaces can trigger and observe but cannot reinterpret sidecar decisions.

Resolution:

- Any Phase C hosted command must delegate to repository-native scripts.
- Browser/API must display route decisions, stop-loss reasons, approval state, and artifact links without creating parallel decision logic.

### Conflict 7: Storage Abstraction vs Local Disk Simplicity

Existing repository rule: Phase A uses local disk because one node and one SQLite DB are enough.

Resolution:

- Build a storage interface with local filesystem as the first backend.
- Do not require object storage until workspace restore or worker expansion needs it.
- Preserve path safety, account/project ownership checks, and artifact source pointers across storage backends.

## Phase C Architecture Gate

Any Phase C implementation that changes thresholds, contracts, security posture, runner isolation, storage semantics, hosted entrypoint contracts, or release policy must create or update the ADR/overlay set before code work.

Minimum architecture artifacts before implementation:

- A Phase C decision log that records selected scope, rejected ECC imports, and risk posture.
- A Phase C architecture overlay or ADR update for runner isolation, storage abstraction, and derived state ownership.
- Test impact notes that name required regression suites before code work starts.

Recommended paths:

- `decision-logs/2026-06-24-phase-c-platform-hardening-route.md`
- `docs/architecture/overlays/PHASE-C-PLATFORM-HARDENING/08/08-Phase-C-Platform-Hardening-Architecture.md`
- `docs/architecture/overlays/PHASE-C-PLATFORM-HARDENING/08/ACCEPTANCE_CHECKLIST.md`

This gate is stricter than C0 cross-linking because Phase C touches host security boundaries and workflow authority.

## Phase C Dependency Gates

Phase C workstreams should not be implemented as an unordered checklist.

| Gate | Required before | Reason |
|---|---|---|
| C0 complete | Any C1-C8 implementation | Phase status and ECC absorption boundaries must be explicit before implementation. |
| C1 minimum schema | C2, C3, C7 | Doctor, hosted entrypoint inventory, and derived state index need the same capability vocabulary. |
| C3 hosted entrypoint decision | Any hosted formal Chapter 6/7 route | Browser/API routes cannot expose formal workflow commands without explicit authority and security decisions. |
| C4 account boundary tests | Production multi-user posture | Token, audit, deletion, and admin browser boundaries must be tested before stronger claims. |
| C5 OS-level isolation | C8 strong-isolation runner tier and multi-worktree hosted orchestration | Strong isolation and concurrency should build on working ACL and runner identity rules. |
| C6 restore contract | Worker expansion and object-backed storage | Scale-out must preserve workspace ownership, artifact readback, and recovery. |
| C7 derived state ownership | Operator dashboards that merge runs, skills, decisions, and governance events | Dashboards must stay rebuildable and source-linked. |

## Phase C Recommended Workstreams

### C0: Phase Alignment Baseline

Goal: make Phase C planning explicit before implementation.

Deliverables:

- This document.
- Cross-links from workflow and project documentation indexes.
- A Phase C decision log before implementation.
- Architecture overlay or ADR update before any Phase C code work that changes runner isolation, storage abstraction, hosted entrypoint contracts, derived state ownership, or security posture.

Acceptance:

- Phase A complete items, Phase B complete items, and deferred items are clearly separated.
- ECC absorption is documented as selective pattern adoption, not dependency adoption.

### C1: Project-Local Agent Asset Catalog

Goal: make agent/workflow assets discoverable and diagnosable.

Deliverables:

- Capability inventory schema.
- Generated capability catalog covering docs, scripts, tests, logs, runtime variables, and safety profile.
- Dry-run command that reports missing or stale assets.

Minimal schema fields:

| Field | Required | Purpose |
|---|---|---|
| `capability_id` | Yes | Stable identifier for the capability. |
| `owner_doc` | Yes | Authoritative source document for intent and boundaries. |
| `entrypoints` | Yes | Script, CLI, API, or browser-triggered entrypoints. |
| `evidence_paths` | Yes | Logs, summaries, sidecars, reports, or dashboards produced by the capability. |
| `security_profile` | Yes | Required or allowed delivery/security profile. |
| `callable_from_browser` | Yes | Whether browser UI may trigger the capability. |
| `callable_from_api` | Yes | Whether Web API may trigger the capability. |
| `callable_from_cli` | Yes | Whether CLI may trigger the capability. |
| `generated_assets` | No | Derived files that doctor/repair may regenerate. |
| `doctor_checks` | No | Checks that validate source references, generated assets, and runtime assumptions. |

Acceptance:

- Catalog can answer which capabilities are browser/API/CLI callable.
- Catalog can distinguish source files from generated assets.
- Catalog does not move execution authority out of scripts.

### C2: Agent Asset Doctor And Repair

Goal: make derived agent assets recoverable.

Deliverables:

- Doctor check for skill references, capability manifests, project-health artifacts, Codex adapter references, and runtime config placement.
- Repair mode for generated indexes only.
- Evidence under `logs/`.

Acceptance:

- Doctor is safe to run repeatedly.
- Repair does not mutate authored source docs except through explicit future implementation tasks.

### C3: Phase A Hosted Entrypoint Closeout

Goal: close remaining script-first hosted entrypoint gaps.

Current evidence:

- Existing project-health support includes `py -3 scripts/python/dev_cli.py project-health-scan`, `scripts/python/project_health_scan.py`, project-health schemas, examples, and Phase A artifact readback references.
- Existing Phase B smoke support includes `scripts/python/phase_b_account_smoke.py`.
- Existing Phase A platform command builders and artifact indexers already call selected repository-native entrypoints.
- Missing or not yet stable as standalone script contracts: `workspace-bootstrap-check`, `describe-task-tools`, `run-artifact-index-refresh`, `run-hosted-resume`, `run-hosted-task`, `export-active-task-summary`, and approval readback/sync.

Recommended C3 order:

1. `describe-task-tools` or equivalent capability catalog export.
2. `workspace-bootstrap-check` for hosted worker readiness.
3. `run-artifact-index-refresh` for stable browser/API readback.
4. `export-active-task-summary` for compact recovery and operator views.
5. `run-hosted-resume` and approval readback/sync.
6. `run-hosted-task`, only after the formal Chapter 6 exposure decision is made.

Deliverables:

- Machine-readable hosted tool description.
- Hosted bootstrap readiness check.
- Artifact index refresh entrypoint.
- Hosted resume and approval readback/sync entrypoints.
- Decision on whether `run-hosted-task` exposes formal Chapter 6 or remains prototype-only.

Acceptance:

- Each entrypoint delegates to existing repository-native commands.
- Each entrypoint emits JSON and writes evidence under `logs/`.
- Each entrypoint documents caller surfaces and forbidden caller surfaces in the capability catalog.

### C4: Phase B Production Identity And Admin Testing

Goal: harden account management beyond prototype token administration.

C4 should be split into two lanes:

- C4a hardening: user deletion behavior, cascade rules, auth middleware integration tests, admin management browser E2E, richer LLM audit export filters, and pagination.
- C4b identity product decision: password login, password reset, OAuth, OIDC, self-service registration, signed invite tokens, or continued admin-issued tokens.

Deliverables:

- User deletion behavior and cascade rules.
- Full auth middleware integration tests.
- Admin management browser E2E.
- Richer LLM audit export filters and pagination.
- Decision on password login vs OAuth/OIDC/self-service registration.

Acceptance:

- Account boundaries are tested at API and browser levels.
- C4a can ship without C4b if admin-issued tokens remain the accepted pre-production identity model.
- Token material and provider secrets remain absent from logs and docs.

### C5: OS-Level Runner Isolation

Goal: move from application-only isolation to host-enforced isolation.

Deliverables:

- Separate Windows account plan for platform and runners.
- Project-level NTFS ACL model.
- Runner process identity rules.
- Caddy/platform binary/metadata DB write-protection checks.
- Recovery procedure for permission drift.

Acceptance:

- A runner cannot write platform binaries, metadata DB, Caddy configuration, or another account's workspace.
- Application checks and OS checks both enforce boundaries.

### C6: Storage Abstraction And Restore

Goal: make workspace and artifact restoration independent of one local machine.

Deliverables:

- Storage abstraction design for artifacts and durable docs.
- Local filesystem backend as the first implementation.
- Restore manifest format with account/project/workspace ownership.
- Migration plan for future object-backed storage.

Acceptance:

- Existing local disk behavior remains the default.
- Restore is tested without rewriting repository workflow logic.

### C7: Minimal Operational Telemetry And Derived State Index

Goal: expose useful operator state without building a second workflow engine.

C7 should be split into three sub-slices:

- C7a event schema: define the minimal telemetry events and stable field names.
- C7b derived state index: map runs, skills, decisions, governance events, and work items back to authoritative files or Phase A DB rows.
- C7c operator dashboard: summarize readiness, recent failures, stop-loss, approvals, and project-health remediation.

Deliverables:

- Event schema for the minimal telemetry set.
- Derived state index that maps runs, skills, decisions, governance events, and work items back to authoritative files or Phase A DB rows.
- Operator summary dashboard for readiness, recent failures, stop-loss, approvals, and project-health remediation.

Acceptance:

- C7a can be implemented without C7b/C7c.
- State index is rebuildable.
- Decisions and workflow evidence remain in their authoritative locations.

### C8: Strong-Isolation Runner Tier

Goal: evaluate and introduce stronger runner isolation for high-risk accounts or workflows.

Deliverables:

- Evaluation of containers, Windows Sandbox, lightweight VMs, or equivalent host-safe isolation.
- Runner tier policy.
- Cost and performance notes.
- Fallback to ACL-isolated local runner.

Acceptance:

- Strong-isolation runners can augment or replace the local runner without breaking workspace ownership, artifact indexing, or recovery.

## Non-Goals

Phase C should not:

- Rewrite repository workflows into a new orchestration engine.
- Import ECC as a full global install.
- Add a broad skills marketplace.
- Import generic MCP servers without a workflow-owned need.
- Make browser/API surfaces reinterpret sidecar decisions.
- Treat object storage as mandatory before a local backend abstraction exists.
- Expose formal Chapter 3-7 hosted execution without a specific product and security decision.

## Open Decisions

| Decision | Blocks | Notes |
|---|---|---|
| Which identity route is preferred for pre-production: username/password, OAuth/OIDC, signed invite token, or admin-issued token continuation? | C4b and production identity posture | C4a hardening can proceed if admin-issued tokens remain the accepted interim model. |
| Which runner isolation technology is realistic on the current Windows host: separate Windows accounts only, Windows Sandbox, containers, lightweight VMs, or a hybrid? | C5 and C8 | C5 can start with Windows account and NTFS ACL design; C8 needs the stronger isolation decision. |
| Should Phase C introduce object storage immediately, or only design the interface and keep local filesystem as the only backend? | C6 worker expansion and object-backed restore | Local filesystem should remain the first backend unless restore or scale-out forces earlier object storage. |
| Where should the derived state index live: Phase A SQLite, separate SQLite, JSON under `logs/`, or generated project-health artifacts? | C7 and operator dashboard implementation | The index must remain rebuildable and source-linked regardless of storage location. |
| Which hosted formal delivery routes, if any, should move beyond prototype lane in Phase C? | C3 hosted formal route exposure | Formal Chapter 6/7 routes require explicit authority and security decisions before browser/API exposure. |
| What is the project-local schema for agent capability inventory? | C1, C2, C3, C7 | This is the shared vocabulary for catalog, doctor, hosted entrypoint inventory, and derived state. |
| Which Codex adapter artifacts should be generated, and which should remain human documentation only? | C1/C2 adapter checks and Codex governance | Generated artifacts should stay project-local unless an operator explicitly opts into global install. |

## Translation Follow-Up

This document is the English baseline requested first. A Chinese translation should be created only after this baseline is accepted, and all Chinese documentation reads/writes must follow the repository UTF-8 documentation rule.

## One-Sentence Rule

Phase C should make the hosted platform portable, isolated, observable, and diagnosable while keeping repository scripts, sidecars, and documented workflow rules as the only execution authority.
