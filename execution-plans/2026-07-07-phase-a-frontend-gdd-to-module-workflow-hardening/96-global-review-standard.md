# Global Review Standard

Status: Required review standard for this split refactor directory.
Language: English

## Purpose

This document freezes the review standard for repeated global reviews of the split refactor directory. It prevents review drift across rounds by making the standard explicit, versioned by document edits, limited to a small authority set, and backed by a durable prior-finding ledger.

## Authority Set

Every global review of this split refactor directory must derive its review standard only from:

1. Repository root `AGENTS.md`.
2. Repository root `README.md`.
3. This file, `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/96-global-review-standard.md`.

No other document may introduce a new review standard during a review round. Other files in this split directory are review targets, not review-standard authorities.

## Review Target

The review target is the whole split refactor directory:

`execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/`

The reviewer must judge the directory as one implementation plan, not as isolated files. A finding is valid only when it identifies a global consistency, authority, implementation-readiness, compatibility, safety, or acceptance problem that affects the plan as a whole.

## Review Modes

Every review must declare exactly one review mode before reporting findings:

1. Whole-directory review:
   - Use this mode when the user asks to review the refactor directory, split plan, document work, or global plan consistency.
   - The target is the full split refactor directory named in `Review Target`.
   - The full `Review Completion Bar` applies.
   - The output may claim whole-directory coverage only after the complete-read rule and all whole-directory mechanical checks pass or skipped checks are reported with residual risk.

2. Standard-only review:
   - Use this mode when the user asks to review this standard file itself without asking to review the whole split directory.
   - The target is only this file, but the authority set remains `AGENTS.md`, `README.md`, and this file.
   - The reviewer must not claim whole-directory coverage or declare the split plan clean.
   - The output must separate findings in the current standard-file target from existing open whole-directory ledger blockers. Existing open `GRD-*` rows are blockers for a future whole-directory clean result, but they are not new standard-file findings unless this file mishandles them.

3. Standard-change self-review:
   - Use this mode after editing this file and before applying the changed standard to a whole-directory review.
   - The target is the changed standard file, with `AGENTS.md`, `README.md`, and this file as the only authority set.
   - The Standard Self-Review Gate passes only when no unresolved P0/P1/P2 findings remain in the changed standard under this mode.
   - Passing this mode does not close open whole-directory `GRD-*` findings unless the split-plan target files were also fixed and the ledger rows receive traceable closure evidence.

## Normative Requirement Rule

A split-plan statement is normative when it uses or appears under any of the following forms:

- `must`, `must not`, `required`, `requires`, `cannot`, `fails`, `rejects`, `blocks`, `acceptance`, `exit criteria`, `Definition of Done`, `guard`, `validator`, `schema`, `contract`, `authority`, `source of truth`, `canonical`, `compatibility`, `migration`, or `evidence`.
- A table row or bullet that declares a route, API, artifact, schema field, status value, persistence owner, phase gate, test, smoke, guard, validator, ledger row, or durable standards destination.
- A statement that a workflow action, source hash, readback field, route state, diagnostics record, admin record, style capability, package readiness state, or acceptance behavior is required before another step can proceed.

Examples and explanatory prose are non-normative only when they do not introduce a required behavior, field, owner, test, phase gate, or durable destination. When a statement is ambiguous between explanation and requirement, classify it as normative if downstream implementation could depend on it.

## Standard Change Protocol

If a reviewer believes the standard is incomplete or should change:

1. Stop before applying the new criterion to the active review target.
2. Update this file first, in English.
3. Add one or more rows to `Standard Change Log` with new `standard_change_id` values, dates, changed rules, reasons, applicability starts, and fixed finding IDs when findings are closed.
4. Run the Standard Self-Review Gate below against the updated standard.
5. State in the review output that the review standard changed before the review was run.
6. Re-run the selected review mode using the updated `AGENTS.md`, `README.md`, and this file as the only authority set. A standard-only review remains standard-only after the standard changes; it must not silently escalate to whole-directory review.

Reviewers must not silently add new criteria during a review. A new criterion that is not present in the authority set is out of scope until this file is updated.

### Standard Self-Review Gate

After any edit to this file and before applying the changed standard to the active review target, the reviewer must check this file itself for P0/P1/P2 issues using only `AGENTS.md`, `README.md`, and this file as authority. The self-review must verify:

1. The change has a `Standard Change Log` row.
2. Any finding closed by the change has a `Prior Finding Ledger` row.
3. The changed rule does not contradict the authority set, severity standard, complete-read rule, mechanical-check requirements, or review output requirements.
4. The self-review output includes the mechanical-check summary required by `Review Output Requirements`, scoped to the standard file and authority files when the whole split directory is not being reviewed.
5. The self-review result is reported before the changed standard is used for a whole-directory review.

The Standard Self-Review Gate passes only when the changed standard has no unresolved P0/P1/P2 findings. If the self-review finds any unresolved P0/P1/P2 issue, the changed standard cannot be applied to a whole-directory review until that issue is fixed or explicitly moved out of scope by a later standard change.

### Standard Change Log

