# 积木云 Bootstrap Review 风险路由与墙钟时间治理方案
## ——用于 VDD 更新 `2026-08-07-bootstrap-review-operability-hardening` 的上游需求输入

> 文档性质：VDD 上游需求 / 设计约束 / 验收输入
> 目标仓库：`skyoxu/ji-mu-yun`
> 仓库核对基线：`main@67e8fba68e2b5ce18036c05226cfa0519890b4ff`
> 核对提交：`Harden bootstrap review operability plan and control plane`
> 唯一目标目录：`execution-plans/2026-08-07-bootstrap-review-operability-hardening/`
> 本文不是实现授权、不是 Bootstrap Review 结果、不是 Acceptance 结果，也不授权 commit / release / archive。

---

## 0. 给 VDD / Quick Dev / Acceptance 的执行摘要

本文件的唯一用途是让 `$vdd-execution-plan` **更新既有需求目录**：

`execution-plans/2026-08-07-bootstrap-review-operability-hardening/`

不得创建第二个平行 execution-plan 目录来承载本次需求。

本次工作采用以下明确交付顺序：

```text
本 Markdown
  ↓
VDD：更新现有 2026-08-07-bootstrap-review-operability-hardening
  ↓
plan-ready + 当前计划验证通过
  ↓
维护者显式发布 implementation-authorized
  ↓
【本次明确跳过实施前 Bootstrap upstream-plan review】
  ↓
Quick Dev strict_tdd_plan
  ↓
确定性 implementation terminal predicate
  ↓
implementation-complete
  ↓
新的 Refactor Acceptance
  ↓
Acceptance 自己确定 semantic review requirement
  ├─ not_required → deterministic_only → Acceptance 完成
  └─ required     → Bootstrap semantic assurance
                      ├─ 首次：full discovery
                      ├─ 修复后无升级：focused verifier
                      ├─ P2：当前 run 内确定性 closure
                      └─ 后续 full discovery：仅 typed trigger + 用户确认
  ↓
acceptance-passed
```

### 0.1 本次实施前 Review 的明确决定

本次计划更新完成后：

- **不要创建 `bootstrap-upstream-plan` run。**
- **不要为了进入 Quick Dev 人工伪造 clean review、finding、predecessor run、review envelope 或 lineage evidence。**
- VDD 的 `plan-ready` 本身仍然**不等于** `implementation-authorized`。
- 由维护者针对本目标计划显式发布 `implementation-authorized` 后，Quick Dev 才能进入。
- 如果 VDD 在更新过程中发现一个现行 Accepted ADR / protected-path rule **明确要求**实施前独立审查，则必须按仓库权威 fail closed 并报告冲突；不得让本文覆盖更高权威。
- 除上述“更高权威硬要求”外，本次用户指令就是：**跳过实施前 Bootstrap Review。**

### 0.2 实施后 Review 的明确决定

本次目标会修改 Bootstrap Review / Acceptance 的工作流控制行为，因此在新规则实现后，本目标自身的实施后 Acceptance 应判定为：

```text
requirement = required
reason includes workflow_control_plane_changed
```

并进入一次完整的实施后语义 assurance。

也就是说：

> 本次不是“取消 Review”，而是把高成本语义 Review 从“实施前 + 实施后固定门禁”调整为“实施后按风险触发的 assurance”。

---

# 1. 当前仓库事实基线

以下内容是本文生成前按 `main@67e8fba68e2b5ce18036c05226cfa0519890b4ff` 重新核对的事实。VDD 更新时必须再次读取当前字节；若 main 已继续演进，以更新时的当前权威为准，本文中的 SHA 只作为本次设计输入基线。

## 1.1 根仓责任边界

当前根仓：

- 是 Ji Mu Yun Phase A/B cloud prototype platform。
- `AGENTS.md` 是仓库路由与不可协商 change contract。
- `README.md` 是产品、阶段、技术栈与入口说明。
- Toolchain workflow 与 Phase browser/API 是不同责任面。
- 当前仓库由一个可信维护者 + AI 助手维护。
- 改 workflow control、contract、security/release threshold 时必须检查 Accepted ADR 是否需要新增、修改或 supersede。
- 代码、测试、脚本与机器输出保持英文；中文用户文档按 UTF-8 处理。
- 失败证据应保留，不通过修改历史证据“做绿”。

本计划属于 **repository toolchain control plane**，不是 Phase API / Hosted workspace / live runtime 需求。

## 1.2 目标计划现状

现有目录：

`execution-plans/2026-08-07-bootstrap-review-operability-hardening/`

当前为：

```text
profile = self-hosted
state   = plan-ready
state owner = vdd-execution-plan
```

当前 `plan-state.v1.json` 中：

- `BROH-S0` pending
- `BROH-S1` pending
- `BROH-S2` pending
- `BROH-S3` pending
- `blocking_conditions = []`
- 只授权 `plan-ready`
- 明确不授权：
  - `implementation-authorized`
  - `implementation-complete`
  - `acceptance-passed`
  - commit
  - release
  - archived

当前 `resume-state.v1.json` 已写明：

> `Enter BROH-S0 after explicit implementation authorization.`

因此本次“跳过实施前 Review”与现有 plan lifecycle 并不冲突。

## 1.3 目标计划当前已有需求

现有 `requirements.v1.json` 包含：

- `BROH-001`：non-authorizing dry-run / closure binding preview
- `BROH-002`：missing context / planned-new file diagnostics
- `BROH-003`：frozen / repair window diagnostics
- `BROH-004`：transport / stale attempt recovery / Windows-safe transport / heartbeat
- `BROH-005`：保留 authority / lineage / Artifact View / verifier / lifecycle / envelope predicates
- `BROH-006`：reviewer read-only repository access + attempt-only writable root
- `BROH-007`：exactEvidence from frozen bytes + malformed/stale retry stop-loss

已有 acceptance：`BROH-A01` ~ `BROH-A12`。

本次要求不是替换这七条，而是在它们上面增加：

1. Review 触发频率治理；
2. Acceptance-owned risk decision；
3. Bootstrap discovery wave 并发；
4. 明确 Quick Dev 与 post-implementation semantic assurance 的边界；
5. 为本目标补齐真正的 implementation terminal predicate。

## 1.4 现有实现 contract 的关键限制

当前 `implementation-contract.v1.json` 只有四个 slice：`BROH-S0` ~ `BROH-S3`。

其 write set 主要局限在：

- `.agents/skills/run-phase-bootstrap-review/**`
- `docs/standards/bootstrap-review-control-plane.md`

但本次需求要让 Acceptance 自己决定是否需要 Review，因此**现有 write set 不足**。

VDD 必须显式扩展到 Acceptance consumer，而不是让 Quick Dev 越权修改 contract 外文件。

## 1.5 当前 plan validator 的硬编码事实

当前 `execution-plans/2026-08-07-bootstrap-review-operability-hardening/tools/validate_plan.py` 硬编码：

- 只允许 `BROH-001..BROH-007`
- 只允许 4 个 slice
- 只允许当前 9 个 operability fixture case
- 只允许当前 command set

所以 VDD 更新此需求时必须同步更新：

