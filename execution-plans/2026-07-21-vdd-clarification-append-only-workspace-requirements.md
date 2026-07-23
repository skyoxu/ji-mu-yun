# VDD 澄清工作区增量持久化需求规格

- Title: `vdd-execution-plan` 澄清机制更新需求规格
- Status: requirements-ready
- Branch: `fixskill1`
- Reviewed baseline commit: `ae7d3bf67531d5f585e983728ca58eb0900f9198`
- Reviewed baseline tree: `833fea71dd7a5be69d79e964e779c70f3dec5ee5`
- Goal: 在保留批量澄清效率的前提下，为 VDD 澄清增加逐用户回合的增量持久化、抗上下文压缩恢复、术语与决策候选记录，以及写入权威文件前的一次性冲突晋升门
- Scope: `.agents/skills/vdd-execution-plan/**` 的澄清协议、状态合同、恢复工具、冲突晋升门、fixtures、测试和 Skill 合规验证
- Non-goal: 本文件不实施 Skill 更新，不创建新的 execution-plan 目录，不修改正式计划、ADR、标准或产品代码
- Current step: 已冻结需求边界；必须先完成 S0 需求注册表、当前基线 manifest、状态机 schema 和预期 RED，之后才允许进入行为实现
- Stop-loss: 不得以即时持久化为由在澄清退出前修改目标计划或其他正式权威文件
- Recovery command: `py -3 -c "from pathlib import Path; print(Path(r'execution-plans/2026-07-21-vdd-clarification-append-only-workspace-requirements.md').read_text(encoding='utf-8'))"`
- Open questions: none
- Exit criteria: 本文件中的稳定需求、失败行为、控制注册表和验收场景成为本次 VDD 澄清机制更新的需求权威；S0 机器门通过前不授权直接 TDD 实现

## 1. 背景与问题

当前 VDD 澄清门已经具备稳定 `CQ-NNN`、按依赖层级批量提问、五维置信度、显式双重退出授权、headless fail-closed、authority/target hash 失效、跨进程锁、`state.json` 和 `events.jsonl` 恢复机制。

当前主要缺口不是“是否记录状态”，而是记录粒度和恢复语义：

1. `record-round` 以完整问题轮次为主要提交单位，尚未把每次真实用户澄清回合定义为必须立即提交的恢复边界。
2. 当前 `state.json` 是可变快照；`events.jsonl` 逻辑追加但由工具重写文件内容，尚未建立“历史事件对象不可修改”的强合同。
3. 已确认边界、术语、场景、决策理由和 ADR 候选没有完整的结构化增量投影。
4. 上下文压缩、会话中断或代理切换后，恢复仍可能依赖聊天摘要补足共同理解。
5. 澄清退出后的正式写入缺少一个明确的三方冲突检查和并发时间差保护合同。

本次更新吸收 `grilling` 和 `domain-modeling` 的事实/决策分流、决策分支、场景化反例、术语消歧与 ADR 候选识别，但不吸收逐题推进，也不允许澄清期间直接修改正式权威文档。

## 2. 已确认决策

### 2.1 保留批量提问

- 每轮通常至少五个同层级问题的现有规则保持不变。
- 不引入“一次只问一个问题”的强制模式。
- 决策依赖关系用于决定同一批次可以包含哪些问题，不用于把所有问题退化为逐题交互。
- 同批问题必须处于相同可回答依赖层级；尚未满足前置决策的问题不能提前进入批次。

### 2.2 即时写入澄清工作区

- 每次真实用户回答产生新的增量记录，不等待整个澄清阶段结束。
- 只允许向澄清工作区写入，不允许提前修改目标计划、正式 ADR、标准、代码或其他权威文件。
- 历史记录不可覆盖、删除或原地修正。后续结论只能通过新事件 supersede、invalidate 或 reopen 旧结论。
- 不保存完整聊天文本；只保存恢复所需的最小化结构化事实、决定、理由、状态和来源引用。

### 2.3 延迟晋升到权威文件

- 用户完成双重退出授权后，才允许把最终澄清结果投影到权威文件。
- 正式写入通过一个 promotion gate 完成。
- promotion gate 对澄清基线、当前权威和最终澄清增量执行一次三方冲突检查。
- 实际写入前必须再次比较已检查的身份哈希；该比较属于同一次 promotion 操作的并发保护，不是第二轮业务澄清。
- 发现冲突时不得部分写入权威文件。

## 3. 权威与优先级

按以下顺序解释本需求：

1. 仓库 `AGENTS.md`、受保护路径、编码和兼容性要求。
2. `.agents/skills/vdd-execution-plan/references/strict-vdd-standard.md`。
3. `.agents/skills/vdd-execution-plan/references/clarification-gate.md`。
4. `.agents/skills/vdd-execution-plan/references/skill-compliance-protocol.md`。
5. 本需求文件。
6. 外部 `grilling`、`grill-with-docs` 和 `domain-modeling` 仅作为设计启发，不构成本仓权威。

如本需求与更高权威冲突，实施必须失败关闭并先更新对应权威，不得在工具代码中静默绕过。

## 4. 功能需求

