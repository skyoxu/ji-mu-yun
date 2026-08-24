namespace PhaseA.Platform.Security;

public sealed record RunnerLease(string LeaseId, string AccountId, string ProjectId, long Fence);

public static class RunnerIsolationPolicy
{
    public static string RequireContainedPath(string root, string relativePath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(root);
        ArgumentException.ThrowIfNullOrWhiteSpace(relativePath);
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var candidate = Path.GetFullPath(Path.Combine(root, relativePath));
        if (!candidate.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase))
            throw new UnauthorizedAccessException("runner path escapes project root");
        return candidate;
    }

    public static void DemandCurrentLease(RunnerLease expected, RunnerLease actual)
    {
        if (expected.LeaseId != actual.LeaseId || expected.AccountId != actual.AccountId || expected.ProjectId != actual.ProjectId || expected.Fence != actual.Fence)
            throw new InvalidOperationException("stale runner lease");
    }
}
