# Bootstrap Review Control Plane Standard

Status: Accepted
Language: English
Authorities: `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`, `docs/adr/ADR-0045-bootstrap-verifier-semantic-commit-and-recovery.md`, `docs/adr/ADR-0049-bootstrap-controller-owned-coverage-and-attempt-retry.md`, `docs/adr/ADR-0051-bootstrap-lineage-family-and-bounded-repair-reentry.md`, and `docs/adr/ADR-0052-bootstrap-review-calibration-and-exact-envelope-reuse.md`

## Purpose

This standard defines the durable protocol for evidence-gated Bootstrap Review. It separates semantic review authority from process execution and keeps review runs recoverable from append-only evidence.

## Semantic Invariants

- A complete review uses three isolated discovery roles: Blind Hunter, Edge Case Hunter, and Acceptance Auditor.
- Discovery roles do not share sessions, candidates, suspected findings, or a minimum finding quota.
- Required artifacts and context are read completely. Sampling is prohibited.
- P0/P1 candidates require an independent verifier that is not a discovery reviewer.
- A stable lineage family has a default two-round budget and a three-full-round hard limit. Changing a review ID, `changeId`, or successor directory does not reset the family budget.
- A final result cannot contain an open accepted P0 or P1.
- A clean or P2-only finalized predecessor does not trigger another complete semantic review. P2 is disposed in the current run with typed targeted evidence.
- Every accepted P2 must be fixed, refuted, or explicitly deferred. High-risk P2 cannot be deferred. A deferral requires schema-valid typed owner, command-registry, non-impact, recheck, and process-result documents bound to the current review, input, frozen candidate, policy, authority root, finding, scope, immutable command descriptor, runner identity, append-only process event, stdout/stderr bytes, success exit, and expiry. Expiry or any stale transitive byte blocks automatically. Successful typed closure-process evidence is required when the disposition becomes fixed or refuted, not while it remains deferred. These proof documents always carry `authorizes=[]` and exclude implementation acceptance, protected handoff, release, commit, and done.
- Each canonical profile hash-binds the authority-root registry. Successor and P2 owner authorities terminate only at that exact root, and command registries must use a root-authorized signer, runner, executable, consumer, and command class. Self-created null-predecessor authorities are not trust anchors.
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
- The runner atomically writes formal reviewer or verifier sidecars from schema-valid child candidate output. The model cannot directly overwrite formal role output. Completed reviewer and verifier payloads revalidate frozen launch authority immediately before publication; if that pre-publication check fails, the prior formal bytes remain unchanged and the attempt fails. An explicit child failure is a retryable transport failure and does not replace the pending formal reviewer output.
- Codex discovery children return semantic candidates plus a compact Artifact View read receipt, never formal coverage arrays. After validating the same-session handshake and receipt, the parent constructs `requiredArtifacts` and `readArtifacts` from the frozen manifest's ordered artifact list and sets `missingArtifacts=[]`. Manual and specialized-agent formal outputs retain explicit coverage validation.
- The verifier runtime prompt derives each blocker's full inclusive evidence range and complete `contextRead` set from the frozen, hash-bound candidate sidecar. A saved or generated start-line-only summary is not sufficient execution input, and one `evidenceChecked` reference must cover the entire finding range.
- Before publishing verifier output, the parent validates its binding, exact blocker evidence coverage, and complete `contextRead` coverage against the frozen gate. A semantic failure appends failed-attempt evidence and leaves formal output unchanged.
- A completed semantically invalid Codex verifier output may be reopened only through `recover-verifier` under ADR-0045. The command preserves the rejected bytes in a unique hash-bound recovery directory, appends a `verifier-recovery-opened` process event, and does not clear the formal file. Valid, finalized, sealed, active-attempt, or non-Codex verifier state cannot use this recovery lane.

## Artifact View And Access Proof

- Codex Exec reads a frozen `artifact-view.v1` under the run directory and does not mix live originals with snapshots in one run.
- The manifest binds original repository path, snapshot path, both hashes, size, encoding, line count, file type, binary/text classification, reparse metadata, Windows case-normalized identity, context classes, source scope, and creation identity.
- Snapshot paths preserve repository-relative layout and reject case collisions, path escape, junction escape, and reparse escape.
- Findings cite original paths. Snapshot evidence is projected back to original inclusive line ranges.
- Codex Exec reviewer and verifier prompts identify the absolute run directory and Artifact View manifest. Sandboxed children resolve relative `snapshotPath` values against that run directory, read only snapshot content, and cite `originalPath`; they do not resolve snapshots against the attempt workspace or fall back to inaccessible or drifting live originals.
- Binary artifacts cannot claim text line evidence.
- Launch requires an identity-equivalent access probe. Each actual reviewer child must also complete a same-process, hash-bound access handshake before semantic work begins.
- The handshake executable material is generated inside the immutable attempt evidence boundary. A sandboxed child must not depend on reading the repository-owned Skill entrypoint, and the parent control plane must independently recompute the expected Artifact View coverage and handshake hash before accepting the result.
- A completed Codex discovery payload binds `bootstrap-artifact-view-read-receipt.v1` to the exact Artifact View manifest hash and artifact count. The receipt and handshake establish controller-visible execution coverage; neither claims to prove model cognition.
- Later live authority drift marks the old run stale. A replacement run starts from a new frozen snapshot and must not inherit stale state.

