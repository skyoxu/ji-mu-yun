# Implementation Evolution Report

This append-only report records implementation corrections and terminal validation results for Bootstrap Review operability hardening. It is non-authorizing and excluded from normative candidate hashes.

## 2026-08-07 Plan Evolution: Cross-Control-Plane Routing

- Input: `docs/review1.md`, consumed as a maintainer-provided VDD update request.
- Scope: preserve `BROH-001..BROH-007` and add `BROH-008..BROH-024` through authority-separated control-plane slices `BROH-S4..BROH-S7`; implementation remains one AI-led maintainer session.
- Boundary: the plan remains `self-hosted` but is currently `draft`-blocked by the stale knowledge catalog; this update does not publish `plan-ready` or `implementation-authorized`, does not create Bootstrap evidence, and does not run semantic review.
- Compatibility: the historical implementation baseline remains `49c5cff216646cf82179d906db60426d5f1ef314`; current authority is reread from `67e8fba68e2b5ce18036c05226cfa0519890b4ff` without rewriting historical evidence.
- Ownership: Acceptance owns review requirement decisions, Bootstrap owns semantic execution, Quick Dev owns implementation completion, and Acceptance remains the owner of `acceptance-passed`.

## 2026-08-07 Plan Evolution: Semantic Review Tightening

- Input: `docs/know9.txt`, consumed as a maintainer-provided VDD refinement.
- Added constraints: deterministic facts are frozen before semantic review; typed risk lenses never reduce Artifact View coverage; valid zero-finding discovery is a clean first-class result; semantic review stops after the current question is answered and focused-verifier failure remains repair, not discovery escalation.
- Implementation mapping: these refinements extend `BROH-S4..BROH-S6` and add fixtures without introducing a new owner or parallel execution-plan directory.
- Authority: all new artifacts remain non-authorizing; the knowledge-catalog freshness blocker remains unchanged.

## 2026-08-08 Plan Evolution: Single-Maintainer Execution Closure

- Candidate freshness now binds `HEAD`, tracked diff bytes, untracked file content manifests, command registry, authority manifest, contract, and validator bytes; contract-only reuse is rejected by the adapter root comparison.
- The plan-local `stage_projection_builder.py` is present because `run_slice_lifecycle.py` loads it unconditionally. Its projection is generic to this plan and records immutable stage hashes plus the current candidate identity.
- S0-S6 now terminate through structured plan-local `validate_slice.py` predicates. Ordinary unittest commands remain GREEN/REFACTOR inputs; they are no longer misused as JSON terminal predicates.
- `validate_implementation.py` is the separate Quick Dev terminal predicate. It checks explicit implementation authorization, current contract-bound slice evidence, command/fixture composition, and plan tests; it emits `implementation-complete` only as a non-authorizing predicate and never launches Bootstrap or Acceptance.
- The plan remains AI-led and single-maintainer: no parallel-owner coordination, external requirement injection, or hidden authorization is introduced. The knowledge-catalog blocker and all fail-closed gates remain unchanged.

Validation evidence for this repair: `validate_plan.py` PASS; plan-local tests `19/19` PASS; Quick Dev adapter contract PASS; S0 invocation build PASS; `git diff --check` PASS. The implementation terminal was exercised in negative mode and correctly returned `implementation-authorization-required:draft` plus missing slice evidence; it did not publish authority or launch another skill.

## 2026-08-08 Plan Evolution: Real Current-Session TDD Bridge

- Correction: the earlier controlled-probe description is superseded. S0-S7 use one named real target test per slice for both RED and GREEN; no `controlled_red_probe.py` command remains registered.
- Execution: the plan-local bridge freezes the complete exact write set, pauses for the AI maintainer's test/documentation edit, observes RED, pauses for the production edit, then observes GREEN and REFACTOR before evaluating the registered predicate.
- Solo boundary: implementation remains one AI-led maintainer session. The bridge launches no implementation model, creates no parallel owner, and consumes no external requirement source.
- Snapshot boundary: every slice declares all exact production, test, and documentation paths. A caller that supplies only the first path fails closed. `persistent_plan_loop.py` is therefore prohibited for this plan; `loop_plan_directory.py` is reinvoked once per phase with the full path set.
- Integrity: completed controller state is continuity only and cannot mask contract, registry, bridge, result, stage, projection, recovery, attempt-ledger, event-chain, or protocol-binding drift.
- Module isolation: plan-local validators load their sibling `validate_all.py` by absolute file identity, preventing a previously loaded execution plan from supplying the wrong candidate-identity implementation.
- Repair validation: `validate_plan.py` PASS; plan-local tests `31/31` PASS; Quick Dev adapter contract PASS; shared Quick Dev adapter tests `68/68` PASS; all 12 plan-local Python sources compile; `git diff --check` reports no whitespace error. Quick Dev routing still fails closed with `KWI-QUICK-FROZEN-CONTEXT-STALE`, and the implementation terminal still rejects the current `draft` state plus missing S0-S7 evidence. No Bootstrap run, lifecycle authorization, or implementation evidence was created.

## 2026-08-08 Plan Evolution: Four-Phase TDD And Dependency Freshness

