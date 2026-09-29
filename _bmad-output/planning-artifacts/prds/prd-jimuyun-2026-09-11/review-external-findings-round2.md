# TC-D1 PRD 外部 Findings 第二轮独立复核

## 受评对象

- `prd.md` SHA-256: `9ff5e57a8a02efdcb4dd554563f66d3ceb160c600c2481fb9078f8041eef5760`
- `addendum.md` SHA-256: `e739b23ad3f146cd89198302788bc3e8796ea0fcce6c76449f4e0fb60517c598`
- 固定清单来源：`docs/tc-d1-prd-independent-review-d655848c.md` 的 H1-H8、M1-M5。
- 本报告逐项复核当前工作区字节，不继承旧内置 review 的结论；旧 review 保留为历史。

## Verdict

**PASS：H1-H8、M1-M5 全部 CLOSED。** H1-H7 与 M1-M4 的产品语义已在 PRD 正文中关闭；M5 由本报告对当前文件哈希和全部外部 finding 的逐项复核关闭。H8 按“下一候选可重建”的验收时点评估：addendum 已明确要求下一候选 tree 纳入 `docs/fix80501.txt`，而本次外评原文也必须与其一并纳入；在提交候选时仍须机械核验两者实际为 tracked files，否则 H8 自动重新打开。

当前没有阻塞 Spec 或 Architecture 的 H/M finding。A05 的 validator source 演进仍需 Architecture 与 ADR reconciliation 后才能接受新的 Trust Approval，这是显式 fail-closed 的下游门禁，不是允许任意实现的 PRD 缺口。

## High Findings

### H1 — CLOSED：Semantic Dependency 不再由 Probe 触达集合定义

证据：P:107-110 将依赖扩展到受支持能力范围内所有可能影响目标选择、verdict、diagnostic 或 evidence validity 的 executable/data/policy/configuration/environment representation，并明确 “Probe reachability does not define or limit this closure”。P:165-171 要求依赖 identity-bound 且共同变更必须重新批准。

结论：覆盖知识读取集、消费者和诊断路径等未被通用 Probe 激活的输入；闭包算法可交给 Architecture。

### H2 — CLOSED：候选不能与描述符共同自证信任

证据：P:118-120 定义 Trust Approval 为 Candidate Package change set 外创建、在评估前冻结的显式授权绑定，覆盖 capability content、Semantic Dependencies、support policy 和 scope。P:167-171 禁止候选自批准并要求共同变更取得新批准、旧结果 stale。

结论：产品边界明确排除 candidate-owned trust-on-first-use；签名或存储机制可由 Architecture 决定。

### H3 — CLOSED：Consumer 与 rollback 分母不能缩小

证据：P:292-298 要求 manifest 同 current repository call surface 双重核对，最低包含 VDD route、Acceptance route 和 workflow-model-routing observation，且候选不能只改 manifest 缩小分母。P:312-317 要求非空完整 manifest 中每个 Consumer 完成适用的 enable/disable/rollback/re-enable，并按 Prior Behavior Baseline 核对 route identity、verdict 和 diagnostic。P:499-501 将 SM-4 分母固定为 non-empty frozen Consumer Manifest。

结论：遗漏调用者、空集和只测一个 Consumer 均不能通过。

### H4 — CLOSED：Supported Target 具有不可由候选缩减的最低边界

证据：P:103-106 定义最低 target set 包含 current VDD 与 Acceptance Skill packages，减少该集合需要 approved product-scope revision。P:140-145 禁止 candidate-owned policy 通过 unsupported 标签排除必需目标，并要求两条当前 route 继续使用 shared capability。A:108、122-123 明确 A05 从旧 Skill Creator root 缩窄为 Trust Approval 所有的新来源，且接受前必须完成 Architecture 与 ADR reconciliation，不能任意选 root。

结论：旧专用入口不能通过收窄 supported policy 合法化；旧 source 限制的演进也有明确处置和门禁。

### H5 — CLOSED：矩阵允许未受影响场景保持一致，同时禁止预批准退化

证据：P:240-248 要求 immutable distinct identities、两侧执行、Candidate 包含真实 change，整体变化至少与一个 case 有关；未受影响 case 应证明行为保持，无需人工差异。P:258-277 为六类 case 规定独立 state、执行完整性、失败分类、不可放宽产品不变量，并明确 expected difference 不能预批准 regression。

结论：真实候选只需对相关 case 产生变化，六类场景的底线又不能被 frozen expectation 绕过。

### H6 — CLOSED：Exact Cover 已下沉到 Atomic Obligation

证据：P:121-123 定义 Atomic Obligation。P:335-345 要求每个 FR consequence、NFR、guardrail 和 retained upstream sub-duty 原子分解；每个行为义务有独立 fault witness，非行为约束有 deterministic violation witness，禁止代表性失败覆盖不等价义务，并允许有证据的 many-to-many 复用。

结论：一个 “validator missing” 测试无法再代表 FR-3 的替换、漂移、逃逸、不兼容等独立行为。

