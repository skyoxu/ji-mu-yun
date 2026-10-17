# Minimal independent forward validation

Result: PASS.

Scope: native `create_persisted_run` plus real `acceptance_cli.py` resume/inspect commands, each in a fresh Python process. Three minimal index-only Git fixtures; no commits, pushes, real plan execution, network calls, or model launches.

1. Two dependent read-only actions execute in separate CLI calls. Fresh-process inspection replays the first completion and exposes the second as ready. The original receipt remains unchanged.
2. A real child changes a tracked fixture file. The read-only guard rejects the execution and marks its run polluted. Detection is post-execution and does not roll back the file.
3. A real child exits 7 with recorded stdout/stderr. Inspection preserves failed state; identical retry is rejected without a second attempt or lifecycle mutation.

`results.json` contains actual invoked commands, working directories, stdout, stderr, exit codes, observations, and source hashes. The tracked-write child has no published process receipt because the guard raises; its real file change and CLI rejection are preserved.

This is function-level persistence and real CLI validation. It is not real Acceptance or Q8 evidence and grants no authority.
