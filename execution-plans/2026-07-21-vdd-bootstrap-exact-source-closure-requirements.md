# VDD 与 Bootstrap 完整计划精确 Source Closure 需求规格

- Title: 完整 VDD 计划七维包的精确 source closure
- Status: requirements-ready
- Branch: `fixskill1`
- Goal: 确保用户明确创建或修改完整 VDD 计划目录时，计划自身的真实权威来源全部进入唯一 Authorization Proof Package，并由 Bootstrap 对冻结 review context、package source inventory 和 predicate closure 执行确定性等集验证
- Scope: `.agents/skills/vdd-execution-plan/**`、`.agents/skills/run-phase-bootstrap-review/**` 及其标准、schemas、fixtures、tests 和兼容入口
- Non-goal: 单一需求文件属于直接实施的小需求工作流；本需求不要求它由 VDD 生成，不要求它携带 obligation 或七维 package，不允许把它自动升级、迁移或纳入未来完整计划
- Current step: 以本修订版重新冻结需求边界；先移除错误的单文件 future-plan/obligation 合同，再按完整计划 source closure 的 S0-S5 顺序实施和验证
- Open questions: none
- Exit criteria: 本文件的稳定需求、失败行为和验收矩阵成为两项 Skill 修复的需求权威；只有完整计划的确定性合同和 Bootstrap review 均通过，才可声明 source closure 机制完成

## 1. 工作流边界与当前缺口

### 1.1 两条独立工作流

单一需求文件用于直接实施的小需求：

```text
普通需求编写
  -> 单一 requirements 文件
  -> 直接实现、测试和验收
  -> focused change 或 implementation conformance review
```

完整计划用于用户明确选择 VDD 的复杂工作：

```text
用户明确调用 $vdd-execution-plan
  -> 直接创建或修改完整 execution-plan 目录
  -> 完整计划自身的 Authorization Proof Package
  -> bootstrap-upstream-plan review
  -> 分阶段实施
```

两条路径不存在自动转换。单一需求文件不会因为时间、规模变化、review 结果或后续计划创建而自动成为完整计划的 source，也不会先创建单一需求文件再由 VDD 消费。若复杂工作需要完整计划，用户直接创建或修改完整 VDD 计划。

### 1.2 完整计划的现有边界

当前两个 Skill 已经建立以下边界：

1. `$vdd-execution-plan` 为能够授权转换的完整计划生成七维 package、isolated mutations 和五项 binding。
2. `$run-phase-bootstrap-review` 的 `bootstrap-upstream-plan` 在 semantic reviewer 启动前验证 package/result 的 hash、provenance、binding、维度 PASS 和 mutation rejection。
3. `bootstrap-focused-change` 和 `bootstrap-implementation-conformance` 服务直接变更工作流，不产生或升级为计划级授权。

尚需完整证明的是：

```text
冻结的完整计划权威来源
== VDD package source inventory
== proof registry 中的 in-closure source proofs
== authorizing predicate closure
== Bootstrap upstream review context
```

完整计划权威来源包括计划目录内的 intent/authority、contracts、validators、fixtures、ledgers 和 source coverage，以及它实际引用的 repository rules、current state、standards、schemas 和其他权威输入。`original-requirements` 仅在创建该完整计划时确实存在独立外部权威需求源才适用；不得为满足 context class 人工创建单一需求文件。

## 2. 已确认决策

### 2.1 单一需求文件不属于 VDD package

- 普通单一需求文件由普通需求编写流程产生并直接实施。
- 单一需求文件不要求 `source-closure-obligation`、计划级 `source_inventory`、proof registry 或 predicate closure。
- focused review 不得要求 future package、future consumer、`obligation-open` 或 profile upgrade。
- 如果小需求后来需要重新定义为复杂工作，由用户发起新的完整 VDD 计划；新计划依据当时直接确认的意图和当前权威创建，不继承或消费旧单一需求文件。

### 2.2 Package 所有权

