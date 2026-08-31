# Adversarial architecture review — 2026-08-31

Target: `ARCHITECTURE-SPINE.md` (frozen review revision)

Method: construct two independently implemented downstream units that both satisfy the written ADs, then identify whether they can produce incompatible trust, lineage, or completion behavior. This is a review only; the spine was not modified.

## Gate verdict

**BLOCKED.** The spine has a strong semantic direction and correctly captures the V5 → V6 → V6A → V7 ordering, staged coverage, selector reuse, write-set isolation, and NN+1 intent. It is not yet a convergent implementation substrate because receipt/observation/edge ownership and whole-plan terminal closure still admit materially different implementations. CAP-9 is also not safely implementable while judge/fixture independence remains only Deferred without a hard acceptance gate.

## Critical findings

### H1 — Receipt, observation, and runtime-edge writers are not uniquely assigned

**Evidence:** AD-4 says the executor performs the process and the independent judge/validator derives the receipt and observation. AD-6 says “executor/judge writes receipts and observations.” The diagram sends a receipt from Executor to Judge, then sends receipt plus runtime edges to Coverage gate. AD-8 says a runtime edge is “created” after execution but does not name its writer.

**Adversarial construction:**

* Unit A has the executor persist the receipt (timestamps, argv, stdout hashes) and the judge persist only observation. The coverage gate derives runtime edges from the observation.
* Unit B has the executor emit an in-memory process record; the judge persists a normalized receipt and observation, and the coverage gate writes runtime edges.

Both read the current ADs as compliant, but they produce different receipt identities, hash inputs, and authority boundaries. A producer can therefore choose which normalization is authoritative, defeating deterministic replay and making a copied or self-authored receipt indistinguishable from executor truth.

**Required architectural decision:** name exactly one receipt writer (the real executor), one observation/classification writer (the independent validator/judge), and one runtime-assertion-edge writer (the coverage/lineage validator, or the judge, but not both). State that consumers may validate but never rewrite these artifacts and that the edge writer may reference only immutable receipt/observation hashes.

### H2 — Terminal result versus terminal predicate definition is ambiguous

**Evidence:** AD-2 assigns VDD ownership of the terminal predicate; AD-6 assigns coverage gate ownership of “terminal”; AD-7 assigns coverage gate ownership of terminal result and evaluator. No rule explicitly distinguishes the immutable predicate definition from the evaluated terminal result or forbids a gate from changing the predicate it evaluates.

**Adversarial construction:**

* Unit A treats `terminal_predicate` as a VDD-authored selector string and lets Q8 evaluate it.
* Unit B treats it as a coverage-gate implementation callback and allows Q8 to compile a weaker predicate from observed evidence.

Both can satisfy “VDD writes terminal predicate” and “coverage gate writes terminal,” yet Unit B can omit a predecessor, Acceptance, or fixture while still emitting `implementation-complete`.

**Required architectural decision:** freeze a VDD-authored, content-addressed predicate specification as input; make coverage gate the sole evaluator/writer of an immutable terminal result; require Q8 to prove the evaluator identity and predicate hash match before writing completion.

### H3 — Whole-plan completion does not explicitly require every partitioned slice to close

**Evidence:** AD-7 requires every active Acceptance to have an admissible many-to-many path and says Q8 rereads every predecessor. It does not state that every V6 slice must have a valid RED→GREEN→REFACTOR→slice-ready result and terminal evidence before `implementation-complete`.

**Adversarial construction:**

* Unit A allows one slice whose edges cover all active Acceptances to satisfy exact cover and marks the plan complete while S2–S6 have no run roots.
* Unit B requires all partitioned slices to close, including per-slice terminal lineage, before the same result.

Both satisfy the current wording; they disagree on whether an unexecuted slice is acceptable. This is a direct false-green and recovery divergence.

**Required architectural decision:** bind Q8 completion to the V6 partition manifest: every emitted slice must have a valid slice-ready result, all required stage observations, and a terminal evidence reference in one current evidence snapshot; exact cover is necessary but not sufficient.

## High findings

### H4 — Frozen judge/fixture independence is deferred without an implementation gate

**Evidence:** AD-10 requires a frozen predecessor judge and detached fixtures, while Deferred states that the independence procedure is outside this spine and is decided only before self-hosted/toolchain acceptance.

**Adversarial construction:**

* Unit A accepts a maintainer-provided detached directory and records only a path.
* Unit B accepts a hash of fixtures generated by the candidate repository itself.

Both can claim “frozen fixtures,” but Unit B permits the candidate to define the oracle and therefore self-certify. CAP-9 and the NN+1 false-green guarantee are not enforceable until the acceptance gate requires independent origin, immutable hashes, and a judge that cannot import candidate evidence writers.

**Required architectural decision:** keep the procedure Deferred if desired, but make the boundary explicit: self-hosted profile and NN+1 promotion are blocked unless an external/maintainer evidence bundle proves independent origin, detached read-only bytes, judge identity, and fixture hashes.

### H5 — Failure-layer legality permits failed results without deterministic identity

**Evidence:** AD-5 lists legal `evidence_state`/`verification_outcome` pairs and says `failure_family`/`failure_id` classify a result, but only explicitly forbids them for `pass` and `not-applicable`. It does not require them for `fail`, nor require a non-null family when a failure ID is present.

**Adversarial construction:**