| standard_change_id | Date | Changed rule | Reason | Applicability start |
| --- | --- | --- | --- | --- |
| `SCR-001` | 2026-07-09 | Created frozen authority set, severity model, review method, and regression-control rule. | Stop repeated review drift across global document checks. | Reviews after this file was introduced. |
| `SCR-002` | 2026-07-09 | Added normative requirement rule, standard change log, complete-read rule, minimum mechanical checks, P2 closure, prior-finding ledger, finding close format, and required standard-change statement in output. | Close gaps found in the first review of this standard. Fixed: GRS-P1-001, GRS-P1-002, GRS-P1-003, GRS-P1-004, GRS-P1-005, GRS-P2-001, GRS-P2-002, GRS-P2-003. | Reviews after this change lands. |
| `SCR-003` | 2026-07-09 | Added baseline prior-finding backfill, mandatory ledger IDs for new findings, standard self-review gate, mechanical-check summary output, and deterministic recently-closed regression scope. | Close gaps found in the second review of this standard. Fixed: GRS-P1-006, GRS-P1-007, GRS-P1-008, GRS-P2-004, GRS-P2-005. | Reviews after this change lands. |
| `SCR-004` | 2026-07-09 | Extended complete-read coverage to all authority files, required mechanical summaries for standard self-review, and backfilled known split-plan findings as open `GRD-*` ledger rows. | Close gaps found in the third review of this standard. Fixed: GRS-P1-009, GRS-P1-010, GRS-P2-006; backfilled GRD-P1-001 through GRD-P2-003. | Reviews after this change lands. |
| `SCR-005` | 2026-07-09 | Defined Standard Self-Review Gate pass/fail semantics as zero unresolved P0/P1/P2 findings before the changed standard can be applied. | Close gate ambiguity found in the fourth review of this standard. Fixed: GRS-P2-007. | Reviews after this change lands. |
| `SCR-006` | 2026-07-09 | Added explicit review modes, scoped mechanical checks, open-ledger blocker reporting, deterministic prose-review evidence fields, source-reference requirements for backfilled findings, and a baseline coverage statement. | Close standard-file gaps found after repeated standard-only review rounds and prevent standard checks from being confused with whole-directory checks. Fixed: GRS-P1-011, GRS-P1-012, GRS-P1-013, GRS-P2-008, GRS-P2-009, GRS-P2-010, GRS-P2-011. | Reviews after this change lands. |
| `SCR-007` | 2026-07-09 | Added closed-finding regression lifecycle rules, semantic ledger validation, source-reference authority and precision rules, optional-context disclosure, open-blocker ID output, and multi-row change-log support. | Close standard-file gaps found in the next standard-only review without weakening the frozen authority model. Fixed: GRS-P1-014, GRS-P1-015, GRS-P1-016, GRS-P1-017, GRS-P2-012, GRS-P2-013, GRS-P2-014, GRS-P2-015. | Reviews after this change lands. |
| `SCR-008` | 2026-07-09 | Made standard-change protocol review-mode aware, added structured linked-finding ledger support, clarified multi-change regression scope, removed non-durable prior-review dependence, strengthened source-reference precision, and required change-log-to-finding traceability. | Close standard-file gaps found in the next standard-only review while keeping regression checks deterministic. Fixed: GRS-P1-018, GRS-P1-019, GRS-P1-020, GRS-P1-021, GRS-P1-022, GRS-P2-016, GRS-P2-017, GRS-P2-018. | Reviews after this change lands. |
| `SCR-009` | 2026-07-09 | Recorded closure evidence for whole-directory split-plan findings without changing review criteria. | Close fixed split-plan blockers after target documents were updated. Fixed: GRD-P1-001, GRD-P1-002, GRD-P1-003, GRD-P1-004, GRD-P1-005, GRD-P2-001, GRD-P2-002, GRD-P2-003. | Reviews after this closure record lands. |
| `SCR-010` | 2026-07-09 | Recorded closure evidence for linked regression finding `GRD-P1-006` without changing review criteria. | Close the `prototype-skeleton-guard` Phase 1 test-list regression linked to GRD-P1-004. Fixed: GRD-P1-006. | Reviews after this closure record lands. |

## Required Review Inputs

Each review round must read:

1. `AGENTS.md`.
2. `README.md`.
3. This file.
4. The full split refactor directory being reviewed when the selected mode is whole-directory review.

The first three files define the standard. The split refactor directory provides evidence to check against that standard only for whole-directory review or for explicitly marked optional context in standard-only review and standard-change self-review.

## Complete-Read Rule

A review round must not claim standard-authority coverage unless the reviewer has read the complete contents of `AGENTS.md`, `README.md`, and this file. A review round must not claim whole-directory coverage unless the reviewer has also read or mechanically inspected the complete contents of every Markdown and machine-readable schema/fixture file in the split directory.

If a tool truncates output, the reviewer must re-read the missing range, use a different tool, or record the unread range as a review blocker. A review with unread content required by the selected review mode cannot report "no P0/P1/P2 findings" for that mode; it must report the coverage gap.

Generated binaries, images, or unsupported file formats may be listed as non-text evidence only when they are not required to determine the document standard or split-plan consistency. If a non-text file is required for a claim, the review must record how it was validated.

## Required Review Method

Each whole-directory review round must perform these checks:

1. Authority alignment:
   - The split plan must not contradict the Phase service scope, Phase service change contract, protected paths, database/API compatibility rules, prototype route recovery order, shared LLM/Codex invocation protocol, runtime recovery rules, encoding rules, or evidence rules from `AGENTS.md`.
   - The split plan must not contradict the product overview, Phase A/B scope, GDD scene-confirmation workflow, hosted route recovery rules, AI/LLM protocol, Godot stack, delivery profile meaning, or stable entrypoint boundaries from `README.md`.

2. Whole-directory consistency:
   - The index, audit files, ledgers, schemas, phase plan, tests, API contracts, frontend compatibility, route-state artifacts, and durable standards destinations must agree.
   - A normative requirement introduced in one split file must be traceable to its owner document, test or acceptance requirement, phase gate, and final durable destination when the plan says one is required.
   - A split-added requirement must be listed in the split-added ledger or explicitly declared non-normative.

3. Implementation readiness:
   - Browser/API-visible behavior must name its route/action/readback contract, account/auth boundary, DTO or artifact projection, compatibility behavior, and targeted validation.
   - Persistent or cross-project behavior must name its persistence owner and not rely on project-local sidecars when deletion-safe or admin-wide lookup is required.
   - Prompt-producing and file-changing workflows must preserve source-boundary authority, route recovery order, shared LLM/Codex entrypoints, and evidence-based completion.

4. Backward compatibility and migration:
   - Existing browser/API fields, routes, statuses, artifact paths, auth behavior, and package/readback compatibility must remain additive unless the plan requires an ADR or decision log.
   - Legacy project paths must either be supported through a defined import/backfill/compatibility flow or explicitly blocked with browser-safe reasons.

5. Test and acceptance closure:
   - Every P0/P1/P2 behavior required by the plan must have a corresponding test, smoke, guard, validator, machine-checkable schema/profile, or explicit evidence requirement appropriate to its severity.
   - P2 closure may use deterministic prose-review acceptance only when the issue is purely ambiguity/linkage/wording within the plan and does not define a machine-consumed contract.
   - Deterministic prose-review acceptance must record: reviewer or review mode, checked rule, checked file and line or section reference, evidence reference, reason no machine fixture/schema is required, and closure result.
   - A phase exit must not claim completion while required schemas, route descriptors, source hashes, status vocabularies, diagnostics, admin blockers, or readiness gates are undefined or inconsistent.
   - Acceptance criteria must be checkable without relying only on assistant prose.

6. Regression control:
   - The review must compare against every `Open` finding in `Prior Finding Ledger`.
   - The review must compare against every `Closed` finding in `Prior Finding Ledger` whose fix reference touches a file or requirement family reviewed in the current round.
   - The review must compare against every `Closed` finding added or changed by any `Standard Change Log` row added or changed in the immediately preceding completed review round. If a single round added multiple standard-change rows, all of those rows are the recently changed regression set for the next round.
   - A baseline backfill must exist before any review may claim full regression coverage: all still-relevant P0/P1/P2 findings from durable prior-review sources named in this file must either appear in `Prior Finding Ledger` or be explicitly declared out of scope by a standard-change row. Reviewers are not required to reconstruct non-durable conversation history; if they choose to rely on a remembered earlier finding, they must first create a durable ledger row with source references available under the active review mode.
   - A prior finding is closed only when the ledger row contains a traceable fix reference, closure reason, and validation method.
   - The reviewer must not limit regression checks to only the immediately previous round.
   - If a `Closed` finding has regressed, do not silently edit the old row back to `Open`. Add a new linked regression finding row with the next stable ID, put the regressed finding ID in the `Linked finding` column, and keep the old row as historical closure evidence unless a later standard change explicitly archives it.
   - If a closed row's closure evidence is itself invalid, add a new standard-file finding that names the invalid row and fix the row evidence under the same or a later standard-change entry before claiming the standard is clean.

