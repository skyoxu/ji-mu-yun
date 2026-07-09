# Backend And API Contracts

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 322-466.

## 6. Backend Changes

### 6.0 Phase Service Implementation Ownership Matrix

Every backend/API item below must be mapped to concrete Phase service implementation files before coding starts.

Required mapping per route or service:

- `PhaseA.Platform/**` handler or endpoint owner.
- C# request/response DTO or readback projection owner.
- Browser caller/surface owner.
- Auth/account-boundary enforcement point.
- Persistence owner: metadata DB table, hosted project sidecar, diagnostic/admin index, or append-only evidence.
- Test owner under `PhaseA.Platform.Tests/**`, plus any script smoke under `scripts/python/phase_a_*.py` or `scripts/python/phase_b_*.py`.

Acceptance criteria:

- A route implementation is not accepted if it only names a conceptual service/API without the handler, DTO, browser caller, auth boundary, persistence owner, and test owner.
- New metadata DB persistence requires additive schema/migration/reuse coverage through the existing Phase metadata schema path.
- New sidecar-only persistence is allowed only for project-local recovery state that is not required after workspace deletion.

### 6.1 New Service: `GameDesignRequirementMapService`

Responsibilities:

- Read `docs/gdd/GDD.md`.
- Read confirmed scene route state from `meta/routes/scene-route/latest.json`.
- Read the canonical project structured game-type metadata from the Phase project metadata service/metadata DB read model, validate its `source_game_type_structured_hash`, and read the mirrored contract snapshot only as route recovery context.
- Read project `contractSnapshot` and game-type default required modules.
- Read the Godot UI capability contract described in this plan and classify UI-facing requirements with expected surfaces, inputs, feedback states, and validation markers.
- Generate `meta/routes/gdd-requirements/latest.json` through `ILlmRouteEngine`/`LlmRouteEngine` structured LLM output or deterministic fallback. The service must not construct provider calls or executable `codex` commands directly.
- Validate coverage and status.
- Persist route state and mirror it if needed.
- Record `source_boundary_enforced` and the common `source_boundary` object from `02a-route-state-artifacts.md` whenever the service builds structured LLM input.

Acceptance criteria:

- Service returns stable JSON with deterministic IDs (`REQ-001`, `REQ-002`, ...).
- Service fails closed when GDD is missing, `meta/routes/scene-route/latest.json` is missing/not confirmed/stale, or returned requirement map JSON is invalid.
- Service validates that the scene sidecar's `confirmed_scene_route_hash` equals the requirement map `source_scene_route_hash`; a mismatch returns a structured blocker before LLM invocation.
- Service validates that the scene sidecar's `source_game_type_structured_hash` equals the current canonical structured game-type metadata hash before requirement map generation; mismatch returns `game_type_structured_stale`.
- Service validates that normalized `docs/gdd/GDD.md` hash equals both `meta/routes/gdd-document/latest.json.generated_gdd_hash` and `meta/routes/scene-route/latest.json.source_generated_gdd_hash`; mismatch returns `generated_gdd_hash_mismatch` before LLM invocation.
- Service produces fallback `needs_review` rows instead of silently returning an empty requirement set.
- Service marks requirements as `kind=ui` or adds UI acceptance markers when the GDD implies player-facing interaction, feedback, HUD, menu, camera overlay, custom drawing, animation state, or visualized procedural content.
- Unit tests cover successful map generation, invalid LLM JSON fallback, missing sources, and default module preservation.
- Generated route state is invalid for completion if LLM prompt evidence exists but the common source-boundary fields are missing, false, or point at mutable broad guide excerpts instead of declared authority sources.

### 6.2 New/Extended Service: `PrototypeContractFreezeService`

Responsibilities:

- Freeze or refresh canonical `routes/prototype-contract/latest.json` from GDD, scene route, requirement map, contract snapshot, and current request fields.
- Add source hashes and traceability.
- Freeze the current Godot UI capability contract version/hash as part of the prototype contract source set.
- Freeze the selected Godot UI style contract version/hash, repo-owned style ID, and UI style snapshot hash as part of the prototype contract source set when the project can produce visible UI.
- Detect stale contract state.

Acceptance criteria:

- Freeze writes a contract with all source hashes.
- Re-freezing unchanged sources is idempotent except `updated_utc`/`updatedUtc` if policy requires updating it.
- Changed GDD, stale scene route sidecar, generated-GDD/scene-route hash mismatch, or changed structured game-type metadata hash marks the previous contract stale.
- Changed Godot UI capability contract version/hash marks contracts as `stale` for new iteration plans unless the change is explicitly declared backward-compatible by a later decision log.
- Changed Godot UI style contract version/hash or frozen UI style snapshot hash marks contracts as `stale` for UI-facing iteration plans unless the change is explicitly declared backward-compatible by a later decision log.
- Freezing does not run Steam lookup or rematch game type.
- Existing `PrototypeContractService` remains backward compatible.
- If implementation writes `meta/routes/prototype-contract/latest.json` for readback compatibility, that file is a mirror only; recovery, stale checks, and contract-hash authority use `routes/prototype-contract/latest.json`, and tests fail when the mirror hash differs.

### 6.2.1 Extend Prototype Skeleton Creation/Readback Guard

Responsibilities:

- Guard the existing prototype/skeleton entrypoints that create, refresh, or validate the first playable skeleton:
  - `POST /api/projects/{projectId}/prototype-7day-playable` through `PrototypeWorkflowService.QueueAsync`.
  - `POST /api/projects/{projectId}/prototype-7day-playable/from-gdd` through `PrototypeWorkflowService.QueueFromGddAsync`.
  - `POST /api/projects/{projectId}/prototype-7day-playable/validate-skeleton` through `PrototypeWorkflowService.ValidateSkeletonAsync`.
- Map the current browser prototype creation/from-GDD/validate-skeleton controls to route action descriptors before new-chain skeleton guard enforcement is accepted. Canonical recommendation IDs come from the descriptor registry; endpoint-specific IDs remain aliases/projections only.
- Read canonical `routes/prototype-contract/latest.json`, requirement map, scene route, and GDD source hashes before new-chain skeleton creation starts.
- Reject new-chain skeleton creation or refresh when the frozen contract is missing, stale, or sourced from unknown hashes.
- Write or update `meta/routes/prototype-skeleton/latest.json` as readback evidence for skeleton compatibility.
- Preserve legacy skeleton/package compatibility only as compatibility readback; it cannot become final readiness evidence for new-chain projects.

Acceptance criteria:

