# Whole-directory Review 与验证标准

## 1. Review Authority

审查必须完整读取：本目录所有 Markdown、`schemas/**`、`bootstrap/**`、`tools/*.py`、`tools/tests/**`、本文件、97、98、99，以及 `AGENTS.md` 中与 review、Phase shared LLM/Codex 和文档维护有关的规则。两个既有重构目录只用于验证依赖/不重复边界和 Bootstrap read-only scope，不成为本计划业务要求来源。

## 2. Mechanical Checks

必须执行：

- Markdown 本地链接存在；
- JSON 与 JSON Schema 可解析；
- fixture suite 必须声明 `validationMode=schema+gateway`；每个实例分别记录 schema validity 与 composite gateway validity，二者不同时必须显式声明 `expectedSchemaValid`；
- finding line range、severity/status、可信 review policy 派生、unverified disposition 和 result layer-set gateway invariants 通过反例 fixture；
- 路径、字段、状态、severity、phase、动作名跨文档一致；
- 97 每条 RFG 有明确 owner 和 acceptance ref；
- 98/99 覆盖全部批准来源要求；
- historical finding ledger 没有 Open P0–P2；
- 未修改或复制两个上游重构目录的业务范围。
- Bootstrap prepare/gate/finalize tests 证明不调用 reviewer、不写目标 scope、缺 required layer 不 clean、stale evidence 被拒绝、P0/P1 必须手工 verifier；
- 检查四类 profile 的 role rubric、误报抑制、untrusted-content、deterministic preflight 与 bounded full-review cycle policy 及 policy hash；
- 检查 `preflight-result.json` 合同、required check 集合、evidence path/hash 和 gate/finalize binding；
- Bootstrap sidecar 使用 `supplemental_bootstrap` authority class，且工具中不存在 `scripts/sc`、LLM backend、BMAD/GDS skill invocation 或上游写入入口。

## 3. Finding 输出门禁

每条 P0–P2 必须包括：

- 稳定 finding ID：`RFG-REV-<round>-P<severity>-<nn>`；
- 精确文件、行号和原文；
- `input/trigger → required state → bad outcome`；
- 已读 authority/consumer/validator 或 caller/callee/test；
- 现有防护为什么未拦住；
- severity rationale；
- proposed owner 和 acceptance ref。

缺任一项时不得记录。零 finding 是合法结果。纯建议、格式和未来优化不进入 ledger。

## 4. Review 生命周期

1. 完整读取和机械检查；
2. candidate discovery；
3. fact gate；
4. fingerprint dedup；
5. P0/P1 独立核验；
6. 首轮 accepted findings 全部汇总后批量修复；
7. 修复期间只跑 targeted deterministic validation，禁止逐 finding 重跑 Whole-directory review；
8. 批量修复后执行一次最终 Whole-directory review；默认两轮，第三轮仅用于新 P0/P1 或 authority/context graph 改变，硬上限后 manual pause；
9. ledger 无 Open 且机械检查通过时 PASS。

## 5. Historical Finding Ledger

