# 积木云机器知识与多 Skill 控制面演进上游方案

> **文档用途**：作为 `vdd-execution-plan` 的上游设计输入，由维护者明确选择后，拆分创建多个独立的 `execution-plans/<date>-<slug>/` 需求目录。  
> **仓库基线**：`skyoxu/ji-mu-yun@8c47a52fc8f241f76da9ccb5d936b0fafe807f0f`  
> **基线提交时间**：2026-08-05  
> **方案日期**：2026-08-06  
> **状态**：Design input；不是实现授权、验收结论或发布授权。  
> **目标读者**：机器、LLM、VDD/Quick Dev/Bootstrap/Acceptance Skill；人类维护者保留显式路由、确认和止损权。  

---

## 0. 执行摘要

本方案作出以下七项确定性决策。

1. **不建立工具链控制面的仓库级 Harness Entry。**
   - 不新增统一的 `toolchain-control-plane.py`、`toolchain run`、总路由器或自动串联所有 Skill 的仓库级入口。
   - VDD、Quick Dev、Bootstrap Review、Refactor Acceptance 继续保留各自独立的 Skill、CLI、生命周期和人类参与边界。
   - 允许共享 schema、枚举、解析器、验证器和结果 envelope，但调用入口仍然归各 Skill 所有。
   - Phase 服务层 Harness Entry 和面向用户的沙箱 Harness Entry 属于两个后续独立工程，不纳入本轮工具链控制面改造。

2. **将 `resume-state` 扩展为唯一的计划执行台账。**
   - 支持显式操作：`create`、`resume`、`repair`、`iterate`、`replan`。
   - 不新增 `subtasks.json`、`work-items.json` 或其他平行当前状态真相源。
   - `plan-state` 继续拥有计划生命周期，`implementation-contract` 继续拥有预期切片和命令，执行证据继续拥有事实；`resume-state` 只拥有“当前执行投影、操作历史、阻塞和下一动作”。

3. **建立 Phase API Inventory。**
   - 对 `PhaseA.Platform/Program.cs` 中的 Minimal API endpoint 建立机器可读映射。
   - 必须覆盖：route、method、auth、DTO、application use case、data owner、external dependency、tests、ADR/standard。
   - Inventory 初期是**可重建、可验证的派生索引**，不是凭手写文档替代源码。
   - 后续 Phase 重构可逐步将显式 endpoint contract/OpenAPI 提升为 R3 SSOT。

4. **升级知识定位为两阶段确定性检索。**
   - 第一阶段继续由当前 Knowledge Catalog / Projection 选择模块和封闭 read-set。
   - 第二阶段在候选文件中使用 `rg`、C# symbol/AST、Markdown heading、JSONPath 等确定性定位。
   - 增加版本化术语表、同义词、旧名/新名、事件/方法/协议/代理/通知/回调等语义族。
   - LLM 只能生成不可信查询提示，不能扩大 Domain、路径、权限、生命周期、预算或 read-set。

5. **将 R0–R5 吸收为机器语义类型，而不是物理目录层级。**
   - 不为了人类阅读顺序大规模重排文档。
   - R0–R5 成为 Catalog module 的正交 `knowledgeClass`，配合 Domain、Visibility、Lifecycle Instance、Enforcement Level、Status 和关系图使用。
   - 本方案补齐 R5：运行事实、实例状态、诊断和验收证据。

6. **为 Phase 知识域建立发布准备，但不接入 live Phase Harness。**
   - 先形成 Phase 的 R1 业务规范、R2 技术规范、R3 API/事件/错误契约映射。
   - 建立 Phase consumer projection 和离线验证。
   - Live Phase 路由消费知识库、上下文冻结和 Hosted dispatch 由独立 Phase Harness 工程完成。

7. **为用户沙箱建立知识契约基础，但不提前宣称 E3 隔离。**
   - 定义沙箱业务能力、技术隔离、接口契约、运行证据所需的机器模块和关系。
   - 不实现沙箱入口、容器/Windows Sandbox/VM、网络/秘密隔离，也不将 Proposed ADR 当成实施授权。

---

## 1. 当前仓库事实基线

### 1.1 知识库不是普通全文索引

当前 `knowledge/` 是一个 main-pinned、派生的 location service，已有三层运行结构：

1. `snapshots/repository-source-snapshot.v1.json`
   - 绑定 eligible committed source、source role、`refs/heads/main` 和 SHA-256。
   - 负责完整性，不直接搜索。

2. `catalogs/repository-knowledge-catalog.v2.json`
   - 包含 typed modules、headings、relationships、governance component bundle、route binding 和 source hash。
   - 负责语义发现。

3. `projections/consumer-projections.v1.json`
   - 冻结每个消费者可见的模块。
   - VDD 和 Bootstrap 可查询并冻结。
   - Quick Dev 投影为空，只能复用 VDD 已冻结上下文。

发布通过 immutable generation、`indexes/current.json` 和 `last-known-good.json` 形成逻辑提交；Locator 使用前验证 publication，返回后重新读取 current main source blob 并验证 read-set hash。

因此，本方案不替换 Snapshot–Catalog–Projection–Publication，只补充：

- 更丰富的机器分类；
- 更准确的文件内定位；
- Phase/API/Sandbox 可扩展来源；
- 每个 Skill 的稳定机器契约。

### 1.2 工具链已经是多个独立控制面

当前四个核心 Skill 的权责已经明确：

- `vdd-execution-plan`
  - 拥有计划创建、计划修复、`draft`、`plan-ready`。
  - 选择 `standard`、`resumable`、`self-hosted`。
  - 生成或维护 implementation contract、resume state、knowledge context 和计划证据。

- `quick-dev-tdd-adapter`
  - 仅消费显式、schema-valid 的 `implementation-contract.v1.json`。
  - 执行 RED、GREEN、REFACTOR、slice predicate 和 terminal predicate。
  - 最多发布 `implementation-complete`，不拥有 Acceptance。

- `run-phase-bootstrap-review`
  - 拥有独立评审协议、profile、review run、lineage、process event、gate 和 finalized envelope。
  - 不拥有被评审计划的业务验收、提交、发布或 done 状态。

- `run-refactor-implementation-acceptance`
  - 负责目标计划的 deterministic acceptance orchestration。
  - 消费 VDD/Quick Dev handoff，决定是否需要 Bootstrap，导入 finalized run，发布 Acceptance 结果。
  - 不实现目标代码，也不拥有发布或部署。

本方案必须保持这些边界，不通过统一入口把它们压成一个不可见的大状态机。

### 1.3 当前 `resume-state` 信息不足

当前代表性 `resume-state.v1.json` 使用 `vdd.resume-state.v2`，主要字段是：

- `plan_id`
- `profile`
- `current_slice`
- `slice_status`
- `invalidated_slices`
- 自由文本 `next_action`
- 自由文本 `recovery`
- `live_phase_paths_allowed`

它可以帮助跨会话恢复，但不足以稳定表达：

- 本次是 create/resume/repair/iterate/replan 中哪一种；
- 谁选择了操作；
- 操作依据和 authority binding；
- 每个切片的依赖、尝试、失败 fingerprint 和失效原因；
- repair round / iteration identity；
- baseline/candidate/contract/knowledge hash；
- 机器可判定的 blocker 和 next action；
- 状态投影是否可以由事件重放得到。

### 1.4 Phase API 需要 Inventory

`PhaseA.Platform/AGENTS.md` 明确：

- `Program.cs` 是 composition root 和 HTTP endpoint map；
- `Security/**` 拥有认证和账户身份；
- `Data/**` 拥有 SQLite 和 metadata；
- `Projects/**`、`Runs/**`、`Llm/**`、`Workspaces/**`、`Readback/**`、`Workflow/**` 分别拥有不同责任面；
- HTTP endpoint 首先解析认证和 account/project ownership，再进入 route service 和执行入口。

