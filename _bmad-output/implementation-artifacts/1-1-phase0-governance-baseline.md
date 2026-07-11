---
baseline_commit: cf2b4db
---

# Story 1.1：Phase 0 治理机器契约基线闭环

## Story

作为 Phase A 平台维护者，我需要把 Whole-directory review 后更新的计划机器契约同步到运行时注册表、持久化镜像和确定性测试中，使 Phase 0A/0B 的治理基线在进入 Phase 1 前具备一致、可解析、可回归的实现证据。

## Acceptance Criteria

1. split-added ledger 按当前 6 列契约解析全部 18 行，并验证稳定 owner ID、首个必需阶段、owner docs 与多个 acceptance IDs。
2. split-added acceptance registry 可解析，ledger 中每一行均与 registry 的 owner 和 acceptance 映射一致；缺失、孤儿、错配或重复项会产生稳定错误原因。
3. coverage validator 对全部 18 行保持闭集检查，并验证 owner doc、acceptance evidence 与 phase-exit evidence；无效 defer/not-applicable 仍被拒绝。
4. Original split inventory 与当前 29 个规范 Markdown/机器 JSON 输出一致，持久化 schema 示例同步更新；重复和缺失项仍被拒绝。
5. Source coverage map 的 16 个原始范围连续覆盖 1–2739，并允许 99 中明确的 split-added machine-contract refs，同时证明 98 的原始 source refs 是其有序子集。
6. execution-plan、docs schema 与测试 fixture 的 Godot UI style example 完全一致且均可解析。
7. Workflow 测试组 118/118 通过；相关目标测试与 JSON 解析检查通过。
8. Phase 0 exit evidence 以 append-only run-id 文件写入 logs，并记录零 unresolved P0/P1/必须修 P2；若 Phase 0 的更大范围仍有失败，不得把 story 标为 review。

## Tasks / Subtasks

- [x] Task 1：升级 split-added ledger 与 registry 机器契约
  - [x] 先更新/新增测试，固定 6 列、18 行、owner/phase/multiple acceptance IDs 与 registry 负例。
  - [x] 实现 parser、row model、registry model 和稳定 validation reasons。
  - [x] 同步 docs schema example，并运行目标测试。
- [x] Task 2：同步 original split inventory 与 source coverage parity
  - [x] 先更新/新增测试，固定 29 项 inventory 和 split-added source ref 规则。
  - [x] 更新 runtime registry、schema examples 与匹配逻辑。
  - [x] 运行 original split/source coverage 目标测试。
- [x] Task 3：同步 Godot UI style fixture 镜像
  - [x] 将 execution-plan example 作为权威，同步 docs 与 test fixture。
  - [x] 运行 style snapshot schema 目标测试和 JSON parse 检查。
- [x] Task 4：完成 Phase 0 回归和阶段证据
  - [x] 运行 Workflow 分组并达到 118/118。
  - [x] 分组定位并处理全量测试 busy-loop 或其真实失败，不以延长超时掩盖问题。
  - [x] 运行 Phase 0 相关确定性检查与 hardening smoke。
  - [x] 写入 append-only Phase 0 exit review evidence；仅在 Phase 0 完整门禁通过后完成本 story。

### Review Findings

