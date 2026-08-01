# Workflow Model Routing Control Plane Execution Plan

Status: `implementation-complete`
Profile: `self-hosted`
Plan ID: `workflow-model-routing-control-plane`
Created: 2026-08-01

## Outcome

Create one typed, evidence-producing workflow model router so VDD, Quick Dev,
and Refactor Acceptance no longer inherit one session model for every task.
Quick Dev becomes the first classified consumer. VDD reuses its existing
profiles, Refactor Acceptance reuses its deterministic next-action contract,
and Bootstrap Review retains its own model-launch authority.

The initial rollout is `observe_only`. It may classify and record a route, but
it cannot silently replace the active Codex session or launch a model until the
shared launcher, capability probe, policy validation, and caller contract all
pass.

## Profile Selection

`self-hosted` is the least sufficient profile because this work changes VDD,
Quick Dev, Refactor Acceptance routing, a shared LLM/Codex entrypoint, and
controlling validators. The work has dependent slices and may cross sessions,
so resume state and an indexed append-only 95 report are required.

## Authority And Decisions

- Repository rules: `AGENTS.md`.
- Product and toolchain boundary: `README.md`.
- Shared Phase LLM/Codex entrypoint: ADR-0037 and
  `docs/architecture/phase-service/llm-codex-execution.md`.
- Bootstrap ownership: ADR-0041 and
  `docs/standards/bootstrap-review-control-plane.md`.
- VDD lifecycle and clarification: ADR-0043 and the VDD Skill references.
- Repository maintenance ownership:
  `docs/standards/repository-maintenance-agent-protocol.md`.
- Knowledge selection: ADR-0048 and the frozen plan-owned knowledge context.

An Accepted ADR is required before active model routing changes provider,
reasoning, fallback, or execution ownership. The implementation may extend
ADR-0037 or add a narrower accepted ADR; it must not rely on a Proposed ADR.

## Current-State Constraints

1. VDD already selects `standard`, `resumable`, or `self-hosted`; no second VDD
   complexity classifier is added.
2. Quick Dev has no `small_mechanical`, `normal`, `complex`, or
   `architectural` classifier today.
3. The Quick Dev adapter is backend-neutral and cannot schedule providers. It
   may emit a route decision; a shared launcher must execute it.
4. Refactor Acceptance orchestration is deterministic. Only a typed complex
   recovery action may request a model child.
5. Bootstrap Review owns its model profiles, per-role access proof, and model
   launches. This plan must not override or normalize those profiles.
6. The current shared Python backend accepts explicit model IDs but its
   reasoning parser does not yet accept `xhigh` or `max`.
7. The relevant worktree is dirty. Existing Bootstrap and Refactor Acceptance
   changes are user-owned external dependencies and must be refrozen before an
   implementation slice touches an overlapping file.
8. `scripts/sc/_llm_backend.py` is protected. Implementation requires explicit
   user approval immediately before modifying it.

## Scope

Expected implementation surfaces:

- A versioned workflow model-routing policy, schema, classifier, decision
  envelope, and shared launcher under `scripts/sc/`.
- Shared backend support and tests only where the new launcher needs behavior
  that `run_llm_exec` cannot currently express.
- Quick Dev typed classification and route-decision integration.
- VDD profile-to-route projection without changing VDD profile selection.
- Refactor Acceptance complex-recovery projection without adding LLM work to
  deterministic orchestration.
- Skill instructions, accepted ADR/standards, migration notes, and evaluation
  evidence required by the executable behavior.

Out of scope:

- Replacing the model of an already-running root Codex session.
- Phase browser/API model selection, `/ui-v2`, or hosted project route changes.
- Auth, metadata DB, Caddy, runtime scripts, live workspaces, or live evidence.
- Rewriting Bootstrap Review model policy or its in-progress worktree changes.
- Enabling Luna or Sol/max without capability and shadow evidence.
- A hidden provider scheduler, automatic fallback loop, or cost-only downgrade.

## Initial Policy

The executable registry uses full model IDs. Short names are display labels
only.

| Consumer route | Initial decision |
| --- | --- |
| VDD `standard` | `gpt-5.6-sol`, `high` |
| VDD `resumable` | `gpt-5.6-sol`, `high` |
| VDD `self-hosted` | `gpt-5.6-sol`, `high` |
| VDD typed complex recovery | capability-gated `gpt-5.6-sol`, `max` |
| Quick Dev `small_mechanical` | `gpt-5.6-terra`, `medium`; Luna shadow candidate only |
| Quick Dev `normal` | `gpt-5.6-terra`, `medium` |
| Quick Dev `complex` | `gpt-5.6-terra`, `high` |
| Quick Dev `architectural` | `gpt-5.6-sol`, `high` |
| Refactor Acceptance normal orchestration | deterministic; no model launch |
| Refactor Acceptance typed complex recovery | `gpt-5.6-sol`, `high` |
| Bootstrap Review | external Bootstrap profile; router cannot override |

`max` is an escalation, not a default. Luna remains unavailable for active
routing until the exact execution surface proves support and representative
shadow tasks pass their predicates.

## Quick Dev Classification

The classifier consumes typed facts, not free-form model confidence. It selects
the highest matching class and records every trigger.

