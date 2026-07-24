# Lifecycle State Contract

Every newly created VDD execution-plan directory must declare this ordered top-level lifecycle:

```text
draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived
```

Each transition has one declared producer, one registered predicate, current hash-bound inputs, and exact `authorizes` and `does_not_authorize` sets. A lower transition never implies a higher one.

## Implementation Authorization

Implementation begins only after `implementation-authorized`. A plan supports exactly two authorization modes:

- `bootstrap-three-rounds`: three finalized Bootstrap envelopes for one `changeId` and contiguous candidate lineage; later candidates must bind the prior round through a current repair closure. Every round has zero accepted P0/P1 and every accepted P2 has a valid disposition.
- `user-confirmed-override`: an explicit, hash-bound operator confirmation produced outside the plan directory and every Quick Dev write root. It records `assurance: operator-confirmed-override`, scope, reason, risk acknowledgement, expiry, and recheck condition.

The plan-local transition validator consumes either mode. Bootstrap produces supplemental evidence only and never writes a lifecycle state. The override authorizes implementation only; it cannot authorize acceptance, handoff, release, or archive.

## Completion, Acceptance, And Archive

Quick Dev may publish only `implementation-complete` after the plan-local terminal predicate passes. It must also produce a schema-validated, non-authorizing acceptance handoff.

Only `run-refactor-implementation-acceptance` may publish `acceptance-passed`, after independently evaluating the current matrix, phase gates, and conditionally required Bootstrap evidence. A future archive Skill alone may publish `archived` after acceptance and knowledge-base update evidence.

## Migration

Plans that began implementation before this contract may use a schema-validated `legacy-not-retroactive` migration marker. The marker has `authorizes: []`, cannot satisfy `implementation-authorized`, and cannot authorize any later state.

## Required Negative Cases

The plan must reject a missing or stale review envelope, a broken review lineage, accepted P0/P1, an override inside a plan or Quick Dev write root, an override that grants more than implementation, Quick Dev acceptance authorization, acceptance before implementation completion, archive before acceptance, and an authorizing legacy marker.
