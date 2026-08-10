# Source Exact-Cover Review

- Review target: `execution-plans/2026-08-10-vdd-conformance-exact-cover-requirements.md`
- Review mode: BMad PRD Validate / source reconciliation
- Sources: root `AGENTS.md`, root `README.md`, `docs/know14.txt`
- Date: 2026-08-10
- Method: 将来源中的规范性陈述分组为稳定的 source unit，再逐组映射到目标行；“提到来源”不计覆盖，只有转化为明确、可证伪、可验收的需求才计完整覆盖。

## Gate verdict

**FAIL。目标文档准确抓住了 deterministic exact-cover 的方向和大部分主链，但当前 `requirements-ready` 结论不成立。** 它既没有把根治理文件中与新 Skill 直接相关的 LLM/Locator、编码、证据、ADR 和文档交付约束纳入需求，也没有完整保留 `know14.txt` 的 Quick Dev 证据绑定、`implementation-complete` 定义、Acceptance typed status、漂移全集、artifact/schema/CLI/error-code 合同及文档/ADR closure。由于这些缺口会让下游实现产生多种互不兼容但表面“满足 PRD”的实现，本 PRD 尚不能作为 exact-cover 的充分上游。

| 用户条件 | 结论 | 判定依据 |
| --- | --- | --- |
| 1. 基于 `AGENTS.md` 和 `README.md` | **FAIL** | 目标没有把两文件列为 Related sources（目标 8），且遗漏根 `AGENTS.md` 110-127、179-187 与 `README.md` 146-150 对本 Skill 直接适用的编码、共享 LLM 入口、Locator/frozen context、证据和 ADR 约束。 |
| 2. 吸收 `docs/know14.txt` 所有内容 | **FAIL** | 主链覆盖良好，但 K04-K09、K11-K14、K16、K19、K21、K24-K29、K32 存在规范性弱化或遗漏；仅在目标 8 声明 Related source 不能替代逐项需求化。 |

## Findings

### Critical

#### SRC-001 — Quick Dev 入口、slice evidence 和 `implementation-complete` 合同被语义弱化

`know14.txt` 541-629 明确要求 Quick Dev 只验证 receipt 存在、schema valid、hash current、`decision == exact_cover_passed`，失败固定路由 `vdd_repair_required`；每个 slice evidence 必须绑定 `slice_id`、`requirement_ids`、`acceptance_ids`、contract hash、exact-cover hash；并正式定义 `implementation-complete = current exact-cover + all required slices complete + current slice evidence`，且不等于 `acceptance-passed`。

目标只在 239 写“拒绝 missing/stale contract，evidence 与 contract hash 绑定”，遗漏 exact-cover hash、requirement/acceptance IDs、decision/schema 检查和 repair route；目标 234 把 `implementation-complete` 用作“新 Skill 自身完成”的门，而 249-264 只有流程图，没有给出 Quick Dev lifecycle predicate。结果是实现可以只校验 contract hash、仍生成旧式 `implementation-complete`，却通过本 PRD 的验收。

修复要求：把上述 Quick Dev gate、slice evidence 字段和 lifecycle predicate 逐项写成 FR/AC，并增加 `vdd_repair_required` 与 hash drift 的可执行负例。

### High

#### SRC-002 — Acceptance matrix 不是完整的机器合同

`know14.txt` 666-810 要求矩阵行包含 slice IDs、implementation refs、test definition refs、test-run evidence IDs、candidate binding hash 和 typed status；状态至少为 `verified|missing|partial|blocked|explicitly_deferred|not_applicable`，禁止模糊状态。implementation ref 还必须处理 repository logical path、custody path、typed tombstone 和 requirement/slice 映射；test evidence 必须绑定 registered command、selector、definition、run result、timestamp/run identity。

目标 107-111、129-135、165-173 仅列宽泛字段和“current/hash-valid”，没有 typed status 枚举、tombstone、selector/registered-command 关联、run result 与 run identity。目标 143 虽称独立重建 matrix，但未规定 canonical `requirement-conformance-matrix.v1.json`。这使“verified”的实现判定仍可各自解释。

