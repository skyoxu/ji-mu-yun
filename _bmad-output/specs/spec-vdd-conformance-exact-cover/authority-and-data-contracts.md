# Authority And Data Contracts

## Authority Graph

Canonical Spec Package contract 与 external selection registry 由 `bmad-spec` 拥有。Package descriptor 是唯一 root `SPEC.md` frontmatter；selection record 在 package 外以 content-addressed record + maintainer-scoped current pointer 承诺 expected descriptor hash 与完整 role graph，不证明 producer identity。其角色为：

本需求必须交付该 `bmad-spec` producer capability：create/refresh 在 package render 后确定性验证 descriptor，原子发布 selection record，再更新 current pointer。VDD 只独立解析和验证；在 producer 尚未交付或 evidence 缺失时 fail closed，不能把 selection registry 解释为现有 prerequisite，也不能自行补写 registry。

| Role | Contract |
| --- | --- |
| `canonical` | 当前 `SPEC.md`。 |
| `normative_companion` | Spec-authored normative companion。 |
| `adopted_companion` | 被显式 adopt 为 normative 的上游 artifact。 |
| `provenance` | 已 fully absorbed 的上游 source；只用于追溯，不再是平级 authority。 |
| `repository_authority` | 仅由 VDD source-freeze manifest 引入的适用 AGENTS、Accepted ADR、standard 与 knowledge binding。 |
| `unresolved_input` | 仅由 VDD source-freeze manifest 引入的 typed assumption/open question；不得静默转成 resolved。 |

只有 canonical、normative、adopted 与适用 repository authority 贡献 active obligations。Provenance 只保留 path、byte hash 与 package relationship，不贡献 downstream obligation。Unresolved input 在 owner 解决前必须映射到 unresolved requirement 或具名 disposition。

Custody / Validation Order 为 source-freeze manifest、其 hash-bound package files、requirements directory、conformance validator。该顺序描述输入的托管与验证链，不定义 normative authority precedence。Caller source list、boolean、旧 run、summary 与 assistant statement 只能作为 diagnostic。

## Source-Freeze Manifest

VDD 必须产生版本化的一等 manifest，概念名为 `vdd-source-freeze-manifest.v1`，其 producer schema 由 `.agents/skills/vdd-execution-plan/references/schemas/vdd-source-freeze-manifest.v1.schema.json` 独占拥有。Exact-cover 只绑定并验证该 schema 的 repository-relative path、精确 byte SHA-256 与 declared version，不复制或发布它。Manifest 至少包含：

- schema/version、唯一 VDD run identity、target identity、canonical package root 与 canonical manifest hash；
- 每个 source 的 path、typed role、精确 byte SHA-256 与 package/source relationship；
- applicable repository rules、knowledge bindings 与 unresolved input；
- `authorizes=[]`。

VDD construction 与 exact-cover 必须消费并重验同一个 frozen manifest identity/hash。Missing/unknown schema、hash/role drift、normative omission、caller-reduced universe 或 manifest A/B mismatch 均 fail closed。

本项目对 VDD 的修改仅限产生 manifest 与通过显式 repair 消费 `vdd-repair-input.v1`。不得把 exact-cover 或 Bootstrap implementation 吸收到 VDD。

## Run Input

| Field | Contract |
| --- | --- |
| `run_id` | 唯一且不可复用；legacy run 只读。 |
| `target_root` | Normalized repository-relative path，禁止 absolute path、`..` 与 custody-path substitution。 |
| `source_manifest` | VDD manifest 的 path、hash、identity 与 schema version。 |
| `requirements_root` | Repository-relative 且只读的 target directory。 |
| `requirements_manifest` | 当前目录 content hash 与 schema version。 |
| `candidate_identity` | 当前 revision/worktree 与 content manifest hash。 |
| `validator_identity` | Validator code、schema 与 rule hashes。 |
| `predecessor_run_id` | Prior run identity 或 `null`。 |
| `execution_mode` | `evidence_only` 或 `controlled_validation`。 |
| `semantic_review_authorization` | 显式 Bootstrap authorization 或 `null`；prompt text 不能授权。 |
| `authorizes` | 固定为 `[]`。 |

