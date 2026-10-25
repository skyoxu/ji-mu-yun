# 需求目录正式范围修订：最小方案（待用户选择）

本文件仅为方案，不是需求目录、执行合同、范围批准回执或 plan-ready。未修改任何现有代码/测试/合同，未运行编译、测试、BMAD、reviewer/A-B 或 CI，未推送。前一步7处撤回保持原样。

## 建议结论

建议**不再扩展宿主协议**，采用“用户范围决定 + 完整有效输入 + 一个独立后继版本”的现有正式编译路线，但分步批准：

1. 先确认246保留/59缩减/25转部署侧的逐项清单；仅作者编写新有效输入及对照映射，不运行模型。
2. 输入完成后先给出实际可复用项、预计新请求范围和成本，再让用户决定是否启动一次现有 VDD 编译。
3. 只有得到该次明确授权，才通过现有公开入口发布新目录。旧目录原样留档，不在旧目录原位删改字段。

**不能把这条路线描述成只改84个 JSON 项的便宜增量修复。**现有通用入口会重新走本次后继计划的必要 V1/V3/V4/切片/交接门禁；V1可按条件复用，但V3/V4等不能预先保证只处理59项。本步没有执行它。若用户仍禁止启动这种 VDD 编译，则当前没有无改宿主、无重编译的正式发布路径；应继续停留在范围方案，而不是伪造已修订合同。

禁止重跑 BMAD PRD/SPEC/Architecture，不重新评审其产物是否获批。已交付文件只是原版输入/来源身份；本次用户变更决定其适用范围。

## 已核实入口与精确限制

| 入口 | 实际能力 | 对本次的结论 |
|---|---|---|
| `--repair-quick-dev-handoff-from` | `quick_dev_handoff.py:389–403` 的 semantic_projection 包含义务、oracle、membership/owner、依赖和proof；约503–504行拒绝语义变化 | 不能删除25项或缩减59项，不能借 runtime-red-intent 换 oracle。 |
| 普通 `--v3-contract-repair` | 修正 failed/unpublished candidate 的选定 V3；V1/来源冻结，原有完整校验仍需通过 | 不是 published 计划的用户范围扣减入口。 |
| `--repair-published-v3-from` | 验证旧源和发布见证，复用未选中 V3；`check_unaffected_published_semantics` 保护其余义务；CLI141–145行禁止 companions/source overrides | 本次包含新用户范围源、59语义缩减、25移出，且旧输入有7 companions，不能默认适用。 |
| `--published-v1-replacement` | `semantic_v3_contract_repair.py:526–561` 实际仅接受 FR-10 和固定旧ID `O-AF55FF781031`、`O-B5F365100D81`，替代必须 active 且有完整 V3 | 文档描述较宽，实际并非通用替代；本次 O IDs/SM 输入不匹配，也不能删除25项。不得改参数或冒用这两个ID。 |
| `--published-v1-split` | 同文件580–617行：一个原 active 项→至少两个同源 active 项，附完整V3 | 不能表达移出义务或新范围源优先级。 |
| `behavior_routing.deferred` | planning-operation.md 明确 deferral 不从最终覆盖集中减项 | 不能把25项藏入 deferred/skip 来满足旧Q8。 |
| 普通公开 `scripts/vdd/compile_plan.py` + `--v1-reuse-from-plan` | 新来源、新空输出目录；按锚点真实身份复用V1，其余走现有规范生产与门禁 | 现有通用可选路线；需要另行批准实际编译及其成本，不是本步执行。 |

核对的是源代码和现有 Markdown，不是一次编译运行成功证明。以上源码位于当前冻结宿主集成链 `127b26a4 → 81cfae78 → f57c2998`；本方案不改宿主。

## 旧版与新版本怎样落地

### 原版不动

