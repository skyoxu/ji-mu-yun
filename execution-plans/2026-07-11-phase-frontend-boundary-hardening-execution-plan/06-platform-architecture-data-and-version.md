# Platform Architecture, Data, And Version

## Correlation And Error

- Stable error/domain code plus requestId.
- `Activity.Current?.TraceId` or `HttpContext.TraceIdentifier`; return `X-Request-ID`.
- Correlate API, run, route, LLM audit, diagnostic, Permit, journal and React error.
- Never return raw exception message, stack, secret, prompt or host path.
- Fallback catch must produce explicit Result, structured log, persistent failure or backup telemetry.

## Version Endpoint Exposure

Split endpoints/projections:

- Public version: platform SemVer and API compatibility version only.
- Admin version: commit, build time, React build ID, DB schema, policy/Permit schema and artifact schema versions.
- Health endpoint does not expose detailed versions.
- Version responses use no-store and have auth/redaction tests.

Minimal build identity lands before React/Permit rollout. Full release governance lands later.

## Endpoint Architecture

Program owns configuration, DI composition, middleware order, endpoint registration and lifecycle only.

Architecture refactor starts only after BH-HANDOFF and consumes the upstream source baseline, compatibility preservation list and route/API owner map. It may move implementation behind unchanged upstream contracts but cannot redefine route/status/readback/diagnostic/UI/GDD semantics.

- Feature endpoint modules do not access DB, runner or filesystem directly.
- Browser/Endpoints -> Application Features -> Contracts/Ports <- Infrastructure.
- Public route/auth/DTO/status remains compatible with upstream contracts.
- Line count is review trigger, not acceptance. Responsibility and dependency tests are authoritative.

### Enforceable Dependency Matrix

```text
Browser/Endpoints -> Application Features -> Domain/Contracts
Infrastructure ---------------------------> Domain/Contracts
Composition Root -------------------------> all modules for wiring only
Domain/Contracts -------------------------> no Platform infrastructure or browser module
```

- Browser/Endpoints may parse/authenticate/map HTTP and call one Application Feature; they cannot use metadata DB, filesystem, process runner, Codex factory, journal or concrete infrastructure.
- Application Features own use-case orchestration and transaction boundaries; they depend on narrow ports/contracts, not endpoint DTOs or infrastructure implementations.
- Domain types keep invariants and behavior with their data. Anemic record-plus-service splits require an explicit serialization/persistence boundary reason.
- Infrastructure implements ports and cannot call browser modules or own business status decisions.
- Interfaces are created only at cross-module, infrastructure, external-system or test-substitution boundaries. A one-implementation private helper does not automatically receive an interface.
- Composition Root contains no business branching, SQL, filesystem operation, prompt building or response rendering.

### Maintainability Guardrails

- A class has one named reason to change; endpoint registration, rendering, persistence, orchestration and process execution cannot coexist in one class.
- Prefer composition. Business inheritance depth greater than three fails; new inheritance requires a framework/polymorphic contract reason.
- Constants are centralized only when they are shared policy/protocol vocabulary. Feature-local literals remain near the owning behavior to avoid global junk drawers and false DRY.
- Duplication is removed only when meaning and change cadence are the same. Similar code in different bounded contexts is not automatically unified.
- Names use business/action vocabulary and avoid generic `Manager`, `Helper`, `Utils`, `Data` or unexplained abbreviations. Comments explain rationale, invariant or workaround, not a restatement of code.
- `Program.cs` remains composition only. `BrowserUiRenderer.cs` is frozen for feature growth and retired by React surface migration rather than expanded or mechanically split into another monolith.

Mechanical architecture checks publish stable rule IDs and machine-readable exceptions:

- `ARCH001`: forbidden project/namespace dependency from the approved matrix
- `ARCH002`: endpoint module references concrete Data/filesystem/process/runner infrastructure
- `ARCH003`: Composition Root contains non-wiring calls or business branching outside an exact framework allowlist
- `ARCH004`: business inheritance depth exceeds three
- `ARCH005`: shared protocol/status/route vocabulary uses an unregistered string outside the owning contract

