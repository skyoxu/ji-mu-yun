# VDD / Quick Dev 差量需求：Case 级执行证据与已有行为 Regression 分流

日期：2026-09-07  
文档性质：独立上游需求，可供 BMAD PRD、Spec、Architecture 消费。  
所属层：工具链控制面。此处为范围说明，不要求新增 requirement_type 枚举。  
分析基线：skyoxu/ji-mu-yun，main commit c75951086e591b2a1113812ee76edc144da9fce3。

## 1. 目标与适用范围

在当前 CH456 编译和执行链上补齐两项能力：

1. 只有实际执行且结果符合合同的 case，才能支持对应 assertion 的运行证据。
2. 每个 obligation 按当前行为分流：缺失行为进入 RED/GREEN，已有行为进入 regression；两条路径共同参与最终覆盖。

必要的 Deferred 门禁随第二项完成。本需求优先保证证明真实性，再改善增量实施效率。

本文件作为新的差量实施输入，取代 2026-08-29《VDD Atomic Behavior Coverage, Slice Contract, and Agent Context Projection》中仍需实施的相关部分。旧文档保留为历史设计来源，不应整体重新立项，也不构成必须逐字复刻的实施合同。

本文不创建 execution-plan，不修改 GitHub，也不授予实施或验收状态。后续是否进入完整 VDD 目录，由明确的用户请求和当前仓库路由决定。

## 2. 当前基线与具体问题

### 2.1 必须复用的现有能力

- scripts/vdd/compile_plan.py 正式编译入口。
- scripts/quick_dev/run.py 正式执行入口。
- Atomic Obligation、独立 source recall、语义链 audit、V5/V6/V6A 覆盖。
- Behavior Slice 中的行为、受影响对象、状态转换、proof 和 rollback scope。
- 每 slice 自动生成的 agent-context，以及当前 worker 和 regression gate 的消费路径。
- 真实进程 receipt、独立 judge、同 selector 连续性、实际写集合检查、重复失败停止。
- Q7 slice-ready 和 Q8 implementation-complete。
- 当前开发治理模式、plan profile 与 execution profile 的独立语义。

### 2.2 Case 级证据缺口

当前 executor 有测试数量及 observed_assertion_ids；runtime edge builder 按 descriptor 声明的 assertions 生成 edge，并继承 stage observation 的结果。结构上的 assertion exact-cover 尚不足以保证每条 assertion 对应的 case 都实际执行且得到符合合同的结果。

需要补齐“声明的 assertion → 指定 case → 实际 case 结果 → 可采纳 edge”，不能仅凭整个 stage 成功或输出中出现 assertion 标记认定所有行为均被验证。

### 2.3 已有行为分流缺口

当前 Skill 已规定已有行为保留为 regression，但正式 semantic contract 和 Q7 路径仍以固定 RED/GREEN/REFACTOR 生命周期为中心。需要让 present obligation 在机器合同、调度及 terminal 中有完整路径，而非删除 obligation、伪造 RED 或依赖文字说明。

## 3. 范围约束

### 纳入

- 现有 pytest/Python 执行范围内的结构化 case 结果采集与验证。
- assertion 与实际 case 身份的绑定。
- 缺失、已有及不可判定行为的逐 obligation 分流。
- 混合实施与 regression 的计划覆盖。
- 防止核心 obligation 经 deferred 脱离当前完成范围。
- 对应的定向测试、少量负向变异和真实任务验证。

### 不纳入

- 新建原子行为编译器、projector、独立 case 管理服务或大型 evidence graph。
- 强制引入名为 run-context.json 的新文件或恢复旧 build_slice_invocation 主链。
- 新增 Toolchain requirement_type 枚举。
- 扩展到所有语言、测试框架或 Phase 服务/用户沙箱业务实现。
- 恢复开发模式中已关闭的治理产物、强制外部 review 或新的审批层。
- 重新开启 8-25 或整套 CH456 历史验收。
- 将全部仓库测试作为每次 VDD create 的前置探测。

