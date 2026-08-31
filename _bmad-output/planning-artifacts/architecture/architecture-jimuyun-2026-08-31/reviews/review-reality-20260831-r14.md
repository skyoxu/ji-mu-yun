# Architecture Spine Reality / Brownfield Review — 2026-08-31 r14

Target: latest working-tree `ARCHITECTURE-SPINE.md` and SPEC companions (base
commit `b3334eac60308ea2d8b381710a64d712cfc7d0ff`, with the current companion
edits present in the worktree).

## Verdict

**BLOCKED.** The architecture and companion contracts are internally
consistent. AD-15 remains a seven-row, mechanical handoff gate; AD-19 fixes
typed runtime closure/cardinality; AD-20 fixes typed snapshot roots and exact
Git delta; AD-21 fixes stable decision identity selection. No contract
ambiguity was found. Handoff is blocked only because the current plan-local
implementation has not migrated to these contracts.

## Findings

### H1 — Receipt and observation writers remain combined (implementation)

`process_executor.py:8-9` returns a process object without persisting a
receipt. `artifact_owners.py:78-109` executes the SUT, creates receipt and
observation, calls the judge validator, and writes a combined artifact. This
does not satisfy AD-15(a)'s executor-only receipt and judge-only
observation/classification ownership.

### H2 — Legacy evidence is still authoritative (implementation)

`artifact_owners.py:104` emits aggregate `executions`, and
`independent_judge.py:30-44` validates that field. The active path does not
produce canonical `evidence_state` with separated
`process_attempts`/`test_executions`/`cases`; AD-15(b) remains blocked.

### H3 — Runtime-edge closure/hash enforcement is missing (implementation)

`coverage_gate.py:7-22` accepts a minimal acceptance/case/observation shape,
without enforcing AD-19 tuple cardinality or re-reading descriptor, receipt,
observation, target, fixture, candidate, producer, validator and failure-ID
hashes. Stale or hand-authored edges can still reach coverage.

### H4 — Lifecycle stages bypass one descriptor/executor seam (implementation)

`stage_command.py:17-18` registers no RED command. GREEN/REFACTOR directly run
pytest and then invoke `artifact_owners.py` separately, permitting selector,
cwd, timeout and producer divergence from the frozen descriptor; this violates
AD-15(d).

### H5 — Terminal success is pre-written (implementation)

`stage_command.py:26-30` invokes `prepare_terminal_observation()` before terminal
execution. That function writes an `exit_code: 0` observation first, allowing
Q8 to consume synthesized process truth instead of a process-derived receipt
and observation, violating AD-15(e).

## Handoff decision

Keep `status: draft`; resolve H1-H5 plus the AD-15 atomic-write and resolver
invocation rows, then run the complete Reviewer Gate on a fresh revision.

