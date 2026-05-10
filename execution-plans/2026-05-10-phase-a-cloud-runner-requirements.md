# Phase A Prototype Lane 云端单机执行平台需求说明

- Title: Phase A Prototype Lane 云端单机执行平台需求说明
- Status: active
- Branch: main
- Git Head: 0b20008cb9110c8f74394a438a588c23c1c727ca
- Goal: 为当前仓库 Prototype lane 云端化定义一份可直接指导 Phase A 实施的完整需求说明，目标是在一台阿里云 ECS Windows 服务器上，把 Chapter 2 bootstrap 与 prototype 7day playable 工作流产品化为可通过浏览器、Web API 和 CLI 访问的单机原型开发平台。
- Scope: 仅覆盖 Phase A（Single-Node Prototype Lane Cloud Runner），包括公网账号登录、按账号限制项目数、单项目单工作区、Chapter 2 bootstrap 顶层编排、Prototype 7-day playable 顶层编排、prototype TDD、工件索引、Web API、最小浏览器界面、平台元数据、运行日志与运维约束；不覆盖 Chapter 3-7 正式交付编排、Phase B 多租户正式化和 Phase C 存储抽象与扩缩容。
- Current step: draft requirements specification
- Last completed step: read workflow index, cloud evolution plan, and execution plan template
- Stop-loss: 不重写现有仓库工作流决策逻辑；不把浏览器/API/平台 runner 做成第二套 orchestration engine；不把多租户、对象存储、复杂协作 UX 提前并入 Phase A。
- Next action: validate this execution plan doc and then derive implementation backlog and architecture slices
- Recovery command: py -3 scripts/python/validate_recovery_docs.py --dir execution-plans
- Open questions: 已澄清 1) Phase A Web API 需要公网访问并要求认证与 HTTPS；2) OpenAI/Codex 远程 LLM 执行纳入 Phase A 且沿用现有调用规则；3) 单机支持多项目，默认按账号项目上限为 2；4) workspace root 使用 `HOSTED_WORKSPACE_ROOT`，默认 `C:\workspaces`；5) 账号体系采用 single-admin + password/token；6) 每个项目只有一个 workspace；7) 浏览器用户不能配置 Git URL，项目由 admin 规则创建；8) Phase A 只实现完整 Prototype lane，包含 Chapter 2 和 prototype 7day playable 两个顶层路由编排，Chapter 3-7 暂不实现；9) 使用 `new-api` 作为可替换 LLM gateway，为每个账户提供独立模型访问、额度和计费；10) Phase A 的 `new-api` 用户/token 采用手动 admin 绑定，API 自动创建后置；11) HTTPS 终止使用 Caddy；12) LLM 成本止损默认 `2.00 CNY/run` 与 `20.00 CNY/account/day`；13) 首个项目创建规则为 `godot-prototype-default`；14) 当前服务器位于马来西亚，不默认适用中国境内生成式 AI 服务要求。仍待上线前决策：正式域名、Caddy 证书来源、AGPL 与上线地区合规姿态。
- Exit criteria: 1) 文档明确 Phase A 的目标、角色、边界、职责、接口、数据模型、部署形态、验收标准和实施顺序；2) 文档可直接作为后续 execution plan、ADR、任务拆分和实现验收输入；3) 文档内容不与 cloud-platform-evolution-plan 的核心原则冲突。
- Related ADRs: docs/architecture/ADR_INDEX_GODOT.md
- Related decision logs: n/a
- Related task id(s): n/a，因为本次工作是平台 Phase A 需求基线编写，不对应既有 Taskmaster task。
- Related run id: n/a，因为本次工作未绑定某一条 review pipeline 或 Chapter 6 运行记录。
- Related latest.json: n/a，因为本次工作是文档规划，不产生 task-scoped latest.json 权威工件。
- Related pipeline artifacts: n/a

## 1. 文档目的

本说明用于把 `docs/workflows/cloud-platform-evolution-plan.md` 中 Phase A 的方向，落实成一份可执行、可验收、可拆分任务的需求基线。

