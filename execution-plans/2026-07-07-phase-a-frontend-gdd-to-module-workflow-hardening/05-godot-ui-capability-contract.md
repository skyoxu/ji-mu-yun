# Godot UI Capability Contract Migration

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 1112-1230.

## 11.2 Godot UI Capability Contract Migration

This section migrates TapTap's UI system capability model into this repository as a Godot-only workflow contract. It is not a technology migration. The source capability idea is: UI system work is a first-class gameplay implementation domain, custom drawing has explicit rules, camera/physics/rendering/animation/procedural systems affect player-facing UI, geometry sizes cannot be guessed, enum/state typing matters, and runtime-specific constraints must be governed.

This contract consumes the Godot engine semantic baseline in `04d-godot-engine-semantics-and-reference-examples.md` for viewport/resolution mode, coordinate spaces, unit scale, input constants, camera projection, TileMap/map coordinates, and curated reference-example use. UI capability work must not redefine those baseline semantics locally.

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
- UI, HUD, custom drawing, camera, input, map, and interaction-region capability rows consume the selected Godot viewport/coordinate/reference-example mode from `04d-godot-engine-semantics-and-reference-examples.md`; missing semantic mode evidence blocks completion for affected P0/P1 rows.

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
- `no_ui_needed` exemption records include reason, decision role, decision timestamp, requirement IDs, and evidence refs; system-created P0/P1 exemptions remain `needs_review` until admin or allowed user confirmation resolves them.

### 11.2.4 Godot Governance Rules

1. No P0/P1 gameplay feature is complete without visible player entry, feedback, state boundary, and validation evidence unless `no_ui_needed` is explicitly justified.
   - `no_ui_needed` exempts only the UI surface requirement. It does not exempt style contract requirements for visible UI, diagnostics, source-boundary checks, or final-readiness evidence.
   - A visible UI surface still needs style validation unless a separate `style_not_applicable` exemption is recorded under the style contract.
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
- Tests fail if `no_ui_needed` is used to bypass style validation for a visible surface or if `style_not_applicable` is used to bypass required UI surface evidence.
- System-created P0/P1 `no_ui_needed` exemptions cannot pass final readiness without required review/confirmation metadata.
- The final phase review confirms zero unresolved P0/P1/P2 findings across all governance rules touched by the migration.
