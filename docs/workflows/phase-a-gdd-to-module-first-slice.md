# Phase A GDD-To-Module Recommended First Slice

Status: Living workflow standard
Language: English
Slice ID: `phase-a-gdd-to-module-recommended-first-slice`
Scope: Phase A GDD-to-module hardening first implementation slice, Phase 0A/0B ordering, Phase 1 minimum route scope, full-target capability schedule, and source-history readiness.

## Authority

This document is the durable workflow source for `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/10-recommended-first-slice.md`. The machine-readable registry is `PhaseA.Platform/Workflow/GddToModuleFirstSlice.cs`.

Related durable sources:

- `docs/workflows/phase-a-gdd-to-module-implementation-phases.md`
- `docs/workflows/phase-a-gdd-to-module-risk-dod-open-questions.md`
- `docs/standards/phase-service.md`
- `docs/standards/godot-engine-semantics.md`
- `docs/standards/godot-ui-capability-contract.md`
- `docs/standards/godot-ui-style-contract.md`
- `docs/standards/godot-ui-style-closure.md`
- `docs/standards/godot-ui-style-schema-acceptance.md`
- `docs/standards/godot-diagnostics-quality-gates.md`
- `docs/schemas/gdd-to-module-first-slice-review.v1.example.json`
- `docs/schemas/full-target-ui-closure-ledger.v1.example.json`

## Ordering Rule

Phase 1 work must not start until Phase 0A exit criteria pass. Phase 0A exit requires every mandatory baseline item in `GddToModuleFirstSlice.Phase0AMandatoryBaseline` and zero unresolved P0/P1/P2 findings in the phase review.

Phase 0B items are route-dependent. A touched Phase 1 route must declare its active Phase 0B dependencies in phase review evidence before it consumes engine semantics, UI capability, UI style, diagnostics, visual evidence, or full-target closure packages. Missing required Phase 0B packages are blockers for that touched route, not cleanup work.

## Phase 0A Mandatory Baseline

Phase 0A covers the governance primitives that must exist before the first route-hardening slice:

- Route module contract template and action descriptor registry.
- Path/readback, no-store, exposure-class, context-boundary, account-boundary, and duplicate-run/idempotency rules.
- Canonical prototype-contract path policy.
- Source-boundary schema and prompt-evidence rules.
- Dimensioned status vocabulary.
- Admin review queue with metadata DB query ownership.
- Complete canonical workflow action mapping.
- Package-download versus final-readiness boundary.
- Scoped exemption semantics.
- Diagnostic spool minimum schema, failure families, and retention.
- Evidence ref kind fixture parity.
- Secret redaction validator.
- ADR/decision-log gate.
- Shared LLM/Codex entrypoint guard.
- Structured game-type metadata hash ownership.
- Phase service standards sync checklist.

The complete stable item inventory is in `GddToModuleFirstSlice.Phase0AMandatoryBaseline`.

## Phase 0B Route-Dependent Baseline

Phase 0B packages are required before touched routes depend on them:

- Godot engine semantic baseline.
- Godot UI capability contract.
- Godot UI style contract.
- Godot diagnostics and quality-gate contract.
- Durable review evidence under `logs/`.
- Phase 0B dependency matrix in phase review evidence.

The complete stable item inventory is in `GddToModuleFirstSlice.Phase0BRouteDependentBaseline`.

## Smallest Phase 1 Slice

The first Phase 1 slice reduces GDD-to-module drift without forcing the complete UI target into early route work. It includes:

- `GameDesignRequirementMapService` through `ILlmRouteEngine`.
- GDD document-generation write-through source hash.
- Requirement map API/readback.
- Artifact-local source hashes and API/readback projections.
- UI capability/style/source-boundary version fields.
- Stale detection and frontend banners.
- Route module contract template application for touched Phase 1 routes.
- Prototype-skeleton compatibility guard.
- Workflow recommendation phase-eligibility tests.
- Guard tests across path, hash, source-boundary, status, evidence, UI/style/diagnostic, readiness, exemption, redaction, shared-entrypoint, and source-history rules.
- Minimum deckbuilder GDD to requirement map to fresh contract chain tests.

The first-slice review evidence uses `docs/schemas/gdd-to-module-first-slice-review.v1.example.json`.

## Full-Target Capability Schedule

The full TapTapMarker non-technology UI capability target remains authoritative, but Phase 1 does not need to prove every advanced style family, lifecycle rule, virtualization path, localization path, toast behavior, custom-style negative path, or full visual-evidence matrix unless the touched route consumes it.

Every capability package row records:

- `firstRequiredPhase`
- `trigger`
- `ownerEvidence`
- `currentCoverageStatus`

If a touched route consumes a capability whose scheduled first required phase has arrived, the row cannot remain `not_consumed_by_first_slice` unless the review records `reviewed_not_applicable` or `explicitly_deferred` with owner, affected routes, expiry or recheck trigger, validation evidence, and phase exit review reference.

`not_consumed_by_first_slice` is an interim Phase 1 coverage value. It is not a final closure state and cannot satisfy Program DoD, final readiness, or Phase 6 full-target closure.

## Full-Target Closure Ledger

Phase 6 must create or update:

```text
logs/phase-a-innernet/reviews/gdd-to-module-hardening/full-target-ui-closure-ledger.json
```

The schema example is `docs/schemas/full-target-ui-closure-ledger.v1.example.json`. Final closure rows must end as one of:

- `covered`
- `reviewed_not_applicable`
- `explicitly_deferred`

Each final row requires owner, affected routes, expiry or recheck trigger, validation evidence refs, and phase exit review ref. Missing rows, duplicate IDs, orphan IDs, invalid closure statuses, and final `not_consumed_by_first_slice` rows fail review.

## Commit And Source-History Gate

The split directory is the implementation authority. A first-slice readiness claim requires:

- The whole split directory is included in the PR/commit.
- Schema fixtures are included.
- There are no untracked split-plan files.
- The monolithic source document is not used as a live implementation mirror.
- Any monolithic source change is recorded as source-history maintenance.

`GddToModuleFirstSlice.IsCommitReady` is the local helper for this gate.

## DoD Boundary

First-slice completion can claim First-Slice DoD only. It cannot claim Program DoD or final full-target UI closure. Program DoD remains blocked until all consumed full-target capability packages are covered, reviewed not applicable, or explicitly deferred with the required owner, expiry, and validation evidence.
