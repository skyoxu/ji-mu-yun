---
plan_id: vdd-conformance-exact-cover
profile: self-hosted
state: plan-ready
authority: _bmad-output/specs/spec-vdd-conformance-exact-cover/SPEC.md
---

# VDD Conformance Exact-Cover

This plan consumes the complete `canonical-spec-package.v1` graph selected by
the current bmad-spec pointer. The 2026-08-10 requirements document is
provenance only.

## Scope

- Preserve and harden the existing bmad-spec typed package descriptor and
  selection-registry producer through regression and mutation fixtures.
- Add VDD source-freeze create/repair consumer behavior.
- Add exact-cover deterministic validator, bounded extraction, fingerprints,
  shards, recovery, and non-authorizing receipts.
- Add the existing authorization-owner receipt preflight prerequisite.

## Slice Order

| Slice | Behavior | RED / negative | GREEN / acceptance | Recovery |
| --- | --- | --- | --- | --- |
| S0 | Existing bmad-spec producer remains the upstream selection authority. | Missing pointer, stale record, role drift, and tampered descriptor reject. | Existing producer tests plus create/refresh/mutation regression pass. | Restore the last valid pointer; never synthesize registry state. |
| S1 | VDD freezes the complete package into `vdd-source-freeze-manifest.v1`. | Caller-reduced universe, provenance promotion, path/hash drift reject. | Independent manifest recomputation and create/repair fixtures pass. | Restart from package selection; preserve prior evidence as stale. |
| S2 | Exact-cover proves sound-and-complete coverage with deterministic hashes. | Unknown, duplicate, orphan, uncovered, wrong binding, and weakening mutations block. | VCEC-A01..A12 and paired producer/consumer golden vectors pass. | Repair requirements or validator input; no semantic retry for deterministic defects. |
| S3a | Semantic handoff and VDD repair input remain explicit and non-authorizing. | Unbound, stale, or implicit repair input rejects. | VCEC-A13..A16 and A39 pass. | Preserve prior requirements and await explicit repair. |
| S3b | Failure taxonomy, bounded retry, and stop-loss are deterministic. | Retry on deterministic defects, unknown family, or missing attempt identity rejects. | VCEC-A30..A32, A40, A42 pass. | Stop at policy ceiling and route typed action. |
| S3c | Fingerprints, shards, reuse, and instability preserve the full universe. | Hash drift, unsafe reuse, deleted quarantine, or vote-as-truth rejects. | VCEC-A33..A38 pass. | Re-run affected shards; quarantine unstable shards. |
| S3d | Recovery checkpoints and bounded model context are restartable. | Stale lineage, artifact drift, raw source recovery, or overflow rejects. | VCEC-A22..A24 and A41 pass. | Resume only from authorized checkpoint lineage. |
| S4 | Authorization prerequisite consumes a current conformant receipt. | Missing, stale, mismatched, prose, or boolean receipt rejects. | Round 5 mapping binds VCEC-A17..A19 and composition evidence; implementation remains pending until the current command wrapper passes. | Leave lifecycle unchanged and return typed prerequisite failure. |
| S5 | Dogfood create, exact-cover, optional review, repair, and rerun. | Legacy schema and target mutation fixtures fail closed. | Round 5 mapping binds VCEC-A25..A27; Round 8 terminal invokes dogfood through the same implementation wrapper. | Start a new requirements identity after explicit repair. |

## Lifecycle

VDD owns `draft -> plan-ready` only. This plan does not authorize implementation,
acceptance, commit, release, or archive. The maintainer authorization adapter
remains the sole owner of `implementation-authorized`.

## Validation

Run the commands in `command-registry.v1.json`, then one Round 7 terminal full replay.
The authoritative requirement/acceptance coverage is in
`repair/round-5/requirements-acceptance-slice-command.v1.json`; the Round 1
mapping is immutable historical evidence only.
Knowledge is bound by `knowledge-context.freeze.v1.json`; its catalog freshness
is recorded as an explicit stale warning under the VDD opt-in policy.
