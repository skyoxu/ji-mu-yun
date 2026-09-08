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

## 2026-09-08: Current Acceptance Practical Closeout

The maintainer approves functional equivalence for the 8-15 Acceptance/Bootstrap
Efficiency, 8-17 Acceptance Coordinator Efficiency and 8-18 Acceptance Coordinator
Trust Recovery directories. The bounded closeout is described in
[Acceptance current closeout](../acceptance-current-closeout.md).

- Bootstrap decision v11 requires explicit maintainer intent. Risk classes remain
  diagnostic context; incomplete deterministic proof still blocks. This supersedes
  automatic review requirements in v10, not ordinary Acceptance verification.
- Current Quick Dev Q8 results are consumed in their native format. The owner
  rederives assertion/case coverage, behavior routes, deferred eligibility and
  runtime-root bytes without launching workers or publishing proof during replay.
  New terminal inputs carry their complete frozen snapshot manifest. Replay checks
  the same runtime roots; newly created Acceptance evidence is not a runtime root.
  Acceptance separately validates explicit changed-path candidate custody and its
  registered checks. Q8 remains non-authorizing implementation evidence.
- Coordinator input parsing validates the actual Skill-input ready receipt, exact
  target, candidate manifests and knowledge context. Bundle-bound actions and
  registry are authoritative. Derived identity includes Skill-input custody.
- A successful replay rechecks persisted inputs, lifecycle-bound command receipts,
  Q8 proof and finalization. Failed commands stop after one attempt; a stored waiting
  result never authorizes automatic retry. Incomplete or stale proof remains blocked.
- No legacy lifecycle reconstruction, consumer-graph project, performance benchmark,
  Bootstrap live run or CH456 reopening is required by this closeout.

Historical results retain their original bindings. A current Q8 result without a
snapshot manifest is not upgraded in place: publish a new Q8 summary in a new output
directory using explicit existing predecessors; this rechecks evidence without
rerunning RED/GREEN or calling a model. Invalid predecessors still require the
current Quick Dev recovery route.
