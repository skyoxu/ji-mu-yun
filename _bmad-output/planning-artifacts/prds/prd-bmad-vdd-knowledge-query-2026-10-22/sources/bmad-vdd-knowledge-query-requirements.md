# BMAD＋VDD 知识查询改造原始需求

- 状态：requirements-input／供 BMAD 规划评审
- 版本：v1.0
- 日期：2026-10-22
- 仓库：skyoxu/ji-mu-yun
- 责任面：仓库工具链控制面
- 建议仓库路径：`docs/workflows/bmad-vdd-knowledge-query-requirements.md`
- 事实核对基线：`main@bf78bb43c5583571eab9ec4001fb3c3a913c0708`
- 前置状态：用户确认 8-05、8-06 已完成并合入 main；本次已核对 main 的 8-06 合并提交。
- 本文性质：原始需求输入，不是 BMAD PRD、SPEC、Architecture、VDD 需求目录或实施授权回执。

## 1. 目标与使用场景

让维护者在使用 BMAD 分析仓库增量需求、设计架构，以及使用 VDD 创建或修复实施计划时，默认先获得相关知识线索，再核对有效来源与当前代码。减少重复建设、遗漏现有消费者、沿用过期架构或把历史计划误当成现状。

本次交付的是现有知识查询能力与 BMAD／VDD 的接入及消费规则。知识索引负责定位，来源文档和实际实现分别证明约束与实现状态，查询记录不成为新的完成权威。

典型场景：后续游戏创建工作流重构、S1／S2 规划，以及工具链维护。它们使用本次交付能力，但其功能不属于本需求。

## 2. 已确定边界与本稿设计建议

### 2.1 来自本会话的已确定方向

1. BMAD 侧关注已有能力、约束、架构决定和明确排除项；VDD 侧进一步关注实现位置、调用方、测试、依赖和写入边界。
2. 默认先查询，再核对相关来源和当前源码；未命中不等于仓库没有该能力。
3. 索引落后要明确记录并复核相关来源；无关知识更新不使整个需求目录失效。
4. development 默认不恢复整份需求的知识库冻结；现有引用完整性和验收证据校验继续保留。
5. 本需求在 8-06／Package A 后、Package B 前实施。Package B 后续负责五个既有非 BMAD Skill 的标准差异迁移。
6. 走原始需求 → BMAD PRD／SPEC／Architecture → 显式请求 VDD 创建目录 → Quick Dev TDD → Acceptance，保留逐阶段外部审核。

### 2.2 本稿提出、需在 BMAD 评审中确认的默认方案

- 将“查询可用性问题”和“输入完整性／权限问题”分开：普通只读查询不可用时可转为有记录的当前源码核查；损坏、越界或被篡改的结果不得当作缺失降级。
- PRD、Architecture 在产生依赖仓库事实的结论前查询；SPEC 默认承接已有来源，只在新增问题、缺失来源或来源变化时补查。
- 查询与采纳摘要复用现有产物、memlog 或执行记录，不强制为每个阶段增加独立文件。
- 以现有 Locator 和配置覆盖点为主；仅补足实际缺失的消费者接入和必要适配。

上述是本稿的可执行建议，不宣称已经获得独立外部审核或架构批准。BMAD 可以调整实现手段，但不得静默删除第 2.1 节的已确定边界。

## 3. 当前事实与增量缺口

以下来自固定基线的文件与静态代码检查，不代表已运行本地 BMAD、Locator 或 VDD。

| 已核对事实 | 本次含义 |
| --- | --- |
| BMAD PRD／Architecture 的 `customize.toml` 提供 activation hooks、persistent_facts、external_sources；external_sources 是按需使用，不保证预先查询 | 需要明确默认触发时机与消费结果，不能把配置存在视为查询已完成 |
| 这两个默认配置文件声明会被更新覆盖，并提供 `_bmad/custom/<skill>.toml` 团队覆盖入口；核对基线时两个对应团队覆盖文件均返回不存在 | 优先使用可维护的项目级配置；不能把本次检查解释为所有本地个人配置也不存在 |
| `consumer-policies.v2.json` 与消费者投影列出 vdd、quick-dev、bootstrap、refactor-acceptance，没有 BMAD 消费者 | 若 BMAD 复用 Locator，需要补受限的消费者身份／策略接入，不能借用别的消费者身份 |
| VDD 在 development／auto 下关闭治理，直接读取当前源码；显式配置可覆盖该模式 | 新查询行为应独立于治理开关，不能顺带改变治理默认值 |
| VDD 已有 knowledge-consumption 引用及治理路径，并非没有知识查询能力 | 应补默认路径与分工，保留有效既有能力，不重建整套知识体系 |
| Locator CLI 校验目录来源快照、策略、投影及发布；存在返回 JSON `status: blocked` 但退出码为 0 的路径 | 调用方须同时检查进程结果和结构化业务状态 |
| 知识维护与发布有独立 owner，不能由 VDD／Quick Dev／Acceptance 自动触发 | 查询失败不得自动重建、发布或恢复知识代次 |

