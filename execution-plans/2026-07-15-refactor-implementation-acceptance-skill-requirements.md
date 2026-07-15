# 重构实施验收 Skill 需求规格

- Title: `run-refactor-implementation-acceptance` Skill 需求规格
- Status: draft
- Branch: 当前工作树
- Git Head: 9e20de9
- Goal: 定义一个以验收条款为单位、按阶段顺序判断重构实施完成度的只读 Skill
- Scope: Skill 的触发、输入、验收矩阵、阶段门禁、DoD 层级、输出和验证场景
- Current step: 最新反馈修订完成，等待实施确认
- Last completed step: 已补齐正向完整性证明、Bootstrap finding映射、适用性不变量、逐check证据要求、内容manifest和DoD结果词汇
- Stop-loss: 本文件不创建或修改 Skill，不修改被验收重构目录，不执行 Bootstrap reviewer
- Next action: 用户确认修订版后，使用 `skill-creator` 创建 Skill
- Recovery command: `py -3 -c "from pathlib import Path; print(Path(r'execution-plans/2026-07-15-refactor-implementation-acceptance-skill-requirements.md').read_text(encoding='utf-8'))"`
- Open questions: 见“待确认项”
- Exit criteria: 本文件中的功能需求、状态规则、阶段门禁和负例成为后续 Skill 创建的对照基准
- Related ADRs: `n/a`，本轮不改变产品架构或运行时合同
- Related decision logs: n/a - 尚未创建独立决策日志
- Related task id(s): `n/a`，本轮没有 Taskmaster 任务
- Related run id: `refactor-acceptance-spec-20260715-225249` - incomplete 且已因目标 hash 变化而 stale 的 supplemental Bootstrap review
- Related latest.json: n/a - 本轮不产生运行结果
- Related pipeline artifacts: `logs/ci/2026-07-15/review-gateway-bootstrap-refactor-acceptance-spec-20260715-225249/review-input.json` - 仅用于追溯首次反馈，不构成当前版本审查权威

## 1. 目的

创建一个新的 `run-refactor-implementation-acceptance` Skill，用于检查 `execution-plans/` 下指定重构目录的真实实现情况。

该 Skill 必须回答：

1. 计划中的每一条验收要求是否有实现、测试和当前运行证据。
2. 当前允许声明 First-slice DoD、Phase exit DoD 还是 Program DoD。
3. 哪些要求是部分实现、缺失、延期、不适用或被前置条件阻断。
4. 当前最早或并列最早未通过的阶段是什么，以及下一步应补什么。

核心原则：

```text
验收条款优先，而不是文档优先
完整矩阵优先，而不是 finding 数量优先
当前可执行证据优先，而不是计划状态或历史总结优先
```

## 2. 与现有 Skill 的职责边界

### 2.1 新 Skill

`run-refactor-implementation-acceptance` 负责：

- 枚举全部适用验收条款；
- 建立并校验实施验收矩阵；
- 绑定代码、测试和 `logs/` 证据；
- 按计划声明的阶段顺序执行验收；
- 计算 First-slice、Phase exit 和 Program DoD 候选结论；
- 输出缺口、阻断阶段和精确复查条件。

它采用 acceptance-first 工作方式，不以“发现了多少问题”推断完成度。

### 2.2 现有 Bootstrap Review

`run-phase-bootstrap-review` 保持现有职责：

- Blind Hunter 检查真实行为缺陷、隐藏耦合和架构漂移；
- Edge Case Hunter 检查边界、状态转换、恢复、并发和幂等路径；
- Acceptance Auditor 审计验收矩阵是否漏项、误分类或引用无效证据；
- gateway 对 findings 做事实门禁，必要时由独立 verifier 核验 P0/P1。

Bootstrap Review 不负责创建实施验收矩阵。Bootstrap `clean` 也不能单独授权 Program DoD。

### 2.3 最终授权关系

```text
实施验收 Skill 的完整矩阵与阶段门禁通过
  + Bootstrap Review 无目标 finding_policy 规定的未解决阻断项
  + 计划自身要求的外部或 protected authority 通过
  = 才能声明相应 DoD 层级
```

新 Skill 不得冒充 `BH-HANDOFF`、发布门禁或计划声明的其他独立权威。

## 3. 触发与目标解析

以下请求应触发新 Skill：

- “验收 7-07 重构的实现情况”；
- “检查这个 execution-plan 是否真正实现完成”；
- “建立实施验收矩阵”；
- “判断 First-slice、Phase exit 或 Program DoD”；
- “按阶段核验重构实现”。

目标解析规则：

1. 用户明确给出目录时，以该目录为目标。
2. 用户使用仓库约定别名时，可以映射到唯一已知目录。
3. 目录不存在或名称匹配多个目标时，失败关闭并请求明确路径。
4. 不允许只抽样目标目录中的部分文档。
5. 若原始单体计划是 98/99 或来源覆盖的权威，必须同时纳入。

## 4. 运行输入与权威

### 4.1 验收 run 输入合同

每次验收必须先冻结一个机器可读 run input，至少包含：

| 字段 | 含义 |
| --- | --- |
| `run_id` | 当前run的唯一标识 |
| `created_utc` | run input冻结时间 |
| `change_id` | 跨run稳定的变更标识 |
| `repository_root_identity` | 仓库根路径、仓库身份和必要的remote/repository fingerprint |
| `target_plan_paths` | 本次验收的计划目录、单体计划和必要外部权威路径集合 |
| `baseline_revision` | 重构开始前或上一已接受状态 |
| `candidate_revision` | 当前候选commit；dirty模式可与HEAD相同 |
| `candidate_mode` | `commit\|dirty_worktree\|proposed_commit_set` |
| `predecessor_run_id` | 前序run；首个run为`null` |
| `execution_mode` | `evidence_only\|controlled_validation` |
| `allowed_write_roots`、`forbidden_write_roots` | 当前run的显式写边界 |
| `baseline_content_manifest_path` | 可展开审计的baseline内容manifest路径 |
| `baseline_content_manifest_hash` | baseline内容manifest自身的hash |
| `candidate_content_manifest_path` | 可展开审计的candidate内容manifest路径 |
| `candidate_content_manifest_hash` | 候选全部受审内容的manifest hash |
| `changed_paths` | baseline到candidate的完整变化路径 |
| `affected_consumer_refs` | 受影响调用方、route、API、脚本和文档消费者 |
| `target_plan_hash` | 目标重构计划及必要原始权威的组合hash |
| `validator_hash` | 本次确定性验证器及规则版本hash |
| `adapter_id`、`adapter_version`、`adapter_hash` | 计划解析适配器身份 |

