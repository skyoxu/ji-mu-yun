# Refactor Acceptance Toolchain And Compact VDD Execution Plan

Status: `implementation-complete`
Profile: `self-hosted`
Plan ID: `refactor-acceptance-toolchain-compact-vdd`
Created: 2026-08-01

## Outcome

Extend Refactor Acceptance so a repository workflow control-plane candidate
can be reviewed as `toolchain`, including explicitly declared shared Phase
entrypoints, without disguising the candidate as Phase-only or leaving the
toolchain partition unreviewed. Add one deterministic compact-VDD prerequisite
projector so a completed compact plan can produce the contract, manifests,
action DAG, command registry, frozen dirty candidate, and run request required
before `start-or-resume`.

The first real consumer is
`execution-plans/2026-08-01-workflow-model-routing-control-plane/`. Its
Acceptance run begins only after this plan's terminal validation passes.

## Profile

`self-hosted` is required because this changes the Refactor Acceptance domain
policy, its run-input contract, package closure, Skill instructions, and the
prerequisite routing that previously failed closed.

## Invariants

1. `phase_service` remains backward compatible and keeps its current policy.
2. `toolchain` uses a separate versioned policy and closed path classification.
3. A shared Phase entrypoint is included in a toolchain candidate only through
   an explicit cross-domain dependency rule and remains visible in evidence.
4. No path may disappear into an unreviewed partition when the selected policy
   claims complete candidate coverage.
5. Compact projection consumes one explicit completed VDD directory, current
   Git identity, exact changed paths, registered commands, and current bytes.
   It never infers a candidate from all dirty worktree paths.
6. Dirty candidates are copied into a target-owned frozen snapshot before a
   run request is prepared.
7. Generated prerequisite artifacts carry `authorizes=[]`; only the existing
   Acceptance lifecycle may publish `acceptance-passed`.
8. Bootstrap retains semantic review, model launch, lineage, and cost
   acknowledgement authority.

## Scope

- Generalize policy pack and run-input validation for `phase_service` and
  `toolchain` without renaming existing public commands.
- Add `policies/toolchain-code-review.v1.json` and deterministic path coverage.
- Add a reusable compact-VDD prerequisite projector and detached tests.
- Update the Acceptance package, Skill instructions, schemas, Accepted ADR,
  and migration behavior.
- Re-run the original workflow model routing terminal validator after the
  Acceptance package is stable.

Out of scope: Phase browser/API behavior, live workspaces, Bootstrap model
profiles, automatic candidate discovery, arbitrary multi-domain policy union,
commit/release, and retroactive mutation of historical Acceptance runs.

## Slices

### RA-TC-S0 - Toolchain Domain Policy

- RED: toolchain policy and mixed control-plane candidate tests are absent.
- GREEN: policy, run-input, binding, unsupported-domain, complete-coverage,
  and Phase compatibility tests pass.
- Recovery: disable only the toolchain policy; Phase behavior remains current.

### RA-TC-S1 - Compact VDD Prerequisite Projection

- RED: no deterministic projector can build the required prerequisite bundle.
- GREEN: detached fixtures prove explicit changed-path projection, baseline and
  candidate manifests, dirty snapshot custody, action/command closure, and
  refusal of ambiguous or unrelated dirty paths.
- Depends on: RA-TC-S0.
- Recovery: remove the projector; existing full-contract plans remain valid.

### RA-TC-S2 - Migration And Terminal Replay

- RED: package closure and Skill instructions do not expose the new route.
- GREEN: all Acceptance tests, Skill validation, projection replay, and the
  original workflow model routing terminal validator pass.
- Depends on: RA-TC-S0 and RA-TC-S1.
- Recovery: preserve generated evidence, disable the new route, and keep the
  original target at `implementation-complete`.

## Lifecycle

This directory initially authorizes only `plan-ready`. The user's agreement to
the stated extension may publish `implementation-authorized` after the plan,
knowledge context, and dirty baseline validate. Target Acceptance remains a
separate later transition.
