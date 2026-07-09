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
    - Required workflow data: camera owner, UI/world separation rule, raycast/input conversion path, layer/mask rationale, third-person camera rig/profile when applicable, validation references.
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

### 11.2.2.1 Godot Geometry, Size, And Material Profiles

The TapTap rules for built-in model dimensions, `CustomGeometry`, and `PBRNoTexture` translate into Godot-owned implementation profiles. These profiles are capability-contract constraints, not a new asset pipeline.

Size and primitive rules:

- Built-in primitives, imported 3D models, generated meshes, collision shapes, textures, and fixed-format UI surfaces must cite a measured or documented size source before implementation can complete.
- Accepted size sources are `AABB`, `get_aabb()`, collision shape dimensions, texture/import metadata, `Control.custom_minimum_size`, theme metrics, documented built-in primitive specs, or generated artifact metadata.
- A route must not assume that a box, sphere, capsule, imported mesh, texture, or UI panel has a specific size because another engine or example used that size.
- Size-sensitive work must record the coordinate space of the measurement: 3D world, Node2D local/global, Control local, viewport, TileMap cell, or texture pixel space.

Geometry fallback rules:

- When Godot built-ins do not provide the needed shape, the route must use a Godot geometry API such as `ArrayMesh`, `ImmediateMesh`, `MeshInstance3D`, `Polygon2D`, `Line2D`, `MeshInstance2D`, or a repo-owned generated scene/resource.
- The route must record the fallback geometry API, vertex/source data owner, collision or interaction shape, redraw/update lifecycle when applicable, and validation evidence.
- Custom geometry is not accepted as a shortcut around size evidence; it still needs bounds, collision/hit-test, and screenshot or deterministic geometry evidence.

Pure-color and no-texture material profiles:

| Profile | Use when | Required source/evidence |
| --- | --- | --- |
| `solid_3d_standard` | Opaque 3D object uses a generated or existing `StandardMaterial3D` with color parameters and no texture dependency. | Color source, roughness/metallic/transparency policy when relevant, owning scene/resource/code path, screenshot or render evidence. |
| `transparent_3d_standard` | Transparent glass/ghost/selection volume uses a generated or existing `StandardMaterial3D` with explicit alpha/transparency policy. | Alpha policy, sorting/visibility risk note when relevant, owning scene/resource/code path, screenshot evidence. |
| `solid_2d_canvas` | 2D or UI visual can be expressed through `ColorRect`, `CanvasItem` modulation, `StyleBoxFlat`, or `_draw` color calls. | Token/color source, target node path or theme slot, viewport/layout evidence. |
| `canvas_item_material` | 2D rendering needs a Godot `CanvasItemMaterial` behavior such as blend/light behavior beyond a simple color. | Existing or generated resource path, parameter source, fallback behavior, screenshot/canvas-pixel evidence. |
| `shader_material` | A shader is required for a visual effect that cannot be expressed by standard material/theme/draw APIs. | Existing repo shader path or generated shader artifact, parameter schema, fallback behavior, package/export validation, screenshot evidence. |
| `existing_material_resource` | The project already owns a `.tres`, `.res`, imported material, or scene-embedded material. | Discovered resource path or scene/import metadata, ownership reason, package/export validation. |

Material path and texture rules:

- Prompts must not guess material, shader, texture, or style resource paths. Paths must come from existing repo files, generated artifacts, import metadata, scene references, or a repo-approved profile that creates the resource.
- Pure-color/no-texture work should prefer generated `StandardMaterial3D`, theme/style resources, `ColorRect`, modulation, or `_draw` colors before introducing texture dependencies.
- External texture/material pipelines are blocked unless the GDD/prototype contract requires them and the route records asset source, license, import settings, package validation, and browser-safe readback refs.
- If a profile above is insufficient, the route must either extend the repo-approved material profile list with tests/evidence or block with a structured `material_profile_missing` diagnostic owned by the diagnostics contract.

### 11.2.2.2 Godot Rendering And Atmosphere Profiles

The TapTap rendering recipe discipline translates into a Godot rendering/atmosphere profile. Lighting, fog, sky, and postprocess are scene-level visual systems; generated routes must not scatter arbitrary light nodes or environment resources without ownership and evidence.

