# 重构实施验收 Skill 需求规格

- Title: `run-refactor-implementation-acceptance` Skill 需求规格
- Status: draft
- Branch: 当前工作树
- Git Head: 48e7b21e6cf33f30aca7c8ac2f3b2fa63b784fe7
- Goal: 定义一个以验收条款为单位、按阶段顺序判断重构实施完成度的只读 Skill
- Scope: Skill 的触发、输入、验收矩阵、阶段门禁、DoD 层级、输出和验证场景
- Current step: 需求规格评审
- Last completed step: 已根据首次 Edge Case Hunter 审查修复延期字段合同和 Program DoD 终态边界
- Stop-loss: 本文件不创建或修改 Skill，不修改被验收重构目录，不执行 Bootstrap reviewer
- Next action: 用户确认本规格后，使用 `skill-creator` 创建 Skill
- Recovery command: `py -3 -c "from pathlib import Path; print(Path(r'execution-plans/2026-07-15-refactor-implementation-acceptance-skill-requirements.md').read_text(encoding='utf-8'))"`
- Open questions: 见“待确认项”
- Exit criteria: 本文件中的功能需求、状态规则、阶段门禁和负例成为后续 Skill 创建的对照基准
- Related ADRs: `n/a`，本轮不改变产品架构或运行时合同
- Related decision logs: n/a - 尚未创建独立决策日志
- Related task id(s): `n/a`，本轮没有 Taskmaster 任务
- Related run id: `n/a`，本轮不执行验收 run
- Related latest.json: n/a - 本轮不产生运行结果
- Related pipeline artifacts: n/a - 本轮只创建需求规格

## 1. 目的

创建一个新的 `run-refactor-implementation-acceptance` Skill，用于检查 `execution-plans/` 下指定重构目录的真实实现情况。

该 Skill 必须回答：

1. 计划中的每一条验收要求是否有实现、测试和当前运行证据。
2. 当前允许声明 First-slice DoD、Phase exit DoD 还是 Program DoD。
3. 哪些要求是部分实现、缺失、延期、不适用或被前置条件阻断。
4. 当前最早未通过的阶段是什么，以及下一步应补什么。

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
  + Bootstrap Review 无未解决 P0/P1/P2
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

## 4. 输入权威顺序

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

Skill 必须先建立完整验收条款清单，再检查实现。条款来源至少包括：

- 阶段 deliverables；
- 阶段 exit criteria；
- `01-*` 至 `07-*` 的局部 acceptance criteria；
- `97-*` 中适用于当前或最终 Program DoD 的新增要求；
- 计划 schemas/registries 中声明的能力、状态或 gate；
- `09-*` 中 First-slice、Phase exit 和 Program DoD 条款；
- 计划明确引用且对实现具有约束力的标准和 ADR。

每一条规范性要求必须恰好对应一个稳定 `check_id`。同一条款不能因出现在多个文档中被重复计数；多个来源必须合并到同一行的 `source_ref` 集合。

## 6. 实施验收矩阵

### 6.1 必需字段

机器矩阵每一行必须包含：

| 字段 | 含义 |
| --- | --- |
| `check_id` | 稳定检查编号 |
| `phase` | 计划声明的阶段，例如 Phase 0A、0B、1-6 |
| `source_ref` | 文档、schema 或 ledger 中的精确验收条款位置 |
| `requirement` | 单一、可观察的要求摘要 |
| `owner` | 后端、前端、DB、脚本、标准文档等责任域 |
| `code_refs` | 实现文件或明确的非代码交付物 |
| `test_refs` | 自动化测试及本次执行结果引用 |
| `evidence_refs` | `logs/` 下 smoke、readback、运行或阶段退出证据 |
| `split_added_ids` | 对应的 97 条目；没有时必须是显式空数组并有来源依据 |
| `status` | 六种允许状态之一 |
| `gap` | 未满足项、阻断原因或特殊分类依据 |

当 `status=explicitly_deferred` 时，还必须包含以下条件必填机器字段：

| 字段 | 含义 |
| --- | --- |
| `defer_owner` | 对延期关闭负责的明确角色或团队 |
| `defer_affected_routes` | 受延期影响的 route、能力或消费者列表 |
| `defer_severity` | 延期风险等级及其权威词汇 |
| `defer_non_impact_evidence_refs` | 证明当前阶段未受影响的代码、测试或运行证据 |
| `defer_recheck_trigger` | 到期时间或可执行的重新检查触发条件 |
| `defer_closure_test_ref` | 最终关闭延期时必须执行的精确测试或验证命令 |
| `defer_acceptance_refs` | 延期最终必须满足的验收条款或 `check_id` 列表 |

这些字段必须由 schema 条件必填并分别校验，不得只写进自由文本 `gap`。允许增加 source hash、candidate hash、验证时间、route和predecessor run等字段，但不得删除上述通用字段或条件字段。

### 6.2 状态词汇

只允许：

