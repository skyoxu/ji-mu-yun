---
id: SPEC-phase-b-c-identity-isolation-workspace-recovery
package_schema: canonical-spec-package.v1
companions:
  - path: _bmad-output/planning-artifacts/architecture/architecture-phase-b-c-identity-isolation-workspace-recovery-2026-08-23/ARCHITECTURE-SPINE.md
    role: adopted_companion
  - path: _bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/identity-and-ownership.md
    role: normative_companion
  - path: _bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/runner-isolation.md
    role: normative_companion
  - path: _bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/workspace-recovery-contract.md
    role: normative_companion
  - path: _bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/api-evolution-and-operations.md
    role: normative_companion
  - path: _bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/requirements-and-acceptance.md
    role: normative_companion
sources:
  - path: _bmad-output/planning-artifacts/prds/prd-jimuyun-2026-08-23/prd.md
    role: provenance
  - path: execution-plans/2026-08-22-phase-b-c-identity-isolation-workspace-recovery-requirements.md
    role: provenance
---

> **Canonical contract.** This SPEC and its `companions:` are the complete, preservation-validated contract for downstream design, implementation planning, testing, and validation. `sources:` are traceability-only provenance; they are not a parallel obligation authority.

# Phase B/C Identity Isolation and Workspace Recovery

## Why

Phase must safely evolve from a single-node prototype into an AI Native SaaS foundation without binding tenant identity, local paths, Runner processes, or hidden model sessions into one irrecoverable unit. Authenticated account ownership, OS-level execution isolation, and versioned Workspace recovery must become independently verifiable contracts before Phase can claim strong multi-user isolation or expand toward Workers, portable sandboxes, and longer-lived Agent runtimes.

## Capabilities

- **CAP-1**
  - **intent:** Phase can resolve an authenticated Principal, tenant Account, Member relationship, Role, and revocable Credential/Session exclusively from server-controlled authority.
  - **success:** Browser-controlled account values cannot override server identity; revoked credentials, disabled accounts, and unauthorized administrator requests are rejected without cache or old-session bypass.
- **CAP-2**
  - **intent:** Phase can enforce Account and Project ownership consistently for every private resource and operation.
  - **success:** Cross-account API, data, artifact, preview, snapshot, restore, and readback access is rejected without existence, path, or tenant disclosure.
- **CAP-3**
  - **intent:** Platform and user code execute through separate, enforceable OS permission boundaries.
  - **success:** A real low-privilege Runner can use only its authorized Workspace and cannot access platform assets, secrets, staging, or another Account's Workspace; containment and ACL drift fail closed.
- **CAP-4**
  - **intent:** Phase can create and restore a logically identified Workspace through a versioned, integrity-verified Snapshot contract independent of machine paths and Agent-session state.
  - **success:** A user- or admin-requested Snapshot restores through controlled staging to a substitute root, preserves verified content and ownership, rebuilds environment-specific state, and supports hosted route/readback plus a later controlled Run; ordinary file changes never trigger either operation.
- **CAP-5**
  - **intent:** Phase can make every restore a durable, idempotent, auditable, and recoverable Restore Attempt.
  - **success:** Failures, cancellation, restart, corruption, ownership mismatch, incompatibility, quota exhaustion, and stale execution all yield bounded typed outcomes and never expose a partially restored Workspace.
- **CAP-6**
  - **intent:** Phase can expose compatible asynchronous resource state while preserving a clean upgrade path from one local node to future Worker and placement topologies.
  - **success:** Existing single-node SQLite/local-storage behavior remains compatible; placement and fencing fields are non-authoritative seeds and cannot change Account/Project/Workspace ownership.
- **CAP-7**
  - **intent:** Operators can prove the security and recovery contract from machine-verifiable evidence rather than UI state, assistant prose, or historical conversations.
  - **success:** A new process can validate the required cross-account, OS-permission, database migration, snapshot round-trip, fault-injection, redaction, and recovery evidence package.

