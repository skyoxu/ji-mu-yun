## SM-K36

**本块生效范围（待确认输入）**：仅针对本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。BMAD 专属新增知识查询交付已转部署侧；不得据旧来源、交叉引用或旧角色启动任何 BMAD skill、原生生成/补查、安装验证或内部 reviewer。已交付 PRD/SPEC/Architecture 只消费明确保留的内容，原文/原角色用于溯源，不要求再判断其是否需要审核或重新生成。保留 Windows 实机验证、权限/四维隔离、来源与字节完整性、查询30/60秒等原预算、development/auto 默认治理关闭、真实 VDD 消费及源码核查、失败/取消和历史证据保护。后续长流程执行预算与业务查询预算分别管理。

**来源角色与上下文归属**：本块是本次范围修订的完整作者输入，尚非正式合同或运行证明。本块下“有效条款明细”及“依赖表达”是本块需要消费的文本；旧 O/A/FI、原文件/原角色和旧引用只标识历史对应项，不成为本版正式ID，不恢复已移出的义务，不继承旧 receipt、RED、Q7/Q8 或审核权限。引用的原文行仅作保留来源，不优先于本块明确范围。

**有效条款范围**：本块对应 2 条旧条款的保留部分；该数量用于覆盖核对，不预设未来模型生成数量。

**逐字保留的旧来源行（仅溯源）**：
> | <a id="SM-K36"></a>K36 | CAP-7, FR-07 | derive from complete source | planning | _bmad-output/specs/spec-bmad-vdd-knowledge-query/failure-modes.md | Original role: normative_companion. Interpretation: Preserve all obligations, conditions, exceptions, quantities and prohibitions in the quoted source. Original IDs remain authority; SM is only a compiler anchor. Verbatim source (UTF-8, reversible HTML escaping):<br># 查询结果与失败分流<br><br>本文件是 CAP-7 的规范 companion，沿用 FR-07 已批准的行为语义，不新建 Locator 公共 schema。以下名称描述消费者决策类别，不宣称是当前 CLI 已有状态字段。Architecture 必须把真实输出/只读诊断逐项映射到这些类别，并保留现有调用方兼容性；实施前不得以字符串猜测代替该映射。<br><br> |

### 有效条款明细

### 条款 O-627B8C4B71A7（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-627B8C4B71A7 / A-7F02B8F22E80（仅溯源，不导入旧运行权限）。
- **前提**：Real core output and verified readonly diagnostics matrix
- **发生时机**：Before implementation of failure handling; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Architecture maps actual outputs/read-only diagnostics individually to decision categories while preserving existing caller compatibility; do not substitute string guessing for that mapping closed mapping table with evidence, not substring guessing; legacy raw_status/exit retained; unknown/mismatched blocked
- **可观察结果**：Every category has an explicit actual-output/diagnostic mapping and compatibility basis Inspect closed mapping table with evidence, not substring guessing; legacy raw_status/exit retained; unknown/mismatched blocked
- **禁止结果**：String guessing instead of explicit mapping；Breaking existing callers
- **原前态**：Actual outputs and read-only diagnostics exist
- **原后态**：Architecture mapping explicit

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-627B8C4B71A7 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-D3207953C3F7（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-D3207953C3F7 / A-F6AE73C0726C（仅溯源，不导入旧运行权限）。
- **前提**：Legacy CLI schema/status/exit and new adapter contract
- **发生时机**：When defining consumer failure categories; evaluate in planning/terminal artifact inspection before admitting its downstream conclusion
- **完整要求**：Use these as consumer decision categories under CAP-7/FR-07, not claims that current CLI has those status fields; do not introduce a new public Locator schema legacy callers retain vocabulary; planning-query.v1 only new consumer-facing interface, no claim those are existing Locator status fields
- **可观察结果**：Documentation and mapping distinguish consumer categories from actual CLI fields Inspect legacy callers retain vocabulary; planning-query.v1 only new consumer-facing interface, no claim those are existing Locator status fields
- **禁止结果**：New public Locator schema；Claiming category names are existing CLI fields
- **原前态**：Approved FR-07 semantics and existing Locator API apply
- **原后态**：Semantics preserved without new public schema

**正式ID边界**：以上旧条款标签和文本锚点用于准确表达前置语义；它们不是新正式 O-ID，不可直接把历史 O-ID 或 SM 锚点字符串当作新计划 depends_on。若未来获准生成，仍须对真实生成的义务ID、对应关系、无环闭包和切片依赖做既有流程核对；本草稿不声称编译器会导入旁置映射文件。

## SM-K37

**本块生效范围（待确认输入）**：仅针对本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。BMAD 专属新增知识查询交付已转部署侧；不得据旧来源、交叉引用或旧角色启动任何 BMAD skill、原生生成/补查、安装验证或内部 reviewer。已交付 PRD/SPEC/Architecture 只消费明确保留的内容，原文/原角色用于溯源，不要求再判断其是否需要审核或重新生成。保留 Windows 实机验证、权限/四维隔离、来源与字节完整性、查询30/60秒等原预算、development/auto 默认治理关闭、真实 VDD 消费及源码核查、失败/取消和历史证据保护。后续长流程执行预算与业务查询预算分别管理。

**来源角色与上下文归属**：本块是本次范围修订的完整作者输入，尚非正式合同或运行证明。本块下“有效条款明细”及“依赖表达”是本块需要消费的文本；旧 O/A/FI、原文件/原角色和旧引用只标识历史对应项，不成为本版正式ID，不恢复已移出的义务，不继承旧 receipt、RED、Q7/Q8 或审核权限。引用的原文行仅作保留来源，不优先于本块明确范围。

**有效条款范围**：本块对应 8 条旧条款的保留部分；该数量用于覆盖核对，不预设未来模型生成数量。

### 有效条款明细