Standard-only review and standard-change self-review must apply the same authority-alignment, regression-control, closure, and output rules only to this standard file and the selected mode's scoped mechanical checks. They must not report split-plan findings unless the standard file itself mishandles the split-plan ledger, review mode boundary, or output semantics.

## Minimum Mechanical Checks

Each whole-directory review round must run or manually perform an equivalent of the following checks:

1. File inventory:
   - List every file under the split directory.
   - Confirm every normative split file is referenced by the index or explicitly classified as supporting evidence.
   - Confirm the split output inventory includes all normative split files and schema/fixture files.
   - Report file count, Markdown count, JSON count, and any unsupported file count in the review output.

2. Link integrity:
   - Check every relative Markdown link in the split directory resolves.
   - Report missing link count in the review output.

3. Machine-readable validity:
   - Parse every `.json` file under the split directory.
   - If a JSON file is documented as a schema/fixture authority, confirm the review notes whether it was parsed successfully.
   - Report parsed JSON count and parse failure count in the review output.

4. Ledger and audit alignment:
   - Confirm split-added requirements are listed in the split-added ledger or explicitly non-normative.
   - Confirm prior findings in this file are either still open, closed with traceable fix evidence, or explicitly out of scope under the current standard.
   - Report prior-finding counts by status in the review output.

5. Status/action/schema vocabulary consistency:
   - Search for canonical workflow actions, route/readback statuses, readiness states, closure statuses, and schema/profile terms.
   - Report inconsistencies that meet the P0/P1/P2 severity definitions.
   - Report the vocabulary families checked in the review output.

If a mechanical check cannot be run, the review must state the skipped check, reason, and residual risk.

### Scoped Mechanical Checks

For standard-only review and standard-change self-review, the minimum mechanical checks are scoped as follows:

1. Authority-file read coverage:
   - Read the complete contents of `AGENTS.md`, `README.md`, and this file.
   - Report line counts or another deterministic evidence summary for those three files.

2. Standard structure and ledger validity:
   - Verify this file contains the authority set, review modes, standard change log, complete-read rule, severity standard, prior-finding ledger, finding close format, review output requirements, and review completion bar.
   - Parse the prior-finding ledger rows in this file and report total row count, status counts, severity counts, duplicate `finding_id` count, and any row missing required close-format columns.
   - Validate closed-row semantics, not only table columns: every `Closed` row must have a non-placeholder fix reference, closure reason, validation method, and required source reference; source references must use durable files, sections, line references, or stable requirement IDs rather than conversation memory.
   - Validate source-reference precision for backfilled `GRD-*` rows: each source reference must identify the source file plus section, line, or stable requirement ID; generic file-level descriptions are not sufficient.

3. Internal reference checks:
   - Check relative Markdown links in this file only.
   - Report missing link count for this file.

4. Open-ledger blocker checks:
   - Report existing open whole-directory `GRD-*` blockers separately from new standard-file findings, including each open blocker ID.
   - Do not claim whole-directory cleanliness while any in-scope open `GRD-*` row remains open.

5. Standard-change completeness:
   - When this file was edited, verify the change has one or more new `Standard Change Log` rows covering the edit scope and naming the fixed finding IDs, and that any standard-file findings fixed by the edit have ledger rows with status, fix reference, closure reason, linked finding value, validation method, and source references.

For standard-only review, the split directory may be inventoried as optional context, but it is not required and must not be used to claim whole-directory coverage. The review output must state whether optional split-directory context was used and, if used, which files or checks were used as evidence. For standard-change self-review, optional split-directory context cannot introduce a new criterion unless the criterion is already present in this file after the change.

## Severity Standard

### P0

Use P0 only for an issue that would make the plan unsafe or invalid to implement.

P0 examples:

- The plan instructs or allows manual mutation of live Phase metadata DB, runtime state, hosted workspaces, secrets, or protected runtime files without the required authorization path.
- The plan contradicts host/account isolation, token secrecy, protected path, public API compatibility, or shared LLM/Codex entrypoint hard rules from `AGENTS.md` or `README.md`.
- The plan allows file-changing hosted routes to bypass required recovery sources, fail-open on missing required sources, or mark completion based only on assistant text.
- The plan cannot be executed without contradicting the Windows/Godot/Phase service stack stated by `AGENTS.md` and `README.md`.

### P1

Use P1 for a required global inconsistency that can cause implementation drift, missed acceptance, unsafe compatibility behavior, or regression of a previously fixed class of problem.

P1 examples:

- A route/action/status/schema/ledger/phase/test requirement is declared in one split file but missing from the index, owner document, phase gate, test plan, or durable destination required by the plan.
- A browser/API or route-state contract is required but lacks a concrete path, DTO/artifact shape, persistence owner, auth/account boundary, or validation rule.
- A metadata DB, admin queue, diagnostic, game-type maintenance, delete tombstone, or cross-project record is required but does not define deletion-safe ownership and minimum query/update behavior.
- The plan creates two competing authorities for the same route, status, artifact, source hash, workflow action, readiness state, or style/diagnostic capability.
- A phase exit can pass while a required downstream guard, source-boundary field, route descriptor, status vocabulary, schema profile, or acceptance test is still missing.

### P2

Use P2 for a required ambiguity or internal inconsistency that is unlikely to make implementation unsafe immediately, but can still cause inconsistent implementation, weak validation, or repeated review churn.

P2 examples:

- Duplicate or contradictory wording weakens a required rule.
- A required owner/test/evidence reference exists but is incomplete or not linked from the expected ledger/index/audit location.
- A status, closure value, action alias, schema field, or readiness term is valid but its boundary with a nearby term is unclear.
- A validation requirement is described in prose but the plan does not make its machine-checkable fixture, schema profile, or evidence relationship clear enough.

## Out Of Scope For Findings

Do not report:

- Pure wording polish.
- Optional improvements that do not affect Phase service safety, compatibility, implementation readiness, or acceptance closure.
- New product ideas not already required by `AGENTS.md`, `README.md`, this standard, or the split plan's own normative claims.
- A stricter rule learned from another repository, framework, previous conversation, or reviewer preference unless this file is updated first.

## Prior Finding Ledger

This ledger is the durable source for regression checks. New findings from any review mode must receive stable IDs in the review output and must be added here before any follow-up fix round may mark them closed. Closed findings remain in the ledger until implementation of the split plan begins or a later standard change explicitly archives them.

Baseline backfill rule:

- `SCR-003` establishes this ledger as the baseline regression source.
- A review after `SCR-003` may claim full regression coverage only if every still-relevant P0/P1/P2 finding from durable prior-review sources named in this file is present in this ledger or explicitly out of scope by standard change.
- If a reviewer relies on a prior finding that is not in this ledger, the first finding must be a P1 ledger-completeness issue, and the missing prior finding must be assigned an ID before it can be treated as closed.
- New review findings must use stable IDs. For standard-document findings, use `GRS-P<severity>-NNN`. For whole-directory split-plan findings, use `GRD-P<severity>-NNN`.
- `SCR-004` backfills the known split-plan findings that were already identified before this ledger existed. These `GRD-*` rows remain `Open` until the split plan is fixed and the row receives traceable closure evidence.
- `SCR-006` records the baseline coverage scope for this standard: the known review rounds before `SCR-004` are covered for authority drift, complete-read gaps, mechanical-check gaps, new-finding ID gaps, standard self-review gaps, and the eight split-plan `GRD-*` findings listed below. Any still-relevant pre-`SCR-004` P0/P1/P2 finding outside those categories must be reported as a new P1 ledger-completeness issue before a review may claim clean coverage.
- Backfilled `GRD-*` findings must include source references in either the validation method or closure evidence before they can be closed. A source reference must identify the split file and section, line, or stable requirement ID that originally created the requirement and the file/section/line that fixes it.
- `SCR-007` normalizes the standard-file ledger source-reference rule: closed standard-file findings must cite durable sections in this file and the relevant standard-change row; whole-directory `GRD-*` findings must cite durable split-plan files plus section, line, or stable requirement IDs. Conversation memory, user-message summaries, or assistant recollections are not valid source references.
- `SCR-008` normalizes linked-finding and change-log traceability: every ledger row has a `Linked finding` value, regression rows must name the regressed finding there, and standard-change rows that close findings must name the closed finding IDs in the changed-rule text or reason.

