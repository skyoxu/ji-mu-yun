---
status: draft
revision: 2
purpose: bmad-prd-bmad-spec-bmad-architect-input
baseline_commit: 20bb2e939dc63cf01f4a8b031050cd494c18a10e
scope: vdd-execution-plan-and-quick-dev-tdd-adapter
---

# VDD 与 Quick Dev TDD 的 Chapter 4/5/6 能力补强草案

## 1. 文档目的

本文不是执行计划、实现授权或验收结果，而是下一轮 `bmad-prd`、`bmad-spec`、`bmad-architect` 的统一输入草案。

目标是补齐两类核心能力：

1. VDD 能把原始需求完整、可追溯地编译成足够细的实施 slice、Acceptance、source refs 和 RED failure intent。
2. Quick Dev TDD 能按 Chapter 6 的方式执行真实 RED → GREEN → REFACTOR，并以轻量、确定性的语义闭合检查判断是否真的完成，而不是仅凭状态文件或形式化 artifact 宣称完成。

本文吸收：

- `workflow.md` Chapter 4 的 refs/contracts 基线与分阶段冻结思想。
- `workflow.md` Chapter 5 的 acceptance/refs/subtasks 语义稳定化、preflight、coverage 和止损思想。
- `workflow.md` Chapter 6 的 6.3～6.6 preflight、RED、GREEN、REFACTOR、恢复、recommendation 和失败分类思想。
- `docs/know76.txt` 对 planned/observed、recommendation-only、failure family、选择性重放和 execution profile 的补充。
- `execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/` 在规划、修复、执行与复核过程中暴露的系统性问题。

开发环境中的 external review、candidate binding、maintainer authorization、source-freeze/conformance、Skill-input attestation 和报告治理已由 phase-aware governance mode 默认关闭；本文不重新引入这些治理负担。

## 2. 核心结论

8-25 的长期反复不是单一原因造成的，而是三个层次叠加：

1. 规划层：原始需求被压缩成过宽的 Acceptance 和过粗的 slice，部分上游语义没有进入可执行合同。
2. 合同层：Acceptance、refs、selector、write set、producer、predecessor 和阶段 scope 没有形成一致的可实现闭包。
3. 执行层：Quick Dev 缺少 Chapter 6 式的显式 preflight、planned/observed 状态、recommendation-only 路由、失败分类、选择性重放和轻量语义闭合。

因此，不能继续把问题修成更多 plan-local 特例，也不能只扩大 validator、hash 或治理 artifact。应当补齐通用编译与执行能力。

## 3. 必须保持的职责边界

### 3.1 VDD 负责

- 读取原始需求及其明确来源。
- 提取不可遗漏的 requirement obligations。
- 生成可观察、可区分、可实施的 Acceptance。
- 建立 requirement → Acceptance → source refs 的多对多映射。
- 根据行为、生产 owner、验证 lane、failure family 和依赖关系生成 slice。
- 为每个 active Acceptance 声明至少一个 RED failure intent。
- 声明允许修改的生产、测试和文档路径。
- 声明依赖、阶段 scope、terminal scope 和失效传播规则。
- 在 plan-ready 前发现 hard-uncovered、不可执行 selector 意图、write-set 不闭合及语义歧义。

### 3.2 VDD 不负责

- 创建或执行 RED command descriptor。
- 写入 RED receipt、run ID、exit code、observation 或 pass 状态。
- 为制造 RED 而回滚现有正确行为。
- 提前实现目标生产代码。
- 用 plan 文本、hash 或 status 代替真实进程执行。

### 3.3 Quick Dev TDD 负责

- 把 VDD failure intent 解析为当前候选上的 shell-free、可执行 RED descriptor。
- 冻结当前 selector、target、fixture、cwd、argv 和 candidate identity。
- 执行真实 RED，分类 observed failure。
- 在同一 selector 与同一语义输入上完成 GREEN 和 REFACTOR。
- 验证每个 slice 的 Acceptance 闭合。
- 维护 planned-only、observed-run、recovered-run、invalid-run 状态。
- 根据变化影响选择性重放。
- 生成 recommendation-only 下一动作。
- 在 terminal 阶段验证 whole-plan semantic closure。

### 3.4 Quick Dev TDD 不负责

- 补写缺失的上游需求。
- 临时发明 Acceptance 或把模糊需求解释成实现。
- 执行 Chapter 6 的 6.7 LLM Review、6.8 多 reviewer Needs Fix 或 6.9 commit authority。
- 把 timeout、repo noise、harness failure 或 artifact existence 当成 RED/GREEN 证据。

## 4. 从 Chapter 4 吸收的能力：先建立可实施基线，再生成 slice

Chapter 4 本身主要解决 overlay refs 和 contracts baseline，并不直接提供通用 slice 算法。应吸收的是它的顺序约束：

1. 先验证上游语义输入。
2. 再生成最小 skeleton。
3. 先 dry-run/simulate，处理 outlier。
4. limited apply 后冻结 refs。
5. contract baseline 通过后才进入实现。

将这一思想泛化到 VDD，应新增以下能力。

### 4.1 Requirement obligation baseline

VDD 必须先把来源解析为不可静默丢失的 obligations。每条 obligation 至少包含：

- 稳定 ID。
- source ref 和可定位锚点。
- 原始语义摘要。
- 类型：functional、non-functional、boundary、recovery、negative 或 compatibility。
- 是否 active。
- 是否必须产生独立 Acceptance。
- 与其他 obligation 的依赖或冲突。

plan-ready 前必须满足：

- 每条 active obligation 至少进入一个 Acceptance。
- 每个 Acceptance 至少回链一个真实 source ref。
- 不允许仅用一条“terminal covers all”吞并尚未展开的 obligation。
- 任何 hard-uncovered 都直接返回 VDD repair。

### 4.2 Slice decomposition compiler

slice 不是 Acceptance 的同义词，也不必一条 Acceptance 一个 slice。

- Acceptance 是可观察的语义义务。
- slice 是一次能够合法完成 RED → GREEN → REFACTOR 的最小实施增量。
- 一个 slice 可以吸收多条高度内聚的 Acceptance。
- 一条 Acceptance 可以由多个 slice 的 evidence 共同闭合，但必须显式声明 aggregation 规则。

必须拆分 slice 的触发条件：

- 涉及不同生产 owner 或不同模块边界。
- 需要不同 verification lane。
- 存在可以独立观察的 failure family。
- 一个 GREEN 无法在同一合法 write set 内完成。
- 前一部分 evidence 是后一部分的真实 predecessor。
- 某项 coverage 只有在后续阶段才可能产生。
- selector、fixture 或 runtime 环境生命周期不同。

允许合并 slice 的条件：

- 修改路径、owner 和 verification lane 一致。
- Acceptance 共享同一业务行为与 failure mechanism。
- 同一个 RED selector 可以在一次最小实现后共同转绿。
- 合并不会制造未来 evidence、阶段越权或模糊 recovery 边界。

### 4.3 Write-set feasibility preflight

每个 slice 在 plan-ready 前必须进行静态可实现性检查：

- RED 所暴露的失败是否能通过 `allowed_changes.production` 中的路径修复。
- selector 与 fixture 是否位于 tests/write contract 中。
- 输入 materializer、producer、owner 和 validator 的直接修改路径是否齐全。
- planned new file 是否在对应阶段允许出现。
- GREEN 所需的生产入口是否被错误放入后续 slice。
- 如果无法在合法 write set 内转绿，必须在 VDD 阶段修合同，不能等 Quick Dev 固定失败后再发现。

### 4.4 Baseline freeze 的轻量化

开发态只冻结实现所需的语义基线：

- requirements identity。
- Acceptance/ref mapping。
- slice dependency graph。
- selector intent。
- allowed write set。
- terminal predicate。

