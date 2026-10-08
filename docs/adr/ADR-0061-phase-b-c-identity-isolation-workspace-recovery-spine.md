# ADR-0061: Phase B/C Identity Isolation And Workspace Recovery Spine

- Status: Accepted
- Date: 2026-08-23
- Scope: `phase-b-c-identity-isolation-workspace-recovery` capability slice only

## Context

The Phase B/C identity, Runner isolation, and Workspace Snapshot/Restore slice has a completed Architecture Spine with AD-1 through AD-13. Those decisions must become an Accepted architectural authority without expanding the slice into React migration, multi-node deployment, object storage, App Server, Agent Session, Tasks/Taskmaster, or Agent Asset governance.

## Decision

Accept the current `ARCHITECTURE-SPINE.md` AD-1 through AD-13 as the narrow architecture contract for this capability slice. The Spine remains the detailed decision record; this ADR establishes its Accepted status and inheritance boundary.

This ADR inherits and does not replace the following Accepted Phase ADRs:

- ADR-0033: SQLite metadata and local-disk Workspaces;
- ADR-0034: account-scoped token authentication;
- ADR-0035: controlled Runner and Workspace-bound execution;
- ADR-0036: prototype route recovery authority and machine-closed acceptance;
- ADR-0037: shared LLM and Codex execution entrypoints;
- ADR-0038: evidence sidecars and account-scoped readback;
- ADR-0039: Phase runtime, Caddy, and local-first recovery order.

Where this slice adds a more specific rule, it must remain compatible with those inherited ADRs. A conflict requires a new ADR or an amendment to the relevant predecessor; implementation code cannot silently override either authority.

## Boundary

This ADR covers only the identity authority, verified context propagation, Windows Runner boundary, logical Workspace identity, Snapshot Manifest, Restore Attempt, staging/publication/cleanup, DB-filesystem reconciliation, route/readback rebuild, single-node lease/fencing seed, migration/adoption, and evidence gate decisions represented by AD-1..AD-13.

It does not authorize implementation, deployment, migration execution, or release. It does not decide an OIDC provider, exact Windows token API, manifest serialization, storage schema, React UI, `Program.cs` restructuring, Worker fleet, object storage, App Server, Agent Session, Tasks/Taskmaster, or Agent Asset governance.

## Consequences

- Independent identity, Runner, storage, restore, and readback implementations have one Accepted authority boundary.
- Existing Phase A/B SQLite, local disk, account-token, controlled-runner, route-recovery, shared-entrypoint, evidence, and runtime-recovery behavior remains inherited and compatible.
- Future scale-out or stronger sandboxing still requires the evidence gates and Accepted ADR triggers defined by AD-10 and AD-13.

## References

- `_bmad-output/planning-artifacts/architecture/architecture-phase-b-c-identity-isolation-workspace-recovery-2026-08-23/ARCHITECTURE-SPINE.md`
- `_bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/SPEC.md`
- `docs/architecture/ADR_INDEX_PHASE.md`

## Recovery implementation clarification (2026-09-28)

This clarification implements the existing AD-1..AD-13 boundary; it does not
change public API routes or introduce a new delivery workflow.

- Restore recovery reads current content and the canonical frozen-contract
  consumer recomputes source hashes. Applicable active sessions need their
  current goal; needs-fix sessions need current diagnostics. Absence is only
  not-applicable when no current session/repair requires the source.
- Restore requires a matching account/project workspace descriptor. Every
  staged and published object receives and passes the explicit Administrator
  full-control / Runner modify ACL; a missing descriptor, reparse point, or
  child ACL drift fails closed before Published.
- An independent A18 reader needs a persisted succeeded producer run and
  exact artifact bindings. Package integrity alone is insufficient. Its
  producer exercises the Windows Runner access boundary and corrupt-snapshot
  quarantine, and the reader checks the resulting artifacts and observations.
- Windows execution evidence remains mandatory. Syntax checks and this
  clarification do not certify implementation-complete or a passed Q8.


## Concurrent publication recovery clarification (2026-10-01)

Startup reconciliation must distinguish an interrupted staging attempt from a live publisher in another process. It takes the existing destination/idempotency-key coordination lock, then re-reads the persisted status before moving staging content or recording interruption. A completed publication remains Published with its ready content intact; an abandoned Staging attempt retains the existing quarantine/recovery behavior. Reconciliation updates only a still-Staging row and appends history for that transition. The existing lock budget, lease/fencing, account/project authority, ACL validation, schema, and public API contracts remain unchanged.

A Windows regression first reproduced the old behavior while an active publisher held its coordination handle, then completed publication. The correction is verified by that regression and the existing S51 independent-process fault matrix and same-key single-publication assertions. This is implementation evidence for the existing ADR boundary, not a reissued plan-level implementation-complete receipt.

## Addendum (2026-10 Runner cancellation fixture readiness)

- The heavy-write cancellation fixture first observes the real Windows Runner
  startup marker within a monotonic 30-second readiness deadline, with immediate
  diagnostics when the operation exits before startup.
