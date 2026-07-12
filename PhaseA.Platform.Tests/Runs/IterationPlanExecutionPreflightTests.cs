using System.Text.Json;
using System.Text.Json.Nodes;
using FluentAssertions;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class IterationPlanExecutionPreflightTests
{
    [Fact]
    public void DiagnosticScope_ShouldRequireExactKindAndReferencePairs()
    {
        var exact = JsonSerializer.Serialize(new[]
        {
            new { kind = "source_hash_ref", @ref = "source-a" },
            new { kind = "plan_hash", @ref = "plan-a" }
        });
        var substringOnly = JsonSerializer.Serialize(new[]
        {
            new { kind = "other", @ref = "prefix-source-a-suffix" },
            new { kind = "plan_hash", @ref = "plan-a-other" }
        });

        PrototypeIterationGoalService.HasDiagnosticScope(exact, "source-a", "plan-a").Should().BeTrue();
        PrototypeIterationGoalService.HasDiagnosticScope(substringOnly, "source-a", "plan-a").Should().BeFalse();
        PrototypeIterationGoalService.HasDiagnosticScope("[]", "no-source", "no-plan").Should().BeFalse();
    }

    [Fact]
    public void Evaluate_ShouldAllowCompleteCapabilityEvidence()
    {
        var result = IterationPlanExecutionPreflight.Evaluate(State().ToJsonString(), "session-1", 1, SourceHashes());

        result.Allowed.Should().BeTrue();
    }

    [Fact]
    public void Evaluate_ShouldBlockBeforeRun_WhenCurrentPlanIsNotConfirmed()
    {
        var state = State();
        state["confirmation"]!["status"] = "unconfirmed";

        var result = IterationPlanExecutionPreflight.Evaluate(state.ToJsonString(), "session-1", 1, SourceHashes());

        result.DomainCode.Should().Be("plan_confirmation_required");
    }

    [Fact]
    public void Evaluate_ShouldKeepLegacyPlanReadableButBlockExecutionWithoutHashes()
    {
        var state = State();
        state.AsObject().Remove("source_contract_hash");

        var result = IterationPlanExecutionPreflight.Evaluate(state.ToJsonString(), "session-1", 1, SourceHashes());

        result.DomainCode.Should().Be("source_stale");
    }

    [Fact]
    public void Evaluate_ShouldBlockDynamicUiBeforeRun_WhenOwnershipIsIncomplete()
    {
        var state = State();
        state["goals"]![0]!["godot_ui_update_ownership"]!.AsObject().Remove("signal_ownership");
        RefreshPlanHash(state);

        var result = IterationPlanExecutionPreflight.Evaluate(state.ToJsonString(), "session-1", 1, SourceHashes());

        result.Allowed.Should().BeFalse();
        result.DomainCode.Should().Be("ui_update_ownership_missing");
    }

    [Fact]
    public void Evaluate_ShouldBlockThirdPersonCameraBeforeRun_WhenProfileIsIncomplete()
    {
        var state = State();
        state["goals"]![0]!["godot_third_person_camera_profile"]!.AsObject().Remove("camera_relative_movement_boundary");
        RefreshPlanHash(state);

        var result = IterationPlanExecutionPreflight.Evaluate(state.ToJsonString(), "session-1", 1, SourceHashes());

        result.DomainCode.Should().Be("third_person_camera_profile_missing");
    }

    [Fact]
    public void Evaluate_ShouldBlockFeatureFamilyBeforeRun_WhenReadingEvidenceIsMissing()
    {
        var state = State();
        state["goals"]![0]!["engine_semantics"]!["reading_evidence_refs"] = new JsonArray();
        RefreshPlanHash(state);

        var result = IterationPlanExecutionPreflight.Evaluate(state.ToJsonString(), "session-1", 1, SourceHashes());

        result.DomainCode.Should().Be("feature_family_reading_missing");
    }

    [Fact]
    public void Evaluate_ShouldBlockInteractionHeavyGoalBeforeRun_WhenArtifactIsMissing()
    {
        var state = State();
        state["goals"]![0]!.AsObject().Remove("interaction_region");
        RefreshPlanHash(state);

        var result = IterationPlanExecutionPreflight.Evaluate(state.ToJsonString(), "session-1", 1, SourceHashes());

        result.DomainCode.Should().Be("interaction_region_missing");
    }

    [Fact]
    public void Evaluate_ShouldBlockWhenConfirmedGoalPayloadNoLongerMatchesPlanHash()
    {
        var state = State();
        state["goals"]![0]!["description"] = "tampered after confirmation";

        var result = IterationPlanExecutionPreflight.Evaluate(state.ToJsonString(), "session-1", 1, SourceHashes());

        result.DomainCode.Should().Be("plan_hash_mismatch");
    }

    [Fact]
    public void Evaluate_ShouldBlockWhenConfirmedCoveragePayloadNoLongerMatchesPlanHash()
    {
        var state = State();
        state["coverage"]!["uncovered_requirement_ids"] = new JsonArray("REQ-999");

        var result = IterationPlanExecutionPreflight.Evaluate(state.ToJsonString(), "session-1", 1, SourceHashes());

        result.DomainCode.Should().Be("plan_hash_mismatch");
    }

    [Fact]
    public void Evaluate_ShouldBlockRecomputedWorkspacePlanAgainstTrustedAnchor()
    {
        var state = State();
        var trustedAnchor = JsonSerializer.Serialize(new
        {
            status = "confirmed",
            session_id = "session-1",
            plan_hash = state["plan_hash"]!.GetValue<string>(),
            source_hash_ref = "source-ref-1"
        });
        state["goals"]![0]!["description"] = "tampered and recomputed";
        RefreshPlanHash(state);

        var result = IterationPlanExecutionPreflight.Evaluate(
            state.ToJsonString(),
            "session-1",
            1,
            SourceHashes(),
            trustedAnchorJson: trustedAnchor,
            requireTrustedAnchor: true);

        result.DomainCode.Should().Be("plan_confirmation_anchor_mismatch");
    }

    [Fact]
    public void Evaluate_ShouldAllowReviewedStyleNotApplicableWithoutSnapshotHash()
    {
        var state = State();
        var hashes = SourceHashes() with { UiStyleSnapshotHash = "" };
        var applicability = new PrototypeIterationStyleApplicability(
            "reviewed_not_applicable",
            "No visible UI requirement is present in the frozen requirement map.",
            "system",
            "when a visible UI requirement is added",
            "style-applicability-evidence-hash");
        var sourceHashRef = IterationPlanTraceabilityBuilder.ComputeSourceHashRef(hashes, applicability);
        state["ui_style_snapshot_hash"] = "";
        state["style_applicability"] = JsonNode.Parse("""
        {
          "status": "reviewed_not_applicable",
          "reason": "No visible UI requirement is present in the frozen requirement map.",
          "reviewed_by": "system",
          "recheck_trigger": "when a visible UI requirement is added",
          "evidence_hash": "style-applicability-evidence-hash"
        }
        """);
        state["source_hash_ref"] = sourceHashRef;
        state["confirmation"]!["source_hash_ref"] = sourceHashRef;
        state["goals"]![0]!["source_hash_ref"] = sourceHashRef;
        state["goals"]![0]!["ui_surface"] = JsonNode.Parse("""
        {
          "scene_owner": "inventory",
          "node_owner": "InventoryPanel",
          "surface_type": "godot_control_surface"
        }
        """);
        RefreshPlanHash(state);

        var result = IterationPlanExecutionPreflight.Evaluate(
            state.ToJsonString(),
            "session-1",
            1,
            hashes,
            currentStyleApplicability: applicability);

        result.Allowed.Should().BeTrue(result.Summary);
    }

    [Fact]
    public void Evaluate_ShouldBlockWhenPlanContainsUnresolvedBlocker()
    {
        var state = State();
        state["blockers"]!.AsArray().Add(new JsonObject { ["domain_code"] = "coverage_gap" });
        RefreshPlanHash(state);

        var result = IterationPlanExecutionPreflight.Evaluate(state.ToJsonString(), "session-1", 1, SourceHashes());

        result.DomainCode.Should().Be("plan_blocked");
    }

    private static JsonObject State()
    {
        var state = JsonNode.Parse("""
        {
          "session_id": "session-1",
          "status": "ready",
          "source_gdd_hash": "gdd-hash",
          "source_scene_route_hash": "scene-hash",
          "source_requirement_map_hash": "requirement-map-hash",
          "source_contract_hash": "contract-hash",
          "source_contract_snapshot_hash": "contract-snapshot-hash",
          "source_godot_ui_contract_hash": "godot-ui-hash",
          "source_ui_style_contract_hash": "ui-style-contract-hash",
          "ui_style_snapshot_hash": "ui-style-snapshot-hash",
          "source_hash_ref": "source-ref-1",
          "plan_hash": "pending",
          "coverage": {
            "uncovered_requirement_ids": []
          },
          "blockers": [],
          "required_modules": [],
          "confirmation": {
            "status": "confirmed",
            "session_id": "session-1",
            "plan_hash": "pending",
            "source_hash_ref": "source-ref-1"
          },
          "goals": [
            {
              "goal_index": 1,
              "title": "Inventory UI",
              "description": "Build inventory UI",
              "acceptance_hint": "Inventory is interactive",
              "status": "pending",
              "requirement_ids": ["REQ-001"],
              "infrastructure_reason": null,
              "source_hash_ref": "source-ref-1",
              "capability_requirements": {
                "dynamic_ui_required": true,
                "third_person_camera_required": true,
                "feature_family_reading_required": true,
                "interaction_region_required": true
              },
              "godot_ui_update_ownership": {
                "construction_owner": "InventoryPanel",
                "update_mode": "signal_driven",
                "state_owner": "InventoryState",
                "cleanup_policy": "disconnect_on_exit",
                "signal_ownership": "InventoryState",
                "stable_item_identity": "item_id"
              },
              "godot_third_person_camera_profile": {
                "rig_ref": "res://Camera/ThirdPersonRig.tscn",
                "target_owner": "Player",
                "input_owner": "PlayerInput",
                "collision_owner": "ThirdPersonRig",
                "yaw_pitch_ownership": "ThirdPersonRig",
                "camera_relative_movement_boundary": "PlayerMotor",
                "camera_state_validation": "camera-state-smoke"
              },
              "engine_semantics": {
                "profile_refs": ["repo-owned-feature-profile"],
                "reading_evidence_refs": ["docs/standards/godot-engine-semantics.md"]
              },
              "interaction_region": {
                "artifact_ref": "meta/routes/iteration-plan/interaction-regions/goal-01.json",
                "validation_refs": ["interaction-region-smoke"]
              }
            }
          ]
        }
        """)!.AsObject();
        RefreshPlanHash(state);
        return state;
    }

    private static void RefreshPlanHash(JsonObject state)
    {
        using var document = JsonDocument.Parse(state.ToJsonString());
        var planHash = IterationPlanIntegrity.Compute(document.RootElement);
        state["plan_hash"] = planHash;
        state["confirmation"]!["plan_hash"] = planHash;
    }

    private static PrototypeIterationPlanSourceHashes SourceHashes()
    {
        return new PrototypeIterationPlanSourceHashes(
            "gdd-hash",
            "scene-hash",
            "requirement-map-hash",
            "contract-hash",
            "contract-snapshot-hash",
            "godot-ui-hash",
            "ui-style-contract-hash",
            "ui-style-snapshot-hash");
    }
}