不要把 external review、签名、候选绑定、source-freeze 或 conformance 加回开发默认路径。

## 5. 从 Chapter 5 吸收的能力：Acceptance 语义稳定化

8-25 的 `00-index.md` 把 Chapter 5 processing 明确列为 non-goal，这是上游需求没有完整进入执行合同的重要原因。新的 VDD 不得在 acceptance 质量不足、refs 漂移或 subtasks 覆盖不清时绕开语义稳定化。

### 5.1 轻量 preflight guard

在任何昂贵模型调用或 plan artifact 生成前，先运行确定性 guard：

- 是否存在 active obligations。
- 是否每条 obligation 有 source ref。
- Acceptance 是否可观察、可判定。
- 是否存在 hard-uncovered。
- 是否存在一条 Acceptance 覆盖过多互不相关行为。
- 是否存在没有 slice 或 RED intent 的 Acceptance。
- 是否存在 slice 没有 Acceptance。
- 是否存在 terminal Acceptance 代替阶段 Acceptance。
- 是否存在 verification lane 与复杂度明显不匹配。

preflight 失败时直接输出结构化 repair recommendation，不继续生成完整计划。

### 5.2 Acceptance 质量模型

每个 Acceptance 至少满足：

- observable：能由进程输出、状态、artifact 内容或明确断言观察。
- discriminating：能区分错误实现与正确实现。
- attributable：能追溯到一个或多个 source refs。
- implementable：能落入至少一个合法 slice/write set。
- testable：存在至少一个 failure intent。
- stage-correct：不会依赖尚未执行的未来 slice。
- non-self-judging：不能由被测 producer 自报 pass。

### 5.3 Exact coverage，而不是 ID 列表相等

VDD 的 plan-ready coverage 应验证完整链：

requirement obligation
→ Acceptance
→ source ref
→ slice
→ RED failure intent
→ verification lane
→ terminal aggregation rule

它是 sound-and-complete 的多对多覆盖，不要求 exclusive partition，但必须同时满足：

- 无 orphan requirement。
- 无 orphan Acceptance。
- 无 orphan slice。
- 无无来源 RED intent。
- 无仅在字符串中出现、却没有执行路径的 coverage edge。

### 5.4 每个 Acceptance 的 refs 和 RED 分配

最低要求：

- 每个 active Acceptance 至少一个 source ref。
- 每个 active Acceptance 至少一个 RED failure intent。
- 对需要 positive、negative、mutation 三类语义的 Acceptance，必须明确三类 case source。
- 同一个 selector 可以覆盖多个 Acceptance，但必须声明每个 Acceptance 对应的 assertion/observation。
- 不允许用一个宽泛的 terminal selector 取代所有局部 RED。
- VDD 只声明 selector intent；真实 descriptor 和 observation 由 Quick Dev 创建。

### 5.5 复杂度与 verification lane

吸收 Chapter 6 6.3 和 `know76`，VDD semantic plan 至少表达：

- complexity class：simple、complex、architectural。
- verification lane：unit、integration、matrix、runtime。
- context lookup required 与原因。
- minimum RED scope。
- upgrade conditions。

建议升级条件：

- Acceptance anchors ≥ 4。
- 多个测试根。
- 跨模块 producer/consumer。
- contract、event、runtime 或 recovery 语义。
- positive/negative/mutation matrix。
- 需要多个独立进程或 independent judge。

### 5.6 语义稳定化输出

BMAD spec 应设计一个紧凑的 machine-readable semantic plan，至少能回答：

- 原始需求是否完整进入 Acceptance。
- 每条 Acceptance 由哪些 refs 支撑。
- 每条 Acceptance 由哪些 slice 实施。
- 每条 Acceptance 的 RED intent 是什么。
- 为什么选择当前 verification lane。
- 哪些变化会使哪些 Acceptance/slice/evidence 失效。

不要求沿用 8-25 的文件数量或 schema 名称；优先一个 owner artifact，避免再次形成几十个相互 hash 绑定的文件。

## 6. 从 Chapter 6 吸收的能力：通用 TDD 实施内核

Quick Dev 应学习 6.3～6.6，而不是吸收 6.7～6.9 的 review/commit 权限。

### 6.1 Recommendation-only 路由

每次昂贵动作前输出：

~~~json
{
  "recommended_action": "run-red|fix-red-contract|implement|run-green|run-refactor|validate-slice|run-terminal|repair-vdd|stop",
  "forbidden_actions": [],
  "reason": "...",
  "blocked_by": [],
  "reusable_observations": [],
  "invalidated_observations": []
}
~~~

该输出必须：

- 只读。
- 不创建新 run。
- 不修改历史 evidence。
- 不授权完成。
- 能直接被跨会话恢复消费。
- 清楚区分需要修 VDD contract 与需要修生产实现。

### 6.2 显式 run state

至少区分：

- planned-only：只完成解析、descriptor 或路由，没有真实执行。
- observed-run：真实进程执行并产生有效 receipt/observation。
- recovered-run：从 hash 与语义均有效的 observation 恢复。
- invalid-run：artifact integrity、identity 或执行语义无效。

规则：

- planned-only 永远不能满足 RED、GREEN、REFACTOR 或 completion。
- timeout-no-observation 既不是 pass，也不是 expected failure。
- recovered-run 必须由显式路径、run ID 和 hash 引用，禁止扫描历史目录猜测。
- invalid-run 保留为历史，但不得成为 predecessor。

### 6.3 RED materializer

Quick Dev 在当前候选冻结后：

1. 读取 VDD failure intent。
2. 解析真实生产入口和 fixture。
3. 生成 shell=false descriptor。
4. 运行真实进程。
5. 从 exit code、stdout/stderr 或结构化 assertion 派生 observed failure。
6. 判断 expected RED、unexpected green、harness failure 或 repo noise。
7. 只有 expected RED 才允许进入 implementation。

同一 slice 的 GREEN 和 REFACTOR 必须重跑同一个 selector 语义。允许 descriptor 中的 stage 参数变化，但 target、fixture、assertion scope 和 Acceptance binding 不得悄然改变。

### 6.4 Failure taxonomy 与止损

至少支持：

- semantic-contract-gap
- expected-red
- unexpected-green
- task-implementation-failure
- test-harness-failure
- target-binding-failure
- repo-noise
- timeout-no-observation
- repeated-deterministic-failure
- artifact-integrity

必须执行：

- repo-noise 不得充当 RED。
- harness failure 不得进入 GREEN。
- unexpected green 必须转为 regression/current-behavior proof 或返回 VDD repair，不能直接宣称完成。
- 相同 deterministic fingerprint 连续出现时停止原参数重跑。
- 同一 failure family 应给出稳定 recommended action。
- 失败分类从真实 observation 派生，不能从 registry 的 expected 值复制。

### 6.5 选择性重放

变化影响矩阵至少覆盖：

| 变化 | 必须失效 |
| --- | --- |
| production/test/schema/validator | 受影响 oracle 的 RED/GREEN/REFACTOR 与 slice terminal |
| requirements/Acceptance/ref mapping | coverage 重算；受语义影响的 selector 重跑 |
| fixture/target/argv/cwd | 对应 slice 的全部 stage observation |
| command compiler/materializer | 所有由其生成的 descriptor 与后继 receipt |
| predecessor evidence | 直接依赖 slice 及其下游 |
| 普通非语义文档 | 默认不使已验证 observation 失效 |
| governance artifact（development） | 不影响 TDD 路由 |

每条 observation 应输出 reusable、invalidated_by、required_next_action。

### 6.6 轻量语义闭合检查

这是 Chapter 6 式基本语义校验，不是 6.7/6.8 的重型 review，也不要求多 agent。

slice-ready 前确定性检查：

