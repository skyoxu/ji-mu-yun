---
title: Phase B/C 身份、执行隔离与 Workspace 恢复
status: final
created: 2026-08-23
updated: 2026-08-23
source_requirements: execution-plans/2026-08-22-phase-b-c-identity-isolation-workspace-recovery-requirements.md
---

# PRD: Phase B/C 身份、执行隔离与 Workspace 恢复

## 0. 文档目的

本 PRD 定义 Ji Mu Yun 从单节点原型走向可安全演进的 AI Native SaaS 时，身份、租户隔离、受限执行和 Workspace 恢复的产品合同。它面向产品、Phase 服务、Sandbox/Runner、测试和后续架构工作；后续 `bmad-spec` 必须保持本文 FR、NFR、验收和开放问题的语义及来源追溯。

本文不授权实现、发布、数据库迁移或运行时配置变更。技术机制、当前仓库基线、威胁模型和架构待决项见 `addendum.md`；上游 requirements 仍是 provenance，而不是与本 PRD 平级的规范权威。

## 1. 愿景

Ji Mu Yun 必须能够可靠地回答三个基础问题：谁在操作哪个账户和项目、该操作实际能访问什么、以及一个工作区在机器或进程失效后如何恢复。今天的单节点 SQLite 与本地磁盘部署可以继续承担权威存储，但不能再让账户、绝对路径、运行进程和一次模型会话隐式地绑成不可迁移的整体。

本阶段使已认证成员能够在其账户的项目中运行受控工作，并在不泄露其他账户数据或平台秘密的前提下，从可校验快照恢复 Workspace。恢复的真相来自版本化 Workspace 内容、manifest、Attempt 和服务器端证据，而非浏览器状态、模型 thread 或人工日志判断。

成功后，产品具备可信的单节点多租户基础：可以继续快速迭代 Phase A/B，且未来可平滑演进为控制面、Worker/节点、账户或项目沙箱的树状部署，而无需推翻身份或恢复合同。

## 2. 范围与非目标

### 2.1 本阶段范围

- 账户/租户、成员、角色、凭据与会话的术语和服务端权威；
- 凭据撤销、轮换、账户停用、必要的保留语义和审计；
- API、数据库、文件、Runner、预览和恢复的账户/项目授权边界；
- 平台进程与用户 Runner 的 OS 权限隔离、路径 containment 和 ACL 漂移处置；
- Workspace 逻辑身份、本地 storage contract、快照 manifest、Restore Attempt、staging、发布、清理和重入；
- 恢复后的路由/readback、临时能力重建、审计、失败类型和验证证据；
- 为 future Worker/节点、placement、lease/fencing 保留兼容合同。

### 2.2 非目标

- 不重建旧前端或实现完整 React 管理/恢复 UI；
- 不以重构 `Program.cs` 为本需求前置或独立交付；
- 不实现多节点调度、对象存储、跨区域灾备、容器、microVM、E2B/Daytona/OpenHands 集成；
- 不实现 Codex App Server、长会话 registry 或让模型会话成为 Workspace 恢复权威；
- 不引入 Tasks、Taskmaster、`workflow.md` Chapter 3-7、overlay 或游戏模板流程；
- 不扩展无关的 Agent Asset Catalog、Doctor、MCP、ECC、Dashboard 或产品功能。

## 3. 术语

| 术语 | 定义 |
| --- | --- |
| Principal | 经过认证的人类或服务主体。 |
| Account / Tenant | 数据、资源和授权隔离边界。 |
| Member | Principal 与 Account 之间的成员关系。 |
| Role | Principal 在账户或平台范围内的权限集合。 |
| Credential / Session | 可撤销、可过期的身份凭据或会话载体。 |
| Workspace | 由 `workspaceId + accountId + projectId` 唯一标识的持久工作内容。 |
| Runner | 在受限 OS 身份和授权 Workspace 视图中执行用户代码或 Agent 任务的进程。 |
| Snapshot | 带版本化 manifest、内容完整性与归属信息的可恢复 Workspace 点。 |
| Restore Attempt | 一次独立、可审计、可重入的恢复执行记录。 |
| Placement | 节点、Runner、沙箱、端口等环境位置元数据；不定义 Workspace 或账户业务身份。 |

