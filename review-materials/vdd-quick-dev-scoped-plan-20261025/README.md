# Current P1-repaired VDD / Quick Dev review entry

This revision publishes the restricted planned-test declaration repair and the
actual native successor. It is production self-check passed, NOT independent
A/B GO, implementation-complete, final Acceptance or permission to merge.

## Current target and frozen predecessor

Use `../../execution-plans/2026-10-25-vdd-knowledge-query-planned-tests-repair-final/`
for the current12-slice plan. Canonical semantic identity:
`sha256:955bca2628a236468cb12b236d2d51f26a62944f18fbdb3d7f8c7716a3ce8b5c`.

The frozen dadd5ea869108893bdfe014c75a06c363b720cc9 predecessor remains under
`../../execution-plans/2026-10-24-vdd-knowledge-query-scoped-v3-r3/` with identity
`sha256:7aa75d0cfda1125fa9c6dab354032a4fe12f19085a56254256df20b46c5216a7`.
It received NO-GO because its absent tests were not declared planned. Do not
use that older directory as the repaired target or rewrite its evidence.

Start with `publication-manifest.json` for exact bytes/roles and
`../../logs/vdd-q1-planned-tests-fix-20261025/REPORT.md` for the production result.
The report's local/unpushed paragraph records the completed repair BEFORE this
publication and is deliberately preserved. This branch's actual latest commit
SHA identifies the publication; the old source HEAD is provenance only.

## Repair and actual evidence

The public `--repair-quick-dev-handoff-from` route now accepts explicit
`--handoff-planned-test <path>` declarations. It changes only each affected
slice's planned_new_files and derived slice hash. The305 obligations,
305 complete Acceptance contracts,305 failure intents, contexts, commands,
owners, write scope, membership, dependency graph and terminal predicates are
unchanged. It creates no tests, new RED roles or implementation authority.

Evidence under `../../logs/vdd-q1-planned-tests-fix-20261025/`:

- `native-verified-result.json`, `verified-launch.json`,
  `verified-process-exit.json`:actual public owner invocation/result.
- `final-q1-results.json`, `final-verification.json`, `final-plan-delta.json`:
  actual12/12 Q1 positives and exact preserved semantics/delta.
- `targeted-final-v3.log`:32 deterministic positive/negative tests passed.
- `default-compatibility.log`:3 default-mode compatibility cases passed.
- `package-final.log`, `skill-final-validation.json`:22 package tests and
  native Skill checks passed.
- `final-plan-manifest.json`:exact successor artifact file hashes.

Original12 Q1 rejections are retained in
`../../logs/vdd-q1-planned-tests-repair-20261025/q1-reproduction.json`.
The public producer reuses V1/V4 and runs native source/semantic/coverage/
feasibility/handoff checks. No new model call or full semantic recompilation
was needed. This publication did not rerun any of those checks.

## Scope and sources

The active scope remains246 retained,59 reduced and25 deployment-side old
clauses, yielding305 current obligations. All330 old IDs remain traceable in
`../../logs/scoped-input-preparation-20261024-v3/old-to-draft-map.json` and the
classification ledger. The seven exact current inputs, source index, four
approved dependency decisions and deployment ledger remain unchanged there.
Original requirements and delivered PRD/SPEC/architecture files are historical
inputs/provenance, never instructions to run or review BMAD.

## Planned tests are not implemented tests

The two active .py paths remain absent. The current successor declares them
planned, and Q1 now accepts that legitimate pre-authoring state. Q2 must still
author correct retained-scope tests. Their mixed historical originals remain
exact inert bytes under `candidate-test-snapshots/<original-path>.txt`, with
source paths/hashes in the manifest. Do not restore those files wholesale or
invoke BMAD to satisfy old scenarios. No actual probe, RED/GREEN, terminal/Q8
or runtime Windows validation is claimed by Q1.

## Publication boundaries

Only the P1 source/docs/tests, final successor, minimal raw validation receipts
and this entry/manifest changed in this publication. Intermediate repair plans,
raw caches, full host transcripts, credentials, BMAD installation and unrelated
logs/edits are excluded. No BMAD-exclusive wrapper/hook/registration increment
is restored. No PR, merge, force push, CI monitoring, external review or
implementation is performed. The original candidate and evidence remain local.