Allowed rendering/atmosphere profiles:

| Profile | Use when | Required source/evidence |
| --- | --- | --- |
| `ambient_3d_default` | A simple 3D scene needs readable base lighting without a specific mood. | `WorldEnvironment`/`Environment` owner or explicit not-needed rationale, at least one light owner, screenshot evidence. |
| `directional_key_light` | Outdoor, tactical, platformer, or character scene needs a primary sun/key light. | `DirectionalLight3D` owner, energy/shadow policy, rotation/source rationale, screenshot evidence. |
| `local_light_group` | Scene needs one or more `OmniLight3D`/`SpotLight3D` lights for props, pickups, rooms, effects, or combat readability. | Light list, purpose per light, energy/range/shadow policy, performance note, screenshot evidence. |
| `environment_fog_atmosphere` | Scene uses fog, sky, background color, ambient light, or mood/visibility atmosphere. | `WorldEnvironment`/`Environment` resource owner, fog/sky/background parameters, visibility/readability evidence, screenshot evidence. |
| `postprocess_profile` | Scene uses glow, tonemap, exposure, color correction, vignette-like shader, or other postprocess. | Environment/shader owner, parameter source, fallback behavior, performance/export validation, screenshot evidence. |
| `rendering_not_applicable` | Feature has no rendered 3D/2D visual effect beyond existing UI/style resources. | Not-applicable rationale and affected requirement IDs. |

Rendering rules:

- Routes must declare the owner of `WorldEnvironment`, `Environment`, light nodes, sky/fog/background settings, postprocess resources, and any scene-specific rendering override.
- Light energy, range, shadow settings, fog density, exposure, and glow/postprocess settings must come from a profile, existing resource, or route evidence. Do not guess numeric values without a rationale and validation.
- Rendering profiles must account for player readability. A dark, foggy, bloom-heavy, or heavily color-graded scene needs visual evidence that UI, interactable objects, enemies, paths, and collision/interaction cues remain readable.
- External rendering/shader resources follow the material path rules above. Missing rendering ownership or missing atmosphere profile blocks with `rendering_profile_missing`.

### 11.2.2.3 Godot Character Animation State Profiles

The TapTap FSM/BlendSpace rule translates into Godot `AnimationPlayer`/`AnimationTree`/state-machine ownership. Character animation must be a typed state system, not scattered string calls.

Allowed animation profiles:

| Profile | Use when | Required source/evidence |
| --- | --- | --- |
| `animation_player_simple` | A character or UI element has a small fixed set of clips and direct transitions. | `AnimationPlayer` owner, clip names, typed state enum or constants, transition triggers, missing-clip behavior, screenshot or test evidence. |
| `animation_tree_state_machine` | Character locomotion/combat needs explicit states such as idle, walk, run, jump, attack, hit, dead. | `AnimationTree` owner, state-machine resource/path, typed state enum, transition table, fallback state, validation evidence. |
| `animation_tree_blendspace` | Movement direction, aim, or locomotion requires blend space behavior. | BlendSpace owner/resource, blend parameter source, input vector/camera-relative owner, clamp/fallback policy, validation evidence. |
| `repo_character_animation_profile` | A route uses a repo-owned character animation template/profile once available. | Template path/version, clip/state mapping, required assets, validation evidence. |
| `animation_not_applicable` | Feature has no animated character/UI state. | Not-applicable rationale and affected requirement IDs. |

Animation rules:

- Feature scripts must not scatter raw `Play("clip")` or animation-state strings without a typed owner. Clip names may appear only at the profile/template boundary or in a declared mapping table.
- Animation state must be separate from authoritative gameplay state. Gameplay owns facts such as grounded/attacking/dead; the animation profile maps those facts to animation states.
- Every character animation route must declare transition triggers, invalid transition behavior, missing clip/resource behavior, fallback state, and validation evidence.
- Third-person character routes must align character animation state with the third-person camera profile and input/movement owner. Camera-relative movement and animation blend parameters must not be computed independently in unrelated scripts.
- Missing or undeclared animation profile blocks with `animation_state_profile_missing`.

