---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - .agents/skills/vdd-execution-plan/SKILL.md
  - .agents/skills/vdd-execution-plan/references/strict-vdd-standard.md
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'Mature GitHub VDD, specification-driven, contract-driven, and verification-first agent skills'
research_goals: 'Identify high-quality, maintained, license-compatible guidance and executable patterns that can strengthen the repository vdd-execution-plan skill without importing unverifiable claims or cargo-cult templates.'
user_name: 'Administrator'
date: '2026-07-13'
web_research_enabled: true
source_verification: true
---

# Research Report: GitHub VDD Agent Skills

## Executive Summary

No single inspected GitHub Skill or agent framework provides a complete strict VDD system. The strongest result is a composite architecture: local BMad supplies the intent kernel, stable capability/architecture identities, vertical story decomposition, and spec-repair loop; Superpowers and Hermes supply observed RED, root-cause debugging, and fresh verification discipline; Spec Kit and OpenSpec supply artifact dependencies, deltas, and cross-artifact analysis; OpenClaw supplies proposal/hash/stale/quarantine/rollback governance; Everything Claude Code supplies behavioral Skill compliance scenarios; the local Bootstrap review supplies evidence-gated multi-reviewer and independent-verifier authority.

The local `vdd-execution-plan` already contains a strong VDD control chain, composite-validator requirement, negative/mutation fixtures, structured failure routing, evidence lineage, and authority-level separation. Its remaining high-value gaps are protocol and self-verification gaps: exact result-envelope semantics, spec delta/drift, repair baseline/apply, requirement-quality checks, optional BMad artifact adapters, and a deterministic Skill compliance fixture surface. The recommended implementation adds these without introducing a remote service, external framework dependency, or a misleading universal business validator.

**Authoritative recommendation:** keep verification in the control position; treat BMad and other planning states as candidate states; authorize transitions only through current hash-bound executable evidence; allow zero review findings; route failures to the earliest invalid layer; and distinguish deterministic fixture evidence from genuine fresh-context Agent compliance evidence.

## Table of Contents

1. Technical Research Scope Confirmation
2. Technology Stack Analysis
3. Integration Patterns Analysis
4. Architectural Patterns and Design
5. Local BMad Method and Skill Research
6. Implementation Approaches and Technology Adoption
7. Final Synthesis and Candidate Assessment
8. Source Verification and Research Limitations

## Research Overview

This research evaluated current public GitHub repositories and the locally installed BMad 6.10.0 Skill set against a strict VDD rubric: executable contracts, validator control, negative and mutation coverage, traceability, drift detection, diagnosis/repair/re-entry, independent verification, portability, and license clarity. Source claims were checked against fixed repository commits and concrete files rather than repository descriptions or star counts.

The full analysis below separates direct VDD mechanisms from adjacent specification-driven, TDD, Skill-governance, and review-gateway patterns. It also records rejected ideas, including fixed finding quotas, optional tests in strict lanes, non-blocking verification used as authority, universal coverage thresholds, and agent self-certification of readiness.

**Date:** 2026-07-13
**Author:** Administrator
**Research Type:** technical

---

## Technical Research Scope Confirmation

**Research Topic:** Mature GitHub VDD, specification-driven, contract-driven, and verification-first agent skills.

**Research Goals:** Identify reusable, evidence-backed mechanisms for improving the local `vdd-execution-plan` skill, including executable contracts, validator control, negative and mutation fixtures, behavior slicing, diagnosis/repair/re-entry, context closure, independent verification, and anti-self-certification controls.

**Research Methodology:**

- Search current public GitHub repositories and code.
- Prefer maintained repositories with inspectable skills, workflows, validators, tests, and licenses.
- Cross-check critical claims against repository files rather than repository descriptions alone.
- Separate direct VDD skills from adjacent specification-driven or verification-first patterns.
- Record rejected candidates and avoid copying license-incompatible or unverifiable content.

**Scope Confirmed:** 2026-07-13

---

<!-- Content will be appended sequentially through research workflow steps -->

## 技术栈分析

### 表达语言与工件格式

成熟方案并未依赖某一种编程语言，而是形成了“人可审阅规范 + 机器可执行验证”的双层栈：Markdown 承载意图、需求、场景和实施切片；YAML/JSON 承载稳定标识、依赖图、诊断信封、测试场景与运行结果；Python/TypeScript/Shell 承载确定性验证器。对本地 `vdd-execution-plan`，最稳妥的技术选择仍是 Markdown + JSON/YAML + Python，而不是引入新的远程平台依赖。

