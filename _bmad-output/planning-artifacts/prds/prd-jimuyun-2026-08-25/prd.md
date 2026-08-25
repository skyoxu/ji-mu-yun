---
title: VDD 与 Quick Dev 语义验证及独立裁判恢复
status: final
created: 2026-08-25
updated: 2026-08-25
source_input: docs/know75.txt, docs/know76.txt
---

# PRD：VDD 与 Quick Dev 语义验证及独立裁判恢复

## 0. 文档目的

本 PRD 定义 Ji Mu Yun self-hosted 工具链如何从“声明验收意图”走到“由真实进程产生可审计 observation”，并以 Acceptance ID exact cover 判定 `implementation-complete`。文档面向 VDD、Quick Dev、工具链维护者、评审者和下游架构/故事工作流。FR 使用稳定编号，技术机制和文件落点保存在 `addendum.md`。本 PRD 不修改历史计划、08-05 实现、Acceptance Skill 或历史证据。

## 1. 愿景

VDD 负责定义“什么算验证过”，Quick Dev 负责冻结目标、测试和 fixture，并调用独立 oracle executor 真实运行被测对象。任何候选实现都不能通过自报 `status=pass`、复制预期值或替换执行目标来证明自己正确。

完成后，维护者能从一个验收 ID 追溯到 oracle、执行 case、process receipt、输入 fixture 和最终 observation；失败会指出 failure family，而不是只给出模糊的红/绿状态。旧计划继续只读兼容，新建或修复的 VDD 计划默认使用 semantic-verification 合同。

## 2. 目标用户

### 2.1 Jobs To Be Done

- 工具链维护者需要定义足够丰富、可拒绝假绿的验证语义，而不是把“文件存在”当作行为证明。
- Quick Dev 执行器维护者需要在不信任 SUT 自报结果的前提下运行测试、fixture 和矩阵，并生成稳定证据。
- 评审者需要确认每个 active Acceptance ID 都有真实 observation、receipt 和未漂移的 hash。
- self-hosted 开发者需要用冻结的前代 judge 验证新一代 Quick Dev，避免验证器自证。

### 2.2 非用户（v1）

- 不面向终端业务用户或游戏项目开发者。
- 不把 PRD 变成通用 CI 平台、远程调度平台或多节点执行系统。

### 2.3 关键用户旅程

- **UJ-1：林工为一个验收需求定义可拒绝假绿的 oracle。**
  - **角色与上下文：** 工具链维护者，正在创建或修复一个 VDD 执行计划。
  - **入口状态：** 已有 Acceptance ID 和行为描述，尚未生成执行命令。
  - **路径：** 描述 oracle 类别、subject role、case roles、预期失败身份和 green observations；为每个 Acceptance ID 建立覆盖；运行验证器检查 matrix 是否有真实 case producer。
  - **高潮：** 验证器拒绝只有“文件存在”RED、缺失覆盖、只有 prose 的 rollback 或自证 judge。
  - **结果：** 生成可供 Quick Dev 冻结的 semantic-verification intent。

- **UJ-2：周工在 RED 阶段冻结可重放的执行输入。**
  - **角色与上下文：** Quick Dev 执行器维护者，准备实现一个 slice。
  - **入口状态：** 已通过 VDD 语义检查，存在目标、测试选择器和 fixture。
  - **路径：** 冻结 executable、argv、cwd、target、fixture 内容 hash、RED oracle/hash；执行正向、负向和 mutation case；验证 0 tests + exit 0 不能通过。
  - **高潮：** 真实进程 receipt 显示执行了预期 target 和 case 数量，而不是只接受 SUT 汇总。
  - **结果：** RED 证据可供 GREEN/REFACTOR 复用且不可静默漂移。

- **UJ-3：陈工用外部 judge 验证 self-hosted Quick Dev。**
  - **角色与上下文：** 工具链发布维护者，正在升级验证器本身。
  - **入口状态：** 候选实现和冻结的前代测试/judge 均可用。
  - **路径：** 运行假绿回归 fixtures（复制 observed_result、忽略 target、硬编码矩阵、替换 root、validator 自证等）；记录每个 failure family；确认修正版通过且未改写 08-05 原目录。
  - **高潮：** 候选 Quick Dev 只能作为 SUT，被独立 judge 判定是否通过。
  - **结果：** 只有通过 N→N+1 外部验证的候选实现才可成为下一代执行器。

