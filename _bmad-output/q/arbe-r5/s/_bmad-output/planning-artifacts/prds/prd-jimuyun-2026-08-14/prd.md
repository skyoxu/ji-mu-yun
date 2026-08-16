---
title: Ji Mu Yun 验收范围与 Bootstrap 审查效率优化
status: final
created: 2026-08-14
updated: 2026-08-14
---

# PRD：Ji Mu Yun 验收范围与 Bootstrap 审查效率优化

## 0. 文档目的

本文面向 Ji Mu Yun 工具链控制面维护者、Acceptance 维护者、Bootstrap Review 维护者、VDD/Quick Dev 工作流维护者以及后续 Architecture 与执行计划作者。本文定义实现验收阶段的范围选择、确定性验证、Bootstrap 路由、分段执行恢复和最终验收行为，目标是在不削弱 authority、完整性和 fail-closed 语义的前提下，消除大目录全量审查、重复模型消费和无界传输重试。

具体 schema、canonical hash payload、路径投影、进程事件实现和 mutation test 设计记录在 [addendum.md](addendum.md)，不作为本文的实现技术选择。

## 1. 背景与问题

2026-08-13 VDD Conformance Exact Cover 需求的语义评审暴露了当前验收链路的结构性成本问题：一个约 1.37 MB、89 个 artifact 的 review closure 被切分为 101 个 segment，并由 Blind Hunter、Edge Case Hunter 和 Acceptance Auditor 三个角色分别消费，理论上需要约 303 次模型 attempt。此前两个候选 run 还分别冻结了 389 个和 125 个 artifact。

当前运行证据同时显示以下问题：

- Acceptance 没有在进入 Bootstrap 前充分收敛 changed-set、consumer closure 和 deterministic route；
- whole-directory scope 在协议允许的情况下被当成默认安全选项，导致 review closure 远大于真实语义边界；
- reviewer 在已分配 segment 之外继续读取完整文件，放大 token、时间和身份不一致风险；
- segment assignment、child receipt 与 parent validation 之间出现 payload mismatch；
- 外层 job 退出后，子 attempt/lease 仍可能残留，重试随后被 write-set overlap 拒绝；
- executable identity 需要操作员重新填写，可能与 access proof 漂移；
- high-cost acknowledgement 允许继续执行，但没有强制触发缩小闭包或改变路由的决策。

这不是“模型速度慢”或“FastCtx 分页慢”的单一问题，而是验收范围、路由 authority 和 Bootstrap 控制面执行缺陷共同造成的问题。

## 2. 愿景

Ji Mu Yun 的实现验收应以当前机器证据为主、模型语义审查为按需能力。Acceptance 应从精确基线和完整 changed-set 建立最小完整 consumer closure，先执行当前 implementation contract 投影的 deterministic required checks，再依据 typed risk policy 决定是否需要 Bootstrap。

普通确定性失败不应启动 reviewer。需要 Bootstrap 时，Bootstrap 仍保持三角色完整审查的既有 authority 语义，但只消费同一个冻结、紧凑、不可截断的 closure。分段 child 只能访问控制器分配的 segment，失败必须有界恢复，所有完成和重试均由 process events、lease reconciliation 和 receipt fold 建立机器证据。

## 3. 产品原则

1. **Acceptance 拥有范围与路由决策。** Acceptance 决定 deterministic-only、focused repair、full Bootstrap 或 manual pause；Bootstrap 不自行决定是否应被调用。
2. **Bootstrap complete review 语义不变。** full Bootstrap 继续要求 Blind Hunter、Edge Case Hunter 和 Acceptance Auditor 三个隔离角色。
3. **Diff-first，不是 diff-only。** Git changed-set 是范围入口，但必须扩展到当前合同、validator、入口和 repository authority 构成的最小完整 consumer closure。
4. **机器先验。** 机器能够确定的 hash、schema、命令结果、授权和 terminal 状态必须先验证，不交给模型重复推断。
5. **计划投影，不硬编码业务命令。** Bootstrap 只执行 Acceptance/implementation contract 投影的 required checks，不直接认识 source-freeze、exact-cover 或任何具体计划命令。
6. **选定闭包完整读取。** 缩小范围不得变成 sampling；选中的 authority 必须完整读取，或由控制器产生 hash-bound range projection。
7. **Segment 强隔离。** child 只处理 parent-assigned segment，不能通过 prompt 自律替代控制面约束。
8. **身份自动继承。** snapshot path、executable identity、model route 和 segment identity 均由已验证 authority 投影，不由操作员重填。
9. **失败与停滞有界。** transport failure 只重试失败 segment，达到 family-specific 上限后产生 typed failure；无人值守 run 超过 policy-defined no-progress window 时必须停止新增模型调用并进入 typed recovery，不以 heartbeat 或重复输出续命。
10. **完成不由模型声明。** Acceptance finalization 必须来自 implementation-complete 前置、deterministic evidence、必要的 Bootstrap 结果和当前 receipt/hash 闭合。