`baseline-content-manifest.json`和`candidate-content-manifest.json`都是run input的必备可展开工件，至少包含：

```json
{
  "schemaVersion": "acceptance-content-manifest.v1",
  "revision": "...",
  "files": [
    {
      "path": "...",
      "sha256": "sha256:...",
      "classification": "changed|consumer|authority|test|evidence",
      "inclusionReason": "..."
    }
  ]
}
```

manifest hash必须对规范化后的完整manifest内容计算，不能只对路径列表或Git revision计算。`dirty_worktree`和`proposed_commit_set`必须绑定每个文件的相对路径、内容hash、分类和纳入原因；仅记录HEAD无效。任何候选文件、计划权威、adapter或validator变化都会使旧结果stale。

Phase 0B或其他按需能力是否被触及，必须依据baseline到candidate diff、当前phase/slice声明和route/capability dependency map共同计算，不能只扫描当前目录或依赖关键词猜测。

缺少可信baseline或candidate manifest时可以运行evidence-only盘点，但不得产生实施验收授权。

### 4.2 输入权威顺序

对每个目标目录，按以下顺序建立验收来源清单：

1. `AGENTS.md` 和目标目录内更具体的仓库规则。
2. `00-index.md` 的状态、权威、命令与执行顺序。
3. `01-*` 至 `07-*` 中的局部 acceptance criteria 和执行合同。
4. `08-implementation-phases.md` 或等价阶段权威。
5. `09-*` 中的风险、DoD、完成层级和全局退出条件。
6. `10-*` 或等价 first-slice 文档。
7. `97-*` 新增要求台账。
8. `98-*`、`99-*` 及原始计划的来源覆盖与语义保全结果。
9. 计划已有的 `100-*` 实施验收矩阵及机器工件。
10. 计划 schemas、fixtures、validators 和 tests。
11. 实际生产代码、受影响消费者和自动化测试。
12. `logs/` 下当前 smoke、readback、运行、评审和阶段退出证据。

已有矩阵只能作为输入和历史候选状态。新 run 必须依据当前代码、测试结果、证据 hash 和计划权威重新判定，不能直接继承旧 `verified`。

若权威文件之间冲突，Skill 必须记录冲突并将相关行设为 `blocked`，不得自行选择更方便的解释。

## 5. 验收条款普查

Skill 必须先建立验收条款清单，再检查实现。条款来源至少包括：

- 阶段 deliverables；
- 阶段 exit criteria；
- `01-*` 至 `07-*` 的局部 acceptance criteria；
- `97-*` 中适用于当前或最终 Program DoD 的新增要求；
- 计划 schemas/registries 中声明的能力、状态或 gate；
- `09-*` 中 First-slice、Phase exit 和 Program DoD 条款；
- 计划明确引用且对实现具有约束力的标准和 ADR。

### 5.1 抽取模式

同一目标计划可以同时包含registry、结构化阶段文档和自然语言外部权威。source inventory必须按来源类别划分为一个或多个partition，每个partition独立声明以下一种模式：

| 模式 | 条件 | 允许的完整度声明 |
| --- | --- | --- |
| `registry_backed` | 计划已有稳定requirement/check registry | 确定性验证后可为`deterministic_complete` |
| `parser_backed` | 计划符合已注册adapter，且parser具有正反fixture | 仅对adapter声明覆盖的条款类型可为`deterministic_complete` |
| `semantic_candidate` | 只能从通用自然语言Markdown抽取 | 本地validator只能给出`candidate`；正向语义审计后可为`semantically_attested_complete` |

source inventory至少记录：

```json
{
  "schemaVersion": "acceptance-source-inventory.v1",
  "partitions": [
    {
      "partition_id": "split-added-registry",
      "source_class": "requirement_registry",
      "source_refs": ["..."],
      "extraction_mode": "registry_backed",
      "completeness": "deterministic_complete",
      "extractor_id": "...",
      "extractor_version": "...",
      "extractor_hash": "sha256:..."
    },
    {
      "partition_id": "referenced-adrs",
      "source_class": "external_authority",
      "source_refs": ["..."],
      "extraction_mode": "semantic_candidate",
      "completeness": "candidate",
      "extractor_id": "...",
      "extractor_version": "...",
      "extractor_hash": "sha256:..."
    }
  ],
  "overallCompleteness": "candidate"
}
```

完整度词汇只允许：

- `deterministic_complete`：registry或已注册parser在其声明覆盖范围内通过确定性完整性验证；
- `semantically_attested_complete`：语义来源已由当前hash绑定的Acceptance Auditor提供正向完整性证明，但不冒充确定性证明；
- `candidate`：已经抽取，但尚未满足相应完整性授权合同；
- `incomplete`：存在已知漏项、冲突、重复、无法原子化或缺失来源。

`overallCompleteness`由所有partition按最弱结果计算；任何`incomplete`使整体为`incomplete`，任何未完成审计的`candidate`使整体最多为`candidate`。阶段授权只检查该阶段`consumed_partition_ids`实际消费的partitions，不能因无关partition仍为candidate而阻断，也不能用一个complete partition覆盖另一个candidate partition。

`semantic_candidate`不得仅凭reviewer已读完文件或findings为空提升完整度。Bootstrap Acceptance Auditor必须在不修改现有`bootstrap-reviewer-output.v1`、`review-finding.v1`和`review-result.v1`的前提下，额外产生版本化companion sidecar：

```json
{
  "schemaVersion": "acceptance-inventory-audit-attestation.v1",
  "reviewId": "...",
  "reviewInputHash": "sha256:...",
  "inventoryPath": "acceptance-source-inventory.json",
  "inventoryHash": "sha256:...",
  "matrixPath": "implementation-acceptance-matrix.json",
  "matrixHash": "sha256:...",
  "partitionAttestations": [
    {
      "partitionId": "referenced-adrs",
      "sourceClauseCount": 120,
      "mappedClauseCount": 120,
      "atomicCheckCount": 147,
      "unmappedClauseIds": [],
      "duplicateCheckIds": [],
      "atomizationConflicts": [],
      "verdict": "semantically_attested_complete"
    }
  ],
  "verdict": "semantically_attested_complete"
}
```

