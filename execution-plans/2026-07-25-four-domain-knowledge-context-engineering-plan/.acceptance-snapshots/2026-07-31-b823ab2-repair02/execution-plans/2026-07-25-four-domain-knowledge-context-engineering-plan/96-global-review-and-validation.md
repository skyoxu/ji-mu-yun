# Whole-Directory Review And Validation

## Required checks

```text
py -3 execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/tools/validate_whole_directory.py
py -3 execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/tools/validate_whole_directory.py --publish-plan-ready
py -3 scripts/python/validate_execution_plan_report_index.py
```

The first command is read-only. The second may only update the plan-local state status after all checks pass. The third validates the repository report index.

## Review boundary

Whole-directory validation checks plan authority and executable artifact composition. It does not run semantic reviewers, does not inspect live workspaces, and does not authorize production code. A later Bootstrap Review must freeze this directory and bind all required context artifacts to its own run.

Round 1 is finalized at `logs/ci/2026-07-25/kc-plan-r1e` and remains immutable `blocked` evidence. Deterministic repair does not retroactively change that result. A Round 2 semantic review requires a fresh run, exact repair closure, current high-cost acknowledgement, and explicit authorization.

## Failure handling

Preserve the validator output, repair the smallest affected plan slice, invalidate dependent slice readiness, and re-run the terminal validator. Do not rewrite failed evidence or mark a fixture passed by changing its expected result.
