namespace PhaseA.Platform.Runs;

public sealed class HeavyRunnerQueueService
{
    private static readonly TimeSpan DefaultEstimatedTaskDuration = TimeSpan.FromMinutes(8);

    private readonly object _gate = new();
    private readonly Queue<HeavyRunnerQueueItem> _waiting = new();
    private readonly TimeSpan _estimatedTaskDuration;
    private HeavyRunnerQueueItem? _running;

    public HeavyRunnerQueueService()
        : this(DefaultEstimatedTaskDuration)
    {
    }

    public HeavyRunnerQueueService(TimeSpan? estimatedTaskDuration)
    {
        _estimatedTaskDuration = estimatedTaskDuration ?? DefaultEstimatedTaskDuration;
    }

    public async Task<T> ExecuteAsync<T>(
        string runId,
        string accountId,
        string projectId,
        string runType,
        Func<CancellationToken, Task<T>> work,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(runType);
        ArgumentNullException.ThrowIfNull(work);

        var item = new HeavyRunnerQueueItem(
            runId,
            accountId,
            projectId,
            runType,
            DateTimeOffset.UtcNow);

        Enqueue(item);
        await item.Ready.Task.WaitAsync(cancellationToken);

        try
        {
            return await work(cancellationToken);
        }
        finally
        {
            Complete(item);
        }
    }

    public async Task<IAsyncDisposable> EnterAsync(
        string runId,
        string accountId,
        string projectId,
        string runType,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(runType);

        var item = new HeavyRunnerQueueItem(
            runId,
            accountId,
            projectId,
            runType,
            DateTimeOffset.UtcNow);

        Enqueue(item);
        await item.Ready.Task.WaitAsync(cancellationToken);
        return new HeavyRunnerLease(this, item);
    }

    public HeavyRunnerQueueReadback GetReadback(string accountId, bool includeAll)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        lock (_gate)
        {
            var waiting = _waiting.ToArray();
            var visibleItems = waiting
                .Select((item, index) => ToReadbackItem(item, index + 1, includeAll || string.Equals(item.AccountId, accountId, StringComparison.Ordinal)))
                .Where(item => item is not null)
                .Cast<HeavyRunnerQueueItemReadback>()
                .ToArray();

            var currentAccountPosition = waiting
                .Select((item, index) => new { item, position = index + 1 })
                .FirstOrDefault(row => string.Equals(row.item.AccountId, accountId, StringComparison.Ordinal))
                ?.position;

            return new HeavyRunnerQueueReadback(
                _running is not null,
                _running is null ? null : ToReadbackItem(_running, 0, includeAll || string.Equals(_running.AccountId, accountId, StringComparison.Ordinal)),
                waiting.Length,
                currentAccountPosition,
                EstimateWaitSeconds(currentAccountPosition),
                visibleItems);
        }
    }

    private void Enqueue(HeavyRunnerQueueItem item)
    {
        lock (_gate)
        {
            _waiting.Enqueue(item);
            TryStartNextLocked();
        }
    }

    private void Complete(HeavyRunnerQueueItem item)
    {
        lock (_gate)
        {
            if (ReferenceEquals(_running, item))
            {
                _running = null;
            }

            TryStartNextLocked();
        }
    }

    private void TryStartNextLocked()
    {
        if (_running is not null || _waiting.Count == 0)
        {
            return;
        }

        _running = _waiting.Dequeue();
        _running.Ready.TrySetResult();
    }

    private int? EstimateWaitSeconds(int? position)
    {
        return position is null
            ? null
            : checked((int)Math.Ceiling(_estimatedTaskDuration.TotalSeconds * position.Value));
    }

    private int EstimateWaitSecondsForPosition(int position)
    {
        return checked((int)Math.Ceiling(_estimatedTaskDuration.TotalSeconds * position));
    }

    private HeavyRunnerQueueItemReadback? ToReadbackItem(HeavyRunnerQueueItem item, int position, bool visible)
    {
        if (!visible)
        {
            return null;
        }

        return new HeavyRunnerQueueItemReadback(
            item.RunId,
            item.AccountId,
            item.ProjectId,
            item.RunType,
            position,
            position <= 0 ? 0 : EstimateWaitSecondsForPosition(position),
            item.EnqueuedUtc.ToString("O"));
    }

    private sealed record HeavyRunnerQueueItem(
        string RunId,
        string AccountId,
        string ProjectId,
        string RunType,
        DateTimeOffset EnqueuedUtc)
    {
        public TaskCompletionSource Ready { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
    }

    private sealed class HeavyRunnerLease : IAsyncDisposable
    {
        private readonly HeavyRunnerQueueService _owner;
        private readonly HeavyRunnerQueueItem _item;
        private bool _disposed;

        public HeavyRunnerLease(HeavyRunnerQueueService owner, HeavyRunnerQueueItem item)
        {
            _owner = owner;
            _item = item;
        }

        public ValueTask DisposeAsync()
        {
            if (!_disposed)
            {
                _disposed = true;
                _owner.Complete(_item);
            }

            return ValueTask.CompletedTask;
        }
    }
}

public sealed record HeavyRunnerQueueReadback(
    bool Running,
    HeavyRunnerQueueItemReadback? Current,
    int QueuedCount,
    int? CurrentAccountPosition,
    int? CurrentAccountEstimatedWaitSeconds,
    IReadOnlyList<HeavyRunnerQueueItemReadback> Items);

public sealed record HeavyRunnerQueueItemReadback(
    string RunId,
    string AccountId,
    string ProjectId,
    string RunType,
    int Position,
    int EstimatedWaitSeconds,
    string EnqueuedUtc);