- 保留旧 `execution-plans/2026-10-23-bmad-vdd-knowledge-query-runtime-r23/`、330项/O-A-assertion-FI关系、source-index、selection及原所有缓存/失败/取消/Q7/Q8记录。
- 旧 plan-ready/已发生运行仍是旧范围的历史事实；不改字段为 archived/success，不抹掉 reviewer 或失败，不改旧 hash。
- 原始需求 v1.0、PRD、SPEC/companions/selection、Architecture 原件保持；用户新范围通过独立记录补充，不回写或重新生成它们。
- 最终 GitHub 交付不再以旧330项目录作为当前活动执行合同；历史原件在原工作树和既有证据位置保全。是否另存历史指针/证据包在正式修订时明确，不在本步移动或删除历史。

### 未来最少作者输入（现在不创建）

1. **范围决定记录**：固定用户消息 `Sentinel_8442780ff29c8191bf283af41f9263d0`，原始输入hash、旧合同hash、已确认分类清单hash和适用优先级。它是来源，不是伪造授权/成功回执。
2. **有效规划输入**：使用既有 anchored Markdown/行为表格式，把246项原义完整保留、59项保留部分的义务/条件/例外/数量/禁止结果完整写出；25项只列在移出/设备侧台账，不作为当前 active 义务。不能只写“见旧SPEC/清单”。
3. **逐项 lineage 对照**：旧O/A/assertion/FI、原SM/FR/AC/AD与旧来源hash → 新有效锚点 → 编译后新O/A/FI/切片；转部署侧明确标记不是passed。清单是作者/audit材料，不能声称编译器会自动读取并应用它。

原7份 normative/adopted companion含有仍强制 BMAD hooks/注册/样例的内容，不能原封不动作为当前有效 companion再次激活，也不能只附一句“忽略BMAD”指望编译器自行覆盖。新的有效输入/必要 scoped companion必须实际承载完整保留内容，并明确以本次用户范围决定限定适用；原7份输入作为完整、hash-bound历史来源保留，**不改它们在原 typed 包中的角色、正文或selection**。这是本次范围修订的作者派生输入，不冒称重新跑过 BMAD 或发布了新 canonical SPEC。

必要 scoped companion仅用于完整承接保留的预算、失败优先级、身份/权限与源码核查规则；不引入新 schema/validator/治理框架。若有界入口大小或格式不满足，先报告，不截断或摘要代替义务。

### 新目录与唯一正式写入者

建议后继目录名（仅示意，未创建）：`execution-plans/2026-10-24-vdd-knowledge-query-scoped-v2/`。沿用VDD self-hosted计划形态；QuickDev standard运行profile与其分开，不通过降profile省门禁。

获得未来授权后，唯一生产入口仍为仓库根的 `scripts/vdd/compile_plan.py`，概念参数为：

```text
python3 -B scripts/vdd/compile_plan.py
  --requirements <new-effective-input.md>
  --out-dir <distinct-empty-successor>
  --profile self-hosted
  --v1-reuse-from-plan execution-plans/2026-10-23-bmad-vdd-knowledge-query-runtime-r23
  [--companion <only-current-effective-companion> ...]
```

这不是待自动执行的命令。不得导入/补造旧worker cache、手写compiler-state、伪造V4/plan-ready，或把旧原件改成新源身份。新source-index/hash必然如实改变，不能维持旧f840…身份来假装未变。

## 义务、oracle、owner、依赖和测试映射

