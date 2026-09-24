# 8-24 Implementation Input Repair

Purpose: maintainer-repaired implementation input for the current Quick Dev TDD consumer. The user explicitly requested direct online repair and no further VDD Skill run.
Target: `execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery`.
Review baseline: `d8219f5a867e2a1bb2ed22c86f0437367617da06`.
Profile: resumable; dependent Windows identity/storage/recovery work crosses sessions.
Governance: development, off. This document grants no lifecycle state or production-write approval.
This is a repair of the existing scope, not a new product requirement or a replacement canonical Spec.

## Source authority and preservation

The compiler must consume the following current sources together, including unnumbered normative prose:

- [SPEC.md](../../_bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/SPEC.md)
- [ARCHITECTURE-SPINE.md](../../_bmad-output/planning-artifacts/architecture/architecture-phase-b-c-identity-isolation-workspace-recovery-2026-08-23/ARCHITECTURE-SPINE.md)
- [identity-and-ownership.md](../../_bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/identity-and-ownership.md)
- [runner-isolation.md](../../_bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/runner-isolation.md)
- [workspace-recovery-contract.md](../../_bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/workspace-recovery-contract.md)
- [api-evolution-and-operations.md](../../_bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/api-evolution-and-operations.md)
- [requirements-and-acceptance.md](../../_bmad-output/specs/spec-phase-b-c-identity-isolation-workspace-recovery/requirements-and-acceptance.md)

The 8-22 requirements and 8-23 PRD remain provenance as declared by SPEC; the refreshed SPEC and its six companions are the direct normative package. Preserve FR-001..FR-026 (including PRD variant intent FR-018a/FR-022a/FR-022b through their canonical companion clauses), NFR-001..NFR-007, PIWR-001..PIWR-040, PIWR-A01..PIWR-A18, CAP-1..CAP-7 and AD-1..AD-13. Do not turn a source into not_applicable because its Rule or paragraph lacks an independent PIWR ID.

The historical Round-3 mapping excluded all thirteen Architecture Rule paragraphs. Its dispositions are not a semantic waiver of the current Spec. Preserve historical files byte-for-byte; recompile current coverage from source and this repair input. Each excluded normative clause must now map to a behavior below, or to an explicit source-grounded non-goal. A broad acceptance reference alone is insufficient. If equivalent obligations merge, retain the original source clause and its distinct assertions.

No new source-freeze, signatures, Bootstrap review or authorization receipts are requested. Existing repair rounds, terminal results and TDD observations remain historical and cannot prove the repaired candidate. The original compiler run remains historical. This revision is an explicit maintainer-authorized input repair, not a new compiler run or a fabricated plan-ready/implementation result. Current Quick Dev consumes the repaired semantic bundle after its native preflight.

## Observed code gaps to guide controlled probes

These are source-review findings at the baseline, not runtime present/missing classifications:

| Surface | Source finding | Probe needed |
| --- | --- | --- |
| RequestContext | Used by new Workspace helpers, not the HTTP/queue/Runner identity chain | I02, I07, I08 |
| RunnerIsolationPolicy / HostedProcessRunner | ACL helper grants Environment.UserName; ordinary process launch does not select the descriptor identity or attach its isolation handle | R01, R02, R04, R05 |
| WorkspaceStorageService | Stores manifest in mutable source root without independent retained content | W03, W04 |
| SnapshotManifest | Lacks complete version/compatibility/recovery contract; extension filtering is not complete secret/transient exclusion | W05, W06 |
| RestoreService | Existing Attempt returned directly; lease checked at start, no full publication revalidation or restart reconciliation | T04, T05, T06, T07 |
| New storage/restore/migration helpers | Not wired to the real host composition and operations | W08, A01, A06 |
| Historical tests | Marker checks, unchanged-source copy and fresh-table reuse do not exercise promised acceptance | All corresponding boundary cases |

Retain working account-token scope, no-store, timeouts, hash checks, basic staging and existing regressions. Do not replace valid behavior to manufacture RED.

## Behavior contract and test intent

Case IDs below are stable repair-input identities, not observed tests or execution receipts.
Each row supplies a source, parent PIWR obligation, acceptance target, production lane, selector intent and stimulus/result oracle. The actor is the authenticated user/admin for HTTP cases, the server queue/startup reconciler for background cases, and the actual restricted OS process for OS cases. Every case requires its own assertion and diagnostic identity. Parameterized boundary categories need individual reported cases.

For each row, the failure intent is the negation of its stated observable result at the named production boundary. Missing selectors, build/import/tool failures, unsupported OS privileges and timeout are harness/environment blockers, not causal RED. A helper returning a constant or a marker file cannot satisfy a boundary oracle.