- [x] [Review][Patch][PH0-REV-001][High] Registry parser 对缺失字段、错误类型、schema_version/path_base 漂移必须 fail-closed，并返回稳定 parse reason。[PhaseA.Platform/Workflow/GddToModuleSplitAddedRequirements.cs:153]
- [x] [Review][Patch][PH0-REV-002][High] Registry/ledger 必须拒绝重复 owner docs、acceptance IDs，并报告 orphan owner、orphan acceptance ref 及空 acceptance 定位字段。[PhaseA.Platform/Workflow/GddToModuleSplitAddedRequirements.cs:214]
- [x] [Review][Patch][PH0-REV-003][High] Coverage row 必须显式闭合 ledger acceptance IDs，不能仅凭任意非空 evidence 字符串通过。[PhaseA.Platform/Workflow/GddToModuleSplitAddedRequirements.cs:287]
- [x] [Review][Patch][PH0-REV-004][Medium] Source coverage parity 必须拒绝重复 ref，并把允许的 split-added machine refs 绑定到 1378-2178 范围。[PhaseA.Platform/Workflow/GddToModuleSourceCoverageMap.cs:94]
- [x] [Review][Patch][PH0-REV-005][Medium] Original split inventory 必须是严格 29 项闭集，拒绝第 30 个未声明输出。[PhaseA.Platform/Workflow/GddToModuleOriginalSplitAudit.cs:167]
- [x] [Review][Patch][PH0-REV-006][High] Question-form 最后 waiter 取消必须同时避免同 cache key 加入已取消任务，并对不响应 cancellation 的底层清理设置有界等待。[PhaseA.Platform/Runs/GameDesignQuestionFormService.cs:48]
- [x] [Review][Patch][PH0-REV-007][High] Durable split-added workflow standard 必须同步当前 6 列 ledger 与 acceptance registry 契约。[docs/workflows/phase-a-gdd-to-module-split-added-requirements.md:16]
- [x] [Review][Patch][PH0-REV-008][High] Phase 0 exit evidence 必须逐行分类受影响 split_added_id，并按 touched route 记录 Phase 0B dependency matrix。[logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-0-exit-review-20260711T051327Z.json:1]
- [x] [Review][Patch][PH0-REV-009][Medium] Smoke/audit evidence refs 必须指向目录内可解析的 summary.json，而不是伪装成 .json 的目录。[logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-0-exit-review-20260711T051327Z.json:61]
- [x] [Review][Patch][PH0-REV-010][Medium] Style schema profile/hash 必须纳入新 fixture 的 visual_evidence_matrix.readback_path_policy 与 visual_validation_refs evidence/status 字段。[PhaseA.Platform/Workflow/GodotUiStyleSnapshotSchema.cs:184]

## Dev Notes

- 权威计划目录：execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/。
- 阶段权威：08-implementation-phases.md；Phase 0A 是 Phase 1 的硬阻塞，触及能力所需的 Phase 0B 同样是阻塞。
- 计划审查基线：0647e53，83 个 finding 全部 Closed；实现基准：cf2b4db。
- 遵守 ADR-0032、ADR-0036、ADR-0038 及 docs/standards/phase-service.md。
- 不修改 live metadata DB、认证、runtime/Caddy 或共享 LLM 入口。
- 中文文档通过 Python 显式 UTF-8 写入；代码、测试与机器输出使用英文。
- 失败证据保留，日志使用新 run-id sidecar，不覆盖历史。
- 现有 Workflow RED：6 个失败，涉及 style fixture、split-added parser/coverage、inventory 与 source coverage parity。

## Dev Agent Record

### Implementation Plan

- 以现有 6 个 Workflow 失败为 RED 起点，按 Task 1 → 4 顺序执行。
- 每个 task 先扩充负例和契约测试，再实现最小正确改动，最后重构并跑目标回归。
- Phase 0 完整回归与证据未通过前不进入 Phase 1。

### Debug Log

- RED：Workflow 118 项中 6 项失败，确认旧 ledger、inventory、coverage 和 style fixture 漂移。
- GREEN：升级为 6 列/18 行 ledger、29 项 inventory、允许声明式 split-added source refs，并同步 style fixture。
- RED：Readback 分组在 run-duration pruning policy 测试触发 45 秒 hang dump。
- GREEN：将大规模逐条 setup 改为单次确定性 SQL seed，再通过生产 completion path 触发三个 bucket 的 prune；Readback 112/112。
- RED：Runs 分组 28 项失败，均由测试仍依赖 raw GameTypeSource 导致 route profile 退化。
- GREEN：测试夹具写入 canonical game_type_match_json；Repair 14/14、Iteration Goal 58/58、Needs Fix 20/20、GdUnit 4/4。
- RED：完整套件剩余 question-form last-waiter cancellation limiter race。
- GREEN：最后一个 waiter 取消时等待底层清理释放 lease；共享 waiter 不被误取消；完整套件 1188/1188。
- REVIEW RED：三层对抗审查识别 10 个需修补 finding，覆盖 registry fail-closed、闭集校验、route cancellation、durable docs、Phase 0 evidence 和 style schema hash。
- REVIEW GREEN：10 个 finding 全部修复；新增 malformed/duplicate/orphan/closed-set/same-key cancellation/bounded-cleanup 回归测试；完整套件 1194/1194。

