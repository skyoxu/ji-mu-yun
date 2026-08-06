# Toolchain Plan Delivery Loop Skill

- Status: `plan-ready`
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

The coordinator is a same-session harness adapter. It computes one typed next
action from current owner-produced evidence, invokes the owning Skill, then
re-inspects. It does not replace VDD, Bootstrap, Quick Dev, or Acceptance and
does not publish their lifecycle states.

## Background Watchdog Decision

Do not create the proposed three-minute background process. A detached process
cannot safely revive a Codex conversation, infer Skill activity from process
names, acknowledge an unknown high-cost estimate, or bypass Bootstrap's
event-backed process ownership. It would also introduce a second controller and
duplicate state authority.

Use an invocation-driven recovery design instead:

- Rebuild current state from the target plan, owner-produced run evidence,
  Bootstrap process events, Quick Dev run state, and Acceptance run state.
- Persist only a compact, non-authorizing checkpoint under `logs/` for fast
  context-compaction recovery.
- Before dispatching any action, call the owning control plane's read-only
  inspect/resume path and reject a live or conflicting controller.
- If the Codex session or host process ends, the next explicit Skill invocation
  resumes from evidence. No external daemon launches a model or mutates a plan.

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

This directory is `plan-ready`. Bootstrap review is required by this plan as
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

- Plan-ready: `py -3 -B execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/tools/validate_plan.py`
- Plan validator tests: `py -3 -B -m unittest discover -s execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/tools/tests -p test_validate_plan.py`
- Current negative implementation predicate: `py -3 -B execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/tools/validate_implementation.py`
- Future terminal implementation predicate: the same implementation command, after all slices and current full validation complete.

