# Adversarial architecture review — 2026-08-31 (r15)

Target: frozen `ARCHITECTURE-SPINE.md`, all normative SPEC companions, the
materialized `architecture-decision-registry.v1.json`, and the plan-local
brownfield tools. The spine was not modified.

## Gate verdict

**BLOCKED.** Runtime closure and registry bindings are aligned in the principal
implementation contract and the registry file's selection/spine hashes match
the current bytes. A stale Q8 contract and incomplete machine envelope remain
document convergence blockers; the legacy executor/stage implementation is a
separate AD-15 handoff blocker.

## Findings

### H1 — Q8 execution protocol still names the superseded opaque edge list

`execution-protocol.md:91` says terminal input contains `assertion edge refs`,
while AD-19 and `implementation-contracts.md:394,403` require the typed
`runtime_closure_tuples` array with `tuple_key`, edge hash, selector identity,
and current-snapshot hash. An implementer following the execution protocol can
legitimately omit the typed closure set and diverge from one following the
implementation contract. Replace the stale field wording and state the exact
tuple cardinality predicate in Q8.

### H2 — Schema companion machine envelope is weaker than its own typed prose

`schema-contracts.md:131-147` declares `roots` and `git_delta` only as generic
arrays/objects; concrete root-item and delta-child properties are described in
prose. The implementation companion has the detailed child schemas, but the
two normative inputs are not mechanically interchangeable. A consumer using
schema-contracts alone can accept arbitrary root kinds or unsafe delta paths.
Inline or `$ref` the typed root/delta child schemas and the exact nine-kind
set in the schema companion as well.

### H3 — AD-15 legacy implementation remains non-conformant

`artifact_owners.py` still executes the process and writes receipt plus judge
observation in one path. `stage_command.py` still launches direct pytest/owner
commands and calls `prepare_terminal_observation()` before terminal execution;
the registered lifecycle path lacks an authoritative RED descriptor. This is
an implementation handoff blocker (not new architecture scope) until a fresh
AD-15 run proves split writers, descriptor-bound executor dispatch, and
post-process terminal evidence.

## Verified closed items

- `runtime_closure_tuple` uses `tuple_key` and identical
  `runtime_edge_ref/runtime_edge_sha256` fields in both implementation and
  schema companions; exact-one V6A cardinality is stated.
- `current-snapshot-manifest.v1` names all nine root kinds and canonical path
  grammar; implementation-contracts contains typed Git delta child paths.
- `architecture-decision-registry.v1.json` exists with 21 AD entries; its
  canonical selection and spine SHA-256 bindings recompute exactly.
- V5→V6→V6A ordering, plan/runtime edge separation, and selector identity
  reuse remain consistent.
- `lint_spine.py`: PASS, zero findings.

## Recommendation

Keep `ARCHITECTURE-SPINE.md` in `draft`. Synchronize Q8 wording and the typed
root/delta schema across companions, then resolve H3 under the explicit AD-15
handoff gate and rerun the complete Reviewer Gate on a new frozen revision.