The compiler must emit the existing behavior-routing intent contract. Quick Dev probes current behavior: present -> regression plus terminal; missing -> causal RED/GREEN/REFACTOR plus terminal; mixed within a row -> finer atomic decomposition; unverifiable -> blocked. No observations are preassigned here.

Selectors are proposed new test methods in the lane classes below. They must be implemented against real production entrypoints before controlled probes. Until created and discovered they are not runnable acceptance evidence.

| Case | PIWR parents | Acceptance | Lane | Source clause owner | Proposed method / falsifiable behavior |
| --- | --- | --- | --- | --- | --- |
| <a id="SM-I01"></a>I01 | PIWR-001 | PIWR-A01, PIWR-A18 | L0 | identity-and-ownership.md | `ResolveContext_UsesServerRelations`: Resolve a valid credential with distinct principal, tenant and member records; return server roles and credential identity without equating tenant and principal IDs. |
| <a id="SM-I02"></a>I02 | PIWR-002, PIWR-010, PIWR-036 | PIWR-A01, PIWR-A17 | L0 | identity-and-ownership.md | `HttpContext_RejectsClientScopeOverride`: Send conflicting account, principal and role fields through protected HTTP routes; the server context and authorization remain credential-derived. |
| <a id="SM-I03"></a>I03 | PIWR-003 | PIWR-A18 | L0 | identity-and-ownership.md | `IdentityCompatibility_UsesDeclaredCredentialKinds`: Validate the OIDC-first integration/compatibility boundary and credential kinds; admin bearer remains bootstrap/migration/controlled-service only. Do not build a password system or invent an external provider deployment. |
| <a id="SM-I04"></a>I04 | PIWR-004 | PIWR-A02, PIWR-A18 | L0 | identity-and-ownership.md | `Credential_StoresLifecycleWithoutPlaintext`: Issue a credential and inspect authoritative storage: stable ID, scope, creation, last-use, expiry and revocation exist; stored secret material is securely derived. |
| <a id="SM-I05"></a>I05 | PIWR-004 | PIWR-A02 | L0 | identity-and-ownership.md | `Rotation_RejectsPreviousCredential`: Rotate a credential, then exercise cached and fresh protected requests; the predecessor cannot authorize beyond the five-second bound. |
| <a id="SM-I06"></a>I06 | PIWR-005 | PIWR-A02 | L0 | identity-and-ownership.md | `Disablement_RejectsNewActivity`: Disable an account, advance the clock through the bounded window, and attempt Run, Restore, Preview and private reads; all deny. |
| <a id="SM-I07"></a>I07 | PIWR-005, PIWR-010 | PIWR-A02, PIWR-A18 | L0 | identity-and-ownership.md | `QueuedWork_RevalidatesIdentity`: Queue authorized work, then disable/revoke before dispatch; the server creates an immutable RunContext containing only the server-authorized account, principal, project, workspace root, policy hash, lease and fencing data; dispatch must revalidate that context and must not widen its scope after enqueue. The real queue cancels or drains without granting a new write lease. |
| <a id="SM-I08"></a>I08 | PIWR-005 | PIWR-A02, PIWR-A13 | L0 | identity-and-ownership.md | `Disablement_BlocksPublication`: Disable during an atomic operation; permit only the declared atomic boundary, then deny publication and subsequent work with an audited outcome. The execution-boundary decision must read the real server-owned Account status; a test-local flag, closure state, or a value captured at enqueue time is not an authorization source. |
| <a id="SM-I09"></a>I09 | PIWR-006 | PIWR-A02 | L0 | identity-and-ownership.md | `RoleChange_ReevaluatesCapabilities`: Remove a role after session/queue creation; protected requests and deferred execution re-evaluate current capabilities from the real server-owned credential/role source. A test-local role collection or capabilities captured at enqueue time cannot prove this behavior. |
| <a id="SM-I10"></a>I10 | PIWR-007, PIWR-008 | PIWR-A02, PIWR-A18 | L0 | identity-and-ownership.md | `AdminLifecycle_IsAuthorizedAndAudited`: Exercise admin disable/enable/revoke with valid and insufficient roles; deny unauthorized actions and retain redacted audit records and recoverable data. |
| <a id="SM-I11"></a>I11 | PIWR-009, PIWR-010, PIWR-011 | PIWR-A03 | L0 | identity-and-ownership.md | `PrivateResources_RejectCrossAccountEnumeration`: Exercise Project, Run, Artifact, Package, Asset, Chat, Workflow, LLM usage, Workspace, Snapshot, Attempt and Preview ownership through their production boundaries; wrong-account and nonexistent targets reveal no target existence or paths. |
| <a id="SM-I12"></a>I12 | PIWR-009, PIWR-012 | PIWR-A04 | L0 | identity-and-ownership.md | `Ownership_RejectsOrphanAndConflictingRecords`: Read/adopt legacy, orphan and conflicting records through the metadata boundary; retain valid ownership and quarantine ambiguity without assigning it to the requester. |
| <a id="SM-I13"></a>I13 | PIWR-013 | PIWR-A15 | L0 | identity-and-ownership.md | `PrivateHttp_UsesNoStoreAndBoundedErrors`: Exercise private HTTP success, denial and internal failure; every response uses no-store and a bounded redacted envelope. |
| <a id="SM-I14"></a>I14 | PIWR-014 | PIWR-A08 | L0 | identity-and-ownership.md | `RunnerSecrets_AreScopedAndCleaned`: Dispatch through the real runner with fixture secrets; inject only authorized Run secrets, exclude platform environment secrets, clean after completion/cancel and block reuse if cleanup fails. |
| <a id="SM-R01"></a>R01 | PIWR-015, PIWR-016 | PIWR-A05 | L1 | runner-isolation.md | `WindowsRunner_UsesRestrictedProjectIdentity`: Launch a harmless file-operation process through the production runner factory on Windows; verify its actual token differs from the platform identity and can write only its authorized project roots. |
| <a id="SM-R02"></a>R02 | PIWR-016 | PIWR-A05 | L1 | runner-isolation.md | `WindowsRunner_DeniesForeignAndPlatformRoots`: From that restricted process bypass application path checks and attempt OS reads/writes to sibling Project, other Account, staging, secrets, platform binary/DB/proxy fixtures; OS denies access. |
| <a id="SM-R03"></a>R03 | PIWR-017 | PIWR-A06 | L1 | runner-isolation.md | `Paths_RejectAllEscapeForms`: Exercise server root resolution with traversal, rooted, UNC, device, symlink/reparse and root-link inputs across Workspace/Snapshot/Restore/Artifact; no escape is read or written. |
| <a id="SM-R04"></a>R04 | PIWR-018 | PIWR-A13 | L1 | runner-isolation.md | `RunnerLifecycle_BoundsChildrenAndWrites`: Exercise production heavy-write queue timeout, cancellation and cleanup; the restricted process is attached to a Windows Job Object before execution, child processes remain contained by that Job Object for lifetime and resource limits, child processes terminate on cancellation, and one Project cannot have simultaneous heavy writers. |
| <a id="SM-R05"></a>R05 | PIWR-019 | PIWR-A07 | L1 | runner-isolation.md | `AclDrift_BlocksLaunchAndPublication`: After create, restore, move and upgrade, expand ACL/inheritance or change owner; verify drift blocks launch/publication until protected audited repair succeeds. |
| <a id="SM-R06"></a>R06 | PIWR-020 | PIWR-A05, PIWR-A18 | L1 | runner-isolation.md | `IsolationClaims_RequireSelectedTierEvidence`: Read the production capability/profile projection; it exposes only the tested current tier and rejects selection or advertising of unsupported stronger tiers. Any isolation-tier upgrade or stronger-tier advertisement is denied until the complete evidence gate is present: accepted ADR, threat-model delta, unauthorized-access negative cases, lease/fencing proof, Snapshot/Restore rollback proof, redaction/readback proof, and compatibility evidence. |
| <a id="SM-R07"></a>R07 | PIWR-018, PIWR-038 | PIWR-A13 | L1 | api-evolution-and-operations.md | `Lease_PersistsAndFencesPublication`: Acquire/supersede a Project lease across process restart; SQLite fencing increases monotonically and stale Run/Restore holders fail at the publication boundary. |
| <a id="SM-W01"></a>W01 | PIWR-021, PIWR-037 | PIWR-A09, PIWR-A16 | L2 | workspace-recovery-contract.md | `WorkspaceIdentity_SurvivesPlacementChange`: Move a server-mapped workspace to another temporary root; workspace/account/project identity remains unchanged and supplied placement values cannot change ownership. |
| <a id="SM-W02"></a>W02 | PIWR-022, PIWR-039 | PIWR-A09, PIWR-A16 | L2 | workspace-recovery-contract.md | `StorageOperations_UseLogicalIdentity`: Exercise create/read/restore/lifecycle validation through the local storage contract using logical IDs; no caller-controlled host path becomes storage or ownership authority. |
| <a id="SM-W03"></a>W03 | PIWR-023 | PIWR-A09, PIWR-A10 | L2 | workspace-recovery-contract.md | `SnapshotContent_SurvivesSourceMutationAndLoss`: Create through the explicit service entry, change/delete the original files, then restore from retained snapshot content to a fresh root; recover the exact original bytes. |
| <a id="SM-W04"></a>W04 | PIWR-023 | PIWR-A09, PIWR-A14 | L2 | workspace-recovery-contract.md | `SnapshotVersions_RemainImmutable`: Create two versions and attempt to reuse an existing ID; preserve the first content, manifest and policy binding byte-for-byte. After a process restart, the same snapshot version, bytes, manifest and policy binding must remain byte-for-byte identical; policy changes must not mutate that already-published version. |
| <a id="SM-W05"></a>W05 | PIWR-023 | PIWR-A08, PIWR-A10 | L2 | workspace-recovery-contract.md | `Manifest_ContainsRequiredRecoveryContract`: Inspect a newly published manifest for schema/compatibility, stable IDs, creator/action/time, inventory/size/hash/exclusions, ACL-policy ref, recovery/rebuild/retention and applicable key reference; no plaintext key. |
| <a id="SM-W06"></a>W06 | PIWR-024 | PIWR-A08 | L2 | workspace-recovery-contract.md | `SnapshotBoundary_ExcludesUnsafeContent`: Use a mixed fixture with GDD/module/source/tests/artifacts plus cache/build/temp/secrets/tickets/absolute paths/links; include supported persistent data and exclude every prohibited category without following links. |
| <a id="SM-W07"></a>W07 | PIWR-023, PIWR-024 | PIWR-A08, PIWR-A14 | L2 | workspace-recovery-contract.md | `AdminPolicy_VersionsBlacklistForNewSnapshots`: Change extension policy through protected admin entry; new snapshots use the new version and exclusions while old snapshots remain unchanged; unauthorized policy changes deny. |
| <a id="SM-W08"></a>W08 | PIWR-025, PIWR-033 | PIWR-A09, PIWR-A17 | L2 | workspace-recovery-contract.md | `SnapshotRestore_RequireExplicitRequest`: Observe a new Project, ordinary edits, Run completion, migration and timers; none create a Snapshot or start Restore. An authorized explicit request does. |
| <a id="SM-W09"></a>W09 | PIWR-031 | PIWR-A14 | L2 | workspace-recovery-contract.md | `Quota_CountsLiveWorkspaceAndSnapshots`: Account for actual live Workspace and all Snapshot usage at user scope; reject over-limit writes/snapshots, reconcile after restart and do not reserve per-Project disk partitions. |
| <a id="SM-W10"></a>W10 | PIWR-009, PIWR-031 | PIWR-A04, PIWR-A14 | L2 | identity-and-ownership.md | `ProjectSoftDelete_ReleasesLogicalQuota`: Soft-delete a Project through its service entry; exclude it from normal lists/new operations, retain ownership/data for protected cleanup and release its logical quota exactly once. This row has three independently reported boundary assertions: `SM-W10.ProjectSoftDelete_ReleasesLogicalQuota` for exactly-once logical release, `SM-W10.ProjectSoftDelete_RetainsDataForProtectedCleanup` for ordinary-operation exclusion plus retained data, and `SM-W10.ProjectSoftDelete_RetainsOwnershipForProtectedCleanup` for retained original-owner resolution. No case may share a CER assertion marker or failure identity with either of the other two. |
| <a id="SM-W11"></a>W11 | PIWR-031 | PIWR-A14 | L2 | workspace-recovery-contract.md | `Retention_ProtectsPinnedAndActiveInputs`: Exercise pin, expiry, deletion and cleanup under the 30-day profile; preserve pinned/active-Attempt inputs, audit each action and refuse unsafe broad-prefix cleanup. |
| <a id="SM-W12"></a>W12 | PIWR-023, PIWR-024 | PIWR-A08, PIWR-A18 | L2 | SPEC.md | `SnapshotEncryption_UsesKeyReferenceBoundary`: Validate the accepted at-rest protection/key-reference profile on the fixture; an unavailable required key blocks recovery and plaintext keys never enter manifests, artifacts or readback. |
| <a id="SM-T01"></a>T01 | PIWR-025 | PIWR-A10, PIWR-A13 | L3 | workspace-recovery-contract.md | `RestoreRequest_BindsOwnershipAndIdempotency`: Submit explicit Restore through the protected service entry; bind requester, tenant, project, snapshot, target and key. Repeated equivalent requests return one operation; mismatched payload/tenant cannot reuse another attempt. |
| <a id="SM-T02"></a>T02 | PIWR-026 | PIWR-A10 | L3 | workspace-recovery-contract.md | `Restore_RejectsInvalidManifestBeforeMutation`: Try wrong tenant, unsupported schema/version, corrupt hash/size, unsafe paths and exhausted quota; typed denial occurs before ready publication and preserves the previous workspace. |
| <a id="SM-T03"></a>T03 | PIWR-026 | PIWR-A06, PIWR-A10 | L3 | workspace-recovery-contract.md | `Restore_RehashesStagingBeforePublication`: Alter staging or source between initial validation and copy completion; recompute staged size/content identity and reject drift before publication. |
| <a id="SM-T04"></a>T04 | PIWR-026, PIWR-019, PIWR-038 | PIWR-A07, PIWR-A13 | L3 | workspace-recovery-contract.md | `Restore_RevalidatesPublicationAuthority`: Change owner/ACL, account/credential status or lease after staging; final publication revalidates all boundaries and denies stale authorization. |
| <a id="SM-T05"></a>T05 | PIWR-025, PIWR-026 | PIWR-A10, PIWR-A11 | L3 | workspace-recovery-contract.md | `Publication_PreservesPreviousReadyWorkspace`: Inject failure around directory switch and metadata commit; either one verified current workspace is ready or a typed repair state is exposed, never partial content. |
| <a id="SM-T06"></a>T06 | PIWR-025, PIWR-028 | PIWR-A11 | L3 | workspace-recovery-contract.md | `Restart_ReconcilesEveryRestoreStage`: Kill a separate restore process after intent, during copy, after verification, during switch and before/after final metadata commit; restart reconciles from durable Attempt/staging without chat or the old process. |
| <a id="SM-T07"></a>T07 | PIWR-025, PIWR-028 | PIWR-A11 | L3 | workspace-recovery-contract.md | `Retry_AppendsHistoryWithoutStuckStaging`: Retry failed/interrupted attempts and repeat idempotent requests; append stage/outcome history, do not overwrite failure history or return Staging forever. |
| <a id="SM-T08"></a>T08 | PIWR-027 | PIWR-A12 | L3 | workspace-recovery-contract.md | `Restore_InvalidatesOldRuntimeCapabilities`: After restore exercise old preview tickets, PID/port references, secrets, Runner credentials and leases; none regain authority and current capabilities are newly allocated. |
| <a id="SM-T09"></a>T09 | PIWR-029, PIWR-030 | PIWR-A09, PIWR-A12 | L3 | workspace-recovery-contract.md | `RestoredWorkspace_ReentersHostedRoute`: Restore GDD/module/source/test/plan/artifact fixture, resolve all eight existing route authorities and current blocker, then perform account-scoped readback and a controlled harmless Run; stale/missing route authority blocks. Restored readback must expose only sanitized logical identifiers or relative paths within the Account scope, and any capability reference exposed by readback must be current and deny after expiry or revocation. |
| <a id="SM-T10"></a>T10 | PIWR-028, PIWR-031 | PIWR-A11, PIWR-A14 | L3 | workspace-recovery-contract.md | `InterruptedRestore_CleansOnlyOwnedStaging`: Cancel/fail restore; cleanup or quarantine only the Attempt-owned staging, protect active inputs and old ready content, and emit bounded failure and audit evidence. |
| <a id="SM-T11"></a>T11 | PIWR-032 | PIWR-A09, PIWR-A18 | L3 | workspace-recovery-contract.md | `SubstituteRootDrill_RecordsBoundedRto`: Use a nonempty representative fixture <=100 MiB and <=10000 files; measure snapshot-to-restored-controlled-run stages, content/ACL/route/readback/cleanup and P95 against 30 minutes with documented samples and approval-time exclusion. |
| <a id="SM-A01"></a>A01 | PIWR-033 | PIWR-A15, PIWR-A17 | L4 | api-evolution-and-operations.md | `AsyncOperations_OutliveBrowserDisconnect`: Invoke Snapshot/Restore/ACL repair through authenticated HTTP; return stable operation ID, bounded state and evidence pointer, disconnect the browser and verify durable execution/re-entry. |
| <a id="SM-A02"></a>A02 | PIWR-034 | PIWR-A04, PIWR-A16 | L4 | api-evolution-and-operations.md | `ApiEvolution_PreservesExistingClients`: Exercise existing token clients and old request/response shapes through the real host; additive fields and absent topology values preserve behavior. |
| <a id="SM-A03"></a>A03 | PIWR-035 | PIWR-A10, PIWR-A15 | L4 | api-evolution-and-operations.md | `Failures_UseBoundedRedactedFamilies`: Induce every declared failure family at its owning boundary; emit the typed family and safe public envelope, retaining raw exceptions only in controlled diagnostics. |

