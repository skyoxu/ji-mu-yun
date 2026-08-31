# Architecture Spine Reality / Brownfield Review — 2026-08-31 r2

Target: `ARCHITECTURE-SPINE.md` (feature-altitude build substrate)

## Verdict

**Needs revision before finalization.** The revised spine fixes the former root
directory ambiguity and explicitly names artifact roles, but the current
plan-local implementation still diverges from several of those invariants.
These are bounded brownfield convergence issues; no CAP expansion is required.

## Findings

### H1 — Receipt and observation writes remain combined in one owner

AD-4/AD-6 require the executor to be the sole process-receipt writer and the
independent judge to be the sole observation/classification writer. In the
current implementation, `process_executor.execute()` only returns a
`CompletedProcess` and writes no receipt. `artifact_owners.produce_receipt()`
then performs the process, constructs both `receipt` and `observation`, and
writes one `process-receipt.v1.json` record with `producer:
"independent-judge"` (`tools/artifact_owners.py:78-110`). Two implementers can
therefore disagree on receipt normalization and judge authority while still
appearing to satisfy the spine.

**Required disposition:** route process execution through a named executor
receipt writer, persist the immutable receipt there, and have the independent
judge consume that receipt and write only observation/classification. Make the
artifact graph and producer labels match those concrete writers; validators may
read but never rewrite either artifact.

### H2 — Current semantic owner emits non-canonical evidence state/counter

The spine's conventions and AD-5 prohibit current owners from writing legacy
`evidence_state=observed` or aggregate `executions`. Nevertheless,
`compile_run_local_semantic_artifacts()` emits verification cases with
`"evidence_state": "observed"` and later writes an observation containing
`"executions": 1` (`tools/semantic_oracle.py:185-188`,
`tools/artifact_owners.py:100-105`). This is on the S1 owner path, not a
read-only compatibility projection, so canonical lifecycle consumers either
must weaken AD-5 or silently rewrite the artifact.

**Required disposition:** emit `observed-run`/`planned-only` according to the
actual lifecycle and use `process_attempts`, `test_executions`, and `cases` in
all current artifacts. If historical fixtures need the old fields, isolate a
read-only compatibility adapter and mark its output non-authoritative.

### H3 — Runtime-edge lineage is not mechanically enforced by the active gate

AD-8 requires a runtime assertion edge to bind plan, slice, candidate, run,
observation/result, selector, target, fixture, case source, producer, and
validator identities. The plan-local `coverage_gate.validate_many_to_many_cover`
checks only `acceptance_id`, `case_id`, `observation_id`, and a string assertion
prefix (`tools/coverage_gate.py:7-22`). `semantic_oracle` delegates to this
module when present, so a minimally hand-authored edge can pass without the
hash and identity bindings mandated by AD-8.

**Required disposition:** add a named runtime-edge validator (or strengthen
the coverage gate) that rejects incomplete edge objects and verifies every
identity/hash against the immutable receipt, observation, descriptor and
current plan. State that coverage calculation consumes only edges that passed
this validator.

### H4 — Process-bearing stage still bypasses the descriptor/executor seam

AD-3 says process-bearing stages must delegate through the declared
descriptor/executor seam. `stage_command.py` directly runs `python -m pytest`
for GREEN/REFACTOR (`tools/stage_command.py:48-74`) and only invokes
`artifact_owners.py` afterward. This is not restricted to a diagnostic
namespace; it is the registered lifecycle path and can execute a selector
without descriptor-bound identity or timeout enforcement.

**Required disposition:** make the dispatcher pass the frozen descriptor to the
executor/owner for every process-bearing lifecycle stage. If a direct selector
is retained for diagnostic probes, put it behind an explicitly non-authoritative
command id and prevent it from writing or satisfying lifecycle evidence.

### M1 — Declared repository cwd differs from owner subprocess cwd

The brownfield rule binds all owner subprocesses to the resolved descriptor
repository root. In `stage_command.py`, pytest is launched with
`cwd=repository_root` while the artifact owner is launched with
`cwd=repository_root.parent` (`tools/stage_command.py:72-80`). The descriptor
contract declares cwd `.`. Relative imports, path containment and generated
artifact paths can therefore vary by stage.

**Required disposition:** use one resolved repository-root cwd for pytest,
owner, and descriptor execution, with an explicit containment check. If a
parent cwd is required by a wrapper, make it a named adapter boundary and
include it in descriptor identity.

### M2 — Terminal result does not carry the bindings required by AD-7

AD-7 requires terminal evaluation to bind the current plan, partition manifest,
slice-ready references, active Acceptance universe, and predicate identity. The
terminal predicate writes only status/predicate/slice/run/plan/producer fields
and hard-codes the plan id (`tools/terminal_predicate.py:27-37`). Although
`validate_all.py` checks several inputs, the emitted implementation-complete
result itself is not a content-addressed summary of those bindings, so another
consumer cannot verify which predicate inputs produced it without re-inference.

**Required disposition:** have the terminal result writer include immutable
references/hashes for the current contract/partition, every slice-ready result,
active Acceptance set and predicate/validator identity; derive plan id from the
loaded contract rather than a literal.

## Brownfield checklist

- Existing Python 3.12.10 and pytest 9.1.1 executables are available via
  `py -3`; plan-local and skill-owned roots in the Structural Seed exist.
- `subprocess.run(..., shell=False)` is used by the process executor, but the
  receipt-writer split, cwd uniformity, and edge validation above are not yet
  realized.
- Runtime evidence is kept under `logs/tdd-adapter/`; no protected Phase
  service tree needs modification for these findings.

## Gate recommendation

Resolve H1–H4 before marking the spine final. Resolve M1–M2 in the same
revision (or explicitly gate the affected execution/terminal lanes). Re-run the
full Reviewer Gate after the ownership, lineage, and cwd changes.

