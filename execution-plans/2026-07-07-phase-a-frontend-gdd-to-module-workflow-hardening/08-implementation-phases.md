# Implementation Phases

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 2413-2621.

## 12. Implementation Phases

### Phase 0: Cross-Cutting Governance Prerequisites

These prerequisites must land before Phase 1 creates new browser/API readback surfaces or new POST route behavior. Phase 6 remains the later consolidation phase for full route governance coverage, but these items are not allowed to wait until the end.

Phase 0 is split for implementation control:

- Phase 0A is the mandatory blocking baseline for Phase 1: route module contract template, action descriptor baseline for the complete canonical workflow action set, status vocabulary, canonical prototype-contract path policy, source-boundary schema, account/path/readback policy, no-store response policy for workflow/evidence readback, duplicate-run convention, admin review queue owner, minimum diagnostic index/schema, shared LLM/Codex entrypoint guard, secret redaction baseline, ADR/decision-log gate, and phase review evidence template.
- Phase 0B is the expanded capability baseline that may proceed in parallel with Phase 1 only when the touched Phase 1 route does not depend on the missing 0B capability: Godot UI capability/style contract templates, diagnostics contract, diagnostic spool schema, visual evidence fixture seeds, and full TapTapMarker non-technology UI capability coverage.
- A Phase 1 task must list which Phase 0A items it consumes and which Phase 0B items are required by its touched route. Missing required 0B items are blockers, not later cleanups.

Phase 0B dependency matrix for Phase 1 routes:

| Phase 1 route | Required Phase 0B package before implementation | Reason |
| --- | --- | --- |
| `structured-game-type-analysis` | Minimum diagnostic taxonomy and admin maintenance readback only | Missing, ambiguous, or unmatched game-type records must become maintainable diagnostics without requiring UI style contracts. |
| `scene-route-confirmation` | Godot UI capability contract template, minimum diagnostic taxonomy, visual evidence rule when scene UI surfaces are inferred | Scene surfaces, route relationships, and UI-heavy defaults must not be lost before requirement extraction. |
| `gdd-document-generation` | Godot UI capability contract template, Godot UI style contract seed when generated GDD includes visible UI/style promises, minimum diagnostic taxonomy | The generated GDD becomes downstream source authority and must preserve UI/style/default contract implications. |
| `gdd-requirements` | Godot UI capability contract template, Godot UI style contract seed for visible UI requirements, diagnostic spool/index seed | Requirement rows classify UI/style/diagnostic obligations and cannot defer required touched capability packages. |
| `prototype-contract` | Godot UI capability contract template, Godot UI style contract seed, diagnostic spool/index seed, style snapshot fixture for visible UI projects | The frozen contract is the source boundary for later execution and must freeze UI/style hashes before downstream work. |
| `prototype-skeleton-guard` | Godot UI capability contract template, Godot UI style contract seed for visible skeletons, diagnostic spool/index seed, prototype-skeleton source-state vocabulary, preview/package readiness boundary | New-chain skeleton creation and validation cannot bypass the frozen contract/requirement-map chain or become final readiness evidence without current hashes. |

The matrix is additive: if the GDD, scene route, default prototype contract, selected style snapshot, or implementation evidence touches another Phase 0B capability, that capability becomes required for the route even if not listed above.

Phase 0A deliverables:

- route module contract template
- Phase path/readback policy
- route action exposure classes: `user_visible|admin_visible|script_only|internal`
- context-boundary and DTO hygiene rules
- no-store response policy for project workflow state, route evidence, prompt/source-boundary evidence, admin review queue data, diagnostic spool summaries, and audit details
- duplicate-run/idempotency convention for POST routes
- common dimensioned status vocabulary for stage timeline, route/readback state, requirement coverage, scene route confirmation, admin review queue, UI surface matrix, readiness labels, prototype-skeleton source state, diagnostic triage, style/capability coverage, full-target closure, and operation status values
- common source-boundary schema with `source_boundary_enforced`, authority sources, forbidden source patterns, prompt evidence refs, and explicit `source_boundary_not_applicable` reason shape
- canonical prototype-contract path policy: `routes/prototype-contract/latest.json` as authority and `meta/routes/prototype-contract/latest.json` only as mirror/cache when present
- route action descriptor registry path and hash/version validation policy
- admin review queue sidecar/API contract for system-detected P0/P1 blockers, generated exemptions, and admin decisions, with metadata DB as the default query owner
- diagnostic spool metadata DB index ownership policy, minimum diagnostic record schema, minimum failure-family seed for GDD/scene/requirement/contract/source/freshness failures, unresolved diagnostics retention, deleted-project lookup, and explicit relationship to admin review queue decisions
- structured game-type metadata ownership/hash policy: Phase project metadata service/metadata DB read model is canonical, `GameTypeSource` remains raw source evidence, English normalized Steam/game-type fields are hashed deterministically, and project contract snapshots are mirrors unless a later Phase ADR changes ownership
- `analyze_game_type` route action descriptor for structured game-type metadata analysis/backfill
- `create_gdd` route action descriptor or non-action display mapping for the existing GDD question-form/start browser flow
- `complete_gdd` route action descriptor or non-action display mapping for the existing GDD draft-completion browser flow
- `import_gdd_form` route action descriptor or non-action display mapping for the non-destructive legacy GDD form import/backfill or confirmation flow
- `generate_gdd_document` route action descriptor or non-action display mapping for the confirmed-scene-to-GDD-document generation flow
- `delete_project` route action descriptor for the ordinary project-delete browser/API flow
- descriptor or disabled/non-action mapping for the complete workflow recommendation action set from `02a-route-state-artifacts.md`; later-route actions may remain forbidden until active, but none may be unmapped
- secret redaction validator baseline with fixtures and denylist/allowlist update path
- local deterministic preflight checklist
- P0/P1/P2 review evidence template for phase exits
- Phase ADR or decision-log gate for new durable cross-cutting standards and architecture contracts, with `docs/architecture/ADR_INDEX_PHASE.md` updated when an ADR is required
- shared LLM/Codex entrypoint guard: structured/read-only LLM through `ILlmRouteEngine`, executable Codex through `CodexHostedProcessCommandFactory`, Python helpers through `scripts/sc/_llm_backend.py::run_llm_exec`

Phase 0B deliverables:

- Godot UI capability contract template at `docs/standards/godot-ui-capability-contract.md`, `docs/standards/_index.md` link, contract version/hash rule, canonical hash exclusion list, and technology-stack leakage denylist
- Godot UI style contract template at `docs/standards/godot-ui-style-contract.md`, `docs/ui-style-guides/` style catalog, `docs/standards/_index.md` link, normalized style taxonomy, UI family tiers, style snapshot schema seed, runtime environment hash-identity fields, repo-owned style IDs, custom style metadata and built-in-equivalent rule, trigger taxonomy, design DNA rules, canonical token format, Godot theme slot mapping, safe theme resource refs with required/resolved/unresolved token coverage, source-name ownership, structured alias-approval rule, deterministic visual evidence rule, technology-stack leakage denylist, and guard fixtures. Full TapTapMarker non-technology UI capability packages remain the target in `06a-ui-style-migration-overview-and-catalog.md` and are implemented across later slices rather than all being forced into Phase 0A or Phase 1.
- Godot diagnostics and quality-gate contract template at `docs/standards/godot-diagnostics-quality-gates.md`, `docs/standards/_index.md` link, failure-family taxonomy, project diagnostic spool schema, symptom-to-remediation table seed, debug-log lifecycle rule, interaction-region artifact rule, preview validation rule, and resource lifecycle/orphan diagnostics rule

Phase 0A exit criteria:

- New readback surfaces cannot be implemented until the path/readback policy exists and names normal-user, admin, prompt evidence, package, and preview/download path behavior.
- New workflow/evidence readback surfaces cannot be implemented until their `Cache-Control: no-store` behavior or explicit compatibility exception is documented and covered by tests.
- New route actions cannot be implemented until exposure class, account/auth boundary, and duplicate-run behavior are documented in the route action descriptor.
- New route actions or recommendations cannot be implemented until status vocabulary, action descriptor mapping, descriptor registry path, and complete canonical workflow action set browser-flow/API/disabled mappings are documented and covered by guard tests.
- New workflow recommendation behavior cannot expose a primary recommended action until the target action's route contract, descriptor, browser/API mapping, exposure class, account boundary, and disabled-state behavior are active for the current phase.
- New prototype-contract readback cannot be implemented until canonical path and mirror/cache behavior are documented and tested.
- New prompt-producing route work cannot be implemented until the common source-boundary schema and prompt-evidence guard exist.
- New P0/P1 conflict or generated exemption behavior cannot be implemented until the admin review queue sidecar/API contract exists and names metadata DB as the default admin query owner.
- New diagnostic-producing route work cannot be implemented until diagnostic spool metadata DB index ownership, minimum diagnostic record schema, minimum failure-family seed, deleted-project retention, and admin-review-queue relationship rules are documented.
- New scene-route, GDD document-generation, requirement-map, or contract-freeze work cannot be implemented until canonical structured game-type metadata ownership, hash canonicalization, and stale/missing domain codes are documented and covered by tests.
- New prompt/evidence persistence cannot be implemented until the secret redaction validator baseline passes fixture-based tests.
- New structured LLM or executable Codex route work cannot be implemented until the shared entrypoint guard and tests prove callers use the Phase service entrypoints instead of local provider/subprocess construction.
- New durable standards, route governance contracts, or cross-cutting architecture rules cannot be accepted until a Phase ADR, ADR update, or decision log records the authority and `docs/architecture/ADR_INDEX_PHASE.md` is updated when an ADR is created.
- The phase exit review template records route, artifact, API, browser surface, script, evidence, reviewer, consumed Phase 0A items, required Phase 0B items, and unresolved P0/P1/P2 count.
- Phase exit review evidence is written as a durable artifact under `logs/` and referenced by the implementation summary; chat text or PR prose alone is not sufficient evidence.
- Default evidence path: `logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-<n>-exit-review-<run_id>.json`, with `phase-<n>-exit-review-latest.json` allowed only as a pointer/readback copy. The JSON records `phase`, `run_id`, `reviewed_utc`, `reviewer`, `implemented_items`, `consumed_phase0a_items`, `required_phase0b_items`, `routes`, `artifacts`, `api_surfaces`, `browser_surfaces`, `scripts`, `evidence_refs`, `durable_decision_refs`, `unresolved_findings_by_severity`, and `regression_checks`. New reviews append new run-id files instead of overwriting prior evidence. If a different path is used, the implementation summary must link it and explain why.
- Phase 0A review records zero unresolved P0/P1/P2 findings before Phase 1 begins.

Phase 0B exit criteria:

- New UI-touching route work cannot be implemented until the Godot UI capability contract template exists and the denylist proves prompts do not import TapTap-only runtime terms.
- New styled UI-touching route work cannot be implemented until the Godot UI style contract template exists, at least one built-in Godot-native style contract exists, and the style technology-leakage denylist proves prompts do not import TapTapMarker-only runtime terms.
- New build, preview, package, repair, UI closure, or project-delete route work cannot be implemented until the full Godot diagnostics and quality-gate contract template exists and defines pre-build/pre-preview diagnostics, expanded diagnostic spool schema, expanded failure-family taxonomy, symptom remediation, debug-log lifecycle, interaction-region artifacts, preview validation, and resource lifecycle/orphan diagnostics.
- The Godot UI capability contract template must be linked from `docs/standards/_index.md` before a UI-touching route can depend on Phase 0B.
- The Godot UI capability contract template must also be linked from `README.md`, `docs/PROJECT_DOCUMENTATION_INDEX.md`, relevant Phase service architecture indexes, and agent-facing routing before a UI-touching route can depend on Phase 0B.
- The Godot UI style contract template and `docs/ui-style-guides/` catalog must be linked from `docs/standards/_index.md`, `README.md`, `docs/PROJECT_DOCUMENTATION_INDEX.md`, relevant Phase service architecture indexes, and agent-facing routing before a styled UI-touching route can depend on Phase 0B.
- The Godot diagnostics and quality-gate contract template must be linked from `docs/standards/_index.md` before build, preview, package, repair, UI closure, or project-delete routes can depend on Phase 0B. Phase 1 GDD/requirement/contract freshness diagnostics may use the Phase 0A minimum diagnostic index/schema before the full template is active.
- When the Godot diagnostics and quality-gate contract becomes a durable standards file, the implementation must also update `README.md`, `docs/PROJECT_DOCUMENTATION_INDEX.md`, relevant Phase service architecture indexes, and agent-facing routing, matching the standards index maintenance rule.
- The Phase 0B failure-family taxonomy seed must cover every initial symptom family listed in [07-godot-diagnostics-quality-gates.md](07-godot-diagnostics-quality-gates.md) before later route phases add more route-specific families.
- The Phase 0B UI style seed must cover at least one Godot-native built-in style with repo-owned internal ID, trigger taxonomy, canonical token format, core token families, semantic usage/action-role rules, UI family tier classification, core-minimum component defaults, theme resource slot mapping, runtime environment hash identity, source-name ownership, forbidden patterns, visual evidence self-description, and machine-readable contract. Non-core conditional families and advanced TapTapMarker capability packages are recorded as full-target requirements but do not block Phase 1 unless needed by the touched route.
- The Godot UI capability contract template must declare its canonical hash exclusions; an empty exclusion list is valid, but an implicit or undocumented exclusion list is not.
- The Godot UI style contract template must declare its canonical hash exclusions; an empty exclusion list is valid, but an implicit or undocumented exclusion list is not.
- Phase 0B review records zero unresolved P0/P1/P2 findings for the specific capability package a touched route consumes.

