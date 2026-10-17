# Input Reconciliation: docs/know-tc-d1-rebuild.md

## 结论

PRD 已覆盖 TC-D1 的主要产品结果、目标/验证器可信性、真实探针、六类矩阵、消费者闭合、行为级回滚、Exact Cover 和生命周期权限分离。当前不能视为与上游完全对齐：有 2 项高优先级问题、5 项中优先级问题。最主要的缺口是上游明确要求的旧 TC-D1 需求演进分类没有进入任何产物；最主要的扭曲是 PRD 为历史兼容场景引入了上游不存在的单侧执行例外。

## 高优先级问题

### H1. 缺少旧 TC-D1 需求逐项演进分类

上游第 7 节要求后续文档将“每一项旧 TC-D1 requirement”分类为 retained、superseded、narrowed 或 removed。PRD 和 addendum 仅概括了保留能力、现有资产和证据缺口，没有旧需求清单、逐项分类、分类理由或对应的新 FR。

这会使 reviewer 无法判断旧的十七项 acceptance assertions 哪些仍有规范效力，也无法证明新 PRD 没有静默删除或继续继承已过时要求。应在 PRD 或 addendum 中增加逐项分类表，并绑定旧需求标识、分类、理由和新 FR；未知项必须列为开放问题，不能由 Spec 自行猜测。

### H2. FR-7 引入未获上游授权的单侧执行例外

上游 D1-R7 要求每个 case 都声明 stable command 与 candidate command，执行两侧并保留分离的进程证据。PRD FR-7 改为“unless the case contract explicitly defines a one-sided historical observation”，允许历史场景单侧执行。该例外无来源，并削弱了上游用真实双版本比较修复弱矩阵的核心边界。

应删除该例外。若历史兼容场景确实无法双侧执行，应先回到上游决策，明确它是矩阵外兼容观察，或明确双侧各自代表什么，不能在 PRD 内自行放宽。

## 中优先级问题

### M1. 三个 Evaluation Seed 的规范身份丢失

D1-R6 明确保留：

- `candidate-baseline-contamination`
- `self-hosted-knowledge-read-set-collision`
- `toolchain-policy-architecture-index-gap`

PRD FR-6 只称“三个 historical repair families”，addendum 也未列名。名称是产品范围的一部分，不是可任意替换的实现细节。应恢复三个稳定身份，避免 Spec 选择错误对象。

### M2. 历史兼容要求弱化了对原生命令的保存

D1-R5 明确要求保存 machine-bound historical command，并验证其 native references 与 hashes。FR-5 只明确历史 evidence、references 和 content identities，没有保留原生命令这一可审计事实。应补入“保留原始机器绑定命令，但不把它描述为可移植或重新执行的当前权威”。

### M3. Current Snapshot 被提前解释为“语义结果相同即可”

FR-12 增加“incidental temporary paths need not have identical bytes”，SM-6 又将目标表述为 fresh-checkout 下复现 semantic verdict。上游要求的是从覆盖决定结果的 roots 重建 final snapshot，尚未授权忽略哪些字节，也未把“相同语义结论”定义为充分的快照重建。addendum 已把这一点列为 Architecture 决策，但 PRD 主文却先行作出结论。

应将该句标为假设或移回 addendum，并在 Architecture 决定 snapshot identity、可移植字段及排除规则之前保留 fail-closed 边界。

### M4. 机器可判定的非授权约束未被保留下游

D1-R11 不只要求文字上的权限分离，还明确要求 replay、seed、matrix、review、Quick Dev 输出使用 `authorizes: []`。PRD 保留了非授权产品语义，但 addendum 没有保存这个明确的下游契约输入。字段设计可留给 Spec，然而“输出必须机器可判定地声明不授权”不应丢失。

建议在 PRD 保留产品能力表述，并在 addendum 记录上游现有约束 `authorizes: []`，由 Spec/Architecture 决定兼容方式。

### M5. 当前 Git baseline 没有明确成为 freshness 输入

D1-R1 要求新轮次绑定 current Git baseline 与 Skill-input v2。PRD 明确保留 Skill-input v2、Current Snapshot 和 pinned inputs，但未明确 Git baseline 是当前性判断的一部分。应补充该产品约束，具体提交字段和计算方式留给 Spec。

## 低优先级与澄清项

### L1. 无来源的治理陈述

PRD 第 10 节声明 Toolchain Maintainer 拥有 product scope 与 implementation authorization，并声明 Accepted ADR owners 管理 durable authority 等变更。上游没有定义这些角色的授权模型。若来自仓库 Agent contract 或 ADR，应引用对应来源；否则标为 `[ASSUMPTION]`，避免创造新的治理权威。

### L2. 回滚证据范围出现轻微扩张

FR-10 要求 “failed candidate, new, and historical evidence” 均保持不变；上游只明确保护 failed candidate 与 historical evidence，并总括要求 append-only。这里的 “new” 含义不清。建议改成“本轮新增证据只追加，既有 failed candidate 和 historical evidence 不变”，以匹配源意。

### L3. Consumer 被提升为独立目标用户但未标记假设

上游把 current Toolchain consumers 定义为验证对象，没有明确把其作为直接 PRD 用户。该推断合理，但应在 assumptions 中说明 Consumer 对确定性接口和错误行为的需求是从下游验证范围推导而来。

## 已正确保留的定性边界

- 只修复现有 TC-D1 目录，不创建替代目录。
- 08-01 和既有 08-05 历史保持不可变，新工作追加。
- round-6 Q8 和历史 Acceptance 仅作输入，不形成当前权威。
- Skill-input v2 已由后续演进拥有，本轮不重新设计。
- TC-E0、TC-D2-D6、Phase service、Hosted workspace、自动晋升、Miner/Memory、学习排序、RL 等保持范围外。
- 标签数量、JSON 相等、预填观察、单一消费者、版本自报和配置状态都不是充分证明。
- 六类场景、真实正反探针、错误目标、恒成功验证器、跳过执行、证据复用、下游成功路径和行为级回滚均形成了产品要求。
- replay、seed、matrix、review、Quick Dev 与 Acceptance 的权限边界在产品语义上得到保留。
- NFR-7 的时间和输出预算被明确标为假设并留作测量，属于合规新增，没有伪装成源需求。

## 无明显遗漏的需求映射

- D1-R2 对应 FR-1、FR-2。
- D1-R3 对应 FR-3。
- D1-R4 对应 FR-4。
- D1-R5 主体对应 FR-5，但需补原生命令。
- D1-R6 主体对应 FR-6，但需补三个稳定身份。
- D1-R7 对应 FR-7、FR-8，但需删除单侧例外。
- D1-R8 对应 FR-9。
- D1-R9 对应 FR-10。
- D1-R10 对应 FR-11、FR-12。
- D1-R11 对应 FR-13，但需把机器可判定的非授权约束保留下游。
