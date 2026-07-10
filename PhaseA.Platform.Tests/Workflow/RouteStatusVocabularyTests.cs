using System.Text.Json;
using FluentAssertions;
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
}