该sidecar由Acceptance Auditor审计步骤写入、由Bootstrap gateway按独立schema校验，并与finalized review result一起导入；不得把字段塞入`additionalProperties: false`的现有v1 reviewer或finding对象。只有review已finalized、required layers完成、全部hash与当前run一致、计数闭合且`unmappedClauseIds`、`duplicateCheckIds`和`atomizationConflicts`均为空时，finalize才能把对应partition从`candidate`提升为`semantically_attested_complete`。sidecar缺失、stale或结论为`incomplete`时不得授权。

### 5.2 原子化与稳定身份

一个原子、可独立判定的验收义务对应一个稳定 `check_id`：

- 一个复合条款可以拆成多个checks；
- 多个等价来源可以合并到同一check；
- 纯换行、排序或行号变化不得生成新ID；
- 语义变化必须使旧check或证据stale，不能静默复用；
- 每个check记录稳定`source_clause_ids`、可选`parent_clause_id`和`atomic_index`。

来源定位使用结构化集合，而不是单一字符串：

```json
{
  "canonical_source_ref": "CLAUSE-001",
  "source_refs": [
    {
      "path": "execution-plans/.../08-implementation-phases.md",
      "section_anchor": "phase-1-exit-criteria",
      "start_line": 10,
      "end_line": 12,
      "source_hash": "sha256:..."
    }
  ]
}
```

行号只用于当前快照定位，不作为稳定身份。无法原子化、无法建立稳定身份或存在来源冲突时，inventory必须保持`candidate`或`incomplete`。

## 6. 实施验收矩阵

### 6.1 通用矩阵行

机器矩阵每一行必须包含：

| 字段 | 含义 |
| --- | --- |
| `check_id` | 原子验收义务的稳定编号 |
| `source_clause_ids` | 一个或多个稳定来源条款ID |
| `canonical_source_ref`、`source_refs` | 当前权威和全部hash-bound来源定位 |
| `requirement` | 单一、可观察、可独立判定的要求摘要 |
| `phase_id` | 计划阶段图中的节点ID |
| `requirement_refs` | namespace+ID形式的通用需求引用 |
| `applicability` | 适用性状态、触发谓词和证据ID |
| `implementation_owner` | 负责实现的角色或团队 |
| `verification_owner` | 负责测试和证据判定的角色 |
| `approval_owner` | 负责阶段或外部授权的角色 |
| `implementation_refs` | 实现文件或明确的非代码交付物 |
| `test_definition_refs` | 测试定义、测试用例或validator规则 |
| `test_run_evidence_ids` | 当前候选上的测试运行证据ID |
| `runtime_evidence_ids` | smoke、readback、build或运行证据ID |
| `evidence_requirements` | 当前check必须满足的证据种类、数量、新鲜度和豁免合同 |
| `disposition` | 实施事实分类 |
| `evaluation_state` | 是否已针对当前候选完成评估 |
| `gate_state` | 是否有资格参与阶段授权 |
| `blocking_predecessors` | 阻断该行授权的阶段、gate或finding |
| `finding_refs` | 与该check绑定的当前Bootstrap finding IDs |
| `gap` | 未满足项或特殊分类依据 |

`requirement_refs` 使用通用namespace，例如`requirement`、`capability`、`pbr`、`adr`、`acceptance`或`split_added`。7-07 adapter可以额外渲染`split_added_ids`，但该字段不得成为通用schema的必填项。

7-07现有`source_ref`、`owner`、`code_refs`、`test_refs`、`evidence_refs`、`split_added_ids`和`status`可以作为兼容输入或派生Markdown列；它们不得取代通用机器字段。

`evidence_requirements`必须由条款权威、已批准adapter或显式计划规则生成，不能在评估时由执行者临时决定：

```json
{
  "required_kinds": ["test_run", "readback"],
  "minimum_by_kind": {
    "test_run": 1,
    "readback": 1
  },
  "freshness_policy": "exact_candidate",
  "waiver_allowed": false,
  "source_refs": ["CLAUSE-001"]
}
```

`minimum_by_kind`的键必须是`required_kinds`的子集且值为正整数。`freshness_policy`必须来自版本化词汇，首版至少支持`exact_candidate`、`current_authority`和`same_candidate_environment`。允许豁免时还必须记录`waiver_authority_refs`、`waiver_evidence_ids`和受影响证据kind；不允许用自由文本把required kind改成可选。文档同步、schema、DB migration、UI行为和protected gate应声明各自真实需要的证据，不得统一伪造runtime smoke。

当 `disposition=explicitly_deferred` 时，还必须包含以下条件必填机器字段：

| 字段 | 含义 |
| --- | --- |
| `defer_owner` | 对延期关闭负责的明确角色或团队 |
| `defer_affected_routes` | 受延期影响的 route、能力或消费者列表 |
| `defer_severity` | 延期风险等级 |
| `defer_severity_namespace` | 风险等级词汇命名空间，例如`acceptance-risk.v1` |
| `defer_severity_source_refs` | 风险等级与阻断规则的权威来源 |
| `defer_non_impact_evidence_ids` | 证明当前阶段未受影响的hash-bound证据ID |
| `defer_recheck_trigger` | 到期时间或可执行的重新检查触发条件 |
| `defer_closure_test_definition_refs` | 最终关闭延期时必须执行的测试定义或validator规则 |
| `defer_closure_required_check_ids` | 延期关闭前必须转为`verified`的精确check列表 |

这些字段必须由schema条件必填并分别校验，不得只写进自由文本`gap`。

### 6.2 正交状态模型

`applicability.status`是适用性事实的唯一权威，只允许：

- `applicable`：触发谓词成立；
- `not_applicable`：触发谓词不成立且已有当前证据；
- `undetermined`：缺少决定适用性所需的来源、diff、dependency map或证据。

`applicability`对象至少包含`status`、`activation_predicate`、`authority_refs`和`evidence_ids`。`disposition`表达适用要求的实施事实，或作为`not_applicable`的受约束投影；仅当`applicability.status=undetermined`时允许为`null`：