现有 Locator 策略并不覆盖仓库所有源码路径，因此不能承诺“查询一定返回所有 C# 实现和测试”。VDD 仍须在本次任务授权范围内追踪实际调用链；本需求不建设全仓符号索引或语义搜索引擎。

## 4. 范围

### 4.1 纳入

- BMAD PRD、Architecture 的默认查询触发与配置；SPEC 的来源承接和必要补查。
- VDD create／repair 中的查询、源码核对、结果采纳和受影响范围处理。
- 复用 Locator 所需的最小消费者策略、请求适配、结果处理及配置解析集成。
- 与变更直接相关的使用说明、ADR／契约增量、测试及可观察执行记录。
- 相关来源的可追溯记录，包括发布索引来源和实际读取的当前源码身份。

### 4.2 排除

- Package B 五个 Skill 的全面标准迁移；本次触及部分按适用标准编写即可。
- 重做 8-05、8-06、7-31；实施 TC-D2／D4／D5／D6。
- 修改 Codex 内核、上下文压缩、自动开新 thread；app-server／SDK 接入。
- 新建知识平台、向量数据库、通用 RAG、Memory/Miner、全仓索引重构或强制全量重新发布。
- Phase API、账号权限、生产节点、用户沙箱及 Hosted 游戏流程的功能变更。
- 自动运行 Bootstrap、增加总入口 Skill、内部 reviewer 平台或切片并行调度。
- 把查询结果直接提升为事实、规范、实施完成或 Acceptance 权威。
- 对历史 plan、证据、知识代次进行改写或补造当前执行记录。

## 5. 功能需求

### FR-01：可维护且可核对的查询配置

提供仓库级配置，能够确定查询入口、适用阶段、消费者身份、范围和有界查询预算。优先复用 BMAD 团队配置覆盖与现有解析器；不把生成器会覆盖的默认文件作为唯一持久配置。

配置解析后应能检查有效值及来源。遵循现有覆盖与数组合并规则，避免重复追加导致同一阶段重复执行。个人配置、模型输入或自然语言查询不能扩大仓库控制的权限范围。

缺失必要配置、非法配置和不支持的消费者应有可区分的诊断；不能静默标记成成功。具体字段和默认预算由 SPEC／Architecture 确定，不在原始需求中提前设计新 schema。

### FR-02：复用既有 Locator 并明确 BMAD 身份

BMAD 使用受约束的消费者身份和策略；可采用共享的 BMAD 规划消费者或分阶段身份，由 Architecture 根据最小必要范围选择。不得伪装为 vdd、bootstrap 或其他消费者绕过准入。

请求必须保留 Domain、Visibility、Lifecycle Instance、Enforcement Level 的现有隔离原则，以及已发布目录／策略／投影的绑定检查。查询只返回定位和来源信息，后续由消费者读取和判断。

必要的消费者声明、策略生产来源及发布兼容变更属于本次范围；不得手改生成投影、伪造发布记录或使用 `--allow-unpublished-inputs`、`--allow-stale-catalog` 绕过正式路径。初次上线若需要发布包含新消费者的代次，走既有维护者显式发布流程；日常查询不得隐式触发发布。

### FR-03：BMAD PRD 默认查询

对于本仓需求的 create 或实质性 update，在形成“已有能力／新增能力／明确约束／排除范围”等依赖仓库事实的结论前执行针对性查询，并读取影响本次判断的原始来源。

输出应区分已有且已核实、已有规划但未核实实现、明确排除／延期、拟新增能力、尚待核实。历史需求目录、勾选状态或旧报告不能独自证明实现完成。

