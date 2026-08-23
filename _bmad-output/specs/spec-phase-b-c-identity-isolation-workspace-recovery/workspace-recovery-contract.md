# Workspace Recovery Contract

## Logical identity and storage

- **PIWR-021 / FR-015:** Workspace identity is exactly `workspaceId + accountId + projectId`. Absolute path, node, Runner identity, port, and process ID are Placement, never business identity or authorization.
- **PIWR-022 / FR-015:** Snapshot, read, restore, deletion/retention, and validation use a stable storage contract. The only current backend is local filesystem; no upper-layer state depends on a Windows drive or current directory layout.

## Snapshot contract

- **PIWR-023 / FR-016:** Every recoverable Snapshot has a versioned manifest containing schema/compatible platform-storage versions; Snapshot/Workspace/Account/Project IDs; provenance; content inventory/index, size, hashes, exclusions; ownership and ACL-policy reference; recovery conditions/compatibility/rebuild/retention; optional non-authoritative runtime refs; and security/key reference when applicable. It never contains plaintext secrets.
- **PIWR-024 / FR-017:** Snapshot boundary is deterministic. Include explicitly supported persistent project files, GDD/module contracts, source, tests, execution-plan/project work files, approved user assets, and persistent Phase artifacts. Exclude cache, transient build output, temporary files, provider secrets, processes, tickets, absolute paths, and unsafe links. The Spec/Architecture operations profile fixes the representative fixture and equivalent content identity proof.

## Restore Attempt and publication

- **PIWR-025 / FR-018:** Each restore has a unique Restore Attempt with requester, source Snapshot, target Workspace, bounded status/stage/failure family, timestamps, correlation, and result. Retries append rather than overwrite; duplicate idempotency keys do not concurrently publish separate targets.
- **PIWR-026 / FR-019:** Restore stages: verify caller and Snapshot ownership; validate schema, compatibility, content hash, size/quota, and path safety; write staging and recompute integrity; apply owner/ACL/security policy; validate Phase readback/route prerequisites; atomically or fail-safely publish; otherwise rollback or isolate staging with no exposed partial Workspace.
- **PIWR-027 / FR-020:** Restore never revives absolute paths, preview URL/ticket, process, port, node lease, Runner credential, or secret. These are invalidated and allocated/rebuilt for the current environment.
- **PIWR-028 / FR-020:** Crash, reboot, cancellation, and interruption are resolved from durable Restore Attempt plus staging state: continue, rollback, isolate, or restart. No Chat/Agent thread, in-memory object, or manual full-log reading is required.
- **PIWR-029 / FR-021:** GDD, module contracts, source, tests, execution-plan/project files, and persistent artifacts are recovery truth. Agent thread/session IDs are optional references only.
- **PIWR-030 / FR-021:** Restore re-enters the existing hosted route recovery authority, rejects stale/missing routes, and exposes readback only to the current Account.
- **PIWR-031 / FR-022:** Snapshot retention, pin, expiry, deletion, quota, and failed-staging cleanup are auditable; cleanup respects active Attempts and audit retention and never uses an unchecked broad path prefix/glob.
- **PIWR-032 / FR-022 and NFR-005:** A standard fixture completes Snapshot to a fresh temporary root or substitute Worker and validates content, ACL, route/readback, controlled Run, and cleanup. RPO preserves the last successfully published integrity-verified Snapshot; unfinished un-published writes may be redone. The first RTO profile targets P95 30 minutes to a controlled runnable state, subject to OQ-4 fixed fixture and measurement boundary.

## Required evidence

- **PIWR-A08:** Snapshot/log/artifact secret scan proves prohibited secrets, temporary tickets, and absolute paths are absent.
- **PIWR-A09:** Substitute-root recovery proves content, ownership/ACL, route/readback, and subsequent controlled Run.
- **PIWR-A10:** Wrong Account, corrupt hash, unknown schema, quota failure, and incompatible version fail before publication without partial overwrite.
- **PIWR-A11:** Failure injection across restore stages produces resumable, rollback, or isolation outcomes from Attempt/staging state.
- **PIWR-A12:** Old preview ticket, port, PID, secret, and lease are unusable after restore; current allocation functions.
- **PIWR-A13:** Duplicate restore key cannot publish two Workspaces and stale fencing cannot overwrite current publication.
- **PIWR-A14:** Retention, pin, quota, deletion, and staging cleanup are audited and protect active restore inputs.
