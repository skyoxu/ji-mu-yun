using PhaseA.Platform.Security;

namespace PhaseA.Platform.Runs;

public sealed class HeavyRunnerQueueService
{
    private static readonly TimeSpan DefaultEstimatedTaskDuration = TimeSpan.FromMinutes(8);
    public const int DefaultMaxConcurrentOtherRuns = 3;

    private readonly object _gate = new();
    private readonly Queue<HeavyRunnerQueueItem> _waiting = new();
    private readonly TimeSpan _estimatedTaskDuration;
    private readonly int _maxConcurrentRuns;
    private readonly List<HeavyRunnerQueueItem> _running = [];

    public HeavyRunnerQueueService()
        : this(DefaultEstimatedTaskDuration, DefaultMaxConcurrentOtherRuns)
    {
    }

    public HeavyRunnerQueueService(TimeSpan? estimatedTaskDuration, int maxConcurrentRuns = DefaultMaxConcurrentOtherRuns)
    {
        if (maxConcurrentRuns <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxConcurrentRuns));
        }

        _estimatedTaskDuration = estimatedTaskDuration ?? DefaultEstimatedTaskDuration;
        _maxConcurrentRuns = maxConcurrentRuns;
    }

    public async Task<T> ExecuteAsync<T>(
        string runId,
        string accountId,
        string projectId,
        string runType,
        Func<CancellationToken, Task<T>> work,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(work);

        return await ExecuteAsync(
            runId,
            accountId,
            projectId,
            runType,
            (_, token) => work(token),
            cancellationToken);
    }

    public async Task<T> ExecuteAuthorizedAsync<T>(
        string runId,
        string accountId,
        string projectId,
        string runType,
        RequestContext context,
        Func<RequestContext, CancellationToken, Task<bool>> reauthorizeAtStart,
        Func<CancellationToken, Task<T>> work,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(reauthorizeAtStart);
        context.DemandAccount(accountId);

        return await ExecuteAsync(
            runId,
            accountId,
            projectId,
            runType,
            async token =>
            {
                if (!await reauthorizeAtStart(context, token))
                {
                    throw new UnauthorizedAccessException("queued work is no longer authorized at execution");
                }

                return await work(token);
            },
            cancellationToken);
    }

    public async Task<T> ExecuteAsync<T>(
        string runId,
        string accountId,
        string projectId,
        string runType,
        Func<HeavyRunnerStartContext, CancellationToken, Task<T>> work,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(runType);
        ArgumentNullException.ThrowIfNull(work);

        using var itemCancellation = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        var item = new HeavyRunnerQueueItem(
            runId,
            accountId,
            projectId,
            runType,
            DateTimeOffset.UtcNow,
            itemCancellation);

        Enqueue(item);
        try
        {
            await item.Ready.Task.WaitAsync(itemCancellation.Token);
        }
        catch
        {
            Cancel(item);
            throw;
        }

        try
        {
            return await work(new HeavyRunnerStartContext(item.QueuePositionAtStart), itemCancellation.Token);
        }
        finally
        {
            Complete(item);
        }
    }

    public async Task<HeavyRunnerLease> EnterAsync(
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

        var itemCancellation = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        var item = new HeavyRunnerQueueItem(
            runId,
            accountId,
            projectId,
            runType,
            DateTimeOffset.UtcNow,
            itemCancellation);

        Enqueue(item);
        try
        {
            await item.Ready.Task.WaitAsync(itemCancellation.Token);
        }
        catch
        {
            Cancel(item);
            itemCancellation.Dispose();
            throw;
        }

        return new HeavyRunnerLease(item.QueuePositionAtStart, () =>
        {
            Complete(item);
            itemCancellation.Dispose();
        });
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
            var current = _running
                .Select(item => ToReadbackItem(item, 0, includeAll || string.Equals(item.AccountId, accountId, StringComparison.Ordinal)))
                .FirstOrDefault(item => item is not null);

            return new HeavyRunnerQueueReadback(
                _running.Count > 0,
                current,
                waiting.Length,
                currentAccountPosition,
                EstimateWaitSeconds(currentAccountPosition),
                visibleItems);
        }
    }

    public bool CancelRun(string runId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);

        lock (_gate)
        {
            var running = _running.FirstOrDefault(item => string.Equals(item.RunId, runId, StringComparison.Ordinal));
            if (running is not null)
            {
                running.Cancellation.Cancel();
                return true;
            }

            var cancelled = false;
            var retained = new List<HeavyRunnerQueueItem>();
            while (_waiting.Count > 0)
            {
                var waiting = _waiting.Dequeue();
                if (string.Equals(waiting.RunId, runId, StringComparison.Ordinal))
                {
                    waiting.Cancellation.Cancel();
                    waiting.Ready.TrySetCanceled();
                    cancelled = true;
                    continue;
                }

                retained.Add(waiting);
            }

            foreach (var waiting in retained)
            {
                _waiting.Enqueue(waiting);
            }

            return cancelled;
        }
    }

    private void Enqueue(HeavyRunnerQueueItem item)
    {
        lock (_gate)
        {
            item.QueuePositionAtStart = _running.Count + _waiting.Count + 1;
            _waiting.Enqueue(item);
            TryStartNextLocked();
        }
    }

    private void Complete(HeavyRunnerQueueItem item)
    {
        lock (_gate)
        {
            _running.Remove(item);

            TryStartNextLocked();
        }
    }

    private void Cancel(HeavyRunnerQueueItem item)
    {
        lock (_gate)
        {
            if (_running.Remove(item))
            {
                TryStartNextLocked();
                return;
            }

            var retained = _waiting.Where(waiting => !ReferenceEquals(waiting, item)).ToArray();
            if (retained.Length == _waiting.Count)
            {
                return;
            }

            _waiting.Clear();
            foreach (var waiting in retained)
            {
                _waiting.Enqueue(waiting);
            }
        }
    }

    private void TryStartNextLocked()
    {
        while (_running.Count < _maxConcurrentRuns)
        {
            var next = DequeueNextEligibleLocked();
            if (next is null)
            {
                return;
            }

            _running.Add(next);
            next.Ready.TrySetResult();
        }
    }

    private HeavyRunnerQueueItem? DequeueNextEligibleLocked()
    {
        var next = _waiting.FirstOrDefault(candidate => _running.All(running =>
            !string.Equals(running.ProjectId, candidate.ProjectId, StringComparison.Ordinal)));
        if (next is null)
        {
            return null;
        }

        var retained = _waiting.Where(candidate => !ReferenceEquals(candidate, next)).ToArray();
        _waiting.Clear();
        foreach (var waiting in retained)
        {
            _waiting.Enqueue(waiting);
        }

        return next;
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
        DateTimeOffset EnqueuedUtc,
        CancellationTokenSource Cancellation)
    {
        public TaskCompletionSource Ready { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public int QueuePositionAtStart { get; set; }
    }

    public sealed class HeavyRunnerLease : IAsyncDisposable
    {
        private readonly Action _complete;
        private bool _disposed;

        internal HeavyRunnerLease(int queuePositionAtStart, Action complete)
        {
            QueuePositionAtStart = queuePositionAtStart;
            _complete = complete;
        }

        public int QueuePositionAtStart { get; }

        public ValueTask DisposeAsync()
        {
            if (!_disposed)
            {
                _disposed = true;
                _complete();
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

public sealed record HeavyRunnerStartContext(int QueuePositionAtStart);
