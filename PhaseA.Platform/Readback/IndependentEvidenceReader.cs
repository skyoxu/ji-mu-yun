using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Readback;

public sealed record IndependentEvidenceResult(bool Accepted, string Reason, IReadOnlyList<string> CheckedArtifacts);

/// <summary>
/// Validates an A18 evidence package from persisted producer output. The
/// declaration field is informational; acceptance is derived only from the
/// executed marker, current timestamp, producer binding, required artifacts,
/// and content hashes.
/// </summary>
public static class IndependentEvidenceReader
{
    private static readonly string[] RequiredArtifacts = ["snapshot", "permission", "fault", "migration", "redaction"];

    public static IndependentEvidenceResult Validate(string packagePath, string expectedRunId, DateTimeOffset? now = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(packagePath);
        ArgumentException.ThrowIfNullOrWhiteSpace(expectedRunId);
        using var document = JsonDocument.Parse(File.ReadAllText(packagePath, Encoding.UTF8));
        var root = document.RootElement;
        if (!root.TryGetProperty("executed", out var executed) || !executed.GetBoolean())
            return Reject("verification_not_executed");
        if (!root.TryGetProperty("producerRunId", out var producer) ||
            !string.Equals(producer.GetString(), expectedRunId, StringComparison.Ordinal))
            return Reject("producer_run_mismatch");
        if (!root.TryGetProperty("timestamp", out var timestamp) ||
            !DateTimeOffset.TryParse(timestamp.GetString(), out var recorded) ||
            (now ?? DateTimeOffset.UtcNow) - recorded > TimeSpan.FromMinutes(5) || recorded - (now ?? DateTimeOffset.UtcNow) > TimeSpan.FromMinutes(1))
            return Reject("stale_evidence");
        if (!root.TryGetProperty("artifacts", out var artifacts) || artifacts.ValueKind != JsonValueKind.Array)
            return Reject("missing_required_evidence");

        var seen = new HashSet<string>(StringComparer.Ordinal);
        var packageRoot = Path.GetFullPath(Path.GetDirectoryName(packagePath) ?? ".");
        foreach (var artifact in artifacts.EnumerateArray())
        {
            if (!artifact.TryGetProperty("kind", out var kindNode) || !artifact.TryGetProperty("path", out var pathNode) ||
                !artifact.TryGetProperty("content", out var contentNode) ||
                !artifact.TryGetProperty("sha256", out var hashNode))
                return Reject("integrity_failure");
            var kind = kindNode.GetString() ?? string.Empty;
            var relativePath = pathNode.GetString() ?? string.Empty;
            if (string.IsNullOrWhiteSpace(relativePath) || Path.IsPathRooted(relativePath))
                return Reject("integrity_failure");
            var artifactPath = Path.GetFullPath(Path.Combine(packageRoot, relativePath));
            if (!IsWithin(packageRoot, artifactPath) || !File.Exists(artifactPath))
                return Reject("integrity_failure");
            var content = contentNode.GetString() ?? string.Empty;
            var persisted = File.ReadAllText(artifactPath, Encoding.UTF8);
            var expectedHash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(persisted))).ToLowerInvariant();
            if (!seen.Add(kind) ||
                !string.Equals(persisted, content, StringComparison.Ordinal) ||
                !string.Equals(expectedHash, hashNode.GetString(), StringComparison.OrdinalIgnoreCase))
                return Reject("integrity_failure");
        }
        if (RequiredArtifacts.Any(required => !seen.Contains(required)))
            return Reject("missing_required_evidence");
        return new IndependentEvidenceResult(true, "accepted", seen.OrderBy(item => item, StringComparer.Ordinal).ToArray());
    }

    public static IndependentEvidenceResult ValidatePersistedRun(
        RunSnapshot run,
        string packagePath,
        DateTimeOffset? now = null)
    {
        ArgumentNullException.ThrowIfNull(run);
        if (!string.Equals(run.Status, "succeeded", StringComparison.OrdinalIgnoreCase) ||
            string.IsNullOrWhiteSpace(run.FinishedUtc) || string.IsNullOrWhiteSpace(run.EvidenceJson))
            return Reject("run_not_succeeded");
        using var evidence = JsonDocument.Parse(run.EvidenceJson);
        if (!evidence.RootElement.TryGetProperty("producerRunId", out var producer) ||
            !string.Equals(producer.GetString(), run.RunId, StringComparison.Ordinal))
            return Reject("producer_run_mismatch");
        if (!evidence.RootElement.TryGetProperty("independentEvidence", out var independent) ||
            independent.ValueKind != JsonValueKind.Object ||
            !independent.TryGetProperty("executionSource", out var source) ||
            !string.Equals(source.GetString(), "platform-run", StringComparison.Ordinal) ||
            !independent.TryGetProperty("artifacts", out var boundArtifacts) ||
            boundArtifacts.ValueKind != JsonValueKind.Array)
            return Reject("run_evidence_binding_missing");

        var result = Validate(packagePath, run.RunId, now);
        if (!result.Accepted)
            return result;

        using var package = JsonDocument.Parse(File.ReadAllText(packagePath, Encoding.UTF8));
        var packageArtifacts = package.RootElement.GetProperty("artifacts").EnumerateArray()
            .ToDictionary(item => item.GetProperty("kind").GetString() ?? string.Empty, StringComparer.Ordinal);
        var bindings = boundArtifacts.EnumerateArray().ToDictionary(
            item => item.GetProperty("kind").GetString() ?? string.Empty, StringComparer.Ordinal);
        if (bindings.Count != packageArtifacts.Count ||
            packageArtifacts.Any(pair => !bindings.TryGetValue(pair.Key, out var binding) ||
                !string.Equals(binding.GetProperty("path").GetString(), pair.Value.GetProperty("path").GetString(), StringComparison.Ordinal) ||
                !string.Equals(binding.GetProperty("sha256").GetString(), pair.Value.GetProperty("sha256").GetString(), StringComparison.OrdinalIgnoreCase)))
            return Reject("run_evidence_binding_mismatch");
        return result;
    }

    private static IndependentEvidenceResult Reject(string reason) => new(false, reason, []);

    private static bool IsWithin(string root, string path)
    {
        var relative = Path.GetRelativePath(root, path);
        return relative.Length == 0 || (!Path.IsPathRooted(relative) && !relative.StartsWith("..", StringComparison.Ordinal));
    }
}
