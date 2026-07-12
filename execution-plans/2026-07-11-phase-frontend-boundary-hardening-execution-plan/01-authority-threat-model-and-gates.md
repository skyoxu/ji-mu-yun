# Authority, Threat Model, And Gates

## Purpose

Define who and what is trusted before Permit, containment, Mutation, or React implementation begins.

## Threat Actors

The threat model must cover at least:

1. Normal user attempting cross-account or host access.
2. Malicious project files, GDD text, uploaded assets, prompts, or route recovery artifacts.
3. Codex following an unsafe or injected instruction.
4. Codex process escaping focused workspace through absolute paths, reparse points, child processes, environment variables, registry, temp paths, or network.
5. Platform Development Codex modifying its own verifier, policy, tests, CI checks, or evidence.
6. Compromised focused workspace or stale baseline.
7. Compromised Phase service account or host admin credential.
8. Modified CI workflow or untrusted PR code attempting to obtain signing material.
9. Replay, scope confusion, or cross-project use of a valid Permit.
10. Crash during multi-file writeback, rollback, or acceptance.
11. Compromised npm package, registry, lockfile, build tool, React bundle, or deployment artifact.
12. Compromised Phase Web or same-user Platform Codex attempting to invoke the signer/key provider as an oracle.
13. Forged test/evidence files that claim success without a trusted runner execution.
14. Generated Godot/C#/asset/import content attacking the Acceptance runner or host.
15. Windows effective-content/path tricks hidden from text diff: untracked/binary/ADS/hard-link/reparse/device/alias/case/TOCTOU.
16. Evidence/quarantine volume exhaustion consuming journal, DB or rollback capacity.
17. Downstream work starting before the upstream GDD-to-module plan is committed and closed, producing competing route/status/readback/UI/schema/standards owners.
18. A stale or selectively assembled upstream handoff omitting deferrals, compatibility obligations, dirty files, migrations or closure blockers.

## Trust Boundaries

```text
User / Project Input                         Untrusted
Codex Prompt And Work Declaration            Untrusted claims
Focused Workspace                            Untrusted mutation area
Codex Tool Child Processes                   Untrusted execution
Phase Route Service                          Trusted orchestration
Permit Authority / Trusted Store             Trusted authorization
External/Pinned Attestation Verifier         Independent trust anchor
Remote Attestation Authority / Private Key   Separate-admin-domain trust anchor
Mutation Lease And Journal Store             Trusted transaction state
Upstream Route Contract / Acceptance         Trusted business authority
Restricted Acceptance Runner                 Untrusted execution, trusted supervisor
Test/Acceptance Attestation Store             Trusted protected evidence
CI Running Repository Code                   Not trusted with private signing keys
```

## Security Invariants

- Untrusted content never grants capability.
- Codex output never signs or approves itself.
- CI that executes repository code never receives a private attestation key.
- Codex, Phase Web, Phase host administrator, repository tests and CI cannot read the private key or invoke an unrestricted signing endpoint; protected signing is outside the Phase host administrative boundary.
- A test report hash is not execution proof; protected completion requires an independent rerun or trusted runner attestation.
- Generated project content executes only in restricted Acceptance containment.
- Effective workspace content is bound by a binary-safe versioned manifest, not text diff alone.
- Hosted workspace-write cannot start without Permit, containment, lease, and Work Policy.
- A valid Permit is usable only once and only for its exact actor/scope/hash/audience.
- Mutation committed does not mean route accepted.
- Acceptance failure defaults to rollback and isolated evidence retention.
- Public React shell contains no account data, secret, token, host path, or privileged version detail.
- No downstream implementation task exists or runs before BH-HANDOFF validates the complete upstream delivery.
- The handoff-only task cannot modify the validator, mutation fixtures, bootstrap contract, this plan/spec or the rules used to authorize itself.
- Upstream route/status/readback/diagnostic/UI/GDD contracts remain business authority; downstream artifacts carry their handoff source IDs/hashes and never redefine them.
- A remote signature over observations from a host-admin-compromisable supervisor is not proof against host-admin compromise. Protected completion under that threat requires hardware-backed measured runner identity or a separately administered remote runner; otherwise the residual risk is explicit and the stronger claim is prohibited.

## Gates

### BH-HANDOFF: Completed Upstream Delivery

This is the first and non-bypassable Gate. After upstream declares completion, exactly one handoff-only verification task may be created to run the already-frozen validator and collect/validate evidence. It cannot implement or modify the validator/rules/plan/spec, Phase source/tests/runtime/DB/React/standards/business contracts. BH-HANDOFF must pass before creating or activating BH-SF0A or any later downstream phase task.

### Frozen BootstrapHandoffContract

