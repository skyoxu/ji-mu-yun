using FluentAssertions;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class HostedProcessRunnerTests
{
    // ADR-0035/0061: a tool failure does not imply cleanup failure.
    [Fact]
    public async Task RunAsync_AllowsNextDispatchAfterNormalNonzeroExit()
    {
        using var temp = TempDirectory.Create("phase-a-nonzero-retry");
        var runner = new HostedProcessRunner();
        var command = new HostedProcessCommand("cmd.exe", ["/d", "/c", "exit 7"], temp.Path, new Dictionary<string, string>());
        var failed = await runner.RunAsync(command);
        var next = await runner.RunAsync(command with { Arguments = ["/d", "/c", "echo RETRY_STARTED"] });
        failed.ExitCode.Should().Be(7);
        next.ExitCode.Should().Be(0, next.Stderr);
        next.Stdout.Should().Contain("RETRY_STARTED");
    }

    [Fact]
    public async Task RunAsync_WritesStandardInputAsUtf8()
    {
        using var temp = TempDirectory.Create("phase-a-stdin");
        var script = Path.Combine(temp.Path, "read-stdin.py");
        await File.WriteAllTextAsync(script, """
import sys
data = sys.stdin.buffer.read()
text = data.decode("utf-8")
if data.startswith(b"\\xef\\xbb\\xbf"):
    raise SystemExit("stdin_has_bom")
print("ok")
""");
        var runner = new HostedProcessRunner();
        var command = new HostedProcessCommand(
            "py",
            ["-3", script],
            temp.Path,
            new Dictionary<string, string>(),
            "目标 1：稳定移动并进入第一次遇敌");

        var result = await runner.RunAsync(command);

        result.ExitCode.Should().Be(0, result.Stderr);
        result.Stdout.Should().Contain("ok");
    }

    [Fact]
    public async Task RunAsync_KillsProcessTree_WhenCanceled()
    {
        using var temp = TempDirectory.Create("phase-a-cancel");
        var marker = Path.Combine(temp.Path, "marker.txt");
        var script = Path.Combine(temp.Path, "sleep.py");
        await File.WriteAllTextAsync(script, $"""
import pathlib
import time
pathlib.Path(r"{marker}").write_text("started")
time.sleep(30)
""");
        var runner = new HostedProcessRunner();
        using var timeout = new CancellationTokenSource();
        var command = new HostedProcessCommand(
            "py",
            ["-3", script],
            temp.Path,
            new Dictionary<string, string>());

        var runTask = runner.RunAsync(command, timeout.Token);
        await WaitForFileAsync(marker);
        await timeout.CancelAsync();

        var act = async () => await runTask;
        await act.Should().ThrowAsync<OperationCanceledException>();
        File.Exists(marker).Should().BeTrue();
        var retry = await runner.RunAsync(command with { Arguments = ["-3", "-c", "print('retry-after-cancel')"] });
        retry.ExitCode.Should().Be(0, retry.Stderr);
    }

    [Fact]
    public async Task RunAsync_ReturnsTimeout_WhenProcessHasNoOutputForInactivityWindow()
    {
        using var temp = TempDirectory.Create("phase-a-inactivity-timeout");
        var script = Path.Combine(temp.Path, "silent-sleep.py");
        await File.WriteAllTextAsync(script, """
import time
time.sleep(30)
""");
        var runner = new HostedProcessRunner();
        var command = new HostedProcessCommand(
            "py",
            ["-3", script],
            temp.Path,
            new Dictionary<string, string>())
            .WithTimeouts(inactivityTimeout: TimeSpan.FromMilliseconds(50));

        var result = await runner.RunAsync(command);

        result.ExitCode.Should().Be(408);
        result.Stderr.Should().Contain("no stdout, stderr, or watched file activity");
        var retry = await runner.RunAsync(command with { FileName = "cmd.exe", Arguments = ["/d", "/c", "exit 0"], InactivityTimeout = null });
        retry.ExitCode.Should().Be(0, retry.Stderr);
    }

    [Fact]
    public async Task RunAsync_DoesNotHitInactivityTimeout_WhenWatchedFileChanges()
    {
        using var temp = TempDirectory.Create("phase-a-file-activity");
        var marker = Path.Combine(temp.Path, "activity", "marker.txt");
        Directory.CreateDirectory(Path.GetDirectoryName(marker)!);
        var script = Path.Combine(temp.Path, "silent-wait.cmd");
        // ADR-0061: let the measured child produce its own watched activity.
        // The same silent script must time out without watching and finish with
        // watching; a delayed test continuation cannot create a false timeout.
        await File.WriteAllTextAsync(script, $"""
@echo off
for /l %%i in (1,1,8) do (
    echo %%i >"{marker}"
    ping.exe -n 2 127.0.0.1 >nul
)
""");
        var runner = new HostedProcessRunner();
        var command = new HostedProcessCommand(
            "cmd.exe",
            ["/d", "/c", script],
            temp.Path,
            new Dictionary<string, string>())
            .WithTimeouts(
                totalTimeout: TimeSpan.FromSeconds(60),
                inactivityTimeout: TimeSpan.FromSeconds(5));

        var unwatched = await runner.RunAsync(command);
        unwatched.ExitCode.Should().Be(408, unwatched.Stderr);
        unwatched.Stdout.Should().BeEmpty();
        unwatched.Stderr.Should().Contain("no stdout, stderr, or watched file activity");
        File.Delete(marker);

        var result = await runner.RunAsync(command.WithActivityWatchPaths(
            ["activity"], pollInterval: TimeSpan.FromMilliseconds(100)));

        result.ExitCode.Should().Be(0, result.Stderr);
        result.Stdout.Should().BeEmpty();
        File.ReadAllText(marker).Trim().Should().Be("8");
    }

    [Fact]
    public async Task RunAsync_ReturnsTimeout_WhenTotalRuntimeExceedsLimitEvenWithOutput()
    {
        using var temp = TempDirectory.Create("phase-a-total-timeout");
        // ADR-0061: exercise a real deadline while allowing Windows CI startup.
        // Emit once per second rather than flooding redirected output. Activity
        // must not extend the total deadline or turn it into an inactivity exit.
        var script = Path.Combine(temp.Path, "noisy-loop.cmd");
        await File.WriteAllTextAsync(script, """
@echo off
:repeat
echo tick
ping.exe -n 2 127.0.0.1 >nul
goto repeat
""");
        var runner = new HostedProcessRunner();
        var command = new HostedProcessCommand(
            "cmd.exe",
            ["/d", "/c", script],
            temp.Path,
            new Dictionary<string, string>())
            .WithTimeouts(
                totalTimeout: TimeSpan.FromSeconds(5),
                inactivityTimeout: TimeSpan.FromSeconds(15))
            .WithActivityWatchPaths([], pollInterval: TimeSpan.FromMilliseconds(100));

        var result = await runner.RunAsync(command);

        result.ExitCode.Should().Be(408);
        result.Stdout.Should().Contain("tick");
        result.Stderr.Should().Contain("total timeout");
        var retry = await runner.RunAsync(command with { Arguments = ["/d", "/c", "exit 0"], TotalTimeout = null });
        retry.ExitCode.Should().Be(0, retry.Stderr);
    }

    private static async Task WaitForFileAsync(string path)
    {
        var deadline = DateTimeOffset.UtcNow.AddSeconds(5);
        while (DateTimeOffset.UtcNow < deadline)
        {
            if (File.Exists(path))
            {
                return;
            }

            await Task.Delay(25);
        }

        File.Exists(path).Should().BeTrue();
    }

    private sealed class TempDirectory : IDisposable
    {
        private TempDirectory(string path)
        {
            Path = path;
        }

        public string Path { get; }

        public static TempDirectory Create(string prefix)
        {
            var path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"{prefix}-{Guid.NewGuid():N}");
            Directory.CreateDirectory(path);
            return new TempDirectory(path);
        }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
