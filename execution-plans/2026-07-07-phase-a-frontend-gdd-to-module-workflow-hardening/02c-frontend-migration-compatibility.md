# Frontend, Migration, And Compatibility

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 467-574.

## 8. Frontend Changes

### 8.0 Status Vocabulary

The browser must not mix stage, route, readiness, and UI matrix statuses as if they were one enum.

Status dimensions:

- Stage timeline status: `not_started|ready|running|needs_review|blocked|completed|stale`.
- Route/readback status: `queued|running|ready|blocked|needs_fix|succeeded|failed|cancelled|stale|unknown`.
- Requirement coverage status: `mapped|missing_scene|missing_module|needs_review|explicitly_deferred|conflict`.
- Scene route confirmation status: `draft|needs_review|confirmed|stale|blocked`.
- Admin review queue status: `open|approved|deferred|rejected|backlog|superseded|resolved`.
- UI surface matrix status: `covered|missing_ui|missing_feedback|needs_fix|no_ui_needed`.
- Readiness label: `not_ready|ready|blocked|stale|unknown`.
- Prototype-skeleton source state: `fresh|stale|missing|unknown|legacy_compatibility_only`.
- Diagnostic triage status: `unresolved|resolved|ignored|backlog`.
- Style/capability coverage status: `required|style_optional|conditional|admin_tooling_or_security_gated|not_applicable|deferred|not_consumed_by_first_slice`.
- Full-target closure status: `covered|reviewed_not_applicable|explicitly_deferred`.
- Operation status values remain the API/readback DTO operation set from `02b-backend-api-contracts.md`: `returned_existing|active_run_reused|created_run|rejected`.

Central owner:

- Phase 0A must create the `PhaseA.Platform/Workflow/` workflow-governance namespace and `PhaseA.Platform.Tests/Fixtures/` fixture directory if they do not already exist, then add a status vocabulary fixture at `PhaseA.Platform.Tests/Fixtures/route-status-vocabulary.v1.json` and runtime mapping owner `PhaseA.Platform/Workflow/RouteStatusVocabulary.cs`.
- Browser mapping tests, route-state validators, and DTO projection tests must consume this fixture/source instead of redefining status dimensions locally.
- Any new status value must declare its dimension in the central fixture/source and update the dimension-specific browser/API/sidecar mapping tests in the same change.
- Validators must reject using a value from the wrong dimension, such as persisting a stage `completed` value in a route-state sidecar or treating admin queue `approved` as a generic route success.
- Artifact sidecars that need a smaller state set must declare `status_dimension` and `status_allowed_values` as a subset of the central vocabulary. Subsets are allowed only when validators prove every value belongs to the declared dimension and browser mapping tests cover the subset.

Acceptance criteria:

- Frontend mapping functions translate route/readback statuses into stage timeline statuses; route status `succeeded` maps to stage status `completed` only after the required sidecar/readback artifact validates.
- UI matrix status `covered` is never displayed as a route success state, and stage status `completed` is never persisted into route-state sidecars.
- Browser tests cover every status mapping above and fail on unknown new status values until a mapping is added.
- Route-state sidecar validators and API/readback DTO projection tests fail if they introduce a status not present in the correct central vocabulary dimension.
- Route-state sidecar validators fail if an artifact-local subset omits its `status_dimension`, uses a value from another dimension, or persists display-only stage values such as `completed` as route/readback state.

### 8.1 Stage Timeline

Add a visible stage timeline:

1. GDD
2. Scene Confirmation
3. GDD Document Generation
4. Requirement Map
5. Contract Freeze
6. Game Modules
7. Task Execution
8. UI Closure
9. Preview/Package

Acceptance criteria:

- Each stage shows `not_started|ready|running|needs_review|blocked|completed|stale`.
- The current recommended action is visually primary.
- Blocked stages show a concrete reason and source artifact.
- GDD Document Generation shows missing/stale/generated states from `meta/routes/gdd-document/latest.json` and disables requirement-map generation when generated GDD hash evidence is missing or mismatched.
- Existing legacy action buttons remain available under advanced/secondary actions during rollout.
- `completed` is display-only stage language. Underlying route readback continues to use route/readiness status vocabulary.

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
- If generated GDD hash differs from the scene-route recorded generated-GDD hash, banner says generated GDD no longer matches confirmed scene route and offers GDD document regeneration or scene reconfirmation.
- If structured game-type metadata changed after scene confirmation, banner says project type analysis changed and offers scene reconfirmation/manual refresh instead of silently continuing.
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
- Shows exemption type and scope when present: `no_ui_needed` exempts only the UI surface requirement, and `style_not_applicable` exempts only the style contract requirement.

