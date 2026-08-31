# Adversarial architecture review — 2026-08-31 (r3)

Target: `ARCHITECTURE-SPINE.md` at the frozen review revision.  This review constructs independently compliant implementations and checks whether ownership, lineage, snapshot, terminal, selector, and write-set rules converge.  The spine was not modified.

## Gate verdict

**BLOCKED.** The spine is materially stronger than r2 (V5/V6A ordering, full stage scope, explicit artifact writers, selector reuse, and NN+1 intent are present), but the architecture and its normative companions still permit incompatible implementations at the machine seams.  In particular, the companion transition matrix contradicts the writer boundary; runtime edges cannot be independently authenticated from the declared schema; terminal and snapshot bindings are incomplete; and path/invalidation semantics are not closed.

## High findings

### H1 — Q3/Q5/Q6 owner rows contradict the sole-writer boundary

AD-4/AD-6 state that the executor alone writes process receipts and the independent judge/observation validator alone writes observations/classification; Quick Dev only orchestrates and writes descriptors/run state.  The normative `implementation-contracts.md` Q3 row still names `executor + deterministic validator`, while Q5/Q6 rows name `Quick Dev` as owner for GREEN/REFACTOR receipts and observations.  Two implementations can therefore let Quick Dev classify a zero exit or let a stage validator persist an observation, changing the trust boundary and allowing candidate-controlled semantic truth.

**Required disposition:** change every Q3–Q6 owner row to the exact split: executor is sole receipt writer; independent judge/observation validator is sole observation/classification writer; runtime-edge validator is sole edge writer; Quick Dev only dispatches and appends lifecycle state.  Explicitly state that Q5/Q6 observations are judge-produced.

### H2 — Runtime assertion edges do not authenticate receipt/observation bytes

AD-8 says edges bind receipt and observation hashes, but `runtime_assertion_edge` in `schema-contracts.md`/`implementation-contracts.md` exposes only `result_ref`/`result_sha256` plus IDs.  It has no immutable receipt reference/hash, observation reference/hash, or descriptor/target/fixture hash bindings.  A mutable path or copied observation can satisfy the current schema, and recovery/coverage cannot distinguish the bytes that were actually judged.

**Required disposition:** require receipt and observation refs+hashes, descriptor/target/fixture hashes, and a re-read/hash check by the edge writer.  Consumers must reject ID-only or path-only edges; hashes must be computed over external immutable artifacts without self-reference.

### H3 — Failure-ID derivation is still not part of the runtime edge contract

AD-4/AD-5 describe deterministic `failure_id` generation, but the runtime edge schema carries neither `failure_family` nor `failure_id` (nor a nullable rule for pass/not-applicable).  A judge can classify identical evidence under different IDs while preserving the same edge identity; RED matching, stop-loss and recovery then diverge.

**Required disposition:** add layered `verification_outcome`, `failure_family`, and nullable/required `failure_id` fields to every runtime edge.  Bind them to a versioned taxonomy and canonical derivation tuple owned solely by the independent judge; Q3/Q8 require exact equality with the VDD failure intent when expected-red.

### H4 — Candidate/current snapshot scope remains implementation-defined

AD-11 names a repository-owned resolver but does not define its canonical root manifest, excluded paths, or treatment of plan-state/evidence writes.  AD-13 lists roots but is not a hashing contract.  One implementation may hash the whole worktree and invalidate on every evidence append; another may hash only production files and miss contract/selector changes.  Both can claim “current hashes”.

**Required disposition:** name the resolver and its versioned root manifest.  Specify inclusion of production, tests, VDD/Quick Dev contracts, selectors, fixtures, validators and plan state; exclude only run-local append-only evidence as defined.  Define exact Git-delta/snapshot comparison and plan-state transition handling.  All Q0/Q4/Q7/Q8/recovery/terminal consumers must call this resolver.

### H5 — Terminal selector is not mechanically bound to the frozen predicate

AD-7 requires predicate/partition/current-snapshot binding, but `terminal_input` contains only `terminal_selector_ref`, `assertion_edge_refs` and `profile_identity`; it omits predicate hash, V6 partition manifest hash, terminal descriptor hash and validator identity/version.  Q8 can therefore run a generic selector or read-only predicate that emits a pass-shaped result without proving it is the declared terminal implementation.

**Required disposition:** require terminal selector + descriptor hashes, VDD predicate hash, V6 partition hash, evaluator identity/version, active Acceptance manifest and current snapshot hash.  Q8 must reject any selector not produced by the declared terminal validator and re-read all referenced bytes before writing terminal evidence.