当前 `Program.cs` 约 135 KB，包含大量 `app.MapGet` / `app.MapPost` endpoint、认证中间件和 DI 注册。API 规范已有命名、兼容、错误、认证和测试规则，但尚缺一个覆盖全部 endpoint 的机器映射。

### 1.5 用户沙箱尚无实施授权

当前 ADR 只允许逐步证明：

- Windows runner account separation；
- project NTFS ACL；
- storage/restore；
- 再评估容器、Windows Sandbox、轻量 VM 或 remote runner。

ADR-0044 也明确 E3 filesystem/process/network/secret isolation 不在当前 E2 决策中。因此，本方案只能准备 Sandbox R1–R5 知识契约，不能把它描述为已实现或已授权的 Harness。

---

## 2. 总体目标与非目标

### 2.1 目标

- 为 VDD 提供七个可独立创建和验收的需求目录。
- 建立单一执行台账，不增加平行任务真相源。
- 保留每个 Skill 的独立入口与人类确认边界。
- 为 Phase 重构提供完整 API inventory。
- 将知识定位从“模块相关”提升到“文件/符号/行范围精确”。
- 把 R0–R5 变成机器可枚举、可查询、可投影的模块分类。
- 为 Phase 和 Sandbox 的知识域扩展提供明确的 schema、关系和发布边界。
- 所有新行为都可通过 deterministic validator 和 replay 验证。

### 2.2 明确非目标

- 不创建工具链仓库级 Harness Entry。
- 不创建统一自动编排 VDD→Quick Dev→Bootstrap→Acceptance 的总 CLI。
- 不新增 `subtasks.json` 或第二份任务状态账本。
- 不把 Markdown 文档当作 API 字段级 SSOT。
- 不在本轮把所有 Phase endpoint 改造成 Controller 或独立 endpoint class。
- 不自动发布知识 Catalog；仍需 `maintain-knowledge-base` 的显式 publication request。
- 不接入 live Phase route knowledge consumption。
- 不实现用户沙箱、E3、容器、Windows Sandbox、VM 或 remote runner。
- 不批量重写历史 execution plan。
- 不让 LLM 输出直接成为 hard gate 或 authority。

---

## 3. 目标架构

```text
Repository Source / ADR / Standards / Contracts
                    │
                    ▼
         Snapshot + Typed Catalog
                    │
                    ▼
           Consumer Projection
                    │
                    ▼
       Deterministic Query Compiler
                    │
                    ▼
     Module Candidate + Closed Read Set
                    │
                    ▼
 rg / Heading / AST / Symbol / JSONPath
                    │
                    ▼
 Source Reread + Hash Verification + Freeze
```

工具链执行保持多入口：

```text
Human
 ├─ VDD Skill local entry
 ├─ Quick Dev local entry
 ├─ Bootstrap Review local entry
 └─ Acceptance local entry

Shared:
- enum/schema
- execution-ledger validator
- operation request/result envelope
- hash/evidence reference format
- compatibility adapters

Forbidden:
- one repository-level toolchain harness/router
```

未来产品层另行建设：

```text
Phase Service Harness Entry        User Sandbox Harness Entry
          │                                  │
          └──── consume stable R3 / knowledge contracts ────┘
```

---

# 4. 建议创建的七个 VDD 需求目录

日期由实际创建时间决定。以下 slug 和依赖关系应保持稳定。

| ID | 建议目录 slug | VDD Profile | 主要 owner | 依赖 |
|---|---|---|---|---|
| P1 | `toolchain-unified-execution-ledger-v3` | `self-hosted` | VDD | 无 |
| P2 | `toolchain-skill-local-operation-contracts` | `self-hosted` | VDD + 各 Skill | P1 |
| P3 | `phase-api-inventory-v1` | `resumable` | Phase | 无 |
| P4 | `knowledge-query-compiler-and-source-locator-v2` | `self-hosted` | Knowledge Locator | 无 |
| P5 | `knowledge-machine-taxonomy-r0-r5` | `self-hosted` | Knowledge Catalog | P4 可并行设计，发布时依赖 |
| P6 | `phase-knowledge-domain-projection` | `resumable` | Knowledge + Phase | P3、P5 |
| P7 | `sandbox-knowledge-contract-foundation` | `standard` 或 `resumable` | Architecture/Knowledge | P5 |

依赖图：

```text
P1 ──> P2

P3 ───────────────┐
                  ├──> P6
P4 ──> P5 ────────┘
        │
        └──> P7
```

推荐执行波次：

- Wave 1：P1、P3、P4 并行。
- Wave 2：P2、P5。
- Wave 3：P6、P7。
- P6/P7 完成后，再分别创建 Phase Harness 和 Sandbox Harness 的独立上游工程；不在本方案中创建。

---

# 5. P1：统一执行台账 `resume-state.v3`

## 5.1 目标

将 `resume-state` 从“当前切片摘要”升级为单一、类型化、可重放的计划执行台账，同时保持：

- `plan-state` 是生命周期 SSOT；
- `implementation-contract` 是意图、切片、命令和 write/read set SSOT；
- receipt、test result、Bootstrap envelope、Acceptance result 是事实证据；
- `resume-state` 不可凭自身宣告 implementation/acceptance 完成。

## 5.2 推荐 source owner

- Schema owner：
  - `.agents/skills/vdd-execution-plan/references/resume-state-contract.v3.json`
- Deterministic core：
  - `.agents/skills/vdd-execution-plan/scripts/execution_ledger.py`
  - 或现有 Skill 内等价脚本。
- Shared read/validate compatibility：
  - 可抽到 `scripts/python/`，但不得形成统一 Harness Entry。
- Plan-local instance：
  - `execution-plans/<target>/resume-state.v1.json`
  - 保持文件名兼容，内部 `schema_version` 升级为 `vdd.resume-state.v3`。

不建议新增 `resume-state.v3.json` 与旧文件并存，否则会产生当前状态双真相。

## 5.3 操作枚举

```text
create
resume
repair
iterate
replan
```

语义：

### `create`

- 仅由显式 VDD create 请求启动。
- 为新目标生成计划身份、初始 contract binding、slice projection 和 ledger event。
- 不因发现一个 requirements 文件或任务变复杂而自动进入。

### `resume`

- 继续一个 schema-valid、authority-valid、未完成且未失效的现有切片。
- 必须验证 baseline、contract、knowledge freeze、当前 source hash 和 predecessor evidence。
- 不改变需求边界和 architecture authority。

### `repair`

- 针对 current blocker、失败 predicate、P0/P1 finding 或 repair completeness 缺口进行原目录内修复。
- 绑定 finding set、predecessor、repair round、affected slices 和 invalidation closure。
- 不使用新目录重置 review budget。

### `iterate`

- 在同一 acceptance target 和 authority boundary 内新增一个明确、有限的新迭代。
- 必须显式声明 `iterationId`、新增目标、受影响切片和兼容性。
- 不允许用 iterate 掩盖 architecture、security、public API、DB schema 或所有权边界变化。

### `replan`

- 当需求、authority、architecture、公共契约、baseline 选择或作用域发生实质变化时重做计划。
- 由 VDD 拥有。
- 必须显式记录旧 contract 被 supersede、哪些历史证据仍可引用、哪些必须失效。
- 可以更新原目录中的版本化 contract，或在 incompatible target 时创建 successor；不得静默覆盖历史。

## 5.4 不使用关键词直接决定操作

`redo`、`bugfix`、`continue`、`重做`、`修复`、`继续` 仅作为 untrusted hint。

确定性选择顺序：

