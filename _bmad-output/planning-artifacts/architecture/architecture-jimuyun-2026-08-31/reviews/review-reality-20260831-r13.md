# Architecture Spine Reality / Brownfield Review — 2026-08-31 r13

Target: latest `ARCHITECTURE-SPINE.md` plus SPEC companions; code baseline
`b3334eac60308ea2d8b381710a64d712cfc7d0ff`.

## Verdict

**BLOCKED.** The schema-companion additions do not introduce a material
architecture contradiction. AD-15's matrix remains an explicit handoff gate,
and AD-19 (typed runtime closure), AD-20 (typed snapshot roots/Git delta), and
AD-21 (stable decision registry) are mutually consistent. The active brownfield
implementation still has not migrated to these contracts, so the spine must
remain `status: draft`.

The phrase “active V6A tuple universe” is interpreted as the tuple set declared
by V6A (not a Cartesian product of every slice and every Acceptance); this is
consistent with the matrix's per-slice Acceptance paths. Implementers should
retain that interpretation when encoding the validator.

## Findings

### H1 — Executor/judge writer split is still absent (implementation)

`execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/process_executor.py:8-9`
returns only a process result. `artifact_owners.py:78-109` executes the SUT,
constructs receipt and observation, invokes the judge validator, and writes a
combined artifact. The independent judge is therefore not the sole
observation/classification writer required by AD-15(a).

### H2 — Legacy evidence fields remain active (implementation)

`artifact_owners.py:104` emits aggregate `executions`, and
`independent_judge.py:30-44` validates it directly. Current writers do not
emit canonical `evidence_state` with separated
`process_attempts`/`test_executions`/`cases`; the compatibility projection is
not isolated read-only, blocking AD-15(b).

### H3 — Runtime-edge typed closure and hash re-read are not enforced (implementation)

`coverage_gate.py:7-22` checks only acceptance/case/observation/assertion
shape. It does not enforce AD-19 tuple cardinality or re-read descriptor,
receipt, observation, target, fixture, candidate, producer, validator and
failure-identity hashes before admission, so stale/minimal edges can pass.

### H4 — Registered lifecycle stages still bypass the descriptor/executor seam (implementation)

`stage_command.py:17-18` exposes no RED command. GREEN/REFACTOR derive and run
pytest directly, then invoke `artifact_owners.py` as a second process. Selector,
cwd, timeout and producer identity are not mechanically frozen as one
descriptor-bound execution, violating AD-15(d).

### H5 — Terminal process truth is synthesized before execution (implementation)

`stage_command.py:26-30` calls `prepare_terminal_observation()` first;
`terminal_validator.py:14-68` writes a successful `exit_code: 0` observation
before terminal process execution. Q8 can therefore consume pre-written success
instead of process-derived evidence, violating AD-15(e).

## Handoff decision

Resolve H1-H5 and the associated AD-15 atomic-write and resolver-invocation
rows in implementation, then rerun the complete Reviewer Gate against a fresh
revision. Do not finalize or hand off based on schema/lint/coherence alone.

