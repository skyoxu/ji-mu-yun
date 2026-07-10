using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GddToModuleRiskDodOpenQuestionsTests
{
    [Fact]
    public void Register_ShouldDeclareRisksWithMitigationAndAcceptance()
    {
        GddToModuleRiskDodOpenQuestions.RegisterHash.Should().NotBeNullOrWhiteSpace();
        GddToModuleRiskDodOpenQuestions.Risks.Should().OnlyHaveUniqueItems(row => row.RiskId);
        GddToModuleRiskDodOpenQuestions.Risks.Should().Contain(row => row.RiskId == "diagnostic_spool_leaks_private_evidence");
        GddToModuleRiskDodOpenQuestions.Risks.Should().Contain(row => row.RiskId == "package_download_mistaken_for_final_readiness");
        GddToModuleRiskDodOpenQuestions.Risks.Should().OnlyContain(row =>
            !string.IsNullOrWhiteSpace(row.Risk) &&
            !string.IsNullOrWhiteSpace(row.Mitigation) &&
            !string.IsNullOrWhiteSpace(row.Acceptance));
    }

    [Fact]
    public void DodLayers_ShouldPreventFirstSliceFromClaimingProgramDod()
    {
        var firstSliceItems = GddToModuleRiskDodOpenQuestions.DodItems
            .Where(item => item.Layer == "first_slice")
            .Select(item => item.ItemId)
            .ToHashSet(StringComparer.Ordinal);

        GddToModuleRiskDodOpenQuestions.CanClaimDodLayer(
            "first_slice",
            firstSliceItems,
            new HashSet<string>(StringComparer.Ordinal)).Should().BeTrue();

        GddToModuleRiskDodOpenQuestions.CanClaimDodLayer(
            "program",
            firstSliceItems,
            new HashSet<string>(StringComparer.Ordinal)).Should().BeFalse();

        var allItems = GddToModuleRiskDodOpenQuestions.DodItems
            .Select(item => item.ItemId)
            .ToHashSet(StringComparer.Ordinal);
        GddToModuleRiskDodOpenQuestions.CanClaimDodLayer(
            "program",
            allItems,
            new HashSet<string>(["ui_final_readiness_style_gate"], StringComparer.Ordinal)).Should().BeFalse();
    }

    [Fact]
    public void DecisionMatrix_ShouldRequireDurableEvidenceClassification()
    {
        GddToModuleRiskDodOpenQuestions.DecisionMatrix.Should().Contain(row =>
            row.RequiredEvidence == "adr_or_update" &&
            row.ChangeType.Contains("metadata DB ownership", StringComparison.Ordinal));
        GddToModuleRiskDodOpenQuestions.IsValidDecisionClassification("adr_or_update").Should().BeTrue();
        GddToModuleRiskDodOpenQuestions.IsValidDecisionClassification("decision_log_or_standards").Should().BeTrue();
        GddToModuleRiskDodOpenQuestions.IsValidDecisionClassification("execution_plan_only").Should().BeTrue();
        GddToModuleRiskDodOpenQuestions.IsValidDecisionClassification("chat_only").Should().BeFalse();
    }

    [Fact]
    public void OpenQuestions_ShouldHaveOwnersAndNonBlockingProof()
    {
        GddToModuleRiskDodOpenQuestions.OpenQuestions.Should().HaveCountGreaterThanOrEqualTo(6);
        GddToModuleRiskDodOpenQuestions.OpenQuestions.Should().OnlyContain(question =>
            !string.IsNullOrWhiteSpace(question.Owner) &&
            !string.IsNullOrWhiteSpace(question.Phase1NonBlockingProof));
        GddToModuleRiskDodOpenQuestions.Phase1DefaultDecisions.Should().Contain([
            "requirement_map_rows_not_user_editable",
            "contract_stale_blocks_new_iteration_plan",
            "ui_closure_not_required_for_ordinary_package_download",
            "workflow_recommended_ui_style_with_override"
        ]);
    }

    [Fact]
    public void ClosureReviewSchema_ShouldExposeDodLayerAndDecisionClassifications()
    {
        using var document = JsonDocument.Parse(ReadRepoFile(GddToModuleRiskDodOpenQuestions.ClosureReviewSchemaPath));
        var root = document.RootElement;

        root.GetProperty("schema_version").GetString().Should().Be("gdd-to-module-dod-closure-review.v1");
        root.GetProperty("claimed_dod_layer").GetString().Should().Be("first_slice");
        root.GetProperty("unresolved_consumed_capabilities").GetArrayLength().Should().Be(0);
        var invalidClassifications = root.GetProperty("decision_classifications").EnumerateArray()
            .Select(item => item.GetProperty("classification").GetString())
            .Where(classification => classification is null || !GddToModuleRiskDodOpenQuestions.IsValidDecisionClassification(classification))
            .ToArray();
        invalidClassifications.Should().BeEmpty();
    }

    [Fact]
    public void DurableWorkflowDoc_ShouldMentionRiskDodOpenQuestionBoundaries()
    {
        var doc = ReadRepoFile(GddToModuleRiskDodOpenQuestions.StandardPath);

        doc.Should().Contain(GddToModuleRiskDodOpenQuestions.RegisterId);
        doc.Should().Contain("Program DoD is not claimed by the first implementation slice");
        doc.Should().Contain("zero unresolved P0/P1/P2");
        doc.Should().Contain("ADR And Decision-Log Matrix");
        doc.Should().Contain("Open Questions");
        doc.Should().Contain("Phase 1 Default Decisions");
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
