# Ji Mu Yun 四域知识与上下文工程 Canonical 实施合同

- Status: Original Requirements
- Plan ID: `jimuyun-four-domain-knowledge-context.v1`
- Date: 2026-07-25
- Original requirements file: `execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan.md`
- Target milestones: Phase E1 Projection, then Phase E2 Knowledge/Context Release
- Explicit exclusion: Phase E3 Runner Isolation Closure

## 0. Original Requirements Authority Notice

- Document role: `original-requirements` and preserved pre-split requirements source.
- Current executable plan authority after `plan-ready`: `execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/00-index.md` and its machine contracts.
- Accepted decision authority: `docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md`.
- `docs/know1.txt` through `docs/know5.txt` remain requirement-evolution sources only.
- Any legacy sentence below that calls this standalone file canonical, says no VDD directory will be created, or asks for a future ADR is retained as source provenance and does not override the split plan or Accepted ADR-0044.
- K5 ambiguity classification must delegate to `scripts/sc/_llm_backend.py::run_llm_exec`; direct provider calls and local `codex exec` construction are forbidden.
- Plan-local schemas, fixtures, requirement ledger, source-generated inventories, and composition validator are materialized under `execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/`.
- Bootstrap Review has not run. A whole-directory PASS authorizes only `plan-ready`, never production implementation or protected-path writes.
- The 2026-07-25 maintenance and consumption amendment adds a repository-local `maintain-knowledge-base` Skill contract and a canonical deterministic Knowledge Locator contract. It does not claim either implementation exists.
- At the Locator boundary, caller intent may come from a human or LLM, but authority, permission, snapshot, scope ceiling, and budget fields are supplied and validated by a trusted adapter or server Registry.


## 1. 文档权威、适用范围与来源谱系

### 1.1 Canonical 声明

本文件是“四域知识与上下文工程”专项唯一的现行方案权威。后续设计、任务拆分、验收、评审和实现必须引用本文件及其精确版本，不得再把 `docs/know1.txt` 至 `docs/know5.txt` 拼接成现行合同。

`docs/know1.txt` 至 `docs/know5.txt` 继续保留为需求演进来源，只用于来源追溯、冲突解释和历史分析。它们不能单独或联合覆盖本文件，也不能直接授权代码、数据库、运行时、Hosted workspace 或保护路径变更。

本文件只在本专项内具有 canonical 方案地位。它不能覆盖仓库上位权威。Phase 决策仍按以下顺序解析：

1. Accepted Phase ADR。
2. `AGENTS.md` 硬规则。
3. 当前运行时事实、源码和兼容合同。
4. `docs/architecture/phase-service/**`。
5. `docs/standards/**`。
6. `README.md` 和导航文档。

该顺序用于解析 Phase 产品、架构和合同语义，不改变 Agent 指令优先级。`AGENTS.md` 中的编码、保护路径、授权、运行和变更合同始终是不可协商的执行约束；任何 ADR 都不能让执行者绕过这些约束。

如果本文件与上位权威冲突，实施必须 fail closed，并先更新本文件或完成 ADR 的接受、更新或 supersede；不得通过实现代码隐式选择一方。

本专项实施时必须同时读取 `docs/architecture/phase-service/_index.md`、`docs/architecture/phase-service/prototype-routes-and-recovery.md`、`docs/architecture/phase-service/llm-codex-execution.md`、`docs/architecture/phase-service/metadata-db.md`、`docs/architecture/phase-service/hosted-workspaces-and-artifacts.md`、`docs/architecture/ADR_INDEX_PHASE.md` 和 `docs/standards/phase-service.md` 的 current revision。它们继续拥有各自的架构、API、DB、安全和运行语义。

### 1.2 来源谱系冻结

本版本基于以下 UTF-8 源文件字节生成。SHA-256 用于证明本次吸收的需求版本，不赋予来源文件现行权威。

| 来源 | SHA-256 | 本文件中的角色 |
| --- | --- | --- |
| `docs/know1.txt` | `aa221f7afc57508163ffb45929195b49aec610313b313059a646a644d083f4e7` | 早期需求演进来源 |
| `docs/know2.txt` | `d4a040f1f6d4d48b9722f5c6b2629e7593ea754fa9262235531516ffd141a965` | 早期需求演进来源 |
| `docs/know3.txt` | `025cd31cf2d92b1cca804012608081971881195884e7a4277be143da9621af40` | 中间修订来源 |
| `docs/know4.txt` | `d1fc0b9083086abe8f44e93feb870d557388cf6b6dbd36407dd54ae852a57455` | 完整基础合同骨架 |
| `docs/know5.txt` | `4072f73efe574d97161879a1a8a4e1356595d5082e880a22f0802ad21cbcf44f` | E1/E2、inventory、合同组合、签名、tokenizer、evaluation、K0、保存与预算增量 |

未来需求变化必须直接修订本文件并记录变更理由。仅更新 `know*.txt` 不会改变现行方案。

### 1.3 本文件授权与不授权的事项

本文件定义目标合同、实施顺序和验收门槛，但当前状态为 `Proposed`。它不证明任何 Schema、Projection、Context Manifest、Scope Gate、迁移或 E1/E2 能力已经实现。

本文件不授权以下动作：

- 修改 `AGENTS.md` 列出的保护路径。
- 修改 live metadata DB 或真实 Hosted workspace。
- 启动、恢复或改变 Phase A 生产运行时。
- 启动正式 Bootstrap Review 的模型评审层。
- 把 `execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md` 中的未来能力描述为当前能力。
- 把 E2 描述为文件系统、进程、账号或多租户强隔离。

## 2. 目标、非目标与当前仓库事实

### 2.1 目标

本专项建立一个确定性、可验证、可恢复的知识与上下文控制面：

- 用四个正交维度描述查询和执行边界。
- 为 Toolchain、Phase、Workspace、Marketplace 建立可独立维护的知识域。
- 先交付只约束检索候选的 Phase E1 Projection。
- 再通过父进程 Context Assembler、服务端权限交集、run-bound Manifest 和三类共享入口 Scope Gate 交付 Phase E2。
- 复用现有 Hosted route recovery、prompt scan、数据库证据绑定和 live blocker 合同，不建立第二套业务权威。
- 用来源 snapshot、可重建 inventory、签名、防重放、预算、omission evidence 和迁移证据证明一次模型调用实际获得了什么上下文。
- Provide one deterministic Knowledge Locator core with a CLI-first JSON contract so CLI, Skill, Tool, MCP, and later Phase adapters receive the same source-location decision.
- Provide a thin repository-local maintenance Skill that compares current knowledge entries or one explicitly scoped consumer object with a pinned local `refs/heads/main` commit and updates only derived knowledge artifacts plus append-only evidence.

### 2.2 非目标

- 不替换 `workflow.md`、VDD、Taskmaster、Chapter 3-7 或 Bootstrap Review 控制面。
- 不为本单文件方案创建 VDD execution-plan 目录。
- 不在 E1/E2 内实现 Windows runner identity、NTFS ACL、restricted token、独立进程根或网络隔离。
- 不把 embedding 或未固定版本的模型作为第一版检索基线。
- 不让 Knowledge Projection、项目配置、项目局部 Skill 或 Marketplace 内容成为权限根。
- 不在 K0 使用真实账号、真实 token、真实 provider secret、live DB 或受保护 workspace。
- 不把固定调用点数量当作迁移完成证据。
- Do not make the caller LLM an authority for permission, source revision, allowed Domain, path allowlist, budget, confidence threshold, or protected-data access.
- Do not let the maintenance Skill modify the inspected consumer object or discover unregistered repository content when no target is supplied.

### 2.3 2026-07-25 当前事实基线

- 本专项尚无可声明 ready 的 Phase E1 或 E2 实现。
- Phase 已有 `hosted-route-recovery-order.v1`、`hosted-route-forbidden-source-scan.v1`、`project_route_prompt_evidence_bindings`、same-project succeeded run binding、authoritative source-hash recomputation 和 latest live acceptance blocker 等独立现行合同。
- `CodexHostedProcessCommandFactory.Build` 当前可观察到 9 个生产服务调用点；这个数字只是生成 inventory 前的观察值。
- `_llmRouteEngine.CompleteAsync` 当前可观察到至少 18 个生产调用语句，Python `run_llm_exec` 另有多个调用方；因此“九个调用点”不能代表全部 Hosted LLM/Codex 面。
- `ProjectWorkspaceSeeder` 当前不排除 `.cache`，根 `.gitignore` 也未定义 `.cache/knowledge`。把动态知识缓存放进根仓会被新 workspace 初始复制，存在递归、污染和跨生命周期泄漏风险。
- `execution-plans/2026-07-11-phase-frontend-boundary-hardening-execution-plan.md` 仍为 `paused`，其 BH-HANDOFF 尚不能被计划就绪验证替代。
- ADR-0033、ADR-0035、ADR-0037、ADR-0038 为 Accepted；ADR-0040 仍为 Proposed，不能授权 E3。

上述计数和状态必须在实施时从新 source snapshot 重新计算，不能作为常量硬编码。


当前实现锚点为：

- `PhaseA.Platform/Workflow/HostedRouteRecoveryContract.cs`：八源恢复顺序。
- `PhaseA.Platform/Workspaces/ProjectWorkspaceSeeder.cs`：模板复制、同步和排除行为。
- `docs/adr/ADR-0033-phase-metadata-sqlite-local-disk.md`：metadata DB 权威。
- `docs/adr/ADR-0035-phase-controlled-runner-workspace-execution.md`：runner/workspace 边界。
- `docs/adr/ADR-0037-phase-shared-llm-codex-entrypoints.md`：共享 LLM/Codex 入口。
- `docs/adr/ADR-0038-phase-evidence-sidecars-readback.md`：evidence/readback 和 prompt binding。
- `docs/adr/ADR-0040-phase-c-hardening-before-scaleout.md`：仍为 Proposed 的 E3 下游边界。

