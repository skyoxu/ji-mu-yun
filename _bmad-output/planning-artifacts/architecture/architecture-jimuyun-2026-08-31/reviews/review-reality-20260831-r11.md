# Architecture Spine Reality / Brownfield Review — 2026-08-31 r11

Target: latest spine plus SPEC companions (candidate baseline
`b3334eac60308ea2d8b381710a64d712cfc7d0ff`).

## Verdict

**BLOCKED.** Contract text is converged: AD-15's matrix is explicit and
consistent with the typed runtime closure (AD-19), typed snapshot roots/Git
delta (AD-20), and stable AD registry (AD-21). No new architecture ambiguity
was found. Handoff remains blocked solely by brownfield implementation drift.

## Findings

### H1 — Executor/judge ownership is not migrated (implementation)

`tools/process_executor.py:8-9` returns a process object but does not persist a
receipt. `tools/artifact_owners.py:78-109` still executes the SUT, builds the
receipt and observation, invokes the judge validator, and writes a combined
artifact. The independent judge is not the sole observation/classification
writer required by AD-15(a).

### H2 — Legacy evidence remains authoritative (implementation)

The active path still emits/validates aggregate `executions` and legacy
`observed` semantics (`artifact_owners.py:104`, `independent_judge.py:30-44`).
The canonical `evidence_state` plus
`process_attempts`/`test_executions`/`cases` projection is not the active write
contract, so AD-15(b) is blocked.

### H3 — Runtime closure is not mechanically enforced (implementation)

`coverage_gate.py:7-22` validates only a minimal edge shape. It does not
enforce AD-19's closed tuple cardinality or re-read descriptor, receipt,
observation, target, fixture, candidate, producer, validator and failure-ID
hashes before admission. This permits stale/minimal edges to reach coverage.

### H4 — Q3/Q5/Q6 still bypass the frozen descriptor/executor seam (implementation)

`stage_command.py:17-18` has no RED registry entry. Its GREEN/REFACTOR path
directly invokes pytest (lines 43-72) and then a separate owner subprocess
(line 79), allowing selector/cwd/timeout/producer divergence from the frozen
descriptor and violating the AD-15(d) rejection rule.

### H5 — Terminal process evidence is pre-written (implementation)

`stage_command.py:26-30` calls `prepare_terminal_observation()` before terminal
execution; that function writes a successful `exit_code: 0` observation. Q8 can
therefore consume synthesized success instead of process-derived evidence,
blocking AD-15(e) and typed runtime closure.