Before the handoff-only task exists, two named approvers outside that task sign a versioned `BootstrapHandoffContract`. This is a downstream planning/security artifact, not an upstream business deliverable. It freezes:

- schema IDs/versions for UpstreamHandoffManifest, UpstreamHandoffStateEvent, UpstreamHandoffActiveRegistry, UpstreamCompletionSnapshot and HandoffSourceMap
- UTF-8 RFC 8785 canonical JSON, SHA-256 content hashing, forward-slash repository-relative paths, explicit Windows case/alias normalization and Ed25519 signatures over `schemaId + schemaVersion + canonicalPayloadHash + signerKeyId`
- pinned validator executable/workflow digest, mutation-fixture digest, bootstrap public-key fingerprints and allowed signature backend
- one selected external lock backend: protected CI/environment concurrency plus branch protection, or an offline host-maintenance lock that disables non-handoff launch identities and applies verified write denial outside the handoff allowlist
- lock owner, monotonic fencing token, acquisition/renewal/release/recovery procedure, maximum lifetime and proof that every task creation/process launcher is blocked or disabled while the lock is active
- complete task-creator/process-launcher inventory hash, inventory source refs and negative proof for every omitted/disabled launcher
- protected ActiveRegistry backend/transaction locator, two evidence-custody locators, external timestamp/commitment provider and receipt schema
- immutable handoff-task write allowlist and HandoffSourceMap schema

Canonical local readback path is `logs/phase-a-innernet/reviews/platform-boundary-hardening/upstream-handoff/bootstrap/<contractId>.json`; authority remains the two signed custody copies and external commitment named by the contract. The local copy is never sufficient by itself.

The handoff task cannot change this contract. Missing external lock enforcement, incomplete launcher inventory, unpinned verifier/rules, unsupported canonicalization, unavailable custody/registry backend or a changed contract hash fails BH-HANDOFF. The stronger general-purpose Attestation Authority remains BH-SF0A/B work; it is not required to validate this bootstrap contract.

Required upstream conditions:

- the final ready commit contains the whole tracked `2026-07-07` split directory and machine-contract bundle and the source-history guard passes; prior upstream work may remain as multiple commits
- upstream Phase 0A, 0B and Phase 1-6 exit evidence pass with zero unresolved P0/P1/P2 findings
- upstream capability/compatibility rows may remain `explicitly_deferred` only where the upstream ledger itself permits that state and supplies owner, expiry/recheck and evidence; a deferred capability row is never treated as an unresolved review finding
- upstream global review and split-added ledger closure pass
- durable standards/ADR/workflow/index destinations have landed
- the implementation worktree is clean for upstream-owned paths and the handoff commit is immutable for downstream planning
- a repository handoff lock prevents new upstream implementation tasks/runs while the completion snapshot and manifest are produced

### UpstreamHandoffManifest

Immutable manifest path:

```text
logs/phase-a-innernet/reviews/platform-boundary-hardening/upstream-handoff/<handoffId>.json
```

Required fields/hashes:

- identity: handoffId, monotonic handoffEpoch, upstream plan ID, final commit/branch, createdUtc, upstream/downstream approvers, BootstrapHandoffContract hash and signature/evidence refs; lifecycle status is not stored in this immutable object
- phase closure: Phase 0A/0B/1/2/3/4/5/6 exit evidence refs/hashes, global review ref/hash, unresolved-finding count and accepted-deferral rows
- actions/status/routes: exact existing upstream `workflow-action-contracts.v1.json`, route module/status/path-policy fixtures and existing recovery/readback/acceptance refs/hashes
- frontend/API: existing upstream browser/E2E/compatibility refs plus `DownstreamFrontendSurfaceInventory` and `DownstreamApiObservationSnapshot` hashes marked `downstream_derived`
- UI/diagnostics: capability inventory, UI style profile/field map, diagnostic taxonomy/quality-gate and closure-ledger hashes
- persistence: existing upstream migration/DB evidence refs where present plus a `DownstreamPersistenceObservationSnapshot` hash marked `downstream_derived`; absence of an upstream schema registry cannot be repaired by inventing upstream ownership
- standards: upstream-owned section anchors/canonical section hashes and owners; whole-file hashes are evidence only and do not freeze downstream-owned sections
- compatibility: `must_preserve`, `time_bounded_compatibility` with owner/expiry/removal test, and `eligible_for_removal` lists
- implementation baseline: upstream-owned path manifest hash, final commit ancestor rule, tracked split-plan inventory and UpstreamCompletionSnapshot hash
- completion snapshot: repository handoff-lock ID, capture start/end commit, scoped `git status --porcelain=v2` hash, upstream-owned dirty paths empty, active upstream task IDs empty, active run/lease/process IDs empty, claimed path inventory and capture timestamps