- GitHub Spec Kit 用 Constitution、Feature Spec、Plan、Tasks 和跨工件 Analyze 建立规范层次；用户故事被要求可独立开发、测试、部署和演示，计划在进入设计前后都要检查 Constitution。[spec-template](https://github.com/github/spec-kit/blob/1be42992e64b08ff0dce3d7a914eaabf04284ffb/templates/spec-template.md) [plan-template](https://github.com/github/spec-kit/blob/1be42992e64b08ff0dce3d7a914eaabf04284ffb/templates/plan-template.md) [analyze](https://github.com/github/spec-kit/blob/1be42992e64b08ff0dce3d7a914eaabf04284ffb/templates/commands/analyze.md)
- OpenSpec 用可配置 schema 声明 `proposal -> specs -> design -> tasks` 的依赖图，并用 ADDED/MODIFIED/REMOVED/RENAMED delta 维护长期规范真相；CLI 提供结构化 JSON、诊断码和非零失败退出码。[schema](https://github.com/Fission-AI/OpenSpec/blob/0a99f410457271aa773d8b106f03f637f7c6b3c0/schemas/spec-driven/schema.yaml) [writing-specs](https://github.com/Fission-AI/OpenSpec/blob/0a99f410457271aa773d8b106f03f637f7c6b3c0/docs/writing-specs.md) [agent-contract](https://github.com/Fission-AI/OpenSpec/blob/0a99f410457271aa773d8b106f03f637f7c6b3c0/docs/agent-contract.md)

_适用结论：高置信度。VDD 目录应同时保留可读规范和机器工件，并为每个 Requirement、Scenario、Validator、Slice、Finding、Evidence 使用稳定 ID。_

### Agent Skill 与工作流框架

候选项目的直接 VDD 命名并不普遍，但相邻框架已经形成可迁移的验证优先机制：

- Superpowers 将开发纪律拆为独立 Skill：测试先行且必须观察到预期 RED、完成前必须重新运行完整证明命令、修复前必须复现并追到根因；其 Skill 编写方法还要求用无指导基线和压力场景对 Skill 本身做 RED-GREEN-REFACTOR。[TDD](https://github.com/obra/superpowers/blob/d884ae04edebef577e82ff7c4e143debd0bbec99/skills/test-driven-development/SKILL.md) [verification-before-completion](https://github.com/obra/superpowers/blob/d884ae04edebef577e82ff7c4e143debd0bbec99/skills/verification-before-completion/SKILL.md) [writing-skills](https://github.com/obra/superpowers/blob/d884ae04edebef577e82ff7c4e143debd0bbec99/skills/writing-skills/SKILL.md)
- Hermes Agent 的计划、TDD、系统化调试和 Skill authoring 延续了相同纪律，并额外强调 tight feedback loop、可检查的步骤完成标准、写入来源 provenance、Skill 安全扫描与 AST 审计。其 Skill 基础设施有大量自动化测试，但计划/TDD 文本本身仍主要依赖流程遵守，不等同于已证明的行为合规。[plan](https://github.com/NousResearch/hermes-agent/blob/f96b2e6ef75ba6ed678c99954bc8f3ee7f6a38ba/skills/software-development/plan/SKILL.md) [systematic-debugging](https://github.com/NousResearch/hermes-agent/blob/f96b2e6ef75ba6ed678c99954bc8f3ee7f6a38ba/skills/software-development/systematic-debugging/SKILL.md) [skill-authoring](https://github.com/NousResearch/hermes-agent/blob/f96b2e6ef75ba6ed678c99954bc8f3ee7f6a38ba/skills/software-development/hermes-agent-skill-authoring/SKILL.md)
- GitHub Awesome Copilot 提供结构化 specification/implementation-plan Skills，包含唯一标识符和声明重复检查，但主要是模板与文本规则，缺少对完整 VDD 时序的行为测试。[create-implementation-plan](https://github.com/github/awesome-copilot/blob/0aaced533251f5b86c69dfbc5e55db74c4b4d1af/skills/create-implementation-plan/SKILL.md)

_适用结论：Superpowers/Hermes 的验证与诊断纪律适合直接综合；Awesome Copilot 只适合借鉴稳定 ID 和结构检查，不应作为完整 VDD 依据。_

### Skill 治理、存储与漂移控制

OpenClaw 的 Skill Workshop 是本轮最成熟的 Skill 生命周期参考。它不允许生成内容直接覆盖生效 Skill，而是先生成 pending proposal；apply 是唯一生效写入点；更新提案绑定目标哈希，目标变化会转为 stale；apply 前重跑扫描器；写入前保存 rollback；reject/quarantine 不触碰生效 Skill；审批超时保持 pending，且禁止盲目循环重试。相关 service/workshop 测试覆盖 hash/stale、rollback、support-file tamper、路径穿越、symlink、secret、prompt injection 和 quarantine 等负例。[Skill Workshop](https://github.com/openclaw/openclaw/blob/b0ebb81e89f5217397d409c996e2bbf914623a94/docs/tools/skill-workshop.md) [proposal scan](https://github.com/openclaw/openclaw/blob/b0ebb81e89f5217397d409c996e2bbf914623a94/src/skills/workshop/proposal-scan.ts) [service tests](https://github.com/openclaw/openclaw/blob/b0ebb81e89f5217397d409c996e2bbf914623a94/src/skills/workshop/service.test.ts)

对本地 VDD Skill，不需要复制 OpenClaw 平台，但应迁移其语义：修复既有目录前记录输入快照/哈希；验证器与规范变化使旧证据失效；修复必须产生新 run lineage；完成结论必须指向当前内容哈希和新鲜运行；高风险权威切换需要独立批准或明确外部 gate。

_适用结论：高置信度。采用生命周期和证据失效规则，不引入 OpenClaw 专用服务。_

### Skill 行为测试与反例平台

Everything Claude Code 的 `skill-comply` 是本轮最直接的“Skill 是否真的被遵守”验证工具参考。它从 Skill 提取 3-7 个可观察步骤，为同一任务生成 supportive、neutral、competing 三档提示，捕获工具调用轨迹，用模型分类语义、再用确定性逻辑检查 before/after 时序。仓库提供 compliant/noncompliant traces、TDD spec fixture，以及 parser/grader/runner 测试；这比仅验证 YAML frontmatter 更接近 VDD 对 Skill 自身的要求。[skill-comply](https://github.com/affaan-m/everything-claude-code/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/skills/skill-comply/SKILL.md) [scenario generator](https://github.com/affaan-m/everything-claude-code/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/skills/skill-comply/prompts/scenario_generator.md) [TDD compliance fixture](https://github.com/affaan-m/everything-claude-code/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/skills/skill-comply/fixtures/tdd_spec.yaml) [grader tests](https://github.com/affaan-m/everything-claude-code/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/skills/skill-comply/tests/test_grader.py)

同仓库的 `spec-miner` 还提供稳定 `id`、`enforced`、`test`、`Last verified(commit)`、`deferred` 和 `uncertainty` 元数据，可增强 brownfield 计划的来源覆盖和漂移检测；`tdd-workflow` 的 RED/GREEN evidence report 则可借鉴为证据索引。[spec-miner](https://github.com/affaan-m/everything-claude-code/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/agents/spec-miner.md) [tdd-workflow](https://github.com/affaan-m/everything-claude-code/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/skills/tdd-workflow/SKILL.md)

_适用结论：高置信度。应为 `vdd-execution-plan` 增加无指导基线、支持/中性/竞争三档场景、合规时序断言和至少一个已知不合规轨迹；模型判定只能补充语义分类，最终门禁仍由确定性检查负责。_

### 工具链与验证器架构

综合候选方案后，推荐的本地工具链是：

1. `SKILL.md` 只保留触发条件、主流程、硬门禁和 reference 路由。
2. `references/strict-vdd-standard.md` 保存完整工件契约、状态机、诊断和修复规则。
3. Python validator 负责目录结构、稳定 ID、引用闭包、依赖图、命令存在性、fixture 绑定、证据新鲜度和退出码。
4. 负例/变异 fixture 证明每条关键 validator rule 能按预期失败，禁止只证明 happy path。
5. Skill 行为微测证明 Agent 在 neutral/competing prompt 下仍遵守 `意图 -> 契约 -> 验证器 -> 切片 -> 实现 -> 诊断/修复` 的控制顺序。
6. composite validator 输出机器 JSON 和简洁人类摘要；任何必需验证器未运行、无新鲜证据或证据绑定旧哈希，都必须失败关闭。

### 平台与分发

这些候选项目均以 GitHub 仓库、普通文本 Skill 和本地 CLI/测试作为主要分发面，许可证核验结果为：Spec Kit、OpenSpec、Superpowers、Awesome Copilot、Hermes Agent、OpenClaw、Everything Claude Code、Claude Code Spec Workflow 均有根目录 MIT License；CheckMate 为 Apache-2.0；`informalsystems/vdd` 当前克隆未发现根许可证，因此只能学习概念，不复制文本。固定 commit 链接用于保证本报告可复核，后续采用时仍需重新检查上游变化。

### 技术采用趋势与质量判断

可观察到的演进方向是：

- 从提示词模板转向工件依赖图和结构化 CLI 契约。
- 从“写完即生效”转向 proposal/review/apply、哈希绑定和 rollback。
- 从 frontmatter/schema 校验转向反例、时序、行为合规和多次独立运行。
- 从“测试通过”转向“测试曾以预期原因 RED、修复后 GREEN、完成声明有新鲜证据”。
- 从一次性规范转向 delta、stable id、last-verified commit/hash 和 drift invalidation。

不应直接移植的内容：Spec Kit 将测试任务设为可选；OpenSpec 的 verify 默认不阻断 archive；Everything Claude Code 的固定 80% 覆盖率不适合所有项目；Hermes 计划模板要求在计划中放完整代码，容易造成计划与实现双重真相；Awesome Copilot 的“零歧义”和固定行号属于过强承诺。严格 VDD Skill 应吸收其机制，但使用仓库自己的风险、ADR、验证器和外部授权边界决定门禁。

**研究覆盖：** 规范驱动框架、Agent Skill 框架、Skill 生命周期治理、Skill 行为合规、确定性验证器、负例与证据存储均已覆盖。

**置信度：** 对上述源码行为为高置信度；对 star、社区采用率和跨模型实际合规率仅作背景参考，不作为质量证明。后续步骤需要把这些机制转成 `vdd-execution-plan` 的明确差距清单、修订项与本地可执行自测。

## 集成模式分析

### 工件 API 与控制协议

本地 `vdd-execution-plan` 不需要接入远程 REST/GraphQL 服务。它真正需要的是稳定的“工件 API”：每个 Markdown、schema、fixture、validator、ledger 和 evidence 文件都应通过稳定 ID、owner、hash、dependency 和 status 字段互操作。OpenSpec 的 schema artifact dependency graph、JSON diagnostic envelope 和退出码契约证明，这类协议可以在纯文件/CLI 环境内实现。[schema](https://github.com/Fission-AI/OpenSpec/blob/0a99f410457271aa773d8b106f03f637f7c6b3c0/schemas/spec-driven/schema.yaml) [agent-contract](https://github.com/Fission-AI/OpenSpec/blob/0a99f410457271aa773d8b106f03f637f7c6b3c0/docs/agent-contract.md)

建议把本地组合验证器输出固定为版本化信封：

```json
{
  "schema_version": "vdd.validation-result.v1",
  "run_id": "...",
  "candidate_hash": "sha256:...",
  "source_hash": "sha256:...",
  "validator_version": "...",
  "predicate": "plan_ready",
  "status": "pass|fail|blocked|incomplete",
  "authorizes": ["..."],
  "does_not_authorize": ["..."],
  "checks": [
    {"rule_id": "VDD-...", "status": "pass|fail|skip", "evidence": ["..."]}
  ],
  "diagnostics": [
    {"severity": "error", "code": "...", "target": "...", "fix": "..."}
  ]
}
```

退出码与机器状态必须双重约束：验证失败返回非零；若某个仓库约定 `blocked` 可返回零，则所有消费者必须解析 `status`，并由测试证明不会把进程成功误判为授权成功。

### 通信协议与权威传递

推荐采用 stdin/file-first、stdout JSON、stderr 人类诊断的本地协议，避免把长规范或提示通过命令行参数传递。工件之间不复制权威文本，而是传递：

- 稳定 ID 与相对路径；
- 内容哈希、schema/validator 版本；
- predecessor/supersedes 关系；
- 当前允许的状态转换；
- 精确的 rerun command 与 expected rule IDs。

权威传递顺序为：approved intent -> executable contract -> validator rule -> behavior slice -> implementation evidence -> phase/handoff authority。任何下游工件只能引用上游权威，不能自行重新定义阈值、枚举或完成条件。GitHub Spec Kit 的 Constitution Check 和跨 `spec/plan/tasks` 分析可作为前置一致性 gate；OpenSpec 的 proposal/spec/design/tasks 依赖图可作为工件就绪 gate。[Spec Kit analyze](https://github.com/github/spec-kit/blob/1be42992e64b08ff0dce3d7a914eaabf04284ffb/templates/commands/analyze.md) [OpenSpec workflows](https://github.com/Fission-AI/OpenSpec/blob/0a99f410457271aa773d8b106f03f637f7c6b3c0/docs/workflows.md)

### 数据格式与长期漂移控制

推荐格式分工：

- Markdown：意图、理由、非目标、切片说明和人工审阅入口；
- JSON/YAML：requirements、acceptance、state machine、failure family、validator rules 和 source coverage；
- JSONL：追加式 run events、diagnostics、finding closure 和 supersession lineage；
- hash manifest：绑定当前目录、关键来源、validator 和 fixture 内容；
- generated Markdown view：从机器 owner 生成，禁止成为第二权威。

规范变更应采用 delta 语义：ADDED、MODIFIED、REMOVED、RENAMED。MODIFIED 必须携带完整新契约及旧 ID；REMOVED 必须给出原因、迁移/影响和反例；archive/merge 后重新计算 source/candidate hash。Everything Claude Code `spec-miner` 的 stable `id`、`enforced`、`test`、`Last verified(commit)`、`deferred` 和 `uncertainty` 可补足 brownfield 来源追踪，但这些元数据仍需由本地 validator 校验，不能只依赖注释存在。[spec-miner](https://github.com/affaan-m/everything-claude-code/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/agents/spec-miner.md)

### 系统互操作与适配层

Skill 必须适配不同仓库，而不是强制所有仓库采用同一文件名。建议把互操作划分为三层：

1. **Canonical VDD roles**：intent、contract、validator、fixture、slice、diagnostic、ledger、coverage、evidence。
2. **Repository mapping**：把现有文件映射到 canonical roles；现有目录不机械重命名。
3. **Validator adapters**：由 `validate_all.py` 调用仓库原有 schema/test/link/smoke 工具，并统一转换为 VDD result envelope。

这样既保留 `execution-plans/YYYY-MM-DD-<slug>/` 的推荐结构，也允许 7-07、7-11、7-12 等已有方案继续使用自己的拆分，只要求 owner、引用和控制链闭合。适配器不能吞掉原验证器的失败；未知输出、缺失工具或不可解析结果必须 fail closed。

### Gateway 与独立验证模式

借鉴 API Gateway，而不是微服务本身：组合验证器是唯一计划级 gateway，负责聚合所有局部结果并决定 `plan_ready`；protected handoff/release verifier 是独立 gateway，拥有不同的规则版本、执行身份和授权域。本地 plan validator 永远不能自行提升到 protected production authority。

LLM reviewer 只通过 candidate channel 进入系统：reviewer -> candidate JSON -> deterministic gateway -> independent verifier（P0/P1）-> accepted finding。不得让 reviewer 文本直接修改 gate status。零 finding 是合法结果，finding 去重必须包含 evidence hash、failure tuple、family、route/version 和 authority revision。

### 事件驱动的失败、修复与重入

VDD 循环适合用追加式事件模型表达：

```text
candidate.snapshotted
  -> contract.validated
  -> validator.red_proven
  -> slice.authorized
  -> implementation.changed
  -> validation.passed | validation.failed
       -> diagnosis.recorded
       -> repair.proposed
       -> candidate.resnapshotted
       -> validation.rerun
```

每次目标 hash 变化必须产生新 run，旧 run 只可被 supersede，不能原地改写。失败事件携带 rule ID、requirement/acceptance ID、failure family、observed outcome、repair owner 和 rerun command。诊断应路由到最早无效层：意图、契约、validator/fixture、slice、实现或 evidence/re-entry，而不是机械地总回到第 3 步。

OpenClaw Skill Workshop 的 pending/apply/stale/quarantine/rollback 生命周期证明了“候选与生效状态分离”的价值。[Skill Workshop](https://github.com/openclaw/openclaw/blob/b0ebb81e89f5217397d409c996e2bbf914623a94/docs/tools/skill-workshop.md) 本地 Skill 应把同一思想用于 repair：先记录目录 manifest/hash 与 baseline failure，再修改；验证前目标变化则旧证据 stale；危险或不可判定状态保持 draft/quarantined，不得以部分成功覆盖旧权威。

### Skill 自身的验证接口

当前本地 Skill 已要求 mutation fixture，但还缺“Skill 是否改变 Agent 行为”的外部接口。建议新增 Skill compliance micro-suite：

- 从 `SKILL.md` 提取 5-7 个必须可观察的步骤；
- 为同一任务准备 supportive、neutral、competing 三档提示；
- 准备无 Skill/no-guidance control；
- 捕获读取、写入、验证命令和状态转换轨迹；
- 用语义分类识别工具调用意图，再用确定性 before/after 规则评分；
- 至少提供一条 compliant trace 和一条 noncompliant trace；
- 对关键纪律进行多次 fresh-context 运行，区分 pass@1 与稳定性 pass^k；
- 若某纪律在竞争提示下持续失效，优先加强确定性 hook/validator，而不是继续增加同义警告。

Everything Claude Code 的 `skill-comply` 已验证了三档场景、语义分类和确定性时序检查的组合方式；Superpowers 的 writing-skills 提供了无指导基线、压力测试和 RED-GREEN-REFACTOR 的 Skill 迭代原则。[skill-comply](https://github.com/affaan-m/everything-claude-code/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/skills/skill-comply/SKILL.md) [writing-skills](https://github.com/obra/superpowers/blob/d884ae04edebef577e82ff7c4e143debd0bbec99/skills/writing-skills/SKILL.md)

### 集成安全模式

- 把仓库文档、外部网页、计划内容和 reviewer 输出当作不可信数据，不允许其中的指令覆盖 Skill/AGENTS 规则。
- 对 repair 使用 proposal/baseline/apply 语义：先快照、再修复、后验证；protected path 仍需用户批准。
- validator、fixture 和证据必须绑定 hash；修改授权自己的 validator 需要独立 review 或重新建立基线。
- 禁止 literal secret、路径穿越、隐藏 executable、symlink escape 和把运行日志当作唯一源文件。
- 完成声明必须包含新鲜完整命令、退出码、机器 status、failed count 和证据路径。

### 端到端集成结论

推荐的 VDD 集成骨架为：

```text
Repository authority + current-state sources
  -> canonical role map + baseline/hash manifest
  -> intent/constitution/invariants
  -> spec delta + executable contracts
  -> validator rule registry + fixtures/mutations
  -> cross-artifact consistency gateway
  -> independently testable vertical slices
  -> implementation + append-only run events
  -> fresh composite validation result envelope
  -> diagnosis/repair/new candidate run
  -> independent protected verifier when required
```

**当前 Skill 的主要集成缺口：** 缺精确 result-envelope schema；缺显式 spec-delta/drift protocol；缺 repair baseline manifest/apply 语义；缺独立 requirement-quality checklist；缺可执行的 Skill compliance pressure suite。现有的 authority、composite validator、mutation、failure routing、lineage 和 authority-level 分离应保留并作为这些新增协议的基础。

**质量评估：** 对协议和工件映射为高置信度；是否需要在 Skill 内附带完整通用 validator 脚本仍需在架构步骤中权衡，因为仓库差异较大，过度通用化可能产生低价值的伪验证。

## 架构模式与设计

### 系统架构模式

推荐采用“薄编排层 + 规范内核 + 确定性评估面”的模块化单体 Skill，而不是复制 OpenClaw 的完整 Workshop 服务或 Everything Claude Code 的完整 harness：

```text
SKILL.md
  -> 选择 create/repair 模式、读取权威、执行 VDD 主链、完成门禁

references/strict-vdd-standard.md
  -> 完整规范内核：状态、工件、结果信封、delta、漂移、诊断、证据

references/skill-compliance-protocol.md
  -> Skill 自身的无指导/支持/中性/竞争场景与可观察时序

scripts/validate_skill_contract.py
  -> 验证 Skill 包结构、触发描述、reference 路由、必需规则和协议 fixture

scripts/tests/ + scripts/fixtures/
  -> compliant/noncompliant traces、result envelope 正反例、delta/drift 正反例

生成或修复的 execution-plan 目录/tools/validate_all.py
  -> 面向该计划和该仓库的真正组合验证器
```

关键边界：Skill 自带脚本只验证 Skill 自身契约和通用协议示例，不能声称验证任意执行计划的业务语义。计划级验证器必须在目标目录内按该仓库的 schemas、tests、standards 和 protected gates 构建。这避免“万能 validator”造成伪安全感。

这一结构符合本地 `skill-creator` 的 progressive disclosure 原则，也吸收 OpenClaw 将 active Skill 与 proposal/runtime 治理解耦的经验。[OpenClaw skill creator](https://github.com/openclaw/openclaw/blob/b0ebb81e89f5217397d409c996e2bbf914623a94/skills/skill-creator/SKILL.md) [Skill Workshop](https://github.com/openclaw/openclaw/blob/b0ebb81e89f5217397d409c996e2bbf914623a94/docs/tools/skill-workshop.md)

### 设计原则与最佳实践

1. **控制权优先于文档完整度**：只有 executable result 能授权状态变化；Markdown 解释但不替代 gate。
2. **单一权威、派生视图**：registry/schema 是机器 owner，Markdown matrix 从 owner 生成。
3. **失败关闭**：缺工具、不可解析输出、stale hash、未知状态和未授权 skip 均阻断。
4. **分层权威**：plan-ready、phase-authorized、implementation-accepted、protected-release 分开。
5. **最早无效层回退**：意图、契约、oracle、slice、实现和 evidence 分别修复。
6. **纵向 tracer slice**：每个切片交付一个可观察行为，并自带 test/evidence/rollback。
7. **新鲜证据**：完成声明前重新运行完整证明命令并读取退出码和机器 status。
8. **规范本身也 RED-GREEN-REFACTOR**：先证明反例能失败，再加强规则，再防止回归。
9. **指导形态匹配失败类型**：纪律绕过用 hard gate/反例；输出形态错误用正向模板；字段遗漏用 schema；条件行为用可观察 predicate。
10. **最小常驻上下文**：核心步骤放 `SKILL.md`，完整字段、schema、例子和评估协议放 references/scripts。

Superpowers 的 Skill 编写方法明确把 Skill 视为需要压力测试的流程代码；Hermes Skill authoring 强调每步完成标准、去除 no-op prose 和渐进披露。[writing-skills](https://github.com/obra/superpowers/blob/d884ae04edebef577e82ff7c4e143debd0bbec99/skills/writing-skills/SKILL.md) [Hermes skill authoring](https://github.com/NousResearch/hermes-agent/blob/f96b2e6ef75ba6ed678c99954bc8f3ee7f6a38ba/skills/software-development/hermes-agent-skill-authoring/SKILL.md)

### 可扩展性与性能模式

此 Skill 的扩展瓶颈是上下文和目录规模，而不是网络吞吐。采用以下策略：

- `SKILL.md` 保持流程骨架，避免复制 strict standard 的所有字段。
- repair 必须完整盘点目标目录，但按 canonical role 和引用图分批读取，不盲扫整个 `docs/`。
- 大目录先生成 inventory/manifest，再按 inbound/outbound authority links 扩展。
- 组合 validator 一次解析机器 owner，在内存中复用索引，避免每条规则重复扫文件。
- diagnostics 有稳定 rule ID 和上限；上限只影响展示，不允许隐藏 blocker 总数或未评估范围。
- source coverage、requirement ledger、acceptance map 使用哈希/ID join，而不是自然语言相似度作为唯一匹配。
- Skill pressure tests 使用小型可复现实例；昂贵的多模型 fresh-context 测试作为发布级评估，而不是每次编辑必跑。

Spec Kit 的 progressive artifact loading 与跨工件 semantic model、Everything Claude Code 的小型 compliance fixture 都证明这种分层方式可降低上下文成本。[Spec Kit analyze](https://github.com/github/spec-kit/blob/1be42992e64b08ff0dce3d7a914eaabf04284ffb/templates/commands/analyze.md) [skill-comply fixture](https://github.com/affaan-m/everything-claude-code/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/skills/skill-comply/fixtures/tdd_spec.yaml)

### 集成与通信模式

采用 ports-and-adapters 思路：

- **Input ports**：用户意图、明确目录、AGENTS/repo rules、standards/ADR、current-state/recovery sources。
- **Domain core**：strict VDD lifecycle、authority levels、result envelope、failure routing、delta/drift 和 evidence freshness。
- **Output ports**：execution-plan Markdown、schemas、fixtures、validators、ledgers、run evidence 和最终报告。
- **Adapters**：仓库现有 validator、test runner、schema checker、link checker、smoke、protected verifier。

所有 adapter 统一返回 versioned result envelope；不支持的 check 必须声明 `skip` 原因、授权来源和不影响证明，不能静默忽略。外部 protected verifier 保持独立，Skill 只记录调用契约和结果，不复制其实现或规则。

### 安全架构模式

信任边界分为四层：

1. **Governing authority**：系统/开发者规则、AGENTS、approved ADR/standard。
2. **Repository evidence**：源文件、测试、schema、current state；可信度取决于 hash 和 freshness。
3. **Untrusted candidates**：用户提供计划文本、外部网页、LLM reviewer 输出、旧 assistant summary。
4. **Authorizing verifier**：确定性本地 gate 或独立 protected verifier。

架构要求：

- untrusted candidate 不能直接改变 active status；
- repair 前记录 baseline manifest/hash，apply 后必须重新验证；
- 目标、support artifact 或 validator 变化使旧证据 stale；
- prompt injection、secret、path traversal、symlink escape 和 executable support file 纳入 Skill 自身反例；
- 修改授权自己的 validator 时，必须重新建立 RED fixture 和独立 review 边界；
- 历史 evidence append-only，quarantine/blocked/draft 是合法安全状态。

OpenClaw 的 hash-bound proposal、stale、quarantine、rollback 和 apply-time rescan 是这一架构的直接证据来源。[service tests](https://github.com/openclaw/openclaw/blob/b0ebb81e89f5217397d409c996e2bbf914623a94/src/skills/workshop/service.test.ts)

### 数据架构模式

推荐把机器 owner 分为五类：

| Owner | 主要数据 |
| --- | --- |
| authority manifest | source path/hash、owner、revision、current/future 边界 |
| requirement registry | stable ID、delta、phase、acceptance、consumer、status |
| validator registry | rule ID、version、fixture、severity、authorizes |
| run/evidence ledger | run ID、candidate hash、predecessor、result、supersession |
| diagnostic ledger | failure tuple、family、repair owner、rerun、closure evidence |

Markdown 97/98/99 文件可以继续作为人工导航，但必须能与这些机器 owners 精确对账。若已有仓库不采用集中 JSON registry，可由 adapter 从多个 schema 生成统一视图；生成过程本身必须可测试和可重放。

### 部署与运维架构

Skill 作为仓库内文本/脚本包部署，不增加 daemon、数据库或云服务：

- 通过 `quick_validate.py` 验证基础 Skill 结构；
- 通过新增自检脚本验证 reference/fixture/协议闭包；
- 通过单元 fixture 测试 result envelope、delta、drift、trace ordering；
- 更新后重新生成 `agents/openai.yaml`，确保 UI 元数据与触发描述一致；
- 可选的真实 Agent fresh-context 合规测试属于发布级证据，在当前禁止未授权 subagent 的约束下不自动运行；
- GitHub 上游只作为研究来源，Skill 运行不依赖网络，也不安装外部框架。

### 关键架构决策

- **采用**：新增一个专门的 Skill compliance reference 和一个确定性自检/fixture test surface。
- **采用**：把 result envelope、spec delta/drift、repair baseline manifest 和 requirement-quality checklist 纳入 strict standard。
- **保留**：现有 create/repair 两模式、canonical role map、failure routing、mutation、independent verifier 和 authority-level 区分。
- **不采用**：完整 OpenClaw Workshop 服务、外部数据库、通用远程 API、强制固定文件名迁移。
- **不采用**：声称能够验证所有目标目录业务语义的 Skill 内置万能 validator。
- **不采用**：固定覆盖率、固定 finding 数、仅模型评分、仅 schema/关键词检查。

**架构置信度：高。** 该设计把上游成熟机制转化为本地可维护的 Skill 结构，同时保留仓库特定验证器的权威位置。剩余风险在于自检脚本的范围控制：它必须验证通用协议和 Skill 行为约束，但不得越权宣称某个实际重构计划已经 VDD 合格。

### 本地 BMAD 方法论与 Skill 研究

本地安装的 BMad Method 版本为 `6.10.0`，其方法论主线为：分析 -> 规划 -> solutioning -> implementation；在实现阶段形成 create-story -> dev-story -> code-review 的循环。来源为 [`_bmad/bmm/module-help.csv`](../../../_bmad/bmm/module-help.csv) 和 [`_bmad/_config/manifest.yaml`](../../../_bmad/_config/manifest.yaml)。这套方法与严格 VDD 的关系不是“完全等价”，而是提供了非常合适的上游权威、行为切片和修复循环骨架。

#### BMad Spec：意图与规范内核

[`bmad-spec`](../../../.agents/skills/bmad-spec/SKILL.md) 把任何输入压缩成五字段 kernel：Why、Capabilities、Constraints、Non-goals、Success signal，并为 capability 分配稳定 `CAP-N`。`.memlog.md` 是追加式 canonical memory，`SPEC.md` 和 companions 从 memlog 派生；later entry supersedes earlier entry 而不删除历史。其 Spec Law 还要求 capability 同时有 intent/success、成功信号可测试/演示、非目标明确、load-bearing claim 必须保全。

可直接吸收：

- `01-intent-authority-and-non-goals.md` 应兼容 SPEC kernel，而不是重新发明另一套意图格式。
- 当目标已有 `SPEC.md + companions + .memlog.md`，VDD 计划应将其作为上游权威包，引用 stable `CAP-N`，不复制或重新编号。
- 追加式 memlog 是 intent/decision lineage 的优良来源，适合映射 predecessor/supersession。
- load-bearing preservation 两遍检查可补强 source-to-split audit。

必须补强：BMad Spec 的 coherence/preservation self-validation 主要是 LLM sweep，success 仍可能只是可测试 prose；VDD 必须把 `CAP-N -> REQ/AC -> validator rule -> fixture` 变成机器映射，并对 source/companion/memlog 绑定 hash。`SPEC.md` 的 `status: complete` 不能自动提升为 plan-ready。

#### Architecture Spine：不变量与机械/语义双门禁

[`bmad-architecture`](../../../.agents/skills/bmad-architecture/SKILL.md) 的 architecture spine 只固定会导致独立单元分歧的非显然 trade-off，并以稳定 `AD-n` 记录 `Binds/Prevents/Rule`。其 Reviewer Gate 先运行确定性 `lint_spine.py`，再运行 rubric/多 lens semantic review；linter 有实际 pytest 覆盖 placeholder、重复/非单调 AD ID、缺字段、未 pin 版本、fence 误报和 UTF-8 失败等正反例。[`reviewer-gate.md`](../../../.agents/skills/bmad-architecture/references/reviewer-gate.md) [`lint_spine.py`](../../../.agents/skills/bmad-architecture/scripts/lint_spine.py) [`test_lint_spine.py`](../../../.agents/skills/bmad-architecture/scripts/tests/test_lint_spine.py)

可直接吸收：

- VDD `02` 应把 architecture spine 的 `AD-n` 作为 inherited invariants，禁止计划本地弱化或重新定义。
- 采用“cheap deterministic pass first，semantic reviewers second”的两层验证架构。
- 每个 invariant 必须表达绑定对象、阻止的分歧和可执行规则，而不只是原则名称。

必须补强：`lint_spine.py` 明确始终返回 exit 0，结果通过 JSON `ok` 传递，但 Reviewer Gate 的消费主要是流程文字；严格 VDD 要求调用者解析测试和 result envelope，证明 `ok=false` 不会被当成通过。语义 reviewer 不能因 subagent 不可用而降级为同上下文自证。

#### Epics/Stories：行为切片与覆盖

[`bmad-create-epics-and-stories`](../../../.agents/skills/bmad-create-epics-and-stories/SKILL.md) 要求完整提取 FR/NFR/Architecture/UX-DR，建立 FR coverage map，以用户价值而不是技术层拆 epic，并要求 epic 独立、story 不依赖未来 story、Given/When/Then AC 可独立测试、每个 story 可由单个开发 Agent 完成。Implementation Readiness 再检查 FR coverage、UX/architecture 对齐、epic user value、story sizing 和 forward dependency。[`step-02-design-epics.md`](../../../.agents/skills/bmad-create-epics-and-stories/steps/step-02-design-epics.md) [`step-03-create-stories.md`](../../../.agents/skills/bmad-create-epics-and-stories/steps/step-03-create-stories.md) [`bmad-check-implementation-readiness`](../../../.agents/skills/bmad-check-implementation-readiness/SKILL.md)

可直接吸收：

- VDD behavior slices 应优先映射已批准 BMAD stories，并继承 FR/NFR/UX-DR/AD IDs。
- no-forward-dependency 和 independently completable 是切片 gate。
- context-size、风险边界和 file churn 可决定合并/拆分，而不是机械追求小故事。

需要协调的冲突：BMAD 反对“技术 epic”，但严格 VDD 要求不可逆决策、共享契约、validator baseline 和 diagnostic vocabulary 在 feature slices 前就位。解决方式不是把它们伪装成用户故事，而是把 VDD control-plane prerequisites 与 BMAD user-value epics 分层：控制基线是 phase gate，用户价值仍通过 vertical story 交付。

必须补强：BMAD coverage/readiness 多数是 Markdown 矩阵和 Agent 判断，缺少 machine owner、稳定 acceptance ID、negative fixture 和非零 gate。VDD composite validator 必须重新验证 coverage，而不能信任“全部 FR 已覆盖”的报告文字。

#### Create Story / Dev Story：上下文闭包与 RED-GREEN

[`bmad-create-story`](../../../.agents/skills/bmad-create-story/SKILL.md) 强调完整读取受影响文件、上一个 story、近期 git、architecture/testing/UX，并把这些压缩到 dedicated story file。随后 [`bmad-dev-story`](../../../.agents/skills/bmad-dev-story/SKILL.md) 记录 `baseline_commit`，按 task 执行 RED -> GREEN -> REFACTOR，只有测试和 AC 都满足才勾选 task，最后重跑 regression suite。

可直接吸收：

- 每个 VDD slice 应有 context manifest，至少列出 source requirement、inherited AD、affected current files、previous-slice evidence 和 test targets。
- 修复/实现前绑定 baseline commit/candidate hash。
- task 完成必须绑定实际存在且运行过的测试，不允许仅勾 checkbox。

必须修正：Create Story 的“flawless/everything needed”和 `ready-for-dev` 属于过度自证；Dev Story 对 unexpected status 会“continuing anyway”，与 fail-closed 冲突；测试命令、输出、candidate hash、validator version 和 diagnosis lineage 没有形成统一 evidence contract。严格 VDD 必须把这些状态转移交给 composite validator。

#### Dev Auto：最接近 VDD 的 BMAD 闭环

[`bmad-dev-auto`](../../../.agents/skills/bmad-dev-auto/SKILL.md) 是本地 BMAD 中与严格 VDD 最接近的实现：spec 有 `draft -> ready-for-dev -> in-progress -> in-review -> done|blocked` 状态；`<intent-contract>` 在实现阶段只读；实现前记录 `baseline_revision`；review 将问题分为 `intent_gap`、`bad_spec`、`patch`、`defer`、`reject`；`bad_spec` 会回退代码、修 spec、重新实现；repair loop 超过 5 次阻断；Spec Change Log 与 Review Triage Log 追加保存。[`step-04-review.md`](../../../.agents/skills/bmad-dev-auto/step-04-review.md) [`spec-template.md`](../../../.agents/skills/bmad-dev-auto/spec-template.md)

可直接吸收：

- intent 与 derived plan 分离，intent contract 不允许在实现过程中被便利性修改。
- finding 按根因层分类，`bad_spec` 回到规范，`patch` 留在实现，`intent_gap` 阻断并请求权威输入。
- repair non-convergence 有明确 stop-loss。
- Spec Change Log 的 KEEP instruction 可防止修复时丢失已正确行为。

必须补强：ready-for-development gate 是 self-review；implementation 未强制 TDD；review 使用的 Blind Hunter 依赖固定 finding quota；finalize 允许根据文字记录设置 `done`，但没有强制重新执行 spec 中全部 verification commands，也没有 hash-bound result envelope、mutation fixture 或 protected verifier。

#### Code Review 与本地 Bootstrap evidence gate

[`bmad-code-review`](../../../.agents/skills/bmad-code-review/SKILL.md) 提供 Blind Hunter、Edge Case Hunter、Acceptance Auditor 多 lens 评审，统一 triage 为 decision-needed/patch/defer/dismiss，且在定级前读取真实代码和 guards。Edge Case Hunter 允许合法空数组并采用机械路径枚举；这是可保留的 reviewer lens。[`bmad-review-edge-case-hunter`](../../../.agents/skills/bmad-review-edge-case-hunter/SKILL.md)

但 [`bmad-review-adversarial-general`](../../../.agents/skills/bmad-review-adversarial-general/SKILL.md) 强制至少十个问题并把零 finding 视为可疑，直接违反严格 VDD 的“零 candidate 合法、禁止 finding quota”。BMad Code Review 的 reviewer layer 失败后仍可继续、模糊 dedup 可能合并同一行上的不同 failure tuple、最终可在未重跑 acceptance/tests 时把 story 标记 done，也不能直接作为 VDD authority。

本仓库的 `C:/Users/Administrator/.codex/skills/run-phase-bootstrap-review/SKILL.md` 已经对这些缺口做了更严格的本地扩展：完整 context classes、hash-bound prepared scope、三 reviewer 隔离、零 candidate、deterministic gateway、P0/P1 independent verifier、route/profile/revision identity、stale run 重建、命令 exit 优先和 final result 不替代 protected handoff。现有 `vdd-execution-plan` 已吸收大部分规则，后续应继续把它视为 review adapter，而不是把普通 BMAD Code Review 当成授权器。

### BMAD 与严格 VDD 的合成结论

本地 BMAD 应成为 VDD Skill 的可选第一方互操作层，但不能成为硬依赖：

```text
BMad SPEC kernel / memlog / companions
  -> VDD intent authority + source preservation
BMad AD-n architecture spine
  -> VDD inherited executable invariants
BMad FR/NFR/UX-DR + stories
  -> VDD requirement registry + behavior slices
BMad baseline_commit / RED-GREEN / review loop
  -> VDD implementation and repair inputs
VDD schemas / fixtures / composite validator / evidence envelope
  -> authorize BMAD status transitions
Bootstrap evidence gate / protected verifier
  -> high-severity review and handoff authority
```

因此架构决策修订为：

- 新增 **BMAD artifact adapter guidance**，明确如何发现并继承 `SPEC.md`、companions、`.memlog.md`、`ARCHITECTURE-SPINE.md`、FR/NFR/UX-DR、epics/stories 和 baseline commit。
- 保留 canonical VDD roles，使没有 BMAD 的仓库仍可使用 Skill。
- 将 BMAD frontmatter/status/checklist 视为 candidate state；只有 VDD result envelope 能授权 `plan-ready` 或更高状态。
- 采用 Dev Auto 的根因分类和 bounded re-derivation loop，但以 executable diagnostics、hash lineage 和 fresh verification 替代自检文字。
- 采用 Architecture Spine 的 deterministic-first review pattern，同时修复 exit-code/status consumption contract。
- 禁止继承 BMAD adversarial general 的固定十 finding 规则；使用允许零 candidate 的证据门禁 reviewer。

**本地 BMAD 评价：方法论相关性高、工件互操作价值高、可执行验证成熟度不均衡。** Spec/Architecture/Dev Auto 的设计明显优于普通模板库；Architecture linter 有真实测试；但多数 readiness/story/review 状态仍依赖 Agent 自评。最佳组合不是用 VDD 取代 BMAD，而是让 VDD validator 成为 BMAD 状态机缺失的可执行控制层。

## 实施方式与技术采用

### 技术采用策略

采用渐进增强而不是整体替换：保留当前 `vdd-execution-plan` 已经正确的 create/repair、authority、composite validator、mutation、failure routing、lineage 和 authority-level 规则；先补规范协议，再补 Skill 自身的确定性评估面，最后才调整主流程。外部项目只提供模式证据，Skill 运行时不安装或调用 Spec Kit、OpenSpec、Hermes、OpenClaw、Everything Claude Code。

实施分为五个可独立验证的增量：

1. **Normative contract**：补充 validation result envelope、spec delta/drift、repair baseline/apply、requirement-quality checklist 和 BMAD adapter。
2. **RED fixtures**：先加入 pass/stale/implementation-first fixtures 与测试，证明缺失验证器时测试失败。
3. **GREEN validator**：实现无第三方依赖的 `validate_skill_contract.py`，只验证 Skill 包和通用协议。
4. **Skill integration**：更新 `SKILL.md` 的 repair/create/complete 流程和 reference 路由。
5. **Release verification**：官方 quick validation、自检、unit tests、mutation tests、UI metadata regeneration。

这种方式综合了 Superpowers 的 Skill RED-GREEN-REFACTOR、OpenClaw 的 proposal/stale/rollback 语义、Everything Claude Code 的 compliance fixture，以及 BMad Architecture 的 deterministic-first review。[Superpowers writing-skills](https://github.com/obra/superpowers/blob/d884ae04edebef577e82ff7c4e143debd0bbec99/skills/writing-skills/SKILL.md) [OpenClaw Skill Workshop](https://github.com/openclaw/openclaw/blob/b0ebb81e89f5217397d409c996e2bbf914623a94/docs/tools/skill-workshop.md) [ECC skill-comply](https://github.com/affaan-m/everything-claude-code/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/skills/skill-comply/SKILL.md)

### 开发工作流与工具

目标 Skill 包结构：

```text
vdd-execution-plan/
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── strict-vdd-standard.md
│   └── skill-compliance-protocol.md
└── scripts/
    ├── validate_skill_contract.py
    ├── skill-contract.json
    ├── fixtures/
    │   ├── compliance-scenarios.json
    │   ├── validation-result-pass.json
    │   ├── validation-result-stale.json
    │   ├── compliance-trace-pass.jsonl
    │   └── compliance-trace-implementation-first.jsonl
    └── tests/
        └── test_validate_skill_contract.py
```

`skill-contract.json` 是 Skill 自检的机器 owner，声明 required files/headings/reference links、result-envelope fields、allowed statuses、observable compliance steps 和 trace ordering。Python 验证器读取该 contract，不通过关键词数量推断质量。

计划使用以下本地工具：

- `C:/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py`
- `C:/Users/Administrator/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py`
- Python 标准库 `json`、`pathlib`、`hashlib`、`unittest`；不增加 pip 依赖。

### 测试与质量保证

RED-GREEN 实施顺序：

1. 写 `test_validate_skill_contract.py` 和 fixtures。
2. 在验证器不存在时运行测试，确认因缺少实现而 RED。
3. 实现最小 validator，使 clean contract/fixture GREEN。
4. 增加 mutation tests：删除 required file、required heading、reference link、result field、trace step 或交换 validator/implementation 顺序。
5. 验证每个 mutation 以预期稳定 rule ID 失败，避免 unrelated failure 造成假绿。
6. 运行完整自检和官方 quick validation。

本轮不运行未经用户授权的 subagent/fresh-context Agent eval。替代证据是 deterministic trace fixtures 和 mutation tests；真实 supportive/neutral/competing 多上下文运行保留为发布级可选步骤，并在 `skill-compliance-protocol.md` 中明确其证据等级。

### 部署与运维实践

Skill 为仓库内、离线可运行的普通文件包：

- 不新增 daemon、数据库、MCP、网络依赖或全局安装。
- `agents/openai.yaml` 由官方脚本生成，避免 UI 元数据漂移。
- 验证结果写 stdout JSON，失败返回非零；测试直接断言 exit code、status 和 rule IDs。
- fixtures 与 contract 随 Skill 版本控制；旧 evidence 绑定内容 hash，变更后必须重跑。
- Skill 自检不写 `logs/`，实际使用 Skill 创建的执行计划仍按仓库规则把运行 evidence 写入 `logs/`。

### 维护职责与所需能力

维护面分为三类：

- **Skill maintainer**：维护触发描述、核心流程、reference 路由和自检 contract。
- **Plan author**：根据目标仓库创建或修复 execution-plan 的机器工件与计划级 validator。
- **Independent authority**：当 protected handoff、P0/P1 review 或 release gate 要求时，由独立 verifier 决定更高权限状态。

一个角色可以在低风险本地场景中承担前两类职责，但不能让同一计划 validator 自行取代 protected authority。

### 成本与资源控制

- 默认验证全部离线执行，成本只包含本地 Python 运行。
- Skill 主体保持精简，详细协议按需加载，降低每次触发的上下文成本。
- deterministic checks 先于 LLM review，避免模型审阅机械问题。
- pressure fixtures 使用小型 trace；多模型、多次 fresh-context 只在重大 Skill 发布或行为回归时运行。
- 不复制上游框架代码和长模板，减少维护与许可证风险。

### 风险评估与缓解

| 风险 | 缓解 |
| --- | --- |
| 自检退化为关键词检查 | 使用结构化 contract、JSON fixture、trace ordering 和 mutation tests |
| 通用 validator 越权宣称业务合格 | 明确只验证 Skill 包；计划业务语义由目标目录 validator 负责 |
| BMAD status 被误当授权 | adapter 规定 BMAD 状态仅为 candidate state，必须经 VDD result envelope |
| Skill 体积继续膨胀 | 主流程留在 SKILL.md，字段和评估协议放 references/scripts |
| 测试只证明 happy path | 为 stale、missing field、wrong order、missing reference 提供独立反例 |
| 上游模式被 cargo-cult | 记录采用/拒绝理由，不复制固定覆盖率、finding quota 或非阻断 verify |
| 无真实 fresh-agent 证据 | 明确证据等级，不把 deterministic fixture 冒充跨模型行为证明 |

## 技术研究建议

### 实施路线图

1. 更新 strict VDD normative reference。
2. 新增 Skill compliance protocol。
3. 先落 tests/fixtures 并记录预期 RED。
4. 实现 validator 和 machine contract。
5. 更新 `SKILL.md` 与 BMAD adapter guidance。
6. 生成 UI metadata。
7. 运行 clean、negative、mutation、official validation。
8. 报告实际证据和未执行的 fresh-context 评估，不夸大完成等级。

### 技术栈建议

- Markdown：Skill 流程和规范。
- JSON/JSONL：machine contract、result envelope、fixture 和 trace。
- Python 3 标准库：validator 和 unittest。
- Git/hash：baseline、candidate、source 和 evidence freshness。

### Skill 开发要求

- `SKILL.md` 保持低上下文成本，并完整覆盖 create/repair 两触发类。
- reference 包含 exact protocol，不用模糊“彻底验证”措辞替代字段。
- scripts 输出稳定 machine status/rule IDs。
- 每个关键规则至少有一个独立负例。
- BMAD adapter 是可选互操作层，不能成为运行前提。
- protected review 使用现有 Bootstrap adapter，不重复实现。

### 成功指标

- 官方 `quick_validate.py` PASS。
- `validate_skill_contract.py` 对 clean Skill PASS 且退出 0。
- 全部 unit tests PASS。
- stale 与 implementation-first fixtures 被拒绝。
- 删除 required reference/heading/fixture/step 的 mutations 被预期 rule ID 捕获。
- `agents/openai.yaml` 与更新后的 Skill 一致。
- 无第三方依赖、无未授权 subagent、无外部运行时写入。
- 最终报告区分：结构自检通过、deterministic fixture 通过、真实 fresh-context eval 未运行。

## 最终综合与候选评估

### 加权评估维度

候选方案按以下维度综合判断，而不是按 star 数排序：维护活跃度、许可证清晰度、VDD 直接相关性、确定性 validator/tests、负例与 mutation、traceability/drift、repair/re-entry、独立权威边界、可移植性和上下文成本。

| 候选 | 最强能力 | 主要限制 | 综合适用度 |
| --- | --- | --- | ---: |
| OpenClaw | proposal/hash/stale/quarantine/rollback Skill 治理 | 完整平台过重，不应作为本地运行依赖 | 9.1/10 |
| Superpowers | observed RED、root-cause、fresh completion evidence、Skill 压力测试 | 缺完整规范目录与证据状态机 | 9.0/10 |
| 本地 BMad | intent/spec/AD/story/repair 全链路 | 多数 readiness 状态仍由 Agent 自评 | 8.9/10 |
| ECC `skill-comply` | supportive/neutral/competing 行为时序合规 | 语义分类含模型判断，真实运行成本较高 | 8.8/10 |
| OpenSpec | artifact DAG、delta、CLI JSON contract | verify 默认不阻断 archive | 8.6/10 |
| Hermes Agent | TDD/debugging/Skill authoring/security infrastructure | 计划与纪律 Skill 本身缺完整行为评估 | 8.4/10 |
| Spec Kit | Constitution、独立 story slice、cross-artifact analysis | 严格测试并非默认硬要求 | 8.3/10 |
| Awesome Copilot | 结构化 spec/plan、稳定 ID | 以模板和文本规则为主 | 6.5/10 |

这些分数是针对增强当前 Skill 的适用度，不是项目总体质量排名。

### 最终合成架构

```text
BMad SPEC/memlog/companions + repository authority
  -> VDD intent kernel and preservation map
BMad AD-n + durable standards/ADRs
  -> inherited invariants and non-bypassable constraints
FR/NFR/UX-DR/stories or repository requirements
  -> stable requirement registry and vertical behavior slices
spec delta + executable contracts + validator RED fixtures
  -> candidate plan authorization
implementation + append-only run/evidence ledger
  -> fresh validation result envelope
failure
  -> intent | contract | validator | slice | implementation | evidence diagnosis
  -> repaired candidate with new hash and predecessor lineage
Bootstrap/protected verifier where required
  -> higher-level handoff or release authority
```

### Final Recommendation

Update `vdd-execution-plan` as a portable strict-VDD Skill with an optional first-party BMad adapter. Add a machine-owned self-contract, deterministic pass/fail fixtures, trace-order tests, exact result-envelope semantics, delta/drift rules, repair baseline/apply rules, and requirement-quality checks. Preserve the target-directory `tools/validate_all.py` as the only plan-specific composite validator; the Skill's own validator must never claim arbitrary business-plan correctness.

## Source Verification and Research Limitations

- Public GitHub sources were inspected at fixed commits recorded throughout this report.
- Local BMad sources were inspected from the installed 6.10.0 files under `.agents/skills/` and `_bmad/`.
- Public license checks found root MIT licenses for Spec Kit, OpenSpec, Superpowers, Awesome Copilot, Hermes Agent, OpenClaw, Everything Claude Code, and Claude Code Spec Workflow; CheckMate uses Apache-2.0. The inspected `informalsystems/vdd` checkout had no root license and was treated as conceptual-only.
- Repository popularity is background context only and was not treated as proof of verification quality.
- No unauthorized subagent or cross-model fresh-context evaluation was run. Deterministic fixture tests can prove the evaluator and contract behavior, but not full cross-model Skill compliance.
- Final acceptance of the improved Skill requires actual official validation, local self-tests, and mutation results after implementation.

---

**Technical Research Completion Date:** 2026-07-13
**Source Verification:** Fixed GitHub commits plus local BMad 6.10.0 sources
**Confidence:** High for inspected source behavior; explicitly limited for cross-model behavioral compliance
