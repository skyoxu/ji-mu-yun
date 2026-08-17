# Quick Dev Phase Regression Repair Mode Execution Plan

## Status

- Plan ID: `quick-dev-phase-regression-repair-mode`
- VDD profile: `self-hosted`
- Lifecycle state: `plan-ready`
- Lifecycle owner: `vdd-execution-plan`
- Model route: `vdd.self_hosted`, `gpt-5.6-sol`, high effort, `observe_only`
- Implementation authorization=<redacted>
- Acceptance: external to this plan and Quick Dev

## Intent

Add a typed `regression_repair` mode to the strict Quick Dev TDD plan lane so
Phase service maintenance can repair a confirmed regression without weakening
RED identity, source investigation, protected-path, evidence, or acceptance
boundaries. The mode is not a free-form repair workflow and does not create a
new Quick Dev lane.

## Current Behavior Established From Source

- The parent router already selects `strict_tdd_plan`, but the adapter's Python
  entrypoints do not programmatically invoke that router before plan-state or
  evidence work.
- `adapter.transition()` accepts RED when the exit is nonzero and one caller
  supplied failure ID is present; it does not compare output with the plan's
  `expected_failure_ids` or `test_selector`.
- `stage_observation_runner.run()` captures command output in memory but
  intentionally discards stdout and stderr, so later consumers cannot prove
  which failure occurred.
- `build_slice_invocation.py` copies expected failure IDs into the stage-result
  core, while `run_slice_lifecycle.py` injects only exit code and timestamp.
- `route_plan_directory.py` can stop on a repeated fingerprint, but no failure
  path currently computes, persists, or increments that fingerprint.
- `stage_lifecycle_runner.py`, `stage_artifact_composer.py`,
  `loop_plan_directory.py`, and `persistent_plan_loop.py` are direct consumers
  of those observations and routing decisions.

These conclusions come from implementation and callsite reads, not function
names.

## Historical Error Check

The read-only historical scan found:

- many RED result files containing expected IDs;
- one current `run-state.v1.json` with `failure_fingerprint: null` and
  `repeat_count: 0`;
- a preserved `s7-lifecycle-r1-20260723/stderr.log` containing
  `RED command unexpectedly passed`;
- no persisted `repeated-failure-fingerprint` stop result in the scanned
  `logs/tdd-adapter/**` evidence.

Exact paths and hashes are frozen in `baseline-and-scope.v1.json`. Historical
matches explain prior behavior but authorize nothing and cannot replace a
current failing test.

## Bounded Related Closure

The complete closure for this change is bounded to:

- parent producer/router: `bmad-quick-dev/scripts/quick_dev_input_router.py`;
- Quick Dev contract schemas and adapter tools that create, consume, persist,
  and route RED observations and run state;
- direct consumers: lifecycle runner, artifact composer, plan router, bounded
  loop, and persistent loop;
- existing tests: parent router tests plus existing adapter, plan-loop, and
  Skill-contract test files;
- Phase standards and log-evidence architecture;
- external Acceptance ownership and the active plan-delivery-loop plan as a
  read-only compatibility consumer.

No Phase application, live runtime, workspace, metadata DB, auth, LLM entrypoint,
or protected host path is in this implementation write set.

## Decisions

1. `regression_repair` is a typed value inside `strict_tdd_plan`.
2. Missing mode remains backward-compatible and normalizes to `implementation`.
3. A referenced repair contract is validated by the parent router before the
   adapter may create evidence.
4. RED requires exact selector, expected IDs, typed failure class, and bounded
   diagnostic evidence in addition to nonzero exit.
5. Repair investigation fails closed until source implementation, at least one
   real callsite, consumers, tests, dependencies, historical log search, and an
   error-to-new-file-read map are current and hash-bound.
6. Existing test files win. A new test file needs a typed searched-and-absent
   result.
7. Phase repair scope carries targeted test/smoke command IDs and explicit
   protected-path disposition; this plan itself changes no protected Phase path.
8. Quick Dev may publish only `implementation-complete`; Acceptance owns
   `acceptance-passed`.

## Implementation Slices

### RMAP-S0 - Typed Contract And Parent Router

RED: the implementation predicate fails because the repair schema/helper and
normalized parent route do not exist.

GREEN: add the mode and repair-contract schemas, validation helper, normalized
router projection, mandatory caller handoff behavior, and cases in existing
router/adapter tests.

REFACTOR: run the existing parent router and adapter suites.

Recovery: remove only unadopted repair-mode files and restore legacy contracts
to normalized implementation behavior. Do not introduce a fallback lane.

### RMAP-S1 - RED Identity And Fingerprint

RED: the implementation predicate fails because output identity and failure
fingerprints are not observed.

GREEN: capture bounded diagnostics, classify failure type, verify selector and
IDs, compute the deterministic fingerprint, and update append-only failure
state.

REFACTOR: run existing adapter and parent-router suites, including wrong-ID,
wrong-selector, compile/harness, truncation, repeat, and reset cases.

Recovery: retain all failed observations and restore the last passing protocol;
never rewrite logs.

### RMAP-S2 - Investigation And Phase Safety

RED: the implementation predicate fails because evidence-bound investigation
and Phase route gates do not exist.

GREEN: enforce the bounded investigation contract, historical log sidecar,
new-file-per-error rule, existing-test priority, no-speculation gate, Phase
validation commands, and protected-path approval.

REFACTOR: run both existing Quick Dev suites, the adapter contract check, plan
validator tests, and the terminal implementation validator.

Recovery: disable repair routing, preserve failed investigation sidecars, and
leave lifecycle state short of implementation completion.

## Validation

Plan readiness:

```powershell
py -3 -B execution-plans/2026-08-06-quick-dev-phase-regression-repair-mode/tools/validate_plan.py
py -3 -B -m unittest discover -s execution-plans/2026-08-06-quick-dev-phase-regression-repair-mode/tools/tests -p test_*.py
```

Implementation RED or slice predicate:

```powershell
py -3 -B execution-plans/2026-08-06-quick-dev-phase-regression-repair-mode/tools/validate_implementation.py --slice RMAP-S0
```

Terminal implementation validation after explicit authorization and all slices:

```powershell
py -3 -B execution-plans/2026-08-06-quick-dev-phase-regression-repair-mode/tools/validate_implementation.py
```

The terminal command may publish only `implementation-complete`. It does not
publish acceptance, commit, release, or archive.

## Non-Goals

- No generic autonomous bug-fixing lane.
- No inference of behavior from function names or assistant summaries.
- No rewrite of historical logs, plan evidence, live DB, or hosted workspace.
- No change to Phase API, auth, DB, runtime, Caddy, or browser behavior.
- No modification of the active plan-delivery-loop plan or knowledge publication
  work.
- No Bootstrap launch or Acceptance decision in this plan.

## ADR

Implementation must add and accept
`docs/adr/ADR-0060-quick-dev-phase-regression-repair-mode.md`, update
`docs/architecture/ADR_INDEX_PHASE.md`, and cite ADR-0041 and ADR-0051 for
control-plane and repair re-entry ownership.
