namespace PhaseA.Platform.Security;

using PhaseA.Platform.Data;
using System.Collections.Concurrent;
using System.ComponentModel;
using System.Diagnostics;
using System.Security.Principal;
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
    private static readonly ConcurrentDictionary<string, RunnerIsolationDescriptor> Workspaces = new(StringComparer.OrdinalIgnoreCase);
    private static readonly ConcurrentDictionary<string, string> WorkspaceSecurityDescriptors = new(StringComparer.OrdinalIgnoreCase);
    private const uint OwnerSecurityInformation = 0x00000001;
    private const uint GroupSecurityInformation = 0x00000002;
    private const uint DaclSecurityInformation = 0x00000004;
    private const uint SecurityInformation = OwnerSecurityInformation | GroupSecurityInformation | DaclSecurityInformation;
    private const uint SeFileObject = 1;

    public static RunnerIsolationHandle PrepareWorkspace(RunnerIsolationDescriptor descriptor)
    {
        ArgumentNullException.ThrowIfNull(descriptor);
        Directory.CreateDirectory(descriptor.WorkspaceRoot);
        RequireNoReparsePoint(descriptor.WorkspaceRoot, descriptor.WorkspaceRoot);
        if (OperatingSystem.IsWindows())
        {
            var runnerSid = ResolveSid(descriptor.OsIdentity);
            RunIcacls(descriptor.WorkspaceRoot, "/reset");
            RunIcacls(descriptor.WorkspaceRoot, "/setowner \"BUILTIN\\Administrators\"");
            RunIcacls(descriptor.WorkspaceRoot, $"/inheritance:r /grant:r \"*S-1-5-32-544:(OI)(CI)F\" \"*{runnerSid}:(OI)(CI)M\"");
        }
        var marker = Path.Combine(descriptor.WorkspaceRoot, ".runner-isolation.json");
        File.WriteAllText(marker, $"{{\"accountId\":\"{descriptor.AccountId}\",\"projectId\":\"{descriptor.ProjectId}\",\"lowPrivilegeRequired\":{descriptor.LowPrivilegeRequired.ToString().ToLowerInvariant()},\"jobObjectRequired\":{descriptor.JobObjectRequired.ToString().ToLowerInvariant()},\"ntfsAclRequired\":{descriptor.NtfsAclRequired.ToString().ToLowerInvariant()}}}\n");
        var normalized = descriptor with { WorkspaceRoot = Path.GetFullPath(descriptor.WorkspaceRoot) };
        Workspaces[normalized.WorkspaceRoot] = normalized;
        if (OperatingSystem.IsWindows())
        {
            WorkspaceSecurityDescriptors[normalized.WorkspaceRoot] = ReadSecurityDescriptor(normalized.WorkspaceRoot);
        }
        return new RunnerIsolationHandle(normalized, marker);
    }

    public static bool TryGetWorkspaceDescriptor(string workingDirectory, out RunnerIsolationDescriptor descriptor)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workingDirectory);
        var candidate = Path.GetFullPath(workingDirectory).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        foreach (var entry in Workspaces.OrderByDescending(item => item.Key.Length))
        {
            var root = entry.Key.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            if (candidate.Equals(root, StringComparison.OrdinalIgnoreCase) || candidate.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            {
                descriptor = entry.Value;
                return true;
            }
        }
        descriptor = null!;
        return false;
    }

    public static RunnerIsolationHandle CreateProcessIsolation(RunnerIsolationDescriptor descriptor) => new(descriptor, string.Empty);

    public static bool HasExpectedWorkspaceSecurity(RunnerIsolationDescriptor descriptor)
    {
        ArgumentNullException.ThrowIfNull(descriptor);
        if (!OperatingSystem.IsWindows()) return true;

        var root = Path.GetFullPath(descriptor.WorkspaceRoot);
        if (!WorkspaceSecurityDescriptors.TryGetValue(root, out var expected))
        {
            PhaseAMetadataStore.TryRecordRegisteredBoundaryDiagnostic(
                root,
                "acl_invalid",
                "Workspace security policy rejected the operation.");
            return false;
        }
        try
        {
            return string.Equals(expected, ReadSecurityDescriptor(root), StringComparison.Ordinal);
        }
        catch (Exception)
        {
            return false;
        }
    }

    public static string CredentialTarget(RunnerIsolationDescriptor descriptor) => $"PhaseA.Runner.{descriptor.AccountId}.{descriptor.ProjectId}";

    private static void RunIcacls(string workspaceRoot, string arguments)
    {
        using var process = Process.Start(new ProcessStartInfo("icacls", $"\"{workspaceRoot}\" {arguments}") { UseShellExecute = false, CreateNoWindow = true });
        if (process is null) throw new UnauthorizedAccessException("runner NTFS ACL could not be applied");
        process.WaitForExit();
        if (process.ExitCode != 0) throw new UnauthorizedAccessException("runner NTFS ACL could not be applied");
    }

    private static string ReadSecurityDescriptor(string path)
    {
        var result = GetNamedSecurityInfo(path, SeFileObject, SecurityInformation, out _, out _, out _, out _, out var securityDescriptor);
        if (result != 0 || securityDescriptor == nint.Zero)
        {
            throw new Win32Exception((int)result, "runner workspace security descriptor is unavailable");
        }

        try
        {
            if (!ConvertSecurityDescriptorToStringSecurityDescriptor(securityDescriptor, 1, SecurityInformation, out var sddl, out _))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "runner workspace security descriptor could not be converted");
            }

            try
            {
                return Marshal.PtrToStringUni(sddl) ?? throw new InvalidOperationException("runner workspace security descriptor is empty");
            }
            finally
            {
                LocalFree(sddl);
            }
        }
        finally
        {
            LocalFree(securityDescriptor);
        }
    }

    private static string ResolveSid(string accountName)
    {
        var account = accountName.Contains('\\', StringComparison.Ordinal)
            ? new NTAccount(accountName)
            : new NTAccount(Environment.MachineName, accountName);
        return ((SecurityIdentifier)account.Translate(typeof(SecurityIdentifier))).Value;
    }

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetNamedSecurityInfo(
        string objectName,
        uint objectType,
        uint securityInformation,
        out nint owner,
        out nint group,
        out nint dacl,
        out nint sacl,
        out nint securityDescriptor);

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool ConvertSecurityDescriptorToStringSecurityDescriptor(
        nint securityDescriptor,
        uint requestedStringSDRevision,
        uint securityInformation,
        out nint stringSecurityDescriptor,
        out uint stringSecurityDescriptorLen);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern nint LocalFree(nint memory);

    public static string RequireContainedPath(string root, string relativePath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(root);
        ArgumentException.ThrowIfNullOrWhiteSpace(relativePath);
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var candidate = Path.GetFullPath(Path.Combine(root, relativePath));
        if (!candidate.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase))
        {
            PhaseAMetadataStore.TryRecordRegisteredBoundaryDiagnostic(
                root,
                "path_escape",
                "Workspace path containment rejected the operation.");
            throw new UnauthorizedAccessException("runner path escapes project root");
        }
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
        if (_job == nint.Zero || !ConfigureKillOnClose(_job) || !AssignProcessToJobObject(_job, process.Handle))
            throw new InvalidOperationException("runner process could not be attached to a Job Object");
    }

    public void Dispose()
    {
        if (_job != nint.Zero) { CloseHandle(_job); _job = nint.Zero; }
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern nint CreateJobObject(nint attributes, string? name);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool AssignProcessToJobObject(nint job, nint process);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool CloseHandle(nint handle);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool SetInformationJobObject(nint job, int infoClass, ref JobObjectExtendedLimitInformation info, uint length);

    private static bool ConfigureKillOnClose(nint job)
    {
        var info = new JobObjectExtendedLimitInformation { BasicLimitInformation = new JobObjectBasicLimitInformation { LimitFlags = 0x00002000 } };
        return SetInformationJobObject(job, 9, ref info, (uint)Marshal.SizeOf<JobObjectExtendedLimitInformation>());
    }

    [StructLayout(LayoutKind.Sequential)] private struct JobObjectBasicLimitInformation
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public nuint MinimumWorkingSetSize;
        public nuint MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public nint Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)] private struct IoCounters
    {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)] private struct JobObjectExtendedLimitInformation
    {
        public JobObjectBasicLimitInformation BasicLimitInformation;
        public IoCounters IoInfo;
        public nuint ProcessMemoryLimit;
        public nuint JobMemoryLimit;
        public nuint PeakProcessMemoryUsed;
        public nuint PeakJobMemoryUsed;
    }
}
