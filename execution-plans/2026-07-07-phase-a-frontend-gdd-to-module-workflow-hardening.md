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

## 3. Non-Goals

1. Do not copy Taskmaster triplets, overlays, or the formal Chapter 6 pipeline directly into frontend projects.
2. Do not force old projects through a destructive migration. Old projects should be lazily backfilled or shown as missing the new artifacts.
3. Do not allow downstream workflows to freely reread `docs/game-type-guides` as a new gameplay authority after GDD generation.
4. Do not silently refresh confirmed contracts. When GDD or scene route changes, prompt for explicit user confirmation.
5. Do not refactor the Godot generator itself in this plan. This plan focuses on inputs, contracts, module planning, workflow state, and frontend governance.

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
   - The system freezes the prototype contract and records artifact-local source hashes (`source_gdd_hash`, `source_scene_route_hash`, `source_requirement_map_hash`, `source_contract_snapshot_hash`) with camelCase API/readback projections.
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
- If `docs/gdd/GDD.md`, scene route, requirement map, or contract snapshot changes, readback reports the contract as `stale`.
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
  "status": "ready|needs_fix|succeeded|blocked",
  "readiness_scope": "ui_wiring_closure",
  "status_reason": "",
  "updated_utc": "...",
  "evidence_refs": [],
  "player_flows": [],
  "ui_surface_matrix": [
    {
      "feature": "route_map_path_selection",
      "source_requirement_ids": ["REQ-001"],
      "source_goal_ids": [],
      "ui_surface": "RouteMapView",
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

## 6. Backend Changes

### 6.1 New Service: `GameDesignRequirementMapService`

Responsibilities:

- Read `docs/gdd/GDD.md`.
- Read confirmed scene route state.
- Read project `contractSnapshot` and game-type default required modules.
- Generate `gdd-requirements/latest.json` through structured LLM output or deterministic fallback.
- Validate coverage and status.
- Persist route state and mirror it if needed.

Acceptance criteria:

- Service returns stable JSON with deterministic IDs (`REQ-001`, `REQ-002`, ...).
- Service fails closed when GDD is missing, scene route is missing, or returned requirement map JSON is invalid.
- Service produces fallback `needs_review` rows instead of silently returning an empty requirement set.
- Unit tests cover successful map generation, invalid LLM JSON fallback, missing sources, and default module preservation.

### 6.2 New/Extended Service: `PrototypeContractFreezeService`

Responsibilities:

- Freeze or refresh `prototype-contract/latest.json` from GDD, scene route, requirement map, contract snapshot, and current request fields.
- Add source hashes and traceability.
- Detect stale contract state.

Acceptance criteria:

- Freeze writes a contract with all source hashes.
- Re-freezing unchanged sources is idempotent except `updated_utc`/`updatedUtc` if policy requires updating it.
- Changed GDD or scene route marks the previous contract stale.
- Freezing does not run Steam lookup or rematch game type.
- Existing `PrototypeContractService` remains backward compatible.

### 6.3 Extend `PrototypeIterationPlanService`

Responsibilities:

- Read requirement map as first-class input.
- Generate goals from requirement rows and required modules.
- Include `requirementIds` in every goal and every `required_modules` entry.
- Block if P0/P1 requirements are unmapped or contract is stale.

Acceptance criteria:

- Every generated goal includes at least one `requirementId` or an explicit infrastructure reason.
- Every P0 requirement is covered by a goal, required module, prototype skeleton, or explicit blocker.
- `required_modules` retains deckbuilder route-map and hand-dragging defaults and adds requirement links.
- If `route_map_path_selection` is required, it appears in `required_modules` as a separate block, not only as a vague goal title.
- Tests cover deckbuilder, RPG, generic fallback, stale contract, missing map, and admin-approved GDD conflict suppression.
- The iteration plan route state must record `sourceGddHash`, `sourceSceneRouteHash`, `sourceRequirementMapHash`, `sourceContractHash`, and `sourceContractSnapshotHash`.
- Every generated goal must record the same source hash set or a `sourceHashRef` that points to the session-level hash set.
- Stale checks must compare execute-next-goal source hashes against the current frozen contract and requirement map before invoking Codex.

### 6.4 Extend `PrototypeIterationGoalService`

Responsibilities:

- Include requirement rows linked to the current goal in the prompt.
- Include contract freshness metadata.
- Refuse executing goals whose source contract/hash does not match the current frozen contract, unless the repair route explicitly allows continuation.

Acceptance criteria:

- Goal input markdown contains `Requirement IDs` and source excerpts.
- Prompt states that the current goal must not expand beyond linked requirements.
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
   - Idempotency: if the source iteration session and validation inputs match the latest closure state, return the existing state; if closure is already running, return the active run/state; otherwise create one closure run.
7. `GET /api/projects/{projectId}/ui-wiring-closure/latest`
   - Read latest UI closure state.

Acceptance criteria:

- All project-scoped routes enforce account ownership.
- Admin-only data remains behind `/api/admin/...`.
- Responses are additive only; no existing route response field is removed or renamed.
- POST API responses include an explicit `operationStatus` (`returned_existing|active_run_reused|created_run|rejected`) plus either a stable route state, an active `runId`, or an `evidenceRefs` pointer that can be read by a GET route; artifact-local sidecars keep the snake_case `evidence_refs` field.
- If operation status is ever persisted in an artifact-local sidecar, it must use `operation_status`; `operationStatus` is reserved for API/readback DTOs.
- `operationStatus=rejected` responses must include the standard error envelope with `requestId` and optional `details.domainCode`.
- `evidenceRefs.kind` / `evidence_refs.kind` uses the Phase standard closed enum: `log|artifact|sidecar|screenshot|db_row|smoke|validator`, unless the standards document is updated first.
- POST responses and generated evidence preserve `requestId`/`correlationId` when the request starts or resumes a run.
- Error envelope `code` values follow Phase standard preferred codes; route-specific business reasons are carried in `details.domainCode`.
- Error status mapping is stable:

  | HTTP status | Envelope `code` | `details.domainCode` examples |
  | --- | --- | --- |
  | `404` | `gdd_not_found`, `scene_route_missing`, `contract_missing`, `requirement_map_missing` only when the caller is allowed to know absence |
  | `409` | `conflict` | `contract_stale`, `iteration_plan_blocked`, `duplicate_active_run` |
  | `422` | `route_state_invalid` | `requirement_map_invalid`, `ui_closure_not_ready` |
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

## 9. Migration And Compatibility

1. Existing projects without requirement map:
   - Show `requirement_map_missing`, but allow lazy generation.
2. Existing prototype contracts without source hashes:
   - Treat freshness as `unknown`.
   - Prompt user to freeze/refresh contract before creating new module plans.
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

### 10.2 Integration / Smoke Tests

Add a deterministic smoke path for:

1. Create project.
2. Generate GDD question form.
3. Confirm scene route.
4. Generate GDD.
5. Generate requirement map.
6. Freeze contract.
7. Generate iteration plan.
8. Execute or dry-run next-goal decision.

Acceptance criteria:

- Smoke writes evidence under `logs/`.
- Smoke asserts route state files exist and contain matching hashes.
- Smoke asserts no downstream route reads broad game-type guide as authority after contract freeze.
- Smoke/test assertions define this concretely: execute-next-goal, needs-fix, repair, and UI closure prompts may include `source_boundary` and artifact paths, but must not include raw `docs/game-type-guides` guide excerpts or use guide-derived requirements that are absent from the frozen contract/requirement map.
- Smoke/test assertions read the saved prompt or run evidence artifact, not only the route-state summary field, when checking source-boundary behavior.
- Route state should record `source_boundary_enforced: true` when the prompt was built from frozen project artifacts only.

### 10.3 Browser Tests

Acceptance criteria:

- Embedded scripts remain syntactically valid.
- Stage timeline renders missing, stale, completed, and blocked states.
- Requirement map table renders empty, loaded, gap, and stale states.
- Contract freshness banner displays the correct action.
- Primary button follows `workflow-recommendation`.

## 11. Observability And Admin

Add admin/readback visibility for:

- Requirement map status and gap counts.
- Contract freshness status.
- Stale artifact reasons.
- Current recommended action.
- UI closure status.
- Repeated failure families from needs-fix/validation.

Acceptance criteria:

- Admin can answer "Why can this project not generate modules right now?" without reading raw logs.
- Admin can answer "Which GDD requirements did not enter the module plan?" from UI/readback.
- Admin can answer "Which GDD, scene route, and contract snapshot hash produced this prototype contract?" from UI/readback.
- User-facing readback remains account-scoped and cannot expose another account's project route state by guessed IDs.
- Admin aggregation may cross accounts, but raw evidence blobs, host paths, prompts, token material, and provider secrets remain redacted or omitted.
- Browser/API responses that expose project workflow state, route evidence, or admin audit details use `Cache-Control: no-store` unless a specific compatibility exception is recorded.

## 12. Implementation Phases

### Phase 1: Requirement Map And Contract Freshness

Deliverables:

- `GameDesignRequirementMapService`
- requirement map API/readback
- prototype contract hash fields
- contract stale detection
- frontend requirement map panel

Exit criteria:

- New deckbuilder project can generate requirement map and freeze a fresh contract.
- Stale GDD blocks new iteration plan.
- Requirement map and contract sidecars use snake_case locally while API/readback exposes camelCase.
- Tests for requirement map and contract freshness pass.

### Phase 2: Iteration Plan Traceability Gate

Deliverables:

- iteration goals include requirement IDs
- required modules include requirement IDs and source reasons
- module plan confirmation UI
- block module generation on P0/P1 coverage gaps

Exit criteria:

- Every P0/P1 requirement is covered by plan or explicit blocker.
- Frontend module plan shows traceability.
- Deckbuilder default modules are visible as required modules with source.

### Phase 3: Workflow Recommendation

Deliverables:

- workflow recommendation service/API
- frontend primary action driven by recommendation
- stale/blocking issue banners

Exit criteria:

- User sees one clear primary next step.
- Forbidden actions are disabled with reason.
- Existing advanced actions remain available where safe.
- Workflow recommendation extends or reads from the existing workflow route authority instead of introducing a competing next-action engine.

### Phase 4: Execute Goal Freshness And Needs-Fix Tightening

Deliverables:

- execute-next-goal stale/missing guards
- requirement rows in goal input
- needs-fix reads requirement map and latest blocker

Exit criteria:

- Codex is not invoked when contract/map is stale.
- Goal execution prompt contains linked requirements.
- Failed acceptance maps back to a requirement or UI closure gap where possible.

### Phase 5: UI Wiring Closure

Deliverables:

- UI closure service/API/readback
- UI surface matrix
- UI closure panel
- optional follow-up goal generation

Exit criteria:

- Completed gameplay modules are checked for player-facing UI exposure.
- Missing UI surfaces are visible and actionable.
- Final package readiness can show UI closure blockers.

## 13. Risks And Mitigations

| Risk | Mitigation | Acceptance |
| --- | --- | --- |
| Too many new stages overwhelm users | Use recommendation-driven primary action; hide advanced controls | User always sees one recommended next action |
| LLM requirement map misses details | Add coverage validation and needs-review fallback | Empty map is invalid unless GDD has no requirements |
| Contract stale blocks old users unexpectedly | Treat legacy as unknown; allow explicit refresh; allow continue only for old hash-bound sessions/goals | Existing preview/package still works; new execution from unknown-source legacy plans remains blocked |
| Too much strictness slows prototype creation | Enforce P0/P1 only by default; keep P2 advisory | Fast path remains usable |
| UI closure delays early playability | UI closure is a late-stage gate, not a skeleton gate | Prototype creation does not require UI closure |
| Formatting-only GDD changes cause hash churn | Normalize text before hashing or classify as advisory stale | Formatting-only changes can avoid hard stale if normalized hash is unchanged |

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
10. No service restart is required as part of writing this plan.

## 15. Open Questions For Later Phases

1. After Phase 1, should users be allowed to manually edit requirement map rows, or should edits continue to happen only by changing GDD/scene route and regenerating?
2. After Phase 1, should `contract_stale` block execute-next-goal for all statuses, or allow broader continuation of already-running sessions with an explicit warning?
3. After Phase 1, should UI closure become mandatory before package download or remain limited to "final package" readiness labeling?
4. After Phase 1, should requirement map generation remain hybrid deterministic + structured LLM, or move toward a fully deterministic/fully LLM-based approach?
5. After Phase 1, should source hash normalization ignore more than whitespace-only Markdown changes, such as heading punctuation or table formatting?

## 15.1 Phase 1 Default Decisions

These defaults apply to the first implementation slice so Phase 1 can proceed without resolving every open question:

1. Requirement map rows are not directly editable by normal users in Phase 1. Users change GDD or scene route and regenerate the map. Admin-only defer/conflict decisions are allowed when they include the structured audit fields defined above.
2. `contract_stale` blocks new iteration plan creation by default. Continuing an old session is allowed only when the session/goal source hashes match the contract and requirement map that were current when the session was created. Missing hashes are `source_unknown` and block new-project execution.
3. UI closure is not required for early prototype creation or ordinary package download in Phase 1. It affects final readiness labeling and can become a hard final-package gate in a later product decision.
4. Requirement map generation starts as hybrid deterministic + structured LLM: deterministic source collection and validation, structured LLM mapping, deterministic fallback to `needs_review` rows.
5. Source hashes should use normalized Markdown/text content where practical to avoid whitespace-only churn. Minimum canonicalization is: normalize line endings to `\n`, trim trailing whitespace, preserve heading text, preserve table cell content, and optionally exclude known volatile frontmatter fields such as `updatedUtc`. Raw hash can be retained as diagnostic metadata if needed.

Acceptance criteria:

- Phase 1 implementation follows these defaults unless a newer decision log supersedes them.
- Frontend copy and API errors reflect these defaults.
- Tests cover the default decisions for map editability, stale blocking, and UI closure non-blocking package behavior.

## 16. Recommended First Implementation Slice

Start with Phase 1 only:

1. Add `GameDesignRequirementMapService`.
2. Add requirement map API/readback.
3. Add artifact-local `contract_hash`, `source_gdd_hash`, `source_scene_route_hash`, `source_requirement_map_hash`, and `source_contract_snapshot_hash`, with readback/API projections `contractHash`, `sourceGddHash`, `sourceSceneRouteHash`, `sourceRequirementMapHash`, and `sourceContractSnapshotHash`.
4. Add stale detection and frontend banner.
5. Add tests for deckbuilder GDD -> requirement map -> fresh contract.

This first slice gives the largest drift reduction with the least UI disruption.
