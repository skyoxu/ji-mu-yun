# Evidence, Telemetry, And Performance

## Retention Authority

After BH-HANDOFF and before downstream evidence implementation, security/operations ADR must approve retention using:

- expected jobs/day by Profile
- average and P95 evidence size
- annual storage estimate
- account/project deletion and privacy request handling
- security audit retention obligations
- unresolved finding preservation
- secure deletion and cleanup audit

Defaults until a stricter standard is accepted:

- Successful detailed Preflight/Permit/Mutation evidence: 90 days.
- Compact redacted audit row: at least 365 days.
- Rejected/rollback/security failures: at least 365 days.
- Unresolved P0/P1/P2: no automatic deletion.
- Prompt body absent by default; store hash and authority refs.
- Workspace deletion does not delete unresolved security/diagnostic evidence.
- Downstream evidence stores Permit/attestation/containment/lease/Mutation/React-technical/platform-governance facts. Upstream route, Godot diagnostic, admin review, UI closure and business readback evidence remain in their handoff-owned schemas; downstream records only immutable upstream evidence IDs/hashes and correlation IDs.

Cleanup is append-only audited with rule version, actor, time, scope, count and retained summary.

## BH-HANDOFF Bootstrap Custody

Before BH-SF0B creates the general protected evidence store, BH-HANDOFF evidence uses bootstrap custody defined by BootstrapHandoffContract: two independently administered append-only copies, Ed25519 signatures from both approvers, an external timestamp/commitment for the manifest bundle hash, and a protected ActiveRegistry CAS record. Ordinary `*-latest.json` files remain readback pointers and cannot select authority. Loss of either evidence copy blocks activation or recovery; later BH-SF0B imports and verifies the complete bootstrap chain without rewriting its original files.

## Stable Evidence Paths

```text
logs/phase-a-innernet/reviews/platform-boundary-hardening/
  threat-model/
  permit/
  preflight/
  postflight/
  containment/
  mutation/
  quarantine/
  react/
  architecture/
  release/
  phase-exit/
  upstream-handoff/
```

- Run-id/timestamp files are immutable history.
- `*-latest.json` is a pointer/readback copy only and cannot overwrite run-id evidence.
- Evidence refs include kind, account/project/task/route/run/permit/journal IDs as applicable, build/policy/schema versions and redacted relative path.
- Every downstream record includes UpstreamHandoffManifest ID/hash, handoffEpoch, selected StateEvent hash and ActiveRegistry rowVersion and, when route/business evidence is involved, the upstream evidence schema/record ID/hash rather than copying its payload or taxonomy.
- Normal users never receive host paths or cross-account evidence refs.
- Permit, Test/Acceptance Attestation, Postflight, journal and phase-exit evidence are written by protected service identities to a store/path not writable by Codex, generated project code, repository tests or ordinary browser handlers.
- Each immutable record includes monotonic scope sequence, content hash, previous-record hash or signed manifest reference, writer identity, schema version and creation time. Append uses compare-and-swap on one protected chain head per scope; concurrent writers retry and cannot create accepted forks. A `latest` pointer cannot change or invalidate immutable history.
- CI rejects evidence whose writer, signature/hash chain, schema, run scope or protected-store origin cannot be verified. Repository-created lookalike files are untrusted diagnostics.
- Evidence cleanup uses a distinct least-privilege identity that may request/delete only policy-selected payloads. It cannot alter the externally anchored deletion audit or chain head. Deletion audit is written by a separate protected audit authority and periodically anchored outside the cleanup/storage administrative boundary.
- Sensitive evidence, rollback backup and quarantine payloads are encrypted at rest with account/project-scoped data keys wrapped by a protected key service. Backup key custody, rotation, access audit and cryptographic erasure are tested; secret scanning/redaction runs before normal evidence persistence, while raw security evidence uses a separately authorized encrypted vault.

## Capacity Gate

Implementation cannot enable full rollout until capacity report proves:

