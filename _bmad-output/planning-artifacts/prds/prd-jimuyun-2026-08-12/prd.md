---
title: Ji Mu Yun 可验证任务连续性标准
status: final
created: 2026-08-12
updated: 2026-08-12
---

# PRD：Ji Mu Yun 可验证任务连续性标准

## 0. 文档目的

本文面向 Ji Mu Yun 产品负责人、Phase 服务维护者、仓库工具链维护者以及后续架构、执行计划和验收流程。本文定义跨工具链控制面、Phase 服务层和用户沙箱层的任务连续性产品能力，重点说明产品行为、权威边界、MVP、功能需求、质量要求和成功指标；具体 schema、类、脚本、存储路径与传输实现放在 [addendum.md](addendum.md) 或后续架构文档中。

## 1. 愿景

Ji Mu Yun 应让长任务在会话中断、进程退出、服务重启、上下文预算耗尽或确定性失败后，能够从当前可信状态继续，而不是依赖聊天历史、自由文本摘要或重复执行整条工作流。

本产品提供一套跨三层共享的任务连续性标准：统一定义恢复上下文、恢复动作、预算、验证、脱敏和证据语义；由各层通过恢复 Profile 声明自己的来源、生命周期和终止条件。共享标准不合并各层状态权威，也不替代现有验证器。

对游戏创作者而言，这项能力发生在其用户沙箱工作区内，使原型制作、迭代目标和修复等游戏长任务能够可靠继续。创作者不需要理解或配置恢复协议；Phase 服务根据平台策略和当前项目证据统一决定如何恢复。只有涉及游戏意图、破坏性选择或不可自动化判断时，系统才请求用户决策。

## 2. 产品原则

1. **先检查，后继续。** 任何恢复动作都必须先形成可验证的当前状态视图。
2. **协议共享，权威隔离。** 三层可共享合同族、编译器和验证器，但不得共享 snapshot、current、cache、LKG 或完成状态。
3. **Phase 控制 Hosted 恢复。** 用户沙箱承载游戏长任务状态，Phase 服务拥有恢复启停、Profile、来源、预算、动作和调度控制权。
4. **Checkpoint 非授权。** 恢复上下文只能帮助确定下一步，不能发布规划完成、实现完成、Review 完成、验收通过或游戏任务完成。
5. **当前证据优先。** 当前来源、哈希、新鲜度和最新 live blocker 优先于历史摘要、聊天记忆和旧 route state。
6. **成本服从正确性。** 上下文压缩、结果复用和减少重跑不能绕过验证、完整性或 stop-loss。
7. **机器闭合。** 完成必须来自本层既有 validator、terminal predicate 或 acceptance evidence，不能来自 assistant 文本。
8. **研究不形成依赖。** Chapter 6 只提供设计观察；新协议独立定义、验证、发布和演进，不接入其运行或工件链路。

### 2.1 关键取舍与代价

- 选择确定性 compiler 和严格 fail-closed，换取可重放与不越权；代价是部分合法任务会被误阻断，由 SM-C1 约束。
- 选择 Phase 独占 Hosted 恢复控制，换取一致的安全、成本和完整性边界；代价是游戏创作者不能自主选择恢复策略，由 SM-C3 约束不必要的用户打扰。
- 选择“共享内核 + Profile 接入”，换取通用语义不漂移；代价是首批消费者需要建立独立映射和验收夹具，采用 M0 至 M2 分阶段交付。
- 选择最小恢复上下文，换取更低上下文成本；代价是存在遗漏耐久结论的风险，由 SM-C2 约束返工。

## 3. 目标用户与工作

### 3.1 游戏创作者

游戏创作者在 Hosted 用户沙箱中创建原型、执行迭代目标、修复失败并完成长时间游戏制作任务。

- 中断后继续当前游戏制作任务，不重复已经可靠完成的步骤。
- 清楚看到任务是在继续、刷新、等待决策、修复还是已停止。
- 在平台需要产品性判断时确认游戏目标或修复方向。
- 不必理解 thread、checkpoint、hash、Profile 或恢复来源。

### 3.2 Phase 平台维护者

