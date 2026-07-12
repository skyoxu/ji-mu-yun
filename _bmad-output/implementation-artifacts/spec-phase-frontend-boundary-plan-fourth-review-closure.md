---
title: 'Phase Frontend Boundary Plan Fourth Review Closure'
type: 'chore'
created: '2026-07-11'
status: 'done'
review_loop_iteration: 1
baseline_commit: '9c8ac4bdf79431d5735ab1d0552357dd6f248ed6'
context:
  - 'C:/jimuyun/AGENTS.md'
  - 'C:/jimuyun/execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Phase 前台边界执行计划第四轮审查仍存在 5 个 P0、13 个 P1 和 4 个 P2，涉及签名自证、测试证据伪造、Acceptance 执行隔离、Windows 实际文件语义、恢复状态、React 安全、在线迁移、架构门禁和容量安全，当前不能直接进入代码实施。

**Approach:** 在不修改 Phase 源码、运行时、live DB/workspace 或上游 GDD-to-module 业务权威的前提下，将全部 finding 写入各自 owner book，并同步顶层恢复索引、阶段、风险、DoD、PBR ledger、split validation 和 source coverage；最终通过机械检查和对抗复审确认无漏项或矛盾。

## Boundaries & Constraints

**Always:** 中文文档以 UTF-8 处理；保持计划 `paused`；每项新增合同必须有 owner、阶段、验收和 ledger ID；所有安全边界默认 fail closed；保留用户现有代码改动。

**Ask First:** 修改 protected Phase 源码、运行时配置、认证实现、live metadata/workspace，或改变上游 route/status/readback/UI 业务合同。

**Never:** 将 Codex 自检当作授权；信任 worker 自报或测试报告 Hash；让 Codex/Phase Web/CI 取得签名私钥；用文本 diff 替代 Windows 实际 Workspace Manifest；宣称已获得尚未存在的 task/owner/approver 授权。

</frozen-after-approval>

## Code Map

- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md` -- 恢复状态、Gate 和全局完成条件。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/01-authority-threat-model-and-gates.md` 到 `09-risks-dod-and-glossary.md` -- owner contracts、阶段和 DoD。
- `../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/96-global-review-and-split-validation.md` 到 `99-source-coverage.md` -- validator、PBR ledger 和覆盖证明。

## Tasks & Acceptance

**Execution:**
- [x] `02`、`03`、`04` -- 关闭 signer/test/manifest/Acceptance/IPC/state/side-effect/capacity finding。
- [x] `05`、`06`、`07` -- 关闭 React/session/supply-chain/trial、architecture/DB migration、evidence/SLO/performance finding。
- [x] `top-level`、`01`、`08`、`09`、`96` 到 `99` -- 同步威胁、阶段、DoD、validator 和 PBR 覆盖。
- [x] 全计划 -- 运行 UTF-8、链接、恢复字段、唯一 ID、required marker 和交叉一致性检查。
- [x] 全计划 -- 完成 Blind Hunter 和 Edge Case Hunter 双层对抗复审，关闭 signer/runner trust、manifest、状态机、phase/ledger/coverage 回归。

**Acceptance Criteria:**
- Given 第四轮 22 条 finding，when 检查 owner books、phase、DoD 和 PBR ledger，then 每条均有唯一可追踪合同与机械验收意图。
- Given 当前 dirty worktree，when 比对 scope，then 除本计划目录、顶层索引和本规格外不产生新修改。
- Given 计划仍缺实际 SF0-A task/owner/approver，when 修订完成，then状态保持 `paused` 且不声称代码 implementation-ready。

## Spec Change Log

- 2026-07-11：双层复审发现 launcher/signer 密钥权属冲突、CI 无法重建 Windows 宿主语义、Permit/Mutation 状态漂移、Change Origin Gate 可规避、实施阶段和 PBR 无法机械覆盖。修订为远程 Attestation Authority、SourceChangeManifest/HostEffectiveManifest 双 manifest、完整最终/回滚状态、全 Phase 变更来源闸门、SF4 和显式 finding-to-PBR/phase/source coverage。

## Verification

**Commands:**
- `py -3 scripts/python/validate_recovery_docs.py --dir execution-plans` -- expected: recovery metadata valid。
- 本轮内联 UTF-8/link/marker/ledger validator -- expected: missing、duplicate、broken link 和 finding coverage 均为零。

**Result:** target recovery errors=0，15 个计划 Markdown UTF-8/link 通过，39 个 PBR 唯一且具有 owner/phase，22 个第四轮 finding 全部显式覆盖，99 source coverage 包含全部 PBR。仓库全目录 recovery validator 仍会因既有上游 `2026-07-07...md` 缺恢复字段而提前失败，本轮未越界修改该上游入口。

## Suggested Review Order

**全局顺序与启动边界**

- 先确认安全基础、SF4 和业务试点的依赖顺序。
  [`execution-plan.md:57`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md#L57)

- 核对 SF0-A 到 SF4 的实际交付与退出门槛。
  [`08-implementation-phases.md:3`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/08-implementation-phases.md#L3)

**签名、证据与实际文件语义**

- 远程 Authority 消除 launcher、Phase 主机和 Codex 自签名。
  [`02-permit-trust-and-attestation.md:23`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/02-permit-trust-and-attestation.md#L23)

- 双 manifest 分离 CI 可重算源内容与 Windows 宿主有效语义。
  [`02-permit-trust-and-attestation.md:65`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/02-permit-trust-and-attestation.md#L65)

- Runner 无私钥，Authority 只为受保护 supervisor 观测签发证明。
  [`02-permit-trust-and-attestation.md:113`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/02-permit-trust-and-attestation.md#L113)

**执行隔离与恢复**

- 所有 Phase 变更必须进入 Change Origin Gate。
  [`03-profiles-preflight-and-containment.md:23`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/03-profiles-preflight-and-containment.md#L23)

- Acceptance 只运行精确候选 manifest，不使用其他 focused workspace。
  [`03-profiles-preflight-and-containment.md:126`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/03-profiles-preflight-and-containment.md#L126)

- 完整状态机覆盖 finalized、中断回滚、回滚失败与人工恢复。
  [`04-mutation-lease-journal-and-acceptance.md:39`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/04-mutation-lease-journal-and-acceptance.md#L39)

**React、数据与维护性**

- 浏览器最低安全头和同源策略成为确定合同。
  [`05-react-ui-v2-migration.md:84`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/05-react-ui-v2-migration.md#L84)

- 试运行使用不可豁免的样本、性能与安全回退门槛。
  [`05-react-ui-v2-migration.md:154`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/05-react-ui-v2-migration.md#L154)

- 架构检查区分可机械规则与必须留证的语义复审。
  [`06-platform-architecture-data-and-version.md:31`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/06-platform-architecture-data-and-version.md#L31)

- 迁移用 fencing、writer drain、全量对账和每状态恢复闭环。
  [`06-platform-architecture-data-and-version.md:101`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/06-platform-architecture-data-and-version.md#L101)

**可追踪闭环**

- 39 个 PBR 明确 owner、phase、finding 和验收家族。
  [`97-post-split-requirements-ledger.md:10`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/97-post-split-requirements-ledger.md#L10)

- 22 个第四轮 finding 均有显式 PBR 关闭关系。
  [`97-post-split-requirements-ledger.md:54`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/97-post-split-requirements-ledger.md#L54)

- Source coverage 逐个枚举 PBR，不再只靠宽泛主题声明。
  [`99-source-coverage.md:46`](../../execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan/99-source-coverage.md#L46)