| Finding ID | Severity | Status | Evidence | Closure |
| --- | --- | --- | --- | --- |
| RFG-REV-1-P1-01 | P1 | Closed | Source refs: pre-fix `tools/validate_whole_directory.py:87` 使用 `re.findall(..., coverage)`；初次运行时 `RFG-001` 与 `RFG-021` 因说明文字被计为重复。触发为执行 validator，状态为覆盖正文含范围说明，结果为有效计划无法取得 PASS；已读取 97/99，旧防护缺口是对整个文档计数。 | validator 现仅解析 `## 3. Requirement Coverage` 表区；本地命令 PASS。Owner: plan validator；acceptance: `review-gate://RFG-021/plan-review-result`。 |
| RFG-REV-1-P1-02 | P1 | Closed | Source refs: pre-fix `schemas/review-finding.v1.schema.json:7-26` 全局要求完整证明，`02-finding-contract-and-severity.md:36-42` 又把 rejected 当 finding 状态。触发为缺字段候选进入 gateway，状态为只能使用 finding schema，结果为 rejection 无法记录或被迫伪造证明；现有防护没有独立 rejection shape。 | 新增 `review-rejection.v1.schema.json` 和 valid fixture。Owner: review contract；acceptance: `review-gate://RFG-007/gateway-validation-tests`。 |
| RFG-REV-1-P1-03 | P1 | Closed | Source refs: pre-fix `tools/validate_whole_directory.py:165-199` 只比较 fixture ID/expectedValid 布尔值，没有执行 schema。触发为 schema 与 fixture 漂移，状态为 JSON 均可解析，结果为错误合同仍返回 PASS；现有防护只检查声明意图。 | validator 现执行本计划所用 Draft 2020-12 关键字子集并逐例比对 expectedValid；P0/P1/P2 缺证明 fixtures 已加入。Owner: plan validator；acceptance: `review-gate://RFG-003/proof-triplet-tests`。 |
| RFG-REV-1-P1-04 | P1 | Closed | Source refs: pre-fix `02-finding-contract-and-severity.md:36-42` 原文为 `candidate -> rejected \| confirmed \| advisory \| refuted \| unverified`，但 `schemas/review-finding.v1.schema.json:52` 没有 rejected。触发为实现 disposition，结果为 consumer 无法决定合同；现有链接未声明两条状态流。 | 02 现拆分 accepted finding 状态机与 rejection record。Owner: review contract；acceptance: `review-gate://RFG-007/gateway-validation-tests`。 |
| RFG-REV-1-P1-05 | P1 | Closed | Source refs: pre-fix `04-gateway-dedup-verification-and-memory.md:32` 要求 rejected fingerprint 依赖 evidence hash，但 `schemas/review-rejection.v1.schema.json:17-38` 只有 candidate/input hash。触发为抑制 schema-invalid 候选，结果为重复误报无法稳定抑制；candidateHash 不能表达 authority/reason 组合。 | rejection schema 增加 `suppressionFingerprint`；04 明确其计算输入。Owner: gateway；acceptance: `review-gate://RFG-009/disposition-memory-tests`。 |
| RFG-REV-1-P1-06 | P1 | Closed | Source refs: pre-fix `schemas/review-result.v1.schema.json:35-49` 只约束 clean/failedLayers，允许空 findings 的 blocked 或携带 P1 的 advisory。触发为汇总状态生成，结果为自动 consumer 错误阻断或错误放行；现有 enum 不验证组合语义。 | result schema 增加 blocked/advisory/incomplete 条件与 fixtures；plan validator 支持 `anyOf/contains/minContains`。Owner: review contract；acceptance: `review-gate://RFG-004/incomplete-result-fixture`。 |
| RFG-REV-1-P1-07 | P1 | Closed | Source refs: pre-fix `schemas/review-finding.v1.schema.json:48` 为 `minimum: 0`。触发为低确信模式匹配候选，状态为泛化文本填满 shape，结果为噪音进入用户结果；现有范围校验只有 0–1。 | 新增 RFG-022，confidence 最低 `0.8`，加入 invalid fixture。Owner: review contract；acceptance: `review-gate://RFG-022/confidence-threshold-test`。 |
| RFG-REV-1-P1-08 | P1 | Closed | Source refs: pre-fix `01-scope-authority-and-non-goals.md:47` 允许“独立 schema/validator 工作”，`05-bmad-gds-and-codex-integration.md:44` 写“R1 gateway 可用”，与 `00-index.md:31`、`07-implementation-phases.md:30-42` 冲突。触发为 R1 实施或 AGENTS 同步，结果为提前触碰长期 owner 或宣称不存在的 gateway；现有 phase 名称未交叉验证。 | 01 限定为本目录 plan-local artifacts；05 要求 R1 standard 与 R2 gateway 均可用后再更新 AGENTS。Owner: phase coordinator；acceptance: `review-gate://RFG-017/upstream-handoff-evidence`。 |
| RFG-REV-1-P1-09 | P1 | Closed | Source refs: pre-fix `schemas/review-rejection.v1.schema.json:25-35` reason enum 没有 `low_confidence`。触发为 `confidence < 0.8` 候选，状态为 gateway 必须拒绝，结果为 rejection sidecar 无法表达真实原因；`schema_invalid` 会丢失可度量分类。 | 增加 `low_confidence` reason code；补充 blocked/advisory/incomplete 合法正例。Owner: review contract；acceptance: `review-gate://RFG-022/confidence-threshold-test`。 |
| RFG-REV-1-P1-10 | P1 | Closed | Source refs: pre-fix `04-gateway-dedup-verification-and-memory.md:68` 原文为 `Given P2 confirmed advisory`，与 `02-finding-contract-and-severity.md:39-44` 的 P0/P1 confirmed、P2 advisory 冲突。触发为汇总 P2，结果为实现者可能写入 result schema 不接受的 `confirmed`；现有 prose 验收未引用状态枚举。 | 改为 `Given P2 advisory`，并由 semantic validator 禁止旧短语。Owner: gateway；acceptance: `review-gate://RFG-011/lifecycle-tests`。 |
| RFG-REV-1-P1-11 | P1 | Closed | Source refs: pre-fix `01-scope-authority-and-non-goals.md:51` 只对 R2–R6 检查 handoff，但同文件 47 行禁止 handoff 前把 R1 schema/validator 迁入长期 owner。触发为开始 R1，结果为验收条款允许绕过上游门；现有正文与 Given/When/Then 范围不一致。 | 验收范围改为 R1–R6，并由 semantic validator 固定。Owner: phase coordinator；acceptance: `review-gate://RFG-017/upstream-handoff-evidence`。 |
| RFG-REV-2-P1-01 | P1 | Closed | Source refs: pre-fix `04-gateway-dedup-verification-and-memory.md:30` 要求合并 reviewer 来源，但 `schemas/review-finding.v1.schema.json:7-55` 没有 provenance 字段。触发为 Blind/Edge/Acceptance 命中同一缺陷，状态为 dedup 后只剩单条 finding，结果为 consumer 无法追溯或校准各 reviewer；现有 `dimension` 只描述审查维度。 | finding schema 新增必填 `sourceReviewers[]`，三个 adapter 和 fixtures 使用稳定 role 值。Owner: review contract；acceptance: `review-gate://RFG-025/source-reviewer-dedup-test`。 |
| RFG-REV-2-P1-02 | P1 | Closed | Source refs: `.agents/skills/bmad-code-review/steps/step-02-review.md:14-16` 明确 no-spec 跳过 Acceptance Auditor，但 pre-fix `schemas/review-result.v1.schema.json:7-24` 只有 failedLayers。触发为 no-spec review，结果为 skip 被误判为空成功或失败，从而产生假 clean/incomplete；现有 result contract 无 not-applicable 状态。 | result schema 新增必填 `skippedLayers[]` 和 reason；zero-finding fixture 覆盖 `not_applicable_no_spec`。Owner: review contract；acceptance: `review-gate://RFG-026/skipped-layer-result-test`。 |
| RFG-REV-2-P1-03 | P1 | Closed | Source refs: `05-bmad-gds-and-codex-integration.md` 的 route handoff 要求版本化，但 pre-fix finding/result/rejection schema 均无 route version。触发为旧 7 月 7 日 run 与 R3 新 route 并存，结果为 sidecar、fingerprint 或 metrics 可能混用，无法证明“不干扰当前审查”；现有 authorityRevision 只标识内容 authority。 | result/rejection schema 增加必填 `routeVersion`，04/05/06 固定 namespace 与切换测试。Owner: review route maintainer；acceptance: `review-gate://RFG-027/route-version-isolation-test`。 |
| RFG-REV-2-P1-04 | P1 | Closed | Source refs: pre-fix finding `sourceReviewers[]` 使用 `edge_case_hunter`，但 `schemas/review-result.v1.schema.json` fixture 使用 `edge-case`，`review-rejection.v1` fixture 使用 `blind`。触发为关联失败层、rejection 和 merged finding，结果为 consumer 无法按 reviewer identity join；现有各 schema 独立使用自由字符串。 | 三份 schema 统一稳定 reviewer role enum，fixtures 和 semantic validator 验证完全相同 vocabulary。Owner: review contract；acceptance: `review-gate://RFG-028/reviewer-role-vocabulary-test`。 |
| RFG-REV-3-P1-01 | P1 | Closed | Source refs: pre-fix `96-global-review-and-validation.md:52` 的 inline code 含未转义 pipe 字符。触发为 Markdown 表格 consumer 读取 ledger，状态为该行被拆成额外列，结果为 finding evidence/closure 无法可靠解析；旧 validator 只搜索整行子串。 | 转义 inline-code pipes；validator 强制五列结构。Owner: plan validator；acceptance: `review-gate://RFG-021/plan-review-result`。 |
| RFG-REV-3-P1-02 | P1 | Closed | Source refs: pre-fix `review-result.v1.schema.json:7-82` 没有 required/completed layer，`zero-findings-clean` fixture 也不证明 reviewer 完成。触发为所有 reviewer skipped，状态为 failed/findings 为空，结果为未经审查的 clean；旧 skippedLayers 只记录跳过。 | result schema 增加 required/completed layers；gateway/validator 强制 layer-set 完备互斥；新增 all-skipped invalid fixture。Owner: review contract；acceptance: `review-gate://RFG-026/skipped-layer-result-test`。 |
| RFG-REV-3-P1-03 | P1 | Closed | Source refs: pre-fix `04-gateway-dedup-verification-and-memory.md:17,32,34` 和 `review-finding.v1.schema.json:7-27` 未把 routeVersion 绑定 candidate/finding/fingerprint。触发为旧/新 route 产生相同候选，结果为跨 route 抑制或错误消费；result/rejection routeVersion 不能保护 candidate sidecar。 | finding schema、fixtures、evidence fingerprint 与 suppression fingerprint 全部绑定 routeVersion。Owner: review gateway；acceptance: `review-gate://RFG-027/route-version-isolation-test`。 |
| RFG-REV-3-P1-04 | P1 | Closed | Source refs: pre-fix `review-finding.v1.schema.json:49-50` 只要求行号大于等于 1。触发为 startLine 20/endLine 10，结果为不可操作 finding 通过；旧 gateway prose 没有反例 fixture。 | gateway semantic validator 强制 endLine 大于等于 startLine；新增 reversed-line-range fixture。Owner: review contract；acceptance: `review-gate://RFG-007/gateway-validation-tests`。 |
| RFG-REV-3-P1-05 | P1 | Closed | Source refs: pre-fix `review-finding.v1.schema.json:62,68` 独立定义 severity/status。触发为 P1 advisory 或 P2 unverified，结果为 blocker 错误放行或 P2 进入 verifier；旧 result schema 只部分限制用户结果。 | finding schema 增加 severity/status 条件，semantic validator 与两个 invalid fixtures 复核。Owner: review contract；acceptance: `review-gate://RFG-007/gateway-validation-tests`。 |
| RFG-REV-3-P1-06 | P1 | Closed | Source refs: pre-fix `validate_whole_directory.py:74-89` 只校验 RFG ID 和 99 次数，未解析 97 owner/phase/acceptance/status 或 98 来源。触发为清空 owner/acceptance 或删除来源映射，结果为不可实施计划仍 PASS；旧 prose 检查没有机器 consumer。 | validator 结构化解析 97/98/99，校验 ID 顺序/唯一性、owner/phase、acceptance URI、status 与 owner/phase 双向一致。Owner: plan validator；acceptance: `review-gate://RFG-021/plan-review-result`。 |
| RFG-REV-3-P1-07 | P1 | Closed | Source refs: pre-fix `validate_whole_directory.py:270-276` 硬编码 15 条并只接受 Closed，与 `96-global-review-and-validation.md:65` 允许 Refuted 冲突。触发为新增或 Refuted finding，结果为合法 review 无法 PASS 或被迫误标 Closed。 | 移除固定数量；结构化验证稳定 ID、severity、Open、Closed 与 Refuted counterevidence。Owner: plan validator；acceptance: `review-gate://RFG-021/plan-review-result`。 |
| RFG-REV-3-P1-08 | P1 | Closed | Source refs: pre-fix `05-bmad-gds-and-codex-integration.md:60-63` 与 `07-implementation-phases.md:81-87` 分别要求 R2 后和 R6 更新 AGENTS，且未满足 `docs/standards/_index.md:33` 的 R1 README/索引同步。触发为 R1/R2/R3/R4 能力落地，结果为文档提前宣称或 operational route 仍指向旧规则。 | 05/07 改为 R1 导航、R2 AGENTS gateway、R3 AGENTS 三层 route、R4 README public behavior、R6 最终状态的同批同步合同。Owner: phase/docs coordinator；acceptance: `review-gate://RFG-020/documentation-sync-check`。 |
| RFG-REV-4-P1-01 | P1 | Closed | Source refs: pre-fix `96-global-review-and-validation.md:13-14` 把 JSON Schema validity 与 gateway invariant 分列，但 `review-validation-fixtures.v1.json:379-427` 的 all-skipped 与 reversed-range 仅由 semantic validator 判 invalid。触发为生产级 Draft 2020-12 validator 单独执行，状态为两个实例 schema-valid，结果为 expectedValid 与声明冲突；旧 fixture 没有 validation stage。 | fixture suite 现固定 `validationMode=schema+gateway`；schema-valid 但 composite-invalid 的案例必须声明 `expectedSchemaValid=true`，validator 分别核对两个阶段。Owner: plan validator；acceptance: `review-gate://RFG-007/gateway-validation-tests`。 |
| RFG-REV-4-P1-02 | P1 | Closed | Source refs: pre-fix `review-result.v1.schema.json:11,25-28` 接受 producer 自报 requiredLayers，`04-gateway-dedup-verification-and-memory.md:28` 仅校验集合内部一致。触发为 producer 只声明 manual reviewer，状态为 required/completed 相同且三层 reviewer skipped，结果为未经既定 route 审查仍 clean；旧合同没有可信 policy authority。 | result 必填 `reviewProfile`/`policyRevision`；gateway/validator 要求其匹配 execution context 已分配 policy，再从可信 registry 派生 requiredLayers；producer-narrowing 与 trusted-profile-substitution 反例均 fail closed。Owner: review policy/gateway；acceptance: `review-gate://RFG-026/skipped-layer-result-test`。 |
| RFG-REV-4-P1-03 | P1 | Closed | Source refs: pre-fix `04-gateway-dedup-verification-and-memory.md:44-45` 区分阻断与人工暂停，但 `review-result.v1.schema.json:137-167` 允许同一 P1 unverified 同时形成 blocked 或 incomplete。触发为相同 verifier 结果由不同 producer 汇总，结果为 consumer 得到相反处置；旧合同没有机器分类。 | finding 新增 gateway-owned `unverifiedClass`/`unverifiedDisposition`；schema、semantic validator 与组合 fixtures 强制 security/data_loss 仅 blocking、other 仅 manual_pause，并拒绝 manual_pause 混入含 confirmed blocker 的 blocked result。Owner: review result contract；acceptance: `review-gate://RFG-010/verifier-scope-tests`。 |
| RFG-REV-4-P1-04 | P1 | Closed | Source refs: pre-fix `review-validation-fixtures.v1.json:61-87` 的 missing-consumer 案例同时使用 `confidence=0.5`。触发为 consumer required 约束被误删，状态为低 confidence 仍存在，结果为 fixture 继续 invalid 并产生假绿；旧 validator 不检查预期失败原因。 | missing-consumer fixture 现使用合法 confidence，并声明 `expectedErrorContains=missing required consumer`；validator 强制目标错误出现。Owner: document adapter fixture owner；acceptance: `review-gate://RFG-006/document-adapter-fixtures`。 |
| RFG-REV-5-P1-01 | P1 | Closed | Source refs: Bootstrap Skill 自审 `BSR-0A5B2119C52CF2BB`、`BSR-1787C8598C0F5E0B`、`BSR-72300A33E211A064`，pre-fix `tools/run_bootstrap_review.py:650-655` 在 gate 重跑时无条件覆盖非空 `verifier-output.json`。触发为独立 verifier 已保存决策后恢复/重跑 gate，结果为核验 evidence 静默丢失；Skill preflight 不能约束直接 CLI 调用。 | `command_gate` 现于任何 sidecar 写入前读取 verifier output，非空 decisions 时非零退出并保持文件字节不变；增加 gate-rerun preservation 回归。Owner: Bootstrap gate owner；acceptance: `review-gate://RFG-043/verifier-decision-preservation-test`。 |
| RFG-REV-5-P1-02 | P1 | Closed | Source refs: Bootstrap Skill 自审 `BSR-7DB895AD69466508`，pre-fix `tools/run_bootstrap_review.py:501-507` 的 fingerprint 未形成 severity-safe evidence root。触发为同证据 P2 先于 P1，结果为 P1 被 duplicate rejection 吞掉并绕过 verifier；旧测试只覆盖同 severity duplicate。 | gateway 现按 artifact、inclusive line range、exact evidence、route/authority 构建 evidence root，组内确定性保留最高 severity、合并 source reviewers，并把其余变体写 duplicate rejection；增加 P2→P1 回归。Owner: Bootstrap dedup owner；acceptance: `review-gate://RFG-044/severity-safe-evidence-root-dedup-test`。 |
| RFG-REV-6-P1-01 | P1 | Closed | Source refs: Skill/route 完整复审 `BSR-17E836AA4258FA55`，pre-fix `04-gateway-dedup-verification-and-memory.md:83` 指定 `routeVersion=review-bootstrap.v1`，而 profile/CLI 实际使用 `bootstrap-review-route.v1`，candidate/rejection 等 sidecar 还未完整绑定 route/profile/hash。触发为 consumer 按文档 route identity 选择 sidecar，结果为真实产物无法匹配或跨 route 混用；现有 validator 只固定 profile 值，未验证全部 sidecar。 | 统一 `review-input.json.routeVersion` 为唯一 authority；所有 Bootstrap sidecar、最终 result 与报告投影完整 binding，gate/finalize 校验中间状态绑定并加入回归。Owner: Bootstrap route owner；acceptance: `review-gate://RFG-046/bootstrap-sidecar-route-binding-test`。 |
| RFG-REV-6-P1-02 | P1 | Closed | Source refs: Skill/route 完整复审 `BSR-B980F079DB28A2F9`，pre-fix `04-gateway-dedup-verification-and-memory.md:85` 声称 P0/P1 gate 保持 incomplete，但 CLI/测试输出 `awaiting_verification`，且该中间 contract 无 Schema。触发为 consumer 处理 accepted P0/P1，结果为把合法待核验 run 当未知/终态而跳过 verifier；Skill 路由能识别实际值但不能修复 plan/Schema 分裂。 | 明确 `awaiting_verification` 是 gate-only 状态；新增 `bootstrap-review-gate-result.v1.schema.json`，CLI 在 gate/finalize 校验，operator/Skill/计划同步并加入无 blocker 反例。Owner: Bootstrap gate contract owner；acceptance: `review-gate://RFG-047/bootstrap-gate-state-schema-test`。 |
| RFG-REV-7-P1-01 | P1 | Closed | Source refs: 修复后 Skill/route 复审 `BSR-228E1FECD473CC01`，pre-fix `tools/run_bootstrap_review.py:519-524` 只验证 failure tuple 字符串非空。触发为 reviewer 提交 `TBD`/`TODO`/`N/A`，状态为其余 hash、行号、context、guard 均合法，结果为无具体失败模式的候选进入 verifier 或 P2 advisory；现有 schema minLength 与测试均未识别占位等价文本。 | gateway 对 failure tuple 做大小写、空白、标点归一化并拒绝稳定占位词表；prompt、Skill、operator 和 02 明确规则，新增 rejection 回归。Owner: Bootstrap fact-gate owner；acceptance: `review-gate://RFG-048/placeholder-failure-tuple-test`。 |
| RFG-REV-8-P2-01 | P2 | Closed | Source refs: 第三轮修复后 Skill/route 复审 `BSR-0DF285E493C6BA06`，pre-fix `tools/run_bootstrap_review.py:459-460` 对 completed `readArtifacts` 与 manifest list 做顺序比较。触发为 reviewer 已读全部 artifact、missing 为空但重排 read array，结果为合法输出被误判 incomplete；schema 和公开合同只要求完整 unique 集合。 | completed coverage 改为 set equality，保留 requiredArtifacts/pending template 的绑定顺序；新增 reversed order clean 回归。Owner: Bootstrap coverage owner；acceptance: `review-gate://RFG-049/order-independent-coverage-test`。 |
| RFG-REV-8-P1-01 | P1 | Closed | Source refs: 第三轮修复后 Skill/route 复审 `BSR-461C76DC1E9C0E73`，pre-fix `tools/run_bootstrap_review.py:810-815` 只验证 verifier evidenceChecked 为非空且 in-scope。触发为 verifier 用 `AGENTS.md:1` 等无关 in-scope 引用确认 P1，结果为 finalize 生成无证据支撑的 blocked result；现有测试只覆盖 out-of-scope。 | verifier 现在必须覆盖 finding 精确行范围及全部 contextRead，prompt/Skill/operator 同步；增加 unrelated in-scope fail-closed 回归。Owner: Bootstrap verifier owner；acceptance: `review-gate://RFG-050/verifier-evidence-relevance-test`。 |
| RFG-REV-9-P1-01 | P1 | Closed | Source refs: 第四轮修复后 Skill/route 复审 `BSR-9BAAC153EC8B1893`，pre-fix `tools/run_bootstrap_review.py:502-505` 在 required context 无行号时接受任意同文件行范围。触发为 contextRead=`AGENTS.md`、verifier 仅检查 `AGENTS.md:1`，结果为局部检查冒充整文件 closure 并控制 blocker disposition。 | `reference_covers` 现要求 path-only required reference 只能由 path-only checked reference 覆盖；新增先失败、整文件引用后成功的回归。Owner: Bootstrap verifier coverage owner；acceptance: `review-gate://RFG-052/path-only-context-coverage-test`。 |
| RFG-REV-9-P1-02 | P1 | Closed | Source refs: 第四轮修复后 Skill/route 复审 `BSR-DE4363AC33AA4D9F`，pre-fix `read_json` 使用 Python 默认 `json.loads`，且 confidence 只做有序比较。触发为 JSON confidence=`NaN`，结果为 `<0.8` 与 `>1` 均 false，非有限数候选进入 blocker；本地 schema runtime 同样从宽解析。 | CLI 与 Whole-directory validator 使用 strict parse_constant；canonical/write 禁止 allow_nan；candidate gate 增加 `math.isfinite`；新增 NaN incomplete 回归。Owner: Bootstrap JSON/fact-gate owner；acceptance: `review-gate://RFG-051/strict-json-finite-confidence-test`。 |
| RFG-REV-10-P1-01 | P1 | Refuted | Source refs: 第五轮 Skill/route 复审 `BSR-4A2CC9007299E3AF` 指出 Skill 的 verifier decision discard 分支不可执行。 | Counterevidence: 同一 Skill 明确提供新 review run 作为保留旧 verifier evidence 的安全恢复路径；CLI 与 `test_gate_refuses_to_overwrite_saved_verifier_decisions` 故意拒绝原 run 重写。因此“无可执行安全恢复路径”的 bad outcome 不成立，独立 verifier refuted。Owner: Bootstrap gate recovery owner；acceptance: `review-gate://RFG-043/verifier-decision-preservation-test`。 |
| RFG-REV-10-P1-02 | P1 | Closed | Source refs: 第五轮 Skill/route 复审 `BSR-D092A28E0D170F4F`，pre-fix prepare 仅把 `requiredContextClasses` 名称写入 manifest，未绑定 artifact。触发为 `bootstrap-skill-route --scope AGENTS.md`，结果为三层可完成单文件 manifest 并 clean，缺失 Skill/operator/CLI/schema/tests/usage authority。 | `prepare` 新增每类必填 `--context-class class=scope`，生成 hash-bound `contextClassArtifacts`；缺失/未知/零匹配在写文件前失败，load_run/prompt/Skill/operator/测试同步。Owner: Bootstrap scope/context owner；acceptance: `review-gate://RFG-053/context-class-artifact-binding-test`。 |
| RFG-REV-11-P1-01 | P1 | Closed | Source refs: 首个 context-bound Skill/route 复审 `BSR-C58577C553B8B272`，pre-fix context class 只校验非空和 in-scope。触发为把 AGENTS.md 同时映射为 Skill/schema/tests/usage 等全部 class，结果为语法完整但 authority 缺失的 manifest 可 clean。 | `bootstrap-skill-route` 新增确定性 artifact semantics：稳定文件名/路径形态、profile+openai 双配置、schema/test/usage/repository rules 分类；spoofed all-class mapping 回归 fail closed。Owner: Bootstrap skill-route context owner；acceptance: `review-gate://RFG-054/skill-route-context-semantics-test`。 |
| RFG-REV-11-P2-01 | P2 | Closed | Source refs: 首个 context-bound Skill/route 复审 `BSR-A2988596569500F7`，pre-fix finalized clean/advisory run 的 verifier decisions 为空，重复 gate 会覆盖 final result 为中间状态。 | `command_gate` 在任何写入前检测 `review-result.v1` 并拒绝重开；增加 final result bytes unchanged 回归。Owner: Bootstrap lifecycle owner；acceptance: `review-gate://RFG-055/finalized-run-immutability-test`。 |
| RFG-REV-12-P1-01 | P1 | Closed | Source refs: 快速 Skill/route review gateway candidate `BSR-70B6B8F91F070A00` 指出 pre-fix `command_finalize()` 未检查现有最终 `review-result.v1`。触发为首次 finalize 后修改 `verifier-output.json` 并再次 finalize，结果为终态 `review-gate-result.json` 与处置 sidecar 可被覆盖；`command_gate()` 的终态防护不能约束直接 finalize。该 candidate 未进入独立 verifier，按用户授权先做保守修复。 | `command_finalize()` 现在于任何 sidecar 写入前拒绝已 finalized run；新增 blocker run 修改 verifier 后重复 finalize 的字节级不可变回归，并把 Skill/operator/RFG-055 同步为 gate/finalize 均不可重开。Owner: Bootstrap lifecycle owner；acceptance: `review-gate://RFG-055/finalized-run-immutability-test`。 |
| RFG-REV-13-P1-01 | P1 | Closed | Source refs: `review-gateway-bootstrap-skill-route-fast-20260714-002501` 的 Acceptance Auditor 输出声明 `status=completed` 且 `readArtifacts` 覆盖 31/31，但模板中的 31 项 `missingArtifacts` 未清空，导致 gate 保持 incomplete；原 prompt 只有自然语言移动要求，没有 reviewer 退出前的确定性自校验。 | CLI 新增不写 sidecar 的 `validate-layer`，生成 prompt 与 Skill 强制 reviewer 保存后自行执行；completed coverage 矛盾回归必须非零，合法输出零退出。Owner: Bootstrap reviewer orchestration owner；acceptance: `review-gate://RFG-060/reviewer-output-self-validation-test`。 |
| RFG-REV-14-P2-01 | P2 | Closed | Source refs: 最终 Skill/Route Review `BSR-035E95627389230A`；pre-fix `candidate_reason()` 对 `existingGuardAnalysis` 只校验非空。触发为 P2 candidate 使用 `N/A` 且其余字段合法，结果为缺少第三联防护缺口证明的 candidate 可成为用户可见 advisory。 | 复用 failure tuple 的大小写/空白/标点归一化词表，`existingGuardAnalysis` 占位文本现在以 `missing_guard_analysis` 拒绝；generated prompt、Skill、02/04/06/09 同步，新增 targeted P2 regression。Owner: Bootstrap fact-gate owner；acceptance: `review-gate://RFG-003/proof-triplet-tests` 与 `review-gate://RFG-007/gateway-validation-tests`。 |
| RFG-REV-15-P1-01 | P1 | Closed | Source refs: VDD Skill/route Round 1 `BSR-1536050B1AF89790`；pre-fix `tools/run_bootstrap_review.py:1577-1584` 的 fingerprint 只有 route、artifact、line、evidence hash 与 authority revision。触发为两个 reviewer 引用同一证据行但给出不同 trigger/state/outcome 或 dimension，结果为一个真实失败被 duplicate rejection 吞并；04 已要求 failure tuple/finding family，但实现和 severity-safe 测试未强制。 | fingerprint 现加入经大小写、空白、标点归一化的三段 failure tuple 与 dimension；只有完整 identity 相同才合并并保留最高 severity/source reviewers，不同失败链保持独立。新增 tuple、dimension 与 true-duplicate 回归。Owner: Bootstrap dedup owner；acceptance: `review-gate://RFG-008/dedup-tests` 与 `review-gate://RFG-044/severity-safe-evidence-root-dedup-test`。 |
| RFG-REV-15-P1-02 | P1 | Closed | Source refs: VDD Skill/route Round 1 `BSR-D2A9146C10CCFDED`；pre-fix `tools/run_bootstrap_review.py:1289-1355` 只要求 acquire PID 为正整数，release 可省略 PID，gate 只消费 completed operation/role。触发为 dead PID 或无 owner PID 的 release，结果为未运行真实 reviewer 也能制造 completed lease；既有 stale 扫描只在后续非 release 操作发生。 | acquire 现要求 PID 当前存活并用只读 OS API捕获创建 identity；lease schema 强制 identity；release 强制原 PID，live 时重验 identity，dead-at-acquire、缺/错 PID 与 identity 漂移均 fail closed，同时保留已正常退出 child 由原 PID 收口。Owner: Bootstrap process-lease owner；acceptance: `review-gate://RFG-065/review-cost-and-process-lease-test`。 |
| RFG-REV-16-P2-01 | P2 | Closed | Source refs: VDD Skill/route Round 2 `BSR-47CBD1FBD59FCEC3`；pre-fix `command_validate_layer()` 接受 schema-valid pending template 并返回零。触发为 reviewer 尚未读取任何 artifact 就运行自校验，结果为 operator 把未完成层当完成信号；gate 虽然后续仍 incomplete，但逐层退出闸门失真。 | `validate-layer` 现显式要求 `status=completed`；pending 反例非零且不写 gate sidecar，06/09 同步。Owner: Bootstrap reviewer orchestration owner；acceptance: `review-gate://RFG-060/reviewer-output-self-validation-test`。 |
| RFG-REV-16-P2-02 | P2 | Closed | Source refs: VDD Skill/route Round 2 `BSR-98829F5D8D6C9A49`；pre-fix VDD `validate_result_fixture()` 在 JSON array/null 成功解析后直接执行 object-only membership/`.get`。触发为 evaluator 提供语法合法的非 object fixture，结果为异常中断且没有 `vdd.skill-validation.v1` 结构化 finding。 | validator 现对非 object 统一返回 `VDD-RESULT-PARSE`；null/array mutation tests 证明结构化 fail-closed。Owner: VDD Skill contract validator owner；acceptance: `.agents/skills/vdd-execution-plan/scripts/tests/test_validate_skill_contract.py::test_non_object_result_fixture_returns_structured_parse_finding`。 |

