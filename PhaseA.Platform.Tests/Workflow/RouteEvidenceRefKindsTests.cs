using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Workflow;
using Xunit;

namespace PhaseA.Platform.Tests.Workflow;

public sealed class RouteEvidenceRefKindsTests
{
    [Fact]
    public void Fixture_ShouldMatchRuntimeKindsAndStandards()
    {
        using var document = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "Fixtures", "evidence-ref-kind.v1.json")));
        var fixtureValues = document.RootElement.GetProperty("values")
            .EnumerateArray()
            .Select(item => item.GetString())
            .ToArray();

        fixtureValues.Should().BeEquivalentTo(RouteEvidenceRefKinds.Values);

        var repositoryRoot = FindRepositoryRoot();
        var standards = File.ReadAllText(Path.Combine(repositoryRoot, "docs", "standards", "phase-service.md"));
        foreach (var kind in RouteEvidenceRefKinds.Values)
        {
            standards.Should().Contain($"`{kind}`");
        }
    }

    private static string FindRepositoryRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "docs", "standards", "phase-service.md")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new DirectoryNotFoundException("Could not locate repository root.");
    }
}
