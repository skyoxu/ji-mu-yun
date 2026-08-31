# Architecture Spine Reality / Brownfield Review — 2026-08-31 r3

Target: `ARCHITECTURE-SPINE.md` (feature-altitude build substrate)

## Verdict

**Needs revision before finalization.** The spine states the intended ownership,
lineage, and Windows execution envelope clearly, but the current plan-local
implementation still violates several of those invariants. These are concrete
implementation seams, not missing product requirements; no CAP expansion is
needed. The prior r2 ownership/cwd findings remain open, and the current code
adds two terminal/slice-validation gaps.

## Findings

### H1 — Receipt and observation are still produced by one authority

AD-4/AD-6 require the executor to write the process receipt and the independent
judge to write observation/classification. `artifact_owners.produce_receipt()`
executes the SUT through `process_executor.execute()`, constructs the receipt
and observation, calls `validate_judge()` in the same process, and writes one
`process-receipt.v1.json` (`tools/artifact_owners.py:78-110`). The
`independent_judge.py` module is a value validator, not a detached judge. A
candidate can therefore supply the hard-coded `judge_id` and self-produced
observation while appearing to satisfy the graph.

**Required disposition:** make a named executor receipt writer persist an
immutable receipt first; provision a separately loaded/read-only judge that
consumes only that receipt and writes observation/classification. Bind the
judge identity and receipt/observation hashes before coverage accepts the edge.

### H2 — Current S1 owner still emits legacy evidence fields

AD-5 and the consistency conventions reserve legacy fields for read-only
compatibility. `compile_run_local_semantic_artifacts()` writes
`evidence_state: "observed"` and `artifact_owners.produce_receipt()` writes
aggregate `executions: 1` (`tools/semantic_oracle.py:185-188`,
`tools/artifact_owners.py:100-105`). These are current owner outputs, not a
compatibility projection, so canonical consumers must either weaken the spine
or silently rewrite them.

**Required disposition:** emit `planned-only`/`observed-run` and
`process_attempts`/`test_executions`/`cases` in current artifacts. Isolate old
fields behind an explicit, read-only versioned adapter.

### H3 — GREEN/REFACTOR bypass the descriptor/executor seam

AD-3, AD-8 and AD-9 require process-bearing stages to execute the frozen
descriptor through the executor seam and preserve selector identity. The
registered `stage_command.py` runs `python -m pytest` directly with a rebuilt
selector list (`tools/stage_command.py:43-49,72-74`) and only then invokes an
artifact owner. This path is not diagnostic-only, has no descriptor hash or
descriptor timeout binding, and can pass/fail independently of the registered
descriptor. The owner is launched with `cwd=repository_root.parent`
(`tools/stage_command.py:79`), while the descriptor declares repository cwd
`.`; this also violates AD-13 and can change relative path/import behavior.

**Required disposition:** dispatch RED/GREEN/REFACTOR through one resolved
repository-root cwd and the frozen descriptor/executor path. If a direct
pytest probe remains, give it a non-authoritative command id and prevent it
from writing or satisfying lifecycle evidence.

### H4 — Runtime-edge lineage is not enforced by the active slice/coverage gates

AD-8 and AD-7 require every runtime assertion edge to bind plan, slice,
candidate, run, observation/result, selector, target, fixture, case source,
producer and validator identities. `validate_slice_ready()` checks only green
and refactor exit codes, successor validity, planned files and artifact
presence (`tools/slice_ready_predicate.py:14-54`); it does not require a RED
observation, runtime-edge refs/hashes, active Acceptance exact cover, or
dependency closure. `validate_all.validate_terminal()` checks terminal evidence
and fixture summaries but never revalidates runtime assertion edges or executes
the terminal selector itself (`tools/validate_all.py:139-237`). A hand-authored
artifact set can therefore reach slice-ready/terminal without the complete
lineage promised by the spine.

**Required disposition:** add one canonical runtime-edge validator and make Q7
and Q8 consume only its validated edges. Re-read descriptor/receipt/observation
hashes, selector identity, active Acceptance set and current candidate before
writing slice-ready or implementation-complete.

### H5 — Terminal observation is recorded before terminal execution

AD-4/AD-7 require observed evidence to follow a real process and deterministic
terminal predicate. For S6, `stage_command.py` calls
`prepare_terminal_observation()` before invoking `artifact_owners.py`
(`tools/stage_command.py:23-31`). `prepare_terminal_observation()` writes
`observations/terminal-observed.json` with `exit_code: 0` after input checks;
it does not execute the terminal command (`tools/terminal_validator.py:14-68`).
The later predicate can fail, but the pre-created successful observation is
already an authoritative-looking process fact.

**Required disposition:** have the executor/terminal owner run the declared
terminal selector first and let the observation writer record its actual exit
and output. Keep input preparation as a non-observing validation step.

### M1 — Evidence writers are not uniformly atomic create-if-absent

AD-6/AD-13 require append-only, atomic evidence writes. The plan-local
`artifact_owners._write()` uses `Path.write_text()` and can overwrite an
existing artifact (`tools/artifact_owners.py:22-25`). The terminal and
slice-ready predicates likewise write result files directly
(`tools/terminal_predicate.py:34-35`, `tools/slice_ready_predicate.py:67-68`).
The stage observation writer performs an existence check followed by a separate
write, leaving a race window (`tools/stage_observation_runner.py:153-157`).

**Required disposition:** centralize evidence persistence on an atomic
create-if-absent helper; retries use a new run root and identical bytes are
idempotently accepted without replacement.

### M2 — RED entry seam is not explicit in the plan-local dispatcher

The architecture promises Q2/Q3 RED materialization and execution through the
same descriptor/executor model, but `stage_command.py` accepts only
`green|refactor|terminal` (`tools/stage_command.py:17-19`). RED is handled by a
separate adapter path, while the command registry exposes only stage-command
wrappers. This split is not documented as a deliberate boundary, so two
implementers can choose different RED ownership or bypass the frozen RED
descriptor.

**Required disposition:** document and enforce the single RED entry point
(including its descriptor, receipt and observation writer), or register a
distinct non-authoritative diagnostic command and ensure Q3 cannot route
through it.

## Brownfield checklist

- Windows `py -3`/pytest baseline and repository-contained `logs/tdd-adapter/`
  roots are present.
- `process_executor.execute()` uses `shell=False`, but receipt ownership,
  descriptor dispatch, terminal ordering, runtime-edge validation and atomic
  persistence are not yet aligned with the spine.
- Findings are confined to plan-local tooling and Quick Dev adapter seams; no
  Phase service or protected runtime tree requires modification for this review.

## Gate recommendation

Resolve H1–H5 before marking the spine final. Resolve M1–M2 in the same
revision (or explicitly gate the affected lanes), then rerun the full Reviewer
Gate with fresh brownfield and adversarial passes.
