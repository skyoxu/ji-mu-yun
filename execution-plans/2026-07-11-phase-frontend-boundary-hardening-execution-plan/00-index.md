# Phase Platform Boundary Hardening Split Index

Status: Primary split implementation plan for Phase platform trust, React migration, internal architecture, version, and evidence governance.

## Authority

- The top-level execution plan is the recovery entry and metadata owner.
- This directory is the implementation detail authority.
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/` remains the authority for GDD-to-module business contracts and route semantics.
- This plan receives the Phase-facing behavior formerly named 7-12 R4. BH-SF2 owns the account/project/workspace-bound Bootstrap review adapter, BH-SF3 keeps review facts separate from mutation and acceptance authority, and BH-PILOT owns the first bounded observation using existing PBR-026, PBR-044, PBR-024, and PBR-062.
- This plan is strictly downstream. No implementation task, protected-path change, React/DB/Gate/runtime work or legacy freeze may start until BH-HANDOFF proves the upstream Phase 0-6/global-review/closure/final-commit package complete.
- After handoff, every downstream business-facing projection resolves through the immutable UpstreamHandoffManifest plus the unique active-registry event chain; downstream-derived API/frontend/persistence observations are technical snapshots with source refs, never new business authority.
- New durable rules move to accepted ADRs, `docs/standards/**`, `docs/architecture/phase-service/**`, or relevant workflow docs when implemented.
- No split book may redefine the upstream status vocabulary, action catalog, route-state schema, diagnostic taxonomy, UI capability/style contract, or GDD workflow.

## Reading Order

1. [Authority, Threat Model, And Gates](01-authority-threat-model-and-gates.md)
2. [Permit Trust And Attestation](02-permit-trust-and-attestation.md)
3. [Profiles, Preflight, And Containment](03-profiles-preflight-and-containment.md)
4. [Mutation Lease, Journal, And Acceptance](04-mutation-lease-journal-and-acceptance.md)
5. [React UI-V2 Migration](05-react-ui-v2-migration.md)
6. [Platform Architecture, Data, And Version](06-platform-architecture-data-and-version.md)
7. [Evidence, Telemetry, And Performance](07-evidence-telemetry-and-performance.md)
8. [Implementation Phases](08-implementation-phases.md)
9. [Risks, Definition Of Done, And Glossary](09-risks-dod-and-glossary.md)
10. [Global Review And Split Validation](96-global-review-and-split-validation.md)
11. [Post-Split Requirements Ledger](97-post-split-requirements-ledger.md)
12. [Original-To-Split Audit](98-original-to-split-audit.md)
13. [Source Coverage](99-source-coverage.md)

## Machine Contracts And Plan Validation

- `schemas/bootstrap-handoff-contract.v1.schema.json`
- `schemas/upstream-handoff-manifest.v1.schema.json`
- `schemas/upstream-handoff-state-event.v1.schema.json`
- `schemas/upstream-handoff-active-registry.v1.schema.json`
- `schemas/upstream-completion-snapshot.v1.schema.json`
- `schemas/handoff-source-map.v1.schema.json`
- `schemas/downstream-observation-snapshots.v1.schema.json`
- `schemas/finding-closure-registry.v1.schema.json` and generated `schemas/finding-closure-registry.v1.json`
- `schemas/original-requirement-family-registry.v1.schema.json` and fixture
- Plan-readiness command: `py -3 execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/tools/validate_whole_directory.py`

## Change Rules

- Every normative change names one owning book.
- Cross-book summaries link to the owner and do not copy full requirements.
- Security trust decisions require ADR and second reviewer.
- React business behavior consumes upstream fixtures plus a handoff-bound downstream API observation snapshot; it does not require upstream to add OpenAPI/surface registries and never becomes a workflow authority.
- Each implementation task records book/section refs, owner, approver, Gate, Permit, tests, evidence, rollback, and expiry for any exception.
- Each downstream implementation task records the same UpstreamHandoffManifest ID/hash, handoffEpoch, selected StateEvent hash and UpstreamHandoffActiveRegistry rowVersion; absence or drift blocks start/heartbeat/apply/Postflight.
- The split/cross-plan overlap validator, its mutation fixtures and bootstrap rule digest are frozen before the handoff-only task; that task may run them but cannot modify them. They run on every later plan change and phase exit.
- A split validator must fail on missing books, broken links, duplicate authority, top-level normative drift, or uncovered post-split requirements.
- AGENTS.md receives truthful transitional routing before implementation; AGENTS/README and durable standards are updated in the same phase change when behavior actually lands.
