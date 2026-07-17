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

Round 2 and Round 3 also require `--predecessor-run-dir` and a hash-bound `--repair-closure`. The closure must cover the exact finalized predecessor finding set, including confirmed, advisory, and refuted dispositions.

Prepare freezes Git HEAD, Git index, direct artifacts, execution read set, dependency closure, context graph, cost estimate, and, for Codex Exec, `artifact-view.v1`. A replacement for a stale run uses a new review ID and fresh snapshot; the new run does not inherit stale state.

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

Each child must execute its same-session Artifact View handshake before semantic work and return only a structured candidate response. The runner validates binding and schema, then atomically writes the formal role output. Failed attempts remain under `attempts/<attempt-id>/` and never replace formal evidence.

For Codex Exec, the child reads every artifact from the frozen Artifact View `snapshotPath` and cites `originalPath`. The runtime prompt names the absolute run directory and manifest. The child must not read live originals, edit formal reviewer/verifier outputs, or invoke `validate-layer`; those are parent control-plane responsibilities.

Only overlapping formal write sets block concurrency. Non-overlapping reviewer roles may run concurrently while Git index and authority freshness remain frozen.

Manual and specialized-agent modes remain external execution boundaries. Their operators own process launch and must preserve the same reviewer independence and output contracts.

## Gate And Verify

After all three layers validate, run `gate`. Report accepted and rejected counts only from successful gate output.

When gate returns `awaiting_verification`, run one independent verifier through `run-layer --role independent_verifier` or the approved external verifier boundary. The verifier must cover each blocker's exact evidence and every `contextRead` reference.

Do not rerun gate over saved verifier decisions or reopen a finalized run.

## Dispose P2 And Finalize

Before finalizing accepted P2 findings, provide `p2-dispositions.json` covering the exact P2 set.

- Every P2 is `fixed`, `refuted`, or `deferred`.
- High-risk P2 cannot be deferred.
- Deferral requires owner, future expiry, reason, and closure test.
- An expired deferral blocks automatically.

Finalize only after independent P0/P1 decisions and complete P2 dispositions. A final result cannot contain an open accepted P0/P1.

## Repair Rounds

Repair all accepted findings as one batch outside the read-only review run. Use deterministic targeted checks during repair; do not launch another full review after each finding.

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

Finalized runs cannot be abandoned. Superseded runs identify a successor. A seal never changes reviewer, verifier, gate, event, lease, or final evidence.

## Validate Skill Changes

Run all of these after changing the control plane:

```text
py -3 .agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py
py -3 C:/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/run-phase-bootstrap-review
```

Then run a fresh `bootstrap-skill-route` review over the repository Skill, external thin route, standard, ADR, compatibility adapter, profiles, schemas, tests, operator guide, repository rules, and usage evidence.
