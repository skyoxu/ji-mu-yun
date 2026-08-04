# RMAP Replay Bootstrap Baseline

## Decision

Repository-maintenance TDD replay may initialize an isolated worktree with a
hash-bound adapter runtime baseline before S0 RED. The baseline is not owned
by a behavior slice and does not authorize slice-ready, implementation
candidate, implementation acceptance, handoff, release, or commit.

## Constraints

- Bootstrap runs only in an isolated worktree.
- Every copied artifact is hash bound to its source.
- Bootstrap artifacts are excluded from the candidate diff and slice effect
  fold, with a separate append-only preparation manifest.
- The first behavior-slice RED remains required.
