using FluentAssertions;
using PhaseA.Platform.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Data;

public sealed class HostedContextManifestSignatureServiceTests
{
    [Fact]
    public void Verify_ShouldAcceptPrimaryAndRetainedRotationKeys()
    {
        var service = new HostedContextManifestSignatureService("key-2", new Dictionary<string, string>
        {
            ["key-1"] = "retained-secret",
            ["key-2"] = "primary-secret"
        });
        var unsigned = CreateRecord() with { KeyId = "key-1" };
        var retained = new HostedContextManifestSignatureService("key-1", new Dictionary<string, string>
        {
            ["key-1"] = "retained-secret"
        }).Sign(unsigned);
        var primary = service.Sign(CreateRecord());

        service.Verify(retained).Should().BeTrue();
        service.Verify(primary).Should().BeTrue();
        service.Verify(primary with { SnapshotId = "snapshot-2" }).Should().BeFalse();
        service.Verify(primary with { KeyId = "unknown" }).Should().BeFalse();
    }

    private static HostedContextManifestRecord CreateRecord()
    {
        return new HostedContextManifestRecord(
            "manifest-1", "account-1", "project-1", "llm:operation-1", "snapshot-1", "policy-1", "", "", "nonce-1",
            "2026-07-26T00:05:00.0000000+00:00", "2026-07-26T00:00:00.0000000+00:00");
    }
}