## 3. 四个正交维度

系统不得再使用单个 `scope` 字段同时表示知识类型、可见性、数据实例和隔离强度。所有配置、查询、Projection、Manifest、gate result 和运行证据必须显式携带以下四个维度。

### 3.1 Domain Scope

回答“当前任务主要属于哪个知识域”。每次查询或执行必须有且只有一个 `primary_domain`：

```text
toolchain
phase
workspace
marketplace
```

跨域内容只能经服务端允许的依赖闭包进入候选集，不能通过查询文本隐式扩域。

### 3.2 Per-Domain Visibility

回答“某项内容在指定 Domain 中以什么方式出现”。Visibility 是映射，而不是文件的全局属性：

```text
visibility[domain] = active | dependency | conditional | historical | excluded
```

| 值 | 语义 |
| --- | --- |
| `active` | 当前 Domain 的默认候选 |
| `dependency` | 仅当当前模块有显式直接依赖时加入 |
| `conditional` | 仅当版本化 route、operation 或 feature predicate 为真时加入 |
| `historical` | 只用于来源追溯、冲突解释和演进分析 |
| `excluded` | Knowledge Query 和 Context Assembler 均不得返回 |

同一个文件可在 Toolchain 中为 `active`，在 Phase 中为 `excluded`。任何查询结果必须记录实际采用的 Domain 和 visibility decision provenance。

### 3.3 Lifecycle Instance

回答“数据属于哪个可独立寻址的实例”。

| Lifecycle | 复合身份 | 内容 |
| --- | --- | --- |
| `repository-source` | repository + source snapshot | 根仓源码、ADR、architecture、standards、稳定测试和 Schema |
| `repository-template` | template revision + seeder policy revision | Seeder 实际复制、同步、条件补齐或退役的模板内容 |
| `project-instance` | account + project + workspace generation + project snapshot | 单项目代码、GDD、素材、配置和脱敏项目知识 |
| `run-artifact-view` | account + project + run + attempt + dispatch | 单次执行实际装配的最小上下文和引用 |

不同 Lifecycle 不得共用 baseline、build generation、RAG namespace、current pointer 或 LKG pointer。不同账号或项目也不得共用 Project corpus。

### 3.4 Enforcement Level

回答“当前实际隔离强度是什么”。

| Level | 名称 | 能保证 | 不能保证 |
| --- | --- | --- | --- |
| `E0` | `unscoped` | 无本专项 Scope 约束 | 检索或访问隔离 |
| `E1` | `retrieval-scoped` | Query 候选受 Domain、Visibility、Lifecycle 和 snapshot 限制 | Agent 不能直接读取其他路径 |
| `E2` | `context-bound` | 父进程按签名 Manifest 装配初始上下文并在共享入口执行 Scope Gate | 子进程不能用绝对路径读取其他文件 |
| `E3` | `filesystem-enforced` | OS/worker 级文件系统、进程、secret 和网络边界 | 不属于本计划 |

本计划的生产终点是 E2。E3 必须在独立 Phase C Runner Isolation Closure 计划中完成。

## 4. 四个知识域与依赖闭包

### 4.1 Domain 定义

| Domain | 包含 | 可显式依赖 | 默认禁止 |
| --- | --- | --- | --- |
| Toolchain | VDD、Quick Dev、Bootstrap Review、Repository Maintenance、BMAD、`workflow.md`、Taskmaster、Chapter 3-7、overlay generator、工具链评估和维护脚本 | Phase 源码与契约；Workspace 共享 Godot kernel | 真实用户项目、账号级运行证据、未审核 Marketplace 包 |
| Phase | `PhaseA.Platform/**`、`PhaseA.Platform.Tests/**`、runtime/Caddy、账号、管理、审计、GDD、prototype、game type、Hosted routes、LLM/Codex 平台入口、Phase ADR/architecture/standards | 共享 Godot kernel；经过枚举的 Toolchain 脚本、Skill、validator；明确标为 historical 的 Phase 设计来源 | `workflow.md`、Taskmaster、Chapter 3-7、BMAD 规划输出和普通 overlay 流程作为默认候选 |
| Workspace | 共享游戏模板、Godot/C# kernel、项目实例代码、GDD、素材、project metadata、session、ledger、route state、受允许 Skill | Phase 公开 API、route/capability contract；审核后 Marketplace package | Phase 管理实现、其他账号项目、未经服务端允许的根仓 Toolchain 工作流 |
| Marketplace | UGC Skill、CLI、素材、模板、版本、许可、来源、capability、评估、bad case、发布状态 | Phase capability/安全/审核合同；Workspace package contract | 未注册 hash 获得指令权威、读取账号私有内容 |

### 4.2 依赖闭包算法

候选域闭包必须按以下顺序计算：

```text
primary_domain
-> server profile 的 allowed_dependency_domains
-> module 声明的 direct_dependencies
-> per-domain visibility 和 predicate
```

硬规则：

- 同域依赖可递归，但必须检测环并记录完整路径。
- 跨域默认只允许一跳。
- 第二次跨域必须由服务端 policy 以精确 source/module 和 operation 显式允许。
- 不自动做无限 transitive traversal。
- `historical` 不参与默认闭包。
- `excluded` 在任何闭包中都不可返回。
- `conditional` predicate 的 ID、revision、输入和结果必须进入 query evidence。
- 未知 Domain、visibility、predicate、revision 或依赖节点一律 fail closed。

## 5. 组件边界与数据流

本专项只引入四个职责清晰的组件。

### 5.1 Repository Source Catalog

Source Catalog 从固定 source snapshot 枚举来源，记录 canonical path、内容 hash、Domain visibility、Lifecycle、trust label、module、relation 和 provenance。它不生成模型指令，也不改变上位权威。

### 5.2 Projection 与 Knowledge Query

Projection 是按 Domain 和 Lifecycle 构建的 derived cache。Query 只返回候选 source ref、section/symbol、ranking evidence、hash 和 provenance。Agent 或父进程在使用前必须从相同 snapshot 读取并重验原始来源。

The canonical consumption surface is one deterministic Knowledge Locator core with a CLI-first adapter. Programmatic callers use versioned JSON on stdin and receive versioned JSON on stdout; diagnostics use stderr and stable exit/failure codes. Other CLI, Skill, Tool, MCP, and later Phase/API adapters must reuse this core instead of reimplementing retrieval or ranking.

The Locator returns a routing decision, not a synthesized fact answer: normalized keywords, matched modules, repository-relative paths, heading or symbol anchors, line ranges, source hashes, ranking breakdown, snapshot identity, confidence status, and an ordered read set. A caller must reread the recommended sources and verify their hashes before using their contents.

### 5.3 Context Assembler

Context Assembler 接收服务端有效权限、当前 route 合同、固定 snapshots、Query 结果和数字预算，生成 `context-assembly.v1`、allowed-read artifact manifest 和 Hosted Context Manifest。它不能自行放宽 route、Skill、账号或项目权限。

### 5.4 Execution Boundary 与 Scope Gate

Scope Gate 位于父进程和三类共享 LLM/Codex 入口处。它校验签名、身份、snapshot、现有 Hosted 合同、预算、read/write 集、nonce 和 gate mode，再决定 dispatch。E2 Gate 是上下文和调度边界，不是 OS sandbox。

```text
authority sources
  -> deterministic snapshot
  -> source catalog
  -> domain/lifecycle projection
  -> scoped query
  -> context assembler

server registries + existing hosted route contracts + budget policy
  -> signed run-bound manifest
  -> pre-dispatch scope gate
  -> shared LLM/Codex entrypoint
  -> append-only dispatch/readback evidence
```

任何组件不得绕过上一层的 snapshot 或 policy revision，也不得用 derived cache 的自声明 hash替代原始来源重算。

## 6. 权威、内容信任与权限交集

### 6.1 Projection 永远不是权威

所有 Projection 根对象必须包含：

```json
{
  "authority_class": "derived_cache",
  "instruction_authority": false,
  "may_override_source": false
}
```

Projection 可返回候选模块、候选路径、检索词、摘要、SHA 和 provenance，不得覆盖原始 ADR、代码、标准、route state 或 live blocker。

### 6.2 内容信任分类

```text
trusted_system_instruction
trusted_service_policy
trusted_route_instruction
trusted_published_skill_instruction
trusted_contract
derived_cache
untrusted_project_data
untrusted_source_comment
untrusted_marketplace_content
untrusted_historical_content
```

只有以下四类内容可改变角色、Domain、工具权限、允许读写路径、网络/沙箱策略、输出目标或执行模式：

```text
trusted_system_instruction
trusted_service_policy
trusted_route_instruction
trusted_published_skill_instruction
```

`trusted_contract` 可被宿主验证器机械执行，但合同正文作为模型上下文时不能自行扩权。Projection 摘要、日志、模型输出、源码注释、用户 GDD、`project.md`、项目局部 Skill、未审核 Marketplace 内容和历史文件均为数据，不具有控制面指令权威。

### 6.3 不可信业务数据仍可决定业务输出

不可信不等于忽略。项目 GDD 可以在已授权操作范围内决定游戏类型、玩法、角色、地图、UI、模块需求和素材风格，但不能决定：

- Agent 系统角色或 Domain。
- 账号、项目、workspace、run 身份。
- 工具、网络、secret、sandbox 或读写路径。
- 输出文件目标。
- 是否跳过测试、source scan、Scope Gate 或 acceptance。

信任标签必须由以下组合确定，不得只看文件名：

```text
source origin
+ lifecycle instance
+ canonical path
+ source snapshot
+ registry revision/hash
+ package publication status
```