- `verified`：实现和当前证据全部满足；
- `partial`：存在部分实现或部分证据；
- `missing`：没有满足条款的实现；
- `not_applicable`：触发条件未成立且有可审核证据；
- `explicitly_deferred`：计划允许延期且具备完整延期合同。

schema和validator必须共同执行以下不变量：

```text
applicability.status = applicable
  -> disposition in verified | partial | missing | explicitly_deferred

applicability.status = not_applicable
  -> disposition = not_applicable
  -> evaluation_state = evaluated
  -> applicability.evidence_ids非空

applicability.status = undetermined
  -> disposition = null
  -> evaluation_state in not_evaluated | stale
  -> gate_state = blocked
  -> 不得参与任何授权
```

因此`disposition=not_applicable`只是对唯一适用性事实的受约束投影，不是第二个可独立修改的事实源。任何交叉组合冲突都必须由schema或validator拒绝。

`evaluation_state`只允许：

- `not_evaluated`：尚未针对当前candidate评估；
- `evaluated`：已完成当前candidate评估；
- `stale`：来源、candidate、evidence、adapter或validator变化后失效。

`gate_state`只允许：

- `eligible`：该行具备参与当前阶段授权的资格；
- `blocked`：被前置阶段、外部gate、缺失authority或finding阻断。

因此已实现的后续阶段条目可以同时为：

```json
{
  "disposition": "verified",
  "evaluation_state": "evaluated",
  "gate_state": "blocked",
  "blocking_predecessors": ["Phase 2"]
}
```

兼容视图可以把三组状态投影成旧`status`列，但阶段计算必须读取正交字段。禁止“看起来完成”“基本完成”“大致通过”“可能满足”等状态或等价自由文本。

### 6.3 结构化证据

路径字符串不能独立证明证据有效。每条证据使用稳定`evidence_id`并至少记录：

```json
{
  "evidence_id": "EVID-...",
  "kind": "test_run|build|smoke|readback|schema_validation|document_validation|static_analysis|visual|migration|rollback|audit_export|protected_attestation",
  "path": "logs/...",
  "sha256": "sha256:...",
  "command": "...",
  "exit_code": 0,
  "started_utc": "...",
  "completed_utc": "...",
  "candidate_revision": "...",
  "candidate_content_manifest_hash": "sha256:...",
  "validator_id": "...",
  "validator_version": "...",
  "covered_check_ids": ["..."],
  "environment_identity": "...",
  "expires_utc": null
}
```

`test_definition_refs`证明测试或validator定义存在，`test_run_evidence_ids`和`runtime_evidence_ids`引用当前执行结果，两者不能互相替代。每个check必须逐项核对`evidence_requirements.required_kinds`、最小数量和freshness policy；相同路径但hash、candidate、validator或environment不匹配时必须拒绝并标记stale。

### 6.4 状态判定硬规则

- `verified`必须具有有效`implementation_refs`、`test_definition_refs`，并完整满足当前行的`evidence_requirements`；仅文档类要求可以用明确的非代码交付物替代生产代码，但仍必须有可执行校验和当前证据。
- `evaluation_state!=evaluated`时不得产生`verified`授权效果。
- `gate_state=blocked`不改变真实`disposition`，但阻止对应阶段授权。
- `not_applicable`必须满足适用性不变量，记录未触发的谓词、权威和证明该结论的证据ID。
- `explicitly_deferred`必须满足全部条件必填机器字段，不得只依赖`gap`；它不计入`verified`数量，也不得自动满足Program DoD。
- `partial`和`missing`不能通过对应阶段；`not_evaluated`、`stale`或`blocked`不能授权对应阶段。
- `gap`对非`verified`行必须非空；对`verified`行应为空或只包含无阻断说明。

## 7. 阶段验收控制

### 7.1 通用规则

阶段名称和依赖关系必须从目标计划或已注册adapter中解析为DAG，不在通用Skill中永久硬编码线性顺序。每个阶段节点至少记录：

```json
{
  "phase_id": "Phase 2",
  "predecessor_phase_ids": ["Phase 1"],
  "predecessor_mode": "all|any",
  "activation_predicate": "...",
  "optional": false
}
```

Skill必须：

1. 计算所有当前active和eligible阶段，不假定只能有一个“最早阶段”。
2. 前置条件未满足时，不得声明该阶段通过，但可以评估其真实实施`disposition`。
3. 支持串行、并行、条件分支和汇合gate；adapter可以把特定计划限制为严格线性DAG。
4. 每个阶段分别生成条款覆盖、状态计数、阻断前置、finding策略和退出结论。
5. 按需能力包只在activation predicate成立时启用；未触发必须使用有证据的`not_applicable`，不能静默跳过。
6. phase graph存在环、孤立必需节点、未知predecessor或无法计算的activation predicate时失败关闭。

### 7.2 7-07 适配要求

对 `2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening`，顺序固定为：

```text
Phase 0A -> Phase 0B -> Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5 -> Phase 6
```

- Phase 0A：跨领域基础契约、动作注册表、状态词汇、路径/readback、账号边界、幂等、secret redaction、共享 LLM 入口、ADR 和标准同步。
- Phase 0B：按每条被触及 route 检查 Godot semantics、UI capability、UI style、diagnostics 和 visual evidence 能力包；它是按需门禁，不是一次性全量要求。
- Phase 1：Requirement Map、GDD/Scene Route/Contract hash 链、freshness、prototype skeleton guard 和首个 deckbuilder 参考路径。
- Phase 2-6：依次检查迭代计划追踪、工作流推荐、执行与修复、UI closure 和最终 route governance。

### 7.3 阶段通过条件

阶段只有同时满足以下条件才能通过：

- 当前阶段全部`consumed_partition_ids`分别达到`deterministic_complete`或`semantically_attested_complete`，且没有`candidate`或`incomplete`分区；
- 全部exit criteria已原子化进入矩阵并有合法结论；
- 对应 `01-*` 至 `07-*` 局部 acceptance criteria 已覆盖；
- 相关 `97-*` 条目全部分类；
- 所有适用行均为`evaluation_state=evaluated`且`gate_state=eligible`；
- 所有应当`verified`的条目均有实现、测试或validator定义，并满足逐check声明的全部`evidence_requirements`；
- 所有 `not_applicable` 和 `explicitly_deferred` 均满足严格字段合同，且目标计划明确允许该延期通过当前阶段出口；
- 没有`partial`、`missing`、`not_evaluated`、`stale`或`gate_state=blocked`行；
- 没有目标计划`finding_policy.blocking_severities`中的未解决finding；
- 计划声明的 predecessor、external 或 protected gate 已通过。

