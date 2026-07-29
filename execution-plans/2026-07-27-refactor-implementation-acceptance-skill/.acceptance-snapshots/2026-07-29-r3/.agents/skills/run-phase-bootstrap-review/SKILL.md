---
name: run-phase-bootstrap-review
description: Prepare, execute, gate, resume, inspect, seal, or finalize Ji Mu Yun evidence-gated Bootstrap Reviews for plan authority, implementation conformance, Skills/routes, and focused changes. Use for Bootstrap Review, Whole-directory review, Blind Hunter / Edge Case Hunter / Acceptance Auditor orchestration, independent blocker verification, repair-round closure, or recovery of an existing review run.
---

# Run Phase Bootstrap Review

Use the repository-owned control plane. This Skill owns the executable protocol and generic schemas; it does not own the reviewed plan's business acceptance, commit, handoff, release, or done state.

## Authority Order

Read these before operating the workflow:

1. `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`.
2. `docs/standards/bootstrap-review-control-plane.md`.
3. `references/review-profiles.v1.json`.
4. `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md` for migration examples.

The repository entrypoint is:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
```

The 2026-07-12 CLI is a revision-bound compatibility adapter only. Do not add durable behavior there.

## Hard Boundaries

- Keep Blind Hunter, Edge Case Hunter, and Acceptance Auditor isolated. Do not share candidates or suspected findings before gate.
- Require complete artifact and context coverage. Sampling is prohibited and zero findings are valid.
- Use an independent verifier for every accepted P0/P1.
- Never run more than three complete semantic rounds for one `changeId` under the current policy.
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
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py inspect-run --run-dir <run>
```

Follow the reported `nextAction`. Do not infer current state from an old assistant summary.

## Prepare

Create a new run with stable `reviewId`, `changeId`, round, profile, scopes, context classes, execution mode, and exclusivity attestation.

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

Round 2 and Round 3 also require `--predecessor-run-dir` and a hash-bound `--repair-closure`. The closure must cover the exact finalized predecessor finding set, including confirmed, advisory, and refuted dispositions.

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

For `codex-exec`, run the explicit identity-equivalent access probe after preflight and before authorization:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py prove-access \
  --run-dir <run> \
  --codex-command <codex executable> \
  --model <profile-allowed model> \
  [--ack-high-cost]
```

The probe must use the same executable identity, model route, sandbox, environment class, and Artifact View contract intended for reviewers. It does not cache artifact, preflight, or authority proof. For a high-cost run, show the estimate and obtain explicit acknowledgement before adding `--ack-high-cost`; no model process starts without it.

The runner materializes the deterministic handshake helper inside each attempt directory so the sandboxed child does not need to read the repository `.agents` entrypoint. The parent revalidates the complete Artifact View coverage and handshake hash; a child-produced hash alone is never access proof.

## Authorize Launch

Run `authorize-launch`. It revalidates preflight, access proof, Artifact View, repair closure, Git index, write set, execution read set, dependency closure, profile, schema, and artifact freshness.

If `reviewCostEstimate.highCost=true`, show the P50/P90 token and wall-time bands, sample count, confidence, verifier likelihood, and retry risk. Obtain explicit user acknowledgement before `--ack-high-cost`.

## Run Layers

Run each discovery role only after explicit user authorization:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py run-layer \
  --run-dir <run> \
  --role <blind_hunter|edge_case_hunter|acceptance_auditor> \
  --codex-command <codex executable> \
  --model <profile-allowed model>
```

Each child must execute its same-session Artifact View handshake before semantic work and return only a structured candidate response. A completed Codex discovery payload returns semantic candidates and `bootstrap-artifact-view-read-receipt.v1`; it never reproduces coverage path arrays. The parent validates the receipt and handshake, constructs exact ordered formal coverage from the frozen manifest, validates the complete formal output, and writes it atomically. Manual and specialized-agent modes still fill and validate explicit coverage arrays because their reads occur outside the parent-owned Codex boundary. Every completed reviewer or verifier payload receives one final frozen-authority validation immediately before publication; a failure at that boundary leaves the prior formal bytes unchanged and records a failed attempt. Verifier output additionally requires exact blocker evidence and complete `contextRead` coverage against the frozen gate before publication. The verifier runtime prompt derives and re-emits every full inclusive blocker range and all `contextRead` references from the hash-bound candidate sidecar; it must not rely on a start-line-only summary in a saved prompt. Failed attempts remain under `attempts/<attempt-id>/` and never replace completed formal evidence.