Missing, stale, untracked, unsigned, mismatched or selectively omitted fields fail closed. Upstream-permitted capability/compatibility deferrals do not silently become downstream work: each must name whether this plan consumes, preserves or explicitly excludes it, with owner and Gate.

### HandoffSourceMap And Derived Snapshots

Every manifest field has one source-map row with `fieldPointer`, `sourceClass`, `sourcePath`, `sourceJsonPointer`, `sourceHash`, `transformId`, `outputHash`, `authorityOwner` and `notApplicableReason`. Allowed source classes are:

- `upstream_committed`: tracked upstream fixtures, standards or source at finalCommit
- `upstream_exit_evidence`: immutable upstream phase/global/closure run evidence
- `downstream_derived`: deterministic read-only observation generated from finalCommit or a protected DB backup without changing upstream code/contracts/data

Minimum source-map bindings are fixed rather than discovered ad hoc:

| Manifest family | Required source |
| --- | --- |
| Phase closure | `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-<n>-exit-review-<run_id>.json` refs selected by the upstream implementation summary; `latest` files are pointers only |
| Global/ledger closure | upstream final implementation summary refs, `96-global-review-standard.md`, `97-split-added-requirements-ledger.md`, `99-source-coverage.md` and their immutable review/closure evidence refs |
| Action/route/status | upstream `schemas/workflow-action-contracts.v1.json`; `PhaseA.Platform.Tests/Fixtures/route-action-descriptors.v1.json`, `route-module-contracts.v1.json`, `route-status-vocabulary.v1.json`; matching finalCommit runtime owners |
| UI capability/style | upstream `schemas/gdd-to-module-capability-inventory.v1.json`, `godot-ui-style-contract.v1.profile.json`, `godot-ui-style-contract.v1.field-map.json`, `split-added-acceptance-registry.v1.json` and referenced durable standards |
| Diagnostics/closure | upstream Phase 6 exit refs, diagnostic standards and full-target closure-ledger refs selected by that exit evidence |
| Frontend/API observation | finalCommit `PhaseA.Platform/Browser/**`, `Program.cs`/endpoint/DTO/auth/error owners and relevant `PhaseA.Platform.Tests/**`; output is downstream-derived |
| Persistence observation | finalCommit metadata-store/migration owners plus protected metadata DB backup/schema inspection; output is downstream-derived and never mutates live DB |
| Compatibility | upstream `02c-frontend-migration-compatibility.md`, Phase 6 exit refs and finalCommit characterization tests; downstream adds only technical preservation indexing |

`DownstreamFrontendSurfaceInventory` observes existing browser routes/renderers/E2E cases. `DownstreamApiObservationSnapshot` observes frozen handlers/DTOs/auth/error behavior and may generate OpenAPI for React tooling. `DownstreamPersistenceObservationSnapshot` observes schema objects, migration markers and table/index usage from a protected copy/backup. Each contains source hashes and `authorityOwner=downstream_technical_observation`; none may claim upstream business ownership. If a required observation cannot be generated deterministically, BH-HANDOFF fails and records a downstream blocker; it does not reopen the upstream plan.

### Lifecycle State And Active Registry

- `UpstreamHandoffStateEvent` is append-only and signed. It records `eventId`, `handoffId`, `handoffEpoch`, `state=active|superseded|revoked`, `previousEventHash`, reason, trigger evidence, createdUtc and approvers.
- `UpstreamHandoffActiveRegistry` is a protected single-row CAS registry containing current handoffId/epoch/stateEventHash/rowVersion. It is a selector, not evidence; the signed event chain is authority. Executable work requires the selected event state to be `active`; `revoked` may intentionally leave zero executable handoffs, but never more than one.
- BootstrapHandoffContract records the protected registry locator and both append-only custody locators. A local `active-registry-latest.json` may exist only as a non-authoritative readback pointer.
- Activation first durably acknowledges both custody copies and the external commitment, then one protected transaction persists the initial state event and CAS-updates the registry. Concurrent activation, duplicate epoch or partial transaction fails; pre-transaction evidence remains orphaned/non-active.
- Revocation durably acknowledges both event custody copies/commitment, then persists the event and registry CAS in the same protected transaction. Replacement activation atomically persists the old-handoff `superseded` event, new-handoff `active` event, monotonic new epoch and registry CAS after all new bundle custody acknowledgements. A failed transaction leaves the previous registry/event authoritative; immutable manifests are never edited and no gap or dual-active state is allowed.

Every task start, Permit issue/heartbeat, trusted apply and Postflight revalidates the active handoffEpoch, final commit ancestry, upstream-owned path manifest and deferral expiry/recheck triggers. Legitimate downstream commits may advance HEAD outside upstream-owned paths without changing the immutable handoff. Any upstream-owned hotfix/path drift, expired deferral or new upstream task supersedes the handoff, blocks new work and revokes/reconciles bound Permits and leases until a new signed handoff is approved.

