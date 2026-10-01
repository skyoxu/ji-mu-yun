# VDD Conformance Exact-Cover Skill 需求规格

- Title: `vdd-conformance-exact-cover` Skill 需求规格
- Status: `requirements-ready`
- Goal: 在 VDD 创建或读取 execution-plan 之后，验证其 requirements 目录是否完整保留了同一次 VDD source-freeze manifest 中的 Canonical Spec Package 规范性内容，并产出可由 VDD `repair` 显式消费、可由现有 implementation authorization owner 验证的非授权 conformance/repair artifact。
- Scope: Canonical Spec Package 权威图、最小 VDD source-freeze producer/repair consumer 合同、deterministic-first adaptive semantic stabilization、上游 obligation 提取、fingerprint/shard safe reuse、typed failure/retry/stop-loss、requirements/acceptance/disposition exact-cover、语义歧义 handoff、implementation prerequisite receipt 和验收夹具。
- Non-goal: 不修改 execution-plan；不实现或替代 `run-phase-bootstrap-review`；不拥有实现代码、测试、current run evidence、Bootstrap 启动决定、Acceptance 或任何 lifecycle/release 权限；不创建新的 review runner、reviewer 层或 legacy 迁移系统。
- Related sources: 根 `AGENTS.md`、`README.md`、`workflow.md` Chapter 5、`docs/know14.txt`、`docs/know17.txt`、`docs/know18.txt`、`.agents/skills/vdd-execution-plan/SKILL.md`、`.agents/skills/run-phase-bootstrap-review/SKILL.md`。
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

新 Skill 专门负责需求目录的机器可证明保真度。它不审查实现闭环，也不决定是否启动 Bootstrap；出现不可由确定性规则解决的语义歧义时，只产生带 source/requirement ID 的 `requirement_semantic_review_required` handoff，由现有 `bootstrap-upstream-plan` 在获得显式授权后审查。

正式需求链路为：

```text
bmad-prd → bmad-spec
         → [必要时 bmad-architecture → bmad-spec refresh]
         → Canonical Spec Package
         → VDD source-freeze → VDD create/repair
         → vdd-conformance-exact-cover
         → existing implementation authorization owner
         → implementation
```

Canonical Spec Package 由 `bmad-spec` 最终拥有。已被 Spec fully absorbed 的 PRD、原始输入或旧 requirements 只保留 provenance 身份，不能重新成为与当前 Spec 平级的 downstream normative authority。

## 2. 职责边界

### 2.1 新 Skill 拥有的职责

1. 消费 VDD 已冻结的 source manifest，不能由 caller 用任意路径集合缩减 authority universe。
2. 将自然语言中的每条 obligation 绑定到稳定 ID、原文摘录、来源 hash 和 source pointer。
3. 验证 source obligation 与 requirements/acceptance/disposition 的双向 sound-and-complete cover。
4. 识别遗漏、unknown、重复、语义弱化、冲突和未处置项；不判断 implementation/test/evidence。
5. 生成 compact、hash-bound、`authorizes=[]` 的 conformance/repair artifact。
6. 对无法由确定性规则判定的映射输出 `requirement_semantic_review_required`，并指向 `bootstrap-upstream-plan`；不自动修改目标目录。
7. 为声明采用 canonical flow 的 VDD plan 生成 current、hash-bound 的 `conformant` receipt，供现有 implementation authorization owner 作为准入前置条件验证；receipt 本身仍固定 `authorizes=[]`。

### 2.2 明确不拥有的职责

- 不执行或修改 Bootstrap Review 的 reviewer、packet、capsule、retry 或 child workspace 实现。
- 不把自然语言语义争议直接判为通过；真实语义冲突交给现有 `bootstrap-upstream-plan`。
- 不信任 caller 传入的 coverage/complete/verified 布尔值。
- 不改变 lifecycle ownership、Acceptance 授权或 release/commit 权限。
- 不拥有实现 ref、test definition、current run evidence、风险分级、review rounds 或 legacy migration。
- 不修改 `execution-plans/<target>`；所有修复由 VDD `repair` 执行。

### 2.3 本项目允许的 VDD 最小改动

本需求允许并要求对 `.agents/skills/vdd-execution-plan/**` 做最小必要修改，以提供正式的 source-freeze producer，并让显式 VDD `repair` 消费 `vdd-repair-input.v1`。这些改动只建立 producer/consumer contract：不得把 exact-cover 算法、Bootstrap reviewer/runtime 或 semantic review 实现吸收到 VDD 内。

VDD 仍是 execution-plan create/repair、`plan-ready` 和 plan lifecycle owner；exact-cover 不执行 VDD repair，也不发布任何 lifecycle 状态。

## 3. 权威与输入

### 3.1 Canonical Spec Package

新流程下，VDD 的主要产品需求 authority 是 `bmad-spec` 输出的 Canonical Spec Package。Package 至少区分：

| 角色 | 语义 |
| --- | --- |
| `canonical` | 当前 canonical `SPEC.md` |
| `normative_companion` | bmad-spec 编写且仍具规范性的 companion |
| `adopted_companion` | bmad-spec adopt 的规范性 companion，例如 `ARCHITECTURE-SPINE.md` |
| `provenance` | 已被 Spec fully absorbed 的 PRD、原始输入或历史来源，只用于追溯 |
| `repository_authority` | 当前适用的 AGENTS、Accepted ADR、标准与知识绑定 |
| `unresolved_input` | typed、可追踪的 assumption/open question；不得静默视为已解决 |

Exact-cover 不重新解释 PRD、Architecture、旧 requirements 或 companions 谁是 authority，只消费 VDD 冻结的 authority graph。Caller 不得把 normative companion 降级为 provenance、从 source universe 删除，或把 provenance 提升为与 canonical Spec 平级的规范来源。

Obligation extraction universe 只包含 `canonical`、`normative_companion`、`adopted_companion` 以及对当前目标适用的 `repository_authority`。`provenance` 只校验路径、hash 和 package relationship，不重新提取 normative obligation。`unresolved_input` 必须保持 typed 并映射到明确的 unresolved requirement/disposition；在 owner 解决或作出具名 defer/not-applicable 决定前，不得被投影成已解决的 active requirement 或静默通过 conformant。

### 3.2 VDD source-freeze manifest prerequisite

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