## Review Scope Closure

- `bootstrap-upstream-plan` may review a complete plan directory because the directory is the review object.
- `bootstrap-implementation-conformance`, `bootstrap-skill-route`, and `bootstrap-focused-change` default to explicit files forming the smallest complete consumer closure: change intent or plan authority, changed implementation, direct consumers, targeted tests and acceptance, repository rules, referenced standards, and current evidence required by the profile.
- A directory passed to a bounded profile requires the exact `directory-is-minimal-complete-closure` attestation. The attestation is non-authorizing and does not permit sampling inside that directory.
- Unchanged repository areas and adjacent cleanup remain out of scope unless a direct dependency or reachable failure path makes them part of the closure.

## Concurrency And Freshness

- Concurrent execution is blocked only when declared write sets overlap.
- Authorization freezes the Git index and records the reviewed write set.
- Freshness checks cover the execution read set and its dependency closure, not only the direct review scope.
- Concurrent drift in the index, reviewed write set, execution read set, dependency closure, profile, schema, validator, or preflight evidence invalidates launch authorization.

## Attempts And Lifecycle

Each process attempt has a unique immutable directory containing request, process result, stdout, stderr, and token usage. A completed attempt must also retain its structured candidate output, access handshake, and exact helper/request bytes. A failed transport attempt may lack valid candidate or handshake output, but its cost remains usable only when its process, token, and append-only lifecycle evidence is complete. `process-events.jsonl` records append-only lifecycle events. Codex Exec children return structured candidates only; they never edit formal reviewer/verifier outputs or invoke the formal validator. Child process failure, malformed JSON, invalid binding, invalid read receipt, or invalid candidate shape appends a transport-class `attempt-failed`, preserves formal bytes, and retries in the same run without consuming a semantic round or requiring a successor lineage.

Verifier recovery directories are immutable execution evidence. An open recovery is valid only while the live formal verifier bytes still equal the archived rejected hash. Its process event projects the verifier lease to `failed`, allowing a new reservation; only a later semantically valid publication and `attempt-completed` event close it. Finalize and finalized-run validation fail closed on an open or stale recovery lineage.

P2 command results reference both their immutable event sidecar and the shared append-only process log. New results anchor the event's hash rather than the mutable whole-log byte hash; validation replays the complete chain and requires the anchored event exactly once. Later valid appends therefore preserve earlier results. Legacy whole-log hash references remain valid while their exact historical log bytes are still current.

## Lineage Family And Bounded Re-entry

- Every new run declares `lineageFamilyId`; consumers derive and retain it from
  the original acceptance target. Historical manifests without the field use
  `changeId` as a read-only compatibility family.
- Bridge pre-family history only with `adopt-lineage`, explicit historical run
  paths, and a hash-bound policy document whose status is `Accepted`. Do not
  rewrite old manifests or infer adoption from directory location.
- The Git-local Bootstrap run registry is a non-authoritative path index. Every
  indexed manifest and adoption record must pass current byte-hash and schema
  validation before it contributes to lineage state. The registry binds the
  source Git revision; a revision change rebuilds it from repository history,
  while controller-created same-revision evidence is registered explicitly.
- A semantic round is consumed when semantic reviewer execution starts. Access
  probe and transport failures remain attempts inside the same round.
- Round 1 uses the minimal complete closure. Round 2 uses the repair delta:
  added, changed, and removed artifacts plus unchanged support artifacts needed
  for direct consumers, authority, targeted tests, and current validation.
- Round 3 requires one schema-valid entry reason: `novel_p0_p1`,
  `authority_context_graph_changed`, or `high_risk_boundary_changed`.
- A successor for the same acceptance target retains the family. It cannot
  restart Round 1 or clear `manual_pause`. A genuinely different target needs
  an explicit supersede or incompatible-scope decision before deriving a new
  family.