```text
无有效计划或明确要求新建
  -> create

当前有失败 predicate / confirmed blocker / repair finding
  -> repair

有效且未完成的当前切片，authority 未漂移
  -> resume

目标相同、边界相同、增加有限能力
  -> iterate

scope / authority / architecture / public contract / baseline 实质变化
  -> replan
```

未知、冲突或无法证明的事实必须 fail closed，并路由到 VDD clarification/replan，不得默认 resume。

## 5.5 推荐 schema

```json
{
  "schema_version": "vdd.resume-state.v3",
  "plan": {
    "plan_id": "example",
    "profile": "resumable",
    "target_identity": "sha256:...",
    "plan_state_ref": {
      "path": "plan-state.v1.json",
      "sha256": "sha256:..."
    },
    "implementation_contract_ref": {
      "path": "implementation-contract.v1.json",
      "sha256": "sha256:..."
    }
  },
  "execution": {
    "operation": "resume",
    "operation_id": "op-...",
    "iteration_id": null,
    "repair_round": null,
    "current_slice": "S2",
    "status": "blocked",
    "selected_by": "quick-dev-tdd-adapter",
    "selected_reason_code": "CURRENT_SLICE_INCOMPLETE"
  },
  "bindings": {
    "baseline": "git:...",
    "candidate": "worktree:...",
    "knowledge_context": "sha256:...",
    "command_registry": "sha256:..."
  },
  "slices": [
    {
      "slice_id": "S1",
      "status": "complete",
      "depends_on": [],
      "attempts": ["attempt-1"],
      "invalidated_by": []
    },
    {
      "slice_id": "S2",
      "status": "blocked",
      "depends_on": ["S1"],
      "attempts": ["attempt-2"],
      "invalidated_by": [],
      "blocker_refs": ["evidence:..."]
    }
  ],
  "blockers": [
    {
      "code": "SLICE_PREDICATE_FAILED",
      "severity": "blocking",
      "slice_id": "S2",
      "evidence_refs": ["..."],
      "repair_operation": "repair"
    }
  ],
  "next_action": {
    "operation": "repair",
    "owner": "vdd-execution-plan",
    "reason_code": "CURRENT_BLOCKER_REQUIRES_PLAN_REPAIR",
    "required_inputs": ["..."]
  },
  "events": [
    {
      "sequence": 1,
      "event_id": "evt-...",
      "operation": "create",
      "actor": "vdd-execution-plan",
      "timestamp_utc": "...",
      "input_hash": "sha256:...",
      "result_hash": "sha256:..."
    }
  ],
  "authorizes": []
}
```

## 5.6 核心不变式

- `events.sequence` 连续、唯一、不可重排。
- 当前 projection 必须可由事件和当前 contract 重放得到。
- `current_slice` 必须存在于 implementation contract。
- slice dependency 必须 acyclic。
- complete slice 的 terminal evidence 必须存在且当前 hash 可验证。
- source/contract/knowledge drift 不能自动继续；必须 invalidate 或 replan。
- `resume-state` 永远不得包含：
  - `acceptance-passed` 的自授权；
  - commit/release/deploy 授权；
  - Bootstrap clean 的伪造结论。
- `authorizes` 默认为空；生命周期发布仍由 owner Skill 的现有正式命令完成。

## 5.7 与其他真相源的关系

| 文件/证据 | 唯一职责 | `resume-state` 是否可覆盖 |
|---|---|---|
| `plan-state.v1.json` | 计划生命周期 | 否 |
| `implementation-contract.v1.json` | 切片、命令、读写边界、退出条件 | 否 |
| `command-registry` | 可执行命令定义 | 否 |
| knowledge freeze | 冻结输入与 source hash | 否 |
| receipts/tests | 已发生事实 | 否 |
| Bootstrap finalized envelope | 评审事实 | 否 |
| Acceptance result | 验收事实 | 否 |
| `resume-state` | 当前操作、当前切片、失效、阻塞、下一动作、事件索引 | 是，且唯一 |

## 5.8 迁移策略

- 新 plan 和被显式 repair/iterate/replan 的 plan 写 v3。
- 未触碰历史 plan 保持原字节。
- 提供 v2 read-only compatibility adapter。
- compatibility adapter 输出 v3 projection，但不得改写旧文件。
- v2 的自由文本 `next_action`、`recovery` 只能映射成 `legacy_untyped`，不能自动授权动作。
- 所有 Skill 先 dual-read，再切换为 v3-only write。
- 不创建 `subtasks.json`。

## 5.9 验收

- schema 正/负 fixture；
- create/resume/repair/iterate/replan 全部可重放；
- 重复 operation idempotent；
- hash drift、未知 slice、循环依赖、非法 owner、非法 lifecycle 自授权全部失败；
- v2 historical fixture 可读取但不会被自动重写；
- Quick Dev 可从 v3 得到唯一 next action；
- Acceptance 可验证 ledger，但不能修改 VDD-owned plan intent；
- repository search 不出现新的 `subtasks.json` current-state owner。

---

# 6. P2：逐 Skill 的 R3-Core Operation Contract

## 6.1 目标

统一跨 Skill 的 request/result/evidence 引用格式，但保持每个 Skill 独立入口，不建立总路由器。

## 6.2 公共 envelope

### Request

```json
{
  "schemaVersion": "jimuyun.skill-operation-request.v1",
  "operation": "implementation.resume",
  "target": {
    "kind": "execution-plan",
    "id": "plan.example",
    "path": "execution-plans/example"
  },
  "caller": "quick-dev-tdd-adapter",
  "expectedState": "implementation-authorized",
  "idempotencyKey": "sha256:...",
  "inputRefs": [
    {
      "role": "resume-state",
      "path": "execution-plans/example/resume-state.v1.json",
      "sha256": "sha256:..."
    }
  ]
}
```

### Result

```json
{
  "schemaVersion": "jimuyun.skill-operation-result.v1",
  "operation": "implementation.resume",
  "status": "succeeded",
  "stateBefore": "ready",
  "stateAfter": "running",
  "nextActions": ["implementation.inspect"],
  "errors": [],
  "evidenceRefs": [],
  "authorizes": []
}
```

## 6.3 不创建公共入口

允许：

- 公共 JSON schema；
- 公共枚举；
- 公共 hash/evidence ref validator；
- 公共 envelope serializer；
- 每个 Skill 自己的 CLI command 映射。

禁止：

```text
scripts/toolchain_control_plane.py
scripts/toolchain.py run ...
toolchain invoke <any-skill>
自动选择并启动下一个 Skill 的总 orchestrator
```

## 6.4 Skill operation 映射

### VDD

```text
plan.inspect
plan.create
plan.repair
plan.iterate
plan.replan
plan.validate
```

VDD 继续拥有计划 intent 和 ledger schema。

### Quick Dev

```text
implementation.inspect
implementation.resume
implementation.run-slice
implementation.complete-slice
implementation.publish-complete
implementation.create-repair-handoff
```

Quick Dev 不拥有 plan create/replan 或 acceptance。

### Bootstrap Review

```text
review.inspect-lineage
review.prepare
review.inspect
review.authorize-launch
review.run-role
review.gate
review.finalize
```

现有 `bootstrap_review.py` 继续是本地入口。公共 envelope 只是薄适配层。

### Refactor Acceptance

```text
acceptance.start-or-resume
acceptance.inspect
acceptance.audit-repair-completeness
acceptance.route
acceptance.import-review
acceptance.finalize
```

Acceptance 不应继续直接依赖 Quick Dev/Bootstrap 私有文件布局；应通过 typed result 和 evidence refs 交接。

## 6.5 公共跨边界状态

只统一少量状态：

```text
pending
ready
running
blocked
succeeded
failed
superseded
manual_pause
```

Skill 内部状态继续保留，例如：