- Authorization Proof Package 的所有权单位是一个完整 VDD 计划及其 authorizing predicate closure。
- 同一个完整计划只能有一个规范 package；不得为计划中的每本书或每个 source 创建彼此独立的 package。
- package 只枚举该完整计划当前真实消费的权威来源，不枚举无关的单一需求文件，也不构造虚假的 future-plan source。
- 计划新增或修改时，`$vdd-execution-plan` 在同一目录工作流中直接更新 inventory、proof、predicate 和 validation result。

### 2.3 Plan-local Source Binding

- 每个 inventory member 的消费关系由完整计划内部生成的版本化 `source_binding` 表达。
- `source_binding` 绑定 plan、package、source、proof、predicate、result 和 review/input lineage；它不是源文件预先携带的 obligation。
- source 文件本身不需要因可能被某个未来计划使用而保存状态机或 sidecar。
- 已实现的 `source-obligation-reference` 若表达了单文件 future consumption，必须迁移为 plan-local binding；不得把该实现反向变成单文件生产要求。

### 2.4 最终确定性验证

- `$vdd-execution-plan` 负责从完整计划的实际 authority/source graph 发现 source，生成 inventory、proof mapping 和 predicate closure，运行 mutation 并输出当前 package result。
- `$run-phase-bootstrap-review` 负责从冻结 Artifact View/context graph 独立构造完整计划 required source set，并与 package inventory 和 predicate closure 做等集验证。
- Bootstrap 不得只比较 package 与 result 内彼此复制的 `source_hash`。
- semantic reviewer 只搜索确定性闭包之外的真实来源、消费者和授权旁路，不重复字段级 membership 检查。

## 3. 权威与威胁模型

按以下顺序解释本需求：

1. 仓库 `AGENTS.md` 和受保护路径规则。
2. `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`。
3. `docs/standards/bootstrap-review-control-plane.md`。
4. `$vdd-execution-plan` 的 `strict-vdd-standard.md` 与 `authorization-proof-package.md`。
5. 两个 Skill 的当前 profile、schema 和 runner 合同。
6. 本需求文件。

本合同面向 workflow-integrity：防止完整计划遗漏权威来源、错误分类、自报闭包、自复制 binding、陈旧证据和普通仓库内伪造。它不声明抵御控制主机、Git 对象库、外部签名根及全部 verifier custody 的恶意管理员。

## 4. 功能需求

