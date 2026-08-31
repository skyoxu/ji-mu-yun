# Rubric Review — Architecture Spine 2026-08-31 r14

Reviewed artifact: `../ARCHITECTURE-SPINE.md` at the latest frozen revision.

Reviewed inputs: canonical SPEC (`CAP-1`…`CAP-10`), normative companions
(`execution-protocol.md`, `schema-contracts.md`, `implementation-contracts.md`,
`success-metrics.md`, `architecture-diagrams.md`), and
`architecture-decision-registry.v1.json`.

## Verdict

**BLOCKED — one machine-contract convergence blocker remains.** AD-1…AD-20,
typed runtime closure/snapshot contracts, CAP map, Deferred table, brownfield
gate and Mermaid views are coherent. AD-21 now has the intended registry
artifact and bindings in the spine, but the normative registry schema rejects
the actual artifact, so recovery implementations do not have one schema-valid
decision-authority contract.

`lint_spine.py` reports zero mechanical findings; the semantic schema mismatch
still requires `status: draft` and blocks handoff.

## Findings

### H1 — AD-21 registry artifact is invalid under its companion schema

`ARCHITECTURE-SPINE.md` AD-21 and the checked-in
`architecture-decision-registry.v1.json` add a required `bindings` object
(`canonical_selection_path`, `canonical_selection_sha256`, `spine_path`, and
`spine_sha256`). However, the normative `architecture_decision_registry`
schema in `implementation-contracts.md` requires only `schema`, `registry_id`,
and `entries`, sets `additionalProperties: false`, and defines no `bindings`
property. The actual registry therefore fails the declared schema, while a
schema-compliant registry would omit the hashes AD-21 requires. Add the closed
typed `bindings` property (with path/hash constraints) to the companion schema,
or amend AD-21 and regenerate the artifact; then rerun package and Reviewer
Gate validation.

## Checklist summary

- AD-1…AD-20 Binds/Prevents/Rule: PASS.
- AD-21 decision intent and artifact: PASS in spine/artifact, schema validity:
  FAIL (H1).
- CAP-1…CAP-10 map, Deferred/open questions, brownfield gate, typed
  runtime/snapshot contracts and Mermaid structure: PASS.
- Overall architecture handoff: BLOCKED by H1 only.
