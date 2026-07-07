# Phase A Frontend GDD-To-Module Workflow Hardening Plan

Status: Draft plan
Date: 2026-07-07
Owner: Phase A platform
Scope: Frontend-visible GDD -> scene route -> requirement map -> prototype contract -> iteration plan -> execute-next-goal -> UI closure workflow hardening

## 1. Background

The current frontend workflow already has the core chain: GDD form, scene confirmation, GDD generation, prototype contract, iteration plan, execute-next-goal, needs-fix, repair, preview, and package. Recent work added game-type Default Prototype Contract support and a project-level `contractSnapshot` to reduce template drift.

However, the current chain still has three structural risks:

1. The transformation from GDD to executable modules does not yet have an explicit `GDD Requirement Map`, so it is difficult to prove that the real GDD requirements were fully carried into downstream modules.
2. `prototype-contract/latest.json` does not yet record strong provenance against the GDD, confirmed scene route, and project contract snapshot, so downstream steps can continue using stale contract or stale module plans after source changes.
3. The frontend still behaves like a collection of action buttons. It does not yet expose a strong recommendation, stop-loss, stage gate, and recovery model comparable to `workflow.md` Chapter 6.

This plan is not a minimum-change patch. It is a complete product/workflow refactor proposal. The intent is to adapt the governance model from `workflow.md` Chapters 3-7: structured inputs, coverage matrix, frozen contract, stage gates, recovery state, single-step execution, validation closure, and UI wiring closure.

## 2. Goals

1. Let users and admins clearly see which GDD requirements were identified and where each one maps: scenes, required modules, and executable goals.
2. Prevent downstream execution from silently using stale contracts or stale plans after GDD, scene route, or type contract changes.
3. Upgrade the frontend flow from button-driven to stage-driven with a clear recommended next action.
4. Add explicit gates before executable module generation: completed GDD, confirmed scene route, requirement coverage, and frozen contract.
5. Add UI wiring closure as a separate late-stage pass after core gameplay modules, so implemented features are visible and usable by players.
6. Preserve compatibility by adding sidecars, additive JSON fields, and readback surfaces instead of breaking current APIs or old projects.
7. Migrate TapTap's UI capability discipline into a Godot-only prototype UI capability contract so generated modules must account for UI surfaces, layout, drawing, input, camera/layer boundaries, animation, rendering, procedural generation, geometry sizing, and typed state evidence.
8. Migrate TapTap's quality-gate and troubleshooting discipline into Godot/Phase route diagnostics: pre-build diagnostics, symptom-to-remediation tables, debug-log lifecycle, interaction design artifacts, preview validation, explicit resource lifecycle checks, and project diagnostic spool/admin triage.

## 3. Non-Goals

1. Do not copy Taskmaster triplets, overlays, or the formal Chapter 6 pipeline directly into frontend projects.
2. Do not force old projects through a destructive migration. Old projects should be lazily backfilled or shown as missing the new artifacts.
3. Do not allow downstream workflows to freely reread `docs/game-type-guides` as a new gameplay authority after GDD generation.
4. Do not silently refresh confirmed contracts. When GDD or scene route changes, prompt for explicit user confirmation.
5. Do not refactor the Godot generator itself in this plan. This plan focuses on inputs, contracts, module planning, workflow state, and frontend governance.
6. Do not copy TapTap's TypeScript/MCP feature layout directly. Borrow its boundary, guard, CLI, logging, and documentation patterns only where they fit the Phase A C# service and browser workflow.
7. Do not import TapTap's UrhoX, Urho3D, Lua, NanoVG, PBRNoTexture, `.emmylua`, or Maker runtime assumptions. All migrated UI capability requirements must be expressed with Godot 4.5/.NET-compatible concepts and repository-owned validation.
8. Do not copy TapTap's local-only LSP, preview, logging, or disposal mechanics literally. Quality gates in this plan must use Godot 4.5, C#/.NET, GdUnit4, Phase route evidence, sanitized readback, and hosted workspace/account boundaries.

## 4. Target Frontend Workflow

The target frontend stages are:

1. `project-created`
   - Project creation is complete. Steam/game-type matching either succeeded or produced a maintenance record.
2. `gdd-question-form`
   - The user fills out the GDD question form.
3. `scene-route-confirmation`
   - The system drafts a scene route form. The user confirms scene count, scene relationships, entry paths, and exits.
4. `gdd-document-generation`
   - The system generates the full GDD from the GDD form, confirmed scene route, and project contract snapshot.
5. `gdd-requirement-map`
   - The system extracts and maps requirements from the GDD and scene route. The map is visible to users/admins.
6. `prototype-contract-freeze`
   - The system freezes the prototype contract and records artifact-local source hashes (`source_gdd_hash`, `source_scene_route_hash`, `source_requirement_map_hash`, `source_contract_snapshot_hash`, `source_godot_ui_contract_hash`) with camelCase API/readback projections.
7. `prototype-skeleton`
   - If the project has no prototype state yet, create the first playable M1 skeleton from the frozen GDD contract.
8. `iteration-plan`
   - Generate executable game modules from the frozen contract, requirement map, and prototype state.
9. `module-execution`
   - Execute one goal at a time, using only the current contract, current route state, and current goal.
10. `needs-fix-or-repair`
   - Failed acceptance enters needs-fix/repair. Repairs must bind to the current step and latest validation blocker.
11. `ui-wiring-closure`
   - After core P0/P1 modules pass, generate/check the UI flow matrix so player-facing entry, feedback, state boundaries, and validation are covered.
12. `preview-package`
   - Preview, package, and download.

## 4.1 Naming Conventions

Artifact-local route-state JSON should follow the naming style already used by that artifact family. New project sidecars under `meta/routes/**` should use Phase sidecar snake_case fields such as `schema_version`, `status_reason`, `evidence_refs`, and `updated_utc`. Browser API/readback responses should expose camelCase DTO fields regardless of artifact-local storage style. Existing prototype contract JSON may keep its current snake_case style (`source_gdd_hash`, `freshness`) to avoid churn in downstream prompt builders and route-state consumers.

Acceptance criteria:

- New sidecar schemas use snake_case unless they are extending an existing artifact family that already has a different durable convention.
- API DTO/readback fields remain camelCase and act as the compatibility adapter over artifact-local JSON.
- Existing artifact-local snake_case fields are not renamed unless a compatibility adapter is provided.

## 4.2 Acceptance Severity Standard

All acceptance criteria in this plan use the following severity gate. A phase, implementation slice, or route change is not accepted if the review leaves any unresolved P0, P1, or P2 issue.

Severity definitions:

- P0: data loss, account isolation failure, auth bypass, secret or host-path leakage, destructive live DB mutation, source-boundary bypass after contract freeze, executing against stale P0 contract state, or a user-visible workflow path that cannot recover.
- P1: P0/P1 GDD requirement lost or silently deferred, route/action/status drift that makes the frontend invoke the wrong operation, missing stale detection, missing audit trail for admin-only decisions, duplicate active run creation, or deterministic tests/smoke missing for a changed gate.
- P2: ambiguity, degraded operator visibility, brittle guard coverage, missing non-critical evidence metadata, unclear migration behavior, or UX that makes the recommended next action hard to understand while still allowing recovery.

Acceptance criteria:

- Every implementation phase exit includes a documented P0/P1/P2 review result with zero unresolved P0, P1, or P2 findings.
- If a P2 issue is intentionally deferred, it must be reclassified as an explicit later-phase open question with owner, scope, and proof that it does not affect current user execution or account/security boundaries.
- A change cannot pass only because manual review found no problem; deterministic tests, smoke evidence, or a documented non-applicability rationale must cover each touched P0/P1 gate.
- Acceptance evidence must identify the exact route, artifact, API, browser surface, or script covered by the check.

## 5. Proposed Artifacts

### 5.1 `meta/routes/gdd-requirements/latest.json`

Add a project-level sidecar. This is the frontend equivalent of the Chapter 3 coverage matrix.

Recommended schema:

```json
{
  "schema_version": "gdd-requirements.v1",
  "route": "gdd-requirements",
  "project_id": "...",
  "source_gdd_path": "docs/gdd/GDD.md",
  "source_gdd_hash": "sha256",
  "source_scene_route_hash": "sha256",
  "source_contract_snapshot_hash": "sha256",
  "godot_ui_contract_version": "godot-ui-capability.v1",
  "source_godot_ui_contract_hash": "sha256",
  "status": "ready|needs_review|blocked|stale",
  "readiness_scope": "requirement_map",
  "status_reason": "",
  "updated_utc": "...",
  "evidence_refs": [],
  "coverage_summary": {
    "requirement_count": 0,
    "covered_count": 0,
    "missing_scene_count": 0,
    "missing_module_count": 0,
    "explicitly_deferred_count": 0,
    "conflict_count": 0
  },
  "requirements": [
    {
      "requirement_id": "REQ-001",
      "source_section": "Core Loop",
      "source_quote": "short excerpt",
      "normalized_requirement": "Player chooses a route node before each battle.",
      "priority": "P0|P1|P2",
      "kind": "scene|mechanic|ui|state|asset|validation|meta",
      "mapped_scene_ids": ["route_map"],
      "mapped_required_module_ids": ["route_map_path_selection"],
      "mapped_iteration_goal_ids": [],
      "status": "mapped|missing_scene|missing_module|needs_review|explicitly_deferred|conflict",
      "defer_reason": "",
      "conflict_reason": "",
      "decision_by": "",
      "decision_role": "admin|system",
      "decision_utc": "",
      "decision_reason": "",
      "affected_requirement_ids": [],
      "acceptance_markers": ["Route node selection changes current path."]
    }
  ]
}
```

Acceptance criteria:

- A GDD with concrete scene and mechanic requirements produces at least one requirement row per concrete gameplay, scene, or UI requirement.
- Every `Always` scene from the confirmed scene route appears in at least one mapped requirement or has an explicit no-requirement rationale.
- Every `Always` required module from the project contract snapshot appears in at least one mapped requirement unless explicitly contradicted by the GDD.
- Every new requirement map created after Phase 0 records the Godot UI capability contract version/hash. Legacy maps without these fields are treated as `unknown` and require refresh before new contract freeze or new iteration plan creation.
- If the Godot UI capability contract hash changes, the previous requirement map is stale for new contract freeze or new iteration plan creation.
- If any P0 requirement is `missing_scene`, `missing_module`, `needs_review`, or `conflict`, the workflow blocks `prototype-contract-freeze` by default.
- The artifact is readable from the project route-state location and mirrored to the repo `meta/routes/gdd-requirements/latest.json` if current route-state conventions require mirroring.
- Tests cover normal mapping, missing scene, missing module, explicit defer, system conflict fallback, admin-approved conflict suppression, stale hash, and invalid JSON fallback.
- Artifact-local `explicitly_deferred` and `conflict` decisions require structured audit fields: `decision_by`, `decision_role`, `decision_utc`, `decision_reason`, and `affected_requirement_ids`; browser/API readback exposes the same data as camelCase.
- P0/P1 `explicitly_deferred` decisions are admin-only by default unless a later product decision grants normal users that authority with an explicit confirmation flow.
- `decision_*` fields are required only for `explicitly_deferred` and `conflict`; for all other requirement statuses they must be empty or omitted.
- `decision_role=system` may mark deterministic conflict or needs-review decisions, but it cannot explicitly defer P0/P1 requirements.
- When the GDD explicitly conflicts with a default required module, the requirement map first records `conflict`; suppressing that default module is allowed only after an admin records the required `decision_*` fields. A system-detected conflict does not automatically unblock contract freeze.
- System-detected conflicts must be surfaced in admin review/readback queues with blocking context instead of remaining only as hidden requirement-map rows.
- Admin review/readback queue entries include at least `account_id`, `project_id`, `requirement_id`, `blocking_reason`, `source_section`, `created_utc`, and `status`.
- User-facing readback must not expose cross-account admin review queue entries.
- A deferred or conflicted requirement is still visible in readback and cannot be deleted from the map; downstream plans must carry the defer/conflict reason when it affects generated modules.

### 5.2 `meta/routes/prototype-contract/latest.json` Extensions

Extend the current prototype contract with provenance and freshness metadata.

Add fields:

```json
{
  "contract_hash": "sha256",
  "source_gdd_hash": "sha256",
  "source_scene_route_hash": "sha256",
  "source_requirement_map_hash": "sha256",
  "source_contract_snapshot_hash": "sha256",
  "godot_ui_contract_version": "godot-ui-capability.v1",
  "source_godot_ui_contract_hash": "sha256",
  "freshness": {
    "status": "fresh|stale|unknown",
    "stale_reasons": []
  },
  "requirement_traceability": []
}
```

Acceptance criteria:

- `contract_hash` is computed from the canonical frozen contract payload, excluding volatile fields such as `updated_utc`/`updatedUtc`, `freshness`, and `contract_hash` itself.
- New contracts always include all source hash fields when source artifacts exist.
- If `docs/gdd/GDD.md`, scene route, requirement map, contract snapshot, or Godot UI capability contract hash changes, readback reports the contract as `stale`.
- Browser/API readback projects artifact-local `godot_ui_contract_version` and `source_godot_ui_contract_hash` as `godotUiContractVersion` and `sourceGodotUiContractHash`.
- Existing contracts without these fields load as `unknown`, not failed.
- New iteration plan creation blocks or returns `contract_stale` when the contract is stale. The user can refresh/freeze the contract and then create a new plan, but cannot bypass stale state with a plain continue confirmation.
- Execute-next-goal refuses to start against a stale contract unless the existing goal was created against the same stale contract hash and the user explicitly continues repair. Default behavior is to block.

### 5.3 `meta/routes/workflow-recommendation/latest.json`

Frontend equivalent of Chapter 6 `chapter6-route --recommendation-only`.

Recommended schema:

```json
{
  "schema_version": "project-workflow-recommendation.v1",
  "project_id": "...",
  "recommended_action": "create_gdd|complete_gdd|confirm_scene_route|generate_requirement_map|freeze_contract|refresh_contract|create_prototype|create_iteration_plan|execute_next_goal|run_needs_fix|run_ui_closure|preview_package|inspect_first",
  "reason": "...",
  "status": "ready|blocked|stale|needs_review",
  "readiness_scope": "workflow_recommendation",
  "status_reason": "",
  "blocking_issues": [],
  "allowed_actions": [],
  "forbidden_actions": [],
  "stale_artifacts": [],
  "updated_utc": "...",
  "evidence_refs": []
}
```

