# Implementation Contracts

本 companion 提取原始能力草案 §15、§16、§17.2 的机器合同，供 Architecture 和实现直接消费。

## Stable CLI

```powershell
py -3 scripts/vdd/compile_plan.py --requirements <requirements-file> --out-dir <plan-dir> --profile standard
py -3 scripts/vdd/compile_plan.py --requirements <requirements-file> --out-dir <plan-dir> --recommendation-only
py -3 scripts/vdd/compile_plan.py --requirements <requirements-file> --out-dir <plan-dir> --resume-from first-failed-stage
py -3 scripts/quick_dev/run.py --plan <plan-dir> --slice <slice-id> --profile standard
py -3 scripts/quick_dev/run.py --plan <plan-dir> --slice <slice-id> --recommendation-only
```

CLI 必须使用参数数组、`shell=False`，路径限于仓库安全边界；recommendation-only 不调用模型、不运行测试、不创建 run、不写状态。

## Agent context projection

VDD 为每个 slice 确定性生成 `agent-context.json`，字段固定为：

```json
{
  "slice_id": "S...",
  "requirement_ids": [],
  "obligation_ids": [],
  "acceptance_ids": [],
  "source_refs": [],
  "contracts": [],
  "allowed_paths": [],
  "forbidden_paths": [],
  "selector_intents": [],
  "validation_commands": []
}
```

缺失字段、空 selector intent、不可解析 source/contract 或越界路径必须返回 `repair-vdd`，Quick Dev 不得重新读取整个需求目录猜测。

## Lifecycle transition contract

```text
planned-only
→ preflight-passed
→ red-materialized
→ red-observed
→ implementation-successor
→ green-observed
→ refactor-observed
→ slice-ready
→ whole-plan-terminal
```

禁止：planned-only/red-materialized 直接实现；非 expected-red 的 RED 进入实现；GREEN 失败进入 REFACTOR；缺局部 assertion 的 slice-ready 进入 terminal。每个 transition 由独立 deterministic predicate 判定。

## Machine-readable descriptor and observation schemas

Descriptor 至少包含 `run_id`、`plan_id`、`slice_id`、`stage`、`candidate_hash`、`argv[]`、`cwd`、`shell=false`、`timeout_seconds>0`、`target_refs`、`fixture_refs` 和 `acceptance_assertions[]`。Assertion edge 的完整绑定字段见 `schema-contracts.md`。

Receipt 至少记录 actual argv/cwd、开始/结束时间、`process_attempts`、`test_executions`、cases、`exit_code`（可为 null）、`timed_out`、stdout/stderr hash、candidate/descriptor/target/fixture hash、observed assertion/failure ID、profile identity 和 executor identity。Receipt/observation 的 `status` 不得由 producer 预填。超时、harness、target-binding 或 artifact failure 允许零 test executions、零 cases、零 assertion edge；只有成功的 RED/GREEN/REFACTOR 才要求 `test_executions>=1` 且 `cases>=1`。

## Deterministic algorithms

### Stable slice ID

按依赖拓扑顺序，将 `(production_owners[], verification_lane, lifecycle_stage, failure_family, state_transition, fixture/runtime compatibility)` 的规范化元组排序后分桶；按排序后的桶序分配稳定序号 `S1`, `S2`, …，并另存 `slice_input_hash` 作为内容承诺。相同输入必须产生相同 ID/partition；slice ID 不直接编码 hash。

### Selector semantic identity

规范化 `target_refs`、`fixture_refs`、`acceptance_assertions`、cwd、argv 选择器和 case-source refs，使用 canonical JSON 计算 identity hash。GREEN/REFACTOR 必须复用该 identity，不能因 stage/run/candidate successor 改变。

### Failure fingerprint and stage-aware classification

fingerprint 由 selector identity、target/fixture hash、stage、exit semantics、observed assertion IDs、failure family 和关键输出摘要构成。先按完整性优先级检查 `artifact-integrity → target-binding-failure → test-harness-failure → timeout-no-observation → repo-noise`；其后按阶段分类：RED 仅当非零且匹配 failure intent 才是 `expected-red`，GREEN/REFACTOR 的非零结果通常是 `task-implementation-failure`，terminal 非零按 semantic/terminal failure 归类；零退出但预期 RED 为 `unexpected-green`。相同 fingerprint 连续两次即 stop。

### Exact-cover traversal

从 active requirement 开始沿 `requirement→obligation→Acceptance→source→RED intent→slice→lane→terminal` 正向遍历，再反向遍历所有实体；缺任一边、孤立实体、无来源 intent 或未来 evidence 立即 fail closed。多对多覆盖 sound-and-complete，不要求 exclusive partition。

### Invalidation traversal

按 `schema-contracts.md` 矩阵计算受影响节点的传递闭包：selector/fixture/target/source 变化从 RED 重跑；production owner 变化至少重跑 GREEN/REFACTOR，语义变化回 RED；compiler/validator/predecessor 变化使其后继失效；普通非语义文档和 development governance artifact 默认可复用。