- Cancellation starts only after that marker. Its existing five-second bound
  and obligations to stop the operation and clear all queue state remain intact.
- Exercise both immediate startup and a deliberate six-second startup delay;
  production startup and execution timeout policy remains unchanged.
- Use a real Python child process, consistent with the existing Hosted Runner
  cancellation fixtures. The queue lifecycle obligation is independent of
  PowerShell initialization; the process writes readiness, remains active for
  30 seconds, and must be stopped by production queue cancellation.

## Addendum (2026-10 owned restore interruption fixture)

The S25 fixture dispatches its current built assembly through VSTest and uses the
existing staging-written fault point in its owned child. A dedicated monitor
requires both the producer checkpoint and real staged files before killing only
that worker process tree. Thirty-two nonempty files replace the former 5,000-file
timing buffer. The original 30-second observation bound remains. There is no
dependency on a delayed filesystem-event continuation and no fabricated
restore/history row. Restart recovery and the independent reader still validate
the actual staged content and nonterminal-operation quarantine. Early worker exit
reports bounded child stdout/stderr rather than an unqualified staging error.


## Addendum (2026-10 main CI fixture publication and HTTP startup)

- The owned S28 PowerShell child closes a complete PID staging file before a
  same-volume rename publishes its readiness path. The existing 30-second
  wait and real pre/post-restore process authority assertions remain intact.
- The S31 HTTP fixture uses one 30-second startup deadline for health and the
  first authenticated project inventory control. Only read-only startup probes
  retry transport failures or per-request timeouts; a non-success status or
  wrong owned inventory fails immediately. The three failure observations keep
  their five-second request timeout, status, redaction and correlation checks
  without retry. Immediate startup and a delayed first real inventory response
  both exercise the full observations. This is a fixture startup budget, not a
  production API latency policy.
- The S42 owned host drains both redirected pipes for its entire lifetime. A
  bounded health burst with real request logging and a one-entry console queue
  exercises Windows pipe backpressure before the same three durable operation/
  readback checks. This queue setting applies to this owned test host only.
  Operation requests retain the original 15-second timeout and are not retried.
- No production listener, service timeout, account authority, execution policy,
  quality gate, coverage threshold or historical failure evidence changes.

## Addendum (2026-10-04 package-version snapshots and activation)

The owner approved automatic package snapshots and user-initiated version recovery.
Each successful new package binds one persisted immutable snapshot and a ZIP hash.
ZIP input comes from the captured bytes, after asset replacement smoke, under the
existing project lock. A snapshot failure cannot publish a successful package.
Export files remain in the registered stable workspace's original `repo/exports`;
active source generations are independent of this historical download catalog.

The authenticated package restore route accepts a server-selected package version,
not a caller-selected snapshot or destination. It obtains a durable run, project
lock and fenced lease, reauthorizes the current credential at execution/publication,
checks the package binding/integrity and snapshot content, and validates native ACLs.
The files are moved to a unique generation inside the protected registration root.
One SQLite transaction switches root/repo/runtime/meta pointers, appends activation
history, invalidates UI cache, pauses the latest iteration session for review, and
records the succeeded run. Failure before that transaction preserves the previous
active paths. Interrupted nonterminal runs retain the existing restart reconciliation.

This file-restoration entry may recover a broken current project: unlike the
existing generic route-authorized restore API, it does not require the broken
current business chain to be ready. It does not authorize route execution or
mark a project ready. Existing ownership, credential revocation, immutable package
binding, lease fencing, snapshot verification, quota and ACL boundaries remain
mandatory. Historical acceptance is ineligible after activation until a new final
prototype validation succeeds; a subsequent failed validation blocks it again.
Current-source, contract and UI-closure validators remain required independently.

Snapshots exclude execution registration, previous generations, staged restore
files, exports and build caches. Platform accounts, credentials, Windows identities,
process memory and database history are not rolled back. The latest saved module
plan is paused for explicit review against the restored files; ordinary source
freshness gates decide whether it may continue or needs regeneration.

The existing workflow readback adds a read-only business-chain summary to the
existing status display. It consumes validated route evidence and adds no second
executable acceptance workflow or additional user acceptance button. Real Windows
activation/ACL tests and browser/consumer regressions provide implementation evidence;
CI evidence is not a claim that a production host was deployed or a live game passed.

## Addendum (2026-10-08 generation-bound acceptance)

A final validation is eligible after restore only when its server-derived
`workspace_generation_id` matches the active source generation. The opaque ID
binds account, project, logical workspace and active root/repo/runtime/meta paths;
it reveals no host path. A restored project with an older unbound receipt requires
a new final validation. A later failed or mismatched final receipt blocks readiness;
skeleton-only validation does not discharge this obligation.

Validation and packaging re-read the active paths after acquiring the project
Runner lock. A changed generation returns the existing project-busy response
without executing validation or publishing a package. Packaging rechecks readiness
inside that lock. No schema, authentication, concurrency budget, or public route
changes; historical runs and package downloads remain additive and readable.
