# Adversarial architecture review — 2026-08-31 (r4)

Target: `ARCHITECTURE-SPINE.md` at the frozen r4 review revision. The review constructs independently compliant implementations and checks whether the trust boundaries, artifact graph, lineage, lifecycle predicates, and handoff gates actually converge. The spine was not modified.

## Gate verdict

**BLOCKED.** AD-15 adds a useful brownfield conformance checklist, but it is only a gate statement; it does not make the companion contracts mechanically converge. The normative transition table still contradicts the sole-writer rules, runtime edges do not carry enough authenticated artifact identity, terminal and current-snapshot bindings remain incomplete, and path/memlog ownership semantics permit incompatible implementations. The rubric substance is strong, but the architecture is not safe for final handoff until the H findings below are closed in the spine and its normative companions.

## High findings

### H1 — Q3/Q5/Q6 owner rows contradict the sole-writer boundary

AD-4/AD-6 state that the executor alone writes process receipts and the independent judge/observation validator alone writes observations/classification; Quick Dev only orchestrates and appends lifecycle state. The normative Q3 row still names `executor + deterministic validator`, while Q5/Q6 rows name Quick Dev as owner for GREEN/REFACTOR receipts and observations (spine lines 467–470). Two compliant implementations can therefore let Quick Dev classify or persist semantic truth, reintroducing candidate-controlled evidence.

**Required disposition:** change every Q3–Q6 owner row to the exact split: executor is sole receipt writer; independent judge/observation validator is sole observation/classification writer; runtime-edge validator is sole edge writer; Quick Dev only dispatches and appends lifecycle state. Explicitly state that Q5/Q6 observations are judge-produced and that a validator may not write a process receipt.

### H2 — Runtime assertion edges do not authenticate receipt and observation bytes

AD-8 says edges bind receipt and observation hashes, but the runtime-edge schema in `schema-contracts.md` and `implementation-contracts.md` exposes only `result_ref`/`result_sha256` plus IDs. It omits immutable receipt reference/hash, observation reference/hash, and descriptor/target/fixture hash bindings. A mutable path or copied observation can satisfy the schema, and recovery/coverage cannot prove which bytes were judged.

**Required disposition:** require receipt and observation refs plus hashes, descriptor/target/fixture hashes, and a re-read/hash check by the edge writer. Consumers must reject ID-only or path-only edges; hashes are over external immutable artifacts and never self-reference.

### H3 — Failure-ID derivation is not part of the runtime-edge contract

AD-4/AD-5 describe deterministic `failure_id` generation, but runtime edges carry neither `failure_family` nor `failure_id`, nor a nullable/required rule for pass/not-applicable. A judge can classify identical evidence under different IDs while preserving edge identity; RED matching, stop-loss, and recovery then diverge.

**Required disposition:** add layered `verification_outcome`, `failure_family`, and nullable/required `failure_id` to every runtime edge. Bind them to a versioned taxonomy and canonical derivation tuple owned solely by the independent judge. Q3/Q8 must require exact equality with the VDD failure intent for expected-red.

### H4 — Candidate/current snapshot scope remains implementation-defined

AD-11 names a repository-owned resolver but does not define its canonical root manifest, excluded paths, or treatment of plan-state/evidence writes. AD-13 lists roots but is not a hashing contract. One implementation can hash the whole worktree and invalidate on every evidence append; another can hash only production files and miss contract/selector changes. Both can report “current hashes”.

**Required disposition:** name the resolver and versioned root manifest. Specify inclusion of production, tests, VDD/Quick Dev contracts, selectors, fixtures, validators, and plan state; exclude only run-local append-only evidence. Define exact Git-delta/snapshot comparison and plan-state transition handling. Require Q0, Q4, Q7, Q8, recovery, and terminal to call this resolver.

### H5 — Terminal selector is not mechanically bound to the frozen predicate

AD-7 requires predicate/partition/current-snapshot binding, but the terminal-input schema contains only `terminal_selector_ref`, assertion-edge refs, and profile identity. It omits predicate hash, V6 partition manifest hash, terminal descriptor hash, and validator identity/version. Q8 can therefore run a generic selector or a read-only predicate that emits a pass-shaped result without proving it is the declared terminal implementation.

**Required disposition:** require terminal selector and descriptor hashes, VDD predicate hash, V6 partition hash, evaluator identity/version, active Acceptance manifest, and current snapshot hash. Q8 must reject selectors not produced by the declared terminal validator and re-read all referenced bytes before writing terminal evidence.

### H6 — Per-Acceptance runtime closure is not a mechanical Q8 predicate