允许空表。`Closed` 必须包含修复 owner 和验收引用；`Refuted` 必须包含反证；`Open` P0–P2 阻止 plan-ready PASS。

## 6. Review Result Contract

最终报告必须说明：scope、authority set、完整读取状态、机械检查结果、finding 数量、Open ledger 数量、跳过项和 residual risk。PASS 只表示计划可实施，不表示任何运行时代码完成。

## 7. Round 1 Review Result（2026-07-12）

- Scope：本目录 13 个 Markdown、`schemas/**` 4 个 JSON、plan-local validator，以及 `AGENTS.md` 中相关规则。
- Authority set：用户批准要求、ECC pinned-source 研究、`AGENTS.md`；两个既有重构目录仅用于依赖和不重复检查。
- Complete-read：PASS；全部目标文件已完整读取。
- Mechanical checks：PASS；本地链接、JSON 解析、Draft 2020-12 声明、fixture 实例、RFG owner/phase/coverage 和 semantic closure checks 均通过。
- Findings：P0 `0`，P1 `11`（全部 Closed），P2 `0`，Open `0`。
- Verification：plan-local deterministic validator 对 schema/fixture、状态组合、confidence、rejection suppression、phase gate 和 ledger closure 做独立复核。
- Skipped：未运行外部完整 JSON Schema metaschema validator；本地 validator 覆盖本目录实际使用的关键字子集，R1 必须使用长期 owner 选定的生产级 Draft 2020-12 validator 再验证。
- Residual risk：两个上游重构尚未提供本计划所需 handoff evidence，因此 R1–R6 不得启动。
- Result：PASS / Plan-ready。该结论不表示代码、gateway、BMAD/GDS override 或前台 Codex 集成已经完成。