| ID | 优先级 | 需求 | 可执行验收意图 |
| --- | --- | --- | --- |
| VCR-001 | P0 | 澄清继续使用批量 CQ；不得引入全局逐题推进要求。 | fixture 证明五个独立同层问题可在一个 round 中提交，依赖未满足的问题被拒绝。 |
| VCR-002 | P1 | 每个 CQ 必须具有互斥的主类型 `fact_gap|user_decision|authority_conflict`，并可另带 `scenario_probe` 探针类型；场景探针不得挤占问题的主决策类型。 | schema/validator 拒绝未知或缺失主类型；冻结 discovery manifest 已找到权威事实时不得继续生成 `fact_gap`。 |
| VCR-003 | P1 | CQ 可以声明前置 CQ 或前置边界；批次只能包含当前依赖层级可回答的问题。 | 负例把未满足父决策的子问题放入当前 round，并以稳定规则 ID 拒绝。 |
| VCR-004 | P1 | 对合同边界、失败恢复或领域关系的重要歧义，应使用具体正常、失败、边界或演进场景探针；不得为满足数量制造无意义场景。 | 确定性层验证 applicability predicate、场景结构和 evidence refs；语义充分性只作为 fresh-context 行为证据，不得由非空字段冒充 package-level PASS。 |
| VCR-005 | P1 | 已确认的模糊或重载术语必须形成结构化术语候选，绑定来源 CQ、定义、适用范围和被替代说法。 | round/checkpoint 后可恢复术语候选；未绑定来源或范围的候选失败。 |
| VCR-006 | P1 | 难以逆转、缺少上下文会令人意外且源于真实权衡的决定应形成 ADR 候选；仓库强制 ADR 规则始终优先。 | 确定性层验证三个判定、证据引用、仓库强制性判定和 disposition 的完整性；判定质量属于 fresh-context 证据；不得直接创建正式 ADR。 |
| VCR-007 | P0 | 每次真实用户澄清回合完成解析后，工具必须立即提交一个 checkpoint，不等待澄清结束。 | 模拟两个用户回合后中断，恢复结果包含两个已提交回合且不依赖聊天文本。 |
| VCR-008 | P0 | checkpoint 历史必须仅增量增长；已提交事件的字节身份和语义不得被后续操作修改。 | 提交新事件前后比较全部旧事件哈希，任何变化以稳定规则 ID 失败。 |
| VCR-009 | P0 | 每个 checkpoint 必须具有单调序号、唯一事件 ID、前序事件身份、用户回合身份、authority/target hash、canonical payload hash 和幂等 transition ID。 | 同 transition ID 且同 canonical payload 返回原提交结果；同 ID 异 payload 在任何状态或事件写入前失败；缺口、分叉、错误前序和响应丢失重试均有负例。 |
| VCR-010 | P0 | 每个 checkpoint 必须生成或绑定一个版本化恢复快照；旧快照保留，新快照不得覆盖旧快照。 | 快照序号与事件前缀一致；删除、覆盖或绑定错误均被检测。 |
| VCR-011 | P0 | 新会话必须能够仅从澄清工作区恢复已确认边界、非目标、冲突、CQ、术语、场景、决策、置信度、退出状态和当前允许动作。 | fresh-process 恢复测试不提供聊天历史，恢复投影与提交前预期完全一致。 |
| VCR-012 | P0 | 持久化继续执行最小化和敏感信息拒绝；不得存储完整用户原文、完整对话、token、凭据、私钥或个人数据。 | 现有敏感字段和值负例继续失败，并增加 snapshot/event/candidate 字段负例。 |
| VCR-013 | P0 | 同一 canonical target 的 checkpoint 必须受跨进程锁和可恢复提交协议保护，Windows 路径比较不区分大小写。 | 并发测试证明无重复序号、双 active run、丢失更新、半事件或分叉。 |
| VCR-014 | P0 | invalidate、reopen、supersede 和 restart 必须通过新增事件表达，不得重写历史决定；restart 必须由 target registry 所有的幂等 successor transaction 原子绑定 predecessor head、successor ID/genesis 和 active pointer。 | 操作前后旧事件哈希保持一致；在 predecessor 终结、successor 初始化和 active pointer 切换的每个故障点重试同一 transition ID，均恢复到唯一 successor 且不存在 terminal predecessor 无 successor 的窗口。 |
| VCR-015 | P0 | 现有 clarification run 必须提供向新合同的兼容恢复路径；迁移不得改写既有历史证据。 | 首个 migration event 绑定每个 legacy 文件的 raw SHA-256、长度、schema、adapter version、规范派生状态和 predecessor；建立 successor 后旧身份漂移必须 quarantine。 |
| VCR-016 | P0 | promotion 必须要求有效的双重退出交互证据、当前 authority/target/clarification-head freshness、允许的 write disposition，以及候选绑定的路径审批。 | generic agreement、headless/model exit、跨 session 重放、stale hash/head、blocker normal-write 和审批候选不匹配均不能进入 promotion。 |
| VCR-017 | P0 | promotion 必须对 run 初始化时冻结的 baseline authority、current authority 和 clarification delta 做一次三方冲突检查。 | fixtures 分别覆盖 unchanged、deterministically compatible、authority conflict、path/mode/owner change 和 deleted source；promotion 不得重建 baseline。 |
| VCR-018 | P0 | 冲突检查必须覆盖术语、决策、非目标、正式所有者、受保护边界，以及实际工作树对象身份。Git 文件同时绑定 HEAD tree entry、index stage 与 working-tree lstat/type/mode/raw/canonical identity；Windows 文件绑定 normalized final path、volume serial/file ID，拒绝 ADS、device path、8.3/hardlink/reparse 别名漂移；二进制继续使用声明的 raw identity。 | 每类冲突具有单一负例和稳定失败 ID；dirty/deleted/untracked working tree、hardlink/短名称/ADS/reparse、句柄解析后 replace 和 mode/type 漂移均零写入失败；不得只做 HEAD blob 或文本 hash 比较。 |
| VCR-019 | P0 | promotion 写入前必须在重叠 write-set 排他锁内重新计算 authority identity、clarification event head、run status、exit attestation 和 write disposition，并与冲突检查输入比较。 | 检查后写入前改变权威输入，或并发 invalidate/reopen/supersede，promotion 均返回 stale 且零权威写入。 |
| VCR-020 | P0 | 任一冲突、stale、权限缺失或候选验证失败必须保证零权威文件写入，并追加不可变 promotion-attempt 证据。 | failure injection 检查权威文件哈希不变且失败记录完整。 |
| VCR-021 | P0 | 无冲突时，promotion 应先生成完整候选、验证全部预期投影，再通过 journaled transaction 集中应用。多文件 promotion 必须写入不可变 generation，并只通过单一原子 committed-generation pointer/manifest 切换可见性；全部机器消费者必须经 resolver 读取，无法门控的直接文件或人工消费者不得被声明具有 commit 前不可见保证。 | S0 枚举全部 authority reader；并发 reader 在每个逐文件故障点、全部 generation 写完但 pointer 未切换、pointer 切换前后、响应丢失和重试时只能观察完整 before 或完整 after generation，不能观察混合版本；未迁移的直接 reader 使该 promotion 失败关闭或降级为单对象原子提交。 |
| VCR-022 | P1 | 术语和 ADR 候选必须投影到仓库指定的正式所有者；不得默认创建根级 `CONTEXT.md`，不得采用外部简化 ADR 格式覆盖仓库规则。 | owner resolution fixture 证明无所有者时 fail-closed，有所有者时只修改声明路径。 |
| VCR-023 | P0 | promotion 只能授权写入，不能声明 plan-ready、phase-authorized、implementation-accepted 或 release-ready。 | 结果 envelope 的 `authorizes`/`does_not_authorize` 精确匹配该边界。 |
| VCR-024 | P0 | Skill 合规协议必须为新机制覆盖 no-guidance、supportive、neutral 和 competing 四级场景，覆盖上下文压缩、会话中断、历史改写诱导、提前写权威文件和冲突后强行 promotion。fresh-context 必须为 VCR-002/004/006 定义版本化 rubric、evaluator authority、允许模型、隔离方式、每级运行数和通过阈值；cross-model 是否为完成门必须显式配置。 | 缺少任一级场景、错误接受捷径、evaluator/rubric 不可信或 fresh-context 未运行/未达阈值时，对应语义 VCR 保持 `unverified` 且 Skill 不得完成；四级结果与 deterministic/package-level 证据分开报告。 |
| VCR-025 | P0 | `run_initialized` 必须冻结 clarification baseline authority manifest，并由首个及全部后继 checkpoint 绑定；baseline 只能随 successor run 更换。authority/source/owner/consumer closure 必须由版本化独立 producer 与 verifier 分别枚举，并与声明 registry 完全一致。 | promotion 时创建、替换或回填 baseline 均失败；manifest 绑定实际工作树身份、来源闭包、owner、validator 和适用二进制身份；删除任一 authority/source/owner/consumer 的 mutation fixture 使 producer/verifier/registry closure comparison 失败。 |
| VCR-026 | P0 | `compatible` 只能由版本化 owner-specific deterministic predicate 证明；LLM 合并理由只能作为候选证据，不能授权写入。 | predicate 未注册、证据不全、稳定 ID/owner/consumer/invariant 任一重叠不明时统一分类为 `conflicting`。 |
| VCR-027 | P0 | promotion 与全部 clarification mutation 必须共享 repository-canonical target mutation lock；固定锁序为 `canonical target lock -> sorted normalized authority write-set reservations`，并从最终 freshness 检查持续持有到 commit/abort 证据落盘。 | 双 promotion 互斥；promotion 持锁时 checkpoint/invalidate/reopen/supersede/restart 被阻塞；反向锁序、Windows 大小写别名和重叠 write set 均以稳定规则失败，不得只在写入后报告 stale。 |
| VCR-028 | P0 | promotion 必须具有唯一 promotion ID 和机器状态机 `prepared|reserved|committing|committed|blocked|recovery_required|aborted`，并定义每个状态的唯一 next action。每个 rollback/roll-forward 写操作必须执行逐文件 CAS：当前对象身份只能等于该事务记录的 before 或 after identity，第三种身份进入 manual recovery。 | 非法边、重复提交、提交后响应丢失、blocked 直接 committed 和 recovery-required 下继续写入均失败；故障后用户修改、文件对象替换或第三种 identity 不被恢复工具覆盖。 |
| VCR-029 | P0 | clarification event 必须使用版本化 canonical byte rule、自身 hash、长度、predecessor hash 和确定性 reducer；事件状态转换矩阵是机器权威。 | 事件重放必须重建同一 snapshot；未知事件、非法边、同 ID 异 payload、reducer version 漂移和尾部半写均失败。 |
| VCR-030 | P0 | 用户交互证据必须区分 `interaction-attested` 与 `trusted-user-identity`；protected-path approval 是由版本化信任根验证的独立、候选绑定、可过期且单次消费 capability。issuer registry 必须规定 producer verifier、签名/MAC 或受保护 runtime-event 身份、撤销 owner，以及 canonical path/risk class 所需 identity level；approval reservation/consumption 与 promotion ID 和 journal 原子绑定。 | schema 和 verifier 绑定 producer、actor/session/turn、canonical path set、candidate/before manifest hash、用途、issued/expiry、nonce、promotion ID、consumption 和 revocation；字段完整但 issuer/signature/event 伪造、identity downgrade、跨 promotion 复制及消费崩溃重试均失败，自报 `actor=user` 不构成可信身份。 |
| VCR-031 | P0 | append-only 规则必须定义敏感数据事故例外：漏检后发现 secret/PII 时立即 revoke/quarantine run，禁止恢复和 promotion，并通过安全删除或加密销毁移除敏感载荷。事故处置必须生成 sensitive-copy custody manifest，覆盖 event、snapshot、pending transition、candidate、transaction rollback/roll-forward 数据、temp、backup 和派生 sidecar。 | custody producer 与独立 verifier 对所有存储位置闭包一致；逐类注入敏感值后全部副本被处置，独立审计 sidecar 只保留不含原值的 hash、范围、原因和证明，后继数据不得继续复制敏感载荷。 |
| VCR-032 | P0 | legacy successor 必须绑定不可变 legacy bundle manifest 和规范 genesis projection；每次恢复重新验证旧身份。 | successor 建立后尾截断、替换、损坏或 adapter identity 改变均 quarantine，且不得 promotion。 |
| VCR-033 | P1 | canonical target registry 必须保存每个 run 的 committed event head、sequence 和 snapshot hash，用于检测完整尾部删除和短链回滚。 | 删除一个或多个完整 event/snapshot 后，内部自洽短链仍因 registry head 不匹配而失败；该机制只声明防崩溃、并发和普通误写，不冒充外部防篡改 custody。 |
| VCR-034 | P0 | 实施前必须生成版本化机器 requirements registry 和 source/consumer coverage，覆盖每个 VCR 的 source、delta、owner、first phase、consumer、acceptance ID、failure family、evidence intent 和 status；source/owner/consumer closure 由相互独立的 producer/verifier 从当前仓库枚举，不得只验证自报集合内部一致。 | registry/Markdown/producer/verifier 四方不一致、orphan VCR、重复 owner、遗漏 authority reader、未覆盖 acceptance 或 source hash 漂移时，S0 非零失败且不得进入行为实现。 |
| VCR-035 | P1 | 每个 `MODIFIED` VCR 必须逐项绑定被替换旧合同的 prior source path、稳定 locator、baseline Git tree/path/mode/blob 或 canonical identity、完整 replacement contract、受影响 consumer 和 acceptance；`ADDED` 不得伪装成 `MODIFIED`。 | S0 validator 拒绝缺少 prior provenance、baseline identity 不匹配、locator 不唯一、replacement 不完整或 consumer/acceptance 与控制注册表不一致的 `MODIFIED` 行。 |

