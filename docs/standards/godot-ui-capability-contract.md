# Godot UI Capability Contract

Status: Living standard
Language: English
Scope: Phase A/B hosted Godot implementation routes, GDD-to-module requirement mapping, prototype contract freeze, iteration planning, module execution, needs-fix/repair, UI closure, preview/package readiness, and browser-safe route readback.

## Purpose

This standard migrates the useful capability model behind TapTap UI workflow guidance into this repository as a Godot-only contract. It is not a technology migration. The contract treats UI system work as a first-class gameplay implementation domain and binds it to Godot 4.5/.NET semantics.

This standard consumes `docs/standards/godot-engine-semantics.md`. It does not redefine viewport modes, coordinate spaces, unit scale, input constants, camera projection, TileMap/map coordinates, geometry measurement, rendering resources, or curated reference-example rules.

Accepted architecture context: ADR-0036 for route recovery authority, ADR-0038 for evidence/readback, and the Godot template ADR index for runtime authority.

## Machine-Readable Contract

The runtime registry is `PhaseA.Platform/Workflow/GodotUiCapabilityContract.cs`.
The parity fixture is `PhaseA.Platform.Tests/Fixtures/godot-ui-capability-contract.v1.json`.
The deterministic test owner is `PhaseA.Platform.Tests/Workflow/GodotUiCapabilityContractTests.cs`.
Route readback enforcement is in `PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs`.

The registry owns:

- Contract id/version/hash.
- Forbidden technology terms that may appear only in migration rationale: `UrhoX`, `Urho3D`, `Lua`, `NanoVG`, `PBRNoTexture`, `.emmylua`.
- Capability domains and required workflow fields.
- Material, rendering, animation, and UI update ownership profiles.
- Workflow injection points.
- Governance rules and blocking diagnostic codes.

Do not add a UI capability domain, profile, governance rule, or blocking diagnostic code in docs only. Update registry, fixture, tests, and this document together.

## Technology Boundary

No implementation prompt, route state, UI closure output, or durable workflow standard may require UrhoX, Urho3D, Lua, NanoVG, PBRNoTexture, or `.emmylua`. Those terms are allowed only in conflict-assessment documentation or migration rationale.

Godot-owned equivalents:

- Runtime: Godot 4.5 + .NET/Mono and hosted Godot workspaces.
- Scripting: C# script ownership; typed GDScript only when an existing project already uses it.
- Custom drawing: `Control._draw`, `CanvasItem._draw`, `Line2D`, `Polygon2D`, `ArrayMesh`, `ImmediateMesh`, `SubViewport`, Godot materials, and shaders.
- Material/no-texture work: approved Godot material profiles in this standard.
- Size discipline: theme metrics, `Control.custom_minimum_size`, texture/import metadata, `AABB`, `get_aabb()`, collision shapes, or generated artifact metadata.
- Typing: C# types, typed GDScript where applicable, generated schema DTOs, and route-state JSON schema.

A technology-stack leak in executable route prompts or route state is a blocking `technology_stack_leakage` issue for P0/P1 work.

## Capability Domains

The workflow treats these domains as first-class prototype implementation capabilities whenever the GDD, scene route, prototype contract, or requirement map implies them:

| Domain id | Godot ownership | Required workflow data |
| --- | --- | --- |
| `ui_scene_architecture` | Control scenes, CanvasLayer HUDs, scene instancing, autoload boundaries, scene transitions, route-specific UI roots. | Scene path, node path, requirement IDs, player flow, state boundary, validation refs. |
| `layout_theme_responsive` | Container nodes, anchors, safe-area handling, theme resources, minimum sizes, fixed-format constraints, viewport-safe scaling. | Layout strategy, fixed-format rationale, theme/min-size source, viewport evidence. |
| `hud_menus_overlays` | CanvasLayer, modal controls, pause/menu overlays, notifications, status bars, combat HUD, inventory/deck/reward panels. | Overlay layer, modal blocking behavior, input routing, state synchronization, evidence refs. |
| `custom_2d_drawing` | Control._draw, CanvasItem._draw, Line2D, Polygon2D, draw invalidation, hit testing, redraw lifecycle. | Drawing surface, redraw trigger, hit-test path, visual feedback states, screenshot/canvas evidence. |
| `input_focus_navigation` | InputMap, mouse/touch events, keyboard focus, gamepad focus, drag/drop, hover/pressed/selected/disabled states. | Input paths, supported devices, focus status, drag/drop boundaries, disabled/error states, validation refs. |
| `camera_viewport_world_physics` | Camera2D, Camera3D, CanvasLayer, SubViewport, physics layers/masks, raycasts, world-space UI, screen-to-world transforms. | Camera owner, UI/world separation rule, raycast/input conversion path, layer/mask rationale, validation refs. |
| `rendering_materials_shaders` | CanvasItemMaterial, StandardMaterial3D, ShaderMaterial, import settings, render layers, lighting mode, repo-approved material profiles. | Material/rendering policy, source asset/import evidence, shader ownership, fallback policy. |
| `animation_state_machines` | AnimationPlayer, AnimationTree, state-machine resources, tweens, transitions, combat/character/UI animation states. | Animation profile, state reference, transition trigger, state enum/constant, validation refs. |
| `procedural_generation` | Deterministic seed inputs, generated map/route/deck/reward layouts, generated scene nodes, headless validation. | Seed/source, generated output summary, validation artifact, replayability rule. |
| `geometry_mesh_size` | AABB, get_aabb(), collision shapes, import metadata, ArrayMesh, ImmediateMesh, MeshInstance3D, Polygon2D, Line2D. | Size source, collision/interaction shape, fallback geometry API, validation ref. |
| `typed_state_schema` | C# enums/classes/records, typed GDScript where used, named constants, DTO/schema enums. | Typed state reference, enum source, schema field, invalid-state behavior, tests. |
| `accessibility_readability_feedback` | Theme contrast, readable font sizes, hover/focus/selected/disabled states, error copy, overflow handling. | Readability target, feedback states, screenshot/browser evidence, no-overlap validation. |

A phase cannot pass if an applicable P0/P1 domain is silently omitted from requirement map, iteration plan, execute-goal prompt, or UI closure.

## Profiles

Material profiles:

- `solid_3d_standard`
- `transparent_3d_standard`
- `solid_2d_canvas`
- `canvas_item_material`
- `shader_material`
- `existing_material_resource`

Rendering/atmosphere profiles:

- `ambient_3d_default`
- `directional_key_light`
- `local_light_group`
- `environment_fog_atmosphere`
- `postprocess_profile`
- `rendering_not_applicable`

Animation profiles:

- `animation_player_simple`
- `animation_tree_state_machine`
- `animation_tree_blendspace`
- `repo_character_animation_profile`
- `animation_not_applicable`

UI update ownership modes:

- `retained_typed_references`
- `registered_control_map`
- `state_apply_pass`
- `dynamic_item_factory`
- `no_dynamic_update`

Missing or unknown profiles block affected P0/P1 surfaces with `material_profile_missing`, `rendering_profile_missing`, `animation_state_profile_missing`, or `ui_update_ownership_missing`.

Third-person camera surfaces must provide `camera_controller_profile` when `third_person_camera_required` is true. Missing profile blocks with `third_person_camera_profile_missing`.

## Workflow Injection Points