## 4. 目标用户与工作

### 4.1 目标用户

- **Acceptance 维护者**：需要以可重放方式决定某次实现是否只需 deterministic 验收，或必须升级 Bootstrap。
- **Bootstrap Review 维护者**：需要在不改变三角色语义的情况下，降低 closure 和 segment 成本，并保证 transport recovery 正确。
- **VDD/Quick Dev 维护者**：需要产生可供 Acceptance 消费的 implementation-complete、changed-set identity 和 implementation evidence。
- **计划维护者**：需要通过 implementation contract 和 command registry 声明 required checks，而不是依赖 Bootstrap 内置业务知识。

### 4.2 核心工作流程

- **UJ-1：维护者验收普通实现。** 林维护者收到 Quick Dev 的 implementation-complete，Acceptance 冻结 baseline/current、建立 changed-set 和最小 consumer closure，重放 required checks；检查全部通过且 typed policy 选择 deterministic-only，流程不启动任何 Bootstrap reviewer，直接进入 Acceptance 后续闭合。
- **UJ-2：维护者验收高风险实现。** 周维护者收到涉及共享入口或 lifecycle authority 的实现；deterministic evidence 通过后，Acceptance 选择 full implementation conformance。Bootstrap 对同一 frozen compact closure 执行三个隔离角色；只有 gate 接受 P0/P1 时才运行 independent verifier，结果返回 Acceptance 完成最终裁决。
- **UJ-3：维护者恢复失败或停滞 segment。** 陈维护者观察到一个 segment transport failure，或控制器发现 run 已超过 no-progress window；控制器自动确认 child 终态、追加 process event、回收 lease，并仅在 policy 允许时重试同一 immutable segment。达到 retry 或 no-progress 上限时流程产生 typed failure 和恢复入口，不继续启动相同 attempt。

## 5. 术语表

- **Acceptance**：消费 implementation-complete 和当前实现证据、拥有验收范围与 Bootstrap 路由决策、发布最终验收结果的控制面能力。
- **Bootstrap Review**：按 profile 对冻结 review closure 执行多角色语义审查、gate 和必要 verifier 的控制面能力。
- **Complete Review**：包含 profile 要求的全部隔离 discovery roles 的正式 Bootstrap review；本产品不改变其三角色定义。
- **Changed-set Manifest**：绑定精确 baseline/current identity，并覆盖修改、新增、删除、重命名和适用未跟踪文件的机器清单。
- **Consumer Closure**：一个验收消费者正确判断当前实现所需的最小完整 authority、实现、依赖和证据集合。
- **Required Check**：由当前 implementation contract/command registry 投影、由 Acceptance 或 Bootstrap deterministic preflight 重放的固定机器检查。
- **Range Projection**：由控制器从完整 authority 中生成的 hash-bound inclusive byte/line 范围；不是 reviewer 自行截取的摘要。
- **Segment Descriptor**：不可变地描述一个 reviewer segment 的 artifact identity、范围、顺序、role 和 payload identity 的控制器工件。
- **Segment-only Snapshot**：只包含一个已分配 segment 内容的 child 可读快照。
- **Process Event**：记录 attempt reservation、start、liveness heartbeat、effective progress、terminal、stale 和 retry 事实的 append-only authority。
- **Effective Progress Event**：由控制器验证并绑定当前 identity 的 segment/phase terminal、有效 evidence/receipt 增量或 policy 注册状态迁移；stdout、重复状态文本和单纯 heartbeat 不属于有效进展。
- **Lease Reconciliation**：根据 process event 和进程身份确认 attempt 是否仍存活，并重建 write-set ownership 的控制面动作。
- **Implementation-complete**：由 Quick Dev/VDD 实现流程产生、作为 Acceptance 入口前置的实现完成 handoff；Bootstrap 不产生该状态。

