# Phase C Platform Hardening And Agent Asset Governance Backlog

Status: Draft skeleton
Date: 2026-06-24
Source plan: `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance.md`
Scope: Phase C backlog for production hardening, deferred Phase A/B closure, and ECC-style agent asset governance.

## Backlog Rules

- Treat Phase C as security, isolation, authority, and governance hardening first; do not use it as a feature-expansion bucket.
- Keep repository scripts and validators as execution authority unless an ADR explicitly moves authority into PhaseA.Platform.
- Keep secrets out of git-tracked docs, logs intended for browser/API readback, and agent-readable summaries.
- Preserve account-scoped readback and package/asset ticket ownership checks from Phase B.
- Do not make ECC or any external repository a runtime dependency. ECC remains a pattern source only.
- Task ids mirror the source plan C0-C8 sections. Do not reuse a C-number for a different topic.
- P0 below means first implementation batch for this backlog, not a currently known production P0 blocker. The source plan still states that no P0 blocker is known in the current Phase C baseline.

## Global Definition Of Done

The Phase C backlog is complete only when:

- Security-sensitive changes cite or update the relevant ADRs.
- Runner isolation and filesystem boundary tests prove platform binaries, metadata DB, Caddy config, and user workspaces have the intended write boundaries.
- Admin/user readback continues to pass Phase B account-boundary smoke tests.
- Agent asset catalog state is machine-readable and recoverable from repository-native files or sidecars.
- External tools, MCP surfaces, and hosted entrypoints are inventoried with owner, purpose, allowed workflows, auth source, and secret source.
- New browser/admin surfaces have automated smoke or browser E2E coverage before being marked complete.
- `git diff --check` passes.

## Cross-Task Gates

- No hosted formal Chapter 3-7 route should be exposed before C0/C1/C3 authority and entrypoint gates are complete.
- No browser/admin/evidence readback expansion should ship before C0-02 secret and raw evidence boundary rules exist.
- No stronger runner isolation claim should be made before C5 filesystem and account-boundary evidence exists.
- No agent asset action should be exposed in browser/admin UI before C1 catalog, C2 doctor, and rollback rules exist.
- No external MCP or integration should be enabled before C1-02 inventory and allowlist rules exist.
- C7 dashboard work must consume C7a event schema and C7b derived state index outputs, not invent state ownership.

## P0 First Implementation Batch

### C0-01 Phase Alignment And Authority Baseline

Depends on: none within this backlog.

Objective: Lock the Phase C authority model so platform, browser, scripts, route state, sidecars, and agent assets do not become competing workflow engines.

Primary outputs:

- Phase C authority decision note or ADR update.
- Updated links from the Phase C plan if authority rules move to an ADR.

Acceptance:

- Scripts/validators remain execution authority unless an ADR says otherwise.
- Browser/API surfaces are trigger/readback/control surfaces, not workflow truth sources.
- Formal Chapter 3-7 hosted route exposure remains blocked until explicit product-lane decision.

### C0-02 Secret And Raw Evidence Boundary

Depends on: C0-01.

Objective: Define production-grade handling for secrets, token hashes, raw logs, raw evidence, provider credentials, and browser/admin readback.

Primary outputs:

- Secret/evidence handling contract or ADR update.
- Redaction/readback requirements linked from Phase B evidence rules.

Acceptance:

- Real secrets are not stored in git-tracked docs or browser-visible logs.
- Raw evidence and raw logs have server-side ownership metadata and are not exposed by default.
- Admin summary readback cannot expose raw command logs, provider keys, token material, or raw prompt bodies.

### C1-01 Project-Local Agent Asset Catalog

Depends on: C0-01, C0-02.

Objective: Create an ECC-inspired project-local catalog for repo-local agent/workflow assets such as skills, prompt contracts, workflow helpers, MCP configs, hosted entrypoint prompts, generated indexes, and runtime config references.

Primary outputs:

- Agent capability inventory schema.
- Catalog generator or validator script.

Acceptance:

- Catalog records capability id, owner doc, entrypoints, evidence paths, security profile, browser/API/CLI callable flags, generated assets, and doctor checks.
- Catalog can distinguish source files from generated assets.
- Catalog does not install, sync, or mutate global user-level assets automatically.

### C3-01 Hosted Entrypoint Inventory And Safety Gate

Depends on: C0-01, C0-02, C1-01.

Objective: Inventory all hosted machine-callable entrypoints before adding or exposing more hosted workflow routes.

Primary outputs:

- Hosted entrypoint inventory document or JSON catalog.
- Validator for entrypoint owner, purpose, allowed inputs, outputs, sandbox, read/write behavior, and evidence path.

Acceptance:

- Every hosted entrypoint has owner, purpose, command source, sandbox/read-write behavior, evidence outputs, and account-boundary notes.
- Unknown entrypoints are blocked from browser/API exposure.
- Existing Codex/LLM shared invocation rules remain the only supported subprocess construction path.

### C4a-01 Account Lifecycle And Admin Hardening

Depends on: C0-02.

Objective: Close deferred Phase B account lifecycle and admin testing gaps that affect pre-production readiness while retaining the current admin-issued-token model unless C4b changes it.

Primary outputs:

- User deletion or deactivation retention policy.
- Full HTTP auth middleware integration test plan.
- Admin management browser E2E scope.
- LLM audit export filter/pagination plan.

Acceptance:

- User deletion/deactivation behavior is deterministic and audited.
- Auth middleware tests cover user/admin boundaries and forbidden cross-account access.
- Admin management browser flows have smoke or E2E coverage before being marked complete.
- LLM audit exports do not leak token material or raw provider credentials.

### C5-01 Windows Runner Account And NTFS ACL Design

Depends on: C0-01, C0-02, C4a-01.

Objective: Design and prove the minimum Windows account/ACL model for separating platform binaries, metadata DB, Caddy config, and user workspaces.

Primary outputs:

- Runner isolation design note or ADR update.
- ACL test plan and fixture script.

Acceptance:

- Runner process cannot write platform binaries, metadata DB, Caddy config, or other users' workspaces.
- Platform process can manage metadata and orchestration without granting user-task write privileges to platform-owned files.
- ACL evidence is captured under `logs/` and is safe for admin readback after sanitization.

## P1 Hardening And Governance Expansion

### C2-01 Agent Asset Doctor And Repair

Depends on: C1-01.

Objective: Add doctor-style validation for agent assets without importing ECC wholesale.

Primary outputs:

- Agent asset doctor script or validator.
- Repair-plan output schema.

Acceptance:

- Doctor reports missing files, invalid manifests, stale references, unsafe external actions, and unsupported runtime assumptions.
- Repair output is a plan or patch proposal, not automatic global mutation.
- Doctor output can be linked from project-health or admin readback.

### C1-02 External Tool And MCP Inventory

Depends on: C1-01, C0-02.

Objective: Inventory external tools, MCP surfaces, and integrations with explicit allowed workflows and secret boundaries.

Primary outputs:

- External action inventory schema.
- Inventory validator.

Acceptance:

- Each entry records owner, purpose, auth source, secret source, network boundary, allowed workflows, and failure behavior.
- Unknown external actions are treated as blocked for hosted workflows.
- MCP is not treated as hidden workflow authority.

### C4b-01 Identity System Decision

Depends on: C4a-01.

Objective: Decide whether Phase C adds username/password login, password reset, OAuth/OIDC, signed invite tokens, or remains token-administered for the next production slice.

Primary outputs:

- Identity decision note or ADR.
- Browser/admin E2E scope if identity UX changes.

Acceptance:

- Decision records threat model, operational cost, recovery behavior, and migration impact.
- If login UX changes, browser E2E is required before completion.
- C4a can ship independently if admin-issued tokens remain the accepted interim model.

### C6-01 Storage Abstraction And Restore Contract

Depends on: C0-02, C5-01.

Objective: Make workspace and artifact restoration independent of one local machine while keeping local filesystem as the first backend.

Primary outputs:

- Storage abstraction design for artifacts and durable docs.
- Restore manifest format with account/project/workspace ownership.
- Migration plan for future object-backed storage.

Acceptance:

- Existing local disk behavior remains the default.
- Restore is tested without rewriting repository workflow logic.
- Restore manifest preserves account/project/workspace ownership.

### C7a-01 Minimal Telemetry Event Schema

Depends on: C0-01, C0-02, C1-01.

Objective: Define minimal telemetry events and stable field names for operational observability, not growth analytics.

Primary outputs:

- Event schema for minimal telemetry set.
- Validator or fixture examples for event shape.

Acceptance:

- Events are minimal and source-linked.
- Events do not include secrets, raw prompts, token material, or raw command logs.
- C7a can ship without C7b/C7c.

### C7b-01 Derived State Index

Depends on: C7a-01, C1-01, C2-01, C3-01.

Objective: Map runs, skills, decisions, governance events, and work items back to authoritative files or Phase A DB rows without becoming a new source of truth.

Primary outputs:

- Derived state index schema.
- Rebuild or validation script.

Acceptance:

- State index is rebuildable.
- Decisions and workflow evidence remain in their authoritative locations.
- Missing/stale source references are represented explicitly.

## P2 Operator Experience And Stronger Isolation Evaluation

### C7c-01 Operator Dashboard

Depends on: C7a-01, C7b-01.

Objective: Summarize readiness, recent failures, stop-loss, approvals, and project-health remediation after event and derived-state contracts exist.

Primary outputs:

- Admin dashboard requirements or UI contract.
- Project-health/readback projection plan.

Acceptance:

- Dashboard consumes generated catalogs, derived state, and sanitized evidence only.
- Dashboard does not become an authority source.
- Account/admin boundaries are tested.

### C8-01 Stronger Runner Isolation Tier Evaluation

Depends on: C5-01, C6-01.

Objective: Evaluate stronger isolation tiers after the minimum Windows account/ACL model and restore contract are proven.

Primary outputs:

- Isolation tier evaluation note.
- Cost/risk/operation comparison.

Acceptance:

- Evaluation compares local runner accounts, stronger Windows isolation, Windows Sandbox, containers, lightweight VMs, and remote/ephemeral runner options where relevant.
- Recommendation preserves existing script and evidence authority model.
- No stronger-isolation claim is made without test evidence.

### C2-02 Agent Asset Lifecycle UX

Depends on: C1-01, C2-01, C1-02, C7b-01.

Objective: Add operator UX for catalog, doctor, repair-plan, and external action inventory after machine-readable governance exists.

Primary outputs:

- Browser/admin UX contract.
- E2E or smoke coverage plan.

Acceptance:

- UX displays catalog/doctor/inventory state from generated artifacts.
- UX does not perform destructive agent asset changes without explicit review and evidence.
- UX respects account/admin authorization boundaries.
