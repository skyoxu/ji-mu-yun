# Restricted VDD primary binding repair

ADR-0041. Local host-only commit: 5b585094288f1958539d88261d78467865cfe8e7. No push, BMAD, external reviewer, CI or Acceptance. The existing dirty caller-record overlay in compile_plan.py and unrelated original dirty context were preserved outside the host commit.

The opt-in mode changes only explicit primary pytest module OR-filter bindings. Default mode control flow is unchanged when no option is supplied. Unsafe/unbound/missing/forbidden/production targets, unsupported argv, incomplete CER mappings, illegal option combinations and corrupt predecessor state reject. Other commands, owners, writes, requirements, oracle and assertion coverage remain unchanged.

New focused verification: 23 passed. Existing declaration/role/default handoff regression: 44 passed and 4 old CLI fixture packaging failures before tested logic (missing workflow_unit_budget). Providing the existing scripts dependency via PYTHONPATH for those four fixtures produced 4 passed; no oracle or source changes. The initial failures remain in old-regression.xml/stdout. VDD Skill validation passed and its existing 22 unittest cases passed. These are targeted regression results, not proof of all VDD functions or zero regression risk. The 45 unrelated per-slice historical replay fixtures were not rerun.

Public native successor: execution-plans/2026-10-26-vdd-knowledge-query-p1-static-bindings. Canonical SHA256 aab95b0036eea778b6651714309c7f9e8d005b0eeabfd07185cf6584cd825c7e. Native source, semantic, feasibility, final and handoff checks passed, V1/V4 reused, model_called=false. preservation.json restores only S1/S12 primary commands and then compares the complete bundle equal to its predecessor; source-index bytes and all305 obligations are unchanged.

Tests: exactly22 equivalent literal rows; all existing function ASTs/oracles unchanged except the equivalent decorator. Actual collection preserves all619 old native collected node IDs, including the22 parameter IDs, with seven added P1 cases (626 total). See test-equivalence.json and raw collection. A first author-side import insertion indentation error was corrected before native freeze; the failed collection is retained.

Native inspect-selection reports complete-static-case-mapping: S1=20 and S12=525 complete required nodes. Q6/terminal still bind the entire shared module, and S12 additional commands remain unchanged. The generic Quick Dev parser/judge/RED matching were not modified.

The active boundary test provenance guard now recognizes only this exact five-file host child and separately pins the preserved combined caller CLI bytes. It does not rewrite the prior publication inventory. Native business execution continues separately under logs/stage5-p1-native-20261026.