## 8. Round 2 Review Result（2026-07-12）

- Change scope：将 Blind Hunter、Edge Case Hunter、Acceptance Auditor 纳入 handoff 后的新 review route，同时保持当前 7 月 7 日 in-flight review 和历史 finding 不变。
- Complete-read：PASS；重新读取全部变更分册、97/98/99、四份 schema、fixtures 和 validator，并核对当前 BMAD/GDS 三层 reviewer 调用约定。
- Mechanical checks：PASS；链接、JSON、fixture、RFG-001 至 RFG-028 owner/phase/coverage 和 semantic checks 均通过。
- Findings：P0 `0`，P1 `4`（RFG-REV-2-P1-01 至 04，全部 Closed），P2 `0`，Open `0`。
- Verification：plan-local validator 确认 `sourceReviewers[]`、`skippedLayers[]`、`routeVersion`、三角色枚举和新增 RFG 覆盖；合法/非法 result fixtures 均符合预期。
- Isolation result：当前 7 月 7 日 route 不改、不重跑、不重分类；R3 仅在上游 handoff 后对新 review run 启用三个 candidate adapter。
- Result：PASS / Plan-ready。该结论仍不表示运行时代码或 route 切换已经完成。

## 9. Round 3 Review Result（2026-07-12）

- Scope：完整读取本目录 13 个 Markdown、`schemas/**` 4 个 JSON、plan-local validator，并核对 AGENTS/README/standards-index 同步权威。
- Mechanical checks：PASS；Markdown links、JSON、schema/fixture、gateway semantic fixtures、96 ledger、97 owner/phase/acceptance、98 source mapping、99 owner/phase coverage 全部通过。
- Findings：P0 `0`，P1 `8`（RFG-REV-3-P1-01 至 08，全部 Closed），P2 `0`，Open `0`。
- Counterexample closure：all-reviewers-skipped clean、candidate missing routeVersion、reversed line range、P1 advisory、P2 unverified、blank owner/acceptance 与 missing source mapping 均被新 validator 拒绝。
- Documentation timing：本轮不修改 AGENTS/README；R1/R2/R3/R4/R6 的同批同步点已冻结，当前 7 月 7 日 in-flight review 不受影响。
- Skipped：未运行外部完整 JSON Schema metaschema validator；R1 必须使用长期 owner 选定的生产级 Draft 2020-12 validator 再验证。
- Result：PASS / Plan-ready。该结论只表示计划可以实施，不表示代码、gateway、adapter、route 切换或前台能力完成。