- `requirements.v1.json`
- `implementation-contract.v1.json`
- `plan-state.v1.json`
- `resume-state.v1.json`
- `command-registry.v1.json`
- `fixtures/operability-cases.v1.json` 或新增等价 fixture registry
- `tools/validate_plan.py`
- `tools/tests/**`

只改 `00-index.md` 不算完成。

## 1.6 当前计划缺少实现终验器

当前 target `tools/` 下只有 `validate_plan.py` 与 `tests/`，没有：

`validate_implementation.py`

这是本次应修复的重要结构缺口。

当前 `00-index.md` 说“实施完成还要 Skill tests、whole-directory validator、terminal full replay”，但当前 `implementation-contract.v1.json` 的 `terminal_validation` 仍只是 plan validator。

本次必须分开：

```text
validate_plan.py
    = plan-ready predicate

validate_implementation.py
    = implementation-complete predicate

Refactor Acceptance
    = acceptance-passed owner
```

三者不得互相替代。

---

# 2. 当前四个控制面的真实边界

## 2.1 VDD：实施前 Bootstrap 已经是可选项

当前 `.agents/skills/vdd-execution-plan/SKILL.md` 已明确：

- 生命周期：`draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`
- VDD 只拥有 `draft` / `plan-ready`。
- 维护者可以在没有 Bootstrap evidence 的情况下显式发布 `implementation-authorized`。
- Bootstrap Review 是 optional supplemental evidence。
- Review 默认可选，除非 maintainer 显式请求或更高权威 protected-path rule 明确要求。
- P2-only 不应自动开启新的 full semantic review。
- self-hosted 需要 deterministic protocol fixtures + migration checks + terminal replay。

因此，不要为了本次需求再发明一套“VDD risk classifier”。

## 2.2 Quick Dev：不能也不应该启动 Bootstrap

当前 `.agents/skills/quick-dev-tdd-adapter/SKILL.md` 已明确：

- 只接受显式 target plan + schema-valid `implementation-contract.v1.json`。
- 进入前由 parent router 确认 `strict_tdd_plan`。
- 按 `RED -> GREEN -> REFACTOR -> slice predicate`。
- 可以消费已经发布的 `implementation-authorized`。
- **Quick Dev 不启动 Bootstrap Review。**
- **Quick Dev 不改变 review evidence。**
- Quick Dev 最多发布 `implementation-complete`。
- Acceptance 外置。
- Frozen VDD knowledge context 不重新扩展。

本次必须保持此边界。

## 2.3 Bootstrap：当前 round policy 已经基本正确

当前 Bootstrap 已经拥有这些正确规则：

- Full discovery 有三个隔离角色：`blind_hunter`、`edge_case_hunter`、`acceptance_auditor`。
- 三者不能共享候选 finding。
- P0/P1 需要独立 verifier。
- Round 1 是唯一自动 finding discovery round。
- Round 1 后普通修复默认使用一个 `focused_repair_verifier`。
- focused verifier 只验证 predecessor finding，不创造新 finding，不重开 discovery。
- 后续 complete discovery 必须由 typed Acceptance trigger 触发：`novel_p0_p1`、`authority_context_graph_changed`、`high_risk_boundary_changed`。
- Round 1 之后 complete discovery 还必须有 recommendation、confidence、explicit user confirmation、hash-bound Bootstrap authorization。
- P2-only 不开启新 full semantic round。
- 默认 full round budget = 2；hard full round limit = 3。
- Round 3 后 unresolved blocker -> `manual_pause`。
- successor 不重置 lineage budget。
- transport failure 不消耗 semantic round。
- process events 是执行事实，lease 是派生视图。
- non-overlapping role write sets 已允许并发。

所以本次不要重写 Bootstrap review semantics。

要改的是：**什么时候调用 Bootstrap** + **一次 full discovery 如何以 owner-owned wave 并发执行**。

## 2.4 Acceptance：当前最大缺口是 review requirement 仍由调用者给出

当前 Acceptance 已支持：

```text
deterministic_only
focused_repair_verification
full_implementation_conformance
manual_pause
```

并且 `bootstrap_integration.py` 已支持：

```text
requirement = not_required
→ deterministic_only
→ 不带 review lineage evidence
```

但是当前 `acceptance_cli.py` 中的 `decide-bootstrap` 本质上只是：

1. 读取 caller 提供的 JSON；
2. 检查 `requirement` 是 `required` 或 `not_required`；
3. 检查 `requirementSources` 非空；
4. 检查 `authorizes=[]`；
5. 原样发布。

也就是说：

> 当前 Acceptance 拥有“路由机制”，但尚未真正拥有“review 是否必要”的确定性决策逻辑。

这是本次最核心的控制面修复。

---

# 3. 问题定义与目标

当前主要墙钟时间浪费不是写需求、VDD、Quick Dev 或 deterministic validation，而是将高成本 semantic review 当成所有 plan 的固定生命周期门禁。

本次目标是：

> 保留 Review 深度，显著降低 Review 频率；保留三个独立角色，显著缩短一次 Review 的墙钟时间。

核心长期关系：

```text
Acceptance = 必须
Bootstrap semantic assurance = 条件触发
```

调用方不能通过手写 `required/not_required` 决定自己是否被 Review；Acceptance 必须从绑定事实推导。

历史 review 的 token、wall time、finding yield、calibration 只能解释成本，不能因为“过去很少发现问题”而把当前 security / authority / protected-path 变更降级。

---
# 4. 新增需求 BROH-008 ~ BROH-020

VDD 应保留现有 `BROH-001..BROH-007`，并新增以下需求。若因现有 schema / naming convention 必须调整机械编号，可以调整编号，但不得改变语义、owner 与 acceptance mapping。

## BROH-008 — Acceptance-owned Review Requirement Decision

Refactor Acceptance 必须从当前 target、candidate custody、changed paths、deterministic acceptance evidence、repository rules、knowledge bindings、protected/high-risk facts 和显式 maintainer intent 中，**确定性地产生** semantic review requirement decision。

调用方不得直接拥有 `required/not_required` 的最终选择权。

决策结果至少包含：

```text
schemaVersion
target
candidate binding
requirement = required | not_required
reasonCodes[]
reviewProfile / null
requirementSources[]
deterministicEvidenceRefs[]
decisionHash
authorizes = []
```

Acceptance criteria：

- 相同输入字节重复执行得到相同语义结果。
- 任一绑定 hash 漂移后旧 decision 不可继续使用。
- caller 手写 `not_required` 不可绕过硬触发条件。
- caller 手写 `required` 也不应成为唯一 authority source。
- decision 不授权 Bootstrap launch、acceptance、commit、release。

## BROH-009 — Closed Review Trigger Policy

建立一个闭集、高风险优先的 review trigger policy。

以下类别必须 `required`：

1. `workflow_control_plane_changed`
2. `lifecycle_authority_changed`
3. `protected_path_changed`
4. `security_or_permission_boundary_changed`
5. `shared_execution_entrypoint_changed`
6. `public_api_contract_changed`
7. `database_schema_or_migration_changed`
8. `runtime_or_deployment_boundary_changed`
9. `destructive_or_irreversible_change`
10. `deterministic_evidence_incomplete`
11. `unresolved_acceptance_blocker`
12. `explicit_maintainer_review_request`