- Correction: the three-call bridge is superseded by four current-session calls. RED accepts only declared test changes, GREEN accepts only declared production changes, and documentation or other declared cleanup occurs between GREEN and the observed REFACTOR stage.
- Dependency freshness: each `slice-ready` binds direct predecessor result hashes plus slice-scoped contract, command, authority, validator, and closure roots. An upstream successor invalidates dependent results without making downstream edits reopen an upstream slice merely because the slices share a production file.
- Recovery: bridge protocol drift starts a new run linked by `predecessor_run_id`; historical run evidence remains append-only and the controller state remains non-authorizing continuity data.
- Solo boundary: all four edit points belong to the same AI-led maintainer session. Bootstrap's concurrent reviewer wave remains semantic-review execution owned by Bootstrap and does not introduce parallel implementation owners or external requirement injection.
- Repair validation: `validate_plan.py` PASS; plan-local tests `37/37` PASS; Quick Dev adapter contract PASS; shared adapter tests `68/68` PASS; all 12 plan-local Python sources compile; `git diff --check` reports no whitespace error. The route still fails closed with `KWI-QUICK-FROZEN-CONTEXT-STALE`, and the implementation terminal rejects `draft` plus missing S0-S7 evidence as expected. No TDD run, Bootstrap run, lifecycle authorization, or external requirement input was created.

## 2026-08-08 Plan Evolution: Command-Side-Effect And Terminal-Guard Closure

- Correction: the bridge now captures a complete Git worktree manifest immediately before and after every observed or auxiliary command. RED permits only declared tests, GREEN only declared production paths, REFACTOR the complete declared write set, and REFACTOR pre-observation plus terminal commands must produce no worktree delta. Any undeclared tracked or non-ignored untracked path fails closed.
- Correction: S7 terminal acceptance now has a bridge-owned stable guard. It independently checks the projection root, stage-result hashes, stable validator hash, contract/slice/run identity, current slice freshness snapshot, terminal predicate fields, and `authorizes=[]`; it does not invoke the mutable `validate_implementation.py` logic.
- Validation: plan-local tests `39/39` PASS; `validate_plan.py` PASS; Quick Dev adapter schema validation PASS; shared adapter tests `68/68` PASS; plan-local sources compile; `git diff --check` reports no whitespace errors. The plan remains `draft` and knowledge-catalog-stale, with no implementation or Bootstrap evidence created.

## 2026-08-08 Plan Evolution: Explicit Planned-New-File Contract

- Correction: S4 now declares its three intentionally new Acceptance files under `planned_new_files`; all other slices declare an empty list. The plan validator rejects any missing write-set/snapshot path not covered by that explicit declaration.
- Bridge boundary: a declared new test must exist before RED observation, declared production/schema files must exist before GREEN observation, and every declared new file must exist before REFACTOR, projection, and terminal validation. This preserves TDD sequencing without creating untracked placeholder files before the run.
- Documentation: the Quick Dev adapter contract now documents this narrow plan-owned exception; wildcard or undeclared missing paths remain fail-closed, and the generic persistent loop remains unsuitable for this current-session bridge.
- Validation: plan-local tests `42/42` PASS; `validate_plan.py` PASS; Quick Dev adapter schema validation PASS; shared adapter tests `68/68` PASS; plan-local sources compile; `git diff --check` reports no whitespace errors.

## 2026-08-08 Implementation Repair: Stable Stage Validator Identity

- Finding: S7 changes `validate_implementation.py`, but that mutable terminal validator was also included in the stage validator hash. RED therefore froze the pre-GREEN hash while the terminal guard required the post-GREEN hash, making the declared S7 lifecycle unsatisfiable.
- Repair: the stage validator hash now covers only the stable plan, slice, bridge, and projection validators. The mutable terminal validator has a separate hash inside the terminal candidate binding, so current terminal bytes remain bound without invalidating RED/GREEN/REFACTOR identity.
- Replay: the shared validator semantic change invalidated every slice, so S0-S6 were replayed before a fresh S7 run. Historical failed and stale runs remain preserved under `logs/tdd-adapter/bootstrap-review-operability-hardening/`.

## 2026-08-08 Overall Implementation Result

- Result: `implementation-complete` passed for BROH-S0 through BROH-S7 after current RED, GREEN, REFACTOR, projection, consumer-closure, and terminal validation.
- Scope: the result is non-authorizing (`authorizes: []`) and does not publish `acceptance-passed`, commit, release, or archive authority.
- Assurance: the terminal consumer closure includes the Bootstrap skill suite, Acceptance review-requirement tests, Acceptance Bootstrap integration tests, and plan-local validator tests. Bootstrap Review and Acceptance were not launched.

## Round 1 Implementation Repair

- Findings: current decision publication accepted caller-authored requirements and risk facts, deterministic evidence incompleteness was routed as `required`, the decision schema revision disagreed with its producer, and required profile selection was not risk-specific.
- Repair: `decide-bootstrap` now accepts only repository-bound prepared-run and deterministic-evidence references; Acceptance replays candidate identity and the repository-owned semantic trigger policy. Current decisions carry producer, policy, candidate, evidence, and decision hashes. Unknown trigger policy input and blocked deterministic evidence fail closed. Workflow-control-plane changes select `bootstrap-skill-route`; ordinary hard triggers retain `bootstrap-implementation-conformance`.
- Provenance closure: route preparation now re-derives the repository-owned decision from the supplied decision request and requires exact equality before routing. This closes the remaining self-hashed hand-authored decision bypass.
- Projection-test closure: the plan-local stage-projection test now creates an isolated Git baseline and explicit candidate modification, rather than assuming the real repository worktree has no declared candidate effects.
- Targeted validation: current Acceptance test suite `251/251` passed; current requirement, schema, package, and Bootstrap integration tests passed. `validate_plan.py` passes and `git diff --check` reports no whitespace errors.
- Plan-local regression: `47/47` passed, including the isolated projection fixture.
- Terminal gap: Quick Dev parent routing succeeds, but `loop_plan_directory.py` stops before slice execution with `KWI-QUICK-FROZEN-CONTEXT-STALE` because the repository knowledge catalog snapshot predates the current main. No new implementation-complete lifecycle state is published and the existing plan state remains unchanged until knowledge freshness is repaired and terminal validation is rerun.