纯排版、措辞修订且不改变仓库事实判断时，可以复用已有有效记录，并说明未触发新查询的原因。不得要求维护者每次手工补一句“请查知识库”。

### FR-04：BMAD Architecture 查询与 SPEC 承接

Architecture 在形成影响实现的架构决定前，查询相关 Accepted ADR、架构 owner、接口与实现现状，并与上游已采纳结论对照。出现来源冲突时明确列出影响，不能以索引摘要覆盖现行约束。

SPEC 保留来源中的有效能力、约束、排除项及未决问题；仅在发现新问题、缺失依据或相关来源变化时补查，不机械重复 PRD 的全部查询。

继续使用现有 canonical SPEC 包、typed companion／provenance 和外部 selection commitment 规则。来源仅用于溯源时按 provenance 处理；下游必须承担的要求必须进入规范内容或适用 companion，不能靠“附上查询日志”传递义务。

### FR-05：VDD 在规划前查询并追踪实际源码

VDD create／实质性 repair 在形成实现边界、消费者、测试位置和依赖切片前，执行与需求相关的 Locator 查询，再读取相关当前源码、调用方、测试及控制契约。

查询结果只能缩小查找范围，不能替代调用链检查。索引未覆盖的文件，可在任务授权范围内直接检索和读取，但应记录为直接源码核查，不能伪造成 Locator 返回结果。

计划应表达对实施有影响的结论：哪些能力可复用，哪些仍缺失，哪些消费者或测试需要一起变化。确已存在的行为作为回归验证，不为制造 RED 而故意走旧路径或重复实现。

### FR-06：区分来源身份与采纳结论

对影响需求或架构判断的被采纳信息，保留可追踪的查询主题、消费者、结果状态、相关来源路径／定位、读取身份、简短结论和用途。未采纳的相关候选记录必要原因即可，不要求保存全部检索噪声。

索引快照、当前本地 main、工作分支提交和未提交工作树内容必须可区分。已发布索引快照不得直接重写为当前 HEAD；工作树中的新增能力可以影响本次候选计划，但不能被声明为已发布 main 的事实。

已有合同要求 hash 验证时继续执行；其他轻量查询不额外建立全仓哈希冻结。正式计划、测试与验收证据仍按原有合同绑定。

### FR-07：可观察的失败与降级处理

同时判断进程退出、超时／取消、输出可解析性、业务状态和适用来源完整性。退出码 0、打印出 JSON、生成一个查询文件均不能单独表示查询成功。

本稿提出如下默认处理；SPEC 应形成无歧义的状态与诊断映射：

| 情况 | 普通规划查询／development 治理关闭 | 已有强制治理或完整性门禁 |
| --- | --- | --- |
| 命中且来源有效 | 读取来源，记录采纳／不采纳 | 继续满足原有门禁 |
| 未命中、低置信度或有歧义 | 补充定向源码核查；不得断言能力不存在 | 不满足 required module 时按现行合同阻断 |
| 已识别的索引过期或选中来源变化 | 标记 degraded，核实当前相关来源；不消费失效候选作为事实 | 仅使用现行合同允许的 source_refresh／修复路径 |
| 可确认的查询入口不可用、未配置或超时 | 记录原因，转为独立的当前源码核查；必要事实仍无法确认则保留未决项并停止依赖它的交付判断 | 不绕过既有 required gate |
| 非法请求／配置、未知或损坏状态、发布绑定损坏、路径越界、策略拒绝 | 停止使用结果并报错，不归类为普通缺失；修正后再继续受影响判断 | 保持 fail-closed |
| 用户取消 | 停止本次查询，保留未完成状态；不得后台自动重试或宣称查询完成 | 保持原有取消与恢复边界 |

“可降级”不等于“允许假定事实”。来源不能验证、约束相互矛盾或缺失信息会影响方案时，应定位阻塞项，而非把不确定结论写成已确认事实。

当前 Locator 的通用 `blocked` 若不足以区分上述情况，应补充最小只读诊断或适配，不得仅凭空候选猜测是未命中。公共结果兼容策略由 SPEC 明确。

### FR-08：治理模式与查询能力解耦

保持现有治理模式优先级和 development／auto 默认关闭行为。默认查询不能创建冻结知识、Skill-input attestation、额外授权、review lineage 或整套治理产物。

