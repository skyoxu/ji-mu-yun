# Adversarial architecture review — 2026-08-31 (r8)

Target: `ARCHITECTURE-SPINE.md` and the current normative companions
(`execution-protocol.md`, `schema-contracts.md`, `implementation-contracts.md`,
and `success-metrics.md`). The spine was not modified. This pass attempts
independently compliant implementations of the receipt/evidence writers,
current-byte resolver, lifecycle dispatcher, and detached promotion bundle.

## Gate verdict

**BLOCKED.** The spine now states the intended V5/V6A ordering, split artifact
ownership, runtime-edge lineage, terminal closure, resolver roots, and detached
bundle requirements. However, the normative machine contracts still contain
an ownership contradiction and leave several of those invariants as prose-only.
Two implementations can therefore pass the published JSON-like schemas while
producing incompatible receipts, path snapshots, or recovery authority.

## High findings

### H1 — Process receipt schema still assigns judge-owned fields to the executor

`implementation-contracts.md` Process receipt requires
`observed_assertion_ids` and `observed_failure_ids` (lines 257–279). AD-4 and
AD-6 state that the executor writes only the process receipt and that the
independent judge writes observations/classification and derives failure
identity. A compliant executor cannot populate those fields before the judge
has run, while a compliant judge cannot update an append-only receipt. One
implementation may leave them empty and another may let the executor infer
assertions from output; both satisfy the current shape but disagree on truth
ownership. Remove judge-derived fields from the receipt (or make them an
explicitly immutable process-only projection) and require assertion/failure
IDs only on the observation/runtime-edge side.

### H2 — Current-snapshot root manifest has no machine-readable schema

AD-17 and `schema-contracts.md` name `current-snapshot-resolver.v1` and list
the nine roots, but no schema fixes the manifest object, per-root path/hash
representation, version field, Git-delta record, or plan-state transition
exception. An implementation can hash a whole directory, another can hash
only production files, and both can claim the same resolver contract. The
unknown-path and exact add/delete/rename rules are also prose-only. Publish a
single typed root-manifest/delta schema with closed properties and explicit
classification (`invalidate` versus `reuse`), then require every lifecycle
consumer to validate that object.

### H3 — Memlog supersession remains non-recoverable

AD-16 requires every decision to carry a stable `AD-*` identity and explicit
`supersedes`. The architecture `.memlog.md` entries are still un-IDed prose;
the ownership correction mentions `supersedes: AD-6` and `supersedes: AD-15` but
does not assign an ID to the new decisions. A renderer/resumer cannot prove
which entry is current or reject two contradictory live ownership entries.
Add stable decision IDs to the memlog entries (including the superseding
decisions) and make recovery fail closed on duplicate live topic authority.

### H4 — Write-set and path containment remain schema-ambiguous

`Slice contract` fields `allowed_write_paths`, `execution_snapshot_paths`, and
`planned_new_files` are only arrays of strings. AD-17's repository-relative
POSIX normalization, symlink/junction escape rejection, and closed-set Git
delta are not represented in the schema or a shared path-manifest object. Two
implementations can consequently accept different paths under an allowed
directory or differ on a rename/junction. Define the canonical normalized path
entry and closed delta result, including rejection of absolute, `..`, symlink,
junction, and unlisted additions/deletions/renames.

## Medium findings

### M1 — Detached judge/fixture bundle is prose-only

AD-18 and `schema-contracts.md` require `detached-judge-bundle.v1`, source
commit/tree, per-artifact hashes, read-only-open verification and promotion
revalidation, but no typed envelope is specified. Implementations can omit
read-only mode, place the bundle inside the candidate tree, or bind a different
source root while remaining schema-valid elsewhere. Add a closed bundle schema
and make the promotion predicate consume exactly that envelope.

### M2 — Resolver invocation is not explicit in the transition rows

AD-17 names resolver calls at Q0/Q4/Q7/Q8, terminal publication and recovery,
and `execution-protocol.md` describes them in prose. The implementation
transition matrix rows (Q0, Q4, Q7, Q8) do not list the resolver manifest/hash
as an input and predicate, so a dispatcher can call the resolver only at Q8
while claiming row compliance. Add the resolver read/re-read and stale-hash
predicate to each row, including the post-evidence/pre-publication ordering.

### M3 — Runtime-edge result hash type is weaker than the stated identity

`runtime_assertion_edge.result_sha256` is a free-form string while the receipt,
observation and descriptor hashes use explicit `sha256:<64 hex>` patterns.
The edge can therefore carry an unparseable or differently normalized result
identity while satisfying the schema and still be accepted by an implementation
that trusts the generic field. Constrain `result_sha256` and all identity/hash
fields to the canonical hash format and require a direct immutable result ref.

### M4 — Terminal edge cardinality is stated but not typed

AD-7 and Q8 prose require exactly one current runtime edge for every
V6A `(slice, Acceptance, stage)` tuple, including terminal. The runtime-edge
schema has no tuple key or closure-set schema, so a validator that groups by
`assertion_id` and one that groups by Acceptance can both satisfy the text yet
accept different duplicate/missing sets. Add a typed closure-set predicate or
explicit tuple-key contract and require Q7/Q8 to validate it before publication.

## Closed checks

- V5/V6/V6A ordering: **PASS** — pre-slice cover is separated from final
  slice-bound plan edges and V7 feasibility.
- Trust boundaries and split writers: **PARTIAL** — architecture rules are
  clear, but H1 leaves the receipt schema contradictory.
- Layered outcome/failure identity: **PASS in principle** — outcome, family,
  and ID are separated on observations/edges; receipt leakage remains H1.
- Selector identity and RED/GREEN/REFACTOR reuse: **PASS** — AD-8/AD-9 and
  Q5/Q6 rows bind the same selector/target/fixture/assertion set.
- Terminal binding and current snapshot: **PARTIAL** — terminal hashes are
  required, but H2/H4 leave the resolver representation and path closure
  ambiguous.
- Many-to-many exact cover: **PASS in principle** — overlap is allowed and
  active Acceptance coverage is required; M4 leaves mechanical cardinality
  grouping underspecified.
- Reuse/invalidation and recovery: **PARTIAL** — AD-11/AD-17 define the
  intended algorithm, but M2 and H3 prevent deterministic independent
  implementations.
- Detached judge/fixture independence: **PARTIAL** — minimum contents are
  named, but M1 lacks an enforceable envelope.
- Lint: **PASS** (`total_findings: 0`).

## Recommendation

Do not mark the spine `final` or hand it off as a mechanically convergent
architecture. Resolve H1–H4 and M1–M4 in the normative companions and memlog,
re-distill the spine without weakening AD-1…AD-18, then rerun the complete
Reviewer Gate against a newly frozen revision.

