using System.Text;
using System.Text.Json;
using PhaseA.Platform.Workspaces;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S3BoundaryTests
{
    private const string PlaintextKeyFixture = "fixture-plaintext-key-not-for-production";
    private readonly ITestOutputHelper _output;

    public S3BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public void O_6578750F6BE9()
    {
        var manifest = SnapshotManifest.Create(
            "snapshot-s3",
            "workspace-s3",
            "account-s3",
            "project-s3",
            "policy-s3",
            new[] { ("src/main.cs", Encoding.UTF8.GetBytes("snapshot content")) });
        var serializedManifest = JsonSerializer.Serialize(manifest);
        using var document = JsonDocument.Parse(serializedManifest);

        var containsPlaintextKeyMaterial =
            !manifest.KeyReference.StartsWith("keyref-", StringComparison.Ordinal)
            || manifest.KeyReference.Contains(PlaintextKeyFixture, StringComparison.Ordinal)
            || ContainsPlaintextKeyField(document.RootElement)
            || serializedManifest.Contains(PlaintextKeyFixture, StringComparison.Ordinal);

        Require(
            !containsPlaintextKeyMaterial,
            "FAILURE-O-6578750F6BE9",
            "Published Snapshot manifest contained plaintext encryption key material.");
        _output.WriteLine("S3-OBSERVATION O_6578750F6BE9 manifest-has-no-plaintext-key-material");
    }

    private static bool ContainsPlaintextKeyField(JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            foreach (var property in element.EnumerateObject())
            {
                if (property.Name.Contains("key", StringComparison.OrdinalIgnoreCase)
                    && !string.Equals(property.Name, "KeyReference", StringComparison.OrdinalIgnoreCase))
                    return true;
                if (ContainsPlaintextKeyField(property.Value))
                    return true;
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in element.EnumerateArray())
            {
                if (ContainsPlaintextKeyField(item))
                    return true;
            }
        }

        return false;
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
    }
}
