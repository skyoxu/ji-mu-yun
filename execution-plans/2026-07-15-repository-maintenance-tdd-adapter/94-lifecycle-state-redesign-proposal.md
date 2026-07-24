# Lifecycle State Redesign Proposal

Status: proposed, non-authoritative until the affected contracts, schemas, validators, fixtures, and tests are implemented and pass.

## Purpose

This proposal separates plan readiness, implementation authorization, implementation completion, final acceptance, and archival. It corrects the current S7 coupling in which a Bootstrap Review envelope is treated as a direct prerequisite for a plan-local implementation-acceptance predicate.

Bootstrap Review remains supplemental semantic-review evidence. It does not itself accept an implementation, grant a handoff, grant release, or write a plan lifecycle state.

## Target Lifecycle

```text
draft
  -> plan-ready
  -> implementation-authorized
  -> implementation-complete
  -> acceptance-passed
  -> archived
```

The lifecycle has exactly one owner for each transition.

| Transition | Required evidence | Transition owner | Explicit exclusions |
| --- | --- | --- | --- |
| `draft -> plan-ready` | Current composite plan validation and negative/mutation evidence | plan-local VDD validator | implementation authorization, completion, acceptance, handoff, release, archive |
| `plan-ready -> implementation-authorized` | Either three current finalized Bootstrap rounds with no accepted P0/P1, or a current explicit user-confirmed override | plan-local implementation-authorization validator | implementation completion, acceptance, handoff, release, archive |
| `implementation-authorized -> implementation-complete` | Current Quick Dev TDD terminal predicate, candidate lineage, declared tests, and implementation evidence | Quick Dev consumed plan-local terminal validator | acceptance, handoff, release, archive |
| `implementation-complete -> acceptance-passed` | Current acceptance matrix, phase gates, required runtime evidence, and conditionally required Bootstrap evidence | `run-refactor-implementation-acceptance` | handoff, release, archive |
| `acceptance-passed -> archived` | Knowledge-base impact analysis, required documentation updates, and archival checks | future archive Skill | handoff or release unless separately declared |

`protected-handoff` and `release-ready` remain separate downstream authorities. None of the transitions above authorizes either one.

## Implementation Authorization

### Bootstrap path

The normal authorization path requires three sequential, finalized Bootstrap Review runs for one `changeId` and one contiguous candidate lineage. A later round may review a changed candidate only through the current repair closure that binds the exact predecessor finding set and repair evidence. It must not reuse a stale earlier envelope as proof for the later candidate.

Each run must have:

- complete required discovery layers;
- no accepted P0 or P1 finding;
- complete disposition for every accepted P2 finding;
- a current finalized-run validation envelope;
- a valid predecessor/repair closure when it is a later review round.

The third envelope must bind the final candidate. The authorization validator must verify the entire three-round lineage, and must reject a missing round, a changed `changeId`, a broken predecessor closure, a stale envelope, or an accepted P0/P1 in any round.

The plan-local authorization validator consumes the three envelopes and publishes the `implementation-authorized` result. Bootstrap Review only produces supplemental evidence and never publishes this state directly.

### Explicit user-confirmed override

To avoid forcing repeated high-cost semantic review, a user may explicitly authorize implementation after `plan-ready` without the three Bootstrap rounds. The override must be represented by a versioned, hash-bound transition input produced outside the plan directory and every Quick Dev declared write root. The plan-local validator may consume this input but must never create, update, or select it.

The input must contain:

- current plan, source, candidate, validator, and authority-root hashes;
- the stable transition name `implementation-authorized`;
- an explicit user confirmation reference and confirmation hash from a controlled operator interaction;
- a declared reason, risk acknowledgement, operator identity, timestamp, and expiry/recheck condition;
- `authorization_mode: user-confirmed-override`.

The input records `assurance: operator-confirmed-override`; it must not claim independent-review, verifier, release, or protected-handoff assurance. The override is narrow: it authorizes Quick Dev implementation only. It does not make Bootstrap clean, does not satisfy a future acceptance matrix, and does not authorize `acceptance-passed`, protected handoff, release, or archive. Any relevant hash change invalidates it.

## 7-15 Migration

### S7 contract

Replace the current S7 terminal predicate `implementation-accepted` with `implementation-complete`.

S7 must verify the current S6 candidate, full candidate lineage, required TDD stage evidence, current validator/authority roots, and handoff-input construction. It must produce a schema-validated, non-authorizing `acceptance-handoff` artifact for the future acceptance Skill.

S7 must not require a Bootstrap run, verifier output, P2 disposition, or Bootstrap finalized envelope. Those are conditionally consumed later by the acceptance Skill, which owns the decision whether Bootstrap is required for its acceptance scope.

The S7 result must explicitly exclude `acceptance-passed`, `protected-handoff`, `release-ready`, and `archived`. Until the acceptance Skill and its validator exist, this handoff cannot be interpreted as an acceptance result and the lifecycle stops at `implementation-complete`.

### Historical rule

7-15 implementation began before this lifecycle protocol existed. No historical Bootstrap evidence may be rewritten or represented as an implementation-preauthorization proof.

Add an append-only migration sidecar with `pre_implementation_authorization: legacy-not-retroactive` and `authorizes: []`. It requires its own schema, a single registered producer, a validator rule, and negative fixtures proving that it cannot satisfy `implementation-authorized` or any downstream acceptance transition. This permits recording `implementation-complete` under the revised contract, but it never claims that 7-15 met the new pre-implementation authorization rule.

## VDD Skill Upgrade

VDD must require every newly created execution-plan directory to define:

- the six top-level lifecycle states and their exact transition graph;
- one owner, one composite predicate, exact `authorizes`, and exact `does_not_authorize` for each transition;
- an implementation-authorization policy with both the Bootstrap and user-confirmed-override paths;
- a Quick Dev terminal predicate limited to `implementation-complete`;
- an acceptance handoff artifact consumed only by the acceptance Skill;
- an archive handoff artifact consumed only by the archive Skill;
- stale-input, wrong-owner, skipped-Bootstrap, invalid-override, and premature-transition negative fixtures.

VDD must reject a plan if Quick Dev can emit `acceptance-passed`, if Bootstrap can directly emit a plan state, if an override is inside a plan or Quick Dev write root, if an override authorizes more than implementation, if a three-round lineage has stale or unbound envelopes, if a migration marker authorizes a transition, or if archive can occur before acceptance.

Required VDD package updates include `SKILL.md`, the strict VDD standard, the package contract, lifecycle schemas/templates, deterministic fixtures, and contract-validation tests.

## Delivery Order

1. Add the lifecycle vocabulary, schema, ownership rules, and negative fixtures to VDD.
2. Update 7-15 contracts, S7 command descriptors, validators, tests, projections, and lifecycle documentation.
3. Add the non-authorizing historical migration sidecar for 7-15.
4. Run the changed VDD package tests and the complete 7-15 deterministic validator suite.
5. Re-run S7 only under the revised `implementation-complete` contract.
6. Create and implement the acceptance Skill separately; it consumes the S7 handoff and independently decides whether Bootstrap evidence is required.
