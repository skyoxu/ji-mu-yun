---
source_plan: execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/08-implementation-phases.md
baseline_commit: 80a863628c6224d80a53a0d7f4bfc07fc061a2fa
---

# Story 1.3: Phase 2 Iteration Plan Traceability Gate

Status: done

## Story

作为 Phase A 平台维护者，
我需要让 iteration plan 成为绑定当前 Requirement Map、Prototype Contract、Godot UI/style 合同和确认状态的可追溯执行计划，
从而保证任何 P0/P1 requirement、动态 UI、第三人称 camera 或交互区域要求都不会在进入 Codex 执行前丢失或被旧计划绕过。

## Acceptance Criteria

1. `PrototypeIterationPlanService` 只为当前 account/project 的 fresh Requirement Map、canonical Prototype Contract、scene/GDD state 和 new-chain skeleton source 创建计划；missing、unknown、stale、mirror mismatch、unresolved admin/diagnostic blocker 在 LLM/Codex 前 fail closed。
2. `meta/routes/iteration-plan/latest.json` 记录 `source_gdd_hash`、`source_scene_route_hash`、`source_requirement_map_hash`、`source_contract_hash`、`source_contract_snapshot_hash`、`source_godot_ui_contract_hash`、`source_ui_style_contract_hash`、`ui_style_snapshot_hash`；每个 goal 使用同一 hash set 或稳定 `source_hash_ref`。
3. 每个 P0/P1 requirement 必须被 goal、独立 required module、已验证 skeleton capability 或显式 blocker 覆盖；empty、duplicate、unknown、orphan requirement ID 或 coverage gap 返回稳定 blocker，计划不得 ready。
4. 每个 goal 至少包含一个 `requirementId`；纯 infrastructure goal 必须包含结构化 infrastructure reason。每个 required module 包含稳定 module ID、`requirementIds[]`、source reason/refs、priority、coverage status、validation refs。
5. Deckbuilder 的 `route_map_path_selection`、`hand_card_dragging`、combat HUD 与 reward selection 保持独立可见，并携带 requirement links；admin-approved conflict suppression 必须引用具体 decision evidence，不能静默删除默认模块。
6. 每个 P0/P1 UI-facing requirement 生成 goal/module 或结构化 blocker，明确 Godot scene/node ownership、surface type、layout/viewport/CanvasLayer、input/focus、feedback state、state boundary 和 validation method；`no_ui_needed` 仅豁免 UI surface 且必须带审核 evidence。
7. 动态 UI goal 保留 `godot_ui_update_ownership` 的 construction owner、update mode、state owner、cleanup policy、signal ownership和 stable item identity；任一必需字段缺失时返回 `ui_update_ownership_missing`，不得调用 Codex。
8. 第三人称 camera goal 保留 repo-owned rig/profile refs、target/input/collision ownership、camera-relative movement boundary 和 camera-state validation；缺失时返回 `third_person_camera_profile_missing`，不得调用 Codex 或生成 feature-local orbit math。
9. UI goal 从 frozen style snapshot 派生 style token、component family、design DNA/composition/motion、UI tree readback 和 visual evidence expectations；不得重新使用 mutable broad style guide 作为 authority，`style_not_applicable` 只能豁免 style scope。
10. UI/input/physics/camera/map/custom-drawing goal 记录 viewport/coordinate/input/layer/profile semantics、reading evidence，以及 interaction-region artifact 或 reviewed `no_interaction_region_needed` rationale；deckbuilder route map 与 hand dragging 不允许该豁免。
11. Browser 将 goals 与 required modules 分区显示，展示 requirement IDs、source reason、UI/style/interaction expectations、blockers 和 source hashes；新链 plan 必须对当前 session + plan hash 显式确认，计划或 source hash 变化使确认失效。
12. 未确认、blocked、stale 或 legacy-without-hashes 的 plan 不得执行。`PrototypeIterationGoalService` 在创建 run、占用 runner lock 或调用 `CodexHostedProcessCommandFactory` 前验证 plan confirmation、完整 source hashes、ownership/camera/interaction gates。
13. `iteration-plan` route contract 包含完整 source artifacts/hash fields、source boundary、account/admin/diagnostic surfaces 和 tests；`create_iteration_plan` 在 Phase 2 激活，`execute_next_goal`、`run_needs_fix`、`run_ui_closure`、`preview_package` 继续 phase-gated/forbidden。
14. Create/confirm/read/list/evaluate/delete/execute responses 使用 server-side no-store、account isolation 和 browser-safe DTO；POST operation status 为 `created_run|returned_existing|active_run_reused|rejected`，rejected envelope 含 stable domain code/request ID，normal user 不见 host path/raw prompt/provider/account/admin row evidence。
15. 相同 account/project/source-hash/request identity 的 double-click、network retry 和 concurrent create 复用同一 active/result state；不同 hash/project/account 不复用。Confirmation 对相同 plan hash 幂等，对不同 hash conflict；regeneration 自动失效旧 confirmation。
16. `coverage_gap`、`ui_update_ownership_missing`、`third_person_camera_profile_missing`、interaction/source/confirmation failures 写入 append-only diagnostic spool 并按 unresolved source scope 去重；legacy plans 继续 readback，但缺 hashes/confirmation 时只能重新生成或确认新 hash-bound plan。
17. Deckbuilder、RPG、generic fallback、stale/missing source、admin-approved conflict、dynamic UI、third-person camera、interaction-region、retry/concurrency/account isolation均有确定性测试；Phase 1 的 1219-test baseline 不回退。
18. Phase 2 hardening smoke/governance audit 覆盖 Requirement Map -> Contract -> Iteration Plan -> Confirmation，append-only exit evidence 记录 route/artifact/API/browser/Phase 0A/0B/capability/diagnostic/regression rows，unresolved P0/P1/必须修 P2 为 0。