VDD 可以依据当前仓库 schema 选择更合适的稳定 code spelling，但必须是 closed enum，不接受 free-form reason 作为 authority。

Precedence：

```text
任何 hard trigger = required
显式 maintainer request = 只允许升级为 required
未知/矛盾风险事实 = fail closed，不得默认为 not_required
只有所有 not_required 条件成立 = not_required
```

`not_required` 必须同时满足：

- 无任何 hard trigger；
- candidate manifest / custody 完整且 current；
- required deterministic acceptance actions 全部通过；
- implementation terminal predicate current pass；
- 无 unresolved P0/P1；
- 无 manual_pause；
- knowledge / source binding current；
- 无显式 maintainer review request；
- 当前 repository authority 未要求 review。

## BROH-010 — 实施前 Review Optionality Regression

保持 VDD 现有规则：

```text
plan-ready
→ explicit maintainer implementation authorization
→ Quick Dev
```

可以在**没有 Bootstrap upstream review** 的情况下合法进入实施。

对本目标，本次 VDD update 后：

```text
upstream Bootstrap review = skipped by explicit maintainer instruction
```

不得产生假 review evidence。

必须有 detached fixture / composition test 证明：

- `plan-ready` alone 不能启动 Quick Dev；
- target-bound explicit maintainer authorization 可以；
- absence of Bootstrap evidence 本身不是 Quick Dev blocker；
- protected hard rule 若存在仍优先；
- Bootstrap clean 也不能代替 maintainer authorization。

## BROH-011 — Deterministic-only Acceptance Happy Path

当 BROH-009 的全部 `not_required` 条件成立时：

```text
Acceptance
→ requirement=not_required
→ routeKind=deterministic_only
→ no Bootstrap run
→ finalize acceptance from current deterministic evidence
```

约束：

- 不创建 lineage family。
- 不附加伪造的 zero-round review envelope。
- 不创建 access proof / launch authorization。
- 不启动模型。
- Acceptance 仍需完成自己的 deterministic inventory / matrix / checklist / evidence / finalization。
- `acceptance-passed` 仍只由 Acceptance 发布。

普通低风险 plan 的 happy path semantic model executions 应允许为 `0`。

## BROH-012 — High-risk Post-Implementation Assurance

对于 BROH-009 的 hard-trigger 变更，Acceptance 必须要求实施后 semantic assurance。

本目标修改 Bootstrap workflow control plane、Acceptance review routing 与 review requirement authority，所以本目标完成 Quick Dev 后，新的 Acceptance decision 必须至少命中：

```text
workflow_control_plane_changed
```

并选择 `required`。

Review profile 必须显式、类型化，至少支持区分：

```text
bootstrap-implementation-conformance
bootstrap-skill-route
```

本目标属于 Skill / route control-plane 变更，预期 profile：

```text
bootstrap-skill-route
```

重要兼容约束：当前 Acceptance 的 exact reuse 逻辑对 `bootstrap-implementation-conformance` 有特定绑定。不得为了支持 `bootstrap-skill-route` 简单放宽为“任何 Bootstrap profile”。若 Acceptance 消费 `bootstrap-skill-route`，应建立独立 typed、hash-bound assurance import/validation path，或者先证明合同等价后再修订。

## BROH-013 — Preserve Bounded Review Re-entry

本次优化不得破坏现有 bounded review semantics：

```text
first semantic entry
→ full discovery

P0/P1 repair + no escalation trigger
→ focused_repair_verification

P2-only
→ current-run deterministic closure

later full discovery
→ typed trigger + recommendation/confidence + explicit user confirmation

hard full review round limit
→ 3

after hard limit
→ manual_pause / existing deterministic closure mechanism
```

禁止 regression：

- repair 后默认 full discovery；
- P2-only 自动开下一轮；
- successor 重置 lineage；
- transport retry 消耗 semantic round；
- focused verifier 创建新 finding；
- Round 4。

## BROH-014 — Bootstrap-owned Concurrent Discovery Wave

在 Bootstrap repository-owned control plane 内新增一个 owner-owned discovery wave 操作。

建议公开操作名：

```text
run-discovery-wave
```

名称如因现有 CLI 约定需要调整可以调整，但 owner 和语义固定。

一次 wave：

1. 验证当前 run 是 `findingMode=discovery`；
2. 重放 launch authorization；
3. 重放所有必要 access proofs；
4. 确认 required discovery roles：`blind_hunter`、`edge_case_hunter`、`acceptance_auditor`；
5. 使用现有 role reservation / process-event / write-set 规则；
6. 为三个 role 分配独立 attempt；
7. 并发运行；
8. 每个 role 独立 handshake；
9. 每个 role 独立 structured candidate；
10. parent 独立验证并原子发布各 formal output；
11. wave 只有在所有 required discovery role 均 terminal-valid 时才可进入 gate。

并发不得变成 shared session、shared prompt memory、shared candidate list 或 reviewer 相互补 finding。角色隔离语义完全不变。

## BROH-015 — Wave Partial Failure / Retry / Round Idempotency

如果 concurrent discovery wave 中：

```text
blind_hunter = success
edge_case_hunter = transport failure
acceptance_auditor = success
```

则：

- 两个成功 formal outputs 保留；
- transport failure append-only 记录；
- 不重跑两个成功 role；
- 只允许 retry failed role；
- 不额外消费一个 semantic round；
- 不通过改 reviewId / changeId 创建“新一轮”；
- retry 后全部 role valid 才 gate。

三个 discovery role 并发启动时必须保证 `semantic-round-started` 对该 lineage round 只产生一个有效 round consumption。

如果 caller / parent 在 wave 中断，inspect 必须可从现有 process-events、attempts 与 formal outputs 重建 completed / active / stale / retryable roles 与 gate readiness，不新增平行 wave-state SSOT。

## BROH-016 — Preserve Human / High-cost Boundaries

本次“减少 Review 次数 + 并发 Review”不得自动跨过任何当前人工边界。

必须保留：

- high-cost acknowledgement；
- later finding-mode re-entry confirmation；
- protected-path approval；
- manual-pause closure acknowledgement；
- fallback model 是新的显式 operator action；
- no hidden provider dispatch。

一个 wave 不能用“用户曾经同意过某次高成本”自动确认新的 stale / changed authorization。必须绑定当前 cost estimate、launch authorization、model/effort、candidate / Artifact View 与 run identity。

## BROH-017 — Historical Compatibility And No Bulk Rewrite

旧的 Bootstrap finalized runs、review profiles、review-input、process events、Acceptance route/import evidence 与 caller-supplied v1 requirement decision 必须按其原合同继续 replay，或明确标记 legacy non-authorizing。

不得批量重写历史 JSON 以“升级”到新规则。

迁移策略：

```text
legacy read
new write
```

即：

- 旧 decision 可读；
- 旧 decision 不自动变成新的 Acceptance-owned risk authority；
- 新 candidate 使用新 decision producer；
- exact finalized evidence 继续按其 frozen historical policy 验证；
- 当前新规则不倒灌到旧 run。

## BROH-018 — Proper Implementation Terminal Predicate

新增 target-local：

`execution-plans/2026-08-07-bootstrap-review-operability-hardening/tools/validate_implementation.py`

并将其作为 Quick Dev 最终 `implementation-complete` 的 plan-local terminal predicate。

