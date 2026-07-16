# Intent, Authority, And Non-Goals

## Intent Kernel

The repository already has rigorous VDD planning and evidence-gated Bootstrap review, but it lacks a small, stable, machine-readable consumption surface between a behavior slice and an implementation agent. The missing control plane permits an implementation workflow to claim progress without proving a real RED, constraining its write set, preserving baseline identity, or separating candidate production from acceptance authority.

The plan succeeds when a repository-owned adapter can consume one implementation-contract instance, enforce the RED -> GREEN -> REFACTOR sequence, recover from hash-bound evidence, and emit a candidate envelope that can enter Bootstrap review without letting the backend review, mark done, commit, accept, or release.

## Approved Sources

| Source | Role | Bound revision |
| --- | --- | --- |
| `agentbuild.txt` | Original intent and proposed P0-P4 sequence | `sha256:1eff0054ca233d70ef00a8b5883f748a8e466e454fc9ff8f8f07a4d4f9dd8807` |
| Closed VDD clarification state | User-approved boundary decisions | `sha256:21da9212cdeb767c579dcdad6e374cba01d81d63563064724335e7016a85a0ec` |
| `AGENTS.md` | Repository routing, evidence, protected paths, and architecture rules | `sha256:304d18663634225834f6724073eef77979d138548b7af75a74c4615e8d68a68e` |
| VDD strict standard | Verification authority and plan contract | `sha256:7d5a73e75a47d25d1752ce128423ff9a8e429b714439931811529603ed6b2140` |
| 7-12 Bootstrap plan and CLI | Current semantic-review extension boundary | Directory authority frozen by the implementation slice baseline |

`agentbuild.txt` remains byte-preserved source history. It must be included in the eventual plan commit; this directory does not copy it into a second authority.

## Three-Layer Ownership

1. `docs/standards/` owns long-lived normative semantics.
2. The repository-owned adapter Skill owns the executable protocol, common schemas, shared validators, and run workflow.
3. Each `execution-plans/<plan>/` owns its `implementation-contract` instance, plan-specific predicates, fixtures, evidence intent, and immutable evidence references.

Mutable run state and result envelopes belong under `logs/tdd-adapter/**`, never inside an execution-plan directory.

## Framework ADR Gate

Before implementation, one framework-level ADR named `Repository Maintenance Agent Protocol Ownership` must be accepted. It records:

- why a top-level Router is rejected;
- why document protocols and a stateless adapter are selected;
- the three-layer ownership model;
- why plan-local validation owns implementation acceptance;
- why an implementation backend cannot own review, `done`, commit, acceptance, or release;
- why new capability is not added to historical script directories.

Ordinary execution plans cite this ADR. They do not create one ADR per plan. Only a change to these framework decisions requires supersession.

## Current-State Boundary

- Git baseline at clarification exit: HEAD `48e7b21e6cf33f30aca7c8ac2f3b2fa63b784fe7`, index tree `27317fd610bcd5f044815436c0de6c023ab34321`.
- The only pre-existing dirty item was untracked `agentbuild.txt`.
- The VDD Skill baseline passed 46 tests.
- The Bootstrap baseline passed 62 tests, and the 7-12 Whole-directory validator passed.
- No BMAD `SPEC.md`, `.memlog.md`, or `ARCHITECTURE-SPINE.md` package applies to this intent.

## Confirmed Scope

- P0-P3 from the approved intent.
- Formal self-hosting in this new plan.
- Additive metadata backfill and non-authoritative shadow validation for exactly three existing plans, in this order: 7-12, 7-07, 7-11.
- A repository-owned Slice Capsule executor as backend v1.
- Existing Bootstrap extension points before any Bootstrap CLI delta.

## Non-Goals

- Removing BMAD. That is a separate P4 plan.
- Editing stock `.agents/skills/bmad-*` or `.agents/skills/gds-*` installation content.
- Modifying the 7-12 Bootstrap CLI before executable evidence proves a missing extension point.
- Changing existing old-plan books, status, validators, historical evidence, or handoff authority during shadow backfill.
- Modifying Phase protected paths, shared LLM/Codex entrypoints, runtime state, auth, Caddy, or live metadata.
- Automatically launching a provider or Codex subprocess in adapter v1.
- Treating confidence, assistant text, process exit, plan validation, or Bootstrap supplemental evidence as release authority.