- 当前 Acceptance 是否都有真实 executed observation。
- process execution count ≥ 1。
- exit semantics 与 expected outcome 双向匹配。
- actual argv/cwd/target/fixture 与 descriptor 一致。
- changed production paths 在 write set 内。
- assertion result 来自真实 case，而非 producer 自报。
- unexpected green 已分类。
- 没有 hard-uncovered。
- GREEN/REFACTOR 重跑相同 selector。
- coverage 只包含当前 dependency closure 已产生的 evidence。

terminal 前检查：

- 全部 active Acceptance exact cover。
- 每条 edge 重新读取 artifact ref 并验证 hash 与 assertion。
- 每个 predecessor 由显式 run-local reference 指定。
- 重试产生多个历史 run 时仍能唯一选择当前 lineage。
- 不扫描 glob、mtime 或“历史上唯一成功 run”。
- terminal input 不反向绑定尚未生成的未来结果。
- 成功路径与关键负例均真实执行。

### 6.7 Execution profiles

profile 只控制成本与范围，不能降低真实性：

- fast-ship：只运行受影响 oracle，P0/P1 阻断。
- standard：完整 slice terminal、负例与 mutation matrix。
- self-hosted：增加 predecessor/frozen judge 与完整反假绿套件。

所有 profile 都必须满足：

- 真实进程执行。
- 非零 case/execution 数。
- Acceptance exact cover。
- target/fixture/selector 绑定。
- 禁止自报 pass。
- RED → GREEN → REFACTOR 顺序。

### 6.8 时间目标

中等任务目标：

- 单次 VDD plan-ready 生成与确定性校验：分钟级。
- Quick Dev 单 slice 的 recommendation/preflight：秒级至低分钟级。
- 中等任务完整 TDD 与轻量语义闭合：目标 60 分钟内。
- 当失败主因是 semantic-contract-gap、hard-uncovered 或 repeated deterministic failure 时，应在第一次或第二次路由即停止无效重跑。

该目标用于产品与架构权衡，不应通过跳过真实执行实现。

## 7. 8-25 暴露的其他系统性问题

| 问题 | 8-25 表现 | 需要的通用修复 |
| --- | --- | --- |
| 上游语义压缩 | 17 个 FR、11 个 NFR 和多项 SM 被压成 7 个宽 Acceptance | obligation baseline 与 completeness gate |
| 主动排除 Chapter 5 | 计划 non-goals 明确排除 Chapter 5 processing | acceptance 不稳时强制进入轻量语义稳定化 |
| terminal 吞并语义 | A-TERMINAL 一项覆盖 FR-1..17、NFR-1..11 与全部 SM | 禁止 terminal 代替局部 Acceptance |
| 形式 exact cover | semantic-verification 宣称覆盖 7 个 ID，但 case_source_refs 只有 FR-1、FR-2、NFR-5 | coverage edge 必须逐条绑定真实 source/assertion |
| slice 过粗 | 仅 S1～S6，S6 同时承担 terminal 与 boundary | 使用行为、owner、lane、failure family 拆分 |
| RED 所有权混乱 | 早期曾把 selector/RED evidence 当成 VDD 产物 | VDD 只声明 failure intent；Quick Dev 物化并执行 |
| selector 不真实 | 早期 RED 没有调用生产入口或无法由合法生产修改转绿 | RED feasibility 与 production-entry guard |
| write set 不闭合 | S1/S5 所需 materializer/build_run_inputs 不在合法修改集 | plan-ready 前做 write-set feasibility |
| producer/consumer 合同冲突 | predecessor_judge_hash 一度写成 freeze 自身 hash，而 owner 要求 S3 receipt hash | typed field semantics 与 producer/consumer composition test |
| 阶段越权 coverage | S4 一度提前宣称 S5/S6 Acceptance | dependency-closure scoped coverage |
| status 自证 | receipt status 或 pass 可被预填，而非从执行派生 | result/status 全部由 observation validator 派生 |
| fixture 自证 | observed failure 一度可能直接复制 expected failure ID | 必须从进程输出/异常派生 observed value |
| exit 语义单向 | 只验证非零或只验证零，无法双向拒绝 | expected zero/nonzero 双向 judge |
| 历史扫描 | S6 依赖目录中“唯一成功 run”，重试后永久 ambiguous | 显式 run-local predecessor refs |
| 时间循环绑定 | 早期 manifest 试图绑定未来 implementation-complete result | lineage input 与最终 closure result 分离 |
| 兼容性回退错误 | repair compatibility 缺历史 contract hash，router 回退 S1 | typed preservation manifest 与受影响 slice 计算 |
| prior RED 续接脆弱 | 合同 repair 后需要复用真实历史 RED，但 handoff binding 不稳定 | append-only prior-RED successor protocol |
| 缺成功路径测试 | terminal 以 fail-closed 负例为主，成功生命周期不充分 | 每个 terminal producer 至少一条真实 happy path |
| 状态来源分裂 | 00-index、plan-state、95 report 曾呈现不同 lifecycle 叙述 | runtime state 从当前 evidence 派生；文档不做路由权威 |
| 治理压倒实施 | 每次合同 repair 都触发 review/binding/authorization 重绑 | development 默认关闭治理；已由 phase-aware mode 处理 |
| 过拟合单计划 | 大量 plan-local adapter 与特殊兼容逻辑围绕 8-25 生长 | detached fixtures + 新任务盲测，禁止只用 8-25 验收 |

## 8. 目标能力架构

### 8.1 VDD 子系统

1. Source Obligation Extractor
   - 读取原始需求。
   - 生成 obligation baseline。
2. Acceptance Compiler
   - 生成可观察 Acceptance。
   - 建立 source refs 与 coverage。
3. Slice Planner
   - 按行为、owner、lane、failure family 和依赖拆分/合并。
4. Failure Intent Compiler
   - 为 Acceptance 分配 RED intent，不生成执行 artifact。
5. Plan Feasibility Validator
   - 检查 write set、selector intent、dependency scope 和 terminal closure。

### 8.2 Quick Dev 子系统

1. Preflight And Recommendation Router
2. RED Descriptor Materializer
3. Lifecycle Executor
4. Observation Classifier
5. Selective Replay Planner
6. Slice Semantic Closure Validator
7. Whole-plan Terminal Aggregator

### 8.3 共享数据最小集

BMAD spec 应决定最终 schema，但至少需要表达四类数据：

- semantic plan：obligations、Acceptance、refs、lane。
- slice contract：依赖、write set、failure intent、stage/terminal scope。
- execution recommendation：next action、forbidden action、blocker、reuse。
- observation index：真实 run、selector identity、classification、reuse/invalidation。

优先少量 owner artifact；不要重建 8-25 的多文件 hash 网。

## 9. 建议实施阶段

### 阶段 A：VDD semantic completeness

- obligation extractor。
- Acceptance quality/preflight。
- source refs exact coverage。
- hard-uncovered fail-fast。
- detached fixtures。

### 阶段 B：VDD slice planner

- split/merge rules。
- verification lane。
- write-set feasibility。
- dependency closure 与 stage scope。
- RED failure intent 分配。

### 阶段 C：Quick Dev recommendation 与 run state

- recommendation-only。
- planned/observed/recovered/invalid。
- failure taxonomy。
- repeated fingerprint stop-loss。

### 阶段 D：真实 TDD lifecycle

- runtime RED descriptor。
- production-entry 与 greenability guard。
- same-selector GREEN/REFACTOR。
- observation-derived result。

### 阶段 E：选择性重放与语义闭合

- invalidation matrix。
- run-local predecessor。
- slice-ready semantic closure。
- terminal exact cover。
- happy path 与 mutation regressions。

### 阶段 F：独立验收与 dogfood

- detached fixtures。
- 8-25 regression replay。
- 一个全新的中等需求盲测。
- 时间与重跑次数测量。
- 现有 VDD/Quick Dev 仅作为 dogfood，不作为唯一验收者。

## 10. 最终产品 Acceptance

