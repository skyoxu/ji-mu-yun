# Authority 与生命周期合同

## 1. Authority 所有权

| Owner | 唯一职责 |
| --- | --- |
| Acceptance owner | baseline/current freeze、Changed-set Manifest、Consumer Closure、required-check projection、typed route、Bootstrap import、`acceptance-passed` |
| Quick Dev / quick-dev-tdd-adapter owner | `implementation-complete`、candidate identity、实现 evidence |
| VDD owner | `draft`、`plan-ready` 与 plan candidate identity |
| Maintainer | `implementation-authorized`；发布 non-authorizing supervised semantic-review decision |
| Bootstrap Review owner | Complete Review 三角色、Segment Descriptor、child isolation、gate、verifier、Process Event、Effective Progress 验证、watchdog enforcement、状态事件、lease/retry recovery |
| Bootstrap control-plane policy owner | no-progress ceiling、terminal grace、status throttle policy 的版本化与 ratification |
| Plan owner | implementation contract、command registry、plan-specific required checks |
| Shared file/model tooling owner | 完整读取、`Partial` 续传和 model-visible output contract |

任何消费者不得代替其他 owner 发布其生命周期状态。

## 2. Canonical 生命周期

1. VDD 发布 identity-bound `draft`，并在 plan contract 完整后发布 `plan-ready`。
2. Maintainer 在独立验证授权前置后发布 `implementation-authorized`。
3. Quick Dev / quick-dev-tdd-adapter 发布 schema-valid、identity-bound `implementation-complete`。
4. Acceptance 冻结不可移动的 baseline commit identity 与 candidate identity。
5. Acceptance 构建 Changed-set Manifest 和 Consumer Closure。
6. Acceptance 投影并执行 deterministic required checks。
7. Acceptance 发布 identity-bound `acceptance_mode`（`supervised` 或 `unattended`）与 typed route。
8. Acceptance 执行固定 mode × route 矩阵：`supervised + deterministic_only + no trigger` 消费 current maintainer decision 且不运行 Bootstrap；`unattended + deterministic_only` 不运行 Bootstrap；任意 mode 的 `focused_repair_verification` 或 `full_implementation_conformance` 运行 Bootstrap；任意 mode 的 `manual_pause` 停止且不授权。
9. 任一 registered Bootstrap trigger 必须先把 route 至少升级为 `full_implementation_conformance` 或 `manual_pause`。需要 Bootstrap 时，Bootstrap 返回 identity-bound evidence；合法 supervised fast-path 只消费 current maintainer decision，不消费网页聊天文本。
10. Acceptance 验证 mode、route 与所需 evidence，发布 `acceptance-passed`。

Bootstrap 不能产生 `draft`、`plan-ready`、`implementation-authorized`、`implementation-complete` 或 `acceptance-passed`。

## 3. Implementation-complete 与 identity freeze

- 缺失、过期或 candidate mismatch 的 handoff 阻止 Acceptance 启动。
- Durable baseline 必须记录解析后的 commit identity，不能记录移动的 `HEAD`。
- Candidate 变化使 changed-set、closure、check result、route、segment、review receipt 和 imported result stale。
- Closure、required-check projection、route policy 或 authority identity 变化使所有依赖它们的未完成及已完成 role output stale。
- 旧 Bootstrap run 只有在正式 reuse contract 独立验证全部输入、命令、输出、时效和完整性时才可复用。

## 4. Changed-set Manifest

Manifest 必须：

- 表达修改、新增、删除、重命名和适用未跟踪实现文件；
- 记录每项与 baseline/current 的关系；
- 可由独立消费者重新计算；
- 不因目录邻接自动纳入历史 logs 或无关工作区状态。

## 5. Consumer Closure

Closure roots 必须来自：

- frozen Changed-set Manifest；
- implementation contract 和 requirement/acceptance bindings；
- 当前 validator、入口与 consumer；
- 适用 repository authority；
- authorization prerequisites；
- 外部 selection authority。

Dependency expansion 必须沿版本化 typed edge classes 计算到 fixed point。每个纳入项有 inclusion reason；每个排除项有可机器复算的 non-applicability/disposition、来源 identity 和 decision authority。Completeness receipt 绑定 roots、edge policy、fixed-point result、纳入项、排除项和 closure identity。Whole plan directory 只有在它被证明为最小完整 closure 时才合法。

