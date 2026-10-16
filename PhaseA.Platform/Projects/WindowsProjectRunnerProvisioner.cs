using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Projects;

public interface IProjectRunnerProvisioner
{
    void Provision(string accountId, string projectId, WorkspaceLayout layout);
}

// ADR-0035/0061: register the ordinary CreateProject path, not a test-only fixture.
// The platform OS identity must be an administrator and remains the vault owner.
public sealed class WindowsProjectRunnerProvisioner(PhaseAPlatformOptions options) : IProjectRunnerProvisioner
{
    public void Provision(string accountId, string projectId, WorkspaceLayout layout)
    {
        if (!OperatingSystem.IsWindows())
            throw new PlatformNotSupportedException("Project Runner provisioning requires Windows.");
        var expected = WorkspaceLayoutBuilder.Build(options.HostedWorkspaceRoot, accountId, projectId);
        if (layout != expected) throw new UnauthorizedAccessException("runner workspace binding is invalid");
        RunnerIsolationPolicy.RequireNoReparsePoint(Path.GetPathRoot(layout.RootPath)!, layout.RootPath);
        if (File.Exists(Path.Combine(layout.RootPath, ".runner-isolation.json")))
            throw new InvalidOperationException("runner workspace is already registered");

        // Windows SAM names are limited to 20 characters; logical UUIDs stay in the descriptor.
        var userName = "prj" + Guid.NewGuid().ToString("N")[..16];
        var descriptor = new RunnerIsolationDescriptor(accountId, projectId, userName, layout.RootPath, true, true, true);
        var accountCreated = false;
        var credentialCreated = false;
        try
        {
            var password = Convert.ToBase64String(RandomNumberGenerator.GetBytes(32)) + "aA1!";
            CreateLocalUser(userName, password);
            accountCreated = true;
            AddToUsers(userName);
            RunnerCredentialStore.Write(RunnerIsolationPolicy.CredentialTarget(descriptor), @".\" + userName, password);
            credentialCreated = true;

            // Parent namespaces are private to the platform. A Runner can traverse to its
            // explicitly granted Project, but cannot list its account or other Projects.
            var accountRoot = Directory.GetParent(layout.RootPath)!.FullName;
            var parentSecurity = new DirectorySecurity();
            var administrator = new SecurityIdentifier("S-1-5-32-544");
            parentSecurity.SetAccessRuleProtection(true, false);
            parentSecurity.SetOwner(administrator);
            parentSecurity.AddAccessRule(new FileSystemAccessRule(administrator, FileSystemRights.FullControl,
                InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow));
            FileSystemAclExtensions.SetAccessControl(new DirectoryInfo(accountRoot), parentSecurity);

            using var registration = RunnerIsolationPolicy.PrepareWorkspace(descriptor);
            foreach (var child in new[] { layout.RepoPath, layout.RuntimePath, layout.MetaPath })
                RunnerIsolationPolicy.PrepareRestoreTree(descriptor, child);
            ProtectMarker(Path.Combine(layout.RootPath, ".runner-isolation.json"), administrator);
            if (!RunnerIsolationPolicy.HasExpectedWorkspaceSecurity(descriptor))
                throw new UnauthorizedAccessException("runner workspace ACL verification failed");
            // Reading back the vault catches incomplete writes before CreateProject succeeds.
            var stored = RunnerCredentialStore.Read(RunnerIsolationPolicy.CredentialTarget(descriptor));
            if (stored.UserName != @".\" + userName)
                throw new InvalidOperationException("runner credential binding is invalid");
        }
        catch
        {
            // Compensate only resources created by this attempt. Never reuse or remove a
            // pre-existing local identity, credential, or retained Project registration.
            RunnerIsolationPolicy.ForgetWorkspace(layout.RootPath);
            try
            {
                if (credentialCreated) RunnerCredentialStore.Delete(RunnerIsolationPolicy.CredentialTarget(descriptor));
            }
            finally
            {
                if (accountCreated) DeleteLocalUser(userName);
            }
            throw;
        }
    }

    private static void ProtectMarker(string marker, SecurityIdentifier administrator)
    {
        var security = new FileSecurity();
        security.SetAccessRuleProtection(true, false);
        security.SetOwner(administrator);
        security.AddAccessRule(new FileSystemAccessRule(administrator, FileSystemRights.FullControl, AccessControlType.Allow));
        FileSystemAclExtensions.SetAccessControl(new FileInfo(marker), security);
    }

    // Used only for disposing fresh test Projects. Soft deletion keeps production
    // registrations for the existing retention/recovery window.
    internal static void RemoveTestRegistration(RunnerIsolationDescriptor descriptor)
    {
        RunnerIsolationPolicy.ForgetWorkspace(descriptor.WorkspaceRoot);
        try { RunnerCredentialStore.Delete(RunnerIsolationPolicy.CredentialTarget(descriptor)); }
        finally { DeleteLocalUser(descriptor.OsIdentity); }
    }

    private static void CreateLocalUser(string userName, string password)
    {
        var info = new UserInfo1
        {
            Name = userName, Password = password, Privilege = 1,
            Comment = "Phase project isolated Runner", Flags = 0x10201
        };
        var result = NetUserAdd(null, 1, ref info, out _);
        if (result != 0) throw new Win32Exception((int)result, "runner local identity registration failed");
    }

    private static void AddToUsers(string userName)
    {
        var group = (NTAccount)new SecurityIdentifier("S-1-5-32-545").Translate(typeof(NTAccount));
        var groupName = group.Value[(group.Value.LastIndexOf('\\') + 1)..];
        var member = new LocalGroupMemberInfo3 { DomainAndName = Environment.MachineName + @"\" + userName };
        var result = NetLocalGroupAddMembers(null, groupName, 3, ref member, 1);
        if (result != 0) throw new Win32Exception((int)result, "runner Users membership registration failed");
    }

    private static void DeleteLocalUser(string userName)
    {
        var result = NetUserDel(null, userName);
        if (result != 0 && result != 2221)
            throw new Win32Exception((int)result, "runner local identity cleanup failed");
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct UserInfo1
    {
        [MarshalAs(UnmanagedType.LPWStr)] public string Name;
        [MarshalAs(UnmanagedType.LPWStr)] public string Password;
        public uint PasswordAge;
        public uint Privilege;
        [MarshalAs(UnmanagedType.LPWStr)] public string? HomeDirectory;
        [MarshalAs(UnmanagedType.LPWStr)] public string? Comment;
        public uint Flags;
        [MarshalAs(UnmanagedType.LPWStr)] public string? ScriptPath;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct LocalGroupMemberInfo3
    {
        [MarshalAs(UnmanagedType.LPWStr)] public string DomainAndName;
    }

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
    private static extern uint NetUserAdd(string? server, uint level, ref UserInfo1 info, out uint parameterError);

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
    private static extern uint NetUserDel(string? server, string userName);

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
    private static extern uint NetLocalGroupAddMembers(string? server, string group, uint level,
        ref LocalGroupMemberInfo3 member, uint count);
}
