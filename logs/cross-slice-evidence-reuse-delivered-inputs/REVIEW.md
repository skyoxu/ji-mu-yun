# Delivered-input boundary recheck

## Scope and minimal decision

The maintainer narrowed the task to VDD and Quick Dev TDD. BMAD output is an
already delivered input, not a workflow whose review status these consumers
must adjudicate. Original r40/738-case BMAD consumer eligibility is not a
success criterion for this repair. The earlier repair notes retain their
historical verification limits but do not define this narrowed scope.

Inspection found no upstream BMAD reviewer/report/approval gate or BMAD
regeneration call in the current source-index/V0A, Quick Dev Q1, or new shared
execution paths. Therefore no runtime implementation was changed.

Inspected ownership:

- scripts/vdd/compile_plan.py -> semantic_compiler_authority.py ->
  semantic_compiler.py build_source_index/source_preflight: source bytes,
  anchors, references and content identity; no BMAD review dependency.
- source_freeze.py -> canonical_package.py: typed package/selection references
  and content binding, not upstream reviewer status. No changes to that other
  skill or official BMAD were made.
- source_freeze.validate_repair_input and legacy route_plan_directory checks
  reference vdd-review-run and explicit VDD repair/authorization inputs. They
  are not upstream BMAD reviewer gates and were preserved.
- current_router/q1_planned_preflight, stage_pipeline/regression_gate,
  shared_execution and case/coverage readers: current VDD/execution contracts
  and original process proof, no upstream generation/reviewer invocation.
- VDD V4 source-to-output alignment and explicit user-requested stage-end
  external A/B are distinct from upstream BMAD review status. Neither was
  removed or executed.

Self-review chose documentation plus deterministic regression tests only.
No official BMAD code, other workflow, model route, runtime implementation,
original production directory or original unfinished requirements were changed.

## Exact changes

- Both SKILL.md files explicitly state direct delivered-input consumption,
  retained integrity/schema/reference checks, no upstream review/generation,
  and the separate user-requested external A/B boundary.
- VDD test_vdd_delivered_inputs.py exercises the actual public CLI in
  recommendation-only mode and V0A. A tiny delivered SPEC plus anchored
  companion needs neither BMAD installation nor a review report. Popen is
  prohibited. Missing/changed sources, missing required companion, invalid
  source reference, missing anchors and invalid UTF-8 remain rejected.
- Quick Dev test_quick_dev_delivered_inputs.py exercises Q1 and the existing
  controlled execution/reuse fixture. No upstream report is present. The
  fixture allows only Git and the owned pytest collector as subprocesses.
  One execution supplies a second slice/terminal reference; removing the
  explicitly bound delivered SPEC invalidates that reference. Q1 still
  rejects missing actual inputs and malformed argv.

## Validation

```sh
PATH=/tmp/evidence-reuse-venv/bin:$PATH python -m pytest -q \
 .agents/skills/vdd-execution-plan/scripts/tests/test_vdd_delivered_inputs.py \
 .agents/skills/quick-dev-tdd-adapter/tools/tests/test_quick_dev_delivered_inputs.py \
 .agents/skills/quick-dev-tdd-adapter/tools/tests/test_ch456_q1_planned_preflight.py \
 .agents/skills/quick-dev-tdd-adapter/tools/tests/test_skill_contract.py \
 .agents/skills/vdd-execution-plan/scripts/tests/test_validate_skill_contract.py
PATH=/tmp/evidence-reuse-venv/bin:$PATH python -B .agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py --skill-root .agents/skills/vdd-execution-plan
```

Results: 39 tests and 21 subtests passed in 4.29 seconds; VDD package checks
passed with no findings. See final-tests.txt and vdd-package.txt. The first
VDD test attempt exposed fixture assumptions (repository marker and anchor
shape), corrected in the tests only; its diagnostic output remains local.
No tests were disabled and no production gate was weakened.

## Limits and stop boundary

No real BMAD model, generator, reviewer or A/B was run. Full VDD semantic
compilation and original task acceptance were not claimed; the public input
entry was verified without launching workers. Prior Windows/host integration
limits remain unchanged. The original r40 expensive suite is not a delivery
goal. This follow-up has no new execution blocker. Keep this on the independent
repair branch; do not integrate, push, create a PR or resume production.
