# Bootstrap Review 上下文溢出系统性治理方案

## 文档状态

| 字段 | 值 |
| --- | --- |
| 日期 | 2026-08-09 |
| 状态 | Concluded - remediation proposed |
| 适用范围 | Acceptance -> Bootstrap Review -> Codex reviewer child |
| 当前验收目标 | `execution-plans/2026-08-07-bootstrap-review-operability-hardening` |
| 历史 run 处理 | `logs/reviews/broh-acceptance-20260809-r4*` 保持 abandoned，不恢复、不改写 |
| 当前 run 处理 | `acceptance-broh-20260809-r5` 在 reviewer launch 前暂停 |

## Hand-off Brief

1. **发生了什么。** Bootstrap Review 的子进程上下文溢出主要由工作流合同造成：分段 child 除了自己的 segment，还被要求重复读取完整 Bootstrap 权威包，并可继续产生无界工具输出。
2. **当前判断。** FastCtx 有可测量的包装开销，但现有 A/B 和历史日志不支持把它认定为主要根因；native shell 同样可以产生更大的无界结果。
3. **下一步。** 先关闭每段重复权威读取并建立启动前上下文预算，再引入确定性 Policy Capsule、隔离工作区和有界 Review Packet，最后才允许 r5 启动 reviewer。

## 执行结论

本问题不能通过单独调小 `ARTIFACT_VIEW_SEGMENT_BYTES`、更换文件读取工具或依赖 Codex 自动压缩来稳定解决。系统必须明确三种上下文所有权：

- Acceptance 主会话只拥有生命周期、状态和最终 envelope，不拥有 reviewer 原始材料。
- Bootstrap 父控制面拥有完整权威、Artifact View、预算计算、分包、验证和聚合。
- reviewer child 只拥有一个有界 Review Packet、一个角色 Policy Capsule 和输出 schema。

任何层级都不得把完整日志、完整 manifest、完整权威包或成功 segment 的原始输出重新注入上一级 LLM 上下文。

## 证据分级

### 已确认事实

| ID | 事实 | 证据 |
| --- | --- | --- |
| C-01 | 当前 Bootstrap Skill 要求完整 artifact/context coverage。 | `.agents/skills/run-phase-bootstrap-review/SKILL.md:31-33` |
| C-02 | 2026-08-05 的提交 `d713e74e` 首次增加 7 个 delegated Bootstrap authority 路径，并要求每个匹配 child 在 semantic review 前读取全部映射快照。 | Git commit `d713e74e`; `.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py:114-122,7144-7184` |
| C-03 | 当前 7 个 authority 文件合计约 160,608 bytes。 | 对声明路径执行 `wc -c` 的 2026-08-09 只读测量 |
| C-04 | 当前未提交修复按最多 64 KiB 创建 Artifact View segment，但仍把 delegated authority contract 注入每个 segment child。 | `.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py:3737-3803,7206-7209,7289-7305` |
| C-05 | r4b/r4c 的 Artifact View 包含 65 个 artifact、约 1,371,506 bytes，生成 78 个 segment。 | `logs/reviews/broh-acceptance-20260809-r4b/review-input.json`; `logs/reviews/broh-acceptance-20260809-r4c/review-input.json`; attempt `request.json` |
| C-06 | r4c 一个 Blind Hunter attempt 只分配到 4,198-byte segment，却产生 1,055,669-byte stdout；约 826,973 bytes 与工具调用记录有关。 | `logs/reviews/broh-acceptance-20260809-r4c/attempts/blind_hunter-20260809T081533-09509800/request.json`; 同目录 `stdout.log` |
| C-07 | 上述 child 读取了 Skill、ADR、standard、profiles、operator guide，随后继续读取 tests、schemas、manifest 和脚本，远超分配 segment。 | 同一 `stdout.log` 的 command execution 记录 |
| C-08 | r4b 的 37 个 attempt stdout 合计 905,043 bytes，最大 68,045 bytes；r4c 合计 6,684,227 bytes，最大 1,055,669 bytes。 | r4b/r4c attempt 只读统计 |
| C-09 | r4b 的代表性大输出使用 FastCtx，r4c 的最大输出使用 native PowerShell/Python；native 单次结果可达约 401 KB。 | r4b/r4c `stdout.log` 工具事件解析 |
| C-10 | 相同 1,382-byte 内容的 10 组 A/B 中，FastCtx 格式化结果相对 raw content 约有 19.3% serialized-byte 开销，但不是数量级差异。 | `fastctx-context-impact-investigation.md` Follow-up #2 |
| C-11 | r5 目前只完成 deterministic validation 和 Bootstrap decision，没有启动 reviewer child。 | `execution-plans/2026-08-07-bootstrap-review-operability-hardening/acceptance-runs/acceptance-broh-20260809-r5/**` |

### 推导结论

