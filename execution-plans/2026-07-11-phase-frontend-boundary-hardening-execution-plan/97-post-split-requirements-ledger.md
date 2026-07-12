# Post-Split Requirements Ledger

## Rules

- Stable IDs use `PBR-###`.
- Pre-fourth-review normalized finding IDs use `PF-###`; legacy requirements never use an ambiguous `prior` source.
- Each active entry names source finding, exactly one owner book, exactly one implementation phase, requirement, acceptance and implementation evidence family.
- Entries are never deleted; superseded entries record replacement ID/reason.
- Fourth-review finding IDs use `F4-P0-##`, `F4-P1-##` and `F4-P2-##`. The Finding Coverage table must contain every fourth-review finding exactly once and may map one finding to multiple owner requirements when implementation responsibilities split.
- Fifth-review upstream-coordination IDs use `F5-P0-##`, `F5-P1-##` and `F5-P2-##` and follow the same complete-coverage rule.
- Sixth-review derivation IDs use `F6-##` and cover handoff bootstrap, runtime epoch, internal-state authority and deterministic sequential execution regressions.
- Seventh-review bootstrap-closure IDs use `F7-P0-##`, `F7-P1-##` and `F7-P2-##`.
- Eighth-review whole-directory IDs use `F8-P0-##`, `F8-P1-##` and `F8-P2-##`.
- Ninth-review schema-closure IDs use `F9-P0-##`, `F9-P1-##` and `F9-P2-##`.
- Requirement status defaults to `active`. A requirement becomes `superseded` only through the machine-parsed Requirement Status Registry; prose in the requirement column cannot change status.
- Every active row has a stable acceptance URI `phase-boundary://requirements/<PBR-ID>/acceptance`; the URI resolves to that row's owner, phase and acceptance family and is unique across the ledger.

## Requirements

