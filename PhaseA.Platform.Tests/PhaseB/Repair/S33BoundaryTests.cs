using PhaseA.Platform.Runs;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S33BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S33BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_BD42DD72212F()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(1), maxConcurrentRuns: 1);
        var root = Directory.CreateTempSubdirectory("s33-cancel-");
        var started = Path.Combine(root.FullName, "started.txt");
        using var operationCancellation = new CancellationTokenSource();
        Task<HostedProcessResult>? operation = null;
        var cancellationRequested = false;
        var stoppedAfterCancellation = false;
        var queueClearedAfterCancellation = false;

        try
        {
            operation = queue.ExecuteAsync(
                "s33-cancel-run",
                "s33-account",
                "s33-project",
                "heavy-write",
                token => new HostedProcessRunner().RunAsync(new HostedProcessCommand(
                    "powershell.exe",
                    ["-NoProfile", "-NonInteractive", "-Command", $"[IO.File]::WriteAllText('{started}', 'started'); Start-Sleep -Seconds 30"],
                    root.FullName,
                    new Dictionary<string, string>(),
                    RunId: "s33-cancel-run"), token),
                operationCancellation.Token);

            await WaitForFileAsync(started, TimeSpan.FromSeconds(5));
            if (!File.Exists(started))
            {
                throw new InvalidOperationException("S33 cancellation fixture did not start the real heavy-write runner.");
            }

            cancellationRequested = queue.CancelRun("s33-cancel-run");
            await Task.Delay(300);
            stoppedAfterCancellation = operation.IsCompleted;
            var readback = queue.GetReadback("s33-account", includeAll: true);
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
        Observe("O-BD42DD72212F cancellation-stopped-running-operation-and-cleared-queue");
    }

    [Fact]
    public async Task O_8E338FFA23D1()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(1), maxConcurrentRuns: 1);
        var workStarted = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var allowTerminalWork = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var operation = queue.ExecuteAsync(
            "s33-cleanup-run",
            "s33-account",
            "s33-project",
            "heavy-write",
            async _ =>
            {
                workStarted.TrySetResult(true);
                await allowTerminalWork.Task;
                return await new HostedProcessRunner().RunAsync(new HostedProcessCommand(
                    "cmd.exe",
                    ["/d", "/c", "echo S33_RUNNER_COMPLETED"],
                    Path.GetTempPath(),
                    new Dictionary<string, string>()));
            });

        await workStarted.Task.WaitAsync(TimeSpan.FromSeconds(5));
        var active = queue.GetReadback("s33-account", includeAll: true);
        allowTerminalWork.TrySetResult(true);
        var runnerResult = await operation;
        var cleaned = queue.GetReadback("s33-account", includeAll: true);

        Require(
            active.Running &&
            active.Current?.RunId == "s33-cleanup-run" &&
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

    private static async Task WaitForFileAsync(string path, TimeSpan timeout)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (!File.Exists(path) && DateTime.UtcNow < deadline)
        {
            await Task.Delay(25);
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
