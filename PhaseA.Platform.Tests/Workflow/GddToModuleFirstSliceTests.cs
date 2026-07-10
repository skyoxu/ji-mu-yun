using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class GddToModuleFirstSliceTests
{
    [Fact]
    public void Registry_ShouldDeclarePhase0AThenPhase0BThenSmallestPhase1Slice()
    {
        GddToModuleFirstSlice.SliceHash.Should().NotBeNullOrWhiteSpace();
        GddToModuleFirstSlice.Phase0AMandatoryBaseline.Should().HaveCount(17);
        GddToModuleFirstSlice.Phase0BRouteDependentBaseline.Should().HaveCount(6);
        GddToModuleFirstSlice.SmallestPhase1Slice.Should().HaveCount(11);

        GddToModuleFirstSlice.Phase0AMandatoryBaseline.Select(item => item.ItemId)
            .Should()
            .Contain([
                "0A-01",
                "0A-08",
                "0A-11",
                "0A-15",
                "0A-17"
            ]);
        GddToModuleFirstSlice.Phase0BRouteDependentBaseline.Select(item => item.ItemId)
            .Should()
            .Contain([
                "0B-18",
                "0B-21",
                "0B-23"
            ]);
        GddToModuleFirstSlice.SmallestPhase1Slice.Select(item => item.ItemId)
            .Should()
            .Contain([
                "P1-23",
                "P1-28",
                "P1-33"
            ]);

        GddToModuleFirstSlice.Phase0AMandatoryBaseline
            .Concat(GddToModuleFirstSlice.Phase0BRouteDependentBaseline)
            .Concat(GddToModuleFirstSlice.SmallestPhase1Slice)
            .Should()
            .OnlyHaveUniqueItems(item => item.ItemId);
    }

    [Fact]
    public void Phase1StartGate_ShouldRequireAllPhase0AItemsAndZeroBlockingFindings()
    {
        var completed = GddToModuleFirstSlice.Phase0AMandatoryBaseline
            .Select(item => item.ItemId)
            .ToHashSet(StringComparer.Ordinal);
        var zeroFindings = new Dictionary<string, int>
        {
            ["P0"] = 0,
            ["P1"] = 0,
            ["P2"] = 0
        };

        GddToModuleFirstSlice.CanStartPhase1(completed, zeroFindings).Should().BeTrue();

        completed.Remove("0A-15");
        GddToModuleFirstSlice.CanStartPhase1(completed, zeroFindings).Should().BeFalse();

        completed.Add("0A-15");
        GddToModuleFirstSlice.CanStartPhase1(completed, new Dictionary<string, int>
        {
            ["P0"] = 0,
            ["P1"] = 0,
            ["P2"] = 1
        }).Should().BeFalse();
    }

    [Fact]
    public void CapabilitySchedule_ShouldCoverFullTargetPackagesAndLedgerFields()
    {
        GddToModuleFirstSlice.CapabilitySchedule.Should().HaveCount(4);
        GddToModuleFirstSlice.CapabilityIds.Should().Contain([
            "ui_component_system",
            "ui_style_snapshot_schema",
            "godot_diagnostic_spool_contract",
            "ui_lifecycle_ownership",
            "godot_interaction_region_gate",
            "ui_final_readiness_style_gate",
            "ui_security_gated_tooling"
        ]);

        GddToModuleFirstSlice.CapabilityIds.Should().OnlyHaveUniqueItems();
        GddToModuleFirstSlice.RequiredLedgerFields.Should().Contain([
            "firstRequiredPhase",
            "trigger",
            "ownerEvidence",
            "currentCoverageStatus",
            "phase_exit_review_ref"
        ]);
    }

    [Fact]
    public void ConsumedScheduleValidator_ShouldRejectInterimStatusWithoutReviewedEscape()
    {
        var rows = MinimalRows().Select(row =>
            row.CapabilityId == "ui_component_system"
                ? row with
                {
                    CurrentCoverageStatus = GddToModuleFirstSlice.InterimCoverageStatus,
                    ClosureStatus = "covered"
                }
                : row);

        var violations = GddToModuleFirstSlice.ValidateConsumedCapabilitySchedule(
            rows,
            new HashSet<string>(["ui_component_system"], StringComparer.Ordinal));

        violations.Should().ContainSingle(v =>
            v.CapabilityId == "ui_component_system" &&
            v.Reason == "consumed_capability_left_not_consumed_by_first_slice");
    }

    [Fact]
    public void ConsumedScheduleValidator_ShouldAllowReviewedDeferralWithOwnerExpiryAndEvidence()
    {
        var rows = MinimalRows().Select(row =>
            row.CapabilityId == "ui_component_system"
                ? row with
                {
                    CurrentCoverageStatus = GddToModuleFirstSlice.InterimCoverageStatus,
                    ClosureStatus = "explicitly_deferred",
                    DeferReason = "Not consumed by the current touched route."
                }
                : row);

        var violations = GddToModuleFirstSlice.ValidateConsumedCapabilitySchedule(
            rows,
            new HashSet<string>(["ui_component_system"], StringComparer.Ordinal));

        violations.Should().BeEmpty();
    }

    [Fact]
    public void FinalClosureLedgerValidator_ShouldRejectMissingOrOrphanOrInterimRows()
    {
        var rows = MinimalRows()
            .Where(row => row.CapabilityId != "ui_security_gated_tooling")
            .Append(new FullTargetCapabilityLedgerRow(
                "orphan_capability",
                "docs/standards/unknown.md",
                "Phase 9",
                "never",
                "none",
                "covered",
                "covered",
                ["prototype-contract"],
                "Phase A platform",
                "phase-6",
                ["PhaseA.Platform.Tests"],
                "",
                "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-6-exit-review-example.json"))
            .Select(row =>
                row.CapabilityId == "ui_component_system"
                    ? row with { CurrentCoverageStatus = GddToModuleFirstSlice.InterimCoverageStatus }
                    : row);

        var violations = GddToModuleFirstSlice.ValidateFinalClosureLedger(rows);

        violations.Should().Contain(v => v.CapabilityId == "ui_security_gated_tooling" && v.Reason == "missing_ledger_row");
        violations.Should().Contain(v => v.CapabilityId == "orphan_capability" && v.Reason == "orphan_ledger_row");
        violations.Should().Contain(v => v.CapabilityId == "ui_component_system" && v.Reason == "interim_status_not_final");
    }

    [Fact]
    public void CommitReadinessGate_ShouldRejectUntrackedSplitFilesOrMonolithLiveMirror()
    {
        GddToModuleFirstSlice.IsCommitReady(new FirstSliceCommitReadiness(
            SplitDirectoryIncluded: true,
            SchemaFixturesIncluded: true,
            NoUntrackedSplitPlanFiles: true,
            MonolithicSourceUsedAsLiveMirror: false,
            MonolithicSourceChanged: false,
            MonolithicSourceChangeRecordedAsHistoryMaintenance: false)).Should().BeTrue();

        GddToModuleFirstSlice.IsCommitReady(new FirstSliceCommitReadiness(
            SplitDirectoryIncluded: true,
            SchemaFixturesIncluded: true,
            NoUntrackedSplitPlanFiles: false,
            MonolithicSourceUsedAsLiveMirror: false,
            MonolithicSourceChanged: false,
            MonolithicSourceChangeRecordedAsHistoryMaintenance: false)).Should().BeFalse();

        GddToModuleFirstSlice.IsCommitReady(new FirstSliceCommitReadiness(
            SplitDirectoryIncluded: true,
            SchemaFixturesIncluded: true,
            NoUntrackedSplitPlanFiles: true,
            MonolithicSourceUsedAsLiveMirror: true,
            MonolithicSourceChanged: true,
            MonolithicSourceChangeRecordedAsHistoryMaintenance: true)).Should().BeFalse();
    }

    [Fact]
    public void FirstSliceReviewSchema_ShouldExposeOrderingAndCommitReadinessFields()
    {
        using var document = JsonDocument.Parse(ReadRepoFile(GddToModuleFirstSlice.FirstSliceReviewSchemaPath));
        var root = document.RootElement;

        root.GetProperty("schema_version").GetString().Should().Be("gdd-to-module-first-slice-review.v1");
        root.GetProperty("slice_id").GetString().Should().Be(GddToModuleFirstSlice.SliceId);
        root.GetProperty("phase0a_exit").GetProperty("can_start_phase1").GetBoolean().Should().BeTrue();
        root.GetProperty("commit_readiness").GetProperty("split_directory_included").GetBoolean().Should().BeTrue();
        root.GetProperty("phase1_slice_items").EnumerateArray()
            .Select(item => item.GetProperty("item_id").GetString())
            .Should()
            .Contain("P1-33");
    }

    [Fact]
    public void FullTargetLedgerSchema_ShouldExposeScheduleFieldsAndNoFinalInterimRows()
    {
        using var document = JsonDocument.Parse(ReadRepoFile(GddToModuleFirstSlice.FullTargetLedgerSchemaPath));
        var root = document.RootElement;

        root.GetProperty("schema_version").GetString().Should().Be("full-target-ui-closure-ledger.v1");
        root.GetProperty("runtime_path").GetString().Should().Be(GddToModuleFirstSlice.FullTargetLedgerRuntimePath);

        var rows = root.GetProperty("capability_packages").EnumerateArray().ToArray();
        rows.Select(row => row.GetProperty("capability_id").GetString())
            .Should()
            .BeEquivalentTo(GddToModuleFirstSlice.CapabilityIds);

        foreach (var row in rows)
        {
            foreach (var field in GddToModuleFirstSlice.RequiredLedgerFields)
            {
                row.TryGetProperty(field, out _).Should().BeTrue($"{field} is required by the full-target ledger schema");
            }

            row.GetProperty("currentCoverageStatus").GetString()
                .Should()
                .NotBe(GddToModuleFirstSlice.InterimCoverageStatus);
            GddToModuleFirstSlice.FinalClosureStatuses
                .Should()
                .Contain(row.GetProperty("closure_status").GetString());
        }
    }

    [Fact]
    public void DurableWorkflowDoc_ShouldMentionFirstSliceBoundaries()
    {
        var doc = ReadRepoFile(GddToModuleFirstSlice.WorkflowDocPath);

        doc.Should().Contain(GddToModuleFirstSlice.SliceId);
        doc.Should().Contain(GddToModuleFirstSlice.FirstSliceReviewSchemaPath);
        doc.Should().Contain(GddToModuleFirstSlice.FullTargetLedgerRuntimePath);
        doc.Should().Contain("Phase 1 work must not start until Phase 0A");
        doc.Should().Contain(GddToModuleFirstSlice.InterimCoverageStatus);
        doc.Should().Contain("not a final closure state");
        doc.Should().Contain("Program DoD");
    }

    private static IReadOnlyList<FullTargetCapabilityLedgerRow> MinimalRows()
    {
        return GddToModuleFirstSlice.CapabilitySchedule
            .SelectMany(schedule => schedule.CapabilityIds.Select(capabilityId => new FullTargetCapabilityLedgerRow(
                capabilityId,
                OwnerDocFor(capabilityId),
                schedule.FirstRequiredPhase,
                schedule.Trigger,
                schedule.OwnerEvidence,
                "covered",
                "covered",
                ["prototype-contract"],
                "Phase A platform",
                "phase-6-or-route-consumption",
                ["PhaseA.Platform.Tests/Workflow/GddToModuleFirstSliceTests.cs"],
                "",
                "logs/phase-a-innernet/reviews/gdd-to-module-hardening/phase-6-exit-review-example.json")))
            .ToArray();
    }

    private static string OwnerDocFor(string capabilityId)
    {
        if (capabilityId.StartsWith("godot_", StringComparison.Ordinal))
        {
            return "docs/standards/godot-diagnostics-quality-gates.md";
        }

        if (capabilityId.Contains("closure", StringComparison.Ordinal) ||
            capabilityId.Contains("repair", StringComparison.Ordinal) ||
            capabilityId.Contains("final_readiness", StringComparison.Ordinal))
        {
            return "docs/standards/godot-ui-style-closure.md";
        }

        return "docs/standards/godot-ui-style-contract.md";
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
