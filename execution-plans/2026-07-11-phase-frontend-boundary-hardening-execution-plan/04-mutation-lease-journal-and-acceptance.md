# Mutation Lease, Journal, And Acceptance

## Work Policy Registry

`CodexWorkPolicyRegistry` key:

```text
routeActionDescriptorId + subOperationId + policyVersion
```

It owns only execution permission:

- descriptor ID/version/hash binding
- read/write/protected/forbidden paths
- provider/tool/process/environment capabilities
- change/delete/time limits
- required Profile and Permit audience

It does not copy business route state or acceptance. Parity tests fail when a file-changing action lacks exactly one active Work Policy.

Registry population occurs only after BH-HANDOFF and imports canonical action/alias/sub-operation IDs from the exact UpstreamHandoffManifest-bound `workflow-action-contracts.v1.json` and route module fixture hashes. It cannot invent, rename, merge or reinterpret an upstream action, status, eligibility rule, recovery input or acceptance reference. An unknown or changed upstream ID/hash requires a new authorized handoff, not a local policy entry.

## Mutation Lease

Lease binds account/project/route/sub-operation/run/permit, active handoffEpoch/StateEvent/ActiveRegistry rowVersion and Permit Authority restoreEpoch, and remains held from baseline creation through final Acceptance plus trusted Postflight persistence, rollback completion plus failure Postflight persistence, or explicit rollback-conflict handoff. Mutation committed or Acceptance accepted alone is not a lease-release point.

- Persistent uniqueness key is `accountId + projectId`; route/run/permit are lease payload, not uniqueness dimensions.
- Every successful acquire/takeover increments a monotonic fencing token. Mutation journal writes, staging apply, Acceptance state, rollback, evidence and Postflight compare the current token, active handoffEpoch and restoreEpoch in the same transaction or fail closed.
- A stale holder with an older token cannot heartbeat, commit, roll back, finalize or release after takeover even if its process resumes.
- Filesystem apply/rollback also holds a takeover-aware per-project OS applier lock. Before and after every replace/move it rechecks the persistent fencing token and journal row version; takeover cannot complete until the current applier exits or is terminated, and a stale applier cannot continue after lock/token loss.

Defaults, configurable by accepted ADR:

- lease TTL: 120 seconds
- heartbeat: 30 seconds
- stale consideration: two missed heartbeats plus process-liveness check
- takeover: only after stale proof, Permit status check, journal inspection, and audited decision
- Acceptance heartbeat owner: trusted Acceptance supervisor, bound to its runner Job Object and Test/Acceptance Attestation record

Cancellation, Permit revoke, process exit, and service restart must reconcile lease and journal. Force-release requires named admin, reason, evidence, and cannot delete journal.

`rollback_conflict`, `rollback_failed` and `manual_recovery_required` create a persistent project recovery block separate from the expiring execution lease. Handoff may release process resources, but no new mutation Permit/lease is issued until a named recovery owner records a verified new baseline and explicitly closes the block.

During long Acceptance and Postflight, heartbeat continues. Users and other runners receive stable mutation-locked/read-only behavior. Lease release is forbidden while Acceptance, rollback, source/host manifest calculation, trusted evidence write or Postflight signing is pending.

Heartbeat cannot be renewed by Codex or an untrusted child process. Trusted orchestration transfers heartbeat ownership from Acceptance supervisor to Postflight supervisor through one compare-and-swap transition. Every heartbeat revalidates manifest ID/hash, handoffEpoch, selected StateEvent hash, ActiveRegistry rowVersion, capability/compatibility deferral state and restoreEpoch. Loss of either supervisor, registry tuple drift, Job Object identity mismatch, expired execution deadline or unavailable protected lease store moves the run to reconciliation; it never silently releases or extends the lease.

## Separate State Machines

### Permit

Owned exclusively by book 02 Permit authority. This book references, and must not restate a subset of, the canonical Permit state enum and transition rules.

### Mutation Transaction

```text
prepared -> validated -> committing -> committed -> acceptance_pending -> postflight_pending -> finalized
   |           |            |             |                 |                    |
   v           v            v             +-> rollback_required <---------------+
aborted     rejected   rollback_required          |
                                          +-------+---------+----------------+
                                          v                 v                v
                                      rolled_back      rollback_conflict  rollback_failed
                                                            |                |
                                                            +--------+-------+
                                                                     v
                                                          manual_recovery_required
```

### Downstream Acceptance Transaction Projection

This is a protected internal transaction-state projection, not the upstream route/readback/acceptance status authority. Persisted values are namespaced under the downstream transaction store and never written into upstream route sidecars, status vocabulary, browser DTOs or business APIs. Upstream Acceptance result/status remains identified by the UpstreamHandoffManifest acceptance registry; downstream maps it into rollback/finalization behavior without redefining it.

