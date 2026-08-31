# Adversarial architecture review — 2026-08-31 (r6)

Target: `ARCHITECTURE-SPINE.md` and its normative companions at the current
workspace revision. This pass re-checks whether the brownfield conformance
matrix and the latest V5/V6A ordering patch mechanically close H1–H8 and
M1–M4 from r5. The spine was not modified.

## Gate verdict

**BLOCKED.** The matrix and spine prose now describe the desired boundaries,
but the active implementation/schema contracts still leave the same authority,
lineage, snapshot, terminal, and path predicates optional or contradictory.
Two independently implemented adapters could still satisfy the published
documents while producing incompatible evidence. The architecture is not
safe for final handoff.

## High findings

### H1 — Q5/Q6 ownership remains contradictory

`implementation-contracts.md` Q5 and Q6 transition rows (the owner column)
still name **Quick Dev**, while AD-4/AD-6 and the matrix require Quick Dev to
dispatch only, the executor to write receipts, the independent judge to write
observations/classification, and the runtime-edge validator to write edges.
The companion therefore permits a combined Quick Dev writer or a self-judging
stage. The owner rows must use the exact split-writer ownership and explicitly
reject direct pytest/owner shortcuts as authoritative paths.

### H2 — Runtime edges do not authenticate receipt/observation bytes

The `runtime_assertion_edge` schema requires only generic `result_ref` and
`result_sha256`. It does not require independent receipt and observation
references/hashes, descriptor hash, target hash, or fixture hash. The matrix
cannot close this gap: an ID/path-only or copied observation remains
schema-valid. Add required refs/hashes and require the edge writer to re-read
and recompute each referenced byte, rejecting stale, path-only, or
self-referential edges.

### H3 — Runtime edges and observations lack deterministic failure identity

`runtime_assertion_edge` has no `failure_family` or `failure_id`; the
observation schema has `failure_family` but no `failure_id`. Consequently two
judges can emit schema-valid RED edges with different classifications, and Q3
cannot mechanically enforce equality with the VDD failure intent. Require
layered outcome/family/id (with the pass/not-applicable null rule) on runtime
edges and require deterministic derivation from the canonical taxonomy tuple.

### H4 — Current-snapshot resolver has no executable root-manifest contract

AD-11 names a resolver and broad roots, but no normative schema defines its
version, exact include/exclude root manifest, evidence-only exclusion,
plan-state transition exception, or Git-delta/snapshot comparison. The
transition tables also do not require a resolver call before publication.
Implementations can hash the whole worktree (invalidating evidence appends) or
production-only bytes (missing contract/validator changes) and both claim
“current”. Publish the versioned manifest and reject every post-candidate byte
change except the explicitly allowed plan-state transition.

### H5 — Terminal input is not bound to the frozen predicate and current bytes

`terminal_input` still contains selector/edge/profile/basic IDs only. Required
predicate hash, V6 partition-manifest hash, terminal descriptor hash,
evaluator identity/version, and current-snapshot hash are absent. A generic
selector or read-only predicate can therefore produce a pass-shaped terminal
result while satisfying the schema. Make all bindings required and force Q8 to
re-read every referenced byte immediately before terminal evidence/result write.

### H6 — Q8 lacks an exact per-Acceptance/per-stage runtime closure predicate

The prose says every Acceptance closes, but no companion predicate enumerates
the active Acceptance/assertion universe and requires exactly one current RED,
GREEN, and REFACTOR edge (and terminal edge where specified) for each tuple.
Duplicate rejection, stage/predicate consistency, and exclusion of plan-only
edges are not machine requirements. Set-membership can therefore mask missing
or duplicate evidence. Encode one-and-only-one closure and reject duplicates,
missing stages, false predicates, and plan-only edges.

### H7 — Write-set and planned-file semantics are not mechanically closed

The slice fields and matrix mention normalized paths, but no single canonical
repository-relative resolver, symlink/junction escape rule, or exact Git-delta
comparison is defined. `planned_new_files` is not an explicitly closed set
and Q4 is not required to compare exact additions/deletions/renames. An
implementation may accept arbitrary files under an allowed directory or an
outside-repository junction. Define the resolver and closed allow-list, then
reject every unlisted addition, deletion, rename, or escape.

### H8 — Memlog supersession is still not mechanically addressable

The memlog entries have no stable `AD-*` identity and the combined-writer
entry is not linked by an explicit `supersedes: AD-*` field. AD-16 in the
rendered spine cannot recover an identity that is absent from the source log.
A refresh can therefore resurrect the historical ownership rule. Append a
repository-owned decision with stable ID and explicit supersession, and make
render/validation reject contradictory live ownership decisions.

## Medium findings

### M1 — Invalidation classification owner is not versioned

AD-11 names a repository-owned resolver but does not identify a versioned path
classifier/change-impact matrix implementation or its unknown-path behavior.
Assign all classification to that versioned resolver; unknown paths must take
the stricter invalidation route.

### M2 — Detached judge/fixture bundle envelope remains incomplete

AD-10 does not define the minimum content-addressed envelope required by the
companion: source commit/tree, judge/oracle/fixture hashes, immutable path,
read-only-open result, and promotion-time revalidation. Keep ceremony
Deferred, but make this minimum envelope normative.

### M3 — Resolver invocation is not explicit on every lifecycle path

The generic Mermaid resolver node and broad prose do not create enforceable
read-only dependencies from Q0, Q4, Q7, Q8, recovery, and terminal
publication. Add explicit transition inputs/edges and require invocation plus
re-read on each path.

### M4 — Revalidation timing is still ambiguous

Some prose mentions a final current-byte check, but the lifecycle contract does
not state that Q7/Q8 and recovery re-read candidate/dependency bytes after
predecessor evidence is written and immediately before terminal publication.
Make that ordering a mandatory terminal-predicate step; any drift routes to
invalidation/repair.

## Additional consistency issue

AD-7 and AD-8 each contain duplicated `Rule` bullets with overlapping but
slightly different wording. Keep one canonical rule per decision; duplicate
normative text is an ambiguity vector for independent implementations.

## Legitimate Deferred items

Comparator/stdout normalization, judge retention/revocation, rollback probe,
semantic-change partial reuse, profile scope/cost matrix, numeric stop-loss,
concurrency/resource quotas, evidence cleanup, and non-Windows normalization
remain valid Deferred items only with their existing “before first use”
conditions. They do not justify bypassing H1–H8 or M1–M4.

## Recommendation

Do not mark the spine `final` or hand it to downstream Architecture consumers.
Amend the normative companions and memlog to close H1–H8 and M1–M4, remove
duplicate AD rules, re-distill the spine, and rerun lint plus the complete
Reviewer Gate against a new frozen revision.

