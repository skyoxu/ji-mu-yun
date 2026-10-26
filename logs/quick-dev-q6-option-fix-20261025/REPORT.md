# Narrow Q6 pytest option parsing repair

## Result
Local host commit b908cb3915cb50c6860445e27c1e1012137e60bb, parent b9c701c1cfe662d679d747533920f992379c4b06. Not pushed.

Q6 previously tested each non-option argv token with Path.is_file(). A 5911-character pytest -k value was consequently treated as a filename and raised ENAMETOOLONG. The new shared operand iterator consumes only the explicit pytest filter/override option values (-k, -m, -o and their long aliases); actual positional paths/node paths, -c file operands and operands after -- remain subject to existing dependency/path checks. Unknown options do not silently consume a following real path. Execution argv and required regressions are unchanged.

Only regression_gate.py and its existing test module are committed. No frozen plan, oracle, evidence gate, model configuration or business production implementation changed.

## Verification
The targeted suite recorded 17 passes and 1 deselection in 1.31 seconds. It covers long -k, inline options, actual files and node IDs, configuration-file operands, positional delimiter, missing filter values, unknown options and retained file dependency tracking. Original two failing reproductions are preserved in before.stdout.txt.

The deselected existing nested consumer-fixture test was also investigated: its subprocess test fails because a legacy TemporaryDirectory targets the read-only filesystem root. The same failure was reproduced using the unmodified b9c701c1 host source. This pre-existing environmental failure was not hidden or fixed as part of the option repair; baseline-nested-result.json and the complete raw outputs remain available.

## Reuse and current S12 evidence
A native read-only existing_result check rejected the old S12 probe because the execution engine binding includes regression_gate.py; changed-engine identity, not merely Git SHA, causes rejection. The old primary regression has 599 passing cases but lacks a completed Q6/stage result after ENAMETOOLONG; it is not upgraded.

S12-r4 on the new host executed a fresh probe: 599 passing cases, 139 present obligations, predicate_result=true. Its test bytes predate S10 authoring and are retained as that exact observation, not relabeled current completion. Q6/Q7/terminal have not completed.

No old receipt or hash was edited. Completed fixture scratch was preserved by verified archives/atomic moves; subsequent pytest successful scratch uses the explicit failed-only retention setting, bound into the new environment. Failed scratch and native evidence remain intact.

## Remaining boundary
This repair grants no new expected-red role or frozen plan authority. S10 authoring and its observed-behavior route are separate; current slice completion still requires the ordinary native gates. No BMAD skill/reviewer, A/B, Q8, Acceptance, remote push or CI operation was performed.
