# VDD 下游可消费性专项审查

- 审查对象：`execution-plans/2026-08-10-vdd-conformance-exact-cover-requirements.md`
- 审查范围：用户条件 3（Chapter 5 核心思想与上游 exact-cover）和条件 4（新 Skill 产物可被 VDD 再次消费）
- 审查方式：只读 PRD Validate；未修改需求文档
- 总结论：**FAIL**。现稿具备确定性 preflight、LLM 非授权、hash/current evidence、fail-closed 和 producer/consumer 组合测试的正确方向，但没有建立“VDD 实际消费的全部上游输入”之闭包，也没有定义现行 `vdd-execution-plan` 能识别的回灌产物和适配器。因此条件 3、条件 4 均未满足。

## 1. 依据与消费者契约

### 1.1 Chapter 5 的实际核心

`workflow.md` Chapter 5 是**按条件进入的语义稳定化 lane**，不是文档所称的一条既定 “自然语言 → obligation → acceptance → exact-cover” 规范链：

- 仅在 acceptance 不足、refs 漂移、subtask 覆盖不清或重复语义 `Needs Fix` 时进入（`workflow.md:528-537`）。
- 确定性 preflight 在 extract 前拦截 acceptance / Refs / 硬门缺失，但通过 preflight **不替代**后续 `extract`、`align`、`coverage`、`semantic_gate`（`workflow.md:571-578`）。
- 支持同一任务集、delivery profile、apply 模式绑定的恢复；跨批次必须换 out-dir 或禁用 resume（`workflow.md:580-600`）。
- 失败必须按 bucket/family 聚合、降载、隔离热点；`hard_uncovered` 应先修内容而不是扩大超时预算（`workflow.md:639-683`）。
- batch lane 的 preflight 同样不替代真正质量判断，并以 recommended action/failure family 驱动止损（`workflow.md:684-714`）。

所以可迁移到新 Skill 的核心不是一句 “exact-cover”，而是：**条件触发 → 确定性前置硬门 → LLM 语义抽取 → 对齐与覆盖 → 语义门 → 可恢复运行 → failure-family 止损**。

### 1.2 `vdd-execution-plan` 的真实输入路由

现行 VDD 只有三类输入路由：

| 输入 | 结果 |
| --- | --- |
| 单个 requirements Markdown | 直达实现；不进入 VDD create/repair，不创建 VDD 目录 |
| 用户明确要求创建完整 execution-plan 目录 | VDD `create` |
| 用户明确要求修复完整现有 execution-plan 目录 | VDD `repair` |

依据：`.agents/skills/vdd-execution-plan/SKILL.md:12-14`；机器契约见 `.agents/skills/vdd-execution-plan/scripts/skill-contract.json:8-12`。文件内容或任务复杂度不能隐式触发 create/repair。

VDD 还要求：

- 先选 `standard|resumable|self-hosted`，计划必须具有对应 plan/lifecycle/Git/slice/terminal validation 产物；self-hosted 还需 resume/dependency/recovery/95 report/protocol fixture/migration check（`SKILL.md:16-26`；`skill-contract.json:3-6`）。
- 生命周期严格区分，VDD 只拥有 `draft`、`plan-ready`；Quick Dev 只拥有 `implementation-complete`；Acceptance 另行拥有 `acceptance-passed`（`SKILL.md:57-67`；`references/lifecycle-state-contract.json:3-12`）。
- 计划准备前必须执行知识消费，冻结 Locator request/result、required modules、adapter decisions、source snapshot/hash，缺少 required match 时阻断（`SKILL.md:104-125`；`references/knowledge-consumption.md:3-33`）。
- repair 必须留在原目录，使用 `repair/round-<n>/`、hash-bound closure、callsite inventory、changed-set manifest 和真实 producer/consumer composition receipt（`SKILL.md:69-102`）。
- 完成要求每个 active requirement 有 observable acceptance path、RED/negative 或 legacy path、targeted stabilization，以及当前 terminal full validation（`SKILL.md:169-171`）。

## 2. 分项判定

