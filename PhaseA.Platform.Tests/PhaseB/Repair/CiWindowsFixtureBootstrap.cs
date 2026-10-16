using System.Runtime.CompilerServices;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

// ADR-0061: prepare the existing Windows fixtures only on disposable hosted CI.
internal static class CiWindowsFixtureBootstrap
{
    private static TestRunnerCredentialScope? _baseline;

    [ModuleInitializer]
    internal static void Initialize()
    {
        if (Environment.GetEnvironmentVariable("PHASEA_CI_FIXTURES") != "1") return;
        if (!OperatingSystem.IsWindows() ||
            Environment.GetEnvironmentVariable("GITHUB_ACTIONS") != "true" ||
            Environment.GetEnvironmentVariable("RUNNER_ENVIRONMENT") != "github-hosted")
            throw new InvalidOperationException("CI Windows fixtures require a disposable GitHub-hosted Windows runner.");

        // Child fault-injection processes inherit the owner's prepared boundary.
        // They must neither recreate nor delete the parent's named test account.
        if (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("PHASEA_CI_BASELINE_OWNER_PID"))) return;
        _baseline = TestRunnerCredentialScope.CreateCiBaseline();
        Environment.SetEnvironmentVariable("PHASEA_CI_BASELINE_OWNER_PID", Environment.ProcessId.ToString());
        var root = Path.Combine(Path.GetTempPath(), "phasea-ci-fixtures-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        Environment.SetEnvironmentVariable("S35_TEST_ROOT", root);
        AppDomain.CurrentDomain.ProcessExit += (_, _) =>
        {
            _baseline?.Dispose();
            if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
        };
    }
}