## 4. 功能需求

### CER-R1：采集可绑定的实际 Case 结果

执行器必须从受控测试运行器的结构化结果获取 case 身份及状态。优先复用 pytest node ID 和参数化实例身份；具体采集格式由 Spec/Architecture 确定。

每条结果至少能关联：case identity、当前 run/stage、selector、case outcome、实际执行阶段和结果来源。沿用现有 descriptor、receipt、candidate、target/fixture 绑定，不另建平行身份体系。

规则：

- 进程 exit zero、汇总数量非零或任意 stdout 标记不能替代具体 case 结果。
- collected 不等于 executed；参数化实例必须能独立区分。
- skip、deselected、未执行、setup/teardown error、timeout 不得被当作目标行为通过。
- xfail/xpass 不得默认满足目标行为合同；如未来需要支持，应有显式结果解释，本需求不要求增加该能力。
- 结构化报告必须来自当前受控运行，旧文件、缺失报告、截断或身份不匹配必须阻断相应证明。
- 重复记录不得重复计数；若存在重试，必须明确选定有效 attempt，不能拼接多轮结果制造完整覆盖。
- 不支持的测试结果格式返回明确的 contract/adapter gap，不回退到只看 stage 成功。

### CER-R2：从 Case 结果生成 Assertion Evidence

每条 assertion 必须绑定明确的 case/node identity 或确定性可解析的 case 集合。一个 case 可以验证多个 assertions，一个 assertion 可以要求多个 cases，但必须有明确的行为映射，不能从同属一个文件推断全覆盖。

默认只有所有必需 cases 满足该 assertion 对应阶段的预期结果，才能生成可用于完成判断的成功 edge。

| 场景 | 可采纳条件 |
| --- | --- |
| 缺失行为的正式 RED | 对应 case 在目标行为断言处失败，失败 ID/原因符合当前合同，且不是 harness/environment failure |
| GREEN / REFACTOR | 对应必需 cases 实际执行并通过，保持原冻结 selector 和行为映射 |
| 已有行为 regression | 对应必需 cases 在当前相关代码状态下执行并通过，无须历史 RED |
| Terminal | 只消费当前有效且符合各自 disposition 的 case/assertion evidence |

单个失败 case 不能给未执行的其他 cases 补发 RED evidence。单个通过 case 也不能给其他 assertions 补发完成证据。

assertion 的语义质量仍由现有 oracle、源需求对齐与定向测试承担；本需求不宣称仅凭 case 身份就能证明任意测试语义正确。

### CER-R3：贯通覆盖与失败诊断

在现有 Q7/Q8 中核对 selected obligation、assertion 及其必需 case 集合与可采纳证据的对应关系。

- 不能遗漏当前范围内的 obligation，也不能以声明的 case 集合替代实际运行结果。
- 额外执行的合法回归 case 可以记录，但不能给无映射的 obligation 充当证明。
- 明确区分 case missing、case skipped、unexpected outcome、assertion binding gap、stale evidence 等诊断。
- 任一必需 case 不可采纳时，阻断依赖它的 assertion/slice，禁止发布整计划完成。
- 沿用现有变更影响和显式 predecessor 规则，仅失效受影响行为及其依赖。
- 保持 Quick Dev 只发布 implementation-complete，Acceptance 仍独立拥有 acceptance-passed。

### CER-R4：逐 Obligation 的当前行为分流

VDD 为每个 obligation 声明可验证意图、生产入口、observable、预期结果及目标 case。由受控确定性执行入口取得当前结果，再产生机器可消费的 disposition。

不要求 VDD 每次 create 运行全量测试，也不要求 VDD 自己执行正式 RED。规划就绪可以包含待执行的探测意图，但没有可采纳探测/RED 结果时不得授权生产实现或宣称已有行为已被证明。

