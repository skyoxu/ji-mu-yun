---
title: 'Phase Boundary Sequential Upstream Handoff Closure'
type: 'chore'
created: '2026-07-11'
status: 'done'
review_loop_iteration: 0
baseline_commit: '9c8ac4bdf79431d5735ab1d0552357dd6f248ed6'
context:
  - 'C:/jimuyun/AGENTS.md'
  - 'C:/jimuyun/execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/00-index.md'
  - 'C:/jimuyun/execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前边界强化计划仍允许与正在执行的 GDD-to-module 重构并行，并在上游 Phase 6 前接入 Hosted route、React、Gate、DB 和架构规则，可能抢占上游业务 route/status/readback/diagnostic/UI/GDD 权威及正在修改的文件。

**Approach:** 将上游完整交付改成不可绕过的第一 Gate；只有上游 Phase 0～6、全局复审、closure ledger、durable standards 和最终 commit 形成不可变 handoff manifest 后，本计划才允许创建实现任务。下游只消费上游 machine contracts，并继续实施 Permit、containment、Mutation、React 技术迁移和平台内部治理。

## Boundaries & Constraints

**Always:** 保持计划 `paused`；不修改上游目录、上游实现代码或 live 数据；所有下游 phase 和 PBR 显式依赖 handoff manifest；React surface、Work Policy action、route evidence、metadata schema 和 standards section 必须引用上游最终 owner/Hash。

**Ask First:** 修改 protected Phase paths、改变上游业务 contract、接受上游未关闭 deferral、选择远程 Authority/HSM 或启动任何下游实现任务。

**Never:** 并行实施；在上游 Phase 6/global review 前启用 Change Origin Gate、legacy freeze、Hosted pilot 或 React pilot；复制 status/action/route/readback/diagnostic/UI schema；把上游 compatibility shim 当普通 residual 删除。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 上游仍在执行 | 缺最终 commit、Phase 6 exit 或 closure evidence | 本计划所有实现 phase 保持 blocked | fail closed，只有只读规划可继续 |
| 上游完成 | handoff manifest 的 commit、fixture、schema、standards 和 evidence Hash 全部验证 | 仅允许创建 BH-SF0A 任务，更晚阶段仍等待直接前序退出 | 任一 Hash/deferral 不匹配则拒绝 |
| 下游需要业务 surface | React/Work Policy/Evidence 任务请求 route/status/surface | 读取 handoff projection，不创建第二套业务合同 | 未映射 ID 阻断任务 |

</frozen-after-approval>

## Code Map

- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md` -- 顶层顺序、恢复状态和 handoff Gate。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/01-authority-threat-model-and-gates.md` -- authority 与启动条件。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/04-mutation-lease-journal-and-acceptance.md` -- Work Policy 对上游 action fixture 的消费。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/05-react-ui-v2-migration.md` -- React 只迁移上游 surface projection。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/08-implementation-phases.md` -- downstream-only 阶段顺序。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/96-global-review-and-split-validation.md` 到 `99-source-coverage.md` -- 跨计划 overlap 和 PBR 覆盖门禁。

## Tasks & Acceptance

**Execution:**
- [x] 顶层、01、08 -- 增加 BH-HANDOFF，删除全部并行/U0/U1/U6 前置实施路径并更名下游阶段。
- [x] 04～07 -- 将 action、surface、diagnostic/evidence、metadata schema 和 standards 绑定上游 handoff，不重复定义业务权威。
- [x] 02～07 -- 修复 host observation、Platform worktree、Permit/lease、manifest、key history、DR、encryption、migration 和 architecture ratchet 残余。
- [x] 96～99 -- 增加 fifth/sixth-review PBR、handoff/overlap validator 和逐项 source coverage。
- [x] 全计划 -- 运行 UTF-8、链接、recovery、phase/PBR/finding、禁止并行和上游 authority overlap 检查。

**Acceptance Criteria:**
- Given 上游未形成完整 handoff，when 任一下游实现任务尝试 active，then Gate 必须拒绝。
- Given 上游 handoff 有效，when React、Work Policy、Evidence 或 DB 任务规划，then 所有业务 ID、schema 和 standards owner 均解析到 handoff Hash，不产生第二权威。
- Given 当前 dirty worktree，when scope check，then 不修改上游目录、Phase 源码、runtime 或 live 数据。

## Spec Change Log

- 2026-07-11: 将计划收紧为严格 downstream-only，以 BH-HANDOFF 作为唯一首门，完成上游权威投影、strict predecessor graph、handoff-only task allowlist、UpstreamCompletionSnapshot、epoch/deferral 失效、standards delta chain 和 internal Acceptance non-leakage 闭环。保留了 Permit/containment/Mutation/React 技术迁移/平台治理的原始下游目标，避免了与 `2026-07-07` 上游业务 route/status/readback/diagnostic/UI/GDD/schema 工作重复。

## Verification

**Commands:**
- 目标级 UTF-8/link/recovery/PBR/handoff validator -- passed: 15 个计划文档、69 条 PBR、72 个 finding 覆盖、15 个严格串行阶段，0 errors。
- `git status --short` scope inspection -- passed for this change: 仅本计划与本规格为本轮产物；上游目录、Phase 源码/测试已有其他 dirty changes，本轮未修改或回退。

## Suggested Review Order

**串行权威与首门**

- 先确认上游业务权威与下游治理边界。
  [`execution-plan.md:24`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md#L24)

- 核对 BH-HANDOFF 是唯一不可绕过的首门。
  [`01-authority-threat-model-and-gates.md:68`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/01-authority-threat-model-and-gates.md#L68)

- 检查 handoff-only task 的机械写路径白名单。
  [`01-authority-threat-model-and-gates.md:110`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/01-authority-threat-model-and-gates.md#L110)

- 确认双采集 UpstreamCompletionSnapshot 关闭竞态窗口。
  [`01-authority-threat-model-and-gates.md:112`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/01-authority-threat-model-and-gates.md#L112)

**阶段与业务契约隔离**

- 按直接前序矩阵确认任何时刻只有一个活动阶段。
  [`08-implementation-phases.md:20`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/08-implementation-phases.md#L20)

- 核对 Pilot 只导入上游 action/route/acceptance ID。
  [`08-implementation-phases.md:175`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/08-implementation-phases.md#L175)

- 确认内部 Acceptance 事务状态不泄漏为业务词汇。
  [`04-mutation-lease-journal-and-acceptance.md:72`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/04-mutation-lease-journal-and-acceptance.md#L72)

**机械验收与覆盖**

- 检查 validator 同时阻断重复权威、越级和越界路径。
  [`96-global-review-and-split-validation.md:7`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/96-global-review-and-split-validation.md#L7)

- 追溯第六轮问题的 PBR 闭环条目。
  [`97-post-split-requirements-ledger.md:76`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/97-post-split-requirements-ledger.md#L76)

- 最后确认 69 条 PBR 均有唯一 owner/phase 覆盖。
  [`99-source-coverage.md:47`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/99-source-coverage.md#L47)