| 条件 | 判定 | 证据摘要 |
| --- | --- | --- |
| 3. 具备 Chapter 5 核心思想，并 exact-cover VDD 消费的全部上游文件内容 | **FAIL** | 文档实现了 preflight/extraction/coverage/fail-closed 的一部分，但把 Chapter 5 错述为固定链；输入 universe 由 caller 提供 `vdd_sources`，没有按 VDD 真实消费图独立发现闭包，也没有 `align`、条件触发、恢复身份和 failure-family 止损合同。 |
| 4. 新 Skill 产物可被 VDD 再次消费 | **FAIL** | 文档只定义 conformance receipt/matrix，未定义 VDD input route、handoff schema、adapter、显式 create/repair 语义或完整计划目录形状。现行 VDD 不消费该 receipt；单个 Markdown 又会被路由到 direct implementation。 |

## 3. 严重性发现

### P1-1：上游 authority universe 不是独立闭包，无法证明“所有 VDD 输入”的 exact-cover

目标文档把 `vdd_sources` 定义成 caller 提供的路径集合（目标文档 `:54-65`），随后仅对该集合做 freeze。若 caller 漏掉 `AGENTS.md`、README/standards、生命周期契约、knowledge policy/catalog/Locator 决策、protected-path rule、当前调用者/测试或 Git identity，Skill 会对一个不完整 universe 给出内部自洽的 PASS。目标文档所称“从 VDD authority 重建”（`:38`、`:143`）没有 source discovery 算法、必需角色、闭包终止规则或 omission oracle。

这也与 VDD 的 knowledge preflight 强约束不一致：knowledge projection 不替代用户输入、repository rules、lifecycle authority 和 direct source evidence（`references/knowledge-consumption.md:31-34`）。

直接修正：

- **FR-AUTH-001**：Skill 必须从 repository root、目标类型和 VDD consumer contract 独立构造 `required_source_roles`，至少包含 user intent、repository/local AGENTS、适用 README/standards/ADR、VDD SKILL 与直接契约、lifecycle contract、knowledge policy/catalog/current generation/Locator accepted decisions、target current state、Git identity、relevant callers/tests/protected-path rules；caller 只能增加候选，不能缩减必需角色。
- **FR-AUTH-002**：每个发现文件及每个规范性语义单元必须归类为 `active_obligation|typed_deferred|non_normative|conflict`，并保留 path/hash/anchor/rationale；未分类文本或缺失 required role 必须 blocked。
- **NFR-AUTH-001**：source discovery 和 role completeness 必须由版本化 adapter/规则确定，绑定 validator hash；禁止以 caller 的 `complete=true` 或手写 manifest 证明闭包。
- **AC-AUTH-001**：删除一个适用 local `AGENTS.md`、knowledge required module 决策或 lifecycle contract 后运行，结果必须为 `blocked`，错误包含稳定 source-role ID，且不得生成 PASS receipt。
- **AC-AUTH-002**：caller 只传目标文档而遗漏 VDD direct contracts 时，独立 discovery 必须补齐；若无法补齐则 fail closed。

### P1-2：不存在 VDD 可识别的 round-trip 产物合同

目标文档的输出是 compact conformance receipt（`:137-148`）和落盘矩阵（`:107-111`），计划 Skill 结构也只有通用 `schemas.md/workflow.md/fixtures.md`（`:202-218`）。它没有声明这些文件属于 VDD 的哪个输入 route，也没有让 VDD Skill/validator 增加该 route。目标文档的组合链 “VDD → exact-cover producer → Quick Dev”（`:194-200`）证明的是下游 Quick Dev，而不是 “exact-cover Skill → VDD 再消费”。

单个生成的 requirements Markdown 也不能解决：VDD 明确把它路由到 direct implementation，不创建 VDD 目录（`SKILL.md:12-14`）。自动带出 `vdd_mode=create` 还会违反“必须由用户显式请求”的路由规则。

直接修正：

- **FR-RT-001**：明确选择一种 round-trip：
  - 推荐：新增 `vdd-source-bundle.v1` 非授权 handoff，并同步扩展 VDD 的显式 create/repair adapter；或
  - 产物就是一个 schema-valid 的完整 execution-plan 目录，仅能在用户显式请求下作为 VDD `repair` 原目标再次消费。