Supersession never directly rebinds an in-flight task. Unapplied isolated-workspace changes become `handoff_invalidated` and require a fresh task/Permit plus full revalidation. Applied but unfinalized changes enter rollback or named manual recovery. Test/Postflight evidence from the old epoch remains historical-only and cannot satisfy the new handoff. Allowed dispositions are `abandoned`, `rolled_back`, `manual_recovery_required` or `restart_required`; there is no `rebind` transition.

Handoff signing does not depend on the not-yet-built downstream Attestation Authority. It uses only the signature backend and key fingerprints frozen by BootstrapHandoffContract. BH-SF0A later bootstraps the stronger downstream Authority from this handoff root.

The handoff-only task obtains the externally enforced repository handoff lock, confirms upstream phase/global completion, invokes only the organization-controlled reusable verifier workflow or host-installed verifier binary selected and pinned by BootstrapHandoffContract, and runs the protected evidence collector. It does not execute a verifier from the reviewed repository. It then captures the completion snapshot and rechecks lock fencing/HEAD/active-task/dirty state immediately before signing. Any concurrent upstream task/run/path claim aborts the handoff.

Its write allowlist is limited to append-only handoff manifest/source-map/snapshot/state-event evidence under `logs/phase-a-innernet/reviews/platform-boundary-hardening/upstream-handoff/**` and the protected active-registry CAS operation. Validator, tests/fixtures, this plan/spec, the `2026-07-07` directory, Phase source/tests, runtime, live metadata/workspaces, standards/ADR/workflow, React assets and business fixtures are read-only. The task declaration, BootstrapHandoffContract, external lock and both completion captures carry the same allowlist hash; any extra changed path fails BH-HANDOFF.

`UpstreamCompletionSnapshot` is the canonical signed object for both captures. It contains the repository handoff-lock ID, capture sequence `before_manifest|before_signature`, start/end commit, scoped `git status --porcelain=v2` bytes/hash, upstream-owned dirty paths, active upstream task/run/lease/process IDs, claimed-path inventory/hash and capture timestamps. Both captures must show the same final commit and zero active/dirty/overlap rows; otherwise the manifest is not signable.

### BH-SF0A Entry: Downstream Trust Foundation

Required after BH-HANDOFF:

- actual downstream task, owner/backup/approver/incident/rollback identities and protected-path authorization
- accepted downstream threat model and general-purpose Authority bootstrap ceremony; the BH-HANDOFF bootstrap contract remains immutable
- external verifier/remote Authority/hardware-or-remote runner decision
- non-symmetric CI attestation and paired manifest design

### BH-REACT1 Entry Summary

Required only after BH-RP1 signed exit and active-registry revalidation:

- frontend surface and API/auth/error observations resolve from the same handoff-bound downstream-derived snapshots; upstream fixtures/E2E/compatibility refs remain business authority
- public HTTPS/session/CSRF/security-header Gate passes
- migration changes technical renderer/client ownership only and do not change upstream business status/action/readback semantics

### BH-ARCH Entry Summary

Required only after BH-REACT2 signed exit:

- architecture violation baseline/ratchet and upstream compatibility preservation list accepted
- DownstreamPersistenceObservationSnapshot and any existing upstream migration refs match the handoff
- standards section ownership and release/rollback compatibility decisions accepted

## Accountability Gate

Before task implementation, the work ledger must contain actual identities, not only roles:

- primary owner
- backup owner
- approver
- incident contact
- rollback decision owner

The canonical accountability artifact is an append-only signed task-ledger row containing `taskId`, `phase`, `handoffId/epoch`, all five identities, protected-path authorization ref, predecessor exit hash, createdUtc and rowVersion. Unassigned values, duplicate active owners or a missing signature block task start. A plan approval does not authorize protected path changes.

## Acceptance

- Threat model includes every actor and invariant above.
- Each mitigation maps to a test, control, or accepted residual risk.
- No P0/P1 threat remains with owner `TBD`.
- Gate status is machine-readable and referenced by every downstream task.
- A mutation test that removes or changes any handoff commit/evidence/fixture/schema/standards/compatibility hash blocks every downstream phase.
- No downstream task/path overlaps an upstream-owned active task or introduces a second business contract owner.
- Handoff predicate inputs come only from the externally fenced repository handoff lock, upstream phase/global closure evidence, `logs/ci/active-tasks/*.active.json`, task/run latest pointers, mutation lease/journal stores, process-liveness checks and twice-captured scoped Git status/HEAD; prompt or caller claims are ignored. The BootstrapHandoffContract must prove that all task creators and process launch identities are fenced, so a task cannot appear after the second capture and before activation.