- The route implementation map names the concrete PhaseA handler/service, DTO/readback projection, browser caller, auth boundary, persistence owner, and test owner for skeleton creation/readback.
- The canonical workflow action for starting prototype creation remains `create_prototype`. Existing prototype-skeleton operations such as `create_prototype_from_gdd`, `validate_prototype_skeleton`, `prototype_skeleton_status`, `prototype_7day_playable`, `prototype_7day_playable_from_gdd`, and `prototype_validate_skeleton` are descriptor aliases, endpoint aliases, or readback projections only; they must not be emitted as canonical workflow recommendation IDs unless a later decision log extends the canonical action set.
- New-chain skeleton creation cannot bypass the frozen contract and requirement-map chain.
- Skeleton readback records `source_contract_hash`, `source_requirement_map_hash`, `source_gdd_hash`, `source_scene_route_hash`, `updated_utc`, and `evidence_refs`.
- Existing legacy projects continue to load, but legacy skeleton state is labeled compatibility-only until the contract chain is refreshed.
- Tests cover stale, missing, unknown, legacy-compatibility, and fresh-contract skeleton paths.

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
- The iteration plan artifact-local route state must record `source_gdd_hash`, `source_scene_route_hash`, `source_requirement_map_hash`, `source_contract_hash`, `source_contract_snapshot_hash`, `source_godot_ui_contract_hash`, `source_ui_style_contract_hash`, and `ui_style_snapshot_hash`; API/readback projects these as camelCase.
- Every generated goal must record the same artifact-local source hash set or a `source_hash_ref` that points to the session-level hash set; API/readback may project the reference as `sourceHashRef`.
- Stale checks must compare execute-next-goal source hashes against the current frozen contract and requirement map before executable work is handed to `CodexHostedProcessCommandFactory`.
- Stale checks must compare `sourceGodotUiContractHash` against the current frozen Godot UI capability contract hash before any UI-touching goal is handed to `CodexHostedProcessCommandFactory`.
- Stale checks must compare `sourceUiStyleContractHash` and `uiStyleSnapshotHash` against the current frozen Godot UI style contract and snapshot before any styled UI-touching goal is handed to `CodexHostedProcessCommandFactory`.

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
- Executable route work must use `CodexHostedProcessCommandFactory`; structured/read-only LLM calls must use `ILlmRouteEngine`; Python LLM/Codex helpers must delegate to `scripts/sc/_llm_backend.py::run_llm_exec`.
- Tests assert Codex is not called in stale/missing cases and assert new LLM/Codex callers use the shared entrypoints rather than local subprocess/provider construction.
- Execute-next-goal can only allow an old goal to continue when the goal/session recorded source hashes match the contract and requirement map that were current when that goal was created.
- If source hashes are missing, execute-next-goal treats the goal as `source_unknown` and blocks by default for new projects.
- `sourceContractHash` in API/readback and route prompts is the camelCase projection of `contract_hash` from the frozen prototype contract.

### 6.5 Extend `ProjectWorkflowRouteService`

Responsibilities:

- Build frontend recommendation from route states, run states, stale artifacts, and validation blockers.
- Replace button-only guidance with structured recommendation.
- Resolve every emitted `recommendedAction` in the complete canonical workflow action set through a route action descriptor, browser action ID, or explicit non-action display mapping.
- Resolve `create_gdd` through the existing GDD question-form/start browser flow or a concrete API descriptor before the recommendation service may emit it.
- Resolve `import_gdd_form` through the legacy GDD form import/backfill or confirmation browser flow before the recommendation service may emit it. This action is non-destructive and must create the explicit legacy import sidecar required by the compatibility rules before scene confirmation proceeds.
- Resolve `analyze_game_type` through the project structured game-type analysis/backfill API or browser/admin-safe flow before the recommendation service may emit it.
- Resolve `confirm_scene_route` through the existing scene route confirmation browser flow or a new concrete confirmation API before the recommendation service may emit it. Either path must write `meta/routes/scene-route/latest.json` and a stable `confirmed_scene_route_hash`.
- Resolve `generate_gdd_document` through the GDD document-generation API or browser flow before the recommendation service may emit it. The mapped action must write `meta/routes/gdd-document/latest.json` and update `meta/routes/scene-route/latest.json.source_generated_gdd_hash`.
- Resolve `delete_project` through the ordinary user project-delete API/browser action before the recommendation service may emit it; the mapped action must preserve admin review and diagnostic tombstone evidence.
- Resolve the phase-gated downstream subset `generate_requirement_map`, `freeze_contract`, `refresh_contract`, `create_prototype`, `create_iteration_plan`, `execute_next_goal`, `run_needs_fix`, `run_ui_closure`, `preview_package`, and `inspect_first` through descriptor entries before those actions may appear in workflow recommendation readback. Inactive later-phase actions return only forbidden/disabled descriptors with stable `disabledDomainCode`; `inspect_first` remains a non-mutating display mapping unless a later API is introduced.

Acceptance criteria:

- API readback includes `recommendedAction`, `blockingIssues`, `allowedActions`, and `forbiddenActions`.
- Existing UI remains usable if recommendation data is missing.
- Recommendation is deterministic for known route state combinations.
- `create_gdd` maps to the existing GDD question-form/start browser flow or a concrete API descriptor and is never emitted as an unmapped string.
- `import_gdd_form` maps to the legacy GDD form import/backfill or confirmation flow and is never emitted as an unmapped string.
- `complete_gdd` maps to the existing GDD form/draft-completion browser flow and is never emitted as an unmapped string.
- `analyze_game_type` maps to the project structured game-type analysis/backfill flow, writes the canonical English structured metadata payload, and is never emitted as an unmapped string.
- `confirm_scene_route` maps to the scene route confirmation browser flow or concrete confirmation API, writes the scene-route confirmation sidecar, and is never emitted as an unmapped string.
- `generate_gdd_document` maps to the GDD document-generation API or browser flow, writes the GDD document sidecar, updates the scene-route generated-GDD hash, and is never emitted as an unmapped string.
- `delete_project` maps to the ordinary project-delete API/browser action, preserves tombstone evidence, and is never emitted as an unmapped string.
- Every action in the complete canonical workflow action set is covered by service-level descriptor mapping tests, including non-mutating `inspect_first` and inactive later-phase actions in `forbiddenActions[]`.

### 6.6 New Admin Review Queue Readback

Responsibilities:

- Surface system-detected P0/P1 conflicts, generated exemptions, and project-level workflow blockers from `meta/routes/admin-review-queue/latest.json`.
- Provide admin-only decision mutation for approve/defer/reject/backlog/resolve actions without rewriting the original failure or route-state history.
- Provide normal-user project readback with only redacted blocking summaries when a queue entry blocks their workflow.
- Maintain deletion-safe queue indexing through the default metadata DB owner defined in `02a-route-state-artifacts.md`. A diagnostic/admin index may mirror or rebuild evidence, but it is not the default query owner unless a later Phase ADR or decision log changes that.
- Serialize concurrent queue updates through metadata DB transactions by default. Sidecar compare-and-swap/write-lock behavior may protect project-local cache writes only; it cannot be the cross-project queue concurrency authority.
- Project deletion must invoke the admin review queue persistence service before destructive workspace cleanup so unresolved queue entries are marked with deleted-project tombstone metadata through metadata DB transactions. Any diagnostic/admin index mirror is written from the same sanitized service event and cannot be the primary tombstone authority.

Acceptance criteria:

- Admin queue readback enforces admin identity and can filter by `projectId`, route, severity, status, and age.
- Admin decision mutation records `decision`, `decision_by`, `decision_role`, `decision_reason`, `decision_utc`, and `decision_evidence_refs`, and appends or updates the queue sidecar without deleting the source artifact.
- Normal users cannot list queue entries, inspect cross-account queue data, or infer another account's project existence through queue APIs.
- System-created P0/P1 `no_ui_needed` or `style_not_applicable` exemptions remain blocking `needs_review` until an admin decision or an explicitly allowed user confirmation flow resolves them.
- Concurrent admin decisions on the same queue entry return a deterministic `409 conflict` or idempotent success when the decision payload hash matches the existing decision.
- Deleted-project admin lookup still returns unresolved queue entries or tombstones with redacted summaries.
- Decision status effects are deterministic: `approved` and `resolved` unblock only the decided entry, `deferred` may temporarily unblock only with expiry/recheck metadata and scoped affected routes, while `rejected` and `backlog` remain blocking for P0/P1 downstream gates and final readiness.

## 7. API Changes

Add or extend routes:

1. `POST /api/projects/{projectId}/game-type/analyze`
   - Analyze or backfill canonical English structured game-type metadata from raw `GameTypeSource`, English Steam/category/tag evidence, and `game-types.csv` `genre_tags` matching.
   - The route writes the metadata DB/project metadata read model payload and returns `gameTypeStructuredHash`, match status, selected game-type ID, selected guide ID, maintenance record ID when ambiguous/unmatched, and browser-safe evidence refs.
