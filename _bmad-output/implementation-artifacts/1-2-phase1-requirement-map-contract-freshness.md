---
baseline_commit: 9c8ac4b
source_plan: execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/08-implementation-phases.md
---

# Story 1.2：Phase 1 Requirement Map 与 Contract Freshness 完整闭环

Status: done

## Story

作为 Phase A 平台维护者，
我需要把场景确认、GDD 文档写回、Requirement Map、Prototype Contract freshness 与新链 skeleton guard 连成真实可读回的浏览器/API 工作流，
从而让新项目只能基于一致且可追溯的 GDD、场景、结构化游戏类型、Godot UI/style 合同来源进入后续模块生成。

## Acceptance Criteria

1. 场景确认写入权威 `meta/routes/scene-route/latest.json`，包含稳定 `confirmed_scene_route_hash`、`source_game_type_structured_hash`、`source_contract_snapshot_hash`、状态/操作状态、source-boundary 与 browser-safe evidence；API readback 返回真实 hash，不返回占位空字符串。
2. GDD 成功生成后写入 `meta/routes/gdd-document/latest.json`，并把同一 `source_generated_gdd_hash` 原子式写回场景 sidecar；任一写回失败必须保留 GDD 运行证据并阻断 Requirement Map，不可伪报 ready。
3. Requirement Map 对缺失、未确认、stale、结构化 game-type hash 漂移、GDD/scene hash 不一致 fail closed；输出 snake_case sidecar 与 camelCase DTO，保留 UI capability domain、动态 UI ownership、第三人称 camera profile 和 acceptance markers。
4. Requirement Map 在提供 `ILlmRouteEngine` 时使用 structured/read-only LLM 输出并执行确定性 schema/coverage 校验；LLM 不可用或输出无效时使用明确的 deterministic fallback/needs-review 行，不得静默丢失 P0/P1。
5. Prototype Contract 权威路径固定为 `routes/prototype-contract/latest.json`；可选 mirror 必须与 canonical `contract_hash` 一致。冻结结果包含并校验 `contract_hash`、GDD/scene/requirement-map/contract-snapshot/Godot UI/style source hashes、style ID/version/snapshot hash 和 source-boundary。
6. 可见 UI 项目不得以 `unknown` 作为 `source_godot_ui_contract_hash`、`source_ui_style_contract_hash` 或 `ui_style_snapshot_hash` 完成 fresh freeze；非 UI 项目必须有结构化 reviewed non-applicability，而不是隐式空值。
7. Canonical route module ID 为 `prototype-skeleton-guard`；`prototype-skeleton` 和具体 prototype endpoints 仅作为 alias。新链项目在 contract missing/stale/unknown 时不得创建 skeleton，legacy readback 只保留兼容性且不能作为 final readiness evidence。
8. Phase 1 六个 route contract 全部存在并通过 guard：`structured-game-type-analysis`、`scene-route-confirmation`、`gdd-document-generation`、`gdd-requirements`、`prototype-contract`、`prototype-skeleton-guard`。
9. Requirement Map 与 contract freeze 的 account boundary、host-path/secret/raw-prompt/admin-evidence 隔离、no-store readback、错误 envelope、double-click/retry/concurrent POST 行为有确定性测试。
10. Deckbuilder 验收链证明 route map、hand drag/drop、combat HUD、reward selection 和最低组件/input/feedback 状态不会从 GDD -> Requirement Map -> fresh Contract 中丢失。
11. Phase 1 相关全量回归、hardening smoke、governance audit 和 phase-exit review 通过，且 unresolved P0/P1/必须修 P2 为 0；否则 Story 不得进入 review/done。

## Tasks / Subtasks

- [x] Task 1：补齐场景确认与 GDD write-through 权威状态（AC: 1, 2, 9）
  - [x] 先为真实 sidecar、真实 API hash、账号隔离和写回失败建立 RED。
  - [x] 复用 `GameDesignSceneRouteService.NormalizeSubmittedSceneRoute`，实现确认持久化与 browser-safe readback。
  - [x] GDD 成功后写入 GDD route state 并更新 scene route；失败时返回稳定 domain code 和 evidence。
- [x] Task 2：完成 Requirement Map structured LLM 与能力分类（AC: 3, 4, 10）
  - [x] 保留确定性 source validation，再通过 `ILlmRouteEngine` 生成 JSON-only rows。
  - [x] 校验 stable requirement ID、P0/P1 coverage、scene/module mapping、UI capability/input/feedback/ownership/camera markers。
  - [x] 为 invalid JSON、missing row、duplicate ID、LLM failure 和 deterministic fallback 建立测试。