### Terminal predicate

逐一解析显式 predecessor，验证 plan/slice/candidate/run/hash/selector identity，重算 exact cover，重读 assertion edge，执行 terminal、profile regression 和 mutation；仅当全部 active Acceptance 通过且不存在 invalid/harness/repo-noise/timeout/unexpected-green 时产生 `implementation-complete`。

## Complete machine-readable schemas

以下 JSON Schema-like 合同是 normative；实现必须拒绝缺少 required 字段、类型不符、未知 enum 或违反 cross-field 约束的输入。`additionalProperties` 默认视为 `false`，扩展只能通过 companion 版本升级。

### Obligation

```json
{
  "type": "object",
    "additionalProperties": false,
    "required": ["obligation_id", "requirement_id", "source_refs", "subject", "trigger", "state_before", "state_after", "expected_behavior", "observable_result", "forbidden_result", "requirement_type", "obligation_kind", "unresolved_fragments", "status", "depends_on"],
  "properties": {
    "obligation_id": {"type": "string", "pattern": "^(O-[A-Z0-9-]+|FR-[0-9]+\\.[A-Z0-9]+|NFR-[0-9]+\\.[A-Z0-9]+|SM-[A-Z0-9-]+\\.[A-Z0-9]+)$"},
    "requirement_id": {"type": "string", "pattern": "^FR-[0-9]+$|^NFR-[0-9]+$|^SM-[A-Z0-9-]+$"},
    "source_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "subject": {"type": "string", "minLength": 1},
    "trigger": {"type": "string", "minLength": 1},
    "state_before": {"type": "string", "minLength": 1},
    "state_after": {"type": "string", "minLength": 1},
    "expected_behavior": {"type": "string", "minLength": 1},
    "observable_result": {"type": "string", "minLength": 1},
    "forbidden_result": {"type": "array", "items": {"type": "string"}},
    "requirement_type": {"enum": ["Product", "Platform", "Governance"]},
    "obligation_kind": {"enum": ["behavior", "quality", "constraint", "governance"]},
    "unresolved_fragments": {"type": "array", "items": {"type": "string"}},
    "status": {"enum": ["active", "deferred", "not_applicable"]},
    "depends_on": {"type": "array", "items": {"type": "string"}}
  }
}
```

### Acceptance

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["acceptance_id", "obligation_ids", "source_refs", "given", "when", "then", "oracle", "assertion_ids", "red_intent_ids"],
  "properties": {
    "acceptance_id": {"type": "string", "pattern": "^A-[A-Z0-9-]+$"},
    "obligation_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "source_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "given": {"type": "string", "minLength": 1},
    "when": {"type": "string", "minLength": 1},
    "then": {"type": "string", "minLength": 1},
    "oracle": {"type": "object", "additionalProperties": false, "required": ["observable", "expected", "forbidden"], "properties": {"observable": {"type": "string", "minLength": 1}, "expected": {"type": "string", "minLength": 1}, "forbidden": {"type": "array", "items": {"type": "string"}}}},
    "assertion_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "red_intent_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}
  }
}
```

### Failure intent

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["failure_intent_id", "acceptance_ids", "failure_id", "failure_family", "selector_intent", "expected_outcome"],
  "properties": {
    "failure_intent_id": {"type": "string", "pattern": "^FI-[A-Z0-9-]+$"},
    "acceptance_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "failure_id": {"type": "string", "pattern": "^[A-Z0-9-]+$"},
    "failure_family": {"enum": ["semantic-contract-gap", "artifact-integrity", "target-binding-failure", "test-harness-failure", "timeout-no-observation", "repo-noise", "unexpected-green", "expected-red", "task-implementation-failure", "repeated-deterministic-failure"]},
    "selector_intent": {"type": "string", "minLength": 1},
    "expected_outcome": {"const": "fail"}
  }
}
```

### Slice contract

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["slice_id", "slice_input_hash", "obligation_ids", "acceptance_ids", "failure_intent_ids", "production_owners", "verification_lane", "behavior_change", "affected_subjects", "state_transition", "proof", "rollback_scope", "allowed_write_paths", "execution_snapshot_paths", "planned_new_files", "terminal_predicate"],
  "properties": {
    "slice_id": {"type": "string", "pattern": "^S[0-9]+$"},
    "slice_input_hash": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
    "obligation_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "acceptance_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "failure_intent_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "production_owners": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1},
    "verification_lane": {"enum": ["unit", "integration", "matrix", "runtime"]},
    "behavior_change": {"type": "string", "minLength": 1},
    "affected_subjects": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "state_transition": {"type": "string", "minLength": 1},
    "proof": {"type": "object", "additionalProperties": false, "required": ["acceptance_ids", "selector_intents", "assertion_ids"], "properties": {"acceptance_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "selector_intents": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "assertion_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}}},
    "rollback_scope": {"type": "object", "additionalProperties": false, "required": ["production_paths", "state_or_schema_compatibility"], "properties": {"production_paths": {"type": "array", "items": {"type": "string"}}, "state_or_schema_compatibility": {"type": "string", "minLength": 1}}},
    "allowed_write_paths": {"type": "array", "items": {"type": "string"}},
    "execution_snapshot_paths": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "planned_new_files": {"type": "array", "items": {"type": "string"}},
    "terminal_predicate": {"type": "string", "minLength": 1}
  }
}
```

### Agent context

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["slice_id", "requirement_ids", "obligation_ids", "acceptance_ids", "source_refs", "contracts", "allowed_paths", "forbidden_paths", "selector_intents", "validation_commands"],
  "properties": {
    "slice_id": {"type": "string", "pattern": "^S[0-9]+$"},
    "requirement_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "obligation_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "acceptance_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "source_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "contracts": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "allowed_paths": {"type": "array", "items": {"type": "string"}},
    "forbidden_paths": {"type": "array", "items": {"type": "string"}},
    "selector_intents": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "validation_commands": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}, "minItems": 1}
  }
}
```

