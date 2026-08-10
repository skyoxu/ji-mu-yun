# PRD Quality Review — VDD Conformance Exact-Cover Skill 需求规格

## Overall verdict

总体判定：**thin，不宜以当前 `requirements-ready` 状态直接进入实现或作为 VDD 的再次消费输入**。文档对 exact-cover 的核心不变量、确定性/LLM 边界、负例和 fail-closed 条件已有扎实实质；但它仍无法证明传入的 `vdd_sources` 就是完整上游全集，也没有定义一个符合当前 `vdd-execution-plan` 路由与输入边界的回流产物，因此最关键的“无静默遗漏”和“产物可被 VDD 再消费”尚未闭合。

## Decision-readiness — thin

文档作出了若干清晰决定：新 Skill 与 Bootstrap Review 分责（§2）、中间产物不授权（§§3、7、11）、deterministic fail 阻止 Bootstrap（§§5、7），并选择渐进迁移（§10）。这些决定足以让团队理解设计方向。

但两个会改变产品正确性的决定仍未落地：authority 全集由谁、以何种不可遗漏的规则冻结；以及 deterministic PASS 后的 risk policy 如何得到唯一结论。当前状态把这两点留给实现者解释，却把文件标记为 `requirements-ready`（第 4 行），决策成熟度与状态不一致。

### Findings

- **critical** 上游 authority 全集没有可证明的闭包规则（§3，第 54–67 行；§5 S0，第 115–117 行）— `vdd_sources` 只是“路径集合”，文档未规定它如何从目标 requirements 目录、repository governance、`AGENTS.md`、`README.md`、Chapter 5 及其他声明来源中独立重建，也未规定必选文件、递归/忽略规则或 expected-source manifest。调用方只要漏传一个源，后续 set equality 仍可能对一个不完整 universe 得出 PASS，这直接违背第 269 行“任何 VDD requirement 都不能静默消失”。*Fix:* 定义规范的 source-discovery/closure 合同：authority 类别、目标根、必选文件、目录展开与忽略规则、规范化算法、expected-source manifest/hash、缺源错误码，并加入“调用方漏传一个真实 authority 仍必须 blocked”的负例。
- **high** 风险路由不是确定性契约（§5 S5，第 141–148 行；§6，第 152–159 行）— `low-risk` 与 `workflow-control-risk` 没有枚举、判定输入、优先级、默认失败行为或 ownership，`Acceptance policy / Bootstrap` 的斜线归属也不唯一。不同实现可对同一 PASS 候选选择不同下游。*Fix:* 给出 schema 化风险类别、逐条 predicate、冲突优先级、unknown 默认值、唯一决策所有者及相应正负例。
- **medium** 已知 legacy 风险没有形成决策或显式 deferred item（元数据第 9 行；§10，第 222–230 行）— “legacy schema 需要逐步适配”只出现在 Confidence 叙述中，未说明首版支持矩阵、触发迁移的条件、退出标准和不兼容时的用户可见结果。*Fix:* 将其提升为版本化兼容性要求或 `[ASSUMPTION]`/Open Question，并为每类 legacy 输入规定 disposition 与验收。

## Substance over theater — adequate

内容总体是实质性的。文档没有无用 persona、泛化愿景或“安全、可靠、可扩展”式空泛 NFR；source hash、双向 set equality、stale evidence、caller 伪造布尔值、Bootstrap launch count 等都对应真实失败模式。§8 的十二个负例尤其增强了规格可信度。

不足主要来自若干核心形容词尚未被操作化，它们一旦进入确定性门禁就不能只靠实现者常识解释。

### Findings

- **medium** 多个决定性术语没有阈值或规范算法（§§3–7、9）— `normalized`（第 59、117 行）、`stable`（第 87、123 行）、`current`（第 109、133、169 行）、`legitimate`（第 111、182 行）、`bounded summary`（第 139、245 行）和“超预算”（第 172 行）都会影响 PASS/blocked，却没有可测试定义。*Fix:* 在 FR/NFR 或 glossary 中为每个词定义可观察规则、单位、上限和错误结果；尤其明确文本规范化、current 的 run/candidate 绑定条件与 summary 字节/条目上限。

## Strategic coherence — adequate

产品 thesis 清楚：用确定性 exact-cover 证明 VDD requirement、实现、测试和当前证据之间没有静默遗漏，并把 Bootstrap 收缩到机器无法判定的语义问题（§§1、12）。职责、工作流、负例和最终语义都围绕这一主线，没有明显的功能堆砌。

战略层面的缺口是没有成功指标与反指标。§11 是构建验收清单，不是上线后判断该 Skill 是否真的降低漏检、误授权、上下文成本或人工审查成本的产品度量。

### Findings

- **medium** 缺少验证 thesis 的成功指标和 counter-metrics（§11，第 232–247 行）— “测试全部通过”和“一次 dogfood”只能证明实现满足夹具，不能衡量真实计划中的漏检率、误阻断率、运行成本、上下文削减或 legacy 迁移负担。*Fix:* 增加产品级指标及基线，例如已知 omission fixture 检出率、false PASS 必须为 0、代表性 corpus 的 false-block 率上限、主进程摘要上限、运行时预算；同时设置反指标，避免通过过度阻断或扩大扫描范围换取表面覆盖率。