- `inspect-lineage` reconstructs consumed rounds from run evidence. Its output
  is hash-bound, non-authorizing, and required by bounded routing even when it
  reports zero rounds; omission never means a fresh budget. Artifact View,
  acceptance snapshot, and nested agent-worktree copies are derived evidence,
  not review-history entries.
- Implementation-acceptance consumers audit sibling callsites and successful
  controlled producer/consumer composition before repair re-entry. Present
  changed paths are content-hash bound and deleted paths use explicit
  tombstones. Each composition check covers a changed path, uses declared
  direct consumers, and binds its receipt as a validation reference. Repair
  paths, inventory matches, composition bindings, registries, receipts, tests,
  and validation evidence must all belong to the same minimal review closure.
  After two rounds, a complete repair without a typed Round 3 trigger uses
  deterministic closure rather than another semantic review.
- An implementation-conformance repair prepare binds the Acceptance-owned
  route and replayed repair-completeness projection by current bytes. Their
  family, consumed round, next round, route kind, and typed Round 3 reason must
  match the Bootstrap invocation. A generic repair closure alone is not valid
  implementation-acceptance re-entry evidence.
- Omitting an unchanged predecessor artifact from a bounded repair scope is not
  deletion. A predecessor artifact is deleted only when the live path is
  absent. Its frozen old bytes enter the current Artifact View deleted tree and
  remain part of formal reviewer coverage and valid finding evidence.

Lifecycle state is split into three dimensions:

- Run execution: prepared, preflight-failed, authorized, layers-running, layers-incomplete, awaiting-verification, finalized, abandoned.
- Run relationship: active, superseded, replaced-after-probe-failure.
- Change cycle: review-required, repair-required, next-round-authorized, accepted, manual-pause, closed.

`list-runs` and `inspect-run` are reproducible views. `seal-run` adds an immutable annotation; it never rewrites reviewer, verifier, gate, event, lease, or final evidence. Finalized runs cannot be abandoned. A run with an active event-backed attempt or acquired lease cannot be sealed; the operator must inspect, reattach, or record terminal recovery evidence first. The incomplete-abandoned same-round replacement exception applies only when no active event-backed attempt remains. Superseded runs identify their successor.

## Repair Closure

Round 2 and Round 3 require an implementation-contract instance named `repair-closure.json` and retain the predecessor's lineage family.

- The canonical predecessor finding set is the exact union derived from finalized gate and disposition evidence.
- Confirmed, advisory, and refuted findings remain represented; none may disappear from the exact set.
- Fixes bind source changes, targeted validation, adjacent regression evidence, and current candidate/source/validator hashes.
- Proof type follows the finding family: regression test, negative fixture or mutation, authority counterexample or predicate proof, restricted-context process fixture, or controlled P2 deferral evidence.
- Prepare validates schema, predecessor identity, exact finding set, and proof-family compatibility.
- Authorize-launch revalidates all evidence hashes, Git index, write set, execution read set, dependency closure, and authority graph freshness.
- Missing or stale repair closure prevents any reviewer lease from starting.

## Finalized-Run Validation Envelope

The repository-owned Skill exposes `validate-finalized-run` as the only durable plan-consumption surface for a finalized Bootstrap run. The command reloads the current profile and run authority, revalidates preflight and gate evidence, reproduces candidate/rejection projection from reviewer outputs, and recomputes final result, disposition, metrics, and byte hashes.

The current `bootstrap-finalized-run-validation.v3` envelope binds review/change/lineage-family/round identity, repair delta and entry-decision state, the complete canonical profile hash, route and control-plane revisions, policy and authority identity, final status, finding closure, validator identity, and hashes of every consumed final artifact. The v1 and v2 schemas remain unchanged for stored-envelope compatibility; new producer output uses v3. All versions include direct hashes for `verifier-output.json` and the applicable `p2-dispositions.json`; a metrics-only transitive reference or file-existence check is insufficient. They always carry `authorizes=[]` and explicitly exclude plan acceptance, implementation acceptance, protected handoff, release, commit, and done.

Plans consume this envelope instead of reimplementing a partial Bootstrap profile or lifecycle validator. The consumer calls the repository producer, compares the full saved and recomputed envelope except `generatedAt`, and then applies only its own candidate and predicate rules. A plan-local validator remains solely responsible for its own candidate and acceptance predicates. Envelope validation alone cannot clear a review-cycle manual pause or create a new semantic-review round. A successor policy decision may authorize consideration of a genuinely superseding target, but it cannot reset the lineage family of the existing target. The consuming plan must bind the explicit supersede or incompatible-scope decision and derive a different acceptance target before a new family is valid; a new change ID, saved minimal envelope, arbitrary event JSON, or `independent=true` assertion is insufficient.