- `plan-ready`
- `slice-ready`
- `gate-complete`
- `prerequisite_blocked`

不得为了统一而创建一个覆盖所有内部状态的巨大枚举。

## 6.6 公共错误族

```text
INVALID_REQUEST
UNSUPPORTED_OPERATION
CALLER_NOT_ALLOWED
TARGET_NOT_FOUND
TARGET_STATE_NOT_ALLOWED
INPUT_BINDING_STALE
CONTRACT_SCHEMA_INVALID
KNOWLEDGE_CONTEXT_STALE
DEPENDENCY_INCOMPLETE
IDEMPOTENCY_CONFLICT
REPAIR_REQUIRED
REPLAN_REQUIRED
MANUAL_CONFIRMATION_REQUIRED
PROTECTED_PATH_CONFIRMATION_REQUIRED
INTERNAL_OPERATION_FAILED
```

Skill-specific error 可放入 `details.skillCode`，但公共消费者首先依赖公共错误族。

## 6.7 状态所有权 hard gate

必须通过 negative tests 证明：

- VDD 不能发布 `implementation-complete` 或 `acceptance-passed`。
- Quick Dev 不能发布 `plan-ready` 或 `acceptance-passed`。
- Bootstrap 不能修改 plan lifecycle。
- Acceptance 不能创建/修改 implementation intent。
- 任意 Skill 不能授权 commit/release/deploy。
- 公共 envelope 中 `authorizes` 不能扩大原 Skill 权限。

## 6.8 改造顺序

1. VDD 支持 ledger v3 和 operation envelope。
2. Quick Dev parent router + TDD adapter 接入。
3. Acceptance 改为消费 typed handoff。
4. Bootstrap 增加薄适配，不改核心评审协议。
5. 加 architecture test，禁止 Acceptance import Quick Dev/Bootstrap 私有实现模块。
6. 保留旧 CLI compatibility，直到所有 detached fixtures 和历史回放通过。

---

# 7. P3：Phase API Inventory v1

## 7.1 目标

为当前和后续 Phase 服务重构建立完整、可重建、可验证的 endpoint 映射，避免只靠搜索 `Program.cs` 或人工记忆。

## 7.2 Inventory 定位

初期：

```text
Program.cs / endpoint source
          +
semantic ownership overlay
          ↓
phase-api-inventory.v1.json
```

Inventory 是 derived verified index，不覆盖：

- 已编译 API 行为；
- Accepted ADR；
- Phase standards；
- source DTO；
- Data owner；
- test evidence。

后续 Phase 重构可以逐步把显式 endpoint descriptor/OpenAPI 提升为 R3 SSOT，再从 R3 生成 Inventory。

## 7.3 推荐文件

```text
contracts/phase/api/
  phase-api-semantic-overlay.v1.json
  phase-api-inventory.schema.v1.json
  auth-policy-registry.v1.json
  dependency-kind-registry.v1.json

generated/phase-api/
  phase-api-inventory.v1.json
  phase-api-inventory.report.v1.json
```

若仓库不接受新 `generated/` 根，可由 VDD 基于现有惯例选择稳定派生路径。不得放入 `knowledge/` 作为手写 source，因为 `knowledge/` 是 derived publication 层。

## 7.4 每个 endpoint 必须包含

```json
{
  "operationId": "phase.projects.list",
  "method": "GET",
  "route": "/api/projects",
  "exposure": "authenticated-api",
  "auth": {
    "policy": "current-account",
    "projectOwnershipRequired": false,
    "adminOnly": false,
    "ticketMode": "none",
    "sourceRefs": ["PhaseA.Platform/Program.cs#..."]
  },
  "request": {
    "routeParams": [],
    "queryParams": [],
    "bodyType": null,
    "serviceParams": ["ArtifactReadbackService"]
  },
  "responses": [
    {
      "status": 200,
      "dto": "ProjectSummary[]"
    }
  ],
  "errors": [
    {
      "status": 401,
      "code": "authentication_required"
    }
  ],
  "applicationUseCase": {
    "owner": "Readback",
    "service": "ArtifactReadbackService",
    "method": "ListProjectsAsync"
  },
  "dataOwners": [
    {
      "kind": "sqlite-metadata",
      "owner": "PhaseAMetadataStore"
    }
  ],
  "externalDependencies": [],
  "tests": [
    {
      "path": "PhaseA.Platform.Tests/...",
      "kind": "integration"
    }
  ],
  "authorities": [
    "docs/adr/ADR-0034-phase-account-scoped-token-auth.md",
    "docs/standards/phase-service.md"
  ],
  "sourceHash": "sha256:..."
}
```

## 7.5 稳定枚举

### Auth policy

```text
public
ticket-scoped
authenticated
current-account
project-owner
admin
internal-only
```

### Exposure

```text
public-page
public-health
authenticated-api
admin-api
ticket-download
browser-artifact
internal
```

### Data owner

```text
sqlite-metadata
workspace-filesystem
artifact-sidecar
runtime-process
in-memory-queue
external-provider
none
```

### External dependency

```text
codex-cli
llm-provider
steam-api
http-service
godot-runtime
caddy
filesystem
process-runner
none
```

## 7.6 Operation ID 规则

格式：

```text
phase.<bounded-context>.<action>
```

示例：

```text
phase.projects.list
phase.runs.cancel
phase.account.active-run
phase.assets.create-preview-ticket
phase.admin.users.rotate-token
```

要求：

- 稳定、全局唯一；
- route rename 时保留 compatibility alias 或显式 supersede；
- 不从方法名临时生成后直接当权威；
- overlay 负责稳定 operationId，extractor 负责验证 route/method/source。

## 7.7 提取器设计

### 自动提取

使用 Roslyn 或等价 C# parser，从 `Program.cs` 自动发现：

- `app.MapGet`、`MapPost`、`MapPut`、`MapDelete`；
- literal route；
- handler 参数；
- `[FromServices]` / keyed service；
- route/query/body 参数；
- handler 中直接调用的 service 方法；
- `Results.*` status；
- source line/heading 和 file hash。

### 语义 overlay

以下字段不能仅靠 AST 可靠推断，使用版本化 overlay：

- stable operationId；
- auth policy；
- application use case；
- data owner；
- external dependency；
- authority ADR；
- canonical tests；
- compatibility status；
- deprecation/supersede。

### Composition validator

- 每个自动发现 endpoint 恰好匹配一个 overlay entry。
- overlay 不得指向不存在 endpoint。
- route+method 不重复。
- operationId 不重复。
- auth、DTO、owner、dependency、tests、ADR 字段均为 closed enum/valid ref。
- 缺测试或 ADR 必须显式 `gapDisposition`，不能静默省略。
- source line 和 hash 必须匹配 current main。
- 公开 exception path、ticket route、admin route 必须与认证中间件规则一致。

## 7.8 初期不要求完整 OpenAPI

P3 的第一目标是 inventory 和 refactor safety，不要求一次完成：

- 所有匿名对象的字段级 schema；
- 所有 response union 的 OpenAPI；
- SDK 生成；
- endpoint class 重构。

但是必须记录：

```text
contractCompleteness:
  inventory-only
  partial-dto
  explicit-schema
```

后续 Phase 服务重构优先把高风险 route 升级到 `explicit-schema`：

- auth/admin；
- project-scoped mutation；
- run start/cancel/recovery；
- package/ticket；
- LLM/Codex；
- workspace/artifact readback。

## 7.9 验收

- 自动扫描 current `Program.cs` 全部 endpoint；
- 100% 有 inventory entry；
- 0 duplicate route+method；
- 0 duplicate operationId；
- public/auth/admin/ticket 分类与中间件例外一致；
- 每个 endpoint 有 application use case 和 data owner，或显式 `none`；
- external dependency 闭集；
- tests 和 ADR/standard ref 可解析；
- 修改/新增 endpoint 未更新 inventory 时测试失败；
- inventory 可从 clean main 重建且 byte deterministic；
- 不读取 live metadata DB 或 live workspace。

