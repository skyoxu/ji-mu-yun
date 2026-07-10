using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class GodotUiStyleCatalog
{
    public const string CatalogId = "godot-ui-style-catalog";
    public const string CatalogVersion = "1";
    public const string StandardPath = "docs/standards/godot-ui-style-contract.md";
    public const string StyleGuideRoot = "docs/ui-style-guides";

    public static readonly IReadOnlyList<string> ForbiddenTechnologyTerms =
    [
        "UrhoX",
        "Yoga",
        "NanoVG",
        "Lua theme",
        "EmmyLua",
        "TapTapMarker font assets"
    ];

    public static readonly IReadOnlyList<string> StyleDriftFamilies =
    [
        "design_dna",
        "palette",
        "typography",
        "radius",
        "border",
        "shadow",
        "opacity",
        "spacing",
        "density_scale",
        "rarity_hud",
        "gradient_glow",
        "bottom_accent",
        "component_defaults",
        "component_coverage",
        "component_family_baseline",
        "variant_coverage",
        "component_exception_rules",
        "forbidden_patterns",
        "motion_transition",
        "game_composition_templates",
        "theme_resource_refs",
        "theme_resource_coverage",
        "semantic_usage",
        "action_role",
        "contrast_readability",
        "font_policy",
        "font_size_unit",
        "localization_overflow",
        "pointer_gesture",
        "gesture_phase",
        "pointer_event_shape",
        "drag_drop_payload",
        "state_ownership",
        "ui_lifecycle",
        "scroll_virtualization",
        "state_tokens",
        "composition",
        "ui_tree_readback",
        "source_name_ownership",
        "runtime_environment",
        "file_upload_security",
        "visual_evidence",
        "visual_evidence_method"
    ];

    public static readonly IReadOnlyList<string> CoverageStatuses = RouteStatusVocabulary.Values(RouteStatusVocabulary.StyleCapabilityCoverage).ToArray();

    public static readonly IReadOnlyList<GodotUiStyleDefinition> Styles =
    [
        new(
            "godot_cosmic",
            "Godot Cosmic",
            "1",
            "docs/ui-style-guides/godot-cosmic.md",
            ["fantasy", "space", "magic", "cosmic", "adventure", "deckbuilder"],
            ["cosmic background tokens", "gold primary CTA", "glow-style Godot shadows", "layered panels", "rarity colors"],
            ["Button", "PanelContainer", "CanvasLayer", "ProgressBar", "TabContainer"],
            ["combat_hud", "route_map", "deck_hand", "reward_panel"]),
        new(
            "godot_combat_hud",
            "Godot Combat HUD",
            "1",
            "docs/ui-style-guides/godot-combat-hud.md",
            ["action", "combat", "arena", "shooter", "survivorslike", "tactical"],
            ["sharp silhouettes", "thick borders", "bold typography", "vivid state colors", "hard-edged HUD bars"],
            ["Button", "PanelContainer", "ProgressBar", "TextureRect", "PopupPanel"],
            ["combat_hud", "stat_bar", "hud_cluster", "inventory_grid"]),
        new(
            "godot_pixel_arcade",
            "Godot Pixel Arcade",
            "1",
            "docs/ui-style-guides/godot-pixel-arcade.md",
            ["pixel", "arcade", "retro", "platformer", "jrpg", "roguelike"],
            ["zero radius", "hard shadows", "pixel-friendly scale", "approved pixel font fallback", "square component templates"],
            ["Button", "PanelContainer", "ScrollContainer", "PopupMenu", "LineEdit"],
            ["dialog_box", "route_map", "card_view", "reward_panel"])
    ];

    public static readonly IReadOnlyList<GodotUiComponentTier> ComponentTiers =
    [
        new("core_minimum", ["button", "checkbox", "toggle", "slider", "text_field", "text_area", "panel_card", "modal", "tooltip", "progress_bar", "tabs", "menu", "dropdown", "scroll_view", "list_view"], "required"),
        new("game_minimum", ["stat_bar", "hud_cluster", "deck_hand", "card_view", "reward_panel", "route_map", "combat_hud", "dialog_box"], "conditional"),
        new("conditional_builtin", ["badge", "chip", "alert", "toast", "drawer", "popover", "table", "grid_view", "timeline", "carousel", "accordion", "tree", "stepper", "breadcrumb", "pagination", "rating", "calendar", "date_picker", "time_picker", "color_picker", "item_slot", "inventory_grid", "quest_tracker"], "conditional"),
        new("admin_tooling_or_security_gated", ["file_upload", "account_asset_tool", "raw_diagnostic_viewer"], "admin_tooling_or_security_gated")
    ];

    public static readonly IReadOnlyList<GodotUiStyleCapability> Capabilities =
    [
        Capability("ui_component_system", "Godot Control scenes, composed controls, component family baseline, and game composition templates."),
        Capability("ui_theme_token_system", "Machine-readable tokens, canonical token value format, Theme slot mapping, StyleBox, FontFile, Texture2D resources, and token coverage evidence."),
        Capability("ui_layout_scale_coordinates", "Godot anchors, containers, size flags, viewport classes, display scale, safe area, layout bounds, and hit-test coordinate readback."),
        Capability("ui_input_pointer_gesture", "InputMap, Control.gui_input, _unhandled_input, pointer event shape, gesture phases, drag/drop lifecycle, keyboard/gamepad equivalents, and validation evidence."),
        Capability("ui_state_data_binding", "Stateless/stateful/controlled/uncontrolled rules, route state binding, form state, IME/composition, selection/cursor, disabled/readonly/placeholder semantics."),
        Capability("ui_lifecycle_ownership", "Godot lifecycle hooks, signal connect/disconnect ownership, timers, tweens, process mode, cleanup, orphan diagnostics, and duplicate subscription guards."),
        Capability("ui_scroll_virtualization", "Scroll/list/grid/timeline visible range, clipping, item measurement, keying, buffer window, recycling, and performance evidence."),
        Capability("ui_overlays_feedback", "Modal/drawer/popover/tooltip focus and dismissal, toast queue/duration/enter-exit, status feedback, and visual evidence."),
        Capability("ui_diagnostics_visual_evidence", "Screenshot/canvas/exported visual evidence, deterministic substitute limits, UI tree readback, style drift findings, and repair prompts."),
        Capability("ui_security_gated_tooling", "File upload and admin tooling UI only when Phase security policy, account isolation, readback safety, and cleanup rules exist.")
    ];

    public static string CatalogHash => Sha256(string.Join("\n",
        [
            CatalogId,
            CatalogVersion,
            StandardPath,
            StyleGuideRoot,
            string.Join("|", ForbiddenTechnologyTerms),
            string.Join("|", StyleDriftFamilies),
            string.Join("|", CoverageStatuses),
            string.Join("\n", Styles.Select(style => string.Join("|", style.StyleId, style.DisplayName, style.Version, style.GuidePath, string.Join(",", style.TriggerTags), string.Join(",", style.DesignDna), string.Join(",", style.GodotControls), string.Join(",", style.GameCompositionTemplates)))),
            string.Join("\n", ComponentTiers.Select(tier => string.Join("|", tier.TierId, string.Join(",", tier.ComponentFamilies), tier.DefaultCoverageStatus))),
            string.Join("\n", Capabilities.Select(capability => string.Join("|", capability.CapabilityId, capability.GodotTranslation)))
        ]));

    public static bool IsKnownStyleId(string styleId)
    {
        return Styles.Any(style => string.Equals(style.StyleId, styleId, StringComparison.Ordinal));
    }

    public static bool IsKnownDriftFamily(string family)
    {
        return StyleDriftFamilies.Contains(family, StringComparer.Ordinal);
    }

    private static GodotUiStyleCapability Capability(string capabilityId, string godotTranslation)
    {
        return new GodotUiStyleCapability(capabilityId, godotTranslation);
    }

    private static string Sha256(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}

public sealed record GodotUiStyleDefinition(
    string StyleId,
    string DisplayName,
    string Version,
    string GuidePath,
    IReadOnlyList<string> TriggerTags,
    IReadOnlyList<string> DesignDna,
    IReadOnlyList<string> GodotControls,
    IReadOnlyList<string> GameCompositionTemplates);

public sealed record GodotUiComponentTier(
    string TierId,
    IReadOnlyList<string> ComponentFamilies,
    string DefaultCoverageStatus);

public sealed record GodotUiStyleCapability(
    string CapabilityId,
    string GodotTranslation);
