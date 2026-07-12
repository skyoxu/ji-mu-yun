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
- Requirement status defaults to `active`. A requirement becomes `superseded` only through the machine-parsed Requirement Status Registry; prose in the requirement column cannot change status.

## Requirements

| ID | Source finding | Owner | Phase | Requirement | Acceptance family |
| --- | --- | --- | --- | --- | --- |
| PBR-001 | PF-001 | 02 | BH-SF0B | Platform Postflight attestation binds source/host manifests, tests and evidence | CI recomputation/trust-chain/signature tests |
| PBR-002 | PF-002 | 04 | BH-SF3 | Mutation lease remains held through Acceptance, durable Postflight and rollback | concurrency/Postflight-race/rollback-conflict tests |
| PBR-003 | PF-003 | 06 | BH-RELEASE | Previous bundle rollback requires current DB schema compatibility | current/previous binary schema matrix |
| PBR-004 | PF-004 | 02 | BH-SF0A | Root public-key ceremony and immutable verifier bootstrap | key replacement/break-glass tests/evidence |
| PBR-005 | PF-005 | 02 | BH-SF0B | Permit Authority outage/backup/restore/fail-closed | DR and availability evidence |
| PBR-006 | PF-006 | 03 | BH-SF1 | Tool broker validates IPC, executable, args, paths, env and output | broker negative tests |
| PBR-007 | PF-007 | 03 | BH-SF1 | Controller cannot directly mutate project files | containment tests |
| PBR-008 | PF-008 | 05 | BH-REACT1 | Session bootstrap, exact Cookie/CSRF/TTL policy | auth/CSRF/session tests |
| PBR-009 | PF-009 | 05 | BH-REACT1 | Legacy raw-token Cookie is actively expired | cutover/browser tests |
| PBR-010 | PF-010 | 05 | BH-REACT1 | Trusted Caddy forwarded headers and origin/rate-limit identity | proxy spoof/downgrade tests |
| PBR-011 | PF-011 | 04 | BH-SF3 | Quarantine is no-execute, restricted and account-safe | ACL/readback tests |
| PBR-012 | PF-012 | 04 | BH-SF3 | Non-file side effects use trusted supervisor ledger/cleanup | process/temp/cache/network tests |
| PBR-013 | PF-013 | 96 | BH-HANDOFF | Superseded by PBR-033 because the original validator entry lacked mandatory early-phase/phase-exit timing | replacement-reference validation |
| PBR-014 | PF-014 | 07 | BH-SF4 | Stable evidence path and immutable run-id evidence | evidence path tests |
| PBR-015 | PF-015 | 07 | BH-SF4 | Permit/verifier availability and recovery telemetry | SLO/alert/DR evidence |
| PBR-016 | F4-P2-04,F5-P2-03 | top-level | BH-HANDOFF | Plan remains paused until upstream handoff, actual owners and authorization exist | recovery metadata check |
| PBR-017 | F4-P0-01 | 02 | BH-SF0B | Remote signing service is separately administered and cannot be used as an unrestricted signing oracle | key/caller/launcher/signer isolation tests |
| PBR-018 | F4-P0-02 | 02 | BH-SF0B | Protected completion uses independent rerun or Authority-signed Test/Acceptance Attestation | forged-runner/report and exact-candidate tests |
| PBR-019 | F4-P0-05 | 02 | BH-SF0B | Paired source/snapshot/host manifests bind Platform Git, Hosted snapshot and Windows-effective content | binary/ADS/hard-link/reparse/ACL golden vectors |
| PBR-020 | F4-P0-03 | 03 | BH-SF1 | Acceptance runner executes generated content under restricted no-network containment | Godot/build/preview escape and orphan-process tests |
| PBR-021 | F4-P0-04 | 04 | BH-SF3 | Side-effect evidence is supervisor/OS-derived rather than worker self-report | omission and undeclared-side-effect fixtures |
| PBR-022 | F4-P1-01 | 03 | BH-SF1 | Tool broker local IPC has protected ACL, mutual identity, nonce/sequence and replay denial | Named Pipe protocol negative tests |
| PBR-023 | F4-P1-02 | 02 | BH-SF0B | Permit revocation propagates in real time and wins final consume races | revoke/control-channel/CAS tests |
| PBR-024 | F4-P1-04 | 04 | BH-SF3 | Internal Mutation/Acceptance transaction states persist finalization and recovery without redefining upstream route/readback status | state-transition and upstream-mapping/non-leakage tests |
| PBR-025 | F4-P1-05 | 03 | BH-SF1 | Windows path enforcement rejects ADS/hard-link/device/UNC/alias/case/TOCTOU escapes | path boundary mutation tests |
| PBR-026 | F4-P1-06 | 03 | BH-SF2 | Every Phase service diff passes equal-assurance Change Origin Gate | CLI/IDE/actor-label/non-protected bypass tests |
| PBR-027 | F4-P1-07 | 05 | BH-REACT1 | React publishes exact minimum CSP/CORS/HSTS/nosniff policy | browser header and wrong-origin tests |
| PBR-028 | F4-P1-08 | 05 | BH-REACT1 | Session creation/revocation/rotation/logout/cleanup are atomic and bounded under concurrency | limit/race/version/cleanup tests |
| PBR-029 | F4-P1-09 | 05 | BH-REACT1 | Dependency admission, npm build and deployment signing/verifier run under isolated protected identities | malicious lifecycle/package/manifest tests |
| PBR-030 | F4-P1-10 | 06 | BH-DATA | DB migration has fenced coordinator, writer drain, checkpointed backfill, atomic dual-write/full reconciliation and failure recovery | crash/partial-write/previous-writer/contract tests |
| PBR-031 | F4-P1-11 | 04 | BH-SF3 | Mutation/quarantine reserves capacity and cannot consume journal/rollback emergency space | disk-exhaustion/reservation/metering tests |
| PBR-032 | F4-P1-12 | 06 | BH-ARCH | Dependency rules are mechanical and semantic maintainability rules have stable human-review evidence | `ARCH001..005` and checklist tests |
| PBR-033 | F4-P1-13 | 96 | BH-HANDOFF | Pinned external split/overlap validator is available before the handoff task and runs for every later phase exit | validator mutation/protected-workflow evidence |
| PBR-034 | F4-P2-01 | 07 | BH-SF4 | Supported workspace size is numerically defined and benchmarked | boundary fixture and P95 evidence |
| PBR-035 | F4-P2-02 | 02 | BH-SF0B | Permit Authority has numeric availability, latency, revocation and recovery SLO | metrics/alert/DR evidence |
| PBR-036 | F4-P2-03 | 05 | BH-REACT1 | React trial has non-waivable quantitative promotion/rollback thresholds and observation window | cohort ledger and forced rollback tests |
| PBR-037 | F4-P0-02 | 07 | BH-SF0B | Minimum trusted evidence custody rejects repository-forged, forked or tampered phase-exit evidence | writer/signature/CAS-chain tests |
| PBR-038 | F4-P1-11 | 07 | BH-SF4 | Evidence capacity governance defines per-scope quotas and host emergency watermark | capacity ADR/quota/cleanup tests |
| PBR-039 | F4-P1-03 | 02 | BH-SF0B | Permit lifecycle has complete terminal states and trusted time/restart semantics | transition/clock/bootId/restart tests |
| PBR-040 | F5-P0-01,F5-P0-02,F5-P0-03,F5-P2-01,F5-P2-02 | 01 | BH-HANDOFF | Downstream implementation is strictly serial and cannot start before complete upstream closure | missing/partial/parallel-start mutation tests |
| PBR-041 | F5-P0-04,F5-P2-01 | 01 | BH-HANDOFF | Signed UpstreamHandoffManifest binds final commit, phase/global closure, fixtures, schemas, standards, compatibility and deferrals | selective/stale/hash-mismatch handoff tests |
| PBR-042 | F5-P1-06 | 96 | BH-HANDOFF | Validator detects cross-plan path/task/owner/acceptance/schema/standards overlap | cross-plan mutation suite |
| PBR-043 | F5-P0-02,F5-P0-03,F5-P1-01 | 05 | BH-REACT1 | React surface ledger is generated exactly from upstream handoff projection and owns technical migration only | missing/extra/redefined-surface tests |
| PBR-044 | F5-P0-02,F5-P1-02 | 04 | BH-PILOT | Work Policy imports exact handoff-bound action/route/sub-operation IDs and acceptance refs | unknown/hash-drift/alias-redefinition tests |
| PBR-045 | F5-P1-03 | 07 | BH-SF4 | Downstream evidence owns trust/runtime facts and references rather than copies upstream diagnostic/readback evidence | taxonomy/schema-duplication tests |
| PBR-046 | F5-P1-04 | 06 | BH-DATA | Data refactor starts from handoff schema/migration/table-owner baseline with no pending upstream migration | owner/ID/pending-migration conflict tests |
| PBR-047 | F5-P1-07 | 06 | BH-RELEASE | Standards sections have one handoff-bound owner and append/supersede rules | duplicate-section-owner tests |
| PBR-048 | F5-P1-08 | 05 | BH-REACT2 | `must_preserve` and unexpired compatibility entries cannot be deleted during migration/residual cleanup | compatibility removal mutation tests |
| PBR-049 | F5-P0-03,F5-P0-05 | 03 | BH-SF1 | Platform Codex uses isolated workspace and trusted apply without primary-worktree/live-data/Git write access | primary/upstream-dirty/live-path denial tests |
| PBR-050 | F5-P0-06 | 01 | BH-SF0A | Host-admin-resistant claim scope and measured-hardware/separate-admin-remote-runner decision are accepted | threat/ADR/claim-boundary review |
| PBR-051 | F5-P0-07 | 04 | BH-SF3 | Project mutation lease has project uniqueness, monotonic fencing and persistent recovery block | stale-holder/takeover/new-permit denial tests |
| PBR-052 | F5-P1-09 | 02 | BH-SF0B | Platform commit, Hosted snapshot and Windows-effective manifests have distinct reproducible contracts | untracked/no-Git/snapshot binding tests |
| PBR-053 | F5-P1-10 | 02 | BH-SF0B | Permit schema/restore includes every lifecycle state, boot/deadline and attestation ref | full-state restore/reconcile tests |
| PBR-054 | F5-P1-11 | 02 | BH-SF0B | Retired signing keys remain available for historical verification through evidence retention | old-attestation audit tests |
| PBR-055 | F5-P1-12 | 06 | BH-ARCH | Architecture enforcement starts from immutable handoff violation baseline and no-growth ratchet | baseline/unknown/expanded-edge tests |
| PBR-056 | F5-P1-13 | top-level | BH-HANDOFF | Recovery command reads this plan without being blocked by unrelated execution-plan files | clean recovery command test |
| PBR-057 | F5-P2-05 | 05 | BH-REACT1 | Trial representation is derived from upstream surface/role/path/browser matrix | homogeneous-sample rejection tests |
| PBR-058 | F5-P2-04 | 08 | BH-HANDOFF | React, architecture, Data and release use separate downstream phases and exits | phase graph/owner/exit validation |
| PBR-059 | F5-P0-06 | 03 | BH-SF1 | Host-admin-resistant runner decision is implemented and passes hostile-admin observation-forgery tests | measured/remote runner negative tests |
| PBR-060 | F6-01 | 01 | BH-HANDOFF | Handoff signing uses an existing external protected VCS/global-review or offline two-approver trust root, not the downstream Authority | bootstrap signature/trust-root tests |
| PBR-061 | F6-02 | 96 | BH-HANDOFF | Exactly one handoff-only task may invoke the pinned external verifier and protected evidence collector without building tooling or modifying implementation/plan paths | task/path allowlist mutation tests |
| PBR-062 | F6-03 | 04 | BH-SF3 | Internal Acceptance transaction states never become upstream route/readback/browser vocabulary | state non-leakage and upstream-mapping tests |
| PBR-063 | F6-04 | 06 | BH-SF0A | Immutable upstream standards section hashes coexist with an append-only downstream standards delta chain | owner/hash/delta ancestry tests |
| PBR-064 | F6-05 | 08 | BH-HANDOFF | Every downstream phase has one immediate predecessor and signed Entry/Exit Gate; only one phase may be active | phase-order/parallel-start tests |
| PBR-065 | F6-06 | 01 | BH-HANDOFF | Repository handoff lock and twice-captured completion snapshot provide authoritative active-task/path/dirty predicates | concurrent-task/dirty-race snapshot tests |
| PBR-066 | F6-07 | 01 | BH-SF0B | Handoff epoch and deferral state are revalidated at task start, heartbeat, apply and Postflight; supersession revokes work | epoch/hotfix/expired-deferral tests |
| PBR-067 | F6-08 | 03 | BH-SF1 | Platform workspace is an independent copy/clone and trusted apply uses repository/path fencing with atomic recheck | shared-Git/TOCTOU apply tests |
| PBR-068 | F6-09 | 02 | BH-SF0B | Permit Authority restore increments restoreEpoch and rejects older executable Permit/attestation state | RPO-loss/replay/reconcile tests |
| PBR-069 | F6-10 | 04 | BH-SF3 | Filesystem applier uses takeover-aware OS lock and rechecks fencing around every replace/move | takeover-between-check-and-replace tests |
| PBR-070 | F7-P0-01 | 96 | BH-HANDOFF | Handoff task runs a pre-frozen validator/rule digest and cannot modify validator, fixtures, plan or spec | self-modification/rule-downgrade mutation tests |
| PBR-071 | F7-P0-02 | 01 | BH-HANDOFF | BootstrapHandoffContract selects an externally enforced fenced lock and complete task-creator/launcher inventory | lock-bypass/concurrent-launch/inventory/recovery tests |
| PBR-072 | F7-P0-03 | 01 | BH-HANDOFF | Immutable manifest, append-only state events and protected transactional CAS ActiveRegistry permit at most one active handoff and atomic replacement | dual-active/gap/partial-transaction/event-ancestry/CAS-race tests |
| PBR-073 | F7-P0-04 | 01 | BH-HANDOFF | Handoff consumes only promised upstream artifacts; absent frontend/API/persistence registries become downstream-derived read-only snapshots | missing-upstream-artifact/no-reopen/authority tests |
| PBR-074 | F7-P0-05 | 01 | BH-HANDOFF | Upstream review findings are zero; only upstream-ledger capability deferrals may remain classified | finding-versus-deferral mutation tests |
| PBR-075 | F7-P0-06 | 01 | BH-HANDOFF | Bootstrap signature backend, verifier digest and public-key fingerprints are frozen before the handoff task | signer-bootstrap/circular-dependency tests |
| PBR-076 | F7-P1-01 | 01 | BH-HANDOFF | Bootstrap handoff objects use versioned schemas, RFC 8785 canonical JSON, SHA-256 and Ed25519 payload binding | cross-host canonicalization/signature vectors |
| PBR-077 | F7-P1-02 | 07 | BH-HANDOFF | Bootstrap evidence has two independent append-only copies, external commitment and protected ActiveRegistry before BH-SF0B | deletion/fork/availability/import tests |
| PBR-078 | F7-P1-03 | 01 | BH-HANDOFF | Every handoff field resolves through a typed HandoffSourceMap row with source hash, transform and authority owner | missing/duplicate/source-class tests |
| PBR-079 | F7-P1-04 | top-level | BH-HANDOFF | Gate Summary uses only formal phase names and exact immediate predecessors | alias/bypass phase tests |
| PBR-080 | F7-P1-05 | top-level | BH-HANDOFF | Recovery has no authoritative static Git Head and uses ActiveRegistry finalCommit | stale-baseline recovery tests |
| PBR-081 | F7-P1-06 | 01 | BH-SF0B | Handoff supersession invalidates in-flight work, forbids rebind and defines abandon/rollback/restart/manual-recovery disposition | supersession/apply/Postflight tests |
| PBR-082 | F7-P1-07 | 08 | BH-SF1 | Platform or Hosted containment failure blocks/corrects course and cannot receive successful exit or start BH-SF2/Pilot | failed-feasibility phase-transition tests |
| PBR-083 | F7-P2-01 | 97 | BH-HANDOFF | Superseded PBRs use explicit status, replacement and reason registry fields | status-registry parser tests |
| PBR-084 | F7-P2-02 | 01 | BH-HANDOFF | Final ready commit contains the complete upstream package without requiring a squashed single-commit history | multi-commit history/source-guard tests |

## Requirement Status Registry

| ID | Status | Superseded by | Reason |
| --- | --- | --- | --- |
| `PBR-013` | superseded | `PBR-033` | Validator timing and phase-exit enforcement moved to the complete active requirement. |

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

## Acceptance

- Validator rejects missing/duplicate ID, active duplicate authority, missing/invalid phase, missing owner/acceptance, malformed status-registry supersession, uncovered ID, duplicate/missing PF/F4/F5/F6/F7 finding or finding/PBR mismatch.
- New adversarial-review requirement is added here before implementation.