- 确认每次恢复使用了正确账户、项目、工作区代次、route、run 和 attempt。
- 在来源缺失、状态漂移或重复失败时阻断错误续接。
- 在不暴露凭据或原始敏感上下文的前提下解释恢复决策。
- 分阶段从 observe 推进到 enforce，并能安全回退。

### 3.3 工具链工作流维护者

- 使用同一标准接入 VDD、Quick Dev TDD、Bootstrap Review 和 Acceptance，而不是在每个 Skill 中建立独立协议。
- 保留每个流程原有生命周期、终止谓词和证据权威。
- 用结构化状态恢复，减少重复读取、重复 Review 和无效重试。
- 验证新标准独立于任何既有 Chapter 工作流即可定义、测试、发布和演进。

### 3.4 非用户

- 游戏创作者不是恢复策略管理员。
- Hosted 工作区中的项目文件、Skill 或提示词不是 Phase 恢复权限来源。
- 外部调用方不能指定更高预算、扩大来源、关闭完整性门或强制恢复失效运行。

## 4. 关键使用场景

### UJ-1：林岚在服务中断后继续原型迭代

林岚正在制作一个进入第 4 天的牌组构筑原型，已提交包含地图奖励和卡牌平衡的多步骤迭代目标。执行进程在首个步骤通过验证后中断。她重新进入项目时，Phase 先检查账户、项目、工作区代次、route contract、当前 goal、最近 attempt、诊断和 live blocker，再决定继续同一安全步骤或建立干净续接。界面显示“正在从已验证进度继续”以及安全原因。如果状态不可信，系统阻止继续并给出可操作的修复状态，而不是从旧聊天猜测。

### UJ-2：林岚遇到需要游戏设计判断的恢复暂停

修复路线发现两个都会改变牌组节奏的合法方向。Phase 不允许模型或恢复协议替林岚选择，任务进入等待决策状态。林岚只回答游戏设计问题；不能选择恢复 Profile、来源、预算或强制 fork。她确认体验方向后，Phase 重新验证当前状态并继续。

### UJ-3：工具链维护者恢复跨会话交付任务

维护者重新进入一个已有 VDD、Quick Dev TDD、Review 或 Acceptance 运行。共享恢复内核读取该消费者 Profile 指定的当前结构化状态，验证任务身份、来源哈希、依赖状态和终止谓词，返回允许动作、推荐动作、禁止动作及原因。对应 Skill 继续拥有自己的完成权威。

### UJ-4：平台维护者评估恢复策略灰度

维护者将一个 Hosted route 置于 observe 模式。系统同时计算旧路径和新标准的恢复决策，记录差异、成本和误阻断，但不改变实际调度。达到准入指标并完成批准后切换 enforce；出现策略漂移时可回退，而不重写历史证据。

## 5. 术语

- **任务连续性**：长任务跨会话、进程、服务或上下文窗口继续并保持语义与证据正确性的能力。
- **恢复 Profile**：消费者声明的版本化配置，定义任务身份、来源顺序、必需来源、动作集合、预算、失效规则和终止谓词。
- **恢复上下文**：从当前可信来源编译出的最小、结构化、可验证且非授权的继续工作输入。
- **Checkpoint**：某个安全边界上的耐久任务投影，包含阶段、来源引用、哈希、耐久结论、未解决项和下一步提示。
- **恢复动作**：由共享标准定义、由 Profile 限定的 `inspect`、`resume`、`refresh`、`fork`、`abort` 或 `manual_pause`。
- **干净续接**：不复制全部旧会话历史，而以已验证恢复上下文开始新的执行上下文。
- **消费者**：接入共享恢复标准的工作流或服务。
- **用户沙箱**：某一账户和项目的 Hosted 游戏制作工作区，拥有项目文件、route、goal、repair、diagnostic 和 acceptance 状态。
- **Phase 控制策略**：由 Phase 服务拥有的恢复启停、Profile 选择、预算、动作选择、调度和强制门禁。
- **Live blocker**：恢复时仍然成立的最新平台或验收阻断，优先于历史状态。
- **LKG**：Last Known Good，仅指某一层自己的已验证最近良好指针，禁止跨层共享。
- **Sidecar**：生产者写出的结构化伴随工件，供恢复消费者按 schema 读取。
- **Lineage family**：同一 Review 验收目标跨修复轮次保持稳定的轮次预算身份。
- **Artifact View**：Bootstrap Review 冻结的最小完整审查输入视图。
- **E2 envelope**：Phase 父进程组装并签名、绑定一次 Hosted dispatch 的上下文清单。
- **传输续接**：Codex CLI 或 App Server 提供的 session/thread resume、fork 或 start 能力，不等同于任务语义恢复。
- **上下文压缩**：减少模型历史上下文的机制，不等同于恢复权威。

