# Bound planned-test declaration repair: production self-check

Approval: Sentinel_9834a5d1716c81918af8ea9399636fd0 (2026-10-25 05:11 UTC).
Frozen predecessor:dadd5ea869108893bdfe014c75a06c363b720cc9.
No push, PR, merge, CI query/monitoring, model, BMAD skill/reviewer, external A/B,
Quick Dev implementation or final Acceptance ran in this step.

## Self-review and minimal repair

The earlier P1 is confirmed:the published tree lacks two active .py test files,
but all12 slices had planned_new_files=[]. Original12 native Q1 rejections and
the diagnostic positive controls remain in
logs/vdd-q1-planned-tests-repair-20261025/. No local unpublished tests were used
to hide the published-tree defect.

The existing public handoff producer now has explicit repeatable
--handoff-planned-test <path>. It selects a declarations-only branch, not the
normal dedicated-test/RED-role repair. It changes only each affected slice's
planned_new_files and derived slice_input_hash. All non-slice bundle fields,
including all305 obligations, full305 Acceptance contracts, all305 failure
intents, contexts, commands, allowed write paths, owners, memberships,
dependencies, routing projection and terminal predicates are exactly unchanged.
No file, marker, runtime role, receipt or observed behavior is manufactured.

Allowed paths must already be bound by slice snapshots, actual pytest argv and
selector intent, and must be missing normalized pytest files under a test
segment. Production/rollback ownership overlap, unbound/forbidden paths, metadata
roots, existing files/directories, symlink/parent symlink, non-directory ancestors,
HEAD/index tracked deletion (including staged deletion), duplicates and unsafe
path forms reject. Partial declarations leaving another missing snapshot
undeclared also reject. This mode creates no new GREEN/write scope. Mode
combinations with role, launcher or custom test-root repair reject. The original
repair_bundle function is byte-identical to the predecessor; default dispatch
retains its existing behavior.

Six source/doc/test files changed (changed-files.json and STEP-DELTA.patch):

- scripts/vdd/compile_plan.py:explicit argument, mode checks, native dispatch.
- quick_dev_handoff.py:bounded declarations-only producer branch and delta.
- tests/test_planned_test_declaration_handoff.py:deterministic unit/public tests.
- VDD SKILL.md and planning-operation.md:admission, reuse and non-authority rules.
- ADR-0041:the maintainer-approved restricted repair decision.

## Actual native successor

FINAL directory:execution-plans/2026-10-25-vdd-knowledge-query-planned-tests-repair-final.
Semantic bundle SHA256:sha256:955bca2628a236468cb12b236d2d51f26a62944f18fbdb3d7f8c7716a3ce8b5c.
Public native status:plan-ready / exit0; model_called=false;12 slices.
The final public producer completed in 0.999s. Exact argv and producer
file hashes are in verified-launch.json; native-verified-result.json and the
final producer's handoff-repair.v1.json are genuine native outputs.

The producer reads the immutable source-index, complete semantic alignment and
atomic-recall witnesses, reuses V1/V4, and runs V0A, V2, V3A, V7 feasibility,
semantic-chain, final contract validation and native Quick Dev handoff checks.
All are valid with no findings. Source-byte rebindings=[], new RED roles=[],
command dispositions=[]. No V1-V4 model regeneration occurred.

The exactly two declared tests are:

- scripts/toolchain/knowledge_query/tests/test_planning_query.py (10 slices)
- tests/toolchain/knowledge_query/test_planning_boundaries.py (S2/S5)

Both remain absent. Their archived original texts are unchanged and were not
restored. These are future new-scope Q2 authoring inputs, not executed tests.
All original predecessor files remain byte-identical. Source identity stays
sha256:4bdddaa521eca69d49354e1e801b18e16b6481b27f3a41f96a78b35673bba322.
Native identities were produced by the public owner, never hand-filled.

Two earlier local native outputs are preserved as intermediate attempts while
metadata-path and partial-declaration negatives were tightened. They have the
same semantic bundle identity because the lawful two-path output did not
change. Only the -final directory is the final candidate for next-step use.
No intermediate plan was pushed or used to rewrite the frozen predecessor.

## Actual targeted checks and reuse

- targeted-final-v3.log:32 passed in1.79s, including safe declarations,
  non-mutating/idempotent repair, unsafe and non-test paths, unreferenced or
  mismatched command/selector, forbidden/production/rollback paths, existing
  files, metadata roots, symlinks, ancestor files, tracked/staged deletions,
  duplicates, partial declarations and public option restrictions. The public
  fake-author fixture proves native successor publication and V1/V4 reuse;
  no true model or business test is invoked.
- default-compatibility.log:3 passed,55 deselected. Default repair semantics,
  historical role behavior and Windows launcher handling remain covered; no
  full old suite or long native business flows were rerun.
- package-final.log:22 Skill-package unittests passed. skill-final-validation.json
  reports ok with empty findings.
- Actual final12 slices:read-only validate_planned_preflight() returns
  planned-contract-valid for12/12 in the real published-tree workspace, with
  model_called/tests_executed/writes_performed all false. See final-q1-results.json.
- The earlier original12 negative results are reused, bound to the unchanged
  original bundle bytes; an additional undeclared-path control after the first
  native successor still rejects. The new partial-declaration negative prevents
  publishing another known gap. Q1 source code is byte-identical to dadd5ea.
- final-verification.json / final-plan-delta.json prove all305 obligations,
  full acceptances, failure intents and all non-slice fields unchanged, with
  only planned_new_files and slice_input_hash changed for12 slices.

The real public step and controlled fixtures are short. Existing independent
unit1800-total/600-genuine-inactivity and bounded retry behavior were not changed.
No business query30/60-second budget was modified.

## Limits and stop

The P1 is technically repaired and production self-check passes. This is not an
independent A/B closure or permission to implement. Q1 only proves the planned
contract is valid; no test body, actual probe, RED/GREEN/terminal/Q8 or runtime
Windows execution has occurred for the new plan. Clone/Windows producer
compatibility was not newly exercised; Linux deterministic/public checks are
recorded honestly. Old unrelated selective-cache limitations remain untouched.

The new code/Skill changes and final successor are LOCAL and uncommitted.
Remote review branch still points to dadd5ea, the old NO-GO baseline; it does
not yet contain this fix. The unrelated prestart-40 worktree modification and
all prior evidence are preserved. No model-setting change was made.

This approved single step is complete and stopped, waiting for the next user
decision. Do not use either the old predecessor or an intermediate attempt as
the repaired final plan.
