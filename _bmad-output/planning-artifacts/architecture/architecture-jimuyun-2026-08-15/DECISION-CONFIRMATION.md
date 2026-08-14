# Architecture Remaining Decision Confirmation

## Purpose

本文汇总 Acceptance Review / Bootstrap Efficiency Architecture 在完成 `ARCHITECTURE-SPINE.md` 前尚未冻结的全部重要架构决策。目标是一次性确认，不再逐项问答。

本文不是新的 requirement authority，也不修改已经冻结的 Canonical Spec Package。它只记录 Architecture 层仍需选择的实现不变量。PRD 与原 requirements 继续作为 provenance；Canonical Spec Package 仍是当前 normative input。

## Already Fixed

以下内容已经确认，不需要再次决定：

- 顶层范式：Evidence-Gated Pipes-and-Filters，并以 Artifact DAG 表达。
- Bootstrap 内部执行范式：Event-Sourced Execution State Machine。
- Lifecycle ownership：VDD owns `draft` / `plan-ready`；Maintainer owns `implementation-authorized`；Quick Dev / `quick-dev-tdd-adapter` owns `implementation-complete`；Acceptance owns `acceptance-passed`；Bootstrap 不发布 lifecycle state。
- Acceptance 负责 freeze、Changed-set Manifest、Consumer Closure、required-check projection、typed route、Bootstrap evidence import 和 finalization。
- Shared Canonical Evidence Primitive 位于 `scripts/toolchain/canonical_evidence/`，是 repository-neutral、pure、deterministic library，不是中央 registry 或 authority owner。
- Canonical identity pipeline：artifact owner builds semantic projection -> shared primitive canonicalizes -> shared primitive applies owner-defined domain separator -> content identity。
- Canonical JSON 合同为 `repository-canonical-json.v1`；值域、strict parse、Unicode、排序、转义、int64 与禁止类型已经冻结。
- Legacy 策略为 `legacy-canonical-sha256.v1` verify-only compatibility；不得 mint、write 或从 current verification 自动 fallback。
- Artifact authority、schema、projection、domain semantics 和 lifecycle ownership 继续由各 producer/owner 分散持有。

## Remaining Decisions

剩余需要确认的共有 **9 项**。以下均给出 Architecture 推荐默认值；若没有异议，可一次性全部固定。

### D1. Current Identity Envelope And Domain Contract

**建议固定：**

- `domain_hash(domain, projection)` 的 canonical hash input 固定为：

```json
{"domain":"<owner-defined-domain>","payload":<semantic-projection>}
```

- 新生成的 artifact 或 receipt 在其 owner schema 中显式携带：
  - `canonical_evidence_version`
  - `identity_domain`
  - `content_identity`
- `identity_domain` 必须匹配：

```text
^[a-z0-9]+(?:[._-][a-z0-9]+)*\.v[1-9][0-9]*$
```

- Domain 的名称和 projection 语义由 artifact owner 定义；shared primitive 只验证 domain 语法并执行 hash。
- Domain 变化、projection 变化或 canonical algorithm 变化都必须产生新的 identity，禁止隐式兼容。

**固定此项可防止：** 不同 consumer 对“domain separation”采用不同 envelope，或 receipt 只保存 hash 而无法证明所用算法与业务 domain。

### D2. Artifact DAG Custody And Mutation Rule

**建议固定：**

- 每类 artifact 由其 lifecycle/contract owner 在 owner-local 路径发布。
- Artifact 一经发布即 immutable；修复、重跑或重新投影必须产生 successor artifact。
- Successor 显式绑定 predecessor identity、输入 identities 和生成策略版本。
- Consumer 只能消费 schema-valid、identity-valid、authority-valid 的 artifact。
- 不允许原地覆盖已被其他 artifact 引用的 manifest、closure、route、receipt、segment descriptor 或 lifecycle evidence。
- 不建立 central evidence store、global mutable registry 或跨 Skill 共享 current-state 文件。
- “current pointer”只能是 owner-scoped selection artifact；pointer 变化不改变被选择 artifact 的内容真值。

**固定此项可防止：** pipeline 退化成共享可变状态，以及 repair 后历史证据被静默改写。

### D3. Consumer Closure Typed Edge Taxonomy

**建议固定 Consumer Closure 的最小 typed edge 集：**