### 7.4 Finding阻断策略

Skill必须从目标计划、已注册adapter或仓库标准解析：

```json
{
  "finding_policy": {
    "blocking_severities": ["P0", "P1"],
    "source_refs": ["..."],
    "unverified_disposition": "block|manual_pause"
  }
}
```

7-12通用Bootstrap合同中的P2是advisory；7-07 adapter因计划自身DoD要求将`blocking_severities`设置为`["P0","P1","P2"]`。目标计划未提供且无法从已批准adapter或仓库标准解析策略时，Skill可以展示P0/P1默认风险视图，但最终授权必须为`incomplete`，不能擅自决定P2是否阻断。

## 8. DoD 层级判定

Skill必须以目标目录的`09-*`或计划声明的等价DoD权威为完成层级来源，分别输出：

1. `First-slice DoD`
2. `Phase exit DoD`
3. `Program DoD`

三个层级必须分别输出，不允许用较低层级推导较高层级。若计划没有定义某一层级，也必须输出该层级并使用`status=not_defined`，同时记录`authoritySearch`和`reason`，不得把“未定义”误报为失败或静默省略：

```json
{
  "dodLevel": "first_slice",
  "status": "not_defined",
  "authoritySearch": ["09-*", "10-*", "00-index.md"],
  "reason": "Target plan defines no first-slice completion layer"
}
```

Program DoD 默认要求所有适用要求达到终态闭合。任何仍未关闭的 `explicitly_deferred` 都必须阻止 Program DoD，即使它已经合法通过某个阶段出口。只有当 `09-*` 明确把该延期定义为允许的 Program 终态，并同时给出终态非影响证明、长期owner、复查机制和关闭权限时，才能作为计划特定例外；Skill不得从“已分类”或“阶段已通过”自行推导该例外。

阶段和Program结果必须区分确定性结论、语义审查、外部gate和有效授权：

```json
{
  "phase_id": "Phase 1",
  "deterministic_result": "not_run|passed|failed|incomplete|stale",
  "semantic_review_result": "not_run|clean|advisory|blocked|incomplete|stale",
  "external_gate_result": "not_required|not_run|passed|failed|blocked|incomplete|stale",
  "effective_result": "candidate_pass|authorized|failed|blocked|incomplete|stale",
  "authorizes": [],
  "does_not_authorize": ["Phase 1 exit DoD"]
}
```

`deterministic_result`、`semantic_review_result`、`external_gate_result`和`effective_result`都必须由schema枚举约束。只有当前hash绑定的Bootstrap结果、正向inventory attestation、finding映射sidecar和计划要求的外部gate均满足时，`candidate_pass`才能转为`authorized`。任何required gate为`not_run`、`incomplete`或`stale`都不得授权。

对包含 `10-*` first-slice 文档的计划：

- `10-*` 完成最多只能证明 First-slice DoD；
- 不得据此声明整个阶段或 Program 完成；
- 若 `09-*` 与 `10-*` 冲突，以 `09-*` 的完成权限边界为准并报告冲突。

对 7-07，Program DoD 至少要求：

- 完整 GDD 到 package 流程通过；
- 所有阶段通过；
- `97-*` 没有未分类或仍未关闭的新增要求；
- 实施验收矩阵中没有剩余 `explicitly_deferred` 行；
- full-target capability ledger 没有非法最终状态；
- API 兼容、账号隔离、诊断、UI capability/style closure 均有当前证据；
- 最终全局审查没有未解决 P0/P1/P2；
- 计划声明的 protected handoff 或外部授权已满足。

## 9. Bootstrap 协作流程

推荐完整流程：

```text
实施验收 Skill
  -> 冻结run input和candidate manifest
  -> 生成source inventory、原子条款和候选矩阵
  -> 运行确定性测试、编译、smoke/readback检查
  -> 计算候选阶段与DoD结果
  -> 生成bootstrap-review-request.json
  -> 使用 bootstrap-implementation-conformance 审查
       -> Blind Hunter
       -> Edge Case Hunter
       -> Acceptance Auditor审计矩阵
       -> Acceptance Auditor写入inventory audit attestation companion
  -> 导入hash-bound finalized review-result.v1
  -> 生成并校验finding-to-acceptance mapping companion
  -> 按目标finding policy写入最终阶段判定
  -> 输出最终验收报告
```

新 Skill 可以准备 Bootstrap 所需 scope、context class 和 plan-bound required checks，但不得绕过 `$run-phase-bootstrap-review` 的隔离 reviewer、gateway 和 verifier 规则。

`bootstrap-review-request.json`至少包含：

```json
{
  "target_plan": "...",
  "candidate_revision": "...",
  "candidate_content_manifest_hash": "sha256:...",
  "matrix_path": "...",
  "matrix_hash": "sha256:...",
  "inventory_audit_attestation_path": "acceptance-inventory-audit-attestation.json",
  "finding_acceptance_map_path": "bootstrap-finding-acceptance-map.json",
  "requested_profile": "bootstrap-implementation-conformance",
  "required_scopes": [],
  "context_class_bindings": {},
  "plan_bound_required_checks": [],
  "blocking_severity_policy": ["P0", "P1"]
}
```

现有Bootstrap reviewer output、finding和result v1对象保持不可变。新Skill和Bootstrap profile通过两个版本化companion sidecar补充验收语义，不得向`additionalProperties: false`的现有对象注入`check_id`、`cross_cutting_gate`或inventory完整度字段：

1. `acceptance-inventory-audit-attestation.v1`：提供第5.1节定义的正向条款完整性证明。
2. `bootstrap-finding-acceptance-map.v1`：把不可变finding映射到acceptance check或跨切面gate。

finding映射sidecar至少包含：

