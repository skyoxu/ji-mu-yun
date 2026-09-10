# Direct implementation closeout and local verification

## Current disposition

The maintainer explicitly requested online direct implementation and GitHub
commits, without VDD, Quick Dev or Acceptance execution. The full W0-W6 scope
is retained. This instruction supersedes the historical execution procedure
for this repair, not the behavioral requirements or historical evidence.

The full W0-W6 package is closed under the maintainer-authorized direct route,
based on the implemented requirement mapping below and the maintainer-reported
Windows validation of source commit 86faa3e0 (139 passed, zero skipped).
This disposition supersedes the pending statements in the historical entries
below. Historical formal lifecycle receipts remain unchanged; no formal
acceptance is claimed. No formal model/worker, Bootstrap, Knowledge publication,
or real historical GC was run online.

## Requirement mapping

| Scope | Implementation and observable test coverage |
| --- | --- |
| W0 | skill_input_selection.py; strict roles/paths, separate selection/content identities, current-byte verification, forbidden source/output overlap |
| W1 | skill_input_transport.py and skill_input_v2.consume; UTF-8 pages, exact continuation identity, persisted bounded retries, lease heartbeat |
| W2 | skill_input_coverage.prove_ranges and finish/readback; full byte/line/hash coverage, incomplete/modified observations block current |
| W3 | knowledge_gate_projection.py; independent gates, healthy/stale/refresh/drift/invalid LKG/publication cases, changed-set self-review; bound Locator validation or explicit non-Knowledge direct-source mode |
| W4 | skill_input_generation.py, skill_input_current.py, finish and require_current; staged immutable content, idempotent replay, source/binding/validator freshness, failed pointer publication preserves predecessor |
| W5 | skill_input_retention.py; leases and transitions, current/native-reference protection, deterministic dry-run, exact approval/commit binding, actual fixture cleanup and sidecars |
| W6 | test_toolchain_workflow_repair_e2e.py; full direct pipeline, all four consumer identities, negative artifacts, shared gate readback and retention |

The former plan-local terminal scanned status-only slice receipts. It now
fails closed and points to the direct verification command; it cannot mint a
new implementation-complete receipt from old statuses. Original source and
produced history remain available at their original Git revisions.

## Local Codex instructions

1. Fetch and switch to `codex/complete-8-18-toolchain-workflow-repair` in a
   clean dedicated checkout. Preserve unrelated user changes.
2. Read AGENTS.md, this document and docs/workflows/skill-input-v2.md. This
   repair is explicitly authorized to use direct tests, without invoking the
   formal VDD/Quick Dev/Acceptance chain.
3. Run `py -3 scripts/python/verify_toolchain_workflow_repair.py` from the
   repository root on Windows. Ensure pytest is installed in that interpreter.
   The full command and per-case JUnit evidence are generated automatically.
4. Confirm the exit code is zero, source_stable=true, platform_exclusions=[],
   windows_verification_pending=false and no unexpected test skips. Verify the
   actual consumer operation/contract files used in this checkout. The online
   tests exercise direct/shared-gate behavior, not live model comprehension or
   a full formal workflow run.
5. Inspect the implementation against W0-W6, especially native-reference
   registration before retention, Knowledge Locator mode in the configured
   repository, and Windows reparse-point behavior. Do not delete real history
   as a test. A direct-source freeze must not be substituted for required
   Knowledge authority to make a blocked Locator path appear successful.
6. If a defect appears, fix it on this branch, preserve failed logs and rerun
   the affected test plus the direct verification command. Do not edit tests
   merely to declare completion.
7. Append the resulting source commit and evidence path to this document and
   record the maintainer's direct closeout decision. Commit actual generated
   logs and changes. Do not fabricate historical formal lifecycle receipts.

Online results and byte hashes are under logs/toolchain-workflow-repair-direct.
The prior environment-blocked checkpoint is historical; the direct route
supersedes that procedure and has executable online tests.

## Online validation result

- Direct behavioral suite: **133 passed, 1 Windows-only test deselected**.
- Evidence: `logs/toolchain-workflow-repair-direct/20260909T172842Z-875d2be5/`.
- Environment: isolated source extraction fetched from the repair branch based
  on c19adde1; this is not a complete authenticated Git checkout. The validation
  report correctly has source_head=null and binds the actual tested file bytes.