- **UJ-4：赵工在跨模块变更前获取实施建议并恢复有效 observation。**
  - **角色与上下文：** 维护者面对复杂度不明的 slice，或从中断会话恢复。
  - **入口状态：** 变更可能涉及多个测试根、schema、validator 或 runtime；已有部分 artifact。
  - **路径：** 运行 preflight，确认 complexity class、verification lane、context lookup 和 minimum RED scope；先读取 recommendation-only 路由，再决定运行 RED、修复合同、重放受影响 oracle 或停止；对未受语义影响的 observation 尝试复用。
  - **高潮：** planned-only 不被误报为完成，timeout-no-observation 不被当作 pass/fail，unexpected_green 被转为 regression 或要求证明既有行为。
  - **结果：** 得到 observed-run、recovered-run 或明确 invalid-run，并避免对相同 deterministic failure 原参数盲目重跑。

## 3. 术语表

- **VDD**：定义需求、验收语义和失败身份的验证驱动文档流程。
- **Quick Dev**：把 VDD intent 编译并执行为 TDD slice 的工具链。
- **Oracle**：独立、可执行的判定定义，可覆盖一个或多个 Acceptance ID。
- **Semantic Verification Contract**：`semantic-verification.v1` 结构化验证意图合同。
- **SUT**：被测目标（System Under Test），可以是候选 Quick Dev，但不能同时担任唯一 judge。
- **Fixture**：用于 positive、negative、mutation 或 recovery case 的冻结输入/目标内容。
- **Observation**：由真实执行过程派生的结果，包含 receipt、身份和每个 case 的实际结果。
- **Process Receipt**：记录 executable、argv、cwd、exit code、stdout/stderr hash 和执行计数的证据。
- **Acceptance ID**：需求中的稳定验收标识；active ID 必须被 oracle exact cover。
- **Failure Family**：可归类的失败身份及其 expected failure ID。
- **Implementation-complete**：所有 active Acceptance ID 均有合格 observation 且通过独立性、hash 和执行数量门禁的终态。
- **Preflight**：执行前对复杂度、验证 lane、上下文查找和最小 RED 范围的机器判定。
- **Verification Lane**：`unit`、`integration`、`matrix` 或 `runtime` 之一，表示所需验证强度。
- **Planned-only**：只完成命令解析、路由或计划生成，尚未真实执行，不得授权完成。
- **Observed-run**：真实进程已执行并产生 process receipt 的运行。
- **Recovered-run**：从仍满足完整性和身份约束的真实 observation 恢复的运行。
- **Invalid-run**：artifact integrity 或执行身份不成立的运行，不能参与完成门禁。
- **Recommendation-only**：只输出下一步建议、禁用动作、阻塞原因和可复用/失效 observation，不直接执行昂贵动作。
- **Execution Profile**：控制执行成本与范围的 `fast-ship`、`standard` 或 `self-hosted` 配置，不得降低真实性底线。

## 4. 功能需求

### 4.1 VDD 语义合同

**描述：** VDD 输出验证意图，但不执行 RED、不生成 command、receipt 或 hash。每个 oracle 必须足以驱动真实执行，并能表达行为、集成、矩阵和恢复语义。

#### FR-1：定义 semantic-verification.v1 oracle

VDD 可以为一个或多个 Acceptance ID 定义 oracle，并填写 `oracle_id`、`covers_acceptance_ids`、`oracle_class`、`test_selector`、`subject_role`、`required_case_roles`、`red_failure_family`、`expected_failure_ids`、`green_expected_observations`、`minimum_executed_cases` 和 `independent_judge_required`。

**可验证后果：**
- 缺少任一必填字段、重复 oracle_id 或引用不存在的 Acceptance ID 时，验证器返回确定性失败。
- 一个 oracle 可覆盖多个 Acceptance ID，但所有 active ID 必须被 exact cover，不能遗漏或额外引用未声明 ID。

#### FR-2：拒绝结构性假绿语义

VDD 验证器必须拒绝只有“文件存在”类 RED 的行为需求、没有真实 case producer 的 matrix、validator/receipt/evidence 工具缺少 positive + negative/mutation fixture、只有 prose 的 rollback，以及让 self-hosted 候选实现作为唯一裁判的定义。

**可验证后果：** 每类违规都产生稳定 failure family 和 expected failure ID；拒绝结果不能由候选实现提供的 status 覆盖。

#### FR-10：执行前完成复杂度与验证 lane preflight

VDD semantic-verification 必须声明 `complexity_class`（`simple|complex|architectural`）、`verification_lane`（`unit|integration|matrix|runtime`）、`context_lookup_required`、`context_lookup_reason`、`minimum_red_scope` 和 `upgrade_conditions`。preflight 应先判断 unit 是否足够；涉及多个测试根、跨模块、合同或 runtime 时自动升级 lane。

