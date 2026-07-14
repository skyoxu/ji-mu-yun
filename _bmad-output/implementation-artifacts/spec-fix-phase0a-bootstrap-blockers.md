---
title: 'Fix Phase 0A Bootstrap Blockers'
type: 'bugfix'
created: '2026-07-13'
status: 'in-review'
review_loop_iteration: 0
baseline_commit: '03dacbf9f580aaed1067804418f55b1bd4d26296'
context:
  - 'C:/jimuyun/AGENTS.md'
  - 'C:/jimuyun/execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/96-global-review-standard.md'
  - 'C:/jimuyun/logs/ci/2026-07-13/review-gateway-bootstrap-7-07-manual-20260713-124206/review-gate-result.json'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The finalized 7-07 Bootstrap Review confirmed three P1 defects: the acceptance matrix falsely treats one permitted Phase 0A deferral as a global phase-exit failure, and both the common recovery contract and `run_needs_fix` machine contract omit the selected route skill prompt block as an independently bound recovery authority.

**Approach:** Make Phase 0A exit projection deferral-aware without crediting later phases as complete, add the missing prompt-block authority to plan and runtime recovery contracts, regenerate deterministic artifacts, and repeat Whole-directory plus Bootstrap review until the confirmed blockers are closed.

## Boundaries & Constraints

**Always:** Preserve 826 stable check IDs; retain strict status vocabulary; keep later-phase checks blocked until their own reviewed check-ID evidence exists; require owner, evidence, and recheck trigger for every exit-permitted deferral; keep recovery input ordering exact and fail closed; update code, tests, generated matrix, plan contracts, and finding ledger together.

**Ask First:** Any change that activates a currently inactive route, changes public API compatibility, modifies live metadata/runtime state, or weakens a P0/P1 blocker into advisory status.

**Never:** Modify the unrelated 7-12 operator-guide change; rewrite historical Bootstrap output; mark Phase 0B/1-6 verified from historical evidence; remove the `import_gdd_form` deferral; treat Bootstrap evidence as BH-HANDOFF authority.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Permitted Phase 0A deferral | 207 verified plus one owned/recheckable explicit deferral | Phase 0A exit prerequisite is satisfied; later checks remain blocked only on their own missing evidence or route dependencies | Missing owner, evidence, or recheck keeps Phase 0A unsatisfied |
| Prompt-producing repair | Parsed route profile and selected skill prompt block | Both appear in ordered recovery inputs and have independent authority/hash identities | Either source missing or mismatched fails closed |
| Matrix regeneration | Current evidence index and plan sources | 826 stable IDs, 207 verified, 1 explicitly deferred, 618 blocked, with no false “Phase 0A unverified” gaps | Check-only fails on drift or unstable IDs |

</frozen-after-approval>

## Code Map

- `scripts/python/build_gdd_to_module_acceptance_matrix.py` -- phase-exit prerequisite projection and generated gaps.
- `scripts/python/tests/test_build_gdd_to_module_acceptance_matrix.py` -- stable-ID, status-count, and deferral-aware gate regression tests.
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/02a-route-state-artifacts.md` -- normative recovery source and hash contract.
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/schemas/workflow-action-contracts.v1.json` -- exact `run_needs_fix` sub-operation inputs.
- `PhaseA.Platform/Workflow/HostedRouteRecoveryContract.cs` -- runtime recovery-order authority.
- `PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs` -- authority-source key normalization and fail-closed validation.
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/96-global-review-standard.md` -- durable closure ledger for the three confirmed findings.

## Tasks & Acceptance

**Execution:**
- [x] Update matrix projection so an audited Phase 0A deferral satisfies only the Phase 0A prerequisite while later rows await their own evidence.
- [x] Add `selected_route_skill_prompt_block` after the parsed profile in common and repair recovery contracts, including independent source-hash identity.
- [x] Update runtime recovery order, authority-key normalization, fixtures, and exact-order negative tests.
- [x] Add durable ledger rows for all confirmed Bootstrap P1 findings and record traceable closure evidence.
- [x] Regenerate matrix Markdown/JSON and run targeted plus full relevant regression.
- [x] Execute Standard Self-Review, Whole-directory review, then a new isolated Bootstrap review run.

**Acceptance Criteria:**
- Given the permitted import deferral, when the matrix is regenerated, then no later row claims Phase 0A is unverified and no later row becomes verified without explicit evidence.
- Given any prompt-producing repair contract, when exact recovery inputs are validated, then profile and selected skill prompt block are separate ordered authorities and omission fails.
- Given the complete 7-07 directory, when Whole-directory and Bootstrap reviews finish, then the three prior blocker IDs have traceable dispositions and no unresolved P0/P1/P2 remains before Phase 0B evaluation.

## Spec Change Log

## Design Notes

The phase prerequisite is a gate over allowed exit dispositions, not a demand that every row equal `verified`. An explicit deferral can satisfy the predecessor gate only when its evidence record is complete; it never manufactures completion for the deferred check or downstream work.

## Verification

**Commands:**
- `py -3 -m pytest scripts/python/tests/test_build_gdd_to_module_acceptance_matrix.py` -- matrix semantics and counts pass.
- `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --no-restore --filter "FullyQualifiedName~RouteModuleContractsTests|FullyQualifiedName~ProjectRouteStateArtifactServiceTests"` -- runtime recovery contract passes.
- `py -3 scripts/python/build_gdd_to_module_acceptance_matrix.py --repository-root C:/jimuyun --check-only` -- generated matrix is current.
- Whole-directory mechanical review plus a new `$run-phase-bootstrap-review` run -- zero unresolved P0/P1/P2.

**Results:**
- PhaseA targeted regression: 211/211 passed.
- PhaseA full regression: 1407/1407 passed.
- Matrix validation: 826 stable check IDs; 10/10 Python tests passed; check-only passed.
- Standard Self-Review and Whole-directory review passed with zero open ledger findings.
- Bootstrap implementation-conformance review `7-07-conformance-20260713-200456` finalized `clean` with zero accepted or rejected candidates.
