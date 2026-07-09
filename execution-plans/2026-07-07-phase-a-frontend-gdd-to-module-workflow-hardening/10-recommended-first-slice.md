# Recommended First Implementation Slice

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 2718-2739.

## 16. Recommended First Implementation Slice

Start with Phase 0A, then the smallest Phase 1 slice. Phase 1 work must not begin until Phase 0A exit criteria pass. Phase 0B items are required before a touched route depends on them, but the full TapTapMarker non-technology UI target must not block unrelated Phase 1 route hardening.

Commit-readiness gate:

- Before implementation starts, the split directory and schema fixture must be included in the commit/PR, with no untracked split-plan files.
- The monolithic source document is not a live implementation mirror. If it changes, the change must be explained as source-history maintenance.
- After the split lands, new implementation guidance for this refactor must be added to the split directory or to durable standards/ADR/workflow docs linked from it. The monolithic source document cannot receive new normative requirements.

Phase 0A mandatory baseline:

1. Add Phase 0 route module contract template and route action descriptor registry baseline, including canonical registry path, descriptor hash/version policy, and parity tests against browser/API action catalogs.
2. Add Phase 0 path/readback policy, no-store response policy for workflow/evidence readback, action exposure classes, context-boundary rules, and account-boundary guard tests.
3. Add Phase 0 duplicate-run/idempotency convention, `active_run_reused` response contract, and local preflight checklist.
4. Add Phase 0 canonical prototype-contract path policy: `routes/prototype-contract/latest.json` is authority, `meta/routes/prototype-contract/latest.json` is optional mirror/cache only, and stale mirror mismatch fails validation.
5. Add Phase 0 common source-boundary schema, prompt-evidence guard for prompt-producing routes, and structured `source_boundary_not_applicable` object for non-prompt route states.
6. Add Phase 0 common dimensioned status vocabulary mapping for stage timeline, route/readback state, requirement coverage, scene route confirmation, admin review queue, UI surface matrix, readiness labels, prototype-skeleton source state, diagnostic triage, style/capability coverage, full-target closure, and operation status values, with central runtime owner and fixture parity tests.
7. Add Phase 0 admin review queue sidecar/API/readback/mutation contract for system-detected P0/P1 blockers, generated exemptions, and admin decisions, with metadata DB as the default query owner and additive migration/reuse tests.
8. Add Phase 0 route action descriptors or non-action browser-flow mappings for the complete canonical workflow action set: `create_gdd`, `complete_gdd`, `import_gdd_form`, `analyze_game_type`, `confirm_scene_route`, `generate_gdd_document`, `generate_requirement_map`, `freeze_contract`, `refresh_contract`, `create_prototype`, `create_iteration_plan`, `execute_next_goal`, `run_needs_fix`, `run_ui_closure`, `preview_package`, `inspect_first`, and `delete_project`. Later-phase actions may be disabled/forbidden until active, but none may be unmapped.
9. Add Phase 0 final-readiness boundary: ordinary package download compatibility is separate from final package readiness and cannot clear unresolved blockers.
10. Add Phase 0 exemption semantics: `no_ui_needed` only exempts UI surface, `style_not_applicable` only exempts style contract, and system-created P0/P1 exemptions require review/confirmation.
11. Add Phase 0 diagnostic spool metadata DB index ownership, minimum diagnostic record schema, minimum failure-family seed for GDD/scene/requirement/contract/source/freshness failures, retention/cleanup boundary with unresolved P0/P1/P2 preservation, and compacted resolved-record replacement evidence.
12. Add Phase 0 evidence ref kind fixture mirrored from `docs/standards/phase-service.md` and parity tests for sidecars, API DTOs, and browser readback.
13. Add Phase 0 secret redaction validator baseline, fixture coverage, and phase review evidence template.
14. Add Phase 0 ADR/decision-log gate for new durable cross-cutting standards and architecture contracts, including `docs/architecture/ADR_INDEX_PHASE.md` updates when an ADR is required.
15. Add Phase 0 shared LLM/Codex entrypoint guard and tests for `ILlmRouteEngine`, `CodexHostedProcessCommandFactory`, and `scripts/sc/_llm_backend.py::run_llm_exec`.
16. Add Phase 0 structured game-type metadata ownership/hash policy and guard tests: Phase project metadata service/metadata DB read model is canonical, raw `GameTypeSource` is source evidence only, English normalized Steam/game-type fields produce `source_game_type_structured_hash`, and missing/stale metadata returns structured blockers.
17. Add Phase 0 phase-service standards sync checklist for API/status/error/readback/no-store semantics, including workflow action gating domain codes, preview/package readiness, admin review queue, diagnostic spool, project delete, and game-type matching maintenance records.