Acceptance criteria:

- The frontend primary action is driven by this recommendation instead of hardcoded button order.
- This recommendation is implemented as a structured read model from the existing `ProjectWorkflowRouteService` authority, or the existing service is extended to emit it; the platform must not keep two independent next-action engines.
- If GDD is incomplete, recommendation is `create_gdd` or `complete_gdd`, and module generation actions are disabled.
- If scene route is missing, recommendation is `confirm_scene_route`.
- If the requirement map has P0/P1 gaps, recommendation is `inspect_first` or `generate_requirement_map`, not `create_iteration_plan`.
- If the contract is stale, recommendation is `freeze_contract` or `refresh_contract`.
- If prototype state is missing, recommendation is `create_prototype`.
- If an iteration plan exists and has a pending goal, recommendation is `execute_next_goal`.
- If latest validation has a P0/P1 blocker, recommendation is `run_needs_fix`.
- Tests cover each recommendation transition.

### 5.4 `meta/routes/ui-wiring/latest.json`

Frontend equivalent of Chapter 7 UI wiring closure.

Recommended schema:

```json
{
  "schema_version": "ui-wiring-closure.v1",
  "project_id": "...",
  "source_iteration_session_id": "...",
  "source_iteration_session_hash": "sha256",
  "source_validation_input_hash": "sha256",
  "source_contract_hash": "sha256",
  "source_requirement_map_hash": "sha256",
  "source_godot_ui_contract_hash": "sha256",
  "status": "ready|needs_fix|succeeded|blocked|stale",
  "readiness_scope": "ui_wiring_closure",
  "status_reason": "",
  "updated_utc": "...",
  "evidence_refs": [],
  "godot_ui_contract_version": "godot-ui-capability.v1",
  "player_flows": [],
  "ui_surface_matrix": [
    {
      "feature": "route_map_path_selection",
      "source_requirement_ids": ["REQ-001"],
      "source_goal_ids": [],
      "ui_surface": "RouteMapView",
      "godot_scene_path": "res://...",
      "godot_node_path": "Main/CanvasLayer/RouteMapView",
      "godot_surface_type": "control|hud_canvas_layer|custom_canvas_item|world_space_2d|world_space_3d|subviewport|no_ui_needed",
      "layout_strategy": "container_theme|anchors_safe_area|fixed_board_with_responsive_bounds|world_overlay|explicit_no_ui",
      "input_paths": ["mouse_left", "touch_press"],
      "focus_navigation": {
        "keyboard": "covered|not_applicable|missing",
        "gamepad": "covered|not_applicable|missing",
        "mouse_touch": "covered|not_applicable|missing"
      },
      "feedback_states": ["idle", "hover", "pressed", "selected", "disabled"],
      "camera_layer_boundary": "ui_canvas_layer_separate_from_world_camera",
      "asset_size_source": "theme_metric|control_min_size|texture_import_metadata|aabb|get_aabb|collision_shape|not_applicable",
      "custom_drawing_surface": "none|Control._draw|CanvasItem._draw|Line2D|Polygon2D|ArrayMesh|ImmediateMesh|SubViewport",
      "animation_state_ref": "AnimationPlayer:RouteMapSelection",
      "material_rendering_policy": "theme_stylebox|canvas_item_material|standard_material_3d|shader_material_repo_approved|not_applicable",
      "typed_state_ref": "RouteMapSelectionState",
      "player_action": "Select reachable next node",
      "system_response": "Highlight path and advance to battle",
      "state_boundary": "Run route state changes only after confirmed selection",
      "validation_refs": [],
      "status": "covered|missing_ui|missing_feedback|needs_fix|no_ui_needed"
    }
  ],
  "summary": {}
}
```

Acceptance criteria:

- UI closure cannot start until the core module plan has no unresolved P0/P1 goals, unless the user explicitly runs preview mode.
- Preview mode produces advisory UI closure output only; it cannot mark final readiness as passed and cannot generate final-package readiness approval.
- Every completed P0/P1 gameplay requirement has a UI surface or explicit `no_ui_needed` rationale.
- Missing player action, system response, or state boundary marks the item `needs_fix`.
- UI closure can produce follow-up iteration goals for missing UI wiring.
- Frontend displays UI closure status separately from gameplay module status.
- UI closure records the iteration session hash, validation input hash, frozen contract hash, requirement map hash, and Godot UI capability contract hash that produced the closure result.
- UI closure validation inputs include latest validation blockers, Godot diagnostics, screenshot/canvas/exported visual evidence references, UI closure mode, manual needs-fix inputs used for closure, and any repair evidence selected as current acceptance authority.
- UI closure returns `stale` or `blocked` instead of final readiness when current iteration session, validation inputs, contract, requirement map, or Godot UI capability contract hash differs from the recorded source hash set.
- Tests cover UI closure `stale` status when the recorded iteration session, validation input, contract, requirement map, or Godot UI capability contract hash does not match current sources.
- Every non-`no_ui_needed` P0/P1 UI surface records a Godot scene path or node path, surface type, layout strategy, input path, feedback state list, and validation reference.
- UI closure blocks final readiness when a required UI surface uses absolute-position-only layout without an explicit fixed-format rationale, when keyboard/gamepad/mouse-touch focus status is missing for an interactive surface, or when camera/layer boundaries are not stated.
- Custom drawing requirements must name the Godot drawing surface (`Control._draw`, `CanvasItem._draw`, `Line2D`, `Polygon2D`, `ArrayMesh`, `ImmediateMesh`, or `SubViewport`) and include redraw/input/state validation evidence.
- 2D/3D asset and geometry sizing cannot be guessed. The closure record must cite a measurable source such as theme metrics, `Control.custom_minimum_size`, texture import metadata, `AABB`, `get_aabb()`, collision shapes, or an explicit not-applicable rationale.
- UI closure acceptance uses the P0/P1/P2 severity standard; a phase cannot pass with unresolved Godot UI contract gaps.

## 6. Backend Changes

### 6.1 New Service: `GameDesignRequirementMapService`

Responsibilities:

- Read `docs/gdd/GDD.md`.
- Read confirmed scene route state.
- Read project `contractSnapshot` and game-type default required modules.
- Read the Godot UI capability contract described in this plan and classify UI-facing requirements with expected surfaces, inputs, feedback states, and validation markers.
- Generate `gdd-requirements/latest.json` through structured LLM output or deterministic fallback.
- Validate coverage and status.
- Persist route state and mirror it if needed.

Acceptance criteria:

- Service returns stable JSON with deterministic IDs (`REQ-001`, `REQ-002`, ...).
- Service fails closed when GDD is missing, scene route is missing, or returned requirement map JSON is invalid.
- Service produces fallback `needs_review` rows instead of silently returning an empty requirement set.
- Service marks requirements as `kind=ui` or adds UI acceptance markers when the GDD implies player-facing interaction, feedback, HUD, menu, camera overlay, custom drawing, animation state, or visualized procedural content.
- Unit tests cover successful map generation, invalid LLM JSON fallback, missing sources, and default module preservation.

### 6.2 New/Extended Service: `PrototypeContractFreezeService`

Responsibilities:

- Freeze or refresh `prototype-contract/latest.json` from GDD, scene route, requirement map, contract snapshot, and current request fields.
- Add source hashes and traceability.
- Freeze the current Godot UI capability contract version/hash as part of the prototype contract source set.
- Detect stale contract state.

Acceptance criteria:

- Freeze writes a contract with all source hashes.
- Re-freezing unchanged sources is idempotent except `updated_utc`/`updatedUtc` if policy requires updating it.
- Changed GDD or scene route marks the previous contract stale.
- Changed Godot UI capability contract version/hash marks contracts as `stale` for new iteration plans unless the change is explicitly declared backward-compatible by a later decision log.
- Freezing does not run Steam lookup or rematch game type.
- Existing `PrototypeContractService` remains backward compatible.

### 6.3 Extend `PrototypeIterationPlanService`

Responsibilities:

- Read requirement map as first-class input.
- Generate goals from requirement rows and required modules.
- Include `requirementIds` in every goal and every `required_modules` entry.
- Generate explicit UI surface goals for P0/P1 requirements that need Godot `Control`, `CanvasLayer`, custom drawing, input/focus, camera/layer separation, animation, rendering, geometry sizing, or procedural visualization work.
- Block if P0/P1 requirements are unmapped or contract is stale.

Acceptance criteria:

- Every generated goal includes at least one `requirementId` or an explicit infrastructure reason.
- Every P0 requirement is covered by a goal, required module, prototype skeleton, or explicit blocker.
- `required_modules` retains deckbuilder route-map and hand-dragging defaults and adds requirement links.
- If `route_map_path_selection` is required, it appears in `required_modules` as a separate block, not only as a vague goal title.
- If a required module has player-facing interaction, the iteration plan includes either a linked UI surface goal or an explicit `no_ui_needed` rationale that survives into UI closure.
- Generated UI goals name the expected Godot scene/node ownership, layout strategy, input/focus coverage, feedback states, and validation method rather than only saying "add UI".
- Tests cover deckbuilder, RPG, generic fallback, stale contract, missing map, and admin-approved GDD conflict suppression.
- The iteration plan route state must record `sourceGddHash`, `sourceSceneRouteHash`, `sourceRequirementMapHash`, `sourceContractHash`, `sourceContractSnapshotHash`, and `sourceGodotUiContractHash`.
- Every generated goal must record the same source hash set or a `sourceHashRef` that points to the session-level hash set.
- Stale checks must compare execute-next-goal source hashes against the current frozen contract and requirement map before invoking Codex.
- Stale checks must compare `sourceGodotUiContractHash` against the current frozen Godot UI capability contract hash before invoking Codex for any UI-touching goal.

### 6.4 Extend `PrototypeIterationGoalService`

Responsibilities:

- Include requirement rows linked to the current goal in the prompt.
- Include contract freshness metadata.
- Include the frozen Godot UI capability contract when the current goal touches player-facing UI, input, drawing, camera/layer boundaries, animation, rendering, geometry, procedural visualization, or typed state.
- Refuse executing goals whose source contract/hash does not match the current frozen contract, unless the repair route explicitly allows continuation.

Acceptance criteria:

- Goal input markdown contains `Requirement IDs` and source excerpts.
- Prompt states that the current goal must not expand beyond linked requirements.
- Prompt states that Godot UI work must use Godot 4.5 concepts only (`Control`, `Container`, `Theme`, `CanvasLayer`, `CanvasItem`/`Control._draw`, `Line2D`, `Polygon2D`, `ArrayMesh`, `ImmediateMesh`, `SubViewport`, `AnimationPlayer`, `AnimationTree`, camera nodes, materials/shaders, typed C#/GDScript state), not TapTap runtime concepts.
- Prompt requires measurable layout/size/input validation evidence for UI goals before they can be marked complete.
- Execution returns `contract_stale` or `requirement_map_missing` before Codex invocation when source state is invalid.
- Tests assert Codex is not called in stale/missing cases.
- Execute-next-goal can only allow an old goal to continue when the goal/session recorded source hashes match the contract and requirement map that were current when that goal was created.
- If source hashes are missing, execute-next-goal treats the goal as `source_unknown` and blocks by default for new projects.
- `sourceContractHash` in API/readback and route prompts is the camelCase projection of `contract_hash` from the frozen prototype contract.

### 6.5 Extend `ProjectWorkflowRouteService`

Responsibilities:

- Build frontend recommendation from route states, run states, stale artifacts, and validation blockers.
- Replace button-only guidance with structured recommendation.

Acceptance criteria:

- API readback includes `recommendedAction`, `blockingIssues`, `allowedActions`, and `forbiddenActions`.
- Existing UI remains usable if recommendation data is missing.
- Recommendation is deterministic for known route state combinations.

## 7. API Changes

Add or extend routes:

1. `POST /api/projects/{projectId}/gdd/requirements-map`
   - Generate or refresh requirement map.
   - Idempotency: if the current source hashes match the latest map, return the existing route state; if sources changed and no active generation exists, create a new generation run; if generation is already active, return the active run/state instead of starting a duplicate.
2. `GET /api/projects/{projectId}/gdd/requirements-map/latest`
   - Read latest requirement map.
3. `POST /api/projects/{projectId}/prototype-contract/freeze`
   - Freeze or refresh prototype contract after requirement map.
   - Idempotency: if source hashes match the frozen contract, return the existing contract status; if sources changed, require explicit refresh intent and write a new frozen contract version; reject unsafe duplicate refresh with `409`.
4. `GET /api/projects/{projectId}/prototype-contract/status`
   - Return fresh/stale/unknown status and hash reasons.
5. `GET /api/projects/{projectId}/workflow-recommendation`
   - Return current recommended next action from the existing workflow route authority/read model.
6. `POST /api/projects/{projectId}/ui-wiring-closure`
   - Generate UI wiring closure state.
   - Idempotency: return an existing closure state only when `source_iteration_session_hash`, `source_validation_input_hash`, `source_contract_hash`, `source_requirement_map_hash`, and `source_godot_ui_contract_hash` all match the latest closure state; if closure is already running for the same hash set, return the active run/state; otherwise create one closure run.
7. `GET /api/projects/{projectId}/ui-wiring-closure/latest`
   - Read latest UI closure state.

Acceptance criteria:

- All project-scoped routes enforce account ownership.
- Admin-only data remains behind `/api/admin/...`.
- Responses are additive only; no existing route response field is removed or renamed.
- POST API responses include an explicit `operationStatus` (`returned_existing|active_run_reused|created_run|rejected`) plus either a stable route state, an active `runId`, or an `evidenceRefs` pointer that can be read by a GET route; artifact-local sidecars keep the snake_case `evidence_refs` field.
- `operationStatus=active_run_reused` responses include `runId`, polling/readback URL or route-state location, operation scope, source hash scope, and server-derived opaque/redacted account-project scope marker so the browser can resume the correct run and tests can prove a stale or cross-account run was not reused. Normal-user responses must not expose internal account IDs, host paths, or metadata DB identifiers.
- If operation status is ever persisted in an artifact-local sidecar, it must use `operation_status`; `operationStatus` is reserved for API/readback DTOs.
- `operationStatus=rejected` responses must include the standard error envelope with `requestId` and optional `details.domainCode`.
- `evidenceRefs.kind` / `evidence_refs.kind` uses the Phase standard closed enum: `log|artifact|sidecar|screenshot|db_row|smoke|validator`, unless the standards document is updated first.
- POST responses and generated evidence preserve `requestId`/`correlationId` when the request starts or resumes a run.
- Error envelope `code` values follow Phase standard preferred codes; route-specific business reasons are carried in `details.domainCode`.
- Error status mapping is stable:

  | HTTP status | Envelope `code` | `details.domainCode` examples |
  | --- | --- | --- |
  | `404` | `gdd_not_found`, `scene_route_missing`, `contract_missing`, `requirement_map_missing` only when the caller is allowed to know absence |
  | `409` | `conflict` | `contract_stale`, `ui_contract_unknown`, `iteration_plan_blocked`, `duplicate_active_run` |
  | `422` | `route_state_invalid` | `requirement_map_invalid`, `ui_closure_not_ready`, `ui_contract_unknown` when detected only while validating legacy route state |
  | `429` | `rate_limited` | `route_concurrency_limit`, `account_concurrency_limit` |

- Cross-account or existence-hiding cases must return generic `project_not_found` or `forbidden` and must not expose fine-grained domain codes such as `gdd_not_found` or `requirement_map_missing`.
- Action routes document whether repeat calls are safe repeat, return existing active work, create a new run, or reject duplicates with `409`.
- Browser callers handle 404/409/422 without showing generic 500 failures.

## 8. Frontend Changes

### 8.1 Stage Timeline

Add a visible stage timeline:

1. GDD
2. Scene Confirmation
3. Requirement Map
4. Contract Freeze
5. Game Modules
6. Task Execution
7. UI Closure
8. Preview/Package

Acceptance criteria:

- Each stage shows `not_started|ready|running|needs_review|blocked|completed|stale`.
- The current recommended action is visually primary.
- Blocked stages show a concrete reason and source artifact.
- Existing legacy action buttons remain available under advanced/secondary actions during rollout.

### 8.2 Requirement Map Review UI

Add a review table for GDD requirements.

Columns:

- Requirement ID
- Source section
- Requirement
- Priority
- Kind
- Scenes
- Required modules
- Goals
- Status
- Issue / conflict reason

Acceptance criteria:

- User can inspect all P0/P1 gaps before generating modules.
- Rows with missing scene/module are visually distinct.
- User can trigger requirement map regeneration.
- User can proceed only when blocking gaps are resolved, or an admin has explicitly deferred them with the required audit fields.

### 8.3 Contract Freshness Banner

Add a banner when contract or iteration plan is stale.

Acceptance criteria:

- If GDD hash changed after contract freeze, banner says GDD changed and offers contract refresh.
- If scene route changed, banner says scene route changed and offers contract refresh plus module regeneration.
- If contract snapshot changed, banner says type default contract changed and offers manual refresh, not automatic overwrite.
- Execute-next-goal button is disabled by default when stale.

### 8.4 Module Plan Confirmation UI

Before execution, show module plan with requirement traceability.

Acceptance criteria:

- Every goal row shows linked requirement IDs.
- Required modules appear in a separate block, not only mixed into goals.
- User can see why each module exists: GDD requirement, default type contract, route strategy, or repair follow-up.
- Starting execution without confirming the module plan is blocked for new projects.

### 8.5 UI Wiring Closure UI

Add a late-stage UI closure panel.

Acceptance criteria:

- Shows completed gameplay capabilities and corresponding UI surfaces.
- Flags completed functionality without player-facing entry or feedback.
- Can generate follow-up goals for missing UI wiring.
- Does not block early prototype creation; blocks final package readiness only when P0/P1 UI gaps exist.
- Shows Godot UI gap families separately: layout, input/focus, feedback, custom drawing, camera/layer, rendering/material, animation, geometry sizing, procedural visualization, and typed state.
- Shows Godot UI contract version/hash and source hashes in an account-safe readback format.

## 9. Migration And Compatibility

1. Existing projects without requirement map:
   - Show `requirement_map_missing`, but allow lazy generation.
2. Existing prototype contracts without source hashes:
    - Treat freshness as `unknown`.
    - Prompt user to freeze/refresh contract before creating new module plans.
    - Treat missing Godot UI capability contract fields as `freshness.status=unknown` with `ui_contract_unknown` recorded as a `freshness.stale_reasons[]` value, API `details.domainCode`, and workflow `blockingIssues[]` entry where applicable. `ui_contract_unknown` is not a freshness status enum value.
    - Preview/package can continue for existing successful prototypes, but new iteration plans require refresh/freeze.
3. Existing iteration plans:
    - Continue readback.
    - Existing successful prototypes can still preview/package.
    - New execution cannot continue from a legacy plan that lacks the required source hashes. The user must refresh/freeze the requirement map and contract, then create or confirm a hash-bound plan.
    - Old hash-bound execution can continue only when the session/goal hashes match the frozen contract and requirement map that were current when the goal was created.
4. Deleted projects in admin match records:
   - Continue showing empty contract snapshot summary.
5. No live DB destructive mutation:
   - Prefer sidecar files and additive JSON fields.

Acceptance criteria:

- Old project list renders without exceptions.
- Existing successful prototypes can still preview/package.
- Creating a new iteration plan on an old project prompts requirement map/contract freeze first.
- Existing projects without Godot UI capability contract fields cannot start new UI-touching goals until the current contract is refreshed and the UI capability hash is recorded.
- No manual DB migration is required unless a later implementation chooses a persistent index table. If added, migration must be backward-compatible.

## 10. Testing Strategy

### 10.1 Unit Tests

Required test areas:

- `GameDesignRequirementMapServiceTests`
- `PrototypeContractFreezeServiceTests`
- `PrototypeIterationPlanServiceTests`
- `PrototypeIterationGoalServiceTests`
- `ProjectWorkflowRouteServiceTests`
- `BrowserUiRendererTests`
- `ArtifactReadbackServiceTests`

Acceptance criteria:

- Tests cover the deckbuilder reference path: class selection, route map, card battle, reward choice; required modules route selection and hand dragging.
- Tests cover stale GDD hash blocking iteration plan.
- Tests cover stale scene route hash blocking execution.
- Tests cover requirement map P0 missing module blocking contract freeze or module generation.
- Tests cover admin-approved GDD conflict suppression of a default module with recorded `decision_*` fields.
- Tests cover system-detected conflict appearing in admin review/readback queue and blocking contract freeze until admin approval.
- Tests cover `operationStatus=rejected` returning the standard error envelope with `requestId` and `details.domainCode`.
- Tests cover UI closure missing surface producing needs-fix status.
- Tests cover UI closure source hash matching for `source_iteration_session_hash`, `source_validation_input_hash`, `source_contract_hash`, `source_requirement_map_hash`, and `source_godot_ui_contract_hash`, including stale behavior when any hash differs.
- Tests cover `ui_contract_unknown` as `freshness.stale_reasons[]`, API `details.domainCode`, and workflow `blockingIssues[]`, not as a freshness status enum value.
- Tests cover route module contract guards, path/readback policy guards, source-boundary guard tests, and operation-status/error-envelope guard tests introduced by the TapTap-derived hardening patterns.

### 10.2 Integration / Smoke Tests

Add a deterministic smoke path for:

1. Verify Phase 0 baseline evidence and guard artifacts exist.
2. Create project.
3. Generate GDD question form.
4. Confirm scene route.
5. Generate GDD.
6. Generate requirement map.
7. Freeze contract.
8. Generate iteration plan.
9. Execute or dry-run next-goal decision.

Acceptance criteria:

- Smoke writes evidence under `logs/`.
- Smoke fails before project creation if Phase 0 baseline evidence, route contract template, path/readback policy, action exposure classes, duplicate-run convention, preflight checklist, or secret redaction fixture baseline is missing.
- Smoke asserts route state files exist and contain matching hashes.
- Smoke asserts no downstream route reads broad game-type guide as authority after contract freeze.
- Smoke/test assertions define this concretely: execute-next-goal, needs-fix, repair, and UI closure prompts may include `source_boundary` and artifact paths, but must not include raw `docs/game-type-guides` guide excerpts or use guide-derived requirements that are absent from the frozen contract/requirement map.
- Smoke/test assertions read the saved prompt or run evidence artifact, not only the route-state summary field, when checking source-boundary behavior.
- Route state must record `source_boundary_enforced: true` when the prompt was built from frozen project artifacts only. Missing or false `source_boundary_enforced` makes the smoke fail and marks the route state invalid for completion.

### 10.3 Browser Tests

Acceptance criteria:

- Embedded scripts remain syntactically valid.
- Stage timeline renders missing, stale, completed, and blocked states.
- Requirement map table renders empty, loaded, gap, and stale states.
- Contract freshness banner displays the correct action.
- Primary button follows `workflow-recommendation`.

### 10.4 Godot UI Capability Tests

Required test areas:

- Godot UI contract source hash and freeze/readback tests.
- Requirement-map classification tests for UI/HUD/menu/input/custom drawing/camera/animation/rendering/procedural visualization requirements.
- Iteration-plan tests proving P0/P1 UI requirements become explicit UI goals or blocking gaps.
- Execute-next-goal prompt tests proving Godot UI capability contract injection for UI goals and no TapTap runtime term leakage.
- UI closure validator tests for Godot scene/node path, layout strategy, input/focus, feedback states, camera/layer boundary, custom drawing, geometry sizing, animation, material/rendering policy, and typed state references.
- Godot headless, screenshot, canvas-pixel, or exported-evidence tests for representative UI surfaces. Validator-only evidence is allowed only for non-visual source-boundary checks or when phase review records a concrete harness limitation and a substitute deterministic check.

Acceptance criteria:

- Tests fail if a P0/P1 UI requirement reaches `succeeded` without a UI surface matrix row or explicit `no_ui_needed` rationale.
- Tests fail if UI-goal prompts mention TapTap-only runtime concepts such as UrhoX, Urho3D, Lua, NanoVG, PBRNoTexture, or `.emmylua` outside a conflict-assessment document.
- Tests fail if a required interactive surface lacks mouse/touch input coverage and keyboard/gamepad focus status.
- Tests fail if a required custom drawing surface lacks a redraw/state validation reference.
- Tests fail if a 2D/3D size-sensitive UI or world-space surface uses guessed dimensions without theme metrics, import metadata, `AABB`, `get_aabb()`, collision shape, or a not-applicable rationale.
- Tests fail if camera/HUD surfaces do not declare whether they are separated by `CanvasLayer`, viewport, or camera ownership.
- Tests fail if a high-risk visual UI change has neither screenshot/canvas-pixel/exported visual evidence nor an approved deterministic substitute tied to a recorded harness limitation.
- Godot UI capability test results are included in phase review evidence and must have zero unresolved P0/P1/P2 findings.

### 10.5 Godot Diagnostics And Quality Gate Tests

Required test areas:

- Pre-build/pre-preview diagnostics gate tests for changed routes.
- Symptom-to-remediation table coverage tests for known failure families.
- Debug-log lifecycle and redaction fixture tests.
- Interaction-region artifact tests for UI/input/physics/camera-heavy goals.
- Preview/package source-hash readiness tests.
- Project diagnostic spool write/readback/triage tests.
- Resource lifecycle and orphan-process diagnostic tests.

Acceptance criteria:

- Tests fail if a route that requires build, Godot validation, preview, package, repair, or UI closure can mark success without diagnostics evidence.
- Tests fail if a known symptom family returns only `unhandled_request_failed` without a structured domain code, evidence ref, and remediation table entry.
- Tests fail if temporary debug output remains the only acceptance evidence for a changed route.
- Tests fail if deckbuilder route-map selection or hand-card dragging lacks an interaction-region artifact.
- Tests fail if preview/package readiness is reported from stale source hashes, missing artifacts, invalid tickets, or missing browser-safe readback.
- Tests fail if deleting a project deletes unresolved P0/P1/P2 project diagnostic spool records.
- Tests fail if admin diagnostic aggregation leaks raw host paths, raw prompts, token material, provider secrets, or cross-account user-visible evidence.
- Tests fail if routes with helper processes or temporary resources can mark success without lifecycle cleanup or orphan-process diagnostic evidence.
- Godot diagnostics and quality gate test results are included in phase review evidence and must have zero unresolved P0/P1/P2 findings.

## 11. Observability And Admin

Add admin/readback visibility for:

- Requirement map status and gap counts.
- Contract freshness status.
- Stale artifact reasons.
- Current recommended action.
- UI closure status.
- Godot UI capability contract version/hash and UI closure gap families.
- Repeated failure families from needs-fix/validation.
- Project diagnostic spool unresolved counts, severity, route, failure family, age, and triage status.
- Preview/package diagnostic readiness, including source hash set and browser-safe failure summary.

Acceptance criteria:

- Admin can answer "Why can this project not generate modules right now?" without reading raw logs.
- Admin can answer "Which GDD requirements did not enter the module plan?" from UI/readback.
- Admin can answer "Which GDD, scene route, and contract snapshot hash produced this prototype contract?" from UI/readback.
- Admin can answer "Which Godot UI capability contract version produced this module plan and UI closure result?" from UI/readback.
- Admin can answer "Which UI gap family is blocking final readiness: layout, input/focus, feedback, custom drawing, camera/layer, rendering/material, animation, geometry sizing, procedural visualization, or typed state?" without reading raw logs.
- Admin can answer "Which projects have unresolved diagnostics after deletion?" without reading workspace directories.
- Admin can triage project diagnostics as `unresolved|resolved|ignored|backlog` without rewriting raw failure history.
- User-facing readback remains account-scoped and cannot expose another account's project route state by guessed IDs.
- Admin aggregation may cross accounts, but raw evidence blobs, host paths, prompts, token material, and provider secrets remain redacted or omitted.
- Browser/API responses that expose project workflow state, route evidence, or admin audit details use `Cache-Control: no-store` unless a specific compatibility exception is recorded.

## 11.1 TapTap-Derived Hardening Patterns

This section records reusable engineering patterns observed in the TapTap project and adapts them to the Phase A frontend GDD-to-module workflow. These are not TypeScript or MCP migrations. They are boundary and governance patterns that should be implemented in Phase A's existing C# service, browser UI, route-state sidecars, and deterministic test style.

### 11.1.1 Conflict Assessment Against This Plan

Potential conflicts and decisions:

| Borrowed pattern | Potential conflict | Decision |
| --- | --- | --- |
| Feature-module style ownership | Phase A currently groups many route services under `Runs/`, `Readback/`, and `Browser/` rather than per-feature folders | Borrow the ownership contract, not the directory layout. Each route gets a route module contract section and tests, while code can remain in current C# ownership areas until a later refactor. |
| Unified definition plus handler | Phase A has ASP.NET handlers, services, route writers, browser callers, and artifact readback instead of MCP tools | Implement a route action descriptor/readback contract per route; do not introduce MCP abstractions. |
| CLI-first initialization | The GDD and scene confirmation flows are intentionally browser-visible | Keep user-facing GDD/scene/review flows in the browser; move deterministic admin, backfill, diagnostics, and guard checks to scripts/CLI where appropriate. |
| Release/workflow guard tests | Current plan is about prototype route governance, not npm release automation | Borrow the deterministic guard-test idea only: tests assert invariant text, artifact fields, route prompts, source boundaries, and API envelope behavior. |
| Path resolution policy | Phase A already has hosted workspace, artifact, package, and admin evidence boundaries | Create a Phase-specific path/readback policy instead of adopting TapTap's `WORKSPACE_ROOT + project_path` formula literally. |
| Runtime lifecycle logging | Phase A already has runtime recovery scripts and watchdogs | Add bounded expected-exit/orphan-process/log-retention guidance without changing runtime startup scripts in this plan. |
| Capability allowlist | Phase A browser routes already have account/auth gates, not MCP remote tool exposure | Borrow the explicit allowlist posture for user-visible workflow actions and admin operations; do not expose raw maintenance capabilities as ordinary project buttons. |
| Context separation | Phase A has account/project/run context mixed across services and readback | Add context-boundary tests and DTO rules rather than adopting TapTap's context types. |
| Progress notifications | Phase A has run state and browser polling instead of MCP progress tokens | Borrow the requirement that long operations expose progress/status through the existing run/readback model. |
| Release guard recovery | Phase A does not use TapTap's npm release flow | Borrow retry/idempotency and deterministic guard principles for workflow operations, not release-specific GitHub mechanics. |

Acceptance criteria:

- No new section requires moving Phase A code into a TapTap-style TypeScript directory layout.
- Existing Phase service standards remain the higher authority for API naming, sidecar naming, status enums, auth, evidence, and readback security.
- Any future implementation that adopts a borrowed pattern must include route-specific tests or a documented reason why the pattern is not applicable to that route.
- Borrowed patterns that touch user-visible actions, admin operations, credentials, paths, process lifecycle, or source authority must be reviewed under the P0/P1/P2 acceptance severity standard.

### 11.1.2 Route Module Contract Template

Borrowed capability: TapTap keeps each feature's definition, handler, resources, docs, and tests under an explicit feature contract. Phase A should define an equivalent contract per browser-consumed prototype route.

Target Phase A route module contract:

1. Route purpose and owner.
2. Required source artifacts.
3. Artifact-local sidecar schema.
4. API/readback DTO projection.
5. Browser action and disabled-state behavior.
6. Service entrypoint and route-state writer.
7. Prompt source boundary, if the route invokes Codex/LLM.
8. Admin/readback visibility.
9. Deterministic tests and smoke evidence.
10. Migration behavior for old projects.

Routes that should receive this contract first:

- `gdd-requirements`
- `prototype-contract`
- `workflow-recommendation`
- `ui-wiring-closure`
- `iteration-plan`
- `execute-next-goal`
- `needs-fix`
- `repair`

Acceptance criteria:

- Each new or changed route has a documented route module contract before implementation is marked complete.
- The route module contract names the route's artifact paths, API DTO fields, browser entrypoints, source hashes, stale behavior, and tests.
- A route cannot be marked complete if its service, browser caller, readback, sidecar schema, and tests disagree on action names, status values, error envelope shape, or source hash fields.

### 11.1.3 Unified Route Action Descriptor

Borrowed capability: TapTap pairs tool definition and handler in one registration object to prevent schema/handler drift. Phase A should use a C#-appropriate version.

Recommended shape:

- Define a route action descriptor per action that names:
  - `actionId`
  - API route
  - required source artifacts
  - operation status set
  - allowed HTTP status/error envelope mappings
  - browser label and disabled-state reason
  - service handler
  - readback sidecar path

This can be implemented as C# records, constants, or test fixtures. The important requirement is single-source verification, not a specific implementation class.

Acceptance criteria:

- `recommended_action`, browser button action, API action, and service handler names are checked by deterministic tests.
- The same action cannot have different names in browser JavaScript, API DTOs, route-state JSON, and service tests.
- Adding a new action requires updating the descriptor and a guard test that fails if the browser or readback omits it.

### 11.1.4 Deterministic Guard Tests For Workflow Invariants

Borrowed capability: TapTap uses tests to assert release and workflow guard behavior instead of relying on reviewers to remember rules.

Phase A should add deterministic guard tests for these invariants:

- Source-boundary prompts after contract freeze do not include raw `docs/game-type-guides` excerpts.
- New sidecars use snake_case and API/readback projections use camelCase.
- `operationStatus` values remain `returned_existing|active_run_reused|created_run|rejected`.
- `operationStatus=rejected` returns the standard error envelope.
- Route-state sidecars include `status`, `status_reason`, `updated_utc`, and `evidence_refs` when applicable.
- `evidence_refs.kind` stays within the Phase standard closed enum.
- `recommended_action` includes every action used by browser primary/secondary controls.
- `contract_hash` excludes volatile fields and source hashes use the canonicalization rules defined in this plan.
- Admin-only conflict/defer decisions cannot be made by normal user routes.
- Cross-account/existence-hiding responses do not expose fine-grained domain codes.

Acceptance criteria:

- Guard tests fail on string, enum, prompt-source, or route-state drift before manual review is required.
- Guard tests read saved prompts/evidence artifacts for source-boundary checks, not only summary route-state fields.
- Guard tests are deterministic and do not call external LLM, Steam, GitHub, or public network services.
- Each guard test names the invariant it protects and the route(s) it covers.

### 11.1.5 CLI/Script-First Admin And Backfill Operations

Borrowed capability: TapTap Maker keeps one-time initialization, environment checks, project binding, and repair-like operations in CLI workflows instead of spreading them across user-facing MCP/browser actions.

Phase A should keep browser flows for user decisions, but use deterministic scripts/CLI for:

- project game-type match backfill
- contract snapshot refresh inspection
- requirement map regeneration diagnostics
- stale artifact inspection
- route-state consistency audits
- prompt source-boundary audits
- admin review queue export
- readback path/security smoke
- runtime/orphan-process diagnostics

Acceptance criteria:

- Browser UI does not expose raw maintenance actions that can mutate many projects without explicit admin intent.
- Each admin/backfill script writes evidence under `logs/` and includes `timestamp_utc`, operation label, scoped IDs, and sanitized paths.
- Scripts are idempotent by default or explicitly document when they create new runs/states.
- Scripts do not manually mutate the live metadata DB unless the user explicitly authorizes that operation and a decision log records the reason.

### 11.1.6 Phase Path And Readback Policy

Borrowed capability: TapTap documents path resolution so users, tools, and hosted environments agree on how paths are interpreted.

Phase A should add a Phase-specific path/readback policy for hosted prototype routes:

- Host filesystem paths stay internal.
- Browser/API output uses workspace-relative paths, artifact IDs, package names, or short-lived tickets.
- Route-state sidecars store stable project-relative paths where possible.
- Admin raw evidence can include more detail only behind admin auth and redaction rules.
- Prompt/evidence artifacts referenced by tests use sanitized paths.
- Package/preview/download routes never accept caller-provided absolute host paths.

Acceptance criteria:

- A path/readback policy document or section exists before implementing new route-state readback surfaces.
- Tests cover path sanitization for user readback, admin readback, prompt evidence, package paths, and preview/download references.
- Browser/API responses never expose absolute host paths for normal users.
- Cross-account guessed project IDs cannot reveal whether a path, artifact, package, or prompt evidence exists.

### 11.1.7 Runtime Logs, Expected Exit, And Orphan Process Hygiene

Borrowed capability: TapTap separates expected lifecycle exits from crashes and bounds runtime log growth.

Phase A should extend runtime/route evidence guidance with:

- expected exit vs failure distinction for Codex/LLM helper processes
- bounded runtime/evidence log size or retention policy
- orphan-process diagnostics for route runners and preview/package helpers
- preserved failure evidence as sidecars, not overwritten summaries
- cleanup guidance that never deletes user workspaces silently

Acceptance criteria:

- Expected process exits are logged as lifecycle events, not crash evidence.
- Route runner failures preserve stderr/stdout or summarized evidence with redaction and size limits.
- Runtime diagnostics identify orphaned route/helper processes without killing them unless an explicit recovery script is invoked.
- Evidence cleanup rules preserve failure artifacts needed for repair and audit.

### 11.1.8 Cache And Freshness Policy

Borrowed capability: TapTap documents TTL, forced refresh, and write-through behavior for cached app data.

Phase A should define cache/freshness behavior for project-level workflow artifacts:

- Requirement map and prototype contract freshness is source-hash based, not time based.
- Admin readback summaries may be cached only when they record source hashes or `updated_utc`.
- Write operations that change GDD, scene route, contract snapshot, requirement map, or prototype contract must invalidate dependent recommendations.
- Manual refresh must be explicit and recorded.
- Old `unknown` freshness must remain diagnostic and cannot be promoted to success.

Acceptance criteria:

- Freshness rules name source artifacts and invalidation edges.
- Write-through or invalidation tests cover GDD changes, scene route changes, contract snapshot changes, requirement map refresh, and contract freeze.
- Cached readback responses expose freshness status and source hash references.
- No route treats a stale or unknown cache as fresh without an explicit compatibility rule and test.

### 11.1.9 Directory-Scoped Agent Instructions

Borrowed capability: TapTap uses directory-scoped instructions for feature modules rather than relying only on one large repository guide.

Phase A should avoid expanding `AGENTS.md` for every route detail. Instead, use focused docs or instructions near the relevant route family.

Recommended targets:

- `docs/standards/phase-service.md` for service-wide invariants.
- A new route-module template document under `docs/workflows/` or `docs/standards/`.
- Route-specific notes near GDD/scene/prototype workflow docs.
- Execution plans for durable project-specific intent.

Acceptance criteria:

- New durable rules are placed in the narrowest authoritative document that owns the topic.
- `AGENTS.md` remains a routing map and does not duplicate detailed route-module schemas.
- Route implementation PRs link to the relevant route contract or standards section instead of relying on hidden conversation history.

### 11.1.10 User-Guided Ambiguity Resolution

Borrowed capability: TapTap tools explicitly instruct the agent to present choices to users when automatic selection would be unsafe.

Phase A should apply the same principle to ambiguous game-design workflow decisions:

- Multiple plausible scene routes require scene confirmation, not automatic selection.
- Multiple candidate required modules require requirement-map review or admin/user decision depending on priority.
- Multiple repair options require recommendation plus visible alternatives.
- Default type contract conflicts require admin-approved defer/conflict decisions when they affect P0/P1 behavior.

Acceptance criteria:

- The workflow recommendation can present one primary action while preserving safe secondary actions.
- Ambiguous P0/P1 scene/module decisions cannot be silently auto-selected.
- User-facing flows ask for confirmation when scene count, scene relation, or module priority changes the prototype scope.
- Admin-only decisions remain admin-only even when the LLM suggests a resolution.

### 11.1.11 Capability Allowlist And Action Exposure

Borrowed capability: TapTap's Maker flow exposes only a small allowlist of runtime tools through MCP while keeping broader setup and maintenance behind CLI/admin flows.

Phase A should apply the same posture to browser-visible project actions:

- User project pages expose only the safe current-stage actions, safe secondary actions, and readback views.
- Bulk backfill, cross-project audits, raw prompt inspection, contract snapshot refresh inspection, and source-boundary audits stay admin-only or script-only.
- Admin UI can list these operations, but mutation still requires explicit admin intent, scoped IDs, and evidence creation.
- Route descriptors identify whether an action is `user_visible`, `admin_visible`, `script_only`, or `internal`.

Acceptance criteria:

- Every route action descriptor includes an exposure class: `user_visible|admin_visible|script_only|internal`.
- Browser tests assert normal users cannot see or invoke admin/script-only mutation actions.
- API tests assert hidden actions are not only hidden in the UI; unauthorized direct calls also fail with the standard account/auth error behavior.
- Adding a new action without an exposure class fails a guard test.

### 11.1.12 Context Boundary And DTO Hygiene

Borrowed capability: TapTap separates business context from transport-layer extras so handlers do not accidentally depend on hidden client details.

Phase A should define route execution context boundaries:

- Account/project authorization context.
- Route source context: GDD, scene route, requirement map, frozen contract, run state.
- Transport context: request ID, correlation ID, browser session, polling/readback concerns.
- Admin context: admin identity, scoped operation, redaction level.

Acceptance criteria:

- Route services do not accept browser-only DTOs as their internal source of authority; they receive validated account/project/source context.
- Tests cover that spoofed project IDs, account IDs, source hashes, or admin flags in client payloads cannot override server-derived context.
- Prompt builders receive explicit source artifacts and sanitized context, not raw request bodies.
- Readback DTOs omit internal-only context fields unless the route is admin-authenticated and redacted.

### 11.1.13 Progress And Long-Running Operation Feedback

Borrowed capability: TapTap tool handlers support progress notification channels for long-running work.

Phase A should express long-running progress through existing run state and readback surfaces:

- GDD requirement map generation, contract freeze, iteration planning, execute-next-goal, repair, UI closure, preview, and package should expose stable progress states.
- Progress should distinguish queued, running, waiting for user/admin decision, failed, blocked, stale, and succeeded.
- Browser polling should show the last meaningful status instead of only a spinner.

Acceptance criteria:

- Long-running POST routes either return an immediately readable route state or an active `runId` with polling/readback URL.
- Browser tests cover queued/running/blocked/failed/succeeded rendering for at least requirement map, iteration plan, and execute-next-goal.
- A failed long-running operation exposes a sanitized failure reason and evidence reference, not only `unhandled_request_failed`.
- Progress status cannot mark success unless the required sidecar/readback artifact exists and validates.

### 11.1.14 Idempotent Recovery And Duplicate-Run Control

Borrowed capability: TapTap release guards include recovery behavior for existing PRs and avoid duplicating release state.

Phase A should apply this to route operations:

- Repeated POST calls with unchanged source hashes return existing results or reuse active runs.
- Changed source hashes require explicit refresh intent when they would invalidate confirmed user decisions.
- Duplicate active run creation is rejected or reused consistently.
- Recovery reads authoritative route state before starting new work.

Acceptance criteria:

- Tests cover double-click, browser retry, network retry, and concurrent duplicate POST behavior for requirement map, contract freeze, iteration plan, execute-next-goal, and UI closure.
- Duplicate run handling returns `operationStatus=returned_existing`, `active_run_reused`, or `rejected`; it must not silently start two conflicting runs.
- Recovery logic compares source hashes and operation scope before reusing a run.
- Existing active runs from another account are never visible or reusable across account boundaries.

### 11.1.15 Credential, Token, And Secret Boundary

Borrowed capability: TapTap docs separate local credential preparation from runtime operations and avoid treating tokens as ordinary workflow data.

Phase A already has token hashing and secret rules. This plan should reinforce them for GDD/prototype workflow changes:

- Prompts, sidecars, route evidence, admin exports, and browser DTOs must not include provider secrets, auth tokens, token hashes, or raw credential material.
- Script/admin evidence records operation scope without copying secret-bearing environment variables.
- LLM/Codex prompt artifacts redact credentials before persistence.

Acceptance criteria:

- Tests or validators scan generated route evidence and prompt artifacts for known secret variable names and token-like fields.
- Redaction tests include fixture-based examples for environment variable names, provider keys, token hashes, bearer-like tokens, local absolute paths that contain user/account identifiers, and prompt/evidence/admin export samples.
- The validator owns a documented denylist and allowlist update path; adding a new secret-bearing variable or evidence field requires updating the fixture set or recording a non-applicability rationale.
- Admin exports redact token hashes and provider credentials even for admin users.
- Any new script that reads environment variables documents which ones are secret and proves they are not written to evidence.
- Secret redaction failure is P0 and blocks acceptance.

### 11.1.16 Configuration And Environment Preflight

Borrowed capability: TapTap Maker CLI performs setup and environment checks before exposing runtime operations.

Phase A should add deterministic preflight checks for workflow-critical capabilities:

- Codex command availability and shared invocation protocol.
- Godot binary availability where a route requires validation or preview/package.
- Hosted workspace root and project boundary availability.
- Metadata DB path readability through the platform service, without manual mutation.
- Game-type guide and `game-types.csv` availability for project creation/matching only.

Acceptance criteria:

- Admin/operator preflight can report missing Codex, Godot, workspace root, metadata DB access, and game-type guide/index inputs without starting a GDD/prototype run.
- User-facing project actions show blocked reasons when a required runtime dependency is unavailable.
- Normal-user preflight/readback responses expose capability status and blocked reason only; host paths, metadata DB paths, environment values, and workspace roots are visible only in admin-authenticated, redacted evidence.
- Preflight checks write sanitized evidence under `logs/`.
- Preflight does not validate by invoking external LLM/Steam/network services unless explicitly requested by an admin/operator command.

### 11.1.17 Documentation Indexing And Route Discoverability

Borrowed capability: TapTap keeps targeted docs for maker, paths, logs, guards, and feature modules, making operational behavior discoverable without reading code.

Phase A should keep this execution plan as intent and move durable implementation rules into authoritative docs during implementation:

- Route module contract template.
- Path/readback policy.
- Guard-test invariant list.
- Admin/backfill script evidence convention.
- Runtime lifecycle and expected-exit guidance.
- Cache/freshness policy.
- Godot diagnostics and quality-gate contract.
- Project diagnostic spool and symptom-to-remediation guide.

Acceptance criteria:

- Each durable rule added by implementation is linked from `docs/standards/_index.md`, `docs/standards/phase-service.md`, or a route workflow doc.
- Execution plan items that become permanent standards are not left only in the plan.
- `AGENTS.md` remains a concise router and links to durable docs instead of duplicating full rule text.
- A reviewer can find route contract, source-boundary, path/readback, guard-test, Godot diagnostics, project diagnostic spool, and symptom-to-remediation rules from the docs index without scanning conversation history.

## 11.2 Godot UI Capability Contract Migration

This section migrates TapTap's UI system capability model into this repository as a Godot-only workflow contract. It is not a technology migration. The source capability idea is: UI system work is a first-class gameplay implementation domain, custom drawing has explicit rules, camera/physics/rendering/animation/procedural systems affect player-facing UI, geometry sizes cannot be guessed, enum/state typing matters, and runtime-specific constraints must be governed.

### 11.2.1 Conflict Assessment

| TapTap capability or constraint | Conflict in this repo | Godot decision |
| --- | --- | --- |
| UrhoX/Urho3D runtime | This repo uses Godot 4.5 + .NET/Mono and hosted Godot workspaces | Translate runtime capability domains only; all implementation terms must be Godot 4.5/C# or Godot-compatible GDScript concepts. |
| Lua 5.4 scripting | This repo's template and tests are C#/.NET-centered | Do not introduce Lua. UI contract examples use C# script ownership and allow typed GDScript only if an existing project already uses it. |
| NanoVG custom drawing | Godot does not use NanoVG as the project UI drawing layer | Use `Control._draw`, `CanvasItem._draw`, `Line2D`, `Polygon2D`, `ArrayMesh`, `ImmediateMesh`, `SubViewport`, and Godot materials/shaders as the valid drawing vocabulary. |
| PBRNoTexture material rule | The exact technique family is Urho-specific | Replace it with repo-approved Godot material/rendering policy fields. Do not invent external texture/material pipelines inside workflow prompts. |
| `boundingBox` size discipline | Godot exposes size through different APIs and import metadata | Require measurable sources: theme metrics, `Control.custom_minimum_size`, texture import metadata, `AABB`, `get_aabb()`, collision shapes, or documented source assets. |
| `CustomGeometry` fallback | Godot geometry APIs differ | Use `ArrayMesh`, `ImmediateMesh`, `MeshInstance3D`, `Polygon2D`, or `Line2D` when built-in shapes are missing. |
| Numeric enum avoidance | The principle applies directly, but names differ | Require C# enums, typed GDScript enums, named constants, or schema enums for route state, UI mode, animation state, input state, and validation status. |
| `.emmylua` typing source | This repo does not use EmmyLua as typing authority | Use C# types, typed GDScript where applicable, generated schema DTOs, and route-state JSON schema as the type authority. |

Acceptance criteria:

- No implementation prompt, route state, UI closure output, or durable workflow standard requires UrhoX, Urho3D, Lua, NanoVG, PBRNoTexture, or `.emmylua`.
- The only permitted references to TapTap-only terms are conflict-assessment documentation or migration rationale.
- Every migrated capability has a Godot-owned equivalent, validation artifact, and route in this workflow.
- Review records zero unresolved P0/P1/P2 findings for technology-stack leakage, missing Godot equivalent, or untestable acceptance.

### 11.2.2 Full Godot Capability Checklist

The workflow must treat the following domains as first-class prototype implementation capabilities whenever the GDD, scene route, default prototype contract, or requirement map implies them:

1. UI scene architecture
   - Godot ownership: `Control` scenes, `CanvasLayer` HUDs, scene instancing, autoload boundaries, scene transitions, and route-specific UI roots.
   - Required workflow data: scene path, node path, owning requirement IDs, player flow, state boundary, validation references.
2. Layout, containers, theme, and responsive rules
   - Godot ownership: `Container` nodes, anchors, safe-area handling, theme resources, minimum sizes, fixed-format board/grid constraints, and viewport-safe scaling.
   - Required workflow data: layout strategy, fixed-format rationale, theme/min-size source, desktop/mobile or viewport evidence.
3. HUD, menus, overlays, and modal state
   - Godot ownership: `CanvasLayer`, modal controls, pause/menu overlays, notification/toast patterns, status bars, combat HUD, inventory/deck/reward panels.
   - Required workflow data: overlay layer, modal blocking behavior, input routing, state synchronization, screenshot/evidence references.
4. Custom 2D drawing and visual affordances
   - Godot ownership: `Control._draw`, `CanvasItem._draw`, `Line2D`, `Polygon2D`, draw invalidation, hit testing, and redraw lifecycle.
   - Required workflow data: drawing surface, redraw trigger, hit-test path, visual feedback states, canvas-pixel or screenshot evidence.
5. Input, focus, and navigation
   - Godot ownership: `InputMap`, mouse/touch events, keyboard focus, gamepad focus, drag/drop, hover/pressed/selected/disabled states, focus neighbors.
   - Required workflow data: input paths, supported devices, focus status, drag/drop boundaries, disabled/error states, validation references.
6. Camera, viewport, world/UI layering, and physics interaction
   - Godot ownership: `Camera2D`, `Camera3D`, `CanvasLayer`, `SubViewport`, physics layers/masks, raycasts, world-space UI, and screen-to-world transforms.
   - Required workflow data: camera owner, UI/world separation rule, raycast/input conversion path, layer/mask rationale, validation references.
7. Rendering, materials, shaders, and import policy
   - Godot ownership: `CanvasItemMaterial`, `StandardMaterial3D`, `ShaderMaterial`, import settings, render layers, lighting mode, and repo-approved material profiles.
   - Required workflow data: material/rendering policy, source asset/import evidence, shader ownership, fallback policy, no unapproved material pipeline.
8. Animation and state machines
   - Godot ownership: `AnimationPlayer`, `AnimationTree`, state-machine resources, tween usage, transitions, combat/character/UI animation states.
   - Required workflow data: animation state reference, transition trigger, state enum/constant, validation or screenshot evidence.
9. Procedural generation and generated UI/world content
   - Godot ownership: deterministic seed inputs, generated map/route/deck/reward layouts, generated scene nodes, headless validation, replayable artifacts.
   - Required workflow data: seed/source, generated output summary, validation artifact, no hidden nondeterministic completion path.
10. Geometry, mesh fallback, and size measurement
    - Godot ownership: `AABB`, `get_aabb()`, collision shapes, import metadata, `ArrayMesh`, `ImmediateMesh`, `MeshInstance3D`, `Polygon2D`, `Line2D`.
    - Required workflow data: size source, collision/interaction shape, fallback geometry API, validation reference.
11. Typed state, enums, and schema contracts
    - Godot ownership: C# enums/classes/records, typed GDScript where used, named constants, DTO/schema enums, route-state schema validation.
    - Required workflow data: typed state reference, enum source, schema field, invalid-state behavior, tests.
12. Accessibility, readability, and feedback legibility
    - Godot ownership: theme contrast, readable font sizes, hover/focus/selected/disabled states, error copy, layout overflow handling, motion restraint where needed.
    - Required workflow data: readability target, feedback states, screenshot/browser evidence, no-overlap validation.

Acceptance criteria:

- Requirement-map generation can classify each applicable domain above as a requirement kind, acceptance marker, or explicit not-applicable rationale.
- Iteration-plan generation can create a goal for each applicable P0/P1 domain or block with a structured reason.
- UI closure can validate each applicable domain through `ui_surface_matrix` fields and evidence references.
- Deckbuilder reference coverage includes route-map UI scene architecture, route path custom drawing or visible node affordance, hand-card drag/drop input, combat HUD feedback, reward selection UI, and state-machine/typed-state references.
- A phase cannot pass if any applicable P0/P1 domain is silently omitted from requirement map, iteration plan, execute-goal prompt, or UI closure.
- The capability checklist is considered complete only when review records zero unresolved P0/P1/P2 findings.

### 11.2.3 Workflow Injection Points

The Godot UI capability contract must be consumed by:

- `gdd-question-form`: optional hints may ask users about UI-heavy flows, but absence of user detail must not suppress default UI capability classification.
- `scene-route-confirmation`: each confirmed scene should declare expected player-facing UI surfaces or `no_ui_needed`.
- `gdd-document-generation`: generated GDD should include UI/HUD/input/drawing/camera/animation/procedural/rendering implications when they are part of the prototype promise.
- `gdd-requirement-map`: extracts UI requirements and assigns severity, source section, scene mapping, module mapping, and acceptance markers.
- `prototype-contract-freeze`: freezes the Godot UI capability contract version/hash and links it to the source artifact hash set.
- `iteration-plan`: creates UI surface goals and required modules from P0/P1 requirements.
- `module-execution`: injects the frozen Godot UI capability contract for relevant goals and requires evidence before completion.
- `needs-fix` and `repair`: map UI failures back to requirement IDs and gap families instead of producing generic "fix UI" prompts.
- `ui-wiring-closure`: validates the complete UI surface matrix, not only whether controls exist.
- `preview-package`: exposes final-readiness blockers from UI closure while preserving the existing early package behavior defined in this plan.

Acceptance criteria:

- Each injection point above has an implementation note, route contract field, prompt section, validator, or explicit non-applicability record before the corresponding phase is accepted.
- Source-boundary tests prove downstream routes use the frozen Godot UI capability contract and current project artifacts, not raw game-type guide excerpts or mutable broad guidance.
- UI failures from validation, screenshots, canvas-pixel checks, or manual needs-fix records can be traced to requirement IDs and UI gap families.
- Recommended next action surfaces UI-contract blockers as actionable workflow states, not hidden log-only failures.

### 11.2.4 Godot Governance Rules

1. No P0/P1 gameplay feature is complete without visible player entry, feedback, state boundary, and validation evidence unless `no_ui_needed` is explicitly justified.
2. Prefer `Control` + `Container` + `Theme` + anchors/safe areas for UI layout. Absolute positioning is allowed only for fixed-format boards, canvas tools, or world overlays with responsive bounds and validation.
3. HUD and menus must declare `CanvasLayer`/viewport ownership and input routing. World-space UI must declare camera and screen/world transform ownership.
4. Drag/drop and pointer-heavy features must declare start, hover, cancel, drop, invalid drop, and commit states.
5. Custom drawing must declare the Godot drawing API, redraw invalidation trigger, hit-test strategy, and screenshot/canvas evidence.
6. Camera/physics interactions must use named layers/masks and measurable raycast/collision boundaries rather than hardcoded magic numbers.
7. Rendering/material/shader work must use repo-approved Godot material profiles or explicitly documented built-in resources. Workflow prompts must not invent a new external material pipeline.
8. 3D and 2D size-sensitive work must cite `AABB`, `get_aabb()`, collision shape, import metadata, theme metric, or min-size source. Guessing dimensions is a blocker.
9. Missing built-in geometry must use Godot geometry APIs (`ArrayMesh`, `ImmediateMesh`, `MeshInstance3D`, `Polygon2D`, `Line2D`) with validation evidence.
10. UI mode, animation state, input state, route state, and validation status must use enums, named constants, or schema enums rather than unexplained numeric codes.
11. Procedural UI/world generation must be seedable, replayable, and validated by headless checks or exported deterministic evidence. A missing headless harness is not a pass condition; it requires a recorded substitute check.
12. Screenshot, canvas-pixel, or exported visual evidence is required for high-risk visual UI changes. A validator-only substitute is allowed only when phase review records the exact harness limitation, affected route, substitute deterministic check, and proof that no P0/P1/P2 issue remains.

Acceptance criteria:

- The full governance checklist remains in scope for the migration. A phase may mark a rule as not-yet-active only when no touched route, artifact, prompt, or UI surface depends on that rule and the phase review records proof.
- A touched route cannot mark an applicable Godot UI governance rule as not-yet-active.
- Any violation of rules 1, 2, 3, 4, 5, 8, or 10 for a P0/P1 requirement is a blocking P1 or higher issue.
- Rule exceptions require structured rationale in route state or phase review evidence and cannot be buried in chat text.
- The final phase review confirms zero unresolved P0/P1/P2 findings across all governance rules touched by the migration.

## 11.3 Godot Diagnostics And Quality Gate Migration

This section migrates TapTap's development quality-gate and troubleshooting discipline into a Godot/Phase service model. It is not a local tooling migration. The source capability idea is: diagnostics must run before build/preview/package, recurring symptoms should map to remediation, debug logs are useful during development but must become structured evidence before acceptance, interaction regions should be designed before implementation, preview is an immediate validation loop, and disposable/runtime resources must be released explicitly.

### 11.3.1 Conflict Assessment

| TapTap quality-gate capability | Conflict in this repo | Godot/Phase decision |
| --- | --- | --- |
| LSP diagnostics before build | Phase routes run through hosted workspaces, C#/.NET, Godot, Python scripts, and browser/API readback rather than a single local IDE | Translate this into pre-build/pre-preview diagnostics using `dotnet build`/tests, Godot self-check, GdUnit4, route-state validators, and saved evidence. No route can rely only on assistant prose. |
| Symptom-to-solution table in `AGENTS.md` | This repo keeps `AGENTS.md` as a routing layer and avoids large embedded rule catalogs | Create a durable diagnostics guide and admin triage taxonomy outside `AGENTS.md`, then link it from standards or workflow indexes. |
| Development-stage print-heavy logging | Phase service logs and browser readback can leak host paths, prompts, and secrets | Allow temporary diagnostics only when they are migrated to sanitized route evidence or removed before acceptance. Raw logs are admin-only or hidden unless redaction rules explicitly allow readback. |
| ASCII collision-region sketch before implementation | Godot prototypes need UI hit zones, CanvasLayer/world boundaries, collision shapes, and raycast areas, not only TapTap collision sketches | Require a lightweight interaction-region artifact for UI/physics/input-heavy goals: ASCII sketch, hit-zone table, node/collision map, or scene sketch. |
| Preview button immediate validation | Phase preview/package is browser/API hosted, ticketed, and source-hash-sensitive | Treat preview as an immediate validation route whose readiness is tied to current source hashes and diagnostic evidence. Preview failures must be actionable, not generic 500s. |
| Immediate `Dispose()` of Object subclasses | Godot nodes and C# resources have different lifecycle ownership | Translate this into explicit lifecycle checks: Godot `QueueFree`/scene ownership, C# `IDisposable`, process/file/SQLite watcher disposal, and orphan-process diagnostics. |

Acceptance criteria:

- No implementation prompt, route state, diagnostics guide, or durable workflow standard requires TapTap local runtime concepts, TapTap-specific LSP APIs, or TapTap disposal rules.
- Every migrated quality-gate capability has a Godot/Phase-owned equivalent, an evidence artifact, and a validation route or test.
- `AGENTS.md` remains a router; durable diagnostics tables live in standards/workflow docs and are linked from the appropriate index.
- Review records zero unresolved P0/P1/P2 findings for technology-stack leakage, missing Godot/Phase equivalent, or untestable acceptance.
- The quality-gate migration cannot pass unless review records zero unresolved P0/P1/P2 findings in diagnostics, preview validation, resource lifecycle, diagnostic spool, admin triage, redaction, or deleted-project retention behavior.

### 11.3.2 Full Quality Gate Migration Checklist

The workflow must treat the following capabilities as first-class diagnostics and quality gates for GDD-to-module execution:

1. Pre-build diagnostics gate
   - Godot/Phase ownership: `dotnet build`, .NET tests, analyzer/nullable diagnostics where enabled, Godot self-check, GdUnit4, scene load checks, route-state validators, and source-hash validation.
   - Required workflow data: diagnostic command, route, project/account scope, source hash set, status, evidence refs, failure family, and remediation hint.
2. Symptom-to-remediation table
   - Godot/Phase ownership: durable diagnostics guide outside `AGENTS.md`, with entries for GDD/scene/requirement/contract/iteration/execute/repair/UI/preview/package/project-delete failures.
   - Required workflow data: symptom, likely causes, owner route, safe first checks, admin-only checks, evidence paths, and recovery action.
3. Debug log lifecycle
   - Godot/Phase ownership: temporary `GD.Print`, `Console.WriteLine`, stdout/stderr, and route debug traces are allowed during development but must be removed, reduced, or converted to sanitized evidence before acceptance.
   - Required workflow data: raw path policy, redaction status, retention class, cleanup status, and replacement evidence refs.
4. Interaction-region design artifact
   - Godot/Phase ownership: ASCII diagram, hit-zone table, collision-shape map, CanvasLayer/world-boundary sketch, raycast/camera transform note, or scene sketch for UI/physics/input-heavy work.
   - Required workflow data: affected requirement IDs, scene/node paths, input devices, hit zones, invalid zones, collision shapes or Control rects, and validation refs.
5. Preview validation loop
   - Godot/Phase ownership: preview route, package route, web preview smoke, Godot smoke, screenshot/canvas-pixel/exported evidence, ticket/readback rules, and source-hash readiness.
   - Required workflow data: preview source hash set, preview readiness status, artifact refs, failure family, browser-safe diagnostic summary, and retry guidance.
6. Explicit resource lifecycle
   - Godot/Phase ownership: C# `IDisposable` resources, SQLite connections, file streams, process handles, watchers, temporary directories, Godot node ownership/`QueueFree`, preview/package helper cleanup, and orphan-process diagnostics.
   - Required workflow data: owned resource list, cleanup strategy, expected exit behavior, orphan detection, evidence refs, and failure handling.
7. Project diagnostic spool and admin triage
   - Godot/Phase ownership: project-scoped diagnostic sidecars outside the deletable workspace, admin triage queue, failure-family taxonomy, redacted summaries, and deletion-safe retention.
   - Required workflow data: account ID, project ID, project name, run ID, route, failure family, severity, source refs, redaction status, triage status, created UTC, and preserved evidence refs.
8. Route failure taxonomy
   - Godot/Phase ownership: bounded failure families such as `gdd_missing`, `scene_route_missing`, `requirement_map_invalid`, `coverage_gap`, `contract_stale`, `source_unknown`, `ui_contract_unknown`, `missing_ui_surface`, `godot_build_failed`, `scene_load_failed`, `preview_blank`, `package_missing`, `workspace_delete_failed`, `duplicate_active_run`, and `diagnostic_spool_write_failed`.
   - Required workflow data: failure family enum, route domain code, remediation table entry, admin visibility, user-safe summary, and test coverage.

Acceptance criteria:

- Each quality-gate capability above has a route contract field, diagnostics guide entry, validator, smoke, or explicit non-applicability record before the corresponding route phase is accepted.
- Any P0/P1 route that invokes build, Godot validation, preview, package, repair, or UI closure must pass the pre-build/pre-preview diagnostics gate or return a structured blocker before invoking downstream work.
- Temporary debug output cannot be the only acceptance evidence for a changed route; final acceptance must cite sanitized evidence refs or structured route state.
- Interaction-heavy P0/P1 goals cannot be marked complete unless the iteration goal or evidence includes an interaction-region artifact or an explicit `no_interaction_region_needed` rationale.
- Preview/package readiness cannot be marked `ready` or `succeeded` when source hashes, diagnostic evidence, package artifact, preview ticket, or browser-safe readback is stale, missing, or invalid.
- Project diagnostic spool records must survive workspace deletion and remain admin-triable without exposing raw host paths, token material, provider secrets, or raw prompts to normal users.
- The quality-gate checklist is considered complete only when review records zero unresolved P0/P1/P2 findings.

### 11.3.3 Project Diagnostic Spool

The project diagnostic spool is the Phase-specific extension of TapTap's symptom table and debug-log discipline. Because Phase projects live in hosted workspaces that may be deleted, critical diagnostics must be preserved outside the project workspace.

Recommended durable path:

```text
logs/phase-a-innernet/diagnostics/projects/<account_id>/<project_id>/
```

Recommended record schema:

```json
{
  "schema_version": "project-diagnostic-spool.v1",
  "account_id": "...",
  "project_id": "...",
  "project_name": "...",
  "run_id": "...",
  "route": "gdd-requirements|prototype-contract|iteration-plan|execute-next-goal|needs-fix|repair|ui-wiring-closure|preview-package|project-delete",
  "failure_family": "gdd_missing|scene_route_missing|requirement_map_invalid|coverage_gap|contract_stale|source_unknown|ui_contract_unknown|missing_ui_surface|godot_build_failed|scene_load_failed|preview_blank|package_missing|workspace_delete_failed|duplicate_active_run|diagnostic_spool_write_failed",
  "severity": "P0|P1|P2|info",
  "triage_status": "unresolved|resolved|ignored|backlog",
  "created_utc": "...",
  "source_refs": [],
  "evidence_refs": [],
  "redaction_status": "redacted|raw_admin_only|blocked",
  "user_safe_summary": "",
  "admin_summary": "",
  "remediation_hint_id": ""
}
```

Acceptance criteria:

- Diagnostic spool files are written outside the hosted workspace so project deletion removes workspace files without deleting preserved diagnostics.
- Deleting a project preserves diagnostic spool records and records a `project-delete` diagnostic event with result code, account scope, and sanitized project identity.
- The spool schema example, failure-family taxonomy seed, and symptom-to-remediation table use the same initial `failure_family` values, or the standards file explicitly declares the schema field as open-ended and points to the taxonomy as authority.
- Admin readback can list unresolved diagnostics by account, project, route, failure family, severity, and age without reading raw logs.
- Normal-user readback cannot access another account's diagnostic spool and cannot see raw host paths, raw prompts, token material, provider secrets, or admin-only evidence.
- Triage status updates are admin-only, append-only or audit-backed, and cannot rewrite raw failure history.
- Retention/cleanup rules must preserve unresolved P0/P1/P2 diagnostics and must never delete diagnostics as a side effect of ordinary project deletion.
- Tests cover spool write, deleted-project lookup, account isolation, admin aggregation, redaction, triage status update, and cleanup/retention non-destruction for unresolved P0/P1/P2 diagnostics.
- Project diagnostic spool review records zero unresolved P0/P1/P2 findings for schema drift, failure-family mismatch, redaction, account isolation, retention, cleanup, triage auditability, or deleted-project lookup.

### 11.3.4 Symptom-To-Remediation Table

The diagnostics guide should include an initial table for the GDD-to-module workflow. This table should be durable documentation, not hidden implementation knowledge.

Initial symptom families:

| Symptom | Likely failure family | First checks | Recovery action |
| --- | --- | --- | --- |
| GDD run completes but no scene confirmation appears | `scene_route_missing` | GDD run state, scene-route sidecar, workflow recommendation | Regenerate scene route or mark route state invalid with evidence. |
| Requirement map is empty or too small | `requirement_map_invalid` | GDD hash, scene route hash, contract snapshot, LLM JSON validity | Regenerate requirement map; block contract freeze if P0/P1 gaps remain. |
| Iteration plan ignores required modules | `coverage_gap` | Requirement IDs, default contract modules, admin conflict decisions | Block plan or create follow-up required module goals. |
| Execute-next-goal starts from stale source | `contract_stale` | Source hash set, current frozen contract, requirement map | Reject before Codex invocation and recommend refresh/freeze. |
| UI closure says success but player cannot use feature | `missing_ui_surface` | UI surface matrix, interaction-region artifact, screenshot/canvas evidence | Create UI follow-up goal and block final readiness. |
| Preview opens blank or stale content | `preview_blank` | Preview source hash, package artifact, web preview smoke, browser console evidence | Rebuild preview/package from current source hash set. |
| Package artifact missing | `package_missing` | Package run evidence, artifact index, ticket creation, workspace path policy | Re-run package or surface artifact readback blocker. |
| Godot scene fails to load | `scene_load_failed` | Godot self-check, GdUnit, scene path, import diagnostics | Run repair with latest Godot diagnostic evidence. |
| Project deletion fails or leaves workspace | `workspace_delete_failed` | project diagnostic spool, delete diagnostic jsonl as legacy/runtime evidence only, workspace path, account/project scope | Preserve diagnostic spool, surface admin cleanup action. |
| Active run is reused incorrectly | `duplicate_active_run` | operation scope, source hash scope, account-project scope marker | Reject stale reuse and start or resume only matching hash scope. |

Acceptance criteria:

- The diagnostics guide includes at least the symptom families above before Phase 6 is accepted.
- Every table row links to a route, failure family enum, safe user summary policy, admin evidence policy, and recovery action.
- New failure families added by implementation must update the table and tests in the same implementation slice.
- A route cannot expose only `unhandled_request_failed` for a known table symptom; it must return a structured domain code and evidence reference.
- The table is linked from `docs/standards/_index.md`, `docs/standards/phase-service.md`, or a route workflow doc before implementation is called complete.

### 11.3.5 Interaction-Region Design Gate

P0/P1 UI, input, physics, route-map, card-dragging, collision, or camera-transform work should include an interaction-region artifact before implementation.

Accepted artifact forms:

- ASCII diagram.
- Hit-zone table.
- Godot scene/node map with `Control` rects or collision shapes.
- CanvasLayer/world boundary sketch.
- Raycast/camera transform note.
- Screenshot annotated by coordinates or named regions.

Acceptance criteria:

- The artifact records affected requirement IDs, scene IDs, node paths, input devices, valid regions, invalid regions, state transitions, and validation refs.
- Deckbuilder route-map path selection and hand-card dragging cannot be accepted without an interaction-region artifact.
- If a goal declares `no_interaction_region_needed`, the route state must include a rationale and tests must prove the requirement has no UI/input/physics/camera interaction.
- The interaction-region artifact is included in prompt/evidence source refs for UI-touching execution and repair routes.
- Review records zero unresolved P0/P1/P2 findings for missing or stale interaction-region artifacts.

### 11.3.6 Resource Lifecycle And Orphan Diagnostics Gate

Resource lifecycle checks should prevent preview/package/repair helpers from leaking processes, handles, or temporary files.

Godot/Phase lifecycle rules:

- C# `IDisposable` resources are disposed through `using`, `await using`, or explicit cleanup in long-lived services.
- SQLite connections, file streams, process handles, filesystem watchers, and temporary workspace handles have deterministic cleanup paths.
- Godot nodes created dynamically have scene-tree ownership or `QueueFree`/`Free` cleanup rules appropriate to Godot object lifetime.
- Preview/package/helper processes record expected exit, timeout, cancellation, and orphan-detection evidence.
- Cleanup never deletes user workspaces silently and never deletes preserved diagnostic spool records.

Acceptance criteria:

- Changed routes that create processes, temp directories, file handles, or Godot runtime nodes include lifecycle tests or documented non-applicability.
- Orphan-process diagnostics run before a route claims preview/package/repair success when helper processes were involved.
- `workspace_delete_failed` and helper cleanup failures write project diagnostic spool records with redacted evidence.
- Resource cleanup failures are never hidden behind a green route status.
- Review records zero unresolved P0/P1/P2 findings for lifecycle leaks, unbounded temp files, or missing orphan diagnostics.
- The resource lifecycle gate cannot pass unless review records zero unresolved P0/P1/P2 findings for leaked processes, undisposed C# resources, unbounded temporary files, unsafe workspace cleanup, or deleted diagnostic spool records.

## 12. Implementation Phases

### Phase 0: Cross-Cutting Governance Prerequisites

These prerequisites must land before Phase 1 creates new browser/API readback surfaces or new POST route behavior. Phase 6 remains the later consolidation phase for full route governance coverage, but these items are not allowed to wait until the end.

Deliverables:

- route module contract template
- Phase path/readback policy
- route action exposure classes: `user_visible|admin_visible|script_only|internal`
- context-boundary and DTO hygiene rules
- duplicate-run/idempotency convention for POST routes
- secret redaction validator baseline with fixtures and denylist/allowlist update path
- local deterministic preflight checklist
- P0/P1/P2 review evidence template for phase exits
- Godot UI capability contract template at `docs/standards/godot-ui-capability-contract.md`, `docs/standards/_index.md` link, contract version/hash rule, canonical hash exclusion list, and technology-stack leakage denylist
- Godot diagnostics and quality-gate contract template at `docs/standards/godot-diagnostics-quality-gates.md`, `docs/standards/_index.md` link, failure-family taxonomy, project diagnostic spool schema, symptom-to-remediation table seed, debug-log lifecycle rule, interaction-region artifact rule, preview validation rule, and resource lifecycle/orphan diagnostics rule

Exit criteria:

- New readback surfaces cannot be implemented until the path/readback policy exists and names normal-user, admin, prompt evidence, package, and preview/download path behavior.
- New route actions cannot be implemented until exposure class, account/auth boundary, and duplicate-run behavior are documented in the route action descriptor.
- New prompt/evidence persistence cannot be implemented until the secret redaction validator baseline passes fixture-based tests.
- New UI-touching route work cannot be implemented until the Godot UI capability contract template exists and the denylist proves prompts do not import TapTap-only runtime terms.
- New build, preview, package, repair, UI closure, or project-delete route work cannot be implemented until the Godot diagnostics and quality-gate contract template exists and defines pre-build/pre-preview diagnostics, diagnostic spool ownership, and failure-family taxonomy.
- The Godot UI capability contract template must be linked from `docs/standards/_index.md` before Phase 0 is accepted.
- The Godot diagnostics and quality-gate contract template must be linked from `docs/standards/_index.md` before Phase 0 is accepted.
- When the Godot diagnostics and quality-gate contract becomes a durable standards file, Phase 0 must also update `README.md`, `docs/PROJECT_DOCUMENTATION_INDEX.md`, relevant Phase service architecture indexes, and agent-facing routing where applicable, matching the standards index maintenance rule.
- The Phase 0 failure-family taxonomy seed must cover every initial symptom family listed in section 11.3.4 before later route phases add more route-specific families.
- The Godot UI capability contract template must declare its canonical hash exclusions; an empty exclusion list is valid, but an implicit or undocumented exclusion list is not.
- The phase exit review template records route, artifact, API, browser surface, script, evidence, reviewer, and unresolved P0/P1/P2 count.
- Phase exit review evidence is written as a durable artifact under `logs/` and referenced by the implementation summary; chat text or PR prose alone is not sufficient evidence.
- Phase 0 review records zero unresolved P0/P1/P2 findings.

### Phase 1: Requirement Map And Contract Freshness

Deliverables:

- `GameDesignRequirementMapService`
- requirement map API/readback
- prototype contract hash fields
- contract stale detection
- frontend requirement map panel
- first route module contracts for `gdd-requirements` and `prototype-contract`
- first guard tests for source hashes, stale behavior, sidecar naming, operation status, and error envelope shape
- path/readback tests for requirement map and prototype contract readback
- exposure-class and account-boundary tests for requirement map/freeze actions
- duplicate-run tests for requirement map generation and contract freeze
- requirement-map classification for Godot UI capability domains and prototype-contract freeze of the Godot UI contract hash
- first failure-family taxonomy entries for GDD, scene route, requirement map, contract stale, source unknown, and UI contract unknown
- route-specific expansion of the Phase 0 taxonomy seed for the first implemented `gdd-requirements` and `prototype-contract` slices

Exit criteria:

- New deckbuilder project can generate requirement map and freeze a fresh contract.
- Stale GDD blocks new iteration plan.
- Requirement map and contract sidecars use snake_case locally while API/readback exposes camelCase.
- Tests for requirement map and contract freshness pass.
- Normal-user requirement map and prototype contract readback do not expose host paths, cross-account state, raw prompts, token material, or admin-only evidence.
- Requirement map generation and contract freeze handle double-click/retry/concurrent POST behavior without creating conflicting active runs.
- Requirement map and frozen contract preserve Godot UI capability domain inputs for UI/HUD/input/custom drawing/camera/animation/rendering/procedural/geometry/typed-state requirements.
- GDD, scene route, requirement map, and contract freshness failures map to failure-family taxonomy entries and project diagnostic spool records where applicable.
- Phase 1 may add route-specific failure families, but it must not shrink or redefine the Phase 0 initial symptom-family taxonomy.
- Route contracts and guard tests for `gdd-requirements` and `prototype-contract` pass the P0/P1/P2 acceptance severity standard.

### Phase 2: Iteration Plan Traceability Gate

Deliverables:

- iteration goals include requirement IDs
- required modules include requirement IDs and source reasons
- module plan confirmation UI
- block module generation on P0/P1 coverage gaps
- iteration-plan route contract and route action descriptor updates
- UI surface goals generated from the Godot UI capability contract
- interaction-region artifact requirement for UI/input/physics/camera-heavy iteration goals

Exit criteria:

- Every P0/P1 requirement is covered by plan or explicit blocker.
- Frontend module plan shows traceability.
- Deckbuilder default modules are visible as required modules with source.
- Every P0/P1 UI-facing requirement has an iteration goal or required module that names expected Godot UI surface, layout/input/focus/feedback requirements, and validation method.
- UI/input/physics/camera-heavy P0/P1 goals include interaction-region artifacts or explicit `no_interaction_region_needed` rationales before execution.
- Iteration-plan service/API/readback and module confirmation UI pass Phase 0 route governance checks for route action descriptor, path/readback policy, exposure class, account boundary, duplicate-run behavior, `active_run_reused` response shape, source-boundary evidence, and secret redaction.
- Phase 2 review records zero unresolved P0/P1/P2 findings.

### Phase 3: Workflow Recommendation

Deliverables:

- workflow recommendation service/API
- frontend primary action driven by recommendation
- stale/blocking issue banners

Exit criteria:

- User sees one clear primary next step.
- Forbidden actions are disabled with reason.
- Existing advanced actions remain available only when route descriptors classify them as user-visible or safe secondary actions.
- Workflow recommendation extends or reads from the existing workflow route authority instead of introducing a competing next-action engine.
- Recommendation actions are checked against the route action descriptor and exposure classes so the frontend cannot recommend an admin-only, script-only, stale, or missing action to a normal user.
- Phase 3 review records zero unresolved P0/P1/P2 findings.

### Phase 4: Execute Goal Freshness And Needs-Fix Tightening

Deliverables:

- execute-next-goal stale/missing guards
- requirement rows in goal input
- needs-fix reads requirement map and latest blocker
- frozen Godot UI capability contract injection for UI-touching goals
- UI gap family mapping in needs-fix and repair prompts
- pre-build diagnostics gate and debug-log lifecycle checks for execute-next-goal, needs-fix, and repair

Exit criteria:

- Codex is not invoked when contract/map is stale.
- Codex is not invoked for build/repair/UI-touching work when required pre-build diagnostics fail or diagnostic prerequisites are missing.
- Goal execution prompt contains linked requirements.
- UI-touching goal prompts contain the frozen Godot UI capability contract and pass technology-stack leakage tests.
- Failed acceptance maps back to a requirement or UI closure gap where possible.
- Needs-fix and repair can classify UI failures as layout, input/focus, feedback, custom drawing, camera/layer, rendering/material, animation, geometry sizing, procedural visualization, or typed state gaps.
- Failed execute/needs-fix/repair runs write sanitized project diagnostic spool records for known failure families.
- Execute-next-goal and needs-fix prompt/evidence artifacts pass source-boundary checks and secret redaction validator checks before the route is accepted.
- Phase 4 review records zero unresolved P0/P1/P2 findings.

### Phase 5: UI Wiring Closure

Deliverables:

- UI closure service/API/readback
- UI surface matrix
- UI closure panel
- optional follow-up goal generation
- Godot UI capability validator for scene/node path, layout, input/focus, feedback, camera/layer, custom drawing, material/rendering, animation, geometry sizing, procedural visualization, and typed state
- preview validation loop, visual evidence, source-hash readiness, and resource lifecycle/orphan diagnostics for UI closure follow-up work

Exit criteria:

- Completed gameplay modules are checked for player-facing UI exposure.
- Missing UI surfaces are visible and actionable.
- UI closure validates Godot-specific capability fields and gap families instead of only checking that a named UI surface exists.
- Follow-up goals preserve requirement IDs, Godot UI capability domain, validation method, and source hashes.
- Final package readiness can show UI closure blockers.
- UI closure and preview readiness cannot pass when diagnostics evidence, visual evidence, source hash set, lifecycle cleanup, or orphan diagnostics are missing for routes that require them.
- UI closure service/API/readback passes Phase 0 route governance checks for path/readback policy, exposure class, account boundary, duplicate-run behavior, `active_run_reused` response shape, and secret redaction.
- Phase 5 review records zero unresolved P0/P1/P2 findings.

### Phase 6: Route Governance Guardrails

Phase 6 is a consolidation and expansion pass. It must not re-litigate or defer the Phase 0 baseline. It expands the already-created route governance primitives to every remaining route, admin script, readback surface, and durable standards document.

Deliverables:

- route module contracts for all remaining prototype routes
- deterministic guard tests for route/action/status/source-boundary invariants across all covered routes
- expanded Phase path/readback policy coverage for admin scripts, package/preview/download, and prompt evidence
- admin/backfill script evidence conventions
- runtime lifecycle and orphan-process diagnostic guidance
- capability allowlist coverage for all user/admin/script/internal route actions
- context-boundary and DTO hygiene tests for all browser-consumed route services
- long-running progress/readback convention coverage for remaining routes
- idempotent recovery and duplicate-run control coverage for remaining POST routes
- credential/secret redaction validator coverage for scripts, admin exports, and newly persisted evidence families
- configuration/environment preflight checklist coverage for every route dependency introduced by Phases 1-5
- docs index links for durable route governance rules
- Godot UI capability contract coverage across route contracts, tests, admin readback, and durable standards docs
- Godot diagnostics and quality-gate contract coverage across route contracts, diagnostics guide, failure taxonomy, project diagnostic spool, admin triage, preview/package, resource lifecycle, and durable standards docs

Exit criteria:

- `gdd-requirements`, `prototype-contract`, `workflow-recommendation`, `iteration-plan`, `execute-next-goal`, `needs-fix`, `repair`, and `ui-wiring-closure` have route module contracts, route action descriptors, exposure classes, and guard-test coverage.
- `preview-package` routes are covered by Phase path/readback, capability exposure, account-boundary, package/preview/download reference, and host-path leakage tests; they do not need full route module contracts in this plan unless their behavior is changed beyond readback/package/preview/download governance.
- Guard tests fail when action names, status enums, source hash fields, error envelope shape, or source-boundary prompt rules drift.
- Path/readback tests prove normal users do not see host paths or cross-account admin review queue entries.
- Admin/backfill scripts produce append-only evidence under `logs/` with scoped IDs and sanitized paths.
- Runtime lifecycle guidance distinguishes expected process exits from crashes.
- Capability exposure tests prove normal users cannot invoke admin/script-only route actions by direct API call.
- Context-boundary tests prove client payload fields cannot spoof account/project/source/admin authority.
- Duplicate-run tests cover retry, double-click, and concurrent POST behavior for the main route actions.
- Secret redaction validators pass over route prompts, evidence, admin exports, and script evidence.
- Preflight checks report missing local dependencies without starting a workflow run.
- Godot UI capability contract is linked from durable docs, covered by guard tests, and consumed by `gdd-requirements`, `prototype-contract`, `iteration-plan`, `execute-next-goal`, `needs-fix`, `repair`, and `ui-wiring-closure`.
- Godot diagnostics and quality-gate contract is linked from durable docs, covered by guard tests, and consumed by build/validation, execute-next-goal, needs-fix, repair, UI closure, preview/package, and project-delete diagnostics.
- Project diagnostic spool supports deleted-project admin lookup, triage status, redaction status, retention class, and unresolved P0/P1/P2 preservation.
- Durable route governance docs are linked from the relevant standards or workflow index.
- Phase 6 evidence proves each Phase 0 baseline primitive was reused and expanded, not duplicated as a competing contract.
- Phase 6 review records zero unresolved P0/P1/P2 findings.

## 13. Risks And Mitigations

| Risk | Mitigation | Acceptance |
| --- | --- | --- |
| Too many new stages overwhelm users | Use recommendation-driven primary action; hide advanced controls | User always sees one recommended next action |
| LLM requirement map misses details | Add coverage validation and needs-review fallback | Empty map is invalid unless GDD has no requirements |
| Contract stale blocks old users unexpectedly | Treat legacy as unknown; allow explicit refresh; allow continue only for old hash-bound sessions/goals | Existing preview/package still works; new execution from unknown-source legacy plans remains blocked |
| Too much strictness slows prototype creation | Enforce P0/P1 as runtime blockers by default; allow P2 to be advisory for ordinary user execution only when it is tracked under the acceptance severity standard | Fast path remains usable, and implementation acceptance still has zero unresolved P0/P1/P2 findings |
| UI closure delays early playability | UI closure is a late-stage gate, not a skeleton gate | Prototype creation does not require UI closure |
| Formatting-only GDD changes cause hash churn | Normalize text before hashing or classify as advisory stale | Formatting-only changes can avoid hard stale if normalized hash is unchanged |
| Borrowed TapTap patterns are copied too literally | Adapt boundary and guard patterns only; keep Phase A C# service architecture | No TypeScript/MCP feature layout is required for Phase A |
| Guard tests become brittle string snapshots | Guard only stable names, enums, source-boundary markers, and contract fields | Tests fail on real contract drift, not harmless copy changes |
| Admin scripts become hidden mutation paths | Require explicit admin intent, idempotency notes, and append-only evidence | Browser user flows remain decision-focused and bulk maintenance stays auditable |
| Capability allowlist hides needed user recovery actions | Route descriptors separate safe secondary actions from admin/script-only actions | User can still recover through visible safe actions while dangerous maintenance stays gated |
| Context boundary rules duplicate existing service authorization | Treat context rules as tests over existing authorization/readback boundaries, not a second auth system | Tests prove server-derived context wins without adding competing auth logic |
| Progress states become optimistic and mask failed runs | Success requires validated sidecar/readback artifact, not only process exit | Browser never shows success for a missing or invalid route artifact |
| Preflight checks become a new dependency on external services | Keep preflight local and deterministic unless admin explicitly requests external probes | Preflight failures are actionable without Steam/LLM/network availability |
| Secret validators produce false confidence | Combine variable-name denylist, token-like pattern scan, and route-specific redaction tests | Prompt/evidence/admin export samples pass redaction tests before acceptance |
| Godot UI capability contract becomes too broad to implement | Phase-gate the contract: Phase 0 defines it, Phase 1 freezes/classifies it, Phase 2 plans from it, Phase 4 injects it, Phase 5 validates it | No phase claims completion for a touched UI domain without tests/evidence and zero unresolved P0/P1/P2 findings |
| UI capability migration accidentally imports TapTap technology | Keep TapTap-only terms in conflict assessment only and add prompt/evidence denylist tests | Route prompts, sidecars, UI closure output, and durable standards contain Godot-only implementation terms |
| UI closure produces generic "missing UI" items that are not actionable | Use gap families and required Godot fields in `ui_surface_matrix` | Each UI closure blocker names requirement IDs, scene/node or missing owner, gap family, and follow-up validation method |
| Visual validation becomes impossible in headless runs | Use layered evidence: route-state validators first, Godot headless/screenshot/canvas-pixel/exported visual evidence for high-risk visual changes, and a recorded deterministic substitute only when the harness limitation is concrete | High-risk visual UI changes include machine-checkable evidence or a documented test-harness limitation that is reviewed as P0/P1/P2 |
| Godot UI contract conflicts with the non-goal of not refactoring the generator | Keep this plan at workflow contract, prompt, validation, and readback level; generator internals change only when later implementation explicitly scopes them | Acceptance can be met by route contracts and generated goals without requiring a generator architecture rewrite in this plan |
| Diagnostics gate slows iteration | Run diagnostics at route boundaries and reuse current source hashes instead of rerunning unchanged checks | Routes block only on changed or stale diagnostic scope, and accepted phases still record zero unresolved P0/P1/P2 findings |
| Project diagnostic spool leaks private evidence | Store spool outside workspaces with redaction status, account ownership, admin-only raw access, and user-safe summaries | Normal-user readback cannot expose cross-account diagnostics, raw host paths, raw prompts, token material, provider secrets, or admin-only evidence |
| Project deletion accidentally removes diagnostics | Keep diagnostic spool outside hosted workspaces and make deletion cleanup ignore preserved diagnostics | Deleted-project admin lookup still finds unresolved diagnostics, and unresolved P0/P1/P2 records survive ordinary project deletion |
| Symptom table becomes stale documentation | Treat failure-family taxonomy and remediation table as tested route contract inputs | New known failure families cannot ship without a table row, domain code, user-safe summary policy, and test coverage |
| Temporary debug logs become permanent acceptance evidence | Require debug-log lifecycle checks and sanitized evidence replacement before acceptance | No changed route can pass with temporary stdout/print output as the only evidence |
| Interaction-region artifacts become busywork | Require them only for UI/input/physics/camera-heavy P0/P1 goals and allow structured alternatives to ASCII | Deckbuilder route-map and hand-dragging goals have useful hit-zone/collision artifacts, not decorative documentation |

## 14. Definition Of Done

This refactor is done when:

1. A new project can complete the full stage flow from GDD form to package with visible stage statuses.
2. GDD requirements are represented in `gdd-requirements/latest.json` with coverage status.
3. `prototype-contract/latest.json` records source hashes and stale status can be read back.
4. Iteration goals and required modules trace back to GDD requirements or explicit default contract reasons.
5. Execute-next-goal refuses stale/missing source state before invoking Codex.
6. Frontend primary action is recommendation-driven.
7. UI closure identifies missing player-facing surfaces for completed P0/P1 capabilities.
8. Tests and smoke evidence cover the deckbuilder reference path.
9. No existing public/browser API field is removed or renamed.
10. Route module contracts and deterministic guard tests cover action names, status enums, source hashes, error envelope shape, and source-boundary prompt rules.
11. Phase path/readback policy prevents normal-user host path leakage and cross-account evidence leakage.
12. Admin/backfill operations are scriptable, auditable, and evidence-backed without bypassing user-facing decision flows.
13. Runtime lifecycle guidance distinguishes expected exits, failures, preserved evidence, and orphan-process diagnostics.
14. Capability exposure classes, context-boundary tests, progress/readback states, duplicate-run controls, secret redaction, and local preflight checks are implemented for the routes touched by each phase.
15. Durable TapTap-derived governance rules are moved or linked into the relevant standards/workflow docs before implementation is called complete.
16. The final review records zero unresolved P0, P1, or P2 findings under the acceptance severity standard.
17. No service restart is required as part of writing this plan.
18. The Godot UI capability contract is frozen into prototype contracts, consumed by requirement map, iteration plan, execute-next-goal, needs-fix/repair, and UI closure, and exposed through account-safe readback.
19. P0/P1 player-facing requirements cannot complete final readiness without UI surface, layout/input/focus/feedback/camera-layer/state evidence or an explicit `no_ui_needed` rationale.
20. Godot UI capability tests prove no TapTap runtime technology is required or leaked into executable route prompts and artifacts.
21. The Godot diagnostics and quality-gate contract is linked from durable docs, consumed by build/validation, execute-next-goal, needs-fix, repair, UI closure, preview/package, and project-delete diagnostics, and covered by guard tests.
22. Project diagnostic spool preserves unresolved P0/P1/P2 diagnostics outside hosted workspaces, supports deleted-project admin lookup and triage, and protects normal users from raw or cross-account evidence.
23. Preview/package readiness, resource lifecycle cleanup, orphan diagnostics, interaction-region artifacts, and symptom-to-remediation table coverage are validated before final readiness.

## 15. Open Questions For Later Phases

These are product/design decisions intentionally scoped out of the first implementation slice. They are not accepted P2 defects. If any item becomes a discovered implementation issue, it must be reclassified under the P0/P1/P2 acceptance severity standard with owner, scope, and proof.

| Question | Owner | Scope | Current proof that Phase 1 is not blocked |
| --- | --- | --- | --- |
| After Phase 1, should users be allowed to manually edit requirement map rows, or should edits continue to happen only by changing GDD/scene route and regenerating? | Product + Phase A platform | Requirement map editing UX and audit policy | Phase 1 default forbids normal-user direct edits and requires regeneration from GDD/scene route, so no unowned edit path exists. |
| After Phase 1, should `contract_stale` block execute-next-goal for all statuses, or allow broader continuation of already-running sessions with an explicit warning? | Phase A platform | Execute-next-goal stale handling beyond hash-bound continuations | Phase 1 default blocks new execution from stale/unknown sources and allows continuation only when goal/session hashes match the original source set. |
| After Phase 1, should UI closure become mandatory before package download or remain limited to "final package" readiness labeling? | Product + Phase A platform | Package readiness policy | Phase 1 default keeps early package download non-blocking while preserving final readiness blockers, so playable prototype creation remains recoverable. |
| After Phase 1, should requirement map generation remain hybrid deterministic + structured LLM, or move toward a fully deterministic/fully LLM-based approach? | Phase A platform | Requirement extraction architecture | Phase 1 default uses deterministic source collection/validation plus structured LLM and deterministic fallback, so invalid or empty LLM output fails closed. |
| After Phase 1, should source hash normalization ignore more than whitespace-only Markdown changes, such as heading punctuation or table formatting? | Phase A platform | Hash canonicalization policy | Phase 1 minimum canonicalization handles line endings and trailing whitespace while retaining raw diagnostic hashes, so stale decisions stay explainable. |

## 15.1 Phase 1 Default Decisions

These defaults apply to the first implementation slice so Phase 1 can proceed without resolving every open question:

1. Requirement map rows are not directly editable by normal users in Phase 1. Users change GDD or scene route and regenerate the map. Admin-only defer/conflict decisions are allowed when they include the structured audit fields defined above.
2. `contract_stale` blocks new iteration plan creation by default. Continuing an old session is allowed only when the session/goal source hashes match the contract and requirement map that were current when the session was created. Missing hashes are `source_unknown` and block new-project execution.
3. UI closure is not required for early prototype creation or ordinary package download in Phase 1. It affects final readiness labeling and can become a hard final-package gate in a later product decision.
4. Requirement map generation starts as hybrid deterministic + structured LLM: deterministic source collection and validation, structured LLM mapping, deterministic fallback to `needs_review` rows.
5. Source hashes use normalized Markdown/text content for Markdown and text artifacts to avoid whitespace-only churn. Minimum canonicalization is: normalize line endings to `\n`, trim trailing whitespace, preserve heading text, preserve table cell content, and optionally exclude known volatile frontmatter fields such as `updatedUtc`. JSON/schema contracts, including the Godot UI capability contract, use deterministic canonical JSON ordering and exclude documented volatile fields before hashing. Route-state and evidence-reference source hashes use deterministic canonical JSON ordering, sorted evidence refs, and exclude volatile timestamps, process IDs, request IDs, and run IDs unless a field is explicitly declared part of source identity. The Godot UI capability contract template at `docs/standards/godot-ui-capability-contract.md` must declare its canonical hash exclusion list; an empty exclusion list is valid. Raw hash can be retained as diagnostic metadata if needed.

Acceptance criteria:

- Phase 1 implementation follows these defaults unless a newer decision log supersedes them.
- Frontend copy and API errors reflect these defaults.
- Tests cover the default decisions for map editability, stale blocking, and UI closure non-blocking package behavior.

## 16. Recommended First Implementation Slice

Start with Phase 0, then the smallest Phase 1 slice. Phase 1 work must not begin until Phase 0 exit criteria pass.

1. Add Phase 0 route module contract template and route action descriptor baseline.
2. Add Phase 0 path/readback policy, action exposure classes, context-boundary rules, and account-boundary guard tests.
3. Add Phase 0 duplicate-run/idempotency convention, `active_run_reused` response contract, and local preflight checklist.
4. Add Phase 0 secret redaction validator baseline, fixture coverage, and phase review evidence template.
5. Add Phase 0 Godot UI capability contract template at `docs/standards/godot-ui-capability-contract.md`, `docs/standards/_index.md` link, version/hash rule, canonical hash exclusion list, technology-stack leakage denylist, and initial guard fixtures.
6. Add Phase 0 Godot diagnostics and quality-gate contract template at `docs/standards/godot-diagnostics-quality-gates.md`, `docs/standards/_index.md` link, `README.md`, `docs/PROJECT_DOCUMENTATION_INDEX.md`, relevant Phase service architecture indexes, agent-facing routing where applicable, failure-family taxonomy seed, project diagnostic spool schema, symptom-to-remediation table seed, debug-log lifecycle rule, interaction-region artifact rule, preview validation rule, resource lifecycle/orphan diagnostics rule, and initial guard fixtures.
7. Add Phase 0 durable review evidence under `logs/`.
8. Add `GameDesignRequirementMapService`.
9. Add requirement map API/readback.
10. Add artifact-local `contract_hash`, `source_gdd_hash`, `source_scene_route_hash`, `source_requirement_map_hash`, `source_contract_snapshot_hash`, and `source_godot_ui_contract_hash`, with readback/API projections `contractHash`, `sourceGddHash`, `sourceSceneRouteHash`, `sourceRequirementMapHash`, `sourceContractSnapshotHash`, and `sourceGodotUiContractHash`.
11. Add artifact-local Godot UI capability contract version and readback/API projection `godotUiContractVersion`.
12. Add stale detection and frontend banner.
13. Apply the route module contract template to `gdd-requirements` and `prototype-contract`.
14. Add guard tests for sidecar naming, source hash fields, Godot UI contract hash fields, diagnostic failure-family fields, action names, error envelope shape, path/readback, exposure class, account boundary, duplicate-run behavior, and secret redaction fixture coverage.
15. Add tests for deckbuilder GDD -> requirement map -> fresh contract, including route-map UI, hand drag/drop, combat HUD feedback, reward selection UI, Godot-only UI capability classification, and interaction-region artifact coverage.

This first slice gives the largest drift reduction with the least UI disruption.
