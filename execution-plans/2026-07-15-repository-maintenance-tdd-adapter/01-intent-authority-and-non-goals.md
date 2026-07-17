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

`agentbuild.txt` remains byte-preserved source history. It must be included in the eventual plan commit; this directory does not copy it into a second authority.

## Three-Layer Ownership

1. `docs/standards/` owns long-lived normative semantics.
2. The repository-owned adapter Skill owns the executable protocol, common schemas, shared validators, and run workflow.
3. Each `execution-plans/<plan>/` owns its `implementation-contract` instance, plan-specific predicates, fixtures, evidence intent, and immutable evidence references.

Mutable run state and result envelopes belong under `logs/tdd-adapter/**`, never inside an execution-plan directory.

## Framework ADR Gate

The existing Accepted [`ADR-0041 Bootstrap Review Execution Control Plane Ownership`](../../docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md) owns the irreversible control-plane boundary used by this plan: durable semantics live in standards, executable review protocol lives in the repository-owned Skill, plan-local validation owns business acceptance, and compatibility adapters do not acquire durable behavior.

S0 cites ADR-0041 and creates only the repository-maintenance adapter standard. It must not allocate another ADR-0041 path or duplicate Bootstrap ownership. A new ADR is permitted only if implementation discovers a distinct irreversible decision not covered by ADR-0041; that decision requires a new unused ID and cannot silently replace this plan's current authority.

## Current-State Boundary

- Current 555 repair baseline: HEAD `6adab7f741b9080a7e14758a815d02403d13a7b2`; the pre-repair 7-15 target hash was `sha256:784b515d72a573427544e71c06587ddecf362ad8a3ffe14cc599540ec203450d`.
- The stabilized 7-12 Bootstrap control-plane bytes and their AGENTS/README/ADR/standard projections remain separate uncommitted upstream changes. This repair may hash-bind them for discovery but does not absorb their commit ownership; clean-checkout proof still requires those bytes to exist in their owning commit or equivalent clean snapshot.
- The VDD Skill baseline passed 46 tests.
- The pre-repair Bootstrap baseline passed 84 tests, the repaired control plane passes 87 tests, and the 7-12 Whole-directory validator passes.
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