### 4.1 实施阶段

| Phase | 所有权 | 退出条件 |
| --- | --- | --- |
| S0 | 需求注册表、prior provenance、独立 source/owner/consumer closure、当前实际工作树 manifest、schema、状态机、RED fixtures | VCR-034/035 registry、provenance 和 producer/verifier closure 通过；HEAD/index/working-tree/Windows file-object identity 与 source hash 已冻结；至少一个新增负例以预期稳定规则 ID 失败。 |
| S1 | CQ 分类、依赖批次、场景、术语和 ADR 候选合同 | 确定性结构门通过，语义质量仅报告为 fresh-context 证据。 |
| S2 | append-only event、checkpoint、snapshot、reducer、head registry 和恢复 | 并发、幂等、崩溃、短链回滚、无聊天恢复和旧事件不变测试通过。 |
| S3 | baseline、冲突分类、trusted approval、统一锁域、committed-generation resolver 和可 CAS 恢复 transaction | 所有冲突、TOCTOU、伪造/重放 approval、双 promotion、并发直接 reader、第三方文件修改和逐故障点 transaction 负例通过。 |
| S4 | legacy/restart successor transaction 与敏感数据事故处置 | predecessor/successor 每个故障点、legacy drift、quarantine、sensitive-copy closure、安全删除/加密销毁和禁止恢复/promotion 测试通过。 |
| S5 | Skill 合规、文档投影和完整验证 | deterministic/package、fresh-context、cross-model 证据分层报告；fresh-context rubric/threshold 完成门通过；现有回归与新增 mutation fixtures 全部通过。 |