## Tasks / Subtasks

- [x] Task 1: 固化 Phase 2 route governance 与 traceability contract（AC: 1-4, 13-16）
  - [x] 为完整八 hash、requirement-ID 闭集、operation status、no-store、account boundary 和 canonical error envelope 建立 RED。
  - [x] 更新 `RouteActionDescriptors`、`RouteModuleContracts`、freshness/phase registry 与 fixtures；只激活 `create_iteration_plan`。
  - [x] 建立 iteration-plan source/goal/module/confirmation DTO 与 sidecar schema；优先复用 route sidecar，只有确需 DB 持久化时才做 additive migration。
- [x] Task 2: 实现 Requirement Map -> goals/modules 的闭集 traceability（AC: 2-6, 9-10, 17）
  - [x] 读取 Phase 1 authority sidecars，生成 goal/module requirement links、source reasons、UI surface/style/validation fields。
  - [x] 保留 deckbuilder route-map、hand drag/drop、combat HUD、reward selection 的独立模块/goal coverage。
  - [x] fail closed 处理 P0/P1 漏项、duplicate/orphan ID、未审核 exemption 和 admin/diagnostic blocker。
- [x] Task 3: 传播 dynamic UI、camera、Godot semantics 与 interaction-region evidence（AC: 6-10, 12, 16）
  - [x] 从 Requirement Map 传播 `godot_ui_update_ownership` 与 `godot_third_person_camera_profile` 到计划 readback/prompt contract。
  - [x] 为 UI/style/engine reading/interaction-region 建立结构化 fields、accepted rationale 和 diagnostic mapping。
  - [x] 在 execution run/lock/Codex 前返回稳定 fail-fast domain code，证明 runner 未被调用。
