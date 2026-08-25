namespace PhaseA.Platform.Security;

public sealed record RunnerLease(string LeaseId, string AccountId, string ProjectId, long Fence);

public sealed record RunnerIsolationDescriptor(
    string AccountId,
    string ProjectId,
    string OsIdentity,
    string WorkspaceRoot,
    bool LowPrivilegeRequired,
    bool JobObjectRequired,
    bool NtfsAclRequired);

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
        RequireNoReparsePoint(fullRoot, candidate);
        return candidate;
    }

    public static void RequireNoReparsePoint(string root, string candidate)
    {
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar);
        var fullCandidate = Path.GetFullPath(candidate);
        var relative = Path.GetRelativePath(fullRoot, fullCandidate);
        var current = fullRoot;
        foreach (var segment in relative.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar, StringSplitOptions.RemoveEmptyEntries))
        {
            current = Path.Combine(current, segment);
            if (Directory.Exists(current) && (File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                throw new UnauthorizedAccessException("runner path contains a reparse point");
            if (File.Exists(current) && (File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                throw new UnauthorizedAccessException("runner path contains a reparse point");
        }
    }

    public static RunnerIsolationDescriptor Describe(string accountId, string projectId, string workspaceRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceRoot);
        return new RunnerIsolationDescriptor(
            accountId,
            projectId,
            $"phase-runner:{accountId}:{projectId}",
            Path.GetFullPath(workspaceRoot),
            LowPrivilegeRequired: true,
            JobObjectRequired: OperatingSystem.IsWindows(),
            NtfsAclRequired: OperatingSystem.IsWindows());
    }

    public static void DemandCurrentLease(RunnerLease expected, RunnerLease actual)
    {
        if (expected.LeaseId != actual.LeaseId || expected.AccountId != actual.AccountId || expected.ProjectId != actual.ProjectId || expected.Fence != actual.Fence)
            throw new InvalidOperationException("stale runner lease");
    }
}
