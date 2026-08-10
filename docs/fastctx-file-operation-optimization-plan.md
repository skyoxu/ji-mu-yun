# FastCtx 文件操作上下文优化方案

状态：Implemented（仓库范围验收完成；外层编排边界待确认）

日期：2026-08-10

## 1. 目标

在接受 FastCtx 约 5-10% 固定上下文开销的前提下，将 FastCtx 作为所有普通文件操作的首选，同时阻止高输出读写、日志、rollout 和诊断原始输出直接膨胀主会话上下文。

本方案只处理工具调用与输出策略，不处理恢复协议、BMAD/GDS Skill 数量或 Skill 注入策略。

## 2. 已知基线

- Codex npm 版本：`@openai/codex 0.147.0`。
- 当前配置：`tool_output_token_limit=6000`、`FASTCTX_TOKEN_BUDGET=6000`。
- 历史主会话观测：两组均为 5 次读取 + 5 次写入；A 组最终输入
  `16063 tokens`，B 组最终输入 `14989 tokens`，差值约 `1074 tokens`。
- 主会话压缩前最高观测输入约 `220273 / 258400 tokens`。
- 主会话中存在宽范围 FastCtx 读取、原始 JSONL/rollout 诊断和多轮重复提交。
- `functions.exec` 是外层编排层，当前未证明它完整继承 Codex 原生工具输出截断策略。

本仓库的受控验收证据位于
[`logs/tool-context/fastctx-ab/2026-08-11-read-write-summary.json`](../logs/tool-context/fastctx-ab/2026-08-11-read-write-summary.json)，并通过
`scripts/python/validate_fastctx_ab_test.py` 校验。该证据是传输策略基准，
不是 Codex 服务端的真实 token 计量。

## 3. 使用策略

### 3.1 默认使用 FastCtx

所有普通文件操作默认使用 FastCtx：

- 新建、读取、写入和替换文件。
- 指定行区间、命中数和返回字节上限的读取与搜索。
- 需要聚合的高输出文件处理命令，使用 FastCtx `run` 后只读取摘要。

该默认路由不改变编辑安全边界：机械替换必须先 dry run 再使用 FastCtx `replace`；语义修改和小型精确补丁继续使用 `apply_patch`。FastCtx 优先指工具路由，不授权绕过既有编辑验证。

### 3.2 大输出必须先聚合

任何会产生高输出的文件读取、搜索、日志、rollout、JSONL、进程清单和完整诊断不得原样返回主会话。统一采用：

1. 子进程读取原始文件。
2. 子进程完成过滤、计数、排序和异常提取。
3. 子进程写出小型 `summary.json` 或等价摘要。
4. 主会话只读取摘要文件。

FastCtx 可以执行上述全部步骤；使用 shell/PowerShell 仅是实现聚合的可选方式，不构成 FastCtx 替代要求。原始内容只能留在子进程工作目录或既有日志位置，禁止作为工具结果直接回传。

摘要必须符合以下最小契约：

```json
{
  "schema_version": "fastctx-summary.v1",
  "status": "complete|partial|failed",
  "source": {"path": "...", "kind": "jsonl|log|text", "sha256": "sha256:..."},
  "query": {},
  "stats": {"records": 0, "bytes": 0, "max_input_tokens": 0},
  "findings": [],
  "offsets": [],
  "truncated": false,
  "omitted_records": 0,
  "generated_at": "RFC3339 timestamp",
  "errors": []
}
```

所有示例字段均为必填字段。摘要文件目标不超过 3000 个仓库侧传输估算 tokens（按 UTF-8 bytes/4 估算），硬上限为 12000 UTF-8 bytes（按最终写盘的 UTF-8 JSON 字节数计算），达到任一上限都必须设置 `truncated=true` 并记录 `omitted_records`。这不是 Codex 服务端真实 token 计量。`partial` 必须提供可继续处理的 `offsets`；`failed` 只返回错误摘要，不回退为原始文件输出。

正式摘要追加写入 `logs/tool-context/fastctx-summaries/<run-id>/summary.json`，作为验证证据保留。聚合过程不得复制原始来源；确需临时中间文件时只能放在子进程临时目录，由创建它的进程在完成后清理。