## 10. Round 4 Review Result（2026-07-12）

- Scope：完整读取本目录 13 个 Markdown、`schemas/**` 4 个 JSON、plan-local validator，并按 ECC 四问与 P0–P2 三联证明复核。
- Mechanical checks：PASS；Markdown links、JSON 解析、schema/composite 分阶段 fixture、96 ledger、97 owner/phase/acceptance、98 source mapping、99 owner/phase coverage 全部通过。
- Findings：P0 `0`，P1 `4`（RFG-REV-4-P1-01 至 04，全部 Closed），P2 `0`，Open `0`。
- Counterexample closure：schema-valid/gateway-invalid fixture 被显式区分；producer-narrowed requiredLayers 和 trusted-profile substitution 被拒绝；security/data-loss 不能 manual-pause，manual-pause 不能混入 blocked；missing-consumer fixture 只因目标约束失败。
- Requirement closure：新增 RFG-029 至 RFG-032，均具有唯一 owner、phase、acceptance ref，并在 98/99 恰好覆盖一次。
- Documentation timing：仍不提前修改 AGENTS/README；按 R1/R2/R3/R4/R6 的能力 operational 同批同步合同执行。
- Skipped：未运行外部完整 JSON Schema metaschema validator；R1 仍须使用长期 owner 选定的生产级 Draft 2020-12 validator 复核。
- Result：PASS / Plan-ready。该结论只表示计划可以实施，不表示代码、gateway、adapter、route 切换或前台能力完成。