- `changed_artifact`
- `implementation_contract`
- `requirement_acceptance_binding`
- `executable_entrypoint`
- `validator_or_consumer`
- `repository_authority`
- `authorization_prerequisite`
- `external_selection`
- `deterministic_evidence`

每条 edge 至少绑定 source identity、target identity、edge type、discovery basis 和 validation result。Owner 可以增加更具体的 subtype，但不得用自由文本替代上述语义类型。Closure 证明消费关系和 required-check 投影，不取得被引用 artifact 的 ownership。

**固定此项可防止：** 只靠路径列表或 Git diff 猜测下游消费者，导致 validator、authority prerequisite 或 external selection 漏检。

### D4. Model-Visible Range Projection

**建议固定：**

- Frozen source identity 以原始文件 bytes 为基础，不以解码后的字符串或模型输出为基础。
- Range 使用 zero-based、start-inclusive、end-exclusive byte offsets。
- Descriptor 显式携带 source content identity、byte range、解码 encoding 和 projection version。
- 不做 newline normalization、Unicode normalization 或 silent replacement decoding。
- Range 必须完整覆盖合法字符边界；非法 UTF-8/指定 encoding 边界 fail closed。
- 重读和续传必须绑定同一 source identity；source 改变后旧 range descriptor stale。
- Architecture 只冻结 range contract，不冻结 8,000 汉字、1 MiB 或其他 model-visible threshold；阈值继续由已存在的 model-visible tool-round policy 管理。

**固定此项可防止：** PowerShell/FastCtx、不同换行和分段策略看到不同内容，同时避免 Architecture 把易变的窗口数值固化成长期不变量。

### D5. Canonical Bootstrap Segment Descriptor

**建议固定：**

Bootstrap segment descriptor 必须按 Canonical Spec Package 已定义字段集构造，并至少绑定：

- review run identity
- frozen baseline/current identities
- Changed-set Manifest identity
- Consumer Closure identity
- route/profile identity
- assigned paths or byte ranges
- applicable requirement / acceptance IDs
- required checks
- parent attempt identity
- model/backend identity where reuse depends on it
- segment ordinal and total
- output/evidence contract
- predecessor or repair input identity when applicable

Identity domain 固定为：

```text
jimuyun.bootstrap.segment-descriptor.v1
```

同一个 descriptor identity 必须贯穿 assignment、model request、segment receipt、validator、parent fold、retry 和 recovery；任何字段变化都产生新 descriptor identity。

**固定此项可防止：** child 实际审阅的范围与 parent 聚合、重试或最终 receipt 所声明的范围不一致。

### D6. Required-Check Execution And Reuse Receipt

**建议固定：**

- 每个 required check 必须绑定固定的真实 runner/validator，不能由通用 receipt checker 替代真实执行。
- Execution receipt 至少绑定：
  - command ID
  - executable identity
  - argv
  - working directory
  - allowlisted environment projection
  - dependency/tool versions
  - acceptance IDs
  - input artifact identities
  - observed exit status
  - output/evidence identities
  - execution policy version
- Receipt 必须由 runner 执行结果生成；手写字段正确的 receipt 不能证明 command 已执行。
- Reuse 只允许 exact match：runner、argv、cwd、environment projection、dependencies、acceptance scope、inputs 和 policy identity 全部一致。
- Required-check receipt 始终 `authorizes=[]`；它只提供 evidence，不发布 lifecycle state。

**固定此项可防止：** 假 GREEN、旧 receipt 跨输入复用，以及 validator evidence 越权成为 authorization。

### D7. Bootstrap Runtime Policy, Event And Lease

**建议固定：**

- Bootstrap runtime 参数由一个 versioned runtime-policy artifact 管理。
- Timeout、heartbeat interval、effective-progress window、retry family maximum、backoff、lease duration、stale reconciliation 和 output ceiling 是可独立调节字段。
- Architecture 只要求字段存在、含义确定、版本可绑定，不冻结具体数值。
- Process Event 是 execution history 的 authority，至少覆盖 reservation、start、heartbeat、effective progress、terminal、stale、retry、reconcile 和 abandon。
- Lease 是从 events + runtime policy 推导的可重建 view，不是独立真值。
- Retry 必须创建或绑定明确 attempt identity；不得覆盖前一次 attempt 的 events/receipt。
- Recovery 必须先 reconcile process liveness、lease 和 latest effective progress，再决定 resume、retry、stale 或 abandon。

