# 验证、成本与发布合同

## 1. Review Cost Decision

模型启动前必须发布 cost decision，至少包含：

- closure bytes；
- segment count；
- required roles；
- required attempts；
- retry exposure；
- whole-plan 与 minimal closure candidate 的差异；
- route 与 launch plan identity。

Acceptance 只能在 authority/risk policy 允许集合内选择继续、rebuild closure、repartition 或 manual pause。High-cost acknowledgement 不能替代决策。Mandatory full conformance 的高成本只能触发 completeness rebuild、repartition、manual pause 或正式 policy override，不能降级 route。

## 2. 已观察基线

| Run | Artifact 数 | Frozen bytes | 估计 P50 wall time | 观察结果 |
| --- | ---: | ---: | ---: | --- |
| `vcec-r1` | 389 | 2,762,341 | 184 分钟 | oversized closure，已封存 |
| `vcec-r1m` | 125 | 1,527,532 | 101 分钟 | oversized，未进入正式 reviewer execution |
| `vcec-r1n` | 89 | 1,372,666 | 91 分钟 | 101 segments，三角色超过两小时仍未完成 |

`vcec-r1n` 正式事件超过 240 个 attempt、累计模型使用超过 2,800 万 token，并出现 stale lease、transport failure、payload mismatch 和 write-set overlap。其 run outcome 固定为 `abandoned`、classification 为 `historical-runtime-failure`、`reusable=false`、`authorizes=[]`；内部 attempt classifications 保持原样。该基线必须作为新策略回归输入，不得改写为成功 run。

## 3. 主要成功指标

| ID | 必须证明 |
| --- | --- |
| SM-1 | Required-check deterministic failure 的 reviewer call 为 0 |
| SM-2 | 8-13 closure 相对 whole-plan 显著缩减；75% 是 provisional target，completeness 必须始终通过 |
| SM-3 | Attempts 不超过 required roles × segment count + authorized retries + required verifier attempts |
| SM-4 | 无人工 executable、lease 或 receipt 修补 |
| SM-5 | Full Bootstrap 相对四小时基线显著改善；60 分钟是 provisional target |
| SM-6 | Segment 越界读取和越界 coverage claim 为 0 |
| SM-7 | Terminal/stale event 与 lease reconciliation 闭合，无超窗 acquired lease |
| SM-8 | Path、range、order、hash、role、executable 和 candidate mutation 全拒绝 |
| SM-9 | Mandatory Bootstrap 保持三角色；accepted P0/P1 保持 independent verifier |
| SM-10 | Frozen semantic corpus 不产生 reference baseline 未允许的 false authorization |
| SM-11 | Heartbeat/output 不刷新 no-progress；超窗停止新模型调用并在 grace 内 terminal/reconcile |

完成后记录实际 closure、segment、attempt、retry、token 和 wall-time。

## 4. Counter-metrics

- Closure 缩减不能产生 applicable authority omission。
- 新 route 不能让未执行 required checks、未授权或 receipt mismatch 的实现进入 `acceptance-passed`。
- Payload mismatch、timeout、stale lease 等 transport failure 不能产生 finding、gate verdict 或完成状态。
- Heartbeat、重复打印和轮询日志不能阻止 stop-loss 或形成 completion evidence。

## 5. 8-13 规模回归

回归必须同时覆盖：

- deterministic failure 零模型调用；
- Bootstrap-required 三角色完整 coverage；
- no out-of-bound read；
- no stale lease；
- no manual executable/receipt repair；
- payload mismatch 在 ceiling 内终止并留下诊断；
- compact closure 相对 whole-plan 的量化差异；
- attempt bound；
- heartbeat-without-progress 与 repeated-output-without-progress；
- Acceptance 导入 current evidence 并发布 `acceptance-passed`。

## 6. Semantic Regression Corpus

Owner-labeled frozen corpus 至少覆盖：

- authority/lifecycle/shared-entrypoint/protected-path mandatory route；
- 已知 P0/P1 对应的 non-authorizing outcome class；
- genuine semantic ambiguity 的 semantic-review/manual-pause outcome；
- 删除 authority root、dependency edge、exception clause 或 negative fixture；
- 形状合法但切掉反例的错误 Range Projection；
- legal deterministic-only 的零 reviewer call；
- false-authorizing mutation。

比较对象是 route、severity/blocking class、non-authorizing outcome 和 evidence class，不要求自然语言 finding 逐字一致。Stability samples、threshold 和 model binding 由 Architecture/Policy 决定。

## 7. MVP 边界

CAP-1 至 CAP-10 及六个 normative companions 的全部约束均属于 MVP。M0、M1、M2 仅定义安全交付顺序，不允许把 Effective Progress、no-progress watchdog、事件驱动状态、semantic corpus、Acceptance import 或其他 canonical obligation 延后为非 MVP。

## 8. 发布阶段

### M0：控制面故障闭合

- canonical segment identity；
- segment-only snapshot 和 absolute path；
- access-proof identity inheritance；
- Effective Progress/no-progress watchdog；
- terminal event 与 lease reconciliation；
- payload mismatch、out-of-bound、PID stale、no-progress 与 overlap fixtures；
- 保留历史失败 run。

### M1：Acceptance 策略接入

- Changed-set Manifest；
- Consumer Closure；
- required-check projection；
- typed decide-bootstrap；
- deterministic failure 零 reviewer call；
- 证明 Bootstrap Complete Review 语义未改变。

### M2：规模与 acceptance-passed

- 运行 8-13 regression 与 semantic corpus；
- 记录成本和时延；
- Acceptance 导入 compact Bootstrap evidence 并发布 `acceptance-passed`；
- 指标和 counter-metrics 通过后才替代 whole-directory default。

## 9. 风险约束

- Closure omission 由 typed roots/edges、fixed point、exclusion proof 和 omission mutations 缓解。
- Projection 反例丢失由 full-source hash、range/inclusion binding 和 semantic corpus 缓解。
- Quiet-but-valid model call 不因 stdout silence 被误杀；只有 controller-observed Effective Progress 刷新窗口。
- PID reuse 由 PID + process creation identity 与 append-only event 缓解。
- Cost threshold 不作为实现常量；只有 current Architecture/Policy 可以 ratify。
- Independent verifier route 必须保持现有 risk/model policy；本产品不自动调整模型价格、模型供应商或全局 token quota。
- Compact closure 的 identity 正确不等于语义正确，必须同时通过 semantic detection parity。
