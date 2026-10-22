# Package A Online Precompile Audit (2026-10-19)

Reviewed base: b99f5df5bc4642a4e9fd5dfc3c6ffcffbd37204e on
fix/08-06-skill-authoring-plan-refresh. This is the maintainer-requested
simulation of VDD planning rules plus bounded repairs. It is not an independent
V4 result, a semantic worker receipt, a published plan or implementation proof.
Current normative input remains ../requirements.md; ../LOCAL-HANDOFF.md owns
the local continuation. This note is advisory, not a compiler companion.

## Scope and authority

Package A retains all 12 original SAS outcomes and all A01--A25 intent IDs.
It implements the static authoring standard, policy/schemas, real validator,
reference fixtures and Package B handoff guidance. Completed 8-05/8-24 owners
are not reopened. Package B, knowledge queries, internal review activation,
Phase runtime/security and sandbox/game work remain separate.

The current source repairs some table-row wording as well as its shared
contract. Earlier notes saying all rows are byte-identical describe the earlier
b99 repair, not this audit. Historical files are never replaced by this note.
The small VDD context-transport repair is toolchain maintenance needed by this
planning input, not Package A product implementation or Package B migration.
Accepted ADR-0041 retains authority, gates and lifecycle ownership.

## Confirmed findings and corrections

| Severity | Finding | Smallest correction |
| --- | --- | --- |
| P1 | A row-level V3 request carried its own frozen table row but not the same file's authoring block, losing concrete future owners, Q2 paths and write boundaries. | Carry the existing V0/V0A-frozen file-level block separately as execution_context_sources; keep source_contracts and obligation refs unchanged. Narrowed repair retains applicable file context. No file is reread or new semantic obligation invented. |
| P1 | Pure terminal-runner rules could be treated as new validator features, while docs-only assertions could acquire an invented executable owner. | A24 now names actual CLI/API integration outcomes. Existing CER/Q7/Q8 execution rules remain authoring constraints. A25/document guards attach to a compatible real runtime lane with separate artifact assertions and non-RED roles. No empty-owner execution mode or fake owner is introduced. |
| P2 | CLI/API shape, inventory eligibility, malformed input and exit-code distinctions were open to incompatible implementations. | Fix the Python signature, sidecar name and explicit strict/inventory decision rules. Unknown invocation/policy/unavailable target is error/2; an inspectable invalid package is fail/1; only absent-sidecar inventory is legacy/3. Argument failures also return structured JSON. |
| P2 | Dependency, database, subprocess and network wording could be misread as runtime execution or host-installation requirements. | Clarify row-local static record/declaration checks. No dependency execution, live version lookup, database drill, process controller or network gateway is added. |
| P2 | Three example outcomes could make a genuine leaf look like a routing Skill. | Distinguish example outcome IDs from actual workflow/child dispatch and its diagram branches. |
| P2 | Test fixtures could reside outside the declared inspection root; no sentinel in stdout did not prove no forbidden content read. | Use an explicit disposable inspection root with byte-identical production policy/schema copies; observe forbidden reads as well as unchanged sentinel bytes/output. Symlink environment failures do not count as passing tests. |
| P2 | Candidate-controlled policy could also supply the expected rule set/limits, making a self-consistent weakened implementation pass. | Freeze independent expected outcomes in Q2. Ignored/mutated policy and dropped rules must be detected by real production calls. |
| P2 | Broad parameter markings could create mixed present/missing obligations or count unexecuted cases. | Preserve independent semantic outcomes and parameter-level CER mappings. No fixed obligation/slice count is imposed. |
| P2 | Shared frozen helpers could be edited by later Q2 work, and whole-module Q6 could select not-yet-implemented later cases. | Reuse frozen bytes or perform native invalidation; target current/predecessor node IDs until a complete group is regression-ready. |
| P2 | The requested terminal limit was 900 seconds but the current stable runner materializes 600. | Align terminal to 600 seconds and pass the supported 300-second caller option for targeted execution. No runner timeout policy is changed. |
| P2 | Requiring a new accepted ADR before any implementation could make creation of that ADR circular. | Existing accepted ADR-0041 governs development. The new standard ADR needs its normal decision before final acceptance and Package B consumption; no test fabricates acceptance. |

