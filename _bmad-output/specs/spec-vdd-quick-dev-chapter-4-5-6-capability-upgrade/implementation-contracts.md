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

Receipt 至少记录 actual argv/cwd、开始/结束时间、exit code、executions/cases、stdout/stderr hash、candidate/descriptor/target/fixture hash、observed assertion/failure ID、profile identity 和 executor identity。Receipt/observation 的 `status` 不得由 producer 预填。

## Deterministic algorithms

### Stable slice ID

按依赖拓扑顺序，将 `(production_owner, verification_lane, lifecycle_stage, failure_family, state_transition, fixture/runtime compatibility)` 的规范化元组排序后分桶；以输入内容 hash 和桶内首个稳定 Acceptance ID 生成 slice ID。相同输入必须产生相同 ID/partition。

### Selector semantic identity

规范化 `target_refs`、`fixture_refs`、`acceptance_assertions`、cwd、argv 选择器和 case-source refs，使用 canonical JSON 计算 identity hash。GREEN/REFACTOR 必须复用该 identity，不能因 stage/run/candidate successor 改变。

### Failure fingerprint and precedence

fingerprint 由 selector identity、target/fixture hash、stage、exit semantics、observed assertion IDs、failure family 和关键输出摘要构成。分类优先级为：artifact-integrity → target-binding-failure → test-harness-failure → timeout-no-observation → repo-noise → unexpected-green → expected-red → task-implementation-failure。相同 fingerprint 连续两次即 stop。

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
  "required": ["obligation_id", "requirement_id", "source_refs", "kind", "status", "depends_on"],
  "properties": {
    "obligation_id": {"type": "string", "pattern": "^O-[A-Z0-9-]+$"},
    "requirement_id": {"type": "string", "pattern": "^FR-[0-9]+$|^NFR-[0-9]+$|^SM-[A-Z0-9-]+$"},
    "source_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "kind": {"enum": ["behavior", "quality", "constraint", "governance"]},
    "status": {"enum": ["active", "deferred", "not_applicable"]},
    "depends_on": {"type": "array", "items": {"type": "string"}}
  }
}
```

### Acceptance

```json
{
  "type": "object",
  "required": ["acceptance_id", "obligation_ids", "source_refs", "observable", "expected", "forbidden", "red_intent_ids"],
  "properties": {
    "acceptance_id": {"type": "string", "pattern": "^A-[A-Z0-9-]+$"},
    "obligation_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "source_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "observable": {"type": "string", "minLength": 1},
    "expected": {"type": "string", "minLength": 1},
    "forbidden": {"type": "array", "items": {"type": "string"}},
    "red_intent_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}
  }
}
```

### Failure intent

```json
{
  "type": "object",
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
  "required": ["slice_id", "obligation_ids", "acceptance_ids", "failure_intent_ids", "production_owner", "verification_lane", "allowed_write_paths", "execution_snapshot_paths", "planned_new_files", "terminal_predicate"],
  "properties": {
    "slice_id": {"type": "string", "pattern": "^S[0-9]+$"},
    "obligation_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "acceptance_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "failure_intent_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "production_owner": {"type": "string", "minLength": 1},
    "verification_lane": {"enum": ["pytest", "semantic-oracle", "coverage", "independent-judge", "terminal"]},
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
  "required": ["plan_id", "plan_hash", "recommendation", "reasons", "created_at"],
  "properties": {
    "plan_id": {"type": "string"},
    "plan_hash": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
    "recommendation": {"enum": ["proceed", "repair-vdd", "repair-quick-dev", "stop"]},
    "reasons": {"type": "array", "items": {"type": "string"}},
    "created_at": {"type": "string", "format": "date-time"}
  }
}
```

### Descriptor

```json
{
  "type": "object",
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
    "acceptance_assertions": {"type": "array", "items": {"type": "string"}, "minItems": 1}
  }
}
```

### Process receipt

```json
{
  "type": "object",
  "required": ["receipt_id", "descriptor_ref", "argv", "cwd", "started_at", "ended_at", "exit_code", "executions", "cases", "stdout_sha256", "stderr_sha256", "candidate_hash", "descriptor_sha256", "target_hashes", "fixture_hashes", "observed_assertion_ids", "observed_failure_ids", "profile_identity", "executor_identity"],
  "properties": {
    "receipt_id": {"type": "string", "pattern": "^RECEIPT-[A-Z0-9-]+$"},
    "descriptor_ref": {"type": "string"},
    "argv": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "cwd": {"type": "string"},
    "started_at": {"type": "string", "format": "date-time"},
    "ended_at": {"type": "string", "format": "date-time"},
    "exit_code": {"type": "integer"},
    "executions": {"type": "integer", "minimum": 1},
    "cases": {"type": "integer", "minimum": 0},
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
  "required": ["observation_id", "receipt_ref", "stage", "exit_code", "executions", "cases", "assertion_edges"],
  "properties": {
    "observation_id": {"type": "string", "pattern": "^OBS-[A-Z0-9-]+$"},
    "receipt_ref": {"type": "string", "minLength": 1},
    "stage": {"enum": ["red", "green", "refactor", "terminal"]},
    "exit_code": {"type": "integer"},
    "executions": {"type": "integer", "minimum": 1},
    "cases": {"type": "integer", "minimum": 0},
    "assertion_edges": {"type": "array", "items": {"type": "object"}, "minItems": 1}
  }
}
```

`schema-contracts.md` 第 3 节的字段集合即为每条 assertion edge 的 canonical schema；observation 只能由 validator 从 receipt 派生。`observed=true`、`outcome`、`actual_outcome` 不得由 descriptor、producer 或模型写入。每个 edge 必须满足上述完整绑定字段及当前字节重读约束。

### Run state

```json
{
  "type": "object",
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
    "required": ["plan_id", "plan_hash", "candidate_hash", "run_id", "slice_ids", "predecessor_refs", "assertion_edge_refs", "profile_identity"],
    "properties": {
      "plan_id": {"type": "string"},
      "plan_hash": {"type": "string"},
      "candidate_hash": {"type": "string"},
      "run_id": {"type": "string"},
      "slice_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
      "predecessor_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
      "assertion_edge_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
      "profile_identity": {"type": "string"}
    }
  },
  "terminal_result": {
    "type": "object",
    "required": ["plan_id", "candidate_hash", "run_id", "status", "acceptance_ids", "evidence_sha256", "validator_identity"],
    "properties": {
      "plan_id": {"type": "string"},
      "candidate_hash": {"type": "string"},
      "run_id": {"type": "string"},
      "status": {"const": "implementation-complete"},
      "acceptance_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
      "evidence_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
      "validator_identity": {"type": "string", "minLength": 1}
    }
  }
}
```

Cross-schema constraints: all hashes must be recomputed from current bytes; a terminal result is valid only when its Acceptance set equals the active exact-cover set, every predecessor is observed, and all referenced run IDs share the same plan/candidate lineage.

## Q0–Q8 transition matrix

| 状态 | 输入 | 成功前置 predicate | 成功输出/转移 | 失败输出/转移 | 创建 run/evidence | owner |
| --- | --- | --- | --- | --- | --- | --- |
| Q0 source intake | requirements + adopted companions | sources readable, hashes captured, no missing required companion | frozen source set → Q1 | `repair-vdd` with missing/ambiguous refs | no run; source-freeze evidence | VDD |
| Q1 obligation extraction | frozen source set | every active obligation has ID, source, type, dependency | obligation graph → Q2 | `repair-vdd` (`hard-uncovered`) | semantic extraction evidence | VDD |
| Q2 Acceptance compile | obligation graph | each active Acceptance observable/expected/forbidden and linked to RED intent | Acceptance graph → Q3 | `repair-vdd` (`acceptance-incomplete`) | semantic compile evidence | VDD |
| Q3 slice planning | Acceptance graph + owners/lanes | sound-and-complete many-to-many cover; exact write/snapshot/new-file paths | slice contracts + agent contexts → Q4 | `repair-vdd` (`orphan`/`write-set-invalid`) | plan artifact, no execution run | VDD |
| Q4 recommendation/preflight | plan + current candidate | schema, hashes, cwd, profile and safety predicates pass; recommendation-only side-effect free | `preflight-passed` → Q5 | `repair-vdd` or `stop`; remain Q4 | preflight evidence only; run not created in recommendation-only | Quick Dev |
| Q5 RED materialization/observation | slice contract + descriptor intent | descriptor compiled by Quick Dev; process executes; non-zero and exact expected failure ID observed | `red-observed` → Q6 | `invalid-run`/`unexpected-green`/`harness-failure`; no implementation | new run + descriptor/receipt/observation | Quick Dev executor + deterministic validator |
| Q6 implementation successor/GREEN | red-observed + allowed write set | successor hash is descendant; same selector identity; GREEN exit 0 and positive path 0 | `green-observed` → Q7 | remain Q6; invalidate successor/evidence | successor + receipt/observation | Quick Dev + production owner |
| Q7 REFACTOR/slice-ready | green-observed | REFACTOR same selector, write-set and regression predicates pass; all slice Acceptance edges observed | `slice-ready` → Q8 (or next slice) | invalidate from RED; remain Q7 | refactor receipt/observation + slice-ready result | Quick Dev + validator |
| Q8 terminal | all slice-ready predecessors + terminal input | exact cover, lineage, current hashes, terminal/regression/mutation and profile predicates pass | `whole-plan-terminal` with implementation-complete | remain Q8; emit repair/invalid result, never pass | terminal evidence/result | deterministic terminal validator |

No transition may be inferred from file existence, self-reported status, stale hashes, or a producer-generated outcome. Q5–Q8 must append evidence; historical invalid runs remain immutable and cannot serve as current predecessors.

## Semantic worker contract

obligation extract、Acceptance compile 和 semantic align 的 worker 必须 read-only、输入范围受限、单 requirement 或受 token 上限的小批次；wrapper 记录 model/version、prompt version、input/prompt hash、耗时和退出状态，结构化 JSON Schema 输出。schema error 只允许一次定向 schema repair；相同 fingerprint 第二次失败即停止。两个 semantic worker 的解释过程彼此不可见，冲突输出 `semantic_ambiguous`，交由 VDD/用户决策，不得静默选择。

## Detached fixture and mutation matrix

| 类别 | 必须覆盖的反假绿行为 | 预期 |
| --- | --- | --- |
| positive | 正确 target、fixture、assertion 和真实生产入口 | pass |
| negative | 错误 target、缺 case、非零/零退出语义错配 | fail closed |
| mutation-expected-copy | 复制 registry expected failure/outcome | rejected |
| mutation-self-report | producer 自报 pass/status | rejected |
| mutation-selector | 缩小 case 集、替换入口或改变 selector | rejected |
| mutation-lineage | 缺 predecessor、错 run/hash、历史 glob/mtime 扫描 | rejected |
| mutation-coverage | 删除 edge、terminal 吞并 Acceptance、未来 evidence | rejected |
| mutation-profile | profile 跳过动态执行或同 selector GREEN | rejected |

detached fixtures 与被测 Quick Dev 使用独立目录/提交和只读 judge；独立 judge 只在 `self-hosted`/toolchain acceptance profile 强制，普通 fast-ship/standard 任务仍必须满足同一 truth floor。
