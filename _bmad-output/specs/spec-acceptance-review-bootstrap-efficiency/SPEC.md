---
id: SPEC-acceptance-review-bootstrap-efficiency
package_schema: canonical-spec-package.v1
companions:
  - path: _bmad-output/specs/spec-acceptance-review-bootstrap-efficiency/authority-and-lifecycle.md
    role: normative_companion
  - path: _bmad-output/specs/spec-acceptance-review-bootstrap-efficiency/authority-projection-and-segmentation.md
    role: normative_companion
  - path: _bmad-output/specs/spec-acceptance-review-bootstrap-efficiency/execution-and-recovery.md
    role: normative_companion
  - path: _bmad-output/specs/spec-acceptance-review-bootstrap-efficiency/verification-and-rollout.md
    role: normative_companion
  - path: _bmad-output/specs/spec-acceptance-review-bootstrap-efficiency/architecture-diagrams.md
    role: normative_companion
  - path: _bmad-output/specs/spec-acceptance-review-bootstrap-efficiency/glossary.md
    role: normative_companion
sources:
  - path: _bmad-output/planning-artifacts/prds/prd-jimuyun-2026-08-14/prd.md
    role: provenance
  - path: _bmad-output/planning-artifacts/prds/prd-jimuyun-2026-08-14/addendum.md
    role: provenance
---

> **Canonical contract.** 本 SPEC 与 `companions:` 中的文件共同构成构建、测试和验证所需的完整合同。`sources:` 仅用于追溯，不是下游 obligation authority。

# 验收范围与 Bootstrap 审查效率优化

## Why

Ji Mu Yun 的实现验收曾因 whole-directory scope、重复模型消费、segment 越界读取、身份漂移和失控恢复产生超过四小时的运行。工具链控制面必须从目录驱动改为证据闭包驱动：Acceptance 先建立可证明的最小完整 Consumer Closure 和 deterministic evidence，再按 typed risk policy 决定是否启动保持既有三角色语义的 Bootstrap，并让所有分段执行、恢复和最终裁决由当前机器证据闭合。

## Capabilities

- **CAP-1**
  - **intent:** Acceptance 能从 Quick Dev / quick-dev-tdd-adapter 发布的有效 implementation-complete handoff 启动验收，并冻结不可移动的 baseline/current identity。
  - **success:** 缺失、过期或 identity 不匹配的 handoff 阻止启动；durable baseline 不使用未解析 `HEAD`；candidate 变化使旧 changed-set、closure、check result 和 review receipt 全部 stale。
- **CAP-2**
  - **intent:** Acceptance 能从完整 changed-set 构建最小但完整、可独立复算的 Consumer Closure。
  - **success:** 修改、新增、删除、重命名和适用未跟踪文件均被表达；closure roots、typed dependency fixed point、纳入项、排除项及 completeness receipt 可独立重算，omission fixtures 稳定拒绝遗漏和错误排除。
- **CAP-3**
  - **intent:** Acceptance 能在模型工作前重放 plan authority 投影的 deterministic required checks，并发布 typed Bootstrap route。
  - **success:** deterministic failure 产生零 reviewer call；route 只能在 authority/risk policy 允许集合内选择；mandatory trigger 只能进入 full implementation conformance 或 manual pause，成本不能将其降级。
- **CAP-4**
  - **intent:** Bootstrap 能在同一 frozen Consumer Closure 上完成既有三角色隔离审查，并只对 gate 接受的 P0/P1 启动 independent verifier。
  - **success:** 任一 required role、required-check replay/reuse proof 或 closure identity 缺失均阻止 semantic launch；零 accepted P0/P1 时 verifier call 为零；结果返回 Acceptance 而不直接发布最终状态。
- **CAP-5**
  - **intent:** 控制面能向 reviewer 完整交付选定 authority，同时对超预算 authority 使用受控投影。
  - **success:** 小型 authority 必须完整读取且 `Partial` 精准续传至 `Complete`；大型 authority 仅可使用 controller-owned、full-source-bound 的 Range Projection，任一 path、range、source hash 或 extracted bytes mutation 均被拒绝。
- **CAP-6**
  - **intent:** Bootstrap 能以单一 canonical Segment identity 和 segment-only snapshot 隔离每个 reviewer child。
  - **success:** assignment、prompt request、child receipt、parent validation、coverage fold 与 retry reuse 使用同一 identity；child 无法遍历完整 Artifact View 或 live repository；snapshot path 为绝对冻结路径，授权 executable/model identity 自动继承。
- **CAP-7**
  - **intent:** 运行控制器能区分 liveness 与 Effective Progress，并有界恢复停滞、进程终态、lease 和 retry。
  - **success:** heartbeat、stdout、轮询和重复状态不能刷新 no-progress window；超限后停止新模型调用、终止或隔离 attempt、追加 typed terminal evidence、reconcile lease 并发布非授权 recovery result；只重试 policy 允许的失败 segment。
- **CAP-8**
  - **intent:** Acceptance 能在启动模型前评估 review 成本，并在 authority/risk policy 内选择继续、重建 closure、重新分区或暂停。
  - **success:** 决策绑定 closure bytes、segment count、required roles、attempts、retry exposure 和 launch plan identity；high-cost acknowledgement 不能替代 route/closure decision；完成后记录实际 token 与 wall time。
- **CAP-9**
  - **intent:** Acceptance 能验证并导入 Bootstrap evidence，随后基于当前机器证据发布 `acceptance-passed`。
  - **success:** candidate、closure、required checks、gate、verifier 或 receipt 任一 stale/mismatch 均拒绝导入；Bootstrap 不能产生 draft、plan-ready、implementation-authorized、implementation-complete 或 acceptance-passed；assistant 文本不能替代完成证据。