本说明服务的不是“另起炉灶的平台重写”，而是“把当前仓库现有工作流以内核形式托管到云端”的第一阶段产品化落地。

## 2. 背景与问题陈述

当前仓库已经具备完整的 repository-native 工作流内核，核心包括：

- `workflow.md`
- `AGENTS.md`
- `scripts/python/dev_cli.py`
- `scripts/sc/run_review_pipeline.py`
- `scripts/sc/llm_review_needs_fix_fast.py`
- `logs/ci/**` 下的恢复 sidecar
- `execution-plans/**`、`decision-logs/**` 下的 durable docs

当前痛点不在于缺少工作流，而在于该工作流主要面向熟悉仓库结构与本地命令拓扑的操作者。对云端托管场景而言，存在以下问题：

- 终端用户需要理解大量原始脚本入口，学习成本高。
- 长时间运行、断线恢复、跨设备续跑需要云端常驻工作区支持。
- 工件和 sidecar 虽然已经存在，但缺少统一的 Hosted 访问层与索引层。
- 当前 CLI、脚本、工件之间的关系对浏览器调用方并不友好。
- 缺少一个受控的、稳定的、产品化的顶层工具面，来暴露“恢复、路由、执行、查看工件、查看健康度”这些核心动作。

因此，Phase A 的问题定义是：

在不重写工作流逻辑的前提下，为现有仓库内核增加一个单机云端托管层，使其可以在一台阿里云 ECS Windows 机器上稳定运行，并通过浏览器、API 和平台内部 CLI 进行统一访问。

## 3. 总体目标

Phase A 的总体目标如下：

- 在一台 Windows 阿里云 ECS 上部署一个可长期运行的单机云端执行平台。
- 通过公网浏览器访问该平台，并在 Phase A 内提供 single-admin 账号、认证、HTTPS 终止和访问审计。
- 支持单机多项目原型开发，默认每个账号项目上限为 2。
- 每个项目默认只有 1 个 workspace。
- 浏览器用户不能自行配置 Git URL；项目由 admin-defined rules 创建。
- Phase A 提供完整 Prototype lane，包括 Chapter 2 repository bootstrap 顶层路由和 prototype 7day playable 顶层路由。
- Chapter 3-7 正式交付编排不属于 Phase A。
- 保留仓库脚本作为唯一执行真相来源和决策权威。
- 把现有仓库命令封装成稳定、低摩擦、可索引的 Hosted Tool Surface。
- 把 OpenAI/Codex 执行通过 `new-api` 可替换网关纳入托管 Runner，并提供审计、重试限制和成本止损。
- 平台继续拥有 account/project/workspace/prototype/run 状态；`new-api` 只负责模型路由、账户额度和 LLM 计费。
- 让操作者能够通过浏览器或 API 发起恢复、路由、执行和工件查看，而不必记忆底层脚本拓扑。
- 让任务恢复、项目健康扫描、任务工件查看在云端变成“产品能力”，而非“人工拼命令”。
- 为 Phase B 多租户化和 Phase C 存储抽象保留扩展边界，但不提前实现。

## 4. 核心原则

Phase A 必须遵守以下原则。

### 4.1 平台托管工作流，而不是替代工作流

平台只负责：

- 托管
- 触发
- 读取
- 恢复
- 暴露

平台不负责：

- 重写 workflow
- 二次解释路由决策
- 重算 stop-loss
- 在浏览器里复制脚本逻辑

### 4.2 执行权属于脚本

以下内容必须继续由仓库脚本负责：

- `preferred_lane`
- `Recommended command`
- `Forbidden commands`
- stop-loss families
- 审批状态迁移
- 质量门禁结论
- recovery consumption order

### 4.3 Git、Workspace、Browser 三层分离

- Git 是代码与持久文档真相源。
- Cloud Workspace 是运行时状态与恢复工件真相源。
- Browser 是交互访问面，不保存流程真相。

### 4.4 Hosted Entry 优先于自由拼命令

Phase A 应优先提供稳定的 Hosted 顶层能力，而不是要求调用方自行拼接原始命令。