## 6. Deterministic Required Checks

- Required-check set 只从当前 implementation contract 和 command registry 投影。
- 每个 check 绑定固定 executable、argv、cwd、依赖、acceptance IDs、输入和结果 identity。
- Bootstrap 不认识计划专属命令名。
- Bootstrap semantic launch 前必须重放每个 required check，或按正式 reuse contract 独立验证其 command identity、输入、输出、时效和完整性。
- 仅由上游声明 `passed` 的状态不构成 evidence。

## 7. Typed Route

Route 至少支持：

- `deterministic_only`
- `focused_repair_verification`
- `full_implementation_conformance`
- `manual_pause`

Authority/risk policy 先计算允许集合，Acceptance 再选择。共享入口、authority/lifecycle control、protected path、requirements identity 变化、控制面 self-hosting、未消除 semantic ambiguity 或其他注册高风险边界必须选择 full conformance 或 manual pause。

`focused_repair_verification` 只适用于已有正式 predecessor findings、Acceptance-owned repair route 和完整 repair projection；它不能替代首次 Complete Review，也不能发现或升级新 blocker。

`acceptance_mode` 是 route 的正交维度：

- `supervised`：maintainer 正在主动监督，并发布 schema-valid、绑定当前 candidate、`decision=semantic_review_satisfied`、`owner=maintainer`、`authorizes=[]` 的 decision artifact。Web Sol 等网页模型仅提供 advisory input；其文本、截图、布尔值或模型 verdict 不进入 Acceptance authority。
- `unattended`：没有 maintainer 实时监督，required Bootstrap route 必须通过 durable Bootstrap protocol、隔离角色、retry/lease/recovery 和 finalized evidence 闭合。

Mode 不改变 route 的确定语义。合法矩阵是：`supervised + deterministic_only + no trigger` 使用 maintainer decision 且不运行 Bootstrap；`unattended + deterministic_only` 不运行 Bootstrap；任意 mode 的 `focused_repair_verification` 与 `full_implementation_conformance` 均运行 Bootstrap；任意 mode 的 `manual_pause` 停止且不授权。Maintainer 或用户主动要求、尚未消除的 advisory high-risk suspicion、security/permission/data-corruption risk、lifecycle/authority control 修改或独立多角色 adversarial review 请求均为 registered trigger，必须将 route 至少升级为 `full_implementation_conformance` 或 `manual_pause`。本项目修改 Acceptance/Bootstrap authority control，因此其自身最终验收仍触发 Bootstrap。

## 8. Bootstrap Complete Review

- Blind Hunter、Edge Case Hunter、Acceptance Auditor 在 gate 前彼此隔离。
- 现有 profile 的 `requiredLayers` 及其 gate 语义必须保持兼容；禁止新增 single-reviewer authorizing profile。
- 三个角色消费同一 candidate、closure、authority 和 deterministic evidence identity。
- Closure 或其 authority identity 变化会使全部未完成和已完成 role output stale。
- 任一 required role 缺失时不能形成 Complete Review。
- Reviewer 不读取 live repository 原件。
- 只有 gate 接受 P0/P1 时启动 independent verifier；零 accepted P0/P1 时 verifier call 为零。
- Independent verifier route 继续遵循现有 risk/model policy，Acceptance 和 Bootstrap 不得为节省成本自行改写。
- Verifier 覆盖每个 accepted blocker 的 exact evidence 和 context reads。
- Gate/verifier 结果返回 Acceptance，不直接发布最终状态。

## 9. Acceptance-passed

Acceptance 只有在 candidate、closure、required checks、mode、route 以及该 route 所需的 evidence 全部闭合时才能发布 `acceptance-passed`。Bootstrap-required 路径必须闭合 gate、必要 verifier 和 receipt；合法 supervised fast-path 必须闭合 current maintainer decision，且该 decision exact-match baseline、candidate、consumer closure、required checks、acceptance mode、route、policy 与 spec selection identities。Stale、不同 closure 或不同 candidate 的证据不能导入。Assistant/网页聊天文本、transport status、历史 passed flag 或人工复制 receipt 不能替代机器 evidence。
