# 重构实施验收 Skill 需求规格

- Title: `run-refactor-implementation-acceptance` Skill 需求规格
- Status: draft
- Branch: 当前工作树
- Reviewed baseline commit: `efd0fa6`
- Goal: 定义一个以验收条款为单位、按阶段顺序判断重构实施完成度的只读 Skill
- Scope: Skill 的触发、输入、验收矩阵、阶段门禁、DoD 层级、输出和验证场景
- Current step: Bootstrap companion与恢复控制合同修订完成，等待实施
- Last completed step: 已冻结companion capability、Acceptance Auditor原子role bundle、approval导入、finding policy隔离和deterministic nextAction
- Stop-loss: 本文件不创建或修改 Skill，不修改被验收重构目录，不执行 Bootstrap reviewer
- Next action: 按第12节change set门禁实施；S0与deterministic core可独立推进，但S4 semantic integration和S5完整发布必须等待S0通过
- Recovery command: `py -3 -c "from pathlib import Path; print(Path(r'execution-plans/2026-07-15-refactor-implementation-acceptance-skill-requirements.md').read_text(encoding='utf-8'))"`
- Open questions: 见“待确认项”
- Exit criteria: 本文件中的功能需求、状态规则、阶段门禁和负例成为后续 Skill 创建的对照基准
- Related ADRs: `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`
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

入口 Skill 名称保持为`run-phase-bootstrap-review`。当前权威实现是仓库内`.agents/skills/run-phase-bootstrap-review/`，必须绑定`controlPlaneRevision=bootstrap-control-plane.v2`；外部同名Skill只是revision-bound薄路由，7-12 plan-local CLI只作为兼容适配器，不得承载新行为。

`run-phase-bootstrap-review` 保持现有职责：

- Blind Hunter 检查真实行为缺陷、隐藏耦合和架构漂移；
- Edge Case Hunter 检查边界、状态转换、恢复、并发和幂等路径；
- Acceptance Auditor 审计验收矩阵是否漏项、误分类或引用无效证据；
- gateway 对 findings 做事实门禁，必要时由独立 verifier 核验 P0/P1。

Bootstrap Review 不负责创建实施验收矩阵。Bootstrap `clean` 也不能单独授权 Program DoD。

当存在被消费的`semantic_candidate` partition时，正向inventory完整性证明必须作为Bootstrap v2 `bootstrap-implementation-conformance`的profile-declared Acceptance Auditor companion输出，由同一隔离Acceptance Auditor会话生成候选、由父控制面按generic schema校验并原子发布。新Skill不启动第二个semantic auditor，不自行实现Codex runner，也不绕过`no-other-semantic-review-in-cycle`。若当前Bootstrap v2 profile、runner或generic schema尚不支持该companion合同，新Skill实施或发布必须失败关闭，先扩展仓库级Bootstrap控制面及其测试；不得回写7-12适配器。

### 2.3 最终授权关系

```text
路径A：确定性授权
  完整矩阵与阶段门禁通过
  + bootstrap requirement = not_required
  + 当前DoD层级具有明确deterministic-only authority
  + external/protected gates全部满足
  = 可以声明deterministically_authorized

路径B：Bootstrap授权
  完整矩阵与阶段门禁通过
  + bootstrap requirement = required
  + Bootstrap v2 finalized且无目标finding policy阻断项
  + external/protected gates全部满足
  = 可以声明bootstrap_authorized
```

任何required来源都优先于deterministic-only许可，用户可以把`not_required`升级为`required`，不能把`required`降级。新Skill不得冒充`BH-HANDOFF`、发布门禁或计划声明的其他独立权威。

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
| `inventory_attestation_scope_expected_path` | `prepare`阶段冻结的scope预期路径，不包含尚未生成的actual hash |
| `inventory_attestation_scope_result_expected_path` | `prepare-attestation`完成后保存actual scope path/hash和生成状态的预期路径 |
| `inventory_attestation_scope_schema_path`、`inventory_attestation_scope_schema_hash` | 新Skill冻结并用于生成和校验attestation scope的schema身份 |
| `inventory_attestation_expected_artifact_name` | Bootstrap v2 run内formal companion的稳定文件名；实际路径由后续import envelope绑定 |
| `inventory_attestation_schema_path`、`inventory_attestation_schema_hash` | Bootstrap v2 generic schema的冻结身份 |
| `finding_acceptance_map_expected_path` | Bootstrap finding映射sidecar的预期输出路径 |
| `finding_acceptance_map_schema_path`、`finding_acceptance_map_schema_hash` | 新Skill冻结并用于finalize的mapping schema身份 |
| `changed_paths` | baseline到candidate的完整变化路径 |
| `affected_consumer_refs` | 受影响调用方、route、API、脚本和文档消费者 |
| `target_plan_hash` | 目标重构计划及必要原始权威的组合hash |
| `validator_hash` | 本次确定性验证器及规则版本hash |
| `adapter_id`、`adapter_version`、`adapter_hash` | 计划解析适配器身份 |

`baseline-content-manifest.json`和`candidate-content-manifest.json`都是run input的必备可展开工件，但职责不同。

baseline manifest是baseline快照，每个当时存在的受审文件至少包含：

```json
{
  "schemaVersion": "acceptance-baseline-content-manifest.v1",
  "revision": "...",
  "files": [
    {
      "path": "...",
      "roles": ["implementation", "consumer", "test"],
      "sha256": "sha256:...",
      "inclusion_reason": "..."
    }
  ]
}
```

candidate manifest表达baseline到candidate的完整受审集合与diff，包括删除tombstone：

```json
{
  "schemaVersion": "acceptance-candidate-content-manifest.v1",
  "baseline_revision": "...",
  "candidate_revision": "...",
  "files": [
    {
      "change_type": "unchanged|added|modified|deleted|renamed|untracked",
      "roles": ["implementation", "consumer", "source", "authority", "test", "evidence"],
      "baseline_path": "old/path.cs",
      "candidate_path": "new/path.cs",
      "baseline_sha256": "sha256:...",
      "candidate_sha256": "sha256:...",
      "inclusion_reason": "..."
    }
  ]
}
```

`roles`必须是来自`implementation|consumer|source|authority|test|evidence`的非空去重数组，一个文件可以同时承担多个角色。原始语义来源使用`source`，解释其规范性语义的直接标准或ADR使用`authority`。字段条件规则为：

- `unchanged`：两侧path和hash都存在，path相同且hash相同；
- `modified`：两侧path和hash都存在，path相同且hash不同；
- `added`或`untracked`：baseline path/hash为`null`，candidate path/hash存在；
- `deleted`：baseline path/hash存在，candidate path/hash为`null`，且baseline manifest中存在相同旧路径与hash；
- `renamed`：两侧path和hash都存在且path不同；允许rename同时修改内容，因此两侧hash可以相同或不同。

manifest hash必须对规范化后的完整manifest内容计算，不能只对路径列表或Git revision计算。`dirty_worktree`和`proposed_commit_set`必须绑定每个文件的角色、路径变化、两侧适用的内容hash和纳入原因；仅记录HEAD无效。任何候选文件、删除tombstone、计划权威、adapter或validator变化都会使旧结果stale。

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
- `semantically_attested_complete`：语义来源已由当前hash绑定的Bootstrap v2 Acceptance Auditor formal companion提供正向完整性证明，但不冒充确定性证明；
- `candidate`：已经抽取，但尚未满足相应完整性授权合同；
- `incomplete`：存在已知漏项、冲突、重复、无法原子化或缺失来源。

`overallCompleteness`由所有partition按最弱结果计算；任何`incomplete`使整体为`incomplete`，任何未完成审计的`candidate`使整体最多为`candidate`。阶段授权只检查该阶段`consumed_partition_ids`实际消费的partitions，不能因无关partition仍为candidate而阻断，也不能用一个complete partition覆盖另一个candidate partition。

当当前授权范围消费的partitions全部为`deterministic_complete`时，后续`bootstrap-decision.json.inventoryAttestationRequirement=not_required`，不得为了流程整齐而要求正向companion。只有至少一个被消费partition为`semantic_candidate`时，该机器状态才为`required`并启用以下正向证明合同。

初始`acceptance-run-input.json`只能冻结scope expected path和scope schema hash，不能保存尚不存在的actual scope hash。inventory、clauses和matrix生成后，`prepare-attestation`必须确定性生成`inventory-attestation-scope.json`：

```json
{
  "schemaVersion": "inventory-attestation-scope.v1",
  "acceptanceRunId": "...",
  "acceptanceRunInputHash": "sha256:...",
  "semanticPartitionIds": ["referenced-adrs"],
  "requiredSourceArtifacts": [
    {
      "path": "docs/adr/example.md",
      "sha256": "sha256:...",
      "partitionIds": ["referenced-adrs"]
    }
  ],
  "requiredDerivedArtifacts": [
    {"path": "acceptance-source-inventory.json", "sha256": "sha256:..."},
    {"path": "acceptance-source-clauses.json", "sha256": "sha256:..."},
    {"path": "implementation-acceptance-matrix.json", "sha256": "sha256:..."}
  ],
  "requiredContextArtifacts": [
    {
      "path": "docs/standards/example.md",
      "sha256": "sha256:...",
      "reason": "Interprets normative terms used by docs/adr/example.md"
    }
  ]
}
```

