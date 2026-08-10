---
name: run-phase-bootstrap-review
description: Prepare, execute, gate, resume, inspect, seal, or finalize Ji Mu Yun evidence-gated Bootstrap Reviews for plan authority, implementation conformance, Skills/routes, and focused changes. Use for Bootstrap Review, Whole-directory review, Blind Hunter / Edge Case Hunter / Acceptance Auditor orchestration, independent blocker verification, repair-round closure, or recovery of an existing review run.
---

# Run Phase Bootstrap Review

Use the repository-owned control plane. This Skill owns the executable protocol and generic schemas; it does not own the reviewed plan's business acceptance, commit, handoff, release, or done state.

## Authority Order

Read these before operating the workflow:

1. `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`.
2. `docs/adr/ADR-0051-bootstrap-lineage-family-and-bounded-repair-reentry.md`.
3. `docs/adr/ADR-0056-ai-native-single-maintainer-finding-mode.md`.
4. `docs/standards/bootstrap-review-control-plane.md`.
5. `references/review-profiles.v1.json`.
6. `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md` for migration examples.

The repository entrypoint is:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
```

The 2026-07-12 CLI is a revision-bound compatibility adapter only. Do not add durable behavior there.

## Hard Boundaries

- Keep Blind Hunter, Edge Case Hunter, and Acceptance Auditor isolated. Do not share candidates or suspected findings before gate.
- Require complete artifact and context coverage. Sampling is prohibited and zero findings are valid.
- Use an independent verifier for every accepted P0/P1.
- Use exactly one `focused_repair_verifier` for a new non-escalated Round 1 repair. It is distinct from all discovery roles and from `independent_verifier`.
- Treat `ai-native-single-maintainer` as first-class review context. Candidates based on multi-maintainer concurrency or external requirement injection are parent-adjusted P0 to P1, P1 to non-blocking P2, and P2 to ignored; runtime product risks are unchanged.
- Allow finding discovery automatically only for Round 1. A later complete discovery requires a typed Acceptance trigger, the orchestrator's explicit recommendation and confidence, explicit user confirmation, and a CLI-produced hash-bound re-entry authorization. Prompt text alone never authorizes finding mode.
- Treat the recommendation as advisory, not a veto. After the user sees the trigger, expected benefit/cost, recommendation, and confidence, explicit confirmation may authorize re-entry even when the recommendation is `do_not_recommend`.
- A `focused_repair_verifier` verifies only predecessor findings. It must return no new blockers and cannot reopen discovery.
- Use one stable `lineageFamilyId` for the same acceptance target. Its default budget is two semantic rounds and its hard limit is three; changing `reviewId`, `changeId`, or successor directory never resets it.
- Do not mutate reviewed files while a review run is active.
- Never edit reviewer, verifier, gate, process-event, or final evidence to make a run pass.
- Do not treat Bootstrap output as protected handoff, production gateway, commit, release, or plan-local validator authority.
- The runner has no hidden provider dispatch. A fallback model is a new explicit operator command after the prior attempt is recorded.
- Subprocesses use argument arrays, `shell=False`, the environment allowlist, and typed placeholders from the control-plane revision.
- Codex Exec uses the current attempt directory as its isolated `workspace-write` root for handshake and candidate evidence. The repository root and formal output paths must remain outside the child workspace.
- Process events are execution facts. `process-leases.json` is a compatibility view derived from those facts.
- Reviewer launch uses a lock-serialized `attempt-reserved` event before `Popen`; overlapping formal write sets and already-completed roles fail before a child starts, while non-overlapping roles remain concurrent.
- The runner refreshes that view immediately after `attempt-started`. A dead event-backed PID must append `attempt-stale` before rebuilding the view; changing only the lease sidecar is insufficient.
- The process-event lock is owner-bound by PID, process creation identity, token, timestamp, and acquired/committed phase. Recovery removes a dead/reused, incomplete stale, or committed owner lock; cleanup retries transient Windows sharing violations and may unlink only its own token.

## Select One Profile

- Plan or Whole-directory authority: `bootstrap-upstream-plan`.
- Implemented code and feature closure: `bootstrap-implementation-conformance`.
- Skill or route: `bootstrap-skill-route`.
- Focused bugfix or bounded change: `bootstrap-focused-change`.

Bind every required context class to real in-scope artifacts. For implementation conformance, bind every plan-mandated deterministic check with `--required-check`.

## Inspect Before Starting

When a run may already exist, use read-only recovery first:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py list-runs --repository-root <repo>
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py inspect-lineage --repository-root <repo> --lineage-family-id <family>
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py inspect-run --run-dir <run>
```