它必须是纯确定性终验，不得：

- 启动 Bootstrap；
- 启动 semantic reviewer；
- 自动 high-cost ack；
- 发布 acceptance-passed。

它至少验证：

1. target plan validator；
2. target plan validator tests；
3. Bootstrap Skill test suite；
4. Acceptance 与新 review requirement / bootstrap integration 相关 tests；
5. concurrent wave deterministic fixtures；
6. legacy compatibility fixtures；
7. no-authority regression fixtures；
8. schema / command registry / plan-state / implementation contract consistency；
9. 本计划声明的完整 changed consumer closure；
10. 当前 HEAD / candidate 与计划允许写集的一致性；
11. 终端实现报告更新条件；
12. 当前 implementation contract 的所有 slice 已完成。

## BROH-019 — Cross-Skill Composition Contract

必须有 detached composition fixtures 覆盖：

```text
VDD plan-ready
→ maintainer authorize
→ Quick Dev implementation-complete
→ Acceptance requirement decision
→ optional Bootstrap
→ Acceptance finalization
```

至少覆盖：

### Case A — 当前本次执行策略

```text
plan-ready
Bootstrap upstream evidence absent
maintainer auth present
→ Quick Dev allowed
```

### Case B — 普通低风险未来 plan

```text
implementation-complete
deterministic evidence complete
no hard trigger
→ deterministic_only
→ zero semantic model execution
```

### Case C — 当前 BROH self-hosted control-plane plan

```text
implementation-complete
workflow_control_plane_changed
→ review required
→ bootstrap-skill-route
→ full Round 1
```

### Case D — Round 1 P0/P1 repaired

```text
repair completeness pass
no novel P0/P1
no authority graph change
no high-risk boundary change
→ focused verifier only
```

### Case E — later full discovery

```text
typed trigger exists
→ no launch until recommendation/confidence + explicit user confirmation
```

### Case F — wave transport failure

```text
2 roles valid + 1 transport fail
→ retry only failed role
→ same semantic round
```

### Case G — authority

```text
Bootstrap clean
≠ implementation-authorized
Bootstrap clean
≠ acceptance-passed
review envelope
≠ commit/release/archive
```

## BROH-020 — Non-authorizing Review Performance Telemetry

Bootstrap cost/yield history已经存在，本次只补充能够衡量优化效果的当前运行指标，不让指标参与 authority。

建议记录/投影：

- `semantic_model_attempts`
- `full_discovery_rounds`
- `focused_verifier_attempts`
- `deterministic_only_count`
- `review_required_count`
- `review_not_required_count`
- `discovery_wave_wall_time`
- 每 role wall time
- wave critical-path wall time
- transport retry count
- P0/P1 confirmed yield
- P2 yield

这些指标必须 `authorizes=[]`。历史低 finding yield 不得自动降级当前风险；不设“为了过 gate 必须达到某个节省百分比”的伪阈值。

---

# 5. 新的 Review Requirement Decision 合同

## 5.1 Owner

唯一 owner：

```text
run-refactor-implementation-acceptance
```

不是 VDD、Quick Dev、Bootstrap、plan author 或 external delivery coordinator。

## 5.2 Proposed input

下面是建议结构，不是声称仓库当前已经存在的 schema：

```json
{
  "schemaVersion": "acceptance-semantic-review-requirement-input.v1",
  "targetPlan": "execution-plans/<target>",
  "candidate": {
    "mode": "commit",
    "baselineRevision": "<commit>",
    "candidateRevision": "<commit>",
    "candidateManifestHash": "sha256:...",
    "candidateCustodyHash": "sha256:...",
    "changedPaths": []
  },
  "deterministicEvidence": [
    {
      "role": "terminal-implementation-validation",
      "path": "...",
      "sha256": "sha256:...",
      "status": "pass"
    }
  ],
  "riskFacts": {
    "workflowControlPlaneChanged": false,
    "lifecycleAuthorityChanged": false,
    "protectedPathChanged": false,
    "securityOrPermissionBoundaryChanged": false,
    "sharedExecutionEntrypointChanged": false,
    "publicApiContractChanged": false,
    "databaseSchemaOrMigrationChanged": false,
    "runtimeOrDeploymentBoundaryChanged": false,
    "destructiveOrIrreversibleChange": false,
    "unknownOrContradictoryFacts": false
  },
  "maintainerReviewRequest": false,
  "knowledgeContextHash": "sha256:...",
  "authorizes": []
}
```

## 5.3 Proposed output

```json
{
  "schemaVersion": "acceptance-semantic-review-requirement-decision.v1",
  "targetPlan": "execution-plans/<target>",
  "requirement": "required",
  "reasonCodes": ["workflow_control_plane_changed"],
  "reviewProfile": "bootstrap-skill-route",
  "candidateBindingHash": "sha256:...",
  "deterministicEvidenceHash": "sha256:...",
  "knowledgeContextHash": "sha256:...",
  "decisionHash": "sha256:...",
  "authorizes": []
}
```

## 5.4 Deterministic algorithm

```text
validate input schema
validate target containment
validate candidate custody
validate candidate manifest completeness
validate current deterministic evidence
validate knowledge freshness
derive typed risk facts from bound sources
merge maintainer explicit upgrade request

if unknown_or_contradictory:
    blocked
else if any hard trigger:
    required
else if deterministic evidence incomplete:
    required
else:
    not_required
```

不允许：

```text
LLM 看一眼 diff → “感觉风险不高” → not_required
```

模型可以给解释性建议，但不能成为 trusted decision owner。

---
# 6. Risk Fact 的来源与责任

不要为了本次实现建立第二个全仓 risk engine。

优先重用：

- target plan profile；
- implementation contract；
- changed path manifest；
- existing protected path rules；
- repository `AGENTS.md`；
- current Acceptance domain / code review policy；
- Quick Dev 已有 deterministic classification fact；
- current plan authority；
- explicit ADR / standards；
- current candidate content manifests。

但必须注意：Quick Dev 的 `architectural / complex / normal / small_mechanical` 是 implementation model routing fact，不应该直接等于 Acceptance 的 review requirement。Acceptance 可以消费其中已验证的 typed facts，但 requirement policy 自己负责最终解释。

---

# 7. Review Profile 选择

## 7.1 普通实现闭包

```text
bootstrap-implementation-conformance
```

用于普通 code feature、bounded refactor、plan contract → implementation closure。

## 7.2 Skill / Route / Control Plane

```text
bootstrap-skill-route
```

用于 `.agents/skills/**` 的控制行为、workflow owner、review/acceptance routing、generic control-plane validator、Skill public CLI behavior。

因此本目标实施后应选择 `bootstrap-skill-route`。

Review profile 必须包含进 decision hash，不能先得到 `required` 再由外部调用者任意换 profile。

---

# 8. Bootstrap Concurrent Discovery Wave 详细设计

## 8.1 为什么必须 owner-owned

不要在外部 delivery coordinator 里直接 spawn 三个 reviewer。Bootstrap 自己拥有：

- process events；
- role reservation；
- launch authorization；
- Artifact View；
- attempt directories；
- formal output publication。

因此 wave 必须由 `.agents/skills/run-phase-bootstrap-review/` owner package 管理。

