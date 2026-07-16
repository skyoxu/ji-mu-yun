---
title: '修复 Repository Maintenance TDD Adapter 五个 P1'
type: 'bugfix'
created: '2026-07-16T01:35:00+08:00'
status: 'blocked'
review_loop_iteration: 3
blocking_state: 'manual_pause_after_round_3'
baseline_commit: '9e20de93290872521220c78e8d1ac4b69b886555'
context:
  - 'execution-plans/2026-07-15-repository-maintenance-tdd-adapter/00-index.md'
  - 'logs/ci/2026-07-16/review-gateway-bootstrap-repo-maint-tdd-final-20260716-0129/review-dispositions.json'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 计划在 authority 文档哈希不可比较、contract 不符合声明 schema、typed path 越界、嵌套 glob 穿透 forbidden set、RMAP-S0 退出证明不可达时仍可获得 `plan-ready`。五项均已由独立 verifier 确认为 P1。

**Approach:** 把五项作为一个控制链批次：先增加稳定 RED 测试与 fixture，再修复 contract、schema、command registry、validator 和受影响文档，最后生成新的 hash-bound `plan-ready` 证据。

## Boundaries & Constraints

**Always:** 保持 readiness、acceptance、handoff、release 权限分离；按 Windows 大小写不敏感语义验证路径；schema 遇到不支持关键字 fail closed；历史 Review/baseline 只读；五项 P1 同批关闭。

**Ask First:** 需要修改目标目录外产品代码、ADR/standard、Bootstrap gateway，或新增第三方依赖时停止。

**Never:** 不削弱 predicate、不删除 forbidden path、不把 `slice-ready` 降为 `plan-ready`、不忽略 schema 关键字、不扩大 backend/release 权限。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Behavior |
|---|---|---|
| Schema invalid | contract 缺 `plan_id` | 非零退出并返回 schema rule |
| Path escape | typed path 为 `../../outside` | containment rule 拒绝 |
| Glob overlap | allow `docs/**`，forbid `docs/standards/**` | overlap rule 拒绝 |
| Authority drift | authority 文档 hash 不匹配 | authority hash rule 拒绝 |
| S0 proof | 执行 S0 GREEN/exit | 有对应 `slice-ready` 命令；产物缺失时 fail closed |

</frozen-after-approval>

## Code Map

目标根：`execution-plans/2026-07-15-repository-maintenance-tdd-adapter/`

- `implementation-contract.v1.json`、`schemas/command-registry.v1.json` -- authority hash 与 S0 proof 合同。
- `schemas/implementation-contract.v1.schema.json` -- contract 结构权威。
- `tools/rmap_checks.py` -- schema、hash、path、glob 规则。
- `tools/validate_all.py` -- composite 与 S0 slice proof 入口。
- `fixtures/fixture-cases.v1.json`、`tools/tests/test_plan_validator.py` -- 五项反例与回归测试。

## Tasks & Acceptance

**Execution:**
- [x] `execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/tests/test_plan_validator.py` 与 `fixtures/fixture-cases.v1.json` -- 先加入五项失败测试并保存 RED。
- [x] 同目录 `tools/rmap_checks.py` 与 `schemas/implementation-contract.v1.schema.json` -- 实施严格 schema、authority hash、typed path containment、glob containment。
- [x] 同目录 `schemas/command-registry.v1.json`、`tools/validate_all.py`、`implementation-contract.v1.json` -- 建立 RMAP-S0 `slice-ready` proof，不降低 predicate。
- [x] 同目录 `02`、`03`、`04`、`05`、`06`、`96` 文档 -- 同步控制语义、诊断与修复证据。
- [x] `logs/vdd-plan-repair/**`、`logs/vdd-plan-validation/**` -- 保存 baseline、RED、修复后证据。

**Acceptance Criteria:**
- Given 五个 P1 最小反例，when 运行 targeted fixtures/tests，then 每项只产生声明的稳定 rule ID。
- Given 修复后的完整目录，when 运行全部 validator tests 与 `validate_all.py --predicate plan-ready`，then 零退出、envelope 为 `pass`、candidate/current/source hash 一致且只授权 `plan-ready`。
- Given baseline 后任一 authority/schema/validator/contract 漂移，when 复用旧证据，then freshness gate 拒绝。

## Spec Change Log

- 2026-07-16: 五个 confirmed P1 已完成修复并通过 fresh VDD plan-ready 验证；等待原 Bootstrap authority 做 blocker recheck。
- 2026-07-16: Bootstrap Round 2 确认原五项修复后又发现三个新 P1；当前保持 in-review/blocked，等待下一批 VDD repair 决策。
- 2026-07-16: 第二批三项 P1 已完成 VDD repair，22 tests 与 fresh plan-ready 通过；Bootstrap Round 3 又确认八项 P1。已达到三轮硬上限，workflow 进入 manual_pause，禁止自动 Round 4。
- 2026-07-16: 第三批八项 P1 已完成确定性 VDD repair；25 tests、三项定向反例、S3/S6/S7 fail-closed 与合成证据绑定均通过预期验证。状态仍为 blocked/manual_pause；未重写 Round 3 disposition，未授权 Round 4，也未声明语义闭环。

## Design Notes

本地 schema evaluator 仅支持当前声明的关键字并拒绝未知关键字，不引入依赖。glob 相交无法证明安全时拒绝。S0 使用专用 slice-proof 命令检查实际产物和索引链接，不以 plan consistency 冒充 slice completion。

## Verification

**Commands:**
- `py -3 execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/tests/test_plan_validator.py -v`
- `py -3 execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validate_all.py --fixture <p1-fixture>` -- 预期唯一 rule、非零退出。
- `py -3 execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validate_all.py --predicate plan-ready --output <fresh-evidence>` -- 预期 `pass`。

最新确定性证据：`logs/vdd-plan-validation/repository-maintenance-tdd-adapter/20260716-p1-r3-repair-final/plan-ready.json`；repair closure：`logs/vdd-plan-repair/repository-maintenance-tdd-adapter/20260716-p1-r3-repair-closure/closure-manifest.json`。该证据只证明当前计划候选的 VDD 控制链与合成绑定路径，不替代 Round 3 Bootstrap authority，也不解除 `manual_pause`。