- [x] Task 4: 实现 hash-bound module-plan confirmation 与 duplicate-run 闭环（AC: 11-16）
  - [x] 新增 account-safe confirm/status readback，confirmation 绑定 session ID、plan hash 和八 hash set。
  - [x] 相同 create/confirm 请求幂等复用；并发 create 返回 `active_run_reused` 或 `returned_existing`，regeneration/source drift 失效 confirmation。
  - [x] legacy plan 可读但不可执行；execute-next 在计划未确认或 source drift 时 fail closed。
- [x] Task 5: 完成 Browser module confirmation UX（AC: 5, 11-15）
  - [x] goals/modules 分区显示 requirement IDs、source reason、UI/style/interaction expectations、blockers 与 freshness。
  - [x] 提供真实 confirmation control/state；未确认/stale/blocked/legacy plan 禁用 execute，且不靠说明文字冒充 gate。
  - [x] 所有 caller 使用 no-store、标准 error projection 和当前 account/project context。
- [x] Task 6: Phase 2 回归、对抗审查与退出（AC: 17-18）
  - [x] 逐任务运行目标测试，最后运行全量 PhaseA tests、hardening smoke、governance audit、JSON/link/ref 与 `git diff --check`。
  - [x] 使用 BMAD code review 的 Blind Hunter、Edge Case Hunter、Acceptance Auditor，修复全部 P0/P1/必须修 P2。
  - [x] 写 append-only Phase 2 regression/exit evidence，Story 仅在所有门禁通过后转 `review`。

## Dev Notes

### Current RED Baseline

- `PrototypeIterationPlanService.CreateAsync` 从 message/prototype contract 生成目标，但不把 Phase 1 Requirement Map 作为闭集输入；goal/module models 没有 requirement IDs 或完整 source hash set。
- iteration-plan sidecar 只有 `source_boundary` 字符串、selected capabilities 和旧 required modules；缺八 hash、plan hash、confirmation、blocking issues 和 source-boundary object。
- `PrototypeIterationGoalService.ExecuteNextAsync` 只检查当前 contract fresh，不比较 plan 创建时 hashes，也不检查 confirmation、ownership/camera/interaction evidence。
- Browser 的 `data-module-plan-confirmation` 只是静态说明；`requirement_ids_pending` 是占位，执行没有真实确认门。
- `create_iteration_plan` descriptor 当前 `not_active`；iteration route contract 只声明 3 个 hash；iteration endpoints 未统一 server-side no-store/operation envelope。

### Existing Components To Extend

- `PrototypeIterationPlanService`：保留 game-type-specific scaffold/refinement/evaluation；在目标生成之后、DB/session 创建之前增加 authority input、traceability enrichment 与 coverage gate，不重写 4500 行现有路线逻辑。
- `PrototypeIterationPlanResult` / `ProjectIterationGoalSnapshot`：采用 additive fields 或 route-state merge，保持既有 JSON 字段和 legacy readback。
- `PrototypeRouteStateWriter`：继续拥有 `meta/routes/iteration-plan/latest.json`；新增 schema/hash/confirmation 仍在该 canonical path，不创建第二套 plan authority。
- `PrototypeIterationGoalService`：在 `CreateRunAsync`、runner lock、heavy-runner lease 和 Codex 前增加纯 read-only preflight；后续执行路径保持不变。
- `ProjectMutationLockRegistry`：复用 Phase 1 reference-counted keyed lock，覆盖 plan create/confirm 同 project mutation。
- `PhaseAMetadataStore` diagnostic/admin query：复用 account/project-scoped query和 unresolved diagnostic dedupe；不手工修改 live DB。
- `RouteActionDescriptors` / `RouteModuleContracts`：从机器权威激活 Phase 2，不在 Program/Browser 复制 canonical action 名。
- `BrowserUiRenderer`：复用现有 iteration plan cards/action helpers，替换静态 confirmation 占位并保持 compact operational UI。

### Architecture And Safety Guardrails

