using FluentAssertions;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class HostedProcessRunnerTests
{
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
    }

    [Fact]
    public async Task RunAsync_DoesNotHitInactivityTimeout_WhenWatchedFileChanges()
    {
        using var temp = TempDirectory.Create("phase-a-file-activity");
        var marker = Path.Combine(temp.Path, "activity", "marker.txt");
        var script = Path.Combine(temp.Path, "touch-marker.py");
        await File.WriteAllTextAsync(script, $"""
import pathlib
import time
path = pathlib.Path(r"{marker}")
path.parent.mkdir(parents=True, exist_ok=True)
for index in range(12):
    path.write_text("x" * (index + 1), encoding="utf-8")
    time.sleep(0.05)
""");
        var runner = new HostedProcessRunner();
        var command = new HostedProcessCommand(
            "py",
            ["-3", script],
            temp.Path,
            new Dictionary<string, string>())
            .WithTimeouts(
                totalTimeout: TimeSpan.FromSeconds(5),
                inactivityTimeout: TimeSpan.FromMilliseconds(500))
            .WithActivityWatchPaths(["activity"], pollInterval: TimeSpan.FromMilliseconds(25));

        var result = await runner.RunAsync(command);

        result.ExitCode.Should().Be(0, result.Stderr);
        File.ReadAllText(marker).Should().Be(new string('x', 12));
    }

    [Fact]
    public async Task RunAsync_ReturnsTimeout_WhenTotalRuntimeExceedsLimitEvenWithOutput()
    {
        using var temp = TempDirectory.Create("phase-a-total-timeout");
        // ADR-0061: emit immediately from the measured process. Python launcher's
        // interpreter startup can consume the entire 120ms budget on Windows CI.
        var script = Path.Combine(temp.Path, "noisy-loop.cmd");
        await File.WriteAllTextAsync(script, """
@echo off
:repeat
echo tick
goto repeat
""");
        var runner = new HostedProcessRunner();
        var command = new HostedProcessCommand(
            "cmd.exe",
            ["/d", "/c", script],
            temp.Path,
            new Dictionary<string, string>())
            .WithTimeouts(
                totalTimeout: TimeSpan.FromMilliseconds(120),
                inactivityTimeout: TimeSpan.FromSeconds(5));

        var result = await runner.RunAsync(command);

        result.ExitCode.Should().Be(408);
        result.Stdout.Should().Contain("tick");
        result.Stderr.Should().Contain("total timeout");
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
