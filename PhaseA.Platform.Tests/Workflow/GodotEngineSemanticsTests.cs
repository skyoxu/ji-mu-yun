using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GodotEngineSemanticsTests
{
    [Fact]
    public void Fixture_ShouldMatchRuntimeSemanticsRegistry()
    {
        using var document = ReadFixture();
        var root = document.RootElement;

        root.GetProperty("baselineId").GetString().Should().Be(GodotEngineSemantics.BaselineId);
        root.GetProperty("baselineVersion").GetString().Should().Be(GodotEngineSemantics.BaselineVersion);
        root.GetProperty("baselineHash").GetString().Should().Be(GodotEngineSemantics.BaselineHash);
        root.GetProperty("standardPath").GetString().Should().Be(GodotEngineSemantics.StandardPath);
        root.GetProperty("officialExamplesIndexPath").GetString().Should().Be(GodotEngineSemantics.OfficialExamplesIndexPath);
        root.GetProperty("recipesIndexPath").GetString().Should().Be(GodotEngineSemantics.RecipesIndexPath);
        root.GetProperty("missingEvidenceCodes").EnumerateArray().Select(item => item.GetString())
            .Should()
            .BeEquivalentTo(GodotEngineSemantics.MissingEvidenceCodes);
        root.GetProperty("exampleManifestFileNames").EnumerateArray().Select(item => item.GetString())
            .Should()
            .BeEquivalentTo(GodotEngineSemantics.ExampleManifestFileNames);
        root.GetProperty("exampleManifestFields").EnumerateArray().Select(item => item.GetString())
            .Should()
            .BeEquivalentTo(GodotEngineSemantics.ExampleManifestFields);

        AssertSemanticFamilies(root);
        AssertViewportModes(root);
        AssertFeatureFamilyGates(root);
        AssertRouteRequirements(root);
    }

    [Fact]
    public void Registry_ShouldCoverMinimumGodotSemanticFamiliesAndViewportModes()
    {
        GodotEngineSemantics.SemanticFamilies.Select(family => family.FamilyId).Should().Contain([
            "unit_scale",
            "coordinate_spaces",
            "viewport_resolution",
            "input_constants",
            "physics_collision",
            "camera_projection",
            "third_person_camera",
            "tilemap_map",
            "geometry_size_measurement",
            "rendering_material_resources"
        ]);

        GodotEngineSemantics.ViewportModes.Select(mode => mode.ModeId).Should().Contain([
            "fixed_design_resolution",
            "responsive_control_layout",
            "camera_world_scaled_view",
            "tilemap_grid_scaled_view",
            "viewport_custom_drawing"
        ]);

        GodotEngineSemantics.MissingEvidenceCodes.Should().Contain([
            "reference_example_missing",
            "godot_recipe_missing",
            "reference_example_manifest_missing"
        ]);
    }

    [Fact]
    public void FeatureFamilyGates_ShouldReferenceKnownSemanticFamiliesAndBlockingCodes()
    {
        foreach (var gate in GodotEngineSemantics.FeatureFamilyGates)
        {
            gate.SemanticFamilyIds.Should().NotBeEmpty($"{gate.FeatureFamilyId} must declare Godot semantic context");
            gate.SemanticFamilyIds.Should().OnlyContain(familyId => GodotEngineSemantics.IsKnownSemanticFamily(familyId));
            gate.RequiredStandardRefs.Should().Contain(GodotEngineSemantics.StandardPath);
            gate.ReferenceExampleFamilies.Should().NotBeEmpty();
        }

        foreach (var routeRequirement in GodotEngineSemantics.RouteRequirements)
        {
            RouteModuleContracts.Find(routeRequirement.RouteId).Should().NotBeNull($"{routeRequirement.RouteId} must be a route contract");
            routeRequirement.FeatureFamilyIds.Should().OnlyContain(featureFamilyId => GodotEngineSemantics.IsKnownFeatureFamily(featureFamilyId));
            routeRequirement.RequiredEvidenceFields.Should().NotBeEmpty();
            routeRequirement.MissingEvidenceCodes.Should().OnlyContain(code => GodotEngineSemantics.IsKnownMissingEvidenceCode(code));
        }
    }

    [Fact]
    public void GodotExecutableRoutes_ShouldHaveSemanticRequirements()
    {
        var requiredRoutes = new[]
        {
            "prototype-skeleton",
            "iteration-plan",
            "execute-next-goal",
            "needs-fix",
            "repair",
            "ui-wiring-closure"
        };

        GodotEngineSemantics.RouteRequirements.Select(requirement => requirement.RouteId)
            .Should()
            .Contain(requiredRoutes);

        foreach (var routeId in requiredRoutes)
        {
            var requirement = GodotEngineSemantics.RouteRequirements.Single(item => item.RouteId == routeId);
            requirement.FeatureFamilyIds.Should().NotBeEmpty();
            requirement.MissingEvidenceCodes.Should().Contain("reference_example_missing");
        }
    }

    [Fact]
    public void ExampleCopyManifestPolicy_ShouldPreserveNonCodeAssetsAndLicenseEvidence()
    {
        GodotEngineSemantics.ExampleManifestFileNames.Should().ContainInOrder("godot-example-manifest.json", "manifest.json");
        GodotEngineSemantics.ExampleManifestFields.Should().Contain([
            "includes",
            "excludes",
            "copyAll",
            "targetDir",
            "preservePaths",
            "licenseRefs",
            "requiredInputActions",
            "requiredProjectSettings",
            "assetImportPolicy"
        ]);
    }

    private static void AssertSemanticFamilies(JsonElement root)
    {
        var fixtureFamilies = root.GetProperty("semanticFamilies").EnumerateArray().ToArray();
        fixtureFamilies.Select(item => item.GetProperty("familyId").GetString())
            .Should()
            .BeEquivalentTo(GodotEngineSemantics.SemanticFamilies.Select(item => item.FamilyId));

        foreach (var runtime in GodotEngineSemantics.SemanticFamilies)
        {
            var fixture = fixtureFamilies.Single(item => item.GetProperty("familyId").GetString() == runtime.FamilyId);
            fixture.GetProperty("displayName").GetString().Should().Be(runtime.DisplayName);
            fixture.GetProperty("scope").GetString().Should().Be(runtime.Scope);
            fixture.GetProperty("requiredDeclarations").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.RequiredDeclarations);
            fixture.GetProperty("blockingExamples").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.BlockingExamples);
        }
    }

    private static void AssertViewportModes(JsonElement root)
    {
        var fixtureModes = root.GetProperty("viewportModes").EnumerateArray().ToArray();
        fixtureModes.Select(item => item.GetProperty("modeId").GetString())
            .Should()
            .BeEquivalentTo(GodotEngineSemantics.ViewportModes.Select(item => item.ModeId));

        foreach (var runtime in GodotEngineSemantics.ViewportModes)
        {
            var fixture = fixtureModes.Single(item => item.GetProperty("modeId").GetString() == runtime.ModeId);
            fixture.GetProperty("displayName").GetString().Should().Be(runtime.DisplayName);
            fixture.GetProperty("useWhen").GetString().Should().Be(runtime.UseWhen);
            fixture.GetProperty("requiredEvidence").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.RequiredEvidence);
        }
    }

    private static void AssertFeatureFamilyGates(JsonElement root)
    {
        var fixtureGates = root.GetProperty("featureFamilyGates").EnumerateArray().ToArray();
        fixtureGates.Select(item => item.GetProperty("featureFamilyId").GetString())
            .Should()
            .BeEquivalentTo(GodotEngineSemantics.FeatureFamilyGates.Select(item => item.FeatureFamilyId));

        foreach (var runtime in GodotEngineSemantics.FeatureFamilyGates)
        {
            var fixture = fixtureGates.Single(item => item.GetProperty("featureFamilyId").GetString() == runtime.FeatureFamilyId);
            fixture.GetProperty("displayName").GetString().Should().Be(runtime.DisplayName);
            fixture.GetProperty("semanticFamilyIds").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.SemanticFamilyIds);
            fixture.GetProperty("requiredStandardRefs").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.RequiredStandardRefs);
            fixture.GetProperty("referenceExampleFamilies").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.ReferenceExampleFamilies);
            fixture.GetProperty("blocksWithoutReadingEvidence").GetBoolean().Should().Be(runtime.BlocksWithoutReadingEvidence);
        }
    }

    private static void AssertRouteRequirements(JsonElement root)
    {
        var fixtureRequirements = root.GetProperty("routeRequirements").EnumerateArray().ToArray();
        fixtureRequirements.Select(item => item.GetProperty("routeId").GetString())
            .Should()
            .BeEquivalentTo(GodotEngineSemantics.RouteRequirements.Select(item => item.RouteId));

        foreach (var runtime in GodotEngineSemantics.RouteRequirements)
        {
            var fixture = fixtureRequirements.Single(item => item.GetProperty("routeId").GetString() == runtime.RouteId);
            fixture.GetProperty("featureFamilyIds").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.FeatureFamilyIds);
            fixture.GetProperty("requiredEvidenceFields").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.RequiredEvidenceFields);
            fixture.GetProperty("missingEvidenceCodes").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.MissingEvidenceCodes);
        }
    }

    private static JsonDocument ReadFixture()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "Fixtures", "godot-engine-semantics.v1.json");
        return JsonDocument.Parse(File.ReadAllText(path));
    }
}
