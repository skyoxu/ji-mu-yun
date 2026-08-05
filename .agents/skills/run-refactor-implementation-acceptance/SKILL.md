---
name: run-refactor-implementation-acceptance
description: Build, resume, and route deterministic implementation-acceptance evidence for one explicit Phase-service or repository-toolchain refactor plan, including compact-VDD prerequisite projection, bounded Bootstrap review handoff, and exact finalized-run reuse.
---

# Refactor Implementation Acceptance

This Skill builds deterministic implementation-acceptance evidence for exactly
one explicit target plan. It does not implement target code, approve a review,
authorize a protected handoff, commit, release, or deploy. It may route to the
Bootstrap Skill, but Bootstrap retains model launch, high-cost acknowledgement,
and review-lifecycle ownership.

## Default Orchestration

Own the complete coordination loop when invoked for a new or existing target.
Do not stop after reporting that another Skill or review is required. Continue
until a typed user-acknowledgement boundary, protected-path boundary,
`manual_pause`, or terminal Acceptance result is reached.

Resolve entry inputs in this order:

1. Require one repository-relative `execution-plans/<target>` directory.
2. Prefer `candidate_mode=commit`. If the caller omits the candidate, use the
   current `HEAD` only when the relevant worktree is clean and report the full
   resolved commit. Otherwise require a frozen dirty-worktree or
   proposed-commit-set snapshot.
3. Read an unambiguous frozen Git baseline from the target plan. If none exists,
   require an explicit baseline revision. Never infer the baseline as
   `candidate^`; one target may span multiple commits.
4. Derive the run directory after creating the typed run request and its
   canonical input hash, but before publishing the `prepare-run` output. Do not
   ask the caller to name it unless they need an explicit recovery identity.

Require either the plan's full implementation contract or one current
`compact-vdd-acceptance-prerequisite-bundle.v1`, plus complete baseline and
candidate content manifests, typed run request, action DAG, and command
registry before starting the persisted run. Resolve their fields from the
target plan and an explicit VDD or Quick Dev handoff. For an
`implementation-complete` compact VDD target, run
`scripts/compact_vdd_projection.py` only with an explicit sorted changed-path
list, consumer refs, commands, actions, policy, and Acceptance-owned knowledge
context. The projector must not enumerate the dirty worktree to infer scope.
The orchestrator may otherwise materialize prerequisites
deterministically from those bindings and immutable Git bytes, but must not
guess scope, revisions, changed paths, commands, or acceptance actions. If a
required source is missing or ambiguous, report `prerequisite_blocked` with the
missing artifacts and stop before `start-or-resume`.

Create the knowledge context only through the canonical Locator and bind the
adapter to exactly one explicit `--target-plan`. If it returns `catalog_stale`,
the adapter emits a hash-bound `knowledge-maintenance-required` route with
`automatic_publication_allowed=false`, `authorizes=[]`, and stops. This Skill
must not invoke publication automatically; a maintainer must explicitly enter
`maintain-knowledge-base` and create a publication request. Other blocked
knowledge failures route to `knowledge-context-repair-required`. Never
hand-author candidate selections, accept an old context, bypass Locator
freshness, or write knowledge artifacts outside the explicit target plan. The
adapter persists the route append-only under
`<target-plan>/knowledge-context-routes/<hash>.json`; maintenance must bind that
exact route before catalog-stale publication.

Create or resume the target-owned append-only run with the canonical run-input
request hash that `prepare-run` will publish as `inputHash`, plus the
implementation-contract file hash and frozen knowledge-context file hash:

```text
py -3 .agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py start-or-resume \
  --repository-root <repo> --target-plan <execution-plans/target> \
  --run-input-hash <sha256:...> --contract-hash <sha256:...> \
  --knowledge-context-hash <sha256:...>
```

`run-input-hash` is the canonical JSON hash that `prepare-run` computes as
`inputHash`. The other two values are SHA-256 hashes of the exact contract
and frozen context file bytes; use the context `sha256` emitted by
`freeze_knowledge_context`, not its semantic `contextHash`.

Omitting `--run-id` derives `acceptance-<16-hex-binding-id>` from all three
hashes. The same target and bindings resume the same persisted run without
rewriting it. Any input, contract, or knowledge-context drift fails closed;
prepare a new candidate/run or use the existing explicit stale-successor
recovery instead of overwriting history.

Treat a historical Acceptance directory without `run-state.json` as an
artifact-only legacy run. Preserve it for replay, never auto-migrate it into
the persisted lifecycle, and create a new binding-derived run directory.

