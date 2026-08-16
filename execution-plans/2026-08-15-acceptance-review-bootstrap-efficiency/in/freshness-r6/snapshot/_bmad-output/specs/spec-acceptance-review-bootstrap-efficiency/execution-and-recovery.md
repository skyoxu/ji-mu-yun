# 执行、进展与恢复合同

## 1. Process Event Authority

Process Event 是 attempt reservation、start、liveness heartbeat、Effective Progress、terminal、stale 和 retry 事实的 append-only authority。Lease view 从 current process identity 与 Process Event 重建；人工编辑 lease sidecar 不改变 authority。

## 2. Liveness 与 Effective Progress

Liveness heartbeat 只证明进程仍存在。Effective Progress Event 必须：

- 由 controller 验证；
- 绑定当前 candidate、closure、segment 和 attempt identity；
- 表达 segment/phase terminal、有效 evidence/receipt 增量，或 policy 注册的状态迁移。

Stdout silence 不能单独证明停滞；heartbeat、stdout、重复状态、轮询日志和用户可见打印也不能证明进展或刷新 no-progress window。

## 3. No-progress Stop-loss

超过当前 policy 的 no-progress ceiling 后，controller 必须：

1. 停止启动新 reviewer/model call；
2. 终止或隔离活动 attempt；
3. 追加 failed/stale terminal event；
4. 按 current process identity reconcile lease；
5. 发布 non-authorizing typed blocked/recovery result。

初始 60 分钟仅为待 M0 ratify 的 assumption。No-progress ceiling、terminal grace、lease、retry 和 status throttle 是一个 versioned owner-local runtime-policy artifact 中可独立调节的字段；具体值仍由 Bootstrap control-plane policy owner ratify。

## 4. Terminal 与 Lease Reconciliation

- 外层 job return 与 child terminal observation 分离。
- Dead 或 PID-reused process 先追加 stale/failed event，再 rebuild lease。
- 外层 job 退出后不能长期遗留占用 write-set 的 acquired lease。
- Retry reservation 前必须完成 reconciliation。
- Retry 不能被自身已终止的前序 attempt 以 write-set overlap 拒绝。

## 5. Bounded Retry

- Retry 只适用于 policy 注册的 transport family。
- 只重试失败 segment；已验证 segment 不重新执行。
- 达到 family-specific ceiling 后输出 typed blocked/recovery result。
- Context-budget failure 必须重新分区，不能对不变输入重复调用。
- Retry 不创建新 semantic round 或 lineage family。
- Retry 保持 segment descriptor、access proof 和 policy identity；任何合法变化都必须通过显式新 identity 表达。

具体 retry ceilings 由 policy ratify，本合同不冻结次数。

## 6. 用户可见状态

用户可见更新仅在以下事件产生：

- phase transition；
- 新 identity-bound evidence；
- retry；
- typed warning；
- exception 或 terminal result。

状态按 event identity 去重并按 policy 节流。内部 heartbeat/轮询可以保留，但不作为用户可见 progress，不刷新 no-progress window，也不能制造仍在推进或已经完成的印象。

## 7. Recovery Independence

- 恢复决策只能由 Process Events、immutable descriptors、current process identity 和 current published policy 重建。
- 聊天历史、Codex resume/compaction 状态、assistant 记忆或人工叙述都不是 recovery authority。
- 不得要求维护者手工重建 lease、手工判断 PID 归属或修改 receipt 才能继续；无法机器重建时 fail closed 为 typed non-authorizing result。

## 8. Ownership

Bootstrap Review runtime controller 负责 Effective Progress 验证、watchdog enforcement、terminal/lease recovery 和状态事件发布。Bootstrap control-plane policy owner 负责 no-progress ceiling、terminal grace 和 status throttle policy 的版本化与 ratification。Runtime 只能执行 current published policy，不能自行放宽。