| ID | Source finding | Owner | Phase | Requirement | Acceptance ref | Acceptance family |
| --- | --- | --- | --- | --- | --- | --- |
| PBR-001 | PF-001 | 02 | BH-SF0B | Platform Postflight attestation binds source/host manifests, tests and evidence | phase-boundary://requirements/PBR-001/acceptance | CI recomputation/trust-chain/signature tests |
| PBR-002 | PF-002 | 04 | BH-SF3 | Mutation lease remains held through Acceptance, durable Postflight and rollback | phase-boundary://requirements/PBR-002/acceptance | concurrency/Postflight-race/rollback-conflict tests |
| PBR-003 | PF-003 | 06 | BH-RELEASE | Previous bundle rollback requires current DB schema compatibility | phase-boundary://requirements/PBR-003/acceptance | current/previous binary schema matrix |
| PBR-004 | PF-004 | 02 | BH-SF0A | Root public-key ceremony and immutable verifier bootstrap | phase-boundary://requirements/PBR-004/acceptance | key replacement/break-glass tests/evidence |
| PBR-005 | PF-005 | 02 | BH-SF0B | Permit Authority outage/backup/restore/fail-closed | phase-boundary://requirements/PBR-005/acceptance | DR and availability evidence |
| PBR-006 | PF-006 | 03 | BH-SF1 | Tool broker validates IPC, executable, args, paths, env and output | phase-boundary://requirements/PBR-006/acceptance | broker negative tests |
| PBR-007 | PF-007 | 03 | BH-SF1 | Controller cannot directly mutate project files | phase-boundary://requirements/PBR-007/acceptance | containment tests |
| PBR-008 | PF-008 | 05 | BH-REACT1 | Session bootstrap, exact Cookie/CSRF/TTL policy | phase-boundary://requirements/PBR-008/acceptance | auth/CSRF/session tests |
| PBR-009 | PF-009 | 05 | BH-REACT1 | Legacy raw-token Cookie is actively expired | phase-boundary://requirements/PBR-009/acceptance | cutover/browser tests |
| PBR-010 | PF-010 | 05 | BH-REACT1 | Trusted Caddy forwarded headers and origin/rate-limit identity | phase-boundary://requirements/PBR-010/acceptance | proxy spoof/downgrade tests |
| PBR-011 | PF-011 | 04 | BH-SF3 | Quarantine is no-execute, restricted and account-safe | phase-boundary://requirements/PBR-011/acceptance | ACL/readback tests |
| PBR-012 | PF-012 | 04 | BH-SF3 | Non-file side effects use trusted supervisor ledger/cleanup | phase-boundary://requirements/PBR-012/acceptance | process/temp/cache/network tests |
| PBR-013 | PF-013 | 96 | BH-HANDOFF | Superseded by PBR-033 because the original validator entry lacked mandatory early-phase/phase-exit timing | phase-boundary://requirements/PBR-013/acceptance | replacement-reference validation |
| PBR-014 | PF-014 | 07 | BH-SF4 | Stable evidence path and immutable run-id evidence | phase-boundary://requirements/PBR-014/acceptance | evidence path tests |
| PBR-015 | PF-015 | 07 | BH-SF4 | Permit/verifier availability and recovery telemetry | phase-boundary://requirements/PBR-015/acceptance | SLO/alert/DR evidence |
| PBR-016 | F4-P2-04,F5-P2-03 | top-level | BH-HANDOFF | Plan remains paused until upstream handoff, actual owners and authorization exist | phase-boundary://requirements/PBR-016/acceptance | recovery metadata check |
| PBR-017 | F4-P0-01 | 02 | BH-SF0B | Remote signing service is separately administered and cannot be used as an unrestricted signing oracle | phase-boundary://requirements/PBR-017/acceptance | key/caller/launcher/signer isolation tests |
| PBR-018 | F4-P0-02 | 02 | BH-SF0B | Protected completion uses independent rerun or Authority-signed Test/Acceptance Attestation | phase-boundary://requirements/PBR-018/acceptance | forged-runner/report and exact-candidate tests |
| PBR-019 | F4-P0-05 | 02 | BH-SF0B | Paired source/snapshot/host manifests bind Platform Git, Hosted snapshot and Windows-effective content | phase-boundary://requirements/PBR-019/acceptance | binary/ADS/hard-link/reparse/ACL golden vectors |
| PBR-020 | F4-P0-03 | 03 | BH-SF1 | Acceptance runner executes generated content under restricted no-network containment | phase-boundary://requirements/PBR-020/acceptance | Godot/build/preview escape and orphan-process tests |
| PBR-021 | F4-P0-04 | 04 | BH-SF3 | Side-effect evidence is supervisor/OS-derived rather than worker self-report | phase-boundary://requirements/PBR-021/acceptance | omission and undeclared-side-effect fixtures |
| PBR-022 | F4-P1-01 | 03 | BH-SF1 | Tool broker local IPC has protected ACL, mutual identity, nonce/sequence and replay denial | phase-boundary://requirements/PBR-022/acceptance | Named Pipe protocol negative tests |
| PBR-023 | F4-P1-02 | 02 | BH-SF0B | Permit revocation propagates in real time and wins final consume races | phase-boundary://requirements/PBR-023/acceptance | revoke/control-channel/CAS tests |
| PBR-024 | F4-P1-04 | 04 | BH-SF3 | Internal Mutation/Acceptance transaction states persist finalization and recovery without redefining upstream route/readback status | phase-boundary://requirements/PBR-024/acceptance | state-transition and upstream-mapping/non-leakage tests |
| PBR-025 | F4-P1-05 | 03 | BH-SF1 | Windows path enforcement rejects ADS/hard-link/device/UNC/alias/case/TOCTOU escapes | phase-boundary://requirements/PBR-025/acceptance | path boundary mutation tests |
| PBR-026 | F4-P1-06 | 03 | BH-SF2 | Every Phase service diff passes equal-assurance Change Origin Gate | phase-boundary://requirements/PBR-026/acceptance | CLI/IDE/actor-label/non-protected bypass tests |
| PBR-027 | F4-P1-07 | 05 | BH-REACT1 | React publishes exact minimum CSP/CORS/HSTS/nosniff policy | phase-boundary://requirements/PBR-027/acceptance | browser header and wrong-origin tests |
| PBR-028 | F4-P1-08 | 05 | BH-REACT1 | Session creation/revocation/rotation/logout/cleanup are atomic and bounded under concurrency | phase-boundary://requirements/PBR-028/acceptance | limit/race/version/cleanup tests |
| PBR-029 | F4-P1-09 | 05 | BH-REACT1 | Dependency admission, npm build and deployment signing/verifier run under isolated protected identities | phase-boundary://requirements/PBR-029/acceptance | malicious lifecycle/package/manifest tests |
| PBR-030 | F4-P1-10 | 06 | BH-DATA | DB migration has fenced coordinator, writer drain, checkpointed backfill, atomic dual-write/full reconciliation and failure recovery | phase-boundary://requirements/PBR-030/acceptance | crash/partial-write/previous-writer/contract tests |
| PBR-031 | F4-P1-11 | 04 | BH-SF3 | Mutation/quarantine reserves capacity and cannot consume journal/rollback emergency space | phase-boundary://requirements/PBR-031/acceptance | disk-exhaustion/reservation/metering tests |
| PBR-032 | F4-P1-12 | 06 | BH-ARCH | Dependency rules are mechanical and semantic maintainability rules have stable human-review evidence | phase-boundary://requirements/PBR-032/acceptance | `ARCH001..005` and checklist tests |
| PBR-033 | F4-P1-13 | 96 | BH-HANDOFF | Pinned external split/overlap validator is available before the handoff task and runs for every later phase exit | phase-boundary://requirements/PBR-033/acceptance | validator mutation/protected-workflow evidence |
| PBR-034 | F4-P2-01 | 07 | BH-SF4 | Supported workspace size is numerically defined and benchmarked | phase-boundary://requirements/PBR-034/acceptance | boundary fixture and P95 evidence |
| PBR-035 | F4-P2-02 | 02 | BH-SF0B | Permit Authority has numeric availability, latency, revocation and recovery SLO | phase-boundary://requirements/PBR-035/acceptance | metrics/alert/DR evidence |
| PBR-036 | F4-P2-03 | 05 | BH-REACT1 | React trial has non-waivable quantitative promotion/rollback thresholds and observation window | phase-boundary://requirements/PBR-036/acceptance | cohort ledger and forced rollback tests |
| PBR-037 | F4-P0-02 | 07 | BH-SF0B | Minimum trusted evidence custody rejects repository-forged, forked or tampered phase-exit evidence | phase-boundary://requirements/PBR-037/acceptance | writer/signature/CAS-chain tests |
| PBR-038 | F4-P1-11 | 07 | BH-SF4 | Evidence capacity governance defines per-scope quotas and host emergency watermark | phase-boundary://requirements/PBR-038/acceptance | capacity ADR/quota/cleanup tests |
| PBR-039 | F4-P1-03 | 02 | BH-SF0B | Permit lifecycle has complete terminal states and trusted time/restart semantics | phase-boundary://requirements/PBR-039/acceptance | transition/clock/bootId/restart tests |
| PBR-040 | F5-P0-01,F5-P0-02,F5-P0-03,F5-P1-05,F5-P2-01,F5-P2-02 | 01 | BH-HANDOFF | Downstream implementation is strictly serial and cannot start before complete upstream closure | phase-boundary://requirements/PBR-040/acceptance | missing/partial/parallel-start mutation tests |
| PBR-041 | F5-P0-04,F5-P2-01 | 01 | BH-HANDOFF | Signed UpstreamHandoffManifest binds final commit, phase/global closure, fixtures, schemas, standards, compatibility and deferrals | phase-boundary://requirements/PBR-041/acceptance | selective/stale/hash-mismatch handoff tests |
| PBR-042 | F5-P1-06 | 96 | BH-HANDOFF | Validator detects cross-plan path/task/owner/acceptance/schema/standards overlap | phase-boundary://requirements/PBR-042/acceptance | cross-plan mutation suite |
| PBR-043 | F5-P0-02,F5-P0-03,F5-P1-01 | 05 | BH-REACT1 | React surface ledger is generated exactly from DownstreamFrontendSurfaceInventory while upstream refs retain business authority | phase-boundary://requirements/PBR-043/acceptance | missing/extra/redefined-surface tests |
| PBR-044 | F5-P0-02,F5-P1-02 | 04 | BH-PILOT | Work Policy imports exact handoff-bound action/route/sub-operation IDs and acceptance refs | phase-boundary://requirements/PBR-044/acceptance | unknown/hash-drift/alias-redefinition tests |
| PBR-045 | F5-P1-03 | 07 | BH-SF4 | Downstream evidence owns trust/runtime facts and references rather than copies upstream diagnostic/readback evidence | phase-boundary://requirements/PBR-045/acceptance | taxonomy/schema-duplication tests |
| PBR-046 | F5-P1-04 | 06 | BH-DATA | Data refactor starts from DownstreamPersistenceObservationSnapshot and existing upstream migration refs with no pending upstream migration | phase-boundary://requirements/PBR-046/acceptance | owner/ID/pending-migration conflict tests |
| PBR-047 | F5-P1-07 | 06 | BH-RELEASE | Standards sections have one handoff-bound owner and append/supersede rules | phase-boundary://requirements/PBR-047/acceptance | duplicate-section-owner tests |
| PBR-048 | F5-P1-08 | 05 | BH-REACT2 | `must_preserve` and unexpired compatibility entries cannot be deleted during migration/residual cleanup | phase-boundary://requirements/PBR-048/acceptance | compatibility removal mutation tests |
| PBR-049 | F5-P0-03,F5-P0-05 | 03 | BH-SF1 | Platform Codex uses isolated workspace and trusted apply without primary-worktree/live-data/Git write access | phase-boundary://requirements/PBR-049/acceptance | primary/upstream-dirty/live-path denial tests |
| PBR-050 | F5-P0-06 | 01 | BH-SF0A | Host-admin-resistant claim scope and measured-hardware/separate-admin-remote-runner decision are accepted | phase-boundary://requirements/PBR-050/acceptance | threat/ADR/claim-boundary review |
| PBR-051 | F5-P0-07 | 04 | BH-SF3 | Project mutation lease has project uniqueness, monotonic fencing and persistent recovery block | phase-boundary://requirements/PBR-051/acceptance | stale-holder/takeover/new-permit denial tests |
| PBR-052 | F5-P1-09 | 02 | BH-SF0B | Platform commit, Hosted snapshot and Windows-effective manifests have distinct reproducible contracts | phase-boundary://requirements/PBR-052/acceptance | untracked/no-Git/snapshot binding tests |
| PBR-053 | F5-P1-10 | 02 | BH-SF0B | Permit schema/restore includes every lifecycle state, boot/deadline and attestation ref | phase-boundary://requirements/PBR-053/acceptance | full-state restore/reconcile tests |
| PBR-054 | F5-P1-11 | 02 | BH-SF0B | Retired signing keys remain available for historical verification through evidence retention | phase-boundary://requirements/PBR-054/acceptance | old-attestation audit tests |
| PBR-055 | F5-P1-12 | 06 | BH-ARCH | Architecture enforcement starts from immutable handoff violation baseline and no-growth ratchet | phase-boundary://requirements/PBR-055/acceptance | baseline/unknown/expanded-edge tests |
| PBR-056 | F5-P1-13 | top-level | BH-HANDOFF | Recovery command reads this plan without being blocked by unrelated execution-plan files | phase-boundary://requirements/PBR-056/acceptance | clean recovery command test |
| PBR-057 | F5-P2-05 | 05 | BH-REACT1 | Trial representation is derived from upstream surface/role/path/browser matrix | phase-boundary://requirements/PBR-057/acceptance | homogeneous-sample rejection tests |
| PBR-058 | F5-P1-05,F5-P2-04 | 08 | BH-HANDOFF | React, architecture, Data and release use separate downstream phases and exits | phase-boundary://requirements/PBR-058/acceptance | phase graph/owner/exit validation |
| PBR-059 | F5-P0-06 | 03 | BH-SF1 | Host-admin-resistant runner decision is implemented and passes hostile-admin observation-forgery tests | phase-boundary://requirements/PBR-059/acceptance | measured/remote runner negative tests |
| PBR-060 | F6-01 | 01 | BH-HANDOFF | Handoff signing uses an existing external protected VCS/global-review or offline two-approver trust root, not the downstream Authority | phase-boundary://requirements/PBR-060/acceptance | bootstrap signature/trust-root tests |
| PBR-061 | F6-02 | 96 | BH-HANDOFF | Exactly one handoff-only task may invoke the pinned external verifier and protected evidence collector without building tooling or modifying implementation/plan paths | phase-boundary://requirements/PBR-061/acceptance | task/path allowlist mutation tests |
| PBR-062 | F6-03 | 04 | BH-SF3 | Internal Acceptance transaction states never become upstream route/readback/browser vocabulary | phase-boundary://requirements/PBR-062/acceptance | state non-leakage and upstream-mapping tests |
| PBR-063 | F6-04 | 06 | BH-SF0A | Immutable upstream standards section hashes coexist with an append-only downstream standards delta chain | phase-boundary://requirements/PBR-063/acceptance | owner/hash/delta ancestry tests |
| PBR-064 | F6-05 | 08 | BH-HANDOFF | Every downstream phase has one immediate predecessor and signed Entry/Exit Gate; only one phase may be active | phase-boundary://requirements/PBR-064/acceptance | phase-order/parallel-start tests |
| PBR-065 | F6-06 | 01 | BH-HANDOFF | Repository handoff lock and twice-captured completion snapshot provide authoritative active-task/path/dirty predicates | phase-boundary://requirements/PBR-065/acceptance | concurrent-task/dirty-race snapshot tests |
| PBR-066 | F6-07 | 01 | BH-SF0B | Handoff epoch and deferral state are revalidated at task start, heartbeat, apply and Postflight; supersession revokes work | phase-boundary://requirements/PBR-066/acceptance | epoch/hotfix/expired-deferral tests |
| PBR-067 | F6-08 | 03 | BH-SF1 | Platform workspace is an independent copy/clone and trusted apply uses repository/path fencing with atomic recheck | phase-boundary://requirements/PBR-067/acceptance | shared-Git/TOCTOU apply tests |
| PBR-068 | F6-09 | 02 | BH-SF0B | Permit Authority restore increments restoreEpoch and rejects older executable Permit/attestation state | phase-boundary://requirements/PBR-068/acceptance | RPO-loss/replay/reconcile tests |
| PBR-069 | F6-10 | 04 | BH-SF3 | Filesystem applier uses takeover-aware OS lock and rechecks fencing around every replace/move | phase-boundary://requirements/PBR-069/acceptance | takeover-between-check-and-replace tests |
| PBR-070 | F7-P0-01 | 96 | BH-HANDOFF | Handoff task runs a pre-frozen validator/rule digest and cannot modify validator, fixtures, plan or spec | phase-boundary://requirements/PBR-070/acceptance | self-modification/rule-downgrade mutation tests |
| PBR-071 | F7-P0-02 | 01 | BH-HANDOFF | BootstrapHandoffContract selects an externally enforced fenced lock and complete task-creator/launcher inventory | phase-boundary://requirements/PBR-071/acceptance | lock-bypass/concurrent-launch/inventory/recovery tests |
| PBR-072 | F7-P0-03 | 01 | BH-HANDOFF | Immutable manifest, append-only state events and protected transactional CAS ActiveRegistry permit at most one active handoff and atomic replacement | phase-boundary://requirements/PBR-072/acceptance | dual-active/gap/partial-transaction/event-ancestry/CAS-race tests |
| PBR-073 | F7-P0-04 | 01 | BH-HANDOFF | Handoff consumes only promised upstream artifacts; absent frontend/API/persistence registries become downstream-derived read-only snapshots | phase-boundary://requirements/PBR-073/acceptance | missing-upstream-artifact/no-reopen/authority tests |
| PBR-074 | F7-P0-05 | 01 | BH-HANDOFF | Upstream review findings are zero; only upstream-ledger capability deferrals may remain classified | phase-boundary://requirements/PBR-074/acceptance | finding-versus-deferral mutation tests |
| PBR-075 | F7-P0-06 | 01 | BH-HANDOFF | Bootstrap signature backend, verifier digest and public-key fingerprints are frozen before the handoff task | phase-boundary://requirements/PBR-075/acceptance | signer-bootstrap/circular-dependency tests |
| PBR-076 | F7-P1-01 | 01 | BH-HANDOFF | Bootstrap handoff objects use versioned schemas, RFC 8785 canonical JSON, SHA-256 and Ed25519 payload binding | phase-boundary://requirements/PBR-076/acceptance | cross-host canonicalization/signature vectors |
| PBR-077 | F7-P1-02 | 07 | BH-HANDOFF | Bootstrap evidence has two independent append-only copies, external commitment and protected ActiveRegistry before BH-SF0B | phase-boundary://requirements/PBR-077/acceptance | deletion/fork/availability/import tests |
| PBR-078 | F7-P1-03 | 01 | BH-HANDOFF | Every handoff field resolves through a typed HandoffSourceMap row with source hash, transform and authority owner | phase-boundary://requirements/PBR-078/acceptance | missing/duplicate/source-class tests |
| PBR-079 | F7-P1-04 | top-level | BH-HANDOFF | Gate Summary uses only formal phase names and exact immediate predecessors | phase-boundary://requirements/PBR-079/acceptance | alias/bypass phase tests |
| PBR-080 | F7-P1-05 | top-level | BH-HANDOFF | Recovery has no authoritative static Git Head and uses ActiveRegistry finalCommit | phase-boundary://requirements/PBR-080/acceptance | stale-baseline recovery tests |
| PBR-081 | F7-P1-06 | 01 | BH-SF0B | Handoff supersession invalidates in-flight work, forbids rebind and defines abandon/rollback/restart/manual-recovery disposition | phase-boundary://requirements/PBR-081/acceptance | supersession/apply/Postflight tests |
| PBR-082 | F7-P1-07 | 08 | BH-SF1 | Platform or Hosted containment failure blocks/corrects course and cannot receive successful exit or start BH-SF2/Pilot | phase-boundary://requirements/PBR-082/acceptance | failed-feasibility phase-transition tests |
| PBR-083 | F7-P2-01 | 97 | BH-HANDOFF | Superseded PBRs use explicit status, replacement and reason registry fields | phase-boundary://requirements/PBR-083/acceptance | status-registry parser tests |
| PBR-084 | F7-P2-02 | 01 | BH-HANDOFF | Final ready commit contains the complete upstream package without requiring a squashed single-commit history | phase-boundary://requirements/PBR-084/acceptance | multi-commit history/source-guard tests |
| PBR-085 | F8-P0-01 | 96 | BH-HANDOFF | Repository-local plan-readiness validator is runnable now and cannot substitute for the protected BH-HANDOFF verifier | phase-boundary://requirements/PBR-085/acceptance | local-versus-protected-verifier boundary tests |
| PBR-086 | F8-P0-02 | 01 | BH-HANDOFF | Bootstrap/handoff/source-map/review contracts have actual parseable JSON Schema files before handoff | phase-boundary://requirements/PBR-086/acceptance | required-schema inventory/parse tests |
| PBR-087 | F8-P1-01 | 97 | BH-HANDOFF | Historical findings have a generated plan-only closure registry with no ambiguous Open state | phase-boundary://requirements/PBR-087/acceptance | closure-registry freshness/open-state tests |
| PBR-088 | F8-P1-02 | 97 | BH-HANDOFF | Finding source fields and coverage tables are bidirectionally identical | phase-boundary://requirements/PBR-088/acceptance | finding/PBR mismatch tests |
| PBR-089 | F8-P1-03 | 97 | BH-HANDOFF | Every active PBR has a unique stable acceptance URI resolving to owner/phase/family | phase-boundary://requirements/PBR-089/acceptance | acceptance-ref uniqueness/resolution tests |
| PBR-090 | F8-P1-04 | 98 | BH-HANDOFF | Original-plan semantic coverage uses a canonical 19-family registry and avoids unsupported byte-level claims | phase-boundary://requirements/PBR-090/acceptance | original-family inventory/coverage tests |
| PBR-091 | F8-P1-05 | 96 | BH-HANDOFF | Authority Families explicitly includes the top-level recovery/metadata owner | phase-boundary://requirements/PBR-091/acceptance | owner-family validation |
| PBR-092 | F8-P1-06 | 01 | BH-SF0B | Every task/evidence/heartbeat binds manifest, epoch, StateEvent hash and ActiveRegistry rowVersion | phase-boundary://requirements/PBR-092/acceptance | stale-registry tuple tests |
| PBR-093 | F8-P1-07 | 05 | BH-REACT1 | React implementation entry requires BH-RP1 and the exact immediate-predecessor chain | phase-boundary://requirements/PBR-093/acceptance | premature-React-start tests |
| PBR-094 | F8-P1-08 | 97 | BH-HANDOFF | PBR terminology uses downstream-derived frontend/API/persistence observations without recreating upstream authority | phase-boundary://requirements/PBR-094/acceptance | stale-authority-term tests |
| PBR-095 | F8-P1-09 | 01 | BH-HANDOFF | Every upstream source-map path is fully repository-qualified and unambiguous | phase-boundary://requirements/PBR-095/acceptance | relative-path ambiguity tests |
| PBR-096 | F8-P1-10 | 09 | BH-SF1 | Platform or Hosted containment failure blocks/corrects course consistently in phase and global DoD | phase-boundary://requirements/PBR-096/acceptance | containment-failure consistency tests |
| PBR-097 | F8-P1-11 | 01 | BH-HANDOFF | Deferral fields name only upstream-permitted capability/compatibility deferrals, never unresolved findings | phase-boundary://requirements/PBR-097/acceptance | deferral-taxonomy tests |
| PBR-098 | F8-P1-12 | 08 | BH-HANDOFF | AGENTS and README have phase-bound documentation synchronization tasks and truthful current-state rules | phase-boundary://requirements/PBR-098/acceptance | docs-sync phase-exit checks |
| PBR-099 | F8-P2-01 | 05 | BH-REACT1 | All React migration terms use derived surface IDs and DownstreamFrontendSurfaceInventory | phase-boundary://requirements/PBR-099/acceptance | surface-vocabulary tests |
| PBR-100 | F8-P2-02 | 06 | BH-DATA | Online migration retry returns explicitly to the checkpointed prior state | phase-boundary://requirements/PBR-100/acceptance | migration-retry transition tests |
| PBR-101 | F8-P2-03 | 09 | BH-SF0A | Glossary defines bootstrap, state registry, source map and downstream observation objects | phase-boundary://requirements/PBR-101/acceptance | glossary completeness check |
| PBR-102 | F9-P0-01 | 01 | BH-HANDOFF | Git commits use exactly 40 lowercase hexadecimal characters while every SHA-256 field uses exactly 64 | phase-boundary://requirements/PBR-102/acceptance | commit/hash schema mutation fixtures |
| PBR-103 | F9-P0-02 | 01 | BH-HANDOFF | Bootstrap, Manifest and StateEvent require two distinct structured signers and CompletionSnapshot requires one structured signature | phase-boundary://requirements/PBR-103/acceptance | empty/duplicate signer and signature-shape fixtures |
| PBR-104 | F9-P0-03 | 01 | BH-HANDOFF | Manifest binds ordered before-manifest and before-signature snapshot hashes plus their common schema and path-allowlist hashes | phase-boundary://requirements/PBR-104/acceptance | missing/changed snapshot binding fixtures |
| PBR-105 | F9-P0-04 | 01 | BH-HANDOFF | HandoffSourceMap accepts every qualified upstream standards, architecture, workflow and protected backup source class promised by the handoff | phase-boundary://requirements/PBR-105/acceptance | qualified-path positive and illegal-path mutation fixtures |
| PBR-106 | F9-P1-01 | 96 | BH-HANDOFF | Plan-readiness validation checks supported Draft 2020-12 schema structure and validates every declared fixture against its schema | phase-boundary://requirements/PBR-106/acceptance | schema meta-shape and fixture validation tests |
| PBR-107 | F9-P1-02 | 99 | BH-HANDOFF | Explicit PBR coverage is parsed structurally and every row owner and phase equals the owning 97 requirement | phase-boundary://requirements/PBR-107/acceptance | coverage owner/phase mutation fixtures |
| PBR-108 | F9-P1-03 | 97 | BH-HANDOFF | Finding plan closure requires explicit review-closure evidence independent of PBR coverage and missing evidence remains plan_open | phase-boundary://requirements/PBR-108/acceptance | explicit evidence freshness/open-finding fixture |
| PBR-109 | F9-P1-04 | 01 | BH-HANDOFF | Downstream observations have strict per-surface, operation and schema-object contracts with field-level source hashes and no business authority fields | phase-boundary://requirements/PBR-109/acceptance | observation item/additional-field fixtures |
| PBR-110 | F9-P1-05 | 01 | BH-HANDOFF | Capability deferrals require disposition, owner, expiry, recheck and evidence and cannot encode review finding IDs | phase-boundary://requirements/PBR-110/acceptance | deferral taxonomy and finding-alias fixtures |
| PBR-111 | F9-P1-06 | 99 | BH-HANDOFF | ActiveRegistry selects the immutable Manifest; recovery reads finalCommit from that selected Manifest rather than from the registry row | phase-boundary://requirements/PBR-111/acceptance | registry-to-manifest recovery relation check |
| PBR-112 | F9-P1-07 | 01 | BH-HANDOFF | Bootstrap sourceMapSchemaId and HandoffSourceMap instance schemaId use the same versioned identity | phase-boundary://requirements/PBR-112/acceptance | schema identity equality check |
| PBR-113 | F9-P1-08 | 98 | BH-HANDOFF | Original-family coverage is an approved hash-bound semantic baseline with approval evidence and no unavailable-byte fidelity claim | phase-boundary://requirements/PBR-113/acceptance | provenance/hash/approval validation |
| PBR-114 | F9-P2-01 | 06 | BH-DATA | Online migration retry uses retryTargetState as data and never persists a recorded-prior-state placeholder as a migration enum | phase-boundary://requirements/PBR-114/acceptance | migration state vocabulary check |
| PBR-115 | F9-P2-02 | 01 | BH-HANDOFF | Source-map not-applicable rows represent absent source, transform and output values as null while retaining an explicit reason | phase-boundary://requirements/PBR-115/acceptance | applicable/N-A branch fixtures |
| PBR-116 | F9-P2-03 | 98 | BH-HANDOFF | Every original semantic family contains a machine-readable acceptance object and stable acceptance URI | phase-boundary://requirements/PBR-116/acceptance | original acceptance object/URI validation |

