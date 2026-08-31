# Adversarial architecture review — 2026-08-31 (r11)

Target: the frozen `ARCHITECTURE-SPINE.md`, normative SPEC companions, and
the plan-local brownfield implementation. This pass rechecks AD-19/20/21 after
their claimed synchronization. The spine was not modified.

## Gate verdict

**BLOCKED.** AD-19 and AD-20 are now represented in
`implementation-contracts.md`, and AD-21 is recorded in the architecture
memlog. However, the equivalent `schema-contracts.md` remains prose-only for
the new closure/root/registry objects, the schemas do not enforce all
cross-field cardinality and containment predicates, and the active brownfield
tools still violate AD-15. The architecture is not yet mechanically convergent
for independent implementers or safe for handoff.

## High findings

### H1 — Typed runtime closure is not synchronized across normative companions

`implementation-contracts.md:394,403` requires
`runtime_closure_tuples`, but `schema-contracts.md:51-96` only gives a
free-form runtime-edge example and prose saying that a closure set must exist.
There is no typed closure-set schema or terminal-input requirement in that
companion. A consumer that follows schema-contracts can still accept opaque
edge references while one following implementation-contracts requires tuples.
Additionally, `uniqueItems` on tuple objects does not prevent duplicate
`(slice_id, acceptance_id, stage)` keys when edge/hash fields differ. Add one
shared closure tuple schema (and tuple-key uniqueness predicate) to both
companions and require it at Q7/Q8.

### H2 — AD-20 root/delta schemas do not enforce exact one-per-kind or safe delta paths

The `current_snapshot_manifest` schema (`implementation-contracts.md:423-433`)
uses `roots` with `minItems: 9`/`uniqueItems`, but does not mechanically require
exactly one entry for each of the nine `root_kind` values. `git_delta` path
properties are unconstrained strings, so absolute paths, `..`, or symlink/junction
targets remain schema-valid. `schema-contracts.md:102-104` states the stricter
rules only in prose. Two resolvers can therefore produce different root sets or
accept different rename/escape behavior. Add root-kind set equality, canonical
path patterns, and closed delta/path predicates in the shared schema.

### H3 — AD-21 identity registry is not an independently addressable artifact

The memlog line `AD_ID_REGISTRY_V1: {AD-1:8, ...}` is embedded as ordinary
decision text. No registry object, hash, or parser contract is defined, and
earlier unlabelled entries remain indistinguishable from later amendments. A
resume implementation can interpret the map as advisory text or select an
ordinal without proving immutability. Define a closed, content-addressed
`ad-identity-registry.v1` artifact (or equivalent typed memlog record), require
its hash in the current snapshot, and reject duplicate/contradictory mappings.

### H4 — Legacy implementation remains outside AD-15 authority seams

The plan-local `artifact_owners.py` still executes the process, constructs the
receipt, invokes the judge, and emits combined evidence; `stage_command.py`
still launches direct pytest/owner commands and pre-writes terminal
observation. The registry still lacks an authoritative RED entry. This is an
implementation-only AD-15 handoff blocker, but it prevents the architecture
from being honestly marked final until a fresh conformance run proves executor-
only receipts, judge-only observations, and one descriptor-bound seam.

## Medium findings

### M1 — Detached bundle isolation remains under-constrained

The detached bundle schema carries paths and hashes but no machine predicate
that all paths are outside the candidate tree and cannot import candidate
evidence writers. AD-18's independence rule is still partly prose-only.

### M2 — Runtime edge `result_sha256` remains less constrained than other hashes

`runtime_assertion_edge.result_sha256` is a free-form string while receipt,
observation, and descriptor hashes require `sha256:<64 hex>`, allowing
inconsistent result identities.

## Closed checks

- AD-19/20/21 appear in the spine and memlog: **PASS in prose**.
- V5→V6→V6A ordering, plan/runtime edge separation, and selector reuse:
  **PASS**.
- Machine-contract synchronization and brownfield implementation handoff:
  **FAIL** (H1–H4).
- `lint_spine.py`: **PASS**, zero findings.

## Recommendation

Keep the spine `draft`. Resolve H1–H3 in the normative schema/memlog and treat
H4 as the explicit AD-15 implementation handoff gate. Then rerun the complete
Reviewer Gate against a new frozen revision; lint or prose coherence alone is
not sufficient.

