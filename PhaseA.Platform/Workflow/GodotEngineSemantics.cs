using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class GodotEngineSemantics
{
    public const string BaselineId = "godot-engine-semantics";
    public const string BaselineVersion = "1";
    public const string StandardPath = "docs/standards/godot-engine-semantics.md";
    public const string OfficialExamplesIndexPath = "docs/reference/godot-official-examples-index.md";
    public const string RecipesIndexPath = "docs/reference/godot-recipes-index.md";

    public static readonly IReadOnlyList<string> MissingEvidenceCodes =
    [
        "reference_example_missing",
        "godot_recipe_missing",
        "reference_example_manifest_missing"
    ];

    public static readonly IReadOnlyList<string> ExampleManifestFileNames =
    [
        "godot-example-manifest.json",
        "manifest.json"
    ];

    public static readonly IReadOnlyList<string> ExampleManifestFields =
    [
        "includes",
        "excludes",
        "copyAll",
        "targetDir",
        "preservePaths",
        "licenseRefs",
        "requiredInputActions",
        "requiredProjectSettings",
        "assetImportPolicy"
    ];

    public static readonly IReadOnlyList<GodotSemanticFamily> SemanticFamilies =
    [
        new("unit_scale", "Unit scale", "Godot project units, 2D pixels/control sizes, TileMap cells, and 3D meter-like project units must not be conflated.", ["unit scale source", "2D/3D scope", "conversion rule when mixed"], ["hard-coded world scale without project source"]),
        new("coordinate_spaces", "Coordinate spaces", "Screen, viewport, Control local, CanvasLayer, Node2D local/global, Camera2D world, TileMap cell, and 3D world coordinates must be named before conversion.", ["source coordinate space", "target coordinate space", "conversion owner"], ["mixed screen/world/cell coordinates without conversion path"]),
        new("viewport_resolution", "Viewport and resolution", "Window size, project stretch settings, viewport size, UI logical size, and screenshot dimensions are distinct unless a route records a rule.", ["viewport mode", "stretch/aspect policy", "evidence dimensions"], ["hard-coded screen size without viewport mode"]),
        new("input_constants", "Input constants", "InputMap actions, Godot enums, named constants, or route schema enums are required before accepting input behavior.", ["input action or named constant", "device scope", "fallback behavior"], ["numeric mouse button or key code without named source"]),
        new("physics_collision", "Physics and collision", "Movement and interaction routes must declare body type, layer/mask ownership, signal ownership, and raycast coordinate space.", ["body type", "layer/mask owner", "signal/raycast owner"], ["collision layer number without fixture or profile"]),
        new("camera_projection", "Camera and projection", "Camera owner, zoom/FOV, projection, and screen/world conversion must be declared for camera-dependent interaction or evidence.", ["camera owner", "zoom or FOV", "screen/world conversion"], ["click/drag hit testing without camera state"]),
        new("third_person_camera", "Third-person camera", "Third-person gameplay should use a repo-owned camera rig/profile before adding gameplay-specific camera behavior.", ["rig/profile source", "target/camera/spring-arm paths", "yaw/pitch/collision semantics"], ["duplicated orbit math while shared rig is required"]),
        new("tilemap_map", "TileMap and map drawing", "Tile size, cell coordinate source, local/world conversion, and TileSet collision/navigation ownership must be declared.", ["tile size", "cell/world conversion", "TileSet ownership"], ["map route using cells without tile source"]),
        new("geometry_size_measurement", "Geometry and size measurement", "Built-in primitives, imported meshes, generated meshes, collision shapes, and hit zones require measured or documented dimensions.", ["AABB/import/shape/source size", "owner resource", "fallback behavior"], ["guessed mesh or collision bounds"]),
        new("rendering_material_resources", "Rendering and material resources", "Material, shader, texture, and generated visual resource paths must come from repo files, generated artifacts, import metadata, or approved profiles.", ["material profile", "resource path source", "validation evidence"], ["invented shader, texture, or material path"])
    ];

    public static readonly IReadOnlyList<GodotViewportMode> ViewportModes =
    [
        new("fixed_design_resolution", "Fixed design resolution", "The GDD or style contract names a target resolution or fixed-format board/map/tool surface.", ["design resolution", "stretch/aspect policy", "target-size screenshot or layout evidence", "overflow behavior"]),
        new("responsive_control_layout", "Responsive Control layout", "UI is built from Godot Control nodes, containers, anchors, and theme resources.", ["anchor/container policy", "minimum size", "font/theme scale", "overflow policy", "non-target-size validation"]),
        new("camera_world_scaled_view", "Camera/world-scaled view", "Gameplay interaction depends on Camera2D/Camera3D, zoom, world units, or world-space UI.", ["camera owner", "zoom or FOV", "world-to-screen conversion", "input hit-test conversion", "camera-state evidence"]),
        new("tilemap_grid_scaled_view", "TileMap/grid-scaled view", "The route paints or reads cells, terrain, route maps, minimaps, or grid gameplay.", ["tile size", "cell/world conversion", "TileSet collision/navigation ownership", "map validation evidence"]),
        new("viewport_custom_drawing", "Viewport/custom drawing", "The route uses _draw, Line2D, Polygon2D, SubViewport, shaders, or procedural visual evidence.", ["viewport size source", "redraw trigger", "coordinate space", "interactive hit testing when applicable", "screenshot or canvas-pixel evidence"])
    ];

    public static readonly IReadOnlyList<GodotFeatureFamilyGate> FeatureFamilyGates =
    [
        Gate("ui_hud_menus", "UI, HUD, menus, dialogs, tooltips, readable text", ["coordinate_spaces", "viewport_resolution", "input_constants", "rendering_material_resources"], ["docs/standards/godot-engine-semantics.md", "docs/reference/godot-official-examples-index.md"], ["ui_control_container_theme", "canvas_layer"], true),
        Gate("input_pointer_gamepad_focus", "Input, pointer, gestures, gamepad, focus, drag/drop", ["input_constants", "coordinate_spaces", "viewport_resolution"], ["docs/standards/godot-engine-semantics.md", "docs/reference/godot-official-examples-index.md"], ["input_map", "ui_interaction"], true),
        Gate("physics_collision_navigation", "Physics, collision, raycast, navigation, interaction regions", ["unit_scale", "coordinate_spaces", "physics_collision", "geometry_size_measurement"], ["docs/standards/godot-engine-semantics.md", "docs/reference/godot-official-examples-index.md"], ["movement_2d_collision", "movement_3d_collision", "raycast_navigation"], true),
        Gate("camera_projection", "Camera, third-person camera, world-to-screen, screen-to-world", ["coordinate_spaces", "viewport_resolution", "camera_projection", "third_person_camera"], ["docs/standards/godot-engine-semantics.md", "docs/reference/godot-official-examples-index.md"], ["camera_2d_3d", "third_person_camera"], true),
        Gate("tilemap_maps", "TileMap, TileSet, route maps, minimaps, terrain, map painting", ["coordinate_spaces", "viewport_resolution", "tilemap_map", "geometry_size_measurement"], ["docs/standards/godot-engine-semantics.md", "docs/reference/godot-official-examples-index.md"], ["tilemap_tileset_navigation"], true),
        Gate("materials_rendering_shaders", "Materials, shaders, textures, rendering, lights, sky, fog, postprocess", ["rendering_material_resources", "geometry_size_measurement", "viewport_resolution"], ["docs/standards/godot-engine-semantics.md", "docs/reference/godot-official-examples-index.md"], ["materials_shaders_rendering"], true),
        Gate("animation_state_signals", "Character animation, animation state machines, blend spaces, combat/locomotion animation", ["unit_scale", "physics_collision", "rendering_material_resources"], ["docs/standards/godot-engine-semantics.md", "docs/reference/godot-official-examples-index.md"], ["animation_player_tree_state_machine"], true),
        Gate("audio_video_media", "Audio, video, cutscenes, media playback", ["rendering_material_resources"], ["docs/standards/godot-engine-semantics.md", "docs/reference/godot-official-examples-index.md"], ["audio_video_playback"], false),
        Gate("save_load_persistence", "Save/load, persistence, settings, project-local data", ["unit_scale"], ["docs/standards/godot-engine-semantics.md", "docs/reference/godot-official-examples-index.md"], ["save_load_project_local"], false),
        Gate("platform_services_monetization", "Ads, monetization, platform services, external SDKs", ["rendering_material_resources"], ["docs/standards/godot-engine-semantics.md", "docs/standards/phase-service.md"], ["repo_approved_platform_integration"], true)
    ];

    public static readonly IReadOnlyList<GodotRouteSemanticRequirement> RouteRequirements =
    [
        new("prototype-skeleton", ["ui_hud_menus", "input_pointer_gamepad_focus", "physics_collision_navigation", "camera_projection", "tilemap_maps", "materials_rendering_shaders"], ["semantic_family", "viewport_mode", "feature_family_reading_evidence", "source_boundary_hash"], MissingEvidenceCodes),
        new("iteration-plan", ["ui_hud_menus", "input_pointer_gamepad_focus", "physics_collision_navigation", "camera_projection", "tilemap_maps", "materials_rendering_shaders", "animation_state_signals", "audio_video_media", "save_load_persistence"], ["semantic_family", "planned_feature_family", "reading_evidence_refs", "source_boundary_hash"], MissingEvidenceCodes),
        new("execute-next-goal", ["ui_hud_menus", "input_pointer_gamepad_focus", "physics_collision_navigation", "camera_projection", "tilemap_maps", "materials_rendering_shaders", "animation_state_signals"], ["semantic_family", "viewport_mode", "implementation_reading_evidence", "route_state_ref"], MissingEvidenceCodes),
        new("needs-fix", ["ui_hud_menus", "input_pointer_gamepad_focus", "physics_collision_navigation", "camera_projection", "tilemap_maps", "materials_rendering_shaders"], ["diagnostic_code", "semantic_family", "repair_evidence_ref", "latest_acceptance_blocker"], MissingEvidenceCodes),
        new("repair", ["ui_hud_menus", "input_pointer_gamepad_focus", "physics_collision_navigation", "camera_projection", "tilemap_maps", "materials_rendering_shaders"], ["diagnostic_code", "semantic_family", "repair_ledger_ref", "validation_evidence_ref"], MissingEvidenceCodes),
        new("ui-wiring-closure", ["ui_hud_menus", "input_pointer_gamepad_focus", "camera_projection", "materials_rendering_shaders"], ["viewport_mode", "ui_style_snapshot_hash", "godot_ui_contract_hash", "feature_family_reading_evidence"], MissingEvidenceCodes)
    ];

    public static string BaselineHash => Sha256(string.Join("\n",
        [
            BaselineId,
            BaselineVersion,
            StandardPath,
            OfficialExamplesIndexPath,
            RecipesIndexPath,
            string.Join("|", MissingEvidenceCodes),
            string.Join("|", ExampleManifestFileNames),
            string.Join("|", ExampleManifestFields),
            string.Join("\n", SemanticFamilies.Select(family => string.Join("|", family.FamilyId, family.DisplayName, family.Scope, string.Join(",", family.RequiredDeclarations), string.Join(",", family.BlockingExamples)))),
            string.Join("\n", ViewportModes.Select(mode => string.Join("|", mode.ModeId, mode.DisplayName, mode.UseWhen, string.Join(",", mode.RequiredEvidence)))),
            string.Join("\n", FeatureFamilyGates.Select(gate => string.Join("|", gate.FeatureFamilyId, gate.DisplayName, string.Join(",", gate.SemanticFamilyIds), string.Join(",", gate.RequiredStandardRefs), string.Join(",", gate.ReferenceExampleFamilies), gate.BlocksWithoutReadingEvidence))),
            string.Join("\n", RouteRequirements.Select(requirement => string.Join("|", requirement.RouteId, string.Join(",", requirement.FeatureFamilyIds), string.Join(",", requirement.RequiredEvidenceFields), string.Join(",", requirement.MissingEvidenceCodes))))
        ]));

    public static bool IsKnownSemanticFamily(string familyId)
    {
        return SemanticFamilies.Any(family => string.Equals(family.FamilyId, familyId, StringComparison.Ordinal));
    }

    public static bool IsKnownFeatureFamily(string featureFamilyId)
    {
        return FeatureFamilyGates.Any(gate => string.Equals(gate.FeatureFamilyId, featureFamilyId, StringComparison.Ordinal));
    }

    public static bool IsKnownMissingEvidenceCode(string code)
    {
        return MissingEvidenceCodes.Contains(code, StringComparer.Ordinal);
    }

    private static GodotFeatureFamilyGate Gate(
        string featureFamilyId,
        string displayName,
        IReadOnlyList<string> semanticFamilyIds,
        IReadOnlyList<string> requiredStandardRefs,
        IReadOnlyList<string> referenceExampleFamilies,
        bool blocksWithoutReadingEvidence)
    {
        return new GodotFeatureFamilyGate(featureFamilyId, displayName, semanticFamilyIds, requiredStandardRefs, referenceExampleFamilies, blocksWithoutReadingEvidence);
    }

    private static string Sha256(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}

public sealed record GodotSemanticFamily(
    string FamilyId,
    string DisplayName,
    string Scope,
    IReadOnlyList<string> RequiredDeclarations,
    IReadOnlyList<string> BlockingExamples);

public sealed record GodotViewportMode(
    string ModeId,
    string DisplayName,
    string UseWhen,
    IReadOnlyList<string> RequiredEvidence);

public sealed record GodotFeatureFamilyGate(
    string FeatureFamilyId,
    string DisplayName,
    IReadOnlyList<string> SemanticFamilyIds,
    IReadOnlyList<string> RequiredStandardRefs,
    IReadOnlyList<string> ReferenceExampleFamilies,
    bool BlocksWithoutReadingEvidence);

public sealed record GodotRouteSemanticRequirement(
    string RouteId,
    IReadOnlyList<string> FeatureFamilyIds,
    IReadOnlyList<string> RequiredEvidenceFields,
    IReadOnlyList<string> MissingEvidenceCodes);
