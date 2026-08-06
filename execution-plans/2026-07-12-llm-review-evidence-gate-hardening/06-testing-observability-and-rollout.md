# 测试、观测与渐进启用

## 1. 确定性测试矩阵

必须覆盖：

- 零 finding 合法 clean；
- reviewer layer 失败不能 clean；
- 缺 artifact/line/evidence 被拒绝；
- `endLine < startLine` 被拒绝；
- 缺 input/state/badOutcome 被拒绝；
- P0–P2 缺 guard analysis 被拒绝；
- P0 缺精确证据、P1 缺失败结果、P2 缺防护分析分别被拒绝；
- confidence 低于 `0.8` 的候选被拒绝；
- schema rejection 以独立 rejection contract 记录，不伪造完整 finding；
- 文档 finding 缺 authority/consumer/validator 被拒绝；
- 只有 evidence、规范化 failure tuple 与 finding family/dimension 全部相同的 duplicate fingerprint 才合并；
- unchanged refuted/rejected fingerprint 不重现；
- P2 不触发 repair loop；
- P0/P1 advisory 与 P2 confirmed/unverified 组合被拒绝；
- verifier 不得新增 finding；
- unchanged input 不允许新增 blocker；
- BMAD/GDS customization 升级回归；
- 两个账户/项目 evidence 隔离。
- Blind Hunter diff-only candidate 无上下文时被拒绝；
- Edge Case Hunter 字段映射保持 trigger/guard/consequence 语义；
- Acceptance Auditor 缺精确 AC、spec 行号或 current-phase ownership 时被拒绝；
- `no-spec` 时 Acceptance Auditor 记录为 not applicable，clean/incomplete 不被误判；
- required/completed/failed/skipped layer 集合违反分区不变量时被拒绝，包括“所有 reviewer skipped 但 status=clean”；
- `reviewProfile`/`policyRevision` 必须匹配 gateway context 已分配 policy，再从可信 registry 派生 required layer；producer 改选较窄可信 profile 或自行缩小集合必须失败；
- candidate/result producer 不能预写或覆盖 gateway-owned unverified class/disposition；security/data-loss 不能 manual-pause；manual-pause 与 confirmed blocker 共存的 blocked result 也必须失败；
- 三个 reviewer 相同 evidenceFingerprint 合并为一条并保留全部 `sourceReviewers[]`；
- 当前 7 月 7 日 in-flight review 在 R3 handoff 前不改变 route version、输出或 ledger。
- old/new `routeVersion` 的 sidecar、fingerprint namespace 和 metrics 不混用。
- finding/candidate 缺 routeVersion，或 fingerprint/suppression fingerprint 未绑定 routeVersion 时被拒绝。
- Bootstrap prepare 不调用 subprocess/LLM/reviewer，且目标 scope 在 prepare/gate/finalize 前后 hash 不变；
- Bootstrap profile/manifest/prompt 必须一致投影 review object/depth、required context、complete/no-sampling policy、逐角色 reasoning 和 mandatory tool probe；Round 1-2 discovery 使用 profile 声明的 Terra/fallback 路由，合法 Round 3 使用 Sol/high，standard P1 verifier 使用 Terra/high，高风险 P1 使用 Sol/high，P0/security 使用 Sol/max；跨会话替换必须 fail closed；
- discovery access proof 必须覆盖每个不同的 role-specific model/reasoning 路由；相同路由可共享 proof，缺任一路由 proof 或 proof/layer 不等价时授权失败；
- Bootstrap 输出目录位于 scope 内、scope 越过 repository root 或包含不存在路径时 fail closed；
- required reviewer 输出缺失与空 findings 明确区分；三层均完成且零 finding 可以 clean；
- 每层 reviewer 写回后必须通过只读 `validate-layer`；该命令只接受 `completed`，`pending`/`failed`、`missingArtifacts` 非空、required/read 集合不等或 coverage 不是精确分区时失败，且不得产生 gate sidecar；
- prepare 后 artifact 漂移、行区间反转、exactEvidence 不匹配、context 越界均产生稳定 rejection；
- failure tuple 或 `existingGuardAnalysis` 使用 `TBD`/`TODO`/`N/A` 等价占位文本时分别产生 `missing_failure_tuple`/`missing_guard_analysis` rejection；
- 相同 evidence、规范化 failure tuple 与 dimension 跨 reviewer 合并 provenance；同 evidence 但任一 failure tuple 字段或 dimension 不同的候选保持独立；
- P0/P1 没有完整 verifier decisions 时保持 incomplete，verifier 新增 finding ID 被拒绝；
- gate 重跑遇到非空 verifier decisions 时非零退出，且 verifier 文件 hash 不变；
- 已 finalized 的 `review-result.v1` run 再次 gate 或 finalize 时非零退出，且最终结果、verifier 与既有 sidecar 字节不变；
- 同一完整 fingerprint 的 P2 先于 P1 到达时，dedup 保留 P1 并进入 verifier；语义等价的空白、大小写或标点差异不能制造重复 finding，但不同 trigger/state/outcome 或 dimension 不能被同证据行吞并；
- Bootstrap sidecar 标记 `supplemental_bootstrap`，不能被正式 repair/summary consumer 自动发现。
- 四类 profile 必须投影 role rubric、误报抑制、untrusted-content、deterministic preflight 与 review-cycle policy；任一字段漂移使 load/gate/finalize fail closed。
- 生成 prompt 必须包含对应角色 rubric、profile 专用误报清单和嵌入指令隔离文本；不能只包含 reviewer 名称。
- repair 阶段不得因单条 finding 自动启动完整三层 Review；默认第二轮完成收口，第三轮仅允许新 P0/P1 或 authority/context graph 改变。
- required deterministic preflight 失败时必须在 reviewer 启动前停止，并保留命令/退出码/输出 evidence。
- `preflight-result.json` pending/failed、check ID 漂移、非零 exitCode、越界 evidence path、缺失或 hash stale evidence 均阻止 gate；gate/finalize 绑定 preflight result hash。
- preflight 后任一 artifact、Git revision、profile/context graph 或 preflight hash 漂移时，`authorize-launch` 非零退出且不得留下授权 sidecar。
- implementation profile 缺 plan-bound `--required-check` 时 prepare 失败；附加检查必须映射到 prepared authority artifact 并进入 preflight requiredChecks。
- 同一 changeId 换 review ID 重开 round 1、缺/错 predecessor、round 4、无 blocker/context change 的 round 3 均被拒绝。
- Bootstrap 语义互斥 attestation 缺失时 prepare 失败；Quick Dev/BMAD/GDS 只能在该周期做实现与确定性检查。
- high-cost review 未显式确认时 reviewer 启动授权失败；lease acquire 必须确认 PID 当前存活并捕获 OS process identity；同 operation 的 live PID lease 禁止重复 acquire，已退出 lease 可标 stale 后重新 acquire。
- `codex-exec` gate 要求三个 reviewer process lease completed；有 P0/P1 时 finalize 还要求独立 verifier lease completed；release 缺 PID、PID 不匹配、live PID process identity 不匹配或 dead PID acquire 均不得形成 completed lease，正常退出的已捕获 child 可由原 PID 收口。

