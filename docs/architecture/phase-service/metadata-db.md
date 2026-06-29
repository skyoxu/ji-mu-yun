# Metadata DB Architecture

## Intent

The metadata DB records the hosted platform's durable control-plane state: accounts, project limits, projects, workspaces, runs, artifacts, approvals, locks, chat state, prototype drafts, iteration sessions, LLM usage, UI state, and audit events.

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

## Invariants

- Schema migrations must preserve existing project, workspace, run, artifact, account, and audit state.
- Path strings read from metadata must still be validated against workspace roots before filesystem access.
- Deleting projects must respect active-run policies and cascade behavior.
- Manual DB edits must not be used to hide failures, skip migrations, or rewrite audit history.

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
