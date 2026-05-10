using FluentAssertions;
using Xunit;

namespace PhaseA.Platform.Tests.Security;

public sealed class DeploymentDocsTests
{
    [Fact]
    public void PhaseACaddyDeploymentDoc_IncludesRequiredHardeningRules()
    {
        var repoRoot = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        var doc = File.ReadAllText(Path.Combine(repoRoot, "docs", "workflows", "phase-a-caddy-deployment.md"));

        doc.Should().Contain("APP_BIND_URL = \"http://127.0.0.1:8080\"");
        doc.Should().Contain("reverse_proxy 127.0.0.1:8080");
        doc.Should().Contain("Authorization: Bearer");
        doc.Should().Contain("return `401` without auth");
        doc.Should().Contain("Do not store upstream provider API keys");
    }
}
