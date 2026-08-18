# ADR-0058: Acceptance Coordinator Persisted Evidence Ownership

- Status: Accepted
- Date: 2026-08-18

## Context

Acceptance coordinator requests currently risk carrying caller-authored route
booleans, action receipts, successor pointers, and telemetry. A self-consistent
request directory is not proof that the Acceptance action happened.

## Decision

- Acceptance-owned persisted runs, action DAGs, append-only events, bound
  command registries, route projections, and action receipts are the current
  evidence root.
- A request only identifies the target plan and prepared run input; it cannot
  provide current route truth or lifecycle authority.
- Every action result binds its run, event, registry, candidate, contract,
  Knowledge, Skill-input, and validator identities.
- v2 request material is historical-only and cannot publish current completion.
- This decision does not grant Bootstrap ownership or allow Bootstrap to start
  automatically.

## Consequences

The coordinator becomes reentrant and replayable from persisted evidence. A
caller-authored complete graph, mismatched receipt, or unregistered action is
rejected. Acceptance remains the owner of `acceptance-passed` only.

## Acceptance Boundary

This decision does not grant Bootstrap ownership, `acceptance-passed`, release,
or commit authority. It only fixes the persisted evidence root for the
Acceptance coordinator.