| ID | 结论 | 推导链 |
| --- | --- | --- |
| D-01 | Skill 编排是主要风险源。 | C-02 + C-03 + C-04：每个本应有界的 segment child 都重复承担约 160 KB 固定权威输入。 |
| D-02 | 当前 segmentation 修复方向正确但闭环不完整。 | C-04 + C-06 + C-07：segment 本身很小，child 实际读取范围仍可无限扩张。 |
| D-03 | FastCtx 是放大器而非已确认根因。 | C-08 + C-09 + C-10：FastCtx 有包装成本，但 native 路径产生了本样本中最大的无界输出。 |
| D-04 | 自动压缩不能作为控制机制。 | 单个 attempt 可在一次或少数几次工具返回中增加数百 KB；硬限制可能在下一次压缩机会前被越过。 |
| D-05 | 仅把工作移入子进程不足以解决问题。 | 子进程有独立窗口，但如果每个新窗口都从高固定输入开始并允许无界读取，仍会逐个溢出。 |

## 根因模型

一次 reviewer attempt 的实际上下文压力可以近似表达为：

```text
fixed Codex instructions
+ discovered repository instructions
+ reviewer role prompt
+ delegated authority bundle
+ assigned review segment
+ tool request/result envelopes
+ model reasoning and candidate output
```

当前 segment 只约束其中一项。delegated authority、仓库指令、工具结果和模型输出没有共享的预算合同，因此 `64 KiB segment` 不等于 `64 KiB attempt`。

如果严格按当前合同执行，三个 reviewer 对 78 个 segment 重复读取约 160,608 bytes 的 authority bundle，理论重复输入约为：

```text
160,608 * 78 * 3 = 37,582,272 bytes
```

这不是单个窗口的累计值，但它使每个新 child 都从高固定成本开始，并造成显著的总 token、时长和失败概率放大。

## 目标架构

```text
Acceptance orchestrator
  -> compact lifecycle/result projection only
Bootstrap parent control plane
  -> validate full authority once
  -> compile role-specific Policy Capsule
  -> build bounded Review Packets
  -> launch isolated children
Reviewer child
  -> read one packet only
  -> return compact candidate/receipt JSON only
Bootstrap aggregator
  -> validate, merge, gate, verify, finalize
Acceptance importer
  -> consume final validation envelope only
```

## 必须建立的控制合同

### 1. Context Budget

新增 schema-valid、prepare 时冻结的 `bootstrap-context-budget.v1`：

```json
{
  "maxFixedPromptBytes": 12288,
  "maxPolicyCapsuleBytes": 16384,
  "maxPacketBytes": 49152,
  "maxSingleToolResultBytes": 16384,
  "maxAttemptToolResultBytes": 65536,
  "maxCandidateBytes": 16384,
  "minimumHeadroomRatio": 0.4,
  "overflowAction": "repartition-no-unchanged-retry"
}
```

这些数值是初始保守值，必须由真实模型 token telemetry 校准；在校准完成前不得上调。

启动前由父控制面计算完整 prompt/packet serialized bytes。任何字段超限都在 `Popen` 前失败，并给出可机器处理的 budget diagnostic。

### 2. Policy Capsule

父控制面一次性读取并 hash 验证全部 Bootstrap authority，由确定性代码生成 role-specific capsule：

```json
{
  "schemaVersion": "bootstrap-review-policy-capsule.v1",
  "role": "blind_hunter",
  "authorityRevision": "...",
  "sourceHashes": {},
  "rules": [],
  "outputContract": {},
  "authorizes": []
}
```

约束：

- capsule 不由 LLM 摘要；生成逻辑和 schema 属于 Bootstrap producer。
- child 不再读取 7 个原始 authority 文件。
- capsule 不包含解释性历史、operator 示例和不属于当前角色的 profile 分支。
- capsule 必须有独立 hash，并进入 request、receipt 和 cache identity。

### 3. Review Packet

Review Packet 替代单纯的文件/行切片，至少绑定：

- 一个主 artifact 或主行区间。
- 直接契约、消费者或测试的必要区间。
- requirement/finding IDs。
- Policy Capsule hash。
- Artifact View source hashes。
- packet byte count 和预算版本。

需要额外上下文时，child 只能返回结构化 `needs_context` 请求。父控制面验证路径、范围、关联性和预算后生成新 packet；child 不能自行遍历 manifest 或目录。

### 4. Child Isolation

- child 的 `-C` 工作目录应位于仓库 Git 根之外，避免自动发现完整仓库控制面。
- 父进程只投放 packet、capsule、handshake helper 和输出 schema。
- 不向 child 暴露 repository root、完整 run directory 或完整 Artifact View manifest 路径。
- child 完成后，父进程验证并把 request、JSONL、stdout/stderr、result 和 receipt 归档到正式 run evidence。
- 是否可完全消除上级 Codex 指令注入需要通过真实 canary 验证；在此之前把这项视为防御增强，不视为已证明根因修复。