| ID | 优先级 | 需求 | 可执行验收意图 |
| --- | --- | --- | --- |
| SCL-001 | P0 | review target 必须被机器分类为 `standalone-direct-change`、`vdd-plan` 或 `implemented-change`；单一需求文件固定属于直接实施路径，只有用户明确创建或修改完整 VDD 目录时才属于 `vdd-plan`。 | 单一 Markdown 选择 focused/implementation 路径且不要求 package；完整 VDD 目录选择 upstream profile；不得从文件内容推断自动升级。 |
| SCL-002 | P0 | `standalone-direct-change` 不要求 obligation、package 或 plan-level source closure，并且不得自动升级、迁移或成为未来 VDD source。 | fixtures 证明普通单需求文件可直接进入实现；缺 package/obligation 不报错；任何自动 upgrade 或 future-consumption sidecar 生成均失败。 |
| SCL-003 | P0 | `$vdd-execution-plan` 只在用户明确调用 create/repair mode 时创建或修改完整计划目录；不得把单一需求文件当作隐式 create-mode 输入。 | generic“生成需求文件”不触发 VDD；显式“创建 VDD 执行计划”才进入 clarification 和目录创建流程。 |
| SCL-004 | P1 | 完整计划的每个 source binding 必须由计划工作流在 inventory 内生成，绑定 plan/package/source/proof/predicate/result/review/input lineage；不得要求 source 文件预先携带 future-plan obligation。 | 删除任一 binding、跨计划/评审重放或从 source 自报消费关系均以稳定规则失败。 |
| SCL-005 | P0 | 完整计划 source identity 必须绑定实际冻结内容。Git tracked source 绑定 tree/path/mode/blob 和 Artifact View 原始字节；generated/external text 绑定 raw/canonical SHA-256、长度和 canonicalization rule；binary 绑定 raw SHA-256 和长度。 | path/mode/blob、原始字节、编码、二进制长度和大小写别名 mutation 均被拒绝。 |
| SCL-006 | P0 | `$vdd-execution-plan` 的 package 必须具有规范 `source_inventory`，逐项保存 source ID、role、context classes、path、identity、plan-local source binding、applicable predicates、consumer、proof ID、classification 和 disposition。 | schema 拒绝缺项、重复 source/proof ID、同 path 多身份、未知 predicate 和 source/proof 无双向映射。 |
| SCL-007 | P0 | `source_hash` 必须从排序后的完整 inventory 及实际重算身份生成，不得从声明列表或 package 内另一个自报 hash 复制。 | 修改、遗漏、新增或重分类任一 source 都改变重算 hash；复制旧 hash 不能通过。 |
| SCL-008 | P0 | 每个 authorizing predicate 的 required source set 必须由独立 producer 与 verifier entrypoint 分别发现。producer 可消费完整计划的 requirement registry/source coverage；verifier 必须从实际 plan links、predicate inputs、context graph、validator read-set 或等价独立路径发现。 | 两个入口相同、共享预构建成员数组、同步遗漏 source 或任一 discovery 与声明不等时失败。 |
| SCL-009 | P0 | package inventory、proof registry 和 predicate closure 必须双向闭合：每个 in-closure source 恰有一个 proof，每个 source proof 恰有一个 inventory member，每个适用 predicate 引用该 proof。 | orphan source、orphan proof、重复 proof、source 未进入 predicate 或 predicate 引用未知 source均命中稳定规则。 |
| SCL-010 | P1 | source 只有在确定性证明不影响任何 authorizing predicate 时才可 `OUT-OF-CLOSURE`；必须提供 reason code、独立 exclusion checks、affected predicates 和 `authorizes=[]`。 | 任意排除真实计划 source、使用 prose 理由或保留授权均失败。 |
| SCL-011 | P0 | `bootstrap-upstream-plan` 必须从完整计划的冻结 source-bearing context classes 构造 `required_context_sources`，绑定 Artifact View original path、snapshot/original hash、Git identity 和完整 context classes。`original-requirements` 仅在存在真实独立权威源时 required。 | 没有外部需求源的直接 VDD 计划不因缺 `original-requirements` 失败；存在真实源却遗漏时失败；不得创建占位文件满足 class。 |
| SCL-012 | P0 | Bootstrap preflight 必须独立比较 `required_context_sources == package source_inventory applicable set == predicate source proof set`，并重算 context source hash 与 result `source_hash`。 | package/result 内部自洽但遗漏 source、增加未声明 source、错误 classification、proof 缺失或 hash 复制均在 reviewer 启动前失败。 |
| SCL-013 | P0 | source membership 失败不得被七维 PASS、mutation PASS、签名有效或 process exit 0 覆盖；preflight 必须停止 semantic reviewer。 | 每个 failure fixture 断言零 reviewer attempt、稳定 rule ID 和非 passed preflight。 |
| SCL-014 | P0 | 七维 mutation suite 必须包含 source-closure mutation，至少覆盖 omit、extra、identity drift、role change、predicate unlink、proof unlink、source-binding replay 和 copied source hash。 | 每个 mutation 只破坏一个规则并命中预期 ID；不得用删除 verdict label 替代真实 source 语义 mutation。 |
| SCL-015 | P1 | `bootstrap-focused-change` 审查单一需求文件时只验证其直接实施边界和非授权性；不得要求 obligation、future package、future consumer、sourceClosureStatus 或 upstream profile upgrade。 | focused 单文件缺任何 VDD 工件仍可完成；一旦声称 plan-ready，作为非法越权直接失败，而不是升级为 upstream。 |
| SCL-016 | P1 | 单一需求文件实施完成后的闭包由 `bootstrap-implementation-conformance` 或等价实现验收证明，绑定需求、代码、测试和运行证据；该闭包不得生成 plan-ready 或七维 package authority。 | 小需求从单文件直接到实现验收；结果明确不授权 plan-ready、protected handoff 或 release。 |
| SCL-017 | P1 | upstream Acceptance Auditor 只审查完整计划的 predicate authority、机器 closure 未追踪的真实 source/consumer、plan-ready 与更高授权边界及 P0/P1 可达性；不得重新打开已通过的逐 source membership 字段检查。 | reviewer fixture 拒绝重复七维/逐字段 finding，并允许对真实未跟踪计划 source 形成候选。 |
| SCL-018 | P1 | 完整计划 source-closure P0/P1 按 predicate、source role、root cause 和 reachable authorization outcome 聚合，保留完整 affected source/artifact 列表，并由 independent verifier 验证精确 source、规则和坏结果。 | 同根因多 source 聚合为一个 finding；不同 predicate 或可达结果不得错误合并。 |
| SCL-019 | P1 | 旧 VDD package 通过版本化只读适配器迁移，不得改写历史 evidence；单一需求文件不属于迁移对象，也不得为其补建 obligation 或 package。 | legacy package 保持可读但不能满足新 predicate；历史单文件保持原状且不会进入 migration inventory。 |
| SCL-020 | P0 | 两个 Skill 的完整 deterministic validation、golden fixture、Skill 自包含 integration sample 和 Bootstrap consumer fixture 必须针对当前 hash 全部通过；旧 hash、超时、skip、BLOCKED 或仅 exit 0 不算 PASS。 | 完整命令产生当前受限 PASS envelope，并额外证明两条工作流没有自动转换。 |