```text
not_started -> running -> accepted -> postflight_pending -> finalized
                   |
                   +-> failed_rollback_pending -> failed_rolled_back -> postflight_pending
                   |                         |
                   |                         +-> failed_rollback_conflict -> manual_recovery_required
                   |                         +-> failed_rollback_failed -> manual_recovery_required
                   |
                   +-> failed_preserved_by_contract -> postflight_pending
                   |
                   +-> interrupted_rollback_pending -> failed_rolled_back/manual_recovery_required
```

Permit, Mutation and downstream Acceptance transaction states are stored separately and linked by permitId/runId/journalId. None may stand in for, or be projected as, an upstream route/readback status.

Every transition has a single owner, compare-and-swap precondition, idempotency key and durable technical evidence reference. `rollback_conflict`, `rollback_failed`, `failed_rollback_failed`, `manual_recovery_required` and force-release handoff are explicit internal persisted states, never free-text notes. Browser/API behavior uses the upstream handoff-bound mapping and domain codes; these internal names are not browser vocabulary. No state called `rolled_back_failed` is used because it is ambiguous.

Cancellation, revoke, timeout, process loss and service restart while Acceptance is running always enter `interrupted_rollback_pending` unless the accepted route contract explicitly permits preserved failure. They cannot transition directly to `aborted` after Mutation commit. Rollback I/O error, partial restore or baseline-verification mismatch enters `rollback_failed`/`failed_rollback_failed` and requires manual recovery.

Acceptance result persistence, trusted attestation reference and candidate HostEffectiveManifest hash commit in one compare-and-swap transaction. If the process crashes before that transaction, recovery treats the result as uncommitted and safely reruns under the same candidate or rolls back by policy. If it crashes after commit, the signed attestation/idempotency key prevents duplicate Acceptance and resumes Postflight.

## Baseline And TOCTOU

- Acquire lease before baseline.
- Baseline includes allowed path inventory and current formal workspace hash.
- Recheck formal workspace immediately before commit.
- Any third-party change creates `mutation_baseline_conflict`; no overwrite or auto-merge.
- User/runner changes remain authoritative; Codex focused workspace is retained for manual recovery evidence.

## Trusted Staging

- Staging is on the same volume as target workspace to permit safe replace/rename semantics.
- ACL allows Phase service only; Codex identity cannot mutate staging or journal.
- Staging path is canonicalized and cannot contain junction/reparse escape.
- Backup files preserve required metadata and inherit protected ACL.
- Sensitive rollback content follows evidence retention and secure deletion policy.

If same-volume staging is unavailable, route is blocked unless an ADR-approved copy-and-verify protocol with equivalent crash recovery exists.

## Journaled Two-Phase Apply

1. Write formal/focused baseline hashes to trusted journal.
2. Calculate add/modify/delete/rename and size.
3. Validate Permit, Work Policy, lease, path and current baseline.
4. Stage allowed new files.
5. Record each target old/new hash, operation and rollback source.
6. Apply one file at a time with safe replace/move and persist journal progress.
7. Crash/failure enters rollback_required.
8. Rollback restores applied files and verifies baseline hash.
9. Restart resumes committing or rollback based on journal, never guesses from filesystem alone.

## Acceptance Failure Default

After Mutation committed, upstream acceptance runs.

Default behavior:

- Acceptance failure enters `failed_rollback_pending`.
- Formal workspace rolls back to baseline.
- Failed focused workspace, sanitized diff and acceptance evidence remain quarantined for repair/admin inspection.
- Browser reports route failure, never Mutation success.

Only an accepted route contract may select `failed_preserved_by_contract`. It must state rationale, user-visible behavior, repair path, retention, and account-safe evidence. Missing declaration always means rollback.

### Relocated Review Facts Are Not Acceptance Authority

A repository Bootstrap finalized-run envelope is a review fact consumed by the
Phase adapter; it is never a Permit, Mutation, Acceptance, Postflight, browser,
deployment, or release decision. BH-SF3 stores its validated hash and bounded
account-scoped reference alongside the transaction correlation tuple, but
continues to derive rollback/finalization from the upstream route acceptance
contract and latest live acceptance blocker.

The adapter may not translate Bootstrap `clean`, `blocked`, `incomplete`,
`manual_pause`, finding severity, or review-cycle state into upstream route or
browser vocabulary. A stale envelope after Mutation preparation blocks the
review-dependent transition and follows normal reconciliation; it cannot
release the lease, skip Acceptance, or overwrite a newer live blocker. This is
the receiving contract for existing `PBR-024` and `PBR-062`.

