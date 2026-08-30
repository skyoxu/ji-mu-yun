---
title: VDD 与 Quick Dev Chapter 4/5/6 通用能力升级
status: final
created: 2026-08-31
updated: 2026-08-31
source_input: docs/vdd-quick-dev-chapter-4-5-6-capability-upgrade-draft.md
---

# PRD：VDD 与 Quick Dev Chapter 4/5/6 通用能力升级

## 0. 文档目的

本 PRD 将 Chapter 4/5/6 能力补强草案提炼为面向 VDD、Quick Dev TDD 和工具链维护者的正式产品合同。它定义可观察的能力、边界、成功指标和验收口径；协议字段、执行阶段和模块落点保存在同目录 `addendum.md`。本文不把文档、计划状态或治理 receipt 当作实现证据，也不重写历史计划证据。

## 1. 愿景

工具链维护者可以把原始需求稳定地编译成完整、可追溯且可执行的验证计划，再由 Quick Dev 以真实 RED → GREEN → REFACTOR 生命周期实施。每个 Acceptance 都能追溯到 source、slice、测试意图和真实 observation，失败会给出可行动的 failure family，而不是模糊的红绿状态。

该能力服务于 AI 主导、单人维护的 self-hosted 开发流程。它把返工和假绿降到最低，并让中等规模任务在约一小时内完成确定性闭合。开发环境默认不被 external review、candidate binding 或 authorization 阻塞；这些治理能力仍可在 test/production 环境启用，但不改变 TDD 真实性。

## 2. 目标用户

### 2.1 Jobs To Be Done

- 工具链维护者需要把需求拆成可观察的 obligation、Acceptance 和最小实施 slice。
- Quick Dev 执行维护者需要运行真实进程并区分 expected RED、unexpected green、harness failure 与 repo noise。
- 评审和发布维护者需要从 Acceptance 追溯到独立证据，并能在变更后只重放受影响的生命周期。
- 单人 self-hosted 开发者需要在中断或失败后恢复有效 lineage，而不是依赖目录扫描或“最新成功结果”。

### 2.2 非用户（v1）

- 终端业务用户、游戏项目用户和远程多节点调度平台。
- 需要 Chapter 6.7 LLM review、6.8 多 reviewer Needs Fix 或游戏仓专用 6.9 pre-commit pipeline 的团队治理流程。
- Taskmaster MCP 本身；当前仅兼容少量 legacy 数据模型，不恢复已移除的 MCP。

### 2.3 关键用户旅程

- **UJ-1：林工编译一个需求的可实施计划。** 林工提供带来源的需求，工具链提取 obligations，生成可判定 Acceptance，检查多对多 exact cover 与 write set，最终只在没有 hard-uncovered 时输出 plan-ready。
- **UJ-2：周工执行一个真实 TDD slice。** 周工读取 recommendation，冻结 selector、target 和 fixture，观察预期 RED，在合法生产写集内实现，再以同一 selector 完成 GREEN、REFACTOR 和 slice-ready；任何 timeout 或无关失败都不会被算作通过。
- **UJ-3：陈工恢复并验收一条中断链路。** 陈工使用显式 run-local predecessor 恢复，工具链验证 candidate、hash、assertion 和依赖闭包；变化只使受影响 observation 失效，terminal 重新计算完整 Acceptance 覆盖。
- **UJ-4：赵工验证执行器本身。** 赵工用独立 judge 和 detached positive/negative/mutation fixtures 测量假绿、错误路由和历史扫描回归，确认被测 Quick Dev 不能自报完成。

## 3. 术语表

- **VDD**：定义需求、验收语义、来源和失败意图的验证驱动流程。
- **Quick Dev**：将 VDD intent 物化并执行为 TDD slice 的工具链。
- **Obligation**：带 source ref、行为语义和活动状态的不可遗漏需求义务。
- **Acceptance**：可观察、可判定并可回链到 obligation 的验收语义单元。
- **Slice**：能够在一个合法写集内完成 RED、GREEN、REFACTOR 的最小实施增量。
- **Failure intent**：VDD 声明的预期失败身份和禁止结果；不包含执行 receipt。
- **Selector identity**：绑定 target、fixture、assertion 和执行范围的稳定语义身份。
- **Verification lane**：`unit`、`integration`、`matrix` 或 `runtime` 中与 Acceptance 复杂度相匹配的验证强度。
- **Production owner**：负责使某个行为转绿的生产模块或受控路径集合。
- **Observation**：由真实进程执行派生的断言结果、分类和证据引用。
- **Run state**：`planned-only`、`observed-run`、`recovered-run` 或 `invalid-run`。
- **Exact cover**：requirement → obligation → Acceptance → source ref → slice → RED intent → verification lane → terminal aggregation 的完整且无孤立边的多对多覆盖，不要求 exclusive partition。
- **Terminal aggregation**：对全部 active Acceptance 与显式 slice lineage 重算覆盖并执行终局验证的确定性过程。
- **Implementation-complete**：所有 active Acceptance 都有经验证的真实生命周期证据并通过终局语义门禁的结果。