## Requirement Status Registry

| ID | Status | Superseded by | Reason |
| --- | --- | --- | --- |
| `PBR-013` | superseded | `PBR-033` | Validator timing and phase-exit enforcement moved to the complete active requirement. |

## Finding Status Registry

Plan-review finding status is generated deterministically at `schemas/finding-closure-registry.v1.json` by joining the coverage tables below with the independent explicit evidence in `schemas/finding-closure-evidence.v1.json`. A PBR mapping alone never closes a finding. `plan_closed` means the plan contract preserves the finding; it does not mean implementation or code acceptance is complete. Missing evidence produces `plan_open`; missing/stale generated output or any `plan_open` row fails the Whole-directory plan-readiness review.

## Pre-Fourth-Review Finding Coverage

| Finding | Required PBR closure |
| --- | --- |
| PF-001 | PBR-001 |
| PF-002 | PBR-002 |
| PF-003 | PBR-003 |
| PF-004 | PBR-004 |
| PF-005 | PBR-005 |
| PF-006 | PBR-006 |
| PF-007 | PBR-007 |
| PF-008 | PBR-008 |
| PF-009 | PBR-009 |
| PF-010 | PBR-010 |
| PF-011 | PBR-011 |
| PF-012 | PBR-012 |
| PF-013 | PBR-013 |
| PF-014 | PBR-014 |
| PF-015 | PBR-015 |