## 8.2 Public behavior

建议：

```text
py -3 .agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py \
  run-discovery-wave \
  --run-dir <run> \
  --codex-command <codex>
```

如果现有 CLI convention 需要其它名称，VDD 可以调整，但不得把并发控制交给非 Bootstrap owner。

## 8.3 Wave state 不应成为新 SSOT

不要增加新的权威 `wave-state.json`。

可生成非权威 projection，但真实状态必须从：

```text
process-events.jsonl
formal role outputs
attempt dirs
launch authorization
review-input
```

重建。

## 8.4 并发机制

具体 Python 并发机制由 Quick Dev 决定，例如 parent-managed subprocess / `concurrent.futures`。关键 contract：

- 共享只读 frozen manifest；
- role 独立 mutable attempt；
- formal output path 不重叠；
- process event append lock 正确；
- exception 独立归类；
- parent wait/join 后投影 wave result。

## 8.5 Semantic round start

现有 `semantic-round-started` 事件必须保持 lineage round 幂等。

目标：

```text
wave authorize
→ semantic round consume once
→ launch three role attempts
```

而不是每个角色各消费一轮。

若当前 `run-layer` 已有首个 discovery attempt 时的 idempotent round-start helper，则 wave 必须复用，不复制第二套 round accounting。

## 8.6 Partial success

如果需要 wave result，必须是 non-authorizing projection，例如：

```json
{
  "schemaVersion": "bootstrap-discovery-wave-result.v1",
  "reviewId": "...",
  "round": 1,
  "roles": {
    "blind_hunter": "completed",
    "edge_case_hunter": "retryable_transport_failure",
    "acceptance_auditor": "completed"
  },
  "gateReady": false,
  "retryRoles": ["edge_case_hunter"],
  "authorizes": []
}
```

如果现有 `inspect-run` 可以无损投影相同信息，则优先不新增持久文件。

---

# 9. Quick Dev 的更新后实施合同

## 9.1 Lane

必须：

```text
strict_tdd_plan
backend = quick-dev-tdd-adapter
```

## 9.2 实施前置

Quick Dev 进入前至少要求：

- target plan 仍是唯一 target；
- VDD update 已通过 plan validator；
- implementation contract current；
- knowledge context / freeze receipt current；
- explicit target-bound `implementation-authorized` 已发布；
- 无必须先修的 plan contract defect。

## 9.3 本次禁止 Quick Dev 做的事

Quick Dev 不得：

- 创建 upstream Bootstrap run；
- 为了实现顺手修改历史 review；
- 更改 lineage；
- 自己决定 `review_required`；
- 自己发布 `acceptance-passed`；
- 把 “tests pass” 直接当 acceptance。

## 9.4 Slice 建议

保留原 S0-S3，并增加：

### `BROH-S4` — Acceptance-owned requirement decision

预计 write scope：

```text
.agents/skills/run-refactor-implementation-acceptance/SKILL.md
.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py
.agents/skills/run-refactor-implementation-acceptance/scripts/bootstrap_integration.py
<owner-local review requirement helper if needed>
<matching schema if needed>
<matching tests>
```

### `BROH-S5` — Risk/profile selection + compatibility

覆盖：

- hard triggers；
- not_required 全条件；
- `bootstrap-skill-route` profile；
- legacy decision compatibility；
- exact-reuse 不误扩大。

### `BROH-S6` — Concurrent discovery wave

覆盖：

- Bootstrap owner operation；
- 3-role isolation；
- single-round accounting；
- partial retry；
- recovery inspection；
- no auto-ack。

### `BROH-S7` — Cross-skill composition and terminal implementation predicate

覆盖：

- target `validate_implementation.py`；
- plan fixtures；
- target validator parity；
- composition tests；
- final implementation report；
- terminal deterministic replay。

### Dependencies 建议

```text
S0 -> S1 -> S2
S0 -> S3
S0 -> S4
S4 -> S5
S2 + S3 -> S6
S1 + S3 + S5 + S6 -> S7
```

VDD 可根据实际 validator 约束调整 DAG，但应避免把可以独立实现的 Acceptance 决策与 Bootstrap operability 人为全串行。

---

# 10. 计划 write set 扩展

VDD 必须把预计实现文件加入 implementation contract，而不是让 Quick Dev 运行时临时扩大 scope。

## 10.1 Bootstrap package

预计：

```text
.agents/skills/run-phase-bootstrap-review/SKILL.md
.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py
.agents/skills/run-phase-bootstrap-review/scripts/_control_plane.py   # only if needed
.agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
.agents/skills/run-phase-bootstrap-review/tests/fixtures/**            # if consumed
docs/standards/bootstrap-review-control-plane.md
```

如确有 consumer，需要再修改 `references/review-profiles.v1.json` / schema；不要为了“看起来完整”无意义改 contract。

## 10.2 Acceptance package

预计：

```text
.agents/skills/run-refactor-implementation-acceptance/SKILL.md
.agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py
.agents/skills/run-refactor-implementation-acceptance/scripts/bootstrap_integration.py
.agents/skills/run-refactor-implementation-acceptance/tests/test_bootstrap_integration.py
```

建议新增（名称可按当前 package convention 调整）：

```text
.agents/skills/run-refactor-implementation-acceptance/scripts/review_requirement.py
.agents/skills/run-refactor-implementation-acceptance/tests/test_review_requirement.py
.agents/skills/run-refactor-implementation-acceptance/schemas/acceptance-semantic-review-requirement-decision.v1.schema.json
```

如果 `acceptance_core.py` 是更合适 owner，可复用，不强制新增模块。

## 10.3 Target plan

VDD 应更新：

```text
execution-plans/2026-08-07-bootstrap-review-operability-hardening/00-index.md
requirements.v1.json
plan-state.v1.json
resume-state.v1.json
authority-manifest.v1.json
baseline-and-scope.v1.json
implementation-contract.v1.json
command-registry.v1.json
fixtures/**
tools/validate_plan.py
tools/tests/**
95-implementation-evolution-and-completion-report.md
```

新增：

```text
tools/validate_implementation.py
```

及其 tests。

---

# 11. 明确不在本次实现范围的文件

默认禁止修改：

```text
PhaseA.Platform/**
PhaseA.Platform.Tests/**
runtime/phase-a/**
logs/phase-a-innernet/**
live hosted workspaces
auth/token/account code
scripts/sc/_llm_backend.py
knowledge/**
logs/reviews/** historical evidence
existing finalized Bootstrap runs
existing Acceptance run historical evidence
```

继续保留当前计划已有：

```text
execution-plans/2026-08-06-toolchain-plan-delivery-loop-skill/**
```

为 forbidden change。

该 delivery-loop 是下游 coordinator，本次先修 owner Skill 的 semantics；下游 plan 以后应单独 VDD repair，避免在本目标中形成跨计划自修改。下游最终必须对齐“upstream review conditional + Acceptance owns post-implementation requirement decision”，但不在本次 Quick Dev write set 内。

---

# 12. Git baseline / authority refreeze 规则

当前 target 的 `baseline-and-scope.v1.json` 与 `authority-manifest.v1.json` 仍绑定：

`49c5cff216646cf82179d906db60426d5f1ef314`

而本文生成时 current main 是：

