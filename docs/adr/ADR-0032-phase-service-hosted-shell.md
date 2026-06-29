# ADR-0032: Phase Service Hosted Shell Over Repository Workflow Kernel

- Status: Accepted
- Date: 2026-06-28

## Context

The repository started as a Windows-only Godot + C# game template and evolved into a Phase A/B hosted prototype platform. The existing repository scripts, Godot project layout, recovery sidecars, test gates, and prototype routes already encode workflow authority.

Moving workflow decisions directly into the web service would create a second workflow engine and make browser/API behavior drift from repository-native scripts.

## Decision

The Phase service is a hosted product shell around the repository workflow kernel.

- Repository scripts, route services, contracts, sidecars, and validators own execution truth.
- `PhaseA.Platform` hosts, scopes, queues, records, reads back, and recovers workflow execution.
- Browser and Web API surfaces trigger controlled capabilities and display readback, but do not reinterpret workflow decisions.
- New hosted capabilities must call existing route services or script-owned entrypoints unless an ADR explicitly moves authority.

## Consequences

- Platform controllers remain thinner and safer.
- Agent behavior is more reproducible because execution truth remains in source-controlled scripts and route contracts.
- New product surfaces must carry recovery and evidence behavior instead of only UI state.
- Some feature velocity is traded for lower workflow drift risk.

## References

- `docs/architecture/phase-service/system-overview.md`
- `docs/architecture/overlays/PHASE-A-CLOUD-RUNNER/08/08-Phase-A-Cloud-Runner-Architecture.md`
- `docs/workflows/cloud-platform-evolution-plan.md`
