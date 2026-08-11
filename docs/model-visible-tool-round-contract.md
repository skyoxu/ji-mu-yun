# 模型可见工具轮次优化合同

状态：Proposed
范围：仓库工具链与代理编排
所有者：Toolchain control plane
日期：2026-08-12

本文件是跨工具的编排合同，不是某一个工具的实现说明。它必须与最近的
`AGENTS.md`、Accepted ADR、运行协议和各工具专属合同同时满足；发生冲突时，
高优先级安全、授权和恢复规则优先。

在完成 Accepted ADR、schema validator、证据 producer 和外层运行时观测前，
本文件不得作为“已启用的自动并行策略”发布。当前仓库提供合同、producer、
validator 以及本地 sidecar 门禁；它们不能声称已经控制 `functions.exec`、
Codex 服务或第三方 MCP 的真实轮次和 token accounting。

### 当前修复边界（P0/P1/P2）

- P0：`complete` 不能依赖 `external-unverified` artifact；repository-scope
  并行必须绑定 `run_id`、`turn_id`、排序 operation manifest、`AGENTS.md`
  SHA-256 和受信 adapter。project、phase 和 workspace scope 在 v1 直接 fail closed。
- P1：`round_events` 是轮次唯一事实来源；validator 还校验 fallback/正式 Schema
  一致性、凭据扫描、reparse containment、blocked 重试、后台生命周期和追加写入。
  CLI 不回显绝对 host path，证据 hash 使用流式计算。
- P2：黄金示例、正反向测试和字段说明已同步；浏览器、图片、MCP、Codex 和
  `functions.exec` 的真实运行时 telemetry 仍是外部边界，未在此文档中虚报为已完成。

P2 外部边界的处置是 `blocked-external`，不是“已验证”：只有接入对应 provider
adapter、产生可重放的 `round_events`/token sidecar，并通过同一 validator 后，
才能把该边界从 `observed=false` 改为 `observed=true`。在此之前 producer 和
validator 会保留 `unknown`/`partial`，不会把文档示例升级为 `Implemented`。
当前版本没有注册任何外部 adapter，也没有注册受信 preflight/background
adapter；因此并行授权和已启动 background operation 不能声明 `complete`。
MCP、浏览器、图片、`functions.exec` 和 `other` operation 即使把 boundary 布尔值
写成 `observed=true` 也会被拒绝。接入 adapter 时必须同时扩展注册集合、sidecar
校验和回归证据；当前注册集合位于
`scripts/python/validate_model_visible_tool_round_summary.py` 的
`REGISTERED_OBSERVED_BOUNDARIES`、`REGISTERED_PREFLIGHT_ADAPTERS` 和
`REGISTERED_BACKGROUND_ADAPTERS`，值均为空。

## 1. 目标与适用范围

目标按优先级排列：

1. 减少 `model_visible_rounds`，即模型重新获得控制权的次数；
2. 限制进入模型上下文的结果量；
3. 保留构建、测试、诊断和日志的完整证据；
4. 不引入数据泄漏、竞态、漏读或副作用。

适用所有会产生模型可见结果的工具：

- FastCtx `read`、`grep`、`glob`、`run`、`run_background`；
- Codex 内置 shell；
- 其他 MCP 工具；
- `functions.exec`；
- 浏览器、图片以及其他工具。

FastCtx 的分页、单次传输上限、摘要和后台日志细节仍由
`docs/fastctx-file-operation-output-contract.md` 拥有；本合同只拥有跨工具
的分组、轮次、证据和验收规则。

## 2. 可观测模型

### 2.1 轮次定义

一次 `model_visible_round` 是：

1. 助手发起一个工具阶段请求；
2. 工具执行一个或多个底层操作；
3. 工具返回一个模型可见的聚合结果；
4. 模型重新获得控制权。

在一次 `functions.exec` 内并行执行多个操作，只有平台确实只返回一个
聚合结果时才计为一轮。若平台分别返回多个结果，必须按实际返回次数计数，
不得按编排代码的意图推算。

