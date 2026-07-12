using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class RouteModuleContractsTests
{
    [Fact]
    public void Fixture_ShouldMatchRuntimeContractRegistry()
    {
        using var document = ReadFixture();
        var root = document.RootElement;

        root.GetProperty("contractSetId").GetString().Should().Be(RouteModuleContracts.ContractSetId);
        root.GetProperty("contractSetVersion").GetString().Should().Be(RouteModuleContracts.ContractSetVersion);
        root.GetProperty("contractSetHash").GetString().Should().Be(RouteModuleContracts.ContractSetHash);
        root.GetProperty("recoverySourceOrderRef").GetString().Should().Be(RouteModuleContracts.RecoverySourceOrderRef);

        var fixtureContracts = root.GetProperty("contracts").EnumerateArray().ToArray();
        fixtureContracts.Select(contract => contract.GetProperty("routeId").GetString())
            .Should()
            .BeEquivalentTo(RouteModuleContracts.All.Select(contract => contract.RouteId));

        foreach (var runtime in RouteModuleContracts.All)
        {
            var fixture = fixtureContracts.Single(contract => contract.GetProperty("routeId").GetString() == runtime.RouteId);
            fixture.GetProperty("owner").GetString().Should().Be(runtime.Owner);
            fixture.GetProperty("canonicalRouteStatePath").GetString().Should().Be(runtime.CanonicalRouteStatePath);
            ReadNullableString(fixture, "mirrorRouteStatePath").Should().Be(runtime.MirrorRouteStatePath);
            fixture.GetProperty("promptSourceBoundaryRequired").GetBoolean().Should().Be(runtime.PromptSourceBoundaryRequired);
            fixture.GetProperty("recoverySourceOrderRef").GetString().Should().Be(runtime.RecoverySourceOrderRef);
            fixture.GetProperty("actionIds").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.ActionIds);
            fixture.GetProperty("apiRoutes").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.ApiRoutes);
            fixture.GetProperty("browserEntrypoints").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.BrowserEntrypoints);
            fixture.GetProperty("requiredSourceArtifacts").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.RequiredSourceArtifacts);
            fixture.GetProperty("sourceHashFields").EnumerateArray().Select(item => item.GetString()).Should().BeEquivalentTo(runtime.SourceHashFields);
            fixture.GetProperty("statusDimension").GetString().Should().Be(runtime.StatusDimension);
            fixture.GetProperty("exposureClass").GetString().Should().Be(runtime.ExposureClass);
            fixture.GetProperty("phaseEligibility").GetString().Should().Be(runtime.PhaseEligibility);
        }
    }

    [Fact]
    public void Contracts_ShouldCoverInitialRouteSetAndUseDescriptorActions()
    {
        RouteModuleContracts.All.Select(contract => contract.RouteId).Should().Contain([
            "gdd-requirements",
            "gdd-document-generation",
            "scene-route-confirmation",
            "structured-game-type-analysis",
            "prototype-contract",
            "prototype-skeleton-guard",
            "workflow-recommendation",
            "ui-wiring-closure",
            "iteration-plan",
            "execute-next-goal",
            "needs-fix",
            "repair",
            "preview-package",
            "project-delete"
        ]);

        foreach (var contract in RouteModuleContracts.All)
        {
            contract.ActionIds.Should().NotBeEmpty($"{contract.RouteId} must declare descriptor mapping");
            contract.ActionIds.Should().OnlyContain(action => RouteActionDescriptors.CanonicalActionIds.Contains(action));
            RouteStatusVocabulary.IsKnownDimension(contract.StatusDimension).Should().BeTrue($"{contract.RouteId} must use a known status dimension");
            contract.ApiRoutes.Should().NotBeEmpty($"{contract.RouteId} must declare API/readback projection");
            contract.BrowserEntrypoints.Should().NotBeEmpty($"{contract.RouteId} must declare browser entrypoints or display mapping");
            contract.SourceHashFields.Should().NotBeEmpty($"{contract.RouteId} must declare source hash fields");
            contract.AdminReadbackSurfaces.Should().Contain("workflow recommendation readback");
        }
    }

    [Fact]
    public void Phase1Contracts_ShouldUseCanonicalSkeletonGuardAndResolveLegacyAlias()
    {
        var phase1Routes = new[]
        {
            "structured-game-type-analysis",
            "scene-route-confirmation",
            "gdd-document-generation",
            "gdd-requirements",
            "prototype-contract",
            "prototype-skeleton-guard"
        };

        RouteModuleContracts.All.Select(item => item.RouteId).Should().Contain(phase1Routes);
        RouteModuleContracts.All.Select(item => item.RouteId).Should().NotContain("prototype-skeleton");
        RouteModuleContracts.Find("prototype-skeleton").Should().BeSameAs(RouteModuleContracts.Find("prototype-skeleton-guard"));
        RouteModuleContracts.Find("prototype-skeleton-guard")!.SourceHashFields.Should().Contain([
            "source_contract_hash",
            "source_scene_route_hash",
            "source_requirement_map_hash",
            "source_godot_ui_contract_hash",
            "source_ui_style_contract_hash",
            "ui_style_snapshot_hash"
        ]);
    }

    [Fact]
    public void IterationPlanContract_ShouldDeclareCompletePhase2AuthorityBoundary()
    {
        var contract = RouteModuleContracts.Find("iteration-plan");

        contract.Should().NotBeNull();
        contract!.PhaseEligibility.Should().Be("active");
        contract.ApiRoutes.Should().Contain([
            "/api/projects/{projectId}/iteration-plan",
            "/api/projects/{projectId}/iteration-plan/latest",
            "/api/projects/{projectId}/iteration-plan/confirm",
            "/api/projects/{projectId}/iteration-plans",
            "/api/projects/{projectId}/iteration-plan/evaluate"
        ]);
        contract.RequiredSourceArtifacts.Should().Contain([
            "docs/gdd/GDD.md",
            "meta/routes/scene-route/latest.json",
            "meta/routes/gdd-requirements/latest.json",
            "routes/prototype-contract/latest.json",
            "meta/routes/prototype-skeleton/latest.json",
            "meta/routes/godot-ui-contract/latest.json",
            "meta/routes/ui-style-contract/latest.json",
            "meta/routes/ui-style-snapshot/latest.json"
        ]);
        contract.SourceHashFields.Should().BeEquivalentTo([
            "source_gdd_hash",
            "source_scene_route_hash",
            "source_requirement_map_hash",
            "source_contract_hash",
            "source_contract_snapshot_hash",
            "source_godot_ui_contract_hash",
            "source_ui_style_contract_hash",
            "ui_style_snapshot_hash"
        ]);
        contract.AdminReadbackSurfaces.Should().Contain(["admin review queue", "diagnostic spool"]);
        contract.DeterministicTestOwners.Should().Contain([
            "PhaseA.Platform.Tests/Runs",
            "PhaseA.Platform.Tests/Workflow",
            "PhaseA.Platform.Tests/Browser"
        ]);
    }

    [Fact]
    public void PromptProducingContracts_ShouldInheritHostedRecoverySourceOrder()
    {
        RouteModuleContracts.All
            .Where(contract => contract.PromptSourceBoundaryRequired)
            .Should()
            .OnlyContain(contract =>
                contract.RecoverySourceOrderRef == RouteModuleContracts.RecoverySourceOrderRef &&
                contract.RequiredSourceArtifacts.Count > 0 &&
                contract.SourceHashFields.Count > 0);

        RouteModuleContracts.All
            .Where(contract => !contract.PromptSourceBoundaryRequired)
            .Should()
            .OnlyContain(contract => contract.RecoverySourceOrderRef == "source_boundary_not_applicable");
    }

    [Fact]
    public void PrototypeContract_ShouldUseCanonicalPathAndMirrorOnlyAsReadbackCache()
    {
        var contract = RouteModuleContracts.Find("prototype-contract");

        contract.Should().NotBeNull();
        contract!.CanonicalRouteStatePath.Should().Be("routes/prototype-contract/latest.json");
        contract.MirrorRouteStatePath.Should().Be("meta/routes/prototype-contract/latest.json");
        contract.SourceHashFields.Should().Contain("contract_hash");
        contract.ActionIds.Should().Contain(["freeze_contract", "refresh_contract"]);
    }

    private static JsonDocument ReadFixture()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "Fixtures", "route-module-contracts.v1.json");
        return JsonDocument.Parse(File.ReadAllText(path));
    }

    private static string? ReadNullableString(JsonElement element, string propertyName)
    {
        var property = element.GetProperty(propertyName);
        return property.ValueKind == JsonValueKind.Null ? null : property.GetString();
    }
}
