# Adversarial architecture review — 2026-08-31 (r2)

Target: `ARCHITECTURE-SPINE.md` (frozen review revision)

Method: construct independently implemented VDD, Quick Dev, executor/judge, and coverage-gate units that satisfy the written ADs, then look for incompatible authority, lineage, selector, and terminal behavior. This review does not modify the spine.

## Gate verdict

**BLOCKED.** The revised spine fixes the previous V5/V6 ordering, explicit writer roles, selector reuse, exact-cover stage scope, and whole-plan predecessor intent. Several machine-level seams remain under-specified enough for two compliant implementations to disagree on whether evidence is authentic or a plan is complete. The highest risk is that process/observation owners and failure IDs are still inconsistent between the ADs and the Q-transition contract; candidate hashing and terminal selector binding also leave stale or generic evidence paths possible.

## Critical findings

### H1 — Q3/Q5 transition owners still contradict the sole-writer boundary

**Evidence:** AD-4 assigns the executor sole process-receipt writing and the independent judge/observation validator sole observation/classification writing. AD-6 names separate writers. However the Q3 row names `executor + deterministic validator` as owner and the Q5/Q6 rows name `Quick Dev` as owner for GREEN/REFACTOR receipts and observations (implementation-contracts.md §Quick Dev matrix). AD-3 also says Quick Dev never writes receipt outcome.

**Adversarial construction:** Unit A lets the executor persist a raw receipt and the deterministic stage validator persist the observation; Unit B lets Quick Dev persist a GREEN observation after seeing a zero exit while the judge only validates it. Both can claim to follow the matrix, yet Unit B permits candidate-controlled semantic truth and Unit A permits a non-independent validator to classify failures. The same run can therefore be promoted with different evidence authority.

**Required disposition:** make the transition matrix owners match AD-4/AD-6 exactly: executor is the only receipt writer; independent judge/observation validator is the only observation and failure-classification writer for every stage; runtime-edge validator is the only runtime-edge writer. Quick Dev may orchestrate and append lifecycle state only. State that all Q5/Q6 observations are judge-produced, not Quick Dev-produced.

### H2 — Runtime edges do not bind receipt/observation bytes or failure identity

**Evidence:** AD-8 requires `observation_id` and `result_ref/result_sha256`, but does not require immutable receipt and observation hashes, descriptor hash, or `failure_family/failure_id` in each `runtime_assertion_edge`. The normative edge schema has the same omission.

**Adversarial construction:** Unit A points an edge at an observation ID while resolving a mutable receipt by path; Unit B points at a copied result artifact with the same observation ID. Both satisfy the current fields. A third implementation can classify the same non-zero process with a different failure ID while retaining the same edge, so exact cover and recovery cannot distinguish the runs.

**Required disposition:** require receipt reference/hash, observation reference/hash, descriptor/target/fixture hash bindings, and the layered `verification_outcome`, `failure_family`, and `failure_id` (or an explicit `failure_id: null` rule for pass/not-applicable) in every runtime edge. The edge writer must re-read and hash those immutable artifacts before publication; consumers must reject path-only or ID-only edges.

### H3 — Failure-ID generation is called deterministic but has no canonical algorithm or owner

**Evidence:** AD-5/AD-8 and the implementation contracts require an “exact” or deterministic failure ID, while the fingerprint algorithm names selector, stage, family, and output summary but not the failure ID. No AD states the canonical input tuple, namespace/version, or sole writer for failure IDs.

**Adversarial construction:** Unit A maps a missing field to `VDD-SEMANTIC-MANIFEST-INCOMPLETE`; Unit B maps the same observation to `VDD-SEMANTIC-TAXONOMY-INCOMPLETE`, both with family `semantic-contract-gap`. RED matching, stop-loss fingerprints, recovery routing, and external review bindings then disagree despite identical process evidence.

**Required disposition:** define one versioned failure-ID derivation/registry owned by the independent observation validator, including the normalized input tuple and expected-red matching rule. Include the ID in the fingerprint (or hash a canonical classification object containing it) and require exact equality with the VDD failure intent at Q3/Q8.

