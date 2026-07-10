using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class GodotUiStyleClosureContract
{
    public const string ContractId = "godot-ui-style-closure";
    public const string ContractVersion = "1";
    public const string StandardPath = "docs/standards/godot-ui-style-closure.md";

    public static readonly IReadOnlyList<string> CapabilityIds =
    [
        "ui_style_closure_gap_taxonomy",
        "ui_style_repair_prompt_contract",
        "ui_final_readiness_style_gate"
    ];

    public static readonly IReadOnlyList<string> GapRowRequiredFields =
    [
        "gap_id",
        "style_drift_family",
        "requirement_ids",
        "scene_node_path",
        "expected_style_token_or_rule",
        "observed_drift",
        "severity",
        "affected_viewport_or_component_state",
        "visual_evidence_method",
        "follow_up_goal_recommendation",
        "status"
    ];

    public static readonly IReadOnlyList<string> RepairPromptRequiredInputs =
    [
        "frozen_style_snapshot_ref",
        "runtime_environment_ref",
        "affected_node_paths",
        "component_defaults_ref",
        "exception_rules_ref",
        "composition_rules_ref",
        "motion_transition_rules_ref",
        "pointer_event_shape_ref",
        "gesture_phase_ref",
        "drag_drop_payload_policy_ref",
        "theme_resource_token_coverage_ref",
        "visual_evidence_method",
        "ui_tree_readback_refs"
    ];

    public static readonly IReadOnlyList<string> FinalReadinessBlockingSeverities =
    [
        "P0",
        "P1"
    ];

    public static readonly IReadOnlyList<string> FullTargetClosureStatuses =
    [
        "covered",
        "reviewed_not_applicable",
        "explicitly_deferred"
    ];

    public static readonly IReadOnlyList<string> InterimOnlyCoverageStatuses =
    [
        "not_consumed_by_first_slice"
    ];

    public static string ContractHash => Sha256(string.Join("\n",
        [
            ContractId,
            ContractVersion,
            StandardPath,
            string.Join("|", CapabilityIds),
            string.Join("|", GapRowRequiredFields),
            string.Join("|", RepairPromptRequiredInputs),
            string.Join("|", FinalReadinessBlockingSeverities),
            string.Join("|", FullTargetClosureStatuses),
            string.Join("|", InterimOnlyCoverageStatuses)
        ]));

    public static bool IsKnownGapFamily(string family)
    {
        return GodotUiStyleCatalog.IsKnownDriftFamily(family);
    }

    public static bool IsFinalReadinessBlockingSeverity(string severity)
    {
        return FinalReadinessBlockingSeverities.Contains(severity, StringComparer.Ordinal);
    }

    public static bool IsFullTargetClosureStatus(string status)
    {
        return FullTargetClosureStatuses.Contains(status, StringComparer.Ordinal);
    }

    private static string Sha256(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}
