# Adversarial architecture review — 2026-08-31 (r5)

Target: `ARCHITECTURE-SPINE.md` and its normative companions at the frozen
workspace revision. This review specifically checks whether AD-15's explicit
brownfield conformance matrix closes the prior H1–H8 findings and whether two
independently compliant implementations are forced onto the same authority,
lineage, lifecycle, and terminal semantics. The spine was not modified.

## Gate verdict

**BLOCKED.** The spine now names the required seams and publishes a useful
conformance matrix, but several matrix rows are not represented by enforceable
fields or predicates in the normative contracts. A compliant implementation can
still choose incompatible receipt/observation ownership, runtime-edge identity,
snapshot scope, terminal binding, per-Acceptance closure, path containment, or
memlog supersession semantics. The architecture is therefore not safe for final
handoff until H1–H8 below are closed in the spine and companions.

## High findings

### H1 — Q5/Q6 owner contract still contradicts the split-writer rule

AD-4, AD-6, AD-15 and the matrix correctly state that the executor alone writes
receipts and the independent judge writes observations/classification. However,
the normative Q5 and Q6 transition rows in `implementation-contracts.md` still
list **Quick Dev** as the owner of GREEN/REFACTOR receipts and observations.
Two implementations can consequently let Quick Dev persist semantic truth or
route through a combined writer while both satisfy the spine text.

**Required disposition:** change Q3–Q6 owner rows to the exact split: Quick Dev
dispatches and appends lifecycle state only; executor writes process receipts;
independent judge/observation validator writes observations and classification;
runtime-edge validator writes edges. Explicitly reject any validator that writes
a process receipt and mark direct pytest/owner paths diagnostic-only.

### H2 — Runtime assertion edge schema does not authenticate receipt/observation bytes

The spine and AD-15 matrix require receipt hash, observation hash,
descriptor/target/fixture hashes and a re-read before admitting an edge. The
actual `runtime_assertion_edge` schema only requires `result_ref` and
`result_sha256`, plus IDs; it has no receipt reference/hash, observation
reference/hash, descriptor hash, target hashes, or fixture hashes. A path-only or
copied observation can therefore satisfy the published schema and still pass a
coverage implementation.

**Required disposition:** add immutable receipt and observation refs/hashes and
descriptor/target/fixture hashes as required fields; require the edge writer to
re-read and recompute every hash and reject ID-only, path-only, stale, or
self-referential edges.

### H3 — Failure identity is not carried by runtime edges

AD-4/AD-5 and the matrix require deterministic `failure_family` and `failure_id`
for process-derived failures, but the runtime-edge schema has neither field nor
nullable pass/not-applicable rule. Different judges can classify identical RED
evidence with different IDs while emitting schema-valid edges, so RED matching,
stop-loss, and recovery do not converge.

**Required disposition:** require layered `verification_outcome`, nullable
`failure_family`, and nullable/required `failure_id` on every runtime edge;
bind derivation to taxonomy version and the canonical tuple owned by the
independent judge; require exact equality with VDD failure intent for
`expected-red` at Q3 and Q8.

### H4 — Current-snapshot resolver remains under-specified

AD-11/AD-13/AD-14 name a repository-owned resolver and list broad roots, but no
normative companion defines its versioned root manifest, included production,
test, contract, selector, fixture, validator, judge and plan-state bytes, or the
sole excluded class of run-local evidence. Treatment of evidence-only writes and
the plan-state transition is not a hashing predicate. Implementations can hash
the whole worktree and invalidate on every evidence append, or hash only
production files and miss contract changes, while both report a “current” hash.

**Required disposition:** publish a versioned resolver/root-manifest contract,
including exact include/exclude sets and Git-delta/snapshot comparison. Permit
only the explicit plan-state transition after candidate capture; reject every
other post-candidate byte change. Require Q0, Q4, Q7, Q8, recovery and terminal
to invoke and re-read this resolver immediately before publication.

### H5 — Terminal selector is not mechanically bound to the frozen predicate

AD-7 and the matrix mention predicate hash, V6 partition hash, evaluator
identity, active Acceptance set and current snapshot. `terminal_input` in
`implementation-contracts.md` contains only selector ref, assertion-edge refs,
profile identity and basic IDs; it omits predicate hash, partition manifest
hash, terminal descriptor hash, evaluator identity/version and current snapshot
hash. A generic selector or read-only predicate can therefore emit a
pass-shaped terminal result.