### H4 — Candidate hash/current-snapshot scope is not fixed, so invalidation and reuse can diverge

**Evidence:** AD-7/AD-8 require current candidate hashes and AD-11 allows ordinary non-semantic documentation to reuse identity-valid observations, but no rule defines which repository bytes constitute `candidate_hash`, whether run logs/evidence are excluded, or how a post-run plan-state/evidence write is treated.

**Adversarial construction:** Unit A hashes the whole worktree and invalidates every observation after an evidence append; Unit B hashes only production roots and reuses a GREEN after an unrelated test/contract file changed. Both can claim “current hashes” and “ordinary non-semantic docs may reuse,” yet produce opposite route decisions and permit unrelated writes to escape closure.

**Required disposition:** name a repository-owned candidate/snapshot resolver and canonical root manifest. Specify excluded run-local/evidence paths, inclusion of plan/contract/selector/fixture/validator bytes, treatment of plan-state transitions, and the exact delta/invalidation operation. All Q4–Q8 consumers must call this resolver rather than compute local hashes.

## High findings

### H5 — Terminal selector is not proven to be the VDD terminal predicate

**Evidence:** AD-7 freezes a VDD-authored `terminal_predicate`, while Q8 accepts a `terminal_selector_ref`; AD-8's exact selector projection rule covers RED/GREEN/REFACTOR but explicitly leaves terminal outside selector reuse. No rule requires the terminal selector descriptor to resolve to the frozen predicate implementation and current validator identity.

**Adversarial construction:** Unit A runs the frozen terminal validator; Unit B runs a generic repository test that emits a pass-shaped result and then invokes a read-only predicate. Both satisfy “terminal input + terminal predicate” unless the selector-to-predicate relation is checked. B can omit active Acceptance or mutation evidence while still producing `implementation-complete`.

**Required disposition:** bind `terminal_selector_ref` to the V6A predicate specification hash, terminal descriptor hash, validator identity/version, active Acceptance universe, and partition manifest. Q8 must reject a selector that is not the declared predicate entry or whose terminal observation is not produced by that validator.

### H6 — Q7/Q8 completion does not make per-acceptance runtime classification a mechanical requirement

**Evidence:** AD-7 prose says every active Acceptance must pass, but the Q8 transition row only states “plan coverage exact cover plus runtime assertion edges” and does not require one valid RED/GREEN/REFACTOR edge for every Acceptance and every required assertion, nor explicit pass classifications for each edge.

**Adversarial construction:** Unit A emits seven Acceptance edges with all required stage observations. Unit B emits one runtime edge for A-SEMANTIC and a plan-only edge for the remaining Acceptances, then reports exact cover through duplicated plan edges. Both can satisfy the abbreviated Q8 predicate unless per-A runtime closure is mandatory.

**Required disposition:** state the per-A closure predicate: for each active Acceptance and assertion, exactly one current edge per required stage (including terminal where applicable), each edge resolves to immutable receipt/observation bytes with `predicate_result=true`, and no edge may be satisfied solely by a plan edge. Q8 should enumerate and reject missing/duplicate/mismatched assertion edges before recomputing cover.

### H7 — Q4 write-set isolation leaves path semantics and planned-file precedence open

**Evidence:** AD-9 says changed paths must be confined to the production write set and selector/fixture/contract/evidence paths are immutable; implementation contracts separately expose `allowed_write_paths`, `execution_snapshot_paths`, and `planned_new_files`, but the spine does not define whether planned files are subsets, exact additions, or how path normalization and symlink/junction escapes are handled.

**Adversarial construction:** Unit A treats an allowed directory as recursive and permits any new file; Unit B permits only the enumerated planned files; Unit C resolves a junction outside the repository before checking the path. All report “within production write set” while accepting different successor trees.

**Required disposition:** bind one path resolver and comparison rule: repository-relative POSIX normalized paths, no symlink/junction escape, `planned_new_files` as an explicit allow-list, and `allowed_write_paths` as a closed set after expansion. Q4 must snapshot and compare the exact union and reject any unlisted creation, deletion, or rename.

