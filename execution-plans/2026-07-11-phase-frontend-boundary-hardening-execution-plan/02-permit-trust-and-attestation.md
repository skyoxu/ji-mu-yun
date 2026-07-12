# Permit Trust And Attestation

## Trust Architecture

### Hosted Permit

- Stored server-side in an additive metadata DB table or equivalent protected host store.
- Codex receives only opaque `permitId`.
- Permit payload is never accepted from browser, prompt, Work Declaration, or caller JSON.
- DB service identity can issue/claim/consume; Codex execution identity cannot read or write the store.

### Platform Development Attestation

- Uses ECDSA P-256 with SHA-256 or an accepted equivalent asymmetric algorithm.
- The canonical launcher is an authenticated signing client only. It holds no private signing key and cannot choose the signed payload.
- CI/reviewer receives public key only.
- PR code and repository workflows that execute changed code never receive private signing material.
- The attestation verifier is an independently protected trust anchor:
  - preferred: organization/security-owned reusable workflow pinned to immutable commit SHA; or
  - host-installed verifier binary with version, publisher, and SHA-256 pinned in protected CI/environment configuration.
- Verification must not call verifier source or tests from the reviewed PR.

### Signing Service Isolation

- Protected-path Preflight/Postflight signing runs in a remote organization/security-owned Attestation Authority under a separate administrative domain. A same-host signer is allowed only for local non-merge development evidence and can never satisfy protected-path CI.
- The private key ACL grants use only to the signing-service identity. Phase Web, Codex, tool workers, Acceptance runners, ordinary administrators, repository scripts, and CI cannot read, export, duplicate, or directly invoke the key provider.
- The signing endpoint uses authenticated local IPC or mutually authenticated service transport with an explicit caller allowlist, request size/time limits, nonce/replay protection, and append-only audit.
- The service signs only a Permit/run that it can load from the protected store and prove was launched by the canonical launcher. Caller-supplied Permit payload, diff, test result, evidence hash, completion state, or workspace path is never trusted.
- Signer binary/workflow version, publisher and SHA-256/immutable commit are pinned outside the reviewed repository. Upgrade requires the trust-boundary change-control procedure.
- The protected trust registry also pins the canonical launcher binary/workflow hash and caller identity. Repository-modified launchers cannot request protected signatures.
- Private signing keys are non-exportable HSM/KMS-backed keys controlled by the separate administrative domain. Compromise of the Phase host administrator does not grant signer administration or key use.
- A same-user in-process library, unrestricted local command, or generic signing endpoint is prohibited because it would create a signing oracle for Codex or compromised Phase code.

Platform Development uses two distinct signed artifacts:

1. `PreflightAttestation`: proves task scope, authority, Permit and allowed paths before work.
2. `PostflightAttestation`: proves the actual final diff, tests and evidence after work.

CI acceptance requires both. A valid Preflight attestation without matching Postflight attestation never authorizes protected-path merge.

HMAC may be used internally between trusted server components only when the verification secret never enters PR/CI execution. HMAC is prohibited for Platform Development attestation verified by CI.

## Permit Schema

Required scope fields:

- permitId, issuer, audience, keyId, signatureAlgorithm
- policyVersion/hash, profile, actorId
- accountId, projectId, taskId, routeId, subOperationId, runId
- operationMode, canonicalWorkingDirectory
- readPathsHash, writePathsHash, capabilitiesHash
- promptHash, baselineHash, buildVersion
- issuedUtc, notBeforeUtc, claimExpiresUtc, executionDeadlineUtc
- nonce, maxChangedFiles, maxChangedBytes, allowDelete

Non-applicable fields are explicit null and validated by Profile rules.

## Canonicalization And Signature

- Versioned canonical JSON, UTF-8, deterministic field order.
- Canonical rules cover null, timestamp precision, path case, separators, Unicode normalization, arrays, and numeric representation.
- Signature covers the complete canonical payload.
- Payload, server row, public attestation, and calculated canonical hash must agree.

### Versioned Source And Host Manifests

Postflight binds two manifest families because Platform commits, Hosted snapshot workspaces and Windows execution hosts do not preserve the same semantics:

1. Platform `SourceChangeManifest`: commit/tree-derived, binary-safe and independently reproducible by CI from base/final commits. Untracked entries are prohibited at trusted-test/Postflight time; every tested source entry must exist in the final commit.
2. Hosted `SnapshotChangeManifest`: derived from trusted baseline/final directory snapshots when a final Git commit is not part of the route contract. It covers every scoped entry, raw byte hash/length, add/modify/delete/rename and original/normalized case and binds upstream handoff/project baseline IDs.
3. `HostEffectiveManifest`: calculated by the protected host or remote runner supervisor while the lease is held. It binds the exact SourceChangeManifest or SnapshotChangeManifest candidate to Windows effective entries, ACL/security descriptor, reparse state, ADS, hard-link count/file identity and relevant attributes.