| Route | Required integration |
| --- | --- |
| `gdd-question-form` | Optional UI-heavy flow hints; absence of user detail must not suppress default UI capability classification. |
| `scene-route-confirmation` | Each confirmed scene declares expected player-facing UI surfaces or `no_ui_needed`. |
| `gdd-document-generation` | Generated GDD includes UI/HUD/input/drawing/camera/animation/procedural/rendering implications when part of the prototype promise. |
| `gdd-requirements` | Extracts UI requirements and assigns severity, source section, scene mapping, module mapping, capability domains, and acceptance markers. |
| `prototype-contract` | Freezes Godot UI capability contract version/hash and links it to source artifact hashes. |
| `iteration-plan` | Creates UI surface goals and required modules from P0/P1 requirements. |
| `execute-next-goal` | Injects the frozen Godot UI capability contract for relevant goals and requires evidence before completion. |
| `needs-fix` | Maps UI failures back to requirement IDs and UI gap families instead of generic fix prompts. |
| `repair` | Keeps repair prompts bound to requirement IDs, diagnostics, and UI capability gaps. |
| `ui-wiring-closure` | Validates the complete UI surface matrix, profiles, evidence, and exemptions. |
| `preview-package` | Exposes final-readiness blockers from UI closure while preserving early package behavior. |

## UI Closure Readback Fields

`meta/routes/ui-wiring/latest.json` should include `ui_surface_matrix` rows. For covered visible surfaces, these fields are required by readback enforcement:

- `feature`
- `priority`
- `status`
- `capability_domain_ids`
- `godot_scene_path` or `godot_node_path`
- `godot_surface_type`
- `layout_strategy`
- `input_paths`
- `feedback_states`
- `camera_layer_boundary`
- `viewport_mode`
- `ui_update_ownership_mode`
- `state_boundary`

Profile fields are validated when present: `material_profile`, `rendering_profile`, and `animation_profile`.

A P0/P1 `no_ui_needed` row must include review metadata: `decision_by`, `decision_role`, `decision_utc`, `decision_reason`, `affected_requirement_ids`, and `evidence_refs`. System-created P0/P1 exemptions remain blocked until an admin or allowed user confirmation resolves them.

## Governance Rules

The machine-readable registry owns the rule list. The operational summary is:

- P0/P1 gameplay features need visible player entry, feedback, state boundary, and validation evidence unless `no_ui_needed` is explicitly reviewed.
- `no_ui_needed` exempts only UI surface requirements. It does not exempt style validation for visible surfaces or final-readiness evidence.
- Prefer Control, Container, Theme, anchors, and safe areas. Absolute positioning requires fixed-format or world-overlay rationale.
- HUD and menus must declare CanvasLayer/viewport ownership and input routing.
- Drag/drop and pointer-heavy features must declare start, hover, cancel, drop, invalid drop, and commit states.
- Custom drawing must declare Godot drawing API, redraw trigger, hit-test strategy, and screenshot/canvas evidence.
- Camera/physics interactions must use named layers/masks and measurable boundaries.
- Rendering/material/shader work must use approved Godot profiles or block.
- Size-sensitive work must cite measured or documented size sources.
- Missing built-in geometry must use Godot geometry APIs with validation evidence.
- UI mode, animation state, input state, route state, and validation status must use enums, named constants, or schema enums.
- Procedural UI/world generation must be seedable, replayable, and validated.
- High-risk visual UI changes require screenshot, canvas-pixel, or exported visual evidence unless a recorded harness limitation and substitute deterministic check exists.
- Dynamic UI must declare construction owner and update ownership mode.
- Third-person camera behavior must use or create the repo-owned shared rig/profile before gameplay-specific camera work.
- Lighting, fog, sky, environment, and postprocess work must select a rendering/atmosphere profile with readability evidence.
- Character animation/state-machine work must select an animation profile with typed state and fallback behavior.

A touched route cannot mark an applicable Godot UI governance rule as not-yet-active. Rule exceptions require structured rationale in route state or phase review evidence and cannot be buried in chat text.

## Validation

Minimum deterministic validation for contract changes:

```powershell
dotnet test PhaseA.Platform.Tests --filter "FullyQualifiedName~GodotUiCapabilityContractTests|FullyQualifiedName~ProjectRouteStateArtifactServiceTests"
```

When the change also affects browser route contracts, run browser readback tests and the GDD-to-module hardening smoke described in `docs/standards/phase-service.md`.