---

# 8. P4：文件内精准搜索与术语扩展

## 8.1 目标

将当前 Locator 从“模块和最高分行定位”升级为：

```text
消费者投影
→ 模块候选
→ 文件候选
→ 确定性查询编译
→ 文件内精准定位
→ hash 验证
→ frozen context
```

## 8.2 Query Compiler

输入：

```json
{
  "intent": "locate-existing-implementation",
  "rawQuery": "查找项目创建失败通知和回调",
  "entities": ["project creation"],
  "operations": ["failure", "notify"],
  "requestedDomains": ["phase"],
  "untrustedHints": []
}
```

输出：

```json
{
  "schemaVersion": "jimuyun.knowledge-query-plan.v1",
  "exactTerms": [
    "ProjectCreationFailure",
    "project_creation_failure"
  ],
  "semanticFamilies": [
    "failure",
    "notification",
    "callback",
    "event"
  ],
  "symbolPatterns": [
    "*ProjectCreation*Failure*",
    "Notify*",
    "*Callback"
  ],
  "protocolPatterns": [
    "*Event",
    "*Notification",
    "*Handler",
    "*Subscriber"
  ],
  "negativeTerms": [],
  "allowedModuleIds": [],
  "allowedReadSet": [],
  "authorizes": []
}
```

## 8.3 候选词来源

按确定性优先级：

1. 用户原始词和显式符号；
2. 版本化术语表；
3. 中英文 alias；
4. 旧名、新名、deprecation mapping；
5. Catalog module 标题、heading、module ID、关系；
6. 代码命名惯例；
7. 事件/命令/查询/协议/代理/适配器/通知/回调语义族；
8. LLM 生成的 untrusted hints。

LLM hint 必须：

- 标记来源；
- 不改变 trusted scope；
- 不自动进入 exact term；
- 只有被 registry/源码匹配验证后才参与结果解释。

## 8.4 术语表 schema

```json
{
  "schemaVersion": "jimuyun.term-registry.v1",
  "revision": "2026-08-...",
  "terms": [
    {
      "canonical": "notification",
      "domain": "toolchain",
      "aliases": ["通知", "notify", "notice"],
      "codePatterns": ["*Notification", "Notify*", "*Notifier"],
      "relatedFamilies": ["event", "callback", "message"],
      "negativePatterns": [],
      "deprecatedAliases": [],
      "relations": ["publishes", "subscribes_to", "dispatches"]
    }
  ]
}
```

要求：

- domain-aware；
- bilingual；
- closed semantic family；
- alias 冲突检测；
- deprecated alias 不能提升 authority；
- revision/hash 进入 Locator result 和 frozen context。

## 8.5 搜索引擎

| Source | 主定位器 | 退化路径 |
|---|---|---|
| Markdown | heading parser + exact/regex | `rg` |
| C# | Roslyn symbol/call-site parser | `rg` |
| Python | AST import/call/definition | `rg` |
| JSON | JSONPath/key/value | exact text |
| YAML | parsed path | exact text |
| OpenAPI | path/method/operationId/schema | JSON/YAML parser |
| Godot `.tscn/.tres` | scene/resource parser | `rg` |
| 日志/证据 | schema-aware ID/path lookup | exact text |

第一版优先实现仓库收益最高的：

1. Markdown；
2. C#；
3. Python；
4. JSON。

其他 source type 可作为后续 slice，但 schema 必须预留 engine kind。

## 8.6 封闭 read-set

- Locator 第一阶段先决定 allowed modules/files。
- 文件内引擎只能搜索 allowed read-set。
- 不允许第二阶段重新全仓扫描。
- relation expansion 仍由 Catalog/consumer policy 控制。
- 每次搜索输出完整 coverage：
  - searched files；
  - searched symbol families；
  - excluded files/reasons；
  - match count；
  - unmatched exact terms。

## 8.7 Match result

```json
{
  "path": "PhaseA.Platform/Projects/ProjectCreationService.cs",
  "sourceHash": "sha256:...",
  "engine": "csharp-symbol",
  "matches": [
    {
      "kind": "method-call",
      "symbol": "RecordProjectCreationFailureAsync",
      "lineStart": 210,
      "lineEnd": 228,
      "matchedTerms": ["ProjectCreationFailure", "failure"],
      "semanticFamilies": ["failure", "notification"],
      "scoreEvidence": [
        "exact-symbol",
        "use-case-owner-match"
      ]
    }
  ]
}
```

## 8.8 排名

建议权重：

```text
exact operationId / exact symbol
> exact route / exact heading
> exact canonical term
> alias exact match
> semantic-family symbol pattern
> relationship-expanded module
> body token match
> LLM-only untrusted hint
```

LLM-only hint 不能单独达到 `sufficient`。

## 8.9 杜绝散落硬编码

必须 registry/schema 化：

- semantic family；
- source engine kind；
- relation type；
- module kind；
- path exclusion；
- domain/visibility/lifecycle；
- consumer budget；
- alias 和 naming pattern。

允许代码固定：

- schema-supported closed enum；
- 安全默认值；
- parser 自身语法规则。

路径策略不得同时散落在 Locator 代码和 JSON policy；必须只有一个版本化 owner。

## 8.10 Evaluation

扩展当前 108-query suite：

- 模糊中文短句；
- 中英混合；
- 旧名称；
- 方法语义而非类名；
- event/notification/callback；
- protocol/adapter/proxy；
- negative query；
- historical exact-only；
- Phase endpoint/use case；
- repair/acceptance evidence。

指标：

```text
module recall@K
file recall@K
symbol/heading precision
line-range precision
false-positive rate
unmatched required term rate
deterministic byte equality
hash freshness rejection
scope expansion rejection
```

## 8.11 验收

- 输入相同、baseline 相同，Query Plan 和结果 byte deterministic；
- 所有结果来自 consumer allowed read-set；
- C#/Markdown/JSON/Python fixture 可返回准确 symbol/heading/JSON path；
- alias/旧名/中英映射可命中 canonical source；
- alias 冲突、unknown family、scope expansion、stale source hash 失败；
- Quick Dev 仍不能自行查询，只能消费 VDD frozen result；
- publication check 包含新 query suite；
- 不允许 LLM hint 扩大 authority。

---

# 9. P5：R0–R5 机器知识分类

## 9.1 关键结论

R0–R5 不应成为目录层次或读取顺序，而应成为每个 Catalog module 的正交机器属性：

```json
{
  "knowledgeClass": "R3",
  "kind": "api-contract",
  "domain": "phase",
  "visibility": "repository",
  "lifecycleInstance": "repository-source",
  "enforcementLevel": "normative",
  "status": "active"
}
```

## 9.2 R0–R5 定义

### R0：产品与系统意图

机器类型：

```text
product-intent
system-mission
capability-map
core-flow
global-index
```

用于回答：

- 系统是什么；
- 哪些责任面存在；
- 顶层业务流和架构边界是什么。

R0 不能覆盖 ADR、source 或 runtime facts。

### R1：业务与领域规范

机器类型：

```text
domain-model
business-rule
business-invariant
permission-policy
state-machine
core-workflow
glossary
```

要求与前后端实现无关。

Phase 示例：

- account/project/workspace/run/artifact；
- project ownership；
- run cancellation；
- ticket scope；
- route lifecycle；
- prototype iteration/repair；
- business permission matrix。

Sandbox 示例：

- sandbox owner；
- capability；
- quota；
- workspace/session lifecycle；
- allowed operation；
- user-visible error semantics。

### R2：技术与架构规范

机器类型：