## Fourth-Review Finding Coverage

| Finding | Required PBR closure |
| --- | --- |
| F4-P0-01 | PBR-017 |
| F4-P0-02 | PBR-018, PBR-037 |
| F4-P0-03 | PBR-020 |
| F4-P0-04 | PBR-021 |
| F4-P0-05 | PBR-019 |
| F4-P1-01 | PBR-022 |
| F4-P1-02 | PBR-023 |
| F4-P1-03 | PBR-039 |
| F4-P1-04 | PBR-024 |
| F4-P1-05 | PBR-025 |
| F4-P1-06 | PBR-026 |
| F4-P1-07 | PBR-027 |
| F4-P1-08 | PBR-028 |
| F4-P1-09 | PBR-029 |
| F4-P1-10 | PBR-030 |
| F4-P1-11 | PBR-031, PBR-038 |
| F4-P1-12 | PBR-032 |
| F4-P1-13 | PBR-033 |
| F4-P2-01 | PBR-034 |
| F4-P2-02 | PBR-035 |
| F4-P2-03 | PBR-036 |
| F4-P2-04 | PBR-016 |

## Fifth-Review Upstream-Coordination Finding Coverage

| Finding | Required PBR closure |
| --- | --- |
| F5-P0-01 | PBR-040 |
| F5-P0-02 | PBR-040, PBR-043, PBR-044 |
| F5-P0-03 | PBR-040, PBR-043, PBR-049 |
| F5-P0-04 | PBR-041 |
| F5-P0-05 | PBR-049 |
| F5-P0-06 | PBR-050, PBR-059 |
| F5-P0-07 | PBR-051 |
| F5-P1-01 | PBR-043 |
| F5-P1-02 | PBR-044 |
| F5-P1-03 | PBR-045 |
| F5-P1-04 | PBR-046 |
| F5-P1-05 | PBR-040, PBR-058 |
| F5-P1-06 | PBR-042 |
| F5-P1-07 | PBR-047 |
| F5-P1-08 | PBR-048 |
| F5-P1-09 | PBR-052 |
| F5-P1-10 | PBR-053 |
| F5-P1-11 | PBR-054 |
| F5-P1-12 | PBR-055 |
| F5-P1-13 | PBR-056 |
| F5-P2-01 | PBR-040, PBR-041 |
| F5-P2-02 | PBR-040 |
| F5-P2-03 | PBR-016 |
| F5-P2-04 | PBR-058 |
| F5-P2-05 | PBR-057 |