`vdd-source-freeze-manifest.v1` 是本需求的概念合同名；最终文件名遵循仓库既有命名规范。若当前 VDD production 尚未提供一等 source-freeze artifact，本项目必须增加最小 producer 能力。Manifest 至少包含：

- schema/version、VDD run identity、target identity 和 canonical package root；
- 每个 source/companion 的 repository-relative path、role、精确 byte SHA-256 和 package/source relationship；
- applicable repository rules、knowledge bindings、unresolved input；
- manifest 自身 canonical hash 和固定 `authorizes=[]`。

VDD plan construction 与 exact-cover 必须绑定并重验同一个 frozen source manifest identity/hash。Caller 不得为 exact-cover 重新提交任意缩减的 source list。Manifest 缺失、schema unknown、hash drift、role drift、normative source omission 或 construction/conformance manifest identity 不一致均 fail closed。

### 3.3 Implementation prerequisite，而非授权

`conformant` 不等于 `implementation-authorized`。对于声明采用 canonical flow 的 VDD plan，在进入 implementation authorization 前，现有 authorization owner 必须验证 current、hash-bound、同时匹配当前 VDD source manifest、requirements manifest 和 validator identity 的 conformant receipt。

Exact-cover 自身不得发布 `plan-ready`、`implementation-authorized`、`implementation-complete` 或 `acceptance-passed`。Missing、stale 或 non-conformant receipt 不得由 prose、人工布尔值、旧 review summary 或 assistant 声明替代。本需求不重新定义 maintainer 或其他现有 authorization owner，只规定其 prerequisite 消费关系。

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

### 5.1 Adaptive Semantic Stabilization

Exact-cover 采用 deterministic-first 的自适应语义稳定化原则，不固定执行一串昂贵 LLM review。默认顺序必须是：

```text
cheap deterministic validation
→ obligation extraction only when needed
→ deterministic canonicalization
→ deterministic exact-cover
→ semantic review only for unresolved semantic ambiguity
```

Schema、hash、path、ID、set equality、orphan、duplicate 和 disposition 等机器可判定问题必须先处理。存在 deterministic failure 时，不得通过增加 LLM 次数、timeout、reasoning effort、jitter 或 Bootstrap Review 绕过；semantic capability 只处理机器无法决定的语义问题，并且只保留 `bootstrap-upstream-plan` 这一条显式 semantic exception lane。

### S0. Source freeze and deterministic preflight

读取 VDD source-freeze manifest，验证 manifest/schema/hash/run identity，并在任何 LLM 调用前完成 path、authority role、source/requirements/validator binding、schema 与已存在 ID/ref 的 cheap deterministic checks。任何缺失、不可解码、manifest 漂移、requirements 目录越界或 hard structural gap 都输出 typed diagnostic、recommended action 和 repair input，并停止 semantic escalation。

### S1. Fingerprint and shard planning

在需要 obligation extraction 时，必须区分两级 identity：

- `run_aggregate_fingerprint` 绑定完整 source-freeze manifest hash、requirements manifest hash、validator/code fingerprint、extraction prompt/schema version、relevant policy/profile version 和 authoritative companion set。任一全局输入变化都使 prior aggregate、conformance result 和 receipt stale；
- `shard_reuse_fingerprint` 绑定 current source-freeze manifest 中该 shard 的稳定 identity、精确 source entry path/range/byte hash、role/package relationship、requirements manifest hash、validator/code fingerprint、extraction prompt/schema version 和 relevant policy/profile version。它不得直接以完整 source-freeze manifest hash 作为“全部 shard 必须相等”的复用条件。

大型 Canonical Spec Package 可按稳定 source/obligation boundary 划分 shard；每个 shard artifact 必须显式记录来源 manifest identity、`source_manifest_hash`、精确 source entries、独立 result hash 和 `shard_reuse_fingerprint`。`source_manifest_hash` 只证明该 artifact 的 provenance/custody，并参与 current aggregate 的完整 source binding；它不得作为“其他 unchanged shard 的 reuse fingerprint 必须与旧完整 manifest hash 相等”的条件。只有 current manifest 可逐项证明该 shard 的 source entries、roles、relationships 及其余 shard-level fingerprint 字段完全一致时，才可复用 prior successful extraction。Source content/role/relationship、requirements、validator、extraction schema 或 semantic policy 任一相关变化均使该 shard stale；authoritative companion set 或完整 source manifest 变化始终使 prior aggregate stale，但不自动使经 current manifest 逐项验证为 unchanged 的其他 shard extraction stale。Reuse 只节省计算成本，固定 `authorizes=[]`，不得成为 authorization authority。

### S2. Obligation extraction and instability detection

LLM 只提出 obligation candidates、解释真实语义冲突、提议可证伪 acceptance。候选必须回到逐字摘录和 source pointer；LLM 不能发布 canonical ID 或 PASS。

相同 frozen input 上出现 obligation 数量变化、boundary 漂移、同一 claim 在 active/ignored 间抖动或无法形成 stable mapping 时，分类为 `obligation_extraction_unstable`。此时只允许小规模 bounded jitter/consensus diagnostics，用于定位 hotspot、判断 extraction 稳定性和决定是否请求上游澄清或 semantic review；多数投票不得决定 normative truth、coverage 或 `conformant`。

### S3. Deterministic canonicalization and aggregation

确定性脚本分配稳定 ID、去重、检查 active/disposition 状态，构建 obligation↔requirement↔acceptance 映射，并合并全部 shard result。Shard 状态至少包括 `clean`、`hotspot` 和 `quarantined`：`shard_reuse_fingerprint` 经 current manifest 逐项重验未变化的 clean shard 可复用；只有变化或失败的 hotspot shard 需要重验；quarantined shard 不得从最终 universe 静默排除。无论复用了多少 shard，最终 aggregate 都必须使用 current `run_aggregate_fingerprint` 针对完整 active normative universe 重新计算，并要求其与 requirements/acceptance 双向 sound-and-complete cover。

### S4. Deterministic exact-cover

通过 JSON/schema parsing、set equality、hashing 和 mapping validation 检查：

- active requirement 无遗漏、无未知引用；
- active acceptance 无孤儿、无重复或错绑；
- 每个 active obligation 有 requirement/acceptance mapping；
- source、requirements、validator hash 一致；
- `not_applicable|deferred|conflict` 明确出现在 disposition，不进入 active universe。

### S5. Typed result and semantic handoff