AD-7 says every active Acceptance passes, but Q8 only requires plan exact cover plus runtime assertion edges (line 472). It does not require one non-duplicated current RED/GREEN/REFACTOR (and terminal where applicable) runtime edge for every active Acceptance/assertion, all with `predicate_result=true`, nor reject duplicates or plan-only satisfaction. Duplicate plan edges can mask missing runtime evidence.

**Required disposition:** enumerate active Acceptance/assertion IDs; require exactly one current edge per required stage, with duplicate rejection and stage semantics consistent with the receipt/observation. Plan edges alone never satisfy Q8.

### H7 — Write-set and planned-file path semantics are open

AD-9 and companions mention `allowed_write_paths`, `execution_snapshot_paths`, and `planned_new_files` but do not define normalization, symlink/junction containment, or whether planned files are an exact allow-list. Implementations can accept arbitrary files beneath a directory or follow a junction outside the repository while reporting the same “confined” result.

**Required disposition:** use one repository-relative POSIX resolver; reject symlink/junction escapes; treat `planned_new_files` as a closed allow-list and `allowed_write_paths` as its normalized union. Q4 snapshots and compares exact additions, deletions, and renames; unlisted changes invalidate the successor.

### H8 — Memlog ownership correction is not explicitly superseding

The architecture memlog retains an earlier decision that Quick Dev uniquely writes RED/GREEN/REFACTOR receipts/observations, followed later by the split-writer decision. AD-14 says “latest non-superseded” wins, but no stable decision ID or explicit supersedes link marks the old entry. A memlog-derived render can therefore select the earlier rule and reintroduce the authority conflict.

**Required disposition:** append a repository-owned memlog decision with a stable ID explicitly superseding the old combined-writer entry, and require renderer/validator rejection of contradictory live ownership decisions.

## Medium findings

### M1 — Invalidation classification has no named deterministic owner

AD-11 distinguishes semantic and non-semantic changes without naming the path classifier or matrix version. Different adapters may classify a fixture helper or validator as documentation and reuse evidence differently.

**Disposition:** assign classification to the versioned repository-owned change-impact resolver; unknown paths take the stricter invalidation route.

### M2 — Detached judge/fixture bundle shape and revalidation timing are incomplete

AD-10 requires independent origin and hashes but does not fix a minimum bundle envelope, source tree/commit, read-only-open result, or promotion-time revalidation record. Two maintainers can supply incompatible bundles.

**Disposition:** require a minimum content-addressed envelope containing source commit/tree, judge/oracle/fixture hashes, immutable path, read-only-open result, and promotion revalidation; leave ceremony details Deferred.

### M3 — Resolver dependencies are not shown on every lifecycle path

The first Mermaid graph has a generic `RES` node, but the artifact graph and lifecycle sequencing do not show resolver edges to Q0, Q4, Q7, Q8, recovery, and terminal validation. Ownership can drift between Quick Dev, executor, and coverage gate.

**Disposition:** add a named read-only snapshot/change-impact resolver and explicit edges to each consumer.

### M4 — Terminal/current-byte revalidation timing is implicit

AD-7/AD-11 require current hashes, but the sequence does not state that Q7/Q8 and recovery re-read candidate bytes after predecessor evidence is written and immediately before terminal publication. Implementations may validate once, then accept unrelated writes.

**Disposition:** make pre-publication revalidation a mandatory terminal predicate step; any byte drift routes to invalidation/repair.

## AD-15 assessment

AD-15 names all seven broad gate themes (writer split, compatibility projection, edge integrity, descriptor seam, terminal closure, path containment, and resolver invocation), but each is phrased as a handoff assertion rather than a complete schema/transition predicate. Passing AD-15 therefore does not close H1–H8 unless the companion contracts and active validators expose and enforce the required fields and re-read checks. AD-15 cannot be treated as evidence that the implementation already conforms.

## Deferred items that remain legitimate

Comparator/stdout normalization, judge lifecycle/retention/revocation, rollback probe, semantic-change partial reuse, profile scope matrix, numeric stop-loss threshold, concurrency/resource quotas, evidence cleanup, and non-Windows normalization may remain Deferred only with their existing “before first use” triggers. They do not justify bypassing H1–H8 or M1–M4.

## Recommendation

Do not mark the spine final or hand it to Architecture consumers. Resolve H1–H8 before Q7/Q8/terminal implementation; resolve M1–M4 in the same revision where practical; append explicit supersession and resolver decisions to the architecture memlog, re-distill, then rerun lint and the complete Reviewer Gate against the new frozen revision.

