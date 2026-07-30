# ADR Index - Phase Service

This index tracks Phase service ADRs for the hosted Phase A/B platform and Phase C evolution path. It is separate from `docs/architecture/ADR_INDEX_GODOT.md`, which remains focused on the Windows-only Godot + C# template baseline.

## Accepted

- ADR-0032: Phase Service Hosted Shell Over Repository Workflow Kernel - `docs/adr/ADR-0032-phase-service-hosted-shell.md`
- ADR-0033: SQLite Metadata And Local Disk Workspaces For Phase A/B (includes versioned admin-review queue/history) - `docs/adr/ADR-0033-phase-metadata-sqlite-local-disk.md`
- ADR-0034: Account-Scoped Token Auth For Phase B Prototype Hardening - `docs/adr/ADR-0034-phase-account-scoped-token-auth.md`
- ADR-0035: Controlled Runner And Workspace-Bound Execution - `docs/adr/ADR-0035-phase-controlled-runner-workspace-execution.md`
- ADR-0036: Prototype Route Recovery Authority And Machine-Closed Acceptance - `docs/adr/ADR-0036-phase-prototype-route-recovery-authority.md`
- ADR-0037: Shared LLM And Codex Execution Entrypoints - `docs/adr/ADR-0037-phase-shared-llm-codex-entrypoints.md`
- ADR-0038: Evidence Sidecars And Account-Scoped Readback (includes source-boundary manifests, hash verification, and raw-prompt exclusion) - `docs/adr/ADR-0038-phase-evidence-sidecars-readback.md`
- ADR-0039: Phase Runtime, Caddy, And Recovery Order - `docs/adr/ADR-0039-phase-runtime-caddy-recovery.md`
- ADR-0044: Knowledge Projection Authority And E2 Hosted Context Envelope (extends ADR-0037; complements ADR-0038; supersedes neither) - `docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md`
- ADR-0046: Knowledge Context Protected Integration Merge Decision (extends ADR-0044; preserves the 2026-07-11 BH-HANDOFF boundary) - `docs/adr/ADR-0046-knowledge-context-protected-integration-merge.md`
- ADR-0047: E2 Hosted Context Readiness Declaration (extends ADR-0044 readiness evidence; does not authorize operational deployment) - `docs/adr/ADR-0047-e2-hosted-context-readiness-declaration.md`
- ADR-0048: Repository Knowledge Locator Workflow Consumption (extends ADR-0044; complements ADR-0037/0041/0043; supersedes none) - `docs/adr/ADR-0048-repository-knowledge-locator-workflow-consumption.md`
- ADR-0049: Bootstrap Controller-Owned Coverage And Attempt Retry (extends ADR-0041; complements ADR-0045; supersedes neither) - `docs/adr/ADR-0049-bootstrap-controller-owned-coverage-and-attempt-retry.md`
- ADR-0050: Knowledge Publication LKG Recovery And Generation Retention (extends ADR-0048; complements ADR-0044; supersedes neither) - `docs/adr/ADR-0050-knowledge-publication-lkg-recovery-and-generation-retention.md`
- ADR-0051: Bootstrap Lineage Family And Bounded Repair Re-entry (extends ADR-0041; complements ADR-0045/0049; supersedes none) - `docs/adr/ADR-0051-bootstrap-lineage-family-and-bounded-repair-reentry.md`

## Proposed

- ADR-0040: Phase C Hardening Before Scale-Out - `docs/adr/ADR-0040-phase-c-hardening-before-scaleout.md`

## Related Architecture

- `docs/architecture/phase-service/_index.md`
- `docs/architecture/overlays/PHASE-A-CLOUD-RUNNER/08/08-Phase-A-Cloud-Runner-Architecture.md`
- `docs/workflows/phase-b-account-isolation.md`
- `docs/workflows/phase-b-agf-godogen-absorption.md`
- `docs/workflows/phase-b-agf-godogen-implementation-backlog.md`
- `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance.md`
- `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance-backlog.md`


## Change Policy

Create or update a Phase ADR before changing any of these boundaries:

- Workflow authority between repository scripts, route services, browser/API surfaces, and platform orchestration.
- Metadata storage, workspace storage, restore semantics, or object-storage migration.
- Authentication, account scoping, token handling, audit visibility, or admin/user authority.
- Runner execution, sandboxing, OS isolation, concurrency limits, or hosted process allowlists.
- LLM/Codex provider routing, sandbox mode, prompt transport, billing, credential, retry, or output handling.
- Evidence readback, redaction, readiness status, route acceptance, or generated sidecar semantics.

Proposed ADRs are planning baselines, not implementation authority. Before code relies on a Proposed ADR, accept that ADR or create a narrower Accepted ADR for the implemented decision.

Update the lightweight architecture notes when implementation shape changes but the decision remains the same. Update `AGENTS.md` only for concise non-negotiable agent rules and route deeper rationale here.