## 5. 机器合同

### 5.1 Workflow Classification

分类由调用意图、目标形态和 profile 共同决定，不要求单一需求文件嵌入机器块：

```json
{
  "workflow_kind": "standalone-direct-change",
  "requires_vdd_plan": false,
  "requires_authorization_proof_package": false,
  "auto_upgrade": false,
  "authorizes": []
}
```

显式 VDD create/repair 的目标必须是完整目录，并分类为 `vdd-plan`。分类证据保存在 run/plan 控制面，不反向修改普通需求文件。

### 5.2 Package Source Inventory

完整计划的每个 inventory member 至少包含：

- stable source ID、canonical path 和 source role；
- 完整 context-class set；
- Git/raw/canonical/binary identity；
- plan-local source binding；
- applicable predicates 和真实 consumer；
- proof ID、classification 和 disposition；
- producer/verifier discovery evidence；
- current/baseline identity 与 lineage；
- member canonical hash。

`source_hash` 是排序后的完整 inventory canonical hash。排序、path case、Unicode、JSON canonicalization 和换行规则必须版本化。

### 5.3 Bootstrap Required Context Sources

Bootstrap 只能从当前完整计划 run 的冻结 Artifact View 和 profile context mapping 构造 required set，不得混合 live original，也不得让 operator 用布尔值声明覆盖。

比较键至少包括：

```text
source role
+ canonical original path
+ frozen content identity
+ complete context-class set
+ applicable predicate
+ proof identity
```

无法确定 predicate applicability 时失败关闭。可选 context class 必须由 profile-bound applicability 判定，不得用占位 artifact 或虚构单一需求文件满足。

## 6. Profile 行为

### 6.1 Focused Change

适用于单一需求文件和其他直接小变更：

- 不要求 VDD plan、package、source obligation 或 plan-level source closure；
- 不检查 future consumer，不自动升级 profile；
- 只报告当前 focused scope 的 finding；
- 输出始终不授权 plan-ready、phase-authorized、implementation-accepted、protected handoff 或 release。

### 6.2 Implementation Conformance

适用于单一需求文件已经进入直接实施后的验收：

- 绑定当前需求、changed code、affected consumers、tests 和 runtime evidence；
- 证明实现符合小需求，但不创建 VDD plan authority；
- 如任务复杂度后来改变，需要用户另行发起新的 VDD 计划，旧单一需求文件不自动成为其 source。

### 6.3 Upstream Plan

仅适用于用户明确创建或修改的完整 VDD 计划目录或 whole-directory authority：

