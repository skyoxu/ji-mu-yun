using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GddToModuleSplitAddedRequirementsTests
{
    [Fact]
    public void Registry_ShouldDeclareLedgerColumnsAndCoverageStatuses()
    {
        GddToModuleSplitAddedRequirements.LedgerHash.Should().NotBeNullOrWhiteSpace();
        GddToModuleSplitAddedRequirements.LedgerColumns.Should().BeEquivalentTo([
            "split_added_id",
            "Requirement",
            "Primary owner doc",
            "Acceptance reference"
        ]);
        GddToModuleSplitAddedRequirements.CoverageStatuses.Should().BeEquivalentTo([
            "implemented",
            "not_applicable",
            "explicitly_deferred"
        ]);
        GddToModuleSplitAddedRequirements.RequiredCoverageFields.Should().Contain([
            "phase_exit_review_ref",
            "expiry_or_recheck_trigger",
            "defer_reason"
        ]);
    }

    [Fact]
    public void ExecutionPlanLedger_ShouldParseStableRows()
    {
        var rows = Rows();

        rows.Should().HaveCount(16);
        rows.Select(row => row.SplitAddedId).Should().OnlyHaveUniqueItems();
        rows.Select(row => row.SplitAddedId).Should().Contain([
            "split_added_workflow_action_import_gdd_form",
            "split_added_full_target_capability_schedule",
            "split_added_godot_reference_example_copy_manifest",
            "split_added_godot_third_person_camera_profile"
        ]);
        rows.Should().OnlyContain(row =>
            row.PrimaryOwnerDocs.Count > 0 &&
            !string.IsNullOrWhiteSpace(row.AcceptanceReference));
    }

    [Fact]
    public void LedgerValidator_ShouldRejectDuplicatesMissingOwnersAndBadIds()
    {
        var rows = new[]
        {
            new SplitAddedRequirementRow("bad_id", "", [], "", GddToModuleSplitAddedRequirements.LedgerColumns.Count),
            new SplitAddedRequirementRow("bad_id", "Duplicate", ["02a-route-state-artifacts.md"], "Evidence.", GddToModuleSplitAddedRequirements.LedgerColumns.Count)
        };

        var issues = GddToModuleSplitAddedRequirements.ValidateLedgerRows(rows);

        issues.Should().Contain(issue => issue.Reason == "invalid_split_added_id");
        issues.Should().Contain(issue => issue.Reason == "duplicate_split_added_id");
        issues.Should().Contain(issue => issue.Reason == "missing_requirement");
        issues.Should().Contain(issue => issue.Reason == "missing_primary_owner_doc");
        issues.Should().Contain(issue => issue.Reason == "missing_acceptance_reference");
    }

    [Fact]
    public void ExecutionPlanLedger_ShouldPassSemanticValidation()
    {
        GddToModuleSplitAddedRequirements.ValidateLedgerRows(Rows()).Should().BeEmpty();
    }

    [Fact]
    public void CoverageValidator_ShouldRequireEveryLedgerRowAndOwnerDocEvidence()
    {
        var rows = Rows();
        var coverage = rows.Select(row => new SplitAddedRequirementCoverageRow(
            row.SplitAddedId,
            "implemented",
            row.PrimaryOwnerDocs,
            ["PhaseA.Platform.Tests/Workflow/GddToModuleSplitAddedRequirementsTests.cs"],
            "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-1-exit-review-example.json",
            "Phase A platform",
            "phase-review",
            "")).ToArray();

        GddToModuleSplitAddedRequirements.ValidateCoverage(rows, coverage).Should().BeEmpty();
    }

    [Fact]
    public void CoverageValidator_ShouldRejectMissingRowsOrInvalidDeferrals()
    {
        var rows = Rows();
        var coverage = rows.Skip(1).Select(row => new SplitAddedRequirementCoverageRow(
            row.SplitAddedId,
            row.SplitAddedId == "split_added_full_target_capability_schedule" ? "explicitly_deferred" : "done",
            [],
            [],
            "",
            "",
            "",
            "")).ToArray();

        var issues = GddToModuleSplitAddedRequirements.ValidateCoverage(rows, coverage);

        issues.Should().Contain(issue => issue.SplitAddedId == rows[0].SplitAddedId && issue.Reason == "missing_coverage_row");
        issues.Should().Contain(issue => issue.Reason == "invalid_coverage_status");
        issues.Should().Contain(issue => issue.Reason == "coverage_missing_primary_owner_doc_ref");
        issues.Should().Contain(issue => issue.Reason == "coverage_missing_acceptance_or_phase_evidence");
        issues.Should().Contain(issue => issue.Reason == "deferred_or_not_applicable_missing_owner_recheck_or_reason");
    }

    [Fact]
    public void SchemaExample_ShouldExposeLedgerCoverageRows()
    {
        using var document = JsonDocument.Parse(ReadRepoFile(GddToModuleSplitAddedRequirements.SchemaExamplePath));
        var root = document.RootElement;

        root.GetProperty("schema_version").GetString().Should().Be("gdd-to-module-split-added-requirements.v1");
        root.GetProperty("ledger_id").GetString().Should().Be(GddToModuleSplitAddedRequirements.LedgerId);
        root.GetProperty("execution_plan_ledger_path").GetString().Should().Be(GddToModuleSplitAddedRequirements.ExecutionPlanLedgerPath);
        root.GetProperty("coverage_statuses").EnumerateArray().Select(item => item.GetString())
            .Should()
            .BeEquivalentTo(GddToModuleSplitAddedRequirements.CoverageStatuses);

        var coverage = root.GetProperty("coverage_rows").EnumerateArray().ToArray();
        coverage.Select(row => row.GetProperty("split_added_id").GetString())
            .Should()
            .Contain("split_added_full_target_capability_schedule");
        foreach (var field in GddToModuleSplitAddedRequirements.RequiredCoverageFields)
        {
            coverage[0].TryGetProperty(field, out _).Should().BeTrue($"{field} must be present in coverage evidence rows");
        }
    }

    [Fact]
    public void DurableWorkflowDoc_ShouldLinkExecutionPlanLedgerAndSchema()
    {
        var doc = ReadRepoFile(GddToModuleSplitAddedRequirements.WorkflowDocPath);

        doc.Should().Contain(GddToModuleSplitAddedRequirements.LedgerId);
        doc.Should().Contain(GddToModuleSplitAddedRequirements.ExecutionPlanLedgerPath);
        doc.Should().Contain(GddToModuleSplitAddedRequirements.SchemaExamplePath);
        doc.Should().Contain("implemented");
        doc.Should().Contain("not_applicable");
        doc.Should().Contain("explicitly_deferred");
        doc.Should().Contain("zero unresolved P0/P1/P2");
    }

    private static IReadOnlyList<SplitAddedRequirementRow> Rows()
    {
        return GddToModuleSplitAddedRequirements.ParseLedger(
            ReadRepoFile(GddToModuleSplitAddedRequirements.ExecutionPlanLedgerPath));
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
