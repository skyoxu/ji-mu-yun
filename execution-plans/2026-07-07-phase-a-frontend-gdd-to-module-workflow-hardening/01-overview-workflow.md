# Overview, Goals, Workflow, Severity

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 1-99.

# Phase A Frontend GDD-To-Module Workflow Hardening Plan

Status: Primary split plan section
Date: 2026-07-07
Owner: Phase A platform
Scope: Frontend-visible GDD -> scene route -> requirement map -> prototype contract -> iteration plan -> execute-next-goal -> UI closure workflow hardening

## 1. Background

The current frontend workflow already has the core chain: GDD form, scene confirmation, GDD generation, prototype contract, iteration plan, execute-next-goal, needs-fix, repair, preview, and package. Recent work added game-type Default Prototype Contract support and a project-level `contractSnapshot` to reduce template drift.

However, the current chain still has three structural risks:

1. The transformation from GDD to executable modules does not yet have an explicit `GDD Requirement Map`, so it is difficult to prove that the real GDD requirements were fully carried into downstream modules.
2. `routes/prototype-contract/latest.json` does not yet record strong provenance against the GDD, confirmed scene route, and project contract snapshot, so downstream steps can continue using stale contract or stale module plans after source changes.
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
9. Migrate TapTapMarker's UI style theme discipline into a Godot-only UI style contract so generated UI uses a selected, versioned visual theme with trigger rules, palette, typography, radius, shadow, density/scale policy, component defaults, font assets, composition examples, forbidden patterns, and visual validation.

## 3. Non-Goals

1. Do not copy Taskmaster triplets, overlays, or the formal Chapter 6 pipeline directly into frontend projects.
2. Do not force old projects through a destructive migration. Old projects should be lazily backfilled or shown as missing the new artifacts.
3. Do not allow downstream workflows to freely reread `docs/game-type-guides` as a new gameplay authority after GDD generation.
4. Do not silently refresh confirmed contracts. When GDD or scene route changes, prompt for explicit user confirmation.
5. Do not refactor the Godot generator itself in this plan. This plan focuses on inputs, contracts, module planning, workflow state, and frontend governance.
6. Do not copy TapTap's TypeScript/MCP feature layout directly. Borrow its boundary, guard, CLI, logging, and documentation patterns only where they fit the Phase A C# service and browser workflow.
7. Do not import TapTap's UrhoX, Urho3D, Lua, NanoVG, PBRNoTexture, `.emmylua`, or Maker runtime assumptions. All migrated UI capability requirements must be expressed with Godot 4.5/.NET-compatible concepts and repository-owned validation.
8. Do not copy TapTap's local-only LSP, preview, logging, or disposal mechanics literally. Quality gates in this plan must use Godot 4.5, C#/.NET, GdUnit4, Phase route evidence, sanitized readback, and hosted workspace/account boundaries.
9. Do not copy TapTapMarker's UI runtime, Widget API, Yoga layout layer, NanoVG drawing layer, Lua code templates, or font files into this repo. UI style migration in this plan must use Godot `Theme`, `StyleBox`, `FontFile`, `Control`, `Container`, `CanvasLayer`, scene templates, and repo-owned font/license policy.

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
   - The system freezes the prototype contract and records artifact-local source hashes (`source_gdd_hash`, `source_scene_route_hash`, `source_requirement_map_hash`, `source_contract_snapshot_hash`, `source_godot_ui_contract_hash`, `source_ui_style_contract_hash`, `ui_style_snapshot_hash`) with camelCase API/readback projections.
7. `prototype-skeleton`
   - If the project has no prototype state yet, create the first playable M1 skeleton from the frozen GDD contract. New-chain skeleton creation must record source hashes and cannot bypass stale/missing prototype-contract guards.
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
