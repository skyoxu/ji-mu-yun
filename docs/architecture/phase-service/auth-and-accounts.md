# Auth And Accounts Architecture

## Intent

The account layer turns the Phase A single-admin console into a Phase B account-scoped prototype platform. Its job is to make project, run, artifact, package, asset, chat, workflow, LLM, and admin readback respect the current account boundary.

## Boundary

In scope:

- Host admin token and database-backed user tokens.
- Token hashing for persisted user tokens.
- Admin-created users, disabled/enabled status, token rotation, account limits, audit events, and LLM binding ownership.
- Account-scoped APIs and readback.

Deferred beyond the current Phase B prototype-hardening slice:

- Username/password login.
- Password reset.
- OAuth/OIDC.
- Self-service registration.
- Full identity product UX.
- Separate Windows runner accounts and project-level NTFS ACLs.

## Key Decisions

- User tokens are returned once and only hashes are stored.
- Admin token material and provider keys are never written to git-tracked docs or logs intended for readback.
- Account-scoped readback is enforced in application code in Phase B.
- Stronger OS-enforced isolation belongs to Phase C after explicit runner identity and ACL design.
- Admin readback may summarize cross-account state, but raw secrets, token hashes, provider keys, and raw command logs must not be exposed by default.

## Invariants

- A user must not list, mutate, or read another account's project data by guessing IDs.
- Project-scoped API routes must resolve the current account before reading projects, runs, artifacts, packages, assets, chats, or workflow state.
- Token material must not be logged, documented, or included in audit metadata.
- Account audit metadata must be useful for operations but safe for admin readback.

## Change Rules

- Auth/token/account changes require tests for both authorized and unauthorized paths.
- Admin API changes must preserve token redaction and account scoping.
- Any new readback surface must decide whether it is account-scoped user readback or admin-only readback.
- Identity-product changes require a decision note or ADR because they affect recovery, audit, and operator workflow.

## Related Code

- `PhaseA.Platform/Security/PhaseAAuth.cs`
- `PhaseA.Platform/Security/AccountIdentity.cs`
- `PhaseA.Platform/Data/PhaseAMetadataStore.cs`
- `PhaseA.Platform/Data/SqliteMetadataSchema.cs`
- `PhaseA.Platform/Llm/LlmBindingService.cs`
- `PhaseA.Platform/Readback/ArtifactReadbackService.cs`
- `PhaseA.Platform/Program.cs`

## Related Tests And Evidence

- `PhaseA.Platform.Tests/Security/PhaseAAuthTests.cs`
- `PhaseA.Platform.Tests/Data/SqliteMetadataSchemaTests.cs`
- `scripts/python/phase_b_account_smoke.py`
- `docs/workflows/phase-b-account-isolation.md`