后续阶段不得绕过前序阶段。尤其 S0 未通过时，不得修改 `clarification_state.py` 的行为路径或新增 promotion 实现。

### 4.2 规范需求控制注册表种子

本节是后续机器 `requirements registry` 的规范种子。所有行的 approved source 均为本文件第 1-2 节冻结的 `INTENT-KERNEL-VCR-20260721`；evidence intent 均为执行对应 acceptance ID 的正例、单规则负例和适用 mutation 后产生的当前 hash-bound 结果；status 均为 `approved`。机器 registry 必须逐行保留这些绑定，不得从表格标题或自然语言推断。

| ID | Accountable owner | First phase | Affected consumers | Acceptance ID | Failure family | Delta |
| --- | --- | --- | --- | --- | --- | --- |
| VCR-001 | `references/clarification-gate.md` | S1 | Agent question rounds, `record-round` | VCR-A001 | batch-dependency | MODIFIED |
| VCR-002 | `scripts/clarification_state.py` | S1 | CQ schema, Agent discovery | VCR-A002 | question-classification | ADDED |
| VCR-003 | `scripts/clarification_state.py` | S1 | CQ schema, round validator | VCR-A003 | dependency-order | ADDED |
| VCR-004 | `references/clarification-gate.md` | S1 | Agent questioning, compliance evaluator | VCR-A004 | scenario-applicability | ADDED |
| VCR-005 | `scripts/clarification_state.py` | S1 | checkpoint, recovery, promotion | VCR-A005 | term-candidate | ADDED |
| VCR-006 | `references/clarification-gate.md` | S1 | Agent decisions, ADR projection | VCR-A006 | adr-candidate | ADDED |
| VCR-007 | `scripts/clarification_state.py` | S2 | user-turn checkpoint, recovery | VCR-A007 | checkpoint-durability | MODIFIED |
| VCR-008 | `scripts/clarification_state.py` | S2 | event store, audit | VCR-A008 | history-immutability | MODIFIED |
| VCR-009 | `scripts/clarification_state.py` | S2 | event writer, retry caller | VCR-A009 | transition-idempotency | MODIFIED |
| VCR-010 | `scripts/clarification_state.py` | S2 | snapshot writer, recovery | VCR-A010 | snapshot-lineage | ADDED |
| VCR-011 | `scripts/clarification_state.py` | S2 | new-session recovery, Agent | VCR-A011 | context-recovery | MODIFIED |
| VCR-012 | `scripts/clarification_state.py` | S2 | event/snapshot/candidate writers | VCR-A012 | data-minimization | MODIFIED |
| VCR-013 | `scripts/clarification_state.py` | S2 | concurrent checkpoint writers | VCR-A013 | checkpoint-concurrency | MODIFIED |
| VCR-014 | `scripts/clarification_state.py` | S2 | invalidate/reopen/supersede/restart | VCR-A014 | additive-lineage | MODIFIED |
| VCR-015 | `scripts/clarification_state.py` | S4 | legacy runs, recovery adapter | VCR-A015 | legacy-migration | MODIFIED |
| VCR-016 | `scripts/clarification_promotion.py` | S3 | promotion caller, protected paths | VCR-A016 | authorization-binding | MODIFIED |
| VCR-017 | `scripts/clarification_promotion.py` | S3 | conflict classifier, authority writers | VCR-A017 | three-way-conflict | ADDED |
| VCR-018 | `scripts/clarification_promotion.py` | S3 | identity resolver, owner resolver | VCR-A018 | authority-identity | ADDED |
| VCR-019 | `scripts/clarification_promotion.py` | S3 | promotion reservation, authority writers | VCR-A019 | promotion-freshness | ADDED |
| VCR-020 | `scripts/clarification_promotion.py` | S3 | promotion failure evidence | VCR-A020 | zero-write-failure | ADDED |
| VCR-021 | `scripts/clarification_promotion.py` | S3 | multi-file authority commit, recovery | VCR-A021 | promotion-transaction | ADDED |
| VCR-022 | `scripts/clarification_promotion.py` | S3 | term/ADR/plan projection owners | VCR-A022 | owner-resolution | ADDED |
| VCR-023 | `scripts/clarification_promotion.py` | S3 | promotion result consumers | VCR-A023 | authorization-boundary | ADDED |
| VCR-024 | `scripts/validate_skill_contract.py` | S5 | compliance scenarios, release evaluator | VCR-A024 | scenario-level-coverage | MODIFIED |
| VCR-025 | `scripts/clarification_state.py` | S0 | checkpoint, promotion baseline consumer | VCR-A025 | baseline-lineage | ADDED |
| VCR-026 | `scripts/clarification_promotion.py` | S3 | compatible classifier, owner predicates | VCR-A026 | semantic-merge-authority | ADDED |
| VCR-027 | `scripts/clarification_promotion.py` | S3 | concurrent promotions and state writers | VCR-A027 | write-set-concurrency | ADDED |
| VCR-028 | `scripts/clarification_promotion.py` | S3 | transaction journal, recovery | VCR-A028 | promotion-state | ADDED |
| VCR-029 | `scripts/clarification_state.py` | S0 | event writer, reducer, validator | VCR-A029 | event-state | ADDED |
| VCR-030 | `scripts/clarification_promotion.py` | S3 | exit/approval producers and consumers | VCR-A030 | identity-attestation | ADDED |
| VCR-031 | `scripts/clarification_state.py` | S4 | evidence custody, recovery, promotion | VCR-A031 | sensitive-incident | ADDED |
| VCR-032 | `scripts/clarification_state.py` | S4 | legacy adapter, successor event | VCR-A032 | legacy-anchor | ADDED |
| VCR-033 | `scripts/clarification_state.py` | S2 | target registry, recovery | VCR-A033 | tail-rollback | ADDED |
| VCR-034 | `scripts/validate_skill_contract.py` | S0 | all implementation and validation phases | VCR-A034 | requirement-closure | ADDED |
| VCR-035 | `scripts/vdd-clarification-requirements.v1.json` | S0 | requirements registry producer/verifier, all modified requirement owners | VCR-A035 | prior-provenance | ADDED |