- `verified`：实现、自动化测试和当前有效证据全部满足。
- `partial`：存在部分实现或部分证据，但未达到完整验收。
- `missing`：没有满足条款的实现。
- `not_applicable`：有可审核的适用性分析和证据。
- `explicitly_deferred`：有明确负责人、影响范围、非影响证明、复查条件和最终关闭测试。
- `blocked`：被尚未满足的前置条件、权威冲突或缺失上下文阻断。

禁止“看起来完成”“基本完成”“大致通过”“可能满足”等状态或等价自由文本。

### 6.3 状态判定硬规则

- `verified` 必须同时具有有效 `code_refs`、`test_refs` 和 `evidence_refs`；仅文档类要求可以用明确的非代码交付物替代生产代码，但仍必须有可执行校验和当前证据。
- 测试文件存在不等于测试通过；必须绑定本次或仍然新鲜的执行结果。
- 日志文件存在不等于证据有效；必须匹配当前候选、范围、版本或 hash。
- `not_applicable` 必须记录触发条件为何未出现，以及证明该结论的代码或运行证据。
- `explicitly_deferred` 必须满足全部条件必填机器字段，不得只依赖 `gap` 中的自然语言；它不计入 `verified` 数量，也不得自动满足 Program DoD。
- `partial`、`missing` 和 `blocked` 均不能通过对应阶段。
- `gap` 对非 `verified` 行必须非空；对 `verified` 行应为空或只包含无阻断说明。

## 7. 阶段验收控制

### 7.1 通用规则

阶段名称和顺序必须从目标计划的阶段权威中解析，不在通用 Skill 中永久硬编码。Skill 必须：

1. 从最早阶段开始验收。
2. 前置阶段未通过时，不得声明后续阶段通过。
3. 可以预扫描后续阶段并记录缺口，但状态只能是待验或 `blocked`。
4. 每个阶段分别生成条款覆盖、状态计数、未解决 findings 和退出结论。
5. 计划声明的按需能力包只在触发条件成立时启用；未触发必须使用有证据的 `not_applicable`，不能静默跳过。

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

- 全部 exit criteria 已进入矩阵并有合法结论；
- 对应 `01-*` 至 `07-*` 局部 acceptance criteria 已覆盖；
- 相关 `97-*` 条目全部分类；
- 所有应当 `verified` 的条目均有代码、测试和 smoke/readback/运行证据；
- 所有 `not_applicable` 和 `explicitly_deferred` 均满足严格字段合同，且目标计划明确允许该延期通过当前阶段出口；
- 没有 `partial`、`missing` 或 `blocked` 行；
- 没有未解决的 P0、P1 或 P2；
- 计划声明的 predecessor、external 或 protected gate 已通过。

## 8. DoD 层级判定

Skill 必须以目标目录的 `09-*` 为完成层级权威，分别计算：

1. `First-slice DoD`
2. `Phase exit DoD`
3. `Program DoD`

三个层级必须分别输出，不允许用较低层级推导较高层级。

Program DoD 默认要求所有适用要求达到终态闭合。任何仍未关闭的 `explicitly_deferred` 都必须阻止 Program DoD，即使它已经合法通过某个阶段出口。只有当 `09-*` 明确把该延期定义为允许的 Program 终态，并同时给出终态非影响证明、长期owner、复查机制和关闭权限时，才能作为计划特定例外；Skill不得从“已分类”或“阶段已通过”自行推导该例外。

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
  -> 生成条款清单和候选矩阵
  -> 运行确定性测试、编译、smoke/readback检查
  -> 计算候选阶段与DoD结果
  -> 使用 bootstrap-implementation-conformance 审查
       -> Blind Hunter
       -> Edge Case Hunter
       -> Acceptance Auditor审计矩阵
  -> 将已接受P0/P1/P2写入最终阶段判定
  -> 输出最终验收报告
```

新 Skill 可以准备 Bootstrap 所需 scope、context class 和 plan-bound required checks，但不得绕过 `$run-phase-bootstrap-review` 的隔离 reviewer、gateway 和 verifier 规则。

若用户只要求确定性验收而未明确授权 reviewer，Skill 应输出“候选完成层级”，并明确 Bootstrap 语义审查尚未执行。

## 10. 输出合同

每次运行使用新的目录：

```text
logs/ci/<date>/refactor-implementation-acceptance-<run-id>/
├── acceptance-source-inventory.json
├── implementation-acceptance-matrix.json
├── implementation-acceptance-matrix.md
├── phase-acceptance-result.json
├── program-dod-result.json
├── acceptance-report.md
└── evidence/
```

要求：

- JSON 是机器权威，Markdown 是派生视图。
- 输出必须绑定目标目录、Git revision、源文件 hashes、验证命令和运行时间。
- 目标、权威或验证器变更后，旧结果必须标记为 stale，不能继续授权。
- 运行目录不得位于被审查的重构目录内。
- Skill 默认只读，不修改生产代码、重构计划、97台账、历史日志或 Bootstrap findings。
- 失败证据必须保留；后续修复使用新 run 或明确 predecessor/supersession 关系。

## 11. 失败关闭条件

遇到以下情况不得产生通过结论：

- 找不到阶段权威或 DoD 权威；
- 无法完整枚举验收条款；
- 97、98、99 或原始来源存在未解释的覆盖缺口；
- 矩阵存在重复、孤立或无来源的 `check_id`；
- `verified` 缺代码、测试或当前证据；
- 证据 hash、Git revision 或运行范围不匹配；
- 阶段顺序被跳过；
- `10-*` 被用于授权 Program DoD；
- 未解决 P0/P1/P2 被隐藏在 `clean`、`advisory` 或文本总结下；
- protected authority 尚未通过却声明其授权层级。

## 12. 新 Skill 的最小包结构

后续实现建议包含：

```text
.agents/skills/run-refactor-implementation-acceptance/
├── SKILL.md
├── agents/openai.yaml
├── references/acceptance-protocol.md
├── schemas/
│   ├── implementation-acceptance-matrix.v1.schema.json
│   ├── phase-acceptance-result.v1.schema.json
│   └── program-dod-result.v1.schema.json
└── scripts/
    ├── validate_acceptance.py
    ├── fixtures/
    └── tests/
