# Adversarial architecture review — 2026-08-31 (r14)

Target: frozen `ARCHITECTURE-SPINE.md`, SPEC companions, and the materialized
`architecture-decision-registry.v1.json`. This pass re-read the current bytes
and verifies AD-19/20/21 against their machine contracts. The spine was not
modified.

## Gate verdict

**BLOCKED — AD-15 handoff only.** The document contracts are now convergent:
runtime closure uses one `tuple_key` shape in both companions, snapshot roots
and Git delta have typed envelopes and canonical path grammar, and the
materialized AD registry contains 21 entries with matching selection/spine
bindings. No remaining architecture-document convergence blocker was found.
The plan-local implementation, however, still violates the declared AD-15
authority seams and therefore cannot be handed off or marked final.

## Findings (implementation handoff blockers)

### H1 — Combined receipt/observation writer remains in production path

`execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/artifact_owners.py:78-110`
executes the process, constructs the receipt, invokes the judge, and emits
observation/classification in one authority. This is incompatible with AD-4,
AD-6 and AD-15(a): the executor must persist the immutable process receipt
first, then an independent judge must consume only that receipt and write the
observation/classification.

### H2 — Lifecycle dispatcher still bypasses descriptor/executor and pre-writes terminal evidence

`tools/stage_command.py:26-30,61-79` directly launches pytest/owner commands,
uses split cwd roots, and calls `prepare_terminal_observation()` before a
terminal process executes. The registry still has no authoritative RED entry.
This violates AD-3/AD-8 and AD-15(d,e); direct probes must be diagnostic-only
and rejected by lifecycle predicates.

### H3 — Runtime snapshot/closure resolver is not used by the active tools

`tools/validate_all.py:16-20,55-57` still computes a Git status/index summary
and selected manifest rather than invoking the versioned
`current-snapshot-manifest.v1` resolver and validating AD-19 tuple closure at
Q0/Q4/Q7/Q8/recovery. Thus the implementation does not yet enforce the typed
root set, exact delta, or one-edge-per-tuple predicates that the documents now
bind.

## Verification of document contracts

- AD-19 closure tuple: **PASS** — both companions use
  `tuple_key`, `runtime_edge_ref`, and `runtime_edge_sha256`; terminal input
  requires the typed tuple array and exact V6A cardinality.
- AD-20 snapshot roots/Git delta: **PASS** — typed root kinds, canonical path
  grammar, and additions/deletions/renames are present in both companions;
  registry binding is part of the root contract.
- AD-21 decision registry: **PASS** — `architecture-decision-registry.v1.json`
  exists with 21 AD entries; canonical selection and spine SHA-256 bindings
  recompute exactly to the referenced bytes.
- V5→V6→V6A ordering, plan/runtime separation, selector reuse: **PASS**.
- `lint_spine.py`: **PASS**, zero findings.

## Recommendation

Keep the spine in `draft` solely because AD-15 implementation conformance is
blocked. Resolve H1–H3 in the plan-local tools, run a fresh AD-15 conformance
report, then rerun the complete Reviewer Gate before setting `status: final`.

