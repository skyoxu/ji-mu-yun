# Acceptance Contract

所有 ID 稳定、只追加、不得重编号或复用。本 package 的详细合同保持 authority；本矩阵不得缩减其语义。

## Requirements

| ID | Normative requirement | Acceptance |
| --- | --- | --- |
| `VCEC-001` | 输入 authority 必须是 `bmad-spec` 拥有的 Canonical Spec Package graph。 | `VCEC-A01`, `VCEC-A02` |
| `VCEC-002` | Canonical、normative、adopted、provenance、repository-authority 与 unresolved roles 必须 typed，caller 不得降级、提升或删除。 | `VCEC-A02`, `VCEC-A03` |
| `VCEC-003` | VDD 必须产生 versioned、first-class、hash-bound、`authorizes=[]` 的 source-freeze manifest。 | `VCEC-A04` |
| `VCEC-004` | VDD construction 与 exact-cover 必须消费并重验同一 manifest identity/hash。 | `VCEC-A05` |
| `VCEC-005` | Missing freeze、unknown schema、hash/role drift、normative omission 或 caller-reduced universe 必须 fail closed。 | `VCEC-A06` |
| `VCEC-006` | 每条 source obligation 必须绑定 stable ID、verbatim anchor、source pointer 与 source hash。 | `VCEC-A07` |
| `VCEC-007` | Active obligations、requirements 与 acceptances 必须形成 bidirectional sound-and-complete cover。 | `VCEC-A08` |
| `VCEC-008` | Not-applicable、deferred 与 conflict dispositions 必须具有 reason、authority reference 与 target plan。 | `VCEC-A09` |
| `VCEC-009` | Unknown、duplicate、orphan、wrong binding、weakening、unresolved conflict 与 silent omission 不得产生 conformant。 | `VCEC-A10` |
| `VCEC-010` | LLM 只能提出 candidates 或解释 ambiguity；canonical IDs/hashes/cover/PASS 由 deterministic producer 决定。 | `VCEC-A11` |
| `VCEC-011` | Results 只能是 typed blocked、conformant 或 requirement-semantic-review handoff，并携带 bounded hash-bound evidence。 | `VCEC-A12` |
| `VCEC-012` | Pre-implementation ambiguity 必须显式路由到 `bootstrap-upstream-plan`，随后 explicit VDD repair 与 exact-cover rerun。 | `VCEC-A13` |
| `VCEC-013` | Requirement review 与 post-implementation assurance 必须使用不同 lifecycle identities 与 typed routes/results。 | `VCEC-A14` |
| `VCEC-014` | `vdd-repair-input.v1` 必须 hash-bound、schema-valid、`authorizes=[]`，且只能由 explicit VDD repair 消费。 | `VCEC-A15` |
| `VCEC-015` | Repair 必须创建/绑定新的 applicable requirements identity，使旧 receipt stale 并重跑 exact-cover。 | `VCEC-A16` |
| `VCEC-016` | Current conformant receipt 是 canonical-flow authorization 的必要证据，但不拥有 lifecycle authority。 | `VCEC-A17` |
| `VCEC-017` | Existing authorization owner 必须拒绝 missing、stale、non-conformant、mismatched、prose、boolean 与 old-summary substitutes。 | `VCEC-A18` |
| `VCEC-018` | Exact-cover 与中间 artifacts 保持 `authorizes=[]`，不得发布 lifecycle 或 acceptance states。 | `VCEC-A19` |
| `VCEC-019` | VDD 修改只限 source-freeze production 与 repair-input consumption，不得包含 exact-cover 或 Bootstrap implementation。 | `VCEC-A20` |
| `VCEC-020` | Exact-cover 不修改 target；VDD 保留 create/repair 与 lifecycle ownership。 | `VCEC-A21` |
| `VCEC-021` | Model-visible output 必须 bounded；完整 source、matrix、reviewer output、stdout 与 prompts 留在 artifacts。 | `VCEC-A22` |
| `VCEC-022` | Run 必须从 compact current artifacts 在新进程重启，不依赖 Codex resume、compaction 或 old chat。 | `VCEC-A23` |
| `VCEC-023` | Limits、truncation、full artifact refs/hashes、repeat-failure stop-loss 与 stale restart 必须 fail closed。 | `VCEC-A24` |
| `VCEC-024` | Delivery 必须包含真实 producer-consumer composition、mutation/negative fixtures 与完整 dogfood。 | `VCEC-A25`, `VCEC-A26` |
| `VCEC-025` | Legacy migration 保持由 VDD/adapters 拥有；exact-cover 不迁移或改写 legacy plans。 | `VCEC-A27` |
| `VCEC-026` | 执行必须 deterministic-first，且只在 structure、bindings 与 mapping 闭合后升级真正 ambiguity。 | `VCEC-A28`, `VCEC-A29` |
| `VCEC-027` | 每个 blocked/diagnostic result 必须具有稳定 typed failure family；raw message 不得替代。 | `VCEC-A30` |
| `VCEC-028` | 只有允许的 transient/instability families 可 retry，并具有 bounded attempts、attempt identity 与 stop-loss。 | `VCEC-A31`, `VCEC-A32`, `VCEC-A42` |
| `VCEC-029` | Reuse 必须绑定两级 fingerprint；global drift 使 aggregate/receipt stale，affected drift 使 shard stale，unchanged reuse 需要 current-manifest proof。 | `VCEC-A33`, `VCEC-A34` |
| `VCEC-030` | Stable shards 必须记录 source manifest hash 与 state；aggregate 始终覆盖完整 active universe。 | `VCEC-A33`, `VCEC-A35`, `VCEC-A36` |
| `VCEC-031` | 相同 frozen input 的 extraction drift 必须成为 typed instability 并标识 affected hotspots。 | `VCEC-A37` |
| `VCEC-032` | Bounded jitter/consensus 只能诊断 stability/escalation，不得决定 truth、coverage 或 PASS。 | `VCEC-A38` |
| `VCEC-033` | Deterministic failure 不得进入 Bootstrap；只有机器不可判定的 requirement ambiguity 可 escalation。 | `VCEC-A29`, `VCEC-A39` |
| `VCEC-034` | Failure family 与 current evidence 必须确定性选择 typed、non-authorizing recommended action。 | `VCEC-A40` |
| `VCEC-035` | Recovery 必须从 manifest、两级 fingerprints 与 shard states 重建；clean reuse 需证明，stale shards 重验，aggregate 重算。 | `VCEC-A41` |

