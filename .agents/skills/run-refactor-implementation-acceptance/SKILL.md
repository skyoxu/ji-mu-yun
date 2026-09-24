---
name: run-refactor-implementation-acceptance
description: Build, resume, and route deterministic implementation-acceptance evidence for one explicit Phase-service or repository-toolchain refactor plan, including compact-VDD prerequisite projection, bounded Bootstrap review handoff, and exact finalized-run reuse.
---

# Refactor Implementation Acceptance

This Skill builds deterministic implementation-acceptance evidence for exactly
one explicit target plan. It does not implement target code, approve a review,
authorize a protected handoff, commit, release, or deploy. It may route to the
Bootstrap Skill, but Bootstrap retains model launch, high-cost acknowledgement,
and review-lifecycle ownership.

## Read By Operation

| Operation | Required guidance |
| --- | --- |
| First acceptance or deterministic prerequisite rebuild | [Prepare and run](references/prepare-and-run.md), including mandatory Knowledge and live Skill-input v2 validation |
| Resume an explicit existing request | Coordinator entry below; read [prepare and run](references/prepare-and-run.md) only when inputs must be rebuilt |
| Inspect completion, blockers or support output | [Operator results](references/operator-results.md); inspection does not authorize execution or retry |
| Explicit Bootstrap request or recovery of its existing lineage | [Bootstrap operations](references/bootstrap-operation.md), after deterministic prerequisites |
| Skill maintenance | Affected operation guides and package validation below |

Do not load every operation guide by default. Before transitioning to another operation, read that guide. Persisted evidence and current binding checks remain mandatory regardless of how much guidance is loaded.

## Completion And Stop Conditions

For execution requests, own coordination until a terminal result or typed acknowledgement/protected boundary is reached. Missing, failed or stale required receipts block finalization. Q8 success and Bootstrap clean alone cannot grant Acceptance success. Only the Acceptance-owned final predicate may publish `acceptance-passed`; evidence-only output remains non-authorizing. Preserve historical inputs and recover only from explicit bound requests.

Bootstrap is explicit-only: only `maintainerIntent=request` can require review. Risk classification alone cannot start it, and incomplete deterministic evidence cannot be replaced by review.

## Modes

- `evidence_only` is the default. It reads current manifests and evidence and may only produce non-authorizing candidate conclusions.
- `controlled_validation` is available only after the caller supplies typed commands and isolated write roots. It cannot write target production code, live Phase state, workspaces, or historical evidence.

## Model Route Decision

Keep every ordinary Acceptance next action deterministic and pass it through
`scripts/model_routing.py` as the no-launch route. Request `gpt-6-sol/high` only when
the current failure matches one policy-owned complex-recovery trigger:
Bootstrap control-plane unavailable, candidate-binding recovery failed, or
lineage evidence inconsistent. Reject free-form recovery reasons. Do not use a
model child for routine evidence collection, routing, replay, or finalization.

The route decision is hash-bound and non-authorizing. The shared workflow
launcher alone may start the child; this Skill does not call it from its
deterministic CLI. In `observe_only`, no child starts and the current caller
session model is unchanged. Bootstrap profile, round, verifier, effort, access
proof, and launch authority remain external to this router.

The canonical policy owns Refactor Acceptance's independent consumer
enablement. Disabling this consumer does not disable VDD or Quick Dev. The
shared launcher revalidates the canonical policy before execution and rejects
caller-supplied policy substitutions; any capability-gated route must replay
policy-bound producer and representative execution receipts.

## Current Coordinator Entry

Use `acceptance_cli.py run-coordinator --request <request> --out <result>`.
The `jimuyun.acceptance-coordinator-request.v3` contains `targetPlan`, hash-bound
`preparedRunInput`, `skillInputReceipt`, `skillInputContract`, and `authorizes=[]`.
References are relative to the request directory. The prepared input comes from
`prepare-run`, using the projection's prerequisite bundle and its knowledge
context. The Coordinator validates the real ready gate and copies that prepared
input into its binding-derived persisted run. It reads actions and commands
from the bound bundle, not caller route or action overrides.

Identical reentry revalidates Q8, candidate custody, Skill input, action events,
receipts and finalization. A failed registered action stops after that attempt;
a waiting result does not authorize an automatic retry. Stale/incomplete proof
requires explicit recovery or a new bound input; historical artifacts remain.
For an explicit user request for Bootstrap only, set `maintainerIntent=request`.
That returns a typed handoff without executing the DAG or launching Bootstrap.
Omission means `default`, which uses deterministic Acceptance.

## Repository-Owned Package Validation

Use this repository-owned command for Skill package validation:

```text
py -3 -B scripts/sc/skill_package_replay.py validate-package --target .agents/skills/run-refactor-implementation-acceptance --capability scripts/sc/config/skill-package-validator-capability.v1.json
```