### 10.1 VDD

- 任意 active source obligation 都能追溯到至少一个 Acceptance。
- 任意 active Acceptance 都有 source ref、slice 和 RED failure intent。
- hard-uncovered 在 plan-ready 前失败。
- 多 owner、多 lane、独立 failure family 会触发 slice 拆分。
- 一个 slice 的 GREEN 可以在合法 write set 内完成。
- stage coverage 不引用未来 slice evidence。
- VDD 输出中不存在 RED receipt、run ID、exit code 或 observed status。
- unexpected-green policy 在计划中明确，不由 Quick Dev 临时猜测。

### 10.2 Quick Dev

- recommendation-only 不产生执行副作用。
- planned-only 不可满足任何完成 predicate。
- RED 调用真实生产入口且进程执行次数非零。
- observed failure 不从 expected registry 复制。
- GREEN/REFACTOR 重跑相同 selector。
- harness failure、repo noise、timeout-no-observation 不得进入 GREEN。
- 重复 deterministic failure 自动止损。
- requirement/fixture/target/validator 变化按矩阵选择性失效。
- 多个历史成功 run 不影响当前显式 lineage。
- slice-ready 和 terminal 由 artifact 内容及真实 assertion 决定，而非 status 字符串。
- terminal 具备一条真实成功路径和关键负例。

### 10.3 整体

- 8-25 回归通过，但实现中没有 plan ID 特判。
- 一个全新中等任务在不修改 VDD/Quick Dev 本身的情况下完成。
- 中等任务目标在 60 分钟内闭合。
- development 状态不产生治理阻塞。
- test/production 可重新启用治理，但治理开关不改变 TDD 真实性。

## 11. BMAD 产物要求

### 11.1 bmad-prd

必须明确：

- 用户是 AI 主导、单人维护。
- 核心用户价值是更少返工、更完整需求覆盖和一小时级中等任务闭合。
- 三条主能力：细粒度 slice、Acceptance/ref/RED 完整映射、Chapter 6 式执行与轻量语义校验。
- 治理能力不是开发态目标。
- 成功指标、时间预算、失败止损和兼容目标。

### 11.2 bmad-spec

必须定义：

- obligation/Acceptance/slice/failure-intent 数据模型。
- split/merge 算法。
- exact coverage 算法。
- write-set feasibility。
- recommendation-only schema。
- run-state 与 failure taxonomy。
- invalidation/reuse matrix。
- slice-ready/terminal semantic predicates。
- detached fixture 与 mutation matrix。
- v1 到新合同的兼容和迁移策略。

### 11.3 bmad-architect

必须决定：

- VDD 与 Quick Dev 的模块所有权。
- 哪些能力属于共享库，哪些属于 skill-local adapter。
- 如何避免 plan-local 特判进入共享 router。
- 如何从 implicit directory scan 迁移到 explicit lineage。
- 如何保持 Windows/pytest/py -3 兼容。
- 如何让轻量语义校验保持 deterministic；如使用模型，只能作为非阻断提示，不能成为默认 completion authority。
- 如何分阶段上线并保持旧计划只读兼容。

## 12. 明确非目标

- 不重写 8-25 历史 evidence。
- 不重新启用开发态 external review、authorization 或签名治理。
- 不把 Chapter 6 的 6.7、6.8、6.9 收进 Quick Dev。
- 不照搬 Taskmaster、Godot、GdUnit、overlay 的业务仓细节。
- 不以增加 hash、schema、receipt 数量作为成功指标。
- 不要求一次大提交完成全部改造。
- 不让现有 VDD/Quick Dev 独立规划、实施并验收自己的全部改造。

## 13. 对 BMAD 的待决问题

BMAD 需要在产物中明确选择，而不是留给实施阶段猜测：

1. obligation 与 Acceptance 的规范化边界。
2. slice split/merge 的确定性规则和阈值。
3. 一条 selector 覆盖多 Acceptance 时 assertion edge 的表达。
4. lightweight semantic validator 的纯确定性范围。
5. v1 计划进入新执行器时的 compatibility adapter 边界。
6. unexpected green 转 regression 的最低证明。
7. 60 分钟目标的任务规模定义与测量方法。
8. fast-ship、standard、self-hosted 的具体执行差异。
9. 哪些变化只需 coverage recompute，哪些必须重跑 RED。
10. detached fixtures 的作者与被测 skill 的独立性保证。

## 14. 推荐决策

本改造采用“外部设计与实现、内部 dogfood”的路径：

1. 以本文为输入运行 `bmad-prd`、`bmad-spec`、`bmad-architect`。
2. 将三类产物提交 GitHub。
3. 由当前 VDD/Quick Dev 之外的实现者审查并实施。
4. 现有 VDD/Quick Dev 只参与 shadow/dogfood。
5. 最终以 detached fixtures、8-25 regression 和全新中等任务盲测共同验收。


## 15. 可直接实现的 VDD 编译协议

本节把第 4、5 章的原则落实为可编码流程。后续 BMAD 可以调整模块名和文件名，但不得删除阶段、输入输出、失败分类或确定性硬门。

### 15.1 模型与确定性程序的职责

| 动作 | 默认执行者 | 是否调用 `codex exec` | 是否有权判定通过 |
| --- | --- | --- | --- |
| source 文件索引、锚点解析、hash | Python 确定性程序 | 否 | 是 |
| requirement → obligation 语义拆解 | 只读 semantic worker | 是 | 否 |
| obligation 结构与 source 支持检查 | Python validator | 否 | 是 |
| obligation → Acceptance 候选 | 只读 semantic worker | 是 | 否 |
| Acceptance/ref 语义对齐复核 | 独立只读 semantic worker | 是 | 否 |
| coverage graph 与 exact-cover | Python validator | 否 | 是 |
| slice 分组候选 | 确定性 partitioner；歧义时由 semantic worker 建议 | 条件调用 | 否 |
| write-set/RED 可实施性检查 | Python validator | 否 | 是 |
| plan-ready 决策 | VDD coordinator | 否 | 是，只能依据前述 gate |

核心规则：

- `codex exec` 负责语义提取、对齐与 repair 建议，不直接写 `pass`、`plan-ready` 或 observed evidence。
- 所有模型调用都必须 read-only、`shell=False`、结构化输出、有限输入范围。
- 所有 source identity、ref 解析、集合覆盖、图闭包、路径边界和最终状态均由确定性程序判断。
- 模型超时、schema error 或空输出不得被解释成“未发现问题”。

### 15.2 建议的顶层入口

建议新增一个稳定入口，命令名可由 BMAD architect 最终确认：

~~~powershell
py -3 scripts/vdd/compile_plan.py --requirements <requirements-file> --out-dir <plan-dir> --profile standard
~~~

内部固定阶段：

~~~text
source-index
→ obligation-extract
→ obligation-guard
→ acceptance-compile
→ semantic-align
→ coverage
→ slice-partition
→ feasibility
→ plan-ready
~~~

推荐诊断入口：

~~~powershell
py -3 scripts/vdd/compile_plan.py --requirements <requirements-file> --out-dir <plan-dir> --recommendation-only
py -3 scripts/vdd/compile_plan.py --requirements <requirements-file> --out-dir <plan-dir> --resume-from first-failed-stage
~~~

`--recommendation-only` 不调用模型、不写 plan，只读取已有状态并返回下一步。

### 15.3 Stage V0：source index

输入：

- canonical requirements 文件。
- 明确列出的补充 spec/architecture 来源。
- 允许解析的 ref 语法。

确定性程序输出 `source-index.v1.json`：

~~~json
{
  "sources": [
    {
      "requirement_id": "FR-13",
      "source_ref": "docs/know76.txt#FR-13",
      "source_path": "docs/know76.txt",
      "anchor": "FR-13",
      "source_sha256": "sha256:...",
      "source_text_sha256": "sha256:...",
      "source_text": "...",
      "source_order": 13
    }
  ]
}
~~~