`67e8fba68e2b5ce18036c05226cfa0519890b4ff`

VDD 不得机械执行：

```text
replace 49c5... with 67e8...
```

必须区分：

### A. Historical implementation baseline

如果 `49c5...` 是本 plan 有意冻结的实现前 baseline，而 `67e8...` 已包含属于本 target 的预实现 hardening，VDD 必须按 current plan identity 决定保留原 baseline、创建 candidate/refreeze binding 或记录 plan evolution 后的新 base。

### B. Current authority read

当前 source authority 必须重新读取最新 main 字节。

### C. 禁止

- 用最新 main 覆盖旧 evidence 里的历史 hash；
- 改 finalized review input；
- 修改 append-only 历史来消除 drift；
- 用 assistant prose 声称“baseline 已更新”而没有机器绑定。

---

# 13. ADR 要求

本次会改变 semantic review requirement authority、workflow review threshold、control-plane execution behavior（concurrent discovery wave）。这属于根 `AGENTS.md` 要求检查 ADR 的范围。

VDD 必须：

1. 读取当前最新 `docs/adr/` 和相应 ADR index；
2. 检查现有 ADR-0041 / ADR-0051 / ADR-0056 是否足以授权 Acceptance-owned risk-based semantic review decision 与 Bootstrap owner-owned concurrent discovery wave；
3. 如果不足，创建**下一个真实可用 ADR 编号**；
4. 不要根据本文猜一个 ADR 号；
5. 新 ADR 必须在 implementation-authorized 前达到仓库要求的 Accepted 状态；
6. 更新相应 ADR index。

建议 ADR 主题：

```text
Risk-Based Semantic Assurance Routing And Bootstrap Discovery Wave
```

标题不是硬合同。

---
# 14. VDD 更新行为要求

## 14.1 这是 existing-plan update

VDD 必须以：

`execution-plans/2026-08-07-bootstrap-review-operability-hardening/`

作为唯一 acceptance target。

不得创建类似：

```text
execution-plans/2026-08-07-bootstrap-review-risk-routing-v2/
```

的平行 plan。

## 14.2 不得制造假 review repair lineage

本次更新是维护者在 implementation 前提出的 scope evolution，不是由 finalized Bootstrap finding 触发。

因此：

- 不得伪造 predecessor review；
- 不得创建虚假的 P0/P1 finding set；
- 不得假装有一个 “Round 1 repair closure”。

如果当前 VDD repair 实现对 `repair/round-n` 强制要求 finalized review predecessor，VDD 应：

1. 保留真实来源：`maintainer_requested_preimplementation_plan_evolution`；
2. 使用仓库现有支持的 pre-implementation plan update/evolution 路径；
3. 如果当前 VDD 实现根本无法表示这种 existing-plan evolution，则这是一个 VDD contract blocker，应显式报告，而不是合成 review evidence。

## 14.3 计划更新后状态

目标仍应处于：

```text
plan-ready
```

直到维护者显式发布：

```text
implementation-authorized
```

## 14.4 知识上下文

计划 update 后：

- 重新执行 VDD knowledge preflight；
- 接受的 source 必须 current hash verified；
- Quick Dev 只消费 VDD frozen context；
- 不允许 Quick Dev 重新扩大 Locator scope。

---

# 15. Plan Validator 更新要求

更新后的 `validate_plan.py` 至少验证：

- requirements 为新的完整 BROH set；
- acceptance ID 无 orphan / duplicate；
- 新 slice set 与 requirements 映射完整；
- 每 requirement 映射到至少一个 acceptance；
- 每 acceptance 映射到至少一个 slice 或 terminal phase；
- S4-S7 write set 包含真实 Acceptance / Bootstrap consumers；
- `validate_implementation.py` 存在；
- command registry 包含 implementation terminal validation；
- fixture set 包含新增 cross-skill cases；
- plan state / resume state slice 集一致；
- authority manifest 覆盖当前 Acceptance owner sources；
- baseline policy 不把 historical hash 和 current authority 混淆；
- forbidden paths 保持；
- `authorizes` 不越权。

---

# 16. Implementation Validator 更新要求

建议 target-local command：

```text
py -3 -B execution-plans/2026-08-07-bootstrap-review-operability-hardening/tools/validate_implementation.py
```

这个命令是 Quick Dev 的 terminal predicate。

## 16.1 Required deterministic commands

VDD 应注册真实存在的命令，至少涵盖：

### Bootstrap tests

```text
py -3 -B .agents/skills/run-phase-bootstrap-review/tests/test_bootstrap_review.py
```

### Acceptance Bootstrap integration

至少：

```text
py -3 -B .agents/skills/run-refactor-implementation-acceptance/tests/test_bootstrap_integration.py
```

如果 review requirement 逻辑拆到新 test file：

```text
py -3 -B .agents/skills/run-refactor-implementation-acceptance/tests/test_review_requirement.py
```

### Acceptance control/package consumers

根据实际 changed modules 注册 current repo 的真实 consumer tests，不要在计划中写不存在的命令。

### Plan tests

```text
py -3 -B -m unittest discover \
  -s execution-plans/2026-08-07-bootstrap-review-operability-hardening/tools/tests \
  -p "test_*.py"
```

### Plan validator

```text
py -3 -B execution-plans/2026-08-07-bootstrap-review-operability-hardening/tools/validate_plan.py
```

## 16.2 Terminal authority

`validate_implementation.py` 应输出机器可读 PASS/FAIL，但 lifecycle authority 必须服从当前 Quick Dev contract。

更保守的推荐是 validator 自身保持：

```json
{
  "status": "pass",
  "authorizes": []
}
```

由 Quick Dev owner 在重放当前 terminal predicate 后发布 `implementation-complete`。

不得让 plan-local script 自己兼任 Acceptance owner。

---

# 17. Fixture / Test 矩阵

建议扩展当前 `fixtures/operability-cases.v1.json`，或拆成 `operability-cases.v1.json` + `review-routing-cases.v1.json`；由 VDD 选择最小消费者结构。

至少新增：

| Case | Expected |
|---|---|
| pre-review-skipped-maintainer-authorized | Quick Dev allowed |
| pre-review-skipped-no-maintainer-auth | blocked |
| low-risk-deterministic-only | no Bootstrap |
| explicit-maintainer-review-upgrade | required |
| workflow-control-plane-required | required + skill-route |
| unknown-risk-fail-closed | blocked |
| p2-no-new-full-round | deterministic closure |
| repaired-p0-p1-focused-only | focused verifier |
| later-discovery-needs-user-confirmation | blocked until confirmation |
| discovery-wave-three-isolated-roles | concurrent execution |
| discovery-wave-partial-transport-failure | retry one role |
| discovery-wave-single-semantic-round | one round consumed |
| wave-high-cost-no-auto-ack | blocked |
| legacy-requirement-decision-readable | compatible |
| skill-route-not-exact-reuse-widened | reject unsafe reuse |
| bootstrap-clean-no-lifecycle-authority | no acceptance/commit/release |
| current-target-post-implementation-review | required |

---

# 18. 实施后验收流程

Quick Dev 发布 `implementation-complete` 后，必须停止 Quick Dev authority，然后显式进入 `run-refactor-implementation-acceptance`。

