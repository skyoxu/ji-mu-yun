# VDD Conformance Exact-Cover Skill 需求规格

- Title: `vdd-conformance-exact-cover` Skill 需求规格
- Status: `requirements-ready`
- Goal: 在 VDD 创建或读取 execution-plan 之后，验证其 requirements 目录是否完整保留了该次 VDD source-freeze manifest 中的规范性上游内容，并产出可由 VDD `repair` 显式消费的非授权 conformance/repair artifact。
- Scope: 上游 obligation 提取、requirements/acceptance/disposition 映射、确定性 exact-cover 检查、语义歧义 handoff、VDD repair 输入合同和验收夹具。
- Non-goal: 不修改 execution-plan；不实现或替代 `run-phase-bootstrap-review`；不拥有实现代码、测试、current run evidence、Bootstrap 启动决定、Acceptance 或任何 lifecycle/release 权限；不创建新的 review runner、reviewer 层或 legacy 迁移系统。
- Related sources: 根 `AGENTS.md`、`README.md`、`workflow.md` Chapter 5、`docs/know14.txt`、`.agents/skills/vdd-execution-plan/SKILL.md`、`.agents/skills/run-phase-bootstrap-review/SKILL.md`。
- Confidence: 0.90。新 Skill 只验证 VDD 已冻结的上游需求保真度；任何语义判断交给现有 `bootstrap-upstream-plan`，任何目录修复交给 VDD `repair`。

## 1. 背景与问题

Chapter 5 的可迁移核心是一个条件触发的语义稳定化 lane：

```text
VDD source-freeze manifest
→ obligation candidates
→ canonical requirements/acceptance mapping
→ deterministic coverage preflight
→ (only when ambiguous) semantic review handoff
→ VDD repair artifact
```

过去这部分职责被混入 Bootstrap Review，导致：

- LLM 既提取需求又承担完整性判断，遗漏无法被机器阻断；
- 大量源文档、工具 stdout 和历史 evidence 被注入主上下文，容易触发 `context window` 溢出；
- “所有 slice 完成”可能被误当作需求已全部实现；
- caller 提供的 `exactCoverPassed=true` 可能绕过独立重算。

新 Skill 专门负责需求目录的机器可证明保真度。它不审查实现闭环，也不决定是否启动 Bootstrap；出现不可由确定性规则解决的语义歧义时，只产生带 source/requirement ID 的 `semantic_review_required` handoff，由现有 `bootstrap-upstream-plan` 在获得显式授权后审查。

## 2. 职责边界

### 2.1 新 Skill 拥有的职责

1. 消费 VDD 已冻结的 source manifest，不能由 caller 用任意路径集合缩减 authority universe。
2. 将自然语言中的每条 obligation 绑定到稳定 ID、原文摘录、来源 hash 和 source pointer。
3. 验证 source obligation 与 requirements/acceptance/disposition 的双向 sound-and-complete cover。
4. 识别遗漏、unknown、重复、语义弱化、冲突和未处置项；不判断 implementation/test/evidence。
5. 生成 compact、hash-bound、`authorizes=[]` 的 conformance/repair artifact。
6. 对无法由确定性规则判定的映射输出 `semantic_review_required`，并指向 `bootstrap-upstream-plan`；不自动修改目标目录。

### 2.2 明确不拥有的职责

- 不执行或修改 Bootstrap Review 的 reviewer、packet、capsule、retry 或 child workspace 实现。
- 不把自然语言语义争议直接判为通过；真实语义冲突交给现有 `bootstrap-upstream-plan`。
- 不信任 caller 传入的 coverage/complete/verified 布尔值。
- 不改变 lifecycle ownership、Acceptance 授权或 release/commit 权限。
- 不拥有实现 ref、test definition、current run evidence、风险分级、review rounds 或 legacy migration。
- 不修改 `execution-plans/<target>`；所有修复由 VDD `repair` 执行。

## 3. 权威与输入

目标是一个由 VDD 产生或已存在的 `execution-plans/<target>` 需求目录。新 Skill 必须消费同一次 VDD 运行的 source-freeze manifest，而不是重新发明仓库 authority 发现器。运行开始时冻结 run input：

