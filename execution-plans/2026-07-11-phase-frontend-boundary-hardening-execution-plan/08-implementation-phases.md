# Implementation Phases

## Phase BH-HANDOFF: Upstream Completion And Freeze

Deliver:

- verify the tracked final `2026-07-07` split directory and upstream final commit
- verify Phase 0A/0B/1-6 exit evidence, global review, split-added closure and zero unresolved P0/P1/P2 findings; classify upstream-permitted capability deferrals separately
- verify the pre-frozen BootstrapHandoffContract, pinned validator/rules and externally enforced lock before the handoff-only task writes evidence
- generate signed UpstreamHandoffManifest, HandoffSourceMap, downstream-derived frontend/API/persistence snapshots, initial StateEvent and atomically selected ActiveRegistry entry
- generate two matching signed UpstreamCompletionSnapshot captures around manifest construction/signing
- classify every accepted upstream deferral as downstream-consumed, preserved or excluded with owner/Gate
- prove upstream-owned dirty path count is zero and no downstream implementation task already exists; only the allowlisted handoff-only validator/evidence task may exist

Exit:

- every required manifest field/hash/approver resolves and mutation tests fail missing/stale/selective handoffs
- immutable manifest plus append-only state-event chain has exactly one protected active-registry selection
- no downstream path/task overlaps an active upstream task
- only after exit may BH-SF0A task creation be authorized

## Mandatory Sequential Dependency Matrix

| Phase | Immediate required predecessor |
| --- | --- |
| BH-HANDOFF | upstream Phase 0A/0B/1-6 plus global review/closure declared complete |
| BH-SF0A | BH-HANDOFF |
| BH-SF0B | BH-SF0A |
| BH-SF0C | BH-SF0B |
| BH-SF1 | BH-SF0C |
| BH-SF2 | BH-SF1 |
| BH-SF3 | BH-SF2 |
| BH-SF4 | BH-SF3 |
| BH-PILOT | BH-SF4 |
| BH-RP1 | BH-PILOT |
| BH-REACT1 | BH-RP1 |
| BH-REACT2 | BH-REACT1 |
| BH-ARCH | BH-REACT2 |
| BH-DATA | BH-ARCH |
| BH-RELEASE | BH-DATA |

Only one downstream phase may be active. A phase task cannot be created or activated until the immediate predecessor has signed exit evidence bound to the same active handoffEpoch. Missing, superseded or expired predecessor evidence fails closed; listing arbitrary dependency task IDs cannot substitute for this matrix.

## Phase BH-SF0A: Threat Model And Trust Anchor

Deliver:

- accepted threat model
- general-purpose downstream verifier/Attestation Authority decision; the narrower bootstrap verifier is already frozen and cannot be replaced here
- remote Attestation Authority, non-exportable key ownership and separate administrative domain decision
- root public-key ceremony, immutable verifier pin and outage/break-glass policy
- actual owner/backup/approver/incident/rollback identities
- minimal build identity
- adopt the already-frozen BH-HANDOFF split validator and mutation fixtures for every later plan change; BH-SF0A cannot replace their bootstrap rule digest
- Platform SourceChangeManifest, Hosted SnapshotChangeManifest and HostEffectiveManifest specification, golden vectors and Windows path/entry rejection policy
- signing-service isolation design: process identity, key ACL, authenticated transport, protected deployment and signing-oracle denial
- one-time general-purpose downstream Authority bootstrap ceremony and closeout; it cannot replace the BH-HANDOFF bootstrap verifier/root
- host-admin threat decision: hardware-backed measured runner or separate-admin remote runner for any claim that must survive host-admin compromise

Exit:

- no unresolved trust-model P0/P1
- PR cannot modify verifier used for its own attestation check
- private key absent from PR/CI code execution
- validator fails removed book/broken link/duplicate authority/uncovered ledger entries before BH-SF0B work starts
- signer/manifest designs have no unresolved P0/P1 and have accepted ADR ownership

## Phase BH-SF0B: Permit Authority

Deliver:

- Permit schema/table/migration
- atomic claim and nonce uniqueness
- expiry/execution deadline/key rotation/revocation
- server-side opaque Permit API
- asymmetric Platform Development attestation
- atomic Permit DB claim, Authority backup/restore and availability SLO
- complete terminal lifecycle, real-time revoke channel, trusted/monotonic time handling and initial numeric SLO
- protected Test/Acceptance Attestation schema and runner identity contract
- remote Attestation Authority implementation for Preflight/Postflight/Test/Acceptance key purposes
- protected runner/launcher trust registry, key rotation/revocation and signing-request ACL
- minimum protected evidence store for all BH-SF phase exits: isolated writer, immutable run records, CAS chain head, external anchor, encryption and verifier

