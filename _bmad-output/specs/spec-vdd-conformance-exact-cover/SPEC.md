---
id: SPEC-vdd-conformance-exact-cover
companions:
  - authority-and-data-contracts.md
  - execution-and-recovery.md
  - implementation-conventions.md
  - execution-policy.md
  - acceptance-contract.md
  - architecture-diagrams.md
sources:
  - ../../../execution-plans/2026-08-10-vdd-conformance-exact-cover-requirements.md
---

> **Canonical contract.** 本 SPEC 与 `companions:` 中的文件共同构成构建、测试和验证所需的完整、经过 preservation validation 的合同。`sources:` 中的源文档仅用于追溯。

# VDD Conformance Exact-Cover

## Why

VDD 需要以机器可证明的方式确认 execution-plan requirements 目录完整保留 frozen Canonical Spec Package 的每条 active obligation。确定性遗漏、漂移和映射缺陷必须在昂贵的语义审查前阻断实现，真正的歧义则必须进入唯一、显式且不授权的审查通道。

## Capabilities

- **CAP-1**
  - **intent:** VDD 能为 plan construction 与 conformance 冻结并验证完整的 Canonical Spec Package authority graph。
  - **success:** 一个 schema-valid、hash-bound 的 source manifest 保留全部 typed authority roles，并由 VDD construction 与 exact-cover 绑定同一 identity/hash。
- **CAP-2**
  - **intent:** 工具链控制面能证明 source obligations、plan requirements、acceptances 与 dispositions 构成 sound-and-complete cover。
  - **success:** 确定性重算覆盖全部 active obligation，并拒绝 unknown、orphan、duplicate、weakening、conflict 或 silent omission。
- **CAP-3**
  - **intent:** 工具链控制面能隔离真正的 requirement-semantic ambiguity，而不把 semantic review 变成通用 coverage gate。
  - **success:** Deterministic failure 保持 blocked；只有结构完整且 source-bound 的歧义才产生不授权的 `bootstrap-upstream-plan` handoff，并经显式 VDD repair 返回。
- **CAP-4**
  - **intent:** Operator 与 VDD 能在不依赖旧模型对话的情况下消费 typed diagnostics、recovery checkpoints 和 repair inputs。
  - **success:** Run 可在新进程中仅凭 compact hash-bound artifacts 重启，保持 target requirements bytes 不变，并将每个 failure family 路由到确定性且不授权的 action。
- **CAP-5**
  - **intent:** 现有 implementation authorization owner 能把 exact-cover 作为 prerequisite 强制执行，而不转移 lifecycle authority。
  - **success:** 匹配 source manifest、requirements manifest 与 validator 的 current receipt 可满足 preflight；missing、stale、mismatched、non-conformant、prose 和 boolean 替代均被拒绝。
- **CAP-6**
  - **intent:** 大型 package 能在保留完整 normative universe 的前提下增量稳定 semantic extraction。
  - **success:** 两级 fingerprint 只允许由 current manifest 证明的 shard reuse，quarantined shard 阻断 conformant，retry 在有界次数后停止，current aggregate 始终确定性重算。
- **CAP-7**
  - **intent:** Maintainer 能通过确定性 schemas、negative fixtures、真实 composition 与 dogfood 验证该能力。
  - **success:** 每条稳定 requirement 映射到可证伪 acceptance，全部 negative cases fail closed，真实 Package-to-authorization-prerequisite 链通过且 exact-cover 不获得 lifecycle authority。

## Constraints

- `bmad-spec` 拥有 Canonical Spec Package；VDD 拥有 source-freeze production、create/repair、`plan-ready` 和 plan lifecycle。
- Exact-cover 对 target plan 只读，不拥有 implementation、test、evidence、review launch、Acceptance、release、commit 或 migration authority。
- 所有 exact-cover 与中间 artifacts 均 hash-bound 且 `authorizes=[]`；只有确定性重算能产生 `conformant`。
- Deterministic schema、hash、path、ID、set、mapping 与 disposition 检查必须先于 semantic work，不能通过 retry、更大 context、reasoning effort 或 Bootstrap 绕过。
- Semantic review 只使用显式的 pre-implementation `bootstrap-upstream-plan` lane；post-implementation semantic assurance 保持独立 Acceptance lifecycle。
- Recovery 必须文件化、有界，并独立于 Codex resume、compaction、context-window 或旧对话行为；v1 policy 固定 retry、shard 与 bounded-output ceilings。
- Chapter 5 只提供治理原则；不得引入其 Taskmaster、游戏、PowerShell、多 reviewer、source discovery、baseline promotion 或 automatic launch 实现。

## Non-goals

- 实现或替代 Bootstrap Review、VDD repair、implementation authorization、Refactor Acceptance 或 release control。
- 修改被检查的 execution-plan、迁移 legacy plan，或创建第二套 authority discovery system。
- 把 LLM output、jitter consensus、cached extraction、prose 或 caller boolean 当作 normative truth 或 PASS authority。
- 引入 Chapter 5 领域工作流或新增 LLM align、coverage、semantic-gate、refs-repair stages。

## Success signal

- 一个真实 Canonical Spec Package 被一次冻结，由 VDD 与 exact-cover 绑定同一 manifest identity/hash，只能通过 VDD 修复，并且只有 current conformant receipt 才能通过现有 authorization preflight。
- Mutation、drift、ambiguity、retry、shard、recovery 与 legacy fixtures 均确定性地产生规定的 typed outcomes，不发生 silent obligation loss 或 lifecycle authority leakage。

## Resolved Policy

- `execution-policy.md` 是本 package 的 v1 policy authority，固定 retry ceilings、deterministic shard partition、hotspot/quarantine thresholds、bounded-output limits 与 schema registry；不允许实现者临场改值。
