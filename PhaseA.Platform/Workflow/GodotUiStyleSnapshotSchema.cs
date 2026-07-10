using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class GodotUiStyleSnapshotSchema
{
    public const string SchemaId = "godot-ui-style-contract";
    public const string SchemaVersion = "1";
    public const string SchemaVersionValue = "godot-ui-style-contract.v1";
    public const string DurableFixturePath = "docs/schemas/godot-ui-style-contract.v1.example.json";
    public const string SourcePlanFixturePath = "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/schemas/godot-ui-style-contract.v1.example.json";

    public static readonly IReadOnlyList<string> RequiredTopLevelFields =
    [
        "schema_version",
        "ui_style_id",
        "ui_style_version",
        "source_ui_style_contract_hash",
        "ui_style_snapshot_hash",
        "selected_by",
        "selection_reason",
        "capability_packages",
        "runtime_environment",
        "palette_tokens",
        "typography_tokens",
        "component_defaults",
        "component_family_baseline",
        "component_coverage_matrix",
        "font_policy",
        "godot_theme_resources",
        "ui_tree_readback_requirements",
        "ui_tree_readback_rows",
        "visual_evidence_matrix",
        "visual_validation_refs",
        "forbidden_patterns"
    ];

    public static readonly IReadOnlyList<string> HashIdentityFields =
    [
        "schema_version",
        "ui_style_id",
        "ui_style_version",
        "source_ui_style_contract_hash",
        "runtime_environment",
        "design_dna_rules",
        "palette_tokens",
        "typography_tokens",
        "spacing_tokens",
        "component_defaults",
        "component_family_baseline",
        "component_coverage_matrix",
        "godot_theme_resources"
    ];

    public static readonly IReadOnlyList<string> Phase0CapabilityIds =
    [
        "ui_style_snapshot_schema",
        "ui_runtime_environment_identity",
        "ui_theme_resource_contract",
        "ui_visual_evidence_contract"
    ];

    public static readonly IReadOnlyList<string> AcceptanceCapabilityIds =
        GodotUiStyleCatalog.Capabilities.Select(capability => capability.CapabilityId)
            .Concat(Phase0CapabilityIds)
            .Concat(GodotUiStyleClosureContract.CapabilityIds)
            .Concat([
                "ui_style_schema_acceptance_gate",
                "godot_diagnostic_spool_contract",
                "godot_failure_family_taxonomy",
                "godot_prebuild_preview_quality_gate",
                "godot_interaction_region_gate",
                "godot_resource_lifecycle_gate"
            ])
            .ToArray();

    public static readonly IReadOnlyList<string> AllowedSelectedBy =
    [
        "user",
        "workflow",
        "admin",
        "fallback"
    ];

    public static readonly IReadOnlyList<string> AllowedStyleIds =
        GodotUiStyleCatalog.Styles.Select(style => style.StyleId).Concat(["custom"]).ToArray();

    public static readonly IReadOnlyList<string> AllowedRendererValues =
    [
        "forward_plus",
        "mobile",
        "compatibility",
        "unknown"
    ];

    public static readonly IReadOnlyList<string> AllowedExportTargets =
    [
        "windows",
        "web",
        "linux",
        "macos",
        "android",
        "ios",
        "editor_headless",
        "unknown"
    ];

    public static readonly IReadOnlyList<string> AllowedEvidenceTypes =
    [
        "screenshot",
        "canvas_pixel",
        "exported_visual",
        "ui_tree_readback",
        "deterministic_substitute"
    ];

    public static readonly IReadOnlyList<string> RequiredActiveArrayFields =
    [
        "design_dna_rules",
        "capability_packages",
        "palette_tokens",
        "typography_tokens",
        "component_defaults",
        "component_family_baseline",
        "component_coverage_matrix",
        "godot_theme_resources",
        "ui_tree_readback_requirements",
        "visual_evidence_matrix",
        "forbidden_patterns"
    ];

    public static readonly IReadOnlyList<string> OptionalEmptyArrayFields =
    [
        "source_inspiration",
        "public_aliases",
        "trigger_tags",
        "suitable_game_tags",
        "visual_validation_refs"
    ];

    public static readonly IReadOnlyList<string> DocumentedVolatileHashExclusions =
    [
        "ui_style_snapshot_hash",
        "selected_by",
        "selection_reason",
        "visual_validation_refs"
    ];

    public static readonly IReadOnlyList<string> CustomStyleRequiredFields =
    [
        "owner",
        "version",
        "source_hash",
        "artifact_ref",
        "created_utc",
        "readback_path_policy"
    ];

    public static readonly IReadOnlyList<string> PublicAliasApprovalRequiredFields =
    [
        "alias",
        "approval_ref",
        "reviewer_owner",
        "approved_utc",
        "decision_log_ref",
        "validation_status"
    ];

    public static readonly IReadOnlyList<string> ThemeResourceRequiredFields =
    [
        "resource_ref",
        "resource_type",
        "node_or_control_owner",
        "token_source",
        "theme_slot_mappings",
        "resource_load_validation_ref",
        "export_package_validation_ref",
        "deterministic_diff_ref",
        "packaging_evidence_refs",
        "readback_path_policy"
    ];

    public static readonly IReadOnlyList<string> DeterministicSubstituteRequiredFields =
    [
        "limitation_type",
        "owner",
        "approved_by",
        "approved_utc",
        "expires_utc",
        "recheck_trigger",
        "replacement_evidence_plan",
        "cannot_substitute_for"
    ];

    public static string SchemaProfileHash => Sha256(string.Join("\n",
        [
            SchemaId,
            SchemaVersion,
            SchemaVersionValue,
            DurableFixturePath,
            SourcePlanFixturePath,
            string.Join("|", RequiredTopLevelFields),
            string.Join("|", HashIdentityFields),
            string.Join("|", Phase0CapabilityIds),
            string.Join("|", AllowedSelectedBy),
            string.Join("|", AllowedStyleIds),
            string.Join("|", AllowedRendererValues),
            string.Join("|", AllowedExportTargets),
            string.Join("|", AllowedEvidenceTypes),
            string.Join("|", RequiredActiveArrayFields),
            string.Join("|", OptionalEmptyArrayFields),
            string.Join("|", AcceptanceCapabilityIds),
            string.Join("|", DocumentedVolatileHashExclusions),
            string.Join("|", CustomStyleRequiredFields),
            string.Join("|", PublicAliasApprovalRequiredFields),
            string.Join("|", ThemeResourceRequiredFields),
            string.Join("|", DeterministicSubstituteRequiredFields)
        ]));

    private static string Sha256(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}