Seeder 复制到项目内的 `AGENTS.md` 不自动继承根仓权威。项目内同名文件、修改后的 Skill 或旧 overlay 不能提升自身信任等级。

### 6.4 服务端 Registry 和有效权限

最大权限的唯一来源位于 workspace 外，由 Phase 服务控制：

```text
Route Policy Registry
Published Skill Registry
Account Capability Policy
Global Scope Policy
```

有效权限必须是以下交集：

```text
effective_permissions
= server route ceiling
  ∩ published skill ceiling
  ∩ account policy
  ∩ project restrictions
  ∩ requested operation
```

项目配置只能缩权，例如 `read_only`、`disable_network`、`deny_asset_generation`、`restrict_modules` 和 `restrict_output_paths`。项目不得声明 `allow_host_root`、`allow_other_project`、`enable_admin_api`、`expand_network`、`expand_write_paths` 或 `override_route_scope`。

未知字段、未知 capability、未知或撤销的 revision、无法解析的 profile 和空交集均 fail closed。客户端输入不能选择更高 Enforcement、Gate mode 或权限 ceiling。

### 6.5 Marketplace Skill 晋级

Marketplace Skill 只有同时满足以下条件，才可成为 `trusted_published_skill_instruction`：

- 精确 package hash 已审核。
- package revision 已注册到 Published Skill Registry。
- capability manifest 已通过 Schema 和组合验证。
- capability 不超过 Domain 和 permission ceiling。
- 当前 dispatch 绑定已注册 hash，而不是项目内同名文件。

项目局部修改会使其自动降级为 `untrusted_project_data`。

## 7. Lifecycle 保存、缓存与恢复合同

### 7.1 Git 跟踪的稳定资产

实施后只跟踪可评审、可复现的稳定资产：

```text
knowledge/schemas/**
knowledge/policies/**
knowledge/fixtures/**
knowledge/evals/**
scripts/python/knowledge/**
对应测试
Accepted ADR、正式计划和标准更新
```

动态 Projection build、临时索引、embedding、锁、nonce、签名密钥、raw prompt 和用户数据不得进入 Git。

### 7.2 Repository 和 Template 动态缓存

仓库/模板本地动态缓存必须位于仓库外：

```text
JIMUYUN_KNOWLEDGE_CACHE_ROOT
默认值: %LOCALAPPDATA%\JiMuYun\knowledge

repository/builds/<build-id>/
repository/current.json
repository/last-known-good.json
templates/<template-revision>/builds/<build-id>/
embeddings/<embedding-revision>/
locks/
```

禁止使用根仓内 `.cache/knowledge`。启动时必须解析 final path、junction 和 reparse point，并拒绝 cache root 位于 repository root、任何 Hosted workspace root、任何 Project workspace 或子进程允许写入根之内。大小写折叠后的重叠也必须拒绝。

### 7.3 Project Instance Projection

Project Projection 默认保存在 workspace 外、由宿主拥有的独立根：

```text
PHASEA_KNOWLEDGE_CACHE_ROOT
默认值: %LOCALAPPDATA%\JiMuYun\phasea-knowledge

projects/<account-key>/<project-key>/<workspace-generation>/builds/<build-id>/
projects/<account-key>/<project-key>/<workspace-generation>/current.json
projects/<account-key>/<project-key>/<workspace-generation>/last-known-good.json
```

路径 segment 必须是经过固定编码的 opaque key，不能直接包含用户可控路径、显示名或分隔符。每个 build 绑定 `account_id`、`project_id`、`workspace_id`、`workspace_generation`、`template_revision` 和 `project_snapshot_id`。

默认不得在项目内创建 `meta/knowledge/**`。如果未来兼容调用方必须读取项目内指针，只允许保存脱敏的逻辑 build ID；在创建前必须把 `meta/knowledge/**` 同时加入 Seeder、Source Catalog、Project snapshot 和 Context Assembler 的硬排除规则，并提供无自递归 fixture。workspace 指针永远不是可信 binding。

服务端数据库或 host-owned runtime state 保存当前可信 build ID、snapshot binding、account/project binding、validation status 和 Manifest binding。子进程修改 workspace 内兼容指针不能改变这些权威记录。

### 7.4 Run Artifact View 和 canonical dispatch 状态

Canonical Manifest、signature metadata、nonce 状态、gate result 和 revocation 状态必须位于服务端数据库或子进程允许写入范围之外的 host-owned runtime state。签名密钥只存在于 host secret store。

浏览器/API 只返回脱敏摘要、逻辑 ID、状态、稳定错误码和允许公开的 evidence ref。响应不得泄漏 prompt、secret、host absolute path、其他项目标识或签名材料，并使用 `Cache-Control: no-store`。

### 7.5 Evidence、保留和 LKG

验证、迁移和失败证据只追加写入：

```text
logs/knowledge-context/<YYYY-MM-DD>/<run-id>/
```

失败 build 不得覆盖 current 或 LKG。current pointer 只在完整验证后原子切换；前一个通过验证的 generation 成为 LKG。任何被 Manifest、run、evaluation 或审计证据引用的 generation 不得清理。其他 generation 只能按版本化 retention policy 清理，并保留清理清单；历史失败证据不能被重写成成功。

### 7.6 Knowledge maintenance Skill

The repository-local `maintain-knowledge-base` Skill is a thin adapter over deterministic snapshot, catalog, projection, validation, and logging tools. Its `SKILL.md` owns triggering and operator guidance; it must not embed a second indexer, Git comparator, ranking engine, or source mutation path.

The Skill has two modes:

- `existing-only`: no consumer target is supplied. It traverses only source entries already registered in the current knowledge snapshot, compares them with one pinned local `refs/heads/main` commit, and may update, mark missing, or retain those entries. It must not discover or add repository content absent from the registered source set.
- `targeted`: an explicit repository-relative consumer target is supplied, such as an execution-plan directory, CLI, Skill, Tool, MCP package, or documentation directory. The target bounds discovery. Main-backed entries may be added or updated; target-only worktree content is recorded as `provisional`/`candidate` and cannot be promoted to repository fact.

The run pins the local `refs/heads/main` object ID at start and performs no implicit fetch, checkout, merge, or branch mutation. Dirty worktree bytes are never repository fact authority. The Skill writes only derived projections, indices, LKG pointers after validation, and append-only maintenance evidence. Source code, consumer objects, Accepted ADRs, runtime state, live metadata, and Hosted workspaces are read-only unless a separate explicitly authorized change request exists.

## 8. 确定性 Snapshot、路径和构建控制面

### 8.1 Snapshot 模式

支持两种显式模式：

- `clean-commit`：用于 release 和受控 Hosted 基线，输入绑定 commit/tree。
- `working-tree`：用于本地实验 E1，包含 eligible tracked、modified、deleted、index 和 eligible untracked 状态。

不得用 `git diff` 文本作为 snapshot 身份，也不得依赖 Git rename detection。rename 固定表示旧路径 deleted 和新路径 added/untracked。

### 8.2 Canonical File State Manifest

每个纳入文件至少记录：

```json
{
  "canonical_path_key": "phasea.platform/runs/example.cs",
  "display_path": "PhaseA.Platform/Runs/Example.cs",
  "file_mode": "100644",
  "state": "modified",
  "head_blob_oid": "...",
  "index_blob_oid": "...",
  "worktree_raw_content_sha256": "...",
  "canonical_text_sha256": "...",
  "size_bytes": 1234
}
```

删除项的 worktree hash 为 `null`；未跟踪项的 Git OID 为 `null`。原始字节 SHA-256 是 snapshot 完整性依据；规范化文本 hash 只服务于检索、fingerprint 和跨换行比较，不能替代 raw hash。

Snapshot JSON 必须使用固定 key、固定枚举、UTF-8、无 BOM、无时间戳输入，并按 `canonical_path_key` 排序。Snapshot 元数据包括：

```json
{
  "snapshot_mode": "working-tree",
  "head_commit_oid": "...",
  "head_tree_oid": "...",
  "scanner_revision": "...",
  "exclusion_policy_revision": "...",
  "file_state_manifest_sha256": "...",
  "source_snapshot_id": "..."
}
```

```text
source_snapshot_id = sha256(canonical file-state manifest bytes)
```

### 8.3 Windows 路径规则

- 只保存来源根相对路径，分隔符统一为 `/`。
- Unicode 使用 NFC。
- `canonical_path_key` 使用固定 Windows case folding，保留原始大小写为 `display_path`。
- 大小写碰撞、`..`、绝对路径、UNC/device path、alternate data stream 和路径根逃逸一律拒绝。
- reparse point、symlink 和 junction 单独记录，默认不跟随；需要跟随时必须由服务端 policy 精确允许并验证 final target 仍在同一来源根。
- source root 或 cache root 自身为未授权 reparse point 时 fail closed。

### 8.4 扫描排除

Repository Source Catalog 默认只纳入 Git 跟踪源码、ADR、architecture、standards、Schema、稳定测试和受控 Skill 定义。默认排除：

```text
logs/**
bin/**
obj/**
TestResults/**
live runtime DB
Hosted workspaces
dynamic knowledge cache
meta/knowledge/**
raw prompt
secret/token material
provider response dumps
```

任何生成目录必须通过精确 canonical path exclusion 自排除，并用 `generated-directory-recursion` fixture 验证。

### 8.5 原子构建、并发锁与 LKG

- 在与目标 build root 同一文件系统的 staging generation 构建。
- staging 完成 Schema、组合、hash、evaluation 和污染检查后，原子 rename 为 immutable build。
- `current.json` 和 `last-known-good.json` 使用临时文件、flush 和原子替换。
- 锁键至少包含 Lifecycle identity、Domain、source snapshot 和 policy revision。
- 锁记录 owner PID、process creation identity、token、acquired time 和 generation；只有确认 owner 已失效且超过 policy TTL 才可回收。
- 并发相同 build 必须复用已验证结果或由单一 owner 构建，不得互相覆盖。
- 失败保留 sidecar evidence，不提升 pointer；恢复优先回到 LKG。

