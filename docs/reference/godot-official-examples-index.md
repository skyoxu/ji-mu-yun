# Godot Official Examples Index

Status: Placeholder curated-index contract
Language: English
Scope: Local, version-pinned Godot official examples or official documentation snippets used as API-pattern evidence for hosted Godot implementation routes.

## Purpose

This file is the canonical reference index path required by `docs/standards/godot-engine-semantics.md`. It intentionally starts as a placeholder because this repository has not yet imported a curated official Godot demo pack. Routes must not compensate by blindly scanning the internet or every demo project.

When a required feature family has no row with a local example path, record `reference_example_missing` in route evidence and keep the route blocked or needs-fix unless an approved substitute repo-owned example/test evidence is recorded.

## Reference Pack

- Current curated pack: not imported.
- Recommended local cache root once imported: `vendor/godot-demo-projects/<godot-version-or-upstream-commit>/`.
- Supported manifest names: `godot-example-manifest.json`, `manifest.json` when this index declares its schema/source.
- Required refresh evidence: upstream URL or commit/tag, Godot version, license note, last refresh date, affected feature families, and deterministic tests or smoke evidence.

## Minimum Family Rows

| Example family id | Feature family | Local example path | Upstream ref | Godot version | License note | Copy manifest | Current status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ui_control_container_theme` | UI Control/container/layout/theme |  |  |  |  |  | `reference_example_missing` |
| `canvas_layer` | HUD/overlays/CanvasLayer |  |  |  |  |  | `reference_example_missing` |
| `input_map` | Input and InputMap |  |  |  |  |  | `reference_example_missing` |
| `ui_interaction` | Pointer/focus/drag/drop |  |  |  |  |  | `reference_example_missing` |
| `movement_2d_collision` | 2D movement and collision |  |  |  |  |  | `reference_example_missing` |
| `movement_3d_collision` | 3D movement and collision |  |  |  |  |  | `reference_example_missing` |
| `raycast_navigation` | Raycast/navigation/interaction regions |  |  |  |  |  | `reference_example_missing` |
| `camera_2d_3d` | Camera2D/Camera3D |  |  |  |  |  | `reference_example_missing` |
| `third_person_camera` | Third-person camera rig/profile |  |  |  |  |  | `reference_example_missing` |
| `tilemap_tileset_navigation` | TileMap/TileSet/navigation/map painting |  |  |  |  |  | `reference_example_missing` |
| `materials_shaders_rendering` | Materials/shaders/rendering/lights |  |  |  |  |  | `reference_example_missing` |
| `animation_player_tree_state_machine` | Animation state/signals |  |  |  |  |  | `reference_example_missing` |
| `audio_video_playback` | Audio/video/media |  |  |  |  |  | `reference_example_missing` |
| `save_load_project_local` | Save/load and project-local persistence |  |  |  |  |  | `reference_example_missing` |
| `repo_approved_platform_integration` | Approved platform integration examples |  |  |  |  |  | `reference_example_missing` |

## Row Update Rules

A row becomes usable only when it names a local path, upstream source or commit/tag, Godot version, license note, last refresh evidence in the change context, and copy manifest path when copying is allowed.

A row remains read-only API-pattern evidence. It cannot create product requirements, bypass the GDD/prototype contract, or override route recovery authority.
