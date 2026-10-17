# Local VDD restart handoff

Execute this handoff as one `vdd-execution-plan` Skill session. The user has
authorized repair of the existing 08-05 execution plan, including a real VDD
run. Proceed through preparation, compilation and readback without returning
to ask the user to clean caches or select files. Do not start Quick Dev,
production implementation or Acceptance.

## Fixed target and reviewed inputs

- Branch: `fix/08-05-real-skill-replay`.
- Reviewed implementation of the plan amendments: `e2f4fb09337a5f298321df39362d363822771f6c`.
- Existing target: `execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed`.
- Repair working area: its `repair/round-7/` directory. Do not create a replacement TC-D1 requirement tree.
- Read `AGENTS.md`, `knowledge/toolchain-workflow-index.md`, the VDD Skill and
  its operation-specific references. Use the self-hosted profile: the planned
  changes include controlling Toolchain validation/Consumer behavior.
- Read `restart-review.md`, `restart-inputs.json` and the repaired current-plan
  bundle in this directory's parent. The inventory is a read-only comparison,
  not a Skill-input attestation or a new approval requirement.

Run from the repository root:

```text
py -3 execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/review-repair-c9fe289e/verify_restart_inputs.py --require-backend
py -3 execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/review-repair-c9fe289e/repair_plan.py --check
py -3 -m unittest discover -s execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/review-repair-c9fe289e -p test_repair_plan.py -v
```

Use the existing configured backend. Do not print credentials or alter shared
LLM/Phase entrypoints. A changed reviewed input needs inspection of the actual
diff, not automatic restoration over user changes. Missing backend credentials
are a real environment blocker; do not synthesize worker responses.

## Full-package source assembly

Canonical entry:
`_bmad-output/specs/spec-tc-d1-trustworthy-skill-replay-and-evaluation-repair/SPEC.md`.

Consume its four normative companions (requirements-and-acceptance,
domain-contract, authority-and-open-questions, atomic-obligations) and both
adopted companions (Architecture spine and PRD addendum), with their declared
roles. PRD prd.md is provenance only; the informative addendum cannot introduce
new product requirements. The inventory pins the seven files and selection
pointer, with selection hash
`sha256:9fcc56d354a7fad51219a02a03a1614e4d2153311496a5593ee8bbc58734503a`.

Before invoking the compiler, assemble one unambiguous compiler-readable input
within round-7, using the Skill's permitted input preparation. Retain original
requirement IDs and map every included rule back to its original file/section.
This projection is derived transport, not a replacement specification. Preserve
every FR/NFR consequence, historical A01-A17 duty, guardrail and adopted
architecture invariant. Do not use only the atomic table, treat absent mentions
in that table as removals, or pass duplicate FR/NFR anchors as independent
requirements. Explain and check consolidation of duplicate references.

Carry the following already-reviewed interpretations through V1 and V3, not
only through a prompt or a terminal-summary field:

1. AO-17a/O-C1E267D7452D: every derived artifact kind has explicit authorizes=[];
   any non-empty value fails regardless of authenticity, and missing/malformed
   fields fail. Include an empty-array control. Lifecycle-owner approval is
   separate. Bind the real Toolchain boundary, not Phase auth or knowledge
   publication auth.
2. AO-09e/O-B9EAA8169232: rebuild the original binding from referenced bytes,
   verify equality before launch, and actually execute a fresh positive replay
   bound to that same identity. Missing/mismatched originals reject before
   launch. A reject-all implementation, echoed identity, skipped launch, silent
   rebinding or reused historical output must fail.
3. FR-9: full, non-empty Consumer Manifest reconciled bidirectionally with real
   repository calls, including VDD, Acceptance and workflow-model-routing.
   Preserve four real route transitions and Prior identity/verdict/diagnostic
   restoration. A route-reachability-only test is insufficient.
4. Keep PhaseA/runtime/Hosted/account/sandbox and installed BMAD/GDS forbidden
   paths outside production owners, allowed writes and rollback writes.
5. C3 remains OPEN; use the existing historical validator source and no Consumer
   exception. Block only decisions relying on unconfirmed approval, not all
   unrelated obligations. Do not assign approval to the user merely because
   they authorized this VDD run.

## One fresh canonical compilation

Preserve current-plan/, review-repair-c9fe289e/before/, old .compiler-cache/,
worker traces and prior compiler results. Allocate a fresh timestamped output
under `repair/round-7/recompilation/`, so old completed-resume and V1/V3/V4
responses cannot shadow the repaired input. No manual user cleanup is needed.

Invoke `scripts/vdd/compile_plan.py` as a process from the repository root, with
the assembled requirements path, fresh output path, `--profile self-hosted`,
and `--result-json` inside that new run. Use the Skill's existing bounded repair
and progress reporting. Do not call compiler internals as a publication path,
inject historical/synthetic worker PASS replies, hand-author plan-ready, or
run the direct repair helper over the newly compiled output.

The final directory may have different content-derived IDs and slice numbers.
Review by source duty and behavior rather than demanding old S14/S19 numbers.
Keep the previous current-plan intact and record which new compiler output is
the candidate for subsequent work; do not imply that the old path became ready.

## Final readback and handoff

After the real compiler returns, check its exit code and result status, then
read the newly published obligations, acceptances, failure intents, both
coverage projections, slices, behavior routing and agent contexts. Verify the
five rules above semantically. Positive controls must appear in actual
acceptance/oracle and failure-intent coverage; added assertion labels alone
are insufficient. Run the repository's deterministic package/plan checks
required by the selected Skill profile and `git diff --check`.

Archive real stdout/stderr, commands, result and validation under logs/. Record
current source/content identities, Windows results and any remaining C3 scope.
Only report plan-ready if the real canonical compiler and required readback
passed. This is plan readiness, never implementation-complete or Acceptance.
If unsuccessful, report the exact first remaining blocker and preserve the
failed run; do not suppress it to satisfy the one-session goal.

Commit and push the scoped prepared inputs and real run artifacts to the same
branch when complete, preserving concurrent changes. Return commit SHA, output
directory, compiler result, verification result and any remaining conditions.