重量级读取和扫描在确定性子进程/脚本中完成。主进程只接收固定上限的摘要、计数、错误 ID、证据路径和 hash；原文 stdout、完整矩阵和源码只落盘到 run evidence，不注入主上下文。结果只能是：`blocked`（确定性缺口）、`conformant`（无语义歧义）或 `requirement_semantic_review_required`（需要既有 Bootstrap requirement review）。

只有 deterministic structure valid、source binding valid、mapping structurally complete，且剩余问题确实是 requirement 是否弱化、表述是否等价、冲突是否真实或 applicability 是否存在机器无法判断的歧义时，结果才可为 `requirement_semantic_review_required`。此时产出完整、hash-bound 的 handoff，固定 profile 为 `bootstrap-upstream-plan`，列出 obligation/requirement IDs、歧义原因、冻结 authority 和 review scope。除非调用方明确授权，不自动启动 Review。

### S6. Failure-family recovery and VDD repair handoff

生成 `vdd-repair-input.v1`，绑定原始 source-freeze、requirements 目录、validator、failure family、affected IDs、typed recommended action 和（如有）Bootstrap validation envelope。Recommendation 必须由 failure family 与 current evidence 确定性派生，只能取版本化 allowlist 中的值；初始 allowlist 至少包含 `repair_manifest|repair_requirements|rerun_changed_shards|retry_transport|semantic_review|inspect_extraction|inspect_validator|restart_from_source_freeze`。Prose 不得覆盖 typed result。该 artifact 始终 `authorizes=[]`，不发布 `plan-ready`，不修改目标目录；VDD 只在用户显式请求 `repair` 时消费它。

## 6. LLM 与确定性边界

| 能力 | 归属 |
| --- | --- |
| 初步抽取 obligation、解释语义冲突 | LLM，非授权 |
| extraction instability 的 bounded jitter diagnostics | LLM，非授权且不决定 PASS |
| source hash、逐字 anchor、稳定 ID | deterministic |
| fingerprint、shard state/reuse、aggregation | deterministic |
| exact-cover、unknown/duplicate/drift 检查 | deterministic |
| failure family 与 recommended action | deterministic |
| mutation/negative fixture | deterministic |
| 语义是否真实冲突 | `bootstrap-upstream-plan`，非本 Skill |
| 是否启动 semantic review | 调用方显式授权；本 Skill 只返回 handoff |
| 实现、测试、current evidence、风险分级 | VDD/Quick Dev/Acceptance/Bootstrap 各自现有 owner |
| 最终 acceptance-passed | 现有 Acceptance 生命周期所有者 |

每次 requirement coverage 不得触发一次 LLM pass。LLM 只用于候选抽取和解释机器无法判断的语义疑义，并必须通过仓库共享 LLM backend、UTF-8 stdin；正常成本应主要是解析、集合运算和哈希。

## 7. 上下文与恢复边界

新 Skill 只控制自身的上下文输入和文件化恢复，不拥有、修改或承诺 Codex 原生 thread resume、context compaction、context window 阈值或 provider 行为。

- 每次运行必须可从 `source_manifest`、`requirements_manifest`、`validator_identity`、`run_aggregate_fingerprint`、current shard states/`shard_reuse_fingerprint` 和落盘 artifact 在新 Codex thread 或无会话进程中重新开始；不得要求 `resume --last` 或依赖旧对话历史。
- 运行开始即写入 compact `run-manifest.v1`，只保存 run/stage、输入路径与 hash、两级 fingerprint、shard identity/state/result hash、artifact 路径与 hash、结果状态、failure family、affected IDs、attempt identity、recommended action 和下一合法动作；不得保存 source 全文、reviewer 正文、工具 stdout 或历史 prompt。
- 中断后只读取 `run-manifest.v1` 和其中指向的当前 artifact。任一 input/validator hash 漂移时必须开始新 run 或 fail closed，不得把旧摘要拼接成当前 authority。
- 主 Agent 不读取完整 source inventory、全部 shard raw output、coverage matrix、reviewer 输出或历史 evidence。完整内容由确定性子进程或隔离的既有 Review Skill读取；主 Agent只接收 schema-valid 的 counts、failure family、affected IDs、路径、hash、verdict、recommended action 和有限 finding IDs。
- `bootstrap-upstream-plan` 的完整 review evidence 保持在其原有 run 目录；新 Skill 只消费当前、hash-bound 的 validation envelope，不复制 reviewer 正文到自己的上下文或 artifact。
- 所有 bounded output 必须有版本化上限、`truncated` 标志和完整 artifact 路径/hash。达到上限时不得静默截断或继续向主上下文追加全文。
- 发现 Codex context-window、transport 或进程中断时，新 Skill 只能保留文件化 checkpoint 并停止；它不得宣称已压缩 Codex thread，也不得通过重复发送相同 prompt 恢复。
- 恢复时只可复用经 current manifest 逐项验证 `shard_reuse_fingerprint` 完全一致的 clean shard；stale、hotspot 或 quarantined shard 必须重验。`run_aggregate_fingerprint` 变化会强制重算 aggregate/receipt，但单个 shard 变化不要求其他已验证 unchanged 的 clean shard重新进入 LLM。

## 7.1 两类 Semantic Review 的生命周期边界

### A. Pre-implementation requirement semantic ambiguity

```text
exact-cover → requirement_semantic_review_required
            → explicit authorization
            → Bootstrap bootstrap-upstream-plan
            → validation envelope
            → explicit VDD repair
            → exact-cover rerun
```

该 review 只判断 source obligation、VDD requirement、acceptance/disposition，以及是否存在语义弱化、错误合并、真实冲突或 applicability ambiguity。它不需要 implementation candidate，不通过 Refactor Acceptance 发起，也不审查 production code、tests 或 runtime evidence。

### B. Post-implementation semantic assurance

```text
implementation-complete
  → Refactor Acceptance
  → decide-bootstrap
  → Bootstrap implementation/focused profile
```

该 review 判断实现风险、runtime closure、changed production code、tests/evidence。它不是 requirement conformance 的替代，也不能消费 pre-implementation 的 `requirement_semantic_review_required` 作为实现审查授权。

两者必须使用不同的 typed route/result 字段和生命周期身份，不得退化为共享的通用 semantic-review 布尔值。Exact-cover 只能声明 deterministic proof 无法闭合；其 handoff 仍为 `authorizes=[]`，实际 Bootstrap launch 继续受 Bootstrap 自身 policy、authorization、模型路由和高成本 acknowledgement 控制。

