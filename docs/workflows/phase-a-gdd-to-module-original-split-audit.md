# Phase A GDD-To-Module Original Split Audit

Status: Living workflow standard
Language: English
Audit ID: `phase-a-gdd-to-module-original-split-audit`
Scope: Machine-checkable audit for original monolithic source coverage by the split GDD-to-module hardening directory.

## Authority

The source audit is:

`execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/98-original-to-split-audit.md`

The compact coverage map is:

`execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/99-source-coverage.md`

The machine-readable owner is `PhaseA.Platform/Workflow/GddToModuleOriginalSplitAudit.cs`. The schema/example fixture is `docs/schemas/gdd-to-module-original-split-audit.v1.example.json`.

## Coverage Contract

The original monolithic source has 2739 lines. The split audit must prove contiguous coverage from source line 1 through source line 2739 with no source-line gap or overlap.

Every source range must name at least one split output and must have a covered result. The style schema block is represented by the schema map, `schemas/godot-ui-style-contract.v1.example.json`, and schema acceptance criteria.

## Inventory Contract

The split output inventory must include every normative split Markdown file and machine-readable fixture, including:

- `96-global-review-standard.md`
- `97-split-added-requirements-ledger.md`
- `98-original-to-split-audit.md`
- `99-source-coverage.md`
- `schemas/godot-ui-style-contract.v1.example.json`

Missing or duplicate inventory entries fail audit validation.

## Source-History Boundary

The monolithic document is source history only. New normative requirements must not be added to the monolithic source document after the split. Commit/PR readiness requires the split directory, schema fixture directory, audit, and coverage map to be included together with no untracked split-plan files.