| 字段 | 要求 |
| --- | --- |
| `run_id` | 唯一、不可复用；legacy run 只读 |
| `target_root` | repository-relative、normalized；禁止绝对路径和 `..` |
| `source_manifest` | VDD source-freeze 的完整 manifest 路径、hash 和 schema 版本；缺失或漂移即阻断 |
| `requirements_root` | 待检查的 requirements 目录，repository-relative；新 Skill 只读 |
| `requirements_manifest` | requirements 目录内容 hash 和 schema 版本 |
| `candidate_identity` | 当前候选 revision/worktree 及内容 manifest hash |
| `validator_identity` | schema、脚本版本和规则 hash |
| `predecessor_run_id` | 无前序时为 `null` |
| `execution_mode` | `evidence_only` 或 `controlled_validation` |
| `semantic_review_authorization` | `null` 或显式授权的 Bootstrap Review handoff；不得由 prompt 隐式授权 |
| `authorizes` | 所有中间 receipt 固定为 `[]` |

权威顺序为：VDD source-freeze manifest → 其 hash-bound 上游文件 → requirements directory → conformance validator。历史总结、旧 run 和 caller 结论只能作为诊断输入；仓库治理规则通过 VDD manifest/Locator 结果进入，不由本 Skill 创建第二套知识闭包。

## 4. Canonical 数据模型

### 4.1 Obligation

每条 obligation 至少包含：

```json
{
  "obligation_id": "OBL-<stable-id>",
  "source_path": "docs/source.md",
  "source_sha256": "sha256:...",
  "anchor": {"line_start": 10, "line_end": 14, "quote": "..."},
  "kind": "behavior|constraint|workflow|non_goal",
  "status": "active|not_applicable|deferred|conflict",
  "disposition": {"reason": "...", "authority_reference": "...", "target_plan": "..."},
  "acceptance_ids": ["AC-001"]
}
```

逻辑 obligation identity 与 source content hash 分离：同一逻辑项的内容变化保留 lineage，并使旧覆盖证据 stale。重复、孤立、无摘录或 hash 漂移必须 fail closed。

### 4.2 Canonical acceptance

Acceptance 必须可证伪并绑定 deterministic check：

```json
{
  "acceptance_id": "AC-001",
  "obligation_ids": ["OBL-001"],
  "predicate": "machine-checkable predicate",
  "negative_case": "expected failure condition",
  "authorizes": []
}
```

`predicate` 不得只是“测试通过”；必须说明输入、观察结果和失败语义。每个 active obligation 至少有一个 acceptance，每个 acceptance 至少回指一个 obligation。实现、测试和 current evidence 由 VDD/Quick Dev/Acceptance 后续阶段绑定，不属于本 Skill 的 conformance matrix。

### 4.3 Conformance matrix 与 evidence

矩阵行至少包含：`obligation_id`、`requirement_ids`、`acceptance_ids`、`mapping_kind`、`source_hashes`、`requirements_hash`、`disposition` 和 `evidence_refs`。本矩阵只证明需求目录覆盖；不得伪造 `implementation-complete`、`verified` 或 `acceptance-passed`。

允许一个 obligation 被多个 requirements/acceptances 合法覆盖，但必须记录关系和合并理由。unknown ref、重复 ID、错误映射、未处置冲突和 silent omission 均为阻断错误。本文的 exact-cover 指 sound-and-complete cover，不要求互斥 partition。

## 5. 核心工作流

### S0. Source freeze

读取 VDD source-freeze manifest，验证 manifest/schema/hash/run identity。任何缺失、不可解码、manifest 漂移或 requirements 目录越界都输出结构化诊断并停止 conformance。

### S1. Obligation extraction

LLM 只提出 obligation candidates、解释真实语义冲突、提议可证伪 acceptance。候选必须回到逐字摘录和 source pointer；LLM 不能发布 canonical ID 或 PASS。

### S2. Canonicalization

确定性脚本分配稳定 ID、去重、检查 active/disposition 状态，构建 obligation↔requirement↔acceptance 映射。要求 active obligation 与 requirements/acceptance 双向 sound-and-complete cover。

### S3. Deterministic coverage preflight

通过 JSON/schema parsing、set equality、hashing 和 mapping validation 检查：

- active requirement 无遗漏、无未知引用；
- active acceptance 无孤儿、无重复或错绑；
- 每个 active obligation 有 requirement/acceptance mapping；
- source、requirements、validator hash 一致；
- `not_applicable|deferred|conflict` 明确出现在 disposition，不进入 active universe。

### S4. Deterministic result and semantic handoff

重量级读取和扫描在确定性子进程/脚本中完成。主进程只接收固定上限的摘要、计数、错误 ID、证据路径和 hash；原文 stdout、完整矩阵和源码只落盘到 run evidence，不注入主上下文。结果只能是：`blocked`（确定性缺口）、`conformant`（无语义歧义）或 `semantic_review_required`（需要既有 Bootstrap Review）。

