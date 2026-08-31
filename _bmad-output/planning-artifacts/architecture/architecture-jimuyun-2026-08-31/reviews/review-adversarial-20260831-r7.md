# Adversarial architecture review — 2026-08-31 (r7)

Target: `ARCHITECTURE-SPINE.md` and the current normative companions
(`execution-protocol.md`, `schema-contracts.md`, `implementation-contracts.md`,
`success-metrics.md`). The spine was not modified. This pass attempts two
independently implemented adapters that both follow the prose but choose
different snapshot/path/resolver and detached-judge behavior.

## Gate verdict

**BLOCKED.** H1–H3, H5 and most of H6 are now materially represented in the
contracts (split writers, authenticated runtime edges, layered failure identity,
terminal bindings, and one-per-stage closure). However, the contracts still do
not force a unique current-byte resolver, closed path delta, detached bundle
envelope, lifecycle resolver invocation, or memlog supersession identity. Two
implementations can therefore remain schema-valid while disagreeing on what is
current and which writes/evidence are admissible.

## High findings

### H4 — Current-snapshot resolver has no machine contract

AD-11/AD-15 name a versioned resolver and list roots, but neither
`implementation-contracts.md` nor `schema-contracts.md` defines a versioned
root-manifest object, exact include/exclude classes, evidence-only exclusion,
plan-state transition exception, or the Git-delta/snapshot algorithm. One
adapter can hash the whole worktree while another hashes only production files;
both satisfy the current text. Define one canonical resolver manifest and
unknown-path behavior, permit only the explicit plan-state transition after
candidate capture, and require current-byte re-read before each publication.

### H7 — Write-set and planned-file semantics remain prose-only

Slice fields contain `allowed_write_paths`, `execution_snapshot_paths` and
`planned_new_files`, but no normative schema defines repository-relative POSIX
normalization, symlink/junction escape rejection, closed-set semantics, or exact
Git additions/deletions/renames comparison. An implementation may add an
unlisted file beneath an allowed directory (or through a junction) and still
claim a valid successor. Add a single path resolver and require exact closed
delta validation for Q4.

### H8 — Memlog decision identity is not recoverable

The rendered spine has AD-16 and states “latest non-superseded” authority, but
`.memlog.md` entries themselves have no stable decision IDs. The ownership
supersession line mentions `supersedes: AD-6` without assigning an ID to the new
decision. A renderer/resumer cannot deterministically distinguish two live
entries or prove which entry supersedes which. Append explicit stable IDs and
make contradictory live ownership entries a validation error.

## Medium findings

### M1 — Invalidation classifier/version is unnamed

The resolver is described as repository-owned and versioned, but no canonical
path to its implementation, manifest version, or unknown-path classification
(`invalidate` versus `reuse`) is fixed. Different adapters can classify a
validator/fixture helper differently. Bind the classifier and require unknown
paths to take the stricter invalidation route.

### M2 — Detached judge/fixture envelope is incomplete

AD-10 requires independence and hashes, but the normative contracts do not
require a minimum content-addressed bundle containing source commit/tree,
judge/oracle/fixture hashes, immutable path, read-only-open result and
promotion-time revalidation. Keep ceremony Deferred, but make that envelope
schema-mandatory for self-hosted/toolchain acceptance.

### M3 — Resolver invocation is not explicit in every lifecycle row

The prose and AD-15 mention Q0/Q4/Q7/Q8/recovery, yet the transition matrix
does not list the resolver as an input/predicate or require a re-read on each
path. An implementation can call it only at Q8 and still satisfy the table.
Add explicit read-only resolver dependencies and invocation/re-read ordering to
Q0, Q4, Q7, Q8, terminal publication and recovery.

### M4 — Recovery revalidation ordering is underspecified

Q8 requires a final current-snapshot check, but recovery has no equivalent
ordered predicate stating that predecessor evidence is written first, then
candidate/dependency bytes are re-read immediately before publishing a recovered
run. Require this ordering and route any drift to invalidation/repair.

## Closed checks

- H1: PASS — Q5/Q6 rows identify dispatch-only Quick Dev, executor receipt,
  independent judge observation/classification.
- H2: PASS — runtime edges require receipt/observation/descriptor/target/fixture
  refs and hashes plus current identity re-read semantics.
- H3: PASS — runtime edges carry layered outcome/family/ID with pass/null and
  process-failure requirements.
- H5: PASS — terminal input binds predicate, partition, descriptor, evaluator and
  current snapshot hashes.
- H6: PASS in principle — Q8 prose requires exactly one current edge per
  Acceptance/stage and rejects duplicates; implementation should expose the
  cardinality predicate directly when the terminal validator is built.

## Recommendation

Do not mark the spine `final` or hand it off as a mechanically convergent
architecture. Add the resolver/root-manifest and closed-path contracts, the
detached bundle envelope, explicit resolver invocation/revalidation order, and
stable memlog decision IDs; then rerun the complete Reviewer Gate on a new
frozen revision.

