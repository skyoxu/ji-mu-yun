# V3 Projection And Source-Role Repair (2026-10-19)

Inspected base: 78a9ee44945f5acedcab43df646325e559f9e593 on
fix/08-06-skill-authoring-plan-refresh. This maintenance change repairs the
compiler/input, not Package A implementation. No plan-ready or runtime evidence
is published here. Accepted ADR-0041 owns the preserved authority boundary.

## Confirmed causes and correction

1. Grouped wire, cached internal output and split/recomposed candidates used
   different projection paths. Cache refresh could reject a future production
   owner before its redundant write/planned fields were normalized. They now
   share an environment-aware projection before cache admission and return.
2. An omitted/empty write set could erase a declared production owner when a
   future pytest snapshot was present. The declared owner is now preserved;
   exact supported future owners are written into the returned write/planned
   projections. Arbitrary unplanned missing owners remain invalid.
3. A repair-stage flag or stale rollback path could promote an explicit all-test
   candidate to a production writer. Test-only candidates now retain empty
   production owners. Production-bearing candidates retain their real owner.
4. The final validator repaired a private candidate copy, so a passing check
   could describe fields absent from the returned object. Projection now owns
   those changes before the gate; the gate validates the actual candidate and
   no longer treats an omitted planned-file field as implicitly present.
5. Source-role inspection found a second cause of test-only candidates: the
   Package A input mixed already-existing Q2/RED/Runner/controller instructions
   with new product work. The source index already separated source_text and
   execution_context_text, but V1 received both. V1 now receives semantic source
   and provenance only. NFR scope/handoff instructions and test-authoring rules
   use the existing selector-repair-binding authoring block; V3 retains the full
   frozen context. All 25 product intent rows are byte-identical to the base.

No empty-owner execution mode is added to Quick Dev, and no schema/V6 runtime
gate is weakened. A genuine unsupported test-only executable contract still
blocks. Existing workflow controls must be consumed as planning/write/terminal
constraints by their current owners, not implemented again as Package A product
features or given an invented production owner.

## Verification and limits

- Baseline directed suite: 89 passed.
- Five root-cause regressions first failed on the old projection/gate path and
  passed after repair; a sixth covers inline/internal-form agreement and
  idempotence. Two further source-role regressions prove the V1 seam and the
  real Package A V0-to-V3 context consumer.
- Expanded directed suite: 115 passed across execution-contract, group safety,
  inline/selective cache repair, frozen source projection, source-role transport
  and explicit path-contract tests. Test seams do not claim live model review.
- Additional V0--V7 compiler/cache compatibility and worker-transport suite:
  31 passed. Its injected-worker tests prove deterministic composition only;
  their fixture plan-ready states are not current Package A readiness.
- Skill package validation: ok=true, no findings; its required unit suite:
  22 tests, OK.
- Read-only projection of every committed v7 group cache: 282 records,
  939 candidate contracts; no owner outside write set, no future owner missing
  from planned files and no test path retained as a production owner. This is
  a field-invariant diagnostic, not semantic alignment or plan readiness.
- Inspecting the old domain also found 26 empty-owner candidates rejected by
  the existing nonempty structural contract. Those historical contracts remain
  unchanged; they must not be forced into the changed semantic source domain.
- Native public compiler recommendation/source preflight passes without a
  model call. Full live V1/V3/V4 and downstream publication were not run here:
  this host has no Codex executable or configured model API credential.
- No semantic-plan-bundle.v1.json or compiler-state.v1.json was generated.
  Package A production/test files and all historical compiler evidence remain
  unchanged by this maintenance commit.

## Local continuation

Synchronize this branch and use LOCAL-HANDOFF.md's canonical compile command.
Keep the existing current-plan/ and failed evidence. Let the compiler resolve
current source identity and refresh V1/V3 and downstream witnesses as required;
do not force a stale whole-domain result or fixture cache into the new input.

Do not repeatedly patch final findings, delete evidence or add fake owners.
Any remaining real semantic/source gap must use bounded native repair. Start
Quick Dev only after actual plan-ready and its current Q0/Q1 checks pass.