## 6. 功能需求

### 6.1 Acceptance 范围与生命周期

#### FR-1：消费正式 implementation-complete

Acceptance 必须只在收到 schema-valid、identity-bound 的 implementation-complete handoff 后进入实现验收。

**可验证结果：**

- 缺失、过期或与当前 candidate identity 不一致的 handoff 必须阻止验收启动；
- Bootstrap 输出不能被接受为 implementation-complete 的替代品；
- lifecycle 顺序固定为 Quick Dev/VDD implementation-complete → Acceptance → optional Bootstrap → Acceptance finalization。

#### FR-2：冻结精确 baseline/current identity

Acceptance 必须冻结不可移动的 baseline commit identity 和当前 candidate identity。

**可验证结果：**

- durable evidence 不得使用未解析的 `HEAD` 作为 baseline；
- candidate 发生变化后，旧 changed-set、closure、required-check result 和 review receipt 必须 stale；
- identity 不一致时不得复用旧 Bootstrap run。

#### FR-3：生成完整 Changed-set Manifest

Acceptance 必须覆盖修改、新增、删除、重命名和适用未跟踪实现文件，并记录每项与 baseline/current 的关系。

**可验证结果：**

- 普通 Git diff 未显示的未跟踪文件和删除状态仍被清单表达；
- changed-set 可以被独立重算；
- 清单不把历史 logs 或无关工作区状态自动纳入实现范围。

#### FR-4：生成最小完整 Consumer Closure

Acceptance 必须从 Changed-set Manifest 扩展到当前消费者正确验收所需的直接合同、入口、validator、authorization prerequisite 和 repository authority。

**可验证结果：**

- closure 对每个纳入 artifact 提供 inclusion reason；
- closure roots 必须由冻结 Changed-set Manifest、implementation contract、requirement/acceptance bindings、适用 repository authority、authorization prerequisites 和外部 selection authority 共同确定；
- dependency expansion 必须沿版本化 typed edge classes 计算至固定点，不能由调用者声明“已经完整”；
- 每个候选排除项必须提供可机器复算的 non-applicability/disposition、来源 identity 和决定 authority；
- completeness receipt 必须绑定 roots、edge policy、固定点结果、纳入项、排除项和 closure identity；
- closure omission、错误 exclusion 或缺失 edge 会被独立 omission fixtures 稳定拒绝；
- whole-plan directory 只有在被证明为最小完整 closure 时才可使用；
- closure 缩减不能以 sampling 或丢弃反例条件实现。

#### FR-5：投影 Deterministic Required Checks

Acceptance 必须从当前 implementation contract 和 command registry 取得 required-check set。

**可验证结果：**

- Bootstrap 不包含 8-13 或其他计划专属命令名称；
- registry/contract 变化会使旧 required-check projection stale；
- 每个 required check 绑定固定 executable、argv、cwd、依赖、acceptance IDs 和结果 identity。

#### FR-6：执行 typed decide-bootstrap

在 deterministic closure 完成后，Acceptance 必须发布 typed route decision。

**可验证结果：**

- 至少支持 `deterministic_only`、`focused_repair_verification`、`full_implementation_conformance` 和 `manual_pause`；
- deterministic failure 默认进入 typed repair，且 reviewer call 数为零；
- route eligibility 必须先由 authority/risk policy 计算允许集合，再由 Acceptance 在允许集合内选择；
- 涉及共享入口、authority/lifecycle control、protected path、requirements identity 变化、控制面 self-hosting、未消除的 semantic ambiguity，或 policy 注册的其他高风险边界时，必须选择 `full_implementation_conformance` 或 `manual_pause`；
- 仅当 deterministic closure 通过、没有 mandatory Bootstrap trigger、没有 semantic ambiguity 且 policy 明确允许时，才可选择 `deterministic_only`；
- `focused_repair_verification` 只适用于已存在正式 predecessor findings、Acceptance-owned repair route 和完整 repair projection 的 bounded verification；它不能替代首次 Complete Review，也不能发现或升级新 blocker；
- full implementation conformance 必须携带 frozen Consumer Closure 和 required-check evidence；
- route decision 不得由 Bootstrap 自行提升或修改。