### 4.3 `MODIFIED` 旧合同 provenance

以下绑定使用本文件头部的 reviewed baseline commit；Git identity 格式为 `mode/blob`。每个当前 VCR 行是对应旧合同的完整 replacement contract，不是只覆盖局部句子的补丁；受影响 consumer 与 acceptance 以 4.2 同 ID 行为准。S0 机器 registry 必须逐项复制并验证这些绑定。

| ID | Prior source path | Stable prior locator | Baseline Git identity | Replacement |
| --- | --- | --- | --- | --- |
| VCR-001 | `.agents/skills/vdd-execution-plan/references/clarification-gate.md` | `Question rounds` | `100644/b42a5de017045a7581820d13867d95e344f51147` | VCR-001 全行 |
| VCR-007 | `.agents/skills/vdd-execution-plan/scripts/clarification_state.py` | `command_record_round` + `_commit_state_and_event` | `100644/d37256aea90921008b133763009ea8ac36846377` | VCR-007 全行 |
| VCR-008 | `.agents/skills/vdd-execution-plan/scripts/clarification_state.py` | `_append_event` + `_commit_state_and_event` | `100644/d37256aea90921008b133763009ea8ac36846377` | VCR-008 全行 |
| VCR-009 | `.agents/skills/vdd-execution-plan/scripts/clarification_state.py` | `_commit_state_and_event` + `_recover_pending_transition` | `100644/d37256aea90921008b133763009ea8ac36846377` | VCR-009 全行 |
| VCR-011 | `.agents/skills/vdd-execution-plan/references/clarification-gate.md` | `Persistence and recovery` | `100644/b42a5de017045a7581820d13867d95e344f51147` | VCR-011 全行 |
| VCR-012 | `.agents/skills/vdd-execution-plan/scripts/clarification_state.py` | `_sensitive_paths` + `validate_state_data` | `100644/d37256aea90921008b133763009ea8ac36846377` | VCR-012 全行 |
| VCR-013 | `.agents/skills/vdd-execution-plan/scripts/clarification_state.py` | `_target_lock` + `_locked_state_command` | `100644/d37256aea90921008b133763009ea8ac36846377` | VCR-013 全行 |
| VCR-014 | `.agents/skills/vdd-execution-plan/scripts/clarification_state.py` | `command_invalidate` + `command_reopen` + `command_supersede` | `100644/d37256aea90921008b133763009ea8ac36846377` | VCR-014 全行 |
| VCR-015 | `.agents/skills/vdd-execution-plan/references/clarification-gate.md` | `Create and repair behavior` + `Persistence and recovery` | `100644/b42a5de017045a7581820d13867d95e344f51147` | VCR-015 全行 |
| VCR-016 | `.agents/skills/vdd-execution-plan/references/clarification-gate.md` | `Confidence and exit` + `Write boundary` | `100644/b42a5de017045a7581820d13867d95e344f51147` | VCR-016 全行 |
| VCR-024 | `.agents/skills/vdd-execution-plan/references/skill-compliance-protocol.md` | `Scenario levels` + `Evidence levels` + `Release checklist` | `100644/a871ce695280743f14a99530ee7a85813b2fb6a2` | VCR-024 全行 |

### 4.4 证据等级

- `deterministic/package-level` 可以证明 schema、字段、hash、依赖顺序、状态转换、已声明 discovery 命中、registered predicate、失败行为和 mutation rejection。
- `fresh-context` 才能观察 Agent 是否真正主动发现事实、提出有价值的场景、正确识别术语歧义和 ADR 候选。
- `cross-model` 证明多个允许模型上的稳定性，不能由单模型 fresh-context 结果推断。
- VCR-002、VCR-004 和 VCR-006 的确定性 PASS 只授权结构合同有效；不得声明对应语义行为已经可靠。
- VCR-016 至 VCR-023、VCR-025 至 VCR-030 的 authorizing gate 只能消费确定性、当前 hash-bound 证据；LLM candidate 或合并理由不能直接授权 promotion。
- fresh-context evaluator 配置必须绑定 rubric version、evaluator owner/version、允许模型、隔离级别、场景运行数、随机性参数、pass threshold 和原始 run identities。VCR-002/004/006 任一未达阈值时保持 `unverified`，S5 和 Skill 完成门失败。
- cross-model 默认是观察性稳定性证据，不构成完成门；只有机器配置显式启用、冻结模型集合与阈值后才可升级为完成门，且不得替代 fresh-context。

## 5. 澄清事件与快照合同

### 5.1 Run 初始化基线

`run_initialized` 在任何用户回合 checkpoint 前冻结 clarification baseline authority manifest。manifest 至少包含：

- canonical target、repository root 和 run identity；
- 全部 authority/source/owner/consumer 路径；
- Git HEAD tree entry、规范化 path、mode、blob、index stage，以及 working-tree 的 lstat/type/mode/raw SHA-256、UTF-8/LF canonical hash、byte length 和 dirty/deleted/untracked 状态；
- Windows normalized final path、volume serial、file ID、link count 和 reparse identity；ADS、device path、8.3/hardlink/reparse 别名必须归并到同一对象或失败关闭；
- 非 Git 文本的 raw hash、UTF-8/LF canonical hash 和长度；
- 二进制的 raw SHA-256 和 byte length；
- schema、validator、reducer 和 owner-registry identity；
- manifest 自身的 canonical hash。

manifest closure 由相互独立、版本化的 producer 和 verifier 从仓库 authority routing、owner registry、调用点及 reader inventory 分别生成；声明集合、producer 集合和 verifier 集合必须完全一致。首个和全部后继 checkpoint 必须绑定同一 baseline hash。authority 在澄清期间发生变化时只能 invalidate 当前 run 或创建 successor；不得在 promotion 时以 current authority 重建 baseline。

### 5.2 事件是恢复权威

