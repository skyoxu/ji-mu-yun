# TC-D1 PRD 独立对抗性评审

**总体结论：FAIL。**

**PRD 决策就绪度：75%，合理区间 70%–80%。** 此数值衡量需求保真、验收语义明确程度及下游能否据此得到一致设计；不是 08-05 实现完成度，也不按篇幅、测试数或日志数计算。主要能力方向已经完整，但若直接据此冻结 Spec/Architecture，仍可能合法地产生范围不同、信任边界不同、成功判据不同的实现。

- 评审日期：2026-09-11。
- 仓库：skyoxu/ji-mu-yun。
- 候选分支：fix/08-05-real-skill-replay。
- 唯一受评候选提交：`d655848c69aa5e11b69ef88e25f7d9f34bb756a7`。
- Git tree：`cfb3041a3806ba963f96c51e4c9f7d9d23a754af`。
- authorizes: []。
- 处置状态：本报告全部 finding 均为 OPEN；未修改 PRD、addendum、source brief、历史执行计划、既有评审或代码。
- 本报告是独立内容评审，不是 bmad-review 工作流运行回执，也不发布 implementation-complete 或 acceptance-passed。

## 1. 范围、证据和限制

全文读取 PRD、addendum、source brief、旧 requirements、implementation-contract、ADR-0058、ADR-0060 及指定 Q8；核对 AGENTS.md 与 Toolchain workflow index。另读取本提交四份内置 review/reconciliation 报告，目的仅是比较遗漏；没有继承其结论。对照读取当前 replay CLI、capability descriptor、Acceptance Skill 入口与 Q8 terminal-input。

获取候选完整 Git tree，确认未截断；主要九份实际存在的输入均通过 Git blob 内容校验。未启动 Quick Dev、VDD、Acceptance、live backend 或 Windows 测试。本次对抗案例是从条文推导的可绕过路径，不冒充已执行的动态测试。FastCtx 未挂载，仓库读取使用固定提交的 GitHub 接口；本地仅整理评审资料。

**输入缺失：`docs/fix80501.txt` 不在候选提交完整 Git tree 中。** 无法完成对此文件原始字节的逐条 reconciliation；不以对话中的旧评审摘要替代文件。缺失限制不妨碍成立下面由实际 PRD 和其他上游直接支持的 findings，但不允许声称已穷尽所有上游要求。

固定源链接：