#### SRC-003 — Exact-cover artifact、schema、CLI 和错误协议缺失

`know14.txt` 420-537 定义 `exact-cover.v1.json` 的最低字段和 source binding；1116-1177 要求两类 schema、支持 `validate`/`inspect` 的 machine-JSON CLI，以及稳定的 VDD-EXACT/ACC-CONF 错误族。目标 137-139 只有 generic compact receipt，202-218 的 Skill 树只有 `references/schemas.md`，没有 JSON schema artifact、inspect mode、artifact filename/version 或错误码合同。目标 181-192 的 fixture 也因此大多只说明“失败”，无法断言具体机器结果。

这不是实现细节：artifact 版本、consumer 可解析字段、命令模式和错误类别是 VDD、Quick Dev、Acceptance 三方的产品接口，必须进入 PRD 可验收面。

#### SRC-004 — Drift binding 集合不完整，不能证明旧证据自动失效

`know14.txt` 882-907 要求 requirements、acceptance、contract、changed paths、implementation bytes、test definitions、test commands、validator、policy、knowledge context 任一变化都使 evidence stale。目标 61-62、109、134、167-170 只覆盖 candidate/source/contract/validator 和笼统 evidence current，未要求 test-command identity、policy hash、knowledge-context binding，也未明确 changed-path/implementation-byte manifest。

该遗漏还与根 `README.md` 150 的知识库 Locator/frozen accepted-source hash 要求相交。新 Skill 若不绑定 knowledge context，可以在上游知识变化后继续复用旧 conformance receipt。

#### SRC-005 — 根仓治理没有转化为 Skill 的交付约束

目标 8 只列 `workflow.md`、`know14.txt`、skill-creator，未列根 `AGENTS.md`/`README.md`。与本 Skill 直接相关但缺失的规则包括：

- 根 `AGENTS.md` 110-127 与 `README.md` 184-192：中文显式 UTF-8、代码/脚本/测试/输出用英文、Windows 兼容、evidence 写入 `logs/`、代码/测试引用 accepted ADR。
- 根 `AGENTS.md` 179-187 与 `README.md` 146-150：新 workflow helper/Python LLM 执行必须走共享 `_llm_backend.py::run_llm_exec`、stdin-first；VDD/Quick Dev/Bootstrap 已接 Locator，冻结上下文需重读并复验 accepted-source hash。
- 根 `AGENTS.md` 252-260：详细规则落标准/ADR，durable intent 放 execution plan，高频 evidence 放 `logs/`。

目标 119-121、150-161 明确引入 LLM，但没有共享入口、UTF-8 stdin 或 Locator requirement；目标 139、175 说 evidence 落盘，却未指定 `logs/`；目标也没有 accepted ADR 或相关标准更新的验收项。

### Medium

#### SRC-006 — Applicability/disposition 合同不足以 fail closed

`know14.txt` 381-416 要求 `applicable|not_applicable|deferred` typed、explicit、authority-bound，并给出 `authority_reference`、`reason`、`target_plan`。目标 81-83 仅有 `active|typed_deferred`，目标 135 只要求 deferred 可见，未覆盖 `not_applicable`、authority reference、reason、target plan；目标 165-173 也遗漏 `ambiguous applicability` 必须停止（来源 998-1021）。

#### SRC-007 — Consumer closure、dogfood 和完成谓词被压缩到不可核验

`know14.txt` 1534-1547 点名必须重放 VDD validator、Quick Dev adapter、Acceptance conformance、Acceptance review decision、cross-skill composition 和 shared CLI/schema 的所有直接消费者；1580-1622 还要求 all registered tests、no undeclared write，并规定 dogfood 从 requirements 一直证明到 acceptance result，全部来自真实 repository artifacts。

目标 246-247 只写“consumer-closure 测试全部通过”和“一个真实 plan dogfood”，没有测试集合、direct-consumer discovery、`no undeclared write` 或 dogfood 全链输出。下游无法客观判断 closure 是否完整。

#### SRC-008 — Documentation/ADR closure 完全遗漏