### 4.5 Script-first，Skill-thin，Resolver-light

- 真正执行工作、写 sidecar、产生日志的能力必须是脚本。
- 技能层只负责指导如何使用脚本。
- 解析器只负责决定何时激活何种指导层，不得接管执行真相。

## 5. 目标用户与使用场景

### 5.1 目标用户

- 平台操作者：负责在 ECS 上维护和使用该托管平台的工程师。
- 开发操作者：通过浏览器或 API 触发任务恢复、执行、查看工件的开发者。
- AI/Agent 调用方：通过 API 或平台内 CLI 使用稳定工具面调用仓库工作流。

### 5.2 核心使用场景

- 创建或恢复一个云端工作区。
- 同步指定仓库和分支到工作区。
- 查看某个任务当前是否已有 active task / latest pipeline run。
- 发起 `resume-task` 读取恢复摘要。
- 发起 `chapter6-route` 判断下一步是 `run-6.7`、`run-6.8`、`inspect-first` 还是止损。
- 发起正式任务执行入口，由 Hosted Task Entry 委托到仓库顶层命令。
- 查看 `repair-guide.md`、`agent-review.md`、`summary.json`、`project-health/latest.html`。
- 在浏览器中查看审批状态，必要时提交审批决定。

## 6. Phase A 范围

### 6.1 In Scope

- 一台 Windows ECS 主机上的单节点部署。
- 单平台 Web Service，公网访问必须具备认证、HTTPS 和访问审计。
- 单 runner 管理模型，Phase A 默认每个项目最多一个活跃重型 runner。
- 多项目原型支持，默认每个账号项目上限为 2。
- single-admin + password/token 账号体系。
- 每个项目一个默认 workspace。
- admin-defined project creation rules。
- 首个 project creation rule 为 `godot-prototype-default`。
- `godot-prototype-default` 只允许 Chapter 2 bootstrap 与 Prototype lane workflows，并阻断 Chapter 3-7。
- Chapter 2 repository bootstrap 顶层编排。
- prototype 7day playable 顶层编排。
- prototype TDD 与 prototype scene creation。
- 基于本地磁盘的持久工作区。
- 基于 SQLite 的最小平台元数据数据库。
- 工作区生命周期管理。
- 仓库状态同步与恢复。
- Hosted 顶层脚本入口定义。
- 任务工件索引与聚合摘要。
- 最小 API。
- 最小浏览器 UI。
- 审批状态读取与写回。
- 平台级 stdout/stderr/命令日志记录。
- 基础健康检查与失败可诊断能力。
- OpenAI/Codex 执行审计、重试限制和成本止损。
- `new-api` account binding、request correlation 和 cost summary readback。

### 6.2 Out of Scope

- 正式多租户鉴权体系。
- 大规模多租户项目配额系统。
- 浏览器用户自定义 Git URL。
- Chapter 3 task triplet generation。
- Chapter 4 overlay baseline。
- Chapter 5 semantics stabilization。
- Chapter 6 formal task delivery。
- Chapter 7 UI wiring closure。
- 分布式 runner 队列。
- 多节点调度。
- 对象存储或远端文件存储抽象。
- 第二套工作流引擎。
- 浏览器内规则引擎。
- 复杂多 Agent 协作界面。
- 技能市场、技能发布平台。
- 全量 SaaS 化计费、组织管理、配额管理。

## 7. 功能性需求

## 7.1 工作区管理

平台必须提供工作区管理能力。

### 7.1.1 工作区创建

平台必须能够：

- 基于项目标识、分支、工作区 ID 创建工作区。
- 在磁盘上生成标准目录结构。
- 完成仓库 clone/checkout/sync。
- 初始化平台元数据文件。

### 7.1.2 工作区恢复

平台必须能够：

- 检测已有工作区是否存在。
- 恢复已有工作区而不是重复创建。
- 保留 `logs/**`、`logs/ci/active-tasks/**` 与历史 run sidecar。
- 允许在浏览器/API 上重新挂载到该工作区。

