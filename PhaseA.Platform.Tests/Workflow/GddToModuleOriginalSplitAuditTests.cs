using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GddToModuleOriginalSplitAuditTests
{
    [Fact]
    public void Registry_ShouldDeclareOriginalLineCountAndInventory()
    {
        GddToModuleOriginalSplitAudit.AuditHash.Should().NotBeNullOrWhiteSpace();
        GddToModuleOriginalSplitAudit.OriginalSourceLineCount.Should().Be(2739);
        GddToModuleOriginalSplitAudit.RequiredInventoryEntries.Should().Contain([
            "00-index.md",
            "schemas/godot-ui-style-contract.v1.example.json",
            "96-global-review-standard.md",
            "97-split-added-requirements-ledger.md",
            "98-original-to-split-audit.md",
            "99-source-coverage.md"
        ]);
    }

    [Fact]
    public void SourceRanges_ShouldBeContiguousAndCovered()
    {
        var rows = GddToModuleOriginalSplitAudit.ParseSourceRanges(
            ReadRepoFile(GddToModuleOriginalSplitAudit.ExecutionPlanAuditPath));

        rows.Should().HaveCount(16);
        rows.First().StartLine.Should().Be(1);
        rows.Last().EndLine.Should().Be(GddToModuleOriginalSplitAudit.OriginalSourceLineCount);
        GddToModuleOriginalSplitAudit.ValidateSourceRanges(rows).Should().BeEmpty();
        rows.Should().Contain(row =>
            row.StartLine == 1378 &&
            row.EndLine == 2178 &&
            row.SplitOutputs.Contains("schemas/godot-ui-style-contract.v1.example.json"));
    }

    [Fact]
    public void SourceRangeValidator_ShouldRejectGapsAndMissingOutputs()
    {
        var rows = new[]
        {
            new SourceRangeCoverageRow(1, 10, ["01-overview-workflow.md"], "Covered"),
            new SourceRangeCoverageRow(12, 20, [], "Missing")
        };

        var issues = GddToModuleOriginalSplitAudit.ValidateSourceRanges(rows);

        issues.Should().Contain(issue => issue.Reason == "source_range_gap_or_overlap");
        issues.Should().Contain(issue => issue.Reason == "source_range_not_covered");
        issues.Should().Contain(issue => issue.Reason == "source_range_missing_split_output");
        issues.Should().Contain(issue => issue.Reason == "source_range_does_not_reach_original_end");
    }

    [Fact]
    public void SplitOutputInventory_ShouldIncludeAllNormativeSplitFiles()
    {
        var inventory = GddToModuleOriginalSplitAudit.ParseSplitOutputInventory(
            ReadRepoFile(GddToModuleOriginalSplitAudit.ExecutionPlanAuditPath));

        inventory.Should().BeEquivalentTo(GddToModuleOriginalSplitAudit.RequiredInventoryEntries);
        GddToModuleOriginalSplitAudit.ValidateInventory(inventory).Should().BeEmpty();
    }

    [Fact]
    public void InventoryValidator_ShouldRejectMissingOrDuplicateEntries()
    {
        var inventory = GddToModuleOriginalSplitAudit.RequiredInventoryEntries
            .Where(entry => entry != "99-source-coverage.md")
            .Concat(["00-index.md"])
            .ToArray();

        var issues = GddToModuleOriginalSplitAudit.ValidateInventory(inventory);

        issues.Should().Contain(issue => issue.Reason == "missing_inventory_entry" && issue.Detail == "99-source-coverage.md");
        issues.Should().Contain(issue => issue.Reason == "duplicate_inventory_entry" && issue.Detail == "00-index.md");
    }

    [Fact]
    public void Audit_ShouldPreserveSourceHistoryBoundary()
    {
        var markdown = ReadRepoFile(GddToModuleOriginalSplitAudit.ExecutionPlanAuditPath);

        GddToModuleOriginalSplitAudit.HasSourceHistoryBoundary(markdown).Should().BeTrue();
        markdown.Should().Contain("Result: no source-line gap or overlap remains");
        markdown.Should().Contain("The split plan covers the original monolithic plan without intentional omissions");
    }

    [Fact]
    public void SchemaExample_ShouldExposeAuditContract()
    {
        using var document = JsonDocument.Parse(ReadRepoFile(GddToModuleOriginalSplitAudit.SchemaExamplePath));
        var root = document.RootElement;

        root.GetProperty("schema_version").GetString().Should().Be("gdd-to-module-original-split-audit.v1");
        root.GetProperty("audit_id").GetString().Should().Be(GddToModuleOriginalSplitAudit.AuditId);
        root.GetProperty("original_source_line_count").GetInt32().Should().Be(GddToModuleOriginalSplitAudit.OriginalSourceLineCount);
        root.GetProperty("execution_plan_audit_path").GetString().Should().Be(GddToModuleOriginalSplitAudit.ExecutionPlanAuditPath);
        root.GetProperty("required_inventory_entries").EnumerateArray().Select(item => item.GetString())
            .Should()
            .BeEquivalentTo(GddToModuleOriginalSplitAudit.RequiredInventoryEntries);
    }

    [Fact]
    public void DurableWorkflowDoc_ShouldLinkAuditAndCoverageMap()
    {
        var doc = ReadRepoFile(GddToModuleOriginalSplitAudit.WorkflowDocPath);

        doc.Should().Contain(GddToModuleOriginalSplitAudit.AuditId);
        doc.Should().Contain(GddToModuleOriginalSplitAudit.ExecutionPlanAuditPath);
        doc.Should().Contain(GddToModuleOriginalSplitAudit.SourceCoveragePath);
        doc.Should().Contain("2739");
        doc.Should().Contain("source history only");
        doc.Should().Contain("no source-line gap or overlap");
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