当结果为 `semantic_review_required`，产出完整、hash-bound 的 handoff，固定 profile 为 `bootstrap-upstream-plan`，列出 obligation/requirement IDs、歧义原因、冻结 authority 和 review scope。除非调用方明确授权，不自动启动 Review。

### S5. VDD repair handoff

生成 `vdd-repair-input.v1`，绑定原始 source-freeze、requirements 目录、validator 和（如有）Bootstrap validation envelope。该 artifact 始终 `authorizes=[]`，不发布 `plan-ready`，不修改目标目录；VDD 只在用户显式请求 `repair` 时消费它。

## 6. LLM 与确定性边界

| 能力 | 归属 |
| --- | --- |
| 初步抽取 obligation、解释语义冲突 | LLM，非授权 |
| source hash、逐字 anchor、稳定 ID | deterministic |
| exact-cover、unknown/duplicate/drift 检查 | deterministic |
| mutation/negative fixture | deterministic |
| 语义是否真实冲突 | `bootstrap-upstream-plan`，非本 Skill |
| 是否启动 semantic review | 调用方显式授权；本 Skill 只返回 handoff |
| 实现、测试、current evidence、风险分级 | VDD/Quick Dev/Acceptance/Bootstrap 各自现有 owner |
| 最终 acceptance-passed | 现有 Acceptance 生命周期所有者 |

每次 requirement coverage 不得触发一次 LLM pass。LLM 只用于候选抽取/对齐建议，并必须通过仓库共享 LLM backend、UTF-8 stdin；正常成本应主要是解析、集合运算和哈希。

## 7. 上下文与恢复边界

新 Skill 只控制自身的上下文输入和文件化恢复，不拥有、修改或承诺 Codex 原生 thread resume、context compaction、context window 阈值或 provider 行为。

- 每次运行必须可从 `source_manifest`、`requirements_manifest`、`validator_identity` 和落盘 artifact 在新 Codex thread 或无会话进程中重新开始；不得要求 `resume --last` 或依赖旧对话历史。
- 运行开始即写入 compact `run-manifest.v1`，只保存 run/stage、输入路径与 hash、artifact 路径与 hash、结果状态、pending obligation/finding IDs 和下一合法动作；不得保存 source 全文、reviewer 正文、工具 stdout 或历史 prompt。
- 中断后只读取 `run-manifest.v1` 和其中指向的当前 artifact。任一 input/validator hash 漂移时必须开始新 run 或 fail closed，不得把旧摘要拼接成当前 authority。
- 主 Agent 不读取完整 source inventory、coverage matrix、reviewer 输出或历史 evidence。完整内容由确定性子进程或隔离的既有 Review Skill读取；主 Agent只接收 schema-valid 的 bounded summary、路径、hash、verdict 和有限 finding IDs。
- `bootstrap-upstream-plan` 的完整 review evidence 保持在其原有 run 目录；新 Skill 只消费当前、hash-bound 的 validation envelope，不复制 reviewer 正文到自己的上下文或 artifact。
- 所有 bounded output 必须有版本化上限、`truncated` 标志和完整 artifact 路径/hash。达到上限时不得静默截断或继续向主上下文追加全文。
- 发现 Codex context-window、transport 或进程中断时，新 Skill 只能保留文件化 checkpoint 并停止；它不得宣称已压缩 Codex thread，也不得通过重复发送相同 prompt 恢复。

## 8. Fail-closed 与 stop-loss

以下任一条件成立，结果不得为 `conformant`，且 `authorizes=[]`：

- source manifest、requirements 或 validator hash 缺失/漂移；
- active obligation/requirement/acceptance 有遗漏、孤儿、重复、unknown ref 或错绑；
- disposition 缺失、冲突未处置或 applicability ambiguous；
- 确定性扫描输出超预算、schema error 或 `hard_uncovered`；
- 路径越界、绝对路径、`..` 或 custody-path substitution。

明确的语义疑义不得伪造 `blocked` 或 `conformant`，必须输出 `semantic_review_required`。同一失败不得原样重试；旧 evidence 追加保留，不覆盖历史文件。新 Skill 不修改 requirements 目录。

## 9. 负例与组合验收

必须提供真实 producer→consumer composition，而不是只测 mocks，至少覆盖：