Execute the orchestration in this order:

1. Inspect the target for an existing request and matching persisted run before
   creating new evidence.
2. Resolve or deterministically materialize the complete manifests, action DAG,
   command registry, Acceptance-owned knowledge context, and typed run request;
   then compute the three entry hashes.
3. Run `start-or-resume`, write the `prepare-run` output inside the returned run
   directory, and inspect/resume its existing action evidence with all three
   hashes. A new persisted run must reject inspect or resume when the frozen
   knowledge-context hash is omitted.
4. Run the deterministic inventory, policy, matrix, checklist, scan, coverage,
   and evidence actions required by the target contract.
5. Publish the immutable Bootstrap requirement decision and obtain a fresh
   repository-owned `inspect-lineage` projection, including zero rounds.
6. Produce the bounded route with `route-acceptance`, the thin public alias for
   `prepare-bootstrap`:

```text
py -3 .agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py route-acceptance \
  --request <bootstrap-route-request.json> --out <bootstrap-route.v1.json>
```

7. Before starting a semantic run, attempt `import-bootstrap` only with an
   explicitly selected finalized run and the exact prepared input and route.
8. Follow the route's typed `nextAction`. Invoke `run-phase-bootstrap-review`
   for `full_implementation_conformance` or `focused_repair_verification`, but stop
   for its explicit high-cost acknowledgement before any model process starts.
    If the route publishes `findingModeReentry=user_confirmation_required`, first
    show the typed trigger, expected benefit/cost, your recommendation, and a
    confidence in `[0,1]`; obtain explicit user confirmation and create the
    Bootstrap CLI re-entry authorization before prepare. The recommendation is
    advisory: explicit confirmation may proceed after either `recommend` or
    `do_not_recommend`.
    When the user explicitly declines that later discovery proposal, do not
    launch Bootstrap. If repair completeness passed, no novel P0/P1 exists,
    the consumed-round count is exactly one, and the only typed trigger is a
    repair-caused authority/context or high-risk-boundary change, run
    `decline-review-reentry`. The append-only result records maintainer risk
    acceptance and may publish `acceptance-passed`; it never authorizes commit,
    release, or archive. Any novel P0/P1, missing replay, stale binding, or
    different round fails closed.
9. Import the finalized Bootstrap result, then continue finding mapping,
   impact projection, evaluation, finalization, and package validation.

Treat `review-history-index.v1.json` and cost-calibration candidates as
non-authorizing observations only. They may explain expected cost and semantic
yield but must never enter a `route-acceptance` request, change `routeKind`,
create `clean`, or satisfy exact reuse. A promoted Bootstrap calibration is
consumed by the Bootstrap producer under its own binding.

For P2-only output, dispose findings in the current semantic run and use
targeted deterministic closure. New runs prefer the exact-set P2 v2 bundle;
stored v1 chains remain read-only compatible. For P0/P1 repair, require the
Quick Dev handoff and `audit-repair-completeness` before routing the next
bounded action. A complete Round 1 repair without an escalation trigger routes
to exactly one independent focused repair verifier. Never open a complete
review without its typed trigger and never create Round 4.

Treat the Acceptance route's maintenance and finding fields as first-class
control data: `maintenanceMode=ai-native-single-maintainer`; multi-maintainer
concurrency and external requirement-injection findings shift P0 to P1, P1 to
non-blocking P2, and P2 to ignored. Round 1 discovery is automatic. Later
discovery is only a proposal until the Bootstrap CLI validates the typed route,
recommendation, confidence, and explicit user confirmation.

When the current lineage has consumed three rounds and routes to
`manual_pause`, do not treat the pause as acceptance or create a successor to
reset the budget. A repaired target may use the ADR-0054 two-stage deterministic
closure lane:

1. Repair every confirmed Round 3 finding and produce a current Quick Dev
   handoff, controlled receipts, targeted tests, validation references, and a
   reproducible repair-completeness projection with
   `semanticRoundsConsumed=3` and the Round 3 run as predecessor.