| Disposition | 条件 | 后续行为 |
| --- | --- | --- |
| missing | 当前目标 case 出现符合行为合同的缺失结果 | 进入正式 TDD 路径 |
| present | 当前目标 case 实际通过，且证明该 obligation 的 observable | 进入 regression-only 路径 |
| unverifiable | 无法确定行为，或受到环境、harness、oracle/contract 缺失影响 | 阻断受影响范围并返回对应修复/澄清入口 |

partially-present 只作为分析中间结果；授权前必须继续拆分为更小 obligation，不能让单个粗分类遮盖独立行为。

探测结果不得仅根据文件存在、状态字符串、历史 acceptance-passed 或模型判断生成。已有可绑定、仍有效的当前执行结果可以复用，不强制无意义重复运行。探测结果只有满足全部正式 RED 条件时才可由当前执行入口采纳为 RED，不能自动升级。

### CER-R5：Regression-only 与混合计划生命周期

present obligation 必须保留在当前需求覆盖范围，并具有 regression assertion/case 和终端证明，不能通过移除或 deferred 来规避 RED 要求。

- 纯 regression slice 可以在当前回归通过后进入对应就绪和终端路径，不要求虚构 RED/GREEN。
- mixed plan 可以包含 missing 与 present obligations，分别验证后共同闭合。
- 同一执行批次内允许复用兼容 cases，但不同 disposition 不得互相借用结果。
- 生产代码变化影响已有行为时，按当前 dependency/change-impact 规则重跑相关 regression。
- 原 present 行为后来回归失败，必须阻断当前完成并触发重新判定/修复，不得沿用历史通过，也不得在缺少实施授权时自动改写行为。
- 不依赖 S1、S2 编号猜顺序；沿用现有依赖和执行合同确定可执行集合。
- 不为新增 regression 分支设计另一套主运行器或平行计划状态机。

### CER-R6：最小 Deferred 门禁

与当前 obligation disposition 关联的 deferred 记录，至少明确：类型、原因、resolution owner、resolution stage、affected obligation IDs 和由规则推导的阻断结果。

| 类型 | 允许推迟的内容 | 完成限制 |
| --- | --- | --- |
| implementation-resolvable | 已知 observable、case、预期结果及合法写边界后的内部实现策略 | 不得推迟证明合同，不满足条件则阻断 |
| external-owner | 明确属于外层 owner 的决策或证明 | 不计作当前实现已完成；若是本阶段核心前置条件，仍阻断 |
| blocking | 预期行为、selector、case、必要 authority 等尚无法确定 | 阻断受影响范围进入可执行实施；不能发布整计划完成 |

deferred 不能改变源需求的适用性，不能直接从 expected coverage universe 删除核心 obligation。只有明确的范围决定才能调整当前 scope，且需保留原因及归属。阻断值不能只相信产物作者填写的 Boolean。

## 5. 实施边界与兼容

1. 优先扩展当前 executor、runtime edge builder、semantic contract、Q7/Q8 与 agent-context 消费路径。
2. 旧证据保留其历史含义，不要求批量重写，也不能自动升级为 case-level proof。
3. 新旧合同通过显式能力/版本识别；缺少本次要求的证据时明确指出限制，不能默默退回 stage-level completion。
4. 保留现有 selector 连续性、写边界、失败分类、重复失败停止和治理模式。新增分支不能绕过这些规则。
5. 新增合同应尽量放入现有 artifact；只有现有产物无法表达时才新增文件。
6. 本次修改影响执行和完成判定，按现有 self-hosted 规则处理自身实施；仅增加被实际修改路径消费的定向验证，不复制整套历史自托管流程。

## 6. 验收标准

