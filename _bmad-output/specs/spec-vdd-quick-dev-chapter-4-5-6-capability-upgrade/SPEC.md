---
id: SPEC-vdd-quick-dev-chapter-4-5-6-capability-upgrade
package_schema: canonical-spec-package.v1
companions:
  - path: _bmad-output/specs/spec-vdd-quick-dev-chapter-4-5-6-capability-upgrade/execution-protocol.md
    role: normative_companion
  - path: _bmad-output/specs/spec-vdd-quick-dev-chapter-4-5-6-capability-upgrade/architecture-diagrams.md
    role: normative_companion
  - path: docs/vdd-quick-dev-chapter-4-5-6-capability-upgrade-draft.md
    role: adopted_companion
sources:
  - path: _bmad-output/planning-artifacts/prds/prd-jimuyun-2026-08-31/prd.md
    role: provenance
  - path: _bmad-output/planning-artifacts/prds/prd-jimuyun-2026-08-31/addendum.md
    role: provenance
  - path: docs/know103.txt
    role: provenance
---

> **Canonical contract.** 本 SPEC 与 `companions:` 中的文件共同构成 VDD 与 Quick Dev Chapter 4/5/6 通用能力升级的完整机器合同。`sources:` 仅用于追溯；原始能力草案第 15、16、18.5 节作为 adopted companion 必须继续读取。

# VDD 与 Quick Dev Chapter 4/5/6 通用能力升级

## Why

当前 VDD 计划常把需求压缩成过宽 Acceptance，Quick Dev 又可能把固定失败、状态字符串或自报 artifact 当成真实 TDD 证据，导致返工、假绿和不可恢复的 lineage。需要把需求编译、真实 RED→GREEN→REFACTOR、选择性重放和终局确定性验证统一为可泛化能力，使 AI 主导的 self-hosted 开发在约一小时内闭合中等任务，同时保持开发态不被重型治理阻塞。

## Capabilities

- **CAP-1**
  - **intent:** VDD 能从明确来源提取不可遗漏、可定位且稳定的 requirement obligation。
  - **success:** 每条 active obligation 都有稳定 ID、source ref、类型、状态和依赖；任何 hard-uncovered 在 plan-ready 前阻断。
- **CAP-2**
  - **intent:** VDD 能把 obligations 编译成可观察、可判定、可实施且不自证的 Acceptance 与 RED failure intent。
  - **success:** 每个 active Acceptance 具备 source refs、observable/expected/forbidden 语义和至少一个 RED intent；不存在 terminal 吞并局部语义。
- **CAP-3**
  - **intent:** VDD 能以 sound-and-complete many-to-many 图生成稳定 slice，并证明其写集可行。
  - **success:** requirement→obligation→Acceptance→source→slice→RED→lane→terminal 覆盖无 orphan、无无源边；不兼容 owner、lane、failure 或生命周期被拆分，合法 producer/consumer 原子例外可合并。
- **CAP-4**
  - **intent:** Quick Dev 能在昂贵动作前提供无副作用 recommendation/preflight，并维护可恢复的显式 run state。
  - **success:** recommendation-only 不运行测试、不创建 run、不改状态；`planned-only`、`observed-run`、`recovered-run`、`invalid-run` 可区分且只有真实 observed lineage 才能推进。
- **CAP-5**
  - **intent:** Quick Dev 能从 VDD intent 物化并执行真实 RED，按实际 observation 分类失败。
  - **success:** descriptor 使用 shell-free 参数数组和安全 cwd；executions≥1，observed failure 来自进程输出/断言；harness、repo-noise、timeout、zero-case 和 unexpected-green 均不能成为 expected-red。
- **CAP-6**
  - **intent:** Quick Dev 能在同一 selector 语义上完成受写集约束的 GREEN 与 REFACTOR。
  - **success:** target、fixture、assertion、cwd 和 selector identity 与 RED 相同；changed paths 全部在合法 production write set，删 case、换入口、复制 expected 值或越界写入均失败。
- **CAP-7**
  - **intent:** Quick Dev 能以真实 assertion、显式 lineage 和当前依赖闭包判定 slice-ready 与 whole-plan terminal。
  - **success:** 每个 active Acceptance 有 RED/GREEN/REFACTOR executed edge；terminal 重读 refs/hash、重算 exact cover、运行 terminal/regression/mutation，只有确定性 predicate 才产生 `implementation-complete`。