## Lifecycle Boundaries

| ID | Boundary |
| --- | --- |
| `VCEC-NG01` | 不创建第二个 review runner、reviewer layer 或 Bootstrap runtime。 |
| `VCEC-NG02` | 不判断 implementation/test/current evidence，也不替代 post-implementation Acceptance。 |
| `VCEC-NG03` | 不修改 target，不执行 VDD repair，不拥有 lifecycle/release/commit authority。 |
| `VCEC-NG04` | 不把 fully absorbed PRD、Architecture 或 raw input 重新提升为 Canonical Spec Package 的平级 authority。 |
| `VCEC-NG05` | 不声明修改 Codex resume、compaction、context-window 或 provider behavior。 |
| `VCEC-NG06` | 不引入 Chapter 5 Taskmaster/Game/PowerShell/scripts、多层 reviewer chain 或 runtime dependency。 |

## Falsifiable Acceptances

| ID | Predicate | Covers |
| --- | --- | --- |
| `VCEC-A01` | VDD 从 valid Canonical Spec Package 冻结唯一 package root，并拒绝非 `bmad-spec` package。 | `VCEC-001` |
| `VCEC-A02` | Role-graph round-trip 保留全部 normative、adopted、unresolved items 与 relationships；任一遗漏失败。 | `VCEC-001`, `VCEC-002` |
| `VCEC-A03` | Role demotion/promotion、provenance obligation extraction、normative deletion 或 silent unresolved-to-resolved fixtures 均失败。 | `VCEC-002` |
| `VCEC-A04` | 真实 VDD producer 输出含所需字段、canonical hash 与 `authorizes=[]` 的 schema-valid manifest。 | `VCEC-003` |
| `VCEC-A05` | Same-manifest VDD/exact-cover binding 通过；manifest A/B composition 失败。 | `VCEC-004` |
| `VCEC-A06` | Missing、unknown、drift、omission 与 reduced-universe fixtures 均在读取 requirements 前 fail closed。 | `VCEC-005` |
| `VCEC-A07` | 每个 stable obligation ID、inclusive quote、source pointer/hash 均可重算；duplicate 或 drift 失败。 | `VCEC-006` |
| `VCEC-A08` | Bidirectional active sets 相等；删除任一合法 edge 后结果 non-conformant。 | `VCEC-007` |
| `VCEC-A09` | Non-active obligation 只有在 disposition 字段完整时才排除；缺任一字段即失败。 | `VCEC-008` |
| `VCEC-A10` | Missing、unknown、duplicate、orphan、wrong-binding、weakening 与 unresolved-conflict mutations 均不 conform。 | `VCEC-009` |
| `VCEC-A11` | Caller/LLM canonical IDs、hashes 或 PASS booleans 不改变 deterministic recomputation。 | `VCEC-010` |
| `VCEC-A12` | 三种 result forms 均能 validate；raw/full output 或缺 evidence path/hash 失败。 | `VCEC-011` |
| `VCEC-A13` | Ambiguity 只产生 requirement-review handoff；无显式授权不启动 Bootstrap；current envelope 只产生 repair input。 | `VCEC-012` |
| `VCEC-A14` | Requirement-review artifact 不含 implementation candidate，post-implementation route 拒绝将其当作 review authorization。 | `VCEC-013` |
| `VCEC-A15` | 真实 VDD repair 接受 current input，拒绝 stale、tampered 或 implicit route，并保持 lifecycle ownership。 | `VCEC-014` |
| `VCEC-A16` | Repair 改变 requirements identity，使旧 receipt stale，并要求 exact-cover 后才能产生新 receipt。 | `VCEC-015` |
| `VCEC-A17` | Matching receipt 满足 authorization preflight，但单独不改变 lifecycle state。 | `VCEC-016` |
| `VCEC-A18` | 真实 authorization entry 拒绝 missing/stale/non-conformant/mismatched receipt 与 prose/boolean substitute。 | `VCEC-017` |
| `VCEC-A19` | 所有 outputs 具有 `authorizes=[]`，且无 lifecycle/acceptance/commit/release publication field。 | `VCEC-018` |
| `VCEC-A20` | VDD diff 只包含 producer/consumer contracts；嵌入 exact-cover 或 Bootstrap algorithms 必须失败。 | `VCEC-019` |
| `VCEC-A21` | Exact-cover 前后 target requirements byte manifest 相同；只有 explicit VDD repair 可改变。 | `VCEC-020` |
| `VCEC-A22` | Model-visible receipt 不含完整 source/reviewer/stdout/prompt；完整 artifacts 保持受控。 | `VCEC-021` |
| `VCEC-A23` | 新 process/thread 仅凭 compact current artifacts 重启，不读取 old rollout/chat。 | `VCEC-022` |
| `VCEC-A24` | Overflow 设置 `truncated=true` 并绑定 full artifact；drift、blind retry 或 missing artifact 均阻断。 | `VCEC-023` |
| `VCEC-A25` | Composition 使用真实 Package、VDD producer/create/repair、exact-cover 与 authorization-preflight entries。 | `VCEC-024` |
| `VCEC-A26` | 一个真实 plan 完成 create、exact-cover、optional review、repair、rerun dogfood；negative evidence 保持 immutable。 | `VCEC-024` |
| `VCEC-A27` | Unknown legacy manifest/schema fail closed，且 legacy target bytes 不变。 | `VCEC-025` |
| `VCEC-A28` | Hard uncovered 即使收到 repeated semantic PASS 仍 blocked；deterministic schema/hash/set failure 不启动额外 semantic LLM 或 Bootstrap。 | `VCEC-026` |
| `VCEC-A29` | Manifest mismatch 阻断 review；完整 deterministic proof 且无 ambiguity 时 Bootstrap calls 为零。 | `VCEC-026`, `VCEC-033` |
| `VCEC-A30` | 每个 taxonomy fixture 产生稳定 family；generic LLM failure 或 raw-exception-only output schema 失败。 | `VCEC-027` |
| `VCEC-A31` | Timeout/transport 只 retry 到 configured maximum，每次 attempt ID 唯一，随后停止。 | `VCEC-028` |
| `VCEC-A32` | Schema/hash/coverage failure 即使提高 timeout/reasoning 也执行零 retry，并产生 repair input。 | `VCEC-028` |
| `VCEC-A33` | 每个 shard artifact 记录 custody `source_manifest_hash`；current-manifest proof 允许 unrelated full-manifest change 下的 identical shard reuse。 | `VCEC-029`, `VCEC-030` |
| `VCEC-A34` | Manifest/companion change 使 aggregate/receipt stale；相关 content/role/relationship/requirements/validator/schema/policy change 使 affected shard stale。 | `VCEC-029` |
| `VCEC-A35` | 100 shards 仅 1 个变化时，全部 artifacts 绑定 source manifest hash，只重跑 affected extraction，并重新 aggregate 全部 100 current shards。 | `VCEC-030` |
| `VCEC-A36` | 任一 quarantined shard 阻断 conformant；删除或忽略它使 aggregation 失败。 | `VCEC-030` |
| `VCEC-A37` | 相同 frozen input 的 count/boundary/status drift 产生 `obligation_extraction_unstable` 与 hotspot refs。 | `VCEC-031` |
| `VCEC-A38` | 2/3 covered vote 但缺 deterministic mapping 时仍 blocked，不产生 conformant receipt。 | `VCEC-032` |
| `VCEC-A39` | 只有 structure/bindings/mapping 通过且剩余问题是 equivalence、weakening、conflict 或 applicability ambiguity 时才产生 handoff。 | `VCEC-033` |
| `VCEC-A40` | 每个 family 确定性映射 allowed action；修改 prose/caller suggestion 不改变结果，且 `authorizes=[]`。 | `VCEC-034` |
| `VCEC-A41` | 新进程恢复时 reuse 已证明 unchanged 的 clean shards、拒绝 stale shards，并重算 current aggregate。 | `VCEC-035` |
| `VCEC-A42` | Malformed extraction 为 `obligation_extraction_invalid`；attempts 唯一，ceiling 前用 `rerun_changed_shards`，随后 stop 并 blocked `inspect_extraction`。 | `VCEC-028` |

