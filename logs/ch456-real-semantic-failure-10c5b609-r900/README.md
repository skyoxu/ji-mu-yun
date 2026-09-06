# CH456 real-semantic failure evidence

Candidate: `10c5b6099ffd4a6de9ba9d8e3fd801b9d4be6f8e`.

The specified regression passed (`193 passed`). The real-semantic command used
`--compile-timeout-seconds 3600 --repair-timeout-seconds 900` and exited `1`
with `status=worker-failed`. The retained progress shows V1 workers and V4
atomic-recall succeeded; V3 initial execution returned exit `124`, its
schema-repair returned successfully after 459 seconds, and V3 then failed
execution-contract validation (`no-real-production-entry` and
`selector-target-missing-not-planned`).

Live blind and final acceptance were not run. The `run/` tree is copied from
the exact temporary compiler run, including cache, worker outputs, receipts,
schemas, progress and watchdog result. External stdout/stderr and exit codes
are under `external-output/`.
