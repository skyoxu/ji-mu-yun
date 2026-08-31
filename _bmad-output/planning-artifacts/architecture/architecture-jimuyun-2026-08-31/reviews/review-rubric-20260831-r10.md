# Rubric Review — Architecture Spine 2026-08-31 r10

Reviewed artifact: `../ARCHITECTURE-SPINE.md` at the frozen revision including
AD-19, AD-20, and AD-21.

Reviewed inputs: canonical SPEC (`CAP-1`…`CAP-10`) and normative companions
(`execution-protocol.md`, `schema-contracts.md`, `implementation-contracts.md`,
`success-metrics.md`, and `architecture-diagrams.md`).

## Verdict

**BLOCKED — convergence blockers remain.** AD-1…AD-18 continue to provide a
coherent spine, and AD-19…AD-21 are individually well-formed decisions, but
the newly frozen typed closure/root contracts are not yet synchronized with the
normative implementation companion. Independent implementers would choose
incompatible field names and shapes, so the architecture cannot be handed off
until the companion schemas are reconciled (or the ADs are amended).

`lint_spine.py` reports zero mechanical findings; this does not override the
semantic contract mismatches below. `status: draft` is therefore required.

## Findings

### H1 — AD-19 runtime closure contract is absent/incompatible in the companion

AD-19 requires `terminal_input.runtime_closure_tuples` as a closed array with
exact keys `slice_id`, `acceptance_id`, `stage`, `runtime_edge_ref`,
`runtime_edge_sha256`, `selector_identity`, and `current_snapshot_sha256`, and
requires one tuple per V6A `(slice, Acceptance, stage)` key. However,
`implementation-contracts.md`'s `terminal_input` schema does not declare
`runtime_closure_tuples` at all; its only related field is a free-form
`assertion_edge_refs` string array. The separate `runtime_closure_tuple`
definition uses only `edge_ref`/`edge_sha256` and omits selector and snapshot
identity. A builder following the companion cannot implement AD-19, while a
builder following the spine will produce schema-invalid input. **Disposition:
fix companion schema and execution protocol together, then rerun preservation
and reviewer gate.**

### H2 — AD-20 typed snapshot-root contract conflicts with the companion schema

AD-20 requires `current-snapshot-manifest.v1` to enumerate typed root objects
containing `root_kind`, normalized repository-relative path,
`content_sha256`, `source_commit`, and `inclusion_reason`, with typed Git
additions/deletions/renames. `implementation-contracts.md` instead defines
`candidate_tree`, `plan`, `contract`, `registry`, `descriptor`, `fixture`,
`source`, `validator_judge`, and `plan_state_transition` as plain strings and
has no typed delta object. This leaves path normalization, provenance, and
delta semantics divergent at the machine-contract level. **Disposition: adopt
the AD-20 typed root/delta schema in the normative companion (or explicitly
amend AD-20), then rerun package validation and this gate.**

## Checklist summary

- AD-1…AD-18 Binds/Prevents/Rule: PASS.
- AD-19/20/21 Binds/Prevents/Rule: PASS as decisions, but AD-19/20 are not
  consumable with the current companion schemas.
- CAP-1…CAP-10 coverage: PASS.
- Brownfield gate, Deferred/open questions, runtime/environment envelope and
  Mermaid structure: PASS.
- Overall handoff: BLOCKED by H1/H2 until schema synchronization.