### 2.2 指标

- `model_visible_rounds`：模型可见续接次数，主要指标；
- `underlying_tool_calls`：底层工具调用数，包含失败和重试；
- `parallel_groups`：并行组数量，不是并行操作数量；
- `sequential_calls`：顺序执行的底层操作数；
- `background_calls`：后台执行的底层操作数；
- `retries`：自动或人工重试次数；
- `visible_result_bytes` / `visible_result_tokens`：脱敏和序列化后进入上下文的结果量；
- `persisted_output_bytes`：完整落盘但未返回上下文的字节数；
- `partial_results` / `failed_calls`：截断和失败数量；
- `blocked_calls`：被 preflight 或工具状态阻断的数量；`interrupted_calls`：被
  外部中断、取消或终止的数量。

`model_visible_rounds` 和 token 数必须标明测量状态：`observed`、`estimated`
或 `unknown`。外层不可观测时必须记录 `external_boundaries`，不能把估算值
写成实测值。`unknown` 对应的数值必须为 `0`；本 schema 中 token 标记为
`estimated` 时统一按精确可见 UTF-8 字节数除以四并向上取整。

工具调用减少只有在轮次下降且结果完整性、安全性和副作用指标没有恶化时
才算有效。

## 3. 并行前置检查

任何 `parallel_read_group` 在启动前必须通过以下 preflight：

- 所有操作属于同一 `scope_kind` 和 `scope_ref`；
- 当前账户、项目、工作区和授权边界已验证；
- 结果脱敏规则已选择并验证；
- 所有操作确实只读、幂等且没有隐含写入；
- 不存在同一文件、数据库行、运行状态或 Hosted workspace 的并发修改；
- 聚合器可以为每个操作保留独立状态、错误和证据引用。

任一项无法证明时，`parallelization_allowed=false`，状态为 `blocked`，并写入
结构化 `block_reason`；不得用助手文本覆盖该阻断。

v1 只实现 repository scope 的自动并行。`parallelization_allowed=true` 时，
`preflight.evidence_ref` 必须指向 workspace-relative、已验证 hash 的
`model-visible-tool-preflight.v1` sidecar。sidecar 必须绑定当前 `run_id`、
`turn_id`、完整且排序后的 `operation_ids`、canonical operation manifest、
repository `scope`，并重新验证根 `AGENTS.md` 的 SHA-256。`authority.adapter_id`
必须存在于 validator 的受信注册集合；仅匹配 `AGENTS.md` hash 或布尔值不能
证明授权。摘要中的三个 preflight 布尔值不能脱离该 sidecar 单独成立。缺少
sidecar、scope/manifest 不一致、authority hash 不一致、adapter 未注册或检查项
不全时必须 fail closed。当前注册集合为空，因此 v1 不启用自动并行。

`scope_ref`、证据路径必须是工作区相对引用或受控 artifact ID，不得是根路径、
Windows 绝对路径、URI 或包含 `..` 的路径。workspace root、所有中间路径组件
和目标文件在解析前都不得是 symlink/reparse point。

## 4. 编排规则

### 4.1 独立只读操作

没有数据依赖、没有副作用的读取、搜索和状态查询应组成一个
`parallel_read_group`，优先在一次 `functions.exec` 内并行执行，并在同一轮
返回有界摘要。

建议单个并行组为 2–8 个操作。超过 8 个时，应缩小范围或让子进程先聚合；
不得为了降低轮次而制造一个不可审计的超大结果。

### 4.2 有依赖的操作

以下操作必须顺序执行：

- 依赖前一步结果的查询；
- `Partial` 精确续读和分页续读；
- 错误恢复和路径选择；
- 需要读取新状态后才能决定的写入。

不得猜测 offset、cursor、路径或恢复状态。

### 4.3 有副作用的操作