For cost/yield governance, build a non-authorizing baseline from the validated
registry or an explicit set of formal run directories:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py build-review-baseline \
  --repository-root <repo> --out-dir logs/review-governance/baselines/<id> \
  [--run-dir <formal-run> ...]
```

The history index includes every located lifecycle state. Only finalized runs
that pass full evidence replay enter semantic statistics, and only those with
complete structured attempt token and process-event evidence enter cost
cohorts. Token counts come from the same Codex JSONL execution, every counted
attempt directory must match a started and terminal process-event lifecycle,
and each selected model must match the role-specific route frozen by the run.
A single-model route keeps the model name as its cohort identity. A legitimate
mixed route, such as Terra discovery plus Sol verification, uses a canonical
hash of the complete configured role route and is never attributed to either
single-model cohort. The history index and calibration candidate publish as
one staged directory. A finalized run that fails replay fails the complete
build. Generated
calibration is a candidate and never updates the promoted reference
automatically. Baselines and calibration always carry `authorizes=[]`.

Pass the hash-bound `inspect-lineage` result to the consumer even when it
reports zero rounds; omission must never mean a fresh family. Follow the
reported `nextAction`. Do not infer current state from an old assistant summary.
The local Git registry is only a performance index: every registered manifest
and adoption record is re-hashed before use, and damaged registered history
fails closed. The index binds its source Git revision. A changed HEAD triggers
one repository reconciliation scan; controller-created runs and adoptions at
the same HEAD are registered explicitly, so ordinary inspection does not scan
the repository repeatedly.
When canonical profile content changes, add the outgoing revision and its
authority-root binding to `references/historical-policy-revisions.v1.json` in
the same change. The archive exists only to replay historical typed decisions;
it cannot prepare a new run. Historical replay reconstructs the content-addressed
profile from the frozen manifest plus registered extensions and rejects any
hash mismatch. Use `baseline-only` for revisions that lack successor authority;
only `baseline-and-successor` entries with a registered authority root may
authorize successor-policy resolution.

When pre-family history must count toward a target-derived family, use
`adopt-lineage` once with explicit historical run directories and a hash-bound
Accepted policy authority. Never rewrite old `review-input.json` files or infer
adoption from directory proximity. One historical run cannot be adopted by
multiple families.

## Prepare

`prepare --dry-run` is a non-authorizing binding preview. Its
`closureBindings` object mirrors the individual candidate, source, validator,
Git, write-set, execution-read-set, and dependency-closure hashes in the
diagnostic output. The preview must report `authorizes: []` and must not create
a run directory; mismatched scope or context inputs remain field-level
diagnostics and fail closed before any model launch. Context diagnostics also
expose `acceptedScopesByClass` so each required class can be traced to the
prepared artifacts that satisfy it.

Create a new run with stable `reviewId`, `changeId`, `lineageFamilyId`, round, profile, scopes, context classes, execution mode, and exclusivity attestation. Derive the family from the original acceptance target and retain it for every in-place repair or successor that still evaluates that target. New runs require `--lineage-family-id`.

Declare:

- `--write-set` for paths the reviewed change may write.
- `--execution-read-set` for validator/runtime inputs already present in scope.
- `--dependency` for the execution dependency closure already present in scope.

Use the smallest complete consumer closure. `bootstrap-upstream-plan` may bind
the whole plan directory because that directory is the review object. For
implementation, Skill-route, and focused-change profiles, prefer explicit
changed files, direct contracts and consumers, targeted tests, repository
rules, referenced standards, and current acceptance evidence. If a directory
is genuinely the minimal complete closure, prepare requires
`--directory-scope-attestation directory-is-minimal-complete-closure`.

Round 2 and Round 3 also require `--predecessor-run-dir` and a hash-bound `--repair-closure`. The closure must cover the exact finalized predecessor finding set, including confirmed, advisory, and refuted dispositions. A later complete discovery also requires `--round-entry-reason` with `novel_p0_p1`, `authority_context_graph_changed`, or `high_risk_boundary_changed`; the last reason also requires explicit changed `--high-risk-boundary` artifacts.

For `bootstrap-implementation-conformance`, repair rounds also require
`--acceptance-repair-route <route.json>` and
`--acceptance-repair-completeness <projection.json>`. Use the exact output of
Acceptance `prepare-bootstrap` and its replayed completeness projection. The
controller binds both files, family, consumed round, next round, and typed
entry reason before preparing reviewer material.

When that route selects complete discovery after Round 1, show the user the
typed trigger, expected benefit/cost, your `recommend` or `do_not_recommend`
judgement, and a confidence in `[0,1]`. Only after explicit confirmation run:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py authorize-finding-mode-reentry \
  --repository-root <repo> --lineage-family-id <family> --next-review-round <round> \
  --predecessor-run-dir <run> [--acceptance-repair-route <route.json>] \
  --round-entry-reason <typed-trigger> --recommendation <recommend|do_not_recommend> \
  --confidence <0..1> --rationale <reason> --user-confirmed --out <authorization.json>
```