```json
{
  "schemaVersion": "bootstrap-finding-acceptance-map.v1",
  "reviewId": "...",
  "reviewInputHash": "sha256:...",
  "reviewResultHash": "sha256:...",
  "matrixHash": "sha256:...",
  "mappings": [
    {
      "findingId": "BSR-...",
      "mappingType": "check",
      "checkIds": ["GTM-AC-P1-017"],
      "mappingMethod": "explicit-validator-ref",
      "mappingEvidence": ["acceptance-check://GTM-AC-P1-017"]
    },
    {
      "findingId": "BSR-...",
      "mappingType": "cross_cutting_gate",
      "affectedPhaseIds": ["Phase 2", "Phase 3"],
      "gateId": "GTM-GATE-SOURCE-BOUNDARY",
      "mappingMethod": "explicit-gate-ref",
      "mappingEvidence": ["..."]
    }
  ]
}
```

映射必须遵守：

- 原Bootstrap finding保持不可变，sidecar只引用`findingId`和hash-bound review result；
- `mappingType`只允许`check|cross_cutting_gate|unmapped`；`unmapped`必须包含`reason`和已经检查过的稳定引用来源；
- finding包含`acceptance-check://<check_id>`或其他已注册稳定引用时，才允许确定性映射；
- 只有语义相似但没有稳定关系时，主Skill不得猜测`check_id`；必须标记为`unmapped`并记录原因，或由明确approval authority补充映射证据；
- `mappingType=check`时`checkIds`非空且全部存在于当前matrix；`mappingType=cross_cutting_gate`时`gateId`和`affectedPhaseIds`非空；
- 无法映射的阻断finding使finalize结果为`incomplete`；非阻断unmapped finding仍必须显示在报告中，不能静默丢弃；
- sidecar的review input、review result和matrix hash必须与当前run完全一致，否则为stale。

导入Bootstrap结果时必须验证：

- 使用finalized `review-result.v1`，不能使用gate中间状态；
- review scope、input hash、authority revision、candidate manifest hash和matrix hash与当前acceptance run一致；
- required reviewer layers全部完成；
- `incomplete`、`blocked`、stale或未finalize结果不能授权；
- 当前run需要语义完整度授权时，必须存在有效`acceptance-inventory-audit-attestation.v1`；
- 每个finding必须在`bootstrap-finding-acceptance-map.v1`中映射到具体`check_id`、明确的`cross_cutting_gate`或可审核的`unmapped`结论；
- P2是否阻断由当前`finding_policy`决定，不能根据`advisory`名称自动推断。

若用户只要求确定性验收而未明确授权 reviewer，Skill 应输出“候选完成层级”，并明确 Bootstrap 语义审查尚未执行。

## 10. 输出合同

每次运行使用新的目录：

```text
logs/ci/<date>/refactor-implementation-acceptance-<run-id>/
├── acceptance-run-input.json
├── baseline-content-manifest.json
├── candidate-content-manifest.json
├── acceptance-source-inventory.json
├── acceptance-source-clauses.json
├── acceptance-evidence-records.json
├── implementation-acceptance-matrix.json
├── implementation-acceptance-matrix.md
├── phase-graph.json
├── phase-acceptance-result.json
├── program-dod-result.json
├── bootstrap-review-request.json
├── acceptance-inventory-audit-attestation.json
├── bootstrap-finding-acceptance-map.json
├── acceptance-report.md
└── evidence/
```

### 10.1 运行模式

`evidence_only`：

- 只读取已有代码、测试定义和证据；
- 不启动build、test、smoke或runtime mutation；
- 最多输出historical/candidate状态；
- 不产生实施验收授权。

`controlled_validation`：

- 允许运行计划要求的build、test、smoke和readback；
- run input必须声明`allowed_write_roots`和`forbidden_write_roots`；
- 优先使用disposable worktree、临时复制目录、外置build root和临时runtime root；
- 不得写入生产源文件、live metadata DB、live hosted workspaces或历史证据；
- 命令写入未声明路径时失败关闭。

典型写边界：

```json
{
  "execution_mode": "controlled_validation",
  "allowed_write_roots": [
    "logs/ci/<run-id>",
    "<disposable-worktree>/bin",
    "<disposable-worktree>/obj",
    "<temporary-runtime-root>"
  ],
  "forbidden_write_roots": [
    "production source tree",
    "live metadata DB",
    "live hosted workspaces",
    "historical evidence"
  ]
}
```

### 10.2 输出要求

- JSON 是机器权威，Markdown 是派生视图。
- 输出必须绑定run input、baseline/candidate content manifest、目标目录、源文件hashes、adapter、validator、验证命令和运行时间。
- companion sidecar在Bootstrap尚未运行时可以不存在，但run input和request必须预先冻结其预期路径；finalize需要语义授权时缺失任一required sidecar必须失败关闭。
- 目标、权威或验证器变更后，旧结果必须标记为 stale，不能继续授权。
- 运行目录不得位于被审查的重构目录内。
- “只读”指不得修改被验收源文件、计划权威、live状态、97台账、历史日志或Bootstrap findings；controlled validation只能写manifest声明的隔离输出路径。
- 失败证据必须保留；后续修复使用新 run 或明确 predecessor/supersession 关系。

## 11. 失败关闭条件

遇到以下情况不得产生通过结论：

- 缺少统一run input、可展开的baseline/candidate content manifest或changed-path/consumer范围，或manifest path/hash不匹配；
- 找不到阶段权威或 DoD 权威；
- 任一partition的抽取模式、extractor/adapter身份或completeness无法证明，或阶段消费的partition仍为`candidate`/`incomplete`；
- `semantic_candidate`缺少当前hash绑定的`acceptance-inventory-audit-attestation.v1`却声明`semantically_attested_complete`；
- 无法把复合条款原子化或建立稳定source clause/check身份；
- 97、98、99 或原始来源存在未解释的覆盖缺口；
- 矩阵存在重复、孤立或无来源的 `check_id`；
- applicability/disposition/evaluation组合违反第6.2节不变量；
- 任一check缺少`evidence_requirements`，或`verified`未满足其required kinds、最小数量、freshness或豁免合同；
- 证据路径、hash、candidate、validator、environment或运行范围不匹配；
- phase graph存在环、未知前置、非法汇合或被绕过的activation predicate；
- 缺少目标计划finding阻断策略；
- `10-*` 被用于授权 Program DoD；
- `finding_policy.blocking_severities`中的未解决finding被隐藏在`clean`、`advisory`或文本总结下；
- Bootstrap结果未finalize、hash不匹配、scope不完整或required layer未完成；
- Bootstrap finding映射sidecar缺失或stale，阻断finding无法稳定映射到check或cross-cutting gate；
- required deterministic、semantic或external gate为`not_run`、`incomplete`或`stale`却声明authorized；
- 验证命令写入未声明路径、live DB/workspace或历史证据；
- protected authority 尚未通过却声明其授权层级。

