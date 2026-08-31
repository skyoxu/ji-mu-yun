# Architecture Spine Reality / Brownfield Review — 2026-08-31 r4

Target: `ARCHITECTURE-SPINE.md` (feature-altitude build substrate)

## Verdict

**Needs revision before finalization.** The spine is structurally coherent and
the repository roots are now named accurately, but the plan-local implementation
still violates several of its own ownership, lineage, and execution invariants.
These are bounded brownfield convergence blockers; no CAP expansion is needed.

## Findings

### H1 — Receipt and observation remain one-owner, one-write operation

AD-4/AD-6 require the executor to be the sole writer of an immutable process
receipt and the independent judge to be the sole writer of observation and
classification. `tools/artifact_owners.py:78-110` calls `process_executor.execute()`,
constructs both `receipt` and `observation`, invokes `validate_judge()` in the
same process, and writes `process-receipt.v1.json` with producer
`independent-judge`. `process_executor.execute()` only returns
`CompletedProcess` and has no receipt writer. The advertised trust boundary is
therefore not executable: a candidate can choose receipt normalization and
judge labels in one authority.

**Required disposition:** add a named executor receipt writer that persists the
actual process result first; load a separately provisioned/read-only judge that
consumes only that receipt and writes observation/classification. Bind both
identities and hashes before coverage accepts an edge.

### H2 — Current S1 output still emits forbidden legacy evidence fields

AD-5 and the data conventions reserve legacy values for read-only compatibility.
`tools/semantic_oracle.py:185-188` emits `evidence_state: "observed"` in
current semantic artifacts, and `tools/artifact_owners.py:100-105` emits the
aggregate `executions` field. These are current owner outputs rather than an
isolated compatibility projection, so canonical consumers must weaken the
four-state/counter contract or silently rewrite evidence.

**Required disposition:** emit only `planned-only`/`observed-run` (as applicable)
and `process_attempts`/`test_executions`/`cases` from current owners. Keep old
fields behind an explicit, versioned, read-only adapter and mark its projection
non-authoritative.

### H3 — Runtime-edge and coverage gates do not enforce the spine's full lineage

AD-8 and AD-7 require every `runtime_assertion_edge` to bind plan, slice,
candidate, run, observation/result, selector, target, fixture, case source,
producer, validator, and all relevant hashes. The active fallback in
`tools/coverage_gate.py:7-22` checks only `acceptance_id`, `case_id`,
`observation_id`, and a receipt assertion prefix; it does not validate the
runtime edge schema or any descriptor/receipt/observation/current-candidate
hashes. `tools/slice_ready_predicate.py:14-54` checks stage exit codes,
successor and file presence but does not require RED observation, edge refs,
active Acceptance exact cover, or dependency closure. `tools/validate_all.py:139-237`
validates terminal envelope fields but does not revalidate runtime edges before
terminal completion.

**Required disposition:** make one canonical runtime-edge validator the mandatory
pre-gate. Q7 and Q8 must consume only edges that pass it and must re-read all
descriptor, receipt, observation, selector, Acceptance, and candidate hashes.

### H4 — Registered process stages still bypass the descriptor/executor seam

AD-3/AD-8/AD-9 require process-bearing stages to execute the frozen descriptor
through one executor seam. `tools/stage_command.py:48-80` reconstructs an
absolute RED selector and runs `python -m pytest` directly for GREEN/REFACTOR,
then invokes `artifact_owners.py` separately. This is the registered lifecycle
path, not a diagnostic-only command, so timeout, cwd, descriptor hash, and
selector identity can be bypassed. The owner subprocess uses
`cwd=repository_root.parent` (`stage_command.py:79`), while pytest uses
`cwd=repository_root` (`:72`) and the registry declares `cwd=.`.

**Required disposition:** pass the frozen descriptor to the executor/owner for
every process-bearing RED/GREEN/REFACTOR action, using one resolved repository
root and an explicit containment check. If direct pytest probes remain, give
them a non-authoritative diagnostic command id and prevent them from writing or
satisfying lifecycle evidence.

### H5 — Terminal observation is pre-written without executing the terminal

AD-4/AD-7 require observed terminal evidence to follow a real process. The S6
path in `tools/stage_command.py:23-31` calls
`prepare_terminal_observation()` before invoking the owner. That function in
`tools/terminal_validator.py:14-68` writes `observations/terminal-observed.json`
with `exit_code: 0` after validating input files; it does not execute the
declared terminal selector. The subsequent predicate therefore receives an
authoritative-looking success observation that was not produced by a process.

**Required disposition:** make terminal preparation read/validate-only. Execute
the declared terminal descriptor through the executor, then let the observation
writer record its actual exit/output and hashes. Only after that may terminal
lineage and implementation-complete predicates run.

### M1 — Evidence writes are overwrite-prone rather than atomic create-if-absent

AD-6/AD-13 require append-only evidence. `tools/artifact_owners.py:22-26`
uses `Path.write_text()` and overwrites existing artifacts. Terminal and
slice-ready predicates also write result files directly, and the skill-owned
stage observation runner performs an existence check followed by a separate
write (`.agents/skills/quick-dev-tdd-adapter/tools/stage_observation_runner.py`),
leaving a race window.

**Required disposition:** centralize evidence persistence in an atomic
create-if-absent helper. Identical retries may be idempotently accepted; changed
bytes must require a new run root and never replace history.

### M2 — RED entry ownership is split but not registered as a deliberate seam

The spine promises Q2/Q3 descriptor materialization and execution, while the
plan registry exposes only `s1..s6-{green,refactor,terminal}` commands and
`stage_command.py` rejects `--stage red` (`:17-19`). RED is handled by a
different adapter path without a registry-level binding to its descriptor,
receipt writer, and observation writer. Two implementations can therefore
choose different RED ownership or bypass selector identity.

**Required disposition:** register and enforce one authoritative RED entry point
with the same descriptor/executor/observation chain, or explicitly register a
non-authoritative diagnostic RED command and prohibit Q3 routing through it.

## Brownfield / technology checklist

- Repository roots used by the spine exist: plan-local tools under
  `execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/` and
  skill-owned adapter tools under `.agents/skills/quick-dev-tdd-adapter/tools/`.
- `py -3` is available as Python 3.12.10 and pytest 9.1.1 is installed; the
  declared Windows baseline is therefore reproducible.
- `process_executor.execute()` uses `shell=False`, but it does not persist a
  receipt, and the registered stage path bypasses it for ordinary pytest runs.
- Run evidence is placed beneath `logs/tdd-adapter/`; no finding requires
  modifying protected Phase service or live workspace trees.
- The architecture linter passes (`ok=true`, zero findings), which confirms
  document structure only and does not clear the implementation blockers above.

## Gate recommendation

Resolve H1–H5 before changing the spine status to `final`; resolve M1–M2 in the
same revision (or explicitly gate the affected lanes). Then rerun the complete
Reviewer Gate with fresh adversarial and brownfield passes. No CAP-1…CAP-10
change is required.