- package/result 各恰好一个；
- source-bearing context classes 按当前计划真实 authority graph 和 profile applicability 确定；
- deterministic preflight 执行 exact source set comparison；
- 比较通过后才允许三个 discovery reviewer 启动。

单一文件即使错误声称 plan-ready，也不得在原 run 中升级为 upstream；应以 workflow-boundary violation 失败。

## 7. 失败行为与规则族

| Rule family | 触发条件 |
| --- | --- |
| `VDD-WORKFLOW-BOUNDARY-*` | 单文件自动升级、隐式触发 VDD、把 direct change 纳入计划或伪造 plan-ready |
| `VDD-PACKAGE-SOURCE-BINDING-*` | 完整计划 source binding 缺失、stale、重放或 lineage 错误 |
| `VDD-PACKAGE-SOURCE-INVENTORY-*` | inventory schema、identity、role、proof 或 predicate 映射错误 |
| `VDD-PACKAGE-SOURCE-DISCOVERY-*` | producer/verifier 不独立或 discovery 集合不一致 |
| `VDD-PACKAGE-SOURCE-HASH-*` | source hash 未从完整实际 inventory 重算 |
| `BOOTSTRAP-SOURCE-CONTEXT-*` | 完整计划 Artifact View/context source 集合无效或不完整 |
| `BOOTSTRAP-SOURCE-CLOSURE-*` | context、inventory、proof closure 不等或 result binding 漂移 |

同一个坏结果只能由一个主规则族负责。诊断必须报告 missing/extra/stale member、source role、predicate、expected/actual identity、package/result hashes 和下一允许动作，不得输出秘密或完整用户原文。

## 8. 最低测试矩阵

1. 普通单 requirements 文件直接实施：不触发 VDD，不要求 package、obligation 或 upstream profile。
2. generic“生成需求文件”调用：只产生单文件；显式“创建 VDD 执行计划”才进入目录 create mode。
3. 单文件错误声称 plan-ready：以 workflow-boundary rule 失败，不升级 upstream。
4. 单文件实现验收：implementation-conformance 绑定代码和测试，但不生成 plan authority。
5. 直接创建完整 VDD 计划且没有独立 external requirements：合法 N/A `original-requirements`，不得创建占位文件。
6. 完整计划确有外部权威源：该 source 必须进入 inventory/proof/predicate/context 等集。
7. 从 package 同时删除 source 和自报 source hash：Bootstrap 仍从 Artifact View 发现遗漏并失败。
8. package 增加 context 中不存在的 source：extra member 失败。
9. context、inventory、proof 分别发生 path、role、identity、predicate 和 proof ID 漂移。
10. producer/verifier 共用 discovery callable、预构建列表或同步遗漏 source。
11. tracked、dirty/untracked、generated/external UTF-8 text 和 binary identity。
12. plan-local source binding 缺失、跨 package/plan/predicate/review replay。
13. 七个维度和八个 source mutation 命中唯一预期规则。
14. package/result 五项 binding 内部自洽但 context source 不等。
15. preflight source closure 失败时零 reviewer attempt。
16. Acceptance Auditor 不重复确定性字段检查，但发现真实未跟踪计划 source。
17. 同根因多 source finding 聚合与 independent verifier 精确覆盖。
18. golden minimal fixture 和 Skill 自包含 integration fixture 产生可解析当前 PASS envelope。
19. 旧 package 只读迁移、stale 和 re-entry；历史单文件完全不参与迁移。
20. negative fixture 证明任何 single-file-to-VDD 自动转换均失败。

## 9. 实施顺序