## 9. Schema、Fixture 和组合验证器

### 9.1 版本化 Schema

K2 至少物化以下 JSON Schema，并固定 JSON Schema draft、`$id`、版本和 `additionalProperties: false`：

```text
domain-scope.v1.schema.json
per-domain-visibility.v1.schema.json
source-entry.v1.schema.json
source-catalog.v1.schema.json
source-snapshot.v1.schema.json
lifecycle-instance.v1.schema.json
relation-graph.v1.schema.json
module-index.v1.schema.json
scope-profile.v1.schema.json
route-policy.v1.schema.json
tokenizer-policy.v1.schema.json
ranking-policy.v1.schema.json
context-budget-policy.v1.schema.json
artifact-entry.v1.schema.json
allowed-read-artifact-manifest.v1.schema.json
hosted-context-manifest.v1.schema.json
hosted-route-contract-aggregate.v1.schema.json
context-assembly.v1.schema.json
scope-gate-result.v1.schema.json
build-manifest.v1.schema.json
query-result.v1.schema.json
knowledge-locator-request.v1.schema.json
knowledge-locator-result.v1.schema.json
knowledge-maintenance-request.v1.schema.json
knowledge-maintenance-result.v1.schema.json
evaluation-case.v1.schema.json
evaluation-result.v1.schema.json
hosted-caller-inventory.v1.schema.json
direct-llm-invocation-violations.v1.schema.json
runtime-evidence-view.v1.schema.json
e2-readiness.v1.schema.json
```

### 9.2 正向 Fixture

```text
minimal-valid
full-repository-source
full-template
full-project-instance
full-run-artifact-view
read-only-route
workspace-write-route
published-skill
project-restricted-skill
prompt-producing-route-contract-composition
non-prompt-source-boundary-not-applicable
valid-key-rotation-overlap
valid-optional-budget-omissions
valid-llm-intent-with-adapter-owned-envelope
valid-consumer-ref-location-result
valid-existing-only-maintenance
valid-targeted-provisional-candidate
```

### 9.3 负向 Fixture

```text
authority-inversion
project-profile-expands-permission
cross-account-source
cross-project-source
stale-project-snapshot
manifest-write-overlap
unknown-policy-revision
unknown-capability
unknown-gate-mode
modified-signed-payload
modified-signature-metadata
replayed-nonce
expired-or-revoked-manifest
cross-run-dispatch
untrusted-content-promoted-to-instruction
historical-source-used-as-current
generated-directory-recursion
cache-root-under-repository
cache-root-under-workspace
windows-path-case-collision
reparse-point-escape
recovery-order-mismatch
forbidden-source-scan-mismatch
source-boundary-exemption-omitted
database-binding-mismatch
old-route-state-overrides-live-blocker
required-artifact-budget-omission
inventory-source-snapshot-drift
manual-migration-status-forgery
observe-rollback-retains-e2-ready
llm-controls-trusted-envelope
locator-result-claims-generated-answer
existing-only-discovers-new-entry
worktree-entry-promoted-to-repository-fact
maintenance-mutates-consumer-source
```

### 9.4 组合验证顺序

单个 JSON 通过 Schema 不代表组合合同有效。纯验证按以下顺序执行：

```text
schema validation
-> canonical JSON and signature verification
-> path normalization and root containment
-> lifecycle identity validation
-> account/project/workspace/run binding
-> policy/profile revision resolution
-> effective permission intersection
-> source and projection freshness
-> trust-label validation
-> existing Hosted route contract composition
-> read/write/output overlap validation
-> provenance closure
-> DB/evidence binding
-> context budget and omission validation
-> inventory/source-snapshot consistency
-> Locator trusted-envelope ownership and result-anchor integrity
-> maintenance mode, pinned-main, discovery, source-mutation and append-only-log checks
-> evaluation and readiness predicates
```

真正 dispatch 必须在数据库事务内再次检查 expiry、revocation、snapshot current、gate mode 和 nonce，然后原子 consume nonce。纯验证不能提前消耗 nonce；一旦 dispatch transaction 成功，即使子进程启动失败也不得复用，retry 必须创建新 attempt、dispatch 和 Manifest。

## 10. 确定性检索、Tokenizer、Ranking 与 Evaluation

### 10.1 候选枚举

第一版不依赖 embedding。候选集按以下顺序过滤：

```text
lifecycle instance
-> primary domain
-> per-domain visibility
-> explicit dependency closure
-> source freshness
-> trust and policy eligibility
```

Query 输出只能引用固定 snapshot 内的来源，并携带 source hash、module、visibility reason、dependency path 和 ranking breakdown。

### 10.2 Tokenizer `jimuyun.hybrid-zh-code.v1`

查询和文档必须使用同一 tokenizer revision。

Unicode 规则：

- 严格 UTF-8、Unicode NFC。
- 拉丁字符使用 invariant lowercase。
- 保留 token 到原始文本的 offset 映射。
- 不依赖操作系统 locale。

连续 Han 字符串生成：

- 完整连续短语。
- 单字符 token。
- 重叠双字符 token。
- 重叠三字符 token；v1 的 Han n-gram 上限固定为 3。

v1 不使用动态词典或在线词库。代码在 camelCase、PascalCase、snake_case、kebab-case、dot path、slash path 和 `namespace::symbol` 边界拆分，同时保留原始完整标识符、规范化完整标识符和各组成部分。

ADR ID、route path、error code、contract ID、Schema version、CLI option、environment variable、SHA/hash 和 project/run ID 作为不可再分的高权重 token 保留。

Build manifest 必须记录：

```text
tokenizer_id
tokenizer_revision
normalization_revision
ranking_revision
dependency_lock_hash
```

任何依赖升级导致 token 或排名变化时必须创建新 build generation，不得静默覆盖。

### 10.3 初始确定性 Ranking

| 匹配 | 分值 |
| --- | ---: |
| 精确 ADR、route、symbol、error code 或 contract ID | 100 |
| 精确路径或文件名 | 90 |
| 精确规范化短语 | 70 |
| 模块标题或公开符号 | 50 |
| BM25/token score | 0-40 |
| 显式 relation graph 一跳依赖 | 10 |

Tie-break 固定为：

1. 直接原始来源优于 generated cache。
2. 当前来源优于 historical。
3. graph distance 更短者优先。
4. `canonical_path_key` 字典序。

Embedding 未来只能作为独立版本化的候选补充，不能改变 v1 确定性基线的可重放结果。


`ranking-policy.v1` 必须固定 BM25 实现 revision、`k1`、`b`、字段权重、IDF 公式、corpus 统计边界、0-40 映射、数值精度和舍入规则。K2 fixture 必须给出完整 token、子分值、总分和 tie-break vectors；这些参数未物化前不得声称 same-snapshot ranking deterministic。

### 10.4 Evaluation Case 与 Glob 语义

所有 pattern 在固定 source snapshot 上展开。路径以 repository-relative `/` 表示，按 v1 Windows canonical key 比较；pattern 锚定来源根。`*` 只匹配单 segment 内字符，`?` 匹配单字符，`**` 匹配零个或多个完整 segment；v1 禁止未定义的 character class 和 brace expansion。matcher revision 和展开结果必须进入 evidence。

Required source 使用分组语义：

```json
{
  "required_source_groups": [
    {
      "group_id": "phase-auth-code",
      "patterns": ["PhaseA.Platform/Security/**"],
      "minimum_hits": 1,
      "required_top_k": 5
    }
  ]
}
```

每个 group 都必须满足；group 内 pattern 的并集构成候选集合，至少命中 `minimum_hits` 个不同来源，并在声明的 top-k 内。只有明确要求 glob 展开的所有文件都出现时才使用 `required_all_matches`。pattern 展开为空、`minimum_hits` 非法或来源不在 snapshot 内均 fail closed。

`forbidden_patterns` 中任意 pattern 匹配任意返回项即失败。Precision 和 recall 的相关性全集不能从运行结果临时推断；每个 case 必须声明 `relevant_source_groups`，并在评估开始时冻结展开集合。

```text
precision@k = top-k 中属于冻结 relevant set 的结果数 / k
recall@k = top-k 中命中的冻结 relevant set 数 / relevant set 总数
```

空 relevant set 是无效 case，不能用零或一代替分母。Evaluation result 必须记录 snapshot ID、pattern expansion、relevant set、ranking revision、tokenizer revision、top-k 完整顺序和每次 tie-break。

### 10.5 初始阻断阈值

关键 Phase 查询：

```text
forbidden@10 = 0
cross-domain unexpected@10 = 0
stale result count = 0
required anchor 必须进入 top 5
critical required source recall@20 = 1.0
```

普通查询集：

```text
macro precision@10 >= 0.80
macro recall@20 >= 0.90
MRR >= 0.70
same snapshot ranking drift = 0
```

隔离评估：

```text
cross-account result count = 0
cross-project result count = 0
```

阈值只能通过版本化 evaluation policy 和对应 ADR/决策更新。

### 10.6 Standard Knowledge Locator consumption contract

The v1 query path is deterministic and retrieval-only:

```text
exact path / identifier / symbol
-> scoped rg lexical recall
-> tokenizer and BM25 ranking
-> relation-graph expansion
-> deterministic tie-break
```

The first adapter is a repository-local CLI. The full core-boundary request is versioned JSON and separates semantic intent from trusted execution fields. Human-friendly flags may be accepted only by a thin adapter that constructs the same request Schema.

Required intent fields include `query`, caller identity/type, intent source, and an optional repository-relative `consumer_ref`. Required trusted fields include the pinned authority ref and commit, knowledge snapshot, allowed Domains, permission source, result/byte budget, and trace identity. Caller-supplied keywords, preferred modules, and primary-domain values are hints and never expand the trusted envelope.

