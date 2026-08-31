# Adversarial architecture review — 2026-08-31 (r13)

Target: frozen `ARCHITECTURE-SPINE.md`, SPEC companions, the materialized
`architecture-decision-registry.v1.json`, and plan-local brownfield tools. The
spine was not modified.

## Gate verdict

**BLOCKED.** The runtime-closure field names and the AD-19/20/21 decisions are
now aligned in the principal implementation contract, and the decision
registry artifact exists with 21 entries. Nevertheless, `schema-contracts.md`
still publishes weaker envelope schemas, the implementation schemas omit key
cross-field/path predicates, and legacy execution code remains outside AD-15.

## High findings

### H1 — `schema-contracts.md` still permits under-specified closure and registry envelopes

The closure object in `schema-contracts.md:98-117` is aligned on
`runtime_edge_ref/runtime_edge_sha256`, but the terminal-input requirement and
tuple-key uniqueness are prose-only. Its registry machine schema
(`schema-contracts.md:152-164`) declares `entries` only as an untyped array,
while `implementation-contracts.md:464-473` requires typed entries. A consumer
using schema-contracts can accept malformed or duplicate ordinal/decision/topic
entries. Publish one shared typed definition (including tuple-key and registry
entry uniqueness) and require both companions to reference it.

### H2 — AD-20 root/delta path safety is not enforced by the machine schema

`implementation-contracts.md:423-433` now has the typed root envelope and
exact-size/root-kind prose, but `git_delta` child `path`, `from_path`, and
`to_path` properties remain unconstrained strings. `schema-contracts.md:123-146`
describes canonical POSIX and symlink/junction rules only as prose. An
implementation can therefore pass schema validation with an absolute path,
`..` segment, or an unlisted rename. Add canonical path patterns and explicit
cross-field plan-state-transition/unknown-path predicates to the shared schema.

### H3 — Materialized AD registry is not bound into the canonical package graph

`architecture-decision-registry.v1.json` exists with 21 entries, but the
canonical SPEC package does not list it as a companion and the spine
frontmatter does not name its path/hash. Only AD-21 prose says the registry is
consumed by recovery. A package consumer can thus omit or substitute the
registry while still seeing a valid SPEC selection. Add the registry as an
explicit adopted architecture companion (or an equivalent mandatory root
binding) and require its content hash in the current snapshot/recovery input.

### H4 — Legacy brownfield execution remains an AD-15 handoff blocker

`artifact_owners.py` still executes the process, constructs receipt and
observation, and invokes the judge in one path. `stage_command.py` still calls
direct pytest/owner commands and pre-writes terminal observation; RED remains
absent from the authoritative registry path. This implementation divergence is
outside the architecture text but prevents `status: final` or implementation
handoff until a fresh AD-15 conformance run proves the split seams.

### H5 — Runtime closure cardinality is still not a schema-level key constraint

`runtime_closure_tuples` has `uniqueItems: true`, which only rejects byte-for-
byte duplicate objects. Two tuples with the same `(slice_id, acceptance_id,
stage)` and different edge/hash payloads remain schema-valid; exact-one
cardinality is only prose. Add a tuple-key uniqueness/set-equality predicate
that is mandatory before Q7/Q8 publication.

## Closed checks

- Runtime closure field-name alignment: **PASS**.
- Registry artifact presence and 21 AD entries: **PASS** (binding still H3).
- V5→V6→V6A ordering, plan/runtime separation, selector reuse: **PASS**.
- Machine-contract convergence and brownfield handoff: **FAIL** (H1–H5).
- `lint_spine.py`: **PASS**, zero findings.

## Recommendation

Keep architecture status `draft`. Synchronize shared typed schemas and
cross-field predicates, bind the registry artifact into the package/recovery
graph, then resolve the AD-15 legacy implementation findings and rerun the
complete Reviewer Gate on a new frozen revision.