`prepare-attestation`随后原子写入`inventory-attestation-scope-result.json`，不得回写初始run input：

```json
{
  "schemaVersion": "inventory-attestation-scope-result.v1",
  "acceptanceRunId": "...",
  "acceptanceRunInputHash": "sha256:...",
  "scopeSchemaHash": "sha256:...",
  "scopePath": "inventory-attestation-scope.json",
  "scopeHash": "sha256:...",
  "inventoryHash": "sha256:...",
  "clausesHash": "sha256:...",
  "matrixHash": "sha256:...",
  "status": "prepared|incomplete",
  "reasonCodes": []
}
```

`requiredSourceArtifacts`必须等于当前被审计semantic partitions全部原始`source_refs`解析后的文件并集；目录、glob或仅有逻辑ID的引用必须在冻结前展开为具体文件和hash。`requiredContextArtifacts`只包含判断这些原始来源规范性语义所需、且由source、adapter或计划权威直接引用的context，不允许auditor临时扩大scope。原始source和必要context都必须作为candidate content manifest中的`source`或`authority`角色记录并使用相同path/hash；无法解析、缺hash或存在冲突时，scope为`incomplete`且不得启动auditor。

`semantic_candidate`不得仅凭reviewer已读完文件或findings为空提升完整度。用户明确授权完整语义闭合后，新Skill通过同名`$run-phase-bootstrap-review`入口请求Bootstrap v2 profile-declared positive-attestation companion。该companion由同一隔离Acceptance Auditor会话在读取Artifact View后返回候选，由Bootstrap父控制面校验schema、coverage和attempt绑定后原子写入formal sidecar；它不是第二套semantic review。发现漏项时只在attestation的结构化缺口字段中给出`incomplete`结论：

```json
{
  "schemaVersion": "acceptance-inventory-audit-attestation.v1",
  "schemaHash": "sha256:...",
  "acceptanceRunId": "...",
  "acceptanceRunInputHash": "sha256:...",
  "bootstrapControlPlaneRevision": "bootstrap-control-plane.v2",
  "bootstrapRouteVersion": "bootstrap-review-route.v2",
  "bootstrapReviewId": "...",
  "bootstrapReviewInputHash": "sha256:...",
  "artifactViewManifestHash": "sha256:...",
  "auditorRole": "acceptance_auditor",
  "reviewerAttemptId": "...",
  "auditorPromptHash": "sha256:...",
  "attestationScopeResultPath": "inventory-attestation-scope-result.json",
  "attestationScopeResultHash": "sha256:...",
  "attestationScopePath": "inventory-attestation-scope.json",
  "attestationScopeHash": "sha256:...",
  "sourceCoverage": {
    "requiredSourceArtifacts": [
      {"path": "docs/adr/example.md", "sha256": "sha256:..."}
    ],
    "readSourceArtifacts": [
      {"path": "docs/adr/example.md", "sha256": "sha256:..."}
    ],
    "missingSourceArtifacts": []
  },
  "derivedArtifactCoverage": {
    "requiredArtifacts": [
      {"path": "acceptance-source-inventory.json", "sha256": "sha256:..."},
      {"path": "acceptance-source-clauses.json", "sha256": "sha256:..."},
      {"path": "implementation-acceptance-matrix.json", "sha256": "sha256:..."}
    ],
    "readArtifacts": [
      {"path": "acceptance-source-inventory.json", "sha256": "sha256:..."},
      {"path": "acceptance-source-clauses.json", "sha256": "sha256:..."},
      {"path": "implementation-acceptance-matrix.json", "sha256": "sha256:..."}
    ],
    "missingArtifacts": []
  },
  "contextCoverage": {
    "requiredContextArtifacts": [
      {"path": "docs/standards/example.md", "sha256": "sha256:..."}
    ],
    "readContextArtifacts": [
      {"path": "docs/standards/example.md", "sha256": "sha256:..."}
    ],
    "missingContextArtifacts": []
  },
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

该formal sidecar属于仓库级Bootstrap v2 generic protocol，由Bootstrap父控制面写入并与review input、Artifact View、Acceptance Auditor attempt和prompt hash绑定。新Skill只通过后续`bootstrap-import-envelope.json`导入，不直接写入、修补或重新解释auditor payload。若control-plane revision、profile companion capability或generic schema不匹配，Bootstrap prepare/launch/import必须失败关闭。

`finalize`必须确定性验证：

- scope expected path与run input一致，`attestationScopeResultPath/hash`有效且result中的actual scope path/hash与attestation一致；
- 每个被审计semantic partition的全部原始`source_refs`都展开并出现在scope的`requiredSourceArtifacts`；
- scope与attestation中required source、derived和context集合分别完全相等；
- source、derived和context三组required/read集合均按`path+sha256`完全相等，所有missing数组为空；
- 每个source和context hash与冻结candidate content manifest中相应`source`/`authority`记录一致，每个derived hash与当前acceptance run工件一致；
- Bootstrap review已finalized且required layers完成，import envelope已把formal attestation绑定到同一review input和final result，auditor provenance完整，partition计数闭合，`unmappedClauseIds`、`duplicateCheckIds`和`atomizationConflicts`均为空。

漏读任一原始source、必要context或派生工件，scope包含无法解释的额外文件，或任一path/hash不匹配时，attestation只能为`incomplete`。只有以上条件全部满足时，finalize才能把对应partition从`candidate`提升为`semantically_attested_complete`。

### 5.2 原子化与稳定身份

一个原子、可独立判定的验收义务对应一个稳定 `check_id`：

- 一个复合条款可以拆成多个checks；
- 多个等价来源可以合并到同一check；
- 纯换行、排序或行号变化不得生成新ID；
- 语义变化必须使旧check或证据stale，不能静默复用；
- 每个check记录稳定`source_clause_ids`、可选`parent_clause_id`和`atomic_index`。

`check_id`必须声明`id_origin=registry|adapter|semantic_candidate`并遵守：

- `registry`：使用权威registry原生ID并加稳定namespace，不得重新hash或重编号；
- `adapter`：由`adapter_id + stable_id_namespace + canonical_clause_key + atomic_index`确定性生成；普通adapter版本升级不得改变stable namespace，canonical key不得包含行号、文件排序或临时路径；
- `semantic_candidate`：由版本化算法对`namespace + canonical source path + stable section anchor + parent clause key + atomic obligation key`生成临时ID，不得只对自由文本或当前行号hash；
- 所有算法记录`id_algorithm`、`id_algorithm_version`和`source_signature`；算法版本变化使旧run stale，但不得静默复用碰巧相同的字符串。

每次run必须生成`check-id-lineage.json`：

```json
{
  "schemaVersion": "check-id-lineage.v1",
  "algorithmVersion": "check-id.v1",
  "entries": [
    {
      "checkId": "GTM-AC-P1-017",
      "idOrigin": "adapter",
      "canonicalKey": "phase-1/contract-hash/atomic-1",
      "sourceSignature": "sha256:...",
      "state": "active|tombstoned",
      "transition": "created|unchanged|split|merged|superseded|retired",
      "predecessorCheckIds": [],
      "successorCheckIds": [],
      "reason": "..."
    }
  ]
}
```

split时旧ID变为tombstone并指向全部新ID；merge时全部旧ID变为tombstone并指向一个新ID；semantic ID被registry/adapter canonical ID取代时使用`superseded`。tombstone不得重新分配给其他义务，历史finding/evidence仍可通过lineage解析。任何同ID不同canonical key、同canonical key多active ID、断裂lineage或生成碰撞必须失败关闭；不得自动追加随机后缀掩盖冲突。

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

Bootstrap v2要求每个accepted P2在finalize前具有`fixed|refuted|deferred`处置；高风险P2不得延期，延期必须有owner、未来expiry、非影响证据和closure test，过期自动阻断。目标`finding_policy`只决定已合法处置的P2是否仍阻断当前验收层级，不能把`advisory`解释为无需处置。7-07 adapter因计划自身DoD要求将`blocking_severities`设置为`["P0","P1","P2"]`，因此P2只有`fixed`或`refuted`才解除其阶段/Program阻断，`deferred`仍阻断。目标计划未提供且无法从已批准adapter或仓库标准解析策略时，Skill可以展示风险视图，但最终授权必须为`incomplete`。

### 7.5 Adapter机器合同

每个adapter必须通过`acceptance-adapter.v1.schema.json`校验，并至少声明：

```json
{
  "schemaVersion": "acceptance-adapter.v1",
  "adapterId": "2026-07-07-gdd-to-module",
  "adapterVersion": "1.0.0",
  "supportedPlanFingerprint": {
    "authorityArtifacts": [
      {"path": "execution-plans/.../00-index.md", "sha256": "sha256:..."}
    ]
  },
  "sourcePartitions": [],
  "requirementExtraction": {},
  "phaseGraph": {},
  "dodSources": [],
  "findingPolicy": {
    "targetAcceptancePolicyRef": "acceptance-adapter://2026-07-07-gdd-to-module/finding-policy",
    "targetAcceptancePolicyHash": "sha256:...",
    "blockingSeverities": ["P0", "P1", "P2"]
  },
  "evidencePolicy": {},
  "mappingApprovalPolicy": {
    "allowedAuthorityRefs": [],
    "allowedApproverRoles": [],
    "identityVerificationMode": "repository-authority",
    "verifierCommandId": null
  },
  "capabilityActivationMap": {},
  "externalAndProtectedGates": [],
  "authorizationScope": {},
  "actionOrder": [
    "prepare",
    "inventory",
    "collect-evidence",
    "evaluate",
    "render",
    "prepare-attestation",
    "decide-bootstrap",
    "prepare-bootstrap",
    "import-bootstrap",
    "map-findings",
    "import-mapping-approval",
    "finalize"
  ],
  "commandRegistryRefs": [],
  "checkIdPolicy": {},
  "fixtureRefs": [],
  "validatorRefs": []
}
```

`mappingApprovalPolicy.identityVerificationMode`只允许`repository-authority|signed-artifact|explicit-user-authorization`。其中`explicit-user-authorization`必须绑定可信交互事件或控制面授权sidecar及其hash，不能只保存模型转述或自由文本身份。

adapter fingerprint必须在每次run重新计算；路径、authority hash、adapter schema、adapter version或validator变化都会使旧结果stale。adapter只能解释其声明支持的计划指纹和字段，不能覆盖计划原始权威。缺少必填策略、引用未知command/check namespace、fixture未通过或多个adapter同时声称唯一匹配时失败关闭。没有匹配adapter的通用Markdown可以降级为`semantic_candidate`候选盘点，但不得产生最终授权。

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
  "effective_result": "candidate_pass|deterministically_authorized|bootstrap_authorized|failed|blocked|incomplete|stale",
  "authorization_basis": "none|deterministic_only|bootstrap",
  "authorizes": [],
  "does_not_authorize": ["Phase 1 exit DoD"]
}
```