### Recommendation

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["plan_id", "plan_hash", "recommended_action", "forbidden_actions", "reason_code", "blocked_by", "reusable_observations", "invalidated_observations", "created_at"],
  "properties": {
    "plan_id": {"type": "string"},
    "plan_hash": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
    "recommended_action": {"enum": ["run-preflight", "author-red", "run-red", "implement", "run-green", "run-refactor", "validate-slice", "run-terminal", "repair-vdd", "stop", "environment-blocked"]},
    "forbidden_actions": {"type": "array", "items": {"type": "string"}},
    "reason_code": {"type": "string", "minLength": 1},
    "blocked_by": {"type": "array", "items": {"type": "string"}},
    "reusable_observations": {"type": "array", "items": {"type": "string"}},
    "invalidated_observations": {"type": "array", "items": {"type": "string"}},
    "created_at": {"type": "string", "format": "date-time"}
  }
}
```

### Descriptor

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["run_id", "plan_id", "slice_id", "stage", "candidate_hash", "argv", "cwd", "shell", "timeout_seconds", "target_refs", "fixture_refs", "acceptance_assertions"],
  "properties": {
    "run_id": {"type": "string", "pattern": "^RUN-[A-Z0-9-]+$"},
    "plan_id": {"type": "string"},
    "slice_id": {"type": "string", "pattern": "^S[0-9]+$"},
    "stage": {"enum": ["red", "green", "refactor", "terminal"]},
    "candidate_hash": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
    "argv": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "cwd": {"type": "string", "minLength": 1},
    "shell": {"const": false},
    "timeout_seconds": {"type": "number", "exclusiveMinimum": 0},
    "target_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "fixture_refs": {"type": "array", "items": {"type": "string"}},
    "acceptance_assertions": {"type": "array", "minItems": 1, "items": {"type": "object", "additionalProperties": false, "required": ["acceptance_id", "assertion_id", "expected_exit", "expected_failure_family"], "properties": {"acceptance_id": {"type": "string"}, "assertion_id": {"type": "string"}, "expected_exit": {"enum": ["zero", "nonzero"]}, "expected_failure_family": {"type": "string", "minLength": 1}}}}
  }
}
```

### Process receipt

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["receipt_id", "descriptor_ref", "argv", "cwd", "started_at", "ended_at", "process_attempts", "test_executions", "cases", "exit_code", "timed_out", "stdout_sha256", "stderr_sha256", "candidate_hash", "descriptor_sha256", "target_hashes", "fixture_hashes", "observed_assertion_ids", "observed_failure_ids", "profile_identity", "executor_identity"],
  "properties": {
    "receipt_id": {"type": "string", "pattern": "^RECEIPT-[A-Z0-9-]+$"},
    "descriptor_ref": {"type": "string"},
    "argv": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "cwd": {"type": "string"},
    "started_at": {"type": "string", "format": "date-time"},
    "ended_at": {"type": "string", "format": "date-time"},
    "process_attempts": {"type": "integer", "minimum": 1},
    "test_executions": {"type": "integer", "minimum": 0},
    "cases": {"type": "integer", "minimum": 0},
    "exit_code": {"type": ["integer", "null"]},
    "timed_out": {"type": "boolean"},
    "stdout_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
    "stderr_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
    "candidate_hash": {"type": "string"},
    "descriptor_sha256": {"type": "string"},
    "target_hashes": {"type": "object"},
    "fixture_hashes": {"type": "object"},
    "observed_assertion_ids": {"type": "array", "items": {"type": "string"}},
    "observed_failure_ids": {"type": "array", "items": {"type": "string"}},
    "profile_identity": {"type": "string"},
    "executor_identity": {"type": "string"}
  }
}
```

### Observation and assertion edge

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["observation_id", "receipt_ref", "stage", "exit_code", "process_attempts", "test_executions", "cases", "timed_out", "classification", "failure_family", "expected_exit", "expected_stage_outcome", "actual_stage_outcome", "predicate_result", "recommended_action", "assertion_edges"],
  "properties": {
    "observation_id": {"type": "string", "pattern": "^OBS-[A-Z0-9-]+$"},
    "receipt_ref": {"type": "string", "minLength": 1},
    "stage": {"enum": ["red", "green", "refactor", "terminal"]},
    "process_attempts": {"type": "integer", "minimum": 1},
    "test_executions": {"type": "integer", "minimum": 0},
    "cases": {"type": "integer", "minimum": 0},
    "exit_code": {"type": ["integer", "null"]},
    "timed_out": {"type": "boolean"},
    "classification": {"enum": ["expected-red", "unexpected-green", "task-implementation-failure", "semantic-contract-gap", "artifact-integrity", "target-binding-failure", "test-harness-failure", "timeout-no-observation", "repo-noise", "repeated-deterministic-failure", "terminal-failure", "pass"]},
    "failure_family": {"type": ["string", "null"]},
    "expected_exit": {"enum": ["zero", "nonzero"]},
    "expected_stage_outcome": {"enum": ["pass", "fail"]},
    "actual_stage_outcome": {"enum": ["pass", "fail"]},
    "predicate_result": {"type": "boolean"},
    "recommended_action": {"enum": ["run-preflight", "author-red", "run-red", "implement", "run-green", "run-refactor", "validate-slice", "run-terminal", "repair-vdd", "stop", "environment-blocked"]},
    "assertion_edges": {"type": "array", "minItems": 0, "items": {"$ref": "#/definitions/runtime_assertion_edge"}}
  }
}
```

