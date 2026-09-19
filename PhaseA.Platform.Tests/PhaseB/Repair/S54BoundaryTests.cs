using System.Diagnostics;
using PhaseA.Platform.Runs;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S54BoundaryTests : IDisposable
{
    private readonly ITestOutputHelper _output;
    private readonly string _root = Path.Combine(Path.GetTempPath(), "phase-s54-" + Guid.NewGuid().ToString("N"));

    public S54BoundaryTests(ITestOutputHelper output)
    {
        _output = output;
        Directory.CreateDirectory(_root);
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
        var platformToken = await RunPlatformAsync("whoami /groups /fo csv /nh");
        var runnerToken = await RunAsync("whoami /groups /fo csv /nh");
        Assert.NotEqual(platformToken.Stdout.Trim(), runnerToken.Stdout.Trim());
        Assert.DoesNotContain("High Mandatory Level", runnerToken.Stdout, StringComparison.OrdinalIgnoreCase);
        Observe("distinct-restricted-os-token", true);
    }

    [Fact]
    public async Task O_C5E83411E41D()
    {
        var workspace = Path.Combine(_root, "account-a", "project-a");
        Directory.CreateDirectory(workspace);
        GrantUsersModify(workspace);
        var result = await RunAsync($"echo runner-owned>\"{Path.Combine(workspace, "owned.txt")}\"");
        Assert.Equal(0, result.ExitCode);
        Assert.Equal("runner-owned", File.ReadAllText(Path.Combine(workspace, "owned.txt")).Trim());
        Observe("authorized-workspace-write", true);
    }

    [Fact]
    public async Task O_824_ACCOUNT_ROOT_ENUMERATION()
    {
        var accountRoot = Path.Combine(_root, "account-a");
        Directory.CreateDirectory(Path.Combine(accountRoot, "project-a"));
        Directory.CreateDirectory(Path.Combine(accountRoot, "project-b"));
        GrantAdministratorsOnly(accountRoot);
        GrantUsersModify(Path.Combine(accountRoot, "project-a"));
        var result = await RunAsync($"dir /b \"{accountRoot}\"");
        Assert.NotEqual(0, result.ExitCode);
        var ownProject = await RunAsync($"dir /b \"{Path.Combine(accountRoot, "project-a")}\"");
        Assert.Equal(0, ownProject.ExitCode);
        Observe("account-root-enumeration-denied", true);
    }

    [Fact]
    public async Task O_270713F3B6BC()
    {
        var childMarker = Path.Combine(_root, "child-marker.txt");
        using var cancellation = new CancellationTokenSource(TimeSpan.FromMilliseconds(500));
        var runner = new HostedProcessRunner();
        try
        {
            await runner.RunAsync(new HostedProcessCommand(
                "cmd.exe",
                ["/c", $"start \"\" /b cmd.exe /c \"timeout /t 3 > nul & echo child-survived>\\\"{childMarker}\\\"\" & timeout /t 30 > nul"],
                _root,
                new Dictionary<string, string>()), cancellation.Token);
        }
        catch (OperationCanceledException) { }

        await Task.Delay(TimeSpan.FromSeconds(4));
        Assert.False(File.Exists(childMarker), "FAILURE-O-270713F3B6BC: child outlived the runner cancellation.");
        Observe("children-terminated-after-parent", true);
    }

    private async Task AssertRunnerDeniedAsync(string resource, string operation, string failureId)
    {
        var protectedRoot = Path.Combine(_root, resource);
        Directory.CreateDirectory(protectedRoot);
        var target = Path.Combine(protectedRoot, "protected.txt");
        await File.WriteAllTextAsync(target, "platform-owned");
        GrantAdministratorsOnly(protectedRoot);
        var platformCommand = operation == "read"
            ? $"type \"{target}\""
            : $"echo platform-write>\"{target}\"";
        var platform = await RunPlatformAsync(platformCommand);
        Assert.Equal(0, platform.ExitCode);
        if (operation == "write") Assert.Equal("platform-write", (await File.ReadAllTextAsync(target)).Trim());
        if (operation == "write") await File.WriteAllTextAsync(target, "platform-owned");
        var command = operation == "read" ? $"type \"{target}\"" : $"echo runner-write>\"{target}\"";
        var result = await RunAsync(command);
        Assert.NotEqual(0, result.ExitCode);
        Assert.Equal("platform-owned", await File.ReadAllTextAsync(target));
        Observe($"os-denied:{resource}:{operation}", true);
    }

    private Task<HostedProcessResult> RunAsync(string command) => new HostedProcessRunner().RunAsync(
        new HostedProcessCommand("cmd.exe", ["/c", command], _root, new Dictionary<string, string>()));

    private static async Task<HostedProcessResult> RunPlatformAsync(string command)
    {
        using var process = Process.Start(new ProcessStartInfo("cmd.exe", $"/c {command}")
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

    private static void GrantAdministratorsOnly(string path) => ApplyAcl(path, "*S-1-5-32-544:(OI)(CI)F");

    private static void GrantUsersModify(string path) => ApplyAcl(path, "*S-1-5-32-545:(OI)(CI)M");

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
        try { Directory.Delete(_root, recursive: true); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }
}