## Sixth-Review Derivation Finding Coverage

| Finding | Required PBR closure |
| --- | --- |
| F6-01 | PBR-060 |
| F6-02 | PBR-061 |
| F6-03 | PBR-062 |
| F6-04 | PBR-063 |
| F6-05 | PBR-064 |
| F6-06 | PBR-065 |
| F6-07 | PBR-066 |
| F6-08 | PBR-067 |
| F6-09 | PBR-068 |
| F6-10 | PBR-069 |

## Seventh-Review Bootstrap Closure Finding Coverage

| Finding | Required PBR closure |
| --- | --- |
| F7-P0-01 | PBR-070 |
| F7-P0-02 | PBR-071 |
| F7-P0-03 | PBR-072 |
| F7-P0-04 | PBR-073 |
| F7-P0-05 | PBR-074 |
| F7-P0-06 | PBR-075 |
| F7-P1-01 | PBR-076 |
| F7-P1-02 | PBR-077 |
| F7-P1-03 | PBR-078 |
| F7-P1-04 | PBR-079 |
| F7-P1-05 | PBR-080 |
| F7-P1-06 | PBR-081 |
| F7-P1-07 | PBR-082 |
| F7-P2-01 | PBR-083 |
| F7-P2-02 | PBR-084 |

## Eighth-Review Whole-Directory Finding Coverage