实现可以选择不可变单事件文件，或能够证明旧记录字节不变的追加日志。无论物理布局如何，必须满足：

- 事件按 canonical target 和 run 隔离。
- 每个事件绑定前序事件，形成单一可验证链。
- 每个事件绑定 schema version、canonical byte rule、自身 hash、raw/canonical length、transition ID 和 canonical payload hash。
- 已提交事件永久不可变。
- 投影缓存可重建，不得成为比事件链更高的权威。
- 损坏或不完整的尾部提交必须恢复或隔离，不能静默跳过。
- canonical target registry 通过与事件提交相同的 pending/recovery 协议保存 committed head、sequence 和 snapshot hash；恢复必须先比较 registry anchor。

事件至少表达以下类型：

```text
run_initialized
user_turn_checkpointed
round_recorded
boundary_confirmed
term_candidate_recorded
decision_candidate_recorded
question_invalidated
question_reopened
clarification_closed
run_superseded
promotion_started
promotion_blocked
promotion_committed
```

一个物理 checkpoint 可以携带同一用户回合产生的多个逻辑变化，但必须保持稳定子项身份，保证重放和幂等。

同一 transition ID 的重试必须先比较 canonical payload hash：相同则返回原提交身份，不同则在写 `state`、event、snapshot 或 registry 前失败。调用方必须从稳定的 run/user-turn/operation identity 派生或保存 transition ID，响应丢失后不得生成新 ID 重放同一逻辑操作。

### 5.3 状态转换矩阵

机器 schema 必须拥有完整转换矩阵，至少约束：

```text
active -> closed | invalidated | superseded
invalidated -> active only through explicit reopen when no sibling active run exists
closed -> invalidated | promotion-prepared
superseded -> terminal

promotion-prepared -> promotion-reserved | promotion-blocked | promotion-aborted
promotion-reserved -> promotion-committing | promotion-blocked | promotion-aborted
promotion-committing -> promotion-committed | promotion-recovery-required
promotion-blocked -> clarification-invalidated or promotion-aborted
promotion-recovery-required -> promotion-committed | promotion-aborted | manual-recovery
promotion-committed -> terminal
```

`promotion-blocked` 不得直接进入 `promotion-committed`。发生语义冲突时，必须追加 invalidation 和受影响 CQ reopen 事件后才能再次关闭澄清。每条 transition 只有一个 owner，非法边必须具有独立稳定规则 ID。

### 5.4 快照是派生恢复投影

每个版本化快照至少包含：

- run、target、mode 和 interaction mode；
- event head、checkpoint sequence 和 predecessor；
- 当前 authority/target hashes；
- 已确认范围、非目标、约束和兼容边界；
- 全部稳定 CQ 的当前 disposition 和依赖；
- 已确认术语、场景和决策候选；
- open/blocking items、confidence 和 deductions；
- 当前退出状态、write disposition 和 next allowed action；
- 快照自身的 schema version 和 canonical hash。
- reducer identity、baseline manifest hash 和 committed target-registry head。

允许额外生成便于人类恢复的 Markdown 视图，但 Markdown 只能从机器快照生成，不能成为独立权威。

恢复时必须从 genesis/baseline 重放事件并独立重算 snapshot。saved snapshot、replayed snapshot 与 target registry head 任一不一致时 quarantine；不得选择其中一个继续运行。

## 6. Promotion 冲突模型

### 6.1 输入

一次 promotion 冻结以下输入：

- clarification baseline authority manifest；
- 当前 authority manifest；
- 最终有效 clarification snapshot；
- 目标文件所有者和允许写入集合；
- repository root、Git tree/path/mode/blob 和适用的二进制身份；
- 当前用户退出交互证据、所需身份等级和 protected-path approval；
- promotion validator/rule version。
- clarification event head、run status、exit attestation、write disposition 和 canonical write set；
- promotion ID、transaction manifest 和 compatible predicate registry。

promotion reservation 先获取 repository-canonical target mutation lock，再按稳定顺序获取 normalized authority write-set reservations。checkpoint、invalidate、reopen、supersede、restart 和 promotion 必须使用同一 target lock owner；禁止反向锁序。路径先做 repository-root、Windows 大小写、final-handle、volume/file-ID、ADS/device/8.3/hardlink/reparse 和规范化检查；任意对象别名或重叠路径互斥。锁必须覆盖最终 freshness 重算、候选验证、所有权威写入及 commit/abort 证据落盘，并在每个 replace 前重新验证最终句柄身份。

protected-path approval 与普通澄清退出授权分离。approval 至少绑定 producer/actor/session/turn attestation、canonical path set、candidate hash、before manifest hash、用途、issued/expiry、nonce、promotion ID、single-use consumption 和 revocation state。版本化 issuer registry 必须把每个 producer 绑定到可信 verifier、签名/MAC key identity 或受保护 runtime-event identity，并机器映射 canonical path/risk class 所需 identity level。approval reservation 与 consumption 是 promotion journal 的状态转换：相同 promotion ID 只能恢复原事务，不同 promotion ID 不能消费已 reservation/consumed capability。候选、路径、before manifest、issuer trust 或所需身份等级变化后不可复用旧 approval。

### 6.2 三方分类

每个拟投影项必须分类为：

| 分类 | 含义 | 行为 |
| --- | --- | --- |
| unchanged | 当前权威与澄清基线一致 | 可以应用澄清增量 |
| compatible | 当前权威已变化，但与澄清增量不冲突 | 记录合并理由后可以应用 |
| conflicting | 当前权威与澄清增量对同一语义给出不兼容结论 | 零写入并重新打开受影响 CQ |
| stale | 路径、身份、所有者、权限或输入在检查后发生变化 | 零写入并要求重新执行 promotion |
| missing-owner | 无法解析正式权威所有者 | 零写入并要求上游决定 |

文本不重叠不能单独证明 `compatible`。语义所有者、稳定 ID、术语定义、决策 disposition、非目标和消费者必须同时检查。

`compatible` 的自动判定仅限 registered owner-specific predicate 能确定性证明的情况。predicate result 至少绑定 item stable IDs、owner、consumer closure、invariant/delta comparison、rule/version、输入 hashes 和反例结果。没有注册规则、证据不完整、存在语义重叠或判定不确定时必须归类为 `conflicting`；LLM 只能生成待验证候选。

### 6.3 提交与恢复