`runtime_assertion_edge`（定义见下文）只能由 Quick Dev Q3–Q8 在运行后生成；observation 只能由 validator 从 receipt 派生。`observed=true`、`expected_stage_outcome`、`actual_stage_outcome`、`predicate_result` 不得由 descriptor、producer 或模型写入。每个 runtime edge 必须满足上述完整绑定字段及当前字节重读约束。VDD V5 仅生成 `pre_slice_coverage_edge`；V6A 在 slice partition 完成后才生成不含运行期 lineage 的最终 `plan_coverage_edge`。

Cross-field predicates：`process_attempts>=1`；`timed_out=true` 时 `exit_code=null` 且 classification=`timeout-no-observation`；`expected-red` 必须 `test_executions>=1`、cases≥1、非零 exit 且至少一条匹配 assertion edge；GREEN/REFACTOR/terminal 的 pass 必须 `test_executions>=1`、cases≥1、零 exit 且所有 bound assertions 为真。artifact-integrity、target-binding-failure、test-harness-failure、timeout-no-observation 可有 `test_executions=0`、cases=0、空 assertion edges，但 `predicate_result=false` 且 `recommended_action` 不得为 implement/run-green/run-refactor/validate-slice/run-terminal。诊断用途的 unconstrained exit expectation 只能进入独立非授权 diagnostic schema，不得进入 descriptor、receipt、observation 或授权 evidence。

`#/definitions/runtime_assertion_edge` 定义如下：

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["plan_id", "plan_hash", "slice_id", "candidate_hash", "observation_id", "acceptance_id", "assertion_id", "selector_identity", "stage", "run_id", "result_ref", "result_sha256", "observed", "expected_stage_outcome", "actual_stage_outcome", "predicate_result", "target_ref", "fixture_ref", "case_source_ref", "producer_identity", "validator_identity", "derived_by"],
  "properties": {
    "plan_id": {"type": "string"}, "plan_hash": {"type": "string"}, "slice_id": {"type": "string"}, "candidate_hash": {"type": "string"}, "observation_id": {"type": "string"}, "acceptance_id": {"type": "string"}, "assertion_id": {"type": "string"}, "selector_identity": {"type": "string"}, "stage": {"enum": ["red", "green", "refactor", "terminal"]}, "run_id": {"type": "string"}, "result_ref": {"type": "string"}, "result_sha256": {"type": "string"}, "observed": {"type": "boolean"}, "expected_stage_outcome": {"enum": ["pass", "fail"]}, "actual_stage_outcome": {"enum": ["pass", "fail"]}, "predicate_result": {"type": "boolean"}, "target_ref": {"type": "string"}, "fixture_ref": {"type": "string"}, "case_source_ref": {"type": "string"}, "producer_identity": {"type": "string"}, "validator_identity": {"type": "string"}, "derived_by": {"const": "deterministic-validator"}
  }
}
```

`#/definitions/pre_slice_coverage_edge` 定义如下；它只服务于 VDD V5 的 pre-slice semantic cover，不得包含 V6/V6A 才能确定的 slice、lane、terminal 或任何运行期字段：

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["requirement_id", "obligation_id", "acceptance_id", "source_ref", "failure_intent_id"],
  "properties": {
    "requirement_id": {"type": "string"},
    "obligation_id": {"type": "string"},
    "acceptance_id": {"type": "string"},
    "source_ref": {"type": "string"},
    "failure_intent_id": {"type": "string"}
  }
}
```

`#/definitions/plan_coverage_edge` 定义如下；它只由 V6A 在 slice partition 后生成最终 plan exact-cover，禁止运行期字段：

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["requirement_id", "obligation_id", "acceptance_id", "source_ref", "failure_intent_id", "slice_id", "verification_lane", "terminal_predicate", "stage_scope"],
  "properties": {
    "requirement_id": {"type": "string"},
    "obligation_id": {"type": "string"},
    "acceptance_id": {"type": "string"},
    "source_ref": {"type": "string"},
    "failure_intent_id": {"type": "string"},
    "slice_id": {"type": "string", "pattern": "^S[0-9]+$"},
    "verification_lane": {"enum": ["unit", "integration", "matrix", "runtime"]},
    "terminal_predicate": {"type": "string", "minLength": 1},
    "stage_scope": {"type": "array", "items": {"enum": ["red", "green", "refactor", "terminal"]}, "minItems": 4, "maxItems": 4, "uniqueItems": true}
  }
}
```

`stage_scope` 必须严格按唯一顺序 `["red", "green", "refactor", "terminal"]` 出现；不得省略、重复或重排阶段。

### Run state

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["run_id", "plan_id", "slice_id", "candidate_hash", "state", "predecessor_refs", "created_at", "updated_at"],
  "properties": {
    "run_id": {"type": "string", "pattern": "^RUN-[A-Z0-9-]+$"},
    "plan_id": {"type": "string"},
    "slice_id": {"type": "string", "pattern": "^S[0-9]+$"},
    "candidate_hash": {"type": "string"},
    "state": {"enum": ["planned-only", "preflight-passed", "red-materialized", "red-observed", "implementation-successor", "green-observed", "refactor-observed", "slice-ready", "whole-plan-terminal", "invalid-run", "recovered-run"]},
    "predecessor_refs": {"type": "array", "items": {"type": "string"}},
    "created_at": {"type": "string", "format": "date-time"},
    "updated_at": {"type": "string", "format": "date-time"}
  }
}
```

