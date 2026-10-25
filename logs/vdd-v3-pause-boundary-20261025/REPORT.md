# Public V3 pause boundary

Approval: Sentinel_994707de86808191a4ad36d536154631 (2026-10-25 03:39 UTC).
This step implements and validates the boundary only. Original r3 compilation was not resumed. No real model, BMAD skill/reviewer, A/B, implementation, Acceptance, push/PR or CI ran. All CLI tests used disposable /tmp repositories, deterministic fake advisory adapters and fake authors over the actual native host request/response protocol.

## Reviewed minimal behavior

The existing CLI had no safe V3 stop. Authority ran V3, V3A and execution preflight and then entered V4 unconditionally. Existing V1/source caches remain reusable, but transient advisory request context can change raw worker keys. Merely saving a stage label or cancelling the first V4 request would not be normal pause or establish reusable V3 candidates.

The public CLI now accepts --stop-after v3 for ordinary create/resume. It completes native V3 worker validation and normalization, V3A semantic preflight and V3 execution preflight, then returns status=paused, stage=V3, next_stage=V4-atomic-recall, exit0 and authorizes=[]. No V4 stage or canonical plan-ready/compiler-state publication occurs at that boundary. A timeout, cancellation, malformed result, current security refusal or failed preflight remains repair-vdd with failure exit semantics. Already-completed output cannot be relabeled paused. Fixture/recommendation/published/handoff/candidate-repair modes cannot create these pause checkpoints.

The unfinished plan remains draft. No lifecycle transition, implementation permission or acceptance claim is added. Default compilation without the option still proceeds through the original gates.

## Resume without regenerated valid V3

A new small module stores the returned native V3 raw candidate only after both V3 preflights pass. The content-addressed record under .compiler-work/v3-checkpoints binds repository/output scope, current source index, full obligations, profile and V3 compiler/validator rules by actual bytes. It contains a candidate digest and authorizes=[]; it is not a receipt or saved instruction pointer. Original raw caches/receipts and history are untouched.

On explicit --resume-from first-failed-stage, current query/security and V0/V2 run first. Only an exact matching candidate may be replayed; its digest, native schema/domain/execution/path validity, deterministic normalization and both preflights are checked again. Corruption blocks without replacement model requests. Source/domain/rule changes miss the saved candidate and fall back to normal current compilation and its matching native caches. Git-only provenance does not invalidate this content binding. Deleting a current owner fails closed. A later V3 correction invalidates in-memory replay so a V4-directed repair cannot be hidden by the earlier candidate.

This module does not import author drafts, consume pending answers, synthesize old receipts, or bypass V4. The original305 drafts still need actual future native request binding. Native V3 caches and the new candidate retain their own ownership; this is not Quick Dev execution-proof reuse.

## Changes

Eight files, isolated in changed-files.json and STEP-DELTA.patch against this step's preserved before/ bytes:

- scripts/vdd/compile_plan.py: explicit option, mode restrictions, scoped candidate replay and normal paused exit.
- semantic_compiler_authority.py: boundary after both preflights and before V4.
- new semantic_v3_checkpoint.py: content-bound native candidate persistence/revalidation; no new plan lifecycle authority.
- new tests/test_public_v3_pause.py: bounded public CLI fake-author positive/negative cases.
- VDD SKILL.md, planning-operation.md and lifecycle-state-contract.md: stop/resume rules and explicit non-authority.
- ADR-0041: the authorized bounded pause decision.

No Quick Dev, business-query implementation/config/budget, frozen requirement/contract or original author draft was edited. Existing unit-budget implementation and ledgers are retained; no old aggregate watchdog was used.

## Actual validation and evidence

Final code: pause-final-v2.log records14 passed in10.06s. compatibility-final.log records11 public source-cache recovery tests passed in8.69s. package.log records22 package unittests passed; skill-validation.json reports ok with empty findings. These are targeted fixtures and static package checks, not real planning or business-test execution. Earlier public-first.log (7 pass), public-final.log (22 pass on the earlier iteration) and additional-negatives.log (3 pass) remain diagnostic history, not extra final-code coverage counts.

The final14 pause cases establish:

- public normal pause after V3/V3A/execution preflight, with no V4 stage and no canonical state;
- default public compilation still reaches plan-ready in a disposable fixture;
- public resume reaches downstream publication with zero new V1/V3 author requests, while current V0/V2/V3A/execution preflight rerun;
- Git-only change reuses the candidate and pauses idempotently, with0 new author requests;
- a changed source re-extracts/rebinds its obligation and requests a current V3 contract, preserving the old checkpoint;
- candidate tamper, semantically invalid body even with recomputed candidate digest, and deleted current owner fail;
- cancellation and invalid native V3 output never become successful pause;
- completed plans cannot be relabeled paused;
- current security refusal still blocks before candidate replay;
- unresolved dependency fails actual execution preflight and saves no pause candidate;
- recommendation/fixture modes are rejected before execution.

fixture-native-results/ preserves actual compact native pause/resume results, checkpoint and progress. fixture-request-counts.json inventories the corresponding fake-author request IDs/output names. The fixture has one source and one obligation: source_content_replays=2 counts native lookups, not two unique sources or model calls. No real-r3 cache hit or V3 acceptance is claimed. Preservation hashes cover the original draft, corrected copy, original V1/index and unchanged prior repair inputs.

## Proposed public commands (not executed)

NEXT-COMMANDS.txt contains the same real r3 requirements and six companions, original output/profile and explicit old V1 session witness, using a new live caller session and --stop-after v3. It also gives later continuation by omitting --stop-after. No session initialization or command in that file was executed. A separate user decision is required before either real execution.

The existing per-unit1800 total/600 genuine-inactivity supervisor and cumulative retry policy remain in force. No workflow round1800 watchdog should wrap recovery. Business query30/60-second limits are unchanged.

## Limits and stop

Linux, deterministic fake-author/public CLI and short processes only. No Windows run, true-model generation, real r3 cache consumption, native V4 semantic review of this requirement, actual305-contract acceptance, implementation or final acceptance was performed. Checkpoint hashes are local content/integrity bindings under the trusted maintainer model, not authentication against a party rewriting both code and storage. Current validators and future V4 retain responsibility for semantic correctness.

This approved step is complete and stopped. No real recovery or next stage was started.
