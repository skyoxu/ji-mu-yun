# Architecture Spine Reality / Brownfield Review — 2026-08-31 r10

Target: frozen `ARCHITECTURE-SPINE.md` with AD-19/AD-20/AD-21 and the current
SPEC companions. Code baseline: `b3334eac60308ea2d8b381710a64d712cfc7d0ff`.

## Verdict

**BLOCKED.** The architecture text has no material AD-15 contract ambiguity:
the seven-row matrix explicitly names inputs, sole writers/evaluators and
rejection predicates, while AD-19/AD-20/AD-21 add typed runtime cardinality,
snapshot roots/Git delta, and stable decision identity. The blocker is
brownfield implementation drift from those decisions, not a missing
architecture rule.

## Findings

### H1 — Writer ownership remains non-conformant (implementation)

`tools/process_executor.py:8-9` returns only `CompletedProcess`. The active
`artifact_owners.py:78-109` executes the SUT and writes receipt plus observation
before/while invoking `validate_judge`; `independent_judge.py` is only a
validator. Executor-only receipt and judge-only observation/classification
writes required by AD-15(a), AD-4 and AD-6 are not implemented.

### H2 — Canonical evidence projection is not active (implementation)

`artifact_owners.py:104` and `independent_judge.py:30-44` still use aggregate
`executions` and legacy evidence semantics. The active writer path does not
produce the SPEC companion's canonical `evidence_state` and separated
`process_attempts`/`test_executions`/`cases`; AD-15(b) remains blocked.

### H3 — Runtime-edge validation is permissive (implementation)

`tools/coverage_gate.py:7-22` checks only a minimal acceptance/case/observation
shape. It does not require/re-read the AD-19 tuple fields or descriptor,
receipt, observation, target, fixture, candidate, producer, validator and
failure-identity hashes. A stale or hand-authored edge can still pass this
gate, blocking AD-15(c).

### H4 — Process stages bypass the frozen descriptor/executor seam (implementation)

`tools/stage_command.py:17-18` has no RED command; lines 43-72 invoke pytest
directly and line 79 invokes `artifact_owners.py` separately. The registered
Q3/Q5/Q6 path can therefore diverge in selector, cwd, timeout and producer
identity, contrary to AD-15(d) and the matrix's direct-path rejection rule.

### H5 — Terminal success is synthesized before process execution (implementation)

`stage_command.py:26-30` calls `prepare_terminal_observation()` first;
`terminal_validator.prepare_terminal_observation()` writes a successful
`exit_code: 0` observation before terminal execution. Q8 can consume this
pre-written process truth, so AD-15(e) and the AD-19 closure cardinality are
not proven.

