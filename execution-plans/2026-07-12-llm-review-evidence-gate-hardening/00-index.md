# LLM 审查事实门禁与降噪实施计划索引

状态：Plan-ready；Phase R0 Bootstrap Review 可以在 handoff 前只读运行，R1–R6 仍等待两个上游重构目录的完成/handoff evidence。通过只表示计划可实施，不表示正式 gateway 或产品代码完成。
语言：中文
研究依据：[`_bmad-output/planning-artifacts/research/technical-everything-claude-code-review-anti-hallucination-research-2026-07-12.md`](../../_bmad-output/planning-artifacts/research/technical-everything-claude-code-review-anti-hallucination-research-2026-07-12.md)

## 目标

为代码、文档和执行计划审查建立一套仓库自有、升级安全、机器可验证的事实门禁，同时覆盖：

- 平台长期开发使用的 Codex；
- 前台用户创建项目、游戏及后续工作流触发的 Codex；
- BMAD/GDS reviewer 产生的候选 finding；
- 后台 Blind Hunter、Edge Case Hunter、Acceptance Auditor 三层 review route；
- profile-bound 角色 rubric、误报抑制、受审内容不可信边界与确定性 preflight；
- 批量修复、默认两轮/硬上限三轮的完整语义 Review 止损；
- reviewer 前 authority freeze、跨 run lineage、单一语义 authority、计划绑定检查、高成本确认与 process lease；
- 本仓 `scripts/sc/**` 审查与恢复链路。

所有 P0、P1、P2 finding 都必须具有三联证明：精确证据与行号、具体失败场景、现有防护为何未阻止。缺少任一项时删除；只有仍能证明较低等级具体失败时才允许降级。零 finding 是合法结果。

## 权威边界

- 本目录是实施意图权威，不直接修改 `.agents/skills/bmad-*` 或 `.agents/skills/gds-*` 安装内容。
- 实施后的长期规则归属 `docs/standards/llm-review-findings.md`，本目录不能成为永久运行时标准。
- `_bmad/custom/*.toml` 只做升级安全的薄适配；机器事实门禁由仓库自有 review gateway 执行。
- reviewer 只能产生 candidate；未经 gateway 接受的 finding 不得展示、写入任务、触发修复或阻断完成。
- `AGENTS.md` 与 `README.md` 按 [05 的分阶段同步合同](05-bmad-gds-and-codex-integration.md#6-agents-与-readme-同步时机) 更新；不得提前声明能力，也不得把已 operational 的路由拖到 R6 才记录。
- 涉及 Phase 共享 LLM/Codex 入口、认证、账户隔离或运行态路径时，必须遵守 `AGENTS.md` 的 Protected Phase Paths 审批要求。

## 与现有两个重构目录的关系

- [`2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening`](../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/00-index.md) 和 [`2026-07-11-phase-frontend-boundary-hardening-execution-plan`](../2026-07-11-phase-frontend-boundary-hardening-execution-plan/00-index.md) 仅作为文档结构参考和后续集成依赖。
- 本目录不复制它们的 GDD-to-module、React `/ui-v2`、Permit、mutation、数据迁移或 Phase 路由业务要求。
- 在上述进行中重构完成前，本计划只允许实施不触碰其文件和共享 Phase 入口的 Phase R0 Bootstrap Review；其余运行时接入必须等待两个上游计划完成并取得明确 handoff evidence。
- Bootstrap Review 是本目录拥有的只读 CLI 与显式授权编排合同：CLI 生成 reviewer prompt/template、消费隔离 reviewer/verifier 输出并写独立 evidence；profile 按计划 authority、实施闭合、Skill/路由、聚焦变更选择不同 reasoning/depth，但全部要求完整 artifact/context、禁止 sampling。CLI 不得自动调用 reviewer、修改目标目录、接入 `scripts/sc`、写 repair guide 或冒充 BH-HANDOFF/production gateway。
- 7 月 7 日既有历史 review run、prompt、输出和 ledger 保持不变；用户可从新的显式 review ID 开始，对 7-07/7-11 运行 supplemental Bootstrap Review。R3 仍只接管 handoff 后的新正式 review route。

## 分册顺序

1. [范围、权威与非目标](01-scope-authority-and-non-goals.md)
2. [Finding 合同与严重等级](02-finding-contract-and-severity.md)
3. [代码、文档与计划审查适配](03-code-document-and-plan-adapters.md)
4. [Gateway、去重、核验与记忆](04-gateway-dedup-verification-and-memory.md)
5. [BMAD/GDS 与两类 Codex 集成](05-bmad-gds-and-codex-integration.md)
6. [测试、观测与渐进启用](06-testing-observability-and-rollout.md)
7. [实施阶段](07-implementation-phases.md)
8. [风险、DoD 与术语](08-risks-dod-and-glossary.md)
9. [Bootstrap Review 手工操作指南](09-bootstrap-review-operator-guide.md)
10. [Whole-directory review 标准](96-global-review-and-validation.md)
11. [计划新增要求台账](97-plan-added-requirements-ledger.md)
12. [来源到拆分审计](98-source-to-split-audit.md)
13. [来源覆盖图](99-source-coverage.md)

机器合同：

- [review-finding.v1.schema.json](schemas/review-finding.v1.schema.json)
- [review-rejection.v1.schema.json](schemas/review-rejection.v1.schema.json)
- [review-result.v1.schema.json](schemas/review-result.v1.schema.json)
- [review-validation-fixtures.v1.json](schemas/review-validation-fixtures.v1.json)
- [bootstrap-reviewer-output.v1.schema.json](schemas/bootstrap-reviewer-output.v1.schema.json)
- [bootstrap-preflight-result.v1.schema.json](schemas/bootstrap-preflight-result.v1.schema.json)
- [bootstrap-verifier-output.v1.schema.json](schemas/bootstrap-verifier-output.v1.schema.json)
- [bootstrap-review-gate-result.v1.schema.json](schemas/bootstrap-review-gate-result.v1.schema.json)
- [bootstrap-review-launch-authorization.v1.schema.json](schemas/bootstrap-review-launch-authorization.v1.schema.json)
- [bootstrap-process-leases.v1.schema.json](schemas/bootstrap-process-leases.v1.schema.json)
- [review-profiles.v1.json](bootstrap/review-profiles.v1.json)

计划验证入口：

```powershell
py -3 execution-plans/2026-07-12-llm-review-evidence-gate-hardening/tools/validate_whole_directory.py
```

## 全局实施顺序

`R0A 计划基线` → `R0B Bootstrap Review 工具` → `R0C 用户手工审查 7-07/7-11` → `R0D 上游 handoff` → `R1 标准和机器合同` → `R2 平台开发审查网关` → `R3 BMAD/GDS 薄适配` → `R4 前台触发 Codex 接入` → `R5 shadow 评估` → `R6 强制门禁与文档同步`。

任何阶段不得以 reviewer 的自然语言总结代替 schema、测试和 evidence sidecar。