## 6. 功能能力

### 6.1 共享恢复 Profile

#### FR-1：版本化 Profile 注册

平台维护者可以为每个消费者发布版本化恢复 Profile，声明任务身份、所属层、必需和可选来源、来源顺序、动作集合、预算档位、脱敏策略、失效传播和终止谓词。

**可验收结果：**

- 未注册、版本未知或字段不完整的 Profile 无法进入恢复执行。
- 消费者只能使用服务器或仓库权威注册表允许的 Profile。
- 用户输入和用户沙箱内容不能创建、替换或扩大 Profile。

#### FR-2：分层命名空间

系统必须按工具链、Phase 和用户沙箱分别绑定任务及生命周期身份。

**可验收结果：**

- 工具链 run 不能被解析为 Hosted project run。
- 不同账户、项目或工作区代次的状态不能交叉恢复。
- 各层 current、snapshot、cache 和 LKG 均保持独立。

#### FR-3：消费者能力声明

消费者只声明差异化来源、动作和终止条件，复用共享 compiler、validator、redactor 和动作语义。新消费者接入不得复制通用恢复 schema 或状态机，且仍由自己的 validator 或 terminal predicate 发布完成状态。

### 6.2 恢复检查与上下文编译

#### FR-4：Inspect-first

系统在执行任何恢复动作前生成结构化检查结果，至少包括身份、当前阶段、来源完整性、新鲜度、允许动作、推荐动作、禁止动作和原因。

#### FR-5：确定性来源消费

系统按 Profile 顺序读取当前来源，并校验任务身份、内容哈希、schema、生命周期、新鲜度和依赖闭包。

**可验收结果：**

- 缺失必需来源、哈希不匹配、跨任务引用、陈旧状态或非法生命周期均 fail closed。
- 自由文本日志不能单独成为恢复权威。
- 位于 `logs/` 的合法结构化状态依据 schema、authority、hash 和生命周期判断，不能仅因目录名排除。

#### FR-6：最小恢复上下文

系统只保留继续任务所需的阶段、来源引用、内容哈希、耐久结论、未解决项、验证状态、证据路径和下一步约束。

**可验收结果：**

- 原始工具输出、完整聊天历史和 assistant 闲聊默认不进入恢复上下文。
- 工具执行只保留退出码、测试状态、证据路径和哈希等耐久结论。
- 当前 `AGENTS.md`、选定 Skill 和常驻规则由宿主重新加载当前版本，不使用 checkpoint 中的历史副本。

#### FR-7：非授权标记

每个恢复上下文、Checkpoint、inspect 结果和推荐动作必须显式声明其非授权性质，不能单独推进任何消费者生命周期。

### 6.3 恢复动作与止损

#### FR-8：统一动作语义

共享标准定义以下动作：

- `inspect`：只读取和解释当前状态。
- `resume`：在同一合法 run 或执行身份下继续。
- `refresh`：保持任务意图，重新编译当前上下文后继续。
- `fork`：保留旧运行证据，创建新的 continuation lifecycle。
- `abort`：将当前运行标记为有意终止。
- `manual_pause`：等待明确的用户、维护者或受保护边界决策。

Profile 可以缩小动作集合，不能改变通用动作含义。

#### FR-9：推荐与禁止动作

每次 inspect 必须同时提供推荐动作、候选动作、禁止动作和机器可读原因；调用方不得执行禁止动作。

#### FR-10：完整性与重复失败止损

系统必须识别不可恢复 bundle、已知确定性失败、重复失败指纹、状态漂移和无价值重试，并阻止用增加预算或重复 resume 绕过。

