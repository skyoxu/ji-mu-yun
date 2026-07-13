# ADR-0033: SQLite Metadata And Local Disk Workspaces For Phase A/B

- Status: Accepted
- Date: 2026-06-28

## Context

Phase A/B run on one Windows host with local Godot, .NET, Python, Codex, Caddy, and hosted project workspaces. The platform needs durable metadata for accounts, projects, workspaces, runs, artifacts, route state pointers, chat, audit, and LLM usage.

At the current scale, distributed database and object-storage dependencies would add operational complexity before the product proves the hosted prototype loop.

## Decision

Use SQLite for Phase A/B control-plane metadata and local disk for hosted workspaces and artifacts.

- `PHASEA_METADATA_DB_PATH` points to the live SQLite metadata DB.
- Hosted project workspaces stay under `logs/phase-a-innernet/workspaces/**`.
- Runtime evidence stays under `logs/phase-a-innernet/**`.
- Schema changes are additive by default and must preserve existing data.
- Cross-project admin review blockers are authoritative in `project_admin_review_queue`; human decisions are versioned in the append-only `project_admin_review_decisions` table in the same SQLite transaction.
- `project_route_prompt_evidence_bindings` is the control-plane authority for the current prompt evidence digest of each project/route. It stores only hashes and project-relative artifact/evidence refs, never raw prompts or secrets, and is replaced atomically when that route produces a new accepted prompt evidence set.
- Regenerated blockers append and supersede prior rows by stable project/route/requirement identity. They never overwrite prior decisions or history.
- Legacy duplicate-key migration chooses the live blocking P0/P1/P2 row before a newer non-blocking row and records every predecessor/successor choice in `project_admin_review_migration_lineage`; migration must not silently discard a real blocker.
- System reconciliation that closes a vanished blocker writes a versioned `resolved` decision with actor `system` into `project_admin_review_decisions` in the same transaction as the queue row.
- Human decision evidence refs are normalized into structured sidecar/artifact objects. Unsafe or missing project-relative paths and artifact IDs not owned by the project are rejected before a new decision version is committed; stale same-payload retries remain idempotent from the recorded metadata snapshot.
- Project-local admin-review sidecars are regenerable projections of SQLite state, not a second query authority.
- Local disk remains the storage backend until Phase C storage abstraction is explicitly designed.


## Rejected Alternatives

- PostgreSQL is not selected for Phase A/B because the current deployment is single-node and would add service installation, backup, credential, and network failure modes before the hosted prototype loop needs multi-host writes.
- MongoDB is not selected because Phase metadata is relational control-plane state: accounts, projects, runs, artifacts, route pointers, audit rows, and usage summaries need joins, constraints, additive schema migrations, and deterministic smoke validation more than document-shape flexibility.
- Redis is not selected as a source of truth because Phase recovery must survive process restarts and host recovery from durable metadata and sidecars. Redis may be evaluated later only as a cache or queue aid, not as authoritative metadata.
- Object storage is deferred because current workspaces, package outputs, route state, and recovery evidence are local-disk oriented. Moving artifacts to object storage requires a restore contract and account-scoped artifact ownership model first.

## Migration Triggers

Revisit this ADR before introducing any of the following:

- More than one runner host or app host writing Phase metadata.
- Object-backed artifact storage, remote restore, or disaster-recovery requirements that cannot be satisfied from local disk snapshots.
- Sustained SQLite write contention that cannot be solved by queueing, indexing, or bounded route concurrency.
- A production tenant model that requires database-level user isolation, managed backup, point-in-time restore, or external audit retention.

## Consequences

- Deployment remains simple and recoverable on a single Windows host.
- Direct live DB mutation is high risk and requires explicit approval.
- Scale-out and remote restore are deferred to Phase C.
- Future storage abstraction must preserve account, workspace, artifact, and recovery semantics.
- Any future metadata backend must preserve optimistic decision versions, append-only human/system decision history, supersession and migration-lineage links, and time-aware deferred-blocker semantics.

## References

- `docs/architecture/phase-service/metadata-db.md`
- `docs/architecture/phase-service/hosted-workspaces-and-artifacts.md`
- `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance.md`