## 4. 用户与关键旅程

### 4.1 目标用户

- 账户成员：在自己被授权的项目中创建、继续和恢复 AI 辅助开发工作。
- 平台管理员：管理账户、成员资格、凭据状态和受控恢复操作，并审计结果。
- 恢复操作者：对故障、中断或权限漂移执行有权限边界的恢复与修复。
- Runner / Service Principal：执行有限作用域任务，不拥有租户生命周期或跨项目调度权威。

### 4.2 Jobs To Be Done

- 成员需要确信自己的项目与秘密不会因他人的 ID、路径或 Runner 行为泄露。
- 管理员需要停用账户或撤销凭据后，确定新活动被阻止且有可复核审计。
- 恢复操作者需要在主机或进程中断后，不依赖聊天上下文，安全地恢复可继续工作的 Workspace。
- 平台维护者需要在不提前建设多节点系统的情况下，避免现在的合同锁死未来 Worker 与沙箱演进。

### 4.3 关键旅程

- **UJ-1 成员在授权项目中启动工作。** 已认证成员选择自己的项目；服务端解析其 Principal、Account 和 Role；Runner 仅获得该 Workspace 的受限视图。若成员篡改账户或项目标识，服务端统一拒绝且不泄露目标存在性。
- **UJ-2 管理员撤销访问。** 管理员停用账户或撤销 Credential；后续 API、恢复、预览与新 Run 被拒绝，正在进行的任务按明确策略进入终止、draining 或原子步骤完成；审计可关联 actor、账户、Run 和结果。
- **UJ-3 恢复操作者恢复 Workspace。** 操作者请求恢复指定 Snapshot；服务端在 staging 中验证归属、schema、内容、配额、路径和 ACL，重建环境相关状态并原子发布。失败只留下可审计 Attempt 与隔离/清理状态，不发布半恢复 Workspace。
- **UJ-4 故障后的继续操作。** 恢复过程在阶段中断后，新进程从 Restore Attempt 和 staging 状态确定继续、回滚、隔离或重新开始；恢复后重新解析 hosted route/readback，并可启动受控 Run。

## 5. 产品能力与功能需求

### 5.1 身份、成员关系与凭据

- **FR-001 身份术语与临时兼容。** 系统必须区分 Principal、Account/Tenant、Member、Role 与 Credential/Session；若原型继续“一账户即一用户”，必须显式作为临时兼容模型，不得永久等同 Account ID 与登录主体 ID。`[PIWR-001]`
- **FR-002 服务端身份解析。** 所有受保护操作必须从经过验证的凭据与服务器端关系解析 Principal、Account 和 Role；浏览器传入的 `accountId`、路由参数或本地存储不得覆盖该上下文。`[PIWR-002]`
- **FR-003 生产身份方向。** 对外 SaaS 发布前必须确定生产身份方案、责任边界与迁移路径；默认产品方向为 OIDC-first，现有管理员 bearer token 仅用于 bootstrap、迁移或受控服务凭据。`[PIWR-003]`
- **FR-004 可撤销凭据。** Credential/Session 必须具有唯一标识、作用域、创建与最后使用信息、过期或撤销状态；服务端只存储安全派生值，轮换后旧凭据不能因缓存继续授权。`[PIWR-004]`
- **FR-005 停用与角色变更。** 账户停用、凭据撤销和角色变更必须在明确传播时间内阻断对应新活动；正在执行工作的处置策略必须可观察、可审计并由后续 Architecture 固定。`[PIWR-005]` `[PIWR-006]` `[PIWR-007]`
- **FR-006 管理与保留。** 管理员高风险操作必须使用独立认证授权与审计；本阶段至少支持可逆停用、立即撤销和明确保留状态，物理 purge 留作受控后续能力。`[PIWR-008]`

### 5.2 账户与项目隔离

