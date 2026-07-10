using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GodotUiStyleClosureContractTests
{
    [Fact]
    public void ClosureContract_ShouldDeclareStableCapabilityIds()
    {
        GodotUiStyleClosureContract.CapabilityIds.Should().Contain([
            "ui_style_closure_gap_taxonomy",
            "ui_style_repair_prompt_contract",
            "ui_final_readiness_style_gate"
        ]);
        GodotUiStyleClosureContract.ContractHash.Should().NotBeNullOrWhiteSpace();
    }

    [Fact]
    public void GapRows_ShouldUseNormalizedStyleDriftTaxonomy()
    {
        GodotUiStyleClosureContract.IsKnownGapFamily("palette").Should().BeTrue();
        GodotUiStyleClosureContract.IsKnownGapFamily("visual_evidence_method").Should().BeTrue();
        GodotUiStyleClosureContract.IsKnownGapFamily("mutable_heading").Should().BeFalse();
        GodotUiStyleClosureContract.GapRowRequiredFields.Should().Contain([
            "requirement_ids",
            "scene_node_path",
            "expected_style_token_or_rule",
            "observed_drift",
            "visual_evidence_method",
            "follow_up_goal_recommendation"
        ]);
    }

    [Fact]
    public void FinalReadiness_ShouldRejectInterimCoverageStatus()
    {
        GodotUiStyleClosureContract.FullTargetClosureStatuses.Should().BeEquivalentTo([
            "covered",
            "reviewed_not_applicable",
            "explicitly_deferred"
        ]);
        GodotUiStyleClosureContract.InterimOnlyCoverageStatuses.Should().Contain("not_consumed_by_first_slice");
        GodotUiStyleClosureContract.IsFinalReadinessBlockingSeverity("P0").Should().BeTrue();
        GodotUiStyleClosureContract.IsFinalReadinessBlockingSeverity("P1").Should().BeTrue();
        GodotUiStyleClosureContract.IsFinalReadinessBlockingSeverity("P2").Should().BeFalse();
    }

    [Fact]
    public void RepairPromptInputs_ShouldUseFrozenSnapshotAndReadbackRefs()
    {
        GodotUiStyleClosureContract.RepairPromptRequiredInputs.Should().Contain([
            "frozen_style_snapshot_ref",
            "runtime_environment_ref",
            "component_defaults_ref",
            "pointer_event_shape_ref",
            "gesture_phase_ref",
            "drag_drop_payload_policy_ref",
            "theme_resource_token_coverage_ref",
            "ui_tree_readback_refs"
        ]);
    }
}
