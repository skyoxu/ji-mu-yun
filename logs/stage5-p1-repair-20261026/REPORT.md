# Two-P1 repair: authorized S1 role completed; new execution-selection boundary

This step is stopped under the user's instruction to report newly required host/contract scope. Neither business fix has been applied yet. No formal RED, Q4, GREEN, new Q7/Q8, model worker, BMAD, A/B, Acceptance, push or CI run occurred.

## Completed authorized change

The actual public compiler command is retained in role-command.json; stdout/stderr are raw native output. Exit 0, status plan-ready. Successor: `execution-plans/2026-10-26-vdd-knowledge-query-p1-role-repair`. File SHA256: `33140e79b1ad0902363289c183ce7816e998b86675e83054176abfc37cb3b761`; native semantic identity: `sha256:33140e79b1ad0902363289c183ce7816e998b86675e83054176abfc37cb3b761`.

Only S1 changed. The original FI-6BF12A63835A semantic-contract-gap remains, with new separate FI-121539D49FA8 expected-red authority for A-988348C16D10 / KQ_2E09F07252E1. S12's FI-A94AB82A3798 / KQ_C442B3B56FCE was already expected-red and is unchanged. V1/V4 were actually reused, with zero model calls. All 305 obligations are byte-value identical, the sole Acceptance difference is A-988348C16D10.red_intent_ids, source-index bytes are identical, and eleven other slices are identical. See role-and-selection-preservation.json and the native handoff-repair.v1.json; no plan was hand-authored.

Both business fixes still target adapter.py, with tests confined to the existing shared planned test module. The preceding four failing / three passing diagnostic cases are reused, not reexecuted. The frozen 1708 original-source/evidence hashes still match. The old worktree and all historical receipts remain intact.

## Newly confirmed native execution boundary

Actual public `inspect-selection` outputs for the new plan are S1-selection.stdout.json and S12-selection.stdout.json. Both commands report `reason=dynamic-parameter-values`; their selected argv are exactly equal. They select the shared test_planning_query.py through the same global -k expression, which contains both test_contract_2e09f07252e1 and test_contract_c442b3b56fce. The public inspection executes no tests and writes no execution proof.

The concrete first fallback is test_contract_f96ecd3253a2's BinOp/list-comprehension parameter declaration at the existing line 337. It carries no required assertion for either S1 or S12, but case_selection.literal_nodes parses it before excluding irrelevant function parameters. dynamic-selection-static.json records the AST location and per-slice non-membership. The literal resolver is additionally passed the raw pytest option/value sequence by stable_runner._descriptor_inputs; a proper narrow fix must preserve supported -k selection semantics rather than treating options as paths. The latter is source analysis, not a newly observed execution failure.

Native independent_judge_v2.judge_receipt accepts formal RED only when process-wide observed_failure_ids exactly equals the descriptor's expected set. It does not merely filter away failures from other executed assertions. stage verification also requires all nonterminal argv/cwd/target/fixture values equal the original probe descriptor. Thus, after both genuine test additions are frozen, the shared process would emit KQ_2E09F07252E1 and KQ_C442B3B56FCE, while S1 declares only the former. This is a static consequence of the real counterexamples and exact source-bound checks, not a claim that a new formal RED was run or rejected.

It would be wrong to hide or suppress the other test's failure, borrow its marker, edit a frozen descriptor/receipt, change argv between probe and RED, or claim that an unexecuted scoped run passed. Sequentially changing the shared test file to expose one issue at a time would contradict the requested combined freeze and create further invalidation; after the first adapter edit, existing full-file Windows checks also cannot pass with the old artifact. No such workaround was attempted.

## Minimal next scope decision

The minimal recommended addition is a separate narrow execution-selection repair: resolve only statically admitted cases for this slice while preserving the declared pytest target/selection bounds; unrelated dynamic parameter declarations must not unnecessarily defeat a provably complete mapping. Unknown or relevant dynamic constructs must still fail safely to the original selection. Supported -k handling must preserve its actual semantics and reject unsupported interpretations. Keep Q6 and terminal's full declared coverage, all case identities, exact failure-ID admission, snapshots and authorization checks unchanged. Validate that independent missing assertions select their own cases and that unsupported/dynamic/ambiguous or deselected cases cannot be silently dropped. Do not introduce a producer/evaluator compatibility protocol or rewrite old evidence.

This would touch the shared selection implementation and its focused tests/necessary guidance, beyond the single-role and two adapter changes expressly approved for this step. It has not been implemented. An alternative is an explicitly approved two-slice VDD execution-binding repair if the existing public producer can express it without semantic reauthoring; no such override was invented or used. Only after that boundary is resolved should both active test additions be frozen, then actual native probe/RED/Q4/GREEN proceed in dependency-safe order.

## Evidence impact and Windows boundary

The earlier proof-impact-static.json remains valid: all twelve saved main/regression and twelve terminal requests inventory-bind adapter.py and the shared test file. Real changes invalidate those content bindings, independently of Git provenance. The new plan identity also differs. No old proof was relabeled for this successor and no costly whole-plan refresh was launched prematurely. Old Q7/Q8 passes remain historical facts for the old candidate, not completion of this successor or the still-unfixed P1s.

The existing real Windows artifact still binds adapter.py's entire old hash. WINDOWS-NEXT-COMMAND.json records the exact six-selector command from its original supervision (thirteen actual cases), 1800/600 limits and existing verification branch/workflow/windows-latest runner. The existing local verification workflow is available, but the present instruction does not authorize a new push or dispatch. After final code/test freeze, a separately authorized delivery/run must produce current Windows originals; the user monitors it. No CI query, dispatch, new runner/credential or false Linux substitute occurred.

## Actual work and stopping point

New native execution this step: one bounded deterministic VDD role repair, plus two public read-only selection inspections. Reused: valid V1/V4 and the previous 7-case counterexample run (4 real failures / 3 controls), current source/index and Windows originals for diagnosis only. New business test processes, formal RED/GREEN and model calls: zero. The isolated diagnostic runtime restored in the prior step is available; it is not asserted identical to the lost old /tmp environment.

No production, current active test, Skill or host source was changed. Only the native successor and append-only local repair records were created. All processes are complete. The increment is ready for a decision on this newly identified narrow selection boundary, not a new A/B round.