### 7.1.3 工作区同步

平台必须能够：

- 从 Git 远端获取最新分支状态。
- 把指定分支同步到工作区。
- 记录上次同步时间。
- 报告同步是否成功、是否冲突、是否需要人工处理。

### 7.1.4 工作区清理

平台应支持：

- 对过期工作区执行软清理或归档策略。
- 仅清理平台定义的工作区，不误删其他目录。
- 清理前记录工作区状态与最后活动时间。

## 7.2 Hosted 顶层执行入口

平台必须提供稳定的 Hosted Tool Surface，对外暴露仓库内核最重要的动作。

### 7.2.1 Phase A 必须具备的脚本级入口

Phase A 至少应具备以下能力，能力的最终落点应是仓库脚本：

1. `workspace-bootstrap-check`
   - 检查 Windows worker 上的依赖是否齐全。
   - 输出机器可读的 readiness 结果。

2. `describe-task-tools`
   - 输出当前稳定任务工具面。
   - 列出每个入口的输入、输出、依赖 sidecar、预期调用方。

3. `run-artifact-index-refresh`
   - 刷新 active task、latest、repair guide、agent review、execution plans、decision logs、project health 的紧凑摘要。

4. `run-hosted-resume`
   - 作为统一恢复入口。
   - 按仓库认可顺序调用 `resume-task`、`chapter6-route`、必要时 `inspect-run`。

5. `run-hosted-task`
   - 作为统一任务执行入口。
   - 委托到 `run-single-task-chapter6` 或其他稳定顶层命令。

6. `export-active-task-summary`
   - 输出前端友好的轻量摘要。

7. `read-approval-state` / `run-approval-sync`
   - 同步审批 sidecar 与平台状态。

### 7.2.2 入口能力约束

每个 Hosted 入口必须：

- 有稳定命名。
- 有机器可读输入输出。
- 明确依赖哪些仓库脚本。
- 明确写哪些平台元数据。
- 明确读写哪些仓库 sidecar。
- 失败时输出清晰错误与下一步建议。

### 7.2.3 禁止事项

Hosted 入口不得：

- 私自重算 workflow 决策。
- 在 API 内用 if/else 复写 `chapter6-route` 逻辑。
- 把审批状态机拆出仓库脚本另行维护。
- 跳过已有 stop-loss 直接执行深层命令。

## 7.3 Runner

平台必须具备统一 Runner。

Runner 必须：

- 只运行顶层仓库入口。
- 记录命令、开始时间、结束时间、退出码。
- 记录 stdout/stderr 到平台 runtime 目录。
- 关联 run 与 workspace、task_id、run_type。
- 支持查询运行状态。
- 支持取消正在运行的任务。

Runner 应支持：

- 一次仅处理一个重型运行任务，避免单机资源争抢导致状态污染。
- 对长任务提供心跳或状态更新时间。

## 7.4 工件索引

平台必须具备 Artifact Indexer。

### 7.4.1 必须索引的工件

- `logs/ci/project-health/latest.html`
- `logs/ci/active-tasks/task-<id>.active.md`
- task-scoped `latest.json`
- `summary.json`
- `execution-context.json`
- `repair-guide.md`
- `repair-guide.json`
- `agent-review.md`
- `agent-review.json`
- `execution-plans/**`
- `decision-logs/**`

### 7.4.2 索引层职责

索引层必须：

- 自动发现最新有效工件。
- 区分“权威原文件”和“前端摘要缓存”。
- 不在前端复制工件解析逻辑。
- 为前端提供 compact summary。
- 能够在仓库 sidecar 更新后刷新平台索引。

### 7.4.3 索引输出

索引输出至少应包含：

- 工件类型
- 文件路径
- 更新时间
- 所属 task_id / run_id
- 状态摘要
- 是否可恢复
- 是否为最新权威文件

## 7.5 Web API

平台必须提供最小 Web API。

### 7.5.1 项目接口

- `POST /projects`
- `GET /projects`
- `GET /projects/:id`

### 7.5.2 工作区接口