`exactDiffHash` and `changedPathManifestHash` derive from the applicable source/snapshot manifest. `finalWorkspaceHash` derives from the HostEffectiveManifest. Postflight signs all hashes, manifest versions and their common commit or snapshot binding. CI independently recomputes Platform SourceChangeManifest; Hosted verification recomputes the trusted snapshot delta from protected custody. Neither pretends to reconstruct host ACL/ADS/file identity from Git.

The SnapshotChangeManifest and HostEffectiveManifest deterministically cover every scoped directory entry, including:

- tracked and untracked files, additions, modifications, deletions and renames
- regular files, directories and explicitly rejected entry types
- raw file-byte SHA-256 and byte length without line-ending conversion
- normalized relative path plus original path spelling/case
- reparse/symlink target, hard-link identity/count and alternate data stream inventory
- relevant Windows attributes and ACL/security-descriptor hash for every readable or writable scoped entry

The HostEffectiveManifest rejects device/UNC/extended-device paths, reparse escapes, ADS, any writable regular file whose hard-link count is not exactly one, reserved device names, trailing dot/space aliases, 8.3 aliases, case-collision entries and entry replacement during enumeration unless an ADR-approved safe representation exists. Protected host components use the same library/version and golden vectors; CI uses the paired SourceChangeManifest implementation. Unknown or incompatible versions fail closed.

## Root Key Ceremony And Verifier Bootstrap

- Initial ECDSA public key fingerprint is approved by named security owner and approver through a decision log outside the reviewed change.
- Public key is installed in protected CI environment/reusable workflow configuration that ordinary PRs cannot modify.
- Attestation Authority non-exportable key generation, backup/continuity, rotation and destruction use HSM/KMS procedures under the separate administrative domain and are witnessed/audited.
- Public-key replacement requires old-key authorization or explicit break-glass ceremony with two named approvers.
- Verifier binary/workflow version and immutable hash/commit are pinned by protected configuration.
- Verifier unavailable or key configuration invalid fails closed for protected-path merge.

Break-glass cannot skip verification. It may install a new trusted verifier/key through a separately audited two-approver procedure, after which the normal check reruns.

### Initial Bootstrap Ceremony

The first trust implementation cannot attest itself. BH-SF0A therefore uses a one-time external bootstrap controlled outside the reviewed repository:

- two named security approvers review the exact signer/verifier/launcher/supervisor source and build instructions after BH-HANDOFF
- an external protected builder produces binaries/workflows and records source commit, toolchain, publisher and SHA-256
- approvers sign an offline bootstrap manifest containing initial public keys, key purposes, protocol versions, protected caller identities and binary hashes
- protected CI/Authority configuration installs that manifest through an organization/security-controlled change, then runs negative and known-answer tests
- normal Preflight/Postflight verification becomes mandatory for every later trust-boundary change; the bootstrap path is closed and cannot be reused as an ordinary exception

## Postflight Attestation

The protected Postflight supervisor, not Codex, computes the payload; the remote Attestation Authority validates and signs:

- permitId, taskId, actorId and policy/build/verifier versions
- baseCommit and finalCommit when committed
- canonical working-tree status
- exactDiffHash calculated from the versioned base/final SourceChangeManifest delta
- changedPathManifestHash
- finalWorkspaceHash and hostEffectiveManifestHash for scoped paths
- targetTestEvidenceHash and smokeEvidenceHash
- trustedTestAttestationHash and AcceptanceAttestationHash when those stages execute
- mutationJournalId and acceptanceEvidenceHash when applicable
- UpstreamHandoffManifest ID/hash/handoffEpoch, active StateEvent hash, ActiveRegistry rowVersion and Permit Authority restoreEpoch
- completion status and issuedUtc

CI independently calculates the reviewed PR diff/path manifest and compares it with the signed Postflight payload. A mismatch, missing test evidence, different base commit, changed protected path outside Permit, or unsigned completion fails.

### Trusted Test And Acceptance Attestation

A report file or `testEvidenceHash` is evidence content, not proof that a test ran. Protected-path completion requires either an independent CI rerun on the exact reviewed change or a signed Test Attestation issued by the remote Attestation Authority from protected runner-supervisor observations.

The Test/Acceptance Attestation binds:

