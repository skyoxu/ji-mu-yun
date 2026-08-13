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

- Upgrade bmad-spec typed package descriptor and selection-registry producer.
- Add VDD source-freeze create/repair consumer behavior.
- Add exact-cover deterministic validator, bounded extraction, fingerprints,
  shards, recovery, and non-authorizing receipts.
- Add the existing authorization-owner receipt preflight prerequisite.

## Slice Order

| Slice | Behavior | RED / negative | GREEN / acceptance | Recovery |
| --- | --- | --- | --- | --- |
| S0 | bmad-spec emits typed descriptor, selection record, and current pointer atomically. | Missing pointer, stale record, role drift, and tampered descriptor reject. | Create/refresh and tamper fixtures recompute the same selection identity. | Restore the last valid pointer; never synthesize registry state. |
| S1 | VDD freezes the complete package into `vdd-source-freeze-manifest.v1`. | Caller-reduced universe, provenance promotion, path/hash drift reject. | Independent manifest recomputation and create/repair fixtures pass. | Restart from package selection; preserve prior evidence as stale. |
| S2 | Exact-cover proves sound-and-complete coverage with deterministic hashes. | Unknown, duplicate, orphan, uncovered, wrong binding, and weakening mutations block. | VCEC-A01..A12 and paired producer/consumer golden vectors pass. | Repair requirements or validator input; no semantic retry for deterministic defects. |
| S3 | Recovery, retry, shard reuse, instability, and semantic handoff are bounded. | Stale checkpoint, unstable shard, unauthorized handoff, or output overflow blocks. | VCEC-A13..A42 fixtures pass; aggregate is always recomputed. | Resume only from authorized checkpoint lineage; quarantine unstable shards. |
| S4 | Authorization prerequisite consumes a current conformant receipt. | Missing, stale, mismatched, prose, or boolean receipt rejects. | VCEC-A17/A18/A25/A26 composition passes. | Leave lifecycle unchanged and return typed prerequisite failure. |
| S5 | Dogfood create, exact-cover, optional review, repair, and rerun. | Legacy schema and target mutation fixtures fail closed. | VCEC-A24..A43 terminal replay passes with current artifacts. | Start a new requirements identity after explicit repair. |

## Lifecycle

VDD owns `draft -> plan-ready` only. This plan does not authorize implementation,
acceptance, commit, release, or archive. The maintainer authorization adapter
remains the sole owner of `implementation-authorized`.

## Validation

Run the commands in `command-registry.v1.json`, then one terminal full replay.
Knowledge is bound by `knowledge-context.freeze.v1.json`; its catalog freshness
is recorded as an explicit stale warning under the VDD opt-in policy.
