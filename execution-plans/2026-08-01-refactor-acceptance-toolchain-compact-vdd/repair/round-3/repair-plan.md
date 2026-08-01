# Repair Round 3 - Architecture Index Policy Coverage

## Finding

The first real policy resolution rejected the combined candidate because
`docs/architecture/ADR_INDEX_PHASE.md` was outside the policy's narrower
`docs/architecture/phase-service/` prefix.

Severity: P1. Failure family: `toolchain-policy-architecture-index-gap`.

## Repair

Cover `docs/architecture/` as a closed toolchain documentation prefix, refresh
the canonical policy revision, and add the ADR index to the positive coverage
fixture. Godot source and other non-toolchain paths remain uncovered and fail
closed.

This repair carries `authorizes=[]`. The complete terminal suite must pass
before a successor Acceptance candidate may use the revised policy.