### 6.2 Bootstrap Authority 保持

#### FR-7：保持 Complete Review 三角色

当 Acceptance 选择 full implementation conformance 时，Bootstrap 必须执行 profile 要求的全部隔离 discovery roles。

**可验证结果：**

- Blind Hunter、Edge Case Hunter 和 Acceptance Auditor 的候选在 gate 前不互相共享；
- 缺少任一 required role 时不能形成 Complete Review；
- Bootstrap implementation conformance 必须按现有 profile 对同一 frozen candidate/closure 重放每个 plan-mandated required check，或依据正式复用合同独立验证可复用结果的 command identity、输入、输出、时效和完整性；
- 未重放、未验证或仅由上游声明 `passed` 的 required-check 状态不能进入 semantic reviewer launch；
- 本产品不得通过默认单 reviewer 静默改变 Bootstrap authority semantics。

#### FR-8：三个角色消费同一 Frozen Consumer Closure

Bootstrap 必须让三个角色基于同一 closure identity、authority identity 和 deterministic evidence 进行审查。

**可验证结果：**

- role 之间不能使用不同版本的 authority；
- closure 变化会使全部未完成和已完成 role output stale；
- reviewer 不读取 live repository 原件。

#### FR-9：按 gate 结果启动 Independent Verifier

只有 gate 接受 P0/P1 时才启动 independent verifier，并按现有 risk/model policy 选择 route。

**可验证结果：**

- 零 accepted P0/P1 时 verifier call 数为零；
- verifier 覆盖每个 accepted blocker 的 exact evidence 和 context reads；
- verifier 结果返回 Acceptance，而不是直接发布最终验收状态。

### 6.3 Authority 投影与完整读取

#### FR-10：小型 Authority 完整传输

对符合当前 model-visible budget 的 normative authority，控制器必须传输完整文件。

**可验证结果：**

- FastCtx 或等价文件工具返回 `Partial` 时必须按指定 offset 续传至 `Complete`；
- 截断输入不能进入 reviewer launch；
- reviewer 不能用摘要替代选定的完整 authority。

#### FR-11：大型 Authority 使用 Range Projection

超出当前 model-visible budget 的 authority 必须由 parent builder 生成 Range Projection。

**可验证结果：**

- projection 绑定 source path、完整 source hash、inclusive range、extracted bytes hash 和 inclusion reason；
- reviewer 不能自行声明截取范围；
- mutation 任一范围、源 hash 或内容字节时，projection validation 必须失败；
- projection 不能省略适用于当前 changed-set 的反例、约束或例外条件。

### 6.4 Segment 控制面 Hardening

#### FR-12：统一 Segment Payload Identity

assignment、prompt request、child receipt 和 parent validation 必须基于同一个 canonical Segment Descriptor identity。

**可验证结果：**

- path、offset、range、artifact hash、role、order 或 payload 任一变化都会产生不同 identity；
- 同义但非 canonical 的序列化不能生成第二种有效 identity；
- parent 不维护独立、漂移的 segment hash 算法。

#### FR-13：提供 Segment-only Snapshot

每个 child attempt 只能读取其被分配的 segment 内容和最小 parent validation attestation。

**可验证结果：**

- child workspace 不包含可遍历的完整 Artifact View；
- 越界路径读取稳定失败并留下诊断证据；
- reviewer 输出不能声明未分配范围的 coverage；
- 同一个 segment 在 retry 时保持相同 descriptor identity。

#### FR-14：投影绝对 Snapshot Path

控制器必须向 child 提供唯一、绝对、已验证的 snapshot path。

**可验证结果：**

- child 不需要猜测 run directory 与 attempt directory 的相对关系；
- path 不存在或指向非冻结 bytes 时在 semantic work 前失败；
- 相对路径尝试不能成为有效 receipt 的读取来源。

#### FR-15：继承 Access-proof Executable Identity

每个 run-layer 和 retry 必须自动继承 access proof/launch authorization 中的 executable、model、reasoning 和 environment identity。