### 条款 O-0531C165C195（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-0531C165C195 / A-22CA88C4990F（仅溯源，不导入旧运行权限）。
- **前提**：Cancellation before source verification completes
- **发生时机**：When user cancels a query; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Stop the query, retain incomplete status, do not retry in background and do not mark unverified work successful owned child stopped, incomplete persists, no background retry or success claim
- **可观察结果**：No background retry or unverified success follows cancellation Inspect owned child stopped, incomplete persists, no background retry or success claim
- **禁止结果**：Background retry；Unverified work marked successful
- **原前态**：Some work may remain unverified
- **原后态**：Query stops incomplete

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-0531C165C195 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-1693A89D7360（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-1693A89D7360 / A-7000BBED23B3（仅溯源，不导入旧运行权限）。
- **前提**：Integrity/policy error observed before cancellation
- **发生时机**：When cancellation follows an observed integrity or permission error; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Retain observed integrity/permission error records and do not rewrite them as ordinary missing because of cancellation previous errors retained in sanitized evidence, not rewritten missing/unavailable
- **可观察结果**：Error record survives cancellation classification Inspect previous errors retained in sanitized evidence, not rewritten missing/unavailable
- **禁止结果**：Integrity/permission error rewritten as missing
- **原前态**：Error already recorded
- **原后态**：Error retained

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-1693A89D7360 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-32C6C396BEC7（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-32C6C396BEC7 / A-A679DB744ED5（仅溯源，不导入旧运行权限）。
- **前提**：Hit/stale/empty alongside trust error
- **发生时机**：When illegal request/config, unknown/corrupt state, damaged publication binding, out-of-bounds path or policy rejection is observed; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Validate consumability before adoption; do not let untrusted candidates enter subsequent factual judgment even alongside hit, stale or empty-array signals; do not downgrade them to ordinary missing trust validation precedes read/adoption and blocks; candidates do not enter downstream facts
- **可观察结果**：Trust errors take priority over hit/stale/empty indications Inspect trust validation precedes read/adoption and blocks; candidates do not enter downstream facts
- **禁止结果**：Adopting untrusted candidate；Trust error downgraded to missing
- **原前态**：Candidates are untrusted
- **原后态**：Candidates excluded from factual reasoning

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-32C6C396BEC7 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-5E3DA627C900（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-5E3DA627C900 / A-80BD1EF39D3D（仅溯源，不导入旧运行权限）。
- **前提**：Conflicting transport/business/integrity signals matrix
- **发生时机**：When judging one query; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Evaluate process exit/exception, timeout, cancellation, parseability, structured business status and applicable source integrity; exit zero, JSON or generated files alone are insufficient exit/exception/timeout/cancel/parse/status/hash jointly evaluated; no single exit0/JSON/file proves success
- **可观察结果**：Decision includes every listed applicable signal Inspect exit/exception/timeout/cancel/parse/status/hash jointly evaluated; no single exit0/JSON/file proves success
- **禁止结果**：Success from a single transport/artifact signal
- **原前态**：Multiple independent result signals available
- **原后态**：All relevant signals evaluated

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-5E3DA627C900 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-7F6AF9FDD617（旧ID溯源；缩减）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-7F6AF9FDD617 / A-A08460BE1FEB（仅溯源，不导入旧运行权限）。
- **前提**：VDD 必要事实不能核实、存在未解决实质冲突或降级核查仍缺事实。
- **发生时机**：在本条所述保留消费者/资料/交接被实际使用，且在依赖其结果的结论被接纳之前。
- **完整要求**：VDD 对必要事实未核实/冲突时停止依赖判断并保留问题。 保留范围内的原有条件、失败与权限保护不得因 BMAD 专属交付移出而被豁免。
- **可观察结果**：VDD 对必要事实未核实/冲突时停止依赖判断并保留问题。 所有断言针对保留消费者/实际来源/当前范围，移出部分不得被声称已执行或已通过。
- **禁止结果**：Delivery judgment continues despite unresolved necessary fact
- **明确移出**：BMAD 原生输出中该行为的执行场景转设备侧。

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K55](07-shared-design.md#SM-K55) 中旧条款 O-9C582F662DBB 对应的保留行为：保留 query 表、固定入口、预算、受限 stage→consumer、来源可查及拒绝任意命令。。适用条件与界限：consumer仍依赖受跟踪配置、固定VDD阶段/身份映射、有效预算/来源；只去除BMAD阶段，不去掉保留VDD调用的真实配置前置。 原映射 O-7F6AF9FDD617 → O-9C582F662DBB 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/planning-query.toml、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-8376A58C8D9A（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-8376A58C8D9A / A-ABDB71FAC4D3（仅溯源，不导入旧运行权限）。
- **前提**：Direct-source fallback while formal required module missing
- **发生时机**：When entering direct source verification; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Do not call direct source verification Locator success or a required-gate replacement; obey existing mandatory constraints whenever governance is on label direct-source, not Locator success; formal gate still blocks
- **可观察结果**：Direct verification has accurate provenance and no gate bypass Inspect label direct-source, not Locator success; formal gate still blocks
- **禁止结果**：Direct verification labeled Locator success；Direct verification replaces required gate
- **原前态**：Locator did not succeed and required gates remain
- **原后态**：Authority boundaries retained

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-8376A58C8D9A → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-D0C9017CF9BC（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-D0C9017CF9BC / A-CB12201ABE6F（仅溯源，不导入旧运行权限）。
- **前提**：Confirmed absence/backend unavailable/timeout contrasted unknown failure
- **发生时机**：When entrypoint reliably diagnosed unconfigured, unavailable or timed out and no untrusted result is consumed; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Record the reliable cause and independently verify current source only under those conditions only diagnosed allowed availability reason allows independent source checks; untrusted results never adopted
- **可观察结果**：Fallback cause is verified and untrusted results are unused Inspect only diagnosed allowed availability reason allows independent source checks; untrusted results never adopted
- **禁止结果**：Fallback using untrusted results；Availability fallback without reliable diagnosis
- **原前态**：Query unavailable
- **原后态**：Recorded independent current-source verification

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-D0C9017CF9BC → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-D15067654AC2（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-D15067654AC2 / A-9A0998F5B85E（仅溯源，不导入旧运行权限）。
- **前提**：Generic blocked/nonzero/empty without reliable cause
- **发生时机**：When generic blocked, nonzero exit or empty candidates occur without a valid cause diagnosis; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Do not infer entrypoint unavailable from those signals alone; treat as unidentified failure and stop affected judgment until corrected or validly diagnosed; never disable validation to eliminate failure blocked unknown_failure, no entrypoint-unavailable assumption; readonly diagnosis may refine reason but no validation disabling
- **可观察结果**：Undiagnosed failures remain stopped and validation stays enabled Inspect blocked unknown_failure, no entrypoint-unavailable assumption; readonly diagnosis may refine reason but no validation disabling
- **禁止结果**：Assuming unavailable from blocked/nonzero/empty alone；Disabling validation to hide failure
- **原前态**：Availability cause unproven
- **原后态**：Affected judgment stopped pending correction/diagnosis

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-D15067654AC2 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

**正式ID边界**：以上旧条款标签和文本锚点用于准确表达前置语义；它们不是新正式 O-ID，不可直接把历史 O-ID 或 SM 锚点字符串当作新计划 depends_on。若未来获准生成，仍须对真实生成的义务ID、对应关系、无环闭包和切片依赖做既有流程核对；本草稿不声称编译器会导入旁置映射文件。

## SM-K38

**本块生效范围（待确认输入）**：仅针对本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。BMAD 专属新增知识查询交付已转部署侧；不得据旧来源、交叉引用或旧角色启动任何 BMAD skill、原生生成/补查、安装验证或内部 reviewer。已交付 PRD/SPEC/Architecture 只消费明确保留的内容，原文/原角色用于溯源，不要求再判断其是否需要审核或重新生成。保留 Windows 实机验证、权限/四维隔离、来源与字节完整性、查询30/60秒等原预算、development/auto 默认治理关闭、真实 VDD 消费及源码核查、失败/取消和历史证据保护。后续长流程执行预算与业务查询预算分别管理。

**来源角色与上下文归属**：本块是本次范围修订的完整作者输入，尚非正式合同或运行证明。本块下“有效条款明细”及“依赖表达”是本块需要消费的文本；旧 O/A/FI、原文件/原角色和旧引用只标识历史对应项，不成为本版正式ID，不恢复已移出的义务，不继承旧 receipt、RED、Q7/Q8 或审核权限。引用的原文行仅作保留来源，不优先于本块明确范围。

**有效条款范围**：本块对应 6 条旧条款的保留部分；该数量用于覆盖核对，不预设未来模型生成数量。

**逐字保留的旧来源行（仅溯源）**：
> | <a id="SM-K38"></a>K38 | source-bound constraint | derive from complete source | planning | _bmad-output/specs/spec-bmad-vdd-knowledge-query/failure-modes.md | Original role: normative_companion. Interpretation: Preserve all obligations, conditions, exceptions, quantities and prohibitions in the quoted source. Original IDs remain authority; SM is only a compiler anchor. Verbatim source (UTF-8, reversible HTML escaping):<br>## 结果类别与允许动作<br><br>&#124; 类别 &#124; 普通规划查询 / governance off &#124; governance on 或既有完整性门禁 &#124;<br>&#124; --- &#124; --- &#124; --- &#124;<br>&#124; 有效命中 &#124; 读取相关原始来源，按合同核对 hash，记录采纳/不采纳 &#124; 继续满足全部原有门禁 &#124;<br>&#124; 未命中 / 低置信 / 歧义 &#124; 定向核查当前源码；不据此证明能力不存在 &#124; required module 未满足按原合同阻断 &#124;<br>&#124; 已识别过期 / 选中来源变化 &#124; 记录 degraded，核实当前相关来源，不把失效候选作为事实 &#124; 只允许现行 source_refresh/修复路径，不扩大选中集合或改发布身份 &#124;<br>&#124; 已确认未配置 / 不可用 / 超时 &#124; 有原因的独立源码核查；必要事实未知则保留未决并停止相关判断 &#124; 不绕过 required gate &#124;<br>&#124; 非法请求/配置 / 损坏或未知输出 / 损坏绑定 / 越界 / 策略拒绝 &#124; 停止消费并报错；修正后继续受影响判断 &#124; fail-closed &#124;<br>&#124; 用户取消 &#124; 停止、未完成、不自动重试 &#124; 保持已有取消/恢复边界 &#124;<br><br> |

### 有效条款明细

### 条款 O-1907855D27FB（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-1907855D27FB / A-D6B079A5F69F（仅溯源，不导入旧运行权限）。
- **前提**：Invalid request/config or denied policy/path
- **发生时机**：When request/configuration is illegal, output unknown/corrupt, binding damaged, scope exceeded or policy rejects; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Stop consumption and report error; affected judgment can continue only after correction; gated mode fails closed stop consumption, error retained and affected judgments cannot resume until correction; fail closed on gates
- **可观察结果**：Each listed error remains blocking until corrected Inspect stop consumption, error retained and affected judgments cannot resume until correction; fail closed on gates
- **禁止结果**：Availability downgrade for invalid/denied result；Affected judgment resumes before correction
- **原前态**：Untrusted query result
- **原后态**：Stop and report error

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-1907855D27FB → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-295A1ED8402C（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-295A1ED8402C / A-0CC6BA1A4A87（仅溯源，不导入旧运行权限）。
- **前提**：Cancel active query then resume same task
- **发生时机**：When user cancels; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Stop and retain incomplete status without automatic retry; preserve existing cancellation/recovery boundaries stop owned child, incomplete history preserved, no automatic retry or quota reset
- **可观察结果**：Cancellation has no automatic retry or false completion Inspect stop owned child, incomplete history preserved, no automatic retry or quota reset
- **禁止结果**：Automatic retry；Violation of existing recovery boundary
- **原前态**：Query active or partially complete
- **原后态**：Stopped incomplete

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-295A1ED8402C → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-5E6CC5C750BC（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-5E6CC5C750BC / A-8ACF89903A5C（仅溯源，不导入旧运行权限）。
- **前提**：Diagnosed availability failure with independent source read success/failure
- **发生时机**：When configuration absence, unavailability or timeout is confirmed; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Record reason and independently verify source; retain unresolved necessary facts and stop related judgments; do not bypass required gates record real reason, direct source identity and unresolved necessary fact; no related judgment or gate bypass on failed read
- **可观察结果**：Fallback preserves necessary-fact blockers and required gates Inspect record real reason, direct source identity and unresolved necessary fact; no related judgment or gate bypass on failed read
- **禁止结果**：Continuing related judgment with necessary fact unknown；Required gate bypass
- **原前态**：Query cannot provide facts
- **原后态**：Reasoned independent source verification

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-5E6CC5C750BC → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-6ECFC199C2D2（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-6ECFC199C2D2 / A-A354334F8B3D（仅溯源，不导入旧运行权限）。
- **前提**：Recognized stale or selected-source change after trust checks
- **发生时机**：When recognized stale input or selected-source change occurs; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Record degraded and verify current relevant sources without adopting invalid candidates as facts; gated mode only uses existing source_refresh/repair and cannot expand selected set or change publication identity degraded record with no invalid-candidate adoption; current direct read, gated owner source_refresh only, selected set/publication identity unchanged
- **可观察结果**：Refresh is bounded to existing selected scope and truthful publication identity Inspect degraded record with no invalid-candidate adoption; current direct read, gated owner source_refresh only, selected set/publication identity unchanged
- **禁止结果**：Invalid candidate used as fact；Expanded selected set；Changed publication identity；Non-owner refresh path
- **原前态**：Prior candidates may be invalid
- **原后态**：Degraded and current sources verified

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-6ECFC199C2D2 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-8FD1E5E14DCA（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-8FD1E5E14DCA / A-E77863D501ED（仅溯源，不导入旧运行权限）。
- **前提**：Valid matched candidate with correct/mutated source
- **发生时机**：When a valid hit occurs; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Read relevant original sources, verify hashes under the contract and record adoption/rejection; governance-on or integrity-gated paths still satisfy every original gate hash before excerpt, actual read before native adoption/rejection; mutation blocks and on-mode all original gates retained
- **可观察结果**：Read/hash/adoption evidence exists without gate bypass Inspect hash before excerpt, actual read before native adoption/rejection; mutation blocks and on-mode all original gates retained
- **禁止结果**：Adoption without source/hash verification；Bypassing original gate
- **原前态**：Sources located but not adopted
- **原后态**：Read and hash-checked adoption

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-8FD1E5E14DCA → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-C9A0D76031FA（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-C9A0D76031FA / A-C55745631AFC（仅溯源，不导入旧运行权限）。
- **前提**：Legal empty, nonempty insufficient, low confidence and ambiguity
- **发生时机**：When no match, low confidence or ambiguity occurs; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Perform targeted current-source verification without inferring capability absence; unsatisfied required modules block under original contracts targeted source verification required, never absence inference; unsatisfied required module remains blocked
- **可观察结果**：Source check occurs while unsatisfied required modules remain blocked Inspect targeted source verification required, never absence inference; unsatisfied required module remains blocked
- **禁止结果**：Query miss proves absence；Unsatisfied required module bypass
- **原前态**：Capability existence unproven
- **原后态**：Current-source checks and gate preservation

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-C9A0D76031FA → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

**正式ID边界**：以上旧条款标签和文本锚点用于准确表达前置语义；它们不是新正式 O-ID，不可直接把历史 O-ID 或 SM 锚点字符串当作新计划 depends_on。若未来获准生成，仍须对真实生成的义务ID、对应关系、无环闭包和切片依赖做既有流程核对；本草稿不声称编译器会导入旁置映射文件。

## SM-K39

**本块生效范围（待确认输入）**：仅针对本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。BMAD 专属新增知识查询交付已转部署侧；不得据旧来源、交叉引用或旧角色启动任何 BMAD skill、原生生成/补查、安装验证或内部 reviewer。已交付 PRD/SPEC/Architecture 只消费明确保留的内容，原文/原角色用于溯源，不要求再判断其是否需要审核或重新生成。保留 Windows 实机验证、权限/四维隔离、来源与字节完整性、查询30/60秒等原预算、development/auto 默认治理关闭、真实 VDD 消费及源码核查、失败/取消和历史证据保护。后续长流程执行预算与业务查询预算分别管理。

**来源角色与上下文归属**：本块是本次范围修订的完整作者输入，尚非正式合同或运行证明。本块下“有效条款明细”及“依赖表达”是本块需要消费的文本；旧 O/A/FI、原文件/原角色和旧引用只标识历史对应项，不成为本版正式ID，不恢复已移出的义务，不继承旧 receipt、RED、Q7/Q8 或审核权限。引用的原文行仅作保留来源，不优先于本块明确范围。

**有效条款范围**：本块对应 4 条旧条款的保留部分；该数量用于覆盖核对，不预设未来模型生成数量。

**逐字保留的旧来源行（仅溯源）**：
> | <a id="SM-K39"></a>K39 | source-bound constraint | derive from complete source | planning | _bmad-output/specs/spec-bmad-vdd-knowledge-query/failure-modes.md | Original role: normative_companion. Interpretation: Preserve all obligations, conditions, exceptions, quantities and prohibitions in the quoted source. Original IDs remain authority; SM is only a compiler anchor. Verbatim source (UTF-8, reversible HTML escaping):<br>## 配置与诊断边界<br><br>缺失必要配置须明确诊断，不能报告成功；能确认“未配置”时适用可用性处理。非法或不可读/损坏的已有配置不是正常未配置。不支持的消费者不准冒用已支持身份；策略拒绝保持 fail-closed。Architecture 定义实际诊断如何区分这些情况，不能通过模型自行猜因或空候选推断。<br><br> |

### 有效条款明细

### 条款 O-3879A47B5106（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-3879A47B5106 / A-7FC4DA693BA0（仅溯源，不导入旧运行权限）。
- **前提**：Adapter branch table against adopted AD7 and real core outputs
- **发生时机**：When distinguishing configuration/consumer failure causes; evaluate in planning/terminal artifact inspection before admitting its downstream conclusion
- **完整要求**：Architecture defines actual diagnostics distinguishing these cases; model guesses and empty candidates cannot establish the cause mapping derives actual diagnostics, not model guess or [] alone; exact insufficient_match split and higher priorities preserved
- **可观察结果**：Cause classification follows actual mapped diagnostics Inspect mapping derives actual diagnostics, not model guess or [] alone; exact insufficient_match split and higher priorities preserved
- **禁止结果**：Model-invented cause；Cause inferred from empty candidates
- **原前态**：Actual diagnostics required
- **原后态**：Architecture-defined distinction used

### 条款 O-65F3B954FB04（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-65F3B954FB04 / A-4B02F6776EDD（仅溯源，不导入旧运行权限）。
- **前提**：Unknown consumer or bmad-planning without admitted policy
- **发生时机**：When consumer is unsupported or policy rejects; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Unsupported consumer must not borrow a supported identity; policy rejection remains fail-closed blocked, never retry as vdd/bootstrap or downgrade policy denial
- **可观察结果**：No identity substitution or policy bypass occurs Inspect blocked, never retry as vdd/bootstrap or downgrade policy denial
- **禁止结果**：Consumer impersonation；Policy rejection downgraded
- **原前态**：Requested identity not permitted
- **原后态**：Fail-closed without impersonation

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K53](07-shared-design.md#SM-K53) 中旧条款 O-F96ECD3253A2 对应的保留行为：VDD 继续真实使用 vdd，身份与 stage 分开，其他既有消费者不变。。适用条件与界限：目标缩为VDD实际vdd身份和stage分离/不冒用既有其他身份；保留请求/策略/来源规则以其为输入，不恢复bmad-planning消费者。 原映射 O-65F3B954FB04 → O-F96ECD3253A2 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 实际来源/时效核对路径：knowledge/contracts/knowledge-locator-request.v1.schema.json、knowledge/policies/consumer-policies.v2.json、scripts/toolchain/knowledge_query/adapter.py。这些是来源绑定，不是新增发布任务。

### 条款 O-6FF05E83E725（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-6FF05E83E725 / A-55CB383DEEC7（仅溯源，不导入旧运行权限）。
- **前提**：Confirmed missing required configuration
- **发生时机**：When necessary configuration is missing; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Clearly diagnose missing required configuration without reporting success; availability treatment applies only when unconfigured is confirmed unavailable/config_missing not success; no fallback before absence confirmed
- **可观察结果**：Missing configuration has a confirmed diagnosis before fallback Inspect unavailable/config_missing not success; no fallback before absence confirmed
- **禁止结果**：Missing configuration reported success；Fallback without confirmation
- **原前态**：Configuration unavailable
- **原后态**：Explicit missing diagnosis

- **移除旧前置的界限（沿用前版草稿建议，待本草稿整体确认）**：原映射 O-6FF05E83E725 → O-DCF68B1ABA8F 不作为本条在新范围内的实施前置。理由：确认配置缺失即应给 config_missing；不能先要求生产一个合法发布才能诊断。 删除的是与policy生产的错误阶段前置，不删除自身的安全/解析断言，也不删除其他需要policy的边。；本条其余权限、来源完整性、拒绝、生产负责方和时效约束仍按有效明细保留。 实际来源/时效核对路径：scripts/toolchain/knowledge_query/adapter.py、knowledge/planning-query.toml。这些是来源绑定，不是新增发布任务。

### 条款 O-D1E9D110AFB1（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-D1E9D110AFB1 / A-71802CDCA6FC（仅溯源，不导入旧运行权限）。
- **前提**：Existing file unreadable, malformed, unknown field or invalid value
- **发生时机**：When an existing configuration is illegal, unreadable or corrupt; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Do not classify illegal, unreadable or corrupt existing configuration as ordinary unconfigured blocked invalid_config, never config_missing/unconfigured
- **可观察结果**：Invalid-existing and absent configurations have distinct outcomes Inspect blocked invalid_config, never config_missing/unconfigured
- **禁止结果**：Corrupt/unreadable/illegal existing config treated as ordinary absence
- **原前态**：Configuration exists but untrusted
- **原后态**：Not classified unconfigured

- **移除旧前置的界限（沿用前版草稿建议，待本草稿整体确认）**：原映射 O-D1E9D110AFB1 → O-DCF68B1ABA8F 不作为本条在新范围内的实施前置。理由：现存配置非法/不可读/损坏的拒绝由本地配置解析判定，不以任何有效代次为前提。 删除的是与policy生产的错误阶段前置，不删除自身的安全/解析断言，也不删除其他需要policy的边。；本条其余权限、来源完整性、拒绝、生产负责方和时效约束仍按有效明细保留。 实际来源/时效核对路径：scripts/toolchain/knowledge_query/adapter.py、knowledge/planning-query.toml。这些是来源绑定，不是新增发布任务。

**正式ID边界**：以上旧条款标签和文本锚点用于准确表达前置语义；它们不是新正式 O-ID，不可直接把历史 O-ID 或 SM 锚点字符串当作新计划 depends_on。若未来获准生成，仍须对真实生成的义务ID、对应关系、无环闭包和切片依赖做既有流程核对；本草稿不声称编译器会导入旁置映射文件。

## SM-K40

**本块生效范围（待确认输入）**：仅针对本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。BMAD 专属新增知识查询交付已转部署侧；不得据旧来源、交叉引用或旧角色启动任何 BMAD skill、原生生成/补查、安装验证或内部 reviewer。已交付 PRD/SPEC/Architecture 只消费明确保留的内容，原文/原角色用于溯源，不要求再判断其是否需要审核或重新生成。保留 Windows 实机验证、权限/四维隔离、来源与字节完整性、查询30/60秒等原预算、development/auto 默认治理关闭、真实 VDD 消费及源码核查、失败/取消和历史证据保护。后续长流程执行预算与业务查询预算分别管理。

**来源角色与上下文归属**：本块是本次范围修订的完整作者输入，尚非正式合同或运行证明。本块下“有效条款明细”及“依赖表达”是本块需要消费的文本；旧 O/A/FI、原文件/原角色和旧引用只标识历史对应项，不成为本版正式ID，不恢复已移出的义务，不继承旧 receipt、RED、Q7/Q8 或审核权限。引用的原文行仅作保留来源，不优先于本块明确范围。

**有效条款范围**：本块对应 5 条旧条款的保留部分；该数量用于覆盖核对，不预设未来模型生成数量。

**逐字保留的旧来源行（仅溯源）**：
> | <a id="SM-K40"></a>K40 | source-bound constraint | derive from complete source | planning | _bmad-output/specs/spec-bmad-vdd-knowledge-query/failure-modes.md | Original role: normative_companion. Interpretation: Preserve all obligations, conditions, exceptions, quantities and prohibitions in the quoted source. Original IDs remain authority; SM is only a compiler anchor. Verbatim source (UTF-8, reversible HTML escaping):<br>## 记录与恢复<br><br>记录查询主题、消费者、结果类别/原诊断、有关来源定位和读取身份、结论/用途或未完成原因。被拒绝的越界内容不得输出；安全诊断仅说明受影响范围与错误类型。预算耗尽、超时和取消不能启动无限重试或自动知识发布。<br><br>相关来源/意图未变化可复用有效记录；相关变化只补受影响部分。无关代次变化不单独使整个需求失效。需要强制治理修复时仍遵守已有合同，不借“轻量查询”跳过它。<br><br> |

### 有效条款明细

### 条款 O-2F2D26DDB39F（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-2F2D26DDB39F / A-9C48607D8D1D（仅溯源，不导入旧运行权限）。
- **前提**：Governance-on required repair/freeze conditions
- **发生时机**：When formal governance repair is required; evaluate in planning/terminal artifact inspection before admitting its downstream conclusion
- **完整要求**：Follow existing mandatory governance repair contracts without using lightweight query as a bypass existing owner repair contract enforced; lightweight query cannot waive mandatory action
- **可观察结果**：Required formal repair is completed through its existing contract Inspect existing owner repair contract enforced; lightweight query cannot waive mandatory action
- **禁止结果**：Lightweight-query label bypasses mandatory repair
- **原前态**：Existing repair contract applies
- **原后态**：Repair contract followed

### 条款 O-3BF54CFB6A2C（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-3BF54CFB6A2C / A-2FD714DFFB39（仅溯源，不导入旧运行权限）。
- **前提**：Same task read-set resume and unrelated generation change contrasted relevant input change
- **发生时机**：When related sources/intent are unchanged or change; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Reuse valid records if relevant sources/intent unchanged; supplement only affected parts on relevant change; unrelated generation change alone does not invalidate entire requirement reuse valid record with permission/dependency check; only affected conclusions refresh, no whole-requirement invalidation
- **可观察结果**：Recovery remains local and unrelated generation drift does not cause full invalidation Inspect reuse valid record with permission/dependency check; only affected conclusions refresh, no whole-requirement invalidation
- **禁止结果**：Whole requirement invalidated solely by unrelated generation change；Unrelated parts refreshed
- **原前态**：Prior valid records available
- **原后态**：Valid reuse or affected-only supplement

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-3BF54CFB6A2C → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-99AF9B9AC486（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-99AF9B9AC486 / A-B7AB5185305B（仅溯源，不导入旧运行权限）。
- **前提**：Denied source contains sentinel and exception includes sensitive environment
- **发生时机**：When reporting denied out-of-bounds content; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Never output denied out-of-bounds content; safe diagnostics describe only affected scope and error type safe enum/hash scope/type diagnostic omits content/credentials/full paths/environment
- **可观察结果**：No denied content appears in diagnostic output Inspect safe enum/hash scope/type diagnostic omits content/credentials/full paths/environment
- **禁止结果**：Denied content disclosure
- **原前态**：Content not authorized
- **原后态**：Only safe diagnostic emitted

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-99AF9B9AC486 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-B9380328BF22（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-B9380328BF22 / A-9E2151BC0D72（仅溯源，不导入旧运行权限）。
- **前提**：Success/degraded/unavailable/blocked/cancelled/exhausted recovery records
- **发生时机**：When recording a query or unfinished attempt; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Record query topic, consumer, result category/original diagnostic, relevant source location/read identity and conclusion/use or unfinished reason topic,consumer,raw/mapped status,source/read identity,conclusion/use or incomplete reason retained in existing record
- **可观察结果**：Record contains each applicable field Inspect topic,consumer,raw/mapped status,source/read identity,conclusion/use or incomplete reason retained in existing record
- **禁止结果**：Missing outcome provenance or unfinished reason
- **原前态**：Result or interruption exists
- **原后态**：Traceable record retained

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-B9380328BF22 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-F031D2D60A88（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-F031D2D60A88 / A-BBD8104BB5D3（仅溯源，不导入旧运行权限）。
- **前提**：Budget exhaustion,timeout,cancel sequence
- **发生时机**：When budget exhausts, timeout occurs or user cancels; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：None of budget exhaustion, timeout or cancellation may launch infinite retries or automatic knowledge publication no infinite retry or publication, shared episode remains bounded
- **可观察结果**：Each listed trigger has bounded recovery without publication Inspect no infinite retry or publication, shared episode remains bounded
- **禁止结果**：Infinite retry；Automatic knowledge publication
- **原前态**：Query cannot continue normally
- **原后态**：No infinite retry or auto publication

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-F031D2D60A88 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

**正式ID边界**：以上旧条款标签和文本锚点用于准确表达前置语义；它们不是新正式 O-ID，不可直接把历史 O-ID 或 SM 锚点字符串当作新计划 depends_on。若未来获准生成，仍须对真实生成的义务ID、对应关系、无环闭包和切片依赖做既有流程核对；本草稿不声称编译器会导入旁置映射文件。

## SM-K41

**本块生效范围（待确认输入）**：仅针对本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。BMAD 专属新增知识查询交付已转部署侧；不得据旧来源、交叉引用或旧角色启动任何 BMAD skill、原生生成/补查、安装验证或内部 reviewer。已交付 PRD/SPEC/Architecture 只消费明确保留的内容，原文/原角色用于溯源，不要求再判断其是否需要审核或重新生成。保留 Windows 实机验证、权限/四维隔离、来源与字节完整性、查询30/60秒等原预算、development/auto 默认治理关闭、真实 VDD 消费及源码核查、失败/取消和历史证据保护。后续长流程执行预算与业务查询预算分别管理。

**来源角色与上下文归属**：本块是本次范围修订的完整作者输入，尚非正式合同或运行证明。本块下“有效条款明细”及“依赖表达”是本块需要消费的文本；旧 O/A/FI、原文件/原角色和旧引用只标识历史对应项，不成为本版正式ID，不恢复已移出的义务，不继承旧 receipt、RED、Q7/Q8 或审核权限。引用的原文行仅作保留来源，不优先于本块明确范围。

**有效条款范围**：本块对应 12 条旧条款的保留部分；该数量用于覆盖核对，不预设未来模型生成数量。

**逐字保留的旧来源行（仅溯源）**：
> | <a id="SM-K41"></a>K41 | source-bound constraint | derive from complete source | planning | _bmad-output/specs/spec-bmad-vdd-knowledge-query/failure-modes.md | Original role: normative_companion. Interpretation: Preserve all obligations, conditions, exceptions, quantities and prohibitions in the quoted source. Original IDs remain authority; SM is only a compiler anchor. Verbatim source (UTF-8, reversible HTML escaping):<br>## 兼容策略与诊断映射<br><br>既有 Locator 调用方继续得到原有字段、状态含义及退出码语义，不通过删除、重命名或重新解释现有返回值完成本增量。新增消费者可以在外置、显式接入的只读适配层得到细化诊断；原始业务状态和诊断依据必须保留。Architecture 确定实际表示与调用边界，不能改变以下映射或把新细化状态强塞给未迁移的消费者。<br><br>&#124; 已核实的诊断依据 &#124; 消费者归类 &#124; 停止/继续条件 &#124;<br>&#124; --- &#124; --- &#124; --- &#124;<br>&#124; 命中且结构/策略/发布/读取完整性成立 &#124; 有效命中 &#124; 来源核对后才能采纳 &#124;<br>&#124; 有效未命中、低置信或歧义 &#124; 未命中/低置信/歧义 &#124; 定向源码核查；required gate 仍按旧合同 &#124;<br>&#124; 能识别的索引过期或同一选中来源字节变化 &#124; 已识别过期/来源变化 &#124; degraded；只能核实当前来源或走已允许刷新 &#124;<br>&#124; 明确缺少配置项/入口；已确认不可用；已确认超时 &#124; 已确认未配置/不可用/超时 &#124; 停止使用本次结果；独立核查，必要事实仍未知则停 &#124;<br>&#124; 配置语法或范围非法、已有配置损坏/不可读、消费者不受支持/策略拒绝 &#124; 不可信失败 &#124; 报错，修正后才继续 &#124;<br>&#124; 发布/目录/策略/投影绑定损坏、越界、来源完整性校验不成立 &#124; 不可信失败 &#124; 不采纳、不披露越界内容，按原 gate 阻断 &#124;<br>&#124; 解析失败、未知状态、退出失败原因未知、只有通用 blocked 而无可信归因 &#124; 未识别失败 &#124; 与不可信失败相同，不推测可用性降级 &#124;<br>&#124; 用户取消 &#124; 取消 &#124; 未完成，无后台重试；保留先前已观察错误 &#124;<br><br>非零退出但原因确认为入口不可用或超时，才进入相应可用性类别；未知原因不能凭退出码降级。未经允许的来源/hash 不一致与已识别过期不同：只有合同允许且可归因的相关变化才适用 degraded/source_refresh，其余完整性失败保持阻断。<br><br> |

### 有效条款明细

### 条款 O-1AC1A5752B1A（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-1AC1A5752B1A / A-84A7B5296778（仅溯源，不导入旧运行权限）。
- **前提**：Cancel after observed validation error
- **发生时机**：When user cancels; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Record cancellation as incomplete without background retry and retain prior observed errors cancelled/incomplete, prior error retained, no background retry
- **可观察结果**：Cancellation retains error history and does not retry Inspect cancelled/incomplete, prior error retained, no background retry
- **禁止结果**：Background retry；Erasing observed errors
- **原前态**：Query unfinished
- **原后态**：Cancelled incomplete

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-1AC1A5752B1A → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-325E95636B4D（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-325E95636B4D / A-CC671F44BAAD（仅溯源，不导入旧运行权限）。
- **前提**：Binding/hash mismatch or denied path plus []
- **发生时机**：When publication/directory/policy/projection binding corrupt, path out of bounds or source integrity fails; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Do not adopt or reveal out-of-bounds content; block under original gate blocked original gate, no candidate adoption or denied content disclosure
- **可观察结果**：Bindings and integrity failures cannot yield adopted content Inspect blocked original gate, no candidate adoption or denied content disclosure
- **禁止结果**：Adoption of untrusted content；Out-of-bounds disclosure；Original gate bypass
- **原前态**：Untrusted source
- **原后态**：Untrusted failure

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-325E95636B4D → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-370A27148C69（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-370A27148C69 / A-8EB220D31236（仅溯源，不导入旧运行权限）。
- **前提**：Old CLI replay against same fixtures before/after extracted shared preflight
- **发生时机**：When adding finer consumer diagnostics; evaluate in planning/terminal artifact inspection before admitting its downstream conclusion
- **完整要求**：Preserve existing fields, status meanings and exit semantics; do not delete, rename or reinterpret existing return values; do not force new finer states on unmigrated consumers fields/status meanings/exit codes equal; unmigrated consumers never see new planning-query outcomes
- **可观察结果**：Legacy callers observe the same contract Inspect fields/status meanings/exit codes equal; unmigrated consumers never see new planning-query outcomes
- **禁止结果**：Deleted/renamed/reinterpreted existing return values；New states forced on unmigrated consumer
- **原前态**：Existing Locator callers use current contract
- **原后态**：Legacy contract unchanged

### 条款 O-4D7902276417（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-4D7902276417 / A-4BD4D7CCB0D3（仅溯源，不导入旧运行权限）。
- **前提**：Attributable permitted selected-source change versus unauthorized hash mutation
- **发生时机**：When source/hash mismatch occurs; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Only contract-allowed attributable relevant changes qualify for degraded/source_refresh; other unauthorized source/hash mismatches remain blocking integrity failures only allowed change degraded/source_changed or source_refresh; unauthorized mismatch integrity_failed blocked
- **可观察结果**：Mismatch handling checks authorization and attribution before refresh Inspect only allowed change degraded/source_changed or source_refresh; unauthorized mismatch integrity_failed blocked
- **禁止结果**：All hash mismatches treated as stale；Unauthorized mismatch downgraded
- **原前态**：May be allowed change or integrity failure
- **原后态**：Only attributable authorized change may degrade

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-4D7902276417 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-6A0DFDBB434A（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-6A0DFDBB434A / A-E472AC9A6440（仅溯源，不导入旧运行权限）。
- **前提**：Malformed config/request or unsupported identity
- **发生时机**：When syntax/scope illegal, existing configuration corrupt/unreadable, consumer unsupported or policy denied; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Report error as untrusted failure and continue only after correction blocked invalid_config/invalid_request/policy_denied as evidenced; resume only after correction
- **可观察结果**：Every listed failure remains blocked until corrected Inspect blocked invalid_config/invalid_request/policy_denied as evidenced; resume only after correction
- **禁止结果**：Availability downgrade for invalid or unsupported input
- **原前态**：Untrusted request or configuration
- **原后态**：Untrusted failure

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-6A0DFDBB434A → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-7D56282FCA48（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-7D56282FCA48 / A-105DA380D784（仅溯源，不导入旧运行权限）。
- **前提**：Legal zero/nonzero insufficient, low confidence and ambiguity after prerequisites
- **发生时机**：When valid no-match, low-confidence or ambiguity occurs; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Classify no-match/low-confidence/ambiguity, perform targeted source check and retain required gates under old contracts exact AD7 pair, targeted source check, existing required gate remains blocking
- **可观察结果**：No result category bypasses required gate Inspect exact AD7 pair, targeted source check, existing required gate remains blocking
- **禁止结果**：Required gate bypass
- **原前态**：Query valid but inconclusive
- **原后态**：Insufficient category and direct check

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-7D56282FCA48 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-8299476377C3（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-8299476377C3 / A-B63FC608FBBF（仅溯源，不导入旧运行权限）。
- **前提**：Nonzero exit with confirmed timeout/unavailable versus unknown cause
- **发生时机**：When process exits nonzero; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Only confirmed entrypoint unavailable or timeout may enter corresponding availability category; unknown causes cannot be downgraded based on exit code only positive diagnosed cause unavailable/timeout or backend_unavailable; unknown blocked unknown_failure
- **可观察结果**：Nonzero exit without confirmed allowed cause remains blocked Inspect only positive diagnosed cause unavailable/timeout or backend_unavailable; unknown blocked unknown_failure
- **禁止结果**：Nonzero exit alone interpreted as unavailable
- **原前态**：Exit code alone lacks cause
- **原后态**：Availability only on confirmed cause

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-8299476377C3 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-8C43A73A097A（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-8C43A73A097A / A-C23CA6A8F3A1（仅溯源，不导入旧运行权限）。
- **前提**：New adapter receives original CLI/raw diagnostic
- **发生时机**：When new consumers receive refined diagnostics; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Allow refined diagnostics only through external explicitly integrated read-only adaptation retaining original business status and diagnostic evidence; Architecture chooses representation/call boundary without changing specified mapping external read-only adaptation retains raw status,exit,evidence_refs; fixed AD7 mapping without changing legacy caller contract
- **可观察结果**：Adapter output is traceable to unchanged original status and actual evidence Inspect external read-only adaptation retains raw status,exit,evidence_refs; fixed AD7 mapping without changing legacy caller contract
- **禁止结果**：Losing original business status/evidence；Changing required mapping
- **原前态**：Actual original status and evidence available
- **原后态**：Explicit read-only adapter preserves originals

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-8C43A73A097A → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-A06E38594D27（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-A06E38594D27 / A-8ED113241EE6（仅溯源，不导入旧运行权限）。
- **前提**：Matched candidates before/after actual hash-verified read
- **发生时机**：When hit structure, policy, publication and read integrity all hold; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Classify as valid hit and adopt only after source verification hit/matched then native adoption only after read verification; no fabricated adapter adoption
- **可观察结果**：Adoption follows verification of all listed prerequisites and source Inspect hit/matched then native adoption only after read verification; no fabricated adapter adoption
- **禁止结果**：Adoption before source verification
- **原前态**：Valid hit not yet adopted
- **原后态**：Valid-hit classification

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-A06E38594D27 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-AF2078FB2E4B（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-AF2078FB2E4B / A-5582203B4E80（仅溯源，不导入旧运行权限）。
- **前提**：Unknown status/exit/exception or mismatched outcome pair
- **发生时机**：When parsing fails, status unknown, exit failure cause unknown or generic blocked lacks trustworthy attribution; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Handle as untrusted failure without guessing availability degradation blocked/unknown_failure, no guessed availability
- **可观察结果**：Unknown failures remain blocking Inspect blocked/unknown_failure, no guessed availability
- **禁止结果**：Guessing unknown failure is availability degradation
- **原前态**：Cause unrecognized
- **原后态**：Unidentified failure treated as untrusted

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-AF2078FB2E4B → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-B0293AD5244C（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-B0293AD5244C / A-60AC7841CD9C（仅溯源，不导入旧运行权限）。
- **前提**：Diagnosed availability failure then independent read unresolved
- **发生时机**：When configuration item/entrypoint is explicitly absent or unavailability/timeout is confirmed; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Stop using this result, independently verify sources and stop dependent judgments if necessary facts remain unknown failed query output never facts; dependent unknown necessary facts stop judgment
- **可观察结果**：Confirmed availability fallback does not consume the failed result Inspect failed query output never facts; dependent unknown necessary facts stop judgment
- **禁止结果**：Using failed result；Continuing with necessary facts unknown
- **原前态**：Current result unusable
- **原后态**：Availability category

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-B0293AD5244C → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-CE5ECD0F87CE（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-CE5ECD0F87CE / A-E1CBC24CC84C（仅溯源，不导入旧运行权限）。
- **前提**：Recognized stale/change after trusted publication and permission checks
- **发生时机**：When index staleness or byte change in the same selected source is recognizable; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Classify recognized stale/source change as degraded; only verify current source or use already permitted refresh degraded stale_verified/source_changed, no stale adoption; current direct check or existing owner refresh only
- **可观察结果**：No unapproved refresh follows recognized change Inspect degraded stale_verified/source_changed, no stale adoption; current direct check or existing owner refresh only
- **禁止结果**：Unapproved refresh；Consuming stale candidate as fact
- **原前态**：Candidate may be stale
- **原后态**：Degraded current-source verification

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-CE5ECD0F87CE → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

**正式ID边界**：以上旧条款标签和文本锚点用于准确表达前置语义；它们不是新正式 O-ID，不可直接把历史 O-ID 或 SM 锚点字符串当作新计划 depends_on。若未来获准生成，仍须对真实生成的义务ID、对应关系、无环闭包和切片依赖做既有流程核对；本草稿不声称编译器会导入旁置映射文件。

## SM-K42

**本块生效范围（待确认输入）**：仅针对本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。BMAD 专属新增知识查询交付已转部署侧；不得据旧来源、交叉引用或旧角色启动任何 BMAD skill、原生生成/补查、安装验证或内部 reviewer。已交付 PRD/SPEC/Architecture 只消费明确保留的内容，原文/原角色用于溯源，不要求再判断其是否需要审核或重新生成。保留 Windows 实机验证、权限/四维隔离、来源与字节完整性、查询30/60秒等原预算、development/auto 默认治理关闭、真实 VDD 消费及源码核查、失败/取消和历史证据保护。后续长流程执行预算与业务查询预算分别管理。

**来源角色与上下文归属**：本块是本次范围修订的完整作者输入，尚非正式合同或运行证明。本块下“有效条款明细”及“依赖表达”是本块需要消费的文本；旧 O/A/FI、原文件/原角色和旧引用只标识历史对应项，不成为本版正式ID，不恢复已移出的义务，不继承旧 receipt、RED、Q7/Q8 或审核权限。引用的原文行仅作保留来源，不优先于本块明确范围。

**有效条款范围**：本块对应 6 条旧条款的保留部分；该数量用于覆盖核对，不预设未来模型生成数量。

**逐字保留的旧来源行（仅溯源）**：
> | <a id="SM-K42"></a>K42 | AD-7, AD-6 | derive from complete source | planning | _bmad-output/specs/spec-bmad-vdd-knowledge-query/failure-modes.md | Original role: normative_companion. Interpretation: Preserve all obligations, conditions, exceptions, quantities and prohibitions in the quoted source. Original IDs remain authority; SM is only a compiler anchor. Verbatim source (UTF-8, reversible HTML escaping):<br>## 合法零命中的唯一映射<br><br>依据 adopted architecture AD-7：先按 AD-6 完成请求、结构、完整性、权限及发布校验，并处理更高优先级的失败、过期、取消及预算状态。仅在此前置条件满足时，原始 status=insufficient_match 且 candidates=[] 唯一映射 no_match/empty；候选非空的 insufficient_match 才映射 degraded/insufficient_match。不得单凭空数组推断 no_match；未知或不一致状态仍 fail-closed。<br><br>两类均要求定向源码核查，不能证明能力不存在或绕过 required gate。原始 Locator 返回字段、status 和旧消费者语义保持不变。该规则明确未来适配器预期，不表示适配器已经实现。<br> |

### 有效条款明细

### 条款 O-0E473B3331BF（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-0E473B3331BF / A-256CF193592B（仅溯源，不导入旧运行权限）。
- **前提**：Unknown/mismatched status with empty array
- **发生时机**：When empty candidates occur with unknown or inconsistent state; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Never infer no_match from an empty array alone; unknown or inconsistent states fail closed blocked unknown_failure; [] alone not no_match proof
- **可观察结果**：Unknown/inconsistent state remains blocked despite empty candidates Inspect blocked unknown_failure; [] alone not no_match proof
- **禁止结果**：Empty array converts unknown/inconsistent state to no_match
- **原前态**：State not safely classifiable
- **原后态**：Fail-closed

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-0E473B3331BF → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-0EECFA4AF377（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-0EECFA4AF377 / A-9FC457F22D6C（仅溯源，不导入旧运行权限）。
- **前提**：Empty candidate array combined with each invalid request, structure/hash/policy/publication failure, stale/cancel/budget state
- **发生时机**：Before classifying insufficient_match as an empty result; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Complete AD-6 request, structure, integrity, permission and publication checks and handle higher-priority failure, staleness, cancellation and budget states before applying AD-7 empty-result mapping each higher-priority condition handled before legal zero-hit mapping; none swallowed by []
- **可观察结果**：Empty-result mapping occurs only after all stated prerequisites Inspect each higher-priority condition handled before legal zero-hit mapping; none swallowed by []
- **禁止结果**：Empty list overrides failure, stale, cancellation or budget state
- **原前态**：Raw result available
- **原后态**：Higher-priority checks resolved first

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-0EECFA4AF377 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-74A2254C30B4（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-74A2254C30B4 / A-B70CA1FCCA52（仅溯源，不导入旧运行权限）。
- **前提**：Legal empty and nonempty insufficient results with required module absent
- **发生时机**：When either no_match/empty or degraded/insufficient_match is emitted; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Both categories require targeted source checks and neither proves capability absence or bypasses required gates both targeted source checks, no absence inference and no required gate bypass
- **可观察结果**：Both branches preserve source verification and required-gate enforcement Inspect both targeted source checks, no absence inference and no required gate bypass
- **禁止结果**：Either category used as proof of absence；Required gate bypass
- **原前态**：Capability presence unresolved
- **原后态**：Targeted source verification

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-74A2254C30B4 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-7DF0A2364C34（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-7DF0A2364C34 / A-9A8642956082（仅溯源，不导入旧运行权限）。
- **前提**：Nonempty insufficient_match after trust checks without higher-priority condition
- **发生时机**：When prerequisites hold and raw status is insufficient_match with nonempty candidates; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Only nonempty insufficient_match maps to degraded/insufficient_match degraded/insufficient_match uniquely, never no_match/empty and no uncertain candidate adoption
- **可观察结果**：Nonempty insufficient result retains degraded/insufficient_match Inspect degraded/insufficient_match uniquely, never no_match/empty and no uncertain candidate adoption
- **禁止结果**：no_match/empty for nonempty insufficient_match
- **原前态**：Valid nonempty insufficient match

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-7DF0A2364C34 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

### 条款 O-81030489D3CB（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-81030489D3CB / A-C9D54179D23A（仅溯源，不导入旧运行权限）。
- **前提**：Legacy CLI regression and planning report
- **发生时机**：When specifying or implementing this future adapter rule; evaluate in planning/terminal artifact inspection before admitting its downstream conclusion
- **完整要求**：Keep original Locator return fields/status and old-consumer semantics unchanged; this rule specifies future adapter behavior and does not prove implementation already exists fields/status/exit/old consumers unchanged; planned adapter not reported already implemented
- **可观察结果**：Legacy results remain unchanged and status reporting distinguishes specified from implemented Inspect fields/status/exit/old consumers unchanged; planned adapter not reported already implemented
- **禁止结果**：Changed Locator legacy semantics；Claiming adapter already implemented from specification
- **原前态**：Original Locator and legacy callers exist
- **原后态**：Legacy contract unchanged

### 条款 O-E042DE12D872（旧ID溯源；保留）

- **适用限定**：仅适用于本次保留的 VDD 查询、QuickDev 既有冻结上下文/证据复用及实际共用设施。不得据本条启动 BMAD skill、原生生成/补查、安装验证或内部 reviewer；原有资源/typed 角色/owner 规则保持，已交付输入只作必要格式/引用/内容身份检查，不审核上游是否需要批准。
- **原义务引用**：O-E042DE12D872 / A-C88DEC915ABA（仅溯源，不导入旧运行权限）。
- **前提**：Actual core returns insufficient_match and [] after all prerequisites and no higher-priority signal
- **发生时机**：When prerequisites hold and raw status is insufficient_match with candidates=[]; evaluate in isolated integration execution before admitting its downstream conclusion
- **完整要求**：Map raw insufficient_match plus empty candidates uniquely to no_match/empty unique no_match/empty; not degraded insufficient_match; direct source checks and required gate retained
- **可观察结果**：Exactly no_match/empty is emitted for this valid case Inspect unique no_match/empty; not degraded insufficient_match; direct source checks and required gate retained
- **禁止结果**：degraded/insufficient_match for valid empty insufficient_match
- **原前态**：Valid insufficient match with zero candidates

- **依赖表达（沿用前版草稿建议，待本草稿整体确认）**：本条在依赖上游结果的保留分支，前置为 [SM-K25](03-behavior-contracts.md#SM-K25) 中旧条款 O-DCF68B1ABA8F 对应的保留行为：保留既有 VDD 等消费者的 policy/catalog/projection 同代 owner 生产与完整性。。适用条件与界限：依赖缩到现有VDD消费者的policy/catalog/projection与同代发布绑定保护；实际命中/来源读取/权限交集/复用必须消费该真实绑定，不要求为BMAD建立新generation。早期失败分支不因此被要求先有合法发布。 原映射 O-E042DE12D872 → O-DCF68B1ABA8F 仅用于历史对照；本次候选关系按此处实际保留生产者理解。 该关系只约束真正使用命中、来源读取、权限交集或有效记录复用的分支；本地早期配置失败、明确不可用、取消等分支不被要求先有合法发布；不得据此新建注册、自动发布或重建任务。 实际来源/时效核对路径：knowledge/policies/consumer-policies.v2.json、scripts/python/_knowledge_catalog_builder.py、scripts/python/_knowledge_locator_core.py。这些是来源绑定，不是新增发布任务。

**正式ID边界**：以上旧条款标签和文本锚点用于准确表达前置语义；它们不是新正式 O-ID，不可直接把历史 O-ID 或 SM 锚点字符串当作新计划 depends_on。若未来获准生成，仍须对真实生成的义务ID、对应关系、无环闭包和切片依赖做既有流程核对；本草稿不声称编译器会导入旁置映射文件。
