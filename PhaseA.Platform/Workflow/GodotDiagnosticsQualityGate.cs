using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class GodotDiagnosticsQualityGate
{
    public const string ContractId = "godot-diagnostics-quality-gate";
    public const string ContractVersion = "v1";
    public const string StandardPath = "docs/standards/godot-diagnostics-quality-gates.md";
    public const string SchemaExamplePath = "docs/schemas/project-diagnostic-spool.v1.example.json";

    public static readonly IReadOnlyList<string> CapabilityIds =
    [
        "godot_diagnostic_spool_contract",
        "godot_failure_family_taxonomy",
        "godot_prebuild_preview_quality_gate",
        "godot_interaction_region_gate",
        "godot_resource_lifecycle_gate"
    ];

    public static readonly IReadOnlyList<string> FailureFamilies =
    [
        "gdd_missing",
        "gdd_form_missing",
        "game_type_structured_missing",
        "game_type_structured_stale",
        "scene_route_missing",
        "scene_route_unconfirmed",
        "gdd_scene_hash_write_failed",
        "generated_gdd_hash_mismatch",
        "requirement_map_invalid",
        "coverage_gap",
        "contract_stale",
        "source_unknown",
        "ui_contract_unknown",
        "prototype_skeleton_stale",
        "workflow_recommendation_unmapped",
        "missing_ui_surface",
        "reference_example_missing",
        "reference_example_manifest_missing",
        "godot_recipe_missing",
        "feature_family_reading_missing",
        "geometry_size_source_missing",
        "material_profile_missing",
        "rendering_profile_missing",
        "animation_state_profile_missing",
        "ui_update_ownership_missing",
        "third_person_camera_profile_missing",
        "godot_build_failed",
        "scene_load_failed",
        "preview_blank",
        "package_missing",
        "workspace_delete_failed",
        "duplicate_active_run",
        "diagnostic_spool_write_failed"
    ];

    public static readonly IReadOnlyList<string> RouteSeeds =
    [
        "structured-game-type-analysis",
        "gdd-question-form",
        "gdd-requirements",
        "gdd-document-generation",
        "scene-route-confirmation",
        "prototype-contract",
        "prototype-skeleton",
        "workflow-recommendation",
        "iteration-plan",
        "execute-next-goal",
        "needs-fix",
        "repair",
        "ui-wiring-closure",
        "preview-package",
        "project-delete"
    ];

    public static readonly IReadOnlyList<string> SeverityValues = ["P0", "P1", "P2", "info"];
    public static readonly IReadOnlyList<string> TriageStatuses = ["unresolved", "resolved", "ignored", "backlog"];
    public static readonly IReadOnlyList<string> RedactionStatuses = ["redacted", "raw_admin_only", "blocked"];
    public static readonly IReadOnlyList<string> RetentionClasses = ["unresolved_blocker", "resolved_audit", "ignored_audit", "backlog_audit", "info_ephemeral"];
    public static readonly IReadOnlyList<string> CleanupStatuses = ["preserved", "compacted", "redacted_compacted", "eligible_after_retention", "not_eligible"];

    public static readonly IReadOnlyList<string> RequiredSpoolColumns =
    [
        "diagnostic_id",
        "account_id",
        "project_id",
        "project_name_snapshot",
        "run_id",
        "route",
        "failure_family",
        "severity",
        "triage_status",
        "retention_class",
        "redaction_status",
        "spool_ref",
        "user_safe_summary",
        "source_refs_json",
        "evidence_refs_json",
        "created_utc",
        "updated_utc",
        "resolved_utc",
        "triage_decision_by",
        "triage_decision_reason",
        "deletion_event_id",
        "project_tombstone_id"
    ];

    public static readonly IReadOnlyList<DiagnosticRemediationRow> RemediationRows =
    [
        Row("gdd_missing", "gdd-requirements", "GDD route state or draft artifact is missing.", "Return to GDD creation or draft-completion flow and block downstream route generation."),
        Row("gdd_form_missing", "gdd-question-form", "GDD question-form source is missing for a legacy GDD-only project.", "Offer non-destructive GDD form import/backfill or new GDD question-form confirmation before scene route confirmation."),
        Row("game_type_structured_missing", "structured-game-type-analysis", "Project structured game-type metadata is missing.", "Block scene route or requirement map generation until project metadata is analyzed or repaired."),
        Row("game_type_structured_stale", "structured-game-type-analysis", "Project structured game-type metadata changed after scene confirmation.", "Mark scene route stale and require reconfirmation or contract snapshot refresh before requirement mapping."),
        Row("scene_route_missing", "scene-route-confirmation", "GDD run completes but no scene confirmation appears.", "Regenerate scene route or mark route state invalid with evidence."),
        Row("scene_route_unconfirmed", "scene-route-confirmation", "Workflow recommends scene confirmation but the user cannot confirm it.", "Block requirement map generation until confirmation mapping exists or route state is repaired."),
        Row("gdd_scene_hash_write_failed", "gdd-document-generation", "GDD document generation cannot write its hash back to scene route state.", "Preserve GDD generation evidence, block requirement map generation, and repair scene-route sidecar write path."),
        Row("generated_gdd_hash_mismatch", "gdd-document-generation", "Generated GDD no longer matches confirmed scene route state.", "Reconfirm scene route or create a requirement-map mismatch blocker before downstream generation."),
        Row("requirement_map_invalid", "gdd-requirements", "Requirement map is empty or too small.", "Regenerate requirement map; block contract freeze if P0/P1 gaps remain."),
        Row("coverage_gap", "iteration-plan", "Iteration plan ignores required modules.", "Block plan or create follow-up required module goals."),
        Row("contract_stale", "execute-next-goal", "Execute-next-goal starts from stale source.", "Reject before Codex invocation and recommend refresh/freeze."),
        Row("source_unknown", "execute-next-goal", "Route cannot prove which frozen source produced an artifact.", "Reject downstream execution and regenerate from declared authority sources."),
        Row("ui_contract_unknown", "ui-wiring-closure", "UI-facing requirement lacks a frozen UI capability contract.", "Refresh requirement map/contract after the UI capability contract is available."),
        Row("prototype_skeleton_stale", "prototype-skeleton", "Prototype skeleton starts without a fresh frozen contract.", "Reject new-chain skeleton creation and require contract refresh/freeze."),
        Row("workflow_recommendation_unmapped", "workflow-recommendation", "Workflow recommendation emits an unmapped action.", "Block primary action display and repair descriptor or recommendation mapping."),
        Row("missing_ui_surface", "ui-wiring-closure", "UI closure says success but player cannot use feature.", "Create UI follow-up goal and block final readiness."),
        Row("reference_example_missing", "repair", "Required local Godot reference example is missing.", "Add or refresh the curated reference index, approve substitute repo-owned evidence, or block the touched semantic family."),
        Row("reference_example_manifest_missing", "repair", "Example copy is requested but the example directory has no usable manifest.", "Add a manifest, approve substitute copy evidence, or block copying while allowing read-only API-pattern reference use."),
        Row("godot_recipe_missing", "repair", "Required Godot feature-family recipe or durable standard row is missing.", "Add or refresh the recipe/standard index, approve substitute evidence, or block implementation for the touched feature family."),
        Row("feature_family_reading_missing", "execute-next-goal", "A touched P0/P1 feature family has no recorded reading evidence.", "Record feature-family reading evidence or return to the appropriate planning/repair step."),
        Row("geometry_size_source_missing", "execute-next-goal", "Geometry or fixed-format UI work has no measured size source.", "Block implementation or repair route state until size source and coordinate space are recorded."),
        Row("material_profile_missing", "ui-wiring-closure", "Material, shader, texture, or pure-color visual work lacks a repo-approved Godot profile.", "Select or extend a repo-approved material profile with evidence."),
        Row("rendering_profile_missing", "ui-wiring-closure", "Lighting, fog, sky, environment, or postprocess work lacks a repo-approved rendering profile.", "Select or extend a rendering profile and record readability evidence."),
        Row("animation_state_profile_missing", "ui-wiring-closure", "Character animation or state-machine work lacks a declared animation profile.", "Select or extend an animation profile or block character animation readiness."),
        Row("ui_update_ownership_missing", "ui-wiring-closure", "Dynamic UI updates do not declare construction owner, update ownership, state owner, or cleanup path.", "Block UI closure or create a follow-up repair goal."),
        Row("third_person_camera_profile_missing", "ui-wiring-closure", "Third-person camera work does not use or create the repo-owned camera rig/profile.", "Create or repair the shared camera rig/profile."),
        Row("godot_build_failed", "preview-package", "Godot build or validation command fails.", "Run repair with preserved diagnostics and block preview/package readiness."),
        Row("scene_load_failed", "preview-package", "Godot scene fails to load.", "Run repair with latest Godot diagnostic evidence."),
        Row("preview_blank", "preview-package", "Preview opens blank or stale content.", "Rebuild preview/package from current source hash set."),
        Row("package_missing", "preview-package", "Package artifact is missing.", "Re-run package or surface artifact readback blocker."),
        Row("workspace_delete_failed", "project-delete", "Project deletion fails or leaves workspace.", "Preserve diagnostic spool and surface admin cleanup action."),
        Row("duplicate_active_run", "workflow-recommendation", "Active run is reused incorrectly.", "Reject stale reuse and start or resume only matching hash scope."),
        Row("diagnostic_spool_write_failed", "workflow-recommendation", "Diagnostic spool write or index update fails.", "Return a structured blocker and repair spool/index before readiness.")
    ];

    public static readonly string ContractHash = ComputeHash();

    public static bool IsKnownFailureFamily(string family)
    {
        return FailureFamilies.Contains(family, StringComparer.Ordinal);
    }

    public static bool IsBlockingSeverity(string severity)
    {
        return severity is "P0" or "P1" or "P2";
    }

    private static DiagnosticRemediationRow Row(string family, string route, string symptom, string recovery)
    {
        return new DiagnosticRemediationRow(
            family,
            route,
            symptom,
            "Return only redacted user-safe summaries; raw host paths, token material, provider secrets, and raw prompts are forbidden.",
            "Admin evidence uses metadata DB diagnostic index rows and preserved spool refs outside hosted workspaces.",
            recovery);
    }

    private static string ComputeHash()
    {
        var source = string.Join("\n", CapabilityIds.Concat(FailureFamilies).Concat(RouteSeeds).Concat(RemediationRows.Select(row => $"{row.FailureFamily}|{row.OwnerRoute}|{row.Symptom}|{row.RecoveryAction}")));
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(source))).ToLowerInvariant();
    }
}

public sealed record DiagnosticRemediationRow(
    string FailureFamily,
    string OwnerRoute,
    string Symptom,
    string UserSafeSummaryPolicy,
    string AdminEvidencePolicy,
    string RecoveryAction);
