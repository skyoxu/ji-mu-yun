using FluentAssertions;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class IterationPlanTraceabilityBuilderTests
{
    [Fact]
    public void Build_ShouldCloseP0P1CoverageAcrossGoalsAndRequiredModules()
    {
        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([
                Requirement("REQ-001", "P0", "scene", goalIds: ["goal-1"]),
                Requirement("REQ-002", "P1", "ui", goalIds: ["goal-2"], moduleIds: ["combat_hud"]),
                Requirement("REQ-003", "P1", "ui", goalIds: ["goal-2"], moduleIds: ["route_map_path_selection"])
            ]),
            [Goal(1, "Field movement"), Goal(2, "Final acceptance")],
            [Module("combat_hud"), Module("route_map_path_selection")],
            SourceHashes(), styleAuthority: StyleAuthority());

        result.Blockers.Should().BeEmpty();
        result.Coverage.UncoveredRequirementIds.Should().BeEmpty();
        result.Coverage.P0P1RequirementCount.Should().Be(3);
        result.Goals.Single(goal => goal.GoalIndex == 1).RequirementIds.Should().Contain("REQ-001");
        result.Goals.Single(goal => goal.GoalIndex == 2).UiSurface.Should().NotBeNull();
        result.Goals.Single(goal => goal.GoalIndex == 2).Style.Should().NotBeNull();
        result.Goals.Should().OnlyContain(goal => goal.RequirementIds!.Count > 0 || goal.InfrastructureReason != null);
        result.RequiredModules.Single(module => module.Id == "combat_hud").RequirementIds.Should().Contain("REQ-002");
        result.RequiredModules.Single(module => module.Id == "route_map_path_selection").RequirementIds.Should().Contain("REQ-003");
        result.PlanHash.Should().NotBeNullOrWhiteSpace();
        result.SourceHashRef.Should().NotBeNullOrWhiteSpace();
    }

    [Fact]
    public void Build_ShouldKeepDeckbuilderRequiredModulesIndependentAndRequirementLinked()
    {
        var moduleIds = new[] { "route_map_path_selection", "hand_card_dragging", "combat_hud", "reward_selection" };
        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap(moduleIds.Select((id, index) => Requirement($"REQ-{index + 1:000}", index == 0 ? "P0" : "P1", "ui", goalIds: ["goal-1"], moduleIds: [id])).ToArray()),
            [Goal(1, "Deckbuilder infrastructure")],
            moduleIds.Select(Module).ToArray(),
            SourceHashes(), styleAuthority: StyleAuthority());

        result.Blockers.Should().BeEmpty();
        result.RequiredModules.Select(module => module.Id).Should().Contain(moduleIds);
        result.RequiredModules.Where(module => moduleIds.Contains(module.Id, StringComparer.OrdinalIgnoreCase))
            .Should().OnlyContain(module => module.RequirementIds!.Count == 1 && module.SourceReason == "requirement_map_module_mapping");
    }

    [Fact]
    public void Build_ShouldBlockExplicitMappingsThatDoNotResolve()
    {
        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([
                Requirement("REQ-001", "P0", "scene", goalIds: ["missing-goal"]),
                Requirement("REQ-002", "P1", "ui", moduleIds: ["missing-module"])
            ]),
            [Goal(1, "Field movement")],
            [Module("combat_hud")],
            SourceHashes(), styleAuthority: StyleAuthority());

        result.Coverage.UncoveredRequirementIds.Should().BeEquivalentTo(["REQ-001"]);
        result.RequiredModules.Should().Contain(module => module.Id == "missing-module" && module.RequirementIds!.Contains("REQ-002"));
        result.Blockers.Should().Contain(blocker => blocker.DomainCode == "coverage_gap");
    }

    [Fact]
    public void Build_ShouldRejectDuplicateEmptyAndUnknownRequirementIds()
    {
        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([
                Requirement("REQ-001", "P0", "scene"),
                Requirement("REQ-001", "P1", "ui"),
                Requirement("", "P1", "ui")
            ]),
            [Goal(1, "Field movement") with { RequirementIds = ["UNKNOWN-001"] }],
            [Module("combat_hud")],
            SourceHashes(), styleAuthority: StyleAuthority());

        result.Blockers.Select(blocker => blocker.DomainCode).Should().Contain([
            "requirement_id_duplicate",
            "requirement_id_empty",
            "requirement_id_unknown"
        ]);
    }

    [Fact]
    public void Build_ShouldBlockIncompleteDynamicUiAndThirdPersonProfiles()
    {
        var dynamicUi = Requirement("REQ-001", "P0", "ui", goalIds: ["goal-1"]) with
        {
            CapabilityDomainIds = ["dynamic_item_factory"],
            GodotUiUpdateOwnership = new GodotUiUpdateOwnership(
                "InventoryPanel",
                "signal_driven",
                "InventoryState",
                "disconnect_on_exit",
                "item_id")
        };
        var camera = Requirement("REQ-002", "P1", "camera", goalIds: ["goal-2"]) with
        {
            NormalizedRequirement = "Third-person camera follows the player.",
            GodotThirdPersonCameraProfile = new GodotThirdPersonCameraProfile(
                "res://Camera/ThirdPersonRig.tscn",
                "Player",
                "PlayerInput",
                "ThirdPersonRig",
                "camera-state-smoke")
        };

        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([dynamicUi, camera]),
            [Goal(1, "Inventory UI"), Goal(2, "Third-person camera")],
            [],
            SourceHashes(), styleAuthority: StyleAuthority());

        result.Blockers.Select(blocker => blocker.DomainCode).Should().Contain([
            "ui_update_ownership_missing",
            "third_person_camera_profile_missing"
        ]);
    }

    [Fact]
    public void Build_ShouldNotInferP0P1CoverageFromSharedFreeTextTokens()
    {
        var requirement = Requirement("REQ-001", "P0", "security") with
        {
            NormalizedRequirement = "Player data must be encrypted.",
            NormalizedSourceSummary = "Protect player account data."
        };

        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([requirement]),
            [Goal(1, "Player movement")],
            [],
            SourceHashes(), styleAuthority: StyleAuthority());

        result.Coverage.UncoveredRequirementIds.Should().ContainSingle().Which.Should().Be("REQ-001");
        result.Blockers.Should().Contain(blocker => blocker.DomainCode == "coverage_gap");
    }

    [Fact]
    public void Build_ShouldCountFreshSkeletonVerifiedSceneOnlyRequirement()
    {
        var requirement = Requirement("REQ-SCENE", "P0", "scene") with
        {
            Status = "mapped",
            MappedSceneIds = ["field_map"]
        };

        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([requirement]),
            [],
            [],
            SourceHashes(),
            styleAuthority: StyleAuthority(),
            verifiedSkeletonRequirementIds: new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "REQ-SCENE" });

        result.Coverage.SkeletonCoveredCount.Should().Be(1);
        result.Coverage.UncoveredRequirementIds.Should().BeEmpty();
        result.Blockers.Should().NotContain(blocker => blocker.DomainCode == "coverage_gap");
    }

    [Fact]
    public void Build_ShouldNotCountSkippedModuleAsRequirementCoverage()
    {
        var skippedModule = Module("combat_hud") with { Status = "skipped_by_explicit_gdd_conflict" };

        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([Requirement("REQ-001", "P0", "ui", moduleIds: ["combat_hud"])]),
            [Goal(1, "Infrastructure")],
            [skippedModule],
            SourceHashes(), styleAuthority: StyleAuthority());

        result.Coverage.UncoveredRequirementIds.Should().ContainSingle().Which.Should().Be("REQ-001");
        result.Blockers.Should().Contain(blocker => blocker.DomainCode == "coverage_gap");
    }

    [Fact]
    public void Build_ShouldCreateCapabilityGoal_WhenExecutableModuleHasInvalidSibling()
    {
        var requirement = Requirement(
            "REQ-001",
            "P0",
            "ui",
            moduleIds: ["combat_hud", "legacy_hud"]) with
        {
            CapabilityDomainIds = ["ui_component_system"],
            GodotUiUpdateOwnership = new GodotUiUpdateOwnership(
                "CombatHud",
                "signal_driven",
                "CombatState",
                "disconnect_on_exit",
                "combatant_id",
                "state_changed")
        };

        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([requirement]),
            [],
            [
                Module("combat_hud") with { Status = "required" },
                Module("legacy_hud") with { Status = "skipped_by_explicit_gdd_conflict" }
            ],
            SourceHashes(),
            styleAuthority: StyleAuthority());

        result.Goals.Should().ContainSingle(goal => goal.RequirementIds!.Contains("REQ-001"));
        result.Goals.Single(goal => goal.RequirementIds!.Contains("REQ-001")).CapabilityRequirements!.DynamicUiRequired.Should().BeTrue();
    }

    [Fact]
    public void Build_ShouldSelectExecutableModuleForSyntheticCapabilityGoal()
    {
        var requirement = Requirement(
            "REQ-001",
            "P0",
            "ui",
            moduleIds: ["legacy_hud", "combat_hud"]) with
        {
            CapabilityDomainIds = ["ui_component_system"],
            GodotUiUpdateOwnership = new GodotUiUpdateOwnership(
                "CombatHud",
                "signal_driven",
                "CombatState",
                "disconnect_on_exit",
                "combatant_id",
                "state_changed")
        };

        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([requirement]),
            [],
            [
                Module("legacy_hud") with { Status = "skipped_by_explicit_gdd_conflict" },
                Module("combat_hud") with { Status = "required" }
            ],
            SourceHashes(),
            styleAuthority: StyleAuthority());

        result.Goals.Should().ContainSingle();
        result.Goals[0].Title.Should().Contain("combat_hud");
        result.Goals[0].Title.Should().NotContain("legacy_hud");
    }

    [Fact]
    public void Build_ShouldNotApproveRequirementBlockerBySubstringMatch()
    {
        var map = RequirementMap([
            Requirement("REQ-1", "P1", "scene", goalIds: ["goal-1"]),
            Requirement("REQ-10", "P1", "scene", goalIds: ["goal-1"])
        ]) with
        {
            BlockingIssues = [new ProjectWorkflowBlockingIssue(
                "gdd-requirements:REQ-10:requirement_gap",
                "requirement_map_invalid",
                "P1",
                "REQ-10 still needs review.",
                [])]
        };

        var result = IterationPlanTraceabilityBuilder.Build(
            map,
            [Goal(1, "Field movement")],
            [],
            SourceHashes(),
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["REQ-1"] = "admin-review:REQ-1"
            },
            StyleAuthority());

        result.Blockers.Should().Contain(blocker => blocker.Summary.Contains("REQ-10", StringComparison.Ordinal));
    }

    [Fact]
    public void Build_ShouldRemoveExecutableWorkForAdminApprovedConflict()
    {
        var deferred = Requirement("REQ-001", "P1", "ui", goalIds: ["goal-1"], moduleIds: ["legacy_hud"]) with
        {
            Status = "conflict",
            CapabilityDomainIds = ["ui_component_system"]
        };

        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([deferred]),
            [Goal(1, "Implement legacy_hud")],
            [Module("legacy_hud") with { Status = "skipped_by_explicit_gdd_conflict" }],
            SourceHashes(),
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["REQ-001"] = "admin-review:REQ-001"
            },
            StyleAuthority());

        result.Goals.Should().BeEmpty();
        result.RequiredModules.Should().Contain(module =>
            module.Id == "legacy_hud" &&
            module.CoverageStatus == "reviewed_not_applicable" &&
            module.SourceRefs!.Contains("admin-review:REQ-001"));
        result.RequiredModules.Should().NotContain(module => module.Id == "decision_disposition_req-001");
        result.Blockers.Should().BeEmpty();
    }

    [Fact]
    public void Build_ShouldAllowReviewedStyleNotApplicableAndRetainDecisionEvidence()
    {
        var uiRequirement = Requirement("REQ-UI", "P1", "ui", goalIds: ["goal-1"]) with
        {
            CapabilityDomainIds = ["ui_component_system"]
        };
        var applicability = new PrototypeIterationStyleApplicability(
            "reviewed_not_applicable",
            "Style scope was reviewed as not applicable.",
            "reviewer",
            "when visible style scope changes",
            "style-decision-hash");

        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([uiRequirement]),
            [Goal(1, "UI surface")],
            [],
            SourceHashes() with { UiStyleSnapshotHash = "" },
            styleApplicability: applicability);

        result.Blockers.Should().NotContain(blocker => blocker.DomainCode == "ui_style_snapshot_missing");
        result.Goals.Should().ContainSingle(goal => goal.Style!.StyleNotApplicableDecisionRef == "style-decision-hash");
    }

    [Fact]
    public void Build_ShouldRequireInteractionRegionForOrdinaryMapRequirement()
    {
        var mapRequirement = Requirement("REQ-MAP", "P0", "scene", goalIds: ["goal-1"]) with
        {
            NormalizedRequirement = "Player moves across a field map and selects a path."
        };

        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([mapRequirement]),
            [Goal(1, "Field map navigation")],
            [],
            SourceHashes(),
            styleAuthority: StyleAuthority());

        result.Goals.Should().ContainSingle(goal => goal.InteractionRegion != null);
    }

    [Fact]
    public void Build_ShouldBlockFreeTextModuleSuppressionWithoutAdminEvidence()
    {
        var result = IterationPlanTraceabilityBuilder.Build(
            RequirementMap([Requirement("REQ-001", "P1", "scene", goalIds: ["goal-1"])]),
            [Goal(1, "Field movement")],
            [Module("reward_panel") with { Status = "skipped_by_explicit_gdd_conflict" }],
            SourceHashes(),
            styleAuthority: StyleAuthority());

        result.Blockers.Should().Contain(blocker => blocker.DomainCode == "admin_decision_evidence_missing");
    }

    private static GameDesignRequirementMapResult RequirementMap(IReadOnlyList<GameDesignRequirementRow> requirements)
    {
        return new GameDesignRequirementMapResult(
            "project-1",
            "ready",
            "gdd-hash",
            "scene-hash",
            "requirement-map-hash",
            "contract-snapshot-hash",
            "godot-ui-capability.v1",
            "godot-ui-hash",
            new GameDesignRequirementCoverageSummary(requirements.Count, requirements.Count, 0, 0, 0, 0),
            requirements,
            [],
            [],
            "2026-07-11T00:00:00Z",
            "returned_existing");
    }

    private static GameDesignRequirementRow Requirement(
        string id,
        string priority,
        string kind,
        IReadOnlyList<string>? goalIds = null,
        IReadOnlyList<string>? moduleIds = null)
    {
        return new GameDesignRequirementRow(
            id,
            "Core Loop",
            $"Requirement {id}",
            "en",
            "summary_only",
            $"Requirement {id}",
            priority,
            kind,
            ["field_map"],
            moduleIds ?? [],
            goalIds ?? [],
            "mapped",
            "",
            "",
            "",
            "",
            "",
            "",
            [],
            ["acceptance"]);
    }

    private static PrototypeIterationPlanGoalResult Goal(int index, string title)
    {
        return new PrototypeIterationPlanGoalResult(index, title, title, "acceptance", "pending");
    }

    private static PrototypeIterationPlanRequiredModuleResult Module(string id)
    {
        return new PrototypeIterationPlanRequiredModuleResult(id, "route_strategy", "required", "explicit_conflict", [], null);
    }

    private static PrototypeIterationPlanSourceHashes SourceHashes()
    {
        return new PrototypeIterationPlanSourceHashes(
            "gdd-hash",
            "scene-hash",
            "requirement-map-hash",
            "contract-hash",
            "contract-snapshot-hash",
            "godot-ui-hash",
            "ui-style-contract-hash",
            "ui-style-snapshot-hash");
    }

    private static PrototypeIterationStyleAuthority StyleAuthority()
    {
        return new PrototypeIterationStyleAuthority(
            "godot_cosmic",
            "1",
            "ui-style-snapshot-hash",
            "docs/ui-style-guides/godot-cosmic.md",
            ["cosmic", "deckbuilder"],
            ["layered panels", "gold primary CTA"],
            ["Button", "PanelContainer"],
            ["combat_hud", "reward_panel"]);
    }
}