**固定此项可防止：** watchdog、retry、lease 各自拥有冲突状态，以及数值调优被误当 Architecture invariant。

### D8. Terminal Taxonomy And `vcec-r1n`

**建议固定 terminal taxonomy：**

- `completed`
- `failed-transport`
- `stale-process`
- `blocked-recovery-required`
- `abandoned`

其中：

- `completed` 只表示 Bootstrap execution terminal，不发布 `acceptance-passed`。
- `failed-transport` 表示当前 attempt 未产生可验证 semantic result。
- `stale-process` 表示 liveness/lease reconciliation 已证明当前执行不可继续。
- `blocked-recovery-required` 表示必须通过明确 repair/recovery input 才能继续。
- `abandoned` 表示该 attempt/run 被保留为历史，不再作为 active execution。

现有 `vcec-r1n` 固定解释为：

- terminal = `abandoned`
- classification = `historical-runtime-failure`
- reusable = `false`
- `authorizes=[]`

不得删除、重写或把它升级为成功 evidence。

**固定此项可防止：** 历史失败被误选为 current，或 Bootstrap terminal 被误解为 Acceptance lifecycle publication。

### D9. Brownfield Migration Sequence

**建议固定迁移顺序：**

1. 实现 shared primitive、strict parser、golden vectors 和 mutation corpus。
2. 迁移已具备 domain separation 的直接 adopters，并证明 bytes/hash 等价。
3. 实现唯一的 `legacy-canonical-sha256.v1` verify-only profile。
4. 为 domainless producers/validators 升级 artifact schema、owner domain 和 identity fields。
5. 切换所有 mandatory consumers，运行跨 consumer vectors 和 current/legacy cross-rejection。
6. 删除 Skill 内重复 canonical JSON/hash/path normalization implementation。
7. 再按独立计划迁移 knowledge、workflow、Git snapshot、SC LLM review 等 repository-wide follow-up adopters。

Mandatory wave 完成前，Acceptance/Bootstrap feature 不得声称 canonical convergence。Follow-up wave 不阻塞本功能，但 shared primitive 落地后禁止新增 private canonical implementation。

**固定此项可防止：** 先删除旧实现导致历史证据不可验证，或只迁移 producer、未迁移 consumer 而形成双重 identity 体系。

## Explicitly Deferred

以下 **4 项不需要本轮确认，也不阻塞 Architecture 或后续 VDD**：

### F1. Formal Wall-Time Target

正式端到端 wall-time SLO 需要真实 telemetry 和基线后再决定。Architecture 只要求计时证据可归因到 deterministic filters、Bootstrap attempts、retry/recovery 和 finalization。

### F2. Formal Consumer-Closure Reduction Threshold

本轮不冻结“必须减少多少百分比”的阈值。先要求 closure 可测量、可重放，并分别报告 changed set、consumer expansion、semantic review scope 和 model-visible bytes。

### F3. Concrete Retry And Watchdog Values

Timeout、attempt maximum、heartbeat、lease、stale window 与 backoff 的具体数值归 versioned runtime policy；在运行数据和故障演练后 ratify/amend，不进入 Architecture spine。

### F4. Non-Python Binding And Algorithm V2

当前先建立 language-neutral contract 和 Python reference implementation。其他语言 binding、性能优化或 `repository-canonical-json.v2` 只有出现真实 consumer 需求时才立项。

## One-Time Confirmation

若以上建议均可接受，请直接回复：

```text
D1-D9 全部按建议固定。
```

若只需修改少数项，可在同一条回复中按 ID 写明，例如：

```text
D1-D9 除 D7 外按建议固定；D7 的 lease 不能由 heartbeat 单独续期，必须有 Effective Progress。
```

收到这一次确认后，Architecture 将不再逐项询问；后续直接：

1. 把 D1-D9 写入 memlog 并完成 `ARCHITECTURE-SPINE.md`。
2. 执行 input reconciliation、deterministic lint 和 Architecture Reviewer Gate。
3. 修复重要问题并完成最终验证。
4. 交付 spine，并建议由 `bmad-spec` refresh/adopt Architecture companion。
