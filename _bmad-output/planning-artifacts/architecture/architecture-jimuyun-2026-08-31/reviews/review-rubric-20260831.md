# Architecture Spine Rubric Review — 2026-08-31

Target: `ARCHITECTURE-SPINE.md` (feature-altitude build substrate)

## Verdict

**Needs revision before finalization.** The spine covers the SPEC capabilities and the central VDD/Quick Dev invariants, but two boundary ambiguities and one silent architecture dimension could let independent implementers diverge. No contradiction with CAP-1…CAP-10 was found.

## Critical / high findings

### H1 — Receipt and observation authority are still conflated

AD-4 says the “independent judge/validator derives receipt, observation…” while AD-6 says “executor/judge writes receipts and observations.” This leaves open whether one implementation may execute the process and also author the receipt and observation, which weakens the independent-judge boundary required by CAP-9 and AD-10. The first Mermaid graph also labels a combined `Executor` → `Independent judge / observation validator` path without assigning sole writers.

**Disposition:** Amend AD-4/AD-6 and the trust-boundary diagram to make the write split explicit: executor is the sole writer of process receipts; independent judge/validator is the sole writer of observations and runtime assertion edges; the judge must consume an immutable receipt and cannot execute the SUT in the same authority. Coverage gate remains sole writer of coverage and completion predicates.

### H2 — Operational and environmental envelope is silent

The spine has no decision or Deferred entry for deployment/execution environments, process isolation/resource limits, filesystem sandbox enforcement, concurrency/locking, evidence retention, or recovery across the Windows/temporary-workspace envelope. `Stack` contains only `[ASSUMPTION]` entries and the structural seed lists directories. At this altitude those omissions allow incompatible choices around cwd containment, timeout enforcement, run concurrency, and append-only evidence durability—the same areas that determine whether the truth-floor and 60-minute signal are implementable.

**Disposition:** Add explicit architecture decisions or separate Deferred rows for (a) supported execution environments and isolation/resource policy, (b) artifact persistence/retention and atomic-write/concurrency policy, and (c) operational recovery/cleanup. Each Deferred row needs a concrete re-decision trigger (before executor deployment, evidence store, or concurrent-run support). Do not invent provider choices; record `[ASSUMPTION]` where the brownfield code has not settled them.

### H3 — NN+1 independence procedure is deferred without a minimum enforceable seam

AD-10 correctly freezes predecessor judge and fixtures for self-hosted/toolchain acceptance, but the actual detached-directory/commit/read-only verification procedure is entirely Deferred. Until that procedure is fixed, two teams can satisfy the words “frozen” with different provenance and isolation guarantees, so the NN+1 promotion gate is not yet mechanically convergent.

**Disposition:** Keep the detailed maintainer procedure Deferred if it is outside this spine, but bind a minimum invariant now: predecessor judge, fixtures, and oracle must be content-addressed, detached from the candidate tree, opened read-only, and their hashes must be revalidated at promotion. Add the exact re-decision trigger before self-hosted/toolchain acceptance is enabled.

## Medium findings

### M1 — Deferred row combines unrelated decisions

The final Deferred row groups comparator/normalization, judge lifecycle, rollback probe, numeric stop-loss threshold, and semantic-change partial reuse. These have different owners and different enabling events; combining them makes a partial implementation appear resolved and permits silent defaults.

**Disposition:** Split into one row per decision (or at least per owner/feature) with an individual re-decision condition. Preserve the current “no silent guessing” stance.

### M2 — Brownfield ratification and technology currency are only asserted

The spine labels `py -3` and pytest as assumptions but does not cite the existing executable entry points or a verification result. The repository currently contains historical/snapshot Quick Dev paths rather than a single obvious `scripts/vdd`/`scripts/quick_dev` implementation root. A future builder could therefore bind to a different launcher or version while still claiming conformance.

**Disposition:** Keep the paths as structural seed, but add a short brownfield convention (or Deferred row) requiring the implementation to discover and record the repository-owned launcher and interpreter/test-runner versions before V0/Q1. Do not pin a version that the codebase has not established.

## Checklist results

- Paradigm named and coherent: **pass** (hexagonal evidence pipeline; append-only authority).
- Divergence points for VDD, Quick Dev, executor/judge, SUT, coverage gate, and coordinator: **mostly pass**; H1 requires explicit receipt/observation writer split.
- Every AD has Binds/Prevents/Rule and is enforceable: **pass with H1/H3 seam clarification**.
- SPEC CAP-1…CAP-10 represented: **pass**.
- Layered result legality, NN+1 freeze, reuse/invalidation, and implementation-complete gate: **pass** at invariant level.
- Diagrams convey trust and lifecycle structure: **pass with H1 update**.
- Named technologies verified current: **deferred/assumption** (M2).
- Brownfield conventions ratified: **partial** (M2).
- Operational/environmental envelope decided, deferred, or explicitly open: **fail** (H2).
- Deferred set gives non-silent re-decision conditions: **partial** (H3 and M1).

## Recommended gate outcome

Apply H1–H3 before setting `status: final`; M1–M2 can be handled in the same revision or explicitly recorded as Deferred. Re-run the full Reviewer Gate against the revised spine.