- Required remaining platform test: the unmodified
  `test_intermediate_junction_is_rejected_when_supported` on Windows.
- Earlier 127-case evidence is retained separately; use the 133-case directory
  for this delivered source set. Historical formal receipts are not resealed.

## Windows encoding correction (2026-09-09)

The maintainer reported Windows validation of 04900158 as 133 passed and
1 failed, with no skips, stable sources and no live backend calls. The CLI
E2E reader used the Windows default GBK codec and raised UnicodeDecodeError.
Reported evidence remains in the maintainer checkout at
`logs/toolchain-workflow-repair-direct/20260909T173411Z-6c910824/`;
these local artifacts have not been independently inspected or uploaded here.

The CLI now explicitly configures stdout/stderr as strict UTF-8, and its E2E
subprocess reader explicitly decodes strict UTF-8. The test covers inherited
UTF-8, GBK and CP1252 streams with Python UTF-8 mode disabled and verifies
exact Unicode page reconstruction before finishing and validating current.

Corrected online suite: **135 passed, 1 Windows-only test deselected**.
Evidence: `logs/toolchain-workflow-repair-direct/20260909T174023Z-0a2570cb/`.
This supersedes the earlier online result for the corrected sources. Windows
validation and final direct closeout remain pending. Rerun the same direct
verification command on the corrected branch; Windows should collect 136
cases, with no platform exclusions. Preserve the failed Windows evidence.

## Source newline oracle correction (2026-09-09)

The maintainer reported 133 passed and 3 failed on Windows at 6f7c9e29,
with stable sources and no skips or live backend calls. Reported evidence is
`logs/toolchain-workflow-repair-direct/20260909T174908Z-d5b74696/` in the
maintainer checkout; it has not been independently inspected or uploaded here.

The CLI correctly preserved source CRLF bytes. The test expectation incorrectly
used read_text(), which normalizes CRLF to LF. Under ADR-0060, coverage binds
original source bytes, so the assertion now compares UTF-8 encoded delivery
with read_bytes(), without normalizing either side. Explicit LF and CRLF
fixtures cross all three inherited stdio encodings on every platform.
Before correcting the assertion, these fixtures reproduced 3 failures and
3 passes online; the corrected full suite reports **138 passed, 1 Windows-only
test deselected**. Evidence is
`logs/toolchain-workflow-repair-direct/20260909T175254Z-d8baa600/`.
No production transport change was necessary. This result supersedes the prior
online count. Windows should collect 139 cases; Windows revalidation and final
direct closeout remain pending. Preserve both failed Windows evidence bundles.

## Final Windows validation and direct closeout (2026-09-10)

The maintainer reported successful local Windows verification in this session:

- Branch: `codex/complete-8-18-toolchain-workflow-repair`.
- Tested source HEAD: `86faa3e0ed4807211bfd76e997d5971c3871c9c0`.
- Result: **139 passed**, skipped=0.
- source_stable=true; platform_exclusions=[].
- windows_verification_pending=false.
- Live backend and formal workflow were not invoked.
- Reported evidence:
  `logs/toolchain-workflow-repair-direct/20260909T175543Z-8c83853f/validation.json`.

Evidence provenance: the maintainer generated these artifacts locally and
archived all three original Windows bundles in commit
`cea4871fb5d1552381afcf4863d80cb544b370e1`, whose parent is the preserved closeout
commit `c4ac1e3df3d567e83dce1b04bdfa7eb67f9a3c96`. The online agent subsequently
read all twelve archived files from that commit. The successful validation.json,
stdout and JUnit agree on 139 cases passing, zero failures/errors/skips, source
HEAD 86faa3e0, stable sources, no platform exclusions, no live backend calls,
and no formal workflow invocation. stderr is empty. Both earlier failed runs
remain archived with their original one-failure and three-failure results.
This inspection verifies the archived reports; it is not a new Windows run.

The originally requested complete W0-W6 direct repair is therefore recorded as
closed on this branch. The two observed Windows defects were corrected before
this passing run. This documentation-only closeout does not change the tested
implementation, merge the branch, publish Knowledge, or generate formal
acceptance/lifecycle receipts. Raw Windows evidence archival is complete. There are no outstanding Windows
verification or evidence archival handoff items for this direct closeout.
