# Gateway、去重、核验与记忆

## 1. Pipeline

```text
review inputs + authority revision
  -> candidate reviewers
  -> schema and evidence gate
  -> stable fingerprint dedup
  -> P0/P1 independent verifier
  -> confirmed/advisory/refuted/unverified
  -> bounded human/action flow
```

P2 通过相同事实门禁，但不自动调用 verifier；抽样核验用于度量。任何 adapter 可返回零 candidate。

每个 candidate/finding/result/rejection 必须绑定 `routeVersion`。旧 route 与新 route 的 sidecar、fingerprint namespace 和 metrics 不能混用。

## 2. 确定性门禁

gateway 必须：

- 校验 schema、行号范围、当前 artifact hash 和 authority revision；
- 校验 failure tuple 非空且不等价于泛化模板；
- 校验文档/计划的 authorityOwner、consumer、validatorRef；
- 对 P0–P2 一律校验 existingGuardAnalysis，并把归一化后的占位等价文本拒绝为 `missing_guard_analysis`；
- 校验 `endLine >= startLine` 以及 severity/disposition 合法组合；
- 校验 layer 集合不变量：`requiredLayers = completedLayers ∪ failedLayers`，completed/failed 互斥，skipped 与 required 互斥，同一 reviewer 只能出现一次；
- 从 gateway execution context 读取 route/scope 已分配的 `reviewProfile` 与 `policyRevision`，再从 gateway-owned policy registry 派生 `requiredLayers`；拒绝缺少 assignment、选择其他可信 profile、revision 漂移和 producer 自报缩小；result 中的 policy/layer 字段只能是该分配的投影及执行状态；
- 使用独立 rejection contract 记录 reason code 和原始 candidate hash，不要求被拒绝候选伪造完整 finding；
- 不允许 LLM 修改 rejection 结果。

## 3. 去重和稳定指纹

fingerprint 输入至少包含 routeVersion、规范化 artifact path、inclusive line range、证据 hash、规范化 failure tuple（trigger input、required state、bad outcome）、authority revision 和 finding family/dimension。只有这些字段全部相同的候选才可合并 `sourceReviewers[]` 并保留最高严重等级；同一证据行若失败链或 dimension 不同，必须保留为独立 finding。不得按标题或 reviewer 名称拆分或合并 finding。

`refuted` finding 使用 evidence fingerprint；rejection record 使用由 routeVersion、candidate hash、input hash、reason code 和 authority revision 生成的 suppression fingerprint。各自绑定的 route/证据/输入/authority 未变化时不得重新出现。处置记忆作为 sidecar 添加，不修改现有 `summary.json` schema。

## 4. 独立 verifier

- 只接收去重后的 P0/P1；
- 只能 confirm、refute 或 unverified；
- 不得扩大 scope 或发现新问题；
- 必须直接检查候选引用的 artifact、上下文和 guard；
- verifier 失败保持 `unverified`，不得静默批准；
- verifier/gateway 按可信 policy 写入机器字段 `unverifiedClass` 与 `unverifiedDisposition`，候选 reviewer 与 result producer 不得写入或覆盖；
- gate 重跑前必须检查现有 verifier decisions；非空时在任何 sidecar 写入前 fail closed，保持 verifier 文件字节不变，并要求新 review run；
- security/data-loss unverified 分别使用 class `security`/`data_loss` 与 disposition `blocking` 并继续阻断，其他 unverified 使用 class `other` 与 disposition `manual_pause` 交人工一次后暂停；blocking 只能汇总为 blocked，manual_pause 只能汇总为 incomplete，两类不得混入同一 result。

## 5. 有限生命周期

- 首轮完整语义 Review 完成后，先汇总全部 accepted findings，再退出只读 review run；
- repair owner 必须批量修复全部 accepted findings，并检查相邻回归风险；禁止逐 finding 自动启动 Whole-scope 三层 Review；
- 修复期间只运行确定性 targeted tests、schema、validator、build/smoke 和反例；这些检查不能替代最终完整语义 Review；
- 批量修复完成后使用新 review ID/input hash 运行一次最终完整语义 Review；artifact stale 只要求新 run，不要求立即重跑；
- 默认最多两轮完整语义 Review；只有最终轮发现新的 P0/P1 或 authority/context graph 被修复改变时才允许第三轮；硬上限三轮，超过后 `manual_pause`；
- P2-only 结果不自动触发新的完整 Review；新 finding 必须引用新变化证据或新增 authority/test evidence；
- 同一 unverified finding 只允许一次人工升级；confirmed blocker 清零且 reviewer layers 完整时结束。

## 6. 跨 run lineage 与启动冻结