### H6 — Per-Acceptance runtime closure is not a mechanical Q8 predicate

AD-7 prose says every active Acceptance passes, but Q8 only says “plan coverage exact cover plus runtime assertion edges”.  It does not require exactly one current RED/GREEN/REFACTOR (and terminal where applicable) runtime edge for every active Acceptance/assertion, with `predicate_result=true`, nor reject duplicates or plan-only satisfaction.  Duplicate plan edges can mask missing runtime evidence.

**Required disposition:** define and enforce per-A closure: enumerate active Acceptance/assertion IDs; require one non-duplicated edge for each required stage, all resolving to immutable receipt/observation hashes with pass/fail semantics consistent with the stage; plan edges alone never satisfy Q8.

### H7 — Write-set and planned-file path semantics are open

AD-9 and companions mention `allowed_write_paths`, `execution_snapshot_paths`, and `planned_new_files` but do not define normalization, symlink/junction containment, or whether planned files are an exact allow-list.  Implementations can accept arbitrary files under a directory, or follow a junction outside the repository, while reporting the same “confined” result.

**Required disposition:** use one repository-relative POSIX path resolver; reject symlink/junction escapes; treat `planned_new_files` as an explicit closed allow-list and `allowed_write_paths` as its normalized union.  Q4 snapshots and compares exact additions, deletions and renames; unlisted changes invalidate the successor.

### H8 — Memlog ownership correction is not explicitly superseding

The architecture `.memlog.md` retains an earlier decision that Quick Dev uniquely writes RED/GREEN/REFACTOR receipts/observations, followed later by the split-writer decision.  Although AD-14 informally says the latest non-superseded rule wins, no stable decision ID or explicit supersedes link marks the old entry.  A future memlog-derived render can select the earlier rule and reintroduce the authority conflict.

**Required disposition:** append a repository-owned memlog decision with a stable ID explicitly superseding the old combined-writer entry, and require the renderer/validator to reject contradictory live ownership decisions.

## Medium findings

### M1 — Invalidation classification has no named deterministic owner

AD-11 distinguishes semantic and non-semantic changes without defining the path classifier or matrix version.  Different adapters may classify a fixture helper or validator as documentation and reuse evidence differently.

**Disposition:** assign classification to the versioned repository-owned change-impact resolver; unknown paths take the stricter invalidation route.

### M2 — Detached judge/fixture bundle shape and revalidation timing are incomplete

AD-10 requires independent origin and hashes but does not fix the minimum bundle envelope, source tree/commit, read-only-open result, or promotion-time revalidation record.  Two maintainers can supply incompatible bundles.

**Disposition:** require a minimum content-addressed bundle envelope (source commit/tree, judge/oracle/fixture hashes, immutable path, read-only-open result and promotion revalidation) before self-hosted promotion; leave ceremony details Deferred.

### M3 — Invalidation/snapshot resolver is only partially represented in diagrams

The first Mermaid diagram has a generic `RES` node, but the artifact graph and lifecycle diagram do not show resolver edges to Q0, Q4, Q7, Q8, recovery and terminal validation.  Ownership can drift between Quick Dev, executor and coverage gate.

**Disposition:** add a named read-only snapshot/change-impact resolver node and explicit edges to every consumer.

### M4 — Terminal and successor current-byte revalidation timing is implicit

AD-7/AD-11 require current hashes, but the sequence does not state that Q7/Q8 and recovery re-read the candidate tree after predecessor evidence is written and immediately before terminal publication.  Implementations may validate once and then accept unrelated writes.

**Disposition:** make pre-publication revalidation a mandatory terminal predicate step; any byte drift routes to invalidation/repair.

## Deferred gates that remain legitimate

Comparator/stdout normalization, judge lifecycle/retention/revocation, rollback probe, semantic-change partial reuse, profile scope matrix, numeric stop-loss threshold, concurrency/resource quotas, evidence cleanup, and non-Windows normalization may remain Deferred only with their existing “before first use” triggers.  They must not be used to justify bypassing the H1–H8 or M1–M4 closure requirements.

## Recommended disposition

Do not mark the spine final or hand it to Architecture consumers.  Resolve H1–H8 before implementation of Q7/Q8/terminal; resolve M1–M4 in the same revision where practical; append all decisions to the architecture memlog, re-distill, then rerun lint and the complete Reviewer Gate against the new frozen revision.