- **CAP-10**
  - **intent:** 维护者能用接近 8-13 规模的回归和冻结语义 corpus 证明优化没有削弱 coverage 或授权安全。
  - **success:** deterministic failure 为零模型调用；Bootstrap-required 保持三角色完整 coverage；无越界读取、stale lease 或人工 identity 修补；transport failure 不形成语义结论；mandatory P0/P1、semantic ambiguity 和 false-authorizing mutation 均产生预期非授权结果类别。

## Constraints

- 生命周期状态 ownership 固定为：VDD 拥有 draft 和 plan-ready；maintainer 拥有 implementation-authorized；Quick Dev / quick-dev-tdd-adapter 拥有 implementation-complete；Acceptance 拥有 acceptance-passed。
- Acceptance、Quick Dev / quick-dev-tdd-adapter、VDD、maintainer、Bootstrap Review、plan owner 和 policy owner 的职责边界遵循 [authority-and-lifecycle.md](authority-and-lifecycle.md)。
- Consumer Closure 必须完整、可复算且禁止 sampling；Git diff 只能作为入口。
- Generic Bootstrap 只能消费 implementation contract/command registry 投影的 required checks，不得硬编码计划命令。
- Bootstrap Complete Review 保持 Blind Hunter、Edge Case Hunter 和 Acceptance Auditor 三个隔离 discovery roles。
- Selected authority 必须整文件或 controller-owned hash-bound Range Projection；reviewer 不能自选摘要或片段。
- Segment child 只消费 parent-assigned segment；canonical identity、snapshot 和 access-proof invariants 遵循 [authority-projection-and-segmentation.md](authority-projection-and-segmentation.md)。
- Heartbeat 和输出不是 Effective Progress；stop-loss、terminal event、lease reconciliation 和 retry 遵循 [execution-and-recovery.md](execution-and-recovery.md)。
- 相同 frozen baseline/current、Changed-set Manifest、Consumer Closure、required-check results 和 policy 输入必须产生相同 route、segment identities 和可验证结果。
- 任何 authority、hash、range、receipt、process identity、authorization 或 closure completeness 无法确认时必须停止在 typed non-authorizing 状态。
- 恢复只能依赖 Process Events、immutable descriptors、current process identity 和 current policy；不得依赖聊天历史、Codex resume/compaction、人工 lease 重建或人工 PID 判断。
- 保持现有 `requiredLayers`、gate、independent verifier 和 historical evidence 的兼容语义。
- 成本不得削弱 mandatory authority coverage；完成、finding、authorization 和 acceptance-passed 均不得由 assistant prose 或上游布尔声明建立。
- 历史 `vcec-r1`、`vcec-r1m`、`vcec-r1n` 失败证据不可重写为成功。
- 本合同仅覆盖 repository toolchain control plane，不改变 Phase service 或 user sandbox 的模型验收行为。
- Canonical serialization、schema 字段、retry 次数、projection budget 和 policy threshold 由 Architecture/Policy ratify；本 SPEC 不提前冻结未决实现参数。

## Non-goals

- 不新增任何 single-reviewer authorizing profile，也不把 Bootstrap Complete Review 改成默认单 reviewer。
- 不在 Bootstrap 中内置 8-13、source-freeze、exact-cover、shard 或 retry 等计划专属命令。
- 不以 Git diff 作为唯一验收 authority。
- 不通过 sampling、自由摘要或 reviewer 自选片段压缩 normative authority。
- 不允许 Bootstrap 产生 draft、plan-ready、implementation-authorized、implementation-complete 或 acceptance-passed。
- 不通过提高 snapshot/context 上限掩盖错误 closure。
- 不改变 maintainer authorization owner 的发布 authority。
- 不自动调整模型价格、模型供应商或全局 token quota。
- 不迁移或重写历史 Bootstrap run。
- 不把全部 repository review 工作流、Phase service 或 user sandbox 纳入本产品。

## Success signal

- 在 8-13 规模回归中，deterministic failure 不启动 reviewer；mandatory Bootstrap 仍完成三角色同闭包审查；无越界读取、stale lease、人工 executable/receipt 修补或无界重试；Acceptance 能用当前 identity-bound evidence 独立发布 acceptance-passed，且语义 corpus 不出现 reference baseline 未允许的 false authorization。

## Assumptions

- 8-13 规模 Consumer Closure 相对 whole-plan baseline 至少缩减 75% 是 M2 前的 provisional target。
- 外部模型服务正常且无需 independent verifier 时，full Bootstrap 低于 60 分钟是 M2 前的 provisional target。
- 无人值守 no-progress window 初始为 60 分钟，且只由 Effective Progress Event 刷新，等待 M0 policy ratification。

## Open Questions

- 正式 full-Bootstrap 目标采用 60 分钟，还是仅采用相对四小时基线的改善比例？Owner：Acceptance/Bootstrap policy owner；M2 首个稳定基线后复议。
- Closure 缩减采用 provisional 75%，还是按 workload bucket 动态计算？Owner：Acceptance/Bootstrap policy owner；M2 baseline 与 completeness corpus 通过后复议。
- Range Projection 沿用现有 model-visible budget，还是建立独立 Acceptance closure budget policy？Owner：Architecture；阻塞 M1 完成。
- no-progress ceiling、terminal grace 和 lease reconciliation window 共用一个 policy family，还是分别版本化？Owner：Bootstrap control-plane policy owner；阻塞 M0 完成。
- `vcec-r1n` 应采用哪一种正式非授权终态以保留回归价值并禁止复用？Owner：Bootstrap lineage owner；阻塞新策略正式回归。