**可验证结果：**

- 操作员不需要重新输入 `codex` 或绝对 executable path；
- 人工覆盖导致 identity 漂移时在 child launch 前失败；
- fallback model 仍需独立、显式、identity-bound authorization。

#### FR-16：自动完成 Progress Watchdog、Attempt Terminal 与 Lease Reconciliation

控制器必须把 child liveness、有效进展、no-progress watchdog、process 终态、attempt terminal event、lease rebuild 和 retry eligibility 组成单一可恢复流程。

**可验证结果：**

- heartbeat 只证明进程 liveness，不能刷新 no-progress window；
- 只有绑定当前 candidate、closure、segment 和 attempt identity 的 Effective Progress Event 才能刷新 no-progress window；
- stdout、重复状态文本、轮询日志或用户可见打印不能被接受为有效进展；
- 超过 policy-defined no-progress ceiling 后，控制器停止新增 reviewer/model call，终止或隔离活动 attempt，追加 failed/stale terminal event，完成 lease reconciliation，并产生 typed blocked/recovery result；
- 外层 job 退出后不存在长期占用 write-set 的孤立 acquired lease；
- dead/reused PID 会先追加 stale/failed event，再重建 lease view；
- retry 不会因为未回收的自身前序 attempt 产生 write-set overlap；
- 人工编辑 lease sidecar 不能改变 authority。

#### FR-17：执行有界 Segment Retry

transport failure 必须只重试失败 segment，并使用当前 policy 定义的 family-specific retry ceiling。

**可验证结果：**

- 已验证 segment 不被重新执行；
- 相同失败达到上限后生成 typed blocked/recovery result；
- retry 不创建新 semantic round 或新 lineage family；
- context-budget failure 必须重新分区，不能用不变输入重复执行。

### 6.5 成本治理与验收闭合

#### FR-18：在模型启动前发布 Review Cost Decision

控制器必须根据 closure、segment plan、required roles 和 route 计算模型调用与上下文成本，并由 Acceptance 在 authority/risk policy 已允许的 route 集合内决定继续、重建 closure、重新分区或 manual pause。

**可验证结果：**

- cost estimate 同时显示 closure bytes、segment count、required attempts 和 retry exposure；
- high-cost acknowledgement 不能替代 closure/routing decision；
- 成本不能把 policy-required 的 `full_implementation_conformance` 降级为 `deterministic_only` 或 `focused_repair_verification`；
- mandatory Bootstrap 的高成本只能触发 closure completeness 重建与重新验证、segment repartition、manual pause，或由正式 policy authority 发布的显式 override；
- whole-plan scope 必须显示相对于 minimal closure candidate 的成本差异；
- route decision 与实际 launch plan hash-bound。

#### FR-19：Acceptance 导入 Bootstrap 结果

Bootstrap 完成后，Acceptance 必须验证 frozen closure、required checks、gate、verifier 和 receipt identity，再决定最终验收状态。

**可验证结果：**

- Bootstrap 不能直接发布 implementation-complete 或 Acceptance final；
- stale、不同 closure 或不同 candidate identity 的 run 不能被导入；
- finalization 能通过当前 repository 和 evidence 独立重放；
- assistant 文本不能替代任何 final evidence。

#### FR-20：提供 8-13 规模回归场景

系统必须提供接近 2026-08-13 VDD Conformance Exact Cover 规模和风险边界的回归场景。

**可验证结果：**

- deterministic failure 路径产生零 reviewer call；
- Bootstrap-required 路径保持三角色完整 coverage；
- 无越界读取、无遗留 lease、无人工 executable 重填；
- payload mismatch 在 retry ceiling 内终止并产生可诊断证据；
- compact closure 相对 whole-plan closure 有可量化缩减；
- 模型 attempt 数不超过 `required roles × segment count + authorized bounded retries`；
- frozen semantic regression corpus 中每个 mandatory P0/P1、semantic ambiguity 和 false-authorizing mutation 都产生预期的非授权结果类别；不得要求 finding 文本逐字一致。

## 7. 非功能需求

### NFR-1：确定性

相同 baseline/current、Changed-set Manifest、Consumer Closure、required-check results 和 policy 输入必须产生相同 route、segment identities 和可验证结果。