```

不要求为该 Skill 创建单独的严格 VDD 00-99执行计划目录。

## 13. Skill 验收标准

### RA-SKILL-001：完整条款抽取

给定一个包含阶段、局部 acceptance、97台账和DoD的重构目录，Skill输出的 `check_id` 集合必须覆盖全部适用条款，且无重复权威。

### RA-SKILL-002：矩阵字段和词汇

缺少任一通用必需字段、缺少状态对应的条件必填字段、使用未知状态或使用模糊完成状态时，验证器必须非零退出并给出稳定规则ID。

### RA-SKILL-003：伪 verified

任一 `verified` 行缺少有效代码、已执行测试或当前证据时，验证器必须拒绝。

### RA-SKILL-004：阶段顺序

前置阶段未通过而后续阶段被标记通过时，验证器必须拒绝。

### RA-SKILL-005：按需 Phase 0B

触及 route 的能力包必须启用并验收；未触发的能力包必须有可审核 `not_applicable`，不得静默缺失。

### RA-SKILL-006：97闭合

每个适用的 split-added requirement 必须映射到至少一个矩阵行；未分类条目阻止相应阶段或 Program DoD，仍未关闭的 `explicitly_deferred` 条目默认阻止 Program DoD。

### RA-SKILL-007：09/10权限边界

仅凭 `10-*` 完成声明 Phase exit 或 Program DoD 时，验证器必须拒绝。

### RA-SKILL-008：三层DoD

输出必须分别报告 First-slice、Phase exit 和 Program DoD，包含通过条件、失败条款和未授权层级；阶段允许的延期不得被自动提升为 Program 终态。

### RA-SKILL-009：findings闭合

存在未解决 P0/P1/P2 时，阶段和 Program DoD 均不得通过。

### RA-SKILL-010：新鲜证据

源文件、Git revision、实现或验证器改变后，旧矩阵和结果必须被识别为 stale。

### RA-SKILL-011：只读边界

验收运行只能在新建的 `logs/ci` run目录写结果，不得修改目标计划、生产代码或历史 evidence。

### RA-SKILL-012：Bootstrap边界

未运行 Bootstrap时只能输出候选完成层级；Bootstrap `clean` 不能替代矩阵和DoD门禁，也不能替代 protected authority。

## 14. 必测反例

后续 Skill 至少应包含以下负例：

1. `verified` 行只有测试文件路径，没有本次执行证据。
2. Phase 0A未通过，但Phase 1被声明通过。
3. 被触及route缺少所需Phase 0B能力包。
4. `not_applicable` 没有触发分析或证据。
5. `explicitly_deferred` 缺少任一条件必填字段，或只在自由文本 `gap` 中描述owner、非影响证明和复查条件。
6. 97存在未映射条目，但Program DoD被声明通过。
7. 只引用10号文件便声明整个重构完成。
8. 使用旧Git revision或旧hash evidence声明当前实现通过。
9. Bootstrap仍有P2 advisory，但阶段被声明通过。
10. 三个reviewer零finding，但验收矩阵漏掉一条源验收要求。
11. `explicitly_deferred` 合法通过阶段出口，但仍未关闭时Program DoD被声明通过。

## 15. 非目标

- 不负责实现或修复重构代码。
- 不负责改写重构计划、97台账或已有矩阵。
- 不替代 `$run-phase-bootstrap-review`。
- 不自动运行未经用户授权的隔离 reviewer 或 verifier。
- 不把7-07阶段名称硬编码为所有重构计划的通用模型。
- 不用固定 finding 数量或固定覆盖率百分比判断质量。
- 不将计划一致性验证等同于运行时实现完成。

## 16. 待确认项

当前建议默认值如下，若无新的决策，创建 Skill 时按此执行：

1. Skill 名称使用 `run-refactor-implementation-acceptance`。
2. Skill 放在仓库 `.agents/skills/` 下。
3. Skill 默认只执行确定性验收；只有用户明确要求完整语义审查时才调用 Bootstrap流程。
4. 通用 Skill 从目标计划解析阶段；7-07规则作为首个适配器和回归 fixture。
5. 现有7-07 `100-*` 与机器矩阵作为兼容输入和真实测试样本，不作为无需重验的完成证明。
