# Implementation Slices

The plan uses five dependent behavior slices. Quick Dev resolves each declared
selector against the frozen current candidate and owns the observed RED/GREEN/
REFACTOR evidence. This plan does not publish RED descriptors or receipts.

## S0 — Identity and Context Authority

- Behavior: Server derives Principal/Account/Member/Role/Credential context and preserves it across HTTP, background Run/Restore, Preview, private readback, and Runner launch. Revocation/disablement uses the five-second cache bound; current atomic work drains/cancels without new lease or publication.
- Obligations: PIWR-001..014; FR-001..009; NFR-001, NFR-002, NFR-004.
- Acceptance: PIWR-A01..A04, PIWR-A15, PIWR-A17.
- Failure intent selectors: `PhaseA.Platform.Tests/**/*Account*`, `*Auth*`, `*Authorization*`, `*Token*`, `*Project*Scope*`, and new focused tests for disabled-account cache expiry, queued context revalidation, cross-account denial, no-store, and redaction.
- GREEN target: One server-owned context contract is used at every boundary; old account-scoped token behavior remains compatible; additive migration preserves fresh/upgrade/reuse data.
- Dependents: S1, S2, S3, S4.
- Recovery: Re-run only the identity/auth and metadata selectors after reverting or isolating the affected migration; do not execute live DB mutation.

## S1 — Runner and OS Isolation

- Behavior: Each Project heavy-write/restore Runner uses a restricted identity, Job Object, deny-by-default NTFS ACLs, explicit Project roots, and lease/fencing checks; path/reparse/ACL drift fails closed.
- Obligations: PIWR-015..020, PIWR-038; FR-010..014, FR-026; NFR-001, NFR-002, NFR-003.
- Acceptance: PIWR-A05..A07, PIWR-A13, PIWR-A16.
- Failure intent selectors: `PhaseA.Platform.Tests/**/*Runner*`, `*Workspace*Path*`, `*Acl*`, `*Containment*`, `*Lease*`, plus a real Windows unauthorized-access negative test.
- GREEN target: Account A cannot access Account B or platform resources even when application authorization is defective; stale lease cannot publish; path escape and ACL drift isolate the target.
- Dependencies: S0.
- Recovery: Re-run isolated filesystem/ACL fixture tests with temporary roots; never use live Hosted workspaces.

## S2 — Logical Workspace and Immutable Snapshot

- Behavior: Workspace identity is `(workspaceId, accountId, projectId)` independent of placement. Explicit user/admin Snapshot creates a new immutable Manifest; no watcher or ordinary file change triggers Snapshot. Boundaries exclude secrets, paths, temp output, unsafe links, and versioned admin-blacklisted extensions; quota is user-level actual space.
- Obligations: PIWR-021..024, FR-015..017; NFR-001..003, NFR-007.
- Acceptance: PIWR-A08..A10, PIWR-A14, PIWR-A16.
- Failure intent selectors: `PhaseA.Platform.Tests/**/*Workspace*`, `*Snapshot*`, `*Manifest*`, `*Quota*`, `*SoftDelete*`, and fixture tests for <=100 MiB/<=10,000 files plus blacklist version binding.
- GREEN target: Snapshot manifests are content-verifiable, immutable, policy-versioned, and account/project-owned; soft delete releases logical quota without mutating historical snapshots.
- Dependencies: S0, S1.
- Recovery: Re-run storage/manifest tests against disposable roots; preserve prior manifests and append new evidence.

## S3 — Restore Attempt and Fail-Safe Publication

- Behavior: Explicit Restore creates an append-only Attempt, validates ownership/schema/hash/quota/path/ACL, writes isolated staging, rebuilds route/readback/secret/runtime state, and atomically or fail-safely publishes. Crash/cancel/restart reconciles durable intent/outcome as continue, rollback, quarantine, or repair.
- Obligations: PIWR-025..032; FR-018..022; NFR-001..003, NFR-005, NFR-006, NFR-007.
- Acceptance: PIWR-A08..A14, PIWR-A18.
- Failure intent selectors: `PhaseA.Platform.Tests/**/*Restore*`, `*Recovery*`, `*Staging*`, `*Readback*`, `*Route*Recovery*`, `*Attempt*`, and fault-injection tests across every stage.
- GREEN target: Wrong tenant, corrupt/incompatible/quota input, interruption, stale lease, and partial publication never expose a ready Workspace; substitute-root drill reaches controlled Run within the bounded profile.
- Dependencies: S0, S1, S2.
- Recovery: Resume from durable Attempt/staging state or quarantine; do not infer state from chat, memory, or full-log reading.

## S4 — API Evolution, Migration, Audit, and Evidence

- Behavior: Async Run/Attempt API remains additive and bounded; fresh/upgrade/reuse SQLite compatibility, placement/fencing seeds, redacted account-scoped evidence, and new-process validation are complete without introducing multi-node or React work.
- Obligations: PIWR-033..040; FR-023..026; NFR-001..006.
- Acceptance: PIWR-A04, PIWR-A12, PIWR-A15..A18.
- Failure intent selectors: `PhaseA.Platform.Tests/**/*Migration*`, `*Readback*`, `*Audit*`, `*Evidence*`, `*Async*`, plus `scripts/python/phase_b_*` account smoke and new-process evidence validation.
- GREEN target: Existing clients/data remain compatible, statuses/failures are bounded, events correlate required IDs without secrets, and placement fields never become authority.
- Dependencies: S0..S3.
- Recovery: Run additive migration rollback/reuse fixtures and targeted readback tests; preserve old evidence as historical.

## Terminal Full Validation

- Command: `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj`
- Additional: `py -3 scripts/python/phase_b_account_smoke.py --help` (then the bounded account smoke with an approved local base URL), schema/migration fixture command, and a controlled Snapshot/Restore fixture runner under `logs/`.
- Terminal result must bind the current candidate, all active slice evidence, and the current contract; targeted checks alone never publish `implementation-complete`.
