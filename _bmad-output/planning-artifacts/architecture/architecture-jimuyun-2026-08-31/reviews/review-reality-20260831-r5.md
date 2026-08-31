# Architecture Spine Reality / Brownfield Review — 2026-08-31 r5

Target: `ARCHITECTURE-SPINE.md` (feature-altitude build substrate)

## Verdict

**Needs revision before finalization.** The spine is internally explicit and its
mechanical lint passes, but the brownfield implementation still does not satisfy
the ownership, execution, lineage, or terminal truth invariants it declares.
These remain implementation handoff blockers; no CAP expansion is required.

## Findings

### H1 — Executor and independent judge are not separate writers

AD-4, AD-6, and AD-15 require the executor to persist the immutable process
receipt first, then a separately provisioned independent judge to consume that
receipt and write observation/classification. In the current plan,
`tools/artifact_owners.py:78-110` calls `process_executor.execute()`, constructs
both `receipt` and `observation`, invokes `validate_judge()` in the same process,
and writes `process-receipt.v1.json` with producer `independent-judge`.
`tools/process_executor.py:8-9` only returns `CompletedProcess`; it has no receipt
writer. `tools/independent_judge.py` is a validator, not a detached writer.
Consequently the advertised trust boundary is not executable and the candidate
can choose receipt normalization and judge identity in one authority.

**Required disposition:** add a named executor receipt writer that persists the
actual process result before loading a separately provisioned/read-only judge.
The judge must write observation and classification only after consuming the
immutable receipt; bind both identities and hashes before coverage accepts it.

### H2 — Current semantic and receipt outputs still use forbidden legacy fields

AD-5 and the data conventions reserve legacy fields for read-only compatibility.
`tools/semantic_oracle.py:185-188` emits `evidence_state: "observed"` in a
current semantic artifact, while `tools/independent_judge.py:30-45` requires
the aggregate `executions` field and `tools/artifact_owners.py:100-105` emits
that field in current process observations. Canonical consumers therefore must
either weaken the four-state/counter contract or silently rewrite current
evidence. The spine requires `observed-run` plus separated
`process_attempts`/`test_executions`/`cases` for current owners.

**Required disposition:** current writers emit only canonical evidence states and
separated counters. Keep `observed`/`executions` behind an explicit, versioned,
read-only compatibility projection that cannot write current evidence.

### H3 — Runtime assertion lineage is not enforced by active gates

AD-7, AD-8, and AD-15 require every runtime assertion edge to bind plan, slice,
candidate, run, observation/result, selector, target, fixture, case source,
producer, validator, hashes, and layered outcome/failure identity. The active
`tools/coverage_gate.py:7-23` checks only acceptance/case/observation IDs and a
`receipt.` assertion prefix; it does not validate the runtime-edge schema or
descriptor, receipt, observation, candidate, producer, or validator hashes.
`tools/slice_ready_predicate.py:14-54` checks only green/refactor exit codes,
successor/file presence, and artifact names; it has no RED observation, runtime
edge references, active-Acceptance exact cover, or dependency-closure check.
`tools/validate_all.py:139-237` validates terminal envelope fields but never
revalidates runtime assertion edges before completion.

**Required disposition:** make one canonical runtime-edge validator a mandatory
pre-gate. Q7 and Q8 must consume only validated edges and re-read all descriptor,
receipt, observation, selector, Acceptance, and current-candidate hashes.

### H4 — Registered lifecycle stages bypass the frozen descriptor/executor seam

AD-3, AD-8, AD-9, and AD-13 require process-bearing stages to execute the frozen
descriptor through one executor seam and one resolved repository cwd.
`tools/stage_command.py:48-80` rebuilds an absolute selector and runs
`python -m pytest` directly for GREEN/REFACTOR, then launches
`artifact_owners.py` separately. This is the registered lifecycle path, not a
diagnostic-only path; descriptor hash, timeout, selector identity, and producer
ownership can therefore be bypassed. Pytest runs with `cwd=repository_root`
(`:72`) while the owner runs with `cwd=repository_root.parent` (`:79`), despite
the registry declaring `cwd=.`. The command registry also has no RED command;
RED is generated in a separate adapter seam rather than sharing the same
descriptor/receipt/observation path.

**Required disposition:** route RED/GREEN/REFACTOR through one structured,
descriptor-bound executor and resolved repository-root cwd. If direct pytest
probes remain, register them explicitly as diagnostic-only and prevent their
outputs from satisfying lifecycle evidence; register/enforce one authoritative
RED entry point.

### H5 — S6 terminal observation is synthesized before terminal execution

AD-4, AD-7, and AD-15 require terminal evidence to follow a real process. The
S6 branch in `tools/stage_command.py:23-31` calls
`prepare_terminal_observation()` before invoking the owner. That function in
`tools/terminal_validator.py:14-68` validates input files and writes
`observations/terminal-observed.json` with `exit_code: 0`; it does not execute
the declared terminal selector. The later predicate therefore receives an
authoritative-looking success observation that is not process-derived.

**Required disposition:** make terminal preparation read/validate-only. Execute
the declared terminal descriptor through the executor first; then let the
observation writer record actual exit/output and hashes. Only after that may
terminal lineage and implementation-complete predicates run.

### M1 — Evidence persistence is not uniformly atomic create-if-absent

AD-6 and AD-13 require append-only atomic evidence. `tools/artifact_owners.py:22-26`
uses `Path.write_text()` and can overwrite an existing artifact. The terminal
and slice-ready predicates also write result files directly
(`tools/terminal_predicate.py:34-35`, `tools/slice_ready_predicate.py:67-68`).
The adapter's `stage_observation_runner.record_observation()` performs an
existence check followed by a separate write (`.agents/skills/quick-dev-tdd-adapter/tools/stage_observation_runner.py:153-157`),
leaving a race window.

**Required disposition:** centralize evidence persistence in an atomic
create-if-absent helper. Identical retries may be accepted idempotently; changed
bytes require a new run root and must never replace history.

### M2 — RED ownership is still split and not registry-enforced

AD-3, AD-8, AD-9, and AD-15 promise a single RED materialization/execution seam.
`tools/stage_command.py:17-19` accepts only `green|refactor|terminal`, while the
adapter's `build_slice_invocation.py:244-257` generates RED descriptors in a
separate path. The plan registry exposes only `s1..s6-{green,refactor,terminal}`
commands. This leaves two possible RED implementations and allows selector,
descriptor, and evidence ownership to diverge between Q3 and the registered
stage path.

**Required disposition:** either register and enforce an authoritative RED
entry point using the same descriptor/executor/observation chain, or explicitly
register a non-authoritative diagnostic RED command and make Q3 reject it.

## Brownfield / technology checklist

- Plan-local tools and adapter roots named by the spine exist.
- `py -3` and pytest are available, but the code paths above do not yet realize
  the declared trust boundaries.
- `process_executor.execute()` uses `shell=False`, but it does not persist a
  receipt and the registered lifecycle bypasses it for direct pytest execution.
- Run evidence is rooted under `logs/tdd-adapter/`; no finding requires changes
  to protected Phase service or live workspace trees.
- `lint_spine.py` returns `ok=true` with zero findings; this confirms document
  structure only and does not clear the implementation blockers.

## Gate recommendation

Resolve H1–H5 before changing the spine status to `final`; resolve M1–M2 in the
same revision or explicitly gate the affected lanes. Then rerun the complete
Reviewer Gate against a frozen new revision. No CAP-1…CAP-10 change is needed.