### NFR-2：Fail-closed

任何 authority、hash、range、receipt、process identity、authorization 或 closure 完整性无法确认时，系统必须停止在 typed non-authorizing 状态。

### NFR-3：可恢复性

控制器或 child 中断后，维护者必须能仅凭 process events、immutable descriptors 和当前进程身份恢复，不依赖聊天历史或人工重建 lease。

### NFR-4：可观测性与无人值守状态输出

每次验收必须能够回答：为什么纳入该 artifact、为什么选择该 route、启动了多少模型 attempt、哪些失败被重试、当前谁拥有 write-set、最后一次 Effective Progress Event 是什么、最终依据是什么。用户可见状态更新必须由阶段变化、新 evidence、retry、typed warning 或异常驱动，并进行去重和节流；内部 heartbeat/轮询日志不得作为用户可见进展、不得刷新 no-progress window，也不得通过连续打印制造仍在推进或已经完成的印象。

### NFR-5：成本可控

系统必须在启动前暴露估计成本，并在完成后记录实际 closure、segment、attempt、retry、token 和 wall-time 指标。成本优化不能削弱 authority coverage。

### NFR-6：兼容性

现有 Bootstrap Complete Review、requiredLayers、gate、independent verifier 和 historical evidence 语义保持兼容；策略升级不得重写历史 run。

### NFR-7：单维护者操作安全

正常恢复和 retry 不应要求维护者手工填写 executable identity、编辑 lease、复制 receipt 或判断 PID 是否仍有效。

## 8. 非目标

- 不把 Bootstrap Complete Review 从三角色改成单 reviewer；
- 不在 Bootstrap 内硬编码 8-13、source-freeze、exact-cover 或其他计划专属命令；
- 不以 Git diff 作为唯一验收 authority；
- 不通过 sampling、自由摘要或 reviewer 自选片段缩小 normative authority；
- 不允许 Bootstrap 产生 implementation-complete；
- 不重写、删除或伪装此前失败的 `vcec-r1`、`vcec-r1m`、`vcec-r1n` evidence；
- 不通过无限提高 snapshot 或模型上下文上限解决错误 closure；
- 不改变 maintainer authorization owner 的既有发布 authority；
- 不在本 PRD 决定 canonical JSON 算法、具体 schema 字段或 retry 次数。

## 9. MVP 范围

### 9.1 纳入 MVP

- Acceptance-owned baseline/current 与 Changed-set Manifest；
- diff-first minimal complete Consumer Closure builder；
- contract/registry-driven required-check projection；
- typed decide-bootstrap 路由；
- Bootstrap 三角色对 compact closure 的完整消费；
- controller-owned Range Projection；
- canonical Segment Descriptor 与 payload identity；
- Segment-only Snapshot 和绝对路径投影；
- access-proof executable identity 自动继承；
- Effective Progress Event、no-progress watchdog、事件驱动状态输出、terminal event + automatic lease reconciliation；
- bounded retry 和 typed recovery result；
- 8-13 规模的策略、故障和成本回归场景；
- Acceptance 导入 Bootstrap evidence 并最终闭合。

### 9.2 MVP 不包含

- 新的单 reviewer authorizing review profile；
- 修改 Bootstrap ADR 中 Complete Review 的三角色定义；
- 对 Phase 服务层或用户沙箱层的模型验收策略改造；
- 自动调整模型价格、模型供应商或全局 token 配额；
- 将历史 Bootstrap run 迁移为新 schema；
- 把所有 repository review 工作流统一到本产品。

## 10. 成功指标

### 10.1 主要指标

