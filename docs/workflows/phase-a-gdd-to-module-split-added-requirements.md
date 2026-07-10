# Phase A GDD-To-Module Split-Added Requirements

Status: Living workflow standard
Language: English
Ledger ID: `phase-a-gdd-to-module-split-added-requirements`
Scope: Machine-checkable handling of split-added hardening requirements introduced after the original monolithic source coverage.

## Authority

The source ledger is:

`execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/97-split-added-requirements-ledger.md`

The machine-readable owner is `PhaseA.Platform/Workflow/GddToModuleSplitAddedRequirements.cs`. The coverage evidence schema/example is `docs/schemas/gdd-to-module-split-added-requirements.v1.example.json`.

## Ledger Contract

Every row has:

- `split_added_id`
- `Requirement`
- `Primary owner doc`
- `Acceptance reference`

The `split_added_id` must be stable and unique. Primary owner docs must identify the split file or durable workflow/standard that owns implementation. Acceptance references must name the tests, validators, phase evidence, or review evidence that close the requirement.

## Phase Review Coverage

Phase exit evidence fails if it implements an affected area without classifying the corresponding ledger row as one of:

- `implemented`
- `not_applicable`
- `explicitly_deferred`

Coverage rows require owner doc refs, acceptance evidence refs, phase exit review ref, owner, expiry or recheck trigger, and defer reason when not applicable or explicitly deferred.

## Boundary

`98-original-to-split-audit.md` and `99-source-coverage.md` prove original source coverage only. This ledger is the source of truth for split-added hardening requirements.

Implementation review must record zero unresolved P0/P1/P2 findings for missing split-added requirement coverage.
