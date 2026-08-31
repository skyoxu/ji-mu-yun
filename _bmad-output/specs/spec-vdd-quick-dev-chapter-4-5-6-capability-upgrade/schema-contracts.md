# Normative Schema and Invalidation Contracts

## Plan coverage edge and runtime assertion edge

VDD V5 只生成计划期 `plan_coverage_edge`；Quick Dev Q3–Q8 才能生成运行期 `runtime_assertion_edge`。两者不可互换。

### Plan coverage edge

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["requirement_id", "obligation_id", "acceptance_id", "source_ref", "failure_intent_id", "slice_id", "verification_lane", "terminal_predicate", "stage_scope"],
  "properties": {
    "requirement_id": "...",
    "obligation_id": "...",
    "acceptance_id": "A-...",
    "source_ref": "...",
    "failure_intent_id": "FI-...",
    "slice_id": "S...",
    "verification_lane": "unit|integration|matrix|runtime",
    "terminal_predicate": "...",
    "stage_scope": ["red", "green", "refactor", "terminal"]
  }
}
```

Plan coverage edge 禁止出现 `candidate_hash`、`run_id`、`observation_id`、`result_ref`、`result_sha256`、实际 outcome 或 producer/validator identity。

### Runtime assertion edge

每个 Acceptance 的每条运行期 observation edge 使用以下语义字段：

```json
{
  "plan_id": "PLAN-...",
  "plan_hash": "sha256:...",
  "slice_id": "S...",
  "candidate_hash": "sha256:...",
  "observation_id": "OBS-...",
  "acceptance_id": "A-...",
  "assertion_id": "ASSERT-...",
  "selector_identity": "sha256:...",
  "stage": "red|green|refactor|terminal",
  "run_id": "RUN-...",
  "result_ref": "...",
  "result_sha256": "sha256:...",
  "observed": true,
  "expected_stage_outcome": "pass|fail",
  "actual_stage_outcome": "pass|fail",
  "predicate_result": true,
  "target_ref": "...",
  "fixture_ref": "...",
  "case_source_ref": "...",
  "producer_identity": "...",
  "validator_identity": "...",
  "derived_by": "deterministic-validator"
}
```

硬规则：`plan_id`/`plan_hash`、`slice_id`、`candidate_hash`、`observation_id`、`acceptance_id`、`assertion_id`、`selector_identity`、`run_id`、`result_ref`、`result_sha256`、producer/validator identity 必须可重读匹配当前 artifact。`expected_stage_outcome` 是该 stage 合同预期（RED 通常为 fail，GREEN/REFACTOR/terminal 通常为 pass），`actual_stage_outcome` 是 receipt/断言实际结果，`predicate_result` 是 validator 对二者及其余约束的确定性判定；三者不得混用。`observed`、`actual_stage_outcome`、`predicate_result` 只能由真实 observation validator 派生。target、fixture、case source 必须直接绑定或引用独立 receipt；同一 selector 覆盖多个 Acceptance 时每个 Acceptance 必须有独立 assertion edge。

`result_ref` 必须指向已物化且不可变的 process receipt 或独立 observation input。assertion edge 不得嵌入它所 hash 的 observation/receipt 本体，也不得通过自引用计算 `result_sha256`；coverage edge 位于 observation 外部时只能引用 immutable observation。

## Invalidation matrix

| 变化 | 必须失效/动作 |
| --- | --- |
| requirement、obligation、Acceptance、source ref | 重算 coverage；重跑受语义影响的 RED/GREEN/REFACTOR 和 terminal |
| selector、fixture、target、case source | 对应 slice 的 RED/GREEN/REFACTOR/terminal 全部失效，从 RED 重新执行 |
| production owner code | 至少重跑 GREEN/REFACTOR；若 failure intent 或 expected behavior 语义变化，从 RED 重跑 |
| descriptor compiler/materializer | 其生成的 descriptor 与所有后继 receipt/observation 失效 |
| validator/judge | 其判断的结果必须重验，必要时重新执行 |
| predecessor result | 直接下游 slice 和 terminal 失效 |
| 普通非语义文档 | observation 可复用 |
| development governance artifact | 不影响 TDD 路由或真实性 predicate |

不确定时采用更严格动作（重跑而非仅重算 coverage）。失效结果保留为历史但不得作为当前 predecessor。

## Execution profile truth floor

`fast-ship` 可减少受影响范围，`standard` 执行完整 slice terminal/负例/mutation，`self-hosted` 增加冻结 predecessor judge 和完整反假绿套件。所有 profile 必须真实执行；成功 RED/GREEN/REFACTOR/terminal 要求 `process_attempts>=1`、`test_executions>=1`、`cases>=1`，保留 RED→GREEN→REFACTOR 顺序、exact cover、selector binding、receipt 中的 profile identity 和同输入同 profile 的确定性重放；任何 profile 不得用静态检查替代动态执行。
