---
name: quick-dev-tdd-adapter
description: Implement or resume an explicit VDD execution plan through real RED, bounded GREEN, REFACTOR, deterministic slice-ready coverage, and whole-plan terminal validation. Chapter 4/5/6 plans use the current staged runtime pipeline; historical implementation-contract.v1 plans are compatibility inputs only.
---

# Repository Maintenance TDD Adapter

Use this Skill only for an explicit plan file or plan directory routed to `strict_tdd_plan`. It is implementation authority for the TDD lifecycle only; it is not review, acceptance, commit, PR, release, or archive authority.

## Read By Operation

Read only the guide selected by the actual input and operation. On a transition from inspection/recovery to execution, load the execution guide before starting a stage.

| Operation | Required guidance |
| --- | --- |
| Current plan preflight, recommendation or execution | [Execution](references/execution-operation.md); recommendation-only remains side-effect free |
| Existing stage, failed attempt or explicit recovery | [Recovery](references/recovery-operation.md), then execution guidance for the selected next stage |
| Historical v1 input or explicitly adopted Skill-input route | [Compatibility](references/compatibility-operation.md); never use legacy evidence as current completion authority |
| Skill maintenance | Affected guides and their existing contract tests; no live run by default |

## Current And Legacy Plan Routes

| Input | Route | Runtime authority |
| --- | --- | --- |
| `vdd.semantic-plan-bundle.v1` / Chapter 4/5/6 current plan | current | stable `scripts/quick_dev/run.py` -> `tools/stable_runner.py`; predicates in `current_router.py`, execution in `stage_pipeline.py`, Q6 regression in `regression_gate.py`, coverage in `coverage_predicates.py` |
| historical `implementation-contract.v1.json` without the current semantic bundle | compatibility | `tools/legacy_compat.py` may inspect/project/route repair only |
| standalone requirements or missing contract | reject | none |

Current plans must never use `loop_plan_directory.py`, `run_slice_lifecycle.py`, `stage_command.py`, plan-local combined writers, `current_lifecycle.py`, `canonical_lifecycle.py`, or `evidence_pipeline.py` as completion authority.

The current stable entry is:

```text
py -3 scripts/quick_dev/run.py --plan <plan-dir> --slice <slice-id> --profile standard
py -3 scripts/quick_dev/run.py --plan <plan-dir> --slice <slice-id> --recommendation-only
```

The stable CLI defaults to deterministic Q1 preflight. `--recommendation-only` is strict Q0 and must not run tests, create a run, call a model, or write state. Advanced deterministic actions are exposed through `--action execute-stage|implementation-handoff|slice-ready|implementation-complete|recover`; model-backed RED authoring and production implementation remain agent/worker actions outside the evidence writers.

## Evidence Ownership

| Artifact | Sole current writer |
| --- | --- |
| descriptor/run orchestration/recommendation/recovery | Quick Dev stable runner/current router |
| process receipt/stdout/stderr facts | `process_executor_v2.py` |
| observation/classification | `independent_judge_v2.py` |
| Q6 regression receipt | `regression_gate.py` |
| runtime assertion edge | runtime-edge validator |
| slice-ready | Q7 coverage predicate |
| implementation-complete | Q8 terminal predicate |
| acceptance-passed | external Acceptance Skill |

All current evidence writes are immutable create-if-absent and reference explicit predecessors. Never infer current authority from glob, mtime, filename ordering or "latest success" scans.

## Failure And Stop-Loss

Current classification must distinguish at least: `semantic-contract-gap`, `expected-red`, `unexpected-green`, `task-implementation-failure`, `test-harness-failure`, `target-binding-failure`, `repo-noise`, `timeout-no-observation`, `repeated-deterministic-failure`, and `artifact-integrity`.

A successful lifecycle stage requires real observed execution and nonzero test/case counts. Current case counts come from structured pytest call events, never from a summary or arbitrary SUT markers. Counts alone do not authorize an assertion edge. Timeout, harness, repo-noise, zero-case, wrong target, unexpected-green and artifact-integrity failures cannot satisfy RED or completion. Deterministic failure fingerprints exclude timestamp/run-duration/output-byte noise; the same fingerprint twice routes `repair-vdd` or `stop`. Rerun is legal only after relevant input changes.

## Implementation Backend Boundary

The implementation worker may change only declared production paths after expected RED. It must not modify selector, fixture, Acceptance, plan contract, historical evidence or terminal predicate to manufacture GREEN. Model/backend text is never evidence authority.

## Boundaries

- Use argv arrays with `shell=false`; reject raw shell commands.
- Keep cwd and all paths repository-contained and POSIX-normalized in contracts.
- Preserve same selector semantics through RED -> GREEN -> REFACTOR and bind GREEN/REFACTOR to the frozen RED predecessor.
- Never let SUT/backend/model text write or authorize evidence.
- Never let governance bytes become runtime truth by default.
- Never use artifact existence or plan status strings as completion proof.
- Never invoke Stock BMAD Quick Dev as authoritative fallback after strict routing.


Before any stage reentry, consult the recovery guide. Matching completed evidence is reused, including failures; stale or partial evidence blocks. Preserve explicit failure history: two matching prior failures block a third attempt. Never scan for a latest run.

Completion remains Q7 exact case/assertion coverage plus Q8 whole-plan terminal proof. Hand the native Q8 result and snapshot inputs to Acceptance; only Acceptance may publish `acceptance-passed`.

## Current Runtime Boundaries

Historical v1 plans are read-only compatibility inputs. The legacy combined receipt/observation fields cannot become current completion authority. The historical replay harness never authorizes current evidence. Read the compatibility guide only when handling those inputs.

Q6 uses `tools/regression_gate.py`. `standard` and `self-hosted` must consume the slice `agent-context.validation_commands`; missing context, an empty required command set, timeout, nonzero exit, or zero-case pytest regression blocks publication before REFACTOR runtime edges/stage result. `fast-ship` may omit extra regressions but never the primary selector truth floor. Read the execution guide before running stages.