2. Run `prepare-manual-pause-closure` with the current manual-pause route and
   the hash-bound `prepare-bootstrap` request that produced it, the
   blocked finalized v3 envelope from the current implementation-conformance
   or adopted upstream-plan lineage, exact finding-to-repair mappings, and the
   current protocol authorities and a finalized clean/advisory protocol-review
   envelope. The review must use `bootstrap-skill-route`, and its frozen
   artifact set must byte-bind the current protocol implementation, schemas,
   Bootstrap Skill and producer, public Acceptance CLI, review-cycle policy,
   Skill, ADR, and standard. It must canonically replay the complete
   finalized run and reject every remaining `unverified` verifier decision;
   selected envelope fields and maintainer judgement cannot replace either
   check. If that protocol review itself exhausted a blocked Round 3, the
   consumer may instead accept the exact composite authority emitted by one
   CLI-authorized `bootstrap-focused-repair-verification` at the same Round 3.
   That lane binds the blocked envelope, exact finding set, current
   deterministic repair closure, explicit user confirmation, and a passed
   verification-only focused envelope; it cannot create Round 4, findings,
   escalation, or `acceptance-passed`. The challenge carries `authorizes=[]`.
   This composite replays the focused envelope and authority from current bytes,
   but validates the authority-bound blocked predecessor as a frozen eligible
   envelope; it must not revalidate that predecessor's old repair closure
   against the newer protocol bytes that the focused verifier already covered.
   Replay the Bootstrap producer from the request repository's own Skill path;
   a caller-adjacent producer or a missing repository-owned producer fails closed.
3. Stop for an explicit maintainer acknowledgement bound to the challenge hash
   and exact confirmed finding IDs.
4. Run `finalize-manual-pause-closure`. It hashes the same challenge byte
   snapshot that it validates and recomputes every binding;
   only its final closure result may publish `acceptance-passed`.

Each finding mapping must select a composition receipt whose bound producer or
consumer paths cover that finding's changed paths and whose registered command
names its mapped targeted tests. Repair completeness reruns every registered
composition command through the controlled runner and rejects saved stdout or
stable execution fields that do not match the current replay. Producer and
consumer path sets are disjoint, and a read-only controlled command must leave
the repository byte manifest unchanged even when a touched file was already
dirty before execution. Tracked deletions use stable tombstones. Closure
request paths are repository-relative after resolved-root normalization, and
finding-repair mappings are canonicalized by finding ID.

This lane never launches a model, reopens the target Bootstrap lineage, creates Round 4, changes a
verifier decision, or authorizes commit, release, or archive. Independently
validate and review a new closure-protocol revision before using that revision
to close a real target; the protocol cannot approve itself.

## Modes

- `evidence_only` is the default. It reads current manifests and evidence and may only produce non-authorizing candidate conclusions.
- `controlled_validation` is available only after the caller supplies typed commands and isolated write roots. It cannot write target production code, live Phase state, workspaces, or historical evidence.

## Model Route Decision

Keep every ordinary Acceptance next action deterministic and pass it through
`scripts/model_routing.py` as the no-launch route. Request Sol/high only when
the current failure matches one policy-owned complex-recovery trigger:
Bootstrap control-plane unavailable, candidate-binding recovery failed, or
lineage evidence inconsistent. Reject free-form recovery reasons. Do not use a
model child for routine evidence collection, routing, replay, or finalization.

The route decision is hash-bound and non-authorizing. The shared workflow
launcher alone may start the child; this Skill does not call it from its
deterministic CLI. In `observe_only`, no child starts and the current caller
session model is unchanged. Bootstrap profile, round, verifier, effort, access
proof, and launch authority remain external to this router.

The canonical policy owns Refactor Acceptance's independent consumer
enablement. Disabling this consumer does not disable VDD or Quick Dev. The
shared launcher revalidates the canonical policy before execution and rejects
caller-supplied policy substitutions; any capability-gated route must replay
policy-bound producer and representative execution receipts.

## Bootstrap Routing

When the immutable Bootstrap requirement decision is `required`, deterministic
validation must publish an append-only route through `prepare-bootstrap`. The
route freezes the consumer-side decision, capability binding, Bootstrap-owned
launch sidecar, stable target-derived `lineageFamilyId`, consumed-round view,
and optional repair-completeness result. It selects exactly one route kind:
`deterministic_only`, `focused_repair_verification`,
`full_implementation_conformance`, or `manual_pause`.

For every required Bootstrap route, pass `repository_root` and obtain a fresh
hash-bound `inspect-lineage` projection, including the zero-round initial state. Omitting
the projection fails closed; absence is never interpreted as a fresh budget.
`prepare-bootstrap` replays that projection itself. A repair route must also
carry its original repair-completeness request so the result can be reproduced
from current repository bytes.