硬门：

- source path 必须位于仓库内。
- anchor 必须唯一解析。
- `source_text` 必须非空。
- ID 不得重复。
- 不允许以后续生成的 Acceptance、plan 或 report 充当原始 source。
- 输入文件变化后必须重新生成 index，旧 semantic result 不得静默复用。

### 15.4 Stage V1：使用 `codex exec` 拆解 obligation

是，需要调用 `codex exec`。但不让调用者自由修改仓库，必须经过统一 wrapper。

建议接口：

~~~powershell
py -3 scripts/vdd/run_semantic_worker.py --stage obligation-extract --input <source-index-item.json> --schema schemas/vdd-obligation-extract.v1.schema.json --output <result.json>
~~~

wrapper 的规范行为：

1. 通过参数数组启动 `codex exec`，`shell=False`。
2. 工作区设为仓库根，但 sandbox/read policy 为只读。
3. prompt 通过 stdin 或临时只读文件提供。
4. 强制 JSON Schema 输出。
5. 一次只处理一个 Requirement，或一个受 token 上限控制的同源小批次。
6. 保存模型版本、prompt version、输入 hash、耗时和退出状态。
7. 不向 worker 提供旧的 `pass`、plan-state 或治理 receipt。

输出至少包含：

~~~json
{
  "requirement_id": "FR-13",
  "obligations": [
    {
      "obligation_id": "FR-13.O1",
      "source_ref": "docs/know76.txt#FR-13",
      "source_span": "repo-noise ... RED",
      "subject": "Quick Dev RED classifier",
      "trigger": "RED command contains an unrelated repository failure",
      "state_before": "red candidate observed",
      "expected_behavior": "classify the result as repo-noise",
      "state_after": "RED rejected",
      "observable_result": "recommended_action is not implement",
      "forbidden_result": "repo-noise is accepted as expected RED",
      "requirement_type": "Platform"
    }
  ],
  "unresolved_fragments": []
}
~~~

拆解规则必须写入 prompt 和 schema：

- 不同 subject 拆开。
- 不同 trigger 拆开。
- 不同状态变化拆开。
- 不同 failure condition 拆开。
- 可以独立观察或独立失败的行为拆开。
- `must`、`must not`、`only`、`at least` 等强制语义不得被摘要丢失。
- 不得把多个行为只保留成一个 Requirement 级 `partially-present`。

### 15.5 Stage V2：obligation 确定性 guard

`obligation-guard` 至少执行：

- 所有 `source_ref` 可解析，且属于当前 source index。
- `source_span` 能在 source text 中定位或通过规范化匹配。
- subject、trigger、expected behavior、observable、forbidden 均非空。
- 同一 Requirement 的 obligation ID 稳定且无重复。
- 两条 obligation 的行为五元组完全相同时拒绝重复项。
- 每个 Requirement 至少一个 obligation。
- 所有强制句片段至少被一个 obligation 声明覆盖。
- 模型新增 source 中不存在的主体、数值、权限或时序时标记 `unsupported_semantics`。
- `unresolved_fragments` 非空时不得进入 acceptance compile。

建议输出：

~~~json
{
  "status": "pass|blocked",
  "failure_family": "none|hard_uncovered|unsupported_semantics|schema_error|ambiguous_source",
  "uncovered_fragments": [],
  "unsupported_obligation_ids": [],
  "recommended_action": "acceptance-compile|repair-obligations|request-clarification"
}
~~~

如果发生 schema error，只允许把 validator error 回传给同一 worker 修复一次。若相同 fingerprint 连续两次出现，停止重跑。

### 15.6 Stage V3：Acceptance 编译

第二类 `codex exec` 调用只从已通过 guard 的 obligations 生成 Acceptance，不重新解释全部仓库。

Acceptance 输出：

~~~json
{
  "acceptance_id": "A-RED-REPO-NOISE",
  "obligation_ids": ["FR-13.O1"],
  "source_refs": ["docs/know76.txt#FR-13"],
  "given": "a task-scoped RED command is executed",
  "when": "the command fails only because of unrelated repository noise",
  "then": "the result is classified as repo-noise and cannot authorize implementation",
  "oracle": {
    "observable": "router result",
    "expected": "classification=repo-noise",
    "forbidden": "classification=expected-red"
  }
}
~~~

允许将多个 obligations 合入一条 Acceptance，仅当以下条件全部满足：

- subject 和生命周期阶段相同。
- 使用同一 observable oracle。
- 由同一生产 owner 负责。
- 同一个测试场景能分别产生每条 obligation 的 assertion。
- 任一 obligation 失败时，测试能指出具体 assertion ID。

否则必须拆成多条 Acceptance。

### 15.7 Stage V4：独立 semantic align

需要第二个独立、只读的 `codex exec` worker。它不能读取第一轮模型的解释过程，只读取 frozen source、obligations、Acceptance 和 RED intents 候选。

输出：

~~~json
{
  "acceptance_id": "A-RED-REPO-NOISE",
  "decision": "valid|partial|unsupported|overbroad|untestable",
  "covered_obligation_ids": ["FR-13.O1"],
  "missing_semantics": [],
  "invented_semantics": [],
  "oracle_alignment": "valid|invalid",
  "recommended_repairs": []
}
~~~

路由：

- `valid`：进入 coverage。
- `partial`：补 Acceptance 或拆分。
- `unsupported`：删除发明语义，或请求用户补 source。
- `overbroad`：按独立 oracle/state transition 拆分。
- `untestable` 或 `oracle_alignment=invalid`：重写 Acceptance/RED intent。
- worker 的 `valid` 不是最终 pass；确定性 coverage gate 仍必须通过。

### 15.8 Stage V5：真实 exact-cover

构建双向图：

~~~text
source requirement
↔ obligation
↔ Acceptance
↔ source ref
↔ RED failure intent
↔ slice
↔ terminal aggregation
~~~

确定性 gate 必须同时验证：

- 每个 active Requirement 至少一个 obligation。
- 每个 active obligation 至少一个 Acceptance。
- 每个 Acceptance 至少一个 obligation 和一个可解析 source ref。
- 每个 Acceptance 至少一个 RED failure intent。
- 每个 RED intent 最终属于一个 slice。
- 每个 slice 至少实施一个 Acceptance。
- 每个 terminal edge 都能回溯到真实局部 assertion，不允许 terminal ID 吞并缺失语义。
- source → Acceptance 与 Acceptance → source 两个方向都通过。
- `hard_uncovered = 0`、`orphan_acceptance = 0`、`orphan_slice = 0`。

这里的 exact-cover 是“完整且无无源边”，不要求一对一或 exclusive partition。

### 15.9 Stage V6：确定性 slice partition

先创建 Acceptance compatibility graph。每个节点至少包含：

~~~json
{
  "acceptance_id": "A-...",
  "production_owners": ["path/or/module"],
  "verification_lane": "unit|integration|matrix|runtime",
  "lifecycle_stage": "red-green-refactor",
  "failure_family": "repo-noise",
  "state_transition": "red-candidate→red-rejected",
  "required_write_paths": [],
  "selector_intents": [],
  "depends_on": []
}
~~~

最终 slice contract 还必须直接回答五个问题，不能只列 ID：

~~~json
{
  "behavior_change": "改变什么可观察行为",
  "affected_subjects": ["谁受到影响"],
  "state_transition": "什么状态如何变化",
  "proof": {
    "acceptance_ids": [],
    "selector_intents": [],
    "assertion_ids": []
  },
  "rollback_scope": {
    "production_paths": [],
    "state_or_schema_compatibility": "..."
  }
}
~~~

先应用硬拆分边界。任一条件成立即禁止放入同一 slice：