#### FR-11：传输尝试与语义工作分离

网络、进程、MCP 或模型调用失败可在同一语义阶段产生新的 attempt；只有实际进入消费者定义的语义工作才消耗语义轮次或预算。

### 6.4 上下文预算与干净续接

#### FR-12：Profile 预算

每个 Profile 必须声明上下文预算和预算计算口径。系统在 dispatch 前检查预算，在安全 Checkpoint 边界决定继续、刷新或干净续接。

#### FR-13：安全边界续接

预算超限不得中断不可分割或非幂等动作。系统必须先完成或回滚到消费者声明的安全边界，再生成恢复上下文。

#### FR-14：传输适配

系统可以将任务恢复决策映射到 Codex CLI、Codex App Server 或 Phase Hosted dispatch，但不得把传输层 resume/fork 当作任务恢复权威。

传输能力边界：

- `codex exec resume --last` 或指定 session ID 只能作为已验证任务恢复决策的执行传输；不能替代当前来源重验、Checkpoint 完整性校验或消费者终止谓词。
- `codex exec --ephemeral` 不持久化 session rollout，不能被声明为支持原生 session 恢复。
- Codex App Server 的 WebSocket transport 当前属于 experimental/unsupported production 能力，不得作为 Hosted 生产恢复的默认依赖；如未来采用，必须先通过 Phase 受控入口、认证、TLS、容量和回退验证。
- 传输能力探测失败、能力声明过期或实际行为与声明不一致时，必须 fail closed 或降级为新 dispatch，不得静默假设支持 resume/fork。

**可验收结果：**

- 需要干净上下文时使用新 thread/session 加恢复上下文，而不是复制全部旧历史。
- 使用原生 resume 时仍需重新验证当前仓库或项目状态。
- 不持久化历史的 ephemeral 运行不能被视为支持原生会话续接。

### 6.5 工具链控制面接入

#### FR-15：独立工具链基线

共享标准可以从 Chapter 6 的既有实践中提炼 inspect-first、稳定身份、完整性门、同源动作、审批状态机、stop-loss 和追加式证据等设计原则，但必须独立定义合同、状态、夹具、validator 和证据。

**可验收结果：**

- 新协议不得读取 Chapter 6 sidecar、`latest.json`、current、snapshot、cache、LKG 或其他运行工件。
- 新协议不得建立 `chapter6-local` adapter、parity 门或 Chapter 6 历史证据兼容层。
- Chapter 6 的 Taskmaster、6.3 至 6.9、Godot、`sc-test` 和 Needs Fix 等专有字段不得进入共享 schema。
- 新协议与 Chapter 6 可分别定义、测试、发布和演进；任一方变更不要求另一方迁移或同步发布。

#### FR-16：VDD 接入

VDD Profile 必须恢复目标 plan、profile、Git 基线、slice 依赖、未解决决策和规划生命周期；恢复能力不得发布超过 VDD 所有权的状态。

#### FR-17：Quick Dev TDD 接入

Quick Dev TDD Profile 必须恢复 implementation contract、精确 snapshot paths、slice 依赖及 RED、GREEN、REFACTOR 证据；漂移或部分 stage 不能作为可恢复证明。

#### FR-18：Review 与 Acceptance 接入

Bootstrap Review Profile 必须绑定 lineage family、round budget、Artifact View、角色 attempt 和 gate；Acceptance Profile 必须绑定 candidate、baseline、run input、action DAG 和导入证据。Review 不发布业务完成态，Acceptance 只能通过自身终止谓词发布 `acceptance-passed`。

### 6.6 用户沙箱游戏长任务恢复

#### FR-19：用户沙箱作为一等恢复场景

系统必须支持用户沙箱内原型制作、迭代目标、修复和验收类游戏长任务的连续性，而不是只恢复 Phase 进程或工具链运行。

#### FR-20：Phase 独占策略控制

Phase 服务独占 Hosted 恢复的启停、Profile 选择、来源集合、预算、动作、调度和门禁控制。

**可验收结果：**