### 5. Tool Output Boundary

- 提供有界 `read_packet`、`search_packet` 等 controller-owned helper。
- 禁止整文件 `Get-Content`、递归目录打印和批量全文输出作为有效 reviewer 操作。
- 单次和累计 tool result 均应用硬预算。
- JSONL 轨迹发现 packet 外路径时，attempt 标记为 `contract-violation`，不能发布 formal output。
- FastCtx 与 native shell 使用相同预算；不能把工具类型当作安全边界。

### 6. Retry Boundary

- 只重试失败 packet，不重放已成功 packet 的原始上下文。
- `context-window-exceeded`、budget exceeded 和越界读取都禁止原样重试。
- 修复动作必须是缩小/repartition packet、收紧 capsule 或修正工具读取合同。
- cache identity 至少包含 role、model、reasoning effort、packet hash、capsule hash、budget revision 和 authority revision。

### 7. Thin Parent Projection

Acceptance 主会话只接收固定大小的状态投影：

```json
{
  "status": "ready|blocked|running|complete",
  "nextAction": "...",
  "completedPackets": 0,
  "remainingPackets": 0,
  "acceptedFindings": 0,
  "evidencePath": "...",
  "authorizes": []
}
```

完整 validator 输出、manifest、attempt stdout 和历史统计写入文件，不回显到主会话。`inspect-run` 应提供明确的 `--summary` 或默认 compact projection。

## Skill 改造边界

### `run-phase-bootstrap-review` - 主改造对象

- 删除 segment child 的 `Read every mapped snapshot` 合同。
- 新增 context budget、Policy Capsule、Review Packet 和有界 helper。
- 将完整 authority 验证保留在父控制面。
- 调整 attempt workspace、request schema、receipt、cache 和 retry 分类。
- 继续由父控制面负责 whole-view completeness 和 formal publication。
- 精简 `SKILL.md`：保留不可违反的流程，将详细历史、示例和迁移材料留在按需 references；确定性逻辑只存在于 scripts。

### `run-refactor-implementation-acceptance` - 次级改造对象

- 继续生成七类 `minimal-complete-closure`，但只把明确文件交给 Bootstrap producer。
- 不读取或转发 reviewer 原始 stdout、完整 manifest 或权威正文。
- 只消费 compact Bootstrap status 和最终 validation envelope。
- 给 parent session 输出建立固定大小门禁。

## 分阶段实施

### P0 - 立即止损，阻止 reviewer launch

1. 删除 segment child 的完整 delegated authority 重读。
2. 增加启动前 prompt/packet byte diagnostic。
3. 将 unchanged retry 对 context overflow 设为 fail closed。
4. 增加回归：4 KB segment 不得触发 160 KB authority 读取。

**退出条件：** 所有 deterministic tests 通过，并能证明 runtime prompt 不包含完整 authority mapping 或 manifest traversal 指令。

**当前状态：已完成（工作区改造，尚未创建新的正式 repair slice）。** 已修改 Bootstrap runtime、回归测试、Skill 和 durable standard；完整 Bootstrap 回归为 `202 tests ... OK`，Skill quick validation、Python compile、whole-directory plan validation 和 `git diff --check` 均通过。将 r4c 中曾分配 4,198-byte segment 的历史 request 重新渲染后，runtime prompt 为 11,117 UTF-8 bytes，且不含完整 authority mapping 或 full-view read 合同。真实 Codex canary 尚未运行。

### P1 - 权威编译与硬预算

1. 实现 Policy Capsule producer、schema、hash 和验证。
2. 实现 Context Budget schema 和 `Popen` 前门禁。
3. 将预算 revision 绑定 request、receipt、cache 和 final validation。

**退出条件：** 合成 2 MB Artifact View 能在不启动真实模型的情况下稳定生成全部预算内 packet；任何超限输入都确定性失败或重分包。

### P2 - 隔离执行与工具边界

1. 将 child workspace 移出 repository Git 根。
2. 投放最小输入包，不提供完整仓库路径。
3. 实现有界读取 helper 和越界轨迹验证。

**退出条件：** adversarial fake child 尝试读取 packet 外路径时无法产生可发布 formal output；归档证据仍完整位于 `logs/`。

### P3 - Acceptance 主会话瘦身

1. 提供 compact `inspect-run` / lifecycle projection。
2. 大型 deterministic output 写文件，只回传摘要、hash 和路径。
3. 禁止 Acceptance 读取 reviewer stdout 来判断结果。

**退出条件：** 从 `start-or-resume` 到 Bootstrap handoff 的主会话返回体均有固定上限。

### P4 - 真实 canary 与正式验收