### Phase 1: Requirement Map And Contract Freshness

Deliverables:

- `GameDesignRequirementMapService`
- requirement map API/readback
- scene route confirmation sidecar/API or browser-flow writer that produces `meta/routes/scene-route/latest.json`
- GDD document-generation write-through that records `source_generated_gdd_hash` back to `meta/routes/scene-route/latest.json` after `docs/gdd/GDD.md` is generated
- prototype contract hash fields
- contract stale detection
- frontend requirement map panel
- first route module contracts for `structured-game-type-analysis`, `scene-route-confirmation`, `gdd-requirements`, `gdd-document-generation`, `prototype-contract`, and `prototype-skeleton-guard`
- prototype-skeleton compatibility guard for new-chain projects
- Phase 0B dependency matrix row for `prototype-skeleton-guard` is satisfied before the guard is implemented.
- first guard tests for source hashes, stale behavior, sidecar naming, operation status, and error envelope shape
- path/readback tests for requirement map and prototype contract readback
- canonical `routes/prototype-contract/latest.json` write/readback, optional mirror validation, and stale mirror rejection
- exposure-class and account-boundary tests for requirement map/freeze actions
- admin review queue sidecar/readback for requirement-map P0/P1 conflicts and generated exemptions
- source-boundary fields on prompt-producing requirement map and contract-freeze route evidence
- duplicate-run tests for requirement map generation and contract freeze
- requirement-map classification for Godot UI capability domains and prototype-contract freeze of the Godot UI contract hash
- UI style selection/readback and prototype-contract freeze of `ui_style_id`, `ui_style_version`, `ui_style_snapshot_hash`, and `source_ui_style_contract_hash`
- first failure-family taxonomy entries for GDD, legacy GDD form backfill, structured game-type metadata, scene route, scene confirmation, GDD document hash write-through, generated GDD mismatch, requirement map, contract stale, source unknown, UI contract unknown, prototype skeleton stale, and unmapped workflow recommendation
- route-specific expansion of the Phase 0 taxonomy seed for the first implemented `structured-game-type-analysis`, `scene-route-confirmation`, `gdd-requirements`, `gdd-document-generation`, and `prototype-contract` slices
- shared LLM/Codex entrypoint tests for new structured LLM or executable Codex callers touched by the first slice

Exit criteria:

- New deckbuilder project can generate requirement map and freeze a fresh contract.
- Scene route confirmation writes `meta/routes/scene-route/latest.json` with stable `confirmed_scene_route_hash`; requirement map generation fails closed without it.
- GDD document generation writes a matching `source_generated_gdd_hash` into `meta/routes/scene-route/latest.json`; requirement map generation fails closed when `docs/gdd/GDD.md` and the scene-route sidecar disagree without reconfirmation or a mismatch blocker.
- Requirement map generation fails closed when the current canonical structured game-type metadata hash differs from the scene sidecar `source_game_type_structured_hash`.
- Stale GDD blocks new iteration plan.
- Requirement map and contract sidecars use snake_case locally while API/readback exposes camelCase.
- Prototype contract authority is `routes/prototype-contract/latest.json`; any `meta/routes/prototype-contract/latest.json` mirror matches `contract_hash` or is treated as stale.
- New-chain skeleton creation cannot run from stale, missing, or unknown prototype-contract sources, and legacy skeleton readback cannot be used as final readiness evidence.
- Prompt-producing Phase 1 route state includes the common source-boundary object and saved prompt evidence proves no raw mutable game-type guide excerpt is used after freeze.
- Admin review queue blocks contract freeze for unresolved P0/P1 conflicts and exposes admin-only decision readback without leaking raw queue data to normal users.
- Tests for requirement map and contract freshness pass.
- Normal-user requirement map and prototype contract readback do not expose host paths, cross-account state, raw prompts, token material, or admin-only evidence.
- Requirement map generation and contract freeze handle double-click/retry/concurrent POST behavior without creating conflicting active runs.
- Requirement map and frozen contract preserve Godot UI capability domain inputs for UI/HUD/input/custom drawing/camera/animation/rendering/procedural/geometry/typed-state requirements.
- Prototype contract freezes the selected Godot UI style snapshot for UI-facing projects, and normal-user readback exposes style ID/version/hash without raw host paths or unapproved font paths.
- Requirement map generation and contract freeze use the shared Phase service LLM/Codex entrypoints and pass the required shared-entrypoint tests before caller-specific tests.
- GDD, scene route, requirement map, and contract freshness failures map to failure-family taxonomy entries and project diagnostic spool records where applicable.
- Phase 1 route module contract tests cover `structured-game-type-analysis`, `scene-route-confirmation`, `gdd-document-generation`, `gdd-requirements`, `prototype-contract`, and `prototype-skeleton-guard` before any downstream module generation can depend on them.
- Phase 1 may add route-specific failure families, but it must not shrink or redefine the Phase 0 initial symptom-family taxonomy.
- Route contracts and guard tests for `structured-game-type-analysis`, `scene-route-confirmation`, `gdd-document-generation`, `gdd-requirements`, `prototype-contract`, and `prototype-skeleton-guard` pass the P0/P1/P2 acceptance severity standard.
- Workflow recommendation tests prove Phase 1 does not recommend `create_prototype`, `create_iteration_plan`, `execute_next_goal`, `run_needs_fix`, `run_ui_closure`, or `preview_package` as the primary action until their later route contracts are active; these actions may appear only in `forbiddenActions[]` with disabled reasons.

### Phase 2: Iteration Plan Traceability Gate

Deliverables:

- iteration goals include requirement IDs
- required modules include requirement IDs and source reasons
- module plan confirmation UI
- block module generation on P0/P1 coverage gaps
- iteration-plan route contract and route action descriptor updates
- UI surface goals generated from the Godot UI capability contract
- UI style-aware goals generated from the frozen Godot UI style contract for UI-facing requirements
- interaction-region artifact requirement for UI/input/physics/camera-heavy iteration goals

Exit criteria:

- Every P0/P1 requirement is covered by plan or explicit blocker.
- Frontend module plan shows traceability.
- Deckbuilder default modules are visible as required modules with source.
- Every P0/P1 UI-facing requirement has an iteration goal or required module that names expected Godot UI surface, layout/input/focus/feedback requirements, and validation method.
- Every P0/P1 UI-facing requirement has style token expectations, design DNA/composition/motion expectations when applicable, UI tree readback expectations, visual evidence matrix requirements, or a `style_not_applicable` rationale before execution.
- UI/input/physics/camera-heavy P0/P1 goals include interaction-region artifacts or explicit `no_interaction_region_needed` rationales before execution.
- Iteration-plan service/API/readback and module confirmation UI pass Phase 0 route governance checks for route action descriptor, path/readback policy, exposure class, account boundary, duplicate-run behavior, `active_run_reused` response shape, source-boundary evidence, and secret redaction.
- Phase 2 review records zero unresolved P0/P1/P2 findings.

