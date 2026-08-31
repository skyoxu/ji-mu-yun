# Normative Schema and Invalidation Contracts

## Pre-slice coverage edge, plan coverage edge and runtime assertion edge

VDD V5 只生成 `pre_slice_coverage_edge`；V6A 在 slice partition 后生成最终 `plan_coverage_edge`；Quick Dev Q3–Q8 才能生成运行期 `runtime_assertion_edge`。三者不可互换。

### Pre-slice coverage edge

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["requirement_id", "obligation_id", "acceptance_id", "source_ref", "failure_intent_id"],
  "properties": {
    "requirement_id": "...",
    "obligation_id": "...",
    "acceptance_id": "A-...",
    "source_ref": "...",
    "failure_intent_id": "FI-..."
  }
}
```

V5 的 pre-slice edge 禁止 `slice_id`、`verification_lane`、`terminal_predicate`、`stage_scope` 以及任何 candidate/run/observation/result hash 字段。

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

最终 `plan_coverage_edge.stage_scope` 必须严格为唯一且有序的 `["red", "green", "refactor", "terminal"]`；实现 schema validator 时应同时执行顺序相等检查，不能仅依赖 `minItems`。

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
  "receipt_ref": "...",
  "receipt_sha256": "sha256:...",
  "observation_ref": "...",
  "observation_sha256": "sha256:...",
  "descriptor_sha256": "sha256:...",
  "target_sha256": "sha256:...",
  "fixture_sha256": "sha256:...",
  "observed": true,
  "expected_stage_outcome": "pass|fail",
  "actual_stage_outcome": "pass|fail",
  "predicate_result": true,
  "verification_outcome": "pass|fail|blocked|incomplete|not-applicable",
  "failure_family": "...|null",
  "failure_id": "...|null",
  "target_ref": "...",
  "fixture_ref": "...",
  "case_source_ref": "...",
  "producer_identity": "...",
  "validator_identity": "...",
  "derived_by": "deterministic-validator"
}
```

硬规则：上述 receipt/observation/descriptor/target/fixture 哈希与 `plan_id`/`plan_hash`、`slice_id`、`candidate_hash`、`observation_id`、`acceptance_id`、`assertion_id`、`selector_identity`、`run_id`、`result_ref`、`result_sha256`、producer/validator identity 必须可重读匹配当前 artifact。`expected_stage_outcome` 是该 stage 合同预期（RED 通常为 fail，GREEN/REFACTOR/terminal 通常为 pass），`actual_stage_outcome` 是 receipt/断言实际结果，`verification_outcome` 分层描述结果，`predicate_result` 是 validator 对二者及其余约束的确定性判定；三者不得混用。已执行进程的 `fail`/`blocked` 必须同时携带唯一 `failure_family` 和 `failure_id`，而 `pass`/`not-applicable` 必须为空。`observed`、`actual_stage_outcome`、`predicate_result` 只能由真实 observation validator 派生。target、fixture、case source 必须直接绑定或引用独立 receipt；同一 selector 覆盖多个 Acceptance 时每个 Acceptance 必须有独立 assertion edge。

`result_ref` 必须指向已物化且不可变的 process receipt 或独立 observation input。assertion edge 不得嵌入它所 hash 的 observation/receipt 本体，也不得通过自引用计算 `result_sha256`；coverage edge 位于 observation 外部时只能引用 immutable observation。Runtime-edge validator 必须在写 edge 前重新读取并重算 receipt、observation、descriptor、target 和 fixture 字节哈希。

For each V6A-declared `(slice, acceptance_id, stage)` tuple, the current closure set must contain exactly one runtime assertion edge. Duplicate, missing, cross-slice, plan-only, or predicate-false edges are rejected before slice-ready or terminal evaluation.

