using PhaseA.Platform.Runs;
using Xunit;
using Xunit.Abstractions;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S63BoundaryTests
{
    private readonly ITestOutputHelper _output;

    public S63BoundaryTests(ITestOutputHelper output) => _output = output;

    [Fact]
    public async Task O_AB9EF0D40F90()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(1), maxConcurrentRuns: 2);
        var firstStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var secondStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var releaseFirst = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var activeWriters = 0;
        var maximumConcurrentWriters = 0;

        async Task<string> WriteAsync(string writer, TaskCompletionSource? started, Task? release)
        {
            var active = Interlocked.Increment(ref activeWriters);
            UpdateMaximum(ref maximumConcurrentWriters, active);
            started?.TrySetResult();
            try
            {
                if (release is not null)
                {
                    await release;
                }

                return writer;
            }
            finally
            {
                Interlocked.Decrement(ref activeWriters);
            }
        }

        var first = queue.ExecuteAsync(
            "s63-first-writer",
            "s63-account",
            "s63-project",
            "heavy-write",
            _ => WriteAsync("first", firstStarted, releaseFirst.Task));

        await firstStarted.Task.WaitAsync(TimeSpan.FromSeconds(5));

        var second = queue.ExecuteAsync(
            "s63-second-writer",
            "s63-account",
            "s63-project",
            "heavy-write",
            _ => WriteAsync("second", secondStarted, null));

        await Task.WhenAny(secondStarted.Task, Task.Delay(TimeSpan.FromMilliseconds(500)));
        var secondWaitedForExclusivity = !secondStarted.Task.IsCompleted;
        var measuredConcurrentWriters = Volatile.Read(ref maximumConcurrentWriters);

        releaseFirst.TrySetResult();
        var completedWriters = await Task.WhenAll(first, second).WaitAsync(TimeSpan.FromSeconds(5));

        Require(
            measuredConcurrentWriters <= 1 &&
            secondWaitedForExclusivity &&
            completedWriters.SequenceEqual(["first", "second"]),
            "FAILURE-O-AB9EF0D40F90",
            "The production heavy-write queue admitted concurrent writers for one Project before the existing writer released exclusivity.");
        Observe("O-AB9EF0D40F90 per-project-heavy-writer-exclusivity-held-until-release");
    }

    private static void UpdateMaximum(ref int maximum, int candidate)
    {
        while (candidate > maximum)
        {
            var observed = Interlocked.CompareExchange(ref maximum, candidate, maximum);
            if (observed == maximum)
            {
                return;
            }
        }
    }

    private void Observe(string observation) => _output.WriteLine($"S63-OBSERVATION {observation}");

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }
}