No P0 was established. The code repair has three exposing regressions: missing
row-level context, preservation/exclusion by source file, and context filtering
when repair narrows to one file. The old path failed these assertions; the
repaired path passes. These tests replace model execution only as deterministic
transport tests, never as semantic review.

## Remaining first-use execution limitation (P1)

scripts/sc/validate_skill_quality.py does not exist at this baseline. The current
Quick Dev execution contract lets Q2 author tests/helpers/fixtures only and Q4
write production only after a genuine expected RED. V7 admits an explicitly
planned owner but does not materialize a callable entry. Thus the first direct
import/call has no established legal production baseline in this plan. A missing
module, process startup failure or test-local imitation cannot establish the
required behavioral RED.

This was inspected in the real consumer's SKILL.md, execution-operation.md,
q1_planned_preflight.py and red_production_entry_guard.py. No legal first-use
production-materialization owner was found in the current route. The handoff
now exposes this before Q2/probe rather than implying that plan-ready alone
solves it. It does not block source preflight or by itself establish that V7
must fail, but it prevents a promise of immediate first-slice execution.

The next execution owner must resolve the actual first-use entry under an
explicit, bounded native protocol before running that TDD loop. This audit
neither changes Quick Dev nor seeds production outside its current stage.
Do not repeatedly repair VDD Acceptance text to disguise this execution gap.

## Stage-by-stage review disposition

| Stage | Online result | Still required locally |
| --- | --- | --- |
| V0/V0A | Public source preflight passes; all 25 intent IDs and the shared context remain indexed. | Bind the final checked-out source to the real compile. |
| V1/V2 | Manual review retains the 12 SAS outcomes and separates product behavior from existing workflow constraints. | Real extraction, normalized obligations and atomic source recall. |
| V3/V3A | Owner/write/planned/snapshot rules and independent oracles reviewed; real row/context transport regressions pass. | Real workers must author contracts; current deterministic contract gates must validate their actual output. |
| V4 | Manual comparison checks scope and expected assertions. It is not independent of this repair. | Independent semantic alignment and its required native recheck/repair. |
| V5/V6/V6A | Reviewed many-to-many coverage, compatible lanes, dependency direction and per-case mappings. | Native exact cover, partitioning and final stage-scope checks on actual compiler output. |
| V7/handoff | Planned-path and real Python-call requirements are explicit; source paths/ADR collision checked. | Current feasibility, native handoff, plus resolution of the first-use execution limitation. |
| Q2--Q8/Acceptance | Existing ownership preserved; no execution receipts produced. | Real controlled probe/TDD, regression, whole-plan terminal and separate Acceptance. |

## Checks actually run

- Expanded directed source/context, group/execution, inline/selective cache,
  explicit path, total coverage/cohesion, planned-file and Quick Dev handoff
  suites: 192 passed.
- Additional compiler/cache compatibility and worker transport suites:
  31 passed. Their synthetic test fixtures are not current plan evidence.
- VDD Skill package validator: ok=true, ten checks, no findings.
- Required Skill package unit suite: 22 tests, OK.
- Public canonical CLI recommendation/source preflight: recommendation-only,
  recommended_action=compile-v1, model_called=false, writes_performed=false.
  The explicitly requested diagnostic result is under
  logs/08-06-precompile-audit-20261019/source-preflight-final.json.
- Read-only historical comparison: all 2,474 committed current-plan files
  match the reviewed base. No historical report/cache/failure is rewritten.
- A01--A25 remain unique and ordered; there is one balanced authoring block;
  the proposed ADR-0062 path is free. No Package A production module or test
  implementation is created. No canonical semantic bundle/compiler state exists.
- Scoped whitespace/UTF-8 checks passed. Unrelated historical line-ending noise
  in the other 08-18 plan is excluded from this change.

A missing authenticated real model backend still prevents full semantic
compilation on this host. The exact public compiler command remains in
LOCAL-HANDOFF.md; preserve the existing output/history and allow normal
source-bound refresh. Do not inject hand-authored worker fixtures, force old
V1/V3 reuse, rewrite failure history or publish plan-ready manually.
