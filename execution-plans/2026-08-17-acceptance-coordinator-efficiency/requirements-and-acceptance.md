# Acceptance Coordinator Efficiency Requirements

## Scope

This is a compact implementation contract derived from
`../2026-08-15-acceptance-review-bootstrap-efficiency/acceptance-workflow-optimization.md`.
It intentionally has four implementation slices, not a separate requirement
and acceptance inventory for every internal artifact.

## S0 - Identity And Authority

Behavior: Quick Dev `implementation-complete` receipts bind candidate content
manifest, candidate custody/snapshot, and terminal-runner identity. Acceptance
requires an exact three-part match. A projection bundle owns its knowledge
context reference; `prepare-run` cannot replace it. Environment identity binds
only descriptor-declared behavior-affecting variables.

Exit: mismatch rejection and matching receipt admission are covered in existing
Quick Dev and Acceptance tests.

## S1 - Deterministic Fast Path

Behavior: Acceptance freezes candidate, projects changed-set/closure/required
checks, then machine-selects the route. Only a machine-selected
`deterministic_only` route consumes a deterministic source-sufficiency receipt;
it starts neither semantic child nor Bootstrap. Existing context refresh/rehash
continues degraded `catalog_stale` and source-byte refresh without a manually
reassembled context.

Exit: caller-provided deterministic route is rejected, while a machine-selected
deterministic route completes with no semantic or Bootstrap invocation.

## S2 - Idempotency And Recovery

Behavior: identical finalization and receipt/import bindings replay immutable
success rather than append-only conflict. Stale actions produce a successor
attempt; a target-level latest-successor pointer makes the current run
deterministic without deleting history.

Exit: replay returns the original result; stale recovery resumes the successor
and concurrent event sequencing does not corrupt the run.

## S3 - Coordinator

Behavior: `acceptance_cli.py run-coordinator` is one-shot, reentrant and
idempotent. It resolves the target, validates handoff, consumes bundle-owned
context, follows the action DAG, recovers stale actions, finalizes and replays
package validation. It records elapsed/wait/intervention telemetry. Semantic
routes emit a typed Bootstrap handoff and stop at the explicit boundary.

Exit: a repeated invocation resumes or replays the same binding without a new
run, and the terminal suite passes.

## Non-Goals

- No Background supervisor or daemon.
- No Bootstrap invocation from deterministic-only acceptance.
- No Knowledge publication by Acceptance.
- No lifecycle ownership change, Phase/runtime/workspace change, or rewrite of
  historical Acceptance evidence.
