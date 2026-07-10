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
            "prototype-skeleton",
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
