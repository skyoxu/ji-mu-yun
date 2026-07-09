# Testing Strategy, Observability, Admin Readback

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 575-750.

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
- `PhaseA.Platform.Tests/**` endpoint/handler tests for every new or changed `/api/...` route.
- Auth/account-boundary tests for every project-scoped and admin-scoped route touched by this plan.
- Persistence tests for every new metadata DB table, deletion-safe diagnostic/admin index, or sidecar writer that survives project deletion.

Acceptance criteria:

- Tests cover the deckbuilder reference path: class selection, route map, card battle, reward choice; required modules route selection and hand dragging.
- Tests cover stale GDD hash blocking iteration plan.
- Tests cover stale scene route hash blocking execution.
- Tests cover requirement map P0 missing module blocking contract freeze or module generation.
- Tests cover requirement-map source text handling: normal-user readback uses English normalized summaries or redacted project-owned excerpts, while raw user-language excerpts or raw prompts are admin-only evidence refs and never copied into `requirements[]`.
- Tests cover canonical structured game-type metadata ownership: scene route generation uses the Phase project metadata service/metadata DB read model, preserves raw `GameTypeSource` only as source evidence, computes `source_game_type_structured_hash` from normalized English fields, and returns `game_type_structured_missing` or `game_type_structured_stale` when the source is absent or changed.
- Tests cover the canonical structured game-type metadata payload fields and hash canonicalization: selected game-type ID, selected guide ID, English Steam/category/tag evidence, normalized `genre_tags` matches, match status/confidence, maintenance record ID, evidence refs, volatile-field exclusions, and metadata DB ownership.
- Tests cover admin-approved GDD conflict suppression of a default module with recorded `decision_*` fields.
- Tests cover system-detected conflict appearing in admin review/readback queue and blocking contract freeze until admin approval.
- Tests cover admin review queue sidecar schema, admin-only readback, admin decision mutation, normal-user redacted blocker summaries, account isolation, and deleted-project lookup where applicable.
- Tests cover admin review queue persistence owner behavior: metadata DB migration/reuse as the default owner, diagnostic-index retention/redaction when an approved mirror or rebuild index exists, and rejection of project-sidecar-only unresolved queue ownership.
- Tests cover metadata DB table contracts for admin review queue, diagnostic index, project-delete tombstones, and game-type maintenance records: required columns, stable IDs, uniqueness/index rules, additive migration/reuse, deleted-project lookup, export query shape, and no project-sidecar-only query ownership for unresolved cross-project records.
- Tests cover concurrent admin review decisions on the same queue entry, including idempotent same-payload retry and conflicting-payload `409`.
- Tests cover `operationStatus=rejected` returning the standard error envelope with `requestId` and `details.domainCode`.
- Tests cover UI closure missing surface producing needs-fix status.
- Tests cover UI closure source hash matching for `source_iteration_session_hash`, `source_validation_input_hash`, `source_contract_hash`, `source_requirement_map_hash`, `source_godot_ui_contract_hash`, `source_ui_style_contract_hash`, and `ui_style_snapshot_hash`, including stale behavior when any hash differs.
- Tests cover `ui_contract_unknown` as `freshness.stale_reasons[]`, API `details.domainCode`, and workflow `blockingIssues[]`, not as a freshness status enum value.
- Tests cover route module contract guards, path/readback policy guards, source-boundary guard tests, and operation-status/error-envelope guard tests introduced by the TapTap-derived hardening patterns.
- Tests cover canonical `routes/prototype-contract/latest.json` authority and treat `meta/routes/prototype-contract/latest.json` only as a mirror/cache path that must match `contract_hash`.
- Tests cover the common `source_boundary_enforced` and `source_boundary` schema from `02a-route-state-artifacts.md` on every prompt-producing route state.
- Tests cover non-prompt route states that set `source_boundary_enforced=false`; they must include the structured `source_boundary_not_applicable` object with allowed reason, `checked_utc`, `decision_by`, and `evidence_refs`.
- Tests cover route action descriptor mapping for every `recommended_action`; `complete_gdd` must map to the existing GDD draft-completion browser flow or an explicit non-action display mapping.
- Tests cover route action descriptor mapping for `analyze_game_type`; it must map to the structured game-type metadata analysis/backfill API or browser/admin-safe flow before workflow recommendation may emit it.
- Tests cover route action descriptor mapping for `create_gdd`; it must map to the existing GDD question-form/start browser flow or a concrete API descriptor before workflow recommendation may emit it.
- Tests cover route action descriptor mapping for `import_gdd_form`; it must map to the non-destructive legacy GDD form import/backfill or confirmation flow, create the explicit import sidecar, and remain account-safe before workflow recommendation may emit it.
- Tests cover route action descriptor mapping for `confirm_scene_route`; it must map to the scene-route confirmation browser flow or concrete API and prove the sidecar writer is active before recommendation may emit it.
- Tests cover route action descriptor mapping for `generate_gdd_document`; it must map to the GDD document-generation API/browser flow before workflow recommendation may emit it.
- Tests cover route action descriptor mapping for `delete_project`; it must map to the ordinary project-delete API/browser action, preserve tombstone evidence, and return browser-safe errors.
- Tests cover route action descriptor mapping for the phase-gated downstream subset `generate_requirement_map`, `freeze_contract`, `refresh_contract`, `create_prototype`, `create_iteration_plan`, `execute_next_goal`, `run_needs_fix`, `run_ui_closure`, `preview_package`, and `inspect_first`. Inactive later-phase actions must appear only in `forbiddenActions[]` with `disabledDomainCode`, and `inspect_first` must be a non-mutating display mapping unless a later API is explicitly introduced.
- Tests cover route action descriptor registry hash/version parity between `PhaseA.Platform/Workflow/RouteActionDescriptors.cs`, `PhaseA.Platform.Tests/Fixtures/route-action-descriptors.v1.json`, workflow recommendation readback, browser actions, and API DTOs.
- Tests cover workflow action gating domain codes `route_contract_not_active`, `phase_gate_blocked`, `source_stale`, `admin_review_blocked`, `diagnostic_blocked`, `account_forbidden`, and `not_applicable` across route status vocabulary fixtures, API DTOs, and browser disabled-state mapping.
- Tests cover central status vocabulary parity between `PhaseA.Platform/Workflow/RouteStatusVocabulary.cs`, `PhaseA.Platform.Tests/Fixtures/route-status-vocabulary.v1.json`, browser mapping functions, route-state validators, and DTO projections, including dimension-specific validation for stage, route/readback, requirement coverage, scene route confirmation, admin review queue, UI surface, readiness, prototype-skeleton source state, diagnostic triage, style/capability coverage, full-target closure, and operation status values.
- Tests cover artifact-local status subset declarations: every sidecar `status` field declares `statusDimension`/`statusAllowedValues` or snake_case equivalents, every subset value belongs to the central dimension, and no route-state sidecar persists display-stage-only values.
- Tests cover `evidence_refs.kind` / `evidenceRefs.kind` parity between `docs/standards/phase-service.md`, `PhaseA.Platform.Tests/Fixtures/evidence-ref-kind.v1.json`, route-state validators, API DTOs, and browser readback.
- Tests cover phase-service standards sync for changed API/status/error/readback/no-store semantics; the implementation fails if descriptors, status vocabulary, action gating domain codes, preview/package readiness, admin review queue behavior, diagnostic retention, project-delete tombstones, or game-type maintenance records change without a linked `docs/standards/phase-service.md` update or accepted not-applicable evidence.
- Tests cover Godot UI style capability inventory parity between the stable capability IDs declared in `06a-ui-style-migration-overview-and-catalog.md`, `06b-ui-style-snapshot-schema.md`, `06c-style-aware-ui-closure.md`, `06d-ui-style-schema-acceptance.md`, `07-godot-diagnostics-quality-gates.md`, `schemas/godot-ui-style-contract.v1.example.json`, the full-target closure ledger fixture, validators, and route/style capability matrix rows; missing IDs, duplicate IDs, mutable heading-derived IDs, orphan fixture rows, or owner-doc mismatches fail the review.
- Tests cover Godot UI style schema contract profile parity: required fields, enum sets, active-row cardinality rules, nested object requirements, and capability IDs must match between the example fixture, machine-readable profile, validators, and documentation; prose-only schema rules fail the review.
- Tests cover full-target capability consumption schedule fields in the ledger: `firstRequiredPhase`, `trigger`, `ownerEvidence`, and `currentCoverageStatus`; consumed capabilities cannot remain `not_consumed_by_first_slice` after their scheduled phase without reviewed non-applicability or explicit deferral.
- Tests cover the Phase service shared LLM/Codex entrypoint rule: structured/read-only LLM callers use `ILlmRouteEngine`, executable Codex routes use `CodexHostedProcessCommandFactory`, Python helpers delegate to `scripts/sc/_llm_backend.py::run_llm_exec`, and no new route constructs local provider calls or subprocess commands directly.
- Tests cover prototype-skeleton compatibility guard status for fresh, stale, missing, unknown, and legacy compatibility-only source states.
- Tests cover scene route confirmation sidecar creation and stale behavior: requirement map generation fails when `meta/routes/scene-route/latest.json` is missing, not `confirmed`, stale, or lacks a stable `confirmed_scene_route_hash`.
- Tests cover legacy GDD-only projects where `docs/gdd/GDD.md` exists but `meta/routes/gdd-question-form/latest.json` is missing: downstream scene route/requirement-map generation returns `gdd_form_missing` and offers a non-destructive import/backfill or confirmation flow.
- Tests cover the Phase 1 route module contract set for `structured-game-type-analysis`, `scene-route-confirmation`, `gdd-document-generation`, `gdd-requirements`, `prototype-contract`, and `prototype-skeleton-guard`.
- Tests cover GDD document-generation hash write-through: after `docs/gdd/GDD.md` is generated, `meta/routes/scene-route/latest.json` records the matching `source_generated_gdd_hash`; downstream requirement map generation fails when the generated GDD hash and scene-route sidecar disagree without a reconfirmation or mismatch blocker.
- Tests cover `meta/routes/gdd-document/latest.json` creation/readback, stale behavior, duplicate-run behavior, and no-store/account-safe readback for GDD document generation.
- Tests cover scene route readback through `GET /api/projects/{projectId}/gdd/scene-route/latest`, including account ownership, browser-safe blockers, source refs, stale reasons, and no raw prompt or host-path leakage.
- Tests fail if downstream `source_scene_route_hash` differs from the current scene sidecar `confirmed_scene_route_hash`.
- Tests cover `scene_route_unconfirmed` propagation through workflow recommendation `blocking_issues[]`, API error `details.domainCode`, diagnostic spool records, and browser disabled-state reason.