2. `POST /api/projects/{projectId}/gdd/requirements-map`
   - Generate or refresh requirement map.
   - Idempotency: if the current source hashes match the latest map, return the existing route state; if sources changed and no active generation exists, create a new generation run; if generation is already active, return the active run/state instead of starting a duplicate.
3. `GET /api/projects/{projectId}/gdd/requirements-map/latest`
    - Read latest requirement map.
4. `POST /api/projects/{projectId}/gdd/document/generate`
   - Generate or refresh `docs/gdd/GDD.md` from the GDD form, confirmed scene route, canonical structured game-type metadata, and project contract snapshot.
   - After successful generation, update `meta/routes/scene-route/latest.json` with `source_generated_gdd_hash` and record a browser-safe evidence ref. If the scene sidecar cannot be updated, return `operationStatus=rejected` with `details.domainCode=gdd_scene_hash_write_failed`.
   - Idempotency: unchanged source hashes return the current generated GDD state and hash; changed source hashes require explicit refresh intent and invalidate dependent requirement-map/contract recommendation state.
5. `GET /api/projects/{projectId}/gdd/document/status`
   - Read latest generated GDD hash/status, source refs, browser-safe blockers, and whether the scene route sidecar carries the matching `source_generated_gdd_hash`.
6. `POST /api/projects/{projectId}/gdd/scene-route/confirm`
   - Confirm or update the scene route draft before requirement map generation. If implementation reuses an existing browser-only confirmation flow instead of a new API, the route action descriptor must record the non-action/browser-flow mapping, the flow must still write `meta/routes/scene-route/latest.json`, and the recommendation service must not expose an unmapped action.
   - Readback/API errors for missing or unconfirmed scene route use `details.domainCode=scene_route_unconfirmed` and include a browser-safe `blockingIssues[]` entry.
7. `GET /api/projects/{projectId}/gdd/scene-route/latest`
   - Read latest scene route confirmation state, including scene relationships, status, stale reasons, `confirmedSceneRouteHash`, source hash refs, browser-safe blockers, and user-actionable next steps.
   - Normal-user readback is account-scoped and redacts raw prompts, provider details, host paths, and admin-only evidence.
8. `POST /api/projects/{projectId}/prototype-contract/freeze`
   - Freeze or refresh prototype contract after requirement map.
   - Idempotency: if source hashes match the frozen contract, return the existing contract status; if sources changed, require explicit refresh intent and write a new frozen contract version; reject unsafe duplicate refresh with `409`.
9. `GET /api/projects/{projectId}/prototype-contract/status`
   - Return fresh/stale/unknown status and hash reasons.
10. `GET /api/projects/{projectId}/prototype-skeleton/status`
   - Return compatibility guard state for skeleton creation/readback, including source hash status and whether the state is final-readiness eligible.
   - `POST /api/projects/{projectId}/prototype-7day-playable`, `POST /api/projects/{projectId}/prototype-7day-playable/from-gdd`, and `POST /api/projects/{projectId}/prototype-7day-playable/validate-skeleton` must reject new-chain requests when this guard is stale, missing, or unknown.
11. `GET /api/projects/{projectId}/workflow-recommendation`
    - Return current recommended next action from the existing workflow route authority/read model.
