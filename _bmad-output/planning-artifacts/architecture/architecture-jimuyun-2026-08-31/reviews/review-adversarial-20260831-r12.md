# Adversarial architecture review — 2026-08-31 (r12)

Target: frozen `ARCHITECTURE-SPINE.md`, normative SPEC companions, and the
plan-local brownfield tools. This pass rechecks AD-19/20/21 synchronization.
The spine was not modified.

## Gate verdict

**BLOCKED.** The companions now describe typed runtime closure, typed snapshot
roots/Git delta, and an architecture decision registry, and the spine records
AD-19/20/21. However, cross-companion schemas still disagree on the closure
tuple field names and the registry is not materialized as a separate artifact.
The active implementation also remains outside the declared AD-15 seams.

## High findings

### H1 — Runtime closure tuple schema is internally inconsistent

`implementation-contracts.md` terminal input requires tuple objects with
`runtime_edge_ref` and `runtime_edge_sha256` (lines 394, 403), while its
standalone `runtime_closure_tuple` definition still requires `edge_ref` and
`edge_sha256` (lines 450–460). `schema-contracts.md` describes only prose and
does not publish either typed object. A producer following the standalone
definition will be rejected by terminal input, while one following terminal
input will fail the standalone schema. The tuple schema and key names must be
single-sourced and imported identically by both companions; tuple-key
uniqueness remains a required cross-field predicate.

### H2 — Typed snapshot/Git-delta rules are not fully shared or executable

`implementation-contracts.md` now has typed `roots` and `git_delta`, but
`schema-contracts.md` still gives the root/delta contract only as prose. The
implementation schema does not constrain delta path fields to the canonical
repository-relative grammar or encode the plan-state-transition exception in
the object. Independent resolvers can therefore differ on root-kind equality,
rename semantics, or unsafe paths while both satisfy one companion. Publish a
shared closed schema and explicit cross-field path/delta predicates.

### H3 — AD-21 registry is still not a materialized, bound artifact

The memlog contains an `AD_ID_REGISTRY_V1` map as decision text and
`implementation-contracts.md` defines a registry shape, but no repository-owned
registry file/hash is listed in the canonical SPEC package or architecture
root set (the root kind `registry` remains generic). Recovery cannot prove that
the map is immutable or that historical ordinals map one-to-one to AD IDs.
Materialize `architecture-decision-registry.v1`, content-address it, bind its
hash in the current snapshot, and reject missing/duplicate/contradictory
entries.

### H4 — Brownfield implementation still violates AD-15

`artifact_owners.py` remains a combined process/receipt/judge/observation
writer, and `stage_command.py` still bypasses the descriptor/executor seam and
pre-writes terminal observation. The registry lacks an authoritative RED path.
These are implementation handoff blockers (not new CAP scope), but they mean
the architecture cannot honestly transition to final until a fresh conformance
run proves split writers, one descriptor-bound executor path, and post-process
terminal evidence.

## Medium findings

### M1 — Detached bundle outside-candidate/import isolation remains prose

The bundle has hashes and read-only booleans, but no typed fields/predicate for
outside-candidate containment or import denial.

### M2 — Runtime `result_sha256` is still an unconstrained string

The runtime-edge schema leaves `result_sha256` without the canonical
`sha256:<64 hex>` pattern used by other hashes.

## Closed checks

- AD-19/20/21 presence in spine/memlog: **PASS in prose**.
- V5→V6→V6A ordering, plan/runtime separation, selector reuse: **PASS**.
- Companion schema convergence and brownfield implementation handoff:
  **FAIL** (H1–H4).
- `lint_spine.py`: **PASS**, zero findings.

## Recommendation

Keep `ARCHITECTURE-SPINE.md` in `draft`. Synchronize one canonical closure
tuple schema and typed snapshot/delta contract across companions, materialize
and bind the AD registry, then resolve AD-15 implementation blockers and rerun
the complete Reviewer Gate on a newly frozen revision.