## 12. 新 Skill 的最小包结构

后续实现建议包含：

```text
.agents/skills/run-refactor-implementation-acceptance/
├── SKILL.md
├── agents/openai.yaml
├── references/acceptance-protocol.md
├── schemas/
│   ├── acceptance-run-input.v1.schema.json
│   ├── acceptance-content-manifest.v1.schema.json
│   ├── acceptance-source-inventory.v1.schema.json
│   ├── acceptance-source-clauses.v1.schema.json
│   ├── implementation-acceptance-matrix.v1.schema.json
│   ├── acceptance-evidence-record.v1.schema.json
│   ├── phase-graph-and-result.v1.schema.json
│   ├── phase-acceptance-result.v1.schema.json
│   ├── program-dod-result.v1.schema.json
│   ├── bootstrap-review-request.v1.schema.json
│   ├── acceptance-inventory-audit-attestation.v1.schema.json
│   └── bootstrap-finding-acceptance-map.v1.schema.json
├── adapters/
│   ├── generic-registry-backed.v1.json
│   └── 2026-07-07-gdd-to-module.v1.json
└── scripts/
    ├── acceptance_cli.py
    ├── fixtures/
    └── tests/
```

`acceptance_cli.py`至少提供以下状态转换或子命令：

```text
prepare
  -> inventory
  -> collect-evidence
  -> evaluate
  -> render
  -> prepare-bootstrap
  -> finalize
```

只提供`validate_acceptance.py`不足以说明矩阵如何生成、证据如何执行、candidate如何冻结以及Bootstrap结果如何导入。每个子命令都必须读取前序机器工件、验证hash并只写新的run-scoped输出。

不要求为该 Skill 创建单独的严格 VDD 00-99执行计划目录。

## 13. Skill 验收标准

### RA-SKILL-001：抽取可信度

对`registry_backed`和`parser_backed` fixture，确定性验证声明范围内的完整覆盖；对`semantic_candidate` partition，在没有当前hash绑定的正向inventory attestation前不得声明`semantically_attested_complete`。

### RA-SKILL-002：矩阵字段和词汇

缺少任一通用必需字段、条件必填字段、适用性字段或正交状态字段，使用未知状态、非法组合或模糊完成状态时，验证器必须非零退出并给出稳定规则ID。

### RA-SKILL-003：伪 verified

任一`verified`行缺少实现引用、测试或validator定义，或未满足逐check的`evidence_requirements`时，验证器必须拒绝。

### RA-SKILL-004：阶段顺序

phase graph存在环、未知前置、未满足汇合gate，或前置阶段未通过而后续阶段被授权时，验证器必须拒绝。

### RA-SKILL-005：按需 Phase 0B

触及 route 的能力包必须启用并验收；未触发的能力包必须有可审核 `not_applicable`，不得静默缺失。

### RA-SKILL-006：97闭合

每个适用的通用`requirement_ref`必须映射到至少一个矩阵行；7-07 adapter额外验证split-added coverage。未分类条目阻止相应阶段或Program DoD，仍未关闭的`explicitly_deferred`默认阻止Program DoD。

### RA-SKILL-007：09/10权限边界

仅凭 `10-*` 完成声明 Phase exit 或 Program DoD 时，验证器必须拒绝。

### RA-SKILL-008：三层DoD

输出必须分别报告 First-slice、Phase exit 和 Program DoD，包含通过条件、失败条款和未授权层级；计划未定义的层级必须显式输出`not_defined`、authority search和reason；阶段允许的延期不得被自动提升为 Program 终态。

### RA-SKILL-009：findings闭合

存在目标计划`finding_policy.blocking_severities`中的未解决finding时，阶段和Program DoD均不得通过；缺少可证明策略时最终结果为incomplete。

### RA-SKILL-010：新鲜证据

源文件、candidate content manifest、dirty worktree内容、adapter或validator改变后，旧矩阵和结果必须被识别为stale。

### RA-SKILL-011：只读边界

`evidence_only`不得运行产生写入的验证；`controlled_validation`只能写manifest声明的隔离路径，不得修改目标计划、生产代码、live DB/workspace或历史evidence。

### RA-SKILL-012：Bootstrap边界

未运行Bootstrap时只能输出候选完成层级；旧hash、未finalize、incomplete或scope不匹配的Bootstrap结果不能导入。需要语义授权时还必须导入有效inventory attestation和finding map。Bootstrap`clean`不能替代矩阵、DoD门禁或protected authority。

### RA-SKILL-013：原子化和ID稳定性

复合条款必须拆分为多个原子check；纯行号、换行或顺序变化不得更换ID，语义变化必须使旧check和证据stale。

### RA-SKILL-014：状态正交性

后续阶段要求已实现但predecessor未通过时，必须保持`disposition=verified`、`evaluation_state=evaluated`和`gate_state=blocked`，不得丢失实施事实。

### RA-SKILL-015：证据绑定

使用相同路径但不同hash、candidate revision、content manifest、validator version或environment identity的证据必须被拒绝。

### RA-SKILL-016：Dirty worktree

HEAD未变但任一受审文件内容改变时，旧结果必须stale；未纳入candidate manifest的dirty文件不得被验收。

### RA-SKILL-017：严重等级策略

通用fixture中P2 advisory不阻断；7-07 adapter fixture中未解决P2阻断；缺少策略时不得授权。

### RA-SKILL-018：非线性阶段

两个并行阶段可以分别验收，汇合阶段必须等待其predecessor policy要求的全部或任一前置完成。

### RA-SKILL-019：运行写边界

验证命令写入未声明路径、production source、live DB、live workspace或历史证据时必须失败关闭。

### RA-SKILL-020：Bootstrap结果绑定

旧matrix/input/candidate hash、未finalize结果、incomplete结果、未完成required layer或缺少required companion sidecar不能用于最终DoD。

### RA-SKILL-021：触发冲突