The machine contract for the closure tuple is:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["tuple_key", "slice_id", "acceptance_id", "stage", "runtime_edge_ref", "runtime_edge_sha256", "selector_identity", "current_snapshot_sha256"],
  "properties": {
    "tuple_key": {"type": "string", "pattern": "^S[0-9]+\\|A-[^|]+\\|(red|green|refactor|terminal)$"},
    "slice_id": {"type": "string", "pattern": "^S[0-9]+$"},
    "acceptance_id": {"type": "string", "minLength": 1},
    "stage": {"enum": ["red", "green", "refactor", "terminal"]},
    "runtime_edge_ref": {"type": "string", "minLength": 1},
    "runtime_edge_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
    "selector_identity": {"type": "string", "minLength": 1},
    "current_snapshot_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
  }
}
```

`terminal_input.runtime_closure_tuples` is an array of these objects with `minItems=1`, `uniqueItems=true`, and a closed cardinality check against the V6A tuple universe. `tuple_key` must equal `slice_id + "|" + acceptance_id + "|" + stage`; because the key is part of the typed object, `uniqueItems=true` mechanically rejects duplicate tuple keys, while the validator additionally rejects key/payload mismatch, missing V6A keys and extra keys.

## Invalidation matrix

Runtime edge 的唯一写入者是 runtime-edge validator；coverage gate 只消费并验证它。所有引用字节必须在写入前重算哈希，禁止自引用。

## Current snapshot resolver

Resolver contract is `current-snapshot-resolver.v1`: it records a content-addressed typed root manifest. `roots` is a closed set with exactly one entry for each `root_kind` in `candidate_tree`, `plan`, `contract`, `registry`, `descriptor`, `fixture`, `source`, `validator_judge`, and `plan_state_transition`; each entry carries `root_kind`, normalized `repository_relative_posix_path`, `content_sha256`, `source_commit` and `inclusion_reason`. `git_delta` is a typed set of additions, deletions and renames, each carrying normalized paths and before/after hashes. `logs`, review records, recovery projections and unrelated documentation are excluded unless an explicit dependency edge names them. Absolute paths, ambiguous normalization and symlink/junction escapes are rejected. Candidate comparison is the exact Git delta against the frozen candidate, with only the declared plan-state transition exception; any path outside the typed root set is invalid. Q0, Q4, Q7, Q8, terminal publication and recovery must invoke this resolver and fail closed on unknown paths or stale root-manifest hash.

The root manifest validator requires `minItems=9`, `maxItems=9`, exactly one entry for each of the nine root kinds above, and rejects duplicate `root_kind` values. Every path in roots and Git delta uses the canonical repository-relative POSIX path grammar (no absolute drive or slash prefix, no `.`/`..` segment, no backslash) and is checked for symlink/junction containment before hashing.

The machine envelope is:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["schema", "roots", "git_delta", "excluded_roots", "sha256"],
  "properties": {
    "schema": {"const": "current-snapshot-resolver.v1"},
    "roots": {"type": "array", "minItems": 9, "maxItems": 9, "uniqueItems": true, "allOf": [{"contains": {"type": "object", "properties": {"root_kind": {"const": "candidate_tree"}}}}, {"contains": {"type": "object", "properties": {"root_kind": {"const": "plan"}}}}, {"contains": {"type": "object", "properties": {"root_kind": {"const": "contract"}}}}, {"contains": {"type": "object", "properties": {"root_kind": {"const": "registry"}}}}, {"contains": {"type": "object", "properties": {"root_kind": {"const": "descriptor"}}}}, {"contains": {"type": "object", "properties": {"root_kind": {"const": "fixture"}}}}, {"contains": {"type": "object", "properties": {"root_kind": {"const": "source"}}}}, {"contains": {"type": "object", "properties": {"root_kind": {"const": "validator_judge"}}}}, {"contains": {"type": "object", "properties": {"root_kind": {"const": "plan_state_transition"}}}}], "items": {"type": "object", "additionalProperties": false, "required": ["root_kind", "repository_relative_posix_path", "content_sha256", "source_commit", "inclusion_reason"], "properties": {"root_kind": {"enum": ["candidate_tree", "plan", "contract", "registry", "descriptor", "fixture", "source", "validator_judge", "plan_state_transition"]}, "repository_relative_posix_path": {"type": "string", "pattern": "^(?!/)(?![A-Za-z]:)(?!.*(?:^|/)\\.\\.?(?:/|$))[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$"}, "content_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}, "source_commit": {"type": "string", "minLength": 1}, "inclusion_reason": {"type": "string", "minLength": 1}}}},
    "git_delta": {"type": "object", "additionalProperties": false, "required": ["base_commit", "additions", "deletions", "renames"], "properties": {"base_commit": {"type": "string", "minLength": 1}, "additions": {"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["path", "after_sha256"], "properties": {"path": {"type": "string", "pattern": "^(?!/)(?![A-Za-z]:)(?!.*(?:^|/)\\.\\.?(?:/|$))[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$"}, "after_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}}}}, "deletions": {"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["path", "before_sha256"], "properties": {"path": {"type": "string", "pattern": "^(?!/)(?![A-Za-z]:)(?!.*(?:^|/)\\.\\.?(?:/|$))[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$"}, "before_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}}}}, "renames": {"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["from_path", "to_path", "before_sha256", "after_sha256"], "properties": {"from_path": {"type": "string", "pattern": "^(?!/)(?![A-Za-z]:)(?!.*(?:^|/)\\.\\.?(?:/|$))[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$"}, "to_path": {"type": "string", "pattern": "^(?!/)(?![A-Za-z]:)(?!.*(?:^|/)\\.\\.?(?:/|$))[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$"}, "before_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}, "after_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}}}}}},
    "excluded_roots": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
  }
}
```