- 浏览器/API 请求不能选择 `resume`、`fork`、预算、Profile 或来源。
- 用户沙箱中的 prompt、Skill、项目文件和 route state 只能在 Phase ceiling 内缩小权限，不能扩大权限。
- 服务端在 dispatch 前重算并验证有效策略。

#### FR-21：Hosted 恢复来源顺序

文件变更型 Hosted route 必须继续遵守 [ADR-0036](../../../../docs/adr/ADR-0036-phase-prototype-route-recovery-authority.md) 和 [Prototype Routes And Recovery](../../../../docs/architecture/phase-service/prototype-routes-and-recovery.md) 定义的八级恢复权威顺序：route profile、选定 route Skill、项目执行指南、prototype contract、当前 route state、当前 goal/session、repair/diagnostic evidence、最新 live blocker。Checkpoint 是该顺序的可验证投影，不新增或替代一级权威；最新 live blocker 仍然最高优先。

#### FR-22：游戏创作者决策边界

当恢复需要游戏意图、体验取舍、破坏性操作或无法自动消解的歧义时，系统进入 `manual_pause` 并请求用户回答业务问题。

**可验收结果：**

- 用户回答只补充任务意图，Phase 在继续前重新验证状态。
- 用户不能通过回答选择内部恢复动作或绕过禁止动作。
- 用户可以主动取消自己的任务，但取消不等于删除历史证据。

#### FR-23：无感自动恢复与安全读回

在不需要用户决策时，Phase 可以自动恢复，并向创作者提供账户范围内的安全状态：当前游戏任务、已验证进度、正在执行的下一步、阻断原因和是否需要输入。

#### FR-24：工作区与账户隔离

Hosted 恢复必须绑定 account、project、workspace generation、route、run、attempt 和 dispatch。任何跨账户、跨项目、跨代、过期、撤销或已消费绑定均 fail closed。

### 6.7 证据、可观测性与灰度

#### FR-25：追加式恢复证据

每次 inspect、动作选择、验证失败、恢复执行和终止均写入追加式证据，并保留失败历史。

#### FR-26：安全读回

系统为用户提供业务可理解状态，为维护者提供结构化诊断；两者均不得暴露凭据、用户 token、原始敏感 prompt 或不必要的用户沙箱内容。

#### FR-27：Observe 与 Enforce

Phase route 支持服务器控制的 observe 和 enforce 灰度。Observe 记录新旧决策差异但不改变执行；Enforce 才允许新标准阻断或选择恢复动作。用户不能选择模式。

#### FR-28：策略与重放审计

系统必须记录 Profile revision、策略 revision、输入身份、决策 hash 和 adapter 版本，使任一恢复决策可在相同权威输入下重放。

### 6.8 功能验收矩阵

| FR | 最小可观察结果 |
| --- | --- |
| FR-1 至 FR-3 | 未注册 Profile、跨层身份和消费者扩权请求均被拒绝；新 adapter 不复制通用 schema，完成态仍由原 validator 发布。 |
| FR-4 至 FR-7 | 每个 fixture 先产生 inspect envelope；缺失、stale、hash drift 和自由文本冒充权威均 fail closed；恢复产物包含 `authorizes: []`。 |
| FR-8 至 FR-11 | 每个前置状态唯一映射到允许/禁止动作及 reason code；重复确定性失败停止；transport retry 不消耗新的语义轮次。 |
| FR-12 至 FR-14 | 预算超限先写完整 checkpoint，再在安全边界新建干净续接；原生 resume 前仍重验当前来源。 |
| FR-15 | 独立夹具覆盖 clean、外部中断、重复失败、planned-only、工件缺失、stale state 和 approval 状态；依赖扫描证明决策、测试与发布链路均不读取或调用 Chapter 6 工件、CLI、producer 或 adapter。 |
| FR-16 | VDD 恢复后最高仍为其所有的规划状态，不能发布 implementation-complete。 |
| FR-17 | Quick Dev 仅从完整且未漂移的 stage 继续；部分或 stale stage 创建 successor 或阻断。 |
| FR-18 | Review round 与 Acceptance action DAG 可恢复，但 Review 不发布业务完成；Acceptance 只有当前 terminal predicate 通过才发布 acceptance-passed。 |
| FR-19 至 FR-24 | Phase 自动恢复同一游戏长任务；API 不暴露策略参数；跨 workspace 注入、沙箱 sidecar 篡改和权限扩大请求被拒绝并留证。 |
| FR-25 至 FR-28 | 每个决定生成追加式、脱敏证据；observe 不改变执行；replay envelope 冻结动态输入、time basis 和 revision，并重现 canonical decision 与 reason codes。 |