## Constraints

- The Phase service owns authentication, authorization, ownership, scheduling, metadata, audit, restore orchestration, and stable API; Browser is a client only; Sandbox/Runner owns restricted execution only; Agent Runtime is replaceable and cannot become a business or recovery authority.
- Account is the tenant boundary. Principal, Member, Role, and Credential/Session remain distinct. One-account-one-user is temporary compatibility, not the permanent identity model.
- OIDC-first is the product direction for human production identity. Existing administrator bearer tokens are restricted to bootstrap, migration, or controlled service use. Provider and session implementation remain Architecture decisions.
- Account disablement and immediate credential revocation are current scope. Physical purge is deferred; the accepted single-node operations profile retains recoverable data for 30 days.
- Snapshot and Restore are disabled by default per Project and occur only through explicit user or protected admin entry points. Every Snapshot is a new immutable version; no historical Snapshot is updated or overwritten.
- Current deployment remains single-node, SQLite, and local-filesystem-first. All new contracts must be path-independent and allow future optional placement, lease, and fencing fields without implementing a Worker fleet.
- Snapshot content includes only explicitly supported persistent project content and artifacts; cache, build/temp output, secrets, processes, temporary capability tickets, absolute paths, unsafe links, and admin-blacklisted extensions are excluded. The representative fixture is normative and must be specified before implementation. The active extension policy is version-bound to each new Snapshot.
- Project deletion is a soft-delete marker. It releases the project's logical share of the user-level actual-space quota while retained bytes are reclaimed only by protected cleanup; no per-Project hard-disk partition is preallocated.
- Every identity, ownership, path, ACL, manifest, snapshot, and restore verification fails closed. Browser values, raw exceptions, model threads, assistant prose, and unverified logs cannot establish authority or completion.
- Existing hosted route recovery remains the sole route/readback authority after restore; this package does not create a second route recovery system.
- The details in the five normative companions are required together; `sources:` are not normative inputs. The adopted Architecture Spine resolves OQ-1..OQ-4 through the decisions below.

## Non-goals

- Rebuild the legacy frontend, implement a full React administrator/recovery UI, or require browser E2E before API/domain/automation closure.
- Refactor `Program.cs` as a prerequisite or stand-alone delivery.
- Implement multi-node scheduling, object storage, remote disaster recovery, container/microVM orchestration, E2B/Daytona/OpenHands integration, Agent App Server, or long-session registry.
- Introduce Tasks, Taskmaster, legacy Chapter 3-7 workflows, overlay generation, game templates, or unrelated Phase product governance capabilities.

## Success signal

An authenticated Account can run only within a real OS-restricted Workspace; its versioned Snapshot can be recovered on a clean substitute root through a durable Attempt without leaking secrets or another Account's resources; and the entire result can be revalidated by a new process from typed evidence. Existing SQLite/local filesystem behavior remains usable while no contract assumes an absolute path, a single process lock, or a hidden Agent conversation.

## Resolved Architecture Decisions

- **AD-OQ-1:** Credential revocation and Account disablement use a maximum five-second control-plane cache window. New Run, Restore, Preview, and private-resource reads revalidate current state at their entry boundary.
- **AD-OQ-2:** An Account disablement prevents new write leases and publication. An already-running atomic operation may finish, then the coordinator drains or cancels the Run and records the typed outcome.
- **AD-OQ-3:** The baseline Windows profile uses one restricted Runner identity per Project. Per-execution identities, containers, or microVMs remain future escalation options requiring separate evidence and approval.
- **AD-OQ-4:** The single-node profile uses 30-day retention, user-level actual-space quota (not preallocated per-Project disk), encryption-at-rest by key reference without plaintext keys, a fixture of at most 100 MiB and 10,000 files, and P95 restore-to-controlled-run RTO of 30 minutes. The admin extension blacklist is versioned and applies to newly created Snapshots; initial examples include `.jpg` and `.mp3`.