The `roots` item schema is the typed root object described above; the nine `root_kind` values are an exact set, not merely a lower bound. The `git_delta` child schemas require canonical normalized `path`/`from_path`/`to_path` fields and before/after hashes; the only permitted post-candidate exception is the explicitly declared plan-state transition root.

## Architecture decision identity registry

`architecture-decision-registry.v1` is a repository-owned, immutable, content-addressed artifact consumed by memlog recovery. It contains `registry_id`, and an `entries` array mapping each historical memlog ordinal to exactly one stable `AD-*` identity, topic and `current|superseded` status, with an optional `supersedes` identity. The registry artifact hash is recorded as the `registry` root content hash in `current-snapshot-manifest.v1`; a registry byte change invalidates the snapshot and all recovered authority decisions.

Its machine schema is:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["schema", "registry_id", "bindings", "entries"],
  "properties": {
    "schema": {"const": "architecture-decision-registry.v1"},
    "registry_id": {"type": "string", "pattern": "^ADR-REG-[0-9]+$"},
    "bindings": {"type": "object", "additionalProperties": false, "required": ["canonical_selection_path", "canonical_selection_sha256", "spine_path", "spine_sha256"], "properties": {"canonical_selection_path": {"type": "string"}, "canonical_selection_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}, "spine_path": {"type": "string"}, "spine_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}}},
    "entries": {"type": "array", "minItems": 1, "uniqueItems": true, "items": {"type": "object", "additionalProperties": false, "required": ["memlog_ordinal", "decision_id", "topic", "status"], "properties": {"memlog_ordinal": {"type": "integer", "minimum": 1}, "decision_id": {"type": "string", "pattern": "^AD-[0-9]+$"}, "topic": {"type": "string", "minLength": 1}, "status": {"enum": ["current", "superseded"]}, "supersedes": {"type": "string", "pattern": "^AD-[0-9]+$"}}}}
  }
}
```

## Detached judge/fixture bundle

Self-hosted/toolchain promotion requires `detached-judge-bundle.v1` containing source commit/tree, detached read-only judge/oracle/fixture paths, per-artifact hashes, judge identity/version, read-only-open result and promotion-time revalidation result. The bundle must be outside the candidate tree and unable to import candidate evidence writers; missing or mutable fields block promotion.

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
