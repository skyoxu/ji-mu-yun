# Risks, Definition Of Done, And Glossary

## Key Risks

| Risk | Mandatory control |
| --- | --- |
| CI attestation key exposure | asymmetric signing; CI public key only |
| Downstream overlaps unfinished upstream refactor | strict BH-HANDOFF before any implementation task or path mutation |
| Downstream duplicates business authority | immutable handoff projections for surfaces/actions/status/readback/diagnostics/schema/standards |
| Handoff task weakens its own verifier or rules | externally signed BootstrapHandoffContract; validator/rules/plan/spec are read-only during handoff |
| Handoff lock exists only as documentation | selected external lock backend, fencing token, launcher/write denial and recovery evidence |
| Multiple manifests claim active | immutable manifest + append-only state events + single CAS ActiveRegistry |
| Handoff demands artifacts upstream never promised | field-level HandoffSourceMap and downstream-derived frontend/API/persistence observation snapshots |
| Capability deferral is mistaken for unresolved finding | upstream Phase 6 review findings remain zero; only upstream-ledger capability deferrals are classified |
| Stale/selective upstream handoff | signed manifest binding final commit, all phase/global closure, deferrals and compatibility lists |
| PR changes its own verifier | external/pinned verifier trust anchor |
| Preflight does not prove final change | trusted Postflight attestation bound to actual diff/test/evidence |
| Codex/Phase code can use signer as an oracle | separately deployed signer identity, private-key ACL, authenticated Permit-bound request and protected binary pin |
| Codex fabricates a passing test report | independent CI rerun or protected Test/Acceptance Attestation bound to exact diff/runner/command/result |
| Text diff misses Platform source, Hosted snapshot or effective Windows content | distinct SourceChangeManifest/SnapshotChangeManifest/HostEffectiveManifest verification |
| Codex provider network leaks to tools | controller proxy + no-network tool broker |
| Generated project attacks Acceptance host | restricted no-network Acceptance runner with Job Object and protected attestation |
| Untrusted worker hides side effects | supervisor/OS-derived ledger; worker self-report is diagnostics only |
| React steals long-lived token | server session exchange; HttpOnly/Secure Cookie; no browser token storage |
| CSRF after Cookie auth | anti-CSRF token/header + Origin validation |
| Public HTTP token exposure | public trial blocked until HTTPS closure |
| Permit replay/scope confusion | atomic claim, nonce, complete binding, short TTL |
| Concurrent workspace overwrite | persistent lease, heartbeat, baseline recheck |
| Stale lease holder writes after takeover | project-level uniqueness plus monotonic fencing token on every mutation/finalization |
| Crash during writeback | same-volume staging, journal, rollback |
| Acceptance/Postflight races with a new mutation | lease held through Acceptance, final manifest/signature and rollback; post-commit hash check; rollback_conflict |
| Invalid committed project | acceptance failure defaults to rollback/quarantine |
| React/backend version mismatch | current+previous 14-day compatibility and versioned bundle |
| Previous binary corrupts newer DB | expand-contract schema and current-schema compatibility matrix |
| Evidence growth/privacy | retention ADR, capacity report, secure cleanup audit |
| Evidence/quarantine exhausts disk | per-scope hard quotas, rollback reserve and emergency free-space watermark |
| Online DB migration becomes partially inconsistent | checkpointed backfill, atomic dual-write/outbox, reconciliation and failure injection |
| Plan/document drift | split authority, one owner per book, durable standards migration |

## Global Definition Of Done

1. Threat model and trust anchor accepted.
2. BH-HANDOFF proves upstream Phase 0-6/global review/closure/final commit complete with zero unresolved P0/P1/P2 findings, and no downstream implementation ran earlier.
3. BootstrapHandoffContract pins schema/canonicalization/signature/verifier/lock/allowlist before the handoff task and prevents self-modification.
4. Immutable manifest, append-only state-event chain and protected CAS ActiveRegistry select exactly one handoff/epoch.
5. Every downstream surface/action/status/evidence/persistence/standards/compatibility reference resolves through one HandoffSourceMap; downstream-derived snapshots never claim upstream business ownership.
6. Private signing material never enters PR/CI code execution.
7. Central factory rejects workspace-write without trusted Permit context.
8. Protected-path merge requires Postflight attestation matching actual diff and tests.
9. Signing service is process/identity separated; Codex, Phase Web, repository tests and CI cannot read the key or invoke an unrestricted signing oracle.
10. Protected completion uses independent rerun or trusted Test/Acceptance Attestation; report-file hashes alone never pass.
11. Platform SourceChangeManifest, Hosted SnapshotChangeManifest and HostEffectiveManifest tests prove source/snapshot/effective-content binding.
12. Platform isolated-workspace apply plus Hosted controller/tool/Acceptance boundaries pass actual-host tests; Platform or Hosted failure blocks/corrects course before BH-SF2.
13. Every Phase service actor uses equal-assurance Preflight/Postflight after handoff.
14. Permit, fenced Mutation and Acceptance states are complete, independent and recoverable; conflict projects remain recovery-blocked.
15. Lease remains held through Acceptance, trusted Postflight persistence and rollback; Acceptance failure defaults to rollback without overwriting newer work.
16. Handoff supersession invalidates rather than rebinds in-flight work and preserves historical-only evidence.
17. Public `/ui-v2` consumes handoff-derived technical observations plus upstream business refs and passes HTTPS/session/CSRF/XSS/cache/CSP/CORS/trusted-proxy and quantitative trial Gates.
18. React bundle has generated handoff-bound contracts, isolated dependency build, signed SBOM/provenance/checksums and DB-compatible rollback.
19. Architecture ratchet, handoff-bound Data migration, correlation and version tests pass without deleting protected compatibility.
20. Protected encrypted evidence custody, retention, per-scope capacity, telemetry and supported-workspace performance pass without duplicating upstream diagnostics.
21. Split/cross-plan overlap validator and source coverage checks run from BH-HANDOFF onward.
22. No unresolved P0/P1; P2 is zero or has named owner, expiry and recheck trigger.
23. Durable rules land only in their handoff-owned standards/ADR/workflow sections.

