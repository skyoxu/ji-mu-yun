# 重构实施验收 Skill 需求规格

- Title: `run-refactor-implementation-acceptance` Skill 需求规格
- Status: requirements-ready
- Branch: 当前工作树
- Reviewed baseline commit: `7243a2a`
- Goal: 定义一个以验收条款为单位、按阶段顺序判断重构实施完成度，并执行Phase服务代码审核策略的只读 Skill
- Scope: Skill 的触发、输入、Phase服务代码审核policy pack、验收矩阵、阶段门禁、DoD 层级、输出和验证场景；Godot代码审核明确排除
- Current step: Phase服务代码审核policy pack已纳入85% diff coverage、任务清单、static/security scan合同；S0-S3 implementation-ready，S4 protocol-ready，S5 release-gated
- Last completed step: 已冻结Phase-only审核域、policy binding/exact coverage、changed-line分母、checkbox证据闭包、scanner read scope、review gate分权、base matrix、impact projection和条件Action DAG
- Stop-loss: 本文件不创建或修改 Skill，不修改被验收重构目录，不执行 Bootstrap reviewer
- Next action: 按第12节change set门禁实施；S0与deterministic core可独立推进，但S4 semantic integration和S5完整发布必须等待S0通过
- Recovery command: `py -3 -c "from pathlib import Path; print(Path(r'execution-plans/2026-07-15-refactor-implementation-acceptance-skill-requirements.md').read_text(encoding='utf-8'))"`
- Open questions: none；见“已确认默认项”
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
- 对Phase服务候选加载hash-bound代码审核policy pack，把架构、复用、质量、安全、性能和变更谱系检查映射为稳定验收义务。

它采用 acceptance-first 工作方式，不以“发现了多少问题”推断完成度。

本Skill的代码审核域仅为Phase服务。Godot engine semantics、场景、UI、渲染、视觉证据、GdUnit4和`Game.Core`游戏领域分层不属于本Skill；候选仅触及这些域时不得伪造Phase代码审核结论，应返回`unsupported_code_review_domain`。Godot代码审核由后续独立Skill拥有。

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
  + execution_mode = controlled_validation
  + external/protected gates全部满足
  = 可以声明deterministically_authorized

路径B：Bootstrap授权
  完整矩阵与阶段门禁通过
  + bootstrap requirement = required
  + execution_mode = controlled_validation
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
| `code_review_domain` | 首版固定为`phase_service`；纯Godot等外部域不得伪装成Phase |
| `code_review_policy_path`、`code_review_policy_hash` | 当前`phase-service-code-review`机器policy身份 |
| `code_review_policy_schema_path`、`code_review_policy_schema_hash` | policy pack schema身份 |
| `code_review_policy_binding_expected_path` | `resolve-code-review-policy`生成的run-scoped binding预期路径 |
| `code_review_policy_binding_schema_path`、`code_review_policy_binding_schema_hash` | binding schema身份 |
| `task_checklist_closure_expected_path`、`task_checklist_closure_schema_hash` | task checklist parser输出身份 |
| `phase_diff_coverage_expected_path`、`phase_diff_coverage_schema_hash` | changed-line coverage输出身份 |
| `minimum_changed_line_coverage_pct` | 首版固定`85.0`；更高authority可提高，不得降低 |
| `phase_static_analysis_expected_path`、`phase_security_scan_expected_path`、`phase_scan_bundle_schema_hash` | Phase static/security bundle输出身份 |
| `bootstrap_capability_binding_expected_path` | `prepare`阶段冻结的条件binding预期路径；仅在Bootstrap required时生成实际文件 |
| `bootstrap_capability_binding_schema_path`、`bootstrap_capability_binding_schema_hash` | 新Skill拥有的binding schema身份；不得依赖尚未存在的Bootstrap companion schema |
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
  "status": "complete|partial|unavailable",
  "revision": "...",
  "coverageGaps": [],
  "authorizes": [],
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
  "status": "complete|partial|unavailable",
  "baseline_revision": "...",
  "candidate_revision": "...",
  "coverageGaps": [],
  "authorizes": [],
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

manifest文件始终必须存在且通过schema；不得用空文件、缺文件或跳过schema表达“不知道”。`status=complete`时`coverageGaps=[]`且完整满足上述文件、角色、diff和tombstone合同；`partial|unavailable`时必须给出结构化`coverageGaps`、已尝试来源、缺失范围、诊断和recheck条件，并强制`authorizes=[]`。任何一个required manifest不是`complete`时，candidate completeness为`incomplete`，只能继续`evidence_only`诊断，不得进入任何授权路径。

manifest hash必须对规范化后的完整manifest内容计算，不能只对路径列表或Git revision计算。`dirty_worktree`和`proposed_commit_set`必须绑定每个文件的角色、路径变化、两侧适用的内容hash和纳入原因；仅记录HEAD无效。任何候选文件、删除tombstone、计划权威、adapter或validator变化都会使旧结果stale。

Phase 0B或其他按需能力是否被触及，必须依据baseline到candidate diff、当前phase/slice声明和route/capability dependency map共同计算，不能只扫描当前目录或依赖关键词猜测。

缺少可信baseline或candidate覆盖时，`prepare`仍必须生成`partial|unavailable` manifest及诊断，然后可以运行evidence-only盘点；不得省略manifest文件或产生实施验收授权。

### 4.2 输入权威顺序

对每个目标目录，按以下顺序建立验收来源清单：

1. `AGENTS.md` 和目标目录内更具体的仓库规则。
2. 当前`phase-service-code-review` policy pack及其hash-bound durable authority refs。
3. `00-index.md` 的状态、权威、命令与执行顺序。
4. `01-*` 至 `07-*` 中的局部 acceptance criteria 和执行合同。
5. `08-implementation-phases.md` 或等价阶段权威。
6. `09-*` 中的风险、DoD、完成层级和全局退出条件。
7. `10-*` 或等价 first-slice 文档。
8. `97-*` 新增要求台账。
9. `98-*`、`99-*` 及原始计划的来源覆盖与语义保全结果。
10. 计划已有的 `100-*` 实施验收矩阵及机器工件。
11. 计划 schemas、fixtures、validators 和 tests。
12. 实际生产代码、受影响消费者和自动化测试。
13. `logs/` 下当前 smoke、readback、运行、评审和阶段退出证据。

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

当当前授权范围消费的partitions全部为`deterministic_complete`时，后续`bootstrap-requirement-decision.json.inventoryAttestationRequirement=not_required`，不得为了流程整齐而要求正向companion。只有至少一个被消费partition为`semantic_candidate`时，该机器状态才为`required`并启用以下正向证明合同。

初始`acceptance-run-input.json`只能冻结`bootstrap-capability-binding.json`的expected path和新Skill-owned binding schema hash，不得无条件冻结尚未存在的Bootstrap companion/profile/schema身份，也不得保存尚不存在的actual scope hash。`decide-bootstrap`完成后：

- `requirement=not_required`：`bind-bootstrap-capabilities`和`prepare-attestation`记录`not_applicable` action result，不生成binding、scope或scope-result；
- `requirement=required`：`bind-bootstrap-capabilities`根据当前Bootstrap profile与仓库级schema registry原子生成immutable `bootstrap-capability-binding.json`，冻结control plane、route、profile/policy revision、companion capability、role-bundle schema、attestation schema和其authority hashes；
- `inventoryAttestationRequirement=required`：`prepare-attestation`必须消费当前binding，并确定性生成`inventory-attestation-scope.json`；
- `inventoryAttestationRequirement=not_required`：`prepare-attestation`记录`not_applicable`且不生成scope工件。

`bootstrap-capability-binding.json`至少包含：

```json
{
  "schemaVersion": "bootstrap-capability-binding.v1",
  "acceptanceRunId": "...",
  "acceptanceRunInputHash": "sha256:...",
  "bootstrapRequirementDecisionHash": "sha256:...",
  "controlPlaneRevision": "bootstrap-control-plane.v2",
  "routeVersion": "bootstrap-review-route.v2",
  "reviewProfile": "review-policy://bootstrap-implementation-conformance/v1",
  "profilePolicyRevision": "sha256:...",
  "profileCompanionPolicyHash": "sha256:...",
  "roleBundleSchemaPath": ".agents/skills/run-phase-bootstrap-review/schemas/bootstrap-reviewer-role-bundle.v1.schema.json",
  "roleBundleSchemaHash": "sha256:...",
  "requiredCompanionCapabilities": [
    {
      "capabilityId": "acceptance-inventory-attestation",
      "capabilityVersion": "1.0",
      "producerRole": "acceptance_auditor",
      "schemaPath": ".agents/skills/run-phase-bootstrap-review/schemas/acceptance-inventory-audit-attestation.v1.schema.json",
      "schemaHash": "sha256:..."
    }
  ],
  "inventoryAttestationScopeExpectedPath": "inventory-attestation-scope.json",
  "inventoryAttestationScopeResultExpectedPath": "inventory-attestation-scope-result.json",
  "inventoryAttestationScopeSchemaPath": "schemas/inventory-attestation-scope.v1.schema.json",
  "inventoryAttestationScopeSchemaHash": "sha256:...",
  "inventoryAttestationExpectedArtifactName": "acceptance-inventory-audit-attestation.json",
  "status": "bound"
}
```

示例表示attestation required路径。Bootstrap required但attestation not-required时，`requiredCompanionCapabilities=[]`，所有attestation scope/artifact/schema字段为`null`，但control plane/profile/policy与role-bundle schema仍必须冻结。binding必须与decision、当前profile registry和authority hashes一致；S0能力未实现、profile未声明required能力或任一hash缺失时，action result为`blocked`且不得发布formal binding或伪造预期schema。inventory、clauses和matrix生成且binding有效后，`prepare-attestation`必须确定性生成`inventory-attestation-scope.json`：

