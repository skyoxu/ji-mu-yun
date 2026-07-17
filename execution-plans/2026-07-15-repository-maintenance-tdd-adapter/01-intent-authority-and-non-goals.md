# Intent, Authority, And Non-Goals

## Intent Kernel

The repository already has rigorous VDD planning and evidence-gated Bootstrap review, but it lacks a small, stable, machine-readable consumption surface between a behavior slice and an implementation agent. The missing control plane permits an implementation workflow to claim progress without proving a real RED, constraining its write set, preserving baseline identity, or separating candidate production from acceptance authority.

The plan succeeds when a repository-owned adapter can consume one implementation-contract instance, enforce the RED -> GREEN -> REFACTOR sequence, recover from hash-bound evidence, and emit a candidate envelope that can enter Bootstrap review without letting the backend review, mark done, commit, accept, or release.

## Approved Sources

| Source | Role | Bound revision |
| --- | --- | --- |
| `agentbuild.txt` | Original intent and proposed P0-P4 sequence | `sha256:1eff0054ca233d70ef00a8b5883f748a8e466e454fc9ff8f8f07a4d4f9dd8807` |
| Durable clarification projection | User-approved creation and repair boundary decisions | `schemas/clarification-decisions.v1.json` |
| `AGENTS.md` | Repository routing, evidence, protected paths, and architecture rules | Current hash in `schemas/authority-manifest.v1.json` |
| VDD strict standard | Verification authority and plan contract | `sha256:7d5a73e75a47d25d1752ce128423ff9a8e429b714439931811529603ed6b2140` |
| Accepted ADR-0041 and Bootstrap standard | Durable review control-plane ownership and semantics | Hash-bound in `schemas/authority-manifest.v1.json` |
| Repository-owned Bootstrap Skill | Executable semantic-review protocol and finalized-run validation envelope | Hash-bound implementation, schemas, profiles, and tests in `schemas/authority-manifest.v1.json` |
| 7-12 Bootstrap plan and CLI | Revision-bound compatibility adapter and migration examples only | Directory authority frozen by the implementation slice baseline |
| Round 3 blocking projection | Current semantic-review disposition and re-entry boundary | `schemas/review-blocking-state.v1.json` |

`agentbuild.txt` remains byte-preserved, committed source history. This directory hash-binds it instead of copying it into a second authority.

## Three-Layer Ownership

1. `docs/standards/` owns long-lived normative semantics.
2. The repository-owned adapter Skill owns the executable protocol, common schemas, shared validators, and run workflow.
3. Each `execution-plans/<plan>/` owns its `implementation-contract` instance, plan-specific predicates, fixtures, evidence intent, and immutable evidence references.

Mutable run state and result envelopes belong under `logs/tdd-adapter/**`, never inside an execution-plan directory.

## Framework ADR Gate

The existing Accepted [`ADR-0041 Bootstrap Review Execution Control Plane Ownership`](../../docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md) owns the shared repository control-plane ownership pattern and Bootstrap-specific execution boundary: durable semantics live in standards, executable protocol lives in a repository-owned Skill, plan-local validation owns business acceptance, and compatibility adapters do not acquire durable behavior. It does not define this TDD Adapter's RED/GREEN/REFACTOR, Capsule, attempt-ledger, candidate-diff, or S7 predecessor semantics; the new repository-maintenance standard and adapter Skill own those details.

S0 cites ADR-0041 and creates only the repository-maintenance adapter standard. It must not allocate another ADR-0041 path or duplicate Bootstrap ownership. A new ADR is permitted only if implementation discovers a distinct irreversible decision not covered by ADR-0041; that decision requires a new unused ID and cannot silently replace this plan's current authority.

## Current-State Boundary

- The 555 repair started from HEAD `6adab7f741b9080a7e14758a815d02403d13a7b2` against target hash `sha256:784b515d72a573427544e71c06587ddecf362ad8a3ffe14cc599540ec203450d` and landed in commit `3d9868dc464284ecb4f6793b51fef7874002f4ed`.
- The stabilized Bootstrap control plane, ADR, standard, and compatibility projections are committed repository-owned authority. The authority manifest binds their current bytes; 7-12 remains a revision-bound compatibility adapter only.
- Test counts are run-scoped observations, not mutable current-state authority: the 555 closure evidence recorded 48 plan tests, 87 Bootstrap Skill tests, and a passing 7-12 Whole-directory validator. Fresh commands and current envelopes supersede those historical observations.
- No BMAD `SPEC.md`, `.memlog.md`, or `ARCHITECTURE-SPINE.md` package applies to this intent.
- The finalized Round 3 Bootstrap result is `blocked` with eight confirmed P1 findings, and the review cycle is `manual_pause_after_round_3`. Deterministic repair cannot clear that semantic disposition.

## Confirmed Scope

- P0-P3 from the approved intent.
- Formal self-hosting in this new plan.
- Additive metadata backfill and non-authoritative shadow validation for exactly three existing plans, in this order: 7-12, 7-07, 7-11.
- A repository-owned Slice Capsule executor as backend v1.
- Immutable per-invocation persisted Capsule revisions and an append-only Agent Attempt Ledger.
- Existing Bootstrap extension points before any Bootstrap CLI delta.

## Non-Goals

- Removing BMAD. That is a separate P4 plan.
- Editing stock `.agents/skills/bmad-*` or `.agents/skills/gds-*` installation content.
- Modifying the 7-12 Bootstrap CLI before executable evidence proves a missing extension point.
- Changing existing old-plan books, status, validators, historical evidence, or handoff authority during shadow backfill.
- Modifying Phase protected paths, shared LLM/Codex entrypoints, runtime state, auth, Caddy, or live metadata.
- Automatically launching a provider or Codex subprocess in adapter v1.
- Adding a Router, another slice, or mutable `ledger.json` state.
- Treating confidence, assistant text, process exit, plan validation, or Bootstrap supplemental evidence as release authority.