Phase 0B route-dependent baseline:

18. Add Phase 0 Godot engine semantic baseline at `docs/standards/godot-engine-semantics.md`, `docs/standards/_index.md` link, viewport/resolution mode policy, coordinate-space/unit/input/physics/camera/TileMap semantics, curated version-pinned official Godot reference-example index at `docs/reference/godot-official-examples-index.md`, `reference_example_missing` diagnostic family coverage, non-import/product-requirement boundary for examples, and initial guard fixtures.
19. Add Phase 0 Godot UI capability contract template at `docs/standards/godot-ui-capability-contract.md`, `docs/standards/_index.md` link, version/hash rule, canonical hash exclusion list, technology-stack leakage denylist, and initial guard fixtures.
20. Add Phase 0 Godot UI style contract template at `docs/standards/godot-ui-style-contract.md`, built-in style seed under `docs/ui-style-guides/`, `docs/standards/_index.md` link, `README.md`, `docs/PROJECT_DOCUMENTATION_INDEX.md`, relevant Phase service architecture indexes, agent-facing routing, normalized style taxonomy, UI family tier table, style snapshot schema seed, runtime environment hash-identity fields, repo-owned style IDs, custom style metadata and built-in-equivalent checks, trigger taxonomy, design DNA rules, canonical token format, Godot theme slot mapping, safe theme resource refs with required/resolved/unresolved token coverage, structured component-default rules for `core_minimum` and GDD-required `game_minimum` families, security-gated family non-applicability rule, visual evidence self-description, deterministic substitute approval/expiry/recheck and substitution-boundary rule, source-name ownership, structured alias approval rule, technology-stack leakage denylist, and initial guard fixtures. Full TapTapMarker non-technology UI capabilities remain the target in `06a` and are implemented across later slices instead of all being forced into Phase 0/1.
21. Add Phase 0 full Godot diagnostics and quality-gate contract template at `docs/standards/godot-diagnostics-quality-gates.md`, `docs/standards/_index.md` link, `README.md`, `docs/PROJECT_DOCUMENTATION_INDEX.md`, relevant Phase service architecture indexes, agent-facing routing, expanded failure-family taxonomy, full project diagnostic spool schema, symptom-to-remediation table seed, debug-log lifecycle rule, interaction-region artifact rule, preview validation rule, resource lifecycle/orphan diagnostics rule, and initial guard fixtures.
22. Add Phase 0 durable review evidence under `logs/`.
23. Add the Phase 0B dependency matrix from `08-implementation-phases.md` to the phase review evidence so every touched Phase 1 route declares which engine semantic, UI capability, style, diagnostic, visual evidence, and full-target closure packages are active blockers.

Smallest Phase 1 slice:

23. Add `GameDesignRequirementMapService` through `ILlmRouteEngine` for structured LLM output.
24. Add GDD document-generation write-through so successful `docs/gdd/GDD.md` generation records matching `source_generated_gdd_hash` in `meta/routes/scene-route/latest.json`.
25. Add requirement map API/readback.
26. Add artifact-local `contract_hash`, `source_gdd_hash`, `source_scene_route_hash`, `source_requirement_map_hash`, `source_contract_snapshot_hash`, `source_godot_ui_contract_hash`, `source_ui_style_contract_hash`, and `ui_style_snapshot_hash`, with readback/API projections `contractHash`, `sourceGddHash`, `sourceSceneRouteHash`, `sourceRequirementMapHash`, `sourceContractSnapshotHash`, `sourceGodotUiContractHash`, `sourceUiStyleContractHash`, and `uiStyleSnapshotHash`.
27. Add artifact-local Godot UI capability contract version, Godot UI style contract version, source-boundary fields, and readback/API projections `godotUiContractVersion`, `uiStyleId`, `uiStyleVersion`, and `sourceBoundaryEnforced`.
28. Add stale detection for GDD, generated GDD hash/scene-route mismatch, structured game-type metadata hash, scene route, requirement map, contract snapshot, Godot UI capability contract hash, Godot UI style contract hash, and frozen UI style snapshot hash, plus frontend banners for user-actionable stale states.
29. Add route module contract template application for `structured-game-type-analysis`, `scene-route-confirmation`, `gdd-requirements`, `gdd-document-generation`, and `prototype-contract`.
30. Add prototype-skeleton compatibility guard for new-chain projects so skeleton creation cannot bypass the frozen contract/requirement-map chain.
31. Add workflow recommendation phase-eligibility tests proving downstream actions remain in `forbiddenActions[]` until their route contracts and descriptors are active.
32. Add guard tests for canonical/mirror prototype-contract paths, sidecar naming, source hash fields, source-boundary fields including non-prompt `source_boundary_not_applicable`, status vocabulary mapping, evidence ref kind fixture parity, Godot UI contract hash fields, Godot UI style contract hash fields, admin review queue blockers, diagnostic failure-family fields, diagnostic spool metadata DB index/retention, every canonical workflow action name, error envelope shape, package/final-readiness boundary, exemption semantics, path/readback, no-store response policy, exposure class, account boundary, duplicate-run behavior, secret redaction fixture coverage, shared LLM/Codex entrypoint usage, and source-history/commit-readiness.
33. Add tests for the minimum deckbuilder GDD -> requirement map -> fresh contract chain:
    - route-map path-selection requirement is preserved as a required module with `requirementIds`;
    - hand drag/drop requirement is preserved as a required module with `requirementIds`;
    - combat HUD feedback and reward selection UI are classified as UI-facing requirements when present in GDD, scene route, or default contract input;
    - the frozen contract records `source_godot_ui_contract_hash`, `ui_style_id`, `ui_style_version`, `source_ui_style_contract_hash`, and `ui_style_snapshot_hash` for visible UI projects;
    - the selected Godot-native style snapshot covers only the Phase 1 minimum component families needed by the touched deckbuilder route: route map node/action button, card/hand item, combat HUD/status, reward option panel, modal/confirmation when required, and their primary input/feedback states;
    - drag/drop coverage includes pointer event shape, payload identity, cancel, commit, rollback, supported devices, and keyboard/gamepad equivalent or a blocking accessibility gap;
    - interaction-region artifacts exist for route-map selection and hand-card dragging;
    - source-boundary prompt evidence proves the route consumes frozen artifacts, not broad mutable guide/style documents.

Full-target coverage not forced into the first slice:

Full-target capability consumption schedule:

| Capability IDs | First required phase | Trigger | Owner evidence |
| --- | --- | --- | --- |
| `ui_component_system`, `ui_theme_token_system`, `ui_layout_scale_coordinates`, `ui_input_pointer_gesture`, `ui_state_data_binding`, `ui_style_snapshot_schema`, `ui_runtime_environment_identity`, `ui_theme_resource_contract`, `ui_style_schema_acceptance_gate`, `godot_failure_family_taxonomy`, `godot_diagnostic_spool_contract` | Phase 0B / Phase 1 touched routes | Any visible UI project, requirement map, scene confirmation, GDD document generation, or contract freeze | Standards templates, style fixture/profile, phase exit evidence, route/style capability matrix |
| `ui_lifecycle_ownership`, `ui_overlays_feedback`, `ui_diagnostics_visual_evidence`, `ui_visual_evidence_contract`, `godot_prebuild_preview_quality_gate`, `godot_interaction_region_gate`, `godot_resource_lifecycle_gate` | Phase 2-5 when consumed by iteration, execution, repair, UI closure, preview, or package | Dynamic UI nodes, overlays, player feedback, diagnostics, preview/package, interaction-heavy goals, resource-owning helpers | Route contracts, diagnostic spool records, visual evidence, interaction-region artifact, lifecycle cleanup evidence |
| `ui_scroll_virtualization`, `ui_style_closure_gap_taxonomy`, `ui_style_repair_prompt_contract`, `ui_final_readiness_style_gate` | Phase 5-6 or earlier if consumed by a touched route | Large lists/grids, style-aware repair, UI closure, final readiness | UI closure readback, style gap rows, repair prompt evidence, full-target closure ledger |
| `ui_security_gated_tooling` | Only when security-gated admin/tooling UI is implemented | File upload, raw diagnostic viewers, account/admin-only asset tooling | Phase service security policy, account-boundary tests, redacted admin evidence, explicit normal-user non-applicability rows |