### Terminal input and result

```json
{
  "terminal_input": {
    "type": "object",
    "additionalProperties": false,
    "required": ["plan_id", "plan_hash", "candidate_hash", "run_id", "predecessors", "active_acceptance_ids", "terminal_selector_ref", "assertion_edge_refs", "profile_identity"],
    "properties": {
      "plan_id": {"type": "string"},
      "plan_hash": {"type": "string"},
      "candidate_hash": {"type": "string"},
      "run_id": {"type": "string"},
      "predecessors": {"type": "array", "minItems": 1, "items": {"type": "object", "additionalProperties": false, "required": ["slice_id", "run_id", "result_ref", "result_sha256"], "properties": {"slice_id": {"type": "string", "pattern": "^S[0-9]+$"}, "run_id": {"type": "string"}, "result_ref": {"type": "string"}, "result_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}}}},
      "active_acceptance_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
      "terminal_selector_ref": {"type": "string", "minLength": 1},
      "assertion_edge_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
      "profile_identity": {"type": "string"}
    }
  },
  "terminal_result": {
    "type": "object",
    "additionalProperties": false,
    "required": ["plan_id", "candidate_hash", "run_id", "status", "active_acceptance_ids", "evidence_ref", "evidence_root", "evidence_sha256", "validator_identity"],
    "properties": {
      "plan_id": {"type": "string"},
      "candidate_hash": {"type": "string"},
      "run_id": {"type": "string"},
      "status": {"const": "implementation-complete"},
      "active_acceptance_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
      "evidence_ref": {"type": "string", "minLength": 1},
      "evidence_root": {"type": "string", "minLength": 1},
      "evidence_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
      "validator_identity": {"type": "string", "minLength": 1}
    }
  }
}
```

Cross-schema constraints: all hashes must be recomputed from current bytes; a terminal result is valid only when its Acceptance set equals the active exact-cover set, every predecessor is observed, and all referenced run IDs share the same plan/candidate lineage.

### Source index, semantic alignment, coverage, feasibility, slice-ready and terminal-failure results