- promotion 必须先在目标外构建完整候选和 manifest。
- 候选验证通过后才能进入权威提交。
- 写入前执行最终身份比较。
- 提交结果必须绑定 before/after manifest、clarification event head 和 validator identity。
- 发生部分文件系统故障时，恢复工具必须能判定未提交、已提交或需要人工恢复，不能把未知状态报告为成功。
- 所有失败尝试保留为新增 sidecar，不得覆盖历史失败。

多文件候选写入 transaction-scoped immutable generation；唯一 commit point 是对 committed-generation pointer/manifest 的单对象原子切换。所有机器 authority reader 必须通过 hash-bound resolver 取得 generation，并验证 `promotion_committed`、after manifest 和 pointer 三者一致。无法迁移的直接文件或人工 reader 必须在 consumer manifest 中明确登记为不具备事务可见性，且其存在会阻止多文件 promotion，除非 owner 将 write set 收敛为可原子替换的单一对象。不得依赖先逐个覆盖规范路径、再追加 sidecar 来声称原子可见。

transaction manifest 至少绑定 promotion ID、snapshot/event head、baseline/current/candidate/write-set/generation/pointer hashes、逐文件 before/after identity、写入顺序、rollback/roll-forward 数据、validator identity 和唯一 commit point。`committing` 或 `recovery_required` 必须 fail-closed。

每个故障点必须有唯一恢复决策：确定性 roll-forward、恢复完整 before manifest，或进入阻断所有后续写入的 manual recovery。每个恢复写操作必须先 CAS 比较当前 final-handle identity：只接受该事务记录的 before 或 after identity；任何第三种 identity 都不得被覆盖并立即进入 manual recovery。重试同一 promotion ID 应返回或完成原事务；不得重复应用澄清 delta。

## 7. 兼容与迁移

1. 已存在的 active、closed、invalidated 和 superseded runs 必须保持可读。
2. 不允许批量改写现有 `events.jsonl`、`state.json` 或历史 run。
3. 如新实现采用不同物理布局，应通过 successor checkpoint 或只读适配器接续旧 run；首个 migration event 绑定 legacy bundle 中每个文件的 raw SHA-256、长度、schema、adapter version、规范 genesis projection 和 predecessor。
4. 稳定 `CQ-NNN`、双重退出授权、五维置信度、问题数量规则、headless fail-closed 和 stale hash 行为保持兼容。
5. 旧调用方继续使用 `record-round` 时，要么获得兼容行为，要么收到明确、版本化、可恢复的迁移错误；不得静默丢失逐用户回合 checkpoint。
6. successor 建立后，每次恢复都重新验证 legacy bundle；尾截断、替换、损坏或 adapter identity 漂移必须 quarantine，并禁止 clarification resume 与 promotion。
7. legacy 只读适配器只能产生派生 projection，不能向旧文件回写 migration marker。
8. restart 使用 target-registry-owned pending successor transaction：先持有 canonical target lock，冻结 predecessor committed head、successor ID、successor genesis/baseline 和目标 active pointer，再幂等完成 predecessor 终结、successor 初始化和 pointer 切换。任一故障点恢复同一 transaction，不允许生成第二个 successor，也不允许留下无法恢复的 terminal predecessor。

## 8. 失败行为

以下情况必须失败关闭：

- 事件序号重复、缺口、分叉或 predecessor 不匹配；
- 尝试修改、删除或重排历史事件；
- snapshot 无法从事件链验证；
- target registry head 与有效短链不一致；
- 用户回答已被用于继续推理但 checkpoint 尚未成功持久化；
- 事实、决定、场景或术语候选携带禁止字段或敏感值；
- clarification exit 无效、已 stale 或来自 headless/model actor；
- promotion 输入与当前 authority/target/Git identity 不一致；
- 冲突检查无法解析正式所有者或保护审批；
- 候选验证失败或多文件提交状态未知。
- 同 transition ID 携带不同 canonical payload；
- promotion reservation 期间 clarification head、退出状态、审批或 write set 漂移；
- legacy bundle 或 adapter identity 在 successor 建立后漂移；
- source/owner/consumer closure producer、verifier 与声明 registry 不一致；
- Git index/working tree 或 Windows final file identity 与 manifest 不一致；
- approval issuer/signature/runtime event 不可信、identity level 降级，或 capability 被其他 promotion ID reservation/consumed；
- committed-generation pointer、commit event、after manifest 或 resolver 结果不一致；
- rollback/roll-forward 遇到不等于事务 before/after identity 的第三方修改；
- restart predecessor/successor transaction 不完整或出现多个 successor；
- sensitive-copy custody manifest 无法证明所有派生副本已处置；
- fresh-context rubric/threshold 未冻结、证据未运行或 VCR-002/004/006 未达阈值；
- 任一 `MODIFIED` VCR 缺少或漂移 prior provenance。

checkpoint 失败后，Agent 不得继续下一轮澄清；它必须先恢复、重试幂等 transition，或报告持久化 blocker。

历史不可变规则仅面向正常运行、崩溃、并发和普通误写，不声明抵御拥有证据根写权限的恶意管理员。若漏检后发现 secret 或个人数据，安全处置优先于普通不可变规则：立即 revoke/quarantine run，阻断恢复和 promotion，停止后继复制，并安全删除敏感载荷或销毁其独立加密密钥。处置前由 custody producer 枚举 event、snapshot、pending transition、candidate、transaction recovery data、temp、backup 和派生 sidecar，处置后由独立 verifier 重新枚举并证明闭包。只允许在独立 sidecar 保留不含原值的 hash、范围、原因、处置方式和审计身份。

## 9. 最低测试与负例

实施至少增加以下验证：

