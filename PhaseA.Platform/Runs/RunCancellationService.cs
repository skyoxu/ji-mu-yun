using System.Collections.Concurrent;

namespace PhaseA.Platform.Runs;

public sealed class RunCancellationService
{
    private readonly ConcurrentDictionary<string, CancellationTokenSource> _tokens = new(StringComparer.Ordinal);

    public CancellationTokenSource CreateLinkedTokenSource(string runId, CancellationToken cancellationToken)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);

        var source = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        _tokens.AddOrUpdate(
            runId,
            source,
            (_, existing) =>
            {
                existing.Dispose();
                return source;
            });
        return source;
    }

    public bool Cancel(string runId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        return _tokens.TryGetValue(runId, out var source) && TryCancel(source);
    }

    public bool IsCancellationRequested(string runId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        return _tokens.TryGetValue(runId, out var source) && source.IsCancellationRequested;
    }

    public void Unregister(string runId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(runId);
        if (_tokens.TryRemove(runId, out var source))
        {
            source.Dispose();
        }
    }

    private static bool TryCancel(CancellationTokenSource source)
    {
        try
        {
            source.Cancel();
            return true;
        }
        catch (ObjectDisposedException)
        {
            return false;
        }
    }
}