- [x] Task 3：完成 Prototype Contract style/UI freshness（AC: 5, 6, 9, 10）
  - [x] 从 Requirement Map 与 repo-owned style snapshot 读取真实 version/hash，不写 `unknown` 占位。
  - [x] canonical/mirror 按 `contract_hash` 校验；补齐 stale reason 和 API DTO。
  - [x] P0/P1 requirement/admin review blocker、重复 freeze 和并发 freeze fail closed/reuse。
- [x] Task 4：规范化 skeleton guard 与六个 route contracts（AC: 7, 8）
  - [x] 将 canonical module ID 改为 `prototype-skeleton-guard`，保留 alias lookup/compatibility。
  - [x] guard 覆盖 new-chain missing/stale/unknown、legacy compatibility 和 final-readiness 边界。
  - [x] workflow recommendation 保证后续动作仍在 `forbiddenActions[]`，不提前成为 primary。
- [x] Task 5：前端/API 闭环与 Phase 1 退出（AC: 1-11）
  - [x] Requirement Map panel、scene/GDD/contract readback 使用真实 camelCase fields 和 stale banners。
  - [x] 运行目标测试、全量 PhaseA 测试、Python smoke/audit、JSON/link/ref 检查。
  - [x] 写 append-only Phase 1 regression summary 和 exit review，清零 P0/P1/必须修 P2 后转 review。

### Review Findings

- [x] [Review][Patch][PH1-CR-P1-001] Validate deterministic floor identity, not only row count, before accepting structured LLM requirements. [PhaseA.Platform/Runs/GameDesignRequirementMapService.cs:484]
- [x] [Review][Patch][PH1-CR-P1-002] Recompute and validate the canonical contract hash and treat missing required freshness fields as stale. [PhaseA.Platform/Runs/PrototypeContractFreezeService.cs:202]
- [x] [Review][Patch][PH1-CR-P1-003] Query admin-review blockers by account and project so the global 500-row window cannot hide a blocker. [PhaseA.Platform/Runs/PrototypeContractFreezeService.cs:63]
- [x] [Review][Patch][PH1-CR-P1-004] Make GDD two-sidecar write-through fail closed during partial writes and validate readback against current artifacts. [PhaseA.Platform/Runs/GddToModulePhase1StateService.cs:140]
- [x] [Review][Patch][PH1-CR-P2-005] Deduplicate unresolved diagnostics emitted by retries for the same route and failure family. [PhaseA.Platform/Runs/GameDesignRequirementMapService.cs:686]
- [x] [Review][Patch][PH1-CR-P2-006] Replace unbounded static per-project semaphore dictionaries with a reference-counted keyed lock registry. [PhaseA.Platform/Runs/GameDesignRequirementMapService.cs:23]
- [x] [Review][Patch][PH1-CR-P1-007] Apply server-side no-store headers to every Phase 1 mutation and readback endpoint. [PhaseA.Platform/Program.cs:813]
- [x] [Review][Patch][PH1-CR-P1-008] Project normal-user contract blockers must not expose admin-review row IDs or metadata paths. [PhaseA.Platform/Runs/PrototypeContractFreezeService.cs:53]
- [x] [Review][Patch][PH1-CR-P0-009] Contract freeze must fail closed on P0/P1 requirement gaps, and requirement conflicts/exemptions must create admin-review ownership. [PhaseA.Platform/Runs/GameDesignRequirementMapService.cs:118]
- [x] [Review][Patch][PH1-CR-P1-010] LLM-unavailable and semantically incomplete structured rows must degrade to explicit needs-review fallback. [PhaseA.Platform/Runs/GameDesignRequirementMapService.cs:485]
- [x] [Review][Patch][PH1-CR-P1-011] First writes must report created_run, while same-input retries reuse state without erasing downstream hashes. [PhaseA.Platform/Runs/GddToModulePhase1StateService.cs:23]

## Dev Notes

### Current RED Baseline

- `Program.cs` 的 `/gdd/scene-route/confirm` 重新调用 draft LLM，却不持久化确认 sidecar，`confirmedSceneRouteHash` 固定为空。
- `/gdd/scene-route/latest`、`/gdd/document/generate`、`/gdd/document/status` 的 hash 字段仍是空字符串占位。
- `GameDesignRequirementMapService` 注入了 `ILlmRouteEngine` 但当前没有调用，Requirement Map 仅做简单行扫描。
- `PrototypeContractFreezeService.ReadSourceHashes` 将 style ID/version/hash 写成固定或 `unknown`，不足以满足 visible UI freshness。
- `RouteModuleContracts` 仍注册 `prototype-skeleton`，与计划要求的 canonical `prototype-skeleton-guard` 不一致。