### 10.2 Integration / Smoke Tests

Add a deterministic smoke path for:

1. Verify Phase 0 baseline evidence and guard artifacts exist for this refactor smoke or for routes that opt into the new contracts.
2. Create project.
3. Generate GDD question form.
4. Confirm scene route.
5. Generate GDD.
6. Generate requirement map.
7. Freeze contract.
8. Generate iteration plan.
9. Execute or dry-run next-goal decision.

Smoke ownership:

- Default script: introduce `scripts/python/phase_a_gdd_to_module_hardening_smoke.py` for the end-to-end GDD -> requirement map -> contract -> iteration-plan route chain.
- Account/admin boundary assertions should extend `scripts/python/phase_b_account_smoke.py` only when the smoke needs cross-account or admin-token checks that are already covered by Phase B helpers.
- The new smoke must be documented in `docs/workflows/phase-a-gdd-to-module-hardening-smoke.md`, linked from `docs/standards/phase-service.md` or `docs/standards/_index.md`, write evidence under `logs/`, and avoid live metadata DB mutation except through public/admin APIs.

Acceptance criteria:

- Smoke writes evidence under `logs/`.
- This refactor smoke fails before project creation if Phase 0 baseline evidence, route contract template, path/readback policy, action exposure classes, duplicate-run convention, preflight checklist, or secret redaction fixture baseline is missing. Existing Phase A/B project creation smokes that do not exercise this refactor remain governed by their existing acceptance gates until the new contracts are adopted.
- Smoke asserts route state files exist and contain matching hashes.
- Smoke asserts prompt-producing route evidence includes the hosted-route recovery source order from `AGENTS.md` and source hashes for every authority artifact used, including `meta/project-execution-guide.md`, current route latest state, and latest live platform acceptance blocker where applicable.
- Smoke asserts `meta/routes/gdd-document/latest.json.generated_gdd_hash`, `docs/gdd/GDD.md` normalized hash, and `meta/routes/scene-route/latest.json.source_generated_gdd_hash` match before requirement map generation.
- Smoke asserts `source_scene_route_hash` in requirement map, prototype contract, and skeleton guard equals `confirmed_scene_route_hash` from `meta/routes/scene-route/latest.json`.
- Smoke asserts no downstream route reads broad game-type guide as authority after contract freeze.
- Smoke/test assertions define this concretely: execute-next-goal, needs-fix, repair, and UI closure prompts may include `source_boundary` and artifact paths, but must not include raw `docs/game-type-guides` guide excerpts or use guide-derived requirements that are absent from the frozen contract/requirement map.
- Smoke/test assertions read the saved prompt or run evidence artifact, not only the route-state summary field, when checking source-boundary behavior.
- Route state must record `source_boundary_enforced: true` when the prompt was built from frozen project artifacts only. Missing or false `source_boundary_enforced` makes the smoke fail and marks the route state invalid for completion.
- Smoke asserts unresolved admin review queue P0/P1 blockers prevent contract freeze, iteration-plan creation, execution, UI closure success, and final readiness.
- Smoke evidence records the exact script name, base URL, account/admin identity class, route IDs, run IDs, and sanitized artifact/readback refs used for the chain.

