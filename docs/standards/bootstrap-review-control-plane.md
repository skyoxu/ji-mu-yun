# Bootstrap Review Control Plane Standard

Status: Accepted
Language: English
Authorities: `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`, `docs/adr/ADR-0045-bootstrap-verifier-semantic-commit-and-recovery.md`, `docs/adr/ADR-0049-bootstrap-controller-owned-coverage-and-attempt-retry.md`, `docs/adr/ADR-0051-bootstrap-lineage-family-and-bounded-repair-reentry.md`, `docs/adr/ADR-0052-bootstrap-review-calibration-and-exact-envelope-reuse.md`, `docs/adr/ADR-0055-focused-repair-verification-and-lightweight-closure.md`, and `docs/adr/ADR-0056-ai-native-single-maintainer-finding-mode.md`

## Purpose

This standard defines the durable protocol for evidence-gated Bootstrap Review. It separates semantic review authority from process execution and keeps review runs recoverable from append-only evidence.

## Semantic Invariants

- A complete review uses three isolated discovery roles: Blind Hunter, Edge Case Hunter, and Acceptance Auditor.
- A focused repair verification uses exactly one independent `focused_repair_verifier`. It is neither a discovery role nor the gate-after-discovery `independent_verifier`.
- New runs freeze `maintenanceMode=ai-native-single-maintainer`. The parent CLI shifts candidates based on multi-maintainer concurrency or external requirement injection from P0 to P1, P1 to non-blocking P2, and P2 to ignored. Runtime product risk retains reported severity.
- Round 1 discovery is automatically eligible. Later complete discovery requires a typed Acceptance trigger plus a hash-bound Bootstrap authorization containing the orchestrator recommendation, confidence, and explicit user confirmation. The recommendation is advisory and may be `recommend` or `do_not_recommend`; explicit user confirmation may authorize either. Prompts and free-form operator claims cannot substitute for that authorization.
- A maintainer may explicitly decline a Round 2 discovery proposal. Refactor Acceptance may publish a hash-bound deterministic `acceptance-passed` closure only when repair completeness replays, the exact lineage consumed one round, no novel P0/P1 exists, and the proposal trigger is solely a repair-derived authority/context or high-risk-boundary change. The closure records residual-risk acceptance and never authorizes commit, release, or archive.
- Focused repair verification is verification-only: it covers the exact predecessor finding set and cannot emit new findings or escalation triggers.
- Discovery roles do not share sessions, candidates, suspected findings, or a minimum finding quota.
- Required artifacts and context are read completely. Sampling is prohibited.
- P0/P1 candidates require an independent verifier that is not a discovery reviewer.
- Discovery model routing is round-bound: every Round 1-2 profile, including Skill/route review, uses Terra at its profile-declared effort, while every valid Round 3 uses Sol/high.
- New discovery candidates carry a structured `verifierRiskClass`. `standard` has no model escalation; `authority_control`, `lifecycle_control`, `protected_path`, and `shared_entrypoint` identify P1 findings that require Sol verification without changing finding severity.
- Independent verification uses Terra/high for a standard P1-only blocker set, Sol/high when any P1 blocker has a high-risk verifier class, and Sol/max when any blocker is P0 or has the `security` dimension. Data-corruption and permission-boundary findings must be classified as P0 or `security`; the highest-risk blocker determines the route for a mixed verifier run.
- Ordinary focused repair verification uses Terra/high. Its access proof and actual layer both derive escalation from the frozen predecessor finding set through the same verifier policy.
- A stable lineage family has a default two-round budget and a three-full-round hard limit. Changing a review ID, `changeId`, or successor directory does not reset the family budget.
- A final result cannot contain an open accepted P0 or P1.
- A clean or P2-only finalized predecessor does not trigger another complete semantic review. New P2-only runs may use one exact-set `bootstrap-p2-closure.v2` bundle with typed targeted evidence; stored v1 disposition chains remain readable.
- Every accepted P2 must be fixed, refuted, or explicitly deferred. High-risk P2 cannot be deferred. A v2 closure binds the exact finding set, current review and candidate, and structured JSON validation results by path/hash, schema version, and successful field/value; it carries `authorizes=[]`. Fixed or refuted findings require passed current validation. Normal-risk deferral requires a named owner, future expiry, bounded non-impact evidence, passed recheck evidence, and a recheck trigger in the same bundle. Stored v1 closures retain their authority-root, command-registry, process-event, and transitive freshness rules.
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
- A controlled command declared read-only compares repository file-content
  hashes before and after execution, including ignored evidence under `logs/`.
  Git porcelain labels alone are not a write detector because already-dirty
  files may be rewritten without changing status. Missing tracked files are
  stable tombstones in that manifest, not stale-path failures.