`know14.txt` 1726-1762 要求更新 VDD Skill、Quick Dev adapter、Refactor Acceptance、repository standard、ADR index，并增加 accepted ADR；还必须明确 `implementation-complete != acceptance-passed` 与 Exact Cover/Bootstrap 分工。目标没有对应交付物或 AC。该遗漏也违反根 `AGENTS.md` 125 的“代码或测试变更至少引用一个 accepted ADR”。

#### SRC-009 — Observability 和 acceptance-passed 语义过弱

`know14.txt` 1550-1574 将 `acceptance-passed` 定义为 current candidate、valid VDD exact-cover、valid Quick Dev implementation-complete、Acceptance conformance exact-cover、required deterministic evidence、required semantic assurance 的合取；1651-1671 列出 14 个最低诊断计数。目标 249-264 只有箭头流程，139 只说摘要/计数，没有枚举 acceptance predicate 或 counters。因此“输出了若干计数”和“走到流程末端”也可能被误判为满足。

### Low

#### SRC-010 — PRD 自身的 source reconciliation 证据不足

目标 8-9 宣称 `know14.txt` 已对齐且 confidence 0.90，但没有 source inventory、source hash、section-to-FR mapping 或未采纳项说明。考虑到本产品本身声称解决“上游不能静默消失”，PRD 应 dogfood 自己：至少附一份 `AGENTS.md`/`README.md`/`know14.txt` 到稳定需求 ID 的覆盖表，并对 intentional non-goal 给出 disposition。

## Root governance coverage map

| ID | Source | 规范性内容 | Target mapping | Status |
| --- | --- | --- | --- | --- |
| G01 | `AGENTS.md` 100-108; `README.md` 86-92 | standalone requirements 是直接实现输入；只有显式请求才建 VDD 目录；正式 Chapter 3-7 不是 Phase 默认路径 | 目标 7-8、52-67 | **完整/一致**：目标明确不创建完整 execution-plan，并把 Chapter 5 作为需求来源而非启动正式编排。 |
| G02 | `AGENTS.md` 110-127; `README.md` 184-192 | UTF-8、Windows、英文代码/测试/输出、logs evidence、小而确定、accepted ADR | 目标 54-65、137-139、175 | **遗漏/弱化**：仅路径和确定性被覆盖。 |
| G03 | `AGENTS.md` 179-187; `README.md` 146-148 | 共享 LLM/Codex entrypoint、stdin-first、读写边界、回归测试 | 目标 119-121、150-161 | **遗漏**：只分配 LLM 职责，未约束调用入口和 transport。 |
| G04 | `README.md` 150 | Locator 已接 VDD/Quick Dev/Bootstrap；冻结知识需重读、验 accepted hash 并绑定 run manifest | 目标 115-139 | **遗漏**：source freeze 未覆盖 Locator/knowledge context。 |
| G05 | `AGENTS.md` 152-159、226-231、252-260 | 验证/证据、历史保留、durable docs 和 evidence 位置 | 目标 137-139、175、222-230 | **部分**：保留历史与 legacy 明确，但未规定 `logs/` 和 docs/ADR 投影。 |
| G06 | `AGENTS.md` 161-165; `README.md` 40-46 | schema/API 默认兼容，未来能力不能提前宣称 active | 目标 4、222-230 | **部分**：legacy 策略存在；`requirements-ready` 却无 source closure evidence，状态声明过早。 |

## `know14.txt` normative coverage map

下表覆盖来源第 1-50 节；“完整”表示目标形成了可验收要求，“部分”表示只保留意图或丢失 consumer-visible 合同，“遗漏”表示没有目标要求。