治理开启时继续履行既有强制校验、冻结和授权规则，不因新增轻量查询而绕过。需要调整旧 ADR 对开发态的表述时，由架构阶段形成明确的适用范围增量；不能静默削弱正式模式。

### FR-09：局部刷新、恢复与有界上下文

已有查询记录在相关来源与任务意图均未变化时可复用，不要求每轮对话重新查询或注入全部历史。进入新阶段或恢复工作时，按实际依赖检查是否需要补查。

相关来源变化时更新受影响结论和下游计划；无关知识代次或无关文件变化，不单独触发整份需求重建、历史证据重写或全量重跑。正式计划本身的有效性仍服从其原有范围绑定。

只装载支撑当前判断所需的片段与文件，使用有界候选数、输出和调用次数。不能无限重试、自动出版知识或开启其他工作流修复查询错误。

### FR-10：真实消费验证与兼容交付

验证必须覆盖“配置解析 → 阶段触发 → 真实查询／诊断 → 来源读取 → 结论被下游采用”，不能只断言配置键、提示文字或文件存在。

可使用固定仓库样例测试确定性分支；还需要有界的实际 BMAD 阶段样例与 VDD 消费样例证明接线。不得伪造检索结果为真实运行结果，也不要求重跑历史全部需求。

保护既有 VDD compiler、Quick Dev TDD、SPEC 包完整性与 Acceptance 权威。对本次改动的实际路径运行针对性回归；Linux 验证不能代替 Windows 路径、编码与子进程行为验证。

## 6. 验收场景

下表是必须具备的验收行为，不预定测试文件名、断言数量或自定义校验框架。VDD 后续把它们绑定到实际入口和可执行验证。

| 编号 | 场景 | 必须观察到的结果 | 对应需求 |
| --- | --- | --- | --- |
| AC-01 | 在有团队覆盖的环境启动 PRD／Architecture | 有效配置正确；默认文件不被当作唯一持久配置；同一次触发无重复执行 | FR-01 |
| AC-02 | BMAD 通过正式查询路径请求知识 | 使用已声明 BMAD 身份及受限策略；未借用 VDD 身份；未放宽既有范围 | FR-02 |
| AC-03 | PRD 处理仓库已实现或已有规划的能力 | 查询后读取真实来源，准确区分已实现、仅计划和待核实；结论影响范围判断 | FR-03、FR-06 |
| AC-04 | Architecture 面对现有 ADR／实现约束 | 在决定前核对；冲突被显式处理，不能用历史摘要覆盖现行约束 | FR-04 |
| AC-05 | SPEC 承接及必要补查 | 规范内容与 provenance 正确分工；已有来源可复用，新事实缺口可补查；包校验保持有效 | FR-04 |
| AC-06 | VDD 在 development／auto 创建或修复目录 | 默认查询并核对当前源码、调用方和测试；没有顺带开启知识冻结或治理产物 | FR-05、FR-08 |
| AC-07 | Locator 未命中，但源码确有实现 | 实际源码核查发现能力并用于计划；没有以空结果证明不存在或重复建造 | FR-05、FR-07 |
| AC-08 | 索引与工作分支相关文件不一致 | 正确区分快照和候选代码，记录降级／刷新；未伪造发布身份或当前结果 | FR-06、FR-07 |
| AC-09 | 可确认的不可用／超时，以及用户取消 | 前者有记录地核查源码，必要事实缺失时不继续下结论；取消保持未完成且不自动重试 | FR-07、FR-09 |
| AC-10 | 退出码 0 但业务 blocked；损坏输出或越界结果 | 不作为成功或空结果接收，不通过取消校验继续，不泄露越界内容 | FR-02、FR-07 |
| AC-11 | governance on 的 required module 或完整性校验失败 | 原有阻断保持；轻量模式不能代替正式 gate | FR-08 |
| AC-12 | 恢复时相关来源变化／仅无关索引变化 | 前者只更新受影响部分；后者不自动重建整份目录或重跑全部流程 | FR-09 |
| AC-13 | 初次接入涉及消费者注册／发布 | 通过现有维护者流程准备有效代次；正常查询不隐式发布、改 main 或修改历史证据 | FR-02 |
| AC-14 | 当前工具链集成回归及 Windows 执行 | 实际消费者有证据；现有 SPEC／VDD／Quick Dev 交接有效；平台验证限制如实记录 | FR-10 |