Before rollback, re-read formal workspace hash and compare it with the recorded post-commit hash. Any unexpected change enters `rollback_conflict`; automatic rollback stops and preserves both baseline and current state. A named recovery owner decides merge/manual restore without overwriting newer user work.

## Quarantine Security

- Quarantine uses no-execute/restricted ACL and is not a web/static root.
- No automatic Godot import, build, preview, script execution or thumbnail generation.
- Normal users cannot enumerate or download quarantine content.
- Admin readback shows sanitized manifest/diff/text only; raw download requires explicit authorization and audit.
- Cross-account access is forbidden.
- Retention and secure deletion follow evidence policy; unresolved security evidence is preserved.
- Quarantine, rollback backup and sensitive diff/evidence content are encrypted at rest with project/account-scoped data keys wrapped by a protected host key. Backup keys, rotation, access audit and cryptographic erasure follow book 07; ACL alone is insufficient.

## Side-Effect Ledger

File journal does not cover non-file effects. A trusted supervisor/broker records a side-effect ledger from OS-enforced boundaries and post-run inspection for:

- child processes and process-tree cleanup
- TEMP/HOME/CODEX_HOME files
- Godot import/cache/output paths
- SQLite/user data touched by allowed tools
- registry/environment mutation attempts
- network/proxy requests where capability is allowed
- external tool output outside project paths

Policy declares allowed side effects and cleanup/verification. Undeclared side effects fail Postflight and block Acceptance. Irreversible external side effects are forbidden unless an ADR and route contract define compensation.

Worker self-report is untrusted supplemental diagnostics only. The authoritative ledger is derived from Job Object process accounting, broker launch records, restricted per-run TEMP/HOME/CODEX_HOME inventory, filesystem before/after manifests, network-denial/proxy logs, allowed output-root scans and cleanup verification. Registry writes and paths outside observable/enforceable roots are denied by token/policy; inability to observe an allowed side effect blocks that capability.

## Evidence And Quarantine Capacity Safety

- Preflight reserves projected journal, backup, evidence and quarantine capacity before granting workspace-write.
- Hard limits exist per file, run, project, account and host; exceeding any limit fails before Mutation commit and retains only bounded diagnostic metadata.
- Default initial limits, replaceable only by capacity ADR: 256 MiB changed bytes/run, 512 MiB quarantine/run, 2 GiB retained quarantine/project, 10 GiB/account and a host emergency reserve of the greater of 20 GiB or 15% of total volume capacity.
- New workspace-write is denied when the emergency reserve would be crossed. Journal/rollback reserved space is never consumed by ordinary evidence.
- Preflight preallocates or otherwise guarantees worst-case backup, rollback and bounded Acceptance-output space. Acceptance output is continuously metered; reaching its reservation cancels the runner and enters the normal rollback path before the emergency reserve is consumed.
- Raw quarantine export is packaged as non-executable data with manifest/checksums, content-disposition attachment, malware scan where available, no preview/import, explicit warning and named-admin authorization/audit.

## Tests

- lease double-acquire, heartbeat loss, stale process, restart and force-release
- project-key uniqueness and stale-holder fencing after takeover
- baseline conflict and no overwrite
- path/reparse/cross-account/protected/delete/rename limits
- crash after each Nth file and deterministic rollback
- same-volume enforcement and cross-volume rejection
- journal/evidence write failure cannot mark committed
- acceptance fail defaults to rollback
- preserved failure only when contract explicitly allows
- Permit revoke/cancel/timeout terminates process and reconciles lease/journal
- lease remains valid through Acceptance, Postflight and rollback
- accepted/failure workspace cannot be mutated between Acceptance result and durable Postflight manifest/signature
- post-commit third-party mutation produces rollback_conflict without overwrite
- quarantine cannot execute or leak cross-account content
- side-effect ledger detects and cleans temp/process/cache effects
- untrusted worker omission cannot hide side effects; supervisor-derived ledger and negative fixtures detect them
- capacity reservation, per-scope quota, emergency reserve and oversized quarantine tests fail safely
- every Mutation/Acceptance transition, rollback failure/conflict and restart replay is idempotent and browser-projectable
- recovery-blocked projects cannot obtain a new Permit/lease until verified manual recovery closure

## Acceptance

- Formal workspace hash returns to baseline after any rejected/rolled-back operation.
- No route reports success from process or Mutation state alone.
- Execution lease is released only after accepted/rolled-back result and its Postflight record are durable, or after audited rollback-conflict handoff; conflict/failure handoff retains the separate project recovery block.
- Journal survives service restart and is not writable by Codex identity.
- Every file-changing route is mapped or disabled.
- Acceptance supervisor, not generated content, owns heartbeat and trusted Acceptance Attestation.