`deterministic_result`、`semantic_review_result`、`external_gate_result`、`effective_result`和`authorization_basis`都必须由schema枚举约束。

- 当Bootstrap为`not_required`、当前DoD层级具有明确deterministic-only authority、所有消费partition均为`deterministic_complete`且external/protected gates满足时，`candidate_pass`可以转为`deterministically_authorized`；
- 当Bootstrap为`required`时，只有当前hash绑定的Bootstrap finalized结果、按需positive attestation、finding映射和external/protected gates全部满足，才能转为`bootstrap_authorized`；
- 没有明确deterministic-only authority且Bootstrap也未完成时只能保持`candidate_pass`；任何required gate为`not_run`、`incomplete`或`stale`都不得授权。

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

### 9.1 Bootstrap调用决策状态

新Skill必须生成`bootstrap-decision.json`，不能只用自由文本决定是否调用语义审查：

```json
{
  "schemaVersion": "bootstrap-decision.v1",
  "acceptanceRunId": "...",
  "acceptanceRunInputHash": "sha256:...",
  "requirement": "required|not_required",
  "executionState": "not_applicable|awaiting_authorization|prepared|running|finalized|blocked|stale",
  "requirementSources": [
    {
      "source": "plan|adapter|semantic_partition|dod_policy|finding_policy|risk_policy|user_request",
      "authorityRefs": ["..."]
    }
  ],
  "reasonCodes": [],
  "semanticPartitionIds": ["referenced-adrs"],
  "inventoryAttestationRequirement": "required|not_required",
  "requiredCompanionCapabilities": [
    {
      "capabilityId": "acceptance-inventory-attestation",
      "capabilityVersion": "1.0",
      "profileCompanionPolicyHash": "sha256:...",
      "schemaHash": "sha256:...",
      "producerRole": "acceptance_auditor"
    }
  ],
  "deterministicAuthorization": {
    "allowed": false,
    "authorityRefs": [],
    "authorizationScopes": ["first_slice", "phase_exit", "program_dod"]
  },
  "authorizationEffect": "candidate_only|deterministic_authorization_eligible|bootstrap_authorization_pending|bootstrap_authorized",
  "requiredEntrySkill": "run-phase-bootstrap-review",
  "requiredControlPlaneRevision": "bootstrap-control-plane.v2",
  "requiredProfile": "bootstrap-implementation-conformance",
  "authorization": {
    "status": "not_required|pending|granted|denied",
    "recordedUtc": null
  },
  "bootstrapRunDir": null,
  "bootstrapReviewId": null
}
```

任一以下条件成立时`requirement=required`：

- 任一被消费partition为`semantic_candidate`；
- 目标计划或adapter明确要求Bootstrap；
- 当前DoD authority或finding policy明确要求语义审查；
- 仓库risk policy要求语义审查；
- 用户明确要求完整finding review。

多个条件可以同时成立，必须全部记录到`requirementSources`；任一required来源优先于deterministic-only许可。用户可以通过`user_request`把`not_required`升级为`required`，不能删除其他required来源或降级。

`requirementSources`只记录使Bootstrap成为`required`的来源；当且仅当不存在任何required来源时，它可以为空并令`requirement=not_required`。此时`executionState=not_applicable`且`authorization.status=not_required`，后续是否可最终授权完全由`deterministicAuthorization`、当前`authorizationScopes`和external/protected gates共同决定。

当`inventoryAttestationRequirement=required`时，`requiredCompanionCapabilities`必须包含唯一的`acceptance-inventory-attestation@1.0`身份，并冻结profile companion policy hash、schema hash和`producerRole=acceptance_auditor`；`not_required`时该数组必须为空。只匹配`bootstrap-control-plane.v2`或profile名称不足以证明能力可用。

`requirement=not_required`不等于candidate-only。只有同时满足以下条件时，`authorizationEffect=deterministic_authorization_eligible`：

- 所有被消费partition均为`deterministic_complete`；
- 目标计划或匹配adapter明确声明`deterministicAuthorization.allowed=true`；
- `authorizationScopes`明确包含当前First-slice、Phase exit或Program DoD层级；
- 没有plan、DoD、finding或risk policy要求的semantic review gate；
- 所有external/protected gates均已满足。

`not_required`但缺少上述明确authority时，`authorizationEffect=candidate_only`。`required`时必须取得用户reviewer授权，`executionState`按`awaiting_authorization -> prepared -> running -> finalized`推进，完成前为`bootstrap_authorization_pending`，finalized并通过导入后才为`bootstrap_authorized`。拒绝授权、缺依赖或控制面能力不足为`blocked`，任一绑定hash或authority变化为`stale`。不得从旧日志、Bootstrap `clean`文本或assistant总结跳转状态。

### 9.2 推荐完整流程

```text
实施验收 Skill
  -> prepare冻结run input、expected paths和schema hashes
  -> 生成source inventory、原子条款和候选矩阵
  -> 运行确定性测试、编译、smoke/readback检查
  -> 计算候选阶段与DoD结果
  -> decide-bootstrap写bootstrap-decision.json
  -> 若not_required且deterministic_authorization_eligible
       -> finalize确定性授权，记录authorization_basis=deterministic_only
  -> 若required
       -> semantic partition存在时prepare-attestation生成actual scope和scope-result
       -> 生成bootstrap-review-request.json
       -> 经用户授权后调用同名$run-phase-bootstrap-review入口
       -> bootstrap-control-plane.v2 / bootstrap-implementation-conformance
       -> Blind Hunter
       -> Edge Case Hunter
       -> Acceptance Auditor审计矩阵并按需产生positive-attestation companion candidate
       -> Bootstrap父控制面校验并原子发布Acceptance Auditor formal role bundle
       -> gate/verifier/P2 dispositions/finalize
       -> import-bootstrap生成hash-bound bootstrap-import-envelope.json
       -> map-findings确定性生成finding-to-acceptance mapping companion
       -> 存在需人工映射的finding时执行import-mapping-approval
       -> 重新运行map-findings，只消费合法approval receipt
       -> finalize校验import envelope、attestation、mapping和外部gate
       -> 记录authorization_basis=bootstrap
  -> 按目标finding policy写入最终阶段判定
  -> 输出最终验收报告
```

新Skill可以准备Bootstrap所需scope、context class、write set、execution read set、dependency closure和plan-bound required checks，但不得绕过同名`$run-phase-bootstrap-review`入口、仓库级Skill、Artifact View、隔离reviewer、gateway、verifier、P2 disposition或三轮止损规则。

### 9.3 Bootstrap request

仅当`requirement=required`时生成`bootstrap-review-request.json`；`not_required`路径不得伪造空Bootstrap run。request至少包含：

