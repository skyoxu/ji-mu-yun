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
- Regenerated blockers append and supersede prior rows by stable project/route/requirement identity. They never overwrite prior decisions or history.
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
- Any future metadata backend must preserve optimistic decision versions, append-only decision history, supersession links, and time-aware deferred-blocker semantics.

## References

- `docs/architecture/phase-service/metadata-db.md`
- `docs/architecture/phase-service/hosted-workspaces-and-artifacts.md`
- `docs/workflows/phase-c-platform-hardening-and-agent-asset-governance.md`