### A03 producer-boundary repair

The A03 evidence consumer must bind each failure family to its real producer,
not only to the HTTP envelope/readback layer. The implementation slice that
owns A03 may therefore change the producer paths for request diagnostics,
workspace/snapshot faults, and restore-attempt faults: `Program.cs`,
`PhaseAMetadataStore.cs`, `ArtifactReadbackService.cs`,
`WorkspaceStorageService.cs`, `RestoreService.cs`, and
`RunnerIsolationPolicy.cs`. These paths are included only to emit the typed
failure family, safe public projection, and controlled diagnostic correlation;
they do not transfer ownership of unrelated identity or runner behavior from
their existing slices. The S25 acceptance must retain all declared families
and its two present obligations, and must not authorize edits to selectors,
fixtures, historical evidence, or the plan contract itself.
| <a id="SM-A04"></a>A04 | PIWR-036 | PIWR-A01, PIWR-A17 | L4 | api-evolution-and-operations.md | `SessionProjection_ExposesServerCapabilities`: Read server session/capabilities after membership/role changes; browser caches or hidden controls cannot authorize protected operations. |
| <a id="SM-A05"></a>A05 | PIWR-037, PIWR-039, PIWR-040 | PIWR-A16, PIWR-A18 | L4 | api-evolution-and-operations.md | `TopologySeeds_DoNotCreateAuthority`: Exercise null/default/changed node, runner, sandbox, attempt and snapshot placement refs on one node; ownership and restore validity derive only from server records/content, without deploying a Worker fleet. |
| <a id="SM-A06"></a>A06 | PIWR-012, PIWR-034 | PIWR-A04 | L4 | identity-and-ownership.md | `RealSchema_UpgradesOldDataAndReusesDatabase`: Start with fresh and populated representative old schemas; invoke the same migration path as service startup, restart/reuse, and verify existing accounts/projects/runs/artifacts/ownership and new fields. Repeated CREATE on an empty DB is insufficient. |
| <a id="SM-A07"></a>A07 | PIWR-009, PIWR-012, PIWR-021 | PIWR-A04, PIWR-A09 | L4 | identity-and-ownership.md | `LegacyWorkspace_RequiresExplicitSafeMapping`: Adopt known old workspaces through server mapping plus containment/manifest/ACL checks; quarantine ambiguous ownership and preserve append-only lineage. |
| <a id="SM-A08"></a>A08 | PIWR-014, PIWR-033 | PIWR-A08, PIWR-A18 | L4 | api-evolution-and-operations.md | `Evidence_CorrelatesAndRedactsAllOperations`: Exercise identity, authorization, Run, Runner, Snapshot and Restore events; retain timestamp/status/action/principal/account/project/workspace/run-or-attempt/correlation and applicable node/runner, with secrets and raw host paths excluded. |
| <a id="SM-A09"></a>A09 | PIWR-040 | PIWR-A18 | L4 | api-evolution-and-operations.md | `NewProcess_ValidatesActualEvidence`: A new process independently validates current isolation, permissions, round-trip, fault, migration and redaction results; reject missing, stale, modified or unexecuted evidence, not merely a declared pass. |