## 4. 功能需求

### 4.1 需求语义与计划编译

#### FR-1：obligation 基线

系统必须从明确列出的原始来源提取稳定的 obligation，保留 source ref、锚点、语义摘要、类型、活动状态以及依赖或冲突关系。任何 active obligation 遗漏都必须阻断 plan-ready。

#### FR-2：Acceptance 编译

系统必须将 obligation 编译为 observable、discriminating、attributable、implementable、testable、stage-correct 且 non-self-judging 的 Acceptance，并保留每条强制语义。

#### FR-3：多对多来源映射

系统必须支持 requirement、obligation、Acceptance 和 source ref 的多对多映射，并能双向查询；不得用单一 terminal Acceptance 吞并未展开的语义。

#### FR-4：语义 preflight 与 repair recommendation

在昂贵模型调用或完整计划生成前，系统必须检查 active source、可观察性、hard-uncovered、孤立节点、过宽 Acceptance、缺失 RED intent 和 lane 不匹配，并输出结构化 repair recommendation。

#### FR-5：exact-cover gate

系统必须验证 obligation → Acceptance → source ref → slice → RED failure intent → verification lane → terminal aggregation 的 sound-and-complete 多对多覆盖；`hard_uncovered`、orphan Acceptance、orphan slice 和无来源 RED intent 必须为零。

#### FR-6：确定性 slice 分解

系统必须依据 production owner、verification lane、failure family、state transition、依赖、fixture/runtime 和合法写集进行稳定的 split/merge。不同 owner、生命周期、独立失败机制或不相容写集不得被强行合并。

#### FR-7：写集可行性

plan-ready 前系统必须证明 RED selector、测试/fixture、输入 materializer、生产 owner、validator 和 planned new files 都位于相应合法写集；无法在合法写集内转绿时必须返回 VDD repair。

#### FR-8：语义基线冻结

开发态只冻结 requirements identity、Acceptance/ref mapping、slice 依赖、selector intent、allowed write set 和 terminal predicate，不要求 external review、签名或 authorization 才能开始本地 TDD。

### 4.2 Quick Dev TDD 执行

#### FR-9：recommendation-only 路由

每次昂贵动作前系统必须输出只读的下一动作、禁止动作、原因、阻断项、可复用 observation 和失效 observation；该阶段不得运行测试、创建 run 或修改状态。

#### FR-10：显式生命周期状态

系统必须区分 planned-only、observed-run、recovered-run 和 invalid-run。planned-only、timeout-no-observation、harness failure 和 repo noise 永远不能满足 RED、GREEN、REFACTOR 或 completion。

#### FR-11：真实 RED 物化与分类

Quick Dev 必须根据 VDD failure intent 解析真实生产入口、selector 和 fixture，生成 shell-free descriptor，执行真实进程，并从实际 exit、输出和断言派生 observed failure。只有 executions ≥ 1 且符合预期失败的 RED 才能进入实现。

#### FR-12：失败分类与止损

系统必须至少区分 semantic-contract-gap、expected-red、unexpected-green、task-implementation-failure、test-harness-failure、target-binding-failure、repo-noise、timeout-no-observation、repeated-deterministic-failure 和 artifact-integrity，并对重复确定性指纹停止无效重跑。

#### FR-13：同一 selector 的 GREEN 与 REFACTOR

GREEN 和 REFACTOR 必须重跑与 RED 相同的 selector identity、target、fixture、assertion scope 和安全 cwd；不得通过删减 case、替换入口或复制预期值制造绿色结果。

#### FR-14：生产实现写集门禁

只有 clean expected-red observation 才能调用实现 worker。实现后的 changed paths 必须完全落在 production write set，且不得改写 selector、fixture、Acceptance 或历史 evidence。

#### FR-15：slice-ready 语义闭合

系统必须验证每个 Acceptance 有真实 RED/GREEN/REFACTOR assertion edge，artifact ref、hash、run ID、candidate 和 selector identity 可重读匹配，结果由 validator 派生，且 coverage 只来自当前依赖闭包。

#### FR-16：whole-plan terminal

