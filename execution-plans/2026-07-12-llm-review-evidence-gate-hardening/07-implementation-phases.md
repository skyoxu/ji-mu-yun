# 实施阶段

## Phase R0：上游等待与计划基线

Owner：平台架构/工作流维护者。

操作步骤：

1. 完成本目录 Whole-directory review；
2. 冻结 schema v1 和 RFG requirement ledger；
3. 记录两个上游重构目录的完成/handoff evidence；
4. 未取得 handoff 前，只允许修改本目录和独立验证 fixture。

退出标准：96 review PASS、97 无缺 owner/acceptance、98/99 覆盖完整、validator 通过。此退出不表示运行时代码完成。

## Phase R1：长期标准与机器合同

Owner：review contract maintainer。

操作步骤：

1. 新增 `docs/standards/llm-review-findings.md` 并更新 standards index；
2. 同步 `docs/PROJECT_DOCUMENTATION_INDEX.md`、相关 architecture index，并在 README 只增加标准导航和未启用状态；
3. 将本目录 schema 迁入长期 schema owner；
4. 实现 deterministic finding validator 与 fixture tests；
5. 建立 evidence fingerprint 和 disposition sidecar 版本策略；
6. 如形成不可逆跨切面决策，新增 ADR 并更新 Phase ADR index。

退出标准：所有 fixture 通过；P0–P2 三联证明机器强制；零 finding 和 incomplete 明确区分。

## Phase R2：平台开发审查网关

Owner：`scripts/sc` review pipeline owner。

操作步骤：

1. 先写 failing tests；
2. 在不改变 `summary.json` 的前提下新增 candidate/gate/disposition sidecars；
3. 接入 dedup、verifier 和 bounded lifecycle；
4. 更新 recovery/readback 文档；
5. 在 gateway operational 的同一变更更新 AGENTS 平台开发 review 路由；
6. 运行 task-scoped review pipeline 回归。

退出标准：不合格 finding 无法进入 repair guide；重复/驳回 finding 不重现；旧 sidecar consumer 兼容。

## Phase R3：BMAD/GDS 薄适配与仓库 wrapper

Owner：agent workflow maintainer。

操作步骤：

1. 创建四个 `_bmad/custom/*.toml` team overrides；
2. 为 Blind Hunter、Edge Case Hunter、Acceptance Auditor 创建三个 candidate adapter；
3. 创建仓库自有 review wrapper，禁止 stock reviewer 直接决定 blocker；
4. 从 7 月 7 日旧 route handoff evidence 生成显式 route-version 切换，不重写历史结果；
5. 在新 route operational 的同一变更更新 AGENTS 三层 candidate 路由和 active routeVersion；
6. 增加 resolver、provenance、dedup 与升级回归测试；
7. 不修改 installer-managed skill files。

退出标准：重装/升级模拟后 override 仍生效；三个 reviewer 输出只能作为 candidate；旧 route 历史不变；新 route finding 保留 `sourceReviewers[]`。

## Phase R4：前台触发 Codex 接入

Owner：Phase route execution owner；Protected Phase Paths 修改前须用户批准。

操作步骤：

1. 基于上游完成后的真实代码重新定位调用点；
2. 先补 account/project/workspace isolation tests；
3. 扩展共享入口而非创建本地 subprocess/provider 分叉；
4. 注入 route recovery authority、current blocker 和 browser-safe projection；
5. 增加 route-specific smoke 与 evidence；
6. 在用户可见行为/API 改变的同一变更更新 README 与 Phase public behavior docs。

退出标准：跨账户隔离、授权/未授权、route recovery、shared-entrypoint regression 和 smoke 全部通过。

## Phase R5：Shadow 与校准

Owner：review quality owner。

操作步骤：运行固定样本/两周 shadow；标注人工 verdict；分析 precision、recall、重复误报和成本；调整 adapter/false-positive list，不降低三联证明。

退出标准：阈值由 ADR 或标准变更明确；没有高 refuted blocker rate 或 seeded-defect recall 回退。

## Phase R6：强制门禁与文档同步

Owner：release owner。

操作步骤：按 adapter 从 advisory 切到 blocking；同步最终 rollout/迁移状态；清理已失效的 planned 标记；执行升级回滚演练。

退出标准：所有入口不可绕过 gateway；文档与真实状态一致；rollback 不恢复强制 finding 数量。
