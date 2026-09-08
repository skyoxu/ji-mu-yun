# Windows Validation

Use a clean checkout of `implementation/acceptance-current-closeout`. Run the
two groups below separately to keep legacy Python module names isolated.
No live backend, Bootstrap review or CH456 live run is needed.

Record the implementation HEAD and raw output under a new `windows-validation/`
subdirectory here, then append the validation result. Preserve historical evidence.
A failed check stops this confirmation; report its exact traceback before changing
code or expanding scope. The policy group includes the historical candidate test
that could not run in the reconstructed Linux environment.

```powershell
$acceptanceTests = @(
  ".agents/skills/run-refactor-implementation-acceptance/tests/test_current_acceptance_closeout.py",
  ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator.py",
  ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_s0.py",
  ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_s1.py",
  ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_s2.py",
  ".agents/skills/run-refactor-implementation-acceptance/tests/test_coordinator_trust.py",
  ".agents/skills/run-refactor-implementation-acceptance/tests/test_deterministic_finalization.py",
  ".agents/skills/run-refactor-implementation-acceptance/tests/test_control.py",
  ".agents/skills/run-refactor-implementation-acceptance/tests/test_compact_vdd_projection.py",
  ".agents/skills/run-refactor-implementation-acceptance/tests/test_review_requirement.py"
)
py -3 -m pytest @acceptanceTests -q
if ($LASTEXITCODE -ne 0) { throw "Acceptance closeout checks failed" }

$quickDevTests = @(
  ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_cer_behavior_routing.py",
  ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_coverage_predicates.py",
  ".agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_reentry.py"
)
py -3 -m pytest @quickDevTests -q
if ($LASTEXITCODE -ne 0) { throw "Quick Dev adjacent checks failed" }
```

There are two pytest groups above; the three Linux result files split the
Bootstrap policy tests from the other Acceptance tests. Windows runs that full
policy file with the Acceptance group. Expected total: 149 tests if collection
matches the pinned candidate; test results, not the expected count, determine pass.