| Phase | 所有权 | 退出条件 |
| --- | --- | --- |
| S0 | workflow classifier、requirement registry、source role vocabulary、plan-local binding/inventory schemas、稳定规则和 RED fixtures | 两条工作流分离；generic 单文件不触发 VDD；至少 omit-source、copied-hash 和 auto-upgrade 三个 fixture 以预期 ID 失败 |
| S1 | VDD 完整计划 inventory、source binding、identity 和 independent discovery | 直接创建/修改完整计划的 golden inventory 通过；producer/verifier 独立性与 source hash mutation 通过 |
| S2 | VDD package runner、七维/source mutation、integration registry 和 result envelope | 当前 golden 与 Skill 自包含 integration package 均产生受限 PASS result |
| S3 | Bootstrap upstream profile、Artifact View source set、applicability、exact comparison 和 preflight | context/inventory/proof 等集及零 reviewer launch 负例通过；无外部 requirements 的计划合法通过 |
| S4 | reviewer/gate/verifier 聚合和 direct-change implementation conformance 边界 | semantic 边界、聚合、独立验证及单文件不升级 fixtures 通过 |
| S5 | 旧 package 兼容迁移、完整验证、Bootstrap Skill review | 两个 Skill 完整 deterministic suite 通过，当前 hash-bound review 无 accepted P0/P1 |

后续阶段不得绕过前序阶段。不得通过修改 golden 输出、放宽 PASS schema、删除 mutation、增加 skip、创建占位需求文件或把 integration failure 改成预期成功来伪造 GREEN。

## 10. 预期影响面

实施至少检查并按需修改：

- `.agents/skills/vdd-execution-plan/SKILL.md`
- `.agents/skills/vdd-execution-plan/references/strict-vdd-standard.md`
- `.agents/skills/vdd-execution-plan/references/authorization-proof-package.md`
- `.agents/skills/vdd-execution-plan/references/vdd-artifact-proof-semantic-contract.v1.json`
- `.agents/skills/vdd-execution-plan/scripts/authorization_proof_package.py`
- `.agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py`
- `.agents/skills/vdd-execution-plan/scripts/fixtures/authorization-proof-package-*.json`
- `.agents/skills/vdd-execution-plan/scripts/tests/test_validate_skill_contract.py`
- `.agents/skills/run-phase-bootstrap-review/SKILL.md`
- `.agents/skills/run-phase-bootstrap-review/references/review-profiles.v1.json`
- `.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py`
- `.agents/skills/run-phase-bootstrap-review/schemas/**`
- `.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py`
- `docs/standards/bootstrap-review-control-plane.md`
- `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`，仅当 authority ownership 或 trust boundary 实际变化时

不得读取、执行或修改 `2026-07-15-repository-maintenance-tdd-adapter/**` 来迎合新验证器；大型 integration 必须是 Skill 自包含样板。

## 11. 完成定义

只有以下条件全部满足，才能声明两个 Skill 的完整计划 exact source closure 修复完成：

- 单一需求文件由普通流程生成并直接实施，不要求 obligation/package，不自动触发或升级 VDD；
- 单一需求文件的实现闭包与 plan-ready 七维闭包保持独立；
- 用户明确创建或修改完整 VDD 计划时，package 逐 source 枚举真实 authority graph，并由实际内容重算 source hash；
- 没有独立 external requirements 的完整计划不会被迫创建占位单文件；确有外部权威源时不得遗漏；
- producer/verifier 从独立 entrypoint 发现相同 source closure；
- inventory、proof registry、predicate closure 和 Bootstrap frozen context 精确等集；
- omit、extra、stale、reclassify、unlink、binding replay 和 copied-hash mutation 命中唯一稳定规则；
- source closure preflight 失败时没有 reviewer process 启动；
- Bootstrap semantic review 不重复确定性字段 finding，但仍能发现机器闭包外真实计划 source/consumer；
- package/result 只证明 deterministic/package-level，不越权声明 fresh-context、cross-model、protected handoff 或 release；
- `$vdd-execution-plan` 完整 Skill contract、单元/集成/mutation tests 和大型样板通过；
- `$run-phase-bootstrap-review` regression、whole-directory compatibility 和 quick validation 通过；
- 新鲜 hash-bound review 已完成，所有 accepted P0/P1 均经独立验证并关闭，P2 均有合法 disposition；
- 所有证据绑定当前 candidate/source/validator/authority/closure hashes，旧 PASS、超时、skip 或仅 exit 0 不得作为完成证据。