Read the PIWR clause in the named source plus the unnumbered constraints surrounding it. W12 also binds SPEC AD-OQ-4. R02 includes the sibling-Project restriction in Architecture AD-4. Source-level direction/evolution constraints (I03, R06, A05) use a contract/composition oracle, not an invented runtime RED or an external system rollout.

## Architecture rules explicitly retained

All rows are applicable constraints; none are waived by a missing requirement ID.

| Architecture rule | Repair cases | Preserved obligation |
| --- | --- | --- |
| AD-1 | I01,I02,I11,I12,A07 | Server relations and explicit ownership; no orphan adoption. |
| AD-2 | I02,I07,I14,A01 | Persist/revalidate background identity; restricted server-created Run context, never broadened after dispatch. |
| AD-3 | I05,I06,I07,I08,I09,I10,T04 | Five-second maximum cache; drain only current atomic work, deny new leases/publication. |
| AD-4 | R01,R02,R03,R04,R05,I14,T04 | Actual per-Project identity, Job Object, NTFS boundary; sibling Projects also denied. |
| AD-5 | W01,W02,A05 | Logical identity independent of placement. |
| AD-6 | W03,W04,W05,W06,W07,W08,W12 | Explicit, immutable content plus complete manifest and versioned policy. |
| AD-7 | T01,T02,T03,T04,T05,T07,T10,A01 | Explicit durable Attempt, staged validation and one publication. |
| AD-8 | T05,T06,T07,A06,A09 | Durable DB/filesystem intent/outcome and startup reconciliation. |
| AD-9 | T08,T09,I14 | Rebuild runtime capabilities and consume existing route authority. |
| AD-10 | R07,T04,A05 | Single-node durable monotonic fencing; scale-out remains deferred. |
| AD-11 | I12,W10,A02,A06,A07 | Additive migration, explicit legacy adoption and soft delete. |
| AD-12 | I13,A03,A08,A09 | Sanitized derived readback; actual current evidence determines outcome. |
| AD-13 | R06,R01,R02,R07,T11,A05 | Do not select or advertise unproven stronger tiers; retain upgrade gate without implementing those tiers. |