Implementation-conformance re-entry requires the Acceptance route argument;
standalone plan/Skill review instead relies on Bootstrap's deterministic typed
entry validation. Pass the append-only result to `prepare --finding-mode-reentry-authorization
<authorization.json>`. The CLI revalidates its lineage, predecessor, round,
typed trigger, Acceptance route hash, recommendation, confidence, and user
confirmation. Without it, later discovery fails before prompts or processes.

For Round 1 implementation conformance, pass the Acceptance-owned prepared
input as `--acceptance-run-input`. A nonexistent `--scope` is valid only when
the replayed candidate identity declares that exact path deleted, the path is
still absent, and its hash matches bytes read from the custody-bound immutable
Git baseline. The public manifest never accepts a caller snapshot or source
path. For repair rounds, a truly deleted predecessor artifact continues to be
inferred from frozen predecessor evidence and current absence; do not pass that
repair-only deletion as a nonexistent `--scope`. Both forms enter the Artifact
View deleted tree and remain formal reviewer evidence.

Prepare freezes Git HEAD, Git index, direct artifacts, execution read set, dependency closure, context graph, cost estimate, and, for Codex Exec, `artifact-view.v1`. A replacement for a stale run uses a new review ID and fresh snapshot; the new run does not inherit stale state.

When knowledge context is supplied, prepare evaluates adapter-owned consumption decisions before freezing the Artifact View. Only accepted decisions with nonempty satisfied context classes may augment required context; rejected decisions remain metadata and cannot satisfy profile completeness. Children never invoke Locator after prepare.

Pass the VDD-owned file through `prepare --knowledge-context <repo-relative-path>`.
Prepare verifies every accepted candidate is already in scope with the exact
source hash, then records the context hash and selected candidates in the
frozen manifest. Bootstrap does not create a new Locator query or promote a
candidate on its own.

Prepare also requires the adjacent VDD freeze receipt, verifies both files from
the same bytes collected into scope, and binds every path in each accepted
candidate's complete Locator read-set into the Artifact View and mapped context
classes. The shared validator must byte-match current main.

The shared context validator also verifies the current publication pointer,
immutable generation manifest, Catalog/policy/projection bindings, and current
main source hashes. A missing, stale, or tampered publication blocks prepare.
No Bootstrap child may use the staging-only `--allow-unpublished-inputs` path.

An abandoned Codex Exec run with no gate and incomplete required layers may be replaced at the same round after repairing the execution defect. Preserve the abandoned evidence and carry any valid partial finding into repair evidence or the replacement review scope; this exception does not reset a gated or completed semantic round.

