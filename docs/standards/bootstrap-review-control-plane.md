# Bootstrap Review Control Plane Standard

Status: Accepted
Language: English
Authority: `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`

## Purpose

This standard defines the durable protocol for evidence-gated Bootstrap Review. It separates semantic review authority from process execution and keeps review runs recoverable from append-only evidence.

## Semantic Invariants

- A complete review uses three isolated discovery roles: Blind Hunter, Edge Case Hunter, and Acceptance Auditor.
- Discovery roles do not share sessions, candidates, suspected findings, or a minimum finding quota.
- Required artifacts and context are read completely. Sampling is prohibited.
- P0/P1 candidates require an independent verifier that is not a discovery reviewer.
- A change cycle has a three-full-round hard limit. Changing a review ID does not reset the round.
- A final result cannot contain an open accepted P0 or P1.
- Every accepted P2 must be fixed, refuted, or explicitly deferred. High-risk P2 cannot be deferred. A deferral requires owner, expiry, non-impact evidence, and a closure test; expiry blocks automatically.
- Bootstrap evidence is supplemental and never substitutes for a protected handoff, plan-local acceptance validator, production release, or commit authority.

## Ownership

| Layer | Authority |
| --- | --- |
| `docs/standards/` | Durable semantics, authority, lifecycle, recovery, and compatibility rules. |
| `.agents/skills/run-phase-bootstrap-review/` | Executable protocol, generic schemas, common validators, Artifact View, runner, attempt/event records, repair closure, and lifecycle commands. |
| `execution-plans/<plan>/` | Contract and implementation-contract instances, plan-specific predicates, fixtures, and current-plan evidence. |
| `logs/` | Append-only run, process, review, verifier, audit, and recovery evidence. |
| External global Skill | Revision-bound stateless route to the repository-owned Skill. |

The implementation backend never owns review acceptance, severity, done, commit, handoff, or release. Plan-local validators remain authoritative for plan-specific business acceptance.

## Execution Boundary

- The control plane has no hidden provider dispatch and no hidden mutable state.
- Recovery is evidence-based: durable sidecars and append-only process events must be sufficient to reconstruct the next valid action.
- Process events are execution-fact authority. Lease files are derived views and may be rebuilt.
- Before child launch, the runner atomically checks and appends an `attempt-reserved` execution fact under the process lease lock. A completed operation, completed formal role output, post-gate discovery rerun, or overlapping formal write set is rejected before `Popen`; non-overlapping role reservations remain concurrent.
- The runner refreshes the derived lease view immediately after `attempt-started`. Recovery of a dead event-backed PID appends `attempt-stale` before rebuilding the lease view so the old write set cannot remain permanently active.
- The process-event append lock records PID, process creation identity, ownership token, creation time, and an acquired/committed phase. A dead, PID-reused, incomplete stale, or committed owner lock is removed before retry; final cleanup removes the lock only when its token still belongs to the current writer and tolerates transient Windows sharing violations.
- Command execution uses argument arrays with `shell=false` semantics.
- Child environments are built from an explicit allowlist. Secrets are referenced by source identity and are never copied into evidence.
- Command templates use typed placeholders; untyped string interpolation into executable arguments is prohibited.
- Codex Exec sets the current attempt directory as the sandbox workspace root and grants `workspace-write` only there for handshake and candidate evidence. The repository root is not the child workspace. Formal outputs remain parent-owned, and no reviewed or unrelated repository path is child-writable.
- Manual and specialized-agent modes remain external execution boundaries. The repository runner v1 owns only isolated Codex Exec execution.
- The runner atomically writes formal reviewer or verifier sidecars from schema-valid child candidate output. The model cannot directly overwrite formal role output.

## Artifact View And Access Proof

- Codex Exec reads a frozen `artifact-view.v1` under the run directory and does not mix live originals with snapshots in one run.
- The manifest binds original repository path, snapshot path, both hashes, size, encoding, line count, file type, binary/text classification, reparse metadata, Windows case-normalized identity, context classes, source scope, and creation identity.
- Snapshot paths preserve repository-relative layout and reject case collisions, path escape, junction escape, and reparse escape.
- Findings cite original paths. Snapshot evidence is projected back to original inclusive line ranges.
- Codex Exec reviewer and verifier prompts identify the absolute run directory and Artifact View manifest. Sandboxed children resolve relative `snapshotPath` values against that run directory, read only snapshot content, and cite `originalPath`; they do not resolve snapshots against the attempt workspace or fall back to inaccessible or drifting live originals.
- Binary artifacts cannot claim text line evidence.
- Launch requires an identity-equivalent access probe. Each actual reviewer child must also complete a same-process, hash-bound access handshake before semantic work begins.
- The handshake executable material is generated inside the immutable attempt evidence boundary. A sandboxed child must not depend on reading the repository-owned Skill entrypoint, and the parent control plane must independently recompute the expected Artifact View coverage and handshake hash before accepting the result.
- Later live authority drift marks the old run stale. A replacement run starts from a new frozen snapshot and must not inherit stale state.

