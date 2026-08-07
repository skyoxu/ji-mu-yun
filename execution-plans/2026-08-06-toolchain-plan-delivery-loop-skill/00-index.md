# Toolchain Plan Delivery Loop Skill

- Status: `implementation-authorized`
- Profile: `self-hosted`
- Profile reason: this plan adds an opt-in Skill that coordinates three existing Toolchain control planes and therefore changes workflow-control behavior.
- Plan ID: `toolchain-plan-delivery-loop-skill`
- Target Skill: `orchestrate-plan-delivery`
- Git baseline: `8c47a52fc8f241f76da9ccb5d936b0fafe807f0f`
- Baseline tree: `6963a7c3ef477ddabd0acd9459d268a8f2ceb982`
- Current step: run a `bootstrap-upstream-plan` review over this directory, repair through VDD when required, then obtain explicit maintainer implementation authorization.
- Recovery command: `py -3 -B execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/tools/validate_plan.py`

## Outcome

Create one repository-local Skill that accepts exactly one existing
`execution-plans/<target>` directory and coordinates its delivery through:

1. Bootstrap upstream-plan review and VDD-owned plan repair.
2. Explicit maintainer publication of `implementation-authorized`.
3. Quick Dev TDD implementation until `implementation-complete`.
4. Refactor Acceptance orchestration, including its bounded Bootstrap and
   Quick Dev repair routes, until `acceptance-passed`.

The coordinator is an opt-in harness adapter. It computes one typed next action
from current owner-produced evidence, invokes the owning Skill, then
re-inspects. Its normal loop may remain in the current session; hook-triggered
recovery uses the explicit fresh-session launcher. It does not replace VDD,
Bootstrap, Quick Dev, or Acceptance and does not publish their lifecycle states.

## Post-Run Hook And Recovery Decision

Do not create the proposed three-minute background process. The coordinator
uses one explicit, project-local, auditable post-run hook. The hook belongs only
to this coordinator; the Bootstrap, Quick Dev, and Acceptance Skills do not
attach it.

The hook runs for controlled completion, controlled failure, timeout, or a
reported poll-stop. It is suppressed for an explicit user-stop and for
manual-pause. It reads only schema-valid filesystem events, current state,
owner evidence, and a hash-bound checkpoint. It has no lifecycle publication
authority and is idempotent by `plan_id:run_id:stop_epoch`.

Hook recovery requests an explicit project-local fresh-session launcher. The
launcher reads structured state and does not assume a global `/new` command or
inherit the previous conversation. Process kill and machine power loss remain
outside this plan's recovery guarantee.

The coordinator loop is filesystem-backed and follows:

`recover -> plan -> execute -> verify -> iterate`

Each stage persists an append-only event and checkpoint. Route selection uses
typed validator predicates and owner evidence only. Coordinator actions require
stable idempotency keys and journaled or owner-declared rollback boundaries.
Terminal exit requires typed terminal predicates, declared closure, and the
owner-published terminal state; intermediate success never converges the loop.

## Authority Boundaries

- Bootstrap findings already require `confidence` in `[0.8, 1.0]`; the new
  Skill consumes that value and never invents a parallel confidence score.
- Bootstrap evidence never publishes plan or implementation lifecycle state.
- VDD owns plan intent and plan repair. The maintainer owns explicit
  implementation authorization. Quick Dev owns only `implementation-complete`.
  Refactor Acceptance owns only `acceptance-passed`.
- Ordinary in-scope work may continue under the user's explicit invocation.
  High-cost model launch, later finding-mode re-entry, protected-path changes,
  and manual-pause closure retain their current typed confirmation boundaries.
- The coordinator never modifies the three child Skill packages or their
  historical evidence. A missing public child operation fails closed and must
  be added through a separately authorized owner change.

## Scope

- `.agents/skills/orchestrate-plan-delivery/**`.
- A deterministic target-path guard, evidence reader, next-action router, and
  non-authorizing checkpoint writer.
- Detached fixtures for path containment, lifecycle ownership, interrupted
  work, active child processes, context compaction, review repair, Quick Dev
  completion, Acceptance repair, and terminal acceptance.
- ADR-0059 and the architecture index entry defining the opt-in coordinator
  boundary.
- Plan-local validators, TDD slices, and recovery evidence.

Out of scope: a repository-global `toolchain` CLI, Phase browser/API routing,
live runtime or hosted workspaces, automatic protected-path approval, silent
high-cost acknowledgement, automatic later-round discovery confirmation,
process-name polling, scheduled tasks, services, watchdogs, commit, release,
deployment, and archive.

## Lifecycle

The lifecycle remains:

`draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`

This directory is `implementation-authorized`. Bootstrap review is required by this plan as
supplemental evidence before the maintainer may authorize implementation, but
Bootstrap does not publish that state.

## Implementation Order

`RMAP-S0 -> RMAP-S1 -> RMAP-S2 -> RMAP-S3`

- `RMAP-S0`: accepted ownership ADR, Skill package skeleton, schemas, and RED fixtures.
- `RMAP-S1`: deterministic path guard, evidence projection, and compact recovery checkpoint.
- `RMAP-S2`: owner-preserving orchestration loop, authorization stops, and repair routing.
- `RMAP-S3`: detached composition/forward tests, package validation, documentation bindings, and terminal closure.

Only `RMAP-S3` may publish `implementation-complete`, and only after the
terminal implementation validator passes. Refactor Acceptance remains a
separate post-implementation lifecycle owner.

## Validation

- Implementation-authorized: `py -3 -B execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/tools/validate_plan.py --implementation-state`
- Plan validator tests: `py -3 -B -m unittest discover -s execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/tools/tests -p test_validate_plan.py`
- Current negative implementation predicate: `py -3 -B execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/tools/validate_implementation.py`
- Future terminal implementation predicate: the same implementation command, after all slices and current full validation complete.
