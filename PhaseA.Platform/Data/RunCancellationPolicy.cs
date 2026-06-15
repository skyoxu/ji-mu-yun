namespace PhaseA.Platform.Data;

public static class RunCancellationPolicy
{
    private static readonly HashSet<string> BlockedRunTypes = new(StringComparer.OrdinalIgnoreCase)
    {
        "chapter2-bootstrap",
        "project-creation",
        "project-asset-generation",
        "asset-generation"
    };

    public static bool IsCancellationBlocked(string? runType)
    {
        return !string.IsNullOrWhiteSpace(runType) && BlockedRunTypes.Contains(runType.Trim());
    }
}
