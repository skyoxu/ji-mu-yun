using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class RouteFreshnessPolicyTests
{
    [Fact]
    public void Edges_ShouldNameCriticalGddToModuleInvalidationChain()
    {
        RouteFreshnessPolicy.IsKnownEdge("docs/gdd/GDD.md", "meta/routes/gdd-requirements/latest.json", "source_gdd_hash").Should().BeTrue();
        RouteFreshnessPolicy.IsKnownEdge("meta/routes/scene-route/latest.json", "meta/routes/gdd-requirements/latest.json", "source_scene_route_hash").Should().BeTrue();
        RouteFreshnessPolicy.IsKnownEdge("meta/routes/gdd-requirements/latest.json", "routes/prototype-contract/latest.json", "source_requirement_map_hash").Should().BeTrue();
        RouteFreshnessPolicy.IsKnownEdge("routes/prototype-contract/latest.json", "meta/routes/iteration-plan/latest.json", "source_contract_hash").Should().BeTrue();
        RouteFreshnessPolicy.IsKnownEdge("metadata:project_admin_review_queue", "meta/routes/workflow-recommendation/latest.json", "admin_review_queue_updated_utc").Should().BeTrue();
        RouteFreshnessPolicy.IsKnownEdge("metadata:project_diagnostic_spool", "meta/routes/workflow-recommendation/latest.json", "diagnostic_spool_updated_utc").Should().BeTrue();
    }

    [Fact]
    public void RouteModuleContractSourceHashes_ShouldHaveFreshnessEdgesForDownstreamArtifacts()
    {
        foreach (var contract in RouteModuleContracts.All.Where(contract => contract.CanonicalRouteStatePath.StartsWith("meta/routes/", StringComparison.Ordinal) || contract.CanonicalRouteStatePath.StartsWith("routes/", StringComparison.Ordinal)))
        {
            foreach (var sourceHashField in contract.SourceHashFields.Where(field => field.StartsWith("source_", StringComparison.Ordinal)))
            {
                var hasEdge = RouteFreshnessPolicy.ForTarget(contract.CanonicalRouteStatePath)
                    .Any(edge => edge.HashField == sourceHashField);
                if (contract.RouteId is "scene-route-confirmation" or "gdd-document-generation" or "repair" or "needs-fix")
                {
                    continue;
                }

                hasEdge.Should().BeTrue($"{contract.RouteId} declares {sourceHashField} and must name an invalidation edge");
            }
        }
    }

    [Fact]
    public void IterationPlan_ShouldNameEveryFrozenAuthorityFreshnessEdge()
    {
        var edges = RouteFreshnessPolicy.ForTarget("meta/routes/iteration-plan/latest.json");

        edges.Select(edge => edge.HashField).Should().BeEquivalentTo([
            "source_gdd_hash",
            "source_scene_route_hash",
            "source_requirement_map_hash",
            "source_contract_hash",
            "source_contract_snapshot_hash",
            "source_godot_ui_contract_hash",
            "source_ui_style_contract_hash",
            "ui_style_snapshot_hash"
        ]);
    }
}
