# Independent-unit timeout repair (2026-10-24)

## Scope and result

User approval: Sentinel_c5672038af888191a8d81c7f0875ebc6. Implemented only VDD/Quick Dev time supervision in the isolated candidate at HEAD f57c2998f83f12dfc98afe11816a4827fffd0228. No r3 recovery, plan generation, real model/BMAD/reviewer, A/B, business query, push or CI operation was executed. No commit or stable-host promotion was performed.

Both SKILLs and affected guides now define a default total of 1800 seconds per independent unit, with 600 seconds of genuine inactivity. scripts/workflow_unit_budget.py is a scoped process supervisor used by the two public entries, not a new task scheduler or evidence writer. Current source identities are in changed-file-identities.json (25 files). The scoped diff also contains earlier query-intake changes in compile_plan.py; those were preserved, not authored or withdrawn by this repair.

## Actual boundaries

VDD semantic_progress wraps actual native stages and workers. V1 extraction/source-check calls and V3 batches (at most four frozen obligations each) are independent units before V6 produces slices. Container stages do not charge independent child time again, including thread-pool workers. Native normal/repair defaults are 1800 seconds. The public caller-session route selects the same total when no explicit host override exists. An explicit old --host-timeout-seconds 600 remains a shorter TOTAL and must not be used to express inactivity.

Quick Dev actual author/implementation/refactor workers, CER subprocess executions and individual non-pytest Q6 commands have unit events. Newly materialized targeted/terminal and worker defaults are 1800; Q1/session accept this value. Existing frozen descriptors are not rewritten: explicit shorter descriptor limits still apply. Existing positive integer session timeouts up to 600 continue to work, with the upper bound raised to 1800.

Per-unit keys and cumulative active costs are retained across transport attempts and explicit resumes in logs/workflow-unit-budgets/<workflow>/<scope-hash>. Query-attempt advisory IDs and schema diagnostic changes cannot renew the same VDD input's budget. These budget-only identities do NOT alter semantic cache identities. Retries remain subject to existing native attempt/stop-loss checks. Genuine output resets inactivity, never total cost; duplicate byte chunks do not reset inactivity. Polling, event-file touches and supervisor checkpoint writes do not count as progress. No heartbeat is generated.

On timeout/cancel the supervisor terminates the owned tree, including detached POSIX descendant sessions, retains native partial files and writes non-authorizing attempt diagnostics. Quick Dev local descriptor timeout also cleans its subprocess tree. SIGTERM and Ctrl-C enter the same cleanup path. No successful process receipt is synthesized. Recommendation-only, inspect-selection and session preflight preserve their no-supervision-write boundary. Native reentry and shared-execution validation still decide reuse before a new execution.

The three private supervision environment variables are removed from actual test subprocess environments; the corresponding environment fingerprint hashes exactly this sanitized environment. All other variables remain bound. Supervisor code bytes are added to engine/reentry identities. This prevents a random event sink path from forcing a fresh process while keeping source/policy changes invalidating proof.

The old r3 supervisor.py is historical and unchanged. It imposed the observed 1800.117-second round cutoff; future normal runs must use the public entries without that old outer wrapper. The standalone real-semantic-quality benchmark still has a separate explicit aggregate cap; it is not the normal recovery route and was not modified or run. Direct imports of internal modules do not substitute for public-entry supervision.

## Validation and raw records

- unit-signal-final.log: 12/12 passed in 0.764s (including actual POSIX SIGTERM cancellation). Virtual-clock tests cover >1800 aggregate normal units, per-unit total, 600 silence, genuine progress without renewing total, duplicate output, retry/resume cumulative cost and parallel V3 batches. Short subprocess tests cover timeout/cancel, POSIX signal cancellation and actual detached descendant cleanup. Windows taskkill tree flags are mocked only.
- vdd-v2.log: 18/18 passed. Existing fake transport tests updated only the three old default timeout expectations (300/180 ->1800); explicit repair overrides still tested. No real model used.
- reuse-stdlib.log: 28/28 passed in 87.84s. After the final SIGTERM-only cleanup addition, reuse-final.log reconfirmed both supervisor-routing and cross-slice original reuse (2/2 passed in7.10s). Includes cross-slice/Q6/terminal original reuse, Git-only reuse, actual dependency/environment changes, tampered/lost originals, duplicate idempotence, current Q8 reads, unknown dependencies and failure refusal. The new private-supervisor-environment case reuses one actual tiny pytest execution with zero second process attempts.
- reuse-session.log: 51 passed /11 failed in the first isolated uv environment. All 11 failures came from safe reuse-publication refusal of an unbound _virtualenv.py injection, not manufactured success. Standard-library venv retest above passed all 28 affected reuse cases. Session and stage-reentry tests passed in the earlier combination, including completed probe/regression/refactor reuse without launching again.
- quickdev-v2.log: 27 passed /1 failed. Failure test_standard_q6_runs_explicit_single_file_consumer_fixture calls historical test_plan_directory_loop.py. consumer-fixture-diagnostic.log identifies its unmodified read_only_index_tree creating /ri... on the read-only filesystem. That underlying suite:47 passed/1 failed. This unrelated fixture was not altered or skipped to claim a clean aggregate suite.
- package.log: repository Skill validation ok, no findings. skill-package.log:22 tests and15 subtests passed. Syntax/whitespace checks passed (an existing historical CRLF Git warning remains).

Initial Python lacked pytest. Dependencies were installed only in temporary /tmp environments; no repository dependency or credential was changed. The first new unit test had an incorrect source-name assertion and was removed in favor of the actual native reentry suite; the earlier failed attempt was reported, not interpreted as runtime proof.

## Preservation and limits

preservation.json confirms all seven frozen input files unchanged, policy raw SHA eabe46712ac4cf3e2f35aad169191f713401166293673a34a74044041c6ffaa7, business query config SHA 0f83722c40f107b7e6bb31c05bf3f905e0e14af90e45f0cbcd886b4c50476302. Among 130 protected launch files, only compile_plan.py changed for this authorized public-entry repair. All other protected files remain byte-identical. Old requirements/contracts, original 330 directory, r3 history/caches and the unconsumed answer were not edited. Business query 30/60-second budgets, model policy and authority predicates were not changed.

Linux deterministic/short-process verification only. No real 1800/600-second wait, Windows runner, real model, original long compilation or original long shared consumer suite was run. The supervisor has no success authority and cannot make old r3 data into a published plan. Recovery inspection is separately recorded in ../vdd-r3-recovery-readonly-20261024/REPORT.md and inventory.json.

## Stop point

This authorized timeout-repair step is finished; do not resume r3 automatically. The inspection found 61 exact V1 raw caches and completed source checks, V2 returned, zero accepted V3 contracts, four real 600-second request timeouts and one late/unconsumed response. Public resume still traverses V1/V2 and query advisory identity may prevent prior semantic-cache hits; this repair deliberately did not bypass or change that boundary. A next recovery/cost decision requires user confirmation.
