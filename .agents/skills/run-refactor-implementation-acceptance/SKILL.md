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

`scripts/acceptance_cli.py prepare-run` validates a hash-bound run input with replayable baseline and candidate content manifests, then writes a new non-authorizing run-input artifact. `policies/phase-service-code-review.v1.json` is the Phase-only policy pack. Pure Godot inputs are rejected as an unsupported code-review domain; mixed candidates must retain an unreviewed external partition.

`analyze-diff-coverage` consumes a frozen `phase-changed-line-set.v1` and a current Cobertura report. It uses only added or modified executable `PhaseA.Platform/**/*.cs` lines for the denominator, records every exclusion reason, and returns `incomplete` when a source mapping is missing. It never substitutes repository-wide coverage.

`audit-task-checklist` reads only explicitly declared authority checklist files. A checked item is `verified` only when its stable item identity has current matrix, implementation, test, and evidence references; source hash drift and checkbox-only closure fail the result. `run-phase-scan` is available only in `controlled_validation`, executes a shell-free typed command, and requires its declared Phase read scope to exactly cover the candidate's Phase changed paths.

The matrix, conditional Bootstrap import, action recovery, and final authorization stages are implemented only when their own plan slices and predicates are complete. A passing unit test or a Bootstrap `clean` result is not Program DoD.