| finding_id | Severity | Summary | First found | Status | Fix reference | Closure reason | Linked finding | Validation method |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `GRS-P1-001` | P1 | Regression control depended on conversation memory instead of a durable prior-finding source. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Prior Finding Ledger` and `Required Review Method` regression-control rules | The standard now names this ledger as the durable regression source and requires incomplete ledger findings to be reported. | None | Read this file and verify the ledger and regression-control bullets exist. Source refs: this file `96-global-review-standard.md` `Prior Finding Ledger` and `Required Review Method` regression-control rules, stable ledger row `GRS-P1-001`, and `Standard Change Log` row `SCR-002`. |
| `GRS-P1-002` | P1 | Standard changes had no durable change-log requirement. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Standard Change Protocol` and `Standard Change Log` | The protocol now requires a change-log row before applying new criteria. | None | Read this file and verify `SCR-002` exists. Source refs: this file `96-global-review-standard.md` `Standard Change Protocol` and `Standard Change Log`, stable ledger row `GRS-P1-002`, and `Standard Change Log` row `SCR-002`. |
| `GRS-P1-003` | P1 | Test and acceptance closure covered only P0/P1 behavior, leaving P2 closure unstable. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Test and acceptance closure` | The closure rule now covers P0/P1/P2 and defines when prose-review acceptance is allowed for P2. | None | Read this file and verify P0/P1/P2 closure text exists. Source refs: this file `96-global-review-standard.md` `Test and acceptance closure`, stable ledger row `GRS-P1-003`, and `Standard Change Log` row `SCR-002`. |
| `GRS-P1-004` | P1 | The standard did not require complete reads or handling truncated tool output. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Complete-Read Rule` | The standard now blocks whole-directory no-finding claims when required content is unread. | None | Read this file and verify the complete-read rule exists. Source refs: this file `96-global-review-standard.md` `Complete-Read Rule`, stable ledger row `GRS-P1-004`, and `Standard Change Log` row `SCR-002`. |
| `GRS-P1-005` | P1 | The standard did not define minimum mechanical checks, leaving repeated reviews too subjective. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Minimum Mechanical Checks` | The standard now requires file inventory, links, JSON parsing, ledger/audit alignment, and vocabulary consistency checks. | None | Read this file and verify the mechanical checklist exists. Source refs: this file `96-global-review-standard.md` `Minimum Mechanical Checks`, stable ledger row `GRS-P1-005`, and `Standard Change Log` row `SCR-002`. |
| `GRS-P2-001` | P2 | `normative requirement` was undefined. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Normative Requirement Rule` | The standard now defines normative wording, structures, and ambiguity handling. | None | Read this file and verify the normative rule exists. Source refs: this file `96-global-review-standard.md` `Normative Requirement Rule`, stable ledger row `GRS-P2-001`, and `Standard Change Log` row `SCR-002`. |
| `GRS-P2-002` | P2 | Review output did not require stating whether the standard changed. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Review Output Requirements` | Output now must state whether the standard changed during the round. | None | Read this file and verify the output requirement exists. Source refs: this file `96-global-review-standard.md` `Review Output Requirements`, stable ledger row `GRS-P2-002`, and `Standard Change Log` row `SCR-002`. |
| `GRS-P2-003` | P2 | Prior finding closure lacked a fixed format. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Prior Finding Ledger` and `Finding Close Format` | The ledger now requires finding ID, status, fix reference, closure reason, and validation method. | None | Read this file and verify the ledger columns and close format exist. Source refs: this file `96-global-review-standard.md` `Prior Finding Ledger` and `Finding Close Format`, stable ledger row `GRS-P2-003`, and `Standard Change Log` row `SCR-002`. |
| `GRS-P1-006` | P1 | Prior-finding regression still allowed reliance on conversation memory because no baseline backfill rule existed. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Required Review Method` regression-control rules and `Prior Finding Ledger` baseline backfill rule | The standard now requires all still-relevant pre-`SCR-003` findings to be in the ledger or explicitly out of scope before full regression coverage can be claimed. | None | Read this file and verify the baseline backfill rule exists. Source refs: this file `96-global-review-standard.md` `Required Review Method` regression-control rules and `Prior Finding Ledger` baseline backfill rule, stable ledger row `GRS-P1-006`, and `Standard Change Log` row `SCR-003`. |
| `GRS-P1-007` | P1 | New findings were not required to receive stable IDs or enter the ledger before a follow-up fix round could close them. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Prior Finding Ledger`, `Finding Close Format`, and `Review Output Requirements` | The standard now requires stable IDs for new findings and ledger insertion before closure. | None | Read this file and verify the new-finding ID and ledger rules exist. Source refs: this file `96-global-review-standard.md` `Prior Finding Ledger`, `Finding Close Format`, and `Review Output Requirements`, stable ledger row `GRS-P1-007`, and `Standard Change Log` row `SCR-003`. |
| `GRS-P1-008` | P1 | Standard changes could be applied to the split directory without first checking the changed standard for self-consistency. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Standard Change Protocol` and `Standard Self-Review Gate` | The standard now requires a self-review before using a changed standard for whole-directory review. | None | Read this file and verify the self-review gate exists. Source refs: this file `96-global-review-standard.md` `Standard Change Protocol` and `Standard Self-Review Gate`, stable ledger row `GRS-P1-008`, and `Standard Change Log` row `SCR-003`. |
| `GRS-P2-004` | P2 | Mechanical checks did not require a reproducible summary in review output. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Minimum Mechanical Checks` and `Review Output Requirements` | The standard now requires file/link/JSON/ledger/vocabulary mechanical-check summaries. | None | Read this file and verify summary output requirements exist. Source refs: this file `96-global-review-standard.md` `Minimum Mechanical Checks` and `Review Output Requirements`, stable ledger row `GRS-P2-004`, and `Standard Change Log` row `SCR-003`. |
| `GRS-P2-005` | P2 | `recently closed` regression scope was undefined. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Required Review Method` regression-control rules | The standard now defines closed-finding regression scope by touched file/requirement family and changes since the previous standard-change row. | None | Read this file and verify deterministic closed-finding scope exists. Source refs: this file `96-global-review-standard.md` `Required Review Method` regression-control rules, stable ledger row `GRS-P2-005`, and `Standard Change Log` row `SCR-003`. |
| `GRS-P1-009` | P1 | Complete-read coverage did not include the authority files `AGENTS.md` and `README.md`. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Complete-Read Rule` | The complete-read rule now requires complete reads of `AGENTS.md`, `README.md`, and this file before standard-authority coverage can be claimed. | None | Read this file and verify authority-file complete-read coverage exists. Source refs: this file `96-global-review-standard.md` `Complete-Read Rule`, stable ledger row `GRS-P1-009`, and `Standard Change Log` row `SCR-004`. |
| `GRS-P1-010` | P1 | Known split-plan findings from before the standard existed had not been backfilled into the prior-finding ledger. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Prior Finding Ledger` `GRD-*` rows | Known earlier split-plan findings are now backfilled as open `GRD-*` rows. | None | Read this file and verify open `GRD-*` rows exist. Source refs: this file `96-global-review-standard.md` `Prior Finding Ledger` `GRD-*` rows, stable ledger row `GRS-P1-010`, and `Standard Change Log` row `SCR-004`. |
| `GRS-P2-006` | P2 | Standard self-review did not require the mechanical-check summary expected from other reviews. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Standard Self-Review Gate` | The self-review gate now requires the mechanical-check summary scoped to the standard and authority files. | None | Read this file and verify self-review mechanical-summary coverage exists. Source refs: this file `96-global-review-standard.md` `Standard Self-Review Gate`, stable ledger row `GRS-P2-006`, and `Standard Change Log` row `SCR-004`. |
| `GRS-P2-007` | P2 | Standard Self-Review Gate did not explicitly require zero unresolved P0/P1/P2 findings to pass. | Review of `96-global-review-standard.md` on 2026-07-09 | Closed | `96-global-review-standard.md` `Standard Self-Review Gate` and `SCR-005` | The self-review gate now passes only when the changed standard has no unresolved P0/P1/P2 findings. | None | Read this file and verify the gate pass/fail sentence exists. Source refs: this file `96-global-review-standard.md` `Standard Self-Review Gate` and `SCR-005`, stable ledger row `GRS-P2-007`, and `Standard Change Log` row `SCR-005`. |
| `GRS-P1-011` | P1 | The standard had no formal standard-only review mode for reviewing this file without claiming whole-directory coverage. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Review Modes`, `Scoped Mechanical Checks`, `Review Output Requirements`, and `Review Completion Bar` | The standard now declares standard-only review as a separate mode with scoped checks and forbids whole-directory clean claims from that mode. | None | Source refs: this file `96-global-review-standard.md` `Review Modes`, `Scoped Mechanical Checks`, `Review Output Requirements`, and `Review Completion Bar`, stable ledger row `GRS-P1-011`, and `Standard Change Log` row `SCR-006`. Validation: read this file and verify standard-only review mode exists, output requirements include review mode, and completion bar separates standard-only from whole-directory review. |
| `GRS-P1-012` | P1 | The standard allowed ambiguous no-finding output while existing open `GRD-*` ledger blockers remained unresolved. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Review Modes`, `Scoped Mechanical Checks`, and `Review Output Requirements` | The standard now requires current-target findings and existing open prior-ledger blockers to be reported separately and forbids whole-directory cleanliness while open in-scope `GRD-*` rows remain. | None | Source refs: `Prior Finding Ledger` open `GRD-*` rows and review output requirement for no-finding statements; fixed by `SCR-006`. Validation: read this file and verify open-ledger blocker reporting is required in scoped checks and output requirements. |
| `GRS-P2-008` | P2 | Deterministic prose-review acceptance lacked fixed evidence fields, leaving P2 closure auditability inconsistent. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Test and acceptance closure` | The standard now requires reviewer or review mode, checked rule, checked file/line or section, evidence reference, reason no machine fixture/schema is required, and closure result for prose-review acceptance. | None | Source refs: `Test and acceptance closure` P2 prose-review rule; fixed by `SCR-006`. Validation: read this file and verify the deterministic prose-review evidence fields exist. |
| `GRS-P2-009` | P2 | Standard self-review required a mechanical summary but did not define the scoped mechanical checks for standard-only or standard-change review modes. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Scoped Mechanical Checks` | The standard now defines authority-read, structure/ledger, internal-link, open-ledger blocker, and standard-change completeness checks for standard-only and standard-change self-review. | None | Source refs: `Standard Self-Review Gate` mechanical-summary requirement and `Minimum Mechanical Checks`; fixed by `SCR-006`. Validation: read this file and verify scoped mechanical checks are explicit. |
| `GRS-P2-010` | P2 | Backfilled `GRD-*` rows lacked source references, reducing close-out auditability for old split-plan findings. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Prior Finding Ledger` `GRD-*` validation methods and `Finding Close Format` | The standard now requires source references for backfilled findings and each open `GRD-*` row names source files and closure validation. | None | Source refs: `Prior Finding Ledger` backfilled `GRD-*` rows; fixed by `SCR-006`. Validation: read this file and verify source refs are present in each open `GRD-*` validation method. |
| `GRS-P2-011` | P2 | The baseline backfill rule did not state which prior-review categories `SCR-004` covered. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Prior Finding Ledger` baseline backfill rule | The standard now states the `SCR-006` baseline coverage scope and requires any still-relevant pre-`SCR-004` finding outside that scope to be reported as a P1 ledger-completeness issue. | None | Source refs: `Prior Finding Ledger` baseline backfill rule; fixed by `SCR-006`. Validation: read this file and verify the baseline coverage scope sentence exists. |
| `GRS-P1-013` | P1 | `Required Review Inputs` and `Required Review Method` still used whole-directory wording after review modes were added, making standard-only review internally contradictory. | Standard-change self-review on 2026-07-09 | Closed | `96-global-review-standard.md` `Required Review Inputs`, `Complete-Read Rule`, and `Required Review Method` | The standard now scopes full split-directory inputs and split-plan method checks to whole-directory review, while standard-only and standard-change self-review apply scoped checks only to the standard file and authority files. | None | Source refs: `Review Modes`, `Required Review Inputs`, and `Required Review Method`; fixed by `SCR-006`. Validation: read this file and verify required inputs/methods are mode-scoped and no standard-only review is forced to read the whole split directory. |
| `GRS-P1-014` | P1 | `Closed` ledger rows did not satisfy the source-reference close rule added by the standard itself. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Prior Finding Ledger` rows and `Finding Close Format` | Existing closed standard-file rows now include durable source references to this file's ledger rows and standard-change rows. | None | Source refs: this file `96-global-review-standard.md` `Prior Finding Ledger` rows and `Finding Close Format`, stable ledger row `GRS-P1-014`, and `Standard Change Log` row `SCR-007`. Validation: parse closed `GRS-*` rows and verify each has `Source refs:` in the validation method. |
| `GRS-P1-015` | P1 | A closed row used conversation memory as a source reference, violating the frozen authority model. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `GRS-P1-011` row and `Finding Close Format` | The row now cites durable sections in this file and `SCR-006`; source-reference rules now explicitly reject conversation memory, user-message summaries, and assistant recollections. | None | Source refs: this file `96-global-review-standard.md` `GRS-P1-011` row and `Finding Close Format`, stable ledger row `GRS-P1-015`, and `Standard Change Log` row `SCR-007`. Validation: verify no ledger validation method contains `repeated user requests`, `conversation memory`, or `assistant recollections` as an accepted source reference. |
| `GRS-P1-016` | P1 | Closed-finding regression checks had no lifecycle rule for what to do when a closed finding regresses. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Required Review Method` regression-control rules | The regression-control rules now require a new linked regression finding row instead of silently editing old closed rows back to `Open`, and require invalid closure evidence to be reported as a new standard-file finding. | None | Source refs: this file `96-global-review-standard.md` `Required Review Method` regression-control rules, stable ledger row `GRS-P1-016`, and `Standard Change Log` row `SCR-007`. Validation: read the regression-control bullets and verify closed-finding regression and invalid closure evidence handling are defined. |
| `GRS-P1-017` | P1 | Scoped mechanical checks parsed ledger shape but did not validate closed-row semantic compliance. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Scoped Mechanical Checks` | Scoped mechanical checks now require semantic validation of closed rows, source-reference authority, and source-reference precision for backfilled `GRD-*` rows. | None | Source refs: this file `96-global-review-standard.md` `Scoped Mechanical Checks`, stable ledger row `GRS-P1-017`, and `Standard Change Log` row `SCR-007`. Validation: read scoped mechanical checks and verify closed-row semantics and source-reference precision are required. |
| `GRS-P2-012` | P2 | Backfilled `GRD-*` source refs were file-level descriptions instead of file plus section, line, or stable requirement ID. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `GRD-*` validation methods | Each open `GRD-*` row now cites concrete split-plan file line references or stable requirement IDs in its validation method. | None | Source refs: this file `96-global-review-standard.md` `GRD-*` validation methods, stable ledger row `GRS-P2-012`, and `Standard Change Log` row `SCR-007`. Validation: verify every open `GRD-*` row contains source references with `:<line>` or an explicit stable requirement ID. |
| `GRS-P2-013` | P2 | Standard-change completeness required exactly one new change-log row, hiding multi-scope standard edits. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Scoped Mechanical Checks` and `Review Output Requirements` | The standard now allows one or more new change-log rows covering the edit scope, and review output must name all added or changed standard-change IDs. | None | Source refs: this file `96-global-review-standard.md` `Scoped Mechanical Checks` and `Review Output Requirements`, stable ledger row `GRS-P2-013`, and `Standard Change Log` row `SCR-007`. Validation: read the standard-change completeness and output requirements and verify multi-row change support exists. |
| `GRS-P2-014` | P2 | Standard-only optional split-directory context could be used without disclosure in review output. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Scoped Mechanical Checks` and `Review Output Requirements` | The standard now requires review output to disclose whether optional split-directory context was used and which files or checks were used as evidence. | None | Source refs: this file `96-global-review-standard.md` `Scoped Mechanical Checks` and `Review Output Requirements`, stable ledger row `GRS-P2-014`, and `Standard Change Log` row `SCR-007`. Validation: read the optional-context rule and output requirements and verify disclosure is required. |
| `GRS-P2-015` | P2 | Open-ledger blocker reporting could be only a summary without listing blocker IDs. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Scoped Mechanical Checks` and `Review Output Requirements` | The standard now requires open whole-directory blockers to be reported with each open blocker ID. | None | Source refs: this file `96-global-review-standard.md` `Scoped Mechanical Checks` and `Review Output Requirements`, stable ledger row `GRS-P2-015`, and `Standard Change Log` row `SCR-007`. Validation: read open-ledger blocker checks and output requirements and verify blocker IDs are required. |
| `GRS-P1-018` | P1 | Closed standard-file source references could be circular because rows cited their own ledger row without citing the repaired rule sections. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Prior Finding Ledger` rows and `Finding Close Format` | Closed standard-file rows now cite repaired rule sections, stable ledger row IDs, and the closing standard-change rows instead of relying on the row itself alone. | `GRS-P1-014` | Source refs: this file `Finding Close Format`, `Prior Finding Ledger`, stable ledger row `GRS-P1-018`, and `Standard Change Log` row `SCR-008`. Validation: inspect closed `GRS-*` validation methods and verify source refs include repaired sections plus SCR rows, not only their own row IDs. |
| `GRS-P1-019` | P1 | Standard-change protocol was not review-mode aware and could force standard-only review back into whole-directory review. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Standard Change Protocol` and `Standard Self-Review Gate` | The protocol now applies the changed standard to the active review target and re-runs the selected review mode without silent escalation. | `GRS-P1-013` | Source refs: this file `Standard Change Protocol`, `Standard Self-Review Gate`, stable ledger row `GRS-P1-019`, and `Standard Change Log` row `SCR-008`. Validation: read the protocol and verify it refers to active review target and selected review mode. |
| `GRS-P1-020` | P1 | Multi-row standard changes conflicted with singular recently-closed regression scope. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Required Review Method` regression-control rules | Regression scope now covers every closed finding added or changed by any standard-change row in the immediately preceding completed review round. | `GRS-P2-013` | Source refs: this file `Required Review Method`, stable ledger row `GRS-P1-020`, and `Standard Change Log` row `SCR-008`. Validation: read regression-control rules and verify multiple standard-change rows in one round are included in the next regression set. |
| `GRS-P1-021` | P1 | Closed-finding regression links were free text instead of a structured ledger value. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Prior Finding Ledger` table schema, `Finding Close Format`, and regression-control rules | The ledger now has a `Linked finding` column, and regression rows must put the regressed finding ID there. | `GRS-P1-016` | Source refs: this file `Prior Finding Ledger`, `Finding Close Format`, `Required Review Method`, stable ledger row `GRS-P1-021`, and `Standard Change Log` row `SCR-008`. Validation: parse ledger rows and verify a `Linked finding` column exists with `None` or one stable finding ID. |
| `GRS-P1-022` | P1 | Baseline backfill still depended on non-durable earlier-review knowledge. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Required Review Method` regression-control rules and `Prior Finding Ledger` baseline rule | Baseline coverage now depends only on durable prior-review sources named in this file; remembered findings must first become durable ledger rows before they can affect clean coverage. | `GRS-P1-006` | Source refs: this file `Required Review Method`, `Prior Finding Ledger`, stable ledger row `GRS-P1-022`, and `Standard Change Log` row `SCR-008`. Validation: read baseline rules and verify non-durable conversation history is not required for full regression coverage. |
| `GRS-P2-016` | P2 | Ledger introduction still scoped new findings to global review rounds instead of all review modes. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Prior Finding Ledger` introduction | The ledger introduction now says new findings from any review mode must receive stable IDs and be added before closure. | `GRS-P1-011` | Source refs: this file `Prior Finding Ledger`, stable ledger row `GRS-P2-016`, and `Standard Change Log` row `SCR-008`. Validation: read ledger introduction and verify it says `any review mode`. |
| `GRS-P2-017` | P2 | Standard-file source refs were allowed to stop at section name plus SCR, weaker than finding line-reference expectations. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Finding Close Format` | Standard-file source refs now require section name plus a line reference or stable ledger row ID and the relevant standard-change ID. | `GRS-P1-014` | Source refs: this file `Finding Close Format`, stable ledger row `GRS-P2-017`, and `Standard Change Log` row `SCR-008`. Validation: read source-reference rules and verify standard-file source refs need section plus line or stable ledger row ID. |
| `GRS-P2-018` | P2 | Standard-change rows did not require forward traceability to fixed finding IDs. | Standard-only review on 2026-07-09 | Closed | `96-global-review-standard.md` `Standard Change Log`, `Scoped Mechanical Checks`, and `Prior Finding Ledger` | Standard-change rows that close findings must name fixed finding IDs, and scoped mechanical checks require this mapping. | `GRS-P2-013` | Source refs: this file `Standard Change Log`, `Scoped Mechanical Checks`, `Prior Finding Ledger`, stable ledger row `GRS-P2-018`, and `Standard Change Log` row `SCR-008`. Validation: inspect SCR rows and verify rows that close findings include fixed finding IDs. |
| `GRD-P1-001` | P1 | `97-split-added-requirements-ledger.md` is required by the index but missing from the split output inventory. | Whole-directory review before `SCR-004` | Closed | `98-original-to-split-audit.md` split output inventory | The split output inventory now includes `97-split-added-requirements-ledger.md` as a first-class output file. | None | Source refs: `00-index.md:28`, `00-index.md:82`, `00-index.md:94`, `98-original-to-split-audit.md` split output inventory row for `97-split-added-requirements-ledger.md`, stable ledger row `GRD-P1-001`, and `Standard Change Log` row `SCR-009`. Validation: verify the split output inventory includes `97-split-added-requirements-ledger.md`. |
| `GRD-P1-002` | P1 | `import_gdd_form` requires an explicit legacy import sidecar, but the split plan does not define the sidecar path and schema. | Whole-directory review before `SCR-004` | Closed | `02a-route-state-artifacts.md` workflow recommendation contract | The route-state artifacts now define canonical legacy import sidecar path `meta/routes/gdd-question-form/legacy-import/latest.json`, schema fields, source hashes, confirmation evidence, and stale behavior. | None | Source refs: `02a-route-state-artifacts.md` `import_gdd_form` workflow recommendation rules, `02b-backend-api-contracts.md` workflow recommendation mapping, `03-testing-observability-admin.md` import action tests, stable ledger row `GRD-P1-002`, and `Standard Change Log` row `SCR-009`. Validation: verify route-state artifacts define legacy import sidecar path, schema, hashes, evidence, confirmation, and stale validation. |
| `GRD-P1-003` | P1 | Metadata DB table contracts are claimed for game-type maintenance records and project-delete tombstones, but concrete minimum table contracts are missing. | Whole-directory review before `SCR-004` | Closed | `02a-route-state-artifacts.md` admin review queue ownership section and `07-godot-diagnostics-quality-gates.md` diagnostic index section | The split plan now declares minimum metadata DB table contracts for admin review queue, diagnostic index, game-type maintenance records, and project-delete tombstones, including keys, columns, indexes, concurrency, export/readback, and deleted-project lookup behavior. | None | Source refs: `02a-route-state-artifacts.md` metadata DB table contract subsections, `07-godot-diagnostics-quality-gates.md` diagnostic index table contract, `02b-backend-api-contracts.md` metadata DB API requirements, stable ledger row `GRD-P1-003`, and `Standard Change Log` row `SCR-009`. Validation: verify all claimed metadata DB record families have minimum columns, stable keys, indexes, concurrency behavior, export/readback rules, and deleted-project lookup behavior. |
| `GRD-P1-004` | P1 | `prototype-skeleton-guard` is a Phase 0B dependency but is omitted from Phase 1 route module contract and guard-test coverage. | Whole-directory review before `SCR-004` | Closed | `08-implementation-phases.md`, `02b-backend-api-contracts.md`, `03-testing-observability-admin.md`, and `97-split-added-requirements-ledger.md` | The Phase 1 route module contract set and route module contract tests now include `prototype-skeleton-guard`; the backend contract and split-added ledger already bind the guard to descriptor/readback and Phase 0B dependency enforcement. | None | Source refs: `08-implementation-phases.md` Phase 1 route module contract list, `02b-backend-api-contracts.md` prototype skeleton guard contract, `03-testing-observability-admin.md` Phase 1 route module contract test list, `97-split-added-requirements-ledger.md` skeleton guard row, stable ledger row `GRD-P1-004`, and `Standard Change Log` row `SCR-009`. Validation: verify Phase 1 route contract tests and exit criteria include `prototype-skeleton-guard` where the dependency matrix requires it. |
| `GRD-P1-005` | P1 | Full-target UI capability ledger schedule fields are required by schedule acceptance but absent from the ledger schema line. | Whole-directory review before `SCR-004` | Closed | `10-recommended-first-slice.md` full-target closure ledger schema | The full-target closure ledger schema now includes `firstRequiredPhase`, `trigger`, `ownerEvidence`, and `currentCoverageStatus` for each capability package. | None | Source refs: `10-recommended-first-slice.md` full-target schedule acceptance and ledger schema, `03-testing-observability-admin.md` full-target schedule-field tests, stable ledger row `GRD-P1-005`, and `Standard Change Log` row `SCR-009`. Validation: verify the ledger schema includes `firstRequiredPhase`, `trigger`, `ownerEvidence`, and `currentCoverageStatus`. |
| `GRD-P1-006` | P1 | `prototype-skeleton-guard` was added to Phase 1 deliverables but remained omitted from `08-implementation-phases.md` Phase 1 route module contract test and guard-test exit lists. | Whole-directory review after `SCR-009` | Closed | `08-implementation-phases.md` Phase 1 exit criteria | The Phase 1 route module contract test list and route contracts/guard tests list now both include `prototype-skeleton-guard`. | `GRD-P1-004` | Source refs: `08-implementation-phases.md` Phase 1 deliverables, Phase 1 route module contract tests, and route contracts/guard tests; stable ledger row `GRD-P1-006`; linked prior finding `GRD-P1-004`; and `Standard Change Log` row `SCR-010`. Validation: verify the three Phase 1 `prototype-skeleton-guard` references are present in deliverables, route module contract tests, and route contracts/guard tests. |
| `GRD-P2-001` | P2 | UI style formal JSON Schema conversion wording duplicates itself and weakens schema/profile parity. | Whole-directory review before `SCR-004` | Closed | `06b-ui-style-snapshot-schema.md` Phase 0 schema authority | The duplicate formal JSON Schema conversion sentence was removed, leaving one fixture/schema/profile parity rule. | None | Source refs: `06b-ui-style-snapshot-schema.md` Phase 0 schema authority, `06d-ui-style-schema-acceptance.md` schema acceptance, stable ledger row `GRD-P2-001`, and `Standard Change Log` row `SCR-009`. Validation: verify the duplicate wording is removed and schema/profile parity remains explicit. |
| `GRD-P2-002` | P2 | The split-added ledger row for `import_gdd_form` omits the testing owner document. | Whole-directory review before `SCR-004` | Closed | `97-split-added-requirements-ledger.md` import GDD form row | The split-added ledger row now links `03-testing-observability-admin.md` as a testing owner document for descriptor, browser, service, and migration tests. | None | Source refs: `97-split-added-requirements-ledger.md` import row, `03-testing-observability-admin.md` import action tests, stable ledger row `GRD-P2-002`, and `Standard Change Log` row `SCR-009`. Validation: verify the row links the testing/observability document that owns descriptor, browser, service, and migration tests. |
| `GRD-P2-003` | P2 | Route/readback status subsets do not explain the boundary between artifact `ready` and route `succeeded`. | Whole-directory review before `SCR-004` | Closed | `02c-frontend-migration-compatibility.md` status vocabulary and `04c-route-operation-governance.md` progress rules | The status vocabulary now separates stage, route/readback, readiness, UI matrix, and operation statuses, and progress rules define when route/readback `succeeded` maps to display-stage `completed`. | None | Source refs: `02c-frontend-migration-compatibility.md` status vocabulary and mapping acceptance, `04c-route-operation-governance.md` progress mapping, `03-testing-observability-admin.md` browser status tests, stable ledger row `GRD-P2-003`, and `Standard Change Log` row `SCR-009`. Validation: verify status vocabulary text explains why sidecar subsets omit or include `succeeded` and how browser mapping handles completion. |

### Finding Close Format

A finding may be marked `Closed` only when its ledger row includes:

1. Stable `finding_id`.
2. Severity.
3. Summary.
4. First found date or round.
5. Status: `Open`, `Closed`, or `OutOfScopeByStandardChange`.
6. Fix reference with file and section or line-level target when available.
7. Closure reason.
8. Linked finding value: `None` or one stable finding ID that this row regresses, supersedes, or directly repairs.
9. Validation method.
10. Source reference for the requirement or prior finding being fixed when the finding is backfilled, derived from an earlier review round, or closed after `SCR-007`.

`OutOfScopeByStandardChange` requires a `standard_change_id` in the closure reason.

Source references must be durable and reviewable under the selected review mode. For standard-file findings, use this file's section name plus a line reference or stable ledger row ID and the relevant `standard_change_id`. For whole-directory findings, use the target split file plus section, line, or stable requirement ID. Do not use conversation memory, user-message summaries, or assistant recollections as a source reference.

New findings reported in a review output must include the stable ID that will be inserted into this ledger. If the reviewer is not editing the ledger in the same turn, the output must say that the finding is `PendingLedgerEntry` and cannot be treated as closed until inserted.

## Review Output Requirements

Each review response must:

1. State the review mode: whole-directory review, standard-only review, or standard-change self-review.
2. State whether this review round changed the standard. If it did, name all `standard_change_id` values added or changed by the round.
3. State that the review standard authority set was limited to `AGENTS.md`, `README.md`, and this file.
4. State whether the Standard Self-Review Gate ran when the standard changed.
5. State the mechanical-check summary required for the selected review mode. For whole-directory review, include file counts by type, missing link count, parsed JSON count and failures, prior-finding counts by status, vocabulary families checked, and skipped checks if any. For standard-only review or standard-change self-review, include authority-file read coverage, standard structure and ledger validity, closed-row semantic validity, internal link count, open-ledger blocker IDs, optional-context usage, and skipped scoped checks if any.
6. Lead with findings, ordered by severity.
7. Assign every new finding a stable finding ID.
8. Use P0/P1/P2 labels.
9. Include file and line references for each finding.
10. Explain the global impact, not just the local typo or missing sentence.
11. Separate current-target findings from existing open prior-ledger blockers. A review may say "no new P0/P1/P2 findings in the current target" only when that is true, and may say "no P0/P1/P2 findings remain for the whole split directory" only when all in-scope open ledger blockers are closed or out of scope.
12. Avoid listing optional issues.
13. State whether any required mechanical check was skipped.

## Review Completion Bar

A review round is complete only when:

1. The reviewer has used only `AGENTS.md`, `README.md`, and this file as the review-standard authority set.
2. The selected review mode has been declared before conclusions are reported.
3. For whole-directory review, the whole split directory has been checked as the review target under the complete-read rule.
4. For standard-only review or standard-change self-review, the standard file and authority files have been checked under the scoped mechanical checks, and the output does not claim whole-directory coverage.
5. The minimum mechanical checks for the selected mode have run or skipped checks are reported with residual risk.
6. Prior findings from `Prior Finding Ledger` have been considered for regression.
7. Any still-relevant earlier finding missing from `Prior Finding Ledger` has been reported as a P1 ledger-completeness issue.
8. Every new finding in the review output has a stable finding ID and is either inserted into this ledger or marked `PendingLedgerEntry`.
9. Any new criterion used by the reviewer already exists in this file, or this file was updated before the criterion was applied and passed the Standard Self-Review Gate.