## Concurrency And Freshness

- Concurrent execution is blocked only when declared write sets overlap.
- Authorization freezes the Git index and records the reviewed write set.
- Freshness checks cover the execution read set and its dependency closure, not only the direct review scope.
- Concurrent drift in the index, reviewed write set, execution read set, dependency closure, profile, schema, validator, or preflight evidence invalidates launch authorization.

## Attempts And Lifecycle

Each process attempt has a unique immutable directory containing request, process result, stdout, stderr, token usage, and structured candidate output. `process-events.jsonl` records append-only lifecycle events. Codex Exec children return structured candidates only; they never edit formal reviewer/verifier outputs or invoke the formal validator. The parent preserves a failed payload's `failureReason` and atomically owns formal output validation.

Lifecycle state is split into three dimensions:

- Run execution: prepared, preflight-failed, authorized, layers-running, layers-incomplete, awaiting-verification, finalized, abandoned.
- Run relationship: active, superseded, replaced-after-probe-failure.
- Change cycle: review-required, repair-required, next-round-authorized, accepted, manual-pause, closed.

`list-runs` and `inspect-run` are reproducible views. `seal-run` adds an immutable annotation; it never rewrites reviewer, verifier, gate, event, lease, or final evidence. Finalized runs cannot be abandoned. Superseded runs identify their successor.

## Repair Closure

Round 2 and Round 3 require an implementation-contract instance named `repair-closure.json`.

- The canonical predecessor finding set is the exact union derived from finalized gate and disposition evidence.
- Confirmed, advisory, and refuted findings remain represented; none may disappear from the exact set.
- Fixes bind source changes, targeted validation, adjacent regression evidence, and current candidate/source/validator hashes.
- Proof type follows the finding family: regression test, negative fixture or mutation, authority counterexample or predicate proof, restricted-context process fixture, or controlled P2 deferral evidence.
- Prepare validates schema, predecessor identity, exact finding set, and proof-family compatibility.
- Authorize-launch revalidates all evidence hashes, Git index, write set, execution read set, dependency closure, and authority graph freshness.
- Missing or stale repair closure prevents any reviewer lease from starting.

## Finalized-Run Validation Envelope

The repository-owned Skill exposes `validate-finalized-run` as the only durable plan-consumption surface for a finalized Bootstrap run. The command reloads the current profile and run authority, revalidates preflight and gate evidence, reproduces candidate/rejection projection from reviewer outputs, and recomputes final result, disposition, metrics, and byte hashes.

The `bootstrap-finalized-run-validation.v1` envelope binds review/change/round identity, the complete canonical profile hash, route and control-plane revisions, policy and authority identity, final status, finding closure, validator identity, and hashes of every consumed final artifact. It always carries `authorizes=[]` and explicitly excludes plan acceptance, implementation acceptance, protected handoff, release, commit, and done.

Plans consume this envelope instead of reimplementing a partial Bootstrap profile or lifecycle validator. A plan-local validator remains solely responsible for its own candidate and acceptance predicates. Envelope validation cannot clear a review-cycle manual pause or create a new semantic-review round.

## Migration

- New plans bootstrap this protocol and own only their contract instances, predicates, fixtures, and evidence.
- Historical plans are read-only. They may receive additive compatibility adapters, backfill indexes, and shadow validation, but their generated review evidence is not rewritten.
- The 2026-07-12 Bootstrap CLI remains a compatibility entry until consumers migrate to the repository-owned Skill.
- A compatibility adapter must be stateless and revision-bound. It must fail closed when the repository-owned implementation or schema revision differs from the declared binding.
- An explicitly abandoned Codex Exec run with no gate and incomplete required layers is not a completed semantic round. It may be replaced at the same round number after the control-plane defect is repaired; the abandoned evidence remains immutable and any valid partial finding is carried into repair evidence or the replacement scope.

## Validation

Protocol changes require:

- Repository-owned Skill quick validation.
- Bootstrap CLI regression tests.
- Generic schema and fixture tests.
- Finalized-run envelope success, stale-profile, stale-artifact, and non-authorizing boundary tests.
- 2026-07-12 Whole-directory compatibility validation.
- Targeted Windows access, case-collision, reparse, atomic-write, event-rebuild, drift, repair-closure, and stale-replacement tests.
- A fresh `bootstrap-skill-route` review after deterministic checks pass.