**可验证后果：** 语义不足、上下文查找必需但未完成或升级条件命中时，返回 `semantic-contract-gap` 并路由到 `repair-vdd`，Quick Dev 不得临时猜测试；检测到 `unexpected-green` 时必须进入 regression 模式或要求证明既有行为。

### 4.2 Quick Dev 执行冻结

**描述：** 通过 VDD 验证后，Quick Dev 在 candidate freeze 阶段把 intent 编译成真实执行描述符，保证 RED 到 GREEN/REFACTOR 的判定基线不变。

#### FR-3：冻结真实执行上下文

Quick Dev 必须以 `shell=false` 绑定 executable、argv、cwd、真实 target、fixture 内容 hash 和 RED 测试/oracle hash；GREEN、REFACTOR 不得替换 RED oracle 或预期结果。

**可验证后果：** 描述符能重建同一执行上下文；target、fixture 或 oracle hash 发生漂移时，生命周期进入失败而非继续宣称完成。

#### FR-4：由独立 oracle executor 派生 observation

Quick Dev 必须从真实进程派生 exit code、stdout/stderr hash、target identity、fixture identity、executed case/test count、failure family/ID 及每个 matrix case 的实际结果；不得接受 SUT 直接提供的 `status` 或 `observed_result`。

**可验证后果：** 缺失 process receipt、执行数量为零、target identity 不匹配或结果仅来自预期值复制时，observation 无效。

#### FR-5：支持测试运行器与 case-matrix 两类执行

系统必须支持解析 pytest、unittest、dotnet-test 等测试运行器，并支持逐项执行 positive、negative、mutation fixture 的 case-matrix。测试运行器出现 0 tests + exit 0 时必须失败；case-matrix 必须自行比较实际 exit/output 与预期。

**可验证后果：** 两类 adapter 均返回统一 observation 结构；任一 case 未执行或只返回汇总 pass 都不能满足 FR-4。

### 4.3 完成门禁与证据

#### FR-6：以 Acceptance ID exact cover 判定完成

系统只能在以下条件全部满足时输出 `implementation-complete`：所有 active Acceptance ID 有当前 observation；每个 observation 有真实 process receipt；`minimum_executed_cases > 0`；target、fixture、oracle hash 未漂移；self-hosted independence gate 通过。

**可验证后果：** 任一条件缺失时终态不是 `implementation-complete`，并返回可定位的 failure family。

#### FR-7：生成语义证据

系统必须生成 `semantic-observation.v1.json` 和 `acceptance-coverage.v1.json`，使评审者能从 Acceptance ID 追溯 oracle、case、receipt、fixture 和实际结果。

**可验证后果：** 证据包含 schema 版本、生成时间、目标/fixture/oracle hash、覆盖集合和失败身份；无法追溯的证据不得进入完成门禁。

### 4.4 Self-hosted 独立性与回归

#### FR-8：执行 N→N+1 独立验证

修改 Quick Dev 或 VDD 验证器自身时，系统必须先冻结黑盒测试、fixtures 和 judge hash，再用前代/外部 judge 将候选实现作为 SUT 执行；候选实现不得提供最终判定。

**可验证后果：** 候选实现只有在外部 judge 验证通过后，才可被登记为下一代执行器；自调用或同一进程同时充当 SUT 与唯一 judge 时失败。

#### FR-9：覆盖假绿回归案例

回归集合至少覆盖：复制 `observed_result` 直接 pass、replay 忽略传入 target、硬编码正负结果但不执行 fixture、矩阵结果全部复制预期、0 tests 返回 0、descriptor root 被调用者目录替换、validator 自证、Acceptance ID 未覆盖、rollback 无 runnable probe。

**可验证后果：** 每个案例有明确 failure family；当前假绿实现必须被阻断，修正版 fixture 必须通过。

#### FR-11：区分 planned、observed、recovered 和 invalid 运行

Quick Dev 必须把运行状态明确标记为 `planned-only`、`observed-run`、`recovered-run` 或 `invalid-run`。只有 observed-run 或满足完整性证明的 recovered-run 可贡献 observation；planned-only 绝不能授权完成，invalid-run 必须使相关覆盖失效。

**可验证后果：** 仅有命令解析、路由、计划或报告而无真实 receipt 时，状态保持 planned-only；artifact integrity、target identity 或 fixture identity 不成立时，状态为 invalid-run。

#### FR-12：提供 recommendation-only 路由

