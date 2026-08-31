# Architecture Spine Reality / Brownfield Review — 2026-08-31 r8

Target: `ARCHITECTURE-SPINE.md` at candidate `b3334eac60308ea2d8b381710a64d712cfc7d0ff`.

## Verdict

**BLOCKED before finalization and implementation handoff.** The spine states a
clear AD-15 brownfield gate and the newer AD-17/AD-18 invariants, but the
current plan-local implementation still fails the gate. This is a current-code
reality finding; it does not require changing CAP-1…CAP-10 or weakening the
architecture decisions.

## AD-15 conformance matrix

| Condition | Current evidence | Verdict |
| --- | --- | --- |
| (a) executor-only receipt and judge-only observation/classification writes | `tools/process_executor.py:8-9` only returns `CompletedProcess`; it has no receipt writer. `tools/artifact_owners.py:78-109` executes the process, constructs receipt and observation, calls `validate_judge`, and writes one combined `process-receipt.v1.json`. `independent_judge.py` only validates an already-combined pair. | **blocked** |
| (b) canonical four-state/separated counters | `artifact_owners.py:104` still emits aggregate `executions`; `independent_judge.py:30-44` validates that legacy field. The active writer path therefore does not emit the canonical separated `process_attempts`/`test_executions`/`cases` contract nor the canonical four-state projection. | **blocked** |
| (c) mandatory runtime-edge validation and hash re-read | `tools/coverage_gate.py:7-22` validates only acceptance/case/observation/assertion presence and a `receipt.*` prefix. It does not validate descriptor/receipt/observation/target/fixture/candidate/producer/validator hashes or failure identity. | **blocked** |
| (d) one frozen descriptor/executor seam for Q3/Q5/Q6 | `tools/stage_command.py:17-18` accepts only `green`, `refactor`, and `terminal`; no authoritative RED command is registered. Lines 43-72 derive a RED test path and invoke `python -m pytest` directly, then line 79 invokes `artifact_owners.py` in a separate process. This bypasses the descriptor/executor seam and permits selector/cwd divergence. | **blocked** |
| (e) terminal execution precedes terminal evidence and Q8 revalidates closure | `stage_command.py:26-30` calls `prepare_terminal_observation()` before the terminal owner. `terminal_validator.prepare_terminal_observation()` synthesizes `exit_code: 0` and writes `terminal-observed.json` before any terminal process. Q8 therefore starts from pre-written process truth. | **blocked** |
| (f) normalized contained paths and write-set enforcement | Some individual path checks exist, but active stage and owner writes use direct `Path.write_text()` (`artifact_owners.py:22-26`) and are not uniformly routed through one atomic create-if-absent writer. The descriptor seam is bypassed, so declared write sets/planned files are not enforced for every process-bearing path. | **blocked** |
| (g) versioned content-addressed current-snapshot resolver at Q0/Q4/Q7/Q8/recovery | `validate_all.py` computes local manifests, but the active dispatcher/owner path shown above does not invoke one versioned resolver at each required lifecycle boundary. Direct pytest/owner shortcuts can run without resolver revalidation; this does not prove the AD-17 invocation order or exact Git-delta roots. | **blocked** |

## Findings

### H1 — Combined process and semantic writer remains active

`artifact_owners.produce_receipt()` performs SUT execution and writes both
receipt and observation, with `judge_id` set in the same producer. A separately
provisioned judge never receives an immutable receipt as its sole input.

**Required disposition:** add an executor-owned immutable receipt writer that
persists the real process result first; make an independent judge consume only
that receipt and write observation/classification. Bind both identities and
hashes before runtime-edge admission.

### H2 — Legacy evidence fields are still authoritative on the active path

The active observation uses `executions`, and the judge validates that field
directly. Legacy `observed`/`executions` must be read-only compatibility
projections; current writers must emit `planned-only`/`observed-run` and the
separated counters.

### H3 — Runtime-edge gate is still permissive

The active coverage gate cannot reject an edge missing descriptor, receipt,
observation, target, fixture, candidate, producer, validator, or deterministic
failure identity hashes. A hand-authored minimal edge can still pass the local
shape check.

### H4 — Registered process stages still bypass the descriptor seam

The registry exposes only `s*-green`, `s*-refactor`, and `s*-terminal`; RED is
not a registry-owned descriptor. GREEN/REFACTOR directly run pytest and then a
separate owner subprocess, so selector, cwd, timeout and producer identity are
not mechanically frozen as one execution.

### H5 — Terminal evidence is synthesized before execution

`prepare_terminal_observation()` writes a successful terminal observation before
the terminal command runs. The terminal owner then publishes replay evidence
from that observation. This violates the AD-15 requirement that process-derived
evidence precede terminal publication and allows a pre-written pass to reach
Q8.

### M1 — Atomic append-only persistence is not universal

`artifact_owners._write()` uses `Path.write_text()` and can overwrite existing
evidence. Slice-ready and stage paths also write directly. A single atomic
create-if-absent primitive is not enforced across all evidence artifacts.

### M2 — RED ownership is not registry-enforced

RED is generated by adapter-side selectors while the registry has no RED command
entry. There is no single authoritative RED descriptor/executor/observation
chain that can be proven identical to GREEN/REFACTOR.

## Reality boundary

The repository-local Windows/Python/pytest substrate and explicit run-root
lineage files exist. Those facts are necessary but do not satisfy AD-15. The
spine must remain `status: draft` until a fresh conformance report marks every
AD-15 row `pass` against the current bytes.

## Gate recommendation

Resolve H1–H5 and M1–M2 in the implementation, then rerun the complete
Reviewer Gate on a fresh revision. Do not mark the spine `final` or hand it to
downstream implementation based on document lint/coherence alone.