## 11. R0B Bootstrap 实施验证结果（2026-07-12）

- Scope：仅验证本目录 Bootstrap CLI、reviewer/verifier Schema、profile registry、operator guide、回归测试及 Whole-directory validator；未对 7-07/7-11 执行 candidate discovery 或 reviewer。
- Mechanical checks：PASS；17 个 Bootstrap 回归测试通过，Whole-directory plan validator 通过。
- Contract closure：pending template 可被 Schema 接受但不能冒充 completed；Windows reviewer/verifier template 显式授予当前用户 Modify 且授权失败时 fail closed；binary artifact 可 hash-bound 但不能作为行证据；candidate context 与 verifier evidence 必须位于 prepared scope；policy revision 绑定 canonical profile；Bootstrap sidecar 标识 `supplemental_bootstrap`；finalize 会从原始 reviewer 输出重算 gate 产物且可幂等重跑。
- Smoke：临时 Git 仓完成 `prepare → 三层合法空输出 → gate → finalize`，结果 clean，目标 scope SHA-256 前后相同；该 smoke 未使用真实上游目录。
- Reviewer execution：按用户要求跳过 Blind Hunter、Edge Case Hunter、Acceptance Auditor 和独立 verifier；零条 7-07/7-11 finding 被生成或代写。
- Result：PASS / R0B Bootstrap-ready。该结论只表示用户现在可以按 09 手工审查 7-07/7-11；不表示 R0C 手工审查、R0D handoff 或 R1–R6 已完成。