- permitId/runId, base/final commit and exactDiffHash
- test/acceptance plan ID and normalized command/argument hash
- runner identity, restricted-token profile, executable/image hashes and environment-policy hash
- start/end time, timeout/cancellation outcome, exit code and structured result
- stdout/stderr/artifact hashes and evidence location
- applicable SourceChangeManifest/SnapshotChangeManifest plus HostEffectiveManifest versions and before/after hashes

The untrusted test/Acceptance child never owns a signing key. A protected supervisor identified by pinned binary hash, service SID and runner registration submits immutable observations over authenticated transport. The Attestation Authority validates runner key/certificate identity, Permit/run scope, command policy, candidate manifests and result before signing with a distinct `test-attestation` or `acceptance-attestation` key purpose. The protected runner trust registry, public keys, rotation, revocation and overlap follow the same independently administered ceremony as Platform attestation.

The Postflight signer loads the attestation from protected storage and verifies its signature, key purpose, runner registry and scope. Codex-authored test reports may be retained as untrusted diagnostics but cannot satisfy completion. CI must rerun or independently verify the trusted attestation; it never accepts a hash that is only asserted by the changed repository.

For Hosted mutations, the Attestation Authority also proves the matching Mutation lease is still held by trusted orchestration while the protected supervisor calculates the final SnapshotChangeManifest/HostEffectiveManifest pair and persists the Postflight record. Permit consumption and lease release occur only after that record is durable; a lease/run mismatch fails closed and enters reconciliation.

## Permit Database Semantics

Minimum columns/indexes:

- `permit_id` primary key
- `nonce` unique index
- scope columns or indexed scope hash
- status and row version
- issued/not-before/claim-expiry/execution-deadline timestamps
- claimed/executor/consumed/revoked metadata
- policy/build/key IDs
- boot ID, trusted wall deadline, maximum monotonic duration and last reconciled boot ID
- terminal reason/code, failure/aborted/postflight timestamps and trusted attestation/Postflight refs
- UpstreamHandoffManifest ID/hash/epoch, active StateEvent hash, ActiveRegistry rowVersion, Permit Authority restoreEpoch and source/snapshot/host manifest versions

Atomic claim uses one conditional transaction:

```sql
UPDATE permits
SET status = 'claimed', executor_id = @executor, claimed_utc = @now, row_version = row_version + 1
WHERE permit_id = @permit
  AND status = 'issued'
  AND not_before_utc <= @now
  AND claim_expires_utc > @now;
```

Affected row count must equal one. Duplicate claim, nonce collision, stale row version, or scope mismatch fails closed.

Permit Authority persistence additionally requires:

- additive migration and restore test
- backup/restore preserving nonce uniqueness, row version, fencing-relevant execution identity, boot/deadline data and attestation refs
- health endpoint/readiness for issue/claim/verify
- no issuance when primary store is unavailable or read-only
- restored `issued`, `claimed`, `executing`, `postflight_pending`, `consumed`, `expired`, `revoked`, `aborted` and `postflight_failed` rows reconciled against executor/process/journal/lease/attestation state; no terminal or in-flight row is reused
- read-only Codex policy explicitly decides whether operation may continue during Authority outage; workspace-write never starts
- every restore increments a protected monotonic restoreEpoch; Permit/attestation execution from an older epoch is rejected and reconciled, while historical terminal signatures remain verification-only

## Permit Lifecycle

Permit lifecycle is independent from Mutation and Acceptance:

```text
issued -> claimed -> executing -> postflight_pending -> consumed
  |         |           |               |
expired  revoked    revoked/aborted   postflight_failed
```

- Default unclaimed TTL: 5 minutes.
- Claim must occur before `claimExpiresUtc`.
- Claimed execution may continue only until policy-bound `executionDeadlineUtc`.
- Permit cannot return to issued and cannot be reused.
- Cancellation/revocation terminates the process and moves transaction handling to Mutation state.
- `aborted` covers launcher/executor failure before Postflight; `postflight_failed` covers signer, trusted-test, manifest or evidence failure after execution. Both are terminal and non-reusable.
- Every state transition is compare-and-swap/idempotent and records reason, actor/service identity, time and row version.
- Executor maintains a protected revocation control channel or bounded polling heartbeat. Revocation propagation target is 5 seconds; loss of the control channel blocks new tool requests and terminates workspace-write no later than the next 5-second check.
- Wall-clock rollback, leap, excessive skew or Authority time uncertainty blocks issue/claim and triggers reconciliation. TTL/deadline enforcement uses trusted UTC plus monotonic elapsed time after claim.
- Permit rows persist claim `bootId`, trusted wall deadline and maximum monotonic duration. Service/host restart changes bootId and forces protected reconciliation; it never reconstructs remaining monotonic time by extending the deadline.
- Revocation wins every compare-and-swap until the final `consumed` transaction commits. The final transaction atomically rechecks not-revoked, trusted attestations, durable Postflight and expected row version; concurrent revoke causes terminal revoked/reconciliation, never consumed.
- Issue, heartbeat, tool request, trusted apply and final consume revalidate the ActiveRegistry handoff/epoch/StateEvent/rowVersion, immutable manifest hash and Authority restoreEpoch. Handoff supersession/revocation, registry CAS drift or restore-epoch drift terminates workspace-write and reconciles Mutation/lease; an in-flight Permit cannot be rebound.

