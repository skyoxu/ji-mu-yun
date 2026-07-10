# Godot Engine Semantics Standard

Status: Living standard
Language: English
Scope: Godot runtime implementation routes, Phase browser-consumed prototype routes, hosted project repair routes, visual preview/package validation, and route evidence that touches Godot scenes, UI, input, physics, camera, maps, rendering, or generated runtime assets.

## Purpose

This document is the durable source of truth for Godot-owned engine semantics in the Phase A/B GDD-to-module workflow. Implementation routes must not infer Godot behavior from another engine or from assistant prose. They must resolve the Godot semantic context first, then implement from the GDD, requirement map, prototype contract, route recovery sources, and accepted Phase/Godot standards.

Accepted architecture context: ADR-0036 for route recovery authority, ADR-0038 for evidence/readback, and `docs/architecture/ADR_INDEX_GODOT.md` for Godot template authority.

## Trigger And Skip Rules

Skip this standard only when the route is pure metadata, account, audit, export, or text-only planning work and does not create or validate Godot runtime code, scenes, UI, input, physics, camera, maps, rendering, preview, or package artifacts.

This standard must trigger when the touched route, requirement, goal, or repair step involves any of these families:

- Player-facing UI, HUD, overlays, menus, tooltips, dialogs, readable text, or layout.
- Custom drawing through `Control._draw`, `CanvasItem._draw`, `Line2D`, `Polygon2D`, `MeshInstance2D`, `ArrayMesh`, `ImmediateMesh`, shaders, or SubViewport rendering.
- Camera2D, Camera3D, viewport, zoom, world-to-screen, screen-to-world, or click/drag hit testing.
- Third-person 3D camera, orbit/follow camera, shoulder camera, camera collision, camera smoothing, or camera-relative movement.
- Character movement, physics, collision, Area/Body signals, ray casts, navigation, or interaction regions.
- TileMap, TileSet, grid/cell coordinates, map painting, terrain, path maps, minimaps, or route maps.
- Rendering, material, shader, texture import, built-in primitive sizing, procedural geometry, mesh fallback, or generated visual resources.
- Screenshot/canvas-pixel evidence, preview/package readiness, visual evidence, or browser-safe readback involving runtime visuals.

A route must block or emit an explicit implementation blocker when it has any of these gaps:

- Hard-coded screen size, DPI, tile size, camera zoom, world scale, input button number, physics layer/mask number, or layout coordinate without a source or conversion rule.
- Mixed screen, viewport, UI local, world, TileMap cell, or physics coordinates without naming the conversion path.
- Official examples treated as product requirements instead of API-pattern references.
- Built-in primitive dimensions, imported mesh extents, collision bounds, texture size, material resource paths, shader paths, or generated asset paths assumed without measured source, documented built-in source, import metadata, generated artifact reference, or repo-approved profile.
- Third-person camera routes duplicating orbit math, yaw sign, pitch clamp, target offset, camera collision, or camera-relative movement when a repo-owned shared rig/profile exists or should be created first.

## Machine-Readable Baseline

The runtime registry is `PhaseA.Platform/Workflow/GodotEngineSemantics.cs`.
The parity fixture is `PhaseA.Platform.Tests/Fixtures/godot-engine-semantics.v1.json`.
The deterministic test owner is `PhaseA.Platform.Tests/Workflow/GodotEngineSemanticsTests.cs`.

The registry owns:

- Baseline id/version/hash.
- Required semantic families.
- Viewport/resolution modes.
- Feature-family reading gates.
- Godot-executable route semantic requirements.
- Missing evidence codes: `reference_example_missing`, `godot_recipe_missing`, and `reference_example_manifest_missing`.
- Example copy manifest names and fields.

Do not add a Godot semantic family, missing evidence code, or copy-manifest field in docs only. Update the registry, fixture, tests, and this document together.

## Required Semantic Families

Implementation prompts, route-state artifacts, and acceptance evidence must name the relevant semantic family before executable Godot work starts.

| Family id | Required declaration |
| --- | --- |
| `unit_scale` | Godot project units, 2D pixels/control sizes, TileMap cells, and 3D meter-like units must not be conflated. Declare the unit source and conversion rule when mixed. |
| `coordinate_spaces` | Distinguish screen, viewport, Control local, CanvasLayer, Node2D local/global, Camera2D world, TileMap cell, and 3D world coordinates. |
| `viewport_resolution` | Distinguish physical window size, project stretch settings, viewport size, UI logical size, and screenshot evidence dimensions. |
| `input_constants` | Use InputMap actions, Godot enums, named constants, or route schema enums. Numeric mouse buttons, key codes, layers, masks, or mode values need a named fixture or documented constant source. |
| `physics_collision` | Declare body type, collision layer/mask ownership, Area/Body signal ownership, raycast coordinate space, and physics-process ownership. |
| `camera_projection` | Declare Camera2D/Camera3D owner, zoom/FOV, projection assumptions, and screen/world conversion for camera-dependent interaction or evidence. |
| `third_person_camera` | Use a repo-owned Godot camera rig/profile before gameplay-specific third-person camera behavior. Gameplay modules may configure the rig but must not duplicate orbit math or invert yaw semantics locally. |
| `tilemap_map` | Declare tile size, cell coordinate source, world/local conversion, TileSet collision/navigation/occlusion ownership, and map evidence refs. |
| `geometry_size_measurement` | Cite `AABB`, `get_aabb()`, collision shape dimensions, texture/import metadata, `Control` minimum size, or another documented source for sizes and hit zones. |
| `rendering_material_resources` | Declare material profile, resource ownership, path source, fallback behavior, and validation evidence. Resource paths must come from repo files, generated artifacts, import metadata, or approved profiles. |

