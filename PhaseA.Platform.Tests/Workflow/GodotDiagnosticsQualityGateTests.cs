using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GodotDiagnosticsQualityGateTests
{
    [Fact]
    public void Contract_ShouldDeclareStableCapabilityIdsAndBoundedEnums()
    {
        GodotDiagnosticsQualityGate.CapabilityIds.Should().BeEquivalentTo([
            "godot_diagnostic_spool_contract",
            "godot_failure_family_taxonomy",
            "godot_prebuild_preview_quality_gate",
            "godot_interaction_region_gate",
            "godot_resource_lifecycle_gate"
        ]);
        GodotDiagnosticsQualityGate.ContractHash.Should().NotBeNullOrWhiteSpace();
        GodotDiagnosticsQualityGate.SeverityValues.Should().BeEquivalentTo(["P0", "P1", "P2", "info"]);
        GodotDiagnosticsQualityGate.TriageStatuses.Should().BeEquivalentTo(["unresolved", "resolved", "ignored", "backlog"]);
        GodotDiagnosticsQualityGate.RedactionStatuses.Should().BeEquivalentTo(["redacted", "raw_admin_only", "blocked"]);
        GodotDiagnosticsQualityGate.RetentionClasses.Should().Contain(["unresolved_blocker", "resolved_audit", "ignored_audit", "backlog_audit", "info_ephemeral"]);
    }

    [Fact]
    public void FailureFamilyTaxonomy_ShouldCoverAllInitialRowsAndRouteSeeds()
    {
        GodotDiagnosticsQualityGate.FailureFamilies.Should().OnlyHaveUniqueItems();
        GodotDiagnosticsQualityGate.RemediationRows.Select(row => row.FailureFamily)
            .Should()
            .BeEquivalentTo(GodotDiagnosticsQualityGate.FailureFamilies);
        GodotDiagnosticsQualityGate.RemediationRows.Select(row => row.OwnerRoute)
            .Should()
            .OnlyContain(route => GodotDiagnosticsQualityGate.RouteSeeds.Contains(route));
        GodotDiagnosticsQualityGate.RouteSeeds.Should().Contain([
            "scene-route-confirmation",
            "prototype-skeleton",
            "workflow-recommendation",
            "preview-package",
            "project-delete"
        ]);
    }

    [Fact]
    public void SpoolSchemaExample_ShouldUseBoundedTaxonomyAndRequiredFields()
    {
        using var document = JsonDocument.Parse(ReadRepoFile(GodotDiagnosticsQualityGate.SchemaExamplePath));
        var root = document.RootElement;

        root.GetProperty("schema_version").GetString().Should().Be("project-diagnostic-spool.v1");
        foreach (var field in new[] { "diagnostic_id", "account_id", "project_id", "project_name", "route", "failure_family", "severity", "triage_status", "source_refs", "evidence_refs", "redaction_status", "retention_class", "cleanup_status", "user_safe_summary", "admin_summary", "remediation_hint_id" })
        {
            root.TryGetProperty(field, out _).Should().BeTrue($"{field} is required by the spool schema example");
        }

        GodotDiagnosticsQualityGate.IsKnownFailureFamily(root.GetProperty("failure_family").GetString()!).Should().BeTrue();
        GodotDiagnosticsQualityGate.SeverityValues.Should().Contain(root.GetProperty("severity").GetString());
        GodotDiagnosticsQualityGate.TriageStatuses.Should().Contain(root.GetProperty("triage_status").GetString());
        GodotDiagnosticsQualityGate.RedactionStatuses.Should().Contain(root.GetProperty("redaction_status").GetString());
        GodotDiagnosticsQualityGate.RetentionClasses.Should().Contain(root.GetProperty("retention_class").GetString());
    }

    [Fact]
    public void StandardsGuide_ShouldContainEveryFailureFamilyAndCapabilityId()
    {
        var guide = ReadRepoFile(GodotDiagnosticsQualityGate.StandardPath);

        foreach (var capabilityId in GodotDiagnosticsQualityGate.CapabilityIds)
        {
            guide.Should().Contain(capabilityId);
        }

        foreach (var family in GodotDiagnosticsQualityGate.FailureFamilies)
        {
            guide.Should().Contain($"`{family}`");
        }

        guide.Should().Contain("No TapTap local runtime concept");
        guide.Should().Contain("metadata DB diagnostic index");
        guide.Should().Contain("outside hosted workspaces");
    }

    [Fact]
    public void WorkflowContracts_ShouldReferenceDiagnosticRoutesAndCapabilityRows()
    {
        var routeModules = File.ReadAllText(Path.Combine(FindRepoRoot(), "PhaseA.Platform", "Workflow", "RouteModuleContracts.cs"));
        routeModules.Should().Contain("diagnostic spool");
        routeModules.Should().Contain("preview-package");

        var docsIndex = ReadRepoFile("docs/standards/_index.md");
        docsIndex.Should().Contain(GodotDiagnosticsQualityGate.StandardPath);
    }

    private static string ReadRepoFile(string relativePath)
    {
        return File.ReadAllText(Path.Combine(FindRepoRoot(), relativePath.Replace('/', Path.DirectorySeparatorChar)));
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

            directory = Directory.GetParent(directory)?.FullName;
        }

        throw new DirectoryNotFoundException("Repository root not found.");
    }
}