## Complete Deterministic Preflight

Run every check from `review-input.json.deterministicPreflightPolicy`. Save command, exit code, output path, and output hash under `<run>/preflight/`, then complete `preflight-result.json`.

Stop before semantic reviewers when a required check fails or evidence is stale.

## Prove Codex Access

For `codex-exec`, run the identity-equivalent access probe after preflight and before authorization. Use `--role discovery` for complete discovery and `--role focused_repair_verifier` for focused verification:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py prove-access \
  --run-dir <run> \
  --codex-command <codex executable> \
  --role <discovery|focused_repair_verifier> \
  --model <profile-allowed model> \
  [--ack-high-cost]
```

The discovery route is round-bound. Every Round 1-2 profile, including Skill/route review, uses Terra at its profile-declared effort; every valid Round 3 uses Sol/high. Ordinary focused repair verification also uses Terra/high. A focused repair whose frozen predecessor contains P0, `security`, or a structured high-risk verifier class uses the same escalation policy as independent verification. The probe must use the same executable identity, exact resolved model/reasoning route, sandbox, environment class, and Artifact View contract intended for reviewers. When reviewer roles resolve to different routes, one `prove-access --role discovery` command creates one proof per distinct route; roles with an identical route share a proof, and launch authorization binds the complete proof set. An explicitly selected allowed fallback model creates a separate model-bound proof sidecar; the preferred proof is never silently reused for a fallback. It does not cache artifact, preflight, or authority proof. For a high-cost run, show the estimate and obtain explicit acknowledgement before adding `--ack-high-cost`; no model process starts without it.

## Execution-Plane Continuity

Choose one command execution plane before `prove-access`. For a Codex Exec run,
the same plane must execute `prove-access`, `authorize-launch`, every
`run-layer`, and `process-lease --action inspect`. FastCtx is the repository
default for this sequence; a PowerShell session must not take over a run that
was proven from FastCtx, or vice versa. The access proof binds the allowlisted
environment evidence hash, user identity, platform, executable, model, and
sandbox. A drift fails before child launch. Preserve that failed evidence and
prepare a new run from the intended plane; do not overwrite a proof or bypass
the drift check.

The runner materializes the deterministic handshake helper inside each attempt directory so the sandboxed child does not need to read the repository `.agents` entrypoint. The parent revalidates the complete Artifact View coverage and handshake hash; a child-produced hash alone is never access proof.

## Authorize Launch

Run `authorize-launch`. It revalidates preflight, access proof, Artifact View, repair closure, Git index, write set, execution read set, dependency closure, profile, schema, and artifact freshness.

If `reviewCostEstimate.highCost=true`, show the P50/P90 token and wall-time bands, sample count, confidence, verifier likelihood, and retry risk. Obtain explicit user acknowledgement before `--ack-high-cost`.

## Run Layers

Run each discovery role only when `review-input.json.findingMode=discovery` and after launch authorization. The CLI rejects discovery roles in `verification_only` mode:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py run-layer \
  --run-dir <run> \
  --role <blind_hunter|edge_case_hunter|acceptance_auditor> \
  --codex-command <codex executable> \
  --model <profile-allowed model>
```

Each child must execute its same-session Artifact View handshake before semantic work and return only a structured candidate response. A completed Codex discovery payload returns semantic candidates and `bootstrap-artifact-view-read-receipt.v1`; it never reproduces coverage path arrays. The parent validates the receipt and handshake, constructs exact ordered formal coverage from the frozen manifest, validates the complete formal output, and writes it atomically. Manual and specialized-agent modes still fill and validate explicit coverage arrays because their reads occur outside the parent-owned Codex boundary. Every completed reviewer or verifier payload receives one final frozen-authority validation immediately before publication; a failure at that boundary leaves the prior formal bytes unchanged and records a failed attempt. Verifier output additionally requires exact blocker evidence and complete `contextRead` coverage against the frozen gate before publication. The verifier runtime prompt derives and re-emits every full inclusive blocker range and all `contextRead` references from the hash-bound candidate sidecar; it must not rely on a start-line-only summary in a saved prompt. Failed attempts remain under `attempts/<attempt-id>/` and never replace completed formal evidence.

