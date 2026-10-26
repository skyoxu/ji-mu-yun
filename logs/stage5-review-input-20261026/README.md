# Fixed local inputs for the stage 5 external review

This prepares inputs only. No reviewer, tests, compilation, native gates, BMAD, Acceptance, CI query, publication or model-setting action was run. Existing evidence is read unchanged. This directory is outside the previously frozen test/snapshot inputs.

## Candidate identity and completeness

- Repository: skyoxu/ji-mu-yun; branch `review/vdd-quick-dev-scoped-plan-20261025`.
- Local HEAD: `d86539b9602d9cff7cfe1d96ae6a58b287ce7b3d`; Git tree: `a89cf95ab0b58cafa4b0bf3c17bdbec7e9f00828`.
- Last published implementation-entry baseline: `965df2e34f71ef197fffd8afb68f037688486ca2`. Current remote state was not queried; the local origin/review tracking ref is absent.
- **HEAD is not the complete review candidate.** manifest.json binds actual current bytes: 1708 files / 149918237 bytes of referenced source and evidence. 201 are byte-identical in HEAD, 1506 absent from HEAD, and scripts/vdd/compile_plan.py is modified from HEAD. This is a hash inventory, not a newly created archive or regenerated execution proof.
- The two current active tests are untracked; the 26-file current successor is untracked; most execution/source logs are ignored. Their absence from git status does not mean absence from the candidate.
- Excluded unrelated dirty file: `execution-plans/2026-08-18-toolchain-workflow-repair/skill-input/prestart-40-output/skill-input-context.v1.json`. Two earlier untracked repair-attempt plans are inventoried only in worktree-status.txt, not selected as current plans. No changes were reverted, staged or committed.

## Review starting points

1. Current range: `logs/scoped-input-preparation-20261024-v3/README.md`, `SCOPE-SOURCE.md`, `DEPENDENCY-APPROVAL.md`, `old-to-draft-map.json`, `deployment-ledger.md`, the seven `inputs/*.md` files and source/role bindings. The classification ledger is `logs/requirements-scope-classification-20261024/classification.json`: 246 retained, 59 reduced, 25 deployment-side; 305 current obligations and all 330 historical IDs remain traceable.
2. Original requirement text: `_bmad-output/planning-artifacts/prds/prd-bmad-vdd-knowledge-query-2026-10-22/sources/bmad-vdd-knowledge-query-requirements.md`. Delivered PRD/SPEC/architecture sources are bound in manifest.json as historical provenance. Their historical BMAD duties are not restored and are not instructions to invoke BMAD.
3. Current plan: `execution-plans/2026-10-25-vdd-knowledge-query-caller-runtime-role`; semantic bundle SHA256 `7b4c69ff7e4a64bafbc3a8d6dd0ed4c83c1ab3c21935bd1f9d3e581f5e583276`. Read its handoff-repair and `logs/quick-dev-s10-runtime-role-20261025/` for the narrowly authorized successor and preserved real RED/Q4/GREEN history.
4. Current completion: `logs/quick-dev-final-slices-20261025-v6/REPORT.md`, `final-proof-summary.json`, `completion-metrics.json`, `evidence-index.json`, and `Q8/implementation-complete-result.v2.json` / `terminal-input.v2.json`. Native Q8 passed exit 0 in 388.415 seconds; 12 current Q7/terminal and 610 runtime tuples. The existing 114-entry evidence index hashes all match; the frozen three source files and plan hash also match. These are byte checks only, not rerun gates or a new independent review.
5. Changes: change-list.json lists both the 11 committed post-publication host paths and full main-to-HEAD scope. Current implementation overlay is compile_plan.py plus the two active tests. Four local host commits contain environment-v2 isolation, Q6 argv handling, Q7 and Q8 invocation-local deduplication. The skill body was not changed by the latest Q8 repair; shared-execution.md was. Current VDD/Quick Dev skill bytes are included through the source inventory.
6. Genuine Windows artifact: `logs/quick-dev-s4-20261025/windows-original/parent-original.zip` and original extracted records, with the S4 report's coverage limitation. It covers its unchanged runtime subset, not all later compiler/Q8 code on Windows.

## Known failed fixture and impact boundary

`logs/quick-dev-q8-performance-fix-20261025/targeted-v2.xml` and corresponding stdout retain the failure of `scripts.quick_dev.tests.test_public_budget_transfer::test_owner_q8_reuses_success_but_rejects_failed_stale_and_changed_cases`: `ValueError: unapproved Q8 owner adapter bytes: .agents/skills/quick-dev-tdd-adapter/tools/behavior_routing.py`.

The separate legacy-fixture-baseline-attribution.json records current and pre-repair 93d06e67 bytes both SHA256 `26e967ece795d54cdc4df4ac6f181872a41b31f24315ba03d515fd8033317cf6`, versus the old adapter pin `c5e6d9402e456866299c51be9f21d17c9f1a20c93dcdeb67459342994638750f`. This is static baseline attribution; the old baseline test was not rerun. The unrelated adapter was not repaired or its pin relaxed. The 25 relevant focused tests plus one native integration passed, and the actual current plan Q8 passed. Do not turn that into a claim of all-repository compatibility success; external reviewers must assess this explicit limit.

## Supported read-only retrieval and present delivery gap

The current tools support reading these paths through the already authorized local executor. A review session attached to this **same environment** can open manifest.json and hash-check each required file before reading it; absolute paths are supplied per item. Git object reads are valid for `same_bytes_in_HEAD=true` entries only. Read-only GitHub fetch_file/fetch_blob/fetch_commit tools can retrieve published objects, not local uncommitted/ignored files or an unpushed local HEAD.

There is **no confirmed cross-session transfer of this new complete candidate**. Do not tell an external session that a GitHub branch/HEAD URL contains the complete stage 5 implementation or proof. If the existing external review session cannot access this environment, its missing overlay/evidence must be supplied later through a separately authorized supported route. This preparation step did not push, create a PR, upload Library files, contact the review chat, or place anything at a new external destination. The external chat URL is a destination reference, not proof of workspace access.

The previous published README/publication-manifest are retained as history and describe the earlier planned-test repair. Their old “tests absent / implementation incomplete” statements must not be used as the current candidate identity.

All selected original bytes remain where they were. The manifest detects later drift; it does not promise that an unstored working tree is an immutable Git snapshot. Work is stopped after this preparation.

## Critical current byte identities

| File | SHA256 | In HEAD with these bytes |
|---|---|---|
| logs/quick-dev-final-slices-20261025-v6/REPORT.md | 5203efd923e818393959ca241bf6a635b2c8fd71c27f62c49ea1841c7518cce6 | False |
| logs/quick-dev-final-slices-20261025-v6/evidence-index.json | be3d1c0f703562456972bd7a426e06ef7ac955d444bb51760eeef94b32a006c4 | False |
| logs/quick-dev-final-slices-20261025-v6/Q8/implementation-complete-result.v2.json | 9a6620fc66ec0530475b4b60396ab8e7888d6e73147c54aae4210055ff2c5f20 | False |
| scripts/vdd/compile_plan.py | 679442ba962e808fff3576a8c1fd32ec9e50135407191084ce6d62500e61167a | False |
| scripts/toolchain/knowledge_query/tests/test_planning_query.py | 71926958969db6cf07c0c636468585dfba31d46d03d190bcd55cdf97c880215d | False |
| tests/toolchain/knowledge_query/test_planning_boundaries.py | 830f3f9f62913d8287a35d2e5fdf3e298a79447b5b08dd52bd5196f81646c480 | False |
