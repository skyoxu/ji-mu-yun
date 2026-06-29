# ADR-0040: Phase C Hardening Before Scale-Out

- Status: Proposed
- Date: 2026-06-28

## Context

Phase C is the next major evolution path after the Phase A hosted prototype core and Phase B account-scoped prototype-hardening slice. The roadmap includes storage abstraction, runner isolation, identity hardening, agent asset governance, derived state indexes, telemetry, and optional stronger runner tiers.

There is a risk that future work treats Phase C as a feature-expansion bucket before security, authority, restore, and isolation boundaries are proven.

## Decision

Phase C should prioritize hardening and governance before scale-out or broad feature expansion.

- Keep repository scripts and validators as execution authority unless an ADR explicitly moves authority.
- Harden account lifecycle, auth middleware tests, admin browser E2E, and LLM audit exports.
- Prove Windows runner account separation and project-level NTFS ACLs before stronger isolation claims.
- Define storage abstraction and restore semantics before object storage or worker expansion.
- Add project-local agent asset catalog and doctor checks without importing external repositories as runtime dependencies.
- Add minimal operational telemetry and derived state indexes from generated evidence.
- Evaluate containers, Windows Sandbox, lightweight VMs, or remote runners only after ACL and restore contracts are proven.

## Consequences

- Production-readiness work is ordered by security and recovery dependencies.
- The platform avoids claiming multi-tenant isolation before OS-level evidence exists.
- Strong isolation and scale-out can evolve without rewriting repository workflow logic.
- Some user-facing expansion is deferred until governance and restore boundaries are explicit.

## References

- `docs/architecture/phase-service/roadmap-and-hardening.md`
- `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance.md`
- `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance-backlog.md`
