# Refactor Implementation Acceptance Skill Execution Plan

- Status: acceptance-passed
- Profile: self-hosted
- Profile reason: This work creates an acceptance-owning Skill and changes the Bootstrap companion, authorization, and validation-control contracts it consumes.
- Plan ID: `refactor-implementation-acceptance-skill`
- Source requirements: `execution-plans/2026-07-15-refactor-implementation-acceptance-skill-requirements.md`
- Source requirements SHA-256: `be6a7c00bff4e78b55014341839cfe1a2f98ccf02de01d72c44da73a8ec71456`
- Git baseline: `108d3112e7c701e97014842600068a912236b7f3`
- Goal: deliver a read-only-by-default `run-refactor-implementation-acceptance` Skill that evaluates implementation acceptance clauses, Phase-service policy coverage, phase gates, and DoD without becoming a second semantic-review or release authority.
- Current step: maintainer accepted the bounded semantic-review history and the final deterministic Acceptance evidence; release, deployment, handoff, and archive remain unauthorized.
- Recovery command: `py -3 -B tools/validate_plan.py`

## Scope

The implementation owns the new Skill package, its machine contracts, adapters, policy pack, controlled-validation protocol, fixtures, and repository-owned Bootstrap v2 companion extensions required by the source requirements. It does not modify a target refactor plan, production refactor code, live Phase state, hosted workspaces, or historical evidence.

## Lifecycle

`draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`.

VDD owns this directory through `plan-ready`; Quick Dev may later publish only `implementation-complete` after the S5 terminal predicate. The new acceptance Skill may own only the acceptance conclusions of its evaluated target, never this plan's release, handoff, deployment, or archive state.

## Knowledge Gate

`knowledge-context.v1.json` freezes the VDD request, location-only Locator result, and adapter-owned decision. The required `repository-rules` candidate was reread from `refs/heads/main` and its source hash was verified before VDD accepted it. The catalog remains `derived_cache`: it supplies a location recommendation and never replaces direct authority reads.

## Slices

1. `S0-bootstrap-companion`: Bootstrap v2 companion capability, role-bundle, Artifact View, launch-authorization, durable-standard, operator, and ADR-0041 no-change-or-update closure.
2. `S1-deterministic-core`: new Skill package, typed run input, content manifests, source inventory, policy binding, task closure, diff coverage, and Phase-aware scan contracts.
3. `S2-matrix-phase`: atomic clause IDs, policy exact coverage, base matrix, impact projection, phase DAG, DoD candidates, and 7-07 adapter fixture.
4. `S3-execution-control`: typed command registry, controlled-validation actions, recovery, locking, stale handling, and deterministic `nextAction`.
5. `S4-bootstrap-integration`: immutable Bootstrap requirement decision, conditional binding, attestation, import, finding mapping, approval receipt, and semantic completeness projection.
6. `S5-finalize-release-candidate`: candidate/final custody, comprehensive positive/negative/mutation fixtures, package validation, fresh-context observations, and terminal replay.

S0 and S1-S3 may proceed in isolated write sets. S4 requires S0-S3; S5 requires S0-S4. Each predicate is non-escalating: lower predicates never authorize a later predicate, target-plan acceptance, release, or handoff.
