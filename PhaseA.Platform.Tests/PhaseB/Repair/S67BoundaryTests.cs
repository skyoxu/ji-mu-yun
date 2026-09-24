using PhaseA.Platform.Runs;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S67BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S67BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_1887FF4A80D2()
    {
        const string controlledSecretName = "S67_CONTROLLED_RUN_SECRET";
        const string controlledSecretValue = "s67-controlled-fixture";
        const string platformSecretName = "S67_PLATFORM_FIXTURE_SECRET";
        const string platformSecretValue = "s67-platform-fixture-must-not-dispatch";
        var previousPlatformSecret = Environment.GetEnvironmentVariable(platformSecretName);
        try
        {
            Environment.SetEnvironmentVariable(platformSecretName, platformSecretValue);
            var result = await new HostedProcessRunner().RunAsync(new HostedProcessCommand(
                "cmd.exe",
                ["/d", "/c", "set S67_"],
                Path.GetTempPath(),
                new Dictionary<string, string> { [controlledSecretName] = controlledSecretValue }));

            Require(
                result.ExitCode == 0 &&
                result.Stdout.Contains($"{controlledSecretName}={controlledSecretValue}", StringComparison.Ordinal) &&
                !result.Stdout.Contains(platformSecretName, StringComparison.Ordinal) &&
                !result.Stdout.Contains(platformSecretValue, StringComparison.Ordinal),
                "FAILURE-O-1887FF4A80D2",
                "The production Runner dispatch did not expose only the controlled fixture secret scope.");
            Observe("O-1887FF4A80D2 runner-dispatched-controlled-secret-only");
        }
        finally
        {
            Environment.SetEnvironmentVariable(platformSecretName, previousPlatformSecret);
        }
    }

    [Fact]
    public async Task O_62BC40D98DBD()
    {
        const string cleanupSecretName = "S67_FAILED_CLEANUP_SECRET";
        var runner = new HostedProcessRunner();
        var cleanupFailure = await runner.RunAsync(new HostedProcessCommand(
            "cmd.exe",
            ["/d", "/c", "echo S67_CLEANUP_FAILURE_REPORTED & exit /b 23"],
            Path.GetTempPath(),
            new Dictionary<string, string> { [cleanupSecretName] = "s67-failed-cleanup-fixture" }));
        var reuseAttempt = await runner.RunAsync(new HostedProcessCommand(
            "cmd.exe",
            ["/d", "/c", "echo S67_REUSE_DISPATCH_STARTED"],
            Path.GetTempPath(),
            new Dictionary<string, string>()));

        Require(
            cleanupFailure.ExitCode == 23 &&
            cleanupFailure.Stdout.Contains("S67_CLEANUP_FAILURE_REPORTED", StringComparison.Ordinal) &&
            reuseAttempt.ExitCode != 0 &&
            !reuseAttempt.Stdout.Contains("S67_REUSE_DISPATCH_STARTED", StringComparison.Ordinal),
            "FAILURE-O-62BC40D98DBD",
            "The production Runner accepted a new dispatch after the Run cleanup failure was reported.");
        Observe("O-62BC40D98DBD cleanup-failure-blocked-reuse-dispatch");
    }

    [Fact]
    public async Task O_664BBD21B5E8()
    {
        const string completionSecretName = "S67_COMPLETION_SECRET";
        const string completionSecretValue = "s67-completion-fixture";
        var runner = new HostedProcessRunner();
        var completion = await runner.RunAsync(new HostedProcessCommand(
            "cmd.exe",
            ["/d", "/c", "set S67_COMPLETION_SECRET"],
            Path.GetTempPath(),
            new Dictionary<string, string> { [completionSecretName] = completionSecretValue }));
        var completedContextProbe = await runner.RunAsync(new HostedProcessCommand(
            "cmd.exe",
            ["/d", "/c", "if defined S67_COMPLETION_SECRET echo S67_COMPLETION_SECRET_RETAINED"],
            Path.GetTempPath(),
            new Dictionary<string, string>()));

        Require(
            completion.ExitCode == 0 &&
            completion.Stdout.Contains($"{completionSecretName}={completionSecretValue}", StringComparison.Ordinal) &&
            completedContextProbe.ExitCode == 0 &&
            !completedContextProbe.Stdout.Contains("S67_COMPLETION_SECRET_RETAINED", StringComparison.Ordinal) &&
            !completedContextProbe.Stdout.Contains(completionSecretValue, StringComparison.Ordinal),
            "FAILURE-O-664BBD21B5E8",
            "The completed production Runner context still exposed its fixture Run secret.");
        Observe("O-664BBD21B5E8 completion-cleaned-run-secret");
    }

    private void Observe(string observation) => _output.WriteLine($"S67-OBSERVATION {observation}");

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }
}