1. 五题批量 round 正例和依赖子问题提前进入负例。
2. 每次用户回合即时 checkpoint，进程中断后无聊天恢复；fresh process 从事件重放重算 snapshot。
3. 新 checkpoint 不改变任何旧事件或旧快照 hash；删除完整尾部后 target registry head 检测短链回滚。
4. 重复 transition、同 ID 异 payload、响应丢失重试、并发 writer、大小写不同 target 路径和 pending-transition 恢复。
5. 术语冲突、模糊术语消歧、具体场景探针和 ADR 候选 disposition；分别断言 deterministic 与 fresh-context 证据边界。
6. sensitive field/value 在 event、snapshot、term 和 decision candidate 中的拒绝。
7. 敏感数据漏检后发现的 revoke/quarantine、安全删除或加密销毁、禁止后继复制和禁止 promotion；对 event、snapshot、pending、candidate、transaction recovery、temp、backup 和 sidecar 逐类注入，并验证 custody producer/verifier 闭包。
8. legacy run 只读兼容和 successor checkpoint；successor 后 legacy 尾截断、替换、损坏及 adapter 漂移负例；restart 在 predecessor 终结、successor 初始化和 active pointer 切换各故障点幂等恢复唯一 successor。
9. 三方冲突检查的 unchanged、registered-compatible、unregistered/ambiguous-compatible、conflicting、stale 和 missing-owner 分支。
10. check 后 authority 或 clarification event head 改变的 TOCTOU 负例；双 promotion；promotion 持 target/write-set locks 时并发 checkpoint/reopen/invalidate/supersede/restart 被阻塞；反向锁序被拒绝。
11. promotion 冲突、候选验证失败和中途故障的零权威写入证明；immutable generation 各写入点和 pointer 切换前后崩溃、响应丢失和幂等重试；并发 resolver 只能读取完整 before 或 after。
12. promotion state machine 每条合法边的正例和每条非法边的单规则负例；rollback/roll-forward 在 before、after、第三方 identity 下分别验证 CAS 决策。
13. interaction-attested、trusted-user-identity、伪造 actor/issuer/signature/runtime event、identity downgrade、跨 session/turn/promotion 重放、审批过期/撤销/候选不匹配，以及 reservation/consumption 各故障点。
14. run 初始化 baseline manifest、首 checkpoint 绑定、澄清中 authority 漂移和 promotion 时重建 baseline 的拒绝；dirty/deleted/untracked working tree、index stage、hardlink/8.3/ADS/device/reparse/final-handle replace 身份负例。
15. requirements registry/source coverage 的完整性、owner 唯一性、acceptance 覆盖和 source hash freshness；独立 closure producer/verifier/声明集合三方比较及逐成员 deletion mutation；所有 `MODIFIED` 行的 prior provenance mutation。
16. promotion 成功结果只授权写入，不越权声明更高 VDD 状态。
17. fresh-context no-guidance、supportive、neutral、competing 四级场景；冻结 rubric/evaluator/model/run count/threshold，验证未运行、低于阈值和 evaluator identity 漂移均阻止 VCR-002/004/006 与 Skill 完成；分别报告 deterministic/package、fresh-context 与 cross-model 证据等级。

## 10. 预期影响面

后续实施预计至少检查并按需修改：

- `.agents/skills/vdd-execution-plan/SKILL.md`
- `.agents/skills/vdd-execution-plan/references/clarification-gate.md`
- `.agents/skills/vdd-execution-plan/references/strict-vdd-standard.md`
- `.agents/skills/vdd-execution-plan/references/skill-compliance-protocol.md`
- `.agents/skills/vdd-execution-plan/scripts/clarification_state.py`
- `.agents/skills/vdd-execution-plan/scripts/clarification_promotion.py`（预期新增 owner；最终路径由 S0 registry 冻结）
- `.agents/skills/vdd-execution-plan/scripts/skill-contract.json`
- `.agents/skills/vdd-execution-plan/scripts/vdd-clarification-requirements.v1.json`（预期新增机器 registry）
- `.agents/skills/vdd-execution-plan/scripts/schemas/clarification-event.v2.schema.json`（预期新增或等价 owner）
- `.agents/skills/vdd-execution-plan/scripts/schemas/clarification-promotion.v1.schema.json`（预期新增或等价 owner）
- `.agents/skills/vdd-execution-plan/scripts/schemas/clarification-approval.v1.schema.json`（预期新增或等价 trusted approval owner）
- `.agents/skills/vdd-execution-plan/scripts/clarification_authority_resolver.py`（预期新增或等价 committed-generation resolver owner）
- `.agents/skills/vdd-execution-plan/scripts/clarification_closure.py`（预期新增或等价 producer/verifier owner；两种角色必须保持实现与证据独立）
- `.agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py`
- `.agents/skills/vdd-execution-plan/scripts/fixtures/clarification-state-pass.json`
- `.agents/skills/vdd-execution-plan/scripts/fixtures/clarification-cases.json`
- `.agents/skills/vdd-execution-plan/scripts/tests/test_clarification_state_concurrency.py`
- `.agents/skills/vdd-execution-plan/scripts/tests/test_clarification_promotion.py`（预期新增或等价测试 owner）
- `.agents/skills/vdd-execution-plan/scripts/tests/test_validate_skill_contract.py`
- `.agents/skills/vdd-execution-plan/agents/openai.yaml`

该列表是影响面下限，不是实施授权或完整 change set。后续实施必须先做当前文件和调用方清单，再按测试优先顺序确定实际修改集合。

## 11. 完成定义

本次机制更新只有在以下条件全部满足时才可声明完成：

- VCR-001 至 VCR-035 均与机器 requirements registry 双向一致，并具有唯一实现所有者、first phase、consumer、acceptance ID、failure family、source/delta/status 和当前验收证据；每个 `MODIFIED` 行的 prior provenance 与 reviewed baseline commit 精确匹配；
- S0 冻结的 source/owner/consumer/baseline manifest 经独立 producer/verifier 证明闭包一致，并与当前 HEAD/index/working-tree、Windows final file-object、非 Git canonical、binary 和 validator identity 一致；
- 每次用户澄清回合都形成可恢复、幂等、增量且不改写历史的 checkpoint；
- 新会话不依赖聊天摘要即可恢复共同理解和下一允许动作；
- event replay、saved snapshot 和 target registry committed head 三方一致，短链回滚不能静默通过；
- 批量 CQ 行为保持，未退化为强制逐题推进；
- 术语、场景和 ADR 只形成候选，澄清期间零正式权威写入；
- baseline 在 run 初始化时冻结且不可由 promotion 重建；`compatible` 只由 registered deterministic predicate 授权；
- promotion 使用统一 target/write-set 锁序；三方冲突检查、clarification-head freshness、trusted 候选绑定审批、approval 原子消费、transaction state machine、immutable generation、原子 committed pointer、resolver reader isolation、恢复 CAS 和零未授权部分可见均通过负例；
- legacy successor 锚点、restart 原子 successor transaction、持续 recheck、quarantine 和 sensitive-copy custody 闭包均通过故障测试；
- 现有 clarification gate、敏感数据、并发、stale、headless 和退出授权测试全部继续通过；
- `validate_skill_contract.py`、Skill 单元测试和新增 mutation fixtures 针对当前 hash 全部通过；
- package-valid、contract-valid、fixture-behavior、fresh-context 和 cross-model 证据等级分别报告，不把前三级冒充后两级；四级 compliance scenario 缺一不可完成；VCR-002/004/006 fresh-context 未运行或未达冻结阈值时保持 `unverified` 且 Skill 不得完成。