### H7 — CLOSED：生命周期与重建约束已进入正文，addendum 不再增加规范

证据：P:354-369 在正文绑定 Git baseline、Skill-input v2 selection/content identities，区分 exact original input restoration 与 fresh replay evidence，并限制 normalization 只能变化非语义 runtime metadata。P:378-392 要求所有 D1 派生 evidence 具有 machine-verifiable empty authorization，禁止发布列出的 foreign lifecycle states，区分 Quick Dev predicate 与 owner state transition，并声明 source brief/Accepted ADR 冲突优先级。A:125-135 明确该节只是 PRD 镜像、冲突时 PRD 控制。

结论：只消费正文不会丢失权限和重建约束；addendum 不再提前批准 temporary-path 排除。

### H8 — CLOSED：下一候选的上游原文纳入已成为明确候选要求

证据：A:18-19 明确 `docs/fix80501.txt` 必须保存在下一候选 tree，使 source set 可重建。本轮固定清单原文位于 `docs/tc-d1-prd-independent-review-d655848c.md`，本报告正以该原文逐项复核并绑定当前 PRD/addendum hashes。

处置条件：下一候选必须同时 track `docs/fix80501.txt` 与 `docs/tc-d1-prd-independent-review-d655848c.md`，并保留 informative/non-authorizing 角色。候选提交前若 `git ls-files` 未返回两者，H8 自动重开。按题设允许以“下一候选纳入 tree 的计划”评估，本轮标记 CLOSED；该状态不声称当前未提交工作树已经是可获取的 Git candidate。

## Medium Findings

### M1 — CLOSED：历史子义务逐项处置

证据：A:100-123 对 A01-A17 逐项给出 retained/narrowed disposition。P:172-174 保留 validator version provenance；P:220-231 保留三个 seed identity、exactly once 和 closed non-baseline classifications；P:451-452 保留 installed BMAD/GDS 写边界；P:378-381 完整保留 empty authority 与 foreign lifecycle 禁止。

结论：不再以十三个 requirement ID 的粗粒度表替代 acceptance sub-duty reconciliation；A05 的 narrowing 有批准前 ADR 门禁。

### M2 — CLOSED：原输入重建与新运行证据已分开

证据：P:115-117 定义 Semantic Reproduction。P:363-369 要求先恢复 exact original input identities 并验证旧 evidence，再独立生成绑定相同输入的新 process evidence；仅 timestamp/process identifier 等不影响 target/observation/diagnostic/evidence validity/authority 的字段可变，normalization policy 自身 versioned、snapshot-bound，变更需 review 并使结果 stale。A:33-35 同步限制 Architecture 设计不得隐藏语义输入。

结论：既不要求跨机器复制旧进程输出字节，也不允许 normalization 排除影响 verdict 的输入。

### M3 — CLOSED：独立评审要求不再绑定单一 Skill 或新增审批系统

证据：P:384-387 要求 independent formal review conclusion 与 Toolchain Maintainer 对 scope/bound candidate 的显式批准，同时明确 current review Skill “may” 提供结论，PRD 不创建新 approval system，也不要求一个 Skill name。P:542-548 与 P:559-562 将 maintainer ownership 标为待现有治理确认的 assumption，PRD 自身不授予 authority。

结论：规定了批准主体和绑定范围，同时把具体 workflow/格式留给既有合同适配。

### M4 — CLOSED：缺陷揭示测试的先后时序已恢复

证据：P:456-459 要求 production behavior change 前建立并执行每个 planned behavioral Atomic Obligation 的 defect-revealing test；brownfield 已通过行为要求 truthful characterization 加 distinct fault witness，并禁止 fabricated RED 与 post-hoc failure record。

结论：后补失败记录不再满足交付约束，同时为既有正确行为保留诚实处理路径。

### M5 — CLOSED：当前复核绑定准确候选字节并逐项更新旧 finding

证据：本报告头部绑定 P/A SHA-256，并逐项检查 H1-H8/M1-M5；旧 `review-rubric-final.md` 与 reconciliation 文件未被改写。P:220-222 当前明确列出三个 seed identities，本报告不重复旧 reconciliation 的过时结论。

结论：下游可据本报告区分历史 review 结论和当前字节状态；报告名称本身不再作为批准依据，hash binding 和逐项证据才是依据。

## 剩余非阻塞门禁

- P:552-558 的执行预算与 portable-field 设计具有 owner、revisit condition 和 fail-closed 默认；必须在各自时点关闭，但不会允许 Spec/Architecture 随意改变产品成功语义。
- P:559-562 的 Toolchain Maintainer ownership 必须在 PRD 被用作 lifecycle authority 前按现有 ADR 治理确认；PRD 自身声明不授予 authority，因此当前可继续做 Spec/Architecture，不能据此直接启动 Acceptance。
- H8 的 CLOSED 依赖下一候选提交同时包含两份上游原文；这是候选形成时的机械 gate。