## 18.1 Acceptance 第一阶段：确定性证据

先完成当前 Acceptance 已拥有的：

- target resolution；
- baseline / candidate manifests；
- custody verification；
- knowledge context；
- requirement inventory；
- policy；
- matrix；
- checklist；
- scan；
- coverage / evidence；
- current implementation predicate replay。

## 18.2 新 review requirement decision

对本目标：

```text
target = execution-plans/2026-08-07-bootstrap-review-operability-hardening
```

由于 changed paths 包含 Bootstrap / Acceptance workflow control plane，预期：

```text
requirement = required
reviewProfile = bootstrap-skill-route
reasonCodes includes workflow_control_plane_changed
```

这个结果仍必须从当前绑定事实确定性复现，不能因为本文写了 expected 就硬编码 pass。

## 18.3 Round 1

调用新的 Bootstrap：

```text
prepare
preflight
prove-access
authorize-launch
run-discovery-wave
gate
independent verifier if P0/P1
finalize
```

注意：

- high-cost 仍需要显式 acknowledgement；
- wave 不得代替 access proof；
- wave 不得代替 launch authorization。

## 18.4 Clean / P2

### Clean

Acceptance 导入 validated Bootstrap assurance，继续 deterministic finalization。

### P2-only

在当前 semantic run 内 fix、refute 或按 policy defer，再做 deterministic targeted closure；不创建新的 full semantic round。

## 18.5 P0/P1

先判 owner：

- Plan intent defect → VDD in-place plan repair/update。
- Implementation defect within current contract → Quick Dev repair。

两者都必须保留 predecessor、current candidate manifest、changed path binding、callsite inventory、direct consumers、targeted tests、controlled composition receipts，并运行 Acceptance `audit-repair-completeness`。

如果没有：

- novel P0/P1；
- authority context graph change；
- high-risk boundary change；

则只运行：

```text
focused_repair_verification
```

## 18.6 后续 full discovery

只有 Acceptance 产生 typed trigger 才能提议，之后必须展示 trigger、expected cost、recommendation、confidence，并取得用户显式确认，再生成 Bootstrap hash-bound re-entry authorization。没有确认，不启动。

## 18.7 Hard limit

保持：

```text
hard full review round limit = 3
```

不得通过换 reviewId、changeId 或 successor dir 重置预算。

---

# 19. 对串行 execution-plans 的长期运行规则

本目标只改 owner Skill，但应支持仓库大量强依赖 plan 的实际使用。

## 19.1 Expensive Review 只针对 delivery frontier

如果 backlog：

```text
A → B → C → D
```

则：

- B/C/D 可以提前写 plan；
- 只对当前要实施/验收的 frontier 做 expensive semantic assurance；
- A acceptance-passed 后，B 重新验证当前 source/hash/knowledge，再进入实施；
- 不提前对未来 plan 做易 stale 的高成本 review。

## 19.2 里程碑 semantic audit 不是单 plan gate

未来可以单独增加 cumulative semantic audit，但不应自动倒退已经通过 lifecycle 的普通 plan。本项不在此次实现范围，只要求本次结构不阻断未来扩展。

---

# 20. 性能预期与观测

本次不设置“必须节省 80%”这类无依据 gate，但系统设计应让以下形态成为可能。

## 20.1 普通低风险 plan

```text
semantic executions = 0
```

仍然有完整 deterministic Acceptance。

## 20.2 高风险 plan

第一次 full review 仍然有三个 discovery role，但 wall clock 应接近：

```text
max(Tblind, Tedge, Tauditor) + orchestration overhead
```

而不是三者相加。

## 20.3 Repair

无升级 trigger：

```text
1 focused verifier
```

而不是三个 reviewer 从头 discovery。

观测指标只作为 non-authorizing metrics，不参与是否放行。

---

# 21. Stop-loss

以下任一出现时停止自动推进：

- candidate / baseline binding 不明确；
- VDD knowledge context stale；
- protected rule 与“跳过 pre-review”发生真实冲突；
- implementation contract write set 不覆盖 required consumer；
- new risk facts unknown/contradictory；
- Acceptance decision schema drift；
- live review controller conflict；
- high-cost 未确认；
- repeated identical transport fingerprint 达 stop-loss；
- Round 3 hard limit；
- current target terminal predicate 不能确定性复现；
- 历史兼容测试失败；
- exact reuse profile 被错误放宽；
- reviewer isolation 被破坏。

---

# 22. 非目标

本次不做：

- Phase API / browser 接入；
- Phase Harness；
- Sandbox Harness；
- 全仓统一 toolchain CLI；
- 后台 watchdog 自动跑 review；
- 自动 commit / release / deploy / archive；
- 修改 live Phase DB / hosted workspace；
- 自动发布 knowledge catalog；
- 将 Review 改造成自由多 Agent manager；
- 删除 Blind Hunter / Edge Case Hunter / Acceptance Auditor；
- 降低 P0/P1 independent verifier；
- 删除 Artifact View / hash / lineage；
- 无限 full discovery；
- 用 LLM confidence 替代 deterministic authority。

---
# 23. Definition of Done

## 23.1 VDD plan-update DoD

在 Quick Dev 前：

- 唯一 target 仍是现有目录；
- BROH-001..007 保留；
- BROH-008..020 已建模；
- acceptance mapping 完整；
- implementation contract 写集包含 Acceptance + Bootstrap 真正 consumers；
- plan validator 更新；
- plan tests 更新；
- `validate_implementation.py` 已成为计划要求；
- plan-state / resume-state / 95 report 一致；
- current knowledge preflight pass；
- current authority / baseline drift 有明确处理；
- ADR decision 完成；
- state = `plan-ready`。

## 23.2 本次实施授权

然后由维护者显式发布：

```text
implementation-authorized
```

本次明确：

```text
do not run bootstrap-upstream-plan
```

## 23.3 Quick Dev DoD

- strict TDD route；
- 每 slice RED/GREEN/REFACTOR；
- 所有 changed paths 在 contract；
- target implementation validator current PASS；
- no semantic review from Quick Dev；
- Quick Dev publish at most `implementation-complete`。

## 23.4 Acceptance DoD

- current candidate / baseline custody pass；
- deterministic Acceptance pass；
- new Acceptance-owned review decision pass；
- 本目标被判 `required`；
- profile = skill-route assurance；
- Round 1 使用 concurrent discovery wave；
- P0/P1 independent verification；
- repair 后无 escalation 时 focused verifier；
- later full discovery only typed/user-confirmed；
- no Round4；
- Acceptance 独自发布 `acceptance-passed`。

---

# 24. VDD 可直接消费的请求块

以下文字可直接作为本文件被 VDD 消费时的高层指令：

