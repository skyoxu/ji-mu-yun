---
type: implementation-reconcile-review
round: r19
status: append-only-reality-reconcile
architecture_status: unchanged-final
source_spine: _bmad-output/planning-artifacts/architecture/architecture-jimuyun-2026-08-31/ARCHITECTURE-SPINE.md
implementation_baseline: 3b33a3e80c7834df8d1317a58c396e5b15cb3e27
authorizes: []
---

# R19 — Chapter 4/5/6 Implementation Reality Reconcile

## Scope and authority

This review is an append-only implementation-reality reconciliation. It does **not** amend, supersede, or rewrite the final Architecture spine, canonical SPEC, PRD, or their normative companions. Its only purpose is to classify each item that the final Architecture left under `Deferred` against the implementation reality reached by the Chapter 4/5/6 branch.

Allowed dispositions are:

- `resolved-by-implementation`: the deferred choice is now mechanically frozen by current code/contracts and regression evidence.
- `still-deferred-outside-v1`: the item remains intentionally outside the initial Windows/single-run v1 scope.
- `trigger-based-future-decision`: current v1 fail-closes without requiring the richer future mechanism; the decision is required only when its trigger is introduced.
- `acceptance-blocked`: implementation support exists, but the product acceptance evidence required to close the item has not yet been produced in a capable environment.

No disposition below grants runtime evidence, Acceptance, promotion, merge, release, review, binding, or authorization authority.

## Deferred decision reconciliation

| Architecture Deferred item | Disposition | Current implementation reality / binding evidence |
| --- | --- | --- |
| obligation↔Acceptance normalization | `resolved-by-implementation` | `.agents/skills/vdd-execution-plan/scripts/semantic_compiler.py` assigns stable obligation identities, requires exact Acceptance obligation groups, rejects duplicate/overlapping semantic groups, and V4/source-recall gates reject missing or invented obligations. |
| slice split/merge thresholds | `resolved-by-implementation` | `semantic_compiler.py::partition_slices` deterministically buckets by owner, lane, state transition, failure families, snapshot/write compatibility and planned files; conflicting tuples split and stable `S<n>` ordering is content-derived. No numeric Acceptance-count threshold is authoritative. |
| deterministic semantic validator boundary | `resolved-by-implementation` | `semantic_compiler_gate.py`, `semantic_compiler_authority.py`, `semantic_plan_contract.py`, and semantic-chain audit own deterministic schema/source/cover/predicate decisions; model workers are read-only candidates and cannot publish plan-ready or runtime truth. |
| v1 compatibility adapter projection | `resolved-by-implementation` | Quick Dev `legacy_compat.py` and current router treat legacy v1 evidence as read-only compatibility input and return projection/repair decisions without rewriting historical evidence or granting current completion authority. |
| 60-minute task measurement | `acceptance-blocked` | Product target remains ≤60 minutes for a fresh medium standard-profile task. A live blind benchmark harness is required to record wall time, worker calls, retries and final closure using real semantic and implementation workers; deterministic fixture tests do not close this item. |
| profile scope differences | `resolved-by-implementation` | Quick Dev `profile-policy.v1.json` freezes `fast-ship|standard|self-hosted` execution scope while preserving one truth floor; self-hosted adds detached promotion, and standard/self-hosted require the declared regression gate. VDD planning profiles remain a separate planning concern. |
| detached fixture/judge independence procedure | `resolved-by-implementation` | `detached_promotion.py` canonical `detached-judge-bundle.v1` requires content-addressed external judge/oracle/fixtures, read-only-open and promotion-time revalidation; stable self-hosted entry rejects compatibility v2 as promotion authority and requires positive/negative/mutation plus exact failure-family cover. |
| comparator types and stdout/stderr normalization | `still-deferred-outside-v1` | Current v1 uses the Windows/pytest observable contract and normalized deterministic failure fingerprint. Cross-platform comparator families and generalized stdout/stderr normalization remain intentionally outside initial v1. |
| judge lifecycle, retention and revocation | `still-deferred-outside-v1` | Current self-hosted path supports a single frozen detached judge identity. Multi-judge rotation, retention, revocation and lifecycle operations are not required for the initial single-judge path. |
| runnable rollback probe interface | `trigger-based-future-decision` | Slice contracts carry rollback scope, but no recovery-class oracle currently requires executing rollback as a completion predicate. Define the runnable probe only before such an oracle is admitted. |
| unexpected-green proof | `trigger-based-future-decision` | Current judge classifies `unexpected-green` and blocks expected-RED progression; current routing fails closed to repair/current-behavior handling. A richer regression/current-behavior proof schema must be frozen before unexpected-green is allowed to become reusable proof rather than a blocker. |
| stop-loss numeric threshold | `resolved-by-implementation` | Current semantic-worker and Quick Dev repeat guards stop unchanged deterministic failure after two identical fingerprints; a third unchanged rerun is blocked before process launch. |
| semantic-change partial reuse | `resolved-by-implementation` | `change-impact-matrix.v1.json`, current-snapshot resolver and observation-aware recommendation implement conservative selective reuse/invalidation. Semantic/source changes recompute coverage and invalidate affected lifecycle evidence; unknown paths fail closed. |
| concurrency and resource quotas | `still-deferred-outside-v1` | AD-13 explicitly scopes the initial executor to single-run local Windows operation. Parallel-run locking, quota and scheduler policy remain outside v1. |
| evidence retention and cleanup | `still-deferred-outside-v1` | Current evidence remains append-only/create-if-absent. Long-lived retention and cleanup are operational concerns deferred until an automated evidence store/cleanup service exists. |
| cross-platform execution normalization | `still-deferred-outside-v1` | Initial supported host remains Windows with runtime-resolved `py -3`/pytest behavior. Non-Windows normalization is deferred until a non-Windows executor is enabled. |

## Reconciliation result

- Deferred items classified: **16 / 16**.
- Items mechanically resolved by current implementation: **8**.
- Items intentionally outside initial v1: **5**.
- Trigger-based future decisions that fail closed today: **2**.
- Acceptance-blocked item: **1** (`60-minute task measurement`).
- Frozen Architecture/SPEC bytes changed by this review: **none**.
- Runtime/current-snapshot authority granted by this review: **none**.

The Chapter 4/5/6 architecture is therefore no longer ambiguous about which historical Deferred entries were consumed by implementation. The only Deferred item that remains part of the current product-acceptance denominator is the live fresh-medium ≤60-minute measurement; the remaining unresolved items are explicitly outside v1 or guarded by a future trigger.