| ID | Source section / lines | Target lines | Status and gap |
| --- | --- | --- | --- |
| K01 | §1-3, 1-119：名称、背景、双向全集、端到端目标 | 1-43, 249-275 | **部分**：主链完整；Acceptance required set 的显式等式未独立成 AC。 |
| K02 | §4-5, 121-197：非目标、五方 ownership、所有中间物非授权 | 42-50, 65, 159, 244 | **部分**：总体 ownership 保留；未逐项禁止自动改需求、Quick Dev 改计划、contract 自证及各 lifecycle owner。 |
| K03 | §6-9, 199-419：canonical sets、mapping、coverage、duplicate、typed disposition | 38-40, 73-111, 123-135 | **部分**：exact-cover/mapping/duplicate 有；disposition authority 字段和 `not_applicable` 缺失。 |
| K04 | §10, 420-460：`exact-cover.v1.json` 最低 schema | 137-139 | **遗漏**：只有 generic receipt，无 canonical artifact/version/fields。 |
| K05 | §11, 462-505：receipt 绑定 bytes、authority、schemas、validator、target 及五类 hash | 56-65, 87, 134, 139 | **部分**：缺 authority/schema/target/exactCoverHash 的明确字段。 |
| K06 | §12, 507-539：VDD plan validator 以 exact-cover 阻断 `plan-ready` | 127-135, 165-173 | **部分**：有 preflight，但未声明 plan-ready gate 和稳定 failure contract。 |
| K07 | §13, 541-571：Quick Dev entry 四项检查及 `vdd_repair_required` | 239 | **部分**：仅 missing/stale；缺 schema、decision、repair route。 |
| K08 | §14, 573-593：slice evidence 五项绑定 | 109, 187, 239 | **部分**：缺 slice/req/acceptance/exact-cover hash 的完整字段。 |
| K09 | §15, 595-631：`implementation-complete` 精确定义及不等于 acceptance | 234-247, 249-264 | **遗漏/冲突风险**：234 定义的是 Skill 自身 DoD，不是 Quick Dev lifecycle predicate。 |
| K10 | §16, 633-665：Acceptance 独立重算及 matrix artifact | 41, 109, 143 | **部分**：独立重算完整；artifact 名称/version 缺失。 |
| K11 | §17-19, 666-753：matrix row、typed status、verified 下限 | 107-111, 129-135 | **部分**：三类 evidence 下限保留；typed status 和部分 row 字段缺失。 |
| K12 | §20, 755-766：implementation ref 验证与 tombstone/custody | 59, 109, 173 | **部分**：path 安全有；typed tombstone、mapping、拒绝 self-report 缺失。 |
| K13 | §21, 768-790：requirement→acceptance→test definition，command/selector/ref | 91-105, 109, 129-135 | **部分**：binding 概念有；registered command/selector 的确定性关联未规定。 |
| K14 | §22, 792-814：current run evidence 五项 identity | 61, 109, 133-134, 169-170 | **部分**：缺 command identity、definition identity、result、timestamp/run ID 的明确合同。 |
| K15 | §23-24, 816-880：Acceptance 双全集和 silent disappearance | 38-43, 109-111, 131-143, 267-275 | **大体完整**：应补 matrix required-set 的显式 equality AC 与稳定错误。 |
| K16 | §25, 882-909：十类 drift | 61-62, 109, 134, 167-170, 186-187 | **部分**：缺 test command、policy、knowledge context 等绑定。 |
| K17 | §26-27, 911-968：deterministic/semantic 边界与 Bootstrap 职责 | 25-32, 45-50, 141-159 | **完整**。 |
| K18 | §28, 970-996：12 步 Acceptance routing order | 113-148 | **部分**：顺序主干存在，未把 resolve/refs/tests/evidence/final acceptance 定为完整 ordered gate。 |
| K19 | §29, 998-1023：fail-closed 全集 | 163-175 | **部分**：缺 exact receipt、slice evidence 和 ambiguous applicability 的明确 stop。 |
| K20 | §30-32, 1025-1114：legacy read/new write、历史 immutable、generic | 54, 175, 220-230 | **完整**。 |
| K21 | §33-35, 1116-1179：JSON schemas、validate/inspect CLI、错误码 | 202-218 | **遗漏**：仅 prose `schemas.md` 和单一 validate script 名。 |
| K22 | §36, 1181-1278：VCEC-S0-S3 | 113-148, 194-200 | **部分**：总体能力存在；S2 的 exact-cover identity/repair route 弱化。 |
| K23 | §37, 1280-1502：18 个正负 fixture | 177-192 | **部分**：场景大多归并覆盖；缺精确 expected artifact/error，clean exact-cover 基准未明确。 |
| K24 | §38-39, 1504-1548：三条 composition 与 consumer closure 清单 | 179-200, 246 | **部分**：composition 完整；named suites/direct consumers 缺失。 |
| K25 | §40, 1550-1576：`acceptance-passed` 合取语义 | 249-264 | **部分**：流程图不等于 machine predicate。 |
| K26 | §41, 1578-1597：terminal predicate | 234-247 | **部分**：缺 all registered tests、no undeclared write，且 slice 与 Skill workflow step 概念混用。 |
| K27 | §42, 1599-1624：真实 dogfood 全链 | 247 | **部分**：只要求一次 dogfood，未规定必须证明的链和 repository-artifact provenance。 |
| K28 | §43, 1626-1649：deterministic-first 性能边界 | 129, 150-161 | **完整**。 |
| K29 | §44, 1651-1673：最低 diagnostics counters、非授权 | 42, 139 | **遗漏/弱化**：未列 counters，仅写“计数”。 |
| K30 | §45, 1675-1705：path/receipt/caller integrity | 49, 54-65, 139, 165-173 | **完整**。 |
| K31 | §46, 1707-1724：三阶段迁移 | 222-230 | **完整**。 |
| K32 | §47-48, 1726-1762：docs updates、accepted ADR、两条必写语义 | 无 | **遗漏**。 |
| K33 | §49, 1765-1792：22 项 completion criteria | 232-247 | **部分**：主项覆盖；Quick Dev exact-cover hash、drift 全集、dogfood 全链等仍缺。 |
| K34 | §50, 1794-1858：最终状态与五条核心原则 | 249-275 | **部分**：核心原则完整；原文还要求 Acceptance 逐条证明当前实现、测试、证据，目标图示未补足前述字段合同。 |

