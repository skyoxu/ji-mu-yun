# Architecture Spine Reality / Brownfield Review — 2026-08-31 r7

Target: `ARCHITECTURE-SPINE.md` (feature-altitude build substrate)

## Verdict

**Blocked before finalization and implementation handoff.** The spine and its
normative companions describe the intended AD-15 trust, ownership, lineage,
and terminal invariants, but the current plan-local implementation still
violates those invariants. This is a brownfield reality finding, not a request
to expand CAP-1…CAP-10 or alter the architecture spine.

## AD-15 conformance matrix

| Condition | Current reality | Verdict |
| --- | --- | --- |
| (a) executor-only receipt and judge-only observation/classification writes | `tools/artifact_owners.py:78-110` executes the process, constructs receipt and observation, invokes `validate_judge`, and writes one combined `process-receipt.v1.json`; `tools/process_executor.py:8-9` has no receipt writer | **blocked** |
| (b) canonical four-state/separated counters | `tools/artifact_owners.py:104` emits aggregate `executions`; `tools/semantic_oracle.py:185-188` emits legacy `evidence_state: observed` on the current path; `tools/independent_judge.py:30-44` validates the legacy counter | **blocked** |
| (c) mandatory runtime-edge validation and hash re-read | `tools/coverage_gate.py:7-22` checks only a small acceptance/case/observation/assertion subset; it does not validate descriptor, receipt, observation, target, fixture, candidate, producer, validator, or hash bindings. `tools/slice_ready_predicate.py:14-54` does not require RED observation, runtime edges, active-A exact cover, or dependency closure | **blocked** |
| (d) one frozen descriptor/executor seam for Q3/Q5/Q6 | `tools/stage_command.py:48-79` directly runs `python -m pytest`, then launches `artifact_owners.py`; registry has no RED entry and owner/pytest paths use different cwd roots (`:72` vs `:79`) | **blocked** |
| (e) terminal execution precedes terminal evidence and Q8 revalidates closure | `tools/stage_command.py:27-30` calls `prepare_terminal_observation()` before any terminal process. `tools/terminal_validator.py:14-68` writes a successful terminal observation without executing the declared selector; Q8 validation therefore starts from synthesized process truth | **blocked** |
| (f) normalized contained paths and write-set enforcement | Some path checks exist in terminal/replay helpers, but active stage/owner writes are not uniformly routed through one atomic writer or one resolved cwd; the descriptor seam is bypassed, so the declared write-set and containment rule is not proven for every process-bearing path | **blocked** |
| (g) versioned content-addressed current-snapshot resolver invoked at Q0/Q4/Q7/Q8/recovery | `tools/validate_all.py:16-46` computes a Git status/index summary and a broad filesystem manifest; there is no demonstrated single resolver invocation at each required lifecycle boundary, and direct stage paths bypass it | **blocked** |

## Findings

### H1 — Receipt and observation remain a combined writer

`artifact_owners.produce_receipt()` performs the SUT process and creates both
receipt and observation in one authority, with a hard-coded `judge_id`.
`independent_judge.py` is only an in-process validator. The executor therefore
does not persist an immutable receipt before the judge consumes it, and the
candidate can still control receipt normalization and classification together.

**Required disposition:** add a named executor receipt writer that persists the
actual process result first; load a separately provisioned/read-only judge that
consumes only that receipt and writes observation/classification. Bind both
identities and hashes before coverage accepts an edge.

### H2 — Current owners still emit legacy evidence fields

The current S1 semantic writer emits `evidence_state: "observed"`, and the
receipt path emits/validates aggregate `executions`. These are not isolated
read-only compatibility projections, so canonical consumers must either weaken
AD-5 or silently rewrite current evidence.

**Required disposition:** current writers emit only `planned-only`/`observed-run`
and `process_attempts`/`test_executions`/`cases`; keep legacy values behind a
versioned, read-only, non-authoritative projection.

### H3 — Runtime assertion lineage is not an active gate

The active coverage gate admits minimally shaped edges and does not verify the
runtime-edge schema or immutable hashes. Slice-ready checks only stage exits,
successor presence, and artifact names. A hand-authored or stale edge can
therefore reach terminal validation without descriptor/receipt/observation,
candidate, Acceptance, producer, validator, and failure identity closure.

**Required disposition:** make one canonical runtime-edge validator mandatory
before Q7 and Q8; re-read all descriptor, receipt, observation, selector,
Acceptance, plan/slice/candidate/run and dependency hashes immediately before
coverage and terminal publication.

### H4 — Registered process stages bypass the descriptor/executor seam

GREEN/REFACTOR execute an absolute pytest selector directly and then invoke the
owner in a separate subprocess. The registry has no authoritative RED command,
and the two subprocesses use different cwd roots. This is the registered
lifecycle path, not a diagnostic-only path, so descriptor identity, timeout,
selector identity, and producer ownership can diverge.

**Required disposition:** route RED/GREEN/REFACTOR through one structured,
descriptor-bound executor and resolved repository-root cwd. Any direct probe
must have an explicit non-authoritative diagnostic command ID and its outputs
must be rejected by lifecycle gates.

### H5 — Terminal observation is synthesized before terminal execution

`prepare_terminal_observation()` writes `observations/terminal-observed.json`
with `exit_code: 0` after validating files and lineage, before `s6-terminal`
executes anything. The terminal predicate consequently receives
authoritative-looking success that is not process-derived.

**Required disposition:** terminal preparation is read/validate-only. Execute
the declared terminal descriptor through the executor first; then have the
observation writer record actual process output, exit, and hashes before
terminal lineage and implementation-complete predicates run.

### M1 — Evidence persistence is not uniformly atomic create-if-absent

`artifact_owners.py:22-26` uses `Path.write_text()` and may overwrite existing
artifacts. `terminal_predicate.py:34-35` and `slice_ready_predicate.py:67-68`
also write directly. The adapter observation runner uses a separate existence
check and write, leaving a race window. Append-only evidence and idempotent
retries are therefore not guaranteed by one persistence primitive.

**Required disposition:** centralize evidence persistence in an atomic
create-if-absent helper. Identical retries may be idempotent; changed bytes
must require a new RUN-* root and never replace history.

### M2 — RED ownership is split and not registry-enforced

`stage_command.py:17-19` accepts only GREEN/REFACTOR/terminal. RED descriptors
are generated by a separate adapter path (`build_slice_invocation.py`), while
the plan registry exposes only `s*-{green,refactor,terminal}` commands. Two
RED implementations can consequently diverge in selector, descriptor, and
evidence ownership.

**Required disposition:** register and enforce one authoritative RED entry point
using the same descriptor/executor/observation chain, or explicitly register a
diagnostic-only RED command and make Q3 reject it as lifecycle evidence.

## Reality boundary

The plan-local roots, Python 3.12.10, pytest 9.1.1, shell-free
`process_executor.execute()`, and logs/tdd-adapter evidence location exist.
Those facts show that the brownfield substrate is present; they do not prove
the AD-15 handoff gate. The current spine status must remain `draft` until a
fresh conformance run records every AD-15 row as `pass`.

## Gate recommendation

Resolve H1–H5 and M1–M2 in the implementation, then run the complete Reviewer
Gate against a fresh revision. Do not mark the spine `final` or hand off to
downstream implementation on the basis of lint or document coherence alone.
