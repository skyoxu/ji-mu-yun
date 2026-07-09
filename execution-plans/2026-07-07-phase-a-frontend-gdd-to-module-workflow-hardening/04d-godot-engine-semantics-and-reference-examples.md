# Godot Engine Semantics And Reference Examples

Source: post-split hardening requirement derived from review of engine-semantics gaps. This document is not part of the original monolithic source coverage; it is tracked by `97-split-added-requirements-ledger.md`.

## Purpose

This document defines a Godot-owned baseline for engine semantics and reference-example use before GDD-to-module implementation work begins. It preserves the useful idea behind TapTapMarker's `nvg-resolution-mode` rule without importing NanoVG, UrhoX, Lua, or TapTapMarker runtime technology.

The core rule is: implementation routes must not guess resolution, coordinate space, unit scale, input constants, camera projection, physics semantics, or TileMap/map coordinates from another engine. They must resolve the Godot semantic context first, then implement from the GDD, requirement map, prototype contract, and route recovery sources.

## Trigger And Skip Rules

SKIP when:

- The route is pure metadata, account, audit, export, or text-only planning work and does not create or validate Godot runtime code, scenes, UI, input, physics, camera, map, rendering, preview, or package artifacts.

MUST trigger when the touched route, requirement, goal, or repair step involves any of:

- Player-facing UI, HUD, overlays, menus, tooltips, dialogs, readable text, or layout.
- Custom drawing through `Control._draw`, `CanvasItem._draw`, `Line2D`, `Polygon2D`, `MeshInstance2D`, `ArrayMesh`, `ImmediateMesh`, shaders, or SubViewport rendering.
- Camera2D, Camera3D, viewport, zoom, world-to-screen, screen-to-world, or click/drag hit testing.
- Third-person 3D camera, orbit/follow camera, shoulder camera, camera collision, camera smoothing, or camera-relative movement.
- Character movement, physics, collision, Area/Body signals, ray casts, navigation, or interaction regions.
- TileMap, TileSet, grid/cell coordinates, map painting, terrain, path maps, minimaps, or route maps.
- Rendering, material, shader, texture import, built-in primitive sizing, procedural geometry, mesh fallback, or any generated visual resource path.
- Screenshot/canvas-pixel evidence, preview/package readiness, visual evidence, or browser-safe readback involving runtime visuals.

MUST block or produce an explicit implementation blocker when:

- A plan or prompt requires hard-coded screen size, DPI, tile size, camera zoom, world scale, input button number, physics layer/mask number, or layout coordinate without a source or conversion rule.
- A route mixes screen, viewport, UI local, world, TileMap cell, or physics coordinates without naming the conversion path.
- A route relies on official examples as product requirements instead of API/implementation references.
- A route assumes built-in primitive dimensions, imported mesh extents, collision bounds, texture size, material resource paths, shader paths, or generated asset paths without a measured source, documented built-in source, import metadata, generated artifact reference, or repo-approved profile.
- A third-person camera route hand-rolls orbit position, yaw sign, pitch clamp, target offset, camera collision, or camera-relative movement when a repo-owned camera rig/profile exists, or when the route should first create that shared profile.

## Godot Semantic Baseline

Implementation prompts, route-state artifacts, and acceptance evidence must use Godot terms and must declare the relevant semantic family before executable work starts.

Minimum semantic families:

- Unit scale: 3D positions, distances, velocities, and collision dimensions are treated as Godot project units with meter-like interpretation unless the project standard declares otherwise. 2D positions, Control sizes, and TileMap cells must not be conflated with 3D world scale.
- Coordinate spaces: distinguish screen coordinates, viewport coordinates, Control local coordinates, CanvasLayer coordinates, Node2D local/global coordinates, Camera2D world coordinates, TileMap cell coordinates, and 3D world coordinates.
- Viewport and resolution: declare whether the work uses fixed design resolution, responsive Control layout, camera/world scaling, or viewport-size-driven drawing. Physical window size, project stretch settings, viewport size, UI logical size, and screenshot evidence dimensions must not be treated as the same value without an explicit rule.
- Input constants: InputMap actions, Godot enums, named constants, or route schema enum values are required. Numeric mouse buttons, key codes, collision layers, or mode values are not accepted unless they are generated from a named fixture or documented constant source.
- Physics and collision: declare body type, collision layer/mask ownership, Area/Body signal ownership, raycast coordinate space, and physics-process ownership before accepting movement or collision behavior.
- Camera and projection: declare Camera2D/Camera3D owner, zoom/FOV, projection assumptions, and screen/world conversion when click, drag, aiming, route-map selection, or viewport evidence depends on camera state.
- Third-person camera: use a repo-owned Godot camera rig/profile before implementing gameplay-specific third-person camera behavior. The preferred repository shape is a reusable scene rig plus C# controller component, such as `Game.Godot/Scenes/Camera/ThirdPersonCameraRig.tscn` backed by `Game.Godot/Scripts/Camera/ThirdPersonCameraRig.cs`, with exported target/camera/spring-arm paths and typed configuration. Gameplay modules may configure the rig, but must not duplicate orbit math or invert yaw semantics locally.
- TileMap and map drawing: declare tile size, cell coordinate source, world/local conversion, TileSet collision/navigation/occlusion ownership, and map evidence refs before generated map logic or map UI is accepted.
- Geometry and size measurement: built-in primitives, imported meshes, generated meshes, collision shapes, and UI/world hit zones must cite `AABB`, `get_aabb()`, collision shape dimensions, texture/import metadata, `Control` minimum size, or another documented source. Guessing dimensions is a blocker.
- Rendering and material resources: pure-color, no-texture, shader, imported texture, and generated material work must declare the Godot material profile, resource ownership, path source, fallback behavior, and validation evidence. Resource paths must come from existing repo files, generated artifacts, import metadata, or a repo-approved profile; prompts must not invent material, texture, or shader paths.

## Godot Resolution And Viewport Mode

The Godot equivalent of a NanoVG resolution mode is a viewport/scale decision recorded before UI, map, camera, or custom drawing work proceeds.

Recommended modes:

| Mode | Use when | Required evidence |
| --- | --- | --- |
| Fixed design resolution | The GDD or style contract names a target resolution or fixed-format board/map/tool surface. | Design resolution, stretch/aspect policy, screenshot or layout evidence at target size, and overflow behavior. |
| Responsive Control layout | UI is built from Godot `Control` nodes, containers, anchors, and theme resources. | Anchor/container policy, minimum size, font/theme scale, overflow policy, and at least one non-target-size validation. |
| Camera/world-scaled view | Gameplay interaction depends on Camera2D/Camera3D, zoom, world units, or world-space UI. | Camera owner, zoom/FOV, world-to-screen conversion, input hit-test conversion, and camera-state evidence. |
| TileMap/grid-scaled view | The route paints or reads cells, terrain, route maps, minimaps, or grid gameplay. | Tile size, cell/world conversion, TileSet collision/navigation ownership, and map validation evidence. |
| Viewport/custom drawing | The route uses `_draw`, Line2D/Polygon2D, SubViewport, shaders, or procedural visual evidence. | Viewport size source, redraw trigger, coordinate space, hit testing if interactive, and screenshot/canvas-pixel evidence. |

Acceptance criteria:

- UI, custom drawing, map, camera, and interaction work cannot be marked complete until one mode above is selected or an explicit non-applicability reason is recorded.
- Preview/package readiness cannot use a visual artifact as final evidence when viewport size, camera state, or TileMap coordinate source is missing or stale for the route under test.
- Route prompts must preserve the selected mode in source-boundary or validation evidence when it affects generated Godot code.

## Godot Feature Family Reading Rule

The TapTapMarker rule of reading the scripting guide, feature API document, examples index, and recipe before implementing a feature translates into a Godot feature-family reading gate. It applies before executable Godot work begins, not after a failure.