### 10.3 Browser Tests

Acceptance criteria:

- Embedded scripts remain syntactically valid.
- Stage timeline renders missing, stale, completed, and blocked states.
- Stage timeline tests distinguish display-stage `completed` from route/readback `succeeded`, readiness `ready`, and UI matrix `covered`.
- Requirement map table renders empty, loaded, gap, and stale states.
- Contract freshness banner displays the correct action.
- Primary button follows `workflow-recommendation`.
- Browser tests fail if `complete_gdd` appears without a button/action mapping into the existing GDD form/draft-completion flow.
- Browser tests fail if `create_gdd` appears without a button/action mapping into the existing GDD question-form/start flow.
- Browser tests fail if `analyze_game_type` appears without a button/action mapping into the structured game-type metadata analysis/backfill flow.
- Browser tests fail if `confirm_scene_route`, `generate_requirement_map`, `freeze_contract`, `refresh_contract`, or `inspect_first` appears without a descriptor-driven button, link, or non-action display mapping.
- Browser tests fail if `generate_gdd_document` appears without a button/action mapping into the GDD document-generation API/browser flow.
- Browser tests fail if inactive later-phase actions such as `create_prototype`, `create_iteration_plan`, `execute_next_goal`, `run_needs_fix`, `run_ui_closure`, or `preview_package` are rendered as enabled primary actions before their route contracts are active.
- Browser tests fail if `delete_project` appears without a button/action mapping into the ordinary project deletion flow.
- Browser tests validate `allowedActions[]` and `forbiddenActions[]` item fields, including `actionId`, `descriptorHash`, `phaseEligibility`, `disabledReason`, `disabledDomainCode`, `blockingIssueRefs`, and `readbackUrl` where applicable.
- Browser tests show GDD Document Generation as a distinct stage with running, stale, blocked, and completed display states.
- Browser tests distinguish ordinary package download from final package readiness and show final readiness blockers when UI closure, diagnostics, source-boundary, style, or admin review blockers remain unresolved.
- Browser/API tests validate preview/package readiness response fields: `sourceHashSet`, `packageArtifactRef`, `previewTicketRef`, `ordinaryDownloadCompatible`, `finalReadinessEligible`, unresolved blocker counts, `blockingIssues`, and `evidenceRefs`.

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
- Tests fail if `no_ui_needed` is used to bypass style contract requirements, or if `style_not_applicable` is used to bypass UI surface requirements.
- Tests fail if a system-created P0/P1 `no_ui_needed` exemption reaches success/final readiness without admin decision or an explicitly allowed user confirmation flow.
- Tests fail if UI-goal prompts mention TapTap-only runtime concepts such as UrhoX, Urho3D, Lua, NanoVG, PBRNoTexture, or `.emmylua` outside a conflict-assessment document.
- Tests fail if a required interactive surface lacks mouse/touch input coverage and keyboard/gamepad focus status.
- Tests fail if a required custom drawing surface lacks a redraw/state validation reference.
- Tests fail if a 2D/3D size-sensitive UI or world-space surface uses guessed dimensions without theme metrics, import metadata, `AABB`, `get_aabb()`, collision shape, or a not-applicable rationale.
- Tests fail if camera/HUD surfaces do not declare whether they are separated by `CanvasLayer`, viewport, or camera ownership.
- Tests fail if a high-risk visual UI change has neither screenshot/canvas-pixel/exported visual evidence nor an approved deterministic substitute tied to a recorded harness limitation. Deterministic substitutes cannot replace interaction behavior validation such as drag/drop, focus trap, keyboard navigation, gamepad navigation, pointer event handling, or route-state mutation.
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
- Tests fail if the bounded failure-family checklist, diagnostic spool schema example, and symptom-to-remediation table in `07-godot-diagnostics-quality-gates.md` disagree on the initial failure-family set.
- Tests fail if temporary debug output remains the only acceptance evidence for a changed route.
- Tests fail if deckbuilder route-map selection or hand-card dragging lacks an interaction-region artifact.
- Tests fail if preview/package readiness is reported from stale source hashes, missing artifacts, invalid tickets, or missing browser-safe readback.
- Tests fail if deleting a project deletes unresolved P0/P1/P2 project diagnostic spool records.
- Tests fail if diagnostic spool cleanup removes unresolved P0/P1/P2 records, removes source evidence refs needed for repair/admin triage, or treats resolved/ignored/backlog retention the same as unresolved blockers.
- Tests fail if ordinary package download compatibility is reported as final package readiness when unresolved UI closure, diagnostics, style, source-boundary, or admin review blockers exist.
- Tests fail if admin diagnostic aggregation leaks raw host paths, raw prompts, token material, provider secrets, or cross-account user-visible evidence.
- Tests fail if routes with helper processes or temporary resources can mark success without lifecycle cleanup or orphan-process diagnostic evidence.
- Tests fail if project deletion lacks route governance coverage for route contract, action descriptor/exposure class, account boundary, duplicate-run/idempotency behavior, diagnostic spool preservation, admin review queue tombstones, and browser-safe error handling.
- Godot diagnostics and quality gate test results are included in phase review evidence and must have zero unresolved P0/P1/P2 findings.

