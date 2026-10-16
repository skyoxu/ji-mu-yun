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

## Recovery Metadata Supplement (2026-09-30)

Added for recovery-document schema completeness. The original narrative,
conclusions, and evidence above remain unchanged. This supplement does not
create a new acceptance result or a historical candidate binding.

- Title: RMAP VDD Creation Risk Log
- Date: 2026-07-21
- Status: observational - does not authorize acceptance or release
- Supersedes: none
- Superseded by: none
- Branch: n/a - the original narrative did not capture its decision-time branch
- Git Head: n/a - the original narrative did not capture its decision-time commit; this metadata supplement does not infer a historical binding
- Why now: Replay exposed missing runtime assets, prerequisite hash failures, and lineage mismatch.
- Context: See Scope, Findings, and Evidence above.
- Decision: Record VDD follow-up requirements; do not reinterpret historical acceptance evidence.
- Consequences: Future plan creation must audit replay prerequisites, ownership, and multi-baseline lineage.
- Recovery impact: Require explicit hash-bound bootstrap preparation and reject unassigned scoped changes.
- Validation: The original Evidence section records mismatches, not a passing replay or acceptance result.
- Related ADRs: n/a - the original risk narrative does not cite an ADR
- Related execution plans: `execution-plans/2026-07-15-repository-maintenance-tdd-adapter/`
- Related task id(s): n/a - no stable task identifier was captured in the original narrative
- Related run id: RUN-20260721T081500Z; replay-preparation-20260721T123500Z (original Evidence section)
- Related latest.json: n/a - no canonical latest.json pointer was captured in the original narrative
- Related pipeline artifacts: `logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S6/RUN-20260721T081500Z/candidate-lineage-mismatch.v1.json`, `logs/tdd-adapter/repository-maintenance-tdd-adapter/RMAP-S6/RUN-20260721T081500Z/candidate-replay-scope.v1.json`; the external replay-preparation path remains recorded above
