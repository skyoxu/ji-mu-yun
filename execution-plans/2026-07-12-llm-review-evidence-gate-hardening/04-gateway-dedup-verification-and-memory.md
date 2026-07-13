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
- 对 P0–P2 一律校验 existingGuardAnalysis；
- 校验 `endLine >= startLine` 以及 severity/disposition 合法组合；
- 校验 layer 集合不变量：`requiredLayers = completedLayers ∪ failedLayers`，completed/failed 互斥，skipped 与 required 互斥，同一 reviewer 只能出现一次；
- 从 gateway execution context 读取 route/scope 已分配的 `reviewProfile` 与 `policyRevision`，再从 gateway-owned policy registry 派生 `requiredLayers`；拒绝缺少 assignment、选择其他可信 profile、revision 漂移和 producer 自报缩小；result 中的 policy/layer 字段只能是该分配的投影及执行状态；
- 使用独立 rejection contract 记录 reason code 和原始 candidate hash，不要求被拒绝候选伪造完整 finding；
- 不允许 LLM 修改 rejection 结果。

## 3. 去重和稳定指纹

fingerprint 输入至少包含 routeVersion、规范化 artifact path、证据 hash、failure tuple、authority revision 和 finding family。多个 reviewer 命中相同指纹时合并 `sourceReviewers[]`，保留最具体证据；不得按标题或 reviewer 名称拆分 finding。

`refuted` finding 使用 evidence fingerprint；rejection record 使用由 routeVersion、candidate hash、input hash、reason code 和 authority revision 生成的 suppression fingerprint。各自绑定的 route/证据/输入/authority 未变化时不得重新出现。处置记忆作为 sidecar 添加，不修改现有 `summary.json` schema。

## 4. 独立 verifier

- 只接收去重后的 P0/P1；
- 只能 confirm、refute 或 unverified；
- 不得扩大 scope 或发现新问题；
- 必须直接检查候选引用的 artifact、上下文和 guard；
- verifier 失败保持 `unverified`，不得静默批准；
- verifier/gateway 按可信 policy 写入机器字段 `unverifiedClass` 与 `unverifiedDisposition`，候选 reviewer 与 result producer 不得写入或覆盖；
- security/data-loss unverified 分别使用 class `security`/`data_loss` 与 disposition `blocking` 并继续阻断，其他 unverified 使用 class `other` 与 disposition `manual_pause` 交人工一次后暂停；blocking 只能汇总为 blocked，manual_pause 只能汇总为 incomplete，两类不得混入同一 result。

## 5. 有限生命周期

- 默认一次 discovery、一次 blocker verification；
- 修复后只复查 evidence/path/authority 变化的 finding；
- P2 不触发自动修复—复审；
- 新 finding 必须引用新变化证据或新增 authority/test evidence；
- 同一 unverified finding 只允许一次人工升级；
- confirmed blocker 清零且 reviewer layers 完整时结束。

## 6. Evidence sidecar

建议在既有 task run 目录追加：

- `review-candidates.json`；
- `review-gate-result.json`；
- `review-rejections.json`；
- `review-dispositions.json`；
- `review-metrics.json`。

不得为满足本计划破坏 `summary.json` 兼容性。

## 7. Bootstrap sidecar 隔离

R0 Bootstrap Review 使用用户选择的独立 run directory，并至少写入：

- `review-input.json`；
- `review-candidates.json`；
- `review-rejections.json`；
- `review-gate-result.json`；
- `review-dispositions.json`；
- `review-metrics.json`；
- `review-report.md`。

所有文件必须标记 `routeVersion=review-bootstrap.v1`、`authorityRevision`、input hash、profile/revision 和 `authorityClass=supplemental_bootstrap`。准备时冻结 scope file hashes；gate/finalize 检测任一引用 artifact 漂移时 fail closed。输出目录不得位于任一目标 scope 内。

P0/P1 gate 后保持 incomplete，并生成 verifier prompt/template。`finalize` 必须要求每个 accepted P0/P1 恰有一个用户手工 verifier decision；verifier 不能新增 finding ID。confirmed/refuted/unverified 以 disposition sidecar 记录，unverified class 决定 blocking/manual_pause。

## 验收标准

- Given 两个 reviewer 引用同一证据和失败链，When dedup，Then只产生一个 fingerprint。
- Given refuted fingerprint 且输入未变，When复审，Then gateway 抑制重现。
- Given P2 advisory，When汇总，Then不启动自动修复循环。
- Given result 的 required layer 与可信 profile/revision 不一致，When gateway 汇总，Then fail closed 而不是接受自报集合。
- Given unverified class/disposition 不匹配，或 finding 被汇总为不一致的 result status，When schema/gateway 校验，Then result 被拒绝。
- Given prepare 后 artifact hash 改变，When gate/finalize，Then stale candidate 被拒绝且不得形成 blocker。
- Given输出目录位于目标 scope 内，When prepare，Then命令在写文件前失败。
