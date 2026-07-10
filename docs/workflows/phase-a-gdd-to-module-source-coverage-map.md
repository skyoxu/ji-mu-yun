# Phase A GDD-To-Module Source Coverage Map

Status: Living workflow standard
Language: English
Coverage Map ID: `phase-a-gdd-to-module-source-coverage-map`
Scope: Compact machine-checkable coverage map for the original monolithic GDD-to-module hardening source.

## Authority

The compact source coverage map is:

`execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/99-source-coverage.md`

The original-to-split audit is:

`execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/98-original-to-split-audit.md`

The machine-readable owner is `PhaseA.Platform/Workflow/GddToModuleSourceCoverageMap.cs`. The schema/example fixture is `docs/schemas/gdd-to-module-source-coverage-map.v1.example.json`.

## Coverage Contract

The coverage map proves source line coverage for original lines 1-2739. Ranges must be contiguous, must not overlap, and must match the original-to-split audit range table.

The style schema range includes the JSON fixture `schemas/godot-ui-style-contract.v1.example.json` as part of source coverage.

## Split-Added Boundary

Original source-line coverage alone is not implementation readiness evidence for split-added hardening requirements. Split-added requirements are tracked by `97-split-added-requirements-ledger.md`, and `04d-godot-engine-semantics-and-reference-examples.md` is post-split hardening coverage tracked through that ledger.
