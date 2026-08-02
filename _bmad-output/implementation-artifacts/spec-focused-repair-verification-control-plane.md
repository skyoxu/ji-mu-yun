---
title: 'Focused Repair Verification Control Plane'
type: 'refactor'
created: '2026-08-02'
status: 'done'
review_loop_iteration: 0
baseline_commit: '49d6948f8c4f29b1e6f6c94c83f92a9702f8c2a8'
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/docs/adr/ADR-0051-bootstrap-lineage-family-and-bounded-repair-reentry.md'
  - '{project-root}/docs/standards/bootstrap-review-control-plane.md'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** `focused_repair_review` 仍启动三名 reviewer，P2 closure 证明链过重，严格 Quick Dev TDD adapter 又不接受无 `implementation-contract.v1.json` 的 compact/legacy 计划，导致精确修复复验接近首次审查成本。

**Approach:** 保留 Round 1 三 reviewer 与 P0/P1 verifier。修复后先跑 deterministic checks，再由一个独立 focused verifier 核验原 finding、diff 和消费者；仅在新 P0/P1、authority graph 或高风险边界变化时升级。P2-only 使用轻量 closure；Quick Dev 增加输入分发。

## Boundaries & Constraints

**Always:** 新协议只用于新 run；旧 profile/policy/envelope、8-1 和 ADR-0051 保持可重放。Focused verifier 独立，绑定 finding、repair mapping、diff、消费者和 receipts，并可报告 blocker。高成本模型仍需单独确认。新增 ADR 并同步协议与测试。

**Ask First:** 改变 Round 1、P0/P1 gate 后 verifier、安全/权限/数据完整性升级规则、三轮上限，或触碰 Phase runtime/live workspace。

**Never:** 复用 gate 后 `independent_verifier` 冒充 repair verifier；把“缺 contract”直接视为 compact；伪造 contract/TDD evidence；授予 acceptance/commit/release authority；重写历史 evidence。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|---------------------------|----------------|
| 精确修复 | Round 1、无升级触发 | 单 focused verifier | closure 不完整时阻塞 |
| 风险升级 | 任一升级触发 | 三 reviewer full review | 未知事实阻塞 |
| P2/Quick Dev | P2-only 或三类输入 | 轻量 closure 或正确 lane | 高风险延期、损坏 contract 阻塞 |

</frozen-after-approval>

## Code Map

- `docs/adr/ADR-0055-*.md`、Bootstrap standard/index -- 协议与迁移权威。
- `.agents/skills/run-refactor-implementation-acceptance/**` -- repair 路由和 closure。
- `.agents/skills/run-phase-bootstrap-review/**` -- focused role/profile、schema、gate 和 replay。
- `.agents/skills/bmad-quick-dev/**`、`quick-dev-tdd-adapter/**`、`scripts/sc/workflow_model_routing.py` -- 输入分发和四档分类。

## Tasks & Acceptance

**Execution:**
- [x] ADR/standard/skills -- 定义 Round 2、升级、P2 v2 和兼容性。
- [x] Acceptance/Bootstrap code、schemas、tests -- 实现 focused lane 与历史 replay。
- [x] P2 validator/tests -- 轻量 bundle，旧 v1 可读，风险规则不降级。
- [x] Quick Dev router/tests -- 区分 standalone、strict、verified compact、invalid 并复用四档分类。

**Acceptance Criteria:**
- Given Round 1 修复完整且无触发，when 路由复验，then 只授权一个 focused verifier。
- Given focused verifier 报告新 P0/P1 或风险变化，when 计算下一动作，then 升级到三 reviewer。
- Given P2-only 或 compact 输入，when 路由，then 走轻量路径且不新增 authority。
- Given 历史三层 run 与 8-1，when 重放，then 原 policy 和结论不变。

## Spec Change Log

## Design Notes

使用独立 role/route kind；新 policy additive 发布，旧 reader 保留。Quick Dev 只选 lane，严格 adapter 仍要求 contract。

## Verification

**Commands:**
- Acceptance 216、Bootstrap 165、Quick Dev router 5、TDD adapter 61、model routing 19 tests -- 通过。
- Acceptance package validation、2026-07-12 whole-directory、JSON/Python static validation -- 通过。
- `git diff --check` 与 UTF-8 检查 -- 通过。

## Suggested Review Order

**Protocol intent**

- Start with the cost and assurance tradeoff governing every downstream control.
  [ADR-0055:18](../../docs/adr/ADR-0055-focused-repair-verification-and-lightweight-closure.md#L18)

**Focused repair replay**

- Import only canonically replayed focused evidence, never caller-supplied envelopes.
  [bootstrap_integration.py:89](../../.agents/skills/run-refactor-implementation-acceptance/scripts/bootstrap_integration.py#L89)

- Bind Acceptance routing to the replayed producer run and repair closure.
  [acceptance_cli.py:612](../../.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py#L612)

- Freeze the focused profile independently from mutable base-profile revisions.
  [review-profiles.v1.json:703](../../.agents/skills/run-phase-bootstrap-review/references/review-profiles.v1.json#L703)

- Project one verifier's exact closure decisions and escalation triggers.
  [bootstrap_review.py:2696](../../.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py#L2696)

**Lightweight P2 closure**

- Validate exact normal-risk P2 sets with current hash-bound structured evidence.
  [bootstrap_review.py:6366](../../.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py#L6366)

**Quick Dev routing**

- Classify explicit inputs before backend or four-tier model selection.
  [SKILL.md:43](../../.agents/skills/bmad-quick-dev/SKILL.md#L43)

- Fail closed across standalone, strict contract, compact VDD, and invalid lanes.
  [quick_dev_input_router.py:186](../../.agents/skills/bmad-quick-dev/scripts/quick_dev_input_router.py#L186)

**Regression coverage**

- Prove historical focused profiles survive future base-profile changes.
  [test_bootstrap_review.py:3008](../../.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py#L3008)

- Prove Acceptance dispatches focused replay without three-layer artifacts.
  [test_bootstrap_integration.py:69](../../.agents/skills/run-refactor-implementation-acceptance/tests/test_bootstrap_integration.py#L69)