在任何昂贵动作前，Quick Dev 必须能输出 `recommended_action`（`run-red|fix-red-contract|run-green|run-refactor|run-terminal|repair-vdd|handoff-acceptance|stop`）、`forbidden_actions`、`reason`、`blocked_by`、`reusable_observations` 和 `invalidated_observations`。该输出只提供建议，不直接执行完整 slice。

**可验证后果：** 缺少 oracle 合同时建议 `repair-vdd`；已有可复用 observation 时不得无理由全量重跑；触发止损条件时建议 `stop` 并列出阻塞原因。

#### FR-13：实施失败分类与止损

Quick Dev 至少支持 `semantic-contract-gap`、`expected-red`、`unexpected-green`、`task-implementation-failure`、`test-harness-failure`、`target-binding-failure`、`repo-noise`、`timeout-no-observation`、`repeated-deterministic-failure` 和 `artifact-integrity`。`repo-noise` 不得充当 RED，`test-harness-failure` 不得进入 GREEN，`timeout-no-observation` 不得等同于 pass 或 fail。

**可验证后果：** 相同 deterministic fingerprint 连续出现时必须停止原参数重跑；oracle 合同缺失直接回到 VDD repair；每次 stop 都保留可审计 fingerprint 和 recommendation。

#### FR-14：按变化影响选择性重放与失效传播

系统必须按变化类型决定 observation 是否复用：代码/测试/schema/validator 变化重跑受影响 oracle；普通非语义文档变化可复用已验证 observation；requirements/acceptance/plan 语义变化须重新计算 acceptance coverage；fixture/target/command 变化使对应 RED、GREEN、REFACTOR 全部失效。

**可验证后果：** 每个 oracle 输出 `reusable`、`invalidated_by` 和 `required_next_action`；失效 observation 不得参与 implementation-complete。

#### FR-15：提供不降低真实性的执行 Profile

系统可以提供 `fast-ship`（只运行精确受影响 oracle）、`standard`（完整 slice terminal、负例和 mutation matrix）和 `self-hosted`（前代/frozen judge 与完整反假绿套件）Profile。Profile 只能调节成本和范围，不能降低真实进程执行、exact cover、非零 case/test、target/fixture 绑定或禁止自报 pass 的底线。

**可验证后果：** 任一 Profile 缺少真实性底线字段时配置无效；`self-hosted` 缺少 predecessor/frozen judge 时不得进入完成门禁。

#### FR-16：保留顶层职责边界

Quick Dev 不得吸收 Chapter 6 的 LLM Review、Needs Fix 多 reviewer 协调、commit 前全仓硬检查、Godot/GdUnit/taskmaster/overlay 业务规则或 Chapter 5 批量 jitter、shard、quarantine。上述能力由 Acceptance/Review 或顶层协调器承接。

**可验证后果：** Quick Dev 路由输出对这些动作只能给出 `handoff-acceptance` 或 `stop`，不得伪造已完成的 review、commit authority 或业务仓验收。

#### FR-17：支持跨会话恢复

顶层协调器必须能依据 recommendation、reusable/invalidated observations、failure fingerprint 和最新 live blocker 恢复运行，而不依赖聊天上下文或隐式 loop 判断。

**可验证后果：** 恢复时先消费当前 artifact integrity、执行身份和 live blocker；历史 summary 不能覆盖当前 invalid-run 或 stop 决定。

## 5. 非功能需求与约束

### 5.1 可审计性与可重放

- NFR-1：同一冻结描述符和 fixture 在相同环境下产生可比较的 target、fixture、oracle hash 及 receipt；差异必须显式报告。
- NFR-2：所有 observation 能通过 Acceptance ID exact cover 反查，不依赖聊天上下文或人工日志。

### 5.2 安全与独立性

- NFR-3：SUT 无权写入或覆盖 judge 结果、receipt、coverage 和完成状态。
- NFR-4：执行默认不经 shell 解释，target/cwd 必须受描述符约束，防止调用者替换根目录或执行对象。

### 5.3 兼容与演进

- NFR-5：旧计划保持只读兼容，不批量迁移；新 VDD create/repair 默认使用 semantic contract。
- NFR-6：旧合同不得用于新的 self-hosted/toolchain `implementation-complete` 判定。

### 5.4 运行质量