- **FR-007 资源归属。** 项目、Run、Artifact、Package、Asset、Chat、Workflow、LLM 使用、Workspace、Snapshot、Restore Attempt 和 Preview 都必须有服务器拥有的 Account/Project 归属，孤立或冲突归属不得自动分配给请求者。`[PIWR-009]` `[PIWR-012]`
- **FR-008 统一授权边界。** API、后台操作和数据访问必须统一执行 Account/Project 授权；跨账户 ID 枚举在项目、Run、Artifact、Snapshot、Restore 和 Preview 上一致拒绝，响应不泄露目标存在性、路径或账户信息。`[PIWR-010]` `[PIWR-011]`
- **FR-009 私有响应与秘密保护。** 私有 API 必须使用适当的无缓存语义；错误和状态必须可被安全消费，浏览器响应、审计、普通 artifact、快照和日志不得包含明文 token、token hash、provider key 或未脱敏秘密。`[PIWR-013]` `[PIWR-014]`

### 5.3 Runner 与执行隔离

- **FR-010 平台/Runner 身份分离。** Phase 平台、数据库、代理配置和部署资产必须由平台身份拥有；用户 Runner 必须运行于低权限、可撤销的独立 OS 权限边界，不能继承平台管理员权限或平台服务凭据。`[PIWR-015]`
- **FR-011 跨账户 OS 隔离。** 即使应用层发生 bug，账户 A 的 Runner 也不得读取或写入账户 B 的 Workspace、snapshot staging、秘密目录或恢复输出；必须以真实权限负例证明，而不仅是路径字符串检查。`[PIWR-016]`
- **FR-012 安全路径与 ACL。** Workspace、快照、恢复和 artifact 路径必须由服务器逻辑标识解析并经过 canonicalization、root containment、traversal 与 symlink/reparse point 检查；创建、移动与恢复后必须验证 owner/ACL，权限漂移需隔离并阻止 Runner。`[PIWR-017]` `[PIWR-019]`
- **FR-013 可控 Runner 生命周期。** Runner 必须受超时、取消、并发和清理约束；同项目默认不并行重型写入执行，未来可演进为持久 lease/fencing，不能永久依赖进程内布尔锁。`[PIWR-018]` `[PIWR-038]`
- **FR-014 隔离等级透明。** 产品只可声明被真实证据覆盖的隔离等级；本阶段最低承诺为跨账户 OS 隔离，按项目临时身份、容器或 microVM 是具备触发条件的后续升级。`[PIWR-020]`

### 5.4 Workspace、Snapshot 与 Restore