### Phase 3: Workflow Recommendation

Deliverables:

- workflow recommendation service/API
- frontend primary action driven by recommendation
- stale/blocking issue banners
- route action descriptor mapping for every recommendation in the complete canonical workflow action set
- status vocabulary mapping from route/readback state into display-stage state

Exit criteria:

- User sees one clear primary next step.
- Forbidden actions are disabled with reason.
- Existing advanced actions remain available only when route descriptors classify them as user-visible or safe secondary actions.
- Workflow recommendation extends or reads from the existing workflow route authority instead of introducing a competing next-action engine.
- Recommendation actions are checked against the route action descriptor and exposure classes so the frontend cannot recommend an admin-only, script-only, stale, or missing action to a normal user.
- `complete_gdd` returns the user to the existing GDD draft-completion flow or a declared non-action display state, and tests fail if it is emitted unmapped.
- `generate_gdd_document` triggers the GDD document-generation API/browser flow or a declared non-action display state, and tests fail if it is emitted unmapped.
- Browser status mapping distinguishes stage `completed`, route `succeeded`, UI matrix `covered`, and readiness `ready`.
- Phase 3 review records zero unresolved P0/P1/P2 findings.

### Phase 4: Execute Goal Freshness And Needs-Fix Tightening

Deliverables:

- execute-next-goal stale/missing guards
- requirement rows in goal input
- needs-fix reads requirement map and latest blocker
- frozen Godot UI capability contract injection for UI-touching goals
- frozen Godot UI style contract injection for styled UI-touching goals
- UI gap family mapping in needs-fix and repair prompts
- style-drift family mapping in needs-fix and repair prompts
- pre-build diagnostics gate and debug-log lifecycle checks for execute-next-goal, needs-fix, and repair

Exit criteria:

- Codex is not invoked when contract/map is stale.
- Codex is not invoked for build/repair/UI-touching work when required pre-build diagnostics fail or diagnostic prerequisites are missing.
- Goal execution prompt contains linked requirements.
- UI-touching goal prompts contain the frozen Godot UI capability contract and pass technology-stack leakage tests.
- Styled UI-touching goal prompts contain the frozen Godot UI style snapshot, generated theme resource refs, component defaults, component exception refs, composition rules, pointer/gesture rules, state ownership rules, UI lifecycle rules, scroll/virtualization policy, motion/transition rules, font-size unit policy, localization/overflow policy, UI tree readback requirements, visual evidence matrix requirements, and pass TapTapMarker technology-stack leakage tests.
- Styled UI-touching goal prompts and route states compare `source_ui_style_contract_hash` and `ui_style_snapshot_hash` against the current frozen prototype contract before Codex invocation.
- Failed acceptance maps back to a requirement or UI closure gap where possible.
- Needs-fix and repair can classify UI failures as layout, input/focus, feedback, custom drawing, camera/layer, rendering/material, animation, geometry sizing, procedural visualization, or typed state gaps.
- Needs-fix and repair classify style failures using the normalized style drift taxonomy from `06a-ui-style-migration-overview-and-catalog.md`. They must not maintain a shorter route-local taxonomy.
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
- Godot UI style validator for selected style ID/version/hash, repo-owned style identity, runtime environment identity, custom style metadata, structured alias approval refs, trigger tags, design DNA rules, canonical token usage, Godot theme slot mapping, theme resource token coverage, semantic usage/action-role rules, density/scale policy, generated theme resources, component defaults, component family baseline, component coverage matrix, variant coverage, component exception rule refs, forbidden patterns, pointer event shape, pointer/gesture phases, drag/drop payload lifecycle, state ownership rules, UI lifecycle rules, scroll/virtualization policy, motion/transition rules, composition rules, game composition templates, UI tree readback refs/rows, safe visual validation refs, visual evidence self-description, deterministic substitute limits, state tokens, contrast/readability, font-size unit policy, localization/overflow policy, icon/font policy, style composition, and normalized style-drift families
- preview validation loop, visual evidence, source-hash readiness, and resource lifecycle/orphan diagnostics for UI closure follow-up work
- explicit `no_ui_needed` and `style_not_applicable` exemption review/readback semantics