## 7. 跨领域质量要求

- **NFR-1 正确性：** 强制测试中不得出现跨任务、跨层、跨账户、跨项目或跨工作区代次污染；恢复产物不得越权发布完成状态。
- **NFR-2 确定性：** 相同 Profile revision 和规范化输入必须产生相同 canonical 决策 hash；时间、新鲜度和 live blocker 等动态输入必须显式绑定。
- **NFR-3 可靠性：** 状态写入必须原子或追加式；任意写入点中断后只能读取完整旧状态或完整新状态。
- **NFR-4 性能：** 不执行外部验证命令时，恢复决策 P95 在 2 秒内完成；恢复上下文相对完整历史重放基线减少至少 60% 模型可见输入。
- **NFR-5 安全与隐私：** 恢复产物实行字段级脱敏和访问控制；实际凭据不得进入模型上下文、浏览器读回、Git 文档或共享工具链证据。
- **NFR-6 解耦与独立演进：** 新协议不得对 Chapter 6 形成运行时、工件、兼容、迁移、测试或发布依赖；Hosted route 的既有公开行为保持向后兼容，不兼容变更必须有版本适配或显式迁移决定。
- **NFR-7 可观测性：** 维护者能区分来源缺失、hash drift、stale state、policy denial、budget rollover、transport failure、deterministic failure、manual pause 和 terminal completion。
- **NFR-8 成本治理：** 重复确定性失败、无新修复内容的 Review、不可恢复 bundle 和已命中 stop-loss 的运行不得通过提高超时或预算自动重试。
- **NFR-9 幂等性：** 相同 checkpoint 和动作请求的重试不得产生两个并发 continuation；冲突请求必须拒绝并留下证据。
- **NFR-10 协议演进：** 共享字段变更必须同时具备真实消费者、schema、fallback validator、golden example 和回归测试。

## 8. 非目标

- 不修改或替代 OpenAI Codex 原生 resume、thread 或 compaction 实现。
- 不把 ChatGPT/Codex Memories 作为必须生效的规则或任务状态权威。
- 不建设跨三层共享的全局任务数据库、current pointer、snapshot、cache 或 LKG。
- 不读取、适配、迁移或复用 Chapter 6 的运行工件、CLI、producer、状态权威或发布门。
- 不让每个 Skill 建立自己的通用恢复 schema、compiler 或状态机。
- 不允许子 LLM 自主扫描仓库或日志并决定恢复来源。
- 不允许游戏创作者配置恢复策略、预算、来源或内部动作。
- 不用恢复成功替代测试、Review、验收、Godot smoke 或其他消费者终止谓词。
- MVP 不处理多区域分布式一致性、跨设备离线合并或操作系统级 E3 隔离。
- MVP 不批量改写或删除历史失败证据。

## 9. MVP 范围

MVP 分为三个可独立验收的里程碑。任一里程碑未通过自己的出口门时，不启动下一阶段。

### 9.1 M0：独立共享内核

**交付：**

- 版本化共享恢复合同族，以及确定性 Profile registry、compiler、validator、redactor 和 inspect envelope。
- 通用动作与原因码：`inspect | resume | refresh | fork | abort | manual_pause`。
- 独立设计的 golden fixtures、决策基线和回归测试。
- 追加式证据、幂等、schema drift 和 identity mismatch 负向测试。

**出口门：** SM-1 至 SM-4 全部通过；依赖扫描证明 M0 的 schema、fixtures、validator、运行与发布链路均不引用 Chapter 6 工件或执行入口。

### 9.2 M1：工具链标准接入

**交付：**

- VDD、Quick Dev TDD、Bootstrap Review 和 Acceptance 的最小 Profile adapter。
- 各 adapter 的 lifecycle ownership、terminal predicate 和 stale-successor 测试。
- Codex 传输能力探测与 fail-closed 映射。