```json
{
  "source_index": {"type": "object", "additionalProperties": false, "required": ["sources"], "properties": {"sources": {"type": "array", "minItems": 1, "items": {"type": "object", "additionalProperties": false, "required": ["requirement_id", "path", "anchor", "source_text", "source_hash", "text_hash", "order"], "properties": {"requirement_id": {"type": "string"}, "path": {"type": "string"}, "anchor": {"type": "string"}, "source_text": {"type": "string", "minLength": 1}, "source_hash": {"type": "string"}, "text_hash": {"type": "string"}, "order": {"type": "integer", "minimum": 0}}}}}},
  "semantic_align_result": {"type": "object", "additionalProperties": false, "required": ["covered_ids", "missing_ids", "invented_semantics", "oracle_alignment", "repairs"], "properties": {"covered_ids": {"type": "array", "items": {"type": "string"}}, "missing_ids": {"type": "array", "items": {"type": "string"}}, "invented_semantics": {"type": "array", "items": {"type": "string"}}, "oracle_alignment": {"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["acceptance_id", "observable", "expected", "forbidden"], "properties": {"acceptance_id": {"type": "string"}, "observable": {"type": "string"}, "expected": {"type": "string"}, "forbidden": {"type": "array", "items": {"type": "string"}}}}}, "repairs": {"type": "array", "items": {"type": "string"}}}},
  "pre_slice_coverage_result": {"type": "object", "additionalProperties": false, "required": ["active_acceptance_ids", "edges", "orphan_ids", "hard_uncovered"], "properties": {"active_acceptance_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "edges": {"type": "array", "items": {"$ref": "#/definitions/pre_slice_coverage_edge"}, "minItems": 1}, "orphan_ids": {"type": "array", "items": {"type": "string"}}, "hard_uncovered": {"type": "array", "items": {"type": "string"}}}},
  "coverage_result": {"type": "object", "additionalProperties": false, "required": ["active_acceptance_ids", "edges", "orphan_ids", "hard_uncovered"], "properties": {"active_acceptance_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}, "edges": {"type": "array", "items": {"$ref": "#/definitions/plan_coverage_edge"}, "minItems": 1}, "orphan_ids": {"type": "array", "items": {"type": "string"}}, "hard_uncovered": {"type": "array", "items": {"type": "string"}}}},
  "feasibility_result": {"type": "object", "additionalProperties": false, "required": ["slice_id", "selector_target", "real_production_entry", "allowed_paths", "planned_new_files", "green_owner", "refactor_selector", "valid"], "properties": {"slice_id": {"type": "string"}, "selector_target": {"type": "string"}, "real_production_entry": {"type": "string"}, "allowed_paths": {"type": "array", "items": {"type": "string"}}, "planned_new_files": {"type": "array", "items": {"type": "string"}}, "green_owner": {"type": "string"}, "refactor_selector": {"type": "string"}, "valid": {"type": "boolean"}}},
  "slice_ready_result": {"type": "object", "additionalProperties": false, "required": ["plan_id", "plan_hash", "slice_id", "candidate_hash", "red_observation", "green_observation", "refactor_observation", "assertion_edge_refs", "predecessor_refs", "dependency_closure_hash", "selector_identity", "validator_identity", "status"], "properties": {"plan_id": {"type": "string"}, "plan_hash": {"type": "string"}, "slice_id": {"type": "string"}, "candidate_hash": {"type": "string"}, "red_observation": {"type": "object", "additionalProperties": false, "required": ["run_id", "ref", "sha256"], "properties": {"run_id": {"type": "string"}, "ref": {"type": "string"}, "sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}}}, "green_observation": {"type": "object", "additionalProperties": false, "required": ["run_id", "ref", "sha256"], "properties": {"run_id": {"type": "string"}, "ref": {"type": "string"}, "sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}}}, "refactor_observation": {"type": "object", "additionalProperties": false, "required": ["run_id", "ref", "sha256"], "properties": {"run_id": {"type": "string"}, "ref": {"type": "string"}, "sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}}}, "assertion_edge_refs": {"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["ref", "sha256"], "properties": {"ref": {"type": "string"}, "sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}}}, "minItems": 1}, "predecessor_refs": {"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["slice_id", "run_id", "ref", "sha256"], "properties": {"slice_id": {"type": "string"}, "run_id": {"type": "string"}, "ref": {"type": "string"}, "sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}}}}, "dependency_closure_hash": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}, "selector_identity": {"type": "string"}, "validator_identity": {"type": "string", "minLength": 1}, "status": {"const": "slice-ready"}}},
  "terminal_failure_result": {"type": "object", "additionalProperties": false, "required": ["plan_id", "run_id", "candidate_hash", "classification", "failure_family", "failed_predecessors", "recommended_action"], "properties": {"plan_id": {"type": "string"}, "run_id": {"type": "string"}, "candidate_hash": {"type": "string"}, "classification": {"enum": ["semantic-contract-gap", "artifact-integrity", "target-binding-failure", "test-harness-failure", "timeout-no-observation", "repo-noise", "unexpected-green", "task-implementation-failure", "repeated-deterministic-failure", "terminal-failure"]}, "failure_family": {"type": "string"}, "failed_predecessors": {"type": "array", "items": {"type": "string"}}, "recommended_action": {"enum": ["repair-vdd", "repair-quick-dev", "stop"]}}}
}
```

## VDD V0–V7 transition matrix