Results use `matched`, `insufficient_match`, or `blocked`. A matched or low-confidence candidate carries module, repository-relative path, heading/symbol anchor, line range, source SHA-256, score breakdown, provenance, snapshot identity, and `revalidation_required=true`. The result contains no free-form generated fact answer. Low confidence returns `insufficient_match` plus bounded candidates; it does not infer a fact.

### 10.7 Caller LLM boundary

A caller LLM may formulate the natural-language query and optional untrusted hints. It cannot supply or override account/permission scope, allowed Domains, authority commit, snapshot, path allowlist, budget ceilings, confidence policy, gate mode, or protected-data access. When a consumer object is available, the caller passes `consumer_ref`; the Locator reads the permitted object and extracts terms deterministically instead of relying on an LLM summary.

Deterministic classification is the default. Only unresolved semantic ambiguity may invoke the centralized K5 ambiguity classifier, and that classifier delegates through `scripts/sc/_llm_backend.py::run_llm_exec`. Its Schema-constrained result cannot widen authority, bypass a failed deterministic gate, or become a fact answer. A caller-owned LLM must not provide a competing ambiguity path.

## 11. Phase E1 与 E2 里程碑

### 11.1 Phase E1 Projection

K6 产出完整的实验性 Phase Projection：

```yaml
status: experimental
primary_domain: phase
lifecycle: repository-source
enforcement_level: E1
authority_class: derived_cache
```

至少包含：

```text
phase/index
phase/modules
phase/source-catalog
phase/relation-graph
phase/query-index
phase/baseline
phase/evaluation-result
```

E1 可用于本地 Knowledge Query、候选模块选择、受 Scope 约束的 `rg`、污染率评估和生成 source refs。E1 不证明 Hosted route 已受上下文控制、Agent 无法读取排除路径、项目实例已实现 OS 隔离或生产 Scope Gate 已完成。

### 11.2 Phase E2 Release

K13 只有在稳定 E1 与以下能力组合后才能发布 E2：

- Repository Template Projection。
- Project Instance Projection。
- Project Recovery Projection。
- 父进程 Context Assembler。
- 服务端 Scope Policy Registry 和权限交集。
- Hosted Context Manifest、签名、防重放和 DB binding。
- 三类共享入口的 server-controlled Scope Gate。
- account/project/workspace/snapshot/run/attempt/dispatch binding。
- Context budget 和 omission evidence。
- 可重建 caller inventory、零违规 bypass 和静态防回归 guard。

K14 不再负责创建 Phase Projection，只补齐其他 Domain 和持续维护能力。

## 12. 三类 Hosted 调用 Inventory

### 12.1 必须生成的文件

每次迁移评估都从固定 source snapshot 机械生成：

```text
codex-hosted-callers.v1.json
llm-route-engine-callers.v1.json
python-llm-backend-callers.v1.json
direct-llm-invocation-violations.v1.json
```

三类入口分别是：

1. `.NET` executable Codex：`CodexHostedProcessCommandFactory`。
2. `.NET` structured/read-only：`ILlmRouteEngine` / `LlmRouteEngine`。
3. Python：`scripts/sc/_llm_backend.py::run_llm_exec` 或只委托给它的薄包装。

### 12.2 Inventory 合同

根对象记录 inventory revision、scanner revision、source snapshot ID、生成器 hash 和完整性摘要。每条 caller 至少记录：

```json
{
  "caller_path": "...",
  "caller_symbol": "...",
  "callsite_fingerprint": "...",
  "entrypoint_family": "codex-hosted|llm-route-engine|python-backend",
  "hosted_reachability": "hosted-route|phase-internal",
  "hosted_reachability_evidence": [],
  "identity_mode": "project-bound|account-bound|platform-bound",
  "primary_domain": "...",
  "allowed_dependency_domains": [],
  "lifecycle": "...",
  "enforcement_level": "E0|E1|E2",
  "route_id": "...",
  "operation": "...",
  "read_write_mode": "read-only|workspace-write",
  "account_binding": "...",
  "project_binding": "...",
  "gate_mode": "legacy|observe|enforce",
  "required_tests": [],
  "gate_evidence_refs": [],
  "migration_status": "unassessed|observed|migrated|blocked"
}
```

`migration_status` 不能手填。它必须由 callsite fingerprint、对应 route policy、Scope Gate evidence、required test evidence 和当前 source snapshot 机械计算。源码或 policy 漂移会自动把状态降为 `unassessed` 或 `blocked`。

扫描器先枚举三类共享入口的全部生产候选，再用服务端 route/script registry 和可重放调用图证明 Hosted reachability。`hosted-route` 与 `phase-internal` 候选进入三份 caller inventory；纯 Toolchain 候选进入同文件的 `excluded_candidates`，并携带精确 path/symbol/hash 和不可从 Hosted route 到达的证据。`unknown` reachability 一律阻断 inventory 完整性，不得作为排除项。K13 的“全部 migrated”指三份 inventory 的完整 `callers` 集，而不是未经证明的人工子集。

### 12.3 Direct invocation guard

违规扫描覆盖：

- 直接构造 `codex exec`。
- 直接调用文本/推理 provider SDK。
- 绕过 `LlmRouteEngine`。
- 绕过 `run_llm_exec`。
- 未登记的 subprocess/model 调用。

非 LLM 的图像 provider、测试替身或迁移 adapter 不能靠源码注释自行豁免；它们必须命中服务端拥有、绑定精确 path/symbol/hash/capability 的版本化 exclusion registry，并在输出中单独列为 `approved_non_llm_or_test_exclusion`。所有未命中排除合同的项进入 violation 集。

K13 的闭合条件不是调用数等于某个常量，而是：

```text
三份 caller inventory 全部 migration_status=migrated
direct invocation violations=0
静态 guard 阻止新增 bypass
inventory source_snapshot_id 等于 release snapshot
所有 evidence hash 和测试仍为 current
```

共享入口变更至少运行 `CodexHostedProcessCommandFactoryTests`、`LlmRouteEngineTests`、`scripts/sc/tests/test_llm_backend.py` 和每个 caller 的 route-specific tests。

## 13. Hosted Context Manifest 与现有 Phase 合同组合

### 13.1 Manifest 的职责边界

新 Manifest 不是新的 route recovery、prompt-security 或 acceptance 权威。它只把现有合同的当前结果、Project snapshot、Context assembly 和一次 dispatch 绑定在一起。

当前 `HostedRouteRecoveryContract.SourceOrder` 的八项顺序是：

1. parsed game-type route profile。
2. selected route skill prompt block。
3. `meta/project-execution-guide.md`。
4. `routes/prototype-contract/latest.json`。
5. current route latest state。
6. current goal/step/session state when applicable。
7. repair ledger and failing acceptance/Godot diagnostic evidence when applicable。
8. latest live platform acceptance blocker。

上述列表是当前实现映射说明。运行时必须解析并验证 `hosted-route-recovery-order.v1` 的现行代码/标准合同，不得在 Manifest 组件中复制出可独立演进的第二套顺序。

Manifest 必须组合：

- `hosted-route-recovery-order.v1`。
- `hosted-route-forbidden-source-scan.v1` 对 exact in-memory execution prompt 的结果。
- `execution_prompt_hash` 和脱敏保存物的 `persisted_prompt_hash`。
- 数据库 `project_route_prompt_evidence_bindings`。
- same-project succeeded run binding。
- 当前结构化来源的 authoritative source-hash recomputation。
- latest live acceptance blocker，其优先级高于旧 assistant summary、route state 和 repair ledger memory。
- 非 prompt route 的显式 `source_boundary_not_applicable` 对象。

组合验证器不得重新定义允许来源、信任 Manifest 内自声明 source hash、让旧 route state 覆盖 live blocker，或把缺少 `source_boundary_not_applicable` 当作默认豁免。

### 13.2 三段式结构

```json
{
  "signed_payload": {},
  "signature": {},
  "validation_state": {}
}
```

HMAC 只覆盖 canonical `signed_payload`。`signature`、`validation_state` 和 HMAC 值自身不进入签名输入。

### 13.3 完整 signed payload

下列字段均属于签名覆盖，字段不得移到未签名的 readback sidecar：

```json
{
  "schema_version": "jimuyun.hosted-context-manifest.v1",
  "manifest_id": "...",
  "identity_mode": "project-bound",
  "service_principal_id": null,
  "primary_domain": "workspace",
  "allowed_dependency_domains": ["phase"],
  "visibility_policy_revision": "...",
  "lifecycle": "run-artifact-view",
  "enforcement_level": "E2",
  "gate_mode": "enforce",
  "route_id": "...",
  "skill_id": null,
  "operation": "...",
  "account_id": "...",
  "project_id": "...",
  "workspace_id": "...",
  "workspace_generation": "...",
  "run_id": "...",
  "attempt_id": "...",
  "dispatch_id": "...",
  "global_policy_revision": "...",
  "route_policy_revision": "...",
  "skill_policy_revision": null,
  "account_policy_revision": "...",
  "project_restrictions_sha256": "...",
  "scope_profile_revision": "...",
  "effective_capabilities": [],
  "repository_snapshot_id": "...",
  "template_snapshot_id": "...",
  "project_snapshot_id": "...",
  "allowed_read_artifact_manifest_ref": "...",
  "allowed_read_artifact_manifest_sha256": "...",
  "allowed_write_paths": [],
  "output_targets": [],
  "context_assembly_result_ref": "...",
  "context_assembly_result_sha256": "...",
  "context_budget_profile_revision": "...",
  "sandbox_policy": {
    "revision": "...",
    "mode": "read-only|workspace-write"
  },
  "network_policy": {
    "revision": "...",
    "mode": "disabled|provider-only|allowlisted",
    "allowlist_sha256": "..."
  },
  "tool_execution_policy": {
    "revision": "...",
    "allowed_tools": [],
    "command_policy_sha256": "..."
  },
  "hosted_route_contracts": {
    "aggregate_ref": "...",
    "aggregate_sha256": "...",
    "recovery_order": {
      "contract_id": "hosted-route-recovery-order.v1",
      "evidence_ref": "...",
      "evidence_sha256": "..."
    },
    "forbidden_source_scan": {
      "contract_id": "hosted-route-forbidden-source-scan.v1",
      "evidence_ref": "...",
      "evidence_sha256": "...",
      "status": "clean"
    },
    "database_binding": {
      "binding_id": "...",
      "binding_sha256": "..."
    },
    "succeeded_run_binding": {
      "run_id": "...",
      "binding_sha256": "..."
    },
    "live_acceptance": {
      "blocker_ref": "...",
      "blocker_sha256": "...",
      "observed_at_utc": "..."
    },
    "source_boundary_disposition": {
      "mode": "required|not_applicable",
      "evidence_ref": "...",
      "evidence_sha256": "..."
    }
  },
  "execution_prompt_hash": "...",
  "persisted_prompt_hash": "...",
  "issued_at_utc": "...",
  "not_before_utc": "...",
  "expires_at_utc": "...",
  "nonce": "...",
  "max_uses": 1
}
```

