using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GddToModuleGlobalReviewStandardTests
{
    [Fact]
    public void Registry_ShouldDeclareAuthorityReviewModesAndMechanicalChecks()
    {
        GddToModuleGlobalReviewStandard.StandardHash.Should().NotBeNullOrWhiteSpace();
        GddToModuleGlobalReviewStandard.AuthorityFiles.Should().BeEquivalentTo([
            "AGENTS.md",
            "README.md",
            GddToModuleGlobalReviewStandard.ExecutionPlanStandardPath
        ]);

        GddToModuleGlobalReviewStandard.ReviewModes.Select(mode => mode.ModeId)
            .Should()
            .BeEquivalentTo([
                "whole-directory",
                "standard-only",
                "standard-change-self-review"
            ]);

        GddToModuleGlobalReviewStandard.WholeDirectoryMechanicalChecks.Should().Contain([
            "file_inventory",
            "link_integrity",
            "json_validity",
            "ledger_and_audit_alignment",
            "status_action_schema_vocabulary_consistency"
        ]);
        GddToModuleGlobalReviewStandard.ScopedMechanicalChecks.Should().Contain([
            "authority_file_read_coverage",
            "standard_structure_and_ledger_validity",
            "open_ledger_blocker_checks",
            "standard_change_completeness"
        ]);
    }

    [Fact]
    public void ExecutionPlanStandard_ShouldContainRequiredSections()
    {
        var markdown = ReadRepoFile(GddToModuleGlobalReviewStandard.ExecutionPlanStandardPath);

        GddToModuleGlobalReviewStandard.HasRequiredSections(markdown).Should().BeTrue();
        markdown.Should().Contain("Every review must declare exactly one review mode");
        markdown.Should().Contain("A split-plan statement is normative");
        markdown.Should().Contain("The Standard Self-Review Gate passes only when");
        markdown.Should().Contain("mechanical-check summary");
    }

    [Fact]
    public void PriorFindingLedger_ShouldParseWithStableIdsAndNoOpenWholeDirectoryBlockers()
    {
        var rows = GddToModuleGlobalReviewStandard.ParsePriorFindingLedger(
            ReadRepoFile(GddToModuleGlobalReviewStandard.ExecutionPlanStandardPath));

        rows.Should().HaveCountGreaterThan(40);
        rows.Select(row => row.FindingId).Should().OnlyHaveUniqueItems();
        rows.Should().Contain(row => row.FindingId == "GRD-P1-005");
        rows.Should().Contain(row => row.FindingId == "GRD-P2-004");
        GddToModuleGlobalReviewStandard.OpenWholeDirectoryBlockerIds(rows).Should().BeEmpty();
    }

    [Fact]
    public void PriorFindingLedgerValidator_ShouldRejectInvalidClosedRows()
    {
        var rows = new[]
        {
            new PriorFindingRow(
                "GRS-P1-999",
                "P1",
                "Closed",
                "None",
                "Closed without evidence.",
                "bad-link",
                "Validation has no source refs.",
                GddToModuleGlobalReviewStandard.PriorFindingLedgerColumns.Count)
        };

        var issues = GddToModuleGlobalReviewStandard.ValidatePriorFindingLedger(rows);

        issues.Should().Contain(issue => issue.Reason == "closed_row_missing_closure_evidence");
        issues.Should().Contain(issue => issue.Reason == "closed_row_missing_source_refs");
        issues.Should().Contain(issue => issue.Reason == "invalid_linked_finding");
    }

    [Fact]
    public void PriorFindingLedger_ShouldPassSemanticValidation()
    {
        var rows = GddToModuleGlobalReviewStandard.ParsePriorFindingLedger(
            ReadRepoFile(GddToModuleGlobalReviewStandard.ExecutionPlanStandardPath));

        var issues = GddToModuleGlobalReviewStandard.ValidatePriorFindingLedger(rows);

        issues.Should().BeEmpty();
    }

    [Fact]
    public void ReviewOutputRequirements_ShouldCoverStableFindingAndMechanicalSummary()
    {
        GddToModuleGlobalReviewStandard.ReviewOutputRequirementIds.Should().Contain([
            "state_review_mode",
            "state_authority_set",
            "mechanical_check_summary",
            "stable_finding_ids",
            "file_line_references",
            "separate_target_findings_from_open_blockers",
            "skipped_mechanical_checks"
        ]);

        GddToModuleGlobalReviewStandard.IsKnownReviewMode("whole-directory").Should().BeTrue();
        GddToModuleGlobalReviewStandard.IsKnownReviewMode("quick-review").Should().BeFalse();
    }

    [Fact]
    public void SchemaExample_ShouldMirrorRegistry()
    {
        using var document = JsonDocument.Parse(ReadRepoFile(GddToModuleGlobalReviewStandard.SchemaExamplePath));
        var root = document.RootElement;

        root.GetProperty("schema_version").GetString().Should().Be("gdd-to-module-global-review-standard.v1");
        root.GetProperty("standard_id").GetString().Should().Be(GddToModuleGlobalReviewStandard.StandardId);
        root.GetProperty("execution_plan_standard_path").GetString().Should().Be(GddToModuleGlobalReviewStandard.ExecutionPlanStandardPath);
        root.GetProperty("authority_files").EnumerateArray().Select(item => item.GetString())
            .Should()
            .BeEquivalentTo(GddToModuleGlobalReviewStandard.AuthorityFiles);
        root.GetProperty("prior_finding_ledger_columns").EnumerateArray().Select(item => item.GetString())
            .Should()
            .BeEquivalentTo(GddToModuleGlobalReviewStandard.PriorFindingLedgerColumns);
    }

    [Fact]
    public void DurableWorkflowDoc_ShouldLinkExecutionPlanStandardAndSchema()
    {
        var doc = ReadRepoFile(GddToModuleGlobalReviewStandard.WorkflowDocPath);

        doc.Should().Contain(GddToModuleGlobalReviewStandard.StandardId);
        doc.Should().Contain(GddToModuleGlobalReviewStandard.ExecutionPlanStandardPath);
        doc.Should().Contain(GddToModuleGlobalReviewStandard.SchemaExamplePath);
        doc.Should().Contain("whole-directory");
        doc.Should().Contain("standard-only");
        doc.Should().Contain("standard-change self-review");
        doc.Should().Contain("Prior Finding Ledger");
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