写入、替换、删除、发布、认证、运行时和 Hosted workspace 操作不得自动
并行。它们必须独立执行、验证结果，并遵守最近的 `AGENTS.md`、保护路径、
授权和批准边界。

### 4.4 失败、超时和重试

- 并行只读组为每个操作返回独立的 `complete|partial|failed|interrupted|blocked` 状态；
- 一个操作失败不得隐藏其他操作的结果；组状态由最严重状态决定；
- 超时必须记录为 `failed`，并记录是否仍有后台任务；
- 只有明确幂等、边界明确的操作允许自动重试；重试计入 `retries` 和
  `underlying_tool_calls`；
- 结果必须按稳定的 `operation_id` 排序，避免同一输入产生不可复现摘要；
- 状态严重度按 `failed > interrupted > blocked > partial > complete` 归并；
- 无法定位单个失败来源时，整个聚合必须 fail closed。

### 4.5 后台任务与轮询

- 长任务使用工具提供的后台 job 和持久日志；
- 启动后台任务后先处理其他独立工作；
- 只有下一步决策需要结果时才查询状态；
- 每次查询都必须读取状态、退出码和未读日志范围；
- 终止状态为 `complete|failed|interrupted`；连续轮询必须有停止原因和上限。
- `execution_mode=background` 且已启动的 operation 必须携带
  `background_lifecycle`：`adapter`、`job_id`、`terminal_state`、`exit_code`、
  `log_evidence_ref`、零基半开 byte `log_start/log_end`、`poll_count`（最多 64）
  和 `stop_reason`。`complete` 还必须由已注册的 tool-family adapter 证明，退出码
  为 0，且日志范围覆盖已验证本地日志；未启动且 `blocked + attempts=0` 才可省略
  lifecycle。当前 background adapter 注册集合为空。

## 5. 输出与证据

### 5.1 统一边界

- 聚合摘要的精确序列化结果（包括包装和尾部换行）不得超过 12,000 UTF-8
  字节，并遵守对应 schema 的 token 估算上限；超限时 producer 必须失败，
  不得静默裁剪并继续报告成功；
- `visible_result_bytes` 统计脱敏、序列化后的模型可见结果总量；
- `persisted_output_bytes` 统计完整落盘文件的实际字节数；
- 大型构建、测试、诊断、JSONL、rollout、进程清单和完整日志必须先落盘；
- 主上下文只接收状态、退出码、计数、哈希、关键发现、错误摘要和证据路径；
- 任何无法证明输出受限、摘要有效或证据已落盘的路径都不得返回原始高输出。

FastCtx `run` 必须使用 `fastctx-summary.v1`；其他工具必须使用已注册并通过
validator 的专属 schema，不得以未校验的“等价摘要”替代。

### 5.2 工具适配要求

| 工具 | 完整输出策略 | 模型可见结果 |
| --- | --- | --- |
| FastCtx `read/grep/glob` | 按工具 offset 分页 | 有界页面和 continuation |
| FastCtx `run` | 显式重定向到证据文件 | `fastctx-summary.v1` |
| FastCtx `run_background` | 将返回的 host 日志登记为受控 artifact，验证退出码和哈希；不得把绝对 host 路径写入 evidence ref | 状态和日志摘要 |
| Codex shell | 显式重定向；路径必须在授权 evidence 目录 | 状态和结构化摘要 |
| MCP | 使用 provider 的 artifact/分页能力；没有则 fail closed | 已校验摘要 |
| 浏览器/图片 | 保存截图、DOM 或原始资源的受控 artifact，并脱敏 | 元数据、哈希和必要视觉摘要 |

### 5.3 证据与恢复

摘要证据使用新增的
`scripts/sc/schemas/model-visible-tool-round-summary.v1.schema.json`，由
`scripts/python/validate_model_visible_tool_round_summary.py` 校验，并由
`scripts/python/build_model_visible_tool_round_summary.py` 从 operation ledger
重算指标后生成。producer 不接受调用方直接提供的聚合计数作为事实来源。
validator 在未安装 `jsonschema` 时仍使用同一合同的 dependency-free 结构门禁，
不能通过“缺少验证依赖”绕过证据、状态或脱敏检查；fallback 与正式 Schema
保持同一字段和类型约束，`tool_call_id` 不能为 null。

