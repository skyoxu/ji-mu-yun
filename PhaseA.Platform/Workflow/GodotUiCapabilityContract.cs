using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class GodotUiCapabilityContract
{
    public const string ContractId = "godot-ui-capability";
    public const string ContractVersion = "1";
    public const string StandardPath = "docs/standards/godot-ui-capability-contract.md";

    public static readonly IReadOnlyList<string> ForbiddenTechnologyTerms =
    [
        "UrhoX",
        "Urho3D",
        "Lua",
        "NanoVG",
        "PBRNoTexture",
        ".emmylua"
    ];

    public static readonly IReadOnlyList<string> CapabilityStatuses =
    [
        "required",
        "covered",
        "missing_ui",
        "missing_feedback",
        "needs_fix",
        "no_ui_needed",
        "not_applicable",
        "explicitly_deferred"
    ];

    public static readonly IReadOnlyList<string> BlockingDiagnosticCodes =
    [
        "godot_ui_contract_missing",
        "godot_ui_capability_missing",
        "godot_ui_semantic_mode_missing",
        "godot_ui_surface_incomplete",
        "godot_ui_no_ui_needed_review_missing",
        "material_profile_missing",
        "rendering_profile_missing",
        "animation_state_profile_missing",
        "third_person_camera_profile_missing",
        "ui_update_ownership_missing",
        "technology_stack_leakage"
    ];

    public static readonly IReadOnlyList<GodotUiCapabilityDomain> CapabilityDomains =
    [
        Domain("ui_scene_architecture", "UI scene architecture", ["Control scenes", "CanvasLayer HUDs", "scene instancing", "autoload boundaries", "scene transitions", "route-specific UI roots"], ["scene_path", "node_path", "requirement_ids", "player_flow", "state_boundary", "validation_refs"], ["coordinate_spaces", "viewport_resolution"]),
        Domain("layout_theme_responsive", "Layout, containers, theme, and responsive rules", ["Container nodes", "anchors", "safe-area handling", "theme resources", "minimum sizes", "viewport-safe scaling"], ["layout_strategy", "fixed_format_rationale", "theme_or_min_size_source", "viewport_evidence"], ["viewport_resolution", "geometry_size_measurement"]),
        Domain("hud_menus_overlays", "HUD, menus, overlays, and modal state", ["CanvasLayer", "modal controls", "pause/menu overlays", "notifications", "status bars", "inventory/deck/reward panels"], ["overlay_layer", "modal_blocking_behavior", "input_routing", "state_synchronization", "evidence_refs"], ["coordinate_spaces", "input_constants"]),
        Domain("custom_2d_drawing", "Custom 2D drawing and visual affordances", ["Control._draw", "CanvasItem._draw", "Line2D", "Polygon2D", "draw invalidation", "hit testing"], ["drawing_surface", "redraw_trigger", "hit_test_path", "visual_feedback_states", "canvas_or_screenshot_evidence"], ["coordinate_spaces", "viewport_resolution", "geometry_size_measurement"]),
        Domain("input_focus_navigation", "Input, focus, and navigation", ["InputMap", "mouse/touch events", "keyboard focus", "gamepad focus", "drag/drop", "hover/pressed/selected/disabled states"], ["input_paths", "supported_devices", "focus_status", "drag_drop_boundaries", "disabled_error_states", "validation_refs"], ["input_constants", "coordinate_spaces"]),
        Domain("camera_viewport_world_physics", "Camera, viewport, world/UI layering, and physics interaction", ["Camera2D", "Camera3D", "CanvasLayer", "SubViewport", "physics layers/masks", "raycasts", "screen-to-world transforms"], ["camera_owner", "ui_world_separation_rule", "raycast_input_conversion_path", "layer_mask_rationale", "validation_refs"], ["camera_projection", "physics_collision", "coordinate_spaces"]),
        Domain("rendering_materials_shaders", "Rendering, materials, shaders, and import policy", ["CanvasItemMaterial", "StandardMaterial3D", "ShaderMaterial", "import settings", "render layers", "lighting mode"], ["material_profile", "rendering_profile", "source_asset_import_evidence", "shader_owner", "fallback_policy"], ["rendering_material_resources", "geometry_size_measurement"]),
        Domain("animation_state_machines", "Animation and state machines", ["AnimationPlayer", "AnimationTree", "state-machine resources", "tween usage", "transitions"], ["animation_profile", "animation_state_reference", "transition_trigger", "state_enum_source", "validation_refs"], ["unit_scale", "physics_collision"]),
        Domain("procedural_generation", "Procedural generation and generated UI/world content", ["deterministic seeds", "generated map/route/deck/reward layouts", "generated scene nodes", "headless validation"], ["seed_source", "generated_output_summary", "validation_artifact", "replayability_rule"], ["tilemap_map", "geometry_size_measurement"]),
        Domain("geometry_mesh_size", "Geometry, mesh fallback, and size measurement", ["AABB", "get_aabb()", "collision shapes", "import metadata", "ArrayMesh", "ImmediateMesh", "Polygon2D", "Line2D"], ["size_source", "collision_or_interaction_shape", "fallback_geometry_api", "validation_ref"], ["geometry_size_measurement"]),
        Domain("typed_state_schema", "Typed state, enums, and schema contracts", ["C# enums/classes/records", "typed GDScript where used", "named constants", "DTO/schema enums"], ["typed_state_reference", "enum_source", "schema_field", "invalid_state_behavior", "tests"], ["input_constants"]),
        Domain("accessibility_readability_feedback", "Accessibility, readability, and feedback legibility", ["theme contrast", "readable font sizes", "hover/focus/selected/disabled states", "error copy", "layout overflow handling"], ["readability_target", "feedback_states", "screenshot_or_browser_evidence", "no_overlap_validation"], ["viewport_resolution", "rendering_material_resources"])
    ];

    public static readonly IReadOnlyList<string> MaterialProfiles =
    [
        "solid_3d_standard",
        "transparent_3d_standard",
        "solid_2d_canvas",
        "canvas_item_material",
        "shader_material",
        "existing_material_resource"
    ];

    public static readonly IReadOnlyList<string> RenderingProfiles =
    [
        "ambient_3d_default",
        "directional_key_light",
        "local_light_group",
        "environment_fog_atmosphere",
        "postprocess_profile",
        "rendering_not_applicable"
    ];

    public static readonly IReadOnlyList<string> AnimationProfiles =
    [
        "animation_player_simple",
        "animation_tree_state_machine",
        "animation_tree_blendspace",
        "repo_character_animation_profile",
        "animation_not_applicable"
    ];

    public static readonly IReadOnlyList<string> UiUpdateOwnershipModes =
    [
        "retained_typed_references",
        "registered_control_map",
        "state_apply_pass",
        "dynamic_item_factory",
        "no_dynamic_update"
    ];

    public static readonly IReadOnlyList<GodotUiWorkflowInjectionPoint> InjectionPoints =
    [
        new("gdd-question-form", "Optionally asks for UI-heavy flow hints without suppressing default UI classification.", ["ui_hints_optional", "default_ui_classification_preserved"]),
        new("scene-route-confirmation", "Declares expected player-facing UI surfaces or no_ui_needed per confirmed scene.", ["scene_ui_surface_expectations", "no_ui_needed_rationale"]),
        new("gdd-document-generation", "Carries UI, HUD, input, drawing, camera, animation, procedural, and rendering implications into generated GDD.", ["ui_implications", "input_feedback_implications"]),
        new("gdd-requirements", "Extracts UI capability requirements with severity, scene/module mapping, and acceptance markers.", ["capability_domain_ids", "acceptance_markers", "source_godot_ui_contract_hash"]),
        new("prototype-contract", "Freezes Godot UI capability contract version/hash into the prototype contract.", ["godot_ui_contract_version", "source_godot_ui_contract_hash"]),
        new("iteration-plan", "Creates UI surface goals and required modules from P0/P1 capability requirements.", ["capability_goal_refs", "semantic_reading_evidence"]),
        new("execute-next-goal", "Injects the frozen UI capability contract for relevant implementation goals.", ["frozen_contract_ref", "required_capability_evidence"]),
        new("needs-fix", "Maps UI failures to requirement IDs and UI gap families.", ["ui_gap_family", "requirement_ids"]),
        new("repair", "Keeps UI repair prompts bound to requirement IDs, diagnostics, and capability gaps.", ["repair_ledger_ref", "ui_gap_family"]),
        new("ui-wiring-closure", "Validates the complete UI surface matrix, profiles, evidence, and exemptions.", ["ui_surface_matrix", "profile_refs", "exemption_review"]),
        new("preview-package", "Exposes final-readiness blockers from UI closure without blocking early package generation.", ["final_readiness_blockers", "ui_closure_ref"])
    ];

    public static readonly IReadOnlyList<GodotUiGovernanceRule> GovernanceRules =
    [
        Rule("visible_entry_feedback_required", "P0/P1 gameplay features need visible player entry, feedback, state boundary, and validation evidence unless no_ui_needed is explicitly reviewed.", true),
        Rule("control_container_theme_preferred", "Prefer Control, Container, Theme, anchors, and safe areas; absolute positioning needs a fixed-format or world-overlay rationale.", true),
        Rule("hud_menu_canvaslayer_input_owner", "HUD and menus must declare CanvasLayer/viewport ownership and input routing.", true),
        Rule("drag_drop_state_complete", "Drag/drop and pointer-heavy features must declare start, hover, cancel, drop, invalid drop, and commit states.", true),
        Rule("custom_drawing_evidence", "Custom drawing must declare drawing API, redraw trigger, hit-test strategy, and screenshot/canvas evidence.", true),
        Rule("named_camera_physics_constants", "Camera/physics interactions must use named layers, masks, and measurable boundaries.", true),
        Rule("approved_material_profiles", "Rendering/material/shader work must use approved Godot profiles or block with material_profile_missing.", true),
        Rule("measured_size_required", "Size-sensitive work must cite AABB, get_aabb(), collision shape, import metadata, theme metric, or min-size source.", true),
        Rule("godot_geometry_fallback", "Missing built-in geometry must use Godot geometry APIs with validation evidence.", true),
        Rule("typed_state_required", "UI mode, animation state, input state, route state, and validation status must use enums, named constants, or schema enums.", true),
        Rule("procedural_generation_replayable", "Procedural UI/world generation must be seedable, replayable, and validated.", false),
        Rule("visual_evidence_required", "High-risk visual UI changes require screenshot, canvas-pixel, or exported visual evidence.", false),
        Rule("material_profile_selected", "Pure-color/no-texture material work must select a known material profile or block.", true),
        Rule("dynamic_ui_update_owner", "Dynamic UI must declare construction owner and update ownership mode.", true),
        Rule("third_person_camera_shared_rig", "Third-person camera behavior must use or create the repo-owned shared rig/profile before gameplay-specific camera work.", true),
        Rule("rendering_profile_selected", "Lighting, fog, sky, environment, and postprocess work must select a rendering/atmosphere profile with readability evidence.", true),
        Rule("animation_profile_selected", "Character animation/state-machine work must select an animation profile with typed state and fallback behavior.", true)
    ];

    public static string ContractHash => Sha256(string.Join("\n",
        [
            ContractId,
            ContractVersion,
            StandardPath,
            string.Join("|", ForbiddenTechnologyTerms),
            string.Join("|", CapabilityStatuses),
            string.Join("|", BlockingDiagnosticCodes),
            string.Join("\n", CapabilityDomains.Select(domain => string.Join("|", domain.DomainId, domain.DisplayName, string.Join(",", domain.GodotOwnership), string.Join(",", domain.RequiredWorkflowFields), string.Join(",", domain.SemanticFamilyIds)))),
            string.Join("|", MaterialProfiles),
            string.Join("|", RenderingProfiles),
            string.Join("|", AnimationProfiles),
            string.Join("|", UiUpdateOwnershipModes),
            string.Join("\n", InjectionPoints.Select(point => string.Join("|", point.RouteId, point.Summary, string.Join(",", point.RequiredFields)))),
            string.Join("\n", GovernanceRules.Select(rule => string.Join("|", rule.RuleId, rule.Summary, rule.BlocksP0P1)))
        ]));

    public static bool IsKnownCapabilityDomain(string domainId)
    {
        return CapabilityDomains.Any(domain => string.Equals(domain.DomainId, domainId, StringComparison.Ordinal));
    }

    public static bool IsKnownMaterialProfile(string profile)
    {
        return MaterialProfiles.Contains(profile, StringComparer.Ordinal);
    }

    public static bool IsKnownRenderingProfile(string profile)
    {
        return RenderingProfiles.Contains(profile, StringComparer.Ordinal);
    }

    public static bool IsKnownAnimationProfile(string profile)
    {
        return AnimationProfiles.Contains(profile, StringComparer.Ordinal);
    }

    public static bool IsKnownUpdateOwnershipMode(string mode)
    {
        return UiUpdateOwnershipModes.Contains(mode, StringComparer.Ordinal);
    }

    private static GodotUiCapabilityDomain Domain(
        string domainId,
        string displayName,
        IReadOnlyList<string> godotOwnership,
        IReadOnlyList<string> requiredWorkflowFields,
        IReadOnlyList<string> semanticFamilyIds)
    {
        return new GodotUiCapabilityDomain(domainId, displayName, godotOwnership, requiredWorkflowFields, semanticFamilyIds);
    }

    private static GodotUiGovernanceRule Rule(string ruleId, string summary, bool blocksP0P1)
    {
        return new GodotUiGovernanceRule(ruleId, summary, blocksP0P1);
    }

    private static string Sha256(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}

public sealed record GodotUiCapabilityDomain(
    string DomainId,
    string DisplayName,
    IReadOnlyList<string> GodotOwnership,
    IReadOnlyList<string> RequiredWorkflowFields,
    IReadOnlyList<string> SemanticFamilyIds);

public sealed record GodotUiWorkflowInjectionPoint(
    string RouteId,
    string Summary,
    IReadOnlyList<string> RequiredFields);

public sealed record GodotUiGovernanceRule(
    string RuleId,
    string Summary,
    bool BlocksP0P1);
