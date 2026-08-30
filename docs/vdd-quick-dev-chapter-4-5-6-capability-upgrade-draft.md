---
status: draft
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