MUST trigger when a route, goal, or repair step adds or changes any feature family below:

| Feature family | Required local standard/recipe target | Reference examples |
| --- | --- | --- |
| UI, HUD, menus, dialogs, tooltips, readable text | Godot UI capability contract, Godot UI style contract, and any durable `docs/reference/godot-recipes-index.md` UI row once available. | `docs/reference/godot-official-examples-index.md` rows for Control/container/theme/CanvasLayer. |
| Input, pointer, gestures, gamepad, focus, drag/drop | Godot engine semantic baseline for input constants and UI style pointer/gesture rules. | Input/InputMap and UI interaction examples. |
| Physics, collision, raycast, navigation, interaction regions | Godot engine semantic baseline plus diagnostics interaction-region gate. | 2D/3D movement, collision, Area/Body, raycast, and navigation examples. |
| Camera, third-person camera, world-to-screen, screen-to-world | Godot engine semantic baseline plus third-person camera rig profile when applicable. | Camera2D/Camera3D and third-person/camera-follow examples when curated. |
| Save/load, persistence, settings, project-local data | Repo persistence standards and relevant Godot/project-local examples. | Save/load and local persistence examples. |
| Materials, shaders, textures, rendering, lights, sky, fog, postprocess | Godot material/rendering profiles, rendering/atmosphere profiles, and rendering recipe rows. | Material/shader/rendering/light/environment examples. |
| Character animation, animation state machines, blend spaces, combat/locomotion animation | Godot animation state profile and relevant character/controller standards. | AnimationPlayer, AnimationTree, StateMachine, BlendSpace, character controller, and third-person examples when curated. |
| Audio, video, cutscenes, media playback | Repo media policy when available and Godot media examples. | Audio/video playback examples. |
| Ads, monetization, platform services, external SDKs | Phase security/release standards and an approved platform integration decision. | Only approved repo-owned examples; official examples are not enough to authorize SDK use. |

Reading order:

1. Read the durable Godot semantic baseline and the relevant capability/diagnostic/style contract rows for the touched feature family.
2. Read the smallest relevant local recipe or standard row when `docs/reference/godot-recipes-index.md` or a durable standards file exists.
3. Read one to three curated examples from `docs/reference/godot-official-examples-index.md`.
4. If a route copies an example directory, follow the example copy manifest rule below.
5. Record feature-family reading evidence in route state or phase review evidence before implementation can claim readiness.

Missing-source behavior:

- If no curated example exists for a required feature family, record `reference_example_missing`.
- If no recipe/standard exists where the feature family requires one, record `godot_recipe_missing` unless an explicit not-applicable rationale is accepted for the current phase.
- If a route proceeds without reading evidence for a touched P0/P1 feature family, diagnostics must block execution or final readiness.

Acceptance criteria:

- Route evidence names the feature family, standards/recipe docs read, reference examples read, version/index refs, and why each source is relevant.
- Feature-family reading evidence is source-boundary evidence only; it cannot override GDD, requirement map, prototype contract, route recovery order, Phase ADRs, or Phase service standards.
- Implementation prompts do not cite raw broad docs as mutable authority after contract freeze. They cite the frozen route state, current contracts, and the recorded feature-family evidence.

## Official Godot Reference Examples

Official Godot examples are implementation references, not product requirements. They help agents avoid guessing API patterns, but they cannot override GDD, requirement map, prototype contract, route recovery order, Phase ADRs, or Phase service standards.

Local reference-pack rule:

- The implementation should use a curated, version-pinned local reference pack for official Godot examples or official documentation snippets relevant to this repository's Godot version.
- The canonical reference index path is `docs/reference/godot-official-examples-index.md`.
- The recommended local cache root is `vendor/godot-demo-projects/<godot-version-or-upstream-commit>/`; if implementation uses a different cache root, `docs/reference/godot-official-examples-index.md` must name the root and explain the decision.
- The pack index must map capability families to local example paths, upstream source URL or commit/tag, Godot version, license note, last refresh date, and example copy manifest path when copying is allowed.
- The pack must be curated. Routes must not blindly scan or read every official demo project.
- Before implementing a touched Godot semantic family, the route should read the local standard plus the smallest relevant example set, normally one to three examples.
- If no local example exists for a required family, the route records `reference_example_missing` as the diagnostic failure family and blocking issue domain code owned by `07-godot-diagnostics-quality-gates.md`; route/readback status remains the appropriate existing route status such as `blocked`, not a new status value.