Exit:

- concurrency, replay, wrong-scope, rotation and restart tests pass
- signer/launcher isolation, forged runner/test evidence, paired-manifest binding, revoke/consume race, clock/restart and terminal-state recovery tests pass

## Phase BH-SF0C: Central Factory

Deliver:

- ValidatedExecutionPermitContext
- sandbox enum
- no-Permit read-only fallback
- raw subprocess source guard
- trust-boundary protected path update

Exit:

- workspace-write bypass tests fail closed

## Phase BH-SF1: Platform And Hosted Containment Feasibility

Deliver:

- restricted token/identity prototype
- Job Object
- focused ACL
- controller/provider proxy
- no-network tool broker
- environment/TEMP/HOME isolation
- protected Named Pipe identity/ACL/challenge/replay protocol
- restricted Acceptance runner for Godot/import/build/test/preview of generated content
- isolated Platform worktree/copy, primary-worktree/Git/live-data denial and trusted reviewed-diff applier
- hardware-backed measured runner or separately administered remote runner when host-admin-resistant attestation is required

Exit:

- actual host negative tests pass for both Platform and Hosted modes required by later phases
- worker omission cannot hide side effects and Acceptance cannot reach network/secrets/Phase source/DB/other workspaces
- if Platform or Hosted containment fails, BH-SF1 does not receive a successful exit: the plan becomes blocked/correct-course and BH-SF2/BH-PILOT cannot start

## Phase BH-SF2: Profiles And Preflight

Deliver:

- shared Policy schema
- Platform and Hosted fixtures
- canonical launcher and IDE/GUI integration policy
- signed attestation review gate
- integrate the BH-SF0B Attestation Authority and protected Postflight supervisor with final source/snapshot/host manifest, test and evidence binding
- mandatory equal-assurance Change Origin Gate for every Phase service diff and actor type
- Work Declaration validation

Exit:

- all supported Platform Codex entries preflight
- unsupported IDE/CLI write integrations cannot produce merge-eligible Codex evidence
- Hosted missing authority/capability fails before writable process

## Phase BH-SF3: Mutation Transaction

Deliver:

- Work Policy registry
- persistent lease/heartbeat/recovery
- project-level unique lease, monotonic fencing token and persistent project recovery block
- same-volume staging
- separate Permit/Mutation/Acceptance states
- default acceptance rollback/quarantine
- lease held through Acceptance, durable Postflight, rollback and rollback-conflict handling
- side-effect ledger and quarantine security
- complete Mutation/Acceptance/rollback-conflict state machines
- evidence/quarantine quotas, rollback capacity reserve and safe raw-export policy

Exit:

- N-file crash/rollback, baseline conflict, restart and acceptance-fail tests pass
- trusted-supervisor side-effect detection, capacity exhaustion and every persisted transition/recovery test pass

## Phase BH-SF4: Evidence Governance, Capacity, Telemetry And Performance

Deliver:

- extend the BH-SF0B protected evidence minimum with retention, cleanup separation, capacity, backup/restore and operations governance
- retention/privacy/capacity ADR, per-scope quotas, cleanup separation and backup/restore impact
- Permit/attestation/containment/Mutation/Acceptance/React telemetry and numeric alert/SLO dashboards
- supported-workspace boundary fixtures and reproducible P50/P95/P99 benchmarks
- phase-exit/latest pointer schema and evidence verifier

Exit:

- forged/tampered/forked/deleted evidence tests fail closed
- quota/reserve/cleanup/restore and supported-workspace performance tests pass
- one Permit -> Mutation -> Acceptance -> Postflight timeline is reconstructable from protected evidence

## Phase BH-PILOT: First Hosted Enforcement Integration

Entry: BH-SF4 signed exit, active handoffEpoch and exact imported upstream action/route/acceptance hashes.

- Select one low-risk file-changing sub-operation from the UpstreamHandoffManifest.
- Import its exact action/route descriptor and acceptance refs into Work Policy without redefining them.
- Run audit-only with enforced containment.
- Enforce after exit criteria.

Exit: audit-only corpus/observation Gate passes, no false negative or unresolved P0/P1, route behavior remains upstream-authoritative, and rollback/containment evidence passes.