**出口门：** 每个 Profile 必须独立通过 §6.8 对应验收，且不存在越权完成或跨消费者状态复用。单个 Profile 可以延后：延后项只能保持 observe、不得进入 enforce，也不能被计入 M1 完成；M1 整体只有四个 Profile 均通过并获准进入 enforce 后才算完成。

### 9.3 M2：Hosted 游戏长任务闭环

**交付：**

- 一个由 Phase 选择的 Hosted 游戏长任务 lane，覆盖用户沙箱状态、Phase 独占控制、安全读回、用户决策暂停、服务重启和预算续接。
- Phase observe 差异报告、limited enforce 准入门和回退能力。
- 脱敏、跨账户/项目/工作区代次负向测试。

[ASSUMPTION: 首个 Hosted lane 选择“执行下一个迭代目标 + 对应 repair-plan”，因为它天然具有多步骤、失败修复、用户决策和当前 route state；M2 架构冻结前由产品负责人确认。]

**出口门：** 至少 50 个 observe 恢复样本或覆盖全部强制 fixture 的等价测试集；SM-1 至 SM-4 保持全绿，SM-5 达到 95%，SM-C1 低于 5%。产品负责人和 Phase 维护者共同批准 limited enforce。

### 9.4 MVP 之外

- 将所有 Hosted route 一次性切换到 enforce。
- 让用户查看底层 checkpoint、内部 reason graph 或完整诊断。
- 使用 LLM 从非结构化历史生成权威恢复状态。
- 自动发布知识库、修改 Accepted ADR 或自动批准受保护路径。
- 跨仓库、跨项目合并一个任务的恢复状态。

## 10. 成功指标

### 10.1 硬门指标

- **SM-1 错误续接为零：** 强制夹具中跨任务、跨层、跨账户、跨项目、跨代、stale 和 hash drift 的错误续接次数为 0。验证 FR-2、FR-5、FR-24。
- **SM-2 越权完成为零：** checkpoint、inspect、推荐动作或 transport 成功单独发布完成/验收状态的次数为 0。验证 FR-7、FR-16 至 FR-18。
- **SM-3 恢复夹具闭合：** 必需的中断点、服务重启、部分写入、预算超限、重复失败和 live blocker 场景 100% 产生预期动作或 fail-closed。验证 FR-4 至 FR-14、FR-25。
- **SM-4 协议独立性：** 新协议的 schema、fixtures、validator、运行和发布依赖图中，Chapter 6 工件、CLI、producer、adapter 与发布门的引用数为 0。验证 FR-15。

### 10.2 效率与体验指标

- **SM-5 首次正确恢复率：** 在可恢复测试和 observe 样本中，至少 95% 无需维护者修正即可到达首个合法下一步。
- **SM-6 上下文减少：** 相比完整历史重放，模型可见恢复输入中位数减少至少 60%，且不降低 SM-1 至 SM-4。
- **SM-7 无效重试减少：** 重复确定性失败和无新信息 Review 的再次执行次数相对基线减少至少 50%。
- **SM-8 用户恢复透明度：** Hosted 测试中 100% 的非正常暂停都向账户内用户显示当前任务、阻断类别和所需下一步，且不暴露内部敏感信息。

### 10.3 反向指标

- **SM-C1 误阻断率：** 合法可恢复样本的误阻断率低于 5%。
- **SM-C2 返工率：** 因遗漏耐久状态而返工或重做已完成步骤的比例不得高于冻结基线。
- **SM-C3 用户打扰率：** 无需产品决策的 Hosted 恢复中，用户介入率不得高于 10%。
- **SM-C4 恢复开销：** 不含外部验证命令时 P95 低于 2 秒，且恢复编译新增模型 token 成本为 0。

### 10.4 测量合同