### H8 — Canonical memlog still contains an unsuperseded-looking ownership rule

**Evidence:** The architecture memlog line 10 states that Quick Dev is the unique writer of RED/GREEN/REFACTOR receipts and observations, while later lines amend the split-writer rule. The spine does not identify the superseding entry or require downstream readers to apply a last-decision-wins rule when loading the memlog.

**Adversarial construction:** Unit A derives from the rendered spine and uses the AD-4 split. Unit B resumes from the memlog and follows the earlier Quick Dev-owns-observations entry, treating the later note as an implementation detail. Both can claim they consumed the canonical source and produce incompatible authority boundaries.

**Required disposition:** mark the old decision explicitly superseded (with a stable decision ID and superseding reference) or compact the render pipeline so only the latest live ownership rule is exposed to consumers. Add a consistency check that rejects contradictory live ownership decisions before reviewer handoff.

## Medium findings

### M1 — Invalidation classification is not independently owned

AD-11 distinguishes semantic from non-semantic documentation changes, but does not name who classifies a changed path or how that classification is versioned. A local Quick Dev implementation can mark a changed fixture helper as documentation and reuse GREEN, while another invalidates from RED. Route decisions are therefore not convergent.

**Disposition:** assign classification to the repository-owned change-impact resolver with a versioned matrix/hash; unknown paths must take the stricter invalidation route.

### M2 — Deferred list contains a duplicate `unexpected-green proof` decision

The Deferred table lists `unexpected-green proof` twice (rows 207 and 214) with near-identical triggers. Future updates can resolve one row and leave the other open, yielding contradictory gate behavior.

**Disposition:** keep one uniquely identified row (or split by owner) and give it a single decision gate before RED materialization.

### M3 — Detached judge/fixture independence remains deferred without binding the provenance artifact shape

AD-10 supplies a minimum gate, but the Deferred row leaves the evidence-bundle schema and revalidation timing open. Two maintainers can provide different detached bundle envelopes while both claim independent origin.

**Disposition:** retain the detailed ceremony as Deferred, but fix a minimum envelope now: immutable bundle path, source commit/tree hash, judge/oracle/fixture hashes, read-only open result, and promotion-time revalidation record. Block self-hosted promotion when any field is absent.

### M4 — Stage matrix and diagrams do not show the invalidation resolver or hash snapshot authority

The diagrams show artifact flow but omit the component that computes current candidate bytes, applies the change-impact matrix, and rejects unrelated writes. This allows that authority to be placed in Quick Dev, the executor, or the coverage gate with different semantics.

**Disposition:** add a named snapshot/invalidation resolver node and edges to Q0, Q4, Q7, Q8, recovery, and terminal validation; keep it read-only and repository-owned.

## Deferred gates that must remain explicit

The following can stay Deferred only with the affected-lane gate stated in the spine: comparator/stdout normalization before cross-platform fixtures; judge lifecycle/retention/revocation before multiple predecessor judges; rollback probe before recovery-class oracles; semantic-change partial reuse before any such reuse; profile scope before profile publication; numeric stop-loss threshold before profile retry policy; concurrency/resource quotas before concurrent runs; evidence retention/cleanup before automated cleanup; and cross-platform normalization before a non-Windows executor. The semantic validator boundary and unexpected-green proof must gate semantic RED and terminal acceptance, not be silently selected by Quick Dev.

## What is already convergent

- V5 pre-slice cover, V6 partition, V6A final plan cover, and V7 feasibility are acyclic.
- Final `stage_scope=["red","green","refactor","terminal"]` is unique and ordered.
- RED/GREEN/REFACTOR selector, target, fixture, assertion, and cwd reuse is explicit.
- Trust-zone separation, append-only writes, run-local predecessor references, no glob/mtime selection, exact many-to-many cover, and NN+1 frozen-judge intent are materially stronger than the prior revision.

## Recommended disposition

Resolve H1–H4 before handoff. Resolve H5–H7 before implementing Q7/Q8 or enabling terminal/promotion. M1–M4 may remain Deferred only after their named owners and gates are recorded. Re-run the complete Reviewer Gate against the amended revision.
