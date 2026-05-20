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
        using var timeout = new CancellationTokenSource(TimeSpan.FromMilliseconds(300));
        var command = new HostedProcessCommand(
            "py",
            ["-3", script],
            temp.Path,
            new Dictionary<string, string>());

        var act = async () => await runner.RunAsync(command, timeout.Token);

        await act.Should().ThrowAsync<OperationCanceledException>();
        File.Exists(marker).Should().BeTrue();
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