- M0 启动时独立冻结强制状态族、canonical 动作、reason code 和工具版本，作为 SM-3 与 SM-4 基线；不得从 Chapter 6 运行工件导入夹具。
- M1/M2 observe 启动时冻结前 30 天可比运行；历史样本不足时使用不少于 50 个覆盖强制状态族的合成/回放样本。
- SM-5 的分母是所有经权威标注为“可恢复”的 observe 样本；SM-7 的分母是命中重复失败或无新信息条件的运行。
- SM-C2 比较同类任务在恢复后重复执行已验证步骤的比例；SM-C4 由恢复 decision telemetry 直接计算。
- Phase 维护者生成测量报告，产品负责人对 M2 limited-enforce go/no-go 负责；硬门任一失败即不得发布。

## 11. 风险与缓解

- **双重权威：** 原生 session 历史与恢复上下文可能冲突。采用当前来源重验、checkpoint 非授权和明确传输优先级。
- **过度抽象：** 通用内核可能演变成全局状态机。内核只拥有通用语义，特定状态留在 adapter 和本层权威。
- **误阻断：** hash 或新鲜度过严可能大量 fail closed。使用 observe 基线、reason code 和 SM-C1 控制。
- **用户控制错位：** 不向游戏创作者暴露内部恢复开关，只暴露业务决策与安全状态。
- **敏感信息：** 使用字段级 allowlist、redactor、账户范围读回和负向测试。
- **成本转移：** MVP 使用确定性 compiler，不依赖 LLM 生成恢复摘要。
- **受保护入口：** 先完成 ADR、observe 和专门批准，再修改 Phase 共享 LLM/Codex 边界。
- **协议自举：** 使用 self-hosted VDD、目标层测试和一次完整端到端 replay。

## 12. 依赖与治理

- 需要 Accepted ADR 定义共享内核、三层隔离、非授权 checkpoint、动作语义、Phase 控制权及 transport 边界。
- 保持 ADR-0036 的 Hosted 八级恢复权威顺序与最新 live blocker 优先级。
- 保持 ADR-0044 的四维隔离、derived cache 和父进程组装/签名边界。
- Bootstrap Review 继续遵守 ADR-0041、ADR-0051 和 ADR-0056。
- 修改 `LlmRouteEngine`、`CodexHostedProcessCommandFactory` 或 `scripts/sc/_llm_backend.py` 前，需要受保护路径批准及对应测试。
- OpenAI 原生能力只作为传输与上下文机制依赖；其实验性或不支持路径必须 fail closed。

## 13. 发布策略

1. 独立冻结共享合同、强制状态族、canonical 动作、reason code 和安全边界。
2. 工具链 observe：四类 Profile 独立接入共享内核并行计算，不改变现有执行；解决全部不一致。
3. 工具链 enforce：Profile 逐个启用；旧流程证据保持原权威，但不自动成为新协议输入。
4. Hosted observe：对首个游戏长任务 lane 记录新旧决策、用户读回和隔离结果。
5. Hosted limited enforce：仅服务器允许的账户和 route 启用，持续监控硬门与反向指标。
6. 达到指标后按 route 注册新 Profile，不复制协议实现。

## 14. 开放问题与冻结点

1. **首个 Hosted lane：** 暂定“执行下一个迭代目标 + repair-plan”；Owner 为产品负责人，最迟在 M2 架构冻结前确认，未确认则 M2 不启动。
2. **用户取消后的资源与证据保留：** Owner 为 Phase 维护者与产品负责人，最迟在 M2 数据合同冻结前决定；默认立即停止新执行、保留追加式证据、不删除项目产物。
3. **预算冻结：** [ASSUMPTION: Profile 同时使用绝对 byte/token 上限与模型窗口占比，取更严格者；M0 基线后由 Phase 维护者冻结具体阈值。]
4. **RTO：** [ASSUMPTION: MVP 不承诺业务恢复 RTO，只执行 NFR-4 的本地决策延迟门；M2 observe 后再按 route 分档。]
5. **Limited enforce：** [ASSUMPTION: 产品负责人和 Phase 维护者共同批准；任一硬门失败自动回退 observe。]

## 15. 假设索引

- §9.3：首个 Hosted lane 暂定为“执行下一个迭代目标 + repair-plan”，M2 架构冻结前确认。
- §14.3：预算同时使用绝对上限与模型窗口占比，取更严格者。
- §14.4：MVP 不承诺业务恢复 RTO。
- §14.5：产品负责人和 Phase 维护者共同批准 limited enforce。