### Existing Components To Extend

- `PhaseA.Platform/Runs/GameDesignSceneRouteService.cs`：保留 draft generation、fallback、normalization；不要复制 scene normalization。
- `PhaseA.Platform/Runs/GameDesignDocumentService.cs`：保留现有 executable Codex、runner lock、artifact 和 billing 流程；写回必须发生在成功产出 GDD 后。
- `PhaseA.Platform/Runs/GameDesignRequirementMapService.cs`：保留 source fail-closed 和 sidecar/readback模型；扩展 structured LLM 与分类，不建立第二套 requirement-map owner。
- `PhaseA.Platform/Runs/PrototypeContractFreezeService.cs`：保留 canonical path、mirror、new-chain guard 和 source validation；替换 placeholder source fields。
- `PhaseA.Platform/Workflow/RouteModuleContracts.cs`、`RouteActionDescriptors.cs`、`RouteFreshnessPolicy.cs`：作为 route/action/freshness 机器权威，不在 Program 或 Browser 复制枚举。
- `PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs`：复用统一 readback/blocker/evidence 投影。

### Architecture And Safety Guardrails

- 遵守 ADR-0032、ADR-0036、ADR-0038 与 `docs/standards/phase-service.md`。
- 结构化只读 LLM 必须走 `ILlmRouteEngine`；GDD 文件生成继续走 `CodexHostedProcessCommandFactory` 的现有路径，不增加 raw subprocess。
- 公开 API additive/backward-compatible；snake_case 只用于 sidecar，ASP.NET DTO 使用 camelCase。
- 不修改 live metadata DB、runtime/Caddy、auth/token 或共享 LLM 入口，除非新测试证明现有入口无法表达所需合同并另行更新 ADR。
- 所有 project path 使用既有 workspace/path guard；normal user 不得看到 host path、raw prompt、token、admin queue raw rows。
- sidecar 写入使用 project-root 约束、UTF-8、确定性 JSON；失败历史 append-only，不覆盖旧 evidence。
- 不以延长 timeout、禁用测试、空 hash、`unknown` 或 assistant 文本绕过 freshness。

### Testing Requirements

- 先扩展 `GddToModuleBackendContractServiceTests` 与 API/integration tests，固定真实 confirm/write-through/readback。
- 扩展 `RouteModuleContractsTests`、`ProjectRouteStateArtifactServiceTests`、workflow recommendation tests 和 skeleton guard tests。
- Requirement Map structured LLM 使用 fake `ILlmRouteEngine`，覆盖 valid/invalid/failure/duplicate/missing P0/P1。
- Prototype Contract 覆盖 visible UI style hash、non-UI reviewed exemption、canonical/mirror mismatch、stale source、retry/concurrency/account boundary。
- 保留 Phase 0 的 `1194/1194` 基线；Phase 1 最终全量不得有 P0/P1/必须修 P2 回归。

### Project Structure Notes

- Route-specific service/model/test 留在 `PhaseA.Platform/Runs/**` 与 `PhaseA.Platform.Tests/Runs/**`。
- 跨 route 的稳定机器合同留在 `PhaseA.Platform/Workflow/**` 与对应 Workflow tests。
- Program endpoint 只做 auth/account projection、service 调用与 HTTP result 映射，不承载 hash/persistence 业务逻辑。
- Browser 继续使用现有 renderer 和 workflow readback，不创建竞争性的 next-action engine。

### Previous Story Intelligence

- Phase 0 checkpoint `9c8ac4b` 已建立 registry fail-closed、闭集 coverage、bounded cancellation 和 append-only evidence 模式。
- 同 cache key 的并发/取消测试必须保持确定性；不要用未绑定 identity 的 dictionary cleanup。
- 机器 JSON/fixture/schema 修改必须同步所有镜像并加入 malformed/duplicate/orphan 负例。

### References

- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/08-implementation-phases.md#phase-1-requirement-map-and-contract-freshness`
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/10-recommended-first-slice.md#smallest-phase-1-slice`
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/02a-route-state-artifacts.md`
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/02b-backend-api-contracts.md`
- `execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/03-testing-observability-admin.md`
- `docs/standards/phase-service.md`
- `docs/standards/godot-engine-semantics.md`
- `docs/standards/godot-ui-capability-contract.md`
- `docs/standards/godot-ui-style-contract.md`
- `docs/standards/godot-diagnostics-quality-gates.md`

## Dev Agent Record

### Agent Model Used

Codex GPT-5.6

### Debug Log References