When the frozen reviewable bytes exceed the controller threshold, the parent creates a stable ordered file/line segment plan and launches isolated attempts for the same reviewer role. Each attempt is bound to one segment and returns `bootstrap-artifact-view-segment-receipt.v1`, including the assigned reviewer role; it cannot claim whole-view coverage. The parent persists each validated segment result, rejects missing, duplicate, reordered, overlapping, role-drifted, or hash-mismatched receipts, retries only the failed transport segment inside the same semantic round, and publishes one formal role output only after every expected receipt passes. Discovery candidates remain independent. Verifier partial decisions are folded once per finding: independent-verifier verdict conflicts fail closed, while focused-repair `blocking` takes precedence over `verified_fixed`; evidence references are unioned deterministically. Segmentation does not shrink the Artifact View, create another reviewer identity, or consume another semantic round.

If a discovery or verifier formal output was validly published but interruption prevented
the immediately following `attempt-completed` append, retry the same role. The
reservation path first requires the original controller identity to be dead,
validates the frozen formal output, and appends one reconciliation completion
event for the original attempt. A live controller is left to finish its own
append. After reconciliation, continue to gate or finalize without launching
another model or overwriting the formal file.

Child launch/exit failure, malformed strict JSON, invalid candidate binding or
shape, and an invalid Artifact View receipt are transport attempt failures.
They append `attempt-failed`, keep formal output bytes unchanged, and retry the
same role in the same run. Do not create a new semantic round, review ID, or
successor lineage for a transport failure.

Codex children launch in a controller-owned process group. A no-progress
timeout terminates that child tree before the controller records the timeout
and terminal transport event. If the controller is interrupted first, a later
`process-lease --action inspect` verifies the recorded PID identity, terminates
an expired no-progress tree, then appends the timeout and `attempt-failed`
events. It never treats the absence of controller output as a semantic result.

For Codex Exec, the child reads every artifact from the frozen Artifact View `snapshotPath` and cites `originalPath`. The runtime prompt names the absolute run directory and manifest. The child must not read live originals, edit formal reviewer/verifier outputs, or invoke `validate-layer`; those are parent control-plane responsibilities.

Only overlapping formal write sets block concurrency. Non-overlapping reviewer roles may run concurrently while Git index and authority freshness remain frozen.

Manual and specialized-agent modes remain external execution boundaries. Their operators own process launch and must preserve the same reviewer independence and output contracts.

## Gate And Verify

After all three layers validate, run `gate`. Report accepted and rejected counts only from successful gate output.

When gate returns `awaiting_verification`, first prove the independent verifier route:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py prove-access \
  --run-dir <run> \
  --codex-command <codex executable> \
  --role independent_verifier \
  [--ack-high-cost]
```

This creates `verifier-access-proof.json` only after the gate exists. A standard P1-only blocker set resolves to Terra/high. A P1 finding classified as `authority_control`, `lifecycle_control`, `protected_path`, or `shared_entrypoint` resolves the whole verifier run to Sol/high. Any P0 or `security` blocker resolves it to Sol/max. `verifierRiskClass` selects model capacity only and never changes severity. Data-corruption and permission-boundary findings must be classified as P0 or `security` so the structured gate can trigger max effort. The discovery `access-proof.json` cannot authorize the verifier.

Then run one independent verifier through `run-layer --role independent_verifier` or the approved external verifier boundary. The verifier must cover each blocker's exact evidence and every `contextRead` reference. If `inspect-run` reports `prove-verifier-access`, complete the verifier probe before launching the verifier.

If `inspect-run` reports `recover-invalid-verifier`, use the explicit append-only recovery command before retrying:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py recover-verifier \
  --run-dir <run>
```

This command is only for a completed Codex verifier output that fails current semantic validation. It archives the exact rejected bytes and opens a retry through a process event without clearing the formal file. It refuses valid, finalized, sealed, active-attempt, manual, or specialized-agent state. After recovery, follow `inspect-run`; do not edit verifier output or process evidence by hand.