### 8.6 Preview, Package, And Final Readiness Boundary

Phase 1 keeps ordinary package download recoverable for existing successful prototypes, but it must not blur that path with final readiness approval.

Acceptance criteria:

- Existing successful legacy prototypes can still preview/package through compatibility paths when their existing package artifact and ticket readback are valid.
- New preview/package readiness cannot be shown as `ready` or `succeeded` when current source hash, diagnostics evidence, package artifact, preview ticket, browser-safe readback, or route artifact validation is stale, missing, or invalid.
- Final package readiness cannot pass with unresolved P0/P1 UI closure blockers, source-boundary blockers, diagnostics blockers, stale style snapshot, or unresolved admin review queue blockers.
- The browser labels ordinary package download separately from final package readiness so users do not mistake a downloadable artifact for a fully closed prototype.

## 9. Migration And Compatibility

1. Existing projects without requirement map:
   - Show `requirement_map_missing`, but allow lazy generation.
   - If scene route, generated GDD hash, or structured game-type metadata required by the new chain is missing, show the upstream refresh action first: `analyze_game_type`, scene confirmation, or GDD document generation.
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
   - Do not manually mutate the live metadata DB.
   - Admin review queue metadata DB ownership and diagnostic spool metadata DB index ownership require additive schema migration/reuse coverage through the normal Phase schema path.
   - Legacy projects may be lazily backfilled or shown as missing new artifacts, but the new metadata indexes required by this plan are not optional once their owning routes are implemented.
   - All DB changes must be backward-compatible and must preserve existing project, run, artifact, account, audit, route, and UI state.
6. Prototype contract path compatibility:
   - `routes/prototype-contract/latest.json` is canonical. A `meta/routes/prototype-contract/latest.json` file, when present, is a readback/cache mirror and must match the canonical `contract_hash`.
7. Admin review queue compatibility:
   - Existing projects without queue sidecars show no admin queue entries, not a failed route state.
   - New P0/P1 conflicts, generated exemptions, and workflow blockers use queue sidecars and admin-only APIs instead of hidden requirement-map-only state.
8. Existing projects without scene route, structured game-type metadata, GDD question-form sidecar, or generated-GDD hash sidecars:
   - Project list and existing preview/package readback still render.
   - New requirement-map generation, contract freeze, iteration plan creation, and execution are blocked until the missing upstream artifact is generated or backfilled through the documented route/API.
   - If `docs/gdd/GDD.md` exists but `meta/routes/gdd-question-form/latest.json` is missing, the browser offers canonical workflow action `import_gdd_form`, mapped to a non-destructive GDD form import/backfill or a new GDD question-form confirmation flow before scene route confirmation. It must not infer `source_gdd_form_hash` from `docs/gdd/GDD.md` without recording an explicit legacy import sidecar and user/admin confirmation.
   - Browser readback shows the concrete next action and domain code: `game_type_structured_missing`, `scene_route_missing`, `scene_route_unconfirmed`, `gdd_form_missing`, `gdd_missing`, or `generated_gdd_hash_mismatch`.

Acceptance criteria:

- Old project list renders without exceptions.
- Existing successful prototypes can still preview/package.
- Creating a new iteration plan on an old project prompts requirement map/contract freeze first.
- Creating a new requirement map on an old project prompts `analyze_game_type`, GDD form import/backfill when needed, scene confirmation, or GDD document generation before requirement-map generation when those upstream artifacts are missing.
- Existing projects without Godot UI capability contract fields cannot start new UI-touching goals until the current contract is refreshed and the UI capability hash is recorded.
- No manual live DB mutation is required. Required metadata DB tables or indexes introduced by this plan use backward-compatible additive schema migration/reuse through the normal Phase schema path.
- The frontend can render projects with no admin review queue, no source-boundary fields, or only a prototype-contract mirror without throwing; new prompt-producing route completion remains blocked until the canonical/source-boundary fields exist.