Responsibility cohesion, naming clarity, interface necessity, comment rationale, over-DRY and data-with-behavior are human-review gates, not falsely automated semantics. Their review record uses a stable checklist with reviewer, affected types, pass/fail rationale, ADR/exception ID and expiry. A task cannot claim architecture acceptance without both analyzer output and the human-review record. Exceptions require ADR, owner and expiry.

### Architecture Baseline And Ratchet

- BH-HANDOFF records every existing `ARCH001..005` violation with source path, dependency/type, upstream reason, compatibility relation and owner.
- Initial downstream Gate prohibits new violations and expansion of existing dependency edges while allowing only the exact baseline rows.
- Each BH-ARCH task declares rows removed, unchanged or temporarily split; baseline count and affected-edge surface cannot increase.
- A compatibility shim from the handoff is not removable merely to reduce the count; its compatibility classification wins until authorized removal.
- Architecture acceptance compares against the handoff baseline and fails unknown, expanded, ownerless or expired rows.

## Data Refactor

Create transaction-domain ledger before migration:

- Accounts
- Projects
- Runs/Artifacts
- LLM
- Iterations
- Chat
- Diagnostics
- Permit/Mutation trusted state

Each slice:

1. characterization/persistence/recovery tests
2. one transaction domain
3. minimal repository/port
4. preserve concurrency/cancellation/recovery
5. migrate callers
6. remove facade methods

Data cannot depend on Runs/Readback internal DTO. Readback cannot queue, execute processes or mutate business state.

## Database Expand-Contract And Rollback Compatibility

BH-DATA begins from the manifest-bound `DownstreamPersistenceObservationSnapshot`, derived read-only from the final upstream commit plus a protected metadata DB copy/backup. It records observed schema objects, migration markers/history where present, table/index callers, pending upstream migration evidence and source hashes without claiming an upstream schema registry exists. It cannot allocate a migration, rename ownership or refactor a table while an upstream migration/deferral remains pending or the observation is incomplete. Permit/session/journal/evidence tables use distinct downstream migration IDs and ownership.

- Application rollback never performs automatic DB downgrade.
- Schema changes during current+previous bundle window are expand-only: additive tables/columns/indexes and backward-compatible reads/writes.
- Rename/drop/type-narrowing/semantic repurpose waits until previous bundle support window closes and a contract migration is approved.
- Current and previous platform binaries are tested against the current DB schema fixture before release.
- Release manifest records `minimumCompatibleDbSchema`, `maximumCompatibleDbSchema`, migration direction and rollback eligibility.
- If previous bundle is incompatible with current DB schema, deployment rollback is blocked and operator receives the compatible recovery path.
- Dual-read/write compatibility is time-bounded with owner, expiry, consistency tests and removal task; it cannot become permanent shim.
- Permit/session/journal tables follow the same expand-contract rule and restore drills.

### Online Migration State Machine

```text
planned -> expanded -> backfilling -> dual_read_write -> verified -> contract_eligible -> contracted
   |          |             |                  |              |             |
   +----------+-------------+------------------+--------------+-------------+-> failed_retryable -> retry
                                                                  |
                                                                  +-> manual_recovery_required
```