- **CAP-8**
  - **intent:** 工具链能按变化影响矩阵选择性失效、重放并恢复 observation。
  - **success:** requirements、selector、fixture、owner、compiler、validator、predecessor 变化只使受影响 lineage 失效；failure intent 语义变化从 RED 重跑；不依赖 glob、mtime 或最新成功扫描。
- **CAP-9**
  - **intent:** 独立 judge 与 detached fixtures 能证明 Quick Dev 抵抗假绿并泛化到新任务。
  - **success:** positive/negative/mutation、8-25 replay 和一个未用于设计的新中等任务通过，错误 target、复制结果、自报 pass、未来 evidence 和历史扫描均被拒绝。

## Constraints

- VDD 只声明 intent、source、Acceptance、slice、failure intent、write set 和 terminal predicate；不生成 descriptor、run ID、receipt、exit code、observation 或 pass。
- Quick Dev 物化并执行 descriptor，维护 run state；terminal 只产生 `implementation-complete`。外部独立语义验收产生 `acceptance-passed` 或 repair，maintainer 才决定 commit、PR、release。
- 所有命令必须使用参数数组、`shell=False`、仓库内安全 cwd、显式 target/fixture identity 和 declared write set。
- 模型 worker 只可在只读语义提取/对齐或受限写集内工作，不能写 plan-ready、pass 或 observed evidence；确定性 validator 拥有最终 predicate。
- Development 默认关闭 external review、candidate binding 和 authorization 阻塞；认证、TDD、语义 predicate、写集安全和运行安全不关闭。Test/production 可开启治理而不降低真实性。
- 旧 v1 计划只读兼容，历史 evidence append-only 保留；不得把 8-25 计划 ID 特判写入通用 router。

## Non-goals

- 不恢复 Taskmaster MCP，不复制 Godot/GdUnit、overlay、游戏仓专用 6.9 pipeline 或长批次 jitter/shard/quarantine。
- 不把 Chapter 6.7 LLM review、6.8 多 reviewer、分布式调度、CI/CD 或 commit/PR/release authority 纳入 Quick Dev。
- 不以状态字符串、artifact 存在、模型输出、治理 receipt 或增加 hash/schema 数量替代真实执行。

## Success signal

在 detached fixtures、8-25 replay 和一个全新中等任务上，VDD 生成无 hard-uncovered 的 exact-cover 计划，Quick Dev 完成真实 RED→GREEN→REFACTOR 与终局 deterministic validation，所有 observation 可由显式 lineage 重放且无 false-green 放行；中等任务 standard profile 目标在 60 分钟内闭合。文档或 happy-path 单测不足以宣称约 90% 能力。

## Assumptions

- 历史 v1 计划通过只读 compatibility adapter 投影；无法映射 source、selector、write set 或 lineage 时返回 repair recommendation。
- 目标使用 Windows、`py -3`、pytest 和临时 workspace；远程执行不是 v1 必需能力。

## Open Questions

- obligation 与 Acceptance 的规范化边界由 VDD 在 schema 冻结前决定。
- slice split/merge 的确定性阈值由 VDD/Architecture 在首次编译器实现前决定。
- 多 Acceptance 单 selector 的 assertion-edge schema 由 Spec 在 schema 定稿前决定。
- lightweight semantic validator 的纯确定性边界由 Architecture 冻结；模型只能产生非阻断 warning。
- v1 compatibility adapter 的字段投影和只读边界由 Architecture 在迁移试验前冻结。
- unexpected-green 的 regression/current-behavior 最低证明由 Quick Dev 在 RED materializer 前定义。
- 60 分钟目标的任务规模、环境和计时方法由 Product 在盲测前发布。
- fast-ship、standard、self-hosted 的差异由 Architecture 在 profile schema 前冻结，均不得降低真实性硬门。
- 变化何时只重算 coverage、何时必须重跑 RED 由 Spec 在 invalidation matrix 前冻结；不确定时采用更严格重跑。
- detached fixture 作者与被测 skill 的独立性由 Maintainer 在验收前以独立目录/提交和只读 judge 证明。
