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

## Recovery Metadata Supplement (2026-09-30)

Added for recovery-document schema completeness. The original narrative,
conclusions, and evidence above remain unchanged. This supplement does not
create a new acceptance result or a historical candidate binding.

- Title: RMAP Replay Bootstrap Baseline
- Date: 2026-07-21
- Status: recorded - original narrative does not state formal acceptance status
- Supersedes: none
- Superseded by: none
- Branch: n/a - the original narrative did not capture its decision-time branch
- Git Head: n/a - the original narrative did not capture its decision-time commit; this metadata supplement does not infer a historical binding
- Why now: The replay baseline lacked adapter runtime assets needed before S0 RED.
- Context: See the original Decision and Constraints sections above.
- Decision: Allow an isolated, hash-bound preparation baseline before S0 RED; it grants no delivery authority.
- Consequences: Keep preparation outside candidate diffs and slice-effect folds; retain the first behavior-slice RED.
- Recovery impact: Recover using the separate append-only preparation manifest and source hashes.
- Validation: The original narrative defines constraints but records no standalone validation result; this supplement grants no completion authority.
- Related ADRs: n/a - the original narrative does not cite an ADR
- Related execution plans: `execution-plans/2026-07-15-repository-maintenance-tdd-adapter/`
- Related task id(s): n/a - no stable task identifier was captured in the original narrative
- Related run id: n/a - the original baseline narrative records no run identifier
- Related latest.json: n/a - no canonical latest.json pointer was captured in the original narrative
- Related pipeline artifacts: n/a - the original baseline narrative records no artifact locator