- Codex Exec sets the current attempt directory as the sandbox workspace root and grants `workspace-write` only there for handshake and candidate evidence. The repository root is not the child workspace. Formal outputs remain parent-owned, and no reviewed or unrelated repository path is child-writable.
- Manual and specialized-agent modes remain external execution boundaries. The repository runner v1 owns only isolated Codex Exec execution.
- The runner atomically writes formal reviewer or verifier sidecars from schema-valid child candidate output. The model cannot directly overwrite formal role output. Completed reviewer and verifier payloads revalidate frozen launch authority immediately before publication; if that pre-publication check fails, the prior formal bytes remain unchanged and the attempt fails. An explicit child failure is a retryable transport failure and does not replace the pending formal reviewer output.
- Codex discovery children return semantic candidates plus a compact Artifact View read receipt, never formal coverage arrays. After validating the same-session handshake and receipt, the parent constructs `requiredArtifacts` and `readArtifacts` from the frozen manifest's ordered artifact list and sets `missingArtifacts=[]`. Manual and specialized-agent formal outputs retain explicit coverage validation.
- The verifier runtime prompt derives each blocker's full inclusive evidence range and complete `contextRead` set from the frozen, hash-bound candidate sidecar. A saved or generated start-line-only summary is not sufficient execution input, and one `evidenceChecked` reference must cover the entire finding range.
- Before publishing verifier output, the parent validates its binding, exact blocker evidence coverage, and complete `contextRead` coverage against the frozen gate. A semantic failure appends failed-attempt evidence and leaves formal output unchanged.
- If interruption occurs after a valid discovery or verifier formal output is atomically published but before its `attempt-completed` event is appended, a retry reservation first proves the original controller process identity is no longer live, validates the completed formal bytes against frozen authority, and reconciles the original attempt with one append-only completion event. A still-live original controller prevents reconciliation, avoiding duplicate completion facts. Recovery never overwrites the formal output or launches another model for that role.
- A completed semantically invalid Codex verifier output may be reopened only through `recover-verifier` under ADR-0045. The command preserves the rejected bytes in a unique hash-bound recovery directory, appends a `verifier-recovery-opened` process event, and does not clear the formal file. Valid, finalized, sealed, active-attempt, or non-Codex verifier state cannot use this recovery lane.

## Artifact View And Access Proof

- Codex Exec reads a frozen `artifact-view.v1` under the run directory and does not mix live originals with snapshots in one run.
- The manifest binds original repository path, snapshot path, both hashes, size, encoding, line count, file type, binary/text classification, reparse metadata, Windows case-normalized identity, context classes, source scope, and creation identity.
- Snapshot paths preserve repository-relative layout and reject case collisions, path escape, junction escape, and reparse escape.
- Findings cite original paths. Snapshot evidence is projected back to original inclusive line ranges.
- Codex Exec reviewer and verifier prompts identify the absolute run directory and Artifact View manifest. Sandboxed children resolve relative `snapshotPath` values against that run directory, read only snapshot content, and cite `originalPath`; they do not resolve snapshots against the attempt workspace or fall back to inaccessible or drifting live originals.
- When a nested Codex session must load the repository Bootstrap Skill or its delegated authority, the parent binds the complete required authority order through Artifact View `originalPath -> snapshotPath` mappings. The child reads those frozen snapshots instead of live `.agents` or repository paths. A missing or stale mandatory mapping fails before semantic reviewer launch. This execution boundary implements ADR-0041 ownership without granting the child live control-plane access.
- Binary artifacts cannot claim text line evidence.
- Discovery launch requires identity-equivalent access proof for every distinct role-specific model/reasoning route. `access-proof.json` owns the first route and deterministic role-qualified sidecars own additional routes; roles with identical routes share one proof. The launch authorization hash-binds the complete ordered proof set.
- A Codex verifier requires a separate `verifier-access-proof.json`, created only after the gate has frozen at least one P0/P1 blocker. It binds the gate hash and the risk-derived Terra/high, Sol/high, or Sol/max route; a discovery proof cannot authorize the verifier.
- Each actual reviewer and verifier child must also complete a same-process, hash-bound access handshake before semantic work begins.
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
- For a new implementation-acceptance lineage, a complete Round 1 repair with
  no escalation trigger routes to one focused repair verifier. The verifier
  covers the exact predecessor finding set, finding-to-repair mappings, repair
  diff, direct consumers, targeted tests, and controlled receipts. It may
  report a still-blocking predecessor repair, but cannot create findings or
  escalation triggers and grants no lifecycle authority.
- Novel P0/P1, authority/context graph change, or high-risk boundary change
  routes to a complete three-layer review proposal. Unknown trigger state
  blocks routing. After Round 1, Bootstrap rejects prepare unless the proposal
  is bound to the orchestrator recommendation/confidence and explicit user
  confirmation through `authorize-finding-mode-reentry`.
- Round 3 requires one schema-valid entry reason: `novel_p0_p1`,
  `authority_context_graph_changed`, or `high_risk_boundary_changed`.