## 12. Round 6 Skill/Route Review 与修复结果（2026-07-13）

- Review run：`logs/ci/2026-07-13/review-gateway-bootstrap-skill-route-postfix-20260713-175433/`；profile 为 `bootstrap-skill-route`，32/32 artifacts 完整读取，禁止 sampling。
- Reviewer execution：Blind Hunter 使用经探针验证的 fallback `gpt-5.5/medium`；Edge Case Hunter 与 Acceptance Auditor 使用 `gpt-5.6-terra/high`；独立 verifier 使用新的 `gpt-5.6-terra/high` 进程。
- Findings：P0 `0`，P1 `2`，P2 `0`；`BSR-17E836AA4258FA55` 与 `BSR-B980F079DB28A2F9` 均经独立 verifier confirmed，并以 `RFG-REV-6-P1-01`、`RFG-REV-6-P1-02` Closed 进入历史 ledger，Open `0`。
- Closure：统一 manifest route identity；candidate/rejection/gate/disposition/metrics/final result/report 全部绑定 route/profile/revision/authority/input；新增 gate-only `bootstrap-review-gate-result.v1` Schema，明确 `awaiting_verification` 不属于最终 `review-result.v1` 状态。
- Mechanical checks：PASS；26 个 Bootstrap 回归测试、Whole-directory validator、Skill quick validation 全部通过。
- Result：修复已达到重新审查条件；本结论只证明本轮两个 confirmed P1 已关闭，不替代修复后新快照的独立复审，也不表示 7-07/7-11 代码完成。

## 13. Round 7 修复后 Skill/Route 复审与修复结果（2026-07-13）

- Review run：`logs/ci/2026-07-13/review-gateway-bootstrap-skill-route-postfix2-20260713-183651/`；profile 为 `bootstrap-skill-route`，35/35 artifacts 完整读取，禁止 sampling。
- Reviewer execution：Blind Hunter 使用 `gpt-5.5/medium`；Edge Case Hunter 使用 `gpt-5.6-terra/high`；Acceptance Auditor 的首选进程未写回并保持 pending，按 fail-closed 记录后由通过 workspace-write 探针的 `gpt-5.5/high` 新进程完成；独立 verifier 使用新的 `gpt-5.6-terra/high` 进程。
- Findings：P0 `0`，P1 `1`，P2 `0`；`BSR-228E1FECD473CC01` 经独立 verifier confirmed，并以 `RFG-REV-7-P1-01` Closed 进入历史 ledger，Open `0`。
- Closure：failure tuple 新增占位文本归一化拒绝，非空 `TBD`/`TODO`/`N/A` 等不能再绕过事实门禁；新增 RFG-048 与 deterministic rejection 回归。
- Mechanical checks：PASS；27 个 Bootstrap 回归测试、Whole-directory validator、Skill quick validation 全部通过。
- Result：本轮 confirmed P1 已关闭并达到再次新快照复审条件；不表示 7-07/7-11 代码完成。

## 14. Round 8 第三轮 Skill/Route 复审与修复结果（2026-07-13）

- Review run：`logs/ci/2026-07-13/review-gateway-bootstrap-skill-route-postfix3-20260713-190302/`；profile 为 `bootstrap-skill-route`，40/40 artifacts 完整读取，禁止 sampling。
- Gate：3 个 raw candidates 中 2 个通过，1 个因 `stale_evidence` 被拒绝；accepted 为 P1 `1`、P2 `1`，rejection 不是 finding。
- Findings：P1 `BSR-461C76DC1E9C0E73` 经独立 verifier confirmed；P2 `BSR-0DF285E493C6BA06` 具备完整三联证明；二者分别以 `RFG-REV-8-P1-01`、`RFG-REV-8-P2-01` Closed 进入 ledger，Open `0`。
- Closure：completed coverage 改为顺序无关集合；verifier evidence 必须覆盖 finding 精确证据和全部 contextRead，无关 in-scope 引用 fail closed。
- Mechanical checks：PASS；29 个 Bootstrap 回归测试、Whole-directory validator、Skill quick validation 全部通过。
- Result：本轮 P1/P2 已关闭并达到新快照完整复审条件；不表示 7-07/7-11 代码完成。

## 15. Round 9 第四轮 Skill/Route 复审与修复结果（2026-07-13）

- Review run：`logs/ci/2026-07-13/review-gateway-bootstrap-skill-route-postfix4-20260713-192955/`；profile 为 `bootstrap-skill-route`，44/44 artifacts 完整读取，禁止 sampling。
- Findings：P0 `0`，P1 `2`，P2 `0`；`BSR-9BAAC153EC8B1893` 与 `BSR-DE4363AC33AA4D9F` 均经独立 verifier confirmed，并以 `RFG-REV-9-P1-01`、`RFG-REV-9-P1-02` Closed 进入 ledger，Open `0`。
- Closure：path-only context 只能由整文件 verifier evidence 覆盖；CLI/validator 严格拒绝 JSON 非有限数，confidence 额外要求 `math.isfinite`，hash/write 同样禁止 NaN。
- Mechanical checks：PASS；31 个 Bootstrap 回归测试、Whole-directory validator、Skill quick validation 全部通过。
- Result：本轮两个 confirmed P1 已关闭并达到新快照完整复审条件；不表示 7-07/7-11 代码完成。

## 16. Round 10 第五轮 Skill/Route 复审与修复结果（2026-07-13）

- Review run：`logs/ci/2026-07-13/review-gateway-bootstrap-skill-route-final-20260713-195601/`；profile 为 `bootstrap-skill-route`，47/47 artifacts 完整读取，禁止 sampling。
- Findings：gate 接受 P1 `2`；独立 verifier 将 `BSR-4A2CC9007299E3AF` refuted、`BSR-D092A28E0D170F4F` confirmed。历史 ledger 记录一条 Refuted 与一条 Closed，Open `0`。
- Closure：prepare 强制把每个 required context class 映射到非空 in-scope hash-bound artifacts，manifest/prompt/recovery 全部绑定；无映射的单文件 skill-route prepare 在写文件前失败。
- Mechanical checks：PASS；32 个 Bootstrap 回归测试、Whole-directory validator、Skill quick validation 全部通过。
- Result：confirmed P1 已关闭；refuted 候选不作为 finding。达到新快照完整复审条件，不表示 7-07/7-11 代码完成。

