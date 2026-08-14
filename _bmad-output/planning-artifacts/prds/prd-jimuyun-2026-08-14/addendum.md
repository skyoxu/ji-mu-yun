# Addendum：验收与 Bootstrap 控制面设计输入

本文保存已在讨论中形成、但属于 Architecture、Policy 或实现合同的机制细节。它们支持 PRD，不替代 PRD authority。

## A. 已观察基线

### A.1 Bootstrap Run 规模

| Run | Artifact 数 | Frozen bytes | 估计 P50 wall time | 观察结果 |
| --- | ---: | ---: | ---: | --- |
| `vcec-r1` | 389 | 2,762,341 | 184 分钟 | 过大 closure，已封存 |
| `vcec-r1m` | 125 | 1,527,532 | 101 分钟 | 仍属 oversized，未进入正式 reviewer execution |
| `vcec-r1n` | 89 | 1,372,666 | 91 分钟 | 101 segments，三角色执行超过两小时仍未完成 |

`vcec-r1n` 的正式事件曾记录超过 240 个 attempt，累计模型使用量超过 2,800 万 token，并出现 stale lease、transport failure、payload mismatch 和 write-set overlap。该基线用于验证新策略，不应被重写为成功 run。

## B. 推荐的 Authority 流程

```text
Quick Dev / VDD implementation-complete
                ↓
Acceptance freezes baseline/current
                ↓
complete Changed-set Manifest
                ↓
minimal complete Consumer Closure
                ↓
contract-projected deterministic required checks
                ↓
        ┌──── machine failure ────→ typed repair, zero reviewer call
        │
        └──── deterministic closure passed
                                ↓
                     Acceptance decide-bootstrap
                                ↓
        ┌───────────────────────┴────────────────────────┐
        │                                                │
deterministic_only                         full implementation conformance
        │                                                │
Acceptance continues                          3-role compact Bootstrap
                                                         ↓
                                      independent verifier if accepted P0/P1
                                                         ↓
                                            Acceptance import/finalize
```

## C. Canonical Segment Projection 候选

Architecture 应让以下消费者调用同一个 canonical projection/hash API：

- segment assignment producer；
- reviewer prompt/request producer；
- child receipt producer；
- parent receipt validator；
- coverage fold；
- retry cache identity。

候选 descriptor 至少需要表达：

- review/input/closure identity；
- reviewer role；
- artifact original path 与 frozen artifact hash；
- inclusive byte 或 line range；
- segment ordinal 与总 segment count；
- segment bytes hash；
- projection/payload schema version；
- selected model identity（当 cache/reuse 依赖模型时）。

具体序列化、domain separator、自身 hash 字段排除规则和算法版本由 Architecture 决定。

## D. Range Projection 候选

大型 normative authority 的 parent-owned projection 应至少绑定：

- source path；
- full source hash；
- inclusive range；
- extracted bytes hash；
- inclusion reason；
- changed-set/requirement/acceptance 关联；
- source encoding 与 newline normalization policy（如 canonical identity 需要）。

小型合同优先整文件，避免为了压缩而制造新的遗漏面。

## E. Mutation Test 集合

以下 mutation 必须稳定拒绝：

- 修改 artifact path；
- 修改 range start/end；
- 修改 segment ordinal 或顺序；
- 修改 artifact/full source hash；
- 修改 extracted bytes；
- 修改 reviewer role；
- 修改 model identity（当 identity 绑定模型时）；
- 将 absolute snapshot path 替换为 live repository path；
- 重放旧 candidate identity 的 receipt；
- 让 child 声明未分配 coverage；
- 在 terminal event 后保留 acquired lease；
- 在前序 acquired lease 存活时启动相同 write-set retry。

## F. 恢复状态机候选

```text
attempt-reserved
→ attempt-started
→ attempt-liveness-heartbeat
→ attempt-effective-progress (zero or more)
→ no-progress watchdog | child terminal observation
→ attempt-completed | attempt-failed | attempt-stale
→ lease reconciliation
→ retry-eligible | terminal blocked | role completed
```

外层 job 返回、liveness heartbeat、Effective Progress Event 和 child terminal observation 必须被区分。只有绑定当前 run/segment/attempt identity 的 terminal、有效 evidence/receipt 增量或 policy 注册状态迁移能够刷新 no-progress window；stdout silence 不能单独证明停滞，重复打印和 heartbeat 也不能证明进展。任何 retry 在 reservation 前都应完成 reconciliation，且操作员不重新填写 executable/model identity。

## G. 被拒绝的替代方向

- **默认单 reviewer 替代 Bootstrap 三角色**：拒绝，因为会静默改变 Complete Review authority semantics。若未来需要，只能建立 non-authorizing semantic check 或正式修改 ADR/standard/profile。
- **Bootstrap 内置计划命令**：拒绝，因为会把 8-13 特定行为固化到通用控制面；应由 implementation contract 投影 required checks。
- **只使用 Git diff**：拒绝，因为会遗漏未跟踪、删除、重命名、依赖、repository authority 和实际执行证据。
- **提高 snapshot 上限解决成本**：拒绝，因为根因是错误 closure；扩大上限只会允许更昂贵的错误输入。
- **只修某个 payload mismatch case**：不足。应统一 canonical segment identity，并用 mutation tests 覆盖所有身份漂移。

## H. Semantic Regression Corpus 候选

紧凑 closure 的验收不能只证明文件更少、segment 更少和 hash 正确，还必须证明重要语义风险没有因投影而消失。Architecture/Acceptance contract 应建立 owner-labeled、冻结的 corpus，至少覆盖：

- 必须进入 full implementation conformance 的 authority/lifecycle/shared-entrypoint/protected-path 场景；
- 已知 P0/P1 缺陷被纳入 compact closure 后应产生的非授权结果类别；
- genuine semantic ambiguity 应产生 semantic-review/manual-pause 类结果，而不是 GREEN；
- 删除关键 authority root、dependency edge、exception clause 或 negative fixture 后，closure completeness 必须失败；
- 错误 range projection 仍满足 path/hash 形状但切掉反例条件时，semantic regression 必须拒绝；
- deterministic-only 合法场景必须保持零 Bootstrap reviewer call；
- compact closure 不得产生 reference baseline 不允许的 false authorizing outcome。

Corpus 比较对象是 route、severity/blocking class、non-authorizing outcome 和 evidence class，不要求模型自然语言 finding 逐字一致。重复采样次数、稳定性阈值和模型版本绑定由 Architecture/Policy 决定。

## I. 无人值守进展与状态输出候选

- liveness heartbeat 只回答进程是否仍存在，不刷新 no-progress window；
- Effective Progress Event 必须绑定当前 candidate、closure、segment、attempt 和新增 evidence/terminal transition；
- 用户可见状态只在阶段变化、新 evidence、retry、typed warning 或异常时发布，并按 event identity 去重、按 policy 节流；
- stdout silence 不是单独的停滞证明，重复打印也不是进展证明；
- 超过 no-progress ceiling 后停止新增模型调用，终止或隔离活动 attempt，追加 terminal/stale event，reconcile lease，并发布 typed blocked/recovery result；
- 初始 60 分钟窗口是待 M0 ratify 的 operator-policy 假设，不是 Architecture 常量；
- Bootstrap Review runtime controller 拥有 Effective Progress Event 验证、watchdog enforcement、terminal/lease recovery 和状态事件发布；
- Bootstrap control-plane policy owner 拥有 no-progress ceiling、terminal grace window 与状态 throttle policy 的版本化和 ratification。