Schedule acceptance:

- Each capability package row in the full-target ledger records `firstRequiredPhase`, `trigger`, `ownerEvidence`, and `currentCoverageStatus`.
- Phase exit tests fail when a touched route consumes a capability whose scheduled first required phase has arrived but the row remains `not_consumed_by_first_slice` without a reviewed non-applicability or explicit deferral.
- `ui_security_gated_tooling` cannot be marked covered for normal-user game UI without the Phase service security policy required by `06a` and `06d`.


- The full TapTapMarker non-technology UI capability target remains authoritative in `06a-ui-style-migration-overview-and-catalog.md`, `06b-ui-style-snapshot-schema.md`, `06c-style-aware-ui-closure.md`, `06d-ui-style-schema-acceptance.md`, and `07-godot-diagnostics-quality-gates.md`.
- Phase 1 does not need to prove every advanced style family, lifecycle rule, virtualization path, localization path, Toast behavior, custom-style negative path, or full visual-evidence matrix unless the touched route, GDD requirement, default contract, or selected style snapshot depends on that capability.
- Any omitted full-target capability must be recorded as `not_consumed_by_first_slice`, not `passed`.
- The record lives in the Phase 1 review evidence under `logs/` and in the affected route/style capability matrix row as `coverage_status: "not_consumed_by_first_slice"`, with `capability_id`, `owner_doc`, `reason`, `affected_routes`, and `recheck_phase`.
- Because this classification can affect final readiness and later route consumption, validators and capability-matrix fixtures must treat `not_consumed_by_first_slice` as a first-class coverage value. Implementation must link the decision log, standards update, or ADR required by the ADR matrix in `09-risks-dod-open-questions.md`.
- Phase 2-6 work cannot claim final readiness for a route that consumes a `not_consumed_by_first_slice` capability until the corresponding validator, fixture, and evidence update that row to `covered` or a reviewed non-applicability status.
- Phase 6 must create or update a full-target closure ledger for the TapTapMarker non-technology UI capability set at `logs/phase-a-innernet/reviews/gdd-to-module-hardening/full-target-ui-closure-ledger.json`.
- The ledger schema records `schema_version`, `updated_utc`, `capability_packages[]`, and for each package: `capability_id`, `owner_doc`, `firstRequiredPhase`, `trigger`, `ownerEvidence`, `currentCoverageStatus`, `closure_status`, `affected_routes`, `owner`, `expiry_or_recheck_trigger`, `validation_evidence_refs`, `defer_reason`, and `phase_exit_review_ref`.
- The canonical capability-package inventory is derived from the package/checklist sections in `06a`, `06b`, `06c`, `06d`, and `07`; validator tests reject missing rows, duplicate IDs, orphan IDs, invalid `closure_status`, and final `not_consumed_by_first_slice` rows.
- Every capability package from `06a`, `06b`, `06c`, `06d`, and `07` must end as `covered`, `reviewed_not_applicable`, or `explicitly_deferred` with owner, affected routes, expiry or recheck trigger, and validation evidence; `not_consumed_by_first_slice` is not a final closure state.

This first slice gives the largest drift reduction with the least UI disruption.
