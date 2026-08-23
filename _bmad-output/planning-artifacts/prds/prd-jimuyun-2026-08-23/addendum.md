# Phase B/C PRD Addendum

## 来源与权威

- 上游需求输入：`execution-plans/2026-08-22-phase-b-c-identity-isolation-workspace-recovery-requirements.md`。
- 本 PRD 不取代 Accepted ADR、适用 `AGENTS.md` 或当前兼容性；冲突顺序为 Accepted ADR、applicable AGENTS、当前 runtime/source compatibility、architecture docs、standards、README。
- 任何改变现有 Accepted ADR 的选择必须先通过 ADR 更新或新增 ADR，而不能由 PRD 文案覆盖。

## 技术决策留给 Architecture

以下方向是约束或候选，不是本 PRD 对实现的指定：OIDC provider 和 session 模型；Windows 本地账户、restricted token、Job Object、NTFS ACL 的具体组合；Runner 身份粒度；storage API、manifest 编码和打包格式；SQLite schema 与 migration；staging 的原子发布机制；lease/fencing 的当前 seed；snapshot 加密与 key reference；恢复的详细状态机；用户级空间上限的具体数值与物理回收调度。

快照产品语义已经固定：每个项目默认不自动创建 Snapshot 或自动 Restore；用户/受保护 admin 入口显式触发；每次创建为不可变新版本。项目删除是软删除，逻辑配额释放与实际磁盘回收分离。Admin 可维护扩展名黑名单，策略版本绑定到新 Snapshot，历史 Snapshot 不回写。

## 已有基线，不重复建设

Phase A/B 已有 host admin token 与 hashed account token、账户启停/轮换、主要资源的账户 scope、审计、SQLite 与本地磁盘权威存储、受控 Workspace/Runner、hosted route recovery、LLM/Codex 入口和 evidence/readback。后续实现应补强而不是并行重建账户系统、Runner 或恢复系统。

## 外部模式的采纳边界

可借鉴 Rakazo 的 API/Worker 分离、durable job/event、runtime/sandbox provider 和 portable checkpoint；借鉴 OpenHands/E2B 的 Agent Runtime 与持久 Workspace 分离、低权限执行和恢复边界；借鉴 Dify 的 SaaS 账户归属、凭据和审计。它们都不是运行时依赖或规范权威。

不纳入：Agent server、多 server session、模型供应商治理、fleet、warm pool、网络策略、对象存储、Daytona 集成、App Server、任务/Taskmaster 工作流。任何不能映射到 PIWR-001 至 PIWR-040 的新增能力是范围扩展。

## 架构输入清单

Architecture 至少读取根/`PhaseA.Platform` AGENTS、Phase architecture index、ADR index、Phase service standard、`docs/workflows/phase-b-account-isolation.md`、roadmap/hardening、Phase C hardening/gov docs，以及 auth/account/workspace/runner/route recovery/LLM 相关 Accepted ADR。

## 可并行工作护栏

G0 合同合并后，Identity/API、Workspace Recovery、Runner Isolation 可分别推进。共享 schema、fixture、migration 编号和 endpoint composition 必须串行整合；不允许多个分支同时重排 `Program.cs`。工具链控制面计划与本产品运行时需求可并行，不能被吸收到本 PRD。
