# 8-15 验收工作流优化方案

## 目的

本文记录 8-15 需求目录本轮验收的效率与恢复性分析，并固定后续优化边界。它是控制面优化输入，不改变已经发布的 `acceptance-passed`、Quick Dev `implementation-complete`、Maintainer authorization 或历史失败证据。

本轮从第一条持久化 Acceptance run 到最终确定性通过，墙钟跨度约 7 小时 17 分钟；实际 `terminal-full` 测试执行时间只有秒级。主要浪费来自前置 artifact 重建、绑定漂移、手动路由和恢复重试，而不是业务测试本身。

## 当前结论

当前验收结果有效：

- 路由为 `deterministic_only`；
- `terminal-full` 已通过；
- `acceptance-passed` 已由 Acceptance 发布；
- `validate-package` 通过；
- 本轮没有调用 Bootstrap。

但当前控制面仍是“多个局部 validator + 模型人工调度”，不是可恢复的完整 evidence coordinator。`SKILL.md` 中关于自动刷新、自动回 Quick Dev 和继续 finalization 的描述，尚未对应一个统一的可执行调度入口。

## 未修复的重要问题

### P0/P1-1：Quick Dev receipt 未绑定 candidate identity

当前 `implementation-complete` receipt 绑定 contract、command registry 和 terminal predicate，但没有绑定 candidate manifest、candidate snapshot 或明确 candidate revision。理论上可以把一个对 candidate A 生成的 receipt 组合到 candidate B 的 Acceptance projection。

修复要求：Quick Dev receipt 增加 `candidateBindingHash`，并固定绑定以下三部分的 identity：

```text
candidate content manifest identity
+ candidate custody/snapshot identity
+ terminal runner identity
```

Acceptance projector 必须对 receipt、candidate manifest/custody、terminal runner 做 exact-match。缺少任一部分或任一部分不匹配时，只允许回 Quick Dev owner 生成 successor receipt；不得把 receipt 移植到另一个 candidate、snapshot 或 runner。

### P1-2：deterministic_only 被不必要地强制经过 semantic child

当前 `start-or-resume` 前要求 Skill-input semantic child，即使最终 route 是 `deterministic_only`。外部模型服务不可用时，纯机器验收会被无关的语义输入消费阻断。

修复要求：

- `deterministic_only` 使用 deterministic source-sufficiency receipt；
- semantic child 只用于 semantic route 或明确要求语义压缩的输入；
- `catalog_stale` 继续作为 `knowledge_freshness=degraded`，不触发 semantic child；
- 语义子进程不可用不得阻断纯机器验收。

route 不能由 caller 自报或通过参数直接选择。Acceptance 必须先完成机器投影，再决定 route：

```text
freeze candidate
  -> changed-set / closure
  -> required checks
  -> deterministic route projection
  -> route == deterministic_only
       ? deterministic source-sufficiency receipt
       : semantic Skill-input
```

因此，caller 提供的 route 只能作为请求意图或诊断字段；它与机器投影不一致时必须拒绝或转入修复，不能借此绕过 semantic gate 或扩大 deterministic fast path 的适用范围。

### P1-3：Projection bundle 与最终 run 的 knowledge context 可能漂移

Projection bundle 可能保留旧 context 路径，而调用者在 `prepare-run` 时手动传入 successor context。这样 bundle、run input 和最终 receipt 的 authority 不再由同一 producer 原子发布。

修复要求：projector 在发布 bundle 时绑定当前 context；`prepare-run` 只能消费 bundle 中的 context 引用；context 发生 successor refresh 时必须生成新的 bundle 和新的 derived run，不允许调用者替换字段。

当前 Acceptance-owned knowledge context 已支持以下 refresh primitive：

- `catalog_stale` 的 `degraded` continuation；
- selected read-set source bytes 变化后的受控 refresh/rehash。

剩余缺口不是 knowledge refresh primitive，而是 projection bundle、`prepare-run` 与 coordinator 尚未把 successor context 收敛为唯一 authority；它们仍可能要求调用者人工重新拼装或替换 context。

目标行为固定为：

```text
catalog_stale
  + selected paths/modules/resource-set/selection semantics unchanged
  -> re-run controlled Locator against current bytes
  -> rehash observed sources
  -> publish successor context and new binding

source bytes changed
  + same selected authority/read-set semantics
  -> rehash through the new Locator result
  -> continue without Knowledge publication

path/module/resource-set/selection/source authority changed or missing
  -> typed repair / maintenance route
```

Acceptance 永不自动发布 Knowledge authority；它只生成自己拥有的 successor context。source hash mismatch 不能被简单忽略，必须通过新的受控 Locator 结果重新建立 hash binding。

### P1-4：finalization 重试不是幂等的

相同输入重复执行 deterministic finalization 会因为已有 `acceptance-finalized` event 的 sequence 不同而报 append-only 冲突，即使第一次已经成功发布 `acceptance-passed`。

修复要求：对相同 run/input/action receipt 集合，finalization 必须重放已有成功结果；只有内容或 binding 不一致时才返回 conflict。重复调用不得创建失败假象，也不得创建新的生命周期状态。

## 哈希策略优化

### 必须保留

- baseline/candidate content manifest 的文件内容 hash；
- Quick Dev receipt 与 contract、command registry、terminal runner 的 binding；
- action receipt 与 command descriptor、exit code、stdout/stderr 的 binding；
- run input、candidate custody、最终 acceptance artifact 的 identity hash。

