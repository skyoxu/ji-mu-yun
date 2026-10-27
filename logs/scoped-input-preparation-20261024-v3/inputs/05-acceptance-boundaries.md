## SM-K43

**本块生效范围（待确认输入）**：仅针对本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。BMAD 专属新增知识查询交付已转部署侧；不得据旧来源、交叉引用或旧角色启动任何 BMAD skill、原生生成/补查、安装验证或内部 reviewer。已交付 PRD/SPEC/Architecture 只消费明确保留的内容，原文/原角色用于溯源，不要求再判断其是否需要审核或重新生成。保留 Windows 实机验证、权限/四维隔离、来源与字节完整性、查询30/60秒等原预算、development/auto 默认治理关闭、真实 VDD 消费及源码核查、失败/取消和历史证据保护。后续长流程执行预算与业务查询预算分别管理。

**来源角色与上下文归属**：本块是本次范围修订的完整作者输入，尚非正式合同或运行证明。本块下“有效条款明细”及“依赖表达”是本块需要消费的文本；旧 O/A/FI、原文件/原角色和旧引用只标识历史对应项，不成为本版正式ID，不恢复已移出的义务，不继承旧 receipt、RED、Q7/Q8 或审核权限。引用的原文行仅作保留来源，不优先于本块明确范围。

**有效条款范围**：本块对应 17 条旧条款的保留部分；该数量用于覆盖核对，不预设未来模型生成数量。

### 有效条款明细