When a repair route has already consumed at least one semantic round and
selects `focused_repair_verification` or `full_implementation_conformance`, pass the
saved route to Bootstrap as `--acceptance-repair-route` and its replayed
completeness projection as `--acceptance-repair-completeness`. Bootstrap
revalidates their byte, family, round, and typed-entry bindings. For the initial
Round 1 `full_implementation_conformance` route, do not pass either repair
argument; retain that route only for the later Acceptance import binding. Pass
the current append-only prepared Acceptance input to Bootstrap as
`--acceptance-run-input`. Candidate tombstones may then remain in `--scope` and
context classes: Bootstrap replays custody and identity, requires current
absence, and freezes old bytes only from the bound immutable Git baseline.

The deterministic CLI never launches an LLM process. The Skill orchestrator
must invoke `run-phase-bootstrap-review` when the selected route requires it,
then complete Bootstrap preflight, identity-equivalent access probe, and
explicit high-cost launch authorization before any reviewer layer starts. It
must not merely report that review is required and stop. A deterministic pass
without a required finalized Bootstrap envelope remains a non-authorizing
candidate, not an implementation-acceptance pass.

After a focused repair run finalizes, call `import-focused-repair` with the
repository-relative `focusedRun` directory plus the exact Acceptance route and
repair-completeness path/hash references. The command canonically replays the
Bootstrap producer; never accept a caller-supplied focused envelope.

Before starting a new semantic run, the caller may invoke `import-bootstrap`
with one explicit finalized run, the append-only `prepare-run` output, and the
exact append-only `prepare-bootstrap` route that launched that run. The command
revalidates the current candidate manifest, changed paths, custody, frozen
knowledge context and accepted knowledge sources, reruns Bootstrap
`validate-finalized-run`, and requires every file in the route's complete
seven-class `reviewScope` to be present in the run's frozen artifact binding.
The prepared Acceptance input, candidate manifest, and knowledge artifacts
must also match their frozen artifact entries. The v3 import envelope directly
binds the route's file hash and canonical document hash; Round 1 does not
pretend the route was a repair-route artifact. Every candidate changed path
must be in the route's `changed-production-code` class.

Exact reuse is emitted only as `bootstrap-import-envelope.v3`. It requires a
non-null exact `candidateBindingHash`, current profile/policy/authority, the
`bootstrap-implementation-conformance` profile, a complete finalized v3
validation envelope, `clean` final status, and a
`full_implementation_conformance` or `focused_repair_review` route. The route's
lineage state must be the immediate predecessor of the selected finalized run,
and that run must be the current reconstructed lineage head. Historical import
envelope v2 evidence remains readable under its original v1/v2 finalized-run
contract but never grants exact reuse. The import binds the canonical
repository-relative Bootstrap run directory and requires the Acceptance
Auditor attestation to match the finalized review/input identity. Any drift
rejects the import and leaves the existing bounded review route unchanged. This is
deterministic validation reuse, not LLM-output caching; historical cost or
finding baselines cannot authorize it.

For a required review, `prepare-bootstrap` must build a
`minimal-complete-closure` from explicit repository-relative files in all
seven implementation-conformance classes: implementation plan, changed
production code, directly affected consumers, tests and acceptance, current
runtime or acceptance evidence, repository rules, and referenced standards.
Do not pass a whole Skill, source, test, document, log, or execution-plan
directory merely because it contains one relevant file. The generated
`reviewScope` is the exact input for Bootstrap `--scope` and `--context-class`
arguments; Bootstrap still owns snapshotting and launch authorization.

A malformed child JSON response, invalid Artifact View receipt, or failed
Codex process is a transport attempt failure. Retry the same role in the same
Bootstrap run after inspecting the attempt evidence; it does not consume a
semantic round or require a successor lineage. P2-only results are disposed in
the current run and use deterministic targeted closure. They do not trigger a
new complete semantic review. The original target plan remains the acceptance
target unless an explicit supersede or incompatible-scope decision exists.

The lineage family is derived from the original `execution-plans/<target>`
root. In-place repairs and successor history for that target retain it; a new
`changeId` does not reset the review budget. Round 1 uses full implementation
conformance. After the first P0/P1 repair, the default route is a single
focused repair verification only when no new P0/P1, authority/context graph
change, or high-risk boundary change exists. Any such trigger selects complete
three-layer review as a non-authorizing proposal requiring recommendation,
confidence, and explicit user confirmation. A clean focused result closes the
ordinary repair; a focused blocker routes back to repair, and the focused
verifier cannot report a new trigger. After two consumed complete rounds, a complete repair with no
typed trigger routes to deterministic closure. Three consumed rounds route to
`manual_pause`.