- **FR-RT-002**：若采用 bundle，至少输出 `bundle.json`、canonical requirements projection、source inventory、obligation disposition、coverage matrix、conflict/open-item list、validator receipt；bundle 必须含 schema version、target repository-relative path、source/validator hashes、candidate identity、recommended route（非授权）、`authorizes: []`。
- **FR-RT-003**：VDD consumer adapter 必须独立重算 bundle hash/closure，拒绝 caller route override，并仍要求用户显式 create/repair；bundle 不能自行发布 `plan-ready`。
- **NFR-RT-001**：producer 与 VDD adapter 的 schema 版本、canonicalization 和 hash 算法必须单一来源；未知 major version、缺文件、hash drift、路径越界均 fail closed。
- **AC-RT-001**：真实 composition 测试运行新 Skill producer，再在全新进程中以其产物调用 VDD adapter；VDD 必须创建/修复预期计划，且每个 source obligation 在计划中有 observable acceptance path。
- **AC-RT-002**：同一测试删除 bundle 中一个 source、篡改 canonical projection、复用旧 receipt、传入隐式 `vdd_mode=create`，VDD 均必须拒绝且不发布 `plan-ready`。
- **AC-RT-003**：输入仅为生成的单个 Markdown 且用户未明确要求 VDD create 时，断言仍走 direct implementation；不得把该行为误报为 round-trip 成功。

### P1-3：目标文档误述 Chapter 5，缺少关键的 align、条件 lane、恢复与止损语义

目标文档 `:13-23` 声称 Chapter 5 “定义”为 obligation/canonical acceptance 链，但原文没有该定义。现稿 S0-S5 虽覆盖 source freeze、extract、canonicalize、preflight 和 receipt，却没有：

- 何时应该/不应该进入该 Skill 的条件门；
- preflight 后不可跳过的独立 `align` 与 semantic gate；
- extract 失败后的下游降载；
- run identity 对 target/source/profile/mode/validator 的 resume 约束；
- `failure_category` / `extract_fail_bucket` / `family` / quarantine / recommended action；
- `hard_uncovered` 时先补内容、禁止原样重试或单纯增加预算的可机检策略。

目标文档 `:175` 只有一句“不得原样重试”，不足以重现 Chapter 5 的可运行控制面。

直接修正：

- **FR-C5-001**：增加 typed activation predicate：只有检测到 coverage/refs/acceptance/semantic instability，或用户显式审查时运行；不满足时输出 `not_required` 非授权 receipt。
- **FR-C5-002**：将工作流明确为 `discover/freeze → deterministic preflight → extract → align → source coverage → semantic gate → receipt`；preflight PASS 不得省略后四步。
- **FR-C5-003**：定义 resume key = target + complete source manifest hash + profile/policy + write/apply mode + validator identity；key 漂移必须新 run 或 `--no-resume`。
- **FR-C5-004**：定义稳定失败 taxonomy、family 聚合、分片重跑、quarantine 和 recommended action；`hard_uncovered|schema_error|obligation_fail` 禁止通过 timeout/retry 转绿。
- **AC-C5-001**：preflight PASS 但 align 或 semantic gate FAIL 的 fixture 必须最终 blocked，证明 preflight 不替代后续门。
- **AC-C5-002**：连续相同 failure family 达阈值时，仅隔离失败 shard，保留成功 shard receipt；变更 source/profile/mode 后拒绝旧 resume state。

### P1-4：“exact-cover”集合语义未定义，当前规则允许多种相互矛盾的解释

目标文档一方面要求 requirement/acceptance 双向 exact-cover（`:125`），另一方面允许一个 requirement 被多个合法 slice 消费（`:111`），还允许一个 acceptance 绑定多个 obligations（`:96-103`）。这可以是合理的多对多 sound-and-complete coverage，但不是数学上的 disjoint exact cover。未定义 universe、投影、重复/合并/别名规则和允许重叠的边界，validator 无法得到唯一判定。

直接修正：