```json
{
  "entry_skill": "run-phase-bootstrap-review",
  "control_plane_revision": "bootstrap-control-plane.v2",
  "target_plan": "...",
  "candidate_revision": "...",
  "candidate_content_manifest_hash": "sha256:...",
  "matrix_path": "...",
  "matrix_hash": "sha256:...",
  "inventory_attestation_requirement": "required|not_required",
  "inventory_attestation_scope_result_path": "inventory-attestation-scope-result.json",
  "inventory_attestation_scope_result_hash": "sha256:...",
  "inventory_attestation_output_name": "acceptance-inventory-audit-attestation.json",
  "inventory_attestation_schema_path": ".agents/skills/run-phase-bootstrap-review/schemas/acceptance-inventory-audit-attestation.v1.schema.json",
  "inventory_attestation_schema_hash": "sha256:...",
  "requested_profile": "bootstrap-implementation-conformance",
  "required_profile_policy_revision": "sha256:...",
  "acceptance_auditor_role_bundle_schema_path": ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-reviewer-role-bundle.v1.schema.json",
  "acceptance_auditor_role_bundle_schema_hash": "sha256:...",
  "required_companion_capabilities": [
    {
      "capability_id": "acceptance-inventory-attestation",
      "capability_version": "1.0",
      "profile_companion_policy_hash": "sha256:...",
      "schema_hash": "sha256:...",
      "producer_role": "acceptance_auditor"
    }
  ],
  "required_scopes": [],
  "context_class_bindings": {},
  "write_set": [],
  "execution_read_set": [],
  "dependency_closure": [],
  "plan_bound_required_checks": [],
  "target_acceptance_finding_policy_ref": "acceptance-adapter://.../finding-policy",
  "target_acceptance_finding_policy_hash": "sha256:..."
}
```

示例表示`inventory_attestation_requirement=required`路径。该字段为`not_required`时，scope-result、output、attestation schema相关字段必须为`null`，`required_companion_capabilities=[]`；不得为了保持对象形状而填写伪路径、伪hash或空sidecar。

`target_acceptance_finding_policy_ref/hash`只作为hash-bound目标验收上下文进入request和import lineage。Bootstrap父控制面不得消费它来改变自己的severity、independent verifier、P2 disposition或finalize规则；新Skill只在导入合法Bootstrap结果后使用它计算当前阶段或DoD是否仍被finding阻断。

`acceptance-inventory-audit-attestation.v1`是Bootstrap v2 generic companion schema，由仓库级`run-phase-bootstrap-review`控制面拥有；新Skill只冻结并引用其path/hash。该能力属于新Skill发布依赖：若profile、runner、Artifact View prompt或父控制面原子发布尚未支持，先在仓库级Bootstrap Skill实现并完成其回归测试、quick validation和`bootstrap-skill-route`复审。不得把schema复制到新Skill形成双重权威，也不得把行为加到7-12兼容适配器。

Bootstrap profile必须新增并由profile policy revision覆盖以下正式能力身份；文件存在或control plane版本相同不能替代此声明：

```json
{
  "formalCompanionPolicy": {
    "policyVersion": "1.0",
    "roleBundleSchemaPath": ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-reviewer-role-bundle.v1.schema.json",
    "roleBundleSchemaHash": "sha256:...",
    "capabilities": [
      {
        "capabilityId": "acceptance-inventory-attestation",
        "capabilityVersion": "1.0",
        "producerRole": "acceptance_auditor",
        "schemaPath": ".agents/skills/run-phase-bootstrap-review/schemas/acceptance-inventory-audit-attestation.v1.schema.json",
        "schemaHash": "sha256:...",
        "requiredWhenRequestField": "inventory_attestation_requirement",
        "requiredValue": "required"
      }
    ]
  }
}
```

当attestation为required时，同一Acceptance Auditor attempt的finding reviewer output和companion candidate组成一个Bootstrap-owned role bundle。attempt目录必须保存candidate bundle manifest、reviewer output、companion、prompt hash、Artifact View hash、stdout/stderr和process evidence；父控制面只有在两项输出均通过schema、scope、hash、role和attempt identity校验后，才能原子发布formal role bundle。以下任一情况都令现有Bootstrap gate `status=incomplete`，使用稳定reason code而不是新增状态词汇，并禁止finalize：

- reviewer output合法但required companion缺失：`BSR-COMPANION-MISSING`；
- companion schema非法：`BSR-COMPANION-SCHEMA-INVALID`；
- companion与reviewer output不是同一attempt：`BSR-COMPANION-ATTEMPT-MISMATCH`；
- companion scope或authority hash过期：`BSR-COMPANION-SCOPE-STALE`；
- 父控制面无法原子发布完整bundle：`BSR-ROLE-BUNDLE-ATOMIC-PUBLISH-FAILED`。

失败时保留finding candidate和全部attempt证据，但不得只发布finding formal output、不得覆盖上一份合法formal bundle，也不得把run标记finalized。后续通过新attempt或replacement run重新执行。attestation为optional/not-required时允许companion缺失，但仍不得伪造空sidecar。

S0至少必须包含以下稳定fixture/test identity，并断言预期status、reason code、formal write set和旧formal bundle保持不变：`required-companion-missing`、`required-companion-schema-invalid`、`required-companion-wrong-attempt`、`required-companion-stale-scope`、`optional-companion-absent`和`atomic-role-bundle-partial-publish`。其中`optional-companion-absent`应通过且不生成sidecar，其余必须得到`incomplete`或原子发布失败的稳定诊断。

### 9.4 Finalized Bootstrap import envelope

新Skill不得直接把裸`review-result.v1`当作导入权威。`import-bootstrap`必须只读校验当前Bootstrap run并原子生成：

```json
{
  "schemaVersion": "bootstrap-import-envelope.v1",
  "acceptanceRunId": "...",
  "acceptanceRunInputHash": "sha256:...",
  "candidateContentManifestHash": "sha256:...",
  "matrixHash": "sha256:...",
  "inventoryAttestationRequirement": "required|not_required",
  "bootstrapRunDir": "logs/ci/...",
  "controlPlaneRevision": "bootstrap-control-plane.v2",
  "routeVersion": "bootstrap-review-route.v2",
  "reviewProfile": "review-policy://bootstrap-implementation-conformance/v1",
  "policyRevision": "sha256:...",
  "companionCapabilityId": "acceptance-inventory-attestation",
  "companionCapabilityVersion": "1.0",
  "profileCompanionPolicyHash": "sha256:...",
  "companionSchemaHash": "sha256:...",
  "companionProducerRole": "acceptance_auditor",
  "reviewId": "...",
  "reviewInputPath": "review-input.json",
  "reviewInputHash": "sha256:...",
  "artifactViewManifestPath": "artifact-view/manifest.json",
  "artifactViewManifestHash": "sha256:...",
  "finalResultPath": "review-gate-result.json",
  "finalResultHash": "sha256:...",
  "reviewDispositionsPath": "review-dispositions.json",
  "reviewDispositionsHash": "sha256:...",
  "p2DispositionsPath": null,
  "p2DispositionsHash": null,
  "verifierOutputPath": null,
  "verifierOutputHash": null,
  "acceptanceAuditorRoleBundlePath": "role-bundles/acceptance-auditor.json",
  "acceptanceAuditorRoleBundleHash": "sha256:...",
  "acceptanceAuditorRoleBundleSchemaHash": "sha256:...",
  "inventoryAttestationPath": "acceptance-inventory-audit-attestation.json",
  "inventoryAttestationHash": "sha256:...",
  "targetAcceptanceFindingPolicyRef": "acceptance-adapter://.../finding-policy",
  "targetAcceptanceFindingPolicyHash": "sha256:...",
  "status": "imported|incomplete|stale"
}
```

示例表示required companion路径。`inventoryAttestationRequirement=not_required`时，companion capability、schema和attestation path/hash字段必须为`null`，但Acceptance Auditor role bundle仍必须绑定合法reviewer output并明确记录companions为空。

envelope必须验证run已finalized、control-plane/profile/policy/route与request一致、required companion capability身份和policy/schema/producer role均匹配、Acceptance Auditor role bundle schema hash一致且formal bundle原子完整、Artifact View和所有formal sidecar hash有效、required layers完成、P0/P1核验闭合、每个accepted P2有合法处置，并且candidate/matrix/scope-result/target acceptance finding policy与当前acceptance run一致。`review-result.v1`本身不含全部控制面身份，因此缺少review input、Artifact View、role bundle、disposition、verifier或required attestation时不得导入。

### 9.5 Finding映射与人工approval

finding映射sidecar至少包含：