Child launch/exit failure, malformed strict JSON, invalid candidate binding or
shape, and an invalid Artifact View receipt are transport attempt failures.
They append `attempt-failed`, keep formal output bytes unchanged, and retry the
same role in the same run. Do not create a new semantic round, review ID, or
successor lineage for a transport failure.

For Codex Exec, the child reads every artifact from the frozen Artifact View `snapshotPath` and cites `originalPath`. The runtime prompt names the absolute run directory and manifest. The child must not read live originals, edit formal reviewer/verifier outputs, or invoke `validate-layer`; those are parent control-plane responsibilities.

Only overlapping formal write sets block concurrency. Non-overlapping reviewer roles may run concurrently while Git index and authority freshness remain frozen.

Manual and specialized-agent modes remain external execution boundaries. Their operators own process launch and must preserve the same reviewer independence and output contracts.

## Gate And Verify

After all three layers validate, run `gate`. Report accepted and rejected counts only from successful gate output.

When gate returns `awaiting_verification`, run one independent verifier through `run-layer --role independent_verifier` or the approved external verifier boundary. The verifier must cover each blocker's exact evidence and every `contextRead` reference.

If `inspect-run` reports `recover-invalid-verifier`, use the explicit append-only recovery command before retrying:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py recover-verifier \
  --run-dir <run>
```

This command is only for a completed Codex verifier output that fails current semantic validation. It archives the exact rejected bytes and opens a retry through a process event without clearing the formal file. It refuses valid, finalized, sealed, active-attempt, manual, or specialized-agent state. After recovery, follow `inspect-run`; do not edit verifier output or process evidence by hand.

Do not rerun gate over saved verifier decisions or reopen a finalized run.

## Dispose P2 And Finalize

Before finalizing accepted P2 findings, provide `p2-dispositions.json` covering the exact P2 set.

- Every P2 is `fixed`, `refuted`, or `deferred`.
- High-risk P2 cannot be deferred.
- Deferral requires a schema-valid authorized owner reference chained to the profile-bound authority-root registry, future expiry, non-impact evidence, a root-authorized command descriptor, current recheck evidence, and a recheck trigger. Successful closure-process evidence is required only when the disposition becomes fixed or refuted.
- Execute registered P2 commands only through `run-p2-command`. It uses argument arrays with `shell=False`, a contained working directory, and the environment allowlist; it appends a hash-chained process event and binds actual stdout/stderr bytes. Each process result anchors its own `eventHash` in the shared append-only log, so later valid appends do not stale earlier results; legacy whole-log hash references remain read-only compatible. A handwritten `exitCode: 0` result is invalid.
- An expired deferral blocks automatically.

Finalize only after independent P0/P1 decisions and complete P2 dispositions. A final result cannot contain an open accepted P0/P1.

After finalization, emit a plan-consumable validation envelope by recomputing the frozen profile, preflight, gate, candidates, rejections, verifier decisions, P2 evidence, final result, dispositions, metrics, and artifact hashes. The envelope directly hash-binds `verifier-output.json` and, when present, `p2-dispositions.json`; a metrics-only or file-existence proof is invalid:

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py validate-finalized-run \
  --run-dir <run> \
  --output <validation-envelope.json>
```

The envelope is validation evidence only. It always has `authorizes=[]` and explicitly excludes plan acceptance, implementation acceptance, protected handoff, release, commit, and done authority. A plan-local validator may consume the envelope, but must independently apply its own acceptance predicate.

After a third-round manual pause, re-entry requires a schema-valid `bootstrap-successor-policy-decision.v1` bound to a trusted authorization event and a genuinely new change, policy, authority, review, and input lineage. The successor authority must bind the exact authority-root registry frozen by that policy revision; a run-local null-predecessor authority is invalid. The consumer must rerun `validate-finalized-run`; a saved minimal envelope or self-declared independence flag cannot clear the pause.

## Repair Rounds

Repair all accepted findings as one batch outside the read-only review run. Use deterministic targeted checks during repair; do not launch another full review after each finding.

A clean or P2-only finalized predecessor does not authorize a new complete
semantic round. Dispose P2 in the current run and use the registered targeted
closure or recheck path. Round 2 and Round 3 are reserved for a predecessor
with P0/P1 repair work, subject to the existing hard-limit rules.

Round 2/3 repair closure is checked twice:

1. Prepare checks schema, predecessor identity, exact finding set, evidence paths, and proof-family compatibility.
2. Authorize checks current evidence hashes, source/validator bindings, Git index, write set, execution read set, dependency closure, and context freshness.

At the third-round hard limit, unresolved blockers produce manual pause. Do not create Round 4 by changing the review ID.

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
