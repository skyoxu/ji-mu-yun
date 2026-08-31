# Normative Success Metrics

这些阈值来自 PRD 与 adopted capability draft §18，属于规范性验收口径。

## VDD semantic quality

- curated requirements fixture 的 active obligation recall ≥ 95%。
- unsupported/invented obligation precision ≥ 95%。
- active obligation → Acceptance → source ref → RED intent → slice 覆盖率 = 100%。
- `hard_uncovered = 0`；overbroad Acceptance、terminal swallowing、source-ref drift mutation 全部阻断。
- 同输入重复编译产生稳定 ID 和等价 partition。

## Slice and TDD truth

- owner/lane/state-transition 不兼容时 100% 拆分；兼容的 Acceptance 可在合法 write set 内合并。
- 固定失败、无法调用生产入口、依赖未来 evidence 的 RED intent 在 plan-ready 阶段 100% 阻断。
- 所有 RED/GREEN/REFACTOR observation 的 `executions >= 1`。
- planned-only、timeout、repo-noise、harness failure、zero-case、unexpected-green 不得成为 pass。
- GREEN/REFACTOR selector identity 与 RED 相同；observed failure 不得复制 registry expected 值。
- selector/fixture/target 变化使对应生命周期全部失效；多个历史成功 run 不得造成当前 lineage 歧义。
- terminal happy path 与关键 mutation 必须真实执行。

## Replay, false-green and generalization

- 选择性重放决策与 invalidation matrix 一致率 ≥ 99%。
- detached fixtures 覆盖所有 failure family 和关键结构 mutation；错误 target、复制结果、未来 evidence、历史扫描和自报 pass 的放行率 = 0%。
- 至少一次 8-25 replay 和一次未用于设计工具链的新中等任务通过，且无需修改 VDD/Quick Dev 本身。
- 中等任务 standard profile 从 plan-ready 到 implementation-complete 的目标 ≤ 60 分钟；任务规模、环境和计时由 Open Question 7 的 Product 决策冻结。
- 相同 deterministic failure fingerprint 连续两次后停止原参数重跑；第三次原参数重跑率 = 0%。

## Anti-gaming counters

- 不得通过降低 assertion、缩小 case 集、增加 receipt/hash 文件或增加模型调用次数提升完成率。
- 文档、schema、happy-path 单测不能单独证明约 90% 能力；必须同时通过 detached mutation、8-25 replay 和新任务盲测。