## Done-ness clarity — thin

§7、§8 和 §11 提供了相当具体的失败条件与验收场景，工程师能据此建立一部分 RED/GREEN 测试。不过，这份文档没有稳定的功能需求 ID，canonical schema 也只展示了片段；“每条 requirement 是否有明确完成条件”仍需人工推断，不能直接形成完整 VDD requirement/acceptance owner artifact。

### Findings

- **high** 功能需求与验收标准没有稳定 ID 和逐项映射（§2，第 34–50 行；§11，第 232–247 行）— 职责条目、S0–S5、fail-closed 条件、负例和最终 12 条验收彼此只有自然语言对应，没有 `FR-*`/`AC-*` 的唯一关系。对一个声称验证 exact-cover 的产品，这使它自己的 requirements 也无法机器证明 exact-cover。*Fix:* 为每条 active FR/NFR 分配稳定 ID，为 §11 条目分配 AC ID，并提供双向 requirement↔acceptance 映射；typed deferred 也必须有 ID 与 disposition。
- **high** 实现合同和 receipt 只被命名，没有完整可验证的 I/O 契约（§3，第 56–66 行；§4.3，第 107–111 行；§5 S4，第 137–140 行）— 未给出 implementation contract schema 版本、receipt 顶层字段/状态枚举、诊断结构、退出码、原子发布规则、输出路径、最大摘要尺寸或 schema 升级兼容行为。工程师无法仅凭本文判断 producer 和 consumer 何时真正 done。*Fix:* 将每个外部产物定义为版本化 schema，列出 required/optional 字段、枚举、路径及原子性、hash 覆盖范围、CLI stdin/stdout/exit contract，并让 composition tests 绑定具体 schema 版本。
- **high** “稳定 ID”算法与 source hash 绑定存在未解决的身份语义冲突（§4.1，第 77–87 行）— 第 87 行要求 ID 由 source path、anchor 和 source hash 产生；任何文字修改都会改变 hash，因而改变 ID。若“稳定”只指同字节输入可复现，应直说；若要求需求演进期间保持身份，则当前算法不满足。*Fix:* 明确 identity stability 的时间范围，并把内容版本 hash 与逻辑 obligation identity 分离，或定义受控 rekey/lineage 映射及其 migration tests。

## Scope honesty — thin

§2.2 和首页 Non-goal 清楚排除了 Bootstrap 内部实现、lifecycle ownership、release/commit 权限及完整 execution-plan 创建，范围边界比多数技术 PRD诚实。问题在于，多项影响架构和下游消费的未知项没有以 Open Question、`[ASSUMPTION]` 或 `[NOTE FOR PM]` 显示，读者会误以为它们已决。

### Findings

- **high** `requirements-ready` 掩盖了未声明假设（第 4、9 行；§§3–6、10）— 文档没有 Open Questions 或 Assumptions Index，但事实上假设了调用方能给出完整 `vdd_sources`、存在统一的“符合 schema”目标、current evidence 可统一判定、risk policy 能唯一分级、legacy 可只读重建。这些不是实现细节，而是会改变安全性和兼容性的产品决定。*Fix:* 建立 Open Questions/Assumptions Index；阻断性问题在 `requirements-ready` 前关闭，非阻断项记录 owner、重访条件与 fail-closed 默认值。
- **medium** Non-goal 未明确 conformance receipt 是“仅证据”还是“可作为新一轮需求输入”（首页第 6–8 行；§5 S4；§9）— 文档排除了创建 execution-plan，却没有说明 Skill 是否应生成新的规范需求文档。这正是“可被 VDD 再消费”范围的核心边界。*Fix:* 在 Scope/Non-goal 中做二选一决定，并同步定义对应产物和验收；不要把该判断留给实现阶段。

## Downstream usability — broken

这是 chain-top 技术能力规格，下游不仅包括实现/测试，还明确包括 Quick Dev、Acceptance、Bootstrap，以及用户要求的 `vdd-execution-plan` 再消费，因此本维度应从严。当前文档给出了概念链 `VDD → exact-cover producer → Quick Dev`，但没有给出 VDD 可接受的回流文件、显式 route 或 consumer closure。

当前 `vdd-execution-plan` 契约还规定：单个 standalone requirements Markdown 默认进入直接实现，只有用户明确要求创建完整 execution-plan directory 才能进入 VDD create；不能从文件内容或复杂度推断 VDD 路由。本文没有承接这个路由约束，因此“新 Skill 执行后产物可被 VDD 再消费”在当前规格下不成立。

### Findings