## Viewport And Resolution Modes

Godot visual work must record one mode before UI, map, camera, interaction, screenshot, or custom drawing work proceeds.

| Mode id | Use when | Required evidence |
| --- | --- | --- |
| `fixed_design_resolution` | The GDD or style contract names a target resolution or fixed-format board/map/tool surface. | Design resolution, stretch/aspect policy, target-size screenshot or layout evidence, and overflow behavior. |
| `responsive_control_layout` | UI is built from Godot `Control` nodes, containers, anchors, and theme resources. | Anchor/container policy, minimum size, font/theme scale, overflow policy, and non-target-size validation. |
| `camera_world_scaled_view` | Gameplay interaction depends on Camera2D/Camera3D, zoom, world units, or world-space UI. | Camera owner, zoom/FOV, world-to-screen conversion, input hit-test conversion, and camera-state evidence. |
| `tilemap_grid_scaled_view` | The route paints or reads cells, terrain, route maps, minimaps, or grid gameplay. | Tile size, cell/world conversion, TileSet collision/navigation ownership, and map validation evidence. |
| `viewport_custom_drawing` | The route uses `_draw`, Line2D/Polygon2D, SubViewport, shaders, or procedural visual evidence. | Viewport size source, redraw trigger, coordinate space, hit testing if interactive, and screenshot/canvas-pixel evidence. |

Preview/package readiness cannot use visual artifacts as final evidence when viewport size, camera state, or TileMap coordinate source is missing or stale for the route under test.

## Feature-Family Reading Gate

Before executable Godot work begins, routes must read the smallest relevant local standard/recipe rows and one to three curated reference examples when available. Reading evidence is source-boundary evidence only; it cannot override GDD, requirement map, prototype contract, route recovery order, Phase ADRs, or Phase service standards.

Reading order:

1. Read this semantic baseline and relevant capability, diagnostic, or style contract rows for the touched feature family.
2. Read the smallest relevant local recipe or standard row when `docs/reference/godot-recipes-index.md` or another durable standards file exists.
3. Read one to three curated examples from `docs/reference/godot-official-examples-index.md`.
4. If copying an example directory or non-code asset, follow the example copy manifest rule.
5. Record feature-family reading evidence in route state or Phase review evidence before implementation can claim readiness.

Required missing-source behavior:

- No curated example for a required feature family: record `reference_example_missing`.
- No recipe/standard where the feature family requires one: record `godot_recipe_missing` unless an explicit not-applicable rationale is accepted for the current phase.
- Copying an example directory without a usable manifest and with non-code or unclear dependencies: record `reference_example_manifest_missing` and block copying unless an approved substitute evidence path exists.

Route evidence must name feature family, standards/recipe docs read, reference examples read, version/index refs, and why each source is relevant.

## Official Godot Reference Examples

Official Godot examples are implementation references, not product requirements. They help agents avoid guessing API patterns, but they do not authorize features or override repository contracts.

Canonical reference index path: `docs/reference/godot-official-examples-index.md`.
Recommended local cache root: `vendor/godot-demo-projects/<godot-version-or-upstream-commit>/`.

The reference pack must be curated and version-pinned. Routes must not blindly scan every official demo project. If no pack row exists for a required family, record `reference_example_missing` and keep route/readback status in the existing bounded route vocabulary, usually `blocked` or `needs_fix`.

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

## Example Copy Manifest Rule

Reference examples are read-only API-pattern evidence by default. Copying an example or part of an example into a hosted project is a separate operation and must use an example copy manifest when the source is a directory or has non-code assets.

Preferred manifest filename: `godot-example-manifest.json`.
Accepted imported-pack filename: `manifest.json`, only when the reference index declares its schema and source.

Supported manifest fields:

- `includes`
- `excludes`
- `copyAll`
- `targetDir`
- `preservePaths`
- `licenseRefs`
- `requiredInputActions`
- `requiredProjectSettings`
- `assetImportPolicy`

If `copyAll: true`, copy the full example directory including `.tscn`, `.cs`, `.gd`, `.tres`, `.res`, `.shader`, textures, audio, fonts, `.import` metadata, and other non-code files unless excluded by the manifest.

If `copyAll` is false or absent, copy only files matched by `includes` and not matched by `excludes`; the manifest must still name required non-code dependencies or explicitly state that none exist.

If no manifest exists, inspect the directory structure first and record whether non-code resources exist. Do not default to copying only scripts. If non-code resources or unclear dependencies exist, block with `reference_example_manifest_missing` unless an approved substitute evidence path is recorded.

Copied examples must not overwrite project authority artifacts, route state, GDD, prototype contract, user assets, or protected runtime evidence. Target paths must stay under the hosted project workspace and preserve license/readback evidence.

Example copy evidence must record source example ID, manifest path/hash or missing-manifest rationale, copied file list, skipped file list, target root, license refs, required input/project-setting follow-ups, and validation refs.

## Route Integration

The registry currently declares semantic requirements for these Godot-executable GDD-to-module routes:

- `prototype-skeleton`
- `iteration-plan`
- `execute-next-goal`
- `needs-fix`
- `repair`
- `ui-wiring-closure`

Future routes that create or validate Godot runtime artifacts must add a `GodotRouteSemanticRequirement` before claiming readiness. Pure metadata/account/audit routes may remain out of this registry with a documented non-applicability reason.

## Validation

Minimum deterministic validation for changes to this standard:

```powershell
dotnet test PhaseA.Platform.Tests --filter FullyQualifiedName~GodotEngineSemanticsTests
```

When the change also affects browser route contracts, run the relevant route contract/readback tests and the GDD-to-module smoke script described in `docs/standards/phase-service.md`.