- **FR-015 逻辑 Workspace 身份与 storage contract。** Workspace 必须由 `workspaceId + accountId + projectId` 唯一标识，绝对路径、节点和 Runner 身份仅是 Placement；所有快照、读取、恢复、删除、保留和校验通过稳定 storage contract 访问。本轮提供本地文件系统 backend。`[PIWR-021]` `[PIWR-022]`
- **FR-016 版本化 Snapshot。** 每个可恢复点必须发布版本化 manifest，涵盖 schema/兼容性、稳定身份、provenance、内容和排除项、ownership/ACL policy、恢复前置与保留状态，必要时含非权威 runtime refs；manifest 不得含明文秘密。`[PIWR-023]`
- **FR-017 确定 Snapshot 边界。** 产品必须定义受支持的持久项目内容和受控 artifact，明确排除 cache、临时构建产物、provider secret、进程、临时 ticket、绝对路径和不安全链接；相同输入与策略应可重算内容身份或等价完整性证明。`[PIWR-024]`
- **FR-018 用户控制的 Snapshot/Restore。** 每个项目默认不自动创建 Snapshot，也不自动触发 Restore。用户通过前端或受保护管理入口显式创建 Snapshot、选择 Snapshot 并发起 Restore；系统不得因普通文件变化、Run 完成、迁移或后台定时器自行触发这两类操作。每次操作仍必须创建独立、幂等、可审计的 Attempt。`[PIWR-025]`
- **FR-018a Snapshot 不可变。** 每次创建 Snapshot 都产生新的版本和 manifest；已发布 Snapshot 不得被更新、覆盖或原地修改。删除/过期只能改变其生命周期状态，不得改变历史内容身份。`[PIWR-023]` `[PIWR-031]`
- **FR-019 校验后发布。** Restore 必须在 staging 中完成身份/归属、schema/兼容性、hash/配额、路径安全、完整性、owner/ACL 和 route/readback 校验后，使用原子切换或等价 fail-safe 发布；失败必须回滚或隔离，绝不暴露半恢复 Workspace。`[PIWR-026]`
- **FR-020 环境状态重建与重入。** 恢复不得原样复用绝对路径、preview ticket、端口、PID、lease、Runner credential 或 secret；当前节点重新分配。崩溃、重启或取消后，系统必须从持久 Attempt 与 staging 决定继续、回滚、隔离或重启。`[PIWR-027]` `[PIWR-028]`
- **FR-021 文件化业务真相与 hosted route 兼容。** GDD、模块合同、源码、测试、execution-plan/项目内文件与持久 artifact 是恢复权威；Agent thread/session 仅为辅助引用。恢复后必须遵循现有 hosted route recovery 权威顺序，并只让当前账户读取当前结果。`[PIWR-029]` `[PIWR-030]`
- **FR-022 项目软删除与用户级空间配额。** 项目删除必须写入 `deleted` 标记并保留可审计元数据，不得立即物理删除。删除后的项目不再出现在普通用户工作区和新操作列表中；其逻辑配额立即释放给该用户，但保留数据的实际磁盘回收由受保护清理流程处理。Workspace 与全部 Snapshot 的空间统一计入用户级可用空间上限，而不是按项目预分配硬盘分区。`[PIWR-009]` `[PIWR-031]`
- **FR-022a 管理员 Snapshot 范围策略。** admin 后台必须能维护 Snapshot 内容范围策略；本阶段至少支持按文件扩展名黑名单排除内容（例如 `.jpg`、`.mp3` 等大型素材）。创建 Snapshot 时使用当时生效的策略并把策略版本写入 manifest；策略变化不修改历史 Snapshot。`[PIWR-023]` `[PIWR-024]`
- **FR-022b 替代根目录演练。** Snapshot 的保留、pin、过期、删除和失败 staging 清理必须受审计，不能误删正在恢复使用的 Snapshot；标准 fixture 必须可恢复到全新根目录或替代 Worker 环境，并验证内容、ACL、route/readback、后续受控 Run 与清理。`[PIWR-031]` `[PIWR-032]`

### 5.5 API、状态和未来拓扑兼容

- **FR-023 异步状态合同。** Snapshot、Restore、权限修复和未来 purge 等长操作必须返回稳定 Run/Attempt ID、状态与 evidence/readback pointer；浏览器连接不是执行生命周期。`[PIWR-033]`
- **FR-024 向后兼容与有界失败。** 公开 API 默认 additive；身份或 schema 破坏必须版本化或提供迁移窗口。状态和失败必须使用有界类型，原始异常只能进入受控诊断。`[PIWR-034]` `[PIWR-035]`
- **FR-025 浏览器是消费者。** 未来 React 只消费服务端返回的 Principal、Account、capability 和状态；隐藏按钮、路由守卫或本地缓存不能替代授权。本阶段不以改造旧前端为通过条件。`[PIWR-036]`
- **FR-026 Placement 与迁移兼容。** 数据合同可容纳 nullable `nodeId`、`runnerId`、`sandboxId`、`attemptId`、`leaseVersion/fencingToken` 和 `workspaceSnapshotId`，但不得据此推断 ownership；Snapshot/Restore 是未来 Worker 迁移边界，API/Worker 分离是演进方向而非本轮拆分部署要求。`[PIWR-037]` `[PIWR-039]` `[PIWR-040]`

## 6. 非功能需求