1. 使用全新 run ID，不恢复 r4。
2. 先运行小型真实 Codex canary，再运行 8-07 完整 scope。
3. 收集每 attempt 的真实 input/output token、最大 tool result、累计 tool bytes、wall time 和失败分类。
4. canary 通过后才继续 r5 或创建明确的新 successor run；不得把 canary 当作 acceptance-passed。

## 必须通过的验收门禁

| 门禁 | 通过条件 |
| --- | --- |
| Authority isolation | segment child 没有完整 authority mapping，且不会读取 7 个原始 authority 文件 |
| Manifest isolation | segment child 不接收或遍历完整 Artifact View manifest |
| Packet budget | 每个 packet 和完整启动 prompt 均在冻结预算内 |
| Tool budget | 单次及累计 tool result 不超过硬限制 |
| Retry safety | context overflow 不会原样重试 |
| Coverage | 所有 packet receipt 无缺失、重复、重排、重叠或 role drift |
| Reviewer isolation | Blind Hunter、Edge Case Hunter、Acceptance Auditor 不共享候选 finding |
| Parent boundedness | Acceptance/Bootstrap 主会话只获得 compact projection |
| Stress | 至少 2 倍当前 reviewable bytes 的合成样本无 context-window failure |
| Real canary | 当前 8-07 等价 scope 的真实 Codex canary 无 overflow、无越界读取、无 unbounded output |

## r5 Go/No-Go

当前结论为 **NO-GO**：在 P0 和 P1 退出条件满足前，不应启动 r5 reviewer child。

允许继续 deterministic Acceptance 检查、schema/test 验证和只读 inspection，但不得：

- 恢复 r4、r4b 或 r4c。
- 原样重试历史 context-window attempt。
- 把旧 stdout 注入新 child。
- 以 segmentation receipt 单测通过替代真实上下文预算证明。

## 置信度评分

评分定义：`0.90-1.00 = High`，`0.75-0.89 = Medium-High`，`0.55-0.74 = Medium`，低于 `0.55 = Low`。

| 判断 | 评分 | 等级 | 依据与剩余不确定性 |
| --- | ---: | --- | --- |
| Skill 工作流编排是主要风险源 | **0.96** | High | 代码合同、提交历史和 r4c 行为形成直接证据链；缺少的只是改造后反事实 canary。 |
| 每段重复 delegated authority 是核心放大条件 | **0.98** | High | `d713e74e`、当前函数和 160 KB 测量直接确认。 |
| 当前 segmentation 修复尚未完整闭环 | **0.97** | High | segment prompt 仍注入 delegated authority，4 KB segment 的实测读取远超范围。 |
| FastCtx 不是主要根因 | **0.92** | High | A/B 只有约 19% 包装差异，最大无界输出来自 native 路径；仍缺严格同模型同 prompt 的真实 token A/B。 |
| 自动压缩无法可靠防止该类失败 | **0.90** | High | 单轮数百 KB 输出和无工具前失败均表明压缩不是硬门禁；Codex 内部压缩时机不可观测。 |
| Policy Capsule + hard budget 能消除主要机制 | **0.89** | Medium-High | 机制与根因直接对应，但尚未通过真实 Codex canary。 |
| 仓库外 child workspace 会显著降低固定上下文 | **0.82** | Medium-High | 符合 Codex 指令发现机制与当前 cwd 结构，但需要真实启动验证实际注入差异。 |
| 建议的初始 KB 数值适合长期生产 | **0.68** | Medium | 数值是保守工程起点，必须由真实 token telemetry 校准。 |

### 总体置信度

**0.94 / 1.00 - High**

高置信度覆盖“根因类别、当前修复缺口和正确治理方向”。剩余不确定性集中在具体预算阈值、外部 workspace 对 Codex 自动注入的实际减少量，以及改造后真实模型 canary 的 token 分布。这些不确定性影响参数校准，不改变先移除重复 authority 读取、建立硬预算和收紧 child 输入边界的优先级。

## 最小验证计划

1. 为当前 4,198-byte 历史 segment 生成新旧两版 runtime prompt，比较完整 serialized bytes 和包含路径。
2. 用 fake Codex runner 验证新 child 只能读取 packet/capsule，越界读取不能发布。
3. 对 2 MB 合成 Artifact View 验证 packet 完整性、预算门禁和只重试失败 packet。
4. 经用户确认后运行一个真实 Codex canary，记录真实 token usage，不启动正式 acceptance reviewer wave。
5. canary 通过后创建 fresh run；r4 系列继续保持 abandoned。

## 非目标

- 不通过提高模型 context window 掩盖无界输入。
- 不通过关闭完整 coverage、独立 reviewer 或 verifier 降低语义门禁。
- 不把 FastCtx 全面替换为 native shell 作为修复。
- 不恢复、删除或改写旧 run evidence。
- 不允许 LLM 自行摘要 authority 并把摘要当作新权威。
