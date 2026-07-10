using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GodotUiStyleSnapshotSchemaTests
{
    [Fact]
    public void Fixture_ShouldExposeRequiredTopLevelSchemaProfileFields()
    {
        using var document = ReadFixture();
        var root = document.RootElement;

        root.GetProperty("schema_version").GetString().Should().Be(GodotUiStyleSnapshotSchema.SchemaVersionValue);
        foreach (var field in GodotUiStyleSnapshotSchema.RequiredTopLevelFields)
        {
            root.TryGetProperty(field, out _).Should().BeTrue($"{field} is required by the style snapshot schema profile");
        }
    }

    [Fact]
    public void SchemaProfile_ShouldDeclareBoundedEnumsAndHashIdentityFields()
    {
        GodotUiStyleSnapshotSchema.SchemaProfileHash.Should().NotBeNullOrWhiteSpace();
        GodotUiStyleSnapshotSchema.AllowedStyleIds.Should().Contain(["godot_cosmic", "godot_combat_hud", "godot_pixel_arcade", "custom"]);
        GodotUiStyleSnapshotSchema.AllowedSelectedBy.Should().Contain(["user", "workflow", "admin", "fallback"]);
        GodotUiStyleSnapshotSchema.AllowedRendererValues.Should().Contain(["forward_plus", "mobile", "compatibility", "unknown"]);
        GodotUiStyleSnapshotSchema.AllowedEvidenceTypes.Should().Contain(["screenshot", "canvas_pixel", "exported_visual", "ui_tree_readback", "deterministic_substitute"]);
        GodotUiStyleSnapshotSchema.HashIdentityFields.Should().Contain(["runtime_environment", "palette_tokens", "component_coverage_matrix", "godot_theme_resources"]);
    }

    [Fact]
    public void Fixture_ShouldIncludePhase0CapabilityPackageIds()
    {
        using var document = ReadFixture();
        var packages = document.RootElement.GetProperty("capability_packages").EnumerateArray().ToArray();
        packages.Select(item => item.GetProperty("capability_id").GetString())
            .Should()
            .Contain(GodotUiStyleSnapshotSchema.Phase0CapabilityIds);

        foreach (var package in packages)
        {
            var capabilityId = package.GetProperty("capability_id").GetString();
            package.GetProperty("owner_doc").GetString().Should().NotBeNullOrWhiteSpace();
            package.GetProperty("coverage_status").GetString().Should().NotBeNullOrWhiteSpace($"{capabilityId} must declare bounded coverage status");
            package.TryGetProperty("validation_refs", out var refs).Should().BeTrue();
            refs.ValueKind.Should().Be(JsonValueKind.Array);
        }
    }

    [Fact]
    public void Fixture_ShouldDistinguishRequiredActiveArraysFromOptionalEmptyArrays()
    {
        using var document = ReadFixture();
        var root = document.RootElement;

        foreach (var field in GodotUiStyleSnapshotSchema.RequiredActiveArrayFields)
        {
            root.TryGetProperty(field, out var value).Should().BeTrue();
            value.ValueKind.Should().Be(JsonValueKind.Array);
            value.GetArrayLength().Should().BeGreaterThan(0, $"{field} must not be absent or empty in the schema profile fixture");
        }

        foreach (var field in GodotUiStyleSnapshotSchema.OptionalEmptyArrayFields)
        {
            root.TryGetProperty(field, out var value).Should().BeTrue();
            value.ValueKind.Should().Be(JsonValueKind.Array);
        }
    }

    [Fact]
    public void RuntimeEnvironment_ShouldParticipateInHashIdentity()
    {
        using var document = ReadFixture();
        var runtime = document.RootElement.GetProperty("runtime_environment");

        runtime.GetProperty("participates_in_hash_identity").GetBoolean().Should().BeTrue();
        runtime.GetProperty("renderer").GetString().Should().NotBeNullOrWhiteSpace();
        runtime.GetProperty("export_target").GetString().Should().NotBeNullOrWhiteSpace();
        runtime.GetProperty("text_direction_policy").GetString().Should().NotBeNullOrWhiteSpace();
        GodotUiStyleSnapshotSchema.HashIdentityFields.Should().Contain("runtime_environment");
    }

    [Fact]
    public void DurableFixture_ShouldMatchExecutionPlanFixture()
    {
        var durable = ReadRepoFile(GodotUiStyleSnapshotSchema.DurableFixturePath);
        var source = ReadRepoFile(GodotUiStyleSnapshotSchema.SourcePlanFixturePath);

        durable.Should().Be(source);
    }

    [Fact]
    public void CapabilityPackages_ShouldMatchDeclaredAcceptanceInventory()
    {
        using var document = ReadFixture();
        var capabilityIds = document.RootElement.GetProperty("capability_packages")
            .EnumerateArray()
            .Select(item => item.GetProperty("capability_id").GetString() ?? "")
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .ToArray();

        capabilityIds.Should().OnlyHaveUniqueItems();
        capabilityIds.Should().Contain(GodotUiStyleSnapshotSchema.AcceptanceCapabilityIds);
        capabilityIds.Should().OnlyContain(id => GodotUiStyleSnapshotSchema.AcceptanceCapabilityIds.Contains(id));
    }

    [Fact]
    public void CustomStyleAndPublicAliasMetadata_ShouldDeclareRequiredFields()
    {
        using var document = ReadFixture();
        var root = document.RootElement;
        var custom = root.GetProperty("custom_style_metadata");
        foreach (var field in GodotUiStyleSnapshotSchema.CustomStyleRequiredFields)
        {
            custom.TryGetProperty(field, out _).Should().BeTrue($"{field} is required for custom style equivalence");
        }

        var alias = root.GetProperty("source_name_policy")
            .GetProperty("public_alias_approval_refs")
            .EnumerateArray()
            .First();
        foreach (var field in GodotUiStyleSnapshotSchema.PublicAliasApprovalRequiredFields)
        {
            alias.TryGetProperty(field, out _).Should().BeTrue($"{field} is required for public alias approval records");
        }
    }

    [Fact]
    public void ThemeResources_ShouldDeclareResolutionValidationAndSafeReadbackFields()
    {
        using var document = ReadFixture();
        var resource = document.RootElement.GetProperty("godot_theme_resources").EnumerateArray().First();

        foreach (var field in GodotUiStyleSnapshotSchema.ThemeResourceRequiredFields)
        {
            resource.TryGetProperty(field, out _).Should().BeTrue($"{field} is required for theme resource acceptance");
        }

        resource.GetProperty("theme_slot_mappings").EnumerateArray().First()
            .TryGetProperty("godot_target", out _)
            .Should()
            .BeTrue();
    }

    [Fact]
    public void VisualEvidenceSubstitutes_ShouldDeclareApprovalExpiryAndCannotSubstituteFor()
    {
        using var document = ReadFixture();
        var visualEvidence = document.RootElement.GetProperty("visual_evidence_matrix").EnumerateArray().First();
        var limitation = visualEvidence.GetProperty("harness_limitation");

        foreach (var field in GodotUiStyleSnapshotSchema.DeterministicSubstituteRequiredFields)
        {
            limitation.TryGetProperty(field, out _).Should().BeTrue($"{field} is required for deterministic substitute acceptance");
        }
    }

    [Fact]
    public void HashIdentity_ShouldDocumentVolatileExclusions()
    {
        GodotUiStyleSnapshotSchema.HashIdentityFields.Should().NotContain("ui_style_snapshot_hash");
        GodotUiStyleSnapshotSchema.DocumentedVolatileHashExclusions.Should().Contain([
            "ui_style_snapshot_hash",
            "selected_by",
            "selection_reason"
        ]);
    }

    private static JsonDocument ReadFixture()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "Fixtures", "godot-ui-style-contract.v1.example.json");
        return JsonDocument.Parse(File.ReadAllText(path));
    }

    private static string ReadRepoFile(string relativePath)
    {
        var root = FindRepoRoot();
        return File.ReadAllText(Path.Combine(root, relativePath.Replace('/', Path.DirectorySeparatorChar)));
    }

    private static string FindRepoRoot()
    {
        var directory = AppContext.BaseDirectory;
        while (!string.IsNullOrWhiteSpace(directory))
        {
            if (File.Exists(Path.Combine(directory, "AGENTS.md")) &&
                Directory.Exists(Path.Combine(directory, "PhaseA.Platform")))
            {
                return directory;
            }

            var parent = Directory.GetParent(directory);
            if (parent is null)
            {
                break;
            }

            directory = parent.FullName;
        }

        throw new DirectoryNotFoundException("Repository root not found.");
    }
}