- Round 3 discovery always resolves to Sol/high for all three roles, regardless
  of the profile's Round 1-2 defaults.
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
  direct consumers, keeps producer and consumer path sets disjoint, and binds
  its receipt as a validation reference. Repair
  paths, inventory matches, composition bindings, registries, receipts, tests,
  and validation evidence must all belong to the same minimal review closure.
  A successful focused repair verification closes ordinary Round 1 repair
  without consuming another complete discovery round. After two complete
  rounds, a complete repair without a typed Round 3 trigger uses deterministic
  closure rather than another semantic review.
- An implementation-conformance repair prepare binds the Acceptance-owned
  route and replayed repair-completeness projection by current bytes. Their
  family, consumed round, next round, route kind, and typed Round 3 reason must
  match the Bootstrap invocation. A generic repair closure alone is not valid
  implementation-acceptance re-entry evidence.
- A new focused repair route embeds and hash-binds the original deterministic
  repair-completeness request. Bootstrap replays that producer request during
  prepare and every live run load. Acceptance later imports the result only by
  canonical replay of the finalized Bootstrap run directory.
- After three consumed rounds, Bootstrap remains in `manual_pause` and never
  creates Round 4. Refactor Acceptance may separately close a repaired target
  only through the ADR-0054 two-stage deterministic closure contract. That
  contract must canonically replay the exact blocked finalized run, reject any
  remaining unverified verifier decision, bind the confirmed finding set,
  replay current repair completeness, require explicit maintainer
  acknowledgement, and preserve all Bootstrap evidence as blocked history.
  Bootstrap does not emit or reinterpret `acceptance-passed`. The independently
  reviewed closure protocol binds the repository Bootstrap producer, Bootstrap
  Skill, public Acceptance CLI, review-cycle policy, Acceptance lineage/replay
  consumers, its final output schema, and the other protocol authorities by
  current bytes; finalization rejects schema revision drift. Request paths are
  normalized to repository-relative identity before replay, and finding-repair
  ordering is canonical rather than caller-authoritative.
- A closure-protocol lineage already blocked at Round 3 may perform one
  same-round hard-limit focused recovery. The CLI binds explicit user
  confirmation, recommendation/confidence, the exact blocked v3 envelope and
  finding set, and current deterministic repair evidence. The run uses only
  `focused_repair_verifier`, remains `verification_only`, is excluded from
  semantic-round accounting, and rejects discovery, new blockers, escalation,
  stale repair bytes, or a non-blocked/different predecessor. Its composite
  authority may authorize only `manual-pause-protocol-review`; it cannot
  authorize Acceptance, commit, release, discovery, or Round 4.
- A hard-limit composite replays its focused envelope and authority from current
  bytes, then validates the hash-bound blocked predecessor envelope as frozen
  history. It does not revalidate the predecessor's historical repair closure
  against the newer protocol revision covered by the focused verifier.
- Omitting an unchanged predecessor artifact from a bounded repair scope is not
  deletion. A predecessor artifact is deleted only when the live path is
  absent. Its frozen old bytes enter the current Artifact View deleted tree and
  remain part of formal reviewer coverage and valid finding evidence.
- Round 1 implementation conformance may freeze an Acceptance candidate
  tombstone only from the prepared input's replayed candidate identity and
  custody-bound immutable Git baseline. The live path must remain absent and
  the Git blob hash must equal the baseline tombstone. Caller-supplied snapshot
  or source paths are forbidden. The binding participates in context coverage,
  `candidateBindingHash`, freshness, finalize, and exact import.

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
`manual_pause` or deterministic-only routes. Every route-scope path must be in
the Bootstrap live artifact set or its verified deleted candidate set; the current prepared run input, candidate manifest,
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
- Historical replay resolves the current canonical profile only when its
  `policyRevision` still matches. Otherwise it reconstructs the profile from
  frozen manifest policy fields plus registered extensions and requires the
  reconstructed canonical hash to equal the frozen revision. Registry entries
  marked `baseline-only` cannot authorize a successor. A
  `baseline-and-successor` entry must retain its exact authority-root binding.
  Neither form may prepare a new run or rewrite historical evidence.
- Its append-only history index includes all lifecycle states. Finalized rows
  must pass complete evidence replay and retain their exact finding closure;
  the index aggregates candidate, visible, confirmed, refuted, unverified, and
  P2 disposition yield. Cost cohorts additionally require every required
  reviewer, required verifier, and every required role-specific access probe to have a unique ordered
  lifecycle whose `attempt-started` event binds the exact request hash and
  selected model, a matching process result, and token usage rederived from the
  same Codex JSONL stdout. Probe, reviewer, verifier, and transport-retry costs
  remain distinguishable. Wall time is the union of active attempt intervals,
  so idle gaps are excluded. A single-model route uses that model as its cohort
  identity. A legitimate mixed route uses a canonical hash of the complete
  configured role-to-model route and is never attributed to either single-model
  cohort. Zero-token, substituted-route, incomplete-route, and legacy
  unbound-request samples do not enter a cohort.
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
