using PhaseA.Platform.Tests.NodeIdentity;
using System.Diagnostics;
using PhaseA.Platform.Runs;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S33BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S33BoundaryTests(ITestOutputHelper output) => _output = output;

    [Theory]
    [InlineData(0)]
    [InlineData(6000)]
    public async Task O_BD42DD72212F(int startupDelayMilliseconds)
    {
        await using var fixture = await S206AuthorityFixture.CreateAsync();
        using var current = S206TestSupport.EnterCurrentContext(fixture.Admin.Context);
        var queue = fixture.Queue();
        var root = Directory.CreateDirectory(Path.Combine(fixture.Admin.Project.RepoPath, "s33-cancel-" + Guid.NewGuid().ToString("N")));
        var started = Path.Combine(root.FullName, "started.txt");
        using var operationCancellation = new CancellationTokenSource();
        Task<HostedProcessResult>? operation = null;
        var cancellationRequested = false;
        var stoppedAfterCancellation = false;
        var queueClearedAfterCancellation = false;
        // ADR-0035/0061: exercise a real Windows child with the same lightweight
        // interpreter used by the HostedProcessRunner cancellation fixtures.
        var script = Path.Combine(root.FullName, "heavy-write.py");
        await File.WriteAllTextAsync(script, """
import pathlib
import sys
import time
time.sleep(int(sys.argv[2]) / 1000)
pathlib.Path(sys.argv[1]).write_text("started", encoding="utf-8")
time.sleep(30)
""");

        try
        {
            operation = queue.ExecuteAsync(
                fixture.Admin.RunId,
                fixture.Admin.AccountId,
                fixture.Admin.Project.ProjectId,
                "heavy-write",
                token => new HostedProcessRunner(authority: fixture.Store).RunAsync(new HostedProcessCommand(
                    "py",
                    ["-3", script, started, startupDelayMilliseconds.ToString(System.Globalization.CultureInfo.InvariantCulture)],
                    root.FullName,
                    new Dictionary<string, string>(),
                    RunId: fixture.Admin.RunId), token),
                operationCancellation.Token);

            // ADR-0035/0061: readiness is separate from the cancellation deadline.
            await WaitForFileAsync(started, operation, TimeSpan.FromSeconds(30));

            cancellationRequested = queue.CancelRun(fixture.Admin.RunId);
            // ADR-0035/0061: observe the actual cancellation/cleanup boundary,
            // rather than sampling a loaded Windows host after a fixed sleep.
            // A lost cancellation still fails: the real process sleeps 30s.
            await Assert.ThrowsAnyAsync<OperationCanceledException>(() => operation.WaitAsync(TimeSpan.FromSeconds(5)));
            stoppedAfterCancellation = operation.IsCanceled;
            var readback = queue.GetReadback(fixture.Admin.AccountId, includeAll: true);
            queueClearedAfterCancellation = !readback.Running &&
                                            readback.Current is null &&
                                            readback.QueuedCount == 0 &&
                                            readback.Items.Count == 0;
        }
        finally
        {
            operationCancellation.Cancel();
            if (operation is not null)
            {
                try
                {
                    await operation;
                }
                catch (OperationCanceledException)
                {
                }
            }

            DeleteDirectory(root.FullName);
        }

        Require(
            cancellationRequested && stoppedAfterCancellation && queueClearedAfterCancellation,
            "FAILURE-O-BD42DD72212F",
            "The production heavy-write queue accepted cancellation without stopping and releasing the running operation.");
        Observe($"O-BD42DD72212F startup-delay-ms={startupDelayMilliseconds} cancellation-stopped-running-operation-and-cleared-queue");
    }

    [Fact]
    public async Task O_8E338FFA23D1()
    {
        await using var fixture = await S206AuthorityFixture.CreateAsync();
        using var current = S206TestSupport.EnterCurrentContext(fixture.Admin.Context);
        var queue = fixture.Queue();
        var workStarted = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var allowTerminalWork = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var operation = queue.ExecuteAsync(
            fixture.Admin.RunId,
            fixture.Admin.AccountId,
            fixture.Admin.Project.ProjectId,
            "heavy-write",
            async _ =>
            {
                workStarted.TrySetResult(true);
                await allowTerminalWork.Task;
                return await new HostedProcessRunner(authority: fixture.Store).RunAsync(new HostedProcessCommand(
                    "cmd.exe",
                    ["/d", "/c", "echo S33_RUNNER_COMPLETED"],
                    fixture.Admin.Project.RepoPath,
                    new Dictionary<string, string>()));
            });

        await workStarted.Task.WaitAsync(TimeSpan.FromSeconds(5));
        var active = queue.GetReadback(fixture.Admin.AccountId, includeAll: true);
        allowTerminalWork.TrySetResult(true);
        var runnerResult = await operation;
        var cleaned = queue.GetReadback(fixture.Admin.AccountId, includeAll: true);

        Require(
            active.Running &&
            active.Current?.RunId == fixture.Admin.RunId &&
            runnerResult.ExitCode == 0 &&
            runnerResult.Stdout.Contains("S33_RUNNER_COMPLETED", StringComparison.Ordinal) &&
            !cleaned.Running &&
            cleaned.Current is null &&
            cleaned.QueuedCount == 0 &&
            cleaned.Items.Count == 0,
            "FAILURE-O-8E338FFA23D1",
            "The production heavy-write cleanup path did not release its active runner lifecycle resources after terminal work.");
        Observe("O-8E338FFA23D1 terminal-runner-completed-and-queue-lifecycle-cleared");
    }

    private static async Task WaitForFileAsync(string path, Task<HostedProcessResult> operation, TimeSpan timeout)
    {
        var elapsed = Stopwatch.StartNew();
        while (!File.Exists(path) && elapsed.Elapsed < timeout)
        {
            if (operation.IsCompleted)
            {
                var result = await operation;
                throw new InvalidOperationException(
                    $"S33 runner exited before readiness: exit={result.ExitCode}; stderr={result.Stderr}.");
            }

            await Task.Delay(25);
        }

        if (!File.Exists(path))
        {
            throw new TimeoutException(
                $"S33 runner did not publish readiness within {timeout.TotalSeconds:0} seconds; operation={operation.Status}.");
        }
    }

    private static void DeleteDirectory(string path)
    {
        try
        {
            if (Directory.Exists(path))
            {
                Directory.Delete(path, recursive: true);
            }
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    private void Observe(string observation) => _output.WriteLine($"S33-OBSERVATION {observation}");

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }
}
