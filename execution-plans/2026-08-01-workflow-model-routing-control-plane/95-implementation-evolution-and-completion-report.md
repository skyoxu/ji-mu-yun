# Implementation Evolution And Completion Report

Plan: `workflow-model-routing-control-plane`
Profile: `self-hosted`
Authority: non-authorizing, append-only implementation continuity report

## Initial Entry - 2026-08-01

- Result: plan source created and validated.
- Lifecycle: `plan-ready` only.
- Implementation: not authorized and not started.
- Protected path: `scripts/sc/_llm_backend.py` requires explicit approval before
  an implementation write.
- Existing work: Bootstrap model-policy and Refactor Acceptance dirty changes
  are preserved as external in-progress dependencies.
- Next action: maintainer decides whether to publish
  `implementation-authorized` after reviewing this plan.

This report cannot authorize implementation, acceptance, commit, release, or
archive. Later entries append corrections and final implementation outcomes;
they do not rewrite this entry.

## Controlled Negative - 2026-08-01

- Command:
  `py -3 execution-plans/2026-08-01-workflow-model-routing-control-plane/tools/validate_implementation.py`
- Observed result: nonzero with `failure_family=implementation-not-present`.
- Missing set: the canonical policy, decision schema, shared router, shared
  router tests/evaluation, and the three consumer integration test modules.
- Interpretation: expected RED before implementation; authorizes nothing.

## Pre-review Knowledge Freshness Repair - 2026-08-01

- Trigger: Bootstrap prepare rejected the frozen Locator result because five
  rejected candidates had stale worktree read-set bytes.
- Repair: superseded the frozen knowledge context with a narrower published
  query for `repository-rules` and
  `standard.repository-maintenance-agent-protocol`; the prior context and
  receipt remain content-addressed history.
- Validator: plan readiness now verifies the VDD freeze receipt and the full
  Locator candidate worktree read-set using the shared validator consumed by
  Bootstrap.
- Lifecycle: remains `plan-ready`; no semantic review round was consumed and
  implementation remains unauthorized.

## Implementation Authorization - 2026-08-01

- Authority: the maintainer explicitly authorized the complete implementation,
  including the protected `scripts/sc/_llm_backend.py` path.
- Lifecycle: advanced to `implementation-authorized`.
- Execution route: direct plan-slice execution because the compact VDD plan
  intentionally has no `implementation-contract.v1.json` and therefore cannot
  enter the Repository Maintenance TDD Adapter.
- Next action: implement RMR-S0 through RMR-S4 and publish no later lifecycle
  state until the terminal validator passes.

## RMR-S0 - Decision And Policy Kernel

- RED: `test_workflow_model_routing.py` was absent and the registered command
  failed with `Errno 2`.
- GREEN: 6 policy contract tests passed.
- Result: the versioned observe-only registry, route-decision schema, closed
  model/effort vocabulary, ownership checks, and deterministic decision kernel
  now exist.
- Authority: no lifecycle transition; router evidence carries
  `authorizes=[]`.

## RMR-S1 - Shared Launcher And Capability Boundary

- RED: the launcher test target was absent after the existing backend suite
  passed 6 tests.
- GREEN: backend tests passed 7 tests and launcher tests passed 7 tests.
- Result: the shared shell-free launcher binds UTF-8 stdin, full model ID,
  effort, and sandbox through `run_llm_exec`; requested/actual identity drift,
  missing capability proof, and hidden fallback fail closed.
- Protected path: the explicitly authorized `_llm_backend.py` change only adds
  policy effort parsing coverage for `xhigh` and `max`.

## RMR-S2 - Quick Dev Four-Class Router

- RED: `tools/tests/test_model_routing.py` was absent.
- GREEN: 5 routing tests, 11 plan-directory-loop tests, and 3 Skill contract
  tests passed.