## Non-functional coverage

| Requirement | Cases and required proof |
| --- | --- |
| NFR-001 | I11,I12,R03,R05,T02,T04,T05,T06,A03: fail closed and explicit DB/filesystem divergence handling |
| NFR-002 | I14,R02,R03,W06,W12,T02,A08: real boundary denial, secret exclusion and quota/bomb rejection |
| NFR-003 | W04,T01,T03,T05,T06,T07,R07: immutable content, idempotency, recomputed integrity and compensation |
| NFR-004 | I12,A02,A06,A07: real fresh/old-data upgrade/reuse and compatibility |
| NFR-005 | T06,T09,T11: restart, runnable substitute root and measured RTO |
| NFR-006 | I10,A01,A03,A08,A09: correlated events, bounded outcomes and verified evidence |
| NFR-007 | W09,W10,W11,T02: actual user usage, quota, soft delete and protected reclamation |

A18 is an evidence-consumer requirement across all behaviors, not a substitute for the other seventeen acceptance oracles.

## Dependency-scoped implementation lanes

These lanes guide compiler decomposition; they do not overwrite the compiler-owned current contract. Move necessary foundation schema/endpoint work into its earliest consuming lane; L4 validates integration and compatibility rather than withholding all wiring until the end.

| Lane | Behavior | Dependencies | Production entry / owner | Proposed targeted test class |
| --- | --- | --- | --- | --- |
| L0 | Identity and context | none | Program.cs authentication/session endpoints; PhaseAMetadataStore; shared queue/dispatch boundaries | PhaseB.Repair.IdentityBoundaryTests |
| L1 | Runner and OS boundary | L0 | HostedProcessRunner and command factory; RunnerIsolationPolicy; heavy-write queue and lease publication boundary | PhaseB.Repair.RunnerBoundaryTests |
| L2 | Immutable Snapshot and lifecycle | L0,L1 | Protected Snapshot/admin policy/Project lifecycle endpoints; WorkspaceStorageService; SnapshotManifest; quota storage | PhaseB.Repair.SnapshotBoundaryTests |
| L3 | Durable Restore and recovery | L0,L1,L2 | Protected Restore entry; RestoreService; startup reconciliation; hosted route/readback and controlled Run entry | PhaseB.Repair.RestoreBoundaryTests |
| L4 | API compatibility, migration and evidence | L0,L1,L2,L3 | Program.cs composition; actual SQLite startup migration; account-scoped operation readback and evidence verifier | PhaseB.Repair.OperationsBoundaryTests |

