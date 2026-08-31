# Rubric Review — Architecture Spine 2026-08-31 r11

Reviewed artifact: `../ARCHITECTURE-SPINE.md` at the latest frozen revision,
including AD-19, AD-20, and AD-21.

Reviewed inputs: canonical SPEC (`CAP-1`…`CAP-10`) and normative companions
(`execution-protocol.md`, `schema-contracts.md`, `implementation-contracts.md`,
`success-metrics.md`, and `architecture-diagrams.md`).

## Verdict

**BLOCKED — convergence blockers remain.** The spine's decisions are clear and
the AD-19/20 typed contracts are now reflected in the implementation companion,
but the package still exposes conflicting/absent machine contracts for the
new decisions. Independent implementers can therefore select incompatible
runtime-closure or decision-recovery behavior.

`lint_spine.py` reports zero mechanical findings; that does not override these
semantic companion mismatches. `status: draft` is required until resolved.

## Findings

### H1 — Duplicate runtime-closure definition conflicts with AD-19

`terminal_input.runtime_closure_tuples` now has the AD-19 seven-key inline
schema, but `implementation-contracts.md` still publishes a separate
`runtime_closure_tuple` definition using `edge_ref`/`edge_sha256` and omitting
`runtime_edge_ref`, `runtime_edge_sha256`, `selector_identity`, and
`current_snapshot_sha256`. Although the inline field is stricter, the duplicate
definition is a normative-looking alternative that permits incompatible
implementations. Remove or replace the stale definition and reference one
canonical tuple schema from terminal input.

### H2 — AD-21 decision-identity registry has no companion schema or artifact

AD-21 binds an immutable append-only registry mapping historical decision
ordinals to stable AD IDs, with supersession resolution. No registry record or
closed schema is defined in the SPEC companions, and the architecture memlog
only records prose decisions. A recovery implementation can still resolve
historical entries by position or invent registry shape. Add a typed
`architecture-decision-registry.v1` contract (or explicitly defer/amend AD-21)
before handoff.

### M1 — Capability map omits the governing AD-19/20/21 bindings

The spine's Capability → Architecture Map maps CAP-7 only to AD-5/7/8, CAP-8
to AD-11, and CAP-9 to AD-10/12. AD-19, AD-20, and AD-21 are therefore not
visible from the capability map even though they bind CAP-7/8/9 and memlog
recovery. Add the new AD IDs to the corresponding map rows so a downstream
reader can trace every binding without searching the full spine.

## Checklist summary

- AD-1…AD-18 Binds/Prevents/Rule: PASS.
- AD-19/20 intent and AD-20 typed roots/delta: PASS in current spine/companion.
- AD-21 prose decision: PASS, machine contract: FAIL (H2).
- CAP-1…CAP-10 intent/success coverage: PASS, map traceability gap (M1).
- Deferred/open questions, brownfield gate, runtime/environment envelope and
  Mermaid structure: PASS.
- Overall architecture handoff: BLOCKED by H1/H2; M1 should be corrected in
  the same revision.