- Migration ownership, minimum application version, compatibility window, batch/checkpoint key, retry limit and rollback/forward-recovery action are recorded before execution.
- A protected migration lease with fencing token permits exactly one migration coordinator/checkpoint writer. Every batch and state transition validates the current fencing token.
- Expand DDL is idempotent and transactionally recorded. Application startup never assumes a partially applied migration is complete.
- Backfill is bounded, resumable and checkpointed; rows written during backfill are handled by transactional dual-write or an ordered change-capture mechanism.
- Before backfill begins, all active writers must either support the accepted dual-write/change-capture contract or be fenced/drained. A previous binary without that capability may remain read-only but cannot continue writing.
- Dual-write updates old/new representations atomically in the same DB transaction when possible. If impossible, an ADR-approved outbox/reconciliation design is required; best-effort sequential writes are prohibited.
- Verification before `contract_eligible` is a full reconciliation of all migrated rows and domain invariants, not sampling. It compares row counts, nullability/domain invariants, deterministic hashes/aggregates and read results through every supported writer/reader version.
- Full reconciliation runs against one database snapshot/change watermark. Writers either pause briefly or publish an ordered watermark; verification proves all changes through that watermark are present in both representations before advancing.
- Every migration state may enter `failed_retryable` or `manual_recovery_required` with checkpoint, fencing token, reason and forward/restore action. Failure injection covers crash before/after DDL, mid-batch backfill, one side of dual-write, service restart, previous-binary write, verification failure, contract failure and retry exhaustion.
- Contract/drop cannot begin until the previous-bundle window closes, all incompatible writers are drained/fenced, full reconciliation remains green for the accepted observation period, a verified restore point exists and a separately authorized migration task exists.
- Handoff `must_preserve` or unexpired `time_bounded_compatibility` schema/read behavior cannot enter contract/drop even when technical reconciliation passes.

## Workflow Service Refactor

- Split Web Preview into orchestration, generator/exporter and readback query.
- Extract policy, prompt builder, state reader/writer, validator and process adapter from giant workflow services.
- Interfaces only at replaceable infrastructure/cross-feature/test boundaries.
- Extraction preserves upstream action descriptors, status dimensions, recovery/readback authority, acceptance refs and compatibility entries by handoff hash; it does not create a second workflow contract.

## SemVer And Release

- Tag: `phase-platform-v0.x.y`.
- MAJOR: incompatible API/auth/data ownership/artifact contract.
- MINOR: backward-compatible capability.
- PATCH: backward-compatible fix.
- DB and artifact schemas version independently.

Release manifest contains platform version, commit, build time, React bundle, SBOM/provenance, policy/Permit schema, DB/artifact schema, migration and rollback compatibility.

## Durable Standards Section Ownership

- UpstreamHandoffManifest lists each relevant standards/ADR/workflow/index path, section anchor, owner plan/domain and content hash.
- Handoff hashes freeze only upstream-owned canonical sections. Downstream-owned section hashes advance through an append-only `DownstreamStandardsDeltaManifest` chain containing parent delta hash, handoff ID/hash, phase/task, changed section anchors, before/after hashes, owner and ADR/decision ref.
- Downstream may append or supersede only sections assigned to Permit/containment/Mutation/React-technical/platform-architecture/version/evidence governance. It references upstream route/status/readback/diagnostic/UI/GDD sections without copying their normative text. A legal downstream section update changes the delta chain, not the immutable handoff.
- A change crossing an upstream-owned section requires a separately approved successor ADR/decision log and refreshed handoff; parallel edits or silent threshold duplication are prohibited.
- Validator combines immutable upstream section hashes with the latest valid downstream delta chain and fails duplicate section owners, copied normative blocks, stale upstream hashes, broken delta ancestry and a downstream durable rule with no declared destination.

## Acceptance

- New reverse dependency and fourth-level business inheritance fail tests.
- `ARCH001..005` analyzer checks and the stable human maintainability review pass or have ADR-bound exceptions.
- Version public/admin boundary passes authorization tests.
- MetadataStore receives no new domain responsibility and is eventually removed or time-bounded thin facade.
- Readback has no mutation/process behavior.
- Release tag does not trigger Godot template release.
- Running instance uniquely identifies compatible platform/React/policy/DB bundle.
- Current and previous binaries pass current-schema compatibility tests; incompatible previous bundle cannot be selected for rollback.
- Online migration crash/backfill/dual-write/reconciliation/previous-writer tests pass before a schema is rollback-eligible.
