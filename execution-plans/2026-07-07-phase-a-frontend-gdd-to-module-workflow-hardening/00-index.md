# Phase A Frontend GDD-To-Module Workflow Hardening Split Index

Status: Primary split plan for this refactor. The original monolithic execution plan remains source history; implementation work should start from this directory.
Language: English
Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md`

## Authority And Global Constraints

This split follows the repository guidance in `AGENTS.md` and `README.md`:

- Phase A/B browser-consumed prototype routes, account boundaries, readback, evidence, preview/package, and shared LLM/Codex entrypoints stay in Phase service scope.
- Durable cross-cutting rules must move into standards or workflow docs when implemented; this directory is the execution-plan workspace, not the final standards source of truth.
- Godot remains the implementation stack. TapTapMarker runtime technology is not imported, but TapTapMarker's non-technology UI framework capabilities are preserved as target capabilities and translated into Godot/Phase contracts.
- Public/browser APIs remain backward-compatible by default. New behavior is additive unless an ADR or decision log approves a breaking change.
- Evidence is required for route success. Assistant prose alone cannot mark completion.

## Commit And Source-History Guard

This directory is the implementation authority for the refactor. The monolithic source document is frozen source history, not a second live mirror.

Active drafting note:

- While this split plan is still being reviewed and edited, the working tree may show the split directory as untracked and the monolithic source as modified.
- The plan is not implementation-ready until those files are included in the same PR/commit or the monolithic source change is reverted according to the source-history policy below.

Acceptance criteria:

- A PR or commit that claims this plan is ready must include this whole split directory, including `schemas/`, `96-global-review-standard.md`, `97-split-added-requirements-ledger.md`, `98-original-to-split-audit.md`, and `99-source-coverage.md`; there must be no untracked split-plan files.
- The monolithic source document must not be used to drive implementation after this split lands. If it changes after the split, the change must be either reverted before commit or recorded as source-history maintenance in `98-original-to-split-audit.md`.
- New normative requirements after the split must land in this split directory or in linked standards/ADR/workflow docs. The monolithic source document may receive only source-history maintenance notes and must not become a second requirements source.
- Reviewers validate `git status --short` before implementation starts and block if the split directory is missing, untracked, or inconsistent with the source-history policy. The generated acceptance matrix binds this as separate machine gate `GTM-GATE-P0A-COMMIT-READINESS`, validated by the proposed-commit-set capture and `COMMIT-PROPOSED-SET-COMPLETE`; Phase 0A row dispositions alone cannot authorize Phase 1.

## Phase Service Execution Mapping

Implementation tasks must translate plan intent into the Phase service change contract from `AGENTS.md`.

Acceptance criteria:

- Every API or browser-consumed route change names its `PhaseA.Platform/**` handler/service, DTO/readback contract, browser caller, auth/account boundary, and `PhaseA.Platform.Tests/**` coverage before implementation is accepted.
- Every smoke or drill requirement names whether it extends an existing `scripts/python/phase_a_*.py` / `scripts/python/phase_b_*.py` entrypoint or introduces a new script with docs and evidence under `logs/`.
- Durable runtime or cross-project state uses an explicit persistence owner: metadata DB table, hosted workspace sidecar, diagnostic spool, or append-only audit/export evidence. Ambiguous "sidecar only" ownership is not accepted for admin cross-project features.

## Task Order

1. [Overview, Goals, Workflow, Severity](01-overview-workflow.md)
   - Establishes the product problem, target GDD-to-module workflow, naming conventions, and P0/P1/P2 acceptance severity.
2. [Route-State Artifacts](02a-route-state-artifacts.md)
   - Defines the project sidecars, including scene route, GDD document generation, requirement map, workflow recommendation, source hashes, freshness fields, admin review queue, prototype-skeleton compatibility guard, UI closure readback shape, and artifact-level acceptance rules.
3. [Backend And API Contracts](02b-backend-api-contracts.md)
   - Defines service responsibilities, API routes, browser-safe DTO projections, and route execution boundaries.
4. [Frontend, Migration, And Compatibility](02c-frontend-migration-compatibility.md)
   - Defines the browser workflow surfaces, staged review UI, contract freshness banners, and compatibility posture for legacy projects.
5. [Testing, Observability, Admin](03-testing-observability-admin.md)
   - Defines route, browser, Godot UI, diagnostics, style contract, and admin/readback evidence requirements.
6. [Route Contracts And Deterministic Guards](04a-route-contracts-and-guards.md)
   - Translates TapTap governance into Phase route module contracts, unified action descriptors, guard tests, and admin/backfill boundaries.
7. [Route Readback, Recovery, And Freshness](04b-route-readback-recovery-and-freshness.md)
   - Defines path/readback policy, runtime evidence handling, cache/freshness rules, directory-scoped instructions, and ambiguity handling.
8. [Route Operation Governance](04c-route-operation-governance.md)
   - Defines action exposure, DTO context boundaries, progress feedback, idempotency, credential boundaries, preflight checks, and docs indexing.
9. [Godot Engine Semantics And Reference Examples](04d-godot-engine-semantics-and-reference-examples.md)
   - Defines Godot viewport/resolution, coordinate-space, unit, input, physics, camera, TileMap/map, and curated official-reference-example rules before GDD-to-module implementation.
10. [Godot UI Capability Contract](05-godot-ui-capability-contract.md)
   - Defines Godot UI capability domains and how UI capability evidence enters GDD, contracts, iteration, execution, repair, and UI closure.
11. [TapTapMarker UI Style Migration Overview And Catalog](06a-ui-style-migration-overview-and-catalog.md)
   - Preserves TapTapMarker non-technology UI framework capabilities as the full target and maps them into Godot style catalogs, component families, and style drift taxonomy.
12. [Godot UI Style Snapshot Schema Map](06b-ui-style-snapshot-schema.md)
   - Maps the machine-contract schema for style snapshots, theme resources, component coverage, input/gesture, lifecycle, virtualization, localization, visual evidence, and readback.
   - Enum-declaration example fixture: [schemas/godot-ui-style-contract.v1.example.json](schemas/godot-ui-style-contract.v1.example.json).
   - Machine-readable structural/vocabulary authority: [schemas/godot-ui-style-contract.v1.profile.json](schemas/godot-ui-style-contract.v1.profile.json).
   - Exhaustive bidirectional source-field contract: [schemas/godot-ui-style-contract.v1.field-map.json](schemas/godot-ui-style-contract.v1.field-map.json).
   - Canonical cross-document capability inventory: [schemas/gdd-to-module-capability-inventory.v1.json](schemas/gdd-to-module-capability-inventory.v1.json).
   - Stable split-added owner and acceptance registry: [schemas/split-added-acceptance-registry.v1.json](schemas/split-added-acceptance-registry.v1.json).
   - Primary/secondary workflow action and repair sub-operation authority: [schemas/workflow-action-contracts.v1.json](schemas/workflow-action-contracts.v1.json).
13. [Style-Aware UI Closure](06c-style-aware-ui-closure.md)
   - Defines how UI closure blocks final readiness on style drift and how repair receives frozen style evidence.
14. [Godot UI Style Schema Acceptance](06d-ui-style-schema-acceptance.md)
   - Defines validation requirements for the schema map, machine-readable schema contract profile, and enum-declaration example fixture.
15. [Godot Diagnostics And Quality Gates](07-godot-diagnostics-quality-gates.md)
   - Migrates diagnostics, symptom remediation, debug-log lifecycle, interaction-region gates, preview validation, and project diagnostic spool.
16. [Implementation Phases](08-implementation-phases.md)
    - Orders Phase 0 through Phase 6 with exit criteria.
17. [Risks, DoD, Open Questions, Phase 1 Defaults](09-risks-dod-open-questions.md)
    - Tracks risks, mitigations, done criteria, scoped questions, and first-slice default decisions.
18. [Recommended First Implementation Slice](10-recommended-first-slice.md)
    - Lists the first implementation slice after Phase 0 passes.
19. [Global Review Standard](96-global-review-standard.md)
    - Freezes the review authority set, P0/P1/P2 severity standard, standard-change protocol, and regression-control rule for repeated global reviews.
20. [Split-Added Requirements Ledger](97-split-added-requirements-ledger.md)
    - Tracks normative hardening requirements added after the monolithic source split.
21. [Original-To-Split Comparison Audit](98-original-to-split-audit.md)
    - Records the explicit source-to-split comparison, heading coverage, split output inventory, and normalization notes.
22. [Source Coverage Map](99-source-coverage.md)
    - Proves the original monolithic plan is covered by the split documents and records intentional normalization notes.
23. [Implementation Acceptance Matrix](100-implementation-acceptance-matrix.md)
    - Tracks Phase 0A, 0B, and Phase 1-6 implementation status by stable acceptance check rather than by document.
    - Machine-readable authority: [schemas/implementation-acceptance-matrix.v1.json](schemas/implementation-acceptance-matrix.v1.json).
    - Regenerate and validate with `py -3 scripts/python/build_gdd_to_module_acceptance_matrix.py`.

## Structural Refactor Principles

- Keep the full TapTapMarker UI framework capability target, excluding its runtime technology stack.
- Do not force every full-target UI capability into Phase 0/Phase 1. Phase 0 seeds contracts and guardrails; Phase 1 consumes the minimum fields required to stop GDD-to-module drift.
- Use one normalized taxonomy for style drift, UI closure, admin readback, tests, and schema validation.
- Use `97-split-added-requirements-ledger.md` for post-split hardening requirements; original source coverage files do not prove these added requirements.
- Keep security-sensitive or tool-only components out of normal-user core UI baselines unless a Phase service security policy exists.
- Move durable rules to `docs/standards/**`, `docs/workflows/**`, `docs/ui-style-guides/**`, README, architecture indexes, and AGENTS routing when implementation begins.
