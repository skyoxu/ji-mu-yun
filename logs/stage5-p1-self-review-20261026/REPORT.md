# Stage 5 P1 production self-review — stopped at explicit scope boundaries

Both review suggestions are confirmed by real targeted counterexamples. Neither P1 has been implemented yet. This is not a GREEN result or a new external review.

## Frozen candidate and ownership

Reviewed publication: 2abfbccbe532f6d934d3bba36d00c915207f5e38. Source host: d86539b9602d9cff7cfe1d96ae6a58b287ce7b3d plus the frozen intake overlay. All 1708 selected byte hashes and original Git status still match the intake. No reset, production edit, active-test edit, Skill/contract edit, push or PR occurred.

P1-1 belongs to S1, O-5CE45BB6B616 / A-988348C16D10 / ASSERT_2E09F07252E1. Its role FI-6BF12A63835A is semantic-contract-gap, not expected-red. P1-2 belongs to S12, O-B0121F2D245E / A-8692A88997B0 / ASSERT_C442B3B56FCE. FI-A94AB82A3798 already is expected-red. Both allowed production scopes include scripts/toolchain/knowledge_query/adapter.py. The shared planned test path is scripts/toolchain/knowledge_query/tests/test_planning_query.py. Both native public Q1 preflights passed in the restored diagnostic environment.

## Actual reproduction

One supervised diagnostic pytest invocation: **4 failed, 3 passed, zero errors**, 1.33 seconds pytest / 1.718 seconds supervised wall time. Limits stayed 1800 total / 600 inactivity; no timeout or retry. Raw stdout/stderr, JUnit, source and supervision are retained here.

1. Catalog missing, policy missing and projection missing each failed independently. The existing pointer and generation remained present. The real public compile_plan.py main/argument/admission path returned code 0 and reached the semantic delegate instead of reporting blocked integrity. Only the semantic delegate was replaced by a stop/control function, so no model or compiler lifecycle executed. This exposes the public caller boundary rather than mocking the adapter's result. The genuinely uninstalled control (all three artifacts and the index directory absent) passed.
2. The first real query returned a permitted hit and recorded its actual read set. A new isolated content-bound generation narrowed VDD paths, used the actual projection builder, preserved every source byte, and passed the real current-publication verifier. The second call returned the revoked candidate with reused=true, permission_checked=true and only one query call. The current policy/projection eligibility assertion failed. Same-generation reuse and an unrelated bootstrap-only policy/generation change both passed while retaining the original index identity and one actual query call. The fixture creates only isolated input data; it does not fabricate a production publication approval or an execution receipt, and invokes no publisher/Skill/reviewer.

These are diagnostic failing Assertions, **not CER-bound formal RED**. They authorize neither Q4 nor a completion claim. Existing tests missed the first issue by testing diagnose directly, and the second by not tightening permissions in a valid new input generation.

## Self-reviewed minimal repairs, not yet applied

For P1-1, the three-file absence shortcut in prepare_consumption runs before current-publication verification. A surviving publication must never become prepared/not_installed just because one artifact is absent. Preserve genuine absence fallback; return a structured blocked integrity/publication diagnostic for partial/corrupt installed state before the caller reaches semantic work. Do not reclassify corruption as availability.

For P1-2, publication validity and the existence of a consumer policy do not establish continued eligibility of old candidates. Before reusing them, resolve current catalog module/path identity, current policy admission and current projection membership (plus applicable read-source checks). A revoked candidate must not be copied with permission_checked=true. Preserve reuse for unrelated generation changes, keep the original actual-query index identity, and do not force a new query solely because a generation ID changed. The passed control fixtures protect that optimization.

## Why production work stopped under this authorization

The current instruction requires reporting first when a frozen contract change or large native refresh is necessary.

- S1's genuine failure has no expected-red implementation role. The existing public VDD --repair-quick-dev-handoff-from / --runtime-red-intent FI-6BF12A63835A route is the narrow proposed next step: retain the original guard, add one justified runtime role in an immutable successor, preserve all 305 obligations/oracles and source scope. No such repair was executed. Another assertion's marker cannot supply permission.
- Static inspection of the exact v6 saved requests found all **12 regression and 12 terminal** inputs explicitly inventory-bind both adapter.py and the shared test module. An adapter/test edit changes real bound contents, not merely a Git SHA. At least those 24 positive originals cannot be relabeled for the repair. Probe routing, required Q6 commands and additional RED/GREEN/REFACTOR costs must be determined from the legally repaired/finally frozen inputs. S12 has four frozen Q6 commands; S1 has one. No fixed 39-call promise or global restart was made, and no business-suite refresh was started.
- The three existing Windows evidence checks compare the current entire adapter file hash against the 13-test historical ZIP. A changed adapter fails that exact binding even if transport mechanics are otherwise unchanged. Existing proof remains authentic historical Windows evidence, not current proof for new source. A fresh Windows candidate/evidence route would need explicit authorization beyond the current no-push instruction; no CI query or new run was attempted.

To avoid collecting S12 RED/GREEN and immediately invalidating it with a subsequent plan change, stop before production now. Recommended next decision: authorize the single S1 VDD runtime-role successor, then freeze the combined two-finding test surface, run the legal missing branches sequentially, and agree the genuinely required refresh/Windows route before the broader completion refresh. Do not redesign the host or weaken any oracle to reduce this cost.

## Environment and retained evidence

The old /tmp/vdd-pause-tests interpreter no longer exists. The first launch exited 127 before the runner or tests executed; its empty stdout and exact stderr are preserved. A new isolated /workspace/scratch/stage5-p1-tests-20261026 environment supplies the same Python 3.12.14 / pytest 9.1.1 versions with existing jsonschema/PyYAML. Matching version numbers are not a claim of identical environment fingerprints or authority to upgrade old receipts.

Reused sources: existing real publication fixture, source Git objects, projection/core implementations, prior plan and raw v6 proofs. New executions: two Q1 preflights and one seven-case diagnostic pytest process. No native Q2/probe/RED/Q4/GREEN/Q6/Q7/Q8, model, BMAD, reviewer, A/B or Acceptance stage was run. Original v6 hashes still match; the old pass facts apply only to their original candidate/context and do not overrule these reproduced defects.

Incremental review entry: self-review-result.json, test_counterexamples.py, diagnostic-input.json, diagnostic-first.xml, diagnostic-executed.stdout.txt and diagnostic-budget/*.json. proof-impact-static.json records exact per-slice dependency membership, not a native replay. evidence-index.json binds these new local diagnostic artifacts. The source/test/contract candidate remains unchanged. Work is stopped awaiting the scope decision.