| 状态 | 输入 | 成功前置 predicate | 成功输出/转移 | 失败输出/转移 | 创建证据 | owner |
| --- | --- | --- | --- | --- | --- | --- |
| V0 source-index | requirements + normative companions | 路径、anchor、source/text hash 可解析且唯一 | source-index → V0A | `repair-vdd`（source missing/ambiguous） | source-index | VDD |
| V0A source preflight | source-index | 编码可读、requirements 可定位、基础 observability/lane 条件满足 | → V1 | `repair-vdd`；不调用模型 | preflight recommendation | VDD |
| V1 obligation-extract | frozen source set | read-only worker 输出 schema-valid obligations | → V2 | `repair-vdd`（schema/worker） | obligation extraction | VDD |
| V2 obligation-guard | obligations | source refs、语义五元组、ID、requirement coverage 完整 | → V3 | `repair-vdd`（hard-uncovered） | guard result | VDD |
| V3 acceptance-compile | guarded obligations | given/when/then/oracle、forbidden、assertion 与 RED intent 完整 | → V3A | `repair-vdd`（acceptance-incomplete） | Acceptance graph | VDD |
| V3A semantic-plan preflight | Acceptance + RED candidates | observability、orphan、overbroad、lane mismatch、terminal swallowing 和 exact-cover 初检通过 | → V4 | `repair-vdd` | semantic-plan preflight | VDD |
| V4 semantic-align | frozen sources + graph | 独立 worker 无 invented semantics，覆盖/冲突显式 | → V5 | `semantic_ambiguous`/`repair-vdd` | align result | VDD |
| V5 pre-slice semantic cover | aligned graph | requirement ↔ obligation ↔ Acceptance ↔ source ref ↔ RED intent 双向覆盖、无 orphan/hard-uncovered；不要求 slice/lane/terminal | → V6 | `repair-vdd` | pre-slice coverage result | VDD |
| V6 slice-partition | pre-slice cover + owners/lanes | deterministic bucket、write/snapshot/new-file 可行，必要时拆分 | → V6A | `repair-vdd` | slice contracts | VDD |
| V6A final plan exact-cover | slice contracts + pre-slice cover | 将每条 pre-slice edge 绑定到合法 slice、verification lane、terminal predicate 与完整唯一 stage scope；sound-and-complete many-to-many、无 orphan/hard-uncovered | → V7 | `repair-vdd` | final coverage result (`plan_coverage_edge`) | VDD |
| V7 feasibility | slices + real entries | selector 可达、真实 production entry、GREEN/REFACTOR 可行 | `plan-ready` | `repair-vdd` | feasibility result | VDD |

## Quick Dev Q0–Q8 transition matrix

| 状态 | 输入 | 成功前置 predicate | 成功输出/转移 | 失败输出/转移 | 创建 run/evidence | owner |
| --- | --- | --- | --- | --- | --- | --- |
| Q0 recommendation | current plan/slice/candidate/run refs | recommendation-only side-effect-free read and reusable/invalidated observation calculation | `recommended_action` → corresponding Q1/Q2/Q3/Q4/Q5/Q6/Q7/Q8 action or repair/stop | remain Q0; no execution | recommendation result only | Quick Dev |
| Q1 preflight | plan + slice contract + environment | schema, refs, failure intent, target/fixture/cwd, argv, timeout, write-set and probe valid | `preflight-passed` → Q2 | `repair-vdd`, `author-red` or `environment-blocked` | preflight result | Quick Dev |
| Q2 RED author/materialize | slice contract + RED intent | test write set only; real production entry; descriptor schema-valid | `red-materialized` → Q3 | remain Q2; no implementation | descriptor | Quick Dev |
| Q3 RED execute/classify | red descriptor | process executes; expected nonzero and exact failure ID; no harness/noise/timeout | `red-observed` → Q4 | `invalid-run`/`unexpected-green`/failure route | run, receipt, observation | executor + deterministic validator |
| Q4 production implementation | clean red-observed + write set | changed paths confined; selector/fixtures/contracts/evidence untouched | `implementation-successor` → Q5 | remain Q4; invalidate successor | successor snapshot | production owner |
| Q5 GREEN | red-observed + successor | same selector identity and target/fixture/assertions; test_executions≥1; cases≥1; exit 0; all bound assertions true | `green-observed` → Q6 | remain Q5; task failure/invalidate | GREEN receipt/observation | Quick Dev |
| Q6 REFACTOR | green-observed | same selector; production-only writes; regression/schema validators pass | `refactor-observed` → Q7 | remain Q6; invalidate from GREEN or RED as required | REFACTOR receipt/observation | Quick Dev |
| Q7 slice-ready | refactor-observed | all local `runtime_assertion_edge` refs and hashes/lineage valid | `slice-ready` → next slice or Q8 | remain Q7; invalidate affected stage only | slice-ready result | deterministic validator |
| Q8 terminal | all slice-ready predecessors + terminal input | plan coverage exact cover plus runtime assertion edges, explicit predecessor mapping, current hashes, terminal/regression/mutation pass | `whole-plan-terminal` | terminal failure result; never pass | terminal result/failure | deterministic terminal validator |

No transition may be inferred from file existence, self-reported status, stale hashes, or a producer-generated outcome. Q2–Q8 append evidence; historical invalid runs remain immutable and cannot serve as current predecessors. A Q7 failure does not destroy valid RED/GREEN lineage unless the invalidation matrix marks those predecessors affected.

## Semantic worker contract

obligation extract、Acceptance compile 和 semantic align 的 worker 必须 read-only、输入范围受限、单 requirement 或受 token 上限的小批次；wrapper 记录 model/version、prompt version、input/prompt hash、耗时和退出状态，结构化 JSON Schema 输出。schema error 只允许一次定向 schema repair；相同 fingerprint 第二次失败即停止。两个 semantic worker 的解释过程彼此不可见，冲突输出 `semantic_ambiguous`，交由 VDD/用户决策，不得静默选择。