### 应降级为 provenance 或内部派生字段

- 当 scoped source bytes 未变化时，不要因无关 `HEAD` 变化使 Skill-input 失效；
- knowledge context 不要同时把 context bytes、semantic hash、source manifest、Locator request/result、freeze artifact 全部作为独立运行阻断条件；
- environment identity 由 command descriptor 声明 behavior-affecting allowlist；executable 已解析为绝对路径并绑定 executable hash 时，PATH 可降级为 provenance，否则必须保留；TEMP、USERPROFILE 等无关变量不作为硬绑定；
- command registry 保留 descriptor hash 和执行结果 hash，invocation/process 的重复 hash 仅作诊断字段；
- historical evidence 路径不得进入 candidate manifest，避免把 scope 投影错误伪装成 hash drift。

优化原则是：一个 artifact 一个主要 content identity，其他 hash 用于诊断、重放或 provenance，不重复升级为新的硬阻断。

## 编排器目标

新增一个 repository-owned、append-only、幂等的 Acceptance coordinator，按以下状态机自动推进：

```text
resolve target
  -> validate Quick Dev handoff
  -> refresh knowledge successor when read-set is unchanged
  -> project compact prerequisites
  -> create/validate Skill-input receipt when route requires it
  -> start-or-resume derived run
  -> execute action DAG
  -> recover stale action or resume successor attempt
  -> deterministic finalization
  -> package validation
```

编排器必须遵守以下边界：

- 不发布 Quick Dev、Maintainer 或 VDD lifecycle state；
- deterministic_only 不调用或启动 Bootstrap；
- semantic route 只生成 typed Bootstrap handoff，并停在显式 acknowledgement/authorization boundary；
- 不猜测 changed paths、baseline、candidate 或 commands；
- 不覆盖历史 run 和失败证据；
- 所有 successor 由输入 binding 派生；
- 同一 binding 重复调用必须 resume 或 replay，而不是产生新 run。

## Harness 恢复改造

当前 claim、PID 检查和 stale event 机制保留，但需要补齐：

1. heartbeat 与 lease expiry，记录 owner token、process start time 和最后有效进度；
2. stale action 自动进入 successor attempt，不依赖模型再次手动调用；
3. action event append 使用进程级或文件级互斥，避免并发 sequence 冲突；
4. finalization 和 receipt import 提供幂等 replay；package validator 保持 pure/read-only，由 coordinator replay 已记录的 identical result；
5. 增加 target-level latest successor pointer，避免人工在 r22-r29 中选择当前权威 run；
6. 先增加一次性、可重入的 `run-coordinator` 命令，负责检查 claim、恢复 dead process 和继续 DAG；后台 supervisor 延后到后续 unattended 需求明确后再评估；
7. 记录每个阶段的 elapsed time、等待原因和人工介入点，用于区分真实测试成本与编排成本。

## 实施顺序

### 阶段一：先消除错误硬阻断

- deterministic_only 移除 semantic child 强制依赖；
- 将现有 Acceptance-owned successor-context refresh 接入 coordinator 与 bundle 单一 authority；
- `catalog_stale` / source-byte refresh 不再产生人工重新拼装步骤；
- 修复 implementation target 的安全 source projection；
- 修复 bundle/context 单一 authority。

### 阶段二：修复身份和幂等

- Quick Dev receipt 增加 candidate binding；
- 收敛重复 hash 层；
- finalization 和 receipt/import 记录支持 identical replay；package validation 仍保持纯只读；
- 加入 latest successor pointer。

### 阶段三：建立恢复编排

- coordinator 执行完整 deterministic DAG；
- semantic route 生成 typed Bootstrap handoff，并在授权边界暂停；
- stale action 自动恢复并继续；
- 增加 heartbeat/lease reconciliation；
- 增加无模型、无 Bootstrap 的验收 smoke。

## 验收标准

优化完成后，针对一个与 8-15 同等规模的 dirty candidate：

- 不需要模型手动选择 successor run；
- catalog_stale 且 selected paths/modules/resource-set/selection semantics 未漂移时不阻断验收；
- 无需 semantic child 或 Bootstrap 即可完成 deterministic_only；
- Quick Dev receipt 与 candidate content、custody/snapshot、terminal runner 任一 identity 不匹配时自动回 owner，三者 exact-match 后自动继续；
- route 由 Acceptance 机器投影决定，caller 不能通过参数绕过 semantic gate；
- coordinator 重启后从同一 run 恢复，不重复执行已完成 action；
- 重复 finalization 返回同一个 `acceptance-passed` artifact；
- stale process 能被自动识别、标记并继续 successor attempt；
- 全流程只留下一个 current authoritative run，历史 evidence 仍保留但不进入 candidate scope；
- 机器可报告总耗时、等待耗时、人工介入次数和实际测试耗时。

## 非目标

- 不重新设计 VDD requirements、Architecture authority 或 lifecycle ownership；
- 不让 Acceptance 取得 Quick Dev、Maintainer、VDD 或 Bootstrap 的发布权；
- 不删除或重写 r22-r29 历史证据；
- 不把整个 Acceptance 流程 event-source 化；事件只记录运行过程，artifact content hash 仍是事实身份。