```text
daily raw bytes
annual raw bytes
compacted annual bytes
peak DB rows/index cost
backup and restore impact
cleanup duration
```

If capacity exceeds approved budget, reduce evidence verbosity or compact success records; never delete unresolved failure evidence to meet budget.

Capacity approval also defines per-file/run/project/account/host hard quotas, journal/rollback reserved capacity and emergency free-space watermark. Preflight denies new workspace-write before a quota or reserve would be crossed; retention policy is not permission for unbounded writes.

## Telemetry

Record by build/policy/profile/route/account-safe scope:

- Preflight pass/block and reason
- Permit issue/claim/consume/expire/replay/revoke
- attestation/verifier version and rejection
- factory missing-Permit rejection
- containment/network/tool/process denial
- lease heartbeat/stale/takeover/conflict
- Mutation allow/deny/commit/rollback/recovery
- Acceptance attestation/rollback outcome with upstream acceptance evidence ID/hash; downstream does not redefine upstream acceptance states
- React session/CSRF, technical fallback and asset/version mismatch; business route/readback/diagnostic metrics remain upstream-owned

Permit Authority/verifier operational metrics:

- issue/claim/verify availability
- P50/P95/P99 latency
- store/verifier/key/clock error rate
- queue depth and outage duration
- read-only degraded-mode activations
- alert acknowledgement and recovery time

Workspace-write SLO excludes planned fail-closed outage only when an incident record exists; security checks are never bypassed to meet availability target.

## Audit-Only Evaluation

Audit-only cannot prove containment false negatives by itself. Evaluation requires:

- enforced OS containment remains active
- shadow Work Policy decision recorded
- seeded negative corpus for paths/delete/rename/capabilities
- sampled manual diff review
- comparison between shadow decision and expected fixture result

Minimum: 7 days and 100 representative runs. Maximum is 14 days; one two-approver extension may add at most 14 days and must state missing sample classes, owner and forced decision date. A second extension is prohibited: the feature is disabled or enforcement decision is made. No unresolved false negative or P0/P1 before enforce.

## Performance Measurement Method

Every benchmark evidence records:

- CPU/RAM/storage/Windows version
- local/CI/live environment
- workspace file count, total bytes and changed bytes
- cold/warm cache
- concurrency and background load
- sample count and percentile calculation
- build/policy/version

Budgets:

- Permit verify P95 <= 100 ms.
- Deterministic Preflight excluding external probe P95 <= 2 s.
- Supported-size incremental inventory P95 <= 5 s.
- Change-limit diff/journal validation P95 <= 10 s.
- React initial gzip JS <= 500 KB and CSS <= 100 KB unless approved split plan.

Initial supported workspace fixture, replaceable by a measured capacity ADR:

- at most 25,000 directory entries and 10,000 regular files
- at most 2 GiB total scoped bytes
- at most 256 MiB changed bytes and 2,000 changed entries per run
- at most 128 MiB per file, path depth 32 and normalized relative path length 240 characters
- fixture set includes at least 10% binary files plus add/modify/delete/rename and cold/warm cache runs

Larger workspaces fail Preflight with a stable capacity code until a separately benchmarked profile is approved; the implementation must not silently exceed the budget or skip manifest/security checks.

Timeout returns stable failure and never disables security checks.

## Acceptance

- Retention ADR includes capacity and privacy analysis.
- Cleanup does not remove unresolved evidence.
- Telemetry can reconstruct one complete Permit -> Mutation -> Acceptance timeline.
- Protected evidence custody rejects forged repository reports and detects immutable-history tampering.
- Concurrent evidence append and malicious cleanup cannot fork the chain or erase deletion audit.
- Per-scope quotas, journal reserve and emergency watermark block disk-exhaustion cases without breaking rollback.
- Benchmarks are reproducible from recorded environment and fixture.
- Supported workspace limits are enforced and the boundary fixture meets every P95 budget.
- Audit-only exit has fixture and sampled-review evidence, not only pass rate.