## Detached fixture and mutation matrix

| failure family | blocked fixture | blocked command | blocked subject exit | blocked lifecycle gate exit | blocked fixture assertion exit | blocked classification | corrected fixture | corrected command | corrected subject exit | corrected lifecycle gate exit | corrected fixture assertion exit | corrected classification | 禁止后继状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| semantic-contract-gap | 缺字段/冲突 schema manifest | `py -3 scripts/quick_dev/run.py --plan <plan> --slice <slice>` | nonzero | nonzero | zero/none | semantic-contract-gap | 完整 schema-valid manifest | same command | zero | zero | zero | pass | implementation-successor/green |
| artifact-integrity | 篡改 descriptor/receipt/result hash | `py -3 scripts/quick_dev/validate_artifacts.py --run <run>` | zero/any | nonzero | zero/none | artifact-integrity | 当前字节可重算且匹配 | same command | zero | zero | zero | pass | slice-ready/terminal |
| target-binding-failure | target 或 fixture ref 错误 | `py -3 scripts/quick_dev/run.py --plan <plan> --slice <slice>` | zero/any | nonzero | zero/none | target-binding-failure | 冻结 target/fixture refs | same command | zero | zero | zero | pass | implementation-successor/green |
| test-harness-failure | 缺 runner、导入错误、零 executions | `py -3 scripts/quick_dev/stage_command.py --stage red --slice <slice>` | nonzero/any | nonzero | zero/none | test-harness-failure | 可执行真实 runner但行为缺口仍在 | same command | nonzero | zero | zero | expected-red | expected-red/implementation |
| timeout-no-observation | 进程超时或无 observation | `py -3 scripts/quick_dev/stage_command.py --stage red --slice <slice>` | timeout/null | nonzero | zero/none | timeout-no-observation | 在 timeout 内产生 receipt/observation | same command | nonzero | zero | zero | expected-red | expected-red/implementation |
| repo-noise | 无关测试失败或噪声污染观察 | `py -3 scripts/quick_dev/stage_command.py --stage red --slice <slice>` | nonzero/any | nonzero | zero/none | repo-noise | 隔离干净 snapshot 中仅目标行为执行且行为缺口仍在 | same command | nonzero | zero | zero | expected-red | slice-ready/terminal |
| unexpected-green | RED selector 零退出或无 expected failure ID | `py -3 scripts/quick_dev/stage_command.py --stage red --slice <slice>` | zero | nonzero | zero/none | unexpected-green | 同 selector 真实行为缺口 | same command | nonzero | zero | zero | expected-red | implementation-successor |
| expected-red | 真实行为缺口且精确 failure ID | `py -3 scripts/quick_dev/stage_command.py --stage red --slice <slice>` | nonzero | zero | zero | expected-red | 实现后同 selector 通过 | `py -3 scripts/quick_dev/stage_command.py --stage green --slice <slice>`（selector identity 完全相同） | zero | zero | zero | pass | green-before-red |
| task-implementation-failure | GREEN/REFACTOR 非零或断言失败 | `py -3 scripts/quick_dev/stage_command.py --stage green --slice <slice>` | nonzero | nonzero | zero/none | task-implementation-failure | 生产实现满足 assertions | same command | zero | zero | zero | pass | refactor/slice-ready |
| repeated-deterministic-failure | 相同 fingerprint 连续失败两次 | `py -3 scripts/quick_dev/run.py --plan <plan> --slice <slice> --profile standard`（相同命令执行两次） | nonzero | nonzero | zero/none | repeated-deterministic-failure | 修复输入或明确 repair 路由 | 输入变化后以新 fingerprint 重跑；输入未变化不得第三次执行原参数 | zero/repair | zero | zero | pass/repair | 原参数第三次重跑 |

另外必须覆盖以下反假绿变异：复制 registry expected failure/outcome、producer 自报 pass/status、缩小 case 集或替换 selector、缺 predecessor/错 run/hash/历史 glob 或 mtime 扫描、删除 assertion edge 或 terminal 吞并 Acceptance、profile 跳过动态执行或复用错误 selector。所有变异均须由独立只读 validator 拒绝。`expected-red` 行表示合法的 pre-implementation RED，不是被 validator 拒绝的 blocked fixture；其 corrected 侧必须是同 selector 的实现后通过。

`repeated-deterministic-failure` 的 corrected 侧只有在输入确实变化并产生新 fingerprint 时才允许重跑；输入字节、selector、profile 与依赖均未变化时，生命周期必须直接输出 `repair-vdd` 或 `stop`，不得执行第三次原参数命令。

detached fixtures 与被测 Quick Dev 使用独立目录/提交和只读 judge；独立 judge 只在 `self-hosted`/toolchain acceptance profile 强制，普通 fast-ship/standard 任务仍必须满足同一 truth floor。
