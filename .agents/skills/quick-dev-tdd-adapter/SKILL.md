---
name: quick-dev-tdd-adapter
description: Implement or resume an explicit VDD execution plan through real RED, bounded GREEN, REFACTOR, deterministic slice-ready coverage, and whole-plan terminal validation. Chapter 4/5/6 plans use the current staged runtime pipeline; historical implementation-contract.v1 plans are compatibility inputs only.
---

# Repository Maintenance TDD Adapter

Use this Skill only for an explicit plan file or plan directory routed to `strict_tdd_plan`. It is implementation authority for the TDD lifecycle only; it is not review, acceptance, commit, PR, release, or archive authority.

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

## Current Required Order

1. Q0 recommendation-only: validate the semantic plan, current snapshot, explicit predecessors and change-impact state without running tests or writing run state.
2. Q1 preflight: validate plan/slice/candidate identity, environment probe, selector/target/fixture/cwd/argv/timeout, write sets and predecessor state.
3. Q2 RED materialization: create a frozen shell-free descriptor from VDD intent. A RED author may touch only the declared test write set and must bind a real production entry.
4. Q3 RED: dispatch the frozen descriptor through `tools/stage_pipeline.py`. `process_executor_v2.py` writes process facts; `independent_judge_v2.py` classifies those facts; runtime-edge code writes only assertion edges.
5. Q4 implementation: only a current expected-red authorizes an implementation-worker handoff. Exact changed paths must stay inside production write paths; selector/test/fixture/plan/evidence changes invalidate RED. The worker never writes evidence authority.
6. Q5 GREEN: before execution, re-read the explicit frozen RED descriptor and RED stage result; require their bound hash and selector identity to match. Then execute the same selector identity/target/fixture/assertion/cwd contract and require real nonzero test/case evidence with exit zero.
7. Q6 REFACTOR: require the same frozen RED predecessor binding plus current GREEN, allow only production paths, rerun the same selector, then apply `tools/regression_gate.py`. `standard` and `self-hosted` must consume the slice `agent-context.validation_commands`; missing context, an empty required command set, timeout, nonzero exit, or zero-case pytest regression blocks publication before REFACTOR runtime edges/stage result. `fast-ship` may omit extra regressions but never the primary selector truth floor.
8. Q7 slice-ready: `tools/coverage_predicates.py` re-reads RED/GREEN/REFACTOR edge -> observation -> receipt -> descriptor -> target/fixture bytes and proves exact Acceptance assertion coverage.
9. Execute the terminal descriptor through `tools/stage_pipeline.py`; terminal may have its own selector identity and process success alone is not completion.
10. Q8 whole-plan terminal: `tools/coverage_predicates.py` verifies one explicit hash-bound predecessor per slice, exact `(slice, Acceptance, stage)` tuple closure, terminal assertions and a freshly recomputed current snapshot before writing `implementation-complete`.

Stop at `implementation-complete`, `repair-vdd`, `environment-blocked`, or repeated deterministic failure. Never publish `acceptance-passed` here.

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

## Snapshot, Invalidation And Recovery

The current snapshot resolver owns exactly eight runtime root kinds: `candidate_tree`, `plan`, `contract`, `descriptor`, `fixture`, `source`, `validator_judge`, `plan_state_transition`. Governance artifacts are excluded unless explicitly adopted by a product/execution dependency.

Use the versioned change-impact resolver for Q0/Q4/Q7/Q8/recovery. Selector/fixture/target/source changes restart at RED; production-owner changes rerun at least GREEN/REFACTOR and restart RED when failure semantics changed; compiler/validator/judge/predecessor changes invalidate their descendants. A recovered run must name an explicit prior run and re-read its receipt, observation and runtime edges with current hashes; it may not scan history.

## Failure And Stop-Loss

Current classification must distinguish at least: `semantic-contract-gap`, `expected-red`, `unexpected-green`, `task-implementation-failure`, `test-harness-failure`, `target-binding-failure`, `repo-noise`, `timeout-no-observation`, `repeated-deterministic-failure`, and `artifact-integrity`.

A successful lifecycle stage requires real observed execution and nonzero test/case counts. Test/case counts come from the executor's recognized test-runner summary, never from arbitrary SUT markers. Timeout, harness, repo-noise, zero-case, wrong target, unexpected-green and artifact-integrity failures cannot satisfy RED or completion. Deterministic failure fingerprints exclude timestamp/run-duration/output-byte noise; the same fingerprint twice routes `repair-vdd` or `stop`. Rerun is legal only after relevant input changes.

## Profiles

Execution profiles are `fast-ship`, `standard`, and `self-hosted`. Profiles may change scope/cost only; none may bypass real execution, selector identity, exact cover, failure classification, current snapshot or terminal truth. `self-hosted` additionally requires the detached promotion/judge contract when promotion is requested. Its detached bundle must contain external read-only `positive`, `negative`, and `mutation` fixture kinds and must exactly cover every current failure family; missing/unknown family coverage, candidate-local judge/oracle bytes, mutable artifacts, or current evidence-writer imports block promotion. This execution profile is distinct from any older VDD plan-shape profile such as `resumable`.

## Implementation Backend Boundary

The implementation worker may change only declared production paths after expected RED. It must not modify selector, fixture, Acceptance, plan contract, historical evidence or terminal predicate to manufacture GREEN. Model/backend text is never evidence authority.

## Legacy Compatibility

Historical v1 plans are read-only compatibility inputs. `tools/legacy_compat.py` may report reusable identities or required current projection, but legacy combined receipt/observation fields, aggregate execution counters and plan-local terminal status cannot directly become current v2 evidence or completion authority. `scripts/quick_dev/replay_legacy_tdd.py` is a regression harness only: it may prove a historical RED baseline and current GREEN with the same declared selector/failure identities, but it never authorizes current evidence.

Legacy compatibility tests may load their explicitly named historical fixtures, Bootstrap helpers, or Acceptance helpers. Those dependencies remain test/replay inputs only; their existence never promotes a legacy loop, governance receipt, historical success, or acceptance route into current runtime authority.

## Boundaries

- Use argv arrays with `shell=false`; reject raw shell commands.
- Keep cwd and all paths repository-contained and POSIX-normalized in contracts.
- Preserve same selector semantics through RED -> GREEN -> REFACTOR and bind GREEN/REFACTOR to the frozen RED predecessor.
- Never let SUT/backend/model text write or authorize evidence.
- Never let governance bytes become runtime truth by default.
- Never use artifact existence or plan status strings as completion proof.
- Never invoke Stock BMAD Quick Dev as authoritative fallback after strict routing.
