# Metadata DB Architecture

## Intent

The metadata DB records the hosted platform's durable control-plane state: accounts, project limits, projects, workspaces, runs, artifacts, route prompt-evidence bindings, approvals, locks, chat state, prototype drafts, iteration sessions, LLM usage, UI state, and audit events.

It is not the source of game code, route semantics, or Godot content truth. Those remain in the project workspace and repository-generated sidecars.

## Boundary

In scope:

- Single-node SQLite metadata at the configured `PHASEA_METADATA_DB_PATH`.
- Additive schema evolution through `SqliteMetadataSchema`.
- Account-scoped project/run/artifact joins.
- Last-activity triggers and cached summaries used for readback.
- Run state, status, progress labels, stdout/stderr summaries, evidence JSON, and LLM cost summaries.

Out of scope:

- Manual mutation of the live DB as an operational fix without explicit approval.
- Treating SQLite as a distributed coordination backend.
- Storing raw secrets or provider keys in database rows.

## Key Decisions

- SQLite is sufficient for Phase A/B because the platform is single-node with local disk.
- Schema changes are additive by default to preserve live metadata and old rows.
- `summary_json`-style fields are caches or readback summaries, not the original authority when route state or evidence exists elsewhere.
- `runs` rows represent command executions; runners are processes, not durable business entities.
- LLM usage is copied into platform metadata for audit/readback, but external billing systems remain their own source of truth.
- `project_admin_review_queue` owns live cross-project blocker queries. Regeneration appends and supersedes rows rather than overwriting them; `project_admin_review_decisions` preserves each committed human decision version in the same transaction as the current-row update.
- `project_route_prompt_evidence_bindings` binds a project's prompt-producing route to its current execution hash, redacted persisted hash, prompt artifact ref, and evidence ref. Readback must match this DB row in addition to validating the workspace sidecar, preventing coordinated workspace-file rewrites from manufacturing clean evidence.
- `project_admin_review_migration_lineage` is append-only migration audit state. When an older schema contains duplicate live keys, migration prefers blocking severity before recency and records every predecessor/successor choice before superseding losers.
- Reconciliation-generated `resolved` rows are system decisions, not history deletion; they carry actor, decision version, decision UTC, structured metadata, and a matching `project_admin_review_decisions` row.

## Invariants

- Schema migrations must preserve existing project, workspace, run, artifact, account, and audit state.
- Path strings read from metadata must still be validated against workspace roots before filesystem access.
- Deleting projects must respect active-run policies and cascade behavior.
- Manual DB edits must not be used to hide failures, skip migrations, or rewrite audit history.
- Superseded admin-review rows and append-only decision rows remain available for audit. `open|rejected|backlog` rows block; `deferred` clears only during a future route-scoped window and becomes blocking when expired, malformed, or out of scope.
- Queue evidence refs are structured JSON objects with a closed kind and a workspace-relative path or artifact ID; malformed JSON, URI/rooted paths, and traversal are rejected before persistence.
- Decision evidence refs use the same structured boundary. New decisions require existing project-owned sidecar paths or artifact IDs; invalid/missing refs are rejected, while an already-committed same-payload retry remains idempotent from its stored decision metadata.

## Change Rules

- DB schema changes require persistence tests and a migration/recovery note.
- New tables must declare ownership: control plane metadata, readback cache, route state pointer, or audit record.
- New account-visible rows must include enough account/project context for scoped readback.
- Any destructive migration needs explicit approval and a decision log.

## Related Code

- `PhaseA.Platform/Data/SqliteMetadataSchema.cs`
- `PhaseA.Platform/Data/PhaseAMetadataStore.cs`
- `PhaseA.Platform/Data/*.cs` snapshot and command records
- `PhaseA.Platform.Tests/Data/SqliteMetadataSchemaTests.cs`
- `PhaseA.Platform.Tests/Data/TempSqliteDatabase.cs`

## Related Roadmap

- Phase C storage abstraction and restore must preserve metadata/workspace ownership and recovery semantics.
- Phase C runner isolation must protect the metadata DB from runner write access.
