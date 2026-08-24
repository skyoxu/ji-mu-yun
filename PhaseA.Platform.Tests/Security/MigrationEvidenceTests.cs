using FluentAssertions;
using PhaseA.Platform.Data;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB;

public sealed class MigrationEvidenceTests
{
    [Fact]
    public void Redacted_RemovesCredentialFieldsAndPreservesOwnershipCorrelation()
    {
        var evidence = new MigrationEvidence(
            "op-1", "account-1", "project-1", "completed", "corr-1",
            new Dictionary<string, string> { ["rows"] = "2", ["access_token"] = "secret" });

        var safe = evidence.Redacted();

        safe.AccountId.Should().Be("account-1");
        safe.ProjectId.Should().Be("project-1");
        safe.CorrelationId.Should().Be("corr-1");
        safe.Fields.Should().ContainKey("rows").And.NotContainKey("access_token");
    }
}
