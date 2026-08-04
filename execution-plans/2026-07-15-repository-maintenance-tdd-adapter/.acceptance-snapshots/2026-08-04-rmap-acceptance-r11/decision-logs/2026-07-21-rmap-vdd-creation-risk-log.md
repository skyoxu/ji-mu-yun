# RMAP VDD Creation Risk Log

## Scope

This log records implementation findings from
`2026-07-15-repository-maintenance-tdd-adapter` for follow-up in the VDD
creation workflow. It is observational and does not authorize acceptance,
release, or a rewrite of historical evidence.

## Findings

1. The plan required S0-S6 to be replayable from Git `HEAD`, while adapter
   runtime assets required by S1 and later were outside that baseline.
2. S0 RED required a single ownership failure, but its contract also pinned
   authority and source bytes produced only after S0 GREEN. A clean replay
   therefore emitted unrelated hash failures before its declared RED.
3. Candidate validation required the current scoped Git diff to equal the
   cumulative slice-effect fold. Historical stage projections did not cover
   every actual scoped worktree change.
4. Adjacent slices used different frozen baselines, while the original
   candidate lineage model assumed one global baseline.

## Evidence

- `logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S6/RUN-20260721T081500Z/candidate-lineage-mismatch.v1.json`
- `logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S6/RUN-20260721T081500Z/candidate-replay-scope.v1.json`
- `C:/jimuyun-rmap-replay-20260721/logs/tdd-adapter/repository-maintenance-tdd-adapter/replay-preparation-20260721T123500Z.json`
- `decision-logs/2026-07-21-rmap-replay-bootstrap-baseline.md`

## VDD Follow-up Requirements

- Audit Git baseline, untracked assets, and required RED runtime before
  declaring a plan replayable.
- Require an explicit, hash-bound bootstrap baseline when runtime assets are
  intentionally outside Git `HEAD`.
- Reject RED definitions whose prerequisite hash checks depend on GREEN writes.
- Require multi-baseline lineage transitions to be path-level and hash-bound.
- Reject plan creation when scoped current changes cannot be assigned to an
  initial baseline, an explicit bootstrap baseline, or a declared slice.