数组内容必须按对应 Schema 的 canonical 顺序签入。签名同时绑定 policy revision 和解析后的依赖域、effective capabilities、sandbox、network、allowed tools，防止同一 revision 被错误解析成不同权限。`allowed_read_artifact_manifest_ref` 指向 host-owned immutable artifact set；Gate 必须读取该对象并重算 SHA-256，不能只相信引用或摘要。

Identity 使用 Schema 条件分支，而不是伪造 project ID：

- `project-bound`：account、project、workspace、workspace generation 和 project snapshot 全部必填，`service_principal_id=null`。
- `account-bound`：account 必填，project/workspace/generation/project snapshot 显式为 `null`；allowed-read 集不得包含项目私有 corpus。
- `platform-bound`：`service_principal_id` 必填，tenant/project/workspace 字段显式为 `null`；只能读取 route policy 允许的平台来源。

所有模式都必须有 run、attempt、dispatch、route、operation、policy 和时效绑定。字段即使不适用也必须以签名覆盖的 `null` 出现，禁止因字段缺失产生歧义。`same-project succeeded run`、live blocker 和 source-boundary scan 等合同按现行 route contract 判断 applicability；适用时必须提供当前证据，不适用时必须提供签名覆盖、Schema 有效的显式 disposition。未知 applicability fail closed。

### 13.4 Manifest 生成位置与不变量

- Manifest 由父进程生成，canonical 记录位于服务端 DB 或 host-owned runtime state，并处于子进程允许写入范围之外。
- 子进程只得到只读副本或逻辑 Manifest ID，不能覆盖 Manifest、Scope Profile、Registry、Gate result、nonce、签名或 readiness evidence。
- `allowed_write_paths` 和 `output_targets` 必须是解析 final path 后的最小集合，不得覆盖 host-owned cache、Manifest/Gate/Registry、其他账号/项目、live DB 或历史 evidence。
- allowed-read、allowed-write 和 output set 必须做交叉重叠验证；只有 route policy 明确允许的同项目输入/输出关系可以通过。
- Project-bound run 的 account/project/workspace/generation 必须与 metadata authority 和 current project snapshot 一致。
- Route、Skill、network、sandbox 和 tool 最大权限来自服务端 Registry；项目输入只能缩权。
- Manifest 创建后不能扩权。任何身份、snapshot、policy、budget、合同证据或路径集合变化都必须作废旧 Manifest 并重新生成。
- E2 的 HMAC/DB binding 用于发现并拒绝篡改，不等同于 E3 的文件系统阻止能力。

### 13.5 Canonical JSON 与 HMAC

- 使用 RFC 8785 JSON Canonicalization Scheme（JCS）生成 `signed_payload` 字节。
- 实现库、wrapper revision 和 reference vectors 必须固定在依赖锁与测试中；不得依赖平台默认 JSON property order。
- 时间固定为规范化 RFC 3339 UTC 字符串，Schema 禁止浮点和重复 key。
- 对 JCS UTF-8 字节计算 SHA-256 和 HMAC-SHA-256。
- 签名比较使用 constant-time comparison。
- 至少提供跨 C#/Python 的同 payload 同字节、同 SHA、同 HMAC reference vectors，以及 Unicode、空数组、null 和顺序负向用例。

```json
{
  "algorithm": "HMAC-SHA-256",
  "canonicalization": "RFC8785-JCS",
  "canonicalization_revision": "jimuyun-jcs.v1",
  "key_id": "...",
  "signed_payload_sha256": "...",
  "hmac_base64": "..."
}
```

### 13.6 Runtime validation state

`validation_state` 由服务端运行时和数据库生成，不是签名输入，也不能由客户端或子进程提交：

```json
{
  "revocation_status": "active|revoked|expired|consumed|superseded",
  "nonce_status": "unused|consumed",
  "validated_at_utc": "...",
  "gate_result_id": "..."
}
```

### 13.7 防重放、密钥轮换和持久化

- nonce 在 `key_id` 范围内唯一，`max_uses` 默认为 1。
- dispatch transaction 原子验证并 consume nonce；并发第二次消费必须失败。
- retry 创建新的 attempt ID、dispatch ID、nonce 和 Manifest。
- consumed、expired、revoked、superseded、跨 run、跨 project 或跨 account 的 Manifest 必须拒绝。
- 允许时钟偏差由 server policy 数字化声明并签入 policy revision。
- 签名密钥来自 host secret store，不写项目、Manifest、日志、子进程环境或 Git。
- DB 只保存 key ID、算法、状态和生命周期 metadata，不保存明文 secret。
- current signing key 与 verify-only old key 状态分离；rotation overlap 和显式 revocation 均可恢复。

新增 Manifest、nonce、revocation 和 route gate mode 存储属于 DB/secret 合同变更。必须提供 backward-compatible migration、旧 DB 升级、持久化重启、并发 nonce、rotation、revocation、restore 和 rollback 测试，并按 ADR-0033 更新数据库权威说明。

## 14. Context Assembler 预算与遗漏证据

### 14.1 数字预算

每个 server-owned Route Policy 必须提供有限数字，禁止 `unlimited` 和隐式默认。以下只是 K0/K6 前的初始 proposed profile，校准后通过新 policy revision 生效：

```json
{
  "max_artifact_count": 64,
  "max_total_raw_bytes": 1500000,
  "max_single_artifact_raw_bytes": 256000,
  "max_estimated_tokens": 120000,
  "token_estimator_revision": "jimuyun-context-estimator.v1"
}
```

预算 profile、token estimator revision 和最终使用量必须进入 Context assembly result，并通过其 hash 间接进入签名 payload。

### 14.2 确定性选择层级

Tier 0，不可遗漏的控制面内容：trusted system/service/route instructions、Scope Policy、Manifest contract、安全和输出约束。超预算 fail closed。

Tier 1，不可遗漏的当前运行事实：recovery-order 当前来源、latest live acceptance blocker、当前 route state、source-boundary evidence 和必要 contract。超预算 fail closed。

Tier 2，项目核心业务输入：当前 GDD、project identity、当前目标、明确请求的素材和模块。可按 route policy 分段，但不能静默丢失。

Tier 3，检索候选源码和测试：

```text
required source
-> exact ID/route/symbol match
-> retrieval score descending
-> graph distance ascending
-> canonical path ascending
```

Tier 4，historical、conditional 和补充参考，最先截断。

### 14.3 确定性裁剪

不得任意截断文件中间字节。只允许：

- 使用已验证的结构化 section。
- 按 heading 或 symbol 边界裁剪。
- 保留 source path、section/symbol、raw hash、裁剪范围和父 artifact hash。
- 对相同 snapshot、policy、query 和 budget 产生相同结果。

### 14.4 Omission evidence

```json
{
  "assembly_status": "complete|optional-omissions|blocked",
  "included_artifacts": [],
  "omitted_artifacts": [
    {
      "source_ref": "...",
      "reason": "artifact_count_budget|byte_budget|token_budget",
      "priority_tier": 4,
      "required": false,
      "raw_bytes": 12345,
      "estimated_tokens": 4567
    }
  ],
  "budget_used": {},
  "budget_remaining": {},
  "selection_boundary": {}
}
```

任何 required artifact 被遗漏时，`assembly_status` 必须为 `blocked`，Scope Gate 不得发起模型调用。缺少 omission evidence、估算器 revision 漂移或 included artifact hash 不匹配同样阻断。

## 15. K0 合成环境安全合同

K0 只测量当前污染和访问基线，不修改生产语义。

### 15.1 禁止项

K0 不得读取或修改：

- 真实受保护 workspace。
- `logs/phase-a-innernet/data/**` 和 live metadata DB。
- 真实账号内容。
- 真实 token、provider secret 或 prompt。
- 当前运行中的 Phase service 状态。

### 15.2 合成环境

K0 只使用：

```text
temporary hosted root
disposable SQLite
fake account IDs
fake project IDs
synthetic project workspaces
canary files
fake prompt/evidence
```

Canary 至少包括本项目允许文件、同账号其他项目文件、其他账号项目文件、合成宿主根内的 host-root canary、Toolchain-only 文件、伪造 `AGENTS.md`、提示注入 GDD 和 reparse point/junction 目标。不得在真实仓库根或真实用户目录创建 canary。

### 15.3 K0 证据

只追加写入：

```text
logs/knowledge-context/<YYYY-MM-DD>/<run-id>/
```

必须保存：

