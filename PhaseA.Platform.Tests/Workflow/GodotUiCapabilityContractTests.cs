using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GodotUiCapabilityContractTests
{
    [Fact]
    public void Fixture_ShouldMatchRuntimeContractRegistry()
    {
        using var document = ReadFixture();
        var root = document.RootElement;

        root.GetProperty("contractId").GetString().Should().Be(GodotUiCapabilityContract.ContractId);
        root.GetProperty("contractVersion").GetString().Should().Be(GodotUiCapabilityContract.ContractVersion);
        root.GetProperty("contractHash").GetString().Should().Be(GodotUiCapabilityContract.ContractHash);
        root.GetProperty("standardPath").GetString().Should().Be(GodotUiCapabilityContract.StandardPath);
        root.GetProperty("forbiddenTechnologyTerms").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(GodotUiCapabilityContract.ForbiddenTechnologyTerms);
        root.GetProperty("capabilityStatuses").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(GodotUiCapabilityContract.CapabilityStatuses);
        root.GetProperty("blockingDiagnosticCodes").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(GodotUiCapabilityContract.BlockingDiagnosticCodes);
        root.GetProperty("materialProfiles").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(GodotUiCapabilityContract.MaterialProfiles);
        root.GetProperty("renderingProfiles").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(GodotUiCapabilityContract.RenderingProfiles);
        root.GetProperty("animationProfiles").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(GodotUiCapabilityContract.AnimationProfiles);
        root.GetProperty("uiUpdateOwnershipModes").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(GodotUiCapabilityContract.UiUpdateOwnershipModes);

        AssertCapabilityDomains(root);
        AssertInjectionPoints(root);
        AssertGovernanceRules(root);
    }

    [Fact]
    public void CapabilityDomains_ShouldCoverFullMigrationChecklistAndGodotSemantics()
    {
        GodotUiCapabilityContract.CapabilityDomains.Select(domain => domain.DomainId).Should().Contain([
            "ui_scene_architecture",
            "layout_theme_responsive",
            "hud_menus_overlays",
            "custom_2d_drawing",
            "input_focus_navigation",
            "camera_viewport_world_physics",
            "rendering_materials_shaders",
            "animation_state_machines",
            "procedural_generation",
            "geometry_mesh_size",
            "typed_state_schema",
            "accessibility_readability_feedback"
        ]);

        foreach (var domain in GodotUiCapabilityContract.CapabilityDomains)
        {
            domain.GodotOwnership.Should().NotBeEmpty();
            domain.RequiredWorkflowFields.Should().NotBeEmpty();
            domain.SemanticFamilyIds.Should().OnlyContain(familyId => GodotEngineSemantics.IsKnownSemanticFamily(familyId));
        }
    }

    [Fact]
    public void Profiles_ShouldCoverMaterialRenderingAnimationUpdateAndCameraGates()
    {
        GodotUiCapabilityContract.MaterialProfiles.Should().Contain([
            "solid_3d_standard",
            "transparent_3d_standard",
            "solid_2d_canvas",
            "canvas_item_material",
            "shader_material",
            "existing_material_resource"
        ]);
        GodotUiCapabilityContract.RenderingProfiles.Should().Contain("rendering_not_applicable");
        GodotUiCapabilityContract.AnimationProfiles.Should().Contain("animation_not_applicable");
        GodotUiCapabilityContract.UiUpdateOwnershipModes.Should().Contain([
            "retained_typed_references",
            "registered_control_map",
            "state_apply_pass",
            "dynamic_item_factory",
            "no_dynamic_update"
        ]);
        GodotUiCapabilityContract.BlockingDiagnosticCodes.Should().Contain([
            "material_profile_missing",
            "rendering_profile_missing",
            "animation_state_profile_missing",
            "third_person_camera_profile_missing",
            "ui_update_ownership_missing"
        ]);
    }

    [Fact]
    public void InjectionPoints_ShouldCoverGddToModuleWorkflowRoutes()
    {
        GodotUiCapabilityContract.InjectionPoints.Select(point => point.RouteId).Should().Contain([
            "gdd-question-form",
            "scene-route-confirmation",
            "gdd-document-generation",
            "gdd-requirements",
            "prototype-contract",
            "iteration-plan",
            "execute-next-goal",
            "needs-fix",
            "repair",
            "ui-wiring-closure",
            "preview-package"
        ]);

        foreach (var point in GodotUiCapabilityContract.InjectionPoints)
        {
            point.RequiredFields.Should().NotBeEmpty();
        }
    }

    [Fact]
    public void ForbiddenTechnologyTerms_ShouldRemainMigrationRationaleOnly()
    {
        GodotUiCapabilityContract.ForbiddenTechnologyTerms.Should().Contain([
            "UrhoX",
            "Urho3D",
            "Lua",
            "NanoVG",
            "PBRNoTexture",
            ".emmylua"
        ]);
    }

    private static void AssertCapabilityDomains(JsonElement root)
    {
        var fixtureDomains = root.GetProperty("capabilityDomains").EnumerateArray().ToArray();
        fixtureDomains.Select(item => item.GetProperty("domainId").GetString())
            .Should()
            .BeEquivalentTo(GodotUiCapabilityContract.CapabilityDomains.Select(item => item.DomainId));

        foreach (var runtime in GodotUiCapabilityContract.CapabilityDomains)
        {
            var fixture = fixtureDomains.Single(item => item.GetProperty("domainId").GetString() == runtime.DomainId);
            fixture.GetProperty("displayName").GetString().Should().Be(runtime.DisplayName);
            fixture.GetProperty("godotOwnership").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.GodotOwnership);
            fixture.GetProperty("requiredWorkflowFields").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.RequiredWorkflowFields);
            fixture.GetProperty("semanticFamilyIds").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.SemanticFamilyIds);
        }
    }

    private static void AssertInjectionPoints(JsonElement root)
    {
        var fixturePoints = root.GetProperty("injectionPoints").EnumerateArray().ToArray();
        fixturePoints.Select(item => item.GetProperty("routeId").GetString())
            .Should()
            .BeEquivalentTo(GodotUiCapabilityContract.InjectionPoints.Select(item => item.RouteId));

        foreach (var runtime in GodotUiCapabilityContract.InjectionPoints)
        {
            var fixture = fixturePoints.Single(item => item.GetProperty("routeId").GetString() == runtime.RouteId);
            fixture.GetProperty("summary").GetString().Should().Be(runtime.Summary);
            fixture.GetProperty("requiredFields").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.RequiredFields);
        }
    }

    private static void AssertGovernanceRules(JsonElement root)
    {
        var fixtureRules = root.GetProperty("governanceRules").EnumerateArray().ToArray();
        fixtureRules.Select(item => item.GetProperty("ruleId").GetString())
            .Should()
            .BeEquivalentTo(GodotUiCapabilityContract.GovernanceRules.Select(item => item.RuleId));

        foreach (var runtime in GodotUiCapabilityContract.GovernanceRules)
        {
            var fixture = fixtureRules.Single(item => item.GetProperty("ruleId").GetString() == runtime.RuleId);
            fixture.GetProperty("summary").GetString().Should().Be(runtime.Summary);
            fixture.GetProperty("blocksP0P1").GetBoolean().Should().Be(runtime.BlocksP0P1);
        }
    }

    private static JsonDocument ReadFixture()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "Fixtures", "godot-ui-capability-contract.v1.json");
        return JsonDocument.Parse(File.ReadAllText(path));
    }
}