| ID | 场景 | 必须得到的结果 |
| --- | --- | --- |
| CER-A1 | descriptor 声明两个必需 cases，实际只执行一个且进程成功 | 未执行 case 不得产生可完成 edge，最终覆盖阻断 |
| CER-A2 | 一个必需 case skipped/deselected，其他 cases 通过 | 对应 assertion 不得通过 |
| CER-A3 | 输出打印全部 ASSERTION_ID，但结构化报告缺少对应 case | 标记不补足证据，覆盖阻断 |
| CER-A4 | 报告来自旧 run、旧 selector 或被截断 | 拒绝采纳，保持历史证据不变 |
| CER-A5 | 多个独立 missing obligations 中只有一个 case 出现预期 RED | 不得给其他 obligations 补发 RED；诊断缺失范围 |
| CER-A6 | 缺失行为的完整合法 RED → GREEN → REFACTOR | 同 selector/case 映射，当前 evidence 完整通过 |
| CER-A7 | 全部行为已存在 | 只执行所需 regression；无虚构 RED，仍可合法闭合 |
| CER-A8 | 一个 Requirement 包含已有与缺失行为 | 原子拆分和正确分流；终端覆盖同时包含两类行为 |
| CER-A9 | 初次判定 present 后，相关生产变更导致 regression 失败 | 当前完成阻断，不复用旧 pass |
| CER-A10 | 环境/import/setup failure | 判为 unverifiable 或对应环境阻断，不得进入行为 GREEN |
| CER-A11 | 核心 obligation 被标为非阻断 deferred | validator 按真实条件阻断，不能通过删覆盖绕过 |
| CER-A12 | 一条 assertion 要求多个参数化实例，缺一个实例 | 不得以总 case 数或其他实例顶替 |

本次新增的上述负向场景必须全部被拒绝；已有合法 TDD 与回归路径应继续通过。没有必要为本次差量工作重新跑无关历史 live 全套验收。

## 7. 实施顺序与停止条件

第一步：实现 CER-R1～R3，先收紧实际 case 结果到 assertion evidence 的生成和覆盖判定。

第二步：实现 CER-R4～R6，在新证据基础上增加已有行为分流及最小 Deferred 门禁。第一步可独立交付，不应被第二步拖成大型升级。

第三步：结合一个普通缺失行为、一个部分已有行为、一个小型控制面变更验证实际使用体验。可使用后续真实需求，不额外建设通用评测平台。记录人工 repair 次数及原因，区分内部自动修复与人工重建计划；出现反复纠正时定位具体失败环节，而不是自动新增治理流程。

满足本文件验收标准、当前合法路径无回归，并完成适用的定向验证后结束。本需求不以固定字段名逐字一致、额外文档数量或名义上的绝对 100% 语义正确作为完成条件。

## 8. 代码参考与审查依据

以下链接固定到本次已审查基线，属于定位依据，不要求未来实现保持原文件布局：

- [当前操作与收口规则](https://github.com/skyoxu/ji-mu-yun/blob/c75951086e591b2a1113812ee76edc144da9fce3/docs/ch456-practical-closeout.md)
- [语义计划合同](https://github.com/skyoxu/ji-mu-yun/blob/c75951086e591b2a1113812ee76edc144da9fce3/.agents/skills/vdd-execution-plan/scripts/semantic_plan_contract.py)
- [进程结果采集](https://github.com/skyoxu/ji-mu-yun/blob/c75951086e591b2a1113812ee76edc144da9fce3/.agents/skills/quick-dev-tdd-adapter/tools/process_executor_v2.py)
- [运行证据生成](https://github.com/skyoxu/ji-mu-yun/blob/c75951086e591b2a1113812ee76edc144da9fce3/.agents/skills/quick-dev-tdd-adapter/tools/runtime_evidence.py)
- [Q7/Q8 覆盖判定](https://github.com/skyoxu/ji-mu-yun/blob/c75951086e591b2a1113812ee76edc144da9fce3/.agents/skills/quick-dev-tdd-adapter/tools/coverage_predicates.py)

基线判断来自代码阅读及已提交记录，并非新一轮 live 执行证明。实施前只需检查相关入口的新变化并去重，不因 main 继续演进而自动扩大本需求范围。
