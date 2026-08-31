# Architecture Spine Reality / Brownfield Review — 2026-08-31 r16

Target: latest working-tree `ARCHITECTURE-SPINE.md` and SPEC companions (base
commit `b3334eac60308ea2d8b381710a64d712cfc7d0ff`).

## Verdict

**BLOCKED.** No architecture or companion contract ambiguity was found. The
AD-15 matrix, AD-19 typed runtime closure, AD-20 typed snapshot/Git delta, and
AD-21 decision registry are explicit and mutually consistent. Existing legacy
implementation remains non-conformant; keep `status: draft` and block handoff.

## Findings

### H1 — Receipt and observation ownership remains combined (implementation)

`process_executor.py:8-9` does not persist receipts. `artifact_owners.py:78-109`
executes the SUT and writes receipt plus observation while calling the judge
validator; independent judge is not the sole observation/classification writer.

### H2 — Legacy `executions`/`observed` semantics remain authoritative (implementation)

`artifact_owners.py:104` emits aggregate `executions`, and
`independent_judge.py:30-44` validates it directly. Canonical evidence state and
separated process/test/case counters are not the active write contract.

### H3 — Runtime-edge typed closure/cardinality and hash re-read are not enforced (implementation)

`coverage_gate.py:7-22` checks only minimal acceptance/case/observation shape;
it does not enforce AD-19 tuple cardinality or complete descriptor/receipt/
observation/target/fixture/candidate/producer/validator/failure hash lineage.

### H4 — Q3/Q5/Q6 bypass a single descriptor/executor seam (implementation)

`stage_command.py` has no RED registry entry and directly runs pytest before a
separate owner subprocess for GREEN/REFACTOR. Selector, cwd, timeout and
producer identity can diverge from the frozen descriptor.

### H5 — Terminal success is written before terminal execution (implementation)

`stage_command.py:26-30` invokes `prepare_terminal_observation()` first;
`terminal_validator.py` writes `exit_code: 0` before a terminal process runs.
Q8 can therefore consume synthesized process truth rather than process-derived
evidence.

