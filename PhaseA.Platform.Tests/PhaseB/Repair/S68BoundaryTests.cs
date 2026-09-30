using System.ComponentModel;
using System.Diagnostics;
using System.Security.Principal;
using System.Text;
using Microsoft.Data.Sqlite;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S68BoundaryTests : IDisposable
{
    private const string ManagedRunnerIdentity = "phase-r-a-p";
    private const string AccessDeniedMarker = "S68_OS_ACCESS_DENIED";
    private const string UnexpectedReadMarker = "S68_UNEXPECTED_READ";
    private readonly string _root = Path.Combine(Path.GetTempPath(), "phase-s68-" + Guid.NewGuid().ToString("N"));
    private readonly string _workspace;
    private readonly string _runnerSid;
    private readonly RunnerIsolationHandle _isolation;

    public S68BoundaryTests()
    {
        Directory.CreateDirectory(_root);
        _workspace = Path.Combine(_root, "account-a", "project-a");
        _runnerSid = ((SecurityIdentifier)new NTAccount(Environment.MachineName, ManagedRunnerIdentity)
            .Translate(typeof(SecurityIdentifier))).Value;
        _isolation = RunnerIsolationPolicy.PrepareWorkspace(new RunnerIsolationDescriptor(
            "account-a", "project-a", ManagedRunnerIdentity, _workspace,
            LowPrivilegeRequired: true, JobObjectRequired: true, NtfsAclRequired: true));
        GrantRunnerModify(_workspace);
    }

    [Fact]
    public async Task O_F4B56371054A()
    {
        const string protectedContent = "S68_PLATFORM_BINARY_CONTENT_MUST_NOT_DISCLOSE";
        var target = Path.Combine(CreatePlatformRoot("binary"), "PhaseA.Platform.dll");
        await File.WriteAllBytesAsync(target, Encoding.UTF8.GetBytes(protectedContent));
        GrantAdministratorsOnly(Path.GetDirectoryName(target)!);
        AssertPlatformCanRead(target, protectedContent);

        var runner = await RunBypassedReadAsync(target);
        RequireOsDeniedRead(runner, protectedContent, "FAILURE-O-F4B56371054A", "platform binary");
    }

    [Fact]
    public async Task O_FF221ED1B7BF()
    {
        const string protectedContent = "S68_PLATFORM_DATABASE_CONTENT_MUST_NOT_DISCLOSE";
        var target = Path.Combine(CreatePlatformRoot("database"), "phasea-platform.sqlite3");
        await CreatePlatformDatabaseAsync(target, protectedContent);
        GrantAdministratorsOnly(Path.GetDirectoryName(target)!);
        AssertPlatformCanRead(target, protectedContent);

        var runner = await RunBypassedReadAsync(target);
        RequireOsDeniedRead(runner, protectedContent, "FAILURE-O-FF221ED1B7BF", "platform database");
    }

    private string CreatePlatformRoot(string fixtureName)
    {
        var root = Path.Combine(_root, "platform-" + fixtureName);
        Directory.CreateDirectory(root);
        return root;
    }

    private static async Task CreatePlatformDatabaseAsync(string path, string protectedContent)
    {
        await using var connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = path, Pooling = false }.ToString());
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "CREATE TABLE platform_secret (value TEXT NOT NULL); INSERT INTO platform_secret(value) VALUES ($value);";
        command.Parameters.AddWithValue("$value", protectedContent);
        await command.ExecuteNonQueryAsync();
    }

    private static void AssertPlatformCanRead(string target, string protectedContent)
    {
        var content = File.ReadAllText(target);
        if (!content.Contains(protectedContent, StringComparison.Ordinal))
        {
            throw new Xunit.Sdk.XunitException($"S68 platform fixture could not be read before the restricted probe: {target}");
        }
    }

    private async Task<HostedProcessResult> RunBypassedReadAsync(string target)
    {
        var escapedTarget = target.Replace("'", "''", StringComparison.Ordinal);
        var script = $"try{{gc '{escapedTarget}' -ea stop;echo {UnexpectedReadMarker};exit 0}}catch{{echo {AccessDeniedMarker};exit 5}}";
        var encodedScript = Convert.ToBase64String(Encoding.Unicode.GetBytes(script));
        var command = new HostedProcessCommand(
            "powershell.exe",
            ["-NoProfile", "-NonInteractive", "-EncodedCommand", encodedScript],
            _workspace,
            new Dictionary<string, string>());
        try
        {
            return await new HostedProcessRunner().RunAsync(command);
        }
        catch (Exception error) when (error is Win32Exception or InvalidOperationException)
        {
            throw new Xunit.Sdk.XunitException($"S68 runner process initialization failed before the bypassed read: type={error.GetType().Name} message={error.Message}");
        }
    }

    private static void RequireOsDeniedRead(HostedProcessResult runner, string protectedContent, string failureId, string resource)
    {
        var output = runner.Stdout + Environment.NewLine + runner.Stderr;
        var denied = runner.ExitCode == 5 &&
            output.Contains(AccessDeniedMarker, StringComparison.Ordinal) &&
            !output.Contains(UnexpectedReadMarker, StringComparison.Ordinal) &&
            !output.Contains(protectedContent, StringComparison.Ordinal);
        if (!denied)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: bypassed restricted Runner read was not denied by the OS for {resource}. exit={runner.ExitCode}; stdout={runner.Stdout}; stderr={runner.Stderr}");
        }
    }

    private static void GrantAdministratorsOnly(string path) => ApplyAcl(path, "*S-1-5-32-544:(OI)(CI)F");

    private void GrantRunnerModify(string path) => ApplyAcl(path, $"*{_runnerSid}:(OI)(CI)M");

    private static void ApplyAcl(string path, string grant)
    {
        using var acl = Process.Start(new ProcessStartInfo("icacls.exe", $"\"{path}\" /inheritance:r /grant:r \"{grant}\"")
        {
            UseShellExecute = false,
            CreateNoWindow = true
        });
        if (acl is null)
        {
            throw new Xunit.Sdk.XunitException($"S68 ACL process did not start for {path}");
        }
        acl.WaitForExit();
        if (acl.ExitCode != 0)
        {
            throw new Xunit.Sdk.XunitException($"S68 ACL process failed for {path}: exit={acl.ExitCode}");
        }
    }

    public void Dispose()
    {
        _isolation.Dispose();
        try { Directory.Delete(_root, recursive: true); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }
}