- 246“保留”指业务语义保留，不保证编译ID/来源ref/依赖字段逐字不变。源路径重绑会重算ID，必须生成可审核旧→新映射，不能强制复用旧ID来获取证据。
- 59“缩减”要逐条给完整新 oracle；保留Windows、source/hash、四维隔离、blocked优先级、预算和治理底线，移出BMAD动作。若一项需拆分，映射可一对多，但各条件不能遗漏/重复实施。
- 25“转部署侧”保留原ID/理由于台账，但不进入新active验收集合；不能标为通过、deferred不阻塞、已有GREEN，或给其追加RED角色。
- 246+59=305仅为旧分类对应的**候选条款量**，不是承诺新编译器必须恰好产生305个O ID；任何合并/拆分必须有语义完整的对照，不能为了凑数手改输出。
- S1的新BMAD身份任务撤出，但一般发布保护不能丢。S4/S6需按实际保留的策略/身份/完整性消费者重分组，不整片删除或把BMAD ACL套给VDD。
- S5只保留VDD public compiler/adapter实际消费及caller记录等owner；去掉两外壳和PRD hook写界。`O-3DAF23250361`与`O-F7FB563211E4`的VDD采纳/拒绝/用途仍需真实caller，不能让adapter自证，也不能保留完整BMAD执行声明却跳过。
- S7保留共享诊断、来源、预算、取消/进程与配置；阶段/身份白名单未来缩到保留消费者。QuickDev仍消费已有frozen context及证据，未授权新live Locator阶段。
- 旧218条义务依赖都至少一端需缩减/转移，需要逐条对账，**不等于218条全部删除/失效或重跑**。新边由实际保留producer→consumer推导；不能保留悬空边、笼统all-to-all、无依据删边或造循环。
- 新切片重新产生owner顺序/共享写面/影响范围；在测试作者工作前核清。43项BMAD可达测试不作为新范围必须补齐的任务，也不能简单删除共享整文件；保留的真实VDD、Windows和防护断言另行绑定。
- 正式测试修改和fresh Q2/probe/RED/回归/Q6/Q7/terminal/Q8是后续实施阶段，当前方案不执行；旧计划和本报告均不授予这些动作。

## 证据怎样复用：能力边界与成本

| 原证据/材料 | 可引用内容 | 不能直接继承的内容 |
|---|---|---|
| 原始需求、已交付PRD/SPEC/Architecture/selection | 原字节、来源角色、历史设计和完整保留条款；必要format/ref/hash检查 | 不重新执行/审核BMAD；旧全部范围批准不覆盖新oracle。 |
| 旧330项VDD发布与V1/V4记录 | 旧源范围见证、明确前驱及精确未变锚点的V1候选复用 | 不能将旧V4或plan-ready写成新范围已通过。 |
| 原r40和S2-r26过程/Windows历史 | 已真实发生的输出与环境事实、保留功能的诊断线索 | 缺新共享依赖身份的receipt不回填；新plan/selector/来源/代码变更后不得改hash或复制成当前权限。 |
| 新宿主99项机制回归 | 当前未变宿主实现的已执行回归事实，无需为本方案再跑 | 不是新业务范围的阶段验收，也不是最终候选Q8。 |
| 原实际S1两case的一次执行+零执行reference | 证明当时同输入reuse确实命中，保留original report身份 | 该S1测试验收的是现已撤出的BMAD注册；7处撤回后不是当前业务pass，不能计入新范围。 |
| 新shared execution机制 | 同一新冻结有效合同/argv/cwd/环境/内容、真实case覆盖且依赖受控的成功原件可供Q6/terminal引用，process_attempts=0 | semantic_identity绑定完整合同，范围变化会改变key；外文件/真实子进程/网络依赖不满足受控发布，不承诺每个terminal零执行。 |
| 两次/后续真实Windows包 | 保留原环境、commit、JUnit与runtime哈希，对未变且仍适用的场景逐项引用 | 不全盘作废，也不冒称覆盖后续变更；须按最终测试/源码/依赖与原协议重新判断，必要补验证另行确认，不监控CI。 |

### V1自动复用的静态上界

`semantic_compiler.py:369–515` 按同requirement_id且完整text_sha256相等重绑；依赖中有不能复用的旧O ID，会将对应锚点退出复用候选。它不是“标成保留就跳过”。

仅对旧分类数据做静态计算、假定所有全保留锚点的完整文本可原样保留：62锚点中23个仅含保留项，覆盖125义务；再按当前依赖闭包规则，剩4个锚点/15义务（SM-K14/K16/K46/K51）有潜在资格。**这不是命中结果，也不是保证可复用15项**；新有效输入未创建，完整文本/引用/身份是否相同尚未验证。路径重绑后的ID还会变化。