- **NFR-001 Fail closed。** 对身份、归属、路径、ACL、manifest 和 Restore 的验证默认拒绝；数据库与文件系统不一致时进入 typed recovery/repair，不得静默择一。`[PIWR-035]`
- **NFR-002 安全与数据最小化。** 秘密只在授权 Run/Runner 生命周期内按需注入；清理失败可检测并阻断复用。威胁模型至少覆盖 ID 枚举、traversal、reparse point、跨账户 Runner、stale credential/lease、恶意 snapshot 与配额耗尽。`[PIWR-014]`
- **NFR-003 一致性与幂等性。** 关键状态变更具备事务、幂等或补偿语义；发布前重新计算 manifest/content 完整性，半完成状态永不视为 ready。`[PIWR-025]` `[PIWR-026]` `[PIWR-028]`
- **NFR-004 兼容性。** SQLite migration 必须覆盖 fresh、upgrade 与 reuse；既有项目、Run、Artifact、route/readback 和 token 客户端默认继续可用；新 topology 字段允许为空并有确定解释。`[PIWR-012]` `[PIWR-034]`
- **NFR-005 可恢复性。** RPO 只承诺用户显式创建且成功发布、通过完整性验证的 Snapshot；系统不承诺每次文件变化都有恢复点。未发布写入可重做。标准 Workspace fixture 的恢复 RTO 目标为 P95 30 分钟内可启动受控 Run，fixture 规模与计时边界必须由 Spec 固定。`[PIWR-032]`
- **NFR-007 用户级空间控制。** 系统按用户统计活动项目 Workspace 与 Snapshot 的实际占用，拒绝超过用户级可用空间上限的新写入或新 Snapshot；删除项目释放其逻辑配额，但物理回收可异步完成。系统不得为每个项目预切硬盘分区，也不得仅因单个项目未用满配额而拒绝创建新项目。`[PIWR-031]`
- **NFR-006 可观测性。** 身份、授权、Run、Runner、Snapshot 与 Restore 事件关联 timestamp、status、action、actor/principal、account、project、workspace、run/attempt、node/runner（适用时）与 correlation ID；高基数内容进入受控 evidence。`[PIWR-033]`

## 7. 成功指标与反指标

### 7.1 成功指标

1. 跨账户 API、数据库、文件、Runner、Preview 和显式 Restore 的负例可重复通过。
2. 撤销 Credential 或停用 Account 后，约定传播窗口内不能启动新 Run、Restore、Preview 或读取私有资源。
3. 真实低权限 Runner 只能访问自身授权 Workspace，无法写平台二进制、SQLite、代理配置及其他账户 Workspace。
4. 用户显式创建的标准 fixture Snapshot 可恢复到替代根目录，随后通过内容、ownership/ACL、route/readback 和受控 Run 验证；普通文件变化不会隐式创建 Snapshot 或触发 Restore。
5. 损坏、错租户、版本不兼容、超配额或中断 Restore 不发布半成品。
6. 最终 evidence package 可由新进程从文件化证据复核，且不暴露秘密。

### 7.2 反指标

- 为获得未来扩展而提前实现 Worker fleet、对象存储、容器/microVM 或长会话 Agent Runtime。
- 将 Account 永久固化为登录用户，或让浏览器/模型会话成为身份和恢复真相。
- 仅用路径前缀或单元 mock 声称完成 OS 隔离。
- 以迁移旧前端、重排 `Program.cs` 或工具链流程替代实际身份、隔离与恢复闭环。

## 8. 验收要求

下游 Spec 必须保留并细化以下验收标识，不能将其简化为泛化的“测试通过”。