- **SM-1：确定性失败零模型调用。** 所有在 required-check replay 阶段失败的回归场景，Bootstrap reviewer call 数必须为 0。验证 FR-5、FR-6、FR-20。
- **SM-2：Closure 显著收敛。** [ASSUMPTION：在 8-13 规模回归中，Consumer Closure bytes 与 segment count 相对 whole-plan baseline 的 provisional target 为至少减少 75%；正式阈值由 Acceptance/Bootstrap policy owner 在 M2 基线数据形成后 ratify。] 无论阈值是否冻结，authority completeness validator 必须通过。验证 FR-4、FR-10、FR-11、FR-20。
- **SM-3：模型 attempt 有界。** Bootstrap-required 场景的模型 attempt 数不得超过 `3 × segment count + policy-authorized retries + required verifier attempts`。验证 FR-7、FR-9、FR-17、FR-20。
- **SM-4：控制面无人工恢复。** 回归场景中不存在人工 executable 重填、人工 lease 编辑或人工 receipt 修补。验证 FR-15、FR-16、FR-19。
- **SM-5：四小时基线显著改善。** [ASSUMPTION：在外部模型服务正常且无需 independent verifier 时，8-13 规模的 full Bootstrap 端到端 wall time 应低于 60 分钟。] 验证 FR-18、FR-20。

### 10.2 质量指标

- **SM-6：Segment 越界读取为零。** 所有 mutation 和 integration 场景均不能读取或声明未分配 coverage。验证 FR-12、FR-13、FR-14。
- **SM-7：Lease 遗留为零。** 每个 terminal child 最终都对应 terminal/stale process event，且不存在超过 reconciliation window 的 acquired lease。验证 FR-16。
- **SM-8：Identity mutation 全拒绝。** path、range、order、artifact hash、role、executable 或 candidate identity 任一改变均导致稳定拒绝。验证 FR-2、FR-11、FR-12、FR-15。
- **SM-9：Bootstrap authority 无回归。** Bootstrap-required 场景仍完成三角色完整 coverage；accepted P0/P1 仍要求 independent verifier。验证 FR-7、FR-8、FR-9。
- **SM-10：语义检出能力不退化。** 对 frozen、owner-labeled 的高风险缺陷与歧义 corpus，在 policy-defined stability sample set 中，compact closure 必须对每个 mandatory P0/P1 或 semantic ambiguity 产生预期的非授权结果类别，且不能产生 reference baseline 未允许的 false authorizing outcome。验证 FR-4、FR-7、FR-8、FR-11、FR-20。
- **SM-11：无人值守停滞有界。** 在 no-progress fixture 中，重复 heartbeat、轮询输出和用户可见状态文本均不能刷新窗口；超过 policy ceiling 后不得启动新模型调用，并必须在 policy grace window 内形成 terminal process event、完成 lease reconciliation 和 typed blocked/recovery result。验证 FR-16、NFR-3、NFR-4。

### 10.3 反指标

- **SM-C1：不得以降低 coverage 换取速度。** Closure 缩减后，适用 authority omission 数必须为 0。制衡 SM-2、SM-5。
- **SM-C2：不得增加假 GREEN。** 新路由不得允许未执行 required checks、未授权或 receipt 不一致的实现进入 Acceptance final。制衡 SM-1、SM-4。
- **SM-C3：不得把 transport failure 当语义结论。** Payload mismatch、timeout 和 stale lease 不得生成 finding、gate verdict 或完成状态。制衡 SM-3、SM-7。
- **SM-C4：不得把活动信号伪装成有效进展。** Heartbeat、重复打印和轮询日志不得延长 no-progress window、阻止 stop-loss 或形成完成证据。制衡 SM-5、SM-11。

## 11. 风险与缓解

- **最小闭包遗漏 authority。** 通过 inclusion reason、dependency expansion、repository authority validation 和 omission mutation tests 缓解。
- **Range Projection 切掉反例。** 小文件默认整文件；大文件 projection 由 controller 生成并绑定完整源 hash、范围和 inclusion reason。
- **成本阈值被实现者冻结为架构常量。** PRD 只定义目标和可测结果；具体 threshold 由 Architecture/Policy ratify，并可版本化演进。
- **自动 lease recovery 误杀活进程。** 必须同时验证 PID 与 process creation identity，并保留 append-only process event。
- **No-progress watchdog 误判安静但有效的模型调用。** 不以 stdout silence 单独判定停滞；窗口由 controller-observed、identity-bound Effective Progress Event 刷新，并保留可版本化 policy 与 grace window。
- **Acceptance 与 Bootstrap authority 漂移。** route、closure 和 imported result 使用同一 candidate/closure identity，Bootstrap 不拥有 finalization。
- **紧凑 closure 仍因单文件过大产生高成本。** 使用 controller-owned Range Projection，而不是扩大整个 snapshot 上限。
- **紧凑 closure 通过边界测试但语义检出退化。** 使用 owner-labeled semantic regression corpus、非授权结果类别和 stability sample set 验证 detection parity，不比较自然语言 finding 的逐字一致性。