## 17. Round 11 Context-bound Skill/Route 复审与修复结果（2026-07-13）

- Review run：`logs/ci/2026-07-13/review-gateway-bootstrap-skill-route-clean-20260713-202629/`；profile 为 `bootstrap-skill-route`，49/49 artifacts 与 8/8 context class bindings 完整读取，禁止 sampling。
- Findings：P1 `BSR-C58577C553B8B272` 经独立 verifier confirmed；P2 `BSR-A2988596569500F7` 通过事实门禁；二者均 Closed，Open `0`。
- Closure：Skill-route context classes 增加稳定 artifact semantics，拒绝同一无关文件冒名；finalized `review-result.v1` run 不得再次 gate 覆盖。
- Mechanical checks：PASS；34 个 Bootstrap 回归测试、Whole-directory validator、Skill quick validation 全部通过。
- Result：本轮 P1/P2 已关闭并达到新快照完整复审条件；不表示 7-07/7-11 代码完成。


## 18. ECC 能力对齐与 Review 成本止损实施验证（2026-07-13）

- Change scope：仅更新 7-12 plan-local profile/CLI/schema/tests/operator guide 与仓库外 `run-phase-bootstrap-review` Skill；未运行 Blind Hunter、Edge Case Hunter、Acceptance Auditor 或独立 verifier，未修改 7-07/7-11、AGENTS、README、`scripts/sc` 或 Phase 共享入口。
- Contract：四类 profile 新增 hash-bound role rubric、profile 专用误报抑制、untrusted-content policy、required deterministic preflight 和默认两轮/硬上限三轮的 full-review cycle policy。
- Enforcement：`prepare` 生成 `preflight-result.json` pending 合同；`gate` 拒绝 pending/failed、check 漂移、非零退出码、越界/缺失/stale evidence；`finalize` 绑定 gate-time preflight hash。修复阶段禁止逐 finding 自动完整复审，P2-only 不触发，硬上限后 manual pause。
- Mechanical checks：PASS；37 个 Bootstrap 回归测试、Python compile、Whole-directory validator、Skill quick validation 全部通过。
- Result：RFG-056 至 RFG-059 已落地，96 finding ledger Open `0`。本节只证明新路由合同和确定性验证可实施，不是新的语义 Whole-directory review，也不表示 7-07/7-11 代码完成。

## 19. Round 12 快速 Skill/Route Review 单项修复（2026-07-14）

- Review run：`logs/ci/2026-07-14/review-gateway-bootstrap-skill-route-fast-20260714-002501/`；Blind Hunter 完成且零 candidate，Edge Case Hunter 产生 `BSR-70B6B8F91F070A00`，Acceptance Auditor 输出不满足 coverage 合同，因此本 run 保持 `incomplete`，不构成完整 Review PASS。
- Closure：按用户授权先修复 gateway accepted P1 candidate；`finalize` 与 `gate` 一致拒绝重开最终 `review-result.v1`，修改 verifier 后重复 finalize 也不得改写终态证据。
- Mechanical checks：38 个 Bootstrap 回归测试通过；其余确定性验证见本次修复证据。
- Result：该单项候选已关闭；不宣称本次三层 Review 完成，不表示 7-07/7-11 代码完成。

## 20. Reviewer Output Self-validation 修复（2026-07-14）

- Runtime evidence：Round 12 Acceptance Auditor 已读 31/31 artifacts，但增量写回时没有清空模板 `missingArtifacts`，其 output 因 coverage 分区矛盾被 gate 正确判 incomplete。
- Closure：新增只读 `validate-layer`；每个 generated reviewer prompt 与 Skill 编排在退出/gate 前执行，失败由原 reviewer 修正自己的 JSON，主会话不得代修。
- Mechanical checks：40 个 Bootstrap 回归测试通过，包括矛盾 coverage 失败且无 gate sidecar、合法 completed output 零退出。
- Result：RFG-060 已落地；本节只证明输出收口闸门可执行，不是新的完整语义 Review。

## 21. Round 14 P2 Targeted Repair（2026-07-14）

- Source review：`logs/ci/2026-07-14/review-gateway-bootstrap-skill-route-final-20260714-020015/` 最终状态 `advisory`，唯一 accepted finding 为 `BSR-035E95627389230A`。
- Closure：`existingGuardAnalysis` 使用 `N/A` 等价占位文本时稳定产生 `missing_guard_analysis` rejection；具体防护分析仍由既有正例通过。
- Validation policy：只运行 targeted Bootstrap tests、Whole-directory validator、Python compile、Skill quick validation 与 diff check；依据 reviewCyclePolicy，P2-only 修复不触发下一轮完整三层 Review。
- Result：该 P2 已关闭；最终 Review 历史证据保持不可变。

## 22. Round 2 VDD Skill/Route 最终复审与 P2 定向修复（2026-07-14）

- Review run：`logs/ci/2026-07-14/review-gateway-bootstrap-vdd-skill-route-review-r2-20260714-170649/`；同一 `changeId=vdd-execution-plan-skill-review`，以 Round 1 finalized blocked run 为 predecessor，42/42 artifacts、8/8 context classes 完整读取，sampling 禁止。
- Reviewer execution：Blind Hunter、Edge Case Hunter、Acceptance Auditor 使用三个独立 `gpt-5.6-terra` `codex exec` 进程与真实 process identity lease；medium/high terminal+workspace-write probes 均完成。Blind `0` candidate，Edge `1`、Acceptance `1`；三层 `validate-layer` 均为零退出。
- Gateway：最终 `advisory`，P0 `0`、P1 `0`、P2 `2`、rejected `0`；P2 不进入独立 verifier。`BSR-47CBD1FBD59FCEC3` 与 `BSR-98829F5D8D6C9A49` 已批量定向修复并以 RFG-REV-16-P2-01/02 Closed 进入 ledger，Open `0`。
- Closure：`validate-layer` 仅接受 completed 输出；VDD validation-result fixture 的 JSON null/array 返回稳定结构化 parse finding。依据 review-cycle policy，P2-only 修复不启动第三轮完整语义 Review。
- Result：Round 2 完整复审有效，VDD Skill/route 当前无 P0/P1；本结论是 supplemental Bootstrap evidence，不是 BH-HANDOFF，也不表示 7-07/7-11 实施完成。

## 验收标准

- Given 零合格 finding 且机械检查全部通过，When生成结果，Then允许 clean PASS。
- Given任一 Open P0–P2，When生成结果，Then不得 plan-ready PASS。
- Given只有“可更完善”的建议，When无法证明 consumer bad outcome，Then不写入 ledger。