Do not rerun gate over saved verifier decisions or reopen a finalized run.

## Dispose P2 And Finalize

Before finalizing accepted P2 findings, provide closure covering the exact P2 set. New runs may provide `p2-closure.v2.json`; stored runs continue to read `p2-dispositions.json` v1.

- Every P2 is `fixed`, `refuted`, or `deferred`.
- High-risk P2 cannot use the lightweight v2 bundle; use the v1 controlled closure path, where deferral remains prohibited.
- A v2 normal-risk deferral requires owner, future expiry, bounded non-impact evidence, current passed recheck evidence, and a recheck trigger inside the hash-bound bundle. A stored v1 deferral retains its profile-root authority and registered-process requirements. Successful current validation is required for v2 fixed/refuted closure.
- For stored v1 chains, execute registered P2 commands only through `run-p2-command`; its process-event and byte-binding rules remain unchanged. A v2 bundle instead references current structured JSON results by path/hash, exact schema version, current review/input/candidate/authority bindings, production time, and a controlled successful field/value. Handwritten prose, failed-state equality, or an unbound `exitCode: 0` is not v2 evidence.
- An expired deferral blocks automatically.

Finalize only after independent P0/P1 decisions and complete P2 dispositions. A final result cannot contain an open accepted P0/P1.

After finalization, emit a plan-consumable validation envelope by recomputing the frozen profile, preflight, gate, candidates, rejections, verifier decisions, P2 evidence, final result, dispositions, metrics, and artifact hashes. The envelope directly hash-binds `verifier-output.json` and, when present, `p2-dispositions.json`; a metrics-only or file-existence proof is invalid:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py validate-finalized-run \
  --run-dir <run> \
  --output <validation-envelope.json>