## 8. Fail-closed 与 stop-loss

### 8.1 Typed failure taxonomy

顶层结果保持 `blocked|conformant|requirement_semantic_review_required`，但每个 blocked/diagnostic 必须有由确定性规则优先分类的稳定 failure family。最小 taxonomy 为：`manifest_invalid`、`source_drift`、`authority_role_drift`、`schema_error`、`deterministic_coverage_gap`、`obligation_extraction_invalid`、`obligation_extraction_unstable`、`semantic_ambiguity`、`semantic_conflict`、`timeout`、`transport_failure`、`validator_failure` 和 `artifact_integrity_failure`。无法通过 extraction output schema/parser 的 malformed model output 必须确定性分类为 `obligation_extraction_invalid`，raw exception/message 只能作为 detail，不能替代 family；不得把所有失败折叠成 generic LLM failure。Downstream recovery 必须根据 family 和 current evidence 派生 typed recommended action。

### 8.2 Retry and stop-loss policy

Missing normative source、manifest mismatch、hash/role drift、source/requirements schema failure、unknown ID、orphan acceptance、hard uncovered obligation、invalid disposition 和 deterministic set mismatch 默认不可通过重复 LLM 调用解决，必须直接产生结构化 repair input。只有 `timeout`、`transport_failure`、分类为 `obligation_extraction_invalid` 的 malformed model output 和明确的 `obligation_extraction_unstable` 可进入 bounded retry；malformed output 的每次失败必须计入同一 family 的 attempt/stop-loss，未达到上限时使用 `rerun_changed_shards` recommended action，达到上限后必须改为 `inspect_extraction`、转为 blocked 且停止模型调用。

每个可重试 family 必须定义最大 attempt 数、唯一 attempt identity 和固定或收缩的上下文边界；连续同 family 达到阈值后必须 stop-loss。Retry 不得无限扩大 context、提高 timeout 来掩盖 coverage failure，或将 transport/timeout 结果解释为 coverage PASS。相同 deterministic failure 禁止原样“再试一次”。

以下任一条件成立，结果不得为 `conformant`，且 `authorizes=[]`：

- source manifest、requirements 或 validator hash 缺失/漂移；
- active obligation/requirement/acceptance 有遗漏、孤儿、重复、unknown ref 或错绑；
- disposition 缺失、冲突未处置或 applicability ambiguous；
- 确定性扫描输出超预算、schema error 或 `hard_uncovered`；
- 路径越界、绝对路径、`..` 或 custody-path substitution。

明确的需求语义疑义不得伪造 `blocked` 或 `conformant`，必须输出 `requirement_semantic_review_required`。存在 deterministic failure 时必须优先 `blocked`，不得进入 Bootstrap；timeout 或 transport failure 也不得覆盖已知 coverage failure。旧 evidence 追加保留，不覆盖历史文件。新 Skill 不修改 requirements 目录。

## 9. 负例与组合验收

必须提供真实 producer→consumer composition，而不是只测 mocks，至少覆盖：

1. missing obligation、unknown requirement、orphan acceptance；
2. requirement→acceptance 错绑、duplicate legitimate consumers；
3. requirement 语义弱化、合法合并、unknown ref 和冲突未处置；
4. source/requirements/validator hash 漂移；
5. typed disposition 正确排除 active universe；
6. 需求语义歧义只输出 `requirement_semantic_review_required`，不伪造 PASS；
7. 旧或篡改的 Bootstrap validation envelope 被拒绝；
8. 新 Skill 执行期间 requirements 目录字节不变；
9. 中断后在新 thread/进程中仅凭 compact run manifest 和 hash-bound artifacts 可重启；
10. resume fixture 证明 source 全文、reviewer 正文、工具 stdout 和历史 prompt 未进入主 Agent；
11. bounded summary 超限时设置 `truncated=true` 并指向完整 artifact，不把全文追加到上下文。
12. bmad-spec Canonical Spec Package → VDD source-freeze producer，且 canonical、normative、adopted、provenance 和 unresolved roles 完整保留；
13. VDD create/repair 与 exact-cover 消费同一 manifest identity/hash；manifest A/B 不一致必须阻断；
14. 删除 normative companion 或将其错标为 provenance 必须阻断；provenance 不得被重新提升为平级规范 authority；
15. `vdd-repair-input.v1` → real VDD repair consumer，repair 后重新生成或绑定新的 applicable requirements identity 并重跑 exact-cover；
16. 旧 conformant receipt 在 source、requirements、validator、role graph 或 manifest identity 任一变化后变为 stale；
17. implementation authorization owner 的真实入口拒绝 missing、stale、non-conformant 或人工布尔值替代的 receipt，并接受匹配当前 bindings 的 receipt，但仍由原 owner 发布授权状态。
18. 存在 hard uncovered obligation 时，即使 semantic LLM 连续返回 PASS 也必须 `blocked`；manifest mismatch 时不得启动 semantic review；
19. Timeout/transport 可按 family bounded retry，但达到最大 attempt 必须 stop-loss；schema/hash/coverage deterministic failure 不得因提高 timeout 或 reasoning effort 重试；
20. Current manifest 逐项证明 `shard_reuse_fingerprint` 一致时可复用 prior successful extraction；全局输入变化使 aggregate/receipt stale，相关 shard 输入变化只使 affected shard stale；
21. 100 个 source shard 中只改变 1 个时，仅受影响 shard 重新 extraction，但 deterministic aggregate 必须针对全部 current shards 重算；
22. 存在 quarantined shard 时不得产生 `conformant`，也不得从 active normative universe 删除该 shard；
23. 相同 frozen input 的 extraction 结果明显漂移时必须产生 instability/hotspot；2/3 majority PASS 不得覆盖缺失的 deterministic mapping；
24. Deterministic proof 完整且无 semantic ambiguity 时不得调用 Bootstrap；只有真正 semantic ambiguity 才可产生 `requirement_semantic_review_required`；
25. 每个 failure family 必须映射稳定 typed recommended action，prose、caller boolean 或 LLM 建议不得覆盖映射；
26. 新进程恢复可复用 fingerprint 未变化的 clean shard，但 stale/hotspot/quarantined shard 必须重验。

组合链至少包括：

```text
 VDD source-freeze → exact-cover producer → (optional) bootstrap-upstream-plan
 semantic result → vdd-repair-input.v1 → explicit VDD repair
```

完整链路至少包括：