## Key Rotation And Revocation

- `keyId` identifies signer.
- Current and previous signing eligibility may overlap only for maximum unclaimed TTL plus 10 minutes clock-skew allowance.
- Previous key cannot sign or authorize newly issued attestations after rotation cutover, but its public verification record, key-purpose history, validity interval and revocation time remain available for at least the longest attestation/evidence retention period.
- Compromised keys support immediate revocation independent of overlap.
- Verifier key cache has bounded refresh and emergency purge.
- Key rotation/revocation is append-only audited.

## Permit Authority Compromise Boundary

- Public Web/API handlers cannot directly insert or update Permit rows.
- Permit issuance is exposed through a narrow internal authority interface with Profile/Policy validation.
- High-risk trust-boundary changes and platform protected paths require named approver evidence in addition to caller authentication.
- Authority service identity cannot modify project source or Mutation journal payloads.
- Permit Authority is process/service and identity separated before Hosted workspace-write is enabled. It independently loads the UpstreamHandoffManifest-bound route descriptor, server route state, approval evidence, account/project ownership and Work Policy; Phase Web may request issuance but cannot assert these authorization facts. A compromised Phase Web residual cannot waive this separation.

## Authority Availability And Disaster Recovery

- Define issue/claim/verify availability and latency SLO.
- Alert on store/verifier/key/clock/nonce failures.
- Authority outage blocks new workspace-write and Permit claim.
- Existing executing jobs may only finish through trusted journal/rollback paths; no new scope is granted.
- Backup restore drill covers issued, claimed, executing, consumed, expired and revoked rows.
- Split-brain or multi-writer Authority is prohibited without a consensus/unique-claim design.
- Initial SLO: issue/claim/verify monthly availability >= 99.9%; local Permit operations P95 <= 100 ms/P99 <= 250 ms; remote attestation request P95 <= 2 seconds/P99 <= 5 seconds excluding test execution; revocation propagation <= 5 seconds; alert acknowledgement <= 15 minutes; recovery-time objective <= 60 minutes; recovery-point objective <= 5 minutes. A stricter accepted ADR may replace these numbers.

## Central Factory Enforcement

- `workspace-write` requires a non-serializable `ValidatedExecutionPermitContext` produced by trusted verifier/store code.
- Raw Permit JSON or permitId alone cannot satisfy factory API.
- Missing, expired, replayed, revoked, wrong-audience, wrong-scope, wrong-prompt, wrong-workspace, or wrong-build Permit fails.
- Sandbox is a constrained enum; caller strings are rejected.
- Without valid Permit, only read-only commands may be constructed.
- Source guard blocks raw `codex exec` and alternate subprocess builders.

## Trust-Boundary Change Control

Permit authority, verifier, command factory, Work Policy registry, launcher, Mutation evaluator, journal, rollback, and CI verifier require:

- protected path authorization
- actual named owner and approver
- second security reviewer
- trust-boundary tests
- independently verified attestation

One task cannot change signer, verifier, enforcement code, public key configuration, and its own acceptance test without separate approval.

The trusted verifier must validate Postflight diff/test/evidence binding, not only the initial Permit signature.

## Acceptance

- CI verifies platform attestation using public key only.
- CI independently matches signed Postflight exactDiffHash/path manifest/base commit to the reviewed change.
- Signing service isolation, key ACL, authenticated request binding and signing-oracle negative tests pass.
- Protected-path completion uses independent rerun or trusted Test/Acceptance Attestation; forged report/hash tests fail.
- Platform SourceChangeManifest, Hosted SnapshotChangeManifest and HostEffectiveManifest golden vectors cover binary/rename/delete/case/ADS/hard-link/reparse/ACL and TOCTOU cases.
- PR cannot replace or bypass the trusted verifier used for its own check.
- Atomic claim passes concurrency/replay tests.
- Cross-actor/account/project/route/task/run use fails.
- Key rotation, compromise revoke, clock skew, expiry, service restart, and verifier cache tests pass.
- `workspace-write` cannot be built without trusted context.
- Authority outage, backup restore, root-key replacement and Postflight mismatch tests pass.
- Revocation propagation, clock rollback/skew and every terminal Permit recovery transition pass.