```

The envelope is validation evidence only. It always has `authorizes=[]` and explicitly excludes plan acceptance, implementation acceptance, protected handoff, release, commit, and done authority. A plan-local validator may consume the envelope, but must independently apply its own acceptance predicate.

New v3 envelopes also bind `candidateBindingHash`, covering the frozen artifact
set, any Acceptance candidate deletion freeze, authority context, write set,
execution read set, and dependency closure.
This permits a consumer to prove exact deterministic reuse after rerunning
`validate-finalized-run`; it is not an LLM result cache. Stored legacy envelopes
without this binding remain readable under their frozen v1/v2 schemas but are
ineligible for exact reuse.

`build-review-baseline` writes only below `logs/`. It records each replayed
finalized run's complete finding closure and aggregate semantic yield. A run
enters a cost cohort only when every required reviewer, required verifier, and
access probe has a unique ordered lifecycle, a bound process result, and token
usage rederived from the same Codex JSONL stdout. Wall time is the union of
active attempt intervals, excluding idle gaps between attempts. Cohorts bind
the configured role-to-model route: a legitimate mixed-model run is eligible
under its route hash when every actual attempt follows that route, while a
substituted or incomplete route remains operational-only.

Cost estimates use the schema-validated promoted calibration reference at
`references/review-cost-calibration.v1.json` with an implementation-bound file
hash. Missing cohorts use its declared conservative fallback. A missing,
corrupt, candidate-status, or substituted promoted reference fails closed.
Promotion adds a new versioned reference and updates the producer binding; it
does not overwrite a reference already bound by historical run manifests.
Synthetic confirmed/refuted calibration pairs live only under test fixtures;
they must never be copied from historical exact evidence or consumed by a
runtime reviewer prompt.

After a third-round manual pause, a successor policy cannot reset the existing lineage family. A new family is valid only after an explicit supersede or incompatible-scope decision creates a genuinely different acceptance target. The successor authority must still bind the exact authority-root registry frozen by that policy revision; a run-local null-predecessor authority is invalid. The consumer must rerun `validate-finalized-run`; a new change ID, saved minimal envelope, or self-declared independence flag cannot clear the old target's pause.

## Repair Rounds

Repair all accepted findings as one batch outside the read-only review run. Use deterministic targeted checks during repair; do not launch another full review after each finding.

For implementation acceptance, require the Acceptance-owned repair completeness
audit before re-entry. Its Quick Dev handoff identifies changed files, direct
consumers, targeted tests, validation references, generated sibling-callsite
inventories, and successful controlled producer/consumer composition receipts.
Producer and consumer path sets must be disjoint; a self-composition is not
consumer evidence. Read-only controlled commands are checked against repository
file-content hashes, including ignored `logs/` evidence, rather than Git status
labels alone. Missing tracked paths are represented as stable tombstones so a
legitimate deletion repair remains replayable.
Bootstrap consumes the resulting bounded route but does not authorize it or
reimplement the consumer audit.

A clean or P2-only finalized predecessor does not authorize a new complete
semantic round. Dispose P2 in the current run and use the registered targeted
closure or recheck path. A later complete discovery is exceptional: Acceptance
must produce a typed trigger, then the user must confirm the orchestrator's
recommendation and confidence through the CLI authorization above. A focused
verifier cannot create the trigger itself.

Round 2/3 repair closure is checked twice:

1. Prepare checks schema, predecessor identity, exact finding set, evidence paths, and proof-family compatibility.
2. Authorize checks current evidence hashes, source/validator bindings, Git index, write set, execution read set, dependency closure, and context freshness. Prepare also adds the live plan validator and every plan-local schema loaded by the control plane to the Artifact View, so any runtime authority drift fails closed before execution.

The current `bootstrap-repair-closure.v1.json` is an authority-only input. It
remains in the frozen Artifact View for reviewer read/hash coverage, while its
exact path is excluded from the repair `candidateHash`. This prevents a
whole-directory plan scope from creating a self-referential closure; all other
candidate artifacts and source/validator bindings remain bound.
Round 2/3 callers must list that closure path explicitly in `--scope`; the
controller does not silently widen a frozen scope. Missing or extra Artifact
View entries fail closed through the required-artifact-set binding.

At the third-round hard limit, unresolved blockers produce manual pause. Do not create Round 4 by changing the review ID.

When a blocked Round 3 reviewed the closure protocol itself and every exact
finding is repaired, one CLI-authorized hard-limit focused recovery may use
`bootstrap-focused-repair-verification` at `fullReviewRound=3`. Run
`authorize-hard-limit-focused-recovery` with the blocked envelope, current
deterministic repair closure, recommendation/confidence, and explicit user
confirmation, then pass its result through
`prepare --hard-limit-repair-recovery`. This verification-only run uses one
`focused_repair_verifier`, cannot discover or escalate, does not consume a
semantic round, and cannot authorize Acceptance. A passed run emits a
composite `manual-pause-protocol-review` authority for the Acceptance closure
consumer; stale repair bytes, a different family/finding set, non-blocked
predecessor, or any new blocker fail closed.

## Seal Without Rewriting History

Use `seal-run` only for additive lifecycle annotation:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py seal-run \
  --run-dir <run> \
  --state <abandoned|superseded|replaced-after-probe-failure> \
  --reason <stable-code> \
  [--successor <run>]
```

Finalized runs cannot be abandoned. A run with an active event-backed attempt or acquired lease cannot be sealed; inspect, reattach, or record terminal recovery evidence first. The incomplete-abandoned replacement exception applies only when no active event-backed attempt remains. Superseded runs identify a successor. A seal never changes reviewer, verifier, gate, event, lease, or final evidence.

## Validate Skill Changes

For a profile-declared companion, verify its capability ID/version, producer role, and schema hash through the repository Skill. Do not implement a consumer-owned semantic runner or bypass the existing `acceptance_auditor` launch authorization.

Run all of these after changing the control plane:

```text
py -3 .agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py
py -3 C:/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/run-phase-bootstrap-review
```

Then run a fresh `bootstrap-skill-route` review over the repository Skill, external thin route, standard, ADR, compatibility adapter, profiles, schemas, tests, operator guide, repository rules, and usage evidence.
