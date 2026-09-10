# Direct implementation closeout and local verification

## Current disposition

Reopened after the 2026-09-10 source audit found four gaps in the earlier
closeout: required-input enforcement, trusted changed-set derivation, live v2
consumer migration, and automatic native-reference retention. The earlier
139-case Windows result remains valid for its tested source, but did not prove
those requirements. Historical closeout statements below are superseded here.

The four corrections are implemented on this branch under the maintainer's
direct authorization, without VDD/Quick Dev/Acceptance orchestration. The subsequent W3 stale-context successor correction is also implemented.
Online verification now reports **178 passed, 1 Windows-only case deselected**.
Fresh Windows verification of the corrected source remains pending; do not
call this revision closed solely from earlier evidence.

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

## Four-gap implementation correction (2026-09-10)

- W0: skill_input_requirements.verify_inputs requires every operation input,
  checks allowed root kinds, selected-source membership and typed directory
  coverage. The normalized mapping is immutable and revalidated on current.
- W3: skill_input_candidate observes tracked changes, deletions and untracked
  files against an authority-bound Git baseline. Ignored Knowledge paths cannot
  hide self-change. Caller changed_paths is optional assertion-only. Missing
  baselines, hidden scope and candidate-byte changes fail closed.
- W4/W6: the shared live gate accepts only v2 current pointers. Existing
  prepare/launch CLI names default to v2; --historical-v1 explicitly retains
  replay only. Four real Skill-input entry functions are exercised in isolated
  processes using the actual contracts. Non-adopting Quick Dev staged runtime
  keeps its separate governance policy.
- W5: native gate use writes consumer/operation/generation/receipt custody
  before handoff and registers the durable lifecycle/authorization/terminal/
  acceptance reference automatically. Successor current and expired attempts
  cannot collect a consumed generation. Native custody tampering blocks GC.
- Also enforce the existing max_context_bytes contract at publication/readback.
  Oversized context blocks; no incomplete context is promoted.

Validation evidence:
`logs/toolchain-workflow-repair-direct/20260910T040103Z-7d9cf1a9/`.
The preceding 035935Z run is preserved; the final source additionally fixes
the entry-probe subprocess stream encoding explicitly for Windows.
This final run verifies unchanged consumer dependencies against remote Git
blob bytes; source_stable=true and skipped_cases=0. The intermediate run at
`logs/toolchain-workflow-repair-direct/20260910T035418Z-b377a199/` is preserved
as source-extraction evidence, not the final source binding.
The preceding failing development run is preserved separately at
`logs/toolchain-workflow-repair-direct/20260910T035252Z-c9d07b25/`.
That failure exposed an old test expecting live v1 acceptance; the test now
preserves historical validation and asserts live rejection under ADR-0060.

The new test module adds 26 cases. Entry tests use real input/current/retention
code, but deliberately replace downstream VDD evaluation and Acceptance run
creation or stop Bootstrap at its next argument check. No live backend or
formal workflow is invoked. They prove the entry boundary, not full formal
workflow execution. Online validation uses a source extraction with source_head
null and records hashes of actual consumer executable dependencies.

Windows handoff: update this branch, preserve all prior bundles, and run
`py -3 scripts/python/verify_toolchain_workflow_repair.py`.
Expected Windows collection is **165 cases**, with zero failures/skips,
source_stable=true, platform_exclusions=[] and
windows_verification_pending=false. New verification evidence is required
before recording another final closeout.


## W3 stale-context successor correction (2026-09-10)

A second source review found that an originally valid preflight marked
knowledge_freshness=current was rejected after the catalog became stale,
before the adapter could verify a controlled successor. This is corrected in
knowledge_gate_projection.observe_knowledge.

The adapter first validates the frozen envelope, hashes and preflight status.
It checks publication integrity, then recomputes freshness only in a deep copy.
Both the pre-refresh and post-refresh validation require catalog membership,
including policy, consumer projection, module and read-set checks, even for a
previously refreshed stale context. The source-refresh marker cannot bypass
membership. Source hashes are refreshed only after those checks. No frozen
context, freeze or Knowledge publication artifact is rewritten, and a failed
preflight or disallowed stale request is not promoted to ready.

The observation now carries the verified successor_context plus its hash into
the immutable Skill-input receipt. source_refreshed compares actual selected
source identities, not freshness metadata, so unchanged selected bytes use
degraded-continuation and changed selected bytes use successor-refresh.
Identical readback is deterministic, and a separately frozen verified successor
can be reused without modifying its predecessor.

New regression: test_knowledge_successor_v2.py, **14 cases**. Tests construct
real Git history and publication-shaped fixture artifacts, use the real
freshness/catalog/source validators, and do not mock gate facts. They cover
current, stale-unselected, stale-selected, full v2 degraded publication,
successor reuse, failed preflight, hash/publication corruption, missing sources,
selection/policy drift, disallowed staleness, malformed freshness and forged
source-refresh markers. All artifacts are temporary fixtures; no live Knowledge
publication, model or formal workflow is invoked.

Final online evidence:
`logs/toolchain-workflow-repair-direct/20260910T083752Z-f1beb77e/`.
Result: **178 passed**, zero skipped, one Windows-only deselection,
source_stable=true. This supersedes the prior 164-case source set.

Windows handoff for this revision: run
`py -3 scripts/python/verify_toolchain_workflow_repair.py` after updating the
branch. Expect **179 cases**, zero failures/skips, no platform exclusions and
stable sources. Final closeout remains pending that fresh Windows result.