- `recommendedAction=create_gdd` returns a descriptor or browser action mapping for the existing GDD question-form/start flow.
- `recommendedAction=import_gdd_form` returns a descriptor or browser action mapping for the non-destructive legacy GDD form import/backfill or confirmation flow.
- `recommendedAction=complete_gdd` returns a descriptor or browser action mapping for the existing GDD draft-completion flow.
- `recommendedAction=analyze_game_type` returns a descriptor or browser action mapping for structured game-type metadata analysis/backfill.
- `recommendedAction=confirm_scene_route` returns a descriptor or browser action mapping for scene route confirmation and cannot be emitted until the writer for `meta/routes/scene-route/latest.json` is active.
- `recommendedAction=generate_gdd_document` returns a descriptor or browser action mapping for `POST /api/projects/{projectId}/gdd/document/generate`.
- The phase-gated downstream subset `recommendedAction=generate_requirement_map`, `freeze_contract`, `refresh_contract`, `create_prototype`, `create_iteration_plan`, `execute_next_goal`, `run_needs_fix`, `run_ui_closure`, `preview_package`, and `inspect_first` returns descriptor/browser mappings only after their phase-specific route contracts are active; otherwise they may appear only in `forbiddenActions[]` with `disabledReason`, `blockingIssues[]`, and the missing route-contract or stale-source reason.
- `inspect_first` returns a non-action display mapping to workflow/readback inspection surfaces and never starts a run, mutates project state, or bypasses admin-only evidence redaction.
12. `DELETE /api/projects/{projectId}`
    - Ordinary user project deletion. The route enforces account ownership, is idempotent for repeated delete requests, preserves diagnostic spool/admin review tombstone evidence with shared `deletionEventId` and `projectTombstoneId`, and returns browser-safe errors such as `workspace_delete_failed` instead of unhandled 500s.
    - `recommendedAction=delete_project` maps to this route or the existing browser action that invokes it.
13. `POST /api/projects/{projectId}/ui-wiring-closure`
    - Generate UI wiring closure state.
    - Idempotency: return an existing closure state only when `source_iteration_session_hash`, `source_validation_input_hash`, `source_contract_hash`, `source_requirement_map_hash`, `source_godot_ui_contract_hash`, `source_ui_style_contract_hash`, and `ui_style_snapshot_hash` all match the latest closure state; if closure is already running for the same hash set, return the active run/state; otherwise create one closure run.
14. `GET /api/projects/{projectId}/ui-wiring-closure/latest`
    - Read latest UI closure state.
15. `GET /api/admin/projects/{projectId}/review-queue/latest`
    - Admin-only readback for current project review queue entries, including unresolved P0/P1 blockers and queue evidence refs.
16. `POST /api/admin/projects/{projectId}/review-queue/{queueEntryId}/decision`
     - Admin-only decision mutation for `approved|deferred|rejected|backlog|resolved`, with idempotency based on queue entry, current status, and decision payload hash.
     - The request/response DTO uses `decision`, `decisionBy`, `decisionRole`, `decisionUtc`, `decisionReason`, and `decisionEvidenceRefs` in browser/API camelCase projection of the snake_case sidecar fields.
     - The request/response DTO includes `blockingEffect`, `deferOwner`, `deferExpiresUtc`, `deferRecheckTrigger`, and `deferAffectedRoutes`; `deferred` decisions require owner, expiry or recheck trigger, affected routes, and evidence refs.
17. `GET /api/admin/review-queue/latest`
     - Admin-only cross-project queue readback with filters for status, severity, route, age, account, project, and deleted-project tombstones.

Minimum API/readback DTO field matrix:

| Route family | Minimum response fields |
| --- | --- |
| Structured game-type analysis/backfill | `operationStatus`, `projectId`, `gameTypeStructuredHash`, `matchStatus`, `selectedGameTypeId`, `selectedGuideId`, `maintenanceRecordId`, `blockingIssues`, `evidenceRefs` |
| Scene route confirmation/status | `operationStatus` when POST, `projectId`, `status`, `confirmedSceneRouteHash`, `sourceGameTypeStructuredHash`, `sourceGddFormHash`, `sourceContractSnapshotHash`, `staleReasons`, `blockingIssues`, `evidenceRefs` |
| GDD document generation/status | `operationStatus` when POST, `projectId`, `status`, `generatedGddHash`, `sceneRouteRecordedGeneratedGddHash`, `sourceSceneRouteHash`, `sourceGameTypeStructuredHash`, `staleReasons`, `blockingIssues`, `evidenceRefs` |
| Requirement map latest | `projectId`, `status`, `sourceGddHash`, `sourceSceneRouteHash`, `sourceRequirementMapHash` when available, `coverageSummary`, `requirements`, `blockingIssues`, `evidenceRefs` |
| Prototype contract status | `projectId`, `status`, `contractHash`, `sourceGddHash`, `sourceSceneRouteHash`, `sourceRequirementMapHash`, `sourceContractSnapshotHash`, `sourceGodotUiContractHash`, `sourceUiStyleContractHash`, `uiStyleSnapshotHash`, `freshness`, `blockingIssues`, `evidenceRefs` |
| Workflow recommendation | `projectId`, `recommendedAction`, `allowedActions[]` with `actionId`, `descriptorHash`, `exposureClass`, `phaseEligibility`, `apiRoute`, `browserActionId`, `displayLabelKey`, `operationScope`, `readbackUrl`, and `blockingIssueRefs`, `forbiddenActions[]` with `actionId`, `descriptorHash`, `exposureClass`, `phaseEligibility`, `disabledReason`, `disabledDomainCode`, `missingContractRef`, `requiredPhase`, and `blockingIssueRefs`, `blockingIssues`, `staleArtifacts`, `actionDescriptorRef`, `descriptorHash`, `status`, `statusReason`, `evidenceRefs` |
| Prototype skeleton status | `projectId`, `status`, `sourceContractHash`, `sourceRequirementMapHash`, `sourceGddHash`, `sourceSceneRouteHash`, `finalReadinessEligible`, `legacyCompatibilityReason`, `blockingIssues`, `evidenceRefs` |
| UI wiring closure latest | `projectId`, `status`, `sourceIterationSessionHash`, `sourceValidationInputHash`, `sourceContractHash`, `sourceRequirementMapHash`, `sourceGodotUiContractHash`, `sourceUiStyleContractHash`, `uiStyleSnapshotHash`, `uiSurfaceMatrixSummary`, `styleGapSummary`, `finalReadinessEligible`, `blockingIssues`, `evidenceRefs` |
| Preview/package readiness | `projectId`, `status`, `packageArtifactRef`, `previewTicketRef`, `sourceHashSet`, `ordinaryDownloadCompatible`, `finalReadinessEligible`, `unresolvedDiagnosticsCount`, `unresolvedUiClosureCount`, `unresolvedStyleBlockerCount`, `unresolvedAdminReviewCount`, `blockingIssues`, `evidenceRefs` |
| Admin review queue readback/decision | `queueEntryId`, `projectId`, `accountId` only for admin readback, `route`, `severity`, `status`, `blockingEffect`, `deferOwner`, `deferExpiresUtc`, `deferRecheckTrigger`, `deferAffectedRoutes`, `deletionEventId`, `projectTombstoneId`, `decisionEvidenceRefs`, `evidenceRefs` |
| Project diagnostic spool summary | `diagnosticId`, `projectId`, `route`, `failureFamily`, `severity`, `triageStatus`, `redactionStatus`, `retentionClass`, `deletionEventId`, `projectTombstoneId`, `evidenceRefs`, `userSafeSummary` |
| Project delete | `operationStatus`, `projectId`, `deletionEventId`, `projectTombstoneId`, `deleted`, `diagnosticPreservationStatus`, `adminReviewPreservationStatus`, `blockingIssues`, `evidenceRefs` |

Acceptance criteria:

- All project-scoped routes enforce account ownership.
- Admin-only data remains behind `/api/admin/...`.
- Admin review queue APIs enforce admin identity, account-safe redaction, stable error envelopes, and append-only/auditable decision evidence.
- Admin review queue APIs use metadata DB as the Phase 0A/Phase 1 query owner, define deletion behavior and concurrency control, and include additive DB migration/recovery tests. Diagnostic-index retention tests are required only when an append-only mirror/rebuild index is implemented.
- Metadata DB persistence APIs for admin review queue, diagnostic index, game-type maintenance records, and project-delete tombstones declare minimum table columns, stable keys, uniqueness/index rules, concurrency behavior, export query fields, and deleted-project lookup behavior before route implementation is accepted.
- Responses are additive only; no existing route response field is removed or renamed.
- POST API responses include an explicit `operationStatus` (`returned_existing|active_run_reused|created_run|rejected`) plus either a stable route state, an active `runId`, or an `evidenceRefs` pointer that can be read by a GET route; artifact-local sidecars keep the snake_case `evidence_refs` field.
- Every workflow/API readback that exposes actions must include enough descriptor/readiness data for the browser to render enabled and disabled controls without hardcoded action IDs.
- Workflow action gating uses stable `disabledDomainCode` values from the route status/error vocabulary: `route_contract_not_active`, `phase_gate_blocked`, `source_stale`, `admin_review_blocked`, `diagnostic_blocked`, `account_forbidden`, and `not_applicable`.
- `operationStatus=active_run_reused` responses include `runId`, polling/readback URL or route-state location, operation scope, source hash scope, and server-derived opaque/redacted account-project scope marker so the browser can resume the correct run and tests can prove a stale or cross-account run was not reused. Normal-user responses must not expose internal account IDs, host paths, or metadata DB identifiers.
- If operation status is ever persisted in an artifact-local sidecar, it must use `operation_status`; `operationStatus` is reserved for API/readback DTOs.
- `operationStatus=rejected` responses must include the standard error envelope with `requestId` and optional `details.domainCode`.
- `evidenceRefs.kind` / `evidence_refs.kind` uses the Phase standard closed enum in `docs/standards/phase-service.md`: `log|artifact|sidecar|screenshot|db_row|smoke|validator`, mirrored by `PhaseA.Platform.Tests/Fixtures/evidence-ref-kind.v1.json`. Phase 0A creates the fixture directory if needed; both the standards document and fixture must be updated before a new kind can appear in route state, API DTOs, or browser readback.
- POST responses and generated evidence preserve `requestId`/`correlationId` when the request starts or resumes a run.
- Error envelope `code` values follow Phase standard preferred codes; route-specific business reasons are carried in `details.domainCode`.
- Error status mapping is stable:

  | HTTP status | Envelope `code` | `details.domainCode` examples |
  | --- | --- | --- |
  | `404` | `project_not_found` or resource-specific `*_not_found` only when the caller is allowed to know absence | `gdd_not_found`, `scene_route_missing`, `contract_missing`, `requirement_map_missing` |
  | `409` | `conflict` | `contract_stale`, `ui_contract_unknown`, `iteration_plan_blocked`, `duplicate_active_run` |
  | `422` | `route_state_invalid` | `requirement_map_invalid`, `ui_closure_not_ready`, `ui_contract_unknown` when detected only while validating legacy route state |
  | `429` | `rate_limited` | `route_concurrency_limit`, `account_concurrency_limit` |

- Cross-account or existence-hiding cases must return generic `project_not_found` or `forbidden` and must not expose fine-grained domain codes such as `gdd_not_found` or `requirement_map_missing`.
- Action routes document whether repeat calls are safe repeat, return existing active work, create a new run, or reject duplicates with `409`.
- Browser callers handle 404/409/422 without showing generic 500 failures.
- Browser/API responses that expose project workflow state, route evidence, prompt/source-boundary evidence, admin review queue data, diagnostic spool summaries, or audit details use `Cache-Control: no-store` unless a compatibility exception is recorded in the route action descriptor and linked implementation evidence.
- Preview/package readiness APIs cannot report `ready` or `succeeded` unless current source hashes, diagnostics evidence, package artifact, preview ticket, and browser-safe readback validate. Ordinary package download for legacy successful prototypes may remain available, but final package readiness labels remain blocked by unresolved UI closure, diagnostics, style, source-boundary, or admin review queue blockers.
- DTOs that expose route state or action descriptors include source-boundary status where relevant; browser callers treat missing `sourceBoundaryEnforced` on prompt-producing routes as blocked/invalid rather than successful.