```text
test-environment-manifest.json
query-baseline.v1.json
workspace-seed-baseline.v1.json
hosted-access-baseline.v1.json
canary-results.v1.json
summary.v1.json
```

结束后清理经过绝对路径和 root containment 验证的临时 hosted root，保留脱敏、无私有数据的 append-only evidence。清理失败作为 evidence，不扩大删除范围。

## 16. 实施顺序 K0-K14

所有切片按顺序取得 exit evidence。K0-K10 只允许新增专项资产、离线/合成构建和 observe-only 产物，不改变生产 Hosted dispatch 语义。任何保护路径接入从 K11 的授权门开始。

### K0：合成环境当前污染基线

执行第 15 章的隔离基线，测量 Phase 查询污染、Toolchain 召回、Seeder 实际复制内容、`.agents/skills` 同步污染和 canary 可达性。Exit 是完整 K0 evidence、零 live 路径接触和可重放环境清单。

### K1：四维模型、权威和内容信任合同

新增并接受本专项 ADR，固定 Domain、Per-Domain Visibility、Lifecycle、Enforcement、依赖闭包、Projection 非权威、trust label、Registry 和权限交集。Exit 前必须明确关联 ADR-0033、ADR-0035、ADR-0037、ADR-0038；ADR-0040 保持 E3 下游决策，不得借用其 Proposed 状态。

### K2：Schema、Fixture 和组合验证器

物化第 9 章全部 Schema、正负 fixture、JCS/HMAC reference vector 和组合 validator。所有 unknown field/revision/capability 用例 fail closed。没有 Schema 和组合 validator 通过，不得实现 Projection。

### K3：Snapshot、路径、原子构建、锁和 LKG

实现 raw SHA、canonical text SHA、Git OID、working-tree manifest、Windows path policy、外置 cache root validation、原子 staging/pointer、并发锁和 LKG。Exit 包括 same-input same-snapshot、case collision、reparse escape、生成目录自排除、并发构建和失败回滚测试。

### K4：Repository Source Catalog

只扫描稳定根仓来源，建立 source entry、module 和 provenance。live logs、runtime DB、workspace、用户内容、raw prompt、动态 cache 和 `meta/knowledge/**` 必须为零结果。Exit 是绑定 snapshot 的完整 catalog 和污染报告。

### K5：分类、关系图、Tokenizer、Ranking 和 Query CLI

实现确定性 Domain/Visibility 分类、关系图、`jimuyun.hybrid-zh-code.v1`、ranking、query、explain、diff、evaluate、stale detection、leakage regression 和 same-snapshot zero-diff。K5 同时交付一个 canonical Knowledge Locator core、CLI-first JSON adapter、request/result Schema、定位结果 fixtures、稳定 failure codes 和 source-hash revalidation contract。LLM 只可处理明确歧义，结果必须以完整输入和模型/prompt revision cache key 固定，且仍为无指令权威的 derived decision。

K5 ambiguity classification is mechanically delegated to `scripts/sc/_llm_backend.py::run_llm_exec`; direct provider calls and local `codex exec` construction are forbidden.

### K6：Experimental Phase E1 Projection

生成第 11.1 节完整 Phase Projection。Exit 必须满足 forbidden@10、stale、ranking drift、required anchor、critical recall、provenance 和跨域污染阈值。此时只允许声明“Phase Projection E1 ready for local retrieval”。

### K7：Repository Template Projection

以 `ProjectWorkspaceSeeder` 当前真实行为生成 Template Projection，记录 `template_revision`、`seeder_policy_revision`、`managed_paths`、`managed_if_missing_paths` 和 `retired_paths`。不得从根目录结构猜测模板。动态 cache 继续位于根仓外，K7 不需要把 `.cache` 复制或写进项目。K7 还必须记录新增 Git-tracked `knowledge/**` 稳定资产是否会被首次 seed；这些物理副本默认不能因此获得 Workspace 可见性或指令权威。若决定改变 Seeder 的复制/排除行为，该修改转入 K11 的保护路径授权和兼容测试，不得在 K7 隐式实施。

### K8：Project Instance Projection

在 `PHASEA_KNOWLEDGE_CACHE_ROOT` 下按 account/project/workspace generation 独立构建 catalog、baseline、query index、namespace 和 LKG。使用合成/测试项目验证跨账号、跨项目、stale generation、项目配置扩权和 workspace 指针篡改均 fail closed。

### K9：Project Recovery Projection

聚合经过脱敏的 route state、ledger、current blocker、checkpoint、evidence manifest 和 repair state。禁止 raw prompt、token、provider secret、宿主绝对路径和其他账号内容。绑定 ADR-0038 的账号作用域、readback 脱敏和 source-hash recomputation。

### K10：Context Assembler 与 Hosted Context Manifest

基于 Root、Template、Project 和 Recovery snapshots 实现离线/observe-only Assembler、allowed-read artifact manifest、预算、合同聚合和签名验证。K10 不修改生产共享入口或 route dispatch；只用合成数据证明同一输入的 assembly 和签名结果可重放。

### K11：三类 Hosted Entry Inventory 与 BH 依赖闭合

从 current source snapshot 生成三份 caller inventory 和 direct invocation violation inventory，并建立静态 guard。只读 inventory 可先生成；任何 `PhaseA.Platform/Llm/LlmRouteEngine.cs`、`PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs`、`scripts/sc/_llm_backend.py`、Hosted route service、Seeder、DB、Browser 或 runtime 修改前，必须同时满足：

1. `2026-07-11` 计划所依赖的 BH-HANDOFF 已成功，或存在明确的 merge/supersede 决策。
2. 用户对精确保护路径和 write set 给出显式授权。
3. 新 Accepted ADR、兼容模式、rollback 和 caller inventory 已冻结。
4. 不存在两个计划并行修改相同保护路径。

### K12：渐进迁移与 Scope Gate

按 inventory 迁移，不按固定数量迁移：

```text
legacy
-> observe
-> read-only enforce
-> workspace-write enforce
-> legacy bypass zero
```

保留 legacy overload 直到 caller inventory、静态 guard 和 tests 证明 bypass 为零。先迁移 read-only，再迁移 GDD/planning，最后迁移 workspace-write prototype 和 preview adapter。任何未迁移 route 必须显式保持 `legacy` 或 `observe`，不得静默视为 E2。

### K13：Phase E2 Knowledge/Context Release

只有第 18.2 节全部 E2 predicate 从 current evidence 机械计算为真时才能发布。发布说明必须明确 E2 是 context-bound，不是 filesystem-enforced。任何 gate mode 回滚、inventory drift、policy/snapshot 失效或新 direct violation 都自动撤销 E2 readiness。

### K14：其他域与持续维护

补齐 Toolchain、Workspace shared/template 和 Marketplace Projection，加入增量构建、周期性全量重建、bad case 自动回归、LKG、retention 和旧索引兼容导航。创建 repository-local `maintain-knowledge-base` Skill，提供 `existing-only` closed-world refresh 和显式 `targeted` discovery 两种模式，并复用 K3-K5 的 deterministic core。所有运行固定本地 `refs/heads/main` commit，只更新 derived knowledge/cache 与 append-only evidence，不修改消费对象或其他 source。Marketplace 首版可为空 Schema 和审核模型，但不能把未发布内容升级为指令。

E3 始终留在独立 Phase C Runner Isolation Closure 计划。

## 17. K11-K13 兼容迁移与保护路径合同

### 17.1 Server-controlled Gate mode

每个 route + operation 的模式只能由服务端 policy 选择：

```text
legacy | observe | enforce
```

- `legacy`：沿用当前 dispatch，记录明确 legacy bypass；不生成 E2 声明。
- `observe`：完整构建并验证 Manifest，记录 would-block 结果，但仍走兼容 dispatch；不生成 E2 声明。
- `enforce`：dispatch 前必须有 current、有效、未消费 Manifest 和通过的 Scope Gate。

客户端、项目配置、query 参数和 Marketplace Skill 都不能选择或提高 gate mode。新 route 默认 `legacy` 或 `observe`，必须经版本化 server policy 才能进入 `enforce`。

### 17.2 稳定错误合同

Enforce mode 至少使用以下稳定错误码：

```text
context_manifest_required
context_manifest_invalid
context_snapshot_stale
context_policy_mismatch
context_budget_exceeded
```

内部日志可记录更细原因，浏览器/API 只返回 browser-safe 摘要、correlation ID 和允许公开的 evidence ref，并设置 `no-store`。不得把 HMAC、nonce、prompt、secret、host path 或其他项目数据放进错误响应。

### 17.3 兼容与 rollback

- Public 和 browser-consumed API 默认保持 route、字段、状态码和 auth 行为兼容。
- 新 Manifest 字段优先采用服务端内部 envelope；不得要求旧客户端自行构造安全上下文。
- observe 到 enforce 按 route/operation 渐进，先 read-only 后 workspace-write。
- rollback 只能由服务端授权策略执行并产生 append-only evidence。
- 任意生产 route 从 enforce 回到 observe/legacy 时，E2 readiness 立即变为 false，README/状态投影不得继续显示 E2 ready。
- rollback 不得删除失败证据、nonce 消费记录或旧 Manifest binding。

## 18. 验收、测试、证据与评审门槛

### 18.1 Phase E1 Definition of Done

E1 完成必须同时满足：

- Phase Source Catalog、relation graph、query index、baseline 和 evaluation result 均绑定同一 source snapshot。
- Projection 明确标记 `derived_cache`、`instruction_authority=false`。
- Tokenizer、ranking、matcher 和 dependency lock revision 已冻结。
- 第 10.5 节阈值全部通过，same-snapshot ranking drift 为零。
- Root cache 位于仓库外，Seeder smoke 证明动态 cache 不进入新 workspace。
- E1 文档不声称 Hosted Scope Gate、项目访问隔离或 E2。

### 18.2 Phase E2 Definition of Done