Each emitted slice must contain exact active obligation/case IDs, source refs, production entry, intended observable, selector, failure intent, green owner path, allowed/forbidden writes, downstream dependents and recovery. Agent context is a projection of this same contract, not independent authority.

## Write boundaries and recovery

The authorized online repair updates this input, current semantic/coverage/agent-context projections, case and dependency maps, handoff/navigation and deterministic validation sidecars. It also adds the necessary bounded .NET test binding to the Quick Dev RED entry guard, its regression tests and execution guide. It does not change Phase production code, executable target behavior tests or historical execution evidence.

No local VDD rerun is required for this revision. Quick Dev Q2 authors the declared test/fixture files; before a controlled probe and valid causal RED, no target production behavior is implemented. Concrete behavior tests belong to the controlled Quick Dev probe/RED stage; GREEN and REFACTOR repeat the same selector and assert the same obligation.

Future implementation owners are the existing Phase Security, Data, Runs, Workspaces and Readback modules plus narrow Program.cs endpoint/composition changes; not a whole-file Program.cs refactor. Future tests use disposable roots and SQLite data, the existing PhaseA.Platform.Tests project and bounded test utilities. Follow nearest AGENTS and ADR-0061 plus adopted ADR-0033..0038. Current input-repair authorization does not authorize protected auth/shared-runner production writes or live changes; the local implementation session must resolve applicable protected-path authorization before those edits.