### 10.6 Godot UI Style Theme Contract Tests

Required test areas:

- UI style catalog schema tests for every built-in Godot style contract and every custom style contract that can enter execution.
- UI style trigger/recommendation tests proving game type, reference direction, project tags, and user/admin override produce deterministic style selection reasons.
- UI style selection/freeze/readback tests for new GDD projects.
- Style snapshot hash tests for design DNA rules, structured style tokens, semantic usage/action-role rules, structured component defaults, component family baseline, component coverage matrix, variant coverage, component exception rule refs, game composition templates, structured composition rules, density/scale policy, pointer/gesture rules, state ownership rules, UI lifecycle rules, scroll/virtualization rules, motion/transition rules, font policy, font-size unit policy, localization/overflow policy, source-name policy, forbidden-pattern rules, safe theme/visual refs, UI tree readback refs, visual evidence matrix, and custom style built-in-equivalent checks.
- Prompt/evidence tests proving UI-touching routes receive the frozen style snapshot and not broad mutable style-guide files.
- Godot theme resource tests for generated `Theme`, `StyleBox`, `FontFile`, `Control`, `Container`, and `CanvasLayer` usage.
- Visual consistency tests for representative controls: button, panel/card, modal, tab/menu/list, status bar/HUD, deck/card/reward panel where applicable.
- Style-drift tests for repair and UI closure routes.
- Font asset/license policy tests for bundled, generated, fallback, and missing-font cases.

