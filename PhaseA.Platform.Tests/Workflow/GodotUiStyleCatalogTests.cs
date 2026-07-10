using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GodotUiStyleCatalogTests
{
    [Fact]
    public void Fixture_ShouldMatchRuntimeStyleCatalog()
    {
        using var document = ReadFixture();
        var root = document.RootElement;

        root.GetProperty("catalogId").GetString().Should().Be(GodotUiStyleCatalog.CatalogId);
        root.GetProperty("catalogVersion").GetString().Should().Be(GodotUiStyleCatalog.CatalogVersion);
        root.GetProperty("catalogHash").GetString().Should().Be(GodotUiStyleCatalog.CatalogHash);
        root.GetProperty("standardPath").GetString().Should().Be(GodotUiStyleCatalog.StandardPath);
        root.GetProperty("styleGuideRoot").GetString().Should().Be(GodotUiStyleCatalog.StyleGuideRoot);
        root.GetProperty("forbiddenTechnologyTerms").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(GodotUiStyleCatalog.ForbiddenTechnologyTerms);
        root.GetProperty("styleDriftFamilies").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(GodotUiStyleCatalog.StyleDriftFamilies);
        root.GetProperty("coverageStatuses").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(GodotUiStyleCatalog.CoverageStatuses);
        AssertStyles(root);
        AssertComponentTiers(root);
        AssertCapabilities(root);
    }

    [Fact]
    public void BuiltInStyles_ShouldUseRepoOwnedInternalIds()
    {
        GodotUiStyleCatalog.Styles.Select(style => style.StyleId).Should().BeEquivalentTo([
            "godot_cosmic",
            "godot_combat_hud",
            "godot_pixel_arcade"
        ]);

        foreach (var style in GodotUiStyleCatalog.Styles)
        {
            style.StyleId.Should().StartWith("godot_");
            style.GuidePath.Should().StartWith("docs/ui-style-guides/");
            style.TriggerTags.Should().NotBeEmpty();
            style.DesignDna.Should().NotBeEmpty();
            style.GodotControls.Should().NotContain(control => control.Contains("Urho", StringComparison.OrdinalIgnoreCase));
        }
    }

    [Fact]
    public void ComponentTiers_ShouldCoverCoreGameConditionalAndSecurityGatedFamilies()
    {
        GodotUiStyleCatalog.ComponentTiers.Select(tier => tier.TierId).Should().Contain([
            "core_minimum",
            "game_minimum",
            "conditional_builtin",
            "admin_tooling_or_security_gated"
        ]);

        var core = GodotUiStyleCatalog.ComponentTiers.Single(tier => tier.TierId == "core_minimum");
        core.DefaultCoverageStatus.Should().Be("required");
        core.ComponentFamilies.Should().Contain(["button", "panel_card", "modal", "scroll_view", "list_view"]);

        var security = GodotUiStyleCatalog.ComponentTiers.Single(tier => tier.TierId == "admin_tooling_or_security_gated");
        security.ComponentFamilies.Should().Contain("file_upload");
        security.DefaultCoverageStatus.Should().Be("admin_tooling_or_security_gated");
    }

    [Fact]
    public void DriftFamilies_ShouldCoverNormalizedStyleAcceptanceTaxonomy()
    {
        GodotUiStyleCatalog.StyleDriftFamilies.Should().Contain([
            "design_dna",
            "palette",
            "typography",
            "component_defaults",
            "component_coverage",
            "semantic_usage",
            "action_role",
            "font_policy",
            "pointer_gesture",
            "drag_drop_payload",
            "ui_lifecycle",
            "scroll_virtualization",
            "source_name_ownership",
            "file_upload_security",
            "visual_evidence_method"
        ]);
    }

    [Fact]
    public void CoverageStatuses_ShouldUseBoundedRouteStatusVocabulary()
    {
        GodotUiStyleCatalog.CoverageStatuses.Should().BeEquivalentTo(RouteStatusVocabulary.Values(RouteStatusVocabulary.StyleCapabilityCoverage));
    }

    private static void AssertStyles(JsonElement root)
    {
        var fixtureStyles = root.GetProperty("styles").EnumerateArray().ToArray();
        fixtureStyles.Select(item => item.GetProperty("styleId").GetString()).Should().BeEquivalentTo(GodotUiStyleCatalog.Styles.Select(item => item.StyleId));
        foreach (var runtime in GodotUiStyleCatalog.Styles)
        {
            var fixture = fixtureStyles.Single(item => item.GetProperty("styleId").GetString() == runtime.StyleId);
            fixture.GetProperty("displayName").GetString().Should().Be(runtime.DisplayName);
            fixture.GetProperty("version").GetString().Should().Be(runtime.Version);
            fixture.GetProperty("guidePath").GetString().Should().Be(runtime.GuidePath);
            fixture.GetProperty("triggerTags").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.TriggerTags);
            fixture.GetProperty("designDna").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.DesignDna);
            fixture.GetProperty("godotControls").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.GodotControls);
            fixture.GetProperty("gameCompositionTemplates").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.GameCompositionTemplates);
        }
    }

    private static void AssertComponentTiers(JsonElement root)
    {
        var fixtureTiers = root.GetProperty("componentTiers").EnumerateArray().ToArray();
        fixtureTiers.Select(item => item.GetProperty("tierId").GetString()).Should().BeEquivalentTo(GodotUiStyleCatalog.ComponentTiers.Select(item => item.TierId));
        foreach (var runtime in GodotUiStyleCatalog.ComponentTiers)
        {
            var fixture = fixtureTiers.Single(item => item.GetProperty("tierId").GetString() == runtime.TierId);
            fixture.GetProperty("componentFamilies").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.ComponentFamilies);
            fixture.GetProperty("defaultCoverageStatus").GetString().Should().Be(runtime.DefaultCoverageStatus);
        }
    }

    private static void AssertCapabilities(JsonElement root)
    {
        var fixtureCapabilities = root.GetProperty("capabilities").EnumerateArray().ToArray();
        fixtureCapabilities.Select(item => item.GetProperty("capabilityId").GetString()).Should().BeEquivalentTo(GodotUiStyleCatalog.Capabilities.Select(item => item.CapabilityId));
        foreach (var runtime in GodotUiStyleCatalog.Capabilities)
        {
            var fixture = fixtureCapabilities.Single(item => item.GetProperty("capabilityId").GetString() == runtime.CapabilityId);
            fixture.GetProperty("godotTranslation").GetString().Should().Be(runtime.GodotTranslation);
        }
    }

    private static JsonDocument ReadFixture()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "Fixtures", "godot-ui-style-catalog.v1.json");
        return JsonDocument.Parse(File.ReadAllText(path));
    }
}
