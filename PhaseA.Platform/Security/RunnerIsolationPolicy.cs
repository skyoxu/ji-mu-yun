namespace PhaseA.Platform.Security;

using PhaseA.Platform.Data;
using System.Collections.Concurrent;
using System.ComponentModel;
using System.Diagnostics;
using System.Security.Principal;
using System.Security.AccessControl;
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
        File.WriteAllText(marker, System.Text.Json.JsonSerializer.Serialize(new PersistedIsolationDescriptor(
            descriptor.AccountId, descriptor.ProjectId, descriptor.OsIdentity,
            descriptor.LowPrivilegeRequired, descriptor.JobObjectRequired, descriptor.NtfsAclRequired)) + Environment.NewLine);
        var normalized = descriptor with { WorkspaceRoot = Path.GetFullPath(descriptor.WorkspaceRoot) };
        Workspaces[normalized.WorkspaceRoot] = normalized;
        if (OperatingSystem.IsWindows())
        {
            var securityDescriptor = ReadSecurityDescriptor(normalized.WorkspaceRoot);
            WorkspaceSecurityDescriptors[normalized.WorkspaceRoot] = securityDescriptor;
            File.WriteAllText(marker, System.Text.Json.JsonSerializer.Serialize(new PersistedIsolationDescriptor(
                normalized.AccountId, normalized.ProjectId, normalized.OsIdentity,
                normalized.LowPrivilegeRequired, normalized.JobObjectRequired, normalized.NtfsAclRequired,
                securityDescriptor)) + Environment.NewLine);
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
        for (var current = new DirectoryInfo(candidate); current is not null; current = current.Parent)
        {
            var marker = Path.Combine(current.FullName, ".runner-isolation.json");
            if (!File.Exists(marker)) continue;
            try
            {
                var persisted = System.Text.Json.JsonSerializer.Deserialize<PersistedIsolationDescriptor>(File.ReadAllText(marker));
                if (persisted is null || !persisted.LowPrivilegeRequired ||
                    (OperatingSystem.IsWindows() && (!persisted.JobObjectRequired || !persisted.NtfsAclRequired))) continue;
                var restored = new RunnerIsolationDescriptor(persisted.AccountId, persisted.ProjectId, persisted.OsIdentity,
                    current.FullName, persisted.LowPrivilegeRequired, persisted.JobObjectRequired, persisted.NtfsAclRequired);
                if (OperatingSystem.IsWindows() && string.IsNullOrWhiteSpace(persisted.SecurityDescriptor)) continue;
                if (OperatingSystem.IsWindows()) WorkspaceSecurityDescriptors[restored.WorkspaceRoot] = persisted.SecurityDescriptor!;
                Workspaces[restored.WorkspaceRoot] = restored;
                descriptor = restored;
                return true;
            }
            catch (Exception) when (File.Exists(marker)) { }
        }
        descriptor = null!;
        return false;
    }

    public static RunnerIsolationHandle CreateProcessIsolation(RunnerIsolationDescriptor descriptor) => new(descriptor, string.Empty);

    // Remove only this registration; retained Projects keep their identity and marker.
    internal static void ForgetWorkspace(string root)
    {
        var fullRoot = Path.GetFullPath(root);
        Workspaces.TryRemove(fullRoot, out _);
        WorkspaceSecurityDescriptors.TryRemove(fullRoot, out _);
    }

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

    // ADR-0061: publication validates every restored object, not just its parent.
    public static void PrepareRestoreTree(RunnerIsolationDescriptor descriptor, string treeRoot)
    {
        DemandRestoreTreeLocation(descriptor, treeRoot);
        if (!OperatingSystem.IsWindows()) return;
        var sid = new SecurityIdentifier(ResolveSid(descriptor.OsIdentity));
        var administrator = new SecurityIdentifier("S-1-5-32-544");
        foreach (var path in RestoreTreePaths(treeRoot))
        {
            var directory = Directory.Exists(path);
            FileSystemSecurity security = directory ? new DirectorySecurity() : new FileSecurity();
            security.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);
            security.SetOwner(administrator);
            var inheritance = directory ? InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit : InheritanceFlags.None;
            security.AddAccessRule(new FileSystemAccessRule(administrator, FileSystemRights.FullControl,
                inheritance, PropagationFlags.None, AccessControlType.Allow));
            security.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.Modify,
                inheritance, PropagationFlags.None, AccessControlType.Allow));
            if (directory) FileSystemAclExtensions.SetAccessControl(new DirectoryInfo(path), (DirectorySecurity)security);
            else FileSystemAclExtensions.SetAccessControl(new FileInfo(path), (FileSecurity)security);
        }
        if (!HasExpectedRestoreTreeSecurity(descriptor, treeRoot))
            throw new UnauthorizedAccessException("restore tree ACL verification failed");
    }

    public static bool HasExpectedRestoreTreeSecurity(RunnerIsolationDescriptor descriptor, string treeRoot)
    {
        try
        {
            DemandRestoreTreeLocation(descriptor, treeRoot);
            if (!HasExpectedWorkspaceSecurity(descriptor)) return false;
            var paths = RestoreTreePaths(treeRoot).ToArray();
            if (!OperatingSystem.IsWindows()) return true;
            var runnerSid = ResolveSid(descriptor.OsIdentity);
            foreach (var path in paths)
            {
                var security = new RawSecurityDescriptor(ReadSecurityDescriptor(path));
                if (security.Owner?.Value != "S-1-5-32-544" || security.DiscretionaryAcl is null ||
                    (security.ControlFlags & ControlFlags.DiscretionaryAclProtected) == 0) return false;
                var admin = false;
                var runner = false;
                foreach (GenericAce entry in security.DiscretionaryAcl)
                {
                    if (entry is not CommonAce ace || ace.AceQualifier != AceQualifier.AccessAllowed ||
                        (ace.AceFlags & AceFlags.InheritOnly) != 0) return false;
                    if (ace.SecurityIdentifier.Value == "S-1-5-32-544" && ace.AccessMask == (int)FileSystemRights.FullControl)
                        admin = true;
                    else if (ace.SecurityIdentifier.Value == runnerSid &&
                             ace.AccessMask == (int)(FileSystemRights.Modify | FileSystemRights.Synchronize)) runner = true;
                    else return false;
                }
                if (!admin || !runner) return false;
            }
            return true;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or ArgumentException or Win32Exception)
        { return false; }
    }

    private static void DemandRestoreTreeLocation(RunnerIsolationDescriptor descriptor, string treeRoot)
    {
        var relative = Path.GetRelativePath(descriptor.WorkspaceRoot, treeRoot);
        _ = RequireContainedPath(descriptor.WorkspaceRoot, relative);
        if (!Directory.Exists(treeRoot)) throw new DirectoryNotFoundException("restore tree is missing");
    }

    private static IEnumerable<string> RestoreTreePaths(string root)
    {
        // Check before descending; SearchOption.AllDirectories can follow a junction.
        if ((File.GetAttributes(root) & FileAttributes.ReparsePoint) != 0)
            throw new UnauthorizedAccessException("restore tree contains a reparse point");
        yield return root;
        foreach (var path in Directory.EnumerateFileSystemEntries(root))
        {
            if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
                throw new UnauthorizedAccessException("restore tree contains a reparse point");
            if (Directory.Exists(path))
            {
                foreach (var child in RestoreTreePaths(path)) yield return child;
            }
            else yield return path;
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

    private sealed record PersistedIsolationDescriptor(string AccountId, string ProjectId, string OsIdentity,
        bool LowPrivilegeRequired, bool JobObjectRequired, bool NtfsAclRequired, string? SecurityDescriptor = null);
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
        // Each dispatch owns a private Job Object. A shared named object would
        // make parallel independent Runner launches contend for the same job.
        _job = CreateJobObject(nint.Zero, null);
        if (_job == nint.Zero)
            throw new InvalidOperationException($"runner process could not create a Job Object (win32={Marshal.GetLastWin32Error()})");
        if (!ConfigureKillOnClose(_job))
            throw new InvalidOperationException($"runner Job Object could not be configured (win32={Marshal.GetLastWin32Error()})");
        if (!AssignProcessToJobObject(_job, process.Handle))
        {
            var error = Marshal.GetLastWin32Error();
            // A process launched by a host already inside a non-breakaway Job
            // Object inherits that containment. In that case Windows rejects
            // assignment to a second job with ERROR_ACCESS_DENIED; accepting
            // the inherited containment preserves cleanup without weakening the
            // isolation boundary. Any other attach failure remains fatal.
            if (error != 5 || !IsProcessInJob(process.Handle, nint.Zero, out var isInJob) || !isInJob)
                throw new InvalidOperationException($"runner process could not be attached to a Job Object (win32={error})");
            CloseHandle(_job);
            _job = nint.Zero;
        }
    }

    public void Dispose()
    {
        if (_job != nint.Zero) { CloseHandle(_job); _job = nint.Zero; }
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern nint CreateJobObject(nint attributes, string? name);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool AssignProcessToJobObject(nint job, nint process);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool IsProcessInJob(nint process, nint job, out bool result);
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
