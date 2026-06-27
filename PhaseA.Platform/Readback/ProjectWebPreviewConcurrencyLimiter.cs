using System.Collections.Concurrent;

namespace PhaseA.Platform.Readback;

public sealed class ProjectWebPreviewConcurrencyLimiter
{
    public const int DefaultMaxConcurrentWebPreviewsPerAccount = 1;

    private readonly ConcurrentDictionary<string, SemaphoreSlim> _accountSemaphores = new(StringComparer.Ordinal);

    public ProjectWebPreviewConcurrencyLimiter()
        : this(DefaultMaxConcurrentWebPreviewsPerAccount)
    {
    }

    public ProjectWebPreviewConcurrencyLimiter(int maxConcurrentWebPreviewsPerAccount)
    {
        if (maxConcurrentWebPreviewsPerAccount <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxConcurrentWebPreviewsPerAccount));
        }

        MaxConcurrentWebPreviewsPerAccount = maxConcurrentWebPreviewsPerAccount;
    }

    public int MaxConcurrentWebPreviewsPerAccount { get; }

    public async ValueTask<ProjectWebPreviewConcurrencyAcquireResult> TryAcquireAsync(
        string accountId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        var accountSemaphore = _accountSemaphores.GetOrAdd(
            accountId,
            _ => new SemaphoreSlim(MaxConcurrentWebPreviewsPerAccount, MaxConcurrentWebPreviewsPerAccount));
        var acquired = await accountSemaphore.WaitAsync(0, cancellationToken);
        return acquired
            ? ProjectWebPreviewConcurrencyAcquireResult.Acquired(new ProjectWebPreviewConcurrencyLease(accountSemaphore))
            : ProjectWebPreviewConcurrencyAcquireResult.AccountLimitExceeded();
    }
}

public sealed record ProjectWebPreviewConcurrencyAcquireResult(
    ProjectWebPreviewConcurrencyLease? Lease,
    string? FailureCode)
{
    public static ProjectWebPreviewConcurrencyAcquireResult Acquired(ProjectWebPreviewConcurrencyLease lease)
    {
        return new ProjectWebPreviewConcurrencyAcquireResult(lease, null);
    }

    public static ProjectWebPreviewConcurrencyAcquireResult AccountLimitExceeded()
    {
        return new ProjectWebPreviewConcurrencyAcquireResult(null, "user_web_preview_concurrency_limit_exceeded");
    }
}

public sealed class ProjectWebPreviewConcurrencyLease : IAsyncDisposable
{
    private readonly SemaphoreSlim _accountSemaphore;
    private bool _disposed;

    internal ProjectWebPreviewConcurrencyLease(SemaphoreSlim accountSemaphore)
    {
        _accountSemaphore = accountSemaphore;
    }

    public ValueTask DisposeAsync()
    {
        if (!_disposed)
        {
            _disposed = true;
            _accountSemaphore.Release();
        }

        return ValueTask.CompletedTask;
    }
}
