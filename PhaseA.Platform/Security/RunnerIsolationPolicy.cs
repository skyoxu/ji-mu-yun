namespace PhaseA.Platform.Security;

using System.Diagnostics;
using System.Runtime.InteropServices;

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
    public static RunnerIsolationHandle PrepareWorkspace(RunnerIsolationDescriptor descriptor)
    {
        ArgumentNullException.ThrowIfNull(descriptor);
        Directory.CreateDirectory(descriptor.WorkspaceRoot);
        RequireNoReparsePoint(descriptor.WorkspaceRoot, descriptor.WorkspaceRoot);
        if (OperatingSystem.IsWindows())
        {
            var user = Environment.UserName;
            var acl = Process.Start(new ProcessStartInfo("icacls", $"\"{descriptor.WorkspaceRoot}\" /inheritance:r /grant:r \"{user}:(OI)(CI)M\"") { UseShellExecute = false, CreateNoWindow = true });
            acl!.WaitForExit();
            if (acl.ExitCode != 0) throw new UnauthorizedAccessException("runner NTFS ACL could not be applied");
        }
        var marker = Path.Combine(descriptor.WorkspaceRoot, ".runner-isolation.json");
        File.WriteAllText(marker, $"{{\"accountId\":\"{descriptor.AccountId}\",\"projectId\":\"{descriptor.ProjectId}\",\"lowPrivilegeRequired\":{descriptor.LowPrivilegeRequired.ToString().ToLowerInvariant()},\"jobObjectRequired\":{descriptor.JobObjectRequired.ToString().ToLowerInvariant()},\"ntfsAclRequired\":{descriptor.NtfsAclRequired.ToString().ToLowerInvariant()}}}\n");
        return new RunnerIsolationHandle(descriptor, marker);
    }

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

public sealed class RunnerIsolationHandle : IDisposable
{
    private nint _job;
    internal RunnerIsolationHandle(RunnerIsolationDescriptor descriptor, string markerPath) { Descriptor = descriptor; MarkerPath = markerPath; }
    public RunnerIsolationDescriptor Descriptor { get; }
    public string MarkerPath { get; }

    public void AttachProcess(Process process)
    {
        ArgumentNullException.ThrowIfNull(process);
        if (!OperatingSystem.IsWindows() || !Descriptor.JobObjectRequired) return;
        _job = CreateJobObject(nint.Zero, $"phase-runner-{Descriptor.AccountId}-{Descriptor.ProjectId}");
        if (_job == nint.Zero || !AssignProcessToJobObject(_job, process.Handle))
            throw new InvalidOperationException("runner process could not be attached to a Job Object");
    }

    public void Dispose()
    {
        if (_job != nint.Zero) { CloseHandle(_job); _job = nint.Zero; }
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern nint CreateJobObject(nint attributes, string? name);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool AssignProcessToJobObject(nint job, nint process);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool CloseHandle(nint handle);
}