Forbidden now and by default later: live metadata/Hosted workspaces under logs/phase-a-innernet, runtime startup/watchdog/Caddy changes, unrelated knowledge/Skill rewrites, upstream Spec rewrites to weaken acceptance, deletion or rewriting of old repair/terminal evidence, and implementation of deferred scope. Evidence goes under logs/phase-b-c-input-repair or the subsequent owned run directory.

After a local failure, preserve diagnostics, restore only disposable fixtures and re-probe the affected lane and dependents. Never repair live metadata to make tests pass, reuse another run's RED, change source hashes to bless a mismatch, or roll back correct production behavior for RED.

## Validation and terminal contract

Underlying .NET verification template, after actual test discovery (the current CER primary selector is the planned pytest wrapper):

```powershell
dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --filter "FullyQualifiedName~PhaseB.Repair.IdentityBoundaryTests" --logger "trx"
```

Replace the class with the exact lane class above; use exact method selectors for causal RED/GREEN/REFACTOR. The current case map and agent-context materialize concrete pytest commands; Q2 creates their real .NET boundary cases and validates exact discovery/TRX before formal RED. Avoid --no-build unless the current-source build artifact is verified. Test discovery and TRX must establish a nonzero count and the expected case IDs; localized console strings, return code alone or a silent early return are insufficient.

