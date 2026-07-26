# Knowledge Locator Workflow Integration Execution Plan

- Title: Knowledge Locator Workflow Integration
- Status: implementation-complete
- Profile: self-hosted
- Profile reason: The change modifies VDD, Quick Dev, Bootstrap Review, and their controlling validators.
- Plan ID: `knowledge-locator-workflow-integration`
- Git baseline: `b823ab2af4253bfc4dfdfefb627ddde831ca067c`
- Baseline tree: `849ad1d921d289ffe8aa94a6823afcee522b90b6`
- Goal: Promote the plan-local Knowledge Locator contract into one stable deterministic repository service and integrate location-only retrieval plus adapter-owned consumption decisions into VDD preflight, Quick Dev verify-bound preparation, and Bootstrap Review prepare-time context freezing.
- Scope: ADR-0048, stable knowledge contracts/catalogs/policies, Locator CLI and index builder, minimal accepted/rejected consumption decisions in three workflow adapters, migration compatibility, tests, and one terminal integration validator.
- Non-goals: Phase route integration, Hosted E2 changes, runtime deployment, live metadata/workspace access, semantic answer generation, embeddings, default LLM retrieval, implementation acceptance, release, or archive.
- Current step: Terminal implementation predicate passed; acceptance remains external.
- Recovery command: `py -3 -B execution-plans/2026-07-26-knowledge-locator-workflow-integration/tools/validate_plan.py`

## Authority

Authority order is `AGENTS.md` and Accepted ADRs, the 2026-07-25 completed knowledge contract, current VDD/Quick Dev/Bootstrap Skill contracts, this plan's machine contract, then explanatory text in this directory. Knowledge projections remain `derived_cache` and never replace repository source authority.

The upstream knowledge-plan authority binding includes its `00-index.md` and active `requirements-ledger.v1.json`; the dated Locator request/result schemas remain separately pinned migration sources. Any drift in those authority artifacts invalidates this plan's authority root before implementation resumes.

ADR-0048 is an implementation deliverable, not an authority that already exists. It must extend ADR-0044, complement ADR-0037/0041/0043, and supersede none of them.

## Lifecycle

The lifecycle is `draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`. This directory and its validator may publish only `plan-ready`. Quick Dev may publish only `implementation-complete` after the terminal integration command passes. Bootstrap Review remains optional supplemental evidence and publishes no lifecycle state.

## Machine Owners

- Requirements and acceptance: `01-requirements-and-acceptance.md`
- Implementation slices and boundaries: `implementation-contract.v1.json`
- Structured commands: `command-registry.v1.json`
- Baseline authority hashes: `authority-manifest.v1.json`
- Lifecycle state: `plan-state.v1.json`
- Resume state: `resume-state.v1.json`
- Self-hosted protocol and migration fixtures: `fixtures/*.v1.json`
- Plan-ready predicate: `tools/validate_plan.py`
- Append-only implementation report: `95-implementation-evolution-and-completion-report.md`

The plan-local validator checks the compact contract subset consumed by the current Quick Dev runtime: command registry, authority manifest, slice dependencies, TDD commands, snapshot paths, read/write boundaries, freshness helpers, and adapter-owned consumption-decision coverage. The larger historical generic implementation-contract schema is a read-only migration reference, not the schema owner for this downstream plan.

## Implementation Order

`RMAP-S0 -> RMAP-S1 -> RMAP-S2 -> RMAP-S3 -> RMAP-S4 -> RMAP-S5 -> RMAP-S6 -> RMAP-S7`.

The first six slices exit at `slice-ready`. `RMAP-S6` publishes only an `implementation-candidate`. `RMAP-S7` runs the current terminal integration validator and is the only slice allowed to publish `implementation-complete`.

## Safety

All slices forbid `logs/phase-a-innernet/**`, `runtime/phase-a/**`, and `PhaseA.Platform/**`. Locator facts pin local `refs/heads/main`; dirty worktree inputs remain direct consumer artifacts or provisional maintenance candidates, never knowledge facts. No adapter may silently fetch, widen a path policy, or add context after its workflow freeze point.