- NFR-7：验证失败必须返回稳定、机器可读的 failure family/ID，避免仅输出自由文本。
- NFR-8：验证器、executor 和 schema 变更必须有正向、负向及 mutation 测试；不得以关闭测试降低门槛。
- NFR-9：preflight、状态、recommendation、failure family 和复用判定必须是机器可读且确定性的。
- NFR-10：Profile、恢复和止损逻辑不得把 timeout、repo noise、planned-only 或 unexpected-green 转换成隐含通过。
- NFR-11：跨会话恢复必须以当前 artifact integrity、target identity、fixture identity 和最新 live blocker 为权威。

## 6. 非目标

- 不实现多节点调度、远程沙箱、容器/microVM、对象存储或跨区域灾备。
- 不修改 Acceptance Skill、08-05 当前实现、历史 snapshots/logs 或 README/计划治理状态。
- 不批量迁移旧计划，不把旧合同升级为新 self-hosted 完成语义。
- 不让 VDD 直接执行命令、生成 receipt/hash 或替代 Quick Dev executor。
- 不把 Chapter 6 的 review、commit authority、业务仓规则或 Chapter 5 批处理能力并入 Quick Dev。

## 7. MVP 范围

### 7.1 In Scope

- semantic-verification.v1 合同及确定性验证器。
- candidate freeze 描述符与 hash 不漂移门禁。
- 独立 oracle executor、test-runner 和 case-matrix adapter。
- semantic observation、acceptance coverage 证据及 implementation-complete 终态门禁。
- N→N+1 self-hosted 验证和九类假绿回归 fixture。
- preflight、四态运行模型、recommendation-only 路由、失败止损、影响选择性重放和三种真实性 Profile。

### 7.2 Out of Scope for MVP

- 旧计划批量迁移；原因是保持历史兼容和可审计性。
- 多执行节点和分布式 artifact 存储；原因是当前需求聚焦单机 self-hosted 工具链。
- 用户界面、商业化、远程协作和模型能力改造；原因是它们不影响语义裁判正确性。

## 8. 成功指标

**Primary**

- **SM-1：** 100% active Acceptance ID 在完成门禁中拥有当前 observation 和 receipt；验证 FR-6、FR-7。
- **SM-2：** 九类假绿回归 fixture 在候选实现上 100% 被阻断，修正版 fixture 100% 通过；验证 FR-8、FR-9。

**Secondary**

- **SM-3：** 新建/修复 VDD 计划中 100% 使用 semantic-verification.v1；验证 FR-1、NFR-5。
- **SM-4：** 真实执行 case/test count 为零时 100% 不得进入 implementation-complete；验证 FR-4、FR-5。

**Counter-metrics（不应优化）**

- **SM-C1：** 不以减少 fixture 数量或放宽 failure family 来追求更高通过率；反向检查 SM-2。
- **SM-C2：** 不以缩短执行时间牺牲独立 judge、hash 稳定性或 receipt 完整性；反向检查 SM-1、NFR-1。
- **SM-C3：** 不以提高 observation 复用率掩盖语义变化或 fixture 漂移；反向检查 FR-14、NFR-10。

## 9. 开放问题

1. `semantic-verification.v1` 的正式 schema 是否需要为不同 oracle_class 拆分子 schema，还是保持一个可扩展合同？
2. test-runner 对 pytest、unittest、dotnet-test 的最小统一计数语义由哪个维护者签字确认？
3. self-hosted N→N+1 judge 的版本保留和撤销策略是什么？
4. stdout/stderr hash 的规范化（换行、编码、时间戳）是否需要跨平台规则？
5. rollback runnable probe 的最小可执行接口由谁拥有？
6. `unexpected-green` 的既有行为证明需要哪些最小独立证据？
7. deterministic fingerprint 连续次数和 stop-loss 阈值如何按 Profile 配置？
8. recommendation-only 输出由哪个顶层协调器消费，跨会话状态如何持久化？
9. requirements/acceptance 语义变化时，哪些 observation 可以部分复用而哪些必须全部失效？

## 10. 假设索引

- **[ASSUMPTION: 内部工具链产品]**：目标用户是工具链维护者和评审者，不需要终端用户 UI；依据 know75.txt 的 self-hosted/toolchain 语境。
- **[ASSUMPTION: 单机优先]**：MVP 在现有 self-hosted 单机执行环境中完成，不引入分布式调度；依据明确的范围排除项。
- **[ASSUMPTION: 证据文件可追加]**：新证据以版本化 JSON 形式生成并与现有日志并存，不改写历史 evidence；依据兼容要求。
- **[ASSUMPTION: 顶层协调器存在]**：recommendation-only、恢复和 review handoff 由外层协调器消费，Quick Dev 不承担 commit 或 review authority；依据 know76.txt 的职责边界。
