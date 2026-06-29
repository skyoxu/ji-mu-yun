# Roadmap And Hardening Architecture

## Intent

This note keeps the implemented Phase service architecture aligned with the Phase B and Phase C roadmap. It prevents future agents from describing deferred security, identity, isolation, storage, and governance work as already complete.

## Current Phase A/B State

Phase A completed the hosted single-node prototype platform core, while final public deployment closure remains a deployment-time follow-up:

- ASP.NET Core Web/API and browser UI.
- SQLite metadata store.
- Hosted workspace management.
- Project creation and prototype routes.
- Runner queues and project-scoped heavy-run serialization.
- Artifact, package, asset, GDD, preview, project-health, and run readback.
- LLM binding, usage summaries, and shared LLM/Codex entrypoints.
- Runtime scripts and Caddy reverse-proxy configuration.

Phase B completed the current prototype-hardening account slice:

- Account-scoped admin/user token model.
- Database-backed user tokens stored as hashes.
- Admin user creation, disable/enable, token rotation, account limits, audit events, CSV export.
- Account-scoped project, run, artifact, package, asset, chat, workflow, and LLM usage readback.
- Phase B smoke verification for unauthenticated rejection and authorized access.

Phase B also defines machine-closed governance direction for AGF/godogen absorption:

- Readiness catalogs must be generated and evidence-backed.
- Prototype routes are contracted, not implied.
- Evidence bundles, route ledgers, sidecars, asset manifests, and diagnostics should be validator-backed.
- Human review may produce artifacts, but cannot be the system-of-record acceptance gate.

## Deferred Inputs To Phase C

The roadmap explicitly defers:

- User deletion and cascade rules.
- Full auth middleware integration tests.
- Admin management browser E2E.
- Full LLM audit export filters and pagination.
- Username/password login, password reset, OAuth/OIDC, invite flows, or self-service registration.
- Separate Windows accounts for platform and runners.
- Project-level NTFS ACLs.
- OS write-permission separation between platform binaries, metadata DB, Caddy config, and user workspaces.
- Stronger runner isolation beyond application-level account checks.
- Storage abstraction and restore contracts.
- Worker expansion, node affinity, object-backed storage, containers, Windows Sandbox, lightweight VMs, or other strong-isolation runners.
- Project-local agent asset catalog, doctor/repair, MCP inventory, external action governance, and derived state indexes.

## Phase C Architecture Direction

Phase C is hardening and governance first, not a feature-expansion bucket.

Primary goals:

- Preserve repository scripts and validators as execution authority unless an ADR explicitly moves authority.
- Harden identity and admin workflows.
- Add OS-level runner isolation and NTFS ACL enforcement.
- Add storage abstraction and restore semantics before scale-out.
- Add project-local agent asset catalog and doctor checks without importing ECC as a runtime dependency.
- Add minimal operational telemetry and derived state indexes from generated evidence.
- Evaluate stronger runner tiers only after ACL and restore contracts are proven.

## Dependency Gates

- C0 alignment and authority baseline must come before other Phase C implementation.
- Capability catalog schema should precede doctor/repair and hosted entrypoint inventory.
- Account boundary tests should precede production multi-user claims.
- OS-level isolation should precede strong-isolation runner claims and multi-worktree hosted orchestration.
- Storage restore contract should precede worker expansion or object-backed storage.
- Derived state ownership should precede dashboards that merge runs, skills, decisions, and governance events.

## Invariants

- Do not rewrite repository workflows into a new orchestration engine.
- Do not import external pattern repositories as runtime dependencies.
- Do not expose formal hosted execution lanes without explicit product and security decisions.
- Do not let browser/API surfaces reinterpret sidecar decisions.
- Do not claim production multi-tenant security before OS-level boundaries and tests exist.

## Change Rules

- Any Phase C implementation that changes thresholds, contracts, security posture, runner isolation, storage semantics, hosted entrypoint contracts, or release policy must create or update an ADR/overlay before code work.
- Roadmap docs must distinguish implemented, prototype-hardening complete, deferred, and proposed work.
- New governance artifacts must be generated from source-linked evidence, not hand-maintained status claims.

## Source Roadmap Documents

- `docs/workflows/phase-b-account-isolation.md`
- `docs/workflows/phase-b-agf-godogen-absorption.md`
- `docs/workflows/phase-b-agf-godogen-implementation-backlog.md`
- `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance.md`
- `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance-backlog.md`
- `docs/workflows/cloud-platform-evolution-plan.md`
- `docs/workflows/cloud-user-telemetry-and-feedback-plan.md`