验证以下路由互不混淆：创建或修复执行计划使用`vdd-execution-plan`；审查计划或代码finding使用`run-phase-bootstrap-review`；建立实施验收矩阵或判断阶段完成度使用本Skill；修改代码完成重构不由本Skill执行。

### RA-SKILL-022：Fresh-context行为验证

分别验证明确点名Skill、普通“验收重构”请求、要求跳阶段、复用旧日志、只看测试文件不运行测试，以及把Bootstrap clean直接当Program DoD的施压场景。package validation、确定性fixture、fresh-context observation和跨模型稳定性必须分级报告。

### RA-SKILL-023：混合来源分区

同一计划同时包含registry、parser-backed阶段文档和semantic外部权威时，inventory必须生成独立partitions和`overallCompleteness`；阶段只消费其声明的`consumed_partition_ids`，不得用一个完整partition覆盖另一个candidate partition。

### RA-SKILL-024：正向完整性证明

三个reviewer均为零finding但缺少`acceptance-inventory-audit-attestation.v1`、存在未映射条款、重复check或原子化冲突时，semantic partition不得提升为`semantically_attested_complete`。

### RA-SKILL-025：Bootstrap finding映射

原Bootstrap finding必须保持不可变。只有稳定`acceptance-check://<check_id>`或已注册gate引用才能确定性映射；阻断finding无法映射、sidecar hash不匹配或引用未知check/gate时，finalize必须为`incomplete`。

### RA-SKILL-026：适用性唯一权威

验证`applicable`、`not_applicable`和`undetermined`各自允许的disposition/evaluation/gate组合。任何`applicable + not_applicable`、`not_applicable + missing`或`undetermined + evaluated`组合必须被拒绝。

### RA-SKILL-027：逐check证据合同

每个check必须具有机器可读`evidence_requirements`。required kind缺失、数量不足、freshness不符、未经授权豁免或requirements缺少权威来源时，不得判定`verified`。

### RA-SKILL-028：内容manifest可重放性

run input必须引用实际存在且hash匹配的baseline和candidate manifest。manifest必须逐文件记录路径、内容hash、classification和inclusion reason；仅有聚合hash或Git revision时不得授权。

### RA-SKILL-029：Gate和DoD状态词汇

deterministic、semantic、external和effective结果只能使用本规格枚举。required gate为`not_run`、`incomplete`或`stale`时不得授权；计划未定义DoD层级时必须使用`not_defined`并记录authority search和reason。

## 14. 必测反例

后续 Skill 至少应包含以下负例：

1. `verified` 行只有测试文件路径，没有本次执行证据。
2. `semantic_candidate`未经当前hash绑定的正向inventory attestation便声明`semantically_attested_complete`。
3. Phase 0A未通过，但Phase 1被声明通过。
4. 已实现的Phase 3条目因Phase 2未通过而被错误改写为实施`missing`。
5. 被触及route缺少所需Phase 0B能力包。
6. `not_applicable`没有触发分析或证据。
7. `explicitly_deferred`缺少任一条件必填字段，或只在自由文本`gap`中描述owner、非影响证明和复查条件。
8. 97存在未映射条目，但Program DoD被声明通过。
9. 只引用10号文件便声明整个重构完成。
10. HEAD未变但dirty内容变化后复用旧evidence。
11. 通用计划存在P2 advisory便被错误阻断，或7-07存在P2却被错误放行。
12. 三个reviewer零finding，但`semantic_candidate`矩阵漏掉一条源验收要求。
13. `explicitly_deferred`合法通过阶段出口，但仍未关闭时Program DoD被声明通过。
14. build/test/smoke写入未声明目录或live状态。
15. 旧matrix hash或未finalize Bootstrap结果被用于Program DoD。
16. 两个并行阶段已通过其一，汇合阶段被提前授权。
17. 同一计划的registry partition完整，但semantic外部权威仍为candidate，却用全局complete授权阶段。
18. Acceptance Auditor零finding，但attestation中的`unmappedClauseIds`非空或source/mapped计数不闭合。
19. Bootstrap finding只因文本相似被猜测映射到`check_id`，没有稳定引用或approval evidence。
20. `applicability.status=applicable`但`disposition=not_applicable`，或`undetermined`却标记为`evaluated`。
21. UI check的`evidence_requirements`要求visual和readback，但只有test run便声明verified。
22. run input只有candidate manifest hash，没有实际manifest文件或逐文件inclusion reason。
23. external gate为`not_run`、`incomplete`或`stale`，但结果仍被声明authorized。
24. 计划未定义First-slice DoD，却被误报为failed或从输出中静默省略。

## 15. 非目标

- 不负责实现或修复重构代码。
- 不负责改写重构计划、97台账或已有矩阵。
- 不替代 `$run-phase-bootstrap-review`。
- 不自动运行未经用户授权的隔离 reviewer 或 verifier。
- 不把7-07阶段名称硬编码为所有重构计划的通用模型。
- 不用关键词猜测结果冒充registry/parser-backed完整覆盖。
- 不在未声明隔离写边界时运行build、test、smoke或runtime mutation。
- 不用固定 finding 数量或固定覆盖率百分比判断质量。
- 不将计划一致性验证等同于运行时实现完成。

## 16. 待确认项

当前建议默认值如下，若无新的决策，创建 Skill 时按此执行：

1. Skill 名称使用 `run-refactor-implementation-acceptance`。
2. Skill 放在仓库 `.agents/skills/` 下。
3. 默认运行模式为`evidence_only`；只有用户明确要求并满足隔离写边界时才使用`controlled_validation`。
4. 来源按partition选择`registry_backed`、`parser_backed`或`semantic_candidate`；语义partition必须通过正向inventory attestation才能成为`semantically_attested_complete`。
5. 只有用户明确要求完整语义审查时才调用Bootstrap流程；未调用时只输出candidate结论。
6. 通用Skill从目标计划解析phase DAG；7-07规则作为首个线性adapter和回归fixture。
7. 现有7-07 `100-*`与机器矩阵作为兼容输入和真实测试样本，不作为无需重验的完成证明。
8. 首版必须实现统一run input、baseline/candidate manifests、partitioned source inventory、structured evidence、orthogonal state、phase graph、Bootstrap request及两个companion sidecar schema；跨模型稳定性属于发布级独立证据，不阻止本地开发迭代。
