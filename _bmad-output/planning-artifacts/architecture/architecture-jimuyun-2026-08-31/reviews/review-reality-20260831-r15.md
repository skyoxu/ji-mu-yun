# Architecture Spine Reality / Brownfield Review — 2026-08-31 r15

Target: current working-tree spine and SPEC companions (base commit
`b3334eac60308ea2d8b381710a64d712cfc7d0ff`).

## Verdict

**BLOCKED.** Architecture text and companions remain contract-convergent:
AD-15's matrix is explicit, and AD-19 typed closure, AD-20 typed snapshot/Git
delta, and AD-21 stable decision registry introduce no ambiguity. The handoff
blocker is implementation migration only; keep spine `status: draft`.

## Findings

### H1 — Executor/judge ownership still violates AD-15(a)

`process_executor.py:8-9` has no receipt writer. `artifact_owners.py:78-109`
executes the SUT and writes a combined receipt/observation while invoking the
judge validator. Independent judge is not the sole observation/classification
writer.

### H2 — Legacy evidence remains active, not read-only projection

`artifact_owners.py:104` emits aggregate `executions`; `independent_judge.py`
validates that field. Canonical evidence state and separated counters required by
the companions are not the active write contract.

### H3 — Runtime typed closure and hash gate are not enforced

`coverage_gate.py:7-22` checks only minimal edge shape; it does not enforce
AD-19 tuple cardinality or re-read descriptor/receipt/observation/target/fixture,
candidate, producer, validator and failure-identity hashes.

### H4 — Lifecycle stages bypass descriptor/executor seam

`stage_command.py` has no RED registry command and directly runs pytest before a
separate owner process for GREEN/REFACTOR. Selector, cwd, timeout and producer
identity can diverge from the frozen descriptor.

### H5 — Terminal process truth is pre-written

`stage_command.py:26-30` calls `prepare_terminal_observation()` first; that
function writes a successful `exit_code: 0` observation before terminal
execution. Q8 can therefore consume synthesized success instead of process
evidence.

