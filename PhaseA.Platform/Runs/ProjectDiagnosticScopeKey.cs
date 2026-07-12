using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Runs;

internal static class ProjectDiagnosticScopeKey
{
    public static string Compute(string sourceHashRef, string planHash = "")
    {
        var stableSource = string.IsNullOrWhiteSpace(sourceHashRef) ? "no-source" : sourceHashRef.Trim();
        var stablePlan = string.IsNullOrWhiteSpace(planHash) ? "no-plan" : planHash.Trim();
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes($"{stableSource}\n{stablePlan}")))
            .ToLowerInvariant();
    }
}