Refactor Acceptance may expose a thin `route-acceptance` alias over its existing
`prepare-bootstrap` projection and may create or resume a target-owned
append-only run from the run-input, implementation-contract, and frozen
knowledge-context hashes. This convenience surface must not launch Bootstrap,
duplicate its lifecycle, or accept a historical review baseline as route
authority. Later inspect and resume operations for a new run must replay all
three bindings. Artifact-only legacy run directories are preserved rather than
auto-migrated. High-cost launch acknowledgement remains Bootstrap-owned. An
initial Round 1 full-conformance route is retained for Acceptance import but
must not be supplied to Bootstrap as a repair-route binding; those arguments
apply only after at least one semantic round has been consumed.

New manifests and v3 envelopes bind `candidateBindingHash`. A replayed legacy
manifest may expose a null v3 binding, and frozen v1/v2 envelopes remain
readable; neither form is eligible for exact reuse. Refactor Acceptance exact
reuse requires the implementation-conformance profile, a non-null binding, a
fresh `validate-finalized-run`, `clean` status, current profile/policy/authority
validation, and `bootstrap-import-envelope.v3`. The v3 consumer binds the exact
append-only `prepare-bootstrap` route, requires that route to be the immediate
lineage predecessor of the current finalized lineage head, and rejects
`manual_pause` or deterministic-only routes. Every route-scope file must be in
the Bootstrap artifact set; the current prepared run input, candidate manifest,
knowledge context and accepted knowledge sources receive additional exact
artifact bindings, while v3 directly binds the route file and canonical hashes.
Frozen import-envelope v2
evidence remains readable only under its original finalized v1/v2 contract and
cannot grant exact reuse. Reuse failure is non-authorizing and leaves the
bounded review route in force.

## Historical Baseline And Cost Calibration

- `build-review-baseline` consumes only the validated Git-local registry or
  explicitly supplied formal run directories. Every explicit directory passes
  the same complete historical `load_run` validation before it can become even
  a nonterminal operational row; a hash-self-consistent partial manifest is not
  a formal run. The builder does not recursively infer authority from arbitrary
  `logs/**` content.
- Its append-only history index includes all lifecycle states. Finalized rows
  must pass complete evidence replay and retain their exact finding closure;
  the index aggregates candidate, visible, confirmed, refuted, unverified, and
  P2 disposition yield. Cost cohorts additionally require every required
  reviewer, required verifier, and access probe to have a unique ordered
  lifecycle whose `attempt-started` event binds the exact request hash and
  selected model, a matching process result, and token usage rederived from the
  same Codex JSONL stdout. Probe, reviewer, verifier, and transport-retry costs
  remain distinguishable. Wall time is the union of active attempt intervals,
  so idle gaps are excluded. Zero-token, mixed-model, or legacy unbound-request
  samples do not enter a cohort.
- Baseline output directories must be append-only descendants of `logs/`.
- The history index and calibration candidate are validated before publication
  and published together by one staged-directory rename. A failed build cannot
  reserve the append-only destination with only one of the two documents.
- History indexes and generated calibration candidates always carry
  `authorizes=[]`. They are operational projections, not clean, acceptance,
  handoff, commit, release, or done authority.
- Only a reviewed committed calibration reference bound by schema, path, and
  hash may affect new estimates. Missing cohorts use its declared conservative
  fallback. Generated candidates never promote themselves. Promotion adds a
  new versioned reference and retains every reference already bound by a run.
- Historical exact evidence is not a runtime finding corpus. Synthetic paired
  confirmed/refuted fixtures are shadow tests only and are forbidden from
  runtime reviewer prompts.

## Acceptance Inventory Attestation Companion

`bootstrap-implementation-conformance` declares the optional `acceptance-inventory-attestation@1.0` capability. The declaration binds its producer role (`acceptance_auditor`) and the exact bytes of `bootstrap-acceptance-inventory-attestation.v1.schema.json`. A consumer may request this capability only after its own immutable requirement decision says it is required; matching a profile name or merely finding a schema file is insufficient. Missing, duplicate, or stale capability declarations fail closed. The companion remains Bootstrap-owned and does not create a second semantic reviewer, Artifact View, or launch path.

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
- Targeted Windows access, case-collision, reparse, atomic-write, event-rebuild, pre-publication reviewer drift, multi-result P2 append, repair-closure, and stale-replacement tests.
- Verifier pre-publication semantic and frozen-authority validation, rejected-byte preservation, recovery idempotence, retry reopening, valid-output refusal, and recovery-lineage finalization tests.
- A fresh `bootstrap-skill-route` review after deterministic checks pass.