```text
bmad-spec Canonical Spec Package
  → VDD source-freeze producer
  → same manifest → VDD create/repair
  → same manifest → exact-cover
  → current conformant receipt
  → existing implementation authorization owner
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

Chapter 5 只作为 execution-governance inspiration，不是 runtime dependency。不得引入 Taskmaster triplet、`tasks_back`/`tasks_gameplay`、游戏领域 taxonomy、Chapter 5 script names、独立于 VDD source-freeze 的第二套 source discovery、自动 semantic baseline promotion、自动 Bootstrap invocation，或 `extract → align → coverage → semantic_gate → refs` 多层 LLM reviewer 链；不得基于多数投票直接宣布 requirement correctness。

## 11. Legacy 与迁移

Legacy compatibility remains owned by VDD and its documented adapters. This Skill reads only a valid VDD source-freeze manifest; unknown manifest/schema versions fail closed. It does not migrate or rewrite legacy plans.

## 11.1 稳定 Requirement Contract

以下 ID 是本需求的稳定引用。后续修订可以补充或 supersede，不能重编号或复用。详细语义仍以所指章节全文为准；本表不得被用来缩减章节中的 load-bearing 内容。

| Requirement ID | Normative requirement | Owning section | Acceptance IDs |
| --- | --- | --- | --- |
| `VCEC-001` | 输入 authority 必须是 bmad-spec 拥有的 Canonical Spec Package authority graph。 | §3.1 | `VCEC-A01`, `VCEC-A02` |
| `VCEC-002` | Canonical、normative、adopted、provenance、repository authority 与 unresolved input roles 必须保持 typed 且不可由 caller 降级、提升或删除。 | §3.1 | `VCEC-A02`, `VCEC-A03` |
| `VCEC-003` | VDD 必须产生版本化、一等、hash-bound、`authorizes=[]` 的 source-freeze manifest。 | §2.3, §3.2 | `VCEC-A04` |
| `VCEC-004` | VDD construction 与 exact-cover 必须消费并重验同一 manifest identity/hash。 | §3.2 | `VCEC-A05` |
| `VCEC-005` | Source-freeze 缺失、unknown schema、hash/role drift、normative omission 或 caller 缩减 source universe 必须 fail closed。 | §3.2, §8 | `VCEC-A06` |
| `VCEC-006` | 每条 source obligation 必须绑定稳定 ID、逐字 anchor、source pointer 和 source hash。 | §2.1, §4.1 | `VCEC-A07` |
| `VCEC-007` | Active obligation、requirement、acceptance 必须形成双向 sound-and-complete cover。 | §4.2, §4.3, §5 S3-S4 | `VCEC-A08` |
| `VCEC-008` | Not-applicable、deferred 和 conflict 必须有 typed disposition、reason、authority reference 与 target plan。 | §4.1, §5 S3-S4 | `VCEC-A09` |
| `VCEC-009` | Unknown、duplicate、orphan、错绑、语义弱化、未处置冲突和 silent omission 不得产生 conformant。 | §4.3, §8 | `VCEC-A10` |
| `VCEC-010` | LLM 只能提出 candidates 或解释歧义；canonical ID、hash、cover 与 PASS 由确定性 producer/validator 决定。 | §5 S2-S4, §6 | `VCEC-A11` |
| `VCEC-011` | Exact-cover 结果只能是 typed blocked、conformant 或 requirement semantic-review handoff，并提供 bounded、hash-bound evidence。 | §5 S5 | `VCEC-A12` |
| `VCEC-012` | Pre-implementation requirement semantic ambiguity 只能显式路由到 Bootstrap `bootstrap-upstream-plan`，并在 validation 后回到显式 VDD repair 与 exact-cover rerun。 | §5 S5-S6, §7.1A | `VCEC-A13` |
| `VCEC-013` | Pre-implementation requirement review 与 post-implementation semantic assurance 必须使用不同生命周期身份和 typed route/result。 | §7.1 | `VCEC-A14` |
| `VCEC-014` | `vdd-repair-input.v1` 必须 hash-bound、schema-valid、`authorizes=[]`，且只能由显式 VDD repair 消费。 | §5 S6, §2.3 | `VCEC-A15` |
| `VCEC-015` | VDD repair 必须产生或绑定新的 applicable requirements identity，并使旧 conformant receipt stale 后重跑 exact-cover。 | §9 | `VCEC-A16` |
| `VCEC-016` | Current conformant receipt 是 canonical-flow implementation authorization 的必要前置证据，但不拥有任何 lifecycle authority。 | §3.3 | `VCEC-A17` |
| `VCEC-017` | Existing authorization owner 必须拒绝 missing、stale、non-conformant 或非当前 binding 的 receipt，且不得接受 prose/boolean/旧 summary 替代。 | §3.3, §9 | `VCEC-A18` |
| `VCEC-018` | Exact-cover 和所有中间 artifact 固定 `authorizes=[]`，不得发布 plan-ready、implementation-authorized、implementation-complete 或 acceptance-passed。 | §2, §3.3, §12 | `VCEC-A19` |
| `VCEC-019` | VDD 修改仅限 source-freeze producer 与 repair-input consumer contract；不得吸收 exact-cover 或 Bootstrap implementation。 | §2.3 | `VCEC-A20` |
| `VCEC-020` | Exact-cover 不修改 target execution-plan；VDD 保持 create/repair 和 plan lifecycle owner。 | §2.2, §5 S6 | `VCEC-A21` |
| `VCEC-021` | 主 Agent 只能接收 bounded summary、路径、hash、verdict、有限 IDs 和 next action；完整 source/matrix/reviewer/stdout/prompt 只落盘。 | §5 S5, §7 | `VCEC-A22` |
| `VCEC-022` | 运行必须可从 compact manifest 和当前 hash-bound artifacts 在新 thread/process 重启，不依赖 Codex resume/compaction 或旧聊天。 | §7 | `VCEC-A23` |
| `VCEC-023` | 输出上限、truncated 标记、完整 artifact ref/hash、重复失败 stop-loss 与 stale restart 必须 fail closed。 | §7, §8 | `VCEC-A24` |
| `VCEC-024` | 实现必须提供真实 producer→consumer composition、mutation/negative fixtures 和至少一个完整 dogfood。 | §9, §12 | `VCEC-A25`, `VCEC-A26` |
| `VCEC-025` | Legacy migration 保持由 VDD 及其 adapter 拥有；Exact-cover 不迁移或改写 legacy plans。 | §11 | `VCEC-A27` |
| `VCEC-026` | Exact-cover 必须 deterministic-first，并仅在 deterministic structure/bindings/mapping 闭合后升级真正的 semantic ambiguity。 | §5.1, §5 S0-S5 | `VCEC-A28`, `VCEC-A29` |
| `VCEC-027` | 所有 blocked/diagnostic 必须具有稳定 typed failure family；raw message 不得替代 family。 | §8.1 | `VCEC-A30` |
| `VCEC-028` | Retry 仅限允许的 transient/instability families，必须 bounded、attempt-bound 并在阈值后 stop-loss。 | §8.2 | `VCEC-A31`, `VCEC-A32`, `VCEC-A42` |
| `VCEC-029` | Reuse 必须绑定 run/aggregate 与 shard 两级 fingerprint；全局 drift 使 aggregate/receipt stale，affected shard drift 使该 shard stale，unchanged shard 仍须由 current manifest 逐项证明后才能复用。 | §5 S1 | `VCEC-A33`, `VCEC-A34` |
| `VCEC-030` | 大型 package 可稳定分 shard；每个 shard artifact 必须绑定 source manifest hash，并区分 clean/hotspot/quarantined；deterministic aggregate 始终覆盖完整 active universe。 | §5 S1-S3 | `VCEC-A35`, `VCEC-A36` |
| `VCEC-031` | 相同 frozen input 的 extraction 漂移必须分类为 obligation extraction instability，并定位 affected hotspot。 | §5 S2 | `VCEC-A37` |
| `VCEC-032` | Bounded jitter/consensus 只能诊断稳定性、hotspot 与 escalation，不得决定 normative truth、coverage 或 PASS。 | §5 S2 | `VCEC-A38` |
| `VCEC-033` | Deterministic failure 不得进入 Bootstrap；仅剩机器不可判定的 requirement ambiguity 才可 semantic escalation。 | §5.1, §5 S5, §8 | `VCEC-A29`, `VCEC-A39` |
| `VCEC-034` | Failure family 必须与 current evidence 确定性映射到 typed recommended action；recommendation 固定 `authorizes=[]`。 | §5 S6, §8.1 | `VCEC-A40` |
| `VCEC-035` | 恢复必须从 manifest、两级 fingerprint 和 current shard states 重建；unchanged clean shard 可复用，stale shard 必须重验，current aggregate 必须重算。 | §7 | `VCEC-A41` |

稳定 non-goal/lifecycle boundary 引用：

| Boundary ID | Boundary |
| --- | --- |
| `VCEC-NG01` | 不创建第二个 review runner、reviewer layer 或 Bootstrap runtime。 |
| `VCEC-NG02` | 不判断 implementation/test/current evidence，不替代 post-implementation Acceptance。 |
| `VCEC-NG03` | 不修改 execution-plan，不执行 VDD repair，不拥有 lifecycle/release/commit authority。 |
| `VCEC-NG04` | 不重新把 fully absorbed PRD、Architecture 或原始输入提升为与 Canonical Spec Package 平级的 downstream authority。 |
| `VCEC-NG05` | 不声明修改 Codex thread resume、compaction、context-window 或 provider 行为。 |
| `VCEC-NG06` | 不把 Chapter 5 的 Taskmaster/Game/PowerShell/script 或多层 LLM reviewer 实现引入新 Skill；Chapter 5 不是 runtime dependency。 |

## 11.2 稳定 Acceptance Contract

| Acceptance ID | Falsifiable acceptance predicate | Covers |
| --- | --- | --- |
| `VCEC-A01` | Canonical Spec Package fixture 可由 VDD producer 接受并冻结唯一 package root；非 bmad-spec package 被拒绝。 | `VCEC-001` |
| `VCEC-A02` | Role graph round-trip 保留全部 normative/adopted/unresolved 项及 relationships；任一缺失导致失败。 | `VCEC-001`, `VCEC-002` |
| `VCEC-A03` | Normative companion 降级为 provenance、provenance 提升为 canonical、从 provenance 重新提取 obligation、caller 删除 normative source 或把 unresolved input 静默标记为 resolved 的 fixtures 均失败。 | `VCEC-002` |
| `VCEC-A04` | Real VDD producer 输出 schema-valid manifest，包含要求字段、canonical hash 和 `authorizes=[]`。 | `VCEC-003` |
| `VCEC-A05` | VDD create/repair 与 exact-cover 使用同一 manifest 时通过 binding gate；manifest A/B 组合必失败。 | `VCEC-004` |
| `VCEC-A06` | Missing/unknown/drift/omission/reduced-universe fixtures 均在读取 requirements 前 fail closed。 | `VCEC-005` |
| `VCEC-A07` | 每个 obligation 的稳定 ID、逐字 inclusive anchor、source pointer/hash 可重算；重复或漂移失败。 | `VCEC-006` |
| `VCEC-A08` | Active obligation、requirement、acceptance 双向集合检查相等，删除任一合法边产生 non-conformant。 | `VCEC-007` |
| `VCEC-A09` | 非 active obligation 只有在完整 disposition 字段存在时排除；缺一字段即失败。 | `VCEC-008` |
| `VCEC-A10` | Missing、unknown、duplicate、orphan、wrong-binding、weakening 和 unresolved-conflict mutation fixtures 均不产生 conformant。 | `VCEC-009` |
| `VCEC-A11` | Caller 或 LLM 传入 canonical IDs、hash 或 pass boolean 不改变确定性重算结果。 | `VCEC-010` |
| `VCEC-A12` | 三种结果均通过 schema；raw/full output 或无证据路径/hash 的结果失败。 | `VCEC-011` |
| `VCEC-A13` | Ambiguous fixture 只产生 requirement-review handoff；未显式授权不启动 Bootstrap，current envelope 后仅生成 VDD repair input。 | `VCEC-012` |
| `VCEC-A14` | Requirement-review artifact 无 implementation candidate 字段；post-implementation route 拒绝把该 handoff 当作 review authorization。 | `VCEC-013` |
| `VCEC-A15` | Real VDD repair entry 接受 current repair input，拒绝 stale/tampered/implicit route，并保持 VDD lifecycle owner。 | `VCEC-014` |
| `VCEC-A16` | Repair 后 requirements identity 改变，旧 receipt 被判 stale，重新 exact-cover 后才产生新 receipt。 | `VCEC-015` |
| `VCEC-A17` | Matching receipt 可满足 authorization preflight，但 receipt 单独不改变 lifecycle state。 | `VCEC-016` |
| `VCEC-A18` | Authorization owner 的真实入口拒绝 missing/stale/non-conformant/mismatched receipt 和 prose/boolean 替代。 | `VCEC-017` |
| `VCEC-A19` | 对所有输出扫描 `authorizes=[]`，且禁止 lifecycle/acceptance/commit/release 发布字段。 | `VCEC-018` |
| `VCEC-A20` | VDD diff 只包含 producer/consumer contract；植入 exact-cover 或 Bootstrap 算法的 fixture/审查失败。 | `VCEC-019` |
| `VCEC-A21` | Exact-cover 前后 requirements directory byte manifest 相同；修复只通过显式 VDD repair 发生。 | `VCEC-020` |
| `VCEC-A22` | Model-visible receipt 不含 source/reviewer/stdout/prompt 全文，且完整 artifacts 保存在受控路径。 | `VCEC-021` |
| `VCEC-A23` | 中断后在新 process/thread 仅凭 compact manifest 和当前 artifacts 重启；不读取旧 rollout/chat。 | `VCEC-022` |
| `VCEC-A24` | 超限设置 `truncated=true` 并绑定完整 artifact；hash drift、原样重试或丢失 artifact 均阻断。 | `VCEC-023` |
| `VCEC-A25` | Composition suites 覆盖 Package→VDD producer→VDD create/repair→exact-cover→authorization preflight 的真实入口。 | `VCEC-024` |
| `VCEC-A26` | 至少一个真实 plan 完成 create→exact-cover→可选 semantic review→repair→rerun dogfood，负例保持不可变。 | `VCEC-024` |
| `VCEC-A27` | Unknown legacy manifest/schema fail closed，且 target legacy plan bytes 不被迁移或改写。 | `VCEC-025` |
| `VCEC-A28` | Hard uncovered obligation 存在时，即使 semantic LLM 连续返回 PASS，结果仍为 blocked；schema/hash/set failure 不启动额外 semantic LLM 或 Bootstrap。 | `VCEC-026` |
| `VCEC-A29` | Manifest mismatch 阻断 semantic review；deterministic proof 完整且无 semantic ambiguity 时 Bootstrap 调用次数为零。 | `VCEC-026`, `VCEC-033` |
| `VCEC-A30` | Taxonomy fixture 为每类 failure 产生稳定 family；generic LLM failure 或仅 raw exception 的结果 schema 失败。 | `VCEC-027` |
| `VCEC-A31` | Timeout/transport fixture 只重试至配置最大 attempt，记录唯一 attempt identities，达到上限后 stop-loss。 | `VCEC-028` |
| `VCEC-A32` | Schema/hash/coverage failure 在提高 timeout、reasoning effort 或重复 LLM 后仍保持零 retry，并直接产生 repair input。 | `VCEC-028` |
| `VCEC-A33` | 每个 shard artifact 显式记录 provenance/custody `source_manifest_hash`；current manifest 逐项验证 shard source entries、roles、relationships 与 shard-level fingerprint 完全相同时可复用 prior successful extraction，且完整 manifest hash 变化本身不使其他 unchanged shard 失去复用资格。 | `VCEC-029`, `VCEC-030` |
| `VCEC-A34` | Source manifest/companion set 任一变化使 prior aggregate/receipt stale；source content/role/relationship、requirements、validator、extraction schema 或 semantic policy 变化使 affected shard stale，而 unchanged shard 只有经 current manifest 逐项重验后才可复用。 | `VCEC-029` |
| `VCEC-A35` | 100 个 source shard 只改变 1 个时，每个 shard artifact 都记录其来源 `source_manifest_hash`，仅受影响 shard 重新 extraction，但 deterministic aggregate 针对当前 manifest 和 100 个 current shard 重算。 | `VCEC-030` |
| `VCEC-A36` | 任一 quarantined shard 存在时不得 conformant，删除或忽略该 shard 的 aggregate 必须失败。 | `VCEC-030` |
| `VCEC-A37` | 相同 frozen input 多次 extraction 的 obligation count/boundary/status 明显漂移时产生 `obligation_extraction_unstable` 和 affected hotspot refs。 | `VCEC-031` |
| `VCEC-A38` | 2/3 extraction 声称 covered 但 deterministic mapping 缺失时结果仍 blocked；majority vote 不生成 conformant receipt。 | `VCEC-032` |
| `VCEC-A39` | 只有 structure、bindings 和 mapping 均有效且剩余问题属于等价、弱化、冲突或 applicability ambiguity 时才产生 requirement-review handoff。 | `VCEC-033` |
| `VCEC-A40` | 每个 failure family 都确定性映射到允许的 typed recommended action；篡改 prose 或 caller suggestion 不改变 action，且 `authorizes=[]`。 | `VCEC-034` |
| `VCEC-A41` | 新进程从 compact manifest 和 shard states 恢复时复用 unchanged clean shard、拒绝 stale shard，并重新计算 current aggregate。 | `VCEC-035` |
| `VCEC-A42` | Malformed extraction output 被分类为 `obligation_extraction_invalid`，每次失败计入唯一 attempt；未达上限时 action 为 `rerun_changed_shards`，达到上限后 stop-loss、停止模型调用并产出 action 为 `inspect_extraction` 的 typed blocked artifact。 | `VCEC-028` |

## 12. 验收标准

本需求实现后的 Skill 只有在以下条件全部成立时才算 `conformance-complete`：

1. 从真实 bmad-spec Canonical Spec Package 产生 VDD source-freeze manifest，并验证 package roles、run/target/validator/schema identity；
2. 对所有 active obligation 生成唯一、可追溯的 requirement/acceptance mapping；
3. missing、unknown、duplicate、错绑、冲突未处置和 hash drift 全部不产生 `conformant`；
4. `not_applicable|deferred|conflict` 均有 reason、authority_reference 和 target_plan；
5. requirement semantic ambiguity 只输出 `requirement_semantic_review_required`，handoff profile 为 `bootstrap-upstream-plan`；
6. 新 Skill 不修改 requirements 目录，所有中间 artifact `authorizes=[]`；
7. `vdd-repair-input.v1` schema-valid、hash-bound、可被显式 VDD `repair` 消费；
8. VDD repair 的真实跨进程 composition 通过，且 VDD 仍独立发布 plan/lifecycle 状态；
9. 缺 source、stale envelope、篡改 artifact、隐式 VDD route 的负例全部 fail closed；
10. 同一 run 可在不恢复旧 Codex thread 的前提下，从 `run-manifest.v1` 和当前 hash-bound artifacts 重启；
11. 主 Agent 的恢复输入只有 bounded summary、路径、hash、verdict、pending IDs 和 next action，不包含完整 source/reviewer/stdout/prompt；
12. Skill 的任何输出均不得声称改变 Codex 原生 resume/compaction，context-window 错误只产生 checkpoint 和停止结果；
13. 至少一个真实 execution-plan 完成 `VDD create → exact-cover → optional semantic review → VDD repair → exact-cover` dogfood。
14. VDD create/repair 与 exact-cover 消费并重验同一个 source-freeze manifest identity/hash；manifest A/B、normative companion omission 和 role downgrade 负例全部阻断；
15. VDD 的真实 producer 提供版本化 source-freeze manifest，真实 repair consumer 接受 current `vdd-repair-input.v1`，且两者均不吸收 exact-cover 或 Bootstrap 实现；
16. Current conformant receipt 可满足现有 implementation authorization owner 的 prerequisite preflight，但 receipt 自身不发布任何 lifecycle 状态；missing、stale、non-conformant 和人工替代均被真实入口拒绝；
17. Pre-implementation requirement review 与 post-implementation semantic assurance 使用不同 typed route/result 和生命周期身份，前者不需要 implementation candidate，也不由 Refactor Acceptance 发起；
18. `VCEC-001` 至 `VCEC-035` 均至少映射一个 `VCEC-Axx`，全部 acceptance 可证伪，且 requirements-only review 确认现有 recovery、bounded context、hash binding、negative fixture 和 dogfood 约束未被弱化；
19. Deterministic-first 顺序被强制，hard gap、manifest mismatch、schema/hash/set failure 不得通过 LLM、timeout 或 Bootstrap 绕过；
20. Failure taxonomy、typed recommended action、bounded retry 和 stop-loss fixtures 全部通过；timeout/transport 不掩盖真实 coverage failure，malformed output 归入 `obligation_extraction_invalid` 并在最大 attempt 后停止；
21. `run_aggregate_fingerprint` 与 `shard_reuse_fingerprint` 共同控制 safe reuse：全局变化强制 aggregate/receipt stale，current manifest 逐项验证 unchanged shard 后才允许复用，且 reuse 永不产生 authorization authority；
22. Shard/hotspot/quarantine 支持大型输入增量重验，但任何 quarantined 或遗漏的 normative shard 均阻断 conformant；
23. Jitter/consensus 只诊断 extraction instability，不能以多数投票发布 coverage PASS；
24. 恢复只把 bounded shard counts/states、family、affected IDs、hashes、artifact refs 和 recommended action 暴露给主 Agent，unchanged clean shard 可复用且 stale shard 强制重验；
25. Chapter 5 的 Taskmaster/Game/PowerShell/script、多层 LLM reviewer、第二套 source discovery、自动 baseline promotion 和自动 Bootstrap invocation 均未成为实现依赖。

## 13. 最终语义

```text
Canonical Spec Package
owner: bmad-spec
        ↓
