using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GddToModuleSourceCoverageMapTests
{
    [Fact]
    public void CoverageMap_ShouldDeclareOriginalLineCountAndSplitAddedBoundaryRefs()
    {
        GddToModuleSourceCoverageMap.CoverageHash.Should().NotBeNullOrWhiteSpace();
        GddToModuleSourceCoverageMap.OriginalSourceLineCount.Should().Be(2739);
        GddToModuleSourceCoverageMap.RequiredSplitAddedBoundaryRefs.Should().BeEquivalentTo([
            "97-split-added-requirements-ledger.md",
            "04d-godot-engine-semantics-and-reference-examples.md"
        ]);
        GddToModuleSourceCoverageMap.AllowedSplitAddedSourceRefs.Should().BeEquivalentTo([
            "schemas/gdd-to-module-capability-inventory.v1.json",
            "schemas/split-added-acceptance-registry.v1.json"
        ]);
    }

    [Fact]
    public void CoverageRows_ShouldBeContiguousAndReachOriginalEnd()
    {
        var rows = CoverageRows();

        rows.Should().HaveCount(16);
        rows.First().StartLine.Should().Be(1);
        rows.Last().EndLine.Should().Be(GddToModuleSourceCoverageMap.OriginalSourceLineCount);
        GddToModuleSourceCoverageMap.ValidateCoverageRows(rows).Should().BeEmpty();
    }

    [Fact]
    public void CoverageMap_ShouldMatchOriginalSplitAuditRanges()
    {
        var coverageRows = CoverageRows();
        var auditRows = GddToModuleOriginalSplitAudit.ParseSourceRanges(
            ReadRepoFile(GddToModuleOriginalSplitAudit.ExecutionPlanAuditPath));

        GddToModuleSourceCoverageMap.MatchesOriginalSplitAudit(coverageRows, auditRows).Should().BeTrue();
        coverageRows.Should().Contain(row =>
            row.StartLine == 1378 &&
            row.EndLine == 2178 &&
            row.SplitDocuments.Contains("schemas/godot-ui-style-contract.v1.example.json"));
    }

    [Fact]
    public void CoverageMap_ShouldRejectUndeclaredAdditionalSourceRefs()
    {
        var coverageRows = new[]
        {
            new SourceCoverageMapRow(1, 10, ["01-overview-workflow.md", "schemas/unknown.json"], "Covered")
        };
        var auditRows = new[]
        {
            new SourceRangeCoverageRow(1, 10, ["01-overview-workflow.md"], "Covered")
        };

        GddToModuleSourceCoverageMap.MatchesOriginalSplitAudit(coverageRows, auditRows).Should().BeFalse();
    }

    [Fact]
    public void CoverageMap_ShouldRejectDuplicateOrMisplacedSplitAddedRefs()
    {
        var duplicateCoverage = new[]
        {
            new SourceCoverageMapRow(1378, 2178, ["06b-ui-style-snapshot-schema.md", "06b-ui-style-snapshot-schema.md"], "Covered")
        };
        var misplacedCoverage = new[]
        {
            new SourceCoverageMapRow(1, 99, ["01-overview-workflow.md", "schemas/gdd-to-module-capability-inventory.v1.json"], "Covered")
        };

        GddToModuleSourceCoverageMap.MatchesOriginalSplitAudit(
            duplicateCoverage,
            [new SourceRangeCoverageRow(1378, 2178, ["06b-ui-style-snapshot-schema.md"], "Covered")]).Should().BeFalse();
        GddToModuleSourceCoverageMap.MatchesOriginalSplitAudit(
            misplacedCoverage,
            [new SourceRangeCoverageRow(1, 99, ["01-overview-workflow.md"], "Covered")]).Should().BeFalse();
    }

    [Fact]
    public void CoverageMap_ShouldStateAssertionAndSplitAddedBoundary()
    {
        var markdown = ReadRepoFile(GddToModuleSourceCoverageMap.ExecutionPlanCoveragePath);

        GddToModuleSourceCoverageMap.HasCoverageAssertion(markdown).Should().BeTrue();
        GddToModuleSourceCoverageMap.HasSplitAddedBoundary(markdown).Should().BeTrue();
    }

    [Fact]
    public void SchemaExample_ShouldExposeCoverageContract()
    {
        using var document = JsonDocument.Parse(ReadRepoFile(GddToModuleSourceCoverageMap.SchemaExamplePath));
        var root = document.RootElement;

        root.GetProperty("schema_version").GetString().Should().Be("gdd-to-module-source-coverage-map.v1");
        root.GetProperty("coverage_map_id").GetString().Should().Be(GddToModuleSourceCoverageMap.CoverageMapId);
        root.GetProperty("execution_plan_coverage_path").GetString().Should().Be(GddToModuleSourceCoverageMap.ExecutionPlanCoveragePath);
        root.GetProperty("original_source_line_count").GetInt32().Should().Be(GddToModuleSourceCoverageMap.OriginalSourceLineCount);
        root.GetProperty("split_added_boundary_refs").EnumerateArray().Select(item => item.GetString())
            .Should()
            .BeEquivalentTo(GddToModuleSourceCoverageMap.RequiredSplitAddedBoundaryRefs);
        root.GetProperty("allowed_split_added_source_refs").EnumerateArray().Select(item => item.GetString())
            .Should()
            .BeEquivalentTo(GddToModuleSourceCoverageMap.AllowedSplitAddedSourceRefs);
    }

    [Fact]
    public void DurableWorkflowDoc_ShouldLinkCoverageMapAndAudit()
    {
        var doc = ReadRepoFile(GddToModuleSourceCoverageMap.WorkflowDocPath);

        doc.Should().Contain(GddToModuleSourceCoverageMap.CoverageMapId);
        doc.Should().Contain(GddToModuleSourceCoverageMap.ExecutionPlanCoveragePath);
        doc.Should().Contain(GddToModuleOriginalSplitAudit.ExecutionPlanAuditPath);
        doc.Should().Contain("1-2739");
        doc.Should().Contain("split-added");
    }

    private static IReadOnlyList<SourceCoverageMapRow> CoverageRows()
    {
        return GddToModuleSourceCoverageMap.ParseCoverageRows(
            ReadRepoFile(GddToModuleSourceCoverageMap.ExecutionPlanCoveragePath));
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
