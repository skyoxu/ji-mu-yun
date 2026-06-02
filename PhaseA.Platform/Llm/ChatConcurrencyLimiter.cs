using System.Collections.Concurrent;

namespace PhaseA.Platform.Llm;

public sealed class ChatConcurrencyLimiter
{
    public const int DefaultMaxConcurrentChats = 8;
    public const int DefaultMaxConcurrentChatsPerAccount = 2;

    private readonly SemaphoreSlim _globalSemaphore;
    private readonly ConcurrentDictionary<string, SemaphoreSlim> _accountSemaphores = new(StringComparer.Ordinal);

    public ChatConcurrencyLimiter()
        : this(DefaultMaxConcurrentChats, DefaultMaxConcurrentChatsPerAccount)
    {
    }

    public ChatConcurrencyLimiter(int maxConcurrentChats, int maxConcurrentChatsPerAccount = DefaultMaxConcurrentChatsPerAccount)
    {
        if (maxConcurrentChats <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxConcurrentChats));
        }

        if (maxConcurrentChatsPerAccount <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxConcurrentChatsPerAccount));
        }

        MaxConcurrentChats = maxConcurrentChats;
        MaxConcurrentChatsPerAccount = maxConcurrentChatsPerAccount;
        _globalSemaphore = new SemaphoreSlim(maxConcurrentChats, maxConcurrentChats);
    }

    public int MaxConcurrentChats { get; }

    public int MaxConcurrentChatsPerAccount { get; }

    public async ValueTask<ChatConcurrencyAcquireResult> TryAcquireAsync(string accountId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        var globalAcquired = await _globalSemaphore.WaitAsync(0, cancellationToken);
        if (!globalAcquired)
        {
            return ChatConcurrencyAcquireResult.GlobalLimitExceeded();
        }

        var accountSemaphore = _accountSemaphores.GetOrAdd(accountId, _ => new SemaphoreSlim(MaxConcurrentChatsPerAccount, MaxConcurrentChatsPerAccount));
        var accountAcquired = await accountSemaphore.WaitAsync(0, cancellationToken);
        if (!accountAcquired)
        {
            _globalSemaphore.Release();
            return ChatConcurrencyAcquireResult.AccountLimitExceeded();
        }

        return ChatConcurrencyAcquireResult.Acquired(new ChatConcurrencyLease(_globalSemaphore, accountSemaphore));
    }
}

public sealed record ChatConcurrencyAcquireResult(
    ChatConcurrencyLease? Lease,
    string? FailureCode)
{
    public static ChatConcurrencyAcquireResult Acquired(ChatConcurrencyLease lease)
    {
        return new ChatConcurrencyAcquireResult(lease, null);
    }

    public static ChatConcurrencyAcquireResult GlobalLimitExceeded()
    {
        return new ChatConcurrencyAcquireResult(null, "chat_concurrency_limit_exceeded");
    }

    public static ChatConcurrencyAcquireResult AccountLimitExceeded()
    {
        return new ChatConcurrencyAcquireResult(null, "user_chat_concurrency_limit_exceeded");
    }
}

public sealed class ChatConcurrencyLease : IAsyncDisposable
{
    private readonly SemaphoreSlim _globalSemaphore;
    private readonly SemaphoreSlim _accountSemaphore;
    private bool _disposed;

    internal ChatConcurrencyLease(SemaphoreSlim globalSemaphore, SemaphoreSlim accountSemaphore)
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