| ID | 验收结果 |
| --- | --- |
| PIWR-A01 | 浏览器篡改 `accountId` 不改变服务端 Principal/Account；受保护入口一致拒绝。 |
| PIWR-A02 | revoked credential、disabled account、无管理员角色的请求均被拒绝，缓存/旧会话不绕过。 |
| PIWR-A03 | project/run/artifact/snapshot/restore/preview 跨账户枚举被拒绝且不泄露存在性。 |
| PIWR-A04 | fresh、upgrade、reuse DB 保持有效数据；孤立/冲突 ownership 不被自动归属。 |
| PIWR-A05 | 真实低权限 Runner 可写授权 Workspace，不能写平台资产或其他账户 Workspace。 |
| PIWR-A06 | traversal、绝对/UNC/device path、symlink/reparse point 和 manifest escape 均不能越出授权根。 |
| PIWR-A07 | 创建、恢复、移动后 ACL 被验证；漂移进入隔离/修复并阻止 Runner。 |
| PIWR-A08 | Snapshot、日志与 artifact 不含 secret、临时 ticket 或绝对路径等禁止内容。 |
| PIWR-A09 | 用户显式创建的标准 Workspace Snapshot 可恢复到新根目录并通过内容、ACL、route/readback 与受控 Run；不存在自动触发路径。 |
| PIWR-A10 | 错账户、损坏 hash、未知 schema、超配额和不兼容版本在发布前失败。 |
| PIWR-A11 | 阶段性进程退出后可依据 Attempt/staging 继续、回滚或隔离。 |
| PIWR-A12 | Restore 后旧 preview ticket、端口、PID、secret、lease 失效，当前节点状态重建可用。 |
| PIWR-A13 | 同一幂等键不发布两个 Workspace；stale fencing token 不能覆盖 current。 |
| PIWR-A14 | Snapshot 保留、pin、不可变版本、用户级配额、软删除项目、admin 扩展名黑名单和 staging 清理均受审计；在用 Snapshot 不被误删。 |
| PIWR-A15 | 私有 API 无缓存，错误/状态有界，原始异常和秘密不进入浏览器。 |
| PIWR-A16 | nullable topology 字段加入后单节点行为不变，Restore 不依赖 nodeId 或绝对路径。 |
| PIWR-A17 | API 层具备授权正负例；React 完成后补 E2E，旧前端迁移不是当前门槛。 |
| PIWR-A18 | 最终 evidence package 覆盖隔离、OS 权限、round-trip、故障注入、DB upgrade、secret redaction，且新进程可复核。 |

## 9. 发布边界与依赖顺序

产品闭环按以下顺序推进：先确定术语、威胁模型、隔离等级和 Restore 发布语义；再并行推进身份/授权硬化、storage/manifest 合同与 Windows Runner/ACL 原型；其后实现本地 Snapshot/Restore；最后做受认证账户在受限 Runner 中恢复并继续运行的端到端证据。

对外身份 UX 与 React 管理/恢复界面在 API/domain 合同稳定后另行推进。实现分支可并行，但共享合同、fixture、数据库 migration 编号和 endpoint composition 必须受控整合，最终在同一候选版本执行 PIWR-A01 至 PIWR-A18。

## 10. 开放产品问题

| ID | 问题 | 建议方向 | 阻塞范围 |
| --- | --- | --- | --- |
| PIWR-Q01 | Account 是用户还是 Tenant？ | Account 作为 tenant，新增 Principal/Member；原型可一对一兼容。 | 身份模型、角色、审计。 |
| PIWR-Q02 | 生产身份方式？ | OIDC-first；现有 token 限定为 bootstrap/service/migration。 | 对外 SaaS 登录与 session。 |
| PIWR-Q03 | 停用、删除、保留如何处置？ | 本轮停用+立即撤销；purge 后续异步、保留期、显式确认。 | 数据保留与管理员 UX。 |
| PIWR-Q04 | 当前 OS 隔离粒度？ | 跨账户 OS 隔离为最低承诺；Architecture 在每账户或更细临时身份中决策。 | Windows 运维成本、承诺等级。 |
| PIWR-Q05 | Snapshot 内容边界？ | 持久项目文件/合同进入，cache/build/temp/secret/runtime capability 排除。 | manifest、规模、恢复一致性。 |
| PIWR-Q06 | 保留、配额、加密与 RPO/RTO？ | 先固定可测 fixture；存储介质加密与 secret 排除，远程 KMS 后续决定。 | 运营成本与恢复 SLA。 |
| PIWR-Q07 | React 接入时点？ | 先 API/domain/automation，React 稳定后补 E2E。 | 不阻塞后台闭环。 |

## 11. 下游交接

`bmad-spec` 应将本 PRD 转为 Canonical Spec Package，使用稳定 capability/acceptance IDs，保留未决项为 typed open question，并将本 PRD与上游 requirements 作为 provenance。`bmad-architecture` 必须基于当前 brownfield、Accepted ADR、适用 AGENTS.md、Phase 标准和 Spec 固定身份权威、Runner/ACL、Storage/Manifest/Attempt、崩溃恢复、路由重建、lease/fencing、兼容迁移和隔离升级门槛等不变量。Architecture 完成后，Spec refresh 将其纳入 adopted companion。

在用户明确创建完整 execution-plan 前，不进入 VDD 或实现流程。
