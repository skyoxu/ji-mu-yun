# Narrow Quick Dev executor call metadata repair

Authorization: Sentinel_4476a30ec6a88191bb3c9b80cefabdf8 (2026-10-25 06:42 UTC).
Status: repair and targeted verification complete; stopped. S2/Q7 were not resumed.

## Self-review and scope

The diagnosis proved volatile CODEX_TOOL_CALL_ID metadata enters the aggregate fingerprint. It did not recover the historical per-variable environment, so this repair does not claim to identify every cause of the old rejection.
The smallest isolated ownership boundary is Quick Dev's controlled pytest environment, not the shared workflow supervisor. One provider removes only CODEX_TOOL_CALL_ID after the existing three private supervisor variables have been removed. The actual child launch and environment fingerprint import that same provider. Parent process environment, VDD, model routing, query configuration and every other variable remain unchanged.

## Changes (six files)

- tools/execution_environment.py: new Quick Dev-only provider; one exact metadata-name exclusion and environment algorithm identity quick-dev.pytest-environment.v2.
- tools/shared_execution.py: fingerprint uses the provider and carries its explicit schema. Current-input validation rejects unversioned, old and unknown environment identities with reuse-environment-schema-incompatible. Identical aggregate digests cannot prove an older filtering rule.
- tools/process_executor_v2.py: actual pytest collector child uses the same provider; it cannot observe the excluded metadata. No hash-only omission or environment restoration from historical receipts.
- tools/tests/test_execution_environment.py: deterministic environment/legacy checks, separate short process captures, and a tiny real native collector/shared-reference fixture. This is not the S2 business test suite.
- references/shared-execution.md: exact boundary, retained variable sensitivity and old-format limitation.
- docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md: narrow authorized ownership/compatibility clarification.
All tools paths above are under .agents/skills/quick-dev-tdd-adapter/.

## Actual verification

Before repair, the existing environment function reproduced the metadata-only inequality: one targeted assertion failed in 0.05 seconds (before-fix.txt). This is a maintenance reproduction, not S2 behavioral RED or Q4 permission.
After repair, the new targeted module passed 13 tests in 4.68 seconds (targeted-tests.txt). It verifies:
- CODEX_TOOL_CALL_ID changing, appearing or disappearing leaves the candidate environment unchanged and does not edit the parent environment;
- PATH, PYTHONPATH, HTTPS_PROXY, GIT_CONFIG_NOSYSTEM, another CODEX_* name, query configuration and an unknown input remain bound;
- absent, present-empty and distinct values of every retained test variable have distinct identities;
- independent short Python processes agree for metadata-only differences and disagree for a meaningful retained input change;
- old aggregate-only, old-version and unknown-version requests are rejected without rewriting their sealed fixture bytes;
- the actual native pytest child cannot see the call identifier; a later terminal fixture consumes the same successful original with process_attempts=0 and no second pytest execution, and later native reference validation tolerates another call-ID change.
Six selected existing shared-execution protection cases passed in 13.97 seconds (existing-protections.txt): cross-slice original identity, private supervisor routing, real environment drift, OS/Windows identity mismatch rejection, legacy incomplete proof rejection and actual subprocess dependency refusal.
Total: 19 targeted passes. git diff --check passed for all changed tracked paths. No real Windows run is claimed by the OS-mismatch negative fixture.

## Existing S2 evidence and recovery limits

The S2 test source, current canonical plan and common workflow_unit_budget.py match the pre-repair hashes. The old 105-case pass and same-process Q6 primary-command reuse remain unchanged historical facts. They are not upgraded into valid new-rule evidence: the old regression environment has no schema, its aggregate cannot be safely converted, and the native engine bytes changed. New-rule Q7 cannot legally accept that old request as current evidence.
The independent subprocess-based reusable-publication refusal is deliberately preserved; this fix does not make Git/source-reading tests eligible for cross-execution shared publication.
Before resuming S2, adopt/freeze the approved repaired host identity and reconcile the test's fixed-host checks through normal Q2. The present S2 stable_owner_guard reads the prior publication inventory, so blindly running its unchanged expectations against this intentionally updated host would create a predictable baseline mismatch. Do not merely replace expected hashes to get a pass.
Then use the public fresh/recovery route to obtain only the current evidence actually required by the changed engine and proceed to Q7/terminal. Exact retained behavior, current test/host/source identity and normal gates must determine that scope. No full PRD/SPEC/Architecture/VDD regeneration is required by this repair.
This report does not authorize that recovery, alter the frozen plan, rewrite any old receipt or claim a completed slice.

No S2 probe/regression/Q7 retry, actual model, BMAD skill/reviewer, A/B, next slice, push, PR, merge, CI query or model-setting action occurred. All targeted test processes completed. Existing unrelated dirty files, original evidence and unpublished intermediate plan directories were preserved. Work stopped for the next user decision.