## 2. Shadow 数据

先在文档/计划审查运行固定样本或至少两周 shadow，再启用代码阻断；前台用户 route 必须在平台开发链路稳定后单独 shadow。记录：

- raw candidates；
- schema/evidence rejected；
- deduplicated unique；
- confirmed、advisory、refuted、unverified；
- human accepted/overridden；
- repeated fingerprint；
- review rounds、tokens、duration；
- first-pass clean rate、完整 Review 平均轮数、达到 hard limit 的 manual-pause 次数。

## 3. 指标

- unsupported finding drop rate；
- duplicate collapse rate；
- confirmed blocker precision；
- refuted P0/P1 rate；
- repeated false-positive rate；
- median visible findings；
- legitimate zero-finding rate；
- review rounds per change、first-pass clean rate、mean rounds to closure；
- human override rate；
- gateway latency 与模型成本。

不得用“finding 越少越好”作为 KPI。上线门槛以 blocker precision、重复误报、一次闭环率和 seeded-defect recall 共同判断。

## 4. Rollout 状态

`disabled` → `shadow` → `advisory` → `blocking`。状态按 adapter 分开配置，默认 fail closed：

- schema/validator 失败：`incomplete`；
- verifier 失败：P0/P1 `unverified`；
- metrics 写入失败：不得丢失 finding 主证据，但阻止宣告 rollout gate 完成；
- rollback 可退回 advisory/disabled，但不得恢复 minimum finding count。

## 5. Evidence 与隐私

证据写入 `logs/` sidecar，继承 token/secret redaction、账户隔离、保留和删除规则。不得把前台项目源代码、prompt、token 或用户内容复制进全局跨账户 metrics。

## 验收标准

- Given shadow run，When完成 review，Then raw/gated/deduped/disposition/成本指标可追溯。
- Given指标不足或 recall 下降，When评估 blocking，Then保持 shadow/advisory，不以主观判断放行。
- Given evidence 含 secret fixture，When持久化，Then redaction test 证明敏感值未进入 sidecar。
