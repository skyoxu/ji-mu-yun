# Adversarial architecture review — 2026-08-31 (r9)

Target: `ARCHITECTURE-SPINE.md` and the current normative companions
(`execution-protocol.md`, `schema-contracts.md`, `implementation-contracts.md`,
and `success-metrics.md`) at the frozen workspace revision. This review also
checks the plan-local brownfield tools that the spine names as the existing
execution substrate. The spine was not modified.

## Gate verdict

**BLOCKED.** The documents now state the split-writer, V5/V6A ordering,
current-snapshot, detached-bundle, and runtime-closure goals, but the active
brownfield implementation still bypasses those seams and several machine
contracts remain weaker than the prose. Independently compliant implementations
can therefore disagree on who owns observations, which runtime tuples close a
terminal, and what bytes constitute the current candidate.

## High findings

### H1 — Brownfield receipt/observation ownership is still a combined writer

`execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/artifact_owners.py:78-110`
executes the SUT, constructs the process receipt, invokes the judge, and emits
the observation from one function. `process_executor.py` remains execution-only
and does not persist a receipt. This directly violates AD-4/AD-6 and the
brownfield handoff gate AD-15(a): a candidate-controlled producer can still
couple process output and semantic classification. The implementation must
persist an immutable executor receipt first, then invoke a separately provisioned
judge that consumes only that receipt and writes observation/classification.

### H2 — Registered lifecycle stages bypass the descriptor/executor seam

`tools/stage_command.py:26-30,61-79` invokes `pytest`/owner subprocesses
directly (and pre-writes terminal observation) instead of dispatching one frozen
descriptor through the executor. The command registry has no authoritative RED
entry, and the direct and owner paths can use different cwd/argv roots. This
leaves selector identity, timeout, write-set, and evidence ownership divergent
across implementations, violating AD-3/AD-8/AD-15(d,e). Q3/Q5/Q6 must all
dispatch the same descriptor/executor path; any direct probe must be explicitly
diagnostic and rejected by lifecycle predicates.

### H3 — Runtime closure cardinality is not wired into the terminal input

`implementation-contracts.md` defines a `runtime_closure_tuple` object, but
`terminal_input` still requires only `assertion_edge_refs: string[]` and does
not require a closed tuple set keyed by `(slice_id, acceptance_id, stage)`.
The companion prose says exactly one current edge per V6A tuple, yet a validator
grouping by assertion ID, Acceptance, or slice can all satisfy the current
schema. Missing/duplicate terminal edges can therefore reach Q8. Require a
typed `runtime_closure_tuples[]` (or equivalent closure-set object) in terminal
input, enforce one-and-only-one for every active V6A tuple, and reject plan-only,
cross-run, or predicate-false edges before terminal publication.

### H4 — Memlog supersession still cannot be recovered deterministically

AD-16 requires stable `AD-*` identities on every decision and explicit
`supersedes`. The architecture `.memlog.md` still stores un-IDed decision lines;
the ownership corrections merely contain free text such as
`supersedes: AD-6`/`supersedes: AD-15`. A renderer/resumer cannot identify the
new decision that supersedes the old one or reject two live decisions for one
topic. Add stable IDs to each decision entry (especially superseding entries)
and make contradictory live ownership decisions a validation error.

### H5 — Current-snapshot and path schemas remain under-specified for exact bytes

Although `current_snapshot_manifest` now exists, its root fields
(`candidate_tree`, `plan`, `contract`, `registry`, `descriptor`, `fixture`,
`source`, `validator_judge`, `plan_state_transition`) are unconstrained strings;
there is no typed per-root normalized path/hash record or schema for the exact
Git additions/deletions/renames delta. Likewise slice write-path arrays do not
encode the repository-relative/symlink-safe closed-set result. Two adapters can
hash different bytes or accept different junction/rename behavior while both
passing the schema. Define a canonical root entry and delta object, enforce
POSIX normalization/containment, and require unknown or unlisted paths to
invalidate.

## Medium findings

### M1 — Detached judge bundle lacks encoded outside-candidate and import rules

The `detached_judge_bundle` shape requires hashes and booleans, but path fields
are unconstrained and there is no machine predicate that the bundle is outside
the candidate tree and cannot import candidate evidence writers. AD-18's
independence claim therefore remains partly prose-only. Add explicit path
containment/import-deny fields and validate them at promotion.

### M2 — Resolver invocation/re-read is not a row-level contract

AD-17 and execution-protocol prose name Q0/Q4/Q7/Q8, terminal publication and
recovery, but the implementation transition matrix still lists only plan/slice
and evidence inputs. An adapter can defer the resolver until Q8 and remain
schema-valid. Add resolver manifest/hash and pre/post evidence re-read as
required predicates to each lifecycle row.

### M3 — Runtime edge `result_sha256` remains a free-form string

Receipt/observation/descriptor hashes enforce `sha256:<64 hex>`, while
`runtime_assertion_edge.result_sha256` does not. A malformed result identity can
therefore pass schema validation and be trusted by a permissive consumer.
Constrain it to the canonical hash format and require a direct immutable result
reference.

## Closed checks

- V5/V6/V6A ordering: **PASS** — pre-slice cover and final plan edges are
  separated before feasibility.
- Split ownership in the architecture text: **PASS in principle**, but H1/H2
  show the current brownfield implementation is non-conformant.
- Layered outcome/failure identity and selector reuse: **PASS in principle**.
- Terminal hash bindings and many-to-many exact-cover intent: **PASS in
  principle**; H3 prevents mechanical closure enforcement.
- Lint: **PASS** (`total_findings: 0`).

## Recommendation

Keep the spine in `draft` and block architecture handoff. Resolve H1–H5 in the
implementation/contracts and M1–M3 in the normative schemas, then rerun the
complete Reviewer Gate on a newly frozen revision. Do not treat a passing lint
or document-only coherence result as brownfield conformance.