Terminal full command after targeted stabilization:

```powershell
dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --logger "trx"
```

The emitted terminal contract must additionally require actual non-skipped Windows OS permission/Job Object/ACL cases, persisted restart/fault scenarios, authenticated Snapshot-to-Restore-to-route/readback-to-controlled-Run evidence, real old-data migration, and independent A18 evidence validation. They should live in the existing test project or explicitly registered owned fixture runner; an unimplemented runner is a blocker. A whole-suite pass lacking any required category cannot publish implementation-complete.

Unavailable Windows identity privileges, missing symlink support, zero test discovery, build failure, timeout or a missing real host fixture produce blocked/not-verified, never pass or RED. Full production live backend is not necessary: a harmless real restricted child process proves the OS and controlled-Run boundary; injected model outputs may isolate unrelated model behavior but may not mock OS denial, persistence or publication.

T11 records fixture inventory, timestamps, samples and percentile calculation. A single tiny file or one untimed run cannot establish P95. Preserve the upstream <=100 MiB / <=10000 file bound and 30-minute target; do not invent a new mandatory fixture minimum or claim a representative distribution without evidence.

## Deliberate non-goals

React rebuild/UI E2E before its baseline; full Program.cs restructuring; multi-node fleet or distributed contention engineering; object storage/remote disaster recovery; per-execution identities, containers/microVMs; App Server/long-lived model sessions; Tasks/Taskmaster; unrelated Phase governance; physical account purge. They remain deferred under the current Spec, not failed mandatory runtime tests.

Do not defer current single-node OS isolation, durable fencing, current identity revocation, explicit async operations, retained immutable snapshot content, quota/soft delete, restart reconciliation or the required evidence. OIDC vendor/deployment specifics are an implementation-owned boundary decision, not permission to omit server-owned identity and credential contracts.

## Output boundary

This input is complete when its coverage and source references are checked. It is not plan-ready, implementation-complete or acceptance-passed. The next local action is current Quick Dev preflight and test authoring using [LOCAL-HANDOFF.md](LOCAL-HANDOFF.md). The user explicitly superseded the earlier requirement to re-run VDD. Native consumer validation and observed case evidence remain mandatory.

## Direct implementation repair clarifications

These clarify existing upstream duties; they do not expand product scope.
The seven canonical source files remain normative; planning instructions are
recorded in `input-repair-dispositions.v1.json`, outside the product runtime
obligation universe. Existing obligation and assertion IDs remain stable.

- AD-4: the real per-Project Runner must also be denied enumeration of the
  parent Account root while retaining access to its own authorized root.
- W06: explicitly include supported execution-plan/project work files and
  approved persistent user assets, under the same safety and extension policy.
- W03/RPO: an interrupted unpublished next Snapshot cannot replace the last
  successfully published integrity-verified recovery point.
- A01: browser disconnection must not terminate durable execution; a remaining
  cancelled or inert record alone is insufficient proof.
- W12: verify actual at-rest protection and successful recovery under the
  accepted key-reference profile, not merely a key-reference field.
- W09/W10: restarting quota reconciliation must preserve the exactly-once
  logical release for a soft-deleted Project even while physical bytes remain.
- W07: scan prohibited retained payload separately from legitimate policy and
  normalized exclusion metadata.
- T11: bind successful checks and timing to the same actual drill samples.
  Retain the existing fixture bounds and P95 target without inventing new
  minimum fixture size or sample-count requirements.

`implementation-case-map.v1.json` binds each atomic obligation to a planned
pytest node, assertions, failure intent and underlying .NET test identity.
`implementation-order.v1.json` defines actual slice dependencies; L0-L4 above
remain conceptual lane labels. No task is preclassified as present or missing.
