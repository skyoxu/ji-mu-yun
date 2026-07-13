using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class RouteStatusVocabularyTests
{
    [Fact]
    public void Fixture_ShouldMatchRuntimeVocabulary()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "Fixtures", "route-status-vocabulary.v1.json");
        using var document = JsonDocument.Parse(File.ReadAllText(path));
        var dimensions = document.RootElement.GetProperty("dimensions");

        dimensions.EnumerateObject().Select(property => property.Name)
            .Should()
            .BeEquivalentTo(RouteStatusVocabulary.AllDimensions.Keys);

        foreach (var dimension in RouteStatusVocabulary.AllDimensions)
        {
            dimensions.GetProperty(dimension.Key)
                .EnumerateArray()
                .Select(item => item.GetString())
                .Should()
                .BeEquivalentTo(dimension.Value);
        }
    }

    [Theory]
    [InlineData("succeeded", true, "completed")]
    [InlineData("succeeded", false, "ready")]
    [InlineData("covered", true, "blocked")]
    [InlineData("blocked", true, "blocked")]
    public void MapRouteReadbackToStageTimeline_ShouldKeepDimensionsSeparate(string routeStatus, bool validatedArtifact, string expected)
    {
        RouteStatusVocabulary.MapRouteReadbackToStageTimeline(routeStatus, validatedArtifact).Should().Be(expected);
    }

    [Fact]
    public void AdminReviewQueuePolicy_ShouldMatchCentralVocabularyAndBlockingSemantics()
    {
        ProjectAdminReviewQueuePolicy.PersistedStatuses
            .Should()
            .BeEquivalentTo(RouteStatusVocabulary.Values(RouteStatusVocabulary.AdminReviewQueue));
        ProjectAdminReviewQueuePolicy.InputStatuses.Should().NotContain("superseded");
        ProjectAdminReviewQueuePolicy.DecisionStatuses.Should().NotContain(["open", "superseded"]);
        new[] { "open", "rejected", "backlog" }
            .Should().OnlyContain(status => ProjectAdminReviewQueuePolicy.IsBlocking(status));
        new[] { "approved", "deferred", "resolved", "superseded" }
            .Should().OnlyContain(status => !ProjectAdminReviewQueuePolicy.IsBlocking(status));
    }

    [Fact]
    public void AdminReviewQueuePolicy_ShouldReopenExpiredOrOutOfScopeDeferredEntries()
    {
        var now = DateTimeOffset.Parse("2026-07-12T12:00:00Z");
        var active = DeferredEntry("2099-01-01T00:00:00Z", "gdd-requirements");
        var expired = DeferredEntry("2026-07-12T11:59:59Z", "gdd-requirements");
        var unrelated = DeferredEntry("2099-01-01T00:00:00Z", "prototype-contract");

        ProjectAdminReviewQueuePolicy.IsBlocking(active, now).Should().BeFalse();
        ProjectAdminReviewQueuePolicy.IsCleared(active, now).Should().BeTrue();
        ProjectAdminReviewQueuePolicy.IsBlocking(expired, now).Should().BeTrue();
        ProjectAdminReviewQueuePolicy.IsCleared(expired, now).Should().BeFalse();
        ProjectAdminReviewQueuePolicy.IsBlocking(unrelated, now).Should().BeTrue();
    }

    private static ProjectAdminReviewQueueEntry DeferredEntry(string untilUtc, string affectedRoute)
    {
        return new ProjectAdminReviewQueueEntry(
            "entry", "account", "project", "gdd-requirements", "REQ-001", "P1", "reason", "source", "[]",
            "deferred", "deferred", "admin", "reason",
            $$"""{"deferred_owner":"platform","recheck_trigger":"timer","deferred_until_utc":"{{untilUtc}}","affected_routes":["{{affectedRoute}}"]}""",
            1, "2026-07-12T00:00:00Z", "2026-07-12T00:00:00Z", "2026-07-12T00:00:00Z", null, null, null);
    }
}
