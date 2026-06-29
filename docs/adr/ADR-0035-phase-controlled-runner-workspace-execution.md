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
