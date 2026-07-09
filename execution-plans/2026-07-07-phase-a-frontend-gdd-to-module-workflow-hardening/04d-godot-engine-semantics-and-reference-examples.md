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
- Character movement, physics, collision, Area/Body signals, ray casts, navigation, or interaction regions.
- TileMap, TileSet, grid/cell coordinates, map painting, terrain, path maps, minimaps, or route maps.
- Screenshot/canvas-pixel evidence, preview/package readiness, visual evidence, or browser-safe readback involving runtime visuals.

MUST block or produce an explicit implementation blocker when:

- A plan or prompt requires hard-coded screen size, DPI, tile size, camera zoom, world scale, input button number, physics layer/mask number, or layout coordinate without a source or conversion rule.
- A route mixes screen, viewport, UI local, world, TileMap cell, or physics coordinates without naming the conversion path.
- A route relies on official examples as product requirements instead of API/implementation references.

## Godot Semantic Baseline

Implementation prompts, route-state artifacts, and acceptance evidence must use Godot terms and must declare the relevant semantic family before executable work starts.

Minimum semantic families:

- Unit scale: 3D positions, distances, velocities, and collision dimensions are treated as Godot project units with meter-like interpretation unless the project standard declares otherwise. 2D positions, Control sizes, and TileMap cells must not be conflated with 3D world scale.
- Coordinate spaces: distinguish screen coordinates, viewport coordinates, Control local coordinates, CanvasLayer coordinates, Node2D local/global coordinates, Camera2D world coordinates, TileMap cell coordinates, and 3D world coordinates.
- Viewport and resolution: declare whether the work uses fixed design resolution, responsive Control layout, camera/world scaling, or viewport-size-driven drawing. Physical window size, project stretch settings, viewport size, UI logical size, and screenshot evidence dimensions must not be treated as the same value without an explicit rule.
- Input constants: InputMap actions, Godot enums, named constants, or route schema enum values are required. Numeric mouse buttons, key codes, collision layers, or mode values are not accepted unless they are generated from a named fixture or documented constant source.
- Physics and collision: declare body type, collision layer/mask ownership, Area/Body signal ownership, raycast coordinate space, and physics-process ownership before accepting movement or collision behavior.
- Camera and projection: declare Camera2D/Camera3D owner, zoom/FOV, projection assumptions, and screen/world conversion when click, drag, aiming, route-map selection, or viewport evidence depends on camera state.
- TileMap and map drawing: declare tile size, cell coordinate source, world/local conversion, TileSet collision/navigation/occlusion ownership, and map evidence refs before generated map logic or map UI is accepted.

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

## Official Godot Reference Examples

Official Godot examples are implementation references, not product requirements. They help agents avoid guessing API patterns, but they cannot override GDD, requirement map, prototype contract, route recovery order, Phase ADRs, or Phase service standards.

Local reference-pack rule:

- The implementation should use a curated, version-pinned local reference pack for official Godot examples or official documentation snippets relevant to this repository's Godot version.
- The canonical reference index path is `docs/reference/godot-official-examples-index.md`.
- The recommended local cache root is `vendor/godot-demo-projects/<godot-version-or-upstream-commit>/`; if implementation uses a different cache root, `docs/reference/godot-official-examples-index.md` must name the root and explain the decision.
- The pack index must map capability families to local example paths, upstream source URL or commit/tag, Godot version, license note, and last refresh date.
- The pack must be curated. Routes must not blindly scan or read every official demo project.
- Before implementing a touched Godot semantic family, the route should read the local standard plus the smallest relevant example set, normally one to three examples.
- If no local example exists for a required family, the route records `reference_example_missing` as the diagnostic failure family and blocking issue domain code owned by `07-godot-diagnostics-quality-gates.md`; route/readback status remains the appropriate existing route status such as `blocked`, not a new status value.

Minimum reference families:

- UI Control/container/layout/theme.
- Input and InputMap.
- 2D movement and collision.
- 3D movement and collision.
- Camera2D/Camera3D.
- TileMap/TileSet/navigation/map painting.
- Custom drawing and procedural visuals.
- Animation state and signals.
- Audio.
- Save/load and project-local persistence where relevant.

Acceptance criteria:

- Phase review evidence records which local reference examples were read, why they were relevant, and which Godot semantic family they support.
- Example references are cited as API-pattern evidence only; any requirement copied from an example without GDD/prototype-contract support is invalid.
- Updating the local reference pack requires a version/commit update, license check, index refresh, and route/test evidence update for affected semantic families.
- `reference_example_missing` evidence records the affected semantic family, attempted index path, substitute repo-owned example or test evidence when accepted, and whether the route remains blocked.

## Durable Destination

When this execution plan is implemented, these rules should move into a durable standard such as `docs/standards/godot-engine-semantics.md`, linked from `docs/standards/_index.md`, README, project documentation indexes, relevant Phase architecture indexes, and agent-facing routing.

Existing split documents consume this baseline:

- `05-godot-ui-capability-contract.md` consumes UI, drawing, input, camera, and coordinate semantics.
- `06b-ui-style-snapshot-schema.md` and `06d-ui-style-schema-acceptance.md` consume viewport/runtime environment and style evidence semantics.
- `07-godot-diagnostics-quality-gates.md` consumes validation, screenshot, interaction-region, preview, package, and example-reference evidence semantics.
- `08-implementation-phases.md` and `10-recommended-first-slice.md` decide when the baseline becomes active for route implementation.