校验命令：

```powershell
py -3 scripts/python/validate_model_visible_tool_round_summary.py <summary.json>
```

生成命令：

```powershell
py -3 scripts/python/build_model_visible_tool_round_summary.py --input <operation-ledger.json> --output <summary.json> --root .
```

`evidence_refs` 必须包含唯一 `ref_id`、`kind`、`sha256`、`hash_status`、
`run_id`、`turn_id`、`scope_kind`、`scope_ref`、`owner`，以及工作区相对 `path`
或受控 `artifact_id`。
本地 `path` 必须由 validator 流式读取并重新计算 SHA-256；workspace member path
拒绝 Windows alternate data stream（ADS）语法，并对 `log`、`summary`
和 `sidecar` 内容流式扫描常见凭据；这些文本不是有效 UTF-8 时直接拒绝。原始
日志中的 host path 可以保留在受控 evidence 文件中，但不得进入 summary、error
或 path 字段。外部 `artifact_id` 必须明确标记 `hash_status=external-unverified`，
并绑定 owner、run 和 turn。
同时绑定当前 `scope_kind`/`scope_ref`，否则 validator 会拒绝该 artifact。
`rounds_evidence_ref` 和 `tokens_evidence_ref` 必须指向
`model-visible-tool-measurement.v1` sidecar；validator 会逐字段比对其中的
round events、scope、可见字节数、token mode 和 token method，不能只凭文件存在
或 hash 格式通过。
producer 输出采用 append-only create-new：目标已存在、是 symlink/reparse 或发生
竞争写入时失败，绝不覆盖历史 bytes。在没有可重算的本地 attestation 前，外部证据只能产生 `partial` 或更严重状态，
不能产生 `complete`。它是运行证据的附加索引，不替代现有
`run-events.jsonl`、`summary.json`、`execution-context.json`、`latest.json`
和 `sc-recovery-compact` 恢复协议。恢复决策仍以现有协议和最新 live blocker
为权威。

producer 的输入 ledger 和输出 summary 也必须位于 `--root` 内；越界路径会在
读取或写入前失败，CLI 只返回 workspace-relative `output_ref`。

原始日志永远不是恢复状态来源；不得在摘要、错误或路径字段中保留 token、
密钥、用户凭据或未经脱敏的用户沙箱内容。

## 6. Schema 最小字段

正式 schema 要求以下顶层字段：

- `schema_version`、`status`、`run_id`、`turn_id`；
- `scope`、`timing`、`measurement`；
- `metrics`、`preflight`、`round_events`、`operations`、`continuation`；
- `evidence_refs`、`external_boundaries`、`errors`。

每个 operation 还必须有唯一的 `operation_id`、`tool_call_id`，可验证的
`parent_tool_call_id` lineage、`round_id`、同 scope 声明、`access_mode`、执行模式、状态、
attempts、可见字节数、落盘字节数和 evidence ref；这些字段用于由 producer
复算聚合指标，而不是接受调用方填入的总数。`model_visible_rounds` 必须等于
`round_events` 的数量；`rounds=unknown` 时 round events、round id 和轮次数值
都必须为空/为零。非空 evidence ref（按规范化本地 path+hash 或 artifact id+hash
判定）不得被多个 operation 重复计数；measurement sidecar 不能冒充 operation
输出，落盘字节数大于零时必须有 evidence ref。
任何 `execution_mode=parallel` 的 operation 都必须有 `access_mode=read-only`；
side-effecting operation 只能使用顺序或受控后台执行。
在调用尚未启动就被 preflight 阻断时，`attempts` 可以为零；其余已执行的
operation 至少要有一次 attempt。`attempts=0` 的 blocked operation 不产生输出、
evidence、round 或 lifecycle 声明；它不产生负重试，`retries` 始终按
`max(attempts-1, 0)` 重算。`execution_mode=background`
且已启动的 operation 还必须有 `background_lifecycle` 及已验证日志；未启动的
`blocked + attempts=0` 才可为 null。

