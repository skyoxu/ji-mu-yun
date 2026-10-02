using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class HeavyRunnerQueueServiceTests
{
    [Fact]
    public async Task TryEnter_RespectsEveryActiveProjectCapacityAndWaitingWork()
    {
        // ADR-0036: recovery is nonblocking and uses the same project ownership as execution.
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(1), maxConcurrentRuns: 3);
        await using var first = await queue.EnterAsync("first", "account", "project-1", "work");
        await using var second = await queue.EnterAsync("second", "account", "project-2", "work");
        Assert.Null(queue.TryEnter("same-second-project", "account", "project-2", "recovery"));

        await using var third = queue.TryEnter("third", "account", "project-3", "recovery");
        Assert.NotNull(third);
        Assert.Null(queue.TryEnter("at-capacity", "account", "project-4", "recovery"));
        await third!.DisposeAsync();

        using var cancellation = new CancellationTokenSource();
        var waiting = queue.EnterAsync("waiting", "account", "project-1", "work", cancellation.Token);
        Assert.Equal(1, queue.GetReadback("account", includeAll: true).QueuedCount);
        Assert.Null(queue.TryEnter("bypass-waiting", "account", "project-4", "recovery"));
        cancellation.Cancel();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => waiting);

        await using var available = queue.TryEnter("available", "account", "project-4", "recovery");
        Assert.NotNull(available);
        Assert.Null(queue.TryEnter("same-available-project", "account", "project-4", "recovery"));
        await available!.DisposeAsync();
        Assert.Equal(0, queue.GetReadback("account", includeAll: true).QueuedCount);
        await second.DisposeAsync();
        await first.DisposeAsync();
        Assert.False(queue.GetReadback("account", includeAll: true).Running);
    }

    [Fact]
    public async Task ExecuteAsync_RunsHeavyWorkOneAtATimeInFifoOrder()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1);
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

    [Fact]
    public async Task ExecuteAsync_UsesConfiguredOtherRunConcurrency()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 2);
        var waitTimeout = TimeSpan.FromSeconds(60);
        var firstCanFinish = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var secondCanFinish = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var firstStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var secondStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var thirdStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);

        var first = queue.ExecuteAsync(
            "run-1",
            "account-1",
            "project-1",
            "prototype-7day-playable",
            async _ =>
            {
                firstStarted.SetResult();
                await firstCanFinish.Task;
                return "first";
            });

        var second = queue.ExecuteAsync(
            "run-2",
            "account-2",
            "project-2",
            "prototype-quick-fix",
            async _ =>
            {
                secondStarted.SetResult();
                await secondCanFinish.Task;
                return "second";
            });

        await firstStarted.Task.WaitAsync(waitTimeout);
        await secondStarted.Task.WaitAsync(waitTimeout);

        var third = queue.ExecuteAsync(
            "run-3",
            "account-3",
            "project-3",
            "prototype-ui-optimization",
            _ =>
            {
                thirdStarted.SetResult();
                return Task.FromResult("third");
            });

        var readback = queue.GetReadback("account-3", includeAll: true);
        Assert.True(readback.Running);
        Assert.Equal(1, readback.QueuedCount);
        Assert.Equal(1, readback.CurrentAccountPosition);
        Assert.False(thirdStarted.Task.IsCompleted);

        firstCanFinish.SetResult();

        Assert.Equal("first", await first.WaitAsync(waitTimeout));
        await thirdStarted.Task.WaitAsync(waitTimeout);
        Assert.Equal("third", await third.WaitAsync(waitTimeout));

        secondCanFinish.SetResult();
        Assert.Equal("second", await second.WaitAsync(waitTimeout));
    }

    [Fact]
    public async Task ExecuteAsync_RemovesCancelledWaitingItemFromQueue()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1);
        var waitTimeout = TimeSpan.FromSeconds(60);
        var firstCanFinish = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var firstStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var thirdStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);

        var first = queue.ExecuteAsync(
            "run-1",
            "account-1",
            "project-1",
            "prototype-7day-playable",
            async _ =>
            {
                firstStarted.SetResult();
                await firstCanFinish.Task;
                return "first";
            });

        await firstStarted.Task.WaitAsync(waitTimeout);

        using var cancelled = new CancellationTokenSource();
        var second = queue.ExecuteAsync(
            "run-2",
            "account-2",
            "project-2",
            "prototype-quick-fix",
            _ => Task.FromResult("second"),
            cancelled.Token);

        var readbackBeforeCancel = queue.GetReadback("account-2", includeAll: true);
        Assert.Equal(1, readbackBeforeCancel.QueuedCount);

        await cancelled.CancelAsync();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => second.WaitAsync(waitTimeout));

        var third = queue.ExecuteAsync(
            "run-3",
            "account-3",
            "project-3",
            "prototype-ui-optimization",
            _ =>
            {
                thirdStarted.SetResult();
                return Task.FromResult("third");
            });

        var readbackAfterCancel = queue.GetReadback("account-3", includeAll: true);
        Assert.Equal(1, readbackAfterCancel.QueuedCount);

        firstCanFinish.SetResult();

        Assert.Equal("first", await first.WaitAsync(waitTimeout));
        await thirdStarted.Task.WaitAsync(waitTimeout);
        Assert.Equal("third", await third.WaitAsync(waitTimeout));
        Assert.Equal(0, queue.GetReadback("account-3", includeAll: true).QueuedCount);
    }

    [Fact]
    public async Task ExecuteAsync_ExposesQueuePositionAtStart()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30), maxConcurrentRuns: 1);
        var waitTimeout = TimeSpan.FromSeconds(60);
        var firstCanFinish = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var firstStarted = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var secondStartedPosition = new TaskCompletionSource<int>(TaskCreationOptions.RunContinuationsAsynchronously);

        var first = queue.ExecuteAsync(
            "run-1",
            "account-1",
            "project-1",
            "prototype-7day-playable",
            async (start, _) =>
            {
                Assert.Equal(1, start.QueuePositionAtStart);
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
            (start, _) =>
            {
                secondStartedPosition.SetResult(start.QueuePositionAtStart);
                return Task.FromResult("second");
            });

        firstCanFinish.SetResult();

        Assert.Equal("first", await first.WaitAsync(waitTimeout));
        Assert.Equal("second", await second.WaitAsync(waitTimeout));
        Assert.Equal(2, await secondStartedPosition.Task.WaitAsync(waitTimeout));
    }

    [Fact]
    public async Task EnterAsync_ExposesQueuePositionAtStart()
    {
        var queue = new HeavyRunnerQueueService(TimeSpan.FromSeconds(30));
        await using var lease = await queue.EnterAsync(
            "run-1",
            "account-1",
            "project-1",
            "prototype-7day-playable");

        Assert.Equal(1, lease.QueuePositionAtStart);
    }
}
