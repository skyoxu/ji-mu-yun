using System.ComponentModel;
using System.Diagnostics;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S54BoundaryTests : IDisposable
{
    private const string LaunchMarker = "S54_PROCESS_LAUNCHED";
    private const string AttemptMarker = "S54_OPERATION_ATTEMPTED";
    private const string AccessDeniedMarker = "S54_ACCESS_DENIED";
    private const string OwnedWriteMarker = "S54_OWNED_WRITE";
    private const string OwnedEnumerationMarker = "S54_OWN_PROJECT_ENUMERATED";
    private const string ManagedRunnerIdentity = "phase-r-a-p";
    private readonly ITestOutputHelper _output;
    private readonly string _root = Path.Combine(Path.GetTempPath(), "phase-s54-" + Guid.NewGuid().ToString("N"));
    private readonly string _workspace;
    private readonly string _runnerSid;
    private readonly RunnerIsolationHandle _isolation;

    public S54BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
        Directory.CreateDirectory(_root);
        _workspace = Path.Combine(_root, "account-a", "project-a");
        _runnerSid = ((SecurityIdentifier)new NTAccount(Environment.MachineName, ManagedRunnerIdentity)
            .Translate(typeof(SecurityIdentifier))).Value;
        _isolation = RunnerIsolationPolicy.PrepareWorkspace(new RunnerIsolationDescriptor(
            "account-a", "project-a", ManagedRunnerIdentity, _workspace,
            LowPrivilegeRequired: true, JobObjectRequired: true, NtfsAclRequired: true));
        GrantRunnerModify(_workspace);
    }

    [Fact] public async Task O_12F85445CCD2() => await AssertRunnerDeniedAsync("platform-binary", "write", "FAILURE-O-12F85445CCD2");
    [Fact] public async Task O_1D8CB3E8262F() => await AssertRunnerDeniedAsync("proxy-config", "read", "FAILURE-O-1D8CB3E8262F");
    [Fact] public async Task O_358D470F6E85() => await AssertRunnerDeniedAsync("unauthorized-staging", "write", "FAILURE-O-358D470F6E85");
    [Fact] public async Task O_3FA9A1207C61() => await AssertRunnerDeniedAsync("secrets", "read", "FAILURE-O-3FA9A1207C61");
    [Fact] public async Task O_4178BD27EC32() => await AssertRunnerDeniedAsync("sibling-project", "read", "FAILURE-O-4178BD27EC32");
    [Fact] public async Task O_4834E9163638() => await AssertRunnerDeniedAsync("other-account", "read", "FAILURE-O-4834E9163638");
    [Fact] public async Task O_4E130E94995A() => await AssertRunnerDeniedAsync("proxy-config", "write", "FAILURE-O-4E130E94995A");
    [Fact] public async Task O_5CBD9C2F5F8E() => await AssertRunnerDeniedAsync("unauthorized-staging", "read", "FAILURE-O-5CBD9C2F5F8E");
    [Fact] public async Task O_D6F9AC452A48() => await AssertRunnerDeniedAsync("platform-owned", "write", "FAILURE-O-D6F9AC452A48");

    [Fact]
    public async Task O_B21A2E1BF669()
    {
        var platformSid = await GetPlatformSidAsync();
        var runner = await RunRunnerWithProofAsync("echo identity-proof>nul");
        AssertRunnerStarted(runner, platformSid, "identity-proof");
        Assert.DoesNotContain("High Mandatory Level", runner.Output, StringComparison.OrdinalIgnoreCase);
        Observe("distinct-restricted-os-token", true);
    }

    [Fact]
    public async Task O_C5E83411E41D()
    {
        var platformSid = await GetPlatformSidAsync();
        var runner = await RunRunnerWithProofAsync(BuildOwnedWrite(Path.Combine(_workspace, "owned.txt")));
        AssertRunnerStarted(runner, platformSid, "authorized-workspace-write");
        Assert.Equal(0, runner.OperationExitCode);
        Assert.Contains(OwnedWriteMarker, runner.Output, StringComparison.Ordinal);
        Assert.Equal("runner-owned", File.ReadAllText(Path.Combine(_workspace, "owned.txt")).Trim());
        Observe("authorized-workspace-write", true);
    }

    [Fact]
    public async Task O_824_ACCOUNT_ROOT_ENUMERATION()
    {
        var accountRoot = Path.Combine(_root, "account-a");
        var ownProject = _workspace;
        Directory.CreateDirectory(Path.Combine(accountRoot, "project-b"));
        GrantAdministratorsOnly(accountRoot);
        GrantRunnerModify(ownProject);
        var platformSid = await GetPlatformSidAsync();

        var rootEnumeration = await RunRunnerWithProofAsync(BuildDirectoryEnumeration(accountRoot));
        AssertRunnerStarted(rootEnumeration, platformSid, "account-root-enumeration");
        AssertAccessDenied(rootEnumeration, "account-root-enumeration");

        var projectEnumeration = await RunRunnerWithProofAsync(BuildOwnedDirectoryEnumeration(ownProject));
        AssertRunnerStarted(projectEnumeration, platformSid, "own-project-enumeration");
        Assert.Equal(0, projectEnumeration.OperationExitCode);
        Assert.Contains(OwnedEnumerationMarker, projectEnumeration.Output, StringComparison.Ordinal);
        Observe("account-root-enumeration-denied", true);
    }

    [Fact]
    public async Task O_270713F3B6BC()
    {
        var childStarted = Path.Combine(_root, "child-started.txt");
        using var cancellation = new CancellationTokenSource();
        var runner = new HostedProcessRunner();
        var launcher = $"$child = Start-Process -FilePath 'cmd.exe' -ArgumentList '/d','/c','timeout /t 30 > nul' -PassThru; [IO.File]::WriteAllText('{childStarted}', [string]$child.Id); Start-Sleep -Seconds 30";
        var run = runner.RunAsync(new HostedProcessCommand(
            "powershell.exe",
            ["-NoProfile", "-NonInteractive", "-Command", launcher],
            _root,
            new Dictionary<string, string>()), cancellation.Token);

        await WaitForFileAsync(childStarted, TimeSpan.FromSeconds(5));
        Assert.True(File.Exists(childStarted), "FAILURE-O-270713F3B6BC: child did not start; cancellation cannot prove cleanup.");
        var childPid = int.Parse((await File.ReadAllTextAsync(childStarted)).Trim(), System.Globalization.CultureInfo.InvariantCulture);
        using var child = Process.GetProcessById(childPid);
        Assert.False(child.HasExited, "FAILURE-O-270713F3B6BC: child exited before parent cancellation.");
        cancellation.Cancel();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => run);
        await Task.Delay(TimeSpan.FromMilliseconds(500));
        child.Refresh();
        Assert.True(child.HasExited, "FAILURE-O-270713F3B6BC: child outlived the runner cancellation.");
        Observe("children-terminated-after-parent", true);
    }

    private async Task AssertRunnerDeniedAsync(string resource, string operation, string failureId)
    {
        var protectedRoot = Path.Combine(_root, resource);
        Directory.CreateDirectory(protectedRoot);
        var target = Path.Combine(protectedRoot, "protected.txt");
        await File.WriteAllTextAsync(target, "platform-owned");
        GrantAdministratorsOnly(protectedRoot);
        var platformCommand = operation == "read" ? $"type \"{target}\"" : $"echo platform-write>\"{target}\"";
        var platform = await RunPlatformAsync(platformCommand);
        Assert.Equal(0, platform.ExitCode);
        if (operation == "write") await File.WriteAllTextAsync(target, "platform-owned");

        var platformSid = await GetPlatformSidAsync();
        var command = BuildProtectedOperation(target, operation);
        var runner = await RunRunnerWithProofAsync(command);
        AssertRunnerStarted(runner, platformSid, resource);
        AssertAccessDenied(runner, resource);
        Assert.Equal("platform-owned", await File.ReadAllTextAsync(target));
        Observe($"os-denied:{resource}:{operation}", true);
    }

    private async Task<RunnerProof> RunRunnerWithProofAsync(string operation)
    {
        var command = $"echo {LaunchMarker} & whoami /user /fo csv /nh & echo {AttemptMarker} & {operation}";
        var probePath = Path.Combine(_workspace, "s54-probe-" + Guid.NewGuid().ToString("N") + ".cmd");
        await File.WriteAllTextAsync(probePath, "@echo off\r\n" + command + "\r\n", Encoding.ASCII);
        try
        {
            var result = await new HostedProcessRunner().RunAsync(new HostedProcessCommand("cmd.exe", ["/d", "/c", probePath], _workspace, new Dictionary<string, string>()));
            return RunnerProof.FromResult(result);
        }
        catch (Exception error) when (error is Win32Exception or InvalidOperationException)
        {
            throw new Xunit.Sdk.XunitException($"S54 runner process initialization failed before the operation: win32={error.HResult & 0xffff} hresult=0x{error.HResult:X8} type={error.GetType().Name} message={error.Message}");
        }
    }

    private static Task<string> GetPlatformSidAsync()
    {
        var sid = WindowsIdentity.GetCurrent().User?.Value;
        if (string.IsNullOrWhiteSpace(sid))
            throw new Xunit.Sdk.XunitException("S54 platform identity is unavailable before the boundary assertion.");
        return Task.FromResult(sid);
    }

    private static void AssertRunnerStarted(RunnerProof runner, string platformSid, string operation)
    {
        Assert.True(runner.Launched, $"S54 runner did not report launch before {operation}. stdout={runner.Stdout} stderr={runner.Stderr}");
        Assert.True(runner.OperationAttempted, $"S54 runner did not report the attempted operation {operation}. stdout={runner.Stdout} stderr={runner.Stderr}");
        Assert.NotEqual(platformSid, runner.Sid);
    }

    private static void AssertAccessDenied(RunnerProof runner, string operation)
    {
        Assert.NotEqual(0, runner.OperationExitCode);
        Assert.True(runner.Output.Contains(AccessDeniedMarker + ":5", StringComparison.Ordinal),
            $"S54 denial probe returned a non-access-denied failure for {operation}: stdout={runner.Stdout} stderr={runner.Stderr}");
        Assert.Contains(AttemptMarker, runner.Stdout, StringComparison.Ordinal);
        Assert.True(runner.Launched, $"S54 runner did not launch for {operation}.");
    }

    private static string BuildProtectedOperation(string target, string operation)
    {
        var action = operation == "read"
            ? $"gc '{target}' -ea stop"
            : $"[IO.File]::WriteAllText('{target}', 'runner-write')";
        return BuildDeniedOperation(action);
    }

    private static string BuildDirectoryEnumeration(string path)
    {
        return BuildDeniedOperation($"ls '{path}' -ea stop|out-null");
    }

    private static string BuildDeniedOperation(string action)
    {
        var script = $"try{{{action};exit 0}}catch{{" +
            "$code=$_.Exception.HResult -band 0xffff;" +
            "$inner=$_.Exception.InnerException;" +
            "$innerCode=if($null -eq $inner){-1}else{$inner.HResult -band 0xffff};" +
            $"if($code -eq 5 -or ($inner -is [System.UnauthorizedAccessException] -and $innerCode -eq 5)){{echo '{AccessDeniedMarker}:5';exit 5}}" +
            "echo ('S54_UNEXPECTED_ERROR:'+$code+':'+$_.Exception.GetType().FullName+':'+$inner.GetType().FullName+':'+$innerCode);exit 6}";
        return BuildPowerShellCommand(script);
    }

    private static string BuildOwnedWrite(string path)
    {
        return BuildPowerShellCommand($"try{{[IO.File]::WriteAllText('{path}','runner-owned');echo {OwnedWriteMarker};exit 0}}catch{{echo S54_UNEXPECTED_ERROR;exit 6}}");
    }

    private static string BuildOwnedDirectoryEnumeration(string path)
    {
        return BuildPowerShellCommand($"try{{ls '{path}' -ea stop|out-null;echo {OwnedEnumerationMarker};exit 0}}catch{{echo S54_UNEXPECTED_ERROR;exit 6}}");
    }

    private static string BuildPowerShellCommand(string script) =>
        $"powershell.exe -NoProfile -NonInteractive -EncodedCommand {Convert.ToBase64String(Encoding.Unicode.GetBytes(script))}";

    private static async Task WaitForFileAsync(string path, TimeSpan timeout)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (!File.Exists(path) && DateTime.UtcNow < deadline)
        {
            await Task.Delay(50);
        }
    }

    private static async Task<HostedProcessResult> RunPlatformAsync(string command)
    {
        using var process = Process.Start(new ProcessStartInfo("cmd.exe", $"/d /c {command}")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        });
        Assert.NotNull(process);
        var stdout = await process.StandardOutput.ReadToEndAsync();
        var stderr = await process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync();
        return new HostedProcessResult(process.ExitCode, stdout, stderr);
    }

    private static string ExtractSid(string output)
    {
        var match = Regex.Match(output, "S-1-5-[0-9-]+", RegexOptions.CultureInvariant);
        Assert.True(match.Success, $"S54 token probe did not return a SID: {output}");
        return match.Value;
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
        Assert.NotNull(acl);
        acl.WaitForExit();
        Assert.Equal(0, acl.ExitCode);
    }

    private void Observe(string key, bool value) => _output.WriteLine($"S54_OBSERVATION:{key}={value.ToString().ToLowerInvariant()}");

    public void Dispose()
    {
        _isolation.Dispose();
        try { Directory.Delete(_root, recursive: true); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }

    private sealed record RunnerProof(int ProcessExitCode, int OperationExitCode, string Stdout, string Stderr, string Sid, bool Launched, bool OperationAttempted)
    {
        public string Output => Stdout + Environment.NewLine + Stderr;

        public static RunnerProof FromResult(HostedProcessResult result)
        {
            var output = result.Stdout + Environment.NewLine + result.Stderr;
            return new RunnerProof(
                result.ExitCode,
                result.ExitCode,
                result.Stdout,
                result.Stderr,
                ExtractSid(result.Stdout),
                result.Stdout.Contains(LaunchMarker, StringComparison.Ordinal),
                result.Stdout.Contains(AttemptMarker, StringComparison.Ordinal));
        }
    }
}