**Required disposition:** make all those hashes/identities required terminal
input fields, require descriptor provenance from the declared terminal producer,
and force Q8 to re-read every referenced byte before terminal evidence is
written.

### H6 — Per-Acceptance runtime closure is not an exact Q8 predicate

AD-7 says every active Acceptance closes, but the Q8 contract does not require
exactly one current RED, GREEN and REFACTOR runtime edge per required
Acceptance/assertion, nor duplicate rejection and stage/predicate consistency.
Plan edges can consequently mask missing runtime evidence, or duplicate edges
can satisfy a set-membership check.

**Required disposition:** enumerate the active Acceptance/assertion universe;
require one and only one current edge for each required stage (and terminal where
specified), reject duplicates, require `predicate_result=true` with receipt and
observation semantics matching the stage, and ensure plan-only edges never
satisfy Q8.

### H7 — Write-set and planned-file semantics are not closed

AD-9/AD-15 mention normalized paths and containment, but the companion schema
does not define one repository-relative POSIX resolver, symlink/junction escape
rejection, or `planned_new_files` as an exact closed allow-list. The successor
validator is not required to compare exact additions, deletions and renames, so
an implementation may accept arbitrary files beneath an allowed directory or a
junction outside the repository.

**Required disposition:** define one canonical path resolver; reject symlink and
junction escapes; treat `planned_new_files` as a closed set and
`allowed_write_paths` as its normalized union; Q4 must compare exact Git-delta
additions/deletions/renames and invalidate every unlisted change.

### H8 — Memlog supersession still has no stable decision identity

The architecture memlog contains the earlier combined-writer decision and a
later line labelled “Superseding ownership decision”, but neither has a stable
decision ID or explicit `supersedes` link. AD-14's “latest non-superseded” rule
is therefore not mechanically resolvable by a renderer or validator; a
memlog-derived refresh can resurrect the old ownership rule.

**Required disposition:** append a repository-owned decision with a stable ID
that explicitly supersedes the old entry, and require render/validation to
reject contradictory live ownership decisions before deriving the spine.

## Medium findings

### M1 — Invalidation classification has no named deterministic owner

AD-11 distinguishes semantic from non-semantic changes but does not name a
versioned path classifier/matrix implementation. Different adapters can classify
fixture helpers or validators differently and reuse incompatible evidence.

**Disposition:** assign all classification to the versioned repository-owned
change-impact resolver; unknown paths take the stricter invalidation route.

### M2 — Detached judge/fixture bundle envelope is incomplete

AD-10 requires independent origin and hashes but does not require a minimum
content-addressed bundle containing source commit/tree, judge/oracle/fixture
hashes, immutable path, read-only-open result and promotion-time revalidation.

**Disposition:** fix that minimum envelope in the companion contract; leave only
ceremony details Deferred.

### M3 — Resolver invocation is not visible on every lifecycle path

The Mermaid graph has a generic resolver node, while the artifact graph and
transition table do not show explicit resolver edges to Q0, Q4, Q7, Q8,
recovery and terminal publication. Ownership can drift between Quick Dev and
the coverage gate.

**Disposition:** name the resolver and show explicit read-only dependencies on
each listed lifecycle path.

### M4 — Terminal/current-byte revalidation timing is implicit

The spine requires current hashes but does not state in the lifecycle sequence
that Q7/Q8 and recovery re-read candidate bytes after predecessor evidence is
written and immediately before terminal publication. A post-validation unrelated
write can therefore be accepted.

**Disposition:** make pre-publication revalidation a mandatory terminal-predicate
step; any byte drift routes to invalidation/repair.

## Matrix assessment

AD-15 is a useful handoff checklist, but it is not itself evidence of
conformance. Rows 177–182 name the desired checks; the required fields and
cross-field predicates above are missing or contradictory in the active
companions. Until the schema and transitions mechanically encode those rows,
the matrix does not close H1–H8 and does not prevent incompatible compliant
implementations.

## Legitimate Deferred items

Comparator/stdout normalization, judge lifecycle/retention/revocation, rollback
probe, semantic-change partial reuse, profile scope matrix, numeric stop-loss,
concurrency/resource quotas, evidence cleanup and non-Windows normalization may
remain Deferred only with their existing “before first use” triggers. They do
not justify bypassing the high findings above.

## Recommendation

Do not mark the architecture final or hand it to downstream Architecture
consumers. Amend the spine companions and memlog to close H1–H8 (and M1–M4),
re-distill the spine, then rerun lint and the complete Reviewer Gate against a
new frozen revision.