- **FR-COV-001**：定义集合 `U`（active source obligations）、`R`（canonical requirements）、`A`（canonical acceptance）、`S`（implementation slices）及版本化关系；至少要求 domain/range equality、无 unknown、每个 active 元素度数下限、typed deferred disjoint、重复经 canonical alias/merge 处置。
- **FR-COV-002**：将术语明确为 `bidirectional sound-and-complete cover`；若坚持 `exact-cover`，必须规定允许重叠的显式例外和唯一 consumer/partition 条件。
- **AC-COV-001**：覆盖 missing、unknown、duplicate alias、非法重复、合法多 consumer、orphan acceptance、deferred leakage，并对每个 fixture 给出唯一预期结果。

### P2-1：产物 schema、稳定错误码和 bounded summary 仅有文字描述

目标文档描述 receipt 应 schema-valid、hash-bound、bounded（`:137-140`），但没有版本化 JSON Schema、canonical serialization、最大预算、错误码集合、原子发布/中断恢复规则。VDD repair 与 knowledge context 已有“完整 bytes 暂存后发布”和 interrupted orphan receipt 恢复语义（`SKILL.md:122-125`），新产物至少应达到同级可恢复性。

直接修正：

- **FR-ART-001**：为 inventory/matrix/receipt/handoff 分别提供版本化 schema，声明 required fields、枚举、canonical JSON 和错误码；写入临时 staging 后原子发布。
- **NFR-ART-001**：bounded summary 必须量化，例如最大错误 ID 数、最大字节数、截断标志和完整 evidence path/hash；不得静默截断。
- **AC-ART-001**：进程在 matrix 已写、receipt 未发布时中断；重启只能补发与既有 bytes hash 一致的 receipt，否则新建 run，历史文件不可覆盖。

## 4. 已满足或部分满足的点

- **PASS**：LLM 只做候选抽取/语义解释，不发布 PASS；exact-cover/hash/ID 归确定性层（目标文档 `:119-135`、`:150-161`）。
- **PASS**：caller 的 `exactCoverPassed`、`complete`、`verified` 不受信任，Acceptance 独立重算（`:141-148`、`:163-175`）。
- **PASS**：evidence 要求 current 且 candidate/hash-bound，中间产物 `authorizes=[]`，没有篡夺 lifecycle owner（`:54-67`、`:107-111`、`:163-175`）。
- **PARTIAL**：有 producer/consumer、negative、mutation 和 stale evidence fixtures（`:177-200`），但缺真正的新 Skill producer → VDD consumer composition。
- **PARTIAL**：有 compact receipt 与主上下文预算意识（`:137-140`、`:245`），但预算和 schema 尚不可执行。

## 5. 必需产物形状（建议最小合同）

若选择推荐的 bundle adapter 路径，最小输出应为：

```text
<run-root>/
├── vdd-source-bundle.v1.json
├── source-inventory.v1.json
├── canonical-requirements.md
├── obligation-dispositions.v1.json
├── source-requirement-acceptance-cover.v1.json
├── conflicts-and-open-items.v1.json
└── conformance-receipt.v1.json
```

`vdd-source-bundle.v1.json` 必须只引用同一 run 的 repository-relative 文件及 hashes，声明 complete source-role set、candidate/validator/policy identity、result、non-authorizing recommended route 和 `authorizes: []`。VDD 必须拥有对应 adapter 并在显式 create/repair 后独立复算；没有 consumer adapter 和真实 composition fixture 时，不得声称“可被 VDD 再次消费”。

## 6. 最小放行条件

只有同时完成以下事项，条件 3/4 才可改判 PASS：

1. 修正 Chapter 5 引述，并加入 conditional/preflight/extract/align/coverage/semantic/resume/failure-family 合同。
2. 以 VDD 真实 consumer graph 独立发现 required source-role closure，而不是信任 caller 的 `vdd_sources`。
3. 决定并冻结 round-trip artifact shape，同时扩展 VDD 明确输入 adapter；继续保留显式 create/repair 用户意图门。
4. 形式化 coverage 集合不变量，区分 sound-and-complete coverage 与 disjoint exact cover。
5. 增加新 Skill producer → VDD consumer 的跨进程正/负 composition tests，并证明 stale/omitted/implicit-route 均 fail closed。