* Unit A emits `observed-run + fail` with `failure_family=null` and no `failure_id` for a non-zero process.
* Unit B emits the same result with `task-implementation-failure` and a deterministic ID.

Both are legal under the prose; downstream recovery and stop-loss can route them differently, and a failure can be retried without a stable fingerprint.

**Required architectural decision:** require `fail` and `blocked` observations that reached a process predicate to carry exactly one family and one deterministic failure ID (except explicitly enumerated integrity/timeout cases), and reject family/ID on pass/not-applicable.

### H6 — Invalidation authority is named conceptually, not as a single resolver

**Evidence:** AD-11 says reuse is selected “per oracle from an explicit change-impact graph,” but no owner or immutable graph artifact is named. It also says owner/compiler/validator/judge changes invalidate affected evidence without defining the exact dependency edges.

**Adversarial construction:**

* Unit A invalidates all slices whenever `implementation-contracts.md` changes.
* Unit B invalidates only observations whose selector or validator identity mentions the changed contract.

Both follow “affected evidence” yet yield different reuse and replay behavior. A stale green can survive in Unit B, while Unit A causes unnecessary RED reruns.

**Required architectural decision:** designate one repository-owned impact resolver and a versioned change-impact matrix/hash. Recovery and recommendation consumers must use that resolver, never recompute dependency reachability locally.

### H7 — Quick Dev may invent a descriptor selector not represented by VDD intent

**Evidence:** AD-3 says Quick Dev materializes descriptors from VDD intent, but no invariant requires a descriptor’s selector, target, fixture, assertions, cwd, or stage scope to equal the V6A slice contract and plan edge. AD-8 constrains RED/GREEN/REFACTOR identity reuse only after a selector exists.

**Adversarial construction:**

* Unit A compiles the exact VDD selector intent into `argv`.
* Unit B chooses a narrower test selector that still passes the same acceptance assertion and declares it “materialized from intent.”

The two units produce different RED coverage and may bypass an acceptance case. This is especially dangerous for shared selectors and many-to-many cover.

**Required architectural decision:** descriptor compilation must be a deterministic projection whose canonical identity is checked against V6A `selector_intents`, target/fixture refs, assertion IDs, cwd, and ordered stage scope; any mismatch is `repair-vdd`.

## Medium findings

### M1 — Recovered-run legality is internally tense

AD-5 allows `recovered-run` with `incomplete` or `blocked`, yet says a recovered run “must reference complete prior evidence.” A unit can interpret “complete prior evidence” as complete receipt only; another can require a complete slice-ready result. Define the minimum predecessor set and evidence-state transition for recovery.

### M2 — Terminal command identity and per-slice terminal evidence are under-specified

AD-8 intentionally excludes terminal from the RED/GREEN/REFACTOR selector-reuse rule, but AD-7 does not require terminal descriptors to reference the exact partition manifest and all slice-ready hashes. A terminal implementation can therefore run a generic repository test and still claim to validate the plan. Bind terminal descriptor inputs to the current plan hash, partition hash, slice-ready refs, active Acceptance universe, and predicate hash.

### M3 — Operational/environmental envelope is silent

The spine assumes `py -3` and pytest but does not decide environment reproducibility, process isolation limits, filesystem atomicity failure handling, or platform-specific cwd/path normalization. Two compliant executors can classify timeout, path, and encoding behavior differently. Add a compact Deferred item with the re-decision trigger before cross-platform execution is enabled.

### M4 — Artifact graph diagram omits the authoritative hash/snapshot resolver

The diagram shows evidence flow but not the component that recomputes current bytes, validates predecessor hashes, and rejects unrelated writes. Two implementations can place this check in Quick Dev or coverage gate and produce different acceptance behavior. Add the resolver as an explicit component and dependency edge.

## Deferred items that are safe only with explicit gates

The following may remain Deferred per SPEC, but each needs an explicit “cannot enter the affected lane until decided” rule to prevent local invention:

1. semantic validator boundary — gate semantic Acceptance and terminal on a deterministic predicate schema;
2. v1 compatibility projection — gate migration on a read-only adapter conformance test;
3. unexpected-green proof — gate RED materialization and require a regression/current-behavior proof artifact;
4. profile scope — gate profile publication on the fixed truth floor;
5. detached judge/fixture independence — gate CAP-9/self-hosted promotion as described in H4;
6. comparator/normalization, judge lifecycle, rollback probe, partial reuse, and stop-loss threshold — gate each corresponding feature and prohibit silent fallback to a local interpretation.

## What is already convergent

- V5 pre-slice semantic cover and V6A post-partition final plan cover are correctly separated; `stage_scope=[red,green,refactor,terminal]` prevents the previously observed terminal-only hole.
- Runtime assertion edges are correctly prohibited from VDD planning output and are bound to execution-time identities.
- RED/GREEN/REFACTOR selector identity, target, fixture, assertion, and cwd reuse is explicit.
- Write-set isolation, append-only artifacts, no glob/mtime/latest-success lineage, and NN+1 candidate-as-SUT intent are clear and materially reduce prior false-green routes.

## Recommended disposition

Resolve H1–H3 before implementation handoff. Resolve H4 as a hard acceptance gate before enabling CAP-9/self-hosted promotion. Resolve H5–H7 in the implementation contract or add narrowly scoped ADs before the first Quick Dev adapter is built. M1–M4 can be Deferred only after adding the explicit gates above.