### 3.3 输出边界

- `read` 必须带有文件范围或行范围；单次模型可见结果最多 300 行且不超过 12000 UTF-8 bytes；遇到 `Partial` 时按偏移续读。
- `grep` 必须限制路径、glob、命中数和返回字段；单次最多 100 个命中且不超过 12000 UTF-8 bytes。
- `glob` 只返回路径和必要元数据，单次最多 500 个路径，不返回文件内容。
- 诊断摘要默认控制在 3000 tokens 以内。
- 原始日志只保存在子进程或日志文件中，不作为主上下文恢复源。
- 写入操作只返回成功状态、目标路径和必要错误，不回读无关内容。
- 删除不是默认文件操作；必须有当前任务的明确授权，递归删除必须单独确认精确目标。

### 3.4 路由判定与 fallback

完整路由规则的 owning document 为 `docs/fastctx-file-operation-output-contract.md`。根 `AGENTS.md` 只保留一条短路由并链接 owning document；通过压缩或替换现有 FastCtx 路由文字实现，不得使根文件净增长，且必须保持在 10000 字符硬上限内。单独新增未被根路由引用的说明文档不会改变运行时行为。规则如下：

| 条件 | 路由 | 结果约束 |
| --- | --- | --- |
| 所有普通文件读写、创建、替换和定量受限搜索 | FastCtx | 单次结果遵守行数、命中数和字节上限 |
| 超过单次输出上限的文件处理、日志、rollout、JSONL、进程清单 | FastCtx `run` 聚合 | 只读取 `fastctx-summary.v1` 摘要 |
| 摘要失败、范围不明确或无法证明输出受限 | 子进程继续聚合 | fail closed，不返回原始内容 |
| 明确授权的删除 | FastCtx 或受控 shell | 执行前确认精确路径并返回状态 |

如果外层 `functions.exec` 无法提供统一截断，路由不得直接把宽范围工具结果交给主会话；必须使用上述摘要路径。

### 3.5 工具轮次与 Skill 输入消费路由

不设置全局工具轮次硬上限。普通任务使用任务级软预算和逐级搜索：

1. 先用 `grep` 的 `summary`/`count` 判断匹配规模。
2. 再用 `files_with_matches` 确定候选文件。
3. 需要原文时使用 `content`，单次最多 100 个命中和 12000 UTF-8 bytes。
4. 最后用 `read` 读取精确行区间；多个相关文件优先使用 `read(files=[...])` 批量读取。

同一任务目标超过 6 次模型可见工具调用时必须复核检索范围；超过 8 次仍在探索同一目标时，必须转为一次 FastCtx `run` 聚合。只有 `Partial` 精确续读、源文件变化或上一次调用明确失败时允许继续单独调用；相同参数的失败调用不得原样重试。

Skill 输入消费不是 FastCtx 的子协议，而是独立的共享契约。完整定义、receipt schema、触发顺序、Skill 接入模板和 validator gate 见
[`docs/skill-input-consumption-contract.md`](skill-input-consumption-contract.md)。

本方案只规定 FastCtx 作为文件传输层时必须遵守的输出限制，并规定需要完整
输入的 Skill 必须调用共享适配器；FastCtx 不负责判断 Skill 的语义输入是否足够。

## 4. 实施边界

### 4.1 本仓库可直接处理

- 维护并验证 `docs/fastctx-file-operation-output-contract.md` 这一完整规则权威源，并以不增加根文件字符数的方式更新 `AGENTS.md` 短路由。
- 已增加 `scripts/python/summarize_fastctx_input.py` 和
  `scripts/python/validate_fastctx_summary.py`，摘要 schema 由
  `scripts/sc/schemas/fastctx-summary.v1.schema.json` 拥有，并由根
  `AGENTS.md` 短路由指向本契约的 FastCtx `run` 聚合规则。
- 已增加 `scripts/python/run_fastctx_ab_test.py`、
  `scripts/python/validate_fastctx_ab_test.py` 及对应
  `fastctx-ab-test.v1` schema，完成同一 fixture 的 5 次读取 + 5 次写入和
  高输出 JSONL 摘要验证。