```json
{
  "schemaVersion": "bootstrap-finding-acceptance-map.v1",
  "schemaHash": "sha256:...",
  "acceptanceRunId": "...",
  "acceptanceRunInputHash": "sha256:...",
  "reviewId": "...",
  "reviewInputHash": "sha256:...",
  "reviewResultHash": "sha256:...",
  "bootstrapImportEnvelopeHash": "sha256:...",
  "matrixHash": "sha256:...",
  "checkIdLineageHash": "sha256:...",
  "mappings": [
    {
      "findingId": "BSR-...",
      "mappingType": "check",
      "checkIds": ["GTM-AC-P1-017"],
      "mappingMethod": "explicit-validator-ref",
      "mappingEvidence": ["acceptance-check://GTM-AC-P1-017"],
      "approvalId": null
    },
    {
      "findingId": "BSR-...",
      "mappingType": "cross_cutting_gate",
      "affectedPhaseIds": ["Phase 2", "Phase 3"],
      "gateId": "GTM-GATE-SOURCE-BOUNDARY",
      "mappingMethod": "explicit-gate-ref",
      "mappingEvidence": ["..."],
      "approvalId": null
    }
  ]
}
```

映射必须遵守：

- 原Bootstrap finding保持不可变，sidecar只引用`findingId`和hash-bound review result；
- `mappingType`只允许`check|cross_cutting_gate|unmapped`；`unmapped`必须包含`reason`和已经检查过的稳定引用来源；
- finding包含`acceptance-check://<check_id>`或其他已注册稳定引用时，才允许确定性映射；
- 只有语义相似但没有稳定关系时，主Skill不得猜测`check_id`；必须标记为`unmapped`并记录原因，或引用合法人工approval；
- `mappingType=check`时`checkIds`非空且全部存在于当前matrix；`mappingType=cross_cutting_gate`时`gateId`和`affectedPhaseIds`非空；
- 无法映射的阻断finding使finalize结果为`incomplete`；非阻断unmapped finding仍必须显示在报告中，不能静默丢弃；
- sidecar的import envelope、review result、matrix和check-ID-lineage hash必须与当前run完全一致，否则为stale。
- 新Skill `finalize`必须先校验run input冻结的mapping schema path/hash，再校验sidecar内容。

人工映射必须使用`finding-mapping-approvals.json`，Skill不得替用户生成approval：

```json
{
  "schemaVersion": "finding-mapping-approvals.v1",
  "approvals": [
    {
      "approvalId": "MAP-APPROVAL-001",
      "findingId": "BSR-...",
      "findingHash": "sha256:...",
      "mappingType": "check|cross_cutting_gate",
      "checkIds": ["GTM-AC-P1-017"],
      "gateId": null,
      "approverIdentity": "...",
      "approvalAuthorityRef": "...",
      "approvalAuthorityPolicyHash": "sha256:...",
      "identityVerificationMode": "repository-authority|signed-artifact|explicit-user-authorization",
      "identityEvidenceRefs": ["..."],
      "authorizationEventRef": null,
      "authorizationEventHash": null,
      "rationale": "...",
      "evidenceRefs": ["..."],
      "acceptanceRunInputHash": "sha256:...",
      "matrixHash": "sha256:...",
      "bootstrapImportEnvelopeHash": "sha256:...",
      "createdUtc": "...",
      "expiresUtc": null
    }
  ]
}
```

approval必须覆盖当前finding hash、matrix、lineage和import envelope，由有权角色明确提供；过期、身份/权限不可验证、目标check已tombstoned或只给语义相似理由时无效。`explicit-user-authorization`必须提供可信授权事件ref/hash；模型转述、聊天摘要或任意字符串不构成身份验证。使用approval的mapping必须记录`mappingMethod=manual-approved`和`approvalId`。无法映射的阻断finding使finalize为`incomplete`；非阻断unmapped finding仍必须显示，不能静默丢弃。

`import-mapping-approval`是接收人工approval的唯一正式动作。它只能读取用户或外部authority提供的文件，不得生成或补写approval内容；必须按adapter `mappingApprovalPolicy`验证authority policy、approver role、identity evidence、finding/matrix/lineage/import envelope绑定和expiry，然后把原始输入及hash原子复制为run-scoped formal input，生成`finding-mapping-approval-import.json` receipt并追加action event。成功导入会把此前不含该receipt的mapping结果标记为stale，并令`map-findings`重新成为唯一next action；验证失败时保留attempt evidence但不得发布formal input。`map-findings`只能消费已成功导入且当前hash有效的approval receipt。

若用户只要求确定性验收而未明确授权 reviewer，Skill 应输出“候选完成层级”，并明确 Bootstrap 语义审查尚未执行。

## 10. 输出合同

每次运行使用新的目录：

