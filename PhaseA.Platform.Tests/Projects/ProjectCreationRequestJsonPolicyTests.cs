using System.Text.Json;
using FluentAssertions;
using PhaseA.Platform.Projects;
using Xunit;

namespace PhaseA.Platform.Tests.Projects;

public sealed class ProjectCreationRequestJsonPolicyTests
{
    [Theory]
    [InlineData("""{"gameName":"Demo","gameTypeSource":"manual","git_url":"https://example.com/repo.git"}""")]
    [InlineData("""{"gameName":"Demo","gameTypeSource":"manual","repositoryUrl":"https://example.com/repo.git"}""")]
    [InlineData("""{"gameName":"Demo","gameTypeSource":"manual","remote_url":"https://example.com/repo.git"}""")]
    public void ContainsForbiddenGitUrl_ReturnsTrue_ForBrowserProvidedGitFields(string json)
    {
        using var document = JsonDocument.Parse(json);

        var result = ProjectCreationRequestJsonPolicy.ContainsForbiddenGitUrl(document.RootElement);

        result.Should().BeTrue();
    }

    [Fact]
    public void ContainsForbiddenGitUrl_ReturnsFalse_ForAllowedProjectFields()
    {
        using var document = JsonDocument.Parse("""{"gameName":"Demo","gameTypeSource":"manual"}""");

        var result = ProjectCreationRequestJsonPolicy.ContainsForbiddenGitUrl(document.RootElement);

        result.Should().BeFalse();
    }
}
