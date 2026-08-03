using FluentAssertions;
using PhaseA.Platform.Data;
using System.Text;
using System.Text.Json;
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

    [Fact]
    public void Verify_ShouldBindEveryCanonicalV1PayloadByte()
    {
        var service = new HostedContextManifestSignatureService("key-2", new Dictionary<string, string>
        {
            ["key-2"] = "primary-secret"
        });
        var project = new ProjectSnapshot(
            "project-1", "account-1", "Project", "Game", "test", "template", false, "[]", "ready", null,
            "workspace-1", @"C:\workspace", @"C:\workspace\project", @"C:\workspace\runtime", @"C:\workspace\meta");
        var payload = HostedContextSignedPayloadV1.CreateServerDerived(
            "manifest-v1", project, "llm:project-chat", new string('1', 64), "policy-1",
            "nonce-v1", "2026-07-26T00:00:00Z", "2026-07-26T00:05:00Z", "prompt");
        var signed = service.Sign(HostedContextManifestRecord.FromPayload(payload));

        service.Verify(signed).Should().BeTrue();
        var changed = HostedContextSignedPayloadV1.Parse(
            signed.SignedPayloadJson!.Replace("\"run_id\":\"", "\"run_id\":\"tampered-", StringComparison.Ordinal));
        service.Verify(signed with { SignedPayloadJson = changed.CanonicalJson }).Should().BeFalse();
    }

    [Fact]
    public void Sign_ShouldMatchPlanJcsHmacReferenceVector()
    {
        var repositoryRoot = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        var path = Path.Combine(
            repositoryRoot,
            "execution-plans", "2026-07-25-four-domain-knowledge-context-engineering-plan",
            "fixtures", "reference-vectors", "jcs-hmac-reference-vector.v1.json");
        using var document = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
        var root = document.RootElement;
        var payload = HostedContextSignedPayloadV1.Parse(root.GetProperty("manifest").GetProperty("signed_payload").GetRawText());
        var key = Encoding.UTF8.GetString(Convert.FromBase64String(root.GetProperty("test_key_base64").GetString()!));
        var service = new HostedContextManifestSignatureService("synthetic-test-key-v1", new Dictionary<string, string>
        {
            ["synthetic-test-key-v1"] = key
        });

        var signed = service.Sign(HostedContextManifestRecord.FromPayload(payload));

        signed.SignedPayloadSha256.Should().Be(root.GetProperty("expected_signed_payload_sha256").GetString());
        signed.Signature.Should().Be(root.GetProperty("expected_hmac_base64").GetString());
    }

    private static HostedContextManifestRecord CreateRecord()
    {
        return new HostedContextManifestRecord(
            "manifest-1", "account-1", "project-1", "llm:operation-1", "snapshot-1", "policy-1", "", "", "nonce-1",
            "2026-07-26T00:05:00.0000000+00:00", "2026-07-26T00:00:00.0000000+00:00");
    }
}
