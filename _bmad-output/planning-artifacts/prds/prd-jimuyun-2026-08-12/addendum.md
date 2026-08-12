# Addendum：恢复标准技术与策略背景

本文件保存不属于 PRD 功能叙述、但对后续架构和执行计划重要的机制背景。

## 1. 与 OpenAI 原生能力的关系

根据 2026-08-12 通过 MCP 获取的 official OpenAI documentation：

- `codex exec resume --last` 和 `codex exec resume <SESSION_ID>` 是非交互 session 续接入口。
- `codex exec --json` 提供 thread、turn、item 和 error 结构化事件，`--output-schema` 可约束最终输出。
- `--ephemeral` 不持久化 session rollout，因此不能依赖原生 session resume。
- Codex App Server 提供 `thread/start`、`thread/resume`、`thread/fork`、`thread/read` 和 `thread/list`。
- start、resume 和 fork 返回 `instructionSources`，可核验加载的指令来源。
- `thread/fork` 复制已存历史，`lastTurnId` 只限制复制到哪个 turn。“干净续接”应使用新 thread 加已验证 handoff。
- Responses API compaction 产生 opaque encrypted compaction item，用于减少上下文；它不是仓库、Phase 或用户沙箱任务状态权威。
- Memories 是辅助召回层；必须生效的规则应保存在 `AGENTS.md` 或受控文档。
- 长任务模式不会扩大 sandbox 或审批权限。
- App Server WebSocket transport 在官方文档中标记为 experimental/unsupported for production；本 PRD 仅把它视为未来可探测的传输能力，不将其作为 Hosted 生产恢复前提。

官方页面：

- https://learn.chatgpt.com/docs/non-interactive-mode.md
- https://learn.chatgpt.com/docs/app-server.md
- https://developers.openai.com/api/docs/guides/compaction.md
- https://learn.chatgpt.com/docs/customization/memories.md
- https://learn.chatgpt.com/docs/long-running-work.md

获取链路使用 `mcp__webFetch__fetch` 经 `r.jina.ai/https://<official-url>` 转取，MCP 配置 UA 为 `ChatGPT-User`。Jina 是第三方传输边界，事实来源仍为返回内容标记的 OpenAI 官方 URL。

## 2. 从 Chapter 6 研究中提炼的能力

### 2.1 推广到共享标准的模式

- 稳定 task/run/turn/item 身份和单调 turn 序号。
- 追加式事件流；稳定 event family 优先于自由文本事件名。
- Inspect-first 和由浅入深的读取顺序。
- 生产者拥有 summary，消费者按声明字段消费。
- 推荐动作、允许动作、禁止动作与原因来自同一 canonical 状态。
- 完整性优先于“最新”；planned-only、dry-run、不完整或 stale bundle 只能作证据。
- 审批是确定性状态机，未决状态不能靠强制 resume/fork 绕过。
- 重复失败、仓库噪声、超时无新信息和无新修复输入触发 stop-loss。
- 已验证阶段条件复用，失效环节定向重做，旧失败证据保留。
- checkpoint、失败、恢复次数、墙钟和上下文刷新预算可见。

### 2.2 明确不继承的 Chapter 6 特例

- Taskmaster task ID、Delivery Profile、6.3 至 6.9 步骤名。
- `sc-test`、Needs Fix Fast、repo-noise 的命令和阈值。
- Chapter 6 sidecar 路径、字段别名和 active-task Markdown。
- 本地 Python CLI、Git snapshot、Godot 参数和 Review lane。
- Chapter 6 本地审批动作与具体 CLI 参数的映射。

这些特例不进入新协议，也不通过 adapter 暴露给新协议。Chapter 6 当前是本地文件协议，不提供 RPC、daemon、多客户端协调或 Web 重连；它只作为设计研究样本，不是 Phase 远程控制面的输入或依赖。

### 2.3 断开声明

Chapter 6 不属于新协议的运行时依赖、输入来源、状态权威、current/snapshot/cache/LKG、adapter、parity 基线、兼容对象、迁移对象或发布门。新协议不会读取 Chapter 6 sidecar、`latest.json`、producer 输出或 CLI，也不要求 Chapter 6 为新协议改造。双方可独立演进。

## 3. 三层控制模型

| 责任层 | 状态位置 | 策略控制者 | 完成权威 |
| --- | --- | --- | --- |
| 工具链控制面 | execution plan、run sidecar、review/acceptance evidence | 仓库控制面与对应 Skill contract | 各流程 validator/terminal predicate |
| Phase 服务层 | metadata、run/attempt/dispatch、policy、Hosted envelope | Phase 服务 | Phase route 和服务状态机 |
| 用户沙箱层 | 游戏项目文件、route、goal、repair、diagnostic、acceptance | Phase 服务控制，项目状态仅提供受限输入 | 当前项目 validator、diagnostic 和 acceptance evidence |

用户沙箱是由 Phase 托管的游戏长任务执行域。用户拥有游戏工作区和产物，但不拥有恢复策略权；Phase 根据共享协议、当前 route/goal/session 和 live blocker 自动执行恢复。用户只能提供业务意图、确认破坏性选择或取消自己的任务。

## 4. Checkpoint 的权威定位

Hosted checkpoint 不成为 ADR-0036 八级来源中的第九级，而是现有来源的可验证投影：

1. 来源由 Phase 选择和冻结。
2. compiler 读取白名单并生成最小上下文。
3. validator 重算 schema、hash、identity、freshness 和 live blocker。
4. 当前 `AGENTS.md`、Skill 和平台规则由宿主重新加载。
5. 恢复上下文带 `authorizes: []`。
6. 最终完成仍由 route validator 和 acceptance evidence 决定。

若未来改变八级来源、优先级或完成权威，必须更新或 supersede ADR-0036，不能通过 Profile 暗改。

## 5. 建议的架构分工

共享恢复内核拥有 Profile registry、canonical checkpoint/handoff schema、context compiler、identity/hash/freshness validator、redactor、budget evaluator、decision engine、append-only evidence contract 和 transport capability adapter。

消费者 adapter 只把本消费者状态映射为共享输入，声明必需来源、动作和安全 checkpoint，并调用本消费者 validator。它不复制共享 schema，也不建立新的通用状态机。

Phase Hosted adapter 绑定 account/project/workspace generation/route/run/attempt/dispatch，遵守八级恢复顺序和 E2 envelope，由 Phase 决定 observe/enforce、预算、动作和传输，并在产品判断边界进入 manual pause。

## 6. 独立构建建议

1. 从研究结论重新定义独立 schema、canonical 动作和 reason code，不复制 Chapter 6 合同。
2. 新建独立 golden fixtures、validator 和回归测试，不导入 Chapter 6 运行工件。
3. 将四类 Skill 的连续性状态映射到共享 Profile，而不是重写它们或为每个 Skill 自建协议。
4. 共享内核先 observe，比较决策 hash、动作、reason code 和成本。
5. Hosted 路线先选择一个多步骤游戏长任务做端到端验证。
6. 所有旧 evidence 保持不可变；旧证据不会自动成为新协议输入，变更时创建新 revision 或 successor。
7. Chapter 6 保持现状，不读取、不修改、不适配；受保护的 Phase LLM/Codex 入口只有在 ADR 与批准完成后才修改。

## 7. 被拒绝的方向

- 替换 Codex resume。
- 依赖自动 compaction 作为业务恢复。
- 每个 Skill 自建协议。
- 允许子 LLM 自主选择来源。
- 让游戏用户选择恢复模式。
- 跨三层共享 current、snapshot、cache 或 LKG。
