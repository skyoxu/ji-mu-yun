# 代码、文档与计划审查适配

## 1. 代码 adapter

contextRead 至少声明：变更行、相关 caller/callee、输入验证或类型收窄、现有测试。failure tuple 必须落到当前可达路径。以下不能单独构成 finding：文件/类大、函数长、重复、缺 interface、feature-local literal、缺 what 注释、框架已经处理的异常、caller 已验证的 internal input、固定基数循环、intentional fire-and-forget、非安全场景随机数。

## 2. 文档 adapter

代码的调用关系映射为文档 authority graph：

```text
精确条款
  -> authority owner
  -> consumer/执行者
  -> validator/验收
  -> 错误动作或不可验收结果
```

文档 finding 除共享字段外，必须声明 `authorityOwner`、`consumer` 和 `validatorRef`。以下不能单独构成 finding：措辞可更清晰、可以补充更多细节、未来工作尚无实现证据、计划 readiness 被误读为 code complete、重复其他 owner 的规则、格式/语气偏好、阶段允许的 TBD、无法构造 consumer bad outcome 的 schema 收紧建议。

## 3. Execution-plan adapter

Whole-directory review 额外检查：

- 完整读取目录 Markdown 与 `schemas/**`；
- Markdown link 和 JSON 可解析；
- schema/fixture 关系、字段、状态、动作、路径、术语一致；
- 96 历史 finding ledger 无 Open 项；
- 97 每条新增要求有 owner 与验收引用；
- 98/99 覆盖批准来源；
- 上游/后继计划只引用，不复制或冲突；
- review PASS 只代表计划可实施。

机械检查失败可直接产生 finding，但仍必须提供精确证据、失败场景和现有检查为何未拦住。

## 4. 严重等级映射

- 文档 P0：错误 authority、执行顺序或安全边界会导致不可逆/不安全实施；
- 文档 P1：明确使实现者做错、漏做关键工作或无法验收；
- 文档 P2：命名 consumer 会产生确定但非阻断的错误或维护失败；
- “更好看、更完整、更优雅”不进入 P0–P2。

## 5. 误报抑制清单维护

误报清单进入长期 standard，并允许 adapter 添加领域条目；删除或放宽条目必须有回归 fixture。清单不是忽略真实故障的白名单：只要候选提供完整三联证明并证明现有上下文不适用，仍可进入门禁。

## 6. 三层 reviewer adapter

### Blind Hunter

- 只把 diff-only 输出视为 hypothesis/candidate；
- 因为没有项目上下文，不能独立满足四问中的 caller/context/test 要求；
- adapter 必须重新读取精确位置、caller/callee、guard 和 tests，补齐三联证明后才能进入 P0–P2；
- 无法补齐时生成 rejection record，不允许用高 severity 弥补上下文缺失。

### Edge Case Hunter

- 将现有 `location`、`trigger_condition`、`guard_snippet`、`potential_consequence` 映射到统一 finding contract；
- adapter 仍须验证 location 属于当前 revision，并补齐 exactEvidence、requiredState、authorityRevision、confidence 和 evidenceFingerprint；
- 已被 guard 或 test 处理的路径直接 rejected。

### Acceptance Auditor

- 必须引用精确 AC/constraint、spec 行号、实现证据和 consumer/validator；
- “没有实现”只有在当前 spec 明确要求本次完成且实际 diff/状态缺失时才成立；
- planned、paused、后继阶段或由其他 owner 接管的要求不得作为当前 finding；
- Markdown 列表先转为结构化 candidate，不能直接写入 story、ledger 或 blocker。
- `no-spec` 模式下必须记录 `not_applicable_no_spec` skip reason；不得伪造空 Acceptance 结果，也不得把它计为 failed layer。

三个 adapter 均写入 `sourceReviewers[]`。同一证据由多个角色发现时合并来源，不增加 finding 数量或 severity。

## 验收标准

- Given 文档候选没有命名 consumer，When gateway 校验，Then拒绝。
- Given planned/paused 要求尚无代码，When 文档未声称代码完成，Then不得以“缺实现证据”产生 finding。
- Given code smell 没有当前可达失败，When reviewer 输出，Then不得进入 P2。
- Given Blind Hunter 只有 diff-only 推断，When无法补齐项目上下文，Then生成 rejection 而不是 P0–P2。
- Given 三个 reviewer 命中相同证据和失败链，When gateway dedup，Then产生一条 finding 且 `sourceReviewers[]` 保留全部来源。
