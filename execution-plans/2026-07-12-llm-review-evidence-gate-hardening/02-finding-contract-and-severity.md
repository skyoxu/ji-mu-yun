# Finding 合同与严重等级

## 1. 四问事实门禁

每条候选 finding 在输出前必须回答：

1. 是否引用当前 revision 的精确 artifact、起止行和原文证据？
2. 是否给出 `输入/触发 → 必要状态 → 坏结果`？
3. 是否读取足够上下文，包括调用者/被调用者/测试或 authority/consumer/validator？
4. 严重等级是否能由可达影响而不是通用检查表辩护？

任一答案为否，finding 不得进入用户可见结果。

候选 confidence 必须不低于 `0.8`。confidence 只是必要条件，不替代三联证明，也不能把缺证据候选提升为 P2。

## 2. P0–P2 统一三联证明

P0、P1、P2 全部必须同时具有：

- 精确证据：当前 revision 的原文片段和精确行号；
- 失败场景：具体输入、必要状态和坏结果；
- 防护缺口：为什么现有 caller、validator、test、authority 或 recovery rule 没有拦住。

三缺一时直接删除。只有 finding 仍保留完整三联证明、但影响被证明较低时，才允许从 P0/P1 降级；不得用“可能存在风险”维持 P2。

## 3. 严重等级

| 等级 | 可辩护影响 | 典型处置 |
| --- | --- | --- |
| P0 | 当前可达的数据丢失、安全边界突破、不可恢复状态、错误 authority 导致不可逆实施，或计划无法安全启动 | 阻断；独立核验；修复后只复查变化证据 |
| P1 | 明确导致核心行为错误、兼容性破坏、验收无法成立、实施者执行错误任务或关键要求漏失 | 阻断；独立核验 |
| P2 | 明确、可复现、非阻断的行为或可维护性失败，且有命名 consumer 和坏结果 | advisory；不触发自动修复循环 |

不存在 P3/LOW finding。纯风格、偏好、建议和未来优化从 review finding 域排除，可进入独立 improvement backlog，但不得伪装成 P2。

## 4. 状态机

通过基本 shape 的 finding：`candidate` → `confirmed | advisory | refuted | unverified`。

未通过基本 shape 或事实门禁的原始候选不进入 finding 状态机，而是生成独立 `review-rejection.v1` 记录。

- rejection record：确定性门禁失败，不展示为 finding；
- `confirmed`：P0/P1 经独立 verifier 确认；
- `advisory`：通过门禁的 P2；
- `refuted`：有直接证据证明误报；
- `unverified`：一次核验无法判断；由独立 verifier/gateway 根据可信 policy 写入 `unverifiedClass=security|data_loss|other` 和 `unverifiedDisposition=blocking|manual_pause`，候选 reviewer 和 result producer 不得自行选择。security/data_loss 只能使用 blocking；other 只能使用 manual_pause；blocking 只能形成 blocked，manual_pause 只能形成 incomplete，且两类不能混入同一 result。

## 5. 零发现与失败层

- `findings=[]` 是合法 clean result；
- 不得设置 minimum finding count；
- reviewer 层失败或超时与“零 finding”不同，结果为 `incomplete`，不得宣告 clean；
- 因 `no-spec` 等明确 scope 条件不适用的 layer 写入 `skippedLayers[]` 及原因，不计为失败；
- clean 只表示所声明 scope 内未发现通过门禁的问题。

## 6. 机器字段

通过基本 shape 校验并进入事实门禁的 finding 以 [review-finding.v1.schema.json](schemas/review-finding.v1.schema.json) 为准。核心包括 `findingId`、`sourceReviewers[]`、`routeVersion`、artifact/line/evidence、failure tuple、contextRead、existingGuardAnalysis、severityRationale、fingerprint、authority revision 和 disposition。`endLine` 必须大于等于 `startLine`；P0/P1 不能使用 `advisory`，P2 不能使用 `confirmed` 或 `unverified`；`unverified` 必须具有 gateway-owned `unverifiedClass` 与 `unverifiedDisposition`。因缺字段或无效结构被拒绝的原始候选使用 [review-rejection.v1.schema.json](schemas/review-rejection.v1.schema.json)，避免为了记录拒绝原因而伪造缺失证明。

result 以 [review-result.v1.schema.json](schemas/review-result.v1.schema.json) 为准。`reviewProfile` 与 `policyRevision` 必须同时匹配 gateway execution context 已分配的 policy key，并解析到可信 policy snapshot；`requiredLayers` 是该 snapshot 的派生输出，不是 reviewer/result producer 可选择 profile 后缩小的自报范围。缺少 assignment、未知 policy、revision/profile 替换或派生集合不一致均 fail closed。

## 验收标准

- Given 任意 P0–P2 候选缺少三联证明之一，When validator 执行，Then finding 被拒绝。
- Given clean diff 或 clean 文档，When reviewer 无合格 finding，Then result schema 接受空数组。
- Given reviewer 层失败且无 finding，When汇总，Then结果是 `incomplete` 而不是 `clean`。
- Given result 声明 clean，When gateway 校验 layer 集合，Then `requiredLayers` 必须与 `completedLayers` 相同，且不得与 failed/skipped 重叠。
- Given producer 缩小 `requiredLayers`，When gateway 对照可信 `reviewProfile`/`policyRevision`，Then result 被拒绝。
- Given P0/P1 为 `unverified`，When result 汇总，Then `blocking` 只能对应 `blocked`，`manual_pause` 只能对应 `incomplete`。
