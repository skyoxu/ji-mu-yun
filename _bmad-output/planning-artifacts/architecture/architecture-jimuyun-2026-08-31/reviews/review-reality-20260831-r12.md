# Architecture Spine Reality / Brownfield Review — 2026-08-31 r12

Target: latest `ARCHITECTURE-SPINE.md` plus SPEC companions; code baseline
`b3334eac60308ea2d8b381710a64d712cfc7d0ff`.

## Verdict

**BLOCKED.** The architecture contract is converged and mechanically stated:
AD-15's matrix distinguishes mechanical inputs, sole writers/evaluators and
rejection predicates; AD-19 fixes typed runtime closure/cardinality; AD-20
fixes typed snapshot roots and exact Git delta; AD-21 fixes stable AD identity
selection. No new architecture ambiguity was found. The remaining blocker is
implementation migration from the current brownfield code to those contracts.

## Findings

### H1 — Receipt/observation ownership is still combined (implementation)

`tools/process_executor.py:8-9` returns only `CompletedProcess`. Active
`tools/artifact_owners.py:78-109` executes the SUT, constructs receipt and
observation, invokes the judge validator, and writes one combined artifact.
The independent judge is not the sole observation/classification writer.

### H2 — Legacy evidence fields remain active (implementation)

`artifact_owners.py:104` emits aggregate `executions`, and
`independent_judge.py:30-44` validates it directly. Canonical
`evidence_state` plus `process_attempts`/`test_executions`/`cases` is not the
active writer contract; compatibility projection is not isolated read-only.

### H3 — Typed runtime closure/hash gate is not enforced (implementation)

`tools/coverage_gate.py:7-22` checks only minimal acceptance/case/observation
shape. It does not enforce AD-19's closed tuple cardinality or re-read
descriptor, receipt, observation, target, fixture, candidate, producer,
validator and failure-identity hashes before coverage admission.

### H4 — Q3/Q5/Q6 bypass one descriptor/executor seam (implementation)

`tools/stage_command.py:17-18` registers no RED command. Its GREEN/REFACTOR
path directly invokes pytest (lines 43-72) and then a separate owner process
(line 79), permitting selector/cwd/timeout/producer divergence from the frozen
descriptor and violating AD-15's direct-path rejection rule.

### H5 — Terminal observation is synthesized before terminal execution (implementation)

`stage_command.py:26-30` calls `prepare_terminal_observation()` first;
`terminal_validator.prepare_terminal_observation()` writes `exit_code: 0`
before the terminal process. Q8 can consume pre-written process truth instead
of process-derived evidence, so terminal closure is not proven.

## Handoff decision

Keep spine `status: draft`. Resolve H1-H5 (and the associated atomic write and
resolver invocation requirements in AD-15) in a fresh implementation revision,
then rerun the complete Reviewer Gate. Do not finalize or hand off solely on
document lint/coherence.