```text
logs/ci/<date>/refactor-implementation-acceptance-<run-id>/
├── acceptance-run-input.json
├── baseline-content-manifest.json
├── candidate-content-manifest.json
├── check-id-lineage.json
├── acceptance-source-inventory.json
├── acceptance-source-clauses.json
├── acceptance-evidence-records.json
├── implementation-acceptance-matrix.json
├── implementation-acceptance-matrix.md
├── phase-graph.json
├── phase-acceptance-result.json
├── program-dod-result.json
├── bootstrap-review-request.json
├── bootstrap-decision.json
├── inventory-attestation-scope.json
├── inventory-attestation-scope-result.json
├── bootstrap-import-envelope.json
├── bootstrap-finding-acceptance-map.json
├── finding-mapping-approvals.json
├── command-registry-snapshot.json
├── acceptance-events.jsonl
├── recovery-state.json
├── actions/
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

### 10.2 Controlled validation安全命令协议

`controlled_validation`不得从Markdown、finding、gap、adapter自由文本或LLM输出直接提取命令执行。所有可执行动作必须引用通过`acceptance-command-registry.v1.schema.json`校验且hash-bound的stable command ID：

```json
{
  "schemaVersion": "acceptance-command-registry.v1",
  "commands": [
    {
      "commandId": "plan-7-07-targeted-tests",
      "order": 100,
      "argv": ["py", "-3", "scripts/python/example.py", "--root", "${DISPOSABLE_ROOT}"],
      "typedPlaceholders": {
        "DISPOSABLE_ROOT": "path:allowed-write-root"
      },
      "cwd": "${REPOSITORY_ROOT}",
      "cwdType": "path:repository-root-read-only",
      "environmentAllowlist": ["PATH", "TEMP", "GODOT_BIN"],
      "timeoutSeconds": 900,
      "expectedWriteRoots": ["${RUN_DIR}", "${DISPOSABLE_ROOT}"],
      "forbiddenWriteRoots": ["${LIVE_DB_ROOT}", "${LIVE_WORKSPACE_ROOT}"],
      "evidenceKinds": ["test_run"]
    }
  ]
}
```

执行器必须：

- 使用结构化argv和`shell=false`，禁止shell字符串、重定向、管道和未类型化插值；
- 在执行前解析并验证typed cwd/path placeholder，所有写目标必须落在run input允许根内；
- 使用环境变量allowlist，不把secret值复制到argv、日志或evidence；
- 使用timeout和Windows process-tree/Job Object等价终止机制，超时后不得遗留子进程；
- 在命令前后生成write manifest并比较新增、修改、删除和rename；任何未声明写入立即失败关闭；
- 保存command registry hash、resolved argv、cwd、环境身份、开始/结束时间、exit code、stdout、stderr、pre/post write manifest和process结果；
- 只接受adapter或计划权威引用的command ID；未知、重复、hash漂移或与证据kind不匹配的命令不得运行。

### 10.3 输出要求

- JSON 是机器权威，Markdown 是派生视图。
- 输出必须绑定run input、baseline/candidate content manifest、目标目录、源文件hashes、adapter、validator、验证命令和运行时间。
- companion在Bootstrap尚未运行时不存在；`bootstrap-decision.inventoryAttestationRequirement=required`时，run input必须冻结scope expected path、formal attestation artifact name和schema hash，`prepare-attestation`必须产生actual scope result，实际formal attestation路径由import envelope绑定；`not_required`时不得生成伪attestation。finding map的预期路径和schema hash始终由run input冻结。
- 目标、权威或验证器变更后，旧结果必须标记为 stale，不能继续授权。
- 运行目录不得位于被审查的重构目录内。
- “只读”指不得修改被验收源文件、计划权威、live状态、97台账、历史日志或Bootstrap findings；controlled validation只能写manifest声明的隔离输出路径。
- 失败证据必须保留；后续修复使用新 run 或明确 predecessor/supersession 关系。

### 10.4 Action生命周期与恢复协议

`acceptance-events.jsonl`是run内action状态的append-only事实权威。每条事件至少绑定`run_id`、`action_id`、`attempt_id`、action type、input hashes、event type、UTC时间、PID/process identity（有子进程时）、owner token和formal write set。event type至少包括：

```text
action-reserved
action-started
action-completed
action-failed
action-stale
run-superseded
```

每个action attempt写入`actions/<action-id>/<attempt-id>/`，保存request、resolved inputs、临时输出、stdout/stderr、process result、write manifests和error。正式JSON/Markdown只能由父CLI在schema和hash校验通过后使用同目录临时文件加原子replace发布；失败或partial attempt不得覆盖上一次formal输出。

`recovery-state.json`是由events和formal artifact hashes确定性重建的派生视图，不是事实源。首版action workflow严格串行；`inspect-run`先排除依赖未满足、已完成且fresh、正在被合法owner执行或已被阻断的action，再从ready集合按以下稳定顺序选出唯一`nextAction`：action dependency拓扑层级 -> adapter `actionOrder`位置 -> command registry显式`order` -> `commandId`字典序。未声明adapter位置或command order时可以使用后续兜底，但同一排序键碰撞、未知action或无法产生唯一结果必须失败关闭。`collect-evidence`展开多个`run-command`时也使用同一排序，不得依赖文件枚举、JSON object顺序或进程完成时序。

`inspect-run`必须报告每个action的completed/failed/running/stale状态、缺失依赖、ready集合、排序依据和唯一`nextAction`；`resume`只能执行该nextAction，已完成且hash仍有效的action必须幂等跳过。输入、adapter、validator、command registry、authority或candidate漂移时追加`action-stale`，不得修改旧事件；跨run修复使用新run并以`run-superseded`和`predecessor_run_id`建立关系。

同一run必须使用owner-bound并发锁，绑定PID、process creation identity、token、acquired UTC和formal write set。活锁或重叠write set阻止第二个session；PID已退出、复用或锁未完成提交时可以记录恢复事件后清理。不得仅删除锁文件来宣称恢复，也不得同时启动相同action的两个formal attempt。

## 11. 失败关闭条件

遇到以下情况不得产生通过结论：

- 缺少统一run input、可展开的baseline/candidate content manifest或changed-path/consumer范围，或manifest path/hash不匹配；
- 初始run input保存了尚未生成的actual attestation scope hash，`prepare-attestation`回写run input，或scope-result未绑定inventory/clauses/matrix当前hash；
- candidate manifest存在空`roles`、非法change type、缺少删除tombstone、两侧path/hash条件不成立，或deleted旧hash无法在baseline manifest中闭合；
- 找不到阶段权威或 DoD 权威；
- adapter schema/fingerprint/fixture无效、多个adapter冲突、必需策略缺失，或任一partition的抽取模式、extractor/adapter身份或completeness无法证明；
- `semantic_candidate`缺少当前hash绑定的`acceptance-inventory-audit-attestation.v1`却声明`semantically_attested_complete`；
- inventory attestation scope未覆盖全部semantic partition原始`source_refs`、必要context或三个派生工件，required/read集合不等、missing非空，或source/context hash与candidate manifest不一致；
- 无法把复合条款原子化或建立稳定source clause/check身份，check-ID lineage断裂、碰撞、非法复用tombstone或split/merge无双向关系；
- 97、98、99 或原始来源存在未解释的覆盖缺口；
- 矩阵存在重复、孤立或无来源的 `check_id`；
- applicability/disposition/evaluation组合违反第6.2节不变量；
- 任一check缺少`evidence_requirements`，或`verified`未满足其required kinds、最小数量、freshness或豁免合同；
- 证据路径、hash、candidate、validator、environment或运行范围不匹配；
- phase graph存在环、未知前置、非法汇合或被绕过的activation predicate；
- 缺少目标计划finding阻断策略；
- `10-*` 被用于授权 Program DoD；
- `finding_policy.blocking_severities`中的未解决finding被隐藏在`clean`、`advisory`或文本总结下；
- Bootstrap `requirement`与`requirementSources`矛盾、遗漏任一required来源、用deterministic-only许可覆盖required来源，或`executionState`非法跳转；
- `requirement=required`时缺用户授权、controlPlaneRevision/profile capability不匹配，或Bootstrap结果未finalize、hash不匹配、scope不完整、required layer未完成；
- `requirement=not_required`时缺少当前DoD层级的明确deterministic-only authority、scope不匹配或external/protected gate未满足，却声明`deterministically_authorized`；
- required companion capability ID/version、profile companion policy hash、schema hash或producer role缺失/不匹配，或仅凭control plane/profile名称宣称能力存在；
- Acceptance Auditor required companion缺失、schema非法、attempt/scope不匹配、formal role bundle非原子发布，或只发布finding output后仍finalize；
- `bootstrap-import-envelope.json`缺失或未绑定review input、Artifact View、Acceptance Auditor role bundle、companion capability、final result、verifier、P2 dispositions、formal attestation和当前candidate/matrix；
- Bootstrap finding映射sidecar缺失或stale，阻断finding无法稳定映射到check或cross-cutting gate；
- 人工finding mapping approval未通过`import-mapping-approval`正式导入，缺身份/权限/authority policy/finding hash/lineage/matrix/import envelope绑定，已过期，或映射到tombstoned check；
- Bootstrap使用target acceptance finding policy改变自身severity、verifier、P2 disposition或finalize规则，或导入后policy ref/hash与当前acceptance run不一致；
- companion schema path/hash与run input不一致，或把Bootstrap v2 formal attestation误报为新Skill自行生成；
- required deterministic、semantic或external gate为`not_run`、`incomplete`或`stale`却声明authorized；
- controlled validation使用未知command ID、shell字符串、未类型化path、非allowlist环境、缺timeout/process-tree收口、缺pre/post write manifest，或写入未声明路径、live DB/workspace或历史证据；
- action event缺失/重写、partial attempt覆盖formal输出、同action并发运行、锁身份不明、recovery state无法从events重建、ready actions排序不确定/碰撞，或resume跳过唯一nextAction；
- protected authority 尚未通过却声明其授权层级。

## 12. 实施 change sets 与最小包结构

### 12.1 Change set门禁

实现必须把以下change set作为机器可判定的独立谓词，而不是只按章节顺序手工推进：

| Change set | 内容 | 前置 | Exit predicate | 仅授权 |
| --- | --- | --- | --- | --- |
| S0 Bootstrap v2 companion prerequisite | profile capability、companion/role-bundle schemas、Acceptance Auditor双输出、Artifact View绑定、父控制面校验、原子role bundle、生命周期测试和`bootstrap-skill-route`复审 | 无；可与S1-S3在写集隔离时独立推进 | `bootstrap_companion_ready` | S4 semantic integration可以开始，不授权新Skill发布 |
| S1 新Skill deterministic core | schemas、adapter、run input、baseline/candidate manifests、inventory和check lineage | 无 | `deterministic_core_ready` | S2可以开始，不授权semantic partition或DoD |
| S2 矩阵与阶段计算 | evidence records、正交状态、phase DAG、DoD计算和7-07 adapter fixture | S1 | `matrix_phase_ready` | deterministic candidate计算，不授权执行或最终DoD |
| S3 执行控制 | command registry、action events、locking、deterministic nextAction、inspect/resume/stale | S1、S2 | `execution_control_ready` | controlled validation可以使用，不授权Bootstrap集成 |
| S4 Bootstrap集成 | decision、request、capability binding、import envelope、finding map和approval import | S0、S1、S2、S3 | `bootstrap_integration_ready` | semantic path和Bootstrap授权候选，不授权完整发布 |
| S5 Finalize与验收 | report、positive/negative/mutation fixtures、7-07真实fixture、fresh-context观察和完整包验证 | S0-S4 | `skill_release_ready` | 新Skill完整发布候选；仍不替代目标计划protected/release authority |

S0未完成时可以开发和验证S1-S3 deterministic core，但必须把所有semantic partition结果保持为candidate，不能通过需要positive attestation的RA，不能进入S4 semantic integration，也不能声明`skill_release_ready`。每个predicate必须输出当前candidate/source/validator hashes、required checks、failed rule IDs、`authorizes`和`does_not_authorize`；低层predicate不得推导高层完成。

### 12.2 新 Skill 的最小包结构

后续实现建议包含：

```text
.agents/skills/run-refactor-implementation-acceptance/
├── SKILL.md
├── agents/openai.yaml
├── references/acceptance-protocol.md
├── references/bootstrap-v2-integration.md
├── schemas/
│   ├── acceptance-run-input.v1.schema.json
│   ├── acceptance-baseline-content-manifest.v1.schema.json
│   ├── acceptance-candidate-content-manifest.v1.schema.json
│   ├── inventory-attestation-scope.v1.schema.json
│   ├── inventory-attestation-scope-result.v1.schema.json
│   ├── acceptance-source-inventory.v1.schema.json
│   ├── acceptance-source-clauses.v1.schema.json
│   ├── check-id-lineage.v1.schema.json
│   ├── implementation-acceptance-matrix.v1.schema.json
│   ├── acceptance-evidence-record.v1.schema.json
│   ├── phase-graph-and-result.v1.schema.json
│   ├── phase-acceptance-result.v1.schema.json
│   ├── program-dod-result.v1.schema.json
│   ├── acceptance-adapter.v1.schema.json
│   ├── acceptance-command-registry.v1.schema.json
│   ├── acceptance-action-event.v1.schema.json
│   ├── acceptance-action-result.v1.schema.json
│   ├── acceptance-recovery-state.v1.schema.json
│   ├── acceptance-run-lock.v1.schema.json
│   ├── bootstrap-decision.v1.schema.json
│   ├── bootstrap-review-request.v1.schema.json
│   ├── bootstrap-import-envelope.v1.schema.json
│   ├── bootstrap-finding-acceptance-map.v1.schema.json
│   ├── finding-mapping-approvals.v1.schema.json
│   └── finding-mapping-approval-import.v1.schema.json
├── adapters/
│   ├── generic-registry-backed.v1.json
│   └── 2026-07-07-gdd-to-module.v1.json
├── commands/
│   └── generic-controlled-validation.v1.json
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
  -> prepare-attestation
  -> decide-bootstrap
  -> prepare-bootstrap
  -> import-bootstrap
  -> map-findings
  -> import-mapping-approval
  -> finalize