1. missing obligation、unknown requirement、orphan acceptance；
2. requirement→acceptance 错绑、duplicate legitimate consumers；
3. requirement 语义弱化、合法合并、unknown ref 和冲突未处置；
4. source/requirements/validator hash 漂移；
5. typed disposition 正确排除 active universe；
6. 语义歧义只输出 `semantic_review_required`，不伪造 PASS；
7. 旧或篡改的 Bootstrap validation envelope 被拒绝；
8. 新 Skill 执行期间 requirements 目录字节不变；
9. 中断后在新 thread/进程中仅凭 compact run manifest 和 hash-bound artifacts 可重启；
10. resume fixture 证明 source 全文、reviewer 正文、工具 stdout 和历史 prompt 未进入主 Agent；
11. bounded summary 超限时设置 `truncated=true` 并指向完整 artifact，不把全文追加到上下文。

组合链至少包括：

```text
 VDD source-freeze → exact-cover producer → (optional) bootstrap-upstream-plan
 semantic result → vdd-repair-input.v1 → explicit VDD repair
```

## 10. 计划的 Skill 结构

后续创建 Skill 时保持渐进披露：

```text
vdd-conformance-exact-cover/
├── SKILL.md
├── agents/openai.yaml
├── scripts/validate_conformance.py
├── scripts/build_obligation_inventory.py
└── references/
    ├── schemas/
    │   ├── run-manifest.v1.json
    │   ├── source-coverage.v1.json
    │   └── vdd-repair-input.v1.json
    ├── workflow.md
    └── fixtures.md
```

`SKILL.md` 只保留触发条件、输入/输出合同、执行顺序和失败路由；schema、夹具和重复检查放入 references/scripts。不得在 Skill 内复制 Bootstrap Review runner、reviewer 层、risk policy、lifecycle 或 VDD repair 实现。脚本必须可单独运行并返回小型 JSON 摘要。

建议 capability 名称为 `vdd-conformance-exact-cover`，目标参数为任意 `execution-plans/<target>`；不得包含 BROH 专用分支。

## 11. Legacy 与迁移

Legacy compatibility remains owned by VDD and its documented adapters. This Skill reads only a valid VDD source-freeze manifest; unknown manifest/schema versions fail closed. It does not migrate or rewrite legacy plans.

## 12. 验收标准

本需求实现后的 Skill 只有在以下条件全部成立时才算 `conformance-complete`：

1. 消费真实 VDD source-freeze manifest，并验证 run/validator/schema identity；
2. 对所有 active obligation 生成唯一、可追溯的 requirement/acceptance mapping；
3. missing、unknown、duplicate、错绑、冲突未处置和 hash drift 全部不产生 `conformant`；
4. `not_applicable|deferred|conflict` 均有 reason、authority_reference 和 target_plan；
5. semantic ambiguity 只输出 `semantic_review_required`，handoff profile 为 `bootstrap-upstream-plan`；
6. 新 Skill 不修改 requirements 目录，所有中间 artifact `authorizes=[]`；
7. `vdd-repair-input.v1` schema-valid、hash-bound、可被显式 VDD `repair` 消费；
8. VDD repair 的真实跨进程 composition 通过，且 VDD 仍独立发布 plan/lifecycle 状态；
9. 缺 source、stale envelope、篡改 artifact、隐式 VDD route 的负例全部 fail closed；
10. 同一 run 可在不恢复旧 Codex thread 的前提下，从 `run-manifest.v1` 和当前 hash-bound artifacts 重启；
11. 主 Agent 的恢复输入只有 bounded summary、路径、hash、verdict、pending IDs 和 next action，不包含完整 source/reviewer/stdout/prompt；
12. Skill 的任何输出均不得声称改变 Codex 原生 resume/compaction，context-window 错误只产生 checkpoint 和停止结果；
13. 至少一个真实 execution-plan 完成 `VDD create → exact-cover → optional semantic review → VDD repair → exact-cover` dogfood。

## 13. 最终语义

```text
VDD source-freeze manifest + execution-plan requirements directory
  ↓
exact-cover Skill
  ├─ deterministic gap → blocked + vdd-repair-input.v1
  ├─ no ambiguity → conformant + authorizes=[]
  └─ semantic ambiguity → semantic_review_required
                              ↓ explicit bootstrap-upstream-plan
                              ↓ validation envelope
                       vdd-repair-input.v1
                              ↓ explicit VDD repair
                       exact-cover Skill rerun
```

核心不变量：

> 任何 VDD requirement 都不能静默消失。
>
> 任何 implementation slice 都不能引用不存在的需求。
>
> “所有 slice 完成”不能替代 requirement coverage 证明。
>
> 机器能确定的问题由 deterministic exact-cover 解决；Bootstrap 只处理机器无法证明的语义问题。
>
> 新 Skill 不修改 execution-plan；VDD 是唯一的 repair、plan-ready 和 lifecycle owner。
>
> Skill 恢复依赖文件化 manifest 和 hash，不依赖或改写 Codex thread 历史。