```text
Update the existing execution-plan directory:

execution-plans/2026-08-07-bootstrap-review-operability-hardening/

Do not create a successor or parallel plan merely for this request.

Treat this as a maintainer-requested pre-implementation evolution of the
existing self-hosted plan. Preserve the current BROH-001..BROH-007 operability
requirements and extend the same target with the review-frequency and wall-time
governance requirements in this document.

The central behavior change is:

1. Keep pre-implementation Bootstrap Review optional under the existing VDD
   lifecycle contract. For this target and this delivery, explicitly skip the
   upstream Bootstrap Review. Do not fabricate a review run, predecessor,
   finding set, repair closure, or clean envelope.
2. After the updated plan reaches plan-ready, require explicit target-bound
   maintainer publication of implementation-authorized before Quick Dev.
3. Quick Dev remains strict_tdd_plan and must not launch Bootstrap. Add a real
   plan-local deterministic implementation terminal predicate separate from
   plan validation and post-implementation acceptance.
4. Move semantic-review requirement ownership into Refactor Acceptance.
   Acceptance must derive required/not_required deterministically from current
   candidate custody, changed paths, deterministic evidence, repository rules,
   protected/high-risk facts, knowledge freshness, and an optional explicit
   maintainer upgrade request. Caller-supplied required/not_required is not
   authority for new runs.
5. Preserve deterministic_only as the ordinary low-risk acceptance lane.
6. Preserve the existing bounded Bootstrap semantics: one automatic discovery
   round, P2 current-run closure, non-escalated P0/P1 repair to one focused
   repair verifier, typed/user-confirmed later discovery, and hard full-review
   limit 3.
7. Add a Bootstrap-owned concurrent discovery wave that runs blind_hunter,
   edge_case_hunter, and acceptance_auditor concurrently while keeping their
   sessions, attempts, candidates, handshakes, evidence, and formal outputs
   isolated. Partial transport failure retries only failed roles and does not
   consume another semantic round.
8. Do not auto-ack high-cost launch, protected paths, later finding-mode reentry,
   or manual-pause closure.
9. Do not weaken Artifact View, exactEvidence, lineage, source hashes,
   independent P0/P1 verification, or authorizes=[] boundaries.
10. Keep historical runs replayable under their frozen contracts. Use
    legacy-read/new-write migration; do not bulk-rewrite old evidence.
11. Because this target changes the review/acceptance workflow control plane,
    its own post-implementation Acceptance must classify semantic assurance as
    required and use an explicit Skill/route review profile. Acceptance remains
    the only owner allowed to publish acceptance-passed.
12. Keep Phase service, live runtime/workspaces, auth, knowledge publication,
    historical review evidence, and the 2026-08-06 delivery-loop plan outside
    this implementation write set.

Re-read current main before freezing the updated plan. The design-input baseline
for this document is main@67e8fba68e2b5ce18036c05226cfa0519890b4ff, while the
existing plan currently carries older 49c5cff... baseline/authority bindings.
Do not blindly replace historical baseline hashes; explicitly determine whether
each binding is a historical implementation baseline, a current authority read,
or a candidate/refreeze binding.

Update the plan-local validator, fixtures, command registry, plan state, resume
state, implementation contract, authority/scope bindings, report, and tests so
the resulting directory is internally complete and immediately consumable by
Quick Dev after explicit implementation authorization.
```

---

# 25. Quick Dev 启动块

VDD 更新并得到显式授权后，实施时应使用的语义是：

```text
Target:
execution-plans/2026-08-07-bootstrap-review-operability-hardening/

Precondition:
- updated plan validates
- state is implementation-authorized
- current frozen knowledge context validates
- no upstream Bootstrap Review is required for this invocation

Execution:
- enter strict_tdd_plan
- execute updated BROH slices in dependency order
- use only declared write sets
- preserve historical review/acceptance evidence
- do not launch Bootstrap
- stop only on typed blocker / repair handoff / terminal implementation predicate
- publish at most implementation-complete
```

---

# 26. 实施后 Acceptance 启动块

Quick Dev `implementation-complete` 后：

```text
Run Refactor Implementation Acceptance for exactly:

execution-plans/2026-08-07-bootstrap-review-operability-hardening/

Use the new Acceptance-owned review requirement decision.

For this target, the decision is expected to be semantic-review required because
the candidate changes review/acceptance workflow-control behavior. The exact
decision must still be reproduced from current bound evidence; do not hardcode a
pass simply because this document says so.

If required:
- select the explicit Skill/route review profile
- invoke repository-owned Bootstrap
- complete deterministic preflight
- prove access
- stop for current high-cost acknowledgement
- authorize launch
- execute one owner-owned concurrent discovery wave
- gate
- independently verify accepted P0/P1
- finalize and import only current hash-bound evidence

For repair:
- route plan-intent defects to VDD
- route implementation defects within the current contract to Quick Dev
- run Acceptance-owned repair completeness
- use one focused repair verifier when no escalation trigger exists
- require typed trigger + recommendation/confidence + explicit user confirmation
  before any later full discovery
- never create Round 4

Only Acceptance may publish acceptance-passed.
```

---

# 27. 最终设计结论

本次真正要固定进仓库的规则不是简单的“Review 少跑一点”，而是：

```text
Deterministic acceptance owns deterministic facts.
Semantic review is conditional assurance.
Acceptance owns the decision to request semantic assurance.
Bootstrap owns semantic execution.
Quick Dev owns implementation only.
VDD owns plan intent only.
Maintainer owns implementation authorization and explicit risk acknowledgements.
```

同时：

```text
Full discovery depth stays high.
Full discovery frequency becomes risk-based.
Repair verification becomes focused.
Three independent discovery roles run concurrently under Bootstrap ownership.
```

这才能在不牺牲当前证据、lineage、Artifact View、独立 verifier 和人工边界的前提下，系统性消除“审查占绝大多数墙钟时间”的结构性问题。

---

# 28. VDD 最终检查清单

VDD 发布更新后的 `plan-ready` 前逐项确认：

- [ ] 当前 main 已重新读取，不依赖本文快照推断最新事实。
- [ ] 只更新既有 `2026-08-07-bootstrap-review-operability-hardening`。
- [ ] BROH-001..007 未被意外删除或语义弱化。
- [ ] BROH-008..020 或等价需求完整进入 requirements/acceptance/slices。
- [ ] Acceptance 已成为新 review requirement 的 owner。
- [ ] `not_required -> deterministic_only` 有可执行 fixture。
- [ ] 当前 control-plane target 的 post-implementation decision 必须可确定性得到 `required`。
- [ ] `bootstrap-skill-route` 与 implementation-conformance exact reuse 边界清楚。
- [ ] concurrent discovery wave 由 Bootstrap owner 实现。
- [ ] 三 reviewer 仍完全隔离。
- [ ] partial transport retry 不额外消费 semantic round。
- [ ] high-cost / later discovery / protected path / manual pause 的用户边界均保留。
- [ ] P2-only 不触发 full review。
- [ ] non-escalated repair 只走 focused verifier。
- [ ] hard full round limit 仍为 3。
- [ ] historical evidence 不批量重写。
- [ ] target-local `validate_implementation.py` 已进入 contract。
- [ ] Quick Dev terminal predicate 不包含 semantic Review。
- [ ] implementation-complete 与 acceptance-passed 明确分离。
- [ ] Phase / live runtime / workspace / auth / knowledge publication 不进入 write set。
- [ ] 2026-08-06 delivery-loop plan 仍不在本次 write set。
- [ ] ADR 权威足够，或已使用真实 next available ADR 编号完成决策。
- [ ] plan validator + validator tests PASS。
- [ ] plan-state = plan-ready；未伪造 implementation authorization。
- [ ] 本次明确记录：pre-implementation Bootstrap Review skipped by maintainer instruction。