## 12. 依赖与所有权

- **Acceptance owner**：Changed-set Manifest、Consumer Closure、required-check projection、decide-bootstrap、Bootstrap import 和 finalization。
- **Quick Dev/VDD owner**：implementation-complete、实现 evidence 和 candidate identity 的生产。
- **Bootstrap Review owner**：Complete Review 三角色、Segment Descriptor、child isolation、gate、verifier、Process Event 生产、Effective Progress Event 验证、no-progress watchdog 执行、用户可见状态事件去重/节流、lease reconciliation 和 retry recovery。
- **Bootstrap control-plane policy owner**：版本化 no-progress ceiling、terminal grace window、状态输出 throttle policy 及其 ratification；运行控制器只能执行当前已发布 policy，不能自行放宽。
- **Plan owner**：implementation contract、command registry 和 plan-specific required checks。
- **Authorization owner**：implementation-authorized 等既有授权状态；本产品不夺取该 authority。
- **Shared file/model tooling owner**：完整读取、Partial 续传和 model-visible output contract。

## 13. 发布阶段

### M0：控制面故障闭合

- 修复 canonical segment identity、segment-only snapshot、绝对路径、executable 继承、no-progress watchdog 和 lease reconciliation；
- 建立 payload mismatch、越界读取、PID stale、heartbeat-without-progress、repeated-output-without-progress 和 write-set overlap 回归；
- 保留现有失败 run 作为不可变回归输入。

### M1：Acceptance 策略接入

- 建立 Changed-set Manifest、Consumer Closure、required-check projection 和 typed decide-bootstrap；
- deterministic failure 验证零 reviewer call；
- 证明 Bootstrap Complete Review 语义未改变。

### M2：规模与验收闭合

- 运行 8-13 规模回归；
- 记录 closure、segment、attempt、retry、token 和 wall-time；
- Acceptance 成功导入 compact Bootstrap evidence 并完成 finalization；
- 达到主要指标与反指标后再替代旧的 whole-directory 默认策略。

## 14. 开放问题

1. 8-13 规模 full Bootstrap 的正式 wall-time 目标是否采用 60 分钟，还是以相对四小时基线的百分比为唯一指标？**Owner：Acceptance/Bootstrap policy owner；revisit：M2 首次稳定基线完成后；不阻塞 M0/M1。**
2. Closure 显著收敛的正式阈值是否采用 provisional 75%，或由 cost policy 根据 workload bucket 动态计算？**Owner：Acceptance/Bootstrap policy owner；revisit：M2 基线与 completeness corpus 同时通过后；不阻塞 M0/M1。**
3. Range Projection 的预算应完全沿用现有 model-visible contract，还是需要单独的 Acceptance closure budget policy？**Owner：Architecture；revisit：Range Projection 合同设计时；阻塞 M1 完成。**
4. [ASSUMPTION：无人值守 no-progress watchdog 的初始窗口为 60 分钟；只有 Effective Progress Event 能刷新窗口，stdout silence 本身不构成停滞证明。] 正式 no-progress ceiling、terminal grace window 与 lease reconciliation window 应共用一个 policy family，还是分别版本化？**Owner：Bootstrap control-plane policy owner；revisit：M0 execution policy ratification；阻塞 M0 完成。**
5. 当前失败的 `vcec-r1n` 应标记为哪一种正式非授权终态，才能同时保留回归价值并避免被误用？**Owner：Bootstrap lineage owner；revisit：M0 historical evidence handling；阻塞新策略正式回归。**

## 15. 假设索引

- §10.1 SM-2：假设 8-13 规模 Consumer Closure 的 provisional reduction target 为至少 75%，等待 M2 基线后 ratify。
- §10.1 SM-5：假设外部模型服务正常且无需 independent verifier 时，8-13 规模 full Bootstrap 应在 60 分钟内完成。
- §14 开放问题 4：假设无人值守 no-progress watchdog 初始窗口为 60 分钟，仅由 Effective Progress Event 刷新，等待 M0 policy ratification。