- `architectural`: any ADR/invariant, public API, DB/schema, auth/security,
  runtime/deployment, shared LLM entrypoint, protected path, or workflow
  control-plane ownership change.
- `complex`: no architectural trigger, but cross-module consumers, state or
  recovery semantics, concurrency/idempotency, multiple production write
  roots, or an unresolved behavioral boundary exists.
- `small_mechanical`: no higher trigger, the transform is deterministic, the
  behavior is already specified, at most one production root and one matching
  test root change, and no new contract or dependency is introduced.
- `normal`: every remaining bounded implementation task.

Unknown or contradictory facts route upward and emit a blocking reason. A user
may force an upgrade. A downgrade cannot clear a protected, architectural, or
unresolved-boundary trigger.

## Slices

### RMR-S0 - Decision And Policy Kernel

Define and accept routing ownership, the closed route vocabulary, classification
precedence, model/effort registry, rollout modes, override rules, and the
non-authorizing decision envelope.

- RED: policy tests reject the current absence of a canonical registry and
  decision schema.
- GREEN: policy/schema tests accept all declared routes and reject ambiguous,
  short-name, silent-fallback, and unsafe-downgrade cases.
- Dependents: RMR-S1 through RMR-S4.
- Recovery: revert only the new policy/ADR layer; no caller behavior has changed.

### RMR-S1 - Shared Launcher And Capability Boundary

Add one shell-free launcher that consumes a validated decision, delegates to
`run_llm_exec`, records requested and actual model/effort identity, and fails
closed on unsupported capabilities. Extend the protected backend only after
explicit approval and only for required effort/model transport.

- RED: backend/launcher tests fail for unsupported `max`, invalid model IDs,
  missing probes, and requested/actual identity drift.
- GREEN: shared backend plus launcher tests pass for supported routes while
  preserving UTF-8 stdin, sandbox, secrets, and no hidden fallback.
- Depends on: RMR-S0.
- Dependents: RMR-S2 through RMR-S4.
- Recovery: disable active launch mode and retain observe-only decisions.

### RMR-S2 - Quick Dev Four-Class Router

Implement deterministic highest-match classification and integrate its decision
with the Quick Dev execution boundary without giving the adapter provider
scheduling authority.

- RED: classifier tests demonstrate missing architectural escalation, ambiguous
  upward routing, downgrade rejection, and normal/mechanical separation.
- GREEN: all four classes, override rules, protected-path escalation, and
  route-decision evidence pass.
- Depends on: RMR-S0 and RMR-S1.
- Dependents: RMR-S3 and RMR-S4.
- Recovery: disable the Quick Dev consumer and continue with the caller session
  model; existing TDD predicates remain authoritative.

### RMR-S3 - VDD And Acceptance Consumers

Project existing VDD profiles into the policy and add only typed complex-repair
escalation. Keep normal Refactor Acceptance deterministic; allow a model child
only for a closed complex-recovery trigger set. Preserve Bootstrap ownership.

- RED: integration tests fail when VDD profile identity, Acceptance next-action,
  Bootstrap policy, or frozen knowledge context can be overridden.
- GREEN: both consumers emit current, hash-bound decisions and all authority
  boundaries remain intact.
- Depends on: RMR-S0 through RMR-S2.
- Dependents: RMR-S4.
- Recovery: disable each consumer independently; do not rewrite historical runs.

### RMR-S4 - Shadow Evaluation, Migration, And Terminal Replay

Run representative classification and execution shadows, publish no active Luna
or Sol/max route without capability evidence, update documentation, and execute
one terminal full validation after all targeted checks stabilize.

- RED: evaluation fixtures reject unsupported or predicate-regressing routes.
- GREEN: required cohorts meet declared correctness, latency, cost, and task
  predicate criteria; unsupported routes remain explicitly disabled.
- Depends on: RMR-S0 through RMR-S3.
- Recovery: keep `observe_only`, preserve evidence under `logs/`, and defer
  activation without blocking deterministic toolchain use.

## Validation

Targeted commands are registered in `requirements.v1.json`. At minimum:

- VDD contract and knowledge tests.
- Quick Dev adapter, routing, and new classifier tests.
- Shared Python LLM backend and launcher tests.
- Refactor Acceptance routing tests.
- Bootstrap regression tests proving the shared router cannot override its
  profile-owned model decisions.
- Skill quick validation for every changed Skill.

The one plan-source terminal command is:

```powershell
py -3 execution-plans/2026-08-01-workflow-model-routing-control-plane/tools/validate_plan.py
```

Implementation completion requires a later terminal command that runs every
registered targeted suite plus an end-to-end observe-only replay. Targeted
checks alone cannot publish `implementation-complete`.

## Lifecycle And Authorization

This directory currently publishes only `plan-ready`. The maintainer must
explicitly publish `implementation-authorized`. That authorization does not
authorize protected backend edits until the user separately approves the exact
protected path, and it never implies acceptance, release, or archive.

Bootstrap Review is supplemental. If requested for implementation conformance,
use one stable lineage family derived from this plan target, require a current
zero-or-more-round lineage projection, and retain the two-round default and
three-round hard limit.
