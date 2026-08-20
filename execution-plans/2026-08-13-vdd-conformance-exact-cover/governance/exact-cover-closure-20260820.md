# Exact-Cover Closure Governance

## Scope And Authority

This is a non-authorizing governance record for the implemented 8-13 exact-cover
capability. It does not reopen implementation or Acceptance.

- Implemented-by: `2026-08-13-vdd-conformance-exact-cover`.
- Cross-plan validated-by: `2026-08-15-acceptance-review-bootstrap-efficiency`,
  `acceptance-runs/acceptance-9d4f50ad88a01456/finalization/acceptance-passed.v1.json`,
  `sha256:ae95d320635f2567fc3938c7144ab3615208d5619531497c169f1cd450e3c4d4`.
- Current source-freeze: `governance/source-freeze-20260820.v1.json`, canonical
  hash `sha256:5fc24efa6edbefeb33626362f1d019f7f29d4465bdcd78647a8f86e9e2bb82fc`.
- Current Canonical Spec Package selection remains
  `sha256:f6d6887ee80f686fb1cbb7b4acdff4c1a257e5762e83287996bfb77396448bdc`.

## VCEC Coverage Matrix

| Requirements | Acceptance | Implemented command / behavior | Current evidence |
| --- | --- | --- | --- |
| VCEC-001..002, 006..011, 026 | A01..A03, A07..A12, A28..A29 | `exact-cover`, `exact-cover-negative` | Core and mutation validator programs exist; current full mapping is stale, see delta. |
| VCEC-003..005, 019..020 | A04..A06, A20..A21 | `vdd-source-freeze`, manifest composition, scope/readonly negatives | Current source-freeze was regenerated; behavior runner and composition validator pass. |
| VCEC-012..015, 033 | A13..A16, A39 | `semantic-handoff` and VDD repair-input protocol | Formal conclusion: open semantic dispositions are deferred boundaries, not accepted decisions. No lifecycle authority is granted. |
| VCEC-016..018 | A17..A19 | authorization preflight and negative preflight | Negative preflight remains an expected typed block until a current conformant exact-cover receipt exists. |
| VCEC-021..023, 035 | A22..A24, A41 | recovery context and negative lineage/overflow checks | Positive recovery validator passes; negative validator rejects as designed. |
| VCEC-024..025 | A25..A27 | `exact-cover-dogfood`, composition negative | Current dogfood runner passes the create/repair/rerun fixture path; negative composition remains a designed non-zero result. |
| VCEC-027..028, 034 | A30..A32, A40, A42 | retry taxonomy and negative mutation checks | Positive retry taxonomy validator passes; negative validator rejects as designed. |
| VCEC-029..032 | A33..A38 | fingerprint/shard and negative mutation checks | Existing implementation coverage retained; current plan mapping must be rebased before it can establish a new full receipt. |
| VCEC-036 | VCEC-A43 | bmad-spec selection-registry regression / mutation fixtures | Existing selection registry is the upstream authority. The current negative fixture deliberately exits non-zero; it is not a green proof by itself. |

## Current Formal Result

At current HEAD, exact-cover with the regenerated source-freeze returns
`blocked/deterministic_coverage_gap/frozen_obligation_universe_mismatch`.
This is an authority/mapping freshness delta: the Round 5 mapping contains 705
obligations while the current frozen package produces 716. Its 36 canonical
VCEC IDs and 43 acceptance IDs remain present, but source hashes embedded in
non-canonical obligation IDs changed, so the old mapping cannot claim current
full-universe conformance.

The current inventory has 80 active obligations, 108 explicit deferred semantic
boundaries, and 528 `not_applicable` structural or explanatory records. The
deferred records have no accepted review/disposition record in the Round 5
mapping. Their official conclusion is therefore `deferred`; they must not be
silently promoted, dismissed as covered, or represented as accepted.

## Uncovered Delta And Next Gate

The only uncovered delta is a VDD-owned mapping refresh bound to the current
source-freeze, followed by the existing exact-cover validator. It must preserve
the 36 requirement IDs, 43 acceptance IDs, and explicit treatment of all
deferred boundaries. This governance record does not perform that repair.

No compact Acceptance is warranted yet: no behavior regression was found in
the source-freeze, retry, recovery, or dogfood positive programs, and the
remaining gap is upstream VDD mapping/semantic authority rather than an
unvalidated implementation delta. If the refreshed mapping introduces behavior
or source changes beyond this custody refresh, only that changed set requires a
new focused Acceptance.