- `POST /projects/:id/workspaces`
- `GET /projects/:id/workspaces`
- `GET /workspaces/:id`
- `POST /workspaces/:id/sync`

### 7.5.3 运行接口

- `POST /workspaces/:id/run/resume-task`
- `POST /workspaces/:id/run/chapter6-route`
- `POST /workspaces/:id/run/chapter6`
- `POST /workspaces/:id/run/project-health`
- `GET /runs/:run_id`
- `GET /runs/:run_id/logs`
- `POST /runs/:run_id/cancel`

### 7.5.4 工件接口

- `GET /workspaces/:id/artifacts/active-task?task_id=...`
- `GET /workspaces/:id/artifacts/latest?task_id=...`
- `GET /workspaces/:id/artifacts/repair-guide?task_id=...`
- `GET /workspaces/:id/artifacts/agent-review?task_id=...`
- `GET /workspaces/:id/artifacts/project-health`
- `GET /workspaces/:id/artifacts/execution-plans`
- `GET /workspaces/:id/artifacts/decision-logs`

### 7.5.5 API 约束

API 必须：

- 返回结构化 JSON。
- 提供明确错误码和错误原因。
- 明确区分“命令已接受”“命令正在运行”“命令已完成”“命令失败”。
- 不在 API 层重写脚本的恢复顺序或执行策略。

## 7.6 浏览器 UI

Phase A 必须提供一个最小可用 UI。

### 7.6.1 必备页面

1. 项目列表页
2. 工作区列表页
3. 任务执行页
4. 恢复 / active task 页
5. 工件查看页
6. 项目健康页

### 7.6.2 任务执行页行为

任务执行页必须：

- 优先引导走恢复链，而不是直接重跑。
- 先触发 `run-hosted-resume` 或仓库恢复入口。
- 显示推荐动作、阻塞原因、最新工件。
- 只有在恢复结果允许时才开放正式执行按钮。

### 7.6.3 工件查看要求

工件查看页必须：

- 清楚区分 active task、latest、repair guide、agent review、project health。
- 能查看原始文本或渲染后的 HTML/Markdown。
- 能显示更新时间、所属任务、所属运行。

## 7.7 审批处理

Phase A 必须具备基础审批能力，但审批逻辑仍应以仓库 sidecar 和脚本为准。

平台必须：

- 读取审批状态。
- 展示 `pending`、`approved`、`denied`、`invalid`、`forbidden-command` 等状态。
- 允许操作者提交审批决定。
- 同步平台审批记录与 sidecar。

平台不得：

- 自创审批状态机。
- 绕过已有审批 sidecar 结论。

## 7.8 平台元数据

平台必须维护最小元数据模型。

### 7.8.1 SQLite 表

#### projects

- `id`
- `account_id`
- `name`
- `source_rule_id`
- `game_type`
- `game_type_source`
- `game_type_guide`
- `status`
- `created_at`

#### workspaces

- `id`
- `project_id`
- `account_id`
- `path`
- `status`
- `last_synced_at`

#### runs

- `id`
- `workspace_id`
- `task_id`
- `prototype_slug`
- `run_type`
- `command`
- `status`
- `started_at`
- `finished_at`
- `run_dir`
- `stdout_path`
- `stderr_path`
- `exit_code`
- `runner_lock_key`
- `llm_backend`
- `llm_gateway`
- `llm_request_id`
- `llm_model`
- `llm_cost_json`

#### approvals

- `id`
- `workspace_id`
- `task_id`
- `status`
- `decision`
- `reason`
- `updated_at`

#### runner_locks

- `lock_key`
- `project_id`
- `workspace_id`
- `run_id`
- `status`
- `acquired_at`
- `heartbeat_at`

#### project_limits

- `id`
- `account_id`
- `max_projects`
- `updated_at`

#### accounts

- `id`
- `username`
- `password_hash`
- `api_token_hash`
- `status`
- `created_at`

#### account_llm_bindings

- `id`
- `account_id`
- `provider`
- `gateway_base_url`
- `external_user_id`
- `token_ref`
- `quota_policy`
- `status`
- `created_at`
- `updated_at`

