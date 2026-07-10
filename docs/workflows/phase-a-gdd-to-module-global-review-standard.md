# Phase A GDD-To-Module Global Review Standard

Status: Living workflow standard
Language: English
Standard ID: `phase-a-gdd-to-module-global-review-standard`
Scope: Machine-checkable registry for repeated global reviews of the split GDD-to-module hardening refactor directory.

## Authority

The normative execution-plan standard remains:

`execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/96-global-review-standard.md`

The machine-readable owner is `PhaseA.Platform/Workflow/GddToModuleGlobalReviewStandard.cs`. The schema/example fixture is `docs/schemas/gdd-to-module-global-review-standard.v1.example.json`.

## Review Authority

Every review standard must use only these authority files:

- `AGENTS.md`
- `README.md`
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/96-global-review-standard.md`

The split directory is a target for whole-directory review, not an additional standard authority.

## Review Modes

- `whole-directory`: full split refactor directory review. Whole-directory coverage is allowed only after complete-read and mechanical checks pass or skipped checks are reported with residual risk.
- `standard-only`: only the standard file is the current target. Output must not claim whole-directory cleanliness.
- `standard-change self-review`: changed standard file before applying the changed standard to the selected review target.

## Mechanical Checks

Whole-directory review requires file inventory, link integrity, JSON validity, ledger/audit alignment, and status/action/schema vocabulary consistency.

Standard-only and standard-change self-review require authority-file read coverage, standard structure and ledger validity, internal reference checks, open-ledger blocker reporting, and standard-change completeness.

## Prior Finding Ledger

The `Prior Finding Ledger` in `96-global-review-standard.md` is the regression source of truth. The runtime parser validates stable IDs, severity values, status values, linked finding shape, closed-row closure evidence, and `Source refs:` coverage.

Open whole-directory `GRD-*` rows must be reported separately from current-target standard findings. A review cannot claim whole-directory cleanliness while any in-scope `GRD-*` row remains open.

## Output Contract

Review output must state review mode, standard-change IDs, authority set, self-review gate status when applicable, mechanical-check summary, stable finding IDs, P0/P1/P2 labels, file/line references, global impact, separation between current-target findings and open prior-ledger blockers, optional issue omission, and skipped mechanical checks.