| Finding | Required PBR closure |
| --- | --- |
| F8-P0-01 | PBR-085 |
| F8-P0-02 | PBR-086 |
| F8-P1-01 | PBR-087 |
| F8-P1-02 | PBR-088 |
| F8-P1-03 | PBR-089 |
| F8-P1-04 | PBR-090 |
| F8-P1-05 | PBR-091 |
| F8-P1-06 | PBR-092 |
| F8-P1-07 | PBR-093 |
| F8-P1-08 | PBR-094 |
| F8-P1-09 | PBR-095 |
| F8-P1-10 | PBR-096 |
| F8-P1-11 | PBR-097 |
| F8-P1-12 | PBR-098 |
| F8-P2-01 | PBR-099 |
| F8-P2-02 | PBR-100 |
| F8-P2-03 | PBR-101 |

## Ninth-Review Schema Closure Finding Coverage

| Finding | Required PBR closure |
| --- | --- |
| F9-P0-01 | PBR-102 |
| F9-P0-02 | PBR-103 |
| F9-P0-03 | PBR-104 |
| F9-P0-04 | PBR-105 |
| F9-P1-01 | PBR-106 |
| F9-P1-02 | PBR-107 |
| F9-P1-03 | PBR-108 |
| F9-P1-04 | PBR-109 |
| F9-P1-05 | PBR-110 |
| F9-P1-06 | PBR-111 |
| F9-P1-07 | PBR-112 |
| F9-P1-08 | PBR-113 |
| F9-P2-01 | PBR-114 |
| F9-P2-02 | PBR-115 |
| F9-P2-03 | PBR-116 |

## Acceptance

- Validator rejects missing/duplicate ID, active duplicate authority, missing/invalid phase, missing owner/acceptance URI/family, malformed status-registry supersession, stale finding closure registry, uncovered ID, duplicate/missing PF/F4/F5/F6/F7/F8/F9 finding, finding/PBR mismatch or missing explicit closure evidence.
- New adversarial-review requirement is added here before implementation.
