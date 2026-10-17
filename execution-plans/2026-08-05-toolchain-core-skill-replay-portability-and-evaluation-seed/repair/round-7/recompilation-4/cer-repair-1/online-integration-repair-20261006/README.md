# TC-D1 Online Integration Repair Handoff

Base candidate: `91279a19ae3d4d6936b86339e9cd5c8c09327fe2` on
`fix/08-05-real-skill-replay`. Accepted ADR-0058 owns this bounded repair.

## Changes

- Refuse candidate-controlled trust-commit environment overrides. Isolated test
  authority stays in copied fixture code; C3 remains OPEN.
- Record actual child-observed Probe targets and restore the inspected
  `replay_identity` contract.
- Require exact rollback Consumer/fixture coverage, preserve native outcomes,
  and report Consumer and fixture counts separately.
- Honor v3 aggregate budgets for both process layers and recompute each
  Stable/Candidate source identity after execution.
- Align affected CER selectors with the real five-Consumer, three-Probe, native
  v3 contracts. Keep their assertion IDs and historical inputs unchanged.

The shared Matrix fixture creates a new temporary input under `logs/`; it does
not rewrite `stable-candidate-replay-matrix.v1.json`. Negative Consumer calls
must reject with the intended diagnostic, rather than return exit zero.

## Online Validation

Evidence: `logs/08-05-real-skill-replay/online-integration-repair-20261006/`.

| Attempt | Observed outcome |
| --- | --- |
| Initial integration faults | 5 expected failures; 13 imported support tests also ran |
| First budget faults | 2 budget failures and 3 isolated-fixture setup errors |
| Corrected budget faults | 5 passed, 2 expected budget failures |
| Final native regressions | 25 passed, 0 failures, 0 errors, 0 skipped; source stable |

All raw attempts remain preserved. The temporary fixture setup error was fixed
before final validation. Final tests use real processes and immutable isolated
Git inputs. This is a Linux scoped-source verification, not a checkout of the
entire GitHub tree. Pytest/jsonschema are unavailable in this online environment;
the full existing CER suite and Windows behavior still require local validation.
No live backend, VDD, Quick Dev or Acceptance workflow was invoked.

## Local Windows Validation

Synchronize this branch first. Run these from the repository root and archive
raw stdout, stderr, JUnit and validation metadata in a new attempt directory:

```powershell
py -3 -B -m unittest discover -s scripts/sc/tests -p "test_skill_replay_*regressions.py" -v
py -3 -B -m pytest -q scripts/sc/tests/test_skill_package_replay.py scripts/sc/tests/test_skill_package_replay_source_identity.py scripts/sc/tests/tc_d1_cer --junitxml=logs/08-05-real-skill-replay/online-integration-windows-1/junit.xml
```

Create the output directory before running pytest. Keep failures intact and use
a new directory for subsequent attempts. Do not set a different
`TC_D1_TRUST_COMMIT`; product trust is pinned, not locally self-approved.

After tests, use the read-only archival checker on the original Q8 result:

```powershell
py -3 -B scripts/sc/audit_skill_replay_archive.py --result execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/recompilation-4/cer-repair-1/quick-dev-ready/current-run/terminal-incremental-20261006/implementation-complete-result.v2.json --output logs/08-05-real-skill-replay/online-integration-windows-1/archive-audit.json
```

Review its exact missing/untracked paths. Preserve the original native run roots
and bytes when archiving; a renamed copy or reconstructed summary cannot replace
them. The checker validates archival membership/references only, and cannot
publish a new implementation or Acceptance decision.

## Acceptance Boundary

The repaired source invalidates old current-candidate bindings. Passing these
tests does not refresh Q7/Q8. Restore missing original raw evidence, bind the
affected current-run selectors to this source, and produce new owning-flow Q7/Q8
evidence before formal Acceptance. Do not rerun unaffected slices blindly or
rewrite historical evidence. `authorizes=[]` and C3's existing blocking scope
remain unchanged. This handoff does not declare 08-05 complete or Acceptance-ready.