VDD source-freeze producer
        ↓
vdd-source-freeze-manifest.v1
        ↓
VDD create / repair
        ↓
Exact-cover deterministic preflight
        ├─ deterministic failure → typed family/action
        │                            ↓
        │                  VDD/source-freeze repair
        │
        ↓
run aggregate fingerprint + shard reuse fingerprints
        ↓
obligation extraction shards
        ├─ unchanged clean → safe reuse
        ├─ unstable → bounded jitter diagnostics → hotspot/quarantine
        └─ stable/changed → deterministic canonicalization
                                  ↓
                        deterministic exact-cover
                                  ├─ blocked → typed repair → rerun
                                  ├─ requirement_semantic_review_required
                                  │     ↓ explicit authorization
                                  │ Bootstrap bootstrap-upstream-plan
                                  │     ↓ validation envelope
                                  │ VDD repair → exact-cover rerun
                                  └─ conformant + authorizes=[]
                                        ↓
                                prerequisite satisfied
                                        ↓
                                existing implementation
                                authorization owner
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
>
> VDD construction 与 exact-cover 必须验证同一个 source-freeze manifest identity/hash。
>
> Requirement semantic review 与 post-implementation semantic assurance 属于不同生命周期，不共享模糊路由状态。
>
> Chapter 5 的价值仅在于治理不稳定 semantic computation；Exact-cover authority 始终来自 frozen source universe 与 deterministic proof。
>
> Jitter、consensus、reuse 和 recommended action 均不拥有 PASS 或 lifecycle authority。

