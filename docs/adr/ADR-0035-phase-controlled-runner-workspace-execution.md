# ADR-0035: Controlled Runner And Workspace-Bound Execution

- Status: Accepted
- Date: 2026-06-28

## Context

Hosted project workflows mutate Godot projects, generated assets, sidecars, packages, logs, and route state. Running multiple mutating commands against one workspace can corrupt state or make recovery ambiguous.

The platform also must not expose arbitrary process execution or user-provided repository URLs.

## Decision

Use controlled hosted process execution with project-scoped workspace boundaries.

- Each project has a server-controlled workspace.
- Long-running mutating work goes through runner/queue services and records a `runs` row.
- Heavy runner execution is serialized per project.
- Route-specific and account-specific concurrency limits are configured through the Phase runtime variables in `runtime/phase-a/start-phasea.ps1`.
- Read-only artifact and status readback may remain concurrent.
- Runner commands must be allowlisted route/service/script entrypoints, not arbitrary browser-provided commands.
- Workspace paths must be normalized and checked against the workspace root before file reads or writes.
- Windows batch entrypoints retain the configured script path when invoked through `cmd.exe`; arguments and UTF-8 stdin remain part of the controlled dispatch.
- A nonzero tool exit is an execution failure, not evidence of cleanup failure. A subsequent dispatch may proceed after verified cleanup, including after timeout or cancellation. A detectable process cleanup failure blocks reuse of that Runner instance (ADR-0061 / PIWR-014).

## Consequences

- Same-project mutation races are reduced.
- Recovery can reason from run rows, route state, and artifacts.
- Throughput is limited per project by design.
- Phase C runner isolation can replace or augment the local runner only if it preserves workspace ownership and recovery semantics.

## References

- `docs/architecture/phase-service/hosted-workspaces-and-artifacts.md`
- `PhaseA.Platform/Runs/HostedProcessRunner.cs`
- `PhaseA.Platform/Runs/HeavyRunnerQueueService.cs`
- `PhaseA.Platform/Workspaces/WorkspacePathPolicy.cs`
- `runtime/phase-a/start-phasea.ps1`

## Creation admission clarification (2026-10-04)

`PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS` remains the existing per-service host
execution budget, also used by the initialization queue. Project creation now waits
for an available host slot instead of returning a global-limit rejection. The
per-account admission limit remains configured and cancellation releases a waiting
account slot. The HTTP success shape remains compatible; while waiting, the browser
shows that server execution resources may be busy. An HTTP disconnect can cancel
creation before admission completes; this is not a new durable creation API.
These variables are not a distributed platform quota or a shared budget across
multiple processes on one server. Future multi-server scheduling must coordinate
host execution capacity without introducing a fixed platform-wide creation cap.
