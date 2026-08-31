# Architecture Spine Reality / Brownfield Review — 2026-08-31 r17

Target: latest know109-converged `ARCHITECTURE-SPINE.md` and frozen SPEC
companions; implementation baseline `b3334eac60308ea2d8b381710a64d712cfc7d0ff`.

## Verdict

**BLOCKED for implementation handoff; architecture text is contract-convergent.**
AD-15 is explicitly diagnostic/migration-only and does not couple runtime
truth-floor execution to governance artifacts. AD-19 typed closure, AD-20
typed snapshot roots/Git delta, AD-21 recovery-only decision registry, and
AD-13 runtime version probing are stated without a new contract fork. The
remaining blockers are current-code migration gaps.

## Findings

### H1 — Executor/judge ownership is still combined (implementation)

`tools/process_executor.py:8-9` returns a `CompletedProcess` and persists no
receipt. `tools/artifact_owners.py:78-109` executes the SUT, constructs receipt
and observation, invokes the judge validator, and writes one combined artifact.
The independent judge is therefore not the sole observation/classification
writer required by AD-15(a).

### H2 — Legacy evidence remains authoritative (implementation)

`artifact_owners.py:104` emits aggregate `executions`, and
`independent_judge.py:30-44` validates that field directly. The active path
does not emit canonical `evidence_state` and separated
`process_attempts`/`test_executions`/`cases`; compatibility projection is not
isolated read-only, blocking AD-15(b).

### H3 — Typed runtime closure and hash lineage are not enforced (implementation)

`coverage_gate.py:7-22` checks only acceptance/case/observation shape. It does
not enforce AD-19 tuple-key cardinality or re-read descriptor, receipt,
observation, target, fixture, candidate, producer, validator and failure-ID
hashes before coverage admission.

### H4 — Registered stages bypass the descriptor/executor seam (implementation)

`stage_command.py` registers no RED command and directly invokes pytest for
GREEN/REFACTOR before a separate owner process. Selector, cwd, timeout and
producer identity can diverge from the frozen descriptor, violating AD-15(d).
The required AD-13 launcher/interpreter/test-runner version probe is likewise
not present in this process path.

### H5 — Terminal truth and snapshot revalidation are not process-derived (implementation)

`stage_command.py:26-30` calls `prepare_terminal_observation()` before terminal
execution; `terminal_validator.py` writes `exit_code: 0` first. The local
`validate_all.py` manifest is not a demonstrated versioned resolver invoked at
Q0/Q4/Q7/Q8/terminal publication/recovery. Q8 can therefore consume synthesized
success without the AD-20 current-snapshot re-read.

## Handoff decision

Keep `status: draft`. Resolve H1-H5 and the associated AD-15 atomic-write and
resolver-invocation predicates, then rerun the complete Reviewer Gate on fresh
bytes. Do not promote this diagnostic report to implementation evidence.
