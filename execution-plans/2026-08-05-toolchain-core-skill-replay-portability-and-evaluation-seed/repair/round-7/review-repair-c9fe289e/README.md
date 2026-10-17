# Direct repair of two round-7 review findings

Base: `c9fe289edb01011a9810f5473e3a0574f0525d00`.
Authority: ADR-0041 (plan predicates and lifecycle separation), ADR-0058
(non-authorizing replay), and the existing TC-D1 canonical Spec package.

## Scope and disposition

- `O-C1E267D7452D` / AO-17a: all derived replay, seed, matrix, review, and
  Quick Dev artifacts require an explicit `authorizes=[]`. Every non-empty
  value fails, including an apparently genuine grant. Missing and malformed
  fields fail. The empty-array control must satisfy this invariant. This
  never grants Acceptance and does not alter lifecycle-owner approval.
- `O-B9EAA8169232` / AO-09e: reconstruct the original binding from referenced
  bytes, verify it, then execute a fresh replay with that same identity.
  A valid positive control is mandatory. Missing/mismatched originals reject
  before launch; echoed identity, skipped launch, silent rebinding, and reused
  historical output cannot satisfy the positive control.
- S14 is rebound from knowledge publication to the actual repository replay
  implementation and tests. S19 adds that replay owner while retaining its
  other existing obligations. No PhaseA/runtime write scope is introduced.
- FR-9/S25 is unchanged, including its bidirectional Consumer Manifest rule.

Sources: `authority-and-open-questions.md` / Confirmed Boundaries (empty
authorization), `domain-contract.md` / Historical and Seed Invariants and
Result and Snapshot Contract, and Architecture AD-7a. These are files in the
existing canonical TC-D1 package; this note creates no replacement Spec/plan.

## Publication and evidence status

This is a user-authorized direct LLM repair, not a VDD compiler run. The repair
script derives new Acceptance and failure IDs with the repository algorithms,
updates coverage/proof/routing/context projections, and records new direct
slice identities and bundle identity. Direct slice hashes deliberately do not
claim to be regenerated compiler bucket hashes.

All replaced file bytes are retained under `before/`. Worker caches and prior
compiler results remain historical and were not rewritten. Old semantic
alignment, recall, and feasibility results are explicitly stale. The current
compiler state is `repair-vdd`, not a fabricated `plan-ready` or Acceptance.
Structural and semantic-chain checks do not prove product behavior or full
source coverage. Independent semantic review and any required canonical
publication remain pending; do not hand-author a passing lifecycle state.

When resuming canonical compilation, explicitly consume these corrected
contracts together with the complete selected Spec/Architecture package and
invalidate dependent V1/V3/V4 results. Blindly reusing the old atomic-table-only
extraction/caches can regenerate the rejected contracts. Recheck both positive
controls in the final published bundle, not merely the worker prompt.

## C3

C3 remains OPEN. No product-scope approval, alternate-validator Trust Approval,
or Consumer exception is issued here. Only decisions relying on those approvals
are blocked. The historical permitted validator source remains in force and
no Consumer may be omitted without an explicit, bound approval from a confirmed
owner. Unrelated work does not acquire an additional global C3 gate.

## Local verification

Run from the repository root (Windows commands):

```text
py -3 execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/review-repair-c9fe289e/repair_plan.py --check
py -3 -m unittest discover -s execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/review-repair-c9fe289e -p test_repair_plan.py -v
git diff --check
```

These are offline plan-repair checks. They run no model, VDD, Quick Dev,
Acceptance, or product replay. Linux evidence is recorded under
`logs/08-05-real-skill-replay/direct-round7-review-repair-c9fe289e/`.
Windows verification is pending. Do not treat either run as product closure.