- 不同生命周期阶段或后一行为依赖前一行为的真实 observation。
- 不同 verification lane 且无法由同一个上位 lane 低成本覆盖。
- 不同 production owner，且不存在明确的 producer/consumer 原子修改。
- 不同 state transition 或互相独立的 failure mechanism。
- 需要不相容的 fixture、runtime 或 selector。
- 合并后无法在同一个合法 write set 内 GREEN。
- 合并会使当前阶段引用未来 evidence。
- 任一 Acceptance 无法获得独立 assertion ID。

随后才允许合并。合并条件全部满足：

- 共享业务行为和生产 owner。
- 同一 RED selector 能产生所有 assertion。
- 一次最小 production successor 能共同转绿。
- 合并不隐藏独立 failure。
- 合并后每条 Acceptance 仍有独立 observation edge。

建议 partitioner 使用确定性顺序：

1. 按依赖图拓扑排序。
2. 按 production owner 和 verification lane 建 bucket。
3. 在 bucket 内按 state transition/failure mechanism 形成候选组。
4. 对候选组运行 write-set 与 selector feasibility。
5. feasibility 失败时按冲突边拆分，不让模型强行合并。
6. 仅当两个分组方式都合法但取舍不明确时，调用只读 `codex exec` 给出 recommendation。
7. 使用稳定 ID 和输入 hash 保证同输入产生同分组。

slice 不设置绝对 Acceptance 数量上限；但如果一个 slice 同时包含多于一个 owner、两个 verification lane、两个独立 failure family，或者不能在一个 selector family 内观测，必须触发 `overbroad_slice` 复核。

### 15.10 Stage V7：RED 与 write-set feasibility

每个 slice 在 plan-ready 前模拟以下闭包：

~~~text
Acceptance
→ failure intent
→ selector target
→ real production entry
→ allowed test paths
→ allowed production paths
→ plausible GREEN owner
→ same-selector REFACTOR
~~~

确定性判定：

- failure intent 明确 expected observation 和 forbidden observation。
- target、fixture 或 case source 能定位；planned new test 有合法路径。
- selector intent 必须指向真实生产入口，不得只测试 plan artifact 自己。
- 测试写集允许 Quick Dev 创建或修改所需 RED。
- 生产写集包含负责该行为的 owner；若无，则 `slice_write_set_not_closed`。
- GREEN 不依赖后续 slice 才能修改的文件。
- RED 不要求回滚当前正确行为。
- RED 有可能由合法生产修改转绿，而非固定失败。
- GREEN/REFACTOR 可以保持同一 selector semantic identity。

无法证明时输出 VDD repair，不允许把固定失败交给 Quick Dev：

~~~json
{
  "status": "blocked",
  "failure_family": "slice_write_set_not_closed|selector_unbound|red_not_greenable|future_evidence_dependency",
  "slice_id": "S5",
  "recommended_action": "repair-vdd",
  "required_contract_changes": []
}
~~~

### 15.11 VDD 恢复与止损

| 失败 | 下一动作 |
| --- | --- |
| schema error | 带 validator errors 修复一次 |
| hard-uncovered | 修 obligations/Acceptance，不增加 timeout |
| unsupported semantics | 删除发明语义或请求用户补 source |
| semantic worker timeout | 在无结构问题时缩小单次输入，再重试一次 |
| 相同 deterministic fingerprint 两次 | 停止，输出 repair recommendation |
| 两个 semantic worker 持续冲突 | 标记 `semantic_ambiguous`，交给 BMAD/用户决策 |
| write set 不闭合 | 返回 VDD contract repair |
| selector 不可绑定生产入口 | 修 RED intent 或 slice，不进入 Quick Dev |

## 16. 可直接实现的 Quick Dev TDD Chapter 6 协议

本节对应 Chapter 6 的 6.3～6.6，以及恢复、recommendation 和止损。6.7 LLM Review、6.8 多 reviewer、6.9 commit authority 仍属于外层。

### 16.1 Quick Dev 顶层入口

建议稳定入口：

~~~powershell
py -3 scripts/quick_dev/run.py --plan <plan-dir> --slice <slice-id> --profile standard
py -3 scripts/quick_dev/run.py --plan <plan-dir> --slice <slice-id> --recommendation-only
~~~

内部状态机：

~~~text
planned-only
→ preflight-passed
→ red-materialized
→ red-observed
→ implementation-successor
→ green-observed
→ refactor-observed
→ slice-ready
→ whole-plan-terminal
~~~

禁止跳转：

- `planned-only → implementation-successor`
- `red-materialized → implementation-successor`
- `red-observed(expected-red 以外) → implementation-successor`
- `green-observed(fail) → refactor`
- `slice-ready 缺局部 assertion → terminal`

每个 transition 由独立 predicate 判断，producer 不得自己写 `status=pass` 后绕过 predicate。

### 16.2 `codex exec` 在 Quick Dev 中的具体用途

| 阶段 | 是否调用 `codex exec` | 权限 |
| --- | --- | --- |
| recommendation/preflight | 否 | 纯确定性只读 |
| RED test 已存在 | 否 | 直接 materialize/执行 |
| RED test 缺失 | 是，`red-author` worker | 只允许 test write set；禁止 production 修改 |
| production implementation | 是，`implementation` worker | 只允许 slice production write set |
| GREEN/REFACTOR 命令执行 | 否 | Python subprocess，真实进程 |
| refactor 代码修改 | 是，`refactor` worker | 只允许已授权 production paths，不得改变 selector 语义 |
| failure classification | 先确定性；未知时可调用模型建议 | 模型不得把 unknown 改成 pass |
| slice-ready/terminal | 否 | 确定性 gate |

所有 `codex exec` 写入阶段都必须：

- 使用当前 slice 的 agent-context projection。
- 明确 allowed/forbidden paths。
- 在调用前记录 worktree baseline。
- 调用后计算 changed paths 并强制验证。
- 不读取 governance receipt 作为实现依据。
- 不修改历史 run。
- 返回 patch/changes summary，但是否接受由确定性 gate 决定。

Quick Dev 不应重新阅读整个需求目录猜测上下文。VDD 应为每个 slice 派生只含必要字段的 `agent-context.json`：

~~~json
{
  "slice_id": "S...",
  "requirement_ids": [],
  "obligation_ids": [],
  "acceptance_ids": [],
  "source_refs": [],
  "contracts": [],
  "allowed_paths": [],
  "forbidden_paths": [],
  "selector_intents": [],
  "validation_commands": []
}
~~~

该文件是从 canonical semantic plan 和 slice contract 确定性投影得到的入口，不是新的手工治理文档。

### 16.3 Stage Q0：recommendation-only

输入：

- 当前 plan/slice contract。
- candidate identity。
- 已有显式 run refs。
- worktree changed paths。
- observation index。

输出：

~~~json
{
  "recommended_action": "run-preflight|author-red|run-red|implement|run-green|run-refactor|validate-slice|run-terminal|repair-vdd|stop",
  "forbidden_actions": [],
  "reason_code": "...",
  "blocked_by": [],
  "reusable_observations": [],
  "invalidated_observations": []
}
~~~

硬要求：

- 不启动 `codex exec`。
- 不运行测试。
- 不创建 run ID。
- 不修改状态或证据。
- recommendation 必须来自当前显式 lineage，禁止 glob/mtime/“唯一历史成功 run”推断。

### 16.4 Stage Q1：6.3 式 preflight

确定性检查：

- slice contract、Acceptance、refs 和 failure intents 完整。
- complexity class 与 verification lane 已声明。
- context lookup 条件已解析；需要时只补充实现上下文，不改 requirement。
- planned selector target/fixture/cwd 可解析。
- `argv` 是非空字符串数组，`shell=False`，timeout 大于零。
- cwd 是仓库内安全相对路径。
- RED test write set 和 production GREEN write set 均闭合。
- predecessor 使用显式 ref、run ID 和 hash。
- candidate/plan/slice identity 一致。
- 本地运行时存在，例如 Windows 下 `py -3` 与 pytest probe 成功。
- 当前变化没有使计划语义失效。