- 遵守 ADR-0032、ADR-0036、ADR-0038、`docs/standards/phase-service.md`、Godot engine/UI/style/diagnostics standards。
- Canonical contract 始终为 `routes/prototype-contract/latest.json`；mirror 不能成为 authority。
- Sidecar 使用 snake_case，ASP.NET DTO 使用 camelCase；path 全部 project-root constrained，普通用户只见相对/browser-safe evidence。
- Source-boundary 必须继承 `hosted-route-recovery-order.v1`，authority 顺序包含 route profile、project execution guide、canonical contract、requirement map、current route state；禁止 raw mutable game-type/style guide 成为 gameplay authority。
- 新 route/action 必须 server-side no-store、existence-hiding account boundary、stable domain code、append-only evidence。
- 不修改 runtime/Caddy/auth/token/live metadata DB；若 metadata schema 必须扩展，使用 normal additive migration/reuse tests并记录恢复路径。
- 规范 domain code 为 `ui_update_ownership_missing`；同步修正 durable standard 中旧的 `ui_update_owner_missing` 术语漂移。

### RED Test Matrix

- Plan source/hash：八 hash 持久化；任一 drift 在 Codex 前阻断；legacy missing hashes 只读。
- Coverage：P0/P1 complete、missing、duplicate、empty、unknown、orphan、blocker/module/skeleton 互斥边界。
- Capability：dynamic UI ownership 每字段缺失；third-person rig/target/input/collision/validation 每字段缺失。
- UI/style/interaction：UI surface contract、frozen style fields、reading evidence、artifact/rationale；route-map/hand-drag禁止豁免。
- Confirmation：same-hash idempotent、different-hash conflict、regeneration invalidation、confirm/execute race。
- Duplicate create：same account/project/hash reuse；cross-project/account/hash isolation。
- Browser/API：真实 confirmation、execute disabled、goals/modules traceability、no-store、error envelope、redaction。

### Previous Story Intelligence

- Phase 1 checkpoint `80a8636` 建立 authority scene/GDD/Requirement Map/Contract hashes、fail-closed contract freeze、admin-safe blockers、diagnostic dedupe、server-side no-store 和共享 project mutation lock。
- Phase 1 对抗审查证明只检查 row count、静态 UI marker、global queue window 或当前 fresh contract 都不足以构成门禁；Phase 2 必须验证 identity、source scope、readback 与执行前行为。
- Phase 1 全量基线为 1219/1219；Phase 2 不得以放宽 legacy/new-chain 边界或禁用测试换取通过。

### References

- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/08-implementation-phases.md#phase-2-iteration-plan-traceability-gate`
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/02b-backend-api-contracts.md#63-extend-prototypeiterationplanservice`
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/02c-frontend-migration-compatibility.md#84-module-plan-confirmation-ui`
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/03-testing-observability-admin.md`
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/04a-route-contracts-and-guards.md`
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/04c-route-operation-governance.md`
- `docs/standards/phase-service.md`
- `docs/standards/godot-engine-semantics.md`
- `docs/standards/godot-ui-capability-contract.md`
- `docs/standards/godot-ui-style-contract.md`
- `docs/standards/godot-diagnostics-quality-gates.md`

## Dev Agent Record

### Agent Model Used

Codex GPT-5.6

### Debug Log References

- Story baseline candidate: `80a8636`.
- Phase 2 context audit: 3 P0, 6 P1, and 2 must-fix P2 implementation gaps identified before RED.

### Implementation Plan

- Execute Task 1 -> 6 strictly in order with RED/GREEN/REFACTOR and per-task acceptance gates.
- Task 1: activate only `create_iteration_plan`, declare the complete frozen authority boundary, add additive Phase 2 result contracts, enforce no-store and standard rejected envelopes, then validate against the full PhaseA suite.
- Task 2: preserve existing game-type planners, then apply a deterministic Requirement Map enrichment/closure builder that synthesizes mapped modules, binds goal/module requirement IDs, creates UI/style projections, computes plan/source hashes, and blocks unresolved coverage before session creation.
- Task 3: carry complete UI update and third-person camera ownership through the frozen requirement map, generate engine-reading and interaction-region evidence, and enforce a pure execution preflight before any run, lock, heavy-runner lease, or Codex invocation.
- Task 4: bind confirmation to the current session/plan/source hash identity, preserve per-session route state for historical readback, reuse same-identity creates under the shared project lock, and require confirmation plus current hashes before execution.
- Task 5: replace the static browser confirmation marker with a real hash-bound confirmation action, expose goal/module traceability and blockers, and keep execution disabled until the current plan is confirmed and executable.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Task 1 completed: Phase 2 action/route registries, eight-hash freshness edges, additive traceability DTOs, iteration endpoint no-store, and standard rejected error projection are implemented. Targeted tests passed 16/16; full PhaseA regression passed 1225/1225 with zero skips.
- Task 2 completed: new-chain iteration plans now consume the fresh frozen Requirement Map/Contract identity, close P0/P1 coverage across goals and independently visible modules, persist snake_case traceability with all eight hashes, and fail closed before DB session creation. Builder/integration tests passed; full PhaseA regression passed 1230/1230 with zero skips.
- Task 3 completed: dynamic UI signal/lifecycle ownership, repo-owned third-person camera movement/state boundaries, feature-family reading evidence, and per-goal interaction-region artifacts are propagated and checked before execution. Failures use stable diagnostic families with unresolved-scope dedupe, and the runner remains untouched. Full PhaseA regression passed 1237/1237 with zero skips.
- Task 4 completed: confirm/readback is account-safe and hash-bound, same-hash confirms and create retries are idempotent, concurrent same requests reuse one session, regeneration invalidates prior confirmation, historical rounds retain their own sidecars, and legacy/unconfirmed/stale plans cannot execute. Full PhaseA regression passed 1241/1241 with zero skips.
- Task 5 completed: the Browser now renders separate goal/module traceability, source hashes, UI/style/interaction expectations and blockers; confirmation is a real server-backed control, and unconfirmed, stale, blocked or legacy plans cannot invoke execute. Browser tests passed 63/63 and full PhaseA regression passed 1242/1242 with zero skips.
- Task 6 completed: all accepted Blind Hunter, Edge Case Hunter, and Acceptance Auditor findings were fixed and re-reviewed clean. Final PhaseA regression passed 1294/1294 with zero skips; API E2E, hardening smoke, governance audit, Whole-directory mechanical review, Python 9/9, fixture JSON parsing, and diff checks passed. Append-only exit evidence is recorded under `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase2-exit-20260712T002000Z/`.
- Final closure rerun completed after `PH2-AA-P2-001`: structured prototype-skeleton source-boundary validation now fails closed before LLM use. Final regression passed 1300/1300 with zero skips; API E2E, hardening smoke, governance audit, Whole-directory mechanical review, Python 9/9, fixture JSON parsing, and diff checks passed. Final append-only evidence is under `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase2-exit-final-20260712T005219Z/`.

### File List

- `_bmad-output/implementation-artifacts/1-3-phase2-iteration-plan-traceability-gate.md`
- `PhaseA.Platform/Program.cs`
- `PhaseA.Platform/Runs/PrototypeIterationPlanResult.cs`
- `PhaseA.Platform/Runs/IterationPlanTraceabilityBuilder.cs`
- `PhaseA.Platform/Runs/IterationPlanExecutionPreflight.cs`
- `PhaseA.Platform/Runs/IterationPlanIntegrity.cs`
- `PhaseA.Platform/Runs/IterationPlanInteractionArtifactValidator.cs`
- `PhaseA.Platform/Runs/ProjectDiagnosticScopeKey.cs`
- `PhaseA.Platform/Runs/PrototypeSkeletonAuthorityGate.cs`
- `PhaseA.Platform/Runs/GameDesignRequirementMapService.cs`
- `PhaseA.Platform/Runs/PrototypeIterationGoalService.cs`
- `PhaseA.Platform/Runs/PrototypeRouteStateWriter.cs`
- `PhaseA.Platform/Runs/PrototypeWorkflowService.cs`
- `PhaseA.Platform/Runs/PrototypeNeedsFixRouteService.cs`
- `PhaseA.Platform/Runs/GddMilestoneStepService.cs`
- `PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs`
- `PhaseA.Platform/Data/PhaseAMetadataStore.cs`
- `PhaseA.Platform/Data/ProjectGovernanceRecords.cs`
- `PhaseA.Platform/Data/ProjectIterationSessionSnapshot.cs`
- `PhaseA.Platform/Data/SqliteMetadataSchema.cs`
- `PhaseA.Platform/Browser/BrowserUiRenderer.cs`
- `PhaseA.Platform/Workflow/GodotDiagnosticsQualityGate.cs`
- `PhaseA.Platform/Workflow/RouteActionDescriptors.cs`
- `PhaseA.Platform/Workflow/RouteFreshnessPolicy.cs`
- `PhaseA.Platform/Workflow/RouteModuleContracts.cs`
- `PhaseA.Platform.Tests/Browser/BrowserUiRendererTests.cs`
- `PhaseA.Platform.Tests/Fixtures/route-action-descriptors.v1.json`
- `PhaseA.Platform.Tests/Fixtures/route-module-contracts.v1.json`
- `PhaseA.Platform.Tests/Runs/PrototypeIterationPlanServiceTests.cs`
- `PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs`
- `PhaseA.Platform.Tests/Runs/IterationPlanTraceabilityBuilderTests.cs`
- `PhaseA.Platform.Tests/Runs/IterationPlanExecutionPreflightTests.cs`
- `PhaseA.Platform.Tests/Runs/PrototypeRouteStateWriterTests.cs`
- `PhaseA.Platform.Tests/Data/SqliteMetadataSchemaTests.cs`
- `PhaseA.Platform.Tests/Workspaces/ProjectWorkspaceSeederTests.cs`
- `PhaseA.Platform.Tests/Workflow/RouteActionDescriptorsTests.cs`
- `PhaseA.Platform.Tests/Workflow/RouteFreshnessPolicyTests.cs`
- `PhaseA.Platform.Tests/Workflow/RouteModuleContractsTests.cs`
- `docs/standards/godot-diagnostics-quality-gates.md`
- `docs/standards/godot-ui-capability-contract.md`
- `scripts/python/phase_a_iteration_plan_e2e.py`
- `scripts/python/tests/test_phase_a_iteration_plan_e2e.py`
- `scripts/python/tests/test_phase_a_gdd_to_module_governance_audit.py`

## Change Log

- 2026-07-11: Created Phase 2 implementation Story from the execution-plan authority and Phase 1 review intelligence.
- 2026-07-11: Completed Task 1 route governance and additive traceability contract baseline; full regression 1225/1225.
- 2026-07-11: Completed Task 2 Requirement Map closure and route-sidecar traceability; full regression 1230/1230.
- 2026-07-11: Completed Task 3 capability propagation, interaction artifacts, and pre-Codex execution preflight; full regression 1237/1237.
- 2026-07-11: Completed Task 4 hash-bound confirmation, duplicate request reuse, and historical session readback; full regression 1241/1241.
- 2026-07-11: Completed Task 5 Browser confirmation and traceability UX; full regression 1242/1242.
- 2026-07-12: Completed Task 6 regression and BMAD closure review; final regression 1294/1294, API E2E/smoke/audit/Whole-directory review clean, unresolved P0/P1/must-fix P2 = 0, Story closed as done.
- 2026-07-12: Closed `PH2-AA-P2-001`, reran final acceptance and edge-case review clean, and refreshed all exit gates; final regression 1300/1300 and unresolved P0/P1/must-fix P2 remains 0.