### Completion Notes

- 完成 split-added ledger、acceptance registry、coverage validator 的当前契约实现与负例覆盖。
- 完成 original split 29 项 inventory、98/99 有序子集匹配与 schema 镜像同步。
- 完成三份 Godot UI style fixture 字节级同步和 JSON 解析校验。
- 消除 Readback hang、修正结构化 game-type 测试权威、关闭 question-form 取消竞态。
- 验证：Workflow 121/121、Readback 112/112、Runs 679/679、全量 1188/1188。
- hardening smoke 与 governance audit 均为 status=ok；205 个计划 Markdown 链接无缺失，11 个相关 JSON 均可解析。
- Phase 0 exit review 记录 P0=0、P1=0、P2=0。
- 对抗审查补丁全部完成：10 handled、0 deferred、2 dismissed；registry、coverage、inventory、source refs、question-form cancellation 和 style hash 均已补强。
- 新的 append-only exit review 逐行闭合全部 18 个 split-added requirement，并记录本轮 6 个 touched route 的 Phase 0B dependency matrix。
- Post-review 验证：完整套件 1194/1194（6m42s），关键审查路径窄回归 55/55，hardening smoke 与 governance audit 均为 status=ok，`git diff --check` 通过。

## File List

- PhaseA.Platform/Workflow/GddToModuleSplitAddedRequirements.cs
- PhaseA.Platform/Workflow/GddToModuleOriginalSplitAudit.cs
- PhaseA.Platform/Workflow/GddToModuleSourceCoverageMap.cs
- PhaseA.Platform/Runs/GameDesignQuestionFormService.cs
- PhaseA.Platform.Tests/Workflow/GddToModuleSplitAddedRequirementsTests.cs
- PhaseA.Platform.Tests/Workflow/GddToModuleOriginalSplitAuditTests.cs
- PhaseA.Platform.Tests/Workflow/GddToModuleSourceCoverageMapTests.cs
- PhaseA.Platform.Tests/Workflow/GodotUiStyleSnapshotSchemaTests.cs
- PhaseA.Platform.Tests/Readback/ArtifactReadbackServiceTests.cs
- PhaseA.Platform.Tests/Runs/GameDesignQuestionFormServiceTests.cs
- PhaseA.Platform.Tests/Runs/PrototypeRepairPlanServiceTests.cs
- PhaseA.Platform.Tests/Runs/PrototypeIterationGoalServiceTests.cs
- PhaseA.Platform.Tests/Runs/PrototypeNeedsFixRouteServiceTests.cs
- PhaseA.Platform.Tests/Runs/PrototypeGdUnitPathResolverTests.cs
- PhaseA.Platform.Tests/Fixtures/godot-ui-style-contract.v1.example.json
- docs/schemas/gdd-to-module-split-added-requirements.v1.example.json
- docs/schemas/gdd-to-module-original-split-audit.v1.example.json
- docs/schemas/gdd-to-module-source-coverage-map.v1.example.json
- docs/schemas/godot-ui-style-contract.v1.example.json
- docs/workflows/phase-a-gdd-to-module-split-added-requirements.md
- _bmad-output/implementation-artifacts/1-1-phase0-governance-baseline.md
- logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-0-post-review-smoke-20260711T065851Z/summary.json
- logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-0-post-review-governance-20260711T065851Z/summary.json
- logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-0-regression-summary-20260711T071611Z.json
- logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-0-exit-review-20260711T071611Z.json

## Change Log

- 2026-07-11：完成 Phase 0A/所需 0B 机器契约同步、全量回归闭环与阶段退出证据，状态转为 review。
- 2026-07-11：创建 Phase 0 治理机器契约闭环 story。
- 2026-07-11：完成三层对抗审查的全部 10 个 patch，追加完整 exit evidence，状态转为 done。

## Status

done