- `prepare` 必须绑定稳定 `changeId`、`fullReviewRound` 和可选 predecessor run；round 1 不得有 predecessor，后续 round 必须指向同 change/profile 的相邻已 finalized run。
- 同一 changeId 不得通过更换 review ID 重开 round 1；round 4 永远拒绝；round 3 只在 predecessor 有 P0/P1 或 `authorityContextHash` 改变时允许。
- deterministic preflight 完成后，必须执行 `authorize-launch`；它重新校验 Git revision、全部 artifact hash、profile/context graph、preflight hash、cycle lineage 和成本确认，并生成 hash-bound `review-launch-authorization.json`。
- `validate-layer`、gate、finalize 和 Codex reviewer/verifier lease 均必须消费仍有效的 launch authorization；授权后 authority 或 preflight 漂移时 fail closed。

## 7. Evidence sidecar

建议在既有 task run 目录追加：

- `review-candidates.json`；
- `review-gate-result.json`；
- `review-rejections.json`；
- `review-dispositions.json`；
- `review-metrics.json`。

不得为满足本计划破坏 `summary.json` 兼容性。

## 8. Bootstrap sidecar 隔离

R0 Bootstrap Review 使用用户选择的独立 run directory，并至少写入：

- `review-input.json`；
- `preflight-result.json` 与 `preflight/**`；
- `review-launch-authorization.json`；
- `process-leases.json`；
- `review-candidates.json`；
- `review-rejections.json`；
- `review-gate-result.json`；
- `review-dispositions.json`；
- `review-metrics.json`；
- `review-report.md`。

所有 Bootstrap JSON sidecar 与报告必须绑定 `routeVersion=bootstrap-review-route.v1`、`authorityRevision`、input hash、profile/revision 和 `authorityClass=supplemental_bootstrap`；`preflight-result.json` 还必须按 profile required checks 记录 command、exitCode、evidence path/hash，gate/finalize 绑定其 hash；`review-input.json.routeVersion` 是唯一 route identity authority。准备时冻结 scope file hashes；gate/finalize 检测任一引用 artifact 漂移或 sidecar route binding 不一致时 fail closed。输出目录不得位于任一目标 scope 内。每个 reviewer 写回后必须由该 reviewer 或编排器调用只读 `validate-layer`；命令只验证当前 layer 的绑定、coverage 分区和 candidate 合同，不写 gate sidecar，也不得替 reviewer 修改 JSON。

P0/P1 gate 后进入 gate-only 状态 `awaiting_verification`，并生成 verifier prompt/template；该中间状态必须通过 [bootstrap-review-gate-result.v1.schema.json](schemas/bootstrap-review-gate-result.v1.schema.json)，不能冒充最终 `review-result.v1`。`finalize` 必须要求每个 accepted P0/P1 恰有一个独立 verifier decision；verifier 不能新增 finding ID。confirmed/refuted/unverified 以 disposition sidecar 记录，unverified class 决定 blocking/manual_pause。已生成最终 `review-result.v1` 后，`gate` 与 `finalize` 都必须在任何 sidecar 写入前拒绝重开并要求新 review run。

Verifier 的 `evidenceChecked` 必须覆盖 finding 的精确 artifact 行范围和全部 `contextRead`；仅引用 manifest 内无关文件或无关行不得形成任何 blocker decision。Reviewer completed coverage 按 artifact 集合判断，`readArtifacts` 顺序不是合同。
Path-only context 表示整份 artifact，只有 path-only `evidenceChecked` 才能覆盖；单行或局部范围不能冒充整文件检查。
Final `review-result.v1` 是 run 终态；后续 gate 不得把它覆盖回 Bootstrap 中间状态，即使 verifier decisions 为空。

## 验收标准

- Given 多个 reviewer 引用同一 hash-bound artifact、inclusive line range、exact evidence、规范化 failure tuple 与 finding family/dimension，When dedup，Then只产生一个稳定 fingerprint、保留最高严重等级并合并 source reviewers；若 failure tuple 或 dimension 不同，则保留独立 finding。
- Given refuted fingerprint 且输入未变，When复审，Then gateway 抑制重现。
- Given P2 advisory，When汇总，Then不启动自动修复循环。
- Given result 的 required layer 与可信 profile/revision 不一致，When gateway 汇总，Then fail closed 而不是接受自报集合。
- Given unverified class/disposition 不匹配，或 finding 被汇总为不一致的 result status，When schema/gateway 校验，Then result 被拒绝。
- Given prepare 后 artifact hash 改变，When gate/finalize，Then stale candidate 被拒绝且不得形成 blocker。
- Given输出目录位于目标 scope 内，When prepare，Then命令在写文件前失败。
- Given任一 Bootstrap sidecar 的 route/profile/hash binding 缺失或替换，When gate/finalize，Then fail closed。
- Given `review-gate-result.json` 已是最终 `review-result.v1`，When再次执行 gate 或 finalize，Then在任何写入前失败，最终结果与 verifier 文件字节不变，并要求新 review run。
- Given gate 有 accepted P0/P1 且 verifier 尚未决策，When生成中间结果，Then状态只能为 schema-valid 的 `awaiting_verification`。
- Given reviewer 把全部 required artifact 写入 `readArtifacts` 但保留非空 `missingArtifacts`，When执行 `validate-layer`，Then命令非零退出且不得写任何 gate sidecar。
