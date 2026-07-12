---
title: 'Phase Boundary Handoff Bootstrap Closure'
type: 'chore'
created: '2026-07-11'
status: 'done'
review_loop_iteration: 0
baseline_commit: '80a863628c6224d80a53a0d7f4bfc07fc061a2fa'
context:
  - 'C:/jimuyun/AGENTS.md'
  - 'C:/jimuyun/execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/00-index.md'
  - 'C:/jimuyun/execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 下游计划虽然已严格等待上游完成，但 BH-HANDOFF 仍存在 validator 自我授权、lock/signer 自举死锁、不可变 manifest 与可变状态冲突，并要求上游未承诺的 OpenAPI、surface、schema 和 migration 产物。

**Approach:** 将 BH-HANDOFF 改为使用预先冻结的 bootstrap contract/verifier、append-only manifest state registry 和下游只读 derived snapshot；只消费上游已承诺产物，不放宽上游 Phase 6 退出标准，并补齐 supersession、go/no-go、owner 和机械验收契约。

## Boundaries & Constraints

**Always:** 计划保持 `paused`；`2026-07-07` 上游目录与当前 Phase 源码不修改；上游 route/status/readback/diagnostic/UI/GDD 仍是唯一业务权威；handoff 缺少任一必需字段、信任根或唯一 active state 均 fail closed。

**Ask First:** 改变上游退出标准、修改 protected Phase paths、启动任何下游实施任务、选择实际 HSM/KMS/远程签名产品。

**Never:** 让 handoff task 修改自己的 validator/rules/plan；要求已完成的上游补做下游技术投影；用普通 `logs/` latest 文件充当唯一 active authority；在 Hosted containment 失败后继续进入 Pilot。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 上游完整闭环 | 零未解决 P0/P1/P2，已承诺 artifact 完整 | 根据 source map 生成 signed handoff 和 downstream-derived snapshots | 任一缺失则拒绝签名 |
| 上游未产出 OpenAPI/surface/schema registry | 只有冻结代码、fixture 和 exit evidence | 在下游 handoff adapter 中生成只读 observed snapshot | 不得重开上游业务实施 |
| handoff 被 supersede | 存在在途 task/Permit/lease/workspace | 进入 abandon 或 restart/revalidate，不允许直接换绑 | 屏蔽 apply/finalize 并保留 evidence |
| Hosted containment 不通过 | BH-SF1 负向测试失败 | 计划 blocked/correct-course | 不签 BH-SF1 success exit |

</frozen-after-approval>

## Code Map

- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md` -- 恢复基线、精确 Gate 和待决策事项。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/01-authority-threat-model-and-gates.md` -- bootstrap contract、manifest/state/source map、lock 和 supersession。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/08-implementation-phases.md` -- 严格阶段与 containment go/no-go。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/96-global-review-and-split-validation.md` -- 机械 validator 和 mutation suite。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/97-post-split-requirements-ledger.md` -- 新 finding/PBR 闭环与 supersession 字段。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/99-source-coverage.md` -- 逐项 owner/phase coverage。

## Tasks & Acceptance

**Execution:**
- [x] 顶层、01 -- 消除 stale Git Head、聚合 Gate、signer/lock/validator 自举循环和上游退出冲突。
- [x] 01、06 -- 增加 versioned BootstrapHandoffContract、Manifest/StateEvent/ActiveRegistry、source map 和 downstream-derived snapshot 边界。
- [x] 01、08 -- 定义 supersession 在途产物处置和 BH-SF1 go/no-go。
- [x] 96、97、99 -- 新增本轮 PBR、mutation rules、机器可判定 supersession 和 source coverage。
- [x] 全计划 -- 验证 UTF-8、链接、PBR/finding/phase 完整性与无上游文件修改。

**Acceptance Criteria:**
- Given 上游 Phase 6 完成，when BH-HANDOFF 运行，then 只消费上游已承诺 artifact，缺失的技术投影由下游只读 adapter 生成。
- Given handoff task 尝试修改 validator/rules/plan，when protected bootstrap verifier 验证，then BH-HANDOFF 失败。
- Given 存在多个 active manifest、stale epoch 或未解决 P0/P1/P2，when 签名或启动下游 task，then fail closed。
- Given Hosted containment 负向测试失败，when BH-SF1 评估退出，then 计划进入 blocked/correct-course 而不是 BH-SF2。

## Spec Change Log

## Verification

**Commands:**
- 目标计划 UTF-8/link/PBR/finding/phase/bootstrap validator -- passed: 15 个计划文档、84 条 PBR、87 个 finding、15 个阶段，0 errors。
- `git status --short` scope inspection -- passed for this change: 本轮仅修改下游计划与本规格；当前上游目录和 Phase 源码仍有用户既有 dirty changes，本轮未触碰或回退。

## Suggested Review Order

**首门与信任自举**

- 先确认上游业务权威与下游只读投影边界。
  [`execution-plan.md:24`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md#L24)

- 检查 verifier、lock、schema、signer 在 handoff task 前冻结。
  [`01-authority-threat-model-and-gates.md:73`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/01-authority-threat-model-and-gates.md#L73)

- 确认 handoff 只运行仓库外保护 verifier。
  [`96-global-review-and-split-validation.md:7`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/96-global-review-and-split-validation.md#L7)

**来源映射与状态权威**

- 逐字段区分上游产物和下游技术快照。
  [`01-authority-threat-model-and-gates.md:123`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/01-authority-threat-model-and-gates.md#L123)

- 以 immutable manifest、event chain 和 CAS registry 防止双 active。
  [`01-authority-threat-model-and-gates.md:146`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/01-authority-threat-model-and-gates.md#L146)

- 确认 supersession 禁止在途任务直接换绑。
  [`01-authority-threat-model-and-gates.md:156`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/01-authority-threat-model-and-gates.md#L156)

**下游实施与阶段停损**

- React client 消费 derived API snapshot，不要求上游补 OpenAPI。
  [`05-react-ui-v2-migration.md:126`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/05-react-ui-v2-migration.md#L126)

- 严格阶段矩阵仍保证唯一活动阶段。
  [`08-implementation-phases.md:22`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/08-implementation-phases.md#L22)

- Platform 或 Hosted containment 失败均必须 blocked/correct-course。
  [`08-implementation-phases.md:103`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/08-implementation-phases.md#L103)

**要求与机械覆盖**

- 第七轮 15 条问题已形成 PBR-070～084。
  [`97-post-split-requirements-ledger.md:88`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/97-post-split-requirements-ledger.md#L88)

- supersession 由状态 registry 机器判定，不再依赖散文。
  [`97-post-split-requirements-ledger.md:104`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/97-post-split-requirements-ledger.md#L104)

- 最后核对 84 条 PBR 的唯一 owner/phase coverage。
  [`99-source-coverage.md:47`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/99-source-coverage.md#L47)