```text
architecture
service-design
technical-standard
data-design
security-design
runtime-design
deployment-design
```

Phase 示例：

- ASP.NET composition；
- SQLite metadata；
- queue/concurrency；
- LLM/Codex entrypoint；
- workspace path policy；
- runtime/Caddy/recovery。

Sandbox 示例：

- isolation tier；
- filesystem mount；
- process owner；
- network policy；
- secret injection；
- cleanup/recovery；
- resource accounting。

### R3：接口与执行契约

机器类型：

```text
api-contract
operation-contract
command-contract
event-contract
dto-schema
error-contract
capability-contract
```

这是未来 Phase 和 Sandbox 最关键的可组合层。

Phase R3：

- API inventory；
- explicit request/response schema；
- auth policy；
- error code；
- application use case；
- data owner；
- external dependency；
- event/command；
- idempotency。

Toolchain R3：

- Skill operation request/result；
- resume ledger schema；
- repair handoff；
- review route；
- acceptance import。

Sandbox R3：

- create/start/exec/read/write/stop/destroy；
- capability request；
- mount/network/secret policy；
- process result；
- resource limit；
- error envelope。

### R4：需求、决策与演进

机器类型：

```text
change-set
execution-plan
decision
adr
incident
migration
deprecation
supersession
```

R4 是横向变化轴，不是 R3 的下一级。

一个 R4 module 应通过关系表达：

```text
affects
supersedes
migrates
implements
validated_by
blocked_by
```

### R5：运行事实、实例状态与证据

本方案补齐 R5。

机器类型：

```text
runtime-state
instance-state
diagnostic
audit-evidence
acceptance-evidence
health
usage-metric
process-event
artifact-view
```

严格限制：

- R5 不是 repository source authority；
- 不能进入全局永久 semantic projection 后覆盖 R0–R4；
- 必须绑定 lifecycle instance：
  - project instance；
  - run artifact view；
  - sandbox instance；
  - acceptance run；
- 必须有 current/LKG/expiry/supersession；
- 必须保留 source producer 和 hash；
- live blocker 优先于旧 clean evidence；
- 只在消费者请求当前实例时投影。

## 9.3 正交维度

每个模块至少携带：

```text
knowledgeClass: R0..R5
kind
domain
visibility
lifecycleInstance
enforcementLevel
status
sourceRole
authorityRank
freshnessPolicy
```

Domain 建议保持现有：

```text
toolchain
phase
workspace
marketplace
```

Sandbox 不应立即增加为第五个全局 Domain，除非 Accepted ADR 明确其权限和生命周期。前期可表示为：

```text
domain = phase
subdomain = sandbox
```

当 Sandbox 成为独立产品责任面后再通过 ADR 决定是否提升为独立 Domain。

## 9.4 关系枚举

```text
governed_by
implements
exposes
consumes
produces
depends_on
owned_by
validated_by
tested_by
affected_by
supersedes
superseded_by
migrates_to
blocks
recovers_from
projects
derived_from
```

禁止每个 producer 自由发明关系字符串。

## 9.5 Catalog 迁移

优先采用 additive v2：

- 新增可选 `knowledgeClass`；
- 新增 closed `kind` 和 relation vocabulary；
- old module 通过 deterministic mapper 得到 class；
- v1 compatibility projection 继续生成；
- query suite 扩展。

仅在 additive v2 无法表达时才创建 Catalog v3。不得仅为了命名整洁升级 major schema。

## 9.6 当前来源映射

| 当前来源 | 推荐 class |
|---|---|
| root README/product overview | R0 |
| `docs/prd/**`、GDD business rule | R1 |
| architecture/standards | R2 |
| schema、API inventory、Skill operation contract | R3 |
| ADR、execution-plan、decision-log | R4 |
| logs、run state、acceptance envelope | R5 |

不是所有 source 都自动成为 semantic module。仍由 source role、consumer policy 和 indexing rule 决定。

## 9.7 验收

- 所有 indexed module 均有有效 class/kind；
- relation vocabulary closed；
- R5 不能进入 repository-global source projection；
- historical/superseded module 保持原 status；
- Toolchain/Phase module classification 有 fixture；
- current query suite 不退化；
- 新 class 可被 consumer projection 过滤；
- source path 搬迁不是分类必要条件；
- knowledge publication 可回滚到 LKG。

---

# 10. P6：Phase 知识域投影准备

## 10.1 目标

把 Phase 业务规范、技术规范和 API inventory 纳入机器知识模型，为未来 Phase Harness 提供可消费的 R1–R3，但本计划不接入 live route。

## 10.2 Phase R1 module 集

至少覆盖：

```text
account
authentication
project
workspace
run
prototype
artifact
package
asset
preview
gdd
iteration
repair
chat
admin-review
quota/concurrency
ticket
```

每个 bounded context 至少有：

- entity/identity；
- owner；
- state machine；
- permissions；
- business invariants；
- core operations；
- error conditions；
- related R3 contracts。

允许来源分散在 ADR、standards、workflow 和 code，但 Catalog 需要生成统一 typed module/relationship，不要求重排目录。

## 10.3 Phase R2 module 集

映射当前责任面：

```text
Program / composition root
Security
Data
Projects
Runs
Llm
Skills
Workspaces
Readback
Workflow
runtime/phase-a
```

关系示例：

```text
phase.projects.create
  implemented_by -> ProjectCreationService
  persists_to -> PhaseAMetadataStore
  uses -> ProjectWorkspaceSeeder
  constrained_by -> account/project policy
  exposed_by -> phase.projects.create API
```

## 10.4 Phase R3 module 集

主要来源：

- P3 Phase API Inventory；
- DTO/schema；
- error code registry；
- auth policy registry；
- route operation governance；
- LLM/Codex shared entrypoint；
- ticket/download contract；
- future event/command contract。

每个 API operation 作为独立或 bounded-context 聚合 module，取决于 Catalog budget。推荐：

- module = bounded context；
- entry = operationId；
- heading/symbol anchor = route source + service method；
- relations = tests/ADR/data owner/dependency。

## 10.5 Consumer projection

新增离线 consumer，例如：

```text
phase-design
phase-refactor
phase-harness-preflight
```

在 live integration 前：

- `phase-design` 可查询 R0–R4 repository source；
- `phase-refactor` 可查询 Phase R1–R4 和 current acceptance blocker；
- `phase-harness-preflight` 只做离线 readiness，不能 dispatch。

不得直接让现有生产 route 读取这个 projection。

## 10.6 冻结 contract

未来 Phase Harness 必须绑定：

```text
repository snapshot
template snapshot
project instance
run/dispatch identity
consumer policy revision
term registry revision
API inventory revision
selected modules/read set
source hashes
```

P6 只定义和验证这些输入，不实现 Hosted dispatch。

## 10.7 验收

- Phase API Inventory 可发布为 R3 module；
- Phase R1/R2 module 覆盖现有责任面；
- 每个高风险 API operation 可追溯到 R1 rule、R2 owner、tests、ADR；
- consumer projection 不包含 live metadata 或 workspace secret；
- current source reread/hash verify；
- live Phase route 未被修改；
- 不新增 Phase Harness Entry；
- 为未来独立 Phase Harness plan 输出明确 prerequisite report。

---

# 11. P7：用户沙箱知识契约基础

## 11.1 目标

只建立未来用户沙箱的机器知识和 R3 contract 轮廓，避免 Phase Harness 开发时临时发明 sandbox 语义。

## 11.2 Authority 状态

- ADR-0040 仍是 Proposed。
- E3 不由 ADR-0044 授权。
- 所有 Sandbox module 初始状态应为：
  - `conditional` 或 `proposed`；
  - `enforcementLevel = design-only`；
  - `authorizes = []`。

