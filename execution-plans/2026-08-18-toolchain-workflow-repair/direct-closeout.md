# Direct implementation closeout and local verification

## Current disposition

The maintainer explicitly requested online direct implementation and GitHub
commits, without VDD, Quick Dev or Acceptance execution. The full W0-W6 scope
is retained. This instruction supersedes the historical execution procedure
for this repair, not the behavioral requirements or historical evidence.

Implementation is delivered for local verification. Do not call the package
closed or change its historical formal lifecycle to acceptance-passed until
the maintainer's local validation is recorded. No formal model/worker,
Bootstrap, Knowledge publication, or real historical GC was run online.

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
