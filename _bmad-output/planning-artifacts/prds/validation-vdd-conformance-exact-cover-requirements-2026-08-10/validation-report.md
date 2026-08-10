# Validation Report - VDD Conformance Exact-Cover Skill 需求规格

- **PRD:** `execution-plans/2026-08-10-vdd-conformance-exact-cover-requirements.md`
- **Rubric:** `.agents/skills/bmad-prd/assets/prd-validation-checklist.md`
- **Run at:** 2026-08-10T01:05:04+08:00
- **Grade:** Poor

## Overall verdict

当前文档四项门禁均为 **FAIL**，不应以现有 `requirements-ready` 状态进入实现，也不能声称其产物可被 VDD 再次消费。现稿对确定性检查、LLM 非授权、hash/current evidence、fail-closed 和负例已有良好方向，但 authority 全集闭包、`know14.txt` 的规范合同、Chapter 5 的完整运行思想以及 VDD round-trip consumer contract 都未闭合。

这不是措辞或章节数量问题。当前设计可能对调用方漏传后的不完整 `vdd_sources` 得出 PASS；现行 `vdd-execution-plan` 也不识别文档定义的 compact receipt。必须先建立可机检的 source closure、版本化产物和显式 consumer adapter，再谈 exact-cover 与二次消费。

## Requested gate verdicts

| Gate | Verdict | Reason |
| --- | --- | --- |
| 1. 基于根 `AGENTS.md` 与 `README.md` | **FAIL** | 只吸收了部分路径、安全和生命周期方向；共享 LLM backend、stdin-first、Locator/accepted hash、UTF-8/English/Windows、`logs/` evidence、accepted ADR 与文档闭环未需求化。 |
| 2. 吸收 `docs/know14.txt` 所有内容 | **FAIL** | 34 个规范主题仅 7 个完整、23 个部分、4 个整块遗漏；缺 Quick Dev gate、versioned exact-cover/matrix schema、CLI/error contract、完整 drift binding、typed status/tombstone、consumer closure 和 ADR closure。 |
| 3. 具备 Chapter 5 核心思想 | **FAIL** | 现稿保留了 preflight/extract/coverage 的方向，却把 Chapter 5 误述为固定链；缺 conditional lane、独立 align/semantic gate、resume identity、failure-family/quarantine 和 stop-loss。 |
| 4. 产物可被 VDD 再次消费 | **FAIL** | compact receipt 不是现行 VDD 输入；没有 handoff schema、VDD adapter、显式 create/repair 语义、profile/lifecycle 投影或 producer-to-VDD 跨进程组合测试。 |

## Dimension verdicts

- Decision-readiness - thin
- Substance over theater - adequate
- Strategic coherence - adequate
- Done-ness clarity - thin
- Scope honesty - thin
- Downstream usability - broken
- Shape fit - adequate

## Findings by severity

### Critical (4)

**[Decision-readiness] - Authority universe 没有可证明闭包** (§3:54-67; §5 S0:115-117)

`vdd_sources` 由 caller 提供，未定义从 repository/local governance、VDD direct contracts、knowledge policy/Locator、lifecycle authority、目标状态和调用者图独立发现 required source roles 的算法。漏传真实 authority 时仍可能对不完整集合得出 PASS。

Fix: 增加版本化 source-discovery/closure 合同、必需角色、目录展开/忽略规则、source manifest/hash、typed disposition 和缺源稳定错误码；caller 只能增加候选，不能缩减必需角色。

**[Source reconciliation] - `know14.txt` 的关键生命周期合同被弱化或遗漏** (§§4-8, 11)

Quick Dev 入口 gate、slice evidence 的 exact-cover hash 绑定、`implementation-complete` 精确定义、Acceptance typed matrix/tombstone/test identity/current-run identity均未形成完整机器需求。文档 §11 的验收无法证明这些来源义务被覆盖。

Fix: 为来源义务分配稳定 ID，恢复 Quick Dev、slice、Acceptance 和 lifecycle predicate 的原始约束，并建立 source obligation -> FR/NFR -> AC 双向映射。

**[Downstream usability] - 没有 VDD 可识别的 round-trip artifact** (§4.3:107-111; §5 S4:137-140; §9:202-220)

唯一明确产物是非授权 compact receipt/matrix，它是校验证据而不是 VDD requirements 输入。现行 VDD 仅接受单 requirements Markdown 的 direct implementation，或在用户显式请求下 create/repair 完整 execution-plan 目录。

Fix: 定义 `vdd-source-bundle.v1` handoff 及 VDD 显式 create/repair adapter，或明确产出 schema-valid 完整 plan 并只走显式 repair；两种路线均不得自行授权 `plan-ready`。

**[Chapter 5 conformance] - 对 Chapter 5 的核心语义描述不完整** (§1:13-23; §5:113-148)

Chapter 5 是条件触发的语义稳定化 lane，不是现稿声称的固定 obligation 链。preflight PASS 不替代 extract、align、coverage、semantic gate，也不能省略 resume identity 与 failure-family 止损。

Fix: 将工作流冻结为 `discover/freeze -> deterministic preflight -> extract -> align -> source coverage -> semantic gate -> receipt`，加入 activation predicate、resume key、failure taxonomy、quarantine 和 recommended action。

### High (8)

**[Done-ness clarity] - FR/NFR/AC 没有稳定 ID 与双向映射** (§§2-8, 11)

职责、S0-S5、fail-closed、负例和 12 条验收仅自然语言对应，规格自身无法 dogfood exact-cover。Fix: 建立全局稳定 ID、typed deferred ID 和 requirement <-> acceptance equality gate。