```

CLI还必须提供`run-command`、`inspect-run`和`resume`。只提供`validate_acceptance.py`不足以说明矩阵如何生成、证据如何执行、candidate如何冻结以及Bootstrap结果如何导入。`prepare-attestation`生成actual scope/result而不回写run input；`decide-bootstrap`写机器状态；`import-bootstrap`只接受有效v2 import envelope；`map-findings`保持确定性且把无法稳定映射的finding写为`unmapped`；`import-mapping-approval`只验证并导入外部approval，不生成approval内容。每个子命令都必须通过action lifecycle读取前序机器工件、验证hash并只原子发布新的run-scoped输出。

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

未运行Bootstrap时只能输出候选完成层级；旧hash、未finalize、incomplete或scope不匹配的Bootstrap结果不能导入。需要语义授权时必须通过同名入口和`bootstrap-control-plane.v2`，semantic partition还要求Bootstrap v2 formal inventory attestation companion。Bootstrap`clean`不能替代矩阵、DoD门禁或protected authority。

### RA-SKILL-013：原子化和ID稳定性

复合条款必须拆分为多个原子check；纯行号、换行或顺序变化不得更换ID。registry、adapter和semantic ID必须遵守版本化算法；split/merge/supersede/retire必须保留双向lineage和tombstone，语义变化必须使旧check和证据stale。

### RA-SKILL-014：状态正交性

后续阶段要求已实现但predecessor未通过时，必须保持`disposition=verified`、`evaluation_state=evaluated`和`gate_state=blocked`，不得丢失实施事实。

### RA-SKILL-015：证据绑定

使用相同路径但不同hash、candidate revision、content manifest、validator version或environment identity的证据必须被拒绝。

### RA-SKILL-016：Dirty worktree

HEAD未变但任一受审文件内容改变时，旧结果必须stale；未纳入candidate manifest的dirty文件不得被验收。

### RA-SKILL-017：严重等级策略

每个accepted P2必须在Bootstrap v2 finalize前合法处置；高风险P2不得defer。通用fixture验证合法deferred P2按目标policy决定是否阻断，7-07 adapter fixture中P2只有fixed/refuted才解除阻断；缺少策略或处置时不得授权。

### RA-SKILL-018：非线性阶段

两个并行阶段可以分别验收，汇合阶段必须等待其predecessor policy要求的全部或任一前置完成。

### RA-SKILL-019：运行写边界

验证命令写入未声明路径、production source、live DB、live workspace或历史证据时必须失败关闭。

### RA-SKILL-020：Bootstrap结果绑定

旧matrix/input/candidate hash、未finalize结果、incomplete结果、未完成required layer、control-plane/profile漂移、import envelope不完整、P2/verifier证据缺失、companion schema hash不匹配或缺少required formal attestation不能用于最终DoD。

### RA-SKILL-021：触发冲突

验证以下路由互不混淆：创建或修复执行计划使用`vdd-execution-plan`；审查计划或代码finding使用`run-phase-bootstrap-review`；建立实施验收矩阵或判断阶段完成度使用本Skill；修改代码完成重构不由本Skill执行。

### RA-SKILL-022：Fresh-context行为验证

分别验证明确点名Skill、普通“验收重构”请求、要求跳阶段、复用旧日志、只看测试文件不运行测试，以及把Bootstrap clean直接当Program DoD的施压场景。package validation、确定性fixture、fresh-context observation和跨模型稳定性必须分级报告。

### RA-SKILL-023：混合来源分区

同一计划同时包含registry、parser-backed阶段文档和semantic外部权威时，inventory必须生成独立partitions和`overallCompleteness`；阶段只消费其声明的`consumed_partition_ids`，不得用一个完整partition覆盖另一个candidate partition。

### RA-SKILL-024：正向完整性证明

三个Bootstrap reviewer均为零finding但同一Acceptance Auditor formal attestation缺失、冻结scope未覆盖任一semantic partition原始source或必要context、Artifact View/attempt/schema hash不合法、任一required/read artifact集合不等、存在未映射条款、重复check或原子化冲突时，semantic partition不得提升为`semantically_attested_complete`。

### RA-SKILL-025：Bootstrap finding映射

原Bootstrap finding必须保持不可变，mapping sidecar必须由新Skill确定性生成和校验。只有稳定引用或合法人工approval才能映射；阻断finding无法映射、approval无效、sidecar/schema/lineage hash不匹配或引用未知/tombstoned check/gate时，finalize必须为`incomplete`。

### RA-SKILL-026：适用性唯一权威

验证`applicable`、`not_applicable`和`undetermined`各自允许的disposition/evaluation/gate组合。任何`applicable + not_applicable`、`not_applicable + missing`或`undetermined + evaluated`组合必须被拒绝。

### RA-SKILL-027：逐check证据合同

每个check必须具有机器可读`evidence_requirements`。required kind缺失、数量不足、freshness不符、未经授权豁免或requirements缺少权威来源时，不得判定`verified`。

### RA-SKILL-028：内容manifest可重放性

run input必须引用实际存在且hash匹配的baseline和candidate manifest。baseline必须保存存在文件的path、roles和hash；candidate必须保存`change_type`、非空多重`roles`、两侧path/hash和inclusion reason。删除必须有tombstone并能回查baseline旧hash，rename必须同时记录旧、新路径；仅有聚合hash、Git revision或单值classification时不得授权。

### RA-SKILL-029：Gate和DoD状态词汇

deterministic、semantic、external和effective结果只能使用本规格枚举。required gate为`not_run`、`incomplete`或`stale`时不得授权；计划未定义DoD层级时必须使用`not_defined`并记录authority search和reason。

### RA-SKILL-030：Attestation冻结时序

初始run input只能冻结scope expected path和schema hash。inventory/matrix完成后由`prepare-attestation`生成actual scope和scope-result；提前保存actual hash、回写run input或scope-result未绑定当前派生工件时必须拒绝。

### RA-SKILL-031：Action恢复协议

每个subcommand必须产生append-only action events和immutable attempt evidence；partial attempt不得覆盖formal输出。`inspect-run`和`resume`必须从events重建ready集合，按冻结排序规则选择唯一next action，并正确处理stale、supersession和并发锁。

### RA-SKILL-032：安全Command Registry

`controlled_validation`只能通过stable command ID执行结构化argv。shell字符串、未知command、未类型化path、非allowlist环境、缺timeout/process-tree收口、未声明写入或缺stdout/stderr/write-manifest evidence必须失败关闭。

### RA-SKILL-033：Adapter Schema

每个adapter必须通过正式schema、plan fingerprint、fixture和validator验证，并完整声明source partitions、extraction、phase graph、DoD、finding/evidence policy、mapping approval policy、capability activation、external/protected gates、authorization scope、action order、command refs和check-ID policy。

### RA-SKILL-034：Check ID Lineage

验证registry、adapter、semantic ID生成算法以及split/merge/supersede/retire/tombstone/collision场景。旧finding和evidence必须能沿lineage解析，碰撞不得用随机后缀静默修复。

### RA-SKILL-035：Bootstrap决策状态

Bootstrap requirement与执行状态必须正交验证。`requirement`只能由全部`requirementSources`确定；`not_required`时`executionState=not_applicable`，`required`时只能按`awaiting_authorization -> prepared -> running -> finalized`推进，并允许按合同进入`blocked`或`stale`。不得跳过用户授权、control-plane capability或hash freshness门禁。

### RA-SKILL-036：Bootstrap Import Envelope

只有同时绑定`bootstrap-control-plane.v2`、profile/policy/route、companion capability、Acceptance Auditor role bundle、review input、Artifact View、final result、verifier、P2 dispositions、formal attestation、target acceptance finding policy和当前candidate/matrix的import envelope才能参与授权。

### RA-SKILL-037：人工Mapping Approval

语义相似不能自动映射finding。人工approval必须通过`import-mapping-approval`按adapter policy验证并绑定有权身份、finding hash、mapping目标、matrix、lineage和import envelope；过期、无权、未经正式导入或目标已tombstone时必须拒绝。

### RA-SKILL-038：单一语义权威

需要正向attestation时，必须由同一Bootstrap v2 Acceptance Auditor会话和父控制面formal companion完成。新Skill启动第二个semantic auditor、直接写formal attestation或把行为加入7-12兼容适配器时必须拒绝。

### RA-SKILL-039：Deterministic-only最终授权

当所有被消费partition均为`deterministic_complete`、计划或adapter对当前DoD层级明确允许deterministic-only acceptance、没有semantic review gate且external/protected gates全部满足时，`requirement=not_required`可以产生`deterministically_authorized`。不得把`not_required`机械降级为candidate-only，也不得把未覆盖当前层级的泛化许可当作授权。

### RA-SKILL-040：Required来源否决优先级

任一plan、adapter、semantic partition、DoD/finding policy、risk policy或user request来源要求Bootstrap时，`requirement`必须为`required`并保留全部authority refs。deterministic-only许可不得覆盖、删除或降级这些来源；完成Bootstrap v2及其适用合同前不得产生最终授权。

### RA-SKILL-041：Companion capability身份

需要positive attestation时，decision、request、Bootstrap profile和import envelope必须一致绑定`acceptance-inventory-attestation@1.0`、profile companion policy hash、schema hash和`producerRole=acceptance_auditor`。只匹配control plane/profile名称、只检查schema文件存在或任一身份漂移时必须拒绝。

### RA-SKILL-042：Acceptance Auditor原子Role Bundle

required companion与finding reviewer output必须来自同一Acceptance Auditor attempt，并在父控制面完成schema、scope、hash、prompt、Artifact View和attempt identity校验后原子发布。缺失、非法、stale、跨attempt或partial publish必须令Bootstrap现有gate `status=incomplete`并产生稳定reason code，保留candidate evidence但不得finalize。

### RA-SKILL-043：Mapping Approval正式导入

人工approval只能通过`import-mapping-approval`导入。该动作必须按adapter policy验证authority、approver role、identity evidence、expiry以及finding/matrix/lineage/import envelope绑定，原子发布formal input和receipt；Skill自行生成、自由文本身份或未经导入的approval不得被`map-findings`消费。

### RA-SKILL-044：目标Finding Policy隔离

Bootstrap request和import lineage必须绑定target acceptance finding policy ref/hash，但Bootstrap不得用该策略改变自身severity、verifier、P2 disposition或finalize规则。新Skill只能在合法导入后使用该策略计算阶段/DoD阻断；策略漂移使结果stale。

### RA-SKILL-045：Deterministic Next Action

ready actions必须按dependency拓扑、adapter action order、command registry显式order和command ID字典序确定唯一`nextAction`。排序碰撞、未知action或依赖文件枚举/完成时序时必须失败关闭；`inspect-run`必须报告ready集合和选择依据，`resume`只能执行该动作。

### RA-SKILL-046：Change Set授权边界

S0-S5必须分别产生hash-bound predicate结果及精确`authorizes/does_not_authorize`。S0未完成时允许S1-S3 deterministic core推进，但semantic partition不得完成、S4不得通过且S5不得声明`skill_release_ready`；任一低层predicate不得推导高层发布或目标计划DoD。

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
11. accepted P2没有fixed/refuted/deferred处置便finalize，或7-07把deferred P2错误视为解除阻断。
12. 三个reviewer零finding，但`semantic_candidate`矩阵漏掉一条源验收要求。
13. `explicitly_deferred`合法通过阶段出口，但仍未关闭时Program DoD被声明通过。
14. build/test/smoke写入未声明目录或live状态。
15. 旧matrix hash或未finalize Bootstrap结果被用于Program DoD。
16. 两个并行阶段已通过其一，汇合阶段被提前授权。
17. 同一计划的registry partition完整，但semantic外部权威仍为candidate，却用全局complete授权阶段。
18. Bootstrap Acceptance Auditor零finding，但formal attestation中的`unmappedClauseIds`非空或source/mapped计数不闭合。
19. Bootstrap finding只因文本相似被猜测映射到`check_id`，没有稳定引用或approval evidence。
20. `applicability.status=applicable`但`disposition=not_applicable`，或`undetermined`却标记为`evaluated`。
21. UI check的`evidence_requirements`要求visual和readback，但只有test run便声明verified。
22. run input只有candidate manifest hash，没有实际manifest文件；或文件只有单值classification，无法表达同时属于test和consumer。
23. external gate为`not_run`、`incomplete`或`stale`，但结果仍被声明authorized。
24. 计划未定义First-slice DoD，却被误报为failed或从输出中静默省略。
25. 删除关键authority/test文件时candidate manifest没有tombstone，或为deleted记录伪造candidate hash。
26. rename只保存新路径，无法回查baseline旧路径和hash。
27. new Skill直接写formal attestation，却被报告为Bootstrap v2父控制面已校验和原子发布。
28. semantic partition引用的一个ADR没有进入auditor source scope，但派生inventory、clauses和matrix内部计数闭合，仍被声明`semantically_attested_complete`。
29. 初始run input保存了尚未生成的actual scope hash，后续通过回写run input掩盖时序循环。
30. `evaluate`中途失败，但partial临时JSON覆盖了上一次合法formal matrix。
31. 两个session同时resume同一action并写入相同formal输出。
32. controlled validation从Markdown代码块提取命令并使用shell字符串执行。
33. command ID合法但产生了未在expected write roots声明的文件，仍被记录为passed。
34. adapter fingerprint与当前计划authority hash不匹配，却继续使用其phase graph和finding policy授权。
35. 一个check split后旧ID被重新分配给其他义务，历史finding被错误映射。
36. 新Skill另启一个semantic inventory auditor，同时仍声明`no-other-semantic-review-in-cycle`。
37. 仅导入裸`review-result.v1`，没有验证control plane revision、Artifact View、verifier或P2 dispositions。
38. finding没有稳定引用，仅凭模型语义相似度或无权approval映射到check。
39. 所有partition均为`deterministic_complete`，但计划或adapter没有对当前DoD层级声明`deterministicAuthorization.authorizationScopes`，仍被错误声明`deterministically_authorized`。
40. plan、DoD/finding policy或risk policy明确要求Bootstrap，却被adapter的deterministic-only许可覆盖并错误写成`requirement=not_required`。
41. control plane和profile名称匹配，但profile未声明`acceptance-inventory-attestation@1.0`或companion policy hash漂移，仍启动semantic reviewer或导入attestation。
42. Acceptance Auditor finding output合法，但required companion缺失、schema非法、scope stale或来自另一attempt，父控制面仍单独发布finding并finalize。
43. `map-findings`直接读取用户放入run目录的approval，未经过`import-mapping-approval`验证authority policy、identity evidence和hash绑定。
44. 目标adapter把P2列为当前DoD阻断项，Bootstrap据此改变自己的P2 disposition/finalize规则，而不是在合法导入后由新Skill计算DoD。
45. 两个独立`run-command`同时ready，`resume`依赖目录枚举顺序选择其中一个，导致不同机器产生不同`nextAction`。
46. S0 companion能力未通过，但S4 semantic integration或S5 `skill_release_ready`仍被声明通过；或S1 deterministic core通过被误报为目标计划DoD完成。

## 15. 非目标

- 不负责实现或修复重构代码。
- 不负责改写重构计划、97台账或已有矩阵。
- 不替代 `$run-phase-bootstrap-review`。
- 不自动运行未经用户授权的Bootstrap reviewer或verifier。
- 不为positive attestation复制第二套semantic runner、Artifact View、gateway或process lifecycle；generic companion能力归仓库级Bootstrap v2控制面。
- 不把新控制面行为写入7-12兼容适配器。
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
4. 来源按partition选择`registry_backed`、`parser_backed`或`semantic_candidate`；语义partition必须通过同一Bootstrap v2 Acceptance Auditor formal companion才能成为`semantically_attested_complete`。
5. 任一`semantic_partition`、plan/adapter、DoD/finding policy、risk policy或`user_request` required来源成立时，必须等待用户reviewer授权并通过同名`$run-phase-bootstrap-review`入口调用Bootstrap v2；只有全部被消费partition均为`deterministic_complete`、目标DoD层级明确允许deterministic-only acceptance、没有semantic review gate且external/protected gates已满足时，Bootstrap才可为`not_required`并产生最终授权。存在被消费的`semantic_candidate` partition时还必须取得positive-attestation companion；缺少任一所需语义步骤时只输出candidate结论。
6. 通用Skill从目标计划解析phase DAG；7-07规则作为首个线性adapter和回归fixture。
7. 现有7-07 `100-*`与机器矩阵作为兼容输入和真实测试样本，不作为无需重验的完成证明。
8. 首版按S0-S5谓词实施：统一run input、双schema baseline/candidate manifests、partitioned source inventory、structured evidence、orthogonal state、phase graph、adapter/command/lineage合同、deterministic action recovery、Bootstrap decision/request/import、冻结inventory attestation scope、确定性`map-findings`和`import-mapping-approval`；同时把带独立capability ID/version、profile policy hash和原子Acceptance Auditor role bundle的positive-attestation能力加入仓库级Bootstrap v2控制面。S0未完成不阻止S1-S3 deterministic core迭代，但阻止S4 semantic integration与S5完整发布。跨模型稳定性属于发布级独立证据，不阻止本地开发迭代。
