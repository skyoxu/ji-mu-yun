# Repair Round 1 - Explicit Project-Local Post-Run Hook

- Repair type: maintainer-directed VDD contract repair
- Predecessor: `plan-ready` initial slice for `toolchain-plan-delivery-loop-skill`
- Finalized semantic finding set: empty; this repair consumes no Bootstrap semantic round
- Lifecycle authority: `authorizes=[]`

## Trigger

The maintainer accepted a post-run hook in place of the proposed background
poller and clarified that user-stop and manual-pause must not trigger it. The
repair must make the hook explicit and project-local because no repository-wide
or Codex-global lifecycle hook contract is authoritative.

## Repair Changes

1. Add a coordinator-only hook trigger/suppression matrix and an idempotency key.
2. Bind the five-stage filesystem loop and structured, cursor-based recovery
   inputs; model context is non-authoritative.
3. Bind fresh-session recovery to an explicit project-local launcher without
   assuming a global `/new` command.
4. Require idempotent/replayable coordinator effects and journaled or
   owner-declared rollback boundaries; prohibit early convergence.
5. Add detached contract tests and update the plan validator to enforce the
   new machine-checkable contract.
6. Refresh the current read-only Bootstrap Skill and standard hashes after the
   repository HEAD advanced; preserve the original Git baseline unchanged.
7. Bind a minimal callsite inventory and controlled producer/consumer
   composition receipt before the repaired target re-enters Bootstrap review.

## Stop Semantics

The hook is required for controlled completion, controlled failure, timeout,
and a poll-stop reported through the coordinator. It is suppressed for
`user-stop` and `manual-pause`. Process kill and machine power loss are outside
the recovery guarantee. Bootstrap Review, Quick Dev, and Refactor Acceptance
do not attach or invoke this hook.

## Bounded Repair Slices

- `RMAP-S0`: package/schema contract and hook ownership fixtures.
- `RMAP-S1`: filesystem event/checkpoint projection, hook input contract, and
  fresh-session launcher contract.
- `RMAP-S2`: five-stage routing, idempotency, rollback boundaries, and
  non-convergence predicates.
- `RMAP-S3`: detached stop matrix, replay, child-hook exclusion, and terminal
  validator coverage.

## RED, GREEN, And Recovery

- RED: the initial contract has no explicit hook, fresh-session launcher,
  five-stage loop, or effect policy; the updated validator and tests must fail
  against that predecessor.
- GREEN: the updated contract, validator, and detached fixtures pass while
  lifecycle `authorizes=[]` remains unchanged.
- Recovery: preserve the initial plan and all historical evidence; rebuild only
  derived repair projections from the plan and owner evidence. Never alter the
  three child Skill packages or launch a live reviewer.