## Completion Gate

完成必须同时满足：

- 真实 Canonical Spec Package 产生具有完整 roles 的 VDD manifest，且 VDD/exact-cover 绑定同一 identity/hash。
- 每个 active obligation 都有 stable、traceable requirement/acceptance coverage；每个 disposition 完整。
- 所有 deterministic gaps、drift、tampering、unknown、duplicate、wrong binding、normative omission、quarantined shard 与 manifest A/B cases 均 fail closed。
- 真实 VDD repair 与现有 authorization preflight 消费 current artifacts，同时保持原 lifecycle ownership。
- Pre/post-implementation semantic review 保持分离；Bootstrap 只对显式授权的 genuine ambiguity 启动。
- Bounded recovery 在新进程工作，保留 historical evidence，不向主模型暴露完整 source/reviewer/stdout/prompt，也不声明 Codex-resume 能力。
- Retry、stop-loss、两级 fingerprint、shard reuse、aggregate recomputation、instability/jitter 与 typed-action fixtures 全部通过。
- `execution-policy.md` 中的 retry ceilings、deterministic shard identity/limits、hotspot/quarantine threshold、bounded-output limits 与 schema registry fixtures 全部通过；实现不得用其他默认值替代。
- VDD 独占 source-freeze producer schema；exact-cover 只验证其 path/hash/version。复制 schema、owner/path/hash drift 或 unknown version fixtures 全部 fail closed。
- 至少一个真实 plan 完成 create → exact-cover → optional review → repair → exact-cover dogfood。
- `VCEC-001` 至 `VCEC-035` 各自映射至少一个可证伪 acceptance，且现有 recovery、hash binding、negative fixtures 与 lifecycle boundaries 得到保留。