## Conflicts and reference-only claims

- **Reference-only:** 目标 8 把 `know14.txt` 列作 Related source，目标 9 声称已对齐；没有覆盖 manifest/hash 或 disposition，不能证明“所有内容已吸收”。
- **Status conflict:** 目标 4 声称 `requirements-ready`，但目标 8 未列根治理来源，且 K04/K09/K21/K32 为整块缺失。
- **Term collision:** 目标 234 使用 `implementation-complete` 描述新 Skill 自身完成，而来源 595-629 把它定义为 Quick Dev 所拥有的 lifecycle state。该命名会让下游 VDD 无法区分“Skill implementation done”和“target plan implementation-complete”。
- **No direct semantic contradiction found:** 对已写出的 exact-cover、independent reconstruction、Bootstrap-after-deterministic、legacy immutability 和 non-authorizing receipt，目标与来源方向一致。

## Minimum changes required before PRD-ready

1. 新增 source authority/coverage 附录，把 `AGENTS.md`、`README.md`、`workflow.md` Chapter 5、`know14.txt` 分配稳定 source IDs、hash 和逐项 disposition。
2. 补齐 versioned artifact/schema/CLI/error contract：`exact-cover.v1.json`、`requirement-conformance-matrix.v1.json`、`validate`/`inspect` machine JSON 及稳定错误族。
3. 恢复 Quick Dev gate、slice evidence exact-cover hash、`vdd_repair_required` 和 `implementation-complete` 精确定义。
4. 补齐 Acceptance typed statuses、ref/test/run identities、tombstone、full drift bindings、required-set equality 和 acceptance-passed 合取 predicate。
5. 加入根治理要求：共享 LLM backend/stdin、Locator/knowledge hash、UTF-8/English/Windows、`logs/` evidence、accepted ADR、标准/三方 Skill 文档更新与明确 consumer closure。

## Residual note

本审查仅判断来源到 PRD 的需求覆盖，不验证 `workflow.md` Chapter 5 的逐条覆盖，也不判断该产物是否已经满足 `$vdd-execution-plan` 的输入合同；这两项应由相邻专项审查合并后给出最终四条件 verdict。
