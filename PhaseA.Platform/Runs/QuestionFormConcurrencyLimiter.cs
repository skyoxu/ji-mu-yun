using System.Collections.Concurrent;

namespace PhaseA.Platform.Runs;

public sealed class QuestionFormConcurrencyLimiter
{
    public const int DefaultMaxConcurrentQuestionForms = 4;
    public const int DefaultMaxConcurrentQuestionFormsPerAccount = 1;

    private readonly SemaphoreSlim _globalSemaphore;
    private readonly ConcurrentDictionary<string, SemaphoreSlim> _accountSemaphores = new(StringComparer.Ordinal);

    public QuestionFormConcurrencyLimiter()
        : this(DefaultMaxConcurrentQuestionForms, DefaultMaxConcurrentQuestionFormsPerAccount)
    {
    }

    public QuestionFormConcurrencyLimiter(
        int maxConcurrentQuestionForms,
        int maxConcurrentQuestionFormsPerAccount = DefaultMaxConcurrentQuestionFormsPerAccount)
    {
        if (maxConcurrentQuestionForms <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxConcurrentQuestionForms));
        }

        if (maxConcurrentQuestionFormsPerAccount <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxConcurrentQuestionFormsPerAccount));
        }

        MaxConcurrentQuestionForms = maxConcurrentQuestionForms;
        MaxConcurrentQuestionFormsPerAccount = maxConcurrentQuestionFormsPerAccount;
        _globalSemaphore = new SemaphoreSlim(maxConcurrentQuestionForms, maxConcurrentQuestionForms);
    }

    public int MaxConcurrentQuestionForms { get; }

    public int MaxConcurrentQuestionFormsPerAccount { get; }

    public async ValueTask<QuestionFormConcurrencyAcquireResult> TryAcquireAsync(
        string accountId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);

        var globalAcquired = await _globalSemaphore.WaitAsync(0, cancellationToken);
        if (!globalAcquired)
        {
            return QuestionFormConcurrencyAcquireResult.GlobalLimitExceeded();
        }

        var accountSemaphore = _accountSemaphores.GetOrAdd(
            accountId,
            _ => new SemaphoreSlim(MaxConcurrentQuestionFormsPerAccount, MaxConcurrentQuestionFormsPerAccount));
        var accountAcquired = await accountSemaphore.WaitAsync(0, cancellationToken);
        if (!accountAcquired)
        {
            _globalSemaphore.Release();
            return QuestionFormConcurrencyAcquireResult.AccountLimitExceeded();
        }

        return QuestionFormConcurrencyAcquireResult.Acquired(
            new QuestionFormConcurrencyLease(_globalSemaphore, accountSemaphore));
    }
}

public sealed record QuestionFormConcurrencyAcquireResult(
    QuestionFormConcurrencyLease? Lease,
    string? FailureCode)
{
    public static QuestionFormConcurrencyAcquireResult Acquired(QuestionFormConcurrencyLease lease)
    {
        return new QuestionFormConcurrencyAcquireResult(lease, null);
    }

    public static QuestionFormConcurrencyAcquireResult GlobalLimitExceeded()
    {
        return new QuestionFormConcurrencyAcquireResult(null, "gdd_question_form_concurrency_limit_exceeded");
    }

    public static QuestionFormConcurrencyAcquireResult AccountLimitExceeded()
    {
        return new QuestionFormConcurrencyAcquireResult(null, "user_gdd_question_form_concurrency_limit_exceeded");
    }
}

public sealed class QuestionFormConcurrencyLease : IAsyncDisposable
{
    private readonly SemaphoreSlim _globalSemaphore;
    private readonly SemaphoreSlim _accountSemaphore;
    private bool _disposed;

    internal QuestionFormConcurrencyLease(SemaphoreSlim globalSemaphore, SemaphoreSlim accountSemaphore)
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
