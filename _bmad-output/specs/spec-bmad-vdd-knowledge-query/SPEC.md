---
id: SPEC-bmad-vdd-knowledge-query
package_schema: canonical-spec-package.v1
companions:
  - path: _bmad-output/planning-artifacts/prds/prd-bmad-vdd-knowledge-query-2026-10-22/addendum.md
    role: adopted_companion
  - path: _bmad-output/specs/spec-bmad-vdd-knowledge-query/behavior-contracts.md
    role: normative_companion
  - path: _bmad-output/specs/spec-bmad-vdd-knowledge-query/failure-modes.md
    role: normative_companion
  - path: _bmad-output/specs/spec-bmad-vdd-knowledge-query/acceptance.md
    role: normative_companion
  - path: _bmad-output/specs/spec-bmad-vdd-knowledge-query/scope-and-decisions.md
    role: normative_companion
  - path: logs/bmad-wrappers/architecture-zero-match-2026-10-22/native/logs/bmad-wrappers/architecture-knowledge-query-2026-10-22/native/_bmad-output/architecture/ARCHITECTURE-SPINE.md
    role: adopted_companion
sources:
  - path: _bmad-output/planning-artifacts/prds/prd-bmad-vdd-knowledge-query-2026-10-22/prd.md
    role: provenance
  - path: _bmad-output/planning-artifacts/prds/prd-bmad-vdd-knowledge-query-2026-10-22/sources/bmad-vdd-knowledge-query-requirements.md
    role: provenance
---

> 本 SPEC 与 companions 中的文件共同构成完整行为合同。sources 仅用于溯源；下游不得靠重新读取 provenance 才发现必须承担的要求。附录中的 PRD 执行记录只说明当时状态，不授予新阶段权限。

# BMAD 与 VDD 知识查询

## Why

仓库维护者在增量规划中需要先了解已有能力、约束与真实实现，避免重复建设、遗漏消费者和沿用历史计划。本增量复用 Locator 定位，再读取有效来源与当前源码；查询辅助判断，不成为事实、实施完成或 Acceptance 权威。

## Capabilities

- **CAP-1**
  - **intent:** 维护者能检查有界查询配置的有效值和来源。
  - **success:** FR-01/AC-01 的覆盖语义、诊断和单次触发要求满足，个人或模型输入不能扩大范围。
- **CAP-2**
  - **intent:** BMAD 能以真实受限身份复用 Locator。
  - **success:** FR-02/AC-02/AC-13 的身份、四维隔离与发布绑定保持；正常查询不隐式发布。
- **CAP-3**
  - **intent:** PRD 默认在形成仓库事实判断前查询并读取来源。
  - **success:** FR-03/AC-03 的来源读取实际影响复用/新增边界，纯编辑复用有理由。
- **CAP-4**
  - **intent:** Architecture 决定前核对来源，SPEC 承接并按需补查。
  - **success:** FR-04/AC-04/AC-05 的冲突、规范/provenance 分工、typed 包与 selection 规则保持。
- **CAP-5**
  - **intent:** VDD 规划前利用查询线索核查当前源码、调用方与测试。
  - **success:** FR-05/AC-06/AC-07 中索引未覆盖的既有行为仍被发现并作为回归，直接核查不伪装成 Locator 结果。
- **CAP-6**
  - **intent:** 维护者能追溯采纳结论所读来源的真实身份。
  - **success:** FR-06/AC-03/AC-08 区分快照、main、分支及未提交字节；不伪造发布身份或新增全仓冻结。
- **CAP-7**
  - **intent:** 消费者能区分正常结果、可用性降级、不可信失败和取消。
  - **success:** FR-07/AC-07至AC-10 的语义按 failure-modes.md 执行，退出码 0 的 blocked 不被当成功或缺失。
- **CAP-8**
  - **intent:** 默认查询与既有治理分别启用。
  - **success:** FR-08/AC-06/AC-11 保持 development/auto 治理关闭，on 模式 required gate 仍阻断。
- **CAP-9**
  - **intent:** 恢复与来源变化时只补充必要且有界的上下文。
  - **success:** FR-09/AC-09/AC-12 允许有效复用、只更新相关结论；不自动重建、无限重试或启动其他流程。
- **CAP-10**
  - **intent:** 维护者能获得真实消费与既有交接兼容的交付证明。
  - **success:** FR-10/AC-14 的实际 BMAD/VDD 样例与 Windows 证据成立；配置文字、静态文件和 Linux 结果不能替代它们。

## Constraints

- 所有 FR 的完整义务在 behavior-contracts.md；失败优先级在 failure-modes.md；AC-01至AC-14 在 acceptance.md，均为必读规范内容。
- 原生 BMAD 6.12.4 保持原样，新增定制外置；SPEC/Architecture 继续由 jimuyun 外壳承接，不恢复退役路径。
- 查询不借用其他消费者身份，不手改生成投影、不绕过发布/新鲜度校验；正式 owner、typed 角色、selection、来源 hash 和 Acceptance 权威保持。
- 明确的可用性问题可以转为有记录的当前源码核查；非法、损坏、越界、策略拒绝或未识别 blocked 必须 fail-closed。
- 不改变现有治理优先级和 development/auto 默认关闭；查询不创建冻结、额外授权、attestation 或 review lineage。
- 稳定已验证工具链主持本需求；未来候选查询/VDD 仅在隔离样例验证，不中途替换主持工具链或改冻结输入。
- 每阶段须独立 A/B 审核和工作会话共同认可才推进；本次架构及 SPEC refresh 待阶段 3 外部 A/B 复核，不授予 VDD、实施、验收或并行工作权限。

## Non-goals

- Package B 全面迁移、重做既有阶段、TC-D2/D4/D5/D6、S1/S2 游戏业务和沙箱重构。
- 新知识平台、通用 RAG/向量库、全仓索引重构、Codex 内核/app-server/SDK、Phase/Hosted 功能变更。
- 自动发布、自动 Bootstrap/总入口/内部 reviewer 平台/切片并行调度、历史证据改写或查询结果提升为完成权威。
- scope-and-decisions.md 中列出的其余明确排除项同样有效。

## Success signal

维护者运行真实 BMAD 和 VDD 样例时，配置解析、默认触发、真实查询/诊断、来源读取和下游采纳形成可核查链条；全部 14 项 AC 得到对应行为证据，既有交接无已知实质回归，正式 Acceptance 按现有 owner 完成。本文只规定未来行为，不声称样例、Windows 验证或功能验收已执行。

## Assumptions

- A1：沿用获批 PRD 的单维护者内部能力表达，不虚构 UI、市场指标或延迟目标。
- A2：预算采用经原生架构审查的保守工程起点，已由 SPEC owner 固化在 behavior-contracts.md；不是性能 SLA，后续调整须经 owner refresh。

## Open Questions

- Q1：维护者在任何 S2 执行前确认具体排期；技术非依赖不代表并行许可，不阻塞本需求规划。
- Q2–Q3 已形成设计：必读 adopted architecture 固定身份/策略、外置接入、接口表示与记录；预算由 behavior-contracts.md 规范固定。
- Q4：相关实施前由 ADR owner 记录适用范围增量，Windows 行为须取得真实平台证据；初次发布仍需维护者在合入后显式授权。见 scope-and-decisions.md。