路由：

- Acceptance/ref/RED intent 缺失 → `repair-vdd`。
- selector/test 尚未创建但合同合法 → `author-red`。
- selector 已存在且 identity 有效 → `run-red`。
- runtime 缺失 → `environment-blocked`，不伪造 RED。
- write set 不闭合 → `repair-vdd`。

### 16.5 Stage Q2：RED author 与 descriptor materialization

如果测试不存在，`red-author` worker 输入：

- Acceptance 与 source refs。
- failure intent。
- real production entry。
- allowed test paths。
- forbidden production paths。
- verification lane。
- expected assertion/failure ID。

输出只能是测试修改。调用后确定性检查：

- production paths 无变化。
- 测试实际 import/call 真实生产入口。
- selector 能收集至少一个 case。
- assertion 对应 Acceptance forbidden result。
- 没有通过改写现有正确生产行为制造 RED。
- 没有硬编码“总是失败”或读取 plan status 自证。
- target、fixture、case source 均可定位。

随后生成 descriptor：

~~~json
{
  "run_id": "RUN-...",
  "slice_id": "S...",
  "stage": "red",
  "candidate_hash": "sha256:...",
  "argv": ["py", "-3", "-m", "pytest", "tests/path/test_file.py::test_case", "-q"],
  "cwd": ".",
  "shell": false,
  "timeout_seconds": 120,
  "target_refs": [],
  "fixture_refs": [],
  "acceptance_assertions": [
    {
      "acceptance_id": "A-...",
      "assertion_id": "ASSERT-...",
      "expected_exit": "nonzero",
      "expected_failure_family": "..."
    }
  ]
}
~~~

descriptor 只描述将要运行什么，仍是 `planned-only`，不能证明 RED。

### 16.6 Stage Q3：真实 RED 执行与分类

executor 必须等价于：

~~~python
subprocess.run(
    descriptor["argv"],
    cwd=resolved_cwd,
    shell=False,
    timeout=descriptor["timeout_seconds"],
    capture_output=True,
    text=True,
)
~~~

receipt 至少保存：

- actual argv/cwd。
- started/finished time。
- exit code。
- executions/cases collected。
- stdout/stderr hash 和必要的结构化摘要。
- candidate、descriptor、target、fixture hash。
- observed assertion/failure ID。
- executor identity。

RED predicate：

1. `executions >= 1`。
2. target/fixture/argv 与 descriptor 完全匹配。
3. 失败来自被声明的 assertion 或 production behavior。
4. 不是 collection/import/config/environment failure。
5. 不是 repo-noise。
6. exit 与 expected RED 双向匹配。
7. observed failure 从进程输出/异常解析，不从 registry expected 值复制。

分类：

| observation | classification | 路由 |
| --- | --- | --- |
| 声明 assertion 失败、非零退出 | `expected-red` | `implement` |
| selector 全绿 | `unexpected-green` | regression/current-behavior proof 或 VDD repair |
| 未收集 case | `target-binding-failure` | 修 selector |
| import/fixture/runner 失败 | `test-harness-failure` | 修 harness，不进入 GREEN |
| 无关仓库测试失败 | `repo-noise` | 隔离 selector |
| timeout 且无有效 observation | `timeout-no-observation` | 缩小范围/修环境 |
| descriptor/identity/hash 不符 | `artifact-integrity` | invalid-run |
| 相同失败 fingerprint 达阈值 | `repeated-deterministic-failure` | stop |

### 16.7 Stage Q4：production implementation

只有 clean `expected-red` observation 才能调用 `implementation` worker。

提供的最小上下文：

~~~json
{
  "slice_id": "S...",
  "acceptance_ids": [],
  "source_refs": [],
  "allowed_production_paths": [],
  "forbidden_paths": [],
  "red_descriptor_ref": "...",
  "red_observation_ref": "...",
  "red_failure_summary": "...",
  "required_selector_identity": "sha256:..."
}
~~~

调用后的确定性检查：

- changed paths 全部位于合法 production write set。
- selector、fixture、Acceptance、plan 文件没有被悄然改写。
- 如果确实必须修改测试合同，当前 RED 立即失效并返回 Q2/Q3，不能继续沿用旧 RED。
- 不允许 producer 直接写 GREEN receipt 或 `status=pass`。
- production change 与 red failure mechanism 有关联；无关大范围改写触发 stop/review recommendation。

### 16.8 Stage Q5：GREEN

生成 GREEN descriptor 时复用 RED 的 semantic selector identity：

- target refs 相同。
- fixture refs 相同。
- Acceptance/assertion 集合相同。
- cwd 与安全策略相同。
- 允许 stage/run/candidate successor identity 变化。
- 不允许通过缩小 case 集、删除断言或切换假入口转绿。

GREEN predicate：

~~~text
executions >= 1
AND actual selector identity == RED selector identity
AND expected_exit == zero
AND exit_code == 0
AND all bound assertions == true
AND no harness/repo-noise/timeout classification
~~~

失败时保持当前实现 successor，按 failure family 给出下一动作；不得为了得到绿色 status 生成替代 receipt。

### 16.9 Stage Q6：REFACTOR

前置硬门：

- 当前 lineage 中最近的 GREEN 为真实 observed-run。
- GREEN candidate 是当前 refactor predecessor。
- selector identity 未变化。

如需代码整理，`refactor` worker 只能修改合法 production paths。随后执行：

1. 与 RED/GREEN 相同的 slice selector。
2. profile 要求的受影响 regression selectors。
3. 必要的静态/schema validator。

REFACTOR predicate 要求 slice selector 继续满足 GREEN，且 regression 不出现新增失败。失败则返回 implementation/refactor 修复，不允许进入 slice-ready。

### 16.10 Stage Q7：slice-ready 轻量语义闭合

这是确定性语义检查，不是 LLM review。

对 slice 中每个 Acceptance 验证：

- 至少一条真实 executed assertion edge。
- edge 指向 RED、GREEN、REFACTOR 对应 observation。
- artifact ref、hash、run ID、candidate、selector identity 可重新读取并匹配。
- RED 证明错误行为，GREEN/REFACTOR 证明期望行为。
- result/status 由 predicate 派生。
- coverage scope 只包含当前 dependency closure。
- predecessor evidence 语义有效，不只检查 `status=pass`。
- 没有 hard-uncovered 或未来 evidence。

输出 `slice-ready-result` 只能由 validator 写入。

可选的 semantic model 只能生成非阻断 warning；不能把确定性 fail 改为 pass。

### 16.11 Stage Q8：whole-plan terminal

terminal 输入必须显式列出当前 lineage：

~~~json
{
  "candidate_hash": "sha256:...",
  "plan_hash": "sha256:...",
  "predecessors": [
    {
      "slice_id": "S1",
      "run_id": "RUN-...",
      "result_ref": ".../slice-ready-result.json",
      "result_sha256": "sha256:..."
    }
  ],
  "terminal_selector_ref": "...",
  "active_acceptance_ids": []
}
~~~

terminal aggregator：

1. 逐个读取显式 predecessor。
2. 验证 path、run ID、candidate lineage 和 hash。
3. 重算 whole-plan Acceptance exact-cover。
4. 重读每条 assertion artifact，不接受仅存在的 edge 字符串。
5. 运行 terminal selector 和 profile 要求的 regression/mutation。
6. 验证全部 active Acceptance。
7. 最后才生成 implementation-complete result。

禁止：

- glob 扫描历史 run。
- 用 mtime 选最新结果。
- 要求历史目录只有一个成功 run。
- 在早期 manifest 中绑定尚未生成的 completion result。
- 由 terminal producer 自报完成。