- [P：prd.md](https://github.com/skyoxu/ji-mu-yun/blob/d655848c69aa5e11b69ef88e25f7d9f34bb756a7/_bmad-output/planning-artifacts/prds/prd-jimuyun-2026-09-11/prd.md)
- [A：addendum.md](https://github.com/skyoxu/ji-mu-yun/blob/d655848c69aa5e11b69ef88e25f7d9f34bb756a7/_bmad-output/planning-artifacts/prds/prd-jimuyun-2026-09-11/addendum.md)
- [S：source brief](https://github.com/skyoxu/ji-mu-yun/blob/d655848c69aa5e11b69ef88e25f7d9f34bb756a7/docs/know-tc-d1-rebuild.md)
- [R：历史 requirements](https://github.com/skyoxu/ji-mu-yun/blob/d655848c69aa5e11b69ef88e25f7d9f34bb756a7/execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/requirements.v1.json)
- [C：历史 implementation-contract](https://github.com/skyoxu/ji-mu-yun/blob/d655848c69aa5e11b69ef88e25f7d9f34bb756a7/execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/implementation-contract.v1.json)
- [ADR-0058](https://github.com/skyoxu/ji-mu-yun/blob/d655848c69aa5e11b69ef88e25f7d9f34bb756a7/docs/adr/ADR-0058-toolchain-skill-replay-portability-and-evaluation-seeds.md)
- [ADR-0060](https://github.com/skyoxu/ji-mu-yun/blob/d655848c69aa5e11b69ef88e25f7d9f34bb756a7/docs/adr/ADR-0060-skill-input-selection-generation-and-retention.md)

下文 P/A/S 均指以上完整路径；行号按该提交文本计算，不指向会移动的分支 HEAD。

| 产物 | Git blob | SHA-256 |
| --- | --- | --- |
| P | 3a5017627d318a58cc338b1a2b83bff6a60372a3 | be839696e4f4dfdffd44b28da5f77b354858fba9fe0c9a5597f88d215863fefc |
| A | dc8697769b746bdd84f0c110d42fd17e9163002c | 4659f495bbe871f7b2432ced4421a79b592f5966d57f9fdd77ddfe97ab5f56c4 |
| S | 110039fab41e5d199df5288fcf19a3741368c84f | c295de91b8224894c724758dbf865ab4f708a6bc7f0f433f8712755921fd89b7 |

## 2. Findings

共 13 项：Critical 0、High 8、Medium 5、Low 0。High 阻塞下游规范基线；Medium 中涉及权限、上游保真和验收覆盖的部分也应在 PRD 修订时关闭。

### H1 — High：Semantic Dependency 被错误收窄为冻结 Probe 集的依赖

**位置：P 105–106、144–154、303–309。**

**问题：** 术语只纳入“字节变化能改变 frozen Probe set verdict”的输入。它排除了仅影响其他受支持目标、矩阵场景、消费者或诊断语义的依赖。PRD 对 Snapshot 的“所有决定结果的输入”没有消除这个定义冲突，也没有要求能力身份覆盖未被 Probe 激活的语义路径。

**对抗案例：** 一个策略文件只影响知识读取集场景，不影响通用正反 Probe。实现可以据定义不将其纳入 Validator Capability 身份；策略替换后两 Probe 仍通过，却改变真实目标或场景判断。

**影响：** Spec 可能选择“Probe 实际触达集合”，Architecture 可能选择“全部能力语义闭包”，两者不能等价验收。有限测试集不能定义全部可信依赖。

**建议：** 将依赖边界改为受支持能力范围内可能影响 verdict、诊断类别、目标选择或证据有效性的可执行/数据/配置输入；Probe 是验证手段，不能定义依赖全集。闭包计算、保守过度绑定及环境表示交给 Architecture。

**上游：** D1-R3、D1-R10；TC-D1-003/004，A06/A07。

### H2 — High：可信身份来源仍可由候选与描述符共同自证

**位置：P 119–121、144–154、451–452；A 24–25。**

**问题：** 正文要求 trusted/current approved identity，却没有规定候选、描述符和所依赖的批准锚点不能一起作为候选自证信任。风险段承认共同漂移，addendum 让 Architecture 定义 trust root，但缺少正文中的最低产品边界：谁批准哪组内容、批准绑定何时冻结、共同替换后什么条件必须失败。

**对抗案例：** 同时更新验证器、dependency manifest、capability hash 和本轮“approved baseline”描述，全部内部校验一致；仅校验描述符所声明 hash 的实现仍可声称满足 trusted identity。

**影响：** 信任机制可留给 Architecture，但是否接受候选自批准不能由实现自由决定。此漏洞正是用户明确要求重点阻止的共同漂移。

**建议：** 正文要求来自候选自声明之外的、可验证且明确授权的信任绑定；批准至少绑定能力及依赖内容、支持策略与作用域。未获得匹配新批准的共同替换必须失败；合法升级必须产生新的批准和失效旧结果。无需现在指定签名系统或存储格式。

**上游：** D1-R3；TC-D1-003/004；ADR-0058 的 bounded resolution。

### H3 — High：Consumer 完整性与 rollback 指标存在可缩小的分母

**位置：P 92–108、248–276、422–424。**

**问题：** Manifest 有 owner、冻结和变更失效规则，但“complete”仅与“declared current Consumers”互相定义，缺少独立的调用者范围核对规则。SM-4 又写成“100% of declared Consumers exercised by the rollback test”；FR-10 只要求“A real Consumer”。

**对抗案例：** 实际 A/B 两个调用者，仅声明 A；或者 A/B 均声明，但回滚测试只 exercise A。B 仍走 Candidate Route。当前指标可报告已测试消费者的 100%，FR-9 的普通执行也不能证明 B 回滚正确。

**影响：** 调用者覆盖与回滚成功可通过减少声明/测试集合获得，违反完整消费者与不跳过执行的产品目标。

**建议：** 定义完整性核对基准及最低必需消费者（现有 contract 至少明确 VDD、Acceptance 路由和 workflow-model-routing 终端观察）；变更时同时核对当前调用面，不得只核对 manifest 自身。SM-4 分母改为完整冻结集合，明确空集不可通过；逐消费者覆盖四种转换及适用 fixture，任何例外须由产品明确处置。

**上游：** D1-R8/R9；TC-D1-002/009/011，A04/A13/A15；C 的 core_skill_routes。

### H4 — High：Supported Target Policy 没有最低能力边界，可以把必须支持的目标声明为 unsupported

**位置：P 103–104、123–142；A 80–81。**

**问题：** 定义只说“冻结策略中存在即支持”，未规定最低支持集合、支持的 Skill 契约或由谁批准缩减。历史 TC-D1-002 被标 retained，但 FR-1/2 没有保留统一仓库入口及核心 Skill 路由的完整产品义务；TC-D1-003 的 Skill Creator 验证器限制是否演进也未处置。

**对抗案例：** 将策略限定为 Acceptance 专用包，拒绝 VDD 包。实现可以证明请求目标确实被读，并正确拒绝“unsupported”，却未修复通用核心 Skill 校验能力。当前 capability 恰好仍指向 Acceptance 专用入口，因此这是与仓库缺陷相连的风险。

**影响：** 强目标绑定不能弥补支持面被缩小；会将旧缺陷转写成合法产品限制。

**建议：** 正文明确必须支持的现有消费者目标与包契约，支持集合的批准/变更规则，并规定不能通过 unsupported 排除必需目标。对 Skill Creator 来源限制明确 retained 或获准 superseded；无需锁定新的 CLI 或内部实现。

**上游：** D1-R2/R3/R8；TC-D1-002/003，A03/A04/A05；C 的 core_skill_routes。

### H5 — High：矩阵“有意义比较”的规则既有无来源过约束，也缺少防止预批准退化的边界

**位置：P 82–85、208–240、326–333；A 27–28。**

**问题：** FR-7 要求每个 case 都有能影响该 case 的真实 delta；上游要求两个独立对象与六种不同场景，没有要求一次修复影响所有六类场景。另一方面 FR-8 允许任何冻结的 expected-difference，没有给出这些差异必须满足的产品不变量和批准依据。

**对抗案例：** 一次仅修复脏基线判断的合理候选，正向兼容 case 应保持相同表现，却可能因“无 case-relevant delta”被拒。另一个实现可以把 Candidate 对知识碰撞错误放行预先写成 expected-difference，再以执行/证据完整为由通过。

**影响：** 容易迫使实现为每个 case 注入人工版本差异，偏离比较真实候选；也可能将已知退化包装成比较成功。

**建议：** 定义 Stable 的来源资格、实际候选与比较对象的关系；要求整对比较有真实相关变化，允许未受影响场景证明行为保持。六类 case 各自给出不可放宽的产品不变量和比较规则；冻结期望不得豁免非法目标、无效包、污染/碰撞/策略缺口等应拒绝条件。选择哪些具体故障注入由 Spec/Architecture 完成。

**上游：** D1-R7；TC-D1-008，A12。历史 accepted behavior 只能作为比较来源，不得变成当前质量或 Acceptance 权威。

### H6 — High：Exact Cover 仍允许“一个复合需求对应一个失败”掩盖子义务遗漏

**位置：P 99–100、284–294、412–414。**

**问题：** FR-11/SM-1 要求每个 requirement 至少一个 independently observable failure，上游要求每个 behavioral assertion 有独立失败。PRD 同时缺少“复合条款所有可观察后果都必须分解覆盖”的规则；rebuilt source requirements 的集合与旧 retained 子条款也没有强制闭合。

**对抗案例：** 将 FR-3 所有缺失/替换/漂移/逃逸/不兼容义务都映射到一个“验证器文件缺失”测试。该测试有真进程、真失败、双向链接且不是 aggregate-only assertion，仍不能证明其他行为。

**影响：** 映射图即使没有孤儿，也可能只覆盖每组要求中最容易的一点，重复 round-6 缩小验收范围的问题。

**建议：** 要求所有 FR consequences、NFR、guardrails 与 retained 上游义务被分解为原子可判定义务；每个行为断言有独立故障见证，禁止用一个代表性失败覆盖互不等价义务。允许合理 many-to-many 复用，但必须逐义务证明，不按唯一测试数评分。非行为约束定义可判定违规见证，不强迫制造无意义进程测试。

**上游：** D1-R10、source brief 第 7 节；TC-D1-001 至 013 的实际 retained 义务。

### H7 — High：addendum 的 informative 定位与规范性约束冲突，生命周期边界在正文仍不完整

**位置：A 3–4、33–34、99–106；P 174–185、303–322、476–479。**

**问题：** addendum 声明不增加产品要求，却承担必须机器可验证空授权集、保留原生命令和 repair-round Git baseline 的下游约束。正文 FR-13 只明确不能授予 Acceptance，没有完整重述 TC-D1 派生产物不得发布其他 owner 的 plan-ready、implementation-complete、release/archive。A 33–34 又预设排除 temporary-path identity，而正文将排除规则留待审查且默认 fail-closed。

**影响：** 只提取正文的 Spec 会丢约束；把 addendum 当规范的实现会提前采用排除规则。旧 C 的 implementation_lifecycle 含 implementation-complete 授权集合，source brief/Q8 明确空集，addendum 仅说字段兼容不足以处置这个权限语义冲突。

**建议：** 把产品约束移入正文或明确规范性引用：TC-D1 派生证据均 authorizes 空集，不能授予其他生命周期权限；Quick Dev 仅报告自身 predicate，生命周期 owner 的独立发布行为另行拥有。声明 source brief/ADR 与旧 C 冲突的处置顺序。原生命令、Git baseline 在正文明确；addendum 的临时路径排除改为待评估设计选项，禁止排除语义输入。

**上游：** D1-R1/R5/R11；TC-D1-005/010，A08/A14；ADR-0060。

### H8 — High：声明使用的上游评审文件不在候选中，输入无法独立重建

**位置：A 18–19；关联 S 199–203。**

**问题：** addendum 称 docs/fix80501.txt 在 PRD workspace 外，但候选整个 Git tree 均没有该路径，也没有提供替代的不可变可获取内容绑定。outside workspace 不是输入可追溯性的替代品。

**证据：** 本次查询候选完整 tree，truncated=false，路径不存在。Q8 terminal-input 仍引用该路径；旧 Q8 内容的存在不能补回文件。

**影响：** 无法核验 PRD 是否忠实演进这一明确上游；无法确认遗漏项是否已被产品批准处置。新操作者无法复现宣称的输入集合。

**建议：** 以新文件/附加归档保存原始评审内容及来源身份，或者提供可获取的不可变外部绑定；明确其 informative/non-authorizing 角色。不要改写旧 Q8。以新候选重新评审，并更新 PRD 输入绑定说明。

**上游：** source brief 第 9 节、D1-R1/R10；本次用户明确指定的上游输入 2。

### M1 — Medium：历史 disposition 全部 retained，但至少数项子义务缺失或演进未说明

**位置：A 79–97；P 144–172、192–206、375–406。**

**问题：** 表格的十三个 ID 齐全不等于 retained 成立。除 H4/H7 外，旧 A06 的版本记录、A11 的允许 candidate class 集合、A16 的 installed BMAD/GDS 禁改边界均没有在相应正文保留；“self-reported version 不可信”不等于可以删除版本记录。FR-6 命名三 seed，但没有保留旧 manifest 的恰好一次及批准分类约束。

**影响：** 下游不知道这些是有意取消还是遗漏。保护 Phase 等边界不能推导出 BMAD/GDS installed 文件也受保护。

**建议：** 正文补回义务，或把对应子义务标 narrowed/superseded 并给出授权依据和替代验收。逐项 reconciliation 应到 A01–A17 和必要子义务，不必保留旧四切片设计。

**上游：** TC-D1-003/006/007/012，A06/A09/A11/A16；source brief 第 7、8 节。

### M2 — Medium：Current Snapshot 重建与运行证据重放的等价边界未完全分开

**位置：P 101–113、296–309、432–434、476–479；A 33–34。**

**问题：** 定义同时要求固定 evidence relationships 的相等与 fresh-run semantic reproduction，但没有区分“还原原始输入并验证既有证据”与“重新执行产生新时间、进程标识和输出证据”。同时便携字段排除没有正文限定不得影响语义/身份关系。

**影响：** 一个设计可能要求旧输出字节原样出现，另一个只要 verdict 相同即可；可能无法跨机重放，或以 normalization 排除真正影响 verdict 的输入。已有 fail-closed 默认防止直接假成功，因此不是要求 PRD 决定哈希算法。

**建议：** 产品层明确原始输入身份精确重建，新执行证据独立生成并绑定相同输入；允许变化仅限不能影响观察、选源、目标和授权的运行元数据。归一化策略自身是版本化绑定输入，变化需重新评审并使受影响结果 stale。具体字段由 Architecture 决定。

**上游：** D1-R1/R10；ADR-0060 的 selection/content 分离、baseline 与完整 membership。

### M3 — Medium：FR-13 提前指定 bmad-review 与新增批准产物，但未给出继承依据

**位置：P 16–18、318–320、464–469；A 21–36。**

**问题：** source brief 要求 independent review，不限定必须 bmad-review；PRD 将特定 workflow 和 explicit Maintainer approval artifact 升级为硬产品门槛，且没有标 assumption、来源或与当前 Acceptance 入口的兼容处置。

**影响：** 内容等价的独立评审可能被拒；Spec 可能设计新审批产物，Architecture 则按当前 owner 合同接入，产生不同生命周期。当前 Acceptance Skill 说明其不批准 review，Bootstrap explicit-only；这不证明新规则必然冲突，但要求明确协调，不能推定相容。

**建议：** 正文规定所需独立评审结论、批准主体和绑定范围；特定 Skill/产物格式作为现有合同适配或经批准的决策引用。若确实必须 bmad-review，说明产品理由、当前 owner 接收方式及所需 ADR 演进；不要默认新增审批系统。

**上游：** D1-R11；TC-D1-010；AGENTS.md 的 owner 分离与 durable contract 变更规则。

### M4 — Medium：缺陷揭示测试的“先于生产变更”时序在下游输入中丢失

**位置：P 412–418；A 64–73；关联 S 152–167。**

**问题：** source brief 明确 Before production changes，SM-1/2 只要求最终有失败见证/对抗测试，没有保留这一执行先后约束或有依据的演进处置。

**影响：** 后补一个失败记录也可能满足指标，无法证明用缺陷揭示测试约束修复。这里要求的是保留上游交付约束，不要求 PRD 设计 Quick Dev 描述符。

**建议：** 在 handoff constraints 保留先建立/运行缺陷揭示测试再修改生产行为的要求，并允许 Spec 明确 brownfield 已通过行为的处理方式；不能伪造 red，也不能以事后运行替代时序证据。若取消该约束须显式处置。

**上游：** source brief 第 6 节。

### M5 — Medium：内置 final 报告与候选正文不一致，且遗漏仍存在的产品决策

**位置：`_bmad-output/planning-artifacts/prds/prd-jimuyun-2026-09-11/reconcile-know-tc-d1-rebuild-final.md` 5、20–27 行；同目录 `review-rubric-final.md` 5、13–15 行；P 197–199。**

**问题：** final reconciliation 仍称三个 seed 名称没有写入，候选正文已实际列出。final rubric 则称没有阻塞产品决策，却未识别 H1–H7。报告没有提供足以说明各自审查旧快照的候选绑定，不能把同提交中的 final 文件名当作当前审批事实。

**影响：** 下游可能相信“唯一残余项已补好，所以通过”，漏过实质语义缺口。

**建议：** 保留旧报告，在新增评审记录中绑定准确产物 hash，并逐项记录复查状态。不得改写旧报告来制造当时已评审最终字节的印象。

**上游：** D1-R1/R10/R11；本次独立评审不继承内置结论的要求。

## 3. 历史 TC-D1-001 至 013 逐项复核

下表核对的是处置是否有实质依据，不强制旧实现和旧四切片继续有效。

| 历史 ID | PRD 自报处置 | 独立判断 |
| --- | --- | --- |
| 001 | retained | 基本成立：FR-5/NFR-5 定义完整成员/路径/字节保护。新 round 的基线约束应进入规范正文。 |
| 002 | retained | 不完整：有效目标加强了，但统一仓库入口、核心 Skill 必需支持/路由未明确保留，见 H4。 |
| 003 | retained | 不完整：Skill Creator root 处置、版本记录、依赖闭包与信任来源仍有缺口，见 H1/H2/H4/M1。 |
| 004 | retained | 主要失败类别覆盖良好；信任及依赖集合可被缩小，故尚未达到可判定闭合。 |
| 005 | retained | 机器绑定与非授权保留；原生命令主要靠 informative addendum 承担，current detached equivalent 的要求也应明确规范继承。 |
| 006 | retained | 三 seed 名称、provenance、missing/counterexample 已补；exactly-once 与 native evidence 下游绑定还需保留。 |
| 007 | retained | 不晋升边界成立；旧允许的 candidate 分类未保留或显式演进。 |
| 008 | retained | 双侧、不同 fixture/state、独立证据明显加强；比较期望和每 case delta 规则需修订，见 H5。 |
| 009 | retained | 明确保留 workflow-model-routing terminal Consumer；Consumer 集完整性仍需独立核对规则。 |
| 010 | retained | Acceptance 分离明确；空集及全部生命周期 owner 权限边界未在规范正文闭合，见 H7。 |
| 011 | retained | 真调用恢复比旧实现明显加强；多消费者分母和转换覆盖仍可绕过，见 H3。 |
| 012 | retained | Phase/runtime/workspace/account/sandbox 基本保留；BMAD/GDS installed 禁改边界遗漏。 |
| 013 | retained | 基本成立：TC-E0/D2–D6、Miner/Memory/Curator、SkillOS、自动晋升/修改、ranking、RL 均被排除。 |

因此，“十三项都有一行 retained”不能作为完成 reconciliation 的证据。对于旧一次性创建工作改为修复、live v1 由 ADR-0060 取代，addendum 的总体演进理由合理；它不能替代对上述剩余子义务的逐项处置。

## 4. 十五个重点审查面的结论

| 审查面 | 结论 |
| --- | --- |
| 上游 source brief 保真 | 主体覆盖强；缺一项指定原始输入，部分约束弱化，未通过完整 reconciliation。 |
| 001–013 处置 | 结构齐全，实质不全。 |
| FR 产品层次 | 大部分是能力/观察；FR-13 固定工作流、addendum atomic/排除决定有提前设计倾向。 |
| 实际目标 | FR-2 明确拒绝错目标和旁置 manifest，方向正确；最低支持策略未闭合。 |
| Capability/Dependency/Trust | H1/H2 阻塞。 |
| Stable/Candidate 独立比较 | 有双侧和身份要求；比较对象来源、每 case delta 与期望政策待修。 |
| 六类 Matrix | 已明确不同 fixture/state、双侧、禁复用；仍需各类产品不变量。 |
| Consumer Manifest | owner、freeze、change invalidation 已有；独立完整性规则缺失。 |
| disable/rollback/re-enable | 真行为要求已建立；完整消费者与四转换覆盖不足。 |
| Exact Cover/Snapshot/stale | 有明显进展；原子覆盖和重建/重跑边界未完全闭合。 |
| 历史/append-only/空集/Acceptance | 历史保护强；规范层级与权限全集仍需修。 |
| Metrics 防刷 | 反测试数/日志数/标签数很好；SM-1、SM-4 的分母仍可取巧。 |
| Open Questions/Assumptions | 显式 OQ 多数可留后续；另有 H1–H7 所涉隐含产品决定未列入。 |
| 范围越界 | 未发现主动吸收 E0/D2–D6、Phase、Hosted、Miner/Memory/SkillOS/RL；installed BMAD/GDS 禁改遗漏需补。 |
| addendum 仅技术上下文 | 未满足：规范性产品约束与 informativity 冲突。 |

## 5. 已确认覆盖良好的内容

- FR-2 明确不能用请求目标 hash 配无关成功命令冒充有效检查，要求 effective inspected content。
- FR-4 要求独立正反 Probe、预期原因与实际执行证据；拒绝预填结果。
- FR-6 当前正文确实列出三个稳定 seed 名称，保留适用性、缺失标签、反例/明确无反例和不得晋升。
- FR-7/8 已取消单侧历史例外，要求每 case 两侧执行、独立观察与不同 fixture/state；基础设施失败不能包装成语义差异。
- FR-9 明确 workflow-model-routing 是终端消费者观察，并排除“一个消费者证明普遍质量”。
- FR-10 明确恢复 Prior Route 身份与 verdict/diagnostic，而不接受仅配置变更。
- NFR-5 把历史保护从口号提升为成员、路径、内容集合，允许 append-only 新路径。
- Windows 可移植性、超时失败、输出受限和不以提速减少覆盖的方向合理。
- Skill-input v2、fresh Acceptance、历史 Acceptance/Q8 不继承权限、Toolchain-only 范围明确。
- 没有把现有代码声明为已满足新 PRD。addendum 的矩阵/回滚缺口叙述与当前代码方向一致。
- SM-C1–C4 能有效拒绝以测试数、日志量、标签数、跳过执行作为成功依据；剩余分母漏洞应修复而非删除这些指标。

## 6. 未解决的产品决策

在 PRD 层解决以下决策，不要求写技术实现：

1. 必须支持的包/消费者能力范围是什么，谁能以何种依据缩减？
2. 谁批准可信 validator/dependency/target-policy 内容；候选自声明之外的批准边界是什么？
3. dependency 的产品语义闭包是什么，不能仅等于冻结 Probe 集。
4. Stable 对象如何取得比较资格；六类 case 哪些不变量不可被 expected-difference 豁免？
5. 所有当前调用者的完整性如何独立判定；回滚是否逐消费者覆盖全部转换？
6. Exact Cover 的原子义务全集及历史 retained 子义务如何进入新规范？
7. addendum 是否具规范效力；权限空集、旧 contract 冲突和特定 review workflow 如何处置？
8. 语义重现允许哪些类别的变化，哪些身份/内容绝不能被 normalization 消除？

当前两项显式 OQ 的处理：具体预算值可以在 Spec 前后测量，但预算必设与失败不减覆盖须保持硬约束；便携字段具体名单可给 Architecture，但允许排除的产品边界应先补。把整个预算义务标 ASSUMPTION 不能用于后续免除它。

## 7. 可以留给 Spec 的问题

- 原子 obligation/acceptance ID、traceability schema 与 many-to-many 覆盖结构。
- 各类正反 fixture 的具体内容、预期诊断与对抗变体。
- 每 case 的精确命令/input/output/process evidence 字段和对比断言。
- 终端状态优先级、退出码、兼容迁移的细节。
- 在已确定完整集合基础上的 Consumer fixture/transition 表。
- 每个进程及整体运行的具体预算值、输出上限。
- 源映射、失败见证和 pre-change 执行时序证据的格式。

这些工作以修订后的产品边界为前提，不能通过 Spec 自行删除上游义务。

## 8. 可以留给 Architecture 的问题

- adapter 如何证明真正读取目标、如何防止读后替换及证据自报。
- 可信批准锚点的存储/验证机制与依赖闭包发现。
- Stable/Candidate、fixture、消费者与回滚环境的隔离方式。
- Prior Route 捕获、原子切换和失败恢复机制。
- Consumer Manifest 存储、调用者发现/核对实现。
- Snapshot 内容封装、Git baseline/Skill-input v2 集成、允许元数据归一化算法。
- 新旧 producer/schema/terminal consumer 的兼容设计。
- 新旧证据 custody/retention 与独立新运行证据的关系。

不要求把加密方案、CLI、JSON 字段或 Python 实现写进 PRD。

## 9. 不应带入后续规范基线的阻塞项与修订验收

H1–H8 关闭前，不应宣称 PRD 已通过并冻结下游 Spec 或 Architecture。可做帮助产品决策的探索草稿，但不能据此授权 08-05 修复实施。

建议以一个 append-only 修订候选完成：

- 补全缺失上游原始输入，绑定新候选与文档 hash。
- 修订支持范围、可信批准边界、语义闭包、Consumer 分母和六类矩阵不变量。
- 修正 FR-7 的每 case delta 过约束与 FR-11 的复合义务覆盖漏洞。
- 将规范约束放入正文，明确历史子义务处置与旧合同冲突，保留原报告。
- 完成 13 个旧 requirement、17 个旧 acceptance 与 D1-R1–R11 的语义 reconciliation。
- 用本报告对抗案例做条文桌面验证：每个案例必须被明确条款拒绝，不能仅诉诸“实现会处理”或泛化 fail-closed。
- 给新评审报告绑定最终产物 hash，不能以旧 final 文件名代替当前审查。

## 10. 内置 review/reconciliation 遗漏与误报

已发现遗漏，主要是 H1 的 Probe 限域依赖、H2 共同漂移信任锚点、H3 自定义消费者/回滚分母、H4 unsupported 范围逃逸、H5 每 case delta 过约束与 expected-difference 退化、H6 原子覆盖，以及 H7 informative/normative 冲突。内置报告看到了部分相关风险，但错误地将术语已定义/owner 已命名等同于语义已闭合。

另有一项可直接核对的过时断言：final reconciliation 所称 seed 名称未写入，对当前 P 197–199 已不成立。该缺口本次判为已经补齐，不能继续列作阻塞。没有依据把过时报告误报视为恶意，也不推定其曾审查当前最终字节。

## 11. 最终阶段结论

| 问题 | 回答 |
| --- | --- |
| 是否可以进入 bmad-spec？ | **不能作为“PRD 已通过”的正式规范阶段进入。** 可做帮助消除决策缺口的探索，但不得冻结 Spec 或授权实施。 |
| 是否可以进入 bmad-architecture？ | **不能据此冻结正式 Architecture。** 可调研机制选项，不能由 Architecture 代替未决产品政策。 |
| 是否需要先修订 PRD？ | **需要。** 优先关闭 H1–H8，同时解决 M1–M4 的保真/权限/覆盖问题。 |
| 是否发现自带报告遗漏？ | **是。** 有实质遗漏，也有 seed 名称已补却仍被报缺失的过时判断。 |
| 是否据此改变实现完成度或发布 Acceptance？ | **否。** 本报告只判断这个固定候选的 PRD 决策就绪度。 |

**最终建议：保留已有能力框架，做一轮聚焦产品语义与上游处置的 PRD 修订，再复核；不需要推倒全部文档，也不能只补自评“通过”状态。**
