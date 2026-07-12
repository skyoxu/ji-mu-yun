using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace PhaseA.Platform.Runs;

internal static class IterationPlanIntegrity
{
    public static string Compute(string sourceHashRef, object goals, object requiredModules, object blockers, object coverage)
    {
        var payload = JsonSerializer.Serialize(new
        {
            source_hash_ref = sourceHashRef,
            goals,
            required_modules = requiredModules,
            blockers,
            coverage
        });
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(payload))).ToLowerInvariant();
    }

    public static string Compute(JsonElement root)
    {
        if (root.ValueKind != JsonValueKind.Object ||
            !root.TryGetProperty("goals", out var goals) || goals.ValueKind != JsonValueKind.Array ||
            !root.TryGetProperty("required_modules", out var modules) || modules.ValueKind != JsonValueKind.Array ||
            !root.TryGetProperty("blockers", out var blockers) || blockers.ValueKind != JsonValueKind.Array ||
            !root.TryGetProperty("coverage", out var coverage) || coverage.ValueKind != JsonValueKind.Object)
        {
            return "";
        }

        return Compute(ReadString(root, "source_hash_ref"), goals, modules, blockers, coverage);
    }

    private static string ReadString(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? ""
            : "";
    }
}