## Obligation And Acceptance

每条 obligation 至少包含 `obligation_id`、`source_path`、`source_sha256`、inclusive `anchor.line_start|line_end|quote`、`kind`、`status`、`disposition.reason|authority_reference|target_plan` 与 `acceptance_ids`。`kind` 只能是 `behavior|constraint|workflow|non_goal`，`status` 只能是 `active|not_applicable|deferred|conflict`。Source 变化时保留 logical identity 以维持 lineage，但 prior coverage evidence 必须 stale；duplicate、orphan、无摘录或 hash drift 均 fail closed。

每条 acceptance 至少包含 `acceptance_id`、`obligation_ids`、`predicate`、`negative_case` 与 `authorizes=[]`。它必须可证伪；未说明 inputs、observations 与 failure meaning 的“tests pass”无效。每个 active obligation 至少有一个 acceptance，每个 acceptance 至少回指一个 obligation。

Conformance matrix 包含 obligation、requirement、acceptance、mapping kind、source hashes、requirements hash、disposition 与 evidence refs。Exact-cover 表示 sound-and-complete cover，不要求 exclusive partition；合法 many-to-many coverage 必须记录 relationships 与 merge reason。

Typed `not_applicable`、`deferred`、`conflict` disposition 必须具有 reason、authority reference 与 target plan。Unknown ref、duplicate ID、orphan acceptance、wrong binding、deterministically provable weakening、unresolved conflict 或 silent omission 均阻断 conformant；无法由机器确定性判定的 weakening 属于 semantic ambiguity，必须进入显式 review handoff。

## Fingerprints And Shards

All JSON identities use `repository-canonical-json.v1` and AD-3 domain-separated envelopes. `run_aggregate_fingerprint.v1` uses the exact AD-6 payload `{source_manifest_hash, requirements_manifest_hash, validator_identity, prompt_identity, policy_identity, authoritative_companions}`. Any global change makes prior aggregate, conformance result, and receipt stale.

`shard_reuse_fingerprint.v1` uses the exact AD-6 payload `{shard_identity, source_segments, roles, relationships, requirements_manifest_hash, validator_identity, prompt_identity, policy_identity}`. Complete source-manifest hash is not an equality condition for unchanged shard reuse. The exact newline-delimited `vcec-shard-v1` SHA-256 identity is the sole typed non-JSON hash exception.

每个 shard artifact 记录 source manifest identity、`source_manifest_hash`、精确 source entries、result hash 与 shard reuse fingerprint。Manifest hash 建立 provenance/custody 与 current aggregate binding；current manifest 的逐字段证明决定 reuse。相关 input drift 使 affected shard stale；全局 manifest 或 companion-set drift 始终使 aggregate stale，但不自动使其他已证明 unchanged 的 shard extraction stale。

Shard states 为 `clean`、`hotspot`、`quarantined`。Quarantined shard 必须保留在 active universe 并阻断 `conformant`。无论是否 reuse，current aggregate 都必须针对完整 active normative universe 重算。

## Result And Receipt

顶层 outcomes 只能是 `blocked`、`conformant`、`requirement_semantic_review_required`。全部 outcome 均携带 bounded hash-bound evidence 且无 lifecycle authority。

Conformant receipt 绑定 current source manifest、requirements manifest、validator identity、role graph 与 run aggregate fingerprint。Receipt 只是 prerequisite；现有 authorization owner 仍独占 `implementation-authorized` 发布权，并必须拒绝 stale、missing、mismatched、non-conformant、prose、boolean 或 old-summary substitute。

Schema projections and canonical identities follow adopted AD-2 through AD-6. Runtime retry/shard/hotspot/quarantine/presentation values are selected only from the maintainer-owned approved registry under AD-7; schema major change invalidates prior artifacts and requires a new validator identity.