终局聚合器必须读取显式 predecessor，验证 lineage 和 hash，重算 active Acceptance exact cover，重读 assertion artifact，并执行 terminal 及 profile 要求的回归/mutation；只有全部通过才可产生 `implementation-complete`。

### 4.3 恢复、独立性与兼容

#### FR-17：选择性失效与重放

系统必须根据 requirements、selector、fixture、production owner、descriptor compiler、validator、predecessor 和治理 artifact 的变化，精确使受影响 observation 失效并推荐重放范围；普通非语义文档默认不使 observation 失效。

#### FR-18：显式 lineage 恢复

系统必须使用显式路径、run ID 和 hash 恢复 observed-run；不得通过 glob、mtime 或“历史上唯一成功 run”猜测 predecessor。invalid-run 保留历史但不能成为 predecessor。

#### FR-19：独立验收与反假绿

系统必须支持 detached positive、negative、mutation fixtures 及独立 judge，用于验证 observed failure 不是从 registry 复制、producer 不能自报 pass、错误 target 和历史扫描都会被拒绝。

#### FR-20：旧计划只读兼容

系统必须提供 v1 execution plan 的只读兼容边界和迁移建议，不得把 8-25 计划 ID 特判写入通用 router，也不得重写历史 evidence。

### 4.4 成本、配置与终止

#### FR-21：执行 profile

系统必须提供 fast-ship、standard 和 self-hosted profile；profile 只能调整成本和验证范围，不能降低真实进程、exact cover、selector 绑定和禁止自报 pass 等真实性要求。

#### FR-22：确定性终止与推荐

当失败属于 semantic-contract-gap、hard-uncovered、harness failure、selector 无 case 或重复 deterministic fingerprint 时，系统必须在第一次或第二次路由停止无效重跑并返回明确的 repair/stop recommendation。

## 5. 非目标

- 不恢复 Taskmaster MCP，不复制 Godot、GdUnit、overlay 或游戏仓专用数据模型与流水线。
- 不把 Chapter 6.7 LLM review、6.8 多 reviewer、游戏仓专用 6.9 pre-commit pipeline 或 commit/PR/release authority 纳入 Quick Dev。
- 不重写 8-25 历史 evidence，不以增加 hash、schema、receipt 文件数量作为成功指标。
- 不让 VDD 或 Quick Dev 独立规划、实现并验收自身全部改造；必须使用 detached fixtures 和新任务盲测。
- 不以模型输出、状态字符串、artifact 存在或治理 receipt 替代真实执行。

## 6. MVP 范围

### 6.1 In Scope

- VDD obligation baseline、Acceptance 语义稳定化、source refs、exact cover 和 slice/write-set feasibility。
- Quick Dev recommendation、显式 run state、真实 RED/GREEN/REFACTOR、failure taxonomy、选择性重放和轻量语义闭合。
- plan-local whole-plan terminal deterministic validation。
- Windows `py -3`/pytest 兼容、detached fixtures、mutation 回归和 8-25 replay。
- development 默认不产生治理阻塞，test/production 保留可配置治理开关。

### 6.2 Out of Scope for MVP

- 远程分布式执行、跨仓库调度和完整 CI/CD 平台。
- 多 reviewer 治理、发布签名和外部授权自动化。
- 长批次 jitter/shard/quarantine 全套能力。
- [ASSUMPTION] 本期不承诺对所有历史 v1 计划自动迁移；只需只读解析和明确的 compatibility adapter 边界。

## 7. 成功指标

**Primary**

- **SM-1 需求召回率**：在维护的 curated requirements fixtures 上，active obligation 被正确提取的 recall ≥ 95%；unsupported/invented obligation precision ≥ 95%。验证 FR-1、FR-2。
- **SM-2 语义覆盖闭合**：active obligation → Acceptance → source ref → RED intent → slice 的有效覆盖率为 100%，`hard_uncovered=0`。验证 FR-3 至 FR-7。
- **SM-3 TDD 真实性**：所有 RED/GREEN/REFACTOR observation 的 executions ≥ 1；planned-only、timeout、repo-noise、harness failure 和 unexpected green 不得被计为通过。验证 FR-10 至 FR-16。
- **SM-4 中等任务闭合时间**：定义好的中等任务在 standard profile 下从 plan-ready 到 implementation-complete 的目标时长 ≤ 60 分钟；超时原因必须可分类。验证 FR-9 至 FR-16。

**Secondary**

