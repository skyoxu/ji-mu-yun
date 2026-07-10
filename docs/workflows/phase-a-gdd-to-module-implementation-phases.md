# Phase A GDD-To-Module Implementation Phases

Status: Living workflow standard
Language: English
Plan ID: `phase-a-gdd-to-module-hardening-implementation-phases`
Scope: Phase A browser-consumed GDD-to-module hardening implementation phases, phase prerequisites, route dependency matrix, and phase exit evidence.

## Authority

This document is the durable workflow source for the split plan in `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/08-implementation-phases.md`. The machine-readable registry is `PhaseA.Platform/Workflow/GddToModuleImplementationPhases.cs`; tests compare this document, route contracts, and the phase exit schema.

Durable dependencies:

- `docs/standards/phase-service.md`
- `docs/standards/godot-engine-semantics.md`
- `docs/standards/godot-ui-capability-contract.md`
- `docs/standards/godot-ui-style-contract.md`
- `docs/standards/godot-ui-style-closure.md`
- `docs/standards/godot-ui-style-schema-acceptance.md`
- `docs/standards/godot-diagnostics-quality-gates.md`
- `docs/schemas/gdd-to-module-phase-exit-review.v1.example.json`

## Phase 0A

Phase 0A is the blocking governance baseline before Phase 1 creates new browser/API readback surfaces or new POST behavior. It covers route module contracts, path/readback policy, action descriptors, exposure classes, no-store readback, duplicate-run convention, status vocabulary, source-boundary schema, canonical prototype-contract path policy, admin review queue, minimum diagnostic index/schema, structured game-type hash ownership, secret redaction, deterministic preflight, phase review evidence, ADR/decision-log gate, and shared LLM/Codex entrypoint guard.

Phase 0A exit requires zero unresolved P0/P1/P2 findings and durable evidence under `logs/phase-a-innernet/reviews/gdd-to-module-hardening`.

## Phase 0B

Phase 0B is the expanded Godot capability baseline. It may proceed in parallel with Phase 1 only when the touched Phase 1 route does not depend on the missing package. Required packages include the Godot engine semantic baseline, UI capability contract, UI style contract, style snapshot schema, style closure contract, diagnostics quality-gate contract, visual evidence seed, and full non-technology UI capability target coverage.

Missing required Phase 0B items are blockers, not later cleanups.

## Phase Route Matrix

| Phase | Purpose | Covered routes | Required Phase 0B packages |
| --- | --- | --- | --- |
| `1` | Requirement map and contract freshness | `structured-game-type-analysis`, `scene-route-confirmation`, `gdd-document-generation`, `gdd-requirements`, `prototype-contract`, `prototype-skeleton` | engine semantics, UI capability, UI style, diagnostics |
| `2` | Iteration plan traceability gate | `iteration-plan` | UI capability, UI style, diagnostics |
| `3` | Workflow recommendation | `workflow-recommendation` | none beyond consumed Phase 0A items unless touched route evidence requires it |
| `4` | Execute goal freshness and needs-fix tightening | `execute-next-goal`, `needs-fix`, `repair` | engine semantics, UI capability, UI style, diagnostics |
| `5` | UI wiring closure | `ui-wiring-closure`, `preview-package` | UI capability, UI style, UI style closure, diagnostics |
| `6` | Route governance guardrails | all covered GDD-to-module routes including `project-delete` and `preview-package` | all Phase 0B packages |

## Phase Exit Review Evidence

Each phase exit writes append-only evidence under:

```text
logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-<n>-exit-review-<run_id>.json
```

`phase-<n>-exit-review-latest.json` may exist only as a pointer/readback copy. New reviews append new run-id files instead of overwriting prior evidence. Chat text, assistant summaries, or PR prose alone are not sufficient.

Required fields are defined in `docs/schemas/gdd-to-module-phase-exit-review.v1.example.json` and in `GddToModuleImplementationPhases.RequiredPhaseExitReviewFields`.

The review must record route, artifact, API, browser surface, script, evidence, reviewer, consumed Phase 0A items, required Phase 0B items, durable decision refs, regression checks, and unresolved findings by severity. A phase cannot exit unless P0, P1, and P2 unresolved counts are all zero.

## Phase 6 Consolidation

Phase 6 expands already-created Phase 0 primitives rather than duplicating competing contracts. Deferred items from Phases 1-5 require owner, affected routes, severity, expiry or recheck trigger, proof that no current P0/P1/P2 gate is bypassed, and the exact Phase 6 acceptance test that will close them. A deferral without expiry/recheck metadata is treated as unresolved P2.

Final readiness remains separate from ordinary package download compatibility. Final readiness is blocked by unresolved diagnostics, source-boundary failures, style blockers, UI closure blockers, stale source hashes, invalid tickets, missing package artifacts, missing browser-safe readback, or unresolved admin review queue blockers.