Exit criteria:

- Completed gameplay modules are checked for player-facing UI exposure.
- Missing UI surfaces are visible and actionable.
- UI closure validates Godot-specific capability fields and gap families instead of only checking that a named UI surface exists.
- UI closure validates Godot UI style fields and style-drift families instead of only checking that controls exist.
- Follow-up goals preserve requirement IDs, Godot UI capability domain, validation method, and source hashes.
- Follow-up goals preserve selected style ID/version/hash, runtime environment identity, expected token family, Godot theme slot or resource expectation, design DNA/composition/motion expectation when relevant, pointer/gesture and pointer-event-shape expectation, drag/drop payload expectation when applicable, state ownership expectation, UI lifecycle expectation, scroll/virtualization expectation, density/scale expectation when relevant, font-size/localization overflow expectation, UI tree readback requirement, visual evidence matrix requirement, normalized style-drift family, and visual validation method.
- Final package readiness can show UI closure blockers.
- `no_ui_needed` exempts only UI surface requirements; `style_not_applicable` exempts only style contract requirements; system-created P0/P1 exemptions stay blocked until the required review/confirmation metadata exists.
- Ordinary package download compatibility remains separate from final package readiness and cannot clear unresolved UI closure, diagnostics, source-boundary, style, or admin review blockers.
- UI closure and preview readiness cannot pass when diagnostics evidence, visual evidence, source hash set, lifecycle cleanup, or orphan diagnostics are missing for routes that require them.
- UI closure and preview readiness cannot pass when `source_ui_style_contract_hash` or `ui_style_snapshot_hash` is missing, stale, or different from the current frozen prototype contract for UI-facing work.
- UI closure service/API/readback passes Phase 0 route governance checks for path/readback policy, exposure class, account boundary, duplicate-run behavior, `active_run_reused` response shape, and secret redaction.
- Phase 5 review records zero unresolved P0/P1/P2 findings.

### Phase 6: Route Governance Guardrails

Phase 6 is a consolidation and expansion pass. It must not re-litigate or defer the Phase 0 baseline. It expands the already-created route governance primitives to every remaining route, admin script, readback surface, and durable standards document.

Deferred governance rule:

- Any item deferred from Phase 1-5 into Phase 6 must record owner, affected routes, severity, expiry or recheck trigger, proof that no current P0/P1/P2 gate is bypassed, and the exact Phase 6 acceptance test that will close it.
- A deferred item without expiry/recheck metadata is treated as an unresolved P2 and blocks the phase that tried to defer it.

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
- Godot UI style contract coverage across route contracts, tests, style catalog, font policy, generated theme resource refs, UI closure, admin readback, and durable standards docs
- full-target TapTapMarker non-technology UI capability closure ledger with final status for every capability package
- closure ledger schema validator and canonical capability-package inventory derived from `06a`, `06b`, `06c`, `06d`, and `07`
- Godot diagnostics and quality-gate contract coverage across route contracts, diagnostics guide, failure taxonomy, project diagnostic spool, admin triage, preview/package, resource lifecycle, and durable standards docs
- admin review queue coverage across route contracts, admin APIs, browser blocker summaries, exports, and guard tests
- final readiness boundary coverage that separates ordinary package download from full closure approval

Exit criteria:

- `structured-game-type-analysis`, `gdd-requirements`, `gdd-document-generation`, `scene-route-confirmation`, `prototype-contract`, `prototype-skeleton`, `workflow-recommendation`, `iteration-plan`, `execute-next-goal`, `needs-fix`, `repair`, `project-delete`, and `ui-wiring-closure` have route module contracts, route action descriptors, exposure classes, and guard-test coverage.
- `preview-package` routes are covered by Phase path/readback, capability exposure, account-boundary, package/preview/download reference, and host-path leakage tests; they do not need full route module contracts in this plan unless their behavior is changed beyond readback/package/preview/download governance.
- Even when `preview-package` does not receive a full route module contract, it must satisfy the preview/package readiness contract in `02b-backend-api-contracts.md`: source hash set, package artifact ref, preview ticket ref, ordinary-download compatibility, final-readiness eligibility, unresolved blocker counts, account boundary, and evidence refs.
- Guard tests fail when action names, status enums, source hash fields, error envelope shape, or source-boundary prompt rules drift.
- Guard tests fail when any action in the complete canonical workflow action set is unmapped, when status vocabulary sets are conflated, or when a prompt-producing route lacks valid source-boundary evidence.
- Path/readback tests prove normal users do not see host paths or cross-account admin review queue entries.
- Admin review queue tests prove unresolved P0/P1 blockers and system-created exemptions block the correct downstream routes until approved/deferred/resolved through auditable admin or allowed user decision paths; `rejected` and `backlog` remain blocking, and `deferred` requires scoped expiry/recheck metadata before any temporary unblock.
- Admin/backfill scripts produce append-only evidence under `logs/` with scoped IDs and sanitized paths.
- Runtime lifecycle guidance distinguishes expected process exits from crashes.
- Capability exposure tests prove normal users cannot invoke admin/script-only route actions by direct API call.
- Context-boundary tests prove client payload fields cannot spoof account/project/source/admin authority.
- Duplicate-run tests cover retry, double-click, and concurrent POST behavior for the main route actions.
- Secret redaction validators pass over route prompts, evidence, admin exports, and script evidence.
- Preflight checks report missing local dependencies without starting a workflow run.
- Godot UI capability contract is linked from durable docs, covered by guard tests, and consumed by `gdd-requirements`, `gdd-document-generation`, `prototype-contract`, `iteration-plan`, `execute-next-goal`, `needs-fix`, `repair`, and `ui-wiring-closure`.
- Godot UI style contract is linked from durable docs, covered by guard tests, and consumed by style selection, `prototype-contract`, `iteration-plan`, `execute-next-goal`, `needs-fix`, `repair`, `ui-wiring-closure`, and preview/package readiness.
- The full-target UI capability closure ledger at `logs/phase-a-innernet/reviews/gdd-to-module-hardening/full-target-ui-closure-ledger.json` has no row left as `not_consumed_by_first_slice` for any capability consumed by the implemented phases; remaining explicit deferrals include owner, affected routes, expiry or recheck trigger, validation evidence, and phase exit review refs.
- The full TapTapMarker non-technology UI capability target remains a program-level closure objective after the first slice. Phase 2-6 reviews must carry forward every `not_consumed_by_first_slice` row and may not mark final readiness for a route that consumes that capability until the ledger row is `covered` or `reviewed_not_applicable`.
- Closure ledger guard tests fail when the ledger omits a capability from the canonical inventory, includes an orphan capability not mapped to an owner doc, has an invalid `closure_status`, or lacks required evidence refs for `covered`, `reviewed_not_applicable`, or `explicitly_deferred` rows.
- Godot diagnostics and quality-gate contract is linked from durable docs, covered by guard tests, and consumed by build/validation, execute-next-goal, needs-fix, repair, UI closure, preview/package, and project-delete diagnostics.
- Project-delete route governance proves ordinary user deletion, admin diagnostic/admin-review preservation, deleted-project tombstones, account-boundary behavior, idempotency, duplicate request handling, and browser-safe errors are covered by route contract tests before Phase 6 exits.
- Project diagnostic spool supports deleted-project admin lookup, triage status, redaction status, retention class, and unresolved P0/P1/P2 preservation.
- Diagnostic spool retention/cleanup tests prove unresolved P0/P1/P2 records are preserved and resolved/ignored/backlog records retain enough replacement evidence for audit and repair explanation after compaction/redaction.
- Preview/package readiness tests prove final readiness cannot pass from stale source hashes, invalid tickets, missing package artifacts, missing browser-safe readback, unresolved diagnostics, source-boundary failures, style blockers, or unresolved admin review queue blockers.
- Durable route governance docs are linked from the relevant standards or workflow index.
- Phase 6 evidence proves each Phase 0 baseline primitive was reused and expanded, not duplicated as a competing contract.
- Phase 6 review records zero unresolved P0/P1/P2 findings.
