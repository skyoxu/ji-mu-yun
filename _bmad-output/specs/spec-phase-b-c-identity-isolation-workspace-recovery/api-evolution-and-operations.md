# API, Evolution, and Operations Contract

## API and state

- **PIWR-033 / FR-023:** Snapshot, Restore, ACL repair, and future purge are asynchronous operations exposing stable Run/Attempt ID, bounded status, and evidence/readback pointer. Browser connection lifetime is not execution lifetime.
- **PIWR-034 / FR-024 and NFR-004:** Public/browser API changes are additive by default. Breaking schema or auth changes require versioning or a migration window; older clients tolerate absent future topology fields.
- **PIWR-035 / FR-024 and NFR-001:** Identity, Runner, Snapshot, and Restore states are bounded enums. Stable failure families include `unauthenticated`, `forbidden`, `account_disabled`, `credential_revoked`, `ownership_mismatch`, `path_escape`, `acl_invalid`, `snapshot_corrupt`, `schema_unsupported`, `quota_exceeded`, `restore_conflict`, `restore_interrupted`, `stale_lease`, and `internal_failure`. Raw exceptions are diagnostics only.
- **PIWR-036 / FR-025:** Browser consumes server-returned Principal, Account, capabilities, and state; hidden controls, client route guards, and local cache cannot substitute server authorization.

## Evolution boundary

- **PIWR-037 / FR-026:** Optional `nodeId`, `runnerId`, `sandboxId`, `attemptId`, `leaseVersion/fencingToken`, and `workspaceSnapshotId` can be introduced without becoming ownership authority. Single-node values may be null/default.
- **PIWR-038 / FR-013:** Exclusive Project write behavior must evolve to durable lease/fencing. Old or timed-out workers cannot publish after lease loss.
- **PIWR-039 / FR-026:** Snapshot/Restore is the migration boundary. Future blob/object placement changes storage placement only, not ownership, manifest validation, or publish rules.
- **PIWR-040 / FR-026:** API/Worker separation, durable job/event, runtime/sandbox provider, checkpoint, lease, and fencing are valid evolution patterns; Phase's Account, Project, Run, Workspace, and recovery contract remains the product authority. This does not require separate deployment services now.

## Cross-cutting operations requirements

- **NFR-001:** Identity, path, ACL, manifest, Snapshot, and Restore validation fails closed. DB/filesystem divergence enters typed recovery/repair, not silent selection.
- **NFR-002:** Secrets are on-demand in authorized Runner lifetime only; threat coverage includes enumeration, traversal, reparse points, cross-Account Runner, stale credentials/leases, malicious snapshots, and restore bomb/quota exhaustion.
- **NFR-003:** Critical state transitions use transactional, idempotent, or compensating semantics; pre/post-publication state is distinguishable and manifests are recomputed before publication.
- **NFR-004:** SQLite migration validates fresh, upgrade, and reuse; local filesystem remains first backend; existing records and token clients receive deterministic compatibility behavior.
- **NFR-005:** The first RPO/RTO profile uses OQ-4 measurements and cannot use an empty fixture as evidence.
- **NFR-006:** Identity, authorization, Run, Runner, Snapshot, and Restore events correlate timestamp, status, action, actor/principal, Account, Project, Workspace, Run/Attempt, node/Runner when applicable, and correlation ID. High-cardinality payloads reside in controlled evidence rather than browser or model summaries.

## Required evidence

- **PIWR-A15:** Private API cache, bounded state/error, and response redaction pass.
- **PIWR-A16:** Nullable topology fields preserve current one-node behavior and Restore has no absolute-path/node dependency.
- **PIWR-A18:** A new process validates the final isolation, OS permission, snapshot round-trip, failure-injection, DB upgrade, and secret-redaction evidence package.
