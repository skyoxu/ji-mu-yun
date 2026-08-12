# PRD Quality Review — Ji Mu Yun 可验证任务连续性标准

## Overall verdict

这份 PRD 的产品 thesis、三层权威边界、Chapter 6 兼容原则，以及 Phase 对用户沙箱恢复策略的独占控制都表达得清楚，已经足以指导架构讨论和风险评审。但它还不是可直接批准进入实现的合同：MVP 同时承诺过多接入面，5 个开放问题中有多项会改变 MVP 设计与发布门槛，而且大量 FR 缺少逐项可验证后果。综合判定为 **Fair / 需修改后再进入架构与 story 拆分**。

## Decision-readiness — thin

PRD 对核心决策并不含糊：§2 明确选择“协议共享，权威隔离”、由 Phase 控制 Hosted 恢复，并把 checkpoint 定位为非授权投影；§8 和 addendum §7 也清楚拒绝了用户选择恢复模式、跨三层共享状态以及用 compaction 代替业务恢复。这些决定足以避免最危险的方向漂移。

但 §14 仍保留了会直接改变 MVP 边界和验收口径的问题，包括首个 Hosted lane、预算模型、RTO、取消后的资源保留，以及 limited enforce 批准责任。尤其 §9.1 已把 Hosted lane 写入“必须交付”，却同时用 “[ASSUMPTION: …实现前由产品负责人确认]”延迟选择；在这些问题收敛前，决策者无法稳定批准架构、容量设计或发布责任链。

### Findings

- **high** MVP 关键决策仍停留在开放问题 (§9.1, §14) — “首个 Hosted lane”“预算计算口径”“业务 RTO”和 limited enforce 批准者都会改变实现合同或发布门槛，不只是实现细节。*Fix:* 在批准进入架构前，至少关闭 §14.1、§14.2、§14.3、§14.5；把确定结果写回 MVP、NFR 和发布策略，确实无法决定的项目标明 owner、截止点和 fail-closed 默认值。
- **medium** 核心取舍虽有结论，但牺牲项分散在风险与 addendum (§2, §11, addendum §7) — PRD 说明选择了确定性 compiler、严格 fail-closed 和 Phase 独占控制，却没有在主叙述中集中说明为此放弃的恢复率、用户自治和接入速度。*Fix:* 在产品原则或 MVP 前加入精简的“关键决策与代价”，明确每个不可逆选择获得什么、牺牲什么、由哪个反向指标约束。

## Substance over theater — strong

愿景不是可互换的基础设施套话：§1 直接锚定 Ji Mu Yun 的三层任务连续性、游戏创作者工作区以及 Phase 策略控制。§6 的能力围绕真实恢复合同展开，Chapter 6 sidecar、Hosted 八级来源、live blocker、workspace generation 和消费者终止谓词等细节均与产品上下文绑定。§7 的 NFR 大多给出了具体边界或阈值；不存在装饰性 persona、泛化创新宣称或大段模板家具。

没有额外 finding。

## Strategic coherence — thin

PRD 的战略主线明确：以 Chapter 6 为兼容基线，抽取共享语义，同时保留工具链、Phase 与用户沙箱各自权威；功能、风险和硬门指标都围绕这条主线。SM-1 至 SM-4 直接验证“不串线、不越权、不放宽”，反向指标也覆盖误阻断与用户打扰。

问题在于 §9.1 的“MVP”同时包含共享内核、Chapter 6 adapter、VDD、Quick Dev TDD、Bootstrap Review、Acceptance、Codex transport、一个 Hosted 游戏长任务 lane、observe/enforce、证据与多类故障测试。这不是一个可快速证明 thesis 的最小产品切片，而是接近完整平台铺设；§13 虽给出发布顺序，却没有定义哪一个最小阶段已经足以验证投资假设或允许停止。

### Findings

- **high** MVP 同时承担六类消费者与 Hosted 控制面，缺少最小验证切片 (§9.1, §13) — “Chapter 6 adapter”之后又要求四类 Skill adapter、Hosted lane、transport 和 enforce 准入，导致首个可用证据出现过晚，任一接入阻塞都可能拖住整体 MVP。*Fix:* 把 MVP 分成有独立 terminal predicate 的最小切片，例如先用 Chapter 6 parity 证明共享内核，再用一个 Phase 选择的 Hosted lane 证明跨层恢复；其余 adapter 设为后续准入批次，并为每个切片定义继续/停止条件。
- **medium** 效率类成功指标缺少测量合同 (§10.2, §10.3) — “至少 95%”“减少至少 50%”“不得高于基线”和“主要延迟或 LLM 成本来源”未定义样本集合、观察窗口、基线版本或主要来源阈值，难以据此做 go/no-go。*Fix:* 为 SM-5、SM-7、SM-C2、SM-C4 补充 denominator、样本最小量、时间窗口、基线冻结点与判定责任人；将 SM-C4 改为明确的延迟和成本占比上限。

## Done-ness clarity — thin

部分关键 FR 已经写出良好的可验收后果，例如 FR-1、FR-2、FR-5、FR-14、FR-15、FR-20、FR-22；NFR-4 和成功指标也提供了性能及安全阈值。这些内容可以直接转为测试夹具。