- **critical** 新 Skill 没有产出一个可被 VDD 再消费的规范 artifact（§4.3，第 107–111 行；§5 S4，第 137–140 行；§9，第 202–220 行）— 唯一明确产物是非授权、compact、hash-bound conformance receipt；它是校验证据，不是 requirements 输入。文档没有定义 `requirements.md`/intent bundle、其 normative content、source lineage、schema/version、路径，也没有规定调用 VDD 时必须出现的显式 “create/repair complete execution-plan directory” 用户意图。*Fix:* 定义一个命名的 VDD re-entry artifact 与显式 handoff contract；若 receipt 仅作证据，则另产出规范化 requirements artifact，并规定用户/上层路由如何显式选择 VDD create/repair。若设计上禁止循环消费，则把“可再次消费”明确列为 Non-goal，而不能声称满足。
- **high** 验收组合没有 VDD consumer closure（§8，第 194–200 行；§11，第 246–247 行）— 组合链只覆盖 Quick Dev、Acceptance 和 review decision，没有“new Skill output → VDD route → plan-ready artifacts”的真实 producer→consumer 测试。因此即使全部 12 项验收通过，也无法证明用户要求的第 4 点。*Fix:* 增加真实 VDD consumer composition：以 Skill 的实际输出作为冻结输入，显式请求正确 VDD route，验证 profile、source freeze、knowledge preflight、requirement/acceptance 映射及 plan-ready 门禁；同时增加缺失显式 route、stale receipt 和仅 receipt 输入时的负例。
- **high** 没有对齐 VDD 的 profile、lifecycle 与 owner artifact（§§9–12）— 修改 VDD/Quick Dev/Acceptance routing 的工作按当前 VDD 契约应属于 `self-hosted` profile，且 VDD 只发布到 `plan-ready`，Quick Dev、Acceptance 分别拥有后续状态。本文提到 lifecycle ownership 不变，却未规定 re-entry 时选择的 profile、owner artifact 或状态边界。*Fix:* 在 VDD handoff 要求中固定此类变更的 profile 选择依据、plan owner artifact、允许读取的 receipt 类型以及每个生命周期状态的唯一发布者。
- **medium** 缺少 glossary，且关键域名存在漂移（§§3–5、11）— `obligation_id`（第 77 行）与 `requirement_id`（第 109 行）、`canonical acceptance` 与生命周期 `Acceptance`、`evidence`/`current run evidence`/`receipt`、`implementation contract`/`matrix` 没有明确同义或不同义关系。source-extract 后容易产生不兼容 schema。*Fix:* 增加术语表，固定每个实体的规范名称、ID namespace 和关系；禁止未声明同义词。

## Shape fit — adequate

作为内部、单操作者、brownfield 的确定性验证能力，采用 capability-spec 形态是合适的；不需要 persona 或叙事型 UJ。文档以边界、数据模型、状态化工作流、负例和验收为主，也符合这类工具的阅读方式。

但它同时是会改变 VDD/Quick Dev/Acceptance 控制链的 chain-top 规格，应比普通技术设计更强调消费者契约和现有 authority 的精确引用。§9 的目录树已经进入实现设计，而更重要的 operator/caller handoff 仍缺位，信息权重略有倒置。

### Findings

- **medium** 缺少最小操作流程/角色交接视图（§§2、5、12）— caller、deterministic producer、Quick Dev、Acceptance owner、Bootstrap route 各自读写什么、在哪一步停止、谁负责显式 VDD re-entry，分散在多节中且有空白。*Fix:* 增加一个不涉及 UI 的 operator/caller journey 或状态转换表，列出每一步的输入、输出、owner、失败结果和下一合法消费者。
- **low** 计划目录结构早于消费契约定稿（§9，第 202–220 行）— 文件树和脚本名属于可放入 addendum/技术设计的实现选择，而 VDD re-entry artifact、risk policy 等产品决定尚未闭合。*Fix:* 保留能力级目录约束即可，把可变脚本布局移至 addendum，并用篇幅优先补齐消费者合同。

## Mechanical notes

- **low** ID 与命名机械一致性不足 — `obligation_id`、`requirement_id`、`acceptance_id` 和 §11 的无 ID 编号无法直接做连续性检查；`Acceptance` 同时指 canonical criteria 与生命周期 owner。建议建立 glossary 和 ID registry 后运行唯一性、连续性、双向引用检查。
- 文档没有 FR/UJ/SM ID，因此不存在可验证的 ID continuity；UJ 对该工具形态不是必需项，缺失本身不构成问题。
- 文档没有任何 `[ASSUMPTION]`、`[NOTE FOR PM]` 或 Assumptions Index；这不是“无假设”的证据。至少首页 Confidence 已声明一个 legacy 风险，且 authority closure、risk policy、VDD re-entry 都是尚未闭合的假设/决定。
- §8 的组合链与 §11 的验收编号均可读，但没有反向链接到 §2 职责、S0–S5 或 schema 字段；下游 source-extract 只能依靠语义匹配。
- 当前目标文件是 standalone Markdown requirements spec，而不是带 BMad PRD frontmatter、稳定 FR/AC ID 与 reviewer/open-item 状态的成型 PRD。这种形态可以作为人工输入，但不足以自行证明 exact-cover，也不会自动触发当前 VDD create/repair 路由。

## Severity summary

- Critical: 2
- High: 7
- Medium: 6
- Low: 2