Acceptance criteria:

- Tests fail if a P0/P1 UI goal starts without a selected `uiStyleId`, frozen `uiStyleSnapshotHash`, or explicit `style_not_applicable` rationale.
- Tests fail if `style_not_applicable` is used for a visible UI requirement that still needs a UI surface, or if a system-created P0/P1 style exemption reaches success/final readiness without admin decision or an explicitly allowed user confirmation flow.
- Tests fail if `uiStyleId: custom` can enter iteration, execution, repair, UI closure, preview, or package readiness without passing the same design DNA, schema, token, font, font-size unit, density/scale, component baseline, component coverage, composition, motion/transition, game composition, pointer/gesture, state ownership, UI lifecycle, scroll/virtualization, localization/overflow, contrast/readability, forbidden-pattern, visual-evidence matrix, UI tree readback, source-name, and technology-leakage checks as built-in styles.
- Tests fail if UI prompts, route state, sidecars, generated code, or durable standards require TapTapMarker-only concepts such as UrhoX widgets, Yoga nodes, NanoVG calls, Lua theme templates, or EmmyLua annotations outside conflict-assessment text.
- Tests fail if visual tokens are hand-authored per component when the selected style contract requires centralized Godot theme resources, unless the exception is listed in the style contract with a component, token, rationale, and validation rule.
- Tests fail if the same screen mixes incompatible style families without a recorded style-composition exception.
- Tests fail if generated UI omits required state tokens for hover, pressed, focused, disabled, selected, active, error, success, drag-hover, drop-valid, or drop-invalid states for controls that expose those states.
- Tests fail if generated UI violates the selected style's semantic usage/action-role rules for primary, secondary, destructive, dismiss, modal footer, rarity, HUD, or component-specific action roles without a structured exception and validation evidence.
- Tests fail if generated UI violates the selected style's Godot density/scale policy, safe-area rules, pixel-alignment rule where applicable, or minimum interactive target rule without a structured exception.
- Tests fail if generated UI violates the selected style's design DNA rules, motion/transition rules, component composition rules, contrast/readability rule, or UI tree readback requirements without a structured exception and validation evidence.
- Tests fail if P0/P1 interactive UI lacks pointer/gesture mapping for press, move, release, cancel, keyboard/gamepad focus, propagation/default-action behavior, and required gestures such as tap, pan, drag/drop, long press, wheel, or pinch where applicable.
- Tests fail if UI state changes lack state ownership rules for stateless/stateful, controlled/uncontrolled, route-state binding, signal/update source, and persistence scope.
- Tests fail if dynamic UI nodes, signals, tweens, timers, or input subscriptions lack lifecycle ownership, duplicate-subscription guards, and cleanup/readback evidence.
- Tests fail if scrollable or large-list UI lacks clipping, overflow, visible-range, keying, and virtualization/performance policy where the component family requires it.
- Tests fail if typography lacks a Godot font-size unit policy, design-pixel conversion rule where applicable, line-height rule, localized text expansion policy, max-lines/ellipsis/overflow behavior, and validation evidence.
- Tests fail if built-in style IDs reuse TapTapMarker skill IDs as internal route IDs without a recorded product/legal approval reference and migration rationale.
- Tests fail if a source-inspired public alias is present without structured approval metadata covering alias, approval ref, reviewer/owner, approval timestamp or decision-log ref, and `validation_status: approved`. Pending or rejected alias records may be retained as audit history, but they cannot appear in active public aliases or route identity.
- Tests fail if a built-in style lacks a component family baseline and component coverage matrix for the UI family tiers defined in `06a-ui-style-migration-overview-and-catalog.md`, or fails to mark each family with `coverage_status` as `required`, `style_optional`, `conditional`, `admin_tooling_or_security_gated`, `not_applicable`, `deferred`, or `not_consumed_by_first_slice` with rationale and validation status. `core_minimum` cannot be deferred without a P1 blocker and owner.
- Tests fail if a P0/P1 visible requirement depends on a component family baseline, component coverage row, composition rule, UI tree readback requirement, visual evidence matrix row, or game composition template marked `deferred`, `not_applicable`, missing, or lacking required scene/node paths and validation refs.
- Tests fail if generated UI uses unlicensed or missing fonts, host-local font paths, or font files copied from TapTapMarker assets.
- Tests fail if screenshot/canvas-pixel/exported visual evidence shows style drift from the frozen style contract for high-risk UI changes, or if the evidence omits required viewport/component/state combinations from the style contract's visual evidence matrix.
- Godot UI style contract test results are included in phase review evidence and must have zero unresolved P0/P1/P2 findings.
- Full-target UI closure ledger tests parse `logs/phase-a-innernet/reviews/gdd-to-module-hardening/full-target-ui-closure-ledger.json`, require every capability package from `06a`, `06b`, `06c`, `06d`, and `07`, reject final `not_consumed_by_first_slice` rows for consumed capabilities, and require owner, affected routes, expiry or recheck trigger, validation evidence refs, and phase exit review refs for explicit deferrals.
- Full-target UI closure ledger tests use stable `capability_id` values from the capability package inventory and fail on missing IDs, duplicate IDs, or IDs derived only from mutable prose headings.