## Glossary

| Term | Meaning | Creator | Trust | Persistence |
| --- | --- | --- | --- | --- |
| Policy Kernel | Common machine rules for Codex jobs | Platform security/runtime | Trusted after version/hash validation | Source + fixture |
| BootstrapHandoffContract | Pre-task signed bootstrap schema/verifier/lock/registry/custody contract | Two external approvers | Trusted after protected signature and digest validation | Two custody copies + local readback |
| UpstreamHandoffManifest | Immutable downstream input binding completed upstream code/contracts/evidence/schema/standards/compatibility | BH-HANDOFF reviewers | Trusted after signature/hash/closure validation | Protected immutable evidence |
| UpstreamHandoffStateEvent | Append-only active/superseded/revoked transition for one handoff | Protected handoff authority | Trusted after signature and event-chain validation | Protected event chain |
| UpstreamHandoffActiveRegistry | CAS selector for the current handoff/epoch/event; not evidence itself | Protected registry service | Trusted only with matching signed event | Protected transactional store |
| HandoffSourceMap | Field-level mapping from manifest output to committed/evidence/derived source | BH-HANDOFF collector | Trusted after source/hash/transform validation | Handoff bundle |
| Downstream Observation Snapshot | Frontend/API/persistence technical observation that cannot own business semantics | Protected handoff collector | Trusted only as downstream-derived evidence | Handoff bundle |
| Profile | Actor-specific Policy specialization | Platform governance | Trusted configuration | Source + fixture |
| Preflight | Deterministic checks before authority | Host/platform | Trusted result | Evidence/store |
| Work Declaration | Codex statement of intended work | Codex | Untrusted claim | Evidence only |
| Permit | One-time scoped authorization | Permit authority | Trusted | Protected store |
| Preflight Attestation | Signed evidence of allowed Platform Development scope before work | Host launcher | Trusted after external verification | Logs/CI artifact |
| Postflight Attestation | Signed evidence binding actual final source/host manifests, tests and evidence after work | Remote Attestation Authority from protected supervisor observations | Trusted after external verification and CI source-manifest recomputation | Protected store/CI artifact |
| SnapshotChangeManifest | Hosted baseline/final directory delta when route completion does not create a Git commit | Trusted mutation supervisor | Trusted after protected snapshot custody and hash verification | Journal/evidence |
| Verifier | Independent Permit/attestation validator | Security-owned trust anchor | Trusted | Outside reviewed PR |
| Work Policy | Execution permission bound to route descriptor | Platform governance | Trusted registry | Source + fixture |
| Containment | OS/process/network boundary during execution | Host runtime | Trusted only after negative tests | Runtime config/evidence |
| Tool Broker | Permit-bound IPC service that validates and launches restricted worker tools | Host runtime | Trusted enforcement | Protected service/evidence |
| Lease | Exclusive project mutation ownership | Platform runtime | Trusted | Protected persistent store |
| Mutation Journal | Crash-recoverable file apply state | Platform runtime | Trusted | Protected store |
| Acceptance | Business validation after Mutation | Upstream route authority | Trusted business result | Route state/evidence |
| Quarantine | Failed focused workspace retained without becoming active project state | Platform runtime | Untrusted content, trusted custody | Restricted evidence storage |
| Session Exchange | HTTPS bootstrap that converts raw user token into opaque server-side browser session | Auth service | Trusted after token validation | Session store/audit |
| Deployment Bundle | Versioned platform binary, React assets, SBOM, provenance and compatibility manifest | Release pipeline | Trusted after signature/checksum validation | External runtime build root/release artifact |

## Review Stop Conditions

- Threat model P0/P1 open.
- BH-HANDOFF missing/incomplete, upstream still active/dirty, or any downstream implementation task exists before handoff.
- Downstream duplicates or changes an upstream surface/action/status/readback/diagnostic/UI/schema/standards owner without a new authorized handoff.
- Verifier can be changed by reviewed PR.
- Private attestation key visible to CI job executing repository code.
- Postflight attestation does not match actual reviewed diff/tests/evidence.
- Signer shares an identity/key boundary with Codex, Phase Web, reviewed repository code or CI, or accepts caller-asserted completion data.
- Passing tests are represented only by an unsigned/untrusted report hash.
- Source/host manifest pair does not cover reproducible source content and effective Windows entries/aliases.
- Hosted controller/tool network split unproven.
- Platform primary-worktree/live-data isolation or trusted reviewed-diff apply unproven.
- Generated-content Acceptance runner isolation or trusted attestation unproven.
- React public trial without HTTPS/session/CSRF closure.
- Lease does not cover Acceptance/Postflight/rollback or rollback conflict protection is unproven.
- Previous bundle is not proven compatible with current DB schema.
- Mutation rollback, quarantine, side-effect cleanup or restart recovery unproven.
- Side-effect evidence relies on worker self-report, or evidence/quarantine can consume rollback reserve.
- Online migration/backfill/dual-write failure recovery is unproven.
- Actual owner/approver missing.
- Mutation lease lacks project uniqueness/fencing or conflict project recovery block.