- 按 [`docs/skill-input-consumption-contract.md`](skill-input-consumption-contract.md) 增加共享的 `skill-input-contract.v1` / `skill-input-consumption.v1` 适配器和 validator，供需要完整输入消费的 Skill 显式接入。
- 增加普通文件读写与高输出日志摘要的验证脚本，并保留不回传原始内容的
  failure fixture。
- 记录 A/B、smoke 和失败证据到 `logs/`。

### 4.2 需要单独确认的外部边界

- 全局 `C:\Users\Administrator\.codex\config.toml` 的预算修改。
- 外层 `functions.exec` 的嵌套输出截断或聚合实现。
- npm/Codex 二进制自身的上下文压缩行为。

如果外层编排层不在本仓库控制范围内，本仓库只提供“摘要后返回”的调用约束和验证证据，不声称修复平台实现。

## 5. 验收标准

### A. 功能

- 普通文件读写仍由 FastCtx 优先完成。
- 高输出文件、日志和 rollout 分析只向主会话返回摘要。
- 摘要包含来源、计数、最大值、异常项和必要偏移信息。
- `fastctx-summary.v1` 必须通过 schema validator；`complete` 不得带截断、
  omitted records 或 errors，`partial` 必须带 continuation offset，`failed`
  必须带 errors。
- 写入操作不会因验证而无意回读完整文件。
- 需要完整输入消费的 Skill 在 `ready=true` 前不会进入生成、修改或验收阶段。

### B. 上下文

- 受控基准完成 5 次读取 + 5 次写入：基线估算读取 9595 tokens，FastCtx
  契约结果估算 9870 tokens，增量 275 tokens（约 2.87%，低于 10%）。该
  数值只反映本仓库输出序列化策略，不代表外层会话的最终 input_tokens。
- 高输出 JSONL 摘要包含 600 条记录，摘要 3392 bytes（约 848 tokens），
  `status=complete`、无 omitted records、脱敏校验通过。
- 大型诊断任务的单次主会话工具返回不超过 3000 tokens；若平台边界无法保证，必须由子进程先落摘要，直接原始回传视为失败。
- 大型诊断 A/B 必须使用同一组文件、同一分析目标、同一调用数和同一提示词；记录最大 `last input_tokens`、累计 input、cached input、单次最大返回、压缩次数和失败数。
- 验收以当前窗口指标和压缩事件为准，不以累计 input 单独判定窗口占用。
- 同一任务目标超过 6 次调用时产生范围复核记录；超过 8 次继续探索时必须有聚合转换证据。
- 验证过程中不得出现未经限制的完整 rollout、日志或源码树回传。

### C. 回归与证据

- A/B 测试再次执行 5 读 + 5 写。
- 增加至少一次大 JSONL/日志摘要 A/B 测试，并验证摘要 schema、大小上限和失败闭合行为。
- 增加单一长文件完整分页、结构化目录缺少必需文件、分页期间源文件变化三类输入消费测试；后两类必须得到 `ready=false`。
- 记录每组的调用数、单次最大返回、累计 input、cached input、最终/最大 `last input_tokens`、压缩次数和失败数。
- 证据追加到 `logs/`，不覆盖历史记录。

## 6. 非目标

- 不修改恢复协议、world state 或恢复来源顺序。
- 不减少、重构或重新注入 BMAD/GDS Skill。
- 不要求所有 Skill 接入输入消费协议；接入范围由 Skill 的输入完整性需求声明。
- 不把 FastCtx 从系统中删除。
- 不修改第三方网关、公开地址、认证或运行时监听配置。

## 7. 建议实施顺序

1. 已实现摘要化输出约束和验证脚本。
2. 已运行普通文件 A/B 和高输出 JSONL 摘要验证。
3. `functions.exec` 的真实截断边界、全局 Codex 配置和服务端压缩行为仍是外部边界，仓库不声称已修改。
4. 暂不调整两个 6000 token 全局预算；预算修改需要独立确认和新的 A/B 证据。
