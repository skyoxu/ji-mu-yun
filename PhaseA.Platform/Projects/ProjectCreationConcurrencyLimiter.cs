using System.Collections.Concurrent;

namespace PhaseA.Platform.Projects;

public sealed class ProjectCreationConcurrencyLimiter
{
    public const int DefaultMaxConcurrentCreations = 3;
    public const int DefaultMaxConcurrentCreationsPerAccount = 1;

    private readonly SemaphoreSlim _globalSemaphore;
    private readonly ConcurrentDictionary<string, SemaphoreSlim> _accountSemaphores = new(StringComparer.Ordinal);

    public ProjectCreationConcurrencyLimiter()
        : this(DefaultMaxConcurrentCreations, DefaultMaxConcurrentCreationsPerAccount)
    {
    }

    public ProjectCreationConcurrencyLimiter(int maxConcurrentCreations, int maxConcurrentCreationsPerAccount = DefaultMaxConcurrentCreationsPerAccount)
    {
        if (maxConcurrentCreations <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxConcurrentCreations));
        }

        if (maxConcurrentCreationsPerAccount <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxConcurrentCreationsPerAccount));
        }

        MaxConcurrentCreations = maxConcurrentCreations;
        MaxConcurrentCreationsPerAccount = maxConcurrentCreationsPerAccount;
        _globalSemaphore = new SemaphoreSlim(maxConcurrentCreations, maxConcurrentCreations);
    }

    public int MaxConcurrentCreations { get; }

    public int MaxConcurrentCreationsPerAccount { get; }

    public async ValueTask<ProjectCreationConcurrencyAcquireResult> TryAcquireAsync(string accountId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        var globalAcquired = await _globalSemaphore.WaitAsync(0, cancellationToken);
        if (!globalAcquired)
        {
            return ProjectCreationConcurrencyAcquireResult.GlobalLimitExceeded();
        }

        var accountSemaphore = _accountSemaphores.GetOrAdd(accountId, _ => new SemaphoreSlim(MaxConcurrentCreationsPerAccount, MaxConcurrentCreationsPerAccount));
        var accountAcquired = await accountSemaphore.WaitAsync(0, cancellationToken);
        if (!accountAcquired)
        {
            _globalSemaphore.Release();
            return ProjectCreationConcurrencyAcquireResult.AccountLimitExceeded();
        }

        return ProjectCreationConcurrencyAcquireResult.Acquired(new ProjectCreationConcurrencyLease(_globalSemaphore, accountSemaphore));
    }
}

public sealed record ProjectCreationConcurrencyAcquireResult(
    ProjectCreationConcurrencyLease? Lease,
    string? FailureCode)
{
    public static ProjectCreationConcurrencyAcquireResult Acquired(ProjectCreationConcurrencyLease lease)
    {
        return new ProjectCreationConcurrencyAcquireResult(lease, null);
    }

    public static ProjectCreationConcurrencyAcquireResult GlobalLimitExceeded()
    {
        return new ProjectCreationConcurrencyAcquireResult(null, "project_creation_concurrency_limit_exceeded");
    }

    public static ProjectCreationConcurrencyAcquireResult AccountLimitExceeded()
    {
        return new ProjectCreationConcurrencyAcquireResult(null, "user_project_creation_concurrency_limit_exceeded");
    }
}

public sealed class ProjectCreationConcurrencyLease : IAsyncDisposable
{
    private readonly SemaphoreSlim _globalSemaphore;
    private readonly SemaphoreSlim _accountSemaphore;
    private bool _disposed;

    internal ProjectCreationConcurrencyLease(SemaphoreSlim globalSemaphore, SemaphoreSlim accountSemaphore)
    {
        _globalSemaphore = globalSemaphore;
        _accountSemaphore = accountSemaphore;
    }

    public ValueTask DisposeAsync()
    {
        if (!_disposed)
        {
            _disposed = true;
            _accountSemaphore.Release();
            _globalSemaphore.Release();
        }

        return ValueTask.CompletedTask;
    }
}