## Recovery Metadata Supplement (2026-09-30)

Added for recovery-document schema completeness. Original source text,
authority notices, paused states, non-goals, and evidence remain unchanged.
These fields are source locators, not a new implementation status or approval.

- Branch: n/a - the original source did not capture an authoring branch
- Git Head: n/a - the original source did not capture an authoring commit; no historical binding is inferred
- Current step: Source-document recovery only; this supplement does not assert current implementation or lifecycle state.
- Last completed step: The original source document was recorded; implementation progress is owned by separate consumer evidence.
- Stop-loss: Preserve original authority and non-goals; do not infer acceptance, activate a paused plan, or rewrite historical evidence.
- Next action: Consult the conformance requirements and their authorized consumer; do not treat a conformance artifact as implementation or release authorization.
- Recovery command: py -3 -c "from pathlib import Path; print(Path('execution-plans/2026-08-10-vdd-conformance-exact-cover-requirements.md').read_text(encoding='utf-8'))"
- Open questions: Consult the original body and its authority notice for unresolved decisions; this supplement resolves none.
- Exit criteria: The original requirements and acceptance conditions remain unchanged; any completion claim requires separate current consumer evidence.
- Related ADRs: n/a - no explicit Accepted ADR binding is added by this source metadata supplement
- Related decision logs: n/a - no decision-log binding was captured in the original source metadata
- Related task id(s): n/a - this source document does not bind a stable implementation task identifier
- Related run id: n/a - this source document does not bind a canonical current execution run
- Related latest.json: n/a - this source document does not bind a canonical current latest.json pointer
- Related pipeline artifacts: n/a - this supplement produces no implementation or acceptance artifacts; retain any original evidence references in the body