## Phase BH-RP1: Correlation And Minimal Version

Entry: BH-PILOT signed exit under the active handoffEpoch.

- Global requestId/error/redaction.
- Public/admin version projections.
- Build identity in Permit, journal, React and evidence.

Exit: request/run/permit/journal/upstream-evidence correlation and public/admin version boundary tests pass.

## Phase BH-REACT1: React Shell And Single-Surface Pilot

Entry: BH-RP1 signed exit plus unchanged active handoff and valid DownstreamFrontendSurfaceInventory/DownstreamApiObservationSnapshot for the selected observed surface.

- HTTPS/session/CSRF prerequisite.
- trusted proxy, legacy Cookie deletion and bootstrap exchange tests.
- React shell and one handoff-projected low-risk read-only surface.
- Handoff-bound downstream API observation/fixture generation, SBOM/provenance, rollback bundle.
- exact CSP/CORS/security-header policy, concurrent session lifecycle and isolated npm/release signing.
- quantitative trial promotion/rollback thresholds and upstream-surface representative observation ledger.

Exit: selected surface parity/security/trial/rollback evidence passes with no business vocabulary drift.

## Phase BH-REACT2: Mandatory Surface Migration

Entry: BH-REACT1 signed exit and unchanged handoff, downstream frontend inventory/API observation and upstream compatibility refs.

- Generate the exact required surface set from DownstreamFrontendSurfaceInventory and its upstream source refs.
- Migrate surface by surface without changing business action/status/readback/diagnostic semantics.
- Preserve `must_preserve` and unexpired `time_bounded_compatibility` behavior.
- Default cutover and legacy retirement require per-surface evidence and verified rollback.

Exit: every handoff-mandatory surface reaches its required state; all preservation entries remain satisfied and rollback bundle passes.

## Phase BH-ARCH: Endpoint And Dependency Ratchet

Entry: BH-REACT2 signed exit and accepted handoff architecture/compatibility baseline.

- Freeze the handoff architecture violation baseline.
- Enforce no-new/no-expanded violations and task-scoped reduction.
- Split Program/endpoints/workflow services behind unchanged upstream contracts.
- Pass `ARCH001..005` and maintainability review without deleting compatibility obligations.

Exit: no new/expanded violation, declared baseline reductions pass, upstream contracts remain hash-compatible and endpoint rollback passes.

## Phase BH-DATA: Transaction Domains And Online Migration

Entry: BH-ARCH signed exit and unchanged DownstreamPersistenceObservationSnapshot with no pending upstream migration evidence.

- Verify the observed schema/migration/caller inventory, source hashes and pending upstream migration count zero without claiming a missing upstream registry.
- Refactor one transaction domain at a time.
- Apply fenced online migration, writer drain, snapshot/watermark reconciliation and current/previous binary compatibility.
- Preserve upstream route/readback/status ownership and compatibility schema behavior.

Exit: every migrated domain passes snapshot/watermark reconciliation, current/previous binary compatibility, restore and rollback eligibility tests.

## Phase BH-RELEASE: SemVer, Bundle And Legacy Closure

Entry: BH-DATA signed exit, valid downstream standards delta chain and all compatibility removal prerequisites.

- Establish Phase platform SemVer and signed release manifest.
- Verify current/previous platform/React/DB/artifact compatibility and rollback.
- Retire legacy surfaces only when handoff compatibility classification permits removal.
- Migrate final durable rules to their handoff-owned standards sections and close downstream ledgers.

Exit: signed release/rollback manifests pass, legacy removal matches handoff classification, downstream PBR/finding ledgers close and no unresolved P0/P1/P2 remains.

## Task Sizing

One task handles one handoff verification family, one trust contract, one enforcement entrypoint, one Profile, one imported route/sub-operation policy, one handoff surface, one endpoint feature, or one transaction domain. No task combines signer/verifier/factory/React/Data changes.

Every task requires actual owner, approver, Gate, allowed/protected paths, target tests, evidence, rollback, estimated slices and expiry for exceptions.

No implementation phase may use role placeholders as actual accountability. BH-HANDOFF must complete before a downstream task exists. Before any later task moves to active, its ledger row must contain UpstreamHandoffManifest ID/hash, task ID, primary/backup owner, approver, incident contact, rollback owner, dependency task IDs, protected-path authorization reference and expected evidence path. Missing values keep that phase paused.