E2 readiness 必须由 current evidence 机械计算，不能人工填写。全部条件为真：

- E1 仍在 current release snapshot 上通过。
- Template、Project 和 Recovery snapshots current 且同项目绑定。
- Context Assembler 的 required artifact、预算、裁剪和 omission evidence 通过。
- Manifest 完整签入四维模型、route/operation/identity、policy revisions、snapshots、read/write/output、合同组合、prompt hashes、执行策略、budget result、nonce 和时效。
- JCS/HMAC、DB binding、防重放、rotation、revocation、restart 和并发 nonce tests 通过。
- `hosted-route-recovery-order.v1`、`hosted-route-forbidden-source-scan.v1`、authoritative hash recomputation、same-project succeeded run、DB prompt binding、live blocker 和 `source_boundary_not_applicable` 组合验证通过。
- 三份 caller inventory 在 release snapshot 上全部为 `migrated`。
- Direct invocation violations 为零，静态 guard 通过。
- 所有生产 route + operation 为 server-controlled `enforce`，不存在未登记 legacy bypass。
- Cross-account、cross-project、stale、modified manifest、prompt injection、budget 和 rollback 负向测试通过。
- API/browser 输出保持兼容、browser-safe、`no-store`，并有 route-specific tests/smoke evidence。
- 产品文档明确声明 E2 不等于 workspace filesystem isolation。

以下任一事实变化会自动撤销 E2 readiness：gate mode 降级、inventory/source snapshot 漂移、新 violation、required test/evidence 失效、policy/key/snapshot 撤销或 LKG rollback 到非 E2 generation。

### 18.3 E2 明确不保证

- 子进程无法读取 workspace 其他文件。
- 子进程无法读取宿主绝对路径。
- 不同 workspace 已由 OS 隔离。
- 已达到生产多租户强隔离。

这些属于 E3，必须由独立 Windows runner identity、NTFS ACL、restricted token、独立 Artifact View root、受控 writeback、reparse boundary、进程/网络/secret 隔离和越界负向测试证明。

### 18.4 测试矩阵

| 范围 | 最低验证 |
| --- | --- |
| Schema/组合合同 | 全部正负 fixture、unknown field/revision、跨对象 invariants |
| Snapshot/路径 | clean/dirty/untracked/deleted、case collision、Unicode NFC、reparse escape、same-input hash |
| 构建/存储 | 外置 root、原子 pointer、并发锁、失败不提升、LKG、retention reference |
| Query/Evaluation | tokenizer vectors、ranking、glob expansion、empty relevant set、threshold、same-snapshot zero diff |
| Knowledge Locator | JSON stdin/stdout contract, trusted-envelope ownership, rg/BM25 ordering, exact anchors, insufficient match, source-hash revalidation |
| Knowledge maintenance Skill | existing-only no-discovery, targeted scope, pinned local main, provisional worktree content, no source mutation, append-only log, LKG |
| Seeder/Template | `ProjectWorkspaceSeederTests`、新 workspace 不含 cache/projection、自递归为零 |
| Project isolation | fake cross-account/project、stale generation、project restriction only narrows |
| Context assembly | tier/budget、required omission blocks、deterministic section crop、artifact hash |
| Manifest security | JCS cross-language vectors、HMAC modification、expiry、replay、rotation、revocation、constant-time verification |
| DB persistence | backward migration、restart、atomic nonce、prompt evidence binding、restore |
| Shared entrypoints | `CodexHostedProcessCommandFactoryTests`、`LlmRouteEngineTests`、`scripts/sc/tests/test_llm_backend.py` |
| Hosted routes | 每个 inventory caller 的 read-only/workspace-write、authorized/unauthorized、stable errors、browser no-store |
| Existing contracts | recovery exact order、prompt scan、source recomputation、same-project succeeded run、live blocker priority、explicit exemption |
| Migration/readiness | legacy/observe/enforce、client cannot select mode、inventory drift、rollback revokes E2 |

共享 Phase 代码变更还必须运行 `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj` 及对应 Phase smoke，并按 `AGENTS.md` 把运行证据写入 `logs/`。本计划不允许为了通过测试禁用测试。

### 18.5 ADR 与保护路径门槛

正式实现前必须新增一份 Accepted ADR，固定四域、E1/E2 边界、外置缓存、Manifest trust root、JCS/HMAC、防重放和 readiness 撤销语义。实施还必须按影响更新或关联：

- ADR-0033：Manifest/nonce/gate mode DB migration 和恢复。
- ADR-0035：Hosted runner、workspace 和 host-owned Artifact View 边界。
- ADR-0037：三类共享 LLM/Codex 入口和 caller migration。
- ADR-0038：route evidence、prompt binding、脱敏 readback 和 source hash。
- ADR-0040：仅作为 E3 下游提案，不为本计划授权。

修改保护路径前，必须向用户列出精确文件、write set、兼容策略、测试和 rollback，并取得显式授权。

### 18.6 Bootstrap Review 入口条件

本计划采用 `run-phase-bootstrap-review` 的门槛语义，但不因创建本文件自动启动评审。正式 `bootstrap-upstream-plan` Review 只能在以下条件满足后由用户显式授权：

- 本文件及所有评审 context artifact 已冻结到精确 source snapshot。
- K1 ADR 草案和 K2 实际 Schema、fixture、组合 validator 已物化，或评审范围明确只评价 plan authority 且 deterministic preflight 可执行。
- 计划专用 validator、命令、输出路径和 hash 已形成 deterministic preflight evidence。
- 评审 write set、execution read set、dependency closure 和 profile context classes 完整。
- 若成本估计为 high-cost，用户已看到 P50/P90 估计并显式确认。
- Blind Hunter、Edge Case Hunter 和 Acceptance Auditor 能保持隔离，且没有同时修改 reviewed target。

在这些条件之前，只能做普通静态评估，不能把未运行的 Bootstrap Review 描述为 PASS。

## 19. 决策门与完成判定

以下事项在对应切片中必须被版本化决定，不能留给运行时猜测：

- K1：新 ADR ID、Domain registry 和跨域二跳 policy。
- K2：JCS 实现、JSON Schema draft、identity/applicability 条件、glob matcher、Tokenizer 参数、BM25/score mapping、token estimator 和 reference vectors。
- K3：cache root 默认值、lock TTL 和 retention policy。
- K6：预算与 evaluation 阈值的校准结果。
- K11：与 BH-SF2 的 merge/supersede 关系和保护路径授权。
- K12：逐 route rollout 顺序、兼容期限和 rollback authority。
- K13：E2 readiness 计算器、release evidence envelope 和文档投影。
- K5: Locator request/result revision, trusted-field ownership, retrieval order, confidence mapping, and stable failure codes.
- K14: maintenance Skill package identity, closed-world/targeted policy, local-main authority semantics, and maintenance log retention.

本专项只有在 K13 全部 evidence current 且第 18.2 节机械 predicate 为真时，才可称为 E2 完成。K14 是扩域和持续维护，不得倒过来补做 E2 的安全前提。E3 永远不能通过本文件、E2 Manifest 或 Bootstrap Review 输出间接宣称完成。

## 20. Requirements Amendment Log

### 2026-07-25: Knowledge maintenance and standardized consumption

- Trigger: the maintainer requested an explicit knowledge-base maintenance entrypoint and one standardized consumption path for CLI, Skill, Tool, MCP, document, and execution-plan consumers.
- Added: the `maintain-knowledge-base` Skill contract, `existing-only` and `targeted` modes, pinned local-main authority, provisional handling for target-only worktree content, source-mutation prohibition, and append-only maintenance evidence.
- Added: the deterministic Knowledge Locator core, CLI-first JSON request/result contract, caller/LLM responsibility split, exact source-location output, hash revalidation, and `insufficient_match` behavior.
- Preserved: Projection remains `derived_cache`; no new provider or invocation path is introduced; ambiguity still delegates only through `scripts/sc/_llm_backend.py::run_llm_exec`; E3 and Phase production integration remain outside this amendment.

## Recovery Metadata Supplement (2026-09-30)

Added for recovery-document schema completeness. Original source text,
authority notices, paused states, non-goals, and evidence remain unchanged.
These fields are source locators, not a new implementation status or approval.

- Title: Ji Mu Yun 四域知识与上下文工程 Canonical 实施合同
- Branch: n/a - the original source did not capture an authoring branch
- Git Head: n/a - the original source did not capture an authoring commit; no historical binding is inferred
- Goal: Preserve the pre-split four-domain knowledge/context requirements for Phase E1 and E2; exclude E3.
- Scope: Original requirements provenance; current executable authority belongs to the split plan and Accepted ADR-0044.
- Current step: Source-document recovery only; this supplement does not assert current implementation or lifecycle state.
- Last completed step: The original source document was recorded; implementation progress is owned by separate consumer evidence.
- Stop-loss: Preserve original authority and non-goals; do not infer acceptance, activate a paused plan, or rewrite historical evidence.
- Next action: Consult execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/00-index.md and its machine contracts for current state.
- Recovery command: py -3 -c "from pathlib import Path; print(Path('execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan.md').read_text(encoding='utf-8'))"
- Open questions: Consult the original body and its authority notice for unresolved decisions; this supplement resolves none.
- Exit criteria: The original requirements and acceptance conditions remain unchanged; any completion claim requires separate current consumer evidence.
- Related ADRs: ADR-0044 (Original Requirements Authority Notice above)
- Related decision logs: n/a - no decision-log binding was captured in the original source metadata
- Related task id(s): n/a - this source document does not bind a stable implementation task identifier
- Related run id: n/a - this source document does not bind a canonical current execution run
- Related latest.json: n/a - this source document does not bind a canonical current latest.json pointer
- Related pipeline artifacts: n/a - this supplement produces no implementation or acceptance artifacts; retain any original evidence references in the body