### 11.2.2.4 Godot UI Construction And Update Ownership

The TapTap UI pattern of declaratively building a tree once and then updating it through explicit references or registries translates into a Godot-owned UI ownership rule. Generated Godot UI must declare how the UI tree is built, how later state changes reach controls, and who owns cleanup.

Construction rules:

- Prefer a stable UI tree built once from `.tscn` scenes, `PackedScene` instancing, or deterministic `_Ready()` construction. Do not rebuild the whole UI tree on every state change, frame, or route event.
- Dynamic lists, card hands, inventories, reward choices, route nodes, and generated panels may create/remove child items, but the owning container, item factory, item identity key, and cleanup path must be declared.
- UI controls must not become the authoritative gameplay state store. Controls reflect state owned by a typed C#/GDScript model, route state, view model, presenter, or scene owner.

Update ownership modes:

| Mode | Use when | Required source/evidence |
| --- | --- | --- |
| `retained_typed_references` | A UI surface has a small number of dynamic controls such as labels, bars, buttons, or one selected panel. | Typed fields or exported node paths, `_Ready()` binding point, update method, null/missing-node behavior, screenshot or deterministic UI evidence. |
| `registered_control_map` | A HUD, inventory, card hand, route map, or multi-panel UI needs many controls or cross-method updates. | Registry owner, control key schema, registration lifecycle, removal cleanup, state-to-control mapping, evidence that stale controls are not updated. |
| `state_apply_pass` | A surface can be updated through a single `ApplyState(...)`, presenter, view model, or render pass without exposing many individual controls. | State type/schema, owner method, idempotency rule, event/signal source, validation evidence. |
| `dynamic_item_factory` | Repeated UI rows/cards/nodes are generated from data. | Item scene/resource or factory owner, stable item key, diff/rebuild policy, cleanup path, focus/input restoration, evidence for add/remove/update cases. |
| `no_dynamic_update` | A surface is static after creation. | Static rationale, source requirement IDs, screenshot/readback evidence. |

Invalid update patterns:

- Repeated string-path `GetNode` calls scattered across unrelated methods without a binding owner.
- Rebuilding the full UI tree as a substitute for updating state.
- Duplicating nodes on every update without identity keys and cleanup.
- Hiding update ownership in assistant prose without route-state fields or evidence.
- Directly reading UI label/button text as gameplay state when a typed state owner should exist.

### 11.2.2.5 Godot Third-Person Camera Rig Profile

For this repository, the recommended "camera library" shape is a reusable Godot scene rig with a C# controller component:

- Scene resource: `Game.Godot/Scenes/Camera/ThirdPersonCameraRig.tscn`.
- Script owner: `Game.Godot/Scripts/Camera/ThirdPersonCameraRig.cs`.
- Expected node shape: `Node3D` rig root, target/follow reference, optional yaw/pitch pivot nodes, optional `SpringArm3D` for collision, and a child `Camera3D`.
- Configuration surface: exported `NodePath` or typed references for target and camera nodes, exported yaw/pitch limits, distance, shoulder offset, smoothing, collision mask, and input action names.
- Evidence surface: scene load validation, camera-state evidence, input action mapping, collision/occlusion check when enabled, screenshot or camera transform evidence for follow/orbit cases.

Third-person camera rules:

- Gameplay modules must configure or instance the repo-owned rig/profile instead of hand-writing orbit position, target offset, yaw/pitch sign, smoothing, collision, or camera-relative movement math.
- If the repo-owned rig/profile does not exist when a route needs third-person camera behavior, the route must create or declare that shared profile first. It must not hide one-off camera math inside a gameplay script.
- Yaw update semantics must stay owned by the rig/profile. Route prompts must not ask downstream repair to "flip" or "reverse" yaw signs unless a failing camera-state test proves the rig profile itself is wrong.
- Camera-relative movement must name the owner of input vector conversion and the camera transform used for conversion. Numeric input codes, unnamed collision masks, and ad hoc camera node paths are not accepted.
- A third-person camera route must record `camera_controller_profile`, rig scene/script refs, target path, input actions, collision policy, and camera-state validation refs in route state or UI closure evidence.

