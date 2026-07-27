---
name: run-refactor-implementation-acceptance
description: Build deterministic implementation-acceptance evidence for one explicit refactor plan.
---

# Refactor Implementation Acceptance

This Skill builds deterministic implementation-acceptance evidence for exactly one explicit target plan. It does not implement target code, run Bootstrap automatically, approve a review, commit, hand off, release, or deploy.

## Modes

- `evidence_only` is the default. It reads current manifests and evidence and may only produce non-authorizing candidate conclusions.
- `controlled_validation` is available only after the caller supplies typed commands and isolated write roots. It cannot write target production code, live Phase state, workspaces, or historical evidence.

## Current Core

`scripts/acceptance_cli.py prepare-run` validates a hash-bound run input with replayable baseline and candidate content manifests, then writes a new non-authorizing run-input artifact. `policies/phase-service-code-review.v1.json` is the Phase-only policy pack. Pure Godot inputs are rejected as an unsupported code-review domain; mixed candidates must retain an unreviewed external partition.

`analyze-diff-coverage` consumes a frozen `phase-changed-line-set.v1` and a current Cobertura report. It uses only added or modified executable `PhaseA.Platform/**/*.cs` lines for the denominator, records every exclusion reason, and returns `incomplete` when a source mapping is missing. It never substitutes repository-wide coverage.

`audit-task-checklist` reads only explicitly declared authority checklist files. A checked item is `verified` only when its stable item identity has current matrix, implementation, test, and evidence references; source hash drift and checkbox-only closure fail the result. `run-phase-scan` is available only in `controlled_validation`, executes a shell-free typed command, and requires its declared Phase read scope to exactly cover the candidate's Phase changed paths.

The matrix, conditional Bootstrap import, action recovery, and final authorization stages are implemented only when their own plan slices and predicates are complete. A passing unit test or a Bootstrap `clean` result is not Program DoD.