- Result: Quick Dev emits one highest-match typed decision for
  `small_mechanical`, `normal`, `complex`, or `architectural`. Unknown or
  contradictory facts block upward, upgrades are allowed, and unsafe
  downgrades are rejected. The adapter has no provider execution API.

## RMR-S3 - VDD And Acceptance Consumers

- RED: both registered consumer routing test modules were absent.
- GREEN: VDD routing passed 3 tests, Acceptance routing passed 4 tests, the
  shared policy suite passed 10 tests, and Acceptance package regression passed
  7 tests.
- Result: VDD projects its existing profile without a second classifier;
  Sol/max requires a closed recovery trigger plus exact capability and shadow
  evidence. Ordinary Acceptance uses `launchMode=none`; only closed recovery
  triggers request Sol/high. Bootstrap remains an external profile owner.
- Preservation: no existing dirty Acceptance core file was modified.

## RMR-S4 - Shadow Evaluation And Migration

- RED: the registered evaluation test module was absent.
- GREEN: 4 evaluation tests passed. All three changed Skill folders passed the
  Skill Creator quick validator.
- Evidence: `logs/workflow-model-routing/2026-08-01/shadow-report.v1.json`.
- Result: synthetic contract replay records predicate quality, latency, and
  cost but grants no activation authority. Luna and Sol/max both remain
  `keep_disabled` because exact-surface capability and representative execution
  evidence are unavailable.
- Migration: ADR-0037, the shared execution architecture, and the repository
  maintenance standard now define observe-only rollout, separate child launch,
  no current-session replacement, no fallback, and Bootstrap ownership.

## Terminal Implementation Validation - 2026-08-01

- Initial replay: the outer 120-second command budget expired while the full
  Bootstrap suite was still running; no test failure was reported by that run.
- External diagnostic: the repository-wide knowledge integration aggregator
  failed only in an old knowledge-plan publication replay due Windows long
  paths and intentionally stale frozen authority hashes. Its current Locator,
  VDD, Quick Dev, Bootstrap, and Refactor Acceptance checks all passed. The
  routing plan terminal list was corrected to run those current consumer
  knowledge contracts directly instead of validating an unrelated old plan.
- Final command:
  `py -3 execution-plans/2026-08-01-workflow-model-routing-control-plane/tools/validate_implementation.py`.
- Final result: PASS in 162.2 seconds; all 13 registered commands returned zero,
  including the complete 152-test Bootstrap suite.
- Lifecycle: `implementation-complete`.
- Authority: does not authorize `acceptance-passed`, release, or archive.

## Refactor Implementation Acceptance - 2026-08-01

- Acceptance target:
  `execution-plans/2026-08-01-workflow-model-routing-control-plane`.
- Bootstrap lineage: `ria-77945989035b122f005c98a2c3661cd2`.
- Round 1: `logs/ci/2026-08-01/wmr-r1c`, finalized `blocked`.
- Round 2: `logs/ci/2026-08-01/wmr-r2`, finalized `blocked`.
- Round 3: `logs/ci/2026-08-01/wmr-r3`, finalized `blocked`; the current v3
  validation envelope replayed successfully.
- Independent verifier result: confirmed P1 findings
  `BSR-70B71A7460628393`, `BSR-9BC70F2A4289C44C`, and
  `BSR-E5FA31807675B5D1`.
- Shared failure: repair completeness binds current targeted-test bytes in the
  candidate manifest but accepts a controlled composition receipt that binds
  only producer and consumer bytes. A changed targeted test can therefore
  reuse a stale successful receipt and still produce `status=passed`.
- Bounded route:
  `repair/bootstrap-round-3/manual-pause-route.v1.json` projects
  `routeKind=manual_pause`, `semanticRoundsConsumed=3`, and
  `nextFullReviewRound=null`.
- Lifecycle remains `implementation-complete`; `acceptance-passed` is not
  authorized. Round 4 and successor-based budget reset are forbidden. Resume
  requires an explicit supersede or incompatible-scope decision for a genuinely
  different acceptance target.
