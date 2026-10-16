using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using System.ComponentModel;
using System.Text;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S2BoundaryTests
{
    private readonly ITestOutputHelper _output;
    public S2BoundaryTests(ITestOutputHelper output) => _output = output;
    [Fact]
    public async Task O_26DE8E588B36()
    {
        var root = Path.Combine(Path.GetTempPath(), "s2-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var output = Path.Combine(root, "output.txt");
        try
        {
            // ADR-0035/0061: the factory requires a registered, isolated Project Workspace.
            using var isolation = RunnerIsolationPolicy.PrepareWorkspace(new RunnerIsolationDescriptor(
                "account-a", "project-a", "phase-r-a-p", root,
                LowPrivilegeRequired: true, JobObjectRequired: true, NtfsAclRequired: true));
            // ADR-0035/0061: consume the prompt to EOF before completing the runner stdin contract.
            var probe = Path.Combine(root, "s2-probe.cmd");
            await File.WriteAllTextAsync(probe,
                $"@echo off\r\necho S2_PROCESS_STARTED\r\npowershell.exe -NoProfile -NonInteractive -Command \"$null = [Console]::In.ReadToEnd()\"\r\necho s2-ok>\"{output}\"\r\n",
                Encoding.ASCII);
            var request = new CodexHostedProcessRequest(root, output, "", "test-model", "low");
            var command = CodexHostedProcessCommandFactory.Build(request with { Prompt = "write harmless marker" });
            var runner = new HostedProcessRunner();
            HostedProcessResult result;
            try
            {
                result = await runner.RunAsync(command with { FileName = "cmd.exe", Arguments = ["/d", "/c", probe] });
            }
            catch (Win32Exception error)
            {
                throw new Xunit.Sdk.XunitException($"S2 runner initialization failed before the file operation: win32={error.NativeErrorCode} hresult=0x{error.HResult:X8} message={error.Message}");
            }
            catch (InvalidOperationException error)
            {
                throw new Xunit.Sdk.XunitException($"S2 runner initialization failed before the file operation: {error.Message}");
            }
            Assert.Contains("S2_PROCESS_STARTED", result.Stdout);
            if (result.ExitCode != 0 || !File.Exists(output) ||
                !(await File.ReadAllTextAsync(output)).Contains("s2-ok", StringComparison.Ordinal))
            {
                throw new Xunit.Sdk.XunitException(
                    $"FAILURE-O-26DE8E588B36: isolated harmless file operation failed; exit={result.ExitCode} stderr={result.Stderr}");
            }
            _output.WriteLine("S2_OBSERVATION:0,true,true");
        }
        finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
    }
}
