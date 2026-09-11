# Stage Recovery

Read this guide only for the operation selected in SKILL.md. Commands run from the repository root unless stated otherwise; inline paths retain their original repository/Skill-root meaning.

## Snapshot, Invalidation And Recovery

The current snapshot resolver owns exactly eight runtime root kinds: `candidate_tree`, `plan`, `contract`, `descriptor`, `fixture`, `source`, `validator_judge`, `plan_state_transition`. Governance artifacts are excluded unless explicitly adopted by a product/execution dependency.

Use the versioned change-impact resolver for Q0/Q4/Q7/Q8/recovery. Selector/fixture/target/source changes restart at RED; production-owner changes rerun at least GREEN/REFACTOR and restart RED when failure semantics changed; compiler/validator/judge/predecessor changes invalidate their descendants. A recovered run must name an explicit prior run and re-read its receipt, observation and runtime edges with current hashes; it may not scan history.

## Stage Reentry And Failure History

Current stages check their explicit run-local evidence before launching tests.
A completed stage with matching plan, descriptor, profile, runtime code and
candidate/target/fixture bytes returns its original result, including a recorded
failure. It does not rerun tests or overwrite history. Partial or stale evidence
returns `stage-reentry-blocked`; preserve it and use explicit recovery or a new
run. Results created before the reentry binding protocol require a new run for
execution; their historical evidence remains readable.

The shared stage dispatcher applies repeat stop-loss to `probe`, `red`, `green`,
`refactor`, `regression` and `terminal`. Pass an ordered JSON history through
`--failure-history`, or place it explicitly at `<run-dir>/failure-history.json`.
Each row binds `failure_fingerprint`, `candidate_hash` and `selector_identity`.
No history scan or latest-run inference is performed; absent history does not
claim knowledge of other runs. Two matching prior failures block the third
attempt before execution. Refactor reentry checks precede its model worker.

For the bounded 8-17 closeout, run the test files listed in
`logs/quick-dev-stage-recovery-closeout-23cf4937/validation.json`, including
`test_stage_reentry.py`, `test_ch456_recovery_mutations.py` and
`test_ch456_public_repeat_guard.py`. No live CH456 run is required.
