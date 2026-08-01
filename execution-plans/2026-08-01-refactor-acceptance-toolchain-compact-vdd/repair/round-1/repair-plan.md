# Repair Round 1 - Dirty Baseline Overlay Custody

## Finding

The first real consumer has a source file that was already dirty before either
implementation plan and later received an Acceptance extension. A HEAD-only
baseline would absorb the maintainer's prior bytes into the candidate.

Severity: P1. Failure family: `candidate-baseline-contamination`.

## Repair

Allow the compact projection request to name a sorted mapping from candidate
changed path to an explicit repository-relative baseline byte source. Build a
temporary Git index from the declared baseline commit, replace only those
blobs, and publish an unreachable synthetic commit as the immutable baseline
revision. Do not move refs or the worktree.

## Validation

- RED: the projector had no baseline overlay input and could only read HEAD.
- GREEN: `test_projection_uses_explicit_baseline_overlay_without_absorbing_prior_dirty_bytes`.
- Terminal: rerun the plan-owned implementation validator.

This repair changes no Acceptance authority and carries `authorizes=[]`.
