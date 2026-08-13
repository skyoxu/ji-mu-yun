# Execution And Recovery

## Deterministic-First Workflow

1. 在任何 LLM call 前验证 source-freeze schema/hash/run、safe paths、authority roles、source/requirements/validator bindings 与已有 IDs/refs。
2. 仅在需要 extraction 时计算 run/shard fingerprints，并按稳定 source/obligation boundaries 划分 shards。
3. LLM 只提出 obligation candidates、解释 ambiguity 与提议 falsifiable acceptance；每个 candidate 必须回到 quoted source anchor，LLM 不能分配 canonical ID 或 PASS。
4. 确定性 canonicalize IDs、states、dispositions、mappings、shard results 与完整 current aggregate。
5. 确定性检查 schema、hashes、set equality、unknown、duplicate、orphan、mapping、disposition 与 full-universe exact cover。
6. 产生 typed outcome：deterministic defect 为 `blocked`，完整证明为 `conformant`，只有 unresolved semantic ambiguity 才能请求 review。
7. 需要 repair 时，由 exact-cover non-mutating handoff adapter 从 accepted current review evidence 产生不授权的 `vdd-repair-input.v1`；VDD 只验证并在 explicit repair 中消费，Exact-cover 永不修改 target。

Deterministic failure 不得通过更多 LLM calls、timeout、reasoning effort、jitter 或 Bootstrap 绕过。Semantic escalation 必须同时满足 structure/source binding 有效、structural mapping 完整，且剩余问题是 weakening、equivalence、true conflict 或 applicability 的机器不可判定歧义。

## Semantic Review Boundaries

Pre-implementation ambiguity 产生 hash-bound `requirement_semantic_review_required` handoff，profile 固定为 `bootstrap-upstream-plan`。Handoff 列出 frozen authority、affected obligation/requirement IDs、ambiguity reason 与 review scope，只能在显式授权后启动；实际 launch 继续受 Bootstrap 自身 policy、model routing 与 high-cost acknowledgement 控制。Current validation envelope 进入显式 VDD repair，随后重跑 exact-cover。

Post-implementation semantic assurance 由 Refactor Acceptance 与 Bootstrap implementation/focused profiles 独立拥有。两条 lane 使用不同 typed routes、results 与 lifecycle identities；requirement-review handoff 不能授权 implementation review。

## Failure Families And Actions

最小稳定 taxonomy 为：

| Family | Default recovery class |
| --- | --- |
| `manifest_invalid` | Repair manifest 或 restart from source freeze。 |
| `source_drift` | Restart from source freeze。 |
| `authority_role_drift` | Repair manifest。 |
| `schema_error` | Repair invalid deterministic input。 |
| `deterministic_coverage_gap` | Repair requirements。 |
| `obligation_extraction_invalid` | Bounded changed-shard rerun，随后 inspect extraction。 |
| `obligation_extraction_unstable` | Bounded jitter diagnosis、hotspot/quarantine，随后 repair 或 semantic review。 |
| `semantic_ambiguity` | Explicit semantic review。 |
| `semantic_conflict` | Explicit semantic review 或 named disposition。 |
| `timeout` | Bounded retry，且不能覆盖已知 coverage failure。 |
| `transport_failure` | Bounded transport retry。 |
| `validator_failure` | Inspect validator。 |
| `artifact_integrity_failure` | 从 valid bound artifact 重启。 |

Raw message 只能是 detail，不能替代 family。Recommended action 来自 versioned allowlist，至少包含 `repair_manifest`、`repair_requirements`、`rerun_changed_shards`、`retry_transport`、`semantic_review`、`inspect_extraction`、`inspect_transport`、`inspect_validator`、`restart_from_source_freeze`。Family 与 current evidence 决定 action，prose 不能覆盖。

## Retry And Instability

Missing normative source、manifest mismatch、hash/role drift、source/requirements schema failure、unknown ID、orphan acceptance、hard uncovered obligation、invalid disposition 与 deterministic set mismatch 直接进入 repair，不允许 LLM retry。

只有 timeout、transport failure、malformed model output 与明确 extraction instability 允许 bounded retry。每个 family 的 finite positive maximum、attempt scope 和 exhaustion action 来自 approved hash-bound runtime-policy profile；每个 attempt 具有唯一 identity、固定或收缩的 context；达到阈值后 stop-loss。

Malformed model output 归类为 `obligation_extraction_invalid`。达到 ceiling 前 action 为 `rerun_changed_shards`；达到 ceiling 后转为 blocked + `inspect_extraction`，并禁止继续 model call。

在相同 frozen input 上，obligation count/boundary、active/ignored state 变化或无法形成 stable mapping 时，结果为 `obligation_extraction_unstable`。Bounded jitter/consensus 只能识别稳定性、hotspot 或建议 clarification/review；majority vote 永不决定 normative truth、coverage 或 `conformant`。

## Bounded Context And Recovery

Run 使用 append-only `recovery-checkpoint.v1` lineage。每个 checkpoint 绑定 run/branch/sequence/stage/state、immutable validator/policy identities、complete sorted artifact refs、stage-tagged input bindings、attempt binding、shard states、live blocker 与 next legal actions。Branch sequence 0 无 same-branch predecessor；authorized fork 通过独立 `fork_from` 绑定 parent branch/checkpoint 与 authorization。

Model-visible surface 只包含 bounded counts、families、affected IDs、hashes、artifact refs、verdict、action 与有限 finding IDs。完整 source inventory、shard output、matrix、reviewer output、stdout、source text 与 prompts 留在受控 artifacts。每个 bounded output 具有 versioned limits、`truncated` 与完整 artifact ref/hash；overflow 不得向 model context 追加全文。12,000-byte hard gate 由 validator 精确重算；presentation caps 仅从 approved hash-bound runtime-policy profile 解析。

重量级读取与扫描必须在确定性子进程或脚本中完成。`bootstrap-upstream-plan` 的完整 review evidence 保持在原 run directory；exact-cover 只消费 current、hash-bound validation envelope，不复制 reviewer 正文。

新进程只从 explicitly authorized branch 的完整 checkpoint hash lineage 和 greatest sequence 恢复，不读取 old chat、rollout、`resume --last` 或 convenience pointer 作为 authority。Resume 重算 validator/policy identities 与每个 artifact ref 的 current bytes/hash；input/validator/policy/artifact drift 必须开始新 run 或 fail closed。经 current manifest 证明的 clean shards 可 reuse；stale、hotspot 与 quarantined shards 必须重验，current aggregate/receipt 始终重算。

Context-window、transport 或 process interruption 只写 checkpoint 并停止。本能力不修改或承诺 Codex resume、compaction、provider 或 context-window behavior。Historical evidence append-only；不得盲目重试相同 failure。

## VDD Repair Input

`vdd-repair-input.v1` 由 exact-cover non-mutating handoff adapter 产生，绑定 review run、source freeze、prior requirements manifest、validator、policy、ambiguity IDs 与 allowed repair scope。它必须 schema-valid、hash-bound、`authorizes=[]`，且只能由 explicit VDD repair 验证并消费。Repair 必须创建或绑定新的 applicable requirements identity，使 prior extraction/aggregate/receipt/authorization evidence stale，并要求 exact-cover rerun。
