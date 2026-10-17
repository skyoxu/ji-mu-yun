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

## Round 2 Implementation Repair

- Profile closure: `bootstrap-implementation-conformance` and `bootstrap-skill-route` now have distinct scope context contracts. Acceptance derives the skill-route lineage from the repository-bound prepared input, and current route/binding checks reject decision/profile drift.
- Trigger closure: `execution-plans/` and `decision-logs/` are explicit known-low-risk metadata roots. Typed repository risk classes cover public API, database, runtime/deployment, and shared execution boundaries; an implementation path outside every repository-owned class blocks instead of becoming `not_required`.
- Lifecycle closure: resume continuity now names `KWI-QUICK-FROZEN-CONTEXT-STALE`; `implementation-authorized` and pending slices remain unchanged because the lifecycle contract has no blocked implementation state and no current terminal predicate has passed.
- Validation: Acceptance `256/256` passed; Bootstrap skill-route `2/2` passed; `validate_plan.py` passed; modified Acceptance sources compile; `git diff --check` reports no whitespace errors. No Bootstrap run or implementation-complete authority was created.

## Round 3 Implementation Repair

- Identity closure: Acceptance candidate identity now preserves the repository-relative paths carried by the complete candidate manifest. The physical target and frozen snapshot remain custody locations and are not projected back into `changedPaths`.
- Composition closure: a real historical prepared run input and candidate manifest now exercise `load_current_candidate_identity` through `decide_review_requirement`, proving a `.agents/skills/**` path remains workflow-control-plane input and selects `required` plus `bootstrap-skill-route`.
- Authority policy closure: `AGENTS.md`, `docs/adr/**`, and `docs/standards/**` now classify through the existing protected-high-risk trigger before the general documentation low-risk fallback. Ordinary documentation and execution-plan metadata remain deterministic low risk.
- Validation: targeted RED observed the prefixed-path regression; Acceptance `258/258` passed, plan-local tests `47/47` passed, `validate_all.py` passed, modified Acceptance sources compile, and `git diff --check` reports no whitespace errors. No Bootstrap run or implementation-complete authority was created.
- Terminal gap: the only remaining blocker is `KWI-QUICK-FROZEN-CONTEXT-STALE`; refresh the VDD knowledge catalog/context and rerun the Quick Dev terminal predicate before any implementation-complete publication.

## 2026-08-08 Knowledge Freshness Recovery

- VDD knowledge publication completed under maintainer authorization. The refreshed `knowledge-context.v1.json` and freeze receipt bind the current repository main and pass `vdd_knowledge_preflight.py` with status `ready`.
- Quick Dev routing now resolves to `run-slice` for `BROH-S0`; the previous `KWI-QUICK-FROZEN-CONTEXT-STALE` blocker is closed.
- `validate_implementation.py` was rerun and remains correctly fail-closed: current evidence is missing for `BROH-S0` through `BROH-S6`, while `BROH-S7` has invalid recovery/stage bindings. No implementation-complete lifecycle state, Bootstrap run, or Acceptance authority was created.
- Next action is the declared single-maintainer Quick Dev TDD bridge in dependency order, beginning with `BROH-S0`, followed by terminal validation.

## 2026-08-09 Round 4 VDD Repair Contract

- Trigger: the abandoned `bootstrap-runs/r2` transport evidence finalized `BROH-R4-01` through `BROH-R4-03`; no historical review or S0-S7 implementation evidence was rewritten.
- Execution contract: `repair/round-4/implementation-contract.v1.json` is the self-hosted, in-place repair input. Its single executable slice `BROH-R4-S1` owns the new RED for parent-validated segmented Artifact View coverage and runs the two existing fixes as registered REFACTOR regressions. `BROH-R4-02` and `BROH-R4-03` remain distinct legacy-regression obligations because their implementations predate this contract; no historical RED is asserted and no fake legacy slice enters the strict RED lifecycle.
- Closure: re-entry requires current hash-bound root-cause inventory, changed-set manifest, producer/consumer composition receipt, complete review scope, and `repair-closure.json`. The root plan remains the only Acceptance target and keeps lineage family `ria-1dd445581b0a69b5a1432c671bd99844`.
- Lifecycle: the repair contract is `implementation-authorized` by the maintainer and does not alter the completed initial S0-S7 history. Quick Dev may publish only the repair `implementation-complete` result; Acceptance remains separately owned.
- Plan validation: Round 4 validation, root `validate_plan.py`, plan-local validator tests, Python compilation, Quick Dev routing, and a dry invocation build for `BROH-R4-S1` pass. Terminal validation intentionally fails until implementation and hash-bound closure artifacts exist.

## 2026-08-09 Round 4 Implementation Result

- Result: `BROH-R4-S1` reached `slice-ready` through a predecessor-linked Quick Dev RED/GREEN/REFACTOR run, and the Round 4 terminal predicate now passes as `implementation-complete` under owner `quick-dev-tdd-adapter`.
- Segmented coverage: the parent creates stable file/line segments, binds every receipt to the reviewer role and frozen Artifact View, rejects duplicate or overlapping plans, persists successful segment results, and resumes by retrying only the failed transport segment before one formal role publication.
- Regression closure: orphan no-progress process-tree recovery and model-specific fallback access proofs remain green. The finalized-run validator now recognizes and revalidates the exact parent-produced segment contract carried by each request.
- Adapter recovery: the shared stage artifact composer now preserves an explicitly absent planned-new file as the baseline state, so `None -> bytes -> bytes` remains continuous and the baseline manifest does not invent a pre-existing file.
- Acceptance repair completeness: canonical lineage inspection reports zero consumed semantic rounds for `ria-1dd445581b0a69b5a1432c671bd99844`. The Acceptance-owned audit passed with complete baseline/candidate manifests, sibling-callsite inventory, changed-path bindings, a deterministic producer/consumer replay, and current authority/high-risk projections.
- Preserved failures: unsuccessful composition receipts v1-v5 remain append-only evidence of the Windows environment allowlist and nondeterministic-stdout failures. The accepted replay is `composition-receipt.v6.json`; no failed receipt was overwritten or promoted.
- Validation: Bootstrap `195/195` passed; Quick Dev adapter `70/70` passed; root plan validation passed; Round 4 terminal validation passed; the deterministic composition validator and Acceptance repair-completeness audit passed. This result authorizes no Acceptance, commit, release, or archive state.

## 2026-08-09 Round 4 Lifecycle Publication Correction

- Correction: the prior Round 4 result was non-authorizing evidence only. After the latest completed Quick Dev bridge run (`RUN-20260809T042302-530182Z`) and a fresh terminal replay, the repair authority is now published as `implementation-complete` with `state_owner: quick-dev-tdd-adapter`; `BROH-R4-S1` is completed and resume routes to `handoff-to-acceptance`.
- Freshness: the immutable `repair-closure.v2.json` and Acceptance completeness audit remain bound to the current contract and candidate bytes. The older slice-ready reference in that append-only audit is retained as historical validation evidence; it does not replace the current terminal predicate or lifecycle authority.
- Final validation: Round 4 terminal validator passed with `authorizes: []` in its evidence envelope; the lifecycle publication authorizes only `implementation-complete`, never Acceptance, commit, release, or archive.