Before any repair re-entry, require Quick Dev's standard handoff and run
`audit-repair-completeness`. The audit discovers sibling callsites from the
declared roots, requires each match to be changed or explicitly excluded, and
validates successful controlled producer/consumer composition receipts whose
input bindings cover every producer and consumer. It derives the exact changed
set from a hash-bound complete candidate manifest and binds present changed
files by content hash, deleted files by their baseline hash, direct consumers,
targeted tests, and validation references. Each
composition check must cover a changed path, use declared direct consumers,
and expose its receipt as a validation reference. Before routing, require all
changed paths, inventory matches, composition bindings, command registries,
receipts, consumers, tests, and validation references to be members of the
same hash-bound `minimal-complete-closure`; consumers and tests must also be in
their corresponding context classes. The audit and route carry `authorizes=[]`;
the plan-local final predicate still decides implementation acceptance.

## Current Core

Before `prepare-run`, create one Refactor Acceptance-owned knowledge context
through the canonical Locator:

```text
py -3 .agents/skills/run-refactor-implementation-acceptance/scripts/prepare_knowledge_context.py \
  --repository-root <repo> --request-id <id> --query <query> \
  --target-plan <execution-plans/target> \
  --required-module acceptance-scope \
  --accept <candidate-path>=acceptance-scope \
  --output <target-plan>/knowledge-context.refactor-acceptance.v1.json
```

The adapter uses `consumer=refactor-acceptance`, records one accepted or
rejected decision for every Locator candidate after reread/hash verification,
and fails closed on publication, snapshot, policy, projection, request/result,
or read-set drift. It never uses unpublished staging inputs.

The formal CLI requires that frozen file at the `acceptance-run-input` freeze
point:

```text
py -3 .agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py prepare-run \
  --input <request.json> --knowledge-context <target-root-relative-path> \
  --out <run-input.json>
```

Historical function-level inputs without a knowledge context remain readable;
new CLI preparations cannot omit it. Later phases consume the frozen summary
and never issue another Locator query. The shared context validator must
byte-match current main, and the complete Locator read-set is revalidated
against both its source commit and current worktree before the summary freezes.

`scripts/acceptance_cli.py prepare-run` validates a hash-bound run input with replayable baseline and candidate content manifests, then writes a new non-authorizing run-input artifact. Commit candidates are checked against raw bytes from resolved immutable Git commits, and the resolved baseline/candidate OIDs are persisted in `candidateCustody`. Dirty-worktree and proposed-commit-set candidates must declare `candidate_frozen_snapshot_path` as `.acceptance-snapshots/<run_id>` beneath the target root; symlinks and live workspace substitutes are rejected, and the snapshot manifest receipt is persisted.

Select `policies/phase-service-code-review.v1.json` only for Phase candidates;
it may retain an explicit unreviewed external partition for mixed candidates.
Select `policies/toolchain-code-review.v1.json` for repository workflow
control-plane candidates. Its closed path rules must cover every changed path,
and its binding records shared Phase entrypoints as cross-domain dependencies.
An uncovered toolchain path fails closed. Pure Godot inputs remain unsupported.

`analyze-diff-coverage` consumes a frozen `phase-changed-line-set.v1` and a current Cobertura report. It uses only added or modified executable `PhaseA.Platform/**/*.cs` lines for the denominator, records every exclusion reason, and returns `incomplete` when a source mapping is missing. It never substitutes repository-wide coverage.

`audit-task-checklist` reads only explicitly declared authority checklist files. A checked item is `verified` only when its stable item identity has current matrix, implementation, test, and evidence references; source hash drift, checkbox-only closure, and request-controlled optionality fail the result. `run-command` resolves an exact descriptor from a hash-bound command registry; it never executes a caller-supplied descriptor. `run-phase-scan` is available only in `controlled_validation`, executes that registered shell-free command from a hash-verified frozen candidate snapshot, and requires its declared Phase read scope to exactly cover the candidate's Phase changed paths.

`audit-repair-completeness` consumes the append-only Quick Dev handoff without
translation. It revalidates the baseline/candidate manifests and rejects an
omitted or invented changed path. Every inventory is discovered from current repository bytes and
every composition check must reference a successful controlled-command
receipt. Feed its result and the Bootstrap `inspect-lineage` projection into
`prepare-bootstrap`; do not hand-author consumed rounds or route kinds.

The matrix, conditional Bootstrap import, action recovery, and final authorization stages are implemented only when their own plan slices and predicates are complete. A passing unit test or a Bootstrap `clean` result is not Program DoD.
