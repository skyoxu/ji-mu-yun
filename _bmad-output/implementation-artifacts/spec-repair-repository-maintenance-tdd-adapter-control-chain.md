---
title: '修复 Repository Maintenance TDD Adapter 控制链'
type: 'bugfix'
created: '2026-07-16T16:45:00+08:00'
status: 'done'
review_loop_iteration: 0
baseline_commit: '8c29ef64f5fa726bc9bbed8a453a55fa96bd5a81'
context:
  - 'AGENTS.md'
  - 'agentbuild.txt'
  - '.agents/skills/vdd-execution-plan/references/strict-vdd-standard.md'
  - 'execution-plans/2026-07-12-llm-review-evidence-gate-hardening/09-bootstrap-review-operator-guide.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 计划文档声明了严格 VDD/TDD/Bootstrap 分权，但机器状态忽略 Round 3 `manual_pause`，candidate/Bootstrap 时序循环，slice、schema、acceptance、authority 和 clean-checkout 证据绑定不足，因此当前 `plan-ready` PASS 不能授权实施。

**Approach:** 保留三层所有权，按 state → contract → validator → fixture/test → slice → ledger 修订完整目录。修订后仅允许 `plan-repair-verified`；在外部 policy decision 解除 manual pause 前继续阻断 plan-ready 和全部实施 predicate。

## Boundaries & Constraints

**Always:** 历史 Review/repair evidence 只读；机器权威可从干净 checkout 复现；S2 只证明 lifecycle，S6 生成 candidate，外部 Bootstrap 后由 S7 acceptance；validator 变化必须带单规则负例。

**Ask First:** 需要修改目标目录外的 Bootstrap policy、Phase protected paths、产品代码、运行时配置或历史 evidence 时停止。

**Never:** 不启动 Round 4，不把本地 validator 当作语义 closure，不晋升 7-07/7-11，不依赖 ignored `logs/**` 作为必要机器权威。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Manual pause | Round 3 authority current | repair predicate 可通过；实施 predicate 阻断 | 稳定 manual-pause rule |
| Candidate | S6 尚无 Bootstrap 结果 | 验证当前 TDD/candidate，只授权 review | 拒绝 stale identity |
| Acceptance | S7 收到 candidate 与 finalized review | 交叉绑定并检查 disposition | 拒绝 identity/open finding |
| Clean checkout | raw logs 不存在 | durable projection 足够验证 | 拒绝缺失/过期 projection |
| Slice proof | 文件存在但行为证据缺失 | slice predicate 失败 | slice-specific rule |

</frozen-after-approval>

## Code Map

- `schemas/plan-state.v1.json`、`00-index.md` -- blocked/manual-pause 状态与入口。
- `implementation-contract.v1.json`、`schemas/implementation-contract.v1.schema.json` -- slice phase 与 stage invocation。
- `schemas/acceptance-contracts.v1.json`、`authority-manifest.v1.json`、`clarification-decisions.v1.json` -- 新机器权威。
- `tools/rmap_checks.py`、`slice_guards.py`、`evidence_guards.py`、`validate_all.py` -- deterministic gates。
- `fixtures/fixture-cases.v1.json`、`tools/tests/test_plan_validator.py` -- mutation 与回归。

## Tasks & Acceptance

**Execution:**
- [x] 机器化 manual pause，并增加不授权实施的 repair predicate。
- [x] 增加 durable clarification/shadow projection、authority manifest、acceptance registry。
- [x] 完整化 schema，拆分 command descriptor 与 stage 期望。
- [x] 重构 S2/S6/S7，移除 presence/global-scan gate。
- [x] 强化 candidate identity、requirement quality、phase mapping、spec delta。
- [x] 增加负例/单测并运行 fresh 与 clean-checkout-equivalent 验证。
- [x] 处理独立 Blind Hunter / Edge Case Hunter 的可执行证据 findings：收紧 TOCTOU、scoped identity、stage/recovery、candidate/Bootstrap、authority 与 acceptance 绑定。

**Acceptance Criteria:**
- Given 当前 Round 3 authority，when 请求实施 predicate，then 非零退出且无实施授权。
- Given 修订目录，when 请求 `plan-repair-verified`，then 全部计划检查通过并排除更高权限。
- Given 声明 mutation，when 执行 fixture，then 命中精确稳定 rule ID。
- Given raw logs 缺失，when 验证，then durable projection 仍足够且必要 source 不位于 `logs/**`。

## Spec Change Log

- 2026-07-16 review patch batch: 保留 manual-pause、S2/S6/S7 时序和 clean-checkout projection；修补验证中途漂移、无关 worktree 误失效、stage 伪造、candidate 任意哈希、Bootstrap 协同伪造、authority inventory 缩减及 acceptance/fixture rule 漂移。已知坏状态是仅检查非空字符串、同名 sidecar 或文件存在。KEEP：`plan-repair-verified` 仍不授权 plan-ready/实施/交付，Round 4 仍未授权。

## Design Notes

`blocked` 是正确仓库事实。repair predicate 只证明被阻断计划内部一致，不能重置 Review 轮次或改写 Bootstrap disposition。

独立审查条目按当前消费者后果去重。目标目录内直接可达的绑定缺口作为 patch 修复；要求执行未来 S1/S2 产品输出语义、或把已有外部 Bootstrap runner 再复制进本计划的建议不在本次 repair predicate 权限内，并由 manual-pause 与外部 Bootstrap 所有权继续 fail closed。

## Verification

**Commands:**
- `py -3 execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validate_all.py --predicate plan-repair-verified` -- pass，无更高授权。
- 同命令 `--predicate plan-ready` -- nonzero，manual pause。
- `py -3 -m unittest discover -s execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/tests -p "test_*.py" -v` -- 38/38 通过。
- 全 fixture loop -- 32/32 invalid/mutation 命中各自唯一 rule ID。
- 独立临时 Git clean snapshot -- 2,912 个文件，完整 composite PASS，运行后 tracked status 为空。

## Suggested Review Order

**Authorization boundary**

- 从唯一 composite 入口理解 manual-pause、TOCTOU 和结果 envelope。
  [`validate_all.py:212`](../../execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validate_all.py#L212)

- 查看 Round 3 projection、closed authority inventory 和 acceptance 绑定。
  [`authority_guards.py:21`](../../execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/authority_guards.py#L21)

**Evidence identity**

- 查看 scoped worktree identity 如何排除无关漂移。
  [`validate_all.py:168`](../../execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validate_all.py#L168)

- 查看 stage 哈希、时序、exit 与 recovery lineage 校验。
  [`slice_guards.py:35`](../../execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/slice_guards.py#L35)

- 查看 candidate artifact 与可信 Bootstrap profile 的交叉绑定。
  [`evidence_guards.py:32`](../../execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/evidence_guards.py#L32)

- 查看这些约束在机器 contract 中的显式声明。
  [`implementation-contract.v1.json:732`](../../execution-plans/2026-07-15-repository-maintenance-tdd-adapter/implementation-contract.v1.json#L732)

**Regression proof**

- 查看无关漂移、TOCTOU、stage 与 clean review 的回归测试。
  [`test_plan_validator.py:273`](../../execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/tests/test_plan_validator.py#L273)