**[Artifact contract] - Schema、CLI、错误码和原子发布合同缺失** (§§4.3, 5 S4, 9)

缺 `exact-cover.v1.json`、matrix/handoff schema、canonical JSON、`validate/inspect` machine output、稳定退出码/错误族、bounded summary 上限和中断恢复。Fix: 将这些 consumer-visible 接口纳入 FR/NFR/AC，而非留在实现阶段。

**[Chapter 5 conformance] - 缺 align、恢复身份与 failure-family stop-loss** (§§5, 7)

现稿只有“不得原样重试”，不足以表达同 task/profile/apply mode 的 resume 约束、跨批次隔离、family 聚合和 `hard_uncovered` 先修内容的策略。Fix: 增加可机检状态机与正负 fixture。

**[Coverage semantics] - `exact-cover` 的集合含义不唯一** (§4:71-111; §5 S2:123-125)

文档同时允许合法多 consumer、多 obligation acceptance，却未说明这是允许重叠的 sound-and-complete cover，还是数学上的 disjoint exact cover。Fix: 形式化 U/R/A/S 集合、关系 domain/range、degree、alias/merge 与 overlap 规则。

**[Evidence currency] - Drift binding 不完整** (§§3, 4.3, 7)

未完整绑定 test definitions/commands、policy、knowledge context、changed paths 和 implementation bytes；知识或命令改变后可能复用旧 receipt。Fix: 按来源列全 drift vector 并加入逐项 mutation tests。

**[Repository governance] - 根治理未转化为交付要求** (Related sources; §§5-6, 11)

缺共享 `_llm_backend.py::run_llm_exec`、UTF-8 stdin、Locator accepted-source hash、Windows/English 约束、`logs/` evidence、accepted ADR 及标准/文档更新。Fix: 将适用治理规则映射到 NFR 与完成条件。

**[Consumer closure] - 没有 producer -> VDD 的真实组合测试** (§8:194-200; §11:246-247)

现有组合只覆盖 Quick Dev、Acceptance 和 review decision。Fix: 新进程运行 producer 后调用 VDD adapter，验证 explicit route、profile、knowledge preflight、plan-ready；对 omitted/stale/tampered/implicit-route 全部 fail closed。

**[Decision-readiness] - Risk route 不是确定性契约** (§5 S5:141-148; §6:152-159)

`low-risk` 与 `workflow-control-risk` 没有枚举、predicate、优先级、unknown 默认值或唯一 owner。Fix: 提供版本化 policy schema、冲突顺序和测试向量。

### Medium (6)

**[Applicability] - disposition 类型不足** (§4.1:81-83; §5 S3:127-135)

缺 `not_applicable`、authority reference、reason、target plan，并未明确 ambiguous applicability 必须停止。

**[Strategic coherence] - 缺产品指标和 counter-metrics** (§11)

只有测试通过与一次 dogfood；缺 false PASS=0、omission detection、false-block、运行/摘要预算和 legacy 成本指标。

**[Terminology] - Glossary 与 ID namespace 缺失** (§§3-5, 11)

`obligation_id`/`requirement_id`、canonical acceptance/Acceptance owner、evidence/receipt/matrix 的关系不明确。

**[Compatibility] - Legacy 风险未成为明确决策** (metadata; §10)

缺首版支持矩阵、迁移触发、退出条件及不兼容结果。

**[Observability] - 完成谓词与最低 counters 不可核验** (§§5 S4, 11-12)

流程箭头和“计数”不能替代 `acceptance-passed` 合取 predicate、registered tests、no undeclared write 与最低诊断字段。

**[Documentation closure] - 标准/ADR/consumer 文档更新遗漏** (§§9-11)

未要求更新 VDD、Quick Dev adapter、Acceptance、repository standard 与 ADR index，也未新增 accepted ADR。

### Low (2)

**[Self-dogfood] - PRD 没有自己的 source reconciliation artifact** (Related sources)

文档声称已对齐 `know14.txt`，却没有 source inventory/hash、section-to-requirement mapping 或 intentional omission disposition。

**[Shape fit] - 实现文件树早于消费契约定稿** (§9)

脚本名和目录布局已经确定，但 VDD re-entry artifact、risk policy、schema 与 route 仍未闭合。

## Mechanical notes

- `requirements-ready` 与当前 source closure、消费者合同状态冲突，应先降回 draft 或关闭 critical findings。
- `implementation-complete` 同时被用作 Skill 自身 DoD 与 Quick Dev lifecycle state，必须拆分命名。
- `stable`、`normalized`、`current`、`legitimate`、`bounded` 和“超预算”均缺可测试定义。
- 当前来源核对结果：`know14.txt` 34 个规范主题中，7 个完整、23 个部分、4 个遗漏。

## Minimum release gate

1. 建立独立 source-role closure，并让本 PRD 自身提供 source -> requirement -> acceptance 的机器可检覆盖表。
2. 补齐 versioned artifact/schema/CLI/error、Quick Dev/Acceptance/lifecycle 与完整 drift 合同。
3. 忠实投影 Chapter 5 的 conditional/preflight/extract/align/coverage/semantic/resume/stop-loss 思想。
4. 决定 round-trip artifact，并同步扩展 VDD 的显式 consumer adapter。
5. 通过 producer -> VDD 的跨进程正负 composition tests，证明缺源、漂移、篡改和隐式 route 均被阻断。

## Reviewer files

- `review-rubric.md`
- `review-source-exact-cover.md`
- `review-vdd-consumability.md`