### 条款 O-01DA6B7A91DC（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-01DA6B7A91DC / A-D312E58615C2（仅溯源，不导入旧运行权限）。
- **前提**：Public VDD create and repair under unset/development auto
- **发生时机**：When VDD creates or repairs a directory in development/auto; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Default-query and check current source, callers and tests without enabling knowledge freezing or governance artifacts under FR-05/FR-08 query/source/caller/test inspection before slices without freeze/attestation/authorization artifacts
- **可观察结果**：Real VDD create/repair proves checks while governance remains off Inspect query/source/caller/test inspection before slices without freeze/attestation/authorization artifacts
- **禁止结果**：Implicit freeze/governance artifacts；Missing current caller/test verification
- **原前态**：Governance defaults off
- **原后态**：Query and source checks without governance side effects

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K55](07-shared-design.md#SM-K55) 中旧条款 O-9C582F662DBB 对应的保留行为：保留 query 表、固定入口、预算、受限 stage→consumer、来源可查及拒绝任意命令。。适用条件与界限：consumer仍依赖受跟踪配置、固定VDD阶段/身份映射、有效预算/来源；只去除BMAD阶段，不去掉保留VDD调用的真实配置前置。 原映射 O-01DA6B7A91DC → O-9C582F662DBB 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/planning-query.toml、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-0D09D61E0B4E（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-0D09D61E0B4E / A-F281D32C6FE2（仅溯源，不导入旧运行权限）。
- **前提**：Resume with unrelated index change or one related source change
- **发生时机**：When recovery sees relevant source change or only unrelated index change; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Relevant changes update only affected parts; unrelated index changes do not automatically rebuild whole directory or rerun all flows under FR-09 unrelated keeps directory/episode, related updates affected conclusion/dependents only, history preserved
- **可观察结果**：Both recovery cases demonstrate bounded effects Inspect unrelated keeps directory/episode, related updates affected conclusion/dependents only, history preserved
- **禁止结果**：Whole rebuild/full rerun for unrelated index change；Unrelated parts changed for relevant local drift
- **原前态**：Prior plan exists
- **原后态**：Affected-only update or no rebuild

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-0D09D61E0B4E → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-113D52ECE151（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-113D52ECE151 / A-33A45B5E4C9C（仅溯源，不导入旧运行权限）。
- **前提**：Real consumer with diagnosed backend absence and unverifiable necessary source
- **发生时机**：When unavailability or timeout is confirmable; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Record source verification and do not continue dependent conclusions when necessary facts are missing under FR-07/FR-09 direct-source verification recorded, dependent scope conclusion remains incomplete rather than guessed
- **可观察结果**：Availability fallback and unresolved-fact stop are observable Inspect direct-source verification recorded, dependent scope conclusion remains incomplete rather than guessed
- **禁止结果**：Continuing conclusion with missing necessary fact
- **原前态**：Query unavailable
- **原后态**：Recorded independent source check with dependent stop

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K55](07-shared-design.md#SM-K55) 中旧条款 O-9C582F662DBB 对应的保留行为：保留 query 表、固定入口、预算、受限 stage→consumer、来源可查及拒绝任意命令。。适用条件与界限：consumer仍依赖受跟踪配置、固定VDD阶段/身份映射、有效预算/来源；只去除BMAD阶段，不去掉保留VDD调用的真实配置前置。 原映射 O-113D52ECE151 → O-9C582F662DBB 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/planning-query.toml、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-40CE012D7173（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-40CE012D7173 / A-11BE3B5502C7（仅溯源，不导入旧运行权限）。
- **前提**：Complete candidate validation including legacy handoff regression
- **发生时机**：When declaring feature complete; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Require observable in-scope behavior, distinct failure versus degradation, no known material existing-consumer regression and formal Acceptance under current owner contract in-scope behaviors observable, untrusted blocked distinct from availability/degradation, known regressions prevent completion; only final Acceptance owner decides
- **可观察结果**：Completion has behavioral, compatibility and owner evidence Inspect in-scope behaviors observable, untrusted blocked distinct from availability/degradation, known regressions prevent completion; only final Acceptance owner decides
- **禁止结果**：Completion with known material regression；Conflated failure/degradation
- **原前态**：Behavior and failure handling need verification
- **原后态**：Formal owner completion supported

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K55](07-shared-design.md#SM-K55) 中旧条款 O-9C582F662DBB 对应的保留行为：保留 query 表、固定入口、预算、受限 stage→consumer、来源可查及拒绝任意命令。。适用条件与界限：consumer仍依赖受跟踪配置、固定VDD阶段/身份映射、有效预算/来源；只去除BMAD阶段，不去掉保留VDD调用的真实配置前置。 原映射 O-40CE012D7173 → O-9C582F662DBB 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/planning-query.toml、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-48A9ADB890E3（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-48A9ADB890E3 / A-7E56126E99EB（仅溯源，不导入旧运行权限）。
- **前提**：Cancel query before complete source verification
- **发生时机**：When user cancels; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Preserve incomplete status and do not automatically retry under FR-07/FR-09 incomplete/cancelled record, child terminated, no auto retry or false complete
- **可观察结果**：Cancellation record remains incomplete without retry Inspect incomplete/cancelled record, child terminated, no auto retry or false complete
- **禁止结果**：Automatic retry；False complete
- **原前态**：Query not completed
- **原后态**：Incomplete without automatic retry

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-48A9ADB890E3 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-54829FE46AF9（旧ID溯源；缩减）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-54829FE46AF9 / A-492A044823B0（仅溯源，不导入旧运行权限）。
- **前提**：确定性分支证据、有界实际 VDD 消费和真实 Windows 路径/编码/子进程证据。
- **发生时机**：在本条所述保留消费者/资料/交接被实际使用，且在依赖其结果的结论被接纳之前。
- **完整要求**：保留实际 VDD 样例和 Windows 路径/编码/子进程，fixture 不冒充真实运行。 保留范围内的原有条件、失败与权限保护不得因 BMAD 专属交付移出而被豁免。
- **可观察结果**：保留实际 VDD 样例和 Windows 路径/编码/子进程，fixture 不冒充真实运行。 所有断言针对保留消费者/实际来源/当前范围，移出部分不得被声称已执行或已通过。
- **禁止结果**：Fixture-only actual-consumer proof；Linux-only Windows proof
- **明确移出**：实际 BMAD 阶段样例转部署侧。

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K55](07-shared-design.md#SM-K55) 中旧条款 O-9C582F662DBB 对应的保留行为：保留 query 表、固定入口、预算、受限 stage→consumer、来源可查及拒绝任意命令。。适用条件与界限：consumer仍依赖受跟踪配置、固定VDD阶段/身份映射、有效预算/来源；只去除BMAD阶段，不去掉保留VDD调用的真实配置前置。 原映射 O-54829FE46AF9 → O-9C582F662DBB 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/planning-query.toml、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-5F92AC05BCFA（旧ID溯源；缩减）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-5F92AC05BCFA / A-0D3DF5D78E13（仅溯源，不导入旧运行权限）。
- **前提**：实际 VDD 调用、QuickDev 原有上下文/证据交接、typed 输入完整性和适用平台结果。
- **发生时机**：在本条所述保留消费者/资料/交接被实际使用，且在依赖其结果的结论被接纳之前。
- **完整要求**：保留实际 VDD 消费证据、QuickDev/Acceptance 交接、typed 输入完整性和真实 Windows 限制。 保留范围内的原有条件、失败与权限保护不得因 BMAD 专属交付移出而被豁免。
- **可观察结果**：保留实际 VDD 消费证据、QuickDev/Acceptance 交接、typed 输入完整性和真实 Windows 限制。 所有断言针对保留消费者/实际来源/当前范围，移出部分不得被声称已执行或已通过。
- **禁止结果**：Unsupported platform-pass claims；Broken downstream handoff
- **明确移出**：不再要求为本次执行 SPEC/BMAD 消费样例。

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K55](07-shared-design.md#SM-K55) 中旧条款 O-9C582F662DBB 对应的保留行为：保留 query 表、固定入口、预算、受限 stage→consumer、来源可查及拒绝任意命令。。适用条件与界限：consumer仍依赖受跟踪配置、固定VDD阶段/身份映射、有效预算/来源；只去除BMAD阶段，不去掉保留VDD调用的真实配置前置。 原映射 O-5F92AC05BCFA → O-9C582F662DBB 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/planning-query.toml、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-7694233DB1C7（旧ID溯源；缩减）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-7694233DB1C7 / A-17F4FC42DBB0（仅溯源，不导入旧运行权限）。
- **前提**：VDD 仓库 query 配置、重复触发及 personal/model 只可缩小预算的覆盖。
- **发生时机**：VDD 查询配置解析和同一判断首次/重复/恢复触发时，且在使用配置发起查询之前。
- **完整要求**：保留 repository config 的持久性、有效值/来源和一次触发去重。 保留知识查询配置 enabled/stages 与四项预算有效值/来源、未知/非法值拒绝、missing 与 corrupt 区分；仓库显式关闭需记录 disabled，personal/model 不能豁免必需阶段或扩大 scope/预算。适用阶段为 vdd-create/vdd-repair，身份固定 vdd；不接受任意命令/绝对入口/任意 consumer，不修改其他既有消费者。相同任务/相关输入的重复阶段或恢复只对应同一 episode 与累计额度，不额外计次或重置；仓库持久配置不依赖可覆盖的 native 默认。
- **可观察结果**：保留 repository config 的持久性、有效值/来源和一次触发去重。 所有断言针对保留消费者/实际来源/当前范围，移出部分不得被声称已执行或已通过。
- **禁止结果**：Default-only persistence；Duplicate trigger execution；Incorrect effective config
- **明确移出**：native reinstall/BMAD 默认配置耐久性转设备侧。

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K55](07-shared-design.md#SM-K55) 中旧条款 O-9C582F662DBB 对应的保留行为：保留 query 表、固定入口、预算、受限 stage→consumer、来源可查及拒绝任意命令。。适用条件与界限：consumer仍依赖受跟踪配置、固定VDD阶段/身份映射、有效预算/来源；只去除BMAD阶段，不去掉保留VDD调用的真实配置前置。 原映射 O-7694233DB1C7 → O-9C582F662DBB 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/planning-query.toml、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-812769EB2D98（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-812769EB2D98 / A-8BA74E0EB825（仅溯源，不导入旧运行权限）。
- **前提**：Governance-on required module/integrity/authorization failures with lightweight query hit
- **发生时机**：When governance-on required module or integrity validation fails; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Preserve original blocking and do not substitute lightweight mode for formal gate under FR-08 original gate remains blocked regardless query result
- **可观察结果**：Required module and integrity failures remain blocked Inspect original gate remains blocked regardless query result
- **禁止结果**：Lightweight mode substitutes formal gate
- **原前态**：Required contract unsatisfied
- **原后态**：Original block retained

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K55](07-shared-design.md#SM-K55) 中旧条款 O-9C582F662DBB 对应的保留行为：保留 query 表、固定入口、预算、受限 stage→consumer、来源可查及拒绝任意命令。。适用条件与界限：consumer仍依赖受跟踪配置、固定VDD阶段/身份映射、有效预算/来源；只去除BMAD阶段，不去掉保留VDD调用的真实配置前置。 原映射 O-812769EB2D98 → O-9C582F662DBB 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/planning-query.toml、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-89793D285B4F（旧ID溯源；缩减）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-89793D285B4F / A-03C47C4FCDD8（仅溯源，不导入旧运行权限）。
- **前提**：已交付输入格式/包身份检查与新范围内功能证据的分别报告。
- **发生时机**：在本条所述保留消费者/资料/交接被实际使用，且在依赖其结果的结论被接纳之前。
- **完整要求**：保留规划/包有效性不等于实施和 Acceptance；范围内验收各自有真实证据。 保留范围内的原有条件、失败与权限保护不得因 BMAD 专属交付移出而被豁免。
- **可观察结果**：保留规划/包有效性不等于实施和 Acceptance；范围内验收各自有真实证据。 所有断言针对保留消费者/实际来源/当前范围，移出部分不得被声称已执行或已通过。
- **禁止结果**：SPEC creation claimed as implementation completion；Package validation substituted for Acceptance
- **明确移出**：旧 all14 全部实现要求按本范围清单缩减；BMAD 场景不能算已通过。

### 条款 O-9A38E9C1D8D3（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-9A38E9C1D8D3 / A-35B26103C2BB（仅溯源，不导入旧运行权限）。
- **前提**：Published snapshot differs from current main/branch/worktree
- **发生时机**：When index differs from relevant working-branch files; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Distinguish snapshot from candidate code, record degradation/refresh and do not forge publication identity or current results under FR-06/FR-07 actual identities retained, recognized relevant drift recorded with permitted refresh, no fabricated current/publication status
- **可观察结果**：Evidence preserves each identity and records response to relevant drift Inspect actual identities retained, recognized relevant drift recorded with permitted refresh, no fabricated current/publication status
- **禁止结果**：Forged publication identity；Fabricated current result
- **原前态**：Published snapshot differs from candidate
- **原后态**：Truthful identity and refresh/degradation record

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-9A38E9C1D8D3 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-9E29614CA1B7（旧ID溯源；缩减）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-9E29614CA1B7 / A-E37295769CA9（仅溯源，不导入旧运行权限）。
- **前提**：实际 VDD 配置到消费 episode；不存在可替代真实采用的提示/键/文件存在声明。
- **发生时机**：在本条所述保留消费者/资料/交接被实际使用，且在依赖其结果的结论被接纳之前。
- **完整要求**：保留 VDD 配置→触发→真实诊断→读取→规划采用，不能只看键/提示/文件。 保留范围内的原有条件、失败与权限保护不得因 BMAD 专属交付移出而被豁免。
- **可观察结果**：保留 VDD 配置→触发→真实诊断→读取→规划采用，不能只看键/提示/文件。 所有断言针对保留消费者/实际来源/当前范围，移出部分不得被声称已执行或已通过。
- **禁止结果**：Static-only acceptance
- **明确移出**：移出 BMAD native adoption 的额外执行条件。

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K55](07-shared-design.md#SM-K55) 中旧条款 O-9C582F662DBB 对应的保留行为：保留 query 表、固定入口、预算、受限 stage→consumer、来源可查及拒绝任意命令。。适用条件与界限：consumer仍依赖受跟踪配置、固定VDD阶段/身份映射、有效预算/来源；只去除BMAD阶段，不去掉保留VDD调用的真实配置前置。 原映射 O-9E29614CA1B7 → O-9C582F662DBB 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/planning-query.toml、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-A37D4E43898B（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-A37D4E43898B / A-3B6C934B9D10（仅溯源，不导入旧运行权限）。
- **前提**：Index misses implementation found through authorized current-source search
- **发生时机**：When Locator misses but source contains implementation; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Actual source check discovers capability and uses it in plan; no absence inference from empty result or duplicate build under FR-05/FR-07 native plan reuses it with direct-source proof and regression path, no duplicate build
- **可观察结果**：Plan adopts found implementation with source discovery evidence Inspect native plan reuses it with direct-source proof and regression path, no duplicate build
- **禁止结果**：Empty result proves absence；Duplicate implementation
- **原前态**：Query misses real capability
- **原后态**：Existing capability reused in plan

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K55](07-shared-design.md#SM-K55) 中旧条款 O-9C582F662DBB 对应的保留行为：保留 query 表、固定入口、预算、受限 stage→consumer、来源可查及拒绝任意命令。。适用条件与界限：consumer仍依赖受跟踪配置、固定VDD阶段/身份映射、有效预算/来源；只去除BMAD阶段，不去掉保留VDD调用的真实配置前置。 原映射 O-A37D4E43898B → O-9C582F662DBB 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/planning-query.toml、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-A6DEA3F8BB0A（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-A6DEA3F8BB0A / A-FEDBD3A2823B（仅溯源，不导入旧运行权限）。
- **前提**：Existing code discovered and candidate proof plan
- **发生时机**：When validating already-existing behavior; evaluate in planning/terminal artifact inspection before admitting its downstream conclusion
- **完整要求**：Regress existing behavior without fake RED or duplicate implementation and without requiring rerun of all historical requirements retain current regression coverage, no obsolete/fake RED/duplicate work or all-history rerun
- **可观察结果**：Validation targets existing behavior and changed scope without duplicate work Inspect retain current regression coverage, no obsolete/fake RED/duplicate work or all-history rerun
- **禁止结果**：Fake RED；Duplicate implementation；Mandatory all-history rerun
- **原前态**：Existing implementation available
- **原后态**：Regression without invented RED

### 条款 O-B34E35470A88（旧ID溯源；缩减）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-B34E35470A88 / A-7FD3EBF5ACDB（仅溯源，不导入旧运行权限）。
- **前提**：已交付 typed 输入的规范/provenance 角色、current/record/selection 与来源字节。
- **发生时机**：在本条所述保留消费者/资料/交接被实际使用，且在依赖其结果的结论被接纳之前。
- **完整要求**：保留作为 VDD 输入的规范/provenance 分工、current/record/来源字节完整性。 保留范围内的原有条件、失败与权限保护不得因 BMAD 专属交付移出而被豁免。
- **可观察结果**：保留作为 VDD 输入的规范/provenance 分工、current/record/来源字节完整性。 所有断言针对保留消费者/实际来源/当前范围，移出部分不得被声称已执行或已通过。
- **禁止结果**：Provenance replaces retained normative input；Invalid delivered package treated as valid
- **明确移出**：SPEC 原生继承和必要补查的行为验证转部署侧。

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K55](07-shared-design.md#SM-K55) 中旧条款 O-9C582F662DBB 对应的保留行为：保留 query 表、固定入口、预算、受限 stage→consumer、来源可查及拒绝任意命令。。适用条件与界限：consumer仍依赖受跟踪配置、固定VDD阶段/身份映射、有效预算/来源；只去除BMAD阶段，不去掉保留VDD调用的真实配置前置。 原映射 O-B34E35470A88 → O-9C582F662DBB 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/planning-query.toml、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-B4DDDFEB665F（旧ID溯源；缩减）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-B4DDDFEB665F / A-6A98EA03A45B（仅溯源，不导入旧运行权限）。
- **前提**：VDD 日常查询及现有正式发布状态；若确需发布，由现有 owner 另行处理。
- **发生时机**：在本条所述保留消费者/资料/交接被实际使用，且在依赖其结果的结论被接纳之前。
- **完整要求**：正常查询不得隐式发布、改 main 或历史；如确需发布仍由现有 owner 显式授权。 保留范围内的原有条件、失败与权限保护不得因 BMAD 专属交付移出而被豁免。
- **可观察结果**：正常查询不得隐式发布、改 main 或历史；如确需发布仍由现有 owner 显式授权。 所有断言针对保留消费者/实际来源/当前范围，移出部分不得被声称已执行或已通过。
- **禁止结果**：Implicit routine publication；Query changes main；Historical evidence alteration
- **明确移出**：不再为 BMAD 新身份安排首次 generation 作为本次交付任务。

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K53](07-shared-design.md#SM-K53) 中旧条款 O-F96ECD3253A2 对应的保留行为：VDD 继续真实使用 vdd，身份与 stage 分开，其他既有消费者不变。。适用条件与界限：目标缩为VDD实际vdd身份和stage分离/不冒用既有其他身份；保留请求/策略/来源规则以其为输入，不恢复bmad-planning消费者。 原映射 O-B4DDDFEB665F → O-F96ECD3253A2 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/contracts/knowledge-locator-request.v1.schema.json、knowledge/policies/consumer-policies.v2.json、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-B56CECA98BA0（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-B56CECA98BA0 / A-53E3F84608E0（仅溯源，不导入旧运行权限）。
- **前提**：Corrupt/out-of-bounds/denied/unknown result with exit0 or []
- **发生时机**：When exit zero carries business blocked or output is corrupt/out-of-bounds; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Do not accept as success or empty, do not disable validation to continue and do not leak out-of-bounds content under FR-02/FR-07 blocked, no false success/empty, no disabling validation or denied-content leak
- **可观察结果**：All listed adversarial cases remain safely blocked Inspect blocked, no false success/empty, no disabling validation or denied-content leak
- **禁止结果**：False success/empty；Disabled validation；Out-of-bounds disclosure
- **原前态**：Transport may appear successful
- **原后态**：Result rejected without disclosure

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-B56CECA98BA0 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

**正式ID边界**：以上旧条款标签和文本锚点用于准确表达前置语义；它们不是新正式 O-ID，不可直接把历史 O-ID 或 SM 锚点字符串当作新计划 depends_on。若未来获准生成，仍须对真实生成的义务ID、对应关系、无环闭包和切片依赖做既有流程核对；本草稿不声称编译器会导入旁置映射文件。