`errors` 只能使用包含 `code`、`family`、`severity`、`message` 和可选
`operation_id` 的结构化对象，并按 operation/code 稳定排序；自由文本错误和
绝对 host path 会被拒绝。

`external_boundaries` 的每一项必须说明边界名称、是否已观测和原因；只要摘要
包含 MCP、浏览器、图片、`functions.exec` 或 `other` operation，就必须记录对应
provider boundary，不能用无关 boundary 代替。图片、
浏览器、MCP provider 和 Codex 服务端 token accounting 无法观测时，必须明确
记录为 `observed=false`。boundary 名称必须唯一并稳定排序，不允许用同名的
`true`/`false` 两条记录制造矛盾结论。
当某 operation 对应的外部 boundary 为 `observed=false` 时，不能同时把该运行
的 `measurement.rounds` 声明为 `observed`；`tokens=unknown` 但引用 rounds
sidecar 时，sidecar 的 `visible_result_bytes` 仍必须与 summary 一致。

## 7. 验收与 A/B 测试

对同一任务、同一输入、同一环境和同一输出要求执行至少 5 次 A/B：

1. A：逐个执行 6 个独立只读操作；
2. B：在一次 `functions.exec` 内并行聚合相同 6 个操作。

每组必须比较中位数和最大值，并记录：

- `model_visible_rounds`；
- `underlying_tool_calls`、重试和失败数；
- `visible_result_bytes/tokens`；
- 结果集合、源文件哈希和关键计数；
- 完整证据是否可从 `evidence_refs` 读取。

通过条件：

- 在外层轮次可观测时，B 的轮次低于 A，目标是 6 降至 1；
- 结果集合、哈希和关键计数完全一致；
- B 不增加截断、漏读、失败归因错误、秘密暴露或副作用；
- 外层轮次或 token 不可观测时，测试只能标记 `external_boundary`，不能报告
  “优化已验证”。

## 8. 止损与采用门禁

出现以下任一情况，停止继续聚合并转为顺序或人工检查：

- 聚合结果接近 12,000 字节；
- 存在数据依赖、精确分页或未知 cursor；
- 任一操作涉及写入、删除、认证、运行时或保护路径；
- 并行操作可能修改相同文件或状态；
- 工具返回格式无法稳定解析；
- 无法定位单个失败来源；
- scope、授权或脱敏 preflight 不完整。

从 `Proposed` 升级为 `Implemented` 前必须同时具备：

1. Accepted ADR 或明确的决策日志；
2. schema、validator、producer 和单元测试；
3. 至少一组当前机器 A/B 证据；当前仓库的 schema/producer/validator 测试不等于
   `functions.exec`、Codex、MCP、浏览器或图片 provider 的真实外层观测；
4. 外层不可观测边界的明确清单；
5. 与现有 FastCtx、run protocol 和恢复 schema 的一致性检查。

## 9. 外部边界声明

本仓可以校验摘要格式、证据路径、哈希、脱敏、分页和本地底层调用记录，
但不能单独证明：

- `functions.exec` 是否始终只产生一次模型续接；
- Codex 服务端真实 token accounting；
- 第三方 MCP、浏览器或图片 provider 的内部缓存、截断和计费。

这些边界必须在证据中显式记录，不得由助手文本或文档示例代替机器证据。

## 10. 决策依据

- Accepted ADR-0038：Evidence Sidecars And Account-Scoped Readback，拥有结构化
  evidence、账户范围、脱敏、workspace-relative readback 和哈希重算要求；
- `docs/workflows/run-protocol.md`：拥有本地运行 sidecar 和恢复协议；
- `docs/fastctx-file-operation-output-contract.md`：拥有 FastCtx 传输限制。
