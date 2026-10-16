using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using PhaseA.Platform.Security;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

// Test-only lifecycle for dynamically generated account/project boundaries.
// No production isolation rule or credential is reused across scopes.
internal sealed class TestRunnerCredentialScope : IDisposable
{
    private const uint CredTypeGeneric = 1;
    private const uint CredPersistSession = 1;
    private readonly string _target;
    private bool _disposed;

    private TestRunnerCredentialScope(string accountId, string projectId, string? accountName = null)
    {
        AccountName = accountName ?? $"pr8{Guid.NewGuid():N}"[..14];
        Password = CreatePassword();
        _target = RunnerIsolationPolicy.CredentialTarget(new RunnerIsolationDescriptor(
            accountId, projectId, AccountName, Path.GetTempPath(), true, true, true));
        AddLocalUser(AccountName, Password);
        try
        {
            WriteCredential(_target, $".\\{AccountName}", Password);
        }
        catch
        {
            DeleteLocalUser(AccountName);
            throw;
        }
    }

    public string AccountName { get; }
    private string Password { get; }
    public string OsIdentity => $"{Environment.MachineName}\\{AccountName}";

    public static TestRunnerCredentialScope Create(string accountId, string projectId)
    {
        if (!OperatingSystem.IsWindows())
            throw new PlatformNotSupportedException("Dynamic Runner credentials require Windows.");
        return new TestRunnerCredentialScope(accountId, projectId);
    }

    // ADR-0061: the existing fixed fixtures use this exact test boundary.
    // Dynamic account/project fixtures still create their own scoped identities.
    internal static TestRunnerCredentialScope CreateCiBaseline() =>
        new("account-a", "project-a", "phase-r-a-p");

    public RunnerIsolationDescriptor Describe(string accountId, string projectId, string workspaceRoot) =>
        new(accountId, projectId, OsIdentity, workspaceRoot, true, true, true);

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        CredDelete(_target, CredTypeGeneric, 0);
        DeleteLocalUser(AccountName);
    }

    private static string CreatePassword()
    {
        const string alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@$%";
        Span<byte> bytes = stackalloc byte[32];
        RandomNumberGenerator.Fill(bytes);
        var builder = new StringBuilder(36);
        builder.Append('A').Append('a').Append('7').Append('!');
        foreach (var value in bytes) builder.Append(alphabet[value % alphabet.Length]);
        return builder.ToString();
    }

    private static void AddLocalUser(string name, string password)
    {
        var script = "$ErrorActionPreference='Stop'; $pw=ConvertTo-SecureString '" + EscapePowerShell(password) + "' -AsPlainText -Force; " +
            "$u=New-LocalUser -Name '" + EscapePowerShell(name) + "' -Password $pw -AccountNeverExpires -PasswordNeverExpires -UserMayNotChangePassword; " +
            "Add-LocalGroupMember -Group 'Users' -Member $u.Name -ErrorAction SilentlyContinue";
        var encoded = Convert.ToBase64String(Encoding.Unicode.GetBytes(script));
        var windowsPowerShell = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "WindowsPowerShell", "v1.0");
        var start = new ProcessStartInfo(Path.Combine(windowsPowerShell, "powershell.exe"), $"-NoProfile -NonInteractive -EncodedCommand {encoded}")
        {
            UseShellExecute = false, CreateNoWindow = true, RedirectStandardError = true, RedirectStandardOutput = true
        };
        // PowerShell 7's inherited module path cannot load Security in Windows
        // PowerShell 5.1. Resolve the version-matched built-in modules explicitly.
        start.Environment["PSModulePath"] = Path.Combine(windowsPowerShell, "Modules");
        using var process = Process.Start(start)
            ?? throw new InvalidOperationException("test Runner account creation process could not start");
        var output = process.StandardOutput.ReadToEndAsync();
        var error = process.StandardError.ReadToEndAsync();
        if (!process.WaitForExit(30_000))
        {
            process.Kill(entireProcessTree: true);
            process.WaitForExit();
            DeleteLocalUser(name);
            throw new TimeoutException("test Runner account creation exceeded its bounded wait");
        }
        Task.WhenAll(output, error).GetAwaiter().GetResult();
        if (process.ExitCode != 0)
        {
            DeleteLocalUser(name);
            // PowerShell error output can echo the password-bearing script.
            // Retain the exit code without returning raw output or command bytes.
            throw new Win32Exception(process.ExitCode, $"test Runner account creation failed (exit={process.ExitCode})");
        }
    }

    private static void DeleteLocalUser(string name) => NetUserDel(null, name);

    private static string EscapePowerShell(string value) => value.Replace("'", "''", StringComparison.Ordinal);

    private static void WriteCredential(string target, string userName, string password)
    {
        var blob = Marshal.StringToCoTaskMemUni(password);
        try
        {
            var credential = new NativeCredential
            {
                TargetName = target,
                UserName = userName,
                Type = CredTypeGeneric,
                Persist = CredPersistSession,
                CredentialBlob = blob,
                CredentialBlobSize = checked((uint)(password.Length * sizeof(char)))
            };
            if (!CredWrite(ref credential, 0)) throw new Win32Exception(Marshal.GetLastWin32Error(), "test Runner credential write failed");
        }
        finally { Marshal.FreeCoTaskMem(blob); }
    }

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode)]
    private static extern uint NetUserDel(string? servername, string username);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredWrite(ref NativeCredential credential, uint flags);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredDelete(string target, uint type, uint flags);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NativeCredential
    {
        public uint Flags;
        public uint Type;
        [MarshalAs(UnmanagedType.LPWStr)] public string TargetName;
        [MarshalAs(UnmanagedType.LPWStr)] public string? Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public uint CredentialBlobSize;
        public nint CredentialBlob;
        public uint Persist;
        public uint AttributeCount;
        public nint Attributes;
        public nint TargetAlias;
        [MarshalAs(UnmanagedType.LPWStr)] public string UserName;
    }
}