因此普通入口可能重新处理大部分有效来源和V3/V4；不能承诺只运行59项，更不能承诺246项都零调用复用。启动前必须把实际输入下的候选/拒绝原因和预估请求范围交用户确认。旧成功模型输出不能靠换source ref/缓存文件名强制命中。

## 可选路线、成本和风险

| 方案 | 改动与成本 | 评价 |
|---|---|---|
| A：现有公开编译器 + 新有效输入 + 前驱V1条件复用 | 宿主代码0改动；约2–3份作者输入/映射，另由owner生成一个后继目录及必要门禁；V3/V4和大部分来源可能重新处理，模型调用量未能预先承诺 | **推荐路线，但先做作者输入/成本确认，实际编译需要另一步授权。**不调用BMAD。 |
| B：新增本需求专用范围扣减/替代宿主入口 | 新增受限25撤出/59替代、前驱/source/hash完整性、246语义保护、依赖重投影和正式发布验证；需新增正负回归/self-hosted稳定化，再恢复原任务 | 可能减少重复语义生成，但引入新的控制面代码和维护成本；现有授权不覆盖，**当前不推荐、不实施**，更不做通用框架。 |
| 只留范围报告、不生成有效后继合同 | 无编译/宿主成本，完整历史保留 | 合法的暂停状态，但不是正式修订完成，也不能继续声称旧Q8代表新范围。 |

不选：手改旧JSON、把withdrawn写成pass、导入伪缓存、套固定FR-10替代ID、deferred减覆盖，或直接按本清单跳过旧门禁。

## 预计修改面与完成判据

预计正式方案A只触及：独立用户范围/有效输入/逐项lineage文件，owner生成的新后继目录及其source-index/验收/依赖/context。已有7处撤回保持；共享adapter/config/测试的后续修改按另一步授权执行。原始需求/PRD/SPEC/Architecture/旧330目录/历史证据/宿主和模型设置不改。

正式修订完成需要：

1. 用户确认范围记录与完整有效条款；25移出有理由，59每条保留条件完整，246无无关语义漂移；Windows和所有保护未丢。
2. 每个旧O/A/assertion/FI与新ID或设备侧台账可双向追溯，FR/AC/AD也能对应；新source-index和实际forwarded context无遗漏、无把旧BMAD要求重新激活。
3. owner通过原生来源/语义/覆盖/依赖/feasibility/handoff门禁发布新plan-ready；无悬空/循环、oracle可GREEN、owner/测试入口/写界和必需RED角色合法。清单/静态通过不能替代正式发布。
4. 明确“旧证据引用”“模型输出复用”“当前执行成功reference”三种身份；新阶段未执行的测试不标通过，失效或不完整身份明确拒绝。
5. 阶段末是否复核及下一动作仍由用户步进确认；不在中间问题调用A/B或自动进入QuickDev/Acceptance/push。

如果后续实际编译获授权，保留单次运行的1800秒总预算、600秒真实无输出静默上限；不改查询30/60秒合同预算、不盲重试、不无限自动修复。不作无法测量的时间/额度承诺；首次实际阻塞保存状态后报告，下一步由用户确认。

## 本步交付身份与停止点

- 原合同SHA256：66919b3d4a2bc7eb53421fdcfd8620903fc35e04a1e70c2a262f4907ff19887e。
- 原始需求SHA256：ce45693489d02227442c04c9b4e7220121a897d81dab03abc7867e6ceff11950。
- 分类JSON SHA256：dc8fb75f265cbb3790037e698be510f0044b392447f904100bfaf7b7add0d9ee。
- 本步授权：Sentinel_0463099f117081919ad54555cba314ef；仅制定方案，不实施。
- 下一步建议仅为：用户先选择A/B/保持暂停；若选A，先批准作者输入与映射准备，暂不启动编译。未获确认前保持停止。
