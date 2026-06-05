using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class HeavyRunnerQueueServiceTests
{
    [Fact]
    public async Task ExecuteAsync_RunsHeavyWorkOneAtATimeInFifoOrder()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30));
        var waitTimeout = TimeSpan.FromSeconds(60);
        var firstCanFinish = new TaskCompletionSource();
        var firstStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var secondStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var order = new List<string>();

        var first = queue.ExecuteAsync(
            "run-1",
            "account-1",
            "project-1",
            "prototype-7day-playable",
            async _ =>
            {
                order.Add("first");
                firstStarted.SetResult();
                await firstCanFinish.Task;
                return "first";
            });

        await firstStarted.Task.WaitAsync(waitTimeout);

        var second = queue.ExecuteAsync(
            "run-2",
            "account-2",
            "project-2",
            "prototype-quick-fix",
            _ =>
            {
                order.Add("second");
                secondStarted.SetResult();
                return Task.FromResult("second");
            });

        var readback = queue.GetReadback("account-2", includeAll: false);
        Assert.True(readback.Running);
        Assert.Equal(1, readback.QueuedCount);
        Assert.Equal(1, readback.CurrentAccountPosition);
        Assert.Equal(30, readback.CurrentAccountEstimatedWaitSeconds);
        Assert.False(secondStarted.Task.IsCompleted);

        firstCanFinish.SetResult();

        Assert.Equal("first", await first.WaitAsync(waitTimeout));
        Assert.Equal("second", await second.WaitAsync(waitTimeout));
        Assert.Equal(["first", "second"], order);
        Assert.False(queue.GetReadback("account-2", includeAll: true).Running);
    }
}