Acceptance criteria:

- Requirement-map generation can classify each applicable domain above as a requirement kind, acceptance marker, or explicit not-applicable rationale.
- Iteration-plan generation can create a goal for each applicable P0/P1 domain or block with a structured reason.
- UI closure can validate each applicable domain through `ui_surface_matrix` fields and evidence references.
- Deckbuilder reference coverage includes route-map UI scene architecture, route path custom drawing or visible node affordance, hand-card drag/drop input, combat HUD feedback, reward selection UI, and state-machine/typed-state references.
- A phase cannot pass if any applicable P0/P1 domain is silently omitted from requirement map, iteration plan, execute-goal prompt, or UI closure.
- The capability checklist is considered complete only when review records zero unresolved P0/P1/P2 findings.
- UI, HUD, custom drawing, camera, input, map, and interaction-region capability rows consume the selected Godot viewport/coordinate/reference-example mode from `04d-godot-engine-semantics-and-reference-examples.md`; missing semantic mode evidence blocks completion for affected P0/P1 rows.
- Geometry, size, and material rows consume the selected profile above or a documented extension. Missing size evidence, invented resource paths, or missing material profiles block completion for affected P0/P1 rows.
- Dynamic UI rows consume one construction/update mode above or a documented extension. Missing construction owner, update mode, state owner, or cleanup path blocks completion for affected P0/P1 rows.
- Third-person camera rows consume the repo-owned rig/profile above or block with a documented `third_person_camera_profile_missing` diagnostic. Hand-rolled orbit math in feature scripts blocks completion for affected P0/P1 rows.
- Rendering/atmosphere rows consume one rendering profile above or block with `rendering_profile_missing`. Missing light/environment ownership, guessed rendering values, or unreadable visual evidence blocks completion for affected P0/P1 rows.
- Character animation rows consume one animation profile above or block with `animation_state_profile_missing`. Scattered raw animation strings, missing transition ownership, or missing fallback behavior blocks completion for affected P0/P1 rows.

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
13. Pure-color/no-texture material work must select `solid_3d_standard`, `transparent_3d_standard`, `solid_2d_canvas`, `canvas_item_material`, `shader_material`, or `existing_material_resource`, or block with `material_profile_missing`. It must not guess material, shader, or texture paths.
14. Dynamic UI must declare a construction owner and one update ownership mode: `retained_typed_references`, `registered_control_map`, `state_apply_pass`, `dynamic_item_factory`, or `no_dynamic_update`. Missing ownership or cleanup evidence blocks P0/P1 UI completion.
15. Third-person camera behavior must use the repo-owned `ThirdPersonCameraRig` scene/script profile once available. Until it exists, third-person camera routes must create or declare that shared profile before gameplay work; feature scripts must not duplicate orbit math or yaw sign handling.
16. Lighting, fog, sky, environment, and postprocess work must select a rendering/atmosphere profile, declare scene/resource ownership, and provide readability evidence. Missing ownership or guessed rendering values block P0/P1 visual completion.
17. Character animation/state-machine work must select an animation profile, declare `AnimationPlayer`/`AnimationTree` ownership, use typed animation states or mappings, and define fallback/missing-clip behavior.

Acceptance criteria:

- The full governance checklist remains in scope for the migration. A phase may mark a rule as not-yet-active only when no touched route, artifact, prompt, or UI surface depends on that rule and the phase review records proof.
- A touched route cannot mark an applicable Godot UI governance rule as not-yet-active.
- Any violation of rules 1, 2, 3, 4, 5, 8, 9, 10, 13, 14, 15, 16, or 17 for a P0/P1 requirement is a blocking P1 or higher issue.
- Rule exceptions require structured rationale in route state or phase review evidence and cannot be buried in chat text.
- Tests fail if `no_ui_needed` is used to bypass style validation for a visible surface or if `style_not_applicable` is used to bypass required UI surface evidence.
- System-created P0/P1 `no_ui_needed` exemptions cannot pass final readiness without required review/confirmation metadata.
- The final phase review confirms zero unresolved P0/P1/P2 findings across all governance rules touched by the migration.
