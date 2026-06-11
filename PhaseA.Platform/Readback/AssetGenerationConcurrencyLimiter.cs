using System.Collections.Concurrent;

namespace PhaseA.Platform.Readback;

public sealed class AssetGenerationConcurrencyLimiter
{
    public const int DefaultMaxConcurrentAssetGenerationsPerAccount = 1;

    private readonly ConcurrentDictionary<string, SemaphoreSlim> _accountSemaphores = new(StringComparer.Ordinal);

    public AssetGenerationConcurrencyLimiter()
        : this(DefaultMaxConcurrentAssetGenerationsPerAccount)
    {
    }

    public AssetGenerationConcurrencyLimiter(int maxConcurrentAssetGenerationsPerAccount)
    {
        if (maxConcurrentAssetGenerationsPerAccount <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxConcurrentAssetGenerationsPerAccount));
        }

        MaxConcurrentAssetGenerationsPerAccount = maxConcurrentAssetGenerationsPerAccount;
    }

    public int MaxConcurrentAssetGenerationsPerAccount { get; }

    public async ValueTask<AssetGenerationConcurrencyAcquireResult> TryAcquireAsync(string accountId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        var accountSemaphore = _accountSemaphores.GetOrAdd(
            accountId,
            _ => new SemaphoreSlim(MaxConcurrentAssetGenerationsPerAccount, MaxConcurrentAssetGenerationsPerAccount));
        var acquired = await accountSemaphore.WaitAsync(0, cancellationToken);
        return acquired
            ? AssetGenerationConcurrencyAcquireResult.Acquired(new AssetGenerationConcurrencyLease(accountSemaphore))
            : AssetGenerationConcurrencyAcquireResult.AccountLimitExceeded();
    }
}

public sealed record AssetGenerationConcurrencyAcquireResult(
    AssetGenerationConcurrencyLease? Lease,
    string? FailureCode)
{
    public static AssetGenerationConcurrencyAcquireResult Acquired(AssetGenerationConcurrencyLease lease)
    {
        return new AssetGenerationConcurrencyAcquireResult(lease, null);
    }

    public static AssetGenerationConcurrencyAcquireResult AccountLimitExceeded()
    {
        return new AssetGenerationConcurrencyAcquireResult(null, "user_asset_generation_concurrency_limit_exceeded");
    }
}

public sealed class AssetGenerationConcurrencyLease : IAsyncDisposable
{
    private readonly SemaphoreSlim _accountSemaphore;
    private bool _disposed;

    internal AssetGenerationConcurrencyLease(SemaphoreSlim accountSemaphore)
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

public sealed class AssetGenerationConcurrencyLimitException : InvalidOperationException
{
    public AssetGenerationConcurrencyLimitException(string failureCode)
        : base(failureCode)
    {
        FailureCode = failureCode;
    }

    public string FailureCode { get; }
}