完成判据：范围内行为可观察，失败与降级不混淆，现有消费者无已知实质回归，且后续正式 Acceptance 按现行 owner 合同完成。本文创建完成不等于本功能实施完成。

## 7. 实施与其他工作的顺序

1. 以已合入 main 的 8-06 成果为基础，完成本原始需求评审。
2. BMAD PRD → SPEC → Architecture，只描述本次增量，不重写整个工具链。
3. 维护者明确请求 VDD 创建一个完整需求目录。因本需求修改 VDD 自身，按现行规则选择 self-hosted，并限制在真正需要的协议样例和迁移检查。
4. Quick Dev TDD 实施、针对性验证及一次范围内终验，随后正式 Acceptance 与外部复核。
5. 验收合入 main 后，后续新需求采用新查询能力；Package B 对更新后的既有五个 Skill 做实际差异迁移，再推进 7-31。

本次自身的规划、实施与验收使用固定的已验证工具链基线；候选 VDD／查询适配器在隔离样例中验证，不在执行中途替换主持当前需求的稳定工具链。不得以此为由修改被冻结输入或避开既有 self-hosted 规则。

S2-06、S2-03A、S2-03B 不必等待本需求，可继续使用稳定工具链；在需求交接点同步版本。游戏工作流重构的正式 BMAD 规划建议采用本次合入后的能力；正式 VDD 规划建议在紧随其后的 Package B 稳定后启动。这是稳妥的版本安排，不是新增业务运行依赖。

## 8. 留给后续规划的实现选择

下列选择由 SPEC／Architecture 基于当前实现确定，不需要为创建原始需求先行阻塞：

- BMAD 使用共享还是分阶段消费者；具体最小策略范围与注册位置。
- 配置覆盖、hook、仓库适配器各自承担哪些步骤；如何让交互和 headless 路径一致生效。
- 如何从现有结果／只读诊断中区分过期、不可用和完整性错误，并保持调用方兼容。
- 查询摘要落在现有哪个产物；如何记录源码身份而不新增全局冻结。
- 有界预算、补查／复用条件，以及初次消费者发布的最小交付步骤。
- 具体受影响的 Accepted ADR、测试命令和 Windows 样例。

不预先指定新服务、长期进程、数据库、独立评估引擎或新治理框架。

## 9. 核对来源与验证限制

以下链接均固定于本次事实基线，后续正式规划应核对目标分支的相关差异，而非把这些版本永久冻结为产品要求。

- [根仓 Agent 合同](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/AGENTS.md)
- [仓库 README](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/README.md)
- [工具链读取入口与知识权威](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/knowledge/toolchain-workflow-index.md)
- [BMAD PRD 配置入口](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/.agents/skills/bmad-prd/customize.toml)
- [BMAD Architecture 配置入口](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/.agents/skills/bmad-architecture/customize.toml)
- [BMAD SPEC 合同](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/.agents/skills/bmad-spec/SKILL.md)
- [VDD 当前入口](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/.agents/skills/vdd-execution-plan/SKILL.md)
- [VDD 既有知识消费合同](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/.agents/skills/vdd-execution-plan/references/knowledge-consumption.md)
- [Locator 实现](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/scripts/python/knowledge_locator.py)
- [消费者策略](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/knowledge/policies/consumer-policies.v2.json)
- [消费者投影](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/knowledge/projections/consumer-projections.v1.json)
- [ADR-0048](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/docs/adr/ADR-0048-repository-knowledge-locator-workflow-consumption.md)
- [知识维护与发布边界](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/.agents/skills/maintain-knowledge-base/SKILL.md)
- [Package A／B 原始范围](https://github.com/skyoxu/ji-mu-yun/blob/bf78bb43c5583571eab9ec4001fb3c3a913c0708/docs/workflows/skill-control-plane-evolution-requirements.md)

本次进行了来源与静态实现核对，以及作者按原始需求检查表的自查；没有执行 BMAD、VDD、Quick Dev 或 Acceptance，没有开展完整仓库审计，也没有宣称独立外部审查通过。本稿仅交付一个原始需求文件，后续阶段需按维护者指令分别启动。
