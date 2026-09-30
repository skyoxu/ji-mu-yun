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
