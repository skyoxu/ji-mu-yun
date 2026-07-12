using FluentAssertions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class ProjectRouteStateArtifactServiceTests
{
    [Fact]
    public void Read_WhenPromptRouteOmitsBoundaryDetails_BlocksWithSourceBoundaryIssue()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", """
        {
          "schema_version": "gdd-requirements.v1",
          "route": "gdd-requirements",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "needs_review", "blocked", "stale", "unknown"],
          "status": "ready",
          "source_boundary_enforced": true,
          "source_boundary": {
            "authority_sources": ["docs/gdd/GDD.md"]
          },
          "requirements": []
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.Status.Should().Be("blocked");
        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-requirements/latest.json:source_boundary_incomplete" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenNonPromptRouteDisablesBoundaryWithoutReason_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "source_boundary_enforced": false,
          "ui_surface_matrix": []
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/ui-wiring/latest.json:source_boundary_not_applicable_missing");
    }

    [Fact]
    public void Read_WhenStatusIsOutsideDeclaredSubset_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-document/latest.json", """
        {
          "schema_version": "gdd-document-generation.v1",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "blocked"],
          "status": "surprising"
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-document/latest.json:status_outside_declared_subset");
    }

    [Fact]
    public void Read_WhenSidecarUsesStatusFromWrongDimension_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-document/latest.json", """
        {
          "schema_version": "gdd-document-generation.v1",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "completed"],
          "status": "completed"
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-document/latest.json:status_allowed_values_outside_dimension");
        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-document/latest.json:status_outside_dimension");
    }

    [Fact]
    public void Read_WhenCanonicalAndMirrorContractDiffer_MarksCanonicalStale()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("routes/prototype-contract/latest.json", """
        {
          "schema_version": "prototype-contract.v1",
          "status": "fresh",
          "contract_hash": "canonical"
        }
        """);
        fixture.WriteJson("meta/routes/prototype-contract/latest.json", """
        {
          "schema_version": "prototype-contract.v1",
          "status": "fresh",
          "contract_hash": "mirror"
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        var contract = readback.Artifacts.Single(artifact => artifact.Route == "prototype-contract");
        contract.Authority.Should().Be("authority");
        contract.Freshness.Should().Be("stale");
        contract.BlockingIssueIds.Should().Contain("prototype-contract:mirror_hash_mismatch");
    }

    [Fact]
    public void Read_WhenP0RequirementHasGap_BlocksContractFreeze()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", """
        {
          "schema_version": "gdd-requirements.v1",
          "status": "ready",
          "source_boundary_enforced": true,
          "source_boundary": {
            "authority_sources": ["docs/gdd/GDD.md"],
            "forbidden_source_patterns": ["docs/game-type-guides/** raw excerpts"]
          },
          "requirements": [
            {
              "requirement_id": "REQ-001",
              "priority": "P0",
              "status": "missing_module"
            }
          ]
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "gdd-requirements:REQ-001:requirement_p0_gap" &&
            issue.DomainCode == "requirement_p0_gap" &&
            issue.Severity == "P0");
    }

    [Fact]
    public void Read_WhenP1DeferredBySystem_BlocksForAdminDecision()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-requirements/latest.json", """
        {
          "schema_version": "gdd-requirements.v1",
          "status": "ready",
          "requirements": [
            {
              "requirement_id": "REQ-002",
              "priority": "P1",
              "status": "explicitly_deferred",
              "decision_by": "system",
              "decision_role": "system",
              "decision_utc": "2026-07-10T00:00:00Z",
              "decision_reason": "fallback",
              "affected_requirement_ids": ["REQ-002"]
            }
          ]
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "gdd-requirements:REQ-002:admin_decision_required" &&
            issue.DomainCode == "admin_review_blocked");
    }

    [Fact]
    public void Read_WhenUiWiringSurfaceOmitsRequiredFields_BlocksClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [
            {
              "feature": "route_map",
              "status": "covered",
              "godot_surface_type": "control"
            }
          ]
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "ui-wiring:route_map:godot_ui_surface_incomplete" &&
            issue.DomainCode == "diagnostic_blocked");
    }

    [Fact]
    public void Read_WhenP1NoUiNeededLacksReviewMetadata_BlocksClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [
            {
              "feature": "combat_hud",
              "priority": "P1",
              "status": "no_ui_needed",
              "capability_domain_ids": ["hud_menus_overlays"]
            }
          ]
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "ui-wiring:combat_hud:godot_ui_no_ui_needed_review_missing" &&
            issue.DomainCode == "admin_review_blocked" &&
            issue.Severity == "P1");
    }

    [Fact]
    public void Read_WhenUiSurfaceUsesUnknownProfilesOrForbiddenTechnology_BlocksClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [
            {
              "feature": "reward_screen",
              "priority": "P1",
              "status": "covered",
              "capability_domain_ids": ["rendering_materials_shaders", "animation_state_machines"],
              "godot_scene_path": "res://Scenes/UI/RewardScreen.tscn",
              "godot_surface_type": "control",
              "layout_strategy": "responsive_control_layout",
              "input_paths": ["ui_accept"],
              "feedback_states": ["hover", "selected"],
              "camera_layer_boundary": "CanvasLayer:ui",
              "viewport_mode": "responsive_control_layout",
              "ui_update_ownership_mode": "invented",
              "state_boundary": "RewardScreenState",
              "material_profile": "PBRNoTexture",
              "rendering_profile": "invented",
              "animation_profile": "raw_strings"
            }
          ]
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Select(issue => issue.IssueId).Should().Contain([
            "ui-wiring:reward_screen:technology_stack_leakage",
            "ui-wiring:reward_screen:ui_update_ownership_missing",
            "ui-wiring:reward_screen:material_profile_missing",
            "ui-wiring:reward_screen:rendering_profile_missing",
            "ui-wiring:reward_screen:animation_state_profile_missing"
        ]);
    }

    [Fact]
    public void Read_WhenUiSurfaceHasCompleteGodotCapabilityEvidence_AllowsClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [
            {
              "feature": "route_map",
              "priority": "P1",
              "status": "covered",
              "capability_domain_ids": ["ui_scene_architecture", "custom_2d_drawing", "input_focus_navigation"],
              "godot_scene_path": "res://Scenes/UI/RouteMap.tscn",
              "godot_surface_type": "control",
              "layout_strategy": "responsive_container",
              "input_paths": ["ui_accept", "ui_cancel"],
              "feedback_states": ["hover", "selected", "disabled"],
              "camera_layer_boundary": "CanvasLayer:ui",
              "viewport_mode": "responsive_control_layout",
              "ui_update_ownership_mode": "registered_control_map",
              "state_boundary": "RouteMapViewState",
              "material_profile": "solid_2d_canvas",
              "rendering_profile": "rendering_not_applicable",
              "animation_profile": "animation_not_applicable",
              "third_person_camera_required": true,
              "camera_controller_profile": "Game.Godot/Scenes/Camera/ThirdPersonCameraRig.tscn"
            }
          ]
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Should().NotContain(issue => issue.IssueId.StartsWith("ui-wiring:route_map:", StringComparison.Ordinal));
    }

    [Fact]
    public void Read_WhenStyleGapRowsContainUnresolvedP1Drift_BlocksFinalReadiness()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [],
          "style_gap_rows": [
            {
              "gap_id": "gap-1",
              "style_drift_family": "palette",
              "requirement_ids": ["REQ-001"],
              "scene_node_path": "res://Scenes/UI/Hud.tscn/HudRoot",
              "expected_style_token_or_rule": "color.primary",
              "observed_drift": "Button uses an ad hoc red.",
              "severity": "P1",
              "affected_viewport_or_component_state": "desktop:hover",
              "visual_evidence_method": "screenshot",
              "follow_up_goal_recommendation": "Repair HUD button token mapping.",
              "status": "open"
            }
          ]
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "ui-wiring:style-gap:gap-1:unresolved_final_readiness_blocker" &&
            issue.Severity == "P1");
    }

    [Fact]
    public void Read_WhenStyleGapFamilyIsUnknown_BlocksClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [],
          "style_gap_rows": [
            {
              "gap_id": "gap-2",
              "style_drift_family": "mutable_heading",
              "requirement_ids": ["REQ-002"],
              "scene_node_path": "res://Scenes/UI/Menu.tscn/Menu",
              "expected_style_token_or_rule": "typography.title",
              "observed_drift": "Unknown taxonomy.",
              "severity": "P2",
              "affected_viewport_or_component_state": "desktop:default",
              "visual_evidence_method": "ui_tree_readback",
              "follow_up_goal_recommendation": "Normalize taxonomy.",
              "status": "open"
            }
          ]
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "ui-wiring:style-gap:gap-2:style_gap_family_unknown");
    }

    [Fact]
    public void Read_WhenStyleRepairPromptInputsAreIncomplete_BlocksClosure()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [],
          "style_repair_prompt_inputs": {
            "frozen_style_snapshot_ref": "meta/routes/ui-style-snapshot/latest.json"
          }
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Select(issue => issue.IssueId).Should().Contain([
            "ui-wiring:style-repair-prompt:missing_runtime_environment_ref",
            "ui-wiring:style-repair-prompt:missing_ui_tree_readback_refs"
        ]);
    }

    [Fact]
    public void Read_WhenFullTargetClosureUsesInterimStatus_BlocksFinalReadiness()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/ui-wiring/latest.json", """
        {
          "schema_version": "ui-wiring-closure.v1",
          "status": "ready",
          "ui_surface_matrix": [],
          "full_target_closure_ledger": [
            {
              "capability_id": "ui_final_readiness_style_gate",
              "status": "not_consumed_by_first_slice"
            }
          ]
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Select(issue => issue.IssueId).Should().Contain([
            "ui-wiring:full-target:ui_final_readiness_style_gate:invalid_final_readiness_status",
            "ui-wiring:full-target:ui_final_readiness_style_gate:interim_status_not_final"
        ]);
    }

    [Fact]
    public void BuildRecommendation_UsesSingleDescriptorCatalogForAllCanonicalActions()
    {
        using var fixture = RouteStateFixture.Create();
        var artifacts = fixture.Service.Read(fixture.Project);
        var recommendation = fixture.Service.BuildRecommendation(
            fixture.Project,
            artifacts,
            new ProjectWorkflowNextAction("create-prototype", "Create", "Create", "Create", "create-prototype", true));

        recommendation.ActionDescriptorRef.DescriptorId.Should().Be(RouteActionDescriptors.DescriptorId);
        recommendation.ActionDescriptorRef.DescriptorVersion.Should().Be(RouteActionDescriptors.DescriptorVersion);
        recommendation.AllowedActions.Concat(recommendation.ForbiddenActions)
            .Select(action => action.ActionId)
            .Should()
            .BeEquivalentTo(RouteActionDescriptors.CanonicalActionIds);
        recommendation.AllowedActions.Concat(recommendation.ForbiddenActions)
            .Should()
            .OnlyContain(action => action.DescriptorHash == recommendation.ActionDescriptorRef.DescriptorHash);
        recommendation.ForbiddenActions
            .Where(action => action.DisabledDomainCode is not null)
            .Should()
            .OnlyContain(action => RouteActionDescriptors.DisabledDomainCodes.Contains(action.DisabledDomainCode!));
    }

    [Fact]
    public void Read_WhenEvidenceRefKindIsOutsideStandardsEnum_Blocks()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteJson("meta/routes/gdd-document/latest.json", """
        {
          "schema_version": "gdd-document-generation.v1",
          "status_dimension": "route_readback",
          "status_allowed_values": ["ready", "blocked"],
          "status": "ready",
          "evidence_refs": [
            { "kind": "raw_prompt", "path": "meta/routes/gdd-document/prompt.txt" }
          ]
        }
        """);

        var readback = fixture.Service.Read(fixture.Project);

        readback.BlockingIssues.Should().Contain(issue =>
            issue.IssueId == "meta/routes/gdd-document/latest.json:evidence_ref_kind_invalid");
    }

    [Fact]
    public void BuildRecommendation_WhenLegacyGddExistsWithoutForm_RecommendsImport()
    {
        using var fixture = RouteStateFixture.Create();
        fixture.WriteText("docs/gdd/GDD.md", "# GDD\n");
        var artifacts = fixture.Service.Read(fixture.Project);

        var recommendation = fixture.Service.BuildRecommendation(
            fixture.Project,
            artifacts,
            new ProjectWorkflowNextAction("create-prototype", "Create", "Create", "Create", "create-prototype", true));

        recommendation.RecommendedAction.Should().Be("import_gdd_form");
        recommendation.ForbiddenActions.Should().Contain(action =>
            action.ActionId == "create_iteration_plan" &&
            action.DisabledDomainCode == "route_contract_not_active");
    }

    private sealed class RouteStateFixture : IDisposable
    {
        private readonly string _root;

        private RouteStateFixture(string root)
        {
            _root = root;
            Project = new ProjectSnapshot(
                "project-1",
                "account-1",
                "Demo",
                "Demo",
                "RPG",
                "default",
                false,
                "[]",
                "succeeded",
                null,
                "workspace-1",
                Path.Combine(root, "workspace"),
                Path.Combine(root, "repo"),
                Path.Combine(root, "runtime"),
                Path.Combine(root, "repo", "meta"));
            Directory.CreateDirectory(Project.RepoPath);
            Directory.CreateDirectory(Project.MetaPath);
            Service = new ProjectRouteStateArtifactService();
        }

        public ProjectSnapshot Project { get; }

        public ProjectRouteStateArtifactService Service { get; }

        public static RouteStateFixture Create()
        {
            var root = Path.Combine(Path.GetTempPath(), "phasea-route-state-artifacts-" + Guid.NewGuid().ToString("N"));
            return new RouteStateFixture(root);
        }

        public void WriteJson(string relativePath, string json)
        {
            WriteText(relativePath, json);
        }

        public void WriteText(string relativePath, string text)
        {
            var path = Path.Combine(Project.RepoPath, relativePath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, text.Replace("\r\n", "\n"));
        }

        public void Dispose()
        {
            if (Directory.Exists(_root))
            {
                Directory.Delete(_root, recursive: true);
            }
        }
    }
}