Example copy manifest rule:

- Reference examples are read-only API-pattern evidence by default. Copying an example or part of an example into a hosted project is a separate operation and must use an example copy manifest when the source is a directory or has non-code assets.
- The preferred manifest filename is `godot-example-manifest.json`; `manifest.json` is accepted for imported packs when the index declares its schema and source.
- If the manifest exists, the copy operation must follow `includes`, `excludes`, `copyAll`, `targetDir`, `preservePaths`, `licenseRefs`, `requiredInputActions`, `requiredProjectSettings`, and `assetImportPolicy` fields when present.
- If `copyAll: true`, copy the full example directory, including `.tscn`, `.cs`, `.gd`, `.tres`, `.res`, `.shader`, textures, audio, fonts, `.import` metadata, and other non-code files unless excluded by the manifest.
- If `copyAll` is false or absent, copy only files matched by `includes` and not matched by `excludes`; the manifest must still name required non-code dependencies or explicitly state that none exist.
- If no manifest exists, the route must inspect the directory structure first and record whether non-code resources exist. It must not default to copying only scripts. If non-code resources or unclear dependencies exist, the route blocks with `reference_example_manifest_missing` unless an approved substitute evidence path is recorded.
- Copied examples must not overwrite project authority artifacts, route state, GDD, prototype contract, user assets, or protected runtime evidence. Target paths must be under the hosted project workspace and must preserve license/readback evidence.
- Example copy evidence must record source example ID, manifest path/hash or missing-manifest rationale, copied file list, skipped file list, target root, license refs, required input/project-setting follow-ups, and validation refs.

Minimum reference families:

- UI Control/container/layout/theme.
- Input and InputMap.
- 2D movement and collision.
- 3D movement and collision.
- Camera2D/Camera3D.
- Third-person camera rig/profile.
- TileMap/TileSet/navigation/map painting.
- Custom drawing and procedural visuals.
- Geometry sizing, mesh fallback, and material/shader profiles.
- Animation state and signals.
- Audio.
- Save/load and project-local persistence where relevant.

Acceptance criteria:

- Phase review evidence records which local reference examples were read, why they were relevant, and which Godot semantic family they support.
- Example references are cited as API-pattern evidence only; any requirement copied from an example without GDD/prototype-contract support is invalid.
- Updating the local reference pack requires a version/commit update, license check, index refresh, and route/test evidence update for affected semantic families.
- `reference_example_missing` evidence records the affected semantic family, attempted index path, substitute repo-owned example or test evidence when accepted, and whether the route remains blocked.
- `reference_example_manifest_missing` evidence records the source example path, attempted manifest names, directory inspection summary, non-code dependency summary, copy decision, and whether copying remains blocked.

## Durable Destination

When this execution plan is implemented, these rules should move into a durable standard such as `docs/standards/godot-engine-semantics.md`, linked from `docs/standards/_index.md`, README, project documentation indexes, relevant Phase architecture indexes, and agent-facing routing.

Existing split documents consume this baseline:

- `05-godot-ui-capability-contract.md` consumes UI, drawing, input, camera, and coordinate semantics.
- `06b-ui-style-snapshot-schema.md` and `06d-ui-style-schema-acceptance.md` consume viewport/runtime environment and style evidence semantics.
- `07-godot-diagnostics-quality-gates.md` consumes validation, screenshot, interaction-region, preview, package, and example-reference evidence semantics.
- `08-implementation-phases.md` and `10-recommended-first-slice.md` decide when the baseline becomes active for route implementation.
