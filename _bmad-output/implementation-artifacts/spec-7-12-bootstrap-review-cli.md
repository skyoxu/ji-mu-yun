---
title: 'Add 7-12 bootstrap review CLI for manual upstream reviews'
type: 'feature'
created: '2026-07-12'
status: 'done'
review_loop_iteration: 0
baseline_commit: '09a378b8e77cda24900bd048101c31a218a371bb'
context:
  - 'execution-plans/2026-07-12-llm-review-evidence-gate-hardening/00-index.md'
  - 'execution-plans/2026-07-12-llm-review-evidence-gate-hardening/07-implementation-phases.md'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** 7-07 and 7-11 need the 7-12 evidence-gated review rules before either upstream refactor can finish, but the current plan delays all usable review capability until both handoffs exist.

**Approach:** Add a plan-local, read-only Bootstrap Review CLI that prepares manual reviewer prompts, validates manually saved outputs, deduplicates candidates, prepares independent verification, and finalizes machine-readable sidecars without invoking reviewers or integrating the production pipeline.

## Boundaries & Constraints

**Always:** Keep executable code and machine contracts inside the 7-12 directory; read target repositories/scopes without mutation; bind every run to current artifact hashes and route/policy revision; allow zero findings; write run output only to the user-selected directory; preserve historical 7-07/7-11 findings unchanged.

**Ask First:** Any change to `scripts/sc`, `_bmad/custom`, AGENTS.md, README.md, Phase shared LLM/Codex entrypoints, protected runtime paths, or upstream plan/code files.

**Never:** Invoke Blind Hunter, Edge Case Hunter, Acceptance Auditor, verifier, Codex, BMAD, or GDS automatically; treat bootstrap evidence as BH-HANDOFF or production gateway authority; rewrite upstream ledgers; modify `summary.json` or `agent-review.v1`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Prepare | Review ID, profile and scope paths | Input manifest, three prompts and output templates | Fail before writing on invalid/out-of-repo scope |
| Gate clean | All required reviewer outputs contain zero findings | Final clean result and metrics | Missing required layer produces incomplete, never clean |
| Gate candidates | Manual outputs contain evidence-backed candidates | Accepted candidates, rejections, dedup and verifier prompt | Stale hash, wrong line/evidence or incomplete proof is rejected |
| Finalize blockers | Verifier decisions cover every P0/P1 | Confirmed/advisory/refuted/unverified dispositions and final result | Unknown/new IDs, missing decisions or invalid class/status fail closed |

</frozen-after-approval>

## Code Map

- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/00-index.md` -- authority and bootstrap routing.
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/07-implementation-phases.md` -- R0A-R0D execution order.
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md` -- manual operator workflow.
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/schemas/` -- reviewer/verifier output contracts.
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/bootstrap/review-profiles.v1.json` -- trusted bootstrap policy assignment.
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py` -- prepare/gate/finalize CLI.
- `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/tests/test_run_bootstrap_review.py` -- deterministic regression suite.

## Tasks & Acceptance

**Execution:**
- [x] Update the 7-12 plan to authorize a plan-local Bootstrap Review lane and add RFG ownership/coverage.
- [x] Add reviewer output, verifier output and bootstrap profile machine contracts.
- [x] Implement prepare, gate and finalize commands without any LLM invocation.
- [x] Add exact-evidence, stale-input, required-layer, dedup, zero-finding and verifier tests.
- [x] Add a copy-paste operator guide for 7-07 and 7-11 manual execution.

**Acceptance Criteria:**
- Given a 7-07 or 7-11 scope, when prepare runs, then no target file changes and manual prompt/template artifacts are produced.
- Given missing, stale or unsupported candidate evidence, when gate runs, then the candidate is rejected with a stable reason and cannot block.
- Given all required layers completed with zero accepted findings, when gate runs, then the result is clean.
- Given accepted P0/P1 candidates, when gate runs, then finalization remains incomplete until manual verifier decisions are supplied.
- Given complete valid verifier decisions, when finalize runs, then final sidecars satisfy the 7-12 schemas and no upstream ledger is modified.

## Spec Change Log

- 2026-07-13: Confirmed EGR-4D81ADCF17D5F6C5 exposed a Bootstrap coverage gap; reviewer outputs now bind required/read/missing artifacts, incomplete mandatory context maps to failed layer, and the gate rejects false completed coverage. KEEP: no-quota policy, scope-only evidence, supplemental authority, and independent P0/P1 verification.

- 2026-07-12：实现后确定性验证补齐 pending template、UTF-8/binary scope、context/evidence scope binding、canonical policy revision、supplemental authority sidecar 和 finalize 幂等性；未运行任何 reviewer，也未生成 7-07/7-11 审查结果。

## Design Notes

Bootstrap is a temporary execution surface, not a second review standard. R1 must promote the same schema revision and fixtures into long-term owners instead of re-deriving another contract.

## Verification

**Commands:**
- `py -3 -m unittest discover -s execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/tests -p "test_*.py"` -- expected: all bootstrap tests pass.
- `py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py` -- expected: Whole-directory PASS.

**Result:** 17 个 Bootstrap 回归测试通过；Whole-directory plan validator 通过；临时仓 `prepare → gate → finalize` 烟测为 clean，目标 scope SHA-256 前后相同，authority class 为 `supplemental_bootstrap`。

## Suggested Review Order

**执行边界与事实门禁**

- 从只读、hash-bound 的 prepare 入口理解 Bootstrap 运行模型。
  [`run_bootstrap_review.py:230`](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py#L230)

- scope-bound context 校验阻止审查证据越界。
  [`run_bootstrap_review.py:342`](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py#L342)

- gate 执行 Schema、证据、去重和 required-layer 判定。
  [`run_bootstrap_review.py:591`](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py#L591)

- finalize 独立核验 blocker，并保持生产 result 合同兼容。
  [`run_bootstrap_review.py:662`](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/run_bootstrap_review.py#L662)

**操作与防回归**

- 手工操作指南给出 7-07/7-11 的复制即用流程。
  [`09-bootstrap-review-operator-guide.md:1`](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md#L1)

- Whole-directory validator 固定 profile、无自动调用和测试覆盖约束。
  [`validate_whole_directory.py:544`](../../execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py#L544)