```json
{
  "schemaVersion": "inventory-attestation-scope.v1",
  "acceptanceRunId": "...",
  "acceptanceRunInputHash": "sha256:...",
  "bootstrapCapabilityBindingHash": "sha256:...",
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
  "bootstrapCapabilityBindingHash": "sha256:...",
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

### 5.3 Phase服务代码审核Policy Pack

代码审核规则不得作为reviewer prompt中的临时清单存在。新Skill必须提供版本化机器工件`policies/phase-service-code-review.v1.json`，并以`code-review-policy-pack.v1` schema验证；每次run生成`code-review-policy-binding.json`，绑定policy path/hash、authority hashes、adapter、candidate manifest、被触发路径和逐检查适用性。policy或任一authority变化后，旧binding、矩阵、finding map和final result全部stale。

Phase policy的默认激活域来自根`AGENTS.md`的Phase Service Scope，至少包括：

- `PhaseA.Platform/**`与`PhaseA.Platform.Tests/**`；
- `runtime/phase-a/**`；
- `scripts/python/phase_a_*.py`、`scripts/python/phase_b_*.py`和Phase-facing smoke/drill脚本；
- Phase浏览器/API调用、SQLite metadata、账号隔离、托管workspace/readback和共享LLM/Codex入口；
- 被目标计划或adapter显式声明为Phase服务consumer、authority、test或evidence的其他文件。

`Game.Godot/**`、`Tests.Godot/**`、Godot scene/UI/rendering/visual evidence、GdUnit4和`Game.Core`游戏领域逻辑不得进入本policy。纯Godot候选返回`unsupported_code_review_domain`；混合候选只能对Phase partition声明代码审核结论，Godot partition必须为`unreviewed_external_domain`，在独立Godot审核权威导入前不得授权覆盖全候选的Program DoD。

Policy pack至少使用以下合同：

```json
{
  "schemaVersion": "code-review-policy-pack.v1",
  "policyId": "phase-service-code-review",
  "policyRevision": "sha256:...",
  "targetDomain": "phase_service",
  "authorityRefs": [
    {"path": "AGENTS.md", "sha256": "sha256:..."},
    {"path": "docs/standards/phase-service.md", "sha256": "sha256:..."}
  ],
  "checks": [
    {
      "policyCheckId": "PHASE-CR-ARCH-001",
      "category": "architecture",
      "requirement": "Phase handlers, services, contracts and browser callers preserve their declared ownership boundaries.",
      "applicabilityPredicate": "phase_api_or_route_touched",
      "evaluationMode": "deterministic|review_gate|hybrid|conditional_gate",
      "defaultSeverity": "P0|P1|P2|advisory",
      "authorityRefs": ["..."],
      "validatorRefs": ["..."],
      "requiredEvidenceKinds": ["source", "test_run"]
    }
  ]
}
```

`evaluationMode`的授权含义固定为：

- `deterministic`：已注册validator/hard gate可直接产生通过或阻断事实；
- `review_gate`：Bootstrap reviewer只能产生candidate finding，必须经gateway和适用的独立verifier后才能阻断；
- `hybrid`：确定性部分与语义审查部分分别给结论，任一required部分缺失时保持`incomplete`；
- `conditional_gate`：只有目标计划、adapter或仓库policy明确赋予阻断权时才阻断，否则为advisory，不得临时升级严重度。

首版Phase policy必须包含以下稳定检查身份；除用户在本规格明确冻结的85%增量行覆盖率外，具体阈值、命令和严重度引用durable authority，不在本需求文档复制第二份权威：

| Policy check | 类别 | 本仓检查要求 | 主要证据与判定方式 |
| --- | --- | --- | --- |
| `PHASE-CR-ARCH-001` | 架构 | API handler只负责认证、输入校验、调用编排和响应映射；持久业务/工作流判断由既有service、policy或route owner承担。API/DTO/browser caller/auth boundary及行为文档按改动同步。 | changed-path/consumer manifest、handler/service引用、兼容性测试；复杂职责漂移由`review_gate`判定。 |
| `PHASE-CR-ARCH-002` | 架构 | SQLite schema演进只进入`SqliteMetadataSchema.cs`或其显式helper；状态SSoT、transaction、migration/recovery和readback owner不得在handler/service间重复。 | schema diff、migration/persistence tests、ADR/architecture refs；DDL散落可确定性拒绝。 |
| `PHASE-CR-REUSE-001` | 架构/复用 | 优先复用现有Phase service、registry、validator和共享入口。结构化LLM调用使用`ILlmRouteEngine`，可执行Codex使用`CodexHostedProcessCommandFactory`，Python使用`run_llm_exec`；不得另造provider调用或本地`codex exec`拼装。 | shared-entrypoint hard check、调用图、目标测试；其他疑似重复模块只产生可验证review candidate。 |
| `PHASE-CR-QUAL-001` | 质量/错误处理 | 错误必须具有明确结果：转换为稳定error code/envelope、记录脱敏诊断、补偿/重试、重新抛出或有权威的not-applicable。禁止吞掉异常、遗漏async/process结果、仅凭成功启动宣称成功，API不得泄露stack trace、secret或host path。 | 编译器/静态规则、异常和失败路径测试、process result、structured error evidence；语义性空catch判断走`review_gate`。 |
| `PHASE-CR-TEST-001` | 质量/测试 | 核心改动必须按change type提供最窄但完整的自动化证据：正常路径及相关失败、边界、stale、权限/跨账号、schema fresh/upgrade、browser caller或runtime recovery路径；不得只检查测试名称或只引用历史绿灯。 | `PhaseA.Platform.Tests/**`、Phase smoke、当前candidate的test-run/readback证据和逐check evidence contract。 |
| `PHASE-CR-TEST-002` | 质量/增量覆盖率 | 当前baseline到candidate中`PhaseA.Platform/**/*.cs`新增或修改的可执行行覆盖率必须达到85%；repo总覆盖率不能替代diff coverage。 | 当前candidate的PhaseA.Platform.Tests Coverlet/Cobertura、规范化changed-line set和`phase-diff-coverage.json`；无可插桩变更时以有证据的`not_applicable`关闭。 |
| `PHASE-CR-TRACE-001` | 规范/任务闭合 | adapter声明的权威任务清单中，全部required checkbox必须勾选；每个勾选项仍须映射实施、测试和证据，不能以`[x]`文本直接产生`verified`。 | `task-checklist-closure.json`、source hash、稳定item ID、矩阵check refs和当前证据。 |
| `PHASE-CR-STATIC-001` | 质量/静态检查 | 对本次Phase changed paths运行已注册的Phase静态检查bundle；至少覆盖适用的C# build/analyzer、Phase Python语法/静态规则、browser/JSON/schema检查。 | typed command registry、完整read scope、tool/process hashes和`phase-static-analysis.json`；skip/warn/partial不能满足required gate。 |
| `PHASE-CR-SEC-001` | 安全/SQL | SQL值使用参数绑定，禁止插值或`string.Format`构造statement；必须运行覆盖全部适用Phase路径的SQL gate。schema DDL集中管理，账号/项目查询保留scope条件，动态identifier只允许权威白名单。 | Phase-scoped SQL gate、query diff、授权/跨账号测试、schema owner evidence；现有`security_hard_sql_gate.py`在扩展并以fixture证明覆盖`PhaseA.Platform`前不得用于授权。 |
| `PHASE-CR-SEC-002` | 安全/边界 | 禁止硬编码或提交token、provider key、真实hash、连接秘密；日志和browser evidence必须redact。认证/admin/account隔离、ticket expiry、`no-store`、workspace/path traversal和HTTPS/host allowlist按触及面验证。 | secret scan、auth/account smoke、path sanitization、redacted logs、API tests；任何protected path写入还需显式批准。 |
| `PHASE-CR-SEC-003` | 安全/扫描闭包 | 对本次Phase changed paths运行已注册的Phase安全扫描bundle，覆盖适用的SQL、path traversal/root、secret、audit/redaction及危险process/network模式；依赖漏洞扫描按repository policy决定hard或advisory。 | `phase-security-scan.json`、scanner版本/hash、required/read path exact coverage、findings/dispositions和process results；Godot-only scanner结果无效。 |
| `PHASE-CR-PERF-001` | 性能/数据库 | 列表和跨项目查询必须有bounded filter/limit/pagination；常用account/project/status/time路径需索引或权威的小表/只写豁免。检查循环内逐行查询、重复readback和无界全表读取等N+1/scan风险。 | query/loop evidence、index/schema refs、代表性数据测试或query-plan/perf evidence；没有显式性能authority时，纯推测不得阻断。 |
| `PHASE-CR-OPS-001` | 质量/性能 | 长运行、进程、文件、SQLite handle、锁和并发slot具有timeout、取消、dispose、幂等、恢复及append-only失败证据；不得遗留子进程或用重写历史掩盖失败。 | lifecycle/concurrency/retry tests、运行证据、write manifest和recovery sidecar。 |
| `PHASE-CR-VCS-001` | 规范/变更谱系 | baseline、candidate、dirty worktree和proposed commit set必须与实际changed files一致。已有commit应清楚描述修改点和原因，并在目标policy要求时带Task/ADR/plan refs；本仓没有通用commit-message硬门时只作advisory。 | Git/manifest hash、commit range和policy authority；不得因措辞偏好阻断Program DoD。 |

#### 5.3.1 本次增量Diff覆盖率合同

`PHASE-CR-TEST-002`由确定性changed-line analyzer拥有。首版只把`PhaseA.Platform/**/*.cs`中baseline到candidate新增或修改的可执行C#行计入分母；删除行、空行、纯注释、编译器生成文件、`obj/**`、`bin/**`以及内容未变化的rename行不计入，但每个排除必须使用版本化reason code并保留path/line来源。新文件的全部可执行行属于增量；rename同时修改内容时只计算candidate中的新增/修改可执行行。

增量行覆盖率公式固定为：

```text
changed_line_coverage_pct = covered_changed_executable_lines / measurable_changed_executable_lines * 100
minimum_changed_line_coverage_pct = 85.0
```

计划、adapter或更高仓库policy可以要求高于85%，不得在单次run中静默降低。若`measurable_changed_executable_lines=0`，只有changed-line set完整且所有非C# Phase改动已进入各自替代测试合同，才能记录`not_applicable`；缺Coverage source mapping、instrumentable C#文件未出现在Cobertura、分母无法重放或coverage report不是当前candidate时必须为`incomplete|stale`，不得把这些行归入exclusion。

`phase-diff-coverage.json`至少包含：

```json
{
  "schemaVersion": "phase-diff-coverage-result.v1",
  "acceptanceRunId": "...",
  "baselineRevision": "...",
  "candidateRevision": "...",
  "candidateContentManifestHash": "sha256:...",
  "changedLineSetHash": "sha256:...",
  "coverageReportPath": "logs/unit/.../coverage.cobertura.xml",
  "coverageReportHash": "sha256:...",
  "testRunEvidenceId": "EVIDENCE-TEST-001",
  "thresholdSource": "user-requirement://phase-diff-coverage-85",
  "minimumChangedLineCoveragePct": 85.0,
  "counts": {
    "measurableChangedExecutableLines": 20,
    "coveredChangedExecutableLines": 18,
    "uncoveredChangedExecutableLines": 2,
    "excludedChangedLines": 4,
    "unmeasurableChangedLines": 0
  },
  "changedLineCoveragePct": 90.0,
  "uncoveredLines": [
    {"path": "PhaseA.Platform/Example.cs", "line": 42},
    {"path": "PhaseA.Platform/Example.cs", "line": 57}
  ],
  "exclusions": [{"path": "PhaseA.Platform/Generated.g.cs", "reasonCode": "generated_source"}],
  "nonInstrumentableChangedPaths": [],
  "status": "passed|failed|incomplete|not_applicable|stale",
  "authorizes": ["PHASE-CR-TEST-002"]
}
```

`authorizes`只有`status=passed`时包含该policy check；其他状态必须为空。changed branch coverage应同时报告（Cobertura可可靠映射时），但首版只有目标计划、adapter或仓库policy明确提供branch threshold时才具有阻断权。

#### 5.3.2 任务清单勾选闭包

`PHASE-CR-TRACE-001`只解析target plan或adapter声明的权威任务清单，不盲扫仓库全部Markdown checkbox。每个任务项生成稳定`taskChecklistItemId`，绑定source path/hash、section anchor、当前文本signature、`required|optional`、checked状态、owner、对应matrix check IDs和证据IDs。任务项默认`required`；只有来源权威或adapter显式标为optional并给出不影响当前DoD的依据时，才可降为optional。

```json
{
  "schemaVersion": "task-checklist-closure.v1",
  "acceptanceRunId": "...",
  "candidateContentManifestHash": "sha256:...",
  "sources": [{"path": "execution-plans/.../08-implementation-phases.md", "sha256": "sha256:..."}],
  "items": [
    {
      "taskChecklistItemId": "TASK-CHECK-P1-001",
      "sourceRef": "...",
      "requiredness": "required|optional",
      "checked": true,
      "matrixCheckIds": ["GTM-AC-P1-017"],
      "evidenceIds": ["EVIDENCE-TEST-001"],
      "status": "verified|checked_without_evidence|unchecked|not_applicable|stale"
    }
  ],
  "requiredItemCount": 1,
  "checkedRequiredItemCount": 1,
  "verifiedRequiredItemCount": 1,
  "status": "passed|failed|incomplete|not_applicable|stale"
}
```

全部required items必须同时`checked=true`且`status=verified`；optional item也必须勾选，或以来源权威支持的`not_applicable`明确关闭，不能保持无结论。`[x]`只是任务状态输入，不是实施证明；已勾选但没有当前实现/测试/证据时使用`checked_without_evidence`并阻断。未勾选required item使用`unchecked`并阻断。只有source inventory完整且adapter明确声明当前目标没有权威任务清单时才允许整体`not_applicable`；任务清单路径缺失、解析失败或只抽样部分section必须`incomplete`。

#### 5.3.3 Phase静态检查与安全扫描

`PHASE-CR-STATIC-001`和`PHASE-CR-SEC-003`必须分别生成`phase-static-analysis.json`与`phase-security-scan.json`。两者都使用typed command registry和controlled invocation协议，绑定candidate manifest、bundle/tool/schema版本与hash、required/read changed paths、process result、finding/disposition和输出hash。

```json
{
  "schemaVersion": "phase-scan-bundle-result.v1",
  "bundleId": "phase-static-analysis|phase-security-scan",
  "acceptanceRunId": "...",
  "candidateContentManifestHash": "sha256:...",
  "commandRegistryHash": "sha256:...",
  "requiredChangedPaths": ["PhaseA.Platform/Example.cs"],
  "readChangedPaths": ["PhaseA.Platform/Example.cs"],
  "missingChangedPaths": [],
  "commands": [
    {
      "commandId": "phase-dotnet-static-analysis",
      "toolHash": "sha256:...",
      "processResultHash": "sha256:...",
      "status": "passed|failed|skipped|incomplete|stale"
    }
  ],
  "findings": [],
  "status": "passed|failed|incomplete|not_applicable|stale",
  "authorizes": ["PHASE-CR-STATIC-001"]
}
```

首版static bundle至少按changed-path类型覆盖：C# build/compiler/analyzer、Phase Python语法和已注册静态规则、browser脚本语法/静态规则以及JSON/schema验证。security bundle至少覆盖适用的SQL construction、path/root/traversal、secret/token/connection material、audit/redaction和危险process/network模式；依赖漏洞扫描是否hard由repository risk policy决定，但结果不得丢弃。

现有`scripts/sc/analyze.py`和`security_hard_path_gate.py`、`security_hard_sql_gate.py`、`security_hard_audit_gate.py`当前主要面向模板的`Game.Core/Game.Godot`范围，不能直接证明Phase changed paths已读。实现S1时必须扩展/supersede为Phase-aware scanner并增加Phase正反fixture，或注册新的Phase scanner；在`requiredChangedPaths == readChangedPaths`且`missingChangedPaths=[]`之前结果只能`incomplete`。只有bundle `status=passed`时`authorizes`才能包含对应policy check；required command为`skipped|warn-only|stale|partial`、未知tool hash或进程失败时必须`authorizes=[]`。

每个activated `policyCheckId`必须恰好映射到一个现有或新增`check_id`，矩阵使用`policy_check_refs`保存引用；同一验收义务已由计划条款拥有时合并来源，不重复造行。binding必须列出`activated|not_applicable|unsupported`及触发证据；`not_applicable`必须证明对应changed-path、route、DB、auth、LLM、runtime或browser predicate未触发。

确定性validator不得用关键词存在性代替行为判定。Bootstrap Artifact View必须读取当前policy pack/binding、candidate manifest、task checklist closure、diff coverage、Phase static/security results、相关Phase authority、实现和测试；review finding仍需具体`trigger -> required state -> bad outcome`、guard gap、consumer和validator。零finding合法，固定finding数量非法。

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
| `policy_check_refs` | 激活的Phase代码审核policy check ID；非policy条款为空数组 |
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
| `deterministic_gate_state` | 仅由阶段前置、基础权威和确定性证据计算的资格状态 |
| `deterministic_blocking_predecessors` | 阻断基础矩阵行的阶段、确定性gate或缺失authority；不得写入Bootstrap finding |
| `gap` | 未满足项或特殊分类依据 |

`requirement_refs` 使用通用namespace，例如`requirement`、`capability`、`pbr`、`adr`、`acceptance`或`split_added`。`policy_check_refs`必须与当前`code-review-policy-binding.json`的activated集合exact-cover；同一policy check映射多个矩阵行、activated check无行或未激活check产生阻断效果均非法。7-07 adapter可以额外渲染`split_added_ids`，但该字段不得成为通用schema的必填项。

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
  -> deterministic_gate_state = blocked
  -> 不得参与任何授权
```

因此`disposition=not_applicable`只是对唯一适用性事实的受约束投影，不是第二个可独立修改的事实源。任何交叉组合冲突都必须由schema或validator拒绝。

`evaluation_state`只允许：

- `not_evaluated`：尚未针对当前candidate评估；
- `evaluated`：已完成当前candidate评估；
- `stale`：来源、candidate、evidence、adapter或validator变化后失效。

`deterministic_gate_state`只允许：

- `eligible`：该行具备参与当前阶段授权的资格；
- `blocked`：被deterministic predecessor、applicability、deterministic evidence、phase activation或缺失deterministic authority阻断；Bootstrap finding、external gate和protected gate不得写入此字段。

因此已实现的后续阶段条目可以同时为：

```json
{
  "disposition": "verified",
  "evaluation_state": "evaluated",
  "deterministic_gate_state": "blocked",
  "deterministic_blocking_predecessors": ["Phase 2"]
}
```

兼容视图可以把三组状态投影成旧`status`列，但阶段计算必须读取正交字段。禁止“看起来完成”“基本完成”“大致通过”“可能满足”等状态或等价自由文本。

### 6.3 结构化证据

路径字符串不能独立证明证据有效。每条证据使用稳定`evidence_id`并至少记录：

```json
{
  "evidence_id": "EVID-...",
  "kind": "test_run|build|smoke|readback|schema_validation|document_validation|static_analysis|visual|migration|rollback|audit_export|protected_attestation",
  "origin": "controlled_invocation|imported_existing",
  "path": "logs/...",
  "sha256": "sha256:...",
  "commandId": "plan-7-07-targeted-tests",
  "commandRegistryHash": "sha256:...",
  "commandInvocationHash": "sha256:...",
  "processResultPath": "actions/.../process-result.json",
  "processResultHash": "sha256:...",
  "importSourcePath": null,
  "importSourceHash": null,
  "importAuthorityRefs": [],
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

`origin=controlled_invocation`时command ID、registry/invocation hash和process result path/hash全部必填，且必须能回查结构化resolved argv；自由command字符串不得成为机器身份。`origin=imported_existing`时这些command字段为`null`，必须提供import source path/hash、authority refs、custody/freshness验证和只读导入receipt；它只能支持当前运行模式允许的candidate结论，不能绕过`evidence_only`授权边界。

`test_definition_refs`证明测试或validator定义存在，`test_run_evidence_ids`和`runtime_evidence_ids`引用当前执行结果，两者不能互相替代。每个check必须逐项核对`evidence_requirements.required_kinds`、最小数量和freshness policy；相同路径但hash、candidate、validator或environment不匹配时必须拒绝并标记stale。

### 6.4 状态判定硬规则

- `verified`必须具有有效`implementation_refs`、`test_definition_refs`，并完整满足当前行的`evidence_requirements`；仅文档类要求可以用明确的非代码交付物替代生产代码，但仍必须有可执行校验和当前证据。
- `evaluation_state!=evaluated`时不得产生`verified`授权效果。
- `deterministic_gate_state=blocked`不改变真实`disposition`，但阻止对应candidate阶段判定；Bootstrap finding和external/protected gate影响由后续projection拥有。
- `not_applicable`必须满足适用性不变量，记录未触发的谓词、权威和证明该结论的证据ID。
- `explicitly_deferred`必须满足全部条件必填机器字段，不得只依赖`gap`；它不计入`verified`数量，也不得自动满足Program DoD。
- `partial`和`missing`不能通过对应阶段；`not_evaluated`、`stale`或`blocked`不能授权对应阶段。
- `gap`对非`verified`行必须非空；对`verified`行应为空或只包含无阻断说明。

### 6.5 Base Matrix、Impact Projection与结果保管

`implementation-acceptance-matrix.json`是Bootstrap前冻结的base matrix，只表达requirement、implementation、evidence、applicability、disposition、evaluation和deterministic gate facts。Bootstrap findings、人工approval、external/protected gate及最终effective状态不得回写base matrix。

`project-acceptance-impact`必须基于当前工件生成：

```json
{
  "schemaVersion": "acceptance-impact-projection.v1",
  "acceptanceRunId": "...",
  "baseMatrixPath": "implementation-acceptance-matrix.json",
  "baseMatrixHash": "sha256:...",
  "codeReviewPolicyBindingHash": "sha256:...",
  "phasePolicyResultHashes": {
    "taskChecklistClosure": "sha256:...",
    "diffCoverage": "sha256:...",
    "staticAnalysis": "sha256:...",
    "securityScan": "sha256:..."
  },
  "bootstrapRequirementDecisionHash": "sha256:...",
  "bootstrapImportEnvelopeHash": null,
  "findingMapHash": null,
  "approvalImportReceiptHashes": [],
  "externalAndProtectedGateResults": [
    {
      "gateId": "BH-HANDOFF",
      "gateClass": "protected|external",
      "resultPath": "logs/...",
      "resultHash": "sha256:...",
      "schemaPath": "schemas/protected-gate-result.v1.schema.json",
      "schemaHash": "sha256:...",
      "authorityRef": "...",
      "authorizationScopes": ["program_dod"],
      "status": "passed|failed|blocked|incomplete|stale"
    }
  ],
  "gateRegistryHash": "sha256:...",
  "phaseGraphHash": "sha256:...",
  "partitionImpacts": [
    {
      "partitionId": "referenced-adrs",
      "baseCompleteness": "candidate",
      "effectiveCompleteness": "semantically_attested_complete",
      "attestationPath": "acceptance-inventory-audit-attestation.json",
      "attestationHash": "sha256:...",
      "scopeResultHash": "sha256:...",
      "status": "current|incomplete|stale"
    }
  ],
  "effectiveOverallCompleteness": "deterministic_complete|semantically_attested_complete|candidate|incomplete|stale",
  "scopeCompleteness": [
    {
      "scopeId": "phase:Phase 1",
      "consumedPartitionIds": ["referenced-adrs"],
      "scopeEffectiveCompleteness": "semantically_attested_complete|candidate|incomplete|stale"
    }
  ],
  "checkImpacts": [
    {
      "checkId": "GTM-AC-P1-017",
      "effectiveGateState": "eligible|blocked|incomplete|stale",
      "effectiveFindingRefs": [],
      "effectiveBlockingReasons": []
    }
  ],
  "status": "current|incomplete|stale"
}
```

base inventory和clauses永久保存抽取时事实，不得在attestation后改写。所有路径都必须绑定当前`codeReviewPolicyBindingHash`和四类`phasePolicyResultHashes`；deterministic-only路径使用`bootstrapImportEnvelopeHash=null`、`findingMapHash=null`和空approval receipts，但仍投影typed external/protected gates；semantic路径必须绑定当前Bootstrap import、finding map、全部required approval receipts和每个被消费partition的attestation/scope-result hash。`effectiveOverallCompleteness`按全run最弱partition计算；每个Phase/DoD必须另外按其`consumedPartitionIds`计算`scopeEffectiveCompleteness`，无关candidate partition不得阻断当前scope，也不得被其他complete partition覆盖。projection不复制base matrix实施事实，只拥有effective completeness、finding和gate影响；policy binding、task checklist、diff coverage、static/security result或任一其他输入hash变化使旧projection stale。

`evaluate`原子发布`phase-acceptance-candidate.json`和`program-dod-candidate.json`，两者必须绑定code-review policy binding与base matrix hash并固定`authorizes=[]`，明确不授权Phase/Program完成。`finalize`只读取immutable candidate结果、当前impact projection、Bootstrap import和gate evidence，另行发布`phase-acceptance-result.json`与`program-dod-result.json`。candidate与final result不得共用路径、覆盖或原地升级；失败attempt不得替换上一份formal结果。

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
- Phase 0B：本Skill只检查Phase服务route是否正确声明、注入、保存和readback Godot semantics、UI capability/style、diagnostics与visual-evidence能力依赖；不审核Godot代码、场景或视觉质量。实际Godot实现结论必须由后续独立Skill以typed external/protected gate导入；它是按需门禁，不是一次性全量要求。
- Phase 1：Requirement Map、GDD/Scene Route/Contract hash 链、freshness、prototype skeleton guard 和首个 deckbuilder 参考路径。
- Phase 2-6：依次检查Phase服务侧迭代计划追踪、工作流推荐、执行与修复、UI closure证据消费和最终route governance；UI/Godot实现本身保持外部审核域。

### 7.3 阶段通过条件

`evaluate`先生成`phase-acceptance-candidate.json`，只根据base matrix、partition completeness、实现和确定性证据计算候选结论：

- 当前阶段全部`consumed_partition_ids`分别达到`deterministic_complete`或`semantically_attested_complete`，且没有`candidate`或`incomplete`分区；
- 当前阶段触及的全部activated Phase policy checks已由`policy_check_refs` exact-cover，且required deterministic/review/hybrid分支均有当前合法结论；
- 全部exit criteria已原子化进入矩阵并有合法结论；
- 对应 `01-*` 至 `07-*` 局部 acceptance criteria 已覆盖；
- 相关 `97-*` 条目全部分类；
- 所有适用行均为`evaluation_state=evaluated`且`deterministic_gate_state=eligible`；
- 所有应当`verified`的条目均有实现、测试或validator定义，并满足逐check声明的全部`evidence_requirements`；
- 所有 `not_applicable` 和 `explicitly_deferred` 均满足严格字段合同，且目标计划明确允许该延期通过当前阶段出口；
- 没有`partial`、`missing`、`not_evaluated`、`stale`或`deterministic_gate_state=blocked`行。

`finalize`只有在候选条件满足，并同时满足以下投影条件时，才能生成通过的`phase-acceptance-result.json`：

- `acceptance-impact-projection.json`绑定当前base matrix、finding map、approval receipts、typed external/protected gate results、gate registry、phase graph和partition attestation hashes；
- 所有适用check的`effective_gate_state=eligible`且不存在未解决effective blocker；
- 当前阶段消费的semantic partition在required路径达到`semantically_attested_complete`；
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
  "actionGraph": {
    "actions": [
      {"actionId": "prepare", "order": 10, "dependsOn": [], "dependsOnAny": [], "activationPredicate": "always", "readinessPredicate": "inputs.available", "notApplicableReasonCode": null, "formalWriteSet": ["acceptance-run-input.json", "baseline-content-manifest.json", "candidate-content-manifest.json"], "reactivationTriggers": ["candidate_or_authority_changed"], "allowMultipleAttempts": false, "invalidatesOnSuccess": []},
      {"actionId": "inventory", "order": 20, "dependsOn": ["prepare"], "dependsOnAny": [], "activationPredicate": "always", "readinessPredicate": "manifests.present", "notApplicableReasonCode": null, "formalWriteSet": ["acceptance-source-inventory.json", "acceptance-source-clauses.json"], "reactivationTriggers": ["manifest_or_source_changed"], "allowMultipleAttempts": false, "invalidatesOnSuccess": []},
      {"actionId": "collect-evidence", "order": 30, "dependsOn": ["inventory"], "dependsOnAny": [], "activationPredicate": "always", "readinessPredicate": "command_or_import_sources_resolved", "notApplicableReasonCode": null, "formalWriteSet": ["acceptance-evidence-records.json"], "reactivationTriggers": ["candidate_command_or_evidence_changed"], "allowMultipleAttempts": true, "invalidatesOnSuccess": ["evaluate", "project-acceptance-impact", "finalize"]},
      {"actionId": "evaluate", "order": 40, "dependsOn": ["collect-evidence"], "dependsOnAny": [], "activationPredicate": "always", "readinessPredicate": "inventory_and_evidence_available", "notApplicableReasonCode": null, "formalWriteSet": ["implementation-acceptance-matrix.json", "phase-acceptance-candidate.json", "program-dod-candidate.json"], "reactivationTriggers": ["inventory_evidence_adapter_or_validator_changed"], "allowMultipleAttempts": true, "invalidatesOnSuccess": ["decide-bootstrap", "project-acceptance-impact", "finalize"]},
      {"actionId": "render", "order": 50, "dependsOn": ["evaluate"], "dependsOnAny": [], "activationPredicate": "always", "readinessPredicate": "candidate_results_current", "notApplicableReasonCode": null, "formalWriteSet": ["implementation-acceptance-matrix.md"], "reactivationTriggers": ["base_matrix_changed"], "allowMultipleAttempts": true, "invalidatesOnSuccess": []},
      {"actionId": "decide-bootstrap", "order": 60, "dependsOn": ["evaluate"], "dependsOnAny": [], "activationPredicate": "always", "readinessPredicate": "candidate_results_current", "notApplicableReasonCode": null, "formalWriteSet": ["bootstrap-requirement-decision.json"], "reactivationTriggers": ["new_run_required_when_decision_inputs_change"], "allowMultipleAttempts": false, "invalidatesOnSuccess": []},
      {"actionId": "bind-bootstrap-capabilities", "order": 70, "dependsOn": ["decide-bootstrap"], "dependsOnAny": [], "activationPredicate": "bootstrap.required", "readinessPredicate": "bootstrap_profile_registry_available", "notApplicableReasonCode": "BOOTSTRAP_NOT_REQUIRED", "formalWriteSet": ["bootstrap-capability-binding.json"], "reactivationTriggers": ["new_run_required_when_binding_inputs_change"], "allowMultipleAttempts": false, "invalidatesOnSuccess": []},
      {"actionId": "prepare-attestation", "order": 80, "dependsOn": ["bind-bootstrap-capabilities"], "dependsOnAny": [], "activationPredicate": "inventory_attestation.required", "readinessPredicate": "binding_and_semantic_scope_available", "notApplicableReasonCode": "INVENTORY_ATTESTATION_NOT_REQUIRED", "formalWriteSet": ["inventory-attestation-scope.json", "inventory-attestation-scope-result.json"], "reactivationTriggers": ["new_run_required_when_scope_inputs_change"], "allowMultipleAttempts": false, "invalidatesOnSuccess": []},
      {"actionId": "prepare-bootstrap", "order": 90, "dependsOn": ["bind-bootstrap-capabilities"], "dependsOnAny": [], "activationPredicate": "bootstrap.required", "readinessPredicate": "attestation_not_required_or_scope_prepared", "notApplicableReasonCode": "BOOTSTRAP_NOT_REQUIRED", "formalWriteSet": ["bootstrap-review-request.json"], "reactivationTriggers": ["new_run_required_when_request_inputs_change"], "allowMultipleAttempts": false, "invalidatesOnSuccess": []},
      {"actionId": "import-bootstrap-launch-authorization", "order": 100, "dependsOn": ["prepare-bootstrap"], "dependsOnAny": [], "activationPredicate": "bootstrap.required", "readinessPredicate": "bootstrap_launch_authorization_sidecar_available", "notApplicableReasonCode": "BOOTSTRAP_NOT_REQUIRED", "formalWriteSet": ["bootstrap-launch-authorization-import.json"], "reactivationTriggers": ["authorization_expired_revoked_or_replaced"], "allowMultipleAttempts": true, "invalidatesOnSuccess": ["import-bootstrap", "finalize"]},
      {"actionId": "import-bootstrap", "order": 110, "dependsOn": ["import-bootstrap-launch-authorization"], "dependsOnAny": [], "activationPredicate": "bootstrap.required", "readinessPredicate": "bootstrap.finalized", "notApplicableReasonCode": "BOOTSTRAP_NOT_REQUIRED", "formalWriteSet": ["bootstrap-import-envelope.json"], "reactivationTriggers": ["bootstrap_run_replaced_or_final_result_changed"], "allowMultipleAttempts": true, "invalidatesOnSuccess": ["map-findings", "project-acceptance-impact", "finalize"]},
      {"actionId": "map-findings", "order": 120, "dependsOn": ["import-bootstrap"], "dependsOnAny": [], "activationPredicate": "bootstrap_import.valid", "readinessPredicate": "finding_and_lineage_inputs_available", "notApplicableReasonCode": "BOOTSTRAP_NOT_REQUIRED", "formalWriteSet": ["bootstrap-finding-acceptance-map.json"], "reactivationTriggers": ["bootstrap_import_mapping_schema_or_approval_changed"], "allowMultipleAttempts": true, "invalidatesOnSuccess": ["project-acceptance-impact", "finalize"]},
      {"actionId": "import-mapping-approval", "order": 130, "dependsOn": ["map-findings"], "dependsOnAny": [], "activationPredicate": "mapping.requires_external_approval", "readinessPredicate": "external_approval_input_available", "notApplicableReasonCode": "MAPPING_APPROVAL_NOT_REQUIRED", "formalWriteSet": ["finding-mapping-approvals.json", "finding-mapping-approval-import.json"], "reactivationTriggers": ["approval_expired_revoked_or_replaced"], "allowMultipleAttempts": true, "invalidatesOnSuccess": ["map-findings", "project-acceptance-impact", "finalize"]},
      {"actionId": "project-acceptance-impact", "order": 140, "dependsOn": ["evaluate"], "dependsOnAny": ["deterministic_inputs_ready", "semantic_mapping_closed"], "activationPredicate": "always", "readinessPredicate": "active_branch_inputs_and_external_gates_current", "notApplicableReasonCode": null, "formalWriteSet": ["acceptance-impact-projection.json"], "reactivationTriggers": ["base_matrix_finding_map_approval_or_gate_changed"], "allowMultipleAttempts": true, "invalidatesOnSuccess": ["finalize"]},
      {"actionId": "finalize", "order": 150, "dependsOn": ["project-acceptance-impact"], "dependsOnAny": ["deterministic_branch_closed", "semantic_branch_closed"], "activationPredicate": "always", "readinessPredicate": "active_branch_closed_and_projection_current", "notApplicableReasonCode": null, "formalWriteSet": ["phase-acceptance-result.json", "program-dod-result.json", "acceptance-report.md"], "reactivationTriggers": ["any_authority_candidate_projection_or_gate_changed"], "allowMultipleAttempts": true, "invalidatesOnSuccess": []}
    ],
    "branchPredicates": {
      "deterministic_inputs_ready": "bootstrap.not_required && candidates.current && manifests.complete && controlled_validation.complete && external_gates.current",
      "semantic_mapping_closed": "bootstrap_import.valid && finding_map.current && (mapping.approval_not_required || mapping.approval_imported)",
      "deterministic_branch_closed": "deterministic_inputs_ready && impact_projection.current",
      "semantic_branch_closed": "semantic_mapping_closed && impact_projection.current && external_gates.current"
    }
  },
  "commandRegistryRefs": [],
  "checkIdPolicy": {},
  "fixtureRefs": [],
  "validatorRefs": []
}
```

`actionGraph.actions`中的`dependsOn`、`dependsOnAny`、`activationPredicate`、`readinessPredicate`、`notApplicableReasonCode`、`formalWriteSet`、`reactivationTriggers`、`allowMultipleAttempts`和`invalidatesOnSuccess`均为schema必填。`dependsOn`只能引用action ID；`dependsOnAny`可以引用action ID或同一adapter注册的`branchPredicates`，未知引用失败关闭。activation为false时生成hash-bound`action-not-applicable`；activation为true但readiness缺外部输入时为`waiting_external`，不得错误关闭为not-applicable。deterministic-only路径必须把binding、attestation、prepare-bootstrap、launch-authorization import、Bootstrap import、finding map和mapping approval全部合法关闭为not-applicable；semantic路径没有需人工批准的mapping时，`import-mapping-approval`必须以`MAPPING_APPROVAL_NOT_REQUIRED`关闭。

`deterministic_inputs_ready`至少要求not-required decision、complete manifests、当前candidate结果、controlled validation evidence和external/protected gates齐全；`semantic_mapping_closed`至少要求current Bootstrap import、finding map和全部required approval dispositions闭合。`project-acceptance-impact`完成后才能分别派生`deterministic_branch_closed|semantic_branch_closed`；`finalize`不得在active branch和projection闭合前进入ready。

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
  "schemaVersion": "phase-acceptance-result.v1",
  "resultKind": "final",
  "phase_id": "Phase 1",
  "phaseAcceptanceCandidateHash": "sha256:...",
  "baseMatrixHash": "sha256:...",
  "acceptanceImpactProjectionHash": "sha256:...",
  "bootstrapImportEnvelopeHash": null,
  "deterministic_result": "not_run|passed|failed|incomplete|stale",
  "semantic_review_result": "not_required|not_run|clean|advisory|blocked|incomplete|stale",
  "external_gate_result": "not_required|not_run|passed|failed|blocked|incomplete|stale",
  "effective_result": "candidate_pass|deterministically_authorized|bootstrap_authorized|failed|blocked|incomplete|stale",
  "authorization_basis": "none|deterministic_only|bootstrap",
  "authorizes": [],
  "does_not_authorize": ["Phase 1 exit DoD"]
}
```

`deterministic_result`、`semantic_review_result`、`external_gate_result`、`effective_result`和`authorization_basis`都必须由schema枚举约束。

对应candidate schema使用`resultKind=candidate`，不得包含impact projection或最终authorization basis，`effective_result`最多为`candidate_pass|failed|blocked|incomplete|stale`且`authorizes=[]`。final schema必须绑定当前candidate、base matrix和impact projection；semantic路径还必须绑定Bootstrap import envelope。两类schema和路径不得互换。

- 当Bootstrap为`not_required`、当前DoD层级具有明确deterministic-only authority、所有消费partition均为`deterministic_complete`且external/protected gates满足时，`candidate_pass`可以转为`deterministically_authorized`；
- 当Bootstrap为`required`时，只有`execution_mode=controlled_validation`、当前hash绑定的Bootstrap finalized结果、按需positive attestation、finding映射和external/protected gates全部满足，才能转为`bootstrap_authorized`；
- deterministic-only路径还必须满足`execution_mode=controlled_validation`；`evidence_only`即使历史证据全部显示passed也只能输出historical/candidate状态。Bootstrap为`not_required`时`semantic_review_result=not_required`，只有`required`但尚未执行时才使用`not_run`；
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
- API兼容、账号隔离和Phase诊断均有当前证据；UI capability/style closure若适用，必须由独立Godot审核Skill或目标计划认可的typed external/protected gate提供当前证据，本Skill不得自行生成Godot结论；
- 最终全局审查没有未解决 P0/P1/P2；
- 计划声明的 protected handoff 或外部授权已满足。

## 9. Bootstrap 协作流程

### 9.1 Bootstrap不可变Requirement Decision与派生Execution State

`decide-bootstrap`必须原子生成不可变`bootstrap-requirement-decision.json`，它只决定需求和候选授权路径，不承载后续运行状态：

```json
{
  "schemaVersion": "bootstrap-requirement-decision.v1",
  "acceptanceRunId": "...",
  "acceptanceRunInputHash": "sha256:...",
  "requirement": "required|not_required",
  "requirementSources": [
    {
      "source": "plan|adapter|semantic_partition|code_review_policy|dod_policy|finding_policy|risk_policy|user_request",
      "authorityRefs": ["..."]
    }
  ],
  "reasonCodes": [],
  "semanticPartitionIds": ["referenced-adrs"],
  "inventoryAttestationRequirement": "required|not_required",
  "requiredCompanionCapabilityExpectations": [
    {
      "capabilityId": "acceptance-inventory-attestation",
      "capabilityVersion": "1.0",
      "producerRole": "acceptance_auditor"
    }
  ],
  "deterministicAuthorization": {
    "allowed": false,
    "authorityRefs": [],
    "authorizationScopes": ["first_slice", "phase_exit", "program_dod"],
    "requiredExecutionMode": "controlled_validation"
  },
  "authorizationEffect": "candidate_only|deterministic_authorization_eligible|bootstrap_authorization_pending",
  "requiredEntrySkill": "run-phase-bootstrap-review",
  "requiredControlPlaneRevision": "bootstrap-control-plane.v2",
  "requiredProfile": "bootstrap-implementation-conformance",
  "generatedUtc": "..."
}
```

任一以下条件成立时`requirement=required`：

- 任一被消费partition为`semantic_candidate`；
- 目标计划或adapter明确要求Bootstrap；
- 当前Phase code-review policy binding激活任一required `review_gate`或`hybrid`语义分支；
- 当前DoD authority或finding policy明确要求语义审查；
- 仓库risk policy要求语义审查；
- 用户明确要求完整finding review。

多个条件可以同时成立，必须全部记录到`requirementSources`；任一required来源优先于deterministic-only许可。用户可以通过`user_request`把`not_required`升级为`required`，不能删除其他required来源或降级。`requirementSources`只记录required来源；当且仅当它为空时，`requirement=not_required`。

当`inventoryAttestationRequirement=required`时，decision的`requiredCompanionCapabilityExpectations`必须包含唯一的`acceptance-inventory-attestation@1.0`及`producerRole=acceptance_auditor`；`not_required`时该数组必须为空。decision只声明机器需求，不读取或冻结尚未存在的profile companion policy/schema hash；实际能力和authority hashes由后续`bind-bootstrap-capabilities`验证并冻结。

`requirement=not_required`不等于candidate-only。只有所有被消费partition均为`deterministic_complete`、目标计划或adapter对当前DoD层级明确允许deterministic-only、`execution_mode=controlled_validation`、没有semantic review gate且所有external/protected gates满足时，`authorizationEffect=deterministic_authorization_eligible`；否则为`candidate_only`。`requirement=required`时为`bootstrap_authorization_pending`。`bootstrap_authorized`只允许出现在最终Phase/Program result，不得写回预审decision。

decision一经发布不得修改、替换或追加运行状态。用户授权、Bootstrap run identity、prepared/running/finalized、import和stale状态必须分别来自正式sidecar、append-only events和派生投影。`bootstrap-capability-binding.json.bootstrapRequirementDecisionHash`只能引用这份初始immutable decision。

`bootstrap-execution-state.json`是从events、decision、binding、Bootstrap-owned launch authorization、local authorization import receipt和Bootstrap import envelope确定性重建的派生视图，不是事实权威：

```json
{
  "schemaVersion": "bootstrap-execution-state.v1",
  "acceptanceRunId": "...",
  "bootstrapRequirementDecisionHash": "sha256:...",
  "bootstrapCapabilityBindingHash": null,
  "bootstrapReviewRequestHash": null,
  "bootstrapLaunchAuthorizationImportHash": null,
  "bootstrapImportEnvelopeHash": null,
  "bootstrapRunDir": null,
  "bootstrapReviewId": null,
  "executionState": "not_applicable|awaiting_authorization|awaiting_external|prepared|running|finalized|blocked|stale",
  "authorizationStatus": "not_required|pending|granted|denied|expired|revoked",
  "importStatus": "not_required|not_run|imported|incomplete|stale",
  "derivedFromEventHash": "sha256:...",
  "generatedUtc": "..."
}
```

`requirement=not_required`时派生`executionState=not_applicable`、`authorizationStatus=not_required`和`importStatus=not_required`。required但尚未获得当前launch authorization时为`awaiting_authorization`；外部Bootstrap尚未finalized时为`awaiting_external`。任何输入或authority漂移必须通过新event使投影为`stale`，不得回写decision。

### 9.2 推荐完整流程

```text
实施验收 Skill
  -> prepare冻结run input、expected paths和schema hashes
  -> 生成source inventory、原子条款、base matrix和Phase/Program candidate结果
  -> 运行确定性测试、编译、smoke/readback检查
  -> 计算候选阶段与DoD结果
  -> decide-bootstrap写bootstrap-requirement-decision.json
  -> 若not_required且deterministic_authorization_eligible
       -> 全部Bootstrap-only import/map/approval动作记录not_applicable，不生成Bootstrap/attestation工件
       -> project-acceptance-impact绑定base matrix和external/protected gates
       -> finalize消费candidate+projection，记录authorization_basis=deterministic_only
  -> 若required
       -> bind-bootstrap-capabilities冻结profile/capability/schema/policy身份
       -> semantic partition存在时prepare-attestation生成actual scope和scope-result；否则记录not_applicable
       -> prepare-bootstrap生成bootstrap-review-request.json
       -> 经用户授权后调用同名$run-phase-bootstrap-review入口完成preflight/authorize-launch
       -> Bootstrap控制面仅依据自身review-launch-authorization.json启动reviewers/verifier
       -> import-bootstrap-launch-authorization只读导入该sidecar，供新Skill恢复、import和final acceptance使用
       -> bootstrap-control-plane.v2 / bootstrap-implementation-conformance继续运行reviewers
       -> Blind Hunter
       -> Edge Case Hunter
       -> Acceptance Auditor审计矩阵并按需产生positive-attestation companion candidate
       -> Bootstrap父控制面校验并原子发布Acceptance Auditor formal role bundle
       -> gate/verifier/P2 dispositions/finalize
       -> import-bootstrap生成hash-bound bootstrap-import-envelope.json
       -> map-findings确定性生成finding-to-acceptance mapping companion
       -> 存在需人工映射的finding时执行import-mapping-approval；否则该action记录not_applicable
       -> approval导入后重新运行map-findings，只消费合法receipt
       -> project-acceptance-impact绑定base matrix、mapping、approval和external/protected gates
       -> finalize消费candidate+projection并校验import envelope、attestation、mapping和外部gate
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
  "code_review_policy_path": "policies/phase-service-code-review.v1.json",
  "code_review_policy_hash": "sha256:...",
  "code_review_policy_binding_path": "code-review-policy-binding.json",
  "code_review_policy_binding_hash": "sha256:...",
  "task_checklist_closure_path": "task-checklist-closure.json",
  "task_checklist_closure_hash": "sha256:...",
  "phase_diff_coverage_path": "phase-diff-coverage.json",
  "phase_diff_coverage_hash": "sha256:...",
  "phase_static_analysis_path": "phase-static-analysis.json",
  "phase_static_analysis_hash": "sha256:...",
  "phase_security_scan_path": "phase-security-scan.json",
  "phase_security_scan_hash": "sha256:...",
  "matrix_path": "...",
  "matrix_hash": "sha256:...",
  "bootstrap_requirement_decision_hash": "sha256:...",
  "bootstrap_capability_binding_path": "bootstrap-capability-binding.json",
  "bootstrap_capability_binding_hash": "sha256:...",
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

#### 9.3.1 Reviewer launch authorization

新Skill不得创建竞争性的launch authorization权威。S0必须扩展或supersede仓库级`bootstrap-review-launch-authorization.v1` schema，由Bootstrap控制面继续拥有并生成`review-launch-authorization.json`。该formal sidecar除现有preflight、Artifact View、cost、write/read set和profile绑定外，还必须绑定：

```json
{
  "acceptanceRunId": "...",
  "bootstrapRequirementDecisionHash": "sha256:...",
  "bootstrapCapabilityBindingHash": "sha256:...",
  "bootstrapReviewRequestHash": "sha256:...",
  "candidateContentManifestHash": "sha256:...",
  "codeReviewPolicyBindingHash": "sha256:...",
  "matrixHash": "sha256:...",
  "profilePolicyRevision": "sha256:...",
  "authorizationStatus": "granted|denied",
  "authorizationEventRef": "...",
  "authorizationEventHash": "sha256:...",
  "authorizedScope": ["launch-reviewers", "launch-verifier"],
  "grantedUtc": "...",
  "expiresUtc": null,
  "predecessorAuthorizationHash": null,
  "revocationEventRef": null,
  "revocationEventHash": null
}
```

授权事件必须来自可信用户交互或仓库批准的外部authority，不能由assistant总结、旧session文本或mutable decision代替。授权仅对当前request、candidate、matrix、binding、profile和scope有效；hash漂移、过期、拒绝或撤回后不得启动reviewer/verifier。

新Skill通过`import-bootstrap-launch-authorization`只读校验Bootstrap-owned formal sidecar，并原子生成本地`bootstrap-launch-authorization-import.json` receipt：

```json
{
  "schemaVersion": "bootstrap-launch-authorization-import.v1",
  "acceptanceRunId": "...",
  "bootstrapRequirementDecisionHash": "sha256:...",
  "bootstrapCapabilityBindingHash": "sha256:...",
  "bootstrapReviewRequestHash": "sha256:...",
  "bootstrapRunDir": "logs/ci/...",
  "bootstrapReviewLaunchAuthorizationPath": "review-launch-authorization.json",
  "bootstrapReviewLaunchAuthorizationHash": "sha256:...",
  "authorizationEventHash": "sha256:...",
  "authorizedScope": ["launch-reviewers", "launch-verifier"],
  "status": "imported|denied|expired|revoked|stale",
  "actionEventHash": "sha256:..."
}
```

采用单向授权模型：Bootstrap-owned sidecar是reviewer/verifier启动的唯一权威，Bootstrap不得读取或等待consumer-private receipt。local receipt只证明当前acceptance run已验证该授权，用于本地恢复、`import-bootstrap`和final acceptance lineage，不反向成为Bootstrap启动前置。结构/schema/hash验证失败时保留attempt evidence但不得发布formal receipt；合法的denied/expired/revoked状态应发布非授权receipt用于恢复和审计，但不得被新Skill用于最终授权。

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
  "bootstrapRequirementDecisionHash": "sha256:...",
  "candidateContentManifestHash": "sha256:...",
  "codeReviewPolicyHash": "sha256:...",
  "codeReviewPolicyBindingHash": "sha256:...",
  "taskChecklistClosureHash": "sha256:...",
  "phaseDiffCoverageHash": "sha256:...",
  "phaseStaticAnalysisHash": "sha256:...",
  "phaseSecurityScanHash": "sha256:...",
  "matrixHash": "sha256:...",
  "inventoryAttestationRequirement": "required|not_required",
  "bootstrapCapabilityBindingPath": "bootstrap-capability-binding.json",
  "bootstrapCapabilityBindingHash": "sha256:...",
  "bootstrapLaunchAuthorizationImportHash": "sha256:...",
  "bootstrapReviewLaunchAuthorizationHash": "sha256:...",
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

envelope必须验证run已finalized、immutable requirement decision、capability binding、request、Bootstrap-owned launch authorization和local import receipt全部一致，control-plane/profile/policy/route与binding一致、Phase code-review policy/binding、task checklist、diff coverage、static/security results与candidate manifest和Artifact View一致、required companion capability身份和policy/schema/producer role均匹配、Acceptance Auditor role bundle schema hash一致且formal bundle原子完整、Artifact View和所有formal sidecar hash有效、required layers完成、P0/P1核验闭合、每个accepted P2有合法处置，并且candidate/base matrix/scope-result/target acceptance finding policy与当前acceptance run一致。`review-result.v1`本身不含全部控制面身份，因此缺少launch authorization、review input、Phase policy/result bindings、Artifact View、role bundle、disposition、verifier或required attestation时不得导入。

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
      "affectedPhaseIds": [],
      "checkIdLineageHash": "sha256:...",
      "gateRegistryHash": "sha256:...",
      "phaseGraphHash": "sha256:...",
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

approval schema必须条件验证：`mappingType=check`时`checkIds`非空、`checkIdLineageHash`必填且`gateId/affectedPhaseIds`为空；`mappingType=cross_cutting_gate`时`gateId`和`affectedPhaseIds`非空、`checkIds`为空，`gateRegistryHash`和`phaseGraphHash`必填。两类mapping都必须绑定当前identity/phase revision，不得让同一approval同时表达两类mapping。

`import-mapping-approval`是接收人工approval的唯一正式动作。它只能读取用户或外部authority提供的文件，不得生成或补写approval内容；必须按adapter `mappingApprovalPolicy`验证authority policy、approver role、identity evidence、finding/matrix/lineage/import envelope绑定和expiry，然后把原始输入及hash原子复制为run-scoped formal input，生成`finding-mapping-approval-import.json` receipt并追加action event：

```json
{
  "schemaVersion": "finding-mapping-approval-import.v1",
  "acceptanceRunId": "...",
  "inputPath": "incoming/finding-mapping-approvals.json",
  "inputHash": "sha256:...",
  "acceptedApprovalIds": ["MAP-APPROVAL-001"],
  "rejectedApprovals": [],
  "adapterApprovalPolicyHash": "sha256:...",
  "identityEvidenceHashes": ["sha256:..."],
  "checkIdLineageHash": "sha256:...",
  "gateRegistryHash": "sha256:...",
  "phaseGraphHash": "sha256:...",
  "formalInputPath": "finding-mapping-approvals.json",
  "formalInputHash": "sha256:...",
  "actionEventHash": "sha256:...",
  "status": "imported|partial|rejected|stale"
}
```

成功导入会把此前不含该receipt的mapping结果标记为stale，并令`map-findings`重新成为唯一next action；验证失败时保留attempt evidence但不得发布formal input。`map-findings`只能消费已成功导入且当前hash有效的approval receipt；`partial`只有在rejected approvals全部为非阻断且policy明确允许时才能继续，否则阻断projection/finalize。

当机器判定`requirement=required`且用户尚未授权reviewer时，Skill只能输出候选完成层级，并明确Bootstrap语义审查尚未执行。当`requirement=not_required`、当前DoD层级具有明确deterministic-only authority、`execution_mode=controlled_validation`且其他门禁满足时，可以输出`deterministically_authorized`，不得因reviewer未运行而降级。

## 10. 输出合同

每次运行使用新的目录：

```text
logs/ci/<date>/refactor-implementation-acceptance-<run-id>/
├── acceptance-run-input.json                         [always]
├── baseline-content-manifest.json                    [always]
├── candidate-content-manifest.json                   [always]
├── code-review-policy-binding.json                   [always after domain resolution]
├── task-checklist-closure.json                       [after checklist audit]
├── phase-diff-coverage.json                          [after coverage analysis]
├── phase-static-analysis.json                        [after static analysis/import]
├── phase-security-scan.json                          [after security scan/import]
├── check-id-lineage.json                             [always]
├── acceptance-source-inventory.json                  [always]
├── acceptance-source-clauses.json                    [always]
├── acceptance-evidence-records.json                  [always]
├── implementation-acceptance-matrix.json             [always]
├── implementation-acceptance-matrix.md               [always]
├── phase-graph.json                                   [always]
├── phase-acceptance-candidate.json                    [after evaluate]
├── program-dod-candidate.json                         [after evaluate]
├── acceptance-impact-projection.json                  [after impact projection]
├── phase-acceptance-result.json                       [after finalize]
├── program-dod-result.json                            [after finalize]
├── bootstrap-requirement-decision.json                [always]
├── bootstrap-execution-state.json                     [always, derived]
├── bootstrap-capability-binding.json                  [if Bootstrap required]
├── inventory-attestation-scope.json                   [if attestation required]
├── inventory-attestation-scope-result.json            [if attestation required]
├── bootstrap-review-request.json                      [if Bootstrap required]
├── bootstrap-launch-authorization-import.json          [if launch authorization imported]
├── bootstrap-import-envelope.json                     [after valid Bootstrap import]
├── bootstrap-finding-acceptance-map.json              [after valid Bootstrap import]
├── finding-mapping-approvals.json                     [if approval imported]
├── finding-mapping-approval-import.json               [if approval imported]
├── command-registry-snapshot.json                     [always]
├── acceptance-events.jsonl                            [always]
├── recovery-state.json                                [always]
├── actions/                                           [always]
├── acceptance-report.md                               [after finalize]
└── evidence/                                          [always]
```

`[always]`是完成基础盘点后的正式run最小闭包；`code-review-policy-binding.json`必须在domain resolution后存在，对Phase候选绑定当前policy，对纯Godot等外部域记录`unsupported_code_review_domain`且`authorizes=[]`。task checklist、diff coverage、static和security结果由policy activation与action events决定requiredness；activated check不得以缺文件或空占位表示not-applicable。条件工件只有在对应action合法完成后才存在。schema validator必须按policy binding、`bootstrap-requirement-decision.json`、conditional action DAG和action events计算required artifact set，不得要求空文件占位，也不得把条件工件缺失误报为deterministic-only run不完整。`bootstrap-execution-state.json`可以随events重建，不得成为新的事实权威。candidate结果、impact projection和final result必须使用不同路径；`finding-mapping-approvals.json`保存成功导入后的formal approval input，receipt单独记录导入验证结果和hash lineage。

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

首版只有`controlled_validation`可以产生`deterministically_authorized`或`bootstrap_authorized`。`evidence_only`不得因历史evidence恰好fresh/hash-bound而升级授权；若未来需要复用外部当前证据，必须新增独立的`imported-current-evidence`模式及authority、custody、freshness和导入验证合同，不能改变`evidence_only`既有语义。

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
- companion在Bootstrap尚未运行时不存在；初始run input只冻结capability binding expected path/schema。`bootstrap-requirement-decision.requirement=required`时由`bind-bootstrap-capabilities`冻结profile/capability/schema/policy身份；其中`inventoryAttestationRequirement=required`时，binding再冻结scope expected path、formal attestation artifact name和schema hash，`prepare-attestation`必须产生actual scope result，实际formal attestation路径由import envelope绑定。`not_required`时相关action记录`not_applicable`且不得生成伪binding、scope或attestation。finding map的预期路径和schema hash始终由run input冻结。
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
action-not-applicable
action-waiting-external
action-stale
run-superseded
```

每个action attempt写入`actions/<action-id>/<attempt-id>/`，保存request、resolved inputs、临时输出、stdout/stderr、process result、write manifests和error。正式JSON/Markdown只能由父CLI在schema和hash校验通过后使用同目录临时文件加原子replace发布；失败或partial attempt不得覆盖上一次formal输出。

`action-not-applicable`必须绑定决定其不适用的decision/binding hash、稳定reason code、禁止生成的formal write set和重新适用触发条件；它是可恢复终态，不等于跳过或未运行。

dependency closure必须使用冻结词汇：`completed|not_applicable`为closed；`reserved|running|waiting_external|blocked|failed|stale`为not closed。一个action只有在决定其activation所需的全部上游事实已经closed且fresh后，才能计算activation；不得把未知或未就绪事实当作false。activation=false生成`action-not-applicable`后，该action可以满足下游dependency；activation=true则继续计算readiness。

`action-waiting-external`只用于activation已成立但readiness依赖尚未满足的外部状态，例如Bootstrap尚未finalized或授权sidecar尚未出现；它必须记录等待的predicate、当前external identity/hash、recheck命令和唤醒事件，不得被finalize当作已关闭。

`recovery-state.json`是由events和formal artifact hashes确定性重建的派生视图，不是事实源。首版action workflow严格串行；`inspect-run`先按action DAG计算activation、dependency和readiness，排除已完成且fresh、已合法not-applicable、正在被合法owner执行或被阻断的action，再从ready集合按以下稳定顺序选出唯一`nextAction`：dependency拓扑层级 -> action graph显式`order` -> command registry显式`order` -> `commandId`字典序。activation为false才可not-applicable；activation为true但readiness缺外部输入时必须waiting_external。同一排序键碰撞、未知action或无法产生唯一结果必须失败关闭。`collect-evidence`展开多个`run-command`时也使用同一排序，不得依赖文件枚举、JSON object顺序或进程完成时序。

`inspect-run`必须报告每个action的completed/failed/not_applicable/waiting_external/blocked/running/stale状态、dependency closure、activation/readiness结论、缺失依赖、ready集合、排序依据和唯一`nextAction`；`resume`只能执行该nextAction，已完成或合法not-applicable且hash仍有效的action必须幂等跳过。外部条件满足后waiting action重新进入ready；输入、adapter、validator、command registry、authority或candidate漂移时追加`action-stale`，不得修改旧事件。跨run修复使用新run并以`run-superseded`和`predecessor_run_id`建立关系。

同一run必须使用owner-bound并发锁，绑定PID、process creation identity、token、acquired UTC和formal write set。活锁或重叠write set阻止第二个session；PID已退出、复用或锁未完成提交时可以记录恢复事件后清理。不得仅删除锁文件来宣称恢复，也不得同时启动相同action的两个formal attempt。

## 11. 失败关闭条件

遇到以下情况不得产生通过结论：

- 缺少统一run input或manifest文件、manifest未通过schema、任一required manifest不是`complete`、changed-path/consumer范围不闭合，或manifest path/hash不匹配；
- 初始run input无条件冻结Bootstrap-owned companion/profile/schema身份、保存尚未生成的actual attestation scope hash，后续action回写run input，或scope-result未绑定decision/binding/inventory/clauses/matrix当前hash；
- candidate manifest存在空`roles`、非法change type、缺少删除tombstone、两侧path/hash条件不成立，或deleted旧hash无法在baseline manifest中闭合；
- 找不到阶段权威或 DoD 权威；
- adapter schema/fingerprint/fixture无效、多个adapter冲突、必需策略缺失，或任一partition的抽取模式、extractor/adapter身份或completeness无法证明；
- Phase candidate缺少当前`phase-service-code-review` policy pack或`code-review-policy-binding.json`，policy/schema/authority/candidate hash不匹配，changed Phase path未触发policy，或binding把未知事实当成`not_applicable`；
- activated Phase policy checks未被矩阵`policy_check_refs` exact-cover、同一policy check重复映射、未激活check产生阻断效果，或policy/authority变化后继续使用旧矩阵、finding map或final result；
- 纯Godot候选被声明已通过Phase代码审核，混合候选未隔离`unreviewed_external_domain`却授权全候选Program DoD，或本Skill加载Godot/GdUnit4/Game.Core游戏领域检查冒充Phase policy；
- `review_gate|hybrid`规则仅凭reviewer结论直接阻断、缺gateway/verifier/evidence tuple，`conditional_gate`在没有计划/adapter/仓库authority时被升级为阻断，或固定要求非零finding数量；
- SQL相关Phase改动未执行已证明覆盖全部适用Phase paths的SQL gate、仅运行当前Godot/Game.Core scope的`security_hard_sql_gate.py`便宣称通过、发现插值/format statement仍通过，账号/项目查询缺scope验证，或性能风险只凭猜测阻断而没有query/loop/index/代表性运行证据；
- `PHASE-CR-TEST-002`增量行覆盖率低于85%、用repo总覆盖率替代、Cobertura/candidate/changed-line hash不一致、instrumentable source mapping缺失却被排除，或删除/注释/generated/rename分母规则不可重放；
- 权威任务清单任一required item未勾选、只抽样部分清单、source hash stale，或已勾选item缺implementation/test/evidence仍被当作`verified`；
- required Phase static/security bundle缺失、`requiredChangedPaths`与`readChangedPaths`不等、存在missing path、使用Godot-only scanner冒充Phase覆盖，或required command为`skipped|warn-only|partial|stale|failed`仍授权；
- commit message风格在缺少目标计划、adapter或仓库policy授权时被用于阻断Phase/Program DoD，或commit/dirty-worktree范围与candidate manifest不一致；
- `semantic_candidate`缺少当前hash绑定的`acceptance-inventory-audit-attestation.v1`却声明`semantically_attested_complete`，或虽有attestation但缺少当前partition的hash-bound effective completeness projection仍发生语义晋升；
- inventory attestation scope未覆盖全部semantic partition原始`source_refs`、必要context或三个派生工件，required/read集合不等、missing非空，或source/context hash与candidate manifest不一致；
- 无法把复合条款原子化或建立稳定source clause/check身份，check-ID lineage断裂、碰撞、非法复用tombstone或split/merge无双向关系；
- 97、98、99 或原始来源存在未解释的覆盖缺口；
- 矩阵存在重复、孤立或无来源的 `check_id`；
- Bootstrap attestation后回写base inventory的completeness，Bootstrap后回写base matrix的finding/effective gate字段，base inventory/matrix hash与attestation/request/import不一致，或impact projection未绑定当前partition/attestation/scope-result/matrix/finding/approval/external gate身份与hash；
- `evaluate`与`finalize`共用或覆盖Phase/Program result路径，candidate错误产生授权，或final result缺candidate/projection绑定；
- applicability/disposition/evaluation组合违反第6.2节不变量；
- 任一check缺少`evidence_requirements`，或`verified`未满足其required kinds、最小数量、freshness或豁免合同；
- 证据路径、hash、candidate、validator、environment或运行范围不匹配；
- phase graph存在环、未知前置、非法汇合或被绕过的activation predicate；
- 缺少目标计划finding阻断策略；
- `10-*` 被用于授权 Program DoD；
- `finding_policy.blocking_severities`中的未解决finding被隐藏在`clean`、`advisory`或文本总结下；
- immutable Bootstrap requirement decision与`requirementSources`矛盾、遗漏required来源、被binding后修改、写入finalized/authorization状态，或派生execution state与events/sidecars不一致；
- `requirement=required`时Bootstrap缺当前Bootstrap-owned launch authorization或可信authorization event仍启动reviewer/verifier，Bootstrap错误读取或等待consumer-private local receipt，或新Skill最终授权缺local authorization import receipt；授权scope/hash过期/撤回、controlPlaneRevision/profile capability不匹配，或Bootstrap结果未finalize、hash不匹配、scope不完整、required layer未完成；
- `requirement=not_required`时semantic result不是`not_required`，或缺少当前DoD层级的明确deterministic-only authority、`execution_mode=controlled_validation`、scope匹配或external/protected gate，却声明`deterministically_authorized`；
- `evidence_only`产生`deterministically_authorized`或`bootstrap_authorized`，或required Bootstrap尚未运行却使用`semantic_review_result=not_required`；
- required Bootstrap缺少当前immutable capability binding，binding与decision/profile/schema registry不一致，或not-required路径生成binding/scope/request条件工件；
- required companion capability ID/version、profile companion policy hash、schema hash或producer role缺失/不匹配，或仅凭control plane/profile名称宣称能力存在；
- Acceptance Auditor required companion缺失、schema非法、attempt/scope不匹配、formal role bundle非原子发布，或只发布finding output后仍finalize；
- `bootstrap-import-envelope.json`缺失或未绑定immutable requirement decision、launch authorization及receipt、review input、Artifact View、Acceptance Auditor role bundle、companion capability、final result、verifier、P2 dispositions、formal attestation和当前candidate/base matrix；
- Bootstrap finding映射sidecar缺失或stale，阻断finding无法稳定映射到check或cross-cutting gate；
- 人工finding mapping approval未通过`import-mapping-approval`正式导入，缺身份/权限/authority policy/finding hash/check-ID lineage/matrix/import envelope绑定，cross-cutting mapping缺`affectedPhaseIds`、`gateRegistryHash`或`phaseGraphHash`，已过期，或映射到tombstoned check；
- Bootstrap使用target acceptance finding policy改变自身severity、verifier、P2 disposition或finalize规则，或导入后policy ref/hash与当前acceptance run不一致；
- companion schema path/hash与capability binding不一致，或把Bootstrap v2 formal attestation误报为新Skill自行生成；
- required artifact set与requirement decision/conditional action DAG/action events不一致、合法条件工件缺失被空文件伪装，或approval导入后缺formal input/receipt；
- required deterministic、semantic或external gate为`not_run`、`incomplete`或`stale`却声明authorized，或external/protected gate仍以无`gateId`、schema、authority、scope和status的裸hash参与projection/finalize；
- evidence record使用自由command字符串冒充机器身份、controlled invocation缺command ID/registry/invocation/process-result绑定，imported evidence缺来源/custody/freshness receipt，或controlled validation使用未知command、shell字符串、未类型化path、非allowlist环境、缺timeout/process-tree收口/写manifest；
- action event缺失/重写、partial attempt覆盖formal输出、同action并发运行、锁身份不明、dependency closure未严格使用`completed|not_applicable`为closed和`reserved|running|waiting_external|blocked|failed|stale`为not closed、conditional DAG activation/readiness/not-applicable/waiting-external计算错误、approval导入未使mapping/projection stale、active branch未闭合就finalize，或resume跳过唯一nextAction；
- S0代码/profile/schema已变更但durable standard、Skill/reference、operator docs、schema registry或ADR-0041复核未同步，却声明`bootstrap_companion_ready`；
- protected authority 尚未通过却声明其授权层级。

## 12. 实施 change sets 与最小包结构

### 12.1 Change set门禁

实现必须把以下change set作为机器可判定的独立谓词，而不是只按章节顺序手工推进：

| Change set | 内容 | 前置 | Exit predicate | 仅授权 |
| --- | --- | --- | --- | --- |
| S0 Bootstrap v2 companion prerequisite | profile capability、companion/role-bundle schemas、Acceptance Auditor双输出、Artifact View绑定、父控制面校验、Bootstrap-owned单向launch authorization、原子role bundle、生命周期测试、durable standard/Skill/operator projection、ADR-0041复核和`bootstrap-skill-route`复审 | 无；可与S1-S3在写集隔离时独立推进 | `bootstrap_companion_ready` | S4 semantic integration可以开始，不授权新Skill发布 |
| S1 新Skill deterministic core | schemas、adapter、run input、complete/partial/unavailable manifests、inventory、check lineage、Phase code-review policy pack/binding、task checklist parser、diff-coverage analyzer、Phase-aware static/security scanner contracts和command-ID evidence | 无 | `deterministic_core_ready` | S2可以开始，不授权semantic partition或DoD |
| S2 矩阵与阶段计算 | base matrix、policy-check exact coverage、task checklist mapping、85% diff-coverage gate、static/security result消费、candidate results、impact projection schema及deterministic branch、正交状态、phase DAG、DoD计算、typed external/protected gate results和7-07 adapter fixture | S1 | `matrix_phase_ready` | deterministic candidate计算，不授权最终DoD |
| S3 执行控制 | conditional action DAG、checklist/static/security/diff-coverage actions、action events、waiting/not-applicable、locking、deterministic nextAction、inspect/resume/stale | S1、S2 | `execution_control_ready` | controlled validation可以使用，不授权Bootstrap集成 |
| S4 Bootstrap集成 | immutable requirement decision、capability binding、request、Bootstrap-owned单向launch authorization扩展、consumer-private import receipt、execution projection、import envelope、Phase policy Artifact View/context、finding map、approval import、semantic completeness projection和scope completeness计算 | S0、S1、S2、S3 | `bootstrap_integration_ready` | semantic path和Bootstrap授权候选，不授权完整发布 |
| S5 Finalize与验收 | candidate/final custody、report、Phase policy positive/negative/mutation fixtures、85% coverage边界/分母/source-map/rename/generated fixtures、checkbox勾选但无证据fixture、wrong-scope/skipped static-security fixtures、纯Godot拒绝与mixed-domain隔离fixture、7-07真实fixture、fresh-context观察和完整包验证 | S0-S4 | `skill_release_ready` | 新Skill完整发布候选；仍不替代目标计划protected/release authority |

S0未完成时可以开发和验证S1-S3 deterministic core，但必须把所有semantic partition结果保持为candidate，不能通过需要positive attestation的RA，不能进入S4 semantic integration，也不能声明`skill_release_ready`。每个predicate必须输出当前candidate/source/validator hashes、required checks、failed rule IDs、`authorizes`和`does_not_authorize`；低层predicate不得推导高层完成。

`bootstrap_companion_ready`的required outputs必须至少绑定：`docs/standards/bootstrap-review-control-plane.md`、仓库级`run-phase-bootstrap-review/SKILL.md`及相关reference、`review-profiles.v1.json`、companion/role-bundle schema registry、扩展或supersede后的Bootstrap-owned launch authorization schema、operator documentation、测试/fixture evidence和`bootstrap-skill-route`复审结果。S0必须复核`docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`：若通用协议变化影响其决策或边界，更新或supersede现有ADR集合；若所有权决策不变，也必须生成hash-bound no-change rationale。不得无依据宣称“一定不需要ADR更新”。

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
│   ├── code-review-policy-pack.v1.schema.json
│   ├── code-review-policy-binding.v1.schema.json
│   ├── phase-diff-coverage-result.v1.schema.json
│   ├── task-checklist-closure.v1.schema.json
│   ├── phase-scan-bundle-result.v1.schema.json
│   ├── inventory-attestation-scope.v1.schema.json
│   ├── inventory-attestation-scope-result.v1.schema.json
│   ├── acceptance-source-inventory.v1.schema.json
│   ├── acceptance-source-clauses.v1.schema.json
│   ├── check-id-lineage.v1.schema.json
│   ├── implementation-acceptance-matrix.v1.schema.json
│   ├── acceptance-impact-projection.v1.schema.json
│   ├── acceptance-evidence-record.v1.schema.json
│   ├── phase-graph.v1.schema.json
│   ├── phase-acceptance-candidate.v1.schema.json
│   ├── phase-acceptance-result.v1.schema.json
│   ├── program-dod-candidate.v1.schema.json
│   ├── program-dod-result.v1.schema.json
│   ├── acceptance-adapter.v1.schema.json
│   ├── acceptance-command-registry.v1.schema.json
│   ├── acceptance-action-event.v1.schema.json
│   ├── acceptance-action-result.v1.schema.json
│   ├── acceptance-recovery-state.v1.schema.json
│   ├── acceptance-run-lock.v1.schema.json
│   ├── bootstrap-requirement-decision.v1.schema.json
│   ├── bootstrap-execution-state.v1.schema.json
│   ├── bootstrap-capability-binding.v1.schema.json
│   ├── bootstrap-launch-authorization-import.v1.schema.json
│   ├── bootstrap-review-request.v1.schema.json
│   ├── bootstrap-import-envelope.v1.schema.json
│   ├── bootstrap-finding-acceptance-map.v1.schema.json
│   ├── finding-mapping-approvals.v1.schema.json
│   └── finding-mapping-approval-import.v1.schema.json
├── adapters/
│   ├── generic-registry-backed.v1.json
│   └── 2026-07-07-gdd-to-module.v1.json
├── policies/
│   └── phase-service-code-review.v1.json
├── commands/
│   ├── generic-controlled-validation.v1.json
│   ├── phase-dotnet-coverage.v1.json
│   ├── phase-static-analysis.v1.json
│   └── phase-security-scan.v1.json
└── scripts/
    ├── acceptance_cli.py
    ├── fixtures/
    └── tests/
```

`acceptance_cli.py`至少提供以下状态转换或子命令：

```text
prepare
  -> resolve-code-review-policy
  -> inventory
  -> audit-task-checklist
  -> collect-evidence
  -> run-static-analysis
  -> run-security-scan
  -> analyze-diff-coverage
  -> evaluate
  -> render
  -> decide-bootstrap
  -> bind-bootstrap-capabilities
  -> prepare-attestation
  -> prepare-bootstrap
  -> import-bootstrap-launch-authorization
  -> import-bootstrap
  -> map-findings
  -> import-mapping-approval
  -> project-acceptance-impact
  -> finalize
```

CLI还必须提供`run-command`、`inspect-run`和`resume`。只提供`validate_acceptance.py`不足以说明policy如何激活、任务清单如何闭合、增量覆盖率如何计算、static/security scope如何证明、矩阵如何生成、candidate如何冻结以及Bootstrap结果如何导入。`resolve-code-review-policy`根据candidate manifest和adapter生成immutable binding并拒绝未支持域；`audit-task-checklist`解析权威清单并映射矩阵/证据；`run-static-analysis`与`run-security-scan`只在controlled mode执行typed commands，evidence-only只能导入并验证当前结果；`analyze-diff-coverage`消费当前changed-line set和Cobertura evidence；`decide-bootstrap`只写immutable requirement decision；`bind-bootstrap-capabilities`条件冻结profile/capability/schema/policy身份；`prepare-attestation`按需生成actual scope/result；`import-bootstrap-launch-authorization`只导入Bootstrap-owned launch sidecar；`import-bootstrap`只接受有效v2 import envelope；`map-findings`保持确定性；`import-mapping-approval`只验证并导入外部approval；`project-acceptance-impact`生成审后effective投影；`finalize`只发布final result，不覆盖candidate、policy binding或base matrix。每个子命令都必须通过conditional action DAG读取前序机器工件、验证hash并只原子发布新的run-scoped输出。

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

触及route的Phase服务能力声明、注入、readback和证据消费必须启用并验收；实际Godot实现只接受独立Skill或计划认可的typed external/protected gate。未触发的能力包必须有可审核`not_applicable`，不得静默缺失或由本Skill伪造Godot结论。

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

当Bootstrap被机器判定为`required`时，未授权、未运行、未finalized、旧hash、incomplete或scope不匹配只能输出候选完成层级，且无效结果不能导入。`requirement=not_required`时按deterministic-only authorization合同判定，不得机械降级为candidate。需要语义授权时必须通过同名入口和`bootstrap-control-plane.v2`，semantic partition还要求Bootstrap v2 formal inventory attestation companion。Bootstrap`clean`不能替代矩阵、DoD门禁或protected authority。

### RA-SKILL-013：原子化和ID稳定性

复合条款必须拆分为多个原子check；纯行号、换行或顺序变化不得更换ID。registry、adapter和semantic ID必须遵守版本化算法；split/merge/supersede/retire必须保留双向lineage和tombstone，语义变化必须使旧check和证据stale。

### RA-SKILL-014：状态正交性

后续阶段要求已实现但predecessor未通过时，base matrix必须保持`disposition=verified`、`evaluation_state=evaluated`和`deterministic_gate_state=blocked`，不得丢失实施事实；finding或外部门禁只能改变impact projection中的effective state。

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

run input必须引用实际存在、schema合法且hash匹配的baseline和candidate manifest。`complete`状态必须保存完整path/roles/hash和candidate diff；`partial|unavailable`必须保存coverage gaps并固定`authorizes=[]`。删除必须有tombstone并能回查baseline旧hash，rename必须同时记录旧、新路径；缺文件、空占位、仅有聚合hash/Git revision或非complete manifest时不得授权。

### RA-SKILL-029：Gate和DoD状态词汇

deterministic、semantic、external和effective结果只能使用本规格枚举。Bootstrap为`not_required`时semantic结果必须为`not_required`，只有required但尚未执行时才可为`not_run`；required gate为`not_run`、`incomplete`或`stale`时不得授权。计划未定义DoD层级时必须使用`not_defined`并记录authority search和reason。

### RA-SKILL-030：Attestation冻结时序

初始run input只能冻结capability binding expected path及新Skill-owned binding schema。`decide-bootstrap`后由`bind-bootstrap-capabilities`条件冻结Bootstrap profile/capability/schema/policy身份，随后`prepare-attestation`按attestation requirement生成actual scope和scope-result；初始输入无条件依赖S0 schema、提前保存actual hash、回写run input、跳过binding或scope-result未绑定当前派生工件时必须拒绝。

### RA-SKILL-031：Action恢复协议

每个subcommand必须产生append-only action events和immutable attempt evidence；partial attempt不得覆盖formal输出。`inspect-run`和`resume`必须按conditional action DAG从events重建activation/readiness、ready集合和唯一next action，并正确处理`not_applicable`、`waiting_external`、stale、reactivation、supersession和并发锁。

### RA-SKILL-032：安全Command Registry

`controlled_validation`只能通过stable command ID执行结构化argv。shell字符串、未知command、未类型化path、非allowlist环境、缺timeout/process-tree收口、未声明写入或缺stdout/stderr/write-manifest evidence必须失败关闭。

### RA-SKILL-033：Adapter Schema

每个adapter必须通过正式schema、plan fingerprint、fixture和validator验证，并完整声明source partitions、extraction、phase graph、DoD、finding/evidence policy、mapping approval policy、capability activation、external/protected gates、authorization scope、conditional action graph、command refs和check-ID policy。

### RA-SKILL-034：Check ID Lineage

验证registry、adapter、semantic ID生成算法以及split/merge/supersede/retire/tombstone/collision场景。旧finding和evidence必须能沿lineage解析，碰撞不得用随机后缀静默修复。

### RA-SKILL-035：Bootstrap决策状态

Bootstrap requirement decision必须immutable且只由全部`requirementSources`确定；reviewer/verifier launch authorization只由Bootstrap-owned sidecar拥有，local import receipt只拥有consumer侧校验与导入事实，execution state由events/binding/import确定性派生。`not_required`投影为`not_applicable`；required路径按`awaiting_authorization -> awaiting_external|prepared -> running -> finalized`推进，并允许进入`blocked|stale`。不得修改decision推进状态、让Bootstrap等待local receipt，或跳过授权、control-plane capability和hash freshness门禁。

### RA-SKILL-036：Bootstrap Import Envelope

只有同时绑定immutable requirement decision、capability binding、Bootstrap-owned launch authorization及local receipt、`bootstrap-control-plane.v2`、profile/policy/route、companion capability、Acceptance Auditor role bundle、review input、Artifact View、final result、verifier、P2 dispositions、formal attestation、target acceptance finding policy和当前candidate/base matrix的import envelope才能参与授权。

### RA-SKILL-037：人工Mapping Approval

语义相似不能自动映射finding。人工approval必须通过`import-mapping-approval`按adapter policy验证并绑定有权身份、finding hash、mapping目标、matrix、check-ID lineage和import envelope；check mapping与cross-cutting mapping条件字段必须互斥完整，过期、无权、未经正式导入或目标已tombstone时必须拒绝。

### RA-SKILL-038：单一语义权威

需要正向attestation时，必须由同一Bootstrap v2 Acceptance Auditor会话和父控制面formal companion完成。新Skill启动第二个semantic auditor、直接写formal attestation或把行为加入7-12兼容适配器时必须拒绝。

### RA-SKILL-039：Deterministic-only最终授权

当所有被消费partition均为`deterministic_complete`、计划或adapter对当前DoD层级明确允许deterministic-only acceptance、没有semantic review gate且external/protected gates全部满足时，`requirement=not_required`可以产生`deterministically_authorized`。不得把`not_required`机械降级为candidate-only，也不得把未覆盖当前层级的泛化许可当作授权。

### RA-SKILL-040：Required来源否决优先级

任一plan、adapter、semantic partition、DoD/finding policy、risk policy或user request来源要求Bootstrap时，`requirement`必须为`required`并保留全部authority refs。deterministic-only许可不得覆盖、删除或降级这些来源；完成Bootstrap v2及其适用合同前不得产生最终授权。

### RA-SKILL-041：Companion capability身份

需要positive attestation时，decision必须声明`acceptance-inventory-attestation@1.0`与`producerRole=acceptance_auditor`需求；capability binding、request、Bootstrap profile和import envelope必须进一步一致绑定profile companion policy hash和schema hash。只匹配control plane/profile名称、只检查schema文件存在或任一身份漂移时必须拒绝。

### RA-SKILL-042：Acceptance Auditor原子Role Bundle

required companion与finding reviewer output必须来自同一Acceptance Auditor attempt，并在父控制面完成schema、scope、hash、prompt、Artifact View和attempt identity校验后原子发布。缺失、非法、stale、跨attempt或partial publish必须令Bootstrap现有gate `status=incomplete`并产生稳定reason code，保留candidate evidence但不得finalize。

### RA-SKILL-043：Mapping Approval正式导入

人工approval只能通过`import-mapping-approval`导入。该动作必须按adapter policy验证authority、approver role、identity evidence、expiry以及finding/matrix/lineage/import envelope绑定，原子发布formal input和receipt；Skill自行生成、自由文本身份或未经导入的approval不得被`map-findings`消费。

### RA-SKILL-044：目标Finding Policy隔离

Bootstrap request和import lineage必须绑定target acceptance finding policy ref/hash，但Bootstrap不得用该策略改变自身severity、verifier、P2 disposition或finalize规则。新Skill只能在合法导入后使用该策略计算阶段/DoD阻断；策略漂移使结果stale。

### RA-SKILL-045：Deterministic Next Action

ready actions必须按conditional DAG dependency拓扑、action显式order、command registry order和command ID字典序确定唯一`nextAction`。排序碰撞、未知action或依赖文件枚举/完成时序时必须失败关闭；activation false与readiness未满足必须分别投影为not-applicable和waiting-external，`inspect-run`报告依据，`resume`只能执行唯一ready动作。

### RA-SKILL-046：Change Set授权边界

S0-S5必须分别产生hash-bound predicate结果及精确`authorizes/does_not_authorize`。S0未完成时允许S1-S3 deterministic core推进，但semantic partition不得完成、S4不得通过且S5不得声明`skill_release_ready`；任一低层predicate不得推导高层发布或目标计划DoD。

### RA-SKILL-047：Evidence-only授权边界

首版`evidence_only`只能产生historical/candidate结果，不得产生`deterministically_authorized`或`bootstrap_authorized`。任何最终实施验收授权都必须来自`controlled_validation`；未来若引入外部当前证据，必须新增独立模式和authority/custody/freshness/import合同，不得改变`evidence_only`语义。

### RA-SKILL-048：条件工件闭包

validator必须根据Bootstrap requirement decision、capability binding、conditional action DAG和action events计算required artifact set。Bootstrap request/binding、launch authorization receipt、attestation scope、import envelope、finding map、approval input/receipt、impact projection及final result只能在对应条件成立时要求存在；不得创建空文件占位，也不得因合法条件工件不存在而判定deterministic-only run失败。

### RA-SKILL-049：条件Capability Binding

初始run input不得依赖Bootstrap-owned companion schema。Bootstrap required时必须由`bind-bootstrap-capabilities`生成immutable、hash-bound binding；not-required时该动作及attestation/prepare-bootstrap记录`not_applicable`且不生成工件。required binding缺失、stale或被回写时必须拒绝。

### RA-SKILL-050：S0 Durable Authority Projection

`bootstrap_companion_ready`必须绑定Bootstrap durable standard、仓库级Skill/reference、profile/schema registry、operator documentation、fixture/test evidence、route review和ADR-0041复核结果。缺少任一required projection、hash不一致或无依据跳过ADR影响分析时不得通过S0。

### RA-SKILL-051：Bootstrap Action顺序

conditional action DAG必须覆盖所有Bootstrap-only action、mapping approval、impact projection和finalize branch closure。Bootstrap not-required时全部Bootstrap-only action合法not-applicable；required但外部结果未就绪时相关action waiting-external；无approval需求时approval action合法not-applicable。任何active branch未闭合便finalize、approval导入未重开mapping/projection或action缺少必填控制字段时必须拒绝。

### RA-SKILL-052：Immutable Bootstrap工件分权

`bootstrap-requirement-decision.json`必须永久不可变且不得包含mutable execution/review identity；Bootstrap-owned sidecar拥有reviewer/verifier launch authorization，local import receipt只拥有consumer验证与导入事实；`bootstrap-execution-state.json`只能从events及sidecars重建。binding引用非初始decision revision、decision被修改、receipt反向成为Bootstrap启动权威或派生state反向成为权威时必须拒绝。

### RA-SKILL-053：Reviewer Launch Authorization

Bootstrap reviewer/verifier只能由仓库级Bootstrap-owned launch authorization控制启动，不得依赖consumer-private receipt。新Skill的local import receipt必须绑定当前request、candidate、base matrix、binding、profile、scope和可信authorization event，用于恢复、Bootstrap结果导入和最终验收；新Skill复制授权schema、旧session文本授权或无receipt声明最终授权必须拒绝。

### RA-SKILL-054：Base Matrix与Impact Projection

base matrix不得包含或回写Bootstrap finding/effective gate状态。`acceptance-impact-projection.json`必须绑定当前base matrix、finding map、approval receipts、typed external/protected gate results、gate registry和phase graph，并独立拥有effective finding refs、blocking reasons和gate state；任一输入漂移使projection stale。

### RA-SKILL-055：Candidate与Final Result保管

`evaluate`只能发布hash-bound Phase/Program candidate并固定`authorizes=[]`；`finalize`必须消费candidate和current projection后发布不同路径的final result。共用路径、原地升级、candidate授权或失败attempt覆盖formal final result必须拒绝。

### RA-SKILL-056：Manifest可用性状态

baseline/candidate manifest文件始终必须存在并通过schema。`complete`要求零coverage gap；`partial|unavailable`必须有结构化缺口和`authorizes=[]`，使candidate completeness为incomplete且仅允许evidence-only诊断。缺文件、空占位或非complete manifest进入授权路径必须拒绝。

### RA-SKILL-057：Approval Lineage与Receipt

check mapping approval必须绑定非空check IDs和check-ID lineage hash；cross-cutting approval必须绑定gate ID和affected phase IDs且check IDs为空。导入receipt必须记录输入/正式工件hash、accepted/rejected IDs、adapter policy、identity evidence、lineage和action event；字段混用、receipt不完整或partial rejection非法放行必须拒绝。

### RA-SKILL-058：Evidence Invocation Identity

controlled invocation evidence必须绑定stable command ID、command registry hash、invocation hash和process-result path/hash，不得使用自由command字符串。imported evidence必须绑定source/custody/freshness receipt且不能越过运行模式授权边界；两种origin条件字段混用或缺失必须拒绝。

### RA-SKILL-059：Conditional Branch Closure

deterministic和semantic branch必须分别由DAG谓词闭合，并在current impact projection完成后才允许finalize。not-required Bootstrap import/map action保持ready、无approval需求阻断finalize、waiting-external被误报not-applicable、或finalize先于active branch closure时必须拒绝。

### RA-SKILL-060：Semantic Completeness Projection

base inventory必须永久保留抽取时completeness。semantic attestation后的`effectiveCompleteness`只能由impact projection拥有，并绑定partition、attestation和scope-result hash；projection必须同时计算全run `effectiveOverallCompleteness`和每个Phase/DoD消费范围的`scopeEffectiveCompleteness`。回写inventory、缺projection晋升或用无关partition污染scope结果必须拒绝。

### RA-SKILL-061：单向Bootstrap启动权威

Bootstrap-owned launch authorization是reviewer/verifier启动的唯一权威，Bootstrap不得读取或等待新Skill local receipt。local receipt只用于consumer恢复、Bootstrap结果导入和最终验收lineage；把receipt作为Bootstrap启动前置、缺receipt阻止Bootstrap自身启动或无receipt声明新Skill最终授权必须拒绝。

### RA-SKILL-062：Deterministic Gate所有权

base matrix的`deterministic_gate_state`只能消费deterministic predecessor、applicability、evidence、authority和phase activation。Bootstrap finding、mapping approval、external/protected gate只能由impact projection拥有；同一影响写入两层或在base matrix引用finding/external gate必须拒绝。

### RA-SKILL-063：Dependency Closure语义

dependency只有`completed|not_applicable`视为closed；`reserved|running|waiting_external|blocked|failed|stale`均不closed。activation只能在决定它的全部上游事实closed且fresh后计算；合法not-applicable可以满足下游dependency，未知事实不得按false关闭。

### RA-SKILL-064：Typed External/Protected Gates

impact projection中的每个external/protected gate必须绑定gate ID/class、result path/hash、schema path/hash、authority、authorization scopes和status，并绑定gate registry与phase graph hash。裸hash数组、重复/未知gate、scope不匹配或cross-cutting approval缺gate registry/phase graph identity时必须拒绝。

### RA-SKILL-065：Phase Policy激活与域隔离

Phase changed path、consumer或adapter触发时，必须加载当前`phase-service-code-review` pack并生成hash-bound binding；纯Godot候选必须返回`unsupported_code_review_domain`，混合候选必须隔离`unreviewed_external_domain`。漏激活Phase policy、加载Godot/GdUnit4/Game.Core游戏检查或未获外部审核便授权混合候选Program DoD必须拒绝。

### RA-SKILL-066：Policy Check Exact Coverage

每个activated `policyCheckId`必须恰好映射一个矩阵`check_id`，并绑定当前policy、authority、candidate和applicability evidence。重复映射、漏项、inactive check产生阻断、policy漂移后沿用旧矩阵或以文本清单代替机器policy必须拒绝。

### RA-SKILL-067：确定性与Review Gate分权

`deterministic|review_gate|hybrid|conditional_gate`必须按第5.3节执行。reviewer finding未经gateway和所需verifier不得阻断；conditional rule缺少计划/adapter/仓库authority时不得升级；deterministic validator不得用关键词或固定finding数量冒充行为证明。

### RA-SKILL-068：Phase代码审核闭包

适用的handler/service/consumer同步、schema与SSoT ownership、共享LLM/Codex复用、错误处理、change-type测试、SQL hard gate、secret/auth/account/path边界、bounded query/index/N+1风险和resource lifecycle检查必须全部具有合法结论与当前证据。任一required check缺失、stale或被无证据`not_applicable`隐藏时不得授权对应Phase/DoD。

### RA-SKILL-069：Commit与变更谱系权限

baseline/candidate/dirty worktree/proposed commit set必须与content manifest闭合。commit message清晰度只有在目标计划、adapter或仓库policy明确授权时才是阻断门禁；无authority的措辞偏好只能advisory。范围不闭合、遗漏changed file或无权以message风格阻断必须拒绝。

### RA-SKILL-070：85%增量Diff覆盖率

`PHASE-CR-TEST-002`必须由当前baseline/candidate diff、candidate manifest和fresh Cobertura确定性计算；新增/修改可执行Phase C#行覆盖率必须至少85%。repo总覆盖率替代、source mapping缺失、错误排除分母、旧coverage report或低于阈值仍通过必须拒绝。

### RA-SKILL-071：任务清单勾选与证据闭包

adapter声明的全部权威任务清单required items必须完整抽取、勾选并映射当前matrix/evidence。未勾选、只抽样、stale source、checked但无实施/测试证据或用checkbox直接产生`verified`必须拒绝。

### RA-SKILL-072：Phase静态检查Scope闭包

`PHASE-CR-STATIC-001`必须绑定typed command、tool/process hash和全部适用Phase changed paths；C#、Phase Python、browser或contract类型触发的required static command不得skip/warn/partial。read scope不完整、未知tool或仅使用模板/Godot分析器必须拒绝。

### RA-SKILL-073：Phase安全扫描Scope闭包

`PHASE-CR-SEC-003`必须证明Phase security bundle覆盖全部适用changed paths及SQL/path/secret/audit/process/network规则。Godot/Game.Core-only scanner、missing path、stale/partial结果、未处置required finding或进程失败仍授权必须拒绝。

## 14. 必测反例

后续 Skill 至少应包含以下负例：

1. `verified` 行只有测试文件路径，没有本次执行证据。
2. `semantic_candidate`未经当前hash绑定的正向inventory attestation便声明`semantically_attested_complete`。
3. Phase 0A未通过，但Phase 1被声明通过。
4. 已实现的Phase 3条目因Phase 2未通过而被错误改写为实施`missing`。
5. 被触及route缺少Phase服务侧Phase 0B能力声明/readback/证据消费，或本Skill用自身结论替代实际Godot外部门禁。
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
47. `evidence_only`矩阵、历史测试和全部引用证据均显示passed，却被错误声明`deterministically_authorized`或`bootstrap_authorized`。
48. deterministic-only run因没有空`bootstrap-review-request.json`、attestation scope或import envelope而失败；或approval已成功导入却缺少`finding-mapping-approval-import.json` receipt仍finalize。
49. S0 companion schema尚不存在时，初始run input仍要求其path/hash导致S1 prepare失败；或decision后回写run input补入schema以掩盖时序循环。
50. 代码、profile和测试已支持companion，但`docs/standards/bootstrap-review-control-plane.md`、仓库级Skill/reference、operator docs或ADR-0041复核缺失，仍声明`bootstrap_companion_ready`。
51. adapter/CLI在`decide-bootstrap`前执行`prepare-attestation`，或Bootstrap not-required时仍生成binding、scope、scope-result或review request。
52. 分别验证`bootstrap-requirement-decision-mutated-after-binding`、`binding-consumes-noninitial-decision-revision`、`finalized-state-written-into-frozen-decision`和`authorization-status-changed-without-sidecar`均失败，且immutable decision保持不变。
53. Bootstrap reviewers依据旧session文本或过期Bootstrap-owned authorization启动；或Bootstrap等待consumer local receipt才启动；或新Skill缺local receipt仍声明最终授权。
54. Bootstrap完成后把finding refs或effective gate state回写base matrix，导致request/import matrix hash stale；或projection使用旧finding/approval/external gate hash仍被接受。
55. `evaluate`把candidate写入final result路径，`finalize`原地升级candidate，或失败attempt覆盖上一份合法Phase/Program final result。
56. 分别验证`not-required-import-bootstrap-remains-ready`、`not-required-map-findings-remains-ready`、`no-approval-import-action-blocks-finalize`、`approval-import-does-not-reactivate-map-findings`和`finalize-selected-before-active-branch-closure`均失败。
57. baseline或candidate覆盖不可获得时省略manifest/创建空文件，或`status=partial|unavailable`仍进入deterministic/Bootstrap授权路径。
58. check approval缺`checkIdLineageHash`，cross-cutting approval缺`affectedPhaseIds`，或approval receipt缺policy/identity/lineage/formal input/action event hash仍参与projection。
59. controlled evidence只保存自由`command`字符串，或缺command registry/invocation/process-result绑定；imported evidence缺source/custody/freshness receipt却被当作当前执行证据。
60. Bootstrap attestation通过后直接改写source inventory；或finalize未通过hash-bound partition projection便宣称`semantically_attested_complete`；或无关candidate partition错误阻断当前Phase scope。
61. Bootstrap把`bootstrap-launch-authorization-import.json`作为reviewer启动前置并等待新Skill回执，形成双向握手；或新Skill把local receipt当成Bootstrap启动权威。
62. base matrix的`deterministic_gate_state`引用Bootstrap finding或external/protected gate，导致同一阻断同时出现在base matrix和impact projection。
63. activation所需上游事实仍为waiting/failed/stale却被当作false生成not-applicable；或合法not-applicable未被视为closed，导致下游永远无法ready。
64. impact projection只保存external/protected gate裸hash，没有gate ID/schema/authority/scope/status；或cross-cutting approval缺gate registry/phase graph hash仍通过。
65. candidate manifest触及`PhaseA.Platform/**`或Phase脚本，但未激活Phase policy；或纯Godot候选被声明通过Phase代码审核；或mixed-domain候选未隔离Godot范围便授权Program DoD。
66. `PHASE-CR-SEC-001`等activated policy check没有矩阵行、被映射到两个active check、policy hash变化后旧矩阵仍有效，或inactive policy check被用作阻断项。
67. reviewer仅凭“可能有N+1”直接给出阻断，没有query/loop/consumer证据和gateway；或commit message措辞在没有authority时被升级为Program blocker。
68. SQL插值被Phase-scoped SQL gate检出仍通过；handler吞掉异常或忽略process结果仍标记verified；账号查询没有cross-account denial证据；共享LLM调用绕过统一入口却被称为复用完成。
69. commit只包含部分changed files、dirty worktree未进入candidate manifest，或提交信息引用旧Task/ADR却仍被当作当前候选谱系证据。
70. repo总体行覆盖率为95%，但本次Phase增量可执行行只覆盖84.9%仍通过；或Cobertura缺一个changed source便把它静默排除；或rename/generated/comment规则错误缩小分母。
71. 任务清单所有框都写成`[x]`，但一个required item没有implementation/test/evidence映射仍通过；或只扫描`08-*`而遗漏adapter声明的另一份权威task list。
72. `scripts/sc/analyze.py`只读模板/Godot范围却被当作Phase static pass；或C# analyzer失败、Phase Python compile被skip、browser/schema command为warn-only仍授权。
73. 现有`security_hard_sql_gate.py`只扫描`Game.Core/Game.Godot`且没有读取`PhaseA.Platform`改动，却被当作Phase安全扫描通过；或security result存在missing changed path/stale finding仍授权。

## 15. 非目标

- 不负责实现或修复重构代码。
- 不负责改写重构计划、97台账或已有矩阵。
- 不替代 `$run-phase-bootstrap-review`。
- 不自动运行未经用户授权的Bootstrap reviewer或verifier。
- 不为positive attestation复制第二套semantic runner、Artifact View、gateway或process lifecycle；generic companion能力归仓库级Bootstrap v2控制面。
- 不把新控制面行为写入7-12兼容适配器。
- 不把7-07阶段名称硬编码为所有重构计划的通用模型。
- 不审核Godot engine、场景、UI、渲染、视觉证据、GdUnit4或`Game.Core`游戏领域代码；不在本Skill内预留伪Godot policy，后续由独立Skill定义。
- 不用关键词猜测结果冒充registry/parser-backed完整覆盖。
- 不在未声明隔离写边界时运行build、test、smoke或runtime mutation。
- 不用固定finding数量或repo总体覆盖率单独判断质量；用户明确冻结的`PHASE-CR-TEST-002`增量可执行行85%门禁除外。
- 不将计划一致性验证等同于运行时实现完成。

## 16. 已确认默认项

以下默认值已确认，创建Skill时按此执行；后续变更必须作为新的authority delta记录：

1. Skill 名称使用 `run-refactor-implementation-acceptance`。
2. Skill 放在仓库 `.agents/skills/` 下。
3. 默认运行模式为`evidence_only`；只有用户明确要求并满足隔离写边界时才使用`controlled_validation`。
4. 来源按partition选择`registry_backed`、`parser_backed`或`semantic_candidate`；语义partition必须通过同一Bootstrap v2 Acceptance Auditor formal companion才能成为`semantically_attested_complete`。
5. 任一`semantic_partition`、Phase code-review policy required review/hybrid gate、plan/adapter、DoD/finding policy、risk policy或`user_request` required来源成立时，必须等待用户reviewer授权并通过同名`$run-phase-bootstrap-review`入口调用Bootstrap v2；只有全部被消费partition均为`deterministic_complete`、全部activated policy checks均可由合法deterministic/conditional authority闭合、目标DoD层级明确允许deterministic-only acceptance、没有semantic review gate且external/protected gates已满足时，Bootstrap才可为`not_required`并产生最终授权。存在被消费的`semantic_candidate` partition时还必须取得positive-attestation companion；缺少任一所需语义步骤时只输出candidate结论。
6. 通用Skill从目标计划解析phase DAG；7-07规则作为首个线性adapter和回归fixture。
7. 现有7-07 `100-*`与机器矩阵作为兼容输入和真实测试样本，不作为无需重验的完成证明。
8. 首版按S0-S5谓词实施：统一run input、带complete/partial/unavailable状态的双manifest、partitioned source inventory、Phase service code-review policy pack及binding、policy-check exact coverage、task checklist closure、85% changed-line coverage、Phase static/security scope results、command-ID-bound evidence、base matrix、candidate结果、同时拥有全run与Phase/DoD scope effective completeness的impact projection、typed external/protected gate results、final结果、conditional action DAG、Bootstrap immutable requirement decision/capability binding/request/单向launch authorization与consumer-private import receipt/execution projection/import envelope、冻结inventory attestation scope、确定性`map-findings`和`import-mapping-approval`；同时把positive-attestation与Bootstrap-owned单向launch authorization扩展加入仓库级Bootstrap v2控制面，并同步durable standard、仓库级Skill/reference、operator docs、profile/schema registry和ADR-0041复核结果。S0未完成不阻止S1-S3 deterministic core迭代，但阻止S4 semantic integration与S5完整发布。跨模型稳定性属于发布级独立证据，不阻止本地开发迭代。
9. 代码审核域固定为Phase服务；纯Godot目标返回`unsupported_code_review_domain`，mixed-domain目标只验收Phase partition并等待独立Godot审核权威。commit message检查默认advisory，只有目标计划、adapter或仓库policy显式授权时才能阻断。
10. `PHASE-CR-TEST-002`最低增量行覆盖率为85%；`PHASE-CR-TRACE-001`要求全部required task checkbox勾选且证据闭合；`PHASE-CR-STATIC-001`与`PHASE-CR-SEC-003`必须使用Phase-aware scanner和exact changed-path read scope，现有Godot/Game.Core-only扫描结果不得授权。
