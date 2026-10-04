using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

// ADR-0036/0038: current validated inputs, not an additional executable workflow.
public sealed class ProjectBusinessChainStatusTests
{
    [Fact]
    public void RestoredFilesRequireAcceptanceEvenWhenTheHistoricalChainWasGreen()
    {
        var (routes, steps) = Complete();
        Assert.Equal("passed", ProjectBusinessChainStatus.Evaluate(routes, steps, false).Status);
        var restored = ProjectBusinessChainStatus.Evaluate(routes, steps, true);
        Assert.Equal("blocked", restored.Status);
        Assert.Contains("workspace:restore_revalidation_required", restored.BlockingReasons);
        Assert.False(restored.RoutesExecuted);
    }

    [Theory]
    [InlineData("stale-contract")]
    [InlineData("missing-package")]
    [InlineData("duplicate-ui")]
    [InlineData("repair-open")]
    public void LocalAcceptanceDoesNotDischargeCrossStageFailures(string fault)
    {
        var (routes, steps) = Complete();
        if (fault == "stale-contract")
            routes = routes with { Artifacts = routes.Artifacts.Select(item => item.Route == "prototype-contract" ? item with { Freshness = "stale" } : item).ToArray() };
        if (fault == "missing-package") steps = steps.Where(step => step.Id != "preview-package").ToArray();
        if (fault == "duplicate-ui") routes = routes with { Artifacts = routes.Artifacts.Append(routes.Artifacts.Last()).ToArray() };
        if (fault == "repair-open") steps = steps.Append(new("needs-fix-or-repair", "Repair", "fix", "open diagnosis")).ToArray();
        Assert.Equal("blocked", ProjectBusinessChainStatus.Evaluate(routes, steps, false).Status);
    }

    private static (ProjectRouteStateArtifactReadback, IReadOnlyList<ProjectWorkflowRouteStep>) Complete()
    {
        var hash = new string('a', 64);
        var routes = new[] { "gdd-question-form", "scene-route-confirmation", "gdd-document-generation", "gdd-requirements", "prototype-contract", "prototype-skeleton", "ui-wiring" }
            .Select(route => new ProjectRouteStateArtifactSummary(route, "meta/current.json", null, "authority",
                route == "ui-wiring" ? "succeeded" : "ready", "readback", ["ready", "succeeded"], "fresh", [],
                SourceRequirementMapHash: hash, SourceGodotUiContractHash: hash, SourceUiStyleContractHash: hash,
                UiStyleSnapshotHash: hash, SourceIterationSessionHash: hash, SourceValidationInputHash: hash, SourceContractHash: hash)).ToArray();
        var steps = new[] { "iteration-plan", "module-execution", "prototype-acceptance", "preview-package" }
            .Select(id => new ProjectWorkflowRouteStep(id, id, "done", "current machine evidence")).ToArray();
        return (new("ready", "current", routes, []), steps);
    }
}