## 11.3 Sandbox R1

```text
sandbox-owner
sandbox-session
workspace-generation
capability
quota
resource-budget
allowed-operation
artifact-ownership
user-visible-lifecycle
```

状态机候选：

```text
requested
provisioning
ready
running
stopping
stopped
failed
destroyed
```

仅作为 contract proposal，不能宣称 runtime 已实现。

## 11.4 Sandbox R2

```text
filesystem boundary
process identity
network policy
secret policy
mount policy
runner tier
cleanup
restore
audit
resource accounting
```

必须区分：

- account ACL；
- workspace path containment；
- E2 context envelope；
- E3 OS/process/network isolation。

不得混写为同一等级。

## 11.5 Sandbox R3

未来 operation contract：

```text
sandbox.capabilities
sandbox.create
sandbox.inspect
sandbox.start
sandbox.exec
sandbox.read-artifact
sandbox.write-input
sandbox.stop
sandbox.destroy
```

每个 operation 需要：

- auth/account/project；
- idempotency；
- input/output schema；
- allowed state；
- capability；
- filesystem/network/secret ceiling；
- evidence；
- error；
- timeout/cancel；
- cleanup guarantee。

## 11.6 Sandbox R5

```text
instance-state
process-event
resource-usage
network-decision
mount-manifest
secret-injection-receipt
cleanup-receipt
isolation-attestation
artifact-manifest
```

R5 必须绑定具体 sandbox instance，不能进入 repository-global projection。

## 11.7 与未来 Harness 的关系

P7 输出未来 Sandbox Harness 的 prerequisite contract，但不创建入口。

未来独立计划应显式处理：

- Harness API；
- provisioner；
- runner；
- isolation tier；
- persistence；
- cancellation；
- recovery；
- readback；
- security tests；
- destructive cleanup；
- OS evidence。

## 11.8 验收

- Sandbox R1–R5 schema 和 module fixture 可验证；
- 所有状态为 conditional/proposed；
- 没有生产代码、runtime 配置或 live workspace 修改；
- 不声称 E3；
- 没有新增 Harness Entry；
- 未来 Harness 的 required inputs、authority gaps 和 ADR trigger 清单完整。

---

# 12. 跨计划测试与门禁

## G0：Authority 与 Scope

Hard gate：

- baseline/main commit 固定；
- AGENTS/ADR/standards 已读取；
- protected path 需显式批准；
- 不允许 dirty control-plane bytes 生产正式 publication；
- target plan 唯一且 repo-relative。

## G1：Schema 与静态一致性

Hard gate：

- JSON schema；
- closed enum；
- path normalization；
- duplicate ID；
- relation vocabulary；
- lifecycle owner；
- hash format；
- no unknown fields，除非 schema 明确允许 extension。

## G2：单元与契约测试

Hard gate：

- ledger fold；
- operation routing；
- idempotency；
- compatibility；
- query compiler；
- term registry；
- source parser；
- API extractor；
- auth classifier；
- taxonomy mapper。

## G3：跨 Skill Composition

Hard gate：

- VDD v3 ledger → Quick Dev resume；
- Quick Dev handoff → Acceptance；
- Acceptance route → Bootstrap；
- Bootstrap finalized result → Acceptance import；
- 每个 consumer 只能使用 typed envelope/evidence ref；
- 不允许 private implementation import。

## G4：知识发布

Hard gate：

- snapshot/catalog/projection composition；
- source hash；
- query suite；
- contamination；
- current/LKG；
- failed publication rollback；
- explicit publication request。

## G5：Phase API Coverage

Hard gate：

- endpoint 100% inventory；
- auth exception 100%；
- route/method uniqueness；
- operationId uniqueness；
- owner/dependency/tests/ADR coverage；
- source hash freshness。

## G6：Semantic Review

- 只有涉及控制面 owner、security、public API、DB、runtime、shared entrypoint、protected path 的计划才默认 self-hosted/Bootstrap。
- LLM reviewer 只产生 candidate finding。
- deterministic verifier 和 owner gate 决定状态。
- 不用 LLM 单独作为 hard gate。

---

# 13. 兼容和迁移总策略

## 13.1 双读、新写

- 旧 ledger/contract：read-only compatibility。
- 新或显式修改的计划：写新 schema。
- 不批量格式化历史 evidence。
- 不覆盖 historical run。

## 13.2 派生优先

以下全部可重建：

- API inventory；
- query plan；
- source match result；
- R0–R5 classification projection；
- Phase projection。

以下不可由派生层覆盖：

- source；
- Accepted ADR；
- plan lifecycle；
- implementation contract；
- live metadata；
- runtime fact；
- current acceptance blocker。

## 13.3 不自动发布

任何 Catalog/indexing rule 改动：

1. 先在计划中生成和验证；
2. consumer 遇到 stale 时生成 typed non-authorizing route；
3. 维护者显式调用 `maintain-knowledge-base`；
4. publication request 绑定 target plan 和 main commit；
5. 成功后才 advance current/LKG。

## 13.4 Phase 和 Sandbox 后续拆分

本方案完成后仍需两个独立计划：

```text
Phase Harness Entry
User Sandbox Harness Entry
```

二者不得并入 P2 的工具链 Skill operation contract。

---

# 14. 风险与止损

| 风险 | 预防 |
|---|---|
| 共享 envelope 演化成隐藏总 Harness | 禁止统一入口；Skill-local command ownership 测试 |
| resume-state 与 plan-state 冲突 | 字段所有权矩阵；非法 lifecycle 写入 hard fail |
| ledger 事件过大 | 当前 projection + bounded event index；历史事实仍在 evidence |
| API extractor 误判 Minimal API | Roslyn + semantic overlay + 100% composition |
| 手写 overlay 漂移 | source hash、route/method、service symbol 验证 |
| 术语表无限膨胀 | domain ownership、alias conflict、usage/evaluation gate |
| LLM hint 污染 trusted search | `untrustedHints` 独立字段；不能单独 sufficient |
| R0–R5 变成目录重构项目 | 明确只加 metadata，不要求路径迁移 |
| R5 污染全局知识 | lifecycle instance + projection + expiry/current pointer |
| Sandbox 被提前当作已实现 | conditional/proposed + design-only + no production changes |
| 七个计划同时改 shared schema | 严格 dependency wave；P1/P4/P5 owner 顺序 |
| 历史兼容成本失控 | detached fixtures；不自动迁移历史目录 |

Stop-loss：

- 同一 schema/contract 修复超过两轮且仍有 P1：暂停并 replan。
- API inventory 无法达到 100% endpoint coverage：不进入 Phase projection。
- source locator precision 提升但 recall 明显下降：保留旧 module candidate path，禁止切换默认。
- R0–R5 classification 导致现有 108 queries 回归：不发布 Catalog。
- Sandbox 需要 production code 才能验证：停止 P7，创建独立 Sandbox Harness 计划并等待 authority。

---

# 15. Program Definition of Done

全部七个计划完成并不等于 Phase/Sandbox Harness 完成。该 program 完成要求：

- `resume-state.v3` 成为新/修改计划唯一执行台账；
- 不存在新的 `subtasks.json` 当前状态 owner；
- VDD/Quick Dev/Bootstrap/Acceptance 均支持 typed operation envelope；
- 没有工具链仓库级总入口；
- Phase endpoint 100% 有 Inventory；
- Locator 支持 query compiler、term registry 和文件内精准定位；
- R0–R5 作为 typed metadata 可查询和投影；
- Phase R1–R3 可离线发布和验证；
- Sandbox R1–R5 contract foundation 完成且仍为 conditional；
- current knowledge publication 回归通过；
- 所有旧 fixture/historical replay 通过；
- Phase live route 和 Sandbox runtime 未被本 program 越权修改。

---