### 16.12 恢复、失效与选择性重放

每次 route 先计算输入变化：

| 变化 | 动作 |
| --- | --- |
| requirement/obligation/Acceptance/ref | 重算 coverage；重跑语义受影响 slice |
| selector/fixture/target/case source | 对应 RED/GREEN/REFACTOR 全失效 |
| production owner code | 重跑受影响 GREEN/REFACTOR；若 failure intent 语义变化则从 RED 开始 |
| descriptor compiler/materializer | 其生成的 descriptor 与后继 observations 失效 |
| validator/judge | 受其判断的结果重验，必要时重跑 |
| predecessor result | 直接下游失效 |
| 普通非语义文档 | observation 可复用 |
| development governance artifact | 不影响 TDD 路由 |

recovered-run 仅可从显式 ref 恢复。验证失败则标记 invalid-run，保留历史但禁止成为 predecessor。

### 16.13 统一止损

- 同一 deterministic failure fingerprint 连续两次：停止原参数重跑。
- timeout 只有在无 hard-uncovered/schema/harness 问题时才允许增加预算。
- unexpected green 不反复制造假 RED；转 current-behavior/regression proof 或 VDD repair。
- selector 无 case 不进入实现。
- failure family 已明确指向 VDD 时，不调用 implementation worker。
- changed paths 越界时停止，只撤销或隔离本次 worker 产生的 patch；必须保留调用前已经存在的用户修改，不得继续扩大授权路径。
- 任何模型 worker 失败都不能用手写 status 补齐生命周期。

## 17. BMAD 扩充后的实施输入要求

只有把本草案转换为以下可测试产物，才具备进入实现的条件。

### 17.1 bmad-prd 必须固定

- “90% 能力接近”的分母和排除项。
- AI 主导、单人维护、development 默认无治理阻塞。
- 中等任务 60 分钟目标。
- requirement recall、Acceptance exact-cover、false-green、错误路由和无效重跑指标。
- VDD 与 Quick Dev 的职责边界。
- 兼容旧 execution plan 的最低要求。

### 17.2 bmad-spec 必须给出

- 本文所有 machine-readable schema。
- `source-index → extract → guard → compile → align → coverage → partition → feasibility` 的状态机。
- slice hard-split/merge 算法及稳定 ID 算法。
- semantic worker prompt contract、context limit、timeout、schema repair 与 conflict protocol。
- Quick Dev Q0～Q8 transition predicates。
- selector semantic identity 算法。
- failure fingerprint 与分类优先级。
- observation reuse/invalidation 算法。
- exact-cover 与 terminal predicate 的伪代码。
- Windows + `py -3` + pytest 的命令执行合同。
- detached fixtures 与 mutation matrix。

### 17.3 bmad-architect 必须给出

- VDD coordinator、semantic worker wrapper、deterministic validators、partitioner 的模块边界。
- Quick Dev router、descriptor materializer、executor、classifier、closure validator、terminal aggregator 的模块边界。
- 共享 schema/identity/invalidation 库的 owner。
- 所有 `codex exec` 调用的 sandbox、allowed paths、输入投影和输出验证。
- append-only run store 与显式 lineage。
- 旧 v1 plan compatibility adapter，禁止把 8-25 特判写入通用 router。
- 分阶段迁移、shadow mode、回滚和遥测方案。

## 18. “达到 Chapter 4/5/6 约 90% 能力”的判定

### 18.1 必须先定义比较范围

如果比较 Chapter 4/5/6 的全部仓库专用能力，包括 Taskmaster overlay、Godot/GdUnit、批量 jitter/shard/quarantine、6.7 LLM Review、6.8 多 reviewer 和 6.9 commit authority，则 VDD + Quick Dev 不应追求 90%，因为这些能力被有意留在外层或属于其他业务仓。

本项目的合理分母是“可泛化且属于 VDD/Quick Dev 职责的能力”：

- Chapter 4：source/refs/contracts baseline、dry-run、拆解、limited apply、freeze 和 feasibility。
- Chapter 5：preflight、extract、align、coverage、semantic gate、repair/recovery 和止损。
- Chapter 6：6.3～6.6 TDD、recommendation、planned/observed、failure classification、selective replay 和恢复。

对这个分母，90% 是合理目标。

### 18.2 能力权重与目标

| 能力组 | 权重 | 实施后目标 | 允许保留的差距 |
| --- | ---: | ---: | --- |
| Chapter 4 泛化基线与 slice feasibility | 25 | 22 | 不复制 overlay/Taskmaster 专用 apply |
| Chapter 5 obligation/Acceptance/ref 稳定化 | 35 | 32 | 不复制长批次 jitter/quarantine 全套 |
| Chapter 6 Quick Dev 执行内核 | 40 | 37 | 不包含 6.7～6.9 |
| 合计 | 100 | 91 | 仅限明确排除项 |

因此：

- 只有本草案：约 50%，因为已有规则但没有实现。
- 完成 BMAD PRD/spec/architect：约 65%～70%，因为协议完整但还没有运行证据。
- 完成代码与内部单元测试：约 80%～85%。
- 再通过 detached fixtures、8-25 回归和全新中等任务盲测：目标 90%～92%。

不能因为文档、schema 或单元测试存在就宣称 90%。

### 18.3 90% 的强制通过证据

#### VDD 语义完整性

- curated requirements fixture 中所有已知 obligations 的 recall ≥ 95%。
- unsupported/invented obligation precision ≥ 95%。
- active obligation → Acceptance → ref → RED intent → slice coverage 为 100%。
- `hard_uncovered = 0`。
- overbroad Acceptance、terminal swallowing 和 source-ref 漂移 mutation 全部被阻断。
- 同输入重复运行产生稳定 ID 和等价 partition。

#### Slice 质量

- owner/lane/state transition 不兼容时 100% 拆分。
- 可共享 selector/owner/write set 的 Acceptance 能合并，不退化成一条 Acceptance 一个 slice。
- 所有生成 slice 均通过 write-set closure。
- 固定失败、无法调用生产入口、依赖未来 evidence 的 RED intent 全部被 plan-ready 阻断。

#### Quick Dev 真实性

- 所有 RED/GREEN/REFACTOR observations 都有 `executions >= 1`。
- planned-only、timeout、repo-noise、harness failure、zero-case 都不能成为 pass。
- unexpected green 被稳定路由到 regression proof 或 VDD repair。
- GREEN/REFACTOR selector identity 与 RED 相同。
- observed failure 不从 expected registry 复制。
- status 全部由 validator 派生。
- 多个历史成功 run 不造成当前 lineage 歧义。
- selector/fixture/target 改变会使对应生命周期全部失效。
- terminal happy path 和关键 mutation 真实执行。

#### 综合盲测

至少三组：

1. detached synthetic fixtures：覆盖所有 failure family 和结构 mutation。
2. 8-25 replay：不得出现 plan ID 特判，能够更早发现当时的语义压缩、write-set、future coverage 和 lineage 问题。
3. 一个从未用于设计 skill 的中等新任务：无需修改 VDD/Quick Dev 自身，在目标 60 分钟内完成并通过轻量语义闭合。

### 18.4 最终判断规则

由外部实现者完成 BMAD 后，再由本助手实施代码，可以把“属于 VDD/Quick Dev 的 Chapter 4/5/6 可泛化能力”做到约 90%；前提是：

- BMAD 产物保留本节的算法、schema、状态机和强制证据，不把它们重新降级成方向描述。
- 实现不围绕 8-25 写特判。
- 90% 由独立 fixtures 和盲测计算，而不是开发者自评。
- 任何 false-green、hard-uncovered 被放行、planned-only 被计为 observed，均直接取消 90% 结论。

如果只完成 BMAD 文档和代码 happy path，没有 detached mutation 与新任务盲测，合理结论只能是 80%～85%，不能宣称 90%。