但 28 个 FR 中相当一部分只有能力陈述，没有逐项可观察的完成条件。FR-3、FR-4、FR-7 至 FR-13、FR-16 至 FR-19、FR-21、FR-23 至 FR-28 多数没有明确的正向/负向示例、状态转换结果或 evidence 产物；诸如“系统必须识别”“能够重放”“支持……连续性”不能单独确定 done。跨流程 adapter 的完成定义尤其容易被不同团队自行解释。

### Findings

- **high** 多数 FR 缺少逐项可验证后果 (§6) — 例如 FR-10 的“识别不可恢复 bundle”、FR-16 至 FR-18 的消费者接入、FR-19 的游戏长任务连续性、FR-27 的 observe/enforce 和 FR-28 的重放都没有说明给定何种输入、产生何种状态/原因码/证据才算通过。*Fix:* 为每个 FR 至少补一个可测试 consequence；对状态机能力写明前置状态、动作、结果状态、禁止副作用和证据字段，对 adapter 写明 golden fixture 与 terminal predicate 边界。
- **medium** “相同权威输入下重放”与动态输入约束未闭合 (§6 FR-28, §7 NFR-2) — 文档要求记录决策 hash 并重放，但没有规定时间、新鲜度、live blocker、策略 revision 等动态值如何冻结或注入，测试可能得到无法比较的结果。*Fix:* 在验收结果中明确 replay input envelope 必须携带规范化动态输入及其 revision/time basis，重放比较 canonical decision 与 reason codes，而非实时外部状态。

## Scope honesty — strong

§8 明确排除了原生 Codex 实现替换、跨层全局状态库、用户策略控制、LLM 自主选源和用恢复替代验收；§9.2 进一步限制 MVP 的 route 覆盖和可见诊断。唯一 inline assumption 在 §15 完成 roundtrip，§14 也没有把未决项伪装成已决结论。对内部平台级 draft 而言，开放项数量可见且没有静默减配。

没有额外 finding。

## Downstream usability — adequate

文档面向 UX、架构和 story 创建，§5 glossary、FR-1 至 FR-28 的连续稳定编号、UJ-1 至 UJ-4、SM 与 NFR 编号都便于抽取。各能力组边界清楚，addendum 把实现机制和迁移建议放在合适位置，没有污染主 PRD。

两个问题会增加下游解释成本：四条 UJ 使用角色类别而不是具名 protagonist；FR-21 只说“当前八级恢复权威顺序”，主 PRD 和 addendum 都没有列出八个来源或给出具体 owning document 路径。后者对 brownfield 架构尤其重要，因为该顺序被声明为不可暗改的既有合同。

### Findings

- **medium** User Journey 没有具名 protagonist (§4) — “创作者”“维护者”是角色标签，不是携带场景上下文的命名人物，UJ-1/2 也未说明同一创作者的项目阶段、任务时长或中断前状态差异。*Fix:* 至少为 Hosted 创作者 journey 使用一个具名 protagonist，并在叙述中携带项目阶段与约束；工具链维护者 journey 若保持 capability-style，可明确标注其作为运维场景而非 persona journey。
- **low** 关键 brownfield 合同引用不可独立解析 (§6 FR-21, §12, addendum §4) — “当前八级恢复权威顺序”和 ADR-0036 被反复引用，但没有列出八级来源或提供具体仓库路径，抽取单一 FR 的团队无法确认精确合同。*Fix:* 在 FR-21 列出八级来源，或链接到确切 owning document/ADR 路径并注明 revision；避免仅依赖编号和“当前”。
- **low** glossary 未覆盖若干下游关键缩写与 artifact 名称 (§5, §6, addendum §3–5) — LKG、sidecar、lineage family、Artifact View、E2 envelope 等出现在要求或架构背景中却未定义。*Fix:* 补齐会进入 schema、story 或验收语言的术语；纯实现名若不需要成为产品合同则留在 addendum 并链接定义源。

## Shape fit — strong

这是高风险、brownfield、跨团队内部平台能力，采用 capability-first 主体、少量承载真实场景的 UJ、独立 NFR、非目标、MVP、指标、风险与治理是合适的。游戏创作者体验被保留为一等场景，但没有把整个内部控制面强行写成大量 persona journey；Chapter 6 既被当作兼容基线，也明确保留在 adapter 而非推倒重建，符合现有系统形态。

没有额外 finding。

## Mechanical notes

- FR ID 从 FR-1 至 FR-28 连续且无重复；UJ-1 至 UJ-4 连续；NFR-1 至 NFR-10 连续。
- SM 主指标使用 SM-1 至 SM-8，反向指标使用 SM-C1 至 SM-C4，命名清楚且无冲突。
- 唯一 inline `[ASSUMPTION: ...]` 位于 §9.1，并已在 §15 假设索引中 roundtrip。
- 未发现 `[NOTE FOR PM]` callout。
- 四条 UJ 均有明确角色，但不满足 rubric 对“具名 protagonist”的严格要求。
- Markdown 相对链接 `[addendum.md](addendum.md)` 可解析；ADR-0036、ADR-0044、ADR-0041、ADR-0051、ADR-0056 仅按编号引用，未给出文件路径。
- 必需形状完整：愿景、目标用户/场景、术语、分组 FR、NFR、非目标、MVP、成功指标/反向指标、风险、治理、发布策略、开放问题与假设索引均存在。