- Phase 0 exit evidence: `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-0-exit-review-20260711T071611Z.json`
- RED：场景确认/GDD 状态 API 返回空 hash，且确认没有持久化权威 sidecar。
- GREEN：新增 Phase 1 state service，完成 account-scoped confirm、GDD write-through、真实 readback 和失败阻断。
- RED：Requirement Map 未使用注入的 `ILlmRouteEngine`，invalid/duplicate/incomplete 输出没有结构化 fallback。
- GREEN：structured JSON route + deterministic floor/validation/needs-review fallback；UI ownership/camera evidence 可读回。
- RED：Contract style hash 为 `unknown`、mirror 按字节比较、并发 freeze 在全量负载下触发 Windows 文件占用。
- GREEN：真实 UI/style snapshot hash、contract-hash mirror、per-project single-flight、原子文件替换。
- RED：`Deckbuilder` 内部 `ui` 子串被误判为 UI requirement；P0/P1 blocker 未进入 diagnostic spool。
- GREEN：UI token boundary、admin review blocker、diagnostic spool 和 deckbuilder chain 全部覆盖。

### Implementation Plan

- 严格按 Task 1 → 5 执行，每项先建立 RED，再实现并通过目标回归。
- Task 1 先把场景确认/GDD write-through 从 `Program.cs` 的占位投影下沉到可单测的 route-state service。
- 复用现有 scene normalization、workspace path guard、route readback DTO 和 source hash 规则，不创建第二套 workflow authority。

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- 完成场景确认、GDD 文档、Requirement Map、Prototype Contract 与 skeleton guard 的 Phase 1 真实闭环。
- 全量 `PhaseA.Platform.Tests` 1209/1209，最终耗时 6m49s；hardening smoke 与 governance audit 均为 status=ok。
- Phase 1 evidence 包含 25 个 full-target capability row、18 个 split-added row、6 个 route dependency row；未消费能力明确标为 `not_consumed_by_first_slice`。
- 实现 self-review 的 unresolved P0/P1/P2 为 0，Story 转为 review，等待独立对抗审查。
- BMAD adversarial review completed: 11 patch findings handled, 0 deferred, 0 dismissed, and unresolved P0/P1/P2 = 0.
- Final post-review regression: 1219/1219 passed, 0 failed, 0 skipped; smoke and governance audit status=ok.

### File List

- `PhaseA.Platform/Program.cs`
- `PhaseA.Platform/Data/PhaseAMetadataStore.cs`
- `PhaseA.Platform/Runs/GddToModulePhase1StateService.cs`
- `PhaseA.Platform/Runs/GameDesignRequirementMapService.cs`
- `PhaseA.Platform/Runs/GameDesignSceneRouteModels.cs`
- `PhaseA.Platform/Runs/ProjectMutationLockRegistry.cs`
- `PhaseA.Platform/Runs/PrototypeContractFreezeService.cs`
- `PhaseA.Platform/Workflow/GddToModuleImplementationPhases.cs`
- `PhaseA.Platform/Workflow/RouteFreshnessPolicy.cs`
- `PhaseA.Platform/Workflow/RouteModuleContracts.cs`
- `PhaseA.Platform.Tests/Browser/BrowserUiRendererTests.cs`
- `PhaseA.Platform.Tests/Fixtures/route-module-contracts.v1.json`
- `PhaseA.Platform.Tests/Runs/GameDesignQuestionFormServiceTests.cs`
- `PhaseA.Platform.Tests/Runs/GddToModuleBackendContractServiceTests.cs`
- `PhaseA.Platform.Tests/Workflow/GddToModuleImplementationPhasesTests.cs`
- `PhaseA.Platform.Tests/Workflow/RouteModuleContractsTests.cs`
- `_bmad-output/implementation-artifacts/1-2-phase1-requirement-map-contract-freshness.md`
- `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-regression-summary-20260711T095025Z.json`
- `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-exit-review-20260711T095025Z.json`
- `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-exit-smoke-20260711T095025Z/summary.json`
- `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-exit-governance-20260711T095025Z/summary.json`
- `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-regression-summary-20260711T104735Z.json`
- `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-exit-review-20260711T104735Z.json`
- `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-exit-smoke-20260711T104735Z/summary.json`
- `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-exit-governance-20260711T104735Z/summary.json`

## Change Log

- 2026-07-11：完成 Phase 1 Requirement Map 与 Contract Freshness 实现、回归和退出证据，状态转为 review。
- 2026-07-11: Closed BMAD adversarial review, passed 1219-test regression and Phase 1 exit gates, and moved Story 1.2 to done.
