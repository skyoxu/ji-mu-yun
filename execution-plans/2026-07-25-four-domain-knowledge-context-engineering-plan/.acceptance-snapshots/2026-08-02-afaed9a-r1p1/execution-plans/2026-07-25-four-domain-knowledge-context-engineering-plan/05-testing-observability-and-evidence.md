# Testing, Observability And Evidence

## Test matrix

| Area | Required command or check | Evidence |
| --- | --- | --- |
| Plan composition | `py -3 tools/validate_whole_directory.py` | validator JSON output |
| Inventory generation | `py -3 tools/build_hosted_inventory.py --output-dir <temporary>` | generated inventory hashes |
| Schema shape | validator Schema inventory and JSON parsing | `schema-validation.v1.json` |
| Positive fixtures | validator fixture pass set | `fixture-positive-results.v1.json` |
| Negative fixtures | validator targeted failure set | `fixture-negative-results.v1.json` |
| Source snapshot | generator same-input replay | `inventory-replay.v1.json` |
| Python backend delegation | static source guard for `run_llm_exec` | `k5-delegation-check.v1.json` |
| Knowledge Locator contract | request/result Schema, positive/negative interface fixtures, ownership and source-identity checks | `knowledge-locator-results.v1.json` |
| Maintenance Skill contract | mode/target, pinned main, discovery, provisional, mutation, LKG and append-only checks | `knowledge-maintenance-results.v1.json` |
| Existing Phase contracts | path/reference and contract-name checks | `existing-contract-coverage.v1.json` |
| Report index | `py -3 scripts/python/validate_execution_plan_report_index.py` | command output |
| Recovery docs | `py -3 scripts/python/validate_recovery_docs.py --dir execution-plans` | pre-existing repository diagnostics plus plan-local check |

## Evidence boundary

Plan-local deterministic outputs are written under `logs/knowledge-context/<date>/<run-id>/` only when a K0-K10 validation or synthetic run is executed. This plan creation does not fabricate such a run. Failure evidence is additive and historical files are never rewritten.

No evidence may contain real tokens, provider secrets, raw user prompts, live account data, live database rows, or absolute paths to protected live workspaces. Locator evidence records normalized terms and source locations, not a generated fact answer. Maintenance evidence records the pinned main commit, target/mode, before/after snapshot, changed/unchanged/missing/candidate entries, LKG disposition and failure code without copying sensitive source content.

## Production validation after authorization

Only after the relevant slice is implementation-authorized may production changes run their required Phase tests, including `PhaseA.Platform.Tests`, shared entrypoint tests, route-specific tests, and Phase smoke. Those commands are not run during this plan-directory creation.