# 16. 给 VDD Skill 的创建输入

以下七段应由维护者分别明确请求创建，不要一次生成一个巨型计划。

## 16.1 P1 请求

```text
请使用 vdd-execution-plan 创建一个 self-hosted 执行计划目录：
目标是将现有 vdd.resume-state.v2 扩展为唯一的 v3 计划执行台账，
支持 create、resume、repair、iterate、replan，
保持 plan-state、implementation-contract 和 evidence 的现有权威边界，
禁止创建 subtasks.json 或任何平行当前状态真相源。
要求包含 v2 read-only compatibility、事件重放、owner hard gate、
VDD/Quick Dev/Acceptance detached composition tests。
不要创建仓库级工具链 Harness Entry。
```

## 16.2 P2 请求

```text
请使用 vdd-execution-plan 创建一个 self-hosted 执行计划目录：
目标是为 vdd-execution-plan、quick-dev-tdd-adapter、
run-phase-bootstrap-review、run-refactor-implementation-acceptance
建立共享的 typed operation request/result/evidence envelope，
但每个 Skill 保留独立 CLI 和人类路由。
禁止统一 toolchain router、总 orchestrator 或 repository harness entry。
要求包含状态所有权 negative tests 和旧 CLI compatibility。
依赖 resume-state v3 计划完成。
```

## 16.3 P3 请求

```text
请使用 vdd-execution-plan 创建一个 resumable 执行计划目录：
目标是从 PhaseA.Platform/Program.cs 和相关源代码生成
Phase API Inventory v1，
覆盖 route、method、auth、DTO、application use case、data owner、
external dependency、tests、ADR/standard。
使用 Roslyn 或等价可靠 parser 加版本化 semantic overlay，
要求 current endpoint 100% coverage、stable operationId 和 drift gate。
本计划不要求完成 OpenAPI，也不重构全部 endpoint。
```

## 16.4 P4 请求

```text
请使用 vdd-execution-plan 创建一个 self-hosted 执行计划目录：
目标是升级 Knowledge Locator，
保留 Catalog/Projection 的模块筛选，
增加 deterministic query compiler、版本化术语/同义词 registry，
以及候选 read-set 内 Markdown/C#/Python/JSON 精准搜索。
搜索词应覆盖事件方法、功能语义、命名习惯、协议/代理/适配器、
通知/回调等语义族。
LLM 只能提供 untrusted hints，不能扩大权限或 read-set。
```

## 16.5 P5 请求

```text
请使用 vdd-execution-plan 创建一个 self-hosted 执行计划目录：
目标是把 R0 产品意图、R1 业务规范、R2 技术规范、
R3 接口契约、R4 需求演进、R5 运行事实/证据
吸收到现有 Knowledge Catalog 的 typed module metadata，
而不是重排物理目录。
要求 closed kind/relation vocabulary、consumer projection filter、
R5 lifecycle isolation、现有 query suite 无回归和 publication rollback。
```

## 16.6 P6 请求

```text
请使用 vdd-execution-plan 创建一个 resumable 执行计划目录：
目标是将 Phase 的业务规范、技术责任面和 Phase API Inventory
形成机器可消费的 R1/R2/R3 module 和离线 consumer projection，
为未来独立 Phase Harness Entry 做准备。
本计划不得修改 live Phase route，不得实现 Hosted dispatch，
不得宣称 Phase 已集成知识 Locator。
依赖 Phase API Inventory 和 R0-R5 taxonomy。
```

## 16.7 P7 请求

```text
请使用 vdd-execution-plan 创建一个 standard 或 resumable 执行计划目录：
目标是定义未来用户沙箱的 R1 业务能力、R2 隔离设计、
R3 operation contract 和 R5 instance evidence 的机器知识基础。
所有状态保持 conditional/proposed，禁止实现 Sandbox Harness、
容器、Windows Sandbox、VM、网络/秘密隔离或 live runtime 变更。
要求输出未来独立 Sandbox Harness 计划的 prerequisite 和 ADR gaps。
依赖 R0-R5 taxonomy。
```

---

# 17. 默认决策

除非仓库事实证明冲突，VDD 应采用以下默认值，不需要再次询问。

1. 不创建工具链总 Harness Entry。
2. `resume-state.v1.json` 保持路径兼容，内部 schema 升级。
3. v2 历史文件只读，不批量迁移。
4. `subtasks.json` 禁止成为当前状态来源。
5. API Inventory 是 derived verified index。
6. P3 不强制完整 OpenAPI。
7. Query Compiler 完全 deterministic；LLM hints 不可信。
8. R0–R5 是 metadata，不是目录层级。
9. R5 不进入 repository-global source projection。
10. Sandbox 初期属于 Phase subdomain，是否升格独立 Domain 需 ADR。
11. Phase/Sandbox live Harness 分别后置为独立计划。
12. 所有 publication 仍需显式 `maintain-knowledge-base` 请求。
13. 当前代码和 API 默认向后兼容。
14. 涉及 auth、DB、shared LLM/Codex、runtime、public API 时走 protected-path 和 ADR gate。

---

# 18. 需要新 ADR 的触发条件

以下情况必须先更新或新增 ADR：

- 将 plan lifecycle owner 从现有 Skill 转移；
- 引入工具链统一 Harness Entry；
- Phase API Inventory 从 derived index 升级为 API SSOT；
- 删除或改变公开 Phase endpoint、auth、DTO、status、error；
- 将 Sandbox 提升为独立 Domain；
- 宣称 E3 filesystem/process/network/secret isolation；
- 改变知识 publication authority；
- 允许 LLM 扩大 trusted query scope；
- 允许 R5 覆盖 repository source/ADR/current blocker；
- 引入跨进程多写者或外部审批身份模型。

---

# 19. 仓库依据

本方案基于以下 current-main 来源：

- `AGENTS.md`
- `README.md`
- `knowledge/README.md`
- `knowledge/catalogs/repository-knowledge-catalog.v2.json`
- `knowledge/projections/consumer-projections.v1.json`
- `docs/adr/ADR-0040-phase-c-hardening-before-scaleout.md`
- `docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md`
- `docs/adr/ADR-0048-repository-knowledge-locator-workflow-consumption.md`
- `docs/adr/ADR-0057-explicit-knowledge-publication-and-nonrecursive-plan-indexing.md`
- `docs/standards/phase-service.md`
- `docs/architecture/phase-service/_index.md`
- `PhaseA.Platform/AGENTS.md`
- `PhaseA.Platform/Program.cs`
- `.agents/skills/vdd-execution-plan/SKILL.md`
- `.agents/skills/quick-dev-tdd-adapter/SKILL.md`
- `.agents/skills/run-phase-bootstrap-review/SKILL.md`
- `.agents/skills/run-refactor-implementation-acceptance/SKILL.md`
- `execution-plans/2026-07-31-toolchain-workflow-evidence-catalog-v1/resume-state.v1.json`
- 现有 implementation contract、plan state、command registry、knowledge freeze、repair 和 acceptance fixtures。

---

## 20. 最终建议

不要将这七项合并成一个“工具链控制面重构”巨型计划。

最稳妥的边界是：

```text
P1/P2：Skill 协作契约
P3：Phase API 事实索引
P4/P5：知识检索与机器分类
P6：Phase 知识发布准备
P7：Sandbox 契约准备
```

这样可以同时满足：

- 人类可以逐 Skill 深度参与；
- 不产生仓库级隐藏编排；
- 计划执行状态只有一个 ledger；
- Phase 重构前已有 API 事实图；
- Locator 能从模块定位到符号和行范围；
- R3 能服务工具链、Phase 和未来 Sandbox；
- Phase/Sandbox Harness 可以在后续独立工程中消费稳定契约，而不污染本轮工具链控制面。