### 10.7 Phase Exit Evidence Tests

Required test areas:

- Phase exit review JSON parse and required-field tests.
- Evidence ref existence and redaction tests for phase review artifacts.
- Severity count tests for unresolved P0/P1/P2 findings.

Acceptance criteria:

- Tests parse every run-id phase exit review file matching `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-*-exit-review-*.json` and fail if required fields from `08-implementation-phases.md` are missing. Accepted phase name suffixes are `0a`, `0b`, `1`, `2`, `3`, `4`, `5`, and `6`; any other suffix must be linked from implementation evidence with an explicit reason. `phase-*-exit-review-latest.json` is allowed only as a pointer/readback copy and tests fail if a new review overwrites prior run-id evidence.
- Phase exit tests fail when a touched Phase 1 route omits the Phase 0B dependency matrix row, marks a required Phase 0B package as not needed without evidence, or claims completion while an active UI capability, style, diagnostic, visual evidence, or full-target closure package remains unresolved.
- Tests fail if phase exit evidence claims zero unresolved P0/P1/P2 findings while linked review evidence, diagnostic spool blockers, admin review queue blockers, or route-state blockers remain unresolved.
- Tests fail if phase exit evidence references chat text or PR prose as the only evidence for route success.

## 11. Observability And Admin

Add admin/readback visibility for:

- Requirement map status and gap counts.
- Contract freshness status.
- Stale artifact reasons.
- Current recommended action.
- Full workflow action catalog parity, disabled/forbidden action counts, phase eligibility blockers, and unmapped-action guard failures.
- Project creation game-type matching records, including raw `GameTypeSource` hash/ref, selected game-type ID, selected guide ID, English Steam/category/tag evidence, normalized `genre_tags` matches, match status/confidence, maintenance record ID, and whether a missing guide or CSV `genre_tags` update is needed.
- UI closure status.
- Godot UI capability contract version/hash and UI closure gap families.
- Godot UI style contract ID/version/hash, selected style family, style-drift status, and font policy status.
- Repeated failure families from needs-fix/validation.
- Project diagnostic spool unresolved counts, severity, route, failure family, age, and triage status.
- Preview/package diagnostic readiness, including source hash set and browser-safe failure summary.
- Admin review queue unresolved counts, route, requirement ID, blocking reason, source artifact path, decision status, and age.

Acceptance criteria:

- Admin can answer "Why can this project not generate modules right now?" without reading raw logs.
- Admin can answer "Which GDD requirements did not enter the module plan?" from UI/readback.
- Admin can answer "Which GDD, scene route, and contract snapshot hash produced this prototype contract?" from UI/readback.
- Admin can answer "Which Godot UI capability contract version produced this module plan and UI closure result?" from UI/readback.
- Admin can answer "Which Godot UI style contract and snapshot hash produced this screen or UI closure result?" from UI/readback.
- Admin can answer "Which UI gap family is blocking final readiness: layout, input/focus, feedback, custom drawing, camera/layer, rendering/material, animation, geometry sizing, procedural visualization, or typed state?" without reading raw logs.
- Admin can answer "Which style-drift family from the normalized taxonomy in `06a-ui-style-migration-overview-and-catalog.md` is blocking final readiness?" without reading raw logs. Admin readback must not maintain a second hard-coded taxonomy list.
- Admin can answer "Which projects have unresolved diagnostics after deletion?" without reading workspace directories.
- Admin can answer "Which project creation game-type matches failed, were ambiguous, or need `game-types.csv` `genre_tags` maintenance or a new guide file?" without reading raw logs.
- Admin can export project creation game-type matching records with account-safe fields for maintenance review; exports include `maintenanceRecordId`, selected IDs, match status/confidence, normalized tags, missing guide flag, and evidence refs but no raw prompts or provider secrets.
- Admin can answer "Which workflow actions are disabled because of phase eligibility, source staleness, admin review, diagnostics, account boundary, or missing route contracts?" from workflow readback.
- Admin can verify full workflow action catalog parity across descriptors, browser actions, API DTOs, and workflow readback without reading source code.
- Admin can triage project diagnostics as `unresolved|resolved|ignored|backlog` without rewriting raw failure history.
- Admin can triage review queue entries and diagnostic spool records through separate readback surfaces; changing either decision writes auditable decision metadata and preserves the original source artifact.
- User-facing readback remains account-scoped and cannot expose another account's project route state by guessed IDs.
- Admin aggregation may cross accounts, but raw evidence blobs, host paths, prompts, token material, and provider secrets remain redacted or omitted.
- Browser/API responses that expose project workflow state, route evidence, prompt/source-boundary evidence, admin review queue data, diagnostic spool summaries, or admin audit details use `Cache-Control: no-store` unless a specific compatibility exception is recorded in the route action descriptor and linked implementation evidence.