### 7.8.2 元数据约束

平台元数据用于索引和访问，不得替代仓库工件真相。

换言之：

- `meta/` 记录平台视角
- `repo/logs/**` 记录工作流视角

二者不应混淆。

## 8. 非功能需求

## 8.1 平台运行环境

Phase A 运行环境必须为 Windows。

必需依赖：

- Windows Server 环境
- `git`
- `python`
- `node.js`
- `codex`
- `.NET SDK 8`
- `Godot .NET`
- 项目运行所需依赖
- 启用 LLM gateway 时的 `LLM_GATEWAY_PROVIDER`
- 启用 LLM gateway 时的 `LLM_GATEWAY_BASE_URL`
- 启用 LLM gateway 时的 `LLM_GATEWAY_TOKEN_MODE`
- 启用 LLM gateway 时的 `LLM_GATEWAY_BINDING_MODE=manual-admin`
- `HTTPS_TERMINATION=caddy`
- `APP_BIND_URL=http://127.0.0.1:8080`
- `PUBLIC_BASE_URL=https://<your-domain>`
- `LLM_COST_STOP_LOSS_PER_RUN_CNY=2.00`
- `LLM_COST_STOP_LOSS_DAILY_ACCOUNT_CNY=20.00`
- `HOSTED_WORKSPACE_ROOT`，默认 `C:\workspaces`
- `HOSTED_PROJECT_LIMIT`，默认每个账号 `2`

## 8.2 可恢复性

平台必须以 sidecar 驱动恢复为基本能力。

要求：

- 平台重启后，不丢失工作区。
- 浏览器断开后，可重新进入并查看最新恢复结果。
- 运行失败后，可从工件和 runtime 日志回放失败原因。

## 8.3 可观测性

平台必须记录：

- 每次运行命令
- 开始/结束时间
- 退出码
- stdout 路径
- stderr 路径
- 对应 workspace / task / run_type
- OpenAI/Codex backend label、执行耗时、退出状态与可用成本元数据
- `new-api` request id、model、gateway label 与 cost summary 关联信息

## 8.4 安全与边界

Phase A 即使在单机模式，也必须遵守仓库现有主机边界规则。

至少包括：

- 工作区隔离在文件系统边界内。
- 公网访问必须认证。
- 公网访问必须 HTTPS。
- 写操作必须记录用户、项目、工作区、操作、时间和结果。
- 不允许任意目录执行或任意目录读写。
- 不允许浏览器提交任意 shell 命令。
- `OPENAI_API_KEY` 不写入 SQLite 或 git-tracked 文档。
- 上游 provider key 由 `new-api` 管理，不进入 Phase A 平台数据库。
- Phase A 平台只保存 `new-api` 绑定引用和调用关联信息，不依赖 `new-api` 内部数据库表。
- 保持 `res://` / `user://`、HTTPS only、`ALLOWED_EXTERNAL_HOSTS`、`GD_OFFLINE_MODE` 等既有边界不被平台层弱化。

## 8.5 性能与响应

Phase A 不要求大规模并发，但必须满足：

- 恢复类请求应快速返回结构化状态。
- 长时任务应异步运行。
- 浏览器轮询或查看工件时不阻塞 runner 主执行链。

## 9. 目录与部署形态要求

## 9.1 工作区目录

推荐目录结构如下：

```text
%HOSTED_WORKSPACE_ROOT%/<account>/<project>/<workspace-id>/
  /repo
  /runtime
    /stdout
    /stderr
    /commands
  /meta
    workspace.json
    latest-run.json
    approvals.json
```

说明：

- `repo/` 内包含仓库 checkout 与仓库原生 `logs/**`。
- `runtime/` 是平台级日志。
- `meta/` 是平台级元数据。

## 9.2 部署形态

Phase A 推荐部署在一台阿里云 ECS Windows 主机上，包含：