- **SM-5 反假绿覆盖**：detached fixtures 覆盖所有 failure family 及关键结构 mutation，错误 target、复制结果、未来 evidence、历史扫描和自报 pass 的放行率为 0%。验证 FR-12、FR-19。
- **SM-6 选择性重放准确度**：对 requirement、selector、fixture、production owner、validator、predecessor 和普通文档变化，重放/复用决策与定义矩阵一致率 ≥ 99%。验证 FR-17、FR-18。
- **SM-7 新任务泛化**：至少一个未用于设计工具链的中等新任务无需修改 VDD/Quick Dev 本身即可完成完整闭合。验证 FR-6、FR-20、FR-21。

**Counter-metrics（不得优化）**

- **SM-C1 误报通过率**：不得通过降低 assertion、缩小 case 集或增加状态/receipt 数量提升完成率；任何 false-green 放行均为失败。
- **SM-C2 无效重跑率**：相同 deterministic fingerprint 的第三次原参数重跑率必须为 0；不能通过无限延长 timeout 提高表面成功率。
- **SM-C3 复杂度膨胀**：新增 artifact、hash 绑定和特殊计划分支应保持最少；不能以文件数量或模型调用次数作为交付指标。

## 8. 跨切质量与约束

- **确定性与可重放**：同一输入应生成稳定 ID 和等价 partition；所有完成 predicate 由确定性程序判断，模型只能给非阻断建议。
- **安全**：执行命令使用参数数组和 `shell=False`；cwd、目标和写集必须位于仓库安全边界；worker 不能访问治理 receipt 代替实现上下文。
- **证据完整性**：receipt、observation 和 terminal result 必须包含实际执行身份、hash、计数和 assertion 引用；producer 不得自报状态。
- **运行兼容**：支持 Windows、`py -3`、pytest 和旧计划只读兼容；测试使用临时 workspace 和数据库，不修改 live state。
- **隔离与恢复**：历史 run append-only；显式 lineage 优先于目录推断；invalid-run 永不成为 predecessor。
- **阶段边界**：VDD 只声明 intent，不写执行 artifact；Quick Dev 物化并执行；terminal 只能产生 `implementation-complete`，不能发布外部 `acceptance-passed`。

## 9. 风险与缓解

- 需求被过度压缩：以 obligation guard、source anchor 和 exact-cover gate 阻断。
- RED 不是可转绿行为：在 plan-ready 做 selector/owner/write-set feasibility，并拒绝固定失败。
- 执行器自证：使用独立 judge、detached fixtures 和 predecessor 冻结。
- 历史证据漂移：采用显式 run-local lineage、candidate/hash 重算和选择性失效。
- 性能目标诱发跳过验证：以 SM-C1、SM-C2 和 profile 不可降低真实性作为反制。

## 10. Open Questions

1. **Obligation 与 Acceptance 的规范化边界**：Owner=VDD；在首次实现 schema 前冻结；若同一语义无法稳定拆分则提交产品决策。
2. **Slice split/merge 的确定性阈值**：Owner=VDD/Architecture；以 owner、lane、failure family、state transition 和 write set 冲突为硬门；数量阈值仅作诊断，不得覆盖硬门。
3. **一条 selector 覆盖多 Acceptance 的 assertion 表达**：Owner=Spec；在 semantic plan schema 定稿前决定独立 assertion edge 格式；缺少独立 edge 时必须拆分。
4. **轻量 semantic validator 的纯确定性范围**：Owner=Architecture；默认只允许确定性校验；模型只能输出 warning，除非未来批准新的非阻断用途。
5. **v1 compatibility adapter 边界**：Owner=Architecture；首个旧计划迁移试验前冻结；任何需要写旧 evidence 的方案返回 VDD repair。
6. **unexpected green 的最低证明**：Owner=Quick Dev；在 RED materializer 实现前定义 regression/current-behavior proof；不能把绿色直接当作实现完成。
7. **60 分钟目标的任务规模定义与测量**：Owner=Product；在盲测前发布 fixture size、环境和计时规则；不同规模不得混算。
8. **fast-ship、standard、self-hosted 的具体差异**：Owner=Architecture；在 profile schema 定稿前冻结；所有 profile 保持真实性硬门。
9. **变化只重算 coverage 还是重跑 RED 的边界**：Owner=Spec；在 invalidation matrix 定稿前冻结；不确定时选择更严格的重跑。
10. **detached fixture 作者与被测 skill 的独立性**：Owner=Maintainer；在验收前由独立目录/提交和只读 judge 证明；不能由被测 skill 自己生成唯一 fixture。

## 11. Assumptions Index

- §6.2：本期只读兼容历史 v1 计划，不承诺自动迁移全部历史格式。
- §1：中等任务目标以约一小时为产品目标，具体规模和测量规则仍待 Open Question 7 冻结。
- §2.3：工具链维护者均能访问仓库和本地 Python/pytest 环境；远程执行不是 v1 目标。
