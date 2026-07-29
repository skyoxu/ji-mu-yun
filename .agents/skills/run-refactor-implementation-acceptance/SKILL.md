---
name: run-refactor-implementation-acceptance
description: Build deterministic implementation-acceptance evidence for one explicit refactor plan.
---

# Refactor Implementation Acceptance

This Skill builds deterministic implementation-acceptance evidence for exactly one explicit target plan. It does not implement target code, run Bootstrap automatically, approve a review, commit, hand off, release, or deploy.

## Modes

- `evidence_only` is the default. It reads current manifests and evidence and may only produce non-authorizing candidate conclusions.
- `controlled_validation` is available only after the caller supplies typed commands and isolated write roots. It cannot write target production code, live Phase state, workspaces, or historical evidence.

## Bootstrap Routing

When the immutable Bootstrap requirement decision is `required`, deterministic
validation must publish an append-only `review_required` route through
`prepare-bootstrap`. The route freezes the consumer-side decision, capability
binding, and Bootstrap-owned launch sidecar, then directs the caller to
`run-phase-bootstrap-review`.

This Skill never launches LLM reviewers itself. A caller must complete the
Bootstrap preflight, identity-equivalent access probe, and explicit high-cost
launch authorization before any reviewer layer starts. A deterministic pass
without a required finalized Bootstrap envelope remains a non-authorizing
candidate, not an implementation-acceptance pass.

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

## Current Core

Before `prepare-run`, create one Refactor Acceptance-owned knowledge context
through the canonical Locator:

```text
py -3 .agents/skills/run-refactor-implementation-acceptance/scripts/prepare_knowledge_context.py \
  --repository-root <repo> --request-id <id> --query <query> \
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

`scripts/acceptance_cli.py prepare-run` validates a hash-bound run input with replayable baseline and candidate content manifests, then writes a new non-authorizing run-input artifact. Commit candidates are checked against raw bytes from resolved immutable Git commits, and the resolved baseline/candidate OIDs are persisted in `candidateCustody`. Dirty-worktree and proposed-commit-set candidates must declare `candidate_frozen_snapshot_path` as `.acceptance-snapshots/<run_id>` beneath the target root; symlinks and live workspace substitutes are rejected, and the snapshot manifest receipt is persisted. `policies/phase-service-code-review.v1.json` is the Phase-only policy pack. Pure Godot inputs are rejected as an unsupported code-review domain; mixed candidates must retain an unreviewed external partition.

`analyze-diff-coverage` consumes a frozen `phase-changed-line-set.v1` and a current Cobertura report. It uses only added or modified executable `PhaseA.Platform/**/*.cs` lines for the denominator, records every exclusion reason, and returns `incomplete` when a source mapping is missing. It never substitutes repository-wide coverage.

`audit-task-checklist` reads only explicitly declared authority checklist files. A checked item is `verified` only when its stable item identity has current matrix, implementation, test, and evidence references; source hash drift, checkbox-only closure, and request-controlled optionality fail the result. `run-command` resolves an exact descriptor from a hash-bound command registry; it never executes a caller-supplied descriptor. `run-phase-scan` is available only in `controlled_validation`, executes that registered shell-free command from a hash-verified frozen candidate snapshot, and requires its declared Phase read scope to exactly cover the candidate's Phase changed paths.

The matrix, conditional Bootstrap import, action recovery, and final authorization stages are implemented only when their own plan slices and predicates are complete. A passing unit test or a Bootstrap `clean` result is not Program DoD.
