# Adversarial architecture review — 2026-08-31 (r16)

Target: frozen `ARCHITECTURE-SPINE.md`, normative SPEC companions, the
materialized `architecture-decision-registry.v1.json`, and plan-local tools.
The spine was not modified.

## Gate verdict

**BLOCKED — AD-15 handoff only.** The documentation and typed contracts now
converge: Q8 explicitly requires `runtime_closure_tuples`; both companions use
the same `tuple_key` shape, exact nine root kinds, canonical Git-delta path
grammar, and registry envelope; and the registry file contains 21 entries with
selection/spine bindings whose SHA-256 values match current bytes. No new
architecture-document convergence blocker was found. Legacy execution code
still fails the explicitly declared AD-15 implementation gate.

## Findings (AD-15 implementation handoff)

### H1 — Receipt and observation are still produced by one legacy authority

`execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/artifact_owners.py:78-110`
executes the SUT, builds the process receipt, invokes the judge, and emits
observation/classification in a single path. This remains incompatible with
AD-4/AD-6 and AD-15(a). A fresh conformance run must show executor-only
receipt persistence followed by judge-only observation/classification.

### H2 — Lifecycle stages still bypass the frozen descriptor/executor seam

`tools/stage_command.py:26-30,61-79` directly launches pytest/owner commands,
uses divergent cwd roots, and pre-writes terminal observation before terminal
execution. The registered path still lacks an authoritative RED descriptor.
This is the AD-15(d,e) blocker; direct probes must be diagnostic-only and their
outputs rejected by lifecycle predicates.

### H3 — Active validator has not adopted typed snapshot/closure predicates

`tools/validate_all.py:16-20,55-57` still computes Git status/index summaries
and selected manifests rather than invoking `current-snapshot-manifest.v1`,
checking the exact Git delta, and validating AD-19 tuple closure at Q0/Q4/Q7/Q8
and recovery. The implementation therefore cannot yet enforce the converged
contracts even though they are present in the companions.

## Contract verification

- Q8 typed `runtime_closure_tuples` and `tuple_key`: **PASS** in
  `execution-protocol.md`, `schema-contracts.md`, and `implementation-contracts.md`.
- Typed root kinds and canonical Git-delta paths: **PASS** in both schema
  companions; exact-nine root set is stated and encoded.
- `architecture-decision-registry.v1.json`: **PASS**; 21 AD entries and
  selection/spine SHA-256 bindings recompute exactly.
- V5→V6→V6A ordering, plan/runtime edge separation, selector reuse: **PASS**.
- Spine lint: **PASS**, zero findings.

## Recommendation

Keep architecture status `draft` solely for AD-15. Resolve H1–H3 in the
plan-local implementation, produce a fresh AD-15 conformance report, then
rerun the complete Reviewer Gate before setting `status: final`.

