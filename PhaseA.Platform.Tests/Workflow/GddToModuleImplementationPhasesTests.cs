using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GddToModuleImplementationPhasesTests
{
    [Fact]
    public void Registry_ShouldDeclarePhase0AAndPhase0BPrerequisites()
    {
        GddToModuleImplementationPhases.PlanHash.Should().NotBeNullOrWhiteSpace();
        GddToModuleImplementationPhases.Phase0AItems.Should().Contain([
            "route_module_contract_template",
            "minimum_diagnostic_index_schema",
            "shared_llm_codex_entrypoint_guard"
        ]);
        GddToModuleImplementationPhases.Phase0BItems.Should().Contain([
            "godot_engine_semantic_baseline",
            "godot_ui_capability_contract_template",
            "godot_ui_style_contract_template",
            "godot_diagnostics_quality_gate_contract"
        ]);
    }

    [Fact]
    public void Registry_ShouldCoverAllImplementationPhasesAndRoutes()
    {
        GddToModuleImplementationPhases.Phases.Select(phase => phase.Phase)
            .Should()
            .BeEquivalentTo(["0A", "0B", "1", "2", "3", "4", "5", "6"]);

        var phase6 = GddToModuleImplementationPhases.Find("6");
        phase6.Should().NotBeNull();
        phase6!.Routes.Should().Contain([
            "structured-game-type-analysis",
            "scene-route-confirmation",
            "gdd-document-generation",
            "gdd-requirements",
            "prototype-contract",
            "prototype-skeleton-guard",
            "workflow-recommendation",
            "iteration-plan",
            "execute-next-goal",
            "needs-fix",
            "repair",
            "project-delete",
            "ui-wiring-closure",
            "preview-package"
        ]);

        phase6.Routes.Where(route => RouteModuleContracts.Find(route) is null)
            .Should()
            .BeEmpty();
    }

    [Fact]
    public void PhaseExitReviewSchema_ShouldExposeRequiredEvidenceFields()
    {
        using var document = JsonDocument.Parse(ReadRepoFile(GddToModuleImplementationPhases.PhaseExitReviewSchemaPath));
        var root = document.RootElement;

        foreach (var field in GddToModuleImplementationPhases.RequiredPhaseExitReviewFields)
        {
            root.TryGetProperty(field, out _).Should().BeTrue($"{field} is required for phase exit review evidence");
        }

        root.GetProperty("evidence_root").GetString().Should().Be(GddToModuleImplementationPhases.DefaultReviewEvidenceRoot);
        root.GetProperty("unresolved_findings_by_severity").GetProperty("P0").GetInt32().Should().Be(0);
        root.GetProperty("unresolved_findings_by_severity").GetProperty("P1").GetInt32().Should().Be(0);
        root.GetProperty("unresolved_findings_by_severity").GetProperty("P2").GetInt32().Should().Be(0);
    }

    [Fact]
    public void ReviewHelpers_ShouldRequireZeroP0P1P2AndStableEvidenceFileNames()
    {
        GddToModuleImplementationPhases.HasZeroBlockingFindings(new Dictionary<string, int>
        {
            ["P0"] = 0,
            ["P1"] = 0,
            ["P2"] = 0
        }).Should().BeTrue();

        GddToModuleImplementationPhases.HasZeroBlockingFindings(new Dictionary<string, int>
        {
            ["P0"] = 0,
            ["P1"] = 1,
            ["P2"] = 0
        }).Should().BeFalse();

        GddToModuleImplementationPhases.ReviewFileName("1", "20260710T000000Z")
            .Should()
            .Be("phase-1-exit-review-20260710T000000Z.json");
    }

    [Fact]
    public void ImportGddFormDeferral_Phase6ClosureGuard_ShouldRemainFailClosed()
    {
        const string evidenceIndexPath =
            "execution-plans/2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening/schemas/implementation-acceptance-evidence-index.v1.json";
        using var document = JsonDocument.Parse(ReadRepoFile(evidenceIndexPath));
        var entry = document.RootElement.GetProperty("entries").EnumerateArray().Single(item =>
            item.GetProperty("check_id").GetString() == "GTM-SAR-WORKFLOW-ACTION-IMPORT-GDD-FORM");

        entry.GetProperty("status").GetString().Should().Be("explicitly_deferred");
        entry.GetProperty("defer_severity").GetString().Should().BeOneOf("P0", "P1", "P2");
        entry.GetProperty("defer_affected_routes").GetArrayLength().Should().BeGreaterThan(0);
        entry.GetProperty("defer_current_scope_non_impact_proof").GetString().Should().NotBeNullOrWhiteSpace();
        entry.GetProperty("defer_phase6_closure_test").GetString().Should().Be(
            "PhaseA.Platform.Tests/Workflow/GddToModuleImplementationPhasesTests.cs::ImportGddFormDeferral_Phase6ClosureGuard_ShouldRemainFailClosed");
        entry.GetProperty("defer_recheck_trigger").GetString().Should().NotBeNullOrWhiteSpace();

        var descriptor = RouteActionDescriptors.Get("import_gdd_form");
        descriptor.OperationScope.Should().Be("non_action");
        descriptor.ApiRouteTemplate.Should().BeEmpty();
    }

    [Fact]
    public void DurableWorkflowDoc_ShouldLinkStandardsAndEvidenceSchema()
    {
        var doc = ReadRepoFile(GddToModuleImplementationPhases.StandardPath);

        doc.Should().Contain(GddToModuleImplementationPhases.PlanId);
        doc.Should().Contain(GddToModuleImplementationPhases.PhaseExitReviewSchemaPath);
        doc.Should().Contain(GddToModuleImplementationPhases.DefaultReviewEvidenceRoot);
        doc.Should().Contain("Phase 0A");
        doc.Should().Contain("Phase 0B");
        doc.Should().Contain("Phase 6");
        doc.Should().Contain("zero unresolved P0/P1/P2");
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