- 一个常驻 Web Service，推荐 ASP.NET Core 8 Minimal API
- 一个 ECS-local Caddy 或 Nginx HTTPS 终止层
- 一个本地 SQLite 数据库
- 一个本地工作区根目录
- 一个按项目加锁的统一 Runner 管理模型

## 10. 交互流程需求

## 10.1 恢复优先流程

当用户进入任务执行页时，平台必须优先执行：

1. 读取 active task / latest 工件
2. 执行 hosted resume
3. 呈现推荐动作
4. 根据推荐动作决定是否开放正式执行

不得直接默认执行完整 Chapter 6。

## 10.2 正式执行流程

当用户明确执行任务时，平台应：

1. 校验 workspace 状态
2. 校验依赖就绪
3. 记录平台 run 元数据
4. 调用 hosted task 入口
5. 实时或准实时暴露运行日志
6. 运行结束后刷新工件索引

## 10.3 项目健康查看流程

当用户查看项目健康时，平台应：

1. 查询最近健康工件
2. 必要时触发 `project-health-scan`
3. 返回 `latest.html` 或结构化摘要

## 11. 非目标与禁止演化

Phase A 明确不做：

- 第二套路由器
- 第二套审批状态机
- 第二套质量门禁解释器
- 对象存储强依赖
- 分布式工作区
- 多节点任务调度
- 技能商城
- 复杂会话总线
- 以自然语言控制替代仓库脚本权威

## 12. 验收标准

Phase A 至少应满足以下验收标准。

### 12.1 环境验收

- Windows ECS 上所有核心依赖安装完成。
- `workspace-bootstrap-check` 能输出机器可读 readiness。

### 12.2 工作区验收

- 能创建、恢复、同步一个工作区。
- 能创建多个项目，默认上限为 2。
- 项目上限按账号计算。
- 每个项目只有 1 个默认 workspace。
- 项目创建来自 admin-defined rules，不接受浏览器用户输入任意 Git URL。
- 工作区可保留仓库 `logs/**` 与恢复工件。

### 12.3 运行验收

- 能远程执行已有顶层命令。
- 能记录并查询 run 状态。
- 能取消运行中的任务。
- 同一项目最多一个活跃重型 runner。
- 不同项目可以在主机能力允许时并发运行。
- Chapter 2 bootstrap route 可运行并产出 project-health。
- Prototype 7-day playable route 可运行并产出 prototype record / sidecar / TDD evidence。
- Chapter 3-7 formal delivery routes 不在 Phase A 暴露。

### 12.4 恢复验收

- 用户可从浏览器触发恢复。
- 平台能展示 `resume-task` / `chapter6-route` 的核心结果。
- 平台不重写恢复决策。

### 12.5 工件验收

- 能查看 active task、latest、repair guide、agent review、project health。
- 工件更新后索引可刷新。

### 12.6 UI 验收

- 具备六个最小页面。
- 任务页能先恢复再执行。

### 12.7 API 验收

- 最小项目、工作区、运行、工件接口可用。
- 公网访问路径具备认证和 HTTPS 决策。
- API 响应结构一致，错误可诊断。

## 13. 实施优先级与推荐建设顺序

Phase A 应按以下顺序建设：

1. 工作区管理
2. 顶层 Runner
3. Artifact Indexer
4. Web API
5. Browser UI
6. 审批处理

在脚本层内部，应遵循：

1. 先补脚本级 hosted entrypoints
2. 再补薄技能层
3. 最后补轻量 resolver 规则

## 14. 后续拆分建议

本需求说明完成后，建议进一步拆成以下交付物：

- 一份 Phase A 架构 ADR / 决策日志
- 一份 Phase A 技术架构文档
- 一份 Hosted Entrypoints 契约文档
- 一份 Workspace/Run/Artifact/Approval SQLite schema 文档
- 一份 API OpenAPI 草案
- 一份 UI 页面线框与状态流说明
- 一份实施 backlog

## 15. 一句话结论

Phase A 不是“把仓库工作流改写成云平台”，而是“在一台 Windows ECS 上，把现有仓库工作流托管成一个可恢复、可执行、可查看、可调用的单机云端产品外壳”。